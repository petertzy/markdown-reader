"""
backend/routers/markdown.py
============================
Markdown rendering and conversion endpoints.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
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


class OutlinePayload(BaseModel):
    """Input for the /outline endpoint."""

    content: str


# ── Heading helpers ───────────────────────────────────────────────────────────

# Matches ATX headings: `# Heading` … `###### Heading`
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+\s*)?$", re.MULTILINE)

# Characters that should be stripped when building a GitHub-style slug
_NON_WORD_RE = re.compile(r"[^\w\s-]")
_WHITESPACE_RE = re.compile(r"\s+")


def _slugify(text: str) -> str:
    """Produce a GitHub-compatible heading anchor from heading text."""
    text = text.lower()
    # Normalise Unicode so accented chars are preserved but combining marks
    # that have no direct ASCII equivalent are stripped.
    text = unicodedata.normalize("NFC", text)
    text = _NON_WORD_RE.sub("", text)
    text = _WHITESPACE_RE.sub("-", text.strip())
    return text


def _extract_outline(markdown: str) -> list[dict]:
    """Return a flat list of heading nodes extracted from *markdown*.

    Each node has the following keys:

    * ``level``  – heading depth (1–6)
    * ``text``   – raw heading text (inline markup stripped)
    * ``anchor`` – GitHub-style slug usable as ``#anchor`` in URLs / scroll targets
    * ``line``   – 1-based line number of the heading in the source text
    """
    outline: list[dict] = []
    # Track slugs so duplicates get the ``-1``, ``-2`` … suffix (GitHub rule).
    slug_counts: dict[str, int] = {}

    for match in _ATX_HEADING_RE.finditer(markdown):
        level = len(match.group(1))
        raw_text = match.group(2).strip()
        # Strip common inline Markdown so the label is readable plain text.
        plain = re.sub(r"\*{1,2}|_{1,2}|`|~~|!\[.*?\]\(.*?\)|\[([^\]]*)\]\(.*?\)", r"\1", raw_text)
        plain = plain.strip()

        base_slug = _slugify(plain)
        count = slug_counts.get(base_slug, 0)
        slug = base_slug if count == 0 else f"{base_slug}-{count}"
        slug_counts[base_slug] = count + 1

        line_number = markdown[: match.start()].count("\n") + 1

        outline.append(
            {
                "level": level,
                "text": plain,
                "anchor": slug,
                "line": line_number,
            }
        )

    return outline


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


@router.post("/outline")
def get_outline(payload: OutlinePayload):
    """Extract the document outline (table of contents) from Markdown text.

    Returns a flat list of heading nodes.  Each node contains:

    * ``level``  – heading depth (1–6, where 1 is ``#`` and 6 is ``######``)
    * ``text``   – plain-text heading label (inline markup stripped)
    * ``anchor`` – GitHub-compatible slug suitable for use as a scroll target
                   or ``#fragment`` in a URL
    * ``line``   – 1-based line number of the heading in the source document,
                   enabling the frontend to implement click-to-scroll behaviour

    This endpoint enables a document-outline / table-of-contents panel that
    gives users a bird's-eye view of the document structure and allows quick
    navigation between sections — a productivity feature common in editors
    such as Typora, Obsidian, and VS Code's Markdown preview.

    Example response::

        {
            "outline": [
                {"level": 1, "text": "Introduction", "anchor": "introduction", "line": 1},
                {"level": 2, "text": "Background", "anchor": "background", "line": 5},
                {"level": 2, "text": "Goals", "anchor": "goals", "line": 10}
            ],
            "heading_count": 3
        }
    """
    outline = _extract_outline(payload.content)
    return {"outline": outline, "heading_count": len(outline)}
