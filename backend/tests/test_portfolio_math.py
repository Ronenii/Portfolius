from datetime import date
from decimal import Decimal

from app.data.models import Holding, Instrument, Price, Profile
from app.domain.portfolio_math import build_portfolio_snapshot


def profile(base_currency: str = "USD") -> Profile:
    return Profile(
        user_id="user-123",
        display_name="Long-Term Investor",
        base_currency=base_currency,
        time_horizon="10+ years",
        investment_frequency="Monthly",
    )


def instrument(
    symbol: str,
    currency: str | None = "USD",
    exchange: str = "NYSEARCA",
) -> Instrument:
    return Instrument(
        id=len(symbol),
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange=exchange,
        currency=currency,
        asset_class="ETF",
        sector="Broad Market",
        country="United States",
        region="North America",
    )


def holding(
    holding_id: int,
    held_instrument: Instrument,
    quantity: str,
    average_cost: str,
) -> Holding:
    return Holding(
        id=holding_id,
        user_id="user-123",
        instrument=held_instrument,
        instrument_id=held_instrument.id,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
    )


def price(
    held_instrument: Instrument,
    close_price: str,
    price_date: date = date(2026, 6, 5),
) -> Price:
    return Price(
        instrument=held_instrument,
        instrument_id=held_instrument.id,
        price_date=price_date,
        close_price=Decimal(close_price),
        currency=held_instrument.currency or "UNKNOWN",
        source="fake",
    )


def test_priced_holding_returns_value_cost_and_gain_math() -> None:
    voo = instrument("VOO")
    saved_holding = holding(1, voo, quantity="2.5", average_cost="400")

    snapshot = build_portfolio_snapshot(
        profile(),
        [saved_holding],
        {voo.id: price(voo, "500")},
    )

    holding_snapshot = snapshot.holdings[0]
    assert holding_snapshot.cost_basis == Decimal("1000.0")
    assert holding_snapshot.market_value == Decimal("1250.0")
    assert holding_snapshot.unrealized_gain == Decimal("250.0")
    assert holding_snapshot.unrealized_gain_percent == Decimal("25.00")
    assert holding_snapshot.price_status == "priced"
    assert snapshot.summary.total_market_value == Decimal("1250.0")
    assert snapshot.summary.total_cost_basis == Decimal("1000.0")
    assert snapshot.summary.total_unrealized_gain == Decimal("250.0")
    assert snapshot.summary.priced_holdings == 1
    assert snapshot.summary.missing_price_holdings == 0


def test_missing_price_is_excluded_from_priced_totals() -> None:
    voo = instrument("VOO")
    saved_holding = holding(1, voo, quantity="2", average_cost="400")

    snapshot = build_portfolio_snapshot(profile(), [saved_holding], {})

    holding_snapshot = snapshot.holdings[0]
    assert holding_snapshot.cost_basis == Decimal("800")
    assert holding_snapshot.market_value is None
    assert holding_snapshot.unrealized_gain is None
    assert holding_snapshot.unrealized_gain_percent is None
    assert holding_snapshot.price_status == "missing_price"
    assert snapshot.summary.total_market_value == Decimal("0")
    assert snapshot.summary.total_cost_basis == Decimal("0")
    assert snapshot.summary.priced_holdings == 0
    assert snapshot.summary.missing_price_holdings == 1


def test_non_finite_price_is_treated_as_missing() -> None:
    voo = instrument("VOO")
    saved_holding = holding(1, voo, quantity="2", average_cost="400")

    snapshot = build_portfolio_snapshot(
        profile(),
        [saved_holding],
        {voo.id: price(voo, "NaN")},
    )

    holding_snapshot = snapshot.holdings[0]
    assert holding_snapshot.market_value is None
    assert holding_snapshot.unrealized_gain is None
    assert holding_snapshot.price_status == "missing_price"
    assert snapshot.summary.total_market_value == Decimal("0")
    assert snapshot.summary.priced_holdings == 0
    assert snapshot.summary.missing_price_holdings == 1


def test_base_currency_totals_exclude_other_currencies() -> None:
    voo = instrument("VOO", currency="USD")
    eur = instrument("EUNA", currency="EUR", exchange="XETRA")
    holdings = [
        holding(1, voo, quantity="2", average_cost="400"),
        holding(2, eur, quantity="3", average_cost="50"),
    ]

    snapshot = build_portfolio_snapshot(
        profile(base_currency="USD"),
        holdings,
        {
            voo.id: price(voo, "500"),
            eur.id: price(eur, "60"),
        },
    )

    assert snapshot.summary.total_market_value == Decimal("1000")
    assert snapshot.summary.total_cost_basis == Decimal("800")
    assert snapshot.summary.total_unrealized_gain == Decimal("200")


def test_currency_totals_group_priced_holdings_by_currency() -> None:
    voo = instrument("VOO", currency="USD")
    eur = instrument("EUNA", currency="EUR", exchange="XETRA")

    snapshot = build_portfolio_snapshot(
        profile(base_currency="USD"),
        [
            holding(1, voo, quantity="2", average_cost="400"),
            holding(2, eur, quantity="3", average_cost="50"),
        ],
        {
            voo.id: price(voo, "500"),
            eur.id: price(eur, "60"),
        },
    )

    assert snapshot.currency_totals["USD"].market_value == Decimal("1000")
    assert snapshot.currency_totals["USD"].cost_basis == Decimal("800")
    assert snapshot.currency_totals["EUR"].market_value == Decimal("180")
    assert snapshot.currency_totals["EUR"].cost_basis == Decimal("150")


def test_zero_cost_basis_does_not_calculate_gain_percent() -> None:
    voo = instrument("VOO")

    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, voo, quantity="2", average_cost="0")],
        {voo.id: price(voo, "500")},
    )

    holding_snapshot = snapshot.holdings[0]
    assert holding_snapshot.cost_basis == Decimal("0")
    assert holding_snapshot.market_value == Decimal("1000")
    assert holding_snapshot.unrealized_gain == Decimal("1000")
    assert holding_snapshot.unrealized_gain_percent is None


def test_portfolio_snapshot_serializes_decimals_as_strings() -> None:
    voo = instrument("VOO")

    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, voo, quantity="2", average_cost="400")],
        {voo.id: price(voo, "500")},
    )

    payload = snapshot.model_dump(mode="json")

    assert payload["summary"]["total_market_value"] == "1000"
    assert payload["holdings"][0]["cost_basis"] == "800"
    assert payload["holdings"][0]["market_value"] == "1000"
    assert payload["currency_totals"]["USD"]["market_value"] == "1000"
