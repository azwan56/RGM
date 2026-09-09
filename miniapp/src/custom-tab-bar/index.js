Component({
  data: {
    selected: 0,
    list: [
      {
        pagePath: "/pages/index/index",
        text: "看板"
      },
      {
        pagePath: "/pages/coach/coach",
        text: "Canova教练"
      },
      {
        pagePath: "/pages/analysis/analysis",
        text: "深度分析"
      },
      {
        pagePath: "/pages/team/rank",
        text: "跑团"
      },
      {
        pagePath: "/pages/profile/profile",
        text: "我的"
      }
    ]
  },
  pageLifetimes: {
    show() {
      this.syncSelected();
    }
  },
  attached() {
    this.syncSelected();
  },
  methods: {
    syncSelected() {
      try {
        const pages = getCurrentPages();
        if (pages && pages.length) {
          const cur = pages[pages.length - 1];
          if (cur && cur.route) {
            const currentPath = cur.route.startsWith('/') ? cur.route : '/' + cur.route;
            const idx = this.data.list.findIndex(item => item.pagePath === currentPath);
            if (idx !== -1 && this.data.selected !== idx) {
              this.setData({ selected: idx });
            }
          }
        }
      } catch (e) {
        // ignore
      }
    },
    switchTab(e) {
      const data = e.currentTarget.dataset;
      const url = data.path;
      const idx = Number(data.index);
      if (this.data.selected !== idx) {
        this.setData({ selected: idx });
      }
      wx.switchTab({ url });
    }
  }
});
