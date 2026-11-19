package com.potatomeet.app.core

import java.io.IOException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException

object ApiError {
    private val json = Json { ignoreUnknownKeys = true }

    fun messageOf(throwable: Throwable): String =
        when (throwable) {
            is HttpException -> httpMessage(throwable)
            is IOException -> "네트워크에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
            else -> throwable.message?.takeIf { it.isNotBlank() } ?: "요청을 처리하지 못했습니다."
        }

    private fun httpMessage(error: HttpException): String {
        val raw = error.response()?.errorBody()?.string().orEmpty()
        val detail =
            runCatching {
                val element = json.parseToJsonElement(raw)
                val detailEl = element.jsonObject["detail"]
                when {
                    detailEl == null -> null
                    detailEl.jsonPrimitive.isString -> detailEl.jsonPrimitive.content
                    else -> detailEl.toString()
                }
            }.getOrNull()
        return when (error.code()) {
            401 -> detail ?: "로그인이 필요합니다."
            403 -> detail ?: "사용할 수 없는 계정입니다."
            409 -> detail ?: "이미 등록된 이메일입니다."
            422 -> detail ?: "입력값을 확인해 주세요."
            in 500..599 -> "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
            else -> detail ?: "요청에 실패했습니다. (${error.code()})"
        }
    }
}
