"""
构建脚本 —— 汇总数据、生成趋势分析与静态 API。

对每个启用榜单：
  1. analyze_board 产出趋势分析（diff / 动能分 / 黑马 / 分类热度 / 题材热度）
  2. AI 生成分类速评（无 API 时规则兜底）
  3. 输出 data/<slug>/{latest_ranks,market_summary,dates}.json
     + data/<slug>/trends/YYYY-MM-DD.json
  4. 生成 api/ 静态接口（GitHub Pages 可直接 fetch）

全站级输出：
  * api/boards.json            榜单索引
  * api/cross-board.json       跨榜影响力 Top30（创新）
  * api/market-brief.json      AI 风向日报
"""
import argparse
import json
import os
import time
from datetime import datetime

from .ai import (ai_available, parallel_summarize, rule_brief,
                 rule_summary, summarize_brief)
from .analyze import analyze_board, cross_board_presence, latest_two
from .config import METRIC_LABELS, board_public_meta, enabled_boards

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
API_DIR = os.path.join(BASE_DIR, "api")


def write_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def safe_filename(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").strip() or "all"


def build_board(board: dict, force: bool = False) -> dict | None:
    slug = board["slug"]
    today, _ = latest_two(slug)
    if not today:
        print(f"  ⏭️  {board['name']}：无快照，跳过")
        return None

    analysis = analyze_board(slug)
    if not analysis:
        return None
    board_name = board["name"]

    # ---- AI 分类速评（同日缓存，--force 重生成）----
    summary_file = os.path.join(DATA_DIR, slug, "ai_cache",
                                f"{today['date']}.json")
    cached = read_json(summary_file) if not force else None
    jobs = []
    cat_lookup = {c["name"]: c for c in today.get("categories", [])}
    for cat_name, trend in analysis["trends"].items():
        if cached and cat_name in cached:
            trend["summary"] = cached[cat_name]
            continue
        cat_data = cat_lookup.get(cat_name, {"books": []})
        from .ai import build_ai_prompt
        jobs.append({
            "key": cat_name,
            "prompt": build_ai_prompt(board_name, cat_name, cat_data, trend),
            "fallback": rule_summary(board_name, cat_name, trend),
        })
    if jobs:
        t0 = time.time()
        results = parallel_summarize(jobs)
        for cat_name, text in results.items():
            analysis["trends"][cat_name]["summary"] = text
        merged = {**(cached or {}), **results}
        write_json(summary_file, merged)
        print(f"  [AI] {board_name} {len(results)} 条速评 "
              f"({'AI' if ai_available() else '规则'}生成，"
              f"{time.time() - t0:.1f}s)")

    # ---- 输出 data/ ----
    board_dir = os.path.join(DATA_DIR, slug)
    write_json(os.path.join(board_dir, "latest_ranks.json"), {
        "date": today["date"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "board": board_public_meta(board) | {
            "rankType": board["rankType"], "period": board.get("period", 0)},
        "categories": today["categories"],
        "analysis": analysis,
    })
    write_json(os.path.join(board_dir, "market_summary.json"), {
        "date": today["date"],
        "category_heat": analysis["category_heat"],
        "keyword_heat": analysis["keyword_heat"],
        "timeline": analysis["timeline"],
    })
    write_json(os.path.join(board_dir, "dates.json"), {
        "dates": [t["date"] for t in analysis["timeline"]],
    })
    write_json(os.path.join(board_dir, "trends", f"{today['date']}.json"),
               analysis)

    # ---- 输出 api/ ----
    api_board_dir = os.path.join(API_DIR, slug, "latest")
    write_json(os.path.join(API_DIR, slug, "latest.json"), {
        "slug": slug, "name": board_name, "date": today["date"],
        "types": [{"name": c["name"],
                   "url": f"api/{slug}/latest/{safe_filename(c['name'])}.json",
                   "count": len(c["books"])}
                  for c in today["categories"]],
    })
    write_json(os.path.join(api_board_dir, "all.json"), {
        "date": today["date"], "board": board_public_meta(board),
        "categories": today["categories"], "analysis": analysis,
    })
    for cat in today["categories"]:
        write_json(os.path.join(api_board_dir,
                                f"{safe_filename(cat['name'])}.json"), {
            "date": today["date"],
            "board": board_public_meta(board),
            "category": cat["name"],
            "books": cat["books"],
            "trend": analysis["trends"].get(cat["name"], {}),
        })

    print(f"  ✅ {board_name}：{len(today['categories'])} 分类已构建")
    return analysis


def build_all(force: bool = False) -> list:
    boards = enabled_boards()
    analyses = []
    for board in boards:
        try:
            a = build_board(board, force=force)
            if a:
                analyses.append(a)
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ {board['name']} 构建出错：{e}")

    # ---- 榜单索引 ----
    write_json(os.path.join(API_DIR, "boards.json"), {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "boards": [
            board_public_meta(b) | {
                "date": (latest_two(b["slug"])[0] or {}).get("date"),
                "url": f"api/{b['slug']}/latest/all.json",
            }
            for b in boards if latest_two(b["slug"])[0]
        ],
    })

    # ---- 跨榜影响力 ----
    try:
        write_json(os.path.join(API_DIR, "cross-board.json"), {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "top": cross_board_presence(),
        })
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ 跨榜影响力构建出错：{e}")

    # ---- AI 风向日报 ----
    brief_file = os.path.join(DATA_DIR, "market_brief.json")
    brief_date = (analyses[0]["date"] if analyses
                  else datetime.now().strftime("%Y-%m-%d"))
    old = read_json(brief_file) or {}
    brief = None
    if not force and old.get("date") == brief_date and old.get("brief"):
        brief = old["brief"]
    elif analyses:
        brief = summarize_brief(analyses)
    else:
        brief = rule_brief([])
    write_json(brief_file, {
        "date": brief_date,
        "engine": "AI" if ai_available() else "rule",
        "brief": brief,
    })
    write_json(os.path.join(API_DIR, "market-brief.json"), {
        "date": brief_date,
        "engine": "AI" if ai_available() else "rule",
        "brief": brief,
    })
    print(f"\n📝 风向日报（{brief_date}）：{brief[:80]}…")
    return analyses


def main():
    parser = argparse.ArgumentParser(
        description="构建 latest 数据 + AI 分析 + 静态 API")
    parser.add_argument("--force", action="store_true",
                        help="忽略 AI 缓存强制重新生成")
    args = parser.parse_args()
    print("开始构建看板数据…")
    build_all(force=args.force)
    print("\n✅ 构建完成。")


if __name__ == "__main__":
    main()
