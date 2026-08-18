/**
 * 风向趋势页逻辑 —— ECharts 可视化（无构建步骤）。
 */
(function () {
  const { createApp, ref, computed, onMounted, nextTick } = Vue;

  // 商务蓝金调色板
  const PALETTE = ['#2563eb', '#c9a45c', '#7c5cff', '#0e7ac4', '#e0533f',
    '#1fa06b', '#d49a2e', '#5a6b8c', '#8b5cf6', '#1648b8'];

  const app = createApp({
    setup() {
      const loading = ref(true);
      const boards = ref([]);
      const activeBoard = ref('');
      const analysis = ref(null);
      const date = ref('');
      const icons = window.ZhIcons;
      let charts = [];

      async function j(p) {
        const r = await fetch(p);
        if (!r.ok) throw new Error(p + ' ' + r.status);
        return r.json();
      }

      async function load() {
        loading.value = true;
        try {
          const meta = await j('api/boards.json');
          boards.value = meta.boards || [];
          const p = new URLSearchParams(location.search);
          const want = p.get('board');
          if (want && boards.value.find(b => b.slug === want)) {
            activeBoard.value = want;
          } else if (boards.value.length) {
            activeBoard.value = boards.value[0].slug;
          }
          await loadBoard();
        } catch (e) {
          console.error(e);
        } finally {
          loading.value = false;
        }
      }

      async function loadBoard() {
        analysis.value = null;
        charts.forEach(c => c.dispose());
        charts = [];
        try {
          const d = await j(`api/${activeBoard.value}/latest/all.json`);
          analysis.value = d.analysis || null;
          date.value = d.date || '';
          loading.value = false;          // 先让 v-if 容器进入 DOM
          await nextTick();
          await nextTick();
          renderCharts();
        } catch (e) {
          console.error(e);
          loading.value = false;
        }
      }

      function switchBoard(slug) {
        if (slug === activeBoard.value) return;
        activeBoard.value = slug;
        const u = new URL(location);
        u.searchParams.set('board', slug);
        history.replaceState(null, '', u);
        loadBoard();
      }

      const boardName = computed(() =>
        boards.value.find(b => b.slug === activeBoard.value)?.name || '');
      const darkhorses = computed(() =>
        analysis.value?.trends?.['全部']?.darkhorses || []);
      const keywordHeat = computed(() =>
        (analysis.value?.keyword_heat || []).slice(0, 18));

      function baseOpt() {
        return {
          color: PALETTE,
          textStyle: { fontFamily: 'inherit', color: '#5a6b8c' },
          tooltip: { backgroundColor: 'rgba(12,28,61,0.92)', borderWidth: 0,
            textStyle: { color: '#fff', fontSize: 12 },
            extraCssText: 'border-radius:10px;backdrop-filter:blur(8px);' },
        };
      }

      function mk(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        return echarts.init(el);
      }

      function renderCharts() {
        const a = analysis.value;
        if (!a) return;

        // 1) 分类热度横向条形图
        const c1 = mk('chart-cate');
        if (c1) {
          const cats = (a.category_heat || []).slice(0, 10);
          c1.setOption({
            ...baseOpt(),
            grid: { left: 8, right: 40, top: 10, bottom: 10, containLabel: true },
            xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(120,140,180,0.15)' } } },
            yAxis: { type: 'category', inverse: true,
              data: cats.map(c => c.name),
              axisLine: { show: false }, axisTick: { show: false },
              axisLabel: { color: '#1d2b4f', fontWeight: 600 } },
            series: [{
              type: 'bar', barWidth: 16,
              data: cats.map(c => c.heat),
              itemStyle: { borderRadius: [0, 9, 9, 0],
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0,
                  [{ offset: 0, color: '#1648b8' }, { offset: 1, color: '#5b8def' }]) },
              label: { show: true, position: 'right', color: '#5a6b8c', fontSize: 11 },
            }],
            animationDuration: 900,
            animationEasing: 'elasticOut',
          });
          charts.push(c1);
        }

        // 2) 关键词柱状图
        const c2 = mk('chart-kw');
        if (c2) {
          const kws = (a.keyword_heat || []).slice(0, 12);
          c2.setOption({
            ...baseOpt(),
            grid: { left: 8, right: 20, top: 14, bottom: 10, containLabel: true },
            xAxis: { type: 'category', data: kws.map(k => k.keyword),
              axisLabel: { rotate: 32, color: '#5a6b8c', fontSize: 11 },
              axisLine: { lineStyle: { color: 'rgba(120,140,180,0.3)' } } },
            yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(120,140,180,0.15)' } } },
            series: [{
              type: 'bar', barWidth: 18,
              data: kws.map(k => k.count),
              itemStyle: { borderRadius: [8, 8, 0, 0],
                color: new echarts.graphic.LinearGradient(0, 1, 0, 0,
                  [{ offset: 0, color: '#c9a45c' }, { offset: 1, color: '#ecd9a8' }]) },
            }],
            animationDuration: 900,
            animationEasing: 'elasticOut',
          });
          charts.push(c2);
        }

        // 3) Top3 时间轴
        const c3 = mk('chart-timeline');
        if (c3) {
          const tl = a.timeline || [];
          c3.setOption({
            ...baseOpt(),
            tooltip: { ...baseOpt().tooltip,
              formatter: (params) => {
                const idx = params[0]?.dataIndex;
                if (idx == null || !tl[idx]) return '';
                const t = tl[idx];
                return `<b>${t.date}</b><br>` + (t.top3 || []).map(
                  (b, i) => `${i + 1}. 《${b.title}》 ${b.author}`).join('<br>');
              } },
            grid: { left: 8, right: 20, top: 20, bottom: 10, containLabel: true },
            xAxis: { type: 'category', data: tl.map(t => (t.date || '').slice(5)),
              axisLabel: { color: '#5a6b8c', fontSize: 11 } },
            yAxis: { show: false, min: 0, max: 4 },
            series: [{
              type: 'line', data: tl.map(() => 1), symbolSize: 12,
              lineStyle: { color: '#2563eb', width: 3 },
              itemStyle: { color: '#2563eb', borderColor: '#fff', borderWidth: 2 },
              areaStyle: { color: 'rgba(37,99,235,0.08)' },
              markPoint: tl.map((t, i) => ({
                coord: [i, 1],
                symbol: 'roundRect', symbolSize: [52, 20],
                symbolOffset: [0, -22],
                label: { show: true, formatter: (t.top3?.[0]?.title || '—').slice(0, 6),
                  fontSize: 10, color: '#0c1c3d', fontWeight: 700 },
                itemStyle: { color: 'rgba(201,164,92,0.16)' },
              })).slice(0, 12),
            }],
          });
          charts.push(c3);
        }
      }

      function copyKw(kw) {
        navigator.clipboard?.writeText(kw).catch(() => {});
      }

      onMounted(load);
      window.addEventListener('resize', () => charts.forEach(c => c.resize()));

      return { icons, loading, boards, activeBoard, boardName, analysis, date,
        darkhorses, keywordHeat, switchBoard, copyKw };
    },
  });

  app.component('zh-icon', window.ZhIcon);
  app.mount('#app');
})();
