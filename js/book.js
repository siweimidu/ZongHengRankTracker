/**
 * 作品详情页 v2 —— 全站检索 bookId，聚合跨榜表现（无可选链）。
 */
(function () {
  var createApp = Vue.createApp;

  var app = createApp({
    data: function () {
      var bid = new URLSearchParams(location.search).get('bookId') || '';
      return {
        icons: window.ZhIcons,
        loading: true,
        book: null,
        appearances: [],
        bookId: bid,
        isAuthorCover: false,
      };
    },

    methods: {
      j: function (p) {
        return fetch(p).then(function (r) {
          if (!r.ok) throw new Error(p);
          return r.json();
        });
      },
      fmtNum: function (n) {
        n = Number(n || 0);
        if (n >= 100000000) return (n / 100000000).toFixed(1) + '亿';
        if (n >= 10000) return (n / 10000).toFixed(1) + '万';
        return String(n);
      },
      load: function () {
        var self = this;
        if (!this.bookId) { this.loading = false; return; }
        this.j('api/boards.json').then(function (meta) {
          var chain = Promise.resolve();
          (meta.boards || []).forEach(function (b) {
            chain = chain.then(function () {
              return self.j('api/' + b.slug + '/latest/all.json').then(function (d) {
                (d.categories || []).forEach(function (cat) {
                  var hit = null;
                  (cat.books || []).forEach(function (x) {
                    if (String(x.bookId) === String(self.bookId)) hit = x;
                  });
                  if (hit) {
                    self.appearances.push({
                      board: b.slug, boardName: b.name, category: cat.name,
                      rank: hit.rank, metric: hit.metric,
                      metricLabel: hit.metricLabel,
                      updatedToday: hit.updatedToday,
                      latestChapter: hit.latestChapter,
                    });
                    if (!self.book) {
                      self.book = hit;
                      // 作者头像 fallback 场景：cover 等于 authorCover → 圆形展示
                      self.isAuthorCover = !hit.cover || (hit.authorCover && hit.cover === hit.authorCover);
                    }
                  }
                });
              }).catch(function () { /* 单榜失败不影响整体 */ });
            });
          });
          return chain;
        }).catch(function (e) {
          console.error(e);
        }).then(function () {
          self.appearances.sort(function (a, b) { return a.rank - b.rank; });
          self.loading = false;
        });
      },
    },

    mounted: function () { this.load(); },
  });

  app.component('zh-icon', window.ZhIcon);
  app.mount('#app');
})();
