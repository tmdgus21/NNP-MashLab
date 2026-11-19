package com.potatomeet.app.data.repository

import com.potatomeet.app.core.TokenStore
import com.potatomeet.app.data.remote.PotatoApi
import com.potatomeet.app.data.remote.dto.AuthTokenResponse
import com.potatomeet.app.data.remote.dto.LoginRequest
import com.potatomeet.app.data.remote.dto.MeResponse
import com.potatomeet.app.data.remote.dto.RegisterRequest
import javax.inject.Inject
import javax.inject.Singleton

interface AuthRepository {
    suspend fun register(
        email: String,
        password: String,
        nickname: String,
    ): AuthTokenResponse

    suspend fun login(
        email: String,
        password: String,
    ): AuthTokenResponse

    suspend fun me(): MeResponse

    suspend fun logout()

    suspend fun hasSession(): Boolean

    suspend fun displayNickname(): String?
}

@Singleton
class AuthRepositoryImpl
@Inject
constructor(
    private val api: PotatoApi,
    private val tokenStore: TokenStore,
) : AuthRepository {
    override suspend fun register(
        email: String,
        password: String,
        nickname: String,
    ): AuthTokenResponse {
        val res = api.register(RegisterRequest(email = email, password = password))
        tokenStore.save(token = res.token, email = res.email, nickname = nickname)
        return res
    }

    override suspend fun login(
        email: String,
        password: String,
    ): AuthTokenResponse {
        val res = api.login(LoginRequest(email = email, password = password))
        val nickname = tokenStore.nickname()?.takeIf { tokenStore.email() == res.email }
        tokenStore.save(token = res.token, email = res.email, nickname = nickname)
        return res
    }

    override suspend fun me(): MeResponse = api.me()

    override suspend fun logout() {
        runCatching { api.logout() }
        tokenStore.clear()
    }

    override suspend fun hasSession(): Boolean = !tokenStore.token().isNullOrBlank()

    override suspend fun displayNickname(): String? = tokenStore.nickname()
}
