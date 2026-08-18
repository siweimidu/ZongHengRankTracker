"""
ZongHengRankTracker —— 榜单注册表（单一事实源）

纵横中文网排行榜 (https://www.zongheng.com/rank) 的全部榜单。
数据接口（逆向自官网前端，纯 HTTP，无需浏览器）：

    POST https://www.zongheng.com/api/rank/details
    Content-Type: application/x-www-form-urlencoded

    cateFineId=<分类ID>   0 = 全部
    cateType=0
    pageNum=<页码>
    pageSize=<每页数量>   最大 200，可单请求拉全量
    period=<周期>         0=周榜 1=日榜 2=月榜（部分榜单无周期概念，传 0 即可）
    rankNo=<期号>         月票榜按月期号(如 20268)，留空自动取当期；新书榜按周
    rankType=<榜单类型>   见下方 BOARDS

爬虫、分析、构建脚本都从这里读取榜单列表。
"""

# ============================================================
#  指标语义：不同榜单的 number 字段含义不同，前端据此渲染
# ============================================================

METRIC_LABELS = {
    "monthly-ticket": "月票",
    "one-day": "24h销量",
    "new-book": "周收藏",
    "click": "点击",
    "recommend": "推荐",
    "claque": "捧场",
    "end": "阅读",
    "new-book-subscribe": "订阅",
    "one-day-update": "更新字数",
    "author-popularity": "人气",
}

# ============================================================
#  题材关键词：命中简介/书名即计入题材热度（趋势页使用）
# ============================================================

KEYWORDS = [
    "系统", "重生", "穿越", "无敌", "签到", "苟道", "种田", "无限流", "诸天", "万界",
    "都市", "异能", "兵王", "战神", "赘婿", "神医", "金融", "鉴宝", "美食", "直播",
    "玄幻", "修仙", "炼丹", "宗门", "废柴逆袭", "废土", "末世", "丧尸", "星际",
    "机甲", "科技", "工业", "国运", "历史", "争霸", "三国", "大明", "网游", "电竞",
    "克苏鲁", "灵异", "规则怪谈", "悬疑", "推理", "盗墓", "扮猪吃虎", "杀伐果断",
    "高武", "仙侠", "武侠", "脑洞", "群像", "轻松", "搞笑", "争霸流", "经营",
]

# ============================================================
#  榜单注册表
# ============================================================
#  字段：
#    slug       —— 英文短名，决定 data/<slug>/ 与 api/<slug>/
#    name       —— 中文榜单名（前端展示）
#    rankType   —— 官网 API 的榜单类型编号
#    period     —— 周期 (0 周榜 / 1 日榜 / 2 月榜)，与官网默认视图保持一致
#    extra      —— 附加参数（如月票榜 isNewBook / rankNo）
#    enabled    —— 是否参与抓取/构建
#    is_author  —— 是否作者榜（数据结构以作者为主）
#    desc       —— 一句话说明

BOARDS = [
    {
        "slug": "monthly-ticket",
        "name": "月票榜",
        "rankType": 1,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "读者真金白银投票，最能反映付费读者的忠诚度",
    },
    {
        "slug": "one-day",
        "name": "24小时畅销榜",
        "rankType": 3,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "最近 24 小时销售表现，捕捉即时市场热度",
    },
    {
        "slug": "new-book",
        "name": "新书榜",
        "rankType": 4,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "每周新书战场，发现下一批潜力作品的风向标",
    },
    {
        "slug": "click",
        "name": "点击榜",
        "rankType": 5,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "流量入口，反映新书引流与老书长尾效应",
    },
    {
        "slug": "recommend",
        "name": "推荐榜",
        "rankType": 6,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "读者主动推荐行为，衡量口碑传播力",
    },
    {
        "slug": "claque",
        "name": "捧场榜",
        "rankType": 7,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "打赏金额榜，观察核心粉丝的消费力",
    },
    {
        "slug": "end",
        "name": "完结榜",
        "rankType": 8,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "完本作品的长青指数，经典书的持久生命力",
    },
    {
        "slug": "new-book-subscribe",
        "name": "新书订阅榜",
        "rankType": 9,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "新书期订阅转化，判断商业化起步质量",
    },
    {
        "slug": "one-day-update",
        "name": "24小时更新榜",
        "rankType": 10,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": False,
        "desc": "按日更字数排序，观察勤更梯队与爆发更新",
    },
    {
        "slug": "author-popularity",
        "name": "作者人气榜",
        "rankType": 12,
        "period": 0,
        "extra": {},
        "enabled": True,
        "is_author": True,
        "no_categories": True,  # 该榜 API 不支持 cateFineId 过滤，仅抓「全部」
        "desc": "头部作者影响力榜，以代表作呈现",
    },
]


def enabled_boards():
    return [b for b in BOARDS if b.get("enabled")]


def get_board(slug: str):
    for b in BOARDS:
        if b["slug"] == slug:
            return b
    return None


def board_public_meta(board: dict) -> dict:
    return {
        "slug": board["slug"],
        "name": board["name"],
        "desc": board["desc"],
        "is_author": bool(board.get("is_author")),
        "metric_label": METRIC_LABELS.get(board["slug"], "数值"),
    }


# 连载状态映射（serialStatus 原始值 → 中文）
SERIAL_STATUS_MAP = {0: "连载中", 1: "已完结"}
