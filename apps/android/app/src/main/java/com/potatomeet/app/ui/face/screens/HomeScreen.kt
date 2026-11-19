package com.potatomeet.app.ui.face.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.snapping.rememberSnapFlingBehavior
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.runtime.snapshots.SnapshotStateMap
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
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.R
import kotlinx.coroutines.launch
import java.util.Calendar
import com.potatomeet.app.ui.face.Appointment
import com.potatomeet.app.ui.face.RecommendationOption
import com.potatomeet.app.ui.face.TimeSlot
import com.potatomeet.app.ui.face.UserAccount
import com.potatomeet.app.ui.face.mergeTimeSlots
import com.potatomeet.app.ui.face.components.CustomBottomBar
import com.potatomeet.app.ui.face.components.LockWheelColumn
import com.potatomeet.app.ui.face.components.RecommendationCard
import com.potatomeet.app.ui.face.components.SeamlessInputBox
import com.potatomeet.app.ui.face.components.StepIndicatorItem
import com.potatomeet.app.ui.face.components.SwipableCalendarWidget
import com.potatomeet.app.ui.face.components.TopLogoHeader

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
    onEditAppointmentToCreate: (Appointment) -> Unit,
    onOpenAppointment: (Appointment) -> Unit = {},
    onJoinClick: (code: String, joinNickname: String) -> Unit = { _, _ -> },
    isMutating: Boolean = false,
) {
    var selectedAppointment by remember { mutableStateOf<Appointment?>(null) }
    var showJoinDialog by remember { mutableStateOf(false) }
    var joinCode by remember { mutableStateOf("") }
    var joinNickname by remember { mutableStateOf("") }

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
                            hasSlotOrApptCheck = { m: Int, d: Int ->
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
                    Text(
                        text = "초대 코드로 참여",
                        fontSize = 13.sp,
                        color = Color(0xFFFF9800),
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable { showJoinDialog = true },
                    )
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
                                        val statusTriple =
                                            when (appt.status.uppercase()) {
                                                "CONFIRMED" -> Triple("확정", Color(0xFFE8F5E9), Color(0xFF2E7D32))
                                                "VOTING" -> Triple("투표", Color(0xFFFFF3E0), Color(0xFFE65100))
                                                "FAILED" -> Triple("불가", Color(0xFFFFEBEE), Color(0xFFC62828))
                                                else -> Triple("입력", Color(0xFFE3F2FD), Color(0xFF1565C0))
                                            }
                                        Surface(
                                            color = statusTriple.second,
                                            shape = RoundedCornerShape(12.dp)
                                        ) {
                                            Text(
                                                text = statusTriple.first,
                                                fontSize = 11.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = statusTriple.third,
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
                    if (appt.isOwner || appt.meetingId.isBlank()) {
                        TextButton(onClick = { showDeleteConfirm = true }) {
                            Text(text = "🗑️ 삭제", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color.Red)
                        }
                    }
                }
            },
            text = {
                Column(
                    modifier = Modifier.verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(text = "📌 모임 이름: ${appt.title}", fontSize = 15.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    if (appt.code.isNotBlank()) {
                        Text(text = "🔑 초대 코드: ${appt.code}", fontSize = 14.sp, color = Color(0xFFFF9800), fontWeight = FontWeight.Bold)
                    }
                    Text(text = "🏷️ 상태: ${appt.status.ifBlank { appt.category }}", fontSize = 14.sp, color = Color(0xFF666666))
                    Text(text = "⏱️ 소요 시간: ${appt.duration}", fontSize = 14.sp, color = Color(0xFF666666))
                    Text(text = "📍 장소: ${appt.location}", fontSize = 14.sp, color = Color(0xFF666666))
                    Text(text = "📅 시간: ${appt.timeInfo}", fontSize = 14.sp, color = Color(0xFF666666))
                    if (appt.invitedFriends.isNotEmpty()) {
                        Text(text = "👥 멤버: ${appt.invitedFriends.joinToString(", ")}", fontSize = 14.sp, color = Color(0xFF666666))
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        selectedAppointment = null
                        if (appt.meetingId.isNotBlank()) {
                            onOpenAppointment(appt)
                        } else {
                            onEditAppointmentToCreate(appt)
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F))
                ) {
                    Text(
                        text = if (appt.meetingId.isNotBlank()) "열기" else "수정",
                        color = Color(0xFF3C1E1E),
                        fontWeight = FontWeight.Bold,
                    )
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

    if (showJoinDialog) {
        AlertDialog(
            onDismissRequest = { if (!isMutating) showJoinDialog = false },
            containerColor = Color.White,
            title = { Text(text = "초대 코드로 참여", fontWeight = FontWeight.Bold) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(
                        value = joinCode,
                        onValueChange = { joinCode = it.uppercase().take(8) },
                        enabled = !isMutating,
                        placeholder = { Text("8자리 코드", color = Color(0xFFAAAAAA)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                    OutlinedTextField(
                        value = joinNickname,
                        onValueChange = { joinNickname = it },
                        enabled = !isMutating,
                        placeholder = { Text("이 모임에서 쓸 닉네임", color = Color(0xFFAAAAAA)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        onJoinClick(joinCode, joinNickname)
                        showJoinDialog = false
                        joinCode = ""
                        joinNickname = ""
                    },
                    enabled = !isMutating,
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                ) {
                    Text(text = "참여", color = Color(0xFF3C1E1E), fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showJoinDialog = false }, enabled = !isMutating) {
                    Text(text = "취소", color = Color(0xFF888888))
                }
            },
        )
    }
}

// 모임 만들기 Step 1
