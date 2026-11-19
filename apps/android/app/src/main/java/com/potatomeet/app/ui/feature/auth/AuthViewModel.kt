package com.potatomeet.app.ui.feature.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.potatomeet.app.domain.usecase.LoginUseCase
import com.potatomeet.app.domain.usecase.LogoutUseCase
import com.potatomeet.app.domain.usecase.RegisterUseCase
import com.potatomeet.app.domain.usecase.RestoreSessionUseCase
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
    private val loginUseCase: LoginUseCase,
    private val registerUseCase: RegisterUseCase,
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
            loginUseCase(email, password)
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
                    _events.tryEmit(AuthEvent.Toast("${session.nickname}님 환영합니다!"))
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
            registerUseCase(nickname, email, password, passwordConfirm)
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
                    _events.tryEmit(AuthEvent.Toast("회원가입이 완료되었습니다!"))
                }
                .onFailure { e ->
                    val msg = e.message ?: "회원가입에 실패했습니다."
                    _uiState.update { it.copy(registerLoading = false, errorMessage = msg) }
                    _events.tryEmit(AuthEvent.Toast(msg))
                }
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
