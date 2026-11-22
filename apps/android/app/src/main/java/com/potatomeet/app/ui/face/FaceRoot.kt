package com.potatomeet.app.ui.face

import android.app.Activity
import android.content.Intent
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.potatomeet.app.core.TimeFmt
import com.potatomeet.app.data.remote.dto.MeetingDto
import com.potatomeet.app.ui.face.screens.AiResultScreen
import com.potatomeet.app.ui.face.screens.CreateRoomScreen
import com.potatomeet.app.ui.face.screens.EditUnavailableScreen
import com.potatomeet.app.ui.face.screens.FriendsScreen
import com.potatomeet.app.ui.face.screens.HomeScreen
import com.potatomeet.app.ui.face.screens.LoginScreen
import com.potatomeet.app.ui.face.screens.MyPageScreen
import com.potatomeet.app.ui.face.screens.ResultScreen
import com.potatomeet.app.ui.face.screens.RoomDetailScreen
import com.potatomeet.app.ui.face.screens.SignUpScreen
// Legacy step screens + CreateAppointmentStep3TimeScreen + submitAvailability are kept on disk
// for later restore; FaceRoot no longer routes to them.
import com.potatomeet.app.ui.feature.auth.AuthEvent
import com.potatomeet.app.ui.feature.auth.AuthViewModel
import com.potatomeet.app.ui.feature.meeting.MeetingEvent
import com.potatomeet.app.ui.feature.meeting.MeetingViewModel

/**
 * Face navigation: Home → CreateRoom → RoomDetail → EditUnavailable / AiResult.
 * Auth OTP + schedule APIs wired; EditUnavailable submits 30-min availability.
 */
@Composable
fun FaceRoot(
    authViewModel: AuthViewModel = hiltViewModel(),
    meetingViewModel: MeetingViewModel = hiltViewModel(),
) {
    val activity = LocalContext.current as? Activity
    val context = LocalContext.current
    val authState by authViewModel.uiState.collectAsStateWithLifecycle()
    val meetingState by meetingViewModel.uiState.collectAsStateWithLifecycle()

    val currentScreen = remember { mutableStateOf("login") }
    val loggedInNickname = remember { mutableStateOf("") }
    val loggedInId = remember { mutableStateOf("") }

    val roomTitle = remember { mutableStateOf("") }
    val roomDesc = remember { mutableStateOf("") }
    val selectedDates = remember { mutableStateListOf<String>() }
    val localUnavailable = remember { mutableStateListOf<UnavailableSlot>() }
    val detailAppointment = remember { mutableStateOf<Appointment?>(null) }

    val appointmentsList = meetingState.meetings.map { it.toAppointment() }

    LaunchedEffect(Unit) {
        authViewModel.events.collect { event ->
            when (event) {
                is AuthEvent.Toast -> Toast.makeText(context, event.message, Toast.LENGTH_SHORT).show()
            }
        }
    }

    LaunchedEffect(Unit) {
        meetingViewModel.events.collect { event ->
            when (event) {
                is MeetingEvent.Toast -> Toast.makeText(context, event.message, Toast.LENGTH_SHORT).show()
                is MeetingEvent.Navigate -> {
                    val route =
                        when (event.route) {
                            "create_step2", "create_step3", "create_step4" -> "room_detail"
                            "create_ai_recommendation" -> "ai_result"
                            else -> event.route
                        }
                    if (route == "room_detail") {
                        meetingViewModel.uiState.value.activeMeeting
                            ?.toAppointment()
                            ?.let { detailAppointment.value = it }
                    }
                    currentScreen.value = route
                }
            }
        }
    }

    LaunchedEffect(authState.isLoggedIn, authState.checkingSession) {
        if (authState.checkingSession) return@LaunchedEffect
        if (authState.isLoggedIn) {
            val email = authState.email.orEmpty()
            loggedInId.value = email
            loggedInNickname.value =
                authState.nickname?.takeIf { it.isNotBlank() }
                    ?: email.substringBefore('@').ifBlank { "사용자" }
            if (currentScreen.value == "login" || currentScreen.value == "signup") {
                currentScreen.value = "home"
            }
            meetingViewModel.refreshList()
            meetingViewModel.loadServerBounds()
        } else if (currentScreen.value !in setOf("login", "signup")) {
            meetingViewModel.clearActive()
            currentScreen.value = "login"
            loggedInNickname.value = ""
            loggedInId.value = ""
        }
    }

    BackHandler(enabled = currentScreen.value != "login") {
        when (currentScreen.value) {
            "signup" -> currentScreen.value = "login"
            "home" -> activity?.finish()
            "friends", "mypage" -> currentScreen.value = "home"
            "create_room" -> currentScreen.value = "home"
            "room_detail" -> currentScreen.value = "home"
            "edit_unavailable" -> currentScreen.value = "room_detail"
            "ai_result" -> currentScreen.value = "room_detail"
            "result" -> currentScreen.value = "home"
            else -> currentScreen.value = "home"
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize().imePadding(),
        color = Color(0xFFFFFCF3),
    ) {
        when {
            authState.checkingSession -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Color(0xFFFF9800))
                }
            }
            currentScreen.value == "login" -> {
                LoginScreen(
                    isLoading = authState.loginLoading,
                    otpPending = authState.otpPurpose == "LOGIN" && authState.pendingChallenge != null,
                    onRequestOtp = { email, password -> authViewModel.login(email, password) },
                    onVerifyOtp = { code -> authViewModel.verifyOtp(code) },
                    onResendOtp = { authViewModel.resendOtp() },
                    onSignUpClick = {
                        authViewModel.clearPendingOtp()
                        currentScreen.value = "signup"
                    },
                )
            }
            currentScreen.value == "signup" -> {
                SignUpScreen(
                    isLoading = authState.registerLoading,
                    otpPending = authState.otpPurpose == "REGISTER" && authState.pendingChallenge != null,
                    onRequestOtp = { nickname, email, password, passwordConfirm ->
                        authViewModel.register(nickname, email, password, passwordConfirm)
                    },
                    onVerifyOtp = { code -> authViewModel.verifyOtp(code) },
                    onResendOtp = { authViewModel.resendOtp() },
                    onBackClick = {
                        authViewModel.clearPendingOtp()
                        currentScreen.value = "login"
                    },
                )
            }
            currentScreen.value in
                setOf(
                    "home",
                    "friends",
                    "mypage",
                    "create_room",
                    "room_detail",
                    "edit_unavailable",
                    "ai_result",
                    "result",
                )
            -> {
                // Dump navigates Home ↔ Friends/My via header links (no bottom bar).
                Scaffold(
                    containerColor = Color(0xFFFFFCF3),
                ) { innerPadding ->
                    Box(modifier = Modifier.padding(innerPadding).fillMaxSize()) {
                        when (currentScreen.value) {
                            "home" -> {
                                HomeScreen(
                                    nickname = loggedInNickname.value,
                                    appointmentsList = appointmentsList,
                                    onLogoutClick = { authViewModel.logout() },
                                    onCreateAppointmentClick = {
                                        meetingViewModel.clearActive()
                                        roomTitle.value = ""
                                        roomDesc.value = ""
                                        selectedDates.clear()
                                        localUnavailable.clear()
                                        currentScreen.value = "create_room"
                                    },
                                    onDeleteAppointment = { appt ->
                                        if (appt.meetingId.isNotBlank()) {
                                            meetingViewModel.deleteMeeting(appt.toMeetingStub())
                                        }
                                    },
                                    onOpenAppointment = { appt ->
                                        detailAppointment.value = appt
                                        localUnavailable.clear()
                                        if (appt.meetingId.isNotBlank()) {
                                            meetingViewModel.openMeetingById(appt.meetingId)
                                        }
                                        currentScreen.value = "room_detail"
                                    },
                                    onFriendsClick = { currentScreen.value = "friends" },
                                    onMyPageClick = { currentScreen.value = "mypage" },
                                    onJoinClick = { code ->
                                        meetingViewModel.joinMeeting(code)
                                    },
                                    isMutating = meetingState.mutating || meetingState.loading,
                                )
                            }
                            "create_room" -> {
                                val today = java.time.LocalDate.now()
                                val maxEnd =
                                    meetingState.maxEndDate
                                        ?.takeIf { it.isNotBlank() }
                                        ?.let {
                                            runCatching { java.time.LocalDate.parse(it.take(10)) }.getOrNull()
                                        }
                                        ?: today.plusMonths(1)
                                CreateRoomScreen(
                                    roomTitle = roomTitle.value,
                                    onRoomTitleChange = { roomTitle.value = it },
                                    roomDesc = roomDesc.value,
                                    onRoomDescChange = { roomDesc.value = it },
                                    selectedDates = selectedDates.toList(),
                                    onToggleSelectedDate = { iso ->
                                        if (selectedDates.contains(iso)) {
                                            selectedDates.remove(iso)
                                        } else {
                                            selectedDates.add(iso)
                                        }
                                    },
                                    onClearSelectedDates = { selectedDates.clear() },
                                    minSelectableDate = today,
                                    maxSelectableDate = maxEnd,
                                    accountNickname = loggedInNickname.value.takeIf { it.isNotBlank() },
                                    isLoading = meetingState.mutating,
                                    onBackClick = { currentScreen.value = "home" },
                                    onCreateClick = {
                                        meetingViewModel.createMeeting(
                                            title = roomTitle.value,
                                            selectedDates = selectedDates.toList(),
                                        )
                                    },
                                )
                            }
                            "room_detail" -> {
                                val appt =
                                    detailAppointment.value
                                        ?: meetingState.activeMeeting?.toAppointment()
                                if (appt == null) {
                                    currentScreen.value = "home"
                                } else {
                                    val merged =
                                        appt.copy(
                                            selectedDates =
                                                meetingState.activeMeeting?.selectedDates
                                                    ?.takeIf { it.isNotEmpty() }
                                                    ?: appt.selectedDates,
                                            invitedFriends =
                                                meetingState.activeMeeting?.members
                                                    ?.map { it.nickname }
                                                    ?.takeIf { it.isNotEmpty() }
                                                    ?: appt.invitedFriends,
                                            code =
                                                meetingState.activeMeeting?.code
                                                    ?.takeIf { it.isNotBlank() }
                                                    ?: appt.code,
                                        )
                                    detailAppointment.value = merged
                                    LaunchedEffect(merged.meetingId, currentScreen.value) {
                                        if (merged.meetingId.isNotBlank()) {
                                            meetingViewModel.refreshCollection(merged.meetingId)
                                        }
                                    }
                                    val col = meetingState.collection
                                    val unavailableLines =
                                        AvailabilityConverter.formatUnavailableDisplay(
                                            selectedIsoDates = merged.selectedDates,
                                            myAvailable = col?.myAvailable.orEmpty(),
                                            mySubmitted = col?.mySubmitted == true,
                                            scopeStartsAt = col?.scopeStartsAt,
                                            scopeEndsAt = col?.scopeEndsAt,
                                        )
                                    RoomDetailScreen(
                                        appointment = merged,
                                        mySubmitted = col?.mySubmitted == true,
                                        myAvailableLines = unavailableLines,
                                        onBackClick = { currentScreen.value = "home" },
                                        onEditAvailabilityClick = {
                                            currentScreen.value = "edit_unavailable"
                                        },
                                        onAiResultClick = {
                                            if (merged.meetingId.isNotBlank()) {
                                                meetingViewModel.openMeetingById(merged.meetingId, navigate = false)
                                                meetingViewModel.refreshCandidates(merged.meetingId)
                                            }
                                            currentScreen.value = "ai_result"
                                        },
                                        onInviteClick = {
                                            val code = merged.code
                                            if (code.isNotBlank()) {
                                                val send =
                                                    Intent(Intent.ACTION_SEND).apply {
                                                        type = "text/plain"
                                                        putExtra(
                                                            Intent.EXTRA_TEXT,
                                                            "Potato Meet 초대 코드: $code\nhttps://oranganman.site/join?code=$code",
                                                        )
                                                    }
                                                context.startActivity(Intent.createChooser(send, "초대 공유"))
                                            }
                                        },
                                    )
                                }
                            }
                            "edit_unavailable" -> {
                                val dates =
                                    meetingState.activeMeeting?.selectedDates
                                        ?.takeIf { it.isNotEmpty() }
                                        ?: detailAppointment.value?.selectedDates.orEmpty()
                                            .ifEmpty { selectedDates.toList() }
                                val meetingId = meetingState.activeMeeting?.id
                                var hydrated by remember(meetingId, currentScreen.value) {
                                    mutableStateOf(false)
                                }
                                LaunchedEffect(meetingId, currentScreen.value) {
                                    hydrated = false
                                    if (meetingId.isNullOrBlank()) return@LaunchedEffect
                                    meetingViewModel.refreshCollection(meetingId)
                                }
                                val scopeStartsAt = meetingState.collection?.scopeStartsAt
                                val scopeEndsAt = meetingState.collection?.scopeEndsAt
                                LaunchedEffect(
                                    meetingState.collection?.id,
                                    meetingState.collection?.mySubmitted,
                                    meetingState.collection?.revision,
                                    meetingState.collection?.scopeStartsAt,
                                    meetingState.collection?.scopeEndsAt,
                                    dates,
                                    hydrated,
                                ) {
                                    if (hydrated) return@LaunchedEffect
                                    val col = meetingState.collection ?: return@LaunchedEffect
                                    if (meetingId != null && col.id.isNotBlank()) {
                                        val restored =
                                            AvailabilityConverter.toUnavailableSlots(
                                                selectedIsoDates = dates,
                                                myAvailable = col.myAvailable,
                                                mySubmitted = col.mySubmitted,
                                                scopeStartsAt = col.scopeStartsAt,
                                                scopeEndsAt = col.scopeEndsAt,
                                            )
                                        localUnavailable.clear()
                                        localUnavailable.addAll(restored)
                                        hydrated = true
                                    }
                                }
                                EditUnavailableScreen(
                                    selectedIsoDates = dates,
                                    unavailableSlots = localUnavailable.toList(),
                                    scopeStartsAt = scopeStartsAt,
                                    scopeEndsAt = scopeEndsAt,
                                    saving = meetingState.mutating,
                                    onToggleSlot = { slot ->
                                        if (meetingState.mutating) return@EditUnavailableScreen
                                        if (!AvailabilityConverter.isSlotInScope(
                                                slot,
                                                scopeStartsAt,
                                                scopeEndsAt,
                                            )
                                        ) {
                                            return@EditUnavailableScreen
                                        }
                                        val idx =
                                            localUnavailable.indexOfFirst { it.matches(slot) }
                                        if (idx >= 0) {
                                            localUnavailable.removeAt(idx)
                                        } else {
                                            localUnavailable.add(slot)
                                        }
                                    },
                                    onBackClick = { currentScreen.value = "room_detail" },
                                    onSaveClick = {
                                        if (meetingState.mutating) return@EditUnavailableScreen
                                        val payload =
                                            AvailabilityConverter.toAvailablePayload(
                                                selectedIsoDates = dates,
                                                unavailable = localUnavailable.toList(),
                                                scopeStartsAt = scopeStartsAt,
                                                scopeEndsAt = scopeEndsAt,
                                            )
                                        meetingViewModel.submitAvailability(
                                            payload.ranges,
                                            allUnavailable = payload.allUnavailable,
                                        )
                                    },
                                )
                            }
                            "ai_result" -> {
                                val apiOptions =
                                    meetingState.candidates.mapIndexed { index, c ->
                                        RecommendationOption(
                                            rank =
                                                when (index) {
                                                    0 -> "1위 (최적 추천)"
                                                    else -> "${index + 1}위"
                                                },
                                            rankColor =
                                                when (index) {
                                                    0 -> Color(0xFFFFB300)
                                                    1 -> Color(0xFFB0BEC5)
                                                    else -> Color(0xFFA1887F)
                                                },
                                            timeText = TimeFmt.slotLabel(c.startsAt, c.endsAt),
                                            infoText =
                                                "${c.availableCount}명 가능 · 득표 ${c.voteCount}" +
                                                    if (c.memberNicknames.isNotEmpty()) {
                                                        "\n${c.memberNicknames.joinToString(", ")}"
                                                    } else {
                                                        ""
                                                    },
                                            fitRate = "${c.availableCount}",
                                            candidateId = c.id,
                                        )
                                    }
                                val voting = meetingState.candidatesStatus.equals("VOTING", ignoreCase = true)
                                AiResultScreen(
                                    meetingTitle =
                                        meetingState.activeMeeting?.title
                                            ?: detailAppointment.value?.title.orEmpty(),
                                    candidates = apiOptions,
                                    aiSummary = meetingState.aiSummary,
                                    multiSelectIds = meetingState.selectedCandidateIds,
                                    onToggleCandidateId =
                                        if (voting) {
                                            { id -> meetingViewModel.toggleCandidate(id) }
                                        } else {
                                            null
                                        },
                                    confirmLabel =
                                        when {
                                            voting -> "선택한 후보에 투표하기"
                                            apiOptions.size == 1 -> "결과 보기"
                                            apiOptions.isEmpty() -> "후보 없음"
                                            else -> "이 시간으로 최종 확정하기"
                                        },
                                    emptyMessage =
                                        when (meetingState.activeMeeting?.status?.uppercase()) {
                                            "COLLECTING" -> "아직 입력·조율이 끝나지 않았습니다."
                                            "FAILED" -> "조율 가능한 후보가 없습니다."
                                            else -> "아직 조율 후보가 없습니다."
                                        },
                                    isLoading = meetingState.mutating || meetingState.loading,
                                    onBackClick = { currentScreen.value = "room_detail" },
                                    onConfirmFinal = {
                                        when {
                                            voting -> meetingViewModel.submitVotes()
                                            meetingState.activeMeeting?.status.equals("CONFIRMED", true) -> {
                                                meetingViewModel.refreshResult()
                                                currentScreen.value = "result"
                                            }
                                            apiOptions.size == 1 -> {
                                                meetingViewModel.refreshResult()
                                                currentScreen.value = "result"
                                            }
                                            else -> {
                                                Toast
                                                    .makeText(
                                                        context,
                                                        "후보가 없거나 투표 중이 아닙니다.",
                                                        Toast.LENGTH_SHORT,
                                                    ).show()
                                            }
                                        }
                                    },
                                )
                            }
                            "friends" ->
                                FriendsScreen(
                                    isAdmin = false,
                                    onBackClick = { currentScreen.value = "home" },
                                )
                            "mypage" -> {
                                MyPageScreen(
                                    nickname =
                                        authState.nickname?.takeIf { it.isNotBlank() }
                                            ?: loggedInNickname.value.ifBlank { "사용자" },
                                    userId = loggedInId.value.ifBlank { "user@example.com" },
                                    onLogoutClick = { authViewModel.logout() },
                                    onNicknameChanged = { newNick ->
                                        authViewModel.updateNickname(newNick)
                                    },
                                    onBackClick = { currentScreen.value = "home" },
                                )
                            }
                            "result" -> {
                                val result = meetingState.result
                                val cand = result?.candidate
                                ResultScreen(
                                    title = meetingState.activeMeeting?.title ?: "확정된 모임",
                                    timeText =
                                        if (cand != null) {
                                            TimeFmt.slotLabel(cand.startsAt, cand.endsAt)
                                        } else {
                                            "결과 로딩 중…"
                                        },
                                    methodText =
                                        when (result?.method) {
                                            "AUTO" -> "자동 확정"
                                            "VOTE" -> "투표 확정"
                                            else -> result?.method ?: "-"
                                        },
                                    memberText =
                                        meetingState.activeMeeting?.members
                                            ?.joinToString(", ") { it.nickname }
                                            ?: "-",
                                    tieBroken = result?.tieBroken == true,
                                    onBackClick = { currentScreen.value = "home" },
                                    onHomeClick = {
                                        meetingViewModel.refreshList()
                                        currentScreen.value = "home"
                                    },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun MeetingDto.toAppointment(): Appointment =
    Appointment(
        id = id.hashCode().toLong(),
        title = title,
        category = status,
        duration = "-",
        location = if (legacy == true) "이전 앱 모임" else "Potato Meet",
        timeInfo = TimeFmt.rangeLabel(startsAt, endsAt),
        invitedFriends = members.map { it.nickname },
        meetingId = id,
        code = code,
        status = status,
        revision = revision,
        isOwner = members.any { it.id == myMemberId && it.role.equals("OWNER", true) },
        collectionId = collectionId,
        selectedDates = selectedDates,
    )

private fun Appointment.toMeetingStub(): MeetingDto =
    MeetingDto(
        id = meetingId,
        code = code,
        title = title,
        status = status,
        revision = revision,
        collectionId = collectionId,
    )
