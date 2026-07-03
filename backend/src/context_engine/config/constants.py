"""Shared constants used across the context engine."""

from __future__ import annotations

EMBEDDING_DIM = 384
"""Dimensionality of chunk embeddings (pgvector Vector column)."""

CHUNK_SIZE_CHARS = 600
"""Target chunk size, in characters, used by the chunker and seeds."""

DEFAULT_FRESHNESS_WINDOW_DAYS = 90
"""Default half-life window for the freshness score decay."""

DEFAULT_AUTHORITY_RANK = 50
"""Default source authority rank (0-100)."""

MAX_PACKET_TOKENS = 8000
"""Default token budget for compiled context packets."""

DEMO_API_KEYS = {
    "admin": "demo-admin-key",
    "lead": "demo-lead-key",
    "engineer": "demo-engineer-key",
    "viewer": "demo-viewer-key",
    "mcp": "demo-mcp-token",
}
"""Deterministic raw demo API keys (hashes are stored in the database)."""

# Seeded app_settings keys (see DATA_MODEL.md).
SETTINGS_RETRIEVAL_WEIGHTS = "retrieval_weights"
SETTINGS_FRESHNESS_WINDOW_DAYS = "freshness_window_days"
SETTINGS_AUTHORITY_RULES = "authority_rules"
SETTINGS_EVAL_THRESHOLDS = "eval_thresholds"
SETTINGS_RETENTION = "retention"
SETTINGS_PII_REDACTION = "pii_redaction"
SETTINGS_FEATURE_FLAGS = "feature_flags"
SETTINGS_TOKEN_BUDGET = "token_budget"
