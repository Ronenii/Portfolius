from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, field_serializer, field_validator, model_validator

from app.schemas.portfolio import PortfolioBreakdowns


class TradeLeg(BaseModel):
    instrument_id: int | None = None
    symbol: str | None = None
    action: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip().upper()
        return normalized_value or None

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Quantity must be greater than zero")
        return value

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value < 0:
            raise ValueError("Price must be zero or greater")
        return value

    @model_validator(mode="after")
    def validate_identifier(self) -> "TradeLeg":
        has_instrument_id = self.instrument_id is not None
        has_symbol = self.symbol is not None
        if has_instrument_id == has_symbol:
            raise ValueError("Provide exactly one of instrument_id or symbol")
        return self


class AllocationDelta(BaseModel):
    dimension: str
    label: str
    currency: str
    percent_before: Decimal
    percent_after: Decimal
    percent_change: Decimal

    @field_serializer("percent_before", "percent_after", "percent_change")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class SimulationResponse(BaseModel):
    current: PortfolioBreakdowns
    simulated: PortfolioBreakdowns
    delta: list[AllocationDelta]
    warnings: list[str]


class SimulationRequest(BaseModel):
    legs: list[TradeLeg]
