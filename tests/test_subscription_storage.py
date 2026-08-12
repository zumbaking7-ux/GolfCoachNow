"""Recording subscription state from webhook events.

The events that matter arrive repeatedly, out of order, and sometimes for
subscriptions we have not seen yet. Stripe retries anything that does not
answer 2xx, and a renewal and a cancellation can cross in flight. Every test
here is about one of those, because the ordinary case works by accident and
these do not.

Real captured payloads, same four fixtures as the parsing tests.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from conftest import FIXTURES_DIR, build_payments_app, post_webhook

from fastapi.testclient import TestClient

from payments.accounts_models import User, UserDevice
from payments.subscription_models import UserSubscription
from payments.subscription_service import has_access

DEVICE = "probe_device_001"


def event(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def with_period_end(payload: dict, when: datetime) -> dict:
    """Move a subscription payload's paid period to a given moment."""
    for item in payload["data"]["object"]["items"]["data"]:
        item["current_period_end"] = int(when.timestamp())
    return payload


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


def only_subscription(db_session) -> UserSubscription:
    rows = db_session.query(UserSubscription).all()
    assert len(rows) == 1, f"expected one subscription, found {len(rows)}"
    return rows[0]


# --- the basics -------------------------------------------------------------


def test_a_new_subscription_is_recorded(client, db_session):
    response = post_webhook(client, event("subscription_created"))

    assert response.status_code == 200
    row = only_subscription(db_session)
    assert row.device_id == DEVICE
    assert row.status == "active"
    assert row.current_period_end is not None
    assert has_access(row)


def test_the_same_event_twice_is_still_one_row(client, db_session):
    """Stripe retries until it gets a 2xx, so this is the normal case."""
    payload = event("subscription_created")

    post_webhook(client, payload)
    post_webhook(client, payload)

    only_subscription(db_session)


def test_a_cancellation_takes_access_away(client, db_session):
    post_webhook(client, event("subscription_created"))
    post_webhook(client, event("subscription_deleted"))

    row = only_subscription(db_session)
    assert row.status == "canceled"
    assert not has_access(row)


def test_cancelling_at_period_end_keeps_access_until_then(client, db_session):
    """They have paid for this month. Taking it back at the click is theft."""
    post_webhook(client, event("subscription_created"))
    post_webhook(client, event("subscription_updated"))

    row = only_subscription(db_session)
    assert row.cancel_at_period_end is True
    assert row.status == "active"
    assert has_access(row)


# --- out of order and crossed events ----------------------------------------


def test_a_late_cancellation_does_not_rewind_a_renewal(client, db_session):
    """The one that would quietly lock out a paying customer.

    A cancellation carries the period end that was current when it fired. If it
    arrives after a renewal has already pushed the period forward, writing its
    date would take back a month the customer has paid for.
    """
    later = datetime.now(timezone.utc) + timedelta(days=40)
    earlier = datetime.now(timezone.utc) + timedelta(days=5)

    post_webhook(client, with_period_end(event("subscription_created"), later))

    stale = with_period_end(event("subscription_updated"), earlier)
    stale["id"] = "evt_stale_update"
    post_webhook(client, stale)

    row = only_subscription(db_session)
    assert row.current_period_end is not None
    assert row.current_period_end.replace(tzinfo=timezone.utc) > later - timedelta(
        minutes=1
    ), "a stale event rewound the paid period"


def test_an_invoice_for_an_unknown_subscription_is_not_an_error(client, db_session):
    """invoice.paid can beat customer.subscription.created."""
    response = post_webhook(client, event("invoice_paid"))

    assert response.status_code == 200
    assert db_session.query(UserSubscription).count() == 0


def test_a_paid_invoice_extends_the_period(client, db_session):
    """Without this everybody lapses after one month having paid for more."""
    soon = datetime.now(timezone.utc) + timedelta(days=1)
    post_webhook(client, with_period_end(event("subscription_created"), soon))

    before = only_subscription(db_session).current_period_end
    post_webhook(client, event("invoice_paid"))
    after = only_subscription(db_session).current_period_end

    assert after > before, "a paid invoice did not extend access"


def test_a_failed_payment_does_not_cut_access_off(client, db_session):
    """Stripe is still retrying the card. A weekend card expiry is not a
    reason to lock somebody out of what they have paid for."""
    post_webhook(client, event("subscription_created"))

    failed = event("invoice_paid")
    failed["id"] = "evt_payment_failed"
    failed["type"] = "invoice.payment_failed"
    failed["data"]["object"]["status"] = "open"
    post_webhook(client, failed)

    assert has_access(only_subscription(db_session))


# --- who it belongs to ------------------------------------------------------


def test_a_subscription_is_attached_to_the_user_from_its_metadata(client, db_session):
    payload = event("subscription_created")
    user = User(email="metadata@example.com")
    db_session.add(user)
    db_session.commit()
    payload["data"]["object"]["metadata"]["user_id"] = str(user.id)

    post_webhook(client, payload)

    assert only_subscription(db_session).user_id == user.id


def test_a_device_already_linked_to_an_account_attaches_too(client, db_session):
    """Subscribed before signing in, then signed in on the same phone."""
    user = User(email="linked@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.add(UserDevice(user_id=user.id, device_id=DEVICE))
    db_session.commit()

    post_webhook(client, event("subscription_created"))

    assert only_subscription(db_session).user_id == user.id


def test_another_products_subscription_is_ignored(client, db_session):
    """One Stripe account can sell more than one thing."""
    payload = event("subscription_created")
    payload["data"]["object"]["metadata"] = {}

    response = post_webhook(client, payload)

    assert response.status_code == 200
    assert db_session.query(UserSubscription).count() == 0
