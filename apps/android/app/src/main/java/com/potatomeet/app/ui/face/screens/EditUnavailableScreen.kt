package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.ui.face.AvailabilityConverter
import com.potatomeet.app.ui.face.UnavailableSlot
import com.potatomeet.app.ui.face.components.TopLogoHeader
import com.potatomeet.app.ui.face.halfHourSlotsForDate
import com.potatomeet.app.ui.face.timeLabel
import java.time.LocalDate
import java.time.format.TextStyle
import java.util.Locale

@Composable
fun EditUnavailableScreen(
    selectedIsoDates: List<String>,
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
            selectedIsoDates.map { iso ->
                iso to formatDateTab(iso)
            }
        }
    var selectedTabIso by remember(selectedIsoDates) {
        mutableStateOf(selectedIsoDates.firstOrNull().orEmpty())
    }
    if (selectedTabIso.isBlank() && selectedIsoDates.isNotEmpty()) {
        selectedTabIso = selectedIsoDates.first()
    }

    val daySlots =
        remember(selectedTabIso) {
            if (selectedTabIso.isBlank()) {
                emptyList()
            } else {
                halfHourSlotsForDate(selectedTabIso)
            }
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
                    Text(text = "초기화", fontSize = 12.sp, color = Color(0xFFFF8F00))
                }
            }
            Text(
                text = "참석할 수 없는 시간을 터치하여 선택하세요.",
                fontSize = 13.sp,
                color = Color(0xFF777777),
            )
            Text(
                text = "선택한 칸은 불가능 시간입니다. 지난 시간은 선택할 수 없습니다.",
                fontSize = 12.sp,
                color = Color(0xFF888888),
            )
            Spacer(modifier = Modifier.height(14.dp))

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

                Spacer(modifier = Modifier.height(16.dp))

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(16.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = "00:00 ~ 24:00",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF555555),
                            )
                            Text(text = "30분 단위 · 48칸", fontSize = 11.sp, color = Color.Gray)
                        }
                        Spacer(modifier = Modifier.height(12.dp))

                        daySlots.chunked(2).forEach { pair ->
                            Row(
                                modifier =
                                    Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 3.dp),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                pair.forEach { slot ->
                                    val selectable =
                                        AvailabilityConverter.isSlotInScope(
                                            slot,
                                            scopeStartsAt,
                                            scopeEndsAt,
                                        )
                                    val isMarked =
                                        selectable &&
                                            unavailableSlots.any { it.matches(slot) }
                                    HalfHourCell(
                                        modifier = Modifier.weight(1f),
                                        label = slot.timeLabel(),
                                        isMarked = isMarked,
                                        enabled = selectable,
                                        onClick = { onToggleSlot(slot) },
                                    )
                                }
                                if (pair.size == 1) {
                                    Spacer(modifier = Modifier.weight(1f))
                                }
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

@Composable
private fun HalfHourCell(
    modifier: Modifier = Modifier,
    label: String,
    isMarked: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    val bg =
        when {
            !enabled -> Color(0xFFEEEEEE)
            isMarked -> Color(0xFFFFCCBC)
            else -> Color(0xFFF5F5F5)
        }
    Column(
        modifier =
            modifier
                .clip(RoundedCornerShape(8.dp))
                .background(bg)
                .then(
                    if (enabled) {
                        Modifier.clickable(onClick = onClick)
                    } else {
                        Modifier
                    },
                )
                .padding(horizontal = 8.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text = label,
            fontSize = 11.sp,
            fontWeight = FontWeight.Medium,
            color = if (enabled) Color(0xFF333333) else Color(0xFF9E9E9E),
            maxLines = 2,
            softWrap = true,
        )
        Text(
            text =
                when {
                    !enabled -> "지난 시간"
                    isMarked -> "불가능"
                    else -> "가능"
                },
            fontSize = 11.sp,
            fontWeight = FontWeight.Bold,
            color =
                when {
                    !enabled -> Color(0xFF9E9E9E)
                    isMarked -> Color(0xFFD32F2F)
                    else -> Color(0xFF388E3C)
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
