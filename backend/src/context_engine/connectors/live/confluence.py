"""Live Confluence connector: pages changed since the cursor via CQL search."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawItem
from context_engine.connectors.live.http import build_client, request_json
from context_engine.connectors.live.util import (
    cursor_since,
    html_to_text,
    now_utc,
    parse_iso,
    resolve_acl,
    to_iso,
)
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Source

logger = get_logger(__name__)

_PAGE_LIMIT = 100


class ConfluenceLiveConnector:
    """Fetch Confluence pages (storage HTML → text) modified since the cursor."""

    source_type: ClassVar[str] = "confluence"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self, source: Source) -> httpx.AsyncClient:
        config = source.config
        return build_client(
            base_url=str(config["base_url"]).rstrip("/"),
            basic_auth=(str(config["email"]), str(config["api_token"])),
            transport=self._transport,
        )

    async def fetch(self, source: Source) -> list[RawItem]:
        config = source.config
        since = cursor_since(source.sync_state, "lastmodified_cursor", config)
        acl = resolve_acl(config)
        cql = _build_cql(config.get("space_keys") or [], since)

        items: list[RawItem] = []
        max_modified = since
        async with self._client(source) as client:
            payload = await request_json(
                client,
                "GET",
                "/rest/api/content/search",
                params={
                    "cql": cql,
                    "limit": _PAGE_LIMIT,
                    "expand": "body.storage,version,space",
                },
            )
            results = payload.get("results", []) if isinstance(payload, dict) else []
            base = (
                str(payload.get("_links", {}).get("base", "")) if isinstance(payload, dict) else ""
            )
            for page in results:
                built = self._page_item(page, acl, base)
                if built is None:
                    continue
                item, modified = built
                items.append(item)
                if modified is not None and modified > max_modified:
                    max_modified = modified

        source.sync_state["lastmodified_cursor"] = to_iso(max_modified)
        return items

    def _page_item(self, page: dict[str, Any], acl: Any, base: str) -> tuple[RawItem, Any] | None:
        try:
            page_id = str(page["id"])
            title = str(page["title"])
        except (KeyError, TypeError):
            logger.warning("confluence_page_malformed", keys=list(page))
            return None

        storage = ((page.get("body") or {}).get("storage") or {}).get("value") or ""
        content = html_to_text(str(storage)) or title
        version = page.get("version") or {}
        modified = parse_iso(str(version.get("when", "")))
        webui = str((page.get("_links") or {}).get("webui") or "")

        item = RawItem(
            external_id=f"conf-{page_id}",
            doc_type="doc",
            title=title,
            content=content,
            url=f"{base}{webui}" if webui else "",
            acl=acl,
            metadata={"space": str((page.get("space") or {}).get("key") or "") or None},
            last_activity_at=modified or now_utc(),
        )
        return item, modified


def _build_cql(space_keys: list[str], since: Any) -> str:
    clause = f'lastmodified >= "{since.strftime("%Y-%m-%d %H:%M")}"'
    parts = ["type=page", clause]
    if space_keys:
        keys = ",".join(f'"{k}"' for k in space_keys)
        parts.append(f"space in ({keys})")
    return " AND ".join(parts) + " ORDER BY lastmodified ASC"
