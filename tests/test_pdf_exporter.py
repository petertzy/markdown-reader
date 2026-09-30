import builtins
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import fitz

from backend.pdf_exporter import export_markdown_to_pdf
from backend.renderer import render_markdown


class TestPdfExporter(unittest.TestCase):
    def test_pdf_export_overrides_renderer_code_whitespace(self):
        captured: dict[str, str] = {}

        class FakeHTML:
            def __init__(self, *, string: str):
                captured["html"] = string

            def write_pdf(self, output_path: str) -> None:
                captured["output_path"] = output_path

        fake_weasyprint = types.ModuleType("weasyprint")
        fake_weasyprint.HTML = FakeHTML

        html = render_markdown("```text\n" + ("long_line_" * 20) + "\n```")
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/document.pdf"
            with patch.dict(sys.modules, {"weasyprint": fake_weasyprint}):
                export_markdown_to_pdf(html, output_path)

            self.assertEqual(captured["output_path"], output_path)

        generated_html = captured["html"]
        self.assertIn(
            "pre code { white-space: pre-wrap !important; overflow-wrap: anywhere; word-break: break-word; }",
            generated_html,
        )
        self.assertIn("pre code {\n      background-color:", generated_html)
        self.assertIn("white-space: pre;", generated_html)

    def test_falls_back_to_pymupdf_when_weasyprint_is_unavailable(self):
        html = '<p>Hello <a href="https://example.com">link</a></p>'
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise OSError("cannot load library 'libgobject-2.0-0'")
            return original_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/export.pdf"
            try:
                builtins.__import__ = fake_import
                export_markdown_to_pdf(html, output_path)
            finally:
                builtins.__import__ = original_import

            document = fitz.open(output_path)
            try:
                self.assertIn("Hello link", document[0].get_text())
                self.assertEqual(
                    document[0].get_links()[0]["uri"], "https://example.com"
                )
            finally:
                document.close()

    def test_math_is_typeset_in_both_pdf_engines(self):
        from backend.pdf_exporter import _export_pdf_with_pymupdf
        from backend.pdf_math import render_pdf_math

        source = (
            r"Cost $5.00 and $10. Inline $\frac{1}{2}+x^2$."
            "\n\n"
            r"$$\sqrt{x^2+y^2}$$"
            "\n\n"
            r"$$\begin{pmatrix}1 & 2\\3 & 4\end{pmatrix}$$"
        )
        html = render_markdown(source)
        for engine in (export_markdown_to_pdf, _export_pdf_with_pymupdf):
            with (
                self.subTest(engine=engine.__name__),
                tempfile.TemporaryDirectory() as tmp,
            ):
                path = f"{tmp}/math.pdf"
                prepared = (
                    html if engine is export_markdown_to_pdf else render_pdf_math(html)
                )
                engine(prepared, path)
                with fitz.open(path) as document:
                    text = "".join(page.get_text() for page in document)
                    self.assertIn("$5.00", text)
                    self.assertIn("$10", text)
                    self.assertNotIn(r"\frac", text)
                    self.assertNotIn(r"\sqrt", text)
                    self.assertGreaterEqual(len(document[0].get_images()), 3)

    def test_math_preparation_preserves_code_and_currency(self):
        from bs4 import BeautifulSoup

        from backend.pdf_math import render_pdf_math

        html = render_pdf_math(render_markdown(r"`$x$` and $5 and $10; $x^2$."))
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(soup.code.get_text(), "$x$")
        self.assertIn("$5 and $10", soup.get_text())
        self.assertEqual(len(soup.select("span.math-inline img")), 1)
        self.assertEqual(soup.select_one("span.math-inline img")["alt"], "x^2")

    def test_math_conversion_failure_is_reported(self):
        from backend.pdf_math import render_pdf_math

        with patch("ziamath.Latex", side_effect=ValueError("invalid formula")):
            with self.assertRaisesRegex(ValueError, "Could not typeset PDF formula"):
                render_pdf_math(render_markdown("$x$"))

    def test_formula_glyphs_are_not_blank(self):
        import base64

        from bs4 import BeautifulSoup

        from backend.pdf_math import render_pdf_math

        html = render_pdf_math(render_markdown("$x$"))
        image = BeautifulSoup(html, "html.parser").select_one("span.math-inline img")
        pixmap = fitz.Pixmap(base64.b64decode(image["src"].split(",", 1)[1]))
        # A glyph-only formula catches SVG references silently ignored by MuPDF.
        self.assertTrue(pixmap.alpha)
        self.assertGreater(sum(pixmap.samples[3::4]), 0)
