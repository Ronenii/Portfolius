"""create transactions table

Revision ID: 20260707_0008
Revises: 20260621_0007
Create Date: 2026-07-07

"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

revision: str = "20260707_0008"
down_revision: str | None = "20260621_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _holdings_table() -> sa.Table:
    return sa.table(
        "holdings",
        sa.column("id", sa.Integer()),
        sa.column("user_id", sa.String()),
        sa.column("instrument_id", sa.Integer()),
        sa.column("quantity", sa.Numeric(20, 8)),
        sa.column("average_cost", sa.Numeric(20, 8)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )


def _merge_duplicate_holdings() -> None:
    """Collapse duplicate (user_id, instrument_id) holdings rows that may
    predate the uq_holdings_user_instrument constraint into a single row:
    quantity is summed, average_cost is quantity-weighted across the group.

    Done in Python via Core (not a single portable SQL statement) because
    the weighted-average recompute isn't expressible identically across
    SQLite and Postgres in one UPDATE.
    """
    bind = op.get_bind()
    holdings = _holdings_table()

    rows = bind.execute(
        sa.select(
            holdings.c.id,
            holdings.c.user_id,
            holdings.c.instrument_id,
            holdings.c.quantity,
            holdings.c.average_cost,
            holdings.c.created_at,
        ).order_by(holdings.c.user_id, holdings.c.instrument_id, holdings.c.id)
    ).all()

    groups: dict[tuple[str, int], list] = {}
    for row in rows:
        groups.setdefault((row.user_id, row.instrument_id), []).append(row)

    for group_rows in groups.values():
        if len(group_rows) < 2:
            continue

        total_quantity = sum((r.quantity for r in group_rows), Decimal("0"))
        if total_quantity == 0:
            # Degenerate case (shouldn't occur for real holdings, which are
            # only ever written with a positive quantity): no meaningful
            # weighted average exists and there is nothing to hold, so drop
            # every row in the group rather than leaving a phantom
            # zero-quantity survivor behind.
            all_ids = [r.id for r in group_rows]
            bind.execute(sa.delete(holdings).where(holdings.c.id.in_(all_ids)))
            continue

        total_cost = sum(
            (r.quantity * r.average_cost for r in group_rows), Decimal("0")
        )
        weighted_average_cost = total_cost / total_quantity

        # Keep the earliest-created row as the survivor and its created_at,
        # so the merged row's "position opened" date is the true first
        # purchase date among the duplicates, not an arbitrary one.
        survivor = min(group_rows, key=lambda r: r.id)
        earliest_created_at = min(r.created_at for r in group_rows)
        duplicate_ids = [r.id for r in group_rows if r.id != survivor.id]

        bind.execute(
            sa.update(holdings)
            .where(holdings.c.id == survivor.id)
            .values(
                quantity=total_quantity,
                average_cost=weighted_average_cost,
                created_at=earliest_created_at,
            )
        )
        bind.execute(sa.delete(holdings).where(holdings.c.id.in_(duplicate_ids)))


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("fees", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.CheckConstraint(
            "action in ('buy', 'sell')",
            name="ck_transactions_action_valid",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_transactions_quantity_positive",
        ),
        sa.CheckConstraint(
            "price >= 0",
            name="ck_transactions_price_non_negative",
        ),
        sa.CheckConstraint(
            "fees >= 0",
            name="ck_transactions_fees_non_negative",
        ),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index(
        "ix_transactions_user_instrument_trade_date_id",
        "transactions",
        ["user_id", "instrument_id", "trade_date", "id"],
    )

    _merge_duplicate_holdings()

    with op.batch_alter_table("holdings") as batch_op:
        batch_op.create_unique_constraint(
            "uq_holdings_user_instrument", ["user_id", "instrument_id"]
        )

    # Seed one opening-balance "buy" transaction per (now-merged) holding so
    # that folding transactions reproduces the current holdings exactly.
    # trade_date uses DATE(h.created_at) rather than CAST(h.created_at AS
    # DATE): on SQLite, created_at is stored as ISO text (e.g.
    # "2026-07-09 07:36:40.455052"), and CAST(... AS DATE) applies SQLite's
    # generic NUMERIC-affinity conversion rules to that text -- verified
    # empirically to silently truncate it to the integer 2026, not a date.
    # SQLite's DATE(...) scalar function, and Postgres's identically-named
    # date(timestamp) function, both correctly return the calendar date in
    # both dialects, so DATE(...) is the portable choice here.
    # currency falls back to 'USD' only when instruments.currency is
    # genuinely NULL (the column is nullable) -- 'USD' matches the default
    # used throughout the app's tests/fixtures for an unset currency.
    op.execute(
        sa.text(
            """
            INSERT INTO transactions (
                user_id, instrument_id, action, quantity, price, fees,
                currency, trade_date, notes, created_at, updated_at
            )
            SELECT
                h.user_id,
                h.instrument_id,
                'buy',
                h.quantity,
                h.average_cost,
                0,
                COALESCE(i.currency, 'USD'),
                DATE(h.created_at),
                'Opening balance',
                h.created_at,
                h.created_at
            FROM holdings h
            JOIN instruments i ON i.id = h.instrument_id
            WHERE h.quantity > 0
            """
        )
    )


def downgrade() -> None:
    # The duplicate-holdings merge in upgrade() is a lossy, one-way data
    # migration: the original per-duplicate rows are gone and cannot be
    # reconstructed. Downgrade only reverses the structural changes -- the
    # seeded opening-balance transactions disappear along with the table,
    # and the new uniqueness constraint on holdings is dropped.
    op.drop_index(
        "ix_transactions_user_instrument_trade_date_id", table_name="transactions"
    )
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")

    with op.batch_alter_table("holdings") as batch_op:
        batch_op.drop_constraint("uq_holdings_user_instrument", type_="unique")
