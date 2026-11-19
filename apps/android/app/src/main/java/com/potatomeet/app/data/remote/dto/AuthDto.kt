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
data class AuthTokenResponse(
    val accountId: String,
    val email: String,
    val token: String,
)

@Serializable
data class MeResponse(
    val accountId: String,
    val email: String,
    val accountType: String,
)
