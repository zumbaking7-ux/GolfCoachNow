import UIKit
import MessageUI

final class HomeViewController: UIViewController, MFMailComposeViewControllerDelegate {

    private let scrollView: UIScrollView = {
        let sv = UIScrollView()
        sv.translatesAutoresizingMaskIntoConstraints = false
        sv.showsVerticalScrollIndicator = false
        return sv
    }()

    private let contentView: UIView = {
        let v = UIView()
        v.translatesAutoresizingMaskIntoConstraints = false
        return v
    }()

    // MARK: - Banner

    private let bannerImageView: UIImageView = {
        let iv = UIImageView(image: UIImage(named: "banner"))
        iv.translatesAutoresizingMaskIntoConstraints = false
        iv.contentMode = .scaleAspectFill
        iv.clipsToBounds = true
        return iv
    }()

    // MARK: - Greeting Card

    private let greetingCard: UIView = {
        let v = UIView()
        v.translatesAutoresizingMaskIntoConstraints = false
        v.backgroundColor = Theme.greetingBackground
        v.layer.cornerRadius = Theme.cardRadius
        v.layer.borderWidth = 1
        v.layer.borderColor = Theme.greenBorder.cgColor
        return v
    }()

    private let greetingAccent: UIView = {
        let v = UIView()
        v.translatesAutoresizingMaskIntoConstraints = false
        v.backgroundColor = Theme.green
        v.layer.cornerRadius = 1.5
        return v
    }()

    private let greetingLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.numberOfLines = 0
        return label
    }()

    private let questionLabel: UILabel = {
        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = "What would you like\nto learn today?"
        label.font = .systemFont(ofSize: 14, weight: .regular)
        label.textColor = UIColor(white: 0.7, alpha: 1.0)
        label.numberOfLines = 2
        return label
    }()

    // MARK: - Skill Cards

    private let skillStack: UIStackView = {
        let s = UIStackView()
        s.translatesAutoresizingMaskIntoConstraints = false
        s.axis = .horizontal
        s.spacing = Theme.cardGap
        s.distribution = .fillEqually
        return s
    }()

    // MARK: - Action Row

    private let actionStack: UIStackView = {
        let s = UIStackView()
        s.translatesAutoresizingMaskIntoConstraints = false
        s.axis = .horizontal
        s.spacing = Theme.cardGap
        s.distribution = .fillEqually
        return s
    }()

    // MARK: - Account

    private let accountButton: UIButton = {
        let btn = UIButton(type: .system)
        btn.translatesAutoresizingMaskIntoConstraints = false
        btn.titleLabel?.font = .systemFont(ofSize: 13, weight: .medium)
        btn.layer.cornerRadius = 10
        btn.backgroundColor = UIColor(white: 1, alpha: 0.05)
        btn.contentEdgeInsets = UIEdgeInsets(top: 0, left: 16, bottom: 0, right: 16)
        return btn
    }()

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = Theme.background
        navigationController?.setNavigationBarHidden(true, animated: false)
        setupUI()
        updateGreeting()
        updateAccountButton()

        NotificationCenter.default.addObserver(
            self, selector: #selector(authStateChanged),
            name: .authStateDidChange, object: nil
        )
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        navigationController?.setNavigationBarHidden(true, animated: animated)
        updateGreeting()
    }

    override var prefersStatusBarHidden: Bool { false }
    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }

    // MARK: - Setup

    private func setupUI() {
        view.addSubview(scrollView)
        scrollView.addSubview(contentView)

        contentView.addSubview(bannerImageView)
        contentView.addSubview(greetingCard)
        contentView.addSubview(skillStack)
        contentView.addSubview(actionStack)
        contentView.addSubview(accountButton)

        setupGreetingCard()
        setupSkillCards()
        setupActionRow()

        accountButton.addTarget(self, action: #selector(accountTapped), for: .touchUpInside)

        NSLayoutConstraint.activate([
            scrollView.topAnchor.constraint(equalTo: view.topAnchor),
            scrollView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scrollView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scrollView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            contentView.topAnchor.constraint(equalTo: scrollView.topAnchor),
            contentView.leadingAnchor.constraint(equalTo: scrollView.leadingAnchor),
            contentView.trailingAnchor.constraint(equalTo: scrollView.trailingAnchor),
            contentView.bottomAnchor.constraint(equalTo: scrollView.bottomAnchor),
            contentView.widthAnchor.constraint(equalTo: scrollView.widthAnchor),

            bannerImageView.topAnchor.constraint(equalTo: contentView.topAnchor),
            bannerImageView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            bannerImageView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            bannerImageView.heightAnchor.constraint(equalToConstant: Theme.bannerHeight),

            greetingCard.topAnchor.constraint(equalTo: bannerImageView.bottomAnchor, constant: Theme.greetingOverlap),
            greetingCard.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: Theme.screenPadding),
            greetingCard.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -Theme.screenPadding),

            skillStack.topAnchor.constraint(equalTo: greetingCard.bottomAnchor, constant: 12),
            skillStack.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: Theme.screenPadding),
            skillStack.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -Theme.screenPadding),

            actionStack.topAnchor.constraint(equalTo: skillStack.bottomAnchor, constant: Theme.cardGap),
            actionStack.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: Theme.screenPadding),
            actionStack.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -Theme.screenPadding),

            accountButton.topAnchor.constraint(equalTo: actionStack.bottomAnchor, constant: 16),
            accountButton.centerXAnchor.constraint(equalTo: contentView.centerXAnchor),
            accountButton.heightAnchor.constraint(equalToConstant: 40),
            accountButton.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -32),
        ])
    }

    private func setupGreetingCard() {
        greetingCard.addSubview(greetingAccent)
        greetingCard.addSubview(greetingLabel)
        greetingCard.addSubview(questionLabel)

        NSLayoutConstraint.activate([
            greetingAccent.leadingAnchor.constraint(equalTo: greetingCard.leadingAnchor, constant: 14),
            greetingAccent.topAnchor.constraint(equalTo: greetingCard.topAnchor, constant: 14),
            greetingAccent.bottomAnchor.constraint(equalTo: greetingCard.bottomAnchor, constant: -14),
            greetingAccent.widthAnchor.constraint(equalToConstant: 3),

            greetingLabel.topAnchor.constraint(equalTo: greetingCard.topAnchor, constant: 14),
            greetingLabel.leadingAnchor.constraint(equalTo: greetingAccent.trailingAnchor, constant: 12),
            greetingLabel.trailingAnchor.constraint(equalTo: greetingCard.trailingAnchor, constant: -14),

            questionLabel.topAnchor.constraint(equalTo: greetingLabel.bottomAnchor, constant: 4),
            questionLabel.leadingAnchor.constraint(equalTo: greetingLabel.leadingAnchor),
            questionLabel.trailingAnchor.constraint(equalTo: greetingLabel.trailingAnchor),
            questionLabel.bottomAnchor.constraint(equalTo: greetingCard.bottomAnchor, constant: -14),
        ])
    }

    private func updateGreeting() {
        // The name comes from the account. "there" is the fallback for anyone
        // signed out, or signed in before names were captured.
        let stored = AuthManager.shared.name?.trimmingCharacters(in: .whitespacesAndNewlines)
        let name = (stored?.isEmpty == false) ? stored! : "there"

        let bold: [NSAttributedString.Key: Any] = [
            .font: UIFont.systemFont(ofSize: 24, weight: .bold),
            .foregroundColor: UIColor.white
        ]

        let text = NSMutableAttributedString()
        text.append(NSAttributedString(string: "Hi ", attributes: bold))
        text.append(NSAttributedString(
            string: name,
            attributes: [
                .font: UIFont.systemFont(ofSize: 24, weight: .bold),
                .foregroundColor: Theme.green
            ]
        ))
        text.append(NSAttributedString(string: ".", attributes: bold))
        greetingLabel.attributedText = text
    }

    // MARK: - Skill Cards

    private func setupSkillCards() {
        skillStack.addArrangedSubview(makeSkillCard(
            title: "SWING LEARN",
            description: "See the grip, stance and swing.",
            ctaTitle: "WATCH  →",
            iconAsset: GolfModule.swing.cardIconAsset,
            action: #selector(learnTapped(_:))
        ))
        skillStack.addArrangedSubview(makeSkillCard(
            title: "SWING CORRECT",
            description: "Record and get instant feedback.",
            ctaTitle: "START  →",
            iconAsset: GolfModule.swing.cardIconAsset,
            action: #selector(correctTapped(_:))
        ))
    }

    private func makeSkillCard(
        title: String,
        description: String,
        ctaTitle: String,
        iconAsset: String,
        action: Selector
    ) -> UIView {
        let card = UIView()
        card.translatesAutoresizingMaskIntoConstraints = false
        card.backgroundColor = Theme.cardBackground
        card.layer.cornerRadius = Theme.cardRadius
        card.layer.borderWidth = 1
        card.layer.borderColor = Theme.greenBorder.cgColor

        let iconContainer = UIImageView()
        iconContainer.translatesAutoresizingMaskIntoConstraints = false
        iconContainer.image = UIImage(named: iconAsset)
        iconContainer.contentMode = .scaleAspectFill
        iconContainer.clipsToBounds = true
        iconContainer.layer.cornerRadius = Theme.iconBoxRadius

        let titleLabel = UILabel()
        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.text = title
        titleLabel.font = .systemFont(ofSize: 13, weight: .heavy)
        titleLabel.textColor = Theme.textPrimary
        titleLabel.textAlignment = .center

        let descLabel = UILabel()
        descLabel.translatesAutoresizingMaskIntoConstraints = false
        descLabel.text = description
        descLabel.font = .systemFont(ofSize: 11, weight: .regular)
        descLabel.textColor = Theme.textMuted
        descLabel.textAlignment = .center
        descLabel.numberOfLines = 2

        let ctaContainer = GradientButton(title: ctaTitle)

        card.addSubview(iconContainer)
        card.addSubview(titleLabel)
        card.addSubview(descLabel)
        card.addSubview(ctaContainer)

        NSLayoutConstraint.activate([
            iconContainer.topAnchor.constraint(equalTo: card.topAnchor, constant: 14),
            iconContainer.centerXAnchor.constraint(equalTo: card.centerXAnchor),
            iconContainer.widthAnchor.constraint(equalToConstant: Theme.iconBoxSize),
            iconContainer.heightAnchor.constraint(equalToConstant: Theme.iconBoxSize),

            titleLabel.topAnchor.constraint(equalTo: iconContainer.bottomAnchor, constant: 10),
            titleLabel.leadingAnchor.constraint(equalTo: card.leadingAnchor, constant: 6),
            titleLabel.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -6),

            descLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 4),
            descLabel.leadingAnchor.constraint(equalTo: card.leadingAnchor, constant: 6),
            descLabel.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -6),

            ctaContainer.topAnchor.constraint(equalTo: descLabel.bottomAnchor, constant: 10),
            ctaContainer.leadingAnchor.constraint(equalTo: card.leadingAnchor, constant: 8),
            ctaContainer.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -8),
            ctaContainer.heightAnchor.constraint(equalToConstant: 30),
            ctaContainer.bottomAnchor.constraint(equalTo: card.bottomAnchor, constant: -12),
        ])

        card.addGestureRecognizer(UITapGestureRecognizer(target: self, action: action))
        card.isUserInteractionEnabled = true

        return card
    }

    // MARK: - Action Row

    private func setupActionRow() {
        // Connect on the left, Share on the right, as specified. The stack
        // distributes them equally, so the two read as a matched pair.
        let connectCard = makeActionCard(
            icon: "headphones",
            title: "CONNECT",
            description: "The founder welcomes your thoughts",
            action: #selector(connectTapped)
        )
        let shareCard = makeActionCard(
            icon: "bubble.left.fill",
            title: "SHARE",
            description: "Send the app to a friend",
            action: #selector(sendTapped)
        )
        actionStack.addArrangedSubview(connectCard)
        actionStack.addArrangedSubview(shareCard)
    }

    private func makeActionCard(icon: String, title: String, description: String, action: Selector) -> UIView {
        let card = UIView()
        card.translatesAutoresizingMaskIntoConstraints = false
        card.backgroundColor = Theme.cardBackground
        card.layer.cornerRadius = Theme.cardRadius
        card.layer.borderWidth = 1
        card.layer.borderColor = Theme.greenBorder.cgColor

        let iconView = UIImageView()
        iconView.translatesAutoresizingMaskIntoConstraints = false
        let config = UIImage.SymbolConfiguration(pointSize: 20, weight: .medium)
            .applying(UIImage.SymbolConfiguration(hierarchicalColor: Theme.green))
        iconView.image = UIImage(systemName: icon, withConfiguration: config)
        iconView.contentMode = .scaleAspectFit

        let titleLabel = UILabel()
        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.text = title
        titleLabel.font = .systemFont(ofSize: 14, weight: .bold)
        titleLabel.textColor = Theme.textPrimary

        let descLabel = UILabel()
        descLabel.translatesAutoresizingMaskIntoConstraints = false
        descLabel.text = description
        descLabel.font = .systemFont(ofSize: 11, weight: .regular)
        descLabel.textColor = Theme.textMuted
        descLabel.numberOfLines = 2

        let arrow = UILabel()
        arrow.translatesAutoresizingMaskIntoConstraints = false
        arrow.text = "→"
        arrow.font = .systemFont(ofSize: 16, weight: .medium)
        arrow.textColor = Theme.green

        card.addSubview(iconView)
        card.addSubview(titleLabel)
        card.addSubview(descLabel)
        card.addSubview(arrow)

        NSLayoutConstraint.activate([
            card.heightAnchor.constraint(equalToConstant: 72),

            iconView.leadingAnchor.constraint(equalTo: card.leadingAnchor, constant: 12),
            iconView.centerYAnchor.constraint(equalTo: card.centerYAnchor),
            iconView.widthAnchor.constraint(equalToConstant: 28),
            iconView.heightAnchor.constraint(equalToConstant: 28),

            titleLabel.topAnchor.constraint(equalTo: card.topAnchor, constant: 14),
            titleLabel.leadingAnchor.constraint(equalTo: iconView.trailingAnchor, constant: 10),
            titleLabel.trailingAnchor.constraint(equalTo: arrow.leadingAnchor, constant: -8),

            descLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 2),
            descLabel.leadingAnchor.constraint(equalTo: titleLabel.leadingAnchor),
            descLabel.trailingAnchor.constraint(equalTo: titleLabel.trailingAnchor),

            arrow.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -14),
            arrow.centerYAnchor.constraint(equalTo: card.centerYAnchor),
        ])

        let tap = UITapGestureRecognizer(target: self, action: action)
        card.addGestureRecognizer(tap)
        card.isUserInteractionEnabled = true

        return card
    }

    // MARK: - Actions

    @objc private func learnTapped(_ gesture: UITapGestureRecognizer) {
        bounce(gesture.view)
        APIClient.shared.trackEvent("module_selected", module: .swing)
        playLesson()
    }

    @objc private func correctTapped(_ gesture: UITapGestureRecognizer) {
        bounce(gesture.view)
        APIClient.shared.trackEvent("module_selected", module: .swing)
        navigationController?.pushViewController(
            CameraViewController(module: .swing),
            animated: true
        )
    }

    private func bounce(_ view: UIView?) {
        UIView.animate(withDuration: 0.1, animations: {
            view?.transform = CGAffineTransform(scaleX: 0.95, y: 0.95)
        }) { _ in
            UIView.animate(withDuration: 0.1) {
                view?.transform = .identity
            }
        }
    }

    /// Plays the lesson clip behind Swing Learn.
    ///
    /// Version 1 ships one instructional video, shared across modes. Until it
    /// is published the lookup returns no url, and the golfer is told that
    /// plainly: a button that quietly does nothing reads as a broken app.
    private func playLesson() {
        APIClient.shared.fetchInstructionalVideo(module: .swing) { [weak self] result in
            DispatchQueue.main.async {
                guard let self else { return }

                switch result {
                case .success(let response):
                    guard
                        let urlString = response.url,
                        let url = URL(string: urlString)
                    else {
                        self.showLessonUnavailable()
                        return
                    }
                    self.present(
                        VideoPlayerViewController(url: url, onFinished: {}),
                        animated: false
                    )
                case .failure:
                    self.showLessonUnavailable()
                }
            }
        }
    }

    private func showLessonUnavailable() {
        let alert = UIAlertController(
            title: "Lesson coming shortly",
            message: "The lesson video is on its way. Try Swing Correct in the meantime.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    @objc private func sendTapped() {
        // Was the system share sheet, which left the golfer to address and send
        // it themselves. This collects the friend's address and our own backend
        // sends the invite.
        present(ContactSheetViewController(mode: .shareWithFriend), animated: true)
    }

    @objc private func connectTapped() {
        present(ContactSheetViewController(mode: .connectWithFounder), animated: true)
    }

    @objc private func accountTapped() {
        if AuthManager.shared.isSignedIn {
            showAccountMenu()
        } else {
            let loginVC = LoginViewController()
            loginVC.modalPresentationStyle = .fullScreen
            present(loginVC, animated: true)
        }
    }

    @objc private func authStateChanged() {
        updateAccountButton()
        updateGreeting()
    }

    private func updateAccountButton() {
        if let email = AuthManager.shared.email, AuthManager.shared.isSignedIn {
            accountButton.setTitle("  \(email)", for: .normal)
            accountButton.setTitleColor(.white, for: .normal)
            let config = UIImage.SymbolConfiguration(pointSize: 13, weight: .medium)
            accountButton.setImage(UIImage(systemName: "person.crop.circle.fill", withConfiguration: config), for: .normal)
            accountButton.tintColor = Theme.green
        } else {
            accountButton.setTitle("  Sign In", for: .normal)
            accountButton.setTitleColor(Theme.green, for: .normal)
            let config = UIImage.SymbolConfiguration(pointSize: 13, weight: .medium)
            accountButton.setImage(UIImage(systemName: "person.crop.circle", withConfiguration: config), for: .normal)
            accountButton.tintColor = Theme.green
        }
    }

    private func showAccountMenu() {
        let sheet = UIAlertController(title: AuthManager.shared.email, message: nil, preferredStyle: .actionSheet)
        sheet.addAction(UIAlertAction(title: "Sign Out", style: .destructive) { _ in
            APIClient.shared.signOut { _ in }
            AuthManager.shared.signOut()
        })
        sheet.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        present(sheet, animated: true)
    }

    func mailComposeController(_ controller: MFMailComposeViewController, didFinishWith result: MFMailComposeResult, error: Error?) {
        controller.dismiss(animated: true)
    }
}

private final class GradientButton: UIView {
    private let gradientLayer = CAGradientLayer()
    let label = UILabel()

    init(title: String) {
        super.init(frame: .zero)
        translatesAutoresizingMaskIntoConstraints = false
        layer.cornerRadius = Theme.ctaRadius
        layer.borderWidth = 1
        layer.borderColor = UIColor(red: 0.38, green: 0.55, blue: 0.12, alpha: 1.0).cgColor
        clipsToBounds = true
        isUserInteractionEnabled = false

        gradientLayer.colors = [
            UIColor(red: 0.56, green: 0.76, blue: 0.22, alpha: 1.0).cgColor,
            UIColor(red: 0.42, green: 0.62, blue: 0.14, alpha: 1.0).cgColor,
        ]
        gradientLayer.startPoint = CGPoint(x: 0.5, y: 0)
        gradientLayer.endPoint = CGPoint(x: 0.5, y: 1)
        layer.insertSublayer(gradientLayer, at: 0)

        label.text = title
        label.font = .systemFont(ofSize: 8.5, weight: .heavy)
        label.textColor = .black
        label.textAlignment = .center
        label.adjustsFontSizeToFitWidth = true
        label.minimumScaleFactor = 0.7
        label.translatesAutoresizingMaskIntoConstraints = false
        addSubview(label)
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 4),
            label.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -4),
            label.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        gradientLayer.frame = bounds
    }
}
