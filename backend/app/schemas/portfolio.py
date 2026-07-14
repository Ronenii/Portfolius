from datetime import date
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
    latest_price_date: date | None

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
    position_count: int
    unit_quantity: Decimal | None = None

    @field_serializer("market_value", "percent", "unit_quantity")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
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
    unit_quantity: Decimal
    percent_of_parent: Decimal
    percent_of_portfolio: Decimal

    @field_serializer(
        "market_value",
        "percent_of_parent",
        "percent_of_portfolio",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)

    @field_serializer("unit_quantity")
    def serialize_unit_quantity(self, value: Decimal) -> str:
        return format(value.normalize(), "f")


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


class ProjectionYearPoint(BaseModel):
    year: int
    conservative: Decimal
    expected: Decimal
    optimistic: Decimal

    @field_serializer("conservative", "expected", "optimistic")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)


class ProjectionResponse(BaseModel):
    base_currency: str
    start_value: Decimal
    target_amount: Decimal | None
    horizon_years: int
    contribution_amount: Decimal
    contribution_frequency: str
    annual_return_expected: Decimal
    series: list[ProjectionYearPoint]
    target_progress_percent: Decimal | None
    on_track: bool | None
    target_reached_year: int | None

    @field_serializer(
        "start_value",
        "target_amount",
        "contribution_amount",
        "annual_return_expected",
        "target_progress_percent",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(value)
