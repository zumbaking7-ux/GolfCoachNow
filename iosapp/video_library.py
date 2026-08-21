"""Which video plays, and when.

Every video URL the apps use is resolved here, so changing where the assets
live - or swapping one clip for a better cut of it - is a change to this file
rather than to three separate apps.

Two lookups:

    instructional_url(module)       the clip that plays before the camera opens
    correction_url(module, fault)   the clip that plays after the engine answers

Both return None when nothing is mapped yet, and None is a real answer rather
than a failure. The apps fall back to the written correction and the rep still
completes. A missing or slow video must never strand somebody mid-rep, which is
the one thing that would make the pipeline feel broken rather than unfinished.
"""

import os

# Where the assets are served from, with no trailing slash.
#
# Kept in the environment because the hosting decision is still open: the videos
# sit on YouTube today and are expected to move onto storage we control, and
# because a staging deployment should never be able to reach production assets
# by accident.
#
# Unset means every lookup returns None, which is the correct behaviour on a
# machine that has no assets rather than a reason to raise.
BASE_URL = os.environ.get("VIDEO_BASE_URL", "").rstrip("/")

# The instructional clip that plays before the camera opens.
#
# Version 1 ships one clip shared by all three modes, per the client. The
# mapping stays per-module anyway so that giving swing its own clip later is a
# one-line change here, with nothing else in the pipeline or the apps touched.
_SHARED_INSTRUCTIONAL = "instructional/all_modes.mp4"

# The two doors onto the swing play different clips, and this is the whole of
# the difference between them.
#
# Swing Learn opens the lesson: a real coach demonstrating grip, stance and the
# full swing, filmed for that screen.
LESSON = {
    "swing": "instructional/learn_swing.mp4",
    "putt": _SHARED_INSTRUCTIONAL,
    "short_game": _SHARED_INSTRUCTIONAL,
}

# Swing Correct opens the general clip before the camera. It covers how to
# frame the shot, which is what somebody about to record needs - not a lesson
# they may have just watched.
INTRO = {
    "swing": _SHARED_INSTRUCTIONAL,
    "putt": _SHARED_INSTRUCTIONAL,
    "short_game": _SHARED_INSTRUCTIONAL,
}

# Kept so nothing that imported the old name breaks. LESSON is what it always
# resolved to.
INSTRUCTIONAL = LESSON

# The correction clip for each mode. This is the whole of Version 1.
#
# Per the correction module spec: one reinforcement clip per mode, reinforcing
# the identity of the correction rather than the specific fault. The engine
# still names a specific fault and returns its own correction text; the video
# deliberately does not branch on it.
#
# Filenames are exactly as the client is delivering them, including
# "shortgame" here against the "short_game" module key everywhere else.
CORRECTION_BY_MODE = {
    "swing": "correction/swing_correction.mp4",
    "putt": "correction/putt_correction.mp4",
    "short_game": "correction/shortgame_correction.mp4",
}

# Version 2: a dedicated clip per fault, keyed by (module, fault name).
#
# Empty for V1 and meant to stay that way. Anything added here wins over the
# per-mode clip above, so expanding to fault-specific coaching later is a
# matter of dropping in files and listing them - no change to the pipeline, and
# no flag day where all sixty have to exist at once.
CORRECTION = {}


def _resolve(path):
    """Turn a stored path into something an app can actually play."""
    if not path:
        return None
    # An absolute URL is passed through untouched, so a single clip can be
    # pointed at a different host without moving the rest.
    if path.startswith(("http://", "https://")):
        return path
    if not BASE_URL:
        return None
    return BASE_URL + "/" + path


def instructional_url(module, screen="learn"):
    """The clip that plays when someone taps one of the two swing buttons.

    `screen` is which button they tapped, "learn" or "correct". It defaults to
    "learn" on purpose: builds already in testers' hands ask without it, and
    that is the behaviour they were shipped with. A default that changed under
    them would alter an installed app from the server.
    """
    table = INTRO if screen == "correct" else LESSON
    return _resolve(table.get(module))


def correction_url(module, fault):
    """The reinforcement clip that plays once a rep has been analysed.

    In Version 1 this is decided by mode alone. The `fault` argument is read
    only so that Version 2 can start returning fault-specific clips without the
    callers, the response shape or the apps changing at all.

    Returns None when nothing is published, so the caller always gets either a
    playable URL or a clear absence.
    """
    if fault:
        specific = CORRECTION.get((module, fault))
        if specific:
            return _resolve(specific)
    return _resolve(CORRECTION_BY_MODE.get(module))
