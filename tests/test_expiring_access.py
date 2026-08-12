"""What unlock-status says once access can expire.

The interesting cases are the ones where the two kinds of access meet: someone
who owns the app outright and also has a subscription, and someone whose
subscription has quietly run out.
"""

import secrets
from datetime import datetime, timedelta, timezone

import pytest
from conftest import DEVICE_ID, build_payments_app, load_event, post_webhook

from fastapi.testclient import TestClient

from payments.accounts import _hash_token
from payments.accounts_models import AuthToken, User, UserDevice
from payments.subscription_models import UserSubscription


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


def subscribe(db_session, device_id=None, user_id=None, days_left=30, **kwargs):
    row = UserSubscription(
        user_id=user_id,
        device_id=device_id,
        stripe_customer_id="cus_x",
        stripe_subscription_id=kwargs.pop("stripe_id", "sub_" + secrets.token_hex(4)),
        status=kwargs.pop("status", "active"),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=days_left),
        cancel_at_period_end=kwargs.pop("cancel_at_period_end", False),
    )
    db_session.add(row)
    db_session.commit()
    return row


def sign_in(db_session, email="expiry@example.com") -> tuple[str, int]:
    user = User(email=email)
    db_session.add(user)
    db_session.commit()
    token = secrets.token_urlsafe(32)
    db_session.add(AuthToken(user_id=user.id, token_hash=_hash_token(token)))
    db_session.commit()
    return token, user.id


def status(client, device_id=None, token=None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params = {"device_id": device_id} if device_id else {}
    return client.get("/payments/unlock-status", params=params, headers=headers).json()


# --- the plans --------------------------------------------------------------


def test_no_access_reports_none(client):
    body = status(client, device_id="nobody")

    assert body["unlocked"] is False
    assert body["plan"] == "none"
    assert body["expires_at"] is None


def test_a_one_time_purchase_is_lifetime_and_never_expires(client):
    post_webhook(client, load_event())

    body = status(client, device_id=DEVICE_ID)

    assert body["unlocked"] is True
    assert body["plan"] == "lifetime"
    assert body["expires_at"] is None, "a purchase that cannot expire must not carry a date"


def test_an_active_subscription_is_monthly_with_an_expiry(client, db_session):
    subscribe(db_session, device_id="d1")

    body = status(client, device_id="d1")

    assert body["unlocked"] is True
    assert body["plan"] == "monthly"
    assert body["expires_at"] is not None


def test_a_lapsed_subscription_is_locked(client, db_session):
    """The whole point of the milestone. Access has to actually stop."""
    subscribe(db_session, device_id="d1", days_left=-1)

    body = status(client, device_id="d1")

    assert body["unlocked"] is False
    assert body["plan"] == "none"


def test_a_cancelled_subscription_keeps_access_until_the_period_ends(client, db_session):
    subscribe(db_session, device_id="d1", cancel_at_period_end=True)

    body = status(client, device_id="d1")

    assert body["unlocked"] is True
    assert body["cancel_at_period_end"] is True, (
        "the billing screen has no way to warn them without this"
    )


def test_a_card_being_retried_does_not_lock_anyone_out(client, db_session):
    subscribe(db_session, device_id="d1", status="past_due")

    assert status(client, device_id="d1")["unlocked"] is True


# --- grandfathering ---------------------------------------------------------


def test_an_early_buyer_who_also_subscribed_stays_lifetime(client, db_session):
    """The one-time purchase wins, and the order is deliberate.

    Somebody who bought the app outright and later subscribed by mistake still
    owns it. Reporting them as monthly would put an expiry on something that
    does not expire, and show a cancel button that takes away nothing.
    """
    post_webhook(client, load_event())
    subscribe(db_session, device_id=DEVICE_ID)

    body = status(client, device_id=DEVICE_ID)

    assert body["plan"] == "lifetime"
    assert body["expires_at"] is None


def test_a_lifetime_buyer_is_never_locked_out_by_an_expired_subscription(
    client, db_session
):
    """The failure this guards against would take the app away from somebody
    who paid for it permanently."""
    post_webhook(client, load_event())
    subscribe(db_session, device_id=DEVICE_ID, days_left=-30, status="canceled")

    body = status(client, device_id=DEVICE_ID)

    assert body["unlocked"] is True
    assert body["plan"] == "lifetime"


# --- by account rather than device ------------------------------------------


def test_a_subscription_follows_the_person_to_a_new_phone(client, db_session):
    """Restore purchase, for subscriptions."""
    token, user_id = sign_in(db_session)
    subscribe(db_session, user_id=user_id)

    body = status(client, device_id="a_brand_new_phone", token=token)

    assert body["unlocked"] is True
    assert body["plan"] == "monthly"


def test_a_subscription_on_an_old_linked_device_is_found(client, db_session):
    token, user_id = sign_in(db_session)
    db_session.add(UserDevice(user_id=user_id, device_id="old_phone"))
    db_session.commit()
    subscribe(db_session, device_id="old_phone")

    assert status(client, device_id="new_phone", token=token)["unlocked"] is True


def test_someone_elses_subscription_is_not_yours(client, db_session):
    subscribe(db_session, device_id="not_your_device")

    assert status(client, device_id="your_device")["unlocked"] is False
