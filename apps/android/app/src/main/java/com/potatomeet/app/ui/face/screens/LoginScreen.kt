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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
fun LoginScreen(
    isLoading: Boolean = false,
    onLoginSubmit: (email: String, password: String) -> Unit,
    onSignUpClick: () -> Unit,
) {
    var inputId by remember { mutableStateOf("") }
    var inputPw by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var inputAuthCode by remember { mutableStateOf("") }
    var isGoogleVerified by remember { mutableStateOf(false) }
    val context = LocalContext.current

    Column(
        modifier = Modifier.fillMaxSize().padding(horizontal = 30.dp).verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Image(
            painter = painterResource(id = R.drawable.potato_logo),
            contentDescription = "Logo",
            modifier = Modifier.size(130.dp)
        )
        Spacer(modifier = Modifier.height(10.dp))

        Text(
            text = buildAnnotatedString {
                withStyle(SpanStyle(color = Color(0xFF4A3B32), fontWeight = FontWeight.ExtraBold)) { append("potato ") }
                withStyle(SpanStyle(color = Color(0xFFFF9800), fontWeight = FontWeight.ExtraBold)) { append("meet") }
            },
            fontSize = 32.sp
        )
        Spacer(modifier = Modifier.height(6.dp))
        Text(text = "함께하는 일정, 더 쉬운 약속", fontSize = 15.sp, color = Color(0xFF666666))
        Spacer(modifier = Modifier.height(24.dp))

        OutlinedTextField(
            value = inputId,
            onValueChange = { inputId = it },
            placeholder = { Text("이메일 입력", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            enabled = !isLoading,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFFFFD54F),
                unfocusedBorderColor = Color(0xFFE0E0E0),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
        Spacer(modifier = Modifier.height(10.dp))

        OutlinedTextField(
            value = inputPw,
            onValueChange = { inputPw = it },
            placeholder = { Text("비밀번호 입력", color = Color(0xFFAAAAAA)) },
            singleLine = true,
            enabled = !isLoading,
            visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            trailingIcon = {
                val image = if (passwordVisible) "👁️‍🗨️" else "👁️‍🗨️"
                IconButton(onClick = { passwordVisible = !passwordVisible }) {
                    Text(text = image, fontSize = 16.sp)
                }
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(26.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Color(0xFFFFD54F),
                unfocusedBorderColor = Color(0xFFE0E0E0),
                focusedContainerColor = Color.White,
                unfocusedContainerColor = Color.White
            )
        )
        Spacer(modifier = Modifier.height(10.dp))

        // Google UI kept for face design; not required for /v1/auth email login.
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Button(
                onClick = {
                    isGoogleVerified = true
                    Toast.makeText(context, "이메일 로그인을 사용해 주세요. (구글 연동 준비 중)", Toast.LENGTH_SHORT).show()
                },
                modifier = Modifier.height(52.dp),
                enabled = !isLoading,
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isGoogleVerified) Color(0xFFE8F5E9) else Color(0xFFFFD54F)
                ),
                shape = RoundedCornerShape(26.dp),
                contentPadding = PaddingValues(horizontal = 12.dp)
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier.size(22.dp).clip(CircleShape).background(Color.White),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(text = "G", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFF4285F4))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = if (isGoogleVerified) "인증완료" else "인증코드 보내기",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (isGoogleVerified) Color(0xFF2E7D32) else Color(0xFF3C1E1E)
                    )
                }
            }

            OutlinedTextField(
                value = inputAuthCode,
                onValueChange = { inputAuthCode = it },
                placeholder = { Text("인증코드 입력", color = Color(0xFFAAAAAA), fontSize = 13.sp) },
                singleLine = true,
                enabled = !isLoading,
                modifier = Modifier.weight(1f).height(52.dp),
                shape = RoundedCornerShape(26.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Color(0xFFFFD54F),
                    unfocusedBorderColor = Color(0xFFE0E0E0),
                    focusedContainerColor = Color.White,
                    unfocusedContainerColor = Color.White
                )
            )
        }

        Spacer(modifier = Modifier.height(20.dp))

        Button(
            onClick = { onLoginSubmit(inputId, inputPw) },
            enabled = !isLoading,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4A3B32)),
            shape = RoundedCornerShape(26.dp)
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(22.dp),
                    color = Color.White,
                    strokeWidth = 2.dp,
                )
            } else {
                Text(text = "로그인하기", fontSize = 17.sp, fontWeight = FontWeight.Bold, color = Color.White)
            }
        }

        Spacer(modifier = Modifier.height(20.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(text = "계정이 없으신가요?", fontSize = 14.sp, color = Color(0xFF999999))
            Spacer(modifier = Modifier.width(6.dp))
            TextButton(onClick = onSignUpClick, enabled = !isLoading, contentPadding = PaddingValues(0.dp)) {
                Text(text = "회원가입", fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color(0xFFFFB300))
            }
        }
    }
}
