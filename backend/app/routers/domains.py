"""广告域名黑名单路由。"""
import aiosqlite
from fastapi import APIRouter, HTTPException

from app.config import DB_PATH
from app.models import DomainItem

router = APIRouter(prefix="/api/v1/domains", tags=["domains"])


@router.get("", response_model=list[DomainItem])
async def list_domains(enabled_only: bool = True):
    """返回全部广告域名黑名单，供客户端 VPN 拦截使用。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT domain, platform, enabled FROM ad_domains"
        if enabled_only:
            sql += " WHERE enabled=1"
        sql += " ORDER BY platform, domain"
        rows = await db.execute(sql)
        items = await rows.fetchall()
        return [DomainItem(domain=r["domain"], platform=r["platform"],
                           enabled=bool(r["enabled"])) for r in items]


@router.post("")
async def add_domain(item: DomainItem):
    """新增/更新一个广告域名（管理用）。"""
    from app.config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO ad_domains(domain, platform, enabled) VALUES(?, ?, ?) "
            "ON CONFLICT(domain) DO UPDATE SET platform=excluded.platform, enabled=excluded.enabled",
            (item.domain, item.platform, int(item.enabled)),
        )
        await db.commit()
    return {"ok": True, "domain": item.domain}


@router.delete("/{domain}")
async def delete_domain(domain: str):
    """删除一个广告域名。"""
    from app.config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM ad_domains WHERE domain=?", (domain,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="domain not found")
    return {"ok": True, "deleted": domain}
