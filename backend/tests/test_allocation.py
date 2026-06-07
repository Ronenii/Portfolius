from datetime import date
from decimal import Decimal

from app.data.models import Holding, Instrument, Price, Profile
from app.domain.allocation import build_allocation_breakdowns
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


def test_instrument_breakdown_creates_one_row_per_symbol() -> None:
    voo = instrument(1, "VOO")
    vti = instrument(2, "VTI")
    snapshot = snapshot_for(
        [
            holding(1, voo, quantity="2"),
            holding(2, vti, quantity="1"),
        ],
        {
            voo.id: price(voo, "500"),
            vti.id: price(vti, "400"),
        },
    )

    breakdowns = build_allocation_breakdowns(snapshot)

    assert [row.label for row in breakdowns.instrument] == ["VOO", "VTI"]
    assert breakdowns.instrument[0].market_value == Decimal("1000")
    assert breakdowns.instrument[0].percent == Decimal("71.42857142857142857142857143")
    assert breakdowns.instrument[1].market_value == Decimal("400")


def test_sector_breakdown_groups_multiple_holdings_with_same_sector() -> None:
    voo = instrument(1, "VOO", sector="Broad Market")
    vti = instrument(2, "VTI", sector="Broad Market")
    snapshot = snapshot_for(
        [
            holding(1, voo, quantity="2"),
            holding(2, vti, quantity="1"),
        ],
        {
            voo.id: price(voo, "500"),
            vti.id: price(vti, "400"),
        },
    )

    breakdowns = build_allocation_breakdowns(snapshot)

    assert len(breakdowns.sector) == 1
    assert breakdowns.sector[0].label == "Broad Market"
    assert breakdowns.sector[0].market_value == Decimal("1400")
    assert breakdowns.sector[0].percent == Decimal("100")
    assert breakdowns.sector[0].holding_count == 2


def test_missing_metadata_appears_as_unclassified() -> None:
    unknown = instrument(
        1,
        "MYST",
        asset_class=None,
        sector=None,
        country=None,
        region=None,
    )
    snapshot = snapshot_for(
        [holding(1, unknown)],
        {unknown.id: price(unknown, "250")},
    )

    breakdowns = build_allocation_breakdowns(snapshot)

    assert breakdowns.asset_class[0].label == "Unclassified"
    assert breakdowns.sector[0].label == "Unclassified"
    assert breakdowns.country[0].label == "Unclassified"
    assert breakdowns.region[0].label == "Unclassified"


def test_percentages_sum_to_100_for_priced_holdings_in_same_currency() -> None:
    voo = instrument(1, "VOO", sector="Broad Market")
    qqq = instrument(2, "QQQ", sector="Technology")
    snapshot = snapshot_for(
        [
            holding(1, voo),
            holding(2, qqq),
        ],
        {
            voo.id: price(voo, "500"),
            qqq.id: price(qqq, "500"),
        },
    )

    breakdowns = build_allocation_breakdowns(snapshot)

    assert sum(row.percent for row in breakdowns.sector) == Decimal("100")


def test_currency_breakdown_creates_one_row_per_priced_currency() -> None:
    usd = instrument(1, "VOO", currency="USD")
    eur = instrument(2, "EUNA", currency="EUR")
    snapshot = snapshot_for(
        [
            holding(1, usd, quantity="2"),
            holding(2, eur, quantity="3"),
        ],
        {
            usd.id: price(usd, "500"),
            eur.id: price(eur, "60"),
        },
    )

    breakdowns = build_allocation_breakdowns(snapshot)

    currency_rows = [
        (row.label, row.market_value, row.percent) for row in breakdowns.currency
    ]
    assert currency_rows == [
        ("USD", Decimal("1000"), Decimal("100")),
        ("EUR", Decimal("180"), Decimal("100")),
    ]


def test_unpriced_holdings_are_counted_but_excluded_from_rows() -> None:
    voo = instrument(1, "VOO")
    missing = instrument(2, "VXUS")
    snapshot = snapshot_for(
        [
            holding(1, voo),
            holding(2, missing),
        ],
        {
            voo.id: price(voo, "500"),
        },
    )

    breakdowns = build_allocation_breakdowns(snapshot)

    assert breakdowns.unpriced_holding_count == 1
    assert [row.label for row in breakdowns.instrument] == ["VOO"]
