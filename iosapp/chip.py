# ============================================
#   GOLF COACH NOW — COMPLETE SHORT GAME ENGINE V1
# ============================================

# --------------------------------------------
# 1. Correction Dictionary (20 deterministic cues)
# --------------------------------------------

CORRECTIONS = {
    "flipping": "If you flip the clubhead past your hands, keep your lead wrist flat through impact.",
    "scooping": "If you scoop the ball, press the shaft forward at address and maintain that angle through impact.",
    "poor_ball_position": "If your ball position is wrong, play chips back of center and pitches just forward of center.",
    "no_weight_forward": "If your weight drifts back, set sixty percent of your weight on your lead foot and keep it there.",
    "too_much_wrist": "If your wrists are too active, chip with a putting stroke — arms and shoulders only.",
    "decelerating": "If you decelerate, commit to a shorter backswing and accelerate through the ball.",
    "poor_club_selection": "If your club selection is off, use less loft when you can — bump and run beats a flop most times.",
    "fat_contact": "If you hit it fat, move the ball back in your stance and lean the shaft toward the target.",
    "thin_contact": "If you hit it thin, keep your chest rotating through impact instead of standing up.",
    "poor_distance_control": "If your distance control is poor, vary the length of your backswing, not your speed.",
    "open_clubface": "If the face is open, square it at address and keep your hands ahead through the strike.",
    "closed_clubface": "If the face is closed, check your grip — a neutral grip prevents the face from shutting down.",
    "poor_trajectory": "If your trajectory is wrong, adjust ball position and shaft lean — forward lean equals lower flight.",
    "no_bounce_use": "If you dig into the turf, use the bounce — open the face slightly and let the sole glide.",
    "steep_attack": "If your attack is too steep, feel the club sweep low through impact instead of chopping down.",
    "shallow_attack": "If your attack is too shallow, set the shaft slightly forward and strike ball then turf.",
    "poor_landing_spot": "If you miss your landing spot, pick a specific target on the green and fly the ball to it.",
    "poor_setup": "If your setup is off, narrow your stance, open it slightly, and grip down for control.",
    "no_follow_through": "If you quit on the shot, match your follow-through length to your backswing length.",
    "tension": "If you are tense over chips, soften your grip pressure and breathe before you swing."
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

def normalize_scores(chip_data: dict) -> dict:
    if not chip_data:
        return {}
    max_score = max(chip_data.values())
    if max_score == 0:
        return chip_data
    return {fault: score / max_score for fault, score in chip_data.items()}

# --------------------------------------------
# 5. Dominant Fault Selector
# --------------------------------------------

def analyze(chip_data: dict) -> str:
    if not chip_data:
        return None
    normalized = normalize_scores(chip_data)
    return max(normalized, key=normalized.get)

# --------------------------------------------
# 6. Full NOW Engine Output
# --------------------------------------------

def chip(chip_data: dict) -> dict:
    rep = increment_rep()
    fault = analyze(chip_data)
    correction = get_correction(fault)

    return {
        "rep": rep,
        "dominant_fault": fault,
        "correction": correction,
        "normalized_scores": normalize_scores(chip_data),
        "status": "ok"
    }

# --------------------------------------------
# 7. Mobile Input Wrapper (Android/iOS)
# --------------------------------------------

def process_mobile_input(raw_scores: dict) -> dict:
    return chip(raw_scores)

# --------------------------------------------
# 8. Multi-Chip Session Loop
# --------------------------------------------

def run_session(chips: list) -> list:
    results = []
    for c in chips:
        results.append(process_mobile_input(c))
    return results
