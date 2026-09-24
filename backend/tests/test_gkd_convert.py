"""GKD 订阅（JSON5）降级转换与入库测试。

轻量版策略：仅转换简单选择器（text/desc/vid/id 字面量），
复杂选择器（层级组合符、preKeys 等）跳过；禁用项不导入。
"""
import aiosqlite
import pytest

from app import config
from app.database import get_rules_version, _bump_version_in
from app.gkd_convert import NEVER_MATCH, convert_subscription
from app.scheduler import apply_gkd_rules, sync_gkd_rules

SAMPLE_SUBSCRIPTION = """
{
  id: 900,
  name: '测试订阅',
  version: 1,
  apps: [
    {
      id: 'com.demo.video',
      groups: [
        {
          name: '开屏广告',
          rules: [
            { name: '精确文案', matches: '[text="跳过"]' },
            { name: 'vid-only', matches: '[vid="iv_splash_skip"]' },
            { name: 'id 后缀', matches: '[id$="tt_splash_skip_btn"]' },
            { name: '包名前缀 id', matches: '[id="com.demo.video:id/tv_close"][clickable=true]' },
          ],
        },
        {
          name: '混合 anyMatches',
          rules: [{
            anyMatches: [
              '[text*="跳过广告"][text.length<10]',
              '@[text="跳过"] + [text*="跳过"]',
            ],
          }],
        },
        {
          name: '默认禁用分组',
          enable: false,
          rules: [{ matches: '[text="更新"]' }],
        },
        {
          name: '复杂规则',
          rules: [
            { name: '多步规则', preKeys: [0], matches: '[text="关闭"]' },
            { name: '层级规则', matches: '[text="关闭"] > [vid="container"]' },
          ],
        },
      ],
    },
    {
      id: 'com.disabled.app',
      enable: false,
      groups: [{ rules: [{ matches: '[text="跳过"]' }] }],
    },
  ],
  globalGroups: [
    {
      name: '开屏-全局',
      rules: [{ matches: '[text*="跳过"][text.length<10]' }],
    },
  ],
}
"""


def test_convert_basic_selectors():
    rules = set(convert_subscription(SAMPLE_SUBSCRIPTION))
    assert ("com.demo.video", "^跳过$", None) in rules
    assert ("com.demo.video", NEVER_MATCH, "(^|/)iv_splash_skip$") in rules
    assert ("com.demo.video", NEVER_MATCH, "tt_splash_skip_btn$") in rules
    assert ("com.demo.video", NEVER_MATCH, "(^|/)tv_close$") in rules
    assert ("com.demo.video", "跳过广告", None) in rules
    assert ("*", "跳过", None) in rules


def test_convert_skips_unsupported_and_disabled():
    rules = set(convert_subscription(SAMPLE_SUBSCRIPTION))
    for pkg, text_re, _ in rules:
        assert text_re != "^更新$"
        assert text_re != "^关闭$"
        assert not (text_re == "^跳过$" and pkg == "com.disabled.app")


def test_convert_operator_mapping():
    sub = """
    {
      apps: [{
        id: 'com.ops',
        groups: [{ rules: [
          { matches: '[text^="同意并"]' },
          { matches: '[text$="广告"]' },
          { matches: '[desc="关闭按钮"]' },
        ] }],
      }],
    }
    """
    rules = set(convert_subscription(sub))
    assert ("com.ops", "^同意并", None) in rules
    assert ("com.ops", "广告$", None) in rules
    assert ("com.ops", "^关闭按钮$", None) in rules


def test_convert_dedup_and_matches_list():
    sub = """
    {
      apps: [{
        id: 'com.dup',
        groups: [{ rules: [
          { matches: ['[text="跳过"]', '[text="跳过"]'] },
          { matches: '[text="跳过"]' },
        ] }],
      }],
    }
    """
    rules = convert_subscription(sub)
    assert rules.count(("com.dup", "^跳过$", None)) == 1


@pytest.mark.asyncio
async def test_apply_gkd_rules_replace_idempotent(client):
    """应用规则：变化→True；相同规则集再应用→False（不误升版本）。"""
    rules = [("*", "^跳过$", None), ("com.x", "关闭", "(^|/)iv_close$")]
    async with aiosqlite.connect(config.DB_PATH) as db:
        assert await apply_gkd_rules(db, rules) is True
        await _bump_version_in(db)
        await db.commit()
    async with aiosqlite.connect(config.DB_PATH) as db:
        assert await apply_gkd_rules(db, rules) is False
        await db.rollback()

    resp = await client.get("/api/v1/popup-rules")
    gkd = [r for r in resp.json() if r["source"] == "gkd"]
    assert len(gkd) == 2
    # builtin 种子不受影响
    assert any(r["source"] == "builtin" for r in resp.json())


@pytest.mark.asyncio
async def test_apply_gkd_rules_preserves_manual(client):
    """全量替换只针对 source='gkd'，手工新增的规则不受影响。"""
    resp = await client.post("/api/v1/popup-rules", json={
        "package_name": "com.manual", "button_text_regex": "手工规则",
    })
    assert resp.status_code == 200

    async with aiosqlite.connect(config.DB_PATH) as db:
        assert await apply_gkd_rules(db, [("*", "订阅文案", None)]) is True
        await db.commit()

    rules = (await client.get("/api/v1/popup-rules")).json()
    manual = [r for r in rules if r["package_name"] == "com.manual"]
    assert len(manual) == 1 and manual[0]["source"] == "manual"


@pytest.mark.asyncio
async def test_sync_gkd_rules_end_to_end(client, monkeypatch):
    """同步全流程：模拟订阅源下载 → 转换入库 → 版本号提升 → 快照可见。"""
    monkeypatch.setattr("app.scheduler.GKD_SUBSCRIPTION_SOURCES", ["http://fake/gkd.json5"])

    class FakeResp:
        text = SAMPLE_SUBSCRIPTION

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url):
            return FakeResp()

    monkeypatch.setattr("app.scheduler.httpx.AsyncClient", FakeClient)

    ver0 = await get_rules_version()
    await sync_gkd_rules()
    ver1 = await get_rules_version()
    assert ver1 == ver0 + 1

    snap = (await client.get("/api/v1/rules/snapshot")).json()
    gkd = [r for r in snap["popup_rules"] if r["source"] == "gkd"]
    assert any(r["package_name"] == "com.demo.video" for r in gkd)
    assert any(r["package_name"] == "*" for r in gkd)

    # 再次同步相同内容：版本号不再变化
    await sync_gkd_rules()
    assert await get_rules_version() == ver1


@pytest.mark.asyncio
async def test_sync_gkd_rules_all_sources_fail_keeps_existing(client, monkeypatch):
    """全部订阅源失败时保留现有 gkd 规则，不清空、不升版本。"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await apply_gkd_rules(db, [("*", "旧规则", None)])
        await db.commit()

    monkeypatch.setattr("app.scheduler.GKD_SUBSCRIPTION_SOURCES", ["http://bad/1", "http://bad/2"])

    class FailClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url):
            raise RuntimeError("network down")

    monkeypatch.setattr("app.scheduler.httpx.AsyncClient", FailClient)

    ver0 = await get_rules_version()
    await sync_gkd_rules()
    assert await get_rules_version() == ver0
    rules = (await client.get("/api/v1/popup-rules")).json()
    assert any(r["source"] == "gkd" for r in rules)
