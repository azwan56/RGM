<template>
  <!-- 微信「用户隐私保护指引」授权弹窗：由 utils/privacy.ts 统一调度 -->
  <view v-if="visible" class="pp-mask" :class="[themeClass, fontScaleClass]" @touchmove.stop.prevent="noop">
    <view class="pp-panel">
      <text class="pp-title">用户隐私保护提示</text>
      <text class="pp-desc">
        感谢使用万跑跑团助手！使用前请阅读
        <text class="pp-link" @click="openContract">{{ contractName || "《万跑跑团助手小程序隐私保护指引》" }}</text>
        。我们仅在对应功能场景（上传头像、保存战报图片、复制邀请码、选择集合地点）及本小程序内训练诊断与体验优化中处理必要信息，绝不向第三方出售或共享。
      </text>
      <text class="pp-sub">不同意仍可浏览，但上述功能将无法使用。</text>
      <view class="pp-actions">
        <button class="pp-btn ghost" @click="disagree">不同意</button>
        <button
          id="agree-btn"
          class="pp-btn primary"
          open-type="agreePrivacyAuthorization"
          @agreeprivacyauthorization="agree"
        >同意并继续</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from "vue";
import { setTabBarHidden } from "../utils/api";
import { fontScaleClass, themeClass } from "../utils/theme";
import { onTelemetryPrivacyDecision } from "../utils/telemetry";
import {
  registerPrivacyHandler,
  unregisterPrivacyHandler,
  getCurrentRoute,
  checkNeedPrivacyAuthorization,
  openPrivacyContract,
  type PrivacyResolve,
} from "../utils/privacy";

const props = defineProps<{
  /** 为 true 时页面打开即检查，未授权则主动弹出（首页使用，实现首次启动统一授权） */
  proactive?: boolean;
}>();

const visible = ref(false);
const contractName = ref("");
let pendingResolve: PrivacyResolve | null = null;

// 自定义 TabBar 在页面之上，会盖住底部弹窗按钮：弹窗显示期间隐藏 TabBar
watch(visible, (v) => setTabBarHidden(v));
let route = "";

function handler(resolve: PrivacyResolve | null) {
  // 同一时间可能有多个隐私接口排队，旧的直接拒绝，只保留最新一个
  if (pendingResolve && resolve && pendingResolve !== resolve) {
    pendingResolve({ event: "disagree" });
  }
  if (resolve) pendingResolve = resolve;
  visible.value = true;
}

function agree() {
  onTelemetryPrivacyDecision(true);
  pendingResolve?.({ event: "agree", buttonId: "agree-btn" });
  pendingResolve = null;
  visible.value = false;
}

function disagree() {
  onTelemetryPrivacyDecision(false);
  pendingResolve?.({ event: "disagree" });
  pendingResolve = null;
  visible.value = false;
}

function openContract() {
  openPrivacyContract();
}

function noop() {}

onMounted(async () => {
  route = getCurrentRoute();
  registerPrivacyHandler(route, handler);
  const res = await checkNeedPrivacyAuthorization();
  contractName.value = res.contractName;
  if (props.proactive && res.need) handler(null);
});

onUnmounted(() => {
  unregisterPrivacyHandler(route, handler);
  // 页面销毁时不要让接口一直挂起
  pendingResolve?.({ event: "disagree" });
  pendingResolve = null;
});
</script>

<style scoped>
.pp-mask {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}
.pp-panel {
  width: 100%;
  padding: 40rpx 36rpx calc(40rpx + env(safe-area-inset-bottom));
  background: var(--rgm-card, #18181b);
  border-top-left-radius: 32rpx;
  border-top-right-radius: 32rpx;
  border-top: 1rpx solid var(--rgm-brand-line, rgba(255, 107, 0, 0.35));
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.pp-title {
  font-size: 32rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}
.pp-desc {
  font-size: 26rpx;
  line-height: 1.7;
  color: var(--rgm-text-2, #d4d4d8);
}
.pp-link {
  color: var(--rgm-brand-text, #ff8533);
  font-weight: 600;
}
.pp-sub {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
}
.pp-actions {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
  margin-top: 12rpx;
}
.pp-btn {
  flex: 1;
  min-width: 0;
  height: 84rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  border-radius: 42rpx;
  font-size: 28rpx;
  font-weight: 600;
  margin: 0;
  padding: 0 16rpx;
}
.pp-btn::after {
  border: none;
}
.pp-btn.ghost {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  color: var(--rgm-text-2, #a1a1aa);
}
.pp-btn.primary {
  background: var(--rgm-brand, #ff6b00);
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}
</style>
