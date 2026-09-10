"""Pydantic 响应/请求模型。"""
from pydantic import BaseModel


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
