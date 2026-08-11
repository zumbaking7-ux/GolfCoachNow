import Foundation

struct CheckoutResponse: Decodable {
    let checkoutUrl: String
    let sessionId: String
}

struct UnlockStatusResponse: Decodable {
    let deviceId: String
    let unlocked: Bool
    let unlockedAt: String?
}

struct EntitlementResponse: Decodable {
    let allowed: Bool
    let isSubscriber: Bool
    let repsUsed: Int
    let repsRemaining: Int
    let dailyLimit: Int
}

struct TalkResponse: Decodable {
    let fault: String?
    let correction: String
    let module: String
    let matched: Bool
}
