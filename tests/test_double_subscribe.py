"""Nobody gets sold two subscriptions to the same product.

Stripe will create the second one without complaint, along with a second
customer, and bill them monthly for both. The customer sees one product and two
charges, and the app cannot tell them which to cancel. That ends in a refund at
best and a chargeback at worst, and chargebacks cost more than the sale.
"""

from datetime import datetime, timedelta, timezone

import pytest
from conftest import build_payments_app

from fastapi.testclient import TestClient

from payments import routes
from payments.accounts_models import User, UserDevice
from payments.config import settings
from payments.subscription_models import UserSubscription


class FakeSession:
    id = "cs_test_subscription"
    url = "https://checkout.example/x"


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


@pytest.fixture(autouse=True)
def priced(monkeypatch):
    monkeypatch.setattr(
        settings, "stripe_subscription_price_id", "price_test_monthly", raising=False
    )


@pytest.fixture
def calls(monkeypatch) -> list:
    recorded = []

    def fake(device_id, user_id=None, customer_email=None):
        recorded.append(device_id)
        return FakeSession()

    monkeypatch.setattr(
        routes.stripe_gateway, "create_subscription_checkout_session", fake
    )
    return recorded


def add_subscription(
    db_session,
    device_id=None,
    user_id=None,
    status="active",
    days_left=20,
    stripe_id="sub_existing",
):
    db_session.add(
        UserSubscription(
            user_id=user_id,
            device_id=device_id,
            stripe_customer_id="cus_x",
            stripe_subscription_id=stripe_id,
            status=status,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=days_left),
        )
    )
    db_session.commit()


def sign_in(db_session, email="already@example.com") -> tuple[str, int]:
    import secrets

    from payments.accounts import _hash_token
    from payments.accounts_models import AuthToken

    user = User(email=email)
    db_session.add(user)
    db_session.commit()
    token = secrets.token_urlsafe(32)
    db_session.add(AuthToken(user_id=user.id, token_hash=_hash_token(token)))
    db_session.commit()
    return token, user.id


# --- the guard --------------------------------------------------------------


def test_subscribing_twice_from_the_same_device_is_refused(client, calls, db_session):
    add_subscription(db_session, device_id="d1")

    response = client.post("/payments/subscribe", json={"device_id": "d1"})

    assert response.status_code == 409
    assert calls == [], "Stripe was asked for a second subscription"


def test_a_signed_in_subscriber_is_refused_on_a_different_device(
    client, calls, db_session
):
    """The subscription belongs to the person, so a new phone is not a new sale."""
    token, user_id = sign_in(db_session)
    add_subscription(db_session, user_id=user_id)

    response = client.post(
        "/payments/subscribe",
        json={"device_id": "a_brand_new_phone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert calls == []


def test_a_subscription_on_a_linked_device_also_counts(client, calls, db_session):
    """Subscribed before signing in, then signed in. Still one subscription."""
    token, user_id = sign_in(db_session)
    db_session.add(UserDevice(user_id=user_id, device_id="old_phone"))
    db_session.commit()
    add_subscription(db_session, device_id="old_phone")

    response = client.post(
        "/payments/subscribe",
        json={"device_id": "new_phone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409


# --- when subscribing again is right ----------------------------------------


def test_a_cancelled_subscriber_can_subscribe_again(client, calls, db_session):
    """Coming back is a new sale, not a duplicate."""
    add_subscription(db_session, device_id="d1", status="canceled")

    response = client.post("/payments/subscribe", json={"device_id": "d1"})

    assert response.status_code == 200
    assert calls == ["d1"]


def test_an_expired_period_does_not_block_a_new_subscription(client, calls, db_session):
    """Status can go stale when a webhook is missed. The date cannot.

    A row still saying active whose paid period ended weeks ago must not stop
    somebody paying us again.
    """
    add_subscription(db_session, device_id="d1", status="active", days_left=-3)

    response = client.post("/payments/subscribe", json={"device_id": "d1"})

    assert response.status_code == 200


def test_a_failed_card_still_counts_as_subscribed(client, calls, db_session):
    """past_due means Stripe is retrying, not that they left."""
    add_subscription(db_session, device_id="d1", status="past_due")

    response = client.post("/payments/subscribe", json={"device_id": "d1"})

    assert response.status_code == 409


def test_someone_elses_subscription_does_not_block_you(client, calls, db_session):
    add_subscription(db_session, device_id="somebody_else")

    response = client.post("/payments/subscribe", json={"device_id": "d1"})

    assert response.status_code == 200
