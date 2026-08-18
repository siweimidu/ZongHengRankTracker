/**
 * 风向趋势页 v2 —— ECharts 可视化（豆包蓝调色板，无可选链语法）。
 */
(function () {
  var createApp = Vue.createApp;

  var PALETTE = ['#0065fd', '#557fff', '#0057da', '#c9a45c', '#6d5ce6',
    '#34c759', '#e0503f', '#8aa2c8', '#0043ad', '#7f8d9f'];

  var app = createApp({
    data: function () {
      return {
        icons: window.ZhIcons,
        loading: true,
        boards: [],
        activeBoard: 'monthly-ticket',
        analysis: null,
        date: '',
      };
    },

    computed: {
      boardName: function () {
        var t = this;
        var hit = this.boards.filter(function (b) { return b.slug === t.activeBoard; })[0];
        return hit ? hit.name : '';
      },
      darkhorses: function () {
        var t = this.analysis && this.analysis.trends && this.analysis.trends['全部'];
        return (t && t.darkhorses) || [];
      },
      keywordHeat: function () {
        return this.analysis ? (this.analysis.keyword_heat || []).slice(0, 18) : [];
      },
    },

    methods: {
      j: function (p) {
        return fetch(p).then(function (r) {
          if (!r.ok) throw new Error(p);
          return r.json();
        });
      },
      switchBoard: function (slug) {
        if (slug === this.activeBoard) return;
        location.href = 'trend.html?board=' + encodeURIComponent(slug);
      },
      copyKw: function (kw) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(kw).catch(function () {});
        }
      },

      baseOpt: function () {
        return {
          color: PALETTE,
          textStyle: { fontFamily: 'inherit', color: '#7f8d9f' },
          tooltip: {
            backgroundColor: 'rgba(14,17,21,0.9)', borderWidth: 0,
            textStyle: { color: '#fff', fontSize: 12 },
            extraCssText: 'border-radius:10px;',
          },
        };
      },
      mk: function (id) {
        var el = document.getElementById(id);
        return el ? echarts.init(el) : null;
      },

      load: function () {
        var self = this;
        this.loading = true;
        this.j('api/boards.json').then(function (meta) {
          self.boards = meta.boards || [];
          var p = new URLSearchParams(location.search);
          var want = p.get('board');
          var hit = self.boards.filter(function (b) { return b.slug === want; })[0];
          if (hit) self.activeBoard = want;
          else if (self.boards.length) self.activeBoard = self.boards[0].slug;
          return self.loadBoard();
        }).catch(function (e) {
          console.error(e);
          self.loading = false;
        });
      },

      loadBoard: function () {
        var self = this;
        this.analysis = null;
        var p = this.j('api/' + this.activeBoard + '/latest/all.json');
        return p.then(function (d) {
          self.analysis = d.analysis || null;
          self.date = d.date || '';
          self.loading = false;
          self.$nextTick(function () { self.$nextTick(function () { self.renderCharts(); }); });
        }).catch(function (e) {
          console.error(e);
          self.loading = false;
        });
      },

      renderCharts: function () {
        var a = this.analysis;
        if (!a || typeof echarts === 'undefined') return;
        var self = this;

        // 1) 分类热度横向条形
        var c1 = this.mk('chart-cate');
        if (c1) {
          var cats = (a.category_heat || []).slice(0, 10);
          c1.setOption(Object.assign(this.baseOpt(), {
            grid: { left: 8, right: 44, top: 8, bottom: 8, containLabel: true },
            xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eef1f6' } } },
            yAxis: {
              type: 'category', inverse: true,
              data: cats.map(function (c) { return c.name; }),
              axisLine: { show: false }, axisTick: { show: false },
              axisLabel: { color: '#0e1115', fontWeight: 600 },
            },
            series: [{
              type: 'bar', barWidth: 15,
              data: cats.map(function (c) { return c.heat; }),
              itemStyle: {
                borderRadius: [0, 8, 8, 0],
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0,
                  [{ offset: 0, color: '#0057da' }, { offset: 1, color: '#557fff' }]),
              },
              label: { show: true, position: 'right', color: '#7f8d9f', fontSize: 10.5 },
            }],
            animationDuration: 850,
            animationEasing: 'cubicOut',
          }));
          this._charts.push(c1);
        }

        // 2) 关键词柱状
        var c2 = this.mk('chart-kw');
        if (c2) {
          var kws = (a.keyword_heat || []).slice(0, 12);
          c2.setOption(Object.assign(this.baseOpt(), {
            grid: { left: 8, right: 14, top: 12, bottom: 8, containLabel: true },
            xAxis: {
              type: 'category', data: kws.map(function (k) { return k.keyword; }),
              axisLabel: { rotate: 30, color: '#7f8d9f', fontSize: 10.5 },
              axisLine: { lineStyle: { color: '#e7eaef' } },
            },
            yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eef1f6' } } },
            series: [{
              type: 'bar', barWidth: 16,
              data: kws.map(function (k) { return k.count; }),
              itemStyle: {
                borderRadius: [7, 7, 0, 0],
                color: new echarts.graphic.LinearGradient(0, 1, 0, 0,
                  [{ offset: 0, color: '#0065fd' }, { offset: 1, color: '#8ab2ff' }]),
              },
            }],
            animationDuration: 850,
            animationEasing: 'cubicOut',
          }));
          this._charts.push(c2);
        }

        // 3) 榜首时间轴
        var c3 = this.mk('chart-timeline');
        if (c3) {
          var tl = a.timeline || [];
          var base = this.baseOpt();
          c3.setOption(Object.assign(base, {
            tooltip: {
              backgroundColor: 'rgba(14,17,21,0.9)', borderWidth: 0,
              textStyle: { color: '#fff', fontSize: 12 },
              formatter: function (params) {
                var idx = params[0] && params[0].dataIndex;
                if (idx == null || !tl[idx]) return '';
                var t = tl[idx];
                var lines = ['<b>' + t.date + '</b>'];
                (t.top3 || []).forEach(function (b, i) {
                  lines.push((i + 1) + '. 《' + b.title + '》 ' + b.author);
                });
                return lines.join('<br>');
              },
            },
            grid: { left: 8, right: 16, top: 26, bottom: 8, containLabel: true },
            xAxis: {
              type: 'category',
              data: tl.map(function (t) { return (t.date || '').slice(5); }),
              axisLabel: { color: '#7f8d9f', fontSize: 10.5 },
            },
            yAxis: { show: false, min: 0, max: 4 },
            series: [{
              type: 'line', data: tl.map(function () { return 1; }), symbolSize: 10,
              lineStyle: { color: '#0065fd', width: 2.5 },
              itemStyle: { color: '#0065fd', borderColor: '#fff', borderWidth: 2 },
              areaStyle: { color: 'rgba(0,101,253,0.06)' },
              markPoint: tl.slice(0, 12).map(function (t, i) {
                var top = (t.top3 && t.top3[0] && t.top3[0].title) || '—';
                return {
                  coord: [i, 1],
                  symbol: 'roundRect', symbolSize: [56, 20],
                  symbolOffset: [0, -24],
                  label: { show: true, formatter: top.slice(0, 6), fontSize: 9.5, color: '#00266b', fontWeight: 700 },
                  itemStyle: { color: 'rgba(229,233,255,0.9)' },
                };
              }),
            }],
          }));
          this._charts.push(c3);
        }
      },
    },

    mounted: function () {
      var self = this;
      this._charts = [];
      this.load();
      window.addEventListener('resize', function () {
        (self._charts || []).forEach(function (c) { c.resize(); });
      });
    },
  });

  app.component('zh-icon', window.ZhIcon);
  app.mount('#app');
})();
