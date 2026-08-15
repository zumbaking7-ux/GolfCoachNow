package com.golfcoachnow.app.util

import android.annotation.SuppressLint
import android.content.Context
import android.provider.Settings
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import com.golfcoachnow.app.data.api.ApiClient
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "entitlement")
private val KEY_UNLOCKED = booleanPreferencesKey("is_unlocked")

object EntitlementManager {

    private val _isUnlocked = MutableStateFlow(false)
    val isUnlocked = _isUnlocked.asStateFlow()

    private var _deviceId: String = ""
    val deviceId: String get() = _deviceId

    @SuppressLint("HardwareIds")
    fun init(context: Context) {
        _deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
    }

    fun observeUnlocked(context: Context): Flow<Boolean> {
        return context.dataStore.data.map { prefs -> prefs[KEY_UNLOCKED] == true }
    }

    suspend fun loadFromDisk(context: Context) {
        val prefs = context.dataStore.data.first()
        _isUnlocked.value = prefs[KEY_UNLOCKED] == true
    }

    suspend fun markUnlocked(context: Context) {
        context.dataStore.edit { it[KEY_UNLOCKED] = true }
        _isUnlocked.value = true
    }

    suspend fun clearUnlock(context: Context) {
        context.dataStore.edit { it[KEY_UNLOCKED] = false }
        _isUnlocked.value = false
    }

    suspend fun checkRemoteStatus(context: Context) {
        val result = ApiClient.checkUnlockStatus(deviceId)
        result.onSuccess { response ->
            if (response.unlocked) {
                markUnlocked(context)
            } else {
                clearUnlock(context)
            }
        }
    }
}
