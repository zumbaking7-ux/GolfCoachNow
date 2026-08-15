import Foundation

struct CorrectionResponse: Decodable {
    let rep: Int
    let dominantFault: String
    let correction: String
    let normalizedScores: [String: Double]
    let status: String
}
