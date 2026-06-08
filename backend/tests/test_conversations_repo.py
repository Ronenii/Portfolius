from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser
from app.data.models import Message
from app.data.repositories.conversations import (
    append_message,
    create_conversation,
    get_conversation_for_user,
    list_conversations_for_user,
    list_messages,
)


def test_create_conversation_and_append_messages_in_order(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> None:
    conversation = create_conversation(
        db_session,
        authenticated_user.user_id,
        "Regional exposure",
    )

    user_message = append_message(
        db_session,
        conversation,
        "user",
        "What if I buy VXUS?",
    )
    assistant_message = append_message(
        db_session,
        conversation,
        "assistant",
        "VXUS would increase international exposure.",
    )

    messages = list_messages(db_session, conversation)

    assert conversation.id is not None
    assert user_message.id is not None
    assert assistant_message.id is not None
    assert [(message.role, message.content) for message in messages] == [
        ("user", "What if I buy VXUS?"),
        ("assistant", "VXUS would increase international exposure."),
    ]


def test_get_conversation_for_user_rejects_other_users(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
) -> None:
    conversation = create_conversation(
        db_session,
        authenticated_user.user_id,
        "Private plan",
    )

    assert (
        get_conversation_for_user(
            db_session,
            second_user.user_id,
            conversation.id,
        )
        is None
    )
    assert (
        get_conversation_for_user(
            db_session,
            authenticated_user.user_id,
            conversation.id,
        )
        == conversation
    )


def test_list_conversations_for_user_returns_newest_first(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
) -> None:
    older = create_conversation(db_session, authenticated_user.user_id, "Older")
    newer = create_conversation(db_session, authenticated_user.user_id, "Newer")
    create_conversation(db_session, second_user.user_id, "Other user")
    append_message(db_session, older, "user", "Bring this conversation forward.")

    conversations = list_conversations_for_user(db_session, authenticated_user.user_id)

    assert [conversation.id for conversation in conversations] == [
        older.id,
        newer.id,
    ]


def test_deleting_conversation_cascades_to_messages(
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> None:
    conversation = create_conversation(
        db_session,
        authenticated_user.user_id,
        "Delete me",
    )
    append_message(db_session, conversation, "user", "Hello")
    append_message(db_session, conversation, "assistant", "Hi")

    db_session.delete(conversation)
    db_session.commit()

    assert list(db_session.scalars(select(Message))) == []
