# 🏆 纵横风向标 · ZongHeng Rank Tracker

> 📚 追踪**纵横中文网全部排行榜**（月票榜 / 24小时畅销榜 / 新书榜 / 点击榜 / 推荐榜 / 捧场榜 / 完结榜 / 新书订阅榜 / 24小时更新榜 / 作者人气榜），每日自动抓取各分类 Top 30 并结合 AI 生成趋势分析，部署为精美的在线看板。

**在线看板**：`https://siweimidu.github.io/ZongHengRankTracker/`

---

## ✨ 功能概览

| 功能 | 说明 |
|------|------|
| ⚡ 纯 HTTP 爬取 | 逆向官网 `/api/rank/details` 接口，**无需浏览器**，10 个榜单全量抓取仅 ~80 秒（传统 Playwright 方案需数分钟） |
| 🔍 分类自动发现 | 分类不是硬编码 —— 从全量榜单数据中自动发现（比页面导航更全，含游戏 / N次元 / 现代言情等隐藏分类） |
| 📊 十榜全覆盖 | 纵横官网 rank 页全部 10 个榜单逐一注册，每分类追踪 Top 30 |
| 🧠 深度趋势引擎 | 新上榜 / 掉榜 / 名次变动之外，自研 **动能分 momentum**（排名×涨幅复合分）、**黑马检测**、**当日更新率** |
| 🌐 跨榜影响力 | 创新指标：同一作品在多少个榜单同时出现，加权计算全站影响力分 |
| 🤖 AI 风向日报 | 接入 OpenAI 兼容 API，生成全站风向日报 + 每分类趋势速评；未配置时自动规则兜底 |
| 🎨 商务玻璃看板 | 液态玻璃 + 商务蓝金设计语言，弹性动效、打字机日报、SVG 图标（零颜文字） |
| 📈 可视化趋势 | ECharts 分类热度 / 题材关键词 / 榜首时间轴 |
| 🔌 静态数据接口 | `api/` 目录标准 JSON，GitHub Pages 直接可读，二次开发友好 |
| ⚙️ 全自动化 | GitHub Actions 每日定时抓取 + 构建 + 部署，零服务器运维 |

---

## 🚀 食用指南（三分钟上线）

### 前置条件

- 一个 GitHub 账号（本地开发才需要 Python 3.10+ 和 Git）

### 第一步：Fork 仓库

点击 [ZongHengRankTracker](https://github.com/siweimidu/ZongHengRankTracker) 页面右上角 **Fork** 按钮。

### 第二步：开启 GitHub Pages

1. 进入你 Fork 后的仓库 → **Settings** → **Pages**
2. **Source** 选择 **Deploy from a branch**（首次可先由 Actions 自动开启，也可以直接选）
3. Branch 选 `main`，目录 `/ (root)`，点击 **Save**

稍等几分钟，看板上线：`https://<你的用户名>.github.io/ZongHengRankTracker/`

### 第三步：配置 AI 分析（可选）

进入仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**：

| Secret 名称 | 说明 | 示例 |
|---|---|---|
| `API_BASE_URL` | OpenAI 兼容 API 地址 | `https://api.openai.com/v1` |
| `API_KEY` | API 密钥 | `sk-xxxxxxxx` |
| `API_MODEL` | 模型名称 | `gpt-4o-mini` / `deepseek-chat` / `moonshot-v1-8k` 均可 |

> 💡 任何 OpenAI 兼容接口都能用（DeepSeek / Moonshot / 智谱 / 自建网关）。不配置则自动使用基于规则的高质量中文文案，**核心功能完全不受影响**。

### 第四步：手动触发首次运行

1. 仓库 → **Actions** → 左侧选 **Daily ZongHeng Rank Scraper**
2. 点右上角 **Run workflow** → **Run workflow**
3. 等待约 2–3 分钟完成，`data/` 与 `api/` 会自动生成并提交

打开 Pages 链接即可看到看板。之后每天 **UTC 20:07（北京时间次日 04:07）** 自动更新，无需任何手动操作。

### 想立刻看到趋势对比？

趋势信号（新上榜 / 黑马 / 动能分）需要**至少两天快照**。可以在 Actions 里手动 **Run workflow** 两次（中间隔一天），或者本地先跑两天。首日看板会显示「首日基线采集中」。

---

## 🖥️ 看板功能导览

- **榜单看板**（`index.html`）：10 个榜单 Tab 一键切换 · 分类 chips · 搜索 · 名次/热度排序 · 卡片/列表双视图 · 黑马区 · 跨榜影响力 Top15
- **风向趋势**（`trend.html`）：分类热度指数（Top10 数量 + 头部强度对数加权）· 高频题材关键词 · 榜首时间轴 · 黑马信号
- **作品情报**（`book.html`）：点击任意书籍卡片，查看该书**跨榜表现**（在各榜的名次 / 指标 / 更新状态）与原著直链

---

## 🔌 最新数据接口

静态 JSON 接口随每次构建更新，GitHub Pages 直接可访问：

| 类型 | 路径 | 说明 |
|---|---|---|
| 榜单索引 | `api/boards.json` | 所有榜单 slug / 名称 / 最新日期 |
| 全站风向日报 | `api/market-brief.json` | AI（或规则）生成的当日风向日报 |
| 跨榜影响力 | `api/cross-board.json` | 全站 Top30 影响力作品 |
| 榜单类型索引 | `api/<slug>/latest.json` | 该榜所有分类及 URL |
| 全量数据 | `api/<slug>/latest/all.json` | 该榜全部分类 + 趋势分析 |
| 单分类数据 | `api/<slug>/latest/<分类名>.json` | 如 `api/click/latest/玄幻奇幻.json` |

榜单 slug：`monthly-ticket`（月票）`one-day`（24h畅销）`new-book`（新书）`click`（点击）`recommend`（推荐）`claque`（捧场）`end`（完结）`new-book-subscribe`（新书订阅）`one-day-update`（24h更新）`author-popularity`（作者人气）

示例：

```bash
curl https://siweimidu.github.io/ZongHengRankTracker/api/boards.json
curl https://siweimidu.github.io/ZongHengRankTracker/api/click/latest/all.json
```

---

## 🔧 本地开发

```bash
git clone https://github.com/<你的用户名>/ZongHengRankTracker.git
cd ZongHengRankTracker

# 依赖极简：只要 requests（AI 可选装 openai）
pip install -r requirements.txt

# 抓取全部榜单（每分类 Top 30）
python scrape_zongheng.py

# 常用参数
python scrape_zongheng.py --top 50          # 自定义 Top N
python scrape_zongheng.py --only click      # 只抓点击榜
python scrape_zongheng.py --build           # 抓完顺带构建

# 构建看板数据 + AI 分析（可选环境变量）
pip install openai
export API_BASE_URL="https://your-api/v1"
export API_KEY="your-key"
export API_MODEL="your-model"
python scripts/build_latest.py              # --force 强制重生成 AI

# 本地预览
python -m http.server 8000
# 打开 http://localhost:8000
```

---

## 📁 项目结构

```
ZongHengRankTracker/
├── .github/workflows/
│   ├── scrape.yml            # 每日定时抓取 + AI 构建 + Pages 部署
│   ├── pages.yml             # main 分支推送时部署 Pages
│   └── force_update.yml      # 手动重抓 / 重算（workflow_dispatch）
├── zh_tracker/               # 核心 Python 包
│   ├── config.py             # 榜单注册表（单一事实源）
│   ├── api.py                # 纯 HTTP 客户端（重试/限速/令牌桶）
│   ├── scrape.py             # 并发抓取器（断点续跑/健康报告）
│   ├── analyze.py            # 趋势引擎（动能分/黑马/分类热度/跨榜）
│   ├── ai.py                 # OpenAI 兼容分析 + 规则兜底
│   └── build.py              # latest 数据 + 静态 API 构建
├── scripts/build_latest.py   # 构建 CLI 入口
├── scrape_zongheng.py        # 抓取 CLI 入口
├── index.html                # 看板主页
├── trend.html                # 风向趋势页
├── book.html                 # 作品情报页
├── css/style.css             # 液态玻璃 + 商务蓝金设计系统
├── js/                       # icons(SVG) / app / trend / book
├── data/<slug>/
│   ├── snapshots/ranks_YYYYMMDD.json   # 每日原始快照
│   ├── trends/YYYY-MM-DD.json          # 趋势归档
│   ├── latest_ranks.json               # 最新聚合（看板数据源）
│   └── discovered_categories.json      # 自动发现的分类
└── api/                      # 静态 JSON 接口（Pages 可直接读）
```

---

## ⚙️ 工作流程

```
┌────────────────────────────────────────────────────────────┐
│              GitHub Actions（每日 04:07 北京时间）           │
│                                                            │
│  ┌────────────┐   ┌─────────────┐   ┌───────────────┐     │
│  │ 纯HTTP爬虫  │──▶│ 趋势引擎+AI  │──▶│ git commit +  │     │
│  │ 10榜×N分类  │   │ 日报/速评    │   │ Pages 部署     │     │
│  └────────────┘   └─────────────┘   └───────────────┘     │
└────────────────────────────────────────────────────────────┘
                         ▼
              在线看板自动更新 🌐
```

---

## 📝 常见问题

<details>
<summary><b>Q: Workflow 失败怎么办？</b></summary>

看 Actions 日志。常见原因：
- 网络波动 → 重跑即可（爬虫自带指数退避重试）
- 官网接口调整 → 用本地 `python -m zh_tracker.api` 快速自检，或提 issue

</details>

<details>
<summary><b>Q: 不配置 AI Secret 也能用吗？</b></summary>

可以。自动 fallback 到规则文案（含动能分、黑马、更新率等真实计算结果），仅缺少自然语言润色。

</details>

<details>
<summary><b>Q: 如何增减榜单 / 调整 Top N？</b></summary>

编辑 `zh_tracker/config.py` 的 `BOARDS`（rankType 对应官网榜单编号），或改 workflow 中 `--top` 参数。新增 rankType 可用官网 rank 页 F12 观察 `/api/rank/details` 的表单参数。

</details>

<details>
<summary><b>Q: 分类是怎么发现的？</b></summary>

抓取时先拉「全部」维度完整榜单（单请求 pageSize=200），从返回数据聚合 `cateFineId/cateFineName` —— 因此**官网页面没展示的分类也会被发现**（如游戏、N次元），并落盘到 `data/<slug>/discovered_categories.json` 供后续复用。

</details>

---

## 📜 License

MIT

---

<p align="center">
  <sub>Made with ☕ and 🤖 —— 数据每日自动更新，无需手动维护</sub>
</p>
