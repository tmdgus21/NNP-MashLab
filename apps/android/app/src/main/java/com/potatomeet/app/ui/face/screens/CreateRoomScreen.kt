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
import com.potatomeet.app.ui.face.components.TopLogoHeader
import com.potatomeet.app.ui.face.components.faceTextFieldColors
import java.time.LocalDate
import java.time.YearMonth

@Composable
fun CreateRoomScreen(
    roomTitle: String,
    onRoomTitleChange: (String) -> Unit,
    roomDesc: String,
    onRoomDescChange: (String) -> Unit,
    selectedDates: List<String>,
    onToggleSelectedDate: (String) -> Unit,
    onClearSelectedDates: () -> Unit,
    minSelectableDate: LocalDate,
    maxSelectableDate: LocalDate,
    accountNickname: String? = null,
    isLoading: Boolean = false,
    onBackClick: () -> Unit,
    onCreateClick: () -> Unit,
) {
    var visibleMonth by remember(minSelectableDate) {
        mutableStateOf(YearMonth.from(minSelectableDate))
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
            Spacer(modifier = Modifier.height(8.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "모임 이름 *",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF555555),
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = roomTitle,
                        onValueChange = onRoomTitleChange,
                        placeholder = { Text("모임 이름을 입력해주세요", color = Color(0xFF9E9E9E)) },
                        singleLine = true,
                        enabled = !isLoading,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = faceTextFieldColors(),
                    )

                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = "모임 설명",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF555555),
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(
                        value = roomDesc,
                        onValueChange = onRoomDescChange,
                        placeholder = { Text("모임에 대한 간단한 설명", color = Color(0xFF9E9E9E)) },
                        singleLine = true,
                        enabled = !isLoading,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = faceTextFieldColors(),
                    )

                    if (!accountNickname.isNullOrBlank()) {
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "계정 닉네임",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF555555),
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = accountNickname,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Medium,
                            color = Color(0xFF333333),
                        )
                        Text(
                            text = "모임에는 이 닉네임이 자동으로 사용됩니다. 변경은 마이페이지에서 하세요.",
                            fontSize = 11.sp,
                            color = Color(0xFF888888),
                        )
                    }

                    Spacer(modifier = Modifier.height(16.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = "모임 날짜 *",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF555555),
                        )
                        Text(
                            text = "모임을 열고 싶은 날짜를 모두 선택해 주세요.",
                            fontSize = 11.sp,
                            color = Color(0xFF888888),
                        )
                    }
                    Spacer(modifier = Modifier.height(10.dp))

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
                onClick = onCreateClick,
                enabled = !isLoading,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp),
            ) {
                Text(
                    text = if (isLoading) "만드는 중…" else "모임 만들기",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF3C1E1E),
                )
            }
        }
    }
}
