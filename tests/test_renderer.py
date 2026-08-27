"""Tests for Markdown-to-HTML rendering."""

import unittest

from backend.renderer import render_markdown


class TestRenderMarkdown(unittest.TestCase):
    """Exported links should remain clickable and open in a new tab."""

    def test_links_open_in_new_tab(self):
        html = render_markdown("[Project documentation](https://example.com/docs)")

        self.assertIn('<a ', html)
        self.assertIn('href="https://example.com/docs"', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener"', html)

