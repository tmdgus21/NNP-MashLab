package com.potatomeet.app.domain.usecase

import com.potatomeet.app.data.remote.dto.AuthChallengeResponse
import com.potatomeet.app.data.remote.dto.AuthTokenResponse
import com.potatomeet.app.data.remote.dto.MeResponse
import com.potatomeet.app.data.repository.AuthRepository
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException

class AuthUseCasesTest {
    @Test
    fun deleteAccount_rejectsBlankPassword() =
        runBlocking {
            val result = DeleteAccountUseCase(FakeAuthRepository()).invoke("  ")
            assertTrue(result.isFailure)
            assertEquals("비밀번호를 입력해 주세요.", result.exceptionOrNull()?.message)
        }

    @Test
    fun startLogin_rejectsBlankEmail() =
        runBlocking {
            val result = StartLoginUseCase(FakeAuthRepository()).invoke("  ", "password123456")
            assertTrue(result.isFailure)
            assertEquals("이메일을 입력해 주세요.", result.exceptionOrNull()?.message)
        }

    @Test
    fun startLogin_rejectsInvalidEmail() =
        runBlocking {
            val result = StartLoginUseCase(FakeAuthRepository()).invoke("not-an-email", "password123456")
            assertTrue(result.isFailure)
            assertEquals("유효한 이메일을 입력해 주세요.", result.exceptionOrNull()?.message)
        }

    @Test
    fun startLogin_mapsNetworkError() =
        runBlocking {
            val repo = FakeAuthRepository(loginError = IOException("offline"))
            val result = StartLoginUseCase(repo).invoke("a@b.com", "password123456")
            assertTrue(result.isFailure)
            assertEquals(
                "네트워크에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
                result.exceptionOrNull()?.message,
            )
        }

    @Test
    fun startLogin_successReturnsChallenge() =
        runBlocking {
            val result = StartLoginUseCase(FakeAuthRepository()).invoke("a@b.com", "password123456")
            assertTrue(result.isSuccess)
            assertEquals("chal-login", result.getOrNull()?.challenge)
        }

    @Test
    fun verifyLogin_successUsesStoredNickname() =
        runBlocking {
            val repo =
                FakeAuthRepository(
                    loginVerifyResponse =
                        AuthTokenResponse(
                            accountId = "acc-1",
                            email = "a@b.com",
                            token = "tok",
                        ),
                    nickname = "감자",
                )
            val result = VerifyLoginUseCase(repo).invoke("chal", "123456", "a@b.com")
            assertTrue(result.isSuccess)
            assertEquals("감자", result.getOrNull()?.nickname)
            assertEquals("acc-1", result.getOrNull()?.accountId)
        }

    @Test
    fun startRegister_requiresPasswordLength12() =
        runBlocking {
            val result =
                StartRegisterUseCase(FakeAuthRepository()).invoke(
                    email = "a@b.com",
                    password = "short",
                    passwordConfirm = "short",
                )
            assertTrue(result.isFailure)
            assertEquals("비밀번호는 12자 이상이어야 합니다.", result.exceptionOrNull()?.message)
        }

    @Test
    fun startRegister_requiresPasswordMatch() =
        runBlocking {
            val result =
                StartRegisterUseCase(FakeAuthRepository()).invoke(
                    email = "a@b.com",
                    password = "password123456",
                    passwordConfirm = "password654321",
                )
            assertTrue(result.isFailure)
            assertEquals("비밀번호가 일치하지 않습니다.", result.exceptionOrNull()?.message)
        }

    @Test
    fun startRegister_mapsConflictDetail() =
        runBlocking {
            val body =
                """{"detail":"already"}""".toResponseBody("application/json".toMediaType())
            val repo = FakeAuthRepository(registerError = HttpException(Response.error<Unit>(409, body)))
            val result =
                StartRegisterUseCase(repo).invoke(
                    email = "a@b.com",
                    password = "password123456",
                    passwordConfirm = "password123456",
                )
            assertTrue(result.isFailure)
            assertEquals("already", result.exceptionOrNull()?.message)
        }

    @Test
    fun verifyRegister_success() =
        runBlocking {
            val result =
                VerifyRegisterUseCase(FakeAuthRepository()).invoke(
                    challenge = "chal",
                    code = "123456",
                )
            assertTrue(result.isSuccess)
            assertEquals("행복한감자100", result.getOrNull()?.nickname)
            assertEquals("a@b.com", result.getOrNull()?.email)
        }

    @Test
    fun restoreSession_returnsNullWhenNoToken() =
        runBlocking {
            val result = RestoreSessionUseCase(FakeAuthRepository(hasSessionFlag = false)).invoke()
            assertTrue(result.isSuccess)
            assertNull(result.getOrNull())
        }

    @Test
    fun restoreSession_clearsOnMeFailure() =
        runBlocking {
            val repo = FakeAuthRepository(hasSessionFlag = true, meError = IOException("gone"))
            val result = RestoreSessionUseCase(repo).invoke()
            assertTrue(result.isSuccess)
            assertNull(result.getOrNull())
            assertTrue(repo.logoutCalled)
        }

    @Test
    fun logout_delegates() =
        runBlocking {
            val repo = FakeAuthRepository(hasSessionFlag = true)
            LogoutUseCase(repo).invoke()
            assertTrue(repo.logoutCalled)
        }
}

private class FakeAuthRepository(
    private val loginChallenge: AuthChallengeResponse? = null,
    private val registerChallenge: AuthChallengeResponse? = null,
    private val loginVerifyResponse: AuthTokenResponse? = null,
    private val registerVerifyResponse: AuthTokenResponse? = null,
    private val meResponse: MeResponse? = null,
    private val nickname: String? = null,
    private var hasSessionFlag: Boolean = false,
    private val loginError: Throwable? = null,
    private val registerError: Throwable? = null,
    private val meError: Throwable? = null,
) : AuthRepository {
    var logoutCalled = false

    override suspend fun startLogin(
        email: String,
        password: String,
    ): AuthChallengeResponse {
        loginError?.let { throw it }
        return loginChallenge
            ?: AuthChallengeResponse(
                challenge = "chal-login",
                expiresIn = 300,
                resendAfter = 60,
                purpose = "LOGIN",
            )
    }

    override suspend fun resendLogin(challenge: String): AuthChallengeResponse =
        AuthChallengeResponse(challenge = "chal-login-2", expiresIn = 300, resendAfter = 60, purpose = "LOGIN")

    override suspend fun verifyLogin(
        challenge: String,
        code: String,
    ): AuthTokenResponse =
        loginVerifyResponse
            ?: AuthTokenResponse(accountId = "id", email = "a@b.com", token = "t")

    override suspend fun startRegister(
        email: String,
        password: String,
    ): AuthChallengeResponse {
        registerError?.let { throw it }
        return registerChallenge
            ?: AuthChallengeResponse(
                challenge = "chal-reg",
                expiresIn = 300,
                resendAfter = 60,
                purpose = "REGISTER",
            )
    }

    override suspend fun resendRegister(challenge: String): AuthChallengeResponse =
        AuthChallengeResponse(challenge = "chal-reg-2", expiresIn = 300, resendAfter = 60, purpose = "REGISTER")

    override suspend fun verifyRegister(
        challenge: String,
        code: String,
    ): AuthTokenResponse =
        registerVerifyResponse
            ?: AuthTokenResponse(
                accountId = "id",
                email = "a@b.com",
                token = "t",
                nickname = "행복한감자100",
            )

    override suspend fun me(): MeResponse {
        meError?.let { throw it }
        return meResponse
            ?: MeResponse(
                accountId = "id",
                email = "a@b.com",
                accountType = "user",
                nickname = nickname ?: "행복한감자100",
            )
    }

    override suspend fun updateNickname(nickname: String): MeResponse =
        MeResponse(
            accountId = "id",
            email = "a@b.com",
            accountType = "user",
            nickname = nickname,
        )

    override suspend fun logout() {
        logoutCalled = true
        hasSessionFlag = false
    }

    override suspend fun deleteAccount(password: String) {
        if (password.isBlank()) throw IllegalStateException("blank")
        hasSessionFlag = false
    }

    override suspend fun hasSession(): Boolean = hasSessionFlag

    override suspend fun displayNickname(): String? = nickname
}
