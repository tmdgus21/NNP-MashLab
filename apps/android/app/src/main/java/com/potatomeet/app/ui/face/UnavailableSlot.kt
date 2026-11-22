package com.potatomeet.app.ui.face

/** Local-only unavailable half-hour slot (not submitted to API). */
data class UnavailableSlot(
    val dateIso: String,
    val startHour: Int,
    val startMin: Int = 0,
    val endHour: Int,
    val endMin: Int = 0,
) {
    fun matches(other: UnavailableSlot): Boolean =
        dateIso == other.dateIso &&
            startHour == other.startHour &&
            startMin == other.startMin
}

/** 00:00–24:00 as 48 independent 30-minute slots. */
fun halfHourSlotsForDate(dateIso: String): List<UnavailableSlot> =
    (0 until 48).map { index ->
        val startTotal = index * 30
        val endTotal = startTotal + 30
        UnavailableSlot(
            dateIso = dateIso,
            startHour = startTotal / 60,
            startMin = startTotal % 60,
            endHour = endTotal / 60,
            endMin = endTotal % 60,
        )
    }

fun UnavailableSlot.timeLabel(): String {
    val endLabel =
        if (endHour == 24 && endMin == 0) {
            "24:00"
        } else {
            String.format("%02d:%02d", endHour, endMin)
        }
    return String.format("%02d:%02d ~ %s", startHour, startMin, endLabel)
}
