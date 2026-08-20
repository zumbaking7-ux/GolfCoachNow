"""Usage keyed to the person rather than the handset.

Everything on the usage path used to key on device_id, a value the client
supplies. Three quiet consequences, and this file pins the fixes:

  - free reps reset on a new phone, so the daily cap leaked
  - a golfer's history did not follow them off the device
  - a purchase made on one handset did not travel with the account

The fallback to device_id stays, and has to: the launch allowance lets a
stranger take a rep before signing in at all, so a row with no user is a real
state. That fallback is the part most likely to hide a bug, because it is the
path that runs when everything else is absent, so it is tested here explicitly
rather than assumed.
"""

import pytest

from payments.accounts import request_login_code, verify_login_code
from payments.accounts_models import User
from payments.db import SessionFactory
from payments.entitlement import check_entitlement, has_paid_access, record_usage
from payments.models import DailyUsage, FREE_REPS_PER_DAY, Unlock, today_utc


def sign_in(email, device):
    with SessionFactory() as session:
        code = request_login_code(session, email)
        verify_login_code(session, email, code, device, "Tester")


def user_for(email):
    with SessionFactory() as session:
        return session.query(User).filter(User.email == email).one()


def reps(device, module="swing", user=None):
    with SessionFactory() as session:
        return check_entitlement(session, device, module, user).reps_used


def take_rep(device, module="swing", user=None):
    with SessionFactory() as session:
        return record_usage(session, device, module, user)


# --- The leak that is being closed ---------------------------------------


def test_free_reps_follow_the_golfer_to_a_new_phone():
    """The whole point. Before this, a second handset meant a fresh set of
    free reps, and the daily cap was worth nothing to anyone willing to
    reinstall."""
    sign_in("two-phones@example.com", "phone_a")
    sign_in("two-phones@example.com", "phone_b")
    person = user_for("two-phones@example.com")

    for _ in range(FREE_REPS_PER_DAY):
        take_rep("phone_a", user=person)

    on_the_new_phone = check_entitlement_for(person, "phone_b")
    assert on_the_new_phone.reps_used == FREE_REPS_PER_DAY
    assert not on_the_new_phone.allowed


def check_entitlement_for(person, device, module="swing"):
    with SessionFactory() as session:
        return check_entitlement(session, device, module, person)


def test_a_purchase_made_on_one_phone_travels_with_the_account():
    sign_in("bought@example.com", "old_phone")
    sign_in("bought@example.com", "new_phone")
    person = user_for("bought@example.com")

    with SessionFactory() as session:
        session.add(Unlock(
            device_id="old_phone",
            checkout_session_id="cs_test_travels",
            amount_total=1499,
            currency="usd",
            status="paid",
            source="test",
        ))
        session.commit()

    with SessionFactory() as session:
        assert has_paid_access(session, "new_phone", person) is True


# --- The seam with the launch allowance ----------------------------------


def test_signing_in_claims_the_rep_taken_moments_before():
    """A stranger takes their one free rep, then signs in. That rep was
    theirs, so it has to count - otherwise signing in quietly hands them a
    second helping of the daily allowance."""
    take_rep("claiming_device")
    assert reps("claiming_device") == 1

    sign_in("claimer@example.com", "claiming_device")
    person = user_for("claimer@example.com")

    assert check_entitlement_for(person, "claiming_device").reps_used == 1


def test_claiming_does_not_invent_a_second_row():
    take_rep("one_row_device")
    sign_in("onerow@example.com", "one_row_device")
    person = user_for("onerow@example.com")
    take_rep("one_row_device", user=person)

    with SessionFactory() as session:
        rows = session.query(DailyUsage).filter(
            DailyUsage.device_id == "one_row_device",
            DailyUsage.usage_date == today_utc(),
        ).all()

    assert len(rows) == 1
    assert rows[0].rep_count == 2
    assert rows[0].user_id == person.id


# --- The fallback, which is the path most likely to hide something --------


def test_a_stranger_is_still_counted_by_device():
    """No account, no token, no problem. This is the pre-migration path and
    it still has to work exactly as it did."""
    take_rep("anonymous_device")
    take_rep("anonymous_device")
    assert reps("anonymous_device") == 2


def test_rows_written_before_this_change_are_still_read():
    """Every row in production predates the user_id column and has NULL in
    it. Those reps must still count, or the cap silently resets for everybody
    on the day this deploys."""
    with SessionFactory() as session:
        session.add(DailyUsage(
            device_id="legacy_device",
            user_id=None,
            module="swing",
            usage_date=today_utc(),
            rep_count=FREE_REPS_PER_DAY,
        ))
        session.commit()

    status = check_entitlement_for(None, "legacy_device")
    assert status.reps_used == FREE_REPS_PER_DAY
    assert not status.allowed


def test_a_legacy_row_is_claimed_rather_than_ignored():
    """Somebody who used their reps anonymously this morning and signs in
    this afternoon does not get them back."""
    with SessionFactory() as session:
        session.add(DailyUsage(
            device_id="legacy_claim_device",
            user_id=None,
            module="swing",
            usage_date=today_utc(),
            rep_count=FREE_REPS_PER_DAY,
        ))
        session.commit()

    sign_in("legacy@example.com", "legacy_claim_device")
    person = user_for("legacy@example.com")

    assert not check_entitlement_for(person, "legacy_claim_device").allowed


# --- Two people, one handset ---------------------------------------------


def test_a_shared_phone_does_not_share_a_daily_cap():
    """Two accounts on one device are two golfers, not one. Keying the cap to
    the person is the whole change; this is what it buys."""
    sign_in("first@example.com", "shared_phone")
    sign_in("second@example.com", "shared_phone")
    first, second = user_for("first@example.com"), user_for("second@example.com")

    for _ in range(FREE_REPS_PER_DAY):
        take_rep("shared_phone", user=first)

    assert not check_entitlement_for(first, "shared_phone").allowed
    assert check_entitlement_for(second, "shared_phone").allowed


# --- Modules stay separate ------------------------------------------------


def test_the_cap_is_still_per_module():
    sign_in("modules@example.com", "module_device")
    person = user_for("modules@example.com")

    for _ in range(FREE_REPS_PER_DAY):
        take_rep("module_device", module="swing", user=person)

    assert not check_entitlement_for(person, "module_device", "swing").allowed
    assert check_entitlement_for(person, "module_device", "putt").allowed
