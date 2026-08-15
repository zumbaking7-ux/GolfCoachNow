# ============================================
#   GOLF COACH NOW — COMPLETE PUTT ENGINE V1
# ============================================

# --------------------------------------------
# 1. Correction Dictionary (20 deterministic cues)
# --------------------------------------------

CORRECTIONS = {
    "poor_alignment": "If your alignment is off, set your putter face square to the target line before settling your stance.",
    "deceleration": "If you decelerate through the ball, make your through-stroke at least as long as your backswing.",
    "wrist_breakdown": "If your wrists break down, keep them firm and rock the stroke from your shoulders.",
    "poor_speed_control": "If your speed is off, focus on the length of your backstroke — longer stroke means more roll.",
    "head_movement": "If your head moves, keep your eyes still and listen for the ball to drop instead of watching it.",
    "open_face_at_impact": "If the face is open at impact, check your grip pressure and square the face through the stroke.",
    "closed_face_at_impact": "If the face is closed at impact, lighten your trail-hand pressure and let the putter swing naturally.",
    "poor_aim": "If your aim is poor, pick a spot six inches ahead of the ball on your target line and roll over it.",
    "inconsistent_strike": "If your strike is inconsistent, focus on hitting the sweet spot — mark a dot on the ball to track contact.",
    "too_wristy": "If your stroke is too wristy, feel the triangle formed by your shoulders and arms stay intact.",
    "backstroke_too_long": "If your backstroke is too long, shorten it and accelerate smoothly through the ball.",
    "poor_green_read": "If your green reads are off, walk behind the ball and read the slope from low to high.",
    "stance_too_wide": "If your stance is too wide, narrow it to shoulder width for better rotation and feel.",
    "stance_too_narrow": "If your stance is too narrow, widen it slightly for more stability over the ball.",
    "ball_position_error": "If your ball position is wrong, place it just forward of center under your lead eye.",
    "grip_pressure_too_tight": "If your grip is too tight, hold the putter like you are holding a bird — firm but gentle.",
    "poor_distance_control": "If your distance control is poor, practice lag putts with your eyes on the hole, not the ball.",
    "pushing_putts": "If you push putts right, check that your shoulders are square and the path is straight back and through.",
    "pulling_putts": "If you pull putts left, make sure you are not rotating your forearms through impact.",
    "yips": "If you have the yips, try a different grip style — claw or cross-handed can break the pattern."
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

def normalize_scores(putt_data: dict) -> dict:
    if not putt_data:
        return {}
    max_score = max(putt_data.values())
    if max_score == 0:
        return putt_data
    return {fault: score / max_score for fault, score in putt_data.items()}

# --------------------------------------------
# 5. Dominant Fault Selector
# --------------------------------------------

def analyze(putt_data: dict) -> str:
    if not putt_data:
        return None
    normalized = normalize_scores(putt_data)
    return max(normalized, key=normalized.get)

# --------------------------------------------
# 6. Full NOW Engine Output
# --------------------------------------------

def putt(putt_data: dict) -> dict:
    rep = increment_rep()
    fault = analyze(putt_data)
    correction = get_correction(fault)

    return {
        "rep": rep,
        "dominant_fault": fault,
        "correction": correction,
        "normalized_scores": normalize_scores(putt_data),
        "status": "ok"
    }

# --------------------------------------------
# 7. Mobile Input Wrapper (Android/iOS)
# --------------------------------------------

def process_mobile_input(raw_scores: dict) -> dict:
    return putt(raw_scores)

# --------------------------------------------
# 8. Multi-Putt Session Loop
# --------------------------------------------

def run_session(putts: list) -> list:
    results = []
    for p in putts:
        results.append(process_mobile_input(p))
    return results
