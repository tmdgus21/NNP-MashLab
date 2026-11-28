package com.example.potatomeet

import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.potatomeet.ui.theme.PotatoMeetTheme
import java.util.Calendar

data class UserAccount(
    var nickname: String,
    val id: String,
    val pw: String,
    val twoFactorCode: String,
    var profileImageUri: Uri? = null
)

data class FriendItem(
    val id: Long = System.currentTimeMillis() + (0..10000).random(),
    val name: String,
    val isFavorite: Boolean = false
)

data class UnavailableTimeSlot(
    val id: Long = System.currentTimeMillis() + (0..10000).random(),
    var dateStr: String,
    var startHour: Int,
    var startMin: Int,
    var endHour: Int,
    var endMin: Int,
    val isPreset: Boolean = false
) {
    fun toFormattedString(): String {
        val sH = String.format("%02d", startHour)
        val sM = String.format("%02d", startMin)
        val eH = String.format("%02d", endHour)
        val eM = String.format("%02d", endMin)
        return "$dateStr   ${sH}:${sM} ~ ${eH}:${eM}"
    }
}

data class AiCandidateSlot(
    val id: Int,
    val rankLabel: String,
    val timeStr: String,
    val availableCount: Int,
    val totalCount: Int,
    val voterNames: List<String> = emptyList()
) {
    fun toAvailabilitySummary(): String {
        val needCoordCount = (totalCount - availableCount).coerceAtLeast(0)
        return if (availableCount >= totalCount && totalCount > 0) {
            "모든 참여자(${totalCount})명 참여가능"
        } else {
            "참여자 ${availableCount}명 참여가능, ${needCoordCount}명 조율 필요"
        }
    }
}

data class RoomModel(
    val id: Long = System.currentTimeMillis(),
    val title: String,
    val description: String,
    val selectedDates: List<String>,
    val hostName: String,
    val ownerId: String = "admin",
    val participants: List<String> = listOf("관리자"),
    val unavailableSlots: List<UnavailableTimeSlot> = emptyList(),
    val aiCandidates: List<AiCandidateSlot> = emptyList(),
    val invitedCount: Int = 0,
    val isConfirmed: Boolean = false,
    val finalAiTime: String = ""
)

private data class HelpItem(
    val title: String,
    val body: String
)

private data class TimeRangePage(
    val startHour: Int,
    val endHour: Int,
    val label: String
)

@Composable
private fun appTextFieldColors(): TextFieldColors {
    return OutlinedTextFieldDefaults.colors(
        focusedTextColor = Color.Black,
        unfocusedTextColor = Color.Black,
        disabledTextColor = Color.Black,
        cursorColor = Color(0xFFFF8F00),
        focusedContainerColor = Color.White,
        unfocusedContainerColor = Color.White,
        disabledContainerColor = Color.White,
        focusedBorderColor = Color(0xFFFF9800),
        unfocusedBorderColor = Color(0xFFE0E0E0)
    )
}

@Composable
private fun GoogleBrandBadge(
    size: Dp = 22.dp,
    fontSize: TextUnit = 14.sp
) {
    Box(
        modifier = Modifier
            .size(size)
            .clip(CircleShape)
            .background(Color.White)
            .border(1.dp, Color(0xFFE0E0E0), CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = buildAnnotatedString {
                withStyle(SpanStyle(color = Color(0xFF4285F4), fontWeight = FontWeight.ExtraBold)) { append("G") }
            },
            fontSize = fontSize,
            lineHeight = fontSize
        )
    }
}

@Composable
private fun ImageStyleSwitch(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    enabled: Boolean = true
) {
    val trackWidth = 54.dp
    val trackHeight = 30.dp
    val thumbSize = 24.dp
    val horizontalPadding = 3.dp

    val thumbOffset by animateDpAsState(
        targetValue = if (checked) trackWidth - thumbSize - horizontalPadding else horizontalPadding,
        label = "switchThumbOffset"
    )
    val trackColor by animateColorAsState(
        targetValue = when {
            !enabled -> Color(0xFFE2E6EC)
            checked -> Color(0xFFFFD54F)
            else -> Color(0xFFC8D0DC)
        },
        label = "switchTrackColor"
    )

    Box(
        modifier = Modifier
            .width(trackWidth)
            .height(trackHeight)
            .clip(CircleShape)
            .background(trackColor)
            .clickable(enabled = enabled) { onCheckedChange(!checked) },
        contentAlignment = Alignment.CenterStart
    ) {
        Box(
            modifier = Modifier
                .offset(x = thumbOffset)
                .size(thumbSize)
                .shadow(elevation = 2.dp, shape = CircleShape, clip = false)
                .clip(CircleShape)
                .background(if (enabled) Color.White else Color(0xFFF5F6F8))
        )
    }
}

private fun buildDefaultAiCandidates(
    selectedDates: List<String>,
    participants: List<String>
): List<AiCandidateSlot> {
    val total = participants.size.coerceAtLeast(1)
    val d1 = selectedDates.firstOrNull() ?: "11.14(토)"
    val d2 = selectedDates.getOrNull(1) ?: "11.18(수)"
    val d3 = selectedDates.getOrNull(2) ?: "11.22(일)"

    return listOf(
        AiCandidateSlot(
            id = 0,
            rankLabel = "1위 (최적 추천)",
            timeStr = "$d1 19:00 ~ 20:30",
            availableCount = total,
            totalCount = total
        ),
        AiCandidateSlot(
            id = 1,
            rankLabel = "2위",
            timeStr = "$d2 18:30 ~ 20:00",
            availableCount = (total - 1).coerceAtLeast(1),
            totalCount = total
        ),
        AiCandidateSlot(
            id = 2,
            rankLabel = "3위",
            timeStr = "$d3 20:00 ~ 21:30",
            availableCount = (total - 2).coerceAtLeast(1),
            totalCount = total
        )
    )
}

private fun parseMonthDayFromTimeStr(timeStr: String): Pair<Int, Int>? {
    val trimmed = timeStr.trim()
    val dotIndex = trimmed.indexOf('.')
    if (dotIndex <= 0) return null
    val month = trimmed.substring(0, dotIndex).toIntOrNull() ?: return null
    val afterDot = trimmed.substring(dotIndex + 1)
    val dayDigits = afterDot.takeWhile { it.isDigit() }
    val day = dayDigits.toIntOrNull() ?: return null
    return month to day
}

private fun buildPresetUnavailableSlots(dates: List<String>): List<UnavailableTimeSlot> {
    val targetDates = dates.ifEmpty { listOf("11.14(토)") }
    return targetDates.flatMap { dateStr ->
        listOf(
            UnavailableTimeSlot(dateStr = dateStr, startHour = 0, startMin = 0, endHour = 0, endMin = 30, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 0, startMin = 30, endHour = 1, endMin = 0, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 1, startMin = 0, endHour = 1, endMin = 30, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 1, startMin = 30, endHour = 2, endMin = 0, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 2, startMin = 0, endHour = 2, endMin = 30, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 2, startMin = 30, endHour = 3, endMin = 0, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 3, startMin = 0, endHour = 3, endMin = 30, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 3, startMin = 30, endHour = 4, endMin = 0, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 4, startMin = 0, endHour = 4, endMin = 30, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 4, startMin = 30, endHour = 5, endMin = 0, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 5, startMin = 0, endHour = 5, endMin = 30, isPreset = true),
            UnavailableTimeSlot(dateStr = dateStr, startHour = 5, startMin = 30, endHour = 6, endMin = 0, isPreset = true)
        )
    }
}

private fun applyPresetToRoomSlots(
    currentSlots: List<UnavailableTimeSlot>,
    selectedDates: List<String>,
    enabled: Boolean
): List<UnavailableTimeSlot> {
    val withoutPreset = currentSlots.filterNot { it.isPreset }
    if (!enabled) {
        return withoutPreset
    }
    val presetSlots = buildPresetUnavailableSlots(selectedDates).filter { preset ->
        withoutPreset.none { userSlot ->
            userSlot.dateStr == preset.dateStr &&
                    userSlot.startHour == preset.startHour &&
                    userSlot.startMin == preset.startMin
        }
    }
    return withoutPreset + presetSlots
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PotatoMeetTheme {
                val currentScreen = remember { mutableStateOf("login") }

                val adminAccount = remember {
                    UserAccount(
                        nickname = "관리자",
                        id = "admin",
                        pw = "admin!@#",
                        twoFactorCode = ""
                    )
                }

                val registeredAccounts = remember { mutableStateListOf<UserAccount>() }
                val loggedInNickname = remember { mutableStateOf("") }
                val loggedInId = remember { mutableStateOf("") }
                var loggedInProfileUri by remember { mutableStateOf<Uri?>(null) }

                val friendsList = remember { mutableStateListOf<FriendItem>() }

                var allNotificationsEnabled by remember { mutableStateOf(true) }
                val dateAlarmStates = remember { mutableStateMapOf<Long, Boolean>() }

                var timeUnitMinutes by remember { mutableIntStateOf(30) }
                var defaultUnavailablePresetEnabled by remember { mutableStateOf(false) }
                var selectAvailableModeEnabled by remember { mutableStateOf(false) }

                var showHomeCalendarEnabled by remember { mutableStateOf(false) }

                val roomTitleInput = remember { mutableStateOf("") }
                val roomDescInput = remember { mutableStateOf("") }
                val selectedDatesList = remember { mutableStateListOf<String>() }

                val roomsList = remember { mutableStateListOf<RoomModel>() }
                var currentRoomId by remember { mutableStateOf<Long?>(null) }

                val currentRoom = roomsList.find { it.id == currentRoomId }

                fun updateRoom(transform: (RoomModel) -> RoomModel) {
                    val idx = roomsList.indexOfFirst { it.id == currentRoomId }
                    if (idx != -1) {
                        roomsList[idx] = transform(roomsList[idx])
                    }
                }

                BackHandler(enabled = currentScreen.value != "login") {
                    when (currentScreen.value) {
                        "signup" -> currentScreen.value = "login"
                        "home", "friends" -> finish()
                        "mypage" -> currentScreen.value = "home"
                        "my_rooms", "notification_settings", "coordination_settings", "app_settings", "help", "manage_friends" -> currentScreen.value = "mypage"
                        "create_room" -> currentScreen.value = "home"
                        "room_detail" -> currentScreen.value = "home"
                        "edit_unavailable" -> currentScreen.value = "room_detail"
                        "ai_result" -> currentScreen.value = "room_detail"
                    }
                }

                Surface(
                    modifier = Modifier.fillMaxSize().imePadding(),
                    color = Color(0xFFFFFCF3)
                ) {
                    when (currentScreen.value) {
                        "login" -> {
                            LoginScreen(
                                adminAccount = adminAccount,
                                registeredAccounts = registeredAccounts,
                                onLoginSuccess = { nickname: String, id: String ->
                                    loggedInNickname.value = nickname
                                    loggedInId.value = id
                                    loggedInProfileUri = if (id == adminAccount.id) {
                                        adminAccount.profileImageUri
                                    } else {
                                        registeredAccounts.find { it.id == id }?.profileImageUri
                                    }
                                    currentScreen.value = "home"
                                },
                                onSignUpClick = { currentScreen.value = "signup" }
                            )
                        }
                        "signup" -> {
                            SignUpScreen(
                                existingAccounts = registeredAccounts,
                                onCompleteClick = { newAccount: UserAccount ->
                                    registeredAccounts.add(newAccount)
                                    currentScreen.value = "login"
                                },
                                onBackClick = { currentScreen.value = "login" }
                            )
                        }
                        "home", "friends", "mypage", "my_rooms", "notification_settings", "coordination_settings", "app_settings", "help", "manage_friends", "create_room", "room_detail", "edit_unavailable", "ai_result" -> {
                            val isAdmin = loggedInId.value == "admin"
                            val visibleRooms = if (isAdmin) {
                                roomsList
                            } else {
                                roomsList.filter { it.ownerId == loggedInId.value }
                            }

                            Box(modifier = Modifier.fillMaxSize()) {
                                when (currentScreen.value) {
                                    "home" -> {
                                        HomeScreen(
                                            nickname = loggedInNickname.value,
                                            roomsList = visibleRooms,
                                            showCalendar = showHomeCalendarEnabled,
                                            onCreateRoomClick = {
                                                roomTitleInput.value = ""
                                                roomDescInput.value = ""
                                                selectedDatesList.clear()
                                                currentScreen.value = "create_room"
                                            },
                                            onRoomClick = { room ->
                                                currentRoomId = room.id
                                                currentScreen.value = "room_detail"
                                            },
                                            onMyPageClick = { currentScreen.value = "mypage" }
                                        )
                                    }
                                    "friends" -> {
                                        FriendsScreen(
                                            friendsList = friendsList,
                                            onBackClick = { currentScreen.value = "home" }
                                        )
                                    }
                                    "manage_friends" -> {
                                        FriendsManagementScreen(
                                            friendsList = friendsList,
                                            onBackClick = { currentScreen.value = "mypage" }
                                        )
                                    }
                                    "mypage" -> {
                                        MyPageScreen(
                                            nickname = loggedInNickname.value.ifBlank { "사용자" },
                                            userId = loggedInId.value.ifBlank { "user" },
                                            profileImageUri = loggedInProfileUri,
                                            onProfileImageChanged = { newUri ->
                                                loggedInProfileUri = newUri
                                                if (loggedInId.value == adminAccount.id) {
                                                    adminAccount.profileImageUri = newUri
                                                } else {
                                                    registeredAccounts.find { it.id == loggedInId.value }?.profileImageUri = newUri
                                                }
                                            },
                                            onLogoutClick = {
                                                loggedInNickname.value = ""
                                                loggedInId.value = ""
                                                loggedInProfileUri = null
                                                currentScreen.value = "login"
                                            },
                                            onNicknameChanged = { newNick ->
                                                loggedInNickname.value = newNick
                                                if (loggedInId.value == adminAccount.id) {
                                                    adminAccount.nickname = newNick
                                                } else {
                                                    registeredAccounts.find { it.id == loggedInId.value }?.nickname = newNick
                                                }
                                            },
                                            onMyRoomsClick = { currentScreen.value = "my_rooms" },
                                            onNotificationSettingsClick = { currentScreen.value = "notification_settings" },
                                            onCoordinationSettingsClick = { currentScreen.value = "coordination_settings" },
                                            onFriendsManagementClick = { currentScreen.value = "manage_friends" },
                                            onAppSettingsClick = { currentScreen.value = "app_settings" },
                                            onHelpClick = { currentScreen.value = "help" },
                                            onBackClick = { currentScreen.value = "home" }
                                        )
                                    }
                                    "help" -> {
                                        HelpScreen(
                                            onBackClick = { currentScreen.value = "mypage" }
                                        )
                                    }
                                    "app_settings" -> {
                                        AppSettingsScreen(
                                            showHomeCalendarEnabled = showHomeCalendarEnabled,
                                            onToggleShowHomeCalendar = { showHomeCalendarEnabled = it },
                                            onBackClick = { currentScreen.value = "mypage" }
                                        )
                                    }
                                    "coordination_settings" -> {
                                        CoordinationSettingsScreen(
                                            timeUnitMinutes = timeUnitMinutes,
                                            onSelectTimeUnit = { timeUnitMinutes = it },
                                            defaultUnavailablePresetEnabled = defaultUnavailablePresetEnabled,
                                            onToggleDefaultUnavailablePreset = { enabled ->
                                                defaultUnavailablePresetEnabled = enabled
                                                roomsList.forEachIndexed { idx, room ->
                                                    roomsList[idx] = room.copy(
                                                        unavailableSlots = applyPresetToRoomSlots(
                                                            currentSlots = room.unavailableSlots,
                                                            selectedDates = room.selectedDates,
                                                            enabled = enabled
                                                        )
                                                    )
                                                }
                                            },
                                            selectAvailableModeEnabled = selectAvailableModeEnabled,
                                            onToggleSelectAvailableMode = { selectAvailableModeEnabled = it },
                                            onBackClick = { currentScreen.value = "mypage" }
                                        )
                                    }
                                    "notification_settings" -> {
                                        val confirmedRooms = visibleRooms.filter { it.isConfirmed }
                                        NotificationSettingsScreen(
                                            allNotificationsEnabled = allNotificationsEnabled,
                                            onToggleAllNotifications = { enabled ->
                                                allNotificationsEnabled = enabled
                                            },
                                            confirmedRooms = confirmedRooms,
                                            dateAlarmStates = dateAlarmStates,
                                            onToggleRoomAlarm = { roomId, enabled ->
                                                dateAlarmStates[roomId] = enabled
                                            },
                                            onBackClick = { currentScreen.value = "mypage" }
                                        )
                                    }
                                    "my_rooms" -> {
                                        MyRoomsScreen(
                                            roomsList = visibleRooms,
                                            onRoomClick = { room ->
                                                currentRoomId = room.id
                                                currentScreen.value = "room_detail"
                                            },
                                            onBackClick = { currentScreen.value = "mypage" }
                                        )
                                    }
                                    "create_room" -> {
                                        CreateRoomScreen(
                                            roomTitle = roomTitleInput.value,
                                            onRoomTitleChange = { roomTitleInput.value = it },
                                            roomDesc = roomDescInput.value,
                                            onRoomDescChange = { roomDescInput.value = it },
                                            selectedDates = selectedDatesList,
                                            onBackClick = { currentScreen.value = "home" },
                                            onCreateComplete = {
                                                val dates = selectedDatesList.toList()
                                                val members = listOf(loggedInNickname.value)
                                                val initialSlots = if (defaultUnavailablePresetEnabled) {
                                                    buildPresetUnavailableSlots(dates)
                                                } else {
                                                    emptyList()
                                                }
                                                val newRoom = RoomModel(
                                                    title = roomTitleInput.value.ifBlank { "새로운 모임" },
                                                    description = roomDescInput.value.ifBlank { loggedInNickname.value },
                                                    selectedDates = dates,
                                                    hostName = loggedInNickname.value,
                                                    ownerId = loggedInId.value,
                                                    participants = members,
                                                    unavailableSlots = initialSlots,
                                                    aiCandidates = buildDefaultAiCandidates(dates, members)
                                                )
                                                roomsList.add(newRoom)
                                                currentRoomId = newRoom.id
                                                currentScreen.value = "room_detail"
                                            }
                                        )
                                    }
                                    "room_detail" -> {
                                        currentRoom?.let { room ->
                                            RoomDetailScreen(
                                                room = room,
                                                timeUnitMinutes = timeUnitMinutes,
                                                selectAvailableModeEnabled = selectAvailableModeEnabled,
                                                onBackClick = { currentScreen.value = "home" },
                                                onEditUnavailableClick = {
                                                    currentScreen.value = "edit_unavailable"
                                                },
                                                onAiResultClick = {
                                                    if (room.aiCandidates.isEmpty()) {
                                                        updateRoom { target ->
                                                            target.copy(
                                                                aiCandidates = buildDefaultAiCandidates(
                                                                    target.selectedDates,
                                                                    target.participants
                                                                )
                                                            )
                                                        }
                                                    }
                                                    currentScreen.value = "ai_result"
                                                },
                                                onInviteKakao = { }
                                            )
                                        }
                                    }
                                    "edit_unavailable" -> {
                                        currentRoom?.let { room ->
                                            EditUnavailableScreen(
                                                room = room,
                                                timeUnitMinutes = timeUnitMinutes,
                                                selectAvailableModeEnabled = selectAvailableModeEnabled,
                                                onToggleSlot = { dateStr, hour, startMin ->
                                                    updateRoom { target ->
                                                        if (timeUnitMinutes == 60) {
                                                            val firstExists = target.unavailableSlots.any {
                                                                it.dateStr == dateStr && it.startHour == hour && it.startMin == 0
                                                            }
                                                            val secondExists = target.unavailableSlots.any {
                                                                it.dateStr == dateStr && it.startHour == hour && it.startMin == 30
                                                            }
                                                            val bothUnavailable = firstExists && secondExists
                                                            val filtered = target.unavailableSlots.filterNot {
                                                                it.dateStr == dateStr && it.startHour == hour
                                                            }
                                                            val updated = if (bothUnavailable) {
                                                                filtered
                                                            } else {
                                                                filtered + listOf(
                                                                    UnavailableTimeSlot(
                                                                        dateStr = dateStr,
                                                                        startHour = hour,
                                                                        startMin = 0,
                                                                        endHour = hour,
                                                                        endMin = 30,
                                                                        isPreset = false
                                                                    ),
                                                                    UnavailableTimeSlot(
                                                                        dateStr = dateStr,
                                                                        startHour = hour,
                                                                        startMin = 30,
                                                                        endHour = hour + 1,
                                                                        endMin = 0,
                                                                        isPreset = false
                                                                    )
                                                                )
                                                            }
                                                            target.copy(unavailableSlots = updated)
                                                        } else {
                                                            val exists = target.unavailableSlots.any {
                                                                it.dateStr == dateStr && it.startHour == hour && it.startMin == startMin
                                                            }
                                                            val updated = if (exists) {
                                                                target.unavailableSlots.filterNot {
                                                                    it.dateStr == dateStr && it.startHour == hour && it.startMin == startMin
                                                                }
                                                            } else {
                                                                val endHour = if (startMin == 30) hour + 1 else hour
                                                                val endMin = if (startMin == 30) 0 else 30
                                                                target.unavailableSlots + UnavailableTimeSlot(
                                                                    dateStr = dateStr,
                                                                    startHour = hour,
                                                                    startMin = startMin,
                                                                    endHour = endHour,
                                                                    endMin = endMin,
                                                                    isPreset = false
                                                                )
                                                            }
                                                            target.copy(unavailableSlots = updated)
                                                        }
                                                    }
                                                },
                                                onClearDateSlots = { dateStr ->
                                                    updateRoom { target ->
                                                        target.copy(
                                                            unavailableSlots = target.unavailableSlots.filterNot { it.dateStr == dateStr }
                                                        )
                                                    }
                                                },
                                                onBackClick = { currentScreen.value = "room_detail" },
                                                onSaveComplete = {
                                                    currentScreen.value = "room_detail"
                                                }
                                            )
                                        }
                                    }
                                    "ai_result" -> {
                                        currentRoom?.let { room ->
                                            val candidates = room.aiCandidates.ifEmpty {
                                                buildDefaultAiCandidates(room.selectedDates, room.participants)
                                            }
                                            AiResultScreen(
                                                room = room,
                                                candidates = candidates,
                                                voterName = loggedInNickname.value.ifBlank { "참여자" },
                                                onToggleVote = { candidateId, voter ->
                                                    updateRoom { target ->
                                                        val baseList = target.aiCandidates.ifEmpty {
                                                            buildDefaultAiCandidates(target.selectedDates, target.participants)
                                                        }
                                                        val updatedCandidates = baseList.map { item ->
                                                            if (item.id == candidateId) {
                                                                val nextVoters = if (item.voterNames.contains(voter)) {
                                                                    item.voterNames - voter
                                                                } else {
                                                                    item.voterNames + voter
                                                                }
                                                                item.copy(voterNames = nextVoters)
                                                            } else {
                                                                item
                                                            }
                                                        }
                                                        target.copy(aiCandidates = updatedCandidates)
                                                    }
                                                },
                                                onBackClick = { currentScreen.value = "room_detail" },
                                                onConfirmFinal = { finalTime ->
                                                    updateRoom { it.copy(isConfirmed = true, finalAiTime = finalTime) }
                                                    currentScreen.value = "home"
                                                }
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun LoginScreen(
    adminAccount: UserAccount,
    registeredAccounts: List<UserAccount>,
    onLoginSuccess: (String, String) -> Unit,
    onSignUpClick: () -> Unit
) {
    var inputId by remember { mutableStateOf("") }
    var inputPw by remember { mutableStateOf("") }
    var input2Fa by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }
    val context = LocalContext.current

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 30.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = buildAnnotatedString {
                withStyle(SpanStyle(color = Color(0xFF4A3B32), fontWeight = FontWeight.ExtraBold)) { append("potato ") }
                withStyle(SpanStyle(color = Color(0xFFFF9800), fontWeight = FontWeight.ExtraBold)) { append("meet") }
            },
            fontSize = 32.sp
        )
        Spacer(modifier = Modifier.height(6.dp))
        Text(text = "함께하는 일정, 더 쉬운 약속", fontSize = 14.sp, color = Color(0xFF666666))
        Spacer(modifier = Modifier.height(28.dp))

        OutlinedTextField(
            value = inputId,
            onValueChange = { inputId = it; errorMessage = "" },
            placeholder = { Text("아이디 입력", color = Color(0xFF9E9E9E)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = appTextFieldColors()
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = inputPw,
            onValueChange = { inputPw = it; errorMessage = "" },
            placeholder = { Text("비밀번호 입력", color = Color(0xFF9E9E9E)) },
            singleLine = true,
            visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                Text(
                    text = if (passwordVisible) "숨김" else "표시",
                    fontSize = 12.sp,
                    color = Color.DarkGray,
                    modifier = Modifier.clickable { passwordVisible = !passwordVisible }.padding(8.dp)
                )
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = appTextFieldColors()
        )
        Spacer(modifier = Modifier.height(10.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Button(
                onClick = {
                    if (inputId == adminAccount.id) {
                        Toast.makeText(context, "관리자 계정은 인증코드가 필요 없습니다.", Toast.LENGTH_SHORT).show()
                    } else {
                        val targetUser = registeredAccounts.find { it.id == inputId }
                        val codeToGuide = targetUser?.twoFactorCode ?: "가입 정보 없음"
                        Toast.makeText(context, "회원가입 당시의 인증코드: $codeToGuide", Toast.LENGTH_LONG).show()
                    }
                },
                modifier = Modifier.weight(0.82f).height(50.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(25.dp),
                contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    GoogleBrandBadge(size = 22.dp, fontSize = 14.sp)
                    Text(
                        text = "인증코드 확인",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF3C1E1E),
                        maxLines = 1,
                        softWrap = false
                    )
                }
            }

            OutlinedTextField(
                value = input2Fa,
                onValueChange = { input2Fa = it; errorMessage = "" },
                placeholder = { Text("인증코드 입력", color = Color(0xFF9E9E9E)) },
                singleLine = true,
                modifier = Modifier.weight(1.28f).height(52.dp),
                shape = RoundedCornerShape(26.dp),
                colors = appTextFieldColors()
            )
        }

        if (errorMessage.isNotEmpty()) {
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = errorMessage,
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFFD32F2F),
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth()
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Button(
            onClick = {
                when {
                    inputId.isBlank() -> { errorMessage = "아이디를 입력하지 않았습니다." }
                    inputPw.isBlank() -> { errorMessage = "비밀번호를 입력하지 않았습니다." }
                    inputId == adminAccount.id && inputPw == adminAccount.pw -> {
                        errorMessage = ""
                        onLoginSuccess(adminAccount.nickname, adminAccount.id)
                    }
                    else -> {
                        if (input2Fa.isBlank()) {
                            errorMessage = "인증코드를 입력하지 않았습니다."
                        } else {
                            val matchedUser = registeredAccounts.find { it.id == inputId && it.pw == inputPw }
                            if (matchedUser != null) {
                                if (input2Fa == matchedUser.twoFactorCode) {
                                    errorMessage = ""
                                    onLoginSuccess(matchedUser.nickname, matchedUser.id)
                                } else {
                                    errorMessage = "인증코드가 일치하지 않습니다. (가입 시 설정한 인증코드 입력)"
                                }
                            } else {
                                errorMessage = "회원가입이 되지 않았거나 아이디/비밀번호가 일치하지 않습니다."
                            }
                        }
                    }
                }
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4A3B32)),
            shape = RoundedCornerShape(26.dp)
        ) {
            Text(text = "로그인하기", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color.White)
        }

        Spacer(modifier = Modifier.height(20.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(text = "계정이 없으신가요?", fontSize = 14.sp, color = Color(0xFF888888))
            Spacer(modifier = Modifier.width(6.dp))
            TextButton(onClick = onSignUpClick, contentPadding = PaddingValues(0.dp)) {
                Text(text = "회원가입", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFB300))
            }
        }
    }
}

@Composable
fun SignUpScreen(
    existingAccounts: List<UserAccount>,
    onCompleteClick: (UserAccount) -> Unit,
    onBackClick: () -> Unit
) {
    var nickname by remember { mutableStateOf("") }
    var id by remember { mutableStateOf("") }
    var pw by remember { mutableStateOf("") }
    var pwConfirm by remember { mutableStateOf("") }
    var twoFactorCode by remember { mutableStateOf("") }

    var pwVisible by remember { mutableStateOf(false) }
    var pwConfirmVisible by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }
    val context = LocalContext.current

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 30.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(text = "회원가입", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
        Spacer(modifier = Modifier.height(24.dp))

        OutlinedTextField(
            value = nickname,
            onValueChange = { nickname = it; errorMessage = "" },
            placeholder = { Text("사용할 닉네임", color = Color(0xFF9E9E9E)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = appTextFieldColors()
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = id,
            onValueChange = { id = it; errorMessage = "" },
            placeholder = { Text("아이디", color = Color(0xFF9E9E9E)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = appTextFieldColors()
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = pw,
            onValueChange = { pw = it; errorMessage = "" },
            placeholder = { Text("비밀번호", color = Color(0xFF9E9E9E)) },
            singleLine = true,
            visualTransformation = if (pwVisible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                Text(
                    text = if (pwVisible) "숨김" else "표시",
                    fontSize = 12.sp,
                    color = Color.DarkGray,
                    modifier = Modifier.clickable { pwVisible = !pwVisible }.padding(8.dp)
                )
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = appTextFieldColors()
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = pwConfirm,
            onValueChange = { pwConfirm = it; errorMessage = "" },
            placeholder = { Text("비밀번호 확인", color = Color(0xFF9E9E9E)) },
            singleLine = true,
            visualTransformation = if (pwConfirmVisible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                Text(
                    text = if (pwConfirmVisible) "숨김" else "표시",
                    fontSize = 12.sp,
                    color = Color.DarkGray,
                    modifier = Modifier.clickable { pwConfirmVisible = !pwConfirmVisible }.padding(8.dp)
                )
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = appTextFieldColors()
        )
        Spacer(modifier = Modifier.height(10.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Button(
                onClick = {
                    twoFactorCode = "123456"
                    Toast.makeText(context, "인증코드가 발송되었습니다 (코드: 123456)", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier.weight(0.82f).height(50.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(25.dp),
                contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp)
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    GoogleBrandBadge(size = 22.dp, fontSize = 14.sp)
                    Text(
                        text = "인증코드 보내기",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF3C1E1E),
                        maxLines = 1,
                        softWrap = false
                    )
                }
            }

            OutlinedTextField(
                value = twoFactorCode,
                onValueChange = { twoFactorCode = it; errorMessage = "" },
                placeholder = { Text("인증코드 입력", color = Color(0xFF9E9E9E)) },
                singleLine = true,
                modifier = Modifier.weight(1.28f).height(52.dp),
                shape = RoundedCornerShape(26.dp),
                colors = appTextFieldColors()
            )
        }

        if (errorMessage.isNotEmpty()) {
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = errorMessage,
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFFD32F2F),
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth()
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Button(
            onClick = {
                when {
                    nickname.isBlank() -> errorMessage = "사용할 닉네임을 입력하지 않았습니다."
                    id.isBlank() -> errorMessage = "아이디를 입력하지 않았습니다."
                    pw.isBlank() -> errorMessage = "비밀번호를 입력하지 않았습니다."
                    pwConfirm.isBlank() -> errorMessage = "비밀번호 확인을 입력하지 않았습니다."
                    pw != pwConfirm -> errorMessage = "비밀번호가 일치하지 않습니다."
                    twoFactorCode.isBlank() -> errorMessage = "인증코드를 입력하지 않았습니다."
                    id == "admin" || existingAccounts.any { it.id == id } -> errorMessage = "이미 사용 중인 아이디입니다."
                    else -> {
                        Toast.makeText(context, "회원가입이 완료되었습니다.", Toast.LENGTH_SHORT).show()
                        onCompleteClick(UserAccount(nickname.trim(), id.trim(), pw.trim(), twoFactorCode.trim()))
                    }
                }
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
            shape = RoundedCornerShape(26.dp)
        ) {
            Text(text = "회원가입 완료", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
        }

        Spacer(modifier = Modifier.height(16.dp))
        TextButton(onClick = onBackClick) {
            Text(text = "돌아가기", fontSize = 14.sp, color = Color(0xFF888888))
        }
    }
}

@Composable
fun FriendsScreen(
    friendsList: List<FriendItem>,
    onBackClick: () -> Unit
) {
    val displayedFriends = friendsList.sortedWith(
        compareByDescending<FriendItem> { it.isFavorite }.thenBy { it.name }
    )

    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Text(text = "친구 목록", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
            Spacer(modifier = Modifier.height(16.dp))

            if (displayedFriends.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxWidth().height(200.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(text = "등록된 친구가 없습니다.", fontSize = 14.sp, color = Color(0xFF999999))
                }
            } else {
                displayedFriends.forEach { friend ->
                    Card(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                        colors = CardDefaults.cardColors(containerColor = Color.White),
                        shape = RoundedCornerShape(12.dp),
                        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(16.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier.size(40.dp).clip(CircleShape).background(Color(0xFFE0E0E0)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(text = friend.name.take(1), fontWeight = FontWeight.Bold, color = Color.DarkGray)
                                }
                                Spacer(modifier = Modifier.width(12.dp))
                                Text(text = friend.name, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                            }
                            Surface(
                                color = if (friend.isFavorite) Color(0xFFFFECB3) else Color(0xFFFFF3E0),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Text(
                                    text = if (friend.isFavorite) "★ 즐겨찾기" else "친구",
                                    fontSize = 12.sp,
                                    color = Color(0xFFFF8F00),
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun FriendsManagementScreen(
    friendsList: MutableList<FriendItem>,
    onBackClick: () -> Unit
) {
    var newFriendName by remember { mutableStateOf("") }
    val context = LocalContext.current

    val sortedFriends = friendsList.sortedWith(
        compareByDescending<FriendItem> { it.isFavorite }.thenBy { it.name }
    )

    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "친구 관리",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333)
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = newFriendName,
                        onValueChange = { newFriendName = it },
                        placeholder = { Text("친구 이름 입력", color = Color(0xFF9E9E9E)) },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(12.dp),
                        colors = appTextFieldColors()
                    )
                    Button(
                        onClick = {
                            val trimmed = newFriendName.trim()
                            if (trimmed.isEmpty()) {
                                Toast.makeText(context, "친구 이름을 입력해 주세요.", Toast.LENGTH_SHORT).show()
                            } else if (friendsList.any { it.name == trimmed }) {
                                Toast.makeText(context, "이미 등록된 친구입니다.", Toast.LENGTH_SHORT).show()
                            } else {
                                friendsList.add(FriendItem(name = trimmed, isFavorite = false))
                                newFriendName = ""
                                Toast.makeText(context, "$trimmed 님을 친구로 추가했습니다.", Toast.LENGTH_SHORT).show()
                            }
                        },
                        modifier = Modifier.height(52.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text(
                            text = "추가",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF3C1E1E)
                        )
                    }
                }
            }

            if (sortedFriends.isEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(14.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(28.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "등록된 친구가 없습니다.",
                            fontSize = 14.sp,
                            color = Color(0xFF999999)
                        )
                    }
                }
            } else {
                for (friend in sortedFriends) {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = Color.White),
                        shape = RoundedCornerShape(14.dp),
                        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.weight(1f)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(38.dp)
                                        .clip(CircleShape)
                                        .background(if (friend.isFavorite) Color(0xFFFFECB3) else Color(0xFFECEFF1)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = friend.name.take(1),
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFF333333)
                                    )
                                }
                                Spacer(modifier = Modifier.width(12.dp))
                                Text(
                                    text = friend.name,
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF333333)
                                )
                            }

                            Row(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = if (friend.isFavorite) "★" else "☆",
                                    fontSize = 22.sp,
                                    color = if (friend.isFavorite) Color(0xFFFFB300) else Color(0xFFB0BEC5),
                                    modifier = Modifier
                                        .clickable {
                                            val idx = friendsList.indexOfFirst { it.id == friend.id }
                                            if (idx != -1) {
                                                friendsList[idx] = friendsList[idx].copy(isFavorite = !friendsList[idx].isFavorite)
                                            }
                                        }
                                        .padding(horizontal = 4.dp)
                                )

                                TextButton(
                                    onClick = {
                                        friendsList.removeAll { it.id == friend.id }
                                        Toast.makeText(context, "${friend.name} 님을 삭제했습니다.", Toast.LENGTH_SHORT).show()
                                    },
                                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp)
                                ) {
                                    Text(
                                        text = "삭제",
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFFD32F2F)
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MyPageScreen(
    nickname: String,
    userId: String,
    profileImageUri: Uri?,
    onProfileImageChanged: (Uri) -> Unit,
    onLogoutClick: () -> Unit,
    onNicknameChanged: (String) -> Unit,
    onMyRoomsClick: () -> Unit,
    onNotificationSettingsClick: () -> Unit,
    onCoordinationSettingsClick: () -> Unit,
    onFriendsManagementClick: () -> Unit,
    onAppSettingsClick: () -> Unit,
    onHelpClick: () -> Unit,
    onBackClick: () -> Unit
) {
    var showEditProfileDialog by remember { mutableStateOf(false) }
    var newNicknameInput by remember { mutableStateOf(nickname) }
    var draftProfileUri by remember { mutableStateOf(profileImageUri) }
    val context = LocalContext.current

    val imagePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            draftProfileUri = uri
            Toast.makeText(context, "프로필 이미지가 선택되었습니다.", Toast.LENGTH_SHORT).show()
        }
    }

    val currentProfileBitmap = remember(profileImageUri) {
        profileImageUri?.let { uri ->
            try {
                context.contentResolver.openInputStream(uri)?.use { stream ->
                    BitmapFactory.decodeStream(stream)?.asImageBitmap()
                }
            } catch (_: Exception) {
                null
            }
        }
    }

    val draftProfileBitmap = remember(draftProfileUri) {
        draftProfileUri?.let { uri ->
            try {
                context.contentResolver.openInputStream(uri)?.use { stream ->
                    BitmapFactory.decodeStream(stream)?.asImageBitmap()
                }
            } catch (_: Exception) {
                null
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 14.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "〈",
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF333333),
                    modifier = Modifier
                        .clickable { onBackClick() }
                        .padding(end = 12.dp)
                )
                Text(
                    text = "마이페이지",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF333333)
                )
            }
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(20.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(64.dp)
                            .clip(CircleShape)
                            .background(Color(0xFFD7CCC8)),
                        contentAlignment = Alignment.Center
                    ) {
                        if (currentProfileBitmap != null) {
                            Image(
                                bitmap = currentProfileBitmap,
                                contentDescription = "프로필 사진",
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.fillMaxSize()
                            )
                        } else {
                            Text(
                                text = nickname.take(1),
                                fontSize = 24.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(16.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(text = nickname, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                        Text(text = userId, fontSize = 13.sp, color = Color(0xFF777777))
                    }
                    OutlinedButton(
                        onClick = {
                            newNicknameInput = nickname
                            draftProfileUri = profileImageUri
                            showEditProfileDialog = true
                        },
                        shape = RoundedCornerShape(20.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                    ) {
                        Text(text = "프로필 수정", fontSize = 12.sp, color = Color(0xFF555555))
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            val menuItems = listOf("내 모임 관리", "알림 설정", "시간 조율 설정", "친구 관리", "설정", "도움말")
            menuItems.forEach { menu ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp)
                        .clickable {
                            when (menu) {
                                "내 모임 관리" -> onMyRoomsClick()
                                "알림 설정" -> onNotificationSettingsClick()
                                "시간 조율 설정" -> onCoordinationSettingsClick()
                                "친구 관리" -> onFriendsManagementClick()
                                "설정" -> onAppSettingsClick()
                                "도움말" -> onHelpClick()
                            }
                        },
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(12.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(text = menu, fontSize = 15.sp, color = Color(0xFF333333))
                        Text(text = "〉", fontSize = 14.sp, color = Color(0xFFAAAAAA))
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            Button(
                onClick = onLogoutClick,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFCDD2)),
                shape = RoundedCornerShape(24.dp)
            ) {
                Text(text = "로그아웃", fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color(0xFFC62828))
            }
        }
    }

    if (showEditProfileDialog) {
        AlertDialog(
            onDismissRequest = { showEditProfileDialog = false },
            containerColor = Color.White,
            title = { Text(text = "프로필 수정", fontWeight = FontWeight.Bold, color = Color(0xFF333333)) },
            text = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Box(
                        modifier = Modifier
                            .size(84.dp)
                            .clip(CircleShape)
                            .background(Color(0xFFD7CCC8))
                            .clickable { imagePickerLauncher.launch("image/*") },
                        contentAlignment = Alignment.Center
                    ) {
                        if (draftProfileBitmap != null) {
                            Image(
                                bitmap = draftProfileBitmap,
                                contentDescription = "프로필 사진 변경",
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.fillMaxSize()
                            )
                        } else {
                            Text(
                                text = (newNicknameInput.ifBlank { nickname }).take(1),
                                fontSize = 28.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    OutlinedTextField(
                        value = newNicknameInput,
                        onValueChange = { newNicknameInput = it },
                        placeholder = { Text("닉네임", color = Color(0xFF9E9E9E)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = appTextFieldColors()
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (newNicknameInput.isNotBlank()) {
                            onNicknameChanged(newNicknameInput.trim())
                        }
                        draftProfileUri?.let { onProfileImageChanged(it) }
                        showEditProfileDialog = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F))
                ) {
                    Text(text = "저장", color = Color(0xFF3C1E1E), fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showEditProfileDialog = false }) {
                    Text(text = "취소", color = Color.DarkGray)
                }
            }
        )
    }
}

@Composable
fun HelpScreen(
    onBackClick: () -> Unit
) {
    val helpSections = remember {
        listOf(
            HelpItem(
                title = "알림 설정",
                body = "• 상단 '알림 켜기 / 끄기' 스위치를 끄면 아래 '확정된 날짜 알림' 항목들도 비활성화되어 전체 알림이 멈춥니다.\n• 전체 알림이 켜진 상태에서는 최종 확정된 약속별 스위치를 개별적으로 켜고 끌 수 있습니다."
            ),
            HelpItem(
                title = "시간 조율 설정 - 기본 시간 분할 단위",
                body = "• '30분' 선택 시 시간표가 00~30분과 30~60분 두 칸으로 나뉘어 세밀하게 선택할 수 있습니다.\n• '60분' 선택 시 한 시간(00~60분) 단위로 한 번에 선택·해제됩니다."
            ),
            HelpItem(
                title = "시간 조율 설정 - 기본 불가 시간 프리셋",
                body = "• 스위치를 켜면 심야 시간대(00:00 ~ 06:00)가 기본 불가 시간으로 자동 반영됩니다.\n• 스위치를 끄면 프리셋으로 자동 추가된 심야 불가 시간만 정리되며, 직접 터치해 지정한 불가 시간은 유지됩니다."
            ),
            HelpItem(
                title = "시간 조율 설정 - 가능/불가한 시간 선택 모드",
                body = "• OFF(불가한 시간 선택 모드): 약속에 참석하기 어려운 시간(주황색 계열)을 기준으로 표시하고 선택합니다.\n• ON(가능한 시간 선택 모드): 참석 가능한 시간(노란색 계열)을 기준으로 직관적으로 확인할 수 있습니다."
            ),
            HelpItem(
                title = "설정 (홈 화면 캘린더 표시)",
                body = "• 기본값은 OFF이며, ON으로 켜면 홈 화면의 '모임 현황' 위에 캘린더가 나타납니다.\n• '내 모임 관리'의 캘린더와 같은 월 이동 및 확정 약속 클릭 기능을 지원하되, 홈 화면 캘린더는 베이지색 배경으로 표시됩니다."
            ),
            HelpItem(
                title = "내 모임 관리 & 프로필 수정",
                body = "• '내 모임 관리'에서는 확정된 약속 날짜를 캘린더와 목록으로 확인하고, 날짜나 항목을 눌러 해당 모임 상세로 바로 이동할 수 있습니다.\n• 프로필 카드의 '프로필 수정' 버튼을 누르면 프로필 사진과 닉네임을 변경할 수 있습니다."
            )
        )
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "도움말",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333)
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFAF0)),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, Color(0xFFFFE082)),
                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                ) {
                    Text(
                        text = "potato meet 주요 기능 안내",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF4A3B32)
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "• 모임 생성 및 후보일 선택: 모임을 만들고 약속 후보 날짜들을 한 번에 고를 수 있습니다.\n• 가능/불가 시간표 조율: 30분 또는 60분 단위로 내 일정에 맞춰 시간표를 입력합니다.\n• AI 최적 시간 추천·투표 및 확정: 추천 후보 시간에 투표하고 최종 약속 시간을 확정할 수 있습니다.\n• 캘린더 및 알림 관리: 확정된 일정을 캘린더로 확인하고 약속별 알림을 관리합니다.",
                        fontSize = 13.sp,
                        lineHeight = 19.sp,
                        color = Color(0xFF555555)
                    )
                }
            }

            for (item in helpSections) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp)
                    ) {
                        Text(
                            text = item.title,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333)
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = item.body,
                            fontSize = 13.sp,
                            lineHeight = 19.sp,
                            color = Color(0xFF555555)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
        }
    }
}

@Composable
fun AppSettingsScreen(
    showHomeCalendarEnabled: Boolean,
    onToggleShowHomeCalendar: (Boolean) -> Unit,
    onBackClick: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Text(
                text = "설정",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333)
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 18.dp, vertical = 16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "홈 화면 캘린더 표시",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333)
                        )
                        Spacer(modifier = Modifier.height(3.dp))
                        Text(
                            text = if (showHomeCalendarEnabled) {
                                "ON: 홈 화면 모임 현황 위에 캘린더를 표시합니다."
                            } else {
                                "OFF: 홈 화면에 캘린더를 표시하지 않습니다."
                            },
                            fontSize = 12.sp,
                            color = Color(0xFF777777)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    ImageStyleSwitch(
                        checked = showHomeCalendarEnabled,
                        onCheckedChange = onToggleShowHomeCalendar
                    )
                }
            }
        }
    }
}

@Composable
fun CoordinationSettingsScreen(
    timeUnitMinutes: Int,
    onSelectTimeUnit: (Int) -> Unit,
    defaultUnavailablePresetEnabled: Boolean,
    onToggleDefaultUnavailablePreset: (Boolean) -> Unit,
    selectAvailableModeEnabled: Boolean,
    onToggleSelectAvailableMode: (Boolean) -> Unit,
    onBackClick: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Text(
                text = "시간 조율 설정",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333)
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(18.dp)
                ) {
                    Text(
                        text = "기본 시간 분할 단위",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF333333)
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "시간표를 30분 단위로 나눌지 60분 단위로 나눌지 선택하세요.",
                        fontSize = 12.sp,
                        color = Color(0xFF777777)
                    )
                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        val is30 = timeUnitMinutes == 30
                        val is60 = timeUnitMinutes == 60

                        Button(
                            onClick = { onSelectTimeUnit(30) },
                            modifier = Modifier.weight(1f).height(46.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (is30) Color(0xFFFFD54F) else Color(0xFFF5F5F5)
                            ),
                            border = if (!is30) BorderStroke(1.dp, Color(0xFFE0E0E0)) else null,
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(
                                text = "30분",
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (is30) Color(0xFF3C1E1E) else Color(0xFF666666)
                            )
                        }

                        Button(
                            onClick = { onSelectTimeUnit(60) },
                            modifier = Modifier.weight(1f).height(46.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (is60) Color(0xFFFFD54F) else Color(0xFFF5F5F5)
                            ),
                            border = if (!is60) BorderStroke(1.dp, Color(0xFFE0E0E0)) else null,
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(
                                text = "60분",
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (is60) Color(0xFF3C1E1E) else Color(0xFF666666)
                            )
                        }
                    }
                }
            }

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 18.dp, vertical = 16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "기본 불가 시간 프리셋",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333)
                        )
                        Spacer(modifier = Modifier.height(3.dp))
                        Text(
                            text = "심야 시간대(00:00 ~ 06:00)를 기본 불가 시간으로 적용합니다.",
                            fontSize = 12.sp,
                            color = Color(0xFF777777)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    ImageStyleSwitch(
                        checked = defaultUnavailablePresetEnabled,
                        onCheckedChange = onToggleDefaultUnavailablePreset
                    )
                }
            }

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 18.dp, vertical = 16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = if (selectAvailableModeEnabled) "가능한 시간 선택 모드" else "불가한 시간 선택 모드",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333)
                        )
                        Spacer(modifier = Modifier.height(3.dp))
                        Text(
                            text = if (selectAvailableModeEnabled) {
                                "ON: 시간표에서 가능한 시간을 기준으로 선택합니다."
                            } else {
                                "OFF: 시간표에서 불가한 시간을 기준으로 선택합니다."
                            },
                            fontSize = 12.sp,
                            color = Color(0xFF777777)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    ImageStyleSwitch(
                        checked = selectAvailableModeEnabled,
                        onCheckedChange = onToggleSelectAvailableMode
                    )
                }
            }
        }
    }
}

@Composable
fun NotificationSettingsScreen(
    allNotificationsEnabled: Boolean,
    onToggleAllNotifications: (Boolean) -> Unit,
    confirmedRooms: List<RoomModel>,
    dateAlarmStates: Map<Long, Boolean>,
    onToggleRoomAlarm: (Long, Boolean) -> Unit,
    onBackClick: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 18.dp, vertical = 16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "🔔",
                            fontSize = 20.sp
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = if (allNotificationsEnabled) "알림 켜기" else "알림 끄기",
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333)
                        )
                    }
                    ImageStyleSwitch(
                        checked = allNotificationsEnabled,
                        onCheckedChange = onToggleAllNotifications
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            Text(
                text = "확정된 날짜 알림",
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333)
            )
            Spacer(modifier = Modifier.height(10.dp))

            if (confirmedRooms.isEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(14.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(24.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "확정된 날짜가 없습니다.",
                            fontSize = 13.sp,
                            color = Color(0xFF999999)
                        )
                    }
                }
            } else {
                for (room in confirmedRooms) {
                    val roomAlarmOn = dateAlarmStates[room.id] ?: true
                    val effectiveChecked = allNotificationsEnabled && roomAlarmOn

                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 5.dp),
                        colors = CardDefaults.cardColors(containerColor = Color.White),
                        shape = RoundedCornerShape(14.dp),
                        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 16.dp, vertical = 14.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = room.finalAiTime,
                                    fontSize = 15.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF333333)
                                )
                                Spacer(modifier = Modifier.height(2.dp))
                                Text(
                                    text = room.title,
                                    fontSize = 12.sp,
                                    color = Color(0xFF777777)
                                )
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            ImageStyleSwitch(
                                checked = effectiveChecked,
                                enabled = allNotificationsEnabled,
                                onCheckedChange = { newState ->
                                    onToggleRoomAlarm(room.id, newState)
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ScheduleCalendarCard(
    roomsList: List<RoomModel>,
    onRoomClick: (RoomModel) -> Unit,
    calendarInnerBackgroundColor: Color,
    calendarInnerBorderColor: Color,
    showConfirmedListBelow: Boolean,
    showLegend: Boolean = true
) {
    val todayCal = remember { Calendar.getInstance() }
    val todayYear = todayCal.get(Calendar.YEAR)
    val todayMonth = todayCal.get(Calendar.MONTH) + 1
    val todayDay = todayCal.get(Calendar.DAY_OF_MONTH)

    var displayYear by remember { mutableIntStateOf(todayYear) }
    var displayMonth by remember { mutableIntStateOf(todayMonth) }

    val confirmedRooms = roomsList.filter { it.isConfirmed }

    val confirmedMonthDays = remember(confirmedRooms) {
        confirmedRooms.mapNotNull { room ->
            parseMonthDayFromTimeStr(room.finalAiTime)
        }.toSet()
    }

    val monthStartCal = remember(displayYear, displayMonth) {
        Calendar.getInstance().apply {
            set(Calendar.YEAR, displayYear)
            set(Calendar.MONTH, displayMonth - 1)
            set(Calendar.DAY_OF_MONTH, 1)
        }
    }
    val firstDayOfWeekIndex = monthStartCal.get(Calendar.DAY_OF_WEEK) - 1
    val daysInMonth = monthStartCal.getActualMaximum(Calendar.DAY_OF_MONTH)

    val calendarCells: List<Int?> = remember(firstDayOfWeekIndex, daysInMonth) {
        val leadingBlanks = List<Int?>(firstDayOfWeekIndex) { null }
        val dayItems = (1..daysInMonth).map { it as Int? }
        val combined = leadingBlanks + dayItems
        val remainder = combined.size % 7
        if (remainder == 0) combined else combined + List<Int?>(7 - remainder) { null }
    }

    val todayHighlightColor = Color(0xFFFFD54F)

    Column(modifier = Modifier.fillMaxWidth()) {
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = calendarInnerBackgroundColor),
            shape = RoundedCornerShape(24.dp),
            elevation = CardDefaults.cardElevation(defaultElevation = 3.dp)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(14.dp)
                    .background(calendarInnerBackgroundColor, RoundedCornerShape(18.dp))
                    .border(1.dp, calendarInnerBorderColor, RoundedCornerShape(18.dp))
                    .padding(horizontal = 16.dp, vertical = 18.dp)
            ) {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "<",
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Normal,
                            color = Color(0xFF222222),
                            modifier = Modifier
                                .clip(RoundedCornerShape(8.dp))
                                .clickable {
                                    if (displayMonth == 1) {
                                        displayMonth = 12
                                        displayYear -= 1
                                    } else {
                                        displayMonth -= 1
                                    }
                                }
                                .padding(horizontal = 8.dp, vertical = 2.dp)
                        )

                        Text(
                            text = "${displayYear}년 ${displayMonth}월",
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF222222)
                        )

                        Text(
                            text = ">",
                            fontSize = 22.sp,
                            fontWeight = FontWeight.Normal,
                            color = Color(0xFF222222),
                            modifier = Modifier
                                .clip(RoundedCornerShape(8.dp))
                                .clickable {
                                    if (displayMonth == 12) {
                                        displayMonth = 1
                                        displayYear += 1
                                    } else {
                                        displayMonth += 1
                                    }
                                }
                                .padding(horizontal = 8.dp, vertical = 2.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(18.dp))

                    val daysOfWeek = listOf("일", "월", "화", "수", "목", "금", "토")
                    Row(modifier = Modifier.fillMaxWidth()) {
                        daysOfWeek.forEachIndexed { idx, dow ->
                            Text(
                                text = dow,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (idx == 0) Color(0xFFE53935) else Color(0xFF333333),
                                textAlign = TextAlign.Center,
                                modifier = Modifier.weight(1f)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    val rows = calendarCells.chunked(7)
                    rows.forEachIndexed { rowIndex, week ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            for (day in week) {
                                if (day == null) {
                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .height(44.dp)
                                    )
                                } else {
                                    val isToday = (displayYear == todayYear && displayMonth == todayMonth && day == todayDay)
                                    val hasMeeting = confirmedMonthDays.contains(displayMonth to day)
                                    val matchedRoom = if (hasMeeting) {
                                        confirmedRooms.firstOrNull { parseMonthDayFromTimeStr(it.finalAiTime) == (displayMonth to day) }
                                    } else {
                                        null
                                    }

                                    val bgColor = if (isToday) todayHighlightColor else Color.Transparent
                                    val borderStroke = if (hasMeeting) {
                                        BorderStroke(1.5.dp, todayHighlightColor)
                                    } else {
                                        null
                                    }

                                    Box(
                                        modifier = Modifier
                                            .weight(1f)
                                            .height(44.dp)
                                            .clip(RoundedCornerShape(10.dp))
                                            .background(bgColor)
                                            .then(
                                                if (borderStroke != null) {
                                                    Modifier.border(borderStroke, RoundedCornerShape(10.dp))
                                                } else {
                                                    Modifier
                                                }
                                            )
                                            .then(
                                                if (matchedRoom != null) {
                                                    Modifier.clickable { onRoomClick(matchedRoom) }
                                                } else {
                                                    Modifier
                                                }
                                            ),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Column(
                                            horizontalAlignment = Alignment.CenterHorizontally,
                                            verticalArrangement = Arrangement.Center
                                        ) {
                                            if (hasMeeting) {
                                                Box(
                                                    modifier = Modifier
                                                        .size(5.dp)
                                                        .clip(CircleShape)
                                                        .background(Color(0xFFE53935))
                                                )
                                                Spacer(modifier = Modifier.height(2.dp))
                                            }
                                            Text(
                                                text = "$day",
                                                fontSize = 15.sp,
                                                fontWeight = if (isToday || hasMeeting) FontWeight.Bold else FontWeight.Medium,
                                                color = Color(0xFF222222)
                                            )
                                        }
                                    }
                                }
                            }
                        }
                        if (rowIndex < rows.lastIndex) {
                            Spacer(modifier = Modifier.height(6.dp))
                        }
                    }
                }
            }
        }

        if (showLegend) {
            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(14.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(todayHighlightColor)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(text = "현재 날짜", fontSize = 12.sp, color = Color(0xFF555555))
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(14.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .border(1.5.dp, todayHighlightColor, RoundedCornerShape(4.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        Box(
                            modifier = Modifier
                                .size(4.dp)
                                .clip(CircleShape)
                                .background(Color(0xFFE53935))
                        )
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(text = "약속 있는 날짜", fontSize = 12.sp, color = Color(0xFF555555))
                }
            }
        }

        if (showConfirmedListBelow) {
            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "확정된 모임 (${confirmedRooms.size}건)",
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333)
            )
            Spacer(modifier = Modifier.height(8.dp))

            if (confirmedRooms.isEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(14.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(24.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "아직 확정된 약속이 없습니다.", fontSize = 13.sp, color = Color(0xFF999999))
                    }
                }
            } else {
                for (room in confirmedRooms) {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .clickable { onRoomClick(room) },
                        colors = CardDefaults.cardColors(containerColor = Color.White),
                        shape = RoundedCornerShape(14.dp),
                        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(14.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(7.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFFE53935))
                            )
                            Spacer(modifier = Modifier.width(10.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(text = room.title, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                                Spacer(modifier = Modifier.height(2.dp))
                                Text(text = room.finalAiTime, fontSize = 12.sp, color = Color(0xFF666666))
                            }
                            Text(text = "〉", fontSize = 14.sp, color = Color(0xFFAAAAAA))
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MyRoomsScreen(
    roomsList: List<RoomModel>,
    onRoomClick: (RoomModel) -> Unit,
    onBackClick: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Text(
                text = "내 모임 관리",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333)
            )

            Spacer(modifier = Modifier.height(14.dp))

            ScheduleCalendarCard(
                roomsList = roomsList,
                onRoomClick = onRoomClick,
                calendarInnerBackgroundColor = Color(0xFFFFFDE7),
                calendarInnerBorderColor = Color(0xFFFFF0B3),
                showConfirmedListBelow = true,
                showLegend = true
            )

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
fun TopLogoHeader(onBackClick: (() -> Unit)? = null) {
    Row(
        verticalAlignment = Alignment.CenterVertically
    ) {
        if (onBackClick != null) {
            Text(
                text = "〈",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333),
                modifier = Modifier
                    .clickable { onBackClick() }
                    .padding(end = 12.dp)
            )
        }
        Text(
            text = buildAnnotatedString {
                withStyle(SpanStyle(color = Color(0xFF4A3B32), fontWeight = FontWeight.ExtraBold)) { append("potato ") }
                withStyle(SpanStyle(color = Color(0xFFFF9800), fontWeight = FontWeight.ExtraBold)) { append("meet") }
            },
            fontSize = 24.sp
        )
    }
}

@Composable
fun HomeScreen(
    nickname: String,
    roomsList: List<RoomModel>,
    showCalendar: Boolean,
    onCreateRoomClick: () -> Unit,
    onRoomClick: (RoomModel) -> Unit,
    onMyPageClick: () -> Unit
) {
    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFFCF3))
                    .padding(horizontal = 20.dp, vertical = 12.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    TopLogoHeader()
                    Text(
                        text = "MY",
                        fontSize = 13.sp,
                        color = Color(0xFF555555),
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable { onMyPageClick() }.padding(4.dp)
                    )
                }
            }

            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp)
            ) {
                if (showCalendar) {
                    Spacer(modifier = Modifier.height(10.dp))
                    ScheduleCalendarCard(
                        roomsList = roomsList,
                        onRoomClick = onRoomClick,
                        calendarInnerBackgroundColor = Color(0xFFFAF6EE),
                        calendarInnerBorderColor = Color(0xFFEAE2D3),
                        showConfirmedListBelow = false,
                        showLegend = false
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                }

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(text = "모임 현황", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Text(text = "더보기", fontSize = 13.sp, color = Color(0xFF888888))
                }
                Spacer(modifier = Modifier.height(10.dp))

                if (roomsList.isEmpty()) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(250.dp)
                            .background(Color.White, RoundedCornerShape(16.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = "모임이 없습니다. 모임을 추가하시겠습니까?",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF666666)
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Button(
                                onClick = onCreateRoomClick,
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                                shape = RoundedCornerShape(20.dp)
                            ) {
                                Text(text = "모임 추가하기", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                            }
                        }
                    }
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        for (room in roomsList) {
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onRoomClick(room) },
                                colors = CardDefaults.cardColors(containerColor = Color.White),
                                shape = RoundedCornerShape(16.dp),
                                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                            ) {
                                Column(modifier = Modifier.padding(16.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = if (room.isConfirmed) "[확정완료] ${room.title}" else room.title,
                                            fontSize = 16.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = if (room.isConfirmed) Color(0xFF2E7D32) else Color(0xFF333333)
                                        )
                                        if (room.isConfirmed) {
                                            Surface(color = Color(0xFFE8F5E9), shape = RoundedCornerShape(6.dp)) {
                                                Text(text = "확정", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color(0xFF2E7D32), modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
                                            }
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        text = if (room.isConfirmed) "📅 확정 시간: ${room.finalAiTime}" else room.description,
                                        fontSize = 13.sp,
                                        color = Color(0xFF666666)
                                    )
                                }
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(90.dp))
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(20.dp)
        ) {
            ExtendedFloatingActionButton(
                onClick = onCreateRoomClick,
                containerColor = Color(0xFFFFD54F),
                contentColor = Color(0xFF3C1E1E),
                shape = RoundedCornerShape(28.dp)
            ) {
                Text(
                    text = "+ 모임 만들기",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 4.dp)
                )
            }
        }
    }
}

@Composable
fun CreateRoomScreen(
    roomTitle: String,
    onRoomTitleChange: (String) -> Unit,
    roomDesc: String,
    onRoomDescChange: (String) -> Unit,
    selectedDates: MutableList<String>,
    onBackClick: () -> Unit,
    onCreateComplete: () -> Unit
) {
    val allCalendarDays = (1..30).toList()

    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(text = "모임 이름 *", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = roomTitle,
                        onValueChange = onRoomTitleChange,
                        placeholder = { Text("모임 이름을 입력해주세요", color = Color(0xFF9E9E9E)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = appTextFieldColors()
                    )

                    Spacer(modifier = Modifier.height(12.dp))
                    Text(text = "모임 설명", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = roomDesc,
                        onValueChange = onRoomDescChange,
                        placeholder = { Text("모임에 대한 간단한 설명", color = Color(0xFF9E9E9E)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = appTextFieldColors()
                    )

                    Spacer(modifier = Modifier.height(16.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(text = "모임 날짜 *", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                        Text(text = "모임을 열고 싶은 날짜를 모두 선택해 주세요.", fontSize = 11.sp, color = Color(0xFF888888))
                    }
                    Spacer(modifier = Modifier.height(10.dp))

                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFFFFFAF0), RoundedCornerShape(12.dp))
                            .border(1.dp, Color(0xFFFFE082), RoundedCornerShape(12.dp))
                            .padding(12.dp)
                    ) {
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(text = "〈 2026년 11월 〉", fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color(0xFF4A3B32))
                            }
                            Spacer(modifier = Modifier.height(10.dp))

                            val daysOfWeek = listOf("일", "월", "화", "수", "목", "금", "토")
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround) {
                                daysOfWeek.forEach {
                                    Text(text = it, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color.Gray, textAlign = TextAlign.Center, modifier = Modifier.weight(1f))
                                }
                            }
                            Spacer(modifier = Modifier.height(6.dp))

                            val createRows = allCalendarDays.chunked(7)
                            createRows.forEachIndexed { rIdx, week ->
                                Row(modifier = Modifier.fillMaxWidth()) {
                                    for (day in week) {
                                        val dayStr = String.format("11.%02d", day)
                                        val dayOfWeekStr = when (day % 7) {
                                            1 -> "(일)"
                                            2 -> "(월)"
                                            3 -> "(화)"
                                            4 -> "(수)"
                                            5 -> "(목)"
                                            6 -> "(금)"
                                            else -> "(토)"
                                        }
                                        val fullTag = "$dayStr$dayOfWeekStr"
                                        val isSelected = selectedDates.contains(fullTag)

                                        Box(
                                            modifier = Modifier
                                                .weight(1f)
                                                .height(38.dp)
                                                .padding(2.dp)
                                                .clip(CircleShape)
                                                .background(if (isSelected) Color(0xFFFF8F00) else Color.Transparent)
                                                .clickable {
                                                    if (isSelected) selectedDates.remove(fullTag)
                                                    else selectedDates.add(fullTag)
                                                },
                                            contentAlignment = Alignment.Center
                                        ) {
                                            Text(
                                                text = "$day",
                                                fontSize = 12.sp,
                                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                                color = if (isSelected) Color.White else Color.Black
                                            )
                                        }
                                    }
                                    if (week.size < 7) {
                                        repeat(7 - week.size) {
                                            Spacer(modifier = Modifier.weight(1f).height(38.dp))
                                        }
                                    }
                                }
                                if (rIdx < createRows.lastIndex) {
                                    Spacer(modifier = Modifier.height(2.dp))
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(text = "선택한 날짜 ${selectedDates.size}개", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFF8F00))
                        TextButton(onClick = { selectedDates.clear() }) {
                            Text(text = "초기화", fontSize = 12.sp, color = Color.Gray)
                        }
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        for (date in selectedDates) {
                            Surface(
                                color = Color(0xFFFFECB3),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Row(
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(text = date, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        text = "✕",
                                        fontSize = 10.sp,
                                        color = Color.Gray,
                                        modifier = Modifier.clickable { selectedDates.remove(date) }
                                    )
                                }
                            }
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(20.dp))
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(20.dp)
        ) {
            Button(
                onClick = onCreateComplete,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(text = "모임 만들기", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }
}

@Composable
fun CalendarCutoutCard(dateTag: String) {
    val monthPart = dateTag.substringBefore(".", "11")
    val afterDot = dateTag.substringAfter(".", "14(토)")
    val dayPart = afterDot.substringBefore("(", "14")
    val dowPart = afterDot.substringAfter("(", "토)").substringBefore(")", "토")

    val dowColor = when (dowPart) {
        "일" -> Color(0xFFD32F2F)
        "토" -> Color(0xFF1976D2)
        else -> Color(0xFF666666)
    }

    Card(
        modifier = Modifier.width(64.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, Color(0xFFFFE082)),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFB300))
                    .padding(vertical = 3.dp),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "${monthPart}월",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = dowPart,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = dowColor
            )

            Text(
                text = dayPart,
                fontSize = 18.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color(0xFF333333)
            )

            Spacer(modifier = Modifier.height(6.dp))
        }
    }
}

@Composable
fun RoomDetailScreen(
    room: RoomModel,
    timeUnitMinutes: Int,
    selectAvailableModeEnabled: Boolean,
    onBackClick: () -> Unit,
    onEditUnavailableClick: () -> Unit,
    onAiResultClick: () -> Unit,
    onInviteKakao: () -> Unit
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(modifier = Modifier.height(6.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Text(text = room.title, fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(text = room.description, fontSize = 13.sp, color = Color(0xFF666666))
                    Spacer(modifier = Modifier.height(16.dp))

                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFFFFFAF0), RoundedCornerShape(14.dp))
                            .border(1.dp, Color(0xFFFFECB3), RoundedCornerShape(14.dp))
                            .padding(12.dp)
                    ) {
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(text = "2026년 11월", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF4A3B32))
                                Text(text = "후보일 ${room.selectedDates.size}개", fontSize = 11.sp, color = Color(0xFFFF8F00), fontWeight = FontWeight.Bold)
                            }
                            Spacer(modifier = Modifier.height(10.dp))

                            if (room.selectedDates.isEmpty()) {
                                Text(text = "선택된 후보 날짜가 없습니다.", fontSize = 12.sp, color = Color(0xFF999999))
                            } else {
                                Row(
                                    modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                                ) {
                                    for (date in room.selectedDates) {
                                        CalendarCutoutCard(dateTag = date)
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))
                    HorizontalDivider(color = Color(0xFFF0F0F0))
                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(text = "현재 참여자", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                        Text(text = "${room.participants.size}명", fontSize = 12.sp, color = Color(0xFF888888))
                    }
                    Spacer(modifier = Modifier.height(8.dp))

                    for (member in room.participants) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(text = if (member == room.hostName) "방장" else "참여자", fontSize = 13.sp, color = Color(0xFF666666))
                            Surface(color = Color(0xFFFFF3E0), shape = RoundedCornerShape(8.dp)) {
                                Text(text = member, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFF8F00), modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp))
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))
                    HorizontalDivider(color = Color(0xFFF0F0F0))
                    Spacer(modifier = Modifier.height(16.dp))

                    Text(text = "친구 초대", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(text = "아직 초대된 친구가 없어요. 함께할 친구에게 모임을 보내주세요.", fontSize = 12.sp, color = Color(0xFF888888))
                    Spacer(modifier = Modifier.height(12.dp))

                    Button(
                        onClick = onInviteKakao,
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFEE58)),
                        shape = RoundedCornerShape(24.dp)
                    ) {
                        Text(text = "💛 카카오톡으로 친구 초대", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                    }

                    Spacer(modifier = Modifier.height(20.dp))
                    HorizontalDivider(color = Color(0xFFF0F0F0))
                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = if (selectAvailableModeEnabled) "내 가능/불가 시간" else "내 불가능 시간",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333)
                        )
                        Text(text = "총 ${room.unavailableSlots.size}개 불가 구간", fontSize = 12.sp, color = Color(0xFFFF8F00), fontWeight = FontWeight.Bold)
                    }
                    Spacer(modifier = Modifier.height(10.dp))

                    if (room.unavailableSlots.isEmpty()) {
                        Text(text = "설정된 불가능 시간이 없습니다.", fontSize = 13.sp, color = Color.Gray)
                    } else {
                        val sortedSlots = room.unavailableSlots.sortedWith(
                            compareBy({ it.dateStr }, { it.startHour }, { it.startMin })
                        )
                        for (slot in sortedSlots) {
                            Card(
                                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFDF9)),
                                shape = RoundedCornerShape(10.dp),
                                border = BorderStroke(1.dp, Color(0xFFFFE082))
                            ) {
                                Row(
                                    modifier = Modifier.fillMaxWidth().padding(12.dp),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(text = slot.dateStr, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                                    Text(
                                        text = String.format("%02d:%02d ~ %02d:%02d", slot.startHour, slot.startMin, slot.endHour, slot.endMin),
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFFE65100)
                                    )
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    Button(
                        onClick = onEditUnavailableClick,
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF8D6E63)),
                        shape = RoundedCornerShape(24.dp)
                    ) {
                        val modeLabel = if (selectAvailableModeEnabled) "가능 시간 선택" else "불가 시간 수정"
                        Text(
                            text = "$modeLabel (${timeUnitMinutes}분 단위 시간표)",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.height(20.dp))
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(20.dp)
        ) {
            Button(
                onClick = onAiResultClick,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(text = "AI 최적 시간 조율 결과 보기 ✨", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }
}

@Composable
fun EditUnavailableScreen(
    room: RoomModel,
    timeUnitMinutes: Int,
    selectAvailableModeEnabled: Boolean,
    onToggleSlot: (dateStr: String, hour: Int, startMin: Int) -> Unit,
    onClearDateSlots: (dateStr: String) -> Unit,
    onBackClick: () -> Unit,
    onSaveComplete: () -> Unit
) {
    val datesToShow = room.selectedDates.ifEmpty { listOf("11.14(토)") }
    var selectedTabDate by remember { mutableStateOf(datesToShow.first()) }
    var selectedTimePage by remember { mutableIntStateOf(1) }

    val timeRanges = remember {
        listOf(
            TimeRangePage(0, 8, "00:00 ~ 08:00"),
            TimeRangePage(8, 16, "08:00 ~ 16:00"),
            TimeRangePage(16, 24, "16:00 ~ 24:00")
        )
    }

    val currentRange = timeRanges[selectedTimePage]
    val startHourOfPage = currentRange.startHour
    val endHourOfPage = currentRange.endHour
    val rangeLabel = currentRange.label

    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = if (selectAvailableModeEnabled) "내 가능 시간 선택" else "내 불가능 시간 수정",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF333333)
                )
                TextButton(onClick = { onClearDateSlots(selectedTabDate) }) {
                    Text(text = "현재 날짜 초기화", fontSize = 12.sp, color = Color(0xFFFF8F00), fontWeight = FontWeight.Bold)
                }
            }
            Text(
                text = if (selectAvailableModeEnabled) {
                    "${timeUnitMinutes}분 단위로 터치하여 가능한 시간을 선택하세요."
                } else {
                    "${timeUnitMinutes}분 단위로 터치하여 불가한 시간을 선택하세요."
                },
                fontSize = 12.sp,
                color = Color(0xFF777777)
            )
            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                for (date in datesToShow) {
                    val isSelected = (date == selectedTabDate)
                    Button(
                        onClick = { selectedTabDate = date },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = if (isSelected) Color(0xFFFF8F00) else Color.White
                        ),
                        border = if (!isSelected) BorderStroke(1.dp, Color(0xFFE0E0E0)) else null,
                        shape = RoundedCornerShape(10.dp),
                        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp)
                    ) {
                        Text(
                            text = date,
                            fontSize = 12.sp,
                            color = if (isSelected) Color.White else Color(0xFF333333),
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                timeRanges.forEachIndexed { index, rangePage ->
                    val isPageSelected = (selectedTimePage == index)
                    Surface(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(10.dp))
                            .clickable { selectedTimePage = index },
                        color = if (isPageSelected) Color(0xFF4A3B32) else Color(0xFFF3EFE6),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Column(
                            modifier = Modifier.padding(vertical = 8.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text(
                                text = "${index + 1}/3 구간",
                                fontSize = 10.sp,
                                color = if (isPageSelected) Color(0xFFFFD54F) else Color(0xFF888888),
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = rangePage.label,
                                fontSize = 11.sp,
                                color = if (isPageSelected) Color.White else Color(0xFF4A3B32),
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(14.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(text = "시간표 ($rangeLabel · ${timeUnitMinutes}분)", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(modifier = Modifier.size(10.dp).background(Color(0xFFF5F5F5), RoundedCornerShape(2.dp)).border(1.dp, Color(0xFFE0E0E0), RoundedCornerShape(2.dp)))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(text = "가능", fontSize = 11.sp, color = Color.Gray)
                            }
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(modifier = Modifier.size(10.dp).background(Color(0xFFFF8A65), RoundedCornerShape(2.dp)))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text(text = "불가", fontSize = 11.sp, color = Color(0xFFD84315), fontWeight = FontWeight.Bold)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(Color(0xFFFFFAF0), RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp))
                            .border(1.dp, Color(0xFFFFE082), RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp))
                            .padding(vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "시간",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF4A3B32),
                            textAlign = TextAlign.Center,
                            modifier = Modifier.width(64.dp)
                        )
                        if (timeUnitMinutes == 60) {
                            Text(
                                text = "00분 ~ 60분 (1시간 단위)",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF4A3B32),
                                textAlign = TextAlign.Center,
                                modifier = Modifier.weight(1f)
                            )
                        } else {
                            Text(
                                text = "00분 ~ 30분",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF4A3B32),
                                textAlign = TextAlign.Center,
                                modifier = Modifier.weight(1f)
                            )
                            Text(
                                text = "30분 ~ 60분",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF4A3B32),
                                textAlign = TextAlign.Center,
                                modifier = Modifier.weight(1f)
                            )
                        }
                    }

                    val hoursInPage = (startHourOfPage until endHourOfPage).toList()
                    for (hour in hoursInPage) {
                        val isFirstHalfUnavailable = room.unavailableSlots.any {
                            it.dateStr == selectedTabDate && it.startHour == hour && it.startMin == 0
                        }
                        val isSecondHalfUnavailable = room.unavailableSlots.any {
                            it.dateStr == selectedTabDate && it.startHour == hour && it.startMin == 30
                        }

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(46.dp)
                                .border(width = 0.5.dp, color = Color(0xFFE0E0E0)),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(
                                modifier = Modifier
                                    .width(64.dp)
                                    .fillMaxHeight()
                                    .background(Color(0xFFFAFAFA)),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = String.format("%02d시", hour),
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF4A3B32)
                                )
                            }

                            Box(modifier = Modifier.width(1.dp).fillMaxHeight().background(Color(0xFFE0E0E0)))

                            if (timeUnitMinutes == 60) {
                                val isHourUnavailable = isFirstHalfUnavailable || isSecondHalfUnavailable
                                val isHighlighted = if (selectAvailableModeEnabled) !isHourUnavailable else isHourUnavailable
                                val cellBg = if (selectAvailableModeEnabled) {
                                    if (isHighlighted) Color(0xFFFFECB3) else Color(0xFFFFCCBC)
                                } else {
                                    if (isHighlighted) Color(0xFFFFCCBC) else Color.White
                                }
                                val cellText = if (selectAvailableModeEnabled) {
                                    if (isHighlighted) String.format("%02d:00~%02d:00 가능", hour, hour + 1)
                                    else String.format("%02d:00~%02d:00 불가", hour, hour + 1)
                                } else {
                                    if (isHighlighted) String.format("%02d:00~%02d:00 불가", hour, hour + 1)
                                    else String.format("%02d:00~%02d:00", hour, hour + 1)
                                }
                                val cellTextColor = if (selectAvailableModeEnabled) {
                                    if (isHighlighted) Color(0xFF3C1E1E) else Color(0xFFBF360C)
                                } else {
                                    if (isHighlighted) Color(0xFFBF360C) else Color(0xFF888888)
                                }

                                Box(
                                    modifier = Modifier
                                        .weight(1f)
                                        .fillMaxHeight()
                                        .background(cellBg)
                                        .clickable { onToggleSlot(selectedTabDate, hour, 0) },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = cellText,
                                        fontSize = 11.sp,
                                        fontWeight = if (isHighlighted) FontWeight.Bold else FontWeight.Normal,
                                        color = cellTextColor
                                    )
                                }
                            } else {
                                val firstBg = if (selectAvailableModeEnabled) {
                                    if (!isFirstHalfUnavailable) Color(0xFFFFECB3) else Color(0xFFFFCCBC)
                                } else {
                                    if (isFirstHalfUnavailable) Color(0xFFFFCCBC) else Color.White
                                }
                                val firstText = if (selectAvailableModeEnabled) {
                                    if (!isFirstHalfUnavailable) String.format("%02d:00~%02d:30 가능", hour, hour)
                                    else String.format("%02d:00~%02d:30 불가", hour, hour)
                                } else {
                                    if (isFirstHalfUnavailable) String.format("%02d:00~%02d:30 불가", hour, hour)
                                    else String.format("%02d:00", hour)
                                }
                                val firstTextColor = if (selectAvailableModeEnabled) {
                                    if (!isFirstHalfUnavailable) Color(0xFF3C1E1E) else Color(0xFFBF360C)
                                } else {
                                    if (isFirstHalfUnavailable) Color(0xFFBF360C) else Color(0xFF888888)
                                }

                                Box(
                                    modifier = Modifier
                                        .weight(1f)
                                        .fillMaxHeight()
                                        .background(firstBg)
                                        .clickable { onToggleSlot(selectedTabDate, hour, 0) },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = firstText,
                                        fontSize = 11.sp,
                                        fontWeight = if (isFirstHalfUnavailable || selectAvailableModeEnabled) FontWeight.Bold else FontWeight.Normal,
                                        color = firstTextColor
                                    )
                                }

                                Box(modifier = Modifier.width(1.dp).fillMaxHeight().background(Color(0xFFE0E0E0)))

                                val secondBg = if (selectAvailableModeEnabled) {
                                    if (!isSecondHalfUnavailable) Color(0xFFFFECB3) else Color(0xFFFFCCBC)
                                } else {
                                    if (isSecondHalfUnavailable) Color(0xFFFFCCBC) else Color.White
                                }
                                val secondText = if (selectAvailableModeEnabled) {
                                    if (!isSecondHalfUnavailable) String.format("%02d:30~%02d:00 가능", hour, hour + 1)
                                    else String.format("%02d:30~%02d:00 불가", hour, hour + 1)
                                } else {
                                    if (isSecondHalfUnavailable) String.format("%02d:30~%02d:00 불가", hour, hour + 1)
                                    else String.format("%02d:30", hour)
                                }
                                val secondTextColor = if (selectAvailableModeEnabled) {
                                    if (!isSecondHalfUnavailable) Color(0xFF3C1E1E) else Color(0xFFBF360C)
                                } else {
                                    if (isSecondHalfUnavailable) Color(0xFFBF360C) else Color(0xFF888888)
                                }

                                Box(
                                    modifier = Modifier
                                        .weight(1f)
                                        .fillMaxHeight()
                                        .background(secondBg)
                                        .clickable { onToggleSlot(selectedTabDate, hour, 30) },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(
                                        text = secondText,
                                        fontSize = 11.sp,
                                        fontWeight = if (isSecondHalfUnavailable || selectAvailableModeEnabled) FontWeight.Bold else FontWeight.Normal,
                                        color = secondTextColor
                                    )
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        OutlinedButton(
                            onClick = { if (selectedTimePage > 0) selectedTimePage -= 1 },
                            enabled = selectedTimePage > 0,
                            shape = RoundedCornerShape(10.dp),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                        ) {
                            Text(text = "〈 이전 8시간", fontSize = 12.sp)
                        }
                        OutlinedButton(
                            onClick = { if (selectedTimePage < 2) selectedTimePage += 1 },
                            enabled = selectedTimePage < 2,
                            shape = RoundedCornerShape(10.dp),
                            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                        ) {
                            Text(text = "다음 8시간 〉", fontSize = 12.sp)
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(20.dp))
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(20.dp)
        ) {
            Button(
                onClick = onSaveComplete,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(text = "불가능 시간 저장", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }
}

@Composable
fun AiResultScreen(
    room: RoomModel,
    candidates: List<AiCandidateSlot>,
    voterName: String,
    onToggleVote: (candidateId: Int, voterName: String) -> Unit,
    onBackClick: () -> Unit,
    onConfirmFinal: (String) -> Unit
) {
    var selectedConfirmIndex by remember { mutableIntStateOf(0) }
    val memberTotalCount = room.participants.size.coerceAtLeast(1)

    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Text(text = "AI 결과 화면 ✨", fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, color = Color(0xFF333333))
            Text(
                text = "'${room.title}' 모임 후보 시간에 투표하고 확정 시간을 선택하세요.",
                fontSize = 13.sp,
                color = Color(0xFF777777)
            )
            Spacer(modifier = Modifier.height(16.dp))

            candidates.forEachIndexed { index, candidate ->
                val isConfirmSelected = (selectedConfirmIndex == index)
                val votedCount = candidate.voterNames.size
                val isVotedByMe = candidate.voterNames.contains(voterName)

                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp)
                        .clickable { selectedConfirmIndex = index },
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(16.dp),
                    border = BorderStroke(
                        width = if (isConfirmSelected) 2.dp else 1.dp,
                        color = if (isConfirmSelected) Color(0xFFFFB300) else Color(0xFFE0E0E0)
                    )
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = candidate.rankLabel,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (index == 0) Color(0xFFFF8F00) else Color.Gray
                            )
                            Text(
                                text = "(${votedCount}/${memberTotalCount})명 투표",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (votedCount > 0) Color(0xFF4A3B32) else Color(0xFF888888)
                            )
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = candidate.timeStr,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF333333),
                                modifier = Modifier.weight(1f)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            OutlinedButton(
                                onClick = { onToggleVote(candidate.id, voterName) },
                                colors = ButtonDefaults.outlinedButtonColors(
                                    containerColor = if (isVotedByMe) Color(0xFFFFECB3) else Color.White,
                                    contentColor = Color(0xFF3C1E1E)
                                ),
                                border = BorderStroke(
                                    1.dp,
                                    if (isVotedByMe) Color(0xFFFF8F00) else Color(0xFFD0D0D0)
                                ),
                                shape = RoundedCornerShape(12.dp),
                                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp)
                            ) {
                                Text(
                                    text = if (isVotedByMe) "투표 취소" else "투표하기",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold
                                )
                            }
                        }

                        if (candidate.voterNames.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "투표 참여: ${candidate.voterNames.joinToString(", ")}",
                                fontSize = 11.sp,
                                color = Color(0xFF888888)
                            )
                        }

                        Spacer(modifier = Modifier.height(6.dp))

                        Text(
                            text = candidate.toAvailabilitySummary(),
                            fontSize = 11.sp,
                            color = Color(0xFF666666)
                        )
                    }
                }
            }
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(20.dp)
        ) {
            val targetCandidate = candidates.getOrElse(selectedConfirmIndex) { candidates.first() }
            Button(
                onClick = {
                    onConfirmFinal(targetCandidate.timeStr)
                },
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(text = "이 시간으로 최종 확정하기", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }
}