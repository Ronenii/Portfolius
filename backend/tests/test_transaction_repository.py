from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.data.models import Instrument, Transaction
from app.data.repositories.transactions import (
    create_transaction,
    delete_transaction,
    get_holding_by_instrument,
    get_transaction_for_user,
    list_transactions_for_user,
    recompute_holding,
    to_legs,
    transactions_for_position,
    update_transaction,
)
from app.domain.transactions import InsufficientQuantityError, TransactionLeg

USER_ID = "user-123"
OTHER_USER_ID = "user-456"


@pytest.fixture
def instrument(db_session: Session) -> Instrument:
    instrument = Instrument(symbol="AAPL", exchange="NASDAQ", currency="USD")
    db_session.add(instrument)
    db_session.flush()
    return instrument


@pytest.fixture
def other_instrument(db_session: Session) -> Instrument:
    instrument = Instrument(symbol="MSFT", exchange="NASDAQ", currency="USD")
    db_session.add(instrument)
    db_session.flush()
    return instrument


def make_transaction(
    db_session: Session,
    instrument: Instrument,
    *,
    user_id: str = USER_ID,
    action: str = "buy",
    quantity: str = "10",
    price: str = "100",
    fees: str = "0",
    trade_date: date = date(2026, 1, 1),
) -> Transaction:
    return create_transaction(
        db_session,
        user_id,
        instrument_id=instrument.id,
        action=action,
        quantity=Decimal(quantity),
        price=Decimal(price),
        fees=Decimal(fees),
        currency="USD",
        trade_date=trade_date,
        notes=None,
    )


def test_to_legs_converts_transactions() -> None:
    transaction = Transaction(
        id=1,
        user_id=USER_ID,
        instrument_id=1,
        action="buy",
        quantity=Decimal("10"),
        price=Decimal("100"),
        fees=Decimal("1"),
        currency="USD",
        trade_date=date(2026, 1, 1),
    )

    legs = to_legs([transaction])

    assert legs == [
        TransactionLeg(
            id=1,
            trade_date=date(2026, 1, 1),
            action="buy",
            quantity=Decimal("10"),
            price=Decimal("100"),
            fees=Decimal("1"),
        )
    ]


def test_create_transaction_recomputes_holding(
    db_session: Session,
    instrument: Instrument,
) -> None:
    make_transaction(db_session, instrument, quantity="10", price="100")

    holding = get_holding_by_instrument(db_session, USER_ID, instrument.id)

    assert holding is not None
    assert holding.quantity == Decimal("10")
    assert holding.average_cost == Decimal("100")


def test_second_buy_recomputes_weighted_average_cost(
    db_session: Session,
    instrument: Instrument,
) -> None:
    make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )
    make_transaction(
        db_session, instrument, quantity="10", price="200", trade_date=date(2026, 1, 2)
    )

    holding = get_holding_by_instrument(db_session, USER_ID, instrument.id)

    assert holding is not None
    assert holding.quantity == Decimal("20")
    assert holding.average_cost == Decimal("150")


def test_transactions_for_position_orders_by_trade_date_then_id(
    db_session: Session,
    instrument: Instrument,
) -> None:
    second = make_transaction(
        db_session, instrument, quantity="5", price="10", trade_date=date(2026, 1, 2)
    )
    first = make_transaction(
        db_session, instrument, quantity="5", price="10", trade_date=date(2026, 1, 1)
    )

    ordered = transactions_for_position(db_session, USER_ID, instrument.id)

    assert [t.id for t in ordered] == [first.id, second.id]


def test_oversell_rolls_back_and_leaves_holding_unchanged(
    db_session: Session,
    instrument: Instrument,
) -> None:
    make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )

    with pytest.raises(InsufficientQuantityError):
        make_transaction(
            db_session,
            instrument,
            action="sell",
            quantity="20",
            price="120",
            trade_date=date(2026, 1, 2),
        )

    holding = get_holding_by_instrument(db_session, USER_ID, instrument.id)
    assert holding is not None
    assert holding.quantity == Decimal("10")
    assert holding.average_cost == Decimal("100")

    transactions = transactions_for_position(db_session, USER_ID, instrument.id)
    assert len(transactions) == 1


def test_sell_to_exact_zero_removes_holding(
    db_session: Session,
    instrument: Instrument,
) -> None:
    make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )
    make_transaction(
        db_session,
        instrument,
        action="sell",
        quantity="10",
        price="120",
        trade_date=date(2026, 1, 2),
    )

    holding = get_holding_by_instrument(db_session, USER_ID, instrument.id)
    assert holding is None


def test_update_transaction_recomputes_holding(
    db_session: Session,
    instrument: Instrument,
) -> None:
    transaction = make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )

    update_transaction(
        db_session,
        transaction,
        instrument_id=instrument.id,
        action="buy",
        quantity=Decimal("20"),
        price=Decimal("100"),
        fees=Decimal("0"),
        currency="USD",
        trade_date=date(2026, 1, 1),
        notes=None,
    )

    holding = get_holding_by_instrument(db_session, USER_ID, instrument.id)
    assert holding is not None
    assert holding.quantity == Decimal("20")
    assert holding.average_cost == Decimal("100")


def test_update_transaction_changing_instrument_recomputes_both(
    db_session: Session,
    instrument: Instrument,
    other_instrument: Instrument,
) -> None:
    transaction = make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )

    update_transaction(
        db_session,
        transaction,
        instrument_id=other_instrument.id,
        action="buy",
        quantity=Decimal("10"),
        price=Decimal("100"),
        fees=Decimal("0"),
        currency="USD",
        trade_date=date(2026, 1, 1),
        notes=None,
    )

    old_holding = get_holding_by_instrument(db_session, USER_ID, instrument.id)
    new_holding = get_holding_by_instrument(db_session, USER_ID, other_instrument.id)

    assert old_holding is None
    assert new_holding is not None
    assert new_holding.quantity == Decimal("10")


def test_update_transaction_oversell_rolls_back(
    db_session: Session,
    instrument: Instrument,
) -> None:
    make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )
    sell = make_transaction(
        db_session,
        instrument,
        action="sell",
        quantity="5",
        price="120",
        trade_date=date(2026, 1, 2),
    )

    with pytest.raises(InsufficientQuantityError):
        update_transaction(
            db_session,
            sell,
            instrument_id=instrument.id,
            action="sell",
            quantity=Decimal("50"),
            price=Decimal("120"),
            fees=Decimal("0"),
            currency="USD",
            trade_date=date(2026, 1, 2),
            notes=None,
        )

    holding = get_holding_by_instrument(db_session, USER_ID, instrument.id)
    assert holding is not None
    assert holding.quantity == Decimal("5")

    refreshed_sell = get_transaction_for_user(db_session, USER_ID, sell.id)
    assert refreshed_sell is not None
    assert refreshed_sell.quantity == Decimal("5")


def test_delete_transaction_recomputes_holding(
    db_session: Session,
    instrument: Instrument,
) -> None:
    first = make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )
    make_transaction(
        db_session, instrument, quantity="10", price="200", trade_date=date(2026, 1, 2)
    )

    delete_transaction(db_session, first)

    holding = get_holding_by_instrument(db_session, USER_ID, instrument.id)
    assert holding is not None
    assert holding.quantity == Decimal("10")
    assert holding.average_cost == Decimal("200")


def test_delete_that_would_go_negative_is_refused(
    db_session: Session,
    instrument: Instrument,
) -> None:
    first_buy = make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )
    make_transaction(
        db_session,
        instrument,
        action="sell",
        quantity="10",
        price="120",
        trade_date=date(2026, 1, 2),
    )

    with pytest.raises(InsufficientQuantityError):
        delete_transaction(db_session, first_buy)

    remaining = transactions_for_position(db_session, USER_ID, instrument.id)
    assert len(remaining) == 2


def test_recompute_holding_upserts_existing_row(
    db_session: Session,
    instrument: Instrument,
) -> None:
    make_transaction(
        db_session, instrument, quantity="10", price="100", trade_date=date(2026, 1, 1)
    )
    holding_before = get_holding_by_instrument(db_session, USER_ID, instrument.id)
    assert holding_before is not None
    holding_id = holding_before.id

    make_transaction(
        db_session, instrument, quantity="10", price="300", trade_date=date(2026, 1, 2)
    )

    holding_after = get_holding_by_instrument(db_session, USER_ID, instrument.id)
    assert holding_after is not None
    assert holding_after.id == holding_id
    assert holding_after.quantity == Decimal("20")
    assert holding_after.average_cost == Decimal("200")


def test_recompute_holding_with_no_transactions_returns_none(
    db_session: Session,
    instrument: Instrument,
) -> None:
    result = recompute_holding(db_session, USER_ID, instrument.id)
    db_session.commit()

    assert result is None
    assert get_holding_by_instrument(db_session, USER_ID, instrument.id) is None


def test_list_and_get_transactions_scoped_by_user(
    db_session: Session,
    instrument: Instrument,
) -> None:
    mine = make_transaction(db_session, instrument, quantity="10", price="100")
    make_transaction(
        db_session, instrument, user_id=OTHER_USER_ID, quantity="5", price="50"
    )

    mine_list = list_transactions_for_user(db_session, USER_ID)
    assert [t.id for t in mine_list] == [mine.id]

    fetched = get_transaction_for_user(db_session, USER_ID, mine.id)
    assert fetched is not None
    assert fetched.id == mine.id

    assert get_transaction_for_user(db_session, OTHER_USER_ID, mine.id) is None
