# 广告屏蔽 App（Kotlin + FastAPI）

组合方案屏蔽手机 APP 内广告：**VPN 网络拦截** + **无障碍服务自动关弹窗**，覆盖国内主流广告 SDK（穿山甲、优量汇、快手联盟、百青藤等）与 UI 弹窗广告。

## 目录结构

```text
adlobcker/
├── android/              # Android 客户端（Kotlin）
│   ├── app/
│   │   ├── src/main/java/com/ldp/adblocker/
│   │   │   ├── vpn/                     # VPN 网络层广告拦截（DNS 伪造 0.0.0.0）
│   │   │   ├── accessibility/           # 无障碍服务自动关弹窗
│   │   │   ├── data/                    # Room 数据库 + Retrofit 后端通信
│   │   │   └── ui/                     # ViewModel
│   │   ├── src/main/res/xml/            # 网络安全配置、无障碍配置
│   │   ├── src/test/                    # 单元测试（PacketHandler/AdDomainFilter/PopupRuleMatcher）
│   │   └── build.gradle.kts
│   └── settings.gradle.kts
└── backend/              # FastAPI 后端
    ├── app/
    │   ├── routers/                     # domains / popup_rules / rules / stats
    │   ├── auth.py                      # 管理 API 鉴权（X-Admin-Key）
    │   ├── settings.py                  # Pydantic-Settings 配置（含生产密钥校验）
    │   ├── config.py                    # 内置广告域名种子库 + 远程同步源 + GKD 订阅源
    │   ├── domain_rules.py              # 域名规范化 / 拦截列表行解析（EasyList+hosts）
    │   ├── gkd_convert.py               # GKD 订阅（JSON5）→ 弹窗规则降级转换
    │   ├── database.py                  # SQLite 初始化 + 规则版本管理
    │   ├── scheduler.py                 # 定时同步远程规则
    │   └── main.py
    ├── frontend/                        # 控制台源码（TypeScript + Tailwind/DaisyUI）
    ├── tests/                           # pytest 集成测试
    ├── Dockerfile / docker-compose.yml  # 容器化部署（开发）
    ├── Caddyfile / docker-compose.prod.yml  # 生产部署：Caddy 自动 HTTPS 反向代理
    └── requirements.txt
```

## 技术方案

### VPN 网络拦截（覆盖：开屏/信息流/激励视频/插屏/Banner/原生/视频贴片等）

- `VpnAdBlockService` 建立本地 VPN 隧道，拦截出站 DNS 查询
- `PacketHandler` 解析 IPv4/UDP/DNS 包，提取被查询域名
- `AdDomainFilter` 内存黑名单后缀匹配，命中域名后由 `PacketHandler.buildBlockedDnsResponse` 注入指向 `0.0.0.0` 的伪造 DNS 应答写回 tun，广告域名立即解析失败、广告无法加载

### 无障碍服务（覆盖：开屏跳过/插屏关闭/悬浮窗关闭/锁屏广告等 UI 弹窗）

- `PopupAccessibilityService` 监听窗口变化，遍历控件树
- `PopupRuleMatcher` 用文案正则（"跳过/关闭/✕/不再显示"）+ 包名匹配规则命中目标按钮
- 自动执行点击，关闭弹窗广告

### 后端（FastAPI）

- 提供广告域名黑名单、弹窗关闭规则、规则版本号、拦截统计接口
- **规则全量快照** `GET /api/v1/rules/snapshot`：一次返回版本+域名+规则，客户端单次同步
- **全局统计聚合** `GET /api/v1/stats/overview`：跨设备活跃数 / 关闭弹窗数 / 拦截域名数
- **拦截统计看板**：`GET /api/v1/stats/top-domains`（域名命中排行）+ `GET /api/v1/stats/daily`（近 N 日趋势），控制台以纯 CSS 条形图展示
- **管理 API 鉴权**：写接口（增删域名 / 改弹窗规则）受 `X-Admin-Key` 保护，密钥为空时放行（仅本地开发）；`ADBLOCK_ENVIRONMENT=production` 时密钥为空则应用拒绝启动
- **Web 控制台**：TypeScript + Tailwind/DaisyUI，支持按包名筛选、弹窗规则增删改（模态框）、密钥仅存页面内存不落盘
- **域名入库规范化**（`domain_rules.py`）：远程列表与管理写入统一解析为可被 Android 后缀匹配的纯域名，跳过例外/路径/过滤选项/通配
- **CORS** 与 **Pydantic-Settings** 配置，支持 `.env` / 环境变量覆盖
- 内置穿山甲/优量汇/快手联盟/百青藤等国内主流广告 SDK 域名种子库，并补充经 AdGuard DNS Filter 核验的国际 SDK（AppLovin/Chartboost/AdColony 等）；宽泛业务根域（如 amap.com / umeng.com）不入库以免误伤
- `apscheduler` 每 6 小时从公开广告拦截列表同步更新，**有新增才自增规则版本号**
- **GKD 订阅集成（轻量版）**：定时下载 GKD 订阅（官方默认订阅 + AIsouler 精选），由 `gkd_convert.py` 把简单选择器（text/desc/vid/id 字面量）降级转换为现有弹窗规则格式写入 `popup_rules`（`source='gkd'`，按来源全量替换，手工/内置规则不受影响），复杂选择器与订阅默认禁用项自动跳过；Android 端零改动直接受益

## 运行

### 后端

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python run.py
# 访问 http://localhost:8000/docs 查看接口文档
```

### Android

用 Android Studio 打开 `android/` 目录，Sync Gradle 后运行到设备/模拟器：

1. 开启「VPN 网络拦截」→ 系统弹 VPN 授权，允许
2. 开启「弹窗自动关闭」→ 跳转无障碍设置，启用 `广告屏蔽` 服务
3. 点「更新规则库」拉取后端最新黑名单（`GET /api/v1/rules/snapshot` 全量快照，本地事务原子写入）

> 后端地址在构建时经 `BuildConfig.BACKEND_BASE_URL` 注入：
> - **debug**：默认 `http://10.0.2.2:8000/`（模拟器访问宿主机）；真机调试改为后端局域网 IP，并在 `src/debug/res/xml/network_security_config.xml` 的 `<domain>` 中放行该地址的明文流量。
> - **release**：必须传入 https 地址，且以 `/` 结尾，否则 Gradle 构建直接报错：
>   ```bash
>   ./gradlew :app:assembleRelease -PbackendBaseUrl=https://your.domain/
>   ```
>   release 不含明文放行，仅信任系统证书（见 `network_security_config.xml`）。

## 合规说明

- 本应用仅拦截已知广告 SDK 网络请求与弹窗关闭按钮，不收集用户隐私数据
- 统计数据仅记录拦截次数，不包含任何浏览内容
- 符合工信部「开屏及弹窗广告须显著标明广告标识和关闭标志、确保一键关闭」的要求方向

## 全栈架构

```text
┌──────────────────── Android App ────────────────────┐      ┌──────────── FastAPI Backend ────────────┐
│  MainActivity / MainViewModel (UI + 状态)          │      │  main.py (CORS + lifespan)              │
│     │                                              │      │     │                                   │
│     ├── VpnAdBlockService ── PacketHandler          │ HTTP │     ├── routers/domains · popup_rules   │
│     │     (DNS 解析 + 0.0.0.0 伪造应答)             │◄────►│     ├── routers/rules (snapshot)        │
│     │     └── AdDomainFilter (后缀匹配黑名单)       │      │     ├── routers/stats (summary/overview/top-daily)│
│     │                                              │      │     ├── auth.py (X-Admin-Key)           │
│     ├── PopupAccessibilityService ── PopupRuleMatcher│     │     ├── scheduler.py (远程同步+版本自增) │
│     │     (遍历节点树, 文案/viewId 正则命中即点击)   │      │     └── database.py (SQLite+规则版本)   │
│     │                                              │      │                                          │
│     └── Room (本地缓存) ◄── RulesRepository (同步)  │      │  SQLite (ad_domains/popup_rules/stats)  │
└────────────────────────────────────────────────────┘      └──────────────────────────────────────────┘
```

## 测试

### 后端（pytest）

```bash
cd backend
pip install -r requirements.txt
python -m pytest -v        # 39 个测试：健康/版本/域名CRUD/规则CRUD/快照/统计/鉴权
                           # + Top域名/每日趋势 + 域名规范化(domain_rules)
                           # + GKD 订阅转换与同步（gkd_convert/scheduler）
                           # + Settings 环境变量与生产校验
```

GitHub Actions（`.github/workflows/backend.yml`）会在 push/PR 到 main 时自动运行后端测试。

### Android（JUnit）

```bash
cd android
./gradlew :app:testDebugUnitTest   # PacketHandler DNS 解析与伪造应答、AdDomainFilter 后缀匹配、
                                   # PopupRuleMatcher 正则、BackendApi 快照 DTO 序列化
```

## 部署（Docker）

`Dockerfile` 为**多阶段构建**：先用 `node:20` 编译前端（TypeScript→app.js、Tailwind→style.css），再装入 `python:3.11` 运行时，因此**全新克隆后直接构建即可获得完整控制台**，无需本地预装 Node。

### 开发 / 本地

```bash
cd backend
cp .env.example .env          # 按需修改（务必设置 ADBLOCK_ADMIN_KEY）
docker compose up -d --build  # http://localhost:8000  （/docs 接口文档）
```

> `docker-compose.yml` 不再挂载 `.env` 文件（缺失会被 Docker 当目录创建而破坏启动），改用 `env_file`（可选）+ `environment` 显式注入；并内置 `healthcheck` 探测 `/health`。

### 生产（Caddy 自动 HTTPS）

`docker-compose.prod.yml` 在后端前加一层 Caddy 反向代理，自动向 Let's Encrypt 申请并续期证书。后端仅 `expose` 到容器网络、不对公网暴露端口，写接口强制要求 `ADBLOCK_ADMIN_KEY`（`ADBLOCK_ENVIRONMENT=production` 下密钥为空则启动失败）。

前置条件：公网域名 DNS 已解析到本机，防火墙放行 80/443，并把 `Caddyfile` 里的 `your-domain.example` 换成真实域名。

```bash
cd backend
cp .env.example .env.prod                       # 设置 ADBLOCK_ENVIRONMENT=production 与 ADBLOCK_ADMIN_KEY
docker compose -f docker-compose.prod.yml up -d --build
```

> 局域网 / 无域名场景可改用 `:80 { reverse_proxy adblocker-backend:8000 }`（仅 HTTP，不建议公网使用）。Android release 包须以 `-PbackendBaseUrl=https://your.domain/` 指向该域名。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ADBLOCK_ENVIRONMENT` | `development` | `production` 时强制要求非空 `ADBLOCK_ADMIN_KEY`，否则拒绝启动 |
| `ADBLOCK_DB_PATH` | `data/adblock.db` | SQLite 路径（兼容旧名 `DB_PATH`） |
| `SYNC_INTERVAL_HOURS` | `6` | 远程规则同步间隔 |
| `CORS_ORIGINS` | `["*"]` | CORS 来源（生产建议收紧） |
| `SYNC_ON_STARTUP` | `true` | 启动时是否立即同步一次 |
| `ADBLOCK_ADMIN_KEY` | （空） | 管理写接口密钥，生产务必设置（兼容旧名 `ADMIN_KEY`） |

## 项目状态

- ✅ 后端：配置层(CORS/Settings/.env)、生产密钥校验、规则版本动态自增、snapshot/overview、域名规范化、admin 鉴权、Docker 多阶段构建(含前端)、GKD 订阅降级转换与定时同步、39 个 pytest 全部通过
- ✅ 前端：TypeScript+Tailwind/DaisyUI 控制台，支持弹窗规则增删改与包名筛选、密钥内存态；拦截统计看板（Top 域名排行 + 近 7 日趋势条形图）；源码与构建产物均已纳入版本库；CI 校验 `npm run build`
- ✅ 数据库：SQLite，种子数据由代码初始化（含 AdGuard 核验的国际 SDK 域名），`backend/data/` 目录随仓库占位存在
- ✅ 部署：开发 `docker compose up -d --build` 一键拉起；生产 `docker-compose.prod.yml` + Caddy 自动 HTTPS
- ✅ Android：DNS 伪造 `0.0.0.0` 应答、快照全量原子同步、规则热更新、拦截域名内存缓冲+统计增量上报（域名明细+弹窗偏移，失败重发不丢数据）、BuildConfig 注入后端地址(release 强制 https)、网络安全配置、单元测试（PacketHandler/AdDomainFilter/PopupRuleMatcher/BackendApi）
- ⚠️ Android 编译已在本地 Gradle 验证（testDebugUnitTest 通过），真机行为仍待真机联调
- 🔜 后续：真机端到端联调、种子库持续扩充（新域名须经公开拦截列表核验后入库）