"""
Pure word-count helpers for the FastAPI backend.

The legacy word count module is tied to tkinter widgets. This module keeps the
API endpoint lightweight during packaged app startup.
"""

from __future__ import annotations

import re

_WPM = 238


def strip_markdown(text: str) -> str:
    """Remove common Markdown syntax tokens before counting words."""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"~~~[\s\S]*?~~~", " ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}|_{1,3}", "", text)
    text = re.sub(r"~~", "", text)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # A setext H1 underline is a run of "=" directly beneath a text line. It
    # becomes part of the heading when the document is rendered, so it must not
    # be counted as a word. The run needs a single "=": markdown2 turns "Title"
    # followed by "=" into an <h1>, exactly as it does for three. The text line
    # is required, so that a "=" that underlines nothing -- which stays literal
    # text in the rendered document -- keeps its word.
    text = re.sub(r"^([^\r\n]+)\r?\n=+[ \t]*\r?$", r"\1", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)
    # A GFM table delimiter row is made only of pipes, dashes and alignment
    # colons, so it holds no words. It has to be matched after the pipes are
    # turned into spaces, and after the horizontal-rule rule above (which
    # cannot see it while the leading pipe is still there).
    text = re.sub(r"^[\s:\-]*\-[\s:\-]*$", "", text, flags=re.MULTILINE)
    # Bullets, optionally followed by a GFM task-list checkbox.
    text = re.sub(r"^[\s]*[-*+]\s+(?:\[[ xX]\]\s+)?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    return text


def count_words(text: str) -> int:
    """Count words with basic CJK character support."""
    if not text.strip():
        return 0

    cjk_pattern = re.compile(
        r"[\u4e00-\u9fff"
        r"\u3400-\u4dbf"
        r"\U00020000-\U0002a6df"
        r"\u3040-\u309f"
        r"\u30a0-\u30ff"
        r"\uac00-\ud7af]"
    )
    spaced = cjk_pattern.sub(r" \g<0> ", text)
    return len(spaced.split())


def reading_time(word_count: int) -> str:
    """Return a human-readable estimated reading time string."""
    if word_count == 0:
        return "< 1 min read"
    minutes = word_count / _WPM
    if minutes < 1:
        return "< 1 min read"
    return f"{round(minutes)} min read"
