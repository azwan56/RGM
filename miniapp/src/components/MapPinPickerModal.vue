<template>
  <view v-if="visible" class="mpp-mask" :class="[themeClass, fontScaleClass]" @click="handleClose" @touchmove.stop.prevent>
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
          placeholder="输入公园/体育场/路名，如：闵行文化公园"
          confirm-type="search"
          @confirm="handleSearchKeyword"
        />
        <view class="mpp-search-btn" @click="handleSearchKeyword">
          <text>{{ searching ? "定位中..." : "🔍 定位" }}</text>
        </view>
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
          show-location
          @tap="onMapTap"
          @regionchange="onMapRegionChange"
        />
        <view class="mpp-map-tip-bar">
          <text class="mpp-map-tip-txt">👆 点击地图放置集合点</text>
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
import { ref, computed, watch, getCurrentInstance, onBeforeUnmount } from "vue";
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
const mapScale = ref<number>(16);
const searching = ref(false);
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
      content: `📌 ${pinTitle.value || keyword.value || "集合点"} (点击地图微调位置)`,
      color: "#ffffff",
      fontSize: 12,
      borderRadius: 8,
      bgColor: "#2563eb",
      padding: 6,
      display: "ALWAYS",
    },
  },
]);

watch(
  () => props.visible,
  async (val) => {
    setTabBarHidden(Boolean(val), "map_pin");
    if (!val) return;
    const kw = (props.initialKeyword || "").trim();
    keyword.value = kw;
    pinTitle.value = kw || "集合点";
    pinAddress.value = (props.initialAddress || "").trim();

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
        // 如果之前没有坐标，或者之前的坐标与当前输入地点差距很大（例如残留的默认坐标），自动飞到输入地点
        const hasValidInitial =
          props.initialLat &&
          props.initialLng &&
          Math.abs(Number(props.initialLat) - first.latitude) < 0.02 &&
          Math.abs(Number(props.initialLng) - first.longitude) < 0.02;
        const targetLat = hasValidInitial ? Number(props.initialLat) : first.latitude;
        const targetLng = hasValidInitial ? Number(props.initialLng) : first.longitude;
        pinLat.value = targetLat;
        pinLng.value = targetLng;
        mapCenterLat.value = targetLat;
        mapCenterLng.value = targetLng;
        mapScale.value = 16;
        return;
      }
    }

    if (props.initialLat && props.initialLng) {
      pinLat.value = Number(props.initialLat);
      pinLng.value = Number(props.initialLng);
      mapCenterLat.value = Number(props.initialLat);
      mapCenterLng.value = Number(props.initialLng);
    } else {
      // 尝试获取用户当前位置作为默认地图中心
      if (typeof uni !== "undefined" && typeof uni.getLocation === "function") {
        uni.getLocation({
          type: "gcj02",
          success: (loc) => {
            if (loc?.latitude && loc?.longitude) {
              pinLat.value = Number(loc.latitude);
              pinLng.value = Number(loc.longitude);
              mapCenterLat.value = Number(loc.latitude);
              mapCenterLng.value = Number(loc.longitude);
            }
          },
        });
      }
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
  const list = await searchGroupRunGeocode(kw);
  searching.value = false;
  candidates.value = list;
  if (list.length > 0) {
    const first = list[0];
    pinTitle.value = kw;
    pinAddress.value = first.address;
    pinLat.value = first.latitude;
    pinLng.value = first.longitude;
    mapCenterLat.value = first.latitude;
    mapCenterLng.value = first.longitude;
    mapScale.value = 16;
    uni.showToast({ title: `已定位到「${first.name}」，可点击地图微调大头针`, icon: "none" });
  } else {
    uni.showToast({ title: "未检索到该地点，可直接拖动地图点击放置大头针", icon: "none" });
  }
}

function selectCandidate(c: GroupRunVenuePreset) {
  pinTitle.value = c.name;
  pinAddress.value = c.address;
  if (!keyword.value.trim()) keyword.value = c.name;
  pinLat.value = c.latitude;
  pinLng.value = c.longitude;
  mapCenterLat.value = c.latitude;
  mapCenterLng.value = c.longitude;
  mapScale.value = 17;
}

function onMapTap(e: any) {
  const lat = Number(e?.detail?.latitude);
  const lng = Number(e?.detail?.longitude);
  if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
    pinLat.value = Number(lat.toFixed(6));
    pinLng.value = Number(lng.toFixed(6));
    mapCenterLat.value = pinLat.value;
    mapCenterLng.value = pinLng.value;
    if (!pinTitle.value && keyword.value.trim()) {
      pinTitle.value = keyword.value.trim();
    }
  }
}

function onMapRegionChange(e: any) {
  if (e?.type === "end" && e?.causedBy === "drag") {
    try {
      const mapCtx = uni.createMapContext("pinPickerMap", instance?.proxy as any);
      mapCtx?.getCenterLocation({
        success: (res: any) => {
          if (res?.latitude && res?.longitude) {
            // Keep center updated without overriding explicit tap unless user hasn't tapped
          }
        },
      });
    } catch {
      // ignore
    }
  }
}

async function handleOpenWechatChooseLocation() {
  const picked = await pickGroupRunLocation(pinLat.value, pinLng.value, keyword.value);
  if (picked) {
    keyword.value = picked.name;
    pinTitle.value = picked.name;
    pinAddress.value = picked.address;
    pinLat.value = picked.latitude;
    pinLng.value = picked.longitude;
    mapCenterLat.value = picked.latitude;
    mapCenterLng.value = picked.longitude;
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
.mpp-map-tip-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12rpx 16rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.08));
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
