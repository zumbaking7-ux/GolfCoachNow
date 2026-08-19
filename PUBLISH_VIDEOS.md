# Publishing the video assets

Four files, 28 MB total. Videos are gitignored — too large for the repository
and they belong on the host that serves them — so these are uploaded directly
rather than deployed with the code.

Once this is done the whole four-wire pipeline is live: tap an engine, watch the
instructional clip, record, get a correction video back.

---

## 1. Make the folders on the server

PythonAnywhere **Bash console**:

```
mkdir -p /home/golfcoachnow/mysite/static/videos/instructional
mkdir -p /home/golfcoachnow/mysite/static/videos/correction
ls -la /home/golfcoachnow/mysite/static/videos/
```

---

## 2. Upload the four files

PythonAnywhere **Files** tab → navigate to
`/home/golfcoachnow/mysite/static/videos/`

Into `instructional/`:

| File | Size |
| --- | --- |
| `all_modes.mp4` | 21.1 MB |

Into `correction/`:

| File | Size |
| --- | --- |
| `swing_correction.mp4` | 2.4 MB |
| `putt_correction.mp4` | 2.4 MB |
| `shortgame_correction.mp4` | 2.1 MB |

They are on your machine at
`C:\Users\DELL\Downloads\GolfCoachNow\assets\videos\`.

**The filenames must match exactly**, including `shortgame_correction.mp4` with
no underscore between "short" and "game" while the instructional folder uses
`all_modes.mp4` with one. That is not a typo: the correction names came from the
client's spec and the code matches them literally.

---

## 3. Check they are actually served

```
for f in instructional/all_modes.mp4 correction/swing_correction.mp4 \
         correction/putt_correction.mp4 correction/shortgame_correction.mp4; do
  printf "%-46s " "$f"
  curl -s -o /dev/null -w "%{http_code}  %{size_download} bytes\n" \
    "https://golfcoachnow.pythonanywhere.com/static/videos/$f"
done
```

All four must return **200**. A 404 means either the filename does not match or
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
