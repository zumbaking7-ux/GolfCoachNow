# GolfCoachNow — working notes

AI golf coaching. Record a swing, get a correction. Android, iOS, web, and a
FastAPI backend. Contract work for John McGraw (founder), picked up from a
previous contractor mid-build.

Read `V2_DIRECTIVES.md` first for what the client has actually decided, and
`GolfCoachNow_V1_Tracker_v2.xlsx` for what is done and what is blocked.

---

## The layout trap

**There are two copies of the backend.** The repository root and `iosapp/` both
contain `server.py`, `payments/`, `tests/`, `alembic/` and the engine files.

**`iosapp/` is the authoritative one. It is what production runs.** The root
copy is a stale duplicate. Work in `iosapp/`, then mirror to root so the two do
not drift further apart. Deleting the root copy is overdue but has not been
done.

There is also a stale copy of the iOS app at `GolfCoachNow/` in the repo root.
The live one is `iosapp/GolfCoachNow/`.

```
iosapp/                  <- authoritative backend + iOS app
  server.py              FastAPI app, all endpoints
  video_analyzer.py      the analysis engine
  video_library.py       resolves every video URL from VIDEO_BASE_URL
  wedge.py putt.py chip.py   fault definitions and correction text, 20 each
  payments/              accounts, auth, Stripe, entitlement, contact routes
  tests/                 244 tests, all passing
android/                 Kotlin + Compose
webapp/index.html        the web app. app.html is a copy of it
assets/videos/           local staging for video assets, gitignored
  _originals/            untouched masters. never edit these
```

---

## Production

`https://golfcoachnow.pythonanywhere.com` — PythonAnywhere, account
`golfcoachnow`.

**The live code is at `/home/golfcoachnow/mysite/`, not `~/GolfCoachNow`.** That
second directory is a git clone of the stale root tree and serves nothing.

- The web app runs **Python 3.10**. The console's default `python3` is a
  different version without the packages. Always use `python3.10` on the server.
- Config is set in the **WSGI file** (`/var/www/golfcoachnow_pythonanywhere_com_wsgi.py`),
  which takes precedence over `.env`. `EMAIL_FROM`, `APP_SHARE_URL` and
  `VIDEO_BASE_URL` live there.
- There are two `.env` files and two `payments.db` files, both from relative
  paths resolved against an unclear working directory. The live database is
  `mysite/payments.db`.
- Database is SQLite. Migrations are Alembic; run them with
  `python3.10 -m alembic upgrade head` from `mysite/`. **The WSGI file also runs
  migrations on startup**, so a reload can migrate.
- The WSGI file is a hand-written **ASGI-to-WSGI bridge**, roughly 80 lines,
  because PythonAnywhere serves WSGI and FastAPI is ASGI. It builds an ASGI
  scope from the WSGI environ by hand.
- **CPU is metered and finite.** Pose analysis is the most expensive thing the
  server does. The previous contractor deliberately left MediaPipe uninstalled
  for this reason. It is installed now, which is the right call for honesty,
  but it means CPU consumption per swing went up sharply. Watch the quota on
  the dashboard once real users arrive; this is the ceiling that arrives
  exactly when success does.

`DEPLOY.md` is the runbook. Follow it. The verification step before reloading
matters: a broken import takes the whole site down, `/upload` included, not just
the new endpoints.

---

## The analysis engine — read this before touching it

Three tiers, tried in order for swing:

1. **MediaPipe pose tracking.** Installed and working, using the **Tasks API**
   (`mediapipe.tasks.python.vision.PoseLandmarker`). The analyser was
   originally written against the legacy `mp.solutions` API, which Google has
   removed from every current release — an import can therefore succeed on a
   library that cannot detect anything. `_ensure_mp()` checks for the Tasks
   API *and* the model weights on disk, not just the package, because the
   package ships the runtime without the model. Any version exposing
   `mediapipe.tasks` works.
2. **OpenCV optical flow.** Fallback when pose fails.
3. **Metadata scoring.** Reads file size and duration and generates plausible
   faults from them. **It never opens the video.** This is the tier that used to
   coach clips of anything at all.

**Putt and short game only ever reach tier 3.** They get a pose *presence check*
so a clip with nobody in it is refused, but their scoring is not real. The pose
scorer produces swing vocabulary — `casting`, `early_extension` — none of which
exists in the putt or short game correction sets, so it cannot simply be reused.

**What the system can and cannot tell:**

- It detects **a person in frame**. A clip of an empty room is refused.
- It does **not** detect **a golf swing**. Someone standing still is still
  coached. That is `D9-04`, scoped and not built.
- Whether a detected fault is the *right* fault has **never been validated
  against a coach**. That is `D9-05` and it is the real platform work.

`STRICT_ANALYSIS=true` disables metadata scoring entirely. Off by default.

Two hard stops exist in pose extraction because phone recordings often report no
frame count: a cap on frames analysed and a wall-clock budget. Without them a
15-second clip ran 450 pose detections and the request never returned.

---

## Things that will bite you

**iOS has never been compiled.** Every change to it — Talk Mode removal, the
video player, contact sheets, the name field — has only had structural checks
(brace balance, no dangling references). There is no Mac and no CI. This is the
largest unverified surface in the project.

**Android is build-verified.** Use the bundled JDK:
`export JAVA_HOME="C:\Program Files\Android\Android Studio\jbr"` then
`./gradlew assembleDebug`. The system JDK is too new.

**The three apps share no front-end code.** Every UI change is made three times.
Backend changes apply to all three at once. Estimate accordingly.

**Videos are never bundled into the apps.** They stream from `VIDEO_BASE_URL`,
so swapping a clip needs no app release. Keep it that way.

**Outbound HTTP from the server needs a User-Agent.** Cloudflare refuses
`Python-urllib` with error 1010. This silently blocked every login email for
weeks and looked like a configuration problem.

**Entitlement is keyed to the device, not the account.** Deliberate: otherwise a
new account every three reps defeats the paywall. It resets at **UTC midnight**,
not in the golfer's own timezone.

**`/upload` takes `module` and `device_id` as query parameters, not form
fields.** Not a style choice: the ASGI-to-WSGI bridge does not parse non-file
fields out of multipart bodies. If the app ever moves to a real ASGI server,
they can go back into the form body.

**Browsers disagree about recording format.** iOS Safari's `MediaRecorder`
produces MP4, Chrome produces WebM. `ALLOWED_EXTENSIONS` accepts both and the
web app detects which it got. Do not "tidy" WebM out of that list.

**Nobody has paid yet.** The `unlocks` table is empty and no Stripe webhook has
ever been processed. The payment path has never run end to end with a real
card, so treat it as untested rather than working.

**The Android keystore is the only copy that exists.** Google Play App Signing
was never enabled, so that one file is the sole means of updating the Play
listing, ever. Losing it means a new listing under a new package name, with
every install and review gone.

**`.gitignore` excludes the internal documents** — audit, client messages,
scope, tracker, pricing. **The repository is public and the previous contractor
has access.** Keep commercial terms and internal assessments out of it.

---

## Working style that has served this project

Verify rather than assert. Build Android, run the test suite, check the live
endpoint, open the browser. Several bugs here looked like configuration and were
not; several "obvious" diagnoses were wrong and only evidence settled them.

The client is non-technical, enthusiastic, and communicates through long
AI-generated messages that contradict each other. Extract the decisions, ask one
binary question at a time, and confirm in writing what is being built.

Be straight about limits. The engine is honest now, not accurate. That
distinction matters to a product being taken to press, and it has been stated
plainly to the client rather than softened.
