# AdBlocker Backend（FastAPI）

屏蔽手机 APP 广告的后端服务，为 Android 客户端提供：

- 广告域名黑名单（穿山甲、优量汇、快手联盟、百青藤等国内主流广告 SDK）
- 弹窗关闭 UI 规则（开屏跳过、插屏关闭等按钮文案正则）
- 拦截统计上报与汇总

## 运行

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate          # Windows
pip install -r requirements.txt
python run.py                   # 或 uvicorn app.main:app --reload
```

服务默认监听 `http://0.0.0.0:8000`，接口文档见 `/docs`，浏览器控制台见 `/`。

## 前端控制台

控制台源码在 `frontend/`（TypeScript + Tailwind/DaisyUI），构建产物落到 `app/static/`。
- 本地开发：`cd frontend && npm install && npm run build`（或 `npm run watch:js` / `watch:css` 热构建）
- Docker 部署：`Dockerfile` 已含 Node 多阶段构建，无需本地预装 Node 即可产出最新前端

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/domains` | 获取广告域名黑名单 |
| POST | `/api/v1/domains` | 新增/更新域名（管理） |
| DELETE | `/api/v1/domains/{domain}` | 删除域名 |
| GET | `/api/v1/popup-rules` | 获取弹窗关闭规则 |
| POST | `/api/v1/popup-rules` | 新增/更新规则 |
| DELETE | `/api/v1/popup-rules/{id}` | 删除规则 |
| GET | `/api/v1/rules/version` | 规则版本号与条目数 |
| POST | `/api/v1/stats/intercept` | 上报拦截统计 |
| GET | `/api/v1/stats/summary?device_id=` | 设备拦截汇总 |
| GET | `/api/v1/stats/overview` | 全局聚合（活跃设备/拦截域名/关弹窗） |
| GET | `/api/v1/stats/top-domains?limit=` | 被拦截域名命中排行 |
| GET | `/api/v1/stats/daily?days=` | 近 N 日拦截趋势 |

定时任务每 6 小时从公开规则源同步广告域名，并从 GKD 订阅源（`app/config.py` 中
`GKD_SUBSCRIPTION_SOURCES`）下载订阅、降级转换为弹窗规则（`app/gkd_convert.py`）：

- 仅转换简单选择器（`text/desc`/`vid/id` 字面量匹配），含层级组合符、多步
  `preKeys` 的复杂规则自动跳过；订阅中默认禁用的应用/分组/规则不导入；
- 转换结果写入 `popup_rules`（`source='gkd'`），每次同步对该来源全量替换，
  手工（`manual`）与内置（`builtin`）规则不受影响；
- 规则集有实际变化才自增规则版本号；全部订阅源失败时保留现有规则不清空。

> 注意：手工编辑/删除 `source='gkd'` 的规则会在下一次订阅同步时被覆盖/复活，
> 订阅规则请通过订阅源管理。
