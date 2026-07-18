"""Live Linear connector: issues updated since the cursor via the GraphQL API."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawItem
from context_engine.connectors.live.http import ConnectorError, build_client, request_json
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

DEFAULT_API_URL = "https://api.linear.app/graphql"
_PAGE_SIZE = 100

_QUERY = """
query Issues($filter: IssueFilter, $first: Int) {
  issues(filter: $filter, first: $first, orderBy: updatedAt) {
    nodes {
      id
      identifier
      title
      description
      url
      createdAt
      updatedAt
      state { name }
      assignee { email }
      team { key name }
    }
  }
}
"""


class LinearLiveConnector:
    """Fetch Linear issues (title + description) updated since the last cursor."""

    source_type: ClassVar[str] = "linear"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self, source: Source) -> httpx.AsyncClient:
        config = source.config
        return build_client(
            headers={
                "Authorization": str(config["api_key"]),
                "Content-Type": "application/json",
            },
            transport=self._transport,
        )

    async def fetch(self, source: Source) -> list[RawItem]:
        config = source.config
        api_url = str(config.get("api_url") or DEFAULT_API_URL)
        since = cursor_since(source.sync_state, "updated_cursor", config)
        acl = resolve_acl(config)
        variables = _build_variables(config.get("team_keys"), since)

        items: list[RawItem] = []
        max_updated = since
        async with self._client(source) as client:
            payload = await request_json(
                client,
                "POST",
                api_url,
                json={"query": _QUERY, "variables": variables},
            )
            if isinstance(payload, dict) and payload.get("errors"):
                raise ConnectorError(f"linear graphql request failed: {payload['errors']}")
            nodes = _extract_nodes(payload)
            for node in nodes:
                built = self._issue_item(node, acl)
                if built is None:
                    continue
                item, updated = built
                items.append(item)
                if updated is not None and updated > max_updated:
                    max_updated = updated

        source.sync_state["updated_cursor"] = to_iso(max_updated)
        return items

    def _issue_item(self, node: dict[str, Any], acl: Any) -> tuple[RawItem, Any] | None:
        try:
            node_id = str(node["id"])
            identifier = str(node["identifier"])
            title = str(node["title"])
        except (KeyError, TypeError):
            keys = list(node) if isinstance(node, dict) else []
            logger.warning("linear_issue_malformed", keys=keys)
            return None

        description = str(node.get("description") or "")
        updated = parse_iso(str(node.get("updatedAt", "")))
        state_raw = node.get("state")
        state: dict[str, Any] = state_raw if isinstance(state_raw, dict) else {}
        assignee_raw = node.get("assignee")
        assignee: dict[str, Any] = assignee_raw if isinstance(assignee_raw, dict) else {}
        team_raw = node.get("team")
        team: dict[str, Any] = team_raw if isinstance(team_raw, dict) else {}

        item = RawItem(
            external_id=node_id,
            doc_type="ticket",
            title=f"{identifier}: {title}",
            content=description,
            url=str(node.get("url") or ""),
            author_email=assignee.get("email") or None,
            team_name=team.get("name") or None,
            acl=acl,
            metadata={
                "state": state.get("name") or None,
                "identifier": identifier,
            },
            last_activity_at=updated or now_utc(),
        )
        return item, updated


def _build_variables(team_keys: Any, since: Any) -> dict[str, Any]:
    filter_: dict[str, Any] = {"updatedAt": {"gt": to_iso(since)}}
    keys = [str(k) for k in team_keys] if isinstance(team_keys, list | tuple) and team_keys else []
    if keys:
        filter_["team"] = {"key": {"in": keys}}
    return {"filter": filter_, "first": _PAGE_SIZE}


def _extract_nodes(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    issues = data.get("issues")
    if not isinstance(issues, dict):
        return []
    nodes = issues.get("nodes")
    return nodes if isinstance(nodes, list) else []
