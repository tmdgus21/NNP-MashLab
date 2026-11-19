package com.potatomeet.app.ui.feature.meeting

import com.potatomeet.app.data.remote.dto.CandidateDto
import com.potatomeet.app.data.remote.dto.CollectionResponse
import com.potatomeet.app.data.remote.dto.MeetingDto
import com.potatomeet.app.data.remote.dto.ResultResponse

data class MeetingUiState(
    val loading: Boolean = false,
    val mutating: Boolean = false,
    val meetings: List<MeetingDto> = emptyList(),
    val activeMeeting: MeetingDto? = null,
    val collection: CollectionResponse? = null,
    val candidates: List<CandidateDto> = emptyList(),
    val candidatesStatus: String = "",
    val aiSummary: String? = null,
    val votingEndsAt: String? = null,
    val myBallotSubmitted: Boolean = false,
    val selectedCandidateIds: Set<String> = emptySet(),
    val result: ResultResponse? = null,
    val maxEndDate: String? = null,
    val errorMessage: String? = null,
    val inviteCode: String? = null,
)
