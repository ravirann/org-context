"""Unit tests for the live Notion connector.

Imports the connector module directly (not via ``get_connector``, the live
registry, or ``live/__init__.py``) so this test is independent of registry
wiring. No real network: every request goes through an ``httpx.MockTransport``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import httpx
import pytest

from context_engine.connectors.live.http import ConnectorAuthError
from context_engine.connectors.live.notion import NotionLiveConnector
from context_engine.connectors.live.util import now_utc, parse_iso
from context_engine.storage import models as m

Handler = Callable[[httpx.Request], httpx.Response]


def _source(config: dict[str, Any], sync_state: dict[str, Any] | None = None) -> m.Source:
    return m.Source(
        type=m.SourceType.notion,
        name="notion live",
        config=config,
        sync_state=sync_state or {},
    )


def _config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {"mode": "live", "token": "secret_notion_token"}
    config.update(overrides)
    return config


def _json_response(request: httpx.Request, payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=request)


def _page(
    page_id: str,
    *,
    title: str,
    last_edited: str,
    created: str = "2026-01-01T00:00:00.000Z",
) -> dict[str, Any]:
    return {
        "id": page_id,
        "url": f"https://www.notion.so/{page_id}",
        "created_time": created,
        "last_edited_time": last_edited,
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": title}]},
            "Status": {"type": "select", "select": {"name": "Done"}},
        },
    }


def _blocks(*texts: str) -> dict[str, Any]:
    return {
        "results": [
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": t}]}} for t in texts
        ]
    }


def _notion_handler(
    seen: dict[str, Any],
    pages: list[dict[str, Any]],
    blocks: dict[str, dict[str, Any]] | None = None,
    *,
    block_status: int = 200,
    search_status: int = 200,
) -> Handler:
    blocks = blocks or {}

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/v1/search":
            seen["search_body"] = json.loads(req.content)
            seen["auth_header"] = req.headers.get("authorization")
            seen["notion_version"] = req.headers.get("notion-version")
            return _json_response(req, {"results": pages}, status=search_status)
        if path.startswith("/v1/blocks/"):
            page_id = path.removeprefix("/v1/blocks/").removesuffix("/children")
            seen.setdefault("blocks_requested", []).append(page_id)
            if block_status != 200:
                return _json_response(req, {}, status=block_status)
            return _json_response(req, blocks.get(page_id, {"results": []}))
        return _json_response(req, {}, status=404)

    return handler


# --------------------------------------------------------------------------- #
# Field mapping                                                               #
# --------------------------------------------------------------------------- #


async def test_notion_fetch_maps_fields_and_auth() -> None:
    seen: dict[str, Any] = {}
    page = _page("page-aaa", title="Payments Retry Notes", last_edited="2026-07-10T10:00:00.000Z")
    blocks = {"page-aaa": _blocks("Ship jittered backoff.", "Rollout behind enable_retry_v2.")}
    connector = NotionLiveConnector(
        transport=httpx.MockTransport(_notion_handler(seen, [page], blocks))
    )
    source = _source(_config())

    items = await connector.fetch(source)
    assert len(items) == 1
    item = items[0]
    assert item.external_id == "page-aaa"
    assert item.doc_type == "doc"
    assert item.title == "Payments Retry Notes"
    assert "Ship jittered backoff." in item.content
    assert "Rollout behind enable_retry_v2." in item.content
    assert item.url == "https://www.notion.so/page-aaa"
    assert item.metadata["created_time"] == "2026-01-01T00:00:00.000Z"
    assert item.acl.public is True
    assert item.last_activity_at.isoformat() == "2026-07-10T10:00:00+00:00"
    assert source.sync_state["last_edited_cursor"] == "2026-07-10T10:00:00+00:00"

    assert seen["auth_header"] == "Bearer secret_notion_token"
    assert seen["notion_version"] == "2022-06-28"
    body = seen["search_body"]
    assert body["sort"] == {"direction": "descending", "timestamp": "last_edited_time"}
    assert body["page_size"] == 100
    assert body["filter"] == {"value": "page", "property": "object"}
    assert "query" not in body


async def test_notion_query_filter_sent_when_configured() -> None:
    seen: dict[str, Any] = {}
    connector = NotionLiveConnector(transport=httpx.MockTransport(_notion_handler(seen, [])))
    await connector.fetch(_source(_config(query="roadmap")))
    assert seen["search_body"]["query"] == "roadmap"


async def test_notion_restrict_to_team_acl() -> None:
    seen: dict[str, Any] = {}
    page = _page("page-aaa", title="Spec", last_edited="2026-07-10T10:00:00.000Z")
    connector = NotionLiveConnector(transport=httpx.MockTransport(_notion_handler(seen, [page])))
    source = _source(_config(restrict_to_team="Payments"))

    items = await connector.fetch(source)
    assert items[0].acl.public is False
    assert items[0].acl.team_names == ["Payments"]


# --------------------------------------------------------------------------- #
# Cursor advance + filtering                                                  #
# --------------------------------------------------------------------------- #


async def test_notion_cursor_written_and_respected_on_second_fetch() -> None:
    seen: dict[str, Any] = {}
    newer = _page("page-new", title="New spec", last_edited="2026-07-10T10:00:00.000Z")
    older = _page("page-old", title="Old spec", last_edited="2026-07-01T09:00:00.000Z")
    connector = NotionLiveConnector(
        transport=httpx.MockTransport(_notion_handler(seen, [newer, older]))
    )
    source = _source(_config(), {"last_edited_cursor": "2026-07-05T00:00:00+00:00"})

    items = await connector.fetch(source)

    assert [i.external_id for i in items] == ["page-new"]
    assert source.sync_state["last_edited_cursor"] == "2026-07-10T10:00:00+00:00"
    # the filtered-out older page must never trigger a children fetch
    assert seen.get("blocks_requested", []) == ["page-new"]


# --------------------------------------------------------------------------- #
# First-sync backfill window                                                  #
# --------------------------------------------------------------------------- #


async def test_notion_first_sync_uses_backfill_window() -> None:
    seen: dict[str, Any] = {}
    in_window = _page(
        "page-in",
        title="Within window",
        last_edited=(now_utc() - timedelta(days=85)).isoformat(),
    )
    too_old = _page(
        "page-old",
        title="Too old",
        last_edited=(now_utc() - timedelta(days=95)).isoformat(),
    )
    connector = NotionLiveConnector(
        transport=httpx.MockTransport(_notion_handler(seen, [in_window, too_old]))
    )
    source = _source(_config())

    items = await connector.fetch(source)

    assert [i.external_id for i in items] == ["page-in"]
    cursor = parse_iso(source.sync_state["last_edited_cursor"])
    assert cursor is not None
    assert cursor > now_utc() - timedelta(days=90)


# --------------------------------------------------------------------------- #
# Error handling / per-item isolation                                         #
# --------------------------------------------------------------------------- #


async def test_notion_401_raises_auth_error() -> None:
    connector = NotionLiveConnector(
        transport=httpx.MockTransport(lambda req: _json_response(req, {}, status=401))
    )
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_source(_config()))


async def test_notion_malformed_page_skipped() -> None:
    seen: dict[str, Any] = {}
    malformed = {
        # missing "id"
        "url": "https://www.notion.so/no-id",
        "last_edited_time": "2026-07-10T10:00:00.000Z",
        "properties": {},
    }
    good = _page("page-good", title="Good page", last_edited="2026-07-09T10:00:00.000Z")
    connector = NotionLiveConnector(
        transport=httpx.MockTransport(_notion_handler(seen, [malformed, good]))
    )

    items = await connector.fetch(_source(_config()))

    assert len(items) == 1
    assert items[0].external_id == "page-good"


async def test_notion_children_fetch_failure_falls_back_to_title_only() -> None:
    seen: dict[str, Any] = {}
    page = _page("page-fail", title="Fallback Title", last_edited="2026-07-10T10:00:00.000Z")
    # 404 is a non-retryable failure status, so this raises immediately (no sleeps).
    connector = NotionLiveConnector(
        transport=httpx.MockTransport(_notion_handler(seen, [page], block_status=404))
    )

    items = await connector.fetch(_source(_config()))

    assert len(items) == 1
    assert items[0].title == "Fallback Title"
    assert items[0].content == "Fallback Title"
