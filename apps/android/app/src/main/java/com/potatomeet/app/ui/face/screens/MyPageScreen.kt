package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.ui.face.components.TopLogoHeader

@Composable
fun MyPageScreen(
    nickname: String,
    userId: String,
    deletingAccount: Boolean = false,
    onLogoutClick: () -> Unit,
    onNicknameChanged: (String) -> Unit,
    onDeleteAccountClick: (password: String) -> Unit = {},
    onBackClick: () -> Unit = {},
) {
    var showEditProfileDialog by remember { mutableStateOf(false) }
    var showDeleteAccountDialog by remember { mutableStateOf(false) }
    var newNicknameInput by remember { mutableStateOf(nickname) }
    var deletePasswordInput by remember { mutableStateOf("") }

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
                        enabled = !deletingAccount,
                        shape = RoundedCornerShape(20.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                    ) {
                        Text(text = "프로필 수정", fontSize = 12.sp, color = Color(0xFF555555))
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = onLogoutClick,
                enabled = !deletingAccount,
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

            Spacer(modifier = Modifier.height(12.dp))

            OutlinedButton(
                onClick = {
                    deletePasswordInput = ""
                    showDeleteAccountDialog = true
                },
                enabled = !deletingAccount,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(24.dp),
                border = BorderStroke(1.dp, Color(0xFFC62828)),
            ) {
                Text(
                    text = if (deletingAccount) "계정 삭제 중…" else "계정 삭제",
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

    if (showDeleteAccountDialog) {
        AlertDialog(
            onDismissRequest = {
                if (!deletingAccount) showDeleteAccountDialog = false
            },
            containerColor = Color.White,
            title = { Text(text = "계정 삭제", fontWeight = FontWeight.Bold, color = Color(0xFFC62828)) },
            text = {
                Column {
                    Text(
                        text =
                            "계정을 삭제하면 이메일·비밀번호·로그인 세션 등 계정 개인정보가 삭제됩니다. " +
                                "참여·생성한 모임은 남지만, 내 모임 기록은 「탈퇴한 사용자」로 익명 처리됩니다. " +
                                "다른 참가자의 계정과 데이터는 삭제되지 않습니다. 이 작업은 되돌릴 수 없습니다.",
                        fontSize = 13.sp,
                        color = Color(0xFF555555),
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedTextField(
                        value = deletePasswordInput,
                        onValueChange = { deletePasswordInput = it },
                        placeholder = { Text("비밀번호 재입력") },
                        singleLine = true,
                        enabled = !deletingAccount,
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (deletePasswordInput.isNotBlank() && !deletingAccount) {
                            onDeleteAccountClick(deletePasswordInput)
                            showDeleteAccountDialog = false
                        }
                    },
                    enabled = !deletingAccount && deletePasswordInput.isNotBlank(),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFC62828)),
                ) {
                    Text(text = "삭제하기", color = Color.White, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { showDeleteAccountDialog = false },
                    enabled = !deletingAccount,
                ) {
                    Text(text = "취소", color = Color.Gray)
                }
            },
        )
    }
}
