import Foundation

enum SwingAnalyzer {

    static func analyze(module: GolfModule) -> [String: Double] {
        let faults = module.faults
        let count = Int.random(in: 2...5)
        let selected = faults.shuffled().prefix(count)
        var scores: [String: Double] = [:]
        for fault in selected {
            scores[fault] = Double.random(in: 0.1...1.0)
        }
        return scores
    }
}
