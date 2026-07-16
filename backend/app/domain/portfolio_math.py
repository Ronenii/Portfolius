from decimal import ROUND_HALF_UP, Decimal

from app.data.models import Holding, Price, Profile
from app.schemas.holdings import InstrumentResponse
from app.schemas.portfolio import (
    CurrencyTotal,
    PortfolioHoldingSnapshot,
    PortfolioSnapshot,
    PortfolioSummary,
)

# Fallback assumed long-run annual returns (%) by asset_class, used only
# when an instrument has no computed `historical_annual_return` yet (see
# app/domain/historical_return_refresh.py). Keys are matched
# case/whitespace-insensitively against `Instrument.asset_class`.
ASSET_CLASS_DEFAULT_RETURN: dict[str, Decimal] = {
    "CRYPTO": Decimal("12"),
    "COMMODITY": Decimal("5"),
    "CASH": Decimal("2"),
    "MONEY MARKET": Decimal("2"),
}
# STOCK/ETF/FUND/ADR and any unrecognized/missing asset_class label.
EQUITY_LIKE_RETURN = Decimal("8")

RETURN_QUANTIZE = Decimal("0.01")


def build_portfolio_snapshot(
    profile: Profile,
    holdings: list[Holding],
    latest_prices: dict[int, Price],
) -> PortfolioSnapshot:
    holding_snapshots: list[PortfolioHoldingSnapshot] = []
    currency_totals: dict[str, CurrencyTotal] = {}
    total_market_value = Decimal("0")
    total_cost_basis = Decimal("0")
    total_unrealized_gain = Decimal("0")
    priced_holdings = 0
    missing_price_holdings = 0
    latest_price_date = None

    for holding in holdings:
        latest_price = latest_prices.get(holding.instrument_id)
        cost_basis = holding.quantity * holding.average_cost
        market_value: Decimal | None = None
        unrealized_gain: Decimal | None = None
        unrealized_gain_percent: Decimal | None = None
        price_status = "missing_price"

        if latest_price is None or not latest_price.close_price.is_finite():
            missing_price_holdings += 1
        else:
            priced_holdings += 1
            price_status = "priced"
            if latest_price_date is None or latest_price.price_date > latest_price_date:
                latest_price_date = latest_price.price_date
            market_value = holding.quantity * latest_price.close_price
            unrealized_gain = market_value - cost_basis
            if cost_basis > 0:
                unrealized_gain_percent = (unrealized_gain / cost_basis) * Decimal(
                    "100"
                )

            currency = latest_price.currency
            currency_totals[currency] = add_currency_total(
                currency_totals.get(currency),
                currency,
                market_value,
                cost_basis,
                unrealized_gain,
            )

            if holding.instrument.currency == profile.base_currency:
                total_market_value += market_value
                total_cost_basis += cost_basis
                total_unrealized_gain += unrealized_gain

        holding_snapshots.append(
            PortfolioHoldingSnapshot(
                holding_id=holding.id,
                instrument=InstrumentResponse.model_validate(holding.instrument),
                quantity=holding.quantity,
                average_cost=holding.average_cost,
                cost_basis=cost_basis,
                market_value=market_value,
                unrealized_gain=unrealized_gain,
                unrealized_gain_percent=unrealized_gain_percent,
                price_status=price_status,
            )
        )

    return PortfolioSnapshot(
        summary=PortfolioSummary(
            base_currency=profile.base_currency,
            total_market_value=total_market_value,
            total_cost_basis=total_cost_basis,
            total_unrealized_gain=total_unrealized_gain,
            priced_holdings=priced_holdings,
            missing_price_holdings=missing_price_holdings,
            latest_price_date=latest_price_date,
        ),
        holdings=holding_snapshots,
        currency_totals=currency_totals,
    )


def add_currency_total(
    current_total: CurrencyTotal | None,
    currency: str,
    market_value: Decimal,
    cost_basis: Decimal,
    unrealized_gain: Decimal,
) -> CurrencyTotal:
    if current_total is None:
        return CurrencyTotal(
            currency=currency,
            market_value=market_value,
            cost_basis=cost_basis,
            unrealized_gain=unrealized_gain,
        )

    return CurrencyTotal(
        currency=currency,
        market_value=current_total.market_value + market_value,
        cost_basis=current_total.cost_basis + cost_basis,
        unrealized_gain=current_total.unrealized_gain + unrealized_gain,
    )


def compute_weighted_average_return(
    holdings: list[PortfolioHoldingSnapshot], base_currency: str
) -> Decimal | None:
    qualifying = [
        held
        for held in holdings
        if held.market_value is not None
        and held.instrument.currency == base_currency
    ]
    if not qualifying:
        return None

    total_value = sum((held.market_value for held in qualifying), Decimal("0"))
    if total_value <= 0:
        return None

    weighted_sum = Decimal("0")
    for held in qualifying:
        rate = held.instrument.historical_annual_return
        if rate is None:
            normalized_class = (
                held.instrument.asset_class.strip().upper()
                if held.instrument.asset_class
                else None
            )
            rate = ASSET_CLASS_DEFAULT_RETURN.get(normalized_class, EQUITY_LIKE_RETURN)
        weighted_sum += (held.market_value / total_value) * rate

    return weighted_sum.quantize(RETURN_QUANTIZE, rounding=ROUND_HALF_UP)
