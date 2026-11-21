package com.potatomeet.app.ui.face.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun TopLogoHeader(onBackClick: (() -> Unit)? = null) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (onBackClick != null) {
            Text(
                text = "〈",
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF333333),
                modifier =
                    Modifier
                        .clickable { onBackClick() }
                        .padding(end = 12.dp),
            )
        }
        Text(
            text =
                buildAnnotatedString {
                    withStyle(SpanStyle(color = Color(0xFF4A3B32), fontWeight = FontWeight.ExtraBold)) { append("potato ") }
                    withStyle(SpanStyle(color = Color(0xFFFF9800), fontWeight = FontWeight.ExtraBold)) { append("meet") }
                },
            fontSize = 24.sp,
        )
    }
}
