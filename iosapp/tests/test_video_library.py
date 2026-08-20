"""Which video a request resolves to.

These are the rules the whole video pipeline rests on, and every one of them is
a decision rather than an implementation detail: what happens before any asset
exists, what happens for a fault nobody has filmed yet, and what an app is
supposed to do when the answer is nothing at all.

The module reads its base URL once at import, so these tests set the attribute
rather than the environment variable. Reloading the module instead would work
but would hand a different object to anything already holding a reference.
"""

import pytest
from fastapi.testclient import TestClient

import server
import video_library

CDN = "https://videos.example.com"


@pytest.fixture
def hosted(monkeypatch):
    """A deployment that has somewhere to serve assets from."""
    monkeypatch.setattr(video_library, "BASE_URL", CDN)


@pytest.fixture
def client():
    return TestClient(server.app)


# --- Instructional clips -------------------------------------------------


def test_swing_has_its_own_lesson_and_the_others_share_one(hosted):
    """Swing got a lesson filmed for it; the other two keep the generic clip.

    This is the change the mapping was built to allow, and it stayed a change
    to this one file, which is the point of resolving every url in one place.
    """
    assert video_library.instructional_url("swing") == (
        f"{CDN}/instructional/learn_swing.mp4"
    )

    shared = f"{CDN}/instructional/all_modes.mp4"
    assert video_library.instructional_url("putt") == shared
    assert video_library.instructional_url("short_game") == shared


def test_no_base_url_means_no_video_rather_than_a_broken_one(monkeypatch):
    """A machine with nowhere to serve assets from must say so plainly.

    Returning a half-built URL would send the apps chasing something that
    cannot exist, and the failure would surface as a stalled video rather than
    a missing one.
    """
    monkeypatch.setattr(video_library, "BASE_URL", "")
    assert video_library.instructional_url("swing") is None


def test_unknown_module_has_no_instructional_clip(hosted):
    assert video_library.instructional_url("croquet") is None


# --- Correction clips ----------------------------------------------------


def test_a_fault_with_no_clip_of_its_own_falls_back_to_the_module_clip(hosted):
    """Version 1 ships one clip per mode, and every fault resolves to it.

    The fault is deliberately not consulted here. Version 2 adds per-fault
    clips and this same call starts returning them, with nothing else
    changing.
    """
    assert (
        video_library.correction_url("swing", "casting")
        == f"{CDN}/correction/swing_correction.mp4"
    )


def test_a_dedicated_clip_wins_over_the_fallback(hosted, monkeypatch):
    monkeypatch.setitem(
        video_library.CORRECTION, ("swing", "casting"), "correction/casting.mp4"
    )
    assert (
        video_library.correction_url("swing", "casting")
        == f"{CDN}/correction/casting.mp4"
    )


def test_no_fault_detected_still_returns_the_module_clip(hosted):
    """The engine can answer without naming a fault, and that is not an error."""
    assert (
        video_library.correction_url("putt", None)
        == f"{CDN}/correction/putt_correction.mp4"
    )


def test_an_absolute_url_is_left_alone(hosted, monkeypatch):
    """One clip can live somewhere else without moving the rest."""
    elsewhere = "https://cdn.somewhere-else.test/special.mp4"
    monkeypatch.setitem(video_library.CORRECTION, ("putt", "push"), elsewhere)
    assert video_library.correction_url("putt", "push") == elsewhere


def test_unknown_module_has_no_correction_clip(hosted):
    assert video_library.correction_url("croquet", "anything") is None


# --- The endpoint the apps actually call ---------------------------------


def test_endpoint_returns_the_clip_for_a_module(client, hosted):
    response = client.get("/videos/instructional", params={"module": "putt"})

    assert response.status_code == 200
    assert response.json() == {
        "module": "putt",
        "url": f"{CDN}/instructional/all_modes.mp4",
    }


def test_endpoint_answers_null_when_nothing_is_published_yet(client, monkeypatch):
    """A null url is a real answer, and the apps are built to act on it.

    This is the state the product ships in before the assets land, so it has to
    be a clean 200 the apps can read rather than an error they have to survive.
    """
    monkeypatch.setattr(video_library, "BASE_URL", "")

    response = client.get("/videos/instructional", params={"module": "swing"})

    assert response.status_code == 200
    assert response.json()["url"] is None


def test_endpoint_rejects_a_module_that_does_not_exist(client):
    response = client.get("/videos/instructional", params={"module": "croquet"})

    assert response.status_code == 400


def test_scored_analysis_comes_back_with_its_correction_clip(client, hosted):
    """Wire four: the correction video arrives with the correction itself.

    One round trip rather than two, so the app never has to ask a second
    question before it can show anything.
    """
    response = client.post(
        "/wedge",
        json={"data": {"casting": 0.9, "sway": 0.2}, "device_id": "video_test_device"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dominant_fault"] == "casting"
    assert body["correction_video_url"] == f"{CDN}/correction/swing_correction.mp4"


def test_the_written_correction_survives_alongside_the_video(client, hosted):
    """The text is not replaced by the video, it backs it up.

    If a clip fails to load on a phone in a field somewhere, the written
    correction is what the golfer still gets.
    """
    response = client.post(
        "/putt",
        json={"data": {"push": 0.8}, "device_id": "video_test_device"},
    )

    body = response.json()
    assert body["correction"]
    assert body["correction_video_url"]
