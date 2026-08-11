import UIKit
import AVFoundation

final class CameraViewController: UIViewController {

    private let module: GolfModule

    #if !targetEnvironment(simulator)
    private let cameraManager = CameraManager()
    #endif
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private var recordingTimer: Timer?
    private var recordingSeconds = 0

    init(module: GolfModule = .swing) {
        self.module = module
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        self.module = .swing
        super.init(coder: coder)
    }

    // MARK: - UI Elements

    private let recordButton: UIButton = {
        let btn = UIButton(type: .custom)
        btn.translatesAutoresizingMaskIntoConstraints = false
        btn.backgroundColor = .systemRed
        btn.layer.cornerRadius = 36
        btn.layer.borderWidth = 4
        btn.layer.borderColor = UIColor.white.cgColor
        return btn
    }()

    private let flipButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 22, weight: .medium)
        btn.setImage(UIImage(systemName: "camera.rotate", withConfiguration: config), for: .normal)
        btn.tintColor = .white
        btn.backgroundColor = UIColor.black.withAlphaComponent(0.4)
        btn.layer.cornerRadius = 22
        return btn
    }()

    private let backButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 20, weight: .medium)
        btn.setImage(UIImage(systemName: "chevron.left", withConfiguration: config), for: .normal)
        btn.tintColor = .white
        btn.backgroundColor = UIColor.black.withAlphaComponent(0.4)
        btn.layer.cornerRadius = 20
        return btn
    }()

    private let moduleBadge: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = .systemFont(ofSize: 13, weight: .semibold)
        label.textColor = .white
        label.textAlignment = .center
        label.backgroundColor = UIColor.systemGreen.withAlphaComponent(0.8)
        label.layer.cornerRadius = 12
        label.layer.masksToBounds = true
        return label
    }()

    private let timerLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = ""
        label.font = .monospacedDigitSystemFont(ofSize: 16, weight: .semibold)
        label.textColor = .systemRed
        label.textAlignment = .center
        label.isHidden = true
        return label
    }()

    private let recordingDot: UIView = {
        let dot = UIView()
        dot.translatesAutoresizingMaskIntoConstraints = false
        dot.backgroundColor = .systemRed
        dot.layer.cornerRadius = 5
        dot.isHidden = true
        return dot
    }()

    private let repLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = "Rep: 0"
        label.font = .systemFont(ofSize: 32, weight: .bold)
        label.textColor = .white
        label.textAlignment = .center
        label.applyShadow()
        return label
    }()

    private let correctionCard: UIView = {
        let card = UIView()
        card.translatesAutoresizingMaskIntoConstraints = false
        card.backgroundColor = UIColor.black.withAlphaComponent(0.7)
        card.layer.cornerRadius = 12
        card.isHidden = true
        return card
    }()

    private let faultLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = .systemFont(ofSize: 15, weight: .bold)
        label.textColor = .systemYellow
        label.textAlignment = .left
        label.numberOfLines = 1
        return label
    }()

    private let correctionLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = .systemFont(ofSize: 14, weight: .regular)
        label.textColor = .white
        label.textAlignment = .left
        label.numberOfLines = 0
        return label
    }()

    private let shareButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 14, weight: .medium)
        btn.setImage(UIImage(systemName: "square.and.arrow.up", withConfiguration: config), for: .normal)
        btn.setTitle(" Share", for: .normal)
        btn.tintColor = .systemGreen
        btn.titleLabel?.font = .systemFont(ofSize: 13, weight: .semibold)
        return btn
    }()

    private let talkButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 18, weight: .medium)
        btn.setImage(UIImage(systemName: "waveform", withConfiguration: config), for: .normal)
        btn.tintColor = .black
        btn.backgroundColor = .systemGreen
        btn.layer.cornerRadius = 22
        return btn
    }()

    private let statusLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = .systemFont(ofSize: 14, weight: .medium)
        label.textColor = .white
        label.textAlignment = .center
        label.applyShadow()
        return label
    }()

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        navigationController?.setNavigationBarHidden(true, animated: false)
        moduleBadge.text = "  \(module.title)  "
        setupUI()
        #if targetEnvironment(simulator)
        statusLabel.text = "Tap record to test API"
        #else
        cameraManager.delegate = self
        requestCameraAccess()
        #endif
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewLayer?.frame = view.bounds
    }

    override var prefersStatusBarHidden: Bool { true }

    // MARK: - UI Setup

    private func setupUI() {
        #if !targetEnvironment(simulator)
        let preview = cameraManager.previewLayer
        preview.frame = view.bounds
        view.layer.addSublayer(preview)
        previewLayer = preview
        #endif

        correctionCard.addSubview(faultLabel)
        correctionCard.addSubview(correctionLabel)
        correctionCard.addSubview(shareButton)

        shareButton.addTarget(self, action: #selector(shareTapped), for: .touchUpInside)

        view.addSubview(backButton)
        view.addSubview(moduleBadge)
        view.addSubview(repLabel)
        view.addSubview(recordingDot)
        view.addSubview(timerLabel)
        view.addSubview(correctionCard)
        view.addSubview(statusLabel)
        view.addSubview(recordButton)
        view.addSubview(flipButton)
        view.addSubview(talkButton)

        recordButton.addTarget(self, action: #selector(recordTapped), for: .touchUpInside)
        flipButton.addTarget(self, action: #selector(flipTapped), for: .touchUpInside)
        backButton.addTarget(self, action: #selector(backTapped), for: .touchUpInside)
        talkButton.addTarget(self, action: #selector(talkTapped), for: .touchUpInside)

        NSLayoutConstraint.activate([
            backButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            backButton.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 16),
            backButton.widthAnchor.constraint(equalToConstant: 40),
            backButton.heightAnchor.constraint(equalToConstant: 40),

            moduleBadge.centerYAnchor.constraint(equalTo: backButton.centerYAnchor),
            moduleBadge.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            moduleBadge.heightAnchor.constraint(equalToConstant: 28),

            repLabel.topAnchor.constraint(equalTo: backButton.bottomAnchor, constant: 16),
            repLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),

            recordingDot.centerYAnchor.constraint(equalTo: repLabel.centerYAnchor),
            recordingDot.trailingAnchor.constraint(equalTo: repLabel.leadingAnchor, constant: -8),
            recordingDot.widthAnchor.constraint(equalToConstant: 10),
            recordingDot.heightAnchor.constraint(equalToConstant: 10),

            timerLabel.topAnchor.constraint(equalTo: repLabel.bottomAnchor, constant: 4),
            timerLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),

            correctionCard.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 16),
            correctionCard.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -16),
            correctionCard.bottomAnchor.constraint(equalTo: statusLabel.topAnchor, constant: -12),

            faultLabel.topAnchor.constraint(equalTo: correctionCard.topAnchor, constant: 12),
            faultLabel.leadingAnchor.constraint(equalTo: correctionCard.leadingAnchor, constant: 14),
            faultLabel.trailingAnchor.constraint(equalTo: correctionCard.trailingAnchor, constant: -14),

            correctionLabel.topAnchor.constraint(equalTo: faultLabel.bottomAnchor, constant: 6),
            correctionLabel.leadingAnchor.constraint(equalTo: correctionCard.leadingAnchor, constant: 14),
            correctionLabel.trailingAnchor.constraint(equalTo: correctionCard.trailingAnchor, constant: -14),

            shareButton.topAnchor.constraint(equalTo: correctionLabel.bottomAnchor, constant: 10),
            shareButton.trailingAnchor.constraint(equalTo: correctionCard.trailingAnchor, constant: -14),
            shareButton.bottomAnchor.constraint(equalTo: correctionCard.bottomAnchor, constant: -10),

            statusLabel.bottomAnchor.constraint(equalTo: recordButton.topAnchor, constant: -16),
            statusLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),

            recordButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            recordButton.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -24),
            recordButton.widthAnchor.constraint(equalToConstant: 72),
            recordButton.heightAnchor.constraint(equalToConstant: 72),

            flipButton.centerYAnchor.constraint(equalTo: recordButton.centerYAnchor),
            flipButton.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),
            flipButton.widthAnchor.constraint(equalToConstant: 44),
            flipButton.heightAnchor.constraint(equalToConstant: 44),

            talkButton.centerYAnchor.constraint(equalTo: recordButton.centerYAnchor),
            talkButton.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            talkButton.widthAnchor.constraint(equalToConstant: 44),
            talkButton.heightAnchor.constraint(equalToConstant: 44),
        ])
    }

    // MARK: - Camera Access

    #if !targetEnvironment(simulator)
    private func requestCameraAccess() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            startCamera()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    if granted {
                        self?.startCamera()
                    } else {
                        self?.showPermissionDenied()
                    }
                }
            }
        case .denied, .restricted:
            showPermissionDenied()
        @unknown default:
            break
        }
    }

    private func startCamera() {
        cameraManager.configure()
        cameraManager.startSession()
    }
    #endif

    private func showPermissionDenied() {
        statusLabel.text = "Camera access required"
        recordButton.isEnabled = false
        recordButton.alpha = 0.4

        let alert = UIAlertController(
            title: "Camera Access Required",
            message: "GolfCoachNow needs camera access to record your swing. Please enable it in Settings.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Open Settings", style: .default) { _ in
            if let url = URL(string: UIApplication.openSettingsURLString) {
                UIApplication.shared.open(url)
            }
        })
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        present(alert, animated: true)
    }

    // MARK: - Actions

    @objc private func recordTapped() {
        #if targetEnvironment(simulator)
        analyzeAndSend(videoURL: URL(fileURLWithPath: "/dev/null"))
        #else
        if cameraManager.isRecording {
            stopRecordingUI()
            cameraManager.stopRecording()
        } else {
            startRecordingUI()
            cameraManager.startRecording()
        }
        #endif
    }

    @objc private func flipTapped() {
        #if !targetEnvironment(simulator)
        cameraManager.flipCamera()
        #endif
    }

    @objc private func shareTapped() {
        let fault = faultLabel.text ?? ""
        let correction = correctionLabel.text ?? ""
        let text = "GolfCoachNow — \(module.title)\n\nFault: \(fault)\n\(correction)"

        let activityVC = UIActivityViewController(activityItems: [text], applicationActivities: nil)
        activityVC.popoverPresentationController?.sourceView = shareButton
        present(activityVC, animated: true)
    }

    @objc private func talkTapped() {
        let talkVC = TalkModeViewController(module: module)
        talkVC.modalPresentationStyle = .fullScreen
        present(talkVC, animated: true)
    }

    @objc private func backTapped() {
        #if !targetEnvironment(simulator)
        cameraManager.stopSession()
        #endif
        navigationController?.popViewController(animated: true)
    }

    // MARK: - Recording UI State

    private func startRecordingUI() {
        recordingSeconds = 0
        timerLabel.text = "00:00"
        timerLabel.isHidden = false
        recordingDot.isHidden = false
        flipButton.isHidden = true
        backButton.isHidden = true
        talkButton.isHidden = true
        statusLabel.text = ""
        correctionCard.isHidden = true

        animateRecordButton(recording: true)
        startRecordingDotAnimation()

        recordingTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.recordingSeconds += 1
            let mins = self.recordingSeconds / 60
            let secs = self.recordingSeconds % 60
            self.timerLabel.text = String(format: "%02d:%02d", mins, secs)
        }
    }

    private func stopRecordingUI() {
        recordingTimer?.invalidate()
        recordingTimer = nil
        timerLabel.isHidden = true
        recordingDot.isHidden = true
        recordingDot.layer.removeAllAnimations()
        flipButton.isHidden = false
        backButton.isHidden = false
        talkButton.isHidden = false
        statusLabel.text = "Processing..."

        animateRecordButton(recording: false)
    }

    private func animateRecordButton(recording: Bool) {
        UIView.animate(withDuration: 0.2) {
            if recording {
                self.recordButton.backgroundColor = .darkGray
                self.recordButton.transform = CGAffineTransform(scaleX: 0.85, y: 0.85)
                self.recordButton.layer.cornerRadius = 12
            } else {
                self.recordButton.backgroundColor = .systemRed
                self.recordButton.transform = .identity
                self.recordButton.layer.cornerRadius = 36
            }
        }
    }

    private func startRecordingDotAnimation() {
        UIView.animate(withDuration: 0.6, delay: 0, options: [.autoreverse, .repeat]) {
            self.recordingDot.alpha = 0.2
        }
    }

    // MARK: - Analyze & Send

    private func analyzeAndSend(videoURL: URL) {
        DispatchQueue.main.async {
            self.recordButton.isEnabled = false
            self.recordButton.alpha = 0.4
        }

        #if targetEnvironment(simulator)
        DispatchQueue.main.async { self.statusLabel.text = "Analyzing \(self.module.title.lowercased())..." }
        let scores = SwingAnalyzer.analyze(module: module)
        APIClient.shared.sendModuleData(scores, module: module) { [weak self] result in
            DispatchQueue.main.async {
                self?.recordButton.isEnabled = true
                self?.recordButton.alpha = 1.0
                switch result {
                case .success(let response): self?.showCorrection(response)
                case .failure(let error): self?.showError(error)
                }
            }
        }
        #else
        DispatchQueue.main.async { self.statusLabel.text = "Uploading & analyzing..." }
        APIClient.shared.uploadVideo(fileURL: videoURL, module: module) { [weak self] result in
            try? FileManager.default.removeItem(at: videoURL)
            DispatchQueue.main.async {
                self?.recordButton.isEnabled = true
                self?.recordButton.alpha = 1.0
                switch result {
                case .success(let response): self?.showCorrection(response)
                case .failure(let error): self?.showError(error)
                }
            }
        }
        #endif
    }

    private func showCorrection(_ response: CorrectionResponse) {
        statusLabel.text = ""

        repLabel.text = "Rep: \(response.rep)"
        UIView.animate(withDuration: 0.15, animations: {
            self.repLabel.transform = CGAffineTransform(scaleX: 1.2, y: 1.2)
        }) { _ in
            UIView.animate(withDuration: 0.15) {
                self.repLabel.transform = .identity
            }
        }

        faultLabel.text = response.dominantFault
            .replacingOccurrences(of: "_", with: " ")
            .uppercased()
        correctionLabel.text = response.correction

        correctionCard.alpha = 0
        correctionCard.isHidden = false
        UIView.animate(withDuration: 0.3) {
            self.correctionCard.alpha = 1
        }
    }

    private func showError(_ error: Error) {
        statusLabel.text = ""

        if case APIError.requestFailed(statusCode: 403) = error {
            showPaywall()
            return
        }

        let alert = UIAlertController(
            title: "Error",
            message: error.localizedDescription,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    private func showPaywall() {
        let paywall = PaywallViewController()
        paywall.modalPresentationStyle = .fullScreen
        present(paywall, animated: true)
    }
}

// MARK: - CameraManagerDelegate

#if !targetEnvironment(simulator)
extension CameraViewController: CameraManagerDelegate {

    func cameraManager(_ manager: CameraManager, didFinishRecordingTo url: URL) {
        analyzeAndSend(videoURL: url)
    }

    func cameraManager(_ manager: CameraManager, didFailWithError error: Error) {
        DispatchQueue.main.async {
            self.stopRecordingUI()
            self.showError(error)
        }
    }
}
#endif

// MARK: - UILabel Shadow Helper

private extension UILabel {
    func applyShadow() {
        layer.shadowColor = UIColor.black.cgColor
        layer.shadowOffset = CGSize(width: 0, height: 1)
        layer.shadowOpacity = 0.8
        layer.shadowRadius = 2
    }
}
