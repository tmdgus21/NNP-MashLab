package com.potatomeet.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.potatomeet.app.core.InviteLinkParser
import com.potatomeet.app.ui.face.FaceRoot
import com.potatomeet.app.ui.theme.PotatoMeetTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    private var deepLinkInviteCode by mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        deepLinkInviteCode = InviteLinkParser.fromIntent(intent)
        enableEdgeToEdge()
        setContent {
            PotatoMeetTheme {
                FaceRoot(
                    deepLinkInviteCode = deepLinkInviteCode,
                    onDeepLinkInviteConsumed = { deepLinkInviteCode = null },
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        deepLinkInviteCode = InviteLinkParser.fromIntent(intent)
    }
}
