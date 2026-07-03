"""Table-driven tests for the rule-based intent classifier."""

from __future__ import annotations

import pytest

from context_engine.reasoning.intent import IntentType, classify_intent

CASES: list[tuple[str, IntentType]] = [
    # bugfix
    ("Fix duplicate charge when webhook retries overlap", IntentType.bugfix),
    ("There is a bug in the pagination helper", IntentType.bugfix),
    ("Payments service crashes on empty payload", IntentType.bugfix),
    ("The retry helper is broken after the deploy", IntentType.bugfix),
    ("Resolve p95 latency regression in the list endpoint", IntentType.bugfix),
    ("500 error on POST /v1/payments/charge", IntentType.bugfix),
    # incident_response
    ("Mitigate the payments outage and page the on-call", IntentType.incident_response),
    ("Draft the postmortem for INC-2107", IntentType.incident_response),
    ("Sev1: checkout is down for all users", IntentType.incident_response),
    ("Respond to the incident in auth-service", IntentType.incident_response),
    # refactor
    ("Refactor the webhook handler into verify/enqueue stages", IntentType.refactor),
    ("Cleanup deprecated feature flags in billing-worker", IntentType.refactor),
    ("Restructure the config loader module", IntentType.refactor),
    ("Migrate the retry helper to the shared library", IntentType.refactor),
    # feature
    ("Add cursor pagination to search results", IntentType.feature),
    ("Implement idempotency keys for mutation endpoints", IntentType.feature),
    ("Build a canary rollout dashboard", IntentType.feature),
    ("Introduce outbox-based event publishing", IntentType.feature),
    ("Ship the new checkout flow behind a flag", IntentType.feature),
    # question
    ("How do we deploy the billing worker?", IntentType.question),
    ("What is the current retry policy for payments?", IntentType.question),
    ("Why is the token TTL 15 minutes", IntentType.question),
    ("Where does the outbox worker publish events", IntentType.question),
    ("Is cursor pagination mandatory?", IntentType.question),
    # unknown
    ("", IntentType.unknown),
    ("   ", IntentType.unknown),
    ("Payments latency dashboards", IntentType.unknown),
]


@pytest.mark.parametrize(("task", "expected"), CASES)
def test_classify_intent(task: str, expected: IntentType) -> None:
    assert classify_intent(task) is expected


PRIORITY_CASES: list[tuple[str, IntentType]] = [
    # incident_response outranks bugfix
    ("Write the postmortem for the retry bug", IntentType.incident_response),
    ("Fix the outage in auth-service", IntentType.incident_response),
    # bugfix outranks refactor / feature / question
    ("Refactor and fix the broken retry helper", IntentType.bugfix),
    ("Add a fix for the crash in checkout", IntentType.bugfix),
    ("Why does the service crash on startup?", IntentType.bugfix),
    # refactor outranks feature
    ("Add tests while we refactor the config loader", IntentType.refactor),
    # feature outranks question
    ("How should we implement dark mode?", IntentType.feature),
    # bare question mark falls back to question
    ("Retry policy for payments?", IntentType.question),
]


@pytest.mark.parametrize(("task", "expected"), PRIORITY_CASES)
def test_classify_intent_priority(task: str, expected: IntentType) -> None:
    assert classify_intent(task) is expected


def test_deterministic_and_case_insensitive() -> None:
    task = "FIX THE BROKEN WEBHOOK"
    assert classify_intent(task) is IntentType.bugfix
    assert all(classify_intent(task) is IntentType.bugfix for _ in range(5))
