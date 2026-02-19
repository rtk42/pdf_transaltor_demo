"""Miscellaneous utility helpers."""

from __future__ import annotations

import os


def env_is_set(name: str) -> bool:
    """Return True if the environment variable is set and non-empty."""
    return bool(os.getenv(name, "").strip())


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
