package com.potatomeet.app.ui.face.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Face-style date cutout card. Accepts `M.d(요일)` or ISO `yyyy-MM-dd`. */
@Composable
fun CalendarCutoutCard(dateTag: String) {
    val parsed = parseDateTag(dateTag)
    val dowColor =
        when (parsed.dow) {
            "일" -> Color(0xFFD32F2F)
            "토" -> Color(0xFF1976D2)
            else -> Color(0xFF666666)
        }

    Card(
        modifier = Modifier.width(64.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White),
        border = BorderStroke(1.dp, Color(0xFFFFE082)),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .background(Color(0xFFFFB300))
                        .padding(vertical = 3.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = "${parsed.month}월",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White,
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = parsed.dow,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = dowColor,
            )
            Text(
                text = parsed.day,
                fontSize = 18.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color(0xFF333333),
            )
            Spacer(modifier = Modifier.height(6.dp))
        }
    }
}

private data class ParsedDateTag(
    val month: String,
    val day: String,
    val dow: String,
)

private fun parseDateTag(dateTag: String): ParsedDateTag {
    if (dateTag.length >= 10 && dateTag[4] == '-') {
        runCatching {
            val d = java.time.LocalDate.parse(dateTag.take(10))
            val dow =
                d.dayOfWeek.getDisplayName(
                    java.time.format.TextStyle.SHORT,
                    java.util.Locale.KOREAN,
                )
            return ParsedDateTag(
                month = d.monthValue.toString(),
                day = d.dayOfMonth.toString(),
                dow = dow,
            )
        }
    }

    val monthPart = dateTag.substringBefore(".", "11")
    val afterDot = dateTag.substringAfter(".", "14(토)")
    val dayPart = afterDot.substringBefore("(", "14")
    val dowPart = afterDot.substringAfter("(", "토)").substringBefore(")", "토")
    return ParsedDateTag(month = monthPart.trimStart('0').ifBlank { monthPart }, day = dayPart, dow = dowPart)
}
