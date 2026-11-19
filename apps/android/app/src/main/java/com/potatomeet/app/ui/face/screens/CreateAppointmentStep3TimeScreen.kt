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
                        onDayChange = { it: Int ->
                            onDayChange(it)
                            showTimePickerModal = true
                        },
                        hasSlotOrApptCheck = { m: Int, d: Int ->
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
                                        onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) editM = it }
                                    )
                                    Text(text = "월 ", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))

                                    SeamlessInputBox(
                                        value = editD,
                                        onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) editD = it }
                                    )
                                    Text(text = "일 ", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))

                                    SeamlessInputBox(
                                        value = editSh,
                                        onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) editSh = it }
                                    )
                                    Text(text = ":", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                    SeamlessInputBox(
                                        value = editSm,
                                        onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) editSm = it }
                                    )

                                    Text(text = " ~ ", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                    SeamlessInputBox(
                                        value = editEh,
                                        onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) editEh = it }
                                    )
                                    Text(text = ":", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                    SeamlessInputBox(
                                        value = editEm,
                                        onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) editEm = it }
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
                                    onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) inputMonth = it }
                                )
                                Text(text = "월 ", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))

                                SeamlessInputBox(
                                    value = inputDay,
                                    onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) inputDay = it }
                                )
                                Text(text = "일 ", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))

                                SeamlessInputBox(
                                    value = inputStartHour,
                                    onValueChange = { newSH: String ->
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
                                    onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) inputStartMin = it }
                                )

                                Text(text = " ~ ", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                SeamlessInputBox(
                                    value = inputEndHour,
                                    onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) inputEndHour = it }
                                )
                                Text(text = ":", fontSize = 13.sp, fontWeight = FontWeight.Bold)

                                SeamlessInputBox(
                                    value = inputEndMin,
                                    onValueChange = { it: String -> if (it.length <= 2 && it.all { c: Char -> c.isDigit() }) inputEndMin = it }
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

// 모임 만들기 Step 4
