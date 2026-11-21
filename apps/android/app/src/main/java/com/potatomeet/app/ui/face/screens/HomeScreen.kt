package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.ui.face.Appointment
import com.potatomeet.app.ui.face.components.TopLogoHeader

@Composable
fun HomeScreen(
    nickname: String,
    appointmentsList: List<Appointment>,
    onLogoutClick: () -> Unit,
    onCreateAppointmentClick: () -> Unit,
    onOpenAppointment: (Appointment) -> Unit,
    onDeleteAppointment: (Appointment) -> Unit = {},
    onFriendsClick: () -> Unit = {},
    onMyPageClick: () -> Unit = {},
    onJoinClick: (code: String) -> Unit = {},
    isMutating: Boolean = false,
) {
    var showJoinDialog by remember { mutableStateOf(false) }
    var joinCode by remember { mutableStateOf("") }
    var pendingDelete by remember { mutableStateOf<Appointment?>(null) }

    Box(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState()),
        ) {
            Box(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .background(Color(0xFFFFFCF3))
                        .padding(horizontal = 20.dp, vertical = 12.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TopLogoHeader()
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = "친구",
                            fontSize = 13.sp,
                            color = Color(0xFF555555),
                            fontWeight = FontWeight.Bold,
                            modifier =
                                Modifier
                                    .clickable { onFriendsClick() }
                                    .padding(4.dp),
                        )
                        Text(
                            text = "MY",
                            fontSize = 13.sp,
                            color = Color(0xFF555555),
                            fontWeight = FontWeight.Bold,
                            modifier =
                                Modifier
                                    .clickable { onMyPageClick() }
                                    .padding(4.dp),
                        )
                        Text(
                            text = "로그아웃",
                            fontSize = 11.sp,
                            color = Color(0xFFAAAAAA),
                            modifier =
                                Modifier
                                    .clickable { onLogoutClick() }
                                    .padding(4.dp),
                        )
                    }
                }
            }

            Column(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp),
            ) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "${nickname.ifBlank { "사용자" }}님, 안녕하세요",
                    fontSize = 13.sp,
                    color = Color(0xFF888888),
                )
                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "모임 현황",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF333333),
                    )
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
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .height(250.dp)
                                .background(Color.White, RoundedCornerShape(16.dp)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                text = "모임이 없습니다. 모임을 추가하시겠습니까?",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF666666),
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Button(
                                onClick = onCreateAppointmentClick,
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                                shape = RoundedCornerShape(20.dp),
                            ) {
                                Text(
                                    text = "모임 추가하기",
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF3C1E1E),
                                )
                            }
                        }
                    }
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        appointmentsList.forEach { appt ->
                            val confirmed = appt.status.equals("CONFIRMED", ignoreCase = true)
                            Card(
                                modifier =
                                    Modifier
                                        .fillMaxWidth()
                                        .clickable { onOpenAppointment(appt) },
                                colors = CardDefaults.cardColors(containerColor = Color.White),
                                shape = RoundedCornerShape(16.dp),
                                elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                            ) {
                                Column(modifier = Modifier.padding(16.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        Text(
                                            text =
                                                if (confirmed) {
                                                    "[확정완료] ${appt.title}"
                                                } else {
                                                    appt.title
                                                },
                                            fontSize = 16.sp,
                                            fontWeight = FontWeight.Bold,
                                            color =
                                                if (confirmed) {
                                                    Color(0xFF2E7D32)
                                                } else {
                                                    Color(0xFF333333)
                                                },
                                            modifier = Modifier.weight(1f),
                                        )
                                        if (confirmed) {
                                            Surface(
                                                color = Color(0xFFE8F5E9),
                                                shape = RoundedCornerShape(6.dp),
                                            ) {
                                                Text(
                                                    text = "확정",
                                                    fontSize = 11.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = Color(0xFF2E7D32),
                                                    modifier =
                                                        Modifier.padding(
                                                            horizontal = 6.dp,
                                                            vertical = 2.dp,
                                                        ),
                                                )
                                            }
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(6.dp))
                                    Text(
                                        text =
                                            when {
                                                confirmed -> "📅 확정 · ${appt.timeInfo}"
                                                appt.selectedDates.isNotEmpty() ->
                                                    "📅 후보일 ${appt.selectedDates.size}개 · ${appt.timeInfo}"
                                                else -> appt.timeInfo.ifBlank { appt.status }
                                            },
                                        fontSize = 13.sp,
                                        color = Color(0xFF666666),
                                    )
                                    if (appt.isOwner) {
                                        Spacer(modifier = Modifier.height(8.dp))
                                        Text(
                                            text = "삭제",
                                            fontSize = 12.sp,
                                            color = Color(0xFFC62828),
                                            modifier = Modifier.clickable { pendingDelete = appt },
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(90.dp))
            }
        }

        Box(
            modifier =
                Modifier
                    .align(Alignment.BottomEnd)
                    .padding(20.dp),
        ) {
            ExtendedFloatingActionButton(
                onClick = onCreateAppointmentClick,
                containerColor = Color(0xFFFFD54F),
                contentColor = Color(0xFF3C1E1E),
                shape = RoundedCornerShape(28.dp),
            ) {
                Text(
                    text = "+ 모임 만들기",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 4.dp),
                )
            }
        }
    }

    if (showJoinDialog) {
        AlertDialog(
            onDismissRequest = { if (!isMutating) showJoinDialog = false },
            containerColor = Color.White,
            title = { Text(text = "초대 코드로 참여", fontWeight = FontWeight.Bold) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(
                        text = "초대 코드만 입력하면 계정 표시명으로 참여합니다.",
                        fontSize = 12.sp,
                        color = Color(0xFF888888),
                    )
                    OutlinedTextField(
                        value = joinCode,
                        onValueChange = { joinCode = it.uppercase().take(8) },
                        enabled = !isMutating,
                        placeholder = { Text("8자리 코드", color = Color(0xFFAAAAAA)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        onJoinClick(joinCode)
                        showJoinDialog = false
                        joinCode = ""
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

    pendingDelete?.let { appt ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            containerColor = Color.White,
            title = { Text(text = "모임 삭제", fontWeight = FontWeight.Bold) },
            text = { Text(text = "'${appt.title}' 모임을 삭제할까요?") },
            confirmButton = {
                Button(
                    onClick = {
                        onDeleteAppointment(appt)
                        pendingDelete = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color.Red),
                ) {
                    Text(text = "삭제", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = { pendingDelete = null }) {
                    Text(text = "취소")
                }
            },
        )
    }
}
