"""Agent run endpoints: list (filters/pagination) and detail."""

from __future__ import annotations

from sqlalchemy import select

from context_engine.storage.models import AgentRun


async def test_list_shape(api_client: object) -> None:
    r = await api_client.get("/v1/agent-runs?page=1&page_size=10")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 2
    item = body["items"][0]
    for key in (
        "id",
        "agent_name",
        "task",
        "user_name",
        "status",
        "started_at",
        "finished_at",
        "context_packet_id",
    ):
        assert key in item


async def test_list_status_filter(api_client: object) -> None:
    body = (
        await api_client.get("/v1/agent-runs?status=failed")  # type: ignore[attr-defined]
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "failed"


async def test_list_agent_filter(api_client: object) -> None:
    body = (
        await api_client.get("/v1/agent-runs?agent=claude-code")  # type: ignore[attr-defined]
    ).json()
    assert all(i["agent_name"] == "claude-code" for i in body["items"])


async def test_detail_shape(api_client: object, seeded_session: object) -> None:
    run = (
        (
            await seeded_session.execute(  # type: ignore[attr-defined]
                select(AgentRun).where(AgentRun.status == "succeeded")
            )
        )
        .scalars()
        .first()
    )
    r = await api_client.get(f"/v1/agent-runs/{run.id}")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    for key in (
        "plan",
        "changed_files",
        "test_output",
        "pr_url",
        "reviewer_comments",
        "langfuse_trace_url",
        "context_packet",
    ):
        assert key in body
    # This run has an embedded context packet.
    assert body["context_packet"] is not None
    assert body["context_packet"]["id"] == str(run.context_packet_id)
    # No Langfuse configured -> trace url is null.
    assert body["langfuse_trace_url"] is None


async def test_detail_no_packet(api_client: object, seeded_session: object) -> None:
    run = (
        (
            await seeded_session.execute(  # type: ignore[attr-defined]
                select(AgentRun).where(AgentRun.status == "failed")
            )
        )
        .scalars()
        .first()
    )
    body = (await api_client.get(f"/v1/agent-runs/{run.id}")).json()  # type: ignore[attr-defined]
    assert body["context_packet"] is None


async def test_detail_404(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/agent-runs/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404
