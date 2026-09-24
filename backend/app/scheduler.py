"""定时从公开规则源同步广告域名列表。"""
import logging

import aiosqlite
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import REMOTE_DOMAIN_SOURCES, GKD_SUBSCRIPTION_SOURCES
from app.database import _bump_version_in, _guess_platform
from app.domain_rules import parse_adblock_line
from app.gkd_convert import convert_subscription
from app.settings import settings

logger = logging.getLogger("adblock.scheduler")
scheduler = AsyncIOScheduler()


async def sync_remote_domains() -> None:
    """从远程源拉取域名并写入数据库（增量合并），完成后自增规则版本号。

    只解析可拦截的纯域名（纯域 / hosts 前缀 / ||domain^），跳过例外、
    路径、过滤选项等条目；同步为增量合并，不覆盖既有 enabled 状态。
    """
    import aiosqlite
    from app.config import DB_PATH

    new_domains: set[str] = set()
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        for url in REMOTE_DOMAIN_SOURCES:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                for line in resp.text.splitlines():
                    domain = parse_adblock_line(line)
                    if domain:
                        new_domains.add(domain)
            except Exception as exc:  # noqa
                logger.warning("同步源 %s 失败: %s", url, exc)

    inserted = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for domain in sorted(new_domains):
            cur = await db.execute(
                "INSERT OR IGNORE INTO ad_domains(domain, platform, enabled) VALUES(?, ?, 1)",
                (domain, _guess_platform(domain)),
            )
            inserted += cur.rowcount

        # 仅有新增时才提升版本号，与写入同一事务，避免客户端无意义增量更新
        if inserted > 0:
            new_ver = await _bump_version_in(db)
            await db.commit()
            logger.info("远程同步完成，新增 %d 条域名，规则版本升至 %d", inserted, new_ver)
        else:
            await db.rollback()
            logger.info("远程同步完成，无新增域名")


async def apply_gkd_rules(db, rules: list[tuple[str, str, str | None]]) -> bool:
    """把 GKD 转换规则写入 popup_rules（source='gkd' 全量替换）。

    仅替换 source='gkd' 的行，manual/builtin 规则不受影响。
    返回规则集是否发生变化（变化时须由调用方提升版本号并提交）。
    """
    db.row_factory = aiosqlite.Row
    rows = await (await db.execute(
        "SELECT package_name, button_text_regex, view_id_regex "
        "FROM popup_rules WHERE source='gkd'"
    )).fetchall()
    existing = {(r["package_name"], r["button_text_regex"], r["view_id_regex"])
                for r in rows}
    if existing == set(rules):
        return False
    await db.execute("DELETE FROM popup_rules WHERE source='gkd'")
    await db.executemany(
        "INSERT INTO popup_rules(package_name, button_text_regex, view_id_regex, enabled, source) "
        "VALUES(?, ?, ?, 1, 'gkd')",
        rules,
    )
    return True


async def sync_gkd_rules() -> None:
    """下载 GKD 订阅并降级转换为弹窗规则；规则集有变化才提升版本号。

    网络/解析失败不清理已有 gkd 规则，避免一次抖动清空订阅规则。
    """
    from app.config import DB_PATH

    merged: list[tuple[str, str, str | None]] = []
    ok = 0
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        for url in GKD_SUBSCRIPTION_SOURCES:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                merged.extend(convert_subscription(resp.text))
                ok += 1
            except Exception as exc:  # noqa
                logger.warning("GKD 订阅源 %s 同步失败: %s", url, exc)
    if ok == 0:
        logger.warning("所有 GKD 订阅源均同步失败，保留现有规则")
        return

    rules = sorted(set(merged))
    async with aiosqlite.connect(DB_PATH) as db:
        changed = await apply_gkd_rules(db, rules)
        if changed:
            new_ver = await _bump_version_in(db)
            await db.commit()
            logger.info("GKD 订阅同步完成，%d 条规则生效，规则版本升至 %d",
                        len(rules), new_ver)
        else:
            await db.rollback()
            logger.info("GKD 订阅同步完成，规则无变化（%d 条）", len(rules))


def start_scheduler() -> None:
    """注册并启动定时任务。"""
    interval = settings.sync_interval_hours
    scheduler.add_job(sync_remote_domains, "interval", hours=interval,
                      id="sync_domains", replace_existing=True, max_instances=1)
    scheduler.add_job(sync_gkd_rules, "interval", hours=interval,
                      id="sync_gkd", replace_existing=True, max_instances=1)
    scheduler.start()
    logger.info("定时任务调度器已启动（每 %d 小时同步一次远程规则）", interval)


async def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
