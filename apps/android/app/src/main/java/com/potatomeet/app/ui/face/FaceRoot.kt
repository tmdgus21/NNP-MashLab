package com.potatomeet.app.ui.face

import android.app.Activity
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
import androidx.compose.runtime.mutableStateMapOf
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
import com.potatomeet.app.ui.face.components.CustomBottomBar
import com.potatomeet.app.ui.face.screens.AiRecommendationScreen
import com.potatomeet.app.ui.face.screens.CreateAppointmentStep1Screen
import com.potatomeet.app.ui.face.screens.CreateAppointmentStep2InviteScreen
import com.potatomeet.app.ui.face.screens.CreateAppointmentStep3TimeScreen
import com.potatomeet.app.ui.face.screens.CreateAppointmentStep4AdjustScreen
import com.potatomeet.app.ui.face.screens.FriendsScreen
import com.potatomeet.app.ui.face.screens.HomeScreen
import com.potatomeet.app.ui.face.screens.LoginScreen
import com.potatomeet.app.ui.face.screens.MyPageScreen
import com.potatomeet.app.ui.face.screens.ResultScreen
import com.potatomeet.app.ui.face.screens.SignUpScreen
import com.potatomeet.app.ui.feature.auth.AuthEvent
import com.potatomeet.app.ui.feature.auth.AuthViewModel
import com.potatomeet.app.ui.feature.meeting.MeetingEvent
import com.potatomeet.app.ui.feature.meeting.MeetingViewModel
import java.util.Calendar

/**
 * Face navigation graph with FastAPI auth + schedule coordination wired in.
 * Out-of-scope face screens (Friends, decorative create fields) kept as-is.
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

    val appointmentName = remember { mutableStateOf("") }
    val category = remember { mutableStateOf("") }
    val duration = remember { mutableStateOf("") }
    val location = remember { mutableStateOf("") }
    val roomNickname = remember { mutableStateOf("") }
    val startDate = remember { mutableStateOf("") }
    val endDate = remember { mutableStateOf("") }

    val createdTimeSlots = remember { mutableStateListOf<TimeSlot>() }
    val selectedFriendsForNew = remember { mutableStateMapOf<String, Boolean>() }
    val selectedAiRecommendationTime = remember { mutableStateOf("") }

    val currentCalendar = remember { Calendar.getInstance() }
    var sharedCalendarYear by remember { mutableStateOf(currentCalendar.get(Calendar.YEAR)) }
    var sharedCalendarMonth by remember { mutableStateOf(currentCalendar.get(Calendar.MONTH) + 1) }
    var sharedSelectedDay by remember { mutableStateOf(currentCalendar.get(Calendar.DAY_OF_MONTH)) }

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
                is MeetingEvent.Navigate -> currentScreen.value = event.route
            }
        }
    }

    LaunchedEffect(authState.isLoggedIn, authState.checkingSession) {
        if (authState.checkingSession) return@LaunchedEffect
        if (authState.isLoggedIn) {
            val email = authState.email.orEmpty()
            loggedInNickname.value =
                authState.nickname?.takeIf { it.isNotBlank() }
                    ?: email.substringBefore('@').ifBlank { "사용자" }
            loggedInId.value = email
            if (currentScreen.value == "login" || currentScreen.value == "signup") {
                currentScreen.value = "home"
            }
            meetingViewModel.refreshList()
            meetingViewModel.loadServerBounds()
            if (startDate.value.isBlank()) {
                val (s, e) = meetingViewModel.defaultDateRange()
                startDate.value = s
                endDate.value = e
            }
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
            "home", "friends", "mypage" -> activity?.finish()
            "create_step1" -> currentScreen.value = "home"
            "create_step2" -> currentScreen.value = "create_step1"
            "create_step3" -> currentScreen.value = "create_step2"
            "create_step4" -> currentScreen.value = "create_step3"
            "create_ai_recommendation" -> currentScreen.value = "create_step4"
            "result" -> currentScreen.value = "home"
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
                    "create_step1",
                    "create_step2",
                    "create_step3",
                    "create_step4",
                    "create_ai_recommendation",
                    "result",
                )
            -> {
                Scaffold(
                    containerColor = Color(0xFFFFFCF3),
                    bottomBar = {
                        if (currentScreen.value != "result") {
                            CustomBottomBar(
                                currentRoute = currentScreen.value,
                                onTabSelected = { route: String -> currentScreen.value = route },
                            )
                        }
                    },
                ) { innerPadding ->
                    Box(modifier = Modifier.padding(innerPadding).fillMaxSize()) {
                        when (currentScreen.value) {
                            "home" -> {
                                HomeScreen(
                                    nickname = loggedInNickname.value,
                                    appointmentsList = appointmentsList,
                                    calendarYear = sharedCalendarYear,
                                    onYearChange = { sharedCalendarYear = it },
                                    calendarMonth = sharedCalendarMonth,
                                    onMonthChange = { sharedCalendarMonth = it },
                                    selectedDay = sharedSelectedDay,
                                    onDayChange = { sharedSelectedDay = it },
                                    onLogoutClick = { authViewModel.logout() },
                                    onCreateAppointmentClick = {
                                        meetingViewModel.clearActive()
                                        createdTimeSlots.clear()
                                        selectedFriendsForNew.clear()
                                        currentScreen.value = "create_step1"
                                    },
                                    onDeleteAppointment = { appt ->
                                        if (appt.meetingId.isNotBlank()) {
                                            meetingViewModel.deleteMeeting(appt.toMeetingStub())
                                        }
                                    },
                                    onEditAppointmentToCreate = { appt ->
                                        appointmentName.value = appt.title
                                        category.value = appt.category
                                        duration.value = appt.duration
                                        location.value = appt.location
                                        currentScreen.value = "create_step1"
                                    },
                                    onOpenAppointment = { appt ->
                                        if (appt.meetingId.isNotBlank()) {
                                            meetingViewModel.openMeetingById(appt.meetingId)
                                        }
                                    },
                                    onJoinClick = { code, nick ->
                                        meetingViewModel.joinMeeting(code, nick)
                                    },
                                    isMutating = meetingState.mutating || meetingState.loading,
                                )
                            }
                            "friends" -> FriendsScreen(isAdmin = false)
                            "mypage" -> {
                                MyPageScreen(
                                    nickname = loggedInNickname.value.ifBlank { "사용자" },
                                    userId = loggedInId.value.ifBlank { "user@example.com" },
                                    onLogoutClick = { authViewModel.logout() },
                                    onNicknameChanged = { newNick -> loggedInNickname.value = newNick },
                                )
                            }
                            "create_step1" -> {
                                CreateAppointmentStep1Screen(
                                    appointmentName = appointmentName.value,
                                    onAppointmentNameChange = { appointmentName.value = it },
                                    category = category.value,
                                    onCategoryChange = { category.value = it },
                                    duration = duration.value,
                                    onDurationChange = { duration.value = it },
                                    location = location.value,
                                    onLocationChange = { location.value = it },
                                    nickname = roomNickname.value,
                                    onNicknameChange = { roomNickname.value = it },
                                    startDate = startDate.value,
                                    onStartDateChange = { startDate.value = it },
                                    endDate = endDate.value,
                                    onEndDateChange = { endDate.value = it },
                                    isLoading = meetingState.mutating,
                                    onBackClick = { currentScreen.value = "home" },
                                    onNextClick = {
                                        meetingViewModel.createMeeting(
                                            title = appointmentName.value,
                                            nickname = roomNickname.value.ifBlank { loggedInNickname.value },
                                            startDate = startDate.value,
                                            endDate = endDate.value,
                                        )
                                    },
                                    onStepClick = { step -> currentScreen.value = step },
                                )
                            }
                            "create_step2" -> {
                                CreateAppointmentStep2InviteScreen(
                                    isAdmin = false,
                                    selectedFriendsMap = selectedFriendsForNew,
                                    inviteCode = meetingState.inviteCode ?: meetingState.activeMeeting?.code,
                                    onBackClick = { currentScreen.value = "create_step1" },
                                    onNextClick = {
                                        meetingState.activeMeeting?.id?.let {
                                            meetingViewModel.refreshCollection(it)
                                        }
                                        currentScreen.value = "create_step3"
                                    },
                                    onStepClick = { step -> currentScreen.value = step },
                                )
                            }
                            "create_step3" -> {
                                CreateAppointmentStep3TimeScreen(
                                    timeSlotsList = createdTimeSlots,
                                    appointmentsList = appointmentsList,
                                    onAddTimeSlot = { slot ->
                                        createdTimeSlots.add(slot)
                                        val merged = mergeTimeSlots(createdTimeSlots)
                                        createdTimeSlots.clear()
                                        createdTimeSlots.addAll(merged)
                                    },
                                    onDeleteTimeSlot = { slot -> createdTimeSlots.remove(slot) },
                                    calendarYear = sharedCalendarYear,
                                    onYearChange = { sharedCalendarYear = it },
                                    calendarMonth = sharedCalendarMonth,
                                    onMonthChange = { sharedCalendarMonth = it },
                                    selectedCalendarDay = sharedSelectedDay,
                                    onDayChange = { sharedSelectedDay = it },
                                    onBackClick = { currentScreen.value = "create_step2" },
                                    onStepClick = { step -> currentScreen.value = step },
                                    onNextClick = { inputSlot ->
                                        if (inputSlot != null) createdTimeSlots.add(inputSlot)
                                        val merged = mergeTimeSlots(createdTimeSlots)
                                        createdTimeSlots.clear()
                                        createdTimeSlots.addAll(merged)
                                        val ranges =
                                            createdTimeSlots.map { slot ->
                                                TimeFmt.seoulInstant(
                                                    sharedCalendarYear,
                                                    slot.month,
                                                    slot.day,
                                                    slot.startHour,
                                                    slot.startMin,
                                                ) to
                                                    TimeFmt.seoulInstant(
                                                        sharedCalendarYear,
                                                        slot.month,
                                                        slot.day,
                                                        slot.endHour,
                                                        slot.endMin,
                                                    )
                                            }
                                        if (meetingState.activeMeeting != null) {
                                            meetingViewModel.submitAvailability(ranges)
                                        } else {
                                            currentScreen.value = "create_step4"
                                        }
                                    },
                                )
                            }
                            "create_step4" -> {
                                CreateAppointmentStep4AdjustScreen(
                                    myNickname =
                                        roomNickname.value.ifBlank {
                                            loggedInNickname.value.ifBlank { "나" }
                                        },
                                    invitedFriends =
                                        meetingState.activeMeeting?.members
                                            ?.map { it.nickname }
                                            ?.filter { it != roomNickname.value }
                                            ?: selectedFriendsForNew.filter { it.value }.keys.toList(),
                                    myTimeSlots = createdTimeSlots,
                                    onBackClick = { currentScreen.value = "create_step3" },
                                    onStepClick = { step -> currentScreen.value = step },
                                    onAiAdjustClick = { chosenTime ->
                                        selectedAiRecommendationTime.value = chosenTime
                                        meetingState.activeMeeting?.id?.let {
                                            meetingViewModel.refreshCandidates(it)
                                        }
                                        currentScreen.value = "create_ai_recommendation"
                                    },
                                )
                            }
                            "create_ai_recommendation" -> {
                                val apiOptions =
                                    meetingState.candidates.mapIndexed { index, c ->
                                        RecommendationOption(
                                            rank = "${index + 1}위",
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
                                AiRecommendationScreen(
                                    myTimeSlots = createdTimeSlots,
                                    invitedFriends =
                                        meetingState.activeMeeting?.members?.map { it.nickname }.orEmpty(),
                                    apiRecommendations = apiOptions.takeIf { it.isNotEmpty() },
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
                                            else -> "이 시간으로 확정하기"
                                        },
                                    isLoading = meetingState.mutating,
                                    onBackClick = { currentScreen.value = "create_step4" },
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
                                                selectedAiRecommendationTime.value = it
                                                currentScreen.value = "home"
                                            }
                                        }
                                    },
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
