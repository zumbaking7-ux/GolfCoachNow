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


# --- The presence check, which runs for every mode -------------------------


def _plausible(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(os.urandom(video_analyzer.MIN_FILE_BYTES + 1))
    return str(clip)


@pytest.fixture
def pose_available(monkeypatch):
    """Pretend MediaPipe is installed, without installing it.

    The production server has it; this machine does not. Pinning it here means
    these rules are tested wherever the suite runs rather than only where the
    library happens to be present.
    """
    monkeypatch.setattr(video_analyzer, "_ensure_mp", lambda: True)


def _pose_finds(monkeypatch, frames):
    monkeypatch.setattr(
        video_analyzer,
        "_extract_pose_landmarks",
        lambda *a, **k: [{"idx": i, "t": i / 30.0, "lm": []} for i in range(frames)],
    )


@pytest.mark.parametrize("module", ["putt", "short_game"])
def test_no_person_is_refused_for_putt_and_short_game_too(
    monkeypatch, tmp_path, pose_available, readable_clip, module
):
    """The gap that let a video of something else be coached.

    Putt and short game have no pose scorer, so before this they skipped
    straight to metadata scoring and would confidently coach anything at all.
    """
    _pose_finds(monkeypatch, 0)

    with pytest.raises(video_analyzer.NoSwingDetected):
        video_analyzer.analyze_video(_plausible(tmp_path), module=module)


@pytest.mark.parametrize("module", ["putt", "short_game"])
def test_a_person_present_still_reaches_scoring(
    monkeypatch, tmp_path, pose_available, readable_clip, module
):
    """The check gates, it does not replace the engine.

    Putt and short game keep their own scoring; the pose pass only decides
    whether there is anybody there to score.
    """
    _pose_finds(monkeypatch, 20)

    assert video_analyzer.analyze_video(_plausible(tmp_path), module=module)


def test_putt_never_comes_back_with_swing_vocabulary(
    monkeypatch, tmp_path, pose_available, readable_clip
):
    """Why the pose scorer is not simply run for every mode.

    It measures a full swing and names swing faults, none of which exist in
    the putt correction set. Running it for putt would produce faults with no
    correction attached.
    """
    import putt as putt_engine

    _pose_finds(monkeypatch, 20)
    scores = video_analyzer.analyze_video(_plausible(tmp_path), module="putt")

    assert set(scores) <= set(putt_engine.CORRECTIONS)


def test_a_broken_library_does_not_accuse_the_golfer(
    monkeypatch, tmp_path, pose_available, readable_clip
):
    """MediaPipe failing is our problem, not a verdict on their recording."""
    def explode(*a, **k):
        raise RuntimeError("mediapipe fell over")

    monkeypatch.setattr(video_analyzer, "_extract_pose_landmarks", explode)

    with pytest.raises(RuntimeError):
        video_analyzer.require_a_person(_plausible(tmp_path))


# --- Availability must mean usable, not merely importable ------------------


def test_a_mediapipe_without_the_tasks_api_is_not_available(monkeypatch, tmp_path):
    """Google removed the Solutions API this analyser first used.

    A MediaPipe missing the Tasks API still imports. Treating that as
    availability sent every clip down a path that raised: swallowed on the
    swing route, where it quietly fell back to a weaker tier, and a server
    error on the others.
    """
    import sys
    import types

    monkeypatch.setattr(video_analyzer, "mp", None)
    monkeypatch.setattr(video_analyzer, "_ensure_cv", lambda: True)
    monkeypatch.setitem(sys.modules, "mediapipe", types.ModuleType("mediapipe"))

    assert video_analyzer._ensure_mp() is False


def _fake_mediapipe(monkeypatch):
    """A MediaPipe that looks the way the Tasks API really does."""
    import sys
    import types

    mediapipe = types.ModuleType("mediapipe")
    tasks = types.ModuleType("mediapipe.tasks")
    tasks_python = types.ModuleType("mediapipe.tasks.python")
    vision = types.ModuleType("mediapipe.tasks.python.vision")
    tasks.python = tasks_python
    tasks_python.vision = vision
    mediapipe.tasks = tasks

    for name, mod in [
        ("mediapipe", mediapipe),
        ("mediapipe.tasks", tasks),
        ("mediapipe.tasks.python", tasks_python),
        ("mediapipe.tasks.python.vision", vision),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)

    monkeypatch.setattr(video_analyzer, "mp", None)
    monkeypatch.setattr(video_analyzer, "_ensure_cv", lambda: True)


def test_the_model_weights_must_be_on_disk_too(monkeypatch, tmp_path):
    """MediaPipe ships the runtime but not the model.

    A correct install with no weights detects nothing, so it must not report
    itself as available - that was the shape of the last failure, arriving as
    a server error rather than an answer.
    """
    _fake_mediapipe(monkeypatch)
    monkeypatch.setattr(
        video_analyzer, "POSE_MODEL_PATH", str(tmp_path / "not_downloaded.task")
    )

    assert video_analyzer._ensure_mp() is False


def test_available_when_the_api_and_the_model_are_both_there(monkeypatch, tmp_path):
    _fake_mediapipe(monkeypatch)
    model = tmp_path / "pose_landmarker_lite.task"
    model.write_bytes(b"not a real model, but present")
    monkeypatch.setattr(video_analyzer, "POSE_MODEL_PATH", str(model))

    assert video_analyzer._ensure_mp() is True
    monkeypatch.setattr(video_analyzer, "mp", None)


# --- Sampling must not depend on metadata the file need not carry ----------


class _FakeCapture:
    """A video that reports no frame count, the way phone recordings often do."""

    def __init__(self, frames, reports_total):
        self._frames = frames
        self._reports_total = reports_total
        self._read = 0

    def isOpened(self):
        return True

    def get(self, prop):
        # 7 is CAP_PROP_FRAME_COUNT, 5 is CAP_PROP_FPS.
        if prop == 7:
            return self._reports_total
        if prop == 5:
            return 30.0
        return 0

    def read(self):
        if self._read >= self._frames:
            return False, None
        self._read += 1
        return True, object()

    def release(self):
        pass


def _stub_pose(monkeypatch, capture, detections):
    """Wire the analyser to a fake camera and a counting landmarker."""
    import types

    monkeypatch.setattr(video_analyzer, "cv2", types.SimpleNamespace(
        VideoCapture=lambda _: capture,
        CAP_PROP_FRAME_COUNT=7,
        CAP_PROP_FPS=5,
        cvtColor=lambda frame, code: frame,
        COLOR_BGR2RGB=4,
    ))
    monkeypatch.setattr(video_analyzer, "mp", types.SimpleNamespace(
        Image=lambda **kw: object(),
        ImageFormat=types.SimpleNamespace(SRGB=1),
    ))

    class _Landmarker:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def detect_for_video(self, image, ts):
            detections.append(ts)
            return types.SimpleNamespace(pose_landmarks=[])

    monkeypatch.setattr(video_analyzer, "mp_tasks", types.SimpleNamespace(
        BaseOptions=lambda **kw: None))
    monkeypatch.setattr(video_analyzer, "mp_vision", types.SimpleNamespace(
        PoseLandmarkerOptions=lambda **kw: None,
        RunningMode=types.SimpleNamespace(VIDEO=1),
        PoseLandmarker=types.SimpleNamespace(create_from_options=lambda o: _Landmarker()),
    ))


def test_a_file_with_no_frame_count_does_not_analyse_every_frame(monkeypatch):
    """The bug that hung a live upload for ten minutes.

    A phone recording often reports zero frames, because the container carries
    no index. The old arithmetic turned that into a step of one and ran pose
    detection on all 450 frames of a fifteen second clip. On a shared CPU the
    request never came back.
    """
    detections = []
    _stub_pose(monkeypatch, _FakeCapture(frames=450, reports_total=0), detections)

    video_analyzer._extract_pose_landmarks("ignored.mp4", max_frames=20)

    assert len(detections) <= 20, "analysed %d frames, cap is 20" % len(detections)


def test_the_cap_holds_even_when_the_frame_count_lies(monkeypatch):
    """Metadata can be wrong as easily as absent."""
    detections = []
    _stub_pose(monkeypatch, _FakeCapture(frames=900, reports_total=10), detections)

    video_analyzer._extract_pose_landmarks("ignored.mp4", max_frames=20)

    assert len(detections) <= 20


def test_a_normal_recording_still_samples_across_the_whole_clip(monkeypatch):
    """The fix must not cost analysis quality on a well-formed file."""
    detections = []
    _stub_pose(monkeypatch, _FakeCapture(frames=450, reports_total=450), detections)

    video_analyzer._extract_pose_landmarks("ignored.mp4", max_frames=20)

    assert len(detections) == 20
    # Spread across the clip rather than bunched at the start: the last sample
    # should be near the end, which is where the follow through is.
    assert detections[-1] > detections[0] * 15


def test_extraction_gives_up_rather_than_hanging(monkeypatch):
    """A partial read that answers beats a complete one that never does."""
    detections = []
    _stub_pose(monkeypatch, _FakeCapture(frames=10_000, reports_total=10_000), detections)
    monkeypatch.setattr(video_analyzer, "POSE_TIME_BUDGET_SECONDS", -1)

    video_analyzer._extract_pose_landmarks("ignored.mp4", max_frames=5000)

    assert detections == [], "the budget should stop it before any work"
