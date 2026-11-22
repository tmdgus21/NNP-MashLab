package com.potatomeet.app.ui.face

import com.potatomeet.app.core.TimeFmt
import com.potatomeet.app.data.remote.dto.TimeRangeDto
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.util.Locale

/**
 * Positive available-slot selection ↔ API `available` ranges (+09:00).
 * Only slots fully inside [scopeStartsAt, scopeEndsAt) may be selected/submitted.
 * Consecutive selected half-hours merge; 24:00 becomes next-day 00:00.
 */
object AvailabilityConverter {
    data class SubmitPayload(
        val ranges: List<Pair<String, String>>,
        /** True only when caller explicitly wants all-unavailable (empty available). */
        val allUnavailable: Boolean,
    )

    data class DisplayLine(
        val dateLabel: String,
        val rangeLabel: String,
    )

    /**
     * Selected available slots → merged API ranges.
     * Empty selection → empty ranges (caller must block save; do not treat as full-day).
     */
    fun toAvailablePayload(
        selectedIsoDates: List<String>,
        selectedAvailable: List<UnavailableSlot>,
        scopeStartsAt: String? = null,
        scopeEndsAt: String? = null,
    ): SubmitPayload {
        val dates = selectedIsoDates.map { it.take(10) }.distinct().sorted()
        if (dates.isEmpty()) {
            return SubmitPayload(emptyList(), allUnavailable = false)
        }
        val scopeStart = parseScope(scopeStartsAt)
        val scopeEnd = parseScope(scopeEndsAt)

        val availableSlots = mutableListOf<Pair<LocalDate, Int>>()
        for (slot in selectedAvailable) {
            val iso = slot.dateIso.take(10)
            if (iso !in dates) continue
            if (!isSlotInScope(slot, scopeStart, scopeEnd)) continue
            val index = slot.startHour * 2 + slot.startMin / 30
            availableSlots.add(LocalDate.parse(iso) to index)
        }
        availableSlots.sortWith(compareBy({ it.first }, { it.second }))

        if (availableSlots.isEmpty()) {
            return SubmitPayload(emptyList(), allUnavailable = false)
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

    /** Restore `myAvailable` directly as selected available slots (no complement). */
    fun toAvailableSlots(
        selectedIsoDates: List<String>,
        myAvailable: List<TimeRangeDto>,
        mySubmitted: Boolean,
        scopeStartsAt: String? = null,
        scopeEndsAt: String? = null,
    ): List<UnavailableSlot> {
        if (!mySubmitted || myAvailable.isEmpty()) return emptyList()
        val dates = selectedIsoDates.map { it.take(10) }.distinct().toSet()
        val scopeStart = parseScope(scopeStartsAt)
        val scopeEnd = parseScope(scopeEndsAt)
        val keys = mutableSetOf<String>()
        for (range in myAvailable) {
            keys.addAll(expandRangeToSlotKeys(range.start, range.end))
        }
        return dates
            .flatMap { iso -> halfHourSlotsForDate(iso) }
            .filter { isSlotInScope(it, scopeStart, scopeEnd) }
            .filter { slotKey(it.dateIso, it.startHour, it.startMin) in keys }
    }

    fun formatAvailableDisplay(
        myAvailable: List<TimeRangeDto>,
        mySubmitted: Boolean,
    ): List<DisplayLine> {
        if (!mySubmitted || myAvailable.isEmpty()) return emptyList()
        val dayFmt = DateTimeFormatter.ofPattern("M.d")
        val timeFmt = DateTimeFormatter.ofPattern("HH:mm")
        return myAvailable.mapNotNull { range ->
            runCatching {
                val start = OffsetDateTime.parse(range.start).atZoneSameInstant(TimeFmt.SEOUL)
                val end = OffsetDateTime.parse(range.end).atZoneSameInstant(TimeFmt.SEOUL)
                val dow = start.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.KOREAN)
                val dateLabel = "${dayFmt.format(start)}($dow)"
                val endLabel =
                    if (end.toLocalTime().hour == 0 && end.toLocalTime().minute == 0 &&
                        end.toLocalDate() != start.toLocalDate()
                    ) {
                        "24:00"
                    } else {
                        timeFmt.format(end)
                    }
                DisplayLine(
                    dateLabel = dateLabel,
                    rangeLabel = "${timeFmt.format(start)} ~ $endLabel",
                )
            }.getOrNull()
        }
    }

    fun isSlotInScope(
        slot: UnavailableSlot,
        scopeStartsAt: String?,
        scopeEndsAt: String?,
    ): Boolean = isSlotInScope(slot, parseScope(scopeStartsAt), parseScope(scopeEndsAt))

    fun isSlotInScope(
        slot: UnavailableSlot,
        scopeStart: ZonedDateTime?,
        scopeEnd: ZonedDateTime?,
    ): Boolean {
        if (scopeStart == null && scopeEnd == null) return true
        val start = slotStart(slot)
        val end = slotEnd(slot)
        if (scopeStart != null && start.isBefore(scopeStart)) return false
        if (scopeEnd != null && end.isAfter(scopeEnd)) return false
        return true
    }

    private fun parseScope(iso: String?): ZonedDateTime? =
        iso
            ?.takeIf { it.isNotBlank() }
            ?.let { OffsetDateTime.parse(it).atZoneSameInstant(TimeFmt.SEOUL) }

    private fun slotStart(slot: UnavailableSlot): ZonedDateTime {
        val day = LocalDate.parse(slot.dateIso.take(10))
        return day.atTime(slot.startHour, slot.startMin).atZone(TimeFmt.SEOUL)
    }

    private fun slotEnd(slot: UnavailableSlot): ZonedDateTime {
        val day = LocalDate.parse(slot.dateIso.take(10))
        return if (slot.endHour == 24 && slot.endMin == 0) {
            day.plusDays(1).atStartOfDay(TimeFmt.SEOUL)
        } else {
            day.atTime(slot.endHour, slot.endMin).atZone(TimeFmt.SEOUL)
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
