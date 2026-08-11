# GolfCoachNow API Documentation

## Live API URL

```
https://golfcoachnow.pythonanywhere.com
```

**Hosting:** PythonAnywhere (paid plan)
**Backend:** FastAPI (ASGI-to-WSGI bridge via a2wsgi)
**Database:** SQLite (payments.db)
**Source repo:** https://github.com/zumbaking7-ux/GolfCoachNow

---

## Modules

| Module | Endpoint | Engine | Faults |
|--------|----------|--------|--------|
| Swing | `/wedge` | wedge.py | 20 |
| Putt | `/putt` | putt.py | 20 |
| Short Game | `/short-game` | chip.py | 20 |

---

## Endpoints

### GET `/`
Health check. Returns `{"status": "ok", "service": "GolfCoachNow API"}`.

### POST `/wedge`, `/putt`, `/short-game`
Analyze pre-computed fault scores for the respective module.

**Body:**
```json
{"data": {"open_clubface": 0.8, "casting": 0.6}, "device_id": "device-uuid"}
```

**Response (200):**
```json
{
  "rep": 1,
  "dominant_fault": "open_clubface",
  "correction": "If the face is open, strengthen your lead-hand grip and square the face earlier.",
  "normalized_scores": {"open_clubface": 1.0, "casting": 0.75},
  "status": "ok"
}
```

**Error:** `403` if daily free limit reached.

### POST `/upload`
Upload video for analysis. Accepts multipart/form-data with field `file`.

**Query params:** `module` (swing|putt|short_game), `device_id`
**Limits:** .mp4/.mov/.avi/.m4v, max 16MB.
**Response:** Same shape as module endpoints.

### POST `/talk`
Talk Mode — maps natural language to fault corrections via keyword matching.

**Body:**
```json
{"text": "I keep slicing", "module": "swing", "device_id": "device-uuid"}
```

**Response (200):**
```json
{
  "fault": "open_clubface",
  "correction": "If the face is open, strengthen your lead-hand grip and square the face earlier.",
  "module": "swing",
  "matched": true
}
```

### GET `/entitlement`
Check if a device can use a module (free rep limit).

**Query params:** `device_id`, `module`
**Response:** `{allowed, is_subscriber, reps_used, reps_remaining, daily_limit}`

### POST `/payments/checkout-session`
Create a Stripe Checkout session for one-time $14.99 unlock.

**Body:** `{"device_id": "device-uuid"}`
**Response:** `{checkout_url, session_id}`

### GET `/payments/unlock-status`
Check if a device is unlocked.

**Query params:** `device_id`
**Response:** `{device_id, unlocked, unlocked_at}`

### POST `/payments/webhook`
Stripe webhook endpoint. Handles `checkout.session.completed` events.

### GET `/payments/success`
Stripe success redirect. Verifies payment and redirects to `golfcoachnow://payment-success`.

### POST `/analytics/event`, `/analytics/batch`
Track usage events. Batch accepts an array.

### GET `/analytics/summary`
Aggregated event stats. **Query:** `days` (1-90).

### GET `/performance/history`, `/performance/trends`, `/performance/stats`
Per-device performance data. **Query:** `device_id`, `module`, `limit`/`days`.

---

## Entitlement Model

- **Free:** 3 reps per module per day (UTC midnight reset)
- **Paid:** One-time $14.99 unlock → unlimited forever
- Device identified by `ANDROID_ID` (Android) or `identifierForVendor` (iOS)

---

## Deep Links

| URL | Trigger |
|-----|---------|
| `golfcoachnow://payment-success` | After successful Stripe checkout |
| `golfcoachnow://payment-cancelled` | If user cancels checkout |

---

## Integration Points

| Client | Directory | API Config |
|--------|-----------|------------|
| iOS | `GolfCoachNow/` | `APIClient.swift` → `APIConfig.baseURL` |
| Android | `android/` | `ApiClient.kt` → `BuildConfig.API_BASE_URL` |
