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

    _WRAPPING_OVERRIDE = (
        "pre code { white-space: pre-wrap !important; overflow-wrap: anywhere; "
        "word-break: break-word; }"
    )

    def _fake_pymupdf(self, captured: dict, doc=None) -> types.ModuleType:
        """A stand-in for ``fitz`` that records the HTML handed to MuPDF."""

        class FakeDocument:
            def save(self, output_path):
                captured["output_path"] = output_path

            def close(self):
                captured["closed"] = True

        class FakeStory:
            def __init__(self, *, html):
                captured["html"] = html

            def write_with_links(self, _rectfn):
                return doc or FakeDocument()

        fake_fitz = types.ModuleType("fitz")
        fake_fitz.Story = FakeStory
        fake_fitz.Rect = lambda *args: args
        fake_fitz.Identity = None
        return fake_fitz

    def test_pymupdf_engine_applies_the_pdf_print_stylesheet(self):
        """The fallback must honour the same overrides weasyprint gets.

        The renderer sets ``white-space: pre`` on ``pre code``, so without the
        print stylesheet MuPDF cannot break a long code line and shrinks the
        document until it fits the text column.
        """
        from backend.pdf_exporter import _export_pdf_with_pymupdf

        captured: dict = {}
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(sys.modules, {"fitz": self._fake_pymupdf(captured)}):
                _export_pdf_with_pymupdf(
                    render_markdown("```python\nprint(1)\n```"),
                    f"{tmp_dir}/out.pdf",
                )

        self.assertIn(self._WRAPPING_OVERRIDE, captured["html"])
        head_end = captured["html"].lower().find("</head>")
        self.assertNotEqual(head_end, -1, "renderer markup should carry a <head>")
        self.assertLess(
            captured["html"].find("pre code { white-space: pre-wrap"),
            head_end,
            "print stylesheet belongs in <head>, before any later stylesheet",
        )

    def test_pymupdf_engine_applies_the_print_style_to_a_fragment(self):
        from backend.pdf_exporter import _export_pdf_with_pymupdf

        captured: dict = {}
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(sys.modules, {"fitz": self._fake_pymupdf(captured)}):
                _export_pdf_with_pymupdf("<p>fragment</p>", f"{tmp_dir}/out.pdf")

        self.assertIn(self._WRAPPING_OVERRIDE, captured["html"])
        self.assertTrue(captured["html"].endswith("<p>fragment</p>"))

    def test_pymupdf_engine_closes_the_document_when_saving_fails(self):
        from backend.pdf_exporter import _export_pdf_with_pymupdf

        class FailingDoc:
            def save(self, _output_path):
                raise OSError("no space left on device")

            def close(self):
                captured["closed"] = True

        captured: dict = {}
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(
                sys.modules, {"fitz": self._fake_pymupdf(captured, FailingDoc())}
            ):
                with self.assertRaises(OSError):
                    _export_pdf_with_pymupdf("<p>x</p>", f"{tmp_dir}/out.pdf")

        self.assertTrue(captured.get("closed"), "document leaked when save failed")

    def _fallback_body_glyph_size(self, markdown: str) -> float:
        """Size of the body glyph in a PDF produced by the fallback engine."""
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise OSError("cannot load library 'libgobject-2.0-0'")
            return original_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/fallback.pdf"
            try:
                builtins.__import__ = fake_import
                export_markdown_to_pdf(render_markdown(markdown), output_path)
            finally:
                builtins.__import__ = original_import

            with fitz.open(output_path) as document:
                sizes = [
                    span["size"]
                    for block in document[0].get_text("dict")["blocks"]
                    for line in block.get("lines", [])
                    for span in line["spans"]
                    if span["text"].startswith("Trailing")
                ]
        self.assertTrue(sizes, "body run missing from the generated PDF")
        return sizes[0]

    # One block per rule the print stylesheet has to supply: the renderer's own
    # stylesheet resolves each of these to `white-space: pre` or to an
    # unbreakable run, so MuPDF down-scales the document to fit the column.
    _UNBREAKABLE_BLOCKS = {
        "fenced code block": (
            "```python\nresult = compute(alpha, beta, gamma, delta, epsilon, "
            "zeta, eta, theta, iota, kappa, lambda, mu)\n```\n"
        ),
        "bare pre from raw html": "<pre>" + "bare_pre_line_" * 12 + "</pre>\n",
        "long url in a link": "See https://example.com/" + "a" * 140 + " now.\n",
        "inline code span": "`" + "inline_token_" * 14 + "`\n",
        "long unbroken word": "supercalifragilistic" * 6 + "\n",
    }

    def test_long_document_paginates_instead_of_shrinking(self):
        """The fallback engine must paginate, not down-scale, long documents.

        `insert_htmlbox` layed every document out on a single page, so a
        multi-thousand-word report came back as one page of tiny text. The
        Story writer opens a fresh A4 page whenever the current one fills up.
        """
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "weasyprint":
                raise OSError("cannot load library 'libgobject-2.0-0'")
            return original_import(name, *args, **kwargs)

        markdown = "# Long Report\n\n" + "\n\n".join(
            f"Paragraph {index}: " + ("lorem ipsum dolor sit amet " * 12).strip()
            for index in range(40)
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/long.pdf"
            try:
                builtins.__import__ = fake_import
                export_markdown_to_pdf(render_markdown(markdown), output_path)
            finally:
                builtins.__import__ = original_import

            with fitz.open(output_path) as document:
                self.assertGreater(
                    len(document), 1, "long content must span multiple pages"
                )
                full_text = "".join(page.get_text() for page in document)
                for index in range(40):
                    self.assertIn(f"Paragraph {index}", full_text)

    def test_pymupdf_fallback_does_not_shrink_the_document(self):
        """No unbreakable block may rescale the whole fallback PDF.

        Every document carries the same body paragraph, so a difference in body
        glyph size can only mean the engine shrank the document to squeeze the
        block into the text column.
        """
        reference = self._fallback_body_glyph_size(
            "# Report\n\nSome intro text.\n\nTrailing paragraph.\n"
        )

        for label, block in self._UNBREAKABLE_BLOCKS.items():
            with self.subTest(block=label):
                size = self._fallback_body_glyph_size(
                    f"# Report\n\nSome intro text.\n\n{block}\nTrailing paragraph.\n"
                )
                self.assertAlmostEqual(
                    size / reference,
                    1.0,
                    delta=0.02,
                    msg=(
                        f"{label} rescaled the fallback PDF to {size / reference:.1%}"
                    ),
                )
