"""
backend/routers/files.py
========================
File system CRUD endpoints + recent-files management.

Document import is handled by a two-level converter chain:
  1. Native converters for Markdown/text, HTML, PDF, and DOCX (always used
     when the extension matches — no external dependency required).
  2. MarkItDown fallback (microsoft/markitdown) for any remaining formats
     such as Excel (.xlsx/.xls), PowerPoint (.pptx), CSV, EPUB, XML, ZIP,
     images (with OCR via optional dependencies), and audio transcription.
     MarkItDown is imported lazily; if the package is not installed the
     endpoint still works for the natively-supported types.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import sys
import tempfile
from importlib import import_module
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Formats supported natively (without MarkItDown)
# ---------------------------------------------------------------------------
_NATIVE_FORMATS: dict[str, str] = {
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".txt": "Plain Text",
    ".html": "HTML",
    ".htm": "HTML",
    ".pdf": "PDF",
    ".docx": "Word Document",
}

# ---------------------------------------------------------------------------
# Formats added by MarkItDown (informational — used by /supported-formats)
# ---------------------------------------------------------------------------
_MARKITDOWN_FORMATS: dict[str, str] = {
    ".pptx": "PowerPoint Presentation",
    ".ppt": "PowerPoint Presentation (legacy)",
    ".xlsx": "Excel Spreadsheet",
    ".xls": "Excel Spreadsheet (legacy)",
    ".csv": "CSV Spreadsheet",
    ".epub": "EPUB eBook",
    ".xml": "XML Document",
    ".zip": "ZIP Archive (contents converted individually)",
    ".wav": "WAV Audio (speech-to-text)",
    ".mp3": "MP3 Audio (speech-to-text)",
    ".jpg": "JPEG Image (OCR)",
    ".jpeg": "JPEG Image (OCR)",
    ".png": "PNG Image (OCR)",
    ".gif": "GIF Image (OCR)",
    ".bmp": "BMP Image (OCR)",
    ".tiff": "TIFF Image (OCR)",
    ".tif": "TIFF Image (OCR)",
    ".msg": "Outlook Email Message",
    ".ipynb": "Jupyter Notebook",
}

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

router = APIRouter()

_RECENT_FILES_KEY = "recent_files"
_MAX_RECENT_FILES = 10


def _settings_file_path() -> Path:
    """Return the shared desktop settings file path without importing legacy UI code."""
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


def _read_settings() -> dict:
    path = _settings_file_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_settings(data: dict) -> None:
    path = _settings_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _get_recent_entries() -> list[str]:
    settings = _read_settings()
    entries = settings.get(_RECENT_FILES_KEY, [])
    if not isinstance(entries, list):
        return []
    return [
        entry for entry in entries if isinstance(entry, str) and os.path.exists(entry)
    ][:_MAX_RECENT_FILES]


def _set_recent_entries(entries: list[str]) -> list[str]:
    settings = _read_settings()
    settings[_RECENT_FILES_KEY] = entries[:_MAX_RECENT_FILES]
    _write_settings(settings)
    return settings[_RECENT_FILES_KEY]


# ── Models ────────────────────────────────────────────────────────────────────


class WritePayload(BaseModel):
    path: str
    content: str


class ConvertToMarkdownPayload(BaseModel):
    path: str | None = None
    filename: str | None = None
    content_base64: str | None = None


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    extension: str


class ProjectPathPayload(BaseModel):
    root: str
    path: str


class RenamePayload(ProjectPathPayload):
    new_name: str


class CreateEntryPayload(BaseModel):
    root: str
    parent: str
    name: str
    is_dir: bool = False


class TransferPayload(ProjectPathPayload):
    dest_parent: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/read")
def read_file(path: str = Query(..., description="Absolute path to the file")):
    """Read a file and return its content."""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    try:
        # "utf-8-sig" strips a leading UTF-8 BOM (common for files saved on
        # Windows) and otherwise reads exactly like "utf-8". Without it the
        # invisible U+FEFF ends up in front of line 1 and hides the first
        # heading from the outline.
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
        return {"path": path, "content": content}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/write")
def write_file(payload: WritePayload):
    """Write (or overwrite) a file with the provided content."""
    path = payload.path
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload.content)
        return {"path": path, "written": True}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _docx_paragraph_to_markdown(paragraph) -> str:
    text = paragraph.text.strip()
    if not text:
        return ""

    style_name = (paragraph.style.name if paragraph.style else "").lower()
    if style_name.startswith("heading"):
        level_text = style_name.replace("heading", "").strip()
        try:
            level = max(1, min(6, int(level_text)))
        except ValueError:
            level = 1
        return f"{'#' * level} {text}"

    if "list bullet" in style_name:
        return f"- {text}"

    if "list number" in style_name:
        return f"1. {text}"

    return text


def _docx_row_cells(row) -> list[str]:
    """Return one entry per distinct cell in a DOCX table row.

    ``row.cells`` expands merged cells: a horizontally merged cell is yielded
    once per grid column it spans, so the same object appears repeatedly and its
    text would be duplicated. python-docx documents this ("If the table
    contains a span, one or more |_Cell| object references are repeated"), so
    repeats are collapsed by object identity. Two distinct cells holding the
    same text are kept as separate cells.
    """
    grid = list(row.cells)  # materialise so every yielded object stays alive
    texts: list[str] = []
    emitted: list[object] = []
    for cell in grid:
        if any(cell is already for already in emitted):
            continue
        emitted.append(cell)
        texts.append(cell.text.strip().replace("\n", " ").replace("|", "\\|"))
    return texts


def _docx_table_to_markdown(table) -> list[str]:
    """Return the Markdown lines for one DOCX table."""
    lines: list[str] = []
    for row_index, row in enumerate(table.rows):
        cells = _docx_row_cells(row)
        if not cells:
            continue
        lines.append("| " + " | ".join(cells) + " |")
        if row_index == 0:
            # GFM requires a delimiter row beneath the header. Without it
            # the renderer does not recognise a table at all and shows the
            # pipes as literal text.
            lines.append("| " + " | ".join("---" for _ in cells) + " |")
    return lines


def _convert_docx_to_markdown(path: str) -> str:
    try:
        Document = import_module("docx").Document
        Table = import_module("docx.table").Table
    except ImportError as exc:
        raise RuntimeError("python-docx is required to convert DOCX files.") from exc

    document = Document(path)
    lines: list[str] = []

    # Walk the body in document order. `document.paragraphs` and
    # `document.tables` are two independent lists, so draining one and then the
    # other moves every table to the end of the export whatever position it held
    # in the document. `iter_inner_content` yields the same top-level
    # paragraphs and tables — revision-marked paragraphs and tables nested in a
    # cell are left out by both — but interleaved the way they appear.
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            lines.extend(_docx_table_to_markdown(block))
            lines.append("")
            continue

        line = _docx_paragraph_to_markdown(block)
        if line:
            lines.append(line)
            lines.append("")

    markdown = "\n".join(lines).strip()
    return markdown


def _convert_with_markitdown(path: str, filename: str | None = None) -> str:
    """Use Microsoft MarkItDown to convert a file to Markdown.

    Raises RuntimeError if markitdown is not installed.
    Raises HTTPException(400) if the format is not supported by MarkItDown.
    """
    try:
        from markitdown import MarkItDown  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "markitdown is not installed. Run: pip install markitdown"
        ) from exc

    md_converter = MarkItDown()
    try:
        result = md_converter.convert(path)
    except Exception as exc:
        ext = Path(filename or path).suffix.lower()
        raise HTTPException(
            status_code=400,
            detail=f"MarkItDown could not convert {ext or 'unknown'} file: {exc}",
        ) from exc

    text = getattr(result, "text_content", None)
    if text is None:
        text = str(result)
    return text.strip()


def _convert_local_file_to_markdown(path: str, filename: str | None = None) -> str:
    ext = Path(filename or path).suffix.lower()

    # ── Native converters (no extra dependencies beyond what is already
    #    required by the application) ─────────────────────────────────────
    if ext in {".md", ".markdown", ".txt"}:
        with open(path, encoding="utf-8-sig", errors="replace") as file_obj:
            return file_obj.read()

    if ext in {".html", ".htm"}:
        from backend.converters import convert_html_to_markdown

        with open(path, encoding="utf-8-sig", errors="replace") as file_obj:
            return convert_html_to_markdown(file_obj.read())

    if ext == ".pdf":
        from backend.converters import convert_pdf_to_markdown

        return convert_pdf_to_markdown(path)

    if ext == ".docx":
        return _convert_docx_to_markdown(path)

    # ── MarkItDown fallback — handles 15+ additional formats ─────────────
    logger.info(
        "No native converter for '%s'; falling back to MarkItDown.", ext or "unknown"
    )
    try:
        return _convert_with_markitdown(path, filename)
    except RuntimeError as exc:
        # MarkItDown not installed: surface as a clear 400 with install hint.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/convert-to-markdown")
def convert_to_markdown(payload: ConvertToMarkdownPayload):
    """Convert a supported local or uploaded file into Markdown."""
    if payload.path:
        if not os.path.isfile(payload.path):
            raise HTTPException(
                status_code=404, detail=f"File not found: {payload.path}"
            )
        try:
            markdown = _convert_local_file_to_markdown(payload.path, payload.filename)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return {"markdown": markdown}

    if not payload.content_base64 or not payload.filename:
        raise HTTPException(
            status_code=400,
            detail="Either path or filename with content_base64 is required.",
        )

    suffix = Path(payload.filename).suffix.lower()
    try:
        file_bytes = base64.b64decode(payload.content_base64)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid base64 file content."
        ) from exc

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name

        markdown = _convert_local_file_to_markdown(tmp_path, payload.filename)
        return {"markdown": markdown}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@router.get("/list")
def list_files(
    path: str = Query(..., description="Directory to list"),
    extensions: str | None = Query(
        None,
        description="Comma-separated list of file extensions to include (e.g. md,txt)",
    ),
):
    """List entries in a directory (non-recursive, sorted: dirs first)."""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")

    allowed_exts: set[str] | None = None
    if extensions:
        allowed_exts = {
            extension
            for segment in extensions.split(",")
            if (extension := segment.strip().lower().lstrip("."))
        }

    entries: list[dict] = []
    try:
        with os.scandir(path) as it:
            for entry in sorted(it, key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith("."):
                    continue
                is_dir = entry.is_dir()
                ext = Path(entry.name).suffix.lstrip(".").lower()
                if not is_dir and allowed_exts and ext not in allowed_exts:
                    continue
                entries.append(
                    {
                        "name": entry.name,
                        "path": entry.path,
                        "is_dir": is_dir,
                        "extension": ext,
                    }
                )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"path": path, "entries": entries}


# ── Project explorer file management ─────────────────────────────────────────


def _resolve_in_project(root: str, path: str, *, allow_root: bool = False) -> Path:
    """
    Resolve ``path`` and make sure it lies inside the project folder ``root``.

    The explorer only ever acts on entries it listed from the open project, so
    anything that resolves outside it (``..`` segments, symlinks, another
    drive) is rejected rather than touched.

    :param str root: Absolute path of the open project folder.
    :param str path: Absolute path of the entry to act on.
    :param bool allow_root: Whether ``path`` may be the project folder itself.

    :return: A Path with symlinks and ``..`` segments resolved.

    :raises HTTPException: 404 if the project folder does not exist, 403 if
        ``path`` is outside it (or is the folder itself and that is not allowed).
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Project not found: {root}")

    target = Path(path).resolve()
    if target != root_path and root_path not in target.parents:
        raise HTTPException(status_code=403, detail="Path is outside the project")

    if target == root_path and not allow_root:
        raise HTTPException(
            status_code=403, detail="The project folder itself cannot be changed"
        )
    return target


def _validate_entry_name(name: str) -> str:
    """
    Check that ``name`` is a single file or folder name, not a path.

    :param str name: The name typed by the user.

    :return: The name with surrounding whitespace removed.

    :raises HTTPException: 400 if the name is empty, ``.``/``..``, or contains a
        path separator or a character Windows does not allow in file names.
    """
    cleaned = name.strip()
    if not cleaned or cleaned in {".", ".."}:
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    # Reject any special/invalid characters
    if any(char in cleaned for char in '/\\:*?"<>|') or any(
        ord(char) < 32 for char in cleaned
    ):
        raise HTTPException(
            status_code=400, detail=f"Name contains invalid characters: {cleaned}"
        )

    return cleaned


def _resolve_transfer(payload: TransferPayload) -> tuple[Path, Path]:
    """
    Resolve and check the source and destination folder of a copy or move.

    :param TransferPayload payload: The project, the entry to transfer, and the
        folder to paste it into.

    :return: The resolved source entry and destination folder.

    :raises HTTPException: 403 if either path is outside the project (or the
        source is the project folder itself), 404 if the source or destination
        is missing, 400 if a folder would be pasted into itself.
    """
    source = _resolve_in_project(payload.root, payload.path)
    dest = _resolve_in_project(payload.root, payload.dest_parent, allow_root=True)
    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Not found: {payload.path}")
    if not dest.is_dir():
        raise HTTPException(status_code=404, detail=f"Folder not found: {dest}")
    if source.is_dir() and (dest == source or source in dest.parents):
        raise HTTPException(
            status_code=400, detail="A folder cannot be pasted into itself"
        )
    return source, dest


def _unique_copy_target(dest: Path, source: Path) -> Path:
    """
    Pick a free name in ``dest`` for a copy of ``source``.

    Keeps the original name when it is free, otherwise follows VS Code:
    ``a.md`` -> ``a copy.md`` -> ``a copy 2.md``. Folders have no extension.

    :param Path dest: Folder the copy goes into.
    :param Path source: Entry being copied.

    :return: A path in ``dest`` that does not exist yet.
    """
    target = dest / source.name
    if not target.exists():
        return target

    if source.is_dir():
        stem, suffix = source.name, ""
    else:
        stem, suffix = source.stem, source.suffix
    counter = 1
    while True:
        label = " copy" if counter == 1 else f" copy {counter}"
        target = dest / f"{stem}{label}{suffix}"
        if not target.exists():
            return target
        counter += 1


def _move_to_trash(path: Path) -> None:
    """Send ``path`` to the system Recycle Bin / Trash (patched in tests)."""
    from send2trash import send2trash

    send2trash(str(path))


@router.post("/create")
def create_entry(payload: CreateEntryPayload):
    """Create an empty file or folder inside the parent path."""
    parent = _resolve_in_project(payload.root, payload.parent, allow_root=True)

    if not parent.is_dir():
        raise HTTPException(status_code=404, detail=f"Folder not found: {parent}")

    target = parent / _validate_entry_name(payload.name)
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Already exists: {target.name}")

    try:
        if payload.is_dir:
            target.mkdir()
        else:
            target.touch(exist_ok=False)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"path": str(target), "is_dir": payload.is_dir}


@router.post("/rename")
def rename_entry(payload: RenamePayload):
    """Rename a file or folder in place, keeping it in the same folder."""
    source = _resolve_in_project(payload.root, payload.path)
    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Not found: {payload.path}")

    target = source.with_name(_validate_entry_name(payload.new_name))
    if target == source:
        return {"old_path": str(source), "path": str(target)}

    # A case-only rename ("notes.md" -> "Notes.md") resolves to the same file on
    # Windows and macOS, so it is not a conflict.
    if target.exists() and not os.path.samefile(source, target):
        raise HTTPException(status_code=409, detail=f"Already exists: {target.name}")
    try:
        source.rename(target)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"old_path": str(source), "path": str(target)}


@router.post("/copy")
def copy_entry(payload: TransferPayload):
    """Copy a file or folder into ``dest_parent``, picking a free name on a clash."""
    source, dest = _resolve_transfer(payload)
    target = _unique_copy_target(dest, source)
    try:
        if source.is_dir():
            # Copy links as links so a symlink cannot pull in files from
            # outside the project.
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"path": str(target)}


@router.post("/move")
def move_entry(payload: TransferPayload):
    """Move a file or folder into ``dest_parent`` (the explorer's Cut and Paste)."""
    source, dest = _resolve_transfer(payload)
    target = dest / source.name
    if target == source:
        # Pasting back into the folder it was cut from changes nothing.
        return {"old_path": str(source), "path": str(target)}
    if target.exists():
        raise HTTPException(status_code=409, detail=f"Already exists: {target.name}")
    try:
        shutil.move(source, target)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"old_path": str(source), "path": str(target)}


@router.post("/delete")
def delete_entry(payload: ProjectPathPayload):
    """Move a file or folder to the system Recycle Bin / Trash."""
    target = _resolve_in_project(payload.root, payload.path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Not found: {payload.path}")

    try:
        _move_to_trash(target)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"path": str(target), "deleted": True}


@router.get("/recent")
def get_recent_files():
    """Return the most-recently-opened file paths."""
    return {"entries": _get_recent_entries()}


@router.post("/recent")
def add_recent_file(path: str = Query(...)):
    """Record a file as most-recently-opened."""
    normalized = os.path.normpath(os.path.abspath(path))
    entries = [entry for entry in _get_recent_entries() if entry != normalized]
    entries.insert(0, normalized)
    return {"entries": _set_recent_entries(entries)}


@router.delete("/recent")
def clear_recent_files():
    """Clear all recent-file entries."""
    _set_recent_entries([])
    return {"entries": []}


@router.get("/supported-formats")
def get_supported_formats():
    """Return all file formats that can be imported and converted to Markdown.

    The response groups formats into two categories:

    * ``native`` – always available; handled by built-in converters.
    * ``markitdown`` – handled by Microsoft MarkItDown (requires the
      ``markitdown`` package to be installed).  The ``markitdown_available``
      flag indicates whether the package is currently installed.
    """
    markitdown_available = False
    try:
        import_module("markitdown")
        markitdown_available = True
    except ImportError:
        pass

    native = [
        {"extension": ext, "description": desc} for ext, desc in _NATIVE_FORMATS.items()
    ]
    markitdown = [
        {"extension": ext, "description": desc}
        for ext, desc in _MARKITDOWN_FORMATS.items()
    ]

    return {
        "native": native,
        "markitdown": markitdown,
        "markitdown_available": markitdown_available,
    }
