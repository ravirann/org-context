"""Live Google Drive connector: files changed since the cursor via ``files.list``.

Authenticates with a service-account key through
:class:`~context_engine.connectors.live.google.GoogleServiceAccountAuth` (optionally
impersonating a user for domain-wide delegation), then lists files whose
``modifiedTime`` is newer than the stored cursor. Content is fetched per file — a
plain-text/CSV export for Google-native docs/sheets/slides, raw bytes for
text-ish mime types — capped at a fixed number of expensive fetches per sync;
everything else (including per-file fetch failures) falls back to a
title-plus-mime-type placeholder so no item is ever dropped.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawItem
from context_engine.connectors.live.google import GoogleServiceAccountAuth
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

DEFAULT_API_URL = "https://www.googleapis.com"
"""Default Drive API host, overridable via ``config["api_url"]`` (e.g. for tests)."""

_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
_PAGE_SIZE = 100
_MAX_CONTENT_FETCHES = 50
"""Per-sync cap on the (expensive) export/media content fetch; beyond this — and on
any per-file fetch failure — files fall back to title+mimeType-only content."""
_MAX_CONTENT_CHARS = 100_000
"""Hard cap on fetched content length."""

_EXPORT_MIME_TYPES: dict[str, str] = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}
"""Google-native mime types and the export format requested for each."""

_FIELDS = "files(id,name,mimeType,modifiedTime,webViewLink,owners(emailAddress))"


class GDriveLiveConnector:
    """Fetch Drive files (title + best-effort content) modified since the cursor."""

    source_type: ClassVar[str] = "gdrive"

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
        since = cursor_since(source.sync_state, "modified_cursor", config)
        acl = resolve_acl(config)
        folder_ids = [str(fid) for fid in (config.get("folder_ids") or [])]
        auth = GoogleServiceAccountAuth(
            str(config["service_account_json"]),
            scopes=[_SCOPE],
            subject=str(config["subject"]) if config.get("subject") else None,
        )

        items: list[RawItem] = []
        max_modified = since
        content_fetches = 0

        async with self._client(source) as client:
            token = await auth.access_token(client)
            client.headers["Authorization"] = f"Bearer {token}"

            payload = await request_json(
                client,
                "GET",
                "/drive/v3/files",
                params={
                    "q": _build_query(since, folder_ids),
                    "orderBy": "modifiedTime",
                    "pageSize": _PAGE_SIZE,
                    "supportsAllDrives": True,
                    "includeItemsFromAllDrives": True,
                    "fields": _FIELDS,
                },
            )
            files = payload.get("files", []) if isinstance(payload, dict) else []

            for file in files:
                if not isinstance(file, dict):
                    logger.warning("gdrive_file_malformed", file=file)
                    continue
                try:
                    file_id = str(file["id"])
                    name = str(file["name"])
                except (KeyError, TypeError):
                    logger.warning("gdrive_file_malformed", keys=list(file))
                    continue

                mime_type = str(file.get("mimeType") or "")
                if _is_fetchable(mime_type) and content_fetches < _MAX_CONTENT_FETCHES:
                    content_fetches += 1
                    fetched = await self._fetch_content(client, file_id, mime_type)
                    content = fetched if fetched is not None else _fallback_content(name, mime_type)
                else:
                    content = _fallback_content(name, mime_type)
                content = content[:_MAX_CONTENT_CHARS]

                modified = parse_iso(str(file.get("modifiedTime") or ""))
                url = (
                    str(file.get("webViewLink") or "")
                    or f"https://drive.google.com/file/d/{file_id}/view"
                )

                items.append(
                    RawItem(
                        external_id=file_id,
                        doc_type="doc",
                        title=name,
                        content=content,
                        url=url,
                        author_email=_first_owner_email(file.get("owners")),
                        acl=acl,
                        metadata={"mimeType": mime_type},
                        last_activity_at=modified or now_utc(),
                    )
                )
                if modified is not None and modified > max_modified:
                    max_modified = modified

        source.sync_state["modified_cursor"] = to_iso(max_modified)
        return items

    async def _fetch_content(
        self, client: httpx.AsyncClient, file_id: str, mime_type: str
    ) -> str | None:
        """Best-effort raw content fetch for one file; ``None`` signals fallback."""
        try:
            if mime_type in _EXPORT_MIME_TYPES:
                response = await client.get(
                    f"/drive/v3/files/{file_id}/export",
                    params={"mimeType": _EXPORT_MIME_TYPES[mime_type]},
                )
            else:
                response = await client.get(
                    f"/drive/v3/files/{file_id}",
                    params={"alt": "media"},
                )
        except httpx.HTTPError as exc:
            logger.warning("gdrive_content_fetch_transport_error", file_id=file_id, error=str(exc))
            return None
        if response.status_code >= 400:
            logger.warning(
                "gdrive_content_fetch_failed", file_id=file_id, status=response.status_code
            )
            return None
        return response.text


def _is_fetchable(mime_type: str) -> bool:
    """Whether content is worth an expensive fetch (export or plain-text-ish)."""
    return (
        mime_type in _EXPORT_MIME_TYPES
        or mime_type.startswith("text/")
        or (mime_type == "application/json")
    )


def _fallback_content(name: str, mime_type: str) -> str:
    """Title+mimeType placeholder used when content wasn't (or couldn't be) fetched."""
    return f"{name} ({mime_type})" if mime_type else name


def _first_owner_email(owners: Any) -> str | None:
    if not isinstance(owners, list):
        return None
    for owner in owners:
        if isinstance(owner, dict) and owner.get("emailAddress"):
            return str(owner["emailAddress"])
    return None


def _build_query(since: datetime, folder_ids: list[str]) -> str:
    parts = [f"modifiedTime > '{to_iso(since)}'", "trashed = false"]
    if folder_ids:
        clause = " or ".join(f"'{fid}' in parents" for fid in folder_ids)
        parts.append(f"({clause})")
    return " and ".join(parts)
