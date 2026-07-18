"""Unit tests for the offline demo Linear connector."""

from __future__ import annotations

from context_engine.connectors.base import DEMO_EPOCH, RawItem
from context_engine.connectors.linear import LinearConnector
from context_engine.storage import models as m

_connector = LinearConnector()


def _source() -> m.Source:
    return m.Source(type=m.SourceType.linear, name="linear demo")


async def test_source_type_is_linear() -> None:
    assert _connector.source_type == "linear"


async def test_fetch_returns_fixtures() -> None:
    items = await _connector.fetch(_source())
    assert 5 <= len(items) <= 8
    assert all(isinstance(item, RawItem) for item in items)


async def test_two_fetches_are_identical() -> None:
    first = await _connector.fetch(_source())
    second = await _connector.fetch(_source())
    assert first == second


async def test_external_ids_unique_and_linear_style() -> None:
    items = await _connector.fetch(_source())
    external_ids = [item.external_id for item in items]
    assert len(set(external_ids)) == len(external_ids)
    assert all(eid.startswith("ENG-") for eid in external_ids)


async def test_fields_populated() -> None:
    items = await _connector.fetch(_source())
    for item in items:
        assert item.doc_type == "ticket"
        assert m.DocType(item.doc_type)
        assert item.title and item.content and item.url
        assert item.author_email
        assert item.team_name
        assert item.metadata.get("identifier")
        assert item.metadata.get("state")
        assert item.last_activity_at.tzinfo is not None
        assert item.last_activity_at <= DEMO_EPOCH


async def test_list_active_external_ids_matches_fetch() -> None:
    items = await _connector.fetch(_source())
    active = await _connector.list_active_external_ids(_source())
    assert set(active) == {item.external_id for item in items}


async def test_timestamps_vary() -> None:
    items = await _connector.fetch(_source())
    ages = {(DEMO_EPOCH - item.last_activity_at).days for item in items}
    assert len(ages) > 1
