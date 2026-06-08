from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Conversation, Message


def create_conversation(db: Session, user_id: str, title: str) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation_for_user(
    db: Session,
    user_id: str,
    conversation_id: int,
) -> Conversation | None:
    return db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )


def list_conversations_for_user(db: Session, user_id: str) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
    )


def append_message(
    db: Session,
    conversation: Conversation,
    role: str,
    content: str,
) -> Message:
    message = Message(conversation=conversation, role=role, content=content)
    conversation.updated_at = datetime.now(UTC)
    db.add(message)
    db.commit()
    db.refresh(message)
    db.refresh(conversation)
    return message


def list_messages(db: Session, conversation: Conversation) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at, Message.id)
        )
    )
