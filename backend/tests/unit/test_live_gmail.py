"""Unit tests for the live Gmail connector.

Imports the connector module directly (not via ``get_connector``, the live
registry, or ``live/__init__.py``) so this test is independent of registry
wiring. No real network: every request — the service-account token exchange
and the Gmail API calls — goes through a single ``httpx.MockTransport`` whose
handler routes by URL, mirroring how the connector shares one client for both.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from context_engine.connectors.live.gmail import GmailLiveConnector
from context_engine.connectors.live.http import ConnectorAuthError
from context_engine.connectors.live.util import backfill_start
from context_engine.storage import models as m

Handler = Callable[[httpx.Request], httpx.Response]

TOKEN_URI = "https://oauth2.googleapis.com/token"


def _rsa_private_pem() -> str:
    """Generate a throwaway 2048-bit RSA private key (PEM), no real credentials."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


_SERVICE_ACCOUNT_JSON = json.dumps(
    {
        "type": "service_account",
        "client_email": "svc@proj.iam.gserviceaccount.com",
        "private_key": _rsa_private_pem(),
        "token_uri": TOKEN_URI,
    }
)


def _source(config: dict[str, Any], sync_state: dict[str, Any] | None = None) -> m.Source:
    return m.Source(
        type=m.SourceType.gmail,
        name="gmail live",
        config=config,
        sync_state=sync_state or {},
    )


def _config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "mode": "live",
        "service_account_json": _SERVICE_ACCOUNT_JSON,
        "subject": "mailbox@acme.dev",
    }
    config.update(overrides)
    return config


def _b64url(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _text_message(
    msg_id: str,
    internal_ms: int,
    *,
    subject: str = "Subject line",
    sender: str = "a@demo.dev",
    text: str = "body text",
    snippet: str = "snippet",
) -> dict[str, Any]:
    """A well-formed Gmail ``messages.get`` payload with a top-level text/plain body."""
    return {
        "id": msg_id,
        "internalDate": str(internal_ms),
        "snippet": snippet,
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
            ],
            "body": {"data": _b64url(text)},
        },
    }


def _gmail_handler(
    seen: dict[str, Any],
    *,
    list_payload: dict[str, Any] | None = None,
    messages: dict[str, dict[str, Any]] | None = None,
    list_status: int = 200,
    token_status: int = 200,
) -> Handler:
    """Route mock requests to the token endpoint, ``messages.list``, or ``messages.get``."""
    messages = messages or {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST" and str(req.url) == TOKEN_URI:
            seen["token_calls"] = seen.get("token_calls", 0) + 1
            return httpx.Response(
                token_status,
                json={"access_token": "test-access-token", "expires_in": 3600},
                request=req,
            )

        path = req.url.path
        if req.method == "GET" and path.endswith("/messages"):
            seen["list_params"] = dict(req.url.params)
            seen["list_auth"] = req.headers.get("authorization")
            return httpx.Response(list_status, json=list_payload or {"messages": []}, request=req)

        if req.method == "GET" and "/messages/" in path:
            msg_id = path.rsplit("/", 1)[-1]
            seen.setdefault("fetched_ids", []).append(msg_id)
            message = messages.get(msg_id)
            if message is None:
                return httpx.Response(404, json={"error": "not found"}, request=req)
            return httpx.Response(200, json=message, request=req)

        return httpx.Response(404, json={}, request=req)

    return handler


# --------------------------------------------------------------------------- #
# Field mapping                                                               #
# --------------------------------------------------------------------------- #


async def test_field_mapping_base64_body_and_from_header() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 10, 9, 0, tzinfo=UTC).timestamp() * 1000)
    message = {
        "id": "msg-1",
        "threadId": "thread-abc",
        "internalDate": str(internal_ms),
        "snippet": "fallback snippet",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": "Re: Duplicate charge"},
                {"name": "From", "value": "Priya K <priya@demo.dev>"},
            ],
            "body": {"data": _b64url("Hello,\n\nThe refund cleared.\n\n— Priya")},
        },
    }
    handler = _gmail_handler(
        seen,
        list_payload={"messages": [{"id": "msg-1", "threadId": "thread-abc"}]},
        messages={"msg-1": message},
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))
    source = _source(_config())

    items = await connector.fetch(source)

    assert len(items) == 1
    item = items[0]
    assert item.external_id == "msg-1"
    assert item.doc_type == "message"
    assert item.title == "Re: Duplicate charge"
    assert "The refund cleared." in item.content
    assert item.author_email == "priya@demo.dev"
    assert item.url == "https://mail.google.com/mail/u/0/#all/msg-1"
    assert item.last_activity_at == datetime.fromtimestamp(internal_ms / 1000, tz=UTC)
    assert item.metadata["thread_id"] == "thread-abc"
    assert seen["list_auth"] == "Bearer test-access-token"


async def test_nested_multipart_text_plain_is_found() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 5, tzinfo=UTC).timestamp() * 1000)
    message = {
        "id": "msg-nested",
        "internalDate": str(internal_ms),
        "snippet": "fallback",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "Subject", "value": "Nested body"},
                {"name": "From", "value": "liam@demo.dev"},
            ],
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": _b64url("plain text body")}},
                        {"mimeType": "text/html", "body": {"data": _b64url("<p>html body</p>")}},
                    ],
                },
            ],
        },
    }
    handler = _gmail_handler(
        seen,
        list_payload={"messages": [{"id": "msg-nested"}]},
        messages={"msg-nested": message},
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))

    items = await connector.fetch(_source(_config()))

    assert items[0].content == "plain text body"
    assert items[0].author_email == "liam@demo.dev"  # bare address, no display name


async def test_snippet_fallback_when_no_text_plain_part() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1000)
    message = {
        "id": "msg-html-only",
        "internalDate": str(internal_ms),
        "snippet": "Plain-text preview from Gmail",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Subject", "value": "HTML only"},
                {"name": "From", "value": "a@demo.dev"},
            ],
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64url("<p>html</p>")}},
            ],
        },
    }
    handler = _gmail_handler(
        seen,
        list_payload={"messages": [{"id": "msg-html-only"}]},
        messages={"msg-html-only": message},
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))

    items = await connector.fetch(_source(_config()))

    assert items[0].content == "Plain-text preview from Gmail"


# --------------------------------------------------------------------------- #
# Cursor + query assembly                                                     #
# --------------------------------------------------------------------------- #


async def test_after_cursor_present_and_advances_in_seconds() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 10, tzinfo=UTC).timestamp() * 1000)
    message = _text_message("msg-1", internal_ms)
    handler = _gmail_handler(
        seen, list_payload={"messages": [{"id": "msg-1"}]}, messages={"msg-1": message}
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))
    source = _source(_config())

    await connector.fetch(source)

    assert seen["list_params"]["q"].startswith("after:")
    cursor = source.sync_state["internal_date_cursor"]
    assert cursor == internal_ms // 1000  # seconds, not milliseconds
    assert cursor < internal_ms


async def test_second_fetch_uses_stored_cursor_as_after() -> None:
    seen: dict[str, Any] = {}
    handler = _gmail_handler(seen, list_payload={"messages": []})
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))
    source = _source(_config(), {"internal_date_cursor": 1751500800})

    await connector.fetch(source)

    assert seen["list_params"]["q"] == "after:1751500800"


async def test_first_sync_uses_backfill_window() -> None:
    seen: dict[str, Any] = {}
    handler = _gmail_handler(seen, list_payload={"messages": []})
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))

    before = int(backfill_start({}).timestamp())
    await connector.fetch(_source(_config()))
    after = int(backfill_start({}).timestamp())

    q = seen["list_params"]["q"]
    assert q.startswith("after:")
    value = int(q.removeprefix("after:"))
    assert before - 2 <= value <= after + 2


async def test_configured_query_anded_into_q() -> None:
    seen: dict[str, Any] = {}
    handler = _gmail_handler(seen, list_payload={"messages": []})
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))
    source = _source(_config(query="from:billing-lead@merchant-corp.example"))

    await connector.fetch(source)

    q = seen["list_params"]["q"]
    assert q.startswith("after:")
    assert q.endswith(" from:billing-lead@merchant-corp.example")


async def test_per_sync_fetch_capped_at_fifty_messages() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1000)
    ids = [f"msg-{i}" for i in range(75)]
    messages = {mid: _text_message(mid, internal_ms) for mid in ids}
    handler = _gmail_handler(
        seen, list_payload={"messages": [{"id": mid} for mid in ids]}, messages=messages
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))

    items = await connector.fetch(_source(_config()))

    assert len(items) == 50
    assert len(seen["fetched_ids"]) == 50


# --------------------------------------------------------------------------- #
# ACL                                                                         #
# --------------------------------------------------------------------------- #


async def test_acl_default_non_public_user_emails_subject() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1000)
    message = _text_message("msg-1", internal_ms)
    handler = _gmail_handler(
        seen, list_payload={"messages": [{"id": "msg-1"}]}, messages={"msg-1": message}
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))
    source = _source(_config(subject="mailbox@acme.dev"))

    items = await connector.fetch(source)

    assert items[0].acl.public is False
    assert items[0].acl.user_emails == ["mailbox@acme.dev"]
    assert items[0].acl.team_names == []


async def test_acl_team_scoped_when_restrict_to_team_configured() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1000)
    message = _text_message("msg-1", internal_ms)
    handler = _gmail_handler(
        seen, list_payload={"messages": [{"id": "msg-1"}]}, messages={"msg-1": message}
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))
    source = _source(_config(restrict_to_team="Payments"))

    items = await connector.fetch(source)

    assert items[0].acl.public is False
    assert items[0].acl.team_names == ["Payments"]


# --------------------------------------------------------------------------- #
# Error handling / per-item isolation                                        #
# --------------------------------------------------------------------------- #


async def test_missing_subject_raises_connector_auth_error() -> None:
    connector = GmailLiveConnector(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={}, request=req))
    )
    config = _config()
    del config["subject"]
    with pytest.raises(ConnectorAuthError, match="subject"):
        await connector.fetch(_source(config))


async def test_missing_service_account_json_raises_connector_auth_error() -> None:
    connector = GmailLiveConnector(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json={}, request=req))
    )
    config = _config()
    del config["service_account_json"]
    with pytest.raises(ConnectorAuthError, match="service_account_json"):
        await connector.fetch(_source(config))


async def test_401_on_list_raises_connector_auth_error() -> None:
    seen: dict[str, Any] = {}
    handler = _gmail_handler(seen, list_payload={}, list_status=401)
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))

    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_source(_config()))


async def test_malformed_message_skipped() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1000)
    good = _text_message("msg-good", internal_ms, subject="Good", text="good body")
    malformed = {"id": "msg-bad", "snippet": "no internalDate or payload at all"}
    handler = _gmail_handler(
        seen,
        list_payload={"messages": [{"id": "msg-bad"}, {"id": "msg-good"}]},
        messages={"msg-bad": malformed, "msg-good": good},
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))

    items = await connector.fetch(_source(_config()))

    assert [i.external_id for i in items] == ["msg-good"]


async def test_per_message_fetch_failure_is_skipped_not_fatal() -> None:
    seen: dict[str, Any] = {}
    internal_ms = int(datetime(2026, 7, 1, tzinfo=UTC).timestamp() * 1000)
    good = _text_message("msg-good", internal_ms, subject="Good", text="good body")
    # "msg-missing" has no entry in `messages`, so the per-message GET 404s.
    handler = _gmail_handler(
        seen,
        list_payload={"messages": [{"id": "msg-missing"}, {"id": "msg-good"}]},
        messages={"msg-good": good},
    )
    connector = GmailLiveConnector(transport=httpx.MockTransport(handler))

    items = await connector.fetch(_source(_config()))

    assert [i.external_id for i in items] == ["msg-good"]
