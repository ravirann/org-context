"""Eval endpoints: list, detail, run enqueue, golden tasks."""

from __future__ import annotations

from sqlalchemy import select

from context_engine.storage.models import EvalRun, EvalRunStatus


async def test_list_shape(api_client: object) -> None:
    r = await api_client.get("/v1/evals?page=1")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] >= 1
    item = body["items"][0]
    for key in ("id", "mode", "status", "started_at", "finished_at", "summary"):
        assert key in item


async def test_detail_shape(api_client: object, seeded_session: object) -> None:
    run = (
        (
            await seeded_session.execute(select(EvalRun))  # type: ignore[attr-defined]
        )
        .scalars()
        .first()
    )
    r = await api_client.get(f"/v1/evals/{run.id}")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert "results" in body and "golden_tasks_total" in body
    assert body["golden_tasks_total"] >= 1
    for res in body["results"]:
        for key in (
            "task_name",
            "mode",
            "score",
            "passed",
            "explanation",
            "tokens_used",
            "details",
        ):
            assert key in res
        # task_name resolved via join.
        assert res["task_name"]


async def test_golden_tasks(api_client: object) -> None:
    r = await api_client.get("/v1/evals/golden-tasks")  # type: ignore[attr-defined]
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body["items"]
    task = body["items"][0]
    for key in ("id", "name", "task", "repo", "service", "is_active", "expected_keywords"):
        assert key in task


async def test_run_enqueues(
    api_client: object, seeded_session: object, monkeypatch: object
) -> None:
    calls: list[tuple] = []

    from context_engine.api.routes import evals as evals_route

    def _fake_send(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((args, kwargs))

    monkeypatch.setattr(  # type: ignore[attr-defined]
        evals_route.run_eval_actor, "send", _fake_send
    )

    r = await api_client.post(  # type: ignore[attr-defined]
        "/v1/evals/run", json={"mode": "comparison"}
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "running"
    assert "eval_run_id" in body

    # A message was enqueued with the new run id and mode.
    assert len(calls) == 1
    args, _ = calls[0]
    assert args[0] == body["eval_run_id"]
    assert args[1] == "comparison"

    # And a running EvalRun row was persisted.
    run = await seeded_session.get(EvalRun, __import__("uuid").UUID(body["eval_run_id"]))  # type: ignore[attr-defined]
    assert run is not None
    assert run.status == EvalRunStatus.running


async def test_detail_404(api_client: object) -> None:
    r = await api_client.get(  # type: ignore[attr-defined]
        "/v1/evals/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404
