package com.potatomeet.app.ui.face.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.widget.Toast
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.potatomeet.app.ui.face.components.StepIndicatorItem
import com.potatomeet.app.ui.face.components.TopLogoHeader

@Composable
fun CreateAppointmentStep2InviteScreen(
    isAdmin: Boolean,
    selectedFriendsMap: MutableMap<String, Boolean>,
    inviteCode: String? = null,
    onBackClick: () -> Unit,
    onNextClick: () -> Unit,
    onStepClick: (String) -> Unit,
) {
    val context = LocalContext.current
    val friendsList = if (isAdmin) listOf("민수", "지훈", "영희", "철수") else emptyList()

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
            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceAround,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                StepIndicatorItem(stepNumber = "1", title = "모임 정보", isActive = false, onClick = { onStepClick("create_step1") })
                StepIndicatorItem(
                    stepNumber = "2",
                    title = "친구 초대",
                    isActive = true,
                    onClick = { onStepClick("create_step2") },
                    activeTextSize = 12.sp,
                )
                StepIndicatorItem(stepNumber = "3", title = "나의 시간", isActive = false, onClick = { onStepClick("create_step3") })
                StepIndicatorItem(stepNumber = "4", title = "시간 조율", isActive = false, onClick = { onStepClick("create_step4") })
            }
            Spacer(modifier = Modifier.height(20.dp))

            if (!inviteCode.isNullOrBlank()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                    shape = RoundedCornerShape(20.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Text(text = "초대 코드", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = inviteCode,
                            fontSize = 28.sp,
                            fontWeight = FontWeight.ExtraBold,
                            color = Color(0xFFFF9800),
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "https://oranganman.site/join?code=$inviteCode",
                            fontSize = 12.sp,
                            color = Color(0xFF888888),
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                        OutlinedButton(
                            onClick = {
                                val clipboard =
                                    context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                clipboard.setPrimaryClip(ClipData.newPlainText("invite", inviteCode))
                                Toast.makeText(context, "초대 코드를 복사했습니다.", Toast.LENGTH_SHORT).show()
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                        ) {
                            Text(text = "코드 복사", fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                        }
                    }
                }
                Spacer(modifier = Modifier.height(14.dp))
            }

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color.White),
                shape = RoundedCornerShape(20.dp),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(text = "누구와 만날까요?", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Color(0xFF333333))
                    Spacer(modifier = Modifier.height(14.dp))

                    OutlinedTextField(value = "", onValueChange = {
                    }, placeholder = {
                        Text("친구 검색하기", color = Color(0xFFAAAAAA))
                    }, singleLine = true, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp))
                    Spacer(modifier = Modifier.height(14.dp))

                    if (friendsList.isEmpty()) {
                        Box(
                            modifier = Modifier.fillMaxWidth().height(150.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                text =
                                    if (!inviteCode.isNullOrBlank()) {
                                        "친구 목록은 준비 중이에요. 위 코드로 초대해 주세요."
                                    } else {
                                        "초대할 친구가 없습니다."
                                    },
                                fontSize = 14.sp,
                                color = Color(0xFFAAAAAA),
                            )
                        }
                    } else {
                        LazyColumn(modifier = Modifier.fillMaxWidth().height(300.dp)) {
                            items(friendsList) { friend ->
                                val isSelected = selectedFriendsMap[friend] ?: false
                                Row(
                                    modifier =
                                        Modifier.fillMaxWidth().clickable { selectedFriendsMap[friend] = !isSelected }.padding(
                                            vertical = 8.dp,
                                        ),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Box(
                                            modifier = Modifier.size(36.dp).clip(CircleShape).background(Color(0xFFE0E0E0)),
                                            contentAlignment = Alignment.Center,
                                        ) {
                                            Text(
                                                text = friend.take(1),
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = Color.DarkGray,
                                            )
                                        }
                                        Spacer(modifier = Modifier.width(12.dp))
                                        Text(text = friend, fontSize = 15.sp, color = Color(0xFF333333))
                                    }
                                    Checkbox(checked = isSelected, onCheckedChange = {
                                        selectedFriendsMap[friend] = it
                                    }, colors = CheckboxDefaults.colors(checkedColor = Color(0xFFFFD54F)))
                                }
                            }
                        }
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFFFFCF3))
                    .padding(horizontal = 20.dp, vertical = 12.dp),
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = {
                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        val clip = ClipData.newPlainText("PotatoMeet Invite", "https://potatomeet.app/invite/room123")
                        clipboard.setPrimaryClip(clip)
                        Toast.makeText(context, "초대 링크가 복사되었습니다!", Toast.LENGTH_SHORT).show()
                    },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Text(text = "🔗 링크로 초대하기 (복사)", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                }

                Button(
                    onClick = {
                        val intent =
                            Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"
                                setPackage("com.kakao.talk")
                                putExtra(Intent.EXTRA_TEXT, "[Potato Meet] 모임에 초대합니다! 링크: https://potatomeet.app/invite/room123")
                            }
                        try {
                            context.startActivity(intent)
                        } catch (e: Exception) {
                            val shareIntent =
                                Intent(Intent.ACTION_SEND).apply {
                                    type = "text/plain"
                                    putExtra(Intent.EXTRA_TEXT, "[Potato Meet] 모임에 초대합니다! 링크: https://potatomeet.app/invite/room123")
                                }
                            context.startActivity(Intent.createChooser(shareIntent, "공유하기"))
                        }
                    },
                    modifier = Modifier.fillMaxWidth().height(44.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFE082)),
                ) {
                    Text(text = "💛 카카오톡으로 공유하기", fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                }

                Button(
                    onClick = onNextClick,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFFFD54F)),
                    shape = RoundedCornerShape(26.dp),
                ) {
                    Text(text = "다음", fontSize = 16.sp, fontWeight = FontWeight.Bold, color = Color(0xFF3C1E1E))
                }
            }
        }
    }
}

// 모임 만들기 Step 3
