from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.data.models import Holding, Instrument, Transaction
from app.data.repositories.instruments import get_instrument_for_payload
from app.data.repositories.transactions import recompute_holding
from app.domain.transactions import InsufficientQuantityError
from app.schemas.holdings import HoldingRequest


def fill_missing_instrument_metadata(
    instrument: Instrument,
    payload: HoldingRequest,
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


def get_or_create_instrument(db: Session, payload: HoldingRequest) -> Instrument:
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


def _opening_balance_transaction(
    user_id: str,
    instrument: Instrument,
    payload: HoldingRequest,
) -> Transaction:
    currency = instrument.currency or "USD"
    return Transaction(
        user_id=user_id,
        instrument_id=instrument.id,
        action="buy",
        quantity=payload.quantity,
        price=payload.average_cost,
        fees=Decimal("0"),
        currency=currency,
        trade_date=date.today(),
        notes="Opening balance",
    )


def create_holding(db: Session, user_id: str, payload: HoldingRequest) -> Holding:
    instrument = get_or_create_instrument(db, payload)
    db.add(_opening_balance_transaction(user_id, instrument, payload))

    try:
        db.flush()
        holding = recompute_holding(db, user_id, instrument.id)
        db.commit()
    except InsufficientQuantityError:
        db.rollback()
        raise

    assert holding is not None
    db.refresh(holding)
    return holding


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


def update_holding(
    db: Session,
    holding: Holding,
    payload: HoldingRequest,
) -> Holding:
    # NOTE: If this update changes the instrument, the returned Holding will
    # have a different id than `holding.id`. Changing a holding's instrument
    # conceptually closes the old position (its transactions are deleted,
    # and recompute_holding removes the now-empty old Holding row) and opens
    # a new one under the new instrument (recompute_holding inserts a fresh
    # Holding row, since none existed for that instrument yet). This is
    # intentional, not a bug — callers must not assume the id is preserved
    # across an instrument change.
    user_id = holding.user_id
    old_instrument_id = holding.instrument_id

    new_instrument = get_or_create_instrument(db, payload)
    new_instrument_id = new_instrument.id

    db.execute(
        delete(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.instrument_id == old_instrument_id,
        )
    )
    db.add(_opening_balance_transaction(user_id, new_instrument, payload))

    try:
        db.flush()
        updated_holding = recompute_holding(db, user_id, old_instrument_id)
        if new_instrument_id != old_instrument_id:
            updated_holding = recompute_holding(db, user_id, new_instrument_id)
        db.commit()
    except InsufficientQuantityError:
        db.rollback()
        raise

    assert updated_holding is not None
    db.refresh(updated_holding)
    return updated_holding


def delete_holding(db: Session, holding: Holding) -> None:
    user_id = holding.user_id
    instrument_id = holding.instrument_id

    db.execute(
        delete(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.instrument_id == instrument_id,
        )
    )

    try:
        db.flush()
        recompute_holding(db, user_id, instrument_id)
        db.commit()
    except InsufficientQuantityError:
        db.rollback()
        raise
