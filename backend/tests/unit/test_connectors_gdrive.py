"""Unit tests for the offline demo Google Drive connector.

Imports the connector module directly (not via ``get_connector`` or the
registry) so this test is independent of registry wiring.
"""

from __future__ import annotations

from context_engine.connectors.base import DEMO_EPOCH, RawItem
from context_engine.connectors.gdrive import GDriveConnector
from context_engine.storage import models as m

_EXPECTED_DOC_TYPES = {"doc"}


def _source() -> m.Source:
    return m.Source(type=m.SourceType.gdrive, name="gdrive demo")


async def _fetch() -> list[RawItem]:
    return await GDriveConnector().fetch(_source())


def test_source_type() -> None:
    assert GDriveConnector.source_type == "gdrive"


async def test_fetch_returns_fixtures() -> None:
    items = await _fetch()

    assert 5 <= len(items) <= 8
    external_ids = [item.external_id for item in items]
    assert len(set(external_ids)) == len(external_ids), "external ids must be unique"

    for item in items:
        assert m.DocType(item.doc_type)  # valid doc type
        assert item.doc_type in _EXPECTED_DOC_TYPES
        assert item.title and item.content and item.url
        assert item.last_activity_at.tzinfo is not None
        assert item.last_activity_at <= DEMO_EPOCH
        if not item.acl.public:
            assert item.acl.team_names or item.acl.user_emails


async def test_fetch_is_deterministic() -> None:
    first = await _fetch()
    second = await _fetch()
    assert first == second


async def test_timestamps_vary() -> None:
    items = await _fetch()
    ages = {(DEMO_EPOCH - item.last_activity_at).days for item in items}
    assert len(ages) > 1, "timestamps should vary across items"


async def test_at_least_one_restricted_item() -> None:
    items = await _fetch()
    restricted = [item for item in items if not item.acl.public]
    assert restricted
    assert all(item.acl.team_names for item in restricted)


async def test_fields_carry_mime_type_metadata() -> None:
    items = await _fetch()
    assert all(item.metadata.get("mimeType") for item in items)


async def test_list_active_external_ids_matches_fetch() -> None:
    connector = GDriveConnector()
    source = _source()
    items = await connector.fetch(source)
    active = await connector.list_active_external_ids(source)
    assert set(active) == {item.external_id for item in items}
