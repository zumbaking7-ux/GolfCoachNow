package com.golfcoachnow.app.data.api

import com.golfcoachnow.app.BuildConfig
import com.golfcoachnow.app.data.model.*
import com.golfcoachnow.app.util.AuthManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

object ApiClient {

    private val baseUrl = BuildConfig.API_BASE_URL

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .build()

    private val json = Json { ignoreUnknownKeys = true }

    suspend fun sendModuleData(
        scores: Map<String, Double>,
        module: GolfModule,
        deviceId: String,
    ): Result<CorrectionResponse> = withContext(Dispatchers.IO) {
        try {
            val payload = buildString {
                append("{\"data\":{")
                append(scores.entries.joinToString(",") { "\"${it.key}\":${it.value}" })
                append("},\"device_id\":\"$deviceId\"}")
            }

            val request = Request.Builder()
                .url("$baseUrl${module.apiEndpoint}")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()

            val response = client.newCall(request).execute()
            handleResponse<CorrectionResponse>(response)
        } catch (e: IOException) {
            Result.failure(e)
        }
    }

    suspend fun uploadVideo(
        file: File,
        module: GolfModule,
        deviceId: String,
    ): Result<CorrectionResponse> = withContext(Dispatchers.IO) {
        try {
            val body = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart(
                    "file",
                    file.name,
                    file.asRequestBody("video/mp4".toMediaType())
                )
                .build()

            val request = Request.Builder()
                .url("$baseUrl/upload?module=${module.uploadParam}&device_id=$deviceId")
                .post(body)
                .apply {
                    AuthManager.token?.let { addHeader("Authorization", "Bearer $it") }
                }
                .build()

            val response = client.newCall(request).execute()
            handleResponse<CorrectionResponse>(response)
        } catch (e: IOException) {
            Result.failure(e)
        }
    }

    suspend fun sendTalkRequest(
        text: String,
        module: GolfModule,
        deviceId: String,
    ): Result<TalkResponse> = withContext(Dispatchers.IO) {
        try {
            val payload = """{"text":"$text","module":"${module.uploadParam}","device_id":"$deviceId"}"""

            val request = Request.Builder()
                .url("$baseUrl/talk")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()

            val response = client.newCall(request).execute()
            handleResponse<TalkResponse>(response)
        } catch (e: IOException) {
            Result.failure(e)
        }
    }

    suspend fun createCheckoutSession(deviceId: String): Result<CheckoutResponse> =
        withContext(Dispatchers.IO) {
            try {
                val payload = """{"device_id":"$deviceId"}"""

                val request = Request.Builder()
                    .url("$baseUrl/payments/checkout-session")
                    .post(payload.toRequestBody("application/json".toMediaType()))
                    .build()

                val response = client.newCall(request).execute()
                handleResponse<CheckoutResponse>(response)
            } catch (e: IOException) {
                Result.failure(e)
            }
        }

    suspend fun checkUnlockStatus(deviceId: String): Result<UnlockStatusResponse> =
        withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url("$baseUrl/payments/unlock-status?device_id=$deviceId")
                    .get()
                    .build()

                val response = client.newCall(request).execute()
                handleResponse<UnlockStatusResponse>(response)
            } catch (e: IOException) {
                Result.failure(e)
            }
        }

    suspend fun getInstructionalVideo(module: GolfModule): Result<InstructionalVideoResponse> =
        withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url("$baseUrl/videos/instructional?module=${module.uploadParam}")
                    .get()
                    .build()

                val response = client.newCall(request).execute()
                handleResponse<InstructionalVideoResponse>(response)
            } catch (e: IOException) {
                Result.failure(e)
            }
        }

    suspend fun shareWithFriend(email: String, deviceId: String): Result<AcceptedResponse> =
        withContext(Dispatchers.IO) {
            try {
                val payload = json.encodeToString(ShareInviteRequest(email, deviceId))
                val request = Request.Builder()
                    .url("$baseUrl/share/invite")
                    .post(payload.toRequestBody("application/json".toMediaType()))
                    .build()
                handleResponse<AcceptedResponse>(client.newCall(request).execute())
            } catch (e: IOException) {
                Result.failure(e)
            }
        }

    suspend fun messageFounder(
        message: String,
        email: String?,
        deviceId: String,
    ): Result<AcceptedResponse> = withContext(Dispatchers.IO) {
        try {
            val payload = json.encodeToString(
                FounderMessageRequest(message, email?.takeIf { it.isNotBlank() }, deviceId)
            )
            val request = Request.Builder()
                .url("$baseUrl/connect/founder")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            handleResponse<AcceptedResponse>(client.newCall(request).execute())
        } catch (e: IOException) {
            Result.failure(e)
        }
    }

    suspend fun requestCode(email: String): Result<RequestCodeResponse> =
        withContext(Dispatchers.IO) {
            try {
                val payload = """{"email":"$email"}"""
                val request = Request.Builder()
                    .url("$baseUrl/auth/request-code")
                    .post(payload.toRequestBody("application/json".toMediaType()))
                    .build()
                val response = client.newCall(request).execute()
                handleResponse<RequestCodeResponse>(response)
            } catch (e: IOException) {
                Result.failure(e)
            }
        }

    suspend fun verifyCode(
        email: String,
        code: String,
        deviceId: String,
        name: String? = null,
    ): Result<VerifyCodeResponse> = withContext(Dispatchers.IO) {
        try {
            val payload = json.encodeToString(
                VerifyCodeRequest(email, code, deviceId, name?.takeIf { it.isNotBlank() })
            )
            val request = Request.Builder()
                .url("$baseUrl/auth/verify-code")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            val response = client.newCall(request).execute()
            handleResponse<VerifyCodeResponse>(response)
        } catch (e: IOException) {
            Result.failure(e)
        }
    }

    suspend fun setName(name: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val payload = json.encodeToString(SetNameRequest(name))
            val request = Request.Builder()
                .url("$baseUrl/auth/name")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .apply {
                    AuthManager.token?.let { addHeader("Authorization", "Bearer $it") }
                }
                .build()
            val response = client.newCall(request).execute()
            response.use {
                if (it.isSuccessful) Result.success(Unit)
                else Result.failure(ApiException(it.code, "Could not save that name"))
            }
        } catch (e: IOException) {
            Result.failure(e)
        }
    }

    suspend fun signOut(token: String): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$baseUrl/auth/sign-out")
                .post("".toRequestBody())
                .addHeader("Authorization", "Bearer $token")
                .build()
            client.newCall(request).execute().close()
            Result.success(Unit)
        } catch (e: IOException) {
            Result.failure(e)
        }
    }

    fun trackEvent(name: String, module: GolfModule? = null) {
        val payload = buildString {
            append("{\"device_id\":\"${com.golfcoachnow.app.util.EntitlementManager.deviceId}\"")
            append(",\"event_name\":\"$name\"")
            append(",\"platform\":\"android\"")
            if (module != null) append(",\"module\":\"${module.uploadParam}\"")
            append("}")
        }
        try {
            val request = Request.Builder()
                .url("$baseUrl/analytics/event")
                .post(payload.toRequestBody("application/json".toMediaType()))
                .build()
            client.newCall(request).enqueue(object : okhttp3.Callback {
                override fun onFailure(call: okhttp3.Call, e: IOException) {}
                override fun onResponse(call: okhttp3.Call, response: okhttp3.Response) {
                    response.close()
                }
            })
        } catch (_: Exception) {}
    }

    private inline fun <reified T> handleResponse(response: okhttp3.Response): Result<T> {
        val body = response.body?.string() ?: return Result.failure(IOException("Empty response"))

        if (!response.isSuccessful) {
            return Result.failure(ApiException(response.code, body))
        }

        return try {
            Result.success(json.decodeFromString<T>(body))
        } catch (e: Exception) {
            Result.failure(IOException("Failed to parse response"))
        }
    }
}

class ApiException(val code: Int, override val message: String) : IOException(message)
