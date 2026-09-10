package com.ldp.adblocker.accessibility

import android.accessibilityservice.AccessibilityService
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.ldp.adblocker.data.AdBlockDatabase
import com.ldp.adblocker.data.RulesRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

/**
 * 无障碍弹窗关闭服务。
 *
 * 工作原理：监听窗口状态/内容变化事件，遍历当前界面的无障碍节点树，
 * 查找命中规则（文案正则如"跳过/关闭/✕/不再显示" + 包名）的可点击节点，
 * 自动执行点击，从而关闭开屏倒计时、插屏、悬浮窗等 UI 弹窗广告。
 */
class PopupAccessibilityService : AccessibilityService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var matcher: PopupRuleMatcher? = null
    private val repo by lazy { RulesRepository(this) }

    // 最近一次点击的节点签名，避免短时间内重复点击同一按钮
    private var lastClickedSig: String? = null
    private var lastClickedTime = 0L

    override fun onServiceConnected() {
        super.onServiceConnected()
        loadRules()
    }

    private fun loadRules() {
        try {
            val rules = runBlocking {
                AdBlockDatabase.get(this@PopupAccessibilityService).popupRuleDao().allRules()
            }
            matcher = PopupRuleMatcher(rules)
            Log.i(TAG, "已加载 ${rules.size} 条弹窗规则")
        } catch (e: Exception) {
            Log.e(TAG, "加载弹窗规则失败", e)
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val event = event ?: return
        val m = matcher ?: return
        val pkg = event.packageName?.toString() ?: return

        val root = rootInActiveWindow ?: return
        try {
            val candidates = mutableListOf<AccessibilityNodeInfo>()
            collectClickable(root, candidates)
            for (node in candidates) {
                val text = node.text?.toString().orEmpty()
                val viewId = node.viewIdResourceName?.toString().orEmpty()
                if (m.match(pkg, text, viewId) != null) {
                    val sig = "$pkg|$text|$viewId"
                    val now = System.currentTimeMillis()
                    // 同一按钮 1.5 秒内只点一次
                    if (sig == lastClickedSig && now - lastClickedTime < 1500) return
                    lastClickedSig = sig
                    lastClickedTime = now
                    performClick(node)
                    scope.launch { repo.incrementPopupsCount(1) }
                    Log.i(TAG, "已自动关闭弹窗：pkg=$pkg text=\"$text\"")
                    return
                }
            }
        } finally {
            try { root.recycle() } catch (_: Exception) {}
        }
    }

    /** 递归收集所有可点击的节点（含 clickable 自身或其父级可点击）。 */
    private fun collectClickable(
        node: AccessibilityNodeInfo,
        out: MutableList<AccessibilityNodeInfo>,
    ) {
        if (node.isClickable) {
            out.add(node)
        }
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            collectClickable(child, out)
        }
    }

    /** 执行点击：优先自身点击，否则向上回溯到可点击祖先并点击。 */
    private fun performClick(node: AccessibilityNodeInfo) {
        var target: AccessibilityNodeInfo? = node
        while (target != null && !target.isClickable) {
            target = target.parent
        }
        if (target == null) target = node
        target.performAction(AccessibilityNodeInfo.ACTION_CLICK)
    }

    override fun onInterrupt() {
        Log.w(TAG, "无障碍服务被中断")
    }
}

private const val TAG = "PopupAccSvc"
