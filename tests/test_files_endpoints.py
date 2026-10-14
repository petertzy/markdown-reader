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


def test_extension_filter_keeps_no_extensionless_file_for_any_segment_form():
    # Empty raw segments and segments that normalise to empty after dropping
    # optional leading dots must never match the extensionless file.
    td = _dir_with_files()
    try:
        for raw in ("md,", "md, ", ",md", " md ", "md,.", "md,.."):
            names = _list_names(td, raw)
            assert "noext" not in names, raw
            assert "a.md" in names, raw
    finally:
        shutil.rmtree(td, ignore_errors=True)


# ── UTF-8 BOM handling ──────────────────────────────────────────────────────


def _write_bom_file(directory: str, name: str, body: bytes) -> str:
    path = os.path.join(directory, name)
    with open(path, "wb") as file_obj:
        file_obj.write(b"\xef\xbb\xbf" + body)
    return path


def test_read_endpoint_strips_a_utf8_bom():
    # Windows editors prepend a UTF-8 BOM. If it survives the read it becomes an
    # invisible first character, so "# Title" is no longer recognised as a
    # heading and the outline loses the document's title.
    td = tempfile.mkdtemp()
    try:
        path = _write_bom_file(td, "note.md", b"# Title\n\nBody.\n")
        with TestClient(app) as client:
            response = client.get("/api/files/read", params={"path": path})
        assert response.status_code == 200, response.text
        assert response.json()["content"] == "# Title\n\nBody.\n"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_convert_local_markdown_strips_a_utf8_bom():
    from backend.routers.files import _convert_local_file_to_markdown

    td = tempfile.mkdtemp()
    try:
        path = _write_bom_file(td, "note.md", b"# Title\n\nBody.\n")
        assert _convert_local_file_to_markdown(path, "note.md") == "# Title\n\nBody.\n"
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_convert_local_html_strips_a_utf8_bom():
    from backend.routers.files import _convert_local_file_to_markdown

    td = tempfile.mkdtemp()
    try:
        path = _write_bom_file(
            td, "page.html", b"<html><body><h1>Title</h1></body></html>"
        )
        converted = _convert_local_file_to_markdown(path, "page.html")
        assert "\ufeff" not in converted
        assert "Title" in converted
    finally:
        shutil.rmtree(td, ignore_errors=True)
