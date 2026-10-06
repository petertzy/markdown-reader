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


if __name__ == "__main__":
    unittest.main()
