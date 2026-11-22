package com.potatomeet.app.core

import android.content.Intent
import android.net.Uri
import java.net.URI

object InviteLinkParser {
    private val CODE_PATTERN = Regex("^[A-Z2-9]{8}$")
    private const val HOST = "oranganman.site"
    private const val PATH_PREFIX = "/join"

    fun inviteUrl(code: String): String = "https://$HOST$PATH_PREFIX?code=${normalize(code).orEmpty()}"

    fun normalize(raw: String?): String? {
        val code = raw?.trim()?.uppercase().orEmpty()
        return code.takeIf { CODE_PATTERN.matches(it) }
    }

    fun fromIntent(intent: Intent?): String? = fromUri(intent?.data)

    fun fromUri(uri: Uri?): String? {
        if (uri == null) return null
        return fromHttpsJoin(
            scheme = uri.scheme,
            host = uri.host,
            path = uri.path,
            codeParam = uri.getQueryParameter("code"),
        )
    }

    /** JVM-safe parse for unit tests (no Android Uri). */
    fun fromUrlString(url: String): String? {
        val uri = runCatching { URI(url) }.getOrNull() ?: return null
        val query = uri.rawQuery.orEmpty()
        val codeParam =
            query
                .split('&')
                .mapNotNull { part ->
                    val idx = part.indexOf('=')
                    if (idx <= 0) return@mapNotNull null
                    val key = part.substring(0, idx)
                    val value = part.substring(idx + 1)
                    if (key == "code") value else null
                }.firstOrNull()
        return fromHttpsJoin(
            scheme = uri.scheme,
            host = uri.host,
            path = uri.path,
            codeParam = codeParam,
        )
    }

    private fun fromHttpsJoin(
        scheme: String?,
        host: String?,
        path: String?,
        codeParam: String?,
    ): String? {
        if (!scheme.equals("https", ignoreCase = true)) return null
        if (!host.equals(HOST, ignoreCase = true)) return null
        if (path?.startsWith(PATH_PREFIX) != true) return null
        return normalize(codeParam)
    }
}
