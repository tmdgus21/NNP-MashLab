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
 * UI unavailable half-hour slots ↔ API `available` ranges (+09:00).
 * Default = available; marked slots = unavailable. Payload is the complement
 * of marked in-scope slots. Empty mark → full remaining scope available.
 * Only slots fully inside [max(scopeStartsAt, nowCeil), scopeEndsAt) may be
 * toggled/submitted — past selectedDates never block future ranges.
 */
object AvailabilityConverter {
    data class SubmitPayload(
        val ranges: List<Pair<String, String>>,
        val allUnavailable: Boolean,
    )

    data class DisplayLine(
        val dateLabel: String,
        val rangeLabel: String,
    )

    fun toAvailablePayload(
        selectedIsoDates: List<String>,
        unavailable: List<UnavailableSlot>,
        scopeStartsAt: String? = null,
        scopeEndsAt: String? = null,
        now: ZonedDateTime = ZonedDateTime.now(TimeFmt.SEOUL),
    ): SubmitPayload {
        val dates = selectedIsoDates.map { it.take(10) }.distinct().sorted()
        if (dates.isEmpty()) {
            return SubmitPayload(emptyList(), allUnavailable = true)
        }
        val scopeEnd = parseScope(scopeEndsAt)
        val windowStart = effectiveWindowStart(parseScope(scopeStartsAt), now)
        val unavailableKeys =
            unavailable
                .filter { it.dateIso.take(10) in dates }
                .filter { isSlotInScope(it, windowStart, scopeEnd) }
                .map { slotKey(it.dateIso, it.startHour, it.startMin) }
                .toSet()

        val availableSlots = mutableListOf<Pair<LocalDate, Int>>()
        for (iso in dates) {
            val day = LocalDate.parse(iso)
            for (index in 0 until 48) {
                val startMin = index * 30
                val endMinTotal = startMin + 30
                val slot =
                    UnavailableSlot(
                        dateIso = iso,
                        startHour = startMin / 60,
                        startMin = startMin % 60,
                        endHour = endMinTotal / 60,
                        endMin = endMinTotal % 60,
                    )
                // Past selectedDates fall outside windowStart and are skipped.
                if (!isSlotInScope(slot, windowStart, scopeEnd)) continue
                val key = slotKey(iso, slot.startHour, slot.startMin)
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

    /** Restore unavailable UI from `myAvailable` complement (scope-clipped). */
    fun toUnavailableSlots(
        selectedIsoDates: List<String>,
        myAvailable: List<TimeRangeDto>,
        mySubmitted: Boolean,
        scopeStartsAt: String? = null,
        scopeEndsAt: String? = null,
        now: ZonedDateTime = ZonedDateTime.now(TimeFmt.SEOUL),
    ): List<UnavailableSlot> {
        if (!mySubmitted) return emptyList()
        val dates = selectedIsoDates.map { it.take(10) }.distinct()
        val windowStart = effectiveWindowStart(parseScope(scopeStartsAt), now)
        val scopeEnd = parseScope(scopeEndsAt)
        val inScopeSlots =
            dates.flatMap { iso ->
                halfHourSlotsForDate(iso).filter { isSlotInScope(it, windowStart, scopeEnd) }
            }
        if (myAvailable.isEmpty()) {
            return inScopeSlots
        }
        val availableKeys = mutableSetOf<String>()
        for (range in myAvailable) {
            availableKeys.addAll(expandRangeToSlotKeys(range.start, range.end))
        }
        return inScopeSlots.filter { slot ->
            slotKey(slot.dateIso, slot.startHour, slot.startMin) !in availableKeys
        }
    }

    /** Display merged unavailable ranges for RoomDetail. */
    fun formatUnavailableDisplay(
        selectedIsoDates: List<String>,
        myAvailable: List<TimeRangeDto>,
        mySubmitted: Boolean,
        scopeStartsAt: String? = null,
        scopeEndsAt: String? = null,
        now: ZonedDateTime = ZonedDateTime.now(TimeFmt.SEOUL),
    ): List<DisplayLine> {
        val slots =
            toUnavailableSlots(
                selectedIsoDates = selectedIsoDates,
                myAvailable = myAvailable,
                mySubmitted = mySubmitted,
                scopeStartsAt = scopeStartsAt,
                scopeEndsAt = scopeEndsAt,
                now = now,
            )
        if (slots.isEmpty()) return emptyList()

        val byDay = slots.groupBy { it.dateIso.take(10) }.toSortedMap()
        val dayFmt = DateTimeFormatter.ofPattern("M.d")
        val lines = mutableListOf<DisplayLine>()
        for ((iso, daySlots) in byDay) {
            val day = LocalDate.parse(iso)
            val dow = day.dayOfWeek.getDisplayName(TextStyle.SHORT, Locale.KOREAN)
            val dateLabel = "${dayFmt.format(day)}($dow)"
            val indices =
                daySlots
                    .map { it.startHour * 2 + it.startMin / 30 }
                    .distinct()
                    .sorted()
            var runStart = -1
            var runEnd = -1

            fun flush() {
                if (runStart < 0) return
                lines.add(
                    DisplayLine(
                        dateLabel = dateLabel,
                        rangeLabel = "${indexLabel(runStart)} ~ ${indexLabel(runEnd)}",
                    ),
                )
                runStart = -1
                runEnd = -1
            }
            for (index in indices) {
                if (runStart >= 0 && index == runEnd) {
                    runEnd = index + 1
                } else {
                    flush()
                    runStart = index
                    runEnd = index + 1
                }
            }
            flush()
        }
        return lines
    }

    fun isSlotInScope(
        slot: UnavailableSlot,
        scopeStartsAt: String?,
        scopeEndsAt: String?,
        now: ZonedDateTime = ZonedDateTime.now(TimeFmt.SEOUL),
    ): Boolean =
        isSlotInScope(
            slot,
            effectiveWindowStart(parseScope(scopeStartsAt), now),
            parseScope(scopeEndsAt),
        )

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

    /** max(scopeStart, ceil-to-30min now) so past selectedDates cannot enter the payload. */
    fun effectiveWindowStart(
        scopeStart: ZonedDateTime?,
        now: ZonedDateTime = ZonedDateTime.now(TimeFmt.SEOUL),
    ): ZonedDateTime? {
        val nowCeil = ceilToSlot(now)
        return when {
            scopeStart == null -> nowCeil
            scopeStart.isAfter(nowCeil) -> scopeStart
            else -> nowCeil
        }
    }

    private fun ceilToSlot(value: ZonedDateTime): ZonedDateTime {
        val truncated = value.withSecond(0).withNano(0)
        if (truncated.minute % 30 == 0 && !value.isAfter(truncated)) {
            return truncated
        }
        val rem = truncated.minute % 30
        val add = if (rem == 0) 30 else 30 - rem
        return truncated.plusMinutes(add.toLong())
    }

    private fun indexLabel(index: Int): String {
        val total = index * 30
        return if (total >= 24 * 60) {
            "24:00"
        } else {
            "%02d:%02d".format(total / 60, total % 60)
        }
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
