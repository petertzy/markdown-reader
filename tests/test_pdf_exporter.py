import builtins
import tempfile
import unittest

import fitz

from backend.pdf_exporter import export_markdown_to_pdf


class TestPdfExporter(unittest.TestCase):
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
