package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import com.potatomeet.app.ui.face.components.TopLogoHeader

@Composable
fun MyPageScreen(
    nickname: String,
    userId: String,
    onLogoutClick: () -> Unit,
    onNicknameChanged: (String) -> Unit,
    onBackClick: () -> Unit = {},
) {
    var showEditProfileDialog by remember { mutableStateOf(false) }
    var newNicknameInput by remember { mutableStateOf(nickname) }

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
                    .fillMaxSize()
                    .padding(20.dp)
                    .verticalScroll(rememberScrollState()),
        ) {
            Text(text = "마이페이지", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
            Spacer(modifier = Modifier.height(16.dp))

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(16.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(20.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(
                        modifier =
                            Modifier
                                .size(60.dp)
                                .clip(CircleShape)
                                .background(Color(0xFFD7CCC8)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = nickname.take(1).ifBlank { "?" },
                            fontSize = 24.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                        )
                    }
                    Spacer(modifier = Modifier.width(16.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = nickname,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF333333),
                        )
                        Text(text = userId, fontSize = 13.sp, color = Color(0xFF777777))
                    }
                    OutlinedButton(
                        onClick = {
                            newNicknameInput = nickname
                            showEditProfileDialog = true
                        },
                        shape = RoundedCornerShape(20.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                    ) {
                        Text(text = "프로필 수정", fontSize = 12.sp, color = Color(0xFF555555))
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            val menuItems = listOf("내 모임 관리", "알림 설정", "시간 조율 설정", "친구 관리", "설정", "도움말")
            menuItems.forEach { menu ->
                Card(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(12.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(text = menu, fontSize = 15.sp, color = Color(0xFF333333))
                        Text(text = "〉", fontSize = 14.sp, color = Color(0xFFAAAAAA))
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            Button(
                onClick = onLogoutClick,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFCDD2)),
                shape = RoundedCornerShape(24.dp),
            ) {
                Text(
                    text = "로그아웃",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFC62828),
                )
            }
        }
    }

    if (showEditProfileDialog) {
        AlertDialog(
            onDismissRequest = { showEditProfileDialog = false },
            containerColor = Color.White,
            title = { Text(text = "프로필 수정 (닉네임 변경)", fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    Text(
                        text = "계정 닉네임을 바꾸면 새로 만들거나 참여하는 모임에만 적용됩니다.",
                        fontSize = 12.sp,
                        color = Color(0xFF888888),
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = newNicknameInput,
                        onValueChange = { newNicknameInput = it },
                        placeholder = { Text("변경할 닉네임 입력") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (newNicknameInput.isNotBlank()) {
                            onNicknameChanged(newNicknameInput.trim())
                            showEditProfileDialog = false
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                ) {
                    Text(text = "저장", color = Color(0xFF3C1E1E), fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showEditProfileDialog = false }) {
                    Text(text = "취소", color = Color.Gray)
                }
            },
        )
    }
}
