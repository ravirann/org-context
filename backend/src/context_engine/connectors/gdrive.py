"""Offline demo Google Drive connector: specs, runbooks, and planning docs."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawAcl, RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://docs.google.com/document/d"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="gdrive-4001",
            doc_type="doc",
            title="Payments API: idempotency key rollout plan",
            content=(
                "This plan sequences the rollout of the event_id idempotency table "
                "(see ENG-142) across payments-api's webhook dispatcher.\n\n"
                "Phase 1: dual-write dedupe keys behind the strict_idempotency flag in "
                "staging. Phase 2: ramp to 10% of production traffic, watching the "
                "duplicate-notification rate. Phase 3: full rollout once the duplicate "
                "rate holds at zero for 72 hours.\n\n"
                "Rollback plan: disable strict_idempotency and revert to the fixed "
                "3-retry policy documented in the payments runbook."
            ),
            url=f"{_BASE}/payments-idempotency-rollout-plan-0001/edit",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"kind": "spec", "mimeType": "application/vnd.google-apps.document"},
            last_activity_at=demo_timestamp(6),
        ),
        RawItem(
            external_id="gdrive-4002",
            doc_type="doc",
            title="auth-service: JWKS rotation runbook",
            content=(
                "Quarterly signing-key rotation for auth-service. Generate the new RSA "
                "key pair in the infra-terraform pipeline, publish it alongside the "
                "current key in the JWKS document for a 24-hour overlap window, then "
                "retire the old key.\n\n"
                "Downstream services refresh JWKS every six hours, so the overlap "
                "window must be at least that long. Verify token verification p95 "
                "latency stays flat during the overlap before retiring the old key.\n\n"
                "If a service fails to pick up the new key within the window, page "
                "Platform on-call rather than extending the overlap."
            ),
            url=f"{_BASE}/auth-service-jwks-rotation-runbook-0002/edit",
            author_email="marcus@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            metadata={"kind": "runbook", "mimeType": "application/vnd.google-apps.document"},
            last_activity_at=demo_timestamp(14),
        ),
        RawItem(
            external_id="gdrive-4003",
            doc_type="doc",
            title="Q3 planning: search relevance workstream",
            content=(
                "Search relevance work for Q3 builds on the weights v2 rerank "
                "experiment (+11% nDCG). Goals: ship a learned reranker behind "
                "search_rerank, reduce p95 query latency by 15%, and close the top "
                "five relevance complaints from the triage backlog.\n\n"
                "Staffing: two engineers from Growth, one from Data for offline eval "
                "tooling. Milestone reviews land at the end of each sprint; the eval "
                "set from the v2 experiment is the baseline for every comparison."
            ),
            url=f"{_BASE}/q3-search-relevance-planning-0003/edit",
            author_email="elena@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            metadata={"kind": "planning", "mimeType": "application/vnd.google-apps.document"},
            last_activity_at=demo_timestamp(27),
        ),
        RawItem(
            external_id="gdrive-4004",
            doc_type="doc",
            title="Incident runbook: checkout outage response",
            content=(
                "Restricted: contains paging details and vendor escalation contacts "
                "for checkout-path outages.\n\n"
                "When checkout error rate exceeds 2% for five minutes, page SRE "
                "primary and the Payments on-call simultaneously. Primary owns the "
                "customer-facing status page; Payments on-call owns merchant comms.\n\n"
                "If the outage traces to the payment provider, use the direct "
                "escalation line in the vendor contacts appendix — do not use the "
                "public support queue, which adds 20+ minutes of latency."
            ),
            url=f"{_BASE}/checkout-outage-response-runbook-0004/edit",
            author_email="omar@demo.dev",
            repo=None,
            service=None,
            team_name="SRE",
            acl=RawAcl(public=False, team_names=["SRE"]),
            metadata={"kind": "runbook", "mimeType": "application/vnd.google-apps.document"},
            last_activity_at=demo_timestamp(38),
        ),
        RawItem(
            external_id="gdrive-4005",
            doc_type="doc",
            title="Payments: refund authority & escalation matrix",
            content=(
                "Restricted: refund limits and escalation contacts for the Payments "
                "team only.\n\n"
                "First responders may authorize refunds up to $500 without approval. "
                "Refunds between $500 and $5,000 require a team lead sign-off; "
                "anything above $5,000 escalates to Finance.\n\n"
                "Escalation contacts and the provider support hotline are listed in "
                "the appendix; do not share this document outside the Payments team."
            ),
            url=f"{_BASE}/payments-refund-escalation-matrix-0005/edit",
            author_email="nina@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            acl=RawAcl(public=False, team_names=["Payments"]),
            metadata={"kind": "spec", "mimeType": "application/vnd.google-apps.document"},
            last_activity_at=demo_timestamp(52),
        ),
        RawItem(
            external_id="gdrive-4006",
            doc_type="doc",
            title="web-app: canary rollout spec",
            content=(
                "Canary deploys for web-app receive 5% of traffic for 15 minutes "
                "before promotion. Automatic rollback triggers when the 5xx ratio "
                "exceeds 2% or p99 latency doubles against the control group.\n\n"
                "Feature-flagged changes should ship dark and ramp via the flag "
                "console rather than riding the canary window. No deploys during a "
                "change freeze without SRE sign-off."
            ),
            url=f"{_BASE}/web-app-canary-rollout-spec-0006/edit",
            author_email="jade@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"kind": "spec", "mimeType": "application/vnd.google-apps.document"},
            last_activity_at=demo_timestamp(68),
        ),
        RawItem(
            external_id="gdrive-4007",
            doc_type="doc",
            title="Platform reliability OKRs: FY26 Q3",
            content=(
                "Objective: reduce sev1/sev2 incident count by 30% quarter-over-"
                "quarter.\n\n"
                "Key results: (1) close every postmortem action item within 30 days, "
                "(2) cut auth-service p95 latency by 20% via the JWKS overlap change, "
                "(3) reach 99.95% availability on the payments-api ingress.\n\n"
                "Reviewed weekly in the reliability review alongside the postmortem "
                "backlog."
            ),
            url=f"{_BASE}/platform-reliability-okrs-fy26-q3-0007/edit",
            author_email="admin@demo.dev",
            repo=None,
            service=None,
            team_name="Platform",
            metadata={"kind": "planning", "mimeType": "application/vnd.google-apps.document"},
            last_activity_at=demo_timestamp(95),
        ),
        RawItem(
            external_id="gdrive-4008",
            doc_type="doc",
            title="New engineer onboarding checklist",
            content=(
                "Week one: repo access, VPN, and the infra-terraform read scope. "
                "Shadow an on-call shift by day three.\n\n"
                "Week two: ship a small fix to a service you don't own — payments-api "
                "and notifications are good starter services with clear runbooks.\n\n"
                "By day thirty: complete the incident-response training and read the "
                "postmortem process doc before joining the on-call rotation."
            ),
            url=f"{_BASE}/new-engineer-onboarding-checklist-0008/edit",
            author_email="grace@demo.dev",
            repo=None,
            service=None,
            team_name="Platform",
            metadata={"kind": "doc", "mimeType": "application/vnd.google-apps.document"},
            last_activity_at=demo_timestamp(133),
        ),
    ]


class GDriveConnector:
    """Deterministic demo connector for the ``gdrive`` source type."""

    source_type: ClassVar[str] = "gdrive"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's Drive docs (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(GDriveConnector())
