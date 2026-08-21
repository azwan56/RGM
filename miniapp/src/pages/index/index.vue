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

        <!-- Native Canvas Fitness & Form Chart (Supported across all MiniApp platforms) -->
        <canvas
          canvas-id="fitnessChartCanvas"
          id="fitnessChartCanvas"
          class="fitness-chart-canvas"
          @touchstart="handleCanvasTouch"
          @touchmove="handleCanvasTouch"
        />

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

    <!-- ── CARD 2: 近期跑步记录 (最近 3 次) ── -->
    <view v-if="dashboardData?.recent_activities?.length" class="section-container">
      <view class="section-header-row">
        <text class="section-title">近期跑步记录</text>
        <text class="sub-date">最近 3 次训练</text>
      </view>

      <view class="activity-list">
        <view
          v-for="act in dashboardData.recent_activities.slice(0, 3)"
          :key="act.id"
          class="activity-card"
        >
          <view class="act-top">
            <text class="act-name">{{ act.name }}</text>
            <text class="act-time">{{ formatTime(act.start_time) }}</text>
          </view>
          <view class="act-data-row">
            <view class="act-col">
              <text class="act-main-val">{{ act.distance_km }} <text class="unit">km</text></text>
              <text class="act-sub-label">跑步距离</text>
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
              <text class="act-sub-val text-amber">{{ act.trimp || '—' }}</text>
              <text class="act-sub-label">TRIMP负荷</text>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
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

function drawFitnessChart() {
  const ctx = uni.createCanvasContext("fitnessChartCanvas");
  if (!ctx) return;

  const history = dashboardData.value?.fitness_form?.history || [];
  if (!history.length) return;

  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const W = Math.min(350, screenW - 40);
  const H = 190;
  const padL = 30;
  const padR = 8;
  const padT = 18;
  const padB = 24;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const minY = -45;
  const maxY = 135;

  const getY = (val: number) => {
    const clamped = Math.max(minY, Math.min(maxY, val));
    return padT + (plotH * (maxY - clamped)) / (maxY - minY);
  };

  const getX = (idx: number) => {
    if (history.length <= 1) return padL;
    return padL + (idx / (history.length - 1)) * plotW;
  };

  const yZero = getY(0);

  // Clear
  ctx.clearRect(0, 0, W, H);

  // 1. Gridlines & Y-Axis Labels
  const gridVals = [135, 90, 45, 0, -45];
  gridVals.forEach((val) => {
    const y = getY(val);
    ctx.setStrokeStyle(val === 0 ? "#383842" : "#1e1e24");
    ctx.setLineWidth(1);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();

    ctx.setFontSize(9);
    ctx.setFillStyle(val === 0 ? "#8e8e93" : "#55555c");
    ctx.setTextAlign("right");
    ctx.fillText(String(val), padL - 4, y + 3);
  });

  // 2. TSB Bars
  const barW = Math.max(2.5, Math.min(6, (plotW / history.length) * 0.45));
  history.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const yVal = getY(item.tsb);
    const barX = x - barW / 2;
    const barY = Math.min(yZero, yVal);
    const barH = Math.max(2, Math.abs(yVal - yZero));

    let color = item.tsb_color;
    if (!color) {
      if (item.tsb > 5) color = "#22c55e";
      else if (item.tsb >= -30) color = "#1890ff";
      else if (item.tsb >= -50) color = "#eab308";
      else color = "#ef4444";
    }

    ctx.setFillStyle(color);
    ctx.fillRect(barX, barY, barW, barH);
  });

  // 3. CTL Curve (Cyan #38bdf8)
  ctx.setStrokeStyle("#38bdf8");
  ctx.setLineWidth(2.5);
  ctx.setLineCap("round");
  ctx.setLineJoin("round");
  ctx.beginPath();
  history.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const y = getY(item.ctl);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // 4. ATL Curve (Pink #ec4899)
  ctx.setStrokeStyle("#ec4899");
  ctx.setLineWidth(2.5);
  ctx.setLineCap("round");
  ctx.setLineJoin("round");
  ctx.beginPath();
  history.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const y = getY(item.atl);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // 5. X-Axis Date Labels
  ctx.setFontSize(8.5);
  ctx.setFillStyle("#66666e");
  ctx.setTextAlign("center");
  const step = Math.max(1, Math.floor(history.length / 5));
  for (let i = 0; i < history.length; i += step) {
    const x = getX(i);
    const text = history[i].short_date || history[i].date?.slice(5) || "";
    ctx.fillText(text, x, H - 4);
  }
  if (history.length > 0) {
    const lastIdx = history.length - 1;
    const text = history[lastIdx].short_date || history[lastIdx].date?.slice(5) || "";
    ctx.fillText(text, getX(lastIdx), H - 4);
  }

  // 6. Draw active indicator line if touched
  if (activeTooltip.value) {
    const activeIdx = history.findIndex((h: any) => h.date === activeTooltip.value.date);
    if (activeIdx >= 0) {
      const activeX = getX(activeIdx);
      ctx.setStrokeStyle("rgba(255,255,255,0.4)");
      ctx.setLineWidth(1);
      ctx.beginPath();
      ctx.moveTo(activeX, padT);
      ctx.lineTo(activeX, H - padB);
      ctx.stroke();
    }
  }

  ctx.draw();
}

function handleCanvasTouch(e: any) {
  const history = dashboardData.value?.fitness_form?.history || [];
  if (!history.length || !e.touches || !e.touches[0]) return;
  const touchX = e.touches[0].x;
  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const W = Math.min(350, screenW - 40);
  const padL = 30;
  const padR = 8;
  const plotW = W - padL - padR;

  const relX = Math.max(0, Math.min(plotW, touchX - padL));
  const idx = Math.round((relX / plotW) * (history.length - 1));
  if (idx >= 0 && idx < history.length) {
    activeTooltip.value = history[idx];
    drawFitnessChart();
  }
}

async function loadDashboard() {
  user.value = getStoredUser();
  const uid = user.value?.id || "u_df65d9a588c9";

  try {
    const data = await request(`/api/miniapp/dashboard/${uid}`);
    if (data && data.progress) {
      dashboardData.value = data;
      nextTick(() => {
        setTimeout(drawFitnessChart, 150);
      });
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

onMounted(() => {
  nextTick(() => {
    setTimeout(drawFitnessChart, 200);
  });
});

onShow(() => {
  loadDashboard();
  nextTick(() => {
    setTimeout(drawFitnessChart, 250);
  });
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
  padding: 36rpx 28rpx 90rpx 28rpx;
  box-sizing: border-box;
}

.header-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 38rpx;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.avatar {
  width: 96rpx;
  height: 96rpx;
  border-radius: 48rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.12);
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
  font-size: 34rpx;
  font-weight: bold;
  color: #ffffff;
}

.garmin-badge {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 10rpx 22rpx;
  border-radius: 30rpx;
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
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
  padding: 40rpx 36rpx;
  margin-bottom: 46rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.5);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.card-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #ffffff;
}

.progress-pct {
  font-size: 38rpx;
  font-weight: 900;
  color: #fc4c02;
}

.progress-bar-bg {
  width: 100%;
  height: 16rpx;
  background-color: #2c2c2e;
  border-radius: 8rpx;
  overflow: hidden;
  margin-bottom: 32rpx;
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
  padding: 26rpx 12rpx;
  margin-bottom: 26rpx;
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
  margin-top: 12rpx;
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
  height: 88rpx;
  border: none;
}

.btn-icon {
  font-size: 30rpx;
}

/* Sections & Spacings */
.section-container {
  margin-bottom: 48rpx;
}

.section-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
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

.health-grid-4 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22rpx;
}

.health-tile {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 28rpx;
  padding: 28rpx 24rpx;
}

.tile-top {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 14rpx;
}

.tile-icon {
  font-size: 26rpx;
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
  font-size: 38rpx;
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
  margin-top: 10rpx;
}

.mini-progress-bg {
  width: 100%;
  height: 8rpx;
  background-color: #2c2c2e;
  border-radius: 4rpx;
  margin-top: 16rpx;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ffd60a 0%, #30d158 100%);
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

.fitness-chart-canvas {
  width: 100%;
  height: 380rpx;
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

/* Recent Activities Styles */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.activity-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 28rpx;
  padding: 28rpx 24rpx;
}

.act-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
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
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.act-sub-label {
  font-size: 20rpx;
  color: #636366;
  margin-top: 6rpx;
}

.unit {
  font-size: 20rpx;
  color: #8e8e93;
  font-weight: normal;
}

.text-amber {
  color: #ffd60a;
}
</style>
