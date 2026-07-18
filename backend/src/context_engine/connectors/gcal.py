"""Offline demo Google Calendar connector: attendee-scoped engineering meetings."""

from __future__ import annotations

from typing import ClassVar

from context_engine.connectors.base import RawAcl, RawItem, demo_timestamp, register
from context_engine.storage.models import Source

_BASE = "https://calendar.demo.dev/event"


def _items() -> list[RawItem]:
    return [
        RawItem(
            external_id="gcal-5001",
            doc_type="doc",
            title="Payments sprint planning",
            content=(
                "Sprint planning for the Payments team.\n\n"
                "Organizer: priya@demo.dev\n\n"
                "Attendees:\n"
                "- priya@demo.dev (accepted)\n"
                "- nina@demo.dev (accepted)\n"
                "- admin@demo.dev (tentative)\n\n"
                "Agenda: jittered backoff rollout (ADR-0042), event_id dedupe follow-up, "
                "and carryover from the duplicate-charge incident.\n\n"
                "Start: 2026-05-25T10:00:00-07:00\n"
                "End: 2026-05-25T10:30:00-07:00"
            ),
            url=f"{_BASE}/gcal-5001",
            author_email="priya@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="Payments",
            acl=RawAcl(
                public=False, user_emails=["priya@demo.dev", "nina@demo.dev", "admin@demo.dev"]
            ),
            metadata={"calendarId": "payments-team@demo.dev", "meeting_type": "sprint_planning"},
            last_activity_at=demo_timestamp(7),
        ),
        RawItem(
            external_id="gcal-5002",
            doc_type="doc",
            title="INC-2107 incident retro",
            content=(
                "Blameless retro for INC-2107 (duplicate charges on payments-api).\n\n"
                "Organizer: omar@demo.dev\n\n"
                "Attendees:\n"
                "- omar@demo.dev (accepted)\n"
                "- priya@demo.dev (accepted)\n"
                "- marcus@demo.dev (accepted)\n\n"
                "Review remediation items: exponential backoff with full jitter, "
                "event_id dedupe before writes, pool-saturation alert. Assign owners "
                "to any action item still open after 30 days.\n\n"
                "Start: 2026-04-08T09:00:00-07:00\n"
                "End: 2026-04-08T10:00:00-07:00"
            ),
            url=f"{_BASE}/gcal-5002",
            author_email="omar@demo.dev",
            repo="payments-api",
            service="payments-api",
            team_name="SRE",
            acl=RawAcl(
                public=False, user_emails=["omar@demo.dev", "priya@demo.dev", "marcus@demo.dev"]
            ),
            metadata={"calendarId": "sre-team@demo.dev", "meeting_type": "incident_retro"},
            last_activity_at=demo_timestamp(48),
        ),
        RawItem(
            external_id="gcal-5003",
            doc_type="doc",
            title="auth-service architecture review",
            content=(
                "Architecture review for the auth-service signing-key rotation redesign.\n\n"
                "Organizer: marcus@demo.dev\n\n"
                "Attendees:\n"
                "- marcus@demo.dev (accepted)\n"
                "- elena@demo.dev (accepted)\n"
                "- admin@demo.dev (needsAction)\n\n"
                "Walk through the JWKS refresh-timer fix from INC-2113 and the proposed "
                "six-hour cache ceiling enforced in the shared client.\n\n"
                "Start: 2026-05-12T13:00:00-07:00\n"
                "End: 2026-05-12T14:00:00-07:00"
            ),
            url=f"{_BASE}/gcal-5003",
            author_email="marcus@demo.dev",
            repo="auth-service",
            service="auth-service",
            team_name="Platform",
            acl=RawAcl(
                public=False, user_emails=["marcus@demo.dev", "elena@demo.dev", "admin@demo.dev"]
            ),
            metadata={
                "calendarId": "platform-team@demo.dev",
                "meeting_type": "architecture_review",
            },
            last_activity_at=demo_timestamp(25),
        ),
        RawItem(
            external_id="gcal-5004",
            doc_type="doc",
            title="search-svc rerank weights sync",
            content=(
                "Sync on the search-svc rerank weight revert proposal.\n\n"
                "Organizer: elena@demo.dev\n\n"
                "Attendees:\n"
                "- elena@demo.dev (accepted)\n"
                "- felix@demo.dev (accepted)\n"
                "- jade@demo.dev (declined)\n\n"
                "Growth is seeing relevance complaints against the v2 weights; decide "
                "whether to hold for the offline eval or revert to v1 now.\n\n"
                "Start: 2026-06-02T11:00:00-07:00\n"
                "End: 2026-06-02T11:30:00-07:00"
            ),
            url=f"{_BASE}/gcal-5004",
            author_email="elena@demo.dev",
            repo="search-svc",
            service="search-svc",
            team_name="Growth",
            acl=RawAcl(
                public=False, user_emails=["elena@demo.dev", "felix@demo.dev", "jade@demo.dev"]
            ),
            metadata={"calendarId": "growth-team@demo.dev", "meeting_type": "design_sync"},
            last_activity_at=demo_timestamp(3),
        ),
        RawItem(
            external_id="gcal-5005",
            doc_type="doc",
            title="mobile-bff canary review",
            content=(
                "Review canary results for the mobile-bff home feed caching rollout.\n\n"
                "Organizer: ines@demo.dev\n\n"
                "Attendees:\n"
                "- ines@demo.dev (accepted)\n"
                "- admin@demo.dev (accepted)\n\n"
                "Canary p95 down to 120ms with zero cache-invalidation misses; confirm "
                "promotion to 100% traffic.\n\n"
                "Start: 2026-06-10T15:00:00-07:00\n"
                "End: 2026-06-10T15:15:00-07:00"
            ),
            url=f"{_BASE}/gcal-5005",
            author_email="ines@demo.dev",
            repo="mobile-bff",
            service="mobile-bff",
            team_name="Mobile",
            acl=RawAcl(public=False, user_emails=["ines@demo.dev", "admin@demo.dev"]),
            metadata={"calendarId": "mobile-team@demo.dev", "meeting_type": "canary_review"},
            last_activity_at=demo_timestamp(1),
        ),
        RawItem(
            external_id="gcal-5006",
            doc_type="doc",
            title="Quarterly change freeze planning",
            content=(
                "Plan the quarterly change freeze window and approver rotation.\n\n"
                "Organizer: admin@demo.dev\n\n"
                "Attendees:\n"
                "- admin@demo.dev (accepted)\n"
                "- omar@demo.dev (accepted)\n"
                "- priya@demo.dev (tentative)\n"
                "- marcus@demo.dev (accepted)\n\n"
                "Only sev1/sev2 fixes ship during the freeze and need an SRE approver "
                "on the PR. Confirm the on-call rotation covering the freeze window.\n\n"
                "Start: 2026-05-29T09:30:00-07:00\n"
                "End: 2026-05-29T10:00:00-07:00"
            ),
            url=f"{_BASE}/gcal-5006",
            author_email="admin@demo.dev",
            repo=None,
            service=None,
            team_name="Platform",
            acl=RawAcl(
                public=False,
                user_emails=[
                    "admin@demo.dev",
                    "omar@demo.dev",
                    "priya@demo.dev",
                    "marcus@demo.dev",
                ],
            ),
            metadata={"calendarId": "platform-team@demo.dev", "meeting_type": "planning"},
            last_activity_at=demo_timestamp(11),
        ),
    ]


class GCalConnector:
    """Deterministic demo connector for the ``gcal`` source type."""

    source_type: ClassVar[str] = "gcal"

    async def fetch(self, source: Source) -> list[RawItem]:
        """Return the demo org's meeting fixtures (offline, deterministic)."""
        return _items()

    async def list_active_external_ids(self, source: Source) -> list[str]:
        """Return the external ids currently visible upstream (for pruning)."""
        return [item.external_id for item in await self.fetch(source)]


register(GCalConnector())
