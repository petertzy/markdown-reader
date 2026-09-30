"""Render the preview's math nodes offline before handing HTML to PDF engines."""

from __future__ import annotations

import base64

from bs4 import BeautifulSoup


def render_pdf_math(html_content: str) -> str:
    """Embed typeset formulas as images supported by both PDF backends.

    Only renderer-created math nodes are processed; code and currency are left
    alone. Fail explicitly if conversion fails instead of exporting raw TeX.
    """
    if 'class="math-' not in html_content:
        return html_content

    import fitz
    import ziamath

    # MuPDF needs SVG 1.1 paths rather than SVG 2 glyph references.
    ziamath.config.svg2 = False

    soup = BeautifulSoup(html_content, "html.parser")
    for node in soup.select("span.math-inline, div.math-display"):
        if node.find_parent(["pre", "code", "script", "style"]):
            continue
        display = "math-display" in node.get("class", [])
        opening, closing = (r"\[", r"\]") if display else (r"\(", r"\)")
        source = node.get_text()
        if not (source.startswith(opening) and source.endswith(closing)):
            continue
        formula = source[2:-2]
        try:
            math = ziamath.Latex(formula, size=18, inline=not display)
            svg = math.svg()
            # Rasterize at 3x resolution for consistent rendering in both
            # WeasyPrint and MuPDF, including embedded math font outlines.
            with fitz.open(stream=svg.encode(), filetype="svg") as document:
                page = document[0]
                width, height = page.rect.width, page.rect.height
                png = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=True).tobytes(
                    "png"
                )
            image = soup.new_tag("img")
            image["src"] = "data:image/png;base64," + base64.b64encode(png).decode()
            image["alt"] = formula
            image["style"] = (
                f"display:inline !important; margin:0 !important; width:{width / 18}em !important; height:{height / 18}em !important; "
                f"vertical-align:{(math.getyofst() - 1) / 18}em;"
            )
            node.clear()
            node.append(image)
        except Exception as exc:
            raise ValueError(f"Could not typeset PDF formula: {formula!r}") from exc
    return str(soup)
