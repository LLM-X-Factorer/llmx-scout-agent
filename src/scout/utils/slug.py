"""Filename slug generation."""

from __future__ import annotations

import re
import unicodedata

_SAFE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 60) -> str:
    """Lowercase ASCII slug, hyphen-separated. Falls back to 'untitled' if empty."""
    norm = unicodedata.normalize("NFKD", text)
    ascii_text = norm.encode("ascii", "ignore").decode("ascii").lower()
    s = _SAFE.sub("-", ascii_text).strip("-")
    if not s:
        return "untitled"
    return s[:max_len].rstrip("-")
