"""Unit tests for the live Zendesk connector.

Imports the connector module directly (not via ``get_connector``, the live
registry, or ``live/__init__.py``) so this test is independent of registry
wiring. No real network: every request goes through an ``httpx.MockTransport``.
"""

from __future__ import annotations

import base64
from collections.abc import Callable

import httpx
import pytest

from context_engine.connectors.live.http import ConnectorAuthError
from context_engine.connectors.live.util import backfill_start
from context_engine.connectors.live.zendesk import ZendeskLiveConnector
from context_engine.storage import models as m

Handler = Callable[[httpx.Request], httpx.Response]


def _source(config: dict, sync_state: dict | None = None) -> m.Source:
    return m.Source(
        type=m.SourceType.zendesk,
        name="zendesk live",
        config=config,
        sync_state=sync_state or {},
    )


def _json_response(request: httpx.Request, payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=request)


def _zendesk_source(sync_state: dict | None = None) -> m.Source:
    return _source(
        {
            "mode": "live",
            "base_url": "https://acme.zendesk.com",
            "email": "bot@acme.dev",
            "api_token": "zd_secret",
        },
        sync_state,
    )


def _zendesk_handler(seen: dict) -> Handler:
    def handler(req: httpx.Request) -> httpx.Response:
        seen["params"] = dict(req.url.params)
        seen["auth_header"] = req.headers.get("Authorization")
        return _json_response(
            req,
            {
                "tickets": [
                    {
                        "id": 4501,
                        "subject": "Duplicate charge on invoice",
                        "description": "Customer charged twice for the same invoice.",
                        "status": "open",
                        "priority": "urgent",
                        "updated_at": "2026-07-01T08:00:00Z",
                    },
                    {
                        "id": 999,
                        "subject": "Deleted ticket",
                        "description": "Should never surface.",
                        "status": "deleted",
                        "priority": "low",
                        "updated_at": "2026-07-01T08:00:00Z",
                    },
                    {"priority": "low", "status": "open"},  # malformed: no id/subject
                ],
                "end_time": 1751362800,
                "end_of_stream": True,
            },
        )

    return handler


def _decoded_basic_auth(header: str | None) -> str:
    assert header is not None
    assert header.startswith("Basic ")
    return base64.b64decode(header.removeprefix("Basic ")).decode()


async def test_zendesk_fetch_maps_fields_and_auth() -> None:
    seen: dict = {}
    connector = ZendeskLiveConnector(transport=httpx.MockTransport(_zendesk_handler(seen)))
    source = _zendesk_source()

    items = await connector.fetch(source)

    assert len(items) == 1  # deleted + malformed both skipped
    item = items[0]
    assert item.external_id == "4501"
    assert item.doc_type == "ticket"
    assert item.title == "Duplicate charge on invoice"
    assert item.content == "Customer charged twice for the same invoice."
    assert item.url == "https://acme.zendesk.com/agent/tickets/4501"
    assert item.metadata["status"] == "open"
    assert item.metadata["priority"] == "urgent"
    assert item.acl.public is True

    # Zendesk API-token auth: username carries a literal "/token" suffix.
    decoded = _decoded_basic_auth(seen["auth_header"])
    assert decoded.startswith("bot@acme.dev/token:")
    assert decoded.endswith("zd_secret")

    assert "start_time" in seen["params"]


async def test_zendesk_deleted_ticket_skipped() -> None:
    seen: dict = {}
    connector = ZendeskLiveConnector(transport=httpx.MockTransport(_zendesk_handler(seen)))
    items = await connector.fetch(_zendesk_source())
    assert not any(i.external_id == "999" for i in items)


async def test_zendesk_malformed_ticket_skipped() -> None:
    seen: dict = {}
    connector = ZendeskLiveConnector(transport=httpx.MockTransport(_zendesk_handler(seen)))
    items = await connector.fetch(_zendesk_source())
    assert all(i.external_id != "" for i in items)
    assert len(items) == 1


async def test_zendesk_first_sync_uses_backfill_window() -> None:
    seen: dict = {}
    connector = ZendeskLiveConnector(transport=httpx.MockTransport(_zendesk_handler(seen)))
    source = _zendesk_source()
    expected = int(backfill_start(source.config).timestamp())

    await connector.fetch(source)

    actual = int(seen["params"]["start_time"])
    assert abs(actual - expected) <= 5  # tolerate real-clock drift between the two calls


async def test_zendesk_cursor_set_from_end_time_and_reused_on_second_fetch() -> None:
    seen: dict = {}
    connector = ZendeskLiveConnector(transport=httpx.MockTransport(_zendesk_handler(seen)))
    source = _zendesk_source()

    await connector.fetch(source)
    assert source.sync_state["start_time_cursor"] == 1751362800

    await connector.fetch(source)
    assert seen["params"]["start_time"] == "1751362800"


async def test_zendesk_restrict_to_team_acl() -> None:
    seen: dict = {}
    connector = ZendeskLiveConnector(transport=httpx.MockTransport(_zendesk_handler(seen)))
    source = _zendesk_source()
    source.config["restrict_to_team"] = "Support"

    items = await connector.fetch(source)

    assert items[0].acl.public is False
    assert items[0].acl.team_names == ["Support"]


async def test_zendesk_401_raises_auth_error() -> None:
    connector = ZendeskLiveConnector(
        transport=httpx.MockTransport(lambda req: _json_response(req, {}, status=401))
    )
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_zendesk_source())
