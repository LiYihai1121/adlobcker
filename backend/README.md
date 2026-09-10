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

服务默认监听 `http://0.0.0.0:8000`，接口文档见 `/docs`。

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

定时任务每 6 小时从公开规则源同步广告域名。
