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
* ``export_docx`` and ``export_pdf`` create the output file before running the
  exporter, so an exporter that raised left a zero-byte (or partial) artifact in
  the temporary directory that nothing ever removed.
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


def _trace_mkstemp(captured: dict) -> mock._patch:
    """Patch ``tempfile.mkstemp`` so generated paths can be inspected."""

    real_mkstemp = tempfile.mkstemp

    def wrapper(*args, **kwargs):
        fd, path = real_mkstemp(*args, **kwargs)
        captured["path"] = path
        return fd, path

    return mock.patch("tempfile.mkstemp", side_effect=wrapper)


def _write_partial_then_fail(*args, **kwargs):
    """Stand in for an exporter that starts writing and then gives up.

    Both exporters take the destination as their second positional argument.
    """
    out_path = args[1]
    with open(out_path, "wb") as handle:
        handle.write(b"%PDF-1.7 partial")
    raise RuntimeError("exporter failed halfway")


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
            self.assertIn('<h1 id="hello">Hello</h1>', f.read())


class TestDownloadHtmlCleansUpTempFile(unittest.TestCase):
    def test_response_contains_rendered_html(self):
        with TestClient(app) as client:
            res = client.post(
                "/api/export/html/download", json={"content": SAMPLE_MARKDOWN}
            )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"].split(";")[0], "text/html")
        self.assertIn('<h1 id="hello">Hello</h1>', res.text)
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


class TestFailedExportCleansUpGeneratedFile(unittest.TestCase):
    """A failed export must not leave its generated file behind."""

    def _fail_export(self, route: str, exporter: str) -> str:
        """Run ``route`` with ``exporter`` failing; return the generated path."""
        captured: dict[str, str] = {}
        with _trace_mkstemp(captured):
            with mock.patch(exporter, side_effect=_write_partial_then_fail):
                with TestClient(app) as client:
                    res = client.post(route, json={"content": SAMPLE_MARKDOWN})

        self.assertEqual(res.status_code, 500)
        self.assertIn("path", captured, "the route should have generated a temp file")
        return captured["path"]

    def test_failed_docx_export_removes_its_temporary_file(self):
        path = self._fail_export(
            "/api/export/docx", "backend.docx_exporter.export_html_to_docx"
        )
        self.addCleanup(_discard_file, path)
        self.assertFalse(
            os.path.exists(path), "failed DOCX export left its temporary file behind"
        )

    def test_failed_pdf_export_removes_its_temporary_file(self):
        path = self._fail_export(
            "/api/export/pdf", "backend.pdf_exporter.export_markdown_to_pdf"
        )
        self.addCleanup(_discard_file, path)
        self.assertFalse(
            os.path.exists(path), "failed PDF export left its temporary file behind"
        )

    def test_failed_export_keeps_a_caller_supplied_path(self):
        """Cleanup must not delete a file the caller asked to have."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = f"{tmp_dir}/report.pdf"
            with mock.patch(
                "backend.pdf_exporter.export_markdown_to_pdf",
                side_effect=_write_partial_then_fail,
            ):
                with TestClient(app) as client:
                    res = client.post(
                        "/api/export/pdf",
                        json={"content": SAMPLE_MARKDOWN, "output_path": target},
                    )

            self.assertEqual(res.status_code, 500)
            self.assertTrue(
                os.path.exists(target),
                "a caller-supplied output path must be left for inspection",
            )

    def test_successful_pdf_export_still_keeps_its_file(self):
        with TestClient(app) as client:
            res = client.post("/api/export/pdf", json={"content": SAMPLE_MARKDOWN})

        self.assertEqual(res.status_code, 200)
        exported = res.json()["path"]
        self.addCleanup(_discard_file, exported)
        self.assertTrue(os.path.exists(exported))
        self.assertGreater(os.path.getsize(exported), 0)


if __name__ == "__main__":
    unittest.main()
