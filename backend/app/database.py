"""SQLite 数据库初始化与连接管理。"""
import aiosqlite

from app.config import DB_PATH, BUILTIN_AD_DOMAINS, BUILTIN_POPUP_RULES

# meta 表中规则版本号的键
RULES_VERSION_KEY = "rules_version"
# 初始规则版本（仅在 meta 无记录时使用）
INITIAL_RULES_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS ad_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    platform TEXT,           -- 归属平台：穿山甲/优量汇/快手联盟/百青藤/其它
    enabled INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS popup_rules (
    id INTEGER PRIMARY KEY,
    package_name TEXT NOT NULL,      -- 目标APP包名，* 表示通配
    button_text_regex TEXT NOT NULL, -- 按钮文案正则
    view_id_regex TEXT,             -- viewId 正则
    enabled INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    intercepted_domains TEXT DEFAULT '',  -- JSON 数组
    closed_popups INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


async def init_db() -> None:
    """启动时初始化数据库并填充内置种子数据。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)

        # 写入初始规则版本（若已存在则保留，不覆盖）
        await db.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO NOTHING",
            (RULES_VERSION_KEY, str(INITIAL_RULES_VERSION)),
        )

        # 种子广告域名
        for domain in BUILTIN_AD_DOMAINS:
            await db.execute(
                "INSERT OR IGNORE INTO ad_domains(domain, platform, enabled) VALUES(?, ?, 1)",
                (domain, _guess_platform(domain)),
            )

        # 种子弹窗规则
        for rule in BUILTIN_POPUP_RULES:
            await db.execute(
                "INSERT OR REPLACE INTO popup_rules(id, package_name, button_text_regex, view_id_regex, enabled) "
                "VALUES(?, ?, ?, ?, ?)",
                (rule["id"], rule["package_name"], rule["button_text_regex"],
                 rule["view_id_regex"], int(rule["enabled"])),
            )

        await db.commit()


async def get_rules_version() -> int:
    """读取当前规则版本号（从 meta 表）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT value FROM meta WHERE key=?", (RULES_VERSION_KEY,)
        )).fetchone()
        return int(row["value"]) if row else INITIAL_RULES_VERSION


async def bump_rules_version() -> int:
    """规则版本号 +1 并返回新值，供远程同步后调用。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1",
            (RULES_VERSION_KEY, str(INITIAL_RULES_VERSION)),
        )
        await db.commit()
        return await get_rules_version()


def _guess_platform(domain: str) -> str:
    if any(k in domain for k in ("pangolin", "snssdk", "oceanengine", "tiktok", "toutiao")):
        return "穿山甲"
    if "qq.com" in domain or "adqq" in domain:
        return "优量汇"
    if "kuaishou" in domain or "ksadx" in domain:
        return "快手联盟"
    if "baidu" in domain:
        return "百青藤"
    return "其它"


async def get_db() -> aiosqlite.Connection:
    """获取一个数据库连接（在路由中通过依赖注入使用）。"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

