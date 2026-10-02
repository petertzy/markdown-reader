from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from base64 import b64decode
from pathlib import Path
from typing import Any

CITATION_MAX_RESULTS = 50


def _get_settings_file_path() -> Path:
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support" / "MarkdownReader"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", "").strip()
        base_dir = (
            Path(appdata) / "MarkdownReader"
            if appdata
            else Path.home() / "AppData" / "Roaming" / "MarkdownReader"
        )
    else:
        base_dir = Path.home() / ".config" / "markdown-reader"
    return base_dir / "settings.json"


APP_SETTINGS_FILE_PATH = _get_settings_file_path()
_SETTINGS_KEY_LIBRARY_PATH = "citation_library_path"
_IMPORTED_LIBRARY_DIR = "citation-libraries"


class CitationLibraryError(RuntimeError):
    """Raised when a .bib file cannot be located or parsed."""


def _load_app_settings() -> dict[str, Any]:
    if not APP_SETTINGS_FILE_PATH.exists():
        return {}
    try:
        with open(APP_SETTINGS_FILE_PATH, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_app_settings(settings: dict[str, Any]) -> None:
    directory = APP_SETTINGS_FILE_PATH.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            json.dump(settings, file_obj, indent=2, ensure_ascii=False)
        os.replace(tmp_path, APP_SETTINGS_FILE_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_persisted_library_path() -> str:
    """Return the last-loaded .bib path, or '' if none is persisted."""
    path = str(_load_app_settings().get(_SETTINGS_KEY_LIBRARY_PATH, "")).strip()
    return path if path and os.path.isfile(path) else ""


def _same_path(path_a: str, path_b: str) -> bool:
    if not path_a or not path_b:
        return False
    try:
        return os.path.samefile(path_a, path_b)
    except OSError:
        # Fall back to comparing realpaths if one side doesn't exist yet.
        return os.path.realpath(path_a) == os.path.realpath(path_b)


def _set_persisted_library_path(path: str) -> None:
    settings = _load_app_settings()
    settings[_SETTINGS_KEY_LIBRARY_PATH] = path
    _save_app_settings(settings)


def _safe_library_filename(filename: str) -> str:
    name = Path(filename or "library.bib").name
    stem = Path(name).stem or "library"
    suffix = Path(name).suffix.lower()
    if suffix != ".bib":
        suffix = ".bib"
    safe_stem = "".join(
        char if char.isalnum() or char in "._-" else "_" for char in stem
    )
    return f"{safe_stem}{suffix}"


def _imported_library_path(filename: str) -> Path:
    directory = APP_SETTINGS_FILE_PATH.parent / _IMPORTED_LIBRARY_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory / _safe_library_filename(filename)


def _format_authors(raw_author: str) -> str:
    """Turn BibTeX 'Last, First and Last, First' into 'First Last, First Last'."""
    if not raw_author:
        return ""
    parts = [part.strip() for part in raw_author.split(" and ") if part.strip()]
    formatted = []
    for part in parts:
        if "," in part:
            last, _, first = part.partition(",")
            formatted.append(f"{first.strip()} {last.strip()}".strip())
        else:
            formatted.append(part)
    return ", ".join(formatted)


def _clean_bibtex_value(value: str) -> str:
    """Remove BibTeX brace-protection, keeping the author's own braces.

    BibTeX lets an author brace-protect a fragment to force capitalisation, as in
    ``{{Deep} {Learning}}``. Only that one wrapping layer is markup, and it may
    only be dropped when the whole value is wrapped. ``str.strip("{}")`` cannot
    express that: it eats characters from both ends independently, so
    ``{Deep} {Learning}`` came out as ``Deep} {Learning`` and a title that
    genuinely ends in a brace lost it.

    Unwrap the outer layer only while it is balanced, so inner braces survive.
    """
    value = value.strip()
    while (
        len(value) >= 2
        and value.startswith("{")
        and value.endswith("}")
        and _braces_are_balanced(value[1:-1])
    ):
        value = value[1:-1].strip()
    return value


def _braces_are_balanced(text: str) -> bool:
    """True when every brace in ``text`` has a matching partner."""
    depth = 0
    for char in text:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _entry_to_dict(entry: dict[str, str]) -> dict[str, str]:
    return {
        "key": entry.get("ID", ""),
        "entry_type": entry.get("ENTRYTYPE", ""),
        "title": _clean_bibtex_value(entry.get("title", "")),
        "author": _format_authors(entry.get("author", "")),
        "year": entry.get("year", ""),
        "container": entry.get("journal")
        or entry.get("booktitle")
        or entry.get("publisher", ""),
    }


def _parse_bib_stream(stream) -> list[dict[str, str]]:
    """Parse an open BibTeX text stream into lightweight citation dicts."""
    try:
        import bibtexparser
    except ImportError as exc:
        raise CitationLibraryError(
            "bibtexparser is required for citation support. "
            "Install it with: pip install bibtexparser"
        ) from exc

    try:
        database = bibtexparser.load(stream)
    except Exception as exc:
        raise CitationLibraryError(f"Could not parse BibTeX file: {exc}") from exc

    entries = [_entry_to_dict(entry) for entry in database.entries]
    entries.sort(key=lambda item: (item["author"], item["year"]))
    return entries


def parse_bib_content(content: str) -> list[dict[str, str]]:
    """Parse BibTeX *text* into citation dicts without touching the filesystem.

    Used to validate an upload before it is allowed to replace the library that
    is currently loaded.
    """
    return _parse_bib_stream(io.StringIO(content))


def parse_bib_file(path: str) -> list[dict[str, str]]:
    """Parse a .bib file into a list of lightweight citation dicts.

    Raises CitationLibraryError if the file is missing or cannot be parsed.
    """
    if not os.path.isfile(path):
        raise CitationLibraryError(f"BibTeX file not found: {path}")

    try:
        with open(path, encoding="utf-8", errors="replace") as file_obj:
            return _parse_bib_stream(file_obj)
    except OSError as exc:
        raise CitationLibraryError(f"Could not read BibTeX file: {exc}") from exc


def load_citation_library(path: str) -> list[dict[str, str]]:
    """Parse a .bib file and persist it as the active library."""
    entries = parse_bib_file(path)
    _set_persisted_library_path(os.path.abspath(path))
    return entries


def load_citation_library_content(
    filename: str, content_base64: str
) -> tuple[str, list[dict[str, str]]]:
    """Persist uploaded BibTeX content, parse it, and set it as active."""
    if not content_base64:
        raise CitationLibraryError("BibTeX content is empty.")
    try:
        content = b64decode(content_base64).decode("utf-8", errors="replace")
    except Exception as exc:
        raise CitationLibraryError(f"Could not decode BibTeX content: {exc}") from exc

    path = _imported_library_path(filename)
    # Parse before writing. The file on disk is the active library, so a
    # malformed upload must not be able to destroy the one already loaded.
    # bibtexparser reports many malformed files by simply yielding no entries
    # rather than raising, so an upload that produces nothing is rejected too.
    entries = parse_bib_content(content)
    if not entries:
        raise CitationLibraryError(
            "No BibTeX entries found in the uploaded file. The existing library "
            "was left unchanged."
        )

    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise CitationLibraryError(f"Could not save BibTeX library: {exc}") from exc

    _set_persisted_library_path(os.path.abspath(str(path)))
    return str(path), entries


def get_active_library_entries() -> list[dict[str, str]]:
    """Return entries from the currently persisted library, if any."""
    path = get_persisted_library_path()
    if not path:
        return []
    try:
        return parse_bib_file(path)
    except CitationLibraryError:
        return []


def search_citations(
    query: str, limit: int = CITATION_MAX_RESULTS
) -> list[dict[str, str]]:
    """Search the active library by key, author, or title (case-insensitive)."""
    entries = get_active_library_entries()
    query = (query or "").strip().lower()
    if not query:
        return entries[:limit]

    matches = [
        entry
        for entry in entries
        if query in entry["key"].lower()
        or query in entry["author"].lower()
        or query in entry["title"].lower()
        or query in entry["container"].lower()
        or query in entry["entry_type"].lower()
        or query in entry["year"]
    ]
    return matches[:limit]
