"""规则聚合路由：一次返回版本号 + 域名列表 + 弹窗规则，减少客户端往返。"""
import aiosqlite
from fastapi import APIRouter

from app.config import DB_PATH
from app.database import _version_in
from app.models import DomainItem, PopupRule, RulesSnapshot

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


@router.get("/snapshot", response_model=RulesSnapshot)
async def get_rules_snapshot(enabled_only: bool = True):
    """返回规则全量快照，客户端一次请求即可完成整体同步。

    版本号与规则内容在同一事务中读取，保证快照自洽。
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # 显式开启读事务，确保 version 与两条 SELECT 看到同一快照
        await db.execute("BEGIN")
        try:
            version = await _version_in(db)

            dsql = "SELECT domain, platform, enabled FROM ad_domains"
            if enabled_only:
                dsql += " WHERE enabled=1"
            dsql += " ORDER BY platform, domain"
            drows = await (await db.execute(dsql)).fetchall()

            psql = ("SELECT id, package_name, button_text_regex, view_id_regex, enabled "
                    "FROM popup_rules")
            if enabled_only:
                psql += " WHERE enabled=1"
            psql += " ORDER BY id"
            prows = await (await db.execute(psql)).fetchall()
        except Exception:
            await db.rollback()
            raise
        await db.commit()

    return RulesSnapshot(
        rules_version=version,
        domains=[DomainItem(domain=r["domain"], platform=r["platform"],
                            enabled=bool(r["enabled"])) for r in drows],
        popup_rules=[PopupRule(id=r["id"], package_name=r["package_name"],
                               button_text_regex=r["button_text_regex"],
                               view_id_regex=r["view_id_regex"],
                               enabled=bool(r["enabled"])) for r in prows],
    )
