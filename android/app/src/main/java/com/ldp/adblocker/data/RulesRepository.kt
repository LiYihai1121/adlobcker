package com.ldp.adblocker.data

import android.content.Context
import android.provider.Settings
import androidx.room.withTransaction
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** 规则仓库：负责从后端同步广告域名与弹窗规则到本地 Room 数据库。 */
class RulesRepository(private val context: Context) {

    private val db = AdBlockDatabase.get(context)
    private val api = BackendClient.api
    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    val deviceName: String get() = Settings.Secure.getString(context.contentResolver, "android_id") ?: "unknown"

    /** 从后端拉取全量快照并原子同步本地库。返回是否成功。 */
    suspend fun syncRules(): Boolean = withContext(Dispatchers.IO) {
        try {
            val resp = api.getSnapshot(true)
            if (!resp.isSuccessful) return@withContext false
            val snap = resp.body() ?: return@withContext false

            // 清空 + 全量写入在同一事务中完成，失败时保留旧数据
            db.withTransaction {
                db.adDomainDao().clear()
                db.adDomainDao().upsertAll(snap.domains.map {
                    AdDomainEntity(it.domain, it.platform, it.enabled)
                })
                db.popupRuleDao().clear()
                db.popupRuleDao().upsertAll(snap.popupRules.map {
                    PopupRuleEntity(it.id, it.packageName, it.buttonTextRegex, it.viewIdRegex, it.enabled)
                })
            }
            prefs.edit().putInt(KEY_LOCAL_RULES_VERSION, snap.rulesVersion).apply()
            true
        } catch (e: Exception) {
            false
        }
    }

    /** 本地已同步的规则版本号（0 表示从未成功同步）。 */
    fun localRulesVersion(): Int = prefs.getInt(KEY_LOCAL_RULES_VERSION, 0)

    /** 本地域名 / 弹窗规则数量。 */
    suspend fun localCounts(): Pair<Int, Int> = withContext(Dispatchers.IO) {
        db.adDomainDao().count() to db.popupRuleDao().count()
    }

    /** 获取当前规则版本号。 */
    suspend fun fetchRulesVersion(): RulesVersionDto? = withContext(Dispatchers.IO) {
        try {
            val resp = api.getRulesVersion()
            if (resp.isSuccessful) resp.body() else null
        } catch (e: Exception) {
            null
        }
    }

    /** 上报拦截统计到后端。返回是否成功（失败时调用方不应推进偏移量）。 */
    suspend fun reportStats(interceptedDomains: List<String>, closedPopups: Int): Boolean =
        withContext(Dispatchers.IO) {
            try {
                api.reportIntercept(InterceptStatDto(deviceName, interceptedDomains, closedPopups))
                    .isSuccessful
            } catch (e: Exception) {
                // 静默失败，统计上报不阻塞主流程
                false
            }
        }

    /** 增量上报：把自上次成功上报以来的新数据发给后端，成功后推进偏移并清空域名缓冲。 */
    suspend fun flushPendingStats() {
        val popupsTotal = getPopupsCount()
        val reportedPopups = prefs.getLong(KEY_REPORTED_POPUPS, 0L)
        val deltaPopups = (popupsTotal - reportedPopups).coerceIn(0L, Int.MAX_VALUE.toLong()).toInt()
        val domains = BlockedDomainBuffer.snapshot()
        if (deltaPopups == 0 && domains.isEmpty()) return
        if (reportStats(domains, deltaPopups)) {
            prefs.edit().putLong(KEY_REPORTED_POPUPS, popupsTotal).apply()
            BlockedDomainBuffer.drain()
        }
    }

    /** 自增本地统计计数。 */
    suspend fun incrementDomainsCount(delta: Long = 1) {
        db.statsDao().incrementOrInit(KEY_DOMAINS, delta)
    }

    suspend fun incrementPopupsCount(delta: Long = 1) {
        db.statsDao().incrementOrInit(KEY_POPUPS, delta)
    }

    suspend fun getDomainsCount(): Long = db.statsDao().get(KEY_DOMAINS)?.value ?: 0
    suspend fun getPopupsCount(): Long = db.statsDao().get(KEY_POPUPS)?.value ?: 0

    companion object {
        private const val PREFS_NAME = "adblock_rules"
        const val KEY_LOCAL_RULES_VERSION = "local_rules_version"
        const val KEY_DOMAINS = "intercepted_domains_count"
        const val KEY_POPUPS = "closed_popups"
        /** 已成功上报到后端的弹窗关闭累计数（用于增量上报）。 */
        private const val KEY_REPORTED_POPUPS = "reported_popups"
    }
}
