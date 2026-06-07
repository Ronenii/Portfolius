import logging
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends

from app.core.auth import AuthenticatedUser, get_current_user, unauthorized
from app.core.config import Settings, get_settings
from app.integrations.fmp import FmpInstrumentLookupClient
from app.schemas.instruments import InstrumentSearchResult

logger = logging.getLogger(__name__)
router = APIRouter(tags=["instruments"])


class InstrumentLookupClient(Protocol):
    def search(self, query: str, limit: int = 10) -> list[InstrumentSearchResult]:
        ...

    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        ...


def get_instrument_lookup_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> InstrumentLookupClient:
    return FmpInstrumentLookupClient(api_key=settings.fmp_api_key)


@router.get(
    "/api/v1/instruments/search",
    response_model=list[InstrumentSearchResult],
)
def search_instruments(
    query: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    lookup_client: Annotated[
        InstrumentLookupClient,
        Depends(get_instrument_lookup_client),
    ],
) -> list[InstrumentSearchResult]:
    if current_user is None:
        raise unauthorized()

    if len(query.strip()) < 2:
        return []

    try:
        return lookup_client.search(query, limit=10)
    except Exception:
        logger.exception("Instrument search failed")
        return []
