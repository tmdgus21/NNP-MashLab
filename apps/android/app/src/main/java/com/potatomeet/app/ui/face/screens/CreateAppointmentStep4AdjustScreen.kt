package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.ui.face.TimeSlot
import com.potatomeet.app.ui.face.components.StepIndicatorItem
import com.potatomeet.app.ui.face.components.TopLogoHeader

@Composable
fun CreateAppointmentStep4AdjustScreen(
    myNickname: String,
    invitedFriends: List<String>,
    myTimeSlots: List<TimeSlot>,
    onBackClick: () -> Unit,
    onStepClick: (String) -> Unit,
    onAiAdjustClick: (String) -> Unit,
) {
    val realMyName = myNickname.ifBlank { "나" }
    val activeMembers = listOf(realMyName) + invitedFriends

    val friendRanges =
        mapOf(
            "민수" to Pair(0, 24), // 24시간 모두 가능
            "지훈" to Pair(0, 12), // 오전만 가능 (0시~12시)
            "영희" to Pair(12, 24), // 오후만 가능 (12시~24시)
            "철수" to Pair(11, 17), // 11시 ~ 17시 가능
        )

    val headerDateStr =
        if (myTimeSlots.isNotEmpty()) {
            "${myTimeSlots[0].month}월 ${myTimeSlots[0].day}일"
        } else {
            "10월 14일"
        }

    val horizontalScrollState = rememberScrollState()

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
            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceAround,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StepIndicatorItem(stepNumber = "1", title = "정보", isActive = false, onClick = { onStepClick("create_step1") })
                StepIndicatorItem(stepNumber = "2", title = "초대", isActive = false, onClick = { onStepClick("create_step2") })
                StepIndicatorItem(stepNumber = "3", title = "나의 시간", isActive = false, onClick = { onStepClick("create_step3") })
                StepIndicatorItem(
                    stepNumber = "4",
                    title = "시간 조율",
                    isActive = true,
                    onClick = { onStepClick("create_step4") },
                    activeTextSize = 12.sp,
                )
            }
            Spacer(modifier = Modifier.height(20.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = "$headerDateStr (화)",
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333),
                        )
                        Text(
                            text = "👈 좌우로 드래그해서 확인",
                            fontSize = 11.sp,
                            color = Color(0xFFFF8F00),
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    Row(modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Box(modifier = Modifier.height(24.dp).width(65.dp), contentAlignment = Alignment.CenterStart) {
                                Text(text = "이름", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFF888888))
                            }
                            activeMembers.forEach { memberName ->
                                Row(
                                    modifier = Modifier.height(24.dp).width(65.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Box(
                                        modifier = Modifier.size(22.dp).clip(CircleShape).background(Color(0xFFE0E0E0)),
                                        contentAlignment = Alignment.Center,
                                    ) {
                                        Text(
                                            text = memberName.take(1),
                                            fontSize = 10.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = Color.DarkGray,
                                        )
                                    }
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(text = memberName, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                                }
                            }
                        }

                        Spacer(modifier = Modifier.width(8.dp))

                        Column(
                            modifier =
                                Modifier
                                    .weight(1f)
                                    .horizontalScroll(horizontalScrollState),
                        ) {
                            Row(modifier = Modifier.padding(bottom = 8.dp)) {
                                (0..24 step 2).forEach { hour ->
                                    Box(
                                        modifier = Modifier.width(50.dp),
                                        contentAlignment = Alignment.CenterStart,
                                    ) {
                                        Text(text = "${hour}시", fontSize = 11.sp, color = Color(0xFFAAAAAA))
                                    }
                                }
                            }

                            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                activeMembers.forEach { memberName ->
                                    Row(
                                        modifier =
                                            Modifier
                                                .width(625.dp)
                                                .height(24.dp),
                                        horizontalArrangement = Arrangement.spacedBy(2.dp),
                                    ) {
                                        (0..23).forEach { hour ->
                                            val isAvailable =
                                                if (memberName == realMyName) {
                                                    myTimeSlots.any { slot -> hour in slot.startHour until slot.endHour }
                                                } else {
                                                    val range = friendRanges[memberName] ?: Pair(0, 0)
                                                    hour in range.first until range.second
                                                }

                                            Box(
                                                modifier =
                                                    Modifier
                                                        .weight(1f)
                                                        .fillMaxHeight()
                                                        .clip(RoundedCornerShape(4.dp))
                                                        .background(if (isAvailable) Color(0xFF81C784) else Color(0xFFF5F5F5)),
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
                        verticalAlignment = Alignment.CenterVertically,
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
            modifier =
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFFCF3))
                    .padding(horizontal = 20.dp, vertical = 12.dp),
        ) {
            Button(
                onClick = {
                    val timeStr =
                        if (myTimeSlots.isNotEmpty()) {
                            myTimeSlots[0].toFormattedString() + " (AI 조율)"
                        } else {
                            "$headerDateStr 18:30 ~ 20:30 (AI 조율)"
                        }
                    onAiAdjustClick(timeStr)
                },
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp),
            ) {
                Text(text = "AI 조율", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }
}

// AI 일정 추천 화면
