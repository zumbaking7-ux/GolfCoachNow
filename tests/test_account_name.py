"""What the app calls somebody on the home screen.

The greeting is "Hi <name>. What would you like to learn today?", specified
verbatim by the client. Before this the apps derived a name from the email
address, so a golfer at waleflutter@gmail.com was greeted as "waleflutter".

The name lives on the account rather than on the phone. That is the whole
point: it has to survive a reinstall and follow the person to a second device,
which is exactly what a locally stored name would not do.
"""

import pytest
from fastapi.testclient import TestClient

from payments import auth_routes
from payments.accounts_models import NAME_LENGTH, User
from payments.rate_limit import SlidingWindowLimiter

from tests.conftest import build_payments_app

EMAIL = "golfer@example.com"


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_payments_app())


@pytest.fixture(autouse=True)
def unlimited(monkeypatch):
    """Rate limits have their own tests. Here they are noise."""
    monkeypatch.setattr(auth_routes, "_by_caller", SlidingWindowLimiter(1000, 60))
    monkeypatch.setattr(auth_routes, "_by_email", SlidingWindowLimiter(1000, 60))


@pytest.fixture
def sent(monkeypatch) -> list:
    captured = []
    monkeypatch.setattr(
        auth_routes, "send_login_code",
        lambda email, code: captured.append((email, code)) or True,
    )
    return captured


def sign_in(client, sent, name=None, email=EMAIL):
    """Run the whole flow, optionally supplying a name, and return the body."""
    client.post("/auth/request-code", json={"email": email})
    body = {"email": email, "code": sent[-1][1]}
    if name is not None:
        body["name"] = name
    response = client.post("/auth/verify-code", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def stored_name(db_session, email=EMAIL):
    return db_session.query(User).filter(User.email == email).one().name


# --- storing it -------------------------------------------------------------


def test_a_name_given_at_sign_in_comes_back(client, sent):
    assert sign_in(client, sent, name="John")["name"] == "John"


def test_the_name_is_kept_on_the_account(client, sent, db_session):
    sign_in(client, sent, name="John")
    assert stored_name(db_session) == "John"


def test_it_is_still_there_on_the_next_sign_in(client, sent):
    """The reason this is server side at all.

    A name stored on the phone would be gone after a reinstall, and would never
    appear on a second device. This proves it survives without being resent.
    """
    sign_in(client, sent, name="John")
    assert sign_in(client, sent)["name"] == "John"


# --- changing it ------------------------------------------------------------


def test_a_new_name_replaces_the_old_one(client, sent, db_session):
    """Somebody who typed a nickname first can correct it by signing in again."""
    sign_in(client, sent, name="Johnny")
    sign_in(client, sent, name="John McGraw")
    assert stored_name(db_session) == "John McGraw"


def test_signing_in_without_a_name_does_not_erase_it(client, sent, db_session):
    """An older app build sends no name at all, and must not wipe it."""
    sign_in(client, sent, name="John")
    sign_in(client, sent)
    assert stored_name(db_session) == "John"


def test_a_blank_name_does_not_erase_it_either(client, sent, db_session):
    """An empty field submitted by accident is not an instruction to forget."""
    sign_in(client, sent, name="John")
    sign_in(client, sent, name="   ")
    assert stored_name(db_session) == "John"


# --- the absence of one -----------------------------------------------------


def test_no_name_is_a_clean_null_rather_than_an_empty_string(client, sent):
    """Everyone who signed in before this column existed is in this state.

    Null tells the apps to use the generic greeting. An empty string would
    render as "Hi ." on the home screen, which is worse than not personalising
    at all.
    """
    assert sign_in(client, sent)["name"] is None


# --- what gets stored -------------------------------------------------------


def test_surrounding_whitespace_is_trimmed(client, sent, db_session):
    sign_in(client, sent, name="  John  ")
    assert stored_name(db_session) == "John"


def test_an_over_long_name_is_refused_rather_than_silently_cut(client, sent):
    """The greeting is one line on a phone, so this is bounded at the edge."""
    client.post("/auth/request-code", json={"email": EMAIL})
    response = client.post(
        "/auth/verify-code",
        json={"email": EMAIL, "code": sent[-1][1], "name": "x" * (NAME_LENGTH + 1)},
    )
    assert response.status_code == 422


def test_a_name_at_the_limit_is_accepted(client, sent, db_session):
    sign_in(client, sent, name="x" * NAME_LENGTH)
    assert stored_name(db_session) == "x" * NAME_LENGTH


# --- it must not become a way in --------------------------------------------


def test_a_name_cannot_sign_anyone_in_on_its_own(client, sent):
    """Supplying a name with a wrong code must still fail, and store nothing."""
    client.post("/auth/request-code", json={"email": EMAIL})
    response = client.post(
        "/auth/verify-code",
        json={"email": EMAIL, "code": "000000", "name": "John"},
    )
    assert response.status_code == 401
