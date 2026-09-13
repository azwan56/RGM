<template>
  <view v-if="visible" class="gps-modal-root">
    <!-- Backdrop: prevents background page scroll and handles backdrop tap to close -->
    <view class="gps-modal-backdrop" @click="handleClose" @touchmove.stop.prevent />

    <!-- Modal Sheet: Sibling to backdrop, with fixed header and smooth scrollable body -->
    <view class="gps-modal-sheet" @click.stop>
      <!-- Fixed Modal Header -->
      <view class="gps-modal-header">
        <view class="header-left">
          <text class="modal-badge">🗺️ GPS 路线与高程</text>
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

          <!-- Tab Switcher (路线地图 / 高程剖面 / 地图切片) -->
          <view class="tab-strip">
            <view
              class="tab-btn"
              :class="{ active: activeTab === 'map' }"
              @click="switchTab('map')"
            >
              <text class="tab-text">🗺️ 轨迹路线</text>
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
              v-if="mapImageUrl"
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
              <text class="loading-tip">正在获取高精度 GPS 轨迹并完成坐标纠偏...</text>
            </view>

            <!-- Error State -->
            <view v-else-if="errorMsg && !trackPoints.length && !mapImageUrl" class="error-box">
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

                <view class="map-corner-pill">
                  <text class="pill-dot">●</text>
                  <text class="pill-text">GCJ-02 纠偏 · 支持双指缩放/拖拽</text>
                </view>
              </view>
              <view v-else-if="mapImageUrl" class="img-fallback-wrapper">
                <image class="fallback-map-img" :src="mapImageUrl" mode="aspectFit" />
                <view class="map-corner-pill">
                  <text class="pill-text">COROS 官方地图实景</text>
                </view>
              </view>
              <view v-else class="empty-track-box">
                <text class="empty-icon">📍</text>
                <text class="empty-text">该次运动未记录 GPS 轨迹（可能为室内跑或跑步机）</text>
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
                  <text class="scrub-hint">👆 在剖面图上左右滑动，可交互查看沿途里程与海拔</text>
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
          </view>

          <!-- Canova Coach Critique Card: Fully visible when scrolling down! -->
          <view v-if="coachCritique" class="coach-critique-card">
            <view class="critique-header">
              <text class="critique-robot">🤖</text>
              <text class="critique-title">Canova教练专属复盘</text>
            </view>
            <text class="critique-content">{{ coachCritique }}</text>
          </view>

          <!-- Workout Key Metrics Detail Grid -->
          <view class="workout-details-card">
            <view class="card-mini-title">📊 训练核心数据汇总</view>
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

          <!-- Bottom Safe Spacing -->
          <view class="scroll-bottom-spacer" />
        </view>
      </scroll-view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, getCurrentInstance } from "vue";
import { request } from "../utils/api";

const props = defineProps<{
  visible: boolean;
  activityId?: string;
  initialActivity?: any;
}>();

const emit = defineEmits(["close"]);
const instance = getCurrentInstance();

const loading = ref(false);
const errorMsg = ref("");
const activeTab = ref<"map" | "elevation" | "image">("map");

const activityData = ref<any>(null);
const trackPoints = ref<Array<{ latitude: number; longitude: number }>>([]);
const elevationProfile = ref<Array<{ dist_km: number; elevation_m: number; hr?: number }>>([]);
const mapImageUrl = ref("");

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
  return activityData.value?.ai_journal || props.initialActivity?.ai_journal || "";
});

const hasElevationProfile = computed(() => {
  return elevationProfile.value && elevationProfile.value.length > 1;
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
      arrowLine: true,
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
    gridSvg += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="rgba(255,255,255,0.08)" stroke-width="1" />`;
    gridSvg += `<text x="${padL - 4}" y="${y + 3}" fill="#71717a" font-size="9" text-anchor="end" font-family="sans-serif">${elevVal}m</text>`;
  });

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="100%">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#FC4C02" stop-opacity="0.5" />
        <stop offset="100%" stop-color="#FC4C02" stop-opacity="0.02" />
      </linearGradient>
    </defs>
    ${gridSvg}
    <path d="${areaD}" fill="url(#g)" />
    <path d="${lineD}" fill="none" stroke="#FC4C02" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="${peakPt.x}" cy="${peakPt.y}" r="4" fill="#ffffff" stroke="#FC4C02" stroke-width="2" />
    <text x="${peakPt.x}" y="${Math.max(12, peakPt.y - 6)}" fill="#fb923c" font-size="9" font-weight="bold" text-anchor="middle" font-family="sans-serif">▲ ${Math.round(peakPt.data.elevation_m)}m</text>
    <text x="${padL}" y="${H - 4}" fill="#71717a" font-size="9" text-anchor="start" font-family="sans-serif">0 km</text>
    <text x="${padL + plotW / 2}" y="${H - 4}" fill="#71717a" font-size="9" text-anchor="middle" font-family="sans-serif">${(totalDist / 2).toFixed(1)} km</text>
    <text x="${W - padR}" y="${H - 4}" fill="#71717a" font-size="9" text-anchor="end" font-family="sans-serif">${totalDist.toFixed(1)} km</text>
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

function switchTab(tab: "map" | "elevation" | "image") {
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
  return t.replace("T", " ").slice(0, 16);
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
    const res = await request(`/api/miniapp/activities/${actId}/track`);
    if (res && res.success) {
      activityData.value = res.activity || activityData.value;
      mapImageUrl.value = res.map_image_url || mapImageUrl.value;

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
  z-index: 9999;
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
}

.gps-modal-sheet {
  position: relative;
  z-index: 10000;
  background-color: #18181b;
  border-top-left-radius: 24px;
  border-top-right-radius: 24px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  padding: 18px 16px 16px;
  box-shadow: 0 -10px 30px rgba(0, 0, 0, 0.5);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  box-sizing: border-box;
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
  color: #FC4C02;
  font-weight: 600;
  text-transform: uppercase;
}

.act-title {
  font-size: 17px;
  font-weight: bold;
  color: #ffffff;
}

.close-hit {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.1);
}

.close-icon {
  font-size: 16px;
  color: #a1a1aa;
}

/* Scroll Area: Full height scroll with visible scrollbar */
.modal-scroll-area {
  width: 100%;
  max-height: 74vh;
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
  background-color: #27272a;
  border-radius: 14px;
  padding: 10px 16px;
  margin-bottom: 12px;
}

.hero-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.hero-divider {
  width: 1px;
  height: 24px;
  background-color: rgba(255, 255, 255, 0.1);
}

.stat-num {
  font-size: 16px;
  font-weight: 800;
  color: #ffffff;
}

.stat-num.orange {
  color: #FC4C02;
}

.stat-unit,
.stat-lbl {
  font-size: 10px;
  color: #a1a1aa;
  margin-top: 2px;
}

.text-rose {
  color: #fb7185;
}

.text-emerald {
  color: #34d399;
}

.text-orange {
  color: #fb923c;
}

.text-blue {
  color: #60a5fa;
}

.tab-strip {
  display: flex;
  background-color: #27272a;
  border-radius: 10px;
  padding: 3px;
  margin-bottom: 12px;
  gap: 4px;
}

.tab-btn {
  flex: 1;
  text-align: center;
  padding: 6px 0;
  border-radius: 8px;
  transition: all 0.2s;
}

.tab-btn.active {
  background-color: #FC4C02;
}

.tab-text {
  font-size: 12px;
  font-weight: 600;
  color: #d4d4d8;
}

.tab-btn.active .tab-text {
  color: #ffffff;
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
  color: #a1a1aa;
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
  background-color: rgba(24, 24, 27, 0.9);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  padding: 4px 7px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
}

.map-ctl-btn.active {
  border-color: #FC4C02;
  background-color: rgba(252, 76, 2, 0.35);
}

.ctl-icon {
  font-size: 13px;
}

.ctl-text {
  font-size: 9px;
  color: #ffffff;
  font-weight: bold;
  margin-top: 1px;
}

.zoom-btn-group {
  background-color: rgba(24, 24, 27, 0.9);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
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
  color: #ffffff;
}

.zoom-divider {
  width: 18px;
  height: 1px;
  background-color: rgba(255, 255, 255, 0.15);
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
}

.pill-dot {
  font-size: 8px;
  color: #10b981;
}

.pill-text {
  font-size: 10px;
  color: #e4e4e7;
}

.fallback-map-img,
.official-map-img {
  width: 100%;
  height: 100%;
  border-radius: 16px;
}

.elevation-wrapper {
  background-color: #27272a;
  border-radius: 16px;
  padding: 10px 14px;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.elevation-stats-bar {
  display: flex;
  justify-content: space-around;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 6px;
}

.elev-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.el-label {
  font-size: 10px;
  color: #a1a1aa;
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
  background-color: rgba(252, 76, 2, 0.15);
  border: 1px solid rgba(252, 76, 2, 0.4);
  border-radius: 8px;
  padding: 4px 10px;
  margin-bottom: 4px;
}

.scrub-dist,
.scrub-elev,
.scrub-hr {
  font-size: 11px;
  font-weight: bold;
  color: #ffedd5;
}

.scrub-hint-banner {
  display: flex;
  justify-content: center;
  margin-bottom: 2px;
}

.scrub-hint {
  font-size: 10px;
  color: #71717a;
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
  border: 2.5px solid #FC4C02;
  box-shadow: 0 0 6px rgba(252, 76, 2, 0.8);
}

/* Canova Coach Critique Card: Full visibility in scroll-view */
.coach-critique-card {
  background: linear-gradient(135deg, rgba(88, 28, 135, 0.28), rgba(30, 27, 75, 0.45));
  border: 1px solid rgba(168, 85, 247, 0.35);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.critique-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.critique-robot {
  font-size: 15px;
}

.critique-title {
  font-size: 13px;
  font-weight: bold;
  color: #d8b4fe;
}

.critique-content {
  font-size: 12px;
  color: #e4e4e7;
  line-height: 1.6;
}

/* Additional Workout Details Card */
.workout-details-card {
  background-color: #27272a;
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.card-mini-title {
  font-size: 12px;
  font-weight: bold;
  color: #a1a1aa;
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
  background-color: rgba(255, 255, 255, 0.03);
  padding: 6px 10px;
  border-radius: 8px;
}

.detail-lbl {
  font-size: 11px;
  color: #71717a;
}

.detail-val {
  font-size: 12px;
  font-weight: 600;
  color: #f4f4f5;
}

.scroll-bottom-spacer {
  height: 30px;
}

/* Custom Sleek Scrollbar */
::-webkit-scrollbar {
  width: 4px;
  background: rgba(255, 255, 255, 0.05);
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.35);
  border-radius: 4px;
}
</style>
