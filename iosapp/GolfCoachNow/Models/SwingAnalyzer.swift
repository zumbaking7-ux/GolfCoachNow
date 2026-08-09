import Foundation

// Generates sample swing fault scores for demo purposes.
// Replace with real video analysis (Core ML, Vision, etc.) when available.
enum SwingAnalyzer {

    private static let faults = [
        "open_clubface", "closed_clubface", "weak_grip", "strong_grip",
        "over_the_top", "under_plane", "early_extension", "casting",
        "chicken_wing", "reverse_pivot", "sway", "slide",
        "spine_angle_loss", "tempo_imbalance", "poor_alignment",
        "ball_position_error", "grip_pressure", "hip_stall",
        "flat_shoulder_turn", "steep_shoulder_turn"
    ]

    static func analyze() -> [String: Double] {
        let count = Int.random(in: 2...5)
        let selected = faults.shuffled().prefix(count)
        var scores: [String: Double] = [:]
        for fault in selected {
            scores[fault] = Double.random(in: 0.1...1.0)
        }
        return scores
    }
}
