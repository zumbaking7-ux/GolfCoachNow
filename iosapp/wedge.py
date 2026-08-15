# ============================================
#   GOLF COACH NOW — COMPLETE WEDGE ENGINE V1
# ============================================

# --------------------------------------------
# 1. Correction Dictionary (20 deterministic cues)
# --------------------------------------------

CORRECTIONS = {
    "open_clubface": "If the face is open, strengthen your lead-hand grip and square the face earlier.",
    "closed_clubface": "If the face is closed, weaken your lead-hand grip and feel the face stay neutral longer.",
    "weak_grip": "If your grip is weak, rotate your lead hand so two to three knuckles are visible.",
    "strong_grip": "If your grip is strong, rotate your lead hand slightly counterclockwise to neutralize the face.",
    "over_the_top": "If you’re coming over-the-top, feel the trail elbow tuck and swing from the inside.",
    "under_plane": "If you’re under-plane, feel the lead shoulder work down and the club move up the plane.",
    "early_extension": "If you early-extend, keep your hips back and maintain your spine angle through impact.",
    "casting": "If you’re casting the club, hold the wrist hinge longer and let it release naturally.",
    "chicken_wing": "If you chicken-wing, extend your lead arm through impact and rotate fully.",
    "reverse_pivot": "If you reverse-pivot, shift pressure into your trail side on the backswing.",
    "sway": "If you sway off the ball, turn around your spine instead of sliding laterally.",
    "slide": "If you slide toward the target, rotate your hips instead of driving them forward.",
    "spine_angle_loss": "If you lose spine angle, keep your chest down and rotate around a stable axis.",
    "tempo_imbalance": "If your tempo is off, smooth the transition and match backswing and downswing rhythm.",
    "poor_alignment": "If your alignment is poor, square your feet, hips, and shoulders to the target line.",
    "ball_position_error": "If your ball position is wrong, adjust it relative to the club: forward for long, center for mid, back for short.",
    "grip_pressure": "If your grip pressure is off, hold the club lightly enough to stay relaxed but firm enough to control the face.",
    "hip_stall": "If your hips stall, keep rotating through impact and let the chest follow.",
    "flat_shoulder_turn": "If your shoulder turn is flat, feel the lead shoulder move down and under your chin.",
    "steep_shoulder_turn": "If your shoulder turn is steep, feel the shoulders rotate more level around your spine."
}

# --------------------------------------------
# 2. Correction Lookup
# --------------------------------------------

def get_correction(fault: str) -> str:
    return CORRECTIONS.get(fault, "No correction available for this fault.")

# --------------------------------------------
# 3. Rep Counter (simple persistence)
# --------------------------------------------

REP_COUNTER = {"count": 0}

def increment_rep():
    REP_COUNTER["count"] += 1
    return REP_COUNTER["count"]

# --------------------------------------------
# 4. Normalize Scores (camera-ready)
# --------------------------------------------

def normalize_scores(swing_data: dict) -> dict:
    if not swing_data:
        return {}
    max_score = max(swing_data.values())
    if max_score == 0:
        return swing_data
    return {fault: score / max_score for fault, score in swing_data.items()}

# --------------------------------------------
# 5. Dominant Fault Selector
# --------------------------------------------

def analyze(swing_data: dict) -> str:
    if not swing_data:
        return None
    normalized = normalize_scores(swing_data)
    return max(normalized, key=normalized.get)

# --------------------------------------------
# 6. Full NOW Engine Output
# --------------------------------------------

def wedge(swing_data: dict) -> dict:
    rep = increment_rep()
    fault = analyze(swing_data)
    correction = get_correction(fault)

    return {
        "rep": rep,
        "dominant_fault": fault,
        "correction": correction,
        "normalized_scores": normalize_scores(swing_data),
        "status": "ok"
    }

# --------------------------------------------
# 7. Mobile Input Wrapper (Android/iOS)
# --------------------------------------------

def process_mobile_input(raw_scores: dict) -> dict:
    return wedge(raw_scores)

# --------------------------------------------
# 8. Multi‑Swing Session Loop
# --------------------------------------------

def run_session(swings: list) -> list:
    results = []
    for swing in swings:
        results.append(process_mobile_input(swing))
    return results
