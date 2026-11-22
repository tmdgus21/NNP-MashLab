package com.potatomeet.app.ui.face

import com.potatomeet.app.data.remote.dto.TimeRangeDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AvailabilityConverterTest {
    @Test
    fun selectedSlots_mergeIntoAvailableRanges() {
        val selected =
            listOf(
                UnavailableSlot("2026-11-21", 14, 0, 14, 30),
                UnavailableSlot("2026-11-21", 14, 30, 15, 0),
                UnavailableSlot("2026-11-21", 16, 0, 16, 30),
            )
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21"),
                selectedAvailable = selected,
                scopeStartsAt = "2026-11-21T00:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertFalse(payload.allUnavailable)
        assertEquals(2, payload.ranges.size)
        assertTrue(payload.ranges[0].first.contains("T14:00"))
        assertTrue(payload.ranges[0].second.contains("T15:00"))
        assertTrue(payload.ranges[1].first.contains("T16:00"))
        assertTrue(payload.ranges[1].second.contains("T16:30"))
    }

    @Test
    fun emptySelection_doesNotImplyFullDay() {
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21"),
                selectedAvailable = emptyList(),
                scopeStartsAt = "2026-11-21T14:30:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertTrue(payload.ranges.isEmpty())
        assertFalse(payload.allUnavailable)
    }

    @Test
    fun pastSlots_areExcludedFromPayload() {
        val selected =
            listOf(
                UnavailableSlot("2026-11-21", 10, 0, 10, 30),
                UnavailableSlot("2026-11-21", 15, 0, 15, 30),
            )
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21"),
                selectedAvailable = selected,
                scopeStartsAt = "2026-11-21T14:30:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertEquals(1, payload.ranges.size)
        assertTrue(payload.ranges.single().first.contains("T15:00"))
        assertFalse(payload.ranges.any { it.first.contains("T10:00") })
    }

    @Test
    fun futureDate_keepsSelectedFullRanges() {
        val selected = halfHourSlotsForDate("2026-11-25").filter { it.startHour in 9..10 }
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-25"),
                selectedAvailable = selected,
                scopeStartsAt = "2026-11-21T14:30:00+09:00",
                scopeEndsAt = "2026-11-26T00:00:00+09:00",
            )
        assertEquals(1, payload.ranges.size)
        assertTrue(payload.ranges.single().first.contains("T09:00"))
        assertTrue(payload.ranges.single().second.contains("T11:00"))
    }

    @Test
    fun multiDate_mergesPerDay() {
        val selected =
            listOf(
                UnavailableSlot("2026-11-21", 18, 0, 18, 30),
                UnavailableSlot("2026-11-23", 10, 0, 10, 30),
                UnavailableSlot("2026-11-23", 10, 30, 11, 0),
            )
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21", "2026-11-23"),
                selectedAvailable = selected,
                scopeStartsAt = "2026-11-21T18:00:00+09:00",
                scopeEndsAt = "2026-11-24T00:00:00+09:00",
            )
        assertEquals(2, payload.ranges.size)
        assertTrue(payload.ranges.any { it.first.contains("2026-11-21T18:00") })
        assertTrue(payload.ranges.any { it.first.contains("2026-11-23T10:00") && it.second.contains("T11:00") })
    }

    @Test
    fun midnightBoundary_endUsesNextDay() {
        val selected = listOf(UnavailableSlot("2026-11-22", 23, 30, 24, 0))
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-22"),
                selectedAvailable = selected,
                scopeStartsAt = "2026-11-22T00:00:00+09:00",
                scopeEndsAt = "2026-11-23T00:00:00+09:00",
            )
        assertEquals(1, payload.ranges.size)
        assertTrue(payload.ranges.single().first.contains("T23:30"))
        assertTrue(payload.ranges.single().second.startsWith("2026-11-23"))
        assertTrue(payload.ranges.single().second.contains("T00:00"))
    }

    @Test
    fun restore_mapsMyAvailableDirectly() {
        val slots =
            AvailabilityConverter.toAvailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable =
                    listOf(
                        TimeRangeDto(
                            start = "2026-11-21T14:00:00+09:00",
                            end = "2026-11-21T15:00:00+09:00",
                        ),
                    ),
                mySubmitted = true,
                scopeStartsAt = "2026-11-21T14:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertEquals(2, slots.size)
        assertTrue(slots.any { it.startHour == 14 && it.startMin == 0 })
        assertTrue(slots.any { it.startHour == 14 && it.startMin == 30 })
    }

    @Test
    fun restore_notSubmitted_isEmpty() {
        val slots =
            AvailabilityConverter.toAvailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable =
                    listOf(
                        TimeRangeDto(
                            start = "2026-11-21T14:00:00+09:00",
                            end = "2026-11-21T15:00:00+09:00",
                        ),
                    ),
                mySubmitted = false,
            )
        assertTrue(slots.isEmpty())
    }

    @Test
    fun restore_submittedEmpty_isEmptySelection() {
        val slots =
            AvailabilityConverter.toAvailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable = emptyList(),
                mySubmitted = true,
                scopeStartsAt = "2026-11-21T14:00:00+09:00",
                scopeEndsAt = "2026-11-22T00:00:00+09:00",
            )
        assertTrue(slots.isEmpty())
    }

    @Test
    fun display_formatsMergedRangesByDate() {
        val lines =
            AvailabilityConverter.formatAvailableDisplay(
                myAvailable =
                    listOf(
                        TimeRangeDto(
                            start = "2026-11-21T14:00:00+09:00",
                            end = "2026-11-21T16:00:00+09:00",
                        ),
                        TimeRangeDto(
                            start = "2026-11-22T23:30:00+09:00",
                            end = "2026-11-23T00:00:00+09:00",
                        ),
                    ),
                mySubmitted = true,
            )
        assertEquals(2, lines.size)
        assertTrue(lines[0].rangeLabel.contains("14:00"))
        assertTrue(lines[0].rangeLabel.contains("16:00"))
        assertTrue(lines[1].rangeLabel.contains("23:30"))
        assertTrue(lines[1].rangeLabel.contains("24:00"))
    }
}
