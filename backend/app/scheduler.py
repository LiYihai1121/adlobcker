"""定时从公开规则源同步广告域名列表。"""
import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import REMOTE_DOMAIN_SOURCES, BUILTIN_AD_DOMAINS
from app.database import _guess_platform, bump_rules_version
from app.settings import settings

logger = logging.getLogger("adblock.scheduler")
scheduler = AsyncIOScheduler()


async def sync_remote_domains() -> None:
    """从远程源拉取域名并写入数据库（去重合并），完成后自增规则版本号。"""
    import aiosqlite
    from app.config import DB_PATH

    new_domains: set[str] = set(BUILTIN_AD_DOMAINS)
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        for url in REMOTE_DOMAIN_SOURCES:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                for line in resp.text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("!") or line.startswith("#"):
                        continue
                    # 兼容 ||example.com^ 与 example.com 形式
                    for token in ("||", "0.0.0.0 ", "0.0.0.0\t"):
                        if line.startswith(token):
                            line = line[len(token):]
                            break
                    line = line.rstrip("^").strip()
                    if "." in line and " " not in line:
                        new_domains.add(line)
            except Exception as exc:  # noqa
                logger.warning("同步源 %s 失败: %s", url, exc)

    inserted = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for domain in new_domains:
            cur = await db.execute(
                "INSERT OR IGNORE INTO ad_domains(domain, platform, enabled) VALUES(?, ?, 1)",
                (domain, _guess_platform(domain)),
            )
            inserted += cur.rowcount
        await db.commit()

    # 仅有新增/变化时才提升版本号，避免客户端无意义增量更新
    if inserted > 0:
        new_ver = await bump_rules_version()
        logger.info("远程同步完成，新增 %d 条域名，规则版本升至 %d", inserted, new_ver)
    else:
        logger.info("远程同步完成，无新增域名")


def start_scheduler() -> None:
    """注册并启动定时任务。"""
    interval = settings.sync_interval_hours
    scheduler.add_job(sync_remote_domains, "interval", hours=interval,
                      id="sync_domains", replace_existing=True, max_instances=1)
    scheduler.start()
    logger.info("定时任务调度器已启动（每 %d 小时同步一次远程规则）", interval)


async def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)

