import logging

from sqlalchemy.orm import Session

from app.data.repositories.holdings import list_etf_instruments_for_user_holdings
from app.data.repositories.instruments import refresh_instrument_metadata
from app.schemas.jobs import MetadataRefreshResult

logger = logging.getLogger(__name__)


def refresh_etf_metadata_for_user(
    db: Session,
    user_id: str,
    lookup_client,
) -> MetadataRefreshResult:
    instruments = list_etf_instruments_for_user_holdings(db, user_id)
    updated = 0
    skipped = 0
    failed = 0

    for instrument in instruments:
        try:
            profile = lookup_client.profile(instrument.symbol)
        except Exception:
            logger.exception("ETF metadata refresh failed for %s", instrument.symbol)
            failed += 1
            continue

        if profile is None:
            skipped += 1
            continue

        if refresh_instrument_metadata(instrument, profile):
            updated += 1
        else:
            skipped += 1

    db.commit()
    return MetadataRefreshResult(
        requested=len(instruments),
        updated=updated,
        skipped=skipped,
        failed=failed,
    )
