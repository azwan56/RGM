<template>
  <view v-if="visible" class="mpp-mask" :class="[themeClass, fontScaleClass]" @click="handleClose">
    <view class="mpp-dialog" @click.stop>
      <!-- Header -->
      <view class="mpp-header">
        <view class="mpp-title-col">
          <text class="mpp-title">📍 地图选点</text>
        </view>
        <text class="mpp-close" @click="handleClose">✕</text>
      </view>

      <!-- Search Row -->
      <view class="mpp-search-row">
        <input
          class="mpp-search-input"
          type="text"
          v-model="keyword"
          placeholder="输入城市+地点，如：苏州米堆山 / 世纪公园"
          confirm-type="search"
          @confirm="handleSearchKeyword"
        />
        <view class="mpp-search-btn" @click="handleSearchKeyword">
          <text>{{ searching ? "定位中..." : "🔍 定位" }}</text>
        </view>
      </view>

      <!-- Fallback / Guidance Banner (one-tap native WeChat Tencent Map search) -->
      <view v-if="searchHint" class="mpp-hint-banner" @click="handleOpenWechatChooseLocation">
        <text class="mpp-hint-txt">{{ searchHint }}</text>
        <text class="mpp-hint-cta">微信搜点 ›</text>
      </view>

      <!-- Candidate POI Pills (when search returns multiple matches/gates) -->
      <scroll-view v-if="candidates.length > 0" scroll-x class="mpp-candidates-scroll" :show-scrollbar="false">
        <view class="mpp-candidates-row">
          <view
            v-for="(c, idx) in candidates"
            :key="idx"
            class="mpp-cand-pill"
            :class="{ active: Math.abs(c.latitude - pinLat) < 0.0005 && Math.abs(c.longitude - pinLng) < 0.0005 }"
            @click="selectCandidate(c)"
          >
            <text>📌 {{ c.name }}</text>
          </view>
        </view>
      </scroll-view>

      <!-- Interactive Map -->
      <view class="mpp-map-wrap">
        <map
          id="pinPickerMap"
          class="mpp-map"
          :latitude="mapCenterLat"
          :longitude="mapCenterLng"
          :scale="mapScale"
          :markers="mapMarkers"
          :enable-scroll="true"
          :enable-zoom="true"
          :show-compass="true"
          @tap="onMapTap"
          @regionchange="onMapRegionChange"
        />
        <view class="mpp-map-tip-bar">
          <view class="mpp-zoom-group">
            <view class="mpp-zoom-btn" @click="zoomMap(-2)"><text>−</text></view>
            <view class="mpp-zoom-btn" @click="zoomMap(2)"><text>+</text></view>
          </view>
          <text class="mpp-map-tip-txt">拖动或点击地图移动集合点</text>
          <text class="mpp-wx-native-btn" @click="handleOpenWechatChooseLocation">🧭 微信全屏选点 ›</text>
        </view>
      </view>

      <!-- Selected Coordinates Summary -->
      <view class="mpp-coord-summary">
        <view class="mpp-coord-left">
          <text class="mpp-coord-title">📌 {{ pinTitle || keyword || "已选集合点" }}</text>
          <text class="mpp-coord-sub">
            {{ pinAddress ? pinAddress + " · " : "" }}坐标 ({{ pinLat.toFixed(4) }}, {{ pinLng.toFixed(4) }})
          </text>
        </view>
      </view>

      <!-- Footer Actions -->
      <view class="mpp-footer">
        <button class="mpp-btn-cancel" @click="handleClose">取消</button>
        <button class="mpp-btn-confirm" @click="handleConfirmPin">📌 确认位置</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, getCurrentInstance, onBeforeUnmount } from "vue";
import { setTabBarHidden } from "../utils/api";
import { searchGroupRunGeocode, pickGroupRunLocation, GroupRunVenuePreset } from "../utils/groupRun";
import { fontScaleClass, themeClass } from "../utils/theme";

const props = defineProps<{
  visible: boolean;
  initialKeyword?: string;
  initialAddress?: string;
  initialLat?: number | null;
  initialLng?: number | null;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm", payload: GroupRunVenuePreset): void;
}>();

const instance = getCurrentInstance();
const keyword = ref("");
const pinTitle = ref("");
const pinAddress = ref("");
const pinLat = ref<number>(31.2165);
const pinLng = ref<number>(121.5518);
const mapCenterLat = ref<number>(31.2165);
const mapCenterLng = ref<number>(121.5518);
const mapScale = ref<number>(15);
const searching = ref(false);
const searchHint = ref("");
const hasResolvedLocation = ref(false);
const candidates = ref<GroupRunVenuePreset[]>([]);

const mapMarkers = computed(() => [
  {
    id: 1,
    latitude: Number(pinLat.value),
    longitude: Number(pinLng.value),
    title: pinTitle.value || keyword.value || "集合点",
    width: 32,
    height: 40,
    callout: {
      content: `📌 ${pinTitle.value || keyword.value || "集合点"} (拖动/点击微调)`,
      color: "#ffffff",
      fontSize: 12,
      borderRadius: 8,
      bgColor: "#2563eb",
      padding: 6,
      display: "ALWAYS",
    },
  },
]);

function moveMapTo(lat: number, lng: number, nextScale?: number) {
  const cleanLat = Number(Number(lat).toFixed(6));
  const cleanLng = Number(Number(lng).toFixed(6));
  if (!cleanLat || !cleanLng || isNaN(cleanLat) || isNaN(cleanLng)) return;

  pinLat.value = cleanLat;
  pinLng.value = cleanLng;

  // Ensure reactive prop diff fires even if map was dragged away from previous center value
  if (Math.abs(mapCenterLat.value - cleanLat) < 0.000001 && Math.abs(mapCenterLng.value - cleanLng) < 0.000001) {
    mapCenterLat.value = Number((cleanLat + 0.00001).toFixed(6));
    mapCenterLng.value = Number((cleanLng + 0.00001).toFixed(6));
  }

  nextTick(() => {
    mapCenterLat.value = cleanLat;
    mapCenterLng.value = cleanLng;
    if (typeof nextScale === "number") {
      mapScale.value = Math.max(5, Math.min(18, Math.round(nextScale)));
    }
    try {
      const mapCtx = uni.createMapContext("pinPickerMap", instance?.proxy as any);
      if (mapCtx && typeof (mapCtx as any).moveToLocation === "function") {
        (mapCtx as any).moveToLocation({
          latitude: cleanLat,
          longitude: cleanLng,
        });
      }
    } catch {
      // ignore on non-weixin environments
    }
  });
}

function zoomMap(delta: number) {
  const next = Math.max(5, Math.min(18, Math.round(mapScale.value + delta)));
  mapScale.value = next;
}

watch(
  () => props.visible,
  async (val) => {
    setTabBarHidden(Boolean(val), "map_pin");
    if (!val) return;
    const kw = (props.initialKeyword || "").trim();
    keyword.value = kw;
    pinTitle.value = kw || "集合点";
    pinAddress.value = (props.initialAddress || "").trim();
    searchHint.value = "";
    hasResolvedLocation.value = Boolean(props.initialLat && props.initialLng);

    if (kw) {
      // 优先根据输入的地点名称检索坐标，确保弹出地图直接定位到输入的地点
      searching.value = true;
      const list = await searchGroupRunGeocode(kw);
      searching.value = false;
      candidates.value = list;
      if (list.length > 0) {
        const first = list[0];
        pinTitle.value = kw;
        if (!pinAddress.value) pinAddress.value = first.address;
        const hasValidInitial =
          props.initialLat &&
          props.initialLng &&
          Math.abs(Number(props.initialLat) - first.latitude) < 0.05 &&
          Math.abs(Number(props.initialLng) - first.longitude) < 0.05;
        const targetLat = hasValidInitial ? Number(props.initialLat) : first.latitude;
        const targetLng = hasValidInitial ? Number(props.initialLng) : first.longitude;
        hasResolvedLocation.value = true;
        if (first.is_city_fallback) {
          searchHint.value = `已定位至目标城市区域，可拖动地图微调或点右侧微信腾讯地图精准搜点`;
        }
        moveMapTo(targetLat, targetLng, first.is_city_fallback ? 12 : 15);
        return;
      }
      searchHint.value = `未在本地库搜到「${kw}」，可拖动地图选点或点右侧微信全屏搜点`;
    }

    if (props.initialLat && props.initialLng) {
      moveMapTo(Number(props.initialLat), Number(props.initialLng), 15);
    }
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  setTabBarHidden(false, "map_pin");
});

async function handleSearchKeyword() {
  const kw = keyword.value.trim();
  if (!kw) {
    uni.showToast({ title: "请输入地点名称", icon: "none" });
    return;
  }
  searching.value = true;
  searchHint.value = "";
  const list = await searchGroupRunGeocode(kw);
  searching.value = false;
  candidates.value = list;
  if (list.length > 0) {
    const first = list[0];
    pinTitle.value = kw;
    pinAddress.value = first.address;
    hasResolvedLocation.value = true;
    const targetScale = first.is_city_fallback ? 12 : 15;
    moveMapTo(first.latitude, first.longitude, targetScale);
    if (first.is_city_fallback) {
      searchHint.value = `已移至该城市区域，可拖动/缩放地图选点或点右侧微信搜点`;
      uni.showToast({ title: "已定位到目标城市，可拖动地图或用微信全屏选点", icon: "none" });
    } else {
      uni.showToast({ title: `已定位到「${first.name}」，可拖动或点击地图微调`, icon: "none" });
    }
  } else {
    searchHint.value = `未搜到「${kw}」精确坐标，建议点右侧用微信全屏地图搜索`;
    uni.showToast({ title: "未检索到坐标，可点「微信全屏选点」用腾讯地图搜索", icon: "none" });
  }
}

function selectCandidate(c: GroupRunVenuePreset) {
  pinTitle.value = c.is_city_fallback ? (keyword.value.trim() || c.name) : c.name;
  pinAddress.value = c.address;
  if (!keyword.value.trim() && !c.is_city_fallback) keyword.value = c.name;
  hasResolvedLocation.value = true;
  searchHint.value = c.is_city_fallback ? "已定位至目标城市区域，可拖动地图微调或用微信搜点" : "";
  moveMapTo(c.latitude, c.longitude, c.is_city_fallback ? 12 : 16);
}

function onMapTap(e: any) {
  const lat = Number(e?.detail?.latitude);
  const lng = Number(e?.detail?.longitude);
  if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
    pinLat.value = Number(lat.toFixed(6));
    pinLng.value = Number(lng.toFixed(6));
    hasResolvedLocation.value = true;
    if (!pinTitle.value && keyword.value.trim()) {
      pinTitle.value = keyword.value.trim();
    }
  }
}

function onMapRegionChange(e: any) {
  if (e?.type !== "end") return;
  try {
    const mapCtx = uni.createMapContext("pinPickerMap", instance?.proxy as any);
    if (e?.causedBy === "drag" && mapCtx && typeof mapCtx.getCenterLocation === "function") {
      mapCtx.getCenterLocation({
        success: (res: any) => {
          const lat = Number(res?.latitude);
          const lng = Number(res?.longitude);
          if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
            // Update pin to dragged center without rewriting mapCenterLat/Lng (avoids native map snap-back)
            pinLat.value = Number(lat.toFixed(6));
            pinLng.value = Number(lng.toFixed(6));
            hasResolvedLocation.value = true;
          }
        },
      });
    } else if (e?.causedBy === "scale" && mapCtx && typeof (mapCtx as any).getScale === "function") {
      (mapCtx as any).getScale({
        success: (res: any) => {
          const sc = Number(res?.scale);
          if (sc >= 3 && sc <= 20) {
            mapScale.value = Math.round(sc);
          }
        },
      });
    }
  } catch {
    // ignore
  }
}

async function handleOpenWechatChooseLocation() {
  const picked = await pickGroupRunLocation(
    pinLat.value,
    pinLng.value,
    keyword.value,
    hasResolvedLocation.value
  );
  if (picked) {
    keyword.value = picked.name;
    pinTitle.value = picked.name;
    pinAddress.value = picked.address;
    hasResolvedLocation.value = true;
    searchHint.value = "";
    moveMapTo(picked.latitude, picked.longitude, 16);
  }
}

function handleConfirmPin() {
  const finalName = (keyword.value || pinTitle.value || "集合点").trim();
  emit("confirm", {
    name: finalName,
    address: pinAddress.value || finalName,
    latitude: Number(pinLat.value.toFixed(6)),
    longitude: Number(pinLng.value.toFixed(6)),
  });
}

function handleClose() {
  emit("close");
}
</script>

<style scoped>
.mpp-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.65);
  z-index: 10050;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24rpx;
}
.mpp-dialog {
  width: 100%;
  max-width: 690rpx;
  background: var(--rgm-card, #141418);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 28rpx;
  padding: 26rpx;
  box-sizing: border-box;
  box-shadow: 0 20rpx 60rpx var(--rgm-shadow, rgba(0, 0, 0, 0.35));
}
.mpp-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 18rpx;
}
.mpp-title-col {
  flex: 1;
}
.mpp-title {
  display: block;
  font-size: 30rpx;
  font-weight: 800;
  color: var(--rgm-text, #f4f4f6);
}
.mpp-close {
  font-size: 32rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 4rpx 12rpx;
}
.mpp-search-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 14rpx;
}
.mpp-search-input {
  flex: 1;
  height: 72rpx;
  background: var(--rgm-card-3, #23232c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  padding: 0 20rpx;
  font-size: 26rpx;
  color: var(--rgm-text, #f4f4f6);
}
.mpp-search-btn {
  height: 72rpx;
  padding: 0 24rpx;
  border-radius: 16rpx;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b2b 100%));
  color: #ffffff;
  font-size: 25rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}
.mpp-candidates-scroll {
  width: 100%;
  white-space: nowrap;
  margin-bottom: 14rpx;
}
.mpp-candidates-row {
  display: inline-flex;
  gap: 10rpx;
}
.mpp-cand-pill {
  display: inline-flex;
  align-items: center;
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
  font-size: 22rpx;
  font-weight: 600;
  background: var(--rgm-card-3, #23232c);
  color: var(--rgm-text-2, #a1a1aa);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}
.mpp-cand-pill.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  color: var(--rgm-brand-text, #fc4c02);
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
}
.mpp-map-wrap {
  border-radius: 18rpx;
  overflow: hidden;
  border: 2rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  background: var(--rgm-card-2, #1b1b22);
}
.mpp-map {
  width: 100%;
  height: 460rpx;
}
.mpp-hint-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  padding: 10rpx 16rpx;
  margin-bottom: 12rpx;
  border-radius: 14rpx;
  background: rgba(245, 158, 11, 0.14);
  border: 1rpx solid rgba(245, 158, 11, 0.35);
}
.mpp-hint-txt {
  flex: 1;
  font-size: 20rpx;
  color: var(--rgm-amber, #f59e0b);
  line-height: 1.4;
}
.mpp-hint-cta {
  font-size: 21rpx;
  font-weight: 800;
  color: var(--rgm-brand-text, #fc4c02);
  white-space: nowrap;
  flex-shrink: 0;
}
.mpp-map-tip-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10rpx;
  padding: 12rpx 14rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.08));
}
.mpp-zoom-group {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-shrink: 0;
}
.mpp-zoom-btn {
  width: 44rpx;
  height: 44rpx;
  border-radius: 10rpx;
  background: var(--rgm-card, #141418);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text, #f4f4f6);
  font-size: 28rpx;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.mpp-map-tip-txt {
  font-size: 21rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 600;
  flex: 1;
}
.mpp-wx-native-btn {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
  margin-left: 12rpx;
  white-space: nowrap;
}
.mpp-coord-summary {
  margin-top: 16rpx;
  padding: 14rpx 18rpx;
  border-radius: 14rpx;
  background: var(--rgm-card-2, #1b1b22);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}
.mpp-coord-title {
  display: block;
  font-size: 25rpx;
  font-weight: 700;
  color: var(--rgm-text, #f4f4f6);
}
.mpp-coord-sub {
  display: block;
  font-size: 21rpx;
  color: var(--rgm-text-3, #71717a);
  margin-top: 4rpx;
}
.mpp-footer {
  display: flex;
  gap: 16rpx;
  margin-top: 20rpx;
}
.mpp-btn-cancel {
  flex: 0.4;
  min-width: 0;
  height: 80rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
  white-space: nowrap;
  border-radius: 18rpx;
  font-size: 26rpx;
  font-weight: 700;
  background: var(--rgm-card-3, #23232c);
  color: var(--rgm-text-2, #a1a1aa);
  margin: 0;
}
.mpp-btn-confirm {
  flex: 1;
  min-width: 0;
  height: 80rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 20rpx;
  white-space: nowrap;
  border-radius: 18rpx;
  font-size: 27rpx;
  font-weight: 800;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b2b 100%));
  color: #ffffff;
  margin: 0;
}
</style>
