package com.potatomeet.app.data.remote

import com.potatomeet.app.BuildConfig
import com.potatomeet.app.core.TokenStore
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources

data class MeetingSseEvent(
    val name: String,
    val data: String,
)

@Singleton
class MeetingSseClient
@Inject
constructor(
    private val okHttpClient: OkHttpClient,
    private val tokenStore: TokenStore,
) {
    fun events(meetingId: String): Flow<MeetingSseEvent> =
        flow {
            var backoffMs = 1_000L
            while (true) {
                try {
                    eventsOnce(meetingId).collect { event ->
                        backoffMs = 1_000L
                        emit(event)
                    }
                } catch (_: Exception) {
                    // reconnect below
                }
                delay(backoffMs)
                backoffMs = (backoffMs * 2).coerceAtMost(30_000L)
            }
        }

    private fun eventsOnce(meetingId: String): Flow<MeetingSseEvent> =
        callbackFlow {
            val base = BuildConfig.API_BASE_URL.trimEnd('/')
            val token = runBlocking { tokenStore.token() }
            val requestBuilder =
                Request.Builder()
                    .url("$base/meetings/$meetingId/events")
                    .header("Accept", "text/event-stream")
            if (!token.isNullOrBlank()) {
                requestBuilder.header("Authorization", "Bearer $token")
            }
            val factory = EventSources.createFactory(okHttpClient)
            val listener =
                object : EventSourceListener() {
                    override fun onEvent(
                        eventSource: EventSource,
                        id: String?,
                        type: String?,
                        data: String,
                    ) {
                        val name = type?.takeIf { it.isNotBlank() } ?: "message"
                        if (name == "ping" || data.isBlank()) return
                        trySend(MeetingSseEvent(name = name, data = data))
                    }

                    override fun onFailure(
                        eventSource: EventSource,
                        t: Throwable?,
                        response: Response?,
                    ) {
                        close(t ?: IllegalStateException("SSE failed: ${response?.code}"))
                    }

                    override fun onClosed(eventSource: EventSource) {
                        close()
                    }
                }
            val source = factory.newEventSource(requestBuilder.build(), listener)
            awaitClose { source.cancel() }
        }
}
