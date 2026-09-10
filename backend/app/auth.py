"""管理接口鉴权：通过 X-Admin-Key 请求头保护写接口。

开发期不配置 admin_key 时默认放行（方便本地调试）；生产部署务必设置环境变量
ADBLOCK_ADMIN_KEY，否则写接口（新增/删除域名、改弹窗规则）将对外开放。
"""
from fastapi import Header, HTTPException

from app.settings import settings


async def verify_admin_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    """校验管理密钥。未配置密钥时直接放行；配置后必须匹配。"""
    if not settings.admin_key:
        return
    if x_admin_key != settings.admin_key:
        raise HTTPException(status_code=401, detail="invalid or missing admin key")
