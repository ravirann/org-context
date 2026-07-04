"""auth: users.external_subject + users.last_login_at

Revision ID: 0002_auth
Revises: 730e5b7a2104
Create Date: 2026-07-04 09:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_auth"
down_revision: str | None = "730e5b7a2104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("external_subject", sa.String(length=320), nullable=True))
    op.add_column(
        "users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "uq_users_external_subject", "users", ["external_subject"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_users_external_subject", table_name="users")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "external_subject")
