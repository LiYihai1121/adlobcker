"""Pydantic 响应/请求模型。"""
from pydantic import BaseModel, Field


class DomainItem(BaseModel):
    domain: str
    platform: str | None = None
    enabled: bool = True


class PopupRule(BaseModel):
    id: int
    package_name: str
    button_text_regex: str
    view_id_regex: str | None = None
    enabled: bool = True


class PopupRuleWrite(BaseModel):
    """弹窗规则写入模型：id 省略时由数据库自增分配，提供时按 id 更新。

    仅做结构与长度校验；正则文法以客户端 Android Java Pattern 为准，
    不在服务端用 Python 正则解析校验。
    """

    id: int | None = Field(default=None, ge=1)
    package_name: str = Field(
        min_length=1, max_length=255,
        pattern=r"^\*$|^[A-Za-z0-9_]+(\.[A-Za-z0-9_-]+)+$",
    )
    button_text_regex: str = Field(min_length=1, max_length=512)
    view_id_regex: str | None = Field(default=None, max_length=512)
    enabled: bool = True


class RulesVersion(BaseModel):
    rules_version: int
    domains_count: int
    popup_rules_count: int


class InterceptStat(BaseModel):
    device_id: str
    intercepted_domains: list[str] = []
    closed_popups: int = 0


class StatsSummary(BaseModel):
    device_id: str
    total_intercepted_domains: int
    total_closed_popups: int


class RulesSnapshot(BaseModel):
    """规则全量快照：一次请求返回版本号 + 域名列表 + 弹窗规则，供客户端整体同步。"""
    rules_version: int
    domains: list[DomainItem]
    popup_rules: list[PopupRule]


class StatsOverview(BaseModel):
    """全局拦截统计聚合（跨所有设备）。"""
    active_devices: int
    total_closed_popups: int
    unique_intercepted_domains: int


class TopDomain(BaseModel):
    """被拦截域名排行项。"""
    domain: str
    hits: int


class DailyStat(BaseModel):
    """单日拦截统计。"""
    day: str                    # YYYY-MM-DD（本地时区）
    closed_popups: int
    intercepted_requests: int   # 当日上报的域名命中次数（含重复域名）

