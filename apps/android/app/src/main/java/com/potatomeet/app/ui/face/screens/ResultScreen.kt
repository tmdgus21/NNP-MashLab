package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.ui.face.components.TopLogoHeader

@Composable
fun ResultScreen(
    title: String,
    timeText: String,
    methodText: String,
    memberText: String,
    tieBroken: Boolean,
    onBackClick: () -> Unit,
    onHomeClick: () -> Unit,
) {
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
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "확정된 약속",
                fontSize = 22.sp,
                fontWeight = FontWeight.ExtraBold,
                color = Color(0xFF333333),
            )
            Spacer(modifier = Modifier.height(16.dp))
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(text = title, fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(10.dp))
                    Text(text = "📅 $timeText", fontSize = 15.sp, color = Color(0xFF555555))
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(text = "👥 $memberText", fontSize = 14.sp, color = Color(0xFF666666))
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(text = "확정 방식: $methodText", fontSize = 13.sp, color = Color(0xFF888888))
                    if (tieBroken) {
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "동점이어서 규칙에 따라 정해졌어요.",
                            fontSize = 13.sp,
                            color = Color(0xFFFF8F00),
                            fontWeight = FontWeight.Bold,
                        )
                    }
                }
            }
        }

        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFFCF3))
                    .padding(horizontal = 20.dp, vertical = 12.dp),
        ) {
            Button(
                onClick = onHomeClick,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                shape = RoundedCornerShape(26.dp),
            ) {
                Text(text = "홈으로", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
            }
        }
    }
}
