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

    def test_dollar_signs_inside_code_are_not_treated_as_math(self):
        html = render_markdown("```\nawk '{print $1, $2}'\n```\n\nUse `$1 and $2` here.")

        self.assertIn("awk &#x27;{print $1, $2}&#x27;", html)
        self.assertIn("<code>$1 and $2</code>", html)
        self.assertNotIn('class="math-inline"', html)

    def test_math_outside_code_is_still_protected(self):
        html = render_markdown("A line before.\n\n`keep $1`\n\nInline $e^{i\\pi} + 1 = 0$ good")

        self.assertIn("math-inline", html)
        self.assertIn("<code>keep $1</code>", html)

    def test_code_placeholder_names_in_document_are_not_mangled(self):
        html = render_markdown(
            "This is CODEPLACEHOLDER0X text and `real code $x`"
        )

        self.assertIn("<code>real code $x</code>", html)
        self.assertIn("CODEPLACEHOLDER0X", html)
        self.assertNotIn(r"\\(real code", html)

    def test_math_placeholder_names_in_document_are_not_mangled(self):
        html = render_markdown(
            "A doc mentioning MATHPLACEHOLDER0X literally. Math $$5+5$$ here."
        )

        self.assertIn("MATHPLACEHOLDER0X", html)
        self.assertIn("math-display", html)

    def test_no_placeholder_tokens_leak_into_output(self):
        import re

        html = render_markdown(
            "Use `cost is $5` and\n\n```\ntotal $$10$$\n```"
        )

        token = re.compile(r"[A-Z]+PLACEHOLDER[0-9a-f]{12}[0-9]X")
        self.assertIsNone(token.search(html))
