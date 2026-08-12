import UIKit
import MessageUI

final class HomeViewController: UIViewController, MFMailComposeViewControllerDelegate {

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
        stack.spacing = 16
        stack.alignment = .fill
        return stack
    }()

    private let titleLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = "GolfCoachNow"
        label.font = .systemFont(ofSize: 32, weight: .bold)
        label.textColor = .white
        label.textAlignment = .center
        return label
    }()

    private let subtitleLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = "Choose your training mode"
        label.font = .systemFont(ofSize: 16, weight: .regular)
        label.textColor = .lightGray
        label.textAlignment = .center
        return label
    }()

    private let pulseView: UIView = {
        let v = UIView()
        v.translatesAutoresizingMaskIntoConstraints = false
        v.backgroundColor = UIColor(red: 0, green: 1, blue: 0.4, alpha: 1.0)
        v.layer.cornerRadius = 5
        v.alpha = 0.6
        return v
    }()

    private let pulseRing: UIView = {
        let v = UIView()
        v.translatesAutoresizingMaskIntoConstraints = false
        v.backgroundColor = .clear
        v.layer.cornerRadius = 12
        v.layer.borderWidth = 1.5
        v.layer.borderColor = UIColor(red: 0, green: 1, blue: 0.4, alpha: 0.3).cgColor
        return v
    }()

    private let contactButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        btn.setTitle("✉  We'd love to hear from you", for: .normal)
        btn.setTitleColor(UIColor(red: 0, green: 1, blue: 0.4, alpha: 0.7), for: .normal)
        btn.titleLabel?.font = .systemFont(ofSize: 13, weight: .medium)
        btn.backgroundColor = UIColor(red: 0, green: 1, blue: 0.4, alpha: 0.08)
        btn.layer.cornerRadius = 10
        btn.layer.borderWidth = 1
        btn.layer.borderColor = UIColor(red: 0, green: 1, blue: 0.4, alpha: 0.12).cgColor
        return btn
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(red: 0.08, green: 0.08, blue: 0.12, alpha: 1.0)
        navigationController?.setNavigationBarHidden(true, animated: false)
        setupUI()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        navigationController?.setNavigationBarHidden(true, animated: animated)
    }

    override var prefersStatusBarHidden: Bool { false }
    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    private func setupUI() {
        view.addSubview(scrollView)
        scrollView.addSubview(contentStack)

        let headerContainer = UIView()
        headerContainer.translatesAutoresizingMaskIntoConstraints = false

        let headerStack = UIStackView(arrangedSubviews: [titleLabel, subtitleLabel])
        headerStack.axis = .vertical
        headerStack.spacing = 8
        headerStack.alignment = .center
        headerStack.translatesAutoresizingMaskIntoConstraints = false

        headerContainer.addSubview(headerStack)
        headerContainer.addSubview(pulseRing)
        headerContainer.addSubview(pulseView)

        NSLayoutConstraint.activate([
            headerStack.topAnchor.constraint(equalTo: headerContainer.topAnchor),
            headerStack.leadingAnchor.constraint(equalTo: headerContainer.leadingAnchor),
            headerStack.trailingAnchor.constraint(equalTo: headerContainer.trailingAnchor),
            headerStack.bottomAnchor.constraint(equalTo: headerContainer.bottomAnchor),

            pulseView.widthAnchor.constraint(equalToConstant: 10),
            pulseView.heightAnchor.constraint(equalToConstant: 10),
            pulseView.centerYAnchor.constraint(equalTo: titleLabel.centerYAnchor),
            pulseView.leadingAnchor.constraint(equalTo: titleLabel.trailingAnchor, constant: 8),

            pulseRing.widthAnchor.constraint(equalToConstant: 24),
            pulseRing.heightAnchor.constraint(equalToConstant: 24),
            pulseRing.centerXAnchor.constraint(equalTo: pulseView.centerXAnchor),
            pulseRing.centerYAnchor.constraint(equalTo: pulseView.centerYAnchor),
        ])

        contentStack.addArrangedSubview(headerContainer)
        contentStack.setCustomSpacing(32, after: headerContainer)

        for module in GolfModule.allCases {
            let card = makeModuleCard(module)
            contentStack.addArrangedSubview(card)
        }

        contactButton.addTarget(self, action: #selector(contactTapped), for: .touchUpInside)
        contentStack.addArrangedSubview(contactButton)
        contentStack.setCustomSpacing(24, after: contentStack.arrangedSubviews[contentStack.arrangedSubviews.count - 2])

        NSLayoutConstraint.activate([
            scrollView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            scrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            contentStack.topAnchor.constraint(equalTo: scrollView.topAnchor, constant: 32),
            contentStack.leadingAnchor.constraint(equalTo: scrollView.leadingAnchor, constant: 20),
            contentStack.trailingAnchor.constraint(equalTo: scrollView.trailingAnchor, constant: -20),
            contentStack.bottomAnchor.constraint(equalTo: scrollView.bottomAnchor, constant: -32),
            contentStack.widthAnchor.constraint(equalTo: scrollView.widthAnchor, constant: -40),

            contactButton.heightAnchor.constraint(equalToConstant: 44),
        ])

        startPulseAnimation()
    }

    private func startPulseAnimation() {
        UIView.animate(withDuration: 1.5, delay: 0, options: [.autoreverse, .repeat, .curveEaseInOut]) {
            self.pulseView.alpha = 1.0
            self.pulseView.transform = CGAffineTransform(scaleX: 1.2, y: 1.2)
            self.pulseRing.alpha = 0.6
            self.pulseRing.transform = CGAffineTransform(scaleX: 1.3, y: 1.3)
        }
    }

    @objc private func contactTapped() {
        guard MFMailComposeViewController.canSendMail() else {
            let alert = UIAlertController(
                title: "Email Not Available",
                message: "Please set up a mail account to send feedback.",
                preferredStyle: .alert
            )
            alert.addAction(UIAlertAction(title: "OK", style: .default))
            present(alert, animated: true)
            return
        }

        let composer = MFMailComposeViewController()
        composer.mailComposeDelegate = self
        composer.setToRecipients(["support@golfcoachnow.net"])
        composer.setSubject("GolfCoachNow Feedback")
        composer.setMessageBody("We'd love to hear from you. Tell us what's on your mind.\n\n", isHTML: false)
        present(composer, animated: true)
    }

    func mailComposeController(_ controller: MFMailComposeViewController, didFinishWith result: MFMailComposeResult, error: Error?) {
        controller.dismiss(animated: true)
    }

    private func makeModuleCard(_ module: GolfModule) -> UIView {
        let card = UIView()
        card.translatesAutoresizingMaskIntoConstraints = false
        card.backgroundColor = UIColor(red: 0.14, green: 0.14, blue: 0.18, alpha: 1.0)
        card.layer.cornerRadius = 16

        let iconView = UIImageView()
        iconView.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 28, weight: .medium)
        iconView.image = UIImage(systemName: module.iconName, withConfiguration: config)
        iconView.tintColor = .systemGreen
        iconView.contentMode = .scaleAspectFit

        let titleLabel = UILabel()
        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.text = module.title
        titleLabel.font = .systemFont(ofSize: 20, weight: .semibold)
        titleLabel.textColor = .white

        let descLabel = UILabel()
        descLabel.translatesAutoresizingMaskIntoConstraints = false
        descLabel.text = module.subtitle
        descLabel.font = .systemFont(ofSize: 14, weight: .regular)
        descLabel.textColor = .lightGray
        descLabel.numberOfLines = 2

        let chevron = UIImageView()
        chevron.translatesAutoresizingMaskIntoConstraints = false
        let chevronConfig = UIImage.SymbolConfiguration(pointSize: 16, weight: .medium)
        chevron.image = UIImage(systemName: "chevron.right", withConfiguration: chevronConfig)
        chevron.tintColor = .systemGreen
        chevron.contentMode = .scaleAspectFit

        card.addSubview(iconView)
        card.addSubview(titleLabel)
        card.addSubview(descLabel)
        card.addSubview(chevron)

        NSLayoutConstraint.activate([
            card.heightAnchor.constraint(greaterThanOrEqualToConstant: 90),

            iconView.leadingAnchor.constraint(equalTo: card.leadingAnchor, constant: 16),
            iconView.centerYAnchor.constraint(equalTo: card.centerYAnchor),
            iconView.widthAnchor.constraint(equalToConstant: 44),
            iconView.heightAnchor.constraint(equalToConstant: 44),

            titleLabel.topAnchor.constraint(equalTo: card.topAnchor, constant: 18),
            titleLabel.leadingAnchor.constraint(equalTo: iconView.trailingAnchor, constant: 14),
            titleLabel.trailingAnchor.constraint(equalTo: chevron.leadingAnchor, constant: -8),

            descLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 4),
            descLabel.leadingAnchor.constraint(equalTo: titleLabel.leadingAnchor),
            descLabel.trailingAnchor.constraint(equalTo: titleLabel.trailingAnchor),
            descLabel.bottomAnchor.constraint(lessThanOrEqualTo: card.bottomAnchor, constant: -18),

            chevron.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -16),
            chevron.centerYAnchor.constraint(equalTo: card.centerYAnchor),
            chevron.widthAnchor.constraint(equalToConstant: 16),
        ])

        let tap = ModuleTapGesture(target: self, action: #selector(moduleTapped(_:)))
        tap.module = module
        card.addGestureRecognizer(tap)
        card.isUserInteractionEnabled = true

        return card
    }

    @objc private func moduleTapped(_ gesture: ModuleTapGesture) {
        guard let module = gesture.module else { return }

        UIView.animate(withDuration: 0.1, animations: {
            gesture.view?.transform = CGAffineTransform(scaleX: 0.97, y: 0.97)
        }) { _ in
            UIView.animate(withDuration: 0.1) {
                gesture.view?.transform = .identity
            }
        }

        APIClient.shared.trackEvent("module_selected", module: module)
        let cameraVC = CameraViewController(module: module)
        navigationController?.pushViewController(cameraVC, animated: true)
    }
}

private final class ModuleTapGesture: UITapGestureRecognizer {
    var module: GolfModule?
}
