import Foundation

struct CorrectionResponse: Decodable {
    let rep: Int
    let dominantFault: String
    let correction: String
    let normalizedScores: [String: Double]
    let status: String

    /// Nil until the clip for this fault is published. The written correction
    /// above is always present, so a missing video costs polish, not coaching.
    let correctionVideoUrl: String?
}

/// The clip that plays between tapping an engine and the camera opening.
///
/// A nil `url` is a real answer meaning nothing is published yet, not a
/// failure. The app is expected to go straight to the camera in that case.
struct InstructionalVideoResponse: Decodable {
    let module: String
    let url: String?
}
