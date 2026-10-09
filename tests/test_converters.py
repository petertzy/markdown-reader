"""Tests for ``backend.converters`` HTML -> Markdown import.

Importing an HTML file must not silently corrupt its text: named and numeric
character references (``&eacute;``, ``&mdash;``, ``&copy;`` …) have to survive
as the characters they name instead of being rewritten to ASCII approximations.
"""

from __future__ import annotations

import unittest

from backend.converters import convert_html_to_markdown


class TestConvertHtmlToMarkdownEntities(unittest.TestCase):
    def test_named_letter_entities_are_preserved(self):
        # html2text's default (``unicode_snob=False``) degrades references to
        # ASCII lookalikes, so importing "café" produced "cafe".
        self.assertEqual(
            convert_html_to_markdown("<p>caf&eacute; &mdash; na&iuml;ve</p>"),
            "café — naïve",
        )

    def test_symbol_entities_are_preserved(self):
        self.assertEqual(
            convert_html_to_markdown("<p>Copyright &copy; 2024 &rarr; done</p>"),
            "Copyright © 2024 → done",
        )

    def test_numeric_character_references_are_preserved(self):
        self.assertEqual(
            convert_html_to_markdown("<p>&#8212; dash &#169; sign</p>"),
            "— dash © sign",
        )

    def test_markup_entities_stay_ascii(self):
        # ``&amp;``/``&lt;``/``&gt;`` decode to plain ASCII and are unchanged.
        self.assertEqual(
            convert_html_to_markdown("<p>plain &amp; simple &lt;tag&gt;</p>"),
            "plain & simple <tag>",
        )

    def test_literal_unicode_is_untouched(self):
        self.assertEqual(
            convert_html_to_markdown("<p>already café</p>"), "already café"
        )


if __name__ == "__main__":
    unittest.main()
