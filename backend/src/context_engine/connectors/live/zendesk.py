"""Live Zendesk connector: support tickets via the incremental ticket export API."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawAcl, RawItem
from context_engine.connectors.live.http import build_client, request_json
from context_engine.connectors.live.util import backfill_start, now_utc, parse_iso, resolve_acl
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Source

logger = get_logger(__name__)

_DELETED_STATUS = "deleted"


class ZendeskLiveConnector:
    """Fetch support tickets updated since the cursor via the incremental export API."""

    source_type: ClassVar[str] = "zendesk"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self, source: Source) -> httpx.AsyncClient:
        config = source.config
        return build_client(
            base_url=str(config["base_url"]).rstrip("/"),
            basic_auth=(f"{config['email']}/token", str(config["api_token"])),
            transport=self._transport,
        )

    async def fetch(self, source: Source) -> list[RawItem]:
        config = source.config
        base_url = str(config["base_url"]).rstrip("/")
        acl = resolve_acl(config)
        start_time = _start_time(source.sync_state, config)

        items: list[RawItem] = []
        async with self._client(source) as client:
            payload = await request_json(
                client,
                "GET",
                "/api/v2/incremental/tickets.json",
                params={"start_time": start_time},
            )
            tickets = payload.get("tickets", []) if isinstance(payload, dict) else []
            for ticket in tickets:
                item = self._ticket_item(ticket, base_url, acl)
                if item is not None:
                    items.append(item)

            # The incremental export is start-time-inclusive, so the next sync can
            # re-fetch the ticket the cursor landed on. That's fine: re-ingesting an
            # unchanged ticket is a no-op downstream (content-hash skip).
            end_time = payload.get("end_time") if isinstance(payload, dict) else None
            if end_time is not None:
                try:
                    source.sync_state["start_time_cursor"] = int(end_time)
                except (TypeError, ValueError):
                    logger.warning("zendesk_end_time_malformed", end_time=end_time)

        return items

    def _ticket_item(self, ticket: Any, base_url: str, acl: RawAcl) -> RawItem | None:
        if not isinstance(ticket, dict):
            logger.warning("zendesk_ticket_malformed", ticket=ticket)
            return None
        if ticket.get("status") == _DELETED_STATUS:
            return None

        try:
            ticket_id = str(ticket["id"])
            subject = str(ticket["subject"])
        except (KeyError, TypeError):
            logger.warning("zendesk_ticket_malformed", keys=list(ticket))
            return None

        description = str(ticket.get("description") or "")
        updated = parse_iso(str(ticket.get("updated_at", "")))
        status = ticket.get("status")
        priority = ticket.get("priority")

        return RawItem(
            external_id=ticket_id,
            doc_type="ticket",
            title=subject,
            content=description,
            url=f"{base_url}/agent/tickets/{ticket_id}",
            acl=acl,
            metadata={
                "status": str(status) if status else None,
                "priority": str(priority) if priority else None,
            },
            last_activity_at=updated or now_utc(),
        )


def _start_time(sync_state: dict[str, Any], config: dict[str, Any]) -> int:
    cursor = sync_state.get("start_time_cursor")
    if isinstance(cursor, int | float) and not isinstance(cursor, bool):
        return int(cursor)
    return int(backfill_start(config).timestamp())
