package com.ldp.adblocker.vpn

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.nio.charset.StandardCharsets
import java.util.HashSet

class PacketHandlerTest {

    /** 构造一个 IPv4/UDP/DNS 查询包（A 记录查询 host）。 */
    private fun dnsQuery(host: String): ByteArray {
        // ---- DNS 消息 ----
        val dns = ByteArrayOutputStream()
        dns.write(0x12); dns.write(0x34)                       // id
        dns.write(0x01); dns.write(0x00)                       // flags: 标准查询, RD
        dns.write(0x00); dns.write(0x01)                       // qd=1
        dns.write(0x00); dns.write(0x00)                       // an
        dns.write(0x00); dns.write(0x00)                       // ns
        dns.write(0x00); dns.write(0x00)                       // ar
        for (label in host.split(".")) {                       // 问题段
            dns.write(label.length and 0xFF)
            for (c in label.toByteArray(StandardCharsets.US_ASCII)) dns.write(c.toInt() and 0xFF)
        }
        dns.write(0x00)                                        // 根标签
        dns.write(0x00); dns.write(0x01)                       // type A
        dns.write(0x00); dns.write(0x01)                       // class IN
        val dnsBytes = dns.toByteArray()

        val udpLen = 8 + dnsBytes.size
        val ipTotal = 20 + udpLen
        val pkt = ByteArrayOutputStream()
        // IP 头
        pkt.write(0x45); pkt.write(0x00)                       // ver/ihl, tos
        pkt.write((ipTotal ushr 8) and 0xFF); pkt.write(ipTotal and 0xFF) // 总长
        pkt.write(0x00); pkt.write(0x00)                       // id
        pkt.write(0x40); pkt.write(0x00)                       // flags DF
        pkt.write(0x40)                                        // ttl
        pkt.write(0x11)                                        // proto UDP
        pkt.write(0x00); pkt.write(0x00)                       // checksum（测试不校验）
        pkt.write(0x0A); pkt.write(0x00); pkt.write(0x02); pkt.write(0x0F) // src 10.0.2.15
        pkt.write(0x08); pkt.write(0x08); pkt.write(0x08); pkt.write(0x08) // dst 8.8.8.8
        // UDP 头
        pkt.write(0x30); pkt.write(0x39)                       // src port 12345
        pkt.write(0x00); pkt.write(0x35)                       // dst port 53
        pkt.write((udpLen ushr 8) and 0xFF); pkt.write(udpLen and 0xFF) // udp len
        pkt.write(0x00); pkt.write(0x00)                       // checksum
        pkt.write(dnsBytes)
        return pkt.toByteArray()
    }

    @Test
    fun parsesBlockedDomain() {
        val filter = AdDomainFilter(HashSet(listOf("pangolin-sdk.com")))
        val pkt = dnsQuery("pangolin-sdk.com")
        val r = PacketHandler.inspect(pkt, pkt.size, filter)
        assertTrue("应为 Blocked", r is PacketHandler.Result.Blocked)
        assertEquals("pangolin-sdk.com", (r as PacketHandler.Result.Blocked).domain)
    }

    @Test
    fun parsesAllowedDomain() {
        val filter = AdDomainFilter(HashSet(listOf("pangolin-sdk.com")))
        val pkt = dnsQuery("example.com")
        val r = PacketHandler.inspect(pkt, pkt.size, filter)
        assertTrue("应为 Allowed", r is PacketHandler.Result.Allowed)
        assertEquals("example.com", (r as PacketHandler.Result.Allowed).domain)
    }

    @Test
    fun nonDnsPacketPassThrough() {
        val filter = AdDomainFilter(HashSet(listOf("pangolin-sdk.com")))
        // 一段太短/非 IPv4 的数据应放行
        val r = PacketHandler.inspect(ByteArray(10), 10, filter)
        assertTrue(r is PacketHandler.Result.PassThrough)
    }

    @Test
    fun buildsBlockedResponseResolvesToZeroAddress() {
        val filter = AdDomainFilter(HashSet(listOf("pangolin-sdk.com")))
        val pkt = dnsQuery("pangolin-sdk.com")
        val resp = PacketHandler.buildBlockedDnsResponse(pkt, pkt.size)
        assertNotNull("应返回伪造应答", resp)
        val r = resp!!
        // 末 4 字节为 0.0.0.0
        val n = r.size
        assertArrayEquals(byteArrayOf(0, 0, 0, 0), r.copyOfRange(n - 4, n))
        // 仍是 IPv4 数据报
        assertEquals(4, (r[0].toInt() ushr 4) and 0x0F)
        // DNS 应答标志：QR=1（flags 高字节 bit7=1，即 0x81）
        // DNS 偏移 = ihl(20) + 8(UDP) = 28；DNS 内 flags 前还有 2 字节 ID → r[30]
        assertEquals(0x81.toByte(), r[30])
    }

    @Test
    fun buildsResponseSwapsSrcDstPorts() {
        val filter = AdDomainFilter(HashSet(listOf("pangolin-sdk.com")))
        val pkt = dnsQuery("pangolin-sdk.com")
        val resp = PacketHandler.buildBlockedDnsResponse(pkt, pkt.size)!!
        // 源端口应为 53（查询目的端口），目的端口应为 12345（查询源端口）
        val srcPort = ((resp[20].toInt() and 0xFF) shl 8) or (resp[21].toInt() and 0xFF)
        val dstPort = ((resp[22].toInt() and 0xFF) shl 8) or (resp[23].toInt() and 0xFF)
        assertEquals(53, srcPort)
        assertEquals(12345, dstPort)
    }
}
