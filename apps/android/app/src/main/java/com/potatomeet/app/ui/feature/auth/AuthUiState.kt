package com.potatomeet.app.ui.feature.auth

data class AuthUiState(
    val checkingSession: Boolean = true,
    val isLoggedIn: Boolean = false,
    val accountId: String? = null,
    val email: String? = null,
    val nickname: String? = null,
    val loginLoading: Boolean = false,
    val registerLoading: Boolean = false,
    val otpPurpose: String? = null,
    val pendingChallenge: String? = null,
    val pendingEmail: String? = null,
    val resendAfterSec: Int = 60,
    val errorMessage: String? = null,
)
