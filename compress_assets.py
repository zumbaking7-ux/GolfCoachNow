"""Compress the delivered videos for phone playback.

Reads from assets/videos/_originals/ and writes the versions the app serves.
Originals are never touched, so any of this can be redone.

Three things matter here beyond making the files smaller:

  faststart   moves the index to the front of the file so a phone can start
              playing before the download finishes. Without it a three minute
              clip is three minutes of nothing happening.

  CRF         quality-targeted rather than bitrate-targeted, so a still talking
              head costs fewer bytes than a fast swing without either looking
              worse.

  1920 cap    a 1440x2560 master is more pixels than any phone screen resolves.
              Capping the long edge is free quality-wise and halves the size.

    python3 compress_assets.py
"""

import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets", "videos")
ORIGINALS = os.path.join(ASSETS, "_originals")

# Higher CRF is smaller. 23 is visually lossless, 28 starts to show on detail.
# 26 for the short correction clips, a little more for the long instructional
# one where the saving is worth most and the subject barely moves.
JOBS = [
    ("swing_correction.mp4",     "correction/swing_correction.mp4",     26),
    ("putt_correction.mp4",      "correction/putt_correction.mp4",      26),
    ("shortgame_correction.mp4", "correction/shortgame_correction.mp4", 26),
    ("all_modes.mp4",            "instructional/all_modes.mp4",         28),
]


def find(tool):
    found = shutil.which(tool)
    if found:
        return found
    pattern = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "*", "bin", tool + ".exe",
    )
    hits = glob.glob(pattern)
    return hits[0] if hits else None


FFMPEG = find("ffmpeg")
if not FFMPEG:
    sys.exit("ffmpeg not found.")

total_before = total_after = 0

for source_name, target_rel, crf in JOBS:
    source = os.path.join(ORIGINALS, source_name)
    target = os.path.join(ASSETS, target_rel.replace("/", os.sep))

    if not os.path.exists(source):
        print("SKIP  %-30s no master in _originals" % source_name)
        continue

    os.makedirs(os.path.dirname(target), exist_ok=True)
    before = os.path.getsize(source)

    result = subprocess.run(
        [
            FFMPEG, "-y", "-loglevel", "error", "-i", source,
            # Cap the long edge at 1920 and keep dimensions even, which h264
            # requires. Never upscales.
            "-vf", "scale='min(1080,iw)':'min(1920,ih)':force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-crf", str(crf), "-preset", "slow",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            target,
        ],
        capture_output=True, text=True, timeout=3600,
    )
    if result.returncode != 0:
        print("FAIL  %-30s %s" % (source_name, result.stderr.strip()[:160]))
        continue

    after = os.path.getsize(target)
    total_before += before
    total_after += after
    print("  %-30s %6.1f MB -> %5.1f MB  (%.0f%% smaller)" % (
        source_name, before / 1_048_576, after / 1_048_576,
        (1 - after / before) * 100))

print()
if total_before:
    print("Total %.1f MB -> %.1f MB, saving %.1f MB (%.0f%%)" % (
        total_before / 1_048_576, total_after / 1_048_576,
        (total_before - total_after) / 1_048_576,
        (1 - total_after / total_before) * 100))
