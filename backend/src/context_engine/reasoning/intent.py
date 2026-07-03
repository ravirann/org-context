"""Rule/keyword-based task intent classification (deterministic, no ML).

Priority order (first match wins):
    1. incident_response — incident/outage/sev*/postmortem/down
    2. bugfix           — fix/bug/error/crash/broken/regression
    3. refactor         — refactor/cleanup/clean up/restructure/migrate
    4. feature          — add/implement/build/support/new/introduce/ship/create/enable
    5. question         — how/why/what/where/which/who/when or a trailing "?"
    6. unknown          — fallback

Incident language outranks bugfix language ("postmortem for the retry bug" is an
incident response), bugfix outranks question ("why does it crash?" is a bugfix),
and question is last so interrogative phrasing never masks an actionable verb.
"""

from __future__ import annotations

import re

from context_engine.storage.models import Intent as IntentType

_PATTERNS: list[tuple[IntentType, re.Pattern[str]]] = [
    (
        IntentType.incident_response,
        re.compile(r"\b(incidents?|outages?|sev\s?\d?|postmortems?|post-mortems?|down)\b"),
    ),
    (
        IntentType.bugfix,
        re.compile(
            r"\b(fix(?:es|ed|ing)?|bugs?|bugfix(?:es)?|errors?|crash(?:es|ed|ing)?"
            r"|broken|regress(?:ions?|ed))\b"
        ),
    ),
    (
        IntentType.refactor,
        re.compile(
            r"\b(refactor(?:s|ed|ing)?|cleanups?|clean\s+up|restructur(?:e|es|ed|ing)"
            r"|migrat(?:e|es|ed|ing))\b"
        ),
    ),
    (
        IntentType.feature,
        re.compile(
            r"\b(add(?:s|ed|ing)?|implement(?:s|ed|ing)?|build(?:s|ing)?|support(?:s|ing)?"
            r"|new|introduc(?:e|es|ed|ing)|ship(?:s|ped|ping)?|creat(?:e|es|ed|ing)"
            r"|enabl(?:e|es|ed|ing))\b"
        ),
    ),
    (
        IntentType.question,
        re.compile(r"\b(how|why|what|where|which|who|when)\b"),
    ),
]


def classify_intent(task: str) -> IntentType:
    """Classify a task string into an :class:`IntentType` (see module docstring)."""
    text = task.lower().strip()
    if not text:
        return IntentType.unknown
    for intent, pattern in _PATTERNS:
        if pattern.search(text):
            return intent
    if "?" in text:
        return IntentType.question
    return IntentType.unknown
