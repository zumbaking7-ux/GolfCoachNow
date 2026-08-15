import UIKit

final class LoginViewController: UIViewController {

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
        let config = UIImage.SymbolConfiguration(pointSize: 50, weight: .medium)
        iv.image = UIImage(systemName: "person.crop.circle.fill", withConfiguration: config)
        iv.tintColor = .systemGreen
        iv.contentMode = .scaleAspectFit
        return iv
    }()

    private let titleLabel: UILabel = {
        let label = UILabel()
        label.text = "Sign In"
        label.font = .systemFont(ofSize: 28, weight: .bold)
        label.textColor = .white
        label.textAlignment = .center
        return label
    }()

    private let subtitleLabel: UILabel = {
        let label = UILabel()
        label.text = "Enter your email to receive a sign-in code.\nNo password needed."
        label.font = .systemFont(ofSize: 15, weight: .regular)
        label.textColor = .lightGray
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
    }()

    private let emailField: UITextField = {
        let field = UITextField()
        field.translatesAutoresizingMaskIntoConstraints = false
        field.placeholder = "Email address"
        field.font = .systemFont(ofSize: 17)
        field.textColor = .white
        field.backgroundColor = UIColor(red: 0.14, green: 0.14, blue: 0.18, alpha: 1.0)
        field.layer.cornerRadius = 12
        field.keyboardType = .emailAddress
        field.autocapitalizationType = .none
        field.autocorrectionType = .no
        field.textContentType = .emailAddress
        field.returnKeyType = .go
        let padding = UIView(frame: CGRect(x: 0, y: 0, width: 16, height: 0))
        field.leftView = padding
        field.leftViewMode = .always
        field.rightView = UIView(frame: CGRect(x: 0, y: 0, width: 16, height: 0))
        field.rightViewMode = .always
        field.attributedPlaceholder = NSAttributedString(
            string: "Email address",
            attributes: [.foregroundColor: UIColor.gray]
        )
        return field
    }()

    private let sendButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        btn.setTitle("Send Code", for: .normal)
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

    private let infoLabel: UILabel = {
        let label = UILabel()
        label.text = "We'll send a 6-digit code to your email.\nIt expires in 10 minutes."
        label.font = .systemFont(ofSize: 13, weight: .regular)
        label.textColor = UIColor.lightGray.withAlphaComponent(0.7)
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.08, green: 0.08, blue: 0.12, alpha: 1.0)
        setupUI()
        emailField.delegate = self
    }

    override var prefersStatusBarHidden: Bool { false }
    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    private func setupUI() {
        let stack = UIStackView(arrangedSubviews: [iconView, titleLabel, subtitleLabel, emailField, sendButton, infoLabel])
        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.axis = .vertical
        stack.spacing = 16
        stack.alignment = .fill

        stack.setCustomSpacing(8, after: iconView)
        stack.setCustomSpacing(32, after: subtitleLabel)
        stack.setCustomSpacing(16, after: emailField)
        stack.setCustomSpacing(20, after: sendButton)

        view.addSubview(closeButton)
        view.addSubview(stack)

        sendButton.addSubview(spinner)
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        sendButton.addTarget(self, action: #selector(sendTapped), for: .touchUpInside)

        NSLayoutConstraint.activate([
            closeButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            closeButton.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -16),
            closeButton.widthAnchor.constraint(equalToConstant: 36),
            closeButton.heightAnchor.constraint(equalToConstant: 36),

            stack.topAnchor.constraint(equalTo: closeButton.bottomAnchor, constant: 40),
            stack.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),

            iconView.heightAnchor.constraint(equalToConstant: 64),
            emailField.heightAnchor.constraint(equalToConstant: 52),
            sendButton.heightAnchor.constraint(equalToConstant: 56),

            spinner.centerXAnchor.constraint(equalTo: sendButton.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: sendButton.centerYAnchor),
        ])
    }

    @objc private func closeTapped() {
        dismiss(animated: true)
    }

    @objc private func sendTapped() {
        guard let email = emailField.text?.trimmingCharacters(in: .whitespacesAndNewlines),
              !email.isEmpty else {
            shake(emailField)
            return
        }

        view.endEditing(true)
        setLoading(true)

        APIClient.shared.requestLoginCode(email: email) { [weak self] result in
            DispatchQueue.main.async {
                self?.setLoading(false)
                switch result {
                case .success:
                    let verifyVC = VerifyCodeViewController(email: email)
                    verifyVC.modalPresentationStyle = .fullScreen
                    self?.present(verifyVC, animated: true)
                case .failure(let error):
                    self?.showError(error)
                }
            }
        }
    }

    private func setLoading(_ loading: Bool) {
        sendButton.isEnabled = !loading
        emailField.isEnabled = !loading
        if loading {
            sendButton.setTitle("", for: .normal)
            spinner.startAnimating()
        } else {
            sendButton.setTitle("Send Code", for: .normal)
            spinner.stopAnimating()
        }
    }

    private func shake(_ view: UIView) {
        let animation = CAKeyframeAnimation(keyPath: "transform.translation.x")
        animation.timingFunction = CAMediaTimingFunction(name: .linear)
        animation.duration = 0.4
        animation.values = [-8, 8, -6, 6, -4, 4, 0]
        view.layer.add(animation, forKey: "shake")
    }

    private func showError(_ error: Error) {
        let message: String
        if case APIError.requestFailed(statusCode: 429) = error {
            message = "Too many requests. Please wait a few minutes."
        } else {
            message = error.localizedDescription
        }
        let alert = UIAlertController(title: "Error", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

extension LoginViewController: UITextFieldDelegate {
    func textFieldShouldReturn(_ textField: UITextField) -> Bool {
        sendTapped()
        return true
    }
}
