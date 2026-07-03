"""Offline demo ADR connector: architecture decision records with stances."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://adr.demo.dev/records"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="adr-0042",
            doc_type="adr",
            title="ADR-0042: Exponential backoff with jitter for payment retries",
            content=(
                "Decision: payment charge retries use exponential backoff with full "
                "jitter, base 200ms, cap 30s, max 6 attempts.\n\n"
                "Context: fixed-interval retries caused synchronized load spikes on the "
                "payments table during INC-2107 and exhausted the payments-api "
                "connection pool.\n\n"
                "Consequences: all retrying clients must go through the shared retry "
                "helper in payments-api; the legacy runbook guidance of three fixed "
                "retries is superseded."
            ),
            url=f"{_BASE}/adr-0042",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            topic_key="payments-retry-policy",
            metadata={"stance": "exponential_backoff", "status": "accepted"},
            last_activity_at=demo_timestamp(60),
        ),
        RawItem(
            external_id="adr-0031",
            doc_type="adr",
            title="ADR-0031: Access tokens expire after 15 minutes",
            content=(
                "Decision: access tokens issued by POST /v1/auth/token expire after 15 "
                "minutes and must be refreshed via POST /v1/auth/refresh.\n\n"
                "Context: the sessions table audit found long-lived tokens surviving "
                "employee offboarding. Short TTLs bound the blast radius of a leaked "
                "token.\n\n"
                "Consequences: clients must implement silent refresh; any TTL override "
                "for a beta requires a dated revert plan."
            ),
            url=f"{_BASE}/adr-0031",
            author_email="marcus@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            topic_key="auth-token-ttl",
            metadata={"stance": "ttl_15m", "status": "accepted"},
            last_activity_at=demo_timestamp(120),
        ),
        RawItem(
            external_id="adr-0027",
            doc_type="adr",
            title="ADR-0027: Expand-contract schema migrations",
            content=(
                "Decision: all schema changes to production tables (payments, invoices, "
                "users) follow expand-contract: add nullable columns, dual-write, "
                "backfill, then drop.\n\n"
                "Context: an in-place column rename locked the payments table for four "
                "minutes in production.\n\n"
                "Consequences: destructive in-place migrations are banned; every "
                "migration ships with a rollback script."
            ),
            url=f"{_BASE}/adr-0027",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            topic_key="db-migration-strategy",
            metadata={"stance": "expand_contract", "status": "accepted"},
            last_activity_at=demo_timestamp(200),
        ),
        RawItem(
            external_id="adr-0038",
            doc_type="adr",
            title="ADR-0038: Use SES for transactional email",
            content=(
                "Decision: notifications sends transactional email through AWS SES with "
                "dedicated IP warmup.\n\n"
                "Context: deliverability on the previous provider degraded below 97% "
                "and support could not raise sending limits during incidents.\n\n"
                "Consequences: the notification_jobs worker retries via SQS with "
                "dead-lettering after 5 attempts; SendGrid setup docs are historical."
            ),
            url=f"{_BASE}/adr-0038",
            author_email="grace@demo.dev",
            repo="notifications",
            service="notifications",
            team_name="Platform",
            topic_key="notifications-provider",
            metadata={"stance": "ses", "status": "accepted"},
            last_activity_at=demo_timestamp(90),
        ),
        RawItem(
            external_id="adr-0044",
            doc_type="adr",
            title="ADR-0044: Weekly mobile release trains",
            content=(
                "Decision: mobile ships on a weekly release train cut every Monday. "
                "Hotfixes ride the next train unless sev1.\n\n"
                "Context: ad-hoc releases made store review timing unpredictable and "
                "broke mobile-bff compatibility guarantees.\n\n"
                "Consequences: the mobile-bff API must stay backward compatible for two "
                "trains; cadence changes require Mobile and Growth lead sign-off."
            ),
            url=f"{_BASE}/adr-0044",
            author_email="kenji@demo.dev",
            repo="mobile-bff",
            service="mobile-bff",
            team_name="Mobile",
            topic_key="mobile-release-cadence",
            metadata={"stance": "weekly", "status": "accepted"},
            last_activity_at=demo_timestamp(75),
        ),
        RawItem(
            external_id="adr-0019",
            doc_type="adr",
            title="ADR-0019: Cursor-based pagination for list APIs",
            content=(
                "Decision: list endpoints return an opaque next_cursor token; offset "
                "pagination is banned for new APIs.\n\n"
                "Context: offset pagination against search_index and events_raw timed "
                "out beyond 100k rows.\n\n"
                "Consequences: clients must treat cursors as opaque and short-lived. "
                "This ADR is pinned as the canonical pagination reference for every "
                "service."
            ),
            url=f"{_BASE}/adr-0019",
            author_email="admin@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Platform",
            metadata={"stance": "cursor_pagination", "status": "accepted", "authority": 0.99},
            last_activity_at=demo_timestamp(150),
        ),
        RawItem(
            external_id="adr-0008",
            doc_type="adr",
            title="ADR-0008: Split the monolith into services (superseded)",
            content=(
                "Decision (2019): split the monolith into payments, auth, and "
                "notifications services over three quarters.\n\n"
                "Status: superseded — the split completed and the sequencing guidance "
                "here no longer reflects the current architecture. Kept for historical "
                "context only."
            ),
            url=f"{_BASE}/adr-0008",
            author_email="admin@demo.dev",
            repo=None,
            service=None,
            team_name="Platform",
            metadata={"stance": "microservices", "status": "superseded", "deprecated": True},
            last_activity_at=demo_timestamp(300),
        ),
        RawItem(
            external_id="adr-0051",
            doc_type="adr",
            title="ADR-0051: PII redaction in logs and context packets",
            content=(
                "Decision: logs and compiled context packets pass through the "
                "pii_redaction patterns (emails, phone numbers, card numbers, cloud "
                "keys) before storage.\n\n"
                "Context: a security review found raw PAN data in payments-api debug "
                "logs.\n\n"
                "Consequences: an audit entry is written whenever a redaction pattern "
                "matches; new log fields must be reviewed against the pattern list."
            ),
            url=f"{_BASE}/adr-0051",
            author_email="admin@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="SRE",
            metadata={"stance": "redact_all", "status": "accepted"},
            last_activity_at=demo_timestamp(30),
        ),
    ]


class AdrConnector:
    """Deterministic demo connector for the ``adr`` source type."""

    source_type: ClassVar[str] = "adr"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's decision records (offline, deterministic)."""
        return _items()


register(AdrConnector())
