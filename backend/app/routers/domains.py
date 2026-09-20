"""广告域名黑名单路由。"""
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from app.auth import verify_admin_key
from app.config import DB_PATH
from app.database import _bump_version_in
from app.domain_rules import normalize_domain
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


@router.post("", dependencies=[Depends(verify_admin_key)])
async def add_domain(item: DomainItem):
    """新增/更新一个广告域名（管理用）。

    域名经规范化校验后入库；内容实际变化才提升规则版本号。
    """
    domain = normalize_domain(item.domain)
    if domain is None:
        raise HTTPException(status_code=422, detail="invalid domain")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await (await db.execute(
            "SELECT platform, enabled FROM ad_domains WHERE domain=?", (domain,)
        )).fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO ad_domains(domain, platform, enabled) VALUES(?, ?, ?)",
                (domain, item.platform, int(item.enabled)),
            )
            await _bump_version_in(db)
            changed = True
        else:
            changed = (
                (row["platform"] or None) != item.platform
                or bool(row["enabled"]) != item.enabled
            )
            if changed:
                await db.execute(
                    "UPDATE ad_domains SET platform=?, enabled=? WHERE domain=?",
                    (item.platform, int(item.enabled), domain),
                )
                await _bump_version_in(db)
        await db.commit()
    return {"ok": True, "domain": domain, "changed": changed}


@router.delete("/{domain}", dependencies=[Depends(verify_admin_key)])
async def delete_domain(domain: str):
    """删除一个广告域名，并提升规则版本号。"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM ad_domains WHERE domain=?", (domain,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="domain not found")
        await _bump_version_in(db)
        await db.commit()
    return {"ok": True, "deleted": domain}
