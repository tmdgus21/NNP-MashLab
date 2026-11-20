package com.potatomeet.app.data.repository

import com.potatomeet.app.core.TokenStore
import com.potatomeet.app.data.remote.PotatoApi
import com.potatomeet.app.data.remote.dto.AuthChallengeRequest
import com.potatomeet.app.data.remote.dto.AuthChallengeResponse
import com.potatomeet.app.data.remote.dto.AuthTokenResponse
import com.potatomeet.app.data.remote.dto.AuthVerifyRequest
import com.potatomeet.app.data.remote.dto.LoginRequest
import com.potatomeet.app.data.remote.dto.MeResponse
import com.potatomeet.app.data.remote.dto.RegisterRequest
import javax.inject.Inject
import javax.inject.Singleton

interface AuthRepository {
    suspend fun startRegister(
        email: String,
        password: String,
    ): AuthChallengeResponse

    suspend fun resendRegister(challenge: String): AuthChallengeResponse

    suspend fun verifyRegister(
        challenge: String,
        code: String,
        nickname: String,
    ): AuthTokenResponse

    suspend fun startLogin(
        email: String,
        password: String,
    ): AuthChallengeResponse

    suspend fun resendLogin(challenge: String): AuthChallengeResponse

    suspend fun verifyLogin(
        challenge: String,
        code: String,
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
    override suspend fun startRegister(
        email: String,
        password: String,
    ): AuthChallengeResponse = api.register(RegisterRequest(email = email, password = password))

    override suspend fun resendRegister(challenge: String): AuthChallengeResponse =
        api.registerResend(AuthChallengeRequest(challenge = challenge))

    override suspend fun verifyRegister(
        challenge: String,
        code: String,
        nickname: String,
    ): AuthTokenResponse {
        val res = api.registerVerify(AuthVerifyRequest(challenge = challenge, code = code))
        tokenStore.save(token = res.token, email = res.email, nickname = nickname)
        return res
    }

    override suspend fun startLogin(
        email: String,
        password: String,
    ): AuthChallengeResponse = api.login(LoginRequest(email = email, password = password))

    override suspend fun resendLogin(challenge: String): AuthChallengeResponse =
        api.loginResend(AuthChallengeRequest(challenge = challenge))

    override suspend fun verifyLogin(
        challenge: String,
        code: String,
    ): AuthTokenResponse {
        val res = api.loginVerify(AuthVerifyRequest(challenge = challenge, code = code))
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
