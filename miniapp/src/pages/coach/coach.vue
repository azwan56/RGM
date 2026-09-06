<template>
  <view class="coach-page">
    <!-- Header -->
    <view class="coach-header">
      <view class="header-left">
        <view class="title-row">
          <text class="title-icon">⚡</text>
          <text class="page-title">Canova AI 智能耐力教练</text>
        </view>
        <text class="page-subtitle">世界级专项化哲学 · 5K/半马/全马/越野因赛制宜 · 动态 TSB 与年龄自适应</text>
      </view>

      <button class="re-analyze-btn" :loading="loading" :disabled="loading" @click="handleReAnalyze">
        <text class="btn-text">{{ loading ? "AI 推理中..." : "启动专项推理" }}</text>
      </button>
    </view>

    <!-- ── ATHLETE PROFILE & TSB FORM CARD ── -->
    <view class="profile-card">
      <view class="profile-top">
        <view class="profile-name-box">
          <text class="profile-name">{{ athleteInfo.name || "跑者" }}</text>
          <text class="profile-meta">
            {{ athleteInfo.gender === 'female' ? '♀ 女' : '♂ 男' }} · 
            {{ athleteInfo.age ? `${athleteInfo.age} 岁` : '未录入年龄' }} · 
            跑龄 {{ athleteInfo.years_running || 2 }} 年
          </text>
        </view>
        <view class="tsb-badge" :class="tsbClass">
          <text class="tsb-badge-text">{{ tsbMetrics.status || "平衡稳健" }}</text>
        </view>
      </view>

      <view class="tsb-grid">
        <view class="tsb-item">
          <text class="tsb-label">体能 CTL</text>
          <text class="tsb-val text-cyan">{{ tsbMetrics.ctl || 0 }}</text>
        </view>
        <view class="tsb-item">
          <text class="tsb-label">疲劳 ATL</text>
          <text class="tsb-val text-amber">{{ tsbMetrics.atl || 0 }}</text>
        </view>
        <view class="tsb-item">
          <text class="tsb-label">状态 TSB</text>
          <text class="tsb-val" :class="tsbMetrics.tsb >= 0 ? 'text-green' : 'text-purple'">
            {{ tsbMetrics.tsb > 0 ? `+${tsbMetrics.tsb}` : (tsbMetrics.tsb || 0) }}
          </text>
        </view>
      </view>

      <view v-if="tsbMetrics.risk_warning" class="risk-box">
        <text class="risk-icon">⚠️</text>
        <text class="risk-text">{{ tsbMetrics.risk_warning }}</text>
      </view>
    </view>

    <!-- ── TARGET RACE CUSTOMIZATION CARD ── -->
    <view class="race-setup-card">
      <view class="card-title-row">
        <text class="section-icon">🎯</text>
        <text class="card-title">目标赛事与专项设定</text>
      </view>

      <!-- Preset Chips -->
      <view class="presets-row">
        <view
          v-for="(p, idx) in racePresets"
          :key="idx"
          class="preset-chip"
          :class="{ active: targetRace === p.race }"
          @click="applyPreset(p)"
        >
          <text class="chip-text">{{ p.label }}</text>
        </view>
      </view>

      <view class="inputs-row">
        <view class="input-col flex-2">
          <text class="input-label">目标赛事</text>
          <input
            v-model="targetRace"
            placeholder="如: 武功山 50K"
            class="setup-input"
          />
        </view>
        <view class="input-col flex-1">
          <text class="input-label">目标时间</text>
          <input
            v-model="targetTime"
            placeholder="8:00:00"
            class="setup-input"
          />
        </view>
      </view>
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

      <!-- ── CARD 1.2: 多赛事宏观统筹与战术推演 ── -->
      <view v-if="analysis.multi_race_strategy" class="section-card multi-race-card">
        <view class="card-title-row">
          <text class="section-icon">📅</text>
          <text class="card-title">Canova 多赛事宏观统筹与战术推演</text>
        </view>

        <!-- Macrocycle Overview -->
        <view class="macrocycle-box">
          <text class="macrocycle-label">🏆 赛季大周期统筹：</text>
          <text class="macrocycle-text">{{ analysis.multi_race_strategy.macro_cycle_overview }}</text>
        </view>

        <!-- Race Timeline List -->
        <view class="race-timeline-list">
          <view
            v-for="(r, idx) in (analysis.multi_race_strategy.race_timeline_advice || [])"
            :key="idx"
            class="race-item"
            :class="`tier-${r.tier ? r.tier.toLowerCase() : 'b'}`"
          >
            <view class="race-item-header">
              <view class="race-tier-badge" :class="`badge-${r.tier ? r.tier.toLowerCase() : 'b'}`">
                <text class="badge-text">{{ r.tactical_role || `${r.tier} 标` }}</text>
              </view>
              <text class="race-item-name">{{ r.race_name }}</text>
              <text v-if="r.days_left !== undefined" class="race-days-countdown">
                {{ r.days_left }}天后
              </text>
            </view>

            <view class="race-detail-row">
              <text class="detail-label">🎯 专项配速/心率：</text>
              <text class="detail-content">{{ r.pacing_strategy }}</text>
            </view>

            <view class="race-detail-row">
              <text class="detail-label">⏳ 减量与恢复规程：</text>
              <text class="detail-content">{{ r.taper_recovery_rule }}</text>
            </view>
          </view>
        </view>

        <!-- Conflict & Synergy Warning -->
        <view v-if="analysis.multi_race_strategy.conflict_resolution" class="conflict-box">
          <text class="conflict-title">⚠️ 战术规避与周期协同：</text>
          <text class="conflict-desc">{{ analysis.multi_race_strategy.conflict_resolution }}</text>
        </view>
      </view>

      <!-- ── CARD 1.5: CANOVA 比赛专项刺激区间 ── -->
      <view v-if="analysis.race_zones" class="section-card">
        <view class="card-title-row">
          <text class="section-icon">⚡</text>
          <text class="card-title">Canova 比赛专项刺激区间 ({{ targetRace }})</text>
        </view>

        <view class="zones-list">
          <view
            v-for="(z, key) in analysis.race_zones"
            :key="key"
            class="zone-item"
          >
            <view class="zone-header">
              <text class="zone-name">{{ z.name }}</text>
              <text class="zone-range">{{ z.range }}</text>
            </view>
            <text class="zone-desc">{{ z.desc }}</text>
          </view>
        </view>
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
      <text class="empty-desc">配置您的目标赛事，点击下方按钮，AI 教练将基于您的近期 Garmin / 高驰训练与生理负荷生成专属报告。</text>
      <button class="primary-btn" :loading="loading" @click="handleReAnalyze">生成最新训练诊断</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import { request, getStoredUser, checkAndAutoLogin, UserProfile } from "../../utils/api";

const racePresets = [
  { label: "🏔️ 武功山 50K", race: "武功山 50K", time: "8:00:00", type: "trail" },
  { label: "🏅 无锡全马", race: "无锡马拉松", time: "3:15:00", type: "marathon" },
  { label: "⚡ 上海半马", race: "上海半程马拉松", time: "1:35:00", type: "half" },
  { label: "🏃 10K 速度", race: "日常 10公里 突破", time: "42:00", type: "10k" },
];

const targetRace = ref("武功山 50K");
const targetTime = ref("8:00:00");
const raceType = ref("trail");

function applyPreset(p: any) {
  targetRace.value = p.race;
  targetTime.value = p.time;
  raceType.value = p.type;
}

const defaultAnalysis = {
  summary: "欢迎来到 Renato Canova AI 耐力教练专区！绑定 Garmin 或高驰手表后将自动生成您的专属报告。",
  fitness_status: "系统将基于您的每日配速、静息心率与夜间 HRV 恢复状态，智能量化评估专项耐力与疲劳水平。",
  periodization_phase: "准备启动期 (Preparation)",
  key_suggestions: [
    "在【我的】页面绑定您的 Garmin 或高驰账号，开启历史运动与每日生理指标同步。",
    "以轻松跑 (Zone 2) 为主积累有氧基线，建立慢肌纤维毛细血管网。",
    "保持科学作息，长跑后注意水分电解质补充与睡眠恢复。"
  ],
  focus_workout_of_the_week: "基础有氧建立：轻松跑 30~45 分钟，心率控制在最大心率的 65%~75% 之间。",
  recovery_advice: "夜间保证 7~8 小时高质量睡眠，观察晨起静息心率变化，建立稳定生理基线。"
};

const user = ref<UserProfile | null>(null);
const analysis = ref<any>(defaultAnalysis);
const loading = ref(false);

const athleteInfo = computed(() => analysis.value?.athlete_snapshot || {});
const tsbMetrics = computed(() => analysis.value?.tsb_metrics || {});

const tsbClass = computed(() => {
  const val = tsbMetrics.value?.tsb ?? 0;
  if (val > 15) return "tsb-fresh";
  if (val >= -10) return "tsb-neutral";
  if (val >= -30) return "tsb-optimal";
  if (val >= -45) return "tsb-fatigued";
  return "tsb-danger";
});

async function loadLatestReport() {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    const res = await request(`/api/coach/latest/${uid}`);
    if (res && res.summary) {
      analysis.value = res;
      if (res.athlete_snapshot?.target_race) {
        targetRace.value = res.athlete_snapshot.target_race;
      }
      if (res.athlete_snapshot?.target_time) {
        targetTime.value = res.athlete_snapshot.target_time;
      }
      if (res.athlete_snapshot?.race_category) {
        raceType.value = res.athlete_snapshot.race_category;
      }
    }
  } catch (e) {
    console.warn("Fetch coach report fallback:", e);
  }
}

async function handleReAnalyze() {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  loading.value = true;
  uni.showLoading({ title: "AI 深度推理中..." });

  try {
    const res = await request("/api/coach/analysis", "POST", {
      uid,
      target_race: targetRace.value,
      target_time: targetTime.value,
      race_type: raceType.value
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

/* ── PROFILE & TSB CARD ── */
.profile-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
}

.profile-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.profile-name {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
}

.profile-meta {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 4rpx;
  display: block;
}

.tsb-badge {
  padding: 6rpx 18rpx;
  border-radius: 24rpx;
  border: 1rpx solid transparent;
}

.tsb-badge-text {
  font-size: 20rpx;
  font-weight: bold;
}

.tsb-fresh {
  background-color: rgba(48, 209, 88, 0.15);
  border-color: rgba(48, 209, 88, 0.3);
  color: #30d158;
}

.tsb-neutral {
  background-color: rgba(100, 210, 255, 0.15);
  border-color: rgba(100, 210, 255, 0.3);
  color: #64d2ff;
}

.tsb-optimal {
  background-color: rgba(175, 82, 222, 0.15);
  border-color: rgba(175, 82, 222, 0.3);
  color: #d084f7;
}

.tsb-fatigued {
  background-color: rgba(255, 159, 10, 0.15);
  border-color: rgba(255, 159, 10, 0.3);
  color: #ff9f0a;
}

.tsb-danger {
  background-color: rgba(255, 69, 58, 0.15);
  border-color: rgba(255, 69, 58, 0.3);
  color: #ff453a;
}

.tsb-grid {
  display: flex;
  gap: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
}

.tsb-item {
  flex: 1;
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 16rpx 12rpx;
  text-align: center;
}

.tsb-label {
  font-size: 20rpx;
  color: #8e8e93;
  display: block;
  margin-bottom: 4rpx;
}

.tsb-val {
  font-size: 28rpx;
  font-weight: 900;
  display: block;
}

.text-cyan { color: #64d2ff; }
.text-amber { color: #ff9f0a; }
.text-green { color: #30d158; }
.text-purple { color: #bf5af2; }

.risk-box {
  margin-top: 18rpx;
  background-color: rgba(255, 69, 58, 0.1);
  border: 1rpx solid rgba(255, 69, 58, 0.25);
  border-radius: 18rpx;
  padding: 16rpx;
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
}

.risk-icon {
  font-size: 24rpx;
}

.risk-text {
  font-size: 22rpx;
  color: #ffb4ab;
  line-height: 1.4;
  flex: 1;
}

/* ── RACE SETUP CARD ── */
.race-setup-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
}

.presets-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.preset-chip {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  padding: 8rpx 20rpx;
  border-radius: 20rpx;
}

.preset-chip.active {
  background-color: rgba(175, 82, 222, 0.25);
  border-color: #af52de;
}

.chip-text {
  font-size: 22rpx;
  color: #c7c7cc;
}

.preset-chip.active .chip-text {
  color: #ffffff;
  font-weight: bold;
}

.inputs-row {
  display: flex;
  gap: 16rpx;
}

.input-col {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.flex-2 { flex: 2; }
.flex-1 { flex: 1; }

.input-label {
  font-size: 20rpx;
  color: #8e8e93;
}

.setup-input {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
  height: 64rpx;
  padding: 0 16rpx;
  font-size: 24rpx;
  color: #ffffff;
}

/* ── ZONES LIST ── */
.zones-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.zone-item {
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 18rpx;
}

.zone-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6rpx;
}

.zone-name {
  font-size: 24rpx;
  font-weight: bold;
  color: #e5e5ea;
}

.zone-range {
  font-size: 24rpx;
  font-weight: 900;
  color: #d084f7;
}

.zone-desc {
  font-size: 20rpx;
  color: #8e8e93;
  line-height: 1.4;
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

.multi-race-card {
  border-left: 6rpx solid #bf5af2;
}

.macrocycle-box {
  background: linear-gradient(135deg, rgba(88, 28, 135, 0.25), rgba(26, 26, 30, 0.8));
  border: 1rpx solid rgba(191, 90, 242, 0.3);
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 24rpx;
}

.macrocycle-label {
  font-size: 22rpx;
  font-weight: bold;
  color: #d8b4fe;
  display: block;
  margin-bottom: 8rpx;
}

.macrocycle-text {
  font-size: 24rpx;
  color: #f3f4f6;
  line-height: 1.5;
  display: block;
}

.race-timeline-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  margin-bottom: 24rpx;
}

.race-item {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 22rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}

.race-item.tier-a {
  border-color: rgba(244, 63, 94, 0.4);
  background-color: rgba(30, 18, 24, 0.9);
}

.race-item.tier-b {
  border-color: rgba(56, 189, 248, 0.3);
  background-color: rgba(18, 24, 30, 0.9);
}

.race-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
  gap: 12rpx;
}

.race-tier-badge {
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  font-size: 20rpx;
  font-weight: bold;
}

.badge-a {
  background-color: rgba(244, 63, 94, 0.2);
  color: #fb7185;
  border: 1rpx solid rgba(244, 63, 94, 0.4);
}

.badge-b {
  background-color: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
  border: 1rpx solid rgba(56, 189, 248, 0.4);
}

.badge-c {
  background-color: rgba(161, 161, 170, 0.2);
  color: #d4d4d8;
  border: 1rpx solid rgba(161, 161, 170, 0.4);
}

.badge-text {
  font-size: 20rpx;
}

.race-item-name {
  flex: 1;
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.race-days-countdown {
  font-size: 22rpx;
  color: #bf5af2;
  font-weight: bold;
}

.race-detail-row {
  margin-top: 10rpx;
  background-color: rgba(0, 0, 0, 0.25);
  padding: 12rpx 16rpx;
  border-radius: 14rpx;
}

.detail-label {
  font-size: 20rpx;
  font-weight: bold;
  color: #a1a1aa;
  margin-bottom: 4rpx;
  display: block;
}

.detail-content {
  font-size: 22rpx;
  color: #e4e4e7;
  line-height: 1.4;
  display: block;
}

.conflict-box {
  background-color: rgba(245, 158, 11, 0.1);
  border: 1rpx solid rgba(245, 158, 11, 0.35);
  border-radius: 20rpx;
  padding: 20rpx;
}

.conflict-title {
  font-size: 22rpx;
  font-weight: bold;
  color: #fbbf24;
  display: block;
  margin-bottom: 8rpx;
}

.conflict-desc {
  font-size: 22rpx;
  color: #fef3c7;
  line-height: 1.5;
  display: block;
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
