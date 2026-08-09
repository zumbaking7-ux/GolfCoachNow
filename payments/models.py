"""Database tables for payments.

Two tables, each with a unique constraint doing real work:

processed_events.stripe_event_id
    Stripe retries a webhook until it gets a 2xx, so the same event arrives
    more than once. The unique index is what makes a repeat delivery a no-op.

unlocks.device_id
    Two different code paths can unlock a device: the success redirect and the
    webhook. They race. The unique index is what makes them converge on one row
    instead of two.

Neither guarantee is enforced in Python. Both are enforced by the database, so
they hold even when two requests are in flight at the same moment.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Column widths. Stripe IDs are well under 255; the email limit is the RFC one.
ID_LENGTH = 255
CURRENCY_LENGTH = 8
SOURCE_LENGTH = 32
EMAIL_LENGTH = 320


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProcessedEvent(Base):
    """One row per Stripe webhook event this service has claimed.

    processed_at stays NULL between claiming an event and finishing it. A row
    with a NULL processed_at is an attempt that died partway through, and a
    later retry is allowed to pick it up again.
    """

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
    """One row per device that has paid. The row existing is the unlock.

    device_id is the value the app sent when the Checkout Session was created,
    which Stripe stores and hands back as client_reference_id.

    customer_email is kept for support. A device ID is not stable forever - iOS
    changes it when the user deletes the app - so the email is the only way to
    identify a paying customer who has lost their unlock.
    """

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
