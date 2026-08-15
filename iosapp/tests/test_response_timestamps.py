"""Timestamps the app can actually parse.

Every datetime here is UTC, but SQLite returns them with no timezone attached
and pydantic then renders them bare:

    2026-09-12T17:12:50        instead of        2026-09-12T17:12:50Z

A reader cannot tell whether that means UTC or the server's local time, and
strict ISO 8601 parsers refuse it - Swift's ISO8601DateFormatter returns nil,
Kotlin's Instant.parse throws.

Both apps currently declare these fields as String and never parse them, so
nothing is broken today. It breaks the first time somebody builds the screen
that says when a subscription renews, which is a screen this milestone exists
to make possible. The documented contract already promised the Z; the API was
the side that was wrong.
"""

import secrets
from datetime import datetime, timedelta, timezone

import pytest
from conftest import DEVICE_ID, build_payments_app, load_event, post_webhook

from fastapi.testclient import TestClient

from payments.schemas import as_utc_iso
from payments.subscription_models import UserSubscription


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


def parses_strictly(value: str) -> datetime:
    """Reject anything a real ISO parser on a phone would reject."""
    assert value.endswith("Z"), f"{value!r} carries no timezone"
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# --- the helper -------------------------------------------------------------


def test_a_naive_timestamp_is_stamped_as_utc():
    """This is the SQLite case, and the one that actually happens."""
    out = as_utc_iso(datetime(2026, 9, 12, 17, 12, 50))

    assert out == "2026-09-12T17:12:50Z"
    assert parses_strictly(out).tzinfo == timezone.utc


def test_an_aware_timestamp_is_converted_rather_than_relabelled():
    """A non-UTC input must move, not just have its label swapped."""
    moscow = timezone(timedelta(hours=3))
    out = as_utc_iso(datetime(2026, 9, 12, 20, 12, 50, tzinfo=moscow))

    assert out == "2026-09-12T17:12:50Z"


def test_none_stays_none():
    assert as_utc_iso(None) is None


# --- the responses ----------------------------------------------------------


def test_a_lifetime_unlock_timestamp_is_parseable(client):
    post_webhook(client, load_event())

    body = client.get(f"/payments/unlock-status?device_id={DEVICE_ID}").json()

    assert body["plan"] == "lifetime"
    parses_strictly(body["unlocked_at"])
    assert body["expires_at"] is None, "lifetime access must not carry an expiry"


def test_a_subscription_expiry_is_parseable(client, db_session):
    db_session.add(
        UserSubscription(
            device_id="tz_device",
            stripe_customer_id="cus_x",
            stripe_subscription_id="sub_" + secrets.token_hex(4),
            status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    db_session.commit()

    body = client.get("/payments/unlock-status?device_id=tz_device").json()

    assert body["plan"] == "monthly"
    expires = parses_strictly(body["expires_at"])
    parses_strictly(body["unlocked_at"])

    # And it has to be a future moment once parsed, not merely well formed.
    assert expires > datetime.now(timezone.utc)


def test_no_access_reports_no_timestamps(client):
    body = client.get("/payments/unlock-status?device_id=nobody_at_all").json()

    assert body["unlocked"] is False
    assert body["unlocked_at"] is None
    assert body["expires_at"] is None
