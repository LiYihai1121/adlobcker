package com.ldp.adblocker.data

import android.content.Context
import android.provider.Settings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** 规则仓库：负责从后端同步广告域名与弹窗规则到本地 Room 数据库。 */
class RulesRepository(private val context: Context) {

    private val db = AdBlockDatabase.get(context)
    private val api = BackendClient.api

    val deviceName: String get() = Settings.Secure.getString(context.contentResolver, "android_id") ?: "unknown"

    /** 从后端拉取并同步全部规则。返回是否成功。 */
    suspend fun syncRules(): Boolean = withContext(Dispatchers.IO) {
        try {
            val domainsResp = api.getDomains(true)
            if (!domainsResp.isSuccessful) return@withContext false
            val domains = domainsResp.body() ?: return@withContext false

            val rulesResp = api.getPopupRules(true)
            if (!rulesResp.isSuccessful) return@withContext false
            val rules = rulesResp.body() ?: return@withContext false

            // 写入本地（先清空再写入，保证全量一致）
            db.adDomainDao().clear()
            db.adDomainDao().upsertAll(domains.map {
                AdDomainEntity(it.domain, it.platform, it.enabled)
            })

            db.popupRuleDao().clear()
            db.popupRuleDao().upsertAll(rules.map {
                PopupRuleEntity(it.id, it.packageName, it.buttonTextRegex, it.viewIdRegex, it.enabled)
            })
            true
        } catch (e: Exception) {
            false
        }
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

    /** 上报拦截统计到后端。 */
    suspend fun reportStats(interceptedDomains: List<String>, closedPopups: Int) =
        withContext(Dispatchers.IO) {
            try {
                api.reportIntercept(InterceptStatDto(deviceName, interceptedDomains, closedPopups))
            } catch (e: Exception) {
                // 静默失败，统计上报不阻塞主流程
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
        const val KEY_DOMAINS = "intercepted_domains_count"
        const val KEY_POPUPS = "closed_popups"
    }
}
