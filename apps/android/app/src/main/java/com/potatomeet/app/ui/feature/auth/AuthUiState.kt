package com.potatomeet.app.ui.feature.auth

data class AuthUiState(
    val checkingSession: Boolean = true,
    val isLoggedIn: Boolean = false,
    val accountId: String = "",
    val email: String = "",
    val nickname: String = "",
    val loginLoading: Boolean = false,
    val registerLoading: Boolean = false,
    val errorMessage: String? = null,
)
