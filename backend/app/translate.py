"""Translate text segments using the OpenAI API."""

from __future__ import annotations

import json
import logging
import time
from typing import Callable, Optional

from openai import OpenAI

from . import config
from .schemas import Direction, TranslationSegment

logger = logging.getLogger(__name__)

# Rough limit: each chunk should stay well under the context window.
# We measure by character count of the source text (conservative proxy).
MAX_CHUNK_CHARS = 12_000


def _build_system_prompt(direction: Direction) -> str:
    if direction == Direction.DE_EN:
        src, tgt = "German", "English"
    else:
        src, tgt = "English", "German"

    return (
        f"You are a professional translator from {src} to {tgt}.\n"
        "You will receive a JSON object with a key \"segments\", which is an array of "
        "{\"id\": \"...\", \"text\": \"...\"}.\n"
        "Translate each segment's text accurately. Preserve:\n"
        "- Original meaning\n"
        "- Line breaks\n"
        "- Numbers, dates, and IDs unchanged\n"
        "Do NOT add or remove content.\n"
        "Return ONLY valid JSON with the same structure: "
        "{\"segments\": [{\"id\": \"...\", \"text\": \"TRANSLATED\"}]}"
    )


def _chunk_segments(
    segments: list[TranslationSegment],
) -> list[list[TranslationSegment]]:
    """Split segments into chunks that respect MAX_CHUNK_CHARS."""
    chunks: list[list[TranslationSegment]] = []
    current: list[TranslationSegment] = []
    current_chars = 0

    for seg in segments:
        seg_len = len(seg.text)
        if current and current_chars + seg_len > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(seg)
        current_chars += seg_len

    if current:
        chunks.append(current)
    return chunks


def _call_openai(
    client: OpenAI,
    system_prompt: str,
    segments: list[TranslationSegment],
    max_retries: int = 3,
) -> list[TranslationSegment]:
    """Call OpenAI with retry + exponential backoff."""
    user_payload = json.dumps(
        {"segments": [{"id": s.id, "text": s.text} for s in segments]},
        ensure_ascii=False,
    )

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            data = json.loads(raw)
            return [TranslationSegment(**s) for s in data["segments"]]
        except Exception:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** (attempt + 1)
            logger.warning("OpenAI call failed (attempt %d), retrying in %ds", attempt + 1, wait)
            time.sleep(wait)

    # Unreachable, but keeps type checkers happy.
    raise RuntimeError("Translation failed after retries")


def translate_segments(
    segments: list[TranslationSegment],
    direction: Direction,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> dict[str, str]:
    """Translate a flat list of segments and return {id: translated_text}.

    ``on_progress(done_chunks, total_chunks)`` is called after each chunk.
    """
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    system_prompt = _build_system_prompt(direction)
    chunks = _chunk_segments(segments)
    total = len(chunks)

    result_map: dict[str, str] = {}

    for idx, chunk in enumerate(chunks):
        translated = _call_openai(client, system_prompt, chunk)
        for seg in translated:
            result_map[seg.id] = seg.text
        if on_progress:
            on_progress(idx + 1, total)

    return result_map
