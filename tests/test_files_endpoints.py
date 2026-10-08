"""
tests/test_files_endpoints.py
=============================
Endpoint tests for the files router's listing behavior.
"""

from __future__ import annotations

import os
import shutil
import tempfile

from fastapi.testclient import TestClient

from backend.main import app


def _dir_with_files() -> str:
    td = tempfile.mkdtemp()
    for name, body in (
        ("a.md", "markdown"),
        ("notes.txt", "text"),
        ("noext", "extensionless"),
    ):
        with open(os.path.join(td, name), "w", encoding="utf-8") as f:
            f.write(body)
    return td


def _list_names(td: str, extensions: str) -> list[str]:
    with TestClient(app) as client:
        response = client.get(
            "/api/files/list", params={"path": td, "extensions": extensions}
        )
        assert response.status_code == 200, response.text
        return sorted(entry["name"] for entry in response.json()["entries"])


def test_extension_filter_ignores_empty_segments():
    # A stray trailing comma ("md,") is the same filter as "md"; it must not
    # silently let extensionless files through because "" landed in the
    # allowlist.
    td = _dir_with_files()
    try:
        assert _list_names(td, "md") == ["a.md"]
        assert _list_names(td, "md,") == ["a.md"]
        assert _list_names(td, "md, ,txt") == ["a.md", "notes.txt"]
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_extension_filter_keeps_no_extentionless_file_for_any_segment_form():
    # "md," / "md, " / ",md" all name the same extension and never match
    # the extensionless file.
    td = _dir_with_files()
    try:
        for raw in ("md,", "md, ", ",md", " md "):
            names = _list_names(td, raw)
            assert "noext" not in names, raw
            assert "a.md" in names, raw
    finally:
        shutil.rmtree(td, ignore_errors=True)
