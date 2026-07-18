"""Offline demo Notion connector: product specs, meeting notes, and onboarding docs."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawAcl, RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://www.notion.so/demo-org"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="notion-4001",
            doc_type="doc",
            title="Product spec: Payments retry v3",
            content=(
                "Goal: replace the fixed 3-retry policy with the jittered exponential "
                "backoff adopted in ADR-0042, and add a dashboard for retry exhaustion "
                "by merchant.\n\n"
                "Rollout: ship behind the enable_retry_v2 flag, ramp 10% -> 50% -> 100% "
                "over two weeks, with rollback triggered by an exhaustion rate above "
                "2%.\n\n"
                "Out of scope: refund automation and merchant-facing status pages are "
                "tracked separately on the Payments roadmap."
            ),
            url=f"{_BASE}/payments-retry-v3",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            topic_key="payments-retry-policy",
            metadata={"stance": "jittered_backoff_v3", "space": "Product"},
            last_activity_at=demo_timestamp(12),
        ),
        RawItem(
            external_id="notion-4002",
            doc_type="doc",
            title="Product spec: Search reranking rollout",
            content=(
                "Ships the v2 ranker weights (vector 0.45, fts 0.25, freshness 0.15, "
                "authority 0.15) behind the search_rerank flag from the feature flag "
                "catalog.\n\n"
                "Success metric: +8% session click-through with no regression in p95 "
                "query latency; review with Growth leadership before removing the v1 "
                "fallback path.\n\n"
                "Dependencies: the search-svc index rebuild must finish before enabling "
                "the flag for more than 25% of traffic."
            ),
            url=f"{_BASE}/search-reranking-rollout",
            author_email="elena@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            metadata={"space": "Product"},
            last_activity_at=demo_timestamp(18),
        ),
        RawItem(
            external_id="notion-4003",
            doc_type="doc",
            title="Meeting notes: Payments weekly sync — 2026-06-18",
            content=(
                "Attendees: priya, nina, on-call lead. Reviewed the retry exhaustion "
                "dashboard: 0.8% of charges exhaust all attempts, within the 2% "
                "rollback threshold.\n\n"
                "Action items: nina to add the new retry_attempts column to the "
                "payments schema reference; priya to file the ticket for merchant-"
                "facing status page discovery.\n\n"
                "Next sync: 2026-06-25, same time."
            ),
            url=f"{_BASE}/payments-weekly-sync-0618",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"space": "Meeting Notes"},
            last_activity_at=demo_timestamp(8),
        ),
        RawItem(
            external_id="notion-4004",
            doc_type="doc",
            title="Meeting notes: Growth roadmap planning — Q3",
            content=(
                "Attendees: jade, elena, growth PM. Prioritized: the search reranking "
                "rollout, web-app canary tuning, and a spike on edge_caching for "
                "mobile-bff.\n\n"
                "Deprioritized: dark_mode_mobile ships only after the flag debt review "
                "confirms renewal or removal.\n\n"
                "Decision: web-app deploy cadence stays weekly; no exceptions during "
                "the July change freeze."
            ),
            url=f"{_BASE}/growth-roadmap-q3",
            author_email="jade@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"space": "Meeting Notes"},
            last_activity_at=demo_timestamp(25),
        ),
        RawItem(
            external_id="notion-4005",
            doc_type="doc",
            title="Onboarding: New engineer setup guide",
            content=(
                "Day 1: request access to the mesh VPN, clone auth-service and "
                "payments-api, and run the bootstrap script in each repo's README.\n\n"
                "Day 2-3: shadow the on-call handoff meeting and read the auth-service "
                "architecture overview and the payments schema reference before "
                "touching production data.\n\n"
                "Checklist: the JWKS refresh timer, the feature flag catalog, and the "
                "postmortem process page are required reading before your first "
                "on-call shift."
            ),
            url=f"{_BASE}/new-engineer-setup",
            author_email="marcus@demo.dev",
            repo=None,
            service=None,
            team_name="Platform",
            metadata={"space": "Onboarding"},
            last_activity_at=demo_timestamp(150),
        ),
        RawItem(
            external_id="notion-4006",
            doc_type="doc",
            title="Onboarding: Payments on-call shadow checklist",
            content=(
                "Shadow the current on-call for one full rotation before joining the "
                "schedule; pair on at least one triage call and one merchant "
                "escalation.\n\n"
                "This checklist links the refund authority limits and the provider "
                "support hotline from the on-call guide, so it is restricted to the "
                "Payments team."
            ),
            url=f"{_BASE}/payments-oncall-shadow-checklist",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            acl=RawAcl(public=False, team_names=["Payments"]),
            metadata={"space": "Onboarding"},
            last_activity_at=demo_timestamp(60),
        ),
        RawItem(
            external_id="notion-4007",
            doc_type="doc",
            title="Meeting notes: SRE postmortem retro — INC-2107",
            content=(
                "Reviewed the payments connection pool exhaustion incident. Root "
                "cause: synchronized fixed-interval retries during a provider "
                "outage.\n\n"
                "Action items: adopt jittered backoff (tracked as ADR-0042), add a "
                "pool saturation alert, and document the provider outage runbook by "
                "end of quarter.\n\n"
                "Blameless: no individual owner assigned; process gaps only."
            ),
            url=f"{_BASE}/sre-postmortem-inc-2107",
            author_email="omar@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="SRE",
            metadata={"space": "Meeting Notes"},
            last_activity_at=demo_timestamp(55),
        ),
    ]


class NotionConnector:
    """Deterministic demo connector for the ``notion`` source type."""

    source_type: ClassVar[str] = "notion"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's Notion pages (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(NotionConnector())
