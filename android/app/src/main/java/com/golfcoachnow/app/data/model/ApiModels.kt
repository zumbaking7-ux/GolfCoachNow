package com.golfcoachnow.app.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class CorrectionResponse(
    @SerialName("dominant_fault") val dominantFault: String = "",
    val correction: String = "",
    @SerialName("normalized_scores") val normalizedScores: Map<String, Double> = emptyMap(),
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
