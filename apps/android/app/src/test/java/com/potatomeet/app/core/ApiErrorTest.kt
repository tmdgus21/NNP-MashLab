package com.potatomeet.app.core

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException

class ApiErrorTest {
    @Test
    fun networkIo_mapsToKoreanMessage() {
        assertEquals(
            "네트워크에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            ApiError.messageOf(IOException("offline")),
        )
    }

    @Test
    fun conflict_usesDetail() {
        val body = """{"detail":"이미 등록된 이메일입니다."}""".toResponseBody("application/json".toMediaType())
        val error = HttpException(Response.error<Unit>(409, body))
        assertEquals("이미 등록된 이메일입니다.", ApiError.messageOf(error))
    }

    @Test
    fun unauthorized_fallback() {
        val body = "".toResponseBody("application/json".toMediaType())
        val error = HttpException(Response.error<Unit>(401, body))
        assertEquals("로그인이 필요합니다.", ApiError.messageOf(error))
    }

    @Test
    fun serverError_fallback() {
        val body = "boom".toResponseBody("text/plain".toMediaType())
        val error = HttpException(Response.error<Unit>(503, body))
        assertEquals(
            "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요. (503)",
            ApiError.messageOf(error),
        )
    }

    @Test
    fun notFound_fallbackMentionsMissingApi() {
        val body = "".toResponseBody("application/json".toMediaType())
        val error = HttpException(Response.error<Unit>(404, body))
        assertEquals(
            "서버에 해당 API가 없습니다. (404) 아직 배포되지 않은 기능일 수 있습니다.",
            ApiError.messageOf(error),
        )
    }
}
