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


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/read")
def read_file(path: str = Query(..., description="Absolute path to the file")):
    """Read a file and return its content."""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
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


def _convert_docx_to_markdown(path: str) -> str:
    try:
        Document = import_module("docx").Document
    except ImportError as exc:
        raise RuntimeError("python-docx is required to convert DOCX files.") from exc

    document = Document(path)
    lines: list[str] = []

    for paragraph in document.paragraphs:
        line = _docx_paragraph_to_markdown(paragraph)
        if line:
            lines.append(line)
            lines.append("")

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            lines.append("| " + " | ".join(cells) + " |")
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
        with open(path, encoding="utf-8", errors="replace") as file_obj:
            return file_obj.read()

    if ext in {".html", ".htm"}:
        logic = import_module("markdown_reader.logic")
        with open(path, encoding="utf-8", errors="replace") as file_obj:
            return logic.convert_html_to_markdown(file_obj.read())

    if ext == ".pdf":
        logic = import_module("markdown_reader.logic")
        return logic.convert_pdf_to_markdown(path)

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
        allowed_exts = {e.strip().lower().lstrip(".") for e in extensions.split(",")}

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
        {"extension": ext, "description": desc}
        for ext, desc in _NATIVE_FORMATS.items()
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
