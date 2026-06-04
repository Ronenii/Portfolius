from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ProfileRequest(BaseModel):
    display_name: str
    base_currency: str
    time_horizon: str
    investment_frequency: str

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


class ProfileResponse(BaseModel):
    id: int
    user_id: str
    display_name: str
    base_currency: str
    time_horizon: str
    investment_frequency: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
