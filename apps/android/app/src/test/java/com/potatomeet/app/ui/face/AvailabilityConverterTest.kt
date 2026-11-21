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
            )
        assertFalse(payload.allUnavailable)
        assertTrue(payload.ranges.isNotEmpty())
        // Day should split around 09:00-10:00 hole (OffsetDateTime may omit :00 seconds).
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
    fun allUnavailable_whenEverySlotMarked() {
        val all = halfHourSlotsForDate("2026-11-21")
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21"),
                unavailable = all,
            )
        assertTrue(payload.allUnavailable)
        assertTrue(payload.ranges.isEmpty())
    }

    @Test
    fun restore_allUnavailable_marksAllSlots() {
        val slots =
            AvailabilityConverter.toUnavailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable = emptyList(),
                mySubmitted = true,
            )
        assertEquals(48, slots.size)
    }

    @Test
    fun restore_notSubmitted_isEmpty() {
        val slots =
            AvailabilityConverter.toUnavailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable = emptyList(),
                mySubmitted = false,
            )
        assertTrue(slots.isEmpty())
    }

    @Test
    fun restore_partialAvailable_marksComplement() {
        val slots =
            AvailabilityConverter.toUnavailableSlots(
                selectedIsoDates = listOf("2026-11-21"),
                myAvailable =
                    listOf(
                        TimeRangeDto(
                            start = "2026-11-21T00:00:00+09:00",
                            end = "2026-11-21T09:00:00+09:00",
                        ),
                        TimeRangeDto(
                            start = "2026-11-21T10:00:00+09:00",
                            end = "2026-11-22T00:00:00+09:00",
                        ),
                    ),
                mySubmitted = true,
            )
        assertEquals(2, slots.size)
        assertTrue(slots.any { it.startHour == 9 && it.startMin == 0 })
        assertTrue(slots.any { it.startHour == 9 && it.startMin == 30 })
    }

    @Test
    fun endOfDay_usesNextMidnight() {
        val unavailable = halfHourSlotsForDate("2026-11-21").filterNot { it.startHour == 23 && it.startMin == 30 }
        val payload =
            AvailabilityConverter.toAvailablePayload(
                selectedIsoDates = listOf("2026-11-21"),
                unavailable = unavailable,
            )
        assertEquals(1, payload.ranges.size)
        assertTrue(payload.ranges.single().first.contains("T23:30"))
        assertTrue(payload.ranges.single().first.contains("+09:00"))
        assertTrue(payload.ranges.single().second.contains("T00:00"))
        assertTrue(payload.ranges.single().second.startsWith("2026-11-22"))
    }
}
