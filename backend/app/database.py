"""SQLite 数据库初始化与连接管理。"""
import aiosqlite

from app.config import DB_PATH, BUILTIN_AD_DOMAINS, BUILTIN_POPUP_RULES

# meta 表中规则版本号的键
RULES_VERSION_KEY = "rules_version"
# meta 表中种子数据版本号的键
SEED_VERSION_KEY = "seed_version"
# 初始规则版本（仅在 meta 无记录时使用）
INITIAL_RULES_VERSION = 1
# 当前种子数据版本：升级种子库时 +1，配合幂等迁移使用
CURRENT_SEED_VERSION = 2

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


async def _get_meta(db: aiosqlite.Connection, key: str) -> str | None:
    db.row_factory = aiosqlite.Row
    row = await (await db.execute("SELECT value FROM meta WHERE key=?", (key,))).fetchone()
    return row["value"] if row else None


async def _set_meta(db: aiosqlite.Connection, key: str, value: str) -> None:
    await db.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


async def _seed(db: aiosqlite.Connection) -> None:
    """幂等写入种子数据，绝不覆盖或复活管理员已有操作。

    - 全新库（表为空）：完整写入当前种子域名与弹窗规则。
    - 已有数据的库（含旧版本创建）：只补充缺失条目（域名按 domain、
      规则按 id 判断），不覆盖已编辑/禁用的行，不复活已删除的规则；
      域名按 domain 补充时使用 INSERT OR IGNORE，保留既有 enabled 状态。
    """
    for domain in BUILTIN_AD_DOMAINS:
        await db.execute(
            "INSERT OR IGNORE INTO ad_domains(domain, platform, enabled) VALUES(?, ?, 1)",
            (domain, _guess_platform(domain)),
        )

    for rule in BUILTIN_POPUP_RULES:
        await db.execute(
            "INSERT INTO popup_rules(id, package_name, button_text_regex, view_id_regex, enabled) "
            "VALUES(?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO NOTHING",
            (rule["id"], rule["package_name"], rule["button_text_regex"],
             rule["view_id_regex"], int(rule["enabled"])),
        )


async def init_db() -> None:
    """启动时初始化数据库：建表、写初始版本号、幂等写入种子数据。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(SCHEMA)

        # 写入初始规则版本（若已存在则保留，不覆盖）
        await db.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO NOTHING",
            (RULES_VERSION_KEY, str(INITIAL_RULES_VERSION)),
        )

        seed_version = await _get_meta(db, SEED_VERSION_KEY)
        if seed_version is None or int(seed_version) < CURRENT_SEED_VERSION:
            await _seed(db)
            await _set_meta(db, SEED_VERSION_KEY, str(CURRENT_SEED_VERSION))

        await db.commit()


async def get_rules_version() -> int:
    """读取当前规则版本号（从 meta 表）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        return await _version_in(db)


async def _version_in(db: aiosqlite.Connection) -> int:
    value = await _get_meta(db, RULES_VERSION_KEY)
    return int(value) if value else INITIAL_RULES_VERSION


async def _bump_version_in(db: aiosqlite.Connection) -> int:
    """在给定连接内把规则版本号 +1（须与业务变更处于同一事务）。"""
    await db.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=CAST(meta.value AS INTEGER)+1",
        (RULES_VERSION_KEY, str(INITIAL_RULES_VERSION + 1)),
    )
    return await _version_in(db)


async def bump_rules_version() -> int:
    """规则版本号 +1 并返回新值（独立事务场景用）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        new_ver = await _bump_version_in(db)
        await db.commit()
        return new_ver


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
