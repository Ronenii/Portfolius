from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class InsufficientQuantityError(ValueError):
    """Raised when a sell leg exceeds the currently held quantity."""


@dataclass(frozen=True)
class TransactionLeg:
    id: int
    trade_date: date
    action: str
    quantity: Decimal
    price: Decimal
    fees: Decimal


@dataclass(frozen=True)
class PositionState:
    quantity: Decimal
    average_cost: Decimal
    total_cost: Decimal
    realized_gain: Decimal


EMPTY_POSITION = PositionState(
    quantity=Decimal("0"),
    average_cost=Decimal("0"),
    total_cost=Decimal("0"),
    realized_gain=Decimal("0"),
)


def sort_legs(legs: list[TransactionLeg]) -> list[TransactionLeg]:
    return sorted(legs, key=lambda leg: (leg.trade_date, leg.id))


def fold_transactions(legs: list[TransactionLeg]) -> PositionState:
    position = EMPTY_POSITION
    for leg in sort_legs(legs):
        if leg.action == "buy":
            position = apply_buy(position, leg)
        elif leg.action == "sell":
            position = apply_sell(position, leg)
        else:
            raise ValueError(f"Unknown action: {leg.action!r}")
    return position


def apply_buy(position: PositionState, leg: TransactionLeg) -> PositionState:
    total_cost = position.total_cost + (leg.quantity * leg.price) + leg.fees
    quantity = position.quantity + leg.quantity
    average_cost = total_cost / quantity

    return PositionState(
        quantity=quantity,
        average_cost=average_cost,
        total_cost=total_cost,
        realized_gain=position.realized_gain,
    )


def apply_sell(position: PositionState, leg: TransactionLeg) -> PositionState:
    if leg.quantity > position.quantity:
        raise InsufficientQuantityError(
            f"Cannot sell {leg.quantity} units; only {position.quantity} held."
        )

    realized_gain = position.realized_gain + (
        leg.quantity * (leg.price - position.average_cost) - leg.fees
    )
    quantity = position.quantity - leg.quantity

    if quantity == 0:
        total_cost = Decimal("0")
    else:
        total_cost = position.total_cost - (leg.quantity * position.average_cost)

    return PositionState(
        quantity=quantity,
        average_cost=position.average_cost,
        total_cost=total_cost,
        realized_gain=realized_gain,
    )
