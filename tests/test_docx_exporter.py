import tempfile
import unittest
from zipfile import ZipFile

from docx import Document

from backend.docx_exporter import export_html_to_docx
from backend.renderer import render_markdown


class TestDocxExporter(unittest.TestCase):
    def test_export_skips_whitespace_between_block_elements(self):
        html = """<body>
<p>first</p>
<h2>heading</h2>
<ul><li>item</li></ul>
<pre><code>code</code></pre>
<p>last</p>
</body>"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/export.docx"

            export_html_to_docx(html, output_path)

            document = Document(output_path)
            self.assertEqual(
                [paragraph.text for paragraph in document.paragraphs],
                ["first", "heading", "item", "code", "last"],
            )

    def test_export_preserves_clickable_links(self):
        html = render_markdown(
            "[Project documentation](https://example.com/docs)\n\n"
            "Bare URL: https://example.com/bare."
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/links.docx"

            export_html_to_docx(html, output_path)

            document = Document(output_path)
            body_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            self.assertIn("Project documentation", body_text)
            self.assertIn("https://example.com/bare", body_text)

            with ZipFile(output_path) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")
                relationships_xml = archive.read("word/_rels/document.xml.rels").decode(
                    "utf-8"
                )

            self.assertEqual(document_xml.count("<w:hyperlink"), 2)
            self.assertIn('Target="https://example.com/docs"', relationships_xml)
            self.assertIn('Target="https://example.com/bare"', relationships_xml)
            self.assertIn(
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"',
                relationships_xml,
            )
