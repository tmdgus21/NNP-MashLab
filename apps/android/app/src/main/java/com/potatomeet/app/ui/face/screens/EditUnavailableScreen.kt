package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.ui.face.AvailabilityConverter
import com.potatomeet.app.ui.face.UnavailableSlot
import com.potatomeet.app.ui.face.components.TopLogoHeader
import com.potatomeet.app.ui.face.halfHourSlotsForDate
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

@Composable
fun EditUnavailableScreen(
    selectedIsoDates: List<String>,
    /** Selected slots = unavailable times (default = available). */
    unavailableSlots: List<UnavailableSlot>,
    scopeStartsAt: String? = null,
    scopeEndsAt: String? = null,
    saving: Boolean = false,
    onToggleSlot: (UnavailableSlot) -> Unit,
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit,
) {
    val dateTabs =
        remember(selectedIsoDates) {
            selectedIsoDates.map { iso -> iso to formatDateTab(iso) }
        }
    var selectedTabIso by remember(selectedIsoDates) {
        mutableStateOf(selectedIsoDates.firstOrNull().orEmpty())
    }
    if (selectedTabIso.isBlank() && selectedIsoDates.isNotEmpty()) {
        selectedTabIso = selectedIsoDates.first()
    }

    var selectedTimePage by remember { mutableIntStateOf(1) }
    val timeRanges =
        listOf(
            Triple(0, 8, "00:00 ~ 08:00"),
            Triple(8, 16, "08:00 ~ 16:00"),
            Triple(16, 24, "16:00 ~ 24:00"),
        )
    val (startHourOfPage, endHourOfPage, rangeLabel) = timeRanges[selectedTimePage]

    val daySlots =
        remember(selectedTabIso) {
            if (selectedTabIso.isBlank()) emptyList() else halfHourSlotsForDate(selectedTabIso)
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
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "내 불가능 시간 수정",
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF333333),
                )
                TextButton(
                    onClick = {
                        daySlots.forEach { slot ->
                            if (!AvailabilityConverter.isSlotInScope(slot, scopeStartsAt, scopeEndsAt)) {
                                return@forEach
                            }
                            if (unavailableSlots.any { it.matches(slot) }) {
                                onToggleSlot(slot)
                            }
                        }
                    },
                ) {
                    Text(
                        text = "현재 날짜 초기화",
                        fontSize = 12.sp,
                        color = Color(0xFFFF8F00),
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
            Text(
                text = "한 시간당 30분 단위(2파트)로 터치하여 불가 시간을 체크하세요.",
                fontSize = 12.sp,
                color = Color(0xFF777777),
            )
            Text(
                text = "선택하지 않은 시간은 모두 가능한 시간으로 처리됩니다.",
                fontSize = 12.sp,
                color = Color(0xFF888888),
            )
            Text(
                text = "지난 시간·범위 밖 시간은 선택할 수 없습니다.",
                fontSize = 12.sp,
                color = Color(0xFF888888),
            )
            Spacer(modifier = Modifier.height(12.dp))

            if (dateTabs.isEmpty()) {
                Text(text = "선택된 모임 날짜가 없습니다.", fontSize = 14.sp, color = Color.Gray)
            } else {
                Row(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    dateTabs.forEach { (iso, label) ->
                        val isSelected = iso == selectedTabIso
                        Button(
                            onClick = { selectedTabIso = iso },
                            colors =
                                ButtonDefaults.buttonColors(
                                    containerColor = if (isSelected) Color(0xFFFF8F00) else Color.White,
                                ),
                            border = if (!isSelected) BorderStroke(1.dp, Color(0xFFE0E0E0)) else null,
                            shape = RoundedCornerShape(10.dp),
                        ) {
                            Text(
                                text = label,
                                fontSize = 12.sp,
                                color = if (isSelected) Color.White else Color(0xFF333333),
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    timeRanges.forEachIndexed { index, (_, _, label) ->
                        val isPageSelected = selectedTimePage == index
                        Surface(
                            modifier =
                                Modifier
                                    .weight(1f)
                                    .clip(RoundedCornerShape(10.dp))
                                    .clickable { selectedTimePage = index },
                            color = if (isPageSelected) Color(0xFF4A3B32) else Color(0xFFF3EFE6),
                            shape = RoundedCornerShape(10.dp),
                        ) {
                            Column(
                                modifier = Modifier.padding(vertical = 8.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                            ) {
                                Text(
                                    text = "${index + 1}/3 구간",
                                    fontSize = 10.sp,
                                    color = if (isPageSelected) Color(0xFFFFD54F) else Color(0xFF888888),
                                    fontWeight = FontWeight.Bold,
                                )
                                Text(
                                    text = label,
                                    fontSize = 11.sp,
                                    color = if (isPageSelected) Color.White else Color(0xFF4A3B32),
                                    fontWeight = FontWeight.Bold,
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = "시간표 ($rangeLabel)",
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF333333),
                            )
                            Row(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Box(
                                        modifier =
                                            Modifier
                                                .size(10.dp)
                                                .background(Color(0xFFF5F5F5), RoundedCornerShape(2.dp))
                                                .border(1.dp, Color(0xFFE0E0E0), RoundedCornerShape(2.dp)),
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(text = "가능", fontSize = 11.sp, color = Color.Gray)
                                }
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Box(
                                        modifier =
                                            Modifier
                                                .size(10.dp)
                                                .background(Color(0xFFFF8A65), RoundedCornerShape(2.dp)),
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        text = "불가",
                                        fontSize = 11.sp,
                                        color = Color(0xFFD84315),
                                        fontWeight = FontWeight.Bold,
                                    )
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(10.dp))

                        Row(
                            modifier =
                                Modifier
                                    .fillMaxWidth()
                                    .background(
                                        Color(0xFFFFFAF0),
                                        RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp),
                                    )
                                    .border(
                                        1.dp,
                                        Color(0xFFFFE082),
                                        RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp),
                                    )
                                    .padding(vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = "시간",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF4A3B32),
                                textAlign = TextAlign.Center,
                                modifier = Modifier.width(64.dp),
                            )
                            Text(
                                text = "00분 ~ 30분",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF4A3B32),
                                textAlign = TextAlign.Center,
                                modifier = Modifier.weight(1f),
                            )
                            Text(
                                text = "30분 ~ 60분",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF4A3B32),
                                textAlign = TextAlign.Center,
                                modifier = Modifier.weight(1f),
                            )
                        }

                        (startHourOfPage until endHourOfPage).forEach { hour ->
                            val first =
                                UnavailableSlot(
                                    dateIso = selectedTabIso,
                                    startHour = hour,
                                    startMin = 0,
                                    endHour = hour,
                                    endMin = 30,
                                )
                            val second =
                                UnavailableSlot(
                                    dateIso = selectedTabIso,
                                    startHour = hour,
                                    startMin = 30,
                                    endHour = if (hour == 23) 24 else hour + 1,
                                    endMin = if (hour == 23) 0 else 0,
                                )
                            Row(
                                modifier =
                                    Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 3.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Text(
                                    text = "%02d시".format(hour),
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF555555),
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier.width(64.dp),
                                )
                                HalfHourCell(
                                    modifier = Modifier.weight(1f).padding(end = 4.dp),
                                    slot = first,
                                    unavailableSlots = unavailableSlots,
                                    scopeStartsAt = scopeStartsAt,
                                    scopeEndsAt = scopeEndsAt,
                                    onToggleSlot = onToggleSlot,
                                )
                                HalfHourCell(
                                    modifier = Modifier.weight(1f).padding(start = 4.dp),
                                    slot = second,
                                    unavailableSlots = unavailableSlots,
                                    scopeStartsAt = scopeStartsAt,
                                    scopeEndsAt = scopeEndsAt,
                                    onToggleSlot = onToggleSlot,
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            TextButton(
                                onClick = { if (selectedTimePage > 0) selectedTimePage -= 1 },
                                enabled = selectedTimePage > 0,
                            ) {
                                Text(text = "〈 이전 8시간", fontSize = 12.sp)
                            }
                            TextButton(
                                onClick = { if (selectedTimePage < 2) selectedTimePage += 1 },
                                enabled = selectedTimePage < 2,
                            ) {
                                Text(text = "다음 8시간 〉", fontSize = 12.sp)
                            }
                        }
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
            Column {
                Text(
                    text = "선택하지 않은 시간은 모두 가능한 시간으로 처리됩니다.",
                    fontSize = 12.sp,
                    color = Color(0xFF777777),
                    modifier = Modifier.padding(bottom = 10.dp),
                )
                Button(
                    onClick = onSaveClick,
                    enabled = !saving && dateTabs.isNotEmpty(),
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                    shape = RoundedCornerShape(26.dp),
                ) {
                    Text(
                        text = if (saving) "저장 중…" else "불가능 시간 저장",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color(0xFF3C1E1E),
                    )
                }
            }
        }
    }
}

@Composable
private fun HalfHourCell(
    modifier: Modifier = Modifier,
    slot: UnavailableSlot,
    unavailableSlots: List<UnavailableSlot>,
    scopeStartsAt: String?,
    scopeEndsAt: String?,
    onToggleSlot: (UnavailableSlot) -> Unit,
) {
    val selectable = AvailabilityConverter.isSlotInScope(slot, scopeStartsAt, scopeEndsAt)
    val isMarked = selectable && unavailableSlots.any { it.matches(slot) }
    val bg =
        when {
            !selectable -> Color(0xFFEEEEEE)
            isMarked -> Color(0xFFFF8A65)
            else -> Color(0xFFF5F5F5)
        }
    Column(
        modifier =
            modifier
                .clip(RoundedCornerShape(8.dp))
                .background(bg)
                .then(
                    if (selectable) {
                        Modifier.clickable(onClick = { onToggleSlot(slot) })
                    } else {
                        Modifier
                    },
                )
                .border(
                    1.dp,
                    if (isMarked) Color(0xFFE64A19) else Color(0xFFE0E0E0),
                    RoundedCornerShape(8.dp),
                )
                .padding(horizontal = 8.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text =
                when {
                    !selectable -> "지난 시간"
                    isMarked -> "불가"
                    else -> "가능"
                },
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color =
                when {
                    !selectable -> Color(0xFF9E9E9E)
                    isMarked -> Color(0xFFBF360C)
                    else -> Color(0xFF757575)
                },
        )
    }
}

private fun formatDateTab(iso: String): String =
    runCatching {
        val d = LocalDate.parse(iso.take(10))
        val dow = d.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.KOREAN)
        "${d.monthValue}.${d.dayOfMonth}($dow)"
    }.getOrDefault(iso)
