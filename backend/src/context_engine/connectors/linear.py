"""Offline demo Linear connector: issue tracker tickets with states and teams."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://linear.app/demo/issue"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="ENG-142",
            doc_type="ticket",
            title="ENG-142: Webhook retries cause duplicate charge notifications",
            content=(
                "Customers on the retry-heavy payments-api path are getting duplicate "
                "'payment received' notifications. Root cause is the webhook dispatcher "
                "re-sending on ack timeout without an idempotency key.\n\n"
                "Plan: add an event_id dedupe table before re-enabling fast retries."
            ),
            url=f"{_BASE}/ENG-142",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"state": "In Progress", "identifier": "ENG-142", "labels": ["bug"]},
            last_activity_at=demo_timestamp(9),
        ),
        RawItem(
            external_id="ENG-158",
            doc_type="ticket",
            title="ENG-158: Search latency spikes correlate with cache eviction",
            content=(
                "p95 latency on search-svc spikes every ~40 minutes, lining up with LRU "
                "cache eviction on the query-plan cache. Increasing cache size masks it "
                "but doesn't fix the underlying churn.\n\n"
                "Next: profile which query shapes are evicting each other."
            ),
            url=f"{_BASE}/ENG-158",
            author_email="jade@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            metadata={"state": "In Progress", "identifier": "ENG-158", "labels": ["performance"]},
            last_activity_at=demo_timestamp(18),
        ),
        RawItem(
            external_id="ENG-163",
            doc_type="ticket",
            title="ENG-163: Rotate billing-worker provider credentials",
            content=(
                "Quarterly credential rotation for the payment provider keys used by "
                "billing-worker. Follow the vault runbook; stagger rotation so in-flight "
                "invoice batches drain first.\n\nBlocked on finance sign-off for sandbox keys."
            ),
            url=f"{_BASE}/ENG-163",
            author_email="nina@demo.dev",
            repo="billing-worker",
            service="billing-worker",
            team_name="Payments",
            metadata={"state": "Blocked", "identifier": "ENG-163", "labels": ["security"]},
            last_activity_at=demo_timestamp(60),
        ),
        RawItem(
            external_id="ENG-171",
            doc_type="ticket",
            title="ENG-171: Quarantine flaky test_day_batches in data-pipeline CI",
            content=(
                "tests/test_backfill.py::test_day_batches fails roughly one night in five "
                "on a batch-boundary off-by-one. Suspect timezone handling in the "
                "events_raw partitioning helper.\n\nQuarantined pending a deterministic "
                "clock fixture."
            ),
            url=f"{_BASE}/ENG-171",
            author_email="lena@demo.dev",
            repo="data-pipeline",
            service="data-pipeline",
            team_name="Data",
            metadata={"state": "Todo", "identifier": "ENG-171", "labels": ["ci", "flaky-test"]},
            last_activity_at=demo_timestamp(30),
        ),
        RawItem(
            external_id="ENG-176",
            doc_type="ticket",
            title="ENG-176: Proposal — batch mobile store submissions biweekly",
            content=(
                "App review overhead is crushing the Mobile team; proposal to move from "
                "the weekly release train (ADR-0044) to biweekly and batch store "
                "submissions.\n\nNeeds sign-off from Mobile and Growth leads; mobile-bff "
                "compatibility guarantees would stretch to four weeks."
            ),
            url=f"{_BASE}/ENG-176",
            author_email="kenji@demo.dev",
            repo="mobile-bff",
            service="mobile-bff",
            team_name="Mobile",
            topic_key="mobile-release-cadence",
            metadata={
                "state": "In Review",
                "identifier": "ENG-176",
                "stance": "biweekly",
                "labels": ["process"],
            },
            last_activity_at=demo_timestamp(20),
        ),
        RawItem(
            external_id="ENG-182",
            doc_type="ticket",
            title="ENG-182: notification_jobs backlog grows during business hours",
            content=(
                "The notifications outbox drains slower than it fills between 9am and "
                "noon. Backlog peaked at 40k jobs today.\n\nShort term: double worker "
                "concurrency. Long term: partition notification_jobs by priority so "
                "transactional email never sits behind marketing sends."
            ),
            url=f"{_BASE}/ENG-182",
            author_email="grace@demo.dev",
            repo="notifications",
            service="notifications",
            team_name="Platform",
            metadata={"state": "In Progress", "identifier": "ENG-182", "labels": ["capacity"]},
            last_activity_at=demo_timestamp(4),
        ),
        RawItem(
            external_id="ENG-189",
            doc_type="ticket",
            title="ENG-189: Remove deprecated new_checkout_flow flag from web-app",
            content=(
                "new_checkout_flow has been fully rolled out for two quarters. Remove the "
                "flag, the dead branch, and stale docs referencing the old checkout.\n\n"
                "Low risk; behind-the-flag code has no traffic."
            ),
            url=f"{_BASE}/ENG-189",
            author_email="felix@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"state": "Todo", "identifier": "ENG-189", "labels": ["cleanup"]},
            last_activity_at=demo_timestamp(140),
        ),
        RawItem(
            external_id="ENG-194",
            doc_type="ticket",
            title="ENG-194: Alert on payments-api connection pool saturation",
            content=(
                "During INC-2107 the pool sat above 90% for twenty minutes before anyone "
                "noticed. Add an alert when utilization stays above 80% for five minutes "
                "and page the Payments on-call.\n\nDashboards already expose the metric; "
                "this is alert wiring only."
            ),
            url=f"{_BASE}/ENG-194",
            author_email="omar@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"state": "Done", "identifier": "ENG-194", "labels": ["observability"]},
            last_activity_at=demo_timestamp(2),
        ),
    ]


class LinearConnector:
    """Deterministic demo connector for the ``linear`` source type."""

    source_type: ClassVar[str] = "linear"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's Linear issues (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(LinearConnector())
