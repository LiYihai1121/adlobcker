package com.ldp.adblocker

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.text.format.DateUtils
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.ldp.adblocker.accessibility.PopupAccessibilityService
import com.ldp.adblocker.databinding.ActivityMainBinding
import com.ldp.adblocker.ui.MainViewModel
import com.ldp.adblocker.vpn.VpnAdBlockService
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val viewModel: MainViewModel by viewModels()

    /** VPN 授权回调。 */
    private val vpnAuthLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            startService(Intent(this, VpnAdBlockService::class.java))
            viewModel.setVpnRunning(true)
        } else {
            Toast.makeText(this, R.string.hint_vpn_needed, Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // 首次启动触发规则同步（异步，不阻塞 UI）
        lifecycleScope.launch {
            viewModel.updateRules()
        }

        // 绑定 VPN 开关
        binding.btnToggleVpn.setOnCheckedChangeListener { _, isChecked ->
            if (isChecked) {
                val intent = VpnService.prepare(this)
                if (intent != null) {
                    vpnAuthLauncher.launch(intent)
                } else {
                    startService(Intent(this, VpnAdBlockService::class.java))
                    viewModel.setVpnRunning(true)
                }
            } else {
                stopService(Intent(this, VpnAdBlockService::class.java).apply {
                    action = VpnAdBlockService.ACTION_STOP
                })
                viewModel.setVpnRunning(false)
            }
        }

        // 绑定无障碍开关
        binding.btnToggleAcc.setOnCheckedChangeListener { _, isChecked ->
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        // 更新规则
        binding.btnUpdateRules.setOnClickListener {
            viewModel.updateRules()
        }

        // 观察状态
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.state.collect { state ->
                    updateVpnUI(state)
                    updateAccessibilityUI(state)
                    updateStatsUI(state)
                    updateRulesInfoUI(state)

                    state.message?.let {
                        Toast.makeText(this@MainActivity, it, Toast.LENGTH_SHORT).show()
                        viewModel.consumeMessage()
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // 回到前台时刷新统计与无障碍状态，并顺带上报一次累计统计
        viewModel.refreshStats()
        viewModel.flushStats()
    }

    private fun updateVpnUI(state: MainViewModel.MainUiState) {
        val running = state.vpnRunning
        binding.tvVpnStatus.text = if (running) R.string.status_running else R.string.status_stopped
        binding.tvVpnStatus.setTextColor(ContextCompat.getColor(this, if (running) R.color.green_status else R.color.gray_status))
        binding.vpnStatusDot.background = ContextCompat.getDrawable(this, if (running) R.drawable.status_dot_green else R.drawable.status_dot_gray)
        binding.btnToggleVpn.isChecked = running
    }

    private fun updateAccessibilityUI(state: MainViewModel.MainUiState) {
        val accOn = isAccessibilityEnabled()
        viewModel.setAccessibilityEnabled(accOn)
        binding.tvAccStatus.text = if (accOn) R.string.status_running else R.string.status_stopped
        binding.tvAccStatus.setTextColor(ContextCompat.getColor(this, if (accOn) R.color.green_status else R.color.gray_status))
        binding.accStatusDot.background = ContextCompat.getDrawable(this, if (accOn) R.drawable.status_dot_green else R.drawable.status_dot_gray)
        binding.btnToggleAcc.isChecked = accOn
    }

    private fun updateStatsUI(state: MainViewModel.MainUiState) {
        binding.tvDomainsCount.text = state.interceptedDomains.toString()
        binding.tvPopupsCount.text = state.closedPopups.toString()
    }

    private fun updateRulesInfoUI(state: MainViewModel.MainUiState) {
        binding.tvRulesVersion.text = state.rulesVersion.toString()
        binding.tvDomainsCountInfo.text = state.domainsCount.toString()
        binding.tvPopupRulesCount.text = state.popupRulesCount.toString()

        if (state.lastSyncTime > 0) {
            val timeAgo = DateUtils.getRelativeTimeSpanString(
                state.lastSyncTime,
                System.currentTimeMillis(),
                DateUtils.MINUTE_IN_MILLIS
            )
            binding.tvLastSync.text = getString(R.string.last_sync, timeAgo)
        } else {
            binding.tvLastSync.text = getString(R.string.never_synced)
        }
    }

    /** 检查本应用的无障碍服务是否已启用。 */
    private fun isAccessibilityEnabled(): Boolean {
        val expected = ComponentName(this, PopupAccessibilityService::class.java).flattenToString()
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
            ?: return false
        val splitter = TextUtils.SimpleStringSplitter(':')
        splitter.setString(enabled)
        for (entry in splitter) {
            if (entry.equals(expected, ignoreCase = true)) return true
        }
        return false
    }
}
