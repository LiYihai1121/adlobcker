"""Settings 环境变量映射与生产模式校验测试。"""
import pytest

from app.settings import Settings


def test_adblock_env_aliases(monkeypatch):
    monkeypatch.setenv("ADBLOCK_DB_PATH", "/tmp/alias-test.db")
    monkeypatch.setenv("ADBLOCK_ADMIN_KEY", "s3cret")
    s = Settings()
    assert s.db_path == "/tmp/alias-test.db"
    assert s.admin_key == "s3cret"


def test_legacy_env_names_still_work(monkeypatch):
    # 新命名（ADBLOCK_*）未被设置时才走旧命名；先清除 conftest 注入的值
    monkeypatch.delenv("ADBLOCK_ADMIN_KEY", raising=False)
    monkeypatch.setenv("DB_PATH", "/tmp/legacy-test.db")
    monkeypatch.setenv("ADMIN_KEY", "legacy-key")
    s = Settings()
    assert s.db_path == "/tmp/legacy-test.db"
    assert s.admin_key == "legacy-key"


def test_production_requires_admin_key(monkeypatch):
    monkeypatch.setenv("ADBLOCK_ENVIRONMENT", "production")
    monkeypatch.setenv("ADBLOCK_ADMIN_KEY", "")
    with pytest.raises(ValueError, match="ADBLOCK_ADMIN_KEY"):
        Settings()


def test_production_accepts_non_blank_key(monkeypatch):
    monkeypatch.setenv("ADBLOCK_ENVIRONMENT", "production")
    monkeypatch.setenv("ADBLOCK_ADMIN_KEY", "prod-key")
    s = Settings()
    assert s.admin_key == "prod-key"
    assert s.environment == "production"


def test_empty_admin_key_normalized_to_none():
    s = Settings(admin_key="   ")
    assert s.admin_key is None
