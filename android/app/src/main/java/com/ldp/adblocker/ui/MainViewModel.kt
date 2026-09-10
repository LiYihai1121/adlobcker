package com.ldp.adblocker.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ldp.adblocker.data.RulesRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/** 主界面状态。 */
data class MainUiState(
    val vpnRunning: Boolean = false,
    val accessibilityEnabled: Boolean = false,
    val interceptedDomains: Long = 0,
    val closedPopups: Long = 0,
    val updating: Boolean = false,
    val message: String? = null,
)

class MainViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = RulesRepository(app)

    private val _state = MutableStateFlow(MainUiState())
    val state: StateFlow<MainUiState> = _state

    init {
        refreshStats()
    }

    fun setVpnRunning(running: Boolean) {
        _state.value = _state.value.copy(vpnRunning = running)
    }

    fun setAccessibilityEnabled(enabled: Boolean) {
        _state.value = _state.value.copy(accessibilityEnabled = enabled)
    }

    fun refreshStats() {
        viewModelScope.launch {
            _state.value = _state.value.copy(
                interceptedDomains = repo.getDomainsCount(),
                closedPopups = repo.getPopupsCount(),
            )
        }
    }

    /** 从后端同步规则库。 */
    fun updateRules() {
        viewModelScope.launch {
            _state.value = _state.value.copy(updating = true, message = null)
            val ok = repo.syncRules()
            val msgRes = if (ok) "rules_updated" else "update_failed"
            val msg = getApplication<Application>().getString(
                if (ok) com.ldp.adblocker.R.string.rules_updated
                else com.ldp.adblocker.R.string.update_failed
            )
            _state.value = _state.value.copy(updating = false, message = msg)
            refreshStats()
        }
    }

    fun consumeMessage() {
        _state.value = _state.value.copy(message = null)
    }
}
