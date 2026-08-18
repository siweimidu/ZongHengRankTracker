"""
趋势分析引擎 —— 对比相邻两日快照，产出多维趋势信号。

相对基础版（新上榜/掉榜/涨跌名次）的深度增强：
  1. 动能分 momentum —— 综合排名位置与名次/指标变化的 0~100 复合分
  2. 黑马检测 darkhorses —— 首次上榜即进入前列，或短期名次暴涨
  3. 更新活跃度 —— 当日更新率、勤更梯队
  4. 分类热度指数 —— 按上榜数量 + 头部占比计算各分类声量
  5. 题材关键词热度 —— 简介命中关键词的加权统计
"""
import json
import os
import re
from datetime import datetime

from .config import KEYWORDS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_snapshots(slug: str):
    """按日期升序返回该榜单全部快照。"""
    snap_dir = os.path.join(DATA_DIR, slug, "snapshots")
    if not os.path.isdir(snap_dir):
        return []
    out = []
    for fn in sorted(os.listdir(snap_dir)):
        if re.fullmatch(r"ranks_\d{8}\.json", fn):
            path = os.path.join(snap_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception:
                continue
    return out


def latest_two(slug: str):
    snaps = load_snapshots(slug)
    if not snaps:
        return None, None
    today = snaps[-1]
    prev = snaps[-2] if len(snaps) >= 2 else None
    return today, prev


def _cat_index(snapshot: dict):
    """分类名 → {bookId: book}"""
    idx = {}
    for cat in (snapshot or {}).get("categories", []):
        m = {}
        for i, b in enumerate(cat.get("books", [])):
            b = dict(b)
            b.setdefault("rank", i + 1)
            m[str(b.get("bookId"))] = b
        idx[cat["name"]] = m
    return idx


def momentum(rank: int, rank_change: int, metric_growth: float,
             top_n: int = 30) -> float:
    """
    动能分（0~100）：
      基础 = 排名位置分（越靠前越高，头部额外加成）
      加成 = 名次上升 + 指标增长（对数压缩，防止头部垄断）
    """
    base = max(0.0, (top_n - rank + 1) / top_n) * 60
    if rank <= 3:
        base += 8  # 前三甲额外曝光加成
    rank_bonus = min(20.0, max(0.0, rank_change) * 2.5)
    growth_bonus = min(20.0, (metric_growth ** 0.5) * 4 if metric_growth > 0
                       else 0)
    return round(min(100.0, base + rank_bonus + growth_bonus), 1)


def compare_category(today_books: list, prev_books: list | None,
                     top_n: int = 30) -> dict:
    """单分类两日对比。prev_books 为 None 表示首日无基线，
    此时新上榜/掉榜/黑马均不判定（无对比意义）。"""
    has_baseline = prev_books is not None
    today_map = {str(b["bookId"]): b for b in today_books}
    prev_map = {str(b["bookId"]): b for b in prev_books} if prev_books else {}

    new_books, dropped_books, movers = [], [], []
    for bid, b in today_map.items():
        if has_baseline and bid not in prev_map:
            new_books.append({"title": b["title"], "author": b["author"],
                              "rank": b["rank"], "bookId": b["bookId"]})
        elif bid in prev_map:
            p = prev_map[bid]
            change = p["rank"] - b["rank"]  # 正 = 上升
            mg = 0.0
            if p.get("metric", 0) > 0:
                mg = (b.get("metric", 0) - p["metric"]) / max(p["metric"], 1)
            if change != 0 or abs(mg) > 0.001:
                movers.append({
                    "bookId": b["bookId"], "title": b["title"],
                    "author": b["author"], "rank": b["rank"],
                    "rankChange": change,
                    "metric": b.get("metric", 0),
                    "metricGrowth": round(mg, 4),
                    "momentum": momentum(b["rank"], change, mg, top_n),
                })
    for bid, p in prev_map.items():
        if has_baseline and bid not in today_map:
            dropped_books.append({"title": p["title"], "author": p["author"],
                                  "prevRank": p["rank"],
                                  "bookId": p["bookId"]})

    new_books.sort(key=lambda x: x["rank"])
    dropped_books.sort(key=lambda x: x["prevRank"])
    movers.sort(key=lambda x: -x["momentum"])

    # 黑马：首次上榜且进入前 15，或一日内上升 ≥ 8 位
    darkhorses = [
        {"bookId": n["bookId"], "title": n["title"], "author": n["author"],
         "rank": n["rank"], "reason": "新上榜即进入前列"}
        for n in new_books if n["rank"] <= 15
    ]
    darkhorses += [
        {"bookId": m["bookId"],
         "title": m["title"], "author": m["author"], "rank": m["rank"],
         "reason": f"一日上升 {m['rankChange']} 位"}
        for m in movers if m["rankChange"] >= 8
    ]
    seen, uniq_dark = set(), []
    for d in darkhorses:
        if d["bookId"] in seen:
            continue
        seen.add(d["bookId"])
        uniq_dark.append(d)
    uniq_dark.sort(key=lambda x: x["rank"])

    updated = sum(1 for b in today_books if b.get("updatedToday"))

    return {
        "first_day": not has_baseline,
        "new_count": len(new_books),
        "dropped_count": len(dropped_books),
        "new_books": new_books[:6],
        "dropped_books": dropped_books[:6],
        "top_movers": movers[:8],
        "darkhorses": uniq_dark[:5],
        "update_rate": round(updated / len(today_books), 3)
        if today_books else 0,
        "summary": "",  # AI 填充
    }


def analyze_board(slug: str, top_n: int = 30) -> dict | None:
    """对一个榜单产出完整趋势分析（含全历史日期序列）。"""
    today, prev = latest_two(slug)
    if not today:
        return None
    today_idx = _cat_index(today)
    prev_idx = _cat_index(prev) if prev else {}

    trends = {}
    for cname, tmap in today_idx.items():
        trends[cname] = compare_category(
            [tmap[k] for k in sorted(tmap, key=lambda k: tmap[k]["rank"])],
            [prev_idx[cname][k] for k in
             sorted(prev_idx.get(cname, {}), key=lambda k: prev_idx[cname][k]["rank"])]
            if cname in prev_idx else None,
            top_n,
        )

    # 分类热度指数：Top10 数量 60% + 该分类 Top10 指标对数压缩 40%
    # 这样既能反映头部数量，又能区分相同规模下头部作品强度
    all_cat = today_idx.get("全部", {})
    cat_heat = []
    for cname, tmap in today_idx.items():
        if cname == "全部":
            continue
        top10_books = [b for b in tmap.values() if b["rank"] <= 10]
        metric_sum = sum(b.get("metric", 0) for b in top10_books)
        import math
        metric_log = math.log10(metric_sum + 1) if metric_sum > 0 else 0
        cat_heat.append({
            "name": cname, "count": len(tmap), "top10": len(top10_books),
            "metric_sum_top10": metric_sum,
            "heat": round(len(top10_books) * 4 + metric_log * 18, 1),
        })
    cat_heat.sort(key=lambda x: -x["heat"])

    # 题材关键词热度（简介 + 书名命中）
    kw_count = {}
    for b in all_cat.values():
        text = f"{b.get('title', '')} {b.get('intro', '')}"
        for kw in KEYWORDS:
            if kw in text:
                kw_count[kw] = kw_count.get(kw, 0) + 1
    keyword_heat = sorted(
        ({"keyword": k, "count": v} for k, v in kw_count.items()),
        key=lambda x: -x["count"])[:15]

    # 历史日期序列（「全部」分类 Top10 标题，供趋势页时间轴）
    snaps = load_snapshots(slug)
    timeline = []
    for s in snaps:
        allc = next((c for c in s.get("categories", [])
                     if c["name"] == "全部"), None)
        timeline.append({
            "date": s.get("date"),
            "top3": [{"title": b["title"], "author": b["author"],
                      "bookId": b["bookId"]} for b in
                     (allc["books"][:3] if allc else [])],
        })

    return {
        "date": today.get("date"),
        "prev_date": prev.get("date") if prev else None,
        "board": today.get("board", {}),
        "trends": trends,
        "category_heat": cat_heat,
        "keyword_heat": keyword_heat,
        "timeline": timeline,
        "total_books": len(all_cat),
    }


def cross_board_presence() -> list:
    """跨榜影响力：同一本书在多少个榜单出现，按上榜数 + 最好名次排序。"""
    from .config import enabled_boards
    presence = {}
    for board in enabled_boards():
        today, _ = latest_two(board["slug"])
        if not today:
            continue
        for cat in today.get("categories", []):
            if cat["name"] != "全部":
                continue
            for b in cat.get("books", []):
                key = str(b["bookId"])
                p = presence.setdefault(key, {
                    "bookId": b["bookId"], "title": b["title"],
                    "author": b["author"], "cover": b.get("cover", ""),
                    "category": b.get("category", ""),
                    "boards": [], "best_rank": 999,
                })
                p["boards"].append({"board": board["slug"],
                                    "name": board["name"],
                                    "rank": b["rank"]})
                p["best_rank"] = min(p["best_rank"], b["rank"])
    out = list(presence.values())
    for p in out:
        # 影响力分 = 上榜数×25 + (31-最好名次)，前 3 名额外 +10
        score = len(p["boards"]) * 25 + max(0, 31 - p["best_rank"])
        if p["best_rank"] <= 3:
            score += 10
        p["score"] = score
    out.sort(key=lambda x: -x["score"])
    return out[:30]
