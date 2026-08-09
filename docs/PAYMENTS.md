# Payments

One product, one price, one payment. A device that has paid is unlocked, and
stays unlocked.

## The flow

1. The user taps buy. The app calls `POST /payments/checkout-session` with its
   device ID.
2. The backend creates a Stripe Checkout Session, storing the device ID on it
   as `client_reference_id`, and returns the Stripe URL.
3. The app opens that URL in a browser. The user pays on Stripe's page.
4. Stripe sends the browser to `GET /payments/success`. That endpoint asks
   Stripe whether the session was paid, records the unlock, then redirects to
   `golfcoachnow://payment-success`.
5. The app catches the deep link and calls `GET /payments/unlock-status` with
   its device ID.
6. Separately, Stripe sends `checkout.session.completed` to
   `POST /payments/webhook`, which records the same unlock.

Steps 4 and 6 both write the unlock, on purpose. The webhook is the reliable
one, because Stripe retries it until it succeeds. The success redirect is the
fast one, because the app needs an answer the moment the user comes back. They
race, and the database makes sure they produce one unlock between them.

## Why Stripe is not pointed straight at the app

Stripe accepts `golfcoachnow://payment-success` as a `success_url`. Nothing
stops you doing it, which is why this is written down.

Doing it means nothing on the server runs when the customer comes back. No
session is retrieved, no payment is confirmed, no unlock is recorded. The app
would be left waiting for the webhook, and the whole point of the success
endpoint is to have the unlock already written by the time the app regains
control.

## Why the app does not read the result from the deep link

`golfcoachnow://payment-success` can be opened by anyone, by hand, without
paying. So can `/payments/success`, with any session ID in the query string.

Neither of those unlocks anything on its own. `/payments/success` ignores what
it was sent and asks Stripe directly whether that session is paid. The deep
link carries no result at all, it only tells the app to go and ask the server.

The app must call `/payments/unlock-status` for its answer. Trusting the deep
link would give the product away to anyone who typed the URL.

## Why there is no Stripe Payment Link

The original scope asked for a product, a price and a payment link. The product
and price exist in Stripe as expected. The payment link does not, and this is
the reason.

A Payment Link is one fixed URL shared by every customer. It carries no device
ID, so the server would have no way of knowing whose product to unlock. The ID
can be appended to the link as a query parameter, but then it is supplied by
whatever opens the URL rather than by the server, and one user could claim
another user's payment by editing it.

Creating the Checkout Session server-side costs one endpoint and removes that
problem entirely. The device ID is attached before the customer ever reaches
Stripe.

## Why the device ID is set server-side

`client_reference_id` is attached when the Checkout Session is created, from
the body of the app's request, before the user is sent to Stripe. Stripe stores
it and hands it back on the webhook event.

That is the only link between a payment and a device. If the app could supply
it later, on the way back from checkout, one user could claim another user's
payment.

## Endpoints

### POST /payments/checkout-session

Start a payment.

Request:

    {"device_id": "8f14e45fceea167a"}

Response `200`:

    {
      "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_a1b2c3",
      "session_id": "cs_test_a1b2c3"
    }

Open `checkout_url` in a browser. It expires 24 hours after creation.

| Status | Cause |
| --- | --- |
| 200 | Session created. |
| 422 | `device_id` missing or empty. |
| 429 | Too many requests from this address. `Retry-After` says how long to wait. |
| 502 | Stripe could not be reached. Safe to retry. |

### GET /payments/success

Where Stripe sends the browser after payment. Not called by the app directly.

Query: `session_id` (Stripe substitutes it into the redirect automatically).

| Status | Cause |
| --- | --- |
| 303 | Redirect to `golfcoachnow://payment-success`. Sent whether or not the session was paid. |
| 400 | Stripe does not recognise that `session_id`. |
| 502 | Stripe could not be reached. |

### GET /payments/cancel

Where Stripe sends the browser if the user backs out. Redirects `303` to
`golfcoachnow://payment-cancelled`. Mirrors the success route so both outcomes
leave Stripe the same way.

### GET /payments/unlock-status

The app's source of truth. Call it on launch, and again after catching the
success deep link.

Query: `device_id`

Response `200`:

    {
      "device_id": "8f14e45fceea167a",
      "unlocked": true,
      "unlocked_at": "2026-08-09T18:24:11Z"
    }

A device that has never paid gets the same `200` with `"unlocked": false` and
`"unlocked_at": null`. Not paying is not an error.

| Status | Cause |
| --- | --- |
| 200 | Always, for any device ID. |
| 422 | `device_id` missing. |
| 429 | Too many requests from this address. `Retry-After` says how long to wait. |

### POST /payments/webhook

Called by Stripe, never by the app. The status code tells Stripe whether to
send the event again.

| Status | Meaning | Stripe's response |
| --- | --- | --- |
| 200 | Handled, already handled, or an event type we ignore. | Stops. |
| 400 | Signature did not verify, so this did not come from Stripe. | Stops. |
| 500 | We should have handled it and could not. | Retries. |

Only `checkout.session.completed` is acted on. Anything else gets a 200 and is
ignored, which is how you stop Stripe resending it.

## The unlock, in prose

A device is unlocked when a row exists for it in the `unlocks` table. There is
no flag to flip and no other state. The row is written in one place,
`grant_unlock` in `payments/service.py`, reached from the webhook and from the
success redirect, and only after Stripe has confirmed `payment_status` is
`paid`.

Two unique constraints keep it to exactly one unlock:

**`uq_processed_events_stripe_event_id`.** Stripe redelivers a webhook until it
gets a 2xx back, so the same event arrives more than once. Every delivery
tries to insert a row into `processed_events` keyed on the Stripe event ID. The
second one is rejected and the handler returns 200 without doing the work
again.

**`uq_unlocks_device_id`.** The webhook and the success redirect run for the
same payment at roughly the same moment. Both call `grant_unlock`, which
inserts unconditionally. One insert wins, the other is rejected, and the
service treats a rejection as "already unlocked" rather than an error.

Neither check happens in Python. Reading first and writing second would let two
requests both find an empty table and both insert. The database makes the
decision while holding a lock, so only one can win.

`processed_at` is what makes a failed attempt recoverable. It stays NULL from
the moment an event is claimed until it is finished. If processing dies partway
through, the handler returns 500, Stripe retries, and the retry sees a claimed
but unfinished row and picks the work back up.

## What protects this

**The webhook is a public URL**, so signature verification is the only thing
between it and anyone who can send a POST. It uses Stripe's own library, which
compares in constant time and rejects timestamps outside a five minute window,
so a captured event cannot be replayed later. A failed signature returns 400 and
writes nothing.

**Signatures are checked against the raw request bytes.** Stripe signs the exact
body it sent, so parsing the JSON and re-serialising it would break every
signature. The handler reads `await request.body()` before anything touches it.

**Payments are confirmed with Stripe, never with the caller.** Anyone can open
`/payments/success` with any session ID. The endpoint ignores what it was given
and asks Stripe directly whether that session is paid.

**Sessions are stamped and checked.** Every session this service creates carries
`metadata: {golf_coach_now: wedge_unlock}`, and the webhook ignores anything
without it. One Stripe account can sell several things, and a webhook only says
"something was paid for" - without the marker, a payment for some future
unrelated product would also unlock the wedge module.

**The redirect target comes from configuration, not from the request.** There is
no way to make this service redirect somewhere of your choosing.

**Rate limiting** applies to `/payments/checkout-session` and
`/payments/unlock-status`, per client address, tunable through the environment.
It is deliberately generous, because mobile customers share carrier addresses
and a tight limit would turn away buyers long before it stopped abuse.

The webhook is **not** rate limited, and should not be. Stripe decides when to
send events. A 429 there becomes a retry, and an unlock delayed because we were
throttling Stripe is worse than anything the limit would prevent.

Two limits worth knowing about. Rate limit counters live in the web process, so
running several workers multiplies the effective limit - that is the point to
move them to Redis rather than tune them. And the client address is read from
`X-Forwarded-For`, which is trustworthy here only because PythonAnywhere's proxy
sets it.

## Known limitation: device IDs are not permanent

The unlock is tied to the device ID, because there are no accounts.

On iOS, `identifierForVendor` changes when the user deletes every app from the
same vendor. On Android, `ANDROID_ID` changes on a factory reset. When that
happens the device asks about an ID nobody has paid for, and the unlock is gone
from the user's point of view.

There is no way to fix this without user accounts. What the service does
instead is store the email address Stripe collected at checkout, on the
`unlocks` row, so support can find the payment and unlock the new device by
hand. See the runbook in [DEPLOYMENT.md](DEPLOYMENT.md).
