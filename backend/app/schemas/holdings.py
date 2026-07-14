from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed_value = value.strip()
    return trimmed_value or None



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
