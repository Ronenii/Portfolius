from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from alembic import command
from alembic.config import Config
from app.core.config import get_settings


def alembic_config(database_url: str) -> Config:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_m3_profile_goal_fields_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'm3_schema.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    columns = {column["name"] for column in inspect(engine).get_columns("profiles")}
    assert {
        "risk_tolerance",
        "interest_tags",
        "excluded_sectors",
        "goals_note",
    }.issubset(columns)

    command.downgrade(config, "20260607_0003")

    downgraded_columns = {
        column["name"] for column in inspect(engine).get_columns("profiles")
    }
    assert "risk_tolerance" not in downgraded_columns
    assert "interest_tags" not in downgraded_columns
    assert "excluded_sectors" not in downgraded_columns
    assert "goals_note" not in downgraded_columns
    get_settings.cache_clear()


def test_projection_profile_fields_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'projection_fields_schema.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    columns = {column["name"] for column in inspect(engine).get_columns("profiles")}
    assert {
        "goal_target_amount",
        "contribution_amount",
        "expected_annual_return",
    }.issubset(columns)

    command.downgrade(config, "20260707_0008")

    downgraded_columns = {
        column["name"] for column in inspect(engine).get_columns("profiles")
    }
    assert "goal_target_amount" not in downgraded_columns
    assert "contribution_amount" not in downgraded_columns
    assert "expected_annual_return" not in downgraded_columns
    get_settings.cache_clear()


def test_m3_assistant_tables_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'm3_assistant_schema.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "conversations" in inspector.get_table_names()
    assert "messages" in inspector.get_table_names()

    conversation_columns = {
        column["name"] for column in inspector.get_columns("conversations")
    }
    message_columns = {column["name"] for column in inspector.get_columns("messages")}
    assert {"id", "user_id", "title", "created_at", "updated_at"}.issubset(
        conversation_columns
    )
    assert {"id", "conversation_id", "role", "content", "created_at"}.issubset(
        message_columns
    )

    message_foreign_keys = inspector.get_foreign_keys("messages")
    assert message_foreign_keys[0]["referred_table"] == "conversations"

    conversation_indexes = {
        index["name"] for index in inspector.get_indexes("conversations")
    }
    message_indexes = {index["name"] for index in inspector.get_indexes("messages")}
    assert "ix_conversations_user_id" in conversation_indexes
    assert "ix_messages_conversation_id" in message_indexes
    assert "ix_messages_created_at" in message_indexes

    command.downgrade(config, "20260608_0004")

    downgraded_tables = inspect(engine).get_table_names()
    assert "conversations" not in downgraded_tables
    assert "messages" not in downgraded_tables
    get_settings.cache_clear()


def test_etf_exposure_data_correction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'etf_exposure.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "20260608_0005")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO instruments (symbol, exchange, country, region)
                VALUES
                  ('INDA', 'BATS', 'US', 'North America'),
                  ('INDA', 'LSE', 'India', 'Asia ex-Japan'),
                  ('CSPX', 'LSE', 'Ireland', 'Europe')
                """
            )
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT symbol, exchange, country, region
                FROM instruments
                ORDER BY symbol, exchange
                """
            )
        ).all()

    assert rows == [
        ("CSPX", "LSE", "United States", "North America"),
        ("INDA", "BATS", "India", "Asia ex-Japan"),
        ("INDA", "LSE", "India", "Asia ex-Japan"),
    ]
    get_settings.cache_clear()


def test_asia_region_normalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'asia_regions.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "20260621_0006")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO instruments (
                  symbol, name, exchange, asset_class, country, region
                )
                VALUES
                  (
                    'AAXJ',
                    'iShares MSCI All Country Asia ex Japan ETF',
                    'NASDAQ',
                    'ETF',
                    'US',
                    'Asia'
                  ),
                  (
                    'EWJ',
                    'iShares MSCI Japan ETF',
                    'NYSEARCA',
                    'ETF',
                    'JP',
                    'Asia'
                  ),
                  (
                    'TSM',
                    'Taiwan Semiconductor Manufacturing Company Limited',
                    'NYSE',
                    'ADR',
                    'TW',
                    'Asia'
                  )
                """
            )
        )

    command.upgrade(config, "head")

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT symbol, country, region
                FROM instruments
                ORDER BY symbol
                """
            )
        ).all()

    assert rows == [
        ("AAXJ", None, "Asia ex-Japan"),
        ("EWJ", "Japan", "Japan"),
        ("TSM", "Taiwan", "Asia ex-Japan"),
    ]
    get_settings.cache_clear()
