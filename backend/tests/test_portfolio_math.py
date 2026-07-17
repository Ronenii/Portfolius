from datetime import date
from decimal import Decimal

from app.data.models import Holding, Instrument, Price, Profile
from app.domain.portfolio_math import (
    ASSET_CLASS_DEFAULT_RETURN,
    EQUITY_LIKE_RETURN,
    build_portfolio_snapshot,
    compute_weighted_average_return,
)


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
    asset_class: str | None = "ETF",
    historical_annual_return: Decimal | None = None,
) -> Instrument:
    return Instrument(
        id=len(symbol),
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange=exchange,
        currency=currency,
        asset_class=asset_class,
        sector="Broad Market",
        country="United States",
        region="North America",
        historical_annual_return=historical_annual_return,
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


def test_summary_reports_latest_valid_price_date() -> None:
    voo = instrument("VOO")
    vxus = instrument("VXUS")
    agg = instrument("AGGZZ")
    holdings = [
        holding(1, voo, quantity="2", average_cost="400"),
        holding(2, vxus, quantity="3", average_cost="50"),
        holding(3, agg, quantity="1", average_cost="300"),
    ]

    snapshot = build_portfolio_snapshot(
        profile(),
        holdings,
        {
            voo.id: price(voo, "500", price_date=date(2026, 6, 5)),
            vxus.id: price(vxus, "60", price_date=date(2026, 6, 7)),
            agg.id: price(agg, "NaN", price_date=date(2026, 6, 8)),
        },
    )

    assert snapshot.summary.latest_price_date == date(2026, 6, 7)


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


def test_weighted_average_uses_stored_historical_return_over_bucket() -> None:
    voo = instrument(
        "VOO", asset_class="ETF", historical_annual_return=Decimal("11.50")
    )
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, voo, quantity="10", average_cost="80")],
        {voo.id: price(voo, "100")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == Decimal("11.50")


def test_weighted_average_falls_back_to_asset_class_bucket() -> None:
    btc = instrument("BTCUSD", asset_class="CRYPTO")
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, btc, quantity="1", average_cost="20000")],
        {btc.id: price(btc, "25000")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == ASSET_CLASS_DEFAULT_RETURN["CRYPTO"]


def test_weighted_average_bucket_matching_is_case_and_whitespace_insensitive() -> None:
    gold = instrument("GLD", asset_class="  commodity ")
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, gold, quantity="10", average_cost="150")],
        {gold.id: price(gold, "180")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == ASSET_CLASS_DEFAULT_RETURN["COMMODITY"]


def test_weighted_average_defaults_unrecognized_asset_class_to_equity_like() -> None:
    mystery = instrument("XYZ", asset_class="SOMETHING_ELSE")
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, mystery, quantity="5", average_cost="40")],
        {mystery.id: price(mystery, "50")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == EQUITY_LIKE_RETURN


def test_weighted_average_combines_multiple_holdings_by_market_value() -> None:
    voo = instrument(
        "VOO", asset_class="ETF", historical_annual_return=Decimal("10.00")
    )
    btc = instrument("BTCUSD", asset_class="CRYPTO")
    snapshot = build_portfolio_snapshot(
        profile(),
        [
            holding(1, voo, quantity="10", average_cost="80"),
            holding(2, btc, quantity="0.5", average_cost="1500"),
        ],
        {voo.id: price(voo, "100"), btc.id: price(btc, "2000")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == Decimal("11.00")


def test_weighted_average_excludes_unpriced_and_non_base_currency_holdings() -> None:
    voo = instrument(
        "VOO", asset_class="ETF", historical_annual_return=Decimal("9.00")
    )
    unpriced = instrument("ZZZZ", asset_class="ETF")
    foreign = instrument("EFAEU", currency="EUR", asset_class="ETF")
    snapshot = build_portfolio_snapshot(
        profile(base_currency="USD"),
        [
            holding(1, voo, quantity="10", average_cost="80"),
            holding(2, unpriced, quantity="5", average_cost="50"),
            holding(3, foreign, quantity="4", average_cost="60"),
        ],
        {voo.id: price(voo, "100"), foreign.id: price(foreign, "70")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == Decimal("9.00")


def test_weighted_average_returns_none_when_no_holdings_qualify() -> None:
    unpriced = instrument("ZZZ", asset_class="ETF")
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, unpriced, quantity="5", average_cost="50")],
        {},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result is None


def test_weighted_average_returns_none_for_empty_portfolio() -> None:
    result = compute_weighted_average_return([], "USD")

    assert result is None
