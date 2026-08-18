"""Share With a Friend, and Connect With the Founder.

These two endpoints take an address a stranger typed and send mail to it, which
makes them the easiest thing in the service to abuse. Most of what is covered
here is that: who the mail actually reaches, how often anyone can trigger it,
and the fact that both endpoints answer identically whatever happened, so
neither becomes a way of testing which addresses exist.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from payments import contact_routes
from payments.config import settings
from payments.contact_routes import router as contact_router

SHARE_URL = "https://golfcoachnow.example/get"
FRIEND = "friend@example.com"


@pytest.fixture
def sent(monkeypatch):
    """Capture what would have gone out, instead of sending it."""
    captured = []

    def fake_send(to, subject, text, reply_to=""):
        captured.append({"to": to, "subject": subject, "text": text, "reply_to": reply_to})
        return True

    monkeypatch.setattr(contact_routes, "send_email", fake_send)
    return captured


@pytest.fixture(autouse=True)
def fresh_limits():
    """These limiters are module level, so one test would otherwise spend
    another's allowance and the failure would move as tests are reordered."""
    contact_routes._by_caller._hits.clear()
    contact_routes._by_recipient._hits.clear()
    yield
    contact_routes._by_caller._hits.clear()
    contact_routes._by_recipient._hits.clear()


@pytest.fixture
def sharing_on(monkeypatch):
    monkeypatch.setattr(settings, "app_share_url", SHARE_URL)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(contact_router)
    return TestClient(app)


# --- Share with a friend --------------------------------------------------


def test_the_invite_goes_to_the_friend_and_nobody_else(client, sent, sharing_on):
    """The founder was explicit: this does not come to him.

    Getting this backwards would mail the founder every time somebody tried to
    tell a friend about the app.
    """
    response = client.post("/share/invite", json={"email": FRIEND, "device_id": "d1"})

    assert response.status_code == 202
    assert len(sent) == 1
    assert sent[0]["to"] == FRIEND
    assert sent[0]["to"] != settings.founder_email


def test_the_invite_carries_the_link(client, sent, sharing_on):
    client.post("/share/invite", json={"email": FRIEND})
    assert SHARE_URL in sent[0]["text"]


def test_the_invite_tells_the_recipient_they_can_ignore_it(client, sent, sharing_on):
    """Anyone can type anyone's address into this form."""
    client.post("/share/invite", json={"email": FRIEND})
    assert "ignore" in sent[0]["text"].lower()


def test_sharing_is_closed_until_there_is_a_link_to_send(client, sent, monkeypatch):
    """An empty share url must not mean mailing people a broken link."""
    monkeypatch.setattr(settings, "app_share_url", "")

    response = client.post("/share/invite", json={"email": FRIEND})

    assert response.status_code == 503
    assert sent == []


def test_a_typo_is_rejected_before_anything_is_sent(client, sent, sharing_on):
    response = client.post("/share/invite", json={"email": "not-an-address"})

    assert response.status_code == 422
    assert sent == []


def test_one_address_cannot_be_mailed_over_and_over(client, sent, sharing_on):
    """Otherwise this is a way to send somebody unlimited mail they never asked for."""
    limit = settings.share_rate_limit_requests
    for _ in range(limit):
        assert client.post("/share/invite", json={"email": FRIEND}).status_code == 202

    blocked = client.post("/share/invite", json={"email": FRIEND})

    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert len(sent) == limit


def test_one_caller_cannot_mail_the_whole_world(client, sent, sharing_on):
    """Different address each time, so only the per-caller limit can stop this."""
    limit = settings.share_rate_limit_requests
    for i in range(limit):
        assert client.post("/share/invite", json={"email": f"f{i}@example.com"}).status_code == 202

    blocked = client.post("/share/invite", json={"email": "one-more@example.com"})

    assert blocked.status_code == 429
    assert len(sent) == limit


# --- Connect with the founder ---------------------------------------------


def test_the_message_reaches_the_founder(client, sent):
    response = client.post(
        "/connect/founder", json={"message": "Love the app", "device_id": "d9"}
    )

    assert response.status_code == 202
    assert sent[0]["to"] == settings.founder_email
    assert "Love the app" in sent[0]["text"]


def test_the_founder_can_reply_when_an_address_was_given(client, sent):
    client.post(
        "/connect/founder", json={"message": "Question", "email": "Golfer@Example.com "}
    )

    assert sent[0]["reply_to"] == "golfer@example.com"


def test_feedback_does_not_require_an_address(client, sent):
    """Demanding an email would stop somebody sending feedback at all."""
    response = client.post("/connect/founder", json={"message": "Anonymous thought"})

    assert response.status_code == 202
    assert sent[0]["reply_to"] == ""


def test_the_device_is_named_so_support_can_follow_it_up(client, sent):
    client.post("/connect/founder", json={"message": "Stuck", "device_id": "device-77"})
    assert "device-77" in sent[0]["text"]


def test_an_empty_message_is_not_delivered(client, sent):
    assert client.post("/connect/founder", json={"message": ""}).status_code == 422
    assert sent == []


def test_an_enormous_message_is_refused(client, sent):
    huge = "x" * (contact_routes.MAX_MESSAGE_LENGTH + 1)

    assert client.post("/connect/founder", json={"message": huge}).status_code == 422
    assert sent == []


def test_a_malformed_reply_address_is_rejected(client, sent):
    response = client.post(
        "/connect/founder", json={"message": "Hello", "email": "nope"}
    )

    assert response.status_code == 422
    assert sent == []


def test_one_person_cannot_flood_the_founder(client, sent):
    limit = settings.share_rate_limit_requests
    for _ in range(limit):
        assert client.post("/connect/founder", json={"message": "hi"}).status_code == 202

    assert client.post("/connect/founder", json={"message": "hi"}).status_code == 429


# --- The promise both endpoints make --------------------------------------


def test_a_failing_provider_still_looks_like_success(client, monkeypatch, sharing_on):
    """The golfer must not see a 500 because a mail provider is having a bad day.

    Sending happens after the response for the same reason. The endpoint's job
    is to accept the request, not to wait on Resend.
    """
    monkeypatch.setattr(contact_routes, "send_email", lambda *a, **k: False)

    assert client.post("/share/invite", json={"email": FRIEND}).status_code == 202
    assert client.post("/connect/founder", json={"message": "hi"}).status_code == 202
