# Deploying to production

Production is `/home/golfcoachnow/mysite/`, which runs the `iosapp/` tree. The
clone at `~/GolfCoachNow` is a stale copy of the root tree and serves nothing —
never deploy from it.

Run each block in a PythonAnywhere **Bash console**, checking the output before
moving to the next.

---

## What this deploy contains

- **Analysis now requires an account**, with one free rep first. `/upload`,
  `/wedge`, `/putt`, `/short-game` and `/talk` refuse a stranger who has
  already used their allowance, with **401** — distinct from the **403** the
  daily limit returns.
- **Usage, history and analytics attach to the person**, not the handset. Free
  reps and purchases now follow a golfer to a new phone.
- The web app's two-button front door, the Connect icon, and the greeting.
- Swing Learn points at Victor's lesson.

**One database migration**, and it is heavier than the last one: it rebuilds
`daily_usage` to change a unique constraint. The backup in step 1 is not
optional.

Videos are published separately — see `PUBLISH_VIDEOS.md`. Until that is done
Swing Learn correctly says the lesson is on its way.

---

## 1. Back up. Both the code and the database.

```
cd /home/golfcoachnow
tar -czf mysite-code-$(date +%Y%m%d-%H%M).tar.gz \
    mysite/server.py mysite/video_analyzer.py mysite/video_library.py \
    mysite/payments mysite/static
cp mysite/payments.db mysite/payments.db.predeploy-$(date +%Y%m%d-%H%M)
ls -lh mysite-code-*.tar.gz mysite/payments.db.predeploy-*
```

Both files must exist and be non-zero before you continue. **This deploy
rebuilds a table.** A rebuild that fails partway is the one case where the
database backup is the only way back.

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
cp deploy-tmp/iosapp/payments/config.py            mysite/payments/
cp deploy-tmp/iosapp/payments/models.py            mysite/payments/
cp deploy-tmp/iosapp/payments/entitlement.py       mysite/payments/
cp deploy-tmp/iosapp/payments/accounts.py          mysite/payments/
cp deploy-tmp/iosapp/payments/accounts_models.py   mysite/payments/
cp deploy-tmp/iosapp/payments/auth_routes.py       mysite/payments/
cp deploy-tmp/iosapp/payments/contact_routes.py    mysite/payments/
cp deploy-tmp/iosapp/payments/email_sender.py      mysite/payments/
cp deploy-tmp/iosapp/payments/schemas.py           mysite/payments/
cp deploy-tmp/iosapp/alembic/versions/c9e2f4a71b38_attribute_usage_to_users.py mysite/alembic/versions/
cp deploy-tmp/iosapp/video_analyzer.py             mysite/
cp deploy-tmp/iosapp/server.py                     mysite/
echo "backend copied"
```

**No `.env` changes are needed.** `UNGATED_REPS` defaults to 1, which is what
we want for the launch window. Setting it to `0` later closes the free rep
without a code change — see step 9.

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

The first `current` should print `b4d17e2a9c53`, the last `c9e2f4a71b38`.

This one does more than add a column. It rebuilds `daily_usage` so two accounts
sharing a phone can each have their own daily count, and it backfills
`user_id` on usage, history and analytics from the existing `user_devices`
links. **If the upgrade fails, stop and restore the database backup. Do not
reload.**

Sanity check the backfill — rows for devices somebody has signed in on should
now carry a user, and rows for devices nobody ever signed in on should not:

```
cd /home/golfcoachnow/mysite
python3.10 - <<'EOF'
import sqlite3
c = sqlite3.connect("payments.db")
for t in ("daily_usage", "rep_results", "analytics_events"):
    total = c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    named = c.execute("SELECT COUNT(*) FROM %s WHERE user_id IS NOT NULL" % t).fetchone()[0]
    print("%-18s %4d rows, %4d attached to an account" % (t, total, named))
EOF
```

Rows left unattached are expected and correct: they came from devices that
never signed in. Nothing should be lost — the totals should match what was
there before.

---

## 5. Copy the web app

```
cd /home/golfcoachnow
mkdir -p mysite/static/img
cp deploy-tmp/webapp/static/img/*.png mysite/static/img/
cp deploy-tmp/webapp/index.html mysite/static/app.html
cp deploy-tmp/webapp/index.html mysite/static/index.html
cp deploy-tmp/webapp/download.html mysite/static/download.html
ls mysite/static/img/*.png | wc -l
echo "web app copied"
```

The count should print **13**.

Both page filenames, because the live site is served from `app.html` and
`index.html` is what the directory root resolves to.

Every image, not a named list. A named list is one more thing to forget, and
forgetting it renders the new front door with broken images - worse than not
deploying at all. This deploy alone replaces the banner and adds three icons
the server has never seen: the three-figure Connect, the paper plane Share,
and the white swing glyph.

Images before the page, so there is never a moment where the page is live and
asking for files that are not there yet.

The page requests each image with a `?v=<hash>` suffix. That is what forces a
browser holding yesterday's banner to fetch today's; without it, anybody who
opened the app before this deploy would keep seeing the old build. Run
`python3 stamp_assets.py` locally after changing any image, or the suffix goes
stale and the caching problem comes back.

---

## 5b. The Android test build

The APK is not in the repository. It is 22 MB of build output and every clone
would carry it forever, so it is uploaded by hand.

PythonAnywhere **Files** tab, into `/home/golfcoachnow/mysite/static/download/`,
creating that folder if it does not exist:

| File | Size |
| --- | --- |
| `golfcoachnow.apk` | ~22 MB |

It is on the build machine under `webapp/static/download/` in this repository.

Then check it is really being served, because a 404 here is a download page
that looks perfectly fine and hands testers nothing:

```
curl -s -o /dev/null -w "apk %{http_code}  %{size_download} bytes\n" \
  "https://golfcoachnow.pythonanywhere.com/static/download/golfcoachnow.apk"
```

The link to share is `/static/download.html`.

**This is the debug build.** A debug-signed app cannot be upgraded in place by
a release-signed one, so anybody testing this will have to uninstall before
installing the eventual Play Store build. Say so when you send the link.

---

## 6. Verify before reloading

```
cd /home/golfcoachnow/mysite
python3.10 -c "import server; print('server imports cleanly')"
python3.10 -c "import video_library; print('video_library OK')"
python3.10 -c "from payments.entitlement import has_paid_access; print('entitlement OK')"
python3.10 -c "from payments.config import settings; print('ungated_reps =', settings.ungated_reps)"
python3.10 -c "from payments.models import DailyUsage; print('user_id column:', hasattr(DailyUsage, 'user_id'))"
```

**If any of these fail, stop and roll back. Do not reload.** A broken import
takes the whole site down — `/upload` and `/wedge` included, not just the new
behaviour.

---

## 7. Reload

Web tab → **Reload**.

---

## 8. Smoke test

```
curl -s "https://golfcoachnow.pythonanywhere.com/health" ; echo
curl -s "https://golfcoachnow.pythonanywhere.com/videos/instructional?module=swing" ; echo
curl -s "https://golfcoachnow.pythonanywhere.com/payments/unlock-status?device_id=deploy_check" ; echo
curl -s -o /dev/null -w "app.html %{http_code}\n" "https://golfcoachnow.pythonanywhere.com/static/app.html"
```

Expected:

- `/health` returns `{"status":"ok",...}`. It moved off `/` when the root
  became the web app: on a domain called `app`, somebody who types the bare
  address expects the app rather than a status blob.
- the video endpoint returns a url once `PUBLISH_VIDEOS.md` is done, `null`
  before that. **`null` is a correct answer, not a failure.**
- unlock-status returns JSON. **A 404 here means the payments package failed to
  import and every payment route is silently gone**, which looks perfectly
  healthy from the front page. This is the check that matters most.
- `app.html 200`

Then check the gate itself, which is the point of this deploy:

```
DEV="gate_probe_$(date +%s)"
for i in 1 2; do
  printf "rep %d: " $i
  curl -s -o /dev/null -w "%{http_code}\n" -X POST \
    "https://golfcoachnow.pythonanywhere.com/upload?module=swing&device_id=$DEV" \
    -F "file=@/dev/null;filename=probe.mp4"
done
```

The first should not be **401** — a new device still has its free rep. The
second **must be 401**: the allowance is spent and the gate is live. Any other
pair of numbers means the gate is not doing its job, and a golfer can analyse
without an account.

Finally, in a browser: open the web app, confirm the two-button front door and
the greeting, sign in, and record a swing.

---

## 9. Closing the free rep, after the press coverage

The un-gated rep exists for the launch window. To close it, no release is
needed:

Web tab → **WSGI configuration file** → add beside the other settings:

```python
os.environ["UNGATED_REPS"] = "0"
```

Save → **Reload**. From that point every analysis needs an account. Removing
the line restores it.

---

## Rollback

```
cd /home/golfcoachnow
tar -xzf mysite-code-<timestamp>.tar.gz
cp mysite/payments.db.predeploy-<timestamp> mysite/payments.db
```

Then reload.

**Restore the database backup rather than running `alembic downgrade`.** The
downgrade works, and is tested, but it is lossy by necessity: the old shape
cannot hold two accounts on one handset, so it collapses those rows and keeps
the larger count. The backup has no such problem. The downgrade is there for
the case where the newer database has to be kept.

If you do need it:

```
cd /home/golfcoachnow/mysite && python3.10 -m alembic downgrade b4d17e2a9c53
```

---

## Afterwards

Delete the scratch clone so nobody mistakes it for the deployed code:

```
rm -rf /home/golfcoachnow/deploy-tmp
```
