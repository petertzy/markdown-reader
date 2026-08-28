"""
renderer.py
===========
Standalone Markdown-to-HTML renderer for the FastAPI backend
so it can be used in the FastAPI backend without requiring a tkinter app object.
"""

from __future__ import annotations

import os
import re
import sys
from html import escape as html_escape
from html.parser import HTMLParser

# Ensure the project root is on sys.path for standalone backend execution.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import markdown2

from backend.render_helpers import (
    fix_image_paths,
    get_math_styles,
    get_mathjax_script,
    protect_math,
    restore_math,
)

_BARE_URL_RE = re.compile(r"https?://[^\s<]+")
_AUTOLINK_SKIP_TAGS = {"a", "code", "pre", "script", "style"}
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}"


def _linkify_bare_urls(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in _BARE_URL_RE.finditer(text):
        url = match.group(0)
        trailing = ""
        while url and url[-1] in _TRAILING_URL_PUNCTUATION:
            trailing = url[-1] + trailing
            url = url[:-1]
        if not url:
            continue
        parts.append(html_escape(text[last : match.start()]))
        escaped_url = html_escape(url, quote=True)
        parts.append(
            f'<a href="{escaped_url}" target="_blank" rel="noopener">{html_escape(url)}</a>'
        )
        parts.append(html_escape(trailing))
        last = match.end()
    parts.append(html_escape(text[last:]))
    return "".join(parts)


class _BareUrlLinkifier(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.skip_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        self.parts.append(self.get_starttag_text() or "")
        if tag.lower() in _AUTOLINK_SKIP_TAGS:
            self.skip_stack.append(tag.lower())

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        tag = tag.lower()
        if self.skip_stack and self.skip_stack[-1] == tag:
            self.skip_stack.pop()

    def handle_data(self, data: str) -> None:
        self.parts.append(
            html_escape(data) if self.skip_stack else _linkify_bare_urls(data)
        )

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")


def linkify_bare_urls(html: str) -> str:
    parser = _BareUrlLinkifier()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def render_markdown(
    markdown_text: str,
    *,
    base_dir: str | None = None,
    dark_mode: bool = False,
    font_family: str = "system-ui, sans-serif",
    font_size: int = 14,
) -> str:
    """
    Convert Markdown text to a full, self-contained HTML document string.

    Parameters
    ----------
    markdown_text : str
        Raw Markdown source.
    base_dir : str | None
        Directory used to resolve relative image paths (optional).
    dark_mode : bool
        Apply a dark-mode colour scheme.
    font_family : str
        CSS font-family for the body text.
    font_size : int
        Base font size in pixels.

    Returns
    -------
    str
        Full HTML document as a string.
    """
    text = markdown_text or ""

    if base_dir:
        text = fix_image_paths(text, base_dir)

    # Protect math before markdown processing
    protected, math_replacements = protect_math(text)

    try:
        html_content = markdown2.markdown(
            protected,
            extras=[
                "fenced-code-blocks",
                "code-friendly",
                "tables",
                "break-on-newline",
                # Keep links usable when exported HTML is shared as a file.
                # markdown2 adds rel="noopener" alongside target="_blank".
                "target-blank-links",
            ],
        )
        html_content = restore_math(html_content, math_replacements)
        html_content = linkify_bare_urls(html_content)
    except Exception:
        import traceback

        tb = traceback.format_exc()
        html_content = f"<h2>Error generating preview</h2><pre>{html_escape(tb)}</pre>"

    # Colour scheme
    if dark_mode:
        bg_color = "#1e1e1e"
        fg_color = "#dcdcdc"
        code_bg = "#2d2d2d"
        code_fg = "#dcdcdc"
        table_header_bg = "#2a2a2a"
        table_header_fg = "#ccc"
        table_alt_bg = "#252525"
        border_color = "#444"
    else:
        bg_color = "#ffffff"
        fg_color = "#1a1a1a"
        code_bg = "#f4f4f4"
        code_fg = "#000000"
        table_header_bg = "#f3f3f3"
        table_header_fg = "#333"
        table_alt_bg = "#fafafa"
        border_color = "#ccc"

    h1 = font_size + 18
    h2 = font_size + 12
    h3 = font_size + 8
    h4 = font_size + 4
    h5 = font_size + 2
    h6 = font_size + 1
    base = font_size + 2

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    {get_math_styles()}
    .copy-button {{
      position: absolute;
      top: 8px;
      right: 8px;
      background: #cacbd0;
      color: #313234;
      font-size: 0.7em;
      padding: 2px 6px;
      border: none;
      border-radius: 3px;
      cursor: pointer;
      z-index: 10;
    }}
    .copy-button:hover {{ background: #a5a8b6; }}
    body {{
      background-color: {bg_color};
      color: {fg_color};
      font-family: {font_family};
      padding: 24px 32px;
      font-size: {base}px;
      line-height: 1.65;
      max-width: 900px;
      margin: 0 auto;
    }}
    h1 {{ font-size: {h1}px; }}
    h2 {{ font-size: {h2}px; }}
    h3 {{ font-size: {h3}px; }}
    h4 {{ font-size: {h4}px; }}
    h5 {{ font-size: {h5}px; }}
    h6 {{ font-size: {h6}px; }}
    b, strong {{ font-weight: bold; }}
    i, em {{ font-style: italic; }}
    u {{ text-decoration: underline; }}
    pre {{
      position: relative;
    }}
    pre code {{
      background-color: {code_bg};
      color: {code_fg};
      font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
      font-size: {max(font_size - 2, 10)}px;
      padding: 28px 14px 14px 14px;
      border-radius: 6px;
      overflow-x: auto;
      display: block;
      white-space: pre;
    }}
    code {{
      background-color: {code_bg};
      color: {code_fg};
      font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
      font-size: {max(font_size - 2, 10)}px;
      padding: 0 4px;
      border-radius: 3px;
    }}
    img {{
      max-width: 90%;
      height: auto;
      display: block;
      margin: 12px 0;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 16px 0;
      font-size: {base}px;
    }}
    th, td {{
      text-align: left;
      border: 1px solid {border_color};
      padding: 10px 14px;
      vertical-align: top;
    }}
    th {{
      background-color: {table_header_bg};
      color: {table_header_fg};
    }}
    tr:nth-child(even) td {{ background-color: {table_alt_bg}; }}
    blockquote {{
      border-left: 4px solid {border_color};
      margin: 0;
      padding: 4px 16px;
      color: {"#aaa" if dark_mode else "#666"};
    }}
    hr {{
      border: none;
      border-top: 1px solid {border_color};
      margin: 20px 0;
    }}
    a {{ color: {"#7ab3f5" if dark_mode else "#0070f3"}; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
  <script>
    document.addEventListener('DOMContentLoaded', function() {{
      document.querySelectorAll('a').forEach(function(link) {{
        if (link.href.startsWith('http://') || link.href.startsWith('https://')) {{
          link.setAttribute('target', '_blank');
          link.setAttribute('rel', 'noopener noreferrer');
        }}
      }});
      
      document.querySelectorAll('pre code').forEach(function(block) {{
        var btn = document.createElement('button');
        btn.className = 'copy-button';
        btn.textContent = 'Copy';
        var pre = block.parentElement;
        pre.appendChild(btn);
        btn.addEventListener('click', function() {{
          navigator.clipboard.writeText(block.innerText).then(function() {{
            btn.textContent = 'Copied!';
            setTimeout(function() {{ btn.textContent = 'Copy'; }}, 1200);
          }});
        }});
      }});
    }});
  </script>
  {get_mathjax_script()}
</head>
<body>
  {html_content}
</body>
</html>"""
