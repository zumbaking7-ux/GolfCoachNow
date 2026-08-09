# Testing

## The automated suite

    pytest

No network calls, no Stripe keys needed. The tests sign their own webhook
payloads with the same HMAC scheme Stripe uses, so signature verification is
really being tested and not stubbed out.

What is covered:

- A valid signature is accepted. A tampered body, a wrong secret, a missing
  header and a non-JSON body are all rejected with 400.
- The same event delivered twice produces exactly one unlock.
- Two different events for the same device produce exactly one unlock.
- The success redirect and the webhook, in either order, produce exactly one
  unlock.
- An event type we do not handle is acknowledged and writes nothing.
- A session with no `client_reference_id`, or one that is not paid, does not
  unlock anything.
- The `unlock-status` response shape, which the mobile app is written against.
- The redirect URLs sent to Stripe are https and carry the session ID
  template.
- A missing Stripe variable stops startup with a message naming the variable
  and pointing at the deployment docs, and the app's deep link is rejected as
  `PUBLIC_BASE_URL`.

The tests build the database with the real Alembic migration rather than
`create_all`, so the schema they run against is the schema that ships,
including both unique constraints.

## Testing against real Stripe, locally

You need the [Stripe CLI](https://docs.stripe.com/stripe-cli/install) and a
test-mode key.

### 1. Forward webhooks to your machine

    stripe listen --forward-to localhost:8000/payments/webhook

It prints a signing secret starting with `whsec_`. Put that in `.env` as
`STRIPE_WEBHOOK_SECRET` and restart the app.

This secret belongs to the temporary endpoint the CLI registers, not to the
account. The deployed service has its own endpoint with its own secret. Both
are real, and they are different values.

### 2. Start the app

    uvicorn server:app --reload

Leave `PUBLIC_BASE_URL=http://localhost:8000` in `.env` for local work.

### 3. Create a checkout session

    curl -X POST http://localhost:8000/payments/checkout-session \
      -H "Content-Type: application/json" \
      -d "{\"device_id\": \"test_device_001\"}"

Open the `checkout_url` from the response in a browser.

### 4. Pay

| Card number | What happens |
| --- | --- |
| 4242 4242 4242 4242 | Payment succeeds. |
| 4000 0000 0000 9995 | Declined, insufficient funds. |
| 4000 0000 0000 3220 | Requires 3D Secure authentication. |

Any future expiry date, any 3 digit CVC, any postal code.

### 5. Check the result

The browser lands on `/payments/success` and is redirected to
`golfcoachnow://payment-success`, which a desktop browser cannot open. That is
expected. The unlock has already been written by then.

    curl "http://localhost:8000/payments/unlock-status?device_id=test_device_001"

Expected:

    {"device_id":"test_device_001","unlocked":true,"unlocked_at":"..."}

The terminal running `stripe listen` shows the webhook arriving, and the app
log shows the unlock being written or skipped as already present.

### 6. Prove the idempotency by hand

Find the event ID in the `stripe listen` output, then resend it:

    stripe events resend evt_xxxxxxxxxxxxx

The app returns 200 and logs `event already processed`. Query the database and
there is still one row:

    sqlite3 payments.db "select count(*) from unlocks;"

## Refreshing the test fixtures

`tests/fixtures/checkout_session_completed.json` is a real
`checkout.session.completed` event captured from a test payment, not a
hand-written one. The only edited fields are the buyer's name and email,
replaced with placeholders. Everything else is exactly what Stripe sent.

Keep it that way. A fixture written by hand only ever matches the assumptions
of whoever wrote it, and the suite then passes while production fails.

To recapture, run a test payment as above, take the event ID from the
`stripe listen` output, and save it:

    python -c "import stripe, json; stripe.api_key=open('.env').read().split('STRIPE_SECRET_KEY=')[1].split(chr(10))[0].strip(); \
    ev=json.loads(str(stripe.Event.retrieve('evt_XXXX'))); \
    cd=ev['data']['object'].get('customer_details') or {}; \
    cd.update({k: v for k, v in [('email','buyer@example.com'),('name','Test Buyer')] if cd.get(k)}); \
    open('tests/fixtures/checkout_session_completed.json','w').write(json.dumps(ev, indent=2))"

The tests read the event ID, session ID, device ID and payment intent ID out of
the fixture, so a refresh does not mean editing every test. Amount, currency
and email stay as explicit assertions, so if those change the tests should fail
and make you look.
