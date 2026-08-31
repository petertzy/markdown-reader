from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from docx import Document
from pypdf import PdfReader

from backend import citation_logic
from backend.docx_exporter import export_html_to_docx
from backend.pdf_exporter import export_markdown_to_pdf
from backend.renderer import render_markdown

SAMPLE_BIB = """
@article{doe2024,
  author = {Doe, Jane and Roe, Richard},
  title = {A Study of Something},
  journal = {Journal of Examples},
  year = {2024},
}

@book{smith2020,
  author = {Smith, John},
  title = {A Great Book},
  publisher = {Example Press},
  year = {2020},
}
"""


class TestCitationLogic(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.bib_path = Path(self.tmp_dir.name) / "library.bib"
        self.bib_path.write_text(SAMPLE_BIB, encoding="utf-8")
        self.settings_path = Path(self.tmp_dir.name) / "settings.json"
        self._patcher = mock.patch.object(
            citation_logic, "APP_SETTINGS_FILE_PATH", self.settings_path
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.tmp_dir.cleanup()

    def test_parse_bib_file_returns_expected_entries(self):
        entries = citation_logic.parse_bib_file(str(self.bib_path))
        keys = {entry["key"] for entry in entries}
        self.assertEqual(keys, {"doe2024", "smith2020"})

        doe = next(e for e in entries if e["key"] == "doe2024")
        self.assertEqual(doe["year"], "2024")
        self.assertIn("Jane Doe", doe["author"])
        self.assertIn("Richard Roe", doe["author"])

    def test_parse_missing_file_raises(self):
        with self.assertRaises(citation_logic.CitationLibraryError):
            citation_logic.parse_bib_file("/does/not/exist.bib")

    def test_load_library_persists_path_for_later_searches(self):
        citation_logic.load_citation_library(str(self.bib_path))
        self.assertTrue(
            citation_logic._same_path(
                citation_logic.get_persisted_library_path(), str(self.bib_path)
            )
        )
        entries = citation_logic.get_active_library_entries()
        self.assertEqual(len(entries), 2)

    def test_search_matches_key_author_title_and_year(self):
        citation_logic.load_citation_library(str(self.bib_path))

        self.assertEqual(len(citation_logic.search_citations("doe2024")), 1)
        self.assertEqual(len(citation_logic.search_citations("smith")), 1)
        self.assertEqual(len(citation_logic.search_citations("great book")), 1)
        self.assertEqual(len(citation_logic.search_citations("2020")), 1)
        self.assertEqual(len(citation_logic.search_citations("")), 2)
        self.assertEqual(len(citation_logic.search_citations("nonexistent")), 0)


class TestCitationSyntaxSurvivesExport(unittest.TestCase):
    """Issue #222, acceptance point 5: exporting must not break citation text."""

    CONTENT = "See [@doe2024] and [@smith2020] for details."

    def test_citation_key_survives_markdown_rendering(self):
        html = render_markdown(self.CONTENT)
        self.assertIn("[@doe2024]", html)
        self.assertIn("[@smith2020]", html)

    def test_citation_key_survives_docx_export(self):
        html = render_markdown(self.CONTENT)
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/export.docx"
            export_html_to_docx(html, output_path)
            document = Document(output_path)
            full_text = "\n".join(p.text for p in document.paragraphs)
            self.assertIn("[@doe2024]", full_text)
            self.assertIn("[@smith2020]", full_text)

    def test_citation_key_survives_pdf_export(self):
        html = render_markdown(self.CONTENT)
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/export.pdf"
            export_markdown_to_pdf(html, output_path)
            reader = PdfReader(output_path)
            full_text = "".join(page.extract_text() for page in reader.pages)
            self.assertIn("[@doe2024]", full_text)
            self.assertIn("[@smith2020]", full_text)


if __name__ == "__main__":
    unittest.main()
