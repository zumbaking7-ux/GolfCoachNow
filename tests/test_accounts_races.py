"""What happens when two sign ins collide.

Both cases here are the same shape: a lookup says the row is absent, another
request creates it, and this one loses the unique index. Real, but impossible
to hit reliably by timing a test, so each one forces the collision by making
the lookup lie once - exactly what a concurrent request would cause.

The reason these matter is not the collision itself. It is what a naive
recovery destroys. Rolling the whole transaction back to survive a duplicate
also throws away the code being marked used, which leaves that code replayable.
"""

import pytest
from conftest import load_event, post_webhook  # noqa: F401  (fixtures)
from fastapi.testclient import TestClient

from payments import accounts, auth_routes
from payments.accounts_models import AuthToken, LoginCode, User, UserDevice
from payments.rate_limit import SlidingWindowLimiter

EMAIL = "racer@example.com"


@pytest.fixture(autouse=True)
def unlimited(monkeypatch):
    monkeypatch.setattr(auth_routes, "_by_caller", SlidingWindowLimiter(1000, 60))
    monkeypatch.setattr(auth_routes, "_by_email", SlidingWindowLimiter(1000, 60))


@pytest.fixture
def sent(monkeypatch) -> list[tuple[str, str]]:
    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(
        auth_routes,
        "send_login_code",
        lambda email, code: captured.append((email, code)) or True,
    )
    return captured


def blind_once(monkeypatch, target: str):
    """Make a lookup return None the first time, whatever the database says.

    That is precisely what a request racing another one sees: it checks, finds
    nothing, and by the time it inserts the row exists.
    """
    real = getattr(accounts, target)
    calls = {"n": 0}

    def lying(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return real(*args, **kwargs)

    monkeypatch.setattr(accounts, target, lying)


def get_code(client: TestClient, sent, email=EMAIL, device_id=None) -> str:
    body = {"email": email}
    if device_id:
        body["device_id"] = device_id
    client.post("/auth/request-code", json=body)
    return sent[-1][1]


def test_losing_the_race_to_create_a_user_still_burns_the_code(
    client, sent, db_session, monkeypatch
):
    """The bug this guards against.

    Recovering from the duplicate with a plain rollback would also undo
    used_at, and the code would still work afterwards. It must not.
    """
    db_session.add(User(email=EMAIL))
    db_session.commit()

    code = get_code(client, sent)
    blind_once(monkeypatch, "_user_by_email")

    first = client.post("/auth/verify-code", json={"email": EMAIL, "code": code})
    replay = client.post("/auth/verify-code", json={"email": EMAIL, "code": code})

    assert first.status_code == 200
    assert replay.status_code == 401

    used = db_session.query(LoginCode).order_by(LoginCode.id.desc()).first()
    db_session.refresh(used)
    assert used.used_at is not None


def test_losing_that_race_does_not_create_a_second_account(
    client, sent, db_session, monkeypatch
):
    db_session.add(User(email=EMAIL))
    db_session.commit()

    code = get_code(client, sent)
    blind_once(monkeypatch, "_user_by_email")
    client.post("/auth/verify-code", json={"email": EMAIL, "code": code})

    assert db_session.query(User).filter(User.email == EMAIL).count() == 1


def test_losing_the_race_to_link_a_device_is_not_a_500(
    client, sent, db_session, monkeypatch
):
    """An uncaught unique violation here would fail the whole sign in."""
    owner = User(email="owner@example.com")
    db_session.add(owner)
    db_session.commit()
    db_session.add(UserDevice(user_id=owner.id, device_id="contested"))
    db_session.commit()

    code = get_code(client, sent, device_id="contested")
    blind_once(monkeypatch, "_device_link")

    response = client.post(
        "/auth/verify-code",
        json={"email": EMAIL, "code": code, "device_id": "contested"},
    )

    assert response.status_code == 200
    assert db_session.query(UserDevice).filter(
        UserDevice.device_id == "contested"
    ).count() == 1


def test_a_signed_in_session_survives_a_device_race(
    client, sent, db_session, monkeypatch
):
    """Losing the device race must not cost the token either."""
    owner = User(email="owner@example.com")
    db_session.add(owner)
    db_session.commit()
    db_session.add(UserDevice(user_id=owner.id, device_id="contested"))
    db_session.commit()

    code = get_code(client, sent, device_id="contested")
    blind_once(monkeypatch, "_device_link")

    token = client.post(
        "/auth/verify-code",
        json={"email": EMAIL, "code": code, "device_id": "contested"},
    ).json()["token"]

    assert db_session.query(AuthToken).count() == 1
    assert (
        client.get(
            "/payments/unlock-status", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )
