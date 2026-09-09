<template>
  <view class="analysis-page">
    <!-- Header -->
    <view class="header-section">
      <text class="page-title">跑步科学与体能深度分析</text>
      <text class="page-desc">
        CTL/ATL/TSB 负荷模型 · 30天生理健康趋势 · Jack Daniels VDOT 跑力诊断 · Canova 专项配速矩阵
      </text>
    </view>

    <!-- ── CARD 1: 生理恢复与健康历史趋势 (30天) ── -->
    <view class="section-card">
      <view class="card-header">
        <view class="title-row">
          <text class="card-icon">📊</text>
          <text class="card-title">生理恢复与健康历史趋势 (30天)</text>
        </view>
        <text class="card-sub">对比夜间 HRV、静息心率 (RHR) 与睡眠质量波动（默认自动展示最新数据）</text>
      </view>

      <!-- Empty State if no trend data -->
      <view v-if="!healthTrend.length" class="empty-analysis-box">
        <text class="empty-icon">📊</text>
        <text class="empty-title">暂无生理历史数据</text>
        <text class="empty-desc">请在【我的】页面登录微信并绑定 Garmin / 高驰手表，系统将自动同步夜间 HRV、静息心率与睡眠质量趋势。</text>
      </view>

      <view v-else>
        <!-- Sub-Chart 1: HRV vs RHR -->
        <view class="sub-chart-box">
          <view class="sub-chart-title-row">
            <text class="sub-chart-icon">💓</text>
            <text class="sub-chart-name">夜间 HRV (ms) 与 静息心率 RHR (bpm) 趋势图</text>
          </view>

          <!-- Tooltip -->
          <view v-if="activeHrvTooltip" class="chart-tooltip">
            <view class="date-badge-box">
              <text class="tip-date">{{ activeHrvTooltip.date_label || activeHrvTooltip.date }}</text>
              <text v-if="isLatestDate(activeHrvTooltip.date)" class="latest-pill">最新</text>
            </view>
            <text class="tip-val text-cyan">HRV: {{ activeHrvTooltip.hrv }} ms</text>
            <text class="tip-val text-rose">RHR: {{ activeHrvTooltip.resting_heart_rate }} bpm</text>
          </view>

          <canvas
            canvas-id="hrvRhrCanvas"
            id="hrvRhrCanvas"
            class="trend-canvas"
            @touchstart="handleHrvTouch"
            @touchmove="handleHrvTouch"
          />

          <view class="chart-legend-row">
            <view class="legend-item">
              <view class="dot cyan" />
              <text class="legend-text">夜间 HRV (ms)</text>
            </view>
            <view class="legend-item">
              <view class="dot rose" />
              <text class="legend-text">静息心率 (RHR bpm)</text>
            </view>
          </view>
        </view>

        <!-- Sub-Chart 2: Body Battery vs Sleep Score -->
        <view class="sub-chart-box divider-top">
          <view class="sub-chart-title-row">
            <text class="sub-chart-icon">⚡</text>
            <text class="sub-chart-name">身体电量 (%) 与 睡眠质量得分</text>
          </view>

          <!-- Tooltip -->
          <view v-if="activeBatteryTooltip" class="chart-tooltip">
            <view class="date-badge-box">
              <text class="tip-date">{{ activeBatteryTooltip.date_label || activeBatteryTooltip.date }}</text>
              <text v-if="isLatestDate(activeBatteryTooltip.date)" class="latest-pill">最新</text>
            </view>
            <text class="tip-val text-indigo">睡眠: {{ activeBatteryTooltip.sleep_score }} 分</text>
            <text class="tip-val text-amber">电量: {{ activeBatteryTooltip.body_battery }}%</text>
          </view>

          <canvas
            canvas-id="batterySleepCanvas"
            id="batterySleepCanvas"
            class="trend-canvas"
            @touchstart="handleBatteryTouch"
            @touchmove="handleBatteryTouch"
          />

          <view class="chart-legend-row">
            <view class="legend-item">
              <view class="dot indigo" />
              <text class="legend-text">睡眠质量得分 (分)</text>
            </view>
            <view class="legend-item">
              <view class="dot amber" />
              <text class="legend-text">身体电量 Max (%)</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- ── CARD 2: VDOT & Race Predictions ── -->
    <view class="section-container">
      <view class="vdot-hero-card">
        <view class="vdot-top">
          <text class="vdot-tag">⚡ JACK DANIELS VDOT</text>
          <text class="vdot-val">{{ scienceData?.vdot != null ? scienceData.vdot : "—" }}</text>
          <text class="vdot-desc">基于近期最佳跑步配速与心率区间综合计算的跑力值。</text>
        </view>
        <view class="vdot-level-row">
          <text class="level-label">评估等级: </text>
          <text class="level-badge">{{ scienceData?.vdot ? '进阶马拉松跑者' : '暂未评估' }}</text>
        </view>
      </view>

      <view class="predictions-card">
        <view class="pred-header">
          <text class="pred-icon">🏆</text>
          <text class="pred-title">基于当前跑力的各距离成绩预测 (Race Predictions)</text>
        </view>

        <view class="predictions-grid">
          <view class="pred-tile">
            <text class="dist-label">5 公里</text>
            <text class="time-val">{{ scienceData?.race_predictions?.five_k || "—" }}</text>
          </view>
          <view class="pred-tile">
            <text class="dist-label">10 公里</text>
            <text class="time-val">{{ scienceData?.race_predictions?.ten_k || "—" }}</text>
          </view>
          <view class="pred-tile">
            <text class="dist-label">半程马拉松</text>
            <text class="time-val text-primary">{{ scienceData?.race_predictions?.half_marathon || "—" }}</text>
          </view>
          <view class="pred-tile">
            <text class="dist-label">全程马拉松</text>
            <text class="time-val text-rose">{{ scienceData?.race_predictions?.marathon || "—" }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- ── CARD 3: Renato Canova 配速矩阵 ── -->
    <view class="section-card">
      <view class="card-header">
        <view class="title-row">
          <text class="card-icon">🎯</text>
          <text class="card-title">Renato Canova 马拉松专项配速矩阵</text>
        </view>
        <text class="card-sub">世界顶级中长跑教练卡诺瓦的核心分期训练区间</text>
      </view>

      <view class="canova-grid">
        <view
          v-for="(zone, key) in canovaZones"
          :key="key"
          class="zone-card"
        >
          <view class="zone-top">
            <text class="zone-name">{{ zone.name }}</text>
            <text class="zone-range">{{ zone.range }}</text>
          </view>
          <text class="zone-desc">{{ zone.desc }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import { onPullDownRefresh, onShow } from "@dcloudio/uni-app";
import { request, getStoredUser, checkAndAutoLogin, syncTabBarIndex } from "../../utils/api";

const defaultCanovaZones: Record<string, any> = {
  aerobic_base: {
    name: "基础有氧 (Aerobic Base)",
    range: "5:45 ~ 6:15 /km",
    desc: "主要用于恢复跑与大容量基础耐力构建，保持心率在 Zone 1-2。"
  },
  specific_aerobic: {
    name: "专项有氧 (Specific Aerobic)",
    range: "5:00 ~ 5:25 /km",
    desc: "提升糖原储备和慢肌纤维效率，马拉松长距离渐速跑的重要配速。"
  },
  threshold: {
    name: "乳酸阈值 (Lactate Threshold)",
    range: "4:25 ~ 4:40 /km",
    desc: "提升乳酸清除与耐受能力，抗疲劳专项课的关键配速。"
  },
  special_pace: {
    name: "马拉松专项 (Marathon Special Pace)",
    range: "4:30 ~ 4:45 /km",
    desc: "比赛目标配速 (MP)，专项准备期 15-30km 专项长跑的核心。"
  },
  specific_endurance: {
    name: "专项耐力 (Specific Endurance)",
    range: "4:10 ~ 4:25 /km",
    desc: "半马到10K节奏跑，提高专项速度储备与神经肌肉协调。"
  },
  support_pace: {
    name: "超专项配速 (Support Pace)",
    range: "3:55 ~ 4:10 /km",
    desc: "短间歇与冲刺，增强最大摄氧量 (VO2Max) 与步幅经济性。"
  }
};

const scienceData = ref<any>({
  vdot: null,
  race_predictions: {
    five_k: "—",
    ten_k: "—",
    half_marathon: "—",
    marathon: "—"
  },
  canova_zones: defaultCanovaZones
});

const canovaZones = ref<Record<string, any>>(defaultCanovaZones);
const healthTrend = ref<any[]>([]);
const activeHrvTooltip = ref<any>(null);
const activeBatteryTooltip = ref<any>(null);

function isLatestDate(dateStr: string) {
  if (!healthTrend.value.length) return false;
  const last = healthTrend.value[healthTrend.value.length - 1];
  return last?.date === dateStr;
}

function selectIndex(idx: number) {
  if (!healthTrend.value.length) return;
  const clampedIdx = Math.max(0, Math.min(healthTrend.value.length - 1, idx));
  const target = healthTrend.value[clampedIdx];
  activeHrvTooltip.value = target;
  activeBatteryTooltip.value = target;
  drawHrvRhrChart();
  drawBatterySleepChart();
}

function drawHrvRhrChart() {
  const ctx = uni.createCanvasContext("hrvRhrCanvas");
  if (!ctx) return;

  const data = healthTrend.value || [];
  if (!data.length) return;

  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const W = Math.min(350, screenW - 40);
  const H = 180;
  const padL = 28;
  const padR = 28;
  const padT = 16;
  const padB = 22;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  // Scales
  const minRhr = 45, maxRhr = 65;
  const minHrv = 20, maxHrv = 55;

  const getY_Rhr = (val: number) => padT + plotH * (maxRhr - Math.max(minRhr, Math.min(maxRhr, val))) / (maxRhr - minRhr);
  const getY_Hrv = (val: number) => padT + plotH * (maxHrv - Math.max(minHrv, Math.min(maxHrv, val))) / (maxHrv - minHrv);
  const getX = (idx: number) => padL + (idx / (data.length - 1)) * plotW;

  ctx.clearRect(0, 0, W, H);

  // Gridlines
  [0, 0.5, 1].forEach((pct) => {
    const y = padT + plotH * pct;
    ctx.setStrokeStyle("#1e1e24");
    ctx.setLineWidth(1);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();
  });

  // HRV Line (Cyan #06b6d4)
  ctx.setStrokeStyle("#06b6d4");
  ctx.setLineWidth(2.2);
  ctx.beginPath();
  data.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const y = getY_Hrv(item.hrv);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // RHR Line (Rose #ef4444)
  ctx.setStrokeStyle("#ef4444");
  ctx.setLineWidth(2.2);
  ctx.beginPath();
  data.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const y = getY_Rhr(item.resting_heart_rate);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // X-Axis Labels
  ctx.setFontSize(8.5);
  ctx.setFillStyle("#66666e");
  ctx.setTextAlign("center");
  const step = Math.max(1, Math.floor(data.length / 5));
  for (let i = 0; i < data.length; i += step) {
    ctx.fillText(data[i].date_label, getX(i), H - 4);
  }
  if (data.length > 0) {
    ctx.fillText(data[data.length - 1].date_label, getX(data.length - 1), H - 4);
  }

  // Active Indicator & Highlight Dots
  if (activeHrvTooltip.value) {
    const idx = data.findIndex((d) => d.date === activeHrvTooltip.value.date);
    if (idx >= 0) {
      const activeX = getX(idx);
      const activeY_Hrv = getY_Hrv(activeHrvTooltip.value.hrv);
      const activeY_Rhr = getY_Rhr(activeHrvTooltip.value.resting_heart_rate);

      // Vertical line
      ctx.setStrokeStyle("rgba(255,255,255,0.4)");
      ctx.setLineWidth(1);
      ctx.beginPath();
      ctx.moveTo(activeX, padT);
      ctx.lineTo(activeX, H - padB);
      ctx.stroke();

      // Highlight Dot - HRV (Cyan)
      ctx.setFillStyle("#06b6d4");
      ctx.beginPath();
      ctx.arc(activeX, activeY_Hrv, 4.5, 0, Math.PI * 2);
      ctx.fill();

      // Highlight Dot - RHR (Rose)
      ctx.setFillStyle("#ef4444");
      ctx.beginPath();
      ctx.arc(activeX, activeY_Rhr, 4.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  ctx.draw();
}

function drawBatterySleepChart() {
  const ctx = uni.createCanvasContext("batterySleepCanvas");
  if (!ctx) return;

  const data = healthTrend.value || [];
  if (!data.length) return;

  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const W = Math.min(350, screenW - 40);
  const H = 180;
  const padL = 28;
  const padR = 12;
  const padT = 16;
  const padB = 22;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const getY = (val: number) => padT + plotH * (100 - Math.max(0, Math.min(100, val))) / 100;
  const getX = (idx: number) => padL + (idx / (data.length - 1)) * plotW;

  ctx.clearRect(0, 0, W, H);

  // Gridlines (0, 50, 100)
  [100, 50, 0].forEach((val) => {
    const y = getY(val);
    ctx.setStrokeStyle("#1e1e24");
    ctx.setLineWidth(1);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();

    ctx.setFontSize(8.5);
    ctx.setFillStyle("#66666e");
    ctx.setTextAlign("right");
    ctx.fillText(String(val), padL - 4, y + 3);
  });

  // Sleep Score Line (Indigo #818cf8)
  ctx.setStrokeStyle("#818cf8");
  ctx.setLineWidth(2.2);
  ctx.beginPath();
  data.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const y = getY(item.sleep_score);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Body Battery Line (Amber #eab308)
  ctx.setStrokeStyle("#eab308");
  ctx.setLineWidth(2.2);
  ctx.beginPath();
  data.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const y = getY(item.body_battery);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // X-Axis Labels
  ctx.setFontSize(8.5);
  ctx.setFillStyle("#66666e");
  ctx.setTextAlign("center");
  const step = Math.max(1, Math.floor(data.length / 5));
  for (let i = 0; i < data.length; i += step) {
    ctx.fillText(data[i].date_label, getX(i), H - 4);
  }
  if (data.length > 0) {
    ctx.fillText(data[data.length - 1].date_label, getX(data.length - 1), H - 4);
  }

  // Active Indicator & Highlight Dots
  if (activeBatteryTooltip.value) {
    const idx = data.findIndex((d) => d.date === activeBatteryTooltip.value.date);
    if (idx >= 0) {
      const activeX = getX(idx);
      const activeY_Sleep = getY(activeBatteryTooltip.value.sleep_score);
      const activeY_Battery = getY(activeBatteryTooltip.value.body_battery);

      // Vertical line
      ctx.setStrokeStyle("rgba(255,255,255,0.4)");
      ctx.setLineWidth(1);
      ctx.beginPath();
      ctx.moveTo(activeX, padT);
      ctx.lineTo(activeX, H - padB);
      ctx.stroke();

      // Highlight Dot - Sleep (Indigo)
      ctx.setFillStyle("#818cf8");
      ctx.beginPath();
      ctx.arc(activeX, activeY_Sleep, 4.5, 0, Math.PI * 2);
      ctx.fill();

      // Highlight Dot - Battery (Amber)
      ctx.setFillStyle("#eab308");
      ctx.beginPath();
      ctx.arc(activeX, activeY_Battery, 4.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  ctx.draw();
}

function handleHrvTouch(e: any) {
  if (!healthTrend.value.length || !e.touches || !e.touches[0]) return;
  const touchX = e.touches[0].x;
  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const W = Math.min(350, screenW - 40);
  const padL = 28;
  const padR = 28;
  const plotW = W - padL - padR;

  const relX = Math.max(0, Math.min(plotW, touchX - padL));
  const idx = Math.round((relX / plotW) * (healthTrend.value.length - 1));
  selectIndex(idx);
}

function handleBatteryTouch(e: any) {
  if (!healthTrend.value.length || !e.touches || !e.touches[0]) return;
  const touchX = e.touches[0].x;
  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const W = Math.min(350, screenW - 40);
  const padL = 28;
  const padR = 12;
  const plotW = W - padL - padR;

  const relX = Math.max(0, Math.min(plotW, touchX - padL));
  const idx = Math.round((relX / plotW) * (healthTrend.value.length - 1));
  selectIndex(idx);
}

async function loadData() {
  let user = getStoredUser();
  if (!user) {
    user = await checkAndAutoLogin();
  }
  if (!user || !user.id) return;
  const uid = user.id;

  try {
    const [sciRes, healthRes] = await Promise.all([
      request(`/api/science/metrics/${uid}`),
      request(`/api/science/health-trend/${uid}`)
    ]);

    if (sciRes) {
      scienceData.value = sciRes;
      if (sciRes.canova_zones) {
        canovaZones.value = sciRes.canova_zones;
      }
    }

    if (healthRes?.trend && healthRes.trend.length) {
      healthTrend.value = healthRes.trend;
      const latest = healthRes.trend[healthRes.trend.length - 1];
      activeHrvTooltip.value = latest;
      activeBatteryTooltip.value = latest;
    }

    nextTick(() => {
      setTimeout(() => {
        drawHrvRhrChart();
        drawBatterySleepChart();
      }, 150);
    });
  } catch (e) {
    console.warn("Analysis data fetch fallback:", e);
  }
}

onMounted(() => {
  nextTick(() => {
    setTimeout(() => {
      drawHrvRhrChart();
      drawBatterySleepChart();
    }, 200);
  });
});

onShow(() => {
  syncTabBarIndex(2);
  loadData();
});

onPullDownRefresh(async () => {
  try {
    await loadData();
    uni.showToast({ title: "数据已更新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新数据", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});
</script>

<style scoped>
.analysis-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 36rpx 28rpx 90rpx 28rpx;
  box-sizing: border-box;
}

.header-section {
  margin-bottom: 40rpx;
}

.page-title {
  font-size: 38rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
}

.page-desc {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 10rpx;
  display: block;
  line-height: 1.4;
}

.section-card {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 36rpx 28rpx;
  margin-bottom: 48rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.5);
}

.card-header {
  margin-bottom: 30rpx;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.card-icon {
  font-size: 32rpx;
}

.card-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
}

.card-sub {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 8rpx;
  display: block;
}

.empty-analysis-box {
  background-color: #1a1a1e;
  border-radius: 24rpx;
  padding: 50rpx 30rpx;
  text-align: center;
  margin: 10rpx 0 20rpx;
}

.empty-icon {
  font-size: 56rpx;
  margin-bottom: 16rpx;
  display: block;
}

.empty-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #ffffff;
  margin-bottom: 10rpx;
  display: block;
}

.empty-desc {
  font-size: 24rpx;
  color: #8e8e93;
  line-height: 1.5;
  display: block;
}

.sub-chart-box {
  margin-bottom: 30rpx;
}

.sub-chart-box.divider-top {
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
  padding-top: 36rpx;
  margin-bottom: 10rpx;
}

.sub-chart-title-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 18rpx;
}

.sub-chart-icon {
  font-size: 26rpx;
}

.sub-chart-name {
  font-size: 24rpx;
  font-weight: bold;
  color: #d4d4d8;
}

.trend-canvas {
  width: 100%;
  height: 360rpx;
  display: block;
}

.chart-tooltip {
  background: linear-gradient(135deg, rgba(30, 30, 36, 0.95) 0%, rgba(20, 20, 24, 0.95) 100%);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 18rpx;
  padding: 12rpx 20rpx;
  display: flex;
  gap: 20rpx;
  align-items: center;
  margin-bottom: 14rpx;
  font-size: 22rpx;
}

.date-badge-box {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.tip-date {
  color: #ffffff;
  font-weight: bold;
  font-family: monospace;
}

.latest-pill {
  font-size: 18rpx;
  background-color: rgba(48, 209, 88, 0.2);
  color: #30d158;
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  font-weight: bold;
}

.tip-val {
  font-weight: bold;
  font-family: monospace;
}

.text-cyan { color: #06b6d4; }
.text-rose { color: #ef4444; }
.text-indigo { color: #818cf8; }
.text-amber { color: #eab308; }

.chart-legend-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 30rpx;
  margin-top: 16rpx;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 7rpx;
}

.dot.cyan { background-color: #06b6d4; }
.dot.rose { background-color: #ef4444; }
.dot.indigo { background-color: #818cf8; }
.dot.amber { background-color: #eab308; }

.legend-text {
  font-size: 20rpx;
  color: #8e8e93;
}

/* VDOT & Predictions */
.section-container {
  display: flex;
  flex-direction: column;
  gap: 36rpx;
  margin-bottom: 48rpx;
}

.vdot-hero-card {
  background: linear-gradient(135deg, #1c1917 0%, #0c0a09 100%);
  border: 1rpx solid rgba(249, 115, 22, 0.3);
  border-radius: 32rpx;
  padding: 36rpx 30rpx;
  box-shadow: 0 10rpx 30rpx rgba(249, 115, 22, 0.1);
}

.vdot-top {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.vdot-tag {
  font-size: 20rpx;
  font-weight: 900;
  color: #ea580c;
  letter-spacing: 2rpx;
}

.vdot-val {
  font-size: 72rpx;
  font-weight: 900;
  color: #f97316;
  line-height: 1;
  font-family: monospace;
}

.vdot-desc {
  font-size: 22rpx;
  color: #a8a29e;
  line-height: 1.4;
  margin-top: 6rpx;
}

.vdot-level-row {
  margin-top: 24rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.level-label {
  font-size: 22rpx;
  color: #78716c;
}

.level-badge {
  font-size: 22rpx;
  font-weight: bold;
  color: #fed7aa;
  background-color: rgba(249, 115, 22, 0.2);
  padding: 4rpx 16rpx;
  border-radius: 10rpx;
}

.predictions-card {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 32rpx 28rpx;
}

.pred-header {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 24rpx;
}

.pred-icon {
  font-size: 28rpx;
}

.pred-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.predictions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}

.pred-tile {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 22rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.dist-label {
  font-size: 20rpx;
  color: #8e8e93;
}

.time-val {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
  font-family: monospace;
}

.text-primary {
  color: #fc4c02;
}

.text-rose {
  color: #f43f5e;
}

/* Canova Zones */
.canova-grid {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.zone-card {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 24rpx;
  border-left: 6rpx solid #fc4c02;
}

.zone-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.zone-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.zone-range {
  font-size: 24rpx;
  font-weight: bold;
  color: #fc4c02;
  font-family: monospace;
}

.zone-desc {
  font-size: 20rpx;
  color: #8e8e93;
  line-height: 1.4;
}
</style>
