"""Reading and writing subscription state.

Kept apart from subscriptions.py, which only parses Stripe payloads and never
touches a session. Splitting them means a parsing test cannot fail for a
database reason and vice versa.
"""

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from payments.accounts_models import User, UserDevice
from payments.logging_config import fields, get_logger
from payments.subscription_models import UserSubscription
from payments.subscriptions import ACTIVE_STATUSES

logger = get_logger("subscriptions")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes even for timezone-aware columns."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def has_access(subscription: UserSubscription) -> bool:
    """Whether this subscription entitles someone to the product right now.

    Two conditions, and both are needed for different reasons.

    The status has to be one Stripe considers current. That covers a card that
    failed and is being retried, which is not a reason to lock somebody out.

    The paid period also has to still be running. Status alone is not enough,
    because a status is only as fresh as the last webhook that arrived. Miss a
    cancellation and the row says active forever. A date cannot go stale that
    way: it either has not been reached yet or it has.
    """
    if subscription.status not in ACTIVE_STATUSES:
        return False

    period_end = _as_utc(subscription.current_period_end)
    if period_end is None:
        # No invoice has been seen yet, which happens between checkout and the
        # first invoice event. Trust the status for that short window rather
        # than deny access to somebody who has just paid.
        return True

    return period_end > _now()


def device_ids_for_user(session: Session, user: User) -> list[str]:
    return list(
        session.scalars(
            select(UserDevice.device_id).where(UserDevice.user_id == user.id)
        ).all()
    )


def find_subscriptions(
    session: Session, user: User | None = None, device_id: str | None = None
) -> list[UserSubscription]:
    """Every subscription belonging to this person or this device.

    Signed in, that means all of their devices as well as the account, which is
    what lets a subscription started on a lost phone be found from a new one.
    """
    conditions = []

    if user is not None:
        conditions.append(UserSubscription.user_id == user.id)
        linked = device_ids_for_user(session, user)
        if linked:
            conditions.append(UserSubscription.device_id.in_(linked))

    if device_id:
        conditions.append(UserSubscription.device_id == device_id)

    if not conditions:
        return []

    return list(
        session.scalars(
            select(UserSubscription)
            .where(or_(*conditions))
            .order_by(UserSubscription.id.desc())
        ).all()
    )


def active_subscription(
    session: Session, user: User | None = None, device_id: str | None = None
) -> UserSubscription | None:
    """The live subscription for this person or device, if there is one.

    Rows accumulate, so somebody who cancelled and came back has several and
    only one of them is current. Newest first, first with access wins.
    """
    for subscription in find_subscriptions(session, user=user, device_id=device_id):
        if has_access(subscription):
            return subscription
    return None
