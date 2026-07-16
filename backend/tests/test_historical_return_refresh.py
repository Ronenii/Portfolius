from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.data.models import Instrument
from app.domain.historical_return_refresh import (
    refresh_historical_returns_for_all_instruments,
)


class ScriptedHistoricalReturnClient:
    def __init__(
        self,
        returns: dict[str, Decimal | None],
        failing_symbols: set[str] | None = None,
    ) -> None:
        self.returns = returns
        self.failing_symbols = failing_symbols or set()
        self.requests: list[tuple[str, str, str | None]] = []

    def get_historical_annualized_return(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> Decimal | None:
        self.requests.append((symbol, exchange, currency_hint))
        if symbol in self.failing_symbols:
            raise RuntimeError("provider down")
        return self.returns.get(symbol)


def instrument(symbol: str, currency: str | None = "USD") -> Instrument:
    return Instrument(
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange="NYSEARCA",
        currency=currency,
        asset_class="ETF",
    )


def test_refresh_stores_computed_return_and_stamps_updated_at(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    db_session.add(voo)
    db_session.commit()
    client = ScriptedHistoricalReturnClient({"VOO": Decimal("14.89")})
    # SQLite (used by the db_session fixture) round-trips DateTime(timezone=True)
    # columns as naive datetimes, so compare against a naive "before" marker.
    before = datetime.now(UTC).replace(tzinfo=None)

    result = refresh_historical_returns_for_all_instruments(db_session, client)

    db_session.refresh(voo)
    assert result.requested == 1
    assert result.updated == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert voo.historical_annual_return == Decimal("14.89")
    assert voo.historical_return_updated_at is not None
    assert voo.historical_return_updated_at >= before
    assert client.requests == [("VOO", "NYSEARCA", "USD")]


def test_refresh_skips_instruments_the_client_returns_none_for(
    db_session: Session,
) -> None:
    btc = instrument("BTC-USD", currency=None)
    db_session.add(btc)
    db_session.commit()
    client = ScriptedHistoricalReturnClient({"BTC-USD": None})

    result = refresh_historical_returns_for_all_instruments(db_session, client)

    db_session.refresh(btc)
    assert result.requested == 1
    assert result.updated == 0
    assert result.skipped == 1
    assert result.failed == 0
    assert btc.historical_annual_return is None
    assert btc.historical_return_updated_at is None


def test_refresh_counts_failures_without_stopping_the_batch(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    bnd = instrument("BND")
    db_session.add_all([voo, bnd])
    db_session.commit()
    client = ScriptedHistoricalReturnClient(
        {"BND": Decimal("3.50")},
        failing_symbols={"VOO"},
    )

    result = refresh_historical_returns_for_all_instruments(db_session, client)

    db_session.refresh(voo)
    db_session.refresh(bnd)
    assert result.requested == 2
    assert result.updated == 1
    assert result.skipped == 0
    assert result.failed == 1
    assert voo.historical_annual_return is None
    assert bnd.historical_annual_return == Decimal("3.50")
