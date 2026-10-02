"""Tests for Markdown-to-HTML rendering."""

import re
import unittest

from backend.ai_logic import _generate_markdown_toc
from backend.render_helpers import fix_image_paths
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


class TestHeadingAnchors(unittest.TestCase):
    """Rendered headings carry canonical anchors matching the outline and TOC."""

    def test_headings_receive_canonical_ids(self):
        html = render_markdown(
            "# Intro -- Details\n\n"
            "## [Click here](https://example.com)\n\n"
            "### A --- B\n\n"
            "#### Trailing Dash-\n\n"
            "##### -Leading Dash\n\n"
            "###### `code span` heading\n"
        )
        self.assertIn('<h1 id="intro----details">Intro -- Details</h1>', html)
        self.assertIn('<h2 id="click-here">', html)
        self.assertIn('<h3 id="a-----b">', html)
        self.assertIn('<h4 id="trailing-dash-">', html)
        self.assertIn('<h5 id="-leading-dash">', html)
        self.assertIn('<h6 id="code-span-heading">', html)

    def test_duplicate_headings_get_suffixed_ids(self):
        html = render_markdown("# Answers\n\n# Answers\n\n# Answers")
        self.assertIn('<h1 id="answers">Answers</h1>', html)
        self.assertIn('<h1 id="answers-1">Answers</h1>', html)
        self.assertIn('<h1 id="answers-2">Answers</h1>', html)

    def test_unicode_and_accented_headings_get_ids(self):
        html = render_markdown("# 第一章\n\n## Résumé")
        self.assertIn('<h1 id="第一章">第一章</h1>', html)
        self.assertIn('<h2 id="résumé">Résumé</h2>', html)

    def test_code_fence_heading_noise_gets_no_id(self):
        md = "```text\n# not a heading\n```"
        html = render_markdown(md)
        self.assertNotIn('<h1 id="not-a-heading">', html)
        self.assertNotIn('id="not-a-heading"', html)

    def test_markdown2_stock_header_ids_are_not_used(self):
        # The renderer must NOT rely on markdown2's `header-ids` extra: that
        # collapapses `[-\s]+`, so `Intro -- Details` would become the wrong
        # anchor. Canonical slugging stays in backend.heading_anchor.
        html = render_markdown("# Intro -- Details")
        self.assertIn('<h1 id="intro----details">', html)
        self.assertNotIn("<!--", html)

    def test_toc_every_href_matches_rendered_heading_id(self):
        md = (
            "# Intro -- Details\n\n"
            "## [Click here](https://example.com)\n\n"
            "### A --- B\n\n"
            "#### Trailing Dash-\n\n"
            "##### -Leading Dash\n\n"
            "###### `code span` heading\n\n"
            "### Answers\n\n"
            "### Answers\n\n"
            "# 第一章\n"
        )
        toc = _generate_markdown_toc(md)
        href_anchors = [match.group(1) for match in re.finditer(r"\]\(#([^)]+)\)", toc)]
        self.assertTrue(href_anchors, "TOC should have produced links")

        html = render_markdown(md)
        rendered_ids = {
            match.group(1) for match in re.finditer(r'<h[1-6][^>]*id="([^"]+)"', html)
        }
        for anchor in href_anchors:
            self.assertIn(anchor, rendered_ids, f"TOC #{anchor} missing from preview")

    def test_preview_outline_anchors_and_args_stay_intact(self):
        # Sanity: other markdown2 output is unchanged by the ID pass.
        html = render_markdown(
            "# Title\n\nSome text before https://example.com/x?y=1&z=2"
        )
        self.assertIn('<h1 id="title">Title</h1>', html)
        self.assertIn("Some text before", html)
        self.assertIn('href="https://example.com/x?y=1&amp;z=2"', html)

    def test_entity_headings_slug_from_visible_text(self):
        # GitHub anchors are computed from the *visible* text, so entities
        # must be decoded before slugging in both the renderer and the
        # shared heading_anchor helpers.
        md = "# Tom &amp; Jerry\n\n## A &#x27;quote&#x27; B\n\n### 5 &lt; 10"
        html = render_markdown(md)
        self.assertIn('<h1 id="tom-jerry">Tom &amp; Jerry</h1>', html)
        self.assertIn('<h2 id="a-quote-b">', html)
        self.assertIn('<h3 id="5-10">', html)

        toc = _generate_markdown_toc(md)
        hrefs = [m.group(1) for m in re.finditer(r"\]\(#([^)]+)\)", toc)]
        rendered_ids = {
            m.group(1) for m in re.finditer(r'<h[1-6][^>]*id="([^"]+)"', html)
        }
        for anchor in hrefs:
            self.assertIn(anchor, rendered_ids)

    def test_nested_entities_and_suffix_collisions_match_all_paths(self):
        from backend.routers.markdown import _extract_outline

        md = "# Tom &amp;amp; Jerry\n\n# A\n\n# A-1\n\n# A\n\n# A\n"
        expected = ["tom-amp-jerry", "a", "a-1", "a-2", "a-3"]
        ids = re.findall(r'<h[1-6][^>]*id="([^"]+)"', render_markdown(md))
        self.assertEqual(ids, expected)
        self.assertEqual([node["anchor"] for node in _extract_outline(md)], expected)
        self.assertEqual(
            re.findall(r"\]\(#([^)]+)\)", _generate_markdown_toc(md)), expected
        )

    def test_fenced_examples_do_not_consume_heading_suffixes(self):
        from backend.routers.markdown import _extract_outline

        md = "```text\n# Same\n```\n\n# Same\n\n# Same\n"
        expected = ["same", "same-1"]
        self.assertEqual(
            re.findall(r'<h[1-6][^>]*id="([^"]+)"', render_markdown(md)), expected
        )
        outline = _extract_outline(md)
        self.assertEqual([node["anchor"] for node in outline], expected)
        self.assertEqual([node["line"] for node in outline], [5, 7])
        self.assertEqual(
            re.findall(r"\]\(#([^)]+)\)", _generate_markdown_toc(md)), expected
        )


class TestImagePathsSkipCodeRegions(unittest.TestCase):
    """Relative image resolution must not rewrite image syntax shown as code.

    ``fix_image_paths`` runs before any code masking, so a Markdown document
    that *demonstrates* image syntax had its own examples rewritten to absolute
    ``file://`` URLs in the rendered preview.
    """

    BASE = "/Users/me/docs"

    def test_image_inside_a_fenced_block_is_left_alone(self):
        html = render_markdown(
            "```markdown\n![diagram](diagram.png)\n```",
            base_dir=self.BASE,
        )
        self.assertIn("diagram.png", html)
        self.assertNotIn(f"file://{self.BASE}/diagram.png", html)

    def test_image_inside_an_inline_code_span_is_left_alone(self):
        html = render_markdown("Use `![alt](shot.png)` to embed.", base_dir=self.BASE)
        self.assertIn("shot.png", html)
        self.assertNotIn(f"file://{self.BASE}/shot.png", html)

    def test_real_image_beside_a_code_sample_is_still_resolved(self):
        html = render_markdown(
            "```markdown\n![diagram](diagram.png)\n```\n\n![chart](chart.png)\n",
            base_dir=self.BASE,
        )
        self.assertIn(f'<img src="file://{self.BASE}/chart.png"', html)
        self.assertNotIn(f"file://{self.BASE}/diagram.png", html)

    def test_tilde_fence_is_treated_as_code(self):
        text = "~~~markdown\n![diagram](diagram.png)\n~~~\n"
        self.assertEqual(fix_image_paths(text, self.BASE), text)

    def test_two_backtick_span_is_treated_as_code(self):
        text = "a ``![d](d.png)`` b"
        self.assertEqual(fix_image_paths(text, self.BASE), text)

    def test_fenced_block_at_end_of_file_without_newline(self):
        text = "intro\n\n```markdown\n![diagram](diagram.png)\n```"
        self.assertEqual(fix_image_paths(text, self.BASE), text)

    def test_ordinary_prose_images_are_unchanged(self):
        text = "![chart](chart.png) and ![abs](/x.png) and ![web](https://e.com/i.png)"
        self.assertEqual(
            fix_image_paths(text, self.BASE),
            f"![chart](file://{self.BASE}/chart.png) and ![abs](/x.png) "
            "and ![web](https://e.com/i.png)",
        )

    def test_no_placeholder_token_leaks_from_the_masking(self):
        html = render_markdown("`![a](b.png)` and ![c](c.png)", base_dir=self.BASE)
        self.assertNotIn("PLACEHOLDER", html)
        self.assertIn("b.png", html)
        self.assertIn(f'<img src="file://{self.BASE}/c.png"', html)
