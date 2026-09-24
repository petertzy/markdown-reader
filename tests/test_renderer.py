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

    def test_bare_urls_keep_query_strings_with_ampersands(self):
        html = render_markdown("Go to https://example.com/?a=1&b=2 now")

        self.assertIn(
            '<a href="https://example.com/?a=1&amp;b=2" target="_blank" '
            'rel="noopener">https://example.com/?a=1&amp;b=2</a>',
            html,
        )

    def test_ampersand_in_plain_text_is_not_rejoined_into_url(self):
        html = render_markdown("Tom & Jerry https://example.com/a")

        self.assertEqual(html.count("&amp;Jerry"), 0)
        self.assertIn("Tom &amp; Jerry", html)
