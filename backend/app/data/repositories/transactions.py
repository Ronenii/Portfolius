from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.data.models import Holding, Instrument, Transaction
from app.domain.transactions import (
    InsufficientQuantityError,
    TransactionLeg,
    fold_transactions,
)


def transactions_for_position(
    db: Session,
    user_id: str,
    instrument_id: int,
) -> list[Transaction]:
    return list(
        db.scalars(
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.instrument_id == instrument_id,
            )
            .order_by(Transaction.trade_date, Transaction.id)
        )
    )


def to_legs(transactions: list[Transaction]) -> list[TransactionLeg]:
    return [
        TransactionLeg(
            id=transaction.id,
            trade_date=transaction.trade_date,
            action=transaction.action,
            quantity=transaction.quantity,
            price=transaction.price,
            fees=transaction.fees,
        )
        for transaction in transactions
    ]


def get_holding_by_instrument(
    db: Session,
    user_id: str,
    instrument_id: int,
) -> Holding | None:
    return db.scalar(
        select(Holding).where(
            Holding.user_id == user_id,
            Holding.instrument_id == instrument_id,
        )
    )


def list_transactions_for_user(
    db: Session,
    user_id: str,
    *,
    instrument_id: int | None = None,
    symbol: str | None = None,
) -> list[Transaction]:
    """List a user's transactions, most recent first.

    Optionally filtered to a single instrument, by id or by symbol (exactly
    one or neither -- the caller is responsible for rejecting requests that
    pass both).
    """
    # Eager-load the instrument: the response reads transaction.instrument per
    # row, so a lazy-load would issue an N+1 query per transaction.
    query = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .options(selectinload(Transaction.instrument))
    )

    if instrument_id is not None:
        query = query.where(Transaction.instrument_id == instrument_id)

    if symbol is not None:
        query = query.join(Instrument).where(Instrument.symbol == symbol)

    query = query.order_by(Transaction.trade_date.desc(), Transaction.id.desc())
    return list(db.scalars(query))


def get_transaction_for_user(
    db: Session,
    user_id: str,
    transaction_id: int,
) -> Transaction | None:
    return db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )


def recompute_holding(
    db: Session,
    user_id: str,
    instrument_id: int,
) -> Holding | None:
    """Replay every transaction for (user_id, instrument_id) through the fold
    and upsert the derived holding row to match. Deletes the holding instead
    of writing a zero row when the position is fully closed.

    Does NOT commit: flushes only, so the caller controls the transaction
    boundary (and can roll back atomically if the fold rejects a leg).
    """
    legs = to_legs(transactions_for_position(db, user_id, instrument_id))
    position = fold_transactions(legs)

    holding = get_holding_by_instrument(db, user_id, instrument_id)

    if position.quantity == 0:
        if holding is not None:
            db.delete(holding)
            db.flush()
        return None

    if holding is None:
        holding = Holding(
            user_id=user_id,
            instrument_id=instrument_id,
            quantity=position.quantity,
            average_cost=position.average_cost,
        )
        db.add(holding)
    else:
        holding.quantity = position.quantity
        holding.average_cost = position.average_cost

    db.flush()
    return holding


def create_transaction(
    db: Session,
    user_id: str,
    *,
    instrument_id: int,
    action: str,
    quantity: Decimal,
    price: Decimal,
    fees: Decimal,
    currency: str,
    trade_date: date,
    notes: str | None = None,
) -> Transaction:
    transaction = Transaction(
        user_id=user_id,
        instrument_id=instrument_id,
        action=action,
        quantity=quantity,
        price=price,
        fees=fees,
        currency=currency,
        trade_date=trade_date,
        notes=notes,
    )
    db.add(transaction)
    try:
        db.flush()
        recompute_holding(db, user_id, instrument_id)
        db.commit()
    except InsufficientQuantityError:
        db.rollback()
        raise
    db.refresh(transaction)
    return transaction


def update_transaction(
    db: Session,
    transaction: Transaction,
    *,
    instrument_id: int,
    action: str,
    quantity: Decimal,
    price: Decimal,
    fees: Decimal,
    currency: str,
    trade_date: date,
    notes: str | None = None,
) -> Transaction:
    user_id = transaction.user_id
    old_instrument_id = transaction.instrument_id

    transaction.instrument_id = instrument_id
    transaction.action = action
    transaction.quantity = quantity
    transaction.price = price
    transaction.fees = fees
    transaction.currency = currency
    transaction.trade_date = trade_date
    transaction.notes = notes

    try:
        db.flush()
        recompute_holding(db, user_id, old_instrument_id)
        if instrument_id != old_instrument_id:
            recompute_holding(db, user_id, instrument_id)
        db.commit()
    except InsufficientQuantityError:
        db.rollback()
        raise
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction: Transaction) -> None:
    user_id = transaction.user_id
    instrument_id = transaction.instrument_id

    db.delete(transaction)
    try:
        db.flush()
        recompute_holding(db, user_id, instrument_id)
        db.commit()
    except InsufficientQuantityError:
        db.rollback()
        raise
