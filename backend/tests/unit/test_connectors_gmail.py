"""Unit tests for the demo Gmail connector (imported directly, no registry)."""

from __future__ import annotations

from context_engine.connectors.base import DEMO_EPOCH, RawItem
from context_engine.connectors.gmail import GmailConnector
from context_engine.storage import models as m

_CONNECTOR = GmailConnector()


def _source() -> m.Source:
    return m.Source(type=m.SourceType.gmail, name="gmail demo")


async def test_source_type() -> None:
    assert _CONNECTOR.source_type == "gmail"


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
        assert item.doc_type == "message"
        assert item.title
        assert item.content
        assert item.url
        assert item.last_activity_at.tzinfo is not None
        assert item.last_activity_at <= DEMO_EPOCH
        if not item.acl.public:
            assert item.acl.team_names or item.acl.user_emails


async def test_timestamps_vary() -> None:
    items = await _CONNECTOR.fetch(_source())
    ages = {(DEMO_EPOCH - item.last_activity_at).days for item in items}
    assert len(ages) > 1, "timestamps should vary across items"


async def test_all_items_are_private_with_user_emails() -> None:
    # Email is inherently private: demo fixtures must never be public, and since
    # there is no natural team scope for a mailbox they carry user_emails instead.
    items = await _CONNECTOR.fetch(_source())
    assert items
    assert all(not item.acl.public for item in items)
    assert all(item.acl.user_emails for item in items)


async def test_list_active_external_ids_matches_fetch() -> None:
    items = await _CONNECTOR.fetch(_source())
    ids = await _CONNECTOR.list_active_external_ids(_source())
    assert set(ids) == {item.external_id for item in items}
