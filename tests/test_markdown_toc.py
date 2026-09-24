"""Tests for the AI table-of-contents generator in ``backend.ai_logic``.

These tests cover:
- Basic heading extraction at mixed levels
- Duplicate heading anchors disambiguated GitHub-style (``-1``, ``-2`` …)
- No table of contents when there are no headings
"""

from __future__ import annotations

from backend.ai_logic import _generate_markdown_toc


def test_toc_lists_headings_with_anchors():
    md = "# Overview\n\nSome text.\n\n## Details"
    toc = _generate_markdown_toc(md)
    assert toc.startswith("## Table of Contents")
    assert "- [Overview](#overview)" in toc
    assert "- [Details](#details)" in toc


def test_toc_indents_inline_items_by_level():
    md = "# Overview\n\n## Details\n\n### Sub"
    toc = _generate_markdown_toc(md)
    assert "  - [Details](#details)" in toc
    assert "    - [Sub](#sub)" in toc


def test_toc_deduplicates_duplicate_heading_anchors():
    md = "# Answers\n\n# Answers\n\n# Answers"
    toc = _generate_markdown_toc(md)
    assert "- [Answers](#answers)" in toc
    assert "- [Answers](#answers-1)" in toc
    assert "- [Answers](#answers-2)" in toc
    assert toc.count("[Answers]") == 3


def test_toc_empty_when_no_headings():
    assert _generate_markdown_toc("Just a paragraph.") == ""
    assert _generate_markdown_toc("") == ""
