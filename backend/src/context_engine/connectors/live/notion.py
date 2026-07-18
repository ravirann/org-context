"""Live Notion connector: pages changed since the cursor via the search API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawAcl, RawItem
from context_engine.connectors.live.http import build_client, request_json
from context_engine.connectors.live.util import cursor_since, parse_iso, resolve_acl, to_iso
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Source

logger = get_logger(__name__)

DEFAULT_API_URL = "https://api.notion.com"
_NOTION_VERSION = "2022-06-28"
_SEARCH_PAGE_SIZE = 100
_BLOCK_PAGE_SIZE = 100
_MAX_CONTENT_FETCHES = 50
"""Per-sync cap on the (expensive) block-children fetch; beyond this pages fall
back to title-only content without attempting the request."""

_TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "toggle",
    "quote",
    "callout",
    "code",
}


class NotionLiveConnector:
    """Fetch Notion pages (title + block text) edited since the last cursor."""

    source_type: ClassVar[str] = "notion"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self, source: Source) -> httpx.AsyncClient:
        config = source.config
        return build_client(
            base_url=str(config.get("api_url") or DEFAULT_API_URL).rstrip("/"),
            bearer_token=str(config["token"]),
            transport=self._transport,
            headers={"Notion-Version": _NOTION_VERSION},
        )

    async def fetch(self, source: Source) -> list[RawItem]:
        config = source.config
        since = cursor_since(source.sync_state, "last_edited_cursor", config)
        acl = resolve_acl(config)

        body: dict[str, Any] = {
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "page_size": _SEARCH_PAGE_SIZE,
            "filter": {"value": "page", "property": "object"},
        }
        query = config.get("query")
        if query:
            body["query"] = str(query)

        items: list[RawItem] = []
        max_edited = since
        content_fetches = 0
        async with self._client(source) as client:
            payload = await request_json(client, "POST", "/v1/search", json=body)
            results = payload.get("results", []) if isinstance(payload, dict) else []

            for page in results:
                if not isinstance(page, dict):
                    logger.warning("notion_page_malformed", page=page)
                    continue
                last_edited = parse_iso(str(page.get("last_edited_time", "")))
                if last_edited is None:
                    logger.warning("notion_page_malformed", keys=list(page))
                    continue
                if last_edited <= since:
                    # Results are sorted descending by last_edited_time: everything
                    # from here on is at least as old, so stop scanning early.
                    break

                fetch_children = content_fetches < _MAX_CONTENT_FETCHES
                item = await self._page_item(
                    client, page, acl, last_edited, fetch_children=fetch_children
                )
                if item is None:
                    continue
                if fetch_children:
                    content_fetches += 1
                items.append(item)
                if last_edited > max_edited:
                    max_edited = last_edited

        source.sync_state["last_edited_cursor"] = to_iso(max_edited)
        return items

    async def _page_item(
        self,
        client: httpx.AsyncClient,
        page: dict[str, Any],
        acl: RawAcl,
        last_edited: datetime,
        *,
        fetch_children: bool,
    ) -> RawItem | None:
        try:
            page_id = str(page["id"])
            url = str(page["url"])
        except (KeyError, TypeError):
            logger.warning("notion_page_malformed", keys=list(page))
            return None

        properties = page.get("properties")
        title = _extract_title(properties if isinstance(properties, dict) else {})

        body_text = ""
        if fetch_children:
            body_text = await self._fetch_children_text(client, page_id)
        content = body_text or title
        if not title and not content:
            logger.warning("notion_page_malformed", keys=list(page))
            return None

        return RawItem(
            external_id=page_id,
            doc_type="doc",
            title=title or page_id,
            content=content or title or page_id,
            url=url,
            acl=acl,
            metadata={"created_time": page.get("created_time")},
            last_activity_at=last_edited,
        )

    async def _fetch_children_text(self, client: httpx.AsyncClient, page_id: str) -> str:
        try:
            payload = await request_json(
                client,
                "GET",
                f"/v1/blocks/{page_id}/children",
                params={"page_size": _BLOCK_PAGE_SIZE},
            )
        except Exception:  # noqa: BLE001 — children fetch is best-effort
            logger.warning("notion_children_fetch_failed", page_id=page_id)
            return ""
        blocks = payload.get("results", []) if isinstance(payload, dict) else []
        lines = [
            text for block in blocks if isinstance(block, dict) and (text := _block_text(block))
        ]
        return "\n".join(lines)


def _extract_title(properties: dict[str, Any]) -> str:
    for prop in properties.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            title_list = prop.get("title")
            if isinstance(title_list, list):
                return "".join(
                    str(t.get("plain_text", "")) for t in title_list if isinstance(t, dict)
                ).strip()
    return ""


def _block_text(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    if block_type not in _TEXT_BLOCK_TYPES:
        return ""
    payload = block.get(block_type)
    if not isinstance(payload, dict):
        return ""
    rich_text = payload.get("rich_text")
    if not isinstance(rich_text, list):
        return ""
    return "".join(
        str(rt.get("plain_text", ""))
        for rt in rich_text
        if isinstance(rt, dict) and rt.get("plain_text")
    )
