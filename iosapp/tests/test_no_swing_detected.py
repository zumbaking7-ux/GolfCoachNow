"""What the engine says when there is no swing in the clip.

The behaviour these cover is the difference between a coaching product and a
random fault generator. Before this existed, an empty file, a text file renamed
to .mp4, and four kilobytes of noise each came back with a confident, specific,
entirely invented correction.

Two distinct answers matter here and must not collapse into one:

    NoSwingDetected     we read the clip, there is nothing to coach
    AnalysisUnavailable we could not read it, and re-recording will not help
"""

import io
import os

import pytest
from fastapi.testclient import TestClient

import server
import video_analyzer

DEVICE = "no_swing_test_device"


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


def upload(client, payload: bytes, module: str = "swing", filename: str = "clip.mp4"):
    return client.post(
        "/upload",
        params={"module": module, "device_id": DEVICE},
        files={"file": (filename, io.BytesIO(payload), "video/mp4")},
    )


# --- The size floor, which works with or without ffprobe ------------------


@pytest.mark.parametrize(
    "label,payload",
    [
        ("empty file", b""),
        ("text renamed .mp4", b"this is not a video, it is a sentence"),
        ("a few random bytes", os.urandom(2048)),
    ],
)
def test_junk_is_not_coached(client, label, payload):
    """The three cases that started this. None of them may produce coaching."""
    response = upload(client, payload)

    assert response.status_code == 200, label
    body = response.json()
    assert body["status"] == "no_swing_detected", label
    assert body["dominant_fault"] == "", label
    assert body["correction"], "the golfer still needs to be told something"


def test_the_message_tells_the_golfer_what_to_do(client):
    body = upload(client, b"").json()
    assert "record" in body["correction"].lower() or "frame" in body["correction"].lower()


def test_no_correction_video_is_offered_when_there_was_no_swing(client):
    assert upload(client, b"").json()["correction_video_url"] is None


@pytest.mark.parametrize("module", ["swing", "putt", "short_game"])
def test_every_module_refuses_to_invent_coaching(client, module):
    """Putt and short game never reach the pose tiers, so they need this most."""
    body = upload(client, b"", module=module).json()
    assert body["status"] == "no_swing_detected"


# --- Not spending a rep on a clip we could not read -----------------------


def test_an_unreadable_clip_does_not_cost_a_rep(client):
    """Three bad camera angles must not paywall somebody who was never coached.

    The allowance is checked before analysis and only spent afterwards, so this
    is the test that keeps those two apart.
    """
    from payments.db import SessionFactory
    from payments.entitlement import check_entitlement

    with SessionFactory() as session:
        before = check_entitlement(session, DEVICE, "swing").reps_used

    for _ in range(3):
        assert upload(client, b"").json()["status"] == "no_swing_detected"

    with SessionFactory() as session:
        after = check_entitlement(session, DEVICE, "swing")

    assert after.reps_used == before, "an unreadable clip was charged as a rep"
    assert after.allowed, "the golfer was paywalled without ever being coached"


# --- The response shape both apps have to decode --------------------------


def test_the_shape_stays_decodable_by_the_existing_apps(client):
    """iOS decodes into a struct whose fields are not optional.

    Dropping a key here would surface as a decode failure on the phone rather
    than as the message we are trying to show, so the shape is part of the
    contract.
    """
    body = upload(client, b"").json()

    for key in ("rep", "dominant_fault", "correction", "normalized_scores", "status"):
        assert key in body, f"{key} missing; iOS would fail to decode this"
    assert isinstance(body["rep"], int)
    assert isinstance(body["normalized_scores"], dict)


# --- Strict mode ----------------------------------------------------------


def test_strict_mode_refuses_to_score_from_metadata(monkeypatch, tmp_path, readable_clip):
    """With STRICT_ANALYSIS on, nothing may be invented under any circumstance.

    This is the switch to throw once the pose libraries are confirmed present
    in production.
    """
    monkeypatch.setattr(video_analyzer, "STRICT_ANALYSIS", True)

    clip = tmp_path / "plausible.mp4"
    clip.write_bytes(os.urandom(video_analyzer.MIN_FILE_BYTES + 1))

    with pytest.raises(video_analyzer.AnalysisUnavailable):
        video_analyzer.analyze_video(str(clip), module="swing")


def test_metadata_scoring_still_works_when_not_strict(tmp_path, readable_clip):
    """Default behaviour is unchanged for anything that looks like a recording.

    Turning the fallback off is a deliberate decision, not a side effect of
    adding these checks.
    """
    clip = tmp_path / "plausible.mp4"
    clip.write_bytes(os.urandom(video_analyzer.MIN_FILE_BYTES + 1))

    scores = video_analyzer.analyze_video(str(clip), module="swing")

    assert scores, "a plausible clip should still be scored while strict mode is off"


# --- The probe distinction ------------------------------------------------


def test_a_short_clip_is_rejected_only_when_ffprobe_measured_it(monkeypatch, tmp_path):
    """A duration of zero means different things in the two cases.

    Measured by ffprobe it means the clip is unusable. Produced by the hash
    fallback it means ffprobe was never installed, and rejecting on it would
    turn away every recording on such a server.
    """
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(os.urandom(video_analyzer.MIN_FILE_BYTES + 1))

    monkeypatch.setattr(
        video_analyzer,
        "_extract_metadata",
        lambda _: {"duration": 0.1, "width": 1920, "height": 1080, "file_size": 50_000, "probed": True},
    )
    with pytest.raises(video_analyzer.NoSwingDetected):
        video_analyzer.analyze_video(str(clip), module="swing")

    monkeypatch.setattr(
        video_analyzer,
        "_extract_metadata",
        lambda _: {"duration": 0.0, "width": 0, "height": 0, "file_size": 50_000, "probed": False},
    )
    assert video_analyzer.analyze_video(str(clip), module="swing")
