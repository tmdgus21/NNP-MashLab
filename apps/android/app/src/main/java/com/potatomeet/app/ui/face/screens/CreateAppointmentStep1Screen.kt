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
    startDate: String = "",
    onStartDateChange: (String) -> Unit = {},
    endDate: String = "",
    onEndDateChange: (String) -> Unit = {},
    isLoading: Boolean = false,
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

                    Text(text = "이 모임에서 쓸 닉네임", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
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
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "날짜 범위 (YYYY-MM-DD)", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = startDate,
                            onValueChange = onStartDateChange,
                            enabled = !isLoading,
                            placeholder = { Text("시작일", color = Color(0xFFAAAAAA)) },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                        )
                        OutlinedTextField(
                            value = endDate,
                            onValueChange = onEndDateChange,
                            enabled = !isLoading,
                            placeholder = { Text("종료일", color = Color(0xFFAAAAAA)) },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                        )
                    }
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "무엇을 할까요?", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(value = category, onValueChange = onCategoryChange, enabled = !isLoading, placeholder = { Text("예) 식사, 카페, 스터디", color = Color(0xFFAAAAAA)) }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "예상 소요시간", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(value = duration, onValueChange = onDurationChange, enabled = !isLoading, placeholder = { Text("예) 2시간 (참고용)", color = Color(0xFFAAAAAA)) }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(text = "장소", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(6.dp))
                    OutlinedTextField(value = location, onValueChange = onLocationChange, enabled = !isLoading, placeholder = { Text("장소를 입력해주세요 (참고용)", color = Color(0xFFAAAAAA)) }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
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
                enabled = !isLoading,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp)
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
