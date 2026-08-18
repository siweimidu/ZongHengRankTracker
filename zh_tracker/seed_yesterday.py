"""
注入一份合成的“昨日”快照，用于在首日时也能展示趋势对比（仅用于演示）。
真实项目里次日 GitHub Actions 跑完后会自动有真实 prev。
"""
import json, os, random
from datetime import datetime, timedelta

BASE = r"C:\Users\35238\Desktop\七猫扫榜\ZongHengRankTracker"
DATA_DIR = os.path.join(BASE, "data")
YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
YDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

random.seed(42)

for slug in os.listdir(DATA_DIR):
    board_dir = os.path.join(DATA_DIR, slug)
    if not os.path.isdir(board_dir): continue
    snap_dir = os.path.join(board_dir, "snapshots")
    if not os.path.isdir(snap_dir): continue
    today_files = [f for f in os.listdir(snap_dir) if f.startswith("ranks_2")]
    if not today_files: continue
    today_path = os.path.join(snap_dir, today_files[0])
    with open(today_path, encoding="utf-8") as f: today = json.load(f)

    # 合成 yesterday：每分类保留 ~70% books，部分名次打乱
    yest = {"date": YDAY, "board": today["board"], "categories": []}
    for cat in today["categories"]:
        books = cat.get("books", [])
        if not books: continue
        # 留下 ~70% 当昨日，剩下的昨日书是今日新上榜
        keep_n = max(1, int(len(books) * 0.7))
        keep = books[:keep_n].copy()
        # 名次随机微调
        shuffled = keep[:]
        random.shuffle(shuffled)
        for i, b in enumerate(shuffled):
            b = dict(b)
            b["rank"] = i + 1
        yest["categories"].append({"id": cat["id"], "name": cat["name"], "books": shuffled})

    out = os.path.join(snap_dir, f"ranks_{YESTERDAY}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(yest, f, ensure_ascii=False, indent=1)
    print(f"seeded {slug} → {out} ({sum(len(c['books']) for c in yest['categories'])} books)")
