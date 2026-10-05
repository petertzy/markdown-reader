import os
import tempfile
import unittest

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from backend.renderer import render_markdown
from backend.routers.files import _convert_docx_to_markdown


def _save(document) -> str:
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "sample.docx")
    document.save(path)
    return path


def _build_table(rows, cols, values):
    document = Document()
    table = document.add_table(rows=rows, cols=cols)
    table.style = "Table Grid"
    for row_index, row in enumerate(values):
        for col_index, value in enumerate(row):
            table.cell(row_index, col_index).text = value
    return document


class TestDocxTableImport(unittest.TestCase):
    def test_table_gets_a_gfm_delimiter_row(self):
        document = _build_table(2, 2, [["Name", "Age"], ["Bob", "30"]])

        markdown = _convert_docx_to_markdown(_save(document))

        # GFM needs `| --- |` under the header; without it the pipes are shown
        # as literal text instead of a table.
        self.assertIn("| Name | Age |", markdown)
        self.assertIn("| --- | --- |", markdown)
        self.assertIn("| Bob | 30 |", markdown)

    def test_imported_table_actually_renders_as_a_table(self):
        document = _build_table(2, 2, [["Name", "Age"], ["Bob", "30"]])

        markdown = _convert_docx_to_markdown(_save(document))

        self.assertIn("<table>", render_markdown(markdown))

    def test_delimiter_row_matches_the_header_width(self):
        document = _build_table(2, 3, [["A", "B", "C"], ["1", "2", "3"]])

        markdown = _convert_docx_to_markdown(_save(document))

        lines = markdown.splitlines()
        self.assertEqual(
            len([cell for cell in lines[0].split("|") if cell.strip()]),
            len([cell for cell in lines[1].split("|") if cell.strip()]),
        )

    def test_horizontally_merged_cell_is_not_duplicated(self):
        document = _build_table(2, 2, [["Report", "Value"], ["A", "1"]])
        table = document.tables[0]
        # Merge the two header cells into one cell spanning both grid columns.
        kept, dropped = table.cell(0, 0)._tc, table.cell(0, 1)._tc
        dropped.getparent().remove(dropped)
        grid_span = OxmlElement("w:gridSpan")
        grid_span.set(qn("w:val"), "2")
        kept.get_or_add_tcPr().append(grid_span)

        markdown = _convert_docx_to_markdown(_save(document))

        # python-docx yields the merged cell once per spanned column, so the
        # header text used to appear twice.
        self.assertEqual(markdown.count("Report"), 1)
        self.assertNotIn("| Report | Report |", markdown)

    def test_merged_table_still_renders_as_a_table(self):
        document = _build_table(2, 2, [["Report", "Value"], ["A", "1"]])
        table = document.tables[0]
        kept, dropped = table.cell(0, 0)._tc, table.cell(0, 1)._tc
        dropped.getparent().remove(dropped)
        grid_span = OxmlElement("w:gridSpan")
        grid_span.set(qn("w:val"), "2")
        kept.get_or_add_tcPr().append(grid_span)

        markdown = _convert_docx_to_markdown(_save(document))

        self.assertIn("<table>", render_markdown(markdown))

    def test_distinct_cells_with_identical_text_are_both_kept(self):
        # Identity dedupe must not degrade into a text dedupe.
        document = _build_table(1, 2, [["same", "same"]])

        markdown = _convert_docx_to_markdown(_save(document))

        self.assertIn("| same | same |", markdown)

    def test_vertically_merged_cell_appears_once_per_spanned_row(self):
        # A vertically merged cell is yielded once per spanned row, carrying the
        # content of the cell it continues, so its text belongs on both rows.
        document = _build_table(3, 2, [["Group", "Total"], ["spans", "5"], ["", "7"]])
        table = document.tables[0]
        table.cell(1, 0).merge(table.cell(2, 0))

        markdown = _convert_docx_to_markdown(_save(document))

        self.assertIn("| spans | 5 |", markdown)
        self.assertIn("| spans | 7 |", markdown)
        # Neither row duplicates the cell into two adjacent columns.
        self.assertNotIn("| spans spans |", markdown)

    def test_newlines_inside_a_cell_are_collapsed(self):
        document = _build_table(1, 1, [["line one\nline two"]])

        markdown = _convert_docx_to_markdown(_save(document))

        self.assertIn("| line one line two |", markdown)

    def test_table_with_empty_cells_still_emits_a_delimiter_row(self):
        document = _build_table(1, 2, [["", ""]])

        markdown = _convert_docx_to_markdown(_save(document))

        self.assertIn("| --- | --- |", markdown)

    def test_document_without_tables_is_unchanged(self):
        document = Document()
        document.add_heading("Doc Title", level=1)
        document.add_paragraph("Body text")

        markdown = _convert_docx_to_markdown(_save(document))

        self.assertEqual(markdown, "# Doc Title\n\nBody text")


if __name__ == "__main__":
    unittest.main(verbosity=2)
