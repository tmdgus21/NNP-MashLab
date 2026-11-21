package com.potatomeet.app.ui.face

import androidx.compose.ui.graphics.Color

data class UserAccount(
    var nickname: String,
    val id: String,
    val pw: String,
    val twoFactorCode: String,
    var loginFailCount: Int = 0,
    var isLocked: Boolean = false,
)

data class TimeSlot(
    val id: Long = System.currentTimeMillis() + (0..1000).random(),
    var month: Int,
    var day: Int,
    var startHour: Int,
    var startMin: Int,
    var endHour: Int,
    var endMin: Int,
) {
    fun toFormattedString(): String {
        val sH = String.format("%02d", startHour)
        val sM = String.format("%02d", startMin)
        val eH = String.format("%02d", endHour)
        val eM = String.format("%02d", endMin)
        return "${month}월 ${day}일 $sH:$sM~$eH:$eM"
    }

    val startTotalMinutes: Int get() = startHour * 60 + startMin
    val endTotalMinutes: Int get() = endHour * 60 + endMin
}

fun mergeTimeSlots(slots: List<TimeSlot>): List<TimeSlot> {
    if (slots.isEmpty()) return emptyList()

    val sorted = slots.sortedWith(compareBy({ it.month }, { it.day }, { it.startTotalMinutes }))
    val merged = mutableListOf<TimeSlot>()

    for (slot in sorted) {
        if (merged.isEmpty()) {
            merged.add(slot.copy())
            continue
        }

        val last = merged.last()
        if (last.month == slot.month && last.day == slot.day && last.endTotalMinutes >= slot.startTotalMinutes) {
            val newEndTotal = maxOf(last.endTotalMinutes, slot.endTotalMinutes)
            last.endHour = newEndTotal / 60
            last.endMin = newEndTotal % 60
        } else {
            merged.add(slot.copy())
        }
    }
    return merged
}

data class Appointment(
    val id: Long = System.currentTimeMillis(),
    val title: String,
    val category: String,
    val duration: String,
    val location: String,
    val timeInfo: String,
    val invitedFriends: List<String>,
    /** Potato Meet API fields (empty for local-only face drafts). */
    val meetingId: String = "",
    val code: String = "",
    val status: String = "",
    val revision: Int = 0,
    val isOwner: Boolean = false,
    val collectionId: String? = null,
    val selectedDates: List<String> = emptyList(),
)

data class RecommendationOption(
    val rank: String,
    val rankColor: Color,
    val timeText: String,
    val infoText: String,
    val fitRate: String,
    val candidateId: String? = null,
)
