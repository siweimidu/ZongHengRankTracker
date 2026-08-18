#!/usr/bin/env python3
"""构建看板数据 + AI 分析 + 静态 API 的 CLI 入口（GitHub Actions 调用）。

用法：
  python scripts/build_latest.py            # 常规构建（AI 结果同日缓存）
  python scripts/build_latest.py --force    # 强制重新生成 AI 分析
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zh_tracker.build import main  # noqa: E402

if __name__ == "__main__":
    main()
