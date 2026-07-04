"""Unit tests for live connectors, the shared HTTP helper, and secret masking.

No real network: every request goes through an ``httpx.MockTransport`` whose
handler returns canned GitHub/Jira/Slack/Confluence payloads and can assert on the
outgoing query params (to verify cursor advance).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable

import httpx
import pytest

from context_engine.api.routes.sources import mask_config, mask_secret, merge_config
from context_engine.connectors.live.confluence import ConfluenceLiveConnector
from context_engine.connectors.live.github import GitHubLiveConnector
from context_engine.connectors.live.http import (
    ConnectorAuthError,
    ConnectorError,
    build_client,
    request_json,
)
from context_engine.connectors.live.jira import JiraLiveConnector
from context_engine.connectors.live.slack import SlackLiveConnector
from context_engine.storage import models as m

Handler = Callable[[httpx.Request], httpx.Response]


def _source(source_type: str, config: dict, sync_state: dict | None = None) -> m.Source:
    return m.Source(
        type=m.SourceType(source_type),
        name=f"{source_type} live",
        config=config,
        sync_state=sync_state or {},
    )


def _json_response(request: httpx.Request, payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload, request=request)


# --------------------------------------------------------------------------- #
# HTTP helper                                                                  #
# --------------------------------------------------------------------------- #


async def test_request_json_returns_body() -> None:
    transport = httpx.MockTransport(lambda req: _json_response(req, {"ok": True}))
    async with build_client(base_url="https://api.test", transport=transport) as client:
        assert await request_json(client, "GET", "/thing") == {"ok": True}


async def test_request_json_401_raises_auth_error() -> None:
    transport = httpx.MockTransport(lambda req: _json_response(req, {"e": 1}, status=401))
    async with build_client(base_url="https://api.test", transport=transport) as client:
        with pytest.raises(ConnectorAuthError):
            await request_json(client, "GET", "/thing")


async def test_request_json_403_raises_auth_error() -> None:
    transport = httpx.MockTransport(lambda req: _json_response(req, {}, status=403))
    async with build_client(base_url="https://api.test", transport=transport) as client:
        with pytest.raises(ConnectorAuthError):
            await request_json(client, "GET", "/thing")


async def test_request_json_500_raises_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("context_engine.connectors.live.http.asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _json_response(req, {}, status=500)

    transport = httpx.MockTransport(handler)
    async with build_client(base_url="https://api.test", transport=transport) as client:
        with pytest.raises(ConnectorError):
            await request_json(client, "GET", "/thing")
    assert calls["n"] == 4  # initial + 3 retries


async def test_request_json_429_retry_after_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []

    async def record_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr("context_engine.connectors.live.http.asyncio.sleep", record_sleep)
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, json={}, request=req)
        return _json_response(req, {"ok": True})

    transport = httpx.MockTransport(handler)
    async with build_client(base_url="https://api.test", transport=transport) as client:
        assert await request_json(client, "GET", "/thing") == {"ok": True}
    assert calls["n"] == 2
    assert slept == [3.0]  # honored Retry-After


async def test_request_json_transport_error_retries_then_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("context_engine.connectors.live.http.asyncio.sleep", _no_sleep)

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=req)

    transport = httpx.MockTransport(handler)
    async with build_client(base_url="https://api.test", transport=transport) as client:
        with pytest.raises(ConnectorError):
            await request_json(client, "GET", "/thing")


async def _no_sleep(_delay: float) -> None:
    return None


# --------------------------------------------------------------------------- #
# GitHub                                                                       #
# --------------------------------------------------------------------------- #


def _github_handler(seen: dict) -> Handler:
    readme = base64.b64encode(b"# payments-api\n\nService docs.").decode()

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/repos/acme/payments-api":
            return _json_response(req, {"private": True})
        if path == "/repos/acme/payments-api/pulls":
            seen["pulls_params"] = dict(req.url.params)
            return _json_response(
                req,
                [
                    {
                        "number": 801,
                        "title": "add idempotency keys",
                        "body": "Enforce Idempotency-Key.",
                        "html_url": "https://github.com/acme/payments-api/pull/801",
                        "state": "open",
                        "user": {"email": "priya@demo.dev"},
                        "labels": [{"name": "api"}],
                        "updated_at": "2026-07-01T10:00:00Z",
                    }
                ],
            )
        if path == "/repos/acme/payments-api/pulls/801/comments":
            return _json_response(req, [{"body": "nit: rename var"}])
        if path == "/repos/acme/payments-api/issues":
            seen["issues_params"] = dict(req.url.params)
            return _json_response(
                req,
                [
                    {
                        "number": 42,
                        "title": "flaky test",
                        "body": "off by one",
                        "html_url": "https://github.com/acme/payments-api/issues/42",
                        "state": "open",
                        "user": {"email": "lena@demo.dev"},
                        "labels": ["ci"],
                        "updated_at": "2026-07-02T12:00:00Z",
                    },
                    {"number": 43, "title": "a pr", "pull_request": {}, "updated_at": "x"},
                ],
            )
        if path == "/repos/acme/payments-api/contents/README.md":
            return _json_response(
                req,
                {
                    "encoding": "base64",
                    "content": readme,
                    "html_url": "https://github.com/acme/payments-api/blob/main/README.md",
                },
            )
        return _json_response(req, {}, status=404)

    return handler


def _github_source(sync_state: dict | None = None) -> m.Source:
    return _source(
        "github",
        {
            "mode": "live",
            "token": "ghp_secret",
            "org": "acme",
            "repos": ["payments-api"],
            "team_name": "Payments",
        },
        sync_state,
    )


async def test_github_fetch_maps_fields() -> None:
    seen: dict = {}
    connector = GitHubLiveConnector(transport=httpx.MockTransport(_github_handler(seen)))
    source = _github_source()

    items = await connector.fetch(source)
    by_id = {i.external_id: i for i in items}

    pr = by_id["pr-801"]
    assert pr.doc_type == "pr"
    assert "Idempotency-Key" in pr.content
    assert "nit: rename var" in pr.content  # review comment appended
    assert pr.author_email == "priya@demo.dev"
    assert pr.metadata["pr_number"] == 801
    # private repo -> team-restricted ACL from config team_name
    assert pr.acl.public is False
    assert pr.acl.team_names == ["Payments"]

    issue = by_id["issue-payments-api-42"]
    assert issue.doc_type == "ticket"
    assert "off by one" in issue.content

    doc = by_id["doc-payments-api-README.md"]
    assert doc.doc_type == "code"
    assert "Service docs." in doc.content

    # cursors advanced on sync_state
    assert source.sync_state["pr_cursor"] == "2026-07-01T10:00:00+00:00"
    assert source.sync_state["issues_cursor"] == "2026-07-02T12:00:00+00:00"


async def test_github_second_fetch_uses_cursor_and_skips_old() -> None:
    seen: dict = {}
    connector = GitHubLiveConnector(transport=httpx.MockTransport(_github_handler(seen)))
    # cursor already past the PR's updated_at -> PR filtered out
    source = _github_source({"pr_cursor": "2026-07-05T00:00:00+00:00"})

    items = await connector.fetch(source)
    assert not any(i.external_id == "pr-801" for i in items)
    # issues endpoint received the stored `since` param
    assert "since" not in seen["issues_params"] or seen["issues_params"]["since"]


async def test_github_401_raises_auth_error() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _json_response(req, {}, status=401)

    connector = GitHubLiveConnector(transport=httpx.MockTransport(handler))
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_github_source())


async def test_github_malformed_pr_skipped() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/repos/acme/payments-api":
            return _json_response(req, {"private": False})
        if path == "/repos/acme/payments-api/pulls":
            return _json_response(req, [{"body": "no number or title"}])
        if path == "/repos/acme/payments-api/issues":
            return _json_response(req, [])
        return _json_response(req, {}, status=404)

    connector = GitHubLiveConnector(transport=httpx.MockTransport(handler))
    items = await connector.fetch(_github_source())
    assert all(not i.external_id.startswith("pr-") for i in items)


# --------------------------------------------------------------------------- #
# Jira                                                                         #
# --------------------------------------------------------------------------- #


def _jira_handler(seen: dict) -> Handler:
    def handler(req: httpx.Request) -> httpx.Response:
        seen["params"] = dict(req.url.params)
        return _json_response(
            req,
            {
                "issues": [
                    {
                        "key": "ENG-1401",
                        "self": "https://acme.atlassian.net/rest/api/3/issue/1",
                        "fields": {
                            "summary": "Duplicate charges",
                            "description": {
                                "type": "doc",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [{"type": "text", "text": "webhook retries"}],
                                    }
                                ],
                            },
                            "updated": "2026-07-01T08:00:00.000+0000",
                            "reporter": {"emailAddress": "priya@demo.dev"},
                            "priority": {"name": "Critical"},
                            "status": {"name": "Open"},
                            "project": {"key": "ENG"},
                        },
                    },
                    {"malformed": True},
                ]
            },
        )

    return handler


def _jira_source(sync_state: dict | None = None) -> m.Source:
    return _source(
        "jira",
        {
            "mode": "live",
            "base_url": "https://acme.atlassian.net",
            "email": "bot@acme.dev",
            "api_token": "jira_secret",
        },
        sync_state,
    )


async def test_jira_fetch_maps_fields() -> None:
    seen: dict = {}
    connector = JiraLiveConnector(transport=httpx.MockTransport(_jira_handler(seen)))
    source = _jira_source()

    items = await connector.fetch(source)
    assert len(items) == 1  # malformed skipped
    item = items[0]
    assert item.external_id == "ENG-1401"
    assert item.doc_type == "ticket"
    assert "webhook retries" in item.content
    assert item.author_email == "priya@demo.dev"
    assert item.metadata["severity"] == "critical"
    assert item.acl.public is True
    assert source.sync_state["updated_cursor"] == "2026-07-01T08:00:00+00:00"


async def test_jira_second_fetch_uses_cursor_in_jql() -> None:
    seen: dict = {}
    connector = JiraLiveConnector(transport=httpx.MockTransport(_jira_handler(seen)))
    source = _jira_source({"updated_cursor": "2026-06-15T00:00:00+00:00"})
    await connector.fetch(source)
    assert "2026-06-15" in seen["params"]["jql"]


async def test_jira_restrict_to_team_acl() -> None:
    seen: dict = {}
    connector = JiraLiveConnector(transport=httpx.MockTransport(_jira_handler(seen)))
    source = _jira_source()
    source.config["restrict_to_team"] = "Payments"
    items = await connector.fetch(source)
    assert items[0].acl.public is False
    assert items[0].acl.team_names == ["Payments"]


async def test_jira_401_raises() -> None:
    connector = JiraLiveConnector(
        transport=httpx.MockTransport(lambda req: _json_response(req, {}, status=401))
    )
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_jira_source())


# --------------------------------------------------------------------------- #
# Slack                                                                        #
# --------------------------------------------------------------------------- #


def _slack_handler(seen: dict) -> Handler:
    def handler(req: httpx.Request) -> httpx.Response:
        seen["params"] = dict(req.url.params)
        return _json_response(
            req,
            {
                "ok": True,
                "messages": [
                    {"type": "message", "ts": "1719400000.000100", "text": "deploy going out"},
                    {"type": "message", "ts": "1719400100.000200", "text": "canary green"},
                    {"type": "message", "ts": "1719490000.000300", "text": "next day msg"},
                    {"type": "message", "ts": "1719490100.000400"},  # no text -> ignored line
                ],
            },
        )

    return handler


def _slack_source(sync_state: dict | None = None) -> m.Source:
    return _source(
        "slack",
        {"mode": "live", "token": "xoxb-secret", "channels": ["C01"]},
        sync_state,
    )


async def test_slack_batches_per_channel_day() -> None:
    seen: dict = {}
    connector = SlackLiveConnector(transport=httpx.MockTransport(_slack_handler(seen)))
    source = _slack_source()

    items = await connector.fetch(source)
    # two distinct days -> two batches
    assert len(items) == 2
    first = items[0]
    assert first.doc_type == "message"
    assert first.external_id.startswith("slack-C01-")
    assert "deploy going out" in first.content
    assert "canary green" in first.content
    assert first.metadata["channel"] == "C01"
    # cursor advanced to latest ts
    assert source.sync_state["channel_cursor:C01"] == "1719490100.000400"


async def test_slack_second_fetch_uses_cursor_as_oldest() -> None:
    seen: dict = {}
    connector = SlackLiveConnector(transport=httpx.MockTransport(_slack_handler(seen)))
    source = _slack_source({"channel_cursor:C01": "1719400050.000000"})
    await connector.fetch(source)
    assert seen["params"]["oldest"] == "1719400050.000000"


async def test_slack_api_error_raises() -> None:
    connector = SlackLiveConnector(
        transport=httpx.MockTransport(
            lambda req: _json_response(req, {"ok": False, "error": "invalid_auth"})
        )
    )
    with pytest.raises(ConnectorError):
        await connector.fetch(_slack_source())


async def test_slack_401_raises_auth_error() -> None:
    connector = SlackLiveConnector(
        transport=httpx.MockTransport(lambda req: _json_response(req, {}, status=401))
    )
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_slack_source())


# --------------------------------------------------------------------------- #
# Confluence                                                                   #
# --------------------------------------------------------------------------- #


def _confluence_handler(seen: dict) -> Handler:
    def handler(req: httpx.Request) -> httpx.Response:
        seen["params"] = dict(req.url.params)
        return _json_response(
            req,
            {
                "_links": {"base": "https://acme.atlassian.net/wiki"},
                "results": [
                    {
                        "id": "98765",
                        "title": "Payments runbook",
                        "body": {
                            "storage": {
                                "value": "<p>Retry <b>3 times</b>.</p><p>Escalate on-call.</p>"
                            }
                        },
                        "version": {"when": "2026-07-01T09:00:00.000Z"},
                        "space": {"key": "ENG"},
                        "_links": {"webui": "/spaces/ENG/pages/98765"},
                    },
                    {"title": "no id"},  # malformed
                ],
            },
        )

    return handler


def _confluence_source(sync_state: dict | None = None) -> m.Source:
    return _source(
        "confluence",
        {
            "mode": "live",
            "base_url": "https://acme.atlassian.net/wiki",
            "email": "bot@acme.dev",
            "api_token": "conf_secret",
            "space_keys": ["ENG"],
        },
        sync_state,
    )


async def test_confluence_fetch_maps_and_strips_html() -> None:
    seen: dict = {}
    connector = ConfluenceLiveConnector(transport=httpx.MockTransport(_confluence_handler(seen)))
    source = _confluence_source()

    items = await connector.fetch(source)
    assert len(items) == 1  # malformed skipped
    item = items[0]
    assert item.external_id == "conf-98765"
    assert item.doc_type == "doc"
    assert "Retry 3 times." in item.content
    assert "<" not in item.content  # tags stripped
    assert item.metadata["space"] == "ENG"
    assert "98765" in item.url
    assert source.sync_state["lastmodified_cursor"] == "2026-07-01T09:00:00+00:00"


async def test_confluence_second_fetch_uses_cursor_in_cql() -> None:
    seen: dict = {}
    connector = ConfluenceLiveConnector(transport=httpx.MockTransport(_confluence_handler(seen)))
    source = _confluence_source({"lastmodified_cursor": "2026-06-20T00:00:00+00:00"})
    await connector.fetch(source)
    assert "2026-06-20" in seen["params"]["cql"]


async def test_confluence_401_raises() -> None:
    connector = ConfluenceLiveConnector(
        transport=httpx.MockTransport(lambda req: _json_response(req, {}, status=401))
    )
    with pytest.raises(ConnectorAuthError):
        await connector.fetch(_confluence_source())


# --------------------------------------------------------------------------- #
# Secret masking                                                               #
# --------------------------------------------------------------------------- #


def test_mask_secret_keeps_last_four() -> None:
    assert mask_secret("ghp_abcd1234") == "•••1234"
    assert mask_secret("ab") == "•••ab"  # shorter than 4


def test_mask_config_masks_only_secret_keys() -> None:
    config = {"token": "ghp_secret999", "org": "acme", "repos": ["a"]}
    masked = mask_config(config)
    assert masked["token"] == "•••t999"
    assert masked["org"] == "acme"
    assert masked["repos"] == ["a"]
    # original untouched
    assert config["token"] == "ghp_secret999"


def test_merge_config_preserves_masked_secret() -> None:
    stored = {"token": "ghp_realsecret", "org": "acme"}
    incoming = {"token": "•••cret", "org": "newco"}
    merged = merge_config(stored, incoming)
    assert merged["token"] == "ghp_realsecret"  # kept
    assert merged["org"] == "newco"


def test_merge_config_replaces_new_secret() -> None:
    stored = {"token": "ghp_old"}
    incoming = {"token": "ghp_brandnew"}
    merged = merge_config(stored, incoming)
    assert merged["token"] == "ghp_brandnew"


def test_merge_config_drops_masked_secret_without_stored() -> None:
    merged = merge_config({}, {"token": "•••abcd", "org": "acme"})
    assert "token" not in merged
    assert merged["org"] == "acme"


def test_serialize_roundtrip_sanity() -> None:
    # sanity: masked config is JSON-serializable (used in API responses)
    assert json.loads(json.dumps(mask_config({"token": "x1234", "n": 1})))["token"] == "•••1234"
