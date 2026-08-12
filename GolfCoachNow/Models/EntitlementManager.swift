import UIKit

final class EntitlementManager {

    static let shared = EntitlementManager()

    private let unlockedKey = "gcn_unlocked"
    private let deviceIdKey = "gcn_device_id"

    var deviceId: String {
        if let stored = UserDefaults.standard.string(forKey: deviceIdKey) {
            return stored
        }
        let id = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
        UserDefaults.standard.set(id, forKey: deviceIdKey)
        return id
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
