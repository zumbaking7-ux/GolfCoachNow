package com.golfcoachnow.app.util

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.authStore by preferencesDataStore(name = "auth")
private val KEY_TOKEN = stringPreferencesKey("token")
private val KEY_EMAIL = stringPreferencesKey("email")

object AuthManager {

    private val _email = MutableStateFlow<String?>(null)
    val email = _email.asStateFlow()

    private var _token: String? = null
    val token: String? get() = _token

    val isSignedIn: Boolean get() = _token != null

    suspend fun load(context: Context) {
        val prefs = context.authStore.data.first()
        _token = prefs[KEY_TOKEN]
        _email.value = prefs[KEY_EMAIL]
    }

    suspend fun save(context: Context, token: String, email: String) {
        context.authStore.edit {
            it[KEY_TOKEN] = token
            it[KEY_EMAIL] = email
        }
        _token = token
        _email.value = email
    }

    suspend fun signOut(context: Context) {
        context.authStore.edit {
            it.remove(KEY_TOKEN)
            it.remove(KEY_EMAIL)
        }
        _token = null
        _email.value = null
    }
}
