from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.data.models import Holding, Instrument, Price, Profile
from app.domain.allocation import build_allocation_breakdowns
from app.domain.portfolio_math import build_portfolio_snapshot
from app.domain.simulation import apply_trades, diff_breakdowns
from app.schemas.simulation import TradeLeg


def profile() -> Profile:
    return Profile(
        user_id="user-123",
        display_name="Long-Term Investor",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="monthly",
    )


def instrument(
    instrument_id: int,
    symbol: str,
    currency: str | None = "USD",
    asset_class: str | None = "ETF",
    sector: str | None = "Broad Market",
    country: str | None = "United States",
    region: str | None = "North America",
) -> Instrument:
    return Instrument(
        id=instrument_id,
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange="NYSEARCA",
        currency=currency,
        asset_class=asset_class,
        sector=sector,
        country=country,
        region=region,
    )


def holding(
    holding_id: int,
    held_instrument: Instrument,
    quantity: str,
    average_cost: str = "100",
) -> Holding:
    return Holding(
        id=holding_id,
        user_id="user-123",
        instrument=held_instrument,
        instrument_id=held_instrument.id,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
    )


def price(held_instrument: Instrument, close_price: str) -> Price:
    return Price(
        instrument=held_instrument,
        instrument_id=held_instrument.id,
        price_date=date(2026, 6, 5),
        close_price=Decimal(close_price),
        currency=held_instrument.currency or "UNKNOWN",
        source="simulation",
    )


def no_instrument(symbol: str) -> Instrument | None:
    return None


def no_price(instrument_id: int) -> Price | None:
    return None


def breakdowns_for(
    holdings: list[Holding],
    latest_prices: dict[int, Price],
):
    snapshot = build_portfolio_snapshot(profile(), holdings, latest_prices)
    return build_allocation_breakdowns(snapshot)


def test_trade_leg_requires_exactly_one_instrument_identifier() -> None:
    with pytest.raises(ValidationError):
        TradeLeg(action="buy", quantity=Decimal("1"))

    with pytest.raises(ValidationError):
        TradeLeg(
            instrument_id=1,
            symbol="VOO",
            action="buy",
            quantity=Decimal("1"),
        )


def test_selling_part_of_position_reduces_value_and_shifts_percentages() -> None:
    voo = instrument(1, "VOO", sector="Broad Market")
    qqq = instrument(2, "QQQ", sector="Technology")
    holdings = [
        holding(1, voo, quantity="2"),
        holding(2, qqq, quantity="1"),
    ]
    latest_prices = {voo.id: price(voo, "500"), qqq.id: price(qqq, "500")}

    simulated_holdings, simulated_prices, warnings = apply_trades(
        holdings,
        latest_prices,
        [TradeLeg(instrument_id=voo.id, action="sell", quantity=Decimal("1"))],
        resolve_instrument=no_instrument,
        resolve_price=no_price,
    )

    breakdowns = breakdowns_for(simulated_holdings, simulated_prices)
    sector_percent = {row.label: row.percent for row in breakdowns.sector}

    assert warnings == []
    assert sum(row.percent for row in breakdowns.sector) == Decimal("100")
    assert sector_percent["Broad Market"] == Decimal("50.0")
    assert sector_percent["Technology"] == Decimal("50.0")


def test_selling_entire_position_removes_it_from_instrument_breakdown() -> None:
    voo = instrument(1, "VOO")
    qqq = instrument(2, "QQQ")
    holdings = [holding(1, voo, "2"), holding(2, qqq, "1")]
    latest_prices = {voo.id: price(voo, "500"), qqq.id: price(qqq, "500")}

    simulated_holdings, simulated_prices, warnings = apply_trades(
        holdings,
        latest_prices,
        [TradeLeg(instrument_id=voo.id, action="sell", quantity=Decimal("2"))],
        resolve_instrument=no_instrument,
        resolve_price=no_price,
    )

    breakdowns = breakdowns_for(simulated_holdings, simulated_prices)

    assert warnings == []
    assert [row.label for row in breakdowns.instrument] == ["QQQ"]


def test_over_selling_caps_at_held_quantity_and_warns() -> None:
    voo = instrument(1, "VOO")
    holdings = [holding(1, voo, "2")]
    latest_prices = {voo.id: price(voo, "500")}

    simulated_holdings, _simulated_prices, warnings = apply_trades(
        holdings,
        latest_prices,
        [TradeLeg(instrument_id=voo.id, action="sell", quantity=Decimal("5"))],
        resolve_instrument=no_instrument,
        resolve_price=no_price,
    )

    assert simulated_holdings == []
    assert warnings == ["Sell for VOO capped at held quantity 2."]


def test_buying_more_of_held_instrument_increases_allocation() -> None:
    voo = instrument(1, "VOO")
    qqq = instrument(2, "QQQ")
    holdings = [holding(1, voo, "1"), holding(2, qqq, "1")]
    latest_prices = {voo.id: price(voo, "500"), qqq.id: price(qqq, "500")}

    simulated_holdings, simulated_prices, warnings = apply_trades(
        holdings,
        latest_prices,
        [TradeLeg(instrument_id=voo.id, action="buy", quantity=Decimal("1"))],
        resolve_instrument=no_instrument,
        resolve_price=no_price,
    )

    breakdowns = breakdowns_for(simulated_holdings, simulated_prices)
    instrument_percent = {row.label: row.percent for row in breakdowns.instrument}

    assert warnings == []
    assert instrument_percent["VOO"] == Decimal("66.66666666666666666666666667")
    assert instrument_percent["QQQ"] == Decimal("33.33333333333333333333333333")


def test_buying_new_instrument_adds_metadata_breakdown_rows() -> None:
    voo = instrument(1, "VOO")
    vxus = instrument(
        3,
        "VXUS",
        asset_class="ETF",
        sector="International",
        country="Global",
        region="Global ex-US",
    )
    holdings = [holding(1, voo, "1")]
    latest_prices = {voo.id: price(voo, "500")}

    simulated_holdings, simulated_prices, warnings = apply_trades(
        holdings,
        latest_prices,
        [TradeLeg(symbol="vxus", action="buy", quantity=Decimal("2"))],
        resolve_instrument=lambda symbol: vxus if symbol == "VXUS" else None,
        resolve_price=lambda instrument_id: price(vxus, "100")
        if instrument_id == vxus.id
        else None,
    )

    breakdowns = breakdowns_for(simulated_holdings, simulated_prices)

    assert warnings == []
    assert [row.label for row in breakdowns.instrument] == ["VOO", "VXUS"]
    assert {row.label for row in breakdowns.sector} == {
        "Broad Market",
        "International",
    }
    assert {row.label for row in breakdowns.country} == {"United States", "Global"}
    assert {row.label for row in breakdowns.region} == {
        "North America",
        "Global ex-US",
    }


def test_buying_new_unpriced_instrument_warns_and_excludes_from_market_value() -> None:
    vxus = instrument(3, "VXUS")

    simulated_holdings, simulated_prices, warnings = apply_trades(
        [],
        {},
        [TradeLeg(symbol="vxus", action="buy", quantity=Decimal("2"))],
        resolve_instrument=lambda symbol: vxus if symbol == "VXUS" else None,
        resolve_price=no_price,
    )

    breakdowns = breakdowns_for(simulated_holdings, simulated_prices)

    assert simulated_prices == {}
    assert breakdowns.instrument == []
    assert breakdowns.unpriced_holding_count == 1
    assert warnings == ["No price available for VXUS; simulated holding is unpriced."]


def test_apply_trades_does_not_mutate_inputs() -> None:
    voo = instrument(1, "VOO")
    holdings = [holding(1, voo, "2")]
    latest_prices = {voo.id: price(voo, "500")}

    apply_trades(
        holdings,
        latest_prices,
        [TradeLeg(instrument_id=voo.id, action="sell", quantity=Decimal("1"))],
        resolve_instrument=no_instrument,
        resolve_price=no_price,
    )

    assert holdings[0].quantity == Decimal("2")
    assert latest_prices[voo.id].close_price == Decimal("500")


def test_diff_breakdowns_emits_before_only_and_after_only_zero_baselines() -> None:
    voo = instrument(1, "VOO", sector="Broad Market")
    qqq = instrument(2, "QQQ", sector="Technology")
    before = breakdowns_for([holding(1, voo, "1")], {voo.id: price(voo, "500")})
    after = breakdowns_for([holding(2, qqq, "1")], {qqq.id: price(qqq, "500")})

    delta = diff_breakdowns(before, after)
    sector_delta = {
        row.label: (row.percent_before, row.percent_after, row.percent_change)
        for row in delta
        if row.dimension == "sector"
    }

    assert sector_delta["Broad Market"] == (
        Decimal("100"),
        Decimal("0.00"),
        Decimal("-100.00"),
    )
    assert sector_delta["Technology"] == (
        Decimal("0.00"),
        Decimal("100"),
        Decimal("100.00"),
    )
