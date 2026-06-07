"""create m2 prices table

Revision ID: 20260607_0003
Revises: 20260604_0002
Create Date: 2026-06-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260607_0003"
down_revision: str | None = "20260604_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("close_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.UniqueConstraint(
            "instrument_id",
            "price_date",
            "source",
            name="uq_prices_instrument_date_source",
        ),
        sa.CheckConstraint(
            "close_price >= 0",
            name="ck_prices_close_price_non_negative",
        ),
    )
    op.create_index(
        "ix_prices_instrument_date",
        "prices",
        ["instrument_id", "price_date"],
    )
    op.create_index("ix_prices_price_date", "prices", ["price_date"])


def downgrade() -> None:
    op.drop_index("ix_prices_price_date", table_name="prices")
    op.drop_index("ix_prices_instrument_date", table_name="prices")
    op.drop_table("prices")
