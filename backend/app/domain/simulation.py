from collections.abc import Callable
from datetime import date
from decimal import Decimal

from app.data.models import Holding, Instrument, Price
from app.schemas.portfolio import AllocationRow, PortfolioBreakdowns
from app.schemas.simulation import AllocationDelta, TradeLeg

DIMENSION_ORDER = [
    "instrument",
    "asset_class",
    "sector",
    "country",
    "region",
    "currency",
]
SIMULATION_PRICE_DATE = date(1970, 1, 1)

ResolveInstrument = Callable[[str], Instrument | None]
ResolvePrice = Callable[[int], Price | None]


def apply_trades(
    holdings: list[Holding],
    latest_prices: dict[int, Price],
    legs: list[TradeLeg],
    *,
    resolve_instrument: ResolveInstrument,
    resolve_price: ResolvePrice,
) -> tuple[list[Holding], dict[int, Price], list[str]]:
    simulated_holdings = [copy_holding(holding) for holding in holdings]
    simulated_prices = dict(latest_prices)
    warnings: list[str] = []

    for leg in legs:
        if leg.action == "buy":
            apply_buy(
                simulated_holdings,
                simulated_prices,
                leg,
                warnings,
                resolve_instrument=resolve_instrument,
                resolve_price=resolve_price,
            )
        else:
            apply_sell(simulated_holdings, leg, warnings)

    return simulated_holdings, simulated_prices, warnings


def apply_buy(
    holdings: list[Holding],
    latest_prices: dict[int, Price],
    leg: TradeLeg,
    warnings: list[str],
    *,
    resolve_instrument: ResolveInstrument,
    resolve_price: ResolvePrice,
) -> None:
    target_holding = find_holding(holdings, leg)
    target_instrument = target_holding.instrument if target_holding else None

    if target_instrument is None:
        if leg.instrument_id is not None:
            warnings.append(f"Instrument {leg.instrument_id} is not held; buy skipped.")
            return
        if leg.symbol is None:
            return
        target_instrument = resolve_instrument(leg.symbol)
        if target_instrument is None:
            warnings.append(
                f"Instrument {leg.symbol} could not be resolved; buy skipped."
            )
            return

    close_price = leg.price
    if close_price is None:
        existing_price = latest_prices.get(target_instrument.id)
        if existing_price is None:
            existing_price = resolve_price(target_instrument.id)
        close_price = existing_price.close_price if existing_price else None

    if close_price is not None:
        latest_prices[target_instrument.id] = simulation_price(
            target_instrument,
            close_price,
        )
    else:
        warnings.append(
            f"No price available for {target_instrument.symbol}; "
            "simulated holding is unpriced."
        )

    if target_holding is None:
        holdings.append(
            Holding(
                id=synthetic_holding_id(holdings),
                user_id="simulation",
                instrument=target_instrument,
                instrument_id=target_instrument.id,
                quantity=leg.quantity,
                average_cost=close_price or Decimal("0"),
            )
        )
    else:
        target_holding.quantity += leg.quantity


def apply_sell(
    holdings: list[Holding],
    leg: TradeLeg,
    warnings: list[str],
) -> None:
    target_holding = find_holding(holdings, leg)
    if target_holding is None:
        label = leg.symbol or f"instrument {leg.instrument_id}"
        warnings.append(f"Sell for {label} skipped; no held position.")
        return

    sell_quantity = min(leg.quantity, target_holding.quantity)
    if leg.quantity > target_holding.quantity:
        warnings.append(
            f"Sell for {target_holding.instrument.symbol} capped at held quantity "
            f"{target_holding.quantity}."
        )

    target_holding.quantity -= sell_quantity
    if target_holding.quantity == 0:
        holdings.remove(target_holding)


def diff_breakdowns(
    before: PortfolioBreakdowns,
    after: PortfolioBreakdowns,
) -> list[AllocationDelta]:
    deltas: list[AllocationDelta] = []
    for dimension in DIMENSION_ORDER:
        before_rows = rows_by_key(getattr(before, dimension))
        after_rows = rows_by_key(getattr(after, dimension))
        for key in set(before_rows) | set(after_rows):
            before_percent = before_rows.get(key, Decimal("0.00"))
            after_percent = after_rows.get(key, Decimal("0.00"))
            label, currency = key
            deltas.append(
                AllocationDelta(
                    dimension=dimension,
                    label=label,
                    currency=currency,
                    percent_before=before_percent,
                    percent_after=after_percent,
                    percent_change=after_percent - before_percent,
                )
            )

    return sorted(
        deltas,
        key=lambda delta: (
            DIMENSION_ORDER.index(delta.dimension),
            -abs(delta.percent_change),
            delta.label,
            delta.currency,
        ),
    )


def copy_holding(holding: Holding) -> Holding:
    return Holding(
        id=holding.id,
        user_id=holding.user_id,
        instrument=holding.instrument,
        instrument_id=holding.instrument_id,
        quantity=holding.quantity,
        average_cost=holding.average_cost,
    )


def find_holding(holdings: list[Holding], leg: TradeLeg) -> Holding | None:
    if leg.instrument_id is not None:
        return next(
            (
                holding
                for holding in holdings
                if holding.instrument_id == leg.instrument_id
            ),
            None,
        )
    if leg.symbol is None:
        return None
    return next(
        (
            holding
            for holding in holdings
            if holding.instrument.symbol.upper() == leg.symbol
        ),
        None,
    )


def simulation_price(instrument: Instrument, close_price: Decimal) -> Price:
    return Price(
        instrument=instrument,
        instrument_id=instrument.id,
        price_date=SIMULATION_PRICE_DATE,
        close_price=close_price,
        currency=instrument.currency or "UNKNOWN",
        source="simulation",
    )


def synthetic_holding_id(holdings: list[Holding]) -> int:
    return -(len([holding for holding in holdings if holding.id < 0]) + 1)


def rows_by_key(rows: list[AllocationRow]) -> dict[tuple[str, str], Decimal]:
    return {(row.label, row.currency): row.percent for row in rows}
