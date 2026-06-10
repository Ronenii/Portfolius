import logging

from sqlalchemy.orm import Session

from app.data.models import Instrument
from app.data.repositories.holdings import list_etf_instruments_for_user_holdings
from app.data.repositories.instruments import (
    MANAGED_METADATA_FIELDS,
    refresh_instrument_metadata,
)
from app.schemas.instruments import InstrumentSearchResult
from app.schemas.jobs import MetadataRefreshResult

logger = logging.getLogger(__name__)


def describe_unfilled_fields(
    instrument: Instrument,
    profile: InstrumentSearchResult,
) -> list[str]:
    """List managed fields still null on the instrument and what the profile offered.

    This is the diagnostic for a "no change" skip: it shows which fields stayed
    empty and whether the provider returned a value the refresh could have used.
    """
    details: list[str] = []
    for field in MANAGED_METADATA_FIELDS:
        if getattr(instrument, field) is None:
            details.append(f"{field}(offered={getattr(profile, field)!r})")
    return details


def refresh_etf_metadata_for_user(
    db: Session,
    user_id: str,
    lookup_client,
) -> MetadataRefreshResult:
    instruments = list_etf_instruments_for_user_holdings(db, user_id)
    logger.info(
        "ETF metadata refresh: %d instrument(s) for user %s",
        len(instruments),
        user_id,
    )
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
            logger.info(
                "ETF metadata refresh skipped %s: provider returned no profile "
                "(both primary and ETF lookups were empty)",
                instrument.symbol,
            )
            skipped += 1
            continue

        if refresh_instrument_metadata(instrument, profile):
            logger.info("ETF metadata refresh updated %s", instrument.symbol)
            updated += 1
        else:
            unfilled = describe_unfilled_fields(instrument, profile)
            if unfilled:
                logger.info(
                    "ETF metadata refresh skipped %s: profile present but no field "
                    "changed; still-null fields: %s",
                    instrument.symbol,
                    ", ".join(unfilled),
                )
            else:
                logger.info(
                    "ETF metadata refresh skipped %s: profile present but no field "
                    "changed; all managed fields already populated",
                    instrument.symbol,
                )
            skipped += 1

    db.commit()
    logger.info(
        "ETF metadata refresh complete: requested=%d updated=%d skipped=%d failed=%d",
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
