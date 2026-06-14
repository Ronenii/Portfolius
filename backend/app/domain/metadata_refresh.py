import logging

from sqlalchemy.orm import Session

from app.data.repositories.instruments import (
    list_all_instruments,
    refresh_instrument_metadata,
)
from app.schemas.jobs import MetadataRefreshResult

logger = logging.getLogger(__name__)


def refresh_instrument_metadata_for_all_instruments(
    db: Session,
    lookup_client,
) -> MetadataRefreshResult:
    instruments = list_all_instruments(db)
    logger.info(
        "Instrument metadata refresh: %d instrument(s)",
        len(instruments),
    )
    updated = 0
    skipped = 0
    failed = 0

    for instrument in instruments:
        try:
            profile = lookup_client.profile(instrument.symbol)
        except Exception:
            logger.exception(
                "Instrument metadata refresh failed for %s",
                instrument.symbol,
            )
            failed += 1
            continue

        if profile is None:
            logger.info(
                "Instrument metadata refresh skipped %s: provider returned no profile "
                "(both primary and ETF lookups were empty)",
                instrument.symbol,
            )
            skipped += 1
            continue

        refresh_instrument_metadata(instrument, profile)
        logger.info("Instrument metadata refresh updated %s", instrument.symbol)
        updated += 1

    db.commit()
    logger.info(
        "Instrument metadata refresh complete: "
        "requested=%d updated=%d skipped=%d failed=%d",
        len(instruments),
        updated,
        skipped,
        failed,
    )
    return MetadataRefreshResult(
        requested=len(instruments),
        updated=updated,
        skipped=skipped,
        failed=failed,
    )
