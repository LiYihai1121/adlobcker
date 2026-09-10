"""规则版本与拦截统计路由。"""
import json

import aiosqlite
from fastapi import APIRouter, HTTPException

from app.config import DB_PATH
from app.database import RULES_VERSION
from app.models import RulesVersion, InterceptStat, StatsSummary

router = APIRouter(prefix="/api/v1", tags=["meta"])


@router.get("/rules/version", response_model=RulesVersion)
async def get_rules_version():
    """返回当前规则库版本号与条目数量，客户端据此判断是否需要增量更新。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        d = await (await db.execute("SELECT COUNT(*) c FROM ad_domains")).fetchone()
        p = await (await db.execute("SELECT COUNT(*) c FROM popup_rules")).fetchone()
        return RulesVersion(
            rules_version=RULES_VERSION,
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
