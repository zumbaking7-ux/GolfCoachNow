# GolfCoachNow API Documentation

## Live API URL

```
https://golfcoachnow.pythonanywhere.com
```

**Hosting:** PythonAnywhere (free tier)
**Username:** golfcoachnow
**Backend:** Flask (converted from FastAPI for WSGI compatibility)
**Source repo:** https://github.com/zumbaking7-ux/GolfCoachNow

---

## Endpoints

### GET `/`

Health check.

**Request:**
```
GET https://golfcoachnow.pythonanywhere.com/
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "GolfCoachNow API"
}
```

---

### POST `/upload`

Upload a golf swing video for analysis. The server extracts video features, generates fault scores, and returns the dominant fault with a coaching correction.

**Request:**
```
POST https://golfcoachnow.pythonanywhere.com/upload
Content-Type: multipart/form-data
```

**Form field:**
| Field | Type | Description |
|-------|------|-------------|
| `file` | File | Video file (.mp4, .mov, .avi, .m4v). Max 16 MB. |

**Response (200 OK):**
```json
{
  "rep": 1,
  "dominant_fault": "under_plane",
  "correction": "If you're under-plane, feel the lead shoulder work down and the club move up the plane.",
  "normalized_scores": {
    "under_plane": 1.0,
    "steep_shoulder_turn": 0.902
  },
  "status": "ok"
}
```

**Error Responses:**
- `400` — No file provided, or invalid file type
- `413` — File exceeds 16 MB limit
- `500` — Video analysis failed

---

### POST `/wedge`

Analyze pre-computed swing fault scores and return correction coaching cue.

**Request:**
```
POST https://golfcoachnow.pythonanywhere.com/wedge
Content-Type: application/json
```

**Body:**
```json
{
  "data": {
    "open_clubface": 0.8,
    "casting": 0.6,
    "sway": 0.3
  }
}
```

The `data` field is a dictionary of fault names mapped to numeric scores (0.0–1.0 severity). The engine normalizes scores, identifies the dominant fault, and returns a correction.

**Response (200 OK):**
```json
{
  "rep": 1,
  "dominant_fault": "open_clubface",
  "correction": "If the face is open, strengthen your lead-hand grip and square the face earlier.",
  "normalized_scores": {
    "open_clubface": 1.0,
    "casting": 0.75,
    "sway": 0.375
  },
  "status": "ok"
}
```

---

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `rep` | Int | Incrementing rep counter (server-side, resets on server restart) |
| `dominant_fault` | String | The highest-scoring fault after normalization |
| `correction` | String | Human-readable correction cue for the dominant fault |
| `normalized_scores` | Dict | All faults normalized to 0.0–1.0 range |
| `status` | String | Always `"ok"` on success |

---

## Available Fault Keys (20 total)

| Fault Key | Correction Summary |
|-----------|-------------------|
| `open_clubface` | Strengthen lead-hand grip, square face earlier |
| `closed_clubface` | Weaken lead-hand grip, keep face neutral longer |
| `weak_grip` | Rotate lead hand so 2–3 knuckles visible |
| `strong_grip` | Rotate lead hand counterclockwise to neutralize |
| `over_the_top` | Trail elbow tuck, swing from the inside |
| `under_plane` | Lead shoulder down, club up the plane |
| `early_extension` | Keep hips back, maintain spine angle |
| `casting` | Hold wrist hinge longer, release naturally |
| `chicken_wing` | Extend lead arm through impact, rotate fully |
| `reverse_pivot` | Shift pressure to trail side on backswing |
| `sway` | Turn around spine, don't slide laterally |
| `slide` | Rotate hips instead of driving forward |
| `spine_angle_loss` | Keep chest down, rotate around stable axis |
| `tempo_imbalance` | Smooth transition, match backswing/downswing rhythm |
| `poor_alignment` | Square feet, hips, shoulders to target line |
| `ball_position_error` | Adjust relative to club length |
| `grip_pressure` | Light enough to relax, firm enough to control |
| `hip_stall` | Keep rotating through impact, chest follows |
| `flat_shoulder_turn` | Lead shoulder moves down and under chin |
| `steep_shoulder_turn` | Shoulders rotate more level around spine |

---

## Quick Test (cURL)

```bash
# Health check
curl https://golfcoachnow.pythonanywhere.com/

# Upload a swing video
curl -X POST https://golfcoachnow.pythonanywhere.com/upload \
  -F "file=@swing.mp4"

# Send pre-computed fault scores
curl -X POST https://golfcoachnow.pythonanywhere.com/wedge \
  -H "Content-Type: application/json" \
  -d '{"data":{"open_clubface":0.8,"casting":0.6,"sway":0.3}}'
```

---

## Integration Points

| Client | File | Config Location |
|--------|------|----------------|
| iOS App | `GolfCoachNow/Network/APIClient.swift` | `APIConfig.uploadURL` — sends video via multipart to `/upload` |
| Desktop Wrapper | `desktop_wrapper/main.py` | `API_URL` — sends video via multipart to `/upload` |

---

## Notes

- The free PythonAnywhere tier has a **100 CPU seconds/day** limit. Fine for testing, may need paid tier ($5/mo) for production.
- The rep counter resets when the server restarts.
- The backend was converted from FastAPI to Flask for PythonAnywhere WSGI compatibility. Same behavior, same endpoints.
- `POST /upload` accepts video files and processes them server-side. `POST /wedge` accepts pre-computed JSON fault scores.
- Visual API docs available at `https://golfcoachnow.pythonanywhere.com/docs`.
