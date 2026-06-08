from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Instrument, Price
from app.data.repositories.holdings import list_holdings_for_user
from app.data.repositories.prices import get_latest_prices_for_instruments
from app.data.repositories.profiles import get_profile_by_user_id
from app.domain.allocation import build_allocation_breakdowns
from app.domain.portfolio_math import build_portfolio_snapshot
from app.domain.simulation import apply_trades, diff_breakdowns
from app.schemas.portfolio import PortfolioBreakdowns, PortfolioSnapshot
from app.schemas.simulation import SimulationResponse, TradeLeg


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


def simulate_for_user(
    db: Session,
    user_id: str,
    legs: list[TradeLeg],
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
            resolve_instrument=lambda symbol: resolve_local_instrument(db, symbol),
            resolve_price=lambda instrument_id: resolve_latest_price(db, instrument_id),
        )
    simulated_snapshot = build_portfolio_snapshot(
        profile,
        simulated_holdings,
        simulated_prices,
    )
    simulated_breakdowns = build_allocation_breakdowns(simulated_snapshot)

    return SimulationResponse(
        current=current_breakdowns,
        simulated=simulated_breakdowns,
        delta=diff_breakdowns(current_breakdowns, simulated_breakdowns),
        warnings=warnings,
    )


def resolve_local_instrument(db: Session, symbol: str) -> Instrument | None:
    normalized_symbol = symbol.strip().upper()
    return db.scalar(
        select(Instrument)
        .where(Instrument.symbol == normalized_symbol)
        .order_by(Instrument.exchange.desc(), Instrument.id)
    )


def resolve_latest_price(db: Session, instrument_id: int) -> Price | None:
    return get_latest_prices_for_instruments(db, [instrument_id]).get(instrument_id)
