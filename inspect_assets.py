"""Inspect every delivered video: is it sound, and is it the right shape?

Covers the two things that actually matter before launch. First, integrity -
the client raised corruption as a concern, and a clip that fails to decode
should be found here rather than on stage. Second, weight: a phone on hotel
wifi has to download the whole clip before it plays, so bitrate is a user
experience problem, not a storage one.

    python3 inspect_assets.py
"""

import glob
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets", "videos")

# Sensible ceiling for phone playback. Above this the clip is bigger than it
# needs to look good on a handset, and every megabyte is delay before it plays.
TARGET_BITRATE_MBPS = 2.5

# The correction module spec calls for 10-20 seconds.
SPEC_MIN_SECONDS, SPEC_MAX_SECONDS = 10, 20


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


FFPROBE = find("ffprobe")
if not FFPROBE:
    sys.exit("ffprobe not found. Install ffmpeg first.")


def probe(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        return None, out.stderr.strip()[:200]
    return json.loads(out.stdout), None


def decode_check(path):
    """Actually decode every frame. This is what catches real corruption.

    Reading the container header only proves the file is labelled correctly.
    A truncated or damaged clip will read fine and then fail partway through
    playback, which is exactly the failure worth finding now.
    """
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=600,
    )
    errors = out.stderr.strip()
    frames = out.stdout.strip().rstrip(",")
    return frames, errors


files = sorted(
    p for p in glob.glob(os.path.join(ASSETS, "**", "*.*"), recursive=True)
    if p.lower().endswith((".mp4", ".mov", ".m4v", ".webm"))
)

if not files:
    sys.exit("No video files found under %s" % ASSETS)

print("Inspecting %d file(s)\n" % len(files))

problems = []
savings = 0

for path in files:
    rel = os.path.relpath(path, ASSETS)
    info, err = probe(path)
    print("=" * 70)
    print(rel)
    if err:
        print("  UNREADABLE: %s" % err)
        problems.append((rel, "will not probe"))
        continue

    fmt = info.get("format", {})
    video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    audio = next((s for s in info["streams"] if s.get("codec_type") == "audio"), None)

    if not video:
        print("  NO VIDEO STREAM")
        problems.append((rel, "no video stream"))
        continue

    size = int(fmt.get("size", os.path.getsize(path)))
    duration = float(fmt.get("duration", 0) or 0)
    mbps = (size * 8 / duration / 1_000_000) if duration else 0

    print("  codec      %s / %s" % (video.get("codec_name"),
                                    audio.get("codec_name") if audio else "NO AUDIO"))
    print("  resolution %sx%s" % (video.get("width"), video.get("height")))
    print("  duration   %.1f s" % duration)
    print("  size       %.1f MB" % (size / 1_048_576))
    print("  bitrate    %.1f Mbps" % mbps)

    frames, decode_errors = decode_check(path)
    if decode_errors:
        print("  DECODE ERRORS: %s" % decode_errors[:200])
        problems.append((rel, "decode errors"))
    else:
        print("  decode     OK, %s frames read cleanly" % frames)

    if not audio:
        print("  WARNING    no audio track - these clips are spoken coaching")
        problems.append((rel, "no audio"))

    if duration and not (SPEC_MIN_SECONDS <= duration <= SPEC_MAX_SECONDS):
        print("  NOTE       spec asks for %d-%d s" % (SPEC_MIN_SECONDS, SPEC_MAX_SECONDS))

    if mbps > TARGET_BITRATE_MBPS and duration:
        would_be = TARGET_BITRATE_MBPS * duration * 1_000_000 / 8
        savings += size - would_be
        print("  NOTE       %.1fx heavier than needed for phone playback"
              % (mbps / TARGET_BITRATE_MBPS))

print("=" * 70)
print()
if problems:
    print("PROBLEMS FOUND:")
    for rel, what in problems:
        print("  %-46s %s" % (rel, what))
else:
    print("All files decode cleanly. No corruption.")

if savings > 0:
    print()
    print("Compressing to %.1f Mbps would save about %.0f MB across the set,"
          % (TARGET_BITRATE_MBPS, savings / 1_048_576))
    print("which is download time before a clip starts playing.")
