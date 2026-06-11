from decimal import Decimal

from app.data.models import Holding, Price, Profile
from app.schemas.holdings import InstrumentResponse
from app.schemas.portfolio import (
    CurrencyTotal,
    PortfolioHoldingSnapshot,
    PortfolioSnapshot,
    PortfolioSummary,
)


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
