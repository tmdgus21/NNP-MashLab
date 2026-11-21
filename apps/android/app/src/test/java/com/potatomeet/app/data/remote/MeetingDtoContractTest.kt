package com.potatomeet.app.data.remote

import com.potatomeet.app.data.remote.dto.CollectionResponse
import com.potatomeet.app.data.remote.dto.CreateMeetingRequest
import com.potatomeet.app.data.remote.dto.MeetingDto
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MeetingDtoContractTest {
    private val json =
        Json {
            ignoreUnknownKeys = true
            explicitNulls = false
        }

    @Test
    fun createMeeting_usesSelectedDatesWithoutRequiredNickname() {
        val encoded =
            json.encodeToString(
                CreateMeetingRequest.serializer(),
                CreateMeetingRequest(
                    title = "모임",
                    selectedDates = listOf("2026-11-20", "2026-11-26"),
                ),
            )
        assertTrue(encoded.contains("\"selectedDates\""))
        assertTrue(!encoded.contains("\"nickname\""))
        assertTrue(!encoded.contains("accounts"))
    }

    @Test
    fun meetingDto_parsesMembersDone() {
        val raw =
            """
            {
              "id":"r1","code":"ABCD2345","title":"t","status":"COLLECTING","revision":1,
              "members":[{"id":"m1","nickname":"감자","role":"OWNER","done":true}],
              "myMemberId":"m1","collectionId":"c1"
            }
            """.trimIndent()
        val dto = json.decodeFromString(MeetingDto.serializer(), raw)
        assertEquals("감자", dto.members.first().nickname)
        assertEquals(true, dto.members.first().done)
        assertEquals("c1", dto.collectionId)
    }

    @Test
    fun collection_parsesSlotCounts() {
        val raw =
            """
            {
              "id":"c1","status":"OPEN",
              "scopeStartsAt":"2026-11-20T00:00:00+09:00",
              "scopeEndsAt":"2026-11-21T00:00:00+09:00",
              "slotCounts":[{"start":"2026-11-20T10:00:00+09:00","end":"2026-11-20T10:30:00+09:00","count":2}],
              "myAvailable":[]
            }
            """.trimIndent()
        val dto = json.decodeFromString(CollectionResponse.serializer(), raw)
        assertEquals(1, dto.slotCounts.size)
        assertEquals(2, dto.slotCounts.first().count)
    }
}
