package com.potatomeet.app.ui.face.components

import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.TextFieldColors
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

@Composable
fun faceTextFieldColors(): TextFieldColors =
    OutlinedTextFieldDefaults.colors(
        focusedBorderColor = Color(0xFFFFB300),
        unfocusedBorderColor = Color(0xFFE0E0E0),
        focusedContainerColor = Color.White,
        unfocusedContainerColor = Color.White,
        cursorColor = Color(0xFFFF8F00),
        focusedLabelColor = Color(0xFF4A3B32),
        unfocusedLabelColor = Color(0xFF888888),
    )
