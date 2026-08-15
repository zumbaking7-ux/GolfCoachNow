"""A paying subscriber must not be treated as a free user.

This is the gap between selling a subscription and honouring one, and it does
not look like a bug from either side. unlock-status correctly reported the
subscriber as unlocked; the module endpoints separately capped them at three
reps a day and told them to subscribe. Both halves were behaving exactly as
written, and the customer was paying 14.99 a month to be shown an advert for
the thing they had bought.

Found by running a real subscription through a local server rather than by
reading code, because nothing in either half looks wrong on its own.
"""

import secrets
from datetime import datetime, timedelta, timezone

import pytest

from payments.entitlement import check_entitlement, has_paid_access, record_usage
from payments.models import FREE_REPS_PER_DAY, Unlock
from payments.subscription_models import UserSubscription

DEVICE = "subscriber_device"


def subscribe(db_session, device_id=DEVICE, days_left=30, status="active"):
    db_session.add(
        UserSubscription(
            device_id=device_id,
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_" + secrets.token_hex(4),
            status=status,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=days_left),
        )
    )
    db_session.commit()


def buy_outright(db_session, device_id=DEVICE):
    db_session.add(
        Unlock(
            device_id=device_id,
            checkout_session_id="cs_" + secrets.token_hex(4),
            amount_total=1499,
            currency="usd",
            status="complete",
            source="webhook",
        )
    )
    db_session.commit()


def use_reps(db_session, count: int, device_id=DEVICE, module="swing"):
    last = None
    for _ in range(count):
        last = record_usage(db_session, device_id, module)
    return last


# --- the bug ----------------------------------------------------------------


def test_a_subscriber_is_not_capped_at_the_free_limit(db_session):
    """The failure: three reps a day for somebody paying monthly."""
    subscribe(db_session)

    status = use_reps(db_session, FREE_REPS_PER_DAY + 2)

    assert status.allowed is True
    assert status.daily_limit == -1
    assert status.is_subscriber is True


def test_a_subscriber_reads_as_paid_before_using_anything(db_session):
    subscribe(db_session)

    status = check_entitlement(db_session, DEVICE, "swing")

    assert status.is_subscriber is True
    assert status.reps_remaining == -1


# --- the boundaries ---------------------------------------------------------


def test_a_lapsed_subscriber_goes_back_to_the_free_limit(db_session):
    """Access has to actually end, here as well as in unlock-status."""
    subscribe(db_session, days_left=-1)

    status = check_entitlement(db_session, DEVICE, "swing")

    assert status.is_subscriber is False
    assert status.daily_limit == FREE_REPS_PER_DAY


def test_a_cancelled_subscriber_is_capped_again(db_session):
    subscribe(db_session, status="canceled")

    assert has_paid_access(db_session, DEVICE) is False


def test_a_card_being_retried_keeps_full_access(db_session):
    """past_due means Stripe is still trying, not that they left."""
    subscribe(db_session, status="past_due")

    assert has_paid_access(db_session, DEVICE) is True


def test_a_one_time_buyer_is_unaffected(db_session):
    """The path that already worked must keep working."""
    buy_outright(db_session)

    status = use_reps(db_session, FREE_REPS_PER_DAY + 2)

    assert status.allowed is True
    assert status.daily_limit == -1


def test_somebody_who_has_paid_nothing_is_still_capped(db_session):
    """The free tier is the business model. It must not be given away."""
    status = use_reps(db_session, FREE_REPS_PER_DAY, device_id="free_device")
    assert status.allowed is True

    over = record_usage(db_session, "free_device", "swing")

    assert over.allowed is False
    assert over.daily_limit == FREE_REPS_PER_DAY


def test_another_devices_subscription_does_not_pay_for_you(db_session):
    subscribe(db_session, device_id="somebody_else")

    assert has_paid_access(db_session, "free_device") is False
