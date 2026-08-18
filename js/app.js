/**
 * 纵横风向标 v2 · 主看板逻辑
 * - 侧边栏 + Fanqie 式 ?board= 真跳转（每次全新加载，避免 SPA 状态问题）
 * - 历史日期切换（◀ ▶ + 原生日期选择 + 最新/昨日预设），读取 data/ 快照
 * - 兼容性：不使用可选链 / 空值合并等 ES2020 语法
 */
(function () {
  var createApp = Vue.createApp;

  var app = createApp({
    data: function () {
      return {
        icons: window.ZhIcons,
        loading: true,
        sidebarOpen: false,
        boardsMeta: [],
        boardData: null,
        brief: '',
        briefTyped: '',
        briefTyping: false,
        crossTop: [],
        activeBoard: 'monthly-ticket',
        activeCat: '全部',
        sortBy: 'rank',
        view: 'list',
        // 日期导航
        viewDate: '',          // '' = 最新
        dates: [],             // 可用快照日期（含今天）
        datePick: '',
        yesterday: '',
        briefDate: '',
      };
    },

    computed: {
      boards: function () { return this.boardsMeta; },
      boardsDate: function () {
        var t = this;
        var hit = this.boardsMeta.filter(function (b) { return b.slug === t.activeBoard; })[0];
        return hit && hit.date ? hit.date : '';
      },
      activeBoardName: function () {
        var t = this;
        var hit = this.boardsMeta.filter(function (b) { return b.slug === t.activeBoard; })[0];
        return hit ? hit.name : '';
      },
      activeBoardEn: function () {
        var map = {
          'monthly-ticket': 'Monthly Ticket Board · 月票刊',
          'one-day': '24h Bestseller · 畅销刊',
          'new-book': 'New Arrivals · 新书刊',
          'click': 'Most Read · 点击刊',
          'recommend': 'Reader’s Choice · 推荐刊',
          'claque': 'Patron’s Circle · 捧场刊',
          'end': 'Completed Works · 完结刊',
          'new-book-subscribe': 'New Subscriptions · 订阅刊',
          'one-day-update': 'Daily Dispatch · 更新刊',
          'author-popularity': 'Author Index · 作者刊',
        };
        return map[this.activeBoard] || 'Rank Review';
      },
      activeBoardDesc: function () {
        var t = this;
        var hit = this.boardsMeta.filter(function (b) { return b.slug === t.activeBoard; })[0];
        return hit && hit.desc ? hit.desc : '';
      },
      isAuthorBoard: function () {
        var t = this;
        var hit = this.boardsMeta.filter(function (b) { return b.slug === t.activeBoard; })[0];
        return hit ? !!hit.is_author : false;
      },
      categories: function () {
        if (!this.boardData || !this.boardData.categories) return [];
        var cats = this.boardData.categories.slice();
        cats.sort(function (a, b) {
          if (a.name === '全部') return -1;
          if (b.name === '全部') return 1;
          return b.books.length - a.books.length;
        });
        return cats;
      },
      currentBooks: function () {
        var t = this;
        var hit = this.categories.filter(function (c) { return c.name === t.activeCat; })[0];
        return hit ? hit.books : [];
      },
      allTrend: function () {
        return (this.boardData && this.boardData.analysis && this.boardData.analysis.trends) || {};
      },
      catTrend: function () { return this.allTrend[this.activeCat] || null; },
      darkhorses: function () {
        var t = this.allTrend['全部'];
        return (t && t.darkhorses) || [];
      },
      stats: function () {
        var seen = {};
        var updateSum = 0, updateCnt = 0, newCnt = 0, firstDay = false;
        var cats = this.boardData ? (this.boardData.categories || []) : [];
        var t = this;
        cats.forEach(function (c) {
          if (c.name !== '全部') return;
          c.books.forEach(function (bk) { seen[bk.bookId] = 1; });
          updateCnt += c.books.length;
          c.books.forEach(function (bk) { if (bk.updatedToday) updateSum++; });
        });
        var keys = Object.keys(this.allTrend);
        var self = this;
        keys.forEach(function (k) {
          var tr = self.allTrend[k];
          if (tr && tr.first_day) firstDay = true;
          if (tr) newCnt += (tr.new_count || 0);
        });
        var n = Object.keys(seen).length;
        return {
          books: n,
          newBooks: firstDay ? '—' : newCnt,
          newHint: firstDay ? '首日基线采集中' : '相对上一期新上榜',
          updateRate: updateCnt ? Math.round(updateSum / updateCnt * 100) : 0,
          boards: this.boardsMeta.length,
        };
      },

      // ---- 日期导航派生 ----
      today: function () { return this.boardsDate; },
      maxDate: function () { return this.dates.length ? this.dates[this.dates.length - 1] : this.today; },
      minDate: function () { return this.dates.length ? this.dates[0] : this.today; },
      hasYesterday: function () {
        return this.yesterday !== '' && this.dates.indexOf(this.yesterday) >= 0;
      },
      canPrev: function () {
        if (!this.dates.length) return false;
        var cur = this.viewDate === '' ? this.dates[this.dates.length - 1] : this.viewDate;
        return this.dates.indexOf(cur) > 0;
      },
      canNext: function () {
        if (!this.dates.length) return false;
        var cur = this.viewDate === '' ? this.dates[this.dates.length - 1] : this.viewDate;
        return this.dates.indexOf(cur) < this.dates.length - 1;
      },

      // 排序 / 过滤
      filteredBooks: function () {
        var list = this.currentBooks.slice();
        if (this.sortBy === 'metric') {
          list.sort(function (a, b) { return (b.metric || 0) - (a.metric || 0); });
        }
        return list;
      },
    },

    watch: {
      datePick: function (v) {
        if (!v) return;
        // 选中的日期有效（在快照列表内）则切换，否则尝试直接读快照
        this.setViewDate(v);
      },
    },

    methods: {
      j: function (path) {
        return fetch(path).then(function (r) {
          if (!r.ok) throw new Error(path + ' ' + r.status);
          return r.json();
        });
      },

      boardHref: function (b) {
        return 'index.html?board=' + encodeURIComponent(b.slug);
      },
      boardIcon: function (b) {
        var map = {
          'monthly-ticket': 'crown', 'one-day': 'bolt', 'new-book': 'star',
          'click': 'eye', 'recommend': 'trend', 'claque': 'medal',
          'end': 'check', 'new-book-subscribe': 'book',
          'one-day-update': 'clock', 'author-popularity': 'author',
        };
        return map[b.slug] || 'medal';
      },
      setCat: function (name) { this.activeCat = name; },

      // ---------- 加载 ----------
      load: function () {
        var self = this;
        this.loading = true;
        this.j('api/boards.json').then(function (meta) {
          self.boardsMeta = meta.boards || [];
          var hit = self.boardsMeta.filter(function (b) { return b.slug === self.activeBoard; })[0];
          if (!hit && self.boardsMeta.length) self.activeBoard = self.boardsMeta[0].slug;
          return self.loadBoard();
        }).catch(function (e) {
          console.error('加载失败', e);
          self.loading = false;
        });
        this.j('api/market-brief.json').then(function (d) {
          self.brief = d.brief || '';
          self.briefDate = d.date || '';
          self.typeBrief();
        }).catch(function () {});
        this.j('api/cross-board.json').then(function (d) {
          self.crossTop = (d.top || []).slice(0, 10);
        }).catch(function () {});
      },

      loadBoard: function () {
        var self = this;
        this.boardData = null;
        var p;
        if (this.viewDate === '') {
          p = this.j('api/' + this.activeBoard + '/latest/all.json');
        } else {
          // 历史快照：直接读仓库 data/ 下的快照文件
          var compact = this.viewDate.replace(/-/g, '');
          p = this.j('data/' + this.activeBoard + '/snapshots/ranks_' + compact + '.json').then(function (snap) {
            return {
              date: snap.date,
              categories: snap.categories || [],
              analysis: { trends: {} },
            };
          });
        }
        return p.then(function (d) {
          self.boardData = d;
          var cats = d.categories || [];
          var found = false;
          for (var i = 0; i < cats.length; i++) if (cats[i].name === self.activeCat) found = true;
          if (!found) self.activeCat = cats.length ? cats[0].name : '全部';
          self.loading = false;
        }).catch(function (e) {
          console.error('榜单加载失败', e);
          self.boardData = { date: '', categories: [], analysis: { trends: {} } };
          self.loading = false;
        });
      },

      loadDates: function () {
        var self = this;
        this.j('data/' + this.activeBoard + '/dates.json').then(function (d) {
          self.dates = d.dates || [];
          if (self.dates.length >= 2) {
            self.yesterday = self.dates[self.dates.length - 2];
          }
        }).catch(function () { self.dates = []; });
      },

      setViewDate: function (d) {
        if (d === this.viewDate) return;
        this.viewDate = d;
        this.loadBoard();
      },
      stepDate: function (dir) {
        if (!this.dates.length) return;
        var cur = this.viewDate === '' ? this.dates[this.dates.length - 1] : this.viewDate;
        var idx = this.dates.indexOf(cur);
        if (idx < 0) return;
        var next = idx + dir;
        if (next < 0 || next >= this.dates.length) return;
        // 走到最后一格 = 回到「最新」视图（带分析数据）
        if (next === this.dates.length - 1) this.setViewDate('');
        else this.setViewDate(this.dates[next]);
      },

      // ---------- 打字机 ----------
      typeBrief: function () {
        var self = this;
        clearInterval(this._typeTimer);
        this.briefTyped = '';
        this.briefTyping = true;
        var text = this.brief;
        var i = 0;
        this._typeTimer = setInterval(function () {
          i += 2;
          self.briefTyped = text.slice(0, i);
          if (i >= text.length) {
            clearInterval(self._typeTimer);
            self.briefTyping = false;
          }
        }, 26);
      },

      // ---------- 工具 ----------
      fmtNum: function (n) {
        n = Number(n || 0);
        if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿';
        if (n >= 10000) return (n / 10000).toFixed(1) + '万';
        return String(n);
      },
      rankClass: function (r) { return r <= 3 ? 'r' + r : ''; },
      rankChangeOf: function (b) {
        var t = this.allTrend['全部'];
        if (!t || !t.top_movers) return 0;
        var movers = t.top_movers;
        for (var i = 0; i < movers.length; i++) {
          if (String(movers[i].bookId) === String(b.bookId)) return movers[i].rankChange || 0;
        }
        return 0;
      },
      isNew: function (b) {
        var t = this.allTrend['全部'];
        if (!t || !t.new_books) return false;
        var ns = t.new_books;
        for (var i = 0; i < ns.length; i++) {
          if (String(ns[i].bookId) === String(b.bookId)) return true;
        }
        return false;
      },
      isDarkhorse: function (b) {
        var t = this.allTrend['全部'];
        if (!t || !t.darkhorses) return false;
        var ds = t.darkhorses;
        for (var i = 0; i < ds.length; i++) {
          if (String(ds[i].bookId) === String(b.bookId)) return true;
        }
        return false;
      },
      goBook: function (bookId) {
        location.href = 'book.html?bookId=' + bookId;
      },
    },

    mounted: function () {
      var p = new URLSearchParams(location.search);
      if (p.get('board')) this.activeBoard = p.get('board');
      if (p.get('cat')) this.activeCat = p.get('cat');
      if (p.get('date')) this.viewDate = p.get('date');
      if (p.get('view')) this.view = p.get('view');
      this.load();
      this.loadDates();
    },
  });

  app.component('zh-icon', window.ZhIcon);
  app.mount('#app');
})();
