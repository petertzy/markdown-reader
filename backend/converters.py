from __future__ import annotations

import re


def convert_html_to_markdown(html: str) -> str:
    try:
        import html2text
    except ImportError as exc:
        raise RuntimeError("html2text is required to convert HTML.") from exc

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.body_width = 0
    return converter.handle(html or "").strip()


def convert_pdf_to_markdown(pdf_path: str) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to convert PDF files.") from exc

    lines: list[str] = []
    with fitz.open(pdf_path) as document:
        for page_index, page in enumerate(document, 1):
            text = page.get_text("text").strip()
            if text:
                if len(document) > 1:
                    lines.append(f"<!-- Page {page_index} -->")
                lines.append(text)
                lines.append("")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def convert_pdf_to_markdown_docling(pdf_path: str) -> str:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise RuntimeError("docling is required for advanced PDF conversion.") from exc

    result = DocumentConverter().convert(pdf_path)
    document = result.document
    if hasattr(document, "export_to_markdown"):
        return document.export_to_markdown().strip()
    return str(document).strip()
