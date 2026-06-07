from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.data.models import Instrument
from app.schemas.holdings import HoldingRequest
from app.schemas.instruments import InstrumentSearchResult


def get_instrument_for_payload(
    db: Session,
    payload: HoldingRequest,
) -> Instrument | None:
    if payload.exchange:
        return db.scalar(
            select(Instrument).where(
                Instrument.symbol == payload.symbol,
                Instrument.exchange == payload.exchange,
            )
        )

    return db.scalar(
        select(Instrument)
        .where(Instrument.symbol == payload.symbol)
        .order_by(Instrument.exchange.desc(), Instrument.id)
    )


def instrument_has_useful_metadata(instrument: Instrument) -> bool:
    return all(
        [
            instrument.name,
            instrument.currency,
            instrument.asset_class,
            instrument.sector,
            instrument.country,
            instrument.region,
        ]
    )


def search_local_instruments(
    db: Session,
    query: str,
    limit: int = 10,
) -> list[InstrumentSearchResult]:
    normalized_query = query.strip().upper()
    if len(normalized_query) < 2:
        return []

    instruments = db.scalars(
        select(Instrument)
        .where(
            or_(
                Instrument.symbol.ilike(f"{normalized_query}%"),
                Instrument.name.ilike(f"%{query.strip()}%"),
            )
        )
        .order_by(Instrument.symbol, Instrument.exchange)
        .limit(limit)
    )
    return [instrument_to_search_result(instrument) for instrument in instruments]


def instrument_to_search_result(instrument: Instrument) -> InstrumentSearchResult:
    return InstrumentSearchResult(
        symbol=instrument.symbol,
        name=instrument.name,
        exchange=instrument.exchange or None,
        currency=instrument.currency,
        asset_class=instrument.asset_class,
        sector=instrument.sector,
        country=instrument.country,
        region=instrument.region,
        source="local",
    )
