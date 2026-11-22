package com.potatomeet.app.ui.face

import com.potatomeet.app.data.remote.dto.TimeRangeDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AvailabilityConverterTest {
    @Test
    fun unmarkedSlots_becomeMergedAvailableRanges() {
        val unavailable =
            listOf(
                UnavailableSlot("2026-11-21", 9, 0, 9, 30),
                UnavailableSlot("2026-11-21", 9, 30, 10, 0),
            )
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21"),
                unavailable = unavailable,
                scopeStartsAt = "2026-11-21T00:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertFalse(payload.allUnavailable)
        assertTrue(payload.ranges.isNotEmpty())
        assertTrue(payload.ranges.any { it.first.contains("T00:00") && it.first.contains("+09:00") })
        assertTrue(payload.ranges.any { it.second.contains("T09:00") && it.second.contains("+09:00") })
        assertTrue(payload.ranges.any { it.first.contains("T10:00") && it.first.contains("+09:00") })
        assertTrue(
            payload.ranges.any {
                it.first.contains("T10:00") && it.second.contains("T00:00") && it.second.startsWith("2026-11-22")
            },
        )
    }

    @Test
    fun emptyUnavailable_meansFullScopeAvailable() {
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21"),
                unavailable = emptyList(),
                scopeStartsAt = "2026-11-21T14:30:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertFalse(payload.allUnavailable)
        assertEquals(1, payload.ranges.size)
        assertTrue(payload.ranges.single().first.contains("T14:30"))
        assertTrue(payload.ranges.single().second.startsWith("2026-11-22"))
        assertFalse(payload.ranges.any { it.first.contains("T00:00") })
    }

    @Test
    fun futureDate_keepsFullDayWhenInScope() {
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-25"),
                unavailable = emptyList(),
                scopeStartsAt = "2026-11-21T14:30:00+09:00",
                scopeEndsAt = "2026-11-26T00:00:00+09:00",
            )
        assertFalse(payload.allUnavailable)
        assertTrue(payload.ranges.any { it.first.startsWith("2026-11-25") && it.first.contains("T00:00") })
        assertTrue(payload.ranges.any { it.second.startsWith("2026-11-26") && it.second.contains("T00:00") })
    }

    @Test
    fun multiDate_clipsOnlyTodayAndKeepsFuture() {
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21", "2026-11-23"),
                unavailable =
                    listOf(
                        UnavailableSlot("2026-11-23", 10, 0, 10, 30),
                    ),
                scopeStartsAt = "2026-11-21T18:00:00+09:00",
                scopeEndsAt = "2026-11-24T00:00:00+09:00",
            )
        assertFalse(payload.allUnavailable)
        assertTrue(payload.ranges.any { it.first.contains("2026-11-21T18:00") })
        assertTrue(payload.ranges.any { it.first.startsWith("2026-11-23") && it.first.contains("T00:00") })
        assertTrue(payload.ranges.any { it.second.contains("T10:00") })
        assertTrue(payload.ranges.any { it.first.contains("T10:30") })
    }

    @Test
    fun midnightBoundary_endUsesNextDay() {
        val unavailable =
            halfHourSlotsForDate("2026-11-22").filterNot { it.startHour == 23 && it.startMin == 30 }
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-22"),
                unavailable = unavailable,
                scopeStartsAt = "2026-11-22T00:00:00+09:00",
                scopeEndsAt = "2026-11-23T00:00:00+09:00",
            )
        assertEquals(1, payload.ranges.size)
        assertTrue(payload.ranges.single().first.contains("T23:30"))
        assertTrue(payload.ranges.single().second.startsWith("2026-11-23"))
        assertTrue(payload.ranges.single().second.contains("T00:00"))
    }

    @Test
    fun allUnavailable_onlyMarksInScopeSlots() {
        val all = halfHourSlotsForDate("2026-11-21")
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21"),
                unavailable = all,
                scopeStartsAt = "2026-11-21T12:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertTrue(payload.allUnavailable)
        assertTrue(payload.ranges.isEmpty())
    }

    @Test
    fun restore_allUnavailable_onlyInScope() {
        val slots =
            AvailabilityConverter.toUnavailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable = emptyList(),
                mySubmitted = true,
                scopeStartsAt = "2026-11-21T20:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertEquals(8, slots.size)
        assertTrue(slots.all { it.startHour >= 20 })
    }

    @Test
    fun restore_notSubmitted_isEmpty() {
        val slots =
            AvailabilityConverter.toUnavailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable = emptyList(),
                mySubmitted = false,
                scopeStartsAt = "2026-11-21T14:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertTrue(slots.isEmpty())
    }

    @Test
    fun restore_partialAvailable_marksComplementInScope() {
        val slots =
            AvailabilityConverter.toUnavailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable =
                    listOf(
                        TimeRangeDto(
                            start = "2026-11-21T14:00:00+09:00",
                            end = "2026-11-21T15:00:00+09:00",
                        ),
                        TimeRangeDto(
                            start = "2026-11-21T16:00:00+09:00",
                            end = "2026-11-22T00:00:00+09:00",
                        ),
                    ),
                mySubmitted = true,
                scopeStartsAt = "2026-11-21T14:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertEquals(2, slots.size)
        assertTrue(slots.any { it.startHour == 15 && it.startMin == 0 })
        assertTrue(slots.any { it.startHour == 15 && it.startMin == 30 })
    }

    @Test
    fun display_mergesUnavailableRanges() {
        val lines =
            AvailabilityConverter.formatUnavailableDisplay(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable =
                    listOf(
                        TimeRangeDto(
                            start = "2026-11-21T00:00:00+09:00",
                            end = "2026-11-21T14:00:00+09:00",
                        ),
                        TimeRangeDto(
                            start = "2026-11-21T16:00:00+09:00",
                            end = "2026-11-22T00:00:00+09:00",
                        ),
                    ),
                mySubmitted = true,
                scopeStartsAt = "2026-11-21T00:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertEquals(1, lines.size)
        assertTrue(lines.single().rangeLabel.contains("14:00"))
        assertTrue(lines.single().rangeLabel.contains("16:00"))
    }

    @Test
    fun pastSlot_isNotSelectable() {
        val past = UnavailableSlot("2026-11-21", 10, 0, 10, 30)
        val future = UnavailableSlot("2026-11-21", 15, 0, 15, 30)
        assertFalse(
            AvailabilityConverter.isSlotInScope(
                past,
                "2026-11-21T14:30:00+09:00",
                "2026-11-22T00:00:00+09:00",
            ),
        )
        assertTrue(
            AvailabilityConverter.isSlotInScope(
                future,
                "2026-11-21T14:30:00+09:00",
                "2026-11-22T00:00:00+09:00",
            ),
        )
    }
}
