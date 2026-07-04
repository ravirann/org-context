"""Offline demo incident connector: postmortems with severity and causing service."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawAcl, RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://incidents.demo.dev"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="inc-2107",
            doc_type="incident",
            title="INC-2107: duplicate charges on payments-api",
            content=(
                "Summary: webhook retries without deduplication double-charged 214 "
                "merchants over 40 minutes.\n\n"
                "Root cause: fixed-interval retries synchronized load spikes and the "
                "handler wrote to the payments table before checking event_id.\n\n"
                "Remediation: exponential backoff with full jitter (ADR-0042), event_id "
                "dedupe before any write, and a pool-saturation alert. Raw customer "
                "impact numbers are restricted to the Payments team."
            ),
            url=f"{_BASE}/inc-2107",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            acl=RawAcl(public=False, team_names=["Payments"]),
            metadata={"severity": "sev1", "caused_by": "payments-api"},
            last_activity_at=demo_timestamp(55),
        ),
        RawItem(
            external_id="inc-2113",
            doc_type="incident",
            title="INC-2113: auth-service token verification outage",
            content=(
                "Summary: 22 minutes of elevated 401s across every service after a "
                "signing-key rotation.\n\n"
                "Root cause: downstream services cached the JWKS document for 24 hours "
                "instead of six, so the new key was unknown.\n\n"
                "Remediation: JWKS refresh timer enforced in the shared client; "
                "rotation runbook now includes a canary verification step."
            ),
            url=f"{_BASE}/inc-2113",
            author_email="marcus@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            metadata={"severity": "sev2", "caused_by": "auth-service"},
            last_activity_at=demo_timestamp(33),
        ),
        RawItem(
            external_id="inc-2118",
            doc_type="incident",
            title="INC-2118: webhook storm overwhelmed notifications",
            content=(
                "Summary: a provider replayed three hours of webhooks in five minutes; "
                "the notification_jobs backlog hit 120k and transactional email "
                "stalled.\n\n"
                "Root cause: no rate limit on the inbound webhook endpoint and a single "
                "shared queue for all priorities.\n\n"
                "Remediation: token-bucket rate limiting, priority partitioning of "
                "notification_jobs, and dead-lettering after 5 attempts."
            ),
            url=f"{_BASE}/inc-2118",
            author_email="grace@demo.dev",
            repo="notifications",
            service="notifications",
            team_name="Platform",
            metadata={"severity": "sev2", "caused_by": "notifications"},
            last_activity_at=demo_timestamp(21),
        ),
        RawItem(
            external_id="inc-2121",
            doc_type="incident",
            title="INC-2121: stale search results served after deploy",
            content=(
                "Summary: search-svc served a stale index snapshot for 3 hours after a "
                "deploy; newly published content was invisible.\n\n"
                "Root cause: the index warmup job silently failed and the deploy did "
                "not gate on it.\n\n"
                "Remediation: deploys now block on index freshness; a canary query "
                "asserts a just-written document is retrievable."
            ),
            url=f"{_BASE}/inc-2121",
            author_email="elena@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            metadata={"severity": "sev3", "caused_by": "search-svc"},
            last_activity_at=demo_timestamp(14),
        ),
        RawItem(
            external_id="inc-2125",
            doc_type="incident",
            title="INC-2125: data-pipeline backfill starved real-time ingestion",
            content=(
                "Summary: a March backfill of events_raw ran without day-sized batching "
                "and consumer lag on data-pipeline exceeded 40 minutes.\n\n"
                "Root cause: the backfill guidance was not followed and nothing "
                "enforced it.\n\n"
                "Remediation: the backfill tool now enforces day-sized batches and "
                "pauses real-time ingestion via the batch flag while running."
            ),
            url=f"{_BASE}/inc-2125",
            author_email="sofia@demo.dev",
            repo="data-pipeline",
            service="data-pipeline",
            team_name="Data",
            metadata={"severity": "sev3", "caused_by": "data-pipeline"},
            last_activity_at=demo_timestamp(9),
        ),
        RawItem(
            external_id="inc-2093",
            doc_type="incident",
            title="INC-2093: billing-worker OOM loop during invoice run",
            content=(
                "Summary: billing-worker OOM-killed repeatedly during the monthly "
                "invoice run; invoices were delayed by six hours.\n\n"
                "Root cause: the run loaded a full month of invoices into memory "
                "instead of streaming.\n\n"
                "Remediation: streaming batches with a hard memory ceiling and an alert "
                "on worker restart loops."
            ),
            url=f"{_BASE}/inc-2093",
            author_email="nina@demo.dev",
            repo="billing-worker",
            service="billing-worker",
            team_name="Payments",
            metadata={"severity": "sev2", "caused_by": "billing-worker"},
            last_activity_at=demo_timestamp(190),
        ),
    ]


class IncidentConnector:
    """Deterministic demo connector for the ``incident`` source type."""

    source_type: ClassVar[str] = "incident"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's postmortems (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(IncidentConnector())
