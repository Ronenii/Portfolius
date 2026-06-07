from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.data.repositories.holdings import list_holdings_for_user
from app.data.repositories.prices import get_latest_prices_for_instruments
from app.data.repositories.profiles import get_profile_by_user_id
from app.domain.allocation import build_allocation_breakdowns
from app.domain.portfolio_math import build_portfolio_snapshot
from app.schemas.portfolio import PortfolioBreakdowns, PortfolioSnapshot


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
