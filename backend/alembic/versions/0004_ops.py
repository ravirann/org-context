"""ingestion ops: sync_runs, search_events, content_hash, embedding_version

Adds:
  - ``sync_runs``     — per-sync telemetry (trigger, status, counts, errors).
  - ``search_events`` — retrieval telemetry (query, counts, timing, cache hit).
  - ``documents.content_hash``  — sha256(title+"\\n"+content) for unchanged skip.
  - ``chunks.embedding_version`` — provider/model that produced the embedding.

Revision ID: 0004_ops
Revises: 0003_connector_state
Create Date: 2026-07-04 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_ops"
down_revision: str | None = "0003_connector_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "chunks",
        sa.Column(
            "embedding_version",
            sa.String(length=100),
            nullable=False,
            server_default="deterministic/sha256-v1",
        ),
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "trigger",
            sa.Enum(
                "manual",
                "scheduled",
                name="sync_trigger",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "running",
                "ok",
                "error",
                name="sync_run_status",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("docs_upserted", sa.Integer(), nullable=False),
        sa.Column("docs_skipped", sa.Integer(), nullable=False),
        sa.Column("docs_pruned", sa.Integer(), nullable=False),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_source_id", "sync_runs", ["source_id"])
    op.create_index("ix_sync_runs_created_at", "sync_runs", ["created_at"])

    op.create_table(
        "search_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("acl_blocked_count", sa.Integer(), nullable=False),
        sa.Column("took_ms", sa.Float(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("top_document_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_events_query", "search_events", ["query"])
    op.create_index("ix_search_events_created_at", "search_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_search_events_created_at", table_name="search_events")
    op.drop_index("ix_search_events_query", table_name="search_events")
    op.drop_table("search_events")
    op.drop_index("ix_sync_runs_created_at", table_name="sync_runs")
    op.drop_index("ix_sync_runs_source_id", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_column("chunks", "embedding_version")
    op.drop_column("documents", "content_hash")
