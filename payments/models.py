"""Database tables for payments.

Three tables:

processed_events.stripe_event_id
    Stripe retries a webhook until it gets a 2xx, so the same event arrives
    more than once. The unique index is what makes a repeat delivery a no-op.

unlocks.device_id
    One-time purchases. The unique index is what keeps a repeated delivery
    from unlocking twice.

The subscriptions table that used to be declared here was scaffolding from a
reverted attempt, never migrated and never called. It was removed so the real
subscription tables could take the name. See subscription_models.py.
"""

from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from datetime import date as date_type

ID_LENGTH = 255
CURRENCY_LENGTH = 8
SOURCE_LENGTH = 32
EMAIL_LENGTH = 320
STATUS_LENGTH = 32


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = (
        UniqueConstraint("stripe_event_id", name="uq_processed_events_stripe_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stripe_event_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    event_type: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Unlock(Base):
    __tablename__ = "unlocks"
    __table_args__ = (UniqueConstraint("device_id", name="uq_unlocks_device_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    checkout_session_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    payment_intent_id: Mapped[str | None] = mapped_column(String(ID_LENGTH), nullable=True)
    amount_total: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(CURRENCY_LENGTH), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(EMAIL_LENGTH), nullable=True)
    status: Mapped[str] = mapped_column(String(SOURCE_LENGTH), nullable=False)
    source: Mapped[str] = mapped_column(String(SOURCE_LENGTH), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


MODULE_LENGTH = 32
FREE_REPS_PER_DAY = 3


def today_utc() -> date_type:
    return datetime.now(timezone.utc).date()


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint("device_id", "module", "usage_date", name="uq_daily_usage_device_module_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    module: Mapped[str] = mapped_column(String(MODULE_LENGTH), nullable=False)
    usage_date: Mapped[date_type] = mapped_column(Date, default=today_utc, nullable=False)
    rep_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


EVENT_NAME_LENGTH = 64
PLATFORM_LENGTH = 16


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(EVENT_NAME_LENGTH), nullable=False, index=True)
    module: Mapped[str | None] = mapped_column(String(MODULE_LENGTH), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(PLATFORM_LENGTH), nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


FAULT_LENGTH = 64


class RepResult(Base):
    __tablename__ = "rep_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(MODULE_LENGTH), nullable=False, index=True)
    dominant_fault: Mapped[str] = mapped_column(String(FAULT_LENGTH), nullable=False)
    correction: Mapped[str] = mapped_column(Text, nullable=False)
    scores_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
