package com.ldp.adblocker.vpn

import android.content.Context
import android.util.Log
import com.ldp.adblocker.data.AdBlockDatabase
import kotlinx.coroutines.runBlocking

/**
 * 广告域名过滤器：维护一份内存中的黑名单集合（域名后缀匹配），
 * 供 [VpnAdBlockService] 的 DNS 解析环节使用。
 *
 * 域名以小写、去点比较；匹配逻辑为「被查询域名以黑名单某条目结尾」即命中。
 */
class AdDomainFilter internal constructor(
    private val blockedSuffixes: HashSet<String>,
) {
    /** 是否命中黑名单。host 可带点，大小写不敏感。 */
    fun isBlocked(host: String): Boolean {
        if (host.isBlank()) return false
        val h = host.trimEnd('.').lowercase()
        if (blockedSuffixes.contains(h)) return true
        // 后缀匹配：a.b.c.com 命中 c.com / b.c.com
        var idx = h.indexOf('.')
        while (idx >= 0 && idx < h.length - 1) {
            val suffix = h.substring(idx + 1)
            if (blockedSuffixes.contains(suffix)) return true
            idx = h.indexOf('.', idx + 1)
        }
        return false
    }

    val size: Int get() = blockedSuffixes.size

    companion object {
        private const val TAG = "AdDomainFilter"

        /** 从 Room 数据库加载黑名单到内存。 */
        suspend fun load(context: Context): AdDomainFilter {
            val dao = AdBlockDatabase.get(context).adDomainDao()
            val domains = dao.allDomains()
            val set = HashSet<String>(domains.size)
            for (d in domains) {
                val cleaned = d.trim().trimEnd('.').lowercase()
                if (cleaned.isNotEmpty()) set.add(cleaned)
            }
            Log.i(TAG, "已加载 ${set.size} 条广告域名黑名单")
            return AdDomainFilter(set)
        }

        /** 同步阻塞加载（仅用于 VPN 服务内不可挂起协程的初始化路径）。 */
        fun loadBlocking(context: Context): AdDomainFilter = runBlocking { load(context) }
    }
}
