package com.potatomeet.app.data.remote.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class CreateMeetingRequest(
    val title: String,
    val nickname: String? = null,
    val selectedDates: List<String>? = null,
    val startDate: String? = null,
    val endDate: String? = null,
)

@Serializable
data class JoinMeetingRequest(
    val code: String,
    val nickname: String? = null,
)

@Serializable
data class MeetingMemberDto(
    val id: String? = null,
    val nickname: String,
    val role: String? = null,
    val done: Boolean? = null,
)

@Serializable
data class MeetingDto(
    val id: String,
    val code: String,
    val title: String,
    val status: String,
    val revision: Int,
    val startsAt: String? = null,
    val endsAt: String? = null,
    val selectedDates: List<String> = emptyList(),
    val serverTime: String? = null,
    val timezone: String? = null,
    val legacy: Boolean? = null,
    val collectionId: String? = null,
    val members: List<MeetingMemberDto> = emptyList(),
    val myMemberId: String? = null,
)

@Serializable
data class MeetingListResponse(
    val meetings: List<MeetingDto> = emptyList(),
)

@Serializable
data class TimeRangeDto(
    val start: String,
    val end: String,
)

@Serializable
data class SubmitResponseRequest(
    val available: List<TimeRangeDto>,
)

@Serializable
data class SlotCountDto(
    val start: String,
    val end: String,
    val count: Int,
)

@Serializable
data class CollectionResponse(
    val id: String,
    val cycle: Int = 1,
    val kind: String = "INITIAL",
    val status: String,
    val scopeStartsAt: String,
    val scopeEndsAt: String,
    val closesAt: String? = null,
    val graceUntil: String? = null,
    val extendedCount: Int = 0,
    val doneCount: Int = 0,
    val memberCount: Int = 0,
    val myAvailable: List<TimeRangeDto> = emptyList(),
    val slotCounts: List<SlotCountDto> = emptyList(),
    val nearMisses: List<JsonElement> = emptyList(),
    val revision: Int = 0,
    val serverTime: String? = null,
)

@Serializable
data class CandidateDto(
    val id: String,
    val startsAt: String,
    val endsAt: String,
    val availableCount: Int,
    val sortOrder: Int,
    val voteCount: Int = 0,
    val memberNicknames: List<String> = emptyList(),
)

@Serializable
data class CandidatesResponse(
    val runId: String? = null,
    val candidates: List<CandidateDto> = emptyList(),
    val status: String,
    val revision: Int,
    val aiSummary: String? = null,
    val votingEndsAt: String? = null,
    val excludedSoonCount: Int = 0,
    val myBallotSubmitted: Boolean = false,
    val closedReason: String? = null,
    val serverTime: String? = null,
)

@Serializable
data class VoteRequest(
    val candidateIds: List<String>,
)

@Serializable
data class RevisionRequest(
    val expectedRevision: Int,
)

@Serializable
data class ServerTimeResponse(
    val serverTime: String,
    val timezone: String,
    val maxEndDate: String,
)

@Serializable
data class ResultResponse(
    val method: String,
    val voteCount: Int? = null,
    val tieBroken: Boolean? = null,
    val confirmedAt: String? = null,
    val candidate: CandidateDto? = null,
    val status: String? = null,
    val revision: Int? = null,
)

@Serializable
data class MeetingSsePayload(
    val meetingId: String? = null,
    val revision: Int? = null,
)
