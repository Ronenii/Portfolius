from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Holding, Instrument
from app.schemas.holdings import HoldingRequest


def get_or_create_instrument(db: Session, payload: HoldingRequest) -> Instrument:
    instrument = db.scalar(
        select(Instrument).where(
            Instrument.symbol == payload.symbol,
            Instrument.exchange == payload.exchange,
        )
    )
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

    return instrument


def create_holding(db: Session, user_id: str, payload: HoldingRequest) -> Holding:
    instrument = get_or_create_instrument(db, payload)
    holding = Holding(
        user_id=user_id,
        instrument=instrument,
        quantity=payload.quantity,
        average_cost=payload.average_cost,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)
    return holding


def list_holdings_for_user(db: Session, user_id: str) -> list[Holding]:
    return list(db.scalars(select(Holding).where(Holding.user_id == user_id)))


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


def update_holding(
    db: Session,
    holding: Holding,
    payload: HoldingRequest,
) -> Holding:
    holding.instrument = get_or_create_instrument(db, payload)
    holding.quantity = payload.quantity
    holding.average_cost = payload.average_cost
    db.commit()
    db.refresh(holding)
    return holding


def delete_holding(db: Session, holding: Holding) -> None:
    db.delete(holding)
    db.commit()
