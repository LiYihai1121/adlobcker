package com.ldp.adblocker

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.ldp.adblocker.accessibility.PopupAccessibilityService
import com.ldp.adblocker.data.AdBlockDatabase
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
        binding.btnToggleVpn.setOnClickListener {
            if (viewModel.state.value.vpnRunning) {
                stopService(Intent(this, VpnAdBlockService::class.java).apply {
                    action = VpnAdBlockService.ACTION_STOP
                })
                viewModel.setVpnRunning(false)
            } else {
                val intent = VpnService.prepare(this)
                if (intent != null) {
                    vpnAuthLauncher.launch(intent)
                } else {
                    startService(Intent(this, VpnAdBlockService::class.java))
                    viewModel.setVpnRunning(true)
                }
            }
        }

        // 绑定无障碍开关
        binding.btnToggleAcc.setOnClickListener {
            if (viewModel.state.value.accessibilityEnabled) {
                // 跳转无障碍设置让用户关闭
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            } else {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }

        // 更新规则
        binding.btnUpdateRules.setOnClickListener {
            viewModel.updateRules()
        }

        // 观察状态
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.state.collect { state ->
                    binding.tvVpnStatus.text = if (state.vpnRunning) "运行中" else "未开启"
                    binding.btnToggleVpn.text = getString(
                        if (state.vpnRunning) R.string.btn_disable_vpn else R.string.btn_enable_vpn
                    )

                    val accOn = isAccessibilityEnabled()
                    viewModel.setAccessibilityEnabled(accOn)
                    binding.tvAccStatus.text = if (accOn) "运行中" else "未开启"
                    binding.btnToggleAcc.text = if (accOn)
                        R.string.btn_disable_acc else R.string.btn_enable_acc

                    binding.tvDomainsCount.text = state.interceptedDomains.toString()
                    binding.tvPopupsCount.text = state.closedPopups.toString()

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
        // 回到前台时刷新统计与无障碍状态
        viewModel.refreshStats()
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
