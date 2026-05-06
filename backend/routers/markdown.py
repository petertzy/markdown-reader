"""
backend/routers/markdown.py
============================
Markdown rendering and conversion endpoints.
"""

from __future__ import annotations

import os
import sys
from importlib import import_module

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.renderer import render_markdown
from backend.word_count import count_words, reading_time, strip_markdown

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────────


class RenderPayload(BaseModel):
    content: str
    base_dir: str | None = None
    dark_mode: bool = False
    font_family: str = "system-ui, sans-serif"
    font_size: int = 14


class HtmlToMarkdownPayload(BaseModel):
    html: str


class PdfToMarkdownPayload(BaseModel):
    path: str
    use_docling: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/render")
def render(payload: RenderPayload):
    """Render Markdown text to a full HTML document string."""
    html = render_markdown(
        payload.content,
        base_dir=payload.base_dir,
        dark_mode=payload.dark_mode,
        font_family=payload.font_family,
        font_size=payload.font_size,
    )
    return {"html": html}


@router.post("/convert/html")
def html_to_markdown(payload: HtmlToMarkdownPayload):
    """Convert an HTML string to Markdown."""
    logic = import_module("markdown_reader.logic")

    try:
        result = logic.convert_html_to_markdown(payload.html)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"markdown": result}


@router.post("/convert/pdf")
def pdf_to_markdown(payload: PdfToMarkdownPayload):
    """Convert a local PDF file to Markdown."""
    logic = import_module("markdown_reader.logic")

    if not os.path.isfile(payload.path):
        raise HTTPException(status_code=404, detail=f"File not found: {payload.path}")
    try:
        if payload.use_docling:
            result = logic.convert_pdf_to_markdown_docling(payload.path)
        else:
            result = logic.convert_pdf_to_markdown(payload.path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"markdown": result}


@router.post("/wordcount")
def word_count(payload: RenderPayload):
    """Return word count statistics for the given Markdown text."""
    stripped = strip_markdown(payload.content)
    words = count_words(stripped)
    chars_with = len(payload.content)
    chars_without = len(
        payload.content.replace(" ", "").replace("\n", "").replace("\t", "")
    )
    return {
        "words": words,
        "chars_with_spaces": chars_with,
        "chars_without_spaces": chars_without,
        "reading_time": reading_time(words),
    }
