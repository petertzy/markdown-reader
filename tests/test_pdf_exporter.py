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
