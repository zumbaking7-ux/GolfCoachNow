import UIKit

/// The Share and Connect sheets.
///
/// One controller serves both because they are the same shape: a short
/// explanation, one or two fields, and a send action that can succeed, fail
/// with a reason worth reading, or be cancelled. Splitting them would duplicate
/// the state handling, which is the only part with any real complexity in it.
final class ContactSheetViewController: UIViewController {

    enum Mode {
        case shareWithFriend
        case connectWithFounder

        var heading: String {
            switch self {
            case .shareWithFriend: return "Share with a friend"
            case .connectWithFounder: return "Connect with the founder"
            }
        }

        var blurb: String {
            switch self {
            case .shareWithFriend: return "We'll email them a link to download Golf Coach Now."
            case .connectWithFounder: return "The founder welcomes your thoughts."
            }
        }

        var successMessage: String {
            switch self {
            case .shareWithFriend: return "Sent. Your friend will get a link to the app."
            case .connectWithFounder: return "Thanks. Your message is on its way to the founder."
            }
        }

        var emailPlaceholder: String {
            switch self {
            case .shareWithFriend: return "Their email address"
            case .connectWithFounder: return "Your email (optional, for a reply)"
            }
        }
    }

    private let mode: Mode

    init(mode: Mode) {
        self.mode = mode
        super.init(nibName: nil, bundle: nil)
        modalPresentationStyle = .formSheet
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) is not used; this controller is created in code")
    }

    // MARK: - Views

    private let headingLabel = ContactSheetViewController.makeLabel(size: 20, weight: .bold, color: .white)
    private let blurbLabel = ContactSheetViewController.makeLabel(size: 14, weight: .regular, color: .lightGray)
    private let statusLabel = ContactSheetViewController.makeLabel(size: 14, weight: .regular, color: .systemRed)

    private let messageView: UITextView = {
        let view = UITextView()
        view.translatesAutoresizingMaskIntoConstraints = false
        view.font = .systemFont(ofSize: 15)
        view.textColor = .white
        view.backgroundColor = UIColor.white.withAlphaComponent(0.08)
        view.layer.cornerRadius = 8
        view.textContainerInset = UIEdgeInsets(top: 10, left: 8, bottom: 10, right: 8)
        return view
    }()

    private let emailField: UITextField = {
        let field = UITextField()
        field.translatesAutoresizingMaskIntoConstraints = false
        field.font = .systemFont(ofSize: 16)
        field.textColor = .white
        field.backgroundColor = UIColor.white.withAlphaComponent(0.08)
        field.layer.cornerRadius = 8
        field.keyboardType = .emailAddress
        field.autocapitalizationType = .none
        field.autocorrectionType = .no
        field.leftView = UIView(frame: CGRect(x: 0, y: 0, width: 12, height: 1))
        field.leftViewMode = .always
        return field
    }()

    private let sendButton: UIButton = {
        let button = UIButton(type: .system)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.setTitle("SEND", for: .normal)
        button.titleLabel?.font = .systemFont(ofSize: 15, weight: .bold)
        button.setTitleColor(.black, for: .normal)
        button.backgroundColor = .systemGreen
        button.layer.cornerRadius = 10
        return button
    }()

    private let cancelButton: UIButton = {
        let button = UIButton(type: .system)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.setTitle("Cancel", for: .normal)
        button.titleLabel?.font = .systemFont(ofSize: 15)
        button.setTitleColor(.lightGray, for: .normal)
        return button
    }()

    private let spinner: UIActivityIndicatorView = {
        let view = UIActivityIndicatorView(style: .medium)
        view.translatesAutoresizingMaskIntoConstraints = false
        view.color = .white
        view.hidesWhenStopped = true
        return view
    }()

    private static func makeLabel(size: CGFloat, weight: UIFont.Weight, color: UIColor) -> UILabel {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.font = .systemFont(ofSize: size, weight: weight)
        label.textColor = color
        label.numberOfLines = 0
        return label
    }

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(white: 0.07, alpha: 1)

        headingLabel.text = mode.heading
        blurbLabel.text = mode.blurb
        statusLabel.isHidden = true

        emailField.attributedPlaceholder = NSAttributedString(
            string: mode.emailPlaceholder,
            attributes: [.foregroundColor: UIColor.gray]
        )

        let stack = UIStackView(arrangedSubviews: [headingLabel, blurbLabel])
        if mode == .connectWithFounder {
            stack.addArrangedSubview(messageView)
        }
        stack.addArrangedSubview(emailField)
        stack.addArrangedSubview(statusLabel)
        stack.axis = .vertical
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(stack)
        view.addSubview(sendButton)
        view.addSubview(cancelButton)
        view.addSubview(spinner)

        sendButton.addTarget(self, action: #selector(sendTapped), for: .touchUpInside)
        cancelButton.addTarget(self, action: #selector(cancelTapped), for: .touchUpInside)

        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 24),
            stack.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            stack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),

            emailField.heightAnchor.constraint(equalToConstant: 44),

            sendButton.topAnchor.constraint(equalTo: stack.bottomAnchor, constant: 20),
            sendButton.leadingAnchor.constraint(equalTo: stack.leadingAnchor),
            sendButton.trailingAnchor.constraint(equalTo: stack.trailingAnchor),
            sendButton.heightAnchor.constraint(equalToConstant: 46),

            spinner.centerXAnchor.constraint(equalTo: sendButton.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: sendButton.centerYAnchor),

            cancelButton.topAnchor.constraint(equalTo: sendButton.bottomAnchor, constant: 8),
            cancelButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
        ])

        if mode == .connectWithFounder {
            messageView.heightAnchor.constraint(equalToConstant: 120).isActive = true
        }
    }

    // MARK: - Actions

    @objc private func cancelTapped() {
        dismiss(animated: true)
    }

    @objc private func sendTapped() {
        let email = emailField.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let message = messageView.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        // Not full validation, which the server does. This only avoids spending
        // a round trip on something obviously incomplete.
        if mode == .shareWithFriend, !email.contains("@") {
            show("Enter your friend's email address.")
            return
        }
        if mode == .connectWithFounder, message.isEmpty {
            show("Write a message first.")
            return
        }

        setSending(true)

        let done: (Result<Void, Error>) -> Void = { [weak self] result in
            DispatchQueue.main.async {
                guard let self else { return }
                self.setSending(false)
                switch result {
                case .success:
                    self.showSuccess()
                case .failure(let error):
                    self.show(self.explain(error))
                }
            }
        }

        switch mode {
        case .shareWithFriend:
            APIClient.shared.shareWithFriend(email: email, completion: done)
        case .connectWithFounder:
            APIClient.shared.messageFounder(message: message, email: email, completion: done)
        }
    }

    // MARK: - Presentation

    /// The server separates these cases deliberately, so collapsing them into
    /// one message would leave somebody retyping a perfectly good address
    /// against a limit that has nothing to do with it.
    private func explain(_ error: Error) -> String {
        if let apiError = error as? APIError, case .requestFailed(let code) = apiError {
            switch code {
            case 422: return "That doesn't look like a valid email address."
            case 429: return "That's been sent a few times already. Try again a little later."
            case 503: return "Sharing isn't switched on yet. Please try again soon."
            default: break
            }
        }
        return "Couldn't send that. Check your connection and try again."
    }

    private func show(_ message: String) {
        statusLabel.textColor = .systemRed
        statusLabel.text = message
        statusLabel.isHidden = false
    }

    private func showSuccess() {
        statusLabel.textColor = .systemGreen
        statusLabel.text = mode.successMessage
        statusLabel.isHidden = false

        messageView.isHidden = true
        emailField.isHidden = true
        sendButton.isHidden = true
        cancelButton.setTitle("Done", for: .normal)
    }

    private func setSending(_ sending: Bool) {
        sendButton.setTitle(sending ? "" : "SEND", for: .normal)
        sendButton.isEnabled = !sending
        if sending {
            spinner.startAnimating()
            statusLabel.isHidden = true
        } else {
            spinner.stopAnimating()
        }
    }
}
