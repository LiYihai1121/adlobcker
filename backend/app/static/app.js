"use strict";
/**
 * AdBlocker 控制台前端逻辑（TypeScript + Tailwind/DaisyUI）。
 * 类型定义与后端 app/models.py 的 Pydantic 模型保持一致。
 * 构建：cd backend/frontend && npm install && npm run build
 */
const AUTO_REFRESH_MS = 30000;
const MAX_ROWS = 40;
const DEBOUNCE_MS = 150;
/** 状态点主题色类（完整字面量写死，便于 Tailwind JIT 扫描到） */
const DOT_OK = "inline-block w-2.5 h-2.5 rounded-full bg-success";
const DOT_BAD = "inline-block w-2.5 h-2.5 rounded-full bg-error";
function $(id) {
    const el = document.getElementById(id);
    if (!el)
        throw new Error(`找不到元素 #${id}`);
    return el;
}
function dialogEl(id) {
    return $(id);
}
function escapeHtml(text) {
    if (text == null)
        return "";
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}
function fmt(n) {
    return n.toLocaleString("zh-CN");
}
/** 按平台返回 DaisyUI 徽章颜色类 */
function platformBadgeClass(platform) {
    switch (platform) {
        case "穿山甲": return "badge-warning";
        case "优量汇": return "badge-info";
        case "快手联盟": return "badge-success";
        case "百青藤": return "badge-primary";
        default: return "badge-ghost";
    }
}
/** 管理密钥仅保存在页面内存中，随写请求发送，不写 storage / URL / 日志。 */
function adminKey() {
    return $("adminKey").value.trim();
}
function showBanner(id, msg) {
    const el = $(id);
    el.textContent = msg;
    el.classList.remove("hidden");
    window.setTimeout(() => el.classList.add("hidden"), 5000);
}
async function fetchJson(url, init = {}) {
    const headers = { Accept: "application/json" };
    if (init.body !== undefined)
        headers["Content-Type"] = "application/json";
    if (init.adminKey)
        headers["X-Admin-Key"] = init.adminKey;
    const resp = await fetch(url, {
        method: init.method ?? "GET",
        headers,
        body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
    if (!resp.ok) {
        let detail = `${resp.status} ${resp.statusText}`;
        try {
            const body = (await resp.json());
            if (typeof body.detail === "string")
                detail = body.detail;
        }
        catch {
            /* 非 JSON 错误体，保留状态行 */
        }
        throw new Error(`HTTP ${detail} (${url})`);
    }
    return (await resp.json());
}
async function loadDashboard() {
    const [health, version, popupRules, domains, overview, topDomains, daily] = await Promise.all([
        fetchJson("/health"),
        fetchJson("/api/v1/rules/version"),
        fetchJson("/api/v1/popup-rules?enabled_only=false"),
        fetchJson("/api/v1/domains?enabled_only=true"),
        fetchJson("/api/v1/stats/overview"),
        fetchJson("/api/v1/stats/top-domains?limit=10"),
        fetchJson("/api/v1/stats/daily?days=7"),
    ]);
    return { health, version, popupRules, domains, overview, topDomains, daily };
}
let allDomains = [];
let allRules = [];
/** 编辑弹窗或删除确认打开时暂停自动刷新，避免覆盖正在编辑的表单 */
let modalOpen = false;
function renderHealth(health) {
    const ok = health.status === "healthy";
    $("health").textContent = ok ? "服务运行中" : "服务异常";
    $("dot").className = ok ? DOT_OK : DOT_BAD;
}
function renderCards(version, overview) {
    $("ver").textContent = `v${version.rules_version}`;
    $("dom").textContent = fmt(version.domains_count);
    $("pop").textContent = fmt(version.popup_rules_count);
    $("stat").textContent =
        `${fmt(overview.active_devices)} / ` +
            `${fmt(overview.unique_intercepted_domains)} / ` +
            `${fmt(overview.total_closed_popups)}`;
}
/** 拦截统计看板：Top 域名排行 + 近 7 日趋势（纯 CSS 条形图）。 */
function renderStatsBoard(topDomains, daily) {
    const maxHits = Math.max(1, ...topDomains.map((t) => t.hits));
    $("topDomains").innerHTML =
        topDomains
            .map((t, i) => `<tr><td class="text-base-content/60">${i + 1}</td>` +
            `<td class="font-mono text-xs break-all">${escapeHtml(t.domain)}</td>` +
            `<td class="w-2/5 min-w-32">` +
            `<div class="h-2 rounded bg-primary/70" style="width:${Math.round((t.hits / maxHits) * 100)}%"></div>` +
            `</td>` +
            `<td class="text-right font-mono">${fmt(t.hits)}</td></tr>`)
            .join("") ||
            `<tr><td colspan="4" class="text-center text-base-content/50 py-6">暂无拦截上报数据</td></tr>`;
    const maxReq = Math.max(1, ...daily.map((d) => d.intercepted_requests));
    $("daily").innerHTML =
        daily
            .map((d) => `<tr><td class="font-mono text-xs">${escapeHtml(d.day.slice(5))}</td>` +
            `<td class="w-2/5 min-w-32">` +
            `<div class="h-2 rounded bg-secondary/70" style="width:${Math.round((d.intercepted_requests / maxReq) * 100)}%"></div>` +
            `</td>` +
            `<td class="text-right font-mono">${fmt(d.intercepted_requests)}</td>` +
            `<td class="text-right font-mono">${fmt(d.closed_popups)}</td></tr>`)
            .join("") ||
            `<tr><td colspan="4" class="text-center text-base-content/50 py-6">近 7 日暂无数据</td></tr>`;
}
function renderPopupRules() {
    const q = $("ruleQ").value.trim();
    const filtered = q
        ? allRules.filter((r) => r.package_name.includes(q))
        : allRules;
    const sourceBadge = (r) => r.source === "gkd"
        ? ' <span class="badge badge-info badge-xs">订阅</span>'
        : r.source === "builtin"
            ? ' <span class="badge badge-ghost badge-xs">内置</span>'
            : "";
    $("rules").innerHTML =
        filtered
            .map((r) => `<tr class="${r.enabled ? "" : "opacity-50"}">` +
            `<td>${r.id}</td>` +
            `<td class="font-mono text-xs">${escapeHtml(r.package_name)}` +
            (r.package_name === "*" ? ' <span class="badge badge-ghost badge-xs">通用</span>' : "") +
            sourceBadge(r) +
            `</td>` +
            `<td><code class="text-xs break-all">${escapeHtml(r.button_text_regex)}</code></td>` +
            `<td class="font-mono text-xs">${escapeHtml(r.view_id_regex) || "—"}</td>` +
            `<td><span class="badge badge-sm ${r.enabled ? "badge-success" : "badge-ghost"}">` +
            `${r.enabled ? "启用" : "停用"}</span></td>` +
            `<td class="text-right whitespace-nowrap">` +
            `<button type="button" class="btn btn-xs btn-ghost" data-act="edit" data-id="${r.id}">编辑</button>` +
            `<button type="button" class="btn btn-xs btn-ghost" data-act="toggle" data-id="${r.id}">` +
            `${r.enabled ? "停用" : "启用"}</button>` +
            `<button type="button" class="btn btn-xs btn-ghost text-error" data-act="del" data-id="${r.id}">删除</button>` +
            `</td></tr>`)
            .join("") ||
            `<tr><td colspan="6" class="text-center text-base-content/50 py-6">没有匹配的规则</td></tr>`;
}
function renderDomains() {
    const q = $("q").value.trim().toLowerCase();
    const filtered = q
        ? allDomains.filter((d) => `${d.domain} ${d.platform ?? ""}`.toLowerCase().includes(q))
        : allDomains;
    const slice = filtered.slice(0, MAX_ROWS);
    $("domains").innerHTML =
        slice
            .map((d) => `<tr><td class="font-mono text-xs break-all">${escapeHtml(d.domain)}</td>` +
            `<td><span class="badge badge-sm ${platformBadgeClass(d.platform)}">` +
            `${escapeHtml(d.platform) || "其它"}</span></td></tr>`)
            .join("") ||
            `<tr><td colspan="2" class="text-center text-base-content/50 py-6">没有匹配项</td></tr>`;
    $("shown").textContent =
        `显示 ${fmt(slice.length)} / ${fmt(filtered.length)} 条` +
            `（共 ${fmt(allDomains.length)}）`;
}
function renderError(err) {
    const msg = err instanceof Error ? err.message : String(err);
    $("health").textContent = "无法连接后端";
    $("dot").className = DOT_BAD;
    const banner = $("error");
    banner.textContent = `加载失败：${msg}（30 秒后自动重试）`;
    banner.classList.remove("hidden");
}
async function refresh() {
    if (modalOpen)
        return;
    const btn = $("refresh");
    btn.disabled = true;
    try {
        const data = await loadDashboard();
        $("error").classList.add("hidden");
        renderHealth(data.health);
        renderCards(data.version, data.overview);
        renderStatsBoard(data.topDomains, data.daily);
        allRules = data.popupRules;
        renderPopupRules();
        allDomains = data.domains;
        renderDomains();
        $("updated").textContent =
            `最后更新：${new Date().toLocaleTimeString("zh-CN")}`;
    }
    catch (err) {
        renderError(err);
    }
    finally {
        btn.disabled = false;
    }
}
// ===== 规则管理 =====
function openRuleDialog(rule) {
    modalOpen = true;
    $("ruleDialogTitle").textContent = rule ? `编辑规则 #${rule.id}` : "新增规则";
    $("fId").value = rule?.id != null ? String(rule.id) : "";
    $("fPackage").value = rule?.package_name ?? "";
    $("fText").value = rule?.button_text_regex ?? "";
    $("fViewId").value = rule?.view_id_regex ?? "";
    $("fEnabled").checked = rule?.enabled ?? true;
    dialogEl("ruleDialog").showModal();
}
function closeRuleDialog() {
    modalOpen = false;
    dialogEl("ruleDialog").close();
}
async function saveRule(ev) {
    ev.preventDefault();
    const key = adminKey();
    const payload = {
        package_name: $("fPackage").value.trim(),
        button_text_regex: $("fText").value,
        view_id_regex: $("fViewId").value.trim() || null,
        enabled: $("fEnabled").checked,
    };
    const idStr = $("fId").value;
    if (idStr)
        payload.id = Number(idStr);
    if (!payload.package_name || !payload.button_text_regex) {
        showBanner("error", "包名与按钮文案正则不能为空");
        return;
    }
    const btn = $("ruleSave");
    btn.disabled = true;
    try {
        await fetchJson("/api/v1/popup-rules", {
            method: "POST",
            body: payload,
            adminKey: key,
        });
        closeRuleDialog();
        showBanner("success", idStr ? `规则 #${idStr} 已更新` : "规则已新增");
        await refresh();
    }
    catch (err) {
        showBanner("error", `保存失败：${err instanceof Error ? err.message : err}`);
    }
    finally {
        btn.disabled = false;
    }
}
async function toggleRule(id) {
    const rule = allRules.find((r) => r.id === id);
    if (!rule)
        return;
    const btn = $("refresh");
    btn.disabled = true;
    try {
        await fetchJson("/api/v1/popup-rules", {
            method: "POST",
            body: { ...rule, enabled: !rule.enabled },
            adminKey: adminKey(),
        });
        showBanner("success", `规则 #${id} 已${rule.enabled ? "停用" : "启用"}`);
        await refresh();
    }
    catch (err) {
        showBanner("error", `操作失败：${err instanceof Error ? err.message : err}`);
    }
    finally {
        btn.disabled = false;
    }
}
async function confirmDelete() {
    const id = Number($("deleteConfirm").dataset.id);
    const btn = $("deleteConfirm");
    btn.disabled = true;
    try {
        await fetchJson(`/api/v1/popup-rules/${id}`, { method: "DELETE", adminKey: adminKey() });
        modalOpen = false;
        dialogEl("deleteDialog").close();
        showBanner("success", `规则 #${id} 已删除`);
        await refresh();
    }
    catch (err) {
        showBanner("error", `删除失败：${err instanceof Error ? err.message : err}`);
    }
    finally {
        btn.disabled = false;
    }
}
function initRuleActions() {
    $("rules").addEventListener("click", (ev) => {
        const target = ev.target.closest("[data-act]");
        if (!target)
            return;
        const id = Number(target.dataset.id);
        const rule = allRules.find((r) => r.id === id);
        if (!rule)
            return;
        if (target.dataset.act === "edit") {
            openRuleDialog(rule);
        }
        else if (target.dataset.act === "toggle") {
            void toggleRule(id);
        }
        else if (target.dataset.act === "del") {
            modalOpen = true;
            $("deleteHint").textContent =
                `确定删除规则 #${id}（${rule.package_name}：${rule.button_text_regex}）吗？`;
            $("deleteConfirm").dataset.id = String(id);
            dialogEl("deleteDialog").showModal();
        }
    });
}
function debounce(fn, ms) {
    let timer;
    return () => {
        window.clearTimeout(timer);
        timer = window.setTimeout(fn, ms);
    };
}
function main() {
    $("q").addEventListener("input", debounce(renderDomains, DEBOUNCE_MS));
    $("ruleQ").addEventListener("input", debounce(renderPopupRules, DEBOUNCE_MS));
    $("refresh").addEventListener("click", () => void refresh());
    $("newRule").addEventListener("click", () => openRuleDialog(null));
    $("ruleCancel").addEventListener("click", closeRuleDialog);
    $("ruleForm").addEventListener("submit", (ev) => void saveRule(ev));
    $("deleteCancel").addEventListener("click", () => {
        modalOpen = false;
        dialogEl("deleteDialog").close();
    });
    $("deleteConfirm").addEventListener("click", () => void confirmDelete());
    initRuleActions();
    void refresh();
    window.setInterval(() => void refresh(), AUTO_REFRESH_MS);
}
main();
//# sourceMappingURL=app.js.map