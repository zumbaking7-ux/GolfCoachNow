# Accounts

Passwordless sign in. Someone types their email, gets a six digit code, types
it back, and the app holds a token from then on.

This exists so a purchase survives a reinstall. Payments are recorded against a
device ID, and those do not last: iOS changes `identifierForVendor` when the
last app from a vendor is deleted, Android changes `ANDROID_ID` on a factory
reset. An account gives a person an identity that outlives the hardware.

## The flow

1. App asks for a code, sending the email and its device ID
2. Server emails a six digit code
3. App sends the email and code back
4. Server returns a token, and links that device to the account
5. App stores the token and sends it from then on

Signing in on a second device links that one too. `unlock-status` then answers
for the person rather than the phone, checking every device they have linked,
which is what makes an old purchase findable from a new handset.

## Endpoints

### POST /auth/request-code

Email a sign in code.

    Request
    {
      "email": "golfer@example.com",
      "device_id": "8f14e45fceea167a"
    }

    202
    {"status": "sent"}

| Status | Cause |
| --- | --- |
| 202 | Accepted. Returned whether or not an account exists. |
| 422 | `email` missing or malformed. |
| 429 | Rate limited. `Retry-After` header gives the seconds to wait. |

`device_id` is optional here but send it. It is what gets linked on the next
step, and linking is what makes an earlier purchase from this phone findable.

**The response is identical whether or not the address has an account.** That
is deliberate. Anything else turns this endpoint into a way of testing which
addresses are registered, so do not build UI that expects to be told.

### POST /auth/verify-code

Exchange the code for a token.

    Request
    {
      "email": "golfer@example.com",
      "code": "418302",
      "device_id": "8f14e45fceea167a"
    }

    200
    {"token": "Zx8kQ2p7vB1nR4wS9tY6uH3jL5aD0fG7cE2mN8qX1oI"}

| Status | Cause |
| --- | --- |
| 200 | Signed in. Store the token. |
| 401 | Wrong code, expired, already used, or too many attempts. |
| 422 | `email` or `code` missing or malformed. |
| 429 | Rate limited. |

**Every failure returns the same 401 with the same message.** Telling them
apart would say which addresses have accounts and how close a guess is getting.
Show one message for all of them: something like "That code is not valid. Ask
for a new one."

### POST /auth/sign-out

Revoke the token being presented.

    Headers
    Authorization: Bearer <token>

    204, no body

Always 204, even for a token that was already dead or missing. Clear the stored
token locally when this returns.

### GET /payments/unlock-status

Unchanged for existing callers. It now also accepts a token.

    With a token
    GET /payments/unlock-status
    Authorization: Bearer <token>

    Without one, exactly as today
    GET /payments/unlock-status?device_id=8f14e45fceea167a

    200
    {
      "device_id": "8f14e45fceea167a",
      "unlocked": true,
      "unlocked_at": "2026-08-09T18:24:11Z"
    }

| Status | Cause |
| --- | --- |
| 200 | Always, for any device or account. Not paying is not an error. |
| 422 | Neither a token nor `device_id` was sent. |
| 429 | Rate limited. |

With a valid token the answer covers **every device that person has linked**.
Without one, or with a token that is not valid, it falls back to answering for
`device_id` alone.

An invalid or revoked token is ignored rather than rejected, so send
`device_id` as well where you have it and the call still answers.

`device_id` in the response echoes whatever was sent in the query string. When
answering by token alone it comes back as an empty string, because the server
is answering for a person and not a handset. Read `unlocked`, not `device_id`.

## What the app stores

**The token, in secure storage.** Keychain on iOS, EncryptedSharedPreferences
on Android. It is a credential, not a preference, and should not sit beside the
cached unlock flag.

**Nothing else.** The code is never stored, and the email only if you want to
prefill the field next time.

Send it as `Authorization: Bearer <token>` on `unlock-status`. If a call that
should be authenticated starts answering as though signed out, treat the token
as dead: clear it and send the person back to sign in.

## Timings and limits

| | |
| --- | --- |
| Code length | 6 digits |
| Code lifetime | 10 minutes |
| Attempts per code | 5, then that code is dead |
| Requesting again | Retires the previous code immediately |
| Rate limit | 5 requests per 5 minutes, counted per caller **and** per email address |

The attempt cap is the thing doing the real work. Six digits is a million
possibilities, which a script tries in seconds, so the cap is what makes the
code space large enough to matter.

Because a new code kills the old one, a "resend" button must replace the code
the person is looking at, not add a second valid one. Say so in the UI.

## Behaviour worth knowing

**A device belongs to one account.** Signing in as somebody else moves the
device rather than sharing it. If a phone could belong to two accounts, one
purchase would unlock both.

**The device path is untouched.** A request with no token behaves exactly as it
did before accounts existed, so nothing breaks the day this deploys and the
sign in screens can land whenever you are ready.

**When to ask for the email** is a product decision, and the recommendation is
at the point of purchase rather than first launch, so the free three reps a day
stay frictionless.

## Not covered here

Subscriptions. Monthly billing, the customer portal and re-locking on
cancellation come next, and they build on this. See the app-side notes in the
repository issues for what lands on the client at that point.
