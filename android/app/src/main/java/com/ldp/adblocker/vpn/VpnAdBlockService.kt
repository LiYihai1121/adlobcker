package com.ldp.adblocker.vpn

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Build
import android.os.ParcelFileDescriptor
import android.util.Log
import androidx.core.app.NotificationCompat
import com.ldp.adblocker.MainActivity
import com.ldp.adblocker.R
import com.ldp.adblocker.data.RulesRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import java.nio.ByteBuffer

/**
 * VPN 广告拦截服务。
 *
 * 工作原理：建立一个本地 VPN 隧道，读取出站 IP 数据报，解析其中的 DNS 查询域名，
 * 命中黑名单的查询直接丢弃（不转发），使广告域名无法解析、广告网络请求失败，
 * 从而屏蔽开屏/信息流/激励视频/插屏/Banner 等所有依赖网络拉取的广告。
 */
class VpnAdBlockService : VpnService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    @Volatile private var vpnInterface: ParcelFileDescriptor? = null
    @Volatile private var running = false
    private var filter: AdDomainFilter? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action
        if (action == ACTION_STOP) {
            stopAndExit()
            return START_NOT_STICKY
        }
        startForeground()
        scope.launch {
            filter = AdDomainFilter.load(this@VpnAdBlockService)
            establishVpn()
        }
        return START_STICKY
    }

    /** 建立 VPN 隧道并开始循环读取/过滤数据包。 */
    private fun establishVpn() {
        val builder = Builder().apply {
            setSession(getString(R.string.app_name))
            // 虚拟网卡地址（避免与常见局域网冲突）
            addAddress(VIRTUAL_IP, 32)
            addRoute("0.0.0.0", 0)  // 拦截全部流量
            addDnsServer("8.8.8.8")
            setMtu(1500)
            setBlocking(true)
        }
        val pfd = builder.establish() ?: run {
            Log.e(TAG, "建立 VPN 隧道失败（权限被拒）")
            stopAndExit()
            return
        }
        vpnInterface = pfd
        running = true
        tunnelLoop(pfd)
    }

    /** 主循环：从 tun 读包 → 过滤 → 写回需要转发的包。 */
    private fun tunnelLoop(pfd: ParcelFileDescriptor) {
        val input = java.io.FileInputStream(pfd.fileDescriptor)
        // ByteBuffer 方式写回（VPN 写入接口要求 ByteBuffer）
        val output = java.io.FileOutputStream(pfd.fileDescriptor)
        val packet = ByteArray(32767)
        val repo = RulesRepository(this)
        val filter = this.filter ?: return

        try {
            while (running && !Thread.interrupted()) {
                val n = input.read(packet)
                if (n <= 0) continue
                when (val result = PacketHandler.inspect(packet, n, filter)) {
                    is PacketHandler.Result.Blocked -> {
                        // 构造 0.0.0.0 伪造应答写回 tun，使广告域名立即解析失败
                        val response = PacketHandler.buildBlockedDnsResponse(packet, n)
                        if (response != null) {
                            try {
                                output.write(response)
                            } catch (e: Exception) {
                                Log.w(TAG, "写回拦截应答失败", e)
                            }
                        }
                        Log.d(TAG, "拦截广告域名: ${result.domain}")
                        // 记入内存缓冲，待回前台时随统计上报后端（域名明细）
                        com.ldp.adblocker.data.BlockedDomainBuffer.record(result.domain)
                        scope.launch {
                            repo.incrementDomainsCount(1)
                        }
                    }
                    else -> {
                        // 放行：写回 tun 让系统处理
                        output.write(packet, 0, n)
                    }
                }
            }
        } catch (e: Exception) {
            if (running) Log.e(TAG, "隧道循环异常", e)
        } finally {
            try { input.close(); output.close() } catch (_: Exception) {}
        }
    }

    private fun stopAndExit() {
        running = false
        try { vpnInterface?.close() } catch (_: Exception) {}
        vpnInterface = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        running = false
        scope.cancel()
        try { vpnInterface?.close() } catch (_: Exception) {}
        super.onDestroy()
    }

    override fun onRevoke() {
        stopAndExit()
        super.onRevoke()
    }

    // ====== 前台服务通知 ======

    private fun startForeground() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.vpn_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply { description = getString(R.string.vpn_channel_desc) }
            nm.createNotificationChannel(channel)
        }
        val openIntent = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val notification: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.vpn_notification_title))
            .setContentText(getString(R.string.vpn_notification_text))
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
            .setContentIntent(openIntent)
            .build()
        startForeground(NOTIF_ID, notification)
    }

    companion object {
        private const val TAG = "VpnAdBlock"
        private const val VIRTUAL_IP = "10.10.10.1"
        private const val CHANNEL_ID = "adblock_vpn"
        private const val NOTIF_ID = 1
        const val ACTION_STOP = "com.ldp.adblocker.action.STOP_VPN"
    }
}
