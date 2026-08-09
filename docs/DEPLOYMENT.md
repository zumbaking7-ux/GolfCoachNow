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
| `PUBLIC_BASE_URL` | Public https origin, no trailing slash. |
| `SUCCESS_DEEP_LINK` | `golfcoachnow://payment-success` |
| `CANCEL_DEEP_LINK` | `golfcoachnow://payment-cancelled` |
| `DATABASE_URL` | See above. |
| `LOG_LEVEL` | `INFO` is right for production. |

The app validates these at startup and exits if a required one is missing. A
failed boot right after a deploy is the intended behaviour, and it is better
than discovering the problem when a customer pays.

## Steps

### 1. Install and migrate

From a Bash console on PythonAnywhere, in the project directory:

    pip install --user -r Requirements.txt
    alembic upgrade head

Run the migration on every deploy that includes one. It is safe to run when
there is nothing to do.

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
- Events: `checkout.session.completed` and nothing else.

Stripe shows the signing secret once, when the endpoint is created. Copy it
into `STRIPE_WEBHOOK_SECRET`. If it is lost, roll it in the dashboard and
update the variable.

Subscribing only to the one event keeps the endpoint quiet. The handler still
answers 200 to anything else, so nothing breaks if more are added later.

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
