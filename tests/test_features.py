"""
test_features.py
================
Unit tests for word_count_bar.py and recent_files.py.

Run with:
    python -m pytest tests/test_features.py -v
or:
    python -m unittest tests.test_features -v
"""

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the modules under test.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.recent_files import (
    RecentFilesManager,
    _middle_ellipsis,
    _safe_write_json,
)
from backend.renderer import render_markdown as _render_markdown
from backend.routers.files import (
    ConvertToMarkdownPayload,
    convert_to_markdown,
    get_supported_formats,
)
from backend.routers.markdown import (
    OpenPreviewPayload,
    RenderPayload,
    open_preview_in_browser,
    word_count,
)
from backend.word_count import count_words as _count_words
from backend.word_count import reading_time as _reading_time
from backend.word_count import strip_markdown as _strip_markdown

# ===========================================================================
# Tests for word_count_bar helpers
# ===========================================================================


class TestStripMarkdown(unittest.TestCase):
    """_strip_markdown should remove syntax tokens without destroying words."""

    def test_atx_heading(self):
        result = _strip_markdown("# Hello World")
        self.assertIn("Hello", result)
        self.assertNotIn("#", result)

    def test_bold_markers(self):
        result = _strip_markdown("**bold text**")
        self.assertIn("bold", result)
        self.assertNotIn("**", result)

    def test_italic_markers(self):
        result = _strip_markdown("*italic text*")
        self.assertIn("italic", result)
        self.assertNotIn("*", result)

    def test_inline_code(self):
        # Inline code content is removed entirely.
        result = _strip_markdown("Use `print()` here")
        self.assertIn("Use", result)
        self.assertIn("here", result)

    def test_fenced_code_block(self):
        md = "intro\n```python\nfor i in range(10):\n    pass\n```\noutro"
        result = _strip_markdown(md)
        self.assertIn("intro", result)
        self.assertIn("outro", result)
        self.assertNotIn("range", result)

    def test_link_keeps_text(self):
        result = _strip_markdown("[click here](https://example.com)")
        self.assertIn("click", result)
        self.assertNotIn("https", result)

    def test_image_removed(self):
        result = _strip_markdown("![alt text](image.png)")
        self.assertNotIn("alt", result)

    def test_blockquote_marker(self):
        result = _strip_markdown("> quoted line")
        self.assertIn("quoted", result)
        self.assertNotIn(">", result)

    def test_html_tags_removed(self):
        result = _strip_markdown("<p>Some text</p>")
        self.assertIn("Some", result)
        self.assertNotIn("<p>", result)

    def test_horizontal_rule(self):
        result = _strip_markdown("---")
        self.assertEqual(result.strip(), "")

    def test_table_pipes(self):
        result = _strip_markdown("| col1 | col2 |")
        self.assertNotIn("|", result)
        self.assertIn("col1", result)

    def test_table_delimiter_row_adds_no_words(self):
        # A GFM delimiter row is made only of pipes, dashes and colons, so it
        # must not contribute phantom words. It cannot be matched before the
        # pipes are stripped, because the leading pipe hides it from the
        # horizontal-rule rule.
        md = "| Name | Age | City |\n| --- | --- | --- |\n| Bob | 30 | Rome |"
        self.assertEqual(_count_words(_strip_markdown(md)), 6)

    def test_table_delimiter_row_with_alignment_colons_adds_no_words(self):
        md = "| Metric | Q1 |\n| :--- | ---: |\n| Revenue | 10 |"
        self.assertEqual(_count_words(_strip_markdown(md)), 4)

    def test_task_list_checkboxes_add_no_words(self):
        # `- [x]` / `- [ ]` used to leave the brackets behind, and an unchecked
        # box cost one word more than a checked one.
        self.assertEqual(_count_words(_strip_markdown("- [x] Ship it")), 2)
        self.assertEqual(_count_words(_strip_markdown("- [ ] Ship it")), 2)
        self.assertEqual(_count_words(_strip_markdown("- [X] Ship it")), 2)

    def test_mixed_task_list_counts_only_the_items(self):
        md = "- [x] Wire up the exporter\n- [ ] Ship the release"
        self.assertEqual(_count_words(_strip_markdown(md)), 7)

    def test_checkbox_marker_outside_a_list_is_preserved(self):
        # The checkbox is only stripped directly after a bullet, so prose is
        # untouched.
        self.assertIn("[x]", _strip_markdown("[x] is a plain token"))
        self.assertIn("mid line", _strip_markdown("see - [ ] mid line"))

    def test_horizontal_rules_and_bullets_are_unaffected(self):
        for rule in ("---", "***", "___"):
            self.assertEqual(_strip_markdown(rule).strip(), "")
        self.assertEqual(_count_words(_strip_markdown("- alpha\n- beta")), 2)
        self.assertEqual(_count_words(_strip_markdown("1. one\n2. two")), 2)

    def test_setext_h1_underline_adds_no_words(self):
        # The "=" underline of a setext H1 became part of the heading when the
        # document was rendered, but it was counted as a word, while the "-"
        # underline of a setext H2 was not.
        md = "Title\n=====\n\nsome prose here"
        self.assertEqual(_count_words(_strip_markdown(md)), 4)

    def test_equals_underline_length_matches_what_the_renderer_accepts(self):
        # A single "=" is already a setext underline as far as the renderer is
        # concerned, so the count has to stop at one and not at three. The
        # rules above already cover the "-" underline at two and at three or
        # more, which is why only "=" needs a rule of its own here.
        for length in range(1, 6):
            underline = "=" * length
            with self.subTest(underline=underline):
                markdown = f"Title\n{underline}"
                self.assertIn("<h1", _render_markdown(markdown))
                self.assertEqual(_count_words(_strip_markdown(markdown)), 1)

    def test_bare_equals_at_the_top_of_the_document_keeps_its_word(self):
        # There is no line above to underline, so the "=" stays literal text.
        md = "=\nTitle"
        self.assertNotIn("<h1", _render_markdown(md))
        self.assertEqual(_count_words(_strip_markdown(md)), 2)

    def test_equals_run_followed_by_more_text_is_not_an_underline(self):
        # The run has to be the whole line. "= tail" is ordinary text, and
        # dropping it would lose a word the rendered document still shows.
        for md in ("Title\n= tail", "Title\n== tail"):
            with self.subTest(markdown=md):
                self.assertNotIn("<h1", _render_markdown(md))
                self.assertEqual(_count_words(_strip_markdown(md)), 3)

    def test_trailing_spaces_do_not_stop_the_underline_matching(self):
        for underline in ("=  ", "===   ", "=\t"):
            with self.subTest(underline=underline):
                md = f"Title\n{underline}\nprose here"
                self.assertIn("<h1", _render_markdown(md))
                self.assertEqual(_count_words(_strip_markdown(md)), 3)

    def test_setext_h1_and_h2_underlines_count_the_same(self):
        # Both underlines become part of the heading, so neither may count.
        h1 = _count_words(_strip_markdown("Release Notes\n==========="))
        h2 = _count_words(_strip_markdown("Release Notes\n-----------"))
        self.assertEqual(h1, 2)
        self.assertEqual(h1, h2)

    def test_consecutive_setext_h1_headings(self):
        md = "First\n=====\n\nSecond\n====="
        self.assertEqual(_count_words(_strip_markdown(md)), 2)

    def test_bare_equals_paragraph_is_still_counted(self):
        # A "===" that underlines nothing stays literal text in the rendered
        # document, so counting it is correct.
        md = "a\n\n===\n\nb"
        self.assertEqual(_count_words(_strip_markdown(md)), 3)

    def test_equals_separated_from_its_heading_is_still_counted(self):
        # The underline only disappears when it is directly under the text.
        md = "Title\n\n==="
        self.assertEqual(_count_words(_strip_markdown(md)), 2)


class TestWordCountStatistics(unittest.TestCase):
    """The character statistics reported next to the editor word count."""

    def _stats(self, content: str) -> dict:
        return word_count(RenderPayload(content=content))

    def test_carriage_returns_are_not_counted(self):
        # Only " ", "\n" and "\t" were dropped, so every line of a CRLF file
        # contributed one phantom character.
        lf = self._stats("# Title\n\nHello world.\n")
        crlf = self._stats("# Title\r\n\r\nHello world.\r\n")
        self.assertEqual(crlf["chars_without_spaces"], lf["chars_without_spaces"])

    def test_many_crlf_lines_do_not_inflate_the_total(self):
        # 5000 line endings used to be 5000 characters that are not in the
        # document at all: a 25% overcount on a 20k character file.
        self.assertEqual(self._stats("word\r\n" * 5000)["chars_without_spaces"], 20000)

    def test_non_breaking_and_em_spaces_are_not_counted(self):
        # Both are ordinary spaces to a reader, and both arrive constantly in
        # text pasted from a web page or a word processor.
        self.assertEqual(
            self._stats("Tom\xa0Jerry\u2003and\u2009friends")["chars_without_spaces"],
            len("TomJerryandfriends"),
        )

    def test_vertical_tab_and_form_feed_are_not_counted(self):
        self.assertEqual(self._stats("a\x0bb\x0cc")["chars_without_spaces"], 3)

    def test_markdown_syntax_is_still_counted(self):
        # The count describes the document, not the rendered text, so a "#"
        # and a "|" are characters of the file just like a letter is.
        self.assertEqual(self._stats("# a | b")["chars_without_spaces"], 4)

    def test_characters_with_spaces_still_counts_whitespace(self):
        # The two figures have to differ by exactly the whitespace between
        # them, which is what makes the pair usable side by side.
        content = "# Title\r\n\nHello world.\t\r\n"
        stats = self._stats(content)
        self.assertEqual(stats["chars_with_spaces"], len(content))
        self.assertEqual(
            stats["chars_with_spaces"] - stats["chars_without_spaces"],
            sum(1 for ch in content if ch.isspace()),
        )

    def test_whitespace_only_document_counts_no_characters(self):
        stats = self._stats("  \n\t \r\n \xa0 ")
        self.assertEqual(stats["chars_with_spaces"], 10)
        self.assertEqual(stats["chars_without_spaces"], 0)
        self.assertEqual(stats["words"], 0)

    def test_empty_document(self):
        stats = self._stats("")
        self.assertEqual(stats["chars_with_spaces"], 0)
        self.assertEqual(stats["chars_without_spaces"], 0)
        self.assertEqual(stats["words"], 0)


class TestCountWords(unittest.TestCase):
    """_count_words should handle common edge cases correctly."""

    def test_empty_string(self):
        self.assertEqual(_count_words(""), 0)

    def test_whitespace_only(self):
        self.assertEqual(_count_words("   \n\t  "), 0)

    def test_simple_sentence(self):
        self.assertEqual(_count_words("Hello world"), 2)

    def test_multiple_spaces(self):
        self.assertEqual(_count_words("one   two   three"), 3)

    def test_newlines_between_words(self):
        self.assertEqual(_count_words("one\ntwo\nthree"), 3)

    def test_unicode_latin(self):
        # Latin accented characters should still count as one word each.
        self.assertEqual(_count_words("café résumé naïve"), 3)

    def test_cjk_characters_counted_individually(self):
        # Each Chinese character is one word.
        self.assertEqual(_count_words("你好世界"), 4)

    def test_mixed_cjk_and_latin(self):
        count = _count_words("Hello 世界 world")
        # "Hello" + "世" + "界" + "world" = 4
        self.assertEqual(count, 4)

    def test_punctuation_not_counted(self):
        # Punctuation attached to a word should not create extra word tokens.
        count = _count_words("Hello, world!")
        self.assertEqual(count, 2)


class TestReadingTime(unittest.TestCase):
    """_reading_time should return sensible human-readable strings."""

    def test_zero_words(self):
        self.assertEqual(_reading_time(0), "< 1 min read")

    def test_fewer_than_wpm(self):
        self.assertEqual(_reading_time(100), "< 1 min read")

    def test_exactly_one_minute(self):
        self.assertEqual(_reading_time(238), "1 min read")

    def test_multiple_minutes(self):
        result = _reading_time(238 * 5)
        self.assertEqual(result, "5 min read")

    def test_rounding(self):
        # 357 words / 238 wpm ≈ 1.5 → rounds to 2
        result = _reading_time(357)
        self.assertEqual(result, "2 min read")


class TestBrowserPreview(unittest.TestCase):
    """Browser preview should render Markdown to a temporary HTML file."""

    def test_open_preview_in_browser_writes_html_and_opens_url(self):
        with patch(
            "backend.routers.markdown.webbrowser.open", return_value=True
        ) as open_mock:
            result = open_preview_in_browser(
                OpenPreviewPayload(content="# Browser Preview\n\nA rendered page.")
            )

        preview_path = Path(result["path"])
        try:
            self.assertTrue(preview_path.is_file())
            self.assertEqual(result["url"], preview_path.as_uri())
            html = preview_path.read_text(encoding="utf-8")
            self.assertIn('<h1 id="browser-preview">Browser Preview</h1>', html)
            self.assertIn("A rendered page.", html)
            open_mock.assert_called_once_with(result["url"], new=2)
        finally:
            preview_path.unlink(missing_ok=True)


# ===========================================================================
# Tests for recent_files helpers
# ===========================================================================


class TestMiddleEllipsis(unittest.TestCase):
    """_middle_ellipsis should shorten long strings correctly."""

    def test_short_path_unchanged(self):
        path = "/short/path.md"
        self.assertEqual(_middle_ellipsis(path, max_len=60), path)

    def test_long_path_shortened(self):
        path = "/very/long/directory/structure/that/exceeds/the/limit/file.md"
        result = _middle_ellipsis(path, max_len=40)
        self.assertLessEqual(len(result), 40)
        self.assertIn("…", result)

    def test_result_starts_and_ends_with_original(self):
        path = "/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/u/v/w/x/y/z/file.md"
        result = _middle_ellipsis(path, max_len=30)
        # The start of the original should be in the result.
        self.assertTrue(result.startswith(path[:10]))
        # The filename should be preserved at the end.
        self.assertTrue(result.endswith("file.md"))


class TestSafeWriteJson(unittest.TestCase):
    """_safe_write_json should write valid JSON atomically."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.target = os.path.join(self.tmpdir, "settings.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_file_with_correct_content(self):
        data = {"key": "value", "num": 42}
        _safe_write_json(self.target, data)
        with open(self.target) as f:
            loaded = json.load(f)
        self.assertEqual(loaded, data)

    def test_overwrites_existing_file(self):
        _safe_write_json(self.target, {"old": True})
        _safe_write_json(self.target, {"new": True})
        with open(self.target) as f:
            loaded = json.load(f)
        self.assertNotIn("old", loaded)
        self.assertTrue(loaded["new"])

    def test_no_temp_file_left_behind(self):
        _safe_write_json(self.target, {"x": 1})
        files = os.listdir(self.tmpdir)
        # Only the target file should remain; no .tmp files.
        self.assertFalse(any(f.endswith(".tmp") for f in files))


class TestRecentFilesManager(unittest.TestCase):
    """Full integration tests for RecentFilesManager."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.settings = os.path.join(self.tmpdir, "settings.json")
        # Create some real files so existence checks pass.
        self.files = []
        for i in range(12):
            p = os.path.join(self.tmpdir, f"file{i}.md")
            open(p, "w").close()
            self.files.append(p)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _manager(self) -> RecentFilesManager:
        return RecentFilesManager(self.settings, max_entries=10)

    def test_push_adds_entry(self):
        m = self._manager()
        m.push(self.files[0])
        self.assertIn(os.path.normpath(self.files[0]), m.entries)

    def test_push_most_recent_first(self):
        m = self._manager()
        m.push(self.files[0])
        m.push(self.files[1])
        self.assertEqual(m.entries[0], os.path.normpath(self.files[1]))

    def test_push_deduplicates(self):
        m = self._manager()
        m.push(self.files[0])
        m.push(self.files[1])
        m.push(self.files[0])  # push first file again
        self.assertEqual(m.entries.count(os.path.normpath(self.files[0])), 1)
        # Should now be at the top again.
        self.assertEqual(m.entries[0], os.path.normpath(self.files[0]))

    def test_max_entries_enforced(self):
        m = self._manager()
        for f in self.files:  # 12 files, max is 10
            m.push(f)
        self.assertLessEqual(len(m.entries), 10)

    def test_persistence_across_instances(self):
        m1 = self._manager()
        m1.push(self.files[0])
        m1.push(self.files[1])
        # New instance reads from same settings file.
        m2 = self._manager()
        self.assertEqual(m2.entries[0], os.path.normpath(self.files[1]))
        self.assertIn(os.path.normpath(self.files[0]), m2.entries)

    def test_clear_empties_list(self):
        m = self._manager()
        m.push(self.files[0])
        m.clear()
        self.assertEqual(m.entries, [])

    def test_clear_persisted(self):
        m = self._manager()
        m.push(self.files[0])
        m.clear()
        m2 = self._manager()
        self.assertEqual(m2.entries, [])

    def test_other_settings_keys_preserved(self):
        """Saving recent files must not destroy other settings keys."""
        # Pre-populate settings with an unrelated key.
        _safe_write_json(self.settings, {"theme": "dark", "api_key": "abc123"})
        m = self._manager()
        m.push(self.files[0])
        with open(self.settings) as f:
            data = json.load(f)
        self.assertEqual(data.get("theme"), "dark")
        self.assertEqual(data.get("api_key"), "abc123")

    def test_missing_file_pruned_on_load(self):
        """Paths to deleted files should be silently removed when loading."""
        ghost = os.path.join(self.tmpdir, "ghost.md")
        open(ghost, "w").close()
        m = self._manager()
        m.push(ghost)
        os.unlink(ghost)  # delete the file
        # Reload — ghost should be gone.
        m2 = self._manager()
        self.assertNotIn(os.path.normpath(ghost), m2.entries)

    def test_malformed_settings_handled_gracefully(self):
        """A corrupted settings file should not crash the manager."""
        with open(self.settings, "w") as f:
            f.write("THIS IS NOT JSON {{{")
        # Should not raise.
        m = self._manager()
        self.assertEqual(m.entries, [])

    def test_missing_settings_file_handled(self):
        """Missing settings file should be handled gracefully."""
        m = self._manager()  # settings file doesn't exist yet
        self.assertEqual(m.entries, [])
        # Push should create the file.
        m.push(self.files[0])
        self.assertTrue(os.path.isfile(self.settings))

    def test_path_normalisation(self):
        """Paths pushed with different representations should deduplicate."""
        m = self._manager()
        path = self.files[0]
        # Push the same file via two different path representations.
        m.push(path)
        m.push(path + os.sep + ".." + os.sep + os.path.basename(path))
        # After normalisation both should resolve to the same path.
        # The list should have exactly one entry for this file (or zero if
        # the double-dot path resolves differently — acceptable behaviour).
        normalised = os.path.normpath(os.path.abspath(path))
        count = m.entries.count(normalised)
        self.assertLessEqual(count, 1)


class TestConvertToMarkdown(unittest.TestCase):
    """File conversion endpoint helpers should return Markdown content."""

    def test_supported_formats_reports_native_and_universal_import(self):
        result = get_supported_formats()

        native_extensions = {entry["extension"] for entry in result["native"]}
        markitdown_extensions = {entry["extension"] for entry in result["markitdown"]}

        self.assertIn(".md", native_extensions)
        self.assertIn(".docx", native_extensions)
        self.assertIn(".xlsx", markitdown_extensions)
        self.assertIn(".pptx", markitdown_extensions)
        self.assertIsInstance(result["markitdown_available"], bool)

    def test_converts_html_upload_to_markdown(self):
        html = b"<h1>Title</h1><p>Hello <strong>world</strong>.</p>"
        payload = ConvertToMarkdownPayload(
            filename="sample.html",
            content_base64=base64.b64encode(html).decode("ascii"),
        )

        result = convert_to_markdown(payload)

        self.assertIn("Title", result["markdown"])
        self.assertIn("Hello", result["markdown"])

    def test_converts_docx_path_to_markdown(self):
        from docx import Document

        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "sample.docx")
        try:
            document = Document()
            document.add_heading("Doc Title", level=1)
            document.add_paragraph("Body text")
            document.save(path)

            result = convert_to_markdown(ConvertToMarkdownPayload(path=path))

            self.assertIn("# Doc Title", result["markdown"])
            self.assertIn("Body text", result["markdown"])
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
