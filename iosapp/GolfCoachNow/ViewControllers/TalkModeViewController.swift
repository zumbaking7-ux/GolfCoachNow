import UIKit
import Speech
import AVFoundation

final class TalkModeViewController: UIViewController {

    private let module: GolfModule
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let audioEngine = AVAudioEngine()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let synthesizer = AVSpeechSynthesizer()
    private var isListening = false

    init(module: GolfModule) {
        self.module = module
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { fatalError() }

    // MARK: - UI

    private let closeButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 18, weight: .medium)
        btn.setImage(UIImage(systemName: "xmark.circle.fill", withConfiguration: config), for: .normal)
        btn.tintColor = .lightGray
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

    private let titleLabel: UILabel = {
        let label = UILabel()
        label.text = "Talk Mode"
        label.font = .systemFont(ofSize: 28, weight: .bold)
        label.textColor = .white
        label.textAlignment = .center
        return label
    }()

    private let instructionLabel: UILabel = {
        let label = UILabel()
        label.text = "Tap the mic and describe your swing issue.\nI'll give you a coaching tip."
        label.font = .systemFont(ofSize: 15, weight: .regular)
        label.textColor = .lightGray
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
    }()

    private let waveformView: UIView = {
        let v = UIView()
        v.translatesAutoresizingMaskIntoConstraints = false
        return v
    }()

    private let transcriptLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = .systemFont(ofSize: 16, weight: .regular)
        label.textColor = .white
        label.textAlignment = .center
        label.numberOfLines = 0
        label.text = ""
        return label
    }()

    private let correctionCard: UIView = {
        let card = UIView()
        card.translatesAutoresizingMaskIntoConstraints = false
        card.backgroundColor = UIColor(red: 0.14, green: 0.14, blue: 0.18, alpha: 1.0)
        card.layer.cornerRadius = 16
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
        label.font = .systemFont(ofSize: 15, weight: .regular)
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

    private let micButton: UIButton = {
        let btn = UIButton(type: .custom)
        btn.translatesAutoresizingMaskIntoConstraints = false
        btn.backgroundColor = .systemGreen
        btn.layer.cornerRadius = 40
        let config = UIImage.SymbolConfiguration(pointSize: 30, weight: .medium)
        btn.setImage(UIImage(systemName: "mic.fill", withConfiguration: config), for: .normal)
        btn.tintColor = .black
        return btn
    }()

    private let statusLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = .systemFont(ofSize: 13, weight: .medium)
        label.textColor = .lightGray
        label.textAlignment = .center
        label.text = "Tap to start"
        return label
    }()

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.08, green: 0.08, blue: 0.12, alpha: 1.0)
        moduleBadge.text = "  \(module.title)  "
        setupUI()
    }

    override func viewDidDisappear(_ animated: Bool) {
        super.viewDidDisappear(animated)
        stopListening()
        synthesizer.stopSpeaking(at: .immediate)
    }

    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    private func setupUI() {
        correctionCard.addSubview(faultLabel)
        correctionCard.addSubview(correctionLabel)
        correctionCard.addSubview(shareButton)

        shareButton.addTarget(self, action: #selector(shareTapped), for: .touchUpInside)

        view.addSubview(closeButton)
        view.addSubview(moduleBadge)
        view.addSubview(titleLabel)
        view.addSubview(instructionLabel)
        view.addSubview(transcriptLabel)
        view.addSubview(correctionCard)
        view.addSubview(micButton)
        view.addSubview(statusLabel)

        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        instructionLabel.translatesAutoresizingMaskIntoConstraints = false

        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        micButton.addTarget(self, action: #selector(micTapped), for: .touchUpInside)

        NSLayoutConstraint.activate([
            closeButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            closeButton.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -16),
            closeButton.widthAnchor.constraint(equalToConstant: 36),
            closeButton.heightAnchor.constraint(equalToConstant: 36),

            moduleBadge.centerYAnchor.constraint(equalTo: closeButton.centerYAnchor),
            moduleBadge.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            moduleBadge.heightAnchor.constraint(equalToConstant: 28),

            titleLabel.topAnchor.constraint(equalTo: closeButton.bottomAnchor, constant: 24),
            titleLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),

            instructionLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 12),
            instructionLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 32),
            instructionLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -32),

            transcriptLabel.topAnchor.constraint(equalTo: instructionLabel.bottomAnchor, constant: 32),
            transcriptLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            transcriptLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),

            correctionCard.topAnchor.constraint(equalTo: transcriptLabel.bottomAnchor, constant: 24),
            correctionCard.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            correctionCard.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),

            faultLabel.topAnchor.constraint(equalTo: correctionCard.topAnchor, constant: 16),
            faultLabel.leadingAnchor.constraint(equalTo: correctionCard.leadingAnchor, constant: 16),
            faultLabel.trailingAnchor.constraint(equalTo: correctionCard.trailingAnchor, constant: -16),

            correctionLabel.topAnchor.constraint(equalTo: faultLabel.bottomAnchor, constant: 8),
            correctionLabel.leadingAnchor.constraint(equalTo: correctionCard.leadingAnchor, constant: 16),
            correctionLabel.trailingAnchor.constraint(equalTo: correctionCard.trailingAnchor, constant: -16),
            shareButton.topAnchor.constraint(equalTo: correctionLabel.bottomAnchor, constant: 10),
            shareButton.trailingAnchor.constraint(equalTo: correctionCard.trailingAnchor, constant: -16),
            shareButton.bottomAnchor.constraint(equalTo: correctionCard.bottomAnchor, constant: -12),

            micButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            micButton.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -48),
            micButton.widthAnchor.constraint(equalToConstant: 80),
            micButton.heightAnchor.constraint(equalToConstant: 80),

            statusLabel.topAnchor.constraint(equalTo: micButton.bottomAnchor, constant: 12),
            statusLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),
        ])
    }

    // MARK: - Actions

    @objc private func shareTapped() {
        let fault = faultLabel.text ?? ""
        let correction = correctionLabel.text ?? ""
        let text = "GolfCoachNow — \(module.title) Talk Mode\n\nFault: \(fault)\n\(correction)"

        let activityVC = UIActivityViewController(activityItems: [text], applicationActivities: nil)
        activityVC.popoverPresentationController?.sourceView = shareButton
        present(activityVC, animated: true)
    }

    @objc private func closeTapped() {
        stopListening()
        synthesizer.stopSpeaking(at: .immediate)
        dismiss(animated: true)
    }

    @objc private func micTapped() {
        if isListening {
            stopListening()
        } else {
            requestPermissionsAndStart()
        }
    }

    // MARK: - Permissions

    private func requestPermissionsAndStart() {
        SFSpeechRecognizer.requestAuthorization { [weak self] authStatus in
            DispatchQueue.main.async {
                switch authStatus {
                case .authorized:
                    self?.requestMicPermission()
                case .denied, .restricted, .notDetermined:
                    self?.showPermissionAlert(for: "Speech Recognition")
                @unknown default:
                    break
                }
            }
        }
    }

    private func requestMicPermission() {
        AVAudioSession.sharedInstance().requestRecordPermission { [weak self] granted in
            DispatchQueue.main.async {
                if granted {
                    self?.startListening()
                } else {
                    self?.showPermissionAlert(for: "Microphone")
                }
            }
        }
    }

    private func showPermissionAlert(for feature: String) {
        let alert = UIAlertController(
            title: "\(feature) Access Required",
            message: "Please enable \(feature) access in Settings for Talk Mode.",
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

    // MARK: - Speech Recognition

    private func startListening() {
        guard let recognizer = speechRecognizer, recognizer.isAvailable else {
            statusLabel.text = "Speech recognition unavailable"
            return
        }

        isListening = true
        correctionCard.isHidden = true
        transcriptLabel.text = ""
        statusLabel.text = "Listening..."
        updateMicButton(listening: true)

        let audioSession = AVAudioSession.sharedInstance()
        try? audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
        try? audioSession.setActive(true, options: .notifyOthersOnDeactivation)

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let request = recognitionRequest else { return }
        request.shouldReportPartialResults = true

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            request.append(buffer)
        }

        audioEngine.prepare()
        try? audioEngine.start()

        recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }

            if let result {
                let text = result.bestTranscription.formattedString
                DispatchQueue.main.async {
                    self.transcriptLabel.text = "\"\(text)\""
                }

                if result.isFinal {
                    self.stopListening()
                    self.sendToTalkAPI(text: text)
                }
            }

            if error != nil {
                self.stopListening()
                if let text = self.transcriptLabel.text, text.count > 3 {
                    let clean = text.replacingOccurrences(of: "\"", with: "")
                    self.sendToTalkAPI(text: clean)
                }
            }
        }
    }

    private func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionRequest = nil
        recognitionTask?.cancel()
        recognitionTask = nil
        isListening = false

        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)

        DispatchQueue.main.async {
            self.updateMicButton(listening: false)
            if self.statusLabel.text == "Listening..." {
                self.statusLabel.text = "Tap to start"
            }
        }
    }

    private func updateMicButton(listening: Bool) {
        let config = UIImage.SymbolConfiguration(pointSize: 30, weight: .medium)
        if listening {
            micButton.backgroundColor = .systemRed
            micButton.setImage(UIImage(systemName: "stop.fill", withConfiguration: config), for: .normal)
            micButton.tintColor = .white
            startPulseAnimation()
        } else {
            micButton.backgroundColor = .systemGreen
            micButton.setImage(UIImage(systemName: "mic.fill", withConfiguration: config), for: .normal)
            micButton.tintColor = .black
            micButton.layer.removeAllAnimations()
            micButton.transform = .identity
        }
    }

    private func startPulseAnimation() {
        UIView.animate(withDuration: 0.8, delay: 0, options: [.autoreverse, .repeat, .allowUserInteraction]) {
            self.micButton.transform = CGAffineTransform(scaleX: 1.1, y: 1.1)
        }
    }

    // MARK: - API

    private func sendToTalkAPI(text: String) {
        DispatchQueue.main.async {
            self.statusLabel.text = "Thinking..."
            self.micButton.isEnabled = false
            self.micButton.alpha = 0.5
        }

        APIClient.shared.sendTalkRequest(text: text, module: module) { [weak self] result in
            DispatchQueue.main.async {
                guard let self else { return }
                self.micButton.isEnabled = true
                self.micButton.alpha = 1.0

                switch result {
                case .success(let response):
                    self.showTalkResponse(response)
                case .failure(let error):
                    if case APIError.requestFailed(statusCode: 403) = error {
                        self.showPaywall()
                    } else {
                        self.statusLabel.text = error.localizedDescription
                    }
                }
            }
        }
    }

    private func showTalkResponse(_ response: TalkResponse) {
        statusLabel.text = "Tap to ask again"

        if let fault = response.fault {
            faultLabel.text = fault.replacingOccurrences(of: "_", with: " ").uppercased()
        } else {
            faultLabel.text = "NO MATCH"
        }
        correctionLabel.text = response.correction

        correctionCard.alpha = 0
        correctionCard.isHidden = false
        UIView.animate(withDuration: 0.3) {
            self.correctionCard.alpha = 1
        }

        speakCorrection(response.correction)
    }

    // MARK: - Text to Speech

    private func speakCorrection(_ text: String) {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)

        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.48
        utterance.pitchMultiplier = 1.0
        synthesizer.speak(utterance)
    }

    private func showPaywall() {
        let paywall = PaywallViewController()
        paywall.modalPresentationStyle = .fullScreen
        present(paywall, animated: true)
    }
}
