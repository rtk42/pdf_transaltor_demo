"""Extract text blocks and layout information from PDF using PyMuPDF."""

from __future__ import annotations

import fitz  # PyMuPDF

from .schemas import PageData, TextBlock


def extract_pages(pdf_path: str) -> list[PageData]:
    """Extract per-page text blocks with bounding boxes from a PDF.

    Returns a list of PageData, one per page. Each page contains its
    dimensions and a list of text blocks with bounding boxes.
    """
    doc = fitz.open(pdf_path)
    pages: list[PageData] = []

    for page_idx, page in enumerate(doc):
        rect = page.rect
        raw_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, type)

        blocks: list[TextBlock] = []
        for blk in raw_blocks:
            # type 0 = text, type 1 = image
            if blk[6] != 0:
                continue
            text = blk[4].strip()
            if not text:
                continue
            block_id = f"p{page_idx + 1}_b{blk[5]}"
            blocks.append(
                TextBlock(
                    id=block_id,
                    bbox=[round(blk[0], 2), round(blk[1], 2), round(blk[2], 2), round(blk[3], 2)],
                    text=text,
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
