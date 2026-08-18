"""
AI 风向分析 —— OpenAI 兼容 API，按分类/全站生成趋势速评。

特性：
  * 标准 OpenAI Chat Completions 协议（Moonshot/DeepSeek/GLM/自建 均可）
  * 批量并发请求 + 单点失败不影响整体
  * 未配置 API 或调用失败时，自动回退到基于规则的高质量中文文案
  * 生成结果缓存，同日重跑不重复计费（--force 可强制重生成）
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

API_BASE_URL = os.environ.get("API_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("API_KEY", "")
API_MODEL = os.environ.get("API_MODEL", "gpt-4o-mini")

_client = None


def ai_available() -> bool:
    return bool(API_BASE_URL and API_KEY)


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY,
                         timeout=60, max_retries=2)
    return _client


def chat(prompt: str, max_tokens: int = 500) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model=API_MODEL,
        messages=[
            {"role": "system", "content": (
                "你是一位资深网文行业分析师，为纵横中文网榜单撰写趋势速评。"
                "要求：观点犀利、有数据支撑、给作者/编辑可执行的洞察；"
                "控制在 120 字以内；直接输出正文，不要客套。")},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def safe_chat(prompt: str, fallback: str) -> str:
    if not ai_available():
        return fallback
    try:
        out = chat(prompt)
        return out if out else fallback
    except Exception as e:  # noqa: BLE001
        print(f"  [AI] 调用失败，使用规则文案兜底：{str(e)[:120]}")
        return fallback


def rule_summary(board_name: str, cat_name: str, trend: dict) -> str:
    parts = []
    if trend.get("new_count"):
        parts.append(f"{trend['new_count']} 本新上榜")
    if trend.get("dropped_count"):
        parts.append(f"{trend['dropped_count']} 本掉榜")
    movers = trend.get("top_movers") or []
    if movers:
        m = movers[0]
        if m.get("rankChange", 0) > 0:
            parts.append(f"《{m['title']}》升 {m['rankChange']} 位至第 "
                         f"{m['rank']} 名")
    dark = trend.get("darkhorses") or []
    if dark:
        parts.append(f"黑马《{dark[0]['title']}》第 {dark[0]['rank']} 名")
    ur = trend.get("update_rate")
    if ur is not None and cat_name == "全部":
        parts.append(f"当日更新率 {int(ur * 100)}%")
    if not parts:
        parts.append("榜单结构稳定，头部固若金汤")
    return f"【{board_name}·{cat_name}】" + "；".join(parts) + "。"


def rule_brief(board_analyses: list) -> str:
    """全站日报的规则兜底版本。"""
    is_first_day = all(a.get("trends", {}).get("全部", {}).get("first_day")
                       for a in board_analyses if a)
    if is_first_day:
        total_books = sum(a.get("total_books", 0) for a in board_analyses if a)
        tops = []
        for a in board_analyses:
            if not a:
                continue
            bname = a.get("board", {}).get("name", "")
            top3 = (a.get("timeline", [{}])[-1].get("top3") or [])
            if top3:
                tops.append(f"{bname}《{top3[0]['title']}》")
        lines = [f"今日纵横 {len(board_analyses)} 个榜单共追踪 "
                 f"{total_books} 条记录。"]
        if tops:
            lines.append("各榜头名：" + "；".join(tops[:4]) + "。")
        lines.append("首日基线建立中，明日起出现新上榜/掉榜/黑马对比信号。")
        return "".join(lines)
    lines = []
    total_new = sum(a.get("trends", {}).get("全部", {}).get("new_count", 0)
                    for a in board_analyses if a)
    total_books = sum(a.get("total_books", 0) for a in board_analyses if a)
    lines.append(f"今日纵横 {len(board_analyses)} 个榜单共追踪 "
                 f"{total_books} 条记录，{total_new} 本新书完成卡位。")
    crossovers = []
    for a in board_analyses:
        if not a:
            continue
        allc = a.get("trends", {}).get("全部", {})
        dark = (allc.get("darkhorses") or [None])[0]
        if dark:
            crossovers.append(f"《{dark['title']}》冲上{a['board'].get('name', a.get('date', ''))}"
                              f"第 {dark['rank']} 名")
    if crossovers:
        lines.append("值得关注的黑马：" + "；".join(crossovers[:4]) + "。")
    lines.append("整体看，付费盘（月票/畅销）与流量盘（点击）的头部重合度，"
                 "决定了新书突围的最优路径。")
    return "".join(lines)


def build_ai_prompt(board_name: str, cat_name: str, cat: dict,
                    trend: dict) -> str:
    books = cat.get("books", [])[:15]
    lines = []
    for i, b in enumerate(books):
        lines.append(f"{i + 1}. 《{b['title']}》{b['author']} "
                     f"[{b.get('category', '?')}] "
                     f"{b.get('metricLabel', '')} {b.get('metric', 0)}"
                     f"{'（当日已更）' if b.get('updatedToday') else ''}")
    new_b = "、".join(f"《{n['title']}》(第{n['rank']}名)"
                      for n in trend.get("new_books", [])[:5]) or "无"
    drop_b = "、".join(f"《{d['title']}》"
                       for d in trend.get("dropped_books", [])[:5]) or "无"
    movers = trend.get("top_movers", [])[:5]
    move_b = "、".join(
        f"《{m['title']}》{'↑' if m['rankChange'] > 0 else '↓'}"
        f"{abs(m['rankChange'])}位" for m in movers) or "无明显变动"

    return f"""纵横中文网「{board_name} · {cat_name}」分类今日榜单：

{chr(10).join(lines)}

新上榜：{new_b}
掉榜：{drop_b}
名次变动：{move_b}

请输出一条 120 字以内的趋势速评：聚焦题材风向、黑马信号、竞争格局变化，
并给作者/编辑一条可执行建议。"""


def build_brief_prompt(board_analyses: list) -> str:
    sec = []
    for a in board_analyses:
        if not a:
            continue
        bname = a.get("board", {}).get("name", "")
        allc = a.get("trends", {}).get("全部", {})
        top3 = "、".join(f"《{b['title']}》"
                         for b in (a.get("timeline", [{}])[-1].get("top3")
                                   or []))
        heat = "、".join(f"{c['name']}({c['heat']})"
                         for c in (a.get("category_heat") or [])[:4])
        sec.append(
            f"【{bname}】Top3：{top3 or '无数据'}；"
            f"热点分类：{heat or '无'}；"
            f"新上榜 {allc.get('new_count', 0)} 本，"
            f"掉榜 {allc.get('dropped_count', 0)} 本")
    return f"""以下是纵横中文网今日各榜单摘要：

{chr(10).join(sec)}

请写一段 150 字以内的「今日网文风向日报」：
1) 用一句话概括大盘情绪；
2) 指出 1~2 个正在走强的题材赛道；
3) 点出 1~2 本值得关注的黑马及其信号；
4) 给写作者一条选题建议。"""


def summarize_board(board_name: str, snapshot_cat: dict, trend: dict,
                    cat_name: str) -> str:
    prompt = build_ai_prompt(board_name, cat_name, snapshot_cat, trend)
    return safe_chat(prompt, rule_summary(board_name, cat_name, trend))


def summarize_brief(board_analyses: list) -> str:
    prompt = build_brief_prompt(board_analyses)
    return safe_chat(prompt, rule_brief(board_analyses))


def parallel_summarize(jobs: list, max_workers: int = 4) -> dict:
    """jobs: [{'key', 'prompt', 'fallback'}] → {key: summary}"""
    results = {}

    def _run(job):
        return job["key"], safe_chat(job["prompt"], job["fallback"])

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for key, text in pool.map(_run, jobs):
            results[key] = text
    return results
