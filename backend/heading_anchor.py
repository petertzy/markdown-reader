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
from html.parser import HTMLParser

# Matches ATX headings: `# Heading` … `###### Heading` (trailing closing
# hashes such as `# Heading #` are allowed, as in CommonMark). The separator
# is horizontal space only: `\s` would swallow a newline, so a bare `#` line
# followed by text would be reported as a heading made of the next line.
_ATX_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]*#+[ \t]*)?$", re.MULTILINE)

# Characters stripped when building a GitHub-style slug.
_NON_WORD_RE = re.compile(r"[^\w\s-]")
_WHITESPACE_RE = re.compile(r"\s+")

# Common inline Markdown markup removed from a heading before slugging so
# the anchor reflects what a reader sees, mirroring GitHub's behaviour.
# Each branch that carries visible text captures it: group 1 for an image's alt
# text, group 2 for a link's label. The remaining branches match no group and so
# are dropped by the `\1\2` replacement.
_INLINE_MARKUP_RE = re.compile(
    r"\*{1,2}|_{1,2}|`|~~"
    r"|!\[([^\]]*)\](?:\(.*?\)|\[[^\]]*\])"
    r"|\[([^\]]*)\](?:\(.*?\)|\[[^\]]*\])"
)

# Angle-bracket autolinks (`<https://example.com>`, `<foo@example.com>`) are
# rendered as real links; the brackets are dropped but the link text kept so
# the anchor matches the link markdown2 actually produces. Only the schemes the
# renderer autolinks count -- http/https/ftp URLs and email addresses, with an
# optional ``mailto:`` that is not part of the visible text. Any other
# angle-bracket text (``<tel:555>``, ``<foo:bar>``) stays an invisible HTML
# element and contributes nothing.
_AUTOLINK_RE = re.compile(
    r"<(?:mailto:)?((?:https?|ftp):[^<>\s]*|[\w.+-]+@[\w.-]+\.[a-zA-Z]+)>"
)

# An inline `<img>` contributes its ``alt`` text to the anchor, exactly like
# the renderer's ``_note_inline_image`` does for the preview's heading ids.
# Attribute values may be double-quoted, single-quoted or unquoted (all valid
# HTML). Match one whole tag, including a ``>`` in a quoted value, then use the
# same HTML attribute parsing rules as the renderer rather than trying to
# identify an ``alt`` attribute with a regular expression.
_INLINE_IMAGE_TAG_RE = re.compile(
    r"""<img\b(?:[^>"']+|"[^"]*"|'[^']*')*>""",
    re.IGNORECASE | re.DOTALL,
)


class _InlineImageAltParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.alt = ""

    def _record_image(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "img":
            self.alt = dict(attrs).get("alt") or ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record_image(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record_image(tag, attrs)


def _inline_image_alt(tag: str) -> str:
    parser = _InlineImageAltParser()
    parser.feed(tag)
    parser.close()
    return parser.alt


# Every other angle-bracket form -- a tag such as ``<b>`` or ``<sup>``, an HTML
# comment, a doctype, a processing instruction -- is removed while its interior
# text survives, so ``<sup>th</sup>`` reads as ``th`` exactly as the preview
# renders it. ``<img>`` is consumed above; the empty match leaves real
# characters like ``a < b`` untouched (no closing ``>`` to form a token).
_HTML_RAW_TOKEN_RE = re.compile(
    r"<!--.*?-->|<\?.*?\?>|<!DOCTYPE[^<>]*>|</?[a-zA-Z][a-zA-Z0-9]*[^<>]*>",
    re.IGNORECASE | re.DOTALL,
)


def extract_heading_text(raw_text: str) -> str:
    """Strip inline Markdown from a heading so the label reads as plain text.

    Handles bold/italic (``**``/``*``/``__``/``_``), inline code (``...``),
    strikethrough (``~~...~~``) and links/images (``[text](url)`` and
    ``![alt](url)`` keep their visible text). Inline HTML contributes only
    the text the preview shows: ``<sup>th</sup>`` reads as ``th``, an
    ``<img alt="X">`` as ``X``, and an autolink such as
    ``<https://example.com>`` as ``https://example.com``. HTML entities are
    decoded so the visible label — and the slug derived from it — matches
    what the rendered preview shows.
    """
    text = raw_text or ""
    text = _AUTOLINK_RE.sub(r"\1", text)
    text = _INLINE_IMAGE_TAG_RE.sub(lambda m: _inline_image_alt(m.group()), text)
    text = _HTML_RAW_TOKEN_RE.sub("", text)
    plain = html_unescape(_INLINE_MARKUP_RE.sub(r"\1\2", text))
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


def unique_heading_slug(base: str, counts: dict[str, int]) -> str:
    """Allocate an unused ID, including collisions with literal suffixed titles."""
    count = counts.get(base, 0)
    candidate = base if count == 0 else f"{base}-{count}"
    while candidate in counts:
        count += 1
        candidate = f"{base}-{count}"
    counts[base] = count + 1
    counts.setdefault(candidate, 1)
    return candidate


# Match the backtick fences supported by the renderer's fenced-code-blocks extra.
_FENCED_CODE_RE = re.compile(
    r"(^[ \t]*`{3,})[ \t]*[\w+-]*[ \t]*\n.*?^\1[ \t]*(?:\n|$)",
    re.MULTILINE | re.DOTALL,
)


def iter_heading_matches(markdown: str):
    """Ignore fenced examples while retaining source offsets for outline lines."""
    masked = _FENCED_CODE_RE.sub(
        lambda match: re.sub(r"[^\r\n]", " ", match.group()), markdown or ""
    )
    return _ATX_HEADING_RE.finditer(masked)
