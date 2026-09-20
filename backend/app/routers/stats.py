"""规则版本与拦截统计路由。"""
import json

import aiosqlite
from fastapi import APIRouter, HTTPException

from app.config import DB_PATH
from app.database import get_rules_version
from app.models import (
    DailyStat,
    InterceptStat,
    RulesVersion,
    StatsOverview,
    StatsSummary,
    TopDomain,
)

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/rules/version", response_model=RulesVersion)
async def get_rules_version_route():
    """返回当前规则库版本号与条目数量，客户端据此判断是否需要增量更新。"""
    version = await get_rules_version()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        d = await (await db.execute("SELECT COUNT(*) c FROM ad_domains")).fetchone()
        p = await (await db.execute("SELECT COUNT(*) c FROM popup_rules")).fetchone()
        return RulesVersion(
            rules_version=version,
            domains_count=d["c"],
            popup_rules_count=p["c"],
        )



@router.post("/stats/intercept")
async def report_intercept(stat: InterceptStat):
    """接收客户端上报的拦截统计。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO stats(device_id, intercepted_domains, closed_popups) VALUES(?, ?, ?)",
            (stat.device_id, json.dumps(stat.intercepted_domains, ensure_ascii=False),
             stat.closed_popups),
        )
        await db.commit()
    return {"ok": True}


@router.get("/stats/summary", response_model=StatsSummary)
async def stats_summary(device_id: str):
    """返回某设备的累计拦截汇总。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT COALESCE(SUM(closed_popups),0) sc, "
            "COUNT(*) c FROM stats WHERE device_id=?", (device_id,)
        )).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="no data")
        # 统计被拦截的不同域名数
        domains_rows = await (await db.execute(
            "SELECT intercepted_domains FROM stats WHERE device_id=?", (device_id,)
        )).fetchall()
        all_domains: set[str] = set()
        for r in domains_rows:
            try:
                all_domains.update(json.loads(r["intercepted_domains"] or "[]"))
            except json.JSONDecodeError:
                continue
        return StatsSummary(
            device_id=device_id,
            total_intercepted_domains=len(all_domains),
            total_closed_popups=row["sc"],
        )


@router.get("/stats/overview", response_model=StatsOverview)
async def stats_overview():
    """全局拦截统计聚合：活跃设备数、累计关闭弹窗数、被拦截的不同域名数。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        devices = await (await db.execute("SELECT COUNT(DISTINCT device_id) c FROM stats")).fetchone()
        popups = await (await db.execute("SELECT COALESCE(SUM(closed_popups),0) s FROM stats")).fetchone()
        rows = await (await db.execute("SELECT intercepted_domains FROM stats")).fetchall()
        all_domains: set[str] = set()
        for r in rows:
            try:
                all_domains.update(json.loads(r["intercepted_domains"] or "[]"))
            except json.JSONDecodeError:
                continue
        return StatsOverview(
            active_devices=devices["c"],
            total_closed_popups=popups["s"],
            unique_intercepted_domains=len(all_domains),
        )


@router.get("/stats/top-domains", response_model=list[TopDomain])
async def stats_top_domains(limit: int = 10):
    """被拦截域名命中次数排行（跨设备聚合，按命中数降序）。"""
    limit = max(1, min(limit, 100))
    counts: dict[str, int] = {}
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute("SELECT intercepted_domains FROM stats")).fetchall()
    for r in rows:
        try:
            domains = json.loads(r["intercepted_domains"] or "[]")
        except json.JSONDecodeError:
            continue
        for domain in domains:
            counts[domain] = counts.get(domain, 0) + 1
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [TopDomain(domain=d, hits=n) for d, n in top]


@router.get("/stats/daily", response_model=list[DailyStat])
async def stats_daily(days: int = 7):
    """近 N 日拦截趋势：每日关闭弹窗数与被拦截的域名命中次数（按上报时间本地日期聚合）。"""
    days = max(1, min(days, 90))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        rows = await (await db.execute(
            "SELECT substr(created_at, 1, 10) day, closed_popups, intercepted_domains "
            "FROM stats "
            "WHERE created_at >= datetime('now', 'localtime', ?)",
            (f"-{days - 1} days",),
        )).fetchall()
    by_day: dict[str, DailyStat] = {}
    for r in rows:
        day = r["day"]
        stat = by_day.get(day)
        if stat is None:
            stat = by_day[day] = DailyStat(day=day, closed_popups=0, intercepted_requests=0)
        stat.closed_popups += r["closed_popups"]
        try:
            stat.intercepted_requests += len(json.loads(r["intercepted_domains"] or "[]"))
        except json.JSONDecodeError:
            continue
    return [by_day[d] for d in sorted(by_day)]
