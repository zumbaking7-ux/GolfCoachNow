package com.golfcoachnow.app.data.model

enum class GolfModule(
    val title: String,
    val subtitle: String,
    val cardDescription: String,
    val iconName: String,
    val apiEndpoint: String,
    val uploadParam: String,
) {
    SWING(
        title = "Swing",
        subtitle = "Full swing analysis",
        cardDescription = "Analyze your swing. Get instant feedback.",
        iconName = "sports_golf",
        apiEndpoint = "/wedge",
        uploadParam = "swing",
    ),
    PUTT(
        title = "Putt",
        subtitle = "Putting stroke analysis",
        cardDescription = "Analyze your putting. Improve your stroke.",
        iconName = "golf_course",
        apiEndpoint = "/putt",
        uploadParam = "putt",
    ),
    SHORT_GAME(
        title = "Short Game",
        subtitle = "Chip & pitch analysis",
        cardDescription = "Chipping, pitching & bunker play.",
        iconName = "landscape",
        apiEndpoint = "/short-game",
        uploadParam = "short_game",
    );

    val faults: List<String>
        get() = when (this) {
            SWING -> listOf(
                "open_clubface", "closed_clubface", "weak_grip", "strong_grip",
                "over_the_top", "under_plane", "early_extension", "casting",
                "chicken_wing", "reverse_pivot", "sway", "slide",
                "spine_angle_loss", "tempo_imbalance", "poor_alignment",
                "ball_position_error", "grip_pressure", "hip_stall",
                "flat_shoulder_turn", "steep_shoulder_turn"
            )
            PUTT -> listOf(
                "poor_alignment", "deceleration", "wrist_breakdown",
                "poor_speed_control", "head_movement", "open_face_at_impact",
                "closed_face_at_impact", "poor_aim", "inconsistent_strike",
                "too_wristy", "backstroke_too_long", "poor_green_read",
                "stance_too_wide", "stance_too_narrow", "ball_position_error",
                "grip_pressure_too_tight", "poor_distance_control",
                "pushing_putts", "pulling_putts", "yips"
            )
            SHORT_GAME -> listOf(
                "flipping", "scooping", "poor_ball_position",
                "no_weight_forward", "too_much_wrist", "decelerating",
                "poor_club_selection", "fat_contact", "thin_contact",
                "poor_distance_control", "open_clubface", "closed_clubface",
                "poor_trajectory", "no_bounce_use", "steep_attack",
                "shallow_attack", "poor_landing_spot", "poor_setup",
                "no_follow_through", "tension"
            )
        }
}
