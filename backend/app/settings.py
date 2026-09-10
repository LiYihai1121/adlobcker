"""基于 Pydantic-Settings 的应用配置。

通过环境变量或 .env 文件覆盖默认值，便于在不同部署环境（开发/生产/Docker）间切换。
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """运行配置，字段名小写，对应环境变量同名（不区分大小写）。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # SQLite 数据库路径，默认放在 data/ 下
    db_path: str = Field(default=str(DATA_DIR / "adblock.db"))

    # 远程规则同步间隔（小时）
    sync_interval_hours: int = 6

    # CORS 允许的来源，生产环境建议收紧为客户端域名/IP
    cors_origins: list[str] = ["*"]

    # 是否在启动时立即执行一次远程同步
    sync_on_startup: bool = True

    # 管理接口密钥：为空表示不启用鉴权（仅本地开发）；生产环境务必设置
    admin_key: str | None = None


settings = Settings()
