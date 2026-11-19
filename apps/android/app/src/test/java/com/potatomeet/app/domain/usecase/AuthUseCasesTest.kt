package com.potatomeet.app.domain.usecase

import com.potatomeet.app.data.remote.dto.AuthTokenResponse
import com.potatomeet.app.data.remote.dto.MeResponse
import com.potatomeet.app.data.repository.AuthRepository
import java.io.IOException
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

class AuthUseCasesTest {
    @Test
    fun login_rejectsBlankEmail() =
        runBlocking {
            val result = LoginUseCase(FakeAuthRepository()).invoke("  ", "password123456")
            assertTrue(result.isFailure)
            assertEquals("이메일을 입력해 주세요.", result.exceptionOrNull()?.message)
        }

    @Test
    fun login_rejectsInvalidEmail() =
        runBlocking {
            val result = LoginUseCase(FakeAuthRepository()).invoke("not-an-email", "password123456")
            assertTrue(result.isFailure)
            assertEquals("유효한 이메일을 입력해 주세요.", result.exceptionOrNull()?.message)
        }

    @Test
    fun login_mapsNetworkError() =
        runBlocking {
            val repo = FakeAuthRepository(loginError = IOException("offline"))
            val result = LoginUseCase(repo).invoke("a@b.com", "password123456")
            assertTrue(result.isFailure)
            assertEquals(
                "네트워크에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
                result.exceptionOrNull()?.message,
            )
        }

    @Test
    fun login_successUsesStoredNickname() =
        runBlocking {
            val repo =
                FakeAuthRepository(
                    loginResponse =
                        AuthTokenResponse(
                            accountId = "acc-1",
                            email = "a@b.com",
                            token = "tok",
                        ),
                    nickname = "감자",
                )
            val result = LoginUseCase(repo).invoke("a@b.com", "password123456")
            assertTrue(result.isSuccess)
            assertEquals("감자", result.getOrNull()?.nickname)
            assertEquals("acc-1", result.getOrNull()?.accountId)
        }

    @Test
    fun register_requiresPasswordLength12() =
        runBlocking {
            val result =
                RegisterUseCase(FakeAuthRepository()).invoke(
                    nickname = "감자",
                    email = "a@b.com",
                    password = "short",
                    passwordConfirm = "short",
                )
            assertTrue(result.isFailure)
            assertEquals("비밀번호는 12자 이상이어야 합니다.", result.exceptionOrNull()?.message)
        }

    @Test
    fun register_requiresPasswordMatch() =
        runBlocking {
            val result =
                RegisterUseCase(FakeAuthRepository()).invoke(
                    nickname = "감자",
                    email = "a@b.com",
                    password = "password123456",
                    passwordConfirm = "password654321",
                )
            assertTrue(result.isFailure)
            assertEquals("비밀번호가 일치하지 않습니다.", result.exceptionOrNull()?.message)
        }

    @Test
    fun register_mapsConflictDetail() =
        runBlocking {
            val body =
                """{"detail":"already"}""".toResponseBody("application/json".toMediaType())
            val repo = FakeAuthRepository(registerError = HttpException(Response.error<Unit>(409, body)))
            val result =
                RegisterUseCase(repo).invoke(
                    nickname = "감자",
                    email = "a@b.com",
                    password = "password123456",
                    passwordConfirm = "password123456",
                )
            assertTrue(result.isFailure)
            assertEquals("already", result.exceptionOrNull()?.message)
        }

    @Test
    fun register_success() =
        runBlocking {
            val result =
                RegisterUseCase(FakeAuthRepository()).invoke(
                    nickname = "감자",
                    email = "a@b.com",
                    password = "password123456",
                    passwordConfirm = "password123456",
                )
            assertTrue(result.isSuccess)
            assertEquals("감자", result.getOrNull()?.nickname)
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
    private val loginResponse: AuthTokenResponse? = null,
    private val registerResponse: AuthTokenResponse? = null,
    private val meResponse: MeResponse? = null,
    private val nickname: String? = null,
    private var hasSessionFlag: Boolean = false,
    private val loginError: Throwable? = null,
    private val registerError: Throwable? = null,
    private val meError: Throwable? = null,
) : AuthRepository {
    var logoutCalled = false

    override suspend fun login(
        email: String,
        password: String,
    ): AuthTokenResponse {
        loginError?.let { throw it }
        return loginResponse
            ?: AuthTokenResponse(accountId = "id", email = email, token = "t")
    }

    override suspend fun register(
        email: String,
        password: String,
        nickname: String,
    ): AuthTokenResponse {
        registerError?.let { throw it }
        return registerResponse
            ?: AuthTokenResponse(accountId = "id", email = email, token = "t")
    }

    override suspend fun me(): MeResponse {
        meError?.let { throw it }
        return meResponse
            ?: MeResponse(accountId = "id", email = "a@b.com", accountType = "user")
    }

    override suspend fun logout() {
        logoutCalled = true
        hasSessionFlag = false
    }

    override suspend fun hasSession(): Boolean = hasSessionFlag

    override suspend fun displayNickname(): String? = nickname
}
