"""Rebuild a translated PDF from extracted page data and translations."""

from __future__ import annotations

import textwrap

from reportlab.lib.pagesizes import letter  # noqa: F401 – side effect import
from reportlab.lib.units import inch  # noqa: F401
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .schemas import PageData

# Register a Unicode-capable font for German characters.
# Helvetica is built-in and handles latin-1; for full Unicode we fall back
# to DejaVu if available, otherwise use Helvetica.
_FONT_NAME = "Helvetica"
try:
    import os

    _dejavu_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if os.path.exists(_dejavu_path):
        pdfmetrics.registerFont(TTFont("DejaVuSans", _dejavu_path))
        _FONT_NAME = "DejaVuSans"
except Exception:
    pass


def _fit_font_size(text: str, bbox_width: float, bbox_height: float, max_size: float = 11) -> float:
    """Heuristically pick a font size that lets text fit in the bbox."""
    # Rough: 0.6 * font_size ≈ average char width for proportional fonts
    avg_chars_per_line = max(bbox_width / (0.6 * max_size), 1)
    lines = text.split("\n")
    wrapped_line_count = 0
    for line in lines:
        if not line.strip():
            wrapped_line_count += 1
            continue
        wrapped_line_count += max(1, -(-len(line) // int(avg_chars_per_line)))  # ceil div

    needed_height = wrapped_line_count * max_size * 1.2
    if needed_height <= bbox_height:
        return max_size

    # Scale down
    scale = bbox_height / needed_height
    return max(5, max_size * scale)


def render_pdf(
    pages: list[PageData],
    translations: dict[str, str],
    output_path: str,
) -> None:
    """Create a new PDF with translated text placed at original positions."""
    c = canvas.Canvas(output_path)

    for page in pages:
        c.setPageSize((page.width, page.height))

        for block in page.blocks:
            text = translations.get(block.id, block.text)
            x0, y0, x1, y1 = block.bbox
            bbox_width = x1 - x0
            bbox_height = y1 - y0

            # ReportLab y-axis is bottom-up; PDF extraction y-axis is top-down.
            rl_y_top = page.height - y0

            font_size = _fit_font_size(text, bbox_width, bbox_height)
            c.setFont(_FONT_NAME, font_size)

            # Wrap text to fit bbox width
            avg_char_width = 0.5 * font_size
            chars_per_line = max(int(bbox_width / avg_char_width), 10)

            raw_lines = text.split("\n")
            drawn_lines: list[str] = []
            for raw_line in raw_lines:
                if not raw_line.strip():
                    drawn_lines.append("")
                    continue
                drawn_lines.extend(textwrap.wrap(raw_line, width=chars_per_line) or [""])

            leading = font_size * 1.2
            cursor_y = rl_y_top - font_size  # first baseline

            for line in drawn_lines:
                if cursor_y < (page.height - y1 - leading):
                    break  # don't overflow past bbox bottom
                c.drawString(x0, cursor_y, line)
                cursor_y -= leading

        c.showPage()

    c.save()
