from __future__ import annotations

import tempfile
import unittest
from base64 import b64encode
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

    def _parse_title(self, title_literal: str) -> str:
        """Parse a one-entry .bib through the real upload path and return title."""
        bib = f"@article{{x, title = {title_literal}, author = {{Doe, Jane}}}}"
        path = Path(self.tmp_dir.name) / "one.bib"
        path.write_text(bib, encoding="utf-8")
        entries = citation_logic.parse_bib_file(str(path))
        return entries[0]["title"]

    def test_title_keeps_inner_case_protection_braces(self):
        # BibTeX braces force capitalisation, so {Deep} {Learning} is meaningful
        # and must survive. str.strip("{}") ate from both ends independently and
        # turned this into "Deep} {Learning".
        self.assertEqual(
            self._parse_title("{{Deep} {Learning} and {Tensors}}"),
            "{Deep} {Learning} and {Tensors}",
        )

    def test_title_keeps_trailing_brace(self):
        self.assertEqual(self._parse_title("{Title {Wrapped}}"), "Title {Wrapped}")

    def test_title_unwraps_only_a_balanced_outer_layer(self):
        self.assertEqual(self._parse_title("{{Fully Wrapped}}"), "Fully Wrapped")
        self.assertEqual(self._parse_title("{Simple}"), "Simple")

    def test_title_without_braces_is_unchanged(self):
        self.assertEqual(
            self._parse_title("{Perfectly Normal Title}"), "Perfectly Normal Title"
        )

    def test_title_keeps_math_braces(self):
        self.assertIn(
            "mathcal{F}",
            self._parse_title(r"{On $\mathcal{F}$ and {DNA}}"),
        )

    def test_clean_bibtex_value_handles_unbalanced_braces(self):
        self.assertEqual(citation_logic._clean_bibtex_value("  {Odd "), "{Odd")
        self.assertEqual(citation_logic._clean_bibtex_value(""), "")
        self.assertEqual(citation_logic._clean_bibtex_value("{"), "{")

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
        self.assertEqual(len(citation_logic.search_citations("journal of examples")), 1)
        self.assertEqual(len(citation_logic.search_citations("2020")), 1)
        self.assertEqual(len(citation_logic.search_citations("")), 2)
        self.assertEqual(len(citation_logic.search_citations("nonexistent")), 0)

    def test_load_library_content_saves_and_persists_uploaded_bib(self):
        content_base64 = b64encode(SAMPLE_BIB.encode("utf-8")).decode("ascii")

        path, entries = citation_logic.load_citation_library_content(
            "../unsafe name.bib", content_base64
        )

        imported_path = Path(path)
        self.assertTrue(imported_path.is_file())
        self.assertEqual(imported_path.name, "unsafe_name.bib")
        self.assertTrue(
            citation_logic._same_path(path, citation_logic.get_persisted_library_path())
        )
        self.assertEqual({entry["key"] for entry in entries}, {"doe2024", "smith2020"})
        self.assertEqual(len(citation_logic.search_citations("doe2024")), 1)

    def test_malformed_upload_leaves_the_active_library_untouched(self):
        content_base64 = b64encode(SAMPLE_BIB.encode("utf-8")).decode("ascii")
        path, _ = citation_logic.load_citation_library_content(
            "refs.bib", content_base64
        )
        original = Path(path).read_text(encoding="utf-8")

        # bibtexparser reports most malformed input by yielding no entries
        # rather than by raising, so each of these used to overwrite the
        # library file and then fail to repopulate it.
        for garbage in (
            "@article{broken, title = {Unclosed",
            "@article{doe 2024,",
            "this is not bibtex at all",
            "\n\n   \n",
        ):
            with self.subTest(garbage=garbage):
                with self.assertRaises(citation_logic.CitationLibraryError):
                    citation_logic.load_citation_library_content(
                        "refs.bib", b64encode(garbage.encode("utf-8")).decode("ascii")
                    )

                self.assertEqual(Path(path).read_text(encoding="utf-8"), original)
                self.assertEqual(
                    {
                        entry["key"]
                        for entry in citation_logic.get_active_library_entries()
                    },
                    {"doe2024", "smith2020"},
                )

    def test_comment_only_upload_is_rejected_without_destroying_the_library(self):
        content_base64 = b64encode(SAMPLE_BIB.encode("utf-8")).decode("ascii")
        path, _ = citation_logic.load_citation_library_content(
            "refs.bib", content_base64
        )
        original = Path(path).read_text(encoding="utf-8")

        with self.assertRaises(citation_logic.CitationLibraryError):
            citation_logic.load_citation_library_content(
                "refs.bib", b64encode(b"% just a comment\n").decode("ascii")
            )

        self.assertEqual(Path(path).read_text(encoding="utf-8"), original)
        self.assertEqual(len(citation_logic.get_active_library_entries()), 2)

    def test_valid_upload_still_replaces_the_library(self):
        replacement = (
            "@misc{gamma2021, author = {Gamma, G}, title = {G}, year = {2021}}\n"
        )
        _, entries = citation_logic.load_citation_library_content(
            "refs.bib", b64encode(replacement.encode("utf-8")).decode("ascii")
        )

        self.assertEqual({entry["key"] for entry in entries}, {"gamma2021"})
        self.assertEqual(
            {entry["key"] for entry in citation_logic.get_active_library_entries()},
            {"gamma2021"},
        )

    def test_parse_bib_content_matches_parse_bib_file(self):
        from_file = citation_logic.parse_bib_file(str(self.bib_path))
        from_text = citation_logic.parse_bib_content(SAMPLE_BIB)

        self.assertEqual(from_file, from_text)

    def test_parse_bib_content_does_not_touch_the_filesystem(self):
        # Validation happens in memory so a rejected upload never creates or
        # replaces a file.
        entries = citation_logic.parse_bib_content(SAMPLE_BIB)

        self.assertEqual({entry["key"] for entry in entries}, {"doe2024", "smith2020"})
        self.assertFalse(
            (Path(self.tmp_dir.name) / "citation-libraries").exists(),
            "parse_bib_content must not create the import directory",
        )


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
