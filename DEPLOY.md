# Deploying the V1 pipeline to production

Production is `/home/golfcoachnow/mysite/`, which runs the `iosapp/` tree. The
clone at `~/GolfCoachNow` is a stale copy of the root tree and serves nothing —
do not deploy from it.

Run these in a PythonAnywhere **Bash console**, one block at a time, checking
the output of each before moving on.

---

## 1. Back up what is running

```
cd /home/golfcoachnow
tar -czf mysite-backup-$(date +%Y%m%d-%H%M).tar.gz \
    mysite/server.py mysite/video_analyzer.py mysite/payments
ls -lh mysite-backup-*.tar.gz
```

This is the rollback. Confirm the file exists and is non-zero before continuing.

---

## 2. Fetch the branch into a scratch directory

```
cd /home/golfcoachnow
rm -rf deploy-tmp
git clone -q -b v1-pipeline https://github.com/zumbaking7-ux/GolfCoachNow.git deploy-tmp
cd deploy-tmp && git log --oneline -1 && cd ..
```

A fresh clone rather than pulling the stale one, so there is no chance of
picking up the wrong tree.

---

## 3. Copy the files, dependencies first

`server.py` imports the other three, so it goes last. If anything interrupts
the copy, the app keeps running the old `server.py` and nothing breaks.

```
cd /home/golfcoachnow
cp deploy-tmp/iosapp/video_library.py            mysite/
cp deploy-tmp/iosapp/payments/contact_routes.py  mysite/payments/
cp deploy-tmp/iosapp/payments/config.py          mysite/payments/
cp deploy-tmp/iosapp/payments/email_sender.py    mysite/payments/
cp deploy-tmp/iosapp/video_analyzer.py           mysite/
cp deploy-tmp/iosapp/server.py                   mysite/
echo "copied"
```

**No `.env` changes are needed.** Every new setting has a working default:
`VIDEO_BASE_URL` empty means no videos are published yet, `STRICT_ANALYSIS`
defaults to false, `FOUNDER_EMAIL` already defaults to the right address, and
`APP_SHARE_URL` empty makes `/share/invite` answer 503 rather than mail anyone a
link that does not exist.

---

## 4. Verify it imports before reloading

```
cd /home/golfcoachnow/mysite
python3 -c "import server; print('server imports cleanly')"
python3 -c "import video_library; print('video_library OK')"
python3 -c "from payments.contact_routes import router; print('contact routes OK')"
```

**If any of these fail, stop and roll back — do not reload.** A broken import
takes the whole site down, `/upload` and `/wedge` included, not just the new
endpoints.

---

## 5. Reload

Web tab → **Reload**.

---

## 6. Smoke test

```
curl -s "https://golfcoachnow.pythonanywhere.com/" ; echo
curl -s "https://golfcoachnow.pythonanywhere.com/videos/instructional?module=swing" ; echo
curl -s "https://golfcoachnow.pythonanywhere.com/payments/unlock-status?device_id=deploy_check" ; echo
```

Expected:

- health returns `{"status":"ok",...}`
- the video endpoint returns `{"module":"swing","url":null}` — `null` is correct,
  it means no assets are published yet
- unlock-status returns JSON, which proves the payments routes still loaded

A 404 on the last one means the payments package failed to import and the
payment routes are silently gone. That is the failure mode the deployment doc
warns about, and it looks completely healthy from the front page.

---

## Rollback

```
cd /home/golfcoachnow
tar -xzf mysite-backup-<the one you made>.tar.gz
```

Then reload. That restores `server.py`, `video_analyzer.py` and the whole
`payments/` package to exactly what was running before.

The two new files (`video_library.py`, `payments/contact_routes.py`) are left
behind by the rollback, which is harmless — nothing imports them once the old
`server.py` is back.

---

## What this deploy changes in production

- Adds `GET /videos/instructional`, and `correction_video_url` on every analysis
  response
- Adds `POST /share/invite` and `POST /connect/founder`
- Stops the analyser inventing coaching for clips it cannot read, and returns a
  plain retry message instead
- Stops an unreadable clip spending one of the three free daily reps

## What it does not change

- No database migration. The schema is untouched.
- No `.env` changes.
- No behaviour change for a clip that analyses normally.
