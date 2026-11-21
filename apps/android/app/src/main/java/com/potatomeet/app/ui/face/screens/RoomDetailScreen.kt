package com.potatomeet.app.ui.face.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.ui.face.Appointment
import com.potatomeet.app.ui.face.AvailabilityConverter
import com.potatomeet.app.ui.face.components.TopLogoHeader
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

@Composable
fun RoomDetailScreen(
    appointment: Appointment,
    mySubmitted: Boolean = false,
    myAvailableLines: List<AvailabilityConverter.DisplayLine> = emptyList(),
    onBackClick: () -> Unit,
    onEditAvailabilityClick: () -> Unit,
    onAiResultClick: () -> Unit,
    onInviteClick: () -> Unit = {},
) {
    val context = LocalContext.current
    val selectedLabels =
        appointment.selectedDates.map { iso ->
            runCatching {
                val d = LocalDate.parse(iso.take(10))
                val dow = d.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.KOREAN)
                "${d.monthValue}.${d.dayOfMonth}($dow)"
            }.getOrDefault(iso)
        }

    Column(modifier = Modifier.fillMaxSize()) {
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFFCF3))
                    .padding(horizontal = 20.dp, vertical = 12.dp),
        ) {
            TopLogoHeader(onBackClick = onBackClick)
        }

        Column(
            modifier =
                Modifier
                    .weight(1f)
                    .padding(horizontal = 20.dp)
                    .verticalScroll(rememberScrollState()),
        ) {
            Text(text = "모임 상세", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
            Spacer(modifier = Modifier.height(16.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Text(text = "모임 정보", fontSize = 12.sp, color = Color(0xFF888888))
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = appointment.title,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF333333),
                    )
                    Text(
                        text = appointment.status.ifBlank { appointment.category },
                        fontSize = 13.sp,
                        color = Color(0xFF666666),
                    )
                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = appointment.timeInfo,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333),
                        )
                        Text(
                            text = "모임 후보일 ${selectedLabels.size.coerceAtLeast(
                                if (appointment.selectedDates.isEmpty()) 0 else selectedLabels.size,
                            )}개",
                            fontSize = 11.sp,
                            color = Color(0xFFFF8F00),
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))

                    if (selectedLabels.isNotEmpty()) {
                        Row(
                            modifier =
                                Modifier
                                    .fillMaxWidth()
                                    .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            selectedLabels.forEach { label ->
                                Surface(
                                    color = Color(0xFFFFFAF0),
                                    shape = RoundedCornerShape(10.dp),
                                    border = BorderStroke(1.dp, Color(0xFFFFD54F)),
                                ) {
                                    Text(
                                        text = label,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color(0xFF3C1E1E),
                                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                    )
                                }
                            }
                        }
                    } else {
                        Text(text = appointment.timeInfo, fontSize = 13.sp, color = Color(0xFF666666))
                    }

                    Spacer(modifier = Modifier.height(20.dp))
                    HorizontalDivider(color = Color(0xFFF0F0F0))
                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(text = "현재 참여자", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                        Text(
                            text = "${appointment.invitedFriends.size.coerceAtLeast(1)}명",
                            fontSize = 12.sp,
                            color = Color(0xFF888888),
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    appointment.invitedFriends.ifEmpty { listOf("나") }.forEachIndexed { index, member ->
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = if (index == 0 && appointment.isOwner) "방장" else "참여자",
                                fontSize = 13.sp,
                                color = Color(0xFF666666),
                            )
                            Surface(color = Color(0xFFFFF3E0), shape = RoundedCornerShape(8.dp)) {
                                Text(
                                    text = member,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFFFF8F00),
                                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))
                    HorizontalDivider(color = Color(0xFFF0F0F0))
                    Spacer(modifier = Modifier.height(16.dp))

                    Text(text = "친구 초대", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(4.dp))
                    if (appointment.code.isNotBlank()) {
                        Text(
                            text = "초대 코드 ${appointment.code}",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFFFF9800),
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                    } else {
                        Text(
                            text = "아직 초대 코드가 없어요.",
                            fontSize = 12.sp,
                            color = Color(0xFF888888),
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                    Button(
                        onClick = {
                            if (appointment.code.isNotBlank()) {
                                val cm =
                                    context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                cm.setPrimaryClip(ClipData.newPlainText("invite", appointment.code))
                                Toast.makeText(context, "초대 코드를 복사했습니다.", Toast.LENGTH_SHORT).show()
                            }
                            onInviteClick()
                        },
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFEE58)),
                        shape = RoundedCornerShape(24.dp),
                    ) {
                        Text(
                            text = "💛 카카오톡으로 친구 초대",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF3C1E1E),
                        )
                    }

                    Spacer(modifier = Modifier.height(20.dp))
                    HorizontalDivider(color = Color(0xFFF0F0F0))
                    Spacer(modifier = Modifier.height(16.dp))

                    Text(text = "내 가능 시간", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(10.dp))
                    when {
                        !mySubmitted -> {
                            Text(
                                text = "아직 가능 시간을 입력하지 않았습니다.",
                                fontSize = 13.sp,
                                color = Color.Gray,
                            )
                        }
                        myAvailableLines.isEmpty() -> {
                            Text(
                                text = "저장된 가능 시간이 없습니다.",
                                fontSize = 13.sp,
                                color = Color.Gray,
                            )
                        }
                        else -> {
                            myAvailableLines.forEach { line ->
                                Text(
                                    text = "${line.dateLabel}  ${line.rangeLabel}",
                                    fontSize = 13.sp,
                                    color = Color(0xFF333333),
                                    modifier = Modifier.padding(vertical = 2.dp),
                                )
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(14.dp))
                    Button(
                        onClick = onEditAvailabilityClick,
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF8D6E63)),
                        shape = RoundedCornerShape(24.dp),
                    ) {
                        Text(text = "가능 시간 수정", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color.White)
                    }
                }
            }
            Spacer(modifier = Modifier.height(20.dp))
        }

        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFFCF3))
                    .padding(20.dp),
        ) {
            Button(
                onClick = onAiResultClick,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp),
            ) {
                Text(
                    text = "AI 최적 시간 조율 결과 보기 ✨",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF3C1E1E),
                )
            }
        }
    }
}
