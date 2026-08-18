import UIKit
import MessageUI

final class FounderMessageViewController: UIViewController, MFMailComposeViewControllerDelegate {

    private let closeButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 20, weight: .medium)
        btn.setImage(UIImage(systemName: "xmark", withConfiguration: config), for: .normal)
        btn.tintColor = .white
        return btn
    }()

    private let iconView: UIImageView = {
        let iv = UIImageView()
        iv.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 48, weight: .light)
            .applying(UIImage.SymbolConfiguration(hierarchicalColor: Theme.green))
        iv.image = UIImage(systemName: "headphones", withConfiguration: config)
        iv.contentMode = .scaleAspectFit
        return iv
    }()

    private let titleLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = "Talk to us."
        label.font = .systemFont(ofSize: 28, weight: .bold)
        label.textColor = .white
        label.textAlignment = .center
        return label
    }()

    private let bodyLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = "This message goes directly to the product developer, founder, and architect.\n\nWe read every message and respond personally."
        label.font = .systemFont(ofSize: 16, weight: .regular)
        label.textColor = Theme.textMuted
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
    }()

    private let composeButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        btn.setTitle("COMPOSE MESSAGE  →", for: .normal)
        btn.setTitleColor(Theme.textDark, for: .normal)
        btn.titleLabel?.font = .systemFont(ofSize: 14, weight: .heavy)
        btn.backgroundColor = Theme.green
        btn.layer.cornerRadius = Theme.ctaRadius
        return btn
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = Theme.background

        view.addSubview(closeButton)
        view.addSubview(iconView)
        view.addSubview(titleLabel)
        view.addSubview(bodyLabel)
        view.addSubview(composeButton)

        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        composeButton.addTarget(self, action: #selector(composeTapped), for: .touchUpInside)

        NSLayoutConstraint.activate([
            closeButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 16),
            closeButton.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),
            closeButton.widthAnchor.constraint(equalToConstant: 44),
            closeButton.heightAnchor.constraint(equalToConstant: 44),

            iconView.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            iconView.centerYAnchor.constraint(equalTo: view.centerYAnchor, constant: -100),
            iconView.widthAnchor.constraint(equalToConstant: 64),
            iconView.heightAnchor.constraint(equalToConstant: 64),

            titleLabel.topAnchor.constraint(equalTo: iconView.bottomAnchor, constant: 20),
            titleLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 32),
            titleLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -32),

            bodyLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 12),
            bodyLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 32),
            bodyLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -32),

            composeButton.topAnchor.constraint(equalTo: bodyLabel.bottomAnchor, constant: 32),
            composeButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            composeButton.widthAnchor.constraint(equalToConstant: 240),
            composeButton.heightAnchor.constraint(equalToConstant: 48),
        ])
    }

    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    @objc private func closeTapped() {
        dismiss(animated: true)
    }

    @objc private func composeTapped() {
        guard MFMailComposeViewController.canSendMail() else {
            let alert = UIAlertController(
                title: "Mail Not Configured",
                message: "Please set up a mail account in Settings to send messages.",
                preferredStyle: .alert
            )
            alert.addAction(UIAlertAction(title: "OK", style: .default))
            present(alert, animated: true)
            return
        }

        let mail = MFMailComposeViewController()
        mail.mailComposeDelegate = self
        // Superseded by ContactSheetViewController, which sends through our own
        // backend rather than the phone's mail app. Nothing presents this
        // controller any more; the address is corrected here only so that a
        // future reader cannot revive it and mail the wrong person.
        mail.setToRecipients(["zumba.king7@gmail.com"])
        mail.setSubject("GolfCoachNow Feedback")
        present(mail, animated: true)
    }

    func mailComposeController(_ controller: MFMailComposeViewController, didFinishWith result: MFMailComposeResult, error: Error?) {
        controller.dismiss(animated: true) { [weak self] in
            if result == .sent {
                self?.dismiss(animated: true)
            }
        }
    }
}
