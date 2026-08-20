"""Entitlement checks. Decides whether a device can use a module.

Paid users get unlimited access, whether they bought the one-time unlock or
subscribe monthly. Everyone else gets FREE_REPS_PER_DAY per module per day
(UTC), and the daily reset happens naturally because only today's rows count.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from payments.accounts import unlock_for
from payments.accounts_models import User
from payments.models import DailyUsage, FREE_REPS_PER_DAY, today_utc
from payments.subscription_service import active_subscription


def has_paid_access(
    session: Session, device_id: str, user: User | None = None
) -> bool:
    """Whether this golfer may use the paid features without a daily cap.

    Both kinds of purchase count, and missing the second one is expensive in a
    quiet way: unlock-status would tell a subscriber they are unlocked, and
    then the module endpoints would cut them off after three reps a day with a
    message inviting them to subscribe. They are already paying.

    The person and the device are a union, never one instead of the other. A
    subscription bought on a phone that was later lost still belongs to the
    account, and an unlock bought on this handset still counts even if it was
    never linked to anybody. Answering with only one of the two produces the
    worst shape of bug there is: a credential that leaves someone worse off
    than no credential at all.
    """
    if unlock_for(session, user, device_id) is not None:
        return True
    return active_subscription(session, user=user, device_id=device_id) is not None


@dataclass(frozen=True)
class EntitlementStatus:
    allowed: bool
    is_subscriber: bool
    reps_used: int
    reps_remaining: int
    daily_limit: int


def check_entitlement(
    session: Session, device_id: str, module: str, user: User | None = None
) -> EntitlementStatus:
    active = has_paid_access(session, device_id, user)
    if active:
        return EntitlementStatus(
            allowed=True,
            is_subscriber=True,
            reps_used=0,
            reps_remaining=-1,
            daily_limit=-1,
        )

    usage = _get_or_create_usage(session, device_id, module, user)
    remaining = max(0, FREE_REPS_PER_DAY - usage.rep_count)

    return EntitlementStatus(
        allowed=remaining > 0,
        is_subscriber=False,
        reps_used=usage.rep_count,
        reps_remaining=remaining,
        daily_limit=FREE_REPS_PER_DAY,
    )


def record_usage(
    session: Session, device_id: str, module: str, user: User | None = None
) -> EntitlementStatus:
    active = has_paid_access(session, device_id, user)
    if active:
        return EntitlementStatus(
            allowed=True,
            is_subscriber=True,
            reps_used=0,
            reps_remaining=-1,
            daily_limit=-1,
        )

    usage = _get_or_create_usage(session, device_id, module, user)
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


def _by_user(session: Session, user_id: int, module: str) -> DailyUsage | None:
    return session.scalars(
        select(DailyUsage).where(
            DailyUsage.user_id == user_id,
            DailyUsage.module == module,
            DailyUsage.usage_date == today_utc(),
        )
    ).first()


def _by_device(session: Session, device_id: str, module: str) -> DailyUsage | None:
    return session.scalars(
        select(DailyUsage).where(
            DailyUsage.device_id == device_id,
            DailyUsage.module == module,
            DailyUsage.usage_date == today_utc(),
        )
    ).first()


def _get_or_create_usage(
    session: Session, device_id: str, module: str, user: User | None = None
) -> DailyUsage:
    """The row for whoever is taking this rep, today.

    Keyed to the account when there is one, so the daily cap follows the golfer
    rather than the handset. Previously a new phone meant a fresh set of free
    reps, and the cap leaked accordingly.

    Falls back to the device when there is no account. That is a real state and
    not a gap: the launch allowance lets a stranger take a rep before signing
    in at all.
    """
    today = today_utc()

    if user is not None:
        usage = _by_user(session, user.id, module)
        if usage:
            return usage

        # Nothing under the account yet. If this device has an unclaimed row
        # for today, it belongs to them: those are the reps they took a moment
        # ago, before signing in. Claiming it means the free rep they just
        # used still counts, rather than being quietly handed to them twice.
        orphan = session.scalars(
            select(DailyUsage).where(
                DailyUsage.device_id == device_id,
                DailyUsage.user_id.is_(None),
                DailyUsage.module == module,
                DailyUsage.usage_date == today,
            )
        ).first()
        if orphan:
            orphan.user_id = user.id
            session.commit()
            return orphan

    else:
        usage = _by_device(session, device_id, module)
        if usage:
            return usage

    usage = DailyUsage(
        device_id=device_id,
        user_id=user.id if user is not None else None,
        module=module,
        usage_date=today,
        rep_count=0,
    )
    session.add(usage)
    try:
        session.commit()
    except IntegrityError:
        # Either another request created the row first, or this handset already
        # has one belonging to somebody else - a shared phone. Look it up the
        # way it will be read back, so the answer is the row this golfer owns.
        session.rollback()
        if user is not None:
            usage = _by_user(session, user.id, module) or _by_device(
                session, device_id, module
            )
        else:
            usage = _by_device(session, device_id, module)

    return usage
