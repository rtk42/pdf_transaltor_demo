"""Rebuild a translated PDF by overlaying translated text on the original.

Instead of creating a blank PDF from scratch (which loses images,
backgrounds, and vector graphics), this module:

1. Opens the *original* PDF with PyMuPDF.
2. For every extracted text block, adds a white-filled redaction
   annotation that erases only the original text.
3. Applies all redactions at once (images and line-art are preserved).
4. Inserts the translated text into each block's bounding box with
   the original font size, color, and bold/italic style.
5. Saves the result.
"""

from __future__ import annotations

import fitz  # PyMuPDF

from .schemas import PageData


def _pick_fontname(is_bold: bool, is_italic: bool) -> str:
    """Map bold/italic flags to a PyMuPDF built-in font short-name."""
    if is_bold and is_italic:
        return "hebi"  # Helvetica-BoldOblique
    if is_bold:
        return "hebo"  # Helvetica-Bold
    if is_italic:
        return "heit"  # Helvetica-Oblique
    return "helv"      # Helvetica


def render_pdf(
    pages: list[PageData],
    translations: dict[str, str],
    output_path: str,
    input_path: str,
) -> None:
    """Create the translated PDF by redacting + re-inserting text."""
    doc = fitz.open(input_path)

    for page_idx, page_data in enumerate(pages):
        if page_idx >= len(doc):
            break
        page = doc[page_idx]

        # --- Step 1: mark every text block for redaction ---
        for block in page_data.blocks:
            rect = fitz.Rect(block.bbox)
            # fill=(1,1,1) → white background replaces the original text
            page.add_redact_annot(rect, fill=(1, 1, 1))

        # --- Step 2: apply redactions (erases text, keeps images/graphics) ---
        page.apply_redactions(images=0, graphics=0)

        # --- Step 3: insert translated text at each bbox ---
        for block in page_data.blocks:
            text = translations.get(block.id, block.text)
            rect = fitz.Rect(block.bbox)

            fontname = _pick_fontname(block.is_bold, block.is_italic)
            color = tuple(block.color) if block.color else (0, 0, 0)
            fontsize = block.font_size

            # Try original size first; shrink if the text doesn't fit.
            while fontsize >= 5:
                rc = page.insert_textbox(
                    rect,
                    text,
                    fontsize=fontsize,
                    fontname=fontname,
                    color=color,
                    align=fitz.TEXT_ALIGN_LEFT,
                )
                if rc >= 0:  # non-negative → text fits
                    break
                fontsize -= 0.5
            else:
                # Last resort: use minimum readable size
                page.insert_textbox(
                    rect,
                    text,
                    fontsize=5,
                    fontname=fontname,
                    color=color,
                    align=fitz.TEXT_ALIGN_LEFT,
                )

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
