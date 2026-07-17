"""drop profile expected annual return

Revision ID: 20260716_0011
Revises: 20260716_0010
Create Date: 2026-07-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0011"
down_revision: str | None = "20260716_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("profiles", "expected_annual_return")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("expected_annual_return", sa.Numeric(20, 8), nullable=True),
    )
