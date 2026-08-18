"""
纵横榜单抓取器 —— 多榜单并发版。

流程（每个榜单）：
  1. 拉取「全部」维度完整榜单（单请求 pageSize=200）
  2. 从数据中自动发现分类（比页面导航更全，含游戏/N次元等隐藏分类）
  3. 逐分类抓取 Top N（默认 30）
  4. 清洗 + 结构校验后增量写入 data/<slug>/snapshots/ranks_YYYYMMDD.json

工程质量：
  * 每榜单独立的 task_state 支持中断续跑
  * 空结果分类自动降级跳过（某些榜单无分类维度）
  * 全程限速 + 重试，绝不硬打对方接口
  * 抓取完成后输出健康报告
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .api import (ZongHengClient, clean_book, discover_categories)
from .config import METRIC_LABELS, enabled_boards

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

TOP_N = 30


def _write_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def scrape_board(board: dict, client: ZongHengClient, top_n: int = TOP_N,
                 sleep_sec: float = 1.0) -> dict:
    """抓取单个榜单，返回健康报告。"""
    slug = board["slug"]
    date_str = datetime.now().strftime("%Y%m%d")
    snap_dir = os.path.join(DATA_DIR, slug, "snapshots")
    output_file = os.path.join(snap_dir, f"ranks_{date_str}.json")
    state_file = os.path.join(DATA_DIR, slug, f"task_state_{date_str}.json")
    metric_label = METRIC_LABELS.get(slug, "数值")

    report = {"slug": slug, "name": board["name"], "ok": False,
              "categories": 0, "books": 0, "warnings": []}

    # ---- 续跑状态 ----
    state = _read_json(state_file) or {"completed": [], "snapshot": None}
    snapshot = state.get("snapshot")
    if not snapshot:
        snapshot = {"date": datetime.now().strftime("%Y-%m-%d"),
                    "board": {"slug": slug, "name": board["name"],
                              "rankType": board["rankType"],
                              "period": board.get("period", 0)},
                    "categories": []}
    completed = {c["name"] for c in snapshot["categories"]}

    print(f"\n{'=' * 56}\n[榜单] {board['name']} ({slug}) rankType={board['rankType']}\n{'=' * 56}")

    # ---- 第 1 步：全部维度 + 分类发现 ----
    all_cat = {"id": 0, "name": "全部", "books": []}
    if "全部" not in completed:
        full = client.fetch_full(board["rankType"],
                                 period=board.get("period", 0),
                                 extra=board.get("extra") or None)
        all_cat["books"] = [clean_book(b, i + 1, metric_label)
                            for i, b in enumerate(full[:top_n])]
        snapshot["categories"].append(all_cat)
        completed.add("全部")
        _write_json(output_file, snapshot)
        _write_json(state_file, {"completed": list(completed),
                                 "snapshot": snapshot})
        print(f"  [全部] 抓取 {len(all_cat['books'])} 本")
        time.sleep(sleep_sec)
    else:
        for c in snapshot["categories"]:
            if c["name"] == "全部":
                all_cat = c
                break

    # ---- 第 2 步：自动发现分类（基于全量数据，含隐藏分类） ----
    source_books = all_cat.get("books") or []
    if not source_books and snapshot["categories"]:
        for c in snapshot["categories"]:
            if c["name"] == "全部":
                source_books = c["books"]
    categories = _read_json(os.path.join(DATA_DIR, slug,
                                         "discovered_categories.json")) or []
    if not categories:
        # 若快照里「全部」被截断过，用最近一次发现的分类兜底
        categories = discover_categories(
            [{"cateFineId": b["cateFineId"], "cateFineName": b["category"]}
             for b in source_books]) if source_books else []
        # 「全部」Top30 可能覆盖不全，补充已知核心分类
        known_ids = {c["id"] for c in categories}
        for cid, name in [(8101, "玄幻奇幻"), (8102, "武侠仙侠"),
                          (8103, "都市"), (8104, "历史"), (8105, "科幻"),
                          (8106, "奇闻异事"), (8107, "游戏"),
                          (8108, "N次元"), (8109, "现实题材")]:
            if cid not in known_ids:
                categories.append({"id": cid, "name": name, "count": 0})
        _write_json(os.path.join(DATA_DIR, slug, "discovered_categories.json"),
                    categories)

    # ---- 第 3 步：逐分类 Top N ----
    for cat in categories:
        cname = cat["name"]
        if cname in completed:
            continue
        cid = cat["id"]
        try:
            raw = client.fetch_top(board["rankType"], cate_fine_id=cid,
                                   limit=top_n,
                                   period=board.get("period", 0),
                                   extra=board.get("extra") or None)
        except RuntimeError as e:
            report["warnings"].append(f"{cname}: {str(e)[:100]}")
            print(f"  [分类] {cname} 抓取失败：{str(e)[:100]}，跳过")
            continue
        books = [clean_book(b, i + 1, metric_label)
                 for i, b in enumerate(raw[:top_n])]
        if not books:
            # 分类在该榜单无数据（正常，如作者榜无分类），记录空但不报错
            snapshot["categories"].append({"id": cid, "name": cname,
                                           "books": []})
            completed.add(cname)
            _write_json(output_file, snapshot)
            _write_json(state_file, {"completed": list(completed),
                                     "snapshot": snapshot})
            continue
        snapshot["categories"].append({"id": cid, "name": cname,
                                       "books": books})
        completed.add(cname)
        _write_json(output_file, snapshot)
        _write_json(state_file, {"completed": list(completed),
                                 "snapshot": snapshot})
        print(f"  [分类] {cname} Top {len(books)} 已存档")
        time.sleep(sleep_sec)

    # ---- 收尾 ----
    live_cats = [c for c in snapshot["categories"] if c["books"]]
    report["ok"] = bool(live_cats)
    report["categories"] = len(live_cats)
    report["books"] = sum(len(c["books"]) for c in live_cats)
    if report["ok"]:
        try:
            os.remove(state_file)
        except OSError:
            pass
    print(f"  ✅ {board['name']} 完成：{report['categories']} 个有效分类，"
          f"共 {report['books']} 条记录")
    return report


def run_scraper(top_n: int = TOP_N, sleep_sec: float = 1.0,
                max_workers: int = 3, only: list | None = None):
    os.makedirs(DATA_DIR, exist_ok=True)
    boards = enabled_boards()
    if only:
        boards = [b for b in boards if b["slug"] in only]
    if not boards:
        print("⚠️  没有启用的榜单。")
        return []

    print(f"开始抓取 {len(boards)} 个榜单（每分类 Top {top_n}，"
          f"并发 {max_workers}）")
    started = time.time()
    client = ZongHengClient()

    reports = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(scrape_board, b, client, top_n, sleep_sec): b
                   for b in boards}
        for fut in as_completed(futures):
            b = futures[fut]
            try:
                reports.append(fut.result())
            except Exception as e:  # noqa: BLE001
                print(f"  ❌ 榜单 {b['name']} 致命错误：{e}")
                reports.append({"slug": b["slug"], "name": b["name"],
                                "ok": False, "categories": 0, "books": 0,
                                "warnings": [str(e)[:200]]})

    client.close()
    elapsed = time.time() - started

    # ---- 健康报告 ----
    print(f"\n{'=' * 56}\n抓取健康报告（耗时 {elapsed:.0f}s，"
          f"{client.stats['requests']} 次请求，"
          f"重试 {client.stats['retries']} 次）\n{'=' * 56}")
    for r in reports:
        flag = "✅" if r["ok"] else "❌"
        warn = f" ⚠️ {len(r['warnings'])} warnings" if r["warnings"] else ""
        print(f"  {flag} {r['name']}: {r['categories']} 分类 / "
              f"{r['books']} 条{warn}")
    _write_json(os.path.join(DATA_DIR, "last_run.json"), {
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_sec": round(elapsed, 1),
        "client_stats": client.stats,
        "reports": reports,
    })
    return reports


if __name__ == "__main__":
    run_scraper()
