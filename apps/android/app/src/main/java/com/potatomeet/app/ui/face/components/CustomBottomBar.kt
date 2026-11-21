package com.potatomeet.app.ui.face.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun CustomBottomBar(
    currentRoute: String,
    onTabSelected: (String) -> Unit,
) {
    val items =
        listOf(
            Triple("home", "홈", "🏠"),
            Triple("create_room", "모임만들기", "➕"),
            Triple("friends", "친구", "👥"),
            Triple("mypage", "MY", "👤"),
        )

    Surface(
        modifier = Modifier.fillMaxWidth().height(65.dp),
        color = Color.White,
        shadowElevation = 8.dp,
    ) {
        Row(
            modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            items.forEach { (route, label, icon) ->
                val isSelected =
                    currentRoute == route ||
                        (route == "create_room" && currentRoute.startsWith("create_"))

                Column(
                    modifier =
                        Modifier
                            .clickable { onTabSelected(route) }
                            .padding(horizontal = 8.dp, vertical = 4.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Text(
                        text = icon,
                        fontSize = 18.sp,
                        color = if (isSelected) Color(0xFFFF9800) else Color(0xFF888888),
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = label,
                        fontSize = 11.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) Color(0xFFFF9800) else Color(0xFF888888),
                    )
                }
            }
        }
    }
}
