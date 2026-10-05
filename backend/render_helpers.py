"""
Lightweight Markdown rendering helpers for the FastAPI backend.

These functions mirror the legacy desktop helpers without importing the
tkinter-era application module. Keeping this path small matters for packaged
sidecar cold starts.
"""

from __future__ import annotations

import os
import re
import secrets


def _fresh_token(prefix: str, text: str) -> str:
    """Return a placeholder token that cannot collide with document text."""
    while True:
        token = f"{prefix}{secrets.token_hex(6)}"
        if token not in text:
            return token


class _PlaceholderFactory:
    """Generate unique, collision-proof placeholder tokens for masking."""

    def __init__(self, prefix: str, text: str, replacements: dict[str, str]) -> None:
        self._token = _fresh_token(prefix, text)
        self._counter = 0
        self._replacements = replacements

    def __call__(self, content: str) -> str:
        key = f"{self._token}{self._counter}X"
        self._counter += 1
        self._replacements[key] = content
        return key


def _mask_code_regions(markdown_text: str, replacements: dict[str, str]) -> str:
    """Temporarily mask code spans so math detection can't touch them."""
    text = markdown_text or ""
    factory = _PlaceholderFactory("CODEPLACEHOLDER", text, replacements)

    # Fenced code blocks: ``` ... ``` or ~~~ ... ~~~, spanning lines.
    text = re.sub(
        r"(?ms)^(`{3,}|~{3,})[^\n]*\n.*?^\1[^\n]*\n?$",
        lambda m: factory(m.group(0)),
        text,
    )

    # Inline code spans: one or two backticks with non-backtick content.
    text = re.sub(
        r"(?<!`)(`{1,2})[^`\n]+(?<!\n)\1(?!`)",
        lambda m: factory(m.group(0)),
        text,
    )

    return text


def protect_math(markdown_text: str) -> tuple[str, dict[str, str]]:
    """Protect math expressions from being escaped by markdown2."""
    text = markdown_text or ""
    replacements: dict[str, str] = {}
    factory = _PlaceholderFactory("MATHPLACEHOLDER", text, replacements)

    def make_placeholder(content: str, display: bool = False) -> str:
        key = factory(content)
        if display:
            replacements[key] = f'<div class="math-display">\\[{content}\\]</div>'
        else:
            replacements[key] = f'<span class="math-inline">\\({content}\\)</span>'
        return key

    def replace_block(match: re.Match[str]) -> str:
        return make_placeholder(match.group(1), display=True)

    def replace_inline(match: re.Match[str]) -> str:
        return make_placeholder(match.group(1), display=False)

    # Mask code spans first so "$...$" inside literals isn't rewritten
    # into math markup (e.g. an awk "{print $1, $2}" example line).
    code_replacements: dict[str, str] = {}
    text = _mask_code_regions(markdown_text, code_replacements)

    text = re.sub(r"\$\$([\s\S]+?)\$\$", replace_block, text)

    # Dollar math requires non-whitespace next to both inner boundaries.
    # A closing dollar cannot introduce another numeric amount. Together
    # these rules preserve currency prose without rejecting $2x$ or $5$.
    # Escaped dollars and double-dollar delimiters are not inline boundaries.
    text = re.sub(
        r"(?<![\$\\])\$(?![\s$])([^\$\n]+?)(?<![\s$\\])\$(?![\d$])",
        replace_inline,
        text,
    )

    # Restore the code spans so markdown2 still renders them as code.
    for key, value in code_replacements.items():
        text = text.replace(key, value)

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
    """Resolve relative Markdown image paths against a base directory.

    Fenced blocks and inline code spans are masked out first. Image syntax
    inside them is literal sample text, not an image to load, and rewriting it
    corrupts the code the author is showing: a tutorial demonstrating
    ``![diagram](diagram.png)`` had its own example rewritten to an absolute
    ``file://`` URL in the rendered preview. Reuses the same code-region masking
    that :func:`protect_math` relies on, so both agree on what counts as code.
    """

    def replace_image(match: re.Match[str]) -> str:
        alt = match.group(1)
        src = match.group(2)
        if src.startswith(("http://", "https://", "file://", "/")):
            return match.group(0)
        abs_path = os.path.abspath(os.path.join(base_path, src))
        abs_url = "file://" + abs_path.replace("\\", "/")
        return f"![{alt}]({abs_url})"

    code_replacements: dict[str, str] = {}
    text = _mask_code_regions(markdown_text or "", code_replacements)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, text)

    # Restore the code spans verbatim.
    for key, value in code_replacements.items():
        text = text.replace(key, value)

    return text
