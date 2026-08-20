"""The correction module's deterministic rules, as specified for Version 1.

Taken straight from the client's definition. Each of these is a rule he stated
rather than an implementation detail, which is why they are pinned here: they
are the contract between the engine, the paywall and the three apps, and the
V1/V2 boundary runs right through them.

    successful rep  -> correction clip plays, rep counted, paywall advances
    failed rep      -> retry message, no clip, no rep counted, no paywall
    the clip        -> chosen by mode, never by fault, in Version 1
"""

import io
import os

import pytest
from fastapi.testclient import TestClient

import server
import video_analyzer
import video_library
from payments.db import SessionFactory
from payments.entitlement import check_entitlement

CDN = "https://videos.example.com"

# Comfortably over the size floor, so the engine treats it as a real recording.
PLAUSIBLE_CLIP = os.urandom(video_analyzer.MIN_FILE_BYTES * 2)
UNREADABLE_CLIP = b""


@pytest.fixture
def hosted(monkeypatch):
    monkeypatch.setattr(video_library, "BASE_URL", CDN)


@pytest.fixture
def readable_clip(monkeypatch):
    """Make the analyser see an ordinary recording.

    These tests are about what happens once a rep analyses successfully, not
    about video decoding. Without this they depend on whether ffprobe happens
    to be installed on the machine running them: with it, the random bytes
    below are correctly rejected as not-a-video; without it they sail through
    and get scored. That is a test that silently changes meaning depending on
    the environment, so the decoding step is pinned here instead.
    """
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

@pytest.fixture
def client():
    return TestClient(server.app)


def upload(client, payload, module="swing", device="correction_module_device",
           headers=None):
    return client.post(
        "/upload",
        params={"module": module, "device_id": device},
        files={"file": ("clip.mp4", io.BytesIO(payload), "video/mp4")},
        headers=headers or {},
    )


def reps_used(device, module="swing"):
    with SessionFactory() as session:
        return check_entitlement(session, device, module).reps_used


# --- One clip per mode, never per fault -----------------------------------


@pytest.mark.parametrize(
    "module,expected",
    [
        ("swing", "swing_correction.mp4"),
        ("putt", "putt_correction.mp4"),
        ("short_game", "shortgame_correction.mp4"),
    ],
)
def test_each_mode_has_exactly_one_correction_clip(hosted, module, expected):
    """The filenames are the ones the client is delivering, exactly as written.

    Note "shortgame" here against the "short_game" module key used everywhere
    else. That inconsistency is his, and matching it is the point: a rename on
    our side would mean the file he sends does not resolve.
    """
    assert video_library.correction_url(module, "any_fault") == f"{CDN}/correction/{expected}"


def test_the_clip_does_not_change_with_the_fault(hosted):
    """V1 reinforces the identity of the correction, not the specific fault."""
    faults = ["casting", "over_the_top", "sway", "chicken_wing"]
    urls = {video_library.correction_url("swing", f) for f in faults}

    assert len(urls) == 1, "the correction clip must not branch on the fault in V1"


# --- A successful rep ------------------------------------------------------


def test_a_successful_rep_returns_a_clip_and_the_written_correction(client, hosted, readable_clip):
    body = upload(client, PLAUSIBLE_CLIP, device="rep_success_device").json()

    assert body["status"] == "ok"
    assert body["dominant_fault"]
    assert body["correction"]
    assert body["correction_video_url"] == f"{CDN}/correction/swing_correction.mp4"


def test_a_successful_rep_counts_towards_the_paywall(client, hosted, readable_clip):
    """The other half of the rule: reps that produced coaching do count.

    Without this, the fix that stopped failed reps being charged could quietly
    have stopped charging for anything at all, and the paywall would never
    trigger.
    """
    device = "rep_counted_device"
    before = reps_used(device)

    upload(client, PLAUSIBLE_CLIP, device=device)

    assert reps_used(device) == before + 1


# --- A failed rep ----------------------------------------------------------


def test_a_failed_rep_plays_no_correction_clip(client, hosted):
    """Stated explicitly: on "try again" the module does not play a clip."""
    body = upload(client, UNREADABLE_CLIP, device="rep_failed_device").json()

    assert body["status"] == "no_swing_detected"
    assert body["correction_video_url"] is None


def test_a_failed_rep_shows_the_retry_message(client, hosted):
    body = upload(client, UNREADABLE_CLIP, device="rep_failed_device").json()

    assert body["correction"], "the golfer must still be told what to do"
    assert body["dominant_fault"] == "", "a failure must not name a fault"


def test_a_failed_rep_does_not_count_towards_the_paywall(client, hosted):
    device = "rep_not_counted_device"
    before = reps_used(device)

    for _ in range(3):
        upload(client, UNREADABLE_CLIP, device=device)

    assert reps_used(device) == before


# --- Where the two meet ----------------------------------------------------


def test_failed_reps_between_good_ones_do_not_advance_the_paywall(
    client, hosted, readable_clip, auth_headers
):
    """The realistic case: somebody films badly, adjusts, films again.

    Three good reps should reach the limit no matter how many unreadable
    attempts happen in between.

    Signed in, because this is a second rep: the un-gated allowance covers the
    first one only, and this test is about rep accounting rather than the gate.
    """
    device = "mixed_reps_device"

    upload(client, PLAUSIBLE_CLIP, device=device, headers=auth_headers)
    for _ in range(4):
        upload(client, UNREADABLE_CLIP, device=device, headers=auth_headers)
    upload(client, PLAUSIBLE_CLIP, device=device, headers=auth_headers)

    assert reps_used(device) == 2


def test_the_written_correction_is_always_present_either_way(client, hosted):
    """Whether it coached or refused, something readable comes back.

    The clip can fail to load on a phone in a field somewhere; the text is what
    survives that.
    """
    for payload in (PLAUSIBLE_CLIP, UNREADABLE_CLIP):
        body = upload(client, payload, device="always_text_device").json()
        assert body["correction"].strip()
