"""Offline demo Zendesk connector: customer support tickets."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://acme.zendesk.com/agent/tickets"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="4501",
            doc_type="ticket",
            title="Duplicate charge on invoice after retrying payment",
            content=(
                "Customer reports being charged twice for the same invoice after the "
                "checkout page timed out and they resubmitted. Correlates with the "
                "webhook retry storm engineering is tracking under ENG-1401.\n\n"
                "Refunded the duplicate charge manually; flagged for the payments team "
                "to confirm the idempotency fix covers this path before closing."
            ),
            url=f"{_BASE}/4501",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"status": "pending", "priority": "urgent"},
            last_activity_at=demo_timestamp(6),
        ),
        RawItem(
            external_id="4507",
            doc_type="ticket",
            title="Search results feel slower than usual since last week",
            content=(
                "Customer says product search has felt noticeably slower since "
                "roughly last Tuesday, especially during business hours. Matches the "
                "p95 latency regression on search-svc engineering is investigating "
                "(ENG-1405).\n\nSet expectations for a fix window and offered to "
                "follow up once the deploy lands."
            ),
            url=f"{_BASE}/4507",
            author_email="jade@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            metadata={"status": "open", "priority": "normal"},
            last_activity_at=demo_timestamp(19),
        ),
        RawItem(
            external_id="4512",
            doc_type="ticket",
            title="Request: export billing history older than 12 months",
            content=(
                "Customer needs invoice history going back three years for an audit "
                "and can't find anything past 12 months in the self-serve billing "
                "portal. Confirmed billing-worker only retains a rolling 12-month "
                "window; escalated to see whether archived records can be pulled on "
                "request."
            ),
            url=f"{_BASE}/4512",
            author_email="nina@demo.dev",
            repo="billing-worker",
            service="billing-worker",
            team_name="Payments",
            metadata={"status": "open", "priority": "low"},
            last_activity_at=demo_timestamp(41),
        ),
        RawItem(
            external_id="4519",
            doc_type="ticket",
            title="Nightly report email arrived with missing rows",
            content=(
                "Customer's scheduled nightly export email was missing roughly a "
                "day's worth of rows. Likely related to the flaky data-pipeline "
                "backfill test failures the team quarantined (ENG-1418).\n\n"
                "Re-triggered the export manually and it came back complete; "
                "monitoring for recurrence."
            ),
            url=f"{_BASE}/4519",
            author_email="lena@demo.dev",
            repo="data-pipeline",
            service="data-pipeline",
            team_name="Data",
            metadata={"status": "solved", "priority": "normal"},
            last_activity_at=demo_timestamp(28),
        ),
        RawItem(
            external_id="4524",
            doc_type="ticket",
            title="How do I get notified when a workflow run fails?",
            content=(
                "Customer asking whether there is a way to subscribe to failure "
                "notifications for their scheduled workflow runs instead of checking "
                "the dashboard manually. Pointed them at the webhook subscription "
                "docs and filed the in-app alerting request with product."
            ),
            url=f"{_BASE}/4524",
            author_email="grace@demo.dev",
            repo="notifications",
            service="notifications",
            team_name="Platform",
            metadata={"status": "solved", "priority": "low"},
            last_activity_at=demo_timestamp(9),
        ),
        RawItem(
            external_id="4530",
            doc_type="ticket",
            title="Checkout page shows old promo banner after feature flag rollout",
            content=(
                "Customer sent a screenshot of a stale promo banner appearing on "
                "checkout that should have been retired with the new_checkout_flow "
                "rollout (ENG-1430). Looks like a CDN cache issue rather than the "
                "flag itself; purging the affected asset paths."
            ),
            url=f"{_BASE}/4530",
            author_email="felix@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"status": "pending", "priority": "normal"},
            last_activity_at=demo_timestamp(2),
        ),
        RawItem(
            external_id="4536",
            doc_type="ticket",
            title="Intermittent 503s when submitting large orders",
            content=(
                "Customer's checkout occasionally returns a 503 on orders with many "
                "line items. Suspect this is the payments-api connection pool "
                "saturation flagged in INC-2107; asked payments on-call to confirm "
                "before we message the customer with a workaround."
            ),
            url=f"{_BASE}/4536",
            author_email="omar@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"status": "open", "priority": "high"},
            last_activity_at=demo_timestamp(1),
        ),
    ]


class ZendeskConnector:
    """Deterministic demo connector for the ``zendesk`` source type."""

    source_type: ClassVar[str] = "zendesk"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's support tickets (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(ZendeskConnector())
