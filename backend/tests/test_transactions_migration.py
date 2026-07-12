from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from alembic import command
from alembic.config import Config
from app.core.config import get_settings
from app.domain.transactions import TransactionLeg, fold_transactions


def alembic_config(database_url: str) -> Config:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_transactions_table_created_with_indexes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'transactions_schema.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "transactions" in inspector.get_table_names()

    columns = {column["name"] for column in inspector.get_columns("transactions")}
    assert {
        "id",
        "user_id",
        "instrument_id",
        "action",
        "quantity",
        "price",
        "fees",
        "currency",
        "trade_date",
        "notes",
        "created_at",
        "updated_at",
    }.issubset(columns)

    index_names = {index["name"] for index in inspector.get_indexes("transactions")}
    assert "ix_transactions_user_id" in index_names
    assert "ix_transactions_user_instrument_trade_date_id" in index_names

    holdings_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("holdings")
    }
    assert "uq_holdings_user_instrument" in holdings_constraints

    command.downgrade(config, "20260621_0007")

    downgraded_tables = inspect(engine).get_table_names()
    assert "transactions" not in downgraded_tables
    downgraded_holdings_constraints = {
        constraint["name"]
        for constraint in inspect(engine).get_unique_constraints("holdings")
    }
    assert "uq_holdings_user_instrument" not in downgraded_holdings_constraints
    get_settings.cache_clear()


def test_migration_merges_duplicate_holdings_and_seeds_equivalent_transactions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'transactions_merge.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "20260621_0007")

    engine = create_engine(database_url)
    created_at = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC).isoformat(sep=" ")
    later_created_at = datetime(2026, 2, 10, 8, 30, 0, tzinfo=UTC).isoformat(sep=" ")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO instruments (symbol, exchange, currency)
                VALUES ('AAPL', 'NASDAQ', 'USD')
                """
            )
        )
        instrument_id = connection.execute(
            text("SELECT id FROM instruments WHERE symbol = 'AAPL'")
        ).scalar_one()

        # Two duplicate rows for the same (user_id, instrument_id) pair --
        # the exact scenario the merge must collapse before the unique
        # constraint can be added.
        connection.execute(
            text(
                """
                INSERT INTO holdings
                    (user_id, instrument_id, quantity, average_cost,
                     created_at, updated_at)
                VALUES
                    (:user_id, :instrument_id, 10, 100, :created_at, :created_at),
                    (:user_id, :instrument_id, 20, 130, :later, :later)
                """
            ),
            {
                "user_id": "user-dup",
                "instrument_id": instrument_id,
                "created_at": created_at,
                "later": later_created_at,
            },
        )
        # A lone, non-duplicated holding that should pass through untouched.
        connection.execute(
            text(
                """
                INSERT INTO holdings
                    (user_id, instrument_id, quantity, average_cost,
                     created_at, updated_at)
                VALUES (:user_id, :instrument_id, 5, 50, :created_at, :created_at)
                """
            ),
            {
                "user_id": "user-solo",
                "instrument_id": instrument_id,
                "created_at": created_at,
            },
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        merged_rows = connection.execute(
            text(
                """
                SELECT id, quantity, average_cost, created_at
                FROM holdings
                WHERE user_id = 'user-dup'
                """
            )
        ).all()
        solo_rows = connection.execute(
            text(
                """
                SELECT id, quantity, average_cost, created_at
                FROM holdings
                WHERE user_id = 'user-solo'
                """
            )
        ).all()

    # Duplicates collapsed into exactly one row.
    assert len(merged_rows) == 1
    merged = merged_rows[0]
    expected_quantity = Decimal("10") + Decimal("20")
    expected_average_cost = (
        Decimal("10") * Decimal("100") + Decimal("20") * Decimal("130")
    ) / expected_quantity
    assert Decimal(str(merged.quantity)) == expected_quantity
    assert Decimal(str(merged.average_cost)) == expected_average_cost
    assert merged.created_at.startswith("2026-01-05")

    # The untouched solo holding survives unchanged.
    assert len(solo_rows) == 1
    solo = solo_rows[0]
    assert Decimal(str(solo.quantity)) == Decimal("5")
    assert Decimal(str(solo.average_cost)) == Decimal("50")

    # Exactly one opening-balance transaction seeded per merged holding, and
    # folding it reproduces that holding's post-merge quantity/average_cost.
    with engine.connect() as connection:
        for user_id, holding_row in (
            ("user-dup", merged),
            ("user-solo", solo),
        ):
            tx_rows = connection.execute(
                text(
                    """
                    SELECT id, action, quantity, price, fees, trade_date, notes
                    FROM transactions
                    WHERE user_id = :user_id AND instrument_id = :instrument_id
                    """
                ),
                {"user_id": user_id, "instrument_id": instrument_id},
            ).all()

            assert len(tx_rows) == 1
            tx = tx_rows[0]
            assert tx.action == "buy"
            assert tx.notes == "Opening balance"

            legs = [
                TransactionLeg(
                    id=tx.id,
                    trade_date=datetime.strptime(tx.trade_date, "%Y-%m-%d").date(),
                    action=tx.action,
                    quantity=Decimal(str(tx.quantity)),
                    price=Decimal(str(tx.price)),
                    fees=Decimal(str(tx.fees)),
                )
            ]
            position = fold_transactions(legs)
            assert position.quantity == Decimal(str(holding_row.quantity))
            assert position.average_cost == Decimal(str(holding_row.average_cost))

    get_settings.cache_clear()


def test_migration_drops_duplicate_group_with_zero_net_quantity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'transactions_merge_zero.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "20260621_0007")

    engine = create_engine(database_url)
    created_at = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC).isoformat(sep=" ")
    later_created_at = datetime(2026, 2, 10, 8, 30, 0, tzinfo=UTC).isoformat(sep=" ")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO instruments (symbol, exchange, currency)
                VALUES ('AAPL', 'NASDAQ', 'USD')
                """
            )
        )
        instrument_id = connection.execute(
            text("SELECT id FROM instruments WHERE symbol = 'AAPL'")
        ).scalar_one()

        # Duplicate rows for the same (user_id, instrument_id) pair whose
        # quantities net out to exactly zero -- the merge must drop the
        # whole group rather than leave a phantom zero-quantity survivor.
        connection.execute(
            text(
                """
                INSERT INTO holdings
                    (user_id, instrument_id, quantity, average_cost,
                     created_at, updated_at)
                VALUES
                    (:user_id, :instrument_id, 10, 100, :created_at, :created_at),
                    (:user_id, :instrument_id, -10, 130, :later, :later)
                """
            ),
            {
                "user_id": "user-zero-net",
                "instrument_id": instrument_id,
                "created_at": created_at,
                "later": later_created_at,
            },
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        remaining_rows = connection.execute(
            text(
                """
                SELECT id FROM holdings WHERE user_id = 'user-zero-net'
                """
            )
        ).all()
        seeded_transactions = connection.execute(
            text(
                """
                SELECT id FROM transactions
                WHERE user_id = 'user-zero-net' AND instrument_id = :instrument_id
                """
            ),
            {"instrument_id": instrument_id},
        ).all()

    # No holdings row survives for the zero-net-quantity duplicate group, and
    # no opening-balance transaction is seeded for it.
    assert remaining_rows == []
    assert seeded_transactions == []

    get_settings.cache_clear()
