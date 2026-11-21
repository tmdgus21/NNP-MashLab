package com.potatomeet.app.core

import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

object TimeFmt {
    val SEOUL: ZoneId = ZoneId.of("Asia/Seoul")
    private val display =
        DateTimeFormatter.ofPattern("M월 d일 (E) HH:mm").withZone(SEOUL)
    private val dayLabel = DateTimeFormatter.ofPattern("M월 d일")

    fun parse(iso: String): OffsetDateTime = OffsetDateTime.parse(iso)

    fun rangeLabel(
        startsAt: String?,
        endsAt: String?,
    ): String {
        if (startsAt.isNullOrBlank() || endsAt.isNullOrBlank()) return "일정 미정"
        return try {
            val s = parse(startsAt).atZoneSameInstant(SEOUL)
            val e = parse(endsAt).atZoneSameInstant(SEOUL)
            "${dayLabel.format(s)} ~ ${dayLabel.format(e)}"
        } catch (_: Exception) {
            "$startsAt ~ $endsAt"
        }
    }

    fun slotLabel(
        startsAt: String,
        endsAt: String,
    ): String =
        try {
            val s = parse(startsAt).atZoneSameInstant(SEOUL)
            val e = parse(endsAt).atZoneSameInstant(SEOUL)
            "${display.format(s)} ~ ${e.toLocalTime().format(DateTimeFormatter.ofPattern("HH:mm"))}"
        } catch (_: Exception) {
            "$startsAt ~ $endsAt"
        }

    fun todaySeoul(): LocalDate = LocalDate.now(SEOUL)

    fun isoDate(date: LocalDate): String = date.toString()

    /** Build ISO +09:00 instant for local calendar day + hour/minute. */
    fun seoulInstant(
        year: Int,
        month: Int,
        day: Int,
        hour: Int,
        minute: Int,
    ): String {
        val zdt =
            java.time.ZonedDateTime.of(year, month, day, hour, minute, 0, 0, SEOUL)
        // Always include seconds for stable API payloads.
        return zdt.toOffsetDateTime().format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)
    }
}
