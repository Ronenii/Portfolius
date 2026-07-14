from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.data.models import Holding, Instrument
from app.data.repositories.instruments import get_instrument_for_payload
from app.schemas.transactions import TransactionRequest


def fill_missing_instrument_metadata(
    instrument: Instrument,
    payload: TransactionRequest,
) -> None:
    for field in (
        "name",
        "currency",
        "asset_class",
        "sector",
        "country",
        "region",
    ):
        if getattr(instrument, field) is None and getattr(payload, field) is not None:
            setattr(instrument, field, getattr(payload, field))


def get_or_create_instrument(db: Session, payload: TransactionRequest) -> Instrument:
    instrument = get_instrument_for_payload(db, payload)
    if instrument is None:
        instrument = Instrument(
            symbol=payload.symbol,
            name=payload.name,
            exchange=payload.exchange,
            currency=payload.currency,
            asset_class=payload.asset_class,
            sector=payload.sector,
            country=payload.country,
            region=payload.region,
        )
        db.add(instrument)
        db.flush()
    else:
        fill_missing_instrument_metadata(instrument, payload)

    return instrument


def list_holdings_for_user(db: Session, user_id: str) -> list[Holding]:
    # Eager-load the instrument: the snapshot reads holding.instrument per row,
    # so a lazy-load would issue an N+1 query per holding.
    return list(
        db.scalars(
            select(Holding)
            .where(Holding.user_id == user_id)
            .options(selectinload(Holding.instrument))
        )
    )


def list_instruments_for_user_holdings(
    db: Session,
    user_id: str,
) -> list[Instrument]:
    return list(
        db.scalars(
            select(Instrument)
            .join(Holding)
            .where(Holding.user_id == user_id)
            .distinct()
            .order_by(Instrument.symbol, Instrument.exchange)
        )
    )


def list_etf_instruments_for_user_holdings(
    db: Session,
    user_id: str,
) -> list[Instrument]:
    return list(
        db.scalars(
            select(Instrument)
            .join(Holding)
            .where(
                Holding.user_id == user_id,
                func.lower(Instrument.asset_class) == "etf",
            )
            .distinct()
            .order_by(Instrument.symbol, Instrument.exchange)
        )
    )


def list_all_instruments_with_holdings(db: Session) -> list[Instrument]:
    return list(
        db.scalars(
            select(Instrument)
            .join(Holding)
            .distinct()
            .order_by(Instrument.symbol, Instrument.exchange)
        )
    )


def get_holding_for_user(
    db: Session,
    user_id: str,
    holding_id: int,
) -> Holding | None:
    return db.scalar(
        select(Holding).where(
            Holding.id == holding_id,
            Holding.user_id == user_id,
        )
    )
