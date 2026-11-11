<template>
  <view v-if="visible" class="gps-modal-root" :class="[themeClass, fontScaleClass]">
    <!-- Backdrop: prevents background page scroll and handles backdrop tap to close -->
    <view class="gps-modal-backdrop" @click="handleClose" @touchmove.stop.prevent />

    <!-- Modal Sheet: Sibling to backdrop, with fixed header and smooth scrollable body -->
    <view class="gps-modal-sheet" @click.stop>
      <!-- Fixed Modal Header -->
      <view class="gps-modal-header">
        <view class="header-left">
          <text class="modal-badge">{{ segmentAnalysis?.mode === 'race' ? '🏆 比赛分段复盘' : '🗺️ 轨迹与分段复盘' }}</text>
          <text class="act-title">{{ activityData?.name || initialActivity?.name || '跑步路线详情' }}</text>
        </view>
        <view class="close-hit" @click="handleClose">
          <text class="close-icon">✕</text>
        </view>
      </view>

      <!-- Scrollable Body with Native WeChat Scrollbar -->
      <scroll-view
        scroll-y="true"
        class="modal-scroll-area"
        enhanced="true"
        :show-scrollbar="true"
        :bounces="true"
      >
        <view class="scroll-content-inner">
          <!-- Sub Header: Distance, Pace, HR, Elev -->
          <view class="activity-hero-stats">
            <view class="hero-stat-item">
              <text class="stat-num orange">{{ distanceKm }}</text>
              <text class="stat-unit">km</text>
            </view>
            <view class="hero-divider" />
            <view class="hero-stat-item">
              <text class="stat-num">{{ activityData?.avg_pace_str || initialActivity?.avg_pace_str || '—' }}</text>
              <text class="stat-lbl">平均配速</text>
            </view>
            <view class="hero-divider" />
            <view class="hero-stat-item">
              <text class="stat-num text-rose">{{ activityData?.average_heartrate || initialActivity?.average_heartrate || '—' }}</text>
              <text class="stat-lbl">心率 (bpm)</text>
            </view>
            <view class="hero-divider" />
            <view class="hero-stat-item">
              <text class="stat-num text-emerald">+{{ Math.round(elevationGain) }}</text>
              <text class="stat-lbl">爬升 (m)</text>
            </view>
          </view>

          <!-- Tab Switcher (路线地图 / 分段诊断 / 高程剖面 / 地图切片) -->
          <view class="tab-strip">
            <view
              class="tab-btn"
              :class="{ active: activeTab === 'map' }"
              @click="switchTab('map')"
            >
              <text class="tab-text">🗺️ 轨迹路线</text>
            </view>
            <view
              v-if="hasSegmentSplits || isSegmentHidden"
              class="tab-btn"
              :class="{ active: activeTab === 'segments' }"
              @click="switchTab('segments')"
            >
              <text class="tab-text">⏱️ 分段配速</text>
            </view>
            <view
              v-if="hasElevationProfile"
              class="tab-btn"
              :class="{ active: activeTab === 'elevation' }"
              @click="switchTab('elevation')"
            >
              <text class="tab-text">📈 海拔剖面</text>
            </view>
            <view
              v-if="mapImageUrl && !trackPoints.length"
              class="tab-btn"
              :class="{ active: activeTab === 'image' }"
              @click="switchTab('image')"
            >
              <text class="tab-text">🖼️ 地图切片</text>
            </view>
          </view>

          <!-- Visualizer Stage: Height 250px, allowing lower content to be visible and scrolled to -->
          <view class="visualizer-stage">
            <!-- Loading Spinner -->
            <view v-if="loading" class="loading-box">
              <text class="loading-spinner">⏳</text>
              <text class="loading-tip">正在加载轨迹...</text>
            </view>

            <!-- Error State -->
            <view v-else-if="errorMsg && !trackPoints.length && !mapImageUrl && !segmentAnalysis" class="error-box">
              <text class="error-icon">⚠️</text>
              <text class="error-text">{{ errorMsg }}</text>
            </view>

            <!-- TAB 1: Native Interactive Map -->
            <view v-else-if="activeTab === 'map'" class="map-wrapper">
              <view v-if="trackPoints.length" class="map-inner">
                <map
                  id="trackMap"
                  class="track-map-view"
                  :latitude="trackCenter.latitude"
                  :longitude="trackCenter.longitude"
                  :scale="mapScale"
                  :markers="trackMarkers"
                  :polyline="trackPolylines"
                  :show-location="false"
                  :enable-zoom="true"
                  :enable-scroll="true"
                  :enable-rotate="true"
                  :enable-overlooking="true"
                  :show-compass="true"
                  :show-scale="true"
                  :enable-satellite="isSatellite"
                />

                <!-- Floating Controls: Fit Route, Satellite Toggle, Zoom In/Out -->
                <view class="map-floating-controls">
                  <!-- Fit Route / Reset Bounds -->
                  <view class="map-ctl-btn" @click="fitRoute" hover-class="btn-hover">
                    <text class="ctl-icon">🎯</text>
                    <text class="ctl-text">全貌</text>
                  </view>
                  <!-- Satellite Toggle -->
                  <view class="map-ctl-btn" :class="{ active: isSatellite }" @click="toggleSatellite" hover-class="btn-hover">
                    <text class="ctl-icon">{{ isSatellite ? '🛰️' : '🗺️' }}</text>
                    <text class="ctl-text">{{ isSatellite ? '卫星' : '标准' }}</text>
                  </view>
                  <!-- Zoom In / Zoom Out -->
                  <view class="zoom-btn-group">
                    <view class="zoom-btn" @click="zoomIn" hover-class="btn-hover">
                      <text class="zoom-icon">＋</text>
                    </view>
                    <view class="zoom-divider" />
                    <view class="zoom-btn" @click="zoomOut" hover-class="btn-hover">
                      <text class="zoom-icon">－</text>
                    </view>
                  </view>
                </view>

              </view>
              <view v-else-if="mapImageUrl" class="img-fallback-wrapper">
                <image class="fallback-map-img" :src="mapImageUrl" mode="aspectFit" />
                <view class="map-corner-pill">
                  <text class="pill-text">🗺️ COROS 航迹路线</text>
                </view>
              </view>
              <view v-else class="empty-track-box">
                <text class="empty-icon">📍</text>
                <text class="empty-text">无 GPS 轨迹（室内跑/跑步机）</text>
              </view>
            </view>

            <!-- TAB 2: Elevation Profile View -->
            <view v-else-if="activeTab === 'elevation'" class="elevation-wrapper">
              <view class="elevation-stats-bar">
                <view class="elev-stat">
                  <text class="el-label">最高海拔</text>
                  <text class="el-val text-orange">{{ maxElevation }} m</text>
                </view>
                <view class="elev-stat">
                  <text class="el-label">最低海拔</text>
                  <text class="el-val text-blue">{{ minElevation }} m</text>
                </view>
                <view class="elev-stat">
                  <text class="el-label">累计爬升</text>
                  <text class="el-val text-emerald">+{{ Math.round(elevationGain) }} m</text>
                </view>
              </view>

              <!-- Interactive Elevation Profile with Native Image SVG + Scrub Layer -->
              <view class="chart-box">
                <!-- Active Scrubbing Reading Banner -->
                <view v-if="scrubPoint" class="scrub-tip-banner">
                  <text class="scrub-dist">📍 距离 {{ scrubPoint.dist_km }}km</text>
                  <text class="scrub-elev">⛰️ 海拔 {{ Math.round(scrubPoint.elevation_m) }}m</text>
                  <text v-if="scrubPoint.hr" class="scrub-hr">❤️ {{ scrubPoint.hr }}bpm</text>
                </view>
                <view v-else class="scrub-hint-banner">
                  <text class="scrub-hint">👆 左右滑动查看里程与海拔</text>
                </view>

                <!-- Elevation Graphic Container -->
                <view
                  class="elev-graphic-container"
                  @touchstart="handleScrubTouch"
                  @touchmove="handleScrubTouch"
                  @touchend="handleScrubEnd"
                >
                  <image
                    v-if="elevationSvgDataUri"
                    class="elev-svg-img"
                    :src="elevationSvgDataUri"
                    mode="scaleToFill"
                  />
                  <!-- Interactive Cursor Line when scrubbing -->
                  <view
                    v-if="scrubCursorX >= 0"
                    class="scrub-cursor-line"
                    :style="{ left: scrubCursorX + 'px' }"
                  >
                    <view class="cursor-dot" :style="{ top: scrubCursorY + 'px' }" />
                  </view>
                </view>
              </view>
            </view>

            <!-- TAB 3: Static Image -->
            <view v-else-if="activeTab === 'image'" class="image-wrapper">
              <image class="official-map-img" :src="mapImageUrl" mode="widthFix" />
            </view>

            <!-- TAB 4: Splits & Phase Timeline Bar -->
            <view v-else-if="activeTab === 'segments'" class="splits-stage-wrapper">
              <view v-if="isSegmentHidden" class="empty-track-box">
                <text class="empty-icon">🔒</text>
                <text class="empty-text">{{ segmentHiddenMsg || '已开启隐私保护，仅本人、师傅及教练可见' }}</text>
              </view>
              <scroll-view v-else scroll-y="true" class="splits-stage-scroll">
                <!-- Proportional Phase Timeline Bar -->
                <view v-if="phaseBlocks.length" class="phase-bar-section">
                  <view class="phase-bar-track">
                    <view
                      v-for="(blk, bi) in phaseBlocks"
                      :key="bi"
                      class="phase-bar-seg"
                      :class="'seg-' + blk.colorClass"
                      :style="{ width: blk.widthPct + '%' }"
                    />
                  </view>
                  <view class="phase-legend-row">
                    <view v-for="(blk, bi) in phaseBlocks" :key="'lg-' + bi" class="phase-legend-item">
                      <view class="legend-dot" :class="'seg-' + blk.colorClass" />
                      <text class="legend-txt">{{ blk.shortLabel }} {{ blk.distance_km }}k</text>
                    </view>
                  </view>
                </view>

                <!-- Per-Km / Lap Bars -->
                <view v-if="splitBars.length" class="km-splits-table">
                  <view class="km-table-head">
                    <text class="km-col-idx">分段</text>
                    <text class="km-col-bar">配速分布</text>
                    <text class="km-col-pace">配速</text>
                    <text class="km-col-hr">心率</text>
                  </view>
                  <view v-for="(sp, si) in splitBars" :key="si" class="km-row">
                    <text class="km-col-idx">{{ sp.label }}</text>
                    <view class="km-col-bar">
                      <view class="km-bar-bg">
                        <view
                          class="km-bar-fill"
                          :class="{ fastest: sp.isFastest }"
                          :style="{ width: sp.barPct + '%' }"
                        />
                      </view>
                    </view>
                    <text class="km-col-pace">{{ sp.paceShort }}</text>
                    <text class="km-col-hr">{{ sp.avg_hr ? sp.avg_hr : '—' }}</text>
                  </view>
                </view>
              </scroll-view>
            </view>
          </view>

          <!-- Structured Segment & Preset-Race Diagnosis Card -->
          <view v-if="isSegmentHidden" class="segment-privacy-card">
            <text class="seg-lock-icon">🔒</text>
            <text class="seg-lock-text">{{ segmentHiddenMsg || '已开启隐私保护，仅本人、师傅及教练可见' }}</text>
          </view>

          <view v-else-if="segmentAnalysis" class="segment-diag-card">
            <view class="seg-diag-header">
              <view class="seg-diag-title-row">
                <text class="seg-mode-pill" :class="'mode-' + segmentAnalysis.mode">{{ segmentAnalysis.mode_label }}</text>
                <text v-if="segmentAnalysis.is_track_run" class="seg-track-pill">🏟️ 田径场</text>
              </view>
              <text class="seg-summary-title">{{ segmentAnalysis.summary_title }}</text>
            </view>

            <!-- Preset Race Split & Attribution Highlight -->
            <view v-if="segmentAnalysis.race_diagnosis" class="race-highlight-box">
              <text class="race-verdict-line">{{ segmentAnalysis.race_diagnosis.goal_verdict }}</text>
              <view v-if="segmentAnalysis.race_diagnosis.half_split" class="race-split-strip">
                <text class="race-split-badge">{{ segmentAnalysis.race_diagnosis.half_split.split_label }}</text>
                <text class="race-split-sub">
                  前半 {{ segmentAnalysis.race_diagnosis.half_split.first_half_pace }} · 后半 {{ segmentAnalysis.race_diagnosis.half_split.second_half_pace }}
                </text>
              </view>
              <text class="race-cause-line">{{ segmentAnalysis.race_diagnosis.cause_title }}</text>
            </view>

            <!-- Planned Workout Main-Set Comparison KPIs -->
            <view v-else-if="segmentAnalysis.plan_comparison" class="plan-comp-grid">
              <view class="plan-kpi-item">
                <text class="plan-kpi-lbl">{{ segmentAnalysis.plan_comparison.has_wucd_structure ? '主课达成' : '课表达成' }}</text>
                <text class="plan-kpi-val brand">{{ segmentAnalysis.plan_comparison.compliance_pct }}%</text>
                <text class="plan-kpi-sub">{{ segmentAnalysis.plan_comparison.actual_main_km }}/{{ segmentAnalysis.plan_comparison.planned_main_km }}km</text>
              </view>
              <view class="plan-kpi-item">
                <text class="plan-kpi-lbl">主课配速</text>
                <text class="plan-kpi-val">{{ segmentAnalysis.plan_comparison.actual_main_pace_str }}</text>
                <text class="plan-kpi-sub">目标 {{ segmentAnalysis.plan_comparison.target_pace_str }}</text>
              </view>
              <view class="plan-kpi-item">
                <text class="plan-kpi-lbl">稳态心率</text>
                <text class="plan-kpi-val rose">{{ segmentAnalysis.plan_comparison.actual_main_steady_hr ? segmentAnalysis.plan_comparison.actual_main_steady_hr + 'bpm' : '—' }}</text>
                <text class="plan-kpi-sub">
                  {{ segmentAnalysis.plan_comparison.aerobic_decoupling_pct !== null && segmentAnalysis.plan_comparison.aerobic_decoupling_pct !== undefined
                    ? '解耦率 ' + segmentAnalysis.plan_comparison.aerobic_decoupling_pct + '%'
                    : (segmentAnalysis.plan_comparison.target_hr_str || '生理稳态') }}
                </text>
              </view>
            </view>

            <!-- Phase-by-Phase Cards -->
            <view class="phase-cards-list">
              <view v-for="(ph, pidx) in segmentAnalysis.phases" :key="pidx" class="phase-card-item">
                <view class="phase-card-top">
                  <view class="phase-card-name-wrap">
                    <text class="phase-card-name">{{ ph.label }}</text>
                    <text class="phase-card-range">{{ ph.range_str }} · {{ ph.distance_km }}km</text>
                  </view>
                  <text v-if="ph.status_tag" class="phase-status-tag" :class="{ warn: ph.status_tag.includes('⚠️') }">
                    {{ ph.status_tag }}
                  </text>
                </view>
                <view class="phase-metrics-inline">
                  <text class="pm-chip">⏱️ {{ ph.pace_str }}</text>
                  <text class="pm-chip">⌛ {{ ph.duration_str }}</text>
                  <text v-if="ph.steady_hr" class="pm-chip hr">❤️ 稳态 {{ ph.steady_hr }}bpm</text>
                  <text v-if="ph.elev_gain_m >= 8" class="pm-chip">⛰️ +{{ Math.round(ph.elev_gain_m) }}m</text>
                </view>
                <text v-if="ph.comment" class="phase-card-comment">{{ ph.comment }}</text>
              </view>
            </view>

            <!-- Actionable Coach Advice -->
            <view v-if="segmentAnalysis.coach_advice" class="seg-advice-footer">
              <text class="seg-advice-text">💡 {{ segmentAnalysis.coach_advice }}</text>
            </view>
          </view>

          <!-- Canova Coach Critique Card: Fully visible when scrolling down! -->
          <view v-if="coachCritique" class="coach-critique-card">
            <view class="critique-header">
              <view class="critique-header-left">
                <text class="critique-robot">🎯</text>
                <text class="critique-title">Canova 教练复盘</text>
                <text class="ai-generated-tag">量化评估</text>
              </view>
              <text class="critique-compliance-tip">仅供参考</text>
            </view>
            <text class="critique-content">{{ coachCritique }}</text>
          </view>

          <!-- Workout Key Metrics Detail Grid -->
          <view class="workout-details-card">
            <view class="card-mini-title">📊 训练数据</view>
            <view class="details-grid">
              <view v-if="activityData?.sport_type" class="detail-item">
                <text class="detail-lbl">运动类型</text>
                <text class="detail-val">{{ activityData.sport_type }}</text>
              </view>
              <view v-if="activityData?.start_time" class="detail-item">
                <text class="detail-lbl">打卡时间</text>
                <text class="detail-val">{{ formatTime(activityData.start_time) }}</text>
              </view>
              <view v-if="elevationGain" class="detail-item">
                <text class="detail-lbl">累计爬升</text>
                <text class="detail-val text-emerald">+{{ Math.round(elevationGain) }} m</text>
              </view>
              <view v-if="maxElevation" class="detail-item">
                <text class="detail-lbl">最高海拔</text>
                <text class="detail-val text-orange">{{ maxElevation }} m</text>
              </view>
              <view v-if="minElevation" class="detail-item">
                <text class="detail-lbl">最低海拔</text>
                <text class="detail-val text-blue">{{ minElevation }} m</text>
              </view>
              <view v-if="activityData?.average_heartrate" class="detail-item">
                <text class="detail-lbl">平均心率</text>
                <text class="detail-val text-rose">{{ activityData.average_heartrate }} bpm</text>
              </view>
            </view>
          </view>

          <!-- Personal Moments Share Card Action -->
          <view class="track-share-cta-box" @click="emit('share-card', activityData?.id || props.activityId || props.initialActivity?.id || props.initialActivity?.activity_id)">
            <text class="tsc-icon">📸</text>
            <view class="tsc-texts">
              <text class="tsc-title">生成分享卡片</text>
            </view>
            <text class="tsc-arrow">›</text>
          </view>

          <!-- Bottom Safe Spacing -->
          <view class="scroll-bottom-spacer" />
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, getCurrentInstance } from "vue";
import { request, getStoredUser } from "../utils/api";
import { chartPalette, fontScaleClass, themeClass } from "../utils/theme";
import { trackModal, trackSubView } from "../utils/telemetry";

const props = defineProps<{
  visible: boolean;
  activityId?: string;
  initialActivity?: any;
}>();

const emit = defineEmits(["close", "share-card"]);
const instance = getCurrentInstance();

const loading = ref(false);
const errorMsg = ref("");
const activeTab = ref<"map" | "segments" | "elevation" | "image">("map");

watch(
  () => props.visible,
  (val, oldVal) => {
    if (val && !oldVal) {
      trackModal("gps_track", "打开跑步轨迹与分段诊断弹窗", "open", {
        activity_id: props.activityId || props.initialActivity?.id,
      });
    } else if (!val && oldVal) {
      trackModal("gps_track", "关闭跑步轨迹弹窗", "close");
    }
  }
);

watch(activeTab, (tab) => {
  if (!props.visible) return;
  const tabLabels: Record<string, string> = {
    map: "GPS轨迹地图",
    segments: "分段配速与心率诊断",
    elevation: "海拔与心率剖面",
    image: "路线缩略图",
  };
  trackSubView(`track_tab_${tab}`, `轨迹弹窗切换：${tabLabels[tab] || tab}`);
});

const activityData = ref<any>(null);
const trackPoints = ref<Array<{ latitude: number; longitude: number }>>([]);
const elevationProfile = ref<Array<{ dist_km: number; elevation_m: number; hr?: number }>>([]);
const mapImageUrl = ref("");
const segmentAnalysis = ref<any>(null);
const isSegmentHidden = ref(false);
const segmentHiddenMsg = ref("");

const trackCenter = ref<{ latitude: number; longitude: number }>({ latitude: 28.0, longitude: 114.0 });
const mapScale = ref(13);
const isSatellite = ref(false);

// Scrubbing state
const scrubPoint = ref<any>(null);
const scrubCursorX = ref(-1);
const scrubCursorY = ref(0);

const distanceKm = computed(() => {
  const m = activityData.value?.distance_meters || props.initialActivity?.distance_meters || 0;
  return (m / 1000).toFixed(2);
});

const elevationGain = computed(() => {
  return Number(activityData.value?.elevation_gain_meters || props.initialActivity?.elevation_gain_meters || 0);
});

const coachCritique = computed(() => {
  const raw = activityData.value?.ai_journal ?? props.initialActivity?.ai_journal;
  if (!raw) return "";
  if (typeof raw === "object") {
    return String(raw.evaluation || raw.summary || raw.critique || raw.content || "");
  }
  const str = String(raw).trim();
  if (str.startsWith("{")) {
    try {
      const parsed = JSON.parse(str);
      if (parsed && typeof parsed === "object") {
        return String(parsed.evaluation || parsed.summary || parsed.critique || parsed.content || "");
      }
    } catch (_) {}
  }
  return str;
});

const hasElevationProfile = computed(() => {
  return elevationProfile.value && elevationProfile.value.length > 1;
});

const hasSegmentSplits = computed(() => {
  const sa = segmentAnalysis.value;
  return Boolean(sa && ((sa.km_splits && sa.km_splits.length >= 1) || (sa.phases && sa.phases.length >= 1)));
});

const phaseBlocks = computed(() => {
  const phases = segmentAnalysis.value?.phases || [];
  if (!phases.length) return [];
  const totalKm = Math.max(0.1, phases.reduce((acc: number, p: any) => acc + Number(p.distance_km || 0), 0));
  return phases.map((p: any) => {
    const pt = String(p.phase_type || "cruise");
    let colorClass = "brand";
    if (pt === "warmup" || pt === "cooldown" || pt === "start_control") colorClass = "blue";
    else if (pt === "intervals" || pt === "progression" || pt === "final_kick") colorClass = "red";
    else if (pt === "fade" || pt === "wall_zone") colorClass = "amber";
    const rawLbl = String(p.label || "").replace(/^[^\u4e00-\u9fa5A-Za-z0-9]+/, "").split(" ")[0];
    return {
      shortLabel: rawLbl || "分段",
      distance_km: p.distance_km,
      widthPct: Math.max(8, Math.round((Number(p.distance_km || 0) / totalKm) * 100)),
      colorClass,
    };
  });
});

const splitBars = computed(() => {
  const splits = segmentAnalysis.value?.km_splits || [];
  if (!splits.length) return [];
  const paces = splits.map((s: any) => Number(s.pace_sec || 0)).filter((v: number) => v > 0);
  const fastest = paces.length ? Math.min(...paces) : 300;
  const slowest = paces.length ? Math.max(...paces) : 420;
  const span = Math.max(25, slowest - fastest);
  return splits.map((s: any, idx: number) => {
    const pSec = Number(s.pace_sec || fastest);
    // Faster pace -> fuller bar (62% to 100%)
    const ratio = Math.max(0, Math.min(1, (slowest - pSec) / span));
    const barPct = Math.round(58 + ratio * 42);
    const dKm = Number(s.distance_m || 1000) / 1000;
    const lbl = Math.abs(dKm - 1.0) <= 0.12 ? `${idx + 1}km` : `${dKm.toFixed(2)}k`;
    return {
      label: lbl,
      paceShort: String(s.pace_str || "—").replace("/km", ""),
      avg_hr: s.avg_hr || null,
      barPct,
      isFastest: paces.length >= 2 && pSec === fastest,
    };
  });
});

const minElevation = computed(() => {
  if (!elevationProfile.value.length) return 0;
  return Math.min(...elevationProfile.value.map((p) => p.elevation_m));
});

const maxElevation = computed(() => {
  if (!elevationProfile.value.length) return 0;
  return Math.max(...elevationProfile.value.map((p) => p.elevation_m));
});

const trackPolylines = computed(() => {
  if (!trackPoints.value.length) return [];
  return [
    {
      points: trackPoints.value,
      color: "#FC4C02",
      width: 5,
      arrowLine: false,
      borderColor: "#ffffff",
      borderWidth: 1,
    },
  ];
});

const trackMarkers = computed(() => {
  if (!trackPoints.value.length) return [];
  const startPt = trackPoints.value[0];
  const endPt = trackPoints.value[trackPoints.value.length - 1];

  const markers: any[] = [
    {
      id: 1,
      latitude: startPt.latitude,
      longitude: startPt.longitude,
      title: "起点",
      callout: {
        content: "🚩 起点",
        color: "#ffffff",
        bgColor: "#10b981",
        display: "ALWAYS",
        padding: 4,
        borderRadius: 4,
        fontSize: 10,
      },
    },
    {
      id: 2,
      latitude: endPt.latitude,
      longitude: endPt.longitude,
      title: "终点",
      callout: {
        content: "🏁 终点",
        color: "#ffffff",
        bgColor: "#fc4c02",
        display: "ALWAYS",
        padding: 4,
        borderRadius: 4,
        fontSize: 10,
      },
    },
  ];

  // If there's an elevation peak, add summit marker
  if (elevationProfile.value.length > 2 && maxElevation.value > minElevation.value + 50) {
    let peakElev = elevationProfile.value[0];
    for (const p of elevationProfile.value) {
      if (p.elevation_m > peakElev.elevation_m) {
        peakElev = p;
      }
    }
    const totalDist = elevationProfile.value[elevationProfile.value.length - 1].dist_km || 1;
    const ratio = Math.max(0, Math.min(1, peakElev.dist_km / totalDist));
    const idx = Math.min(trackPoints.value.length - 1, Math.round(ratio * (trackPoints.value.length - 1)));
    const peakPt = trackPoints.value[idx];
    if (peakPt && idx > 0 && idx < trackPoints.value.length - 1) {
      markers.push({
        id: 3,
        latitude: peakPt.latitude,
        longitude: peakPt.longitude,
        title: "最高点",
        callout: {
          content: `⛰️ 最高点 ${Math.round(peakElev.elevation_m)}m`,
          color: "#ffffff",
          bgColor: "#8b5cf6",
          display: "ALWAYS",
          padding: 4,
          borderRadius: 4,
          fontSize: 10,
        },
      });
    }
  }

  return markers;
});

// Pure Base64 encoder for universal Mini Program compatibility
const b64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
function base64Encode(str: string): string {
  const utf8Bytes = encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (_, p1) => {
    return String.fromCharCode(parseInt(p1, 16));
  });
  let output = "";
  for (let i = 0; i < utf8Bytes.length; i += 3) {
    const a = utf8Bytes.charCodeAt(i);
    const b = utf8Bytes.charCodeAt(i + 1);
    const c = utf8Bytes.charCodeAt(i + 2);
    output += b64chars.charAt(a >> 2);
    output += b64chars.charAt(((a & 3) << 4) | (b >> 4));
    output += isNaN(b) ? "=" : b64chars.charAt(((b & 15) << 2) | (c >> 6));
    output += isNaN(b) || isNaN(c) ? "=" : b64chars.charAt(c & 63);
  }
  return output;
}

// Generate complete SVG vector graph for the elevation profile
const elevationSvgDataUri = computed(() => {
  const list = elevationProfile.value;
  const P = chartPalette.value;
  if (!list || list.length < 2) return "";

  const W = 330;
  const H = 140;
  const padL = 38;
  const padR = 12;
  const padT = 18;
  const padB = 20;

  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const minE = minElevation.value;
  const maxE = maxElevation.value;
  const diffE = Math.max(20, maxE - minE);

  const totalDist = list[list.length - 1].dist_km || 1;

  const getX = (distKm: number) => Math.round((padL + (distKm / totalDist) * plotW) * 10) / 10;
  const getY = (elevM: number) => Math.round((padT + (plotH * (maxE - elevM)) / diffE) * 10) / 10;

  const pts = list.map((item) => ({
    x: getX(item.dist_km),
    y: getY(item.elevation_m),
    data: item,
  }));

  // Build Line Path
  let lineD = "";
  for (let i = 0; i < pts.length; i++) {
    lineD += i === 0 ? `M ${pts[i].x} ${pts[i].y}` : ` L ${pts[i].x} ${pts[i].y}`;
  }

  // Build Area Path
  const first = pts[0];
  const last = pts[pts.length - 1];
  const bottomY = H - padB;
  const areaD = `${lineD} L ${last.x} ${bottomY} L ${first.x} ${bottomY} Z`;

  // Find Peak
  let peakPt = pts[0];
  for (const p of pts) {
    if (p.data.elevation_m > peakPt.data.elevation_m) {
      peakPt = p;
    }
  }

  // Grid levels
  const gridSteps = [0, 0.5, 1];
  let gridSvg = "";
  gridSteps.forEach((step) => {
    const y = padT + plotH * step;
    const elevVal = Math.round(maxE - step * diffE);
    gridSvg += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="${P.svgGrid}" stroke-width="1" />`;
    gridSvg += `<text x="${padL - 4}" y="${y + 3}" fill="${P.axis}" font-size="9" text-anchor="end" font-family="sans-serif">${elevVal}m</text>`;
  });

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${P.brand}" stop-opacity="0.5" />
        <stop offset="100%" stop-color="${P.brand}" stop-opacity="0.02" />
      </linearGradient>
    </defs>
    ${gridSvg}
    <path d="${areaD}" fill="url(#g)" />
    <path d="${lineD}" fill="none" stroke="${P.brand}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="${peakPt.x}" cy="${peakPt.y}" r="4" fill="#ffffff" stroke="${P.brand}" stroke-width="2" />
    <text x="${peakPt.x}" y="${Math.max(12, peakPt.y - 6)}" fill="${P.brandText}" font-size="9" font-weight="bold" text-anchor="middle" font-family="sans-serif">▲ ${Math.round(peakPt.data.elevation_m)}m</text>
    <text x="${padL}" y="${H - 4}" fill="${P.axis}" font-size="9" text-anchor="start" font-family="sans-serif">0 km</text>
    <text x="${padL + plotW / 2}" y="${H - 4}" fill="${P.axis}" font-size="9" text-anchor="middle" font-family="sans-serif">${(totalDist / 2).toFixed(1)} km</text>
    <text x="${W - padR}" y="${H - 4}" fill="${P.axis}" font-size="9" text-anchor="end" font-family="sans-serif">${totalDist.toFixed(1)} km</text>
  </svg>`;

  return "data:image/svg+xml;base64," + base64Encode(svg);
});

// Interactive touch scrubbing on elevation graphic
function handleScrubTouch(e: any) {
  const list = elevationProfile.value;
  if (!list || list.length < 2) return;

  const touch = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0]);
  if (!touch) return;

  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const containerW = Math.min(330, screenW - 60);

  const padL = 38;
  const padR = 12;
  const plotW = containerW - padL - padR;

  const touchX = typeof touch.x === "number" ? touch.x : (touch.clientX - 30);
  const clampedX = Math.max(padL, Math.min(containerW - padR, touchX));

  const ratio = (clampedX - padL) / plotW;
  const totalDist = list[list.length - 1].dist_km || 1;
  const targetDist = ratio * totalDist;

  let closest = list[0];
  let minDiff = Math.abs(list[0].dist_km - targetDist);
  for (const p of list) {
    const d = Math.abs(p.dist_km - targetDist);
    if (d < minDiff) {
      minDiff = d;
      closest = p;
    }
  }

  scrubPoint.value = closest;
  scrubCursorX.value = clampedX;

  const minE = minElevation.value;
  const maxE = maxElevation.value;
  const diffE = Math.max(20, maxE - minE);
  const normY = (maxE - closest.elevation_m) / diffE;
  scrubCursorY.value = 18 + normY * (140 - 18 - 20);
}

function handleScrubEnd() {
  setTimeout(() => {
    scrubPoint.value = null;
    scrubCursorX.value = -1;
  }, 2500);
}

function switchTab(tab: "map" | "segments" | "elevation" | "image") {
  activeTab.value = tab;
  if (tab === "map") {
    nextTick(() => {
      setTimeout(fitRoute, 250);
    });
  }
}

function toggleSatellite() {
  isSatellite.value = !isSatellite.value;
}

function zoomIn() {
  mapScale.value = Math.min(18, mapScale.value + 1);
}

function zoomOut() {
  mapScale.value = Math.max(3, mapScale.value - 1);
}

function fitRoute() {
  if (!trackPoints.value.length) return;
  const mapCtx = uni.createMapContext("trackMap", instance?.proxy);
  if (mapCtx && typeof mapCtx.includePoints === "function") {
    mapCtx.includePoints({
      points: trackPoints.value,
      padding: [40, 25, 40, 25],
    });
  }
}

function formatTime(t?: string) {
  if (!t) return "";
  const s = t.replace("T", " ");
  return s.length >= 16 ? s.slice(5, 16) : s.slice(0, 16);
}

watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      loadTrack();
    } else {
      resetState();
    }
  },
  { immediate: true }
);

function resetState() {
  activityData.value = null;
  trackPoints.value = [];
  elevationProfile.value = [];
  mapImageUrl.value = "";
  segmentAnalysis.value = null;
  isSegmentHidden.value = false;
  segmentHiddenMsg.value = "";
  errorMsg.value = "";
  activeTab.value = "map";
  mapScale.value = 13;
  isSatellite.value = false;
  scrubPoint.value = null;
  scrubCursorX.value = -1;
}

async function loadTrack() {
  const actId = props.activityId || props.initialActivity?.id;
  if (!actId) return;

  loading.value = true;
  errorMsg.value = "";

  if (props.initialActivity) {
    activityData.value = props.initialActivity;
    mapImageUrl.value = props.initialActivity.map_image_url || "";
  }

  try {
    const storedUser = getStoredUser();
    const viewerQ = storedUser?.id ? `?viewer_uid=${encodeURIComponent(storedUser.id)}` : "";
    const res = await request(`/api/miniapp/activities/${actId}/track${viewerQ}`);
    if (res && res.success) {
      activityData.value = res.activity || activityData.value;
      mapImageUrl.value = res.map_image_url || mapImageUrl.value;
      isSegmentHidden.value = Boolean(res.is_segment_hidden);
      segmentHiddenMsg.value = res.segment_hidden_message || res.message || "";
      segmentAnalysis.value = res.segment_analysis || null;

      if (res.track) {
        const tr = res.track;
        if (tr.points && tr.points.length) {
          trackPoints.value = tr.points;
          trackCenter.value = tr.center || tr.points[0];
        }
        if (tr.elevation_profile && tr.elevation_profile.length) {
          elevationProfile.value = tr.elevation_profile;
        }
      }

      if (!trackPoints.value.length && !mapImageUrl.value && (segmentAnalysis.value || isSegmentHidden.value)) {
        activeTab.value = "segments";
      }
      if (res.is_gps_hidden && !trackPoints.value.length) {
        errorMsg.value = res.message || "该跑者已将运动轨迹与分段诊断设为保密";
      }
    } else {
      errorMsg.value = res?.message || "暂未找到 GPS 轨迹数据";
    }
  } catch (err: any) {
    console.error("Fetch GPS track error:", err);
    errorMsg.value = err.message || "轨迹加载失败";
  } finally {
    loading.value = false;
    nextTick(() => {
      setTimeout(() => {
        if (activeTab.value === "map") {
          fitRoute();
        }
      }, 250);
    });
  }
}

function handleClose() {
  emit("close");
}
</script>

<style scoped>
.gps-modal-root {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 99999 !important;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.gps-modal-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.gps-modal-sheet {
  position: relative;
  z-index: 100000 !important;
  background-color: var(--rgm-card, #18181b);
  border-top-left-radius: 24px;
  border-top-right-radius: 24px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  padding: 18px 16px;
  padding-bottom: calc(20px + constant(safe-area-inset-bottom));
  padding-bottom: calc(20px + env(safe-area-inset-bottom));
  box-shadow: 0 -10px 30px var(--rgm-shadow, rgba(0, 0, 0, 0.5));
  border-top: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gps-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 4px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.modal-badge {
  font-size: 11px;
  color: var(--rgm-brand-text, #FC4C02);
  font-weight: 600;
  text-transform: uppercase;
}

.act-title {
  font-size: 17px;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.close-hit {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
}

.close-icon {
  font-size: 16px;
  color: var(--rgm-text-2, #a1a1aa);
}

/* Scroll Area: Full height scroll with visible scrollbar */
.modal-scroll-area {
  width: 100%;
  max-height: 72vh;
  box-sizing: border-box;
}

.scroll-content-inner {
  display: flex;
  flex-direction: column;
  padding-right: 2px;
}

.activity-hero-stats {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--rgm-card-3, #27272a);
  border-radius: 14px;
  padding: 10px 16px;
  margin-bottom: 12px;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.hero-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hero-divider {
  width: 1px;
  height: 24px;
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
}

.stat-num {
  font-size: 16px;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.stat-num.orange {
  color: var(--rgm-brand-text, #FC4C02);
}

.stat-unit,
.stat-lbl {
  font-size: 10px;
  color: var(--rgm-text-2, #a1a1aa);
  margin-top: 2px;
}

.text-rose {
  color: var(--rgm-red, #fb7185);
}

.text-emerald {
  color: var(--rgm-green, #34d399);
}

.text-orange {
  color: var(--rgm-brand-text, #fb923c);
}

.text-blue {
  color: var(--rgm-blue, #60a5fa);
}

.tab-strip {
  display: flex;
  background-color: var(--rgm-card-3, #27272a);
  border-radius: 10px;
  padding: 3px;
  margin-bottom: 12px;
  gap: 4px;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tab-btn {
  flex: 1;
  text-align: center;
  padding: 6px 0;
  border-radius: 8px;
  transition: all 0.2s;
}

.tab-btn.active {
  background-color: var(--rgm-brand, #FC4C02);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.tab-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--rgm-text-2, #d4d4d8);
}

.tab-btn.active .tab-text {
  color: var(--rgm-text, #ffffff);
}

/* Stage Area: Height 250px so lower coaching advice is immediately reachable */
.visualizer-stage {
  position: relative;
  width: 100%;
  height: 250px;
  margin-bottom: 12px;
}

.loading-box,
.error-box,
.empty-track-box {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.loading-spinner,
.error-icon,
.empty-icon {
  font-size: 28px;
}

.loading-tip,
.error-text,
.empty-text {
  font-size: 12px;
  color: var(--rgm-text-2, #a1a1aa);
  text-align: center;
}

.map-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 16px;
  overflow: hidden;
}

.map-inner {
  position: relative;
  width: 100%;
  height: 100%;
}

.track-map-view {
  width: 100%;
  height: 100%;
  border-radius: 16px;
}

.map-floating-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 100;
}

.map-ctl-btn {
  background-color: var(--rgm-card, rgba(24, 24, 27, 0.9));
  backdrop-filter: blur(6px);
  border: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.18));
  border-radius: 8px;
  padding: 4px 7px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px var(--rgm-shadow, rgba(0, 0, 0, 0.35));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.map-ctl-btn.active {
  border-color: var(--rgm-brand, #FC4C02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.35));
}

.ctl-icon {
  font-size: 13px;
}

.ctl-text {
  font-size: 9px;
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  margin-top: 1px;
}

.zoom-btn-group {
  background-color: var(--rgm-card, rgba(24, 24, 27, 0.9));
  backdrop-filter: blur(6px);
  border: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.18));
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
  box-shadow: 0 4px 12px var(--rgm-shadow, rgba(0, 0, 0, 0.35));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.zoom-btn {
  width: 30px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.zoom-icon {
  font-size: 15px;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.zoom-divider {
  width: 18px;
  height: 1px;
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.15));
}

.btn-hover {
  opacity: 0.75;
}

.map-corner-pill {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background-color: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  padding: 4px 8px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
  z-index: 100;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.pill-text {
  font-size: 10px;
  color: var(--rgm-text, #e4e4e7);
}

.img-fallback-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: var(--rgm-card, #121215);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.fallback-map-img,
.official-map-img {
  max-width: 100%;
  max-height: 100%;
  border-radius: 16px;
  filter: hue-rotate(-52deg) saturate(1.25) contrast(1.08);
}

.elevation-wrapper {
  background-color: var(--rgm-card-3, #27272a);
  border-radius: 16px;
  padding: 10px 14px;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.elevation-stats-bar {
  display: flex;
  justify-content: space-around;
  border-bottom: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  padding-bottom: 6px;
}

.elev-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.el-label {
  font-size: 10px;
  color: var(--rgm-text-2, #a1a1aa);
}

.el-val {
  font-size: 13px;
  font-weight: bold;
  margin-top: 1px;
}

.chart-box {
  width: 100%;
  display: flex;
  flex-direction: column;
  margin-top: 4px;
}

.scrub-tip-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1px solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
  border-radius: 8px;
  padding: 4px 10px;
  margin-bottom: 4px;
}

.scrub-dist,
.scrub-elev,
.scrub-hr {
  font-size: 11px;
  font-weight: bold;
  color: var(--rgm-text, #ffedd5);
}

.scrub-hint-banner {
  display: flex;
  justify-content: center;
  margin-bottom: 2px;
}

.scrub-hint {
  font-size: 10px;
  color: var(--rgm-text-3, #71717a);
}

.elev-graphic-container {
  position: relative;
  width: 100%;
  height: 140px;
}

.elev-svg-img {
  width: 100%;
  height: 100%;
  display: block;
}

.scrub-cursor-line {
  position: absolute;
  top: 15px;
  bottom: 20px;
  width: 1px;
  background-color: rgba(255, 255, 255, 0.75);
  pointer-events: none;
}

.cursor-dot {
  position: absolute;
  left: -5px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background-color: #ffffff;
  border: 2.5px solid var(--rgm-brand, #FC4C02);
  box-shadow: 0 0 6px var(--rgm-brand-glow, rgba(252, 76, 2, 0.8));
}

/* Canova Coach Critique Card: Full visibility in scroll-view */
.coach-critique-card {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(88, 28, 135, 0.28), rgba(30, 27, 75, 0.45)));
  border: 1px solid var(--rgm-brand-line, rgba(168, 85, 247, 0.35));
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.critique-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.critique-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.critique-robot {
  font-size: 15px;
}

.critique-title {
  font-size: 13px;
  font-weight: bold;
  color: var(--rgm-brand-text, #d8b4fe);
}

.ai-generated-tag {
  font-size: 10px;
  color: var(--rgm-brand-text, #c084fc);
  background: var(--rgm-brand-tint, rgba(192, 132, 252, 0.15));
  border: 1px solid var(--rgm-brand-line, rgba(192, 132, 252, 0.3));
  padding: 1px 6px;
  border-radius: 4px;
}

.critique-compliance-tip {
  font-size: 10px;
  color: var(--rgm-text-2, #a1a1aa);
}

.critique-content {
  font-size: 12px;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.6;
}

/* Additional Workout Details Card */
.workout-details-card {
  background-color: var(--rgm-card-3, #27272a);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 12px;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.card-mini-title {
  font-size: 12px;
  font-weight: bold;
  color: var(--rgm-text-2, #a1a1aa);
  margin-bottom: 10px;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 12px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  padding: 6px 10px;
  border-radius: 8px;
}

.detail-lbl {
  font-size: 11px;
  color: var(--rgm-text-3, #71717a);
  white-space: nowrap;
  flex-shrink: 0;
}

.detail-val {
  font-size: 12px;
  font-weight: 600;
  color: var(--rgm-text, #f4f4f5);
  white-space: nowrap;
}

/* Splits & Structured Segment Diagnosis Styles */
.splits-stage-wrapper {
  background-color: var(--rgm-card-3, #27272a);
  border-radius: 16px;
  padding: 10px 12px;
  height: 100%;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.splits-stage-scroll {
  height: 100%;
  width: 100%;
}

.phase-bar-section {
  margin-bottom: 10px;
}

.phase-bar-track {
  display: flex;
  width: 100%;
  height: 10px;
  border-radius: 6px;
  overflow: hidden;
  gap: 2px;
}

.phase-bar-seg {
  height: 100%;
  border-radius: 3px;
}

.seg-blue {
  background-color: var(--rgm-blue, #3b82f6);
}
.seg-brand {
  background-color: var(--rgm-brand, #FC4C02);
}
.seg-red {
  background-color: var(--rgm-red, #ef4444);
}
.seg-amber {
  background-color: var(--rgm-amber, #f59e0b);
}

.phase-legend-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 6px;
}

.phase-legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.legend-txt {
  font-size: 10px;
  color: var(--rgm-text-2, #a1a1aa);
}

.km-splits-table {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.km-table-head {
  display: flex;
  align-items: center;
  font-size: 10px;
  color: var(--rgm-text-3, #71717a);
  padding-bottom: 3px;
  border-bottom: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.km-row {
  display: flex;
  align-items: center;
  font-size: 11px;
}

.km-col-idx {
  width: 42px;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 600;
}

.km-col-bar {
  flex: 1;
  padding-right: 8px;
}

.km-bar-bg {
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  overflow: hidden;
}

.km-bar-fill {
  height: 100%;
  border-radius: 4px;
  background-color: var(--rgm-brand, #FC4C02);
}

.km-bar-fill.fastest {
  background-color: var(--rgm-green, #10b981);
}

.km-col-pace {
  width: 44px;
  text-align: right;
  font-weight: 700;
  color: var(--rgm-text, #f4f4f5);
}

.km-col-hr {
  width: 38px;
  text-align: right;
  color: var(--rgm-red, #fb7185);
  font-weight: 600;
}

.segment-privacy-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  border-radius: 12px;
  background-color: var(--rgm-card-3, #27272a);
  border: 1px dashed var(--rgm-line, rgba(255, 255, 255, 0.14));
}

.seg-lock-icon {
  font-size: 14px;
}

.seg-lock-text {
  font-size: 11px;
  color: var(--rgm-text-2, #a1a1aa);
}

.segment-diag-card {
  background-color: var(--rgm-card-3, #27272a);
  border: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 12px;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.seg-diag-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.seg-diag-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.seg-mode-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  color: var(--rgm-brand-text, #FC4C02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  border: 1px solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
}

.seg-track-pill {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 6px;
  color: var(--rgm-blue, #3b82f6);
  background-color: var(--rgm-tint, rgba(59, 130, 246, 0.1));
}

.seg-summary-title {
  font-size: 14px;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.race-highlight-box {
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.1));
  border: 1px solid var(--rgm-brand-line, rgba(252, 76, 2, 0.28));
  border-radius: 10px;
  padding: 9px 11px;
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.race-verdict-line {
  font-size: 12px;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.race-split-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 4px;
}

.race-split-badge {
  font-size: 11px;
  font-weight: 700;
  color: var(--rgm-brand-text, #FC4C02);
}

.race-split-sub {
  font-size: 10px;
  color: var(--rgm-text-2, #a1a1aa);
}

.race-cause-line {
  font-size: 11px;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.45;
}

.plan-comp-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 10px;
}

.plan-kpi-item {
  background-color: var(--rgm-card, rgba(255, 255, 255, 0.04));
  border: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 10px;
  padding: 7px 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.plan-kpi-lbl {
  font-size: 10px;
  color: var(--rgm-text-3, #71717a);
}

.plan-kpi-val {
  font-size: 13px;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  margin: 2px 0;
}

.plan-kpi-val.brand {
  color: var(--rgm-brand-text, #FC4C02);
}

.plan-kpi-val.rose {
  color: var(--rgm-red, #fb7185);
}

.plan-kpi-sub {
  font-size: 9px;
  color: var(--rgm-text-2, #a1a1aa);
}

.phase-cards-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.phase-card-item {
  background-color: var(--rgm-card, rgba(255, 255, 255, 0.04));
  border: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.07));
  border-radius: 10px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.phase-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.phase-card-name-wrap {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}

.phase-card-name {
  font-size: 12px;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.phase-card-range {
  font-size: 10px;
  color: var(--rgm-text-3, #71717a);
}

.phase-status-tag {
  font-size: 10px;
  font-weight: 700;
  color: var(--rgm-green, #10b981);
}

.phase-status-tag.warn {
  color: var(--rgm-amber, #d97706);
}

.phase-metrics-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pm-chip {
  font-size: 11px;
  font-weight: 600;
  color: var(--rgm-text-2, #d4d4d8);
}

.pm-chip.hr {
  color: var(--rgm-red, #fb7185);
}

.phase-card-comment {
  font-size: 11px;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.45;
}

.seg-advice-footer {
  margin-top: 9px;
  padding-top: 8px;
  border-top: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.seg-advice-text {
  font-size: 11px;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.5;
}

.track-share-cta-box {
  margin-top: 14px;
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  border: 1px solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  display: flex;
  align-items: center;
  gap: 12px;
}

.tsc-icon {
  font-size: 24px;
}

.tsc-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.tsc-title {
  font-size: 14px;
  font-weight: 800;
  color: var(--rgm-brand-text, #FC4C02);
}

.tsc-arrow {
  font-size: 20px;
  font-weight: bold;
  color: var(--rgm-brand-text, #FC4C02);
}

.scroll-bottom-spacer {
  height: 40px;
  padding-bottom: constant(safe-area-inset-bottom);
  padding-bottom: env(safe-area-inset-bottom);
}

/* Custom Sleek Scrollbar */
::-webkit-scrollbar {
  width: 4px;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.05));
}

::-webkit-scrollbar-thumb {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.35));
  border-radius: 4px;
}

</style>
