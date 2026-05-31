"""create app health checks table

Revision ID: 20260531_0001
Revises:
Create Date: 2026-05-31

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260531_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_health_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_health_checks")
