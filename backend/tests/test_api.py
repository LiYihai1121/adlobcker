"""后端 API 集成测试：覆盖健康检查、域名/规则/版本/统计全链路。"""
import pytest


pytestmark = pytest.mark.asyncio


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_rules_version_initial(client):
    resp = await client.get("/api/v1/rules/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rules_version"] == 1
    assert body["domains_count"] > 0
    assert body["popup_rules_count"] == 4


async def test_list_domains(client):
    resp = await client.get("/api/v1/domains")
    assert resp.status_code == 200
    items = resp.json()
    assert any(d["domain"] == "pangolin-sdk.com" for d in items)
    # 启用态域名应排除禁用项
    assert all(d["enabled"] for d in items)


async def test_add_and_delete_domain(client):
    # 新增
    resp = await client.post("/api/v1/domains", json={
        "domain": "ad.test.example", "platform": "测试", "enabled": True,
    })
    assert resp.status_code == 200
    # 查询确认存在
    resp = await client.get("/api/v1/domains?enabled_only=false")
    assert any(d["domain"] == "ad.test.example" for d in resp.json())
    # 删除
    resp = await client.delete("/api/v1/domains/ad.test.example")
    assert resp.status_code == 200
    # 再删应 404
    resp = await client.delete("/api/v1/domains/ad.test.example")
    assert resp.status_code == 404


async def test_list_popup_rules(client):
    resp = await client.get("/api/v1/popup-rules")
    assert resp.status_code == 200
    rules = resp.json()
    assert len(rules) == 4
    assert any("跳过" in r["button_text_regex"] for r in rules)


async def test_upsert_popup_rule(client):
    resp = await client.post("/api/v1/popup-rules", json={
        "id": 5, "package_name": "com.test.app",
        "button_text_regex": "残忍拒绝", "view_id_regex": "reject",
        "enabled": True,
    })
    assert resp.status_code == 200
    resp = await client.get("/api/v1/popup-rules?enabled_only=false")
    assert any(r["id"] == 5 for r in resp.json())


async def test_stats_report_and_summary(client):
    # 上报拦截
    resp = await client.post("/api/v1/stats/intercept", json={
        "device_id": "dev-1",
        "intercepted_domains": ["pangolin-sdk.com", "gdt.qq.com"],
        "closed_popups": 3,
    })
    assert resp.status_code == 200
    # 再上报一次
    await client.post("/api/v1/stats/intercept", json={
        "device_id": "dev-1",
        "intercepted_domains": ["pangolin-sdk.com"],
        "closed_popups": 1,
    })
    # 汇总
    resp = await client.get("/api/v1/stats/summary", params={"device_id": "dev-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["device_id"] == "dev-1"
    assert body["total_closed_popups"] == 4
    # 去重后 2 个不同域名
    assert body["total_intercepted_domains"] == 2


async def test_rules_snapshot(client):
    resp = await client.get("/api/v1/rules/snapshot")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rules_version"] == 1
    assert len(body["domains"]) > 0
    assert len(body["popup_rules"]) == 4
    # 快照应与分接口一致
    domains_resp = await client.get("/api/v1/domains")
    assert body["domains"] == domains_resp.json()


async def test_stats_overview(client):
    # 上报两个设备的数据
    await client.post("/api/v1/stats/intercept", json={
        "device_id": "dev-1", "intercepted_domains": ["a.com"], "closed_popups": 2,
    })
    await client.post("/api/v1/stats/intercept", json={
        "device_id": "dev-2", "intercepted_domains": ["b.com"], "closed_popups": 5,
    })
    resp = await client.get("/api/v1/stats/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_devices"] == 2
    assert body["total_closed_popups"] == 7
    assert body["unique_intercepted_domains"] == 2


async def test_admin_key_protects_writes(client, monkeypatch):
    """配置 admin_key 后，写接口需带正确 X-Admin-Key。"""
    import app.settings as s
    monkeypatch.setattr(s.settings, "admin_key", "secret-key")

    # 不带 key → 401
    resp = await client.post("/api/v1/domains", json={
        "domain": "x.test", "platform": "T", "enabled": True,
    })
    assert resp.status_code == 401

    # 错误 key → 401
    resp = await client.post("/api/v1/domains", json={
        "domain": "x.test", "platform": "T", "enabled": True,
    }, headers={"X-Admin-Key": "wrong"})
    assert resp.status_code == 401

    # 正确 key → 200
    resp = await client.post("/api/v1/domains", json={
        "domain": "x.test", "platform": "T", "enabled": True,
    }, headers={"X-Admin-Key": "secret-key"})
    assert resp.status_code == 200

    # 删除同样受保护
    resp = await client.delete("/api/v1/domains/x.test", headers={"X-Admin-Key": "secret-key"})
    assert resp.status_code == 200

    # 弹窗规则写接口也受保护
    resp = await client.post("/api/v1/popup-rules", json={
        "id": 9, "package_name": "com.x", "button_text_regex": "跳过",
        "view_id_regex": "skip", "enabled": True,
    }, headers={"X-Admin-Key": "secret-key"})
    assert resp.status_code == 200

