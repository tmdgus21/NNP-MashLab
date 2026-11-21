package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.CircularProgressIndicator
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
import com.potatomeet.app.ui.face.RecommendationOption
import com.potatomeet.app.ui.face.components.TopLogoHeader

@Composable
fun AiResultScreen(
    meetingTitle: String,
    candidates: List<RecommendationOption>,
    aiSummary: String? = null,
    multiSelectIds: Set<String> = emptySet(),
    onToggleCandidateId: ((String) -> Unit)? = null,
    confirmLabel: String = "이 시간으로 최종 확정하기",
    emptyMessage: String = "아직 조율 후보가 없습니다. 입력이 끝나면 여기에 표시됩니다.",
    isLoading: Boolean = false,
    onBackClick: () -> Unit,
    onConfirmFinal: (selectedTimeText: String) -> Unit,
) {
    var selectedIndex by remember(candidates) { mutableStateOf(0) }

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
            Text(
                text = "AI 결과 화면 ✨",
                fontSize = 22.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color(0xFF333333),
            )
            Text(
                text =
                    if (meetingTitle.isNotBlank()) {
                        "'$meetingTitle' 모임을 위한 최적의 시간 후보입니다."
                    } else {
                        "모임을 위한 최적의 시간 후보입니다."
                    },
                fontSize = 13.sp,
                color = Color(0xFF777777),
            )
            if (!aiSummary.isNullOrBlank()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(text = aiSummary, fontSize = 12.sp, color = Color(0xFF666666))
            }
            Spacer(modifier = Modifier.height(16.dp))

            when {
                isLoading && candidates.isEmpty() -> {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 40.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(color = Color(0xFFFF9800))
                    }
                }
                candidates.isEmpty() -> {
                    Text(
                        text = emptyMessage,
                        fontSize = 14.sp,
                        color = Color(0xFF888888),
                        modifier = Modifier.padding(vertical = 24.dp),
                    )
                }
                else -> {
                    candidates.forEachIndexed { index, option ->
                        val candidateId = option.candidateId.orEmpty()
                        val multiOn = onToggleCandidateId != null && candidateId.isNotBlank()
                        val isSelected =
                            if (multiOn) {
                                multiSelectIds.contains(candidateId)
                            } else {
                                index == selectedIndex
                            }
                        val rankLabel =
                            when (index) {
                                0 -> "1위 (최적 추천)"
                                else -> "${index + 1}위"
                            }
                        Card(
                            modifier =
                                Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 6.dp)
                                    .clickable {
                                        if (multiOn) {
                                            onToggleCandidateId?.invoke(candidateId)
                                        } else {
                                            selectedIndex = index
                                        }
                                    },
                            colors = CardDefaults.cardColors(containerColor = Color.White),
                            shape = RoundedCornerShape(16.dp),
                            border =
                                BorderStroke(
                                    width = if (isSelected) 2.dp else 1.dp,
                                    color = if (isSelected) Color(0xFFFFB300) else Color(0xFFE0E0E0),
                                ),
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Text(
                                        text = option.rank.ifBlank { rankLabel },
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = if (index == 0) Color(0xFFFF8F00) else Color.Gray,
                                    )
                                    if (isSelected) {
                                        Surface(
                                            color = Color(0xFFFFE082),
                                            shape = RoundedCornerShape(6.dp),
                                        ) {
                                            Text(
                                                text = "선택됨",
                                                fontSize = 11.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = Color(0xFF3C1E1E),
                                                modifier =
                                                    Modifier.padding(
                                                        horizontal = 6.dp,
                                                        vertical = 2.dp,
                                                    ),
                                            )
                                        }
                                    }
                                }
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = option.timeText,
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF333333),
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = option.infoText,
                                    fontSize = 12.sp,
                                    color = Color(0xFF666666),
                                )
                            }
                        }
                    }
                }
            }
        }

        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFFCF3))
                    .padding(20.dp),
        ) {
            Button(
                onClick = {
                    val text =
                        when {
                            onToggleCandidateId != null -> {
                                candidates
                                    .filter { multiSelectIds.contains(it.candidateId) }
                                    .joinToString(", ") { it.timeText }
                                    .ifBlank { candidates.getOrNull(selectedIndex)?.timeText.orEmpty() }
                            }
                            else -> candidates.getOrNull(selectedIndex)?.timeText.orEmpty()
                        }
                    onConfirmFinal(text)
                },
                enabled = !isLoading && candidates.isNotEmpty(),
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp),
            ) {
                Text(
                    text = confirmLabel,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF3C1E1E),
                )
            }
        }
    }
}
