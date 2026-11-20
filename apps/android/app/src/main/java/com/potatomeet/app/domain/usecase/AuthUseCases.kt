package com.potatomeet.app.domain.usecase

import com.potatomeet.app.core.ApiError
import com.potatomeet.app.data.remote.dto.AuthChallengeResponse
import com.potatomeet.app.data.repository.AuthRepository
import javax.inject.Inject

data class AuthSession(
    val accountId: String,
    val email: String,
    val nickname: String,
)

data class AuthChallenge(
    val challenge: String,
    val expiresIn: Int,
    val resendAfter: Int,
    val purpose: String,
)

private fun AuthChallengeResponse.toDomain(): AuthChallenge =
    AuthChallenge(
        challenge = challenge,
        expiresIn = expiresIn,
        resendAfter = resendAfter,
        purpose = purpose ?: "",
    )

class StartLoginUseCase
@Inject
constructor(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke(
        email: String,
        password: String,
    ): Result<AuthChallenge> {
        val trimmed = email.trim()
        if (trimmed.isBlank()) return Result.failure(IllegalStateException("이메일을 입력해 주세요."))
        if (password.isBlank()) return Result.failure(IllegalStateException("비밀번호를 입력해 주세요."))
        if ('@' !in trimmed) return Result.failure(IllegalStateException("유효한 이메일을 입력해 주세요."))
        return runCatching { authRepository.startLogin(trimmed, password).toDomain() }.fold(
            onSuccess = { Result.success(it) },
            onFailure = { Result.failure(IllegalStateException(ApiError.messageOf(it))) },
        )
    }
}

class VerifyLoginUseCase
@Inject
constructor(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke(
        challenge: String,
        code: String,
        email: String,
    ): Result<AuthSession> {
        val trimmedCode = code.trim()
        if (trimmedCode.length != 6 || trimmedCode.any { !it.isDigit() }) {
            return Result.failure(IllegalStateException("인증코드 6자리를 입력해 주세요."))
        }
        return runCatching {
            val res = authRepository.verifyLogin(challenge, trimmedCode)
            val nickname = authRepository.displayNickname() ?: email.substringBefore('@')
            AuthSession(accountId = res.accountId, email = res.email, nickname = nickname)
        }.fold(
            onSuccess = { Result.success(it) },
            onFailure = { Result.failure(IllegalStateException(ApiError.messageOf(it))) },
        )
    }
}

class ResendLoginOtpUseCase
@Inject
constructor(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke(challenge: String): Result<AuthChallenge> =
        runCatching { authRepository.resendLogin(challenge).toDomain() }.fold(
            onSuccess = { Result.success(it) },
            onFailure = { Result.failure(IllegalStateException(ApiError.messageOf(it))) },
        )
}

class StartRegisterUseCase
@Inject
constructor(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke(
        nickname: String,
        email: String,
        password: String,
        passwordConfirm: String,
    ): Result<AuthChallenge> {
        val nick = nickname.trim()
        val trimmed = email.trim()
        if (nick.isBlank()) return Result.failure(IllegalStateException("닉네임을 입력해 주세요."))
        if (trimmed.isBlank()) return Result.failure(IllegalStateException("이메일을 입력해 주세요."))
        if ('@' !in trimmed) return Result.failure(IllegalStateException("유효한 이메일을 입력해 주세요."))
        if (password.isBlank()) return Result.failure(IllegalStateException("비밀번호를 입력해 주세요."))
        if (password.length < 12) {
            return Result.failure(IllegalStateException("비밀번호는 12자 이상이어야 합니다."))
        }
        if (password != passwordConfirm) {
            return Result.failure(IllegalStateException("비밀번호가 일치하지 않습니다."))
        }
        return runCatching { authRepository.startRegister(trimmed, password).toDomain() }.fold(
            onSuccess = { Result.success(it) },
            onFailure = { Result.failure(IllegalStateException(ApiError.messageOf(it))) },
        )
    }
}

class VerifyRegisterUseCase
@Inject
constructor(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke(
        challenge: String,
        code: String,
        nickname: String,
    ): Result<AuthSession> {
        val nick = nickname.trim()
        val trimmedCode = code.trim()
        if (trimmedCode.length != 6 || trimmedCode.any { !it.isDigit() }) {
            return Result.failure(IllegalStateException("인증코드 6자리를 입력해 주세요."))
        }
        return runCatching {
            val res = authRepository.verifyRegister(challenge, trimmedCode, nick)
            AuthSession(accountId = res.accountId, email = res.email, nickname = nick)
        }.fold(
            onSuccess = { Result.success(it) },
            onFailure = { Result.failure(IllegalStateException(ApiError.messageOf(it))) },
        )
    }
}

class ResendRegisterOtpUseCase
@Inject
constructor(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke(challenge: String): Result<AuthChallenge> =
        runCatching { authRepository.resendRegister(challenge).toDomain() }.fold(
            onSuccess = { Result.success(it) },
            onFailure = { Result.failure(IllegalStateException(ApiError.messageOf(it))) },
        )
}

class RestoreSessionUseCase
@Inject
constructor(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke(): Result<AuthSession?> =
        runCatching {
            if (!authRepository.hasSession()) return@runCatching null
            val me = authRepository.me()
            val nickname = authRepository.displayNickname() ?: me.email.substringBefore('@')
            AuthSession(accountId = me.accountId, email = me.email, nickname = nickname)
        }.fold(
            onSuccess = { Result.success(it) },
            onFailure = {
                authRepository.logout()
                Result.success(null)
            },
        )
}

class LogoutUseCase
@Inject
constructor(
    private val authRepository: AuthRepository,
) {
    suspend operator fun invoke() {
        authRepository.logout()
    }
}
