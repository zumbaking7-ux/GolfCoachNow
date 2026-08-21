"""Serving video with byte ranges.

Android's VideoView wraps MediaPlayer, which asks for ranges and expects a
206. The static host answers 200 with the whole file and no Accept-Ranges
header, so every clip failed on Android - and failed silently, because the
player's error path and its finished path are the same callback.

Two things are pinned here. The range arithmetic, because an off-by-one in a
Content-Range is the kind of thing that plays on one device and not another.
And the path handling, because this route takes a path from the caller and
the only thing standing between that and the filesystem is the check below.
"""

import io
import os

import pytest
from fastapi.testclient import TestClient

import server

BODY = bytes(range(256)) * 40  # 10240 bytes, and every byte tells you its offset


@pytest.fixture
def clip(tmp_path, monkeypatch):
    videos = tmp_path / "videos"
    (videos / "instructional").mkdir(parents=True)
    (videos / "instructional" / "learn_swing.mp4").write_bytes(BODY)
    (tmp_path / "secret.txt").write_text("not for serving", encoding="utf-8")
    monkeypatch.setattr(server, "_VIDEO_DIR", str(videos))
    return videos


@pytest.fixture
def client():
    return TestClient(server.app)


URL = "/media/instructional/learn_swing.mp4"


# --- the whole file ------------------------------------------------------


def test_without_a_range_the_whole_clip_comes_back(client, clip):
    r = client.get(URL)
    assert r.status_code == 200
    assert r.content == BODY
    assert r.headers["content-type"] == "video/mp4"


def test_it_advertises_that_it_takes_ranges(client, clip):
    """MediaPlayer looks for this before it tries to seek."""
    assert client.get(URL).headers["accept-ranges"] == "bytes"


# --- ranges --------------------------------------------------------------


def test_a_range_answers_206_with_exactly_those_bytes(client, clip):
    r = client.get(URL, headers={"Range": "bytes=0-1023"})
    assert r.status_code == 206
    assert r.content == BODY[:1024]
    assert r.headers["content-range"] == "bytes 0-1023/%d" % len(BODY)
    assert r.headers["content-length"] == "1024"


def test_a_range_from_the_middle(client, clip):
    r = client.get(URL, headers={"Range": "bytes=5000-5999"})
    assert r.status_code == 206
    assert r.content == BODY[5000:6000]
    assert r.headers["content-range"] == "bytes 5000-5999/%d" % len(BODY)


def test_an_open_ended_range_runs_to_the_end(client, clip):
    """"bytes=9000-" means from there to the end, which is what a player
    sends when it resumes."""
    r = client.get(URL, headers={"Range": "bytes=9000-"})
    assert r.status_code == 206
    assert r.content == BODY[9000:]
    assert r.headers["content-range"] == "bytes 9000-%d/%d" % (len(BODY) - 1, len(BODY))


def test_a_suffix_range_takes_the_last_bytes(client, clip):
    """"bytes=-500" is the last 500, not the first. A player reads the tail
    of a file to find its index when the index is not at the front."""
    r = client.get(URL, headers={"Range": "bytes=-500"})
    assert r.status_code == 206
    assert r.content == BODY[-500:]


def test_a_range_past_the_end_is_clamped(client, clip):
    r = client.get(URL, headers={"Range": "bytes=10000-99999"})
    assert r.status_code == 206
    assert r.content == BODY[10000:]


def test_a_range_starting_past_the_end_is_refused(client, clip):
    """416, with the real size, so the player can correct itself."""
    r = client.get(URL, headers={"Range": "bytes=99999-"})
    assert r.status_code == 416
    assert r.headers["content-range"] == "bytes */%d" % len(BODY)


def test_a_malformed_range_is_ignored_rather_than_failing(client, clip):
    """Serving the whole file is a worse answer than a range but a better
    one than an error: the clip still plays."""
    r = client.get(URL, headers={"Range": "furlongs=1-2"})
    assert r.status_code == 200
    assert r.content == BODY


# --- what the path may reach --------------------------------------------


def test_a_path_climbing_out_is_refused(client, clip):
    for attempt in (
        "/media/../secret.txt",
        "/media/instructional/../../secret.txt",
        "/media/....//secret.txt",
    ):
        assert client.get(attempt).status_code in (404, 400), attempt


def test_a_clip_that_does_not_exist_is_a_404(client, clip):
    assert client.get("/media/instructional/nothing.mp4").status_code == 404


def test_a_directory_is_not_served(client, clip):
    assert client.get("/media/instructional").status_code == 404


# --- who may watch -------------------------------------------------------


def test_watching_needs_no_account(client, clip):
    """The lesson is open, like the endpoint that hands out its url. Gating
    the clip but not the link that points at it would be theatre."""
    assert client.get(URL).status_code == 200
