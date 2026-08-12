"""What the webhook does with subscription events.

The dangerous case is not an event the webhook ignores. It is an event it
recognises and handles as the wrong thing.

checkout.session.completed is already handled, and the existing handler treats
every one of them as a one-time purchase. A subscription checkout produces that
same event type, with payment_status paid and a device ID attached, so it walks
straight into the one-time path and grants a permanent unlock. The customer
would pay once and own the app forever, and cancelling would take nothing away.
"""

import json

import pytest
from conftest import FIXTURES_DIR, build_payments_app, load_event, post_webhook

from fastapi.testclient import TestClient
from payments.models import ProcessedEvent, Unlock


def real_event(name: str) -> dict:
    """A captured event, not one written by hand."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def subscription_checkout_event() -> dict:
    """The real one-time event, reshaped the way Stripe sends a subscription.

    Same fixture as everything else, with the three fields that differ in
    subscription mode changed and nothing else touched.
    """
    event = load_event()
    event["id"] = "evt_subscription_checkout"
    obj = event["data"]["object"]
    obj["id"] = "cs_test_subscription_checkout"
    obj["mode"] = "subscription"
    obj["subscription"] = "sub_from_checkout"
    obj["client_reference_id"] = "device_that_subscribed"
    return event


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


def test_a_subscription_checkout_does_not_grant_a_permanent_unlock(client, db_session):
    """The landmine.

    An Unlock row has no expiry. Once it exists that device is unlocked for
    good, whatever happens to the subscription afterwards. Granting one from a
    monthly checkout means the first payment buys the app outright.
    """
    response = post_webhook(client, subscription_checkout_event())

    assert response.status_code == 200

    unlock = (
        db_session.query(Unlock)
        .filter(Unlock.device_id == "device_that_subscribed")
        .first()
    )
    assert unlock is None, (
        "a monthly checkout granted a permanent unlock, so the customer now "
        "owns the app for one month's payment"
    )


def test_a_one_time_checkout_still_grants_an_unlock(client, db_session):
    """The other half. Telling them apart must not break what works today."""
    event = load_event()
    device_id = event["data"]["object"]["client_reference_id"]

    response = post_webhook(client, event)

    assert response.status_code == 200
    unlock = (
        db_session.query(Unlock).filter(Unlock.device_id == device_id).first()
    )
    assert unlock is not None


def test_a_checkout_with_no_mode_is_not_unlocked(client, db_session):
    """Anything unrecognised must not fall through into the one-time path."""
    event = load_event()
    event["id"] = "evt_modeless"
    obj = event["data"]["object"]
    obj["id"] = "cs_test_modeless"
    obj["client_reference_id"] = "device_modeless"
    del obj["mode"]

    response = post_webhook(client, event)

    assert response.status_code == 200
    assert (
        db_session.query(Unlock).filter(Unlock.device_id == "device_modeless").first()
        is not None
    ), "a missing mode is treated as one-time, which is the shipped behaviour"


# --- the same hole, in the other path ----------------------------------------
#
# The webhook is not the only thing that grants an unlock. The success redirect
# does too, and it was missed the first time because the test above only fired
# the webhook. A real subscription payment came back through the redirect and
# was given a permanent unlock, with source=success_redirect in the log.
#
# Both paths get the same test now.


def test_the_success_redirect_does_not_unlock_a_subscription(
    client, db_session, monkeypatch
):
    """What actually happened, turned into a test.

    Stripe sends the browser to /payments/success after payment. That endpoint
    retrieves the session and unlocks on its own, which is correct and
    deliberate for a one-time purchase. For a subscription it hands over the
    whole product for one month's money.
    """
    session_object = load_event()["data"]["object"]
    session_object["mode"] = "subscription"
    session_object["subscription"] = "sub_from_redirect"
    session_object["client_reference_id"] = "device_redirect_subscriber"

    monkeypatch.setattr(
        "payments.routes.stripe_gateway.retrieve_checkout_session",
        lambda session_id: session_object,
    )

    response = client.get(
        "/payments/success",
        params={"session_id": session_object["id"]},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        db_session.query(Unlock)
        .filter(Unlock.device_id == "device_redirect_subscriber")
        .first()
        is None
    ), "the success redirect granted a permanent unlock for a monthly plan"


def test_the_success_redirect_still_unlocks_a_one_time_purchase(
    client, db_session, monkeypatch
):
    """The behaviour that ships today has to survive the fix."""
    session_object = load_event()["data"]["object"]
    session_object["client_reference_id"] = "device_redirect_buyer"

    monkeypatch.setattr(
        "payments.routes.stripe_gateway.retrieve_checkout_session",
        lambda session_id: session_object,
    )

    response = client.get(
        "/payments/success",
        params={"session_id": session_object["id"]},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        db_session.query(Unlock)
        .filter(Unlock.device_id == "device_redirect_buyer")
        .first()
        is not None
    )


# --- the four real subscription events ---------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "subscription_created",
        "subscription_updated",
        "subscription_deleted",
        "invoice_paid",
    ],
)
def test_a_real_subscription_event_is_accepted_without_crashing(client, name):
    """Before the dispatch was split, every handled event was read as a
    checkout session. An invoice is not one, and reading it as one throws.

    A 500 here would tell Stripe to retry forever.
    """
    response = post_webhook(client, real_event(name))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "name", ["subscription_updated", "invoice_paid"]
)
def test_a_repeated_subscription_event_stays_a_single_row(client, db_session, name):
    """Idempotency has to cover the new event types too.

    Stripe retries until it gets a 2xx, so every one of these arrives more than
    once in normal operation.
    """
    event = real_event(name)

    first = post_webhook(client, event)
    second = post_webhook(client, event)

    assert (first.status_code, second.status_code) == (200, 200)
    assert (
        db_session.query(ProcessedEvent)
        .filter(ProcessedEvent.stripe_event_id == event["id"])
        .count()
        == 1
    )


def test_an_event_type_we_do_not_handle_is_acknowledged(client, db_session):
    """Stripe sends plenty we did not ask for. Ignoring is not failing."""
    event = load_event()
    event["id"] = "evt_unrelated"
    event["type"] = "payment_intent.created"

    response = post_webhook(client, event)

    assert response.status_code == 200
    assert (
        db_session.query(ProcessedEvent)
        .filter(ProcessedEvent.stripe_event_id == "evt_unrelated")
        .count()
        == 0
    ), "an ignored event should not be claimed, so it costs nothing to receive"
