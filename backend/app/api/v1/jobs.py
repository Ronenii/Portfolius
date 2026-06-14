from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthenticatedUser,
    bearer_scheme,
    decode_supabase_jwt,
    unauthorized,
)
from app.core.config import Settings, get_settings
from app.data.database import get_db
from app.domain.market_hours import is_us_market_open
from app.domain.metadata_refresh import refresh_instrument_metadata_for_all_instruments
from app.domain.price_refresh import (
    PriceRefreshResult,
    refresh_prices_for_all_users,
    refresh_prices_for_user,
)
from app.integrations.fmp import FmpInstrumentLookupClient
from app.integrations.instrument_lookup import CompositeInstrumentLookupClient
from app.integrations.market_data import MarketDataClient
from app.integrations.yfinance_client import YFinanceMarketDataClient
from app.integrations.yfinance_etf_profile import YFinanceEtfProfileClient
from app.schemas.jobs import MetadataRefreshResult

router = APIRouter(tags=["jobs"])


def get_market_data_client() -> MarketDataClient:
    return YFinanceMarketDataClient()


def get_instrument_lookup_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CompositeInstrumentLookupClient:
    return CompositeInstrumentLookupClient(
        FmpInstrumentLookupClient(settings.fmp_api_key),
        YFinanceEtfProfileClient(),
    )


def current_utc_time() -> datetime:
    return datetime.now(UTC)


def get_optional_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser | None:
    if credentials is None:
        return None

    claims = decode_supabase_jwt(credentials.credentials, settings)
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise unauthorized()

    email = claims.get("email")
    return AuthenticatedUser(
        user_id=subject,
        email=email if isinstance(email, str) else None,
        claims=claims,
    )


@router.post("/api/v1/jobs/refresh-prices", response_model=PriceRefreshResult)
def refresh_prices(
    db: Annotated[Session, Depends(get_db)],
    market_data_client: Annotated[MarketDataClient, Depends(get_market_data_client)],
    current_time: Annotated[datetime, Depends(current_utc_time)],
    settings: Annotated[Settings, Depends(get_settings)],
    current_user: Annotated[
        AuthenticatedUser | None,
        Depends(get_optional_current_user),
    ] = None,
    scheduler_secret: Annotated[str | None, Header(alias="X-Scheduler-Secret")] = None,
) -> PriceRefreshResult:
    is_scheduler = validate_scheduler_secret(settings, scheduler_secret)

    if is_scheduler and not is_us_market_open(current_time):
        return PriceRefreshResult(requested=0, updated=0, skipped=0, failed=0)

    if is_scheduler:
        return refresh_prices_for_all_users(db, market_data_client)

    if current_user is None:
        raise unauthorized()
    return refresh_prices_for_user(db, current_user.user_id, market_data_client)


@router.post(
    "/api/v1/jobs/refresh-etf-metadata",
    response_model=MetadataRefreshResult,
)
def refresh_etf_metadata(
    db: Annotated[Session, Depends(get_db)],
    lookup_client: Annotated[
        CompositeInstrumentLookupClient,
        Depends(get_instrument_lookup_client),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    scheduler_secret: Annotated[str | None, Header(alias="X-Scheduler-Secret")] = None,
) -> MetadataRefreshResult:
    if not validate_scheduler_secret(settings, scheduler_secret):
        raise unauthorized()
    return refresh_instrument_metadata_for_all_instruments(db, lookup_client)


def validate_scheduler_secret(
    settings: Settings,
    scheduler_secret: str | None,
) -> bool:
    if scheduler_secret is None:
        return False
    if not settings.scheduler_secret or scheduler_secret != settings.scheduler_secret:
        raise unauthorized()
    return True
