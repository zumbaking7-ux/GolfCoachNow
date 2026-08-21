import UIKit

enum Theme {
    static let background = UIColor.black
    static let cardBackground = UIColor(red: 0.055, green: 0.055, blue: 0.055, alpha: 1.0)
    static let green = UIColor(red: 0.68, green: 0.79, blue: 0.20, alpha: 1.0)
    static let greenDark = UIColor(red: 0.56, green: 0.66, blue: 0.15, alpha: 1.0)
    static let greenBorder = UIColor(red: 0.56, green: 0.66, blue: 0.15, alpha: 0.5)
    static let greenGlow = UIColor(red: 0.68, green: 0.79, blue: 0.20, alpha: 0.4)
    static let greenDim = UIColor(red: 0.68, green: 0.79, blue: 0.20, alpha: 0.12)
    static let greetingBackground = UIColor(red: 0.055, green: 0.055, blue: 0.055, alpha: 1.0)
    static let textPrimary = UIColor.white
    static let textMuted = UIColor(white: 0.6, alpha: 1.0)
    static let textDark = UIColor(red: 0.07, green: 0.07, blue: 0.07, alpha: 1.0)

    static let screenPadding: CGFloat = 16
    static let cardGap: CGFloat = 8
    static let cardPadding: CGFloat = 14
    static let cardRadius: CGFloat = 14
    static let iconBoxSize: CGFloat = 48
    static let iconBoxRadius: CGFloat = 12
    static let ctaRadius: CGFloat = 8
    static let greetingOverlap: CGFloat = -24

    static func timeGreeting() -> String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 5..<12: return "Good morning,"
        case 12..<17: return "Good afternoon,"
        default: return "Good evening,"
        }
    }
}
