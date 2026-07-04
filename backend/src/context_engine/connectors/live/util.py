"""Shared helpers for live connectors: cursors, backfill windows, ACL, text."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from context_engine.connectors.base import RawAcl

DEFAULT_BACKFILL_DAYS = 90
"""First-sync lookback window when no cursor and no ``backfill_days`` config."""


def now_utc() -> datetime:
    """Current time as a timezone-aware UTC datetime (isolated for testability)."""
    return datetime.now(UTC)


def backfill_start(config: dict[str, Any], reference: datetime | None = None) -> datetime:
    """Return the first-sync window start (``backfill_days`` before now)."""
    days = config.get("backfill_days")
    window = int(days) if isinstance(days, int | float) and not isinstance(days, bool) else None
    window = window if window and window > 0 else DEFAULT_BACKFILL_DAYS
    ref = reference if reference is not None else now_utc()
    return ref - timedelta(days=window)


def cursor_since(sync_state: dict[str, Any], key: str, config: dict[str, Any]) -> datetime:
    """Resolve the ``since`` timestamp for a stream: stored cursor or backfill start."""
    raw = sync_state.get(key)
    if isinstance(raw, str) and raw:
        parsed = parse_iso(raw)
        if parsed is not None:
            return parsed
    return backfill_start(config)


def parse_iso(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, normalizing ``Z`` and naive values to UTC."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def to_iso(value: datetime) -> str:
    """Serialize a datetime to an ISO-8601 UTC string for cursor storage."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def resolve_acl(config: dict[str, Any], *, private: bool = False) -> RawAcl:
    """Map connector config + item visibility to a :class:`RawAcl`.

    GitHub private repos and any source with ``restrict_to_team`` become
    team-restricted (via ``team_name``/``restrict_to_team``); everything else is
    public.
    """
    team = config.get("team_name") or config.get("restrict_to_team")
    if (private or config.get("restrict_to_team")) and team:
        return RawAcl(public=False, team_names=[str(team)])
    return RawAcl(public=True)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def html_to_text(html: str) -> str:
    """Strip Confluence storage-format HTML tags to readable plain text."""
    # Convert common block boundaries to newlines before stripping tags so the
    # resulting text keeps paragraph structure.
    text = re.sub(r"(?i)</(p|div|li|h[1-6]|tr|br\s*/?)>", "\n", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = _TAG_RE.sub("", text)
    text = _unescape(text)
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _unescape(text: str) -> str:
    for entity, char in (
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&nbsp;", " "),
    ):
        text = text.replace(entity, char)
    return text
