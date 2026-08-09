"""The success redirect.

This endpoint is a public URL that anybody can open with anything in the query
string. It unlocks only what Stripe confirms, and it hands the browser back to
the app afterwards.
"""

import stripe
from conftest import load_event, post_webhook
from payments.models import Unlock

DEEP_LINK = "golfcoachnow://payment-success"


def paid_session(**overrides) -> dict:
    """A Checkout Session as Stripe returns it from retrieve()."""
    session = dict(load_event()["data"]["object"])
    session.update(overrides)
    return session


def patch_retrieve(monkeypatch, session: dict) -> None:
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", lambda _id: session)


def test_paid_session_unlocks_and_redirects_to_the_app(client, db_session, monkeypatch):
    patch_retrieve(monkeypatch, paid_session())

    response = client.get(
        "/payments/success?session_id=cs_test_a1b2c3d4e5f6", follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == DEEP_LINK
    assert db_session.query(Unlock).count() == 1


def test_unpaid_session_redirects_but_does_not_unlock(client, db_session, monkeypatch):
    """The redirect still happens.

    The app never reads its unlock state from the deep link, so there is no
    point sending a different one. It asks /unlock-status and gets false.
    """
    patch_retrieve(monkeypatch, paid_session(payment_status="unpaid"))

    response = client.get(
        "/payments/success?session_id=cs_test_a1b2c3d4e5f6", follow_redirects=False
    )

    assert response.status_code == 303
    assert db_session.query(Unlock).count() == 0


def test_unknown_session_id_returns_400(client, db_session, monkeypatch):
    """Someone typing the URL by hand gets nothing."""

    def fake_retrieve(_id):
        raise stripe.InvalidRequestError("no such checkout session", param="session_id")

    monkeypatch.setattr(stripe.checkout.Session, "retrieve", fake_retrieve)

    response = client.get("/payments/success?session_id=made_up", follow_redirects=False)

    assert response.status_code == 400
    assert db_session.query(Unlock).count() == 0


def test_success_redirect_then_webhook_produce_one_unlock(client, db_session, monkeypatch):
    """Both paths run for the same payment, because both always run.

    The redirect fires as soon as the customer's browser comes back. The
    webhook arrives independently. Whichever lands second must not create a
    second unlock.
    """
    patch_retrieve(monkeypatch, paid_session())

    client.get("/payments/success?session_id=cs_test_a1b2c3d4e5f6", follow_redirects=False)
    post_webhook(client, load_event())

    unlocks = db_session.query(Unlock).all()
    assert len(unlocks) == 1
    assert unlocks[0].source == "success_redirect"


def test_webhook_then_success_redirect_produce_one_unlock(client, db_session, monkeypatch):
    """The same race, arriving in the other order."""
    patch_retrieve(monkeypatch, paid_session())

    post_webhook(client, load_event())
    client.get("/payments/success?session_id=cs_test_a1b2c3d4e5f6", follow_redirects=False)

    unlocks = db_session.query(Unlock).all()
    assert len(unlocks) == 1
    assert unlocks[0].source == "webhook"


def test_cancel_redirects_to_the_app(client):
    response = client.get("/payments/cancel", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "golfcoachnow://payment-cancelled"
