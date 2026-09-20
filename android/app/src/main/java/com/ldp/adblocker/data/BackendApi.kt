package com.ldp.adblocker.data

import com.ldp.adblocker.BuildConfig
import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

/** 后端返回的广告域名。 */
@JsonClass(generateAdapter = false)
data class DomainDto(
    val domain: String,
    val platform: String?,
    val enabled: Boolean,
)

/** 后端返回的弹窗规则。 */
@JsonClass(generateAdapter = false)
data class PopupRuleDto(
    val id: Int,
    @Json(name = "package_name") val packageName: String,
    @Json(name = "button_text_regex") val buttonTextRegex: String,
    @Json(name = "view_id_regex") val viewIdRegex: String?,
    val enabled: Boolean,
)

/** 规则全量快照（/api/v1/rules/snapshot）。 */
@JsonClass(generateAdapter = false)
data class RulesSnapshotDto(
    @Json(name = "rules_version") val rulesVersion: Int,
    val domains: List<DomainDto>,
    @Json(name = "popup_rules") val popupRules: List<PopupRuleDto>,
)

/** 规则版本信息。 */
@JsonClass(generateAdapter = false)
data class RulesVersionDto(
    @Json(name = "rules_version") val rulesVersion: Int,
    @Json(name = "domains_count") val domainsCount: Int,
    @Json(name = "popup_rules_count") val popupRulesCount: Int,
)

/** 拦截统计上报体。 */
@JsonClass(generateAdapter = false)
data class InterceptStatDto(
    @Json(name = "device_id") val deviceId: String,
    @Json(name = "intercepted_domains") val interceptedDomains: List<String> = emptyList(),
    @Json(name = "closed_popups") val closedPopups: Int = 0,
)

/** Retrofit 接口定义。 */
interface BackendApi {
    @GET("api/v1/domains")
    suspend fun getDomains(@Query("enabled_only") enabledOnly: Boolean = true): Response<List<DomainDto>>

    @GET("api/v1/popup-rules")
    suspend fun getPopupRules(@Query("enabled_only") enabledOnly: Boolean = true): Response<List<PopupRuleDto>>

    @GET("api/v1/rules/snapshot")
    suspend fun getSnapshot(@Query("enabled_only") enabledOnly: Boolean = true): Response<RulesSnapshotDto>

    @GET("api/v1/rules/version")
    suspend fun getRulesVersion(): Response<RulesVersionDto>

    @POST("api/v1/stats/intercept")
    suspend fun reportIntercept(@Body stat: InterceptStatDto): Response<Unit>
}

object BackendClient {
    // 构建时注入：debug 默认为模拟器宿主机地址，release 必须在构建时传入 https 地址
    private val baseUrl: String = BuildConfig.BACKEND_BASE_URL.ifBlank {
        throw IllegalStateException(
            "未配置后端地址：debug 构建使用模拟器地址；release 构建请以 " +
                "-PbackendBaseUrl=https://your.domain/ 指定 https 地址"
        )
    }

    private val moshi: Moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    val api: BackendApi by lazy {
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create(BackendApi::class.java)
    }
}
