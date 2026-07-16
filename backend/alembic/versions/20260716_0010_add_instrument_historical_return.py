"""add instrument historical return

Revision ID: 20260716_0010
Revises: 20260707_0009
Create Date: 2026-07-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0010"
down_revision: str | None = "20260707_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("historical_annual_return", sa.Numeric(20, 8), nullable=True),
    )
    op.add_column(
        "instruments",
        sa.Column(
            "historical_return_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("instruments", "historical_return_updated_at")
    op.drop_column("instruments", "historical_annual_return")
