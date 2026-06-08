from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AppHealthCheck(Base):
    __tablename__ = "app_health_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_profiles_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    time_horizon: Mapped[str] = mapped_column(String(120), nullable=False)
    investment_frequency: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_tolerance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    interest_tags: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    excluded_sectors: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    goals_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "role in ('user', 'assistant')",
            name="ck_messages_role_valid",
        ),
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_instruments_symbol_exchange"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exchange: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )
    prices: Mapped[list["Price"]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        Index("ix_holdings_user_id", "user_id"),
        Index("ix_holdings_instrument_id", "instrument_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    instrument: Mapped[Instrument] = relationship(back_populates="holdings")


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "price_date",
            "source",
            name="uq_prices_instrument_date_source",
        ),
        CheckConstraint(
            "close_price >= 0",
            name="ck_prices_close_price_non_negative",
        ),
        Index("ix_prices_instrument_date", "instrument_id", "price_date"),
        Index("ix_prices_price_date", "price_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id"),
        nullable=False,
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    instrument: Mapped[Instrument] = relationship(back_populates="prices")
