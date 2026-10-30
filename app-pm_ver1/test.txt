package com.example.potatomeet

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.snapping.rememberSnapFlingBehavior
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.potatomeet.ui.theme.PotatoMeetTheme
import kotlinx.coroutines.launch
import java.util.Calendar

data class UserAccount(
    val nickname: String,
    val id: String,
    val pw: String,
    val twoFactorCode: String,
    var loginFailCount: Int = 0,
    var isLocked: Boolean = false
)

data class TimeSlot(
    val id: Long = System.currentTimeMillis() + (0..1000).random(),
    var month: Int,
    var day: Int,
    var startHour: Int,
    var startMin: Int,
    var endHour: Int,
    var endMin: Int
) {
    fun toFormattedString(): String {
        val sH = String.format("%02d", startHour)
        val sM = String.format("%02d", startMin)
        val eH = String.format("%02d", endHour)
        val eM = String.format("%02d", endMin)
        return "${month}월 ${day}일 ${sH}:${sM}~${eH}:${eM}"
    }

    val startTotalMinutes: Int get() = startHour * 60 + startMin
    val endTotalMinutes: Int get() = endHour * 60 + endMin
}

fun mergeTimeSlots(slots: List<TimeSlot>): List<TimeSlot> {
    if (slots.isEmpty()) return emptyList()

    val sorted = slots.sortedWith(compareBy({ it.month }, { it.day }, { it.startTotalMinutes }))
    val merged = mutableListOf<TimeSlot>()

    for (slot in sorted) {
        if (merged.isEmpty()) {
            merged.add(slot.copy())
            continue
        }

        val last = merged.last()
        if (last.month == slot.month && last.day == slot.day && last.endTotalMinutes >= slot.startTotalMinutes) {
            val newEndTotal = maxOf(last.endTotalMinutes, slot.endTotalMinutes)
            last.endHour = newEndTotal / 60
            last.endMin = newEndTotal % 60
        } else {
            merged.add(slot.copy())
        }
    }
    return merged
}

data class Appointment(
    val id: Long = System.currentTimeMillis(),
    val title: String,
    val category: String,
    val duration: String,
    val location: String,
    val timeInfo: String,
    val invitedFriends: List<String>
)

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
                        twoFactorCode = "GOOGLE_AUTH_VERIFIED"
                    )
                }

                val registeredAccount = remember { mutableStateOf<UserAccount?>(null) }
                val loggedInNickname = remember { mutableStateOf("") }
                val loggedInId = remember { mutableStateOf("") }

                val appointmentName = remember { mutableStateOf("") }
                val category = remember { mutableStateOf("") }
                val duration = remember { mutableStateOf("") }
                val location = remember { mutableStateOf("") }

                val createdTimeSlots = remember { mutableStateListOf<TimeSlot>() }
                val selectedFriendsForNew = remember { mutableStateMapOf<String, Boolean>() }
                val selectedAiRecommendationTime = remember { mutableStateOf("") }

                val appointmentsList = remember { mutableStateListOf<Appointment>() }

                val currentCalendar = remember { Calendar.getInstance() }
                var sharedCalendarYear by remember { mutableStateOf(currentCalendar.get(Calendar.YEAR)) }
                var sharedCalendarMonth by remember { mutableStateOf(currentCalendar.get(Calendar.MONTH) + 1) }
                var sharedSelectedDay by remember { mutableStateOf(currentCalendar.get(Calendar.DAY_OF_MONTH)) }

                BackHandler(enabled = currentScreen.value != "login") {
                    when (currentScreen.value) {
                        "signup" -> currentScreen.value = "login"
                        "home", "friends", "mypage" -> finish()
                        "create_step1" -> currentScreen.value = "home"
                        "create_step2" -> currentScreen.value = "create_step1"
                        "create_step3" -> currentScreen.value = "create_step2"
                        "create_step4" -> currentScreen.value = "create_step3"
                        "create_ai_recommendation" -> currentScreen.value = "create_step4"
                    }
                }

                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Color(0xFFFFFCF3)
                ) {
                    when (currentScreen.value) {
                        "login" -> {
                            LoginScreen(
                                adminAccount = adminAccount,
                                registeredAccount = registeredAccount.value,
                                onLoginSuccess = { nickname, id ->
                                    loggedInNickname.value = nickname
                                    loggedInId.value = id
                                    currentScreen.value = "home"
                                },
                                onSignUpClick = { currentScreen.value = "signup" }
                            )
                        }
                        "signup" -> {
                            SignUpScreen(
                                onCompleteClick = { newAccount ->
                                    registeredAccount.value = newAccount
                                    currentScreen.value = "login"
                                },
                                onBackClick = { currentScreen.value = "login" }
                            )
                        }
                        "home", "friends", "mypage", "create_step1", "create_step2", "create_step3", "create_step4", "create_ai_recommendation" -> {
                            Scaffold(
                                containerColor = Color(0xFFFFFCF3),
                                bottomBar = {
                                    CustomBottomBar(
                                        currentRoute = currentScreen.value,
                                        onTabSelected = { route ->
                                            currentScreen.value = route
                                        }
                                    )
                                }
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
                                                onLogoutClick = {
                                                    loggedInNickname.value = ""
                                                    currentScreen.value = "login"
                                                },
                                                onCreateAppointmentClick = {
                                                    currentScreen.value = "create_step1"
                                                },
                                                onDeleteAppointment = { appt ->
                                                    appointmentsList.remove(appt)
                                                },
                                                onUpdateAppointment = { updatedAppt ->
                                                    val index = appointmentsList.indexOfFirst { it.id == updatedAppt.id }
                                                    if (index != -1) {
                                                        appointmentsList[index] = updatedAppt
                                                    }
                                                },
                                                onEditAppointmentToCreate = { appt ->
                                                    appointmentName.value = appt.title
                                                    category.value = appt.category
                                                    duration.value = appt.duration
                                                    location.value = appt.location
                                                    appointmentsList.remove(appt)
                                                    currentScreen.value = "create_step1"
                                                }
                                            )
                                        }
                                        "friends" -> {
                                            FriendsScreen()
                                        }
                                        "mypage" -> {
                                            MyPageScreen(
                                                nickname = loggedInNickname.value.ifBlank { "사용자" },
                                                userId = loggedInId.value.ifBlank { "user@naver.com" },
                                                onLogoutClick = {
                                                    loggedInNickname.value = ""
                                                    currentScreen.value = "login"
                                                }
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
                                                onBackClick = { currentScreen.value = "home" },
                                                onNextClick = { currentScreen.value = "create_step2" },
                                                onStepClick = { step -> currentScreen.value = step }
                                            )
                                        }
                                        "create_step2" -> {
                                            CreateAppointmentStep2InviteScreen(
                                                selectedFriendsMap = selectedFriendsForNew,
                                                onBackClick = { currentScreen.value = "create_step1" },
                                                onNextClick = { currentScreen.value = "create_step3" },
                                                onStepClick = { step -> currentScreen.value = step }
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
                                                    if (inputSlot != null) {
                                                        createdTimeSlots.add(inputSlot)
                                                    }
                                                    val merged = mergeTimeSlots(createdTimeSlots)
                                                    createdTimeSlots.clear()
                                                    createdTimeSlots.addAll(merged)
                                                    currentScreen.value = "create_step4"
                                                }
                                            )
                                        }
                                        "create_step4" -> {
                                            CreateAppointmentStep4AdjustScreen(
                                                myNickname = loggedInNickname.value.ifBlank { "나" },
                                                invitedFriends = selectedFriendsForNew.filter { it.value }.keys.toList(),
                                                myTimeSlots = createdTimeSlots,
                                                onBackClick = { currentScreen.value = "create_step3" },
                                                onStepClick = { step -> currentScreen.value = step },
                                                onAiAdjustClick = { chosenTime ->
                                                    selectedAiRecommendationTime.value = chosenTime
                                                    currentScreen.value = "create_ai_recommendation"
                                                }
                                            )
                                        }
                                        "create_ai_recommendation" -> {
                                            AiRecommendationScreen(
                                                myTimeSlots = createdTimeSlots,
                                                invitedFriends = selectedFriendsForNew.filter { it.value }.keys.toList(),
                                                onBackClick = { currentScreen.value = "create_step4" },
                                                onConfirmFinal = { finalTimeStr ->
                                                    val chosenFriends = selectedFriendsForNew.filter { it.value }.keys.toList()

                                                    val newAppt = Appointment(
                                                        title = appointmentName.value.ifBlank { "제목 없는 모임" },
                                                        category = category.value.ifBlank { "기타" },
                                                        duration = duration.value.ifBlank { "시간 미정" },
                                                        location = location.value.ifBlank { "장소 미정" },
                                                        timeInfo = finalTimeStr,
                                                        invitedFriends = chosenFriends
                                                    )
                                                    appointmentsList.add(newAppt)

                                                    appointmentName.value = ""
                                                    category.value = ""
                                                    duration.value = ""
                                                    location.value = ""
                                                    createdTimeSlots.clear()
                                                    selectedFriendsForNew.clear()
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
fun CustomBottomBar(
    currentRoute: String,
    onTabSelected: (String) -> Unit
) {
    val items = listOf(
        Triple("home", "홈", "🏠"),
        Triple("create_step1", "모임만들기", "➕"),
        Triple("friends", "친구", "👥"),
        Triple("mypage", "MY", "👤")
    )

    Surface(
        modifier = Modifier.fillMaxWidth().height(65.dp),
        color = Color.White,
        shadowElevation = 8.dp
    ) {
        Row(
            modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically
        ) {
            items.forEach { (route, label, icon) ->
                val isSelected = currentRoute == route || (currentRoute.startsWith("create_") && route == "create_step1")

                Column(
                    modifier = Modifier
                        .clickable { onTabSelected(route) }
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Text(
                        text = icon,
                        fontSize = 18.sp,
                        color = if (isSelected) Color(0xFFFF9800) else Color(0xFF888888)
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = label,
                        fontSize = 11.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) Color(0xFFFF9800) else Color(0xFF888888)
                    )
                }
            }
        }
    }
}

@Composable
fun FriendsScreen() {
    val friendsList = listOf("민수", "지훈", "영희", "철수")
    Column(
        modifier = Modifier.fillMaxSize().padding(20.dp).verticalScroll(rememberScrollState())
    ) {
        Text(text = "친구 목록", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
        Spacer(modifier = Modifier.height(16.dp))

        friendsList.forEach { friend ->
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
                            Text(text = friend.take(1), fontWeight = FontWeight.Bold, color = Color.DarkGray)
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(text = friend, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    }
                    Surface(
                        color = Color(0xFFFFF3E0),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text(text = "친구", fontSize = 12.sp, color = Color(0xFFFF8F00), modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp))
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
    onLogoutClick: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(20.dp).verticalScroll(rememberScrollState())
    ) {
        Text(text = "마이페이지", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
        Spacer(modifier = Modifier.height(16.dp))

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
                    modifier = Modifier.size(60.dp).clip(CircleShape).background(Color(0xFFD7CCC8)),
                    contentAlignment = Alignment.Center
                ) {
                    Text(text = nickname.take(1), fontSize = 24.sp, fontWeight = FontWeight.Bold, color = Color.White)
                }
                Spacer(modifier = Modifier.width(16.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(text = nickname, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Text(text = userId, fontSize = 13.sp, color = Color(0xFF777777))
                }
                OutlinedButton(
                    onClick = {},
                    shape = RoundedCornerShape(20.dp),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Text(text = "프로필 수정", fontSize = 12.sp, color = Color(0xFF555555))
                }
            }
        }

        Spacer(modifier = Modifier.height(20.dp))

        val menuItems = listOf("내 캘린더", "캘린더 연결", "알림 설정", "AI 설정 (선택 시간, 요일 등)", "친구 관리", "설정", "도움말")
        menuItems.forEach { menu ->
            Card(
                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
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
fun StepIndicatorItem(
    stepNumber: String,
    title: String,
    isActive: Boolean,
    onClick: () -> Unit,
    activeTextSize: androidx.compose.ui.unit.TextUnit = 11.sp
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.clickable { onClick() }
    ) {
        Box(
            modifier = Modifier
                .size(26.dp)
                .clip(CircleShape)
                .background(if (isActive) Color(0xFFFFD54F) else Color(0xFFE0E0E0)),
            contentAlignment = Alignment.Center
        ) {
            Text(text = stepNumber, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = if (isActive) Color(0xFF3C1E1E) else Color(0xFF888888))
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = title,
            fontSize = if (isActive) activeTextSize else 10.sp,
            color = if (isActive) Color(0xFF333333) else Color(0xFFAAAAAA),
            fontWeight = if (isActive) FontWeight.Bold else FontWeight.Normal
        )
    }
}

@Composable
fun LoginScreen(
    adminAccount: UserAccount,
    registeredAccount: UserAccount?,
    onLoginSuccess: (String, String) -> Unit,
    onSignUpClick: () -> Unit
) {
    var inputId by remember { mutableStateOf("") }
    var inputPw by remember { mutableStateOf("") }
    var inputAuthCode by remember { mutableStateOf("") }
    var isGoogleVerified by remember { mutableStateOf(false) }
    val context = LocalContext.current

    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 30.dp).verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Image(
            painter = painterResource(id = R.drawable.potato_logo),
            contentDescription = "Logo",
            modifier = Modifier.size(130.dp)
        )
        Spacer(modifier = Modifier.height(10.dp))

        Text(
            text = buildAnnotatedString {
                withStyle(SpanStyle(color = Color(0xFF4A3B32), fontWeight = FontWeight.ExtraBold)) { append("potato ") }
                withStyle(SpanStyle(color = Color(0xFFFF9800), fontWeight = FontWeight.ExtraBold)) { append("meet") }
            },
            fontSize = 32.sp
        )
        Spacer(modifier = Modifier.height(6.dp))
        Text(text = "함께하는 일정, 더 쉬운 약속", fontSize = 15.sp, color = Color(0xFF666666))
        Spacer(modifier = Modifier.height(24.dp))

        OutlinedTextField(
            value = inputId,
            onValueChange = { inputId = it },
            placeholder = { Text("아이디 입력", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFFFFD54F),
                unfocusedBorderColor = Color(0xFFE0E0E0),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = inputPw,
            onValueChange = { inputPw = it },
            placeholder = { Text("비밀번호 입력", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFFFFD54F),
                unfocusedBorderColor = Color(0xFFE0E0E0),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
        Spacer(modifier = Modifier.height(10.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Button(
                onClick = {
                    isGoogleVerified = true
                    Toast.makeText(context, "구글 인증코드가 발송되었습니다!", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier.height(52.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isGoogleVerified) Color(0xFFE8F5E9) else Color(0xFFFFD54F)
                ),
                shape = RoundedCornerShape(26.dp),
                contentPadding = PaddingValues(horizontal = 12.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier.size(22.dp).clip(CircleShape).background(Color.White),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "G", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF4285F4))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = if (isGoogleVerified) "인증완료" else "인증코드 보내기",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (isGoogleVerified) Color(0xFF2E7D32) else Color(0xFF3C1E1E)
                    )
                }
            }

            OutlinedTextField(
                value = inputAuthCode,
                onValueChange = { inputAuthCode = it },
                placeholder = { Text("인증코드 입력", color = Color(0xFFAAAAAA), fontSize = 13.sp) },
                singleLine = true,
                modifier = Modifier.weight(1f).height(52.dp),
                shape = RoundedCornerShape(26.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Color(0xFFFFD54F),
                    unfocusedBorderColor = Color(0xFFE0E0E0),
                    focusedContainerColor = Color.White,
                    unfocusedContainerColor = Color.White
                )
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Button(
            onClick = {
                if (inputId == adminAccount.id && inputPw == adminAccount.pw) {
                    Toast.makeText(context, "관리자모드로 로그인되었습니다.", Toast.LENGTH_SHORT).show()
                    onLoginSuccess(adminAccount.nickname, adminAccount.id)
                } else {
                    if (inputId.isBlank()) {
                        Toast.makeText(context, "아이디를 입력하지 않았습니다.", Toast.LENGTH_SHORT).show()
                    } else if (inputPw.isBlank()) {
                        Toast.makeText(context, "비밀번호를 입력하지 않았습니다.", Toast.LENGTH_SHORT).show()
                    } else if (inputAuthCode.isBlank() && !isGoogleVerified) {
                        Toast.makeText(context, "구글 인증코드를 입력하지 않았습니다.", Toast.LENGTH_SHORT).show()
                    } else if (registeredAccount == null) {
                        Toast.makeText(context, "등록된 계정이 없습니다. 회원가입을 먼저 해주세요!", Toast.LENGTH_SHORT).show()
                    } else if (registeredAccount.isLocked) {
                        Toast.makeText(context, "비밀번호를 5회 이상 틀려 계정이 잠겼습니다. 관리자에게 문의하세요.", Toast.LENGTH_LONG).show()
                    } else if (inputId == registeredAccount.id && inputPw == registeredAccount.pw) {
                        registeredAccount.loginFailCount = 0
                        Toast.makeText(context, "${registeredAccount.nickname}님 환영합니다!", Toast.LENGTH_SHORT).show()
                        onLoginSuccess(registeredAccount.nickname, registeredAccount.id)
                    } else {
                        registeredAccount.loginFailCount++
                        val remaining = 5 - registeredAccount.loginFailCount
                        if (remaining <= 0) {
                            registeredAccount.isLocked = true
                            Toast.makeText(context, "비밀번호를 5회 이상 틀려 계정이 잠겼습니다.", Toast.LENGTH_LONG).show()
                        } else {
                            Toast.makeText(context, "정보가 일치하지 않습니다. (실패: ${registeredAccount.loginFailCount}/5, 남은 횟수: ${remaining}회)", Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4A3B32)),
            shape = RoundedCornerShape(26.dp)
        ) {
            Text(text = "로그인하기", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = Color.White)
        }

        Spacer(modifier = Modifier.height(20.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(text = "계정이 없으신가요?", fontSize = 14.sp, color = Color(0xFF999999))
            Spacer(modifier = Modifier.width(6.dp))
            TextButton(onClick = onSignUpClick, contentPadding = PaddingValues(0.dp)) {
                Text(text = "회원가입", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFB300))
            }
        }
    }
}

@Composable
fun SignUpScreen(
    onCompleteClick: (UserAccount) -> Unit,
    onBackClick: () -> Unit
) {
    var nickname by remember { mutableStateOf("") }
    var id by remember { mutableStateOf("") }
    var pw by remember { mutableStateOf("") }
    var pwConfirm by remember { mutableStateOf("") }
    var authCode by remember { mutableStateOf("") }
    var isGoogleRegistered by remember { mutableStateOf(false) }
    val context = LocalContext.current

    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 30.dp).verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Spacer(modifier = Modifier.height(10.dp))
        Text(text = "회원가입", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
        Spacer(modifier = Modifier.height(20.dp))

        OutlinedTextField(
            value = nickname,
            onValueChange = { nickname = it },
            placeholder = { Text("사용할 닉네임", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFFFFD54F),
                unfocusedBorderColor = Color(0xFFE0E0E0),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = id,
            onValueChange = { id = it },
            placeholder = { Text("아이디 (이메일 형태)", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFFFFD54F),
                unfocusedBorderColor = Color(0xFFE0E0E0),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = pw,
            onValueChange = { pw = it },
            placeholder = { Text("비밀번호", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFFFFD54F),
                unfocusedBorderColor = Color(0xFFE0E0E0),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = pwConfirm,
            onValueChange = { pwConfirm = it },
            placeholder = { Text("비밀번호 확인", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFFFFD54F),
                unfocusedBorderColor = Color(0xFFE0E0E0),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
        Spacer(modifier = Modifier.height(10.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Button(
                onClick = {
                    isGoogleRegistered = true
                    Toast.makeText(context, "구글 인증코드가 발송되었습니다!", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier.height(52.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isGoogleRegistered) Color(0xFFE8F5E9) else Color(0xFFFFD54F)
                ),
                shape = RoundedCornerShape(26.dp),
                contentPadding = PaddingValues(horizontal = 12.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier.size(22.dp).clip(CircleShape).background(Color.White),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "G", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF4285F4))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = if (isGoogleRegistered) "인증완료" else "인증코드 보내기",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (isGoogleRegistered) Color(0xFF2E7D32) else Color(0xFF3C1E1E)
                    )
                }
            }

            OutlinedTextField(
                value = authCode,
                onValueChange = { authCode = it },
                placeholder = { Text("인증코드 입력", color = Color(0xFFAAAAAA), fontSize = 13.sp) },
                singleLine = true,
                modifier = Modifier.weight(1f).height(52.dp),
                shape = RoundedCornerShape(26.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Color(0xFFFFD54F),
                    unfocusedBorderColor = Color(0xFFE0E0E0),
                    focusedContainerColor = Color.White,
                    unfocusedContainerColor = Color.White
                )
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Button(
            onClick = {
                if (nickname.isBlank()) {
                    Toast.makeText(context, "닉네임을 입력하지 않았습니다.", Toast.LENGTH_SHORT).show()
                } else if (id.isBlank()) {
                    Toast.makeText(context, "아이디를 입력하지 않았습니다.", Toast.LENGTH_SHORT).show()
                } else if (pw.isBlank()) {
                    Toast.makeText(context, "비밀번호를 입력하지 않았습니다.", Toast.LENGTH_SHORT).show()
                } else if (pwConfirm.isBlank()) {
                    Toast.makeText(context, "비밀번호 확인을 입력하지 않았습니다.", Toast.LENGTH_SHORT).show()
                } else if (authCode.isBlank() && !isGoogleRegistered) {
                    Toast.makeText(context, "구글 인증코드를 입력하지 않았습니다.", Toast.LENGTH_SHORT).show()
                } else if (pw != pwConfirm) {
                    Toast.makeText(context, "비밀번호가 일치하지 않습니다.", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(context, "회원가입이 완료되었습니다!", Toast.LENGTH_SHORT).show()
                    onCompleteClick(
                        UserAccount(
                            nickname = nickname.trim(),
                            id = id.trim(),
                            pw = pw,
                            twoFactorCode = "GOOGLE_AUTH_VERIFIED"
                        )
                    )
                }
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
            shape = RoundedCornerShape(26.dp)
        ) {
            Text(text = "회원가입 완료", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
        }

        Spacer(modifier = Modifier.height(10.dp))
        TextButton(onClick = onBackClick) {
            Text(text = "돌아가기", fontSize = 14.sp, color = Color(0xFF888888))
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun SwipableCalendarWidget(
    calendarYear: Int,
    calendarMonth: Int,
    selectedDay: Int,
    onYearChange: (Int) -> Unit,
    onMonthChange: (Int) -> Unit,
    onDayChange: (Int) -> Unit,
    onMonthSwiped: (() -> Unit)? = null,
    hasSlotOrApptCheck: (month: Int, day: Int) -> Boolean
) {
    val daysOfWeek = listOf("일", "월", "화", "수", "목", "금", "토")

    val totalPages = 4000
    val initialPage = 2000 + (calendarYear - 2026) * 12 + (calendarMonth - 1)
    val pagerState = rememberPagerState(initialPage = initialPage) { totalPages }

    LaunchedEffect(pagerState.currentPage) {
        val diffFromInitial = pagerState.currentPage - 2000
        val baseCal = Calendar.getInstance().apply {
            set(2026, Calendar.JANUARY, 1)
            add(Calendar.MONTH, diffFromInitial)
        }
        val newYear = baseCal.get(Calendar.YEAR)
        val newMonth = baseCal.get(Calendar.MONTH) + 1
        if (newYear != calendarYear || newMonth != calendarMonth) {
            onYearChange(newYear)
            onMonthChange(newMonth)
            onMonthSwiped?.invoke()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Color(0xFFFFFDF9))
            .border(1.dp, Color(0xFFFFE082), RoundedCornerShape(12.dp))
            .padding(12.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            val coroutineScope = rememberCoroutineScope()
            Text(
                text = "〈",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF4A3B32),
                modifier = Modifier
                    .clickable {
                        coroutineScope.launch {
                            pagerState.animateScrollToPage(pagerState.currentPage - 1)
                        }
                    }
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            )

            Text(
                text = "${calendarYear}년 ${calendarMonth}월",
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF4A3B32)
            )

            Text(
                text = "〉",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF4A3B32),
                modifier = Modifier
                    .clickable {
                        coroutineScope.launch {
                            pagerState.animateScrollToPage(pagerState.currentPage + 1)
                        }
                    }
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            )
        }

        Spacer(modifier = Modifier.height(10.dp))

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround) {
            daysOfWeek.forEach { dayName ->
                Text(
                    text = dayName,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (dayName == "일") Color.Red else Color(0xFF666666),
                    modifier = Modifier.weight(1f),
                    textAlign = TextAlign.Center
                )
            }
        }
        Spacer(modifier = Modifier.height(8.dp))

        HorizontalPager(
            state = pagerState,
            modifier = Modifier.fillMaxWidth().height(270.dp)
        ) { page ->
            val diff = page - 2000
            val pageCal = Calendar.getInstance().apply {
                set(2026, Calendar.JANUARY, 1)
                add(Calendar.MONTH, diff)
            }
            val pYear = pageCal.get(Calendar.YEAR)
            val pMonth = pageCal.get(Calendar.MONTH) + 1
            val pMaxDays = pageCal.getActualMaximum(Calendar.DAY_OF_MONTH)
            pageCal.set(Calendar.DAY_OF_MONTH, 1)
            val pFirstDayOfWeek = pageCal.get(Calendar.DAY_OF_WEEK) - 1
            val pTotalGridItems = pFirstDayOfWeek + pMaxDays

            LazyVerticalGrid(
                columns = GridCells.Fixed(7),
                modifier = Modifier.fillMaxSize(),
                userScrollEnabled = false
            ) {
                items(pTotalGridItems) { index ->
                    if (index < pFirstDayOfWeek) {
                        Box(modifier = Modifier.aspectRatio(1f))
                    } else {
                        val dayNumber = index - pFirstDayOfWeek + 1
                        val isSelected = (pYear == calendarYear && pMonth == calendarMonth && dayNumber == selectedDay)
                        val hasMark = hasSlotOrApptCheck(pMonth, dayNumber)

                        Box(
                            modifier = Modifier
                                .padding(2.dp)
                                .aspectRatio(1f)
                                .clip(RoundedCornerShape(12.dp))
                                .background(if (isSelected) Color(0xFFFFD54F) else Color.Transparent)
                                .border(
                                    width = if (hasMark && !isSelected) 2.5.dp else 0.dp,
                                    color = if (hasMark && !isSelected) Color(0xFFFFD54F) else Color.Transparent,
                                    shape = RoundedCornerShape(12.dp)
                                )
                                .clickable {
                                    if (pYear != calendarYear || pMonth != calendarMonth) {
                                        onYearChange(pYear)
                                        onMonthChange(pMonth)
                                    }
                                    onDayChange(dayNumber)
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center
                            ) {
                                if (hasMark) {
                                    Box(
                                        modifier = Modifier
                                            .size(4.dp)
                                            .clip(CircleShape)
                                            .background(Color.Red)
                                    )
                                    Spacer(modifier = Modifier.height(1.dp))
                                }
                                Text(
                                    text = "$dayNumber",
                                    fontSize = 13.sp,
                                    fontWeight = if (isSelected || hasMark) FontWeight.Bold else FontWeight.Normal,
                                    color = Color.Black
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
fun HomeScreen(
    nickname: String,
    appointmentsList: List<Appointment>,
    calendarYear: Int,
    onYearChange: (Int) -> Unit,
    calendarMonth: Int,
    onMonthChange: (Int) -> Unit,
    selectedDay: Int,
    onDayChange: (Int) -> Unit,
    onLogoutClick: () -> Unit,
    onCreateAppointmentClick: () -> Unit,
    onDeleteAppointment: (Appointment) -> Unit,
    onUpdateAppointment: (Appointment) -> Unit,
    onEditAppointmentToCreate: (Appointment) -> Unit
) {
    var selectedAppointment by remember { mutableStateOf<Appointment?>(null) }

    Box(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxSize()) {
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
                        text = "로그아웃",
                        fontSize = 11.sp,
                        color = Color(0xFFAAAAAA),
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .clickable { onLogoutClick() }
                            .padding(horizontal = 6.dp, vertical = 4.dp)
                    )
                }
            }

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 20.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Spacer(modifier = Modifier.height(16.dp))

                val greetingAnnotatedString = if (nickname == "관리자") {
                    buildAnnotatedString {
                        append("안녕하세요, ")
                        withStyle(SpanStyle(color = Color(0xFF2196F3), fontWeight = FontWeight.Bold)) {
                            append("관리자")
                        }
                        append("님! 👋")
                    }
                } else if (nickname.isNotBlank()) {
                    buildAnnotatedString { append("안녕하세요, ${nickname}님! 👋") }
                } else {
                    buildAnnotatedString { append("안녕하세요! 👋") }
                }

                Text(
                    text = greetingAnnotatedString,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF333333)
                )
                Text(text = "오늘도 좋은 하루 보내세요!", fontSize = 13.sp, color = Color(0xFF777777))

                Spacer(modifier = Modifier.height(26.dp))

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(18.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp)
                    ) {
                        SwipableCalendarWidget(
                            calendarYear = calendarYear,
                            calendarMonth = calendarMonth,
                            selectedDay = selectedDay,
                            onYearChange = onYearChange,
                            onMonthChange = onMonthChange,
                            onDayChange = onDayChange,
                            hasSlotOrApptCheck = { m, d ->
                                appointmentsList.any { appt ->
                                    appt.timeInfo.contains("${m}월 ${d}일")
                                }
                            }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(text = "다가오는 모임", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Text(text = "전체보기 >", fontSize = 13.sp, color = Color(0xFF888888))
                }
                Spacer(modifier = Modifier.height(10.dp))

                if (appointmentsList.isEmpty()) {
                    Box(
                        modifier = Modifier.fillMaxWidth().height(90.dp).clip(RoundedCornerShape(16.dp)).background(Color.White),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "모임이 없습니다.", fontSize = 14.sp, color = Color(0xFFAAAAAA))
                    }
                } else {
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                        modifier = Modifier.fillMaxWidth().height(200.dp)
                    ) {
                        items(appointmentsList) { appt ->
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        selectedAppointment = appt
                                    },
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
                                        Text(text = appt.title, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                                        Surface(
                                            color = Color(0xFFE8F5E9),
                                            shape = RoundedCornerShape(12.dp)
                                        ) {
                                            Text(
                                                text = "확정",
                                                fontSize = 11.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = Color(0xFF2E7D32),
                                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                            )
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(text = "📅 ${appt.timeInfo}", fontSize = 13.sp, color = Color(0xFF666666))
                                    Text(text = "📍 ${appt.location} (${appt.category})", fontSize = 13.sp, color = Color(0xFF666666))
                                }
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(80.dp))
            }
        }

        Box(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(end = 20.dp, bottom = 20.dp)
        ) {
            Button(
                onClick = onCreateAppointmentClick,
                modifier = Modifier
                    .width(130.dp)
                    .height(38.dp),
                contentPadding = PaddingValues(0.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(19.dp),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 6.dp)
            ) {
                Text(text = "+ 모임 만들기", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }

    selectedAppointment?.let { appt ->
        var showDeleteConfirm by remember { mutableStateOf(false) }

        AlertDialog(
            onDismissRequest = { selectedAppointment = null },
            containerColor = Color.White,
            title = {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "모임 상세 정보",
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF333333)
                    )
                    TextButton(onClick = { showDeleteConfirm = true }) {
                        Text(text = "🗑️ 삭제", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color.Red)
                    }
                }
            },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(text = "📌 모임 이름: ${appt.title}", fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Text(text = "🏷️ 카테고리: ${appt.category}", fontSize = 14.sp, color = Color(0xFF666666))
                    Text(text = "⏱️ 소요 시간: ${appt.duration}", fontSize = 14.sp, color = Color(0xFF666666))
                    Text(text = "📍 장소: ${appt.location}", fontSize = 14.sp, color = Color(0xFF666666))
                    Text(text = "📅 시간: ${appt.timeInfo}", fontSize = 14.sp, color = Color(0xFF666666))
                    if (appt.invitedFriends.isNotEmpty()) {
                        Text(text = "👥 초대된 친구: ${appt.invitedFriends.joinToString(", ")}", fontSize = 14.sp, color = Color(0xFF666666))
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        selectedAppointment = null
                        onEditAppointmentToCreate(appt)
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F))
                ) {
                    Text(text = "수정", color = Color(0xFF3C1E1E), fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { selectedAppointment = null }
                ) {
                    Text(text = "닫기", color = Color(0xFF888888), fontWeight = FontWeight.Bold)
                }
            }
        )

        if (showDeleteConfirm) {
            AlertDialog(
                onDismissRequest = { showDeleteConfirm = false },
                title = { Text(text = "모임 삭제", fontWeight = FontWeight.Bold) },
                text = { Text(text = "정말 모임을 삭제하시겠습니까?") },
                confirmButton = {
                    Button(
                        onClick = {
                            onDeleteAppointment(appt)
                            showDeleteConfirm = false
                            selectedAppointment = null
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color.Red)
                    ) {
                        Text(text = "삭제", color = Color.White)
                    }
                },
                dismissButton = {
                    TextButton(onClick = { showDeleteConfirm = false }) {
                        Text(text = "취소")
                    }
                }
            )
        }
    }
}

// 모임 만들기 Step 1
@Composable
fun CreateAppointmentStep1Screen(
    appointmentName: String,
    onAppointmentNameChange: (String) -> Unit,
    category: String,
    onCategoryChange: (String) -> Unit,
    duration: String,
    onDurationChange: (String) -> Unit,
    location: String,
    onLocationChange: (String) -> Unit,
    onBackClick: () -> Unit,
    onNextClick: () -> Unit,
    onStepClick: (String) -> Unit
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
            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround, verticalAlignment = Alignment.CenterVertically) {
                StepIndicatorItem(stepNumber = "1", title = "모임 정보", isActive = true, onClick = { onStepClick("create_step1") }, activeTextSize = 12.sp)
                StepIndicatorItem(stepNumber = "2", title = "친구 초대", isActive = false, onClick = { onStepClick("create_step2") })
                StepIndicatorItem(stepNumber = "3", title = "나의 시간", isActive = false, onClick = { onStepClick("create_step3") })
                StepIndicatorItem(stepNumber = "4", title = "시간 조율", isActive = false, onClick = { onStepClick("create_step4") })
            }
            Spacer(modifier = Modifier.height(20.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(text = "모임 정보", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(16.dp))

                    Text(text = "모임 이름", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(value = appointmentName, onValueChange = onAppointmentNameChange, placeholder = { Text("예) 친구들과 저녁 모임", color = Color(0xFFAAAAAA)) }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "무엇을 할까요?", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(value = category, onValueChange = onCategoryChange, placeholder = { Text("예) 식사, 카페, 스터디", color = Color(0xFFAAAAAA)) }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "예상 소요시간", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(value = duration, onValueChange = onDurationChange, placeholder = { Text("예) 2시간", color = Color(0xFFAAAAAA)) }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "장소", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(value = location, onValueChange = onLocationChange, placeholder = { Text("장소를 입력해주세요", color = Color(0xFFAAAAAA)) }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            Button(
                onClick = onNextClick,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(text = "다음", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }
}

// 모임 만들기 Step 2
@Composable
fun CreateAppointmentStep2InviteScreen(
    selectedFriendsMap: MutableMap<String, Boolean>,
    onBackClick: () -> Unit,
    onNextClick: () -> Unit,
    onStepClick: (String) -> Unit
) {
    val context = LocalContext.current
    val friendsList = listOf("민수", "지훈", "영희", "철수")

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

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround, verticalAlignment = Alignment.CenterVertically) {
                StepIndicatorItem(stepNumber = "1", title = "모임 정보", isActive = false, onClick = { onStepClick("create_step1") })
                StepIndicatorItem(stepNumber = "2", title = "친구 초대", isActive = true, onClick = { onStepClick("create_step2") }, activeTextSize = 12.sp)
                StepIndicatorItem(stepNumber = "3", title = "나의 시간", isActive = false, onClick = { onStepClick("create_step3") })
                StepIndicatorItem(stepNumber = "4", title = "시간 조율", isActive = false, onClick = { onStepClick("create_step4") })
            }
            Spacer(modifier = Modifier.height(20.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(text = "누구와 만날까요?", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(14.dp))

                    OutlinedTextField(value = "", onValueChange = {}, placeholder = { Text("친구 검색하기", color = Color(0xFFAAAAAA)) }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                    Spacer(modifier = Modifier.height(14.dp))

                    LazyColumn(modifier = Modifier.fillMaxWidth().height(300.dp)) {
                        items(friendsList) { friend ->
                            val isSelected = selectedFriendsMap[friend] ?: false
                            Row(
                                modifier = Modifier.fillMaxWidth().clickable { selectedFriendsMap[friend] = !isSelected }.padding(vertical = 8.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Box(modifier = Modifier.size(36.dp).clip(CircleShape).background(Color(0xFFE0E0E0)), contentAlignment = Alignment.Center) {
                                        Text(text = friend.take(1), fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color.DarkGray)
                                    }
                                    Spacer(modifier = Modifier.width(12.dp))
                                    Text(text = friend, fontSize = 15.sp, color = Color(0xFF333333))
                                }
                                Checkbox(checked = isSelected, onCheckedChange = { selectedFriendsMap[friend] = it }, colors = CheckboxDefaults.colors(checkedColor = Color(0xFFFFD54F)))
                            }
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = {
                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        val clip = ClipData.newPlainText("PotatoMeet Invite", "https://potatomeet.app/invite/room123")
                        clipboard.setPrimaryClip(clip)
                        Toast.makeText(context, "초대 링크가 복사되었습니다!", Toast.LENGTH_SHORT).show()
                    },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(text = "🔗 링크로 초대하기 (복사)", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                }

                Button(
                    onClick = {
                        val intent = Intent(Intent.ACTION_SEND).apply {
                            type = "text/plain"
                            setPackage("com.kakao.talk")
                            putExtra(Intent.EXTRA_TEXT, "[Potato Meet] 모임에 초대합니다! 링크: https://potatomeet.app/invite/room123")
                        }
                        try {
                            context.startActivity(intent)
                        } catch (e: Exception) {
                            val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                putExtra(Intent.EXTRA_TEXT, "[Potato Meet] 모임에 초대합니다! 링크: https://potatomeet.app/invite/room123")
                            }
                            context.startActivity(Intent.createChooser(shareIntent, "공유하기"))
                        }
                    },
                    modifier = Modifier.fillMaxWidth().height(44.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFE082))
                ) {
                    Text(text = "💛 카카오톡으로 공유하기", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                }

                Button(
                    onClick = onNextClick,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                    shape = RoundedCornerShape(26.dp)
                ) {
                    Text(text = "다음", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                }
            }
        }
    }
}

// 모임 만들기 Step 3
@Composable
fun CreateAppointmentStep3TimeScreen(
    timeSlotsList: MutableList<TimeSlot>,
    appointmentsList: List<Appointment>,
    onAddTimeSlot: (TimeSlot) -> Unit,
    onDeleteTimeSlot: (TimeSlot) -> Unit,
    calendarYear: Int,
    onYearChange: (Int) -> Unit,
    calendarMonth: Int,
    onMonthChange: (Int) -> Unit,
    selectedCalendarDay: Int,
    onDayChange: (Int) -> Unit,
    onBackClick: () -> Unit,
    onStepClick: (String) -> Unit,
    onNextClick: (TimeSlot?) -> Unit
) {
    var showTimePickerModal by remember { mutableStateOf(false) }

    val currentCalendar = remember { Calendar.getInstance() }
    val curHour = currentCalendar.get(Calendar.HOUR_OF_DAY)
    val curMin = (currentCalendar.get(Calendar.MINUTE) / 10) * 10
    val endHourVal = if (curHour + 2 <= 24) curHour + 2 else 24

    var inputMonth by remember { mutableStateOf(calendarMonth.toString()) }
    var inputDay by remember { mutableStateOf(selectedCalendarDay.toString()) }
    var inputStartHour by remember { mutableStateOf(String.format("%02d", curHour)) }
    var inputStartMin by remember { mutableStateOf(String.format("%02d", curMin)) }
    var inputEndHour by remember { mutableStateOf(String.format("%02d", endHourVal)) }
    var inputEndMin by remember { mutableStateOf(String.format("%02d", curMin)) }

    LaunchedEffect(calendarMonth, selectedCalendarDay) {
        inputMonth = calendarMonth.toString()
        inputDay = selectedCalendarDay.toString()
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
                .weight(1f)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround, verticalAlignment = Alignment.CenterVertically) {
                StepIndicatorItem(stepNumber = "1", title = "모임 정보", isActive = false, onClick = { onStepClick("create_step1") })
                StepIndicatorItem(stepNumber = "2", title = "친구 초대", isActive = false, onClick = { onStepClick("create_step2") })
                StepIndicatorItem(stepNumber = "3", title = "나의 시간", isActive = true, onClick = { onStepClick("create_step3") }, activeTextSize = 12.sp)
                StepIndicatorItem(stepNumber = "4", title = "시간 조율", isActive = false, onClick = { onStepClick("create_step4") })
            }
            Spacer(modifier = Modifier.height(20.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(18.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {

                    SwipableCalendarWidget(
                        calendarYear = calendarYear,
                        calendarMonth = calendarMonth,
                        selectedDay = selectedCalendarDay,
                        onYearChange = onYearChange,
                        onMonthChange = onMonthChange,
                        onDayChange = {
                            onDayChange(it)
                            showTimePickerModal = true
                        },
                        hasSlotOrApptCheck = { m, d ->
                            timeSlotsList.any { slot ->
                                slot.month == m && slot.day == d
                            } || appointmentsList.any { appt ->
                                appt.timeInfo.contains("${m}월 ${d}일")
                            }
                        }
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    Column(
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        timeSlotsList.forEach { slot ->
                            var editM by remember { mutableStateOf(slot.month.toString()) }
                            var editD by remember { mutableStateOf(slot.day.toString()) }
                            var editSh by remember { mutableStateOf(String.format("%02d", slot.startHour)) }
                            var editSm by remember { mutableStateOf(String.format("%02d", slot.startMin)) }
                            var editEh by remember { mutableStateOf(String.format("%02d", slot.endHour)) }
                            var editEm by remember { mutableStateOf(String.format("%02d", slot.endMin)) }

                            LaunchedEffect(editM, editD, editSh, editSm, editEh, editEm) {
                                slot.month = editM.toIntOrNull() ?: slot.month
                                slot.day = editD.toIntOrNull() ?: slot.day
                                slot.startHour = editSh.toIntOrNull() ?: slot.startHour
                                slot.startMin = editSm.toIntOrNull() ?: slot.startMin
                                slot.endHour = editEh.toIntOrNull() ?: slot.endHour
                                slot.endMin = editEm.toIntOrNull() ?: slot.endMin
                            }

                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clip(RoundedCornerShape(12.dp))
                                    .background(Color.White)
                                    .border(1.dp, Color(0xFFFFE082), RoundedCornerShape(12.dp))
                                    .padding(horizontal = 12.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    modifier = Modifier.weight(1f)
                                ) {
                                    SeamlessInputBox(
                                        value = editM,
                                        onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) editM = it }
                                    )
                                    Text(text = "월 ", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))

                                    SeamlessInputBox(
                                        value = editD,
                                        onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) editD = it }
                                    )
                                    Text(text = "일 ", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))

                                    SeamlessInputBox(
                                        value = editSh,
                                        onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) editSh = it }
                                    )
                                    Text(text = ":", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                    SeamlessInputBox(
                                        value = editSm,
                                        onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) editSm = it }
                                    )

                                    Text(text = " ~ ", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                    SeamlessInputBox(
                                        value = editEh,
                                        onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) editEh = it }
                                    )
                                    Text(text = ":", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                    SeamlessInputBox(
                                        value = editEm,
                                        onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) editEm = it }
                                    )
                                }

                                Box(
                                    modifier = Modifier
                                        .size(28.dp)
                                        .clip(RoundedCornerShape(8.dp))
                                        .clickable { onDeleteTimeSlot(slot) },
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text(text = "❌", fontSize = 11.sp)
                                }
                            }
                        }

                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .background(Color.White)
                                .border(1.dp, Color(0xFFFFE082), RoundedCornerShape(12.dp))
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.weight(1f)
                            ) {
                                SeamlessInputBox(
                                    value = inputMonth,
                                    onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) inputMonth = it }
                                )
                                Text(text = "월 ", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))

                                SeamlessInputBox(
                                    value = inputDay,
                                    onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) inputDay = it }
                                )
                                Text(text = "일 ", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))

                                SeamlessInputBox(
                                    value = inputStartHour,
                                    onValueChange = { newSH ->
                                        if (newSH.length <= 2 && newSH.all { it.isDigit() }) {
                                            val oldSH = inputStartHour.toIntOrNull() ?: 0
                                            inputStartHour = newSH
                                            val shVal = newSH.toIntOrNull() ?: 0
                                            val ehVal = inputEndHour.toIntOrNull() ?: 0

                                            val diff = ehVal - oldSH
                                            var newEH = shVal + if (diff > 0) diff else 2
                                            if (newEH > 24) newEH = 24
                                            inputEndHour = String.format("%02d", newEH)
                                        }
                                    }
                                )
                                Text(text = ":", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                SeamlessInputBox(
                                    value = inputStartMin,
                                    onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) inputStartMin = it }
                                )

                                Text(text = " ~ ", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                SeamlessInputBox(
                                    value = inputEndHour,
                                    onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) inputEndHour = it }
                                )
                                Text(text = ":", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                SeamlessInputBox(
                                    value = inputEndMin,
                                    onValueChange = { if (it.length <= 2 && it.all { c -> c.isDigit() }) inputEndMin = it }
                                )
                            }

                            Button(
                                onClick = {
                                    val m = inputMonth.toIntOrNull() ?: calendarMonth
                                    val d = inputDay.toIntOrNull() ?: selectedCalendarDay
                                    val sH = inputStartHour.toIntOrNull() ?: curHour
                                    val sM = inputStartMin.toIntOrNull() ?: curMin
                                    val eH = inputEndHour.toIntOrNull() ?: endHourVal
                                    val eM = inputEndMin.toIntOrNull() ?: curMin

                                    val slot = TimeSlot(
                                        month = m,
                                        day = d,
                                        startHour = sH,
                                        startMin = sM,
                                        endHour = eH,
                                        endMin = eM
                                    )
                                    onAddTimeSlot(slot)
                                },
                                modifier = Modifier.size(36.dp),
                                contentPadding = PaddingValues(0.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text(text = "+", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                            }
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            Button(
                onClick = {
                    val m = inputMonth.toIntOrNull() ?: calendarMonth
                    val d = inputDay.toIntOrNull() ?: selectedCalendarDay
                    val sH = inputStartHour.toIntOrNull() ?: curHour
                    val sM = inputStartMin.toIntOrNull() ?: curMin
                    val eH = inputEndHour.toIntOrNull() ?: endHourVal
                    val eM = inputEndMin.toIntOrNull() ?: curMin

                    val currentInputSlot = TimeSlot(
                        month = m,
                        day = d,
                        startHour = sH,
                        startMin = sM,
                        endHour = eH,
                        endMin = eM
                    )
                    onNextClick(currentInputSlot)
                },
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(text = "다음", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }

    if (showTimePickerModal) {
        val amPmList = listOf("오전", "오후")
        val hours12List = (1..12).toList()
        val minutesList = listOf(0, 10, 20, 30, 40, 50)

        val defaultAmPm = if (curHour >= 12) 1 else 0
        val default12Hour = if (curHour == 0) 12 else if (curHour > 12) curHour - 12 else curHour

        var startAmPmIndex by remember { mutableStateOf(defaultAmPm) }
        var startHour12 by remember { mutableStateOf(default12Hour) }
        var startMin by remember { mutableStateOf(curMin) }

        var endAmPmIndex by remember { mutableStateOf(if (endHourVal >= 12) 1 else 0) }
        var endHour12 by remember { mutableStateOf(if (endHourVal == 0) 12 else if (endHourVal > 12) endHourVal - 12 else endHourVal) }
        var endMin by remember { mutableStateOf(curMin) }

        AlertDialog(
            onDismissRequest = { showTimePickerModal = false },
            containerColor = Color.White,
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(text = "시작 시간", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFF8F00))
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        LockWheelColumn(
                            items = amPmList,
                            selectedIndex = startAmPmIndex,
                            widthDp = 54,
                            onSelect = { startAmPmIndex = it }
                        )
                        LockWheelColumn(
                            items = hours12List.map { String.format("%02d시", it) },
                            selectedIndex = hours12List.indexOf(startHour12),
                            widthDp = 54,
                            onSelect = { idx -> startHour12 = hours12List[idx] }
                        )
                        Text(text = ":", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                        LockWheelColumn(
                            items = minutesList.map { String.format("%02d분", it) },
                            selectedIndex = minutesList.indexOf(startMin),
                            widthDp = 54,
                            onSelect = { startMin = minutesList[it] }
                        )
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(text = "종료 시간", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFF8F00))
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        LockWheelColumn(
                            items = amPmList,
                            selectedIndex = endAmPmIndex,
                            widthDp = 54,
                            onSelect = { endAmPmIndex = it }
                        )
                        LockWheelColumn(
                            items = hours12List.map { String.format("%02d시", it) },
                            selectedIndex = hours12List.indexOf(endHour12),
                            widthDp = 54,
                            onSelect = { idx -> endHour12 = hours12List[idx] }
                        )
                        Text(text = ":", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                        LockWheelColumn(
                            items = minutesList.map { String.format("%02d분", it) },
                            selectedIndex = minutesList.indexOf(endMin),
                            widthDp = 54,
                            onSelect = { endMin = minutesList[it] }
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        fun convertTo24Hour(amPmIdx: Int, hour12: Int): Int {
                            var h = hour12 % 12
                            if (amPmIdx == 1) h += 12
                            return h
                        }

                        val calculatedStartHour = convertTo24Hour(startAmPmIndex, startHour12)
                        val calculatedEndHour = convertTo24Hour(endAmPmIndex, endHour12)

                        inputStartHour = String.format("%02d", calculatedStartHour)
                        inputStartMin = String.format("%02d", startMin)
                        inputEndHour = String.format("%02d", calculatedEndHour)
                        inputEndMin = String.format("%02d", endMin)

                        val slot = TimeSlot(
                            month = calendarMonth,
                            day = selectedCalendarDay,
                            startHour = calculatedStartHour,
                            startMin = startMin,
                            endHour = calculatedEndHour,
                            endMin = endMin
                        )
                        onAddTimeSlot(slot)
                        showTimePickerModal = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F))
                ) {
                    Text(text = "+", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                }
            },
            dismissButton = {
                TextButton(onClick = { showTimePickerModal = false }) {
                    Text(text = "취소", color = Color.Gray)
                }
            }
        )
    }
}

// 모임 만들기 Step 4 (시간 조율 화면 - 가로 스크롤 그래프 반영)
@Composable
fun CreateAppointmentStep4AdjustScreen(
    myNickname: String,
    invitedFriends: List<String>,
    myTimeSlots: List<TimeSlot>,
    onBackClick: () -> Unit,
    onStepClick: (String) -> Unit,
    onAiAdjustClick: (String) -> Unit
) {
    val realMyName = myNickname.ifBlank { "나" }
    val activeMembers = listOf(realMyName) + invitedFriends

    // 0시부터 24시까지 1시간 단위 24개 구간
    // 친구별 가능 시간 (0: 불가, 1: 가능)
    val friendRanges = mapOf(
        "민수" to Pair(0, 24),   // 24시간 모두 가능
        "지훈" to Pair(0, 12),   // 오전만 가능 (0시~12시)
        "영희" to Pair(12, 24),  // 오후만 가능 (12시~24시)
        "철수" to Pair(11, 17)   // 11시 ~ 17시 가능
    )

    val headerDateStr = if (myTimeSlots.isNotEmpty()) {
        "${myTimeSlots[0].month}월 ${myTimeSlots[0].day}일"
    } else {
        "10월 14일"
    }

    val horizontalScrollState = rememberScrollState()

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

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceAround,
                verticalAlignment = Alignment.CenterVertically
            ) {
                StepIndicatorItem(stepNumber = "1", title = "정보", isActive = false, onClick = { onStepClick("create_step1") })
                StepIndicatorItem(stepNumber = "2", title = "초대", isActive = false, onClick = { onStepClick("create_step2") })
                StepIndicatorItem(stepNumber = "3", title = "나의 시간", isActive = false, onClick = { onStepClick("create_step3") })
                StepIndicatorItem(stepNumber = "4", title = "시간 조율", isActive = true, onClick = { onStepClick("create_step4") }, activeTextSize = 12.sp)
            }
            Spacer(modifier = Modifier.height(20.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "$headerDateStr (화)",
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333)
                        )
                        Text(
                            text = "👈 좌우로 드래그해서 확인",
                            fontSize = 11.sp,
                            color = Color(0xFFFF8F00),
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    // 가로 스크롤 영역 (친구 프로필 고정 + 시간 그래프 드래그)
                    Row(modifier = Modifier.fillMaxWidth()) {
                        // 왼쪽 고정: 멤버 목록
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            // 시간 헤더 높이만큼 여백
                            Box(modifier = Modifier.height(24.dp).width(65.dp), contentAlignment = Alignment.CenterStart) {
                                Text(text = "이름", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFF888888))
                            }
                            activeMembers.forEach { memberName ->
                                Row(
                                    modifier = Modifier.height(24.dp).width(65.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Box(
                                        modifier = Modifier.size(22.dp).clip(CircleShape).background(Color(0xFFE0E0E0)),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text(text = memberName.take(1), fontSize = 10.sp, fontWeight = FontWeight.Bold, color = Color.DarkGray)
                                    }
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(text = memberName, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                                }
                            }
                        }

                        Spacer(modifier = Modifier.width(8.dp))

                        // 오른쪽 스크롤: 0시~24시 시간축 및 그래프
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .horizontalScroll(horizontalScrollState)
                        ) {
                            // 상단 시간 눈금 (0시 ~ 24시)
                            Row(modifier = Modifier.padding(bottom = 8.dp)) {
                                (0..24 step 2).forEach { hour ->
                                    Box(
                                        modifier = Modifier.width(50.dp),
                                        contentAlignment = Alignment.CenterStart
                                    ) {
                                        Text(text = "${hour}시", fontSize = 11.sp, color = Color(0xFFAAAAAA))
                                    }
                                }
                            }

                            // 멤버별 시간 바 (0시~24시 = 총 600dp 너비)
                            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                activeMembers.forEach { memberName ->
                                    Row(
                                        modifier = Modifier
                                            .width(625.dp)
                                            .height(24.dp),
                                        horizontalArrangement = Arrangement.spacedBy(2.dp)
                                    ) {
                                        (0..23).forEach { hour ->
                                            val isAvailable = if (memberName == realMyName) {
                                                myTimeSlots.any { slot -> hour in slot.startHour until slot.endHour }
                                            } else {
                                                val range = friendRanges[memberName] ?: Pair(0, 0)
                                                hour in range.first until range.second
                                            }

                                            Box(
                                                modifier = Modifier
                                                    .weight(1f)
                                                    .fillMaxHeight()
                                                    .clip(RoundedCornerShape(4.dp))
                                                    .background(if (isAvailable) Color(0xFF81C784) else Color(0xFFF5F5F5))
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(modifier = Modifier.size(10.dp).clip(CircleShape).background(Color(0xFF81C784)))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(text = "가능 시간", fontSize = 12.sp, color = Color(0xFF666666))
                        }
                        Spacer(modifier = Modifier.width(20.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(modifier = Modifier.size(10.dp).clip(CircleShape).background(Color(0xFFF5F5F5)))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(text = "불가", fontSize = 12.sp, color = Color(0xFF666666))
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            Button(
                onClick = {
                    val timeStr = if (myTimeSlots.isNotEmpty()) {
                        myTimeSlots[0].toFormattedString() + " (AI 조율)"
                    } else {
                        "$headerDateStr 18:30 ~ 20:30 (AI 조율)"
                    }
                    onAiAdjustClick(timeStr)
                },
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(text = "AI 조율", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }
}

// AI 일정 추천 화면
data class RecommendationOption(
    val rank: String,
    val rankColor: Color,
    val timeText: String,
    val infoText: String,
    val fitRate: String
)

@Composable
fun AiRecommendationScreen(
    myTimeSlots: List<TimeSlot>,
    invitedFriends: List<String>,
    onBackClick: () -> Unit,
    onConfirmFinal: (String) -> Unit
) {
    var selectedIndex by remember { mutableStateOf(0) }

    val overlappingRecommendations = remember(myTimeSlots, invitedFriends) {
        val totalPeople = 1 + invitedFriends.size
        val baseSlots = if (myTimeSlots.isNotEmpty()) {
            myTimeSlots
        } else {
            listOf(TimeSlot(month = 10, day = 14, startHour = 14, startMin = 0, endHour = 16, endMin = 0))
        }

        val friendRanges = mapOf(
            "민수" to Pair(0, 24),   // 24시간 모두
            "지훈" to Pair(0, 12),   // 오전만
            "영희" to Pair(12, 24),  // 오후만
            "철수" to Pair(11, 17)   // 11시 ~ 17시
        )

        val resultList = mutableListOf<RecommendationOption>()

        baseSlots.forEach { mySlot ->
            var overlapStartMinutes = mySlot.startTotalMinutes
            var overlapEndMinutes = mySlot.endTotalMinutes

            for (friend in invitedFriends) {
                val range = friendRanges[friend] ?: Pair(0, 24)
                val friendStartMin = range.first * 60
                val friendEndMin = range.second * 60

                overlapStartMinutes = maxOf(overlapStartMinutes, friendStartMin)
                overlapEndMinutes = minOf(overlapEndMinutes, friendEndMin)
            }

            if (overlapEndMinutes > overlapStartMinutes) {
                val sH = String.format("%02d", overlapStartMinutes / 60)
                val sM = String.format("%02d", overlapStartMinutes % 60)
                val eH = String.format("%02d", overlapEndMinutes / 60)
                val eM = String.format("%02d", overlapEndMinutes % 60)

                val slotStr = "${mySlot.month}월 ${mySlot.day}일 ${sH}:${sM}~${eH}:${eM}"
                resultList.add(
                    RecommendationOption(
                        rank = "${resultList.size + 1}위",
                        rankColor = when (resultList.size) {
                            0 -> Color(0xFFFFB300)
                            1 -> Color(0xFFB0BEC5)
                            else -> Color(0xFFA1887F)
                        },
                        timeText = slotStr,
                        infoText = "${totalPeople}명 모두 가능",
                        fitRate = "${100 - (resultList.size * 5)}%"
                    )
                )
            }
        }
        resultList
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
                .weight(1f)
                .padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "AI가 최적의 시간을 찾았어요!",
                fontSize = 22.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color(0xFF333333),
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(24.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Start
            ) {
                Text(
                    text = "추천 시간",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF333333)
                )
            }
            Spacer(modifier = Modifier.height(12.dp))

            if (overlappingRecommendations.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(120.dp)
                        .background(Color.White, RoundedCornerShape(16.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "모두 겹치는 시간이 없습니다 😢\n시간대를 다시 조율해보세요.",
                        fontSize = 14.sp,
                        color = Color(0xFF888888),
                        textAlign = TextAlign.Center
                    )
                }
            } else {
                overlappingRecommendations.forEachIndexed { index, option ->
                    RecommendationCard(
                        rank = option.rank,
                        rankColor = option.rankColor,
                        dateText = option.timeText,
                        infoText = option.infoText,
                        fitRate = option.fitRate,
                        isSelected = selectedIndex == index,
                        onClick = { selectedIndex = index }
                    )
                    Spacer(modifier = Modifier.height(10.dp))
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "왜 이 시간이 좋나요?",
                fontSize = 13.sp,
                color = Color(0xFFFF8F00),
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(16.dp))
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFFFFCF3))
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            Button(
                onClick = {
                    if (overlappingRecommendations.isNotEmpty()) {
                        val finalChosenStr = overlappingRecommendations[selectedIndex].timeText
                        onConfirmFinal(finalChosenStr)
                    }
                },
                enabled = overlappingRecommendations.isNotEmpty(),
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFFFFD54F),
                    disabledContainerColor = Color(0xFFE0E0E0)
                ),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(
                    text = "이 시간으로 확정하기",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (overlappingRecommendations.isNotEmpty()) Color(0xFF3C1E1E) else Color.Gray
                )
            }
        }
    }
}

@Composable
fun RecommendationCard(
    rank: String,
    rankColor: Color,
    dateText: String,
    infoText: String,
    fitRate: String,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        colors = CardDefaults.cardColors(containerColor = Color.White),
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(width = if (isSelected) 2.dp else 1.dp, color = if (isSelected) Color(0xFFFFB300) else Color(0xFFE0E0E0)),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(text = "👑 $rank", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = rankColor)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(text = dateText, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(text = "👤 $infoText", fontSize = 13.sp, color = Color(0xFF666666))
                Text(
                    text = "적합도 $fitRate",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF2E7D32)
                )
            }
        }
    }
}

@Composable
fun SeamlessInputBox(value: String, onValueChange: (String) -> Unit) {
    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        textStyle = TextStyle(
            fontSize = 13.sp,
            fontWeight = FontWeight.Bold,
            color = Color(0xFFFF8F00),
            textAlign = TextAlign.Center
        ),
        modifier = Modifier
            .width(24.dp)
            .padding(horizontal = 1.dp)
    )
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun LockWheelColumn(
    items: List<String>,
    selectedIndex: Int,
    widthDp: Int = 62,
    onSelect: (Int) -> Unit
) {
    val validIndex = if (selectedIndex in items.indices) selectedIndex else 0
    val listState = rememberLazyListState(initialFirstVisibleItemIndex = validIndex)
    val snapFlingBehavior = rememberSnapFlingBehavior(lazyListState = listState)
    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(listState.isScrollInProgress) {
        if (!listState.isScrollInProgress) {
            val layoutInfo = listState.layoutInfo
            val visibleItems = layoutInfo.visibleItemsInfo
            if (visibleItems.isNotEmpty()) {
                val containerCenter = layoutInfo.viewportStartOffset + (layoutInfo.viewportEndOffset - layoutInfo.viewportStartOffset) / 2
                val closestItem = visibleItems.minByOrNull { item ->
                    kotlin.math.abs((item.offset + item.size / 2) - containerCenter)
                }
                closestItem?.let {
                    if (it.index in items.indices && it.index != validIndex) {
                        onSelect(it.index)
                    }
                }
            }
        }
    }

    Box(
        modifier = Modifier
            .width(widthDp.dp)
            .height(76.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(Color.White)
            .border(1.dp, Color(0xFFFFE082), RoundedCornerShape(10.dp)),
        contentAlignment = Alignment.Center
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(26.dp)
                .background(Color(0xFFFFECB3).copy(alpha = 0.4f), RoundedCornerShape(6.dp))
        )

        LazyColumn(
            state = listState,
            flingBehavior = snapFlingBehavior,
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            contentPadding = PaddingValues(vertical = 25.dp)
        ) {
            items(items.size) { index ->
                val isSelected = index == validIndex
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(26.dp)
                        .clickable {
                            onSelect(index)
                            coroutineScope.launch {
                                listState.animateScrollToItem(index)
                            }
                        },
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = items[index],
                        fontSize = if (isSelected) 12.sp else 10.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) Color(0xFFFF8F00) else Color(0xFFB0BEC5)
                    )
                }
            }
        }
    }
}