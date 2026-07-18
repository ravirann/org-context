"""Unit tests for the live Linear connector.

No real network: every request goes through an ``httpx.MockTransport`` whose
handler returns canned Linear GraphQL payloads and can assert on the outgoing
request body (to verify the cursor/team filters and cursor advance).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import httpx
import pytest

from context_engine.connectors.live.http import ConnectorAuthError, ConnectorError
from context_engine.connectors.live.linear import LinearLiveConnector
from context_engine.connectors.live.util import now_utc, parse_iso
from context_engine.storage import models as m

Handler = Callable[[httpx.Request], httpx.Response]

_GOOD_NODE: dict[str, Any] = {
    "id": "abc123",
    "identifier": "ENG-142",
    "title": "Webhook retries duplicate charges",
    "description": "Root cause is the webhook dispatcher retrying without an idempotency key.",
    "url": "https://linear.app/acme/issue/ENG-142",
    "createdAt": "2026-06-01T00:00:00.000Z",
    "updatedAt": "2026-07-01T08:00:00.000Z",
    "state": {"name": "In Progress"},
    "assignee": {"email": "priya@demo.dev"},
    "team": {"key": "ENG", "name": "Payments"},
}


def _source(config: dict[str, Any], sync_state: dict[str, Any] | None = None) -> m.Source:
    return m.Source(
        type=m.SourceType.linear,
        name="linear live",
        config=config,
        sync_state=sync_state or {},
    )


def _config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {"mode": "live", "api_key": "lin_api_secret"}
    config.update(overrides)
    return config


def _linear_handler(
    seen: dict[str, Any],
    *,
    nodes: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    status: int = 200,
) -> Handler:
    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers.get("authorization")
        if errors is not None:
            return httpx.Response(status, json={"errors": errors}, request=req)
        payload = {"data": {"issues": {"nodes": nodes or []}}}
        return httpx.Response(status, json=payload, request=req)

    return handler


async def test_linear_fetch_maps_fields_and_sends_filters() -> None:
    seen: dict[str, Any] = {}
    connector = LinearLiveConnector(
        transport=httpx.MockTransport(_linear_handler(seen, nodes=[_GOOD_NODE]))
    )
    source = _source(
        _config(team_keys=["ENG"]),
        {"updated_cursor": "2026-06-15T00:00:00+00:00"},
    )

    items = await connector.fetch(source)
    assert len(items) == 1
    item = items[0]
    assert item.external_id == "abc123"
    assert item.doc_type == "ticket"
    assert item.title == "ENG-142: Webhook retries duplicate charges"
    assert "idempotency key" in item.content
    assert item.url == "https://linear.app/acme/issue/ENG-142"
    assert item.author_email == "priya@demo.dev"
    assert item.team_name == "Payments"
    assert item.metadata["identifier"] == "ENG-142"
    assert item.metadata["state"] == "In Progress"
    assert item.acl.public is True
    assert source.sync_state["updated_cursor"] == "2026-07-01T08:00:00+00:00"

    body = seen["body"]
    assert body["variables"]["filter"]["updatedAt"]["gt"] == "2026-06-15T00:00:00+00:00"
    assert body["variables"]["filter"]["team"]["key"]["in"] == ["ENG"]
    assert body["variables"]["first"] == 100


async def test_linear_auth_header_is_raw_api_key_no_bearer_prefix() -> None:
    seen: dict[str, Any] = {}
    connector = LinearLiveConnector(transport=httpx.MockTransport(_linear_handler(seen, nodes=[])))
    await connector.fetch(_source(_config(api_key="lin_api_secret")))
    assert seen["auth"] == "lin_api_secret"


async def test_linear_restrict_to_team_acl() -> None:
    seen: dict[str, Any] = {}
    connector = LinearLiveConnector(
        transport=httpx.MockTransport(_linear_handler(seen, nodes=[_GOOD_NODE]))
    )
    source = _source(_config(restrict_to_team="Payments"))
    items = await connector.fetch(source)
    assert items[0].acl.public is False
    assert items[0].acl.team_names == ["Payments"]


async def test_linear_second_fetch_uses_advanced_cursor() -> None:
    seen: dict[str, Any] = {}
    connector = LinearLiveConnector(
        transport=httpx.MockTransport(_linear_handler(seen, nodes=[_GOOD_NODE]))
    )
    source = _source(_config())

    await connector.fetch(source)
    assert source.sync_state["updated_cursor"] == "2026-07-01T08:00:00+00:00"

    await connector.fetch(source)
    body = seen["body"]
    assert body["variables"]["filter"]["updatedAt"]["gt"] == "2026-07-01T08:00:00+00:00"


async def test_linear_first_sync_uses_backfill_window() -> None:
    seen: dict[str, Any] = {}
    connector = LinearLiveConnector(transport=httpx.MockTransport(_linear_handler(seen, nodes=[])))
    source = _source(_config())

    before = now_utc()
    await connector.fetch(source)
    after = now_utc()

    since = parse_iso(seen["body"]["variables"]["filter"]["updatedAt"]["gt"])
    assert since is not None
    assert (before - timedelta(days=90)) <= since <= (after - timedelta(days=90))


async def test_linear_401_raises_auth_error() -> None:
    connector = LinearLiveConnector(
        transport=httpx.MockTransport(lambda req: httpx.Response(401, json={}, request=req))
    )
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_source(_config()))


async def test_linear_graphql_errors_payload_raises_connector_error() -> None:
    seen: dict[str, Any] = {}
    connector = LinearLiveConnector(
        transport=httpx.MockTransport(
            _linear_handler(seen, errors=[{"message": "Argument Validation Error"}])
        )
    )
    with pytest.raises(ConnectorError):
        await connector.fetch(_source(_config()))


async def test_linear_malformed_node_skipped() -> None:
    seen: dict[str, Any] = {}
    malformed = {"title": "no id or identifier field"}
    connector = LinearLiveConnector(
        transport=httpx.MockTransport(_linear_handler(seen, nodes=[malformed, _GOOD_NODE]))
    )
    items = await connector.fetch(_source(_config()))
    assert len(items) == 1
    assert items[0].external_id == "abc123"
