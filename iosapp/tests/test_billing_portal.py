"""The link to Stripe's subscription management page.

The security question here is the whole test file. Stripe's portal is opened
for a customer ID, and if this endpoint accepted one from the caller then
anybody with a cus_ identifier could cancel a stranger's subscription or read
their invoices and billing address. It looks like a harmless parameter because
Stripe requires it, which is exactly why it is worth a test that would fail
loudly if somebody added it back.
"""

import secrets
from datetime import datetime, timedelta, timezone

import pytest
from conftest import build_payments_app

from fastapi.testclient import TestClient

import stripe
from payments import routes
from payments.accounts import _hash_token
from payments.accounts_models import AuthToken, User, UserDevice
from payments.subscription_models import UserSubscription


class FakePortal:
    url = "https://billing.stripe.com/p/session/test_abc123"


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


@pytest.fixture
def opened_for(monkeypatch) -> list[str]:
    """Record which Stripe customer the portal was opened for."""
    recorded: list[str] = []

    def fake(customer_id):
        recorded.append(customer_id)
        return FakePortal()

    monkeypatch.setattr(routes.stripe_gateway, "create_billing_portal_session", fake)
    return recorded


def subscribe(db_session, device_id=None, user_id=None, customer="cus_theirs", days_left=30, status="active"):
    db_session.add(
        UserSubscription(
            user_id=user_id,
            device_id=device_id,
            stripe_customer_id=customer,
            stripe_subscription_id="sub_" + secrets.token_hex(4),
            status=status,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=days_left),
        )
    )
    db_session.commit()


def sign_in(db_session, email="portal@example.com") -> tuple[str, int]:
    user = User(email=email)
    db_session.add(user)
    db_session.commit()
    token = secrets.token_urlsafe(32)
    db_session.add(AuthToken(user_id=user.id, token_hash=_hash_token(token)))
    db_session.commit()
    return token, user.id


# --- the security property --------------------------------------------------


def test_the_customer_id_comes_from_the_database_not_the_request(
    client, opened_for, db_session
):
    """A customer ID in the body must never be honoured.

    If it were, anybody could open a portal session for a stranger's Stripe
    customer and cancel their subscription or read their billing address.
    """
    subscribe(db_session, device_id="mine", customer="cus_mine")
    subscribe(db_session, device_id="yours", customer="cus_yours")

    response = client.post(
        "/payments/billing-portal",
        json={"device_id": "mine", "customer_id": "cus_yours", "customer": "cus_yours"},
    )

    assert response.status_code == 200
    assert opened_for == ["cus_mine"], "the portal was opened for somebody else"


def test_a_caller_with_no_subscription_gets_404(client, opened_for):
    response = client.post("/payments/billing-portal", json={"device_id": "nobody"})

    assert response.status_code == 404
    assert opened_for == []


def test_a_lapsed_subscription_has_nothing_to_manage(client, opened_for, db_session):
    subscribe(db_session, device_id="d1", days_left=-5, status="canceled")

    assert (
        client.post("/payments/billing-portal", json={"device_id": "d1"}).status_code
        == 404
    )


def test_never_subscribed_and_lapsed_look_identical(client, opened_for, db_session):
    """Same answer either way. Which of the two it is not something an
    unauthenticated caller should be able to learn."""
    subscribe(db_session, device_id="lapsed", days_left=-5, status="canceled")

    never = client.post("/payments/billing-portal", json={"device_id": "never"})
    lapsed = client.post("/payments/billing-portal", json={"device_id": "lapsed"})

    assert never.status_code == lapsed.status_code == 404
    assert never.json() == lapsed.json()


# --- the ordinary paths -----------------------------------------------------


def test_a_device_with_a_subscription_gets_a_url(client, opened_for, db_session):
    subscribe(db_session, device_id="d1", customer="cus_d1")

    response = client.post("/payments/billing-portal", json={"device_id": "d1"})

    assert response.status_code == 200
    assert response.json()["portal_url"].startswith("https://billing.stripe.com/")
    assert opened_for == ["cus_d1"]


def test_a_signed_in_person_needs_no_device_id(client, opened_for, db_session):
    """They may be on a phone that never touched the subscription."""
    token, user_id = sign_in(db_session)
    subscribe(db_session, user_id=user_id, customer="cus_account")

    response = client.post(
        "/payments/billing-portal",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert opened_for == ["cus_account"]


def test_a_subscription_on_a_linked_device_is_reachable(client, opened_for, db_session):
    token, user_id = sign_in(db_session)
    db_session.add(UserDevice(user_id=user_id, device_id="old_phone"))
    db_session.commit()
    subscribe(db_session, device_id="old_phone", customer="cus_old")

    response = client.post(
        "/payments/billing-portal",
        json={"device_id": "new_phone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert opened_for == ["cus_old"]


# --- bad input and Stripe being down ----------------------------------------


def test_neither_token_nor_device_is_422(client, opened_for):
    assert client.post("/payments/billing-portal", json={}).status_code == 422


def test_stripe_being_unreachable_is_502(client, db_session, monkeypatch):
    subscribe(db_session, device_id="d1")

    def explode(customer_id):
        raise stripe.APIConnectionError("network down")

    monkeypatch.setattr(routes.stripe_gateway, "create_billing_portal_session", explode)

    response = client.post("/payments/billing-portal", json={"device_id": "d1"})

    assert response.status_code == 502
