import UIKit

final class EntitlementManager {

    static let shared = EntitlementManager()

    private let unlockedKey = "gcn_unlocked"

    var deviceId: String {
        UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
    }

    var isUnlocked: Bool {
        get { UserDefaults.standard.bool(forKey: unlockedKey) }
        set { UserDefaults.standard.set(newValue, forKey: unlockedKey) }
    }

    func checkRemoteStatus(completion: ((Bool) -> Void)? = nil) {
        APIClient.shared.checkUnlockStatus(deviceId: deviceId) { [weak self] result in
            switch result {
            case .success(let response):
                self?.isUnlocked = response.unlocked
                completion?(response.unlocked)
            case .failure:
                completion?(self?.isUnlocked ?? false)
            }
        }
    }

    func markUnlocked() {
        isUnlocked = true
        NotificationCenter.default.post(name: .entitlementDidChange, object: nil)
    }
}

extension Notification.Name {
    static let entitlementDidChange = Notification.Name("gcn_entitlementDidChange")
}
