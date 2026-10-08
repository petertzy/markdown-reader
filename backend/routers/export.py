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
from starlette.background import BackgroundTask

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
        # A directory is a mistake, not a destination, and it has to be
        # rejected here rather than by the exporter: the PDF path falls back to
        # fitz.Document.save(), which removes whatever sits at the target, so
        # exporting onto an empty directory the user made for their exports
        # deleted that directory and answered 200 with its path. isdir() follows
        # symlinks, so a link to a directory is refused too.
        if suggested.endswith(("/", "\\")) or os.path.isdir(suggested):
            raise HTTPException(
                status_code=400,
                detail=f"Export destination is a directory, not a file path: {suggested}",
            )
        return suggested
    fd, path = tempfile.mkstemp(suffix=suffix)
    # mkstemp leaves the descriptor open, but the endpoints open() the path
    # with a separate handle later. Close it right away so each export does
    # not leak a file descriptor (which also lets open(path, "w") work on
    # Windows, where an open mkstemp handle blocks re-opening).
    os.close(fd)
    return path


def _remove_file(path: str) -> None:
    """Best-effort cleanup of a temporary download file after it is sent."""
    try:
        os.remove(path)
    except OSError:
        pass


def _discard_failed_export(out_path: str, requested_path: str | None) -> None:
    """Drop the file a failed export left behind.

    ``_make_output_path`` creates the output file before the exporter runs, so an
    exporter that raises leaves a zero-byte artifact in the temporary directory
    that nothing ever removes. Only clean up paths we generated ourselves: a
    caller who asked for a specific path may be holding a partial file worth
    looking at.
    """
    if not requested_path:
        _remove_file(out_path)


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
    fd, tmp = tempfile.mkstemp(suffix=".html")
    try:
        # fdopen adopts the descriptor from mkstemp, so writing the export
        # without close-on-write leaks an fd when the file is streamed.
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return FileResponse(
        tmp,
        media_type="text/html",
        filename="export.html",
        background=BackgroundTask(_remove_file, tmp),
    )


@router.post("/docx")
def export_docx(payload: ExportPayload):
    """Export Markdown to DOCX and return the output file path."""
    from backend import docx_exporter
    from backend.renderer import render_markdown

    html = render_markdown(
        payload.content,
        base_dir=payload.base_dir,
        dark_mode=payload.dark_mode,
        font_family=payload.font_family,
        font_size=payload.font_size,
    )

    out_path = _make_output_path(payload.output_path, ".docx")
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    try:
        docx_exporter.export_html_to_docx(html, out_path, base_dir=payload.base_dir)
    except Exception as exc:
        _discard_failed_export(out_path, payload.output_path)
        raise HTTPException(status_code=500, detail=str(exc))
    return {"path": out_path}


@router.post("/pdf")
def export_pdf(payload: ExportPayload):
    """Export Markdown to PDF via WeasyPrint and return the output file path."""
    from backend import pdf_exporter
    from backend.renderer import render_markdown

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
        pdf_exporter.export_markdown_to_pdf(html, out_path, base_url=payload.base_dir)
    except Exception as exc:
        _discard_failed_export(out_path, payload.output_path)
        raise HTTPException(status_code=500, detail=str(exc))
    return {"path": out_path}
