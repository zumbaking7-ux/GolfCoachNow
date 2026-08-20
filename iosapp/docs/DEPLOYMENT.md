# Deployment

## Where this runs

PythonAnywhere, at https://golfcoachnow.pythonanywhere.com. The app is ASGI and
PythonAnywhere serves WSGI, so it is wrapped with `a2wsgi` in the WSGI
configuration file. That is already how the wedge endpoints are served, and the
payment routes are mounted on the same app, so they need no separate setup.

The webhook needs a public HTTPS URL Stripe can reach, which that domain
provides.

**The database is SQLite**, and on this host that is the right choice.
PythonAnywhere keeps a persistent filesystem, so `payments.db` survives
restarts and redeploys.

    DATABASE_URL=sqlite:////home/<username>/GolfCoachNow/payments.db

Use an absolute path in production. A relative path resolves against the
working directory, which is not guaranteed to be the project folder when the
web app starts.

If this service is ever moved to a host that rebuilds its filesystem on deploy
- Render, Railway, Fly without a mounted volume, Cloud Run - SQLite stops being
safe. Every payment record is wiped on the next deploy, and with no user
accounts there is no way to rebuild it. Switch `DATABASE_URL` to Postgres and
add the driver:

    pip install "psycopg[binary]"
    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname

Nothing else changes. The migrations and both unique constraints behave the
same on either database.

## Environment variables

All of them are listed in `.env.example`. Whichever way they are set, the file
holding them is never committed - `.gitignore` covers `.env`.

| Variable | Notes |
| --- | --- |
| `STRIPE_SECRET_KEY` | Live key starts with `sk_live_` or `rk_live_`. |
| `STRIPE_WEBHOOK_SECRET` | From the live webhook endpoint, not the CLI. |
| `STRIPE_PRICE_ID` | The live mode price ID, which differs from the test one. |
| `STRIPE_SUBSCRIPTION_PRICE_ID` | The live recurring price. **May be left empty**, see below. |
| `PORTAL_RETURN_DEEP_LINK` | `golfcoachnow://subscription-updated` |
| `PUBLIC_BASE_URL` | Public https origin, no trailing slash. |
| `SUCCESS_DEEP_LINK` | `golfcoachnow://payment-success` |
| `CANCEL_DEEP_LINK` | `golfcoachnow://payment-cancelled` |
| `DATABASE_URL` | See above. |
| `LOG_LEVEL` | `INFO` is right for production. |
| `RATE_LIMIT_ENABLED` | `true`. Set to `false` to turn limiting off without a deploy. |
| `RATE_LIMIT_REQUESTS` | `30` per window, per client address. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60`. |
| `VIDEO_BASE_URL` | Origin the video assets are served from, no trailing slash. Unset means no videos are published; the API answers `null` and the apps skip to the camera. |
| `POSE_MODEL_PATH` | Pose model weights. MediaPipe ships the runtime but not the model; download it once (see `.env.example`). Missing means pose tracking is silently unavailable. |
| `STRICT_ANALYSIS` | `false` by default. Set to `true` once the pose libraries are confirmed installed, so a clip can never be scored from its metadata. See below. |
| `FOUNDER_EMAIL` | Where "connect with the founder" messages land. |
| `APP_SHARE_URL` | The link the Share button emails to a friend. **May be left empty**, which makes `/share/invite` answer 503 and sends nobody anything. |
| `SHARE_RATE_LIMIT_REQUESTS` | `3` per window, counted per caller and separately per recipient. |
| `SHARE_RATE_LIMIT_WINDOW_SECONDS` | `3600`. |
| `EMAIL_PROVIDER` | **`resend` in production.** Defaults to `console`, which sends nothing. See below. |
| `RESEND_API_KEY` | Required when `EMAIL_PROVIDER` is `resend`. |
| `EMAIL_FROM` | From address on sign in emails. Defaults to Resend's shared onboarding domain. |
| `LOGIN_CODE_LENGTH` | `6`. |
| `LOGIN_CODE_TTL_MINUTES` | `10`. |
| `LOGIN_CODE_MAX_ATTEMPTS` | `5`. |
| `AUTH_RATE_LIMIT_REQUESTS` | `5` per window. Tighter than the general limit because this sends email. |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `300`. |

The rate limit defaults are deliberately loose. Mobile customers share carrier
addresses, so a whole city can arrive from one, and tightening this blocks
buyers before it blocks abuse. Raise the limit if legitimate users ever see a
429; the counters are per web process, so several workers multiply it anyway.

The app validates these at startup and exits if a required one is missing. A
failed boot right after a deploy is the intended behaviour, and it is better
than discovering the problem when a customer pays.

### The recurring price is the one setting allowed to be empty

Every other Stripe variable is required and the app refuses to start without
it, because a payment service missing a key should fail at boot rather than on
a customer's card.

`STRIPE_SUBSCRIPTION_PRICE_ID` is deliberately not. Leaving it unset means
`/payments/subscribe` answers 503 and everything else keeps working, so the
subscription code can deploy before the plan goes on sale without taking the
live one-time checkout down with it.

The consequence to know: **an empty value fails quietly.** Nothing crashes,
nothing logs an error at startup, and the subscribe button simply never works.
If subscriptions appear unavailable in production, check this variable first.

**Put the recurring price on a product that already carries an eligible tax
code.** Managed Payments is enabled on this account and rejects checkout for a
product without one. That rejection happens live, on a real customer's card,
and it is what broke checkout once already.

### `STRICT_ANALYSIS` decides whether a correction can be invented

The analyser has three tiers. The first two look at the video: MediaPipe pose
tracking, then OpenCV motion. The third does not. It reads the file's size and
duration, seeds a random number generator with them, and picks faults.

That third tier is why an empty file used to come back with confident coaching.
Clips that are clearly not recordings are now rejected outright regardless of
this setting, and a tier that genuinely looked and found nobody in frame now
says so instead of falling through. But a plausible-looking video on a server
without the pose libraries still gets metadata scoring while this is `false`.

    STRICT_ANALYSIS=true

turns that last path off. A clip that cannot be really analysed then comes back
as `no_swing_detected` with an explanation, and nothing is ever fabricated.

**Leave it `false` until `mediapipe`, `opencv-python` and `numpy` are confirmed
installed**, because switching it on without them means every upload is
refused. `python3 deploy_check.py` on the server answers that in one command.

### Sign in sends no email until `EMAIL_PROVIDER` is set

`EMAIL_PROVIDER` defaults to `console`, which writes the login code to the
application log and sends nothing. That default is right for local work and
wrong everywhere else, and it is the second setting on this page whose failure
mode is silence rather than a crash.

A deployment that never sets it starts cleanly, serves every endpoint, accepts
an email address at the sign in screen, and returns the same `202` it would on
success. Nobody is signed in and nothing in the logs looks like an error. The
code is sitting in the log where only an operator can see it.

Production needs both:

    EMAIL_PROVIDER=resend
    RESEND_API_KEY=re_...

The key is validated at startup, so setting the provider without the key stops
the app rather than stranding someone on a login screen.

One request settles whether it is working, and it has to be a real address you
can open:

    curl -X POST https://golfcoachnow.pythonanywhere.com/auth/request-code \
      -H 'Content-Type: application/json' \
      -d '{"email":"you@example.com"}'

A `202` proves only that the request was accepted. **The endpoint answers the
same way whether or not an email was ever sent**, deliberately, so that it
cannot be used to test which addresses are registered. The inbox is the only
confirmation.

## Steps

### 1. Install and migrate

From a Bash console on PythonAnywhere, in the project directory:

    pip install --user -r Requirements.txt
    alembic upgrade head

Run the migration on every deploy that includes one. It is safe to run when
there is nothing to do.

**Check the payment routes actually loaded before calling a deploy finished.**
`server.py` imports the payments package inside a `try/except ImportError`, so
if the dependencies above are not installed the app still starts, `/upload` and
`/wedge` work normally, and the payment routes simply are not there. Nothing
looks wrong. Stripe's webhook gets a 404, customers pay, and no unlock is ever
written.

One request settles it:

    curl "https://golfcoachnow.pythonanywhere.com/payments/unlock-status?device_id=deploy_check"

A JSON body with `"unlocked": false` means the routes loaded. A 404 means the
dependencies are missing - run the install again and reload.

### 2. Set the environment variables and reload

PythonAnywhere does not read a `.env` file for you. Either add the variables to
the WSGI configuration file before the app is imported, or keep a `.env` beside
the project, which `payments/config.py` picks up automatically.

Then hit **Reload** on the Web tab.

**Set the variables before you reload.** The settings are validated when the
module is imported, which is deliberate - a payment service should not start
half configured and discover the problem on someone's card. But it means a
missing variable stops the whole application from starting, `/upload` and
`/wedge` included, not just the payment routes. The error appears in the web
app's error log as a Settings validation error naming the variable.

If that happens: set the variable and reload again. Nothing is lost, and no
payment data is affected.

### 3. Copy the product to live mode

Test mode and live mode are separate. The product and price created for testing
do not exist in live mode.

In the Stripe dashboard, open the product, click **Copy to live mode**, then
take the live price ID and set `STRIPE_PRICE_ID`.

**The product needs a tax code or checkout will not work.** This account has
Managed Payments enabled, which makes Stripe the merchant of record and handles
tax, and it requires every product to carry an eligible tax code. Without one,
creating a Checkout Session fails with:

    Invalid line_items[0]: the product tax code is missing.

The test product is set to `txcd_10103000`, "Software as a service - personal
use", which is what a cloud service analysing an uploaded swing is. That is a
tax classification and it belongs to whoever owns the business, so confirm it
before going live rather than copying it because it was the default here.

### 4. Register the webhook endpoint

Dashboard, Developers, Webhooks, Add endpoint.

- URL: `https://your-domain/payments/webhook`
- Events: the six below, and nothing else.

```
checkout.session.completed
customer.subscription.created
customer.subscription.updated
customer.subscription.deleted
invoice.paid
invoice.payment_failed
```

**All six are required once subscriptions are on sale, and missing one fails
silently.** The endpoint answers 200 to anything it does not handle, so an
under-subscribed endpoint looks perfectly healthy in the dashboard while the
thing it should have done never happens:

| Missing event | What breaks |
| --- | --- |
| `customer.subscription.created` | Nobody's subscription is ever recorded |
| `invoice.paid` | Nothing renews. Everybody lapses after one month, having paid for more |
| `customer.subscription.deleted` | Cancelled customers keep full access forever |
| `customer.subscription.updated` | Status changes are missed, including cancellations scheduled for period end |

Only `checkout.session.completed` is needed while the one-time product is the
only thing on sale, which is what this endpoint was originally created with.
Adding the other five is part of turning subscriptions on, not an optional
extra.

Stripe shows the signing secret once, when the endpoint is created. Copy it
into `STRIPE_WEBHOOK_SECRET`. If it is lost, roll it in the dashboard and
update the variable.

### 5. Switch the keys

Replace the test key with the live one. Live mode also requires the Stripe
account to have completed business verification, which is done in the
dashboard and is not something the service can work around.

### 6. Verify

- `curl https://your-domain/docs` loads.
- In the dashboard, Developers, Webhooks, send a test event to the endpoint and
  confirm a 200.
- Make one real payment with a real card, for the real price. Confirm the
  payment appears in the dashboard, then confirm the unlock:

      curl "https://your-domain/payments/unlock-status?device_id=<the device you used>"

- Refund that payment from the dashboard afterwards if you want the money back.
  Note that a refund does not re-lock the device. That was not in scope. See
  below for how to do it by hand.

## Runbook

### Did this person pay?

By device:

    select * from unlocks where device_id = '<device id>';

By email, which is what support usually has:

    select * from unlocks where customer_email = '<email>';

A row means unlocked. No row means not unlocked. `source` says which path
recorded it, `webhook` or `success_redirect`.

### They paid but the app still says locked

Check whether the unlock exists at all. If it does, the problem is on the app
side, not here. Confirm with:

    curl "https://your-domain/payments/unlock-status?device_id=<device id>"

If there is no unlock, find the payment in the Stripe dashboard, open the
event, and look at the delivery attempts on the webhook endpoint.

### Resending a failed webhook event

Dashboard, Developers, Webhooks, select the endpoint, find the event, click
**Resend**. Or from the CLI:

    stripe events resend evt_xxxxxxxxxxxxx

Resending is always safe. A duplicate is recognised and ignored.

### Unlocking a device by hand

Needed when a user reinstalls and their device ID changes. Confirm the payment
in the Stripe dashboard first, by email.

    insert into unlocks
      (device_id, checkout_session_id, payment_intent_id, amount_total,
       currency, customer_email, status, source, created_at)
    values
      ('<new device id>', '<cs_ from the dashboard>', '<pi_ from the dashboard>',
       1499, 'usd', '<email>', 'paid', 'manual', '2026-01-01T00:00:00');

`amount_total` is in cents, so 1499 is the 14.99 price. Copy the real figure
from the payment in the dashboard rather than assuming.

Use `manual` as the source so these are easy to find later.

### Locking a device after a refund

    delete from unlocks where device_id = '<device id>';

The webhook does not do this. Refund handling was not part of the scope, so if
it is wanted it should be added deliberately rather than assumed.

## What to watch in the logs

Every payment line carries the IDs needed to follow it end to end.

| Line | Meaning |
| --- | --- |
| `checkout session created` | The app started a payment. |
| `event received` | A webhook passed signature verification. |
| `unlock written` | A device was unlocked. |
| `unlock already present` | The other path got there first. Normal. |
| `event already processed` | Stripe retried something already done. Normal. |
| `rejected webhook, signature did not verify` | Something posted to the webhook that was not Stripe. |
| `retrying event left unfinished` | A previous attempt died partway. Investigate if frequent. |
| `failed to process event` | Needs a human. Stripe will keep retrying. |

Payload bodies are never logged. Stripe events carry customer email and billing
address, and those do not belong in application logs.
