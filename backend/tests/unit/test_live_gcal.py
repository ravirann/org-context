"""Unit tests for the live Google Calendar connector.

Imports the connector module directly (not via ``get_connector``, the live
registry, or ``live/__init__.py``) so this test is independent of registry
wiring. No real network: both the JWT-bearer token exchange and the per-calendar
``events`` requests go through a single ``httpx.MockTransport`` whose handler
routes by URL, reusing the throwaway-RSA-key service-account fixture pattern
from ``test_google_auth.py``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from context_engine.connectors.live.gcal import GCalLiveConnector
from context_engine.connectors.live.http import ConnectorAuthError
from context_engine.connectors.live.util import now_utc, parse_iso
from context_engine.storage import models as m

Handler = Callable[[httpx.Request], httpx.Response]

TOKEN_URI = "https://oauth2.example.test/token"
CLIENT_EMAIL = "gcal-svc@proj.iam.gserviceaccount.com"


def _rsa_private_pem() -> str:
    """Generate a throwaway 2048-bit RSA key so the JWT-bearer assertion can sign."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


_PRIVATE_PEM = _rsa_private_pem()


def _sa_json() -> str:
    return json.dumps(
        {
            "type": "service_account",
            "client_email": CLIENT_EMAIL,
            "private_key": _PRIVATE_PEM,
            "token_uri": TOKEN_URI,
        }
    )


def _source(config: dict[str, Any], sync_state: dict[str, Any] | None = None) -> m.Source:
    return m.Source(
        type=m.SourceType.gcal,
        name="gcal live",
        config=config,
        sync_state=sync_state or {},
    )


def _config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "mode": "live",
        "service_account_json": _sa_json(),
        "subject": "alix@acme.dev",
        "api_url": "https://gcal.example.test",
    }
    config.update(overrides)
    return config


def _event(
    event_id: str,
    *,
    summary: str = "Sprint planning",
    updated: str = "2026-07-01T08:00:00.000Z",
    start: dict[str, Any] | None = None,
    end: dict[str, Any] | None = None,
    status: str | None = None,
    description: str | None = "Plan the sprint.",
    organizer: dict[str, Any] | None = None,
    attendees: list[dict[str, Any]] | None = None,
    html_link: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "id": event_id,
        "summary": summary,
        "updated": updated,
        "start": start if start is not None else {"dateTime": "2026-07-01T10:00:00-07:00"},
        "end": end if end is not None else {"dateTime": "2026-07-01T10:30:00-07:00"},
    }
    if status is not None:
        event["status"] = status
    if description is not None:
        event["description"] = description
    event["organizer"] = organizer if organizer is not None else {"email": "priya@demo.dev"}
    event["attendees"] = (
        attendees
        if attendees is not None
        else [
            {"email": "priya@demo.dev", "responseStatus": "accepted"},
            {"email": "nina@demo.dev", "responseStatus": "needsAction"},
        ]
    )
    if html_link is not None:
        event["htmlLink"] = html_link
    return event


def _handler(
    seen: dict[str, Any],
    events_by_calendar: dict[str, list[dict[str, Any]]],
    *,
    token_status: int = 200,
    calendar_statuses: dict[str, int] | None = None,
) -> Handler:
    calendar_statuses = calendar_statuses or {}
    counter = {"token_calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/token":
            counter["token_calls"] += 1
            seen["token_calls"] = counter["token_calls"]
            if token_status != 200:
                return httpx.Response(
                    token_status,
                    json={"error": "invalid_grant", "error_description": "bad key"},
                    request=req,
                )
            return httpx.Response(
                200, json={"access_token": "ya29.gcal-token", "expires_in": 3600}, request=req
            )

        path = req.url.path
        prefix = "/calendar/v3/calendars/"
        if path.startswith(prefix) and path.endswith("/events"):
            calendar_id = path[len(prefix) : -len("/events")]
            seen.setdefault("params_by_calendar", {})[calendar_id] = dict(req.url.params)
            seen.setdefault("auth_by_calendar", {})[calendar_id] = req.headers.get("authorization")
            status = calendar_statuses.get(calendar_id, 200)
            if status != 200:
                return httpx.Response(status, json={"error": "boom"}, request=req)
            items = events_by_calendar.get(calendar_id, [])
            return httpx.Response(200, json={"items": items}, request=req)

        return httpx.Response(404, json={}, request=req)

    return handler


async def _no_sleep(_delay: float) -> None:
    return None


# --------------------------------------------------------------------------- #
# Field mapping                                                               #
# --------------------------------------------------------------------------- #


async def test_gcal_fetch_maps_fields_and_renders_content() -> None:
    seen: dict[str, Any] = {}
    events = {"primary": [_event("evt-1")]}
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler(seen, events)))
    source = _source(_config(calendar_ids=["primary"]))

    items = await connector.fetch(source)
    assert len(items) == 1
    item = items[0]
    assert item.external_id == "primary:evt-1"
    assert item.doc_type == "doc"
    assert item.title == "Sprint planning"
    assert "Plan the sprint." in item.content
    assert "Organizer: priya@demo.dev" in item.content
    assert "priya@demo.dev (accepted)" in item.content
    assert "nina@demo.dev (needsAction)" in item.content
    assert "Start: 2026-07-01T10:00:00-07:00" in item.content
    assert "End: 2026-07-01T10:30:00-07:00" in item.content
    assert item.author_email == "priya@demo.dev"
    assert item.url  # constructed fallback since no htmlLink
    assert item.metadata["calendarId"] == "primary"
    assert item.metadata["start"] == {"dateTime": "2026-07-01T10:00:00-07:00"}
    assert item.last_activity_at.isoformat() == "2026-07-01T08:00:00+00:00"

    assert seen["auth_by_calendar"]["primary"] == "Bearer ya29.gcal-token"
    params = seen["params_by_calendar"]["primary"]
    assert params["orderBy"] == "updated"
    assert params["maxResults"] == "100"
    assert params["showDeleted"] == "false"


async def test_gcal_uses_html_link_when_present() -> None:
    events = {"primary": [_event("evt-2", html_link="https://calendar.google.com/event?eid=abc")]}
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler({}, events)))
    items = await connector.fetch(_source(_config()))
    assert items[0].url == "https://calendar.google.com/event?eid=abc"


async def test_gcal_token_minted_once_and_reused_across_calendars() -> None:
    seen: dict[str, Any] = {}
    events = {"cal-a": [_event("a-1")], "cal-b": [_event("b-1")]}
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler(seen, events)))
    source = _source(_config(calendar_ids=["cal-a", "cal-b"]))

    await connector.fetch(source)
    assert seen["token_calls"] == 1


# --------------------------------------------------------------------------- #
# Per-calendar cursors                                                        #
# --------------------------------------------------------------------------- #


async def test_gcal_per_calendar_cursors_advance_independently() -> None:
    seen: dict[str, Any] = {}
    events = {
        "cal-a": [_event("a-1", updated="2026-07-01T08:00:00.000Z")],
        "cal-b": [_event("b-1", updated="2026-07-03T09:00:00.000Z")],
    }
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler(seen, events)))
    source = _source(_config(calendar_ids=["cal-a", "cal-b"]))

    await connector.fetch(source)
    assert source.sync_state["updated_cursor:cal-a"] == "2026-07-01T08:00:00+00:00"
    assert source.sync_state["updated_cursor:cal-b"] == "2026-07-03T09:00:00+00:00"

    # second fetch: each calendar's updatedMin reflects its own advanced cursor
    await connector.fetch(source)
    assert seen["params_by_calendar"]["cal-a"]["updatedMin"] == "2026-07-01T08:00:00+00:00"
    assert seen["params_by_calendar"]["cal-b"]["updatedMin"] == "2026-07-03T09:00:00+00:00"


async def test_gcal_first_sync_uses_backfill_window() -> None:
    seen: dict[str, Any] = {}
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler(seen, {"primary": []})))
    source = _source(_config())

    before = now_utc()
    await connector.fetch(source)
    after = now_utc()

    since = parse_iso(seen["params_by_calendar"]["primary"]["updatedMin"])
    assert since is not None
    assert (before - timedelta(days=90)) <= since <= (after - timedelta(days=90))


# --------------------------------------------------------------------------- #
# Cancelled / malformed events                                                #
# --------------------------------------------------------------------------- #


async def test_gcal_cancelled_event_skipped_but_still_advances_cursor() -> None:
    events = {
        "primary": [
            _event("evt-ok", updated="2026-07-01T08:00:00.000Z"),
            _event("evt-cancelled", status="cancelled", updated="2026-07-05T08:00:00.000Z"),
        ]
    }
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler({}, events)))
    source = _source(_config())

    items = await connector.fetch(source)
    assert [i.external_id for i in items] == ["primary:evt-ok"]
    assert source.sync_state["updated_cursor:primary"] == "2026-07-05T08:00:00+00:00"


async def test_gcal_malformed_event_skipped() -> None:
    malformed_no_id = {
        "summary": "no id",
        "start": {"dateTime": "2026-07-01T10:00:00-07:00"},
        "updated": "2026-07-01T08:00:00.000Z",
    }
    malformed_no_start = {
        "id": "evt-no-start",
        "summary": "no start",
        "updated": "2026-07-01T08:00:00.000Z",
    }
    good = _event("evt-good")
    events = {"primary": [malformed_no_id, malformed_no_start, good]}
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler({}, events)))

    items = await connector.fetch(_source(_config()))
    assert [i.external_id for i in items] == ["primary:evt-good"]


# --------------------------------------------------------------------------- #
# ACL                                                                          #
# --------------------------------------------------------------------------- #


async def test_gcal_acl_is_attendee_scoped_by_default() -> None:
    events = {"primary": [_event("evt-1")]}
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler({}, events)))
    source = _source(_config(subject="alix@acme.dev"))

    items = await connector.fetch(source)
    acl = items[0].acl
    assert acl.public is False
    assert acl.user_emails == ["alix@acme.dev", "priya@demo.dev", "nina@demo.dev"]


async def test_gcal_restrict_to_team_acl() -> None:
    events = {"primary": [_event("evt-1")]}
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler({}, events)))
    source = _source(_config(restrict_to_team="Payments"))

    items = await connector.fetch(source)
    assert items[0].acl.public is False
    assert items[0].acl.team_names == ["Payments"]
    assert items[0].acl.user_emails == []


# --------------------------------------------------------------------------- #
# Per-calendar isolation                                                      #
# --------------------------------------------------------------------------- #


async def test_gcal_one_calendar_failure_does_not_lose_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("context_engine.connectors.live.http.asyncio.sleep", _no_sleep)
    events = {"cal-a": [_event("a-1")], "cal-b": [_event("b-1")]}
    connector = GCalLiveConnector(
        transport=httpx.MockTransport(_handler({}, events, calendar_statuses={"cal-a": 500}))
    )
    source = _source(_config(calendar_ids=["cal-a", "cal-b"]))

    items = await connector.fetch(source)
    assert [i.external_id for i in items] == ["cal-b:b-1"]
    assert "updated_cursor:cal-a" not in source.sync_state
    assert source.sync_state["updated_cursor:cal-b"]


# --------------------------------------------------------------------------- #
# Auth errors                                                                 #
# --------------------------------------------------------------------------- #


async def test_gcal_missing_subject_raises_auth_error() -> None:
    connector = GCalLiveConnector(transport=httpx.MockTransport(_handler({}, {})))
    config = _config()
    del config["subject"]

    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_source(config))


async def test_gcal_token_401_raises_auth_error() -> None:
    connector = GCalLiveConnector(
        transport=httpx.MockTransport(_handler({}, {"primary": []}, token_status=401))
    )
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_source(_config()))


async def test_gcal_calendar_events_401_raises_auth_error() -> None:
    connector = GCalLiveConnector(
        transport=httpx.MockTransport(
            _handler({}, {"primary": []}, calendar_statuses={"primary": 401})
        )
    )
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_source(_config()))
