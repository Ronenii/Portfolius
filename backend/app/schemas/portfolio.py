from decimal import Decimal

from pydantic import BaseModel, field_serializer

from app.schemas.holdings import InstrumentResponse


class PortfolioHoldingSnapshot(BaseModel):
    holding_id: int
    instrument: InstrumentResponse
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    market_value: Decimal | None
    unrealized_gain: Decimal | None
    unrealized_gain_percent: Decimal | None
    price_status: str

    @field_serializer(
        "quantity",
        "average_cost",
        "cost_basis",
        "market_value",
        "unrealized_gain",
        "unrealized_gain_percent",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(value)


class PortfolioSummary(BaseModel):
    base_currency: str
    total_market_value: Decimal
    total_cost_basis: Decimal
    total_unrealized_gain: Decimal
    priced_holdings: int
    missing_price_holdings: int

    @field_serializer(
        "total_market_value",
        "total_cost_basis",
        "total_unrealized_gain",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class CurrencyTotal(BaseModel):
    currency: str
    market_value: Decimal
    cost_basis: Decimal
    unrealized_gain: Decimal

    @field_serializer("market_value", "cost_basis", "unrealized_gain")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class PortfolioSnapshot(BaseModel):
    summary: PortfolioSummary
    holdings: list[PortfolioHoldingSnapshot]
    currency_totals: dict[str, CurrencyTotal]


class AllocationRow(BaseModel):
    dimension: str
    label: str
    currency: str
    market_value: Decimal
    percent: Decimal
    holding_count: int

    @field_serializer("market_value", "percent")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class PortfolioBreakdowns(BaseModel):
    instrument: list[AllocationRow]
    asset_class: list[AllocationRow]
    sector: list[AllocationRow]
    country: list[AllocationRow]
    region: list[AllocationRow]
    currency: list[AllocationRow]
    unpriced_holding_count: int


class CompositionRow(BaseModel):
    instrument_id: int
    symbol: str
    name: str
    currency: str
    market_value: Decimal
    holding_count: int
    percent_of_parent: Decimal
    percent_of_portfolio: Decimal

    @field_serializer(
        "market_value",
        "percent_of_parent",
        "percent_of_portfolio",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class CompositionResponse(BaseModel):
    dimension: str
    key: str
    currency: str
    market_value: Decimal
    percent_of_portfolio: Decimal
    children: list[CompositionRow]
    unpriced_holding_count: int

    @field_serializer("market_value", "percent_of_portfolio")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)
