/**
 * 纵横风向标 · 主看板逻辑
 * Vue 3 (global build)，无构建步骤，GitHub Pages 直接可跑。
 */
(function () {
  const { createApp, ref, computed, onMounted, watch } = Vue;

  const app = createApp({
    setup() {
      // ---------- 状态 ----------
      const loading = ref(true);
      const boardsMeta = ref([]);     // api/boards.json
      const boardData = ref(null);    // 当前榜单 all.json
      const brief = ref('');
      const briefTyped = ref('');
      const briefTyping = ref(false);
      const crossTop = ref([]);
      const activeBoard = ref('');
      const activeCat = ref('全部');
      const query = ref('');
      const sortBy = ref('rank');
      const view = ref('grid');
      const icons = window.ZhIcons;

      // ---------- 数据加载 ----------
      async function j(path) {
        const r = await fetch(path);
        if (!r.ok) throw new Error(path + ' ' + r.status);
        return r.json();
      }

      async function load() {
        loading.value = true;
        try {
          const meta = await j('api/boards.json');
          boardsMeta.value = meta.boards || [];
          if (boardsMeta.value.length) {
            activeBoard.value = boardsMeta.value[0].slug;
            await loadBoard(activeBoard.value);
          }
        } catch (e) {
          console.error('加载失败', e);
        } finally {
          loading.value = false;
        }
        // 日报与跨榜（失败不影响主界面）
        j('api/market-brief.json').then(d => {
          brief.value = d.brief || '';
          typeBrief();
        }).catch(() => {});
        j('api/cross-board.json').then(d => {
          crossTop.value = (d.top || []).slice(0, 15);
        }).catch(() => {});
      }

      async function loadBoard(slug) {
        boardData.value = null;
        try {
          boardData.value = await j(`api/${slug}/latest/all.json`);
          const cats = boardData.value.categories || [];
          if (!cats.find(c => c.name === activeCat.value)) {
            activeCat.value = cats.length ? cats[0].name : '全部';
          }
        } catch (e) {
          console.error('榜单加载失败', slug, e);
        }
      }

      function switchBoard(slug) {
        if (slug === activeBoard.value) return;
        activeBoard.value = slug;
        activeCat.value = '全部';
        query.value = '';
        loadBoard(slug);
      }

      // ---------- 打字机 ----------
      let typeTimer = null;
      function typeBrief() {
        clearInterval(typeTimer);
        briefTyped.value = '';
        briefTyping.value = true;
        const text = brief.value;
        let i = 0;
        typeTimer = setInterval(() => {
          i += 2;
          briefTyped.value = text.slice(0, i);
          if (i >= text.length) {
            clearInterval(typeTimer);
            briefTyping.value = false;
          }
        }, 28);
      }

      // ---------- 派生 ----------
      const boards = computed(() => boardsMeta.value);
      const boardsDate = computed(() =>
        boardsMeta.value.find(b => b.slug === activeBoard.value)?.date || '');
      const activeBoardName = computed(() =>
        boardsMeta.value.find(b => b.slug === activeBoard.value)?.name || '');
      const categories = computed(() =>
        (boardData.value?.categories || []).slice().sort((a, b) =>
          a.name === '全部' ? -1 : b.name === '全部' ? 1 : b.books.length - a.books.length));

      const allTrend = computed(() => boardData.value?.analysis?.trends || {});
      const catTrend = computed(() => allTrend.value[activeCat.value] || null);

      const darkhorseSet = computed(() => {
        const set = new Set();
        Object.values(allTrend.value).forEach(t =>
          (t.darkhorses || []).forEach(d => set.add(String(d.bookId))));
        return set;
      });
      const newSet = computed(() => {
        const set = new Set();
        Object.values(allTrend.value).forEach(t =>
          (t.new_books || []).forEach(n => set.add(String(n.bookId))));
        return set;
      });
      const changeMap = computed(() => {
        const m = {};
        Object.values(allTrend.value).forEach(t =>
          (t.top_movers || []).forEach(v => {
            const k = String(v.bookId);
            m[k] = Math.max(m[k] || 0, v.rankChange);
          }));
        return m;
      });
      const momentumMap = computed(() => {
        const m = {};
        Object.values(allTrend.value).forEach(t =>
          (t.top_movers || []).forEach(v => {
            const k = String(v.bookId);
            m[k] = Math.max(m[k] || 0, v.momentum || 0);
          }));
        return m;
      });

      const currentBooks = computed(() =>
        categories.value.find(c => c.name === activeCat.value)?.books || []);

      const filteredBooks = computed(() => {
        let list = currentBooks.value.slice();
        const q = query.value.trim().toLowerCase();
        if (q) {
          list = list.filter(b =>
            (b.title || '').toLowerCase().includes(q) ||
            (b.author || '').toLowerCase().includes(q) ||
            (b.category || '').includes(q) ||
            (b.intro || '').includes(query.value.trim()));
        }
        if (sortBy.value === 'metric') {
          list.sort((a, b) => (b.metric || 0) - (a.metric || 0));
        }
        return list;
      });

      const darkhorses = computed(() => {
        const t = allTrend.value['全部'];
        return t?.darkhorses || [];
      });

      const stats = computed(() => {
        const seen = new Set();
        let updateSum = 0, updateCnt = 0, newCnt = 0, firstDay = false;
        (boardData.value?.categories || []).forEach(c => {
          if (c.name !== '全部') return;
          c.books.forEach(bk => seen.add(String(bk.bookId)));
          updateCnt += c.books.length;
          updateSum += c.books.filter(bk => bk.updatedToday).length;
        });
        Object.values(allTrend.value).forEach(t => {
          if (t.first_day) firstDay = true;
          newCnt += t.new_count || 0;
        });
        return {
          boards: boardsMeta.value.length,
          books: seen.size,
          newBooks: firstDay ? '—' : newCnt,
          newHint: firstDay ? '首日基线采集，明日开启对比' : '相对上一期快照',
          updateRate: updateCnt ? Math.round(updateSum / updateCnt * 100) : 0,
        };
      });

      // ---------- 工具函数 ----------
      function fmtNum(n) {
        n = Number(n || 0);
        if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿';
        if (n >= 10000) return (n / 10000).toFixed(1) + '万';
        return String(n);
      }
      function rankClass(r) { return r <= 3 ? 'r' + r : ''; }
      function rankChangeOf(b) { return changeMap.value[String(b.bookId)] || 0; }
      function momentumOf(b) { return momentumMap.value[String(b.bookId)] || 0; }
      function isNew(b) { return newSet.value.has(String(b.bookId)); }
      function isDarkhorse(b) { return darkhorseSet.value.has(String(b.bookId)); }
      function onCoverError(e) {
        e.target.style.display = 'none';
      }
      function openBook(b) { goBook(b.bookId); }
      function goBook(bookId) {
        location.href = 'book.html?bookId=' + bookId;
      }
      function boardIcon(b) {
        const map = {
          'monthly-ticket': 'crown', 'one-day': 'bolt', 'new-book': 'star',
          'click': 'eye', 'recommend': 'trend', 'claque': 'medal',
          'end': 'check', 'new-book-subscribe': 'book',
          'one-day-update': 'clock', 'author-popularity': 'author',
        };
        return map[b.slug] || 'medal';
      }

      // ---------- URL 同步 ----------
      onMounted(() => {
        const p = new URLSearchParams(location.search);
        if (p.get('board')) activeBoard.value = p.get('board');
        load();
      });
      watch(activeBoard, s => {
        const u = new URL(location);
        u.searchParams.set('board', s);
        history.replaceState(null, '', u);
      });

      return {
        icons, loading, boards, boardsDate, activeBoard, activeBoardName,
        categories, activeCat, query, sortBy, view, currentBooks,
        filteredBooks, catTrend, darkhorses, crossTop, brief, briefTyped,
        briefTyping, stats,
        switchBoard, fmtNum, rankClass, rankChangeOf, momentumOf, isNew,
        isDarkhorse, onCoverError, openBook, goBook, boardIcon,
      };
    },
  });

  app.component('zh-icon', window.ZhIcon);
  app.mount('#app');
})();
