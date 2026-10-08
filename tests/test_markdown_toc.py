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


def test_toc_includes_setext_headings():
    # The renderer turns ``Title`` over ``=====`` into an anchored <h1> and
    # ``Sub`` over ``---`` into an anchored <h2>, so the generated table of
    # contents has to list them or the anchors cannot be reached.
    md = "Title\n=====\n\nIntro.\n\nSub\n---\n\nBody."
    toc = _generate_markdown_toc(md)
    assert toc.startswith("## Table of Contents")
    assert "- [Title](#title)" in toc
    assert "  - [Sub](#sub)" in toc


def test_toc_recognizes_two_dash_setext_underline():
    # The renderer treats a two-dash underline as a level-2 setext heading
    # (a single dash is a list item, so it must not be one).
    assert "  - [Sub](#sub)" in _generate_markdown_toc("Sub\n--\n")
    assert _generate_markdown_toc("Sub\n-\n") == ""


def test_toc_orders_setext_and_atx_by_source_position():
    md = "# First\n\nSetext\n===\n\n## Last"
    toc = _generate_markdown_toc(md)
    assert toc.index("[First]") < toc.index("[Setext]") < toc.index("[Last]")


def test_toc_setext_duplicate_anchors_disambiguated():
    md = "Same\n===\n\nSame\n==="
    toc = _generate_markdown_toc(md)
    assert "- [Same](#same)" in toc
    assert "- [Same](#same-1)" in toc


def test_toc_ignores_setext_underline_after_blank_line():
    # A run of ``=`` separated from its text by a blank line is not a setext
    # heading, so it must not invent a table of contents entry.
    assert _generate_markdown_toc("Para\n\n===") == ""


def test_toc_skips_setext_inside_code_fence():
    md = "```\ncode\n=====\n```\n# Real\n"
    toc = _generate_markdown_toc(md)
    assert "[code]" not in toc
    assert "- [Real](#real)" in toc
