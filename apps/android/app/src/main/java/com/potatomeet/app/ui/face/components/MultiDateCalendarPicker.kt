package com.potatomeet.app.ui.face.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.TextStyle
import java.util.Locale

@Composable
fun MultiDateCalendarPicker(
    selectedDates: List<String>,
    onToggleDate: (String) -> Unit,
    onClear: () -> Unit,
    minDate: LocalDate,
    maxDate: LocalDate,
    visibleMonth: YearMonth,
    onPrevMonth: () -> Unit,
    onNextMonth: () -> Unit,
    enabled: Boolean = true,
) {
    val locale = Locale.KOREAN
    val daysOfWeek = listOf("일", "월", "화", "수", "목", "금", "토")
    val cells = remember(visibleMonth) { monthCells(visibleMonth) }

    Column {
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

        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFFAF0), RoundedCornerShape(12.dp))
                    .border(1.dp, Color(0xFFFFE082), RoundedCornerShape(12.dp))
                    .padding(12.dp),
        ) {
            Column {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "〈",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF4A3B32),
                        modifier =
                            Modifier
                                .clickable(enabled = enabled) { onPrevMonth() }
                                .padding(8.dp),
                    )
                    Text(
                        text = "${visibleMonth.year}년 ${visibleMonth.monthValue}월",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF4A3B32),
                    )
                    Text(
                        text = "〉",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF4A3B32),
                        modifier =
                            Modifier
                                .clickable(enabled = enabled) { onNextMonth() }
                                .padding(8.dp),
                    )
                }
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceAround,
                ) {
                    daysOfWeek.forEach { label ->
                        Text(
                            text = label,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.Gray,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
                Spacer(modifier = Modifier.height(6.dp))
                LazyVerticalGrid(
                    columns = GridCells.Fixed(7),
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .height(220.dp),
                    userScrollEnabled = false,
                ) {
                    items(cells) { day ->
                        if (day == null) {
                            Box(modifier = Modifier.aspectRatio(1f))
                        } else {
                            val iso = day.toString()
                            val selectable = !day.isBefore(minDate) && !day.isAfter(maxDate)
                            val isSelected = selectedDates.contains(iso)
                            Box(
                                modifier =
                                    Modifier
                                        .padding(2.dp)
                                        .aspectRatio(1f)
                                        .clip(CircleShape)
                                        .background(
                                            when {
                                                isSelected -> Color(0xFFFF8F00)
                                                else -> Color.Transparent
                                            },
                                        )
                                        .clickable(enabled = enabled && selectable) {
                                            onToggleDate(iso)
                                        },
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(
                                    text = day.dayOfMonth.toString(),
                                    fontSize = 12.sp,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                    color =
                                        when {
                                            isSelected -> Color.White
                                            !selectable -> Color(0xFFCCCCCC)
                                            else -> Color.Black
                                        },
                                )
                            }
                        }
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(14.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "선택한 날짜 ${selectedDates.size}개",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFFFF8F00),
            )
            TextButton(onClick = onClear, enabled = enabled && selectedDates.isNotEmpty()) {
                Text(text = "초기화", fontSize = 12.sp, color = Color.Gray)
            }
        }
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            selectedDates.sorted().forEach { iso ->
                val label =
                    runCatching {
                        val d = LocalDate.parse(iso)
                        val dow =
                            d.dayOfWeek.getDisplayName(TextStyle.SHORT, locale)
                        "${d.monthValue}.${d.dayOfMonth}($dow)"
                    }.getOrDefault(iso)
                Surface(color = Color(0xFFFFECB3), shape = RoundedCornerShape(8.dp)) {
                    Row(
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = label,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF3C1E1E),
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "✕",
                            fontSize = 10.sp,
                            color = Color.Gray,
                            modifier = Modifier.clickable(enabled = enabled) { onToggleDate(iso) },
                        )
                    }
                }
            }
        }
    }
}

private fun monthCells(month: YearMonth): List<LocalDate?> {
    val first = month.atDay(1)
    // Sunday-first grid (Calendar dump style).
    val lead = first.dayOfWeek.value % 7
    val cells = MutableList<LocalDate?>(lead) { null }
    for (day in 1..month.lengthOfMonth()) {
        cells.add(month.atDay(day))
    }
    while (cells.size % 7 != 0) {
        cells.add(null)
    }
    return cells
}
