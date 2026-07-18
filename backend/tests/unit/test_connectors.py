"""Unit tests for the demo connectors and the connector registry."""

from __future__ import annotations

import pytest

from context_engine.connectors import (
    ALL_SOURCE_TYPES,
    DEMO_EPOCH,
    RawItem,
    get_connector,
)
from context_engine.storage import models as m

EXPECTED_DOC_TYPES: dict[str, set[str]] = {
    "github": {"pr", "code"},
    "jira": {"ticket"},
    "slack": {"message"},
    "confluence": {"doc"},
    "adr": {"adr"},
    "incident": {"incident"},
    "ci": {"ci_run"},
    "feedback": {"feedback"},
    "notion": {"doc"},
    "linear": {"ticket"},
    "zendesk": {"ticket"},
    "gdrive": {"doc"},
    "gmail": {"message"},
    "gcal": {"doc"},
}


def _dummy_source(source_type: str) -> m.Source:
    return m.Source(type=m.SourceType(source_type), name=f"{source_type} demo")


async def _fetch(source_type: str) -> list[RawItem]:
    return await get_connector(source_type).fetch(_dummy_source(source_type))


async def test_all_source_types_have_a_connector() -> None:
    assert set(ALL_SOURCE_TYPES) == {t.value for t in m.SourceType}
    for source_type in ALL_SOURCE_TYPES:
        connector = get_connector(source_type)
        assert connector.source_type == source_type
        assert callable(connector.fetch)


def test_get_connector_unknown_type_raises() -> None:
    with pytest.raises(ValueError, match="No connector registered"):
        get_connector("gitlab")


def test_get_connector_accepts_enum() -> None:
    assert get_connector(m.SourceType.github).source_type == "github"


@pytest.mark.parametrize("source_type", ALL_SOURCE_TYPES)
async def test_connector_returns_valid_items(source_type: str) -> None:
    items = await _fetch(source_type)

    assert 6 <= len(items) <= 12
    external_ids = [item.external_id for item in items]
    assert len(set(external_ids)) == len(external_ids), "external ids must be unique"

    for item in items:
        assert m.DocType(item.doc_type)  # valid doc type
        assert item.doc_type in EXPECTED_DOC_TYPES[source_type]
        assert item.title and item.content and item.url
        assert item.last_activity_at.tzinfo is not None
        assert item.last_activity_at <= DEMO_EPOCH
        if not item.acl.public:
            assert item.acl.team_names or item.acl.user_emails


@pytest.mark.parametrize("source_type", ALL_SOURCE_TYPES)
async def test_connector_is_deterministic(source_type: str) -> None:
    first = await _fetch(source_type)
    second = await _fetch(source_type)
    assert first == second


async def test_timestamps_spread_over_past_year() -> None:
    for source_type in ALL_SOURCE_TYPES:
        items = await _fetch(source_type)
        ages = [(DEMO_EPOCH - item.last_activity_at).days for item in items]
        assert all(0 <= age <= 366 for age in ages)
        assert len(set(ages)) > 1, "timestamps should vary within a source"


async def test_acl_variety_across_connectors() -> None:
    all_items = [item for st in ALL_SOURCE_TYPES for item in await _fetch(st)]

    public = [i for i in all_items if i.acl.public]
    team_restricted = [i for i in all_items if not i.acl.public and i.acl.team_names]
    user_restricted = [i for i in all_items if not i.acl.public and i.acl.user_emails]

    assert len(public) > len(all_items) * 0.7, "most items should be public"
    assert len(team_restricted) >= 2
    assert len(user_restricted) >= 1
    restricted_teams = {name for i in team_restricted for name in i.acl.team_names}
    assert restricted_teams & {"Payments", "Platform"}


async def test_topic_keys_and_stances_exist_for_conflict_detection() -> None:
    all_items = [item for st in ALL_SOURCE_TYPES for item in await _fetch(st)]
    by_topic: dict[str, set[str]] = {}
    for item in all_items:
        if item.topic_key and item.metadata.get("stance"):
            by_topic.setdefault(item.topic_key, set()).add(item.metadata["stance"])
    divergent = {k: v for k, v in by_topic.items() if len(v) > 1}
    assert divergent, "at least one topic_key must have divergent stances across sources"
    assert "payments-retry-policy" in divergent


async def test_github_items_carry_pr_metadata() -> None:
    items = await _fetch("github")
    prs = [i for i in items if i.doc_type == "pr"]
    assert prs and all(
        isinstance(i.metadata.get("pr_number"), int) and i.metadata.get("labels") for i in prs
    )


async def test_source_specific_metadata() -> None:
    assert all(i.metadata.get("severity") for i in await _fetch("jira"))
    assert all(i.metadata.get("channel") for i in await _fetch("slack"))
    assert all(i.metadata.get("stance") for i in await _fetch("adr"))
    incidents = await _fetch("incident")
    assert all(i.metadata.get("severity") and i.metadata.get("caused_by") for i in incidents)
    assert all(i.metadata.get("status") in {"pass", "fail"} for i in await _fetch("ci"))
