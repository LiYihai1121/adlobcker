"""基于 Pydantic-Settings 的应用配置。

通过环境变量或 .env 文件覆盖默认值，便于在不同部署环境（开发/生产/Docker）间切换。
"""
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """运行配置；ADBLOCK_* 为推荐名称，保留历史字段名环境变量兼容。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False,
        populate_by_name=True,
    )

    db_path: str = Field(
        default=str(DATA_DIR / "adblock.db"),
        validation_alias=AliasChoices("ADBLOCK_DB_PATH", "DB_PATH"),
    )
    sync_interval_hours: int = Field(default=6, ge=1)
    cors_origins: list[str] = ["*"]
    sync_on_startup: bool = True
    admin_key: str | None = Field(
        default=None, validation_alias=AliasChoices("ADBLOCK_ADMIN_KEY", "ADMIN_KEY"),
    )
    environment: Literal["development", "production"] = Field(
        default="development", validation_alias="ADBLOCK_ENVIRONMENT",
    )

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.admin_key is not None:
            self.admin_key = self.admin_key.strip() or None
        if self.environment == "production" and not self.admin_key:
            raise ValueError("ADBLOCK_ADMIN_KEY must be set in production")
        return self


settings = Settings()
