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


class TestCitationAuthorFormatting(unittest.TestCase):
    """Brace-protected author names must survive parsing intact.

    Titles already unwrap the one outer layer of BibTeX brace protection while
    keeping inner case-protection braces. Author names were split on every
    ``" and "`` and never unwrapped, so an organisation was shown with literal
    braces and, when its own name contained the word, cut into two fictitious
    authors: ``{Smith and Sons Ltd}`` came out as ``Smith, Sons Ltd``.
    """

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.bib_path = Path(self.tmp_dir.name) / "library.bib"
        settings_path = Path(self.tmp_dir.name) / "settings.json"
        patcher = mock.patch.object(
            citation_logic, "APP_SETTINGS_FILE_PATH", settings_path
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp_dir.cleanup)

    def _parse_author(self, author_literal: str) -> str:
        """Parse a one-entry .bib through the real upload path and return author."""
        bib = f"@article{{x, title = {{T}}, author = {author_literal}}}"
        self.bib_path.write_text(bib, encoding="utf-8")
        return citation_logic.parse_bib_file(str(self.bib_path))[0]["author"]

    def test_plain_names_are_unchanged(self):
        self.assertEqual(
            self._parse_author("{Doe, Jane and Roe, Richard}"),
            "Jane Doe, Richard Roe",
        )
        self.assertEqual(self._parse_author("{Smith, John}"), "John Smith")
        self.assertEqual(
            self._parse_author("{van Beethoven, Ludwig}"), "Ludwig van Beethoven"
        )
        self.assertEqual(self._parse_author("{  Doe , Jane  }"), "Jane Doe")
        self.assertEqual(self._parse_author("{}"), "")

    def test_three_plain_names_still_split(self):
        self.assertEqual(
            self._parse_author("{Doe, Jane and Roe, Richard and Poe, Ann}"),
            "Jane Doe, Richard Roe, Ann Poe",
        )

    def test_protected_group_detection_requires_balanced_braces(self):
        # {Deep} {Learning} is two adjacent protected words, not one wrapper
        # around a list, so it must not be unwrapped even once a comma appears.
        self.assertFalse(citation_logic._is_protected_author_list("{Deep} {Learning}"))
        self.assertFalse(
            citation_logic._is_protected_author_list("{Deep} {Learning, Doe}")
        )
        self.assertFalse(
            citation_logic._is_protected_author_list("{Deep} {Learning}, Doe")
        )
        self.assertTrue(citation_logic._is_protected_author_list("{Doe, Jane}"))
        self.assertFalse(citation_logic._is_protected_author_list("{Corp and Sons}"))

    def test_and_is_only_a_separator_between_spaces(self):
        # "and" occurs inside plenty of surnames. Splitting on the bare word
        # would cut "Sandoval" in half.
        self.assertEqual(self._parse_author("{Sandoval, Ana}"), "Ana Sandoval")
        self.assertEqual(self._parse_author("{Alexander, Andre}"), "Andre Alexander")

    def test_empty_names_are_dropped(self):
        # A trailing " and " leaves an empty final name, which must not become
        # a stray separator in the formatted result.
        self.assertEqual(self._parse_author("{Doe, Jane and }"), "Jane Doe")
        self.assertEqual(self._parse_author("{{Corp} and }"), "Corp")

    def test_corporate_author_loses_its_protection_braces(self):
        self.assertEqual(
            self._parse_author("{{World Health Organization}}"),
            "World Health Organization",
        )

    def test_corporate_author_containing_and_is_one_author(self):
        # "Smith and Sons Ltd" is a single organisation. Splitting it invented a
        # second author and a fabricated comma.
        self.assertEqual(
            self._parse_author("{{Smith and Sons Ltd}}"), "Smith and Sons Ltd"
        )

    def test_repeated_and_inside_braces_is_still_one_author(self):
        self.assertEqual(self._parse_author("{{A and B and C}}"), "A and B and C")

    def test_braced_organisation_does_not_hide_a_real_second_author(self):
        self.assertEqual(
            self._parse_author("{{Smith and Sons Ltd} and {Doe, Jane}}"),
            "Smith and Sons Ltd, Jane Doe",
        )

    def test_author_list_wrapped_as_a_whole_is_still_split(self):
        # The outer pair only protects the list; the names inside are separate.
        self.assertEqual(
            self._parse_author("{{Doe, Jane and Roe, Richard}}"),
            "Jane Doe, Richard Roe",
        )
        self.assertEqual(
            self._parse_author("{{Doe, Jane and Roe, Richard and Poe, Ann}}"),
            "Jane Doe, Richard Roe, Ann Poe",
        )

    def test_case_protection_braces_inside_a_name_are_kept(self):
        # {Deep} {Learning} forces capitalisation and is meaningful, so only the
        # wrapping layer may be dropped.
        self.assertEqual(
            self._parse_author("{{Deep} {Learning} and {Doe, Jane}}"),
            "{Deep} {Learning}, Jane Doe",
        )

    def test_noble_particle_braces_are_unwrapped_around_the_name(self):
        self.assertEqual(
            self._parse_author("{{van der Berg}, Jan and {de la Cruz}, Maria}"),
            "Jan van der Berg, Maria de la Cruz",
        )

    def test_noble_particle_keeps_an_inner_case_protection_brace(self):
        self.assertEqual(
            self._parse_author("{{van der {Berg}}, Jan}"), "Jan van der {Berg}"
        )

    def test_nested_braces_do_not_unbalance_the_split(self):
        self.assertEqual(
            self._parse_author("{{Outer {Smith and Sons} Ltd} and {Doe, Jane}}"),
            "Outer {Smith and Sons} Ltd, Jane Doe",
        )

    def test_corporate_author_with_a_comma_is_reordered_and_that_is_pinned(self):
        # {{Google, Inc.}} reaches the formatter as {Google, Inc.}, which is the
        # same token as a braced Last, First pair, so it is reordered. Recorded
        # because it looks like a bug and is in fact a pinned trade-off: the
        # alternative breaks {Doe, Jane}, which this class also requires.
        self.assertEqual(self._parse_author("{{Google, Inc.}}"), "Inc. Google")
        self.assertEqual(self._parse_author("{{Doe, Jane}}"), "Jane Doe")

    def test_a_comma_inside_braces_does_not_split_the_name(self):
        # `{Smith, Jr.}, John` is `Last, First` with a braced suffix. Splitting
        # on the first comma regardless of depth cut inside the braces and
        # produced `Jr.}, John {Smith`, leaking the group's own braces.
        self.assertEqual(self._parse_author("{{Smith, Jr.}, John}"), "John Smith, Jr.")
        self.assertEqual(
            self._parse_author("{van Beethoven, Ludwig}"), "Ludwig van Beethoven"
        )
        self.assertEqual(
            citation_logic._split_on_top_level_comma("{Smith, Jr.}, John"),
            ("{Smith, Jr.}", " John"),
        )
        # Through the real upload path the parser takes one brace layer off, so
        # the field arrives as `author = {{Smith, Jr.}, John}`.
        self.assertEqual(
            citation_logic._format_authors("{Smith, Jr.}, John"), "John Smith, Jr."
        )

    def test_and_separates_authors_across_a_line_break(self):
        # Long .bib fields wrap, so `and` can arrive on the next line. Requiring
        # a literal " and " folded both names into one and left the word inside
        # the result.
        self.assertEqual(
            self._parse_author("{Doe, Jane and\nRoe, Richard}"), "Jane Doe, Richard Roe"
        )
        self.assertEqual(
            self._parse_author("{Doe, Jane and\tRoe, Richard}"), "Jane Doe, Richard Roe"
        )
        # Still one word, whatever the line break does.
        self.assertEqual(self._parse_author("{Sandoval, Ana}"), "Ana Sandoval")
        self.assertEqual(self._parse_author("{Brand, X and Doe, Y}"), "X Brand, Y Doe")

    def test_and_needs_whitespace_on_both_sides(self):
        # A stray comma or an unspaced "and" in a hand-written .bib is not a
        # separator. Cutting there invents a second author and strands the comma
        # on the first one, which is the corruption this parser exists to stop.
        self.assertEqual(
            citation_logic._split_author_names("Doe, J,and Roe, R"),
            ["Doe, J,and Roe, R"],
        )
        self.assertEqual(
            citation_logic._split_author_names("{Doe, J}and Roe, R"),
            ["{Doe, J}and Roe, R"],
        )
        self.assertEqual(
            citation_logic._split_author_names("Android Inc."), ["Android Inc."]
        )

    def test_search_matches_a_corporate_author_by_its_full_name(self):
        content = (
            "@article{who2020, author = {{World Health Organization}},"
            " title = {Report}, year = {2020}}\n"
        )
        citation_logic.load_citation_library_content(
            "who.bib", b64encode(content.encode()).decode()
        )

        self.assertEqual(len(citation_logic.search_citations("world health")), 1)
        self.assertEqual(len(citation_logic.search_citations("organization")), 1)


if __name__ == "__main__":
    unittest.main()
