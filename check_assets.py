"""Do the video assets on disk match what the code will ask for?

Assets arrive in stages, so this is worth re-running each time a batch lands.
It reads the paths straight out of video_library rather than repeating them, so
it cannot drift from what the server will actually request.

    python3 check_assets.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "iosapp"))

import video_library  # noqa: E402

ASSETS = os.path.join(HERE, "assets", "videos")

MODULES = ["swing", "putt", "short_game"]


def relative_path(url_path):
    """video_library stores paths relative to VIDEO_BASE_URL."""
    return url_path.replace("/", os.sep)


def check(label, stored_path):
    if not stored_path:
        print("  %-14s %-42s NOT MAPPED" % (label, "-"))
        return False, 0
    full = os.path.join(ASSETS, relative_path(stored_path))
    if os.path.exists(full):
        size = os.path.getsize(full)
        print("  %-14s %-42s %6.1f MB" % (label, stored_path, size / 1_048_576))
        return True, size
    print("  %-14s %-42s MISSING" % (label, stored_path))
    return False, 0


total_bytes = 0
present = 0
expected = 0

print("Instructional clips (play before the camera opens)")
for m in MODULES:
    expected += 1
    ok, size = check(m, video_library.INSTRUCTIONAL.get(m))
    present += ok
    total_bytes += size

print()
print("Correction clips, Version 1 (play after a rep)")
for m in MODULES:
    expected += 1
    ok, size = check(m, video_library.CORRECTION_BY_MODE.get(m))
    present += ok
    total_bytes += size

if video_library.CORRECTION:
    print()
    print("Correction clips, Version 2 (per fault)")
    for (m, fault), path in sorted(video_library.CORRECTION.items()):
        expected += 1
        ok, size = check("%s/%s" % (m, fault), path)
        present += ok
        total_bytes += size

print()
print("-" * 66)
print("%d of %d present, %.1f MB total" % (present, expected, total_bytes / 1_048_576))

if present == expected:
    print("Complete. Ready to publish and set VIDEO_BASE_URL.")
else:
    print("Incomplete. Missing clips fall back gracefully: the apps skip")
    print("straight to the camera rather than stalling, so this is shippable")
    print("but not finished.")
