"""Offline demo feedback connector: agent feedback on context packets."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://feedback.demo.dev/items"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="fb-301",
            doc_type="feedback",
            title="Agent feedback: missing payments-api incident context",
            content=(
                "The compiled packet for the duplicate-charge bugfix omitted the "
                "INC-2107 postmortem, so the agent re-derived the root cause from "
                "scratch. Incident sources should rank higher for bugfix intents on "
                "payments-api."
            ),
            url=f"{_BASE}/fb-301",
            author_email="jade@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            metadata={"feedback_type": "missing_context"},
            last_activity_at=demo_timestamp(7),
        ),
        RawItem(
            external_id="fb-302",
            doc_type="feedback",
            title="Agent feedback: stale doc cited for web-app checkout",
            content=(
                "The packet cited the pre-refactor checkout guide; the flag it "
                "references (new_checkout_flow) is fully rolled out and slated for "
                "removal in ENG-1430. The doc should be marked stale."
            ),
            url=f"{_BASE}/fb-302",
            author_email="felix@demo.dev",
            repo="web-app",
            service="web-app",
            team_name="Growth",
            metadata={"feedback_type": "stale_context"},
            last_activity_at=demo_timestamp(12),
        ),
        RawItem(
            external_id="fb-303",
            doc_type="feedback",
            title="Agent feedback: auth-service packet was spot on",
            content=(
                "Packet for the signing-key rotation task selected ADR-0031, the "
                "architecture overview, and the INC-2113 postmortem — exactly the "
                "three sources a human reviewer would have picked. Zero wasted "
                "tokens."
            ),
            url=f"{_BASE}/fb-303",
            author_email="admin@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            metadata={"feedback_type": "useful"},
            last_activity_at=demo_timestamp(3),
        ),
        RawItem(
            external_id="fb-304",
            doc_type="feedback",
            title="Agent feedback: ACL blocked a needed postmortem",
            content=(
                "The packet reported one ACL-blocked document for the billing-worker "
                "task; the agent lacked the Payments team grant for the INC-2107 "
                "postmortem. Requesting access or a redacted public summary."
            ),
            url=f"{_BASE}/fb-304",
            author_email="jade@demo.dev",
            repo="billing-worker",
            service="billing-worker",
            team_name="Payments",
            metadata={"feedback_type": "permission_issue"},
            last_activity_at=demo_timestamp(20),
        ),
        RawItem(
            external_id="fb-305",
            doc_type="feedback",
            title="Agent feedback: wrong retry advice for payments-api",
            content=(
                "The packet quoted the legacy fixed-3-retries runbook instead of "
                "ADR-0042 and the agent implemented the wrong backoff. The retry "
                "topic has an open conflict; the ADR should win on authority."
            ),
            url=f"{_BASE}/fb-305",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            topic_key="payments-retry-policy",
            metadata={"feedback_type": "irrelevant"},
            last_activity_at=demo_timestamp(9),
        ),
        RawItem(
            external_id="fb-306",
            doc_type="feedback",
            title="Agent feedback: connect the on-call handbook as a source",
            content=(
                "Three packets in a row lacked escalation-path context that lives in "
                "the on-call handbook. Suggest connecting it as a confluence source "
                "so incident-response intents can cite it."
            ),
            url=f"{_BASE}/fb-306",
            author_email="maya@demo.dev",
            repo=None,
            service=None,
            team_name="SRE",
            metadata={"feedback_type": "suggest_source"},
            last_activity_at=demo_timestamp(15),
        ),
    ]


class FeedbackConnector:
    """Deterministic demo connector for the ``feedback`` source type."""

    source_type: ClassVar[str] = "feedback"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's agent feedback items (offline, deterministic)."""
        return _items()


register(FeedbackConnector())
