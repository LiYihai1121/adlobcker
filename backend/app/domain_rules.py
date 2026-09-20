"""广告域名规范化与拦截列表解析。

统一用于管理 API 与远程规则同步，保证入库条目都是可被 Android
AdDomainFilter 后缀匹配的纯域名，避免把例外、路径、过滤选项等
不可拦截的条目写入黑名单。
"""
import re

# 单标签：字母/数字/连字符/下划线（宽松），1-63 字符
_LABEL = r"[a-z0-9_-]{1,63}"
_DOMAIN_RE = re.compile(rf"^(?:{_LABEL}\.)+[a-z0-9_-]{{2,63}}$", re.IGNORECASE)

# 远程列表中的注释前缀（EasyList 风格）
_COMMENT_PREFIXES = ("!", "#", "[")
# hosts 风格前缀
_HOSTS_PREFIXES = ("0.0.0.0", "127.0.0.1", "::", "0")
# 需要跳过的片段（例外规则、路径、过滤选项、通配等；"||" 前缀先剥掉再判断）
_SKIP_MARKERS = ("@@", "/", "$", ",", "*", "=", "<", ">")


def normalize_domain(raw: str | None) -> str | None:
    """规范化一个纯域名：小写、去尾点、校验合法，非法返回 None。"""
    if not raw:
        return None
    d = raw.strip().strip(".").lower()
    if len(d) > 253:
        return None
    if not d or not _DOMAIN_RE.match(d):
        return None
    return d


def parse_adblock_line(line: str) -> str | None:
    """从远程拦截列表的一行解析出可拦截的纯域名。

    支持：纯域名、EasyList 的 ||domain^、hosts 风格的前缀行。
    跳过：注释、@@ 例外、含路径/过滤选项/通配/空白的多规则行。
    返回规范化域名，无法解析返回 None。
    """
    text = line.strip()
    if not text or text.startswith(_COMMENT_PREFIXES):
        return None
    if text.startswith("@@") or any(m in text for m in _SKIP_MARKERS):
        return None

    for prefix in _HOSTS_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            if text[len(prefix):len(prefix) + 1] in (" ", "\t"):
                text = text[len(prefix):].strip()
                break
    if text.startswith("||"):
        text = text[2:]
    if text.endswith("^"):
        text = text[:-1]

    # 仍可能带路径/选项/通配的条目在此兜底拒绝
    if any(m in text for m in ("/", "$", ",", "*", "|", " ", "\t")):
        return None
    return normalize_domain(text)
