package com.potatomeet.app.ui.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.potatomeet.app.domain.usecase.LogoutUseCase
import com.potatomeet.app.domain.usecase.ResendLoginOtpUseCase
import com.potatomeet.app.domain.usecase.ResendRegisterOtpUseCase
import com.potatomeet.app.domain.usecase.RestoreSessionUseCase
import com.potatomeet.app.domain.usecase.StartLoginUseCase
import com.potatomeet.app.domain.usecase.StartRegisterUseCase
import com.potatomeet.app.domain.usecase.UpdateNicknameUseCase
import com.potatomeet.app.domain.usecase.VerifyLoginUseCase
import com.potatomeet.app.domain.usecase.VerifyRegisterUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface AuthEvent {
    data class Toast(val message: String) : AuthEvent
}

@HiltViewModel
class AuthViewModel
    @Inject
    constructor(
        private val startLoginUseCase: StartLoginUseCase,
        private val verifyLoginUseCase: VerifyLoginUseCase,
        private val resendLoginOtpUseCase: ResendLoginOtpUseCase,
        private val startRegisterUseCase: StartRegisterUseCase,
        private val verifyRegisterUseCase: VerifyRegisterUseCase,
        private val resendRegisterOtpUseCase: ResendRegisterOtpUseCase,
        private val restoreSessionUseCase: RestoreSessionUseCase,
        private val updateNicknameUseCase: UpdateNicknameUseCase,
        private val logoutUseCase: LogoutUseCase,
    ) : ViewModel() {
        private val _uiState = MutableStateFlow(AuthUiState())
        val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

        private val _events = MutableSharedFlow<AuthEvent>(extraBufferCapacity = 1)
        val events: SharedFlow<AuthEvent> = _events.asSharedFlow()

        init {
            restoreSession()
        }

        fun restoreSession() {
            viewModelScope.launch {
                _uiState.update { it.copy(checkingSession = true, errorMessage = null) }
                restoreSessionUseCase()
                    .onSuccess { session ->
                        if (session == null) {
                            _uiState.update {
                                AuthUiState(checkingSession = false, isLoggedIn = false)
                            }
                        } else {
                            _uiState.update {
                                AuthUiState(
                                    checkingSession = false,
                                    isLoggedIn = true,
                                    accountId = session.accountId,
                                    email = session.email,
                                    nickname = session.nickname,
                                )
                            }
                        }
                    }
                    .onFailure {
                        _uiState.update {
                            AuthUiState(checkingSession = false, isLoggedIn = false)
                        }
                    }
            }
        }

        fun login(
            email: String,
            password: String,
        ) {
            viewModelScope.launch {
                _uiState.update { it.copy(loginLoading = true, errorMessage = null) }
                startLoginUseCase(email, password)
                    .onSuccess { challenge ->
                        _uiState.update {
                            it.copy(
                                loginLoading = false,
                                otpPurpose = "LOGIN",
                                pendingChallenge = challenge.challenge,
                                pendingEmail = email.trim(),
                                resendAfterSec = challenge.resendAfter,
                            )
                        }
                        _events.tryEmit(AuthEvent.Toast("인증코드를 이메일로 보냈습니다."))
                    }
                    .onFailure { e ->
                        val msg = e.message ?: "로그인에 실패했습니다."
                        _uiState.update { it.copy(loginLoading = false, errorMessage = msg) }
                        _events.tryEmit(AuthEvent.Toast(msg))
                    }
            }
        }

        fun register(
            email: String,
            password: String,
            passwordConfirm: String,
        ) {
            viewModelScope.launch {
                _uiState.update { it.copy(registerLoading = true, errorMessage = null) }
                startRegisterUseCase(email, password, passwordConfirm)
                    .onSuccess { challenge ->
                        _uiState.update {
                            it.copy(
                                registerLoading = false,
                                otpPurpose = "REGISTER",
                                pendingChallenge = challenge.challenge,
                                pendingEmail = email.trim(),
                                resendAfterSec = challenge.resendAfter,
                            )
                        }
                        _events.tryEmit(AuthEvent.Toast("인증코드를 이메일로 보냈습니다."))
                    }
                    .onFailure { e ->
                        val msg = e.message ?: "회원가입에 실패했습니다."
                        _uiState.update { it.copy(registerLoading = false, errorMessage = msg) }
                        _events.tryEmit(AuthEvent.Toast(msg))
                    }
            }
        }

        fun verifyOtp(code: String) {
            val state = _uiState.value
            val challenge = state.pendingChallenge ?: return
            val purpose = state.otpPurpose ?: return
            viewModelScope.launch {
                val loadingUpdate =
                    if (purpose == "LOGIN") {
                        state.copy(loginLoading = true, errorMessage = null)
                    } else {
                        state.copy(registerLoading = true, errorMessage = null)
                    }
                _uiState.value = loadingUpdate
                val result =
                    if (purpose == "LOGIN") {
                        verifyLoginUseCase(challenge, code, state.pendingEmail.orEmpty())
                    } else {
                        verifyRegisterUseCase(challenge, code)
                    }
                result
                    .onSuccess { session ->
                        _uiState.update {
                            AuthUiState(
                                checkingSession = false,
                                isLoggedIn = true,
                                accountId = session.accountId,
                                email = session.email,
                                nickname = session.nickname,
                            )
                        }
                        val msg =
                            if (purpose == "LOGIN") {
                                "${session.nickname}님 환영합니다!"
                            } else {
                                "회원가입이 완료되었습니다!"
                            }
                        _events.tryEmit(AuthEvent.Toast(msg))
                    }
                    .onFailure { e ->
                        val msg = e.message ?: "인증에 실패했습니다."
                        _uiState.update {
                            it.copy(
                                loginLoading = false,
                                registerLoading = false,
                                errorMessage = msg,
                            )
                        }
                        _events.tryEmit(AuthEvent.Toast(msg))
                    }
            }
        }

        fun resendOtp() {
            val state = _uiState.value
            val challenge = state.pendingChallenge ?: return
            val purpose = state.otpPurpose ?: return
            viewModelScope.launch {
                val result =
                    if (purpose == "LOGIN") {
                        resendLoginOtpUseCase(challenge)
                    } else {
                        resendRegisterOtpUseCase(challenge)
                    }
                result
                    .onSuccess { next ->
                        _uiState.update {
                            it.copy(
                                pendingChallenge = next.challenge,
                                resendAfterSec = next.resendAfter,
                                errorMessage = null,
                            )
                        }
                        _events.tryEmit(AuthEvent.Toast("인증코드를 다시 보냈습니다."))
                    }
                    .onFailure { e ->
                        val msg = e.message ?: "재발송에 실패했습니다."
                        _uiState.update { it.copy(errorMessage = msg) }
                        _events.tryEmit(AuthEvent.Toast(msg))
                    }
            }
        }

        fun clearPendingOtp() {
            _uiState.update {
                it.copy(
                    otpPurpose = null,
                    pendingChallenge = null,
                    pendingEmail = null,
                )
            }
        }

        fun logout() {
            viewModelScope.launch {
                logoutUseCase()
                _uiState.update { AuthUiState(checkingSession = false, isLoggedIn = false) }
                _events.tryEmit(AuthEvent.Toast("로그아웃되었습니다."))
            }
        }

        fun updateNickname(nickname: String) {
            viewModelScope.launch {
                updateNicknameUseCase(nickname)
                    .onSuccess { session ->
                        _uiState.update {
                            it.copy(nickname = session.nickname, errorMessage = null)
                        }
                        _events.tryEmit(AuthEvent.Toast("닉네임을 저장했습니다."))
                    }.onFailure { e ->
                        val msg = e.message ?: "닉네임 변경에 실패했습니다."
                        _uiState.update { it.copy(errorMessage = msg) }
                        _events.tryEmit(AuthEvent.Toast(msg))
                    }
            }
        }

        fun clearError() {
            _uiState.update { it.copy(errorMessage = null) }
        }
    }
