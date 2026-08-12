"""Signing in, and what it gives you.

The point of accounts is restore purchase: a payment recorded against a phone
someone no longer owns still has to be findable. Most of what follows is about
the ways a six digit code could be abused if the surrounding rules were not
there.

Codes never leave the process in these tests. The sender is replaced with a
recorder, which is also the only way to read a code - the database stores only
its hash.
"""

from datetime import datetime, timedelta, timezone

import pytest
from conftest import DEVICE_ID
from fastapi.testclient import TestClient

from payments import auth_routes
from payments.accounts_models import LoginCode
from payments.config import settings
from payments.models import Unlock
from payments.rate_limit import SlidingWindowLimiter

EMAIL = "golfer@example.com"


@pytest.fixture(autouse=True)
def unlimited(monkeypatch):
    """Rate limits get their own tests. Everywhere else they are noise."""
    monkeypatch.setattr(auth_routes, "_by_caller", SlidingWindowLimiter(1000, 60))
    monkeypatch.setattr(auth_routes, "_by_email", SlidingWindowLimiter(1000, 60))


@pytest.fixture
def sent(monkeypatch) -> list[tuple[str, str]]:
    """Capture what would have been emailed."""
    captured: list[tuple[str, str]] = []

    def recorder(email: str, code: str) -> bool:
        captured.append((email, code))
        return True

    monkeypatch.setattr(auth_routes, "send_login_code", recorder)
    return captured


def ask_for_code(client: TestClient, email: str = EMAIL, device_id=None):
    body = {"email": email}
    if device_id:
        body["device_id"] = device_id
    return client.post("/auth/request-code", json=body)


def sign_in(client: TestClient, sent, email: str = EMAIL, device_id=None) -> str:
    """Complete the whole flow and return the token."""
    ask_for_code(client, email, device_id)
    code = sent[-1][1]
    body = {"email": email, "code": code}
    if device_id:
        body["device_id"] = device_id
    response = client.post("/auth/verify-code", json=body)
    assert response.status_code == 200, response.text
    return response.json()["token"]


# --- requesting a code ------------------------------------------------------


def test_a_code_is_sent(client, sent):
    response = ask_for_code(client)

    assert response.status_code == 202
    assert len(sent) == 1
    assert sent[0][0] == EMAIL
    assert len(sent[0][1]) == settings.login_code_length
    assert sent[0][1].isdigit()


def test_the_answer_is_the_same_whether_the_account_exists(client, sent):
    """Otherwise this endpoint tells you which of someone's customers are here."""
    first = ask_for_code(client, "brand-new@example.com")
    sign_in(client, sent)
    second = ask_for_code(client, EMAIL)

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()


def test_the_address_is_normalised(client, sent, db_session):
    """One person, not three accounts, from capitals and stray spaces."""
    sign_in(client, sent, email="  Golfer@Example.COM  ")

    stored = db_session.query(LoginCode).all()
    assert {row.email for row in stored} == {EMAIL}


def test_rubbish_addresses_are_rejected(client, sent):
    for bad in ["not-an-email", "no@domain", "spaces in@example.com", "@example.com"]:
        response = ask_for_code(client, bad)
        assert response.status_code == 422, bad
    assert sent == []


def test_asking_again_retires_the_previous_code(client, sent):
    """Every code ever requested staying valid is a much larger target."""
    ask_for_code(client)
    first_code = sent[-1][1]
    ask_for_code(client)
    second_code = sent[-1][1]

    assert client.post(
        "/auth/verify-code", json={"email": EMAIL, "code": first_code}
    ).status_code == 401
    assert client.post(
        "/auth/verify-code", json={"email": EMAIL, "code": second_code}
    ).status_code == 200


# --- verifying --------------------------------------------------------------


def test_the_right_code_returns_a_token(client, sent):
    token = sign_in(client, sent)

    assert isinstance(token, str)
    assert len(token) > 30


def test_the_wrong_code_is_rejected(client, sent):
    ask_for_code(client)

    response = client.post(
        "/auth/verify-code", json={"email": EMAIL, "code": "000000"}
    )

    assert response.status_code == 401


def test_a_code_works_only_once(client, sent):
    ask_for_code(client)
    code = sent[-1][1]

    assert client.post(
        "/auth/verify-code", json={"email": EMAIL, "code": code}
    ).status_code == 200
    assert client.post(
        "/auth/verify-code", json={"email": EMAIL, "code": code}
    ).status_code == 401


def test_guessing_is_capped(client, sent, db_session):
    """Six digits is a million tries, which a script does in seconds.

    The cap is what makes the code space big enough to matter, so it is worth
    proving the real code stops working once the budget is spent.
    """
    ask_for_code(client)
    real_code = sent[-1][1]

    for _ in range(settings.login_code_max_attempts):
        client.post("/auth/verify-code", json={"email": EMAIL, "code": "000000"})

    response = client.post(
        "/auth/verify-code", json={"email": EMAIL, "code": real_code}
    )

    assert response.status_code == 401


def test_an_expired_code_is_rejected(client, sent, db_session):
    ask_for_code(client)
    code = sent[-1][1]

    row = db_session.query(LoginCode).order_by(LoginCode.id.desc()).first()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = client.post("/auth/verify-code", json={"email": EMAIL, "code": code})

    assert response.status_code == 401


def test_verifying_without_asking_first_is_rejected(client):
    response = client.post(
        "/auth/verify-code", json={"email": EMAIL, "code": "123456"}
    )

    assert response.status_code == 401


def test_every_failure_looks_identical(client, sent, db_session):
    """Different messages would say which addresses have accounts."""
    never_asked = client.post(
        "/auth/verify-code", json={"email": "nobody@example.com", "code": "123456"}
    )

    ask_for_code(client)
    wrong = client.post("/auth/verify-code", json={"email": EMAIL, "code": "000000"})

    assert never_asked.status_code == wrong.status_code == 401
    assert never_asked.json() == wrong.json()


# --- what a token is for ----------------------------------------------------


def test_a_token_answers_unlock_status(client, sent):
    token = sign_in(client, sent, device_id="device_a")

    response = client.get(
        "/payments/unlock-status", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["unlocked"] is False


def test_restore_purchase_across_a_reinstall(client, sent, db_session):
    """The whole reason accounts exist.

    Someone pays on one phone, deletes the app, and comes back on a device the
    payment was never recorded against. Signing in has to find it.
    """
    db_session.add(
        Unlock(
            device_id="old_phone",
            checkout_session_id="cs_live_old",
            amount_total=1499,
            currency="usd",
            status="paid",
            source="webhook",
        )
    )
    db_session.commit()

    sign_in(client, sent, device_id="old_phone")
    token_on_new_phone = sign_in(client, sent, device_id="new_phone")

    by_device = client.get("/payments/unlock-status?device_id=new_phone")
    by_account = client.get(
        "/payments/unlock-status",
        headers={"Authorization": f"Bearer {token_on_new_phone}"},
    )

    assert by_device.json()["unlocked"] is False
    assert by_account.json()["unlocked"] is True


def test_one_device_belongs_to_one_account(client, sent, db_session):
    """Otherwise a single purchase unlocks every account it is shared with."""
    db_session.add(
        Unlock(
            device_id="shared_phone",
            checkout_session_id="cs_live_shared",
            amount_total=1499,
            currency="usd",
            status="paid",
            source="webhook",
        )
    )
    db_session.commit()

    first = sign_in(client, sent, email="one@example.com", device_id="shared_phone")
    second = sign_in(client, sent, email="two@example.com", device_id="shared_phone")

    still_first = client.get(
        "/payments/unlock-status", headers={"Authorization": f"Bearer {first}"}
    )
    now_second = client.get(
        "/payments/unlock-status", headers={"Authorization": f"Bearer {second}"}
    )

    assert still_first.json()["unlocked"] is False
    assert now_second.json()["unlocked"] is True


def test_signing_out_kills_the_token(client, sent):
    token = sign_in(client, sent, device_id="device_a")
    headers = {"Authorization": f"Bearer {token}"}

    assert client.post("/auth/sign-out", headers=headers).status_code == 204

    after = client.get("/payments/unlock-status", headers=headers)
    assert after.status_code == 422


def test_a_made_up_token_is_ignored(client):
    response = client.get(
        "/payments/unlock-status?device_id=some_device",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 200
    assert response.json()["device_id"] == "some_device"


# --- the old path must not change -------------------------------------------


def test_the_device_path_still_works_untouched(client):
    """The shipped app sends no token. It must behave exactly as before.

    The three subscription fields are additions, not changes. `unlocked` still
    means the same thing and still comes back in the same place, which is the
    part the installed app reads. Both clients ignore keys they do not know -
    Android sets ignoreUnknownKeys explicitly and Swift's Decodable does it by
    default - so the extra fields cost the shipped version nothing.
    """
    response = client.get(f"/payments/unlock-status?device_id={DEVICE_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == DEVICE_ID
    assert body["unlocked"] is False
    assert body["unlocked_at"] is None
    assert body["plan"] == "none"


def test_neither_token_nor_device_is_a_422(client):
    assert client.get("/payments/unlock-status").status_code == 422


# --- rate limiting ----------------------------------------------------------


def test_one_caller_cannot_email_the_world(client, sent, monkeypatch):
    monkeypatch.setattr(auth_routes, "_by_caller", SlidingWindowLimiter(2, 300))

    ask_for_code(client, "a@example.com")
    ask_for_code(client, "b@example.com")
    blocked = ask_for_code(client, "c@example.com")

    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert len(sent) == 2


def test_the_world_cannot_email_one_person(client, sent, monkeypatch):
    """A per caller limit alone does not stop this, which is why there are two."""
    monkeypatch.setattr(auth_routes, "_by_email", SlidingWindowLimiter(2, 300))

    ask_for_code(client, EMAIL)
    ask_for_code(client, EMAIL)
    blocked = ask_for_code(client, EMAIL)

    assert blocked.status_code == 429
    assert len(sent) == 2
