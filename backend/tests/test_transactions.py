from datetime import date
from decimal import Decimal

import pytest

from app.domain.transactions import (
    InsufficientQuantityError,
    PositionState,
    TransactionLeg,
    fold_transactions,
    sort_legs,
)


def leg(
    leg_id: int,
    action: str,
    quantity: str,
    price: str,
    fees: str = "0",
    trade_date: date = date(2026, 1, 1),
) -> TransactionLeg:
    return TransactionLeg(
        id=leg_id,
        trade_date=trade_date,
        action=action,
        quantity=Decimal(quantity),
        price=Decimal(price),
        fees=Decimal(fees),
    )


def test_single_buy_sets_quantity_and_average_cost() -> None:
    legs = [leg(1, "buy", "10", "100")]

    position = fold_transactions(legs)

    assert position == PositionState(
        quantity=Decimal("10"),
        average_cost=Decimal("100"),
        total_cost=Decimal("1000"),
        realized_gain=Decimal("0"),
    )


def test_two_buys_average_correctly() -> None:
    legs = [
        leg(1, "buy", "10", "100", trade_date=date(2026, 1, 1)),
        leg(2, "buy", "10", "200", trade_date=date(2026, 1, 2)),
    ]

    position = fold_transactions(legs)

    assert position.quantity == Decimal("20")
    assert position.total_cost == Decimal("3000")
    assert position.average_cost == Decimal("150")
    assert position.realized_gain == Decimal("0")


def test_buy_then_sell_realizes_gain_and_keeps_average_cost() -> None:
    legs = [
        leg(1, "buy", "10", "100", trade_date=date(2026, 1, 1)),
        leg(2, "sell", "4", "150", trade_date=date(2026, 1, 2)),
    ]

    position = fold_transactions(legs)

    assert position.quantity == Decimal("6")
    assert position.average_cost == Decimal("100")
    assert position.total_cost == Decimal("600")
    assert position.realized_gain == Decimal("200")


def test_sell_to_exactly_zero_resets_total_cost() -> None:
    legs = [
        leg(1, "buy", "10", "100", trade_date=date(2026, 1, 1)),
        leg(2, "sell", "10", "120", trade_date=date(2026, 1, 2)),
    ]

    position = fold_transactions(legs)

    assert position.quantity == Decimal("0")
    assert position.total_cost == Decimal("0")
    assert position.average_cost == Decimal("100")
    assert position.realized_gain == Decimal("200")


def test_oversell_raises_insufficient_quantity_error() -> None:
    legs = [
        leg(1, "buy", "10", "100", trade_date=date(2026, 1, 1)),
        leg(2, "sell", "11", "120", trade_date=date(2026, 1, 2)),
    ]

    with pytest.raises(InsufficientQuantityError):
        fold_transactions(legs)


def test_unknown_action_raises_value_error() -> None:
    legs = [leg(1, "dividend", "10", "100")]

    with pytest.raises(ValueError, match="Unknown action"):
        fold_transactions(legs)


def test_out_of_order_legs_fold_deterministically_by_date_then_id() -> None:
    ordered = [
        leg(1, "buy", "10", "100", trade_date=date(2026, 1, 1)),
        leg(2, "sell", "4", "150", trade_date=date(2026, 1, 2)),
    ]
    shuffled = [ordered[1], ordered[0]]

    assert fold_transactions(shuffled) == fold_transactions(ordered)
    assert sort_legs(shuffled) == ordered


def test_sort_legs_breaks_same_date_ties_by_id() -> None:
    same_day = date(2026, 3, 1)
    first = leg(1, "buy", "5", "100", trade_date=same_day)
    second = leg(2, "buy", "5", "100", trade_date=same_day)

    assert sort_legs([second, first]) == [first, second]


def test_fees_capitalized_on_buy_and_deducted_on_sell() -> None:
    legs = [
        leg(1, "buy", "10", "100", fees="10", trade_date=date(2026, 1, 1)),
        leg(2, "sell", "10", "100", fees="5", trade_date=date(2026, 1, 2)),
    ]

    position = fold_transactions(legs)

    assert position.quantity == Decimal("0")
    assert position.average_cost == Decimal("101")
    assert position.total_cost == Decimal("0")
    assert position.realized_gain == Decimal("-15")
