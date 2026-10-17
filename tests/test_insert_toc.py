"""Endpoint tests for the offline ``/api/markdown/toc`` table-of-contents route.

The deterministic generator itself is covered in ``test_markdown_toc.py``; these
tests cover the new endpoint wiring and the offline contract for issue #420:

- a document with headings returns a nested Markdown table of contents
- the generated anchors match the shared slug rules (duplicates get ``-1`` …)
- a document without headings returns an empty string rather than an error
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def _toc(content: str) -> str:
    with TestClient(app) as client:
        response = client.post("/api/markdown/toc", json={"content": content})
        assert response.status_code == 200, response.text
        return response.json()["toc"]


def test_toc_endpoint_lists_headings_with_anchors():
    toc = _toc("# Overview\n\nSome text.\n\n## Details")
    assert toc.startswith("## Table of Contents")
    assert "- [Overview](#overview)" in toc
    assert "  - [Details](#details)" in toc


def test_toc_endpoint_preserves_heading_hierarchy():
    toc = _toc("# Overview\n\n## Details\n\n### Sub")
    assert "- [Overview](#overview)" in toc
    assert "  - [Details](#details)" in toc
    assert "    - [Sub](#sub)" in toc


def test_toc_endpoint_disambiguates_duplicate_headings():
    toc = _toc("# Answers\n\n# Answers")
    assert "- [Answers](#answers)" in toc
    assert "- [Answers](#answers-1)" in toc


def test_toc_endpoint_ignores_headings_inside_code_fences():
    toc = _toc("```\n# Not a heading\n```\n\n# Real")
    assert "[Not a heading]" not in toc
    assert "- [Real](#real)" in toc


def test_toc_endpoint_empty_without_headings():
    assert _toc("Just a paragraph with no headings.") == ""
    assert _toc("") == ""
