"""
纵横排行榜 HTTP 客户端 —— 纯 requests 实现，无需浏览器。

特性：
  * 指数退避重试 + 抖动
  * 令牌桶限速，避免触发风控
  * 会话复用（Connection keep-alive）
  * 响应结构校验，坏数据直接判失败进入重试
"""
import json
import random
import threading
import time
from datetime import datetime

import requests

API_URL = "https://www.zongheng.com/api/rank/details"

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Origin": "https://www.zongheng.com",
    "Referer": "https://www.zongheng.com/rank",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}


class RateLimiter:
    """简单令牌桶：最少间隔 min_interval 秒放行一次，线程安全。"""

    def __init__(self, min_interval: float = 0.6):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            gap = now - self._last
            if gap < self.min_interval:
                sleep = self.min_interval - gap
            else:
                sleep = 0
            self._last = now + sleep if sleep else now
        if sleep > 0:
            time.sleep(sleep)


class ZongHengClient:
    def __init__(self, min_interval: float = 0.6, max_retries: int = 4,
                 timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.limiter = RateLimiter(min_interval)
        self.max_retries = max_retries
        self.timeout = timeout
        self.stats = {"requests": 0, "retries": 0, "failures": 0}

    def fetch_rank_page(self, rank_type: int, cate_fine_id: int = 0,
                        period: int = 0, page_num: int = 1, page_size: int = 30,
                        extra: dict | None = None) -> dict:
        """请求一页榜单。返回 result 字典；失败抛 RuntimeError。"""
        payload = {
            "cateFineId": cate_fine_id,
            "cateType": 0,
            "pageNum": page_num,
            "pageSize": page_size,
            "period": period,
            "rankNo": "",
            "rankType": rank_type,
        }
        if extra:
            payload.update(extra)

        last_err = None
        for attempt in range(1, self.max_retries + 1):
            self.limiter.wait()
            self.stats["requests"] += 1
            try:
                resp = self.session.post(API_URL, data=payload,
                                         timeout=self.timeout)
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                data = resp.json()
                if data.get("code") != 0 or "result" not in data:
                    raise RuntimeError(f"bad payload: {str(data)[:120]}")
                result = data["result"]
                if "resultList" not in result:
                    raise RuntimeError("missing resultList")
                return result
            except Exception as e:  # noqa: BLE001
                last_err = e
                self.stats["retries"] += 1
                # 指数退避 + 抖动：1s, 2s, 4s, 8s ± 30%
                backoff = (2 ** (attempt - 1)) * (1 + random.uniform(-0.3, 0.3))
                time.sleep(max(0.3, backoff))
        self.stats["failures"] += 1
        raise RuntimeError(
            f"rank/details rankType={rank_type} cate={cate_fine_id} "
            f"page={page_num} failed after {self.max_retries} tries: {last_err}")

    def fetch_top(self, rank_type: int, cate_fine_id: int = 0, limit: int = 30,
                  period: int = 0, extra: dict | None = None) -> list:
        """抓取某榜单某分类的 Top N（单请求优先，必要时翻页）。"""
        result = self.fetch_rank_page(rank_type, cate_fine_id=cate_fine_id,
                                      period=period, page_num=1,
                                      page_size=limit, extra=extra)
        books = result.get("resultList") or []
        if len(books) < limit:
            total = result.get("rankCount") or len(books)
            remaining = min(limit, total) - len(books)
            page = 2
            while remaining > 0:
                nxt = self.fetch_rank_page(rank_type,
                                           cate_fine_id=cate_fine_id,
                                           period=period, page_num=page,
                                           page_size=min(50, remaining),
                                           extra=extra)
                chunk = nxt.get("resultList") or []
                if not chunk:
                    break
                books.extend(chunk)
                remaining -= len(chunk)
                page += 1
        return books[:limit]

    def fetch_full(self, rank_type: int, period: int = 0,
                   extra: dict | None = None) -> list:
        """拉取「全部」维度的完整榜单（最多 200），用于自动发现分类。"""
        result = self.fetch_rank_page(rank_type, period=period, page_num=1,
                                      page_size=200, extra=extra)
        return result.get("resultList") or []

    def close(self):
        self.session.close()


def discover_categories(books: list) -> list:
    """从「全部」榜单数据中自动发现全部分类（id + name），按上榜数量排序。"""
    counter = {}
    for b in books:
        cid = b.get("cateFineId")
        name = (b.get("cateFineName") or "").strip()
        if not cid or not name:
            continue
        counter.setdefault(cid, {"id": cid, "name": name, "count": 0})
        counter[cid]["count"] += 1
    cats = sorted(counter.values(), key=lambda x: -x["count"])
    return cats


def clean_book(b: dict, rank: int, metric_label: str) -> dict:
    """清洗单本书/作者数据为统一 schema。"""
    book_id = b.get("bookId") or 0
    latest_time = (b.get("latestChapterTime") or "").strip()
    today = datetime.now().strftime("%m-%d")
    return {
        "rank": rank,
        "bookId": book_id,
        "title": (b.get("bookName") or "").strip(),
        "author": (b.get("pseudonym") or "").strip(),
        "authorId": b.get("authorId") or 0,
        "authorCover": (b.get("authorCover") or "").strip(),
        "cover": (b.get("bookCover") or "").strip(),
        "category": (b.get("cateFineName") or "").strip(),
        "cateFineId": b.get("cateFineId") or 0,
        "metric": b.get("number") or 0,          # 榜单核心指标（月票/点击…）
        "metricLabel": metric_label,
        "serialStatus": b.get("serialStatus"),   # 原始值，前端映射
        "intro": (b.get("description") or "").strip().replace("\n", " "),
        "latestChapter": (b.get("latestChapterName") or "").strip(),
        "latestChapterTime": latest_time,
        "updatedToday": latest_time.startswith(today),
        "url": f"https://www.zongheng.com/book/{book_id}.html",
    }
