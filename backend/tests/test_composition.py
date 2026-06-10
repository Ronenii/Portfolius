from copy import deepcopy
from datetime import date
from decimal import Decimal

from app.data.models import Holding, Instrument, Price, Profile
from app.domain.allocation import build_composition
from app.domain.portfolio_math import build_portfolio_snapshot


def profile() -> Profile:
    return Profile(
        user_id="user-123",
        display_name="Long-Term Investor",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="Monthly",
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
    quantity: str = "1",
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
        source="fake",
    )


def snapshot_for(
    holdings: list[Holding],
    latest_prices: dict[int, Price],
):
    return build_portfolio_snapshot(profile(), holdings, latest_prices)


def test_asset_class_composition_returns_child_instruments_with_percentages() -> None:
    voo = instrument(1, "VOO", asset_class="ETF")
    vxus = instrument(2, "VXUS", asset_class="ETF")
    aapl = instrument(3, "AAPL", asset_class="Stock", sector="Technology")
    snapshot = snapshot_for(
        [
            holding(1, voo, quantity="3"),
            holding(2, vxus, quantity="2"),
            holding(3, aapl, quantity="1"),
        ],
        {
            voo.id: price(voo, "100"),
            vxus.id: price(vxus, "100"),
            aapl.id: price(aapl, "500"),
        },
    )

    composition = build_composition(snapshot, "asset_class", "ETF")

    assert composition.dimension == "asset_class"
    assert composition.key == "ETF"
    assert composition.currency == "USD"
    assert composition.market_value == Decimal("500")
    assert composition.percent_of_portfolio == Decimal("50.0")
    assert composition.unpriced_holding_count == 0
    assert [(row.symbol, row.market_value) for row in composition.children] == [
        ("VOO", Decimal("300")),
        ("VXUS", Decimal("200")),
    ]
    assert [row.percent_of_parent for row in composition.children] == [
        Decimal("60.0"),
        Decimal("40.0"),
    ]
    assert [row.percent_of_portfolio for row in composition.children] == [
        Decimal("30.0"),
        Decimal("20.0"),
    ]


def test_composition_collapses_multiple_lots_for_the_same_instrument() -> None:
    voo = instrument(1, "VOO", asset_class="ETF")
    snapshot = snapshot_for(
        [
            holding(1, voo, quantity="1"),
            holding(2, voo, quantity="2"),
        ],
        {voo.id: price(voo, "100")},
    )

    composition = build_composition(snapshot, "asset_class", "ETF")

    assert len(composition.children) == 1
    assert composition.children[0].symbol == "VOO"
    assert composition.children[0].holding_count == 2
    assert composition.children[0].market_value == Decimal("300")
    assert composition.children[0].percent_of_parent == Decimal("100")


def test_unclassified_composition_uses_the_same_label_as_breakdowns() -> None:
    mystery = instrument(1, "MYST", sector=None, region=None)
    known = instrument(2, "VOO", sector="Broad Market", region="North America")
    snapshot = snapshot_for(
        [holding(1, mystery), holding(2, known)],
        {
            mystery.id: price(mystery, "250"),
            known.id: price(known, "750"),
        },
    )

    composition = build_composition(snapshot, "sector", "Unclassified")

    assert [row.symbol for row in composition.children] == ["MYST"]
    assert composition.market_value == Decimal("250")
    assert composition.percent_of_portfolio == Decimal("25.00")


def test_unknown_key_returns_empty_zeroed_composition() -> None:
    voo = instrument(1, "VOO", asset_class="ETF")
    snapshot = snapshot_for([holding(1, voo)], {voo.id: price(voo, "500")})

    composition = build_composition(snapshot, "asset_class", "Bond")

    assert composition.currency == ""
    assert composition.market_value == Decimal("0")
    assert composition.percent_of_portfolio == Decimal("0")
    assert composition.children == []


def test_instrument_dimension_returns_the_selected_instrument_at_100_percent() -> None:
    voo = instrument(1, "VOO")
    qqq = instrument(2, "QQQ")
    snapshot = snapshot_for(
        [holding(1, voo, quantity="4"), holding(2, qqq, quantity="1")],
        {
            voo.id: price(voo, "100"),
            qqq.id: price(qqq, "600"),
        },
    )

    composition = build_composition(snapshot, "instrument", "VOO")

    assert composition.market_value == Decimal("400")
    assert composition.percent_of_portfolio == Decimal("40.0")
    assert len(composition.children) == 1
    assert composition.children[0].symbol == "VOO"
    assert composition.children[0].percent_of_parent == Decimal("100")
    assert composition.children[0].percent_of_portfolio == Decimal("40.0")


def test_unpriced_holdings_are_excluded_from_children_and_counted() -> None:
    priced = instrument(1, "VOO", asset_class="ETF")
    missing = instrument(2, "VXUS", asset_class="ETF")
    snapshot = snapshot_for(
        [holding(1, priced), holding(2, missing)],
        {priced.id: price(priced, "500")},
    )

    composition = build_composition(snapshot, "asset_class", "ETF")

    assert [row.symbol for row in composition.children] == ["VOO"]
    assert composition.unpriced_holding_count == 1


def test_multicurrency_slice_can_be_scoped_to_the_requested_currency() -> None:
    usd_etf = instrument(1, "VOO", currency="USD", asset_class="ETF")
    eur_etf = instrument(2, "EUNA", currency="EUR", asset_class="ETF")
    usd_stock = instrument(3, "AAPL", currency="USD", asset_class="Stock")
    snapshot = snapshot_for(
        [
            holding(1, usd_etf, quantity="5"),
            holding(2, eur_etf, quantity="3"),
            holding(3, usd_stock, quantity="1"),
        ],
        {
            usd_etf.id: price(usd_etf, "100"),
            eur_etf.id: price(eur_etf, "60"),
            usd_stock.id: price(usd_stock, "500"),
        },
    )

    composition = build_composition(snapshot, "asset_class", "ETF", currency="EUR")

    assert composition.currency == "EUR"
    assert composition.market_value == Decimal("180")
    assert composition.percent_of_portfolio == Decimal("100")
    assert [row.symbol for row in composition.children] == ["EUNA"]
    assert composition.children[0].percent_of_parent == Decimal("100")


def test_composition_does_not_mutate_the_snapshot() -> None:
    voo = instrument(1, "VOO", asset_class="ETF")
    snapshot = snapshot_for([holding(1, voo)], {voo.id: price(voo, "500")})
    before = deepcopy(snapshot)

    build_composition(snapshot, "asset_class", "ETF")

    assert snapshot == before
