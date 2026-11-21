package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun SignUpScreen(
    isLoading: Boolean = false,
    otpPending: Boolean = false,
    onRequestOtp: (nickname: String, email: String, password: String, passwordConfirm: String) -> Unit,
    onVerifyOtp: (code: String) -> Unit,
    onResendOtp: () -> Unit = {},
    onBackClick: () -> Unit,
) {
    var nickname by remember { mutableStateOf("") }
    var id by remember { mutableStateOf("") }
    var pw by remember { mutableStateOf("") }
    var pwConfirm by remember { mutableStateOf("") }
    var authCode by remember { mutableStateOf("") }
    var pwVisible by remember { mutableStateOf(false) }
    var pwConfirmVisible by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }

    val fieldColors =
        OutlinedTextFieldDefaults.colors(
            unfocusedContainerColor = Color.White,
            focusedContainerColor = Color.White,
            unfocusedBorderColor = Color(0xFFE0E0E0),
            focusedBorderColor = Color(0xFFFF9800),
        )

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .padding(horizontal = 30.dp)
                .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(text = "회원가입", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
        Spacer(modifier = Modifier.height(24.dp))

        OutlinedTextField(
            value = nickname,
            onValueChange = {
                nickname = it
                errorMessage = ""
            },
            placeholder = { Text("사용할 닉네임", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            enabled = !isLoading,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = fieldColors,
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = id,
            onValueChange = {
                id = it
                errorMessage = ""
            },
            placeholder = { Text("이메일", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            enabled = !isLoading,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = fieldColors,
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = pw,
            onValueChange = {
                pw = it
                errorMessage = ""
            },
            placeholder = { Text("비밀번호 (12자 이상)", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            enabled = !isLoading,
            visualTransformation =
                if (pwVisible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                Text(
                    text = if (pwVisible) "숨김" else "표시",
                    fontSize = 12.sp,
                    color = Color.Gray,
                    modifier =
                        Modifier
                            .clickable(enabled = !isLoading) { pwVisible = !pwVisible }
                            .padding(8.dp),
                )
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = fieldColors,
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = pwConfirm,
            onValueChange = {
                pwConfirm = it
                errorMessage = ""
            },
            placeholder = { Text("비밀번호 확인", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            enabled = !isLoading,
            visualTransformation =
                if (pwConfirmVisible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                Text(
                    text = if (pwConfirmVisible) "숨김" else "표시",
                    fontSize = 12.sp,
                    color = Color.Gray,
                    modifier =
                        Modifier
                            .clickable(enabled = !isLoading) { pwConfirmVisible = !pwConfirmVisible }
                            .padding(8.dp),
                )
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = fieldColors,
        )
        Spacer(modifier = Modifier.height(10.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Button(
                onClick = {
                    when {
                        nickname.isBlank() -> errorMessage = "사용할 닉네임을 입력하지 않았습니다."
                        id.isBlank() -> errorMessage = "이메일을 입력하지 않았습니다."
                        pw.isBlank() -> errorMessage = "비밀번호를 입력하지 않았습니다."
                        pwConfirm.isBlank() -> errorMessage = "비밀번호 확인을 입력하지 않았습니다."
                        pw != pwConfirm -> errorMessage = "비밀번호가 일치하지 않습니다."
                        else -> {
                            errorMessage = ""
                            if (otpPending) onResendOtp() else onRequestOtp(nickname, id, pw, pwConfirm)
                        }
                    }
                },
                enabled = !isLoading,
                modifier = Modifier.weight(1f).height(52.dp),
                colors =
                    ButtonDefaults.buttonColors(
                        containerColor = if (otpPending) Color(0xFFE8F5E9) else Color(0xFFFFD54F),
                    ),
                shape = RoundedCornerShape(26.dp),
            ) {
                Text(
                    text = if (otpPending) "재발송" else "인증코드 보내기",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = if (otpPending) Color(0xFF2E7D32) else Color(0xFF3C1E1E),
                )
            }

            OutlinedTextField(
                value = authCode,
                onValueChange = {
                    authCode = it.filter { ch -> ch.isDigit() }.take(6)
                    errorMessage = ""
                },
                placeholder = { Text("인증코드 입력", color = Color(0xFFAAAAAA)) },
                singleLine = true,
                enabled = !isLoading,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.weight(1.1f).height(52.dp),
                shape = RoundedCornerShape(26.dp),
                colors = fieldColors,
            )
        }

        if (errorMessage.isNotEmpty()) {
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = errorMessage,
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFFD32F2F),
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Button(
            onClick = {
                when {
                    !otpPending -> errorMessage = "먼저 인증코드를 받아 주세요."
                    authCode.isBlank() -> errorMessage = "인증코드를 입력하지 않았습니다."
                    else -> {
                        errorMessage = ""
                        onVerifyOtp(authCode)
                    }
                }
            },
            enabled = !isLoading,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
            shape = RoundedCornerShape(26.dp),
        ) {
            Text(text = "회원가입 완료", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
        }

        Spacer(modifier = Modifier.height(16.dp))
        TextButton(onClick = onBackClick, enabled = !isLoading) {
            Text(text = "돌아가기", fontSize = 14.sp, color = Color(0xFF888888))
        }
    }
}
