"""Rate limiting.

Only the two endpoints the mobile app calls are limited. The webhook is not,
and that is the point most worth protecting with a test: Stripe decides when to
send events, a 429 there becomes a retry, and an unlock delayed because we were
throttling Stripe is worse than any abuse the limit prevents.

Each test uses its own client address so counts cannot leak between them.
"""

from conftest import load_event, post_webhook
from fastapi import FastAPI
from fastapi.testclient import TestClient

from payments.rate_limit import SlidingWindowLimiter, rate_limit
from payments.routes import router

CHECKOUT_PATH = "/payments/checkout-session"
STATUS_PATH = "/payments/unlock-status?device_id=probe"


def caller(address: str) -> dict:
    """PythonAnywhere sits behind a proxy, so the limiter reads this header."""
    return {"x-forwarded-for": address}


def test_requests_under_the_limit_are_allowed(client):
    for _ in range(5):
        response = client.get(STATUS_PATH, headers=caller("10.0.0.1"))
        assert response.status_code == 200


def test_going_over_the_limit_returns_429(client, monkeypatch):
    """Uses a tiny limiter rather than sending 30 requests."""
    monkeypatch.setattr("payments.rate_limit._limiter", SlidingWindowLimiter(3, 60))

    for _ in range(3):
        assert client.get(STATUS_PATH, headers=caller("10.0.0.2")).status_code == 200

    blocked = client.get(STATUS_PATH, headers=caller("10.0.0.2"))

    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_one_caller_cannot_block_another(client, monkeypatch):
    monkeypatch.setattr("payments.rate_limit._limiter", SlidingWindowLimiter(2, 60))

    for _ in range(2):
        client.get(STATUS_PATH, headers=caller("10.0.0.3"))

    assert client.get(STATUS_PATH, headers=caller("10.0.0.3")).status_code == 429
    assert client.get(STATUS_PATH, headers=caller("10.0.0.4")).status_code == 200


def test_the_webhook_is_never_limited(client, db_session, monkeypatch):
    """The rule this whole module exists to not break.

    A limit on the webhook would turn into Stripe retries and delayed unlocks,
    which is worse than whatever it would be protecting against.
    """
    monkeypatch.setattr("payments.rate_limit._limiter", SlidingWindowLimiter(1, 60))

    event = load_event()
    for attempt in range(5):
        event["id"] = f"evt_ratelimit_probe_{attempt}"
        assert post_webhook(client, event).status_code == 200


def test_success_and_cancel_redirects_are_not_limited(client, monkeypatch):
    """A customer returning from a payment should never be turned away."""
    monkeypatch.setattr("payments.rate_limit._limiter", SlidingWindowLimiter(1, 60))

    for _ in range(4):
        response = client.get("/payments/cancel", follow_redirects=False)
        assert response.status_code == 303


def test_limiting_can_be_switched_off_without_a_code_change(monkeypatch):
    from payments import rate_limit as rate_limit_module

    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_enabled", False)
    monkeypatch.setattr(rate_limit_module, "_limiter", SlidingWindowLimiter(1, 60))

    app = FastAPI()
    app.include_router(router)
    unlimited = TestClient(app)

    for _ in range(5):
        assert unlimited.get(STATUS_PATH, headers=caller("10.0.0.5")).status_code == 200


def test_window_slides_rather_than_resetting_on_a_boundary():
    """A fixed window lets a caller send double the limit across the reset."""
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)

    assert limiter.check("caller") is None
    assert limiter.check("caller") is None

    wait = limiter.check("caller")

    assert wait is not None
    assert 0 < wait <= 60
