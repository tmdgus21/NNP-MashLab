package com.potatomeet.app.ui.feature.meeting

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.potatomeet.app.core.ApiError
import com.potatomeet.app.core.TimeFmt
import com.potatomeet.app.data.remote.dto.MeetingDto
import com.potatomeet.app.data.repository.MeetingRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface MeetingEvent {
    data class Toast(val message: String) : MeetingEvent

    data class Navigate(
        val route: String,
    ) : MeetingEvent
}

@HiltViewModel
class MeetingViewModel
    @Inject
    constructor(
        private val meetingRepository: MeetingRepository,
    ) : ViewModel() {
        private val _uiState = MutableStateFlow(MeetingUiState())
        val uiState: StateFlow<MeetingUiState> = _uiState.asStateFlow()

        private val _events = MutableSharedFlow<MeetingEvent>(extraBufferCapacity = 4)
        val events: SharedFlow<MeetingEvent> = _events.asSharedFlow()

        private var sseJob: Job? = null

        fun refreshList() {
            viewModelScope.launch {
                _uiState.update { it.copy(loading = true, errorMessage = null) }
                runCatching {
                    meetingRepository.list()
                }.onSuccess { meetings ->
                    _uiState.update {
                        it.copy(loading = false, meetings = meetings)
                    }
                }.onFailure { e ->
                    val msg = ApiError.messageOf(e)
                    _uiState.update { it.copy(loading = false, errorMessage = msg) }
                    _events.tryEmit(MeetingEvent.Toast(msg))
                }
            }
        }

        fun loadServerBounds() {
            viewModelScope.launch {
                runCatching { meetingRepository.serverTime() }
                    .onSuccess { time ->
                        _uiState.update { it.copy(maxEndDate = time.maxEndDate) }
                    }
            }
        }

        fun createMeeting(
            title: String,
            selectedDates: List<String>,
        ) {
            viewModelScope.launch {
                val t = title.trim()
                val dates = selectedDates.map { it.trim() }.filter { it.isNotEmpty() }.distinct().sorted()
                when {
                    t.isBlank() -> {
                        _events.tryEmit(MeetingEvent.Toast("모임 이름을 입력해 주세요."))
                        return@launch
                    }
                    dates.isEmpty() -> {
                        _events.tryEmit(MeetingEvent.Toast("날짜를 1개 이상 선택해 주세요."))
                        return@launch
                    }
                }
                _uiState.update { it.copy(mutating = true, errorMessage = null) }
                runCatching {
                    meetingRepository.create(t, dates)
                }.onSuccess { meeting ->
                    _uiState.update {
                        it.copy(
                            mutating = false,
                            activeMeeting = meeting,
                            inviteCode = meeting.code,
                            meetings = listOf(meeting) + it.meetings.filterNot { m -> m.id == meeting.id },
                        )
                    }
                    attachSse(meeting.id)
                    _events.tryEmit(MeetingEvent.Toast("모임이 만들어졌습니다. 초대 코드: ${meeting.code}"))
                    _events.tryEmit(MeetingEvent.Navigate("room_detail"))
                }.onFailure { e ->
                    val base = ApiError.messageOf(e)
                    val msg =
                        if (base.contains("selectedDates", ignoreCase = true) ||
                            base.contains("422") ||
                            base.contains("404")
                        ) {
                            "복수 날짜 모임 생성 실패: $base"
                        } else {
                            base
                        }
                    _uiState.update { it.copy(mutating = false, loading = false, errorMessage = msg) }
                    _events.tryEmit(MeetingEvent.Toast(msg))
                }
            }
        }

        fun joinMeeting(
            code: String,
            @Suppress("UNUSED_PARAMETER") fromInviteConfirm: Boolean = false,
        ) {
            viewModelScope.launch {
                val c = code.trim().uppercase()
                if (c.length != 8) {
                    val msg = "초대 코드 8자리를 입력해 주세요."
                    _uiState.update { it.copy(errorMessage = msg) }
                    _events.tryEmit(MeetingEvent.Toast(msg))
                    return@launch
                }
                val alreadyMember =
                    _uiState.value.meetings.any { it.code.equals(c, ignoreCase = true) }
                _uiState.update { it.copy(mutating = true, errorMessage = null) }
                runCatching {
                    meetingRepository.join(c)
                }.onSuccess { meeting ->
                    openMeeting(meeting, navigate = true)
                    val toast =
                        if (alreadyMember) {
                            "이미 참여 중인 모임입니다."
                        } else {
                            "모임에 참여했습니다."
                        }
                    _events.tryEmit(MeetingEvent.Toast(toast))
                }.onFailure { e ->
                    // 409 closed / forbidden re-entry: errorMessage stays for invite confirm UI.
                    fail(e)
                }
            }
        }

        fun clearError() {
            _uiState.update { it.copy(errorMessage = null) }
        }

        fun openMeetingById(
            meetingId: String,
            navigate: Boolean = true,
        ) {
            viewModelScope.launch {
                _uiState.update { it.copy(loading = true, errorMessage = null) }
                runCatching { meetingRepository.get(meetingId) }
                    .onSuccess { meeting -> openMeeting(meeting, navigate = navigate) }
                    .onFailure { e -> fail(e) }
            }
        }

        private suspend fun openMeeting(
            meeting: MeetingDto,
            navigate: Boolean,
        ) {
            _uiState.update {
                it.copy(
                    loading = false,
                    mutating = false,
                    activeMeeting = meeting,
                    inviteCode = meeting.code,
                    meetings = listOf(meeting) + it.meetings.filterNot { m -> m.id == meeting.id },
                )
            }
            attachSse(meeting.id)
            when (meeting.status.uppercase()) {
                "COLLECTING" -> {
                    refreshCollection(meeting.id)
                    if (navigate) _events.tryEmit(MeetingEvent.Navigate("room_detail"))
                }
                "VOTING" -> {
                    refreshCandidates(meeting.id)
                    if (navigate) _events.tryEmit(MeetingEvent.Navigate("ai_result"))
                }
                "CONFIRMED" -> {
                    refreshResult(meeting.id)
                    if (navigate) _events.tryEmit(MeetingEvent.Navigate("result"))
                }
                else -> {
                    refreshCollection(meeting.id)
                    if (navigate) _events.tryEmit(MeetingEvent.Navigate("room_detail"))
                }
            }
        }

        fun refreshActive() {
            val id = _uiState.value.activeMeeting?.id ?: return
            viewModelScope.launch {
                runCatching { meetingRepository.get(id) }
                    .onSuccess { meeting ->
                        _uiState.update { it.copy(activeMeeting = meeting, inviteCode = meeting.code) }
                        when (meeting.status.uppercase()) {
                            "VOTING" -> refreshCandidates(meeting.id)
                            "CONFIRMED" -> refreshResult(meeting.id)
                            else -> refreshCollection(meeting.id)
                        }
                    }
                    .onFailure { e ->
                        _events.tryEmit(MeetingEvent.Toast(ApiError.messageOf(e)))
                    }
            }
        }

        fun refreshCollection(meetingId: String? = _uiState.value.activeMeeting?.id) {
            val id = meetingId ?: return
            viewModelScope.launch {
                runCatching { meetingRepository.collection(id) }
                    .onSuccess { col ->
                        _uiState.update { it.copy(collection = col) }
                    }
                    .onFailure { e ->
                        // collection may be closed after coordination
                        if (e.message?.contains("404") == true || ApiError.messageOf(e).contains("입력")) {
                            refreshCandidates(id)
                        } else {
                            _events.tryEmit(MeetingEvent.Toast(ApiError.messageOf(e)))
                        }
                    }
            }
        }

        fun submitAvailability(
            ranges: List<Pair<String, String>>,
            allUnavailable: Boolean = false,
        ) {
            val meeting = _uiState.value.activeMeeting ?: return
            if (_uiState.value.mutating) return
            val collectionId = meeting.collectionId ?: _uiState.value.collection?.id
            if (collectionId.isNullOrBlank()) {
                _events.tryEmit(MeetingEvent.Toast("입력 기간을 불러오지 못했습니다."))
                return
            }
            viewModelScope.launch {
                _uiState.update { it.copy(mutating = true) }
                runCatching {
                    meetingRepository.submitAvailability(
                        meeting.id,
                        collectionId,
                        ranges,
                        allUnavailable = allUnavailable,
                    )
                }.onSuccess { col ->
                    _uiState.update { it.copy(mutating = false, collection = col) }
                    _events.tryEmit(MeetingEvent.Toast("불가능 시간을 서버에 저장했습니다."))
                    refreshActive()
                    _events.tryEmit(MeetingEvent.Navigate("room_detail"))
                }.onFailure { e ->
                    fail(e)
                }
            }
        }

        fun refreshCandidates(meetingId: String? = _uiState.value.activeMeeting?.id) {
            val id = meetingId ?: return
            viewModelScope.launch {
                runCatching { meetingRepository.candidates(id) }
                    .onSuccess { res ->
                        _uiState.update {
                            it.copy(
                                candidates = res.candidates,
                                candidatesStatus = res.status,
                                aiSummary = res.aiSummary,
                                votingEndsAt = res.votingEndsAt,
                                myBallotSubmitted = res.myBallotSubmitted,
                                selectedCandidateIds =
                                    if (res.myBallotSubmitted) {
                                        it.selectedCandidateIds
                                    } else {
                                        it.selectedCandidateIds.intersect(res.candidates.map { c -> c.id }.toSet())
                                    },
                            )
                        }
                        if (res.status.uppercase() == "CONFIRMED") {
                            refreshResult(id)
                        }
                    }
                    .onFailure { e ->
                        _events.tryEmit(MeetingEvent.Toast(ApiError.messageOf(e)))
                    }
            }
        }

        fun toggleCandidate(id: String) {
            _uiState.update { state ->
                val next =
                    if (id in state.selectedCandidateIds) {
                        state.selectedCandidateIds - id
                    } else {
                        state.selectedCandidateIds + id
                    }
                state.copy(selectedCandidateIds = next)
            }
        }

        fun submitVotes() {
            val meeting = _uiState.value.activeMeeting ?: return
            val ids = _uiState.value.selectedCandidateIds.toList()
            viewModelScope.launch {
                _uiState.update { it.copy(mutating = true) }
                runCatching {
                    meetingRepository.vote(meeting.id, ids)
                }.onSuccess { res ->
                    _uiState.update {
                        it.copy(
                            mutating = false,
                            candidates = res.candidates,
                            candidatesStatus = res.status,
                            aiSummary = res.aiSummary,
                            votingEndsAt = res.votingEndsAt,
                            myBallotSubmitted = res.myBallotSubmitted,
                        )
                    }
                    _events.tryEmit(MeetingEvent.Toast(if (ids.isEmpty()) "빈 투표를 제출했습니다." else "투표를 저장했습니다."))
                    if (res.status.uppercase() == "CONFIRMED") {
                        refreshResult(meeting.id)
                        _events.tryEmit(MeetingEvent.Navigate("result"))
                    }
                }.onFailure { e ->
                    fail(e)
                }
            }
        }

        fun refreshResult(meetingId: String? = _uiState.value.activeMeeting?.id) {
            val id = meetingId ?: return
            viewModelScope.launch {
                runCatching { meetingRepository.result(id) }
                    .onSuccess { result ->
                        _uiState.update { it.copy(result = result) }
                    }
                    .onFailure { e ->
                        _events.tryEmit(MeetingEvent.Toast(ApiError.messageOf(e)))
                    }
            }
        }

        fun deleteActiveMeeting() {
            val meeting = _uiState.value.activeMeeting ?: return
            viewModelScope.launch {
                _uiState.update { it.copy(mutating = true) }
                runCatching {
                    meetingRepository.delete(meeting.id, meeting.revision)
                }.onSuccess {
                    detachSse()
                    _uiState.update {
                        it.copy(
                            mutating = false,
                            activeMeeting = null,
                            collection = null,
                            candidates = emptyList(),
                            result = null,
                            meetings = it.meetings.filterNot { m -> m.id == meeting.id },
                        )
                    }
                    _events.tryEmit(MeetingEvent.Toast("모임을 삭제했습니다."))
                    _events.tryEmit(MeetingEvent.Navigate("home"))
                }.onFailure { e ->
                    fail(e)
                }
            }
        }

        fun deleteMeeting(meeting: MeetingDto) {
            viewModelScope.launch {
                runCatching { meetingRepository.delete(meeting.id, meeting.revision) }
                    .onSuccess {
                        _uiState.update {
                            it.copy(meetings = it.meetings.filterNot { m -> m.id == meeting.id })
                        }
                        _events.tryEmit(MeetingEvent.Toast("모임을 삭제했습니다."))
                    }
                    .onFailure { e ->
                        _events.tryEmit(MeetingEvent.Toast(ApiError.messageOf(e)))
                    }
            }
        }

        fun clearActive() {
            detachSse()
            _uiState.update {
                it.copy(
                    activeMeeting = null,
                    collection = null,
                    candidates = emptyList(),
                    result = null,
                    selectedCandidateIds = emptySet(),
                    inviteCode = null,
                )
            }
        }

        private fun attachSse(meetingId: String) {
            sseJob?.cancel()
            sseJob =
                viewModelScope.launch {
                    meetingRepository.events(meetingId).collect { event ->
                        when (event.name) {
                            "meeting_deleted" -> {
                                _events.tryEmit(MeetingEvent.Toast("모임이 삭제되었습니다."))
                                clearActive()
                                refreshList()
                                _events.tryEmit(MeetingEvent.Navigate("home"))
                            }
                            else -> refreshActive()
                        }
                    }
                }
        }

        private fun detachSse() {
            sseJob?.cancel()
            sseJob = null
        }

        private fun fail(e: Throwable) {
            val msg = ApiError.messageOf(e)
            _uiState.update { it.copy(mutating = false, loading = false, errorMessage = msg) }
            _events.tryEmit(MeetingEvent.Toast(msg))
        }

        fun defaultDateRange(): Pair<String, String> {
            val start = TimeFmt.todaySeoul()
            val end = start.plusDays(6)
            return TimeFmt.isoDate(start) to TimeFmt.isoDate(end)
        }
    }
