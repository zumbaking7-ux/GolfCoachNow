import AVFoundation
import AVKit
import UIKit

/// Plays one clip and then gets out of the way.
///
/// `onFinished` fires exactly once, for every outcome this screen can reach:
/// the clip ending, the clip failing, or the golfer skipping it. Callers can
/// therefore treat it as "the video step is over" without caring which of those
/// happened, which is what keeps the pipeline moving when an asset is missing or
/// the network is poor.
///
/// The controller dismisses itself before calling back, so callers never have to
/// coordinate the two.
final class VideoPlayerViewController: UIViewController {

    private let url: URL
    private let onFinished: () -> Void

    private var player: AVPlayer?
    private var playerLayer: AVPlayerLayer?

    /// Guards the callback. Completion and failure notifications can both
    /// arrive for one item, and a golfer can tap Skip while either is in
    /// flight; the caller must still only be told once.
    private var hasFinished = false

    private let skipButton: UIButton = {
        let button = UIButton(type: .system)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.setTitle("SKIP", for: .normal)
        button.titleLabel?.font = .systemFont(ofSize: 14, weight: .semibold)
        button.tintColor = .white
        button.backgroundColor = UIColor.black.withAlphaComponent(0.4)
        button.layer.cornerRadius = 16
        button.contentEdgeInsets = UIEdgeInsets(top: 8, left: 16, bottom: 8, right: 16)
        return button
    }()

    private let spinner: UIActivityIndicatorView = {
        let view = UIActivityIndicatorView(style: .large)
        view.translatesAutoresizingMaskIntoConstraints = false
        view.color = .white
        return view
    }()

    init(url: URL, onFinished: @escaping () -> Void) {
        self.url = url
        self.onFinished = onFinished
        super.init(nibName: nil, bundle: nil)
        modalPresentationStyle = .fullScreen
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) is not used; this controller is created in code")
    }

    override var prefersStatusBarHidden: Bool { true }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        view.addSubview(spinner)
        view.addSubview(skipButton)
        spinner.startAnimating()

        skipButton.addTarget(self, action: #selector(finish), for: .touchUpInside)

        NSLayoutConstraint.activate([
            spinner.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: view.centerYAnchor),

            skipButton.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -20),
            skipButton.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -20),
        ])

        startPlayback()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        playerLayer?.frame = view.bounds
    }

    private func startPlayback() {
        let item = AVPlayerItem(url: url)
        let player = AVPlayer(playerItem: item)

        let layer = AVPlayerLayer(player: player)
        layer.frame = view.bounds
        layer.videoGravity = .resizeAspect
        // Below the controls, so Skip stays tappable over the video.
        view.layer.insertSublayer(layer, at: 0)

        self.player = player
        self.playerLayer = layer

        let center = NotificationCenter.default
        center.addObserver(
            self,
            selector: #selector(finish),
            name: .AVPlayerItemDidPlayToEndTime,
            object: item
        )
        // A clip that cannot be played must not leave the golfer staring at
        // black. Both failure notifications route to the same exit as success.
        center.addObserver(
            self,
            selector: #selector(finish),
            name: .AVPlayerItemFailedToPlayToEndTime,
            object: item
        )
        center.addObserver(
            self,
            selector: #selector(finish),
            name: .AVPlayerItemNewErrorLogEntry,
            object: item
        )

        player.play()
        spinner.stopAnimating()
    }

    @objc private func finish() {
        guard !hasFinished else { return }
        hasFinished = true

        player?.pause()
        NotificationCenter.default.removeObserver(self)

        let callback = onFinished
        if presentingViewController != nil {
            dismiss(animated: false) { callback() }
        } else {
            callback()
        }
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }
}
