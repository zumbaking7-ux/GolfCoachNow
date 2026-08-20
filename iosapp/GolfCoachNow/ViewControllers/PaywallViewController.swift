import UIKit
import SafariServices

final class PaywallViewController: UIViewController {

    private let scrollView: UIScrollView = {
        let sv = UIScrollView()
        sv.translatesAutoresizingMaskIntoConstraints = false
        sv.showsVerticalScrollIndicator = false
        return sv
    }()

    private let contentStack: UIStackView = {
        let stack = UIStackView()
        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.axis = .vertical
        stack.spacing = 20
        stack.alignment = .fill
        return stack
    }()

    private let closeButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 18, weight: .medium)
        btn.setImage(UIImage(systemName: "xmark.circle.fill", withConfiguration: config), for: .normal)
        btn.tintColor = .lightGray
        return btn
    }()

    private let iconView: UIImageView = {
        let iv = UIImageView()
        iv.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 60, weight: .medium)
        iv.image = UIImage(systemName: "lock.open.fill", withConfiguration: config)
        iv.tintColor = .systemGreen
        iv.contentMode = .scaleAspectFit
        return iv
    }()

    private let titleLabel: UILabel = {
        let label = UILabel()
        label.text = "Unlock Full Access"
        label.font = .systemFont(ofSize: 28, weight: .bold)
        label.textColor = .white
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
    }()

    private let subtitleLabel: UILabel = {
        let label = UILabel()
        label.text = "One-time payment. No subscriptions.\nKeep it forever."
        label.font = .systemFont(ofSize: 16, weight: .regular)
        label.textColor = .lightGray
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
    }()

    private let priceLabel: UILabel = {
        let label = UILabel()
        label.text = "$14.99"
        label.font = .systemFont(ofSize: 48, weight: .heavy)
        label.textColor = .white
        label.textAlignment = .center
        return label
    }()

    private let priceSubLabel: UILabel = {
        let label = UILabel()
        label.text = "one-time purchase"
        label.font = .systemFont(ofSize: 14, weight: .medium)
        label.textColor = .systemGreen
        label.textAlignment = .center
        return label
    }()

    private let purchaseButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        btn.setTitle("Unlock Now — $14.99", for: .normal)
        btn.setTitleColor(.black, for: .normal)
        btn.titleLabel?.font = .systemFont(ofSize: 18, weight: .bold)
        btn.backgroundColor = .systemGreen
        btn.layer.cornerRadius = 14
        return btn
    }()

    private let spinner: UIActivityIndicatorView = {
        let s = UIActivityIndicatorView(style: .medium)
        s.translatesAutoresizingMaskIntoConstraints = false
        s.color = .black
        s.hidesWhenStopped = true
        return s
    }()

    private let restoreButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.setTitle("Already purchased? Restore", for: .normal)
        btn.setTitleColor(.systemGreen, for: .normal)
        btn.titleLabel?.font = .systemFont(ofSize: 14, weight: .medium)
        return btn
    }()

    private let features: [(icon: String, text: String)] = [
        ("figure.golf", "Swing Analysis — 20 fault corrections"),
        ("infinity", "Unlimited reps per day"),
        ("play.rectangle.fill", "A correction video with every session"),
        ("square.and.arrow.up", "Share results with your coach"),
    ]

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.08, green: 0.08, blue: 0.12, alpha: 1.0)
        setupUI()

        NotificationCenter.default.addObserver(
            self, selector: #selector(handleEntitlementChange),
            name: .entitlementDidChange, object: nil
        )
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    override var prefersStatusBarHidden: Bool { false }
    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    private func setupUI() {
        view.addSubview(scrollView)
        view.addSubview(closeButton)
        scrollView.addSubview(contentStack)

        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        purchaseButton.addTarget(self, action: #selector(purchaseTapped), for: .touchUpInside)
        restoreButton.addTarget(self, action: #selector(restoreTapped), for: .touchUpInside)

        purchaseButton.addSubview(spinner)

        let priceStack = UIStackView(arrangedSubviews: [priceLabel, priceSubLabel])
        priceStack.axis = .vertical
        priceStack.spacing = 4
        priceStack.alignment = .center

        contentStack.addArrangedSubview(iconView)
        contentStack.addArrangedSubview(titleLabel)
        contentStack.addArrangedSubview(subtitleLabel)
        contentStack.setCustomSpacing(32, after: subtitleLabel)

        let featuresStack = makeFeaturesStack()
        contentStack.addArrangedSubview(featuresStack)
        contentStack.setCustomSpacing(32, after: featuresStack)

        contentStack.addArrangedSubview(priceStack)
        contentStack.setCustomSpacing(24, after: priceStack)
        contentStack.addArrangedSubview(purchaseButton)
        contentStack.addArrangedSubview(restoreButton)

        NSLayoutConstraint.activate([
            closeButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            closeButton.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -16),
            closeButton.widthAnchor.constraint(equalToConstant: 36),
            closeButton.heightAnchor.constraint(equalToConstant: 36),

            scrollView.topAnchor.constraint(equalTo: closeButton.bottomAnchor, constant: 8),
            scrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            contentStack.topAnchor.constraint(equalTo: scrollView.topAnchor, constant: 16),
            contentStack.leadingAnchor.constraint(equalTo: scrollView.leadingAnchor, constant: 24),
            contentStack.trailingAnchor.constraint(equalTo: scrollView.trailingAnchor, constant: -24),
            contentStack.bottomAnchor.constraint(equalTo: scrollView.bottomAnchor, constant: -40),
            contentStack.widthAnchor.constraint(equalTo: scrollView.widthAnchor, constant: -48),

            iconView.heightAnchor.constraint(equalToConstant: 80),
            purchaseButton.heightAnchor.constraint(equalToConstant: 56),

            spinner.centerXAnchor.constraint(equalTo: purchaseButton.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: purchaseButton.centerYAnchor),
        ])
    }

    private func makeFeaturesStack() -> UIStackView {
        let stack = UIStackView()
        stack.axis = .vertical
        stack.spacing = 14

        for feature in features {
            let row = UIStackView()
            row.axis = .horizontal
            row.spacing = 12
            row.alignment = .center

            let icon = UIImageView()
            icon.translatesAutoresizingMaskIntoConstraints = false
            let config = UIImage.SymbolConfiguration(pointSize: 18, weight: .medium)
            icon.image = UIImage(systemName: feature.icon, withConfiguration: config)
            icon.tintColor = .systemGreen
            icon.contentMode = .scaleAspectFit
            icon.widthAnchor.constraint(equalToConstant: 28).isActive = true

            let label = UILabel()
            label.text = feature.text
            label.font = .systemFont(ofSize: 15, weight: .medium)
            label.textColor = .white
            label.numberOfLines = 0

            row.addArrangedSubview(icon)
            row.addArrangedSubview(label)
            stack.addArrangedSubview(row)
        }

        return stack
    }

    // MARK: - Actions

    @objc private func closeTapped() {
        dismiss(animated: true)
    }

    @objc private func purchaseTapped() {
        setLoading(true)

        let deviceId = EntitlementManager.shared.deviceId
        APIClient.shared.createCheckoutSession(deviceId: deviceId) { [weak self] result in
            DispatchQueue.main.async {
                self?.setLoading(false)
                switch result {
                case .success(let response):
                    self?.openCheckout(urlString: response.checkoutUrl)
                case .failure(let error):
                    self?.showError(error)
                }
            }
        }
    }

    @objc private func restoreTapped() {
        setLoading(true)

        EntitlementManager.shared.checkRemoteStatus { [weak self] unlocked in
            DispatchQueue.main.async {
                self?.setLoading(false)
                if unlocked {
                    EntitlementManager.shared.markUnlocked()
                    self?.showRestoreSuccess()
                } else {
                    self?.showRestoreNotFound()
                }
            }
        }
    }

    @objc private func handleEntitlementChange() {
        if EntitlementManager.shared.isUnlocked {
            dismiss(animated: true)
        }
    }

    // MARK: - Checkout

    private func openCheckout(urlString: String) {
        guard let url = URL(string: urlString) else {
            showError(APIError.invalidURL)
            return
        }

        let safari = SFSafariViewController(url: url)
        safari.preferredBarTintColor = UIColor(red: 0.08, green: 0.08, blue: 0.12, alpha: 1.0)
        safari.preferredControlTintColor = .systemGreen
        present(safari, animated: true)
    }

    // MARK: - UI State

    private func setLoading(_ loading: Bool) {
        purchaseButton.isEnabled = !loading
        restoreButton.isEnabled = !loading
        if loading {
            purchaseButton.setTitle("", for: .normal)
            spinner.startAnimating()
        } else {
            purchaseButton.setTitle("Unlock Now — $14.99", for: .normal)
            spinner.stopAnimating()
        }
    }

    private func showError(_ error: Error) {
        let alert = UIAlertController(
            title: "Error",
            message: error.localizedDescription,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    private func showRestoreSuccess() {
        let alert = UIAlertController(
            title: "Purchase Restored",
            message: "Your full access has been restored!",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default) { [weak self] _ in
            self?.dismiss(animated: true)
        })
        present(alert, animated: true)
    }

    private func showRestoreNotFound() {
        let alert = UIAlertController(
            title: "No Purchase Found",
            message: "No previous purchase was found for this device.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}
