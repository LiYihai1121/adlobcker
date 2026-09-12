/**
 * AdBlocker 控制台前端逻辑（TypeScript + Tailwind/DaisyUI）。
 * 类型定义与后端 app/models.py 的 Pydantic 模型保持一致。
 * 构建：cd backend/frontend && npm install && npm run build
 */

interface DomainItem {
  domain: string;
  platform: string | null;
  enabled: boolean;
}
interface PopupRule {
  id: number;
  package_name: string;
  button_text_regex: string;
  view_id_regex: string | null;
  enabled: boolean;
}
interface RulesVersion {
  rules_version: number;
  domains_count: number;
  popup_rules_count: number;
}
interface StatsOverview {
  active_devices: number;
  total_closed_popups: number;
  unique_intercepted_domains: number;
}
interface HealthStatus {
  status: string;
}
interface DashboardData {
  health: HealthStatus;
  version: RulesVersion;
  popupRules: PopupRule[];
  domains: DomainItem[];
  overview: StatsOverview;
}

const AUTO_REFRESH_MS = 30_000;
const MAX_ROWS = 40;
const DEBOUNCE_MS = 150;

/** 状态点主题色类（完整字面量写死，便于 Tailwind JIT 扫描到） */
const DOT_OK = "inline-block w-2.5 h-2.5 rounded-full bg-success";
const DOT_BAD = "inline-block w-2.5 h-2.5 rounded-full bg-error";

function $<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) throw new Error(`找不到元素 #${id}`);
  return el as T;
}

function escapeHtml(text: string | null | undefined): string {
  if (text == null) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmt(n: number): string {
  return n.toLocaleString("zh-CN");
}

/** 按平台返回 DaisyUI 徽章颜色类 */
function platformBadgeClass(platform: string | null): string {
  switch (platform) {
    case "穿山甲": return "badge-warning";
    case "优量汇": return "badge-info";
    case "快手联盟": return "badge-success";
    case "百青藤": return "badge-primary";
    default: return "badge-ghost";
  }
}

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url, { headers: { Accept: "application/json" } });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} ${resp.statusText} (${url})`);
  }
  return (await resp.json()) as T;
}

async function loadDashboard(): Promise<DashboardData> {
  const [health, version, popupRules, domains, overview] = await Promise.all([
    fetchJson<HealthStatus>("/health"),
    fetchJson<RulesVersion>("/api/v1/rules/version"),
    fetchJson<PopupRule[]>("/api/v1/popup-rules"),
    fetchJson<DomainItem[]>("/api/v1/domains?enabled_only=true"),
    fetchJson<StatsOverview>("/api/v1/stats/overview"),
  ]);
  return { health, version, popupRules, domains, overview };
}


let allDomains: DomainItem[] = [];

function renderHealth(health: HealthStatus): void {
  const ok = health.status === "healthy";
  $("health").textContent = ok ? "服务运行中" : "服务异常";
  $("dot").className = ok ? DOT_OK : DOT_BAD;
}

function renderCards(version: RulesVersion, overview: StatsOverview): void {
  $("ver").textContent = `v${version.rules_version}`;
  $("dom").textContent = fmt(version.domains_count);
  $("pop").textContent = fmt(version.popup_rules_count);
  $("stat").textContent =
    `${fmt(overview.active_devices)} / ` +
    `${fmt(overview.unique_intercepted_domains)} / ` +
    `${fmt(overview.total_closed_popups)}`;
}

function renderPopupRules(rules: PopupRule[]): void {
  $("rules").innerHTML = rules
    .map(
      (r) =>
        `<tr><td>${r.id}</td>` +
        `<td class="font-mono text-xs">${escapeHtml(r.package_name)}</td>` +
        `<td><code class="text-xs break-all">${escapeHtml(r.button_text_regex)}</code></td>` +
        `<td class="font-mono text-xs">${escapeHtml(r.view_id_regex) || "—"}</td></tr>`
    )
    .join("");
}

function renderDomains(): void {
  const q = $<HTMLInputElement>("q").value.trim().toLowerCase();
  const filtered = q
    ? allDomains.filter((d) =>
        `${d.domain} ${d.platform ?? ""}`.toLowerCase().includes(q)
      )
    : allDomains;
  const slice = filtered.slice(0, MAX_ROWS);
  $("domains").innerHTML =
    slice
      .map(
        (d) =>
          `<tr><td class="font-mono text-xs break-all">${escapeHtml(d.domain)}</td>` +
          `<td><span class="badge badge-sm ${platformBadgeClass(d.platform)}">` +
          `${escapeHtml(d.platform) || "其它"}</span></td></tr>`
      )
      .join("") ||
    `<tr><td colspan="2" class="text-center text-base-content/50 py-6">没有匹配项</td></tr>`;
  $("shown").textContent =
    `显示 ${fmt(slice.length)} / ${fmt(filtered.length)} 条` +
    `（共 ${fmt(allDomains.length)}）`;
}

function renderError(err: unknown): void {
  const msg = err instanceof Error ? err.message : String(err);
  $("health").textContent = "无法连接后端";
  $("dot").className = DOT_BAD;
  const banner = $("error");
  banner.textContent = `加载失败：${msg}（30 秒后自动重试）`;
  banner.classList.remove("hidden");
}

async function refresh(): Promise<void> {
  const btn = $<HTMLButtonElement>("refresh");
  btn.disabled = true;
  try {
    const data = await loadDashboard();
    $("error").classList.add("hidden");
    renderHealth(data.health);
    renderCards(data.version, data.overview);
    renderPopupRules(data.popupRules);
    allDomains = data.domains;
    renderDomains();
    $("updated").textContent =
      `最后更新：${new Date().toLocaleTimeString("zh-CN")}`;
  } catch (err) {
    renderError(err);
  } finally {
    btn.disabled = false;
  }
}

function debounce(fn: () => void, ms: number): () => void {
  let timer: number | undefined;
  return () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(fn, ms);
  };
}

function main(): void {
  $("q").addEventListener("input", debounce(renderDomains, DEBOUNCE_MS));
  $("refresh").addEventListener("click", () => void refresh());
  void refresh();
  window.setInterval(() => void refresh(), AUTO_REFRESH_MS);
}

main();