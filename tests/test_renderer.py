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

    def test_code_block_escapes_html_special_characters(self):
        html = render_markdown("```\nif a < b and c > d and x & y:\n```")

        self.assertIn("<code>if a &lt; b and c &gt; d and x &amp; y:\n</code>", html)

    def test_style_block_body_is_not_escaped(self):
        # html.parser hands a <style> body over verbatim, so escaping it turned
        # the child selector `.x > .y` into `.x &gt; .y` and broke the rule.
        html = render_markdown("<style>\n.x > .y { color: red }\n</style>")

        self.assertIn(".x > .y { color: red }", html)
        self.assertNotIn("&gt;", html)

    def test_script_block_body_is_not_escaped(self):
        html = render_markdown('<script>const s = "a & b"; if (1<2) {}</' + "script>")

        self.assertIn('const s = "a & b"; if (1<2) {}', html)
        self.assertNotIn("&lt;", html)
        self.assertNotIn("&amp;", html)
        self.assertNotIn("&quot;", html)

    def test_code_and_pre_bodies_are_still_escaped_exactly_once(self):
        # script/style are CDATA and must pass through raw, but code/pre are
        # escaped by markdown2 before the linkifier sees them and must not be
        # escaped a second time.
        html = render_markdown('```\n<div> & "x"\n```')

        self.assertIn("<code>&lt;div&gt; &amp; &quot;x&quot;\n</code>", html)
        self.assertNotIn("&amp;lt;", html)

    def test_urls_are_not_linkified_inside_script_or_style(self):
        html = render_markdown(
            "<style>a{background:url(https://example.com/x.png)}</style>"
        )

        self.assertNotIn("<a href=", html)
        self.assertIn("https://example.com/x.png", html)

    def test_dollar_signs_inside_code_are_not_treated_as_math(self):
        html = render_markdown(
            "```\nawk '{print $1, $2}'\n```\n\nUse `$1 and $2` here."
        )

        self.assertIn("awk &#x27;{print $1, $2}&#x27;", html)
        self.assertIn("<code>$1 and $2</code>", html)
        self.assertNotIn('class="math-inline"', html)

    def test_math_outside_code_is_still_protected(self):
        html = render_markdown(
            "A line before.\n\n`keep $1`\n\nInline $e^{i\\pi} + 1 = 0$ good"
        )

        self.assertIn("math-inline", html)
        self.assertIn("<code>keep $1</code>", html)

    def test_code_placeholder_names_in_document_are_not_mangled(self):
        html = render_markdown("This is CODEPLACEHOLDER0X text and `real code $x`")

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

        html = render_markdown("Use `cost is $5` and\n\n```\ntotal $$10$$\n```")

        token = re.compile(r"[A-Z]+PLACEHOLDER[0-9a-f]{12}[0-9]X")
        self.assertIsNone(token.search(html))

    def test_currency_amounts_are_not_treated_as_math(self):
        html = render_markdown(
            "The upgrade costs $5.00 and the plan is $10 per month.\n\n"
            "Save $20 today — regular price is $25.\n\n"
            "$100 total, or $3.50 each."
        )
        body = html.split("<body>")[1].split("</body>")[0]

        self.assertNotIn('class="math-inline"', body)
        self.assertIn("costs $5.00 and the plan is $10 per month.", body)
        self.assertIn("Save $20 today — regular price is $25.", body)
        self.assertIn("$100 total, or $3.50 each.", body)

    def test_dollar_followed_by_digit_does_not_open_math(self):
        html = render_markdown("Balance: $5 and $10 are different.")
        body = html.split("<body>")[1].split("</body>")[0]

        self.assertNotIn('class="math-inline"', body)
        self.assertIn("Balance: $5 and $10 are different.", body)

    def test_escaped_dollars_are_not_math_delimiters(self):
        html = render_markdown(r"The symbol \$ is a literal dollar, not math.")
        body = html.split("<body>")[1].split("</body>")[0]

        self.assertNotIn('class="math-inline"', body)
        # markdown2 keeps the backslash escape as-is; the important part is
        # that the escaped dollar is not converted into a math span.
        self.assertNotIn(r"\(", body)
        self.assertIn("literal dollar", body)

    def test_inline_math_still_renders_next_to_currency(self):
        html = render_markdown("Total $50 with $x^2 + y^2 = z^2$ geometry and more.")
        body = html.split("<body>")[1].split("</body>")[0]

        self.assertIn('class="math-inline"', body)
        self.assertIn("Total $50 with", body)
        self.assertNotIn("$50 with \\(", body)

    def test_digit_leading_math_and_currency_remain_separate(self):
        for expression in ("2x + 1", "5", "2x", "x^2 + y^2 = z^2"):
            with self.subTest(expression=expression):
                html = render_markdown(f"Total $50 with ${expression}$ geometry.")
                body = html.split("<body>")[1].split("</body>")[0]
                self.assertIn("Total $50 with", body)
                self.assertEqual(body.count('class="math-inline"'), 1)
                self.assertIn(
                    '<span class="math-inline">\\(' + expression + r"\)</span>",
                    body,
                )

    def test_math_requires_non_whitespace_at_inner_boundaries(self):
        for source in ("$ b $", "$a $", "$ a$", "$a $b$"):
            with self.subTest(source=source):
                html = render_markdown(source)
                if source == "$a $b$":
                    self.assertIn('<span class="math-inline">' + r"\(b\)</span>", html)
                else:
                    self.assertNotIn('class="math-inline"', html)

    def test_paired_escaped_dollars_are_literal(self):
        for source in (r"\$x\$", r"$x\$", r"\$5 and \$10"):
            with self.subTest(source=source):
                html = render_markdown(source)
                self.assertNotIn('class="math-inline"', html)

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
