from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

RISK_TOLERANCES = {"conservative", "balanced", "aggressive"}
INTEREST_TAGS = {
    "dividends",
    "growth",
    "value",
    "technology",
    "esg",
    "bonds",
    "real_estate",
    "emerging_markets",
    "broad_market",
    "income",
}
EXCLUDABLE_SECTORS = {
    "tobacco",
    "weapons",
    "fossil_fuels",
    "gambling",
    "crypto",
    "alcohol",
}


def normalize_vocab(values: list[str], allowed_values: set[str]) -> list[str]:
    normalized_values: list[str] = []
    seen_values: set[str] = set()
    for value in values:
        normalized_value = value.strip().lower()
        if normalized_value in allowed_values and normalized_value not in seen_values:
            normalized_values.append(normalized_value)
            seen_values.add(normalized_value)
    return normalized_values


class ProfileRequest(BaseModel):
    display_name: str
    base_currency: str
    time_horizon: str
    investment_frequency: str
    risk_tolerance: str | None = None
    interest_tags: list[str] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list)
    goals_note: str | None = Field(default=None, max_length=1000)

    @field_validator("display_name", "time_horizon", "investment_frequency")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        trimmed_value = value.strip()
        if not trimmed_value:
            raise ValueError("Value cannot be empty")
        return trimmed_value

    @field_validator("base_currency")
    @classmethod
    def validate_base_currency(cls, value: str) -> str:
        if len(value) != 3 or not value.isalpha() or value.upper() != value:
            raise ValueError("Currency must be a three-letter uppercase code")
        return value

    @field_validator("risk_tolerance")
    @classmethod
    def validate_risk_tolerance(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip().lower()
        if normalized_value not in RISK_TOLERANCES:
            raise ValueError("Risk tolerance is not supported")
        return normalized_value

    @field_validator("interest_tags")
    @classmethod
    def normalize_interest_tags(cls, value: list[str]) -> list[str]:
        return normalize_vocab(value, INTEREST_TAGS)

    @field_validator("excluded_sectors")
    @classmethod
    def normalize_excluded_sectors(cls, value: list[str]) -> list[str]:
        return normalize_vocab(value, EXCLUDABLE_SECTORS)

    @field_validator("goals_note")
    @classmethod
    def trim_goals_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed_value = value.strip()
        return trimmed_value or None


class ProfileResponse(BaseModel):
    id: int
    user_id: str
    display_name: str
    base_currency: str
    time_horizon: str
    investment_frequency: str
    risk_tolerance: str | None = None
    interest_tags: list[str] = Field(default_factory=list)
    excluded_sectors: list[str] = Field(default_factory=list)
    goals_note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
