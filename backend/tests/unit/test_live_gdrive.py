"""Unit tests for the live Google Drive connector.

Imports the connector module directly (not via ``get_connector``, the live
registry, or ``live/__init__.py``) so this test is independent of registry
wiring. No real network: every request — including the Google service-account
token exchange — goes through a single ``httpx.MockTransport`` routed by URL,
mirroring how the shared client must serve both (see
:mod:`context_engine.connectors.live.google` and its tests for the underlying
JWT-bearer flow this connector authenticates through).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from context_engine.connectors.live.gdrive import GDriveLiveConnector
from context_engine.connectors.live.http import ConnectorAuthError
from context_engine.connectors.live.util import backfill_start, parse_iso
from context_engine.storage import models as m

Handler = Callable[[httpx.Request], httpx.Response]

TOKEN_URI = "https://oauth2.example.test/token"
CLIENT_EMAIL = "svc@proj.iam.gserviceaccount.com"
API_URL = "https://drive.example.test"


def _rsa_private_pem() -> str:
    """Generate a throwaway RSA key so the JWT-bearer assertion can be signed."""
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


def _source(config_extra: dict | None = None, sync_state: dict | None = None) -> m.Source:
    config = {
        "mode": "live",
        "service_account_json": _sa_json(),
        "api_url": API_URL,
        **(config_extra or {}),
    }
    return m.Source(
        type=m.SourceType.gdrive, name="gdrive live", config=config, sync_state=sync_state or {}
    )


def _json_response(request: httpx.Request, payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=request)


_FILES_PAYLOAD: dict = {
    "files": [
        {
            "id": "file-doc-1",
            "name": "Idempotency key rollout plan",
            "mimeType": "application/vnd.google-apps.document",
            "modifiedTime": "2026-07-01T10:00:00.000Z",
            "webViewLink": "https://docs.google.com/document/d/file-doc-1/edit",
            "owners": [{"emailAddress": "priya@demo.dev"}],
        },
        {
            "id": "file-txt-1",
            "name": "notes.txt",
            "mimeType": "text/plain",
            "modifiedTime": "2026-07-02T09:00:00.000Z",
            "webViewLink": "https://drive.google.com/file/d/file-txt-1/view",
        },
        {
            "id": "file-bin-1",
            "name": "diagram.png",
            "mimeType": "image/png",
            "modifiedTime": "2026-07-03T09:00:00.000Z",
        },
        {"name": "missing id field"},  # malformed
    ]
}


def _make_handler(
    *,
    files_status: int = 200,
    files_payload: dict | None = None,
    export_status: int = 200,
    export_text: str = "Exported plain-text body.",
    media_status: int = 200,
    media_text: str = "Raw text body.",
    token_status: int = 200,
    seen: dict | None = None,
) -> Handler:
    seen = seen if seen is not None else {}
    payload = files_payload if files_payload is not None else _FILES_PAYLOAD

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if url.startswith(TOKEN_URI):
            seen["token_calls"] = seen.get("token_calls", 0) + 1
            if token_status != 200:
                return _json_response(req, {"error": "invalid_grant"}, status=token_status)
            return _json_response(req, {"access_token": "ya29.mock-token", "expires_in": 3600})

        path = req.url.path
        if path == "/drive/v3/files":
            seen["files_params"] = dict(req.url.params)
            seen["files_headers"] = {k.lower(): v for k, v in req.headers.items()}
            return _json_response(req, payload, status=files_status)

        if path.endswith("/export"):
            seen.setdefault("export_calls", []).append(path)
            if export_status != 200:
                return httpx.Response(export_status, text="export failed", request=req)
            return httpx.Response(200, text=export_text, request=req)

        if req.url.params.get("alt") == "media":
            seen.setdefault("media_calls", []).append(path)
            if media_status != 200:
                return httpx.Response(media_status, text="media failed", request=req)
            return httpx.Response(200, text=media_text, request=req)

        return _json_response(req, {}, status=404)

    return handler


async def test_fetch_maps_fields() -> None:
    seen: dict = {}
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler(seen=seen)))

    items = await connector.fetch(_source())
    by_id = {i.external_id: i for i in items}

    assert len(items) == 3  # malformed entry skipped

    doc = by_id["file-doc-1"]
    assert doc.doc_type == "doc"
    assert doc.title == "Idempotency key rollout plan"
    assert doc.content == "Exported plain-text body."
    assert doc.url == "https://docs.google.com/document/d/file-doc-1/edit"
    assert doc.author_email == "priya@demo.dev"
    assert doc.metadata["mimeType"] == "application/vnd.google-apps.document"

    text_file = by_id["file-txt-1"]
    assert text_file.content == "Raw text body."
    assert text_file.author_email is None

    binary = by_id["file-bin-1"]
    assert binary.content == "diagram.png (image/png)"
    assert binary.url == "https://drive.google.com/file/d/file-bin-1/view"  # constructed fallback


async def test_api_request_carries_bearer_token() -> None:
    seen: dict = {}
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler(seen=seen)))

    await connector.fetch(_source())

    assert seen["files_headers"]["authorization"] == "Bearer ya29.mock-token"
    assert seen["token_calls"] == 1


async def test_cursor_advances_and_used_on_second_fetch() -> None:
    seen: dict = {}
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler(seen=seen)))
    source = _source()

    await connector.fetch(source)
    assert source.sync_state["modified_cursor"] == "2026-07-03T09:00:00+00:00"

    await connector.fetch(source)
    assert "2026-07-03T09:00:00" in seen["files_params"]["q"]


async def test_first_sync_uses_backfill_window() -> None:
    seen: dict = {}
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler(seen=seen)))
    source = _source({"backfill_days": 30})

    await connector.fetch(source)

    match = re.search(r"modifiedTime > '([^']+)'", seen["files_params"]["q"])
    assert match is not None
    actual = parse_iso(match.group(1))
    expected = backfill_start(source.config)
    assert actual is not None
    assert abs((actual - expected).total_seconds()) <= 5  # tolerate real-clock drift


async def test_folder_ids_scope_query() -> None:
    seen: dict = {}
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler(seen=seen)))
    source = _source({"folder_ids": ["folder-a", "folder-b"]})

    await connector.fetch(source)

    q = seen["files_params"]["q"]
    assert "'folder-a' in parents" in q
    assert "'folder-b' in parents" in q
    assert " or " in q


async def test_google_doc_uses_export_and_binary_never_fetched() -> None:
    seen: dict = {}
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler(seen=seen)))

    items = await connector.fetch(_source())
    by_id = {i.external_id: i for i in items}

    assert seen["export_calls"]  # the google-native doc went through /export
    assert by_id["file-doc-1"].content == "Exported plain-text body."
    assert by_id["file-bin-1"].content == "diagram.png (image/png)"
    assert "media_calls" not in seen or "/drive/v3/files/file-bin-1" not in seen["media_calls"]


async def test_export_failure_falls_back_to_title_only() -> None:
    seen: dict = {}
    connector = GDriveLiveConnector(
        transport=httpx.MockTransport(_make_handler(export_status=500, seen=seen))
    )

    items = await connector.fetch(_source())
    doc = next(i for i in items if i.external_id == "file-doc-1")
    assert doc.content == "Idempotency key rollout plan (application/vnd.google-apps.document)"


async def test_content_fetch_cap_falls_back_beyond_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("context_engine.connectors.live.gdrive._MAX_CONTENT_FETCHES", 0)
    seen: dict = {}
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler(seen=seen)))

    items = await connector.fetch(_source())

    doc = next(i for i in items if i.external_id == "file-doc-1")
    assert doc.content == "Idempotency key rollout plan (application/vnd.google-apps.document)"
    assert "export_calls" not in seen
    assert "media_calls" not in seen


async def test_401_on_files_list_raises_auth_error() -> None:
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler(files_status=401)))
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_source())


async def test_malformed_file_entry_skipped() -> None:
    connector = GDriveLiveConnector(transport=httpx.MockTransport(_make_handler()))
    items = await connector.fetch(_source())
    assert all(i.external_id for i in items)
    assert len(items) == 3
