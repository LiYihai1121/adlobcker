"""应用配置：常量定义 + 对 Settings 的再导出。"""
from app.settings import settings

# 数据库路径（向后兼容：原有模块 `from app.config import DB_PATH`）
DB_PATH = settings.db_path

# 远程规则源（公开的广告域名拦截列表，调度器定期同步）
REMOTE_DOMAIN_SOURCES = [
    # 国内常见广告 SDK 域名（穿山甲、优量汇、快手联盟、百青藤等）
    "https://raw.githubusercontent.com/cjx82630/cjxlist/master/cjx-annoyance.txt",
]

# 内置的国内主流广告 SDK 域名种子库（用于首次启动初始化）
BUILTIN_AD_DOMAINS: list[str] = [
    # 穿山甲（字节跳动）
    "pangolin-sdk.com",
    "pangolin.snssdk.com",
    "sf3-fe-tos.pglstatp.com",
    "ad.toutiao.com",
    "is.snssdk.com",
    "ad.oceanengine.com",
    "log.snssdk.com",
    "ad.tiktok.com",
    # 优量汇（腾讯广告）
    "gdt.qq.com",
    "mi.gdt.qq.com",
    "win.gdt.qq.com",
    "t.gdt.qq.com",
    "pgdt.3g.qq.com",
    "adqq.com",
    "qzs.qq.com",
    # 快手联盟
    "e.kuaishou.com",
    "ssp.ksadx.com",
    "p.kuaishou.com",
    "adsdk.ksadx.com",
    # 百青藤（百度联盟）
    "pos.baidu.com",
    "cpro.baidu.com",
    "mobads.baidu.com",
    "afd.baidu.com",
    # 其它常见广告/统计联盟
    "adview.cn",
    "admaster.com.cn",
    "adcdn.com",
    "domob.cn",
    "domob.org",
    "inmobi.com",
    "inmobisdk.com",
    "miaozhen.com",
    "irs01.com",
    "umeng.com",
    "umeng.co",
    "umengcloud.com",
    "youmi.net",
    "adcdn.com.cn",
    "dianru.com",
    "madhouse.cn",
    "mediav.com",
    "mwad.com",
    "ad-servers.com",
    "adsame.com",
    "yoyi.com.cn",
    "iyioyo.com",
    "tanx.com",
    "amap.com",
    "dianru.cn",
]

# 弹窗关闭按钮的通用文案正则（中文 APP 常见"跳过/关闭/广告"等）
BUILTIN_POPUP_RULES: list[dict] = [
    {"id": 1, "package_name": "*", "button_text_regex": "跳过|跳过广告|跳过 ?\\d+|跳过 ?\\d+s", "view_id_regex": "skip", "enabled": True},
    {"id": 2, "package_name": "*", "button_text_regex": "关闭|✕|×|关闭广告|不再显示", "view_id_regex": "close|dismiss|cancel", "enabled": True},
    {"id": 3, "package_name": "*", "button_text_regex": "跳过.*", "view_id_regex": "splash_skip", "enabled": True},
    {"id": 4, "package_name": "*", "button_text_regex": "我知道了|立即体验|知道了", "view_id_regex": "confirm|ok", "enabled": True},
]
