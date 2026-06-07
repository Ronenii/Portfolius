from collections.abc import Callable
from decimal import Decimal

from app.schemas.portfolio import (
    AllocationRow,
    PortfolioBreakdowns,
    PortfolioHoldingSnapshot,
    PortfolioSnapshot,
)

UNCLASSIFIED = "Unclassified"


def build_allocation_breakdowns(snapshot: PortfolioSnapshot) -> PortfolioBreakdowns:
    priced_holdings = [
        holding for holding in snapshot.holdings if holding.market_value is not None
    ]
    unpriced_holding_count = len(snapshot.holdings) - len(priced_holdings)

    return PortfolioBreakdowns(
        instrument=build_dimension_rows(
            "instrument",
            priced_holdings,
            lambda holding: holding.instrument.symbol,
        ),
        asset_class=build_dimension_rows(
            "asset_class",
            priced_holdings,
            lambda holding: classified(holding.instrument.asset_class),
        ),
        sector=build_dimension_rows(
            "sector",
            priced_holdings,
            lambda holding: classified(holding.instrument.sector),
        ),
        country=build_dimension_rows(
            "country",
            priced_holdings,
            lambda holding: classified(holding.instrument.country),
        ),
        region=build_dimension_rows(
            "region",
            priced_holdings,
            lambda holding: classified(holding.instrument.region),
        ),
        currency=build_currency_rows(priced_holdings),
        unpriced_holding_count=unpriced_holding_count,
    )


def build_dimension_rows(
    dimension: str,
    holdings: list[PortfolioHoldingSnapshot],
    label_for: Callable[[PortfolioHoldingSnapshot], str],
) -> list[AllocationRow]:
    grouped: dict[tuple[str, str], tuple[Decimal, int]] = {}
    currency_totals: dict[str, Decimal] = {}

    for holding in holdings:
        if holding.market_value is None:
            continue
        currency = holding_currency(holding)
        label = label_for(holding)
        market_value, holding_count = grouped.get((currency, label), (Decimal("0"), 0))
        grouped[(currency, label)] = (
            market_value + holding.market_value,
            holding_count + 1,
        )
        currency_totals[currency] = currency_totals.get(currency, Decimal("0")) + (
            holding.market_value
        )

    rows = [
        AllocationRow(
            dimension=dimension,
            label=label,
            currency=currency,
            market_value=market_value,
            percent=percent_of(market_value, currency_totals[currency]),
            holding_count=holding_count,
        )
        for (currency, label), (market_value, holding_count) in grouped.items()
    ]
    return sorted(rows, key=lambda row: (-row.market_value, row.label))


def build_currency_rows(
    holdings: list[PortfolioHoldingSnapshot],
) -> list[AllocationRow]:
    grouped: dict[str, tuple[Decimal, int]] = {}
    for holding in holdings:
        if holding.market_value is None:
            continue
        currency = holding_currency(holding)
        market_value, holding_count = grouped.get(currency, (Decimal("0"), 0))
        grouped[currency] = (market_value + holding.market_value, holding_count + 1)

    rows = [
        AllocationRow(
            dimension="currency",
            label=currency,
            currency=currency,
            market_value=market_value,
            percent=Decimal("100"),
            holding_count=holding_count,
        )
        for currency, (market_value, holding_count) in grouped.items()
    ]
    return sorted(rows, key=lambda row: (-row.market_value, row.label))


def classified(value: str | None) -> str:
    return value or UNCLASSIFIED


def holding_currency(holding: PortfolioHoldingSnapshot) -> str:
    return holding.instrument.currency or "UNKNOWN"


def percent_of(value: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0")
    return (value / total) * Decimal("100")
