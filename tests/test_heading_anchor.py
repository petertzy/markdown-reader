"""Tests for backend.heading_anchor, the canonical heading-anchor helpers.

The outline, the AI table-of-contents generator and the renderer's heading-id
pass must all produce identical ``#anchor`` targets: a TOC link must resolve
against the rendered document. These tests pin the contract for headings
whose raw source contains inline HTML, autolinks, entities and lone ``#``
lines.
"""

import re
import unittest

from backend.ai_logic import _generate_markdown_toc
from backend.heading_anchor import extract_heading_text, slugify_heading
from backend.renderer import render_markdown
from backend.routers.markdown import _extract_outline


def _rendered_ids(html):
    return {m.group(1) for m in re.finditer(r'<h[1-6][^>]*id="([^"]+)"', html)}


def _toc_hrefs(markdown):
    return [
        m.group(1)
        for m in re.finditer(r"\]\(#([^)]+)\)", _generate_markdown_toc(markdown))
    ]


class TestHeadingAnchorHelpers(unittest.TestCase):
    def test_slug_uses_visible_text_of_inline_html(self):
        self.assertEqual(slugify_heading("Day 5<sup>th</sup> day"), "day-5th-day")
        self.assertEqual(slugify_heading("Meeting <b>Notes</b>"), "meeting-notes")
        self.assertEqual(extract_heading_text("Meeting <b>Notes</b>"), "Meeting Notes")

    def test_slug_uses_img_alt_text(self):
        self.assertEqual(
            slugify_heading('Logo <img src="x.png" alt="Big Co">'),
            "logo-big-co",
        )

    def test_slug_uses_unquoted_img_alt_text(self):
        # Unquoted attribute values are valid HTML and the renderer reads them
        # via html.parser, so the slug must include the alt text too.
        self.assertEqual(
            slugify_heading('Logo <img src="x.png" alt=Big>'),
            "logo-big",
        )

    def test_prefixed_alt_attribute_is_not_an_alt(self):
        # `data-alt` is a different attribute; the renderer ignores it, so the
        # slug must too. Only a whitespace-separated bare `alt` counts.
        for attr in ("data-alt", "aria-alt", "x-alt", "@alt", ":alt"):
            self.assertEqual(
                slugify_heading(f'Logo <img src="x.png" {attr}=Big>'),
                "logo",
                attr,
            )

    def test_alt_like_text_inside_a_quoted_attribute_is_not_an_alt(self):
        self.assertEqual(slugify_heading('Logo <img title=" alt=Big" src=x>'), "logo")

    def test_slug_keeps_autolink_content(self):
        self.assertEqual(
            slugify_heading("Read <https://example.com> now"),
            "read-httpsexamplecom-now",
        )
        self.assertEqual(
            extract_heading_text("<https://example.com>"), "https://example.com"
        )


class TestHeadingAnchorConvergence(unittest.TestCase):
    """Outline, TOC and rendered ids agree on headings with inline HTML."""

    def test_inline_html_contributes_only_visible_text_to_anchor(self):
        md = (
            "# Day 5<sup>th</sup> day\n\n"
            "## Meeting <b>Notes</b>\n\n"
            "### A <i>soft</i> launch"
        )
        html = render_markdown(md)
        self.assertIn('<h1 id="day-5th-day">', html)
        self.assertIn('<h2 id="meeting-notes">', html)
        self.assertIn('<h3 id="a-soft-launch">', html)

        hrefs = _toc_hrefs(md)
        self.assertEqual(hrefs, ["day-5th-day", "meeting-notes", "a-soft-launch"])
        for anchor in hrefs:
            self.assertIn(anchor, _rendered_ids(html))

    def test_img_alt_and_html_comment_in_heading_keep_anchors_aligned(self):
        md = '# Logo <img src="x.png" alt="Big Co">\n\n# Title <!-- note -->'
        html = render_markdown(md)
        self.assertIn('<h1 id="logo-big-co">', html)
        self.assertIn('<h1 id="title">', html)
        self.assertEqual(
            [node["anchor"] for node in _extract_outline(md)],
            ["logo-big-co", "title"],
        )
        self.assertEqual(_toc_hrefs(md), ["logo-big-co", "title"])

    def test_unquoted_img_alt_in_heading_keeps_anchors_aligned(self):
        md = '# Logo <img src="x.png" alt=Big>\n\n# Title'
        html = render_markdown(md)
        self.assertIn('<h1 id="logo-big">', html)
        self.assertEqual(
            [node["anchor"] for node in _extract_outline(md)],
            ["logo-big", "title"],
        )
        self.assertEqual(_toc_hrefs(md), ["logo-big", "title"])

    def test_prefixed_alt_attribute_keeps_anchors_aligned(self):
        for attr in ("data-alt", "aria-alt", "x-alt"):
            md = f'# Logo <img src="x.png" {attr}=Big>'
            html = render_markdown(md)
            self.assertIn('<h1 id="logo">', html)
            self.assertEqual(
                [node["anchor"] for node in _extract_outline(md)], ["logo"], attr
            )
            self.assertEqual(_toc_hrefs(md), ["logo"], attr)

    def test_quoted_alt_like_text_keeps_anchors_aligned(self):
        md = '# Logo <img title=" alt=Big" src=x>'
        html = render_markdown(md)
        self.assertIn('<h1 id="logo">', html)
        self.assertEqual([node["anchor"] for node in _extract_outline(md)], ["logo"])
        self.assertEqual(_toc_hrefs(md), ["logo"])

    def test_autolink_heading_anchor_resolves_in_outline_and_toc(self):
        md = "# Read <https://example.com> now\n\n## Mail <foo@example.com>"
        html = render_markdown(md)
        self.assertIn('<h1 id="read-httpsexamplecom-now">', html)
        self.assertIn('<h2 id="mail-fooexamplecom">', html)

        hrefs = _toc_hrefs(md)
        self.assertTrue(hrefs)
        for anchor in hrefs:
            self.assertIn(anchor, _rendered_ids(html))

    def test_bare_hash_line_does_not_invent_a_phantom_heading(self):
        # A lone `#` followed by a newline is not a heading (CommonMark), so
        # the outline must not harvest the following line's text as one.
        md = "Intro\n\n#\nHello world\n\nBody"
        self.assertEqual(_extract_outline(md), [])
        self.assertEqual(_generate_markdown_toc(md), "")
        self.assertNotIn("hello-world", render_markdown(md))

    def test_bare_less_than_in_heading_is_not_an_html_tag(self):
        md = "# 5 < 10 and > 3"
        html = render_markdown(md)
        self.assertIn('<h1 id="5-10-and-3">', html)
        self.assertEqual(_toc_hrefs(md), ["5-10-and-3"])


class TestHeadingAnchorLinkParity(unittest.TestCase):
    """The heading extractor mirrors the renderer's link handling.

    markdown2 autolinks only http/https/ftp URLs and email addresses, resolves
    reference-style links/images to their label, and shows a ``mailto:`` link as
    the bare address. Inline-only stripping (``[text](url)``) missed all three,
    so heading anchors and generated TOC links did not match the preview.
    """

    def test_non_renderer_autolink_schemes_contribute_no_text(self):
        # "<tel:555>"/"<foo:bar>" are not autolinks; the renderer leaves them as
        # invisible HTML elements, so they add no visible heading text.
        self.assertEqual(extract_heading_text("Call <tel:555> now"), "Call  now")
        self.assertEqual(slugify_heading("Call <tel:555> now"), "call-now")
        self.assertEqual(slugify_heading("see <foo:bar> baz"), "see-baz")

    def test_mailto_scheme_is_not_part_of_the_link_text(self):
        # The preview shows "bob@example.com" for "<mailto:bob@example.com>".
        self.assertEqual(
            extract_heading_text("Mail <mailto:bob@example.com>"),
            "Mail bob@example.com",
        )
        self.assertEqual(
            slugify_heading("Mail <mailto:bob@example.com>"), "mail-bobexamplecom"
        )

    def test_reference_links_and_images_keep_their_label(self):
        self.assertEqual(extract_heading_text("See [RFC 2119][rfc]"), "See RFC 2119")
        self.assertEqual(slugify_heading("See [RFC 2119][rfc]"), "see-rfc-2119")
        self.assertEqual(extract_heading_text("Logo ![Big Co][logo]"), "Logo Big Co")
        self.assertEqual(slugify_heading("Logo ![Big Co][logo]"), "logo-big-co")

    def test_reference_link_headings_keep_anchors_aligned(self):
        md = (
            "# See [RFC 2119][rfc]\n\n"
            "## Logo ![Big Co][logo]\n\n"
            "[rfc]: https://example.com/rfc\n"
            "[logo]: x.png"
        )
        html = render_markdown(md)
        self.assertIn('<h1 id="see-rfc-2119">', html)
        self.assertIn('<h2 id="logo-big-co">', html)
        self.assertEqual(
            [node["anchor"] for node in _extract_outline(md)],
            ["see-rfc-2119", "logo-big-co"],
        )
        self.assertEqual(_toc_hrefs(md), ["see-rfc-2119", "logo-big-co"])

    def test_non_renderer_autolink_heading_keeps_anchors_aligned(self):
        md = "# Call <tel:555> now\n\n## Mail <mailto:bob@example.com>"
        html = render_markdown(md)
        self.assertIn('<h1 id="call-now">', html)
        self.assertIn('<h2 id="mail-bobexamplecom">', html)
        self.assertEqual(
            [node["anchor"] for node in _extract_outline(md)],
            ["call-now", "mail-bobexamplecom"],
        )
        self.assertEqual(_toc_hrefs(md), ["call-now", "mail-bobexamplecom"])


if __name__ == "__main__":
    unittest.main()
