from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed_value = value.strip()
    return trimmed_value or None


class HoldingRequest(BaseModel):
    symbol: str
    name: str | None = None
    exchange: str | None = ""
    currency: str | None = None
    asset_class: str | None = None
    sector: str | None = None
    country: str | None = None
    region: str | None = None
    quantity: Decimal
    average_cost: Decimal

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized_value = value.strip().upper()
        if not normalized_value:
            raise ValueError("Symbol cannot be empty")
        return normalized_value

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, value: str | None) -> str:
        if value is None:
            return ""
        return value.strip().upper()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        normalized_value = normalize_optional_text(value)
        if normalized_value is None:
            return None
        return normalized_value.upper()

    @field_validator("name", "asset_class", "sector", "country", "region")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Quantity must be greater than zero")
        return value

    @field_validator("average_cost")
    @classmethod
    def validate_average_cost(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("Average cost must be zero or greater")
        return value


class InstrumentResponse(BaseModel):
    id: int
    symbol: str
    name: str | None
    exchange: str
    currency: str | None
    asset_class: str | None
    sector: str | None
    country: str | None
    region: str | None

    model_config = ConfigDict(from_attributes=True)


class HoldingResponse(BaseModel):
    id: int
    instrument: InstrumentResponse
    quantity: Decimal
    average_cost: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("quantity", "average_cost")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)
