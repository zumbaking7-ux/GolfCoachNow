"""Idempotency.

Stripe redelivers an event until it gets a 2xx back, so the same
checkout.session.completed can arrive several times. Delivery two must not
produce unlock two.
"""

from conftest import EVENT_ID, load_event, post_webhook
from payments.models import ProcessedEvent, Unlock


def test_same_event_twice_produces_exactly_one_unlock(client, db_session):
    """The test promised in the proposal.

    Both deliveries get a 200, because from Stripe's point of view both
    succeeded and it should stop resending. Only one unlock row exists.
    """
    event = load_event()

    first = post_webhook(client, event)
    second = post_webhook(client, event)

    assert first.status_code == 200
    assert second.status_code == 200
    assert db_session.query(Unlock).count() == 1
    assert db_session.query(ProcessedEvent).count() == 1


def test_event_is_recorded_as_processed(client, db_session):
    post_webhook(client, load_event())

    processed = db_session.query(ProcessedEvent).one()
    assert processed.stripe_event_id == EVENT_ID
    assert processed.event_type == "checkout.session.completed"
    assert processed.processed_at is not None


def test_two_events_for_the_same_device_produce_one_unlock(client, db_session):
    """Different event IDs, same device.

    The event ID index does not help here - these are genuinely different
    events. The unique constraint on device_id is what stops the second one
    creating a duplicate row.
    """
    first_event = load_event()
    second_event = load_event()
    second_event["id"] = EVENT_ID + "_second"
    second_event["data"]["object"]["id"] = "cs_test_a_second_session"

    assert post_webhook(client, first_event).status_code == 200
    assert post_webhook(client, second_event).status_code == 200

    assert db_session.query(Unlock).count() == 1
    assert db_session.query(ProcessedEvent).count() == 2


def test_unhandled_event_type_is_acknowledged_and_ignored(client, db_session):
    """Returning 200 tells Stripe to stop sending this type.

    A 500 here would put the endpoint in a retry loop over an event it was
    never going to act on.
    """
    event = load_event()
    event["id"] = EVENT_ID + "_other_type"
    event["type"] = "payment_intent.succeeded"

    response = post_webhook(client, event)

    assert response.status_code == 200
    assert db_session.query(Unlock).count() == 0
    assert db_session.query(ProcessedEvent).count() == 0


def test_session_without_client_reference_id_is_not_unlocked(client, db_session):
    """No device ID means there is nobody to unlock.

    Acknowledged so Stripe stops retrying, logged as a warning, and no row
    written - guessing which device to unlock would be worse than doing
    nothing.
    """
    event = load_event()
    event["data"]["object"]["client_reference_id"] = None

    response = post_webhook(client, event)

    assert response.status_code == 200
    assert db_session.query(Unlock).count() == 0


def test_payment_for_a_different_product_does_not_unlock(client, db_session):
    """A paid session this service did not create must be ignored.

    Their Stripe account already holds more than one product. If anything else
    is ever sold through it and carries a client_reference_id, that buyer would
    otherwise get a free wedge unlock.

    It is acknowledged with a 200, not failed. Somebody else's payment is not
    an error here, it is simply not ours to act on, and a 500 would put Stripe
    into a retry loop over an event we are never going to handle.
    """
    event = load_event()
    event["data"]["object"]["metadata"] = {"some_other_product": "yes"}

    response = post_webhook(client, event)

    assert response.status_code == 200
    assert db_session.query(Unlock).count() == 0


def test_session_with_no_metadata_does_not_unlock(client, db_session):
    event = load_event()
    event["data"]["object"]["metadata"] = {}

    response = post_webhook(client, event)

    assert response.status_code == 200
    assert db_session.query(Unlock).count() == 0


def test_unpaid_session_is_not_unlocked(client, db_session):
    """checkout.session.completed can arrive for a session that is not paid."""
    event = load_event()
    event["data"]["object"]["payment_status"] = "unpaid"

    response = post_webhook(client, event)

    assert response.status_code == 200
    assert db_session.query(Unlock).count() == 0
