package com.ldp.adblocker.data

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Moshi DTO 与后端快照接口的序列化/反序列化测试（反射适配器路径）。 */
class BackendApiTest {

    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    @Test
    fun snapshotDtoParsesFromJson() {
        val json = """
            {"rules_version":3,
             "domains":[{"domain":"pangolin-sdk.com","platform":"穿山甲","enabled":true}],
             "popup_rules":[{"id":1,"package_name":"*","button_text_regex":"跳过",
                             "view_id_regex":"skip","enabled":true}]}
        """.trimIndent()
        val snap = moshi.adapter(RulesSnapshotDto::class.java).fromJson(json)!!
        assertEquals(3, snap.rulesVersion)
        assertEquals("pangolin-sdk.com", snap.domains[0].domain)
        assertEquals("穿山甲", snap.domains[0].platform)
        assertTrue(snap.domains[0].enabled)
        assertEquals(1, snap.popupRules[0].id)
        assertEquals("*", snap.popupRules[0].packageName)
        assertEquals("跳过", snap.popupRules[0].buttonTextRegex)
        assertEquals("skip", snap.popupRules[0].viewIdRegex)
    }

    @Test
    fun popupRuleSerializesSnakeCaseFields() {
        val dto = PopupRuleDto(7, "com.x.app", "关闭|✕", "close", false)
        val json = moshi.adapter(PopupRuleDto::class.java).toJson(dto)
        assertTrue(json.contains("\"package_name\":\"com.x.app\""))
        assertTrue(json.contains("\"button_text_regex\":\"关闭|✕\""))
        assertTrue(json.contains("\"view_id_regex\":\"close\""))
        assertTrue(json.contains("\"enabled\":false"))
    }

    @Test
    fun popupRuleNullableViewId() {
        val json = """{"id":2,"package_name":"*","button_text_regex":"关闭","view_id_regex":null,"enabled":true}"""
        val rule = moshi.adapter(PopupRuleDto::class.java).fromJson(json)!!
        assertEquals(null, rule.viewIdRegex)
    }

    @Test
    fun snapshotRoundTrip() {
        val snap = RulesSnapshotDto(
            rulesVersion = 9,
            domains = listOf(DomainDto("ad.example.com", "测试", true)),
            popupRules = listOf(PopupRuleDto(5, "com.a.b", "领取", null, true)),
        )
        val json = moshi.adapter(RulesSnapshotDto::class.java).toJson(snap)
        val back = moshi.adapter(RulesSnapshotDto::class.java).fromJson(json)!!
        assertEquals(snap, back)
    }
}
