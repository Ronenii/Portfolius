from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

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
