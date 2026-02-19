"""Extract text blocks and layout information from PDF using PyMuPDF.

Uses the detailed ``dict`` extraction mode to capture per-span font
metadata (size, color, bold/italic) so the renderer can reproduce the
original styling.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from .schemas import PageData, TextBlock


def _int_to_rgb(color_int: int) -> list[float]:
    """Convert a PyMuPDF integer color (0xRRGGBB) to an [r, g, b] list (0–1)."""
    r = ((color_int >> 16) & 0xFF) / 255.0
    g = ((color_int >> 8) & 0xFF) / 255.0
    b = (color_int & 0xFF) / 255.0
    return [round(r, 4), round(g, 4), round(b, 4)]


def _dominant_properties(
    spans: list[dict],
) -> tuple[float, list[float], bool, bool]:
    """Derive the dominant font size, color, bold, and italic from spans.

    Each property is weighted by the character length of the span so that
    the most-used style wins.
    """
    if not spans:
        return 11.0, [0.0, 0.0, 0.0], False, False

    size_w: dict[float, int] = {}
    color_w: dict[int, int] = {}
    bold_w = 0
    non_bold_w = 0
    italic_w = 0
    non_italic_w = 0

    for span in spans:
        w = len(span["text"])
        if w == 0:
            continue

        sz = round(span["size"], 1)
        size_w[sz] = size_w.get(sz, 0) + w

        col = span["color"]
        color_w[col] = color_w.get(col, 0) + w

        is_bold = bool(span["flags"] & (1 << 4)) or "bold" in span["font"].lower()
        if is_bold:
            bold_w += w
        else:
            non_bold_w += w

        is_italic = (
            bool(span["flags"] & (1 << 1))
            or "italic" in span["font"].lower()
            or "oblique" in span["font"].lower()
        )
        if is_italic:
            italic_w += w
        else:
            non_italic_w += w

    if not size_w:
        return 11.0, [0.0, 0.0, 0.0], False, False

    dom_size = max(size_w, key=size_w.get)  # type: ignore[arg-type]
    dom_color = _int_to_rgb(max(color_w, key=color_w.get))  # type: ignore[arg-type]
    dom_bold = bold_w > non_bold_w
    dom_italic = italic_w > non_italic_w

    return dom_size, dom_color, dom_bold, dom_italic


def extract_pages(pdf_path: str) -> list[PageData]:
    """Extract per-page text blocks with bounding boxes and font metadata."""
    doc = fitz.open(pdf_path)
    pages: list[PageData] = []

    for page_idx, page in enumerate(doc):
        rect = page.rect
        page_dict = page.get_text("dict")

        blocks: list[TextBlock] = []
        for blk_idx, block in enumerate(page_dict["blocks"]):
            if block["type"] != 0:  # skip image blocks
                continue

            all_spans: list[dict] = []
            lines_text: list[str] = []
            for line in block["lines"]:
                parts: list[str] = []
                for span in line["spans"]:
                    parts.append(span["text"])
                    all_spans.append(span)
                lines_text.append("".join(parts))

            text = "\n".join(lines_text).strip()
            if not text:
                continue

            font_size, color, is_bold, is_italic = _dominant_properties(all_spans)
            bbox = block["bbox"]

            blocks.append(
                TextBlock(
                    id=f"p{page_idx + 1}_b{blk_idx}",
                    bbox=[round(bbox[0], 2), round(bbox[1], 2), round(bbox[2], 2), round(bbox[3], 2)],
                    text=text,
                    font_size=font_size,
                    is_bold=is_bold,
                    is_italic=is_italic,
                    color=color,
                )
            )

        pages.append(
            PageData(
                page_number=page_idx + 1,
                width=round(rect.width, 2),
                height=round(rect.height, 2),
                blocks=blocks,
            )
        )

    doc.close()
    return pages


def total_text_length(pages: list[PageData]) -> int:
    """Return the total character count across all blocks."""
    return sum(len(b.text) for p in pages for b in p.blocks)
