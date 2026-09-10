package com.ldp.adblocker.vpn

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.HashSet

class AdDomainFilterTest {

    private fun filterOf(vararg domains: String) = AdDomainFilter(HashSet(domains.toList()))

    @Test
    fun exactDomainBlocked() {
        val f = filterOf("pangolin-sdk.com")
        assertTrue(f.isBlocked("pangolin-sdk.com"))
    }

    @Test
    fun subdomainBlockedBySuffix() {
        val f = filterOf("gdt.qq.com")
        // 子域名命中父域名后缀
        assertTrue(f.isBlocked("mi.gdt.qq.com"))
        assertTrue(f.isBlocked("a.b.gdt.qq.com"))
        // 父域名父级不应被误伤（qq.com 不在黑名单）
        assertFalse(f.isBlocked("qq.com"))
    }

    @Test
    fun caseInsensitive() {
        val f = filterOf("baidu.com")
        assertTrue(f.isBlocked("POS.BAIDU.COM"))
    }

    @Test
    fun trailingDotHandled() {
        val f = filterOf("baidu.com")
        assertTrue(f.isBlocked("baidu.com."))
    }

    @Test
    fun emptyOrBlankHostNotBlocked() {
        val f = filterOf("baidu.com")
        assertFalse(f.isBlocked(""))
        assertFalse(f.isBlocked("   "))
    }

    @Test
    fun unrelatedDomainPasses() {
        val f = filterOf("baidu.com")
        assertFalse(f.isBlocked("cdn.example.org"))
    }
}
