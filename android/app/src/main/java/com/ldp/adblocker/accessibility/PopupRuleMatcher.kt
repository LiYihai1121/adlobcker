package com.ldp.adblocker.accessibility

import android.util.Log
import com.ldp.adblocker.data.PopupRuleEntity
import java.util.regex.Pattern

/**
 * 弹窗规则匹配器：判断一个无障碍节点（按钮文案/viewId）是否匹配某条规则。
 *
 * 规则匹配逻辑：
 * - packageName 为 "*" 表示通配任意应用；否则必须精确匹配（或后缀匹配，便于匹配子进程）。
 * - buttonTextRegex 对节点文本做正则匹配（大小写不敏感）。
 * - viewIdRegex（可选）对节点 viewId 做正则匹配，命中即增强可信度。
 */
class PopupRuleMatcher(private val rules: List<PopupRuleEntity>) {

    private data class Compiled(
        val rule: PopupRuleEntity,
        val textPattern: Pattern,
        val idPattern: Pattern?,
    )

    private val compiled: List<Compiled> = rules.map { r ->
        Compiled(
            rule = r,
            textPattern = Pattern.compile(r.buttonTextRegex, Pattern.CASE_INSENSITIVE),
            idPattern = r.viewIdRegex?.takeIf { it.isNotBlank() }?.let {
                Pattern.compile(it, Pattern.CASE_INSENSITIVE)
            },
        )
    }

    /**
     * 判断给定节点的文案/viewId/包名是否命中任意规则。
     * 返回命中的规则，否则 null。
     */
    fun match(packageName: String, text: String, viewId: String): PopupRuleEntity? {
        for (c in compiled) {
            // 包名匹配
            if (c.rule.packageName != "*" && c.rule.packageName != packageName) continue
            // 文案匹配
            if (text.isBlank() && c.idPattern == null) continue
            val textHit = text.isNotBlank() && c.textPattern.matcher(text).find()
            val idHit = c.idPattern != null && viewId.isNotBlank() && c.idPattern.matcher(viewId).find()
            if (textHit || idHit) {
                Log.d(TAG, "命中规则 #${c.rule.id}（pkg=$packageName text=\"$text\" id=\"$viewId\"）")
                return c.rule
            }
        }
        return null
    }

    companion object {
        private const val TAG = "PopupMatcher"
    }
}
