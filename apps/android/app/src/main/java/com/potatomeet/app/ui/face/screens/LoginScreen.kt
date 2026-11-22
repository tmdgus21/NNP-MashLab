package com.potatomeet.app.ui.face.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.Image
import com.potatomeet.app.R

@Composable
fun LoginScreen(
    isLoading: Boolean = false,
    otpPending: Boolean = false,
    onRequestOtp: (email: String, password: String) -> Unit,
    onVerifyOtp: (code: String) -> Unit,
    onResendOtp: () -> Unit = {},
    onSignUpClick: () -> Unit,
) {
    var inputId by remember { mutableStateOf("") }
    var inputPw by remember { mutableStateOf("") }
    var inputAuthCode by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .padding(horizontal = 30.dp)
                .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Image(
            painter = painterResource(id = R.drawable.potato_logo),
            contentDescription = "Logo",
            modifier = Modifier.size(130.dp),
        )
        Spacer(modifier = Modifier.height(10.dp))
        Text(
            text =
                buildAnnotatedString {
                    withStyle(SpanStyle(color = Color(0xFF4A3B32), fontWeight = FontWeight.ExtraBold)) {
                        append("potato ")
                    }
                    withStyle(SpanStyle(color = Color(0xFFFF9800), fontWeight = FontWeight.ExtraBold)) {
                        append("meet")
                    }
                },
            fontSize = 32.sp,
        )
        Spacer(modifier = Modifier.height(6.dp))
        Text(text = "함께하는 일정, 더 쉬운 약속", fontSize = 14.sp, color = Color(0xFF666666))
        Spacer(modifier = Modifier.height(28.dp))

        OutlinedTextField(
            value = inputId,
            onValueChange = {
                inputId = it
                errorMessage = ""
            },
            placeholder = { Text("이메일 입력", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            enabled = !isLoading,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors =
                OutlinedTextFieldDefaults.colors(
                    unfocusedContainerColor = Color.White,
                    focusedContainerColor = Color.White,
                    unfocusedBorderColor = Color(0xFFE0E0E0),
                    focusedBorderColor = Color(0xFFFF9800),
                ),
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = inputPw,
            onValueChange = {
                inputPw = it
                errorMessage = ""
            },
            placeholder = { Text("비밀번호 입력", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            enabled = !isLoading,
            visualTransformation =
                if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
            trailingIcon = {
                Text(
                    text = if (passwordVisible) "숨김" else "표시",
                    fontSize = 12.sp,
                    color = Color.Gray,
                    modifier =
                        Modifier
                            .clickable(enabled = !isLoading) { passwordVisible = !passwordVisible }
                            .padding(8.dp),
                )
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors =
                OutlinedTextFieldDefaults.colors(
                    unfocusedContainerColor = Color.White,
                    focusedContainerColor = Color.White,
                    unfocusedBorderColor = Color(0xFFE0E0E0),
                    focusedBorderColor = Color(0xFFFF9800),
                ),
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
                        inputId.isBlank() -> errorMessage = "이메일을 입력하지 않았습니다."
                        inputPw.isBlank() -> errorMessage = "비밀번호를 입력하지 않았습니다."
                        else -> {
                            errorMessage = ""
                            if (otpPending) onResendOtp() else onRequestOtp(inputId, inputPw)
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
                value = inputAuthCode,
                onValueChange = {
                    inputAuthCode = it.filter { ch -> ch.isDigit() }.take(6)
                    errorMessage = ""
                },
                placeholder = { Text("인증코드 입력", color = Color(0xFFAAAAAA)) },
                singleLine = true,
                enabled = !isLoading,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.weight(1.1f).height(52.dp),
                shape = RoundedCornerShape(26.dp),
                colors =
                    OutlinedTextFieldDefaults.colors(
                        unfocusedContainerColor = Color.White,
                        focusedContainerColor = Color.White,
                        unfocusedBorderColor = Color(0xFFE0E0E0),
                        focusedBorderColor = Color(0xFFFF9800),
                    ),
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
                    inputId.isBlank() -> errorMessage = "이메일을 입력하지 않았습니다."
                    inputPw.isBlank() -> errorMessage = "비밀번호를 입력하지 않았습니다."
                    !otpPending -> errorMessage = "먼저 인증코드를 받아 주세요."
                    inputAuthCode.isBlank() -> errorMessage = "인증코드를 입력하지 않았습니다."
                    else -> {
                        errorMessage = ""
                        onVerifyOtp(inputAuthCode)
                    }
                }
            },
            enabled = !isLoading,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4A3B32)),
            shape = RoundedCornerShape(26.dp),
        ) {
            Text(text = "로그인하기", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color.White)
        }

        Spacer(modifier = Modifier.height(20.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(text = "계정이 없으신가요?", fontSize = 14.sp, color = Color(0xFF999999))
            Spacer(modifier = Modifier.width(6.dp))
            TextButton(
                onClick = onSignUpClick,
                enabled = !isLoading,
                contentPadding = PaddingValues(0.dp),
            ) {
                Text(
                    text = "회원가입",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFFFB300),
                )
            }
        }
    }
}
