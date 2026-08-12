"""Entitlement checks. Decides whether a device can use a module.

Paid users get unlimited access, whether they bought the one-time unlock or
subscribe monthly. Everyone else gets FREE_REPS_PER_DAY per module per day
(UTC), and the daily reset happens naturally because only today's rows count.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from payments.models import DailyUsage, FREE_REPS_PER_DAY, today_utc
from payments.service import find_unlock
from payments.subscription_service import active_subscription


def has_paid_access(session: Session, device_id: str) -> bool:
    """Whether this device may use the paid features without a daily cap.

    Both kinds of purchase count, and missing the second one is expensive in a
    quiet way: unlock-status would tell a subscriber they are unlocked, and
    then the module endpoints would cut them off after three reps a day with a
    message inviting them to subscribe. They are already paying.

    Checked by device rather than by account because that is what these
    endpoints are given. A subscriber who signs in on a second phone links it,
    and from that point the device is found through the account anyway.
    """
    if find_unlock(session, device_id) is not None:
        return True
    return active_subscription(session, device_id=device_id) is not None


@dataclass(frozen=True)
class EntitlementStatus:
    allowed: bool
    is_subscriber: bool
    reps_used: int
    reps_remaining: int
    daily_limit: int


def check_entitlement(session: Session, device_id: str, module: str) -> EntitlementStatus:
    active = has_paid_access(session, device_id)
    if active:
        return EntitlementStatus(
            allowed=True,
            is_subscriber=True,
            reps_used=0,
            reps_remaining=-1,
            daily_limit=-1,
        )

    usage = _get_or_create_usage(session, device_id, module)
    remaining = max(0, FREE_REPS_PER_DAY - usage.rep_count)

    return EntitlementStatus(
        allowed=remaining > 0,
        is_subscriber=False,
        reps_used=usage.rep_count,
        reps_remaining=remaining,
        daily_limit=FREE_REPS_PER_DAY,
    )


def record_usage(session: Session, device_id: str, module: str) -> EntitlementStatus:
    active = has_paid_access(session, device_id)
    if active:
        return EntitlementStatus(
            allowed=True,
            is_subscriber=True,
            reps_used=0,
            reps_remaining=-1,
            daily_limit=-1,
        )

    usage = _get_or_create_usage(session, device_id, module)
    if usage.rep_count >= FREE_REPS_PER_DAY:
        return EntitlementStatus(
            allowed=False,
            is_subscriber=False,
            reps_used=usage.rep_count,
            reps_remaining=0,
            daily_limit=FREE_REPS_PER_DAY,
        )

    usage.rep_count += 1
    session.commit()

    remaining = max(0, FREE_REPS_PER_DAY - usage.rep_count)
    return EntitlementStatus(
        allowed=True,
        is_subscriber=False,
        reps_used=usage.rep_count,
        reps_remaining=remaining,
        daily_limit=FREE_REPS_PER_DAY,
    )


def _get_or_create_usage(session: Session, device_id: str, module: str) -> DailyUsage:
    today = today_utc()
    usage = session.scalars(
        select(DailyUsage).where(
            DailyUsage.device_id == device_id,
            DailyUsage.module == module,
            DailyUsage.usage_date == today,
        )
    ).first()

    if usage:
        return usage

    usage = DailyUsage(device_id=device_id, module=module, usage_date=today, rep_count=0)
    session.add(usage)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        usage = session.scalars(
            select(DailyUsage).where(
                DailyUsage.device_id == device_id,
                DailyUsage.module == module,
                DailyUsage.usage_date == today,
            )
        ).first()

    return usage
