# Publishing the video assets

**Two files, 15 MB total.** Only Swing is reachable in Version 1, so only the
two clips on that path need to go up. The putt and short game clips stay
staged locally until those modes come back in Version 2.

Videos are gitignored — too large for the repository, and they belong on the
host that serves them — so these are uploaded directly rather than deployed
with the code.

Once this is done the pipeline is live end to end: tap Swing Learn and watch
the lesson, tap Swing Correct and record, get a correction video back.

---

## 1. Make the folders on the server

PythonAnywhere **Bash console**:

```
mkdir -p /home/golfcoachnow/mysite/static/videos/instructional
mkdir -p /home/golfcoachnow/mysite/static/videos/correction
ls -la /home/golfcoachnow/mysite/static/videos/
```

---

## 2. Upload the two files

PythonAnywhere **Files** tab → navigate to
`/home/golfcoachnow/mysite/static/videos/`

Into `instructional/`:

| File | Size | |
| --- | --- | --- |
| `learn_swing.mp4` | 12.4 MB | Victor's lesson, plays on Swing Learn |

Into `correction/`:

| File | Size | |
| --- | --- | --- |
| `swing_correction.mp4` | 2.4 MB | plays after a swing is analysed |

They are on your machine at
`C:\Users\DELL\Downloads\GolfCoachNow\assets\videos\`.

**The filenames must match exactly.** `video_library.py` resolves them
literally, so a rename here means a code change too.

---

## 3. Check they are actually served

```
for f in instructional/learn_swing.mp4 correction/swing_correction.mp4; do
  printf "%-46s " "$f"
  curl -s -o /dev/null -w "%{http_code}  %{size_download} bytes\n" \
    "https://golfcoachnow.pythonanywhere.com/static/videos/$f"
done
```

Both must return **200**. A 404 means either the filename does not match or
`/static/` is not mapped to that folder — check the Web tab's static files
mapping before going further.

---

## 4. Point the app at them

The `.env` loading on this host has proved unreliable, so this goes in the WSGI
file alongside the other settings, where it is read at process start regardless
of working directory.

Web tab → **WSGI configuration file** → add near the top, beside the existing
`EMAIL_FROM` line:

```python
os.environ["VIDEO_BASE_URL"] = "https://golfcoachnow.pythonanywhere.com/static/videos"
```

**No trailing slash.** The code appends one.

Save → Web tab → **Reload**.

---

## 5. Confirm

```
curl -s "https://golfcoachnow.pythonanywhere.com/videos/instructional?module=swing" ; echo
curl -s "https://golfcoachnow.pythonanywhere.com/videos/instructional?module=putt" ; echo
```

Both should now return the `all_modes.mp4` URL rather than `null` — the same
clip for every mode, which is the Version 1 design.

Then in a browser: open the web app, tap **Swing**, and the instructional clip
should play and hand off to the camera when it ends.

---

## Rolling it back

Remove the `VIDEO_BASE_URL` line from the WSGI file and reload. Every lookup
returns `null` again, the apps skip straight to the camera, and the written
correction still comes back. The files can stay where they are.
