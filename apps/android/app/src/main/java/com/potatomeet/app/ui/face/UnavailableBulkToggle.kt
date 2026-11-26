package com.potatomeet.app.ui.face

import java.time.ZonedDateTime

/** Bulk unavailable/available toggles for the half-hour grid (no separate Boolean flag). */
object UnavailableBulkToggle {
    fun pageSlots(
        dateIso: String,
        startHour: Int,
        endHour: Int,
    ): List<UnavailableSlot> {
        if (dateIso.isBlank() || startHour >= endHour) return emptyList()
        return halfHourSlotsForDate(dateIso).filter { slot ->
            slot.startHour in startHour until endHour
        }
    }

    fun daySlots(dateIso: String): List<UnavailableSlot> =
        if (dateIso.isBlank()) emptyList() else halfHourSlotsForDate(dateIso)

    fun selectable(
        candidates: List<UnavailableSlot>,
        scopeStartsAt: String?,
        scopeEndsAt: String?,
        now: ZonedDateTime = ZonedDateTime.now(com.potatomeet.app.core.TimeFmt.SEOUL),
    ): List<UnavailableSlot> =
        candidates.filter { AvailabilityConverter.isSlotInScope(it, scopeStartsAt, scopeEndsAt, now) }

    /**
     * When every selectable target is already unavailable → next action makes them available.
     * Otherwise (any available) → next action marks all unavailable.
     */
    fun shouldMarkUnavailable(
        selectable: List<UnavailableSlot>,
        unavailable: List<UnavailableSlot>,
    ): Boolean {
        if (selectable.isEmpty()) return true
        val allUnavailable = selectable.all { target -> unavailable.any { it.matches(target) } }
        return !allUnavailable
    }

    fun actionLabel(markUnavailable: Boolean): String =
        if (markUnavailable) "전체 불가로 변경" else "전체 가능으로 변경"

    /** Apply target slots without rewriting unrelated dates/hours. Skips no-op slots. */
    fun apply(
        current: List<UnavailableSlot>,
        selectable: List<UnavailableSlot>,
        markUnavailable: Boolean,
    ): List<UnavailableSlot> {
        if (selectable.isEmpty()) return current
        val targetKeys = selectable.map(::key).toSet()
        val kept = current.filter { key(it) !in targetKeys }
        return if (markUnavailable) {
            kept + selectable
        } else {
            kept
        }
    }

    private fun key(slot: UnavailableSlot): String =
        "${slot.dateIso.take(10)}|${slot.startHour}|${slot.startMin}"
}
