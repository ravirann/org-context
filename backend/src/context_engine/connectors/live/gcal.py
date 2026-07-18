"""Live Google Calendar connector: attendee-scoped meetings via the Calendar API.

Authenticates as a Google service account impersonating ``config["subject"]``
(domain-wide delegation) using the shared :class:`GoogleServiceAccountAuth` helper,
then lists events per configured calendar via ``GET .../calendars/{id}/events``
ordered by ``updated``. Each configured calendar keeps its own cursor
(``updated_cursor:<calendarId>``) so one calendar's failure never loses another's
items — mirroring the live Slack connector's per-channel cursor isolation.

Meetings are attendee-scoped by default: unless the source config sets an explicit
``team_name``/``restrict_to_team``, every emitted item carries a ``user_emails`` ACL
of the impersonated subject plus the event's attendees. This connector never emits
a public ACL.
"""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from context_engine.connectors.base import RawAcl, RawItem
from context_engine.connectors.live.google import GoogleServiceAccountAuth
from context_engine.connectors.live.http import (
    ConnectorAuthError,
    ConnectorError,
    build_client,
    request_json,
)
from context_engine.connectors.live.util import (
    cursor_since,
    now_utc,
    parse_iso,
    resolve_acl,
    to_iso,
)
from context_engine.observability.logging import get_logger
from context_engine.storage.models import Source

logger = get_logger(__name__)

DEFAULT_API_URL = "https://www.googleapis.com"
_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
_MAX_RESULTS = 100
_MAX_ATTENDEE_EMAILS = 20
_CANCELLED_STATUS = "cancelled"


class GCalLiveConnector:
    """Fetch calendar events (per configured calendar) since each calendar's cursor."""

    source_type: ClassVar[str] = "gcal"

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _client(self, source: Source) -> httpx.AsyncClient:
        api_url = str(source.config.get("api_url") or DEFAULT_API_URL).rstrip("/")
        return build_client(base_url=api_url, transport=self._transport)

    async def fetch(self, source: Source) -> list[RawItem]:
        config = source.config
        subject = config.get("subject")
        if not subject:
            raise ConnectorAuthError(
                "gcal live connector requires config['subject'] "
                "(the calendar user to impersonate via domain-wide delegation)"
            )
        subject = str(subject)
        calendar_ids = [str(c) for c in (config.get("calendar_ids") or ["primary"])]
        auth = GoogleServiceAccountAuth(
            str(config["service_account_json"]), scopes=[_SCOPE], subject=subject
        )

        items: list[RawItem] = []
        async with self._client(source) as client:
            for calendar_id in calendar_ids:
                cursor_key = f"updated_cursor:{calendar_id}"
                since = cursor_since(source.sync_state, cursor_key, config)

                try:
                    token = await auth.access_token(client)
                    events = await self._list_events(client, token, calendar_id, since)
                except ConnectorAuthError:
                    # Credential/config failures are fatal for the whole sync, not
                    # just one calendar — surface them immediately.
                    raise
                except ConnectorError as exc:
                    logger.warning(
                        "gcal_calendar_fetch_failed", calendar_id=calendar_id, error=str(exc)
                    )
                    continue

                max_updated = since
                for event in events:
                    updated = (
                        parse_iso(str(event.get("updated") or ""))
                        if isinstance(event, dict)
                        else None
                    )
                    if updated is not None and updated > max_updated:
                        max_updated = updated
                    item = self._event_item(event, calendar_id, config, subject)
                    if item is not None:
                        items.append(item)
                source.sync_state[cursor_key] = to_iso(max_updated)

        return items

    async def _list_events(
        self, client: httpx.AsyncClient, token: str, calendar_id: str, since: Any
    ) -> list[dict[str, Any]]:
        payload = await request_json(
            client,
            "GET",
            f"/calendar/v3/calendars/{calendar_id}/events",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "updatedMin": to_iso(since),
                "orderBy": "updated",
                "maxResults": _MAX_RESULTS,
                "showDeleted": False,
            },
        )
        events = payload.get("items") if isinstance(payload, dict) else None
        return events if isinstance(events, list) else []

    def _event_item(
        self,
        event: Any,
        calendar_id: str,
        config: dict[str, Any],
        subject: str,
    ) -> RawItem | None:
        if not isinstance(event, dict):
            logger.warning("gcal_event_malformed", calendar_id=calendar_id)
            return None
        if event.get("status") == _CANCELLED_STATUS:
            return None

        event_id = event.get("id")
        start = event.get("start")
        if not event_id or not start:
            logger.warning("gcal_event_malformed", calendar_id=calendar_id, keys=list(event))
            return None

        organizer = event.get("organizer")
        organizer_email = organizer.get("email") if isinstance(organizer, dict) else None
        attendees_raw = event.get("attendees")
        attendees = [
            a
            for a in (attendees_raw if isinstance(attendees_raw, list) else [])
            if isinstance(a, dict) and a.get("email")
        ]

        title = str(event.get("summary") or "(no title)")
        content = _render_content(event, organizer_email, attendees)
        url = str(
            event.get("htmlLink") or f"https://calendar.google.com/calendar/event?eid={event_id}"
        )
        updated = parse_iso(str(event.get("updated") or "")) or now_utc()
        attendee_emails = [str(a["email"]) for a in attendees]
        acl = _resolve_event_acl(config, subject, attendee_emails)

        return RawItem(
            external_id=f"{calendar_id}:{event_id}",
            doc_type="doc",
            title=title,
            content=content,
            url=url,
            author_email=str(organizer_email) if organizer_email else None,
            acl=acl,
            metadata={"calendarId": calendar_id, "start": start, "end": event.get("end")},
            last_activity_at=updated,
        )


def _render_content(
    event: dict[str, Any], organizer_email: str | None, attendees: list[dict[str, Any]]
) -> str:
    lines: list[str] = []
    description = event.get("description")
    if description:
        lines.append(str(description).strip())
    if organizer_email:
        lines.append(f"Organizer: {organizer_email}")
    if attendees:
        attendee_lines = "\n".join(
            f"- {a['email']} ({a.get('responseStatus') or 'needsAction'})" for a in attendees
        )
        lines.append(f"Attendees:\n{attendee_lines}")
    start_str = _format_when(event.get("start"))
    if start_str:
        lines.append(f"Start: {start_str}")
    end_str = _format_when(event.get("end"))
    if end_str:
        lines.append(f"End: {end_str}")
    if not lines:
        return str(event.get("summary") or "(no title)")
    return "\n\n".join(lines)


def _format_when(when: Any) -> str:
    if not isinstance(when, dict):
        return ""
    date_time = when.get("dateTime")
    if date_time:
        return str(date_time)
    date = when.get("date")
    if date:
        return f"{date} (all-day)"
    return ""


def _resolve_event_acl(config: dict[str, Any], subject: str, attendee_emails: list[str]) -> RawAcl:
    """Team-scope the ACL only when the source explicitly configures a team.

    Otherwise the event stays attendee-scoped: the impersonated subject plus up
    to ``_MAX_ATTENDEE_EMAILS`` attendee emails. Never returns a public ACL.
    """
    team_acl = resolve_acl(config, private=True)
    if not team_acl.public:
        return team_acl
    emails = _dedup_emails([subject, *attendee_emails])[: 1 + _MAX_ATTENDEE_EMAILS]
    return RawAcl(public=False, user_emails=emails)


def _dedup_emails(emails: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for email in emails:
        if email and email not in seen:
            seen.add(email)
            out.append(email)
    return out
