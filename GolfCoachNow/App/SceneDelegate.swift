import UIKit

class SceneDelegate: UIResponder, UIWindowSceneDelegate {

    var window: UIWindow?

    func scene(
        _ scene: UIScene,
        willConnectTo session: UISceneSession,
        options connectionOptions: UIScene.ConnectionOptions
    ) {
        guard let windowScene = scene as? UIWindowScene else { return }
        let window = UIWindow(windowScene: windowScene)
        let nav = UINavigationController(rootViewController: HomeViewController())
        nav.setNavigationBarHidden(true, animated: false)
        window.rootViewController = nav
        window.makeKeyAndVisible()
        self.window = window

        EntitlementManager.shared.checkRemoteStatus()

        if let url = connectionOptions.urlContexts.first?.url {
            handleDeepLink(url)
        }
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        guard let url = URLContexts.first?.url else { return }
        handleDeepLink(url)
    }

    private func handleDeepLink(_ url: URL) {
        guard url.scheme == "golfcoachnow" else { return }

        switch url.host {
        case "payment-success":
            EntitlementManager.shared.markUnlocked()
            dismissPresentedThenShow(
                title: "Payment Successful",
                message: "Thank you! Your full access has been unlocked."
            )

        case "payment-cancelled":
            dismissPresentedThenShow(
                title: "Payment Cancelled",
                message: "Your payment was not completed. You can try again anytime."
            )

        default:
            break
        }
    }

    private func dismissPresentedThenShow(title: String, message: String) {
        guard let root = window?.rootViewController else { return }

        let show = {
            let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default))

            var presenter: UIViewController = root
            while let next = presenter.presentedViewController {
                presenter = next
            }
            presenter.present(alert, animated: true)
        }

        if root.presentedViewController != nil {
            root.dismiss(animated: false) { show() }
        } else {
            show()
        }
    }
}
