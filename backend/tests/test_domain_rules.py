"""域名规范化与拦截列表解析的单元测试。"""
from app.domain_rules import normalize_domain, parse_adblock_line


def test_normalize_valid_domains():
    assert normalize_domain("Example.com") == "example.com"
    assert normalize_domain("  a.b.example.com  ") == "a.b.example.com"
    assert normalize_domain("example.com.") == "example.com"
    assert normalize_domain("xn--fiqs8s.com") == "xn--fiqs8s.com"


def test_normalize_invalid_domains():
    assert normalize_domain("") is None
    assert normalize_domain(None) is None
    assert normalize_domain("not a domain") is None
    assert normalize_domain("https://example.com") is None
    assert normalize_domain("*.example.com") is None
    assert normalize_domain("example.com/path") is None
    assert normalize_domain("example.com$third-party") is None
    assert normalize_domain("localhost") is None  # 无点，不进黑名单
    assert normalize_domain("a" * 254) is None


def test_parse_adblock_line_valid():
    assert parse_adblock_line("||example.com^") == "example.com"
    assert parse_adblock_line("0.0.0.0 example.com") == "example.com"
    assert parse_adblock_line("127.0.0.1 example.com") == "example.com"
    assert parse_adblock_line("example.com") == "example.com"
    assert parse_adblock_line("  ||sub.example.com^  ") == "sub.example.com"


def test_parse_adblock_line_skips():
    # 注释
    assert parse_adblock_line("! 注释") is None
    assert parse_adblock_line("# 注释") is None
    # 例外规则
    assert parse_adblock_line("@@||example.com^") is None
    # 路径 / 过滤选项 / 多规则 / 通配
    assert parse_adblock_line("||example.com/path^") is None
    assert parse_adblock_line("||example.com^$third-party") is None
    assert parse_adblock_line("||example.com,example2.com^") is None
    assert parse_adblock_line("||*.example.com^") is None
    assert parse_adblock_line("example.com##.banner") is None
