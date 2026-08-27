from docx import Document

from backend.docx_exporter import export_html_to_docx


def test_export_skips_whitespace_between_block_elements(tmp_path):
    html = """<body>
<p>first</p>
<h2>heading</h2>
<ul><li>item</li></ul>
<pre><code>code</code></pre>
<p>last</p>
</body>"""
    output_path = tmp_path / "export.docx"

    export_html_to_docx(html, str(output_path))

    document = Document(output_path)
    assert [paragraph.text for paragraph in document.paragraphs] == [
        "first",
        "heading",
        "item",
        "code",
        "last",
    ]
