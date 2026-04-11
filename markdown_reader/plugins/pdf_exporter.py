import base64
import mimetypes
import os
import re
from urllib.parse import urlparse

import requests
from weasyprint import HTML


def custom_url_fetcher(url):
    """
    Custom URL fetcher that handles both local and remote resources.

    :param url: The URL to fetch
    :return: A dictionary with 'string', 'mime_type', and 'encoding' keys
    """
    # Parse the URL
    parsed = urlparse(url)

    if parsed.scheme in ("http", "https"):
        # For remote URLs, fetch them
        try:
            response = requests.get(url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            return {
                "string": response.content,
                "mime_type": response.headers.get("Content-Type", "image/png"),
                "encoding": None,
            }
        except Exception:
            # Return a placeholder or empty content if fetch fails
            return {
                "string": b"",
                "mime_type": "image/png",
                "encoding": None,
            }
    elif parsed.scheme == "file":
        # For file URLs, use the default behavior
        file_path = parsed.path
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            return {
                "string": content,
                "mime_type": "application/octet-stream",
                "encoding": None,
            }
        except Exception:
            return {
                "string": b"",
                "mime_type": "application/octet-stream",
                "encoding": None,
            }
    else:
        # For other schemes, try to handle as file path
        try:
            with open(url, "rb") as f:
                content = f.read()
            return {
                "string": content,
                "mime_type": "application/octet-stream",
                "encoding": None,
            }
        except Exception:
            return {
                "string": b"",
                "mime_type": "application/octet-stream",
                "encoding": None,
            }


def _inline_local_images(html_content: str, base_dir: str = None) -> str:
    """
    Replace every local <img src="..."> reference with an inline base64 data URI.

    This makes the HTML fully self-contained so WeasyPrint never needs to read
    from the filesystem at render time — critical inside a sandboxed .app bundle
    where relative paths and file:// URLs are often unresolvable.

    Remote (http/https) and already-inlined (data:) sources are left untouched.
    """

    def _try_inline(src: str):
        """Return a data-URI string for *src*, or None if it cannot be inlined."""
        if src.startswith(("http://", "https://", "data:")):
            return None
        try:
            if src.startswith("file://"):
                file_path = src[7:]
                # Windows: file:///C:/... -> C:/...
                if (
                    file_path.startswith("/")
                    and len(file_path) > 2
                    and file_path[2] == ":"
                ):
                    file_path = file_path[1:]
            elif os.path.isabs(src):
                file_path = src
            elif base_dir:
                file_path = os.path.join(base_dir, src)
            else:
                return None

            file_path = os.path.abspath(file_path)
            if not os.path.isfile(file_path):
                return None

            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/png"

            with open(file_path, "rb") as fh:
                data = base64.b64encode(fh.read()).decode("ascii")

            return f"data:{mime_type};base64,{data}"
        except Exception:
            return None

    def _replace_attr(m):
        quote = m.group(1)
        src = m.group(2)
        inlined = _try_inline(src)
        if inlined:
            return f"src={quote}{inlined}{quote}"
        return m.group(0)

    # Match src="..." and src='...'
    return re.sub(
        r'src=(["\'])([^"\']+)\1', _replace_attr, html_content, flags=re.IGNORECASE
    )


def _wrap_html_for_pdf(html_content: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset=\"UTF-8\">
    <style>
        @page {{
            size: A4;
            margin: 20mm 15mm;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            line-height: 1.6;
            overflow-wrap: break-word;
        }}

        img {{
            max-width: 100% !important;
            width: auto !important;
            height: auto !important;
            object-fit: contain;
            page-break-inside: avoid;
        }}

        pre {{
            white-space: pre-wrap;
            overflow-wrap: normal;
            word-break: normal;
            background: #f6f8fa;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 12px;
            font-family: Menlo, Monaco, Consolas, "Courier New", monospace;
            font-size: 12px;
            line-height: 1.45;
        }}

        pre code {{
            white-space: inherit;
            font-family: inherit;
            font-size: inherit;
        }}

        code {{
            font-family: Menlo, Monaco, Consolas, "Courier New", monospace;
            font-size: 0.95em;
        }}

        pre, code, table {{
            page-break-inside: avoid;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""


def _normalize_image_tags(html_content: str) -> str:
    def _strip_size_attributes(match):
        tag = match.group(0)
        tag = re.sub(r'\swidth\s*=\s*(["\']).*?\1', "", tag, flags=re.IGNORECASE)
        tag = re.sub(r'\sheight\s*=\s*(["\']).*?\1', "", tag, flags=re.IGNORECASE)
        tag = re.sub(r"\swidth\s*=\s*\S+", "", tag, flags=re.IGNORECASE)
        tag = re.sub(r"\sheight\s*=\s*\S+", "", tag, flags=re.IGNORECASE)
        return tag

    return re.sub(
        r"<img\b[^>]*>", _strip_size_attributes, html_content, flags=re.IGNORECASE
    )


def export_markdown_to_pdf(html_content: str, output_path: str, base_url: str = None):
    """
    Export rendered HTML content to PDF

    Args:
        html_content (str): HTML string already rendered from Markdown
        output_path (str): Target PDF file path
        base_url (str): Base directory (filesystem path or file:// URL) where the
                        source Markdown file lives, used to resolve relative image paths
                        before they are inlined as base64 data URIs.
    """
    try:
        # Resolve base_dir from whatever form base_url arrives in
        base_dir = None
        if base_url:
            if base_url.startswith("file://"):
                base_dir = base_url[7:]
                # Windows: file:///C:/... -> C:/...
                if (
                    base_dir.startswith("/")
                    and len(base_dir) > 2
                    and base_dir[2] == ":"
                ):
                    base_dir = base_dir[1:]
            else:
                base_dir = base_url

        normalized_html = _normalize_image_tags(html_content)
        # Inline all local images as base64 data URIs so WeasyPrint never has
        # to touch the filesystem for images — essential in a bundled .app.
        normalized_html = _inline_local_images(normalized_html, base_dir)
        full_html = _wrap_html_for_pdf(normalized_html)

        # No base_url / url_fetcher needed: all local resources are now inlined.
        html = HTML(string=full_html)
        html.write_pdf(output_path)
    except Exception:
        import traceback

        traceback.print_exc()
        raise
