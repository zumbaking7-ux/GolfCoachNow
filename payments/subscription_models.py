"""The subscription record.

Named user_subscriptions rather than subscriptions, and the reason changed.

It started as a way around a collision: models.py declared a Subscription class
on this same Base, and two classes cannot map one table name without SQLAlchemy
raising at import. That class has since been deleted, so the collision is gone.

The name stays anyway, for a better reason. A subscriptions table already
exists in the production database. It was created directly on the server rather
than by a migration, which is the subject of issue #5, so nothing in this
repository would tell you it is there. A migration creating a table of that
name would run fine on every fresh database and fail on the only one that
matters.

Taking the name would mean dropping a live table first, and a destructive
migration to save eleven characters is a bad trade.

Why a table of its own rather than reusing that one: it is keyed on device_id
with no user at all. Accounts exist now, and a subscription that belongs to a
handset dies with the handset while the charges continue, which is a refund.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from payments.models import Base, utcnow

ID_LENGTH = 255
STATUS_LENGTH = 32


class UserSubscription(Base):
    """One row per Stripe subscription, past or present.

    Rows are kept rather than replaced. Someone who cancels and comes back
    later has two subscriptions and both are real history, so "does this person
    have access" is a question asked across their rows rather than answered by
    a single current one. Overwriting would also make a late webhook for an old
    subscription silently rewrite the new one.
    """

    __tablename__ = "user_subscriptions"
    __table_args__ = (
        # Stripe's ID is the natural key. The unique index is what makes a
        # repeated webhook a no-op rather than a second row, in the same way
        # processed_events.stripe_event_id does for events.
        UniqueConstraint(
            "stripe_subscription_id", name="uq_user_subscriptions_stripe_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Both nullable, and at least one is always set in practice.
    #
    # user_id is absent when somebody subscribes without signing in first. The
    # app is told to ask for sign in before the subscribe screen, but the
    # endpoint cannot depend on the app doing that, and refusing the payment
    # would be the wrong way to enforce it.
    #
    # device_id is absent for a subscription started somewhere other than a
    # phone, which the billing portal makes possible.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    device_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), nullable=True, index=True
    )

    stripe_customer_id: Mapped[str] = mapped_column(String(ID_LENGTH), nullable=False)
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), nullable=False
    )

    status: Mapped[str] = mapped_column(String(STATUS_LENGTH), nullable=False)

    # When the paid period runs out. Null only before the first invoice is
    # known. Access is granted until this moment, not for as long as the status
    # says active, because a status can go stale if a webhook is missed and a
    # date cannot.
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # They have cancelled but already paid for the period they are in. Access
    # continues to current_period_end. Cutting it off at the click would be
    # taking back time they were charged for.
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
