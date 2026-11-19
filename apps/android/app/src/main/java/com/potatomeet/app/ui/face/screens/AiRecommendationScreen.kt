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
fun AiRecommendationScreen(
    myTimeSlots: List<TimeSlot>,
    invitedFriends: List<String>,
    apiRecommendations: List<RecommendationOption>? = null,
    aiSummary: String? = null,
    multiSelectIds: Set<String> = emptySet(),
    onToggleCandidateId: ((String) -> Unit)? = null,
    confirmLabel: String = "이 시간으로 확정하기",
    isLoading: Boolean = false,
    onBackClick: () -> Unit,
    onConfirmFinal: (String) -> Unit,
) {
    var selectedIndex by remember { mutableStateOf(0) }

    val localRecommendations =
        remember(myTimeSlots, invitedFriends) {
            val totalPeople = 1 + invitedFriends.size
            val baseSlots =
                if (myTimeSlots.isNotEmpty()) {
                    myTimeSlots
                } else {
                    listOf(TimeSlot(month = 10, day = 14, startHour = 14, startMin = 0, endHour = 16, endMin = 0))
                }

            val friendRanges =
                mapOf(
                    "민수" to Pair(0, 24),
                    "지훈" to Pair(0, 12),
                    "영희" to Pair(12, 24),
                    "철수" to Pair(11, 17),
                )

            val resultList = mutableListOf<RecommendationOption>()

            baseSlots.forEach { mySlot ->
                var overlapStartMinutes = mySlot.startTotalMinutes
                var overlapEndMinutes = mySlot.endTotalMinutes

                for (friend in invitedFriends) {
                    val range = friendRanges[friend] ?: Pair(0, 24)
                    val friendStartMin = range.first * 60
                    val friendEndMin = range.second * 60

                    overlapStartMinutes = maxOf(overlapStartMinutes, friendStartMin)
                    overlapEndMinutes = minOf(overlapEndMinutes, friendEndMin)
                }

                if (overlapEndMinutes > overlapStartMinutes) {
                    val sH = String.format("%02d", overlapStartMinutes / 60)
                    val sM = String.format("%02d", overlapStartMinutes % 60)
                    val eH = String.format("%02d", overlapEndMinutes / 60)
                    val eM = String.format("%02d", overlapEndMinutes % 60)

                    val slotStr = "${mySlot.month}월 ${mySlot.day}일 ${sH}:${sM}~${eH}:${eM}"
                    resultList.add(
                        RecommendationOption(
                            rank = "${resultList.size + 1}위",
                            rankColor =
                                when (resultList.size) {
                                    0 -> Color(0xFFFFB300)
                                    1 -> Color(0xFFB0BEC5)
                                    else -> Color(0xFFA1887F)
                                },
                            timeText = slotStr,
                            infoText = "${totalPeople}명 모두 가능",
                            fitRate = "${100 - (resultList.size * 5)}%",
                        ),
                    )
                }
            }
            resultList
        }
    val overlappingRecommendations = apiRecommendations ?: localRecommendations

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
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "AI가 최적의 시간을 찾았어요!",
                fontSize = 22.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color(0xFF333333),
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(24.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Start
            ) {
                Text(
                    text = "추천 시간",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF333333)
                )
            }
            Spacer(modifier = Modifier.height(12.dp))

            if (overlappingRecommendations.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(120.dp)
                        .background(Color.White, RoundedCornerShape(16.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "모두 겹치는 시간이 없습니다 😢\n시간대를 다시 조율해보세요.",
                        fontSize = 14.sp,
                        color = Color(0xFF888888),
                        textAlign = TextAlign.Center
                    )
                }
            }             else {
                overlappingRecommendations.forEachIndexed { index, option ->
                    val candidateId = option.candidateId
                    val selected =
                        if (onToggleCandidateId != null && candidateId != null) {
                            candidateId in multiSelectIds
                        } else {
                            selectedIndex == index
                        }
                    RecommendationCard(
                        rank = option.rank,
                        rankColor = option.rankColor,
                        dateText = option.timeText,
                        infoText = option.infoText,
                        fitRate = option.fitRate,
                        isSelected = selected,
                        onClick = {
                            if (onToggleCandidateId != null && candidateId != null) {
                                onToggleCandidateId(candidateId)
                            } else {
                                selectedIndex = index
                            }
                        },
                    )
                    Spacer(modifier = Modifier.height(10.dp))
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "왜 이 시간이 좋나요?",
                fontSize = 13.sp,
                color = Color(0xFFFF8F00),
                fontWeight = FontWeight.Bold,
            )
            if (!aiSummary.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = aiSummary,
                    fontSize = 13.sp,
                    color = Color(0xFF666666),
                    textAlign = TextAlign.Start,
                    modifier = Modifier.fillMaxWidth(),
                )
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
                    if (onToggleCandidateId != null) {
                        onConfirmFinal("")
                    } else if (overlappingRecommendations.isNotEmpty()) {
                        onConfirmFinal(overlappingRecommendations[selectedIndex].timeText)
                    }
                },
                enabled = !isLoading && (
                    onToggleCandidateId != null || overlappingRecommendations.isNotEmpty()
                ),
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFFFFD54F),
                    disabledContainerColor = Color(0xFFE0E0E0)
                ),
                shape = RoundedCornerShape(26.dp)
            ) {
                Text(
                    text = if (isLoading) "처리 중…" else confirmLabel,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (overlappingRecommendations.isNotEmpty() || onToggleCandidateId != null) {
                        Color(0xFF3C1E1E)
                    } else {
                        Color.Gray
                    },
                )
            }
        }
    }
}
