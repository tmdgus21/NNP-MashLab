package com.potatomeet.app.ui.face

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZonedDateTime

class UnavailableBulkToggleTest {
    private val date = "2026-11-26"
    private val now = ZonedDateTime.parse("2026-11-26T00:00:00+09:00")
    private val scopeStart = "2026-11-26T00:00:00+09:00"
    private val scopeEnd = "2026-11-27T00:00:00+09:00"

    @Test
    fun pageSlots_coversSixteenHalfHours() {
        val page = UnavailableBulkToggle.pageSlots(date, 8, 16)
        assertEquals(16, page.size)
        assertEquals(8, page.first().startHour)
        assertEquals(0, page.first().startMin)
        assertEquals(15, page.last().startHour)
        assertEquals(30, page.last().startMin)
    }

    @Test
    fun daySlots_coversFortyEight() {
        assertEquals(48, UnavailableBulkToggle.daySlots(date).size)
    }

    @Test
    fun toggle_allAvailable_thenAllUnavailable_thenAllAvailable() {
        val targets =
            UnavailableBulkToggle.selectable(
                UnavailableBulkToggle.pageSlots(date, 0, 8),
                scopeStart,
                scopeEnd,
                now,
            )
        assertEquals(16, targets.size)

        var current = emptyList<UnavailableSlot>()
        assertTrue(UnavailableBulkToggle.shouldMarkUnavailable(targets, current))
        assertEquals("전체 불가로 변경", UnavailableBulkToggle.actionLabel(true))

        current = UnavailableBulkToggle.apply(current, targets, markUnavailable = true)
        assertEquals(16, current.size)
        assertFalse(UnavailableBulkToggle.shouldMarkUnavailable(targets, current))
        assertEquals("전체 가능으로 변경", UnavailableBulkToggle.actionLabel(false))

        current = UnavailableBulkToggle.apply(current, targets, markUnavailable = false)
        assertTrue(current.none { targets.any { t -> t.matches(it) } })
        assertTrue(UnavailableBulkToggle.shouldMarkUnavailable(targets, current))
    }

    @Test
    fun partialAvailable_forcesMarkAllUnavailable() {
        val targets =
            UnavailableBulkToggle.selectable(
                UnavailableBulkToggle.pageSlots(date, 8, 16),
                scopeStart,
                scopeEnd,
                now,
            )
        val current = listOf(targets.first())
        assertTrue(UnavailableBulkToggle.shouldMarkUnavailable(targets, current))
        val next = UnavailableBulkToggle.apply(current, targets, markUnavailable = true)
        assertEquals(16, next.size)
        assertTrue(targets.all { t -> next.any { it.matches(t) } })
    }

    @Test
    fun pageAndDay_areIndependent() {
        val page =
            UnavailableBulkToggle.selectable(
                UnavailableBulkToggle.pageSlots(date, 0, 8),
                scopeStart,
                scopeEnd,
                now,
            )
        val day =
            UnavailableBulkToggle.selectable(
                UnavailableBulkToggle.daySlots(date),
                scopeStart,
                scopeEnd,
                now,
            )
        var current = UnavailableBulkToggle.apply(emptyList(), page, markUnavailable = true)
        assertEquals(16, current.size)

        current = UnavailableBulkToggle.apply(current, day, markUnavailable = true)
        assertEquals(48, current.size)

        current = UnavailableBulkToggle.apply(current, page, markUnavailable = false)
        assertEquals(32, current.size)
        assertTrue(page.none { p -> current.any { it.matches(p) } })
        assertTrue(
            day.filter { it.startHour >= 8 }.all { d -> current.any { it.matches(d) } },
        )
    }

    @Test
    fun pastAndOutOfScope_excluded() {
        val lateNow = ZonedDateTime.parse("2026-11-26T10:15:00+09:00")
        val page =
            UnavailableBulkToggle.selectable(
                UnavailableBulkToggle.pageSlots(date, 8, 16),
                scopeStart,
                scopeEnd,
                lateNow,
            )
        // 08:00–10:00 past relative to ceil(10:15)=10:30 → only 10:30–16:00 remain
        assertTrue(page.all { it.startHour > 10 || (it.startHour == 10 && it.startMin >= 30) })
        assertEquals(11, page.size)

        val narrowEnd = "2026-11-26T12:00:00+09:00"
        val clipped =
            UnavailableBulkToggle.selectable(
                UnavailableBulkToggle.daySlots(date),
                scopeStart,
                narrowEnd,
                now,
            )
        assertTrue(clipped.all { AvailabilityConverter.isSlotInScope(it, scopeStart, narrowEnd, now) })
        assertEquals(24, clipped.size)
    }

    @Test
    fun apply_skipsAlreadyDesiredSlots_withoutDuplicating() {
        val targets =
            UnavailableBulkToggle.selectable(
                UnavailableBulkToggle.pageSlots(date, 16, 24),
                scopeStart,
                scopeEnd,
                now,
            )
        val current = listOf(targets[0], targets[1])
        val next = UnavailableBulkToggle.apply(current, targets, markUnavailable = true)
        assertEquals(16, next.size)
        assertEquals(16, next.distinctBy { "${it.startHour}:${it.startMin}" }.size)
    }
}
