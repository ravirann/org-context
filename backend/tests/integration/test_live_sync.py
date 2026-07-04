"""Integration tests: live-mode sync through the pipeline + sources API masking.

Live connectors are exercised against the real test DB but with an injected
``httpx.MockTransport`` (no network). We monkeypatch the live connector's default
transport so ``get_connector(type, config)`` -> ``sync_source`` uses the mock.
"""

from __future__ import annotations

import base64

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import auth_headers

from context_engine.connectors.live import github as live_github
from context_engine.ingestion.pipeline import sync_source
from context_engine.storage import models as m

_PR_STATE = {"updated_at": "2026-07-01T10:00:00Z"}


def _github_transport() -> httpx.MockTransport:
    readme = base64.b64encode(b"# payments-api\n\nDocs.").decode()

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path == "/repos/acme/payments-api":
            return httpx.Response(200, json={"private": True}, request=req)
        if path == "/repos/acme/payments-api/pulls":
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 801,
                        "title": "add idempotency keys",
                        "body": "Enforce Idempotency-Key on charge.",
                        "html_url": "https://github.com/acme/payments-api/pull/801",
                        "state": "open",
                        "user": {"email": "priya@demo.dev"},
                        "labels": [{"name": "api"}],
                        "updated_at": _PR_STATE["updated_at"],
                    }
                ],
                request=req,
            )
        if path == "/repos/acme/payments-api/pulls/801/comments":
            return httpx.Response(200, json=[], request=req)
        if path == "/repos/acme/payments-api/issues":
            return httpx.Response(200, json=[], request=req)
        if path == "/repos/acme/payments-api/contents/README.md":
            return httpx.Response(
                200,
                json={
                    "encoding": "base64",
                    "content": readme,
                    "html_url": "https://github.com/acme/payments-api/blob/main/README.md",
                },
                request=req,
            )
        return httpx.Response(404, json={}, request=req)

    return httpx.MockTransport(handler)


def _install_transport(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    """Force GitHubLiveConnector instances to use the given transport."""
    original_init = live_github.GitHubLiveConnector.__init__

    def patched_init(self: object, _transport: object = None) -> None:
        original_init(self, transport)  # type: ignore[arg-type]

    monkeypatch.setattr(live_github.GitHubLiveConnector, "__init__", patched_init)


async def _make_live_github(session: AsyncSession) -> m.Source:
    source = m.Source(
        type=m.SourceType.github,
        name="GitHub Live (acme)",
        enabled=True,
        config={
            "mode": "live",
            "token": "ghp_livesecret",
            "org": "acme",
            "repos": ["payments-api"],
            "team_name": "Payments",
        },
        sync_state={},
        authority_rank=70,
        freshness_window_days=90,
    )
    session.add(source)
    await session.flush()
    return source


async def test_live_sync_creates_docs_and_persists_cursor(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_transport(monkeypatch, _github_transport())
    source = await _make_live_github(seeded_session)

    count = await sync_source(seeded_session, source)
    assert count >= 2  # PR + README doc
    assert source.sync_status == m.SyncStatus.ok
    assert source.last_error is None

    docs = (
        (await seeded_session.execute(select(m.Document).where(m.Document.source_id == source.id)))
        .scalars()
        .all()
    )
    by_id = {d.external_id: d for d in docs}
    assert "pr-801" in by_id
    pr = by_id["pr-801"]
    # private repo -> team-restricted ACL, resolved to the seeded Payments team id
    payments_id = (
        await seeded_session.execute(select(m.Team.id).where(m.Team.name == "Payments"))
    ).scalar_one()
    assert pr.acl_public is False
    assert pr.acl_team_ids == [str(payments_id)]

    chunk_count = (
        await seeded_session.execute(
            select(func.count())
            .select_from(m.Chunk)
            .join(m.Document, m.Document.id == m.Chunk.document_id)
            .where(m.Document.source_id == source.id, m.Chunk.embedding.is_not(None))
        )
    ).scalar_one()
    assert chunk_count >= count

    # cursor persisted: re-read a fresh Source row from the DB
    reread = await seeded_session.get(m.Source, source.id)
    assert reread is not None
    assert reread.sync_state.get("pr_cursor") == "2026-07-01T10:00:00+00:00"


async def test_live_resync_empty_delta_no_new_docs(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_transport(monkeypatch, _github_transport())
    source = await _make_live_github(seeded_session)

    first = await sync_source(seeded_session, source)
    cursor_after_first = source.sync_state.get("pr_cursor")

    docs_before = (
        await seeded_session.execute(
            select(func.count()).select_from(m.Document).where(m.Document.source_id == source.id)
        )
    ).scalar_one()

    # Second sync: same PR (updated_at unchanged) is now <= cursor -> skipped.
    second = await sync_source(seeded_session, source)
    docs_after = (
        await seeded_session.execute(
            select(func.count()).select_from(m.Document).where(m.Document.source_id == source.id)
        )
    ).scalar_one()

    assert docs_after == docs_before  # no new documents
    assert second <= first  # PR filtered out on the second pass
    # cursor did not regress
    assert source.sync_state.get("pr_cursor") == cursor_after_first


async def test_live_sync_auth_failure_marks_error_and_keeps_cursor(
    seeded_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth_transport = httpx.MockTransport(
        lambda req: httpx.Response(401, json={"message": "Bad credentials"}, request=req)
    )
    _install_transport(monkeypatch, auth_transport)
    source = await _make_live_github(seeded_session)
    source.sync_state = {"pr_cursor": "2026-06-01T00:00:00+00:00"}
    await seeded_session.flush()

    count = await sync_source(seeded_session, source)

    assert count == 0
    assert source.sync_status == m.SyncStatus.error
    assert source.last_error is not None
    assert "authentication failed" in source.last_error.lower()
    # sync_state unchanged (cursor not advanced on failure)
    assert source.sync_state == {"pr_cursor": "2026-06-01T00:00:00+00:00"}


# --------------------------------------------------------------------------- #
# Sources API: masking + PATCH sentinel handling                              #
# --------------------------------------------------------------------------- #


async def test_sources_api_get_masks_token(
    api_client: object, seeded_session: AsyncSession
) -> None:
    source = m.Source(
        type=m.SourceType.github,
        name="GH Masked",
        config={"mode": "live", "token": "ghp_supersecret9999", "org": "acme"},
    )
    seeded_session.add(source)
    await seeded_session.flush()

    r = await api_client.get("/v1/sources")  # type: ignore[attr-defined]
    assert r.status_code == 200
    match = next(s for s in r.json()["items"] if s["name"] == "GH Masked")
    assert match["config"]["token"] == "•••9999"
    assert match["config"]["org"] == "acme"
    assert "sync_state" in match


async def test_sources_api_patch_masked_sentinel_preserves_secret(
    api_client: object, seeded_session: AsyncSession
) -> None:
    source = m.Source(
        type=m.SourceType.github,
        name="GH Patch",
        config={"mode": "live", "token": "ghp_keepme12345", "org": "acme"},
    )
    seeded_session.add(source)
    await seeded_session.flush()

    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}",
        json={"config": {"mode": "live", "token": "•••2345", "org": "newco"}},
    )
    assert r.status_code == 200
    assert r.json()["config"]["org"] == "newco"

    refreshed = await seeded_session.get(m.Source, source.id)
    assert refreshed is not None
    assert refreshed.config["token"] == "ghp_keepme12345"  # preserved
    assert refreshed.config["org"] == "newco"


async def test_sources_api_patch_new_secret_replaces(
    api_client: object, seeded_session: AsyncSession
) -> None:
    source = m.Source(
        type=m.SourceType.github,
        name="GH Rotate",
        config={"mode": "live", "token": "ghp_oldtoken", "org": "acme"},
    )
    seeded_session.add(source)
    await seeded_session.flush()

    r = await api_client.patch(  # type: ignore[attr-defined]
        f"/v1/sources/{source.id}",
        json={"config": {"mode": "live", "token": "ghp_newrotated", "org": "acme"}},
        headers=auth_headers(),
    )
    assert r.status_code == 200

    refreshed = await seeded_session.get(m.Source, source.id)
    assert refreshed is not None
    assert refreshed.config["token"] == "ghp_newrotated"
