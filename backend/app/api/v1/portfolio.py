from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings, get_settings
from app.data.database import get_db
from app.domain.allocation import COMPOSITION_DIMENSIONS
from app.domain.portfolio_service import (
    build_breakdowns_for_user,
    build_composition_for_user,
    build_projection_for_user,
    build_snapshot_for_user,
    simulate_for_user,
)
from app.integrations.fmp import FmpInstrumentLookupClient
from app.integrations.instrument_lookup import CompositeInstrumentLookupClient
from app.integrations.market_data import MarketDataClient
from app.integrations.yfinance_client import YFinanceMarketDataClient
from app.integrations.yfinance_etf_profile import YFinanceEtfProfileClient
from app.schemas.portfolio import (
    CompositionResponse,
    PortfolioBreakdowns,
    PortfolioSnapshot,
    ProjectionResponse,
)
from app.schemas.simulation import SimulationRequest, SimulationResponse

router = APIRouter(tags=["portfolio"])


def get_instrument_lookup_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CompositeInstrumentLookupClient:
    return CompositeInstrumentLookupClient(
        FmpInstrumentLookupClient(api_key=settings.fmp_api_key),
        YFinanceEtfProfileClient(),
    )


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


@router.get(
    "/api/v1/portfolio/breakdowns/{dimension}/{key}/composition",
    response_model=CompositionResponse,
)
def read_portfolio_composition(
    dimension: str,
    key: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    currency: str | None = None,
) -> CompositionResponse:
    if dimension not in COMPOSITION_DIMENSIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown allocation dimension",
        )
    return build_composition_for_user(
        db,
        current_user.user_id,
        dimension,
        key,
        currency,
    )


@router.get("/api/v1/portfolio/projection", response_model=ProjectionResponse)
def read_portfolio_projection(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    target: Decimal | None = None,
    contribution: Decimal | None = None,
    annual_return: Decimal | None = None,
    years: int | None = None,
) -> ProjectionResponse:
    if target is not None and target < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target must be zero or greater",
        )
    if contribution is not None and contribution < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="contribution must be zero or greater",
        )
    if years is not None and years <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="years must be greater than zero",
        )
    return build_projection_for_user(
        db,
        current_user.user_id,
        target=target,
        contribution=contribution,
        annual_return=annual_return,
        years=years,
    )


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
