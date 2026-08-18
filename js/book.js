/**
 * 作品详情页 —— 全站检索 bookId，聚合跨榜表现。
 */
(function () {
  const { createApp, ref, computed, onMounted } = Vue;

  const app = createApp({
    setup() {
      const loading = ref(true);
      const book = ref(null);
      const appearances = ref([]);
      const icons = window.ZhIcons;
      const bookId = String(new URLSearchParams(location.search).get('bookId') || '');

      async function j(p) {
        const r = await fetch(p);
        if (!r.ok) throw new Error(p);
        return r.json();
      }

      async function load() {
        if (!bookId) { loading.value = false; return; }
        try {
          const meta = await j('api/boards.json');
          for (const b of meta.boards || []) {
            let d;
            try { d = await j(`api/${b.slug}/latest/all.json`); }
            catch (e) { continue; }
            for (const cat of d.categories || []) {
              const hit = (cat.books || []).find(x => String(x.bookId) === bookId);
              if (hit) {
                appearances.value.push({
                  board: b.slug, boardName: b.name, category: cat.name,
                  rank: hit.rank, metric: hit.metric,
                  metricLabel: hit.metricLabel,
                  updatedToday: hit.updatedToday,
                  latestChapter: hit.latestChapter,
                });
                if (!book.value) book.value = hit;
              }
            }
          }
          appearances.value.sort((a, b2) => a.rank - b2.rank);
        } catch (e) {
          console.error(e);
        } finally {
          loading.value = false;
        }
      }

      function fmtNum(n) {
        n = Number(n || 0);
        if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿';
        if (n >= 10000) return (n / 10000).toFixed(1) + '万';
        return String(n);
      }

      onMounted(load);

      return { icons, loading, book, appearances, bookId, fmtNum };
    },
  });

  app.component('zh-icon', window.ZhIcon);
  app.mount('#app');
})();
