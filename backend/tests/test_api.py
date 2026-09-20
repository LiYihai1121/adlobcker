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


async def test_stats_top_domains(client):
    await client.post("/api/v1/stats/intercept", json={
        "device_id": "d1",
        "intercepted_domains": ["pangolin-sdk.com", "gdt.qq.com", "pangolin-sdk.com"],
        "closed_popups": 0,
    })
    await client.post("/api/v1/stats/intercept", json={
        "device_id": "d2",
        "intercepted_domains": ["pangolin-sdk.com"],
        "closed_popups": 0,
    })
    resp = await client.get("/api/v1/stats/top-domains")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0] == {"domain": "pangolin-sdk.com", "hits": 3}
    assert body[1] == {"domain": "gdt.qq.com", "hits": 1}
    # limit 生效
    resp = await client.get("/api/v1/stats/top-domains", params={"limit": 1})
    assert len(resp.json()) == 1


async def test_stats_daily(client):
    await client.post("/api/v1/stats/intercept", json={
        "device_id": "d1",
        "intercepted_domains": ["a.com", "b.com"],
        "closed_popups": 2,
    })
    await client.post("/api/v1/stats/intercept", json={
        "device_id": "d1",
        "intercepted_domains": ["a.com"],
        "closed_popups": 1,
    })
    resp = await client.get("/api/v1/stats/daily")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1  # 两次上报在同一天
    assert body[0]["closed_popups"] == 3
    assert body[0]["intercepted_requests"] == 3


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


# ===== 规则生命周期与版本自增 =====


async def _version(client) -> int:
    resp = await client.get("/api/v1/rules/version")
    return resp.json()["rules_version"]


async def test_popup_rule_create_without_id_bumps_version(client):
    v0 = await _version(client)
    resp = await client.post("/api/v1/popup-rules", json={
        "package_name": "com.new.app", "button_text_regex": "领取奖励",
        "view_id_regex": "reward", "enabled": True,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["id"] is not None
    assert await _version(client) == v0 + 1

    # 列表可见且按新 id 排序
    resp = await client.get("/api/v1/popup-rules?enabled_only=false")
    ids = [r["id"] for r in resp.json()]
    assert body["id"] in ids


async def test_popup_rule_identical_update_no_bump(client):
    v0 = await _version(client)
    await client.post("/api/v1/popup-rules", json={
        "id": 2, "package_name": "*", "button_text_regex": "关闭|✕|×|关闭广告|不再显示",
        "view_id_regex": "close|dismiss|cancel", "enabled": True,
    })
    assert await _version(client) == v0  # 内容未变不升版本


async def test_popup_rule_changed_update_bumps(client):
    v0 = await _version(client)
    resp = await client.post("/api/v1/popup-rules", json={
        "id": 2, "package_name": "*", "button_text_regex": "关闭|✕|×",
        "view_id_regex": "close|dismiss|cancel", "enabled": True,
    })
    assert resp.status_code == 200
    assert resp.json()["changed"] is True
    assert await _version(client) == v0 + 1


async def test_popup_rule_delete_bumps_version(client):
    v0 = await _version(client)
    resp = await client.delete("/api/v1/popup-rules/4")
    assert resp.status_code == 200
    assert await _version(client) == v0 + 1
    resp = await client.get("/api/v1/popup-rules?enabled_only=false")
    assert all(r["id"] != 4 for r in resp.json())
    # 删除不存在的规则：404 且不升版本
    v1 = await _version(client)
    resp = await client.delete("/api/v1/popup-rules/999")
    assert resp.status_code == 404
    assert await _version(client) == v1


async def test_popup_rule_package_name_filter(client):
    await client.post("/api/v1/popup-rules", json={
        "package_name": "com.special.app", "button_text_regex": "领取",
        "view_id_regex": None, "enabled": True,
    })
    resp = await client.get("/api/v1/popup-rules", params={"package_name": "com.special.app"})
    items = resp.json()
    assert len(items) == 1 and items[0]["package_name"] == "com.special.app"
    # 通配规则不属于该包名
    assert "*" not in [r["package_name"] for r in items]


async def test_popup_rule_invalid_package_rejected(client):
    resp = await client.post("/api/v1/popup-rules", json={
        "package_name": "bad package name!", "button_text_regex": "x", "enabled": True,
    })
    assert resp.status_code == 422


async def test_domain_add_and_version_bump(client):
    v0 = await _version(client)
    resp = await client.post("/api/v1/domains", json={
        "domain": "Ad.Example.COM.", "platform": "测试", "enabled": True,
    })
    assert resp.status_code == 200
    assert resp.json()["domain"] == "ad.example.com"  # 已规范化
    assert await _version(client) == v0 + 1

    # 完全相同的再次提交：不升版本
    resp = await client.post("/api/v1/domains", json={
        "domain": "ad.example.com", "platform": "测试", "enabled": True,
    })
    assert resp.json()["changed"] is False
    assert await _version(client) == v0 + 1


async def test_domain_invalid_rejected(client):
    resp = await client.post("/api/v1/domains", json={
        "domain": "not a domain", "platform": "测试", "enabled": True,
    })
    assert resp.status_code == 422


async def test_restart_keeps_admin_edits(client):
    """模拟重启：init_db 再次执行不得覆盖/复活管理员对规则的修改与删除。"""
    # 管理员禁用规则 1、删除规则 2
    resp = await client.post("/api/v1/popup-rules", json={
        "id": 1, "package_name": "*", "button_text_regex": "跳过|跳过广告",
        "view_id_regex": "skip", "enabled": False,
    })
    assert resp.status_code == 200
    await client.delete("/api/v1/popup-rules/2")

    from app.database import init_db
    await init_db()  # 模拟服务重启

    resp = await client.get("/api/v1/popup-rules?enabled_only=false")
    rules = {r["id"]: r for r in resp.json()}
    assert rules[1]["enabled"] is False          # 禁用状态保留
    assert rules[1]["button_text_regex"] == "跳过|跳过广告"  # 编辑内容保留
    assert 2 not in rules                         # 已删除的不复活


async def test_snapshot_matches_version_and_after_change(client):
    v0 = await _version(client)
    await client.post("/api/v1/popup-rules", json={
        "package_name": "com.snap.app", "button_text_regex": "关闭",
        "view_id_regex": "close", "enabled": True,
    })
    resp = await client.get("/api/v1/rules/snapshot")
    body = resp.json()
    assert body["rules_version"] == v0 + 1
    assert any(r["package_name"] == "com.snap.app" for r in body["popup_rules"])
    # 快照与版本接口一致
    assert body["rules_version"] == await _version(client)

