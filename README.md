# 广告屏蔽 App（Kotlin + FastAPI）

组合方案屏蔽手机 APP 内广告：**VPN 网络拦截** + **无障碍服务自动关弹窗**，覆盖国内主流广告 SDK（穿山甲、优量汇、快手联盟、百青藤等）与 UI 弹窗广告。

## 目录结构

```
adlobcker/
├── android/          # Android 客户端（Kotlin）
│   ├── app/
│   │   ├── src/main/java/com/ldp/adblocker/
│   │   │   ├── vpn/                 # VPN 网络层广告拦截
│   │   │   ├── accessibility/       # 无障碍服务自动关弹窗
│   │   │   ├── data/                # Room 数据库 + Retrofit 后端通信
│   │   │   └── ui/                  # ViewModel
│   │   └── src/main/res/            # 布局、字符串、图标
│   ├── build.gradle.kts
│   └── settings.gradle.kts
└── backend/          # FastAPI 后端
    ├── app/
    │   ├── routers/                 # domains / popup_rules / stats
    │   ├── config.py                # 内置广告域名种子库
    │   ├── database.py              # SQLite 初始化
    │   ├── scheduler.py             # 定时同步远程规则
    │   └── main.py
    └── requirements.txt
```

## 技术方案

### VPN 网络拦截（覆盖：开屏/信息流/激励视频/插屏/Banner/原生/视频贴片等）
- `VpnAdBlockService` 建立本地 VPN 隧道，拦截出站 DNS 查询
- `PacketHandler` 解析 IPv4/UDP/DNS 包，提取被查询域名
- `AdDomainFilter` 内存黑名单后缀匹配，命中域名直接丢弃查询，使广告 SDK 无法解析、广告无法加载

### 无障碍服务（覆盖：开屏跳过/插屏关闭/悬浮窗关闭/锁屏广告等 UI 弹窗）
- `PopupAccessibilityService` 监听窗口变化，遍历控件树
- `PopupRuleMatcher` 用文案正则（"跳过/关闭/✕/不再显示"）+ 包名匹配规则命中目标按钮
- 自动执行点击，关闭弹窗广告

### 后端（FastAPI）
- 提供广告域名黑名单、弹窗关闭规则、规则版本号、拦截统计接口
- 内置穿山甲/优量汇/快手联盟/百青藤等国内主流广告 SDK 域名种子库
- `apscheduler` 每 6 小时从公开广告拦截列表同步更新

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
3. 点「更新规则库」拉取后端最新黑名单

> 注：模拟器访问宿主机后端用 `10.0.2.2`（已在 `BackendApi.kt` 配置）。真机部署请改为后端实际 IP。

## 合规说明
- 本应用仅拦截已知广告 SDK 网络请求与弹窗关闭按钮，不收集用户隐私数据
- 统计数据仅记录拦截次数，不包含任何浏览内容
- 符合工信部「开屏及弹窗广告须显著标明广告标识和关闭标志、确保一键关闭」的要求方向
