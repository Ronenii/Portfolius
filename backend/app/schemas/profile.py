from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

RISK_TOLERANCES = {"conservative", "balanced", "aggressive"}
MAX_KEYWORDS = 30
MAX_KEYWORD_LENGTH = 40


def normalize_keywords(values: list[str]) -> list[str]:
    normalized_values: list[str] = []
    seen_values: set[str] = set()
    for value in values:
        normalized_value = value.strip().lower()
        if (
            normalized_value
            and len(normalized_value) <= MAX_KEYWORD_LENGTH
            and normalized_value not in seen_values
        ):
            normalized_values.append(normalized_value)
            seen_values.add(normalized_value)
        if len(normalized_values) >= MAX_KEYWORDS:
            break
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
    goal_target_amount: Decimal | None = None
    contribution_amount: Decimal | None = None

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
        return normalize_keywords(value)

    @field_validator("excluded_sectors")
    @classmethod
    def normalize_excluded_sectors(cls, value: list[str]) -> list[str]:
        return normalize_keywords(value)

    @field_validator("goals_note")
    @classmethod
    def trim_goals_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed_value = value.strip()
        return trimmed_value or None

    @field_validator("goal_target_amount", "contribution_amount")
    @classmethod
    def validate_non_negative(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if value < 0:
            raise ValueError("Value must be zero or greater")
        return value


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
    goal_target_amount: Decimal | None = None
    contribution_amount: Decimal | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("goal_target_amount", "contribution_amount")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(value)
