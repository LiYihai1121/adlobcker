"""pytest 公共 fixture：每个测试用独立的临时 SQLite 数据库，互不干扰。"""
import os

import pytest
import pytest_asyncio

# 测试隔离：在任何 app 模块导入前覆盖真实 .env 配置，
# 强制以开发模式、空管理密钥运行，避免本机 .env 影响测试结果。
os.environ["ADBLOCK_ENVIRONMENT"] = "development"
os.environ["ADBLOCK_ADMIN_KEY"] = ""


def _patch_db_path(monkeypatch, db_file: str) -> None:
    """把所有在模块级绑定 DB_PATH 的模块都指向临时库，保证全链路一致。"""
    import app.config as cfg
    import app.database as db_mod
    import app.routers.domains as domains_mod
    import app.routers.popup_rules as popup_mod
    import app.routers.rules as rules_mod
    import app.routers.stats as stats_mod

    monkeypatch.setattr(cfg, "DB_PATH", db_file)
    monkeypatch.setattr(db_mod, "DB_PATH", db_file)
    monkeypatch.setattr(domains_mod, "DB_PATH", db_file)
    monkeypatch.setattr(popup_mod, "DB_PATH", db_file)
    monkeypatch.setattr(rules_mod, "DB_PATH", db_file)
    monkeypatch.setattr(stats_mod, "DB_PATH", db_file)


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    """提供指向临时数据库的 httpx AsyncClient（不走真实 lifespan/调度器）。"""
    db_file = str(tmp_path / "test.db")
    _patch_db_path(monkeypatch, db_file)

    # 禁用启动期联网同步，避免测试依赖外网
    import app.settings as s
    monkeypatch.setattr(s.settings, "sync_on_startup", False)

    from app.database import init_db
    await init_db()

    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
