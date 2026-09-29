"""
tests/test_export_fd_leak.py
============================
Regression tests for file-descriptor and temporary-file hygiene in
backend/routers/export.py.

* ``_make_output_path`` previously ignored the descriptor returned by
  ``tempfile.mkstemp`` and leaked one fd per export that had no explicit
  output path (the open ``mkstemp`` handle also blocked ``open(path, "w")``
  on Windows).
* ``download_html`` previously opened the temp file with an unrelated handle
  (leaking the ``mkstemp`` fd) and never removed the temp file after serving
  the download.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.export import _make_output_path

SAMPLE_MARKDOWN = "# Hello\n\nSome **bold** text.\n"


def _discard_fd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


def _discard_file(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


class TestMakeOutputPathClosesDescriptor(unittest.TestCase):
    def test_mkstemp_descriptor_is_closed(self):
        fd, path = tempfile.mkstemp(suffix=".tmp")
        self.addCleanup(_discard_fd, fd)
        self.addCleanup(_discard_file, path)

        with mock.patch("tempfile.mkstemp", return_value=(fd, path)):
            result = _make_output_path(None, ".html")

        self.assertEqual(result, path)
        # fstat on a closed descriptor raises EBADF.
        with self.assertRaises(OSError):
            os.fstat(fd)

    def test_suggested_path_is_returned_unchanged(self):
        self.assertEqual(
            _make_output_path("/tmp/custom.html", ".html"), "/tmp/custom.html"
        )

    def test_suggested_path_never_touches_mkstemp(self):
        with mock.patch("tempfile.mkstemp") as mkstemp:
            result = _make_output_path("/tmp/custom.html", ".html")
        mkstemp.assert_not_called()
        self.assertEqual(result, "/tmp/custom.html")


class TestExportHtmlWritesFile(unittest.TestCase):
    def test_export_writes_html_to_returned_path(self):
        with TestClient(app) as client:
            res = client.post("/api/export/html", json={"content": SAMPLE_MARKDOWN})

        self.assertEqual(res.status_code, 200)
        exported = res.json()["path"]
        self.addCleanup(_discard_file, exported)
        with open(exported, encoding="utf-8") as f:
            self.assertIn("<h1>Hello</h1>", f.read())


class TestDownloadHtmlCleansUpTempFile(unittest.TestCase):
    def test_response_contains_rendered_html(self):
        with TestClient(app) as client:
            res = client.post(
                "/api/export/html/download", json={"content": SAMPLE_MARKDOWN}
            )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"].split(";")[0], "text/html")
        self.assertIn("<h1>Hello</h1>", res.text)
        self.assertIn("<strong>bold</strong>", res.text)

    def test_temp_file_is_removed_after_stream(self):
        captured: dict[str, str] = {}
        real_mkstemp = tempfile.mkstemp

        def trace_mkstemp(*args, **kwargs):
            fd, path = real_mkstemp(*args, **kwargs)
            captured["path"] = path
            return fd, path

        with mock.patch("tempfile.mkstemp", side_effect=trace_mkstemp):
            with TestClient(app) as client:
                res = client.post(
                    "/api/export/html/download", json={"content": SAMPLE_MARKDOWN}
                )

        self.assertEqual(res.status_code, 200)
        self.assertIn("path", captured, "download path should come from mkstemp")
        self.assertFalse(
            os.path.exists(captured["path"]),
            "temporary download file should be cleaned up after streaming",
        )


if __name__ == "__main__":
    unittest.main()
