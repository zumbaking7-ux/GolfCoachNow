import Foundation

enum GolfModule: String, CaseIterable {
    case swing
    case putt
    case shortGame = "short_game"

    var title: String {
        switch self {
        case .swing: return "Swing"
        case .putt: return "Putt"
        case .shortGame: return "Short Game"
        }
    }

    var subtitle: String {
        switch self {
        case .swing: return "Full swing analysis with 20 fault corrections"
        case .putt: return "Putting stroke analysis and speed control"
        case .shortGame: return "Chipping, pitching, and around-the-green shots"
        }
    }

    var iconName: String {
        switch self {
        case .swing: return "figure.golf"
        case .putt: return "target"
        case .shortGame: return "flag.fill"
        }
    }

    var cardIconAsset: String {
        switch self {
        case .swing: return "icon_swing"
        case .putt: return "icon_putt"
        case .shortGame: return "icon_shortgame"
        }
    }

    var cardDescription: String {
        switch self {
        case .swing: return "Analyze your swing. Get instant feedback."
        case .putt: return "Analyze your putting. Improve your stroke."
        case .shortGame: return "Chipping, pitching & bunker play."
        }
    }

    var apiEndpoint: String {
        switch self {
        case .swing: return "/wedge"
        case .putt: return "/putt"
        case .shortGame: return "/short-game"
        }
    }

    var uploadModuleParam: String {
        return rawValue
    }

    var faults: [String] {
        switch self {
        case .swing:
            return [
                "open_clubface", "closed_clubface", "weak_grip", "strong_grip",
                "over_the_top", "under_plane", "early_extension", "casting",
                "chicken_wing", "reverse_pivot", "sway", "slide",
                "spine_angle_loss", "tempo_imbalance", "poor_alignment",
                "ball_position_error", "grip_pressure", "hip_stall",
                "flat_shoulder_turn", "steep_shoulder_turn"
            ]
        case .putt:
            return [
                "poor_alignment", "deceleration", "wrist_breakdown",
                "poor_speed_control", "head_movement", "open_face_at_impact",
                "closed_face_at_impact", "poor_aim", "inconsistent_strike",
                "too_wristy", "backstroke_too_long", "poor_green_read",
                "stance_too_wide", "stance_too_narrow", "ball_position_error",
                "grip_pressure_too_tight", "poor_distance_control",
                "pushing_putts", "pulling_putts", "yips"
            ]
        case .shortGame:
            return [
                "flipping", "scooping", "poor_ball_position",
                "no_weight_forward", "too_much_wrist", "decelerating",
                "poor_club_selection", "fat_contact", "thin_contact",
                "poor_distance_control", "open_clubface", "closed_clubface",
                "poor_trajectory", "no_bounce_use", "steep_attack",
                "shallow_attack", "poor_landing_spot", "poor_setup",
                "no_follow_through", "tension"
            ]
        }
    }
}
