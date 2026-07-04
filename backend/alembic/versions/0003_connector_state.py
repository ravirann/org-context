"""connector sync_state

Adds ``sources.sync_state`` (JSONB NOT NULL DEFAULT '{}') for incremental live
connector cursors. Demo connectors ignore it; live connectors read+advance
per-stream cursors stored here.

Revision ID: 0003_connector_state
Revises: 0002_auth
Create Date: 2026-07-04 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_connector_state"
down_revision: str | None = "0002_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "sync_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sources", "sync_state")
