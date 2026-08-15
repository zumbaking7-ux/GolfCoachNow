# GolfCoachNow V1.0

AI-powered golf coaching platform with swing, putt, and short game analysis.

## Live URLs

| What | URL |
|------|-----|
| Web App | https://golfcoachnow.pythonanywhere.com/static/app.html |
| APK Download | https://golfcoachnow.pythonanywhere.com/static/download.html |
| Backend API | https://golfcoachnow.pythonanywhere.com/ |

## Deliverables

### 1. Android App (Kotlin + Jetpack Compose)
- Full native Android app with CameraX video recording
- 3 coaching modules: Swing, Putt, Short Game
- Talk Mode: voice-describe your issue, get spoken coaching response
- Stripe subscription checkout ($14.99/mo)
- Entitlement system: 3 free reps/day, unlimited with subscription
- Share corrections via system share sheet
- Signed APK and AAB delivered
- **Location:** `android/`

### 2. iOS App (Swift + SwiftUI)
- Full native iOS app with AVFoundation video capture
- Same feature set as Android
- Passwordless sign-in flow
- **Location:** `iosapp/GolfCoachNow/`

### 3. FastAPI Backend (Python)
- Deployed and live on PythonAnywhere
- 16+ API endpoints (see API section below)
- Video analysis engine with 3-tier processing (MediaPipe Pose > OpenCV Motion > Metadata)
- 20 swing faults, 10 putt faults, 10 short game faults
- Stripe webhook handling for subscription management
- Daily rep entitlement system with automatic reset
- Analytics event tracking
- Performance history and trend tracking
- **Location:** `iosapp/server.py`, `iosapp/video_analyzer.py`, `iosapp/wedge.py`, `iosapp/putt.py`, `iosapp/chip.py`, `iosapp/talk.py`

### 4. Web App (Mobile-First PWA)
- Single-page app accessible instantly via URL — no install required
- Same UI and feature set as native apps
- Camera recording + file upload fallback for video analysis
- Talk Mode with Web Speech API
- Stripe payment integration
- **Location:** `webapp/index.html`

### 5. Desktop Video Uploader
- Drag-and-drop video upload wrapper
- **Location:** `desktop_wrapper/`

## Why There Is No "Day 1 App Store Link"

Mobile apps **cannot** be published to Google Play or the Apple App Store instantly. This is an industry-wide requirement, not a limitation of this project:

| Platform | Review Timeline | What Happens |
|----------|----------------|--------------|
| **Google Play** (first submission) | **7+ business days** | Google manually reviews the app for policy compliance, content ratings, data safety declarations, and technical quality. There is no way to skip or expedite this. |
| **Apple App Store** (first submission) | **1–7 business days** | Apple reviews for Human Interface Guidelines, privacy policy, App Store Review Guidelines. Requires an Apple Developer Account ($99/year). |
| **Google Play** (updates after approval) | 1–3 days | Subsequent updates go through automated review. |
| **Apple App Store** (updates after approval) | 1–2 days | Faster after initial approval. |

**A website is different.** A website can be deployed and accessed instantly because there is no review process — you upload files to a server and they are live. That's why the web app at `https://golfcoachnow.pythonanywhere.com/static/app.html` was accessible immediately.

**What was done for distribution:**
1. **APK file** — the compiled Android app, downloadable and installable directly on any Android phone
2. **Google Play Internal Testing** — AAB uploaded, testers invited, pending Google's mandatory review period
3. **Firebase App Distribution** — set up for beta testing
4. **Web App** — built as a bonus deliverable so the product could be accessed instantly via URL with no install and no review wait

An APK **is** a production build. It is the exact same compiled application that goes on the Play Store. The only difference is the delivery method (direct download vs. Play Store listing), and the Play Store listing requires Google's review.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/upload` | Upload video for AI analysis |
| POST | `/wedge` | Swing analysis (JSON scores) |
| POST | `/putt` | Putt analysis (JSON scores) |
| POST | `/short-game` | Short game analysis (JSON scores) |
| POST | `/talk` | Talk Mode voice coaching |
| GET | `/entitlement` | Check daily rep allowance |
| POST | `/payments/subscribe` | Create Stripe checkout session |
| POST | `/payments/webhook` | Stripe webhook handler |
| GET | `/payments/unlock-status` | Check subscription status |
| POST | `/analytics/event` | Track analytics event |
| POST | `/analytics/batch` | Batch analytics events |
| GET | `/analytics/summary` | Analytics dashboard |
| GET | `/performance/history` | Rep history per module |
| GET | `/performance/trends` | Fault frequency trends |
| GET | `/performance/stats` | Overall stats per device |

## Tech Stack

- **Android:** Kotlin, Jetpack Compose, CameraX, Material 3
- **iOS:** Swift, SwiftUI, AVFoundation
- **Backend:** Python, FastAPI, SQLAlchemy
- **Video Analysis:** MediaPipe Pose, OpenCV, ffprobe (3-tier fallback)
- **Payments:** Stripe Checkout ($14.99/month subscription)
- **Hosting:** PythonAnywhere
- **Web App:** Vanilla HTML/CSS/JS, MediaRecorder API, Web Speech API

## Project Structure

```
GolfCoachNow/
├── android/                    # Android app (Kotlin + Jetpack Compose)
├── iosapp/
│   ├── GolfCoachNow/           # iOS app (Swift + SwiftUI)
│   ├── server.py               # FastAPI backend
│   ├── video_analyzer.py       # 3-tier video analysis engine
│   ├── wedge.py                # Swing corrections (20 faults)
│   ├── putt.py                 # Putt corrections (10 faults)
│   ├── chip.py                 # Short game corrections (10 faults)
│   ├── talk.py                 # Talk Mode voice coaching
│   ├── payments/               # Stripe payments & entitlements
│   ├── alembic/                # Database migrations
│   └── tests/                  # Backend test suite
├── webapp/                     # Mobile-first web app
├── desktop_wrapper/            # Desktop video upload tool
└── docs/                       # Architecture & API docs
```

## Setup

### Backend
```bash
cd iosapp
pip install -r Requirements.txt
cp .env.example .env       # Fill in your keys
alembic upgrade head       # Run migrations
uvicorn server:app --host 0.0.0.0 --port 8000
```

### Android
```bash
cd android
./gradlew assembleDebug      # Debug APK
./gradlew bundleRelease      # Signed release AAB
```

### iOS
1. Open `iosapp/GolfCoachNow.xcodeproj` in Xcode
2. Set your development team
3. Build & Run (Cmd+R)

### Tests
```bash
cd iosapp
pytest
```
