"""Offline demo Slack connector: engineering channel messages."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawAcl, RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://slack.demo.dev/archives"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="slack-9001",
            doc_type="message",
            title="heads up: payments-api deploy going out",
            content=(
                "heads up: payments-api deploy going out in 10 minutes with the "
                "idempotency changes from PR #801. canary gets 5% traffic for 15 "
                "minutes; auto-rollback if the 5xx ratio doubles."
            ),
            url=f"{_BASE}/payments/p9001",
            author_email="liam@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"channel": "#payments"},
            last_activity_at=demo_timestamp(2),
        ),
        RawItem(
            external_id="slack-9002",
            doc_type="message",
            title="we bumped token TTL to 24h for the mobile beta",
            content=(
                "heads up: to unblock the mobile beta we bumped access token TTL to 24 "
                "hours in auth-service config. remember to revert before GA — sessions "
                "table growth is already noticeable and ADR-0031 still says 15 minutes."
            ),
            url=f"{_BASE}/platform/p9002",
            author_email="marcus@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            topic_key="auth-token-ttl",
            metadata={"channel": "#platform", "stance": "ttl_24h"},
            last_activity_at=demo_timestamp(40),
        ),
        RawItem(
            external_id="slack-9003",
            doc_type="message",
            title="who owns the search_index table these days?",
            content=(
                "who owns the search_index table these days? need a schema change for "
                "the rerank experiment and the CODEOWNERS entry still points at a team "
                "that got reorged."
            ),
            url=f"{_BASE}/engineering/p9003",
            author_email="jade@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            metadata={"channel": "#engineering"},
            last_activity_at=demo_timestamp(18),
        ),
        RawItem(
            external_id="slack-9004",
            doc_type="message",
            title="canary for mobile-bff looks green",
            content=(
                "canary for mobile-bff home feed caching looks green: p95 down to 120ms, "
                "zero cache-invalidation misses in the last hour. promoting to 100% "
                "after lunch unless someone objects."
            ),
            url=f"{_BASE}/mobile/p9004",
            author_email="ines@demo.dev",
            repo="mobile-bff",
            service="mobile-bff",
            team_name="Mobile",
            metadata={"channel": "#mobile"},
            last_activity_at=demo_timestamp(6),
        ),
        RawItem(
            external_id="slack-9005",
            doc_type="message",
            title="pool saturation alert on payments-api",
            content=(
                "pool saturation alert on payments-api — utilization at 87% for six "
                "minutes. retries look jittered this time, suspect the invoice backfill. "
                "pausing the backfill via batch_invoicing to confirm."
            ),
            url=f"{_BASE}/incidents/p9005",
            author_email="aisha@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="SRE",
            metadata={"channel": "#incidents"},
            last_activity_at=demo_timestamp(3),
        ),
        RawItem(
            external_id="slack-9006",
            doc_type="message",
            title="on-call handoff notes for the payments rotation",
            content=(
                "on-call handoff: merchant escalation still open, contact is "
                "billing-lead@merchant-corp.example, cell +1 415-555-0142. they were "
                "double charged during the webhook storm; refund is queued in "
                "billing-worker.\n\n"
                "watch the notification_jobs backlog dashboard; it spiked yesterday."
            ),
            url=f"{_BASE}/sre/p9006",
            author_email="omar@demo.dev",
            repo="billing-worker",
            service="billing-worker",
            team_name="SRE",
            metadata={"channel": "#sre"},
            last_activity_at=demo_timestamp(1),
        ),
        RawItem(
            external_id="slack-9007",
            doc_type="message",
            title="reminder: change freeze starts friday",
            content=(
                "reminder: the quarterly change freeze starts friday 18:00 UTC. only "
                "sev1/sev2 fixes ship during the freeze, and they need an SRE approver "
                "on the PR. plan your web-app and payments-api merges accordingly."
            ),
            url=f"{_BASE}/engineering/p9007",
            author_email="admin@demo.dev",
            repo=None,
            service=None,
            team_name="Platform",
            metadata={"channel": "#engineering"},
            last_activity_at=demo_timestamp(27),
        ),
        RawItem(
            external_id="slack-9008",
            doc_type="message",
            title="revert search rerank weights to v1?",
            content=(
                "seeing relevance complaints from growth — proposing we revert "
                "search-svc rerank weights to the v1 profile (vector 0.7, fts 0.3) "
                "until the offline eval finishes. the v2 doc says otherwise but the "
                "numbers do not look great."
            ),
            url=f"{_BASE}/growth/p9008",
            author_email="felix@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            topic_key="search-ranking-weights",
            metadata={"channel": "#growth", "stance": "weights_v1"},
            last_activity_at=demo_timestamp(20),
        ),
        RawItem(
            external_id="slack-9009",
            doc_type="message",
            title="postmortem draft for the duplicate charge incident",
            content=(
                "draft of the INC-2107 postmortem is up. raw customer impact numbers "
                "stay restricted to the payments leads until legal clears the merchant "
                "comms; ping me for access."
            ),
            url=f"{_BASE}/payments/p9009",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            acl=RawAcl(public=False, user_emails=["admin@demo.dev", "priya@demo.dev"]),
            metadata={"channel": "#payments"},
            last_activity_at=demo_timestamp(50),
        ),
    ]


class SlackConnector:
    """Deterministic demo connector for the ``slack`` source type."""

    source_type: ClassVar[str] = "slack"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's channel messages (offline, deterministic)."""
        return _items()


register(SlackConnector())
