package com.potatomeet.app.data.repository

import com.potatomeet.app.data.remote.MeetingSseClient
import com.potatomeet.app.data.remote.MeetingSseEvent
import com.potatomeet.app.data.remote.PotatoApi
import com.potatomeet.app.data.remote.dto.CandidatesResponse
import com.potatomeet.app.data.remote.dto.CollectionResponse
import com.potatomeet.app.data.remote.dto.CreateMeetingRequest
import com.potatomeet.app.data.remote.dto.JoinMeetingRequest
import com.potatomeet.app.data.remote.dto.MeetingDto
import com.potatomeet.app.data.remote.dto.ResultResponse
import com.potatomeet.app.data.remote.dto.RevisionRequest
import com.potatomeet.app.data.remote.dto.ServerTimeResponse
import com.potatomeet.app.data.remote.dto.SubmitResponseRequest
import com.potatomeet.app.data.remote.dto.TimeRangeDto
import com.potatomeet.app.data.remote.dto.VoteRequest
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class MeetingRepository
    @Inject
    constructor(
        private val api: PotatoApi,
        private val sseClient: MeetingSseClient,
    ) {
        suspend fun serverTime(): ServerTimeResponse = api.serverTime()

        suspend fun list(): List<MeetingDto> = api.listMeetings().meetings

        suspend fun create(
            title: String,
            selectedDates: List<String>,
        ): MeetingDto =
            api.createMeeting(
                CreateMeetingRequest(
                    title = title,
                    selectedDates = selectedDates.sorted(),
                ),
            )

        suspend fun join(code: String): MeetingDto =
            api.joinMeeting(JoinMeetingRequest(code = code))

        suspend fun get(id: String): MeetingDto = api.getMeeting(id)

        suspend fun delete(
            id: String,
            expectedRevision: Int,
        ) {
            api.deleteMeeting(id, RevisionRequest(expectedRevision = expectedRevision))
        }

        suspend fun collection(meetingId: String): CollectionResponse = api.getCollection(meetingId)

        suspend fun submitAvailability(
            meetingId: String,
            collectionId: String,
            ranges: List<Pair<String, String>>,
        ): CollectionResponse =
            api.submitResponse(
                meetingId,
                collectionId,
                SubmitResponseRequest(
                    available = ranges.map { (s, e) -> TimeRangeDto(start = s, end = e) },
                ),
            )

        suspend fun candidates(meetingId: String): CandidatesResponse = api.getCandidates(meetingId)

        suspend fun vote(
            meetingId: String,
            candidateIds: List<String>,
        ): CandidatesResponse = api.submitVotes(meetingId, VoteRequest(candidateIds = candidateIds))

        suspend fun result(meetingId: String): ResultResponse = api.getResult(meetingId)

        fun events(meetingId: String): Flow<MeetingSseEvent> = sseClient.events(meetingId)
    }
