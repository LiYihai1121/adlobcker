package com.ldp.adblocker.accessibility

import com.ldp.adblocker.data.PopupRuleEntity
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class PopupRuleMatcherTest {

    private val rules = listOf(
        PopupRuleEntity(1, "*", "跳过|跳过广告|跳过 ?\\d+|跳过 ?\\d+s", "skip", true),
        PopupRuleEntity(2, "*", "关闭|✕|×|关闭广告|不再显示", "close|dismiss|cancel", true),
    )
    private val matcher = PopupRuleMatcher(rules)

    @Test
    fun matchesSkipByButtonText() {
        // 「跳过」文案命中规则 #1
        assertNotNull(matcher.match("com.any.app", "跳过", ""))
    }

    @Test
    fun matchesSkipSecondsVariant() {
        // 「跳过 5s」应被正则 跳过 ?\d+s 命中
        assertNotNull(matcher.match("com.any.app", "跳过 5s", ""))
    }

    @Test
    fun matchesCloseByViewIdOnly() {
        // 文案为空但 viewId 含 close，应命中规则 #2
        assertNotNull(matcher.match("com.any.app", "", "com.x:id/btn_close"))
    }

    @Test
    fun noMatchForIrrelevantText() {
        assertNull(matcher.match("com.any.app", "立即购买", ""))
    }

    @Test
    fun noMatchWhenNoTextAndNoIdPattern() {
        // 文案空、且该规则无 viewIdRegex —— 不命中
        assertNull(matcher.match("com.any.app", "", ""))
    }
}
