from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Instrument, Price
from app.data.repositories.holdings import list_holdings_for_user
from app.data.repositories.prices import (
    get_latest_prices_for_instruments,
    upsert_price,
)
from app.data.repositories.profiles import get_profile_by_user_id
from app.domain.allocation import build_allocation_breakdowns, build_composition
from app.domain.portfolio_math import (
    build_portfolio_snapshot,
    compute_weighted_average_return,
)
from app.domain.projection import build_projection
from app.domain.simulation import apply_trades, diff_breakdowns
from app.integrations.market_data import MarketDataClient
from app.schemas.instruments import InstrumentSearchResult
from app.schemas.portfolio import (
    CompositionResponse,
    PortfolioBreakdowns,
    PortfolioSnapshot,
    ProjectionResponse,
)
from app.schemas.simulation import SimulationResponse, TradeLeg

# Risk-tolerance -> expected annual return (%) default, used when
# `compute_weighted_average_return` has no qualifying holdings to compute
# from. Keys mirror `schemas/profile.py`'s `RISK_TOLERANCES`, which already
# normalizes and validates `risk_tolerance` to one of these three strings
# (or `None`).
RISK_TOLERANCE_DEFAULT_RETURN = {
    "conservative": Decimal("4"),
    "balanced": Decimal("6"),
    "aggressive": Decimal("8"),
}
# Used when risk_tolerance is also unset/unrecognized.
DEFAULT_ANNUAL_RETURN = Decimal("6")

# Time-horizon label -> projection years. `time_horizon` is a free-form
# string field (not DB-constrained), but the frontend only ever sends these
# four exact labels (see `ProfileWizardPage.tsx`/`ProfileEditPage.tsx`).
HORIZON_YEARS = {
    "1-3 years": 3,
    "3-7 years": 7,
    "7-10 years": 10,
    "10+ years": 15,
}
# Used when `time_horizon` doesn't match a known label, mirroring the same
# "unrecognized input falls back to a sensible default" precedent
# `domain/projection.py` established for `frequency`.
DEFAULT_HORIZON_YEARS = 7


class InstrumentLookupClient:
    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        ...


def profile_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Profile not found",
    )


def build_snapshot_for_user(db: Session, user_id: str) -> PortfolioSnapshot:
    profile = get_profile_by_user_id(db, user_id)
    if profile is None:
        raise profile_not_found()

    holdings = list_holdings_for_user(db, user_id)
    latest_prices = get_latest_prices_for_instruments(
        db,
        [holding.instrument_id for holding in holdings],
    )
    return build_portfolio_snapshot(profile, holdings, latest_prices)


def build_breakdowns_for_user(db: Session, user_id: str) -> PortfolioBreakdowns:
    return build_allocation_breakdowns(build_snapshot_for_user(db, user_id))


def build_composition_for_user(
    db: Session,
    user_id: str,
    dimension: str,
    key: str,
    currency: str | None = None,
) -> CompositionResponse:
    snapshot = build_snapshot_for_user(db, user_id)
    return build_composition(snapshot, dimension, key, currency=currency)


def build_projection_for_user(
    db: Session,
    user_id: str,
    *,
    target: Decimal | None = None,
    contribution: Decimal | None = None,
    annual_return: Decimal | None = None,
    years: int | None = None,
) -> ProjectionResponse:
    profile = get_profile_by_user_id(db, user_id)
    if profile is None:
        raise profile_not_found()

    snapshot = build_snapshot_for_user(db, user_id)

    resolved_target = target if target is not None else profile.goal_target_amount
    resolved_contribution = (
        contribution if contribution is not None else profile.contribution_amount
    )

    if annual_return is not None:
        resolved_annual_return = annual_return
    else:
        computed_return = compute_weighted_average_return(
            snapshot.holdings, snapshot.summary.base_currency
        )
        resolved_annual_return = (
            computed_return
            if computed_return is not None
            else RISK_TOLERANCE_DEFAULT_RETURN.get(
                profile.risk_tolerance, DEFAULT_ANNUAL_RETURN
            )
        )

    if years is not None:
        resolved_years = years
    else:
        resolved_years = HORIZON_YEARS.get(
            profile.time_horizon.strip(), DEFAULT_HORIZON_YEARS
        )

    return build_projection(
        base_currency=snapshot.summary.base_currency,
        start_value=snapshot.summary.total_market_value,
        start_cost_basis=snapshot.summary.total_cost_basis,
        target=resolved_target,
        contribution=resolved_contribution,
        annual_return=resolved_annual_return,
        years=resolved_years,
        frequency=profile.investment_frequency,
    )


def simulate_for_user(
    db: Session,
    user_id: str,
    legs: list[TradeLeg],
    lookup_client: InstrumentLookupClient | None = None,
    market_data_client: MarketDataClient | None = None,
) -> SimulationResponse:
    profile = get_profile_by_user_id(db, user_id)
    if profile is None:
        raise profile_not_found()

    holdings = list_holdings_for_user(db, user_id)
    latest_prices = get_latest_prices_for_instruments(
        db,
        [holding.instrument_id for holding in holdings],
    )
    current_snapshot = build_portfolio_snapshot(profile, holdings, latest_prices)
    current_breakdowns = build_allocation_breakdowns(current_snapshot)

    with db.no_autoflush:
        simulated_holdings, simulated_prices, warnings = apply_trades(
            holdings,
            latest_prices,
            legs,
            resolve_instrument=lambda symbol: resolve_or_create_instrument(
                db,
                symbol,
                lookup_client,
            ),
            resolve_price=lambda instrument_id: resolve_latest_price(
                db,
                instrument_id,
                market_data_client,
            ),
        )
    with db.no_autoflush:
        simulated_snapshot = build_portfolio_snapshot(
            profile,
            simulated_holdings,
            simulated_prices,
        )
    simulated_breakdowns = build_allocation_breakdowns(simulated_snapshot)

    response = SimulationResponse(
        current=current_breakdowns,
        simulated=simulated_breakdowns,
        delta=diff_breakdowns(current_breakdowns, simulated_breakdowns),
        warnings=warnings,
    )
    db.rollback()
    return response


def resolve_local_instrument(db: Session, symbol: str) -> Instrument | None:
    normalized_symbol = symbol.strip().upper()
    return db.scalar(
        select(Instrument)
        .where(Instrument.symbol == normalized_symbol)
        .order_by(Instrument.exchange.desc(), Instrument.id)
    )


def resolve_or_create_instrument(
    db: Session,
    symbol: str,
    lookup_client: InstrumentLookupClient | None,
) -> Instrument | None:
    local_instrument = resolve_local_instrument(db, symbol)
    if local_instrument is not None:
        return local_instrument

    if lookup_client is None:
        return None

    profile = lookup_client.profile(symbol.strip().upper())
    if profile is None:
        return None

    instrument = Instrument(
        symbol=profile.symbol,
        name=profile.name,
        exchange=profile.exchange or "",
        currency=profile.currency,
        asset_class=profile.asset_class,
        sector=profile.sector,
        country=profile.country,
        region=profile.region,
    )
    db.add(instrument)
    db.flush()
    db.commit()
    db.refresh(instrument)
    return instrument


def resolve_latest_price(
    db: Session,
    instrument_id: int,
    market_data_client: MarketDataClient | None = None,
) -> Price | None:
    existing_price = get_latest_prices_for_instruments(db, [instrument_id]).get(
        instrument_id
    )
    if market_data_client is None:
        return existing_price

    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        return existing_price

    try:
        market_price = market_data_client.get_latest_close(
            instrument.symbol,
            instrument.exchange,
            instrument.currency,
        )
    except Exception:
        return existing_price

    if market_price is None:
        return existing_price

    price = upsert_price(db, instrument, market_price)
    db.commit()
    db.refresh(price)
    return price
