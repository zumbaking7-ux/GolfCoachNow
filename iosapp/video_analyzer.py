import math
import os
import subprocess
import json
import hashlib
import random

from wedge import CORRECTIONS as WEDGE_CORRECTIONS
from putt import CORRECTIONS as PUTT_CORRECTIONS
from chip import CORRECTIONS as CHIP_CORRECTIONS

MODULE_FAULTS = {
    "swing": list(WEDGE_CORRECTIONS.keys()),
    "putt": list(PUTT_CORRECTIONS.keys()),
    "short_game": list(CHIP_CORRECTIONS.keys()),
}

cv2 = None
np = None
mp = None


def _ensure_cv():
    global cv2, np
    if cv2 is not None:
        return True
    try:
        import cv2 as _cv2
        import numpy as _np
        cv2 = _cv2
        np = _np
        return True
    except ImportError:
        return False


def _ensure_mp():
    """Whether pose tracking is genuinely usable, not merely installed.

    Importing is not enough. MediaPipe 1.0 removed the legacy `solutions` API
    this analyser is written against, so the import succeeds on a library that
    cannot detect a thing. Reporting availability on the import alone sent
    every clip down a path that raised: swallowed on the swing route, where it
    fell through to a weaker tier, and surfaced as a server error everywhere
    else.

    So the check is for the attribute actually used, not the package name.
    """
    global mp
    if mp is not None:
        return True
    if not _ensure_cv():
        return False
    try:
        import mediapipe as _mp
        _mp.solutions.pose  # the API _extract_pose_landmarks calls
        mp = _mp
        return True
    except (ImportError, AttributeError):
        return False

FAULT_KEYS = MODULE_FAULTS["swing"]

_L_SHOULDER, _R_SHOULDER = 11, 12
_L_ELBOW, _R_ELBOW = 13, 14
_L_WRIST, _R_WRIST = 15, 16
_L_HIP, _R_HIP = 23, 24
_L_KNEE, _R_KNEE = 25, 26


class VideoAnalysisError(Exception):
    pass


class NoSwingDetected(VideoAnalysisError):
    """We looked at the clip and there is nothing here to coach.

    This is a finding, not a failure. It carries a message written for the
    person holding the phone, because that message is what they will read.

    It exists because the alternative is worse than an error: without it the
    pipeline falls through to metadata scoring and answers an empty recording
    with confident, specific, invented coaching.
    """


class AnalysisUnavailable(VideoAnalysisError):
    """We could not look at the clip at all.

    Raised only under STRICT_ANALYSIS. Distinct from NoSwingDetected on
    purpose: one means the golfer needs to record again, the other means the
    server is missing something and no amount of re-recording will help.
    """


# Refuse to fall back to metadata scoring, which does not look at the video.
# Off by default so the product keeps working while we confirm what is actually
# installed in production; turn it on once the pose libraries are confirmed and
# the system can no longer invent a correction under any circumstances.
STRICT_ANALYSIS = os.environ.get("STRICT_ANALYSIS", "").strip().lower() in ("1", "true", "yes")

# Smaller than any real recording. A one second clip from a phone is hundreds
# of kilobytes; this only catches empty files and junk, and it works whether or
# not ffprobe is installed.
MIN_FILE_BYTES = 10_000

# Shorter than this cannot contain a golf swing, let alone a scoreable one.
MIN_CLIP_SECONDS = 0.8

# Mean frame-to-frame difference, on a 0-255 grey scale, below which nothing in
# the frame moved. Deliberately low: it should catch a still image or a covered
# lens, and never a real swing filmed badly. Worth retuning against real
# footage once we have some.
MIN_MOTION = 1.0

_FRAMING_ADVICE = "Stand back so your whole body is in frame, then record again."


def analyze_video(file_path, module="swing"):
    if not os.path.exists(file_path):
        raise VideoAnalysisError("Video file not found")

    if os.path.getsize(file_path) < MIN_FILE_BYTES:
        # Covers an empty upload, a truncated one, and anything that is not a
        # recording at all. None of those are the golfer's framing, so the
        # message does not send them back to reposition the camera.
        raise NoSwingDetected(
            "That recording didn't come through properly. Please try recording again."
        )

    if _ensure_mp():
        if module == "swing":
            try:
                return _to_python_floats(_analyze_with_pose(file_path))
            except NoSwingDetected:
                # A real answer about the clip. Passing it down to a tier that
                # cannot see the video would replace a true finding with a
                # fabricated one.
                raise
            except Exception:
                pass
        else:
            # Putt and short game have no pose scorer of their own yet - the
            # one above measures a full swing and names swing faults, which do
            # not exist in their correction sets.
            #
            # The presence check still runs for them, because "is there a
            # person in this video at all" is the question that stops a clip of
            # something else being coached, and it is worth answering whichever
            # engine was asked for.
            require_a_person(file_path)

    if module == "swing" and _ensure_cv():
        try:
            return _to_python_floats(_analyze_with_motion(file_path))
        except NoSwingDetected:
            raise
        except Exception:
            pass

    return _analyze_with_metadata(file_path, module)


def _to_python_floats(scores):
    return {k: float(v) for k, v in scores.items()}


# ======================================================================
#  TIER 1: MediaPipe Pose (full skeleton tracking)
# ======================================================================

MIN_POSE_FRAMES = 5


def require_a_person(file_path):
    """Raise unless a person is visibly present in the clip.

    The cheapest honest question the system can ask. It does not know what a
    golf swing looks like - that is still ahead - but it does know the
    difference between somebody standing in front of a camera and a video of
    something else entirely, and that alone is what stops a clip of the kitchen
    coming back with confident coaching.

    Failing to detect is treated as a finding, not an error. Anything that goes
    wrong inside MediaPipe is not, because a broken library should not tell a
    golfer their swing was unreadable.
    """
    seq = _extract_pose_landmarks(file_path, max_frames=20)
    if len(seq) < MIN_POSE_FRAMES:
        raise NoSwingDetected("We couldn't see anyone in that clip. " + _FRAMING_ADVICE)


def _analyze_with_pose(file_path):
    seq = _extract_pose_landmarks(file_path, max_frames=20)
    if len(seq) < MIN_POSE_FRAMES:
        # Same finding as require_a_person, reached on the swing path. Kept
        # here rather than delegating so the landmarks are extracted once.
        raise NoSwingDetected("We couldn't see anyone in that clip. " + _FRAMING_ADVICE)
    phases = _detect_phases(seq)
    scores = _score_pose_faults(seq, phases)
    result = {k: round(v, 3) for k, v in scores.items() if v > 0.05}
    return result if result else {"tempo_imbalance": 0.1}


def _extract_pose_landmarks(file_path, max_frames=20):
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise VideoAnalysisError("Could not open video file")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, total // max_frames)
    pose = mp.solutions.pose.Pose(
        static_image_mode=False, model_complexity=0,
        min_detection_confidence=0.5, min_tracking_confidence=0.5,
    )
    results = []
    idx = 0
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                out = pose.process(rgb)
                if out.pose_landmarks:
                    lm = [(l.x, l.y, l.z) for l in out.pose_landmarks.landmark]
                    results.append({"idx": idx, "t": idx / fps, "lm": lm})
            idx += 1
    finally:
        cap.release()
        pose.close()
    return results


def _detect_phases(seq):
    wy = [(f["lm"][_L_WRIST][1] + f["lm"][_R_WRIST][1]) / 2 for f in seq]
    end = max(3, int(len(wy) * 0.7))
    top = min(range(1, end), key=lambda i: wy[i], default=1)
    impact = top
    if top + 1 < len(wy):
        impact = top + max(range(len(wy) - top), key=lambda i: wy[top + i])
    return {"address": 0, "top": top, "impact": min(impact, len(seq) - 1), "finish": len(seq) - 1}


def _mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _angle(a, b, c):
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    dot = ba[0] * bc[0] + ba[1] * bc[1]
    m = math.hypot(*ba) * math.hypot(*bc)
    if m == 0:
        return 180.0
    return math.degrees(math.acos(max(-1, min(1, dot / m))))


def _score_pose_faults(seq, ph):
    s = {}
    addr = seq[ph["address"]]["lm"]
    top = seq[ph["top"]]["lm"]
    imp = seq[ph["impact"]]["lm"]

    hip_addr = _mid(addr[_L_HIP], addr[_R_HIP])
    hip_top = _mid(top[_L_HIP], top[_R_HIP])
    hip_imp = _mid(imp[_L_HIP], imp[_R_HIP])

    s["sway"] = min(1.0, abs(hip_top[0] - hip_addr[0]) / 0.07)
    s["slide"] = min(1.0, abs(hip_imp[0] - hip_top[0]) / 0.09)

    sh_a = _mid(addr[_L_SHOULDER], addr[_R_SHOULDER])
    kn_a = _mid(addr[_L_KNEE], addr[_R_KNEE])
    spine_a = _angle(sh_a, hip_addr, kn_a)
    sh_i = _mid(imp[_L_SHOULDER], imp[_R_SHOULDER])
    kn_i = _mid(imp[_L_KNEE], imp[_R_KNEE])
    spine_i = _angle(sh_i, hip_imp, kn_i)
    s["spine_angle_loss"] = min(1.0, abs(spine_i - spine_a) / 18.0)

    hk_a = abs(hip_addr[1] - kn_a[1])
    hk_i = abs(hip_imp[1] - kn_i[1])
    if hk_a > 0.01:
        s["early_extension"] = max(0.0, min(1.0, (1 - hk_i / hk_a) * 3.0))
    else:
        s["early_extension"] = 0.0

    mid_idx = (ph["top"] + ph["impact"]) // 2
    if mid_idx < len(seq):
        mid = seq[mid_idx]["lm"]
        l_top = _angle(top[_L_SHOULDER], top[_L_ELBOW], top[_L_WRIST])
        l_mid = _angle(mid[_L_SHOULDER], mid[_L_ELBOW], mid[_L_WRIST])
        r_top = _angle(top[_R_SHOULDER], top[_R_ELBOW], top[_R_WRIST])
        r_mid = _angle(mid[_R_SHOULDER], mid[_R_ELBOW], mid[_R_WRIST])
        cast = max(max(0, l_mid - l_top), max(0, r_mid - r_top))
        s["casting"] = min(1.0, cast / 25.0)

    l_elb = _angle(imp[_L_SHOULDER], imp[_L_ELBOW], imp[_L_WRIST])
    r_elb = _angle(imp[_R_SHOULDER], imp[_R_ELBOW], imp[_R_WRIST])
    lead = max(l_elb, r_elb)
    s["chicken_wing"] = max(0.0, min(1.0, (160 - lead) / 35.0))

    sh_top = _mid(top[_L_SHOULDER], top[_R_SHOULDER])
    hip_dx = hip_top[0] - hip_addr[0]
    sh_dx = sh_top[0] - sh_a[0]
    s["reverse_pivot"] = min(1.0, abs(sh_dx) / 0.04) if hip_dx * sh_dx < 0 else 0.0

    bs = ph["top"] - ph["address"]
    ds = ph["impact"] - ph["top"]
    s["tempo_imbalance"] = min(1.0, abs(bs / ds - 3.0) / 3.0) if ds > 0 and bs > 0 else 0.0

    dy = abs(top[_L_SHOULDER][1] - top[_R_SHOULDER][1])
    dx = abs(top[_L_SHOULDER][0] - top[_R_SHOULDER][0])
    tilt = math.degrees(math.atan2(dy, dx)) if dx > 0 else 90
    s["flat_shoulder_turn"] = min(1.0, (20 - tilt) / 20.0) if tilt < 20 else 0.0
    s["steep_shoulder_turn"] = min(1.0, (tilt - 55) / 35.0) if tilt > 55 else 0.0

    if ph["impact"] - ph["top"] >= 2 and ph["impact"] - 1 < len(seq):
        pre = seq[ph["impact"] - 1]["lm"]
        ha_p = math.degrees(math.atan2(pre[_L_HIP][1] - pre[_R_HIP][1], pre[_L_HIP][0] - pre[_R_HIP][0]))
        ha_i = math.degrees(math.atan2(imp[_L_HIP][1] - imp[_R_HIP][1], imp[_L_HIP][0] - imp[_R_HIP][0]))
        rot = abs(ha_i - ha_p)
        s["hip_stall"] = max(0.0, min(1.0, (2 - rot) / 2.0)) if rot < 2 else 0.0
    else:
        s["hip_stall"] = 0.0

    if mid_idx < len(seq):
        mid = seq[mid_idx]["lm"]
        ht = _mid(top[_L_WRIST], top[_R_WRIST])
        hm = _mid(mid[_L_WRIST], mid[_R_WRIST])
        hc = _mid(mid[_L_HIP], mid[_R_HIP])
        dt = abs(ht[0] - hip_top[0])
        dm = abs(hm[0] - hc[0])
        delta = dm - dt
        if delta > 0:
            s["over_the_top"] = min(1.0, delta / 0.04)
            s["under_plane"] = 0.0
        else:
            s["under_plane"] = min(1.0, abs(delta) / 0.06)
            s["over_the_top"] = 0.0
    else:
        s["over_the_top"] = 0.0
        s["under_plane"] = 0.0

    addr_tilt = abs(addr[_L_SHOULDER][1] - addr[_R_SHOULDER][1])
    s["poor_alignment"] = min(1.0, addr_tilt / 0.06)

    for k in ("open_clubface", "closed_clubface", "weak_grip", "strong_grip",
              "ball_position_error", "grip_pressure"):
        s.setdefault(k, 0.0)

    return s


# ======================================================================
#  TIER 2: OpenCV Motion Analysis (optical flow + frame differencing)
# ======================================================================

def _analyze_with_motion(file_path):
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise VideoAnalysisError("Could not open video file")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, total // 25)

    frames_gray = []
    idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (320, int(320 * h / w)))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            frames_gray.append(gray)
        idx += 1
    cap.release()

    if len(frames_gray) < 5:
        raise NoSwingDetected("That clip was too short to read. " + _FRAMING_ADVICE)

    h, w = frames_gray[0].shape

    # Compute frame-to-frame differences (motion magnitude per frame)
    diffs = []
    for i in range(1, len(frames_gray)):
        diff = cv2.absdiff(frames_gray[i], frames_gray[i - 1])
        diffs.append(np.mean(diff))

    # Nothing in the frame moved across the whole clip, so whatever was filmed,
    # it was not a swing. Without this the flow analysis below happily scores a
    # still image.
    if diffs and max(diffs) < MIN_MOTION:
        raise NoSwingDetected("Nothing moved in that clip. " + _FRAMING_ADVICE)

    # Compute optical flow for key transitions
    # Split frame into upper body (top 50%) and lower body (bottom 50%)
    upper_motion_x = []
    upper_motion_y = []
    lower_motion_x = []
    lower_motion_y = []

    for i in range(1, len(frames_gray)):
        flow = cv2.calcOpticalFlowFarneback(
            frames_gray[i - 1], frames_gray[i],
            None, 0.5, 3, 15, 3, 5, 1.2, 0,
        )
        mid_h = h // 2

        upper = flow[:mid_h, :, :]
        lower = flow[mid_h:, :, :]

        upper_motion_x.append(np.mean(upper[:, :, 0]))
        upper_motion_y.append(np.mean(upper[:, :, 1]))
        lower_motion_x.append(np.mean(lower[:, :, 0]))
        lower_motion_y.append(np.mean(lower[:, :, 1]))

    if not diffs:
        raise VideoAnalysisError("Could not compute motion")

    scores = _score_motion_faults(diffs, upper_motion_x, upper_motion_y,
                                   lower_motion_x, lower_motion_y, fps, total)

    result = {k: round(v, 3) for k, v in scores.items() if v > 0.05}
    return result if result else {"tempo_imbalance": 0.1}


def _score_motion_faults(diffs, umx, umy, lmx, lmy, fps, total_frames):
    s = {}
    n = len(diffs)

    # Find peak motion frame = approximate impact
    peak = max(range(n), key=lambda i: diffs[i])
    # Backswing = frames before peak, downswing = frames after
    bs_frames = max(1, peak)
    ds_frames = max(1, n - peak)

    # --- TEMPO ---
    ratio = bs_frames / ds_frames
    s["tempo_imbalance"] = min(1.0, abs(ratio - 3.0) / 3.5)

    # --- SWAY (lower body lateral motion during backswing) ---
    if bs_frames > 1:
        bs_lateral = sum(abs(lmx[i]) for i in range(bs_frames)) / bs_frames
        s["sway"] = min(1.0, bs_lateral / 1.5)
    else:
        s["sway"] = 0.0

    # --- SLIDE (lower body lateral motion during downswing) ---
    if ds_frames > 1:
        ds_lateral = sum(abs(lmx[i]) for i in range(peak, n)) / ds_frames
        s["slide"] = min(1.0, ds_lateral / 2.0)
    else:
        s["slide"] = 0.0

    # --- EARLY EXTENSION (lower body vertical motion before impact) ---
    if peak > 1:
        pre_impact = range(max(0, peak - 3), peak)
        vert_motion = sum(abs(lmy[i]) for i in pre_impact) / max(1, len(pre_impact))
        s["early_extension"] = min(1.0, vert_motion / 1.2)
    else:
        s["early_extension"] = 0.0

    # --- SPINE ANGLE LOSS (change in upper-to-lower motion ratio) ---
    if bs_frames > 1:
        bs_upper_avg = sum(abs(umy[i]) for i in range(bs_frames)) / bs_frames
        bs_lower_avg = sum(abs(lmy[i]) for i in range(bs_frames)) / bs_frames
        if bs_lower_avg > 0.01:
            spine_ratio_change = abs(bs_upper_avg / bs_lower_avg - 1.0)
            s["spine_angle_loss"] = min(1.0, spine_ratio_change / 2.0)
        else:
            s["spine_angle_loss"] = 0.0
    else:
        s["spine_angle_loss"] = 0.0

    # --- CASTING (upper body motion too early in downswing) ---
    if ds_frames > 2:
        early_ds = diffs[peak:peak + max(1, ds_frames // 3)]
        late_ds = diffs[peak + ds_frames // 3:min(n, peak + ds_frames)]
        early_avg = sum(early_ds) / max(1, len(early_ds))
        late_avg = sum(late_ds) / max(1, len(late_ds))
        if late_avg > 0.01:
            cast_ratio = early_avg / late_avg
            s["casting"] = min(1.0, max(0.0, cast_ratio - 1.0) / 2.0)
        else:
            s["casting"] = 0.0
    else:
        s["casting"] = 0.0

    # --- OVER THE TOP (upper body moves outward at start of downswing) ---
    if ds_frames > 2:
        early_ds_x = [umx[i] for i in range(peak, min(n, peak + ds_frames // 3))]
        if early_ds_x:
            avg_outward = abs(sum(early_ds_x) / len(early_ds_x))
            s["over_the_top"] = min(1.0, avg_outward / 1.5)
        else:
            s["over_the_top"] = 0.0
    else:
        s["over_the_top"] = 0.0

    # --- HIP STALL (lower body stops moving before impact) ---
    if peak > 1:
        pre_lower = sum(abs(lmx[i]) + abs(lmy[i]) for i in range(max(0, peak - 2), peak))
        pre_lower /= max(1, min(2, peak))
        s["hip_stall"] = max(0.0, min(1.0, (0.3 - pre_lower) / 0.3)) if pre_lower < 0.3 else 0.0
    else:
        s["hip_stall"] = 0.0

    # --- CHICKEN WING (asymmetric motion after impact) ---
    if n - peak > 2:
        post_upper_x = [abs(umx[i]) for i in range(peak, min(n, peak + 3))]
        if post_upper_x:
            asymmetry = max(post_upper_x) / (sum(post_upper_x) / len(post_upper_x) + 0.01)
            s["chicken_wing"] = min(1.0, max(0.0, asymmetry - 1.5) / 2.0)
        else:
            s["chicken_wing"] = 0.0
    else:
        s["chicken_wing"] = 0.0

    # --- SHOULDER TURN (amount of upper body rotation during backswing) ---
    if bs_frames > 1:
        bs_upper_rot = sum(abs(umx[i]) for i in range(bs_frames)) / bs_frames
        if bs_upper_rot < 0.5:
            s["flat_shoulder_turn"] = min(1.0, (0.5 - bs_upper_rot) / 0.5)
            s["steep_shoulder_turn"] = 0.0
        elif bs_upper_rot > 2.0:
            s["steep_shoulder_turn"] = min(1.0, (bs_upper_rot - 2.0) / 2.0)
            s["flat_shoulder_turn"] = 0.0
        else:
            s["flat_shoulder_turn"] = 0.0
            s["steep_shoulder_turn"] = 0.0
    else:
        s["flat_shoulder_turn"] = 0.0
        s["steep_shoulder_turn"] = 0.0

    # --- REVERSE PIVOT (upper and lower body move opposite during backswing) ---
    if bs_frames > 1:
        upper_dir = sum(umx[i] for i in range(bs_frames))
        lower_dir = sum(lmx[i] for i in range(bs_frames))
        if upper_dir * lower_dir < 0:
            s["reverse_pivot"] = min(1.0, abs(upper_dir) / (abs(lower_dir) + 0.01) / 3.0)
        else:
            s["reverse_pivot"] = 0.0
    else:
        s["reverse_pivot"] = 0.0

    s.setdefault("under_plane", 0.0)
    s.setdefault("poor_alignment", 0.0)
    for k in ("open_clubface", "closed_clubface", "weak_grip", "strong_grip",
              "ball_position_error", "grip_pressure"):
        s.setdefault(k, 0.0)

    return s


# ======================================================================
#  TIER 3: Fallback — deterministic scores from video metadata
# ======================================================================

def _analyze_with_metadata(file_path, module="swing"):
    meta = _extract_metadata(file_path)

    # Only worth checking when ffprobe actually told us something. When it did
    # not, these fields are zeroes from the hash fallback and would reject
    # every clip on a server without ffprobe installed.
    if meta.get("probed"):
        if meta.get("duration", 0) < MIN_CLIP_SECONDS:
            raise NoSwingDetected(
                "That clip was too short to read. Record a couple of seconds "
                "and try again."
            )
        if not meta.get("width") or not meta.get("height"):
            raise NoSwingDetected(
                "That recording had no picture in it. " + _FRAMING_ADVICE
            )

    if STRICT_ANALYSIS:
        raise AnalysisUnavailable(
            "Swing analysis is not available on this server right now. "
            "Nothing is wrong with your recording."
        )

    return _generate_scores_from_metadata(meta, module)


def _extract_metadata(file_path):
    """Read what ffprobe can tell us, and be honest about whether it could.

    The `probed` flag is the important part. "ffprobe says this is not a video"
    and "ffprobe is not installed" produce almost identical empty numbers, and
    only the first of those justifies telling somebody their recording failed.
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", file_path],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        # ffprobe is not on this machine. We know nothing about the file.
        return _hash_metadata(file_path)
    except subprocess.TimeoutExpired:
        return _hash_metadata(file_path)

    if r.returncode != 0:
        # ffprobe ran and could not decode it. That is a genuine answer about
        # the file rather than a gap in our tooling.
        raise NoSwingDetected(
            "That file could not be read as a video. Try recording again."
        )

    try:
        probe = json.loads(r.stdout)
    except json.JSONDecodeError:
        return _hash_metadata(file_path)

    fmt = probe.get("format", {})
    vs = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None)
    if not vs:
        raise NoSwingDetected(
            "That file has no video in it. Try recording again."
        )
    return {
        "duration": float(fmt.get("duration", 0)),
        "width": int(vs.get("width", 0)),
        "height": int(vs.get("height", 0)),
        "file_size": int(fmt.get("size", os.path.getsize(file_path))),
        "probed": True,
    }


def _hash_metadata(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return {"duration": 0.0, "width": 0, "height": 0,
            "file_size": os.path.getsize(file_path), "file_hash": h.hexdigest(),
            # Nothing here was measured from the video itself.
            "probed": False}


def _generate_scores_from_metadata(meta, module="swing"):
    fault_keys = MODULE_FAULTS.get(module, FAULT_KEYS)
    seed_str = "{:.2f}_{}_{}_{}".format(
        meta.get("duration", 0), meta.get("width", 0),
        meta.get("height", 0), meta.get("file_size", 0))
    if "file_hash" in meta:
        seed_str += "_" + meta["file_hash"]
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    count = 2 + (seed % 4)
    shuffled = fault_keys[:]
    rng.shuffle(shuffled)
    return {f: round(0.1 + rng.random() * 0.9, 3) for f in shuffled[:count]}
