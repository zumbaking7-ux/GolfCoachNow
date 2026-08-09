"""Creating the Checkout Session.

Stripe is patched at the SDK boundary so these tests check the arguments this
service actually sends, without a network call.
"""

import stripe

CHECKOUT_URL = "https://checkout.stripe.com/c/pay/cs_test_a1b2c3d4e5f6"
SESSION_ID = "cs_test_a1b2c3d4e5f6"


class FakeSession(dict):
    """Stripe returns a dict-like object with attribute access. So does this."""

    id = SESSION_ID
    url = CHECKOUT_URL


def test_device_id_is_sent_as_client_reference_id(client, monkeypatch):
    """The device ID must be attached server-side.

    This is the only link between a payment and a device. If it were sent by
    the browser instead, a user could claim someone else's payment.
    """
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return FakeSession()

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    response = client.post("/payments/checkout-session", json={"device_id": "device_abc"})

    assert response.status_code == 200
    assert response.json() == {"checkout_url": CHECKOUT_URL, "session_id": SESSION_ID}
    assert captured["client_reference_id"] == "device_abc"
    assert captured["mode"] == "payment"


def test_redirect_urls_are_https_not_the_deep_link(client, monkeypatch):
    """Stripe only accepts http and https for redirect URLs.

    Passing golfcoachnow:// here fails at session creation, which is why the
    app's deep link is reached through /payments/success instead of directly.
    This test is here so nobody "simplifies" that away later.
    """
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return FakeSession()

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    client.post("/payments/checkout-session", json={"device_id": "device_abc"})

    assert captured["success_url"].startswith("https://")
    assert captured["cancel_url"].startswith("https://")
    assert "{CHECKOUT_SESSION_ID}" in captured["success_url"]


def test_empty_device_id_is_rejected(client):
    response = client.post("/payments/checkout-session", json={"device_id": ""})

    assert response.status_code == 422


def test_stripe_failure_returns_502(client, monkeypatch):
    """A Stripe outage is not the caller's fault, so it is not a 4xx."""

    def fake_create(**kwargs):
        raise stripe.APIConnectionError("stripe is unreachable")

    monkeypatch.setattr(stripe.checkout.Session, "create", fake_create)

    response = client.post("/payments/checkout-session", json={"device_id": "device_abc"})

    assert response.status_code == 502
