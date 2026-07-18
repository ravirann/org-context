"""Offline demo Gmail connector: escalations, release notes, incident follow-ups."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawAcl, RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://mail.google.com/mail/u/0/#all"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="gmail-7001",
            doc_type="message",
            title="Re: Duplicate charge on invoice #4471",
            content=(
                "Hi team,\n\n"
                "Following up on the double charge during Tuesday's webhook storm. "
                "The customer (billing-lead@merchant-corp.example) says the refund "
                "still hasn't posted to their statement. Can payments confirm the "
                "refund actually cleared in billing-worker before I reply?\n\n"
                "Thanks,\nPriya"
            ),
            url=f"{_BASE}/gmail-7001",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            acl=RawAcl(public=False, user_emails=["priya@demo.dev", "admin@demo.dev"]),
            metadata={"thread": "duplicate-charge-4471", "labels": ["support"]},
            last_activity_at=demo_timestamp(1),
        ),
        RawItem(
            external_id="gmail-7002",
            doc_type="message",
            title="Re: Webhook deliveries failing since Tuesday",
            content=(
                "Marcus,\n\n"
                "Merchant-corp is still seeing dropped webhook deliveries for order "
                "events. Their integration retries three times and gives up, so "
                "they're missing shipment updates. Is this related to the auth-service "
                "token TTL change, or something on the delivery worker side?\n\n"
                "Please loop in on-call if this needs a hotfix before end of day.\n\n"
                "— Support"
            ),
            url=f"{_BASE}/gmail-7002",
            author_email="support@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            acl=RawAcl(public=False, user_emails=["marcus@demo.dev", "admin@demo.dev"]),
            metadata={"thread": "webhook-delivery-failures", "labels": ["support"]},
            last_activity_at=demo_timestamp(3),
        ),
        RawItem(
            external_id="gmail-7003",
            doc_type="message",
            title="[Release] payments-api v3.4.0 — idempotency keys shipped",
            content=(
                "payments-api v3.4.0 is live in production as of this morning.\n\n"
                "Highlights:\n"
                "- Idempotency-Key enforcement on the charge endpoint (PR #801)\n"
                "- Canary ran at 5% traffic for 15 minutes with no 5xx increase\n"
                "- Rollback plan: revert to v3.3.2 via the standard deploy pipeline\n\n"
                "Full changelog is linked from the release notes doc. Ping #payments "
                "with any questions."
            ),
            url=f"{_BASE}/gmail-7003",
            author_email="liam@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            acl=RawAcl(
                public=False, user_emails=["priya@demo.dev", "liam@demo.dev", "admin@demo.dev"]
            ),
            metadata={"thread": "release-payments-api-3.4.0", "labels": ["release"]},
            last_activity_at=demo_timestamp(10),
        ),
        RawItem(
            external_id="gmail-7004",
            doc_type="message",
            title="[Release] mobile-bff home feed caching — canary promoted to 100%",
            content=(
                "The home feed caching change for mobile-bff finished its canary "
                "window clean: p95 dropped to 120ms with zero cache-invalidation "
                "misses over the full hour.\n\n"
                "Promoted to 100% of traffic just now. Dashboards look steady; will "
                "keep an eye on them through end of week before calling this done."
            ),
            url=f"{_BASE}/gmail-7004",
            author_email="ines@demo.dev",
            repo="mobile-bff",
            service="mobile-bff",
            team_name="Mobile",
            acl=RawAcl(public=False, user_emails=["ines@demo.dev", "admin@demo.dev"]),
            metadata={"thread": "release-mobile-bff-caching", "labels": ["release"]},
            last_activity_at=demo_timestamp(6),
        ),
        RawItem(
            external_id="gmail-7005",
            doc_type="message",
            title="Postmortem review meeting — INC-2107 duplicate charges",
            content=(
                "Scheduling the postmortem review for INC-2107 (payments connection "
                "pool exhaustion, duplicate charges) for Thursday 2pm.\n\n"
                "Draft doc covers the root cause (synchronized fixed-interval "
                "retries during the provider outage) and proposes jittered backoff "
                "per ADR-0042. Please read ahead — raw customer impact numbers stay "
                "restricted to the payments leads until legal clears the merchant "
                "comms.\n\n"
                "— Omar"
            ),
            url=f"{_BASE}/gmail-7005",
            author_email="omar@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="SRE",
            acl=RawAcl(
                public=False, user_emails=["priya@demo.dev", "omar@demo.dev", "admin@demo.dev"]
            ),
            metadata={"thread": "postmortem-inc-2107", "labels": ["incident"]},
            last_activity_at=demo_timestamp(50),
        ),
        RawItem(
            external_id="gmail-7006",
            doc_type="message",
            title="Action items from pool saturation incident",
            content=(
                "Recapping this morning's pool saturation alert on payments-api "
                "(utilization hit 87% for six minutes, traced to the invoice "
                "backfill job).\n\n"
                "Action items:\n"
                "1. Aisha: add a pool saturation alert with a lower threshold\n"
                "2. Omar: document the provider outage runbook\n"
                "3. Both: confirm batch_invoicing pause/resume is safe to automate\n\n"
                "No customer-facing impact this time, but let's close these out "
                "before the next backfill run."
            ),
            url=f"{_BASE}/gmail-7006",
            author_email="aisha@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="SRE",
            acl=RawAcl(
                public=False, user_emails=["aisha@demo.dev", "omar@demo.dev", "admin@demo.dev"]
            ),
            metadata={"thread": "pool-saturation-followup", "labels": ["incident"]},
            last_activity_at=demo_timestamp(2),
        ),
        RawItem(
            external_id="gmail-7007",
            doc_type="message",
            title="Refund request — order #88213 not received",
            content=(
                "Hello,\n\n"
                "A customer is asking about a refund for order #88213 that was "
                "promised over a week ago. I checked billing-worker and don't see "
                "a completed payout record, only a queued one.\n\n"
                "Can someone from payments confirm whether this is stuck behind the "
                "notification_jobs backlog, or if it needs a manual retry?\n\n"
                "Thanks,\nSupport"
            ),
            url=f"{_BASE}/gmail-7007",
            author_email="support@demo.dev",
            repo="billing-worker",
            service="billing-worker",
            team_name="Payments",
            acl=RawAcl(public=False, user_emails=["priya@demo.dev", "admin@demo.dev"]),
            metadata={"thread": "refund-order-88213", "labels": ["support"]},
            last_activity_at=demo_timestamp(18),
        ),
    ]


class GmailConnector:
    """Deterministic demo connector for the ``gmail`` source type."""

    source_type: ClassVar[str] = "gmail"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's mailbox messages (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(GmailConnector())
