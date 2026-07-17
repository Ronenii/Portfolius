from pydantic import BaseModel


class MetadataRefreshResult(BaseModel):
    requested: int
    updated: int
    skipped: int
    failed: int


class HistoricalReturnRefreshResult(BaseModel):
    requested: int
    updated: int
    skipped: int
    failed: int
