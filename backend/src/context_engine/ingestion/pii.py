"""Regex-based PII redaction applied by the ingestion pipeline."""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

DEFAULT_PII_PATTERNS: list[str] = [
    # Email addresses.
    r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
    # Phone-like numbers: optional country code, 3-3-4 groupings with common separators.
    r"(?<!\w)(?:\+?\d{1,2}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b",
    # AWS access key ids.
    r"\bAKIA[0-9A-Z]{16}\b",
]
"""Fallback patterns when the ``pii_redaction`` setting does not provide any."""


def redact(text: str, patterns: list[str]) -> tuple[str, int]:
    """Replace every pattern match in ``text`` with ``[REDACTED]``.

    Returns the redacted text and the total number of replacements made.
    """
    total = 0
    for pattern in patterns:
        text, hits = re.subn(pattern, REDACTED, text)
        total += hits
    return text, total
