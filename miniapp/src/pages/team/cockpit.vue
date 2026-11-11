<template>
  <view class="cockpit-tab-shell" :class="themeClass">
    <CockpitWorkspace
      :show-tick="showTick"
      :refresh-tick="refreshTick"
      @refresh-done="handleRefreshDone"
    />
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad, onShow, onPullDownRefresh, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import { syncTabBarIndex } from "../../utils/api";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import CockpitWorkspace from "../../components/CockpitWorkspace.vue";

const showTick = ref(0);
const refreshTick = ref(0);
let refreshFallbackTimer: ReturnType<typeof setTimeout> | null = null;

function handleRefreshDone() {
  if (refreshFallbackTimer) {
    clearTimeout(refreshFallbackTimer);
    refreshFallbackTimer = null;
  }
  uni.stopPullDownRefresh();
}

onLoad(() => {
  initShareMenu();
});

onShow(() => {
  applySystemTheme(currentTheme.value);
  syncTabBarIndex();
  showTick.value += 1;
});

onPullDownRefresh(() => {
  refreshTick.value += 1;
  if (refreshFallbackTimer) clearTimeout(refreshFallbackTimer);
  refreshFallbackTimer = setTimeout(() => {
    uni.stopPullDownRefresh();
  }, 8000);
});

onShareAppMessage(() => getUnifiedShareAppMessage());
onShareTimeline(() => getUnifiedShareTimeline());
</script>

<style scoped>
.cockpit-tab-shell {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
}
</style>
