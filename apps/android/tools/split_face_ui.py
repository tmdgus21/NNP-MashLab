#!/usr/bin/env python3
"""Split face UI dump into Compose source files. Preserves UI body; renames package only."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUMP = ROOT / "upstream" / "face-db93eeb" / "app-pm_ver1_test.txt"
OUT = ROOT / "app" / "src" / "main" / "java" / "com" / "potatomeet" / "app"

COMMON_IMPORTS = """\
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
"""

# 1-based inclusive ranges from Select-String on dump
SECTIONS: list[tuple[str, int, int, str]] = [
    ("ui/face/FaceModels.kt", 58, 120, "com.potatomeet.app.ui.face"),
    ("ui/face/components/CustomBottomBar.kt", 363, 412, "com.potatomeet.app.ui.face.components"),
    ("ui/face/components/TopLogoHeader.kt", 593, 649, "com.potatomeet.app.ui.face.components"),
    ("ui/face/components/SwipableCalendarWidget.kt", 1024, 1198, "com.potatomeet.app.ui.face.components"),
    ("ui/face/components/RecommendationCard.kt", 2529, 2675, "com.potatomeet.app.ui.face.components"),
    ("ui/face/screens/FriendsScreen.kt", 413, 592, "com.potatomeet.app.ui.face.screens"),
    ("ui/face/screens/LoginScreen.kt", 650, 828, "com.potatomeet.app.ui.face.screens"),
    ("ui/face/screens/SignUpScreen.kt", 829, 1023, "com.potatomeet.app.ui.face.screens"),
    ("ui/face/screens/HomeScreen.kt", 1199, 1474, "com.potatomeet.app.ui.face.screens"),
    ("ui/face/screens/CreateAppointmentStep1Screen.kt", 1475, 1566, "com.potatomeet.app.ui.face.screens"),
    ("ui/face/screens/CreateAppointmentStep2InviteScreen.kt", 1567, 1707, "com.potatomeet.app.ui.face.screens"),
    ("ui/face/screens/CreateAppointmentStep3TimeScreen.kt", 1708, 2138, "com.potatomeet.app.ui.face.screens"),
    ("ui/face/screens/CreateAppointmentStep4AdjustScreen.kt", 2139, 2342, "com.potatomeet.app.ui.face.screens"),
    ("ui/face/screens/AiRecommendationScreen.kt", 2343, 2528, "com.potatomeet.app.ui.face.screens"),
]


def slice_lines(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def write(path: Path, package: str, body: str, extra_imports: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Drop leading @Composable lone lines that belong with following fun — keep as-is from dump
    content = (
        f"package {package}\n\n"
        f"{COMMON_IMPORTS}"
        f"{extra_imports}\n"
        f"{body.rstrip()}\n"
    )
    # Fix any leftover example package / theme refs inside body
    content = content.replace("com.example.potatomeet", "com.potatomeet.app")
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({len(body.splitlines())} lines)")


def main() -> None:
    text = DUMP.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    print(f"dump lines={len(lines)}")

    for rel, start, end, package in SECTIONS:
        end = min(end, len(lines))
        body = slice_lines(lines, start, end)
        extras = ""
        if "screens" in rel or "components" in rel:
            extras = (
                "import com.potatomeet.app.ui.face.Appointment\n"
                "import com.potatomeet.app.ui.face.RecommendationOption\n"
                "import com.potatomeet.app.ui.face.TimeSlot\n"
                "import com.potatomeet.app.ui.face.UserAccount\n"
                "import com.potatomeet.app.ui.face.mergeTimeSlots\n"
                "import com.potatomeet.app.ui.face.components.CustomBottomBar\n"
                "import com.potatomeet.app.ui.face.components.LockWheelColumn\n"
                "import com.potatomeet.app.ui.face.components.RecommendationCard\n"
                "import com.potatomeet.app.ui.face.components.SeamlessInputBox\n"
                "import com.potatomeet.app.ui.face.components.StepIndicatorItem\n"
                "import com.potatomeet.app.ui.face.components.SwipableCalendarWidget\n"
                "import com.potatomeet.app.ui.face.components.TopLogoHeader\n"
            )
        if "RecommendationCard" in rel:
            # includes SeamlessInputBox + LockWheelColumn in same range
            pass
        write(OUT / rel, package, body, extras)

    # Face root nav: MainActivity body (lines 122-361) → FaceRoot.kt as composable
    main_body = slice_lines(lines, 125, 359)  # inside setContent { PotatoMeetTheme { ... } }
    # Convert Activity wrapper to @Composable FaceRoot
    face_root = """
import android.app.Activity
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import com.potatomeet.app.ui.face.components.CustomBottomBar
import com.potatomeet.app.ui.face.screens.AiRecommendationScreen
import com.potatomeet.app.ui.face.screens.CreateAppointmentStep1Screen
import com.potatomeet.app.ui.face.screens.CreateAppointmentStep2InviteScreen
import com.potatomeet.app.ui.face.screens.CreateAppointmentStep3TimeScreen
import com.potatomeet.app.ui.face.screens.CreateAppointmentStep4AdjustScreen
import com.potatomeet.app.ui.face.screens.FriendsScreen
import com.potatomeet.app.ui.face.screens.HomeScreen
import com.potatomeet.app.ui.face.screens.LoginScreen
import com.potatomeet.app.ui.face.screens.MyPageScreen
import com.potatomeet.app.ui.face.screens.SignUpScreen
import java.util.Calendar

@Composable
fun FaceRoot() {
    val activity = LocalContext.current as? Activity
    val currentScreen = remember { mutableStateOf("login") }

                val adminAccount = remember {
                    UserAccount(
                        nickname = "관리자",
                        id = "admin",
                        pw = "admin!@#",
                        twoFactorCode = "GOOGLE_AUTH_VERIFIED"
                    )
                }

                val registeredAccount = remember { mutableStateOf<UserAccount?>(null) }
                val loggedInNickname = remember { mutableStateOf("") }
                val loggedInId = remember { mutableStateOf("") }

                val appointmentName = remember { mutableStateOf("") }
                val category = remember { mutableStateOf("") }
                val duration = remember { mutableStateOf("") }
                val location = remember { mutableStateOf("") }

                val createdTimeSlots = remember { mutableStateListOf<TimeSlot>() }
                val selectedFriendsForNew = remember { mutableStateMapOf<String, Boolean>() }
                val selectedAiRecommendationTime = remember { mutableStateOf("") }

                val appointmentsList = remember { mutableStateListOf<Appointment>() }

                val currentCalendar = remember { Calendar.getInstance() }
                var sharedCalendarYear by remember { mutableStateOf(currentCalendar.get(Calendar.YEAR)) }
                var sharedCalendarMonth by remember { mutableStateOf(currentCalendar.get(Calendar.MONTH) + 1) }
                var sharedSelectedDay by remember { mutableStateOf(currentCalendar.get(Calendar.DAY_OF_MONTH)) }

                BackHandler(enabled = currentScreen.value != "login") {
                    when (currentScreen.value) {
                        "signup" -> currentScreen.value = "login"
                        "home", "friends", "mypage" -> activity?.finish()
                        "create_step1" -> currentScreen.value = "home"
                        "create_step2" -> currentScreen.value = "create_step1"
                        "create_step3" -> currentScreen.value = "create_step2"
                        "create_step4" -> currentScreen.value = "create_step3"
                        "create_ai_recommendation" -> currentScreen.value = "create_step4"
                    }
                }

                Surface(
                    modifier = Modifier.fillMaxSize().imePadding(),
                    color = Color(0xFFFFFCF3)
                ) {
"""
    # Extract from original Surface block — use lines 170-357 from dump (Surface...closing)
    surface = slice_lines(lines, 170, 357)
    # fix finish() already handled in BackHandler above; remove finish() if in surface - N/A
    face_path = OUT / "ui/face/FaceRoot.kt"
    face_path.parent.mkdir(parents=True, exist_ok=True)
    face_path.write_text(
        "package com.potatomeet.app.ui.face\n\n" + face_root + surface + "\n}\n",
        encoding="utf-8",
    )
    print(f"wrote {face_path.relative_to(ROOT)}")

    # MyPage was bundled with Friends range start — Friends is 413-465, MyPage 466-592
    # Already in FriendsScreen.kt range 413-592 which includes MyPage — OK same file or split
    friends = slice_lines(lines, 413, 465)
    mypage = slice_lines(lines, 466, 592)
    write(
        OUT / "ui/face/screens/FriendsScreen.kt",
        "com.potatomeet.app.ui.face.screens",
        friends,
        "import com.potatomeet.app.ui.face.components.TopLogoHeader\n",
    )
    write(
        OUT / "ui/face/screens/MyPageScreen.kt",
        "com.potatomeet.app.ui.face.screens",
        mypage,
        "import com.potatomeet.app.ui.face.components.TopLogoHeader\n",
    )

    # Split RecommendationCard file: 2529-2577 card, 2578-2597 input, 2598-end wheels
    write(
        OUT / "ui/face/components/RecommendationCard.kt",
        "com.potatomeet.app.ui.face.components",
        slice_lines(lines, 2529, 2577),
        "import com.potatomeet.app.ui.face.RecommendationOption\n",
    )
    write(
        OUT / "ui/face/components/SeamlessInputBox.kt",
        "com.potatomeet.app.ui.face.components",
        slice_lines(lines, 2578, 2597),
        "",
    )
    write(
        OUT / "ui/face/components/LockWheelColumn.kt",
        "com.potatomeet.app.ui.face.components",
        slice_lines(lines, 2598, len(lines)),
        "",
    )
    write(
        OUT / "ui/face/components/StepIndicatorItem.kt",
        "com.potatomeet.app.ui.face.components",
        slice_lines(lines, 619, 649),
        "",
    )
    # TopLogo only 593-618
    write(
        OUT / "ui/face/components/TopLogoHeader.kt",
        "com.potatomeet.app.ui.face.components",
        slice_lines(lines, 593, 618),
        "",
    )


if __name__ == "__main__":
    main()
