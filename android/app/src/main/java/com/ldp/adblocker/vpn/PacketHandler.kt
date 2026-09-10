package com.ldp.adblocker.vpn

import java.io.ByteArrayOutputStream
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
     *
     * 复用原查询的 IP/UDP/DNS 头：交换收发地址与端口、DNS 置为应答（QR=1）、追加一条
     * 指向 0.0.0.0 的 A 记录。返回完整 IP 数据报，可直接写回 tun 网卡，使广告域名
     * 「立即解析失败」而非长时间等待超时，体验优于直接丢弃查询。
     */
    fun buildBlockedDnsResponse(originalQuery: ByteArray, queryLen: Int): ByteArray? {
        val b = originalQuery
        if (queryLen < 20) return null
        if (((b[0].toInt() ushr 4) and 0x0F) != 4) return null
        val ihl = (b[0].toInt() and 0x0F) * 4
        if (queryLen < ihl + 8) return null
        if ((b[9].toInt() and 0xFF) != PROTO_UDP) return null
        val dnsStart = ihl + 8
        if (queryLen < dnsStart + 12) return null
        val qdCount = ((b[dnsStart + 4].toInt() and 0xFF) shl 8) or (b[dnsStart + 5].toInt() and 0xFF)
        val qEnd = findQuestionEnd(b, dnsStart + 12, queryLen) ?: return null

        // ---- DNS 应答 ----
        val dns = ByteArrayOutputStream()
        dns.write(b[dnsStart].toInt() and 0xFF); dns.write(b[dnsStart + 1].toInt() and 0xFF) // id
        dns.write(0x81); dns.write(0x80)                        // flags: QR=1, RD=1, RA=1
        val qd = if (qdCount > 0) qdCount else 1
        dns.write((qd ushr 8) and 0xFF); dns.write(qd and 0xFF) // qdcount
        dns.write(0x00); dns.write(0x01)                        // ancount=1
        dns.write(0x00); dns.write(0x00)                        // nscount
        dns.write(0x00); dns.write(0x00)                        // arcount
        for (i in dnsStart + 12 until qEnd) dns.write(b[i].toInt() and 0xFF) // 问题段照抄
        dns.write(0xC0); dns.write(0x0C)                        // 名字指针指向 DNS 偏移 12
        dns.write(0x00); dns.write(0x01)                        // type A
        dns.write(0x00); dns.write(0x01)                        // class IN
        dns.write(0x00); dns.write(0x00); dns.write(0x00); dns.write(0x3C) // ttl 60
        dns.write(0x00); dns.write(0x04)                        // rdlength=4
        dns.write(0x00); dns.write(0x00); dns.write(0x00); dns.write(0x00) // rdata 0.0.0.0
        val dnsBytes = dns.toByteArray()

        // ---- UDP 头（收发端口互换） ----
        val srcPort = ((b[ihl + 2].toInt() and 0xFF) shl 8) or (b[ihl + 3].toInt() and 0xFF) // 查询目的端口→应答源端口
        val dstPort = ((b[ihl].toInt() and 0xFF) shl 8) or (b[ihl + 1].toInt() and 0xFF)    // 查询源端口→应答目的端口
        val udpLen = 8 + dnsBytes.size
        val udp = ByteArrayOutputStream()
        udp.write((srcPort ushr 8) and 0xFF); udp.write(srcPort and 0xFF)
        udp.write((dstPort ushr 8) and 0xFF); udp.write(dstPort and 0xFF)
        udp.write((udpLen ushr 8) and 0xFF); udp.write(udpLen and 0xFF)
        udp.write(0x00); udp.write(0x00)                        // checksum=0（IPv4 UDP 可选）
        udp.write(dnsBytes)
        val udpBytes = udp.toByteArray()

        // ---- IP 头（交换收发地址、重算总长与校验和） ----
        val totalLen = ihl + udpBytes.size
        val ipBytes = ByteArray(ihl)
        for (i in 0 until ihl) ipBytes[i] = b[i]
        ipBytes[2] = ((totalLen ushr 8) and 0xFF).toByte()
        ipBytes[3] = (totalLen and 0xFF).toByte()
        ipBytes[6] = 0x40.toByte(); ipBytes[7] = 0x00.toByte()  // flags DF, frag 0
        for (i in 0..3) {                                       // 交换 src/dst
            val tmp = ipBytes[12 + i]
            ipBytes[12 + i] = ipBytes[16 + i]
            ipBytes[16 + i] = tmp
        }
        ipBytes[10] = 0x00.toByte(); ipBytes[11] = 0x00.toByte() // 清零校验和
        val ck = ipChecksum(ipBytes, ihl)
        ipBytes[10] = ((ck ushr 8) and 0xFF).toByte()
        ipBytes[11] = (ck and 0xFF).toByte()

        val result = ByteArrayOutputStream()
        result.write(ipBytes)
        result.write(udpBytes)
        return result.toByteArray()
    }

    /** 定位 DNS 问题段在数据报中的结束绝对偏移（含 qtype+qclass）。 */
    private fun findQuestionEnd(packet: ByteArray, start: Int, limit: Int): Int? {
        var pos = start
        while (pos < limit) {
            val len = packet[pos].toInt() and 0xFF
            if (len == 0) { // 根标签
                val end = pos + 1 + 4
                return if (end <= limit) end else null
            }
            if (len and 0xC0 == 0xC0) { // 压缩指针（查询段一般不出现，兜底处理）
                val end = pos + 2 + 4
                return if (end <= limit) end else null
            }
            pos += 1 + len
        }
        return null
    }

    /** 计算 IP 头校验和（16 位反码求和）。 */
    private fun ipChecksum(header: ByteArray, len: Int): Int {
        var sum = 0
        var i = 0
        while (i < len) {
            val hi = header[i].toInt() and 0xFF
            val lo = if (i + 1 < len) header[i + 1].toInt() and 0xFF else 0
            sum += (hi shl 8) or lo
            i += 2
        }
        while ((sum ushr 16) != 0) sum = (sum and 0xFFFF) + (sum ushr 16)
        return (sum.inv()) and 0xFFFF
    }

    /** 仅用于工具方法占位，保持对象可单测。 */
    fun byteBufferOf(data: ByteArray): ByteBuffer = ByteBuffer.wrap(data)
}
