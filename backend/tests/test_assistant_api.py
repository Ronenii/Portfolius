import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.assistant import (
    get_llm_client,
    list_assistant_conversations,
    post_assistant_message,
    read_assistant_conversation,
    router,
)
from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings
from app.data.models import Profile
from app.data.repositories.conversations import (
    append_message,
    create_conversation,
    list_messages,
)
from app.integrations.llm import ChatCompletion, ChatMessage, ToolSpec
from app.integrations.market_data import MarketPrice
from app.main import app
from app.schemas.assistant import AssistantMessageRequest


class FakeLlmClient:
    def __init__(self, reply: str = "Fake assistant reply.") -> None:
        self.reply = reply
        self.calls: list[tuple[list[ChatMessage], list[ToolSpec] | None]] = []

    def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> ChatCompletion:
        self.calls.append((messages, tools))
        return ChatCompletion(
            message=ChatMessage(role="assistant", content=self.reply),
            tool_calls=[],
        )


class FakeMarketDataClient:
    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        return None


def add_profile(db_session: Session, user_id: str = "user-123") -> Profile:
    profile = Profile(
        user_id=user_id,
        display_name="Ronen",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="monthly",
    )
    db_session.add(profile)
    db_session.commit()
    return profile


def assistant_routes() -> list[object]:
    paths = {
        "/api/v1/assistant/messages",
        "/api/v1/assistant/conversations",
        "/api/v1/assistant/conversations/{conversation_id}",
    }
    return [route for route in app.routes if getattr(route, "path", None) in paths]


def test_assistant_routes_are_registered_and_require_auth() -> None:
    routes = assistant_routes()
    paths = {getattr(route, "path", None) for route in routes}

    assert {
        "/api/v1/assistant/messages",
        "/api/v1/assistant/conversations",
        "/api/v1/assistant/conversations/{conversation_id}",
    }.issubset(paths)
    for route in router.routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_post_message_without_conversation_creates_conversation(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    llm_client = FakeLlmClient("A balanced portfolio depends on your goals.")

    response = post_assistant_message(
        AssistantMessageRequest(message="How balanced am I across sectors?"),
        authenticated_user,
        db_session,
        llm_client,
        FakeMarketDataClient(),
    )

    assert response.conversation_id > 0
    assert response.title == "How balanced am I across sectors?"
    assert response.reply == "A balanced portfolio depends on your goals."
    assert response.used_tools == []
    assert len(llm_client.calls) == 1


def test_post_message_with_existing_conversation_appends_to_it(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    conversation = create_conversation(
        db_session,
        authenticated_user.user_id,
        "Existing thread",
    )
    append_message(db_session, conversation, "user", "Earlier question")
    append_message(db_session, conversation, "assistant", "Earlier answer")

    response = post_assistant_message(
        AssistantMessageRequest(
            conversation_id=conversation.id,
            message="Follow up",
        ),
        authenticated_user,
        db_session,
        FakeLlmClient("New answer"),
        FakeMarketDataClient(),
    )

    assert response.conversation_id == conversation.id
    assert response.title == "Existing thread"
    saved_messages = [
        (message.role, message.content)
        for message in list_messages(db_session, conversation)
    ]
    assert saved_messages == [
        ("user", "Earlier question"),
        ("assistant", "Earlier answer"),
        ("user", "Follow up"),
        ("assistant", "New answer"),
    ]


def test_user_cannot_read_another_users_conversation(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    conversation = create_conversation(
        db_session,
        second_user.user_id,
        "Other user's thread",
    )

    with pytest.raises(HTTPException) as exc_info:
        read_assistant_conversation(
            conversation.id,
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 404


def test_post_message_without_llm_configuration_returns_503() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_llm_client(Settings(llm_api_key=None))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Assistant is not configured"


def test_list_and_read_conversations_are_user_scoped(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first = create_conversation(db_session, authenticated_user.user_id, "First")
    append_message(db_session, first, "user", "Hello")
    create_conversation(db_session, second_user.user_id, "Other")

    listed = list_assistant_conversations(authenticated_user, db_session)
    detail = read_assistant_conversation(first.id, authenticated_user, db_session)

    assert [item.title for item in listed] == ["First"]
    assert detail.id == first.id
    assert detail.messages[0].content == "Hello"
