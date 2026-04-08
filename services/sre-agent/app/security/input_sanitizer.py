"""Layer 1 — strip control chars, zero-width Unicode, enforce length limit."""
from __future__ import annotations

import unicodedata

MAX_LEN = 8000
ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}


def sanitize(text: str) -> str:
    if not text:
        return ""
    text = "".join(c for c in text if c not in ZERO_WIDTH)
    text = "".join(c for c in text if unicodedata.category(c)[0] != "C" or c in "\n\t ")
    return text[:MAX_LEN]
