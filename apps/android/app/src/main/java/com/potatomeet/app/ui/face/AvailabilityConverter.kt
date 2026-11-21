package com.potatomeet.app.ui.face

import com.potatomeet.app.core.TimeFmt
import com.potatomeet.app.data.remote.dto.TimeRangeDto
import java.time.LocalDate
import java.time.OffsetDateTime

/**
 * Convert between UI unavailable half-hour slots and API available ranges (+09:00).
 * Unmarked slots are available; consecutive available slots merge into one range.
 * End at 24:00 becomes next-day 00:00.
 */
object AvailabilityConverter {
    data class SubmitPayload(
        val ranges: List<Pair<String, String>>,
        val allUnavailable: Boolean,
    )

    fun toAvailablePayload(
        selectedIsoDates: List<String>,
        unavailable: List<UnavailableSlot>,
    ): SubmitPayload {
        val dates = selectedIsoDates.map { it.take(10) }.distinct().sorted()
        if (dates.isEmpty()) {
            return SubmitPayload(emptyList(), allUnavailable = true)
        }
        val unavailableKeys =
            unavailable
                .filter { it.dateIso.take(10) in dates }
                .map { slotKey(it.dateIso, it.startHour, it.startMin) }
                .toSet()

        val availableSlots = mutableListOf<Pair<LocalDate, Int>>() // date + slot index 0..47
        for (iso in dates) {
            val day = LocalDate.parse(iso)
            for (index in 0 until 48) {
                val startMin = index * 30
                val key = slotKey(iso, startMin / 60, startMin % 60)
                if (key !in unavailableKeys) {
                    availableSlots.add(day to index)
                }
            }
        }
        if (availableSlots.isEmpty()) {
            return SubmitPayload(emptyList(), allUnavailable = true)
        }

        val merged = mutableListOf<Pair<String, String>>()
        var runDay: LocalDate? = null
        var runStart = -1
        var runEnd = -1
        fun flush() {
            val day = runDay ?: return
            if (runStart < 0) return
            merged.add(rangeIso(day, runStart, runEnd))
            runDay = null
            runStart = -1
            runEnd = -1
        }
        for ((day, index) in availableSlots) {
            if (runDay == day && index == runEnd) {
                runEnd = index + 1
            } else {
                flush()
                runDay = day
                runStart = index
                runEnd = index + 1
            }
        }
        flush()
        return SubmitPayload(merged, allUnavailable = false)
    }

    fun toUnavailableSlots(
        selectedIsoDates: List<String>,
        myAvailable: List<TimeRangeDto>,
        mySubmitted: Boolean,
    ): List<UnavailableSlot> {
        if (!mySubmitted) return emptyList()
        val dates = selectedIsoDates.map { it.take(10) }.distinct()
        if (myAvailable.isEmpty()) {
            // Submitted with no ranges → all unavailable on meeting dates.
            return dates.flatMap { halfHourSlotsForDate(it) }
        }
        val availableKeys = mutableSetOf<String>()
        for (range in myAvailable) {
            availableKeys.addAll(expandRangeToSlotKeys(range.start, range.end))
        }
        return dates.flatMap { iso ->
            halfHourSlotsForDate(iso).filter { slot ->
                slotKey(slot.dateIso, slot.startHour, slot.startMin) !in availableKeys
            }
        }
    }

    private fun slotKey(
        dateIso: String,
        hour: Int,
        min: Int,
    ): String = "${dateIso.take(10)}|${hour.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}"

    private fun rangeIso(
        day: LocalDate,
        startIndex: Int,
        endIndexExclusive: Int,
    ): Pair<String, String> {
        val startTotal = startIndex * 30
        val endTotal = endIndexExclusive * 30
        val start =
            TimeFmt.seoulInstant(
                day.year,
                day.monthValue,
                day.dayOfMonth,
                startTotal / 60,
                startTotal % 60,
            )
        val end =
            if (endTotal >= 24 * 60) {
                val next = day.plusDays(1)
                TimeFmt.seoulInstant(next.year, next.monthValue, next.dayOfMonth, 0, 0)
            } else {
                TimeFmt.seoulInstant(
                    day.year,
                    day.monthValue,
                    day.dayOfMonth,
                    endTotal / 60,
                    endTotal % 60,
                )
            }
        return start to end
    }

    private fun expandRangeToSlotKeys(
        startIso: String,
        endIso: String,
    ): Set<String> {
        val start = OffsetDateTime.parse(startIso).atZoneSameInstant(TimeFmt.SEOUL)
        val end = OffsetDateTime.parse(endIso).atZoneSameInstant(TimeFmt.SEOUL)
        val keys = mutableSetOf<String>()
        var cursor = start
        while (cursor.plusMinutes(30) <= end) {
            val local = cursor.toLocalDateTime()
            keys.add(
                slotKey(
                    local.toLocalDate().toString(),
                    local.hour,
                    local.minute,
                ),
            )
            cursor = cursor.plusMinutes(30)
        }
        return keys
    }
}
