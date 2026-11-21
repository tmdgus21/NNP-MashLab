package com.potatomeet.app.data.remote

import com.potatomeet.app.data.remote.dto.CreateMeetingRequest
import com.potatomeet.app.data.remote.dto.VoteRequest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertTrue
import org.junit.Test

class DtoContractTest {
    private val json =
        Json {
            ignoreUnknownKeys = true
            explicitNulls = false
        }

    @Test
    fun createMeeting_usesCamelCase() {
        val encoded =
            json.encodeToString(
                CreateMeetingRequest.serializer(),
                CreateMeetingRequest(
                    title = "모임",
                    nickname = "방장",
                    selectedDates = listOf("2026-11-20", "2026-11-26", "2026-11-30"),
                ),
            )
        assertTrue(encoded.contains("\"selectedDates\""))
        assertTrue(!encoded.contains("\"startDate\""))
        assertTrue(!encoded.contains("start_date"))
    }

    @Test
    fun voteRequest_candidateIds() {
        val encoded =
            json.encodeToString(
                VoteRequest.serializer(),
                VoteRequest(candidateIds = listOf("c1", "c2")),
            )
        assertTrue(encoded.contains("\"candidateIds\""))
        assertTrue(!encoded.contains("candidate_ids"))
    }
}
