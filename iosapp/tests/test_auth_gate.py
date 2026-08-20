"""The sign-in gate on the analysis path.

Until now anybody who knew the url could post a video and consume analysis:
`/upload` took a `device_id` the caller supplied and checked nothing else. The
paywall rested on a value the client chose.

These tests pin the gate and, as importantly, the seam either side of it:

    no token, first rep      -> allowed, because of the launch allowance
    no token, second rep     -> 401 sign_in_required
    signed in                -> allowed past the allowance
    daily limit reached      -> 403, not 401

That last pair is the one worth being careful about. A golfer who has used
their free reps must be told to subscribe, and a stranger must be told to sign
in, and the apps decide which screen to show from the status code alone.
"""

import io
import os

import pytest
from fastapi.testclient import TestClient

import server
import video_analyzer
from payments.accounts import request_login_code, verify_login_code
from payments.config import settings
from payments.db import SessionFactory

PLAUSIBLE_CLIP = os.urandom(video_analyzer.MIN_FILE_BYTES * 2)


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture
def readable_clip(monkeypatch):
    """Pin decoding, so these tests are about the gate and nothing else."""
    monkeypatch.setattr(
        video_analyzer,
        "_extract_metadata",
        lambda _: {
            "duration": 12.0,
            "width": 1080,
            "height": 1920,
            "file_size": 4_000_000,
            "probed": True,
        },
    )


def upload(client, device, headers=None, module="swing"):
    return client.post(
        "/upload",
        params={"module": module, "device_id": device},
        files={"file": ("clip.mp4", io.BytesIO(PLAUSIBLE_CLIP), "video/mp4")},
        headers=headers or {},
    )


def token_for(email="gate@example.com", device="gate_device"):
    with SessionFactory() as session:
        code = request_login_code(session, email)
        return verify_login_code(session, email, code, device, "Tester").token


def headers_for(token):
    return {"Authorization": "Bearer %s" % token}


# --- The launch allowance -------------------------------------------------


def test_a_stranger_gets_one_rep(client, readable_clip):
    """A journalist handed a link sees the product work before being asked
    for anything. That is the whole reason the allowance exists."""
    assert upload(client, "stranger_one").status_code == 200


def test_the_second_rep_asks_them_to_sign_in(client, readable_clip):
    device = "stranger_two"
    assert upload(client, device).status_code == 200

    second = upload(client, device)
    assert second.status_code == 401
    assert second.json()["detail"]["error"] == "sign_in_required"


def test_the_allowance_counts_every_mode_not_each_one(client, readable_clip):
    """One rep in total, not one per mode. Otherwise a stranger gets three."""
    device = "stranger_modes"
    assert upload(client, device, module="swing").status_code == 200
    assert upload(client, device, module="putt").status_code == 401


def test_closing_the_allowance_gates_the_very_first_rep(
    client, readable_clip, monkeypatch
):
    """UNGATED_REPS=0 is how this closes after the press coverage, and it has
    to work without a code change or a release."""
    monkeypatch.setattr(settings, "ungated_reps", 0)

    refused = upload(client, "stranger_closed")
    assert refused.status_code == 401
    assert refused.json()["detail"]["error"] == "sign_in_required"


# --- Signing in gets you through ------------------------------------------


def test_a_signed_in_golfer_goes_past_the_allowance(client, readable_clip):
    device = "member_device"
    headers = headers_for(token_for("member@example.com", device))

    for _ in range(2):
        assert upload(client, device, headers=headers).status_code == 200


def test_a_revoked_token_is_not_a_token(client, readable_clip):
    """Signing out has to actually close the door."""
    from payments.accounts import revoke_token

    device = "revoked_device"
    token = token_for("revoked@example.com", device)

    assert upload(client, device, headers=headers_for(token)).status_code == 200

    with SessionFactory() as session:
        revoke_token(session, token)

    refused = upload(client, device, headers=headers_for(token))
    assert refused.status_code == 401


def test_a_nonsense_token_is_refused_rather_than_trusted(client, readable_clip):
    device = "forged_device"
    upload(client, device)  # spend the allowance

    refused = upload(client, device, headers=headers_for("not-a-real-token"))
    assert refused.status_code == 401


# --- Sign in and subscribe must stay distinguishable ----------------------


def test_running_out_of_free_reps_is_403_not_401(client, readable_clip):
    """The seam that matters. A golfer at their daily limit is a customer to
    be sold to, not a stranger to be identified, and the apps tell those two
    apart by status code alone."""
    from payments.models import FREE_REPS_PER_DAY

    device = "limit_device"
    headers = headers_for(token_for("limit@example.com", device))

    for _ in range(FREE_REPS_PER_DAY):
        assert upload(client, device, headers=headers).status_code == 200

    spent = upload(client, device, headers=headers)
    assert spent.status_code == 403
    assert spent.json()["detail"]["error"] == "daily_limit_reached"


# --- What stays open ------------------------------------------------------


def test_the_lesson_video_needs_no_account(client):
    """Swing Learn is open, per the brief."""
    assert client.get("/videos/instructional", params={"module": "swing"}).status_code == 200


def test_share_and_connect_need_no_account(client):
    """A golfer should be able to tell a friend, or write to the founder,
    without an account. Both are how people arrive rather than what they do
    once they have."""
    share = client.post("/share/invite", json={"email": "friend@example.com"})
    assert share.status_code != 401

    founder = client.post(
        "/connect/founder",
        json={"message": "Hello", "email": "someone@example.com"},
    )
    assert founder.status_code != 401
