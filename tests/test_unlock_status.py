"""The unlock status endpoint.

The mobile app is written against this response, so the shape is part of the
contract and is checked here rather than assumed.
"""

from conftest import DEVICE_ID, PAYMENT_INTENT_ID, SESSION_ID, load_event, post_webhook


def test_unknown_device_is_not_unlocked(client):
    """A device that has never paid gets a plain answer, not a 404.

    The app calls this on every launch. Making "no" an error would mean every
    non-paying user starts the app on an error path.
    """
    response = client.get("/payments/unlock-status?device_id=never_seen_before")

    assert response.status_code == 200
    assert response.json() == {
        "device_id": "never_seen_before",
        "unlocked": False,
        "unlocked_at": None,
    }


def test_paid_device_is_unlocked(client):
    post_webhook(client, load_event())

    response = client.get(f"/payments/unlock-status?device_id={DEVICE_ID}")
    body = response.json()

    assert response.status_code == 200
    assert body["device_id"] == DEVICE_ID
    assert body["unlocked"] is True
    assert body["unlocked_at"] is not None


def test_device_id_is_required(client):
    response = client.get("/payments/unlock-status")

    assert response.status_code == 422


def test_payment_details_are_recorded_for_support(client, db_session):
    """Enough is stored to answer "did this person pay?" months later.

    The email matters most. Device IDs change when a user reinstalls, so it is
    the only durable way to identify a customer who has lost their unlock.
    """
    from payments.models import Unlock

    post_webhook(client, load_event())
    unlock = db_session.query(Unlock).one()

    assert unlock.device_id == DEVICE_ID
    assert unlock.checkout_session_id == SESSION_ID
    assert unlock.payment_intent_id == PAYMENT_INTENT_ID
    assert unlock.amount_total == 1499
    assert unlock.currency == "usd"
    assert unlock.customer_email == "buyer@example.com"
    assert unlock.status == "paid"
