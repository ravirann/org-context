"""Human-readable eval reports for the ``ctx eval`` CLI (pure string building)."""

from __future__ import annotations

from typing import Any

from context_engine.storage.models import EvalResult, EvalResultMode, EvalRun

_SUMMARY_KEYS = (
    "avg_score",
    "pass_rate",
    "total_tokens",
    "baseline_avg_score",
    "baseline_total_tokens",
)


def format_report(run: EvalRun, results: list[EvalResult]) -> str:
    """Render a comparison table plus summary block for an eval run.

    Results should have their ``eval_task`` relationship loaded so task names
    can be shown; otherwise the task id is used (no lazy loads are triggered).
    """
    by_task: dict[str, dict[EvalResultMode, EvalResult]] = {}
    for result in results:
        by_task.setdefault(_task_name(result), {})[EvalResultMode(result.mode)] = result

    lines = [
        f"Eval run {run.id} — mode={_enum_value(run.mode)} status={_enum_value(run.status)}",
        f"Started:  {_ts(run.started_at)}",
        f"Finished: {_ts(run.finished_at)}",
        "",
    ]
    lines.extend(_table_lines(by_task))
    lines.append("")
    lines.append("Summary:")
    summary = run.summary if isinstance(run.summary, dict) else {}
    for key in _SUMMARY_KEYS:
        if key in summary:
            lines.append(f"  {key}: {summary[key]}")
    if "error" in summary:
        lines.append(f"  error: {summary['error']}")

    if summary.get("regression"):
        regressed = summary.get("regressed_task_names") or []
        lines.append("")
        lines.append("!!! REGRESSION DETECTED !!!")
        lines.append(f"  regressed tasks: {', '.join(regressed) if regressed else '-'}")
    return "\n".join(lines)


def _table_lines(by_task: dict[str, dict[EvalResultMode, EvalResult]]) -> list[str]:
    if not by_task:
        return ["(no results)"]
    name_width = max(len("Task"), *(len(name) for name in by_task))
    header = (
        f"{'Task':<{name_width}} | {'Baseline':>14} | {'Engine':>14} | "
        f"{'Δ':>7} | {'Tokens (b/e)':>13}"
    )
    lines = [header, "-" * len(header)]
    for name in sorted(by_task):
        legs = by_task[name]
        baseline = legs.get(EvalResultMode.baseline)
        engine = legs.get(EvalResultMode.context_engine)
        lines.append(
            f"{name:<{name_width}} | {_leg_cell(baseline):>14} | {_leg_cell(engine):>14} | "
            f"{_delta_cell(baseline, engine):>7} | {_tokens_cell(baseline, engine):>13}"
        )
    return lines


def _task_name(result: EvalResult) -> str:
    # Read the relationship straight from __dict__ so an unloaded (lazy)
    # attribute never triggers I/O from this pure function.
    task = result.__dict__.get("eval_task")
    if task is not None:
        return str(task.name)
    return str(result.eval_task_id)


def _leg_cell(result: EvalResult | None) -> str:
    if result is None:
        return "-"
    verdict = "PASS" if result.passed else "FAIL"
    return f"{result.score:.3f} {verdict}"


def _delta_cell(baseline: EvalResult | None, engine: EvalResult | None) -> str:
    if baseline is None or engine is None:
        return "-"
    return f"{engine.score - baseline.score:+.3f}"


def _tokens_cell(baseline: EvalResult | None, engine: EvalResult | None) -> str:
    baseline_tokens = str(baseline.tokens_used) if baseline is not None else "-"
    engine_tokens = str(engine.tokens_used) if engine is not None else "-"
    return f"{baseline_tokens}/{engine_tokens}"


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _ts(value: Any) -> str:
    return value.isoformat() if value is not None else "-"
