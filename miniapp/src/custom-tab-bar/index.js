const ALL_TABS = [
  {
    pagePath: "/pages/index/index",
    text: "首页",
    iconPath: "/static/tabbar/home.png",
    selectedIconPath: "/static/tabbar/home-active.png"
  },
  {
    pagePath: "/pages/coach/coach",
    text: "训练",
    iconPath: "/static/tabbar/train.png",
    selectedIconPath: "/static/tabbar/train-active.png"
  },
  {
    pagePath: "/pages/team/team",
    text: "跑团",
    iconPath: "/static/tabbar/team.png",
    selectedIconPath: "/static/tabbar/team-active.png"
  },
  {
    pagePath: "/pages/team/cockpit",
    text: "教练",
    iconPath: "/static/tabbar/coach.png",
    selectedIconPath: "/static/tabbar/coach-active.png",
    coachOnly: true
  },
  {
    pagePath: "/pages/profile/profile",
    text: "我的",
    iconPath: "/static/tabbar/profile.png",
    selectedIconPath: "/static/tabbar/profile-active.png"
  }
];

function checkIsCoachOrOwner() {
  try {
    const flag = wx.getStorageSync('rgm_is_coach_or_owner');
    if (flag === true || flag === 1 || flag === '1' || flag === 'true') return true;
    if (flag === false || flag === 0 || flag === '0' || flag === 'false') return false;
    const rawUser = wx.getStorageSync('rgm_user');
    const u = typeof rawUser === 'string' ? JSON.parse(rawUser) : rawUser;
    if (u && (u.is_coach_or_owner || u.is_admin || u.role === 'coach' || u.role === 'owner' || u.role === 'admin')) {
      return true;
    }
  } catch (e) {
    // ignore
  }
  return false;
}

function resolveFontScale() {
  try {
    const saved = wx.getStorageSync('rgm_font_scale');
    if (saved === 'normal' || saved === 'large' || saved === 'xlarge') return saved;
    if (typeof wx.getAppBaseInfo === 'function') {
      const info = wx.getAppBaseInfo();
      const sysPx = Number((info && info.fontSizeSetting) || 0);
      if (sysPx >= 22) return 'xlarge';
      if (sysPx >= 19) return 'large';
    }
  } catch (e) {
    // ignore
  }
  return 'normal';
}

Component({
  data: {
    selected: 0,
    hidden: false,
    theme: 'dark',
    fontScale: 'normal',
    isCoach: false,
    // 默认仅展示普通跑者 4 个 Tab（首页 / 训练 / 跑团 / 我的）；教练或团长自动展示「教练」Tab
    list: ALL_TABS.filter(item => !item.coachOnly)
  },
  pageLifetimes: {
    show() {
      this.syncTheme();
      this.syncSelected();
    }
  },
  attached() {
    this.syncTheme();
    this.syncSelected();
  },
  methods: {
    syncTheme() {
      try {
        const raw = wx.getStorageSync('rgm_theme') || 'dark';
        const theme = (raw === 'volt' || raw === 'trail') ? 'volt' : 'dark';
        const fontScale = resolveFontScale();
        const isCoach = checkIsCoachOrOwner();
        const baseList = ALL_TABS.filter(item => !item.coachOnly || isCoach);
        if (
          this.data.theme !== theme ||
          this.data.isCoach !== isCoach ||
          this.data.list.length !== baseList.length ||
          !this.data.list[0] ||
          !this.data.list[0].src
        ) {
          // 明亮主题（经典竞技 volt）使用深色图标（static/tabbar/light），暗黑主题沿用原图标
          const list = baseList.map((item) => {
            const name = item.iconPath.replace('/static/tabbar/', '').replace('.png', '');
            if (theme === 'dark') {
              return Object.assign({}, item, { src: item.iconPath, activeSrc: item.selectedIconPath });
            }
            return Object.assign({}, item, {
              src: '/static/tabbar/light/' + name + '.png',
              activeSrc: item.selectedIconPath
            });
          });
          this.setData({ theme, fontScale, isCoach, list });
        } else if (this.data.fontScale !== fontScale) {
          this.setData({ fontScale });
        }
      } catch (e) {
        // ignore
      }
    },
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
      try {
        if (typeof wx !== 'undefined' && typeof wx.$rgmTrack === 'function') {
          const item = (this.data.list || [])[idx];
          wx.$rgmTrack(
            'button_click',
            'tabbar_switch',
            item && item.text ? ('底部栏：' + item.text) : ('底部栏：' + url),
            { target_path: url, tab_index: idx }
          );
        }
      } catch (_) {}
      if (this.data.selected !== idx) {
        this.setData({ selected: idx });
      }
      wx.switchTab({ url });
    }
  }
});
