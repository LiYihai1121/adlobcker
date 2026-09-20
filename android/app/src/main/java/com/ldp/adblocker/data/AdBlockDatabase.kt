package com.ldp.adblocker.data

import android.content.Context
import androidx.room.*
import kotlinx.coroutines.flow.Flow

// ====== 实体 ======

/** 广告域名黑名单。 */
@Entity(tableName = "ad_domains")
data class AdDomainEntity(
    @PrimaryKey val domain: String,
    val platform: String?,
    val enabled: Boolean = true,
    val updatedAt: Long = System.currentTimeMillis(),
)

/** 弹窗关闭规则。 */
@Entity(tableName = "popup_rules")
data class PopupRuleEntity(
    @PrimaryKey val id: Int,
    val packageName: String,
    val buttonTextRegex: String,
    val viewIdRegex: String?,
    val enabled: Boolean = true,
    val updatedAt: Long = System.currentTimeMillis(),
)

/** 拦截统计（本地累计）。 */
@Entity(tableName = "stats")
data class StatEntity(
    @PrimaryKey val key: String,   // "intercepted_domains_count" / "closed_popups"
    val value: Long,
)

// ====== DAO ======

@Dao
interface AdDomainDao {
    @Query("SELECT * FROM ad_domains WHERE enabled=1")
    fun observeAll(): Flow<List<AdDomainEntity>>

    @Query("SELECT domain FROM ad_domains WHERE enabled=1")
    suspend fun allDomains(): List<String>

    @Query("SELECT COUNT(*) FROM ad_domains WHERE enabled=1")
    suspend fun count(): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(domains: List<AdDomainEntity>)

    @Query("DELETE FROM ad_domains")
    suspend fun clear()
}

@Dao
interface PopupRuleDao {
    @Query("SELECT * FROM popup_rules WHERE enabled=1")
    fun observeAll(): Flow<List<PopupRuleEntity>>

    @Query("SELECT * FROM popup_rules WHERE enabled=1")
    suspend fun allRules(): List<PopupRuleEntity>

    @Query("SELECT COUNT(*) FROM popup_rules WHERE enabled=1")
    suspend fun count(): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(rules: List<PopupRuleEntity>)

    @Query("DELETE FROM popup_rules")
    suspend fun clear()
}

@Dao
interface StatsDao {
    @Query("SELECT * FROM stats WHERE `key`=:key")
    suspend fun get(key: String): StatEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(stat: StatEntity)

    @Query("UPDATE stats SET value=value+:delta WHERE `key`=:key")
    suspend fun increment(key: String, delta: Long)

    /** 原子自增：若不存在则插入初始值。 */
    suspend fun incrementOrInit(key: String, delta: Long) {
        val existing = get(key)
        if (existing == null) {
            upsert(StatEntity(key, delta))
        } else {
            increment(key, delta)
        }
    }
}

// ====== 数据库 ======

@Database(
    entities = [AdDomainEntity::class, PopupRuleEntity::class, StatEntity::class],
    version = 1, exportSchema = false
)
abstract class AdBlockDatabase : RoomDatabase() {
    abstract fun adDomainDao(): AdDomainDao
    abstract fun popupRuleDao(): PopupRuleDao
    abstract fun statsDao(): StatsDao

    companion object {
        @Volatile private var INSTANCE: AdBlockDatabase? = null

        fun get(context: Context): AdBlockDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AdBlockDatabase::class.java,
                    "adblock.db"
                ).fallbackToDestructiveMigration().build().also { INSTANCE = it }
            }
    }
}
