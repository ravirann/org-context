"""Live Gmail connector: mailbox messages via the Gmail REST API.

Authenticates as a Google service account with domain-wide delegation: the
configured ``subject`` mailbox is impersonated (see
:mod:`context_engine.connectors.live.google`), so a single service-account key
can pull mail for whichever address the org grants delegation for.

Email is inherently private, so this connector never emits a public ACL: absent
an explicit team scope in config, every item is restricted to the impersonated
mailbox owner.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from email.utils import parseaddr
from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawAcl, RawItem
from context_engine.connectors.live.google import GoogleServiceAccountAuth
from context_engine.connectors.live.http import ConnectorAuthError, build_client, request_json
from context_engine.connectors.live.util import backfill_start, resolve_acl
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Source

logger = get_logger(__name__)

DEFAULT_API_URL = "https://gmail.googleapis.com"
"""Gmail API host, used when the source config omits ``api_url``."""

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
"""OAuth scope requested for the service-account token."""

_LIST_PAGE_SIZE = 100
"""``maxResults`` for ``messages.list``."""

_MAX_MESSAGE_FETCHES = 50
"""Per-sync cap on the (expensive) per-message ``messages.get`` fetch."""

_MAX_CONTENT_CHARS = 100_000
"""Truncation length for extracted message bodies."""


class GmailLiveConnector:
    """Fetch mailbox messages new since the cursor for a delegated mailbox."""

    source_type: ClassVar[str] = "gmail"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self, source: Source) -> httpx.AsyncClient:
        config = source.config
        return build_client(
            base_url=str(config.get("api_url") or DEFAULT_API_URL).rstrip("/"),
            transport=self._transport,
        )

    async def fetch(self, source: Source) -> list[RawItem]:
        config = source.config

        subject = config.get("subject")
        if not subject:
            raise ConnectorAuthError(
                "gmail source config is missing required 'subject' "
                "(the mailbox address to impersonate)"
            )
        subject = str(subject)

        service_account_json = config.get("service_account_json")
        if not service_account_json:
            raise ConnectorAuthError(
                "gmail source config is missing required 'service_account_json'"
            )

        since_seconds = _since_seconds(source.sync_state, config)
        extra_query = config.get("query")
        q = f"after:{since_seconds}"
        if extra_query:
            q = f"{q} {extra_query}"

        acl = _resolve_gmail_acl(config, subject)
        auth = GoogleServiceAccountAuth(
            str(service_account_json), scopes=[GMAIL_READONLY_SCOPE], subject=subject
        )

        items: list[RawItem] = []
        max_seconds = since_seconds
        async with self._client(source) as client:
            token = await auth.access_token(client)
            client.headers["Authorization"] = f"Bearer {token}"

            message_ids = await self._list_message_ids(client, subject, q)
            for message_id in message_ids[:_MAX_MESSAGE_FETCHES]:
                item = await self._message_item(client, subject, message_id, acl)
                if item is None:
                    continue
                items.append(item)
                seconds = int(item.last_activity_at.timestamp())
                if seconds > max_seconds:
                    max_seconds = seconds

        source.sync_state["internal_date_cursor"] = max_seconds
        return items

    async def _list_message_ids(self, client: httpx.AsyncClient, subject: str, q: str) -> list[str]:
        payload = await request_json(
            client,
            "GET",
            f"/gmail/v1/users/{subject}/messages",
            params={"q": q, "maxResults": _LIST_PAGE_SIZE},
        )
        if not isinstance(payload, dict):
            return []
        raw_messages = payload.get("messages")
        if not isinstance(raw_messages, list):
            return []
        ids: list[str] = []
        for entry in raw_messages:
            if isinstance(entry, dict) and entry.get("id"):
                ids.append(str(entry["id"]))
        return ids

    async def _message_item(
        self, client: httpx.AsyncClient, subject: str, message_id: str, acl: RawAcl
    ) -> RawItem | None:
        try:
            payload = await request_json(
                client,
                "GET",
                f"/gmail/v1/users/{subject}/messages/{message_id}",
                params={"format": "full"},
            )
        except Exception:  # noqa: BLE001 — one message's failure must not abort the sync
            logger.warning("gmail_message_fetch_failed", message_id=message_id)
            return None

        if not isinstance(payload, dict):
            logger.warning("gmail_message_malformed", message_id=message_id)
            return None

        try:
            msg_id = str(payload["id"])
            last_activity_at = datetime.fromtimestamp(int(payload["internalDate"]) / 1000, tz=UTC)
        except (KeyError, TypeError, ValueError):
            logger.warning("gmail_message_malformed", keys=list(payload))
            return None

        message_payload = payload.get("payload")
        message_payload = message_payload if isinstance(message_payload, dict) else {}
        headers = _headers_map(message_payload)
        title = headers.get("subject") or "(no subject)"
        author_email = _parse_from_header(headers.get("from"))

        body = _extract_body(message_payload)
        if not body:
            body = str(payload.get("snippet") or "")
        content = body[:_MAX_CONTENT_CHARS]

        return RawItem(
            external_id=msg_id,
            doc_type="message",
            title=title,
            content=content,
            url=f"https://mail.google.com/mail/u/0/#all/{msg_id}",
            author_email=author_email,
            acl=acl,
            metadata={"thread_id": payload.get("threadId")},
            last_activity_at=last_activity_at,
        )


def _since_seconds(sync_state: dict[str, Any], config: dict[str, Any]) -> int:
    """Resolve the ``after:`` epoch-seconds value: stored cursor or backfill start."""
    cursor = sync_state.get("internal_date_cursor")
    if isinstance(cursor, int | float) and not isinstance(cursor, bool):
        return int(cursor)
    return int(backfill_start(config).timestamp())


def _resolve_gmail_acl(config: dict[str, Any], subject: str) -> RawAcl:
    """Team-scope the ACL only when config explicitly asks; default to mailbox-only.

    Email is inherently private, so unlike other live connectors this never falls
    back to a public ACL: absent ``team_name``/``restrict_to_team`` config, items
    are restricted to the impersonated mailbox owner.
    """
    if config.get("team_name") or config.get("restrict_to_team"):
        acl = resolve_acl(config, private=True)
        if not acl.public:
            return acl
    return RawAcl(public=False, user_emails=[subject])


def _headers_map(message_payload: dict[str, Any]) -> dict[str, str]:
    """Lower-cased ``header name -> value`` map from a Gmail message payload."""
    headers = message_payload.get("headers")
    if not isinstance(headers, list):
        return {}
    out: dict[str, str] = {}
    for header in headers:
        if isinstance(header, dict) and header.get("name"):
            out[str(header["name"]).lower()] = str(header.get("value") or "")
    return out


def _parse_from_header(value: str | None) -> str | None:
    """Extract the bare address from a ``"Name <addr>"``-style ``From`` header."""
    if not value:
        return None
    _, addr = parseaddr(value)
    return addr or None


def _extract_body(message_payload: dict[str, Any]) -> str:
    """First ``text/plain`` part found walking ``parts`` recursively, else top body."""
    found = _find_text_plain(message_payload)
    if found is not None:
        return found
    body = message_payload.get("body")
    if isinstance(body, dict) and body.get("data"):
        return _b64url_decode(str(body["data"]))
    return ""


def _find_text_plain(part: Any) -> str | None:
    if not isinstance(part, dict):
        return None
    body = part.get("body")
    if part.get("mimeType") == "text/plain" and isinstance(body, dict) and body.get("data"):
        return _b64url_decode(str(body["data"]))
    sub_parts = part.get("parts")
    if isinstance(sub_parts, list):
        for sub_part in sub_parts:
            found = _find_text_plain(sub_part)
            if found is not None:
                return found
    return None


def _b64url_decode(data: str) -> str:
    try:
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""
