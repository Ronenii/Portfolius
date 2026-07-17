import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Instrument
from app.data.repositories.instruments import list_all_instruments
from app.integrations.market_data import MarketDataClient
from app.schemas.jobs import HistoricalReturnRefreshResult

logger = logging.getLogger(__name__)


def refresh_historical_returns_for_all_instruments(
    db: Session,
    market_data_client: MarketDataClient,
) -> HistoricalReturnRefreshResult:
    instruments = list_all_instruments(db)
    updated = 0
    skipped = 0
    failed = 0

    for instrument in instruments:
        try:
            annualized_return = market_data_client.get_historical_annualized_return(
                instrument.symbol,
                instrument.exchange,
                instrument.currency,
            )
        except Exception:
            logger.exception(
                "Historical return refresh failed for %s", instrument.symbol
            )
            failed += 1
            continue

        if annualized_return is None:
            skipped += 1
            continue

        instrument.historical_annual_return = annualized_return
        instrument.historical_return_updated_at = datetime.now(UTC)
        updated += 1

    db.commit()
    logger.info(
        "Historical return refresh complete: "
        "requested=%d updated=%d skipped=%d failed=%d",
        len(instruments),
        updated,
        skipped,
        failed,
    )
    return HistoricalReturnRefreshResult(
        requested=len(instruments),
        updated=updated,
        skipped=skipped,
        failed=failed,
    )


def historical_returns_never_computed(db: Session) -> bool:
    return (
        db.scalar(
            select(Instrument.id).where(
                Instrument.historical_return_updated_at.is_not(None)
            )
        )
        is None
    )


def bootstrap_historical_returns_if_never_run(
    db: Session,
    market_data_client: MarketDataClient,
) -> HistoricalReturnRefreshResult | None:
    if not historical_returns_never_computed(db):
        return None
    return refresh_historical_returns_for_all_instruments(db, market_data_client)
