"""Live Slack connector: conversations.history batched per channel-day."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawItem
from context_engine.connectors.live.http import ConnectorError, build_client, request_json
from context_engine.connectors.live.util import backfill_start, now_utc, resolve_acl
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Source

logger = get_logger(__name__)

_BASE_URL = "https://slack.com/api"
_PAGE_LIMIT = 200


class SlackLiveConnector:
    """Fetch channel history and batch messages into one RawItem per channel-day."""

    source_type: ClassVar[str] = "slack"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self, source: Source) -> httpx.AsyncClient:
        return build_client(
            base_url=_BASE_URL,
            bearer_token=str(source.config["token"]),
            transport=self._transport,
        )

    async def fetch(self, source: Source) -> list[RawItem]:
        config = source.config
        channels: list[str] = list(config.get("channels") or [])
        acl = resolve_acl(config)

        items: list[RawItem] = []
        async with self._client(source) as client:
            for channel in channels:
                cursor_key = f"channel_cursor:{channel}"
                since_ts = str(source.sync_state.get(cursor_key) or "")
                oldest = since_ts or _dt_to_ts(backfill_start(config))

                messages = await self._history(client, channel, oldest)
                if not messages:
                    continue
                items.extend(self._batch_by_day(channel, messages, acl))
                latest = max(str(m.get("ts", "0")) for m in messages)
                source.sync_state[cursor_key] = latest
        return items

    async def _history(
        self, client: httpx.AsyncClient, channel: str, oldest: str
    ) -> list[dict[str, Any]]:
        payload = await request_json(
            client,
            "GET",
            "/conversations.history",
            params={"channel": channel, "oldest": oldest, "limit": _PAGE_LIMIT},
        )
        if not isinstance(payload, dict) or not payload.get("ok"):
            error = payload.get("error") if isinstance(payload, dict) else "unknown"
            raise ConnectorError(f"slack conversations.history failed: {error}")
        return [m for m in payload.get("messages", []) if m.get("type") == "message"]

    def _batch_by_day(
        self, channel: str, messages: list[dict[str, Any]], acl: Any
    ) -> list[RawItem]:
        by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for msg in messages:
            ts = str(msg.get("ts") or "")
            if not ts:
                logger.warning("slack_message_missing_ts", channel=channel)
                continue
            day = _ts_to_day(ts)
            by_day[day].append(msg)

        items: list[RawItem] = []
        for day, day_messages in sorted(by_day.items()):
            ordered = sorted(day_messages, key=lambda m: str(m.get("ts", "0")))
            lines = [str(m.get("text") or "").strip() for m in ordered if m.get("text")]
            if not lines:
                continue
            first_ts = str(ordered[0]["ts"])
            items.append(
                RawItem(
                    external_id=f"slack-{channel}-{first_ts}",
                    doc_type="message",
                    title=f"{channel} — {day}",
                    content="\n".join(lines),
                    url="",
                    acl=acl,
                    metadata={"channel": channel, "day": day, "message_count": len(ordered)},
                    last_activity_at=_ts_to_dt(str(ordered[-1]["ts"])),
                )
            )
        return items


def _ts_to_dt(ts: str) -> datetime:
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (ValueError, OSError):
        return now_utc()


def _dt_to_ts(value: datetime) -> str:
    return f"{value.timestamp():.6f}"


def _ts_to_day(ts: str) -> str:
    return _ts_to_dt(ts).date().isoformat()
