"""Reading real Stripe subscription and invoice payloads.

Every fixture here was captured from this account in test mode, at API version
2026-07-29.dahlia, which is the version the live webhook sends. That matters
more than usual: the two bugs these tests exist to prevent are both fields that
moved between API versions, and a hand-written fixture would have agreed with
whichever assumption the code was written under.

No database and no network. These are pure functions, so a failure here is
always about reading Stripe rather than about anything else.
"""

import json
from datetime import timezone

from conftest import FIXTURES_DIR

from payments.subscriptions import (
    read_invoice_event,
    read_subscription_event,
)


def load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def subscription_object(name: str = "subscription_created") -> dict:
    return load(name)["data"]["object"]


def invoice_object() -> dict:
    return load("invoice_paid")["data"]["object"]


# --- the field that moved off the subscription ------------------------------


def test_the_payload_really_does_not_carry_the_old_field():
    """Guards the premise. If this fails the rest of the file proves nothing.

    Should Stripe ever put current_period_end back at the top level, this test
    fails and tells us the workaround below is no longer load bearing.
    """
    for name in ("subscription_created", "subscription_updated", "subscription_deleted"):
        assert "current_period_end" not in subscription_object(name)


def test_period_end_is_read_from_the_subscription_item():
    state = read_subscription_event(subscription_object())

    assert state.current_period_end is not None
    assert state.current_period_end.tzinfo is not None
    expected = subscription_object()["items"]["data"][0]["current_period_end"]
    assert int(state.current_period_end.timestamp()) == expected


def test_reading_the_old_location_would_have_returned_nothing():
    """The shape of the bug, stated so nobody reintroduces it.

    Reading the top level does not raise. It returns None, the expiry is never
    written, access is never extended, and the webhook still answers 200. A
    silent failure is why this is worth a test of its own.
    """
    assert subscription_object().get("current_period_end") is None


def test_the_latest_item_period_wins():
    """One item today, but the field is per item and Stripe allows several."""
    payload = subscription_object()
    first = payload["items"]["data"][0]
    later = json.loads(json.dumps(first))
    later["current_period_end"] = first["current_period_end"] + 86_400
    payload["items"]["data"] = [first, later]

    state = read_subscription_event(payload)

    assert int(state.current_period_end.timestamp()) == later["current_period_end"]


def test_a_subscription_with_no_items_has_no_period_end():
    payload = subscription_object()
    payload["items"]["data"] = []

    assert read_subscription_event(payload).current_period_end is None


# --- status and cancellation ------------------------------------------------


def test_a_live_subscription_is_active():
    state = read_subscription_event(subscription_object("subscription_created"))

    assert state.status == "active"
    assert state.is_active
    assert state.cancel_at_period_end is False


def test_cancel_at_period_end_is_not_the_same_as_cancelled():
    """Someone who has cancelled keeps access until the period they paid for ends.

    Treating this event as the end of access would cut them off the moment they
    click cancel, which is time they have already been charged for.
    """
    state = read_subscription_event(subscription_object("subscription_updated"))

    assert state.cancel_at_period_end is True
    assert state.status == "active"
    assert state.is_active


def test_a_deleted_subscription_is_not_active():
    state = read_subscription_event(subscription_object("subscription_deleted"))

    assert state.status == "canceled"
    assert state.is_active is False


def test_a_failed_renewal_still_counts_as_active():
    """past_due means Stripe is still retrying the card, not that they left."""
    payload = subscription_object()
    payload["status"] = "past_due"

    assert read_subscription_event(payload).is_active


def test_an_unpaid_subscription_is_not_active():
    payload = subscription_object()
    payload["status"] = "unpaid"

    assert read_subscription_event(payload).is_active is False


# --- identity ---------------------------------------------------------------


def test_identity_comes_off_subscription_metadata():
    state = read_subscription_event(subscription_object())

    assert state.is_ours
    assert state.device_id == "probe_device_001"
    assert state.can_apply


def test_a_user_id_is_parsed_from_its_string():
    payload = subscription_object()
    payload["metadata"]["user_id"] = "42"

    assert read_subscription_event(payload).user_id == 42


def test_a_junk_user_id_is_ignored_rather_than_crashing():
    """Metadata is free text. Anything can end up in it."""
    payload = subscription_object()
    payload["metadata"]["user_id"] = "not-a-number"

    assert read_subscription_event(payload).user_id is None


def test_another_products_subscription_is_not_ours():
    """One Stripe account can sell more than one thing."""
    payload = subscription_object()
    payload["metadata"] = {}

    state = read_subscription_event(payload)

    assert state.is_ours is False
    assert state.can_apply is False


def test_a_subscription_naming_nobody_cannot_be_applied():
    payload = subscription_object()
    payload["metadata"] = {"golf_coach_now": "wedge_unlock"}

    assert read_subscription_event(payload).can_apply is False


# --- the field that moved off the invoice -----------------------------------


def test_the_invoice_really_does_not_carry_the_old_field():
    """The other premise. invoice.subscription reads as None in this version."""
    assert invoice_object().get("subscription") is None


def test_the_subscription_is_found_under_parent():
    payment = read_invoice_event(invoice_object())

    expected = invoice_object()["parent"]["subscription_details"]["subscription"]
    assert payment.stripe_subscription_id == expected
    assert payment.stripe_subscription_id.startswith("sub_")


def test_a_renewal_is_still_traceable_to_a_person():
    """The reason subscription metadata is set at checkout rather than session
    metadata: this event arrives every month for years afterwards."""
    payment = read_invoice_event(invoice_object())

    assert payment.is_ours
    assert payment.device_id == "probe_device_001"


def test_paid_is_read_from_status_not_the_boolean():
    """The boolean `paid` field reads as None in this API version."""
    assert invoice_object().get("paid") is None
    assert read_invoice_event(invoice_object()).paid is True


def test_a_failed_payment_is_not_paid():
    payload = invoice_object()
    payload["status"] = "open"

    assert read_invoice_event(payload).paid is False


def test_the_paid_period_comes_from_the_invoice_line():
    payment = read_invoice_event(invoice_object())

    expected = invoice_object()["lines"]["data"][0]["period"]["end"]
    assert int(payment.period_end.timestamp()) == expected
    assert payment.period_end.tzinfo == timezone.utc


def test_an_invoice_with_no_lines_has_no_period():
    payload = invoice_object()
    payload["lines"]["data"] = []

    assert read_invoice_event(payload).period_end is None


def test_an_invoice_that_is_not_for_a_subscription_is_handled():
    """One-time invoices exist too, and they have no subscription parent."""
    payload = invoice_object()
    payload["parent"] = None

    payment = read_invoice_event(payload)

    assert payment.stripe_subscription_id is None
    assert payment.is_ours is False
