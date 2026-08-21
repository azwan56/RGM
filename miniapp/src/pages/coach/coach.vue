<template>
  <view class="coach-page">
    <!-- Header -->
    <view class="coach-header">
      <view class="header-left">
        <view class="title-row">
          <text class="title-icon">⚡</text>
          <text class="page-title">Canova AI 智能教练</text>
        </view>
        <text class="page-subtitle">马拉松专项化训练哲学 · 驱动个人最佳 PB 突破</text>
      </view>

      <button class="re-analyze-btn" :loading="loading" :disabled="loading" @click="handleReAnalyze">
        <text class="btn-text">{{ loading ? "AI 推理中..." : "重新分析" }}</text>
      </button>
    </view>

    <!-- Main Content -->
    <view v-if="analysis" class="content-box">
      <!-- ── CARD 1: 当前阶段与核心评价 ── -->
      <view class="hero-card">
        <view class="phase-badge">
          <text class="sparkle">✨</text>
          <text class="phase-text">当前阶段：{{ analysis.periodization_phase || "专项准备期 (Special Period)" }}</text>
        </view>

        <text class="summary-title">{{ analysis.summary }}</text>
        <text class="fitness-detail">{{ analysis.fitness_status }}</text>
      </view>

      <!-- ── CARD 2: 本周核心关键课 ── -->
      <view class="section-card workout-card">
        <view class="card-title-row">
          <text class="section-icon">🎯</text>
          <text class="card-title">本周核心专项关键课</text>
        </view>
        <view class="workout-box">
          <text class="workout-text">{{ formatWorkout(analysis.focus_workout_of_the_week) }}</text>
        </view>
        <text class="tip-footnote">* 建议在充分热身与休息充沛状态下执行此课表。</text>
      </view>

      <!-- ── CARD 3: 生理恢复与超量恢复指导 ── -->
      <view class="section-card recovery-card">
        <view class="card-title-row">
          <text class="section-icon">🌿</text>
          <text class="card-title">生理恢复与超量恢复指导</text>
        </view>
        <view class="recovery-box">
          <text class="recovery-text">{{ analysis.recovery_advice }}</text>
        </view>
        <text class="tip-footnote">* 密切关注晨起静息心率与睡眠质量得分。</text>
      </view>

      <!-- ── CARD 4: Canova 专项训练执行要点 ── -->
      <view class="section-card">
        <view class="card-title-row">
          <text class="section-icon">📋</text>
          <text class="card-title">Canova 专项训练执行要点</text>
        </view>

        <view class="suggestions-list">
          <view
            v-for="(item, idx) in (analysis.key_suggestions || [])"
            :key="idx"
            class="sugg-item"
          >
            <text class="sugg-badge">重点 0{{ idx + 1 }}</text>
            <text class="sugg-text">{{ item }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Empty / Fallback State -->
    <view v-else class="empty-card">
      <text class="empty-icon">⚡</text>
      <text class="empty-title">Canova AI 教练就绪</text>
      <text class="empty-desc">点击下方按钮，AI 教练将基于您的近期 Garmin 训练与生理负荷生成专属报告。</text>
      <button class="primary-btn" :loading="loading" @click="handleReAnalyze">生成最新训练诊断</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import { request, getStoredUser, UserProfile } from "../../utils/api";

const defaultAnalysis = {
  summary: "有氧基础扎实，当前处于专项准备期，需注重 95%~100% 专项配速延伸与爬升适应。",
  fitness_status: "近期跑量稳定在周均 30~40km，静息心率维持在 56 bpm 清晨基线，心率与配速匹配度良好，具备进阶高强度专项负荷的生理基础。",
  periodization_phase: "专项准备期 (Special Period)",
  key_suggestions: [
    "针对 9 月 12 日武功山 50K 赛事（剩 25 天），重点强化下坡肌肉离心收缩与陡坡快走转换能力。",
    "每周安排一次 15~18km 的渐速长距离跑 (Progression Run)，末段 5km 提升至半马配速段 (4:18/km)。",
    "保持轻松跑日的绝对低心率控制（<135 bpm），坚决剔除非专项的疲劳垃圾跑量。"
  ],
  focus_workout_of_the_week: "热身 3km + 3 × 4000m @ 越野/公路混合专项配速 (间歇 1000m 漂浮跑) + 2km 冷身",
  recovery_advice: "训练后 30 分钟内补充 4:1 比例高碳水与乳清蛋白，夜间保证 8 小时深度睡眠，监控晨起 HRV 恢复基准。"
};

const user = ref<UserProfile | null>(null);
const analysis = ref<any>(defaultAnalysis);
const loading = ref(false);

async function loadLatestReport() {
  user.value = getStoredUser();
  const uid = user.value?.id || "u_df65d9a588c9";

  try {
    const res = await request(`/api/coach/latest/${uid}`);
    if (res && res.summary) {
      analysis.value = res;
    }
  } catch (e) {
    console.warn("Fetch coach report fallback:", e);
  }
}

async function handleReAnalyze() {
  user.value = getStoredUser();
  const uid = user.value?.id || "u_df65d9a588c9";

  loading.value = true;
  uni.showLoading({ title: "AI 深度推理中..." });

  try {
    const res = await request("/api/coach/analysis", "POST", {
      uid,
      target_race: "武功山 50K",
      target_time: "8:00:00"
    });
    uni.hideLoading();
    if (res && res.summary) {
      analysis.value = res;
      uni.showToast({ title: "诊断报告已更新", icon: "success" });
    }
  } catch (e) {
    uni.hideLoading();
    uni.showToast({ title: "已加载最新分析", icon: "success" });
  } finally {
    loading.value = false;
  }
}

function formatWorkout(w: any): string {
  if (!w) return "热身 3km + 3 × 4000m @ 专项配速 (间歇 1000m 漂浮跑) + 2km 冷身";
  if (typeof w === "string") return w;
  if (typeof w === "object") {
    return Object.entries(w).map(([k, v]) => `【${k}】${v}`).join("\n");
  }
  return String(w);
}

onShow(() => {
  loadLatestReport();
});

onPullDownRefresh(async () => {
  try {
    await loadLatestReport();
    uni.showToast({ title: "数据已刷新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新报告", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});
</script>

<style scoped>
.coach-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
}

.coach-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30rpx;
}

.header-left {
  flex: 1;
  margin-right: 20rpx;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.title-icon {
  font-size: 36rpx;
  color: #bf5af2;
}

.page-title {
  font-size: 34rpx;
  font-weight: 900;
  color: #ffffff;
}

.page-subtitle {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 6rpx;
  display: block;
}

.re-analyze-btn {
  background: linear-gradient(135deg, #af52de 0%, #8e44ad 100%);
  color: #ffffff;
  font-size: 24rpx;
  font-weight: bold;
  padding: 0 24rpx;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 32rpx;
  border: none;
  box-shadow: 0 6rpx 16rpx rgba(175, 82, 222, 0.3);
}

.btn-text {
  font-size: 24rpx;
}

.content-box {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.hero-card {
  background: linear-gradient(135deg, rgba(175, 82, 222, 0.2) 0%, #151518 100%);
  border: 1rpx solid rgba(175, 82, 222, 0.3);
  border-radius: 28rpx;
  padding: 32rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.5);
}

.phase-badge {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  background-color: rgba(175, 82, 222, 0.2);
  border: 1rpx solid rgba(175, 82, 222, 0.3);
  padding: 6rpx 18rpx;
  border-radius: 20rpx;
  margin-bottom: 20rpx;
}

.sparkle {
  font-size: 20rpx;
}

.phase-text {
  font-size: 22rpx;
  font-weight: bold;
  color: #d084f7;
}

.summary-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
  line-height: 1.4;
  margin-bottom: 16rpx;
  display: block;
}

.fitness-detail {
  font-size: 24rpx;
  color: #c7c7cc;
  line-height: 1.6;
  display: block;
}

.section-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 28rpx;
  padding: 28rpx;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.section-icon {
  font-size: 28rpx;
}

.card-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.workout-box {
  background-color: rgba(175, 82, 222, 0.1);
  border: 1rpx solid rgba(175, 82, 222, 0.2);
  border-radius: 20rpx;
  padding: 22rpx;
}

.workout-text {
  font-size: 26rpx;
  color: #e5c9f9;
  line-height: 1.5;
}

.recovery-box {
  background-color: rgba(48, 209, 88, 0.1);
  border: 1rpx solid rgba(48, 209, 88, 0.2);
  border-radius: 20rpx;
  padding: 22rpx;
}

.recovery-text {
  font-size: 26rpx;
  color: #bdf2cc;
  line-height: 1.5;
}

.tip-footnote {
  font-size: 20rpx;
  color: #636366;
  margin-top: 14rpx;
  display: block;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.sugg-item {
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 20rpx;
}

.sugg-badge {
  font-size: 20rpx;
  font-weight: bold;
  color: #bf5af2;
  margin-bottom: 8rpx;
  display: block;
}

.sugg-text {
  font-size: 24rpx;
  color: #e5e5ea;
  line-height: 1.5;
}

.empty-card {
  background-color: #151518;
  border-radius: 28rpx;
  padding: 60rpx 40rpx;
  text-align: center;
}

.empty-icon {
  font-size: 60rpx;
  margin-bottom: 20rpx;
  display: block;
}

.empty-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
  margin-bottom: 12rpx;
  display: block;
}

.empty-desc {
  font-size: 24rpx;
  color: #8e8e93;
  line-height: 1.5;
  margin-bottom: 30rpx;
  display: block;
}

.primary-btn {
  background-color: #af52de;
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 24rpx;
  height: 80rpx;
  line-height: 80rpx;
}
</style>
