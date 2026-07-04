"""Offline demo Confluence connector: wiki docs, runbooks and guides."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawAcl, RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://wiki.demo.dev/spaces/ENG"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="conf-2001",
            doc_type="doc",
            title="Payments runbook: retry handling (legacy)",
            content=(
                "When a charge fails, retry exactly 3 times with a fixed 5 second delay "
                "before marking the payment_attempts row failed. This keeps behavior "
                "predictable for support engineers reading the payments table.\n\n"
                "Escalate to the Payments on-call if all three retries fail for more "
                "than ten distinct merchants inside an hour.\n\n"
                "Note: this page predates ADR-0042 and has not been reconciled with the "
                "jittered backoff decision."
            ),
            url=f"{_BASE}/payments-retry-legacy",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            topic_key="payments-retry-policy",
            metadata={"stance": "fixed_3_retries", "space": "ENG"},
            last_activity_at=demo_timestamp(320),
        ),
        RawItem(
            external_id="conf-2002",
            doc_type="doc",
            title="auth-service architecture overview",
            content=(
                "auth-service issues and verifies tokens for every other service. "
                "POST /v1/auth/token mints an access token; POST /v1/auth/refresh "
                "rotates it against the sessions table.\n\n"
                "Signing keys rotate quarterly via the infra-terraform pipeline. "
                "Downstream services must fetch the JWKS document at boot and on a "
                "six-hour refresh timer.\n\n"
                "Capacity: two replicas per region behind the mesh; scale on p95 "
                "latency, not CPU, because token verification is bursty."
            ),
            url=f"{_BASE}/auth-architecture",
            author_email="marcus@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            metadata={"space": "ENG"},
            last_activity_at=demo_timestamp(60),
        ),
        RawItem(
            external_id="conf-2003",
            doc_type="doc",
            title="On-call guide: Payments team",
            content=(
                "Payments on-call rotates weekly on Mondays. First responder owns "
                "triage; the secondary owns merchant comms.\n\n"
                "Escalation ladder, refund authority limits, and the provider support "
                "hotline are listed below — this page is restricted to the Payments "
                "team because it contains direct contact details and refund limits."
            ),
            url=f"{_BASE}/payments-oncall",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            acl=RawAcl(public=False, team_names=["Payments"]),
            metadata={"space": "ENG"},
            last_activity_at=demo_timestamp(30),
        ),
        RawItem(
            external_id="conf-2004",
            doc_type="doc",
            title="Schema reference: payments and payment_attempts",
            content=(
                "payments holds one row per settled charge; payment_attempts records "
                "every try, including failures. Both tables are hot — schema changes "
                "must follow the expand-contract migration policy with a rollback "
                "script.\n\n"
                "Retention: payment_attempts rolls up into daily aggregates after 90 "
                "days. Never join payments to events_raw in an online path; use the "
                "warehouse."
            ),
            url=f"{_BASE}/payments-schema",
            author_email="nina@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"space": "ENG"},
            last_activity_at=demo_timestamp(90),
        ),
        RawItem(
            external_id="conf-2005",
            doc_type="doc",
            title="How to deploy web-app",
            content=(
                "web-app deploys via the pipeline in the web-app repo. Canary receives "
                "5% of traffic for 15 minutes; automatic rollback triggers when the 5xx "
                "ratio exceeds 2% or p99 latency doubles against control.\n\n"
                "Feature-flagged changes should ship dark, then ramp via the flag "
                "console. Never deploy during the change freeze without SRE approval."
            ),
            url=f"{_BASE}/web-app-deploys",
            author_email="jade@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"space": "ENG"},
            last_activity_at=demo_timestamp(45),
        ),
        RawItem(
            external_id="conf-2006",
            doc_type="doc",
            title="Feature flag catalog",
            content=(
                "Live flags: strict_idempotency (payments-api), enable_retry_v2 "
                "(payments-api), async_webhooks (notifications), search_rerank "
                "(search-svc), edge_caching (mobile-bff), batch_invoicing "
                "(billing-worker), dark_mode_mobile (mobile apps).\n\n"
                "Every flag needs an owner, a rollout plan, and a removal ticket. Flags "
                "older than two quarters get flagged in the weekly debt review."
            ),
            url=f"{_BASE}/feature-flags",
            author_email="admin@demo.dev",
            repo=None,
            service=None,
            team_name="Platform",
            metadata={"space": "ENG"},
            last_activity_at=demo_timestamp(15),
        ),
        RawItem(
            external_id="conf-2007",
            doc_type="doc",
            title="Postmortem process",
            content=(
                "Every sev1/sev2 incident gets a blameless postmortem within five "
                "working days. The draft lives in the incident tracker; the review "
                "meeting assigns owners to every action item.\n\n"
                "Action items older than 30 days page the owning team's lead in the "
                "weekly reliability review."
            ),
            url=f"{_BASE}/postmortem-process",
            author_email="omar@demo.dev",
            repo=None,
            service=None,
            team_name="SRE",
            metadata={"space": "ENG"},
            last_activity_at=demo_timestamp(200),
        ),
        RawItem(
            external_id="conf-2008",
            doc_type="doc",
            title="Search ranking weights v2",
            content=(
                "The GET /v1/search ranker uses vector 0.45, fts 0.25, freshness 0.15, "
                "authority 0.15 after the rerank experiment. The search_rerank flag "
                "must stay enabled for these weights to apply.\n\n"
                "Offline eval showed +11% nDCG over the v1 profile; relevance "
                "complaints should be triaged against the eval set before proposing a "
                "revert."
            ),
            url=f"{_BASE}/search-weights-v2",
            author_email="elena@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            topic_key="search-ranking-weights",
            metadata={"stance": "weights_v2", "space": "ENG"},
            last_activity_at=demo_timestamp(10),
        ),
    ]


class ConfluenceConnector:
    """Deterministic demo connector for the ``confluence`` source type."""

    source_type: ClassVar[str] = "confluence"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's wiki docs (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(ConfluenceConnector())
