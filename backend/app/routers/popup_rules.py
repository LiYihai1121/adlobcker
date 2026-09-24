"""弹窗关闭规则路由（供无障碍服务使用）。"""
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from app.auth import verify_admin_key
from app.config import DB_PATH
from app.database import _bump_version_in
from app.models import PopupRule, PopupRuleWrite

router = APIRouter(prefix="/api/v1/popup-rules", tags=["popup-rules"])


@router.get("", response_model=list[PopupRule])
async def list_popup_rules(enabled_only: bool = True, package_name: str | None = None):
    """返回弹窗关闭规则列表；package_name 为精确过滤（* 为通配规则）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = (
            "SELECT id, package_name, button_text_regex, view_id_regex, enabled, source "
            "FROM popup_rules"
        )
        conds: list[str] = []
        params: list = []
        if enabled_only:
            conds.append("enabled=1")
        if package_name:
            conds.append("package_name=?")
            params.append(package_name)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY id"
        rows = await db.execute(sql, params)
        items = await rows.fetchall()
        return [PopupRule(
            id=r["id"], package_name=r["package_name"],
            button_text_regex=r["button_text_regex"],
            view_id_regex=r["view_id_regex"], enabled=bool(r["enabled"]),
            source=r["source"],
        ) for r in items]


@router.post("", dependencies=[Depends(verify_admin_key)])
async def upsert_rule(rule: PopupRuleWrite):
    """新增/更新一条弹窗规则。

    省略 id 时由数据库分配；带 id 时按 id 更新。规则内容实际变化才
    提升规则版本号（与变更同一事务），客户端据此增量同步。
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if rule.id is None:
            cur = await db.execute(
                "INSERT INTO popup_rules(package_name, button_text_regex, view_id_regex, enabled) "
                "VALUES(?, ?, ?, ?)",
                (rule.package_name, rule.button_text_regex,
                 rule.view_id_regex, int(rule.enabled)),
            )
            new_id = cur.lastrowid
            await _bump_version_in(db)
            changed = True
        else:
            row = await (await db.execute(
                "SELECT id, package_name, button_text_regex, view_id_regex, enabled "
                "FROM popup_rules WHERE id=?", (rule.id,)
            )).fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO popup_rules(id, package_name, button_text_regex, view_id_regex, enabled) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (rule.id, rule.package_name, rule.button_text_regex,
                     rule.view_id_regex, int(rule.enabled)),
                )
                changed = True
            else:
                changed = (
                    row["package_name"] != rule.package_name
                    or row["button_text_regex"] != rule.button_text_regex
                    or (row["view_id_regex"] or None) != rule.view_id_regex
                    or bool(row["enabled"]) != rule.enabled
                )
                if changed:
                    await db.execute(
                        "UPDATE popup_rules SET package_name=?, button_text_regex=?, "
                        "view_id_regex=?, enabled=? WHERE id=?",
                        (rule.package_name, rule.button_text_regex,
                         rule.view_id_regex, int(rule.enabled), rule.id),
                    )
            if changed:
                await _bump_version_in(db)
            new_id = rule.id
        await db.commit()
    return {"ok": True, "id": new_id, "changed": changed}


@router.delete("/{rule_id}", dependencies=[Depends(verify_admin_key)])
async def delete_rule(rule_id: int):
    """删除一条弹窗规则，并提升规则版本号。"""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM popup_rules WHERE id=?", (rule_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="rule not found")
        await _bump_version_in(db)
        await db.commit()
    return {"ok": True, "deleted": rule_id}
