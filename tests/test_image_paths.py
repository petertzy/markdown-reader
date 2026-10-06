"""Data-URI images must survive relative-path resolution unchanged.

``fix_image_paths`` skips URL/image sources that are already absolute
(``http(s)://``, ``file://``, a ``/`` root path) and rewrites everything else
into a ``file://`` URL. A ``data:`` URI is not a filesystem path, but it fell
into the rewrite branch: ``![pic](data:image/png;base64,…)`` became
``![pic](file:///…/data:image/png;base64,…)``, so the rendered preview showed
a broken image instead of the embedded one.
"""

import unittest

from backend.render_helpers import fix_image_paths
from backend.renderer import render_markdown


class TestDataUriImagesSurviveResolution(unittest.TestCase):
    BASE = "/Users/me/docs"

    def test_data_uri_image_syntax_is_left_exactly_as_written(self):
        text = "![pic](data:image/png;base64,iVBORw0KGgoAAAANSUhEUg)"
        self.assertEqual(fix_image_paths(text, self.BASE), text)

    def test_data_uri_scheme_is_case_insensitive(self):
        text = "![pic](DATA:image/png;base64,iVBORw0KGgoAAAANSUhEUg)"
        self.assertEqual(fix_image_paths(text, self.BASE), text)

    def test_data_uri_renders_as_an_embedded_image(self):
        html = render_markdown(
            "![pic](data:image/png;base64,iVBORw0KGgo)",
            base_dir=self.BASE,
        )
        self.assertIn('<img src="data:image/png;base64,iVBORw0KGgo"', html)
        self.assertNotIn(f"file://{self.BASE}/data:", html)

    def test_data_uri_in_a_fenced_code_block_is_left_alone(self):
        # Demonstrating a data-URI diagram in a fence must not be rewritten
        # either (the code masking already protects it, independent of the
        # skip tuple).
        text = "```markdown\n![pic](data:image/svg+xml;utf8,<svg/>)\n```\n"
        self.assertEqual(fix_image_paths(text, self.BASE), text)

    def test_relative_and_absolute_urls_still_resolve_as_before(self):
        text = (
            "![a](a.png) ![b](/b.png) ![c](https://e.com/c.png) ![d](file:///f/d.png)"
        )
        self.assertEqual(
            fix_image_paths(text, self.BASE),
            f"![a](file://{self.BASE}/a.png) ![b](/b.png) "
            "![c](https://e.com/c.png) ![d](file:///f/d.png)",
        )


if __name__ == "__main__":
    unittest.main()
