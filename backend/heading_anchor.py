"""
heading_anchor.py
=================
Canonical heading-anchor helpers shared by the document outline
(``backend/routers/markdown.py``) and the AI table-of-contents generator
(``backend/ai_logic.py``).

Both callers must produce identical ``#anchor`` targets so that a
``/toc`` link (``[Intro -- Details](#intro----details)``) actually
resolves against the rendered document's outline. Keeping the plain-text
stripping and slugging rules in one place guarantees the two never
diverge again.
"""

from __future__ import annotations

import re
import unicodedata
from html import unescape as html_unescape

# Matches ATX headings: `# Heading` … `###### Heading` (trailing closing
# hashes such as `# Heading #` are allowed, as in CommonMark).
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+\s*)?$", re.MULTILINE)

# Characters stripped when building a GitHub-style slug.
_NON_WORD_RE = re.compile(r"[^\w\s-]")
_WHITESPACE_RE = re.compile(r"\s+")

# Common inline Markdown markup removed from a heading before slugging so
# the anchor reflects what a reader sees, mirroring GitHub's behaviour.
_INLINE_MARKUP_RE = re.compile(
    r"\*{1,2}|_{1,2}|`|~~|!\[.*?\]\(.*?\)|\[([^\]]*)\]\(.*?\)"
)


def extract_heading_text(raw_text: str) -> str:
    """Strip inline Markdown from a heading so the label reads as plain text.

    Handles bold/italic (``**``/``*``/``__``/``_``), inline code (``...``),
    strikethrough (``~~...~~``) and links/images (``[text](url)`` keep
    their visible text; auto-links such as ``<https://example.com>`` are
    left intact). HTML entities are decoded so the visible label — and the
    slug derived from it — matches what the rendered preview shows.
    """
    plain = html_unescape(_INLINE_MARKUP_RE.sub(r"\1", raw_text or ""))
    return plain.strip()


def slugify_heading(text: str) -> str:
    """Produce a GitHub-compatible heading anchor from heading text.

    Preserves Unicode word characters and existing hyphens (``intro --
    details`` -> ``intro----details``), matching what GitHub renders for
    the same heading so TOC links resolve against the outline.
    """
    text = extract_heading_text(text)
    text = text.lower()
    # Normalise Unicode so accented chars are preserved but combining marks
    # that have no direct ASCII equivalent are stripped.
    text = unicodedata.normalize("NFC", text)
    text = _NON_WORD_RE.sub("", text)
    text = _WHITESPACE_RE.sub("-", text.strip())
    return text
