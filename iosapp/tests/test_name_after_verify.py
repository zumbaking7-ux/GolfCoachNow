"""Naming an account after signing in, rather than during it.

The obvious way to stop asking a returning golfer for a name they already gave
is to have the app find out, before the code is checked, whether that address
has one. That is also a way of asking the server which email addresses have
accounts, and it will answer every time.

So the name is set afterwards, over an authenticated call. A new golfer sees
the question once; an existing one never sees it. Nothing is leaked, because
nothing is answered until a valid code has been presented.
"""

import pytest
from fastapi.testclient import TestClient

from payments.accounts import request_login_code
from payments.db import SessionFactory


def code_for(email):
    with SessionFactory() as session:
        return request_login_code(session, email)


def sign_in(client, email, device="name_device", name=None):
    body = {"email": email, "code": code_for(email), "device_id": device}
    if name is not None:
        body["name"] = name
    return client.post("/auth/verify-code", json=body)


def auth(token):
    return {"Authorization": "Bearer %s" % token}


# --- What the app needs in order to decide whether to ask -----------------


def test_a_new_account_comes_back_with_no_name(client):
    body = sign_in(client, "unnamed@example.com").json()
    assert body["token"]
    assert body["name"] is None


def test_naming_the_account_sticks(client):
    token = sign_in(client, "namer@example.com").json()["token"]

    named = client.post("/auth/name", json={"name": "John"}, headers=auth(token))
    assert named.status_code == 200
    assert named.json()["name"] == "John"

    again = sign_in(client, "namer@example.com")
    assert again.json()["name"] == "John"


def test_a_returning_golfer_is_never_asked_again(client):
    """The whole point of the change. Signing in a second time comes back with
    the name already attached, so the app has nothing to ask for."""
    token = sign_in(client, "returning@example.com").json()["token"]
    client.post("/auth/name", json={"name": "Wale"}, headers=auth(token))

    for _ in range(3):
        assert sign_in(client, "returning@example.com").json()["name"] == "Wale"


def test_a_name_survives_signing_in_on_another_device(client):
    token = sign_in(client, "roaming@example.com", device="phone_one").json()["token"]
    client.post("/auth/name", json={"name": "Roamer"}, headers=auth(token))

    on_the_tablet = sign_in(client, "roaming@example.com", device="tablet_two")
    assert on_the_tablet.json()["name"] == "Roamer"


# --- It is a real endpoint, so it is guarded like one ---------------------


def test_naming_needs_a_token(client):
    assert client.post("/auth/name", json={"name": "Nobody"}).status_code == 401


def test_a_dead_token_cannot_name_anybody(client):
    token = sign_in(client, "revoked-namer@example.com").json()["token"]
    client.post("/auth/sign-out", headers=auth(token))

    refused = client.post("/auth/name", json={"name": "Ghost"}, headers=auth(token))
    assert refused.status_code == 401


def test_an_empty_name_is_refused_rather_than_stored(client):
    token = sign_in(client, "blank@example.com").json()["token"]
    assert client.post(
        "/auth/name", json={"name": ""}, headers=auth(token)
    ).status_code == 422


def test_whitespace_is_trimmed_rather_than_kept(client):
    token = sign_in(client, "spaces@example.com").json()["token"]
    named = client.post(
        "/auth/name", json={"name": "  John  "}, headers=auth(token)
    )
    assert named.json()["name"] == "John"


def test_a_name_of_only_spaces_leaves_the_account_alone(client):
    """Trimming turns it into nothing, and nothing is not a name. The stored
    value must not be replaced with an empty string, which would render as a
    blank greeting rather than a generic one."""
    token = sign_in(client, "spaces-only@example.com").json()["token"]
    client.post("/auth/name", json={"name": "Real"}, headers=auth(token))

    client.post("/auth/name", json={"name": "     "}, headers=auth(token))
    assert sign_in(client, "spaces-only@example.com").json()["name"] == "Real"


def test_a_long_name_is_truncated_not_rejected(client):
    token = sign_in(client, "long@example.com").json()["token"]
    stored = client.post(
        "/auth/name", json={"name": "A" * 80}, headers=auth(token)
    ).json()["name"]
    assert len(stored) == 80


# --- The old path still works, for apps already in someone's hands -------


def test_a_name_sent_at_sign_in_is_still_accepted(client):
    """Older builds send it with the code. They should keep working rather
    than quietly losing the name."""
    body = sign_in(client, "oldclient@example.com", name="Legacy").json()
    assert body["name"] == "Legacy"
