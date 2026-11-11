<template>
  <view class="analysis-page" :class="themeClass">
    <!-- 首屏骨架屏：首次进入时盖住尚未加载的数据 -->
    <PageSkeleton v-if="firstLoadPending" overlay />

    <!-- 教练/师傅跨视角调阅顶部横幅 -->
    <view v-if="isInspectingOther" class="inspect-banner">
      <view class="inspect-left">
        <text class="inspect-badge">{{ scienceData?.basic_status_only ? '👤 跑友基本状态视角' : '🔍 教练 / 师傅调阅视角' }}</text>
        <text class="inspect-title">
          正在查看：{{ scienceData?.student_profile?.display_name || targetName || '跑友' }}
          <text v-if="scienceData?.student_profile?.class_name" class="inspect-sub">（{{ scienceData.student_profile.class_name }}）</text>
        </text>
      </view>
      <view class="inspect-back-btn" @click="goBackPage">返回</view>
    </view>

    <!-- ── 跨团 / 未入团跑友：仅展示基本状态名片（隐藏具体运动记录与详细曲线） ── -->
    <view v-if="scienceData?.basic_status_only" class="section-container">
      <view class="vdot-hero-card">
        <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20rpx;">
          <view style="display: flex; align-items: center; gap: 16rpx;">
            <image
              style="width: 88rpx; height: 88rpx; border-radius: 50%; border: 2rpx solid rgba(252,76,2,0.4);"
              :src="scienceData?.basic_status?.avatar_url || scienceData?.student_profile?.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
              mode="aspectFill"
            />
            <view style="display: flex; flex-direction: column; gap: 6rpx;">
              <text style="font-size: 32rpx; font-weight: 800; color: var(--rgm-text, #fff);">
                {{ scienceData?.basic_status?.display_name || scienceData?.student_profile?.display_name || targetName || '跑友' }}
              </text>
              <text style="font-size: 22rpx; color: var(--rgm-text-2, #a1a1aa);">
                ⏰ 注册/入团：{{ scienceData?.basic_status?.joined_at_display || '已注册跑友' }}
              </text>
            </view>
          </view>
          <text class="level-badge">👤 基本状态</text>
        </view>

        <!-- 基本状态三宫格：手表绑定、目标设定、本月进度 -->
        <view style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 14rpx; margin-bottom: 18rpx;">
          <view
            style="padding: 18rpx 20rpx; border-radius: 16rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));"
          >
            <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8rpx;">
              <text style="font-size: 22rpx; font-weight: 700; color: var(--rgm-text, #fff);">⌚ 手表绑定</text>
              <text
                style="font-size: 20rpx; font-weight: 700; padding: 2rpx 12rpx; border-radius: 999rpx;"
                :style="scienceData?.basic_status?.watch_bound ? 'background: rgba(34,197,94,0.18); color: #22c55e;' : 'background: rgba(245,158,11,0.18); color: #f59e0b;'"
              >
                {{ scienceData?.basic_status?.watch_bound ? (scienceData?.basic_status?.watch_status_label || '已绑表') : '未绑定' }}
              </text>
            </view>
            <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa);">
              累计同步 {{ scienceData?.basic_status?.total_runs_count || 0 }} 次跑步
            </text>
          </view>

          <view
            style="padding: 18rpx 20rpx; border-radius: 16rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));"
          >
            <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8rpx;">
              <text style="font-size: 22rpx; font-weight: 700; color: var(--rgm-text, #fff);">🎯 目标设定</text>
              <text
                style="font-size: 20rpx; font-weight: 700; padding: 2rpx 12rpx; border-radius: 999rpx;"
                :style="scienceData?.basic_status?.goal_set ? 'background: rgba(34,197,94,0.18); color: #22c55e;' : 'background: rgba(245,158,11,0.18); color: #f59e0b;'"
              >
                {{ scienceData?.basic_status?.goal_set ? '已设定' : '未设目标' }}
              </text>
            </view>
            <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa);">
              周 {{ scienceData?.basic_status?.weekly_target_km || 50 }}km · 月 {{ scienceData?.basic_status?.monthly_target_km || 200 }}km
            </text>
          </view>
        </view>

        <!-- 本月跑量进度汇总 -->
        <view
          style="padding: 20rpx 22rpx; border-radius: 16rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1)); margin-bottom: 18rpx;"
        >
          <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10rpx;">
            <text style="font-size: 23rpx; font-weight: 700; color: var(--rgm-text, #fff);">📊 本月完成进度</text>
            <text style="font-size: 24rpx; font-weight: 800; color: var(--rgm-brand-text, #fc4c02);">
              {{ scienceData?.basic_status?.month_km || 0 }} / {{ scienceData?.basic_status?.monthly_target_km || 200 }} km ({{ scienceData?.basic_status?.month_progress_pct || 0 }}%)
            </text>
          </view>
          <view class="matrix-bar-bg">
            <view
              class="matrix-bar-fill"
              :style="{ width: Math.min(100, Math.max(4, Number(scienceData?.basic_status?.month_progress_pct || 0))) + '%' }"
            />
          </view>
        </view>

        <!-- 跨跑团隐私保护提示 -->
        <view
          style="padding: 18rpx 20rpx; border-radius: 16rpx; background: rgba(245, 158, 11, 0.12); border: 1rpx solid rgba(245, 158, 11, 0.35);"
        >
          <text style="font-size: 22rpx; font-weight: 700; color: #f59e0b; display: block; margin-bottom: 6rpx;">
            🔒 具体运动记录与生理数据已隐藏
          </text>
          <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa); line-height: 1.45; display: block;">
            {{ scienceData?.privacy_notice || '您与该跑友不在同一个跑团，仅可相互查看基本状态（绑表、目标设定与月跑量进度），不能相互查看具体的运动记录、GPS轨迹与详细生理恢复数据。' }}
          </text>
        </view>
      </view>
    </view>

    <!-- ── CARD 1: 有效 VDOT、耐力保持系数与 Canova 五维矩阵 (首屏核心结论置顶) ── -->
    <template v-else>
    <view class="section-container">
      <view class="vdot-hero-card">
        <view class="vdot-header-flex">
          <view class="vdot-top">
            <view class="vdot-tag-row">
              <text class="vdot-tag">⚡ 有效 VDOT</text>
              <text class="term-info" @click.stop="explainTerm('vdot')">ⓘ</text>
            </view>
            <text class="vdot-val">{{ scienceData?.vdot != null ? scienceData.vdot : "—" }}</text>
          </view>
          <view class="vdot-badges-col">
            <text class="level-badge">{{ vdotLevel(scienceData?.vdot) }}</text>
            <text
              v-if="scienceData?.canova_matrix?.watch_vo2max || scienceData?.vo2max"
              class="endurance-type-badge"
            >
              ⌚ 手表 VO2Max {{ scienceData.canova_matrix?.watch_vo2max || scienceData.vo2max }}
            </text>
            <text v-if="scienceData?.canova_matrix?.runner_type_label" class="endurance-type-badge">
              🧬 {{ scienceData.canova_matrix.runner_type_label }}
            </text>
          </view>
        </view>

        <!-- 恢复/休整期 · 历史巅峰双轨标识 -->
        <view
          v-if="scienceData?.canova_matrix?.recovery_phase_label"
          style="margin: 14rpx 0 6rpx; padding: 12rpx 18rpx; border-radius: 14rpx; background: rgba(245, 158, 11, 0.14); border: 1rpx solid rgba(245, 158, 11, 0.42);"
        >
          <text style="font-size: 22rpx; font-weight: 700; color: #d97706; line-height: 1.4;">
            {{ scienceData.canova_matrix.recovery_phase_label }}
          </text>
        </view>

        <!-- Canova 一句话结论 -->
        <view v-if="scienceData?.canova_matrix?.canova_one_line_summary" class="canova-summary-pill">
          <text class="canova-summary-text">💡 {{ scienceData.canova_matrix.canova_one_line_summary }}</text>
        </view>

        <!-- Canova 专项五维矩阵 (紧凑进度条) -->
        <view v-if="scienceData?.canova_matrix?.dimensions?.length" class="matrix-box">
          <view class="matrix-header-row">
            <view style="display: flex; align-items: center; gap: 6rpx;">
              <text class="matrix-title">📐 Canova 五维矩阵</text>
              <text class="term-info" @click.stop="explainTerm('canova_matrix')">ⓘ</text>
            </view>
            <text class="matrix-overall">综合 {{ scienceData.canova_matrix.overall_score || 0 }} 分</text>
          </view>
          <view class="matrix-list">
            <view
              v-for="dim in scienceData.canova_matrix.dimensions"
              :key="dim.key"
              class="matrix-row"
            >
              <view class="matrix-label-row">
                <text class="matrix-name">{{ dim.label }}</text>
                <view class="matrix-right-meta">
                  <text class="matrix-val">{{ dim.display_value }}</text>
                  <text class="matrix-dot-sep">·</text>
                  <text class="matrix-score">{{ dim.score }}分</text>
                </view>
              </view>
              <view class="matrix-bar-bg">
                <view
                  class="matrix-bar-fill"
                  :style="{ width: Math.min(100, Math.max(8, dim.score)) + '%' }"
                />
              </view>
            </view>
          </view>
        </view>

        <!-- 赛前 7 天减量 (Taper) 状态推演 -->
        <view v-if="scienceData?.taper_simulation?.scenarios?.length" class="taper-sim-box">
          <view class="taper-header-row" @click="showTaperDetail = !showTaperDetail">
            <view class="taper-title-wrap">
              <text class="taper-title">🏁 赛前减量推演</text>
              <text class="term-info" @click.stop="explainTerm('taper_sim')">ⓘ</text>
              <text class="taper-rec-pill">荐：{{ scienceData.taper_simulation.recommended_strategy_label }}</text>
            </view>
            <text class="taper-toggle-link">{{ showTaperDetail ? '收起 ▴' : '展开 ▾' }}</text>
          </view>
          <text class="taper-summary-desc">{{ scienceData.taper_simulation.recommendation_summary }}</text>

          <view v-if="showTaperDetail" class="taper-scenarios-grid">
            <view
              v-for="sc in scienceData.taper_simulation.scenarios"
              :key="sc.key"
              class="taper-sc-card"
              :class="{ active: sc.key === scienceData.taper_simulation.recommended_strategy }"
            >
              <view class="taper-sc-top">
                <text class="taper-sc-name">{{ sc.label }}</text>
                <text class="taper-sc-tsb" :class="sc.projected_day7_tsb >= 5 ? 'tsb-good' : 'tsb-mid'">
                  7天后 TSB: {{ sc.projected_day7_tsb > 0 ? '+' + sc.projected_day7_tsb : sc.projected_day7_tsb }} ({{ sc.readiness_label }})
                </text>
              </view>
              <text class="taper-sc-sub">{{ sc.subtitle }} · 日均 TRIMP {{ sc.daily_trimp }}</text>
            </view>
          </view>
        </view>
      </view>

      <view class="predictions-card">
        <view class="pred-header">
          <text class="pred-icon">🏆</text>
          <text class="pred-title">专项成绩预测</text>
        </view>

        <view class="predictions-grid">
          <view class="pred-tile">
            <text class="dist-label">5K</text>
            <text class="time-val">{{ scienceData?.race_predictions?.five_k || "—" }}</text>
          </view>
          <view class="pred-tile">
            <text class="dist-label">10K</text>
            <text class="time-val">{{ scienceData?.race_predictions?.ten_k || "—" }}</text>
          </view>
          <view class="pred-tile">
            <text class="dist-label">半马</text>
            <text class="time-val text-primary">{{ scienceData?.race_predictions?.half_marathon || "—" }}</text>
          </view>
          <view class="pred-tile">
            <text class="dist-label">全马</text>
            <text class="time-val text-rose">{{ scienceData?.race_predictions?.marathon || "—" }}</text>
          </view>
        </view>
        <text
          v-if="scienceData?.race_predictions?.endurance_note"
          style="display: block; margin-top: 14rpx; font-size: 22rpx; line-height: 1.45; color: #9ca3af;"
        >
          {{ scienceData.race_predictions.endurance_note }}
        </text>
      </view>

      <!-- ── 马拉松官兔六维胜任度评估 ── -->
      <PacerEvaluationCard
        v-if="effectiveRunnerUid"
        :uid="effectiveRunnerUid"
        :viewer-uid="viewerUidRef"
      />
    </view>

    <!-- ── CARD 2: 生理恢复与健康历史趋势 (30天) ── -->
    <view class="section-card">
      <view class="card-header">
        <view class="title-row">
          <text class="card-icon">📊</text>
          <text class="card-title">30天恢复趋势</text>
        </view>
      </view>

      <!-- 保密提示 -->
      <view v-if="scienceData?.biometrics_confidential" class="empty-analysis-box">
        <text class="empty-icon">🔒</text>
        <text class="empty-title">该队员已将生理恢复数据设为保密</text>
        <text class="empty-desc">仅本人、认证教练及师傅可见</text>
      </view>

      <!-- Empty State if no trend data -->
      <view v-else-if="!healthTrend.length" class="empty-analysis-box">
        <text class="empty-icon">📊</text>
        <text class="empty-title">暂无生理历史数据</text>
        <text class="empty-desc">绑定手表后展示近 30 天趋势</text>
        <button v-if="!isInspectingOther" class="rgm-empty-cta" @click="goBindWatch">⌚ 绑定手表</button>
      </view>

      <view v-else>
        <!-- Sub-Chart 1: HRV vs RHR -->
        <view class="sub-chart-box">
          <view class="sub-chart-title-row">
            <text class="sub-chart-icon">💓</text>
            <text class="sub-chart-name">夜间 HRV 与 静息心率 (RHR)</text>
            <text class="term-info" @click.stop="explainTerm('hrv')">ⓘ</text>
          </view>

          <!-- Tooltip -->
          <view v-if="activeHrvTooltip" class="chart-tooltip">
            <view class="date-badge-box">
              <text class="tip-date">{{ activeHrvTooltip.date_label || activeHrvTooltip.date }}</text>
              <text v-if="isLatestDate(activeHrvTooltip.date)" class="latest-pill">最新</text>
            </view>
            <text class="tip-val text-cyan">HRV: {{ activeHrvTooltip.hrv != null ? activeHrvTooltip.hrv : '—' }} ms</text>
            <text class="tip-val text-rose">RHR: {{ activeHrvTooltip.resting_heart_rate != null ? activeHrvTooltip.resting_heart_rate : '—' }} bpm</text>
          </view>

          <canvas
            canvas-id="hrvRhrCanvas"
            v-show="!firstLoadPending"
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
            <text class="tip-val text-indigo">睡眠: {{ activeBatteryTooltip.sleep_score != null ? activeBatteryTooltip.sleep_score : '—' }} 分</text>
            <text class="tip-val text-amber">电量: {{ activeBatteryTooltip.body_battery != null ? activeBatteryTooltip.body_battery : '—' }}%</text>
          </view>

          <canvas
            canvas-id="batterySleepCanvas"
            v-show="!firstLoadPending"
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

    <!-- ── CARD 3: Renato Canova 配速矩阵 (默认折叠，按需展开) ── -->
    <view class="section-card">
      <view class="card-header clickable-header" @click="showCanovaZones = !showCanovaZones">
        <view class="title-row-between">
          <view class="title-row">
            <text class="card-icon">🎯</text>
            <text class="card-title">{{ hasPersonalZones ? 'Canova 专项训练配速区间' : 'Canova 专项训练配速（示例）' }}</text>
          </view>
          <text class="zones-collapse-pill">{{ showCanovaZones ? '收起 ▴' : '展开配速表 ▾' }}</text>
        </view>
      </view>

      <view v-if="showCanovaZones" class="canova-grid">
        <view
          v-for="(zone, key) in canovaZones"
          :key="key"
          class="zone-card"
        >
          <view class="zone-top">
            <text class="zone-name">{{ zone.name }}</text>
            <text class="zone-range">{{ zone.range }}</text>
          </view>
        </view>
      </view>
    </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme, chartPalette } from "../../utils/theme";
import PageSkeleton from "../../components/PageSkeleton.vue";
import PacerEvaluationCard from "../../components/PacerEvaluationCard.vue";
import { explainTerm } from "../../utils/glossary";
import { ref, onMounted, nextTick } from "vue";
import { onPullDownRefresh, onShow, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import { request, getStoredUser, checkAndAutoLogin, syncTabBarIndex, navigateToDeviceBinding } from "../../utils/api";
import { trackClick, trackSubView } from "../../utils/telemetry";

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
const hasPersonalZones = ref(false);
const showCanovaZones = ref(false);
const showTaperDetail = ref(false);
const targetUid = ref("");
const targetName = ref("");
const effectiveRunnerUid = ref("");
const viewerUidRef = ref("");
const isInspectingOther = ref(false);
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
  const P = chartPalette.value;
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

  // Scales - dynamic based on actual dataset to avoid clipping athletic ranges
  const validRhr = data.map((d: any) => d.resting_heart_rate).filter((v: any) => v != null && v > 0);
  const validHrv = data.map((d: any) => d.hrv).filter((v: any) => v != null && v > 0);

  const minRhr = validRhr.length ? Math.max(30, Math.min(...validRhr) - 4) : 40;
  const maxRhr = validRhr.length ? Math.min(100, Math.max(...validRhr) + 4) : 70;

  const minHrv = validHrv.length ? Math.max(10, Math.min(...validHrv) - 8) : 20;
  const maxHrv = validHrv.length ? Math.min(130, Math.max(...validHrv) + 8) : 80;

  const getY_Rhr = (val: number) => padT + plotH * (maxRhr - Math.max(minRhr, Math.min(maxRhr, val))) / Math.max(1, maxRhr - minRhr);
  const getY_Hrv = (val: number) => padT + plotH * (maxHrv - Math.max(minHrv, Math.min(maxHrv, val))) / Math.max(1, maxHrv - minHrv);
  const getX = (idx: number) => padL + (idx / Math.max(1, data.length - 1)) * plotW;

  ctx.clearRect(0, 0, W, H);

  // Gridlines
  [0, 0.5, 1].forEach((pct) => {
    const y = padT + plotH * pct;
    ctx.setStrokeStyle(P.grid);
    ctx.setLineWidth(1);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();
  });

  // HRV Line (Cyan #06b6d4)
  ctx.setStrokeStyle(P.hrv);
  ctx.setLineWidth(2.2);
  ctx.beginPath();
  let startedHrv = false;
  data.forEach((item: any, idx: number) => {
    if (item.hrv != null) {
      const x = getX(idx);
      const y = getY_Hrv(item.hrv);
      if (!startedHrv) {
        ctx.moveTo(x, y);
        startedHrv = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
  });
  ctx.stroke();

  // RHR Line (Rose #ef4444)
  ctx.setStrokeStyle(P.rhr);
  ctx.setLineWidth(2.2);
  ctx.beginPath();
  let startedRhr = false;
  data.forEach((item: any, idx: number) => {
    if (item.resting_heart_rate != null) {
      const x = getX(idx);
      const y = getY_Rhr(item.resting_heart_rate);
      if (!startedRhr) {
        ctx.moveTo(x, y);
        startedRhr = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
  });
  ctx.stroke();

  // X-Axis Labels
  ctx.setFontSize(8.5);
  ctx.setFillStyle(P.axis);
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

      // Vertical line
      ctx.setStrokeStyle(P.cross);
      ctx.setLineWidth(1);
      ctx.beginPath();
      ctx.moveTo(activeX, padT);
      ctx.lineTo(activeX, H - padB);
      ctx.stroke();

      // Highlight Dot - HRV (Cyan)
      if (activeHrvTooltip.value.hrv != null) {
        const activeY_Hrv = getY_Hrv(activeHrvTooltip.value.hrv);
        ctx.setFillStyle(P.hrv);
        ctx.beginPath();
        ctx.arc(activeX, activeY_Hrv, 4.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Highlight Dot - RHR (Rose)
      if (activeHrvTooltip.value.resting_heart_rate != null) {
        const activeY_Rhr = getY_Rhr(activeHrvTooltip.value.resting_heart_rate);
        ctx.setFillStyle(P.rhr);
        ctx.beginPath();
        ctx.arc(activeX, activeY_Rhr, 4.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  ctx.draw();
}

function drawBatterySleepChart() {
  const ctx = uni.createCanvasContext("batterySleepCanvas");
  const P = chartPalette.value;
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
  const getX = (idx: number) => padL + (idx / Math.max(1, data.length - 1)) * plotW;

  ctx.clearRect(0, 0, W, H);

  // Gridlines (0, 50, 100)
  [100, 50, 0].forEach((val) => {
    const y = getY(val);
    ctx.setStrokeStyle(P.grid);
    ctx.setLineWidth(1);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();

    ctx.setFontSize(8.5);
    ctx.setFillStyle(P.axis);
    ctx.setTextAlign("right");
    ctx.fillText(String(val), padL - 4, y + 3);
  });

  // Sleep Score Line (Indigo #818cf8)
  ctx.setStrokeStyle(P.sleep);
  ctx.setLineWidth(2.2);
  ctx.beginPath();
  let startedSleep = false;
  data.forEach((item: any, idx: number) => {
    if (item.sleep_score != null) {
      const x = getX(idx);
      const y = getY(item.sleep_score);
      if (!startedSleep) {
        ctx.moveTo(x, y);
        startedSleep = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
  });
  ctx.stroke();

  // Body Battery Line (Amber #eab308)
  ctx.setStrokeStyle(P.battery);
  ctx.setLineWidth(2.2);
  ctx.beginPath();
  let startedBattery = false;
  data.forEach((item: any, idx: number) => {
    if (item.body_battery != null) {
      const x = getX(idx);
      const y = getY(item.body_battery);
      if (!startedBattery) {
        ctx.moveTo(x, y);
        startedBattery = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
  });
  ctx.stroke();

  // X-Axis Labels
  ctx.setFontSize(8.5);
  ctx.setFillStyle(P.axis);
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

      // Vertical line
      ctx.setStrokeStyle(P.cross);
      ctx.setLineWidth(1);
      ctx.beginPath();
      ctx.moveTo(activeX, padT);
      ctx.lineTo(activeX, H - padB);
      ctx.stroke();

      // Highlight Dot - Sleep (Indigo)
      if (activeBatteryTooltip.value.sleep_score != null) {
        const activeY_Sleep = getY(activeBatteryTooltip.value.sleep_score);
        ctx.setFillStyle(P.sleep);
        ctx.beginPath();
        ctx.arc(activeX, activeY_Sleep, 4.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Highlight Dot - Battery (Amber)
      if (activeBatteryTooltip.value.body_battery != null) {
        const activeY_Battery = getY(activeBatteryTooltip.value.body_battery);
        ctx.setFillStyle(P.battery);
        ctx.beginPath();
        ctx.arc(activeX, activeY_Battery, 4.5, 0, Math.PI * 2);
        ctx.fill();
      }
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
  const currentUid = user.id;
  const uid = targetUid.value || currentUid;
  effectiveRunnerUid.value = uid;
  viewerUidRef.value = currentUid;
  isInspectingOther.value = Boolean(targetUid.value && targetUid.value !== currentUid);
  const viewerQuery = isInspectingOther.value ? `?viewer_uid=${encodeURIComponent(currentUid)}` : "";

  try {
    const [sciRes, healthRes] = await Promise.all([
      request(`/api/science/metrics/${uid}${viewerQuery}`),
      request(`/api/science/health-trend/${uid}${viewerQuery}`)
    ]);

    if (sciRes) {
      scienceData.value = sciRes;
      if (sciRes.basic_status_only) {
        trackSubView(
          "analysis_basic_status_card",
          `查看跨跑团/自由跑友基本状态卡：${targetName.value || uid}`,
          { target_uid: uid, relation_scope: sciRes.relation_scope }
        );
      } else if (isInspectingOther.value) {
        trackSubView(
          "analysis_member_full_report",
          `查看同团/管理视角跑力档案：${targetName.value || uid}`,
          { target_uid: uid }
        );
      }
      if (sciRes.canova_zones && Object.keys(sciRes.canova_zones).length) {
        canovaZones.value = sciRes.canova_zones;
        hasPersonalZones.value = true;
      } else {
        canovaZones.value = defaultCanovaZones;
        hasPersonalZones.value = false;
      }
    }

    if (healthRes?.trend && healthRes.trend.length) {
      healthTrend.value = healthRes.trend;
      const latest = healthRes.trend[healthRes.trend.length - 1];
      activeHrvTooltip.value = latest;
      activeBatteryTooltip.value = latest;
    } else {
      healthTrend.value = [];
    }

    nextTick(() => {
      setTimeout(() => {
        drawHrvRhrChart();
        drawBatterySleepChart();
      }, 150);
    });
  } catch (e) {
    console.warn("Analysis data fetch fallback:", e);
    uni.showToast({ title: "分析数据加载失败，下拉可重试", icon: "none" });
  }
}

function goBackPage() {
  uni.navigateBack({
    fail: () => {
      uni.switchTab({ url: "/pages/team/team" });
    }
  });
}

// 按 VDOT 粗略分级（参考 Jack Daniels 跑力表），替代原先写死的"进阶马拉松跑者"
function vdotLevel(v: number | null | undefined): string {
  if (!v) return "暂未评估";
  if (v < 35) return "入门跑者";
  if (v < 45) return "进阶跑者";
  if (v < 55) return "中高级跑者";
  if (v < 65) return "精英业余跑者";
  return "专业级跑者";
}

function goBindWatch() {
  trackClick("analysis_go_bind_watch", "从身体与跑力分析页去绑定运动手表");
  navigateToDeviceBinding();
}

onMounted(() => {
  nextTick(() => {
    setTimeout(() => {
      drawHrvRhrChart();
      drawBatterySleepChart();
    }, 200);
  });
});

// 首屏骨架屏开关
const firstLoadPending = ref(true);

onShow(() => {
  applySystemTheme(currentTheme.value);
  if (firstLoadPending.value) {
    const timer = setTimeout(() => (firstLoadPending.value = false), 8000);
    Promise.resolve(loadData())
      .catch(() => {})
      .finally(() => {
        clearTimeout(timer);
        firstLoadPending.value = false;
      });
  } else {
    loadData();
  }
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

onLoad((options: any) => {
  if (options?.target_uid) {
    targetUid.value = String(options.target_uid).trim();
  }
  if (options?.target_name) {
    try {
      targetName.value = decodeURIComponent(String(options.target_name));
    } catch {
      targetName.value = String(options.target_name);
    }
  }
  initShareMenu();
});

onShareAppMessage(() => {
  return getUnifiedShareAppMessage();
});

onShareTimeline(() => {
  return getUnifiedShareTimeline();
});
</script>

<style scoped>
.analysis-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  padding: 24rpx 28rpx calc(48rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.inspect-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.16) 0%, rgba(6, 182, 212, 0.12) 100%);
  border: 1rpx solid rgba(16, 185, 129, 0.38);
  border-radius: 24rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 20rpx;
}

.inspect-left {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.inspect-badge {
  font-size: 20rpx;
  font-weight: 800;
  color: #10b981;
}

.inspect-title {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.inspect-sub {
  font-size: 22rpx;
  font-weight: normal;
  color: var(--rgm-text-3, #8e8e93);
}

.inspect-back-btn {
  font-size: 22rpx;
  font-weight: 700;
  color: #10b981;
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
  padding: 10rpx 24rpx;
  border-radius: 999rpx;
}

.header-section {
  margin-bottom: 40rpx;
}

.page-title {
  font-size: 38rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
}


.section-card {
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 32rpx;
  padding: 36rpx 28rpx;
  margin-bottom: 48rpx;
  box-shadow: 0 10rpx 30rpx var(--rgm-shadow, rgba(0, 0, 0, 0.5));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.card-header {
  margin-bottom: 30rpx;
}

.clickable-header {
  margin-bottom: 0;
}

.title-row-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.zones-collapse-pill {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #f97316);
  background: var(--rgm-brand-tint, rgba(249, 115, 22, 0.14));
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
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
  font-size: 30rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}


.empty-analysis-box {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 24rpx;
  padding: 50rpx 30rpx;
  text-align: center;
  margin: 10rpx 0 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.empty-icon {
  font-size: 56rpx;
  margin-bottom: 16rpx;
  display: block;
}

.empty-title {
  font-size: 30rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 10rpx;
  display: block;
}

.empty-desc {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.5;
  display: block;
}

.sub-chart-box {
  margin-bottom: 30rpx;
}

.sub-chart-box.divider-top {
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
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
  color: var(--rgm-text-2, #d4d4d8);
}

.trend-canvas {
  width: 100%;
  height: 360rpx;
  display: block;
}

.chart-tooltip {
  background: var(--rgm-card, linear-gradient(135deg, rgba(30, 30, 36, 0.95) 0%, rgba(20, 20, 24, 0.95) 100%));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  border-radius: 18rpx;
  padding: 12rpx 20rpx;
  display: flex;
  gap: 20rpx;
  align-items: center;
  margin-bottom: 14rpx;
  font-size: 22rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.date-badge-box {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.tip-date {
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  font-family: monospace;
}

.latest-pill {
  font-size: 18rpx;
  background-color: rgba(48, 209, 88, 0.2);
  color: var(--rgm-green, #30d158);
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  font-weight: bold;
}

.tip-val {
  font-weight: bold;
  font-family: monospace;
}

.text-cyan { color: var(--rgm-blue, #06b6d4); }
.text-rose { color: var(--rgm-red, #ef4444); }
.text-indigo { color: var(--rgm-blue, #818cf8); }
.text-amber { color: var(--rgm-amber, #eab308); }

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

.dot.cyan { background-color: #06b6d4;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2); }
.dot.rose { background-color: #ef4444;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2); }
.dot.indigo { background-color: #818cf8;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2); }
.dot.amber { background-color: #eab308;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2); }

.legend-text {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

/* VDOT & Predictions */
.section-container {
  display: flex;
  flex-direction: column;
  gap: 36rpx;
  margin-bottom: 48rpx;
}

.vdot-hero-card {
  background: var(--rgm-card, linear-gradient(135deg, #1c1917 0%, #0c0a09 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(249, 115, 22, 0.3));
  border-radius: 32rpx;
  padding: 36rpx 30rpx;
  box-shadow: 0 10rpx 30rpx var(--rgm-brand-glow, rgba(249, 115, 22, 0.1));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.vdot-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 18rpx;
}

.vdot-top {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.vdot-tag-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.vdot-tag {
  font-size: 22rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #ea580c);
  letter-spacing: 1rpx;
}

.vdot-val {
  font-size: 72rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #f97316);
  line-height: 1;
  font-family: monospace;
}

.vdot-badges-col {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10rpx;
}

.endurance-type-badge {
  font-size: 20rpx;
  font-weight: 800;
  color: #06b6d4;
  background-color: rgba(6, 182, 212, 0.14);
  border: 1rpx solid rgba(6, 182, 212, 0.3);
  padding: 4rpx 16rpx;
  border-radius: 10rpx;
}

.canova-summary-pill {
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.04));
  border-left: 6rpx solid #f97316;
  border-radius: 14rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 24rpx;
}

.canova-summary-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #e4e4e7);
  line-height: 1.5;
}


.matrix-box {
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  padding-top: 24rpx;
  margin-top: 12rpx;
}

.matrix-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
}

.matrix-title {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.matrix-overall {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-brand-text, #f97316);
}

.matrix-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.matrix-row {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.matrix-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
  min-width: 0;
}

.matrix-name {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #d4d4d8);
  white-space: nowrap;
  flex-shrink: 0;
}

.matrix-right-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6rpx;
  flex: 1;
  min-width: 0;
}

.matrix-val {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.matrix-dot-sep {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  flex-shrink: 0;
}

.matrix-score {
  font-size: 22rpx;
  color: var(--rgm-text, #ffffff);
  font-weight: 800;
  white-space: nowrap;
  flex-shrink: 0;
}

.matrix-bar-bg {
  height: 10rpx;
  background-color: var(--rgm-card-2, rgba(255, 255, 255, 0.08));
  border-radius: 999rpx;
  overflow: hidden;
}

.matrix-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #f97316 0%, #fbbf24 100%);
  border-radius: 999rpx;
}

.taper-sim-box {
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  padding-top: 24rpx;
  margin-top: 24rpx;
}

.taper-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.taper-title-wrap {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}

.taper-title {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.taper-rec-pill {
  font-size: 18rpx;
  font-weight: 800;
  color: #10b981;
  background: rgba(16, 185, 129, 0.14);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.taper-toggle-link {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #f97316);
}

.taper-summary-desc {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.45;
  display: block;
}

.taper-scenarios-grid {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-top: 18rpx;
}

.taper-sc-card {
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
}

.taper-sc-card.active {
  border-color: rgba(16, 185, 129, 0.45);
  background: rgba(16, 185, 129, 0.08);
}

.taper-sc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6rpx;
}

.taper-sc-name {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.taper-sc-tsb {
  font-size: 20rpx;
  font-weight: 800;
  font-family: monospace;
}

.tsb-good { color: #10b981; }
.tsb-mid { color: #38bdf8; }

.taper-sc-sub {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.level-badge {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-amber, #fed7aa);
  background-color: var(--rgm-brand-tint, rgba(249, 115, 22, 0.2));
  padding: 4rpx 16rpx;
  border-radius: 10rpx;
}

.predictions-card {
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 32rpx;
  padding: 32rpx 28rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
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
  color: var(--rgm-text, #ffffff);
}

.predictions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}

.pred-tile {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 22rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.dist-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.time-val {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  font-family: monospace;
}

.text-primary {
  color: var(--rgm-brand-text, #fc4c02);
}

.text-rose {
  color: var(--rgm-red, #f43f5e);
}

/* Canova Zones */
.canova-grid {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-top: 28rpx;
}

.zone-card {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 24rpx;
  border-left: 6rpx solid var(--rgm-brand, #fc4c02);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
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
  color: var(--rgm-text, #ffffff);
}

.zone-range {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  font-family: monospace;
}

</style>
