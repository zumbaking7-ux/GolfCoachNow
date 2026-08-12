# Subscriptions

Monthly billing at $14.99, on top of the accounts layer in [ACCOUNTS.md](ACCOUNTS.md).

The important change is not the new endpoints. It is that access can now end.
Everything shipped so far assumed a purchase was permanent, and a subscription
that cannot be taken away is not a subscription.

## What changed for the app

`unlock-status` gained three fields and lost nothing. `unlocked` still means
exactly what it meant before, in the same place, so the version already in the
store keeps working the day this deploys.

The new fields describe the shape of the access rather than whether it exists:

| Field | |
| --- | --- |
| `plan` | `lifetime`, `monthly`, or `none` |
| `expires_at` | when monthly access runs out. Null for lifetime and for none |
| `cancel_at_period_end` | they cancelled but have paid until `expires_at` |

**Read `unlocked` to decide what to show. Nothing else.** `plan` and
`expires_at` are for the billing screen. A future plan would break any UI that
gates features on the plan name, and none of them will break a UI that checks
`unlocked`.

## The flow

1. App calls `POST /payments/subscribe` with the device ID and, if signed in, the bearer token
2. Server returns a Stripe Checkout URL
3. App opens it in a browser
4. Stripe sends the browser back to the app's deep link when it's done
5. **App re-checks `unlock-status`.** It does not trust the deep link
6. Stripe sends the server webhooks; the server records the subscription

Step 5 matters. The deep link only says the browser came back, not that a
payment succeeded. Anyone can open a deep link. The server's answer is the only
thing that means anything.

## Endpoints

### POST /payments/subscribe

Start a monthly subscription.

    Request
    Authorization: Bearer <token>        (optional, but send it)
    {"device_id": "8f14e45fceea167a"}

    200
    {
      "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
      "session_id": "cs_test_..."
    }

| Status | Cause |
| --- | --- |
| 200 | Open `checkout_url` in a browser. |
| 409 | Already subscribed. Send them to the billing portal instead. |
| 422 | `device_id` missing or empty. |
| 429 | Rate limited. |
| 502 | Stripe unreachable. Worth a retry. |
| 503 | Subscriptions are not on sale yet. Hide the button. |

**Send the token if you have one.** Signed in, the subscription belongs to the
account and follows the person to a new phone. Not signed in, it belongs to the
device, and losing the phone loses the subscription while the charges continue.
Ask for sign in *before* this screen, not after.

**409 is not an error to show as a failure.** It means they already have a live
subscription. Open the billing portal instead of a second checkout - Stripe
would happily create one and bill them twice for the same product.

**503 means the plan is not configured yet**, not that something is broken.

### POST /payments/billing-portal

A link to Stripe's own page for cancelling, changing a card, and downloading
invoices.

    Request
    Authorization: Bearer <token>        (or send device_id)
    {"device_id": "8f14e45fceea167a"}

    200
    {"portal_url": "https://billing.stripe.com/p/session/..."}

| Status | Cause |
| --- | --- |
| 200 | Open `portal_url` in a browser. |
| 404 | Nothing to manage. Never subscribed, or it ended. |
| 422 | Neither a token nor `device_id` was sent. |
| 429 | Rate limited. |
| 502 | Stripe unreachable. |

**The URL is single use and short lived.** Request a fresh one each time the
button is tapped; do not cache it.

**There is no customer ID parameter and there will not be one.** The server
looks it up from the caller's own subscription. If it took one from the
request, anybody with a `cus_` identifier could cancel a stranger's
subscription.

**Re-check `unlock-status` when they come back from the portal.** They may have
cancelled.

### GET /payments/unlock-status

    With a token
    Authorization: Bearer <token>

    Or by device
    GET /payments/unlock-status?device_id=8f14e45fceea167a

    200
    {
      "device_id": "8f14e45fceea167a",
      "unlocked": true,
      "unlocked_at": "2026-08-09T18:24:11Z",
      "plan": "monthly",
      "expires_at": "2026-09-09T18:24:11Z",
      "cancel_at_period_end": false
    }

Unchanged otherwise: 200 for everyone, 422 only when neither a token nor a
device ID is sent, and a token covers every device that person has linked.

## What the app has to do

**Re-check on foreground, not only at launch.** A subscription ends on Stripe's
clock, not on the app's. If the only check is at cold start, somebody who
cancels keeps access until they next fully restart the app, which can be days.

**Turn access off when the server says so.** This is the one that matters most
and it is not currently true on Android. `EntitlementManager` only ever calls
`markUnlocked`; there is no path that clears the flag. That was correct for a
permanent purchase and it breaks subscriptions completely - when someone
cancels or their card finally fails, the backend marks them inactive and the
app keeps letting them in for free. iOS already assigns `response.unlocked`
directly and syncs both ways.

Tracked on [issue #6](https://github.com/zumbaking7-ux/GolfCoachNow/issues/6)
and [issue #7](https://github.com/zumbaking7-ux/GolfCoachNow/issues/7).

**Warn before access ends.** When `cancel_at_period_end` is true, the billing
screen should say when it runs out rather than letting it stop without notice.

**Do not cache `expires_at` and count down locally.** A renewal moves it
forward, a failed payment can move it, and a clock on a phone can be wrong. Ask
the server.

## Grandfathering

Everyone who bought the $14.99 one-time unlock keeps it permanently. They
report `plan: "lifetime"` and `expires_at: null`, and that is checked before
any subscription - so somebody who bought it outright and later subscribed by
mistake still owns the app, and an expired subscription can never lock them out
of something they paid for once.

Nothing is required on the app side for this. It is worth knowing so nobody
"fixes" a lifetime user showing no expiry date.

## What the server does with Stripe events

| Event | Effect |
| --- | --- |
| `checkout.session.completed` | Subscription mode is recognised and does **not** grant a permanent unlock |
| `customer.subscription.created` | Records the subscription |
| `customer.subscription.updated` | Updates status and the cancellation flag |
| `customer.subscription.deleted` | Ends access |
| `invoice.paid` | Extends the paid period. This is what makes a renewal renew |
| `invoice.payment_failed` | Deliberately changes nothing |

A failed payment not cutting access off is intentional. Stripe retries on its
own schedule and moves the subscription to `past_due`, then to `canceled` or
`unpaid` if it gives up. Locking someone out at the first failed attempt would
hit people whose card expired over a weekend and who are about to pay.

Events arrive repeatedly and out of order. The paid period only ever moves
forward, so a cancellation arriving after a renewal cannot rewind a month
somebody has already paid for.

## Access, precisely

Someone has access when either:

- a one-time unlock exists for them, which never expires, or
- a subscription exists whose status is `active`, `trialing` or `past_due`
  **and** whose paid period has not run out

Both conditions are required for the subscription case. Status alone is not
enough, because a status is only as fresh as the last webhook that arrived -
miss a cancellation and the row says active forever. A date cannot go stale
that way.

## Not covered here

Refunds and proration are Stripe's, through the portal. Plan changes and annual
billing do not exist yet; when they do, `plan` gains a value and `unlocked`
keeps meaning the same thing, which is why the app should be reading that one.
