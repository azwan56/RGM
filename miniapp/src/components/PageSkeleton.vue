<template>
  <!-- 首屏骨架屏：overlay=true 时铺满页面盖住尚未加载好的内容 -->
  <view class="sk-wrap" :class="{ overlay }">
    <view v-if="header" class="sk-header">
      <view class="sk sk-avatar" />
      <view class="sk-col">
        <view class="sk sk-line" style="width: 160rpx" />
        <view class="sk sk-line lg" style="width: 260rpx" />
      </view>
    </view>
    <view v-for="i in cards" :key="i" class="sk-card">
      <view class="sk sk-line lg" style="width: 45%" />
      <view class="sk sk-block" />
      <view class="sk sk-line" style="width: 80%" />
      <view class="sk sk-line" style="width: 60%" />
    </view>
  </view>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ overlay?: boolean; header?: boolean; cards?: number }>(), {
  overlay: false,
  header: true,
  cards: 3,
});
</script>

<style scoped>
.sk-wrap {
  padding: 36rpx 28rpx;
  box-sizing: border-box;
}
.sk-wrap.overlay {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 50;
  background: var(--rgm-bg, #0b0b0d);
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.sk-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 36rpx;
}
.sk-col {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.sk-card {
  padding: 28rpx;
  margin-bottom: 28rpx;
  border-radius: 24rpx;
  background: var(--rgm-card, #141418);
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.sk {
  border-radius: 12rpx;
  background: var(--rgm-card, linear-gradient(90deg, #1c1c20 25%, #2a2a30 37%, #1c1c20 63%));
  background-size: 400% 100%;
  animation: sk-shimmer 1.4s ease infinite;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.sk-avatar {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
}
.sk-line {
  height: 24rpx;
}
.sk-line.lg {
  height: 34rpx;
}
.sk-block {
  height: 180rpx;
  border-radius: 16rpx;
}
@keyframes sk-shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}
</style>
