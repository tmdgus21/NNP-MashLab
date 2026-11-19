package com.potatomeet.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val PotatoLightColors =
    lightColorScheme(
        primary = Color(0xFFFF9800),
        onPrimary = Color(0xFF3C1E1E),
        secondary = Color(0xFFFF8F00),
        background = Color(0xFFFFFCF3),
        surface = Color(0xFFFFFCF3),
        onBackground = Color(0xFF333333),
        onSurface = Color(0xFF333333),
    )

@Composable
fun PotatoMeetTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = PotatoLightColors,
        content = content,
    )
}
