from pathlib import Path
from urllib.parse import urlparse
import re

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
    
    if parsed.scheme in ('http', 'https'):
        # For remote URLs, fetch them
        try:
            response = requests.get(url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            return {
                'string': response.content,
                'mime_type': response.headers.get('Content-Type', 'image/png'),
                'encoding': None,
            }
        except Exception:
            # Return a placeholder or empty content if fetch fails
            return {
                'string': b'',
                'mime_type': 'image/png',
                'encoding': None,
            }
    elif parsed.scheme == 'file':
        # For file URLs, use the default behavior
        file_path = parsed.path
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return {
                'string': content,
                'mime_type': 'application/octet-stream',
                'encoding': None,
            }
        except Exception:
            return {
                'string': b'',
                'mime_type': 'application/octet-stream',
                'encoding': None,
            }
    else:
        # For other schemes, try to handle as file path
        try:
            with open(url, 'rb') as f:
                content = f.read()
            return {
                'string': content,
                'mime_type': 'application/octet-stream',
                'encoding': None,
            }
        except Exception:
            return {
                'string': b'',
                'mime_type': 'application/octet-stream',
                'encoding': None,
            }


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
        tag = re.sub(r'\swidth\s*=\s*(["\']).*?\1', '', tag, flags=re.IGNORECASE)
        tag = re.sub(r'\sheight\s*=\s*(["\']).*?\1', '', tag, flags=re.IGNORECASE)
        tag = re.sub(r'\swidth\s*=\s*\S+', '', tag, flags=re.IGNORECASE)
        tag = re.sub(r'\sheight\s*=\s*\S+', '', tag, flags=re.IGNORECASE)
        return tag

    return re.sub(r'<img\b[^>]*>', _strip_size_attributes, html_content, flags=re.IGNORECASE)

def export_markdown_to_pdf(html_content: str, output_path: str, base_url: str = None):
    """ 
    Export rendered HTML content to PDF 

    Args:
        html_content (str): HTML string already rendered from Markdown 
        output_path (str): Target PDF file path  
        base_url (str): Base URL for resolving relative image paths (e.g., '/path/to/dir' or 'file:///path/to/dir/')
    """
    try:
        # Prepare the base_url for HTML
        if base_url:
            # Convert Windows paths to proper file URLs
            if not base_url.startswith('file://'):
                base_url = Path(base_url).as_uri()

        normalized_html = _normalize_image_tags(html_content)
        full_html = _wrap_html_for_pdf(normalized_html)

        # Create HTML object with custom URL fetcher in the constructor
        html = HTML(string=full_html, base_url=base_url, url_fetcher=custom_url_fetcher)

        # Write PDF
        html.write_pdf(output_path)
    except Exception:
        import traceback
        traceback.print_exc()
        raise



