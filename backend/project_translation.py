"""
backend/project_translation.py
==============================
Translate every Markdown file in a folder as one cancellable task.

Source files are never modified. Each translation is written under an output
directory that mirrors the project layout. Code fences, inline code, URLs,
math, HTML, and front matter keys are replaced with ``<!--MR:N-->`` tokens
before the translator runs and restored afterwards, so a model cannot rewrite
them. A failure on one file does not stop the rest of the task.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.knowledge_logic import (
    IGNORED_DIRECTORIES,
    NOTE_READ_ENCODING,
    _markdown_fence,
    _split_frontmatter,
)

Translator = Callable[[str, str, str], str]

MARKDOWN_EXTENSIONS = frozenset({".md", ".markdown"})
MAX_FILE_BYTES = 1_000_000
_TOKEN_RE = re.compile(r"<!--MR:(\d+)-->")
_TOKEN_RULE = (
    "Tokens of the form <!--MR:N--> mark protected Markdown. "
    "Copy each of those tokens into the result unchanged and do not translate them."
)
_KEY_VALUE_RE = re.compile(r"^(\s*)([A-Za-z_][\w.-]*)(\s*:\s*)(.*)$")
_LIST_ITEM_RE = re.compile(r"^(\s*-\s+)(.*)$")
_URL_RE = re.compile(r"https?://[^\s<>)\]]+")
_AUTOLINK_RE = re.compile(r"^<(?:https?://|mailto:)[^>\s]+>", re.IGNORECASE)
_SCALAR_RE = re.compile(
    r"^(?:~|null|true|false|yes|no|on|off|\d+(?:\.\d+)?|https?://\S+|\S+)$",
    re.IGNORECASE,
)

_lock = threading.Lock()
_tasks: dict[str, dict[str, Any]] = {}


def default_translator(content: str, source_language: str, target_language: str) -> str:
    """Translate masked Markdown with the configured AI provider."""
    from backend.ai_logic import translate_markdown_with_ai

    return translate_markdown_with_ai(
        content,
        source_language,
        target_language,
        extra_rules=_TOKEN_RULE,
    )


def language_slug(language: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", (language or "").strip().lower()).strip("-")
    return slug or "target"


def default_output_dir(root: Path, target_language: str) -> Path:
    return (
        root.resolve()
        / ".markdown-reader"
        / "translations"
        / language_slug(target_language)
    )


class ProjectTranslationError(ValueError):
    """The project translation request cannot be started."""


def discover_markdown_files(root: Path, *, exclude: Path | None = None) -> list[Path]:
    """Return Markdown files under ``root``, skipping hidden and vendor folders."""
    base = root.resolve()
    if not base.is_dir():
        return []
    excluded = exclude.resolve() if exclude is not None else None
    found: list[Path] = []
    for directory, dirs, files in os.walk(base):
        current = Path(directory)
        dirs[:] = [
            name
            for name in dirs
            if name not in IGNORED_DIRECTORIES
            and not name.startswith(".")
            and not (current / name).is_symlink()
            and not _is_inside(current / name, excluded)
        ]
        if _is_inside(current, excluded):
            continue
        for name in files:
            if name.startswith("."):
                continue
            path = current / name
            if path.is_symlink() or not path.is_file():
                continue
            if path.suffix.lower() not in MARKDOWN_EXTENSIONS:
                continue
            if _is_inside(path, excluded):
                continue
            found.append(path)
    found.sort(key=lambda path: path.relative_to(base).as_posix())
    return found


def protect_markdown(text: str) -> tuple[str, list[str]]:
    """Replace non-prose spans with tokens. Returns masked text and originals."""
    mask = _Mask()
    split = _split_frontmatter(text)
    if split is None:
        _protect_body(text, mask)
    else:
        frontmatter, remainder = split
        opening, closing, newline = _frontmatter_delimiters(text)
        mask.add_text(opening)
        if frontmatter:
            _protect_frontmatter(frontmatter, mask)
            mask.add_text(newline)
        mask.add_text(closing)
        _protect_body(remainder, mask)
    return "".join(mask.parts), mask.slots


def restore_markdown(text: str, slots: list[str]) -> str:
    """Put protected spans back. Raises if the translator dropped or invented one."""
    seen: set[int] = set()

    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if index >= len(slots) or index in seen:
            raise ProjectTranslationError(
                "The translation duplicated or invented a protected token."
            )
        seen.add(index)
        return slots[index]

    restored = _TOKEN_RE.sub(replace, text)
    if len(seen) != len(slots):
        raise ProjectTranslationError(
            "The translation dropped a protected Markdown token."
        )
    return restored


def translate_markdown_document(
    content: str,
    source_language: str,
    target_language: str,
    translator: Translator,
) -> str:
    """Translate prose and restore protected spans. Unchanged files skip the model."""
    masked, slots = protect_markdown(content)
    if not _has_translatable_text(masked):
        return content
    translated = translator(masked, source_language, target_language)
    if not isinstance(translated, str) or not translated.strip():
        raise ProjectTranslationError("The translator returned an empty document.")
    return restore_markdown(translated, slots)


def run_project_translation(
    *,
    root: Path,
    source_language: str,
    target_language: str,
    translator: Translator | None = None,
    output_dir: Path | None = None,
    cancel_event: threading.Event | None = None,
    on_file: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Translate a project into ``output_dir`` and return a result snapshot."""
    base = _require_directory(root)
    destination = (
        output_dir.resolve()
        if output_dir is not None
        else default_output_dir(base, target_language)
    )
    _validate_output_dir(base, destination)
    files = discover_markdown_files(base, exclude=destination)
    translate = translator or default_translator
    cancel_event = cancel_event or threading.Event()
    results: list[dict[str, Any]] = [
        {
            "rel_path": path.relative_to(base).as_posix(),
            "status": "pending",
            "error": None,
        }
        for path in files
    ]
    counts = {"translated": 0, "unchanged": 0, "failed": 0, "cancelled": 0}
    status = "completed"

    for index, path in enumerate(files):
        if cancel_event.is_set():
            status = "cancelled"
            for pending in results[index:]:
                pending["status"] = "cancelled"
                counts["cancelled"] += 1
            break
        record = results[index]
        record["status"] = "running"
        if on_file is not None:
            on_file(record)
        try:
            outcome = _translate_one(
                path,
                base,
                destination,
                source_language,
                target_language,
                translate,
            )
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = str(exc) or exc.__class__.__name__
            counts["failed"] += 1
        else:
            record["status"] = outcome
            counts[outcome] += 1
        if on_file is not None:
            on_file(record)

    return {
        "status": status,
        "root": str(base),
        "output_dir": str(destination),
        "source_language": source_language or "auto",
        "target_language": target_language,
        "total": len(files),
        "completed": counts["translated"] + counts["unchanged"] + counts["failed"],
        **counts,
        "files": results,
    }


def start_project_translation(
    *,
    root: str,
    source_language: str,
    target_language: str,
    output_dir: str | None = None,
    translator: Translator | None = None,
) -> dict[str, Any]:
    """Start a background translation task and return its initial snapshot."""
    if not (target_language or "").strip():
        raise ProjectTranslationError("A target language is required.")
    base = _require_directory(Path(root).expanduser())
    destination = (
        Path(output_dir).expanduser().resolve()
        if (output_dir or "").strip()
        else default_output_dir(base, target_language)
    )
    _validate_output_dir(base, destination)
    files = discover_markdown_files(base, exclude=destination)
    task_id = uuid.uuid4().hex
    cancel_event = threading.Event()
    task: dict[str, Any] = {
        "id": task_id,
        "status": "running" if files else "completed",
        "root": str(base),
        "output_dir": str(destination),
        "source_language": source_language or "auto",
        "target_language": target_language.strip(),
        "total": len(files),
        "completed": 0,
        "translated": 0,
        "unchanged": 0,
        "failed": 0,
        "cancelled": 0,
        "files": [
            {
                "rel_path": path.relative_to(base).as_posix(),
                "status": "pending",
                "error": None,
            }
            for path in files
        ],
        "cancel_event": cancel_event,
        "thread": None,
    }
    with _lock:
        _tasks[task_id] = task
    if not files:
        return _public_snapshot(task)

    def runner() -> None:
        try:
            result = run_project_translation(
                root=base,
                source_language=source_language,
                target_language=target_language,
                translator=translator,
                output_dir=destination,
                cancel_event=cancel_event,
                on_file=_remember_file(task_id),
            )
        except Exception as exc:
            result = {
                "status": "failed",
                "root": str(base),
                "output_dir": str(destination),
                "source_language": source_language or "auto",
                "target_language": target_language.strip(),
                "total": len(files),
                "completed": 0,
                "translated": 0,
                "unchanged": 0,
                "failed": len(files),
                "cancelled": 0,
                "files": [
                    {
                        "rel_path": path.relative_to(base).as_posix(),
                        "status": "failed",
                        "error": str(exc) or exc.__class__.__name__,
                    }
                    for path in files
                ],
            }
        with _lock:
            current = _tasks[task_id]
            current.update(result)
            current["id"] = task_id

    thread = threading.Thread(
        target=runner, name=f"project-translation-{task_id}", daemon=True
    )
    task["thread"] = thread
    thread.start()
    return _public_snapshot(task)


def get_project_translation(task_id: str) -> dict[str, Any] | None:
    with _lock:
        task = _tasks.get(task_id)
        return None if task is None else _public_snapshot(task)


def cancel_project_translation(task_id: str) -> dict[str, Any] | None:
    with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return None
        event = task["cancel_event"]
        if task["status"] == "running":
            event.set()
        return _public_snapshot(task)


def wait_for_project_translation(task_id: str, timeout: float = 5) -> dict[str, Any]:
    """Block until a background task finishes. Used by tests."""
    with _lock:
        task = _tasks.get(task_id)
        thread = None if task is None else task.get("thread")
    if task is None:
        raise ProjectTranslationError(f"Unknown translation task: {task_id}")
    if thread is not None:
        thread.join(timeout)
    snapshot = get_project_translation(task_id)
    if snapshot is None:
        raise ProjectTranslationError(f"Unknown translation task: {task_id}")
    return snapshot


def reset_project_translations() -> None:
    """Drop in-memory tasks. Used by tests."""
    with _lock:
        _tasks.clear()


def _remember_file(task_id: str) -> Callable[[dict[str, Any]], None]:
    def update(record: dict[str, Any]) -> None:
        with _lock:
            task = _tasks.get(task_id)
            if task is None:
                return
            for current in task["files"]:
                if current["rel_path"] == record["rel_path"]:
                    current["status"] = record["status"]
                    current["error"] = record["error"]
                    break
            files = task["files"]
            task["translated"] = sum(item["status"] == "translated" for item in files)
            task["unchanged"] = sum(item["status"] == "unchanged" for item in files)
            task["failed"] = sum(item["status"] == "failed" for item in files)
            task["cancelled"] = sum(item["status"] == "cancelled" for item in files)
            task["completed"] = task["translated"] + task["unchanged"] + task["failed"]

    return update


def _public_snapshot(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task["id"],
        "status": task["status"],
        "root": task["root"],
        "output_dir": task["output_dir"],
        "source_language": task["source_language"],
        "target_language": task["target_language"],
        "total": task["total"],
        "completed": task["completed"],
        "translated": task["translated"],
        "unchanged": task["unchanged"],
        "failed": task["failed"],
        "cancelled": task["cancelled"],
        "files": [dict(item) for item in task["files"]],
    }


def _translate_one(
    path: Path,
    root: Path,
    output_dir: Path,
    source_language: str,
    target_language: str,
    translator: Translator,
) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ProjectTranslationError(
            f"{path.name} is larger than {MAX_FILE_BYTES} bytes."
        )
    original = path.read_text(encoding=NOTE_READ_ENCODING)
    if not original.strip():
        _write_output(path, root, output_dir, original)
        return "unchanged"
    translated = translate_markdown_document(
        original, source_language, target_language, translator
    )
    _write_output(path, root, output_dir, translated)
    return "unchanged" if translated == original else "translated"


def _write_output(source: Path, root: Path, output_dir: Path, content: str) -> None:
    relative = source.resolve().relative_to(root.resolve())
    destination = (output_dir / relative).resolve()
    output_root = output_dir.resolve()
    if not destination.is_relative_to(output_root):
        raise ProjectTranslationError("Refusing to write outside the output directory.")
    if destination == source.resolve():
        raise ProjectTranslationError("Refusing to overwrite a source file.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=destination.parent,
        prefix=".translation-",
        suffix=".tmp",
        delete=False,
    )
    try:
        with temporary:
            temporary.write(content)
        os.replace(temporary.name, destination)
    except Exception:
        try:
            os.unlink(temporary.name)
        except OSError:
            pass
        raise


def _require_directory(root: Path) -> Path:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise ProjectTranslationError(f"Project folder does not exist: {root}")
    return resolved


def _validate_output_dir(root: Path, output_dir: Path) -> None:
    root_resolved = root.resolve()
    output_resolved = output_dir.resolve()
    if output_resolved == root_resolved or root_resolved.is_relative_to(
        output_resolved
    ):
        raise ProjectTranslationError(
            "The output directory must not contain the project sources."
        )


def _is_inside(path: Path, parent: Path | None) -> bool:
    if parent is None:
        return False
    try:
        path.resolve().relative_to(parent)
    except (OSError, ValueError):
        return False
    return True


def _has_translatable_text(masked: str) -> bool:
    return bool(re.search(r"[^\W\d_]", _TOKEN_RE.sub(" ", masked), flags=re.UNICODE))


def _frontmatter_delimiters(text: str) -> tuple[str, str, str]:
    newline = "\r\n" if text.startswith("---\r\n") else "\n"
    return f"---{newline}", f"---{newline}", newline


def _protect_frontmatter(frontmatter: str, mask: _Mask) -> None:
    if frontmatter == "":
        return
    lines = frontmatter.split("\n")
    for index, line in enumerate(lines):
        ending = "\n" if index < len(lines) - 1 else ""
        key_match = _KEY_VALUE_RE.match(line)
        if key_match:
            indent, key, separator, value = key_match.groups()
            mask.add_text(indent)
            mask.add_protected(key)
            mask.add_text(separator)
            _protect_frontmatter_value(value, mask)
        else:
            item_match = _LIST_ITEM_RE.match(line)
            if item_match and _is_opaque_scalar(item_match.group(2).strip()):
                mask.add_text(item_match.group(1))
                mask.add_protected(item_match.group(2))
            else:
                _protect_inline(line, mask)
        mask.add_text(ending)


def _protect_frontmatter_value(value: str, mask: _Mask) -> None:
    stripped = value.strip()
    if _is_opaque_scalar(stripped):
        mask.add_protected(value)
        return
    _protect_inline(value, mask)


def _is_opaque_scalar(value: str) -> bool:
    if not value:
        return False
    unquoted = value
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        unquoted = value[1:-1]
    return _SCALAR_RE.fullmatch(unquoted) is not None and " " not in unquoted


def _protect_body(text: str, mask: _Mask) -> None:
    if text == "":
        return
    lines = text.split("\n")
    fence: tuple[str, int] | None = None
    math_block = False
    block: list[str] = []
    for index, line in enumerate(lines):
        ending = "\n" if index < len(lines) - 1 else ""
        piece = f"{line}{ending}"
        if fence is not None:
            block.append(piece)
            if _markdown_fence(line, fence) is not None:
                mask.add_protected("".join(block))
                fence = None
                block = []
            continue
        if math_block:
            block.append(piece)
            if line.strip() == "$$":
                mask.add_protected("".join(block))
                math_block = False
                block = []
            continue
        opened = _markdown_fence(line)
        if opened is not None and line.strip()[:1] in {"`", "~"}:
            fence = opened
            block = [piece]
            continue
        if line.strip() == "$$":
            math_block = True
            block = [piece]
            continue
        _protect_inline(line, mask)
        mask.add_text(ending)
    if block:
        mask.add_protected("".join(block))


def _protect_inline(line: str, mask: _Mask) -> None:
    index = 0
    length = len(line)
    while index < length:
        if line.startswith("<!--", index):
            end = line.find("-->", index + 4)
            end = length if end < 0 else end + 3
            mask.add_protected(line[index:end])
            index = end
            continue
        if line[index] == "`":
            consumed = _consume_code_span(line, index)
            if consumed > index:
                mask.add_protected(line[index:consumed])
                index = consumed
                continue
        if line[index] == "$":
            consumed = _consume_math(line, index)
            if consumed > index:
                mask.add_protected(line[index:consumed])
                index = consumed
                continue
        if line[index] == "<":
            autolink = _AUTOLINK_RE.match(line, index)
            if autolink:
                mask.add_protected(autolink.group(0))
                index = autolink.end()
                continue
            if _looks_like_html_tag(line, index):
                end = line.find(">", index + 1)
                end = length if end < 0 else end + 1
                mask.add_protected(line[index:end])
                index = end
                continue
        if line.startswith("![", index) or line.startswith("[", index):
            consumed = _consume_link(line, index, mask)
            if consumed > index:
                index = consumed
                continue
        url = _URL_RE.match(line, index)
        if url and (index == 0 or line[index - 1] not in "([])"):
            mask.add_protected(url.group(0))
            index = url.end()
            continue
        next_special = _next_special(line, index + 1)
        mask.add_text(line[index:next_special])
        index = next_special


def _consume_code_span(line: str, start: int) -> int:
    marker_length = 0
    while start + marker_length < len(line) and line[start + marker_length] == "`":
        marker_length += 1
    if marker_length >= 3:
        return start
    closer = line.find("`" * marker_length, start + marker_length)
    if closer < 0:
        return start
    return closer + marker_length


def _consume_math(line: str, start: int) -> int:
    if start > 0 and line[start - 1] == "\\":
        return start
    if line.startswith("$$", start):
        closer = line.find("$$", start + 2)
        return start if closer < 0 else closer + 2
    if start + 1 < len(line) and line[start + 1].isspace():
        return start
    closer = start + 1
    while closer < len(line):
        if line[closer] == "$" and line[closer - 1] != "\\":
            if closer == start + 1 or line[closer - 1].isspace():
                return start
            return closer + 1
        closer += 1
    return start


def _looks_like_html_tag(line: str, start: int) -> bool:
    if start + 1 >= len(line):
        return False
    next_char = line[start + 1]
    return next_char in "!/" or next_char.isalpha()


def _consume_link(line: str, start: int, mask: _Mask) -> int:
    """Protect destinations and reference ids. Leave visible prose in place.

    Returns ``start`` when the brackets are ordinary text, so the caller keeps
    scanning. On a real link, protected spans are written to ``mask``.
    """
    image = line.startswith("![", start)
    label_start = start + (2 if image else 1)
    label_end = _find_unescaped(line, "]", label_start)
    if label_end < 0:
        return start
    following = label_end + 1
    if following >= len(line):
        return start

    if line[following] == "(":
        destination_end = _link_destination_end(line, following + 1)
        if destination_end < 0:
            return start
        _protect_link_label(line, label_start, label_end, image, mask)
        mask.add_text("(")
        _protect_link_destination(line[following + 1 : destination_end], mask)
        closer = line.find(")", destination_end)
        if closer < 0:
            _protect_inline(line[destination_end:], mask)
            return len(line)
        _protect_inline(line[destination_end:closer], mask)
        mask.add_text(")")
        return closer + 1

    if line[following] == "[":
        reference_end = _find_unescaped(line, "]", following + 1)
        if reference_end < 0:
            return start
        _protect_link_label(line, label_start, label_end, image, mask)
        mask.add_text("[")
        mask.add_protected(line[following + 1 : reference_end])
        mask.add_text("]")
        return reference_end + 1

    if line[following] == ":" and not image:
        mask.add_text("[")
        mask.add_protected(line[label_start:label_end])
        mask.add_text("]:")
        rest = line[following + 1 :]
        leading = rest[: len(rest) - len(rest.lstrip(" \t"))]
        mask.add_text(leading)
        destination, remainder = _split_destination(rest.lstrip(" \t"))
        _protect_link_destination(destination, mask)
        _protect_inline(remainder, mask)
        return len(line)

    return start


def _protect_link_label(
    line: str,
    label_start: int,
    label_end: int,
    image: bool,
    mask: _Mask,
) -> None:
    mask.add_text("![" if image else "[")
    _protect_inline(line[label_start:label_end], mask)
    mask.add_text("]")


def _split_destination(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    if text[0] == "<":
        end = text.find(">")
        if end < 0:
            return text, ""
        return text[: end + 1], text[end + 1 :]
    index = 0
    while index < len(text) and not text[index].isspace():
        index += 1
    return text[:index], text[index:]


def _link_destination_end(line: str, start: int) -> int:
    """Index of the first character after an inline link destination."""
    if start >= len(line):
        return -1
    if line[start] == "<":
        end = line.find(">", start + 1)
        return -1 if end < 0 else end + 1
    index = start
    while index < len(line) and not line[index].isspace() and line[index] != ")":
        index += 1
    return index if index > start else -1


def _protect_link_destination(destination: str, mask: _Mask) -> None:
    if destination == "":
        return
    if (
        destination.startswith("<")
        and destination.endswith(">")
        and len(destination) >= 2
    ):
        mask.add_text("<")
        mask.add_protected(destination[1:-1])
        mask.add_text(">")
        return
    mask.add_protected(destination)


def _next_special(line: str, start: int) -> int:
    specials = set("`<$[!")
    index = start
    while index < len(line) and line[index] not in specials:
        if line.startswith("http://", index) or line.startswith("https://", index):
            break
        if line.startswith("<!--", index):
            break
        index += 1
    return index


class _Mask:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.slots: list[str] = []

    def add_text(self, text: str) -> None:
        if not text:
            return
        cursor = 0
        for match in _TOKEN_RE.finditer(text):
            if match.start() > cursor:
                self.parts.append(text[cursor : match.start()])
            self.add_protected(match.group(0))
            cursor = match.end()
        if cursor < len(text):
            self.parts.append(text[cursor:])

    def add_protected(self, text: str) -> None:
        self.parts.append(f"<!--MR:{len(self.slots)}-->")
        self.slots.append(text)


def _find_unescaped(line: str, character: str, start: int) -> int:
    index = start
    while index < len(line):
        if line[index] == "\\" and index + 1 < len(line):
            index += 2
            continue
        if line[index] == character:
            return index
        index += 1
    return -1
