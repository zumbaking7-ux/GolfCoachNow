package com.golfcoachnow.app.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CorrectionResponse(
    @SerialName("dominant_fault") val dominantFault: String = "",
    val correction: String = "",
    @SerialName("normalized_scores") val normalizedScores: Map<String, Double> = emptyMap(),
    // Null until the asset for this fault is published. The written correction
    // above is always present, so a missing clip costs polish, not coaching.
    @SerialName("correction_video_url") val correctionVideoUrl: String? = null,
)

@Serializable
data class InstructionalVideoResponse(
    val module: String = "",
    val url: String? = null,
)

// Built as objects and serialised properly rather than interpolated into a
// string. The founder message is free-form text a person types, so a quote or a
// newline in it would otherwise produce malformed JSON and a confusing 422.
@Serializable
data class ShareInviteRequest(
    val email: String,
    @SerialName("device_id") val deviceId: String,
)

@Serializable
data class FounderMessageRequest(
    val message: String,
    val email: String? = null,
    @SerialName("device_id") val deviceId: String,
)

@Serializable
data class AcceptedResponse(
    val status: String = "",
)

@Serializable
data class TalkResponse(
    val fault: String? = null,
    val correction: String = "",
    val module: String = "",
    val matched: Boolean = false,
)

@Serializable
data class CheckoutResponse(
    @SerialName("checkout_url") val checkoutUrl: String = "",
    @SerialName("session_id") val sessionId: String = "",
)

@Serializable
data class UnlockStatusResponse(
    @SerialName("device_id") val deviceId: String = "",
    val unlocked: Boolean = false,
    @SerialName("unlocked_at") val unlockedAt: String? = null,
)

@Serializable
data class EntitlementResponse(
    val allowed: Boolean = true,
    @SerialName("is_subscriber") val isSubscriber: Boolean = false,
    @SerialName("reps_used") val repsUsed: Int = 0,
    @SerialName("reps_remaining") val repsRemaining: Int = -1,
    @SerialName("daily_limit") val dailyLimit: Int = -1,
)

@Serializable
data class VerifyCodeResponse(
    val token: String = "",
)

@Serializable
data class RequestCodeResponse(
    val status: String = "",
)
