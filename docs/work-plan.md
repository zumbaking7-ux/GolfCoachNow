# Work Plan

## Phase 1: Project Setup
- [ ] Create Xcode project (UIKit, no storyboards)
- [ ] Configure Info.plist (camera + microphone permissions)
- [ ] Set up folder structure (Camera, Network, Models, ViewControllers)
- [ ] Set deployment target to iOS 16.0

## Phase 2: Camera Preview
- [ ] Implement `CameraManager` with `AVCaptureSession`
- [ ] Configure back camera input
- [ ] Set video quality preset (`.high` or `.hd1920x1080`)
- [ ] Add audio input
- [ ] Create `AVCaptureVideoPreviewLayer` in `CameraViewController`
- [ ] Handle camera permission request flow
- [ ] Test live preview on physical device

## Phase 3: Video Recording
- [ ] Add `AVCaptureMovieFileOutput` to capture session
- [ ] Implement start/stop recording methods
- [ ] Save recorded video to app's documents directory
- [ ] Add record button UI with visual state toggle (recording/idle)
- [ ] Test recording produces valid .mov file on device

## Phase 4: Upload to API
- [ ] Implement `VideoUploader` with `URLSession`
- [ ] Build multipart form-data request body
- [ ] Add upload progress tracking
- [ ] Handle success/failure responses
- [ ] Add upload status indicator to UI
- [ ] **Requires:** API endpoint URL and expected request format from client

## Phase 5: JSON Parsing & Rep Counter
- [ ] Define `CorrectionResponse` model (Codable)
- [ ] Parse API JSON response
- [ ] Extract rep count and correction data
- [ ] Display rep counter label on screen
- [ ] Display correction feedback on screen
- [ ] **Requires:** Sample JSON response from client

## Phase 6: Polish & Testing
- [ ] Error handling (camera access denied, upload failure, invalid JSON)
- [ ] UI polish (button styles, label positioning, status indicators)
- [ ] Test full flow on physical iPhone
- [ ] Record video demo for client proof

## Open Questions (Need Client Input)
1. **API endpoint URL** — What is the upload URL?
2. **API request format** — Multipart form-data? What field name for the video file? Any additional parameters (user ID, exercise type, etc.)?
3. **API response JSON structure** — What does the correction JSON look like? Sample response needed.
4. **Video constraints** — Max duration? Resolution preference? File size limit?
5. **Rep counter behavior** — Does it persist across recordings or reset each time?
6. **Correction display** — How should corrections appear? Text overlay? List? Specific positioning?

## Dependencies / Blockers
- Physical iPhone required for camera testing (simulator won't work)
- API endpoint details from client required before Phase 4
- JSON response structure from client required before Phase 5

## Estimated Timeline
| Phase | Duration |
|-------|----------|
| Phase 1: Setup | 0.5 day |
| Phase 2: Camera Preview | 1 day |
| Phase 3: Video Recording | 1 day |
| Phase 4: API Upload | 1 day |
| Phase 5: JSON + Rep Counter | 0.5 day |
| Phase 6: Polish & Testing | 1 day |
| **Total** | **~5 days** |
