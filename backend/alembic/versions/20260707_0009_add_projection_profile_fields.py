"""add projection profile fields

Revision ID: 20260707_0009
Revises: 20260707_0008
Create Date: 2026-07-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260707_0009"
down_revision: str | None = "20260707_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("goal_target_amount", sa.Numeric(20, 8), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("contribution_amount", sa.Numeric(20, 8), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column("expected_annual_return", sa.Numeric(20, 8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "expected_annual_return")
    op.drop_column("profiles", "contribution_amount")
    op.drop_column("profiles", "goal_target_amount")
