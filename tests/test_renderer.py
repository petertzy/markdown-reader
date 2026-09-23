"""Tests for Markdown-to-HTML rendering."""

import unittest

from backend.renderer import render_markdown


class TestRenderMarkdown(unittest.TestCase):
    """Exported links should remain clickable and open in a new tab."""

    def test_links_open_in_new_tab(self):
        html = render_markdown("[Project documentation](https://example.com/docs)")

        self.assertIn("<a ", html)
        self.assertIn('href="https://example.com/docs"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener"', html)

    def test_bare_urls_are_clickable(self):
        html = render_markdown("Read https://example.com/docs.")

        self.assertIn(
            '<a href="https://example.com/docs" target="_blank" rel="noopener">https://example.com/docs</a>.',
            html,
        )

    def test_bare_urls_do_not_wrap_existing_links_or_code(self):
        html = render_markdown(
            "[Docs](https://example.com/docs)\n\n"
            "`https://example.com/code`\n\n"
            "```text\nhttps://example.com/fence\n```"
        )

        self.assertEqual(html.count('href="https://example.com/docs"'), 1)
        self.assertNotIn('href="https://example.com/code"', html)
        self.assertNotIn('href="https://example.com/fence"', html)

    def test_bare_url_with_balanced_parentheses_is_fully_linked(self):
        html = render_markdown(
            "See http://en.wikipedia.org/wiki/Bracket_(disambiguation)."
        )

        self.assertIn(
            '<a href="http://en.wikipedia.org/wiki/Bracket_(disambiguation)" '
            'target="_blank" rel="noopener">'
            "http://en.wikipedia.org/wiki/Bracket_(disambiguation)</a>.",
            html,
        )

    def test_bare_url_with_stray_closing_bracket_is_trimmed(self):
        html = render_markdown("Jump to http://example.com/done) now.")

        self.assertIn(
            '<a href="http://example.com/done" target="_blank" rel="noopener">'
            "http://example.com/done</a>) now.",
            html,
        )

    def test_bare_url_in_quotes_leaves_quotes_outside_the_link(self):
        html = render_markdown('Read "https://example.com/foo" for details.')

        self.assertIn(
            '<a href="https://example.com/foo" target="_blank" rel="noopener">'
            "https://example.com/foo</a>",
            html,
        )
        self.assertNotIn('href="https://example.com/foo&quot;"', html)
        self.assertIn("</a>&quot; for details.", html)
