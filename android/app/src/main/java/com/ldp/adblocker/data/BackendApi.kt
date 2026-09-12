package com.ldp.adblocker.data

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

/** 后端返回的广告域名。 */
@JsonClass(generateAdapter = true)
data class DomainDto(
    val domain: String,
    val platform: String?,
    val enabled: Boolean,
)

/** 后端返回的弹窗规则。 */
@JsonClass(generateAdapter = true)
data class PopupRuleDto(
    val id: Int,
    @Json(name = "package_name") val packageName: String,
    @Json(name = "button_text_regex") val buttonTextRegex: String,
    @Json(name = "view_id_regex") val viewIdRegex: String?,
    val enabled: Boolean,
)

/** 规则版本信息。 */
@JsonClass(generateAdapter = true)
data class RulesVersionDto(
    @Json(name = "rules_version") val rulesVersion: Int,
    @Json(name = "domains_count") val domainsCount: Int,
    @Json(name = "popup_rules_count") val popupRulesCount: Int,
)

/** 拦截统计上报体。 */
@JsonClass(generateAdapter = true)
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

    @GET("api/v1/rules/version")
    suspend fun getRulesVersion(): Response<RulesVersionDto>

    @POST("api/v1/stats/intercept")
    suspend fun reportIntercept(@Body stat: InterceptStatDto): Response<Unit>
}

object BackendClient {
    // 默认后端地址，实际部署时可改为局域网/公网 IP。模拟器请用 10.0.2.2 指向宿主机。
    private const val BASE_URL = "http://10.0.2.2:8000/"

    val api: BackendApi by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(MoshiConverterFactory.create())
            .build()
            .create(BackendApi::class.java)
    }
}
