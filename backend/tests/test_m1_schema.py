from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.data.models import Base, Holding, Instrument, Profile


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        yield session


def test_metadata_contains_m1_tables() -> None:
    assert {"profiles", "instruments", "holdings"}.issubset(Base.metadata.tables)


def test_profile_can_be_inserted_and_queried_by_user_id(db_session: Session) -> None:
    profile = Profile(
        user_id="user-123",
        display_name="Ronen",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="monthly",
    )

    db_session.add(profile)
    db_session.commit()

    saved_profile = db_session.scalar(
        select(Profile).where(Profile.user_id == "user-123")
    )
    assert saved_profile is not None
    assert saved_profile.display_name == "Ronen"
    assert saved_profile.base_currency == "USD"


def test_holding_can_be_inserted_with_linked_instrument(
    db_session: Session,
) -> None:
    instrument = Instrument(
        symbol="VOO",
        name="Vanguard S&P 500 ETF",
        exchange="NYSEARCA",
        currency="USD",
        asset_class="equity",
        sector="broad market",
        country="US",
        region="North America",
    )
    holding = Holding(
        user_id="user-123",
        instrument=instrument,
        quantity=Decimal("3.25"),
        average_cost=Decimal("421.50"),
    )

    db_session.add(holding)
    db_session.commit()

    saved_holding = db_session.scalar(
        select(Holding).where(Holding.user_id == "user-123")
    )
    assert saved_holding is not None
    assert saved_holding.instrument.symbol == "VOO"
    assert saved_holding.quantity == Decimal("3.25")
    assert saved_holding.average_cost == Decimal("421.50")


def test_duplicate_profile_user_id_fails(db_session: Session) -> None:
    first_profile = Profile(
        user_id="user-123",
        display_name="Ronen",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="monthly",
    )
    duplicate_profile = Profile(
        user_id="user-123",
        display_name="Ron",
        base_currency="USD",
        time_horizon="5 years",
        investment_frequency="weekly",
    )

    db_session.add_all([first_profile, duplicate_profile])

    with pytest.raises(IntegrityError):
        db_session.commit()
