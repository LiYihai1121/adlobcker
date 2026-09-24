"""GKD 订阅（JSON5）→ 本项目弹窗规则的降级转换（轻量版）。

GKD 规则核心是 `matches` 选择器（属性 + 层级组合语法），表达能力远强于
本项目的（包名 + 文案正则 + viewId 正则）三元组。本模块只做**保守降级**：

- 仅转换不含层级组合符（@ > < + - 等）与多步 preKeys 的"平坦"选择器；
- 从选择器中提取 text/desc 字面量（= *= ^= $=）生成文案正则，
  提取 vid/id 字面量生成 viewId 正则；
- 其余结构性条件（text.length/width/clickable 等）直接忽略 —— 转换结果
  语义只会比原 GKD 规则**更宽松**（更多节点可能命中），因此同时跳过
  订阅中默认禁用的 app/分组/规则，把误点风险控制在合理范围。

转换产物：`[(package_name, button_text_regex, view_id_regex), ...]` 去重列表。
"""
from __future__ import annotations

import logging
import re

import pyjson5

logger = logging.getLogger("adblock.gkd")

# [attr op "literal"] 形式的属性条件（op: = *= ^= $=）
_COND_RE = re.compile(
    r'\[\s*(text|desc|vid|id)\s*(=|\*=|\^=|\$=)\s*"((?:[^"\\]|\\.)*)"\s*\]'
)
# 结构性组合符（在剥掉字符串字面量与方括号条件后检测，出现即放弃该分支）
_STRUCT_RE = re.compile(r"[@><+\-]|&&|\bparent\b|\bchildCount\b|\bindex\b")
# 用于 vid-only 规则的永不命中文案正则（空正则会被 Java 匹配一切，必须避免）
NEVER_MATCH = "a^"


def _unescape(lit: str) -> str:
    """还原选择器字符串字面量中的转义（\\" \\\\）。"""
    return lit.replace('\\"', '"').replace("\\\\", "\\")


def _strip_literals(s: str) -> str:
    """剥掉双引号字符串与 [...] 条件，剩下的才可能是组合符。"""
    s = re.sub(r'"(?:[^"\\]|\\.)*"', "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    return s


def _text_regex(conds: list[tuple[str, str, str]]) -> str | None:
    """从 text/desc 条件中选最长字面量生成文案正则。"""
    cands = [(op, _unescape(lit)) for attr, op, lit in conds if attr in ("text", "desc")]
    if not cands:
        return None
    op, lit = max(cands, key=lambda c: len(c[1]))
    if not lit:
        return None
    esc = re.escape(lit)
    return {"=": f"^{esc}$", "*=": esc, "^=": f"^{esc}", "$=": f"{esc}$"}[op]


def _vid_regex(conds: list[tuple[str, str, str]]) -> str | None:
    """从 vid/id 条件中选最长字面量生成 viewId 正则。

    Android viewIdResourceName 形如 com.pkg:id/iv_close，GKD 的 vid
    指 id 段本身，因此精确匹配锚定到 id 段末尾（(^|/)literal$）。
    """
    cands = [(attr, op, _unescape(lit)) for attr, op, lit in conds if attr in ("vid", "id")]
    if not cands:
        return None
    attr, op, lit = max(cands, key=lambda c: len(c[2]))
    if not lit:
        return None
    # id="com.pkg:id/iv_close" 时取 id 段；vid 本来就是 id 段
    seg = lit.rsplit("/", 1)[-1] if attr == "id" else lit
    esc = re.escape(seg)
    return {"=": f"(^|/){esc}$", "*=": esc, "^=": f"(^|/){esc}", "$=": f"{esc}$"}[op]


def _convert_selector(selector: str) -> tuple[str, str | None] | None:
    """转换单条选择器 → (文案正则, viewId正则)；不可转换返回 None。"""
    for part in selector.split("||"):
        part = part.strip()
        if not part or _STRUCT_RE.search(_strip_literals(part)):
            continue
        conds = _COND_RE.findall(part)
        if not conds:
            continue
        text_re = _text_regex(conds)
        vid_re = _vid_regex(conds)
        if text_re is None and vid_re is None:
            continue
        return (text_re or NEVER_MATCH), vid_re
    return None


def _rule_selectors(rule: dict) -> list[str]:
    """收集一条规则的候选选择器（matches / anyMatches）。"""
    out: list[str] = []
    for key in ("matches", "anyMatches"):
        value = rule.get(key)
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, list):
            out.extend(v for v in value if isinstance(v, str))
    return out


def convert_subscription(text: str) -> list[tuple[str, str, str | None]]:
    """解析 GKD 订阅 JSON5，降级转换为 (包名, 文案正则, viewId正则) 去重列表。"""
    sub = pyjson5.decode(text)
    seen: set[tuple[str, str, str | None]] = set()
    skipped = 0

    def add(package: str, selector: str) -> None:
        nonlocal skipped
        converted = _convert_selector(selector)
        if converted is None:
            skipped += 1
            return
        seen.add((package, converted[0], converted[1]))

    # 全局规则组（对所有应用生效 → 包名 *）
    for group in sub.get("globalGroups") or []:
        if group.get("enable") is False:
            continue
        for rule in group.get("rules") or []:
            if rule.get("enable") is False or rule.get("preKeys"):
                continue
            for sel in _rule_selectors(rule):
                add("*", sel)

    # 按应用分组规则
    for app in sub.get("apps") or []:
        package = app.get("id")
        if not package or app.get("enable") is False:
            continue
        for group in app.get("groups") or []:
            if group.get("enable") is False:
                continue
            for rule in group.get("rules") or []:
                if rule.get("enable") is False or rule.get("preKeys"):
                    continue
                for sel in _rule_selectors(rule):
                    add(package, sel)

    logger.info("GKD 订阅转换完成：%d 条规则入库，%d 条复杂选择器跳过",
                len(seen), skipped)
    return sorted(seen)
