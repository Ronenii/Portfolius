from collections.abc import Callable
from decimal import Decimal

from app.schemas.portfolio import (
    AllocationRow,
    CompositionResponse,
    CompositionRow,
    PortfolioBreakdowns,
    PortfolioHoldingSnapshot,
    PortfolioSnapshot,
)

UNCLASSIFIED = "Unclassified"
COMPOSITION_DIMENSIONS = (
    "instrument",
    "asset_class",
    "sector",
    "country",
    "region",
    "currency",
)

LabelFor = Callable[[PortfolioHoldingSnapshot], str]

DIMENSION_LABELS: dict[str, LabelFor] = {
    "instrument": lambda holding: holding.instrument.symbol,
    "asset_class": lambda holding: classified(holding.instrument.asset_class),
    "sector": lambda holding: classified(holding.instrument.sector),
    "country": lambda holding: classified(holding.instrument.country),
    "region": lambda holding: classified(holding.instrument.region),
    "currency": lambda holding: holding_currency(holding),
}


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


def build_composition(
    snapshot: PortfolioSnapshot,
    dimension: str,
    key: str,
    *,
    currency: str | None = None,
) -> CompositionResponse:
    if dimension not in DIMENSION_LABELS:
        raise ValueError(f"Unknown composition dimension: {dimension}")

    priced_holdings = [
        holding for holding in snapshot.holdings if holding.market_value is not None
    ]
    unpriced_holding_count = len(snapshot.holdings) - len(priced_holdings)
    label_for = DIMENSION_LABELS[dimension]
    matching_holdings = [
        holding for holding in priced_holdings if label_for(holding) == key
    ]

    selected_currency = resolve_composition_currency(
        matching_holdings,
        dimension,
        key,
        currency,
    )
    if selected_currency:
        matching_holdings = [
            holding
            for holding in matching_holdings
            if holding_currency(holding) == selected_currency
        ]

    currency_total = portfolio_total_for_currency(snapshot, selected_currency)
    grouped: dict[int, tuple[PortfolioHoldingSnapshot, Decimal, Decimal]] = {}
    for holding in matching_holdings:
        if holding.market_value is None:
            continue
        instrument_id = holding.instrument.id
        representative, market_value, unit_quantity = grouped.get(
            instrument_id,
            (holding, Decimal("0"), Decimal("0")),
        )
        grouped[instrument_id] = (
            representative,
            market_value + holding.market_value,
            unit_quantity + holding.quantity,
        )

    slice_total = sum(
        (market_value for _, market_value, _ in grouped.values()),
        Decimal("0"),
    )
    children = [
        CompositionRow(
            instrument_id=representative.instrument.id,
            symbol=representative.instrument.symbol,
            name=representative.instrument.name or representative.instrument.symbol,
            currency=holding_currency(representative),
            market_value=market_value,
            unit_quantity=unit_quantity,
            percent_of_parent=percent_of(market_value, slice_total),
            percent_of_portfolio=percent_of(market_value, currency_total),
        )
        for representative, market_value, unit_quantity in grouped.values()
    ]
    children = sorted(children, key=lambda row: (-row.market_value, row.symbol))

    return CompositionResponse(
        dimension=dimension,
        key=key,
        currency=selected_currency,
        market_value=slice_total,
        percent_of_portfolio=percent_of(slice_total, currency_total),
        children=children,
        unpriced_holding_count=unpriced_holding_count,
    )


def build_dimension_rows(
    dimension: str,
    holdings: list[PortfolioHoldingSnapshot],
    label_for: Callable[[PortfolioHoldingSnapshot], str],
) -> list[AllocationRow]:
    grouped: dict[tuple[str, str], tuple[Decimal, set[int], Decimal]] = {}
    currency_totals: dict[str, Decimal] = {}

    for holding in holdings:
        if holding.market_value is None:
            continue
        currency = holding_currency(holding)
        label = label_for(holding)
        market_value, instrument_ids, unit_quantity = grouped.get(
            (currency, label),
            (Decimal("0"), set(), Decimal("0")),
        )
        instrument_ids.add(holding.instrument.id)
        grouped[(currency, label)] = (
            market_value + holding.market_value,
            instrument_ids,
            unit_quantity + holding.quantity,
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
            position_count=len(instrument_ids),
            unit_quantity=unit_quantity if dimension == "instrument" else None,
        )
        for (currency, label), (
            market_value,
            instrument_ids,
            unit_quantity,
        ) in grouped.items()
    ]
    return sorted(rows, key=lambda row: (-row.market_value, row.label))


def build_currency_rows(
    holdings: list[PortfolioHoldingSnapshot],
) -> list[AllocationRow]:
    grouped: dict[str, tuple[Decimal, set[int]]] = {}
    for holding in holdings:
        if holding.market_value is None:
            continue
        currency = holding_currency(holding)
        market_value, instrument_ids = grouped.get(currency, (Decimal("0"), set()))
        instrument_ids.add(holding.instrument.id)
        grouped[currency] = (market_value + holding.market_value, instrument_ids)

    rows = [
        AllocationRow(
            dimension="currency",
            label=currency,
            currency=currency,
            market_value=market_value,
            percent=Decimal("100"),
            position_count=len(instrument_ids),
        )
        for currency, (market_value, instrument_ids) in grouped.items()
    ]
    return sorted(rows, key=lambda row: (-row.market_value, row.label))


def resolve_composition_currency(
    matching_holdings: list[PortfolioHoldingSnapshot],
    dimension: str,
    key: str,
    currency: str | None,
) -> str:
    if currency is not None:
        return currency
    if dimension == "currency":
        return key
    if not matching_holdings:
        return ""
    return holding_currency(matching_holdings[0])


def portfolio_total_for_currency(
    snapshot: PortfolioSnapshot,
    currency: str,
) -> Decimal:
    if not currency:
        return Decimal("0")
    currency_total = snapshot.currency_totals.get(currency)
    if currency_total is None:
        return Decimal("0")
    return currency_total.market_value


def classified(value: str | None) -> str:
    return value or UNCLASSIFIED


def holding_currency(holding: PortfolioHoldingSnapshot) -> str:
    return holding.instrument.currency or "UNKNOWN"


def percent_of(value: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0")
    return (value / total) * Decimal("100")
