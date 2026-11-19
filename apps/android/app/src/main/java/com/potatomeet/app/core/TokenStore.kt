package com.potatomeet.app.core

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore("potato_session")

@Singleton
class TokenStore
@Inject
constructor(
    @ApplicationContext private val context: Context,
) {
    private val tokenKey = stringPreferencesKey("bearer_token")
    private val emailKey = stringPreferencesKey("email")
    private val nicknameKey = stringPreferencesKey("nickname")

    val tokenFlow: Flow<String?> =
        context.dataStore.data.map { prefs -> prefs[tokenKey] }

    suspend fun token(): String? = tokenFlow.first()

    suspend fun email(): String? =
        context.dataStore.data.map { it[emailKey] }.first()

    suspend fun nickname(): String? =
        context.dataStore.data.map { it[nicknameKey] }.first()

    suspend fun save(
        token: String,
        email: String,
        nickname: String? = null,
    ) {
        context.dataStore.edit { prefs ->
            prefs[tokenKey] = token
            prefs[emailKey] = email
            if (nickname.isNullOrBlank()) {
                prefs.remove(nicknameKey)
            } else {
                prefs[nicknameKey] = nickname
            }
        }
    }

    suspend fun saveNickname(nickname: String) {
        context.dataStore.edit { it[nicknameKey] = nickname }
    }

    suspend fun clear() {
        context.dataStore.edit { it.clear() }
    }
}
