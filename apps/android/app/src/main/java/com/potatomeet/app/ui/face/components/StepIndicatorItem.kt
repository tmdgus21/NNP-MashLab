package com.potatomeet.app.ui.face.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun StepIndicatorItem(
    stepNumber: String,
    title: String,
    isActive: Boolean,
    onClick: () -> Unit,
    activeTextSize: androidx.compose.ui.unit.TextUnit = 11.sp,
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.clickable { onClick() },
    ) {
        Box(
            modifier =
                Modifier
                    .size(26.dp)
                    .clip(CircleShape)
                    .background(if (isActive) Color(0xFFFFD54F) else Color(0xFFE0E0E0)),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = stepNumber,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold,
                color = if (isActive) Color(0xFF3C1E1E) else Color(0xFF888888),
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = title,
            fontSize = if (isActive) activeTextSize else 10.sp,
            color = if (isActive) Color(0xFF333333) else Color(0xFFAAAAAA),
            fontWeight = if (isActive) FontWeight.Bold else FontWeight.Normal,
        )
    }
}
