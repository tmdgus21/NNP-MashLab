package com.potatomeet.app.ui.face

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class UnavailableSlotTest {
    @Test
    fun halfHourSlots_coverFullDayAs48IndependentCells() {
        val slots = halfHourSlotsForDate("2026-11-21")
        assertEquals(48, slots.size)
        assertEquals(0, slots.first().startHour)
        assertEquals(0, slots.first().startMin)
        assertEquals(23, slots[46].startHour)
        assertEquals(0, slots[46].startMin)
        assertEquals(23, slots[47].startHour)
        assertEquals(30, slots[47].startMin)
        assertEquals(24, slots.last().endHour)
        assertEquals(0, slots.last().endMin)
        assertEquals("09:00 ~ 09:30", slots[18].timeLabel())
        assertEquals("09:30 ~ 10:00", slots[19].timeLabel())
        assertTrue(slots[18].matches(UnavailableSlot("2026-11-21", 9, 0, 9, 30)))
        assertTrue(!slots[18].matches(slots[19]))
    }
}
