# GolfCoachNow V1.0 — Full Project Handoff

## Project Structure

```
GolfCoachNow/
├── android/                    # Android app (Kotlin + Jetpack Compose)
├── iosapp/
│   ├── GolfCoachNow/           # iOS app (Swift + SwiftUI)
│   ├── GolfCoachNow.xcodeproj/ # Xcode project
│   ├── server.py               # FastAPI backend
│   ├── wedge.py                # Swing analysis & corrections (20 faults)
│   ├── putt.py                 # Putt analysis & corrections
│   ├── chip.py                 # Short game analysis & corrections
│   ├── talk.py                 # Talk Mode voice coaching
│   ├── video_analyzer.py       # Video upload analysis pipeline
│   ├── payments/               # Stripe payments, entitlements, auth
│   ├── alembic/                # Database migrations
│   └── tests/                  # Backend test suite
├── desktop_wrapper/            # Desktop video upload wrapper
├── docs/                       # Architecture docs, API contract, UI references
└── README-HANDOFF.md           # This file
```

## Tech Stack

- **Android**: Kotlin, Jetpack Compose, CameraX, Material 3
- **iOS**: Swift, SwiftUI, AVFoundation
- **Backend**: Python, FastAPI, SQLAlchemy, PostgreSQL
- **Payments**: Stripe Checkout (monthly subscription $14.99/mo)
- **Hosting**: PythonAnywhere (golfcoachnow.pythonanywhere.com)
- **Analytics**: Firebase Analytics (Android), custom event tracking

## Features

- **3 Coaching Modes**: Swing, Putt, Short Game
- **Video Recording & Analysis**: Record a rep, upload, get AI correction
- **Talk Mode**: Voice-describe your issue, get coaching response via TTS
- **Entitlement System**: 3 free reps/day per module, then paywall
- **Stripe Subscription**: $14.99/month for unlimited access
- **Share**: Share corrections via system share sheet
- **Performance Tracking**: Rep history, fault trends, stats per module

## Backend API Endpoints

| Method | Endpoint              | Description                        |
|--------|-----------------------|------------------------------------|
| GET    | /                     | Health check                       |
| POST   | /upload               | Upload video for analysis          |
| POST   | /wedge                | Swing analysis (JSON scores)       |
| POST   | /putt                 | Putt analysis (JSON scores)        |
| POST   | /short-game           | Short game analysis (JSON scores)  |
| POST   | /talk                 | Talk Mode voice coaching           |
| GET    | /entitlement          | Check rep allowance                |
| POST   | /payments/checkout    | Create Stripe checkout session     |
| POST   | /payments/webhook     | Stripe webhook handler             |
| GET    | /payments/status      | Check subscription status          |
| POST   | /analytics/event      | Track analytics event              |
| POST   | /analytics/batch      | Batch analytics events             |
| GET    | /analytics/summary    | Analytics dashboard                |
| GET    | /performance/history  | Rep history per module             |
| GET    | /performance/trends   | Fault frequency trends             |
| GET    | /performance/stats    | Overall stats per device           |
| GET    | /go/swing             | Deep link landing page (swing)     |
| GET    | /go/putt              | Deep link landing page (putt)      |
| GET    | /go/short-game        | Deep link landing page (short game)|

## Configuration & Keys

### Stripe (Live)
- Price ID (monthly): price_1U2mNxJEmmOCtdLJGGKLtfzT
- Price ID (one-time): price_1U2kALJEmmOCtdLJKVJUlpuT
- Product ID: prod_V2pqrvnTbluJue
- Webhook endpoint configured on Stripe dashboard

### PythonAnywhere
- URL: https://golfcoachnow.pythonanywhere.com
- Username: golfcoachnow

### Firebase (Android)
- Project: golfcoachnow-95c5f
- App ID: 1:89198832923:android:9cc9c6b4f963094e36b7be

### Android Signing
- Keystore: android/app/golfcoachnow-release.jks
- Key alias: golfcoachnow
- Store password: golfcoach2026
- Key password: golfcoach2026

## Build Instructions

### Android
```bash
cd android
./gradlew assembleDebug      # Debug APK
./gradlew bundleRelease      # Signed release AAB for Google Play
```
Output: `app/build/outputs/bundle/release/app-release.aab`

### iOS
1. Open `iosapp/GolfCoachNow.xcodeproj` in Xcode
2. Set your development team in Signing & Capabilities
3. Build & Run (Cmd+R)

### Backend
```bash
cd iosapp
pip install -r Requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Database Setup
```bash
cd iosapp
alembic upgrade head
```

## Video Assets
No video files were included in the project scope. The app has a Lessons screen placeholder ready for video URLs to be added via the backend.
