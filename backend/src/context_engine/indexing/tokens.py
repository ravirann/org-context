"""Token estimation utility — use everywhere token counts are needed."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Rough token estimate: chars // 4, minimum 1."""
    return max(1, len(text) // 4)
