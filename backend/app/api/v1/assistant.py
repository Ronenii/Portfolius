from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings, get_settings
from app.data.database import get_db
from app.data.models import Conversation
from app.data.repositories.conversations import (
    create_conversation,
    get_conversation_for_user,
    list_conversations_for_user,
    list_messages,
)
from app.domain.assistant import run_assistant_turn
from app.integrations.llm import GroqLlmClient, LlmClient, is_llm_configured
from app.schemas.assistant import (
    AssistantMessageRequest,
    AssistantMessageResponse,
    ConversationDetailResponse,
    ConversationSummaryResponse,
    MessageResponse,
)

router = APIRouter(tags=["assistant"])


def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LlmClient:
    if not is_llm_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant is not configured",
        )
    return GroqLlmClient.from_settings(settings)


def assistant_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Conversation not found",
    )


def derive_title(message: str) -> str:
    title = " ".join(message.split())
    if len(title) <= 80:
        return title
    return f"{title[:77].rstrip()}..."


def conversation_detail(conversation: Conversation) -> ConversationDetailResponse:
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageResponse.model_validate(message)
            for message in conversation.messages
        ],
    )


@router.post(
    "/api/v1/assistant/messages",
    response_model=AssistantMessageResponse,
)
def post_assistant_message(
    payload: AssistantMessageRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    llm_client: Annotated[LlmClient, Depends(get_llm_client)],
) -> AssistantMessageResponse:
    if payload.conversation_id is None:
        conversation = create_conversation(
            db,
            current_user.user_id,
            derive_title(payload.message),
        )
    else:
        conversation = get_conversation_for_user(
            db,
            current_user.user_id,
            payload.conversation_id,
        )
        if conversation is None:
            raise assistant_not_found()

    result = run_assistant_turn(
        db,
        current_user.user_id,
        conversation,
        payload.message,
        llm_client,
    )
    return AssistantMessageResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        reply=result.reply,
        used_tools=result.used_tools,
    )


@router.get(
    "/api/v1/assistant/conversations",
    response_model=list[ConversationSummaryResponse],
)
def list_assistant_conversations(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ConversationSummaryResponse]:
    return [
        ConversationSummaryResponse.model_validate(conversation)
        for conversation in list_conversations_for_user(db, current_user.user_id)
    ]


@router.get(
    "/api/v1/assistant/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def read_assistant_conversation(
    conversation_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationDetailResponse:
    conversation = get_conversation_for_user(
        db,
        current_user.user_id,
        conversation_id,
    )
    if conversation is None:
        raise assistant_not_found()

    messages = list_messages(db, conversation)
    conversation.messages = messages
    return conversation_detail(conversation)
