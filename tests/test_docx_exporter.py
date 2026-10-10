import base64
import re
import tempfile
import unittest
from urllib.parse import quote_from_bytes
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn

from backend.docx_exporter import export_html_to_docx
from backend.renderer import render_markdown


def _document_text(document: Document) -> str:
    texts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                texts.extend(paragraph.text for paragraph in cell.paragraphs)
    return "\n".join(texts)


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
                ["first", "heading", "item", "last"],
            )
            self.assertIn("code", _document_text(document))

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

    def test_export_styles_code_blocks_with_background(self):
        html = render_markdown("```python\nprint('hello')\n```")
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/code.docx"

            export_html_to_docx(html, output_path)

            document = Document(output_path)
            self.assertIn("print", _document_text(document))

            with ZipFile(output_path) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")

            self.assertIn('<w:shd w:fill="F6F8FA"/>', document_xml)
            self.assertIn("<w:tcMar>", document_xml)
            self.assertIn('<w:left w:w="120" w:type="dxa"/>', document_xml)
            self.assertIn('<w:right w:w="120" w:type="dxa"/>', document_xml)
            self.assertNotIn("<w:ind ", document_xml)
            self.assertNotIn('w:before="120"', document_xml)
            self.assertNotIn('w:after="120"', document_xml)
            self.assertIn('w:ascii="Courier New"', document_xml)

    def test_data_uri_image_is_embedded_not_leaked_as_text(self):
        png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR"
            "42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/data-uri.docx"

            export_html_to_docx(
                render_markdown(f"![pixel](data:image/png;BASE64,{png})"),
                output_path,
            )

            document = Document(output_path)
            body_text = "\n".join(p.text for p in document.paragraphs)
            # The raw base64 blob must not land in the document as visible text.
            self.assertNotIn("data:", body_text)
            self.assertNotIn("[data:", body_text)
            self.assertGreater(
                len(document.inline_shapes),
                0,
                "the data-URI image should be embedded as a picture",
            )

    def test_data_uri_image_with_url_encoded_payload_is_embedded(self):
        png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR"
            "42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        data_uri = "DATA:image/png," + quote_from_bytes(base64.b64decode(png))
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/url-encoded-data-uri.docx"

            export_html_to_docx(f'<img src="{data_uri}">', output_path)

            document = Document(output_path)
            self.assertEqual(len(document.inline_shapes), 1)
            self.assertNotIn("data:", _document_text(document).lower())

    def test_percent_encoded_local_image_path_is_embedded(self):
        # Markdown image destinations are URLs, so a space arrives as "%20".
        # The exporter must decode it before opening the file, or the picture is
        # replaced by its "[path]" fallback text.
        png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR"
            "42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/My Pic.png", "wb") as file_obj:
                file_obj.write(base64.b64decode(png))
            output_path = f"{tmp_dir}/encoded-image.docx"

            export_html_to_docx(
                render_markdown("![pic](My%20Pic.png)"),
                output_path,
                base_dir=tmp_dir,
            )

            document = Document(output_path)
            self.assertEqual(len(document.inline_shapes), 1)
            self.assertNotIn("[My%20Pic.png]", _document_text(document))

    def test_percent_encoded_file_uri_image_path_is_embedded(self):
        png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR"
            "42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = f"{tmp_dir}/My Pic.png"
            with open(image_path, "wb") as file_obj:
                file_obj.write(base64.b64decode(png))
            output_path = f"{tmp_dir}/file-uri-image.docx"

            encoded_src = "file://" + image_path.replace(" ", "%20")
            export_html_to_docx(
                f'<img src="{encoded_src}">',
                output_path,
                base_dir=tmp_dir,
            )

            document = Document(output_path)
            self.assertEqual(len(document.inline_shapes), 1)

    def test_plain_local_image_path_still_resolves(self):
        png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR"
            "42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/plain.png", "wb") as file_obj:
                file_obj.write(base64.b64decode(png))
            output_path = f"{tmp_dir}/plain-image.docx"

            export_html_to_docx(
                render_markdown("![pic](plain.png)"),
                output_path,
                base_dir=tmp_dir,
            )

            document = Document(output_path)
            self.assertEqual(len(document.inline_shapes), 1)

    def test_export_preserves_escaped_html_entities(self):
        # Escaped HTML like "&amp;" must be exported as the real character
        # ("&") rather than being silently dropped or written as raw markup.
        html = """<body>
<p>R&amp;D budget &amp; plans</p>
<p>AT&amp;T &amp; T-Mobile</p>
<p>Tommy&#39;s &quot;quoted&quot; text</p>
<p>less &lt;html&gt; more</p>
</body>"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/entities.docx"

            export_html_to_docx(html, output_path)

            document = Document(output_path)
            body_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            self.assertIn("R&D budget & plans", body_text)
            self.assertIn("AT&T & T-Mobile", body_text)
            self.assertIn('Tommy\'s "quoted" text', body_text)
            self.assertIn("less <html> more", body_text)
            # Raw markup must not leak into the export unescaped.
            self.assertNotIn("&amp;", body_text)
            self.assertNotIn("&lt;", body_text)
            self.assertNotIn("&quot;", body_text)

    def test_export_preserves_entities_inside_table_cells_and_code(self):
        html = """<body>
<table><tr><td>A &amp; B</td><td>1 &lt; 2</td></tr></table>
<pre><code>if (a &lt; b &amp;&amp; c &gt; d) {}</code></pre>
</body>"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/entities_rich.docx"

            export_html_to_docx(html, output_path)

            document = Document(output_path)
            body_text = _document_text(document)
            self.assertIn("A & B", body_text)
            self.assertIn("1 < 2", body_text)
            self.assertIn("if (a < b && c > d) {}", body_text)

    def test_export_preserves_entities_from_rendered_markdown(self):
        # Markdown with an entity-like literal ("&amp;") flows through the
        # renderer, whose markdown2 output escapes it. The DOCX export must
        # round-trip it back to the plain character.
        html = render_markdown("Cost: 5 &amp; 6\n\n`R&D` and `a < b` inline")
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/roundtrip.docx"

            export_html_to_docx(html, output_path)

            document = Document(output_path)
            body_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            body_text += "\n" + _document_text(document)
            self.assertIn("Cost: 5 & 6", body_text)
            self.assertIn("R&D", body_text)
            self.assertIn("a < b", body_text)


def _export_paragraphs(markdown: str) -> list[tuple[str, str]]:
    """Render ``markdown`` and return ``(style name, text)`` for each paragraph."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = f"{tmp_dir}/export.docx"

        export_html_to_docx(render_markdown(markdown), output_path)

        document = Document(output_path)
        return [
            (paragraph.style.name, paragraph.text) for paragraph in document.paragraphs
        ]


class TestDocxExporterLists(unittest.TestCase):
    """Loose lists must not strand an empty bullet beside their text.

    A "loose" Markdown list has a blank line between items, so the renderer
    emits ``<li><p>text</p></li>``. The ``<p>`` used to open a brand new
    unstyled paragraph, leaving the bullet that ``<li>`` had already opened
    empty: Word then showed a stray bullet dot followed by plain body text.
    """

    def test_loose_bullet_list_keeps_bullets_on_their_text(self):
        self.assertEqual(
            _export_paragraphs("- alpha\n\n- beta\n"),
            [("List Bullet", "alpha"), ("List Bullet", "beta")],
        )

    def test_loose_ordered_list_keeps_numbers_on_their_text(self):
        self.assertEqual(
            _export_paragraphs("1. alpha\n\n2. beta\n"),
            [("List Number", "alpha"), ("List Number", "beta")],
        )

    def test_tight_lists_are_unchanged(self):
        self.assertEqual(
            _export_paragraphs("- alpha\n- beta\n"),
            [("List Bullet", "alpha"), ("List Bullet", "beta")],
        )
        self.assertEqual(
            _export_paragraphs("1. alpha\n2. beta\n"),
            [("List Number", "alpha"), ("List Number", "beta")],
        )

    def test_every_paragraph_of_a_loose_item_keeps_the_list_style(self):
        # "alpha" and its continuation paragraph are both part of one item, so
        # both stay in the list rather than falling back to body text.
        self.assertEqual(
            _export_paragraphs("- alpha\n\n  more text\n\n- beta\n"),
            [
                ("List Bullet", "alpha"),
                ("List Bullet", "more text"),
                ("List Bullet", "beta"),
            ],
        )

    def test_paragraph_after_a_heading_in_a_list_item_keeps_its_own_style(self):
        # The first paragraph is not always the first block in a list item.
        # It must not be appended to an earlier heading while attempting to
        # reuse the paragraph opened for ``<li>``.
        self.assertEqual(
            _export_paragraphs("- ## Title\n\n  body\n"),
            [("List Bullet", ""), ("Heading 2", "Title"), ("List Bullet", "body")],
        )

    def test_inline_formatting_inside_a_loose_item_keeps_the_list_style(self):
        paragraphs = _export_paragraphs("- **bold** text\n\n- *ital*\n")

        self.assertEqual(
            paragraphs,
            [("List Bullet", "bold text"), ("List Bullet", "ital")],
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/formatting.docx"

            export_html_to_docx(
                render_markdown("- **bold** text\n\n- *ital*\n"), output_path
            )

            document = Document(output_path)
            self.assertTrue(any(run.bold for run in document.paragraphs[0].runs))
            self.assertTrue(any(run.italic for run in document.paragraphs[1].runs))

    def test_nested_loose_list_does_not_strand_its_outer_bullet(self):
        self.assertEqual(
            _export_paragraphs("- alpha\n\n  - beta\n  - gamma\n"),
            [
                ("List Bullet", "alpha"),
                ("List Bullet", "beta"),
                ("List Bullet", "gamma"),
            ],
        )

    def test_loose_list_item_holding_a_sublist_keeps_both_bullets(self):
        paragraphs = _export_paragraphs("- alpha\n\n  - beta\n")

        self.assertEqual([style for style, _ in paragraphs], ["List Bullet"] * 2)
        self.assertEqual([text for _, text in paragraphs], ["alpha", "beta"])

    def test_loose_and_tight_items_in_one_list_stay_uniform(self):
        self.assertEqual(
            _export_paragraphs("- a\n- b\n\n- c\n"),
            [
                ("List Bullet", "a"),
                ("List Bullet", "b"),
                ("List Bullet", "c"),
            ],
        )

    def test_paragraphs_outside_lists_are_not_given_a_list_style(self):
        self.assertEqual(_export_paragraphs("plain text\n"), [("Normal", "plain text")])
        self.assertEqual(
            _export_paragraphs("intro\n\n- alpha\n\n- beta\n\noutro\n"),
            [
                ("Normal", "intro"),
                ("List Bullet", "alpha"),
                ("List Bullet", "beta"),
                ("Normal", "outro"),
            ],
        )

    def test_loose_list_style_does_not_leak_past_the_closing_tag(self):
        # The paragraph that closes a loose item is recorded as having claimed
        # it; that bookkeeping must be discarded at </li> so later top-level
        # blocks are not mistaken for part of the list.
        self.assertEqual(
            _export_paragraphs("- alpha\n\n- beta\n\noutro\n"),
            [
                ("List Bullet", "alpha"),
                ("List Bullet", "beta"),
                ("Normal", "outro"),
            ],
        )
        self.assertEqual(
            _export_paragraphs("1. alpha\n\n2. beta\n\noutro\n"),
            [
                ("List Number", "alpha"),
                ("List Number", "beta"),
                ("Normal", "outro"),
            ],
        )

    def test_blocks_after_a_loose_list_keep_their_own_styles(self):
        self.assertEqual(
            _export_paragraphs("- alpha\n\n- beta\n\n## Section\n\ntail\n"),
            [
                ("List Bullet", "alpha"),
                ("List Bullet", "beta"),
                ("Heading 2", "Section"),
                ("Normal", "tail"),
            ],
        )

    def test_paragraph_after_a_sublist_stays_in_its_own_list_item(self):
        # "a" and "c" are two paragraphs of one item separated by a sublist.
        # Unwinding the inner </li> must not disturb the outer item, so "c"
        # still belongs to the list rather than falling back to body text.
        self.assertEqual(
            _export_paragraphs("- a\n\n  - b\n\n  c\n"),
            [
                ("List Bullet", "a"),
                ("List Bullet", "b"),
                ("List Bullet", "c"),
            ],
        )
        self.assertEqual(
            _export_paragraphs("- a\n\n  - b\n\n    - c\n\n  d\n"),
            [
                ("List Bullet", "a"),
                ("List Bullet", "b"),
                ("List Bullet", "c"),
                ("List Bullet", "d"),
            ],
        )

    def test_a_second_list_after_a_loose_list_picks_its_own_style(self):
        self.assertEqual(
            _export_paragraphs("- a\n\n- b\n\n1. one\n\n2. two\n"),
            [
                ("List Bullet", "a"),
                ("List Bullet", "b"),
                ("List Number", "one"),
                ("List Number", "two"),
            ],
        )

    def test_loose_list_does_not_leak_its_style_into_the_next_list(self):
        paragraphs = _export_paragraphs("- a\n\n- b\n\n1. one\n\n2. two\n")

        self.assertEqual(
            paragraphs,
            [
                ("List Bullet", "a"),
                ("List Bullet", "b"),
                ("List Number", "one"),
                ("List Number", "two"),
            ],
        )


class TestDocxExporterBlockquotes(unittest.TestCase):
    """A blockquote must not leave a stray whitespace-only paragraph behind.

    ``> quoted text`` renders as ``<blockquote>\\n  <p>quoted text</p>
    \\n</blockquote>``. The opening ``<blockquote>`` tag used to create an
    empty paragraph of its own, which then received the inter-tag whitespace
    as a visible run: every exported quote was preceded by a blank paragraph
    (which even picked up a stray bullet inside a loose list).
    """

    def test_plain_blockquote_has_no_stray_paragraph(self):
        self.assertEqual(
            _export_paragraphs("> quoted text\n"),
            [("Normal", "quoted text")],
        )

    def test_blockquote_with_two_paragraphs(self):
        self.assertEqual(
            _export_paragraphs("> first\n>\n> second\n"),
            [("Normal", "first"), ("Normal", "second")],
        )

    def test_blockquote_inside_a_loose_list_adds_no_stray_bullet(self):
        self.assertEqual(
            _export_paragraphs("- alpha\n\n  > quoted\n\n- beta\n"),
            [
                ("List Bullet", "alpha"),
                ("List Bullet", "quoted"),
                ("List Bullet", "beta"),
            ],
        )

    def test_heading_inside_a_blockquote_is_not_preceded_by_whitespace(self):
        self.assertEqual(
            _export_paragraphs("> # Heading\n>\n> body\n"),
            [("Heading 1", "Heading"), ("Normal", "body")],
        )


class TestDocxExporterLinkWhitespace(unittest.TestCase):
    """Hyperlink text keeps the same whitespace treatment as plain runs.

    python-docx marks a ``w:t`` with ``xml:space="preserve"`` whenever its
    text has leading/trailing whitespace, so identical text in a plain run
    survives LibreOffice/converter round-trips. The hand-built hyperlink
    ``w:t`` must follow the same rule or link text loses its edge spaces.
    """

    def _hyperlink_t_elements(self, markdown):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/links.docx"
            export_html_to_docx(render_markdown(markdown), output_path)
            with ZipFile(output_path) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")
        search = re.search(r"<w:hyperlink[^>]*>.*?</w:hyperlink>", document_xml, re.S)
        self.assertIsNotNone(search, "no hyperlink found in exported docx")
        return re.findall(r"<w:t[^>]*>[^<]*</w:t>", search.group(0))

    def test_hyperlink_text_with_edge_whitespace_is_marked_preserve(self):
        self.assertEqual(
            self._hyperlink_t_elements("[  spaced  ](https://example.com)"),
            ['<w:t xml:space="preserve">  spaced  </w:t>'],
        )

    def test_hyperlink_text_without_edge_whitespace_is_left_alone(self):
        self.assertEqual(
            self._hyperlink_t_elements("[docs](https://example.com)"),
            ["<w:t>docs</w:t>"],
        )


class TestDocxExporterThematicBreaks(unittest.TestCase):
    """A thematic break must export as a horizontal rule, not vanish.

    ``render_markdown`` emits ``<hr />`` for ``---``. The parser used to
    ignore the tag, so every rule was silently dropped from the Word export.
    """

    def _rule_paragraphs(self, markdown):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = f"{tmp_dir}/rule.docx"

            export_html_to_docx(render_markdown(markdown), output_path)

            document = Document(output_path)
            rules = []
            for paragraph in document.paragraphs:
                properties = paragraph._p.find(qn("w:pPr"))
                if properties is not None and properties.find(qn("w:pBdr")) is not None:
                    rules.append(paragraph)
        return document, rules

    def test_thematic_break_draws_a_horizontal_rule(self):
        document, rules = self._rule_paragraphs("Above\n\n---\n\nBelow")

        self.assertEqual(len(rules), 1, "the rule should be drawn once")
        self.assertEqual(rules[0].text, "", "the rule paragraph itself is empty")
        self.assertEqual(
            [paragraph.text for paragraph in document.paragraphs if paragraph.text],
            ["Above", "Below"],
        )

    def test_rule_is_not_drawn_without_a_thematic_break(self):
        _, rules = self._rule_paragraphs("Just a paragraph.")

        self.assertEqual(rules, [])
