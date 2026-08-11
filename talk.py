"""Talk Mode — maps natural language to golf fault corrections.

Takes free-text input (typically from speech recognition), identifies
which fault the user is describing, and returns the matching correction
from the appropriate module engine.
"""

from wedge import CORRECTIONS as SWING_CORRECTIONS
from putt import CORRECTIONS as PUTT_CORRECTIONS
from chip import CORRECTIONS as CHIP_CORRECTIONS

MODULE_CORRECTIONS = {
    "swing": SWING_CORRECTIONS,
    "putt": PUTT_CORRECTIONS,
    "short_game": CHIP_CORRECTIONS,
}

KEYWORD_MAP = {
    "swing": {
        "open_clubface": ["open face", "open clubface", "face is open", "clubface open", "slicing", "slice", "fading too much", "ball goes right"],
        "closed_clubface": ["closed face", "closed clubface", "face is closed", "clubface closed", "hooked", "hooking", "ball goes left", "pulling left"],
        "weak_grip": ["weak grip", "grip is weak", "grip weak", "grip too weak", "grip is too weak"],
        "strong_grip": ["strong grip", "grip is strong", "grip strong", "grip too strong", "grip is too strong"],
        "over_the_top": ["over the top", "outside in", "come over", "coming over", "outside", "cutting across"],
        "under_plane": ["under plane", "under the plane", "too flat", "too inside", "dropping under"],
        "early_extension": ["early extension", "early extend", "stand up", "standing up", "thrust", "humping", "losing posture"],
        "casting": ["casting", "cast the club", "release too early", "early release", "throwing", "releasing early"],
        "chicken_wing": ["chicken wing", "bent arm", "lead arm bends", "elbow out", "arm bending"],
        "reverse_pivot": ["reverse pivot", "weight forward", "falling back", "lean forward", "weight on front foot"],
        "sway": ["sway", "swaying", "sliding back", "lateral movement back"],
        "slide": ["slide", "sliding forward", "sliding toward", "lateral slide"],
        "spine_angle_loss": ["spine angle", "lose spine", "posture", "standing up early", "losing angle"],
        "tempo_imbalance": ["tempo", "rhythm", "too fast", "too quick", "rushing", "jerky"],
        "poor_alignment": ["alignment", "aimed wrong", "aiming", "lined up wrong", "setup wrong"],
        "ball_position_error": ["ball position", "ball too far", "ball too forward", "ball too back"],
        "grip_pressure": ["grip pressure", "gripping too hard", "holding too tight", "grip too tight", "death grip"],
        "hip_stall": ["hip stall", "hips stop", "hips stall", "no hip rotation", "hips not turning"],
        "flat_shoulder_turn": ["flat shoulder", "shoulder flat", "not turning enough"],
        "steep_shoulder_turn": ["steep shoulder", "shoulder steep", "dipping", "shoulder dip"],
    },
    "putt": {
        "poor_alignment": ["alignment", "aimed wrong", "aiming off", "lined up wrong"],
        "deceleration": ["decelerate", "decelerating", "deceleration", "slow down", "slowing down", "quitting", "stop at ball"],
        "wrist_breakdown": ["wrist breakdown", "wrist break", "wrists break", "flippy", "wristy"],
        "poor_speed_control": ["speed control", "too fast", "too slow", "pace", "speed is off"],
        "head_movement": ["head movement", "head moves", "looking up", "look up", "peeking", "moving head", "lifting head", "head up too early", "head up"],
        "open_face_at_impact": ["open face", "face open", "miss right", "pushing"],
        "closed_face_at_impact": ["closed face", "face closed", "miss left", "pulling face"],
        "poor_aim": ["aim", "aiming", "can't aim", "aim is off"],
        "inconsistent_strike": ["inconsistent", "miss hit", "mishit", "thin", "fat", "off center"],
        "too_wristy": ["too wristy", "wrists", "hands", "handsy"],
        "backstroke_too_long": ["backstroke long", "back too far", "too long back"],
        "poor_green_read": ["green read", "reading green", "read the green", "break", "slope"],
        "stance_too_wide": ["stance wide", "too wide", "feet too wide"],
        "stance_too_narrow": ["stance narrow", "too narrow", "feet too close"],
        "ball_position_error": ["ball position", "ball too far", "ball placement"],
        "grip_pressure_too_tight": ["grip tight", "grip pressure", "squeezing", "holding too tight"],
        "poor_distance_control": ["distance control", "distance", "lag", "leave short", "too far past"],
        "pushing_putts": ["push", "pushing", "miss right", "goes right"],
        "pulling_putts": ["pull", "pulling", "miss left", "goes left"],
        "yips": ["yips", "twitch", "flinch", "nervous", "jerk"],
    },
    "short_game": {
        "flipping": ["flipping", "flip", "hands flip", "scooping up"],
        "scooping": ["scooping", "scoop", "trying to lift", "lifting"],
        "poor_ball_position": ["ball position", "ball too far", "ball placement"],
        "no_weight_forward": ["weight forward", "weight back", "leaning back", "no weight shift"],
        "too_much_wrist": ["too much wrist", "wristy", "hands", "handsy"],
        "decelerating": ["decelerate", "decelerating", "quitting", "slow down", "giving up", "stop at ball"],
        "poor_club_selection": ["wrong club", "club selection", "which club", "club choice"],
        "fat_contact": ["fat", "chunky", "chunk", "dig", "heavy", "behind ball"],
        "thin_contact": ["thin", "blade", "skull", "top", "topped", "belly"],
        "poor_distance_control": ["distance", "too far", "too short", "distance control"],
        "open_clubface": ["open face", "face open", "going right"],
        "closed_clubface": ["closed face", "face closed", "going left"],
        "poor_trajectory": ["trajectory", "too high", "too low", "flight", "balloon"],
        "no_bounce_use": ["bounce", "not using bounce", "digging", "leading edge"],
        "steep_attack": ["steep", "too steep", "chopping", "digging down"],
        "shallow_attack": ["shallow", "too shallow", "picking", "thin contact"],
        "poor_landing_spot": ["landing spot", "where to land", "landing zone", "target spot"],
        "poor_setup": ["setup", "address", "stance", "position"],
        "no_follow_through": ["follow through", "no finish", "stopping", "abbreviating"],
        "tension": ["tension", "tight", "tense", "stressed", "stiff", "rigid"],
    },
}


def process_talk(text: str, module: str = "swing") -> dict:
    corrections = MODULE_CORRECTIONS.get(module, SWING_CORRECTIONS)
    keywords = KEYWORD_MAP.get(module, KEYWORD_MAP["swing"])
    text_lower = text.lower()

    best_fault = None
    best_score = 0

    for fault, phrases in keywords.items():
        for phrase in phrases:
            if phrase in text_lower:
                score = len(phrase)
                if score > best_score:
                    best_score = score
                    best_fault = fault

    if best_fault and best_fault in corrections:
        return {
            "fault": best_fault,
            "correction": corrections[best_fault],
            "module": module,
            "matched": True,
        }

    return {
        "fault": None,
        "correction": f"I didn't catch a specific {module} issue. Try describing what happens to your ball or what your body does during the swing.",
        "module": module,
        "matched": False,
    }
