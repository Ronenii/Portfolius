"""create m1 profile holdings tables

Revision ID: 20260604_0002
Revises: 20260531_0001
Create Date: 2026-06-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260604_0002"
down_revision: str | None = "20260531_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("time_horizon", sa.String(length=120), nullable=False),
        sa.Column("investment_frequency", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_profiles_user_id"),
    )
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("exchange", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("asset_class", sa.String(length=80), nullable=True),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("metadata_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "symbol",
            "exchange",
            name="uq_instruments_symbol_exchange",
        ),
    )
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("average_cost", sa.Numeric(20, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
    )
    op.create_index("ix_holdings_user_id", "holdings", ["user_id"])
    op.create_index("ix_holdings_instrument_id", "holdings", ["instrument_id"])


def downgrade() -> None:
    op.drop_index("ix_holdings_instrument_id", table_name="holdings")
    op.drop_index("ix_holdings_user_id", table_name="holdings")
    op.drop_table("holdings")
    op.drop_table("instruments")
    op.drop_table("profiles")
