# Deploying to production

Production is `/home/golfcoachnow/mysite/`, which runs the `iosapp/` tree. The
clone at `~/GolfCoachNow` is a stale copy of the root tree and serves nothing —
never deploy from it.

Run each block in a PythonAnywhere **Bash console**, checking the output before
moving to the next.

---

## What this deploy contains

- The video pipeline: `GET /videos/instructional`, and `correction_video_url` on
  every analysis response
- `POST /share/invite` and `POST /connect/founder`
- The analyser refusing to invent coaching for a clip it cannot read, and not
  spending a rep on one
- A `name` on the account, captured at sign-in, for the greeting
- The web app: Talk Mode removed, the five-button front door, contact modals

**One database migration**, adding a nullable `name` column to `users`.

---

## 1. Back up. Both the code and the database.

```
cd /home/golfcoachnow
tar -czf mysite-code-$(date +%Y%m%d-%H%M).tar.gz \
    mysite/server.py mysite/video_analyzer.py mysite/payments mysite/static
cp mysite/payments.db mysite/payments.db.predeploy-$(date +%Y%m%d-%H%M)
ls -lh mysite-code-*.tar.gz mysite/payments.db.predeploy-*
```

Both files must exist and be non-zero before you continue. The database backup
matters more than usual here because this deploy migrates the schema.

---

## 2. Fetch the branch

```
cd /home/golfcoachnow
rm -rf deploy-tmp
git clone -q -b v1-pipeline https://github.com/zumbaking7-ux/GolfCoachNow.git deploy-tmp
cd deploy-tmp && git log --oneline -1 && cd ..
```

A fresh clone, so there is no chance of picking up the stale tree.

---

## 3. Copy the backend, dependencies before `server.py`

`server.py` imports the rest, so it goes last. If anything interrupts the copy,
the app keeps running the old `server.py` and nothing breaks.

```
cd /home/golfcoachnow
cp deploy-tmp/iosapp/video_library.py              mysite/
cp deploy-tmp/iosapp/payments/contact_routes.py    mysite/payments/
cp deploy-tmp/iosapp/payments/config.py            mysite/payments/
cp deploy-tmp/iosapp/payments/email_sender.py      mysite/payments/
cp deploy-tmp/iosapp/payments/accounts.py          mysite/payments/
cp deploy-tmp/iosapp/payments/accounts_models.py   mysite/payments/
cp deploy-tmp/iosapp/payments/auth_routes.py       mysite/payments/
cp deploy-tmp/iosapp/payments/schemas.py           mysite/payments/
cp deploy-tmp/iosapp/alembic/versions/b4d17e2a9c53_add_user_name.py mysite/alembic/versions/
cp deploy-tmp/iosapp/video_analyzer.py             mysite/
cp deploy-tmp/iosapp/server.py                     mysite/
echo "backend copied"
```

The repo's `email_sender.py` already contains the User-Agent fix applied by hand
earlier, plus the general send function the contact endpoints need. It is a
superset of what is running — nothing is lost.

**No `.env` changes are needed.** `EMAIL_FROM` and `APP_SHARE_URL` are set in
the WSGI file and take precedence. `VIDEO_BASE_URL` stays unset until the assets
are published, which correctly means "no videos yet".

---

## 4. Run the migration

```
cd /home/golfcoachnow/mysite
python3.10 -m alembic current
python3.10 -m alembic upgrade head
python3.10 -m alembic current
```

Use **python3.10** — that is what the web app runs, and the console's default
`python3` is a different version without the packages.

The first `current` should print `a7b3e9f12c84`, the last `b4d17e2a9c53`. If the
upgrade fails, stop and restore the database backup; do not reload.

---

## 5. Copy the web app

```
cd /home/golfcoachnow
cp deploy-tmp/webapp/index.html mysite/static/app.html
cp deploy-tmp/webapp/index.html mysite/static/index.html
echo "web app copied"
```

Both filenames, because the live site is served from `app.html` and `index.html`
is what the directory root resolves to.

The three styling refinements someone made directly on the server — the image
sign-in icon and the button treatment — are already merged into this file, so
they survive.

---

## 6. Verify before reloading

```
cd /home/golfcoachnow/mysite
python3.10 -c "import server; print('server imports cleanly')"
python3.10 -c "import video_library; print('video_library OK')"
python3.10 -c "from payments.contact_routes import router; print('contact routes OK')"
python3.10 -c "from payments.accounts_models import User; print('name column:', hasattr(User, 'name'))"
```

**If any of these fail, stop and roll back. Do not reload.** A broken import
takes the whole site down — `/upload` and `/wedge` included, not just the new
endpoints.

---

## 7. Reload

Web tab → **Reload**.

---

## 8. Smoke test

```
curl -s "https://golfcoachnow.pythonanywhere.com/" ; echo
curl -s "https://golfcoachnow.pythonanywhere.com/videos/instructional?module=swing" ; echo
curl -s "https://golfcoachnow.pythonanywhere.com/payments/unlock-status?device_id=deploy_check" ; echo
curl -s -o /dev/null -w "app.html %{http_code}\n" "https://golfcoachnow.pythonanywhere.com/static/app.html"
```

Expected:

- health returns `{"status":"ok",...}`
- the video endpoint returns `{"module":"swing","url":null}` — `null` is correct,
  no assets are published yet
- unlock-status returns JSON. **A 404 here means the payments package failed to
  import and every payment route is silently gone**, which looks perfectly
  healthy from the front page. This is the check that matters most.
- `app.html 200`

Then in a browser: open the web app, confirm the five-button front door with no
Talk Mode, and sign in. The greeting should use the name you enter.

---

## Rollback

```
cd /home/golfcoachnow
tar -xzf mysite-code-<timestamp>.tar.gz
cp mysite/payments.db.predeploy-<timestamp> mysite/payments.db
cd mysite && python3.10 -m alembic downgrade a7b3e9f12c84
```

Then reload. Restoring the database backup alone is enough; the downgrade is
there in case you keep the newer database.

The two new files (`video_library.py`, `payments/contact_routes.py`) are left
behind by a rollback, which is harmless — nothing imports them once the old
`server.py` is back.

---

## Afterwards

Delete the scratch clone so nobody mistakes it for the deployed code:

```
rm -rf /home/golfcoachnow/deploy-tmp
```
