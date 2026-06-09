from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings, get_settings
from app.data.database import get_db
from app.domain.portfolio_service import (
    build_breakdowns_for_user,
    build_snapshot_for_user,
    simulate_for_user,
)
from app.integrations.fmp import FmpInstrumentLookupClient
from app.integrations.market_data import MarketDataClient
from app.integrations.yfinance_client import YFinanceMarketDataClient
from app.schemas.portfolio import PortfolioBreakdowns, PortfolioSnapshot
from app.schemas.simulation import SimulationRequest, SimulationResponse

router = APIRouter(tags=["portfolio"])


def get_instrument_lookup_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FmpInstrumentLookupClient:
    return FmpInstrumentLookupClient(api_key=settings.fmp_api_key)


def get_market_data_client() -> MarketDataClient:
    return YFinanceMarketDataClient()


@router.get("/api/v1/portfolio/snapshot", response_model=PortfolioSnapshot)
def read_portfolio_snapshot(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PortfolioSnapshot:
    return build_snapshot_for_user(db, current_user.user_id)


@router.get("/api/v1/portfolio/breakdowns", response_model=PortfolioBreakdowns)
def read_portfolio_breakdowns(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PortfolioBreakdowns:
    return build_breakdowns_for_user(db, current_user.user_id)


@router.post("/api/v1/portfolio/simulate", response_model=SimulationResponse)
def simulate_portfolio(
    payload: SimulationRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    lookup_client: Annotated[
        FmpInstrumentLookupClient,
        Depends(get_instrument_lookup_client),
    ],
    market_data_client: Annotated[MarketDataClient, Depends(get_market_data_client)],
) -> SimulationResponse:
    return simulate_for_user(
        db,
        current_user.user_id,
        payload.legs,
        lookup_client,
        market_data_client,
    )
