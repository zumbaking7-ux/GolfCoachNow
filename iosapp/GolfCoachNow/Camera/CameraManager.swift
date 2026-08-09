import AVFoundation
import UIKit

protocol CameraManagerDelegate: AnyObject {
    func cameraManager(_ manager: CameraManager, didFinishRecordingTo url: URL)
    func cameraManager(_ manager: CameraManager, didFailWithError error: Error)
}

final class CameraManager: NSObject {

    weak var delegate: CameraManagerDelegate?

    private let session = AVCaptureSession()
    private let movieOutput = AVCaptureMovieFileOutput()
    private let sessionQueue = DispatchQueue(label: "camera.session")

    private var currentCameraPosition: AVCaptureDevice.Position = .back
    private var videoInput: AVCaptureDeviceInput?

    private(set) var isRecording = false
    private(set) var isSessionRunning = false

    var previewLayer: AVCaptureVideoPreviewLayer {
        let layer = AVCaptureVideoPreviewLayer(session: session)
        layer.videoGravity = .resizeAspectFill
        return layer
    }

    // MARK: - Setup

    func configure() {
        sessionQueue.async { [weak self] in
            self?.setupSession()
        }
    }

    private func setupSession() {
        session.beginConfiguration()
        session.sessionPreset = .high

        guard addVideoInput(position: .back) else {
            session.commitConfiguration()
            return
        }

        if let audioDevice = AVCaptureDevice.default(for: .audio),
           let audioInput = try? AVCaptureDeviceInput(device: audioDevice),
           session.canAddInput(audioInput) {
            session.addInput(audioInput)
        }

        guard session.canAddOutput(movieOutput) else {
            session.commitConfiguration()
            return
        }
        session.addOutput(movieOutput)

        if let connection = movieOutput.connection(with: .video) {
            connection.preferredVideoStabilizationMode = .auto
        }

        session.commitConfiguration()
    }

    private func addVideoInput(position: AVCaptureDevice.Position) -> Bool {
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: position),
              let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input) else {
            return false
        }
        session.addInput(input)
        videoInput = input
        currentCameraPosition = position
        return true
    }

    // MARK: - Session Control

    func startSession() {
        sessionQueue.async { [weak self] in
            guard let self, !self.session.isRunning else { return }
            self.session.startRunning()
            self.isSessionRunning = true
        }
    }

    func stopSession() {
        sessionQueue.async { [weak self] in
            guard let self, self.session.isRunning else { return }
            self.session.stopRunning()
            self.isSessionRunning = false
        }
    }

    // MARK: - Camera Flip

    func flipCamera() {
        guard !isRecording else { return }
        sessionQueue.async { [weak self] in
            guard let self, let currentInput = self.videoInput else { return }
            let newPosition: AVCaptureDevice.Position = self.currentCameraPosition == .back ? .front : .back

            self.session.beginConfiguration()
            self.session.removeInput(currentInput)

            if !self.addVideoInput(position: newPosition) {
                self.session.addInput(currentInput)
                self.videoInput = currentInput
            }
            self.session.commitConfiguration()
        }
    }

    // MARK: - Recording

    func startRecording() {
        guard !isRecording else { return }
        let outputURL = makeOutputURL()
        isRecording = true
        movieOutput.startRecording(to: outputURL, recordingDelegate: self)
    }

    func stopRecording() {
        guard isRecording else { return }
        movieOutput.stopRecording()
    }

    private func makeOutputURL() -> URL {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let fileName = "swing_\(Int(Date().timeIntervalSince1970)).mov"
        return docs.appendingPathComponent(fileName)
    }
}

// MARK: - AVCaptureFileOutputRecordingDelegate

extension CameraManager: AVCaptureFileOutputRecordingDelegate {

    func fileOutput(
        _ output: AVCaptureFileOutput,
        didFinishRecordingTo outputFileURL: URL,
        from connections: [AVCaptureConnection],
        error: Error?
    ) {
        isRecording = false
        if let error {
            delegate?.cameraManager(self, didFailWithError: error)
        } else {
            delegate?.cameraManager(self, didFinishRecordingTo: outputFileURL)
        }
    }
}
