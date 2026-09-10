"""弹窗关闭规则路由（供无障碍服务使用）。"""
import aiosqlite
from fastapi import APIRouter, HTTPException

from app.config import DB_PATH
from app.models import PopupRule

router = APIRouter(prefix="/api/v1/popup-rules", tags=["popup-rules"])


@router.get("", response_model=list[PopupRule])
async def list_popup_rules(enabled_only: bool = True):
    """返回弹窗关闭规则列表。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = (
            "SELECT id, package_name, button_text_regex, view_id_regex, enabled "
            "FROM popup_rules"
        )
        if enabled_only:
            sql += " WHERE enabled=1"
        sql += " ORDER BY id"
        rows = await db.execute(sql)
        items = await rows.fetchall()
        return [PopupRule(
            id=r["id"], package_name=r["package_name"],
            button_text_regex=r["button_text_regex"],
            view_id_regex=r["view_id_regex"], enabled=bool(r["enabled"]),
        ) for r in items]


@router.post("")
async def upsert_rule(rule: PopupRule):
    """新增/更新一条弹窗规则。"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO popup_rules(id, package_name, button_text_regex, view_id_regex, enabled) "
            "VALUES(?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET package_name=excluded.package_name, "
            "button_text_regex=excluded.button_text_regex, "
            "view_id_regex=excluded.view_id_regex, enabled=excluded.enabled",
            (rule.id, rule.package_name, rule.button_text_regex,
             rule.view_id_regex, int(rule.enabled)),
        )
        await db.commit()
    return {"ok": True, "id": rule.id}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int):
    """删除一条弹窗规则。"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM popup_rules WHERE id=?", (rule_id,))
        await db.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="rule not found")
    return {"ok": True, "deleted": rule_id}
