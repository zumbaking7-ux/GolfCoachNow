import UIKit

final class VerifyCodeViewController: UIViewController {

    private let email: String

    /// True once the code has been accepted and the account turned out to have
    /// no name. The same button then means Continue rather than Verify.
    private var askingForName = false

    init(email: String) {
        self.email = email
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) { fatalError() }

    private let backButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 18, weight: .medium)
        btn.setImage(UIImage(systemName: "chevron.left.circle.fill", withConfiguration: config), for: .normal)
        btn.tintColor = .lightGray
        return btn
    }()

    private let iconView: UIImageView = {
        let iv = UIImageView()
        iv.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 50, weight: .medium)
        iv.image = UIImage(systemName: "envelope.badge.fill", withConfiguration: config)
        iv.tintColor = .systemGreen
        iv.contentMode = .scaleAspectFit
        return iv
    }()

    private let titleLabel: UILabel = {
        let label = UILabel()
        label.text = "Check Your Email"
        label.font = .systemFont(ofSize: 28, weight: .bold)
        label.textColor = .white
        label.textAlignment = .center
        return label
    }()

    private let subtitleLabel: UILabel = {
        let label = UILabel()
        label.font = .systemFont(ofSize: 15, weight: .regular)
        label.textColor = .lightGray
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
    }()

    private var digitFields: [UITextField] = []

    /// Holds the six code boxes. A property rather than a local, because it is
    /// hidden once the code is accepted and the name step takes over.
    private let digitsStack = UIStackView()

    /// Asked for here rather than on the email screen so requesting a code
    /// stays a single field. Optional: left blank it never erases a name
    /// already stored on the account.
    private let nameField: UITextField = {
        let field = UITextField()
        field.translatesAutoresizingMaskIntoConstraints = false
        field.font = .systemFont(ofSize: 17, weight: .medium)
        field.textColor = .white
        field.textAlignment = .center
        field.backgroundColor = UIColor(red: 0.14, green: 0.14, blue: 0.18, alpha: 1.0)
        field.layer.cornerRadius = 12
        field.autocapitalizationType = .words
        field.textContentType = .givenName
        field.attributedPlaceholder = NSAttributedString(
            string: "Your first name",
            attributes: [.foregroundColor: UIColor(white: 1, alpha: 0.35)]
        )
        return field
    }()

    private let verifyButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        btn.setTitle("Verify", for: .normal)
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

    private let resendButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.setTitle("Resend Code", for: .normal)
        btn.setTitleColor(.systemGreen, for: .normal)
        btn.titleLabel?.font = .systemFont(ofSize: 14, weight: .medium)
        return btn
    }()

    private let warningLabel: UILabel = {
        let label = UILabel()
        label.text = "Requesting a new code will invalidate the current one."
        label.font = .systemFont(ofSize: 12, weight: .regular)
        label.textColor = UIColor.lightGray.withAlphaComponent(0.5)
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.08, green: 0.08, blue: 0.12, alpha: 1.0)
        subtitleLabel.text = "We sent a 6-digit code to\n\(email)"
        setupUI()
        // Hidden until the code has been accepted and the account turns out
        // to have no name. Asking here rather than alongside the code, because
        // the alternative reveals which addresses have accounts.
        nameField.isHidden = true
        verifyButton.setTitle("Verify", for: .normal)
        // Only ask a name the first time this device signs in with this
        // address. Asking every time invites people to keep changing it.
        nameField.text = nil
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        digitFields.first?.becomeFirstResponder()
    }

    override var prefersStatusBarHidden: Bool { false }
    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    private func setupUI() {
        digitsStack.translatesAutoresizingMaskIntoConstraints = false
        digitsStack.axis = .horizontal
        digitsStack.spacing = 10
        digitsStack.distribution = .fillEqually

        for i in 0..<6 {
            let field = UITextField()
            field.translatesAutoresizingMaskIntoConstraints = false
            field.font = .systemFont(ofSize: 28, weight: .bold)
            field.textColor = .white
            field.textAlignment = .center
            field.backgroundColor = UIColor(red: 0.14, green: 0.14, blue: 0.18, alpha: 1.0)
            field.layer.cornerRadius = 12
            field.keyboardType = .numberPad
            field.textContentType = .oneTimeCode
            field.tag = i
            field.delegate = self
            digitFields.append(field)
            digitsStack.addArrangedSubview(field)
        }

        let stack = UIStackView(arrangedSubviews: [iconView, titleLabel, subtitleLabel, digitsStack, nameField, verifyButton, resendButton, warningLabel])
        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.axis = .vertical
        stack.spacing = 16
        stack.alignment = .fill

        stack.setCustomSpacing(8, after: iconView)
        stack.setCustomSpacing(32, after: subtitleLabel)
        stack.setCustomSpacing(16, after: digitsStack)
        stack.setCustomSpacing(24, after: nameField)
        stack.setCustomSpacing(16, after: verifyButton)
        stack.setCustomSpacing(4, after: resendButton)

        view.addSubview(backButton)
        view.addSubview(stack)
        verifyButton.addSubview(spinner)

        backButton.addTarget(self, action: #selector(backTapped), for: .touchUpInside)
        verifyButton.addTarget(self, action: #selector(verifyTapped), for: .touchUpInside)
        resendButton.addTarget(self, action: #selector(resendTapped), for: .touchUpInside)

        NSLayoutConstraint.activate([
            backButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            backButton.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 16),
            backButton.widthAnchor.constraint(equalToConstant: 36),
            backButton.heightAnchor.constraint(equalToConstant: 36),

            stack.topAnchor.constraint(equalTo: backButton.bottomAnchor, constant: 40),
            stack.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),

            iconView.heightAnchor.constraint(equalToConstant: 64),
            nameField.heightAnchor.constraint(equalToConstant: 52),
            verifyButton.heightAnchor.constraint(equalToConstant: 56),

            spinner.centerXAnchor.constraint(equalTo: verifyButton.centerXAnchor),
            spinner.centerYAnchor.constraint(equalTo: verifyButton.centerYAnchor),
        ])

        for field in digitFields {
            field.heightAnchor.constraint(equalToConstant: 56).isActive = true
        }
    }

    @objc private func backTapped() {
        dismiss(animated: true)
    }

    @objc private func verifyTapped() {
        if askingForName {
            saveNameAndFinish()
            return
        }

        let code = digitFields.map { $0.text ?? "" }.joined()
        guard code.count == 6 else {
            shakeFields()
            return
        }

        view.endEditing(true)
        setLoading(true)

        APIClient.shared.verifyLoginCode(
            email: email,
            code: code,
            name: nil
        ) { [weak self] result in
            DispatchQueue.main.async {
                self?.setLoading(false)
                switch result {
                case .success(let signedIn):
                    self?.handleSuccess(token: signedIn.token, name: signedIn.name)
                case .failure(let error):
                    self?.handleFailure(error)
                }
            }
        }
    }

    @objc private func resendTapped() {
        digitFields.forEach { $0.text = "" }
        digitFields.first?.becomeFirstResponder()

        resendButton.isEnabled = false
        resendButton.setTitle("Sending...", for: .normal)

        APIClient.shared.requestLoginCode(email: email) { [weak self] result in
            DispatchQueue.main.async {
                self?.resendButton.isEnabled = true
                self?.resendButton.setTitle("Resend Code", for: .normal)
                switch result {
                case .success:
                    self?.showToast("New code sent")
                case .failure:
                    self?.showError("Failed to resend. Try again.")
                }
            }
        }
    }

    private func handleSuccess(token: String, name: String?) {
        AuthManager.shared.token = token
        AuthManager.shared.email = email
        AuthManager.shared.name = name
        NotificationCenter.default.post(name: .authStateDidChange, object: nil)
        EntitlementManager.shared.checkRemoteStatus()

        // A returning golfer already has a name and is never asked again, on
        // any device. Only an account without one sees the field.
        if (name ?? "").isEmpty {
            askForName()
            return
        }

        finish()
    }

    private func askForName() {
        titleLabel.text = "Almost there"
        subtitleLabel.text = "What should we call you?"
        digitsStack.isHidden = true
        resendButton.isHidden = true
        nameField.isHidden = false
        verifyButton.setTitle("Continue", for: .normal)
        askingForName = true
        nameField.becomeFirstResponder()
    }

    private func saveNameAndFinish() {
        let typed = (nameField.text ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !typed.isEmpty else {
            finish()
            return
        }

        view.endEditing(true)
        setLoading(true)
        APIClient.shared.setName(typed) { [weak self] result in
            DispatchQueue.main.async {
                self?.setLoading(false)
                if case .success = result {
                    AuthManager.shared.name = typed
                    NotificationCenter.default.post(name: .authStateDidChange, object: nil)
                }
                // Signed in either way. A name is a nicety, and failing to
                // store one must not strand somebody who has already proved
                // who they are.
                self?.finish()
            }
        }
    }

    private func finish() {
        let presenting = presentingViewController?.presentingViewController
        presenting?.dismiss(animated: true)
    }

    private func handleFailure(_ error: Error) {
        digitFields.forEach { $0.text = "" }
        digitFields.first?.becomeFirstResponder()
        shakeFields()

        if case APIError.requestFailed(statusCode: 401) = error {
            showError("Invalid or expired code. Try again.")
        } else {
            showError(error.localizedDescription)
        }
    }

    private func setLoading(_ loading: Bool) {
        verifyButton.isEnabled = !loading
        resendButton.isEnabled = !loading
        digitFields.forEach { $0.isEnabled = !loading }
        if loading {
            verifyButton.setTitle("", for: .normal)
            spinner.startAnimating()
        } else {
            verifyButton.setTitle("Verify", for: .normal)
            spinner.stopAnimating()
        }
    }

    private func shakeFields() {
        let animation = CAKeyframeAnimation(keyPath: "transform.translation.x")
        animation.timingFunction = CAMediaTimingFunction(name: .linear)
        animation.duration = 0.4
        animation.values = [-8, 8, -6, 6, -4, 4, 0]
        for field in digitFields {
            field.layer.add(animation, forKey: "shake")
        }
    }

    private func showToast(_ message: String) {
        let label = UILabel()
        label.text = message
        label.font = .systemFont(ofSize: 14, weight: .medium)
        label.textColor = .white
        label.backgroundColor = UIColor.systemGreen.withAlphaComponent(0.9)
        label.textAlignment = .center
        label.layer.cornerRadius = 8
        label.clipsToBounds = true
        label.translatesAutoresizingMaskIntoConstraints = false

        view.addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            label.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -20),
            label.widthAnchor.constraint(equalToConstant: 160),
            label.heightAnchor.constraint(equalToConstant: 36),
        ])

        label.alpha = 0
        UIView.animate(withDuration: 0.3) { label.alpha = 1 }
        UIView.animate(withDuration: 0.3, delay: 2.0) {
            label.alpha = 0
        } completion: { _ in
            label.removeFromSuperview()
        }
    }

    private func showError(_ message: String) {
        let alert = UIAlertController(title: "Error", message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

extension VerifyCodeViewController: UITextFieldDelegate {

    func textField(_ textField: UITextField, shouldChangeCharactersIn range: NSRange, replacementString string: String) -> Bool {
        if string.isEmpty {
            textField.text = ""
            if textField.tag > 0 {
                digitFields[textField.tag - 1].becomeFirstResponder()
            }
            return false
        }

        let digits = string.filter(\.isNumber)
        guard !digits.isEmpty else { return false }

        if digits.count == 6 {
            for (i, char) in digits.enumerated() where i < 6 {
                digitFields[i].text = String(char)
            }
            digitFields.last?.becomeFirstResponder()
            return false
        }

        textField.text = String(digits.first!)
        if textField.tag < 5 {
            digitFields[textField.tag + 1].becomeFirstResponder()
        }
        return false
    }
}
