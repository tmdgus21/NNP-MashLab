package com.potatomeet.app.data.remote.dto

import kotlinx.serialization.Serializable

@Serializable
data class RegisterRequest(
    val email: String,
    val password: String,
)

@Serializable
data class LoginRequest(
    val email: String,
    val password: String,
)

@Serializable
data class AuthChallengeRequest(
    val challenge: String,
)

@Serializable
data class AuthVerifyRequest(
    val challenge: String,
    val code: String,
)

@Serializable
data class AuthChallengeResponse(
    val challenge: String,
    val expiresIn: Int,
    val resendAfter: Int,
    val purpose: String? = null,
)

@Serializable
data class AuthTokenResponse(
    val accountId: String,
    val email: String,
    val token: String,
    val nickname: String? = null,
)

@Serializable
data class MeResponse(
    val accountId: String,
    val email: String,
    val accountType: String,
    val nickname: String? = null,
)

@Serializable
data class NicknamePatchRequest(
    val nickname: String,
)

@Serializable
data class DeleteAccountRequest(
    val password: String,
)

@Serializable
data class DeleteAccountResponse(
    val deleted: Boolean = false,
)
