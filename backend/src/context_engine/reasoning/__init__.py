"""Reasoning: intent classification, scoring and conflict detection."""

from context_engine.reasoning.conflicts import (
    conflicts_for_documents,
    detect_and_persist_conflicts,
    token_jaccard,
)
from context_engine.reasoning.intent import IntentType, classify_intent
from context_engine.reasoning.scoring import (
    authority_from_rank,
    freshness_score,
    packet_confidence,
)

__all__ = [
    "IntentType",
    "authority_from_rank",
    "classify_intent",
    "conflicts_for_documents",
    "detect_and_persist_conflicts",
    "freshness_score",
    "packet_confidence",
    "token_jaccard",
]
