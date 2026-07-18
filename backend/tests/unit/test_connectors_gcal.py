"""Unit tests for the demo Google Calendar connector (imported directly, no registry)."""

from __future__ import annotations

from context_engine.connectors.base import DEMO_EPOCH, RawItem
from context_engine.connectors.gcal import GCalConnector
from context_engine.storage import models as m

_CONNECTOR = GCalConnector()


def _source() -> m.Source:
    return m.Source(type=m.SourceType.gcal, name="gcal demo")


async def test_source_type() -> None:
    assert _CONNECTOR.source_type == "gcal"


async def test_fetch_returns_fixtures() -> None:
    items = await _CONNECTOR.fetch(_source())
    assert 5 <= len(items) <= 8
    assert all(isinstance(item, RawItem) for item in items)
    external_ids = [item.external_id for item in items]
    assert len(set(external_ids)) == len(external_ids), "external ids must be unique"


async def test_fetch_is_deterministic() -> None:
    first = await _CONNECTOR.fetch(_source())
    second = await _CONNECTOR.fetch(_source())
    assert first == second


async def test_fields_populated() -> None:
    items = await _CONNECTOR.fetch(_source())
    for item in items:
        assert m.DocType(item.doc_type)  # valid doc type
        assert item.doc_type == "doc"
        assert item.title
        assert item.content
        assert item.url
        assert item.last_activity_at.tzinfo is not None
        assert item.last_activity_at <= DEMO_EPOCH


async def test_timestamps_vary() -> None:
    items = await _CONNECTOR.fetch(_source())
    ages = {(DEMO_EPOCH - item.last_activity_at).days for item in items}
    assert len(ages) > 1, "timestamps should vary across items"


async def test_meetings_are_attendee_scoped_not_public() -> None:
    items = await _CONNECTOR.fetch(_source())
    # Meetings are attendee-scoped by default: every demo fixture is non-public
    # and carries plausible attendee emails (never bare team-only restriction).
    assert items
    for item in items:
        assert item.acl.public is False
        assert item.acl.user_emails or item.acl.team_names


async def test_narrative_meeting_titles_present() -> None:
    titles = " ".join(item.title.lower() for item in await _CONNECTOR.fetch(_source()))
    assert "sprint planning" in titles
    assert "retro" in titles
    assert "architecture review" in titles


async def test_list_active_external_ids_matches_fetch() -> None:
    items = await _CONNECTOR.fetch(_source())
    ids = await _CONNECTOR.list_active_external_ids(_source())
    assert set(ids) == {item.external_id for item in items}
