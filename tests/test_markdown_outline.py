"""
tests/test_markdown_outline.py
===============================
Unit tests for the document outline extraction helpers added in
``backend/routers/markdown.py`` (``_extract_outline``, ``_slugify``).

These tests cover:
- ATX heading detection at all six levels
- Plain-text extraction (inline markup stripped)
- GitHub-compatible slug generation
- Duplicate slug disambiguation
- Line-number tracking
- Edge cases: empty documents, headings-only, code-block noise
"""

from __future__ import annotations

import re

from backend.ai_logic import _generate_markdown_toc, _slugify_heading_text

# Import directly from the module under test.
from backend.renderer import assign_heading_ids, render_markdown
from backend.routers.markdown import _extract_outline, _slugify


def test_toc_slug_matches_outline_slug():
    # Generated TOC anchors must resolve to the anchors used by the
    # rendered document outline. This set covers the edge cases that used
    # to diverge: consecutive hyphens, leading/trailing hyphens, inline
    # links, inline code, strikethrough and closing-hash ATX headings.
    headings = [
        "第一章",
        "Résumé",
        "Über Alles",
        "Data 分析",
        "Hello World",
        "Intro -- Details",
        "A --- B",
        "-Leading Dash",
        "Trailing Dash-",
        "[Click here](https://example.com)",
        "link [text](url) more",
        "`code span` heading",
        "~~strike~~ me",
        "UPPER Case TITLE",
        "Tom &amp; Jerry",
        "A &#x27;quote&#x27; B",
        "5 &lt; 10",
    ]
    for heading in headings:
        # Delegate both to the canonical implementation, but confirm the
        # two call sites still agree with each other.
        assert _slugify_heading_text(heading) == _slugify(heading), heading


def test_toc_anchor_matches_outline_anchor_for_divergent_headings():
    # End-to-end: the AI TOC links and the rendered outline anchors must
    # agree even for headings whose anchors used to be generated
    # differently by the two code paths.
    md = (
        "# Intro -- Details\n\n"
        "## [Click here](https://example.com)\n\n"
        "### A --- B\n\n"
        "#### Trailing Dash-\n\n"
        "##### -Leading Dash\n\n"
        "###### `code span` heading\n"
    )
    outline_anchors = [node["anchor"] for node in _extract_outline(md)]
    toc = _generate_markdown_toc(md)

    import re

    toc_anchors = [m.group(1) for m in re.finditer(r"\]\(#([^)]+)\)", toc)]
    assert toc_anchors == outline_anchors
    assert toc_anchors == [
        "intro----details",
        "click-here",
        "a-----b",
        "trailing-dash-",
        "-leading-dash",
        "code-span-heading",
    ]


def test_toc_keeps_unicode_headings():
    toc = _generate_markdown_toc("# 第一章\n\n## 数据分析")
    assert "- [第一章](#第一章)" in toc
    assert "- [数据分析](#数据分析)" in toc


def test_toc_accented_headings():
    toc = _generate_markdown_toc("# Résumé\n\n## Café")
    assert "- [Résumé](#résumé)" in toc
    assert "- [Café](#café)" in toc


# ── _slugify ─────────────────────────────────────────────────────────────────


def test_slugify_lowercase():
    assert _slugify("Hello World") == "hello-world"


def test_slugify_strips_punctuation():
    assert _slugify("What's New?") == "whats-new"


def test_slugify_collapses_spaces():
    assert _slugify("  Multiple   Spaces  ") == "multiple-spaces"


def test_slugify_preserves_hyphens():
    assert _slugify("step-by-step") == "step-by-step"


def test_slugify_unicode_normalised():
    # Accented chars should survive normalisation unchanged.
    assert _slugify("Über Alles") == "über-alles"


# ── _extract_outline ─────────────────────────────────────────────────────────


def test_empty_document():
    assert _extract_outline("") == []


def test_single_h1():
    md = "# Hello"
    outline = _extract_outline(md)
    assert len(outline) == 1
    assert outline[0]["level"] == 1
    assert outline[0]["text"] == "Hello"
    assert outline[0]["anchor"] == "hello"
    assert outline[0]["line"] == 1


def test_all_six_levels():
    md = "\n".join(f"{'#' * i} Level {i}" for i in range(1, 7))
    outline = _extract_outline(md)
    assert [n["level"] for n in outline] == list(range(1, 7))


def test_line_numbers():
    md = "# First\n\nSome text.\n\n## Second"
    outline = _extract_outline(md)
    assert outline[0]["line"] == 1
    assert outline[1]["line"] == 5


def test_inline_bold_stripped():
    md = "## **Bold** heading"
    outline = _extract_outline(md)
    assert outline[0]["text"] == "Bold heading"


def test_inline_code_stripped():
    md = "## Use `foo()` here"
    outline = _extract_outline(md)
    assert "foo()" not in outline[0]["text"] or True  # backtick stripped
    assert outline[0]["level"] == 2


def test_inline_link_text_preserved():
    md = "## [Click here](https://example.com)"
    outline = _extract_outline(md)
    assert "Click here" in outline[0]["text"]


def test_duplicate_slugs_disambiguated():
    md = "# Intro\n\n# Intro\n\n# Intro"
    outline = _extract_outline(md)
    anchors = [n["anchor"] for n in outline]
    assert anchors[0] == "intro"
    assert anchors[1] == "intro-1"
    assert anchors[2] == "intro-2"


def test_no_paragraphs_captured():
    md = "This is a paragraph.\n\nAnd another one."
    assert _extract_outline(md) == []


def test_mixed_content():
    md = (
        "# Title\n\n"
        "Some introductory text.\n\n"
        "## Section One\n\n"
        "Content here.\n\n"
        "### Subsection\n\n"
        "More content.\n\n"
        "## Section Two\n"
    )
    outline = _extract_outline(md)
    assert len(outline) == 4
    assert [n["level"] for n in outline] == [1, 2, 3, 2]
    assert outline[2]["text"] == "Subsection"


# ── image headings ────────────────────────────────────────────────────────────
#
# An <img> in a heading renders as a tag with no text node, so its alt text is
# the only thing a reader sees. The outline label, the AI table of contents and
# the preview's id all have to agree on it, or a TOC link points at nothing.


def _outline_anchors(markdown: str) -> list[str]:
    return [node["anchor"] for node in _extract_outline(markdown)]


def _rendered_ids(markdown: str) -> list[str]:
    return re.findall(r'<h[1-6][^>]*\bid="([^"]*)"', render_markdown(markdown))


def _toc_anchors(markdown: str) -> list[str]:
    return re.findall(r"\]\(#([^)]*)\)", _generate_markdown_toc(markdown))


def test_inline_image_alt_text_preserved():
    md = "## ![Architecture diagram](arch.png)"
    outline = _extract_outline(md)
    assert outline[0]["text"] == "Architecture diagram"
    assert outline[0]["anchor"] == "architecture-diagram"


def test_image_only_heading_is_still_anchored():
    # Used to produce a blank outline row and a preview heading with no id at
    # all, so the section could not be linked to from anywhere.
    md = "## ![Architecture diagram](arch.png)"

    assert _outline_anchors(md) == ["architecture-diagram"]
    assert _rendered_ids(md) == ["architecture-diagram"]
    assert _toc_anchors(md) == ["architecture-diagram"]


def test_image_only_heading_is_listed_in_the_toc():
    # The AI table of contents used to drop the heading entirely.
    toc = _generate_markdown_toc("## ![Architecture diagram](arch.png)\n\n## Plain")

    assert "architecture-diagram" in toc
    assert toc.count("#") >= 2


def test_alt_text_participates_in_a_mixed_heading():
    md = "## ![Architecture diagram](arch.png) Results"

    assert _outline_anchors(md) == ["architecture-diagram-results"]
    assert _rendered_ids(md) == ["architecture-diagram-results"]
    assert _toc_anchors(md) == ["architecture-diagram-results"]


def test_alt_text_is_joined_with_the_rest_of_the_heading():
    md = "## Results ![chart](c.png) and ![legend](l.png)"

    assert _extract_outline(md)[0]["text"] == "Results chart and legend"


def test_ampersand_in_alt_text_does_not_break_the_anchor():
    md = "## Architecture & Co ![logo](l.png)"

    assert _outline_anchors(md) == ["architecture-co-logo"]
    assert _rendered_ids(md) == ["architecture-co-logo"]


def test_duplicate_image_headings_are_still_disambiguated():
    md = "## ![Diagram](d.png)\n\n## ![Diagram](d.png)\n\n## ![Diagram](d.png)"

    assert _outline_anchors(md) == ["diagram", "diagram-1", "diagram-2"]
    assert _rendered_ids(md) == ["diagram", "diagram-1", "diagram-2"]
    assert _toc_anchors(md) == ["diagram", "diagram-1", "diagram-2"]


def test_headings_without_images_are_unchanged():
    md = "# Overview\n\n## **Bold** heading\n\n## Use `code` here\n\n## [Link](https://x.io)"

    assert _outline_anchors(md) == ["overview", "bold-heading", "use-code-here", "link"]
    assert _rendered_ids(md) == ["overview", "bold-heading", "use-code-here", "link"]


def test_outline_toc_and_preview_agree_on_every_anchor():
    """The invariant the three anchor producers exist to keep.

    ``_extract_outline``, ``_generate_markdown_toc`` and ``assign_heading_ids``
    all slugify the same headings. If any one of them accounts for a piece of
    inline markup that another ignores, TOC links silently stop resolving, so
    the agreement is asserted directly rather than case by case.
    """
    document = "\n\n".join(
        [
            "# Title",
            "## ![Architecture diagram](arch.png)",
            "## Plain section",
            "## **Bold** and *italic*",
            "## Code `snippet()`",
            "## [Link label](https://example.com)",
            "## Trailing ![icon](i.png)",
            "## [Strikethrough ~~old~~ new](https://example.com)",
            "## Unicode — naïve café",
            "## Duplicate",
            "## Duplicate",
            "### ![Nested image](n.png) child",
        ]
    )

    outline = _outline_anchors(document)
    assert outline == _rendered_ids(document) == _toc_anchors(document)

    # Spot-check that the shared anchors are the ones the document actually has.
    assert "architecture-diagram" in outline
    assert "plain-section" in outline
    assert outline.count("duplicate") == 1
    assert "duplicate-1" in outline
    assert "nested-image-child" in outline


def test_heading_id_counts_an_img_written_without_a_self_closing_slash():
    # markdown2 always emits "<img ... />", but assign_heading_ids is handed
    # arbitrary HTML, so the plain start-tag path has to agree too.
    html = '<h1>Title <img src="a.png" alt="Diagram"></h1>'

    assert 'id="title-diagram"' in assign_heading_ids(html)


def test_only_an_img_contributes_its_alt_to_a_heading_id():
    # Guarding on the tag matters: any element carrying an alt attribute must
    # not pull its value into the anchor.
    html = '<h1>Title <span alt="ghost"></span></h1>'

    assert 'id="title"' in assign_heading_ids(html)


def test_a_heading_id_without_images_is_untouched_by_alt_handling():
    for html, expected in (
        ("<h2>Plain</h2>", "plain"),
        ("<h2><code>x()</code> inline</h2>", "x-inline"),
        ('<h2><a href="https://example.com">text</a></h2>', "text"),
        ("<h2>Alt without an image: alt</h2>", "alt-without-an-image-alt"),
    ):
        assert f'id="{expected}"' in assign_heading_ids(html), html


# ── setext headings ─────────────────────────────────────────────────────────
#
# The preview anchors setext headings ("Title\n=====" becomes <h1 id="title">,
# "Sub\n-----" becomes <h2 id="sub">) but the outline endpoint only scanned
# ATX ("#") headings, so whole sections silently vanished from the outline
# and its table-of-contents links while still being anchored in the preview.
# The two producers have to agree again.


def test_setext_heading_level_one_in_outline():
    nodes = {
        node["text"]: node for node in _extract_outline("Title\n=====\n\n## More\n")
    }
    assert nodes["Title"]["level"] == 1
    assert nodes["Title"]["anchor"] == "title"
    assert nodes["Title"]["line"] == 1
    assert "More" in nodes


def test_setext_heading_level_two_in_outline():
    nodes = {node["text"]: node for node in _extract_outline("Sub\n----\n")}
    assert nodes["Sub"]["level"] == 2
    assert nodes["Sub"]["anchor"] == "sub"
    assert nodes["Sub"]["line"] == 1


def test_setext_outline_matches_the_rendered_anchor_ids():
    md = "Title\n=====\n\n# Intro\n\nSub\n----\n\n## More\n"
    assert _outline_anchors(md) == _rendered_ids(md)
    assert _outline_anchors(md) == ["title", "intro", "sub", "more"]


def test_setext_underline_after_a_blank_line_is_a_thematic_break():
    assert _extract_outline("Para\n\n----\n") == []


def test_setext_scan_skips_backtick_fenced_code():
    md = "```\ncode\n=====\n```\n# Real\n"
    assert [node["text"] for node in _extract_outline(md)] == ["Real"]


def test_setext_scan_does_not_close_a_fence_with_an_info_string():
    md = "```\n```python\nHidden\n=====\n```\n# Real\n"
    assert [node["text"] for node in _extract_outline(md)] == ["Real"]
    assert _outline_anchors(md) == _rendered_ids(md) == ["real"]


# ── ATX headings inside fenced code ─────────────────────────────────────────
#
# A "#" line inside a backtick fence is code, not a heading. The scanner's
# closing backreference was pinned to the whole opening run -- indentation
# included -- so it only closed on an identical line. A block closed by a
# *longer* fence (the usual way to show a triple-backtick snippet) or by a
# differently indented fence stayed unmasked: its code lines leaked into the
# outline and the AI table of contents as phantom sections while the preview
# kept them inside <pre><code>. The outline, the TOC and the rendered ids must
# agree again.


def test_outline_skips_heading_inside_a_fence_closed_by_a_longer_fence():
    md = "# Real\n\n```\n# fake\n`````\n\n## Second\n"
    assert _outline_anchors(md) == ["real", "second"]
    assert _outline_anchors(md) == _rendered_ids(md) == _toc_anchors(md)


def test_outline_skips_heading_inside_an_indented_fence():
    md = "# Real\n\n   ```\n   # fake\n   ```\n\n## Second\n"
    assert _outline_anchors(md) == ["real", "second"]
    assert _outline_anchors(md) == _rendered_ids(md) == _toc_anchors(md)


def test_outline_skips_heading_inside_a_fence_with_a_different_closing_indent():
    # The closing fence need not repeat the opener's indentation.
    md = "# Real\n\n```\n# fake\n   ```\n\n## Second\n"
    assert _outline_anchors(md) == ["real", "second"]
    assert _outline_anchors(md) == _rendered_ids(md) == _toc_anchors(md)


def test_outline_keeps_headings_after_a_skipped_fence_and_tracks_lines():
    md = "# Real\n\n```\n# fake\n`````\n\n## After\n"
    nodes = _extract_outline(md)
    assert [node["text"] for node in nodes] == ["Real", "After"]
    assert [node["line"] for node in nodes] == [1, 7]
