<template>
  <view v-if="visible" class="gps-modal-mask" @click="handleClose" @touchmove.stop.prevent>
    <view class="gps-modal-container" @click.stop>
      <!-- Modal Header -->
      <view class="gps-modal-header">
        <view class="header-left">
          <text class="modal-badge">🗺️ GPS 路线与高程</text>
          <text class="act-title">{{ activityData?.name || initialActivity?.name || '跑步路线详情' }}</text>
        </view>
        <view class="close-hit" @click="handleClose">
          <text class="close-icon">✕</text>
        </view>
      </view>

      <!-- Sub Header: Distance & Time -->
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

      <!-- Tab Switcher (路线地图 / 高程剖面 / 卫星实景) -->
      <view class="tab-strip">
        <view
          class="tab-btn"
          :class="{ active: activeTab === 'map' }"
          @click="activeTab = 'map'"
        >
          <text class="tab-text">🗺️ 轨迹路线</text>
        </view>
        <view
          v-if="hasElevationProfile"
          class="tab-btn"
          :class="{ active: activeTab === 'elevation' }"
          @click="activeTab = 'elevation'"
        >
          <text class="tab-text">📈 海拔剖面</text>
        </view>
        <view
          v-if="mapImageUrl"
          class="tab-btn"
          :class="{ active: activeTab === 'image' }"
          @click="activeTab = 'image'"
        >
          <text class="tab-text">🖼️ 地图切片</text>
        </view>
      </view>

      <!-- Body Content Area -->
      <view class="gps-modal-body">
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

        <!-- TAB 1: Native Map -->
        <view v-else-if="activeTab === 'map'" class="map-wrapper">
          <view v-if="trackPoints.length" class="map-inner">
            <map
              id="trackMap"
              class="track-map-view"
              :latitude="trackCenter.latitude"
              :longitude="trackCenter.longitude"
              :markers="trackMarkers"
              :polyline="trackPolylines"
              :include-points="trackPoints"
              :show-location="false"
              :enable-zoom="true"
              :enable-scroll="true"
            />
            <view class="map-corner-pill">
              <text class="pill-dot">●</text>
              <text class="pill-text">GCJ-02 火星坐标纠偏 · 微信原生地图</text>
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

        <!-- TAB 2: Elevation Profile -->
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

          <!-- SVG-like Elevation Profile Visualization -->
          <view class="chart-box">
            <svg class="elev-svg" viewBox="0 0 320 120" preserveAspectRatio="none">
              <defs>
                <linearGradient id="elevGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#FC4C02" stop-opacity="0.6" />
                  <stop offset="100%" stop-color="#FC4C02" stop-opacity="0.05" />
                </linearGradient>
              </defs>
              <!-- Filled Area Under Curve -->
              <path :d="elevationAreaPath" fill="url(#elevGrad)" />
              <!-- Top Profile Line -->
              <path :d="elevationLinePath" fill="none" stroke="#FC4C02" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <view class="axis-x-row">
              <text class="axis-x">0 km</text>
              <text class="axis-x">{{ (distanceKm / 2).toFixed(1) }} km</text>
              <text class="axis-x">{{ distanceKm }} km</text>
            </view>
          </view>
        </view>

        <!-- TAB 3: Static Image -->
        <view v-else-if="activeTab === 'image'" class="image-wrapper">
          <image class="official-map-img" :src="mapImageUrl" mode="widthFix" />
        </view>

        <!-- Canova Coach Critique Snapshot -->
        <view v-if="coachCritique" class="coach-critique-card">
          <view class="critique-header">
            <text class="critique-robot">🤖</text>
            <text class="critique-title">Canova教练专属复盘</text>
          </view>
          <text class="critique-content">{{ coachCritique }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { request } from "../utils/api";

const props = defineProps<{
  visible: boolean;
  activityId?: string;
  initialActivity?: any;
}>();

const emit = defineEmits(["close"]);

const loading = ref(false);
const errorMsg = ref("");
const activeTab = ref<"map" | "elevation" | "image">("map");

const activityData = ref<any>(null);
const trackPoints = ref<Array<{ latitude: number; longitude: number }>>([]);
const elevationProfile = ref<Array<{ dist_km: number; elevation_m: number }>>([]);
const mapImageUrl = ref("");

const trackCenter = ref<{ latitude: number; longitude: number }>({ latitude: 28.0, longitude: 114.0 });

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

  return [
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
});

// SVG Path generator for Elevation Chart
const elevationCoords = computed(() => {
  const list = elevationProfile.value;
  if (!list || list.length < 2) return [];
  const minE = minElevation.value;
  const maxE = maxElevation.value;
  const diffE = Math.max(10, maxE - minE);

  const totalDist = list[list.length - 1].dist_km || 1;

  return list.map((item) => {
    const x = Math.round(((item.dist_km / totalDist) * 300 + 10) * 10) / 10;
    const normH = (item.elevation_m - minE) / diffE;
    const y = Math.round((105 - normH * 85) * 10) / 10;
    return { x, y };
  });
});

const elevationLinePath = computed(() => {
  const coords = elevationCoords.value;
  if (!coords.length) return "";
  return coords.reduce((acc, pt, idx) => {
    return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`;
  }, "");
});

const elevationAreaPath = computed(() => {
  const coords = elevationCoords.value;
  if (!coords.length) return "";
  const first = coords[0];
  const last = coords[coords.length - 1];
  const linePart = elevationLinePath.value;
  return `${linePart} L ${last.x} 115 L ${first.x} 115 Z`;
});

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
  }
}

function handleClose() {
  emit("close");
}
</script>

<style scoped>
.gps-modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.75);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  z-index: 9999;
  backdrop-filter: blur(8px);
}

.gps-modal-container {
  background-color: #18181b;
  border-top-left-radius: 24px;
  border-top-right-radius: 24px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  padding: 20px 16px 36px;
  box-shadow: 0 -10px 30px rgba(0, 0, 0, 0.5);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.gps-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
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

.gps-modal-body {
  overflow-y: auto;
  max-height: 60vh;
}

.loading-box,
.error-box,
.empty-track-box {
  padding: 40px 16px;
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
  border-radius: 16px;
  overflow: hidden;
  margin-bottom: 12px;
}

.map-inner {
  position: relative;
  width: 100%;
  height: 280px;
}

.track-map-view {
  width: 100%;
  height: 100%;
  border-radius: 16px;
}

.map-corner-pill {
  position: absolute;
  bottom: 8px;
  left: 8px;
  background-color: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  padding: 4px 8px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
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
  border-radius: 16px;
}

.elevation-wrapper {
  background-color: #27272a;
  border-radius: 16px;
  padding: 14px;
  margin-bottom: 12px;
}

.elevation-stats-bar {
  display: flex;
  justify-content: space-around;
  margin-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 8px;
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
  font-size: 14px;
  font-weight: bold;
  margin-top: 2px;
}

.chart-box {
  width: 100%;
  display: flex;
  flex-direction: column;
}

.elev-svg {
  width: 100%;
  height: 130px;
}

.axis-x-row {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  padding: 0 4px;
}

.axis-x {
  font-size: 10px;
  color: #71717a;
}

.coach-critique-card {
  background: linear-gradient(135deg, rgba(88, 28, 135, 0.25), rgba(30, 27, 75, 0.4));
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 14px;
  padding: 12px 14px;
  margin-top: 8px;
}

.critique-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.critique-robot {
  font-size: 14px;
}

.critique-title {
  font-size: 12px;
  font-weight: bold;
  color: #d8b4fe;
}

.critique-content {
  font-size: 11px;
  color: #e4e4e7;
  line-height: 1.5;
}
</style>
