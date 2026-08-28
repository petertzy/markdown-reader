from __future__ import annotations

import base64
import contextlib
import io
import mimetypes
import os
import re


def _inline_local_images(html_content: str, base_dir: str | None = None) -> str:
    def _try_inline(src: str) -> str | None:
        if src.startswith(("http://", "https://", "data:")):
            return None
        file_path = src[7:] if src.startswith("file://") else src
        if not os.path.isabs(file_path):
            if not base_dir:
                return None
            file_path = os.path.join(base_dir, file_path)
        file_path = os.path.abspath(file_path)
        if not os.path.isfile(file_path):
            return None
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/png"
        with open(file_path, "rb") as file_obj:
            data = base64.b64encode(file_obj.read()).decode("ascii")
        return f"data:{mime_type};base64,{data}"

    def _replace_attr(match: re.Match[str]) -> str:
        quote = match.group(1)
        src = match.group(2)
        inlined = _try_inline(src)
        return f"src={quote}{inlined}{quote}" if inlined else match.group(0)

    return re.sub(r'src=(["\'])([^"\']+)\1', _replace_attr, html_content, flags=re.I)


def _normalize_image_tags(html_content: str) -> str:
    def _strip_size_attributes(match: re.Match[str]) -> str:
        tag = match.group(0)
        tag = re.sub(r'\swidth\s*=\s*(["\']).*?\1', "", tag, flags=re.I)
        tag = re.sub(r'\sheight\s*=\s*(["\']).*?\1', "", tag, flags=re.I)
        return tag

    return re.sub(r"<img\b[^>]*>", _strip_size_attributes, html_content, flags=re.I)


def export_markdown_to_pdf(
    html_content: str, output_path: str, base_url: str | None = None
) -> None:
    base_dir = base_url[7:] if base_url and base_url.startswith("file://") else base_url
    normalized_html = _inline_local_images(
        _normalize_image_tags(html_content), base_dir
    )
    full_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    @page {{ size: A4; margin: 20mm 15mm; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; line-height: 1.6; overflow-wrap: break-word; }}
    img {{ max-width: 100% !important; width: auto !important; height: auto !important; page-break-inside: avoid; }}
    pre {{ white-space: pre-wrap; background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px; }}
    pre, code, table {{ page-break-inside: avoid; }}
  </style>
</head>
<body>
{normalized_html}
</body>
</html>"""
    try:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            from weasyprint import HTML

            HTML(string=full_html).write_pdf(output_path)
    except Exception:
        _export_pdf_with_pymupdf(normalized_html, output_path)


def _export_pdf_with_pymupdf(html_content: str, output_path: str) -> None:
    import fitz

    page_width = 595
    page_height = 842
    margin = 50
    doc = fitz.open()
    page = doc.new_page(width=page_width, height=page_height)
    rect = fitz.Rect(margin, margin, page_width - margin, page_height - margin)
    page.insert_htmlbox(rect, html_content)
    doc.save(output_path)
    doc.close()
