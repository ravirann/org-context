"""Offline demo Jira connector: engineering tickets with severities."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://jira.demo.dev/browse"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="ENG-1401",
            doc_type="ticket",
            title="Two merchants report duplicate charges after webhook retries",
            content=(
                "Two merchants report duplicate charges within minutes of each other. Both "
                "correlate with a webhook retry storm on payments-api.\n\n"
                "Reproduction: replay the same provider event twice without an event_id "
                "dedupe. Fix tracked in PR #803; interim mitigation is pausing provider "
                "retries via the strict_idempotency flag."
            ),
            url=f"{_BASE}/ENG-1401",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"severity": "critical", "labels": ["payments", "bug"]},
            last_activity_at=demo_timestamp(14),
        ),
        RawItem(
            external_id="ENG-1405",
            doc_type="ticket",
            title="Investigate p95 latency regression on search-svc",
            content=(
                "p95 on GET /v1/search rose from 240ms to 800ms after last Tuesday's "
                "deploy. Profiling points at an N+1 query against search_index.\n\n"
                "Plan: batch the lookups, add a covering index, and confirm with a load "
                "test before re-enabling the search_rerank flag."
            ),
            url=f"{_BASE}/ENG-1405",
            author_email="jade@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            metadata={"severity": "high", "labels": ["performance"]},
            last_activity_at=demo_timestamp(22),
        ),
        RawItem(
            external_id="ENG-1412",
            doc_type="ticket",
            title="Rotate payment provider credentials for billing-worker",
            content=(
                "Quarterly rotation of the provider API keys used by billing-worker. "
                "Follow the vault runbook and stagger the rotation so in-flight invoice "
                "batches drain first.\n\nBlocked on finance sign-off for the sandbox keys."
            ),
            url=f"{_BASE}/ENG-1412",
            author_email="nina@demo.dev",
            repo="billing-worker",
            service="billing-worker",
            team_name="Payments",
            metadata={"severity": "medium", "labels": ["security", "ops"]},
            last_activity_at=demo_timestamp(70),
        ),
        RawItem(
            external_id="ENG-1418",
            doc_type="ticket",
            title="Flaky nightly test in data-pipeline CI",
            content=(
                "tests/test_backfill.py::test_day_batches fails roughly one night in five "
                "with an off-by-one on the batch boundary. Suspect timezone handling in "
                "the events_raw partitioning helper.\n\n"
                "Quarantined the test; needs a deterministic clock fixture."
            ),
            url=f"{_BASE}/ENG-1418",
            author_email="lena@demo.dev",
            repo="data-pipeline",
            service="data-pipeline",
            team_name="Data",
            metadata={"severity": "low", "labels": ["ci", "flaky-test"]},
            last_activity_at=demo_timestamp(35),
        ),
        RawItem(
            external_id="ENG-1422",
            doc_type="ticket",
            title="Proposal: move mobile releases to a biweekly train",
            content=(
                "App review overhead is crushing the Mobile team; proposal to move from "
                "the weekly train (ADR-0044) to biweekly releases and batch store "
                "submissions.\n\n"
                "Needs sign-off from the Mobile and Growth leads before changing the "
                "train schedule; mobile-bff compatibility guarantees would stretch to "
                "four weeks."
            ),
            url=f"{_BASE}/ENG-1422",
            author_email="kenji@demo.dev",
            repo="mobile-bff",
            service="mobile-bff",
            team_name="Mobile",
            topic_key="mobile-release-cadence",
            metadata={"severity": "medium", "stance": "biweekly", "labels": ["process"]},
            last_activity_at=demo_timestamp(25),
        ),
        RawItem(
            external_id="ENG-1427",
            doc_type="ticket",
            title="notification_jobs backlog growing during business hours",
            content=(
                "The notifications outbox drains slower than it fills between 9am and "
                "noon. Backlog peaked at 40k jobs today.\n\n"
                "Short term: double the worker concurrency. Long term: partition "
                "notification_jobs by priority so transactional email is never stuck "
                "behind marketing sends."
            ),
            url=f"{_BASE}/ENG-1427",
            author_email="grace@demo.dev",
            repo="notifications",
            service="notifications",
            team_name="Platform",
            metadata={"severity": "high", "labels": ["capacity"]},
            last_activity_at=demo_timestamp(5),
        ),
        RawItem(
            external_id="ENG-1430",
            doc_type="ticket",
            title="Clean up the deprecated new_checkout_flow flag in web-app",
            content=(
                "new_checkout_flow has been fully rolled out for two quarters. Remove the "
                "flag, the dead branch, and the stale docs that still reference the old "
                "checkout.\n\nLow risk; behind-the-flag code has no traffic."
            ),
            url=f"{_BASE}/ENG-1430",
            author_email="felix@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"severity": "low", "labels": ["cleanup", "feature-flags"]},
            last_activity_at=demo_timestamp(160),
        ),
        RawItem(
            external_id="ENG-1433",
            doc_type="ticket",
            title="Add alerting for payments-api connection pool saturation",
            content=(
                "During INC-2107 the pool sat above 90% for twenty minutes before anyone "
                "noticed. Add an alert when utilization stays above 80% for five minutes "
                "and page the Payments on-call.\n\n"
                "Dashboards already expose the metric; this is alert wiring only."
            ),
            url=f"{_BASE}/ENG-1433",
            author_email="omar@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"severity": "high", "labels": ["observability"]},
            last_activity_at=demo_timestamp(3),
        ),
    ]


class JiraConnector:
    """Deterministic demo connector for the ``jira`` source type."""

    source_type: ClassVar[str] = "jira"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's tickets (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(JiraConnector())
