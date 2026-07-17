from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    field_serializer,
    field_validator,
    model_validator,
)

from app.schemas.holdings import InstrumentResponse, normalize_optional_text


class TransactionRequest(BaseModel):
    instrument_id: int | None = None
    symbol: str | None = None
    name: str | None = None
    exchange: str | None = ""
    currency: str | None = None
    asset_class: str | None = None
    sector: str | None = None
    country: str | None = None
    region: str | None = None
    action: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal
    fees: Decimal = Decimal("0")
    trade_date: date
    notes: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip().upper()
        return normalized_value or None

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

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("Price must be zero or greater")
        return value

    @field_validator("fees")
    @classmethod
    def validate_fees(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("Fees must be zero or greater")
        return value

    @model_validator(mode="after")
    def validate_identifier(self) -> "TransactionRequest":
        has_instrument_id = self.instrument_id is not None
        has_symbol = self.symbol is not None
        if has_instrument_id == has_symbol:
            raise ValueError("Provide exactly one of instrument_id or symbol")
        return self


class TransactionResponse(BaseModel):
    id: int
    instrument: InstrumentResponse
    action: str
    quantity: Decimal
    price: Decimal
    fees: Decimal
    currency: str
    trade_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("quantity", "price", "fees")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)
