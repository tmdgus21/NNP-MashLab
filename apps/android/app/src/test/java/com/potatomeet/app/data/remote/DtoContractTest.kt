package com.potatomeet.app.data.remote

import com.potatomeet.app.data.remote.dto.CandidatesResponse
import com.potatomeet.app.data.remote.dto.CreateMeetingRequest
import com.potatomeet.app.data.remote.dto.VoteRequest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
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
                    nickname = "감자",
                    startDate = "2026-11-20",
                    endDate = "2026-11-22",
                ),
            )
        assertTrue(encoded.contains("\"startDate\""))
        assertTrue(encoded.contains("\"endDate\""))
        assertTrue(!encoded.contains("start_date"))
    }

    @Test
    fun voteRequest_candidateIds() {
        val encoded =
            json.encodeToString(
                VoteRequest.serializer(),
                VoteRequest(candidateIds = listOf("a", "b")),
            )
        assertTrue(encoded.contains("\"candidateIds\""))
    }

    @Test
    fun candidatesResponse_parsesAiSummary() {
        val raw =
            """
            {"runId":"r1","candidates":[],"status":"VOTING","revision":3,
             "aiSummary":"두 명이 가능합니다","votingEndsAt":null,"excludedSoonCount":0,
             "myBallotSubmitted":false}
            """.trimIndent()
        val parsed = json.decodeFromString(CandidatesResponse.serializer(), raw)
        assertEquals("두 명이 가능합니다", parsed.aiSummary)
        assertEquals("VOTING", parsed.status)
    }
}
