<template>
  <view
    v-if="visible"
    class="gsm-mask"
    :class="[themeClass, { 'gsm-light': isVolt }]"
    @click="handleClose"
    @touchmove.stop.prevent
  >
    <view class="gsm-sheet" @click.stop>
      <!-- Header -->
      <view class="gsm-header">
        <view class="gsm-title-row">
          <text class="gsm-icon">🎯</text>
          <text class="gsm-title">设定周计划与月计划</text>
        </view>
        <view class="gsm-close" @click="handleClose">✕</view>
      </view>

      <!-- Dual Segmented Tabs: Weekly | Monthly -->
      <view class="gsm-tabs">
        <view
          class="gsm-tab"
          :class="{ active: activeTab === 'week' }"
          @click="switchTab('week')"
        >
          <text>🏃 下周目标 ({{ editWeeklyKm }}k)</text>
        </view>
        <view
          class="gsm-tab"
          :class="{ active: activeTab === 'month' }"
          @click="switchTab('month')"
        >
          <text>📅 下个月目标 ({{ previewNextMonthKm }}k)</text>
        </view>
      </view>

      <scroll-view scroll-y class="gsm-body">
        <!-- TAB 1: Weekly Target -->
        <view v-if="activeTab === 'week'" class="gsm-section">
          <view class="gsm-hero-num-card">
            <view class="gsm-num-row">
              <text class="gsm-big-num">{{ editWeeklyKm }}</text>
              <text class="gsm-big-unit">km / 周</text>
            </view>
            <text class="gsm-sub-hint">
              即将应用于 {{ nextWeekLabel || "下周一" }} 起的新周周期
            </text>
          </view>

          <text class="gsm-label">快捷档位：</text>
          <view class="gsm-pills">
            <view
              v-for="km in [20, 30, 40, 50, 60, 70, 80, 100]"
              :key="km"
              class="gsm-pill"
              :class="{ active: editWeeklyKm === km }"
              @click="selectWeeklyPreset(km)"
            >
              {{ km }}k
            </view>
          </view>

          <view class="gsm-slider-box">
            <slider
              :value="editWeeklyKm"
              :min="10"
              :max="160"
              :step="5"
              activeColor="#10b981"
              :backgroundColor="isVolt ? '#e4e4e7' : '#2c2c2e'"
              block-size="22"
              @change="onWeeklySliderChange"
            />
            <view class="gsm-slider-ends">
              <text>10 km</text>
              <text>160 km</text>
            </view>
          </view>

          <!-- Auto-sync Monthly Toggle (Safe: defaults OFF if user customized per-month targets) -->
          <view class="gsm-sync-row" @click="toggleAutoSyncMonthly">
            <view class="gsm-sync-left">
              <text class="gsm-sync-title">
                {{ goalState.autoSyncMonthly ? "☑️" : "⬜" }} 同步换算下个月目标（约 {{ calcSyncedMonthlyKm(goalState.editWeeklyKm) }} km/月）
              </text>
              <text class="gsm-sync-desc">
                {{
                  goalState.hasIndependentMonthly
                    ? `您已单独设置月跑量（当前 ${goalState.editUniformMonthlyKm} km/月），默认关闭同步以防覆盖`
                    : "勾选后修改周跑量将按 ×4.3 自动同步下个月目标"
                }}
              </text>
            </view>
          </view>
        </view>

        <!-- TAB 2: Monthly Target -->
        <view v-else class="gsm-section">
          <view class="gsm-hero-num-card">
            <view class="gsm-num-row">
              <text class="gsm-big-num">{{ previewNextMonthKm }}</text>
              <text class="gsm-big-unit">km / 月</text>
            </view>
            <text class="gsm-sub-hint">
              {{ nextMonthSubHint }}
            </text>
          </view>

          <text class="gsm-label">快捷月跑量档位：</text>
          <view class="gsm-pills">
            <view
              v-for="mkm in [80, 100, 120, 150, 200, 250, 300, 350]"
              :key="mkm"
              class="gsm-pill"
              :class="{ active: !goalState.customMonthMode && displayedUniformMonthlyKm === mkm }"
              @click="selectMonthlyPreset(mkm)"
            >
              {{ mkm }}k
            </view>
          </view>

          <view class="gsm-slider-box">
            <slider
              :value="displayedUniformMonthlyKm"
              :min="40"
              :max="500"
              :step="10"
              activeColor="#FC4C02"
              :backgroundColor="isVolt ? '#e4e4e7' : '#2c2c2e'"
              block-size="22"
              @change="onMonthlySliderChange"
            />
            <view class="gsm-slider-ends">
              <text>40 km</text>
              <text>500 km</text>
            </view>
          </view>

          <!-- Optional Per-Month Fine-Tuning -->
          <view v-if="currentCalMonth < 12" class="gsm-custom-months-wrap">
            <view class="gsm-custom-toggle" @click="goalState.customMonthMode = !goalState.customMonthMode">
              <text class="gsm-custom-toggle-txt">
                🎛️ 按月份单独微调（夏训/冬训差异化）
              </text>
              <text class="gsm-custom-arrow">{{ goalState.customMonthMode ? "收起 ▴" : "展开 ▾" }}</text>
            </view>

            <view v-if="goalState.customMonthMode" class="gsm-months-grid">
              <view
                v-for="(val, idx) in goalState.editMonthlyArray"
                :key="idx"
                class="gsm-month-cell"
                :class="{ locked: idx + 1 <= currentCalMonth }"
              >
                <text class="gsm-m-name">
                  {{ idx + 1 }}月 {{ idx + 1 <= currentCalMonth ? "🔒" : "" }}
                </text>
                <input
                  v-if="idx + 1 > currentCalMonth"
                  type="number"
                  class="gsm-m-input"
                  :value="String(val)"
                  @input="(e: any) => updateSingleMonth(idx, e.detail.value)"
                />
                <text v-else class="gsm-m-locked-val">{{ val }}k</text>
              </view>
            </view>
          </view>
        </view>

        <!-- Plain-Language Lock Rule Explanation -->
        <view class="gsm-rule-note">
          <text class="gsm-rule-text">
            💡 进行中的本周（{{ lockedWeekDisplay }}k）与本月（{{ lockedMonthDisplay }}k）目标已锁定不变；本次保存自下周一及下个月 1 日起生效。
          </text>
        </view>
      </scroll-view>

      <!-- Footer Actions -->
      <view class="gsm-footer">
        <button class="gsm-btn cancel" @click="handleClose">取消</button>
        <button class="gsm-btn save" :loading="saving" @click="handleSave">
          保存目标
        </button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onBeforeUnmount } from "vue";
import { currentTheme, themeClass } from "../utils/theme";
import { request, getStoredUser, setTabBarHidden } from "../utils/api";
import { trackModal } from "../utils/telemetry";
import {
  calcSyncedMonthlyKm,
  createGoalSheetState,
  setWeeklyKmInState,
  toggleAutoSyncInState,
  setUniformMonthlyKmInState,
  setSingleMonthKmInState,
  willStateRewriteFutureMonths,
  getPreviewNextMonthKm,
  buildGoalSavePayload,
} from "../utils/goalSheetLogic";

const props = defineProps<{
  visible: boolean;
  defaultTab?: "week" | "month";
  userId?: string;
  initialGoal?: any;
  currentWeekLockedKm?: number;
  currentMonthLockedKm?: number;
  nextWeekLabel?: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "saved", savedGoal: any): void;
}>();

const isVolt = computed(() => currentTheme.value === "volt");
const currentCalMonth = new Date().getMonth() + 1;

const activeTab = ref<"week" | "month">("week");
const saving = ref<boolean>(false);
const goalState = reactive(createGoalSheetState(null, currentCalMonth));
const editWeeklyKm = computed(() => goalState.editWeeklyKm);

const displayedUniformMonthlyKm = computed(() => {
  if (willStateRewriteFutureMonths(goalState)) {
    return calcSyncedMonthlyKm(goalState.editWeeklyKm);
  }
  return goalState.editUniformMonthlyKm;
});

const lockedWeekDisplay = computed(() => {
  return (
    props.currentWeekLockedKm ??
    props.initialGoal?.current_week_target ??
    props.initialGoal?.weekly_target ??
    goalState.editWeeklyKm
  );
});

const lockedMonthDisplay = computed(() => {
  if (props.currentMonthLockedKm != null) return props.currentMonthLockedKm;
  const arr = goalState.initialMonthlyArray;
  if (arr && arr.length >= currentCalMonth) {
    return arr[currentCalMonth - 1];
  }
  return goalState.editUniformMonthlyKm;
});

const previewNextMonthKm = computed(() => getPreviewNextMonthKm(goalState));

const nextMonthSubHint = computed(() => {
  if (currentCalMonth >= 12) {
    return "即将应用于次年 1月（1月1日起生效）";
  }
  const nextM = currentCalMonth + 1;
  if (goalState.customMonthMode) {
    return `当前展示 ${nextM}月目标（下方可按月份微调）`;
  }
  if (nextM === 12) {
    return "即将应用于 12月（12月1日起生效）";
  }
  return `即将应用于 ${nextM}月（同步更新后续未开始月份）`;
});

function hydrateFromGoal(g: any) {
  Object.assign(goalState, createGoalSheetState(g, currentCalMonth));
}

onBeforeUnmount(() => {
  setTabBarHidden(false, "goal_sheet");
});

watch(
  () => props.visible,
  async (val) => {
    setTabBarHidden(Boolean(val), "goal_sheet");
    if (!val) return;
    activeTab.value = props.defaultTab === "month" ? "month" : "week";
    trackModal("goal_sheet", "打开周/月目标二合一弹窗", "open", {
      default_tab: activeTab.value,
    });

    if (props.initialGoal && Array.isArray(props.initialGoal.monthly_targets)) {
      hydrateFromGoal(props.initialGoal);
      return;
    }

    if (props.initialGoal) {
      hydrateFromGoal(props.initialGoal);
    }
    const uid = props.userId || getStoredUser()?.id;
    if (uid) {
      try {
        const res: any = await request(`/api/profile/${encodeURIComponent(uid)}`, "GET");
        if (res?.goal) {
          hydrateFromGoal(res.goal);
        }
      } catch (_) {}
    }
  }
);

function switchTab(tab: "week" | "month") {
  activeTab.value = tab;
}

function selectWeeklyPreset(km: number) {
  setWeeklyKmInState(goalState, km);
}

function onWeeklySliderChange(e: any) {
  setWeeklyKmInState(goalState, Number(e?.detail?.value) || 50);
}

function toggleAutoSyncMonthly() {
  toggleAutoSyncInState(goalState);
}

function selectMonthlyPreset(mkm: number) {
  setUniformMonthlyKmInState(goalState, mkm);
}

function onMonthlySliderChange(e: any) {
  setUniformMonthlyKmInState(goalState, Number(e?.detail?.value) || 200);
}

function updateSingleMonth(idx: number, rawVal: string) {
  setSingleMonthKmInState(goalState, idx, rawVal);
}

function handleClose() {
  trackModal("goal_sheet", "关闭周/月目标弹窗", "close");
  emit("close");
}

async function handleSave() {
  const uid = props.userId || getStoredUser()?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }

  saving.value = true;
  try {
    const { shouldSyncMonthly, payload } = buildGoalSavePayload(goalState);
    const wk = payload.weekly_target;
    const nextMonthPreview = previewNextMonthKm.value;

    const res: any = await request(
      `/api/profile/${encodeURIComponent(uid)}/goal`,
      "PUT",
      payload
    );

    const savedGoal = res?.goal || res?.data || payload;

    try {
      uni.setStorageSync("rgm_dashboard_dirty", 1);
    } catch (_) {}

    trackModal("goal_sheet", "保存周/月计划目标", "submit", {
      weekly_target: wk,
      target_distance: payload.target_distance,
      auto_sync_monthly: shouldSyncMonthly,
      custom_month_mode: goalState.customMonthMode,
    });

    emit("saved", savedGoal);
    emit("close");
    uni.showToast({
      title: `已保存：下周 ${wk}k · 下个月 ${nextMonthPreview}k`,
      icon: "none",
      duration: 2400,
    });
  } catch (err: any) {
    uni.showToast({ title: err?.message || "保存失败", icon: "none" });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.gsm-mask {
  position: fixed;
  inset: 0;
  z-index: 9800;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.gsm-sheet {
  width: 100%;
  max-height: 86vh;
  background: var(--rgm-card, #18181b);
  border-top-left-radius: 36rpx;
  border-top-right-radius: 36rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 30rpx 32rpx calc(28rpx + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink, #ffffff);
  --rgm-text-2: var(--rgm-ink-2, #d4d4d8);
  --rgm-text-3: var(--rgm-ink-3, #8e8e93);
}
.gsm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22rpx;
}
.gsm-title-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.gsm-icon {
  font-size: 34rpx;
}
.gsm-title {
  font-size: 32rpx;
  font-weight: 800;
  color: var(--rgm-text);
}
.gsm-close {
  width: 56rpx;
  height: 56rpx;
  border-radius: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  color: var(--rgm-text-3);
  background: rgba(128, 128, 128, 0.12);
}
.gsm-tabs {
  display: flex;
  gap: 12rpx;
  padding: 8rpx;
  border-radius: 22rpx;
  background: rgba(128, 128, 128, 0.12);
  margin-bottom: 22rpx;
}
.gsm-tab {
  flex: 1;
  text-align: center;
  padding: 16rpx 10rpx;
  border-radius: 16rpx;
  font-size: 25rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
}
.gsm-tab.active {
  background: #fc4c02;
  color: #ffffff;
}
.gsm-body {
  max-height: 56vh;
}
.gsm-section {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}
.gsm-hero-num-card {
  padding: 24rpx;
  border-radius: 24rpx;
  background: rgba(16, 185, 129, 0.09);
  border: 1rpx solid rgba(16, 185, 129, 0.28);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
}
.gsm-num-row {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
}
.gsm-big-num {
  font-size: 64rpx;
  font-weight: 900;
  color: #10b981;
  line-height: 1.05;
}
.gsm-big-unit {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
}
.gsm-sub-hint {
  font-size: 22rpx;
  color: var(--rgm-text-3);
}
.gsm-label {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
}
.gsm-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}
.gsm-pill {
  padding: 12rpx 22rpx;
  border-radius: 999rpx;
  font-size: 25rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
  background: rgba(128, 128, 128, 0.13);
  border: 1rpx solid transparent;
}
.gsm-pill.active {
  background: rgba(16, 185, 129, 0.18);
  color: #10b981;
  border-color: #10b981;
}
.gsm-slider-box {
  padding: 4rpx 6rpx 0;
}
.gsm-slider-ends {
  display: flex;
  justify-content: space-between;
  font-size: 21rpx;
  color: var(--rgm-text-3);
  margin-top: -6rpx;
}
.gsm-sync-row {
  padding: 18rpx 20rpx;
  border-radius: 20rpx;
  background: rgba(128, 128, 128, 0.1);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}
.gsm-sync-left {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}
.gsm-sync-title {
  font-size: 25rpx;
  font-weight: 700;
  color: var(--rgm-text);
}
.gsm-sync-desc {
  font-size: 21rpx;
  color: var(--rgm-text-3);
  line-height: 1.45;
}
.gsm-custom-months-wrap {
  margin-top: 4rpx;
  padding: 16rpx 18rpx;
  border-radius: 20rpx;
  background: rgba(128, 128, 128, 0.08);
}
.gsm-custom-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.gsm-custom-toggle-txt {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
}
.gsm-custom-arrow {
  font-size: 22rpx;
  color: #fc4c02;
  font-weight: 700;
}
.gsm-months-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
  margin-top: 18rpx;
}
.gsm-month-cell {
  padding: 12rpx 10rpx;
  border-radius: 16rpx;
  background: rgba(128, 128, 128, 0.12);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
}
.gsm-month-cell.locked {
  opacity: 0.52;
}
.gsm-m-name {
  font-size: 21rpx;
  color: var(--rgm-text-3);
}
.gsm-m-input {
  width: 100%;
  height: 48rpx;
  text-align: center;
  font-size: 25rpx;
  font-weight: 800;
  color: var(--rgm-text);
  background: rgba(0, 0, 0, 0.18);
  border-radius: 10rpx;
}
.gsm-m-locked-val {
  height: 48rpx;
  line-height: 48rpx;
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
}
.gsm-rule-note {
  margin-top: 20rpx;
  padding: 16rpx 20rpx;
  border-radius: 18rpx;
  background: rgba(245, 158, 11, 0.11);
  border: 1rpx solid rgba(245, 158, 11, 0.3);
}
.gsm-rule-text {
  font-size: 22rpx;
  line-height: 1.5;
  color: #d97706;
}
.gsm-footer {
  display: flex;
  gap: 18rpx;
  margin-top: 22rpx;
}
.gsm-btn {
  flex: 1;
  min-width: 0;
  height: 84rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 20rpx;
  white-space: nowrap;
  border-radius: 42rpx;
  font-size: 28rpx;
  font-weight: 700;
  margin: 0;
}
.gsm-btn::after {
  border: none;
}
.gsm-btn.cancel {
  flex: 0.65;
  background: rgba(128, 128, 128, 0.16);
  color: var(--rgm-text-2);
}
.gsm-btn.save {
  background: linear-gradient(135deg, #fc4c02 0%, #ff7a00 100%);
  color: #ffffff;
}
</style>
