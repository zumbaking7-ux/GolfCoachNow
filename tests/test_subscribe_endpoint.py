"""Starting a monthly subscription.

Nothing here reaches Stripe. The gateway call is replaced, because what these
tests are about is what this service decides before and after it: whether the
plan is on sale, who the subscription gets attached to, and what the app is
told when something is wrong.
"""

import pytest
from conftest import build_payments_app

from fastapi.testclient import TestClient

import stripe
from payments import routes
from payments.accounts_models import User
from payments.config import settings


class FakeSession:
    def __init__(self, session_id="cs_test_subscription", url="https://checkout.example/x"):
        self.id = session_id
        self.url = url


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


@pytest.fixture
def priced(monkeypatch):
    """A recurring price is configured."""
    monkeypatch.setattr(
        settings, "stripe_subscription_price_id", "price_test_monthly", raising=False
    )


@pytest.fixture
def calls(monkeypatch) -> list[dict]:
    """Record what the gateway was asked for, without calling Stripe."""
    recorded: list[dict] = []

    def fake(device_id, user_id=None, customer_email=None):
        recorded.append(
            {"device_id": device_id, "user_id": user_id, "customer_email": customer_email}
        )
        return FakeSession()

    monkeypatch.setattr(
        routes.stripe_gateway, "create_subscription_checkout_session", fake
    )
    return recorded


def sign_in(client: TestClient, db_session, email="subscriber@example.com") -> tuple[str, int]:
    """Get a real bearer token the way the app does."""
    from payments.accounts import _hash_token
    from payments.accounts_models import AuthToken
    import secrets

    user = User(email=email)
    db_session.add(user)
    db_session.commit()

    token = secrets.token_urlsafe(32)
    db_session.add(AuthToken(user_id=user.id, token_hash=_hash_token(token)))
    db_session.commit()
    return token, user.id


# --- when the plan is not on sale -------------------------------------------


def test_subscribing_with_no_price_configured_is_503(client, db_session):
    """Not an error in this service. The plan simply is not available yet.

    503 rather than 500 so the app can say "not available" instead of showing a
    failure, and so it does not look like something is broken when it is not.
    """
    response = client.post("/payments/subscribe", json={"device_id": "d1"})

    assert response.status_code == 503
    assert "not available" in response.json()["detail"].lower()


# --- the ordinary path ------------------------------------------------------


def test_subscribing_returns_a_checkout_url(client, priced, calls):
    response = client.post("/payments/subscribe", json={"device_id": "d1"})

    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://checkout.example/x"
    assert calls == [{"device_id": "d1", "user_id": None, "customer_email": None}]


def test_a_signed_in_subscriber_is_attached_to_their_account(
    client, priced, calls, db_session
):
    """The reason accounts came first.

    Attached to the account, the subscription survives a new phone. Attached to
    the device only, it does not, and the person keeps being charged for access
    they cannot reach.
    """
    token, user_id = sign_in(client, db_session)

    response = client.post(
        "/payments/subscribe",
        json={"device_id": "d1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert calls[0]["user_id"] == user_id
    assert calls[0]["customer_email"] == "subscriber@example.com"


def test_a_dead_token_still_subscribes_by_device(client, priced, calls, db_session):
    """An expired or revoked token must not stop someone paying us."""
    response = client.post(
        "/payments/subscribe",
        json={"device_id": "d1"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 200
    assert calls[0]["user_id"] is None


# --- bad input and Stripe being down ----------------------------------------


def test_a_missing_device_id_is_rejected(client, priced):
    assert client.post("/payments/subscribe", json={}).status_code == 422


def test_an_empty_device_id_is_rejected(client, priced):
    assert (
        client.post("/payments/subscribe", json={"device_id": ""}).status_code == 422
    )


def test_stripe_being_unreachable_is_502_not_500(client, priced, monkeypatch):
    """A 500 says we are broken. A 502 says the thing behind us is."""

    def explode(**kwargs):
        raise stripe.APIConnectionError("network down")

    monkeypatch.setattr(
        routes.stripe_gateway, "create_subscription_checkout_session", explode
    )

    response = client.post("/payments/subscribe", json={"device_id": "d1"})

    assert response.status_code == 502
