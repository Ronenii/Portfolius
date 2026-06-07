from pydantic import BaseModel


class InstrumentSearchResult(BaseModel):
    symbol: str
    name: str | None
    exchange: str | None
    currency: str | None
    asset_class: str | None
    sector: str | None
    country: str | None
    region: str | None
    source: str
