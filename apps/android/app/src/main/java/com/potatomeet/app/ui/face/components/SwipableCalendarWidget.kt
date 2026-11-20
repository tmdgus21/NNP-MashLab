package com.potatomeet.app.ui.face.components

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
import androidx.compose.foundation.layout.aspectRatio
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
    hasSlotOrApptCheck: (month: Int, day: Int) -> Boolean,
    isDayEnabled: (year: Int, month: Int, day: Int) -> Boolean = { _, _, _ -> true },
) {
    val daysOfWeek = listOf("일", "월", "화", "수", "목", "금", "토")
    val baseYear = remember { Calendar.getInstance().get(Calendar.YEAR) }

    val totalPages = 4000
    val initialPage = 2000 + (calendarYear - baseYear) * 12 + (calendarMonth - 1)
    val pagerState = rememberPagerState(initialPage = initialPage) { totalPages }

    LaunchedEffect(pagerState.currentPage) {
        val diffFromInitial = pagerState.currentPage - 2000
        val baseCal = Calendar.getInstance().apply {
            set(baseYear, Calendar.JANUARY, 1)
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
                set(baseYear, Calendar.JANUARY, 1)
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
                        val enabled = isDayEnabled(pYear, pMonth, dayNumber)
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
                                .clickable(enabled = enabled) {
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
                                    color = if (enabled) Color.Black else Color(0xFFCCCCCC)
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
