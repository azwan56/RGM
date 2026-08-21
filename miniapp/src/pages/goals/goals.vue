<template>
  <view class="goals-page">
    <view class="page-title-box">
      <text class="title">目标设定与生理参数</text>
      <text class="subtitle">科学量化训练负荷，为 AI 教练提供精准分析基准</text>
    </view>

    <!-- Monthly Target Card -->
    <view class="setting-card">
      <view class="card-header">
        <text class="card-title">月度跑量目标</text>
        <text class="target-display">{{ overallTarget }} <text class="unit">km / 月</text></text>
      </view>

      <!-- Slider -->
      <slider
        :value="overallTarget"
        :min="50"
        :max="600"
        :step="10"
        activeColor="#FC4C02"
        backgroundColor="rgba(255,255,255,0.1)"
        block-color="#ffffff"
        block-size="20"
        @change="onSliderChange"
      />

      <!-- Quick Preset Chips -->
      <view class="chips-row">
        <view
          v-for="preset in [100, 150, 200, 250, 300, 400]"
          :key="preset"
          class="chip"
          :class="{ active: overallTarget === preset }"
          @click="overallTarget = preset"
        >
          <text>{{ preset }}k</text>
        </view>
      </view>

      <!-- Monthly breakdown toggle -->
      <view class="breakdown-toggle" @click="showMonthly = !showMonthly">
        <text class="toggle-text">{{ showMonthly ? "收起 12 个月独立设定 ▲" : "展开 12 个月独立设定 (夏训/冬训调整) ▼" }}</text>
      </view>

      <view v-if="showMonthly" class="months-grid">
        <view v-for="(val, idx) in monthlyTargets" :key="idx" class="month-cell">
          <text class="month-label">{{ idx + 1 }}月</text>
          <input
            class="month-input"
            type="number"
            :value="val"
            @input="(e) => updateMonthTarget(idx, e.detail.value)"
          />
        </view>
      </view>
    </view>

    <!-- Physiological Parameters Card -->
    <view class="setting-card">
      <text class="card-title">心率与生理参数</text>
      
      <view class="form-item">
        <view class="form-label-row">
          <text class="form-label">最大心率 (Max HR)</text>
          <text class="form-val">{{ maxHr }} bpm</text>
        </view>
        <slider
          :value="maxHr"
          :min="150"
          :max="220"
          activeColor="#38bdf8"
          backgroundColor="rgba(255,255,255,0.1)"
          block-size="18"
          @change="(e) => maxHr = e.detail.value"
        />
      </view>

      <view class="form-item">
        <view class="form-label-row">
          <text class="form-label">静息心率 (Resting HR)</text>
          <text class="form-val">{{ restHr }} bpm</text>
        </view>
        <slider
          :value="restHr"
          :min="35"
          :max="90"
          activeColor="#10b981"
          backgroundColor="rgba(255,255,255,0.1)"
          block-size="18"
          @change="(e) => restHr = e.detail.value"
        />
      </view>
    </view>

    <!-- Save Button -->
    <view class="action-box">
      <button class="save-btn" :loading="saving" @click="handleSave">保存设定</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { request, getStoredUser } from "../../utils/api";

const overallTarget = ref(200);
const monthlyTargets = ref<number[]>(Array(12).fill(200));
const showMonthly = ref(false);
const maxHr = ref(190);
const restHr = ref(60);
const saving = ref(false);

function onSliderChange(e: any) {
  overallTarget.value = e.detail.value;
  monthlyTargets.value = Array(12).fill(e.detail.value);
}

function updateMonthTarget(idx: number, valStr: string) {
  const n = parseInt(valStr, 10) || 0;
  monthlyTargets.value[idx] = n;
}

async function loadData() {
  const user = getStoredUser();
  if (!user) return;

  try {
    const res = await request(`/api/profile/${user.id}`);
    if (res.goal) {
      overallTarget.value = res.goal.target_distance || 200;
      if (res.goal.monthly_targets && Array.isArray(res.goal.monthly_targets)) {
        monthlyTargets.value = res.goal.monthly_targets;
      } else {
        monthlyTargets.value = Array(12).fill(overallTarget.value);
      }
    }
    if (res.profile) {
      if (res.profile.max_heart_rate) maxHr.value = res.profile.max_heart_rate;
      if (res.profile.resting_heart_rate) restHr.value = res.profile.resting_heart_rate;
    }
  } catch (e) {
    console.error("Load goal error:", e);
  }
}

async function handleSave() {
  const user = getStoredUser();
  if (!user) return;

  saving.value = true;
  try {
    // 1. Save goal
    await request(`/api/profile/${user.id}/goal`, "PUT", {
      target_distance: overallTarget.value,
      monthly_targets: monthlyTargets.value,
    });

    // 2. Save physiological metrics
    await request(`/api/profile/${user.id}`, "PUT", {
      max_heart_rate: maxHr.value,
      resting_heart_rate: restHr.value,
    });

    uni.showToast({ title: "设定保存成功！", icon: "success" });
  } catch (e) {
    // Error toast handled by apiClient
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.goals-page {
  padding: 32rpx;
  background-color: #0a0a0a;
  min-height: 100vh;
}
.page-title-box {
  margin-bottom: 32rpx;
}
.title {
  font-size: 36rpx;
  font-weight: 800;
  color: #ffffff;
  display: block;
}
.subtitle {
  font-size: 22rpx;
  color: #71717a;
  margin-top: 6rpx;
  display: block;
}

.setting-card {
  background-color: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 32rpx;
  margin-bottom: 32rpx;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}
.card-title {
  font-size: 30rpx;
  font-weight: 700;
  color: #ffffff;
}
.target-display {
  font-size: 40rpx;
  font-weight: 800;
  color: #FC4C02;
}
.unit {
  font-size: 22rpx;
  color: #a1a1aa;
}

.chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-top: 24rpx;
  margin-bottom: 20rpx;
}
.chip {
  padding: 10rpx 24rpx;
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: 16rpx;
  font-size: 24rpx;
  color: #a1a1aa;
}
.chip.active {
  background-color: #FC4C02;
  color: #ffffff;
  font-weight: bold;
}

.breakdown-toggle {
  text-align: center;
  padding: 16rpx 0;
}
.toggle-text {
  font-size: 22rpx;
  color: #38bdf8;
}

.months-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16rpx;
  margin-top: 20rpx;
}
.month-cell {
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: 16rpx;
  padding: 12rpx;
  text-align: center;
}
.month-label {
  font-size: 20rpx;
  color: #71717a;
  display: block;
}
.month-input {
  font-size: 28rpx;
  color: #ffffff;
  font-weight: bold;
  margin-top: 4rpx;
}

.form-item {
  margin-top: 24rpx;
}
.form-label-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8rpx;
}
.form-label {
  font-size: 24rpx;
  color: #a1a1aa;
}
.form-val {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.action-box {
  margin-top: 48rpx;
}
.save-btn {
  background: linear-gradient(90deg, #FC4C02 0%, #ea580c 100%);
  color: #ffffff;
  font-size: 30rpx;
  font-weight: bold;
  height: 90rpx;
  line-height: 90rpx;
  border-radius: 24rpx;
}
</style>
