package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.background
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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import com.potatomeet.app.ui.face.components.MultiDateCalendarPicker
import com.potatomeet.app.ui.face.components.StepIndicatorItem
import com.potatomeet.app.ui.face.components.TopLogoHeader
import java.time.LocalDate
import java.time.YearMonth

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
    nickname: String = "",
    onNicknameChange: (String) -> Unit = {},
    selectedDates: List<String> = emptyList(),
    onToggleSelectedDate: (String) -> Unit = {},
    onClearSelectedDates: () -> Unit = {},
    minSelectableDate: LocalDate = LocalDate.now(),
    maxSelectableDate: LocalDate = LocalDate.now().plusMonths(1),
    isLoading: Boolean = false,
    onBackClick: () -> Unit,
    onNextClick: () -> Unit,
    onStepClick: (String) -> Unit,
) {
    var visibleMonth by remember { mutableStateOf(YearMonth.from(minSelectableDate)) }
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
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = "모임 만들기", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                Surface(color = Color(0xFF2196F3), shape = RoundedCornerShape(6.dp)) {
                    Text(
                        text = "복수 날짜 선택",
                        fontSize = 11.sp,
                        color = Color.White,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                    )
                }
            }
            Spacer(modifier = Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceAround,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StepIndicatorItem(
                    stepNumber = "1",
                    title = "모임 정보",
                    isActive = true,
                    onClick = { onStepClick("create_step1") },
                    activeTextSize = 12.sp,
                )
                StepIndicatorItem(stepNumber = "2", title = "친구 초대", isActive = false, onClick = { onStepClick("create_step2") })
                StepIndicatorItem(stepNumber = "3", title = "나의 시간", isActive = false, onClick = { onStepClick("create_step3") })
                StepIndicatorItem(stepNumber = "4", title = "시간 조율", isActive = false, onClick = { onStepClick("create_step4") })
            }
            Spacer(modifier = Modifier.height(20.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(text = "모임 정보", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(16.dp))

                    Text(text = "모임 이름 *", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = appointmentName,
                        onValueChange = onAppointmentNameChange,
                        enabled = !isLoading,
                        placeholder = { Text("예) 친구들과 저녁 모임", color = Color(0xFFAAAAAA)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "이 모임에서 쓸 닉네임 *", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = nickname,
                        onValueChange = onNicknameChange,
                        enabled = !isLoading,
                        placeholder = { Text("예) 감자", color = Color(0xFFAAAAAA)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                    Spacer(modifier = Modifier.height(16.dp))

                    MultiDateCalendarPicker(
                        selectedDates = selectedDates,
                        onToggleDate = onToggleSelectedDate,
                        onClear = onClearSelectedDates,
                        minDate = minSelectableDate,
                        maxDate = maxSelectableDate,
                        visibleMonth = visibleMonth,
                        onPrevMonth = { visibleMonth = visibleMonth.minusMonths(1) },
                        onNextMonth = { visibleMonth = visibleMonth.plusMonths(1) },
                        enabled = !isLoading,
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "모임 설명 (선택·미전송)", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = category,
                        onValueChange = onCategoryChange,
                        enabled = !isLoading,
                        placeholder = { Text("모임에 대한 간단한 설명", color = Color(0xFFAAAAAA)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(text = "예상 소요시간 (참고·미전송)", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = duration,
                        onValueChange = onDurationChange,
                        enabled = !isLoading,
                        placeholder = { Text("예) 2시간", color = Color(0xFFAAAAAA)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(text = "장소 (참고·미전송)", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = location,
                        onValueChange = onLocationChange,
                        enabled = !isLoading,
                        placeholder = { Text("장소를 입력해주세요", color = Color(0xFFAAAAAA)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
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
                onClick = onNextClick,
                enabled = !isLoading,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp),
            ) {
                Text(
                    text = if (isLoading) "만드는 중…" else "다음",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF3C1E1E),
                )
            }
        }
    }
}

// 모임 만들기 Step 2
