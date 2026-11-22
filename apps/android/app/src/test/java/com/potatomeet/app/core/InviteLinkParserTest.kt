package com.potatomeet.app.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class InviteLinkParserTest {
    @Test
    fun normalize_acceptsValidCode() {
        assertEquals("ABCD2345", InviteLinkParser.normalize(" abcd2345 "))
    }

    @Test
    fun normalize_rejectsInvalid() {
        assertNull(InviteLinkParser.normalize("SHORT"))
        assertNull(InviteLinkParser.normalize(null))
        assertNull(InviteLinkParser.normalize("ABCD234!"))
        assertNull(InviteLinkParser.normalize("ABCD23401"))
    }

    @Test
    fun fromUrlString_parsesJoinLink() {
        assertEquals(
            "ABCD2345",
            InviteLinkParser.fromUrlString("https://oranganman.site/join?code=abCD2345"),
        )
    }

    @Test
    fun fromUrlString_rejectsWrongHostOrPath() {
        assertNull(InviteLinkParser.fromUrlString("https://example.com/join?code=ABCD2345"))
        assertNull(InviteLinkParser.fromUrlString("https://oranganman.site/other?code=ABCD2345"))
        assertNull(InviteLinkParser.fromUrlString("http://oranganman.site/join?code=ABCD2345"))
    }

    @Test
    fun inviteUrl_buildsCanonical() {
        assertEquals(
            "https://oranganman.site/join?code=ABCD2345",
            InviteLinkParser.inviteUrl("abcd2345"),
        )
    }
}
