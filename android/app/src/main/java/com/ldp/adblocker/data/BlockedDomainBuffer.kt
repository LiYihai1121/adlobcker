package com.ldp.adblocker.data

import java.util.concurrent.ConcurrentLinkedQueue

/**
 * 进程内被拦截域名缓冲（供统计上报用）。
 *
 * VPN 服务与 UI 运行在同一进程，因此用单例共享：
 * - [VpnAdBlockService] 拦截命中时 [record] 域名；
 * - 上报流程先 [snapshot] 取一份去重列表发送，成功后再 [drain] 清空，
 *   失败则不清空、下次连同新数据重发，避免丢统计。
 * 进程重启后缓冲清零，仅影响域名明细（累计计数存于 Room，不受影响）。
 */
object BlockedDomainBuffer {

    /** 缓冲上限：防止长时间不上报时无限增长。 */
    private const val MAX_ENTRIES = 500

    private val queue = ConcurrentLinkedQueue<String>()

    /** 记录一次域名拦截命中。 */
    fun record(domain: String) {
        if (domain.isBlank()) return
        if (queue.size >= MAX_ENTRIES) queue.poll()
        queue.offer(domain)
    }

    /** 当前缓冲的去重快照（不修改缓冲）。 */
    fun snapshot(): List<String> = queue.toSet().toList()

    /** 清空缓冲（仅在上报成功后调用）。 */
    fun drain() {
        queue.clear()
    }
}
