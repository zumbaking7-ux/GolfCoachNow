"""Sending a valid token must never make someone worse off.

The rule this file protects is simple: any request that answers "unlocked"
without a token must still answer "unlocked" with one. A credential can grant
access it could not otherwise prove. It can never take away access the caller
already had.

That was broken. unlock-status answered by account alone once a token was
present, ignoring the device_id in the same request. A device that bought the
one-time unlock, whose owner then signed in without the app sending device_id,
read as unpaid - while the identical request without the token read as
unlocked.

It hit the one-time buyers specifically, the people who paid once for permanent
access, and it was invisible because both halves looked correct on their own.
Subscriptions were always answered as a union of account and device; unlocks
now are too.
"""

import secrets
from datetime import datetime, timedelta, timezone

import pytest
from conftest import build_payments_app

from fastapi.testclient import TestClient

from payments.accounts import _hash_token
from payments.accounts_models import AuthToken, User, UserDevice
from payments.models import Unlock
from payments.subscription_models import UserSubscription


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


def signed_in(db_session, email="holder@example.com") -> str:
    user = User(email=email)
    db_session.add(user)
    db_session.commit()
    token = secrets.token_urlsafe(32)
    db_session.add(AuthToken(user_id=user.id, token_hash=_hash_token(token)))
    db_session.commit()
    return token, user.id


def bought_outright(db_session, device_id):
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


def subscribed(db_session, device_id=None, user_id=None):
    db_session.add(
        UserSubscription(
            user_id=user_id,
            device_id=device_id,
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_" + secrets.token_hex(4),
            status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    db_session.commit()


def status(client, device_id, token=None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(
        "/payments/unlock-status", params={"device_id": device_id}, headers=headers
    ).json()


# --- the rule ---------------------------------------------------------------


def test_a_token_never_hides_a_one_time_purchase(client, db_session):
    """The bug, stated as the rule it broke."""
    bought_outright(db_session, "paid_device")
    token, _ = signed_in(db_session)

    without = status(client, "paid_device")
    with_token = status(client, "paid_device", token)

    assert without["unlocked"] is True
    assert with_token["unlocked"] is True, (
        "signing in made a paying customer read as unpaid"
    )
    assert with_token["plan"] == "lifetime"


def test_a_token_never_hides_a_subscription(client, db_session):
    """The same rule on the other path, which already held."""
    subscribed(db_session, device_id="sub_device")
    token, _ = signed_in(db_session)

    assert status(client, "sub_device")["unlocked"] is True
    assert status(client, "sub_device", token)["unlocked"] is True


@pytest.mark.parametrize("linked", [True, False])
def test_the_answer_does_not_depend_on_whether_the_device_was_linked(
    client, db_session, linked
):
    """Linking is an optimisation for finding old purchases, not a gate.

    Whether the app remembered to send device_id at sign in must not decide
    whether somebody keeps the app they bought.
    """
    token, user_id = signed_in(db_session)
    bought_outright(db_session, "this_phone")
    if linked:
        db_session.add(UserDevice(user_id=user_id, device_id="this_phone"))
        db_session.commit()

    assert status(client, "this_phone", token)["unlocked"] is True


# --- what the account still adds -------------------------------------------


def test_the_account_still_finds_a_purchase_from_another_device(client, db_session):
    """The union has to keep working in the direction it already did."""
    token, user_id = signed_in(db_session)
    db_session.add(UserDevice(user_id=user_id, device_id="old_phone"))
    db_session.commit()
    bought_outright(db_session, "old_phone")

    assert status(client, "new_phone", token)["unlocked"] is True
    assert status(client, "new_phone")["unlocked"] is False


def test_a_token_does_not_grant_access_to_somebody_elses_device(client, db_session):
    """A union must not become a free-for-all."""
    bought_outright(db_session, "stranger_device")
    token, _ = signed_in(db_session)

    assert status(client, "my_device", token)["unlocked"] is False


def test_lifetime_still_wins_over_a_subscription_when_signed_in(client, db_session):
    token, user_id = signed_in(db_session)
    bought_outright(db_session, "my_device")
    subscribed(db_session, user_id=user_id)

    body = status(client, "my_device", token)

    assert body["plan"] == "lifetime"
    assert body["expires_at"] is None
