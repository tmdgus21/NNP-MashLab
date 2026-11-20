package com.potatomeet.app.ui.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.potatomeet.app.domain.usecase.LogoutUseCase
import com.potatomeet.app.domain.usecase.ResendLoginOtpUseCase
import com.potatomeet.app.domain.usecase.ResendRegisterOtpUseCase
import com.potatomeet.app.domain.usecase.RestoreSessionUseCase
import com.potatomeet.app.domain.usecase.StartLoginUseCase
import com.potatomeet.app.domain.usecase.StartRegisterUseCase
import com.potatomeet.app.domain.usecase.VerifyLoginUseCase
import com.potatomeet.app.domain.usecase.VerifyRegisterUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

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
        nickname: String,
        email: String,
        password: String,
        passwordConfirm: String,
    ) {
        viewModelScope.launch {
            _uiState.update { it.copy(registerLoading = true, errorMessage = null) }
            startRegisterUseCase(nickname, email, password, passwordConfirm)
                .onSuccess { challenge ->
                    _uiState.update {
                        it.copy(
                            registerLoading = false,
                            otpPurpose = "REGISTER",
                            pendingChallenge = challenge.challenge,
                            pendingEmail = email.trim(),
                            pendingNickname = nickname.trim(),
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
                    verifyRegisterUseCase(challenge, code, state.pendingNickname.orEmpty())
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
                pendingNickname = null,
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

    fun clearError() {
        _uiState.update { it.copy(errorMessage = null) }
    }
}
