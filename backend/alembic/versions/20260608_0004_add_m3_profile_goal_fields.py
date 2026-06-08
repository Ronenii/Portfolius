"""add m3 profile goal fields

Revision ID: 20260608_0004
Revises: 20260607_0003
Create Date: 2026-06-08

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260608_0004"
down_revision: str | None = "20260607_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("risk_tolerance", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "interest_tags",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "excluded_sectors",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )
    op.add_column(
        "profiles",
        sa.Column("goals_note", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profiles", "goals_note")
    op.drop_column("profiles", "excluded_sectors")
    op.drop_column("profiles", "interest_tags")
    op.drop_column("profiles", "risk_tolerance")
