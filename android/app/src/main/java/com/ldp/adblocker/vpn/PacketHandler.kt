package com.ldp.adblocker.vpn

import java.nio.ByteBuffer

/**
 * 网络包工具：解析 IP 头与 UDP/DNS 负载，用于在 VPN 隧道中识别 DNS 查询域名。
 *
 * 仅处理 IPv4/UDP/DNS，其余流量原样放行。被命中黑名单的 DNS 查询会返回一个
 * 解析为 0.0.0.0 的伪造 DNS 应答，从而使广告域名解析失败、广告无法加载。
 */
object PacketHandler {

    private const val PROTO_UDP = 17

    /** 解析结果。 */
    sealed class Result {
        /** 非 DNS 包，直接放行。 */
        data object PassThrough : Result()
        /** DNS 查询，且域名命中黑名单。 */
        data class Blocked(val domain: String) : Result()
        /** DNS 查询，但域名不在黑名单，放行。 */
        data class Allowed(val domain: String) : Result()
    }

    /**
     * 检查一个 IP 数据报（自 IP 头开始）。
     */
    fun inspect(packet: ByteArray, length: Int, filter: AdDomainFilter): Result {
        if (length < 20) return Result.PassThrough
        val version = (packet[0].toInt() ushr 4) and 0x0F
        if (version != 4) return Result.PassThrough // 仅处理 IPv4
        val ihl = (packet[0].toInt() and 0x0F) * 4
        if (length < ihl + 8) return Result.PassThrough
        val proto = packet[9].toInt() and 0xFF
        if (proto != PROTO_UDP) return Result.PassThrough

        // UDP 源端口 53 表示这是 DNS 应答；目标端口 53 表示 DNS 查询
        val srcPort = ((packet[ihl].toInt() and 0xFF) shl 8) or (packet[ihl + 1].toInt() and 0xFF)
        val dstPort = ((packet[ihl + 2].toInt() and 0xFF) shl 8) or (packet[ihl + 3].toInt() and 0xFF)

        // 只拦截「发往 53 端口的 DNS 查询」
        if (dstPort != 53) return Result.PassThrough

        val dnsOffset = ihl + 8
        if (length < dnsOffset + 12) return Result.PassThrough

        // DNS 头 12 字节：id(2) flags(2) qdcount(2) ...
        val qdCount = ((packet[dnsOffset + 4].toInt() and 0xFF) shl 8) or (packet[dnsOffset + 5].toInt() and 0xFF)
        if (qdCount == 0) return Result.PassThrough

        val domain = parseDomain(packet, dnsOffset + 12, length) ?: return Result.PassThrough
        return if (filter.isBlocked(domain)) Result.Blocked(domain) else Result.Allowed(domain)
    }

    /** 从 DNS 问题段解析域名（RFC 1035 标签格式）。 */
    private fun parseDomain(packet: ByteArray, offset: Int, limit: Int): String? {
        val sb = StringBuilder()
        var pos = offset
        var jumped = false
        var safety = 0
        while (pos < limit && safety < 128) {
            safety++
            val len = packet[pos].toInt() and 0xFF
            if (len == 0) break
            if (len and 0xC0 == 0xC0) {
                // 指针压缩，本场景查询段一般不压缩，简单跳过
                if (!jumped) pos += 2
                break
            }
            if (pos + 1 + len > limit) return null
            for (i in 1..len) {
                sb.append((packet[pos + i].toInt() and 0xFF).toChar())
            }
            sb.append('.')
            pos += 1 + len
        }
        val domain = sb.toString().trimEnd('.')
        return domain.ifBlank { null }
    }

    /**
     * 构造一个伪造的 DNS 应答（A 记录指向 0.0.0.0），用于拦截命中域名的查询。
     * 为简化实现，这里不直接构造完整应答包，而是返回空表示「丢弃该查询」，
     * 由 VPN 服务决定是否注入应答。返回 null 表示丢弃即可。
     */
    fun buildBlockedDnsResponse(originalQuery: ByteArray, queryLen: Int): ByteArray? = null

    /** 仅用于工具方法占位，保持对象可单测。 */
    fun byteBufferOf(data: ByteArray): ByteBuffer = ByteBuffer.wrap(data)
}
