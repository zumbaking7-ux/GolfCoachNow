# Architecture Overview

## Context: GolfCoachNow
This is a golf swing coaching app. The iOS module records swings, and the backend (FastAPI) analyzes fault scores and returns corrections with a rep counter.

## App Structure
Single-screen iOS application. No navigation stack, no tabs, no multi-screen flow.

## Screen Layout
One `UIViewController` containing:
- **Camera Preview** — full-screen `AVCaptureVideoPreviewLayer`
- **Record Button** — start/stop video recording toggle
- **Rep Counter Label** — displays the current rep count from the API (`rep` field)
- **Correction Label** — displays the dominant fault correction from the API
- **Fault Display** — shows the dominant fault name and normalized scores
- **Upload/Analysis Status** — shows progress state

## Data Flow
```
[Camera Preview] → [Record Swing Video] → [Save to Local File]
                                                ↓
                                    [Send Swing Data to /wedge]
                                                ↓
                                    [Receive JSON: rep + correction]
                                                ↓
                                    [Display Rep Count + Correction]
```

Note: The current API (`POST /wedge`) accepts fault scores as JSON, not video files. There may be an intermediate step (on-device ML or a separate endpoint) that converts video → fault scores. This needs clarification from the client.

## Key Components

### 1. CameraManager
Handles all AVFoundation logic:
- `AVCaptureSession` setup and configuration
- Camera input (back camera, video quality preset)
- `AVCaptureMovieFileOutput` for recording
- Preview layer management
- Start/stop recording

### 2. APIClient
Handles communication with the GolfCoachNow backend:
- `POST /wedge` with swing data JSON
- Decode `CorrectionResponse` from JSON
- Error handling for network failures

### 3. Models
```swift
struct SwingRequest: Encodable {
    let data: [String: Double]  // fault name → score
}

struct CorrectionResponse: Decodable {
    let rep: Int
    let dominantFault: String
    let correction: String
    let normalizedScores: [String: Double]
    let status: String
}
```

### 4. CameraViewController
The single screen:
- Manages UI layout (camera preview, buttons, labels)
- Coordinates between CameraManager and APIClient
- Updates UI with rep count and corrections

## Technology Choices
- **Language:** Swift 5+
- **UI:** UIKit (programmatic layout, no storyboards)
- **Camera:** AVFoundation (`AVCaptureSession`, `AVCaptureMovieFileOutput`)
- **Networking:** `URLSession` (no third-party dependencies)
- **JSON:** `Codable` with `JSONDecoder.KeyDecodingStrategy.convertFromSnakeCase`
- **Min iOS Target:** iOS 16.0

## File Organization
```
iosapp/
├── GolfCoachNow.xcodeproj
├── GolfCoachNow/
│   ├── App/
│   │   ├── AppDelegate.swift
│   │   └── SceneDelegate.swift
│   ├── Camera/
│   │   └── CameraManager.swift
│   ├── Network/
│   │   └── APIClient.swift
│   ├── Models/
│   │   ├── SwingRequest.swift
│   │   └── CorrectionResponse.swift
│   ├── ViewControllers/
│   │   └── CameraViewController.swift
│   └── Info.plist
```

## No Third-Party Dependencies
The entire module uses only Apple frameworks:
- `AVFoundation`
- `UIKit`
- `Foundation`
