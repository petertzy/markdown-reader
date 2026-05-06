"""
Lightweight Markdown rendering helpers for the FastAPI backend.

These functions mirror the legacy desktop helpers without importing the
tkinter-era application module. Keeping this path small matters for packaged
sidecar cold starts.
"""

from __future__ import annotations

import os
import re


def protect_math(markdown_text: str) -> tuple[str, dict[str, str]]:
    """Protect math expressions from being escaped by markdown2."""
    replacements: dict[str, str] = {}
    counter = 0

    def make_placeholder(content: str, display: bool = False) -> str:
        nonlocal counter
        key = f"MATHPLACEHOLDER{counter}X"
        counter += 1
        if display:
            replacements[key] = f'<div class="math-display">\\[{content}\\]</div>'
        else:
            replacements[key] = f'<span class="math-inline">\\({content}\\)</span>'
        return key

    def replace_block(match: re.Match[str]) -> str:
        return make_placeholder(match.group(1), display=True)

    def replace_inline(match: re.Match[str]) -> str:
        return make_placeholder(match.group(1), display=False)

    text = re.sub(r"\$\$([\s\S]+?)\$\$", replace_block, markdown_text)
    text = re.sub(r"(?<!\$)\$(?!\$)([^\$\n]+?)(?<!\$)\$(?!\$)", replace_inline, text)
    return text, replacements


def restore_math(html_content: str, replacements: dict[str, str]) -> str:
    """Restore MathJax-compatible HTML placeholders."""
    for key, value in replacements.items():
        html_content = html_content.replace(key, value)
        html_content = html_content.replace(f"<p>{key}</p>", value)
    return html_content


def get_math_styles() -> str:
    return """
        .math-display {
            display: block;
            text-align: center;
            margin: 1em 0;
            overflow-x: auto;
        }
        .math-inline {
            display: inline;
        }
    """


def get_mathjax_script() -> str:
    return """
        <script>
            window.MathJax = {
                tex: {
                    inlineMath: [['\\\\(', '\\\\)']],
                    displayMath: [['\\\\[', '\\\\]']],
                    processEscapes: true,
                    processEnvironments: true
                },
                options: {
                    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
                }
            };
        </script>
        <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
    """


def fix_image_paths(markdown_text: str, base_path: str) -> str:
    """Resolve relative Markdown image paths against a base directory."""

    def replace_image(match: re.Match[str]) -> str:
        alt = match.group(1)
        src = match.group(2)
        if src.startswith(("http://", "https://", "file://", "/")):
            return match.group(0)
        abs_path = os.path.abspath(os.path.join(base_path, src))
        abs_url = "file://" + abs_path.replace("\\", "/")
        return f"![{alt}]({abs_url})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, markdown_text)
