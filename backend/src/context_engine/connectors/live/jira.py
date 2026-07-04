"""Live Jira connector: issues updated since the cursor via the REST search API."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawItem
from context_engine.connectors.live.http import build_client, request_json
from context_engine.connectors.live.util import (
    cursor_since,
    now_utc,
    parse_iso,
    resolve_acl,
    to_iso,
)
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Source

logger = get_logger(__name__)

_PAGE_SIZE = 100


class JiraLiveConnector:
    """Fetch Jira issues (summary + description) updated since the last cursor."""

    source_type: ClassVar[str] = "jira"

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
        since = cursor_since(source.sync_state, "updated_cursor", config)
        acl = resolve_acl(config)
        jql = _build_jql(config.get("jql"), since)

        items: list[RawItem] = []
        max_updated = since
        async with self._client(source) as client:
            payload = await request_json(
                client,
                "GET",
                "/rest/api/3/search",
                params={"jql": jql, "maxResults": _PAGE_SIZE, "fields": "*all"},
            )
            issues = payload.get("issues", []) if isinstance(payload, dict) else []
            for issue in issues:
                built = self._issue_item(issue, acl)
                if built is None:
                    continue
                item, updated = built
                items.append(item)
                if updated is not None and updated > max_updated:
                    max_updated = updated

        source.sync_state["updated_cursor"] = to_iso(max_updated)
        return items

    def _issue_item(self, issue: dict[str, Any], acl: Any) -> tuple[RawItem, Any] | None:
        try:
            key = str(issue["key"])
            fields = issue["fields"]
        except (KeyError, TypeError):
            logger.warning("jira_issue_malformed", keys=list(issue))
            return None

        summary = str(fields.get("summary") or key)
        description = _extract_text(fields.get("description"))
        content = f"{summary}\n\n{description}" if description else summary
        updated = parse_iso(str(fields.get("updated", "")))

        item = RawItem(
            external_id=key,
            doc_type="ticket",
            title=summary,
            content=content,
            url=str(fields.get("_url") or f"{issue.get('self', '')}"),
            author_email=_reporter_email(fields),
            service=str((fields.get("project") or {}).get("key") or "") or None,
            acl=acl,
            metadata={
                "severity": str((fields.get("priority") or {}).get("name") or "").lower() or None,
                "status": str((fields.get("status") or {}).get("name") or "") or None,
            },
            last_activity_at=updated or now_utc(),
        )
        return item, updated


def _build_jql(base_jql: Any, since: Any) -> str:
    clause = f'updated >= "{since.strftime("%Y-%m-%d %H:%M")}"'
    if base_jql:
        return f"({base_jql}) AND {clause} ORDER BY updated ASC"
    return f"{clause} ORDER BY updated ASC"


def _reporter_email(fields: dict[str, Any]) -> str | None:
    reporter = fields.get("reporter") or {}
    email = reporter.get("emailAddress")
    return str(email) if email else None


def _extract_text(description: Any) -> str:
    """Flatten an Atlassian Document Format (ADF) body, or return plain strings."""
    if isinstance(description, str):
        return description.strip()
    if not isinstance(description, dict):
        return ""
    parts: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text" and node.get("text"):
                parts.append(str(node["text"]))
            for child in node.get("content", []) or []:
                _walk(child)

    _walk(description)
    return " ".join(parts).strip()
