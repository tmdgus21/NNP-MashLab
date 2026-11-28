package com.potatomeet.app.ui.face.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import com.potatomeet.app.ui.face.components.CalendarCutoutCard
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
    val monthHeader =
        appointment.selectedDates.firstOrNull()?.let { iso ->
            runCatching {
                val d = LocalDate.parse(iso.take(10))
                "${d.year}년 ${d.monthValue}월"
            }.getOrNull()
        } ?: appointment.timeInfo

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
            Spacer(modifier = Modifier.height(6.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Text(
                        text = appointment.title,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF333333),
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = appointment.status.ifBlank { appointment.category }.ifBlank { "입력 중" },
                        fontSize = 13.sp,
                        color = Color(0xFF666666),
                    )
                    Spacer(modifier = Modifier.height(16.dp))

                    Box(
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .background(Color(0xFFFFFAF0), RoundedCornerShape(14.dp))
                                .border(1.dp, Color(0xFFFFECB3), RoundedCornerShape(14.dp))
                                .padding(12.dp),
                    ) {
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Text(
                                    text = monthHeader,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF4A3B32),
                                )
                                Text(
                                    text = "후보일 ${selectedLabels.size}개",
                                    fontSize = 11.sp,
                                    color = Color(0xFFFF8F00),
                                    fontWeight = FontWeight.Bold,
                                )
                            }
                            Spacer(modifier = Modifier.height(10.dp))
                            if (selectedLabels.isEmpty()) {
                                Text(text = "선택된 후보 날짜가 없습니다.", fontSize = 12.sp, color = Color(0xFF999999))
                            } else {
                                Row(
                                    modifier =
                                        Modifier
                                            .fillMaxWidth()
                                            .horizontalScroll(rememberScrollState()),
                                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                                ) {
                                    selectedLabels.forEach { label ->
                                        CalendarCutoutCard(dateTag = label)
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
                    Text(
                        text =
                            if (appointment.code.isNotBlank()) {
                                "초대 코드 ${appointment.code}"
                            } else {
                                "아직 초대된 친구가 없어요. 함께할 친구에게 모임을 보내주세요."
                            },
                        fontSize = 12.sp,
                        color = if (appointment.code.isNotBlank()) Color(0xFFFF9800) else Color(0xFF888888),
                        fontWeight = if (appointment.code.isNotBlank()) FontWeight.Bold else FontWeight.Normal,
                    )
                    Spacer(modifier = Modifier.height(12.dp))
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

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(text = "내 불가능 시간", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                        if (mySubmitted) {
                            Text(
                                text = "총 ${myAvailableLines.size}개 구간",
                                fontSize = 12.sp,
                                color = Color(0xFFFF8F00),
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(10.dp))
                    when {
                        !mySubmitted -> {
                            Text(
                                text = "아직 불가능 시간을 입력하지 않았습니다.",
                                fontSize = 13.sp,
                                color = Color.Gray,
                            )
                        }
                        myAvailableLines.isEmpty() -> {
                            Text(
                                text = "설정된 불가능 시간이 없습니다.",
                                fontSize = 13.sp,
                                color = Color.Gray,
                            )
                        }
                        else -> {
                            myAvailableLines.forEach { line ->
                                Card(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                    colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFDF9)),
                                    shape = RoundedCornerShape(10.dp),
                                    border = BorderStroke(1.dp, Color(0xFFFFE082)),
                                ) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth().padding(12.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        Text(
                                            text = line.dateLabel,
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = Color(0xFF333333),
                                        )
                                        Text(
                                            text = line.rangeLabel,
                                            fontSize = 13.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = Color(0xFFE65100),
                                        )
                                    }
                                }
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
                        Text(
                            text = "불가 시간 수정 (30분 단위 시간표)",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                        )
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
