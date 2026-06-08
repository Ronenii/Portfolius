from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class AssistantMessageRequest(BaseModel):
    conversation_id: int | None = None
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        trimmed_value = value.strip()
        if not trimmed_value:
            raise ValueError("Message cannot be empty")
        return trimmed_value


class AssistantMessageResponse(BaseModel):
    conversation_id: int
    title: str
    reply: str
    used_tools: list[str]


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationSummaryResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]

    model_config = ConfigDict(from_attributes=True)
