"""
tests/test_export_directory_destination.py
==========================================
Regression tests for the export endpoints accepting a directory as a
destination.

``_make_output_path`` returned a caller-supplied path with no validation, so
``POST /api/export/pdf`` with ``output_path`` pointing at an existing **empty**
directory removed that directory and replaced it with the PDF. ``fitz
Document.save()`` removes the target first, and ``pdf_exporter`` reaches it
even when WeasyPrint is working, because it treats *any* failure from the
WeasyPrint attempt -- including the ``IsADirectoryError`` raised by the bad
destination -- as "renderer unavailable, use the fallback". The endpoint then
answered ``200 {"path": <the directory that no longer exists>}``.

An empty directory is the case that matters: it is what an exports folder is
before the first export lands, and it is the only shape with nothing to stop
the removal. A directory with contents in it survives only because ``fitz``'s
remove fails with ENOTEMPTY, which is luck rather than a guard -- so both are
pinned here.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers.export import _make_output_path

SAMPLE_MARKDOWN = "# Hello\n\nSome **bold** text.\n"
EXPORT_ENDPOINTS = ("html", "docx", "pdf")


class TestMakeOutputPathRefusesDirectories(unittest.TestCase):
    """The guard itself, which is where every endpoint's destination is decided."""

    def test_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            victim = os.path.join(tmp_dir, "Exports")
            os.makedirs(victim)

            with self.assertRaises(HTTPException) as caught:
                _make_output_path(victim, ".pdf")

            self.assertEqual(getattr(caught.exception, "status_code", None), 400)
            self.assertTrue(os.path.isdir(victim), "the guard must not touch it")

    def test_directory_is_refused_for_every_suffix(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            victim = os.path.join(tmp_dir, "Exports")
            os.makedirs(victim)

            for suffix in (".html", ".docx", ".pdf"):
                with self.subTest(suffix=suffix):
                    with self.assertRaises(HTTPException) as caught:
                        _make_output_path(victim, suffix)
                    self.assertEqual(
                        getattr(caught.exception, "status_code", None), 400
                    )

    def test_symlink_to_a_directory_is_refused(self):
        # A link is a directory as far as the filesystem is concerned, and
        # following it is exactly how a guard like this gets bypassed.
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = os.path.join(tmp_dir, "real")
            link = os.path.join(tmp_dir, "link")
            os.makedirs(target)
            os.symlink(target, link)

            with self.assertRaises(HTTPException) as caught:
                _make_output_path(link, ".pdf")

            self.assertEqual(getattr(caught.exception, "status_code", None), 400)
            self.assertTrue(os.path.isdir(target))

    def test_an_existing_file_destination_is_still_returned_unchanged(self):
        # Re-exporting over the previous export is the normal case, so the
        # destination is usually a file that already exists. The guard has to be
        # about directories only; refusing files too would break every re-export.
        with tempfile.TemporaryDirectory() as tmp_dir:
            victim = os.path.join(tmp_dir, "report.pdf")
            with open(victim, "w", encoding="utf-8") as f:
                f.write("previous export")
            self.assertEqual(_make_output_path(victim, ".pdf"), victim)
            with open(victim, encoding="utf-8") as f:
                self.assertEqual(f.read(), "previous export")

    def test_a_path_that_does_not_exist_yet_is_still_returned(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            victim = os.path.join(tmp_dir, "not-created-yet.pdf")
            self.assertEqual(_make_output_path(victim, ".pdf"), victim)


class TestExportRefusesDirectoryDestination(unittest.TestCase):
    """End to end: the directory has to still be a directory afterwards."""

    def _post_to_existing_directory(
        self, endpoint: str, *, populate: bool = False
    ) -> tuple[int, str, bool]:
        tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp_dir, True)
        victim = os.path.join(tmp_dir, f"Exports.{endpoint}")
        os.makedirs(victim)
        if populate:
            with open(os.path.join(victim, "earlier.txt"), "w", encoding="utf-8") as f:
                f.write("an export from last week")

        with TestClient(app, raise_server_exceptions=False) as client:
            # raise_server_exceptions=False so an unhandled IsADirectoryError arrives
            # as the 500 it is, instead of blowing up the test with a traceback. The
            # assertion below is about the destination's fate, and that has to be
            # observable on every endpoint, not just the ones that happen to catch.
            res = client.post(
                f"/api/export/{endpoint}",
                json={"content": SAMPLE_MARKDOWN, "output_path": victim},
            )
        return res.status_code, res.text, os.path.isdir(victim)

    def test_empty_directory_is_not_destroyed(self):
        for endpoint in EXPORT_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                status, body, still_a_directory = self._post_to_existing_directory(
                    endpoint
                )
                self.assertTrue(
                    still_a_directory,
                    f"/{endpoint} removed the directory it was pointed at",
                )
                self.assertEqual(status, 400, f"/{endpoint} response: {body[:120]}")

    def test_directory_holding_a_file_is_refused_too(self):
        for endpoint in EXPORT_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                status, _, still_a_directory = self._post_to_existing_directory(
                    endpoint, populate=True
                )
                self.assertTrue(still_a_directory)
                self.assertEqual(
                    status, 400, "the guard must not depend on the directory's contents"
                )

    def test_pdf_destination_survives_and_answers_400(self):
        # Pinned precisely for the endpoint that used to lose data.
        status, body, still_a_directory = self._post_to_existing_directory("pdf")
        self.assertTrue(still_a_directory)
        self.assertEqual(status, 400)
        self.assertIn("directory", body)


class TestOrdinaryExportStillWorks(unittest.TestCase):
    """The guard must not cost anything on the normal path."""

    def test_export_to_a_normal_path_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            for endpoint in EXPORT_ENDPOINTS:
                with self.subTest(endpoint=endpoint):
                    out_path = os.path.join(tmp_dir, f"report.{endpoint}")
                    with TestClient(app) as client:
                        res = client.post(
                            f"/api/export/{endpoint}",
                            json={"content": SAMPLE_MARKDOWN, "output_path": out_path},
                        )
                    self.assertEqual(res.status_code, 200, res.text[:200])
                    self.assertEqual(res.json()["path"], out_path)
                    self.assertTrue(os.path.isfile(out_path))

    def test_re_exporting_over_an_existing_file_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "report.html")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("stale export")
            with TestClient(app) as client:
                res = client.post(
                    "/api/export/html",
                    json={"content": SAMPLE_MARKDOWN, "output_path": out_path},
                )
            self.assertEqual(res.status_code, 200, res.text[:200])
            with open(out_path, encoding="utf-8") as f:
                self.assertNotIn("stale export", f.read())


if __name__ == "__main__":
    unittest.main()
