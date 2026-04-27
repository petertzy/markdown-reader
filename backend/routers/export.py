"""
backend/routers/export.py
=========================
File export endpoints (HTML, DOCX, PDF).
"""

from __future__ import annotations

import os
import sys
import tempfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

router = APIRouter()


class ExportPayload(BaseModel):
    content: str  # Markdown source
    output_path: str | None = None  # Optional explicit output path
    base_dir: str | None = None  # For resolving relative image paths
    dark_mode: bool = False
    font_family: str = "system-ui, sans-serif"
    font_size: int = 14


def _make_output_path(suggested: str | None, suffix: str) -> str:
    if suggested:
        return suggested
    _, path = tempfile.mkstemp(suffix=suffix)
    return path


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/html")
def export_html(payload: ExportPayload):
    """Export Markdown to a self-contained HTML file, return its path."""
    from backend.renderer import render_markdown

    html = render_markdown(
        payload.content,
        base_dir=payload.base_dir,
        dark_mode=payload.dark_mode,
        font_family=payload.font_family,
        font_size=payload.font_size,
    )
    out_path = _make_output_path(payload.output_path, ".html")
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"path": out_path}


@router.post("/html/download")
def download_html(payload: ExportPayload):
    """Export Markdown to HTML and stream the file for download."""
    from backend.renderer import render_markdown

    html = render_markdown(
        payload.content,
        base_dir=payload.base_dir,
        dark_mode=payload.dark_mode,
        font_family=payload.font_family,
        font_size=payload.font_size,
    )
    _, tmp = tempfile.mkstemp(suffix=".html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    return FileResponse(tmp, media_type="text/html", filename="export.html")


@router.post("/docx")
def export_docx(payload: ExportPayload):
    """Export Markdown to DOCX and return the output file path."""
    # We use a minimal stub that shells out to the existing logic.  The legacy
    # export_to_docx() function requires a MarkdownReader 'app' object, so we
    # create a lightweight adapter.
    import markdown_reader.logic as legacy_logic

    export_to_docx = legacy_logic.export_to_docx

    out_path = _make_output_path(payload.output_path, ".docx")
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    # Build a minimal duck-typed adapter the legacy function can use
    class _AppAdapter:
        editors = [None]
        notebook = type(
            "NB", (), {"index": lambda self, _: 0, "select": lambda self: None}
        )()
        file_paths = [payload.base_dir]
        current_font_family = payload.font_family
        current_font_size = payload.font_size
        dark_mode = payload.dark_mode
        _markdown_content = payload.content

    adapter = _AppAdapter()

    # Monkey-patch the text area to return our content
    class _FakeTextArea:
        def get(self, *_):
            return payload.content

    adapter.editors = [_FakeTextArea()]

    # Disable any legacy GUI message boxes from the backend export path.
    def _noop(*args, **kwargs):
        return None

    if hasattr(legacy_logic, "messagebox"):
        legacy_logic.messagebox.showinfo = _noop
        legacy_logic.messagebox.showerror = _noop

    try:
        success = export_to_docx(adapter, out_path)
        if not success:
            raise RuntimeError("DOCX export failed")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"path": out_path}


@router.post("/pdf")
def export_pdf(payload: ExportPayload):
    """Export Markdown to PDF via WeasyPrint and return the output file path."""
    from backend.renderer import render_markdown
    from markdown_reader.plugins.pdf_exporter import export_markdown_to_pdf

    html = render_markdown(
        payload.content,
        base_dir=payload.base_dir,
        dark_mode=payload.dark_mode,
        font_family=payload.font_family,
        font_size=payload.font_size,
    )

    out_path = _make_output_path(payload.output_path, ".pdf")
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        export_markdown_to_pdf(html, out_path, base_url=payload.base_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"path": out_path}
