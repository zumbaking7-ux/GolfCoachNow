import Foundation
import Security

final class AuthManager {

    static let shared = AuthManager()

    private let tokenAccount = "gcn_auth_token"
    private let emailKey = "gcn_auth_email"
    private let nameKey = "gcn_auth_name"
    private let service = "com.golfcoachnow.auth"

    var isSignedIn: Bool { token != nil }

    var email: String? {
        get { UserDefaults.standard.string(forKey: emailKey) }
        set {
            if let newValue {
                UserDefaults.standard.set(newValue, forKey: emailKey)
            } else {
                UserDefaults.standard.removeObject(forKey: emailKey)
            }
        }
    }

    /// What to call this person on the home screen.
    ///
    /// Comes from the account rather than the email address. Deriving it from
    /// the address greeted waleflutter@gmail.com as "Waleflutter".
    var name: String? {
        get { UserDefaults.standard.string(forKey: nameKey) }
        set {
            let cleaned = newValue?.trimmingCharacters(in: .whitespacesAndNewlines)
            if let cleaned, !cleaned.isEmpty {
                UserDefaults.standard.set(cleaned, forKey: nameKey)
            } else {
                UserDefaults.standard.removeObject(forKey: nameKey)
            }
        }
    }

    var token: String? {
        get { readKeychain() }
        set {
            if let newValue {
                saveKeychain(newValue)
            } else {
                deleteKeychain()
            }
        }
    }

    func signOut() {
        token = nil
        email = nil
        name = nil
        NotificationCenter.default.post(name: .authStateDidChange, object: nil)
    }

    // MARK: - Keychain

    private func saveKeychain(_ value: String) {
        deleteKeychain()
        let data = Data(value.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: tokenAccount,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        SecItemAdd(query as CFDictionary, nil)
    }

    private func readKeychain() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: tokenAccount,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    private func deleteKeychain() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: tokenAccount,
        ]
        SecItemDelete(query as CFDictionary)
    }
}

extension Notification.Name {
    static let authStateDidChange = Notification.Name("gcn_authStateDidChange")
}
