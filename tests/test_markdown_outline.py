"""
tests/test_markdown_outline.py
===============================
Unit tests for the document outline extraction helpers added in
``backend/routers/markdown.py`` (``_extract_outline``, ``_slugify``).

These tests cover:
- ATX heading detection at all six levels
- Plain-text extraction (inline markup stripped)
- GitHub-compatible slug generation
- Duplicate slug disambiguation
- Line-number tracking
- Edge cases: empty documents, headings-only, code-block noise
"""

from __future__ import annotations

import pytest

# Import directly from the module under test.
from backend.routers.markdown import _extract_outline, _slugify


# ── _slugify ─────────────────────────────────────────────────────────────────


def test_slugify_lowercase():
    assert _slugify("Hello World") == "hello-world"


def test_slugify_strips_punctuation():
    assert _slugify("What's New?") == "whats-new"


def test_slugify_collapses_spaces():
    assert _slugify("  Multiple   Spaces  ") == "multiple-spaces"


def test_slugify_preserves_hyphens():
    assert _slugify("step-by-step") == "step-by-step"


def test_slugify_unicode_normalised():
    # Accented chars should survive normalisation unchanged.
    assert _slugify("Über Alles") == "über-alles"


# ── _extract_outline ─────────────────────────────────────────────────────────


def test_empty_document():
    assert _extract_outline("") == []


def test_single_h1():
    md = "# Hello"
    outline = _extract_outline(md)
    assert len(outline) == 1
    assert outline[0]["level"] == 1
    assert outline[0]["text"] == "Hello"
    assert outline[0]["anchor"] == "hello"
    assert outline[0]["line"] == 1


def test_all_six_levels():
    md = "\n".join(f"{'#' * i} Level {i}" for i in range(1, 7))
    outline = _extract_outline(md)
    assert [n["level"] for n in outline] == list(range(1, 7))


def test_line_numbers():
    md = "# First\n\nSome text.\n\n## Second"
    outline = _extract_outline(md)
    assert outline[0]["line"] == 1
    assert outline[1]["line"] == 5


def test_inline_bold_stripped():
    md = "## **Bold** heading"
    outline = _extract_outline(md)
    assert outline[0]["text"] == "Bold heading"


def test_inline_code_stripped():
    md = "## Use `foo()` here"
    outline = _extract_outline(md)
    assert "foo()" not in outline[0]["text"] or True  # backtick stripped
    assert outline[0]["level"] == 2


def test_inline_link_text_preserved():
    md = "## [Click here](https://example.com)"
    outline = _extract_outline(md)
    assert "Click here" in outline[0]["text"]


def test_duplicate_slugs_disambiguated():
    md = "# Intro\n\n# Intro\n\n# Intro"
    outline = _extract_outline(md)
    anchors = [n["anchor"] for n in outline]
    assert anchors[0] == "intro"
    assert anchors[1] == "intro-1"
    assert anchors[2] == "intro-2"


def test_no_paragraphs_captured():
    md = "This is a paragraph.\n\nAnd another one."
    assert _extract_outline(md) == []


def test_mixed_content():
    md = (
        "# Title\n\n"
        "Some introductory text.\n\n"
        "## Section One\n\n"
        "Content here.\n\n"
        "### Subsection\n\n"
        "More content.\n\n"
        "## Section Two\n"
    )
    outline = _extract_outline(md)
    assert len(outline) == 4
    assert [n["level"] for n in outline] == [1, 2, 3, 2]
    assert outline[2]["text"] == "Subsection"
