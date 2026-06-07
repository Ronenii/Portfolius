from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.data import models
from app.data.models import Base, Instrument


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        yield session


def require_price_model() -> type:
    price_model = getattr(models, "Price", None)
    assert price_model is not None, "Price model should be defined for M2"
    return price_model


def create_instrument(db_session: Session) -> Instrument:
    instrument = Instrument(
        symbol="VOO",
        name="Vanguard S&P 500 ETF",
        exchange="NYSEARCA",
        currency="USD",
        asset_class="ETF",
        sector="Broad Market",
        country="United States",
        region="North America",
    )
    db_session.add(instrument)
    db_session.commit()
    return instrument


def test_metadata_contains_prices_table() -> None:
    require_price_model()

    assert "prices" in Base.metadata.tables


def test_price_can_be_inserted_and_queried_by_instrument(
    db_session: Session,
) -> None:
    price_model = require_price_model()
    instrument = create_instrument(db_session)
    price = price_model(
        instrument=instrument,
        price_date=date(2026, 6, 5),
        close_price=Decimal("500.25"),
        currency="USD",
        source="yfinance",
    )

    db_session.add(price)
    db_session.commit()

    saved_price = db_session.scalar(
        select(price_model).where(price_model.instrument_id == instrument.id)
    )
    assert saved_price is not None
    assert saved_price.instrument.symbol == "VOO"
    assert saved_price.price_date == date(2026, 6, 5)
    assert saved_price.close_price == Decimal("500.25")
    assert saved_price.currency == "USD"
    assert saved_price.source == "yfinance"


def test_duplicate_price_for_same_instrument_date_and_source_fails(
    db_session: Session,
) -> None:
    price_model = require_price_model()
    instrument = create_instrument(db_session)
    first_price = price_model(
        instrument=instrument,
        price_date=date(2026, 6, 5),
        close_price=Decimal("500.25"),
        currency="USD",
        source="yfinance",
    )
    duplicate_price = price_model(
        instrument=instrument,
        price_date=date(2026, 6, 5),
        close_price=Decimal("501.10"),
        currency="USD",
        source="yfinance",
    )

    db_session.add_all([first_price, duplicate_price])

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_same_instrument_and_date_can_have_different_sources(
    db_session: Session,
) -> None:
    price_model = require_price_model()
    instrument = create_instrument(db_session)
    yfinance_price = price_model(
        instrument=instrument,
        price_date=date(2026, 6, 5),
        close_price=Decimal("500.25"),
        currency="USD",
        source="yfinance",
    )
    manual_price = price_model(
        instrument=instrument,
        price_date=date(2026, 6, 5),
        close_price=Decimal("500.30"),
        currency="USD",
        source="manual",
    )

    db_session.add_all([yfinance_price, manual_price])
    db_session.commit()

    prices = list(db_session.scalars(select(price_model)))
    assert len(prices) == 2


def test_negative_close_price_fails(db_session: Session) -> None:
    price_model = require_price_model()
    instrument = create_instrument(db_session)
    price = price_model(
        instrument=instrument,
        price_date=date(2026, 6, 5),
        close_price=Decimal("-1.00"),
        currency="USD",
        source="yfinance",
    )

    db_session.add(price)

    with pytest.raises(IntegrityError):
        db_session.commit()
