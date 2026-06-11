import logging

from sqlalchemy.orm import Session

from app.data.models import Instrument
from app.data.repositories.instruments import (
    MANAGED_METADATA_FIELDS,
    list_all_instruments,
    refresh_instrument_metadata,
)
from app.schemas.instruments import InstrumentSearchResult
from app.schemas.jobs import MetadataRefreshResult

logger = logging.getLogger(__name__)


def describe_no_change(
    instrument: Instrument,
    profile: InstrumentSearchResult,
) -> str:
    """Explain a "no change" skip: per-field stored value vs what the profile offered.

    A field is only updated when the provider offers a non-null value that differs
    from what is stored. "No change" therefore means every offered value was either
    None or already equal to the stored value. Logging the profile ``source`` and the
    offered-vs-stored values reveals the common cause: when ``source`` lacks
    ``alphavantage``, the ETF profile lookup returned nothing (missing key, rate
    limit, or no coverage) and the composite fell back to the existing data, so wrong
    legacy values are never corrected.
    """
    fields: list[str] = []
    for field in MANAGED_METADATA_FIELDS:
        stored = getattr(instrument, field)
        offered = getattr(profile, field)
        fields.append(f"{field}: stored={stored!r} offered={offered!r}")
    return f"source={profile.source!r}; " + "; ".join(fields)


def refresh_instrument_metadata_for_all_instruments(
    db: Session,
    lookup_client,
    force: bool = False,
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

        if refresh_instrument_metadata(instrument, profile, force=force):
            logger.info("Instrument metadata refresh updated %s", instrument.symbol)
            updated += 1
        else:
            logger.info(
                "Instrument metadata refresh skipped %s: profile present but no field "
                "changed; %s",
                instrument.symbol,
                describe_no_change(instrument, profile),
            )
            skipped += 1

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
