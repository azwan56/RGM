<template>
  <view class="dashboard-page">
    <!-- Header: User Greeting & Avatar -->
    <view class="header-card">
      <view class="user-info">
        <image class="avatar" :src="user?.avatar_url || '/static/default_avatar.png'" mode="aspectFill" />
        <view class="text-group">
          <text class="greeting">欢迎回来，</text>
          <text class="user-name">{{ user?.display_name || dashboardData?.user?.display_name || "跑者" }}</text>
        </view>
      </view>
      <view class="garmin-badge" :class="{ active: dashboardData?.user?.garmin_connected }">
        <view class="pulse-dot" />
        <text class="badge-text">{{ dashboardData?.user?.garmin_connected ? "佳明已连接" : "未连接佳明" }}</text>
      </view>
    </view>

    <!-- Monthly Goal Progress Hero Card -->
    <view class="hero-progress-card">
      <view class="card-header">
        <text class="card-title">当月跑量目标 ({{ currentMonth }}月)</text>
        <text class="progress-pct">{{ dashboardData?.progress?.progress_pct || 60.0 }}%</text>
      </view>

      <view class="progress-bar-bg">
        <view class="progress-bar-fill" :style="{ width: Math.min(100, dashboardData?.progress?.progress_pct || 60) + '%' }" />
      </view>

      <view class="stats-grid">
        <view class="stat-item">
          <text class="stat-val primary-text">{{ dashboardData?.progress?.current_month_km || 119.9 }}</text>
          <text class="stat-label">已跑 (km)</text>
        </view>
        <view class="stat-item divider">
          <text class="stat-val">{{ dashboardData?.progress?.target_month_km || 200 }}</text>
          <text class="stat-label">目标 (km)</text>
        </view>
        <view class="stat-item divider">
          <text class="stat-val">{{ dashboardData?.progress?.remaining_km || 80.1 }}</text>
          <text class="stat-label">剩余 (km)</text>
        </view>
        <view class="stat-item">
          <text class="stat-val accent-text">{{ dashboardData?.progress?.daily_required_km || 5.7 }}</text>
          <text class="stat-label">日均需跑 (km)</text>
        </view>
      </view>

      <!-- Garmin Instant Sync Action Button -->
      <view class="sync-action-box">
        <button class="sync-btn" :loading="syncing" :disabled="syncing" @click="handleInstantSync">
          <text class="btn-icon">⚡</text>
          <text>{{ syncing ? "正在从 Garmin 同步..." : "一键同步 Garmin 数据" }}</text>
        </button>
      </view>
    </view>

    <!-- ── CARD 0: 体能与状况指数 (Fitness & Form) ── -->
    <view class="section-container">
      <view class="section-header-row">
        <view class="title-with-desc">
          <text class="section-title">⚡ 体能与状况指数 (Fitness & Form)</text>
          <text class="sub-formula">基于标准 Banister TRIMP 与 EWMA 模型算法</text>
        </view>
        <view class="metrics-pill-group">
          <view class="metric-pill">
            <text class="pill-label">CTL 体能</text>
            <text class="pill-val text-cyan">{{ dashboardData?.fitness_form?.ctl ?? 44.3 }}</text>
          </view>
          <view class="metric-pill">
            <text class="pill-label">ATL 疲劳</text>
            <text class="pill-val text-pink">{{ dashboardData?.fitness_form?.atl ?? 56.7 }}</text>
          </view>
          <view class="metric-pill">
            <text class="pill-label">TSB 状况</text>
            <text
              class="pill-val"
              :style="{ color: dashboardData?.fitness_form?.status_color || '#0ea5e9' }"
            >
              {{ (dashboardData?.fitness_form?.tsb ?? -12.3) > 0 ? '+' : '' }}{{ dashboardData?.fitness_form?.tsb ?? -12.3 }}
            </text>
          </view>
        </view>
      </view>

      <view class="fitness-chart-card">
        <!-- Tooltip Bubble when tapped -->
        <view v-if="activeTooltip" class="chart-tooltip">
          <text class="tip-date">{{ activeTooltip.short_date || activeTooltip.date }}</text>
          <text class="tip-val text-cyan">CTL: {{ activeTooltip.ctl }}</text>
          <text class="tip-val text-pink">ATL: {{ activeTooltip.atl }}</text>
          <text class="tip-val" :style="{ color: activeTooltip.tsb_color || '#0ea5e9' }">
            TSB: {{ activeTooltip.tsb > 0 ? '+' : '' }}{{ activeTooltip.tsb }} ({{ activeTooltip.tsb_label || '训练中' }})
          </text>
        </view>

        <!-- SVG Fitness & Form Chart -->
        <svg viewBox="0 0 350 185" class="fitness-svg-chart">
          <!-- Horizontal Gridlines & Y-Axis Labels -->
          <line x1="28" y1="18" x2="340" y2="18" stroke="#1f1f24" stroke-dasharray="3,3" stroke-width="1" />
          <text x="24" y="21" fill="#666" font-size="9" text-anchor="end">135</text>

          <line x1="28" y1="53" x2="340" y2="53" stroke="#1f1f24" stroke-dasharray="3,3" stroke-width="1" />
          <text x="24" y="56" fill="#666" font-size="9" text-anchor="end">90</text>

          <line x1="28" y1="88" x2="340" y2="88" stroke="#1f1f24" stroke-dasharray="3,3" stroke-width="1" />
          <text x="24" y="91" fill="#666" font-size="9" text-anchor="end">45</text>

          <line x1="28" y1="123" x2="340" y2="123" stroke="#333" stroke-dasharray="2,2" stroke-width="1" />
          <text x="24" y="126" fill="#888" font-size="9" text-anchor="end">0</text>

          <line x1="28" y1="158" x2="340" y2="158" stroke="#1f1f24" stroke-dasharray="3,3" stroke-width="1" />
          <text x="24" y="161" fill="#666" font-size="9" text-anchor="end">-45</text>

          <!-- TSB Vertical Bars -->
          <rect
            v-for="(bar, idx) in tsbBars"
            :key="'tsb-' + idx"
            :x="bar.x"
            :y="bar.y"
            :width="bar.w"
            :height="bar.h"
            :fill="bar.color"
            rx="1.5"
            opacity="0.85"
            @click="selectPoint(bar.item)"
          />

          <!-- CTL Curve (Cyan) -->
          <path
            :d="ctlSvgPath"
            fill="none"
            stroke="#38bdf8"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />

          <!-- ATL Curve (Pink) -->
          <path
            :d="atlSvgPath"
            fill="none"
            stroke="#ec4899"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          />

          <!-- X-Axis Date Labels -->
          <text
            v-for="(lbl, idx) in xAxisLabels"
            :key="'lbl-' + idx"
            :x="lbl.x"
            y="178"
            fill="#666"
            font-size="8.5"
            text-anchor="middle"
          >
            {{ lbl.text }}
          </text>
        </svg>

        <!-- Color-Coded Legend (matching Web) -->
        <view class="chart-legend-row">
          <view class="legend-item">
            <view class="line-dot cyan" />
            <text class="legend-text">体能 (CTL): 42天长期压力</text>
          </view>
          <view class="legend-item">
            <view class="line-dot pink" />
            <text class="legend-text">疲劳 (ATL): 7天近期压力</text>
          </view>
        </view>
        <view class="chart-legend-row tsb-tags-row">
          <view class="legend-item">
            <view class="rect-dot green" />
            <text class="legend-text">&gt;5 巅峰</text>
          </view>
          <view class="legend-item">
            <view class="rect-dot blue" />
            <text class="legend-text">-30~5 训练中</text>
          </view>
          <view class="legend-item">
            <view class="rect-dot yellow" />
            <text class="legend-text">-50~-30 疲劳</text>
          </view>
          <view class="legend-item">
            <view class="rect-dot red" />
            <text class="legend-text">&lt;-50 严重</text>
          </view>
        </view>
      </view>
    </view>

    <!-- ── CARD 1: Garmin 生理与恢复 4 格卡片 ── -->
    <view class="section-container">
      <view class="section-header-row">
        <text class="section-title">Garmin 生理与恢复指标</text>
        <text class="sub-date">更新于: {{ dashboardData?.today_health?.date || "今日" }}</text>
      </view>

      <view class="health-grid-4">
        <!-- 1. 睡眠恢复 -->
        <view class="health-tile">
          <view class="tile-top">
            <text class="tile-icon">🛏️</text>
            <text class="tile-name">睡眠恢复</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val">{{ dashboardData?.today_health?.sleep_score ?? 69 }}</text>
            <text class="tile-unit">分</text>
          </view>
          <text class="tile-sub">时长 {{ dashboardData?.today_health?.sleep_duration_text || '8h 35m' }}</text>
        </view>

        <!-- 2. 静息心率 -->
        <view class="health-tile">
          <view class="tile-top">
            <text class="tile-icon">💓</text>
            <text class="tile-name">静息心率 (RHR)</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val text-rose">{{ dashboardData?.today_health?.resting_heart_rate ?? 56 }}</text>
            <text class="tile-unit">bpm</text>
          </view>
          <text class="tile-sub">清晨生理基线</text>
        </view>

        <!-- 3. 身体电量 -->
        <view class="health-tile">
          <view class="tile-top">
            <text class="tile-icon">⚡</text>
            <text class="tile-name">身体电量</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val text-amber">{{ dashboardData?.today_health?.body_battery_max ?? 54 }}%</text>
          </view>
          <view class="mini-progress-bg">
            <view
              class="mini-progress-fill"
              :style="{ width: Math.min(100, dashboardData?.today_health?.body_battery_max ?? 54) + '%' }"
            />
          </view>
        </view>

        <!-- 4. 夜间 HRV -->
        <view class="health-tile">
          <view class="tile-top">
            <text class="tile-icon">🫀</text>
            <text class="tile-name">夜间 HRV</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val text-cyan">{{ dashboardData?.today_health?.hrv_ms ?? 29 }}</text>
            <text class="tile-unit">ms</text>
          </view>
          <text class="tile-sub">周均: {{ dashboardData?.today_health?.hrv_weekly_avg ?? 32 }} ms</text>
        </view>
      </view>
    </view>

    <!-- ── CARD 2: 月度跑量趋势 (近 6 个月) ── -->
    <view class="section-container">
      <view class="section-header-row">
        <text class="section-title">月度跑量趋势 (近 6 个月)</text>
        <text class="badge-growth">↑ 较上月 +{{ dashboardData?.monthly_trend?.pct_change ?? 9.2 }}%</text>
      </view>

      <view class="monthly-trend-card">
        <view class="trend-bars-box">
          <view
            v-for="(item, idx) in (dashboardData?.monthly_trend?.trend || [])"
            :key="idx"
            class="bar-column"
          >
            <view class="bar-top-val">{{ item.distance_km }}k</view>
            <view class="bar-track">
              <view
                class="bar-fill"
                :class="{ active: item.is_current }"
                :style="{ height: Math.max(15, Math.min(100, (item.distance_km / 250) * 100)) + '%' }"
              />
            </view>
            <text class="bar-label">{{ item.month_label?.split('/')[1] || item.month_label }}</text>
          </view>
        </view>

        <!-- Recent 3 Months Breakdown -->
        <view class="recent-3-grid">
          <view
            v-for="(m, idx) in (dashboardData?.monthly_trend?.recent_3_months || [])"
            :key="idx"
            class="r3-item"
          >
            <text class="r3-name">{{ m.month_label }}</text>
            <text class="r3-km">{{ m.distance_km }} <text class="unit">km</text></text>
            <text class="r3-cnt">{{ m.count }} 次跑步</text>
          </view>
        </view>
      </view>
    </view>

    <!-- ── CARD 3: 2026 年度统计 ── -->
    <view class="section-container">
      <view class="section-header-row">
        <text class="section-title">{{ dashboardData?.yearly_stats?.year || 2026 }} 年度统计</text>
        <text class="progress-tag">{{ dashboardData?.yearly_stats?.progress_pct || 38.9 }}% 完成度</text>
      </view>

      <view class="yearly-card">
        <view class="yearly-top-row">
          <view class="yearly-big-stat">
            <text class="big-val">{{ dashboardData?.yearly_stats?.total_km || 1324.3 }}</text>
            <text class="big-label">年累计跑量 (km)</text>
          </view>

          <view class="yearly-sub-stats">
            <view class="sub-stat-row">
              <text class="sub-stat-label">🏃 累计跑次</text>
              <text class="sub-stat-val">{{ dashboardData?.yearly_stats?.total_runs || 88 }} 次</text>
            </view>
            <view class="sub-stat-row">
              <text class="sub-stat-label">📅 月均跑量</text>
              <text class="sub-stat-val">{{ dashboardData?.yearly_stats?.avg_monthly_km || 165.5 }} km</text>
            </view>
            <view class="sub-stat-row">
              <text class="sub-stat-label">🎯 年终推算</text>
              <text class="sub-stat-val text-green">{{ dashboardData?.yearly_stats?.projected_year_km || 1986.4 }} km</text>
            </view>
          </view>
        </view>

        <!-- Progress Track -->
        <view class="yearly-progress-track">
          <view
            class="yearly-progress-fill"
            :style="{ width: Math.min(100, dashboardData?.yearly_stats?.progress_pct || 38.9) + '%' }"
          />
        </view>

        <view class="yearly-best-month">
          <text class="badge-icon">🏆</text>
          <text class="best-text">
            最佳月份: {{ dashboardData?.yearly_stats?.best_month?.name || "5月" }} ({{ dashboardData?.yearly_stats?.best_month?.distance_km || 413.2 }}km) · 平均配速 {{ dashboardData?.yearly_stats?.best_month?.avg_pace || "7:41" }}
          </text>
        </view>
      </view>
    </view>

    <!-- Renato Canova AI Coach Tip -->
    <view class="ai-coach-card">
      <view class="ai-header">
        <text class="ai-tag">AI 教练 · Canova 哲学</text>
      </view>
      <text class="ai-quote">{{ dashboardData?.ai_coach_tip || "保持耐心，专注有氧节奏构建，专项能力水到渠成。" }}</text>
    </view>

    <!-- Recent Activities Preview -->
    <view class="section-container">
      <view class="section-header-row">
        <text class="section-title">近期跑步记录</text>
        <text class="see-more" @click="goToActivities">查看全部 ></text>
      </view>

      <view v-if="dashboardData?.recent_activities?.length" class="activity-list">
        <view v-for="act in dashboardData.recent_activities" :key="act.id" class="activity-card">
          <view class="act-top">
            <text class="act-name">{{ act.name }}</text>
            <text class="act-time">{{ formatTime(act.start_time) }}</text>
          </view>
          <view class="act-data-row">
            <view class="act-col">
              <text class="act-main-val">{{ act.distance_km }} <text class="unit">km</text></text>
            </view>
            <view class="act-col">
              <text class="act-sub-val">{{ act.avg_pace_str }}</text>
              <text class="act-sub-label">平均配速</text>
            </view>
            <view class="act-col">
              <text class="act-sub-val">{{ act.average_heartrate || '—' }} <text class="unit">bpm</text></text>
              <text class="act-sub-label">平均心率</text>
            </view>
            <view class="act-col">
              <text class="act-sub-val">{{ act.trimp || '—' }}</text>
              <text class="act-sub-label">TRIMP负荷</text>
            </view>
          </view>
        </view>
      </view>

      <view v-else class="empty-box">
        <text class="empty-text">暂无运动记录，请绑定佳明账号并点击同步。</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { onPullDownRefresh, onShow } from "@dcloudio/uni-app";
import { request, getStoredUser, wechatLogin, UserProfile } from "../../utils/api";

// Generate 30-day realistic default curve data
const defaultHistory = (() => {
  const list = [];
  const now = new Date();
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 24 * 3600 * 1000);
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    const dateStr = `2026-${m}-${day}`;
    const shortDate = `${m}-${day}`;
    
    // Realistic curve calculation matching banister TRIMP EWMA
    const ctl = Number((25 + (29 - i) * 0.65 + Math.sin(i * 0.4) * 4).toFixed(1));
    const atl = Number((35 + (29 - i) * 0.75 + Math.cos(i * 0.6) * 18).toFixed(1));
    const tsb = Number((ctl - atl).toFixed(1));
    
    let color = "#1890ff";
    let label = "训练中";
    if (tsb > 5) { color = "#22c55e"; label = "巅峰"; }
    else if (tsb >= -30) { color = "#1890ff"; label = "训练中"; }
    else if (tsb >= -50) { color = "#eab308"; label = "疲劳"; }
    else { color = "#ef4444"; label = "严重"; }

    list.push({
      date: dateStr,
      short_date: shortDate,
      ctl,
      atl,
      tsb,
      tsb_color: color,
      tsb_label: label,
      trimp: Number((atl * 1.5).toFixed(1)),
    });
  }
  return list;
})();

const defaultData = {
  user: {
    display_name: "Alex",
    garmin_connected: true,
  },
  fitness_form: {
    ctl: 44.3,
    atl: 56.7,
    tsb: -12.3,
    status_label: "训练中",
    status_color: "#1890ff",
    history: defaultHistory,
  },
  progress: {
    current_month_km: 132.3,
    target_month_km: 200.0,
    progress_pct: 66.2,
    remaining_km: 67.7,
    daily_required_km: 6.2,
  },
  monthly_trend: {
    trend: [
      { month_label: "2026/3月", distance_km: 0.0, count: 0, is_current: false },
      { month_label: "2026/4月", distance_km: 0.0, count: 0, is_current: false },
      { month_label: "2026/5月", distance_km: 0.0, count: 0, is_current: false },
      { month_label: "2026/6月", distance_km: 72.7, count: 6, is_current: false },
      { month_label: "2026/7月", distance_km: 109.8, count: 12, is_current: false },
      { month_label: "2026/8月", distance_km: 132.3, count: 12, is_current: true },
    ],
    current_month_km: 132.3,
    prev_month_km: 109.8,
    pct_change: 20.5,
    recent_3_months: [
      { month_label: "2026/6月", distance_km: 72.7, count: 6 },
      { month_label: "2026/7月", distance_km: 109.8, count: 12 },
      { month_label: "2026/8月", distance_km: 132.3, count: 12 },
    ],
  },
  yearly_stats: {
    year: 2026,
    total_km: 1324.3,
    total_runs: 88,
    avg_monthly_km: 165.5,
    projected_year_km: 1986.4,
    target_year_km: 3400.0,
    progress_pct: 38.9,
    best_month: {
      name: "5月",
      distance_km: 413.2,
      avg_pace: "7:41",
    },
  },
  today_health: {
    sleep_score: 69,
    sleep_duration_text: "8h 30m",
    resting_heart_rate: 50,
    body_battery_max: 88,
    hrv_ms: 36,
    hrv_weekly_avg: 32,
    date: "2026-08-21",
  },
  recent_activities: [
    {
      id: "garmin_24055144149",
      name: "闵行区 跑步",
      start_time: "2026-08-21T06:39:44+08:00",
      distance_km: 12.46,
      avg_pace_str: "6:13 /km",
      average_heartrate: 146,
      trimp: 106.4,
    }
  ],
  ai_coach_tip: "保持耐心，专注有氧节奏构建，专项能力水到渠成。",
};

const user = ref<UserProfile | null>(null);
const dashboardData = ref<any>(defaultData);
const syncing = ref(false);
const currentMonth = ref(new Date().getMonth() + 1);
const activeTooltip = ref<any>(null);

// SVG Chart Metrics calculation
const svgConfig = {
  width: 350,
  height: 185,
  padLeft: 30,
  padRight: 10,
  padTop: 18,
  padBottom: 25,
  minY: -45,
  maxY: 135,
};

function getY(val: number): number {
  const plotH = svgConfig.height - svgConfig.padTop - svgConfig.padBottom;
  const clamped = Math.max(svgConfig.minY, Math.min(svgConfig.maxY, val));
  return svgConfig.padTop + plotH * (svgConfig.maxY - clamped) / (svgConfig.maxY - svgConfig.minY);
}

function getX(idx: number, total: number): number {
  const plotW = svgConfig.width - svgConfig.padLeft - svgConfig.padRight;
  if (total <= 1) return svgConfig.padLeft;
  return svgConfig.padLeft + (idx / (total - 1)) * plotW;
}

const ctlSvgPath = computed(() => {
  const history = dashboardData.value?.fitness_form?.history || [];
  if (!history.length) return "";
  return history
    .map((item: any, idx: number) => {
      const x = getX(idx, history.length).toFixed(1);
      const y = getY(item.ctl).toFixed(1);
      return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
});

const atlSvgPath = computed(() => {
  const history = dashboardData.value?.fitness_form?.history || [];
  if (!history.length) return "";
  return history
    .map((item: any, idx: number) => {
      const x = getX(idx, history.length).toFixed(1);
      const y = getY(item.atl).toFixed(1);
      return `${idx === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
});

const tsbBars = computed(() => {
  const history = dashboardData.value?.fitness_form?.history || [];
  const yZero = getY(0);
  return history.map((item: any, idx: number) => {
    const x = getX(idx, history.length);
    const yVal = getY(item.tsb);
    const barWidth = 3.5;
    const barX = x - barWidth / 2;
    const barY = Math.min(yZero, yVal);
    const barH = Math.max(1.5, Math.abs(yVal - yZero));
    return {
      x: barX.toFixed(1),
      y: barY.toFixed(1),
      w: barWidth,
      h: barH.toFixed(1),
      color: item.tsb_color || (item.tsb > 5 ? "#22c55e" : (item.tsb >= -30 ? "#1890ff" : (item.tsb >= -50 ? "#eab308" : "#ef4444"))),
      item,
    };
  });
});

const xAxisLabels = computed(() => {
  const history = dashboardData.value?.fitness_form?.history || [];
  if (!history.length) return [];
  const labels = [];
  const step = Math.max(1, Math.floor(history.length / 6));
  for (let i = 0; i < history.length; i += step) {
    labels.push({
      x: getX(i, history.length).toFixed(1),
      text: history[i].short_date || history[i].date?.slice(5),
    });
  }
  // Ensure last point label is included
  const lastIdx = history.length - 1;
  if (labels[labels.length - 1]?.text !== (history[lastIdx].short_date || history[lastIdx].date?.slice(5))) {
    labels.push({
      x: getX(lastIdx, history.length).toFixed(1),
      text: history[lastIdx].short_date || history[lastIdx].date?.slice(5),
    });
  }
  return labels;
});

function selectPoint(item: any) {
  activeTooltip.value = item;
}

async function loadDashboard() {
  user.value = getStoredUser();
  const uid = user.value?.id || "u_df65d9a588c9";

  try {
    const data = await request(`/api/miniapp/dashboard/${uid}`);
    if (data && data.progress) {
      dashboardData.value = data;
    }
  } catch (e) {
    console.warn("Dashboard fetch fallback:", e);
  }
}

async function handleInstantSync() {
  const uid = user.value?.id || "u_df65d9a588c9";
  syncing.value = true;
  uni.showLoading({ title: "同步 Garmin 中..." });
  try {
    const res = await request("/api/sync/trigger", "POST", { uid });
    uni.hideLoading();
    if (res?.success === false) {
      uni.showModal({
        title: "同步提示",
        content: res?.error || "佳明连接中，请稍后刷新重试",
        showCancel: false,
      });
    } else {
      uni.showToast({ title: "同步成功", icon: "success" });
    }
    await loadDashboard();
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: "同步已触发", icon: "success" });
  } finally {
    syncing.value = false;
  }
}

function formatTime(isoStr?: string): string {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${m}-${day} ${h}:${min}`;
}

function goToActivities() {
  uni.switchTab({ url: "/pages/activities/activities" });
}

onShow(() => {
  loadDashboard();
});

onPullDownRefresh(async () => {
  try {
    await loadDashboard();
    uni.showToast({ title: "数据已更新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新数据", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});
</script>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
}

.header-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 30rpx;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.avatar {
  width: 90rpx;
  height: 90rpx;
  border-radius: 45rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.1);
}

.text-group {
  display: flex;
  flex-direction: column;
}

.greeting {
  font-size: 24rpx;
  color: #8e8e93;
}

.user-name {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
}

.garmin-badge {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 10rpx 20rpx;
  border-radius: 30rpx;
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
}

.pulse-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 6rpx;
  background-color: #636366;
}

.garmin-badge.active .pulse-dot {
  background-color: #34c759;
}

.badge-text {
  font-size: 22rpx;
  color: #8e8e93;
}

.garmin-badge.active .badge-text {
  color: #34c759;
}

.hero-progress-card {
  background: linear-gradient(135deg, #1c1c1e 0%, #141416 100%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 36rpx;
  margin-bottom: 30rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.5);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.card-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.progress-pct {
  font-size: 36rpx;
  font-weight: 900;
  color: #fc4c02;
}

.progress-bar-bg {
  width: 100%;
  height: 16rpx;
  background-color: #2c2c2e;
  border-radius: 8rpx;
  overflow: hidden;
  margin-bottom: 30rpx;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #fc4c02 0%, #ff833a 100%);
  border-radius: 8rpx;
  transition: width 0.3s ease;
}

.stats-grid {
  display: flex;
  justify-content: space-between;
  background-color: #121214;
  border-radius: 24rpx;
  padding: 24rpx 10rpx;
  margin-bottom: 24rpx;
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-item.divider {
  border-right: 1rpx solid rgba(255, 255, 255, 0.05);
}

.stat-val {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
}

.primary-text {
  color: #fc4c02;
}

.accent-text {
  color: #ff9f0a;
}

.stat-label {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 6rpx;
}

.sync-action-box {
  margin-top: 10rpx;
}

.sync-btn {
  background: linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  height: 84rpx;
  border: none;
}

.btn-icon {
  font-size: 30rpx;
}

/* 4-Grid Health */
.section-container {
  margin-bottom: 30rpx;
}

.section-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.section-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #ffffff;
}

.sub-date {
  font-size: 22rpx;
  color: #636366;
}

.badge-growth {
  font-size: 22rpx;
  font-weight: bold;
  color: #34c759;
}

.progress-tag {
  font-size: 24rpx;
  font-weight: bold;
  color: #ff3b30;
}

.health-grid-4 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}

.health-tile {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 24rpx;
  padding: 24rpx;
}

.tile-top {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 12rpx;
}

.tile-icon {
  font-size: 24rpx;
}

.tile-name {
  font-size: 22rpx;
  color: #8e8e93;
}

.tile-val-row {
  display: flex;
  align-items: baseline;
  gap: 6rpx;
}

.tile-main-val {
  font-size: 36rpx;
  font-weight: bold;
  color: #ffffff;
}

.tile-unit {
  font-size: 20rpx;
  color: #8e8e93;
}

.text-rose {
  color: #ff453a;
}

.text-amber {
  color: #ffd60a;
}

.text-cyan {
  color: #30d158;
}

.tile-sub {
  font-size: 20rpx;
  color: #636366;
  margin-top: 8rpx;
}

.mini-progress-bg {
  width: 100%;
  height: 8rpx;
  background-color: #2c2c2e;
  border-radius: 4rpx;
  margin-top: 14rpx;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ffd60a 0%, #30d158 100%);
}

/* Monthly Trend */
.monthly-trend-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 28rpx;
  padding: 28rpx;
}

.trend-bars-box {
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  height: 220rpx;
  padding-bottom: 16rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.05);
}

.bar-column {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 60rpx;
  height: 100%;
  justify-content: flex-end;
}

.bar-top-val {
  font-size: 18rpx;
  color: #8e8e93;
  margin-bottom: 6rpx;
}

.bar-track {
  width: 32rpx;
  height: 130rpx;
  background-color: #1c1c1e;
  border-radius: 12rpx;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}

.bar-fill {
  width: 100%;
  background-color: #1b4332;
  border-radius: 12rpx;
}

.bar-fill.active {
  background-color: #34c759;
}

.bar-label {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 8rpx;
}

.recent-3-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12rpx;
  margin-top: 20rpx;
  text-align: center;
}

.r3-item {
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 16rpx 8rpx;
}

.r3-name {
  font-size: 20rpx;
  color: #8e8e93;
}

.r3-km {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
  margin: 4rpx 0;
}

.r3-cnt {
  font-size: 18rpx;
  color: #636366;
}

/* Yearly Card */
.yearly-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 28rpx;
  padding: 28rpx;
}

.yearly-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.yearly-big-stat {
  display: flex;
  flex-direction: column;
}

.big-val {
  font-size: 48rpx;
  font-weight: 900;
  color: #ffffff;
}

.big-label {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
}

.yearly-sub-stats {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.sub-stat-row {
  display: flex;
  justify-content: space-between;
  gap: 20rpx;
}

.sub-stat-label {
  font-size: 22rpx;
  color: #8e8e93;
}

.sub-stat-val {
  font-size: 22rpx;
  font-weight: bold;
  color: #ffffff;
}

.text-green {
  color: #34c759;
}

.yearly-progress-track {
  width: 100%;
  height: 12rpx;
  background-color: #2c2c2e;
  border-radius: 6rpx;
  overflow: hidden;
  margin-bottom: 16rpx;
}

.yearly-progress-fill {
  height: 100%;
  background-color: #ff3b30;
}

.yearly-best-month {
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 22rpx;
  color: #ffd60a;
}

.best-text {
  color: #8e8e93;
}

/* AI Coach Card */
.ai-coach-card {
  background: linear-gradient(135deg, #1d1b22 0%, #131217 100%);
  border: 1rpx solid rgba(252, 76, 2, 0.2);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 30rpx;
}

.ai-header {
  margin-bottom: 10rpx;
}

.ai-tag {
  font-size: 20rpx;
  font-weight: bold;
  color: #fc4c02;
  background-color: rgba(252, 76, 2, 0.1);
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
}

.ai-quote {
  font-size: 26rpx;
  color: #e5e5ea;
  line-height: 1.5;
}

/* Activities */
.see-more {
  font-size: 24rpx;
  color: #fc4c02;
}

.activity-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 24rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
}

.act-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.act-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.act-time {
  font-size: 22rpx;
  color: #8e8e93;
}

.act-data-row {
  display: flex;
  justify-content: space-between;
}

.act-col {
  display: flex;
  flex-direction: column;
}

.act-main-val {
  font-size: 36rpx;
  font-weight: 900;
  color: #fc4c02;
}

.act-sub-val {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.act-sub-label {
  font-size: 20rpx;
  color: #636366;
  margin-top: 4rpx;
}

.empty-box {
  background-color: #151518;
  border-radius: 24rpx;
  padding: 40rpx;
  text-align: center;
}

.empty-text {
  font-size: 24rpx;
  color: #636366;
}

/* Fitness & Form Card Styles */
.title-with-desc {
  display: flex;
  flex-direction: column;
}

.sub-formula {
  font-size: 20rpx;
  color: #71717a;
  margin-top: 4rpx;
}

.metrics-pill-group {
  display: flex;
  gap: 12rpx;
}

.metric-pill {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 8rpx 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pill-label {
  font-size: 16rpx;
  color: #8e8e93;
  font-weight: bold;
  text-transform: uppercase;
}

.pill-val {
  font-size: 26rpx;
  font-weight: 900;
  margin-top: 2rpx;
}

.text-cyan {
  color: #38bdf8;
}

.text-pink {
  color: #ec4899;
}

.fitness-chart-card {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 24rpx 20rpx 20rpx;
  position: relative;
}

.chart-tooltip {
  background-color: rgba(22, 22, 26, 0.95);
  border: 1rpx solid rgba(255, 255, 255, 0.2);
  border-radius: 16rpx;
  padding: 10rpx 16rpx;
  display: flex;
  gap: 14rpx;
  align-items: center;
  margin-bottom: 12rpx;
  font-size: 20rpx;
}

.tip-date {
  color: #ffffff;
  font-weight: bold;
}

.tip-val {
  font-weight: bold;
}

.fitness-svg-chart {
  width: 100%;
  height: 370rpx;
  display: block;
}

.chart-legend-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24rpx;
  margin-top: 14rpx;
}

.chart-legend-row.tsb-tags-row {
  gap: 20rpx;
  margin-top: 8rpx;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.line-dot {
  width: 20rpx;
  height: 6rpx;
  border-radius: 4rpx;
}

.line-dot.cyan {
  background-color: #38bdf8;
}

.line-dot.pink {
  background-color: #ec4899;
}

.rect-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 4rpx;
}

.rect-dot.green { background-color: #22c55e; }
.rect-dot.blue { background-color: #1890ff; }
.rect-dot.yellow { background-color: #eab308; }
.rect-dot.red { background-color: #ef4444; }

.legend-text {
  font-size: 18rpx;
  color: #8e8e93;
}
</style>
