<template>
  <view class="pec-card" :class="[themeClass, { 'pec-light': isVolt }]">
    <!-- Top Header -->
    <view class="pec-header">
      <view class="pec-title-col">
        <view class="pec-title-row">
          <text class="pec-emoji">🐰</text>
          <text class="pec-title">马拉松官兔胜任度评估</text>
          <text class="pec-tag">六维量化</text>
        </view>
        <text class="pec-sub">融合赛事规程标牌、当期实力与证书双闸门、90天稳态控速波动</text>
      </view>
      <view v-if="sel" class="pec-share-btn" @click="showResumeModal = true">
        📋 履历卡
      </view>
    </view>

    <!-- Distance Mode Tabs -->
    <view class="pec-dist-tabs">
      <view
        v-for="dt in distanceTabs"
        :key="dt.key"
        class="pec-dist-tab"
        :class="{ active: distanceType === dt.key }"
        @click="switchDistance(dt.key)"
      >
        {{ dt.label }}
      </view>
    </view>

    <!-- Event Selector OR Custom Club LSD Inputs -->
    <view v-if="distanceType !== 'custom'" class="pec-event-box">
      <view v-if="upcomingRoadRaces.length > 0" class="pec-chip-section">
        <text class="pec-chip-label">🎯 待参赛程：</text>
        <scroll-view scroll-x class="pec-h-scroll" show-scrollbar="false">
          <view class="pec-chip-row">
            <view
              v-for="ur in upcomingRoadRaces"
              :key="ur.id || ur.name"
              class="pec-chip upcoming"
              :class="{ active: eventName === ur.name }"
              @click="selectEvent(ur.name, ur.date || '')"
            >
              {{ ur.name }}
            </view>
          </view>
        </scroll-view>
      </view>

      <scroll-view scroll-x class="pec-h-scroll" show-scrollbar="false">
        <view class="pec-chip-row">
          <view
            v-for="ev in hotEvents"
            :key="ev"
            class="pec-chip"
            :class="{ active: eventName === ev }"
            @click="selectEvent(ev, '')"
          >
            {{ ev }}
          </view>
        </view>
      </scroll-view>

      <view class="pec-search-row">
        <input
          v-model="customEventInput"
          class="pec-search-input"
          placeholder="输入任意路跑赛事名称检索规程..."
          confirm-type="search"
          @confirm="searchCustomEvent"
        />
        <view class="pec-search-btn" @click="searchCustomEvent">
          {{ searchingWeb ? "校准中..." : "🔍 校准" }}
        </view>
      </view>

      <view v-if="calib?.calibration_tags?.length" class="pec-calib-tags">
        <text
          v-for="(tg, idx) in calib.calibration_tags"
          :key="idx"
          class="pec-calib-tag"
        >
          {{ tg }}
        </text>
      </view>
    </view>

    <view v-else class="pec-event-box">
      <text class="pec-lsd-tip">🐰 跑团内部拉练模式：豁免官方田协证书，聚焦当期真实体能与控速节拍</text>
      <view class="pec-custom-inputs">
        <view class="pec-input-col">
          <text class="pec-input-lbl">拉练距离 (km)</text>
          <input v-model="customDistKm" type="number" class="pec-mini-input" />
        </view>
        <view class="pec-input-col">
          <text class="pec-input-lbl">领跑配速 (分:秒)</text>
          <input v-model="customPaceStr" class="pec-mini-input" placeholder="5:00" />
        </view>
        <view class="pec-recalc-btn" @click="loadEvaluation(false)">测算</view>
      </view>
    </view>

    <!-- All-Groups Suitability Matrix Strip -->
    <view v-if="distanceType !== 'custom' && allGroups.length > 0" class="pec-matrix-wrap">
      <view class="pec-matrix-head">
        <text class="pec-matrix-lbl">全组别适配矩阵（点击切换）</text>
        <text v-if="evalData?.recommended_group" class="pec-matrix-rec">
          ★ 首推 {{ evalData.recommended_group.group_label }}
        </text>
      </view>
      <scroll-view scroll-x class="pec-h-scroll" show-scrollbar="false">
        <view class="pec-group-row">
          <view
            v-for="g in allGroups"
            :key="g.group_code"
            class="pec-group-pill"
            :class="{ active: sel?.group_code === g.group_code }"
            @click="selectGroup(g.group_code)"
          >
            <text v-if="g.is_recommended" class="pec-rec-star">★首推</text>
            <text class="pec-g-code">{{ g.group_code }}兔</text>
            <text class="pec-g-pace">{{ formatPaceLabel(g.target_pace_str) }}</text>
            <text class="pec-g-score" :style="{ color: adaptTone(g.verdict_color) }">{{ g.overall_score }}分 · {{ g.grade }}</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- Main Result -->
    <view v-if="loading && !sel" class="pec-loading">正在演算六维官兔胜任度...</view>
    <view v-else-if="sel" class="pec-body">
      <!-- Score Hero -->
      <view class="pec-hero">
        <view class="pec-hero-left">
          <text class="pec-hero-ev">{{ calib?.event_name }} · {{ sel.group_label }}</text>
          <text class="pec-hero-time">
            {{ sel.target_time }} <text class="pec-hero-pace">({{ formatPaceLabel(sel.target_pace_str) }})</text>
          </text>
          <text
            class="pec-verdict-pill"
            :style="{ color: adaptTone(sel.verdict_color), backgroundColor: (sel.verdict_color || '#fc4c02') + '20' }"
          >
            {{ sel.verdict_label }}
          </text>
        </view>
        <view class="pec-score-ring">
          <text class="pec-score-num">{{ sel.overall_score }}</text>
          <text class="pec-score-grade" :style="{ color: adaptTone(sel.verdict_color) }">{{ sel.grade }}级</text>
        </view>
      </view>

      <view v-if="sel.gates?.cert_gate?.status === 'missing_cert'" class="pec-priv-banner">
        <text>🏃 跑团私兔 / 内部拉练兔真实胜任分：</text>
        <text class="pec-priv-score">{{ sel.private_pacer_score }} / 100</text>
      </view>

      <!-- Dual Gatekeepers -->
      <view class="pec-gates">
        <view
          v-for="gk in visibleGates"
          :key="gk.key"
          class="pec-gate-item"
          :class="'gate-' + gk.status"
        >
          <text class="pec-gate-badge">{{ gk.badge }}</text>
          <text class="pec-gate-detail">{{ gk.detail }}</text>
        </view>
      </view>

      <!-- 6-Dimension Bars -->
      <view class="pec-dims">
        <view v-for="dim in sel.dimensions" :key="dim.key" class="pec-dim-card">
          <view class="pec-dim-top">
            <text class="pec-dim-name">{{ dim.label }} ({{ dim.weight_pct }}%)</text>
            <text class="pec-dim-score">{{ dim.score }}分</text>
          </view>
          <text class="pec-dim-val">{{ dim.display_value }}</text>
          <view class="pec-bar-bg">
            <view
              class="pec-bar-fill"
              :style="{ width: Math.min(100, Math.max(8, dim.score || 0)) + '%' }"
            />
          </view>
          <text class="pec-dim-desc">{{ dim.desc }}</text>
        </view>
      </view>

      <!-- Showcase Run Summary -->
      <view v-if="showcase" class="pec-showcase">
        <view class="pec-showcase-top">
          <text class="pec-showcase-title">⏱️ 稳态巡航代表作：{{ showcase.name }}</text>
          <text class="pec-showcase-sigma">±{{ showcase.sigma_gap_sec }}s/km</text>
        </view>
        <text class="pec-showcase-meta">
          {{ showcase.date }} · {{ showcase.distance_km }}km · 均配 {{ formatPaceLabel(showcase.avg_pace_str) }}（已剥离热身冷身与红绿灯单点停顿）
        </text>
      </view>

      <!-- Action Tips -->
      <view v-if="sel.action_tips?.length" class="pec-tips-box">
        <text class="pec-tips-title">🎯 官兔选拔冲刺建议</text>
        <text v-for="(tip, idx) in sel.action_tips" :key="idx" class="pec-tip-line">
          • {{ tip }}
        </text>
      </view>

      <!-- On-Demand AI Prescription & Recruitment Bio -->
      <view class="pec-ai-box">
        <view class="pec-ai-head">
          <view>
            <text class="pec-ai-title">✨ AI 4周盲跑处方 & 竞选自荐语</text>
            <text class="pec-ai-sub">一键生成无表定速特训与报名表180字自荐陈词</text>
          </view>
          <view class="pec-ai-btn" @click="generateAiBio">
            {{ aiLoading ? "撰写中..." : aiResult ? "重新生成" : "立即生成" }}
          </view>
        </view>

        <view v-if="aiResult" class="pec-ai-content">
          <text v-if="aiResult.pacing_strategy_tip" class="pec-ai-strat">
            🧭 {{ aiResult.pacing_strategy_tip }}
          </text>
          <view class="pec-ai-plan">
            <text class="pec-ai-sec-lbl">📅 赛前4周盲跑特训重点</text>
            <text class="pec-ai-text">{{ aiResult.four_week_plan }}</text>
          </view>
          <view class="pec-ai-bio">
            <view class="pec-ai-bio-top">
              <text class="pec-ai-sec-lbl">📝 组委会报名表竞选自荐语</text>
              <text class="pec-copy-pill" @click="copyBio">📋 一键复制</text>
            </view>
            <text class="pec-ai-text">{{ aiResult.application_statement }}</text>
          </view>
        </view>
      </view>
    </view>

    <PacerResumeModal
      :visible="showResumeModal"
      :eval-data="evalData"
      @close="showResumeModal = false"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { request } from "../utils/api";
import { isVolt, themeClass } from "../utils/theme";
import PacerResumeModal from "./PacerResumeModal.vue";

const props = defineProps<{
  uid: string;
  viewerUid?: string;
}>();

const distanceTabs = [
  { key: "fm", label: "全马官兔" },
  { key: "hm", label: "半马官兔" },
  { key: "10k", label: "10K路跑" },
  { key: "custom", label: "跑团拉练" },
] as const;

const hotEvents = [
  "上海马拉松",
  "北京马拉松",
  "厦门马拉松",
  "无锡马拉松",
  "武汉马拉松",
  "成都马拉松",
  "广州马拉松",
  "兰州马拉松",
];

const distanceType = ref<"fm" | "hm" | "10k" | "custom">("fm");
const eventName = ref<string>("上海马拉松");
const targetRaceDate = ref<string>("");
const customEventInput = ref<string>("");
const selectedGroup = ref<string>("");
const customDistKm = ref<string>("30");
const customPaceStr = ref<string>("5:00");

const evalData = ref<any>(null);
const loading = ref<boolean>(false);
const searchingWeb = ref<boolean>(false);

const aiLoading = ref<boolean>(false);
const aiResult = ref<any>(null);
const showResumeModal = ref<boolean>(false);

const sel = computed(() => evalData.value?.selected_evaluation || null);
const calib = computed(() => evalData.value?.event_calibration || null);
const allGroups = computed(() => evalData.value?.all_groups_matrix || []);
const showcase = computed(() => evalData.value?.showcase_run || null);
const upcomingRoadRaces = computed(() =>
  (evalData.value?.upcoming_races || []).filter((r: any) => !r.is_trail).slice(0, 3)
);

const visibleGates = computed(() => {
  const gMap = sel.value?.gates || {};
  const list: any[] = [];
  ["fitness_gate", "cert_gate", "schedule_gate", "age_gate"].forEach((k) => {
    const obj = gMap[k];
    if (!obj) return;
    if ((k === "schedule_gate" || k === "age_gate") && obj.status === "pass") return;
    list.push({ key: k, ...obj });
  });
  return list;
});

function formatPaceLabel(s?: string) {
  if (!s) return "--";
  return s.endsWith("/km") ? s : `${s}/km`;
}

function adaptTone(c?: string): string {
  if (!c) return isVolt.value ? "#0f172a" : "#ffffff";
  if (!isVolt.value) return c;
  const low = c.toLowerCase();
  if (low === "#fbbf24" || low === "#fcd34d" || low === "#f59e0b" || low === "#fde68a") return "#b45309";
  if (low === "#34d399" || low === "#10b981" || low === "#22c55e" || low === "#4ade80") return "#047857";
  if (low === "#38bdf8" || low === "#60a5fa") return "#0369a1";
  if (low === "#f87171" || low === "#fb7185") return "#be123c";
  return c;
}

async function loadEvaluation(allowWeb = false) {
  if (!props.uid) return;
  if (allowWeb) searchingWeb.value = true;
  else loading.value = true;
  try {
    const parts: string[] = [`distance_type=${encodeURIComponent(distanceType.value)}`];
    if (distanceType.value !== "custom" && eventName.value) {
      parts.push(`event_name=${encodeURIComponent(eventName.value)}`);
    }
    if (selectedGroup.value) {
      parts.push(`target_group=${encodeURIComponent(selectedGroup.value)}`);
    }
    if (targetRaceDate.value) {
      parts.push(`target_race_date=${encodeURIComponent(targetRaceDate.value)}`);
    }
    if (distanceType.value === "custom") {
      parts.push(`custom_distance_km=${encodeURIComponent(customDistKm.value || "30")}`);
      parts.push(`custom_target_pace=${encodeURIComponent(customPaceStr.value || "5:00")}`);
    }
    if (props.viewerUid && props.viewerUid !== props.uid) {
      parts.push(`viewer_uid=${encodeURIComponent(props.viewerUid)}`);
    }
    parts.push(`allow_web_search=${allowWeb ? "true" : "false"}`);

    const res: any = await request(
      `/api/science/pacer-eval/${encodeURIComponent(props.uid)}?${parts.join("&")}`
    );
    if (res) {
      evalData.value = res;
      if (!selectedGroup.value && res.selected_evaluation?.group_code) {
        selectedGroup.value = res.selected_evaluation.group_code;
      }
    }
  } catch (e) {
    console.error("MiniApp pacer eval error:", e);
  } finally {
    loading.value = false;
    searchingWeb.value = false;
  }
}

function switchDistance(d: "fm" | "hm" | "10k" | "custom") {
  distanceType.value = d;
  selectedGroup.value = "";
  aiResult.value = null;
  loadEvaluation(false);
}

function selectEvent(ev: string, dt = "") {
  eventName.value = ev;
  targetRaceDate.value = dt;
  aiResult.value = null;
  loadEvaluation(false);
}

function searchCustomEvent() {
  const q = customEventInput.value.trim();
  if (!q) return;
  eventName.value = q;
  aiResult.value = null;
  loadEvaluation(true);
}

function selectGroup(code: string) {
  selectedGroup.value = code;
  aiResult.value = null;
  loadEvaluation(false);
}

async function generateAiBio() {
  if (!props.uid || !sel.value || aiLoading.value) return;
  aiLoading.value = true;
  try {
    const res: any = await request(
      `/api/science/pacer-ai-prescription/${encodeURIComponent(props.uid)}`,
      "POST",
      {
        event_name: distanceType.value === "custom" ? "跑团专场模拟拉练" : eventName.value,
        distance_type: distanceType.value,
        target_group: sel.value.group_code,
        custom_distance_km: distanceType.value === "custom" ? Number(customDistKm.value || 30) : undefined,
        custom_target_pace: distanceType.value === "custom" ? customPaceStr.value : undefined,
        target_race_date: targetRaceDate.value || undefined,
      }
    );
    if (res?.success) {
      aiResult.value = res;
    }
  } catch (e) {
    uni.showToast({ title: "生成失败，请稍后重试", icon: "none" });
  } finally {
    aiLoading.value = false;
  }
}

function copyBio() {
  if (!aiResult.value?.application_statement) return;
  uni.setClipboardData({
    data: aiResult.value.application_statement,
    success: () => {
      uni.showToast({ title: "自荐语已复制", icon: "success" });
    },
  });
}

watch(
  () => props.uid,
  (u) => {
    if (u) loadEvaluation(false);
  }
);

onMounted(() => {
  if (props.uid) loadEvaluation(false);
});
</script>

<style scoped>
.pec-card {
  min-height: auto;
  box-sizing: border-box;
  margin-top: 24rpx;
  padding: 28rpx;
  border-radius: 32rpx;
  background: #14151b;
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  display: flex;
  flex-direction: column;
  gap: 22rpx;
}
.pec-light.pec-card {
  background: #ffffff;
  border-color: rgba(252, 76, 2, 0.28);
  box-shadow: 0 8rpx 28rpx rgba(15, 23, 42, 0.06);
}
.pec-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
}
.pec-title-col {
  flex: 1;
}
.pec-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
}
.pec-emoji {
  font-size: 34rpx;
}
.pec-title {
  font-size: 30rpx;
  font-weight: 800;
  color: #ffffff;
}
.pec-light .pec-title {
  color: #0f172a;
}
.pec-tag {
  font-size: 20rpx;
  font-weight: 700;
  color: #fc4c02;
  background: rgba(252, 76, 2, 0.14);
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
}
.pec-sub {
  display: block;
  margin-top: 6rpx;
  font-size: 22rpx;
  color: #94a3b8;
  line-height: 1.4;
}
.pec-share-btn {
  padding: 12rpx 22rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #fc4c02, #f59e0b);
  color: #ffffff;
  font-size: 23rpx;
  font-weight: 800;
  flex-shrink: 0;
}
.pec-dist-tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10rpx;
}
.pec-dist-tab {
  text-align: center;
  padding: 14rpx 6rpx;
  border-radius: 18rpx;
  font-size: 23rpx;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.05);
  color: #cbd5e1;
}
.pec-light .pec-dist-tab {
  background: #f1f5f9;
  color: #334155;
}
.pec-dist-tab.active {
  background: #fc4c02;
  color: #ffffff;
}
.pec-event-box {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 22rpx;
  padding: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.pec-light .pec-event-box {
  background: #f8fafc;
}
.pec-chip-label {
  font-size: 22rpx;
  font-weight: 700;
  color: #10b981;
  margin-bottom: 8rpx;
  display: block;
}
.pec-h-scroll {
  width: 100%;
  white-space: nowrap;
}
.pec-chip-row {
  display: inline-flex;
  gap: 12rpx;
}
.pec-chip {
  padding: 10rpx 20rpx;
  border-radius: 14rpx;
  font-size: 22rpx;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
}
.pec-light .pec-chip {
  background: #e2e8f0;
  color: #475569;
}
.pec-chip.active {
  background: rgba(252, 76, 2, 0.2);
  color: #fc4c02;
  border: 1rpx solid rgba(252, 76, 2, 0.5);
}
.pec-search-row {
  display: flex;
  gap: 12rpx;
  align-items: center;
}
.pec-search-input {
  flex: 1;
  height: 64rpx;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 16rpx;
  padding: 0 20rpx;
  font-size: 23rpx;
  color: #ffffff;
}
.pec-light .pec-search-input {
  background: #ffffff;
  color: #0f172a;
  border: 1rpx solid #cbd5e1;
}
.pec-search-btn {
  padding: 0 24rpx;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 16rpx;
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  font-size: 23rpx;
  font-weight: 700;
}
.pec-light .pec-search-btn {
  background: #0f172a;
  color: #ffffff;
}
.pec-calib-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
}
.pec-calib-tag {
  font-size: 20rpx;
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.05);
  color: #cbd5e1;
}
.pec-light .pec-calib-tag {
  background: #e2e8f0;
  color: #334155;
}
.pec-lsd-tip {
  font-size: 22rpx;
  color: #f59e0b;
  line-height: 1.4;
}
.pec-custom-inputs {
  display: flex;
  align-items: flex-end;
  gap: 16rpx;
}
.pec-input-col {
  flex: 1;
}
.pec-input-lbl {
  font-size: 20rpx;
  color: #94a3b8;
  display: block;
  margin-bottom: 6rpx;
}
.pec-mini-input {
  height: 64rpx;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 14rpx;
  padding: 0 18rpx;
  font-size: 24rpx;
  color: #ffffff;
}
.pec-light .pec-mini-input {
  background: #ffffff;
  color: #0f172a;
  border: 1rpx solid #cbd5e1;
}
.pec-recalc-btn {
  height: 64rpx;
  line-height: 64rpx;
  padding: 0 28rpx;
  border-radius: 14rpx;
  background: #fc4c02;
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 800;
}
.pec-matrix-head {
  display: flex;
  justify-content: space-between;
  font-size: 22rpx;
  margin-bottom: 10rpx;
}
.pec-matrix-lbl {
  color: #94a3b8;
}
.pec-matrix-rec {
  color: #10b981;
  font-weight: 700;
}
.pec-group-row {
  display: inline-flex;
  gap: 14rpx;
  padding-top: 8rpx;
}
.pec-group-pill {
  position: relative;
  min-width: 144rpx;
  padding: 16rpx 18rpx;
  border-radius: 20rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.pec-light .pec-group-pill {
  background: #f8fafc;
  border-color: #e2e8f0;
}
.pec-group-pill.active {
  border-color: #fc4c02;
  background: rgba(252, 76, 2, 0.14);
}
.pec-rec-star {
  font-size: 18rpx;
  color: #10b981;
  font-weight: 800;
}
.pec-g-code {
  font-size: 25rpx;
  font-weight: 800;
  color: #ffffff;
}
.pec-light .pec-g-code {
  color: #0f172a;
}
.pec-g-pace {
  font-size: 20rpx;
  color: #94a3b8;
}
.pec-g-score {
  font-size: 22rpx;
  font-weight: 800;
}
.pec-loading {
  padding: 50rpx 0;
  text-align: center;
  font-size: 25rpx;
  color: #94a3b8;
}
.pec-body {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.pec-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx;
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.04);
}
.pec-light .pec-hero {
  background: #f8fafc;
}
.pec-hero-left {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  flex: 1;
}
.pec-hero-ev {
  font-size: 22rpx;
  color: #94a3b8;
}
.pec-hero-time {
  font-size: 34rpx;
  font-weight: 900;
  color: #ffffff;
}
.pec-light .pec-hero-time {
  color: #0f172a;
}
.pec-hero-pace {
  font-size: 24rpx;
  color: #fc4c02;
}
.pec-verdict-pill {
  align-self: flex-start;
  padding: 6rpx 18rpx;
  border-radius: 999rpx;
  font-size: 22rpx;
  font-weight: 800;
}
.pec-score-ring {
  width: 136rpx;
  height: 136rpx;
  border-radius: 999rpx;
  border: 6rpx solid #fc4c02;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.pec-score-num {
  font-size: 44rpx;
  font-weight: 900;
  color: #ffffff;
  line-height: 1;
}
.pec-light .pec-score-num {
  color: #0f172a;
}
.pec-score-grade {
  font-size: 22rpx;
  font-weight: 800;
  margin-top: 4rpx;
}
.pec-priv-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 22rpx;
  border-radius: 18rpx;
  background: rgba(245, 158, 11, 0.14);
  font-size: 23rpx;
  color: #fbbf24;
}
.pec-light .pec-priv-banner {
  color: #b45309;
}
.pec-priv-score {
  font-weight: 900;
  color: #10b981;
}
.pec-gates {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.pec-gate-item {
  padding: 18rpx 20rpx;
  border-radius: 18rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}
.gate-pass,
.gate-exempt {
  background: rgba(16, 185, 129, 0.12);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
}
.gate-warn,
.gate-missing_cert,
.gate-conflict {
  background: rgba(245, 158, 11, 0.12);
  border: 1rpx solid rgba(245, 158, 11, 0.38);
}
.gate-fail {
  background: rgba(239, 68, 68, 0.12);
  border: 1rpx solid rgba(239, 68, 68, 0.38);
}
.pec-gate-badge {
  font-size: 24rpx;
  font-weight: 800;
  color: #ffffff;
}
.pec-light .pec-gate-badge {
  color: #0f172a;
}
.pec-gate-detail {
  font-size: 21rpx;
  color: #cbd5e1;
  line-height: 1.45;
}
.pec-light .pec-gate-detail {
  color: #475569;
}
.pec-dims {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}
.pec-dim-card {
  padding: 20rpx;
  border-radius: 20rpx;
  background: rgba(255, 255, 255, 0.03);
}
.pec-light .pec-dim-card {
  background: #f8fafc;
}
.pec-dim-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pec-dim-name {
  font-size: 24rpx;
  font-weight: 800;
  color: #ffffff;
}
.pec-light .pec-dim-name {
  color: #0f172a;
}
.pec-dim-score {
  font-size: 25rpx;
  font-weight: 900;
  color: #f59e0b;
}
.pec-dim-val {
  display: block;
  font-size: 22rpx;
  color: #cbd5e1;
  margin: 6rpx 0 10rpx;
}
.pec-light .pec-dim-val {
  color: #334155;
}
.pec-bar-bg {
  width: 100%;
  height: 12rpx;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 999rpx;
  overflow: hidden;
  margin-bottom: 10rpx;
}
.pec-light .pec-bar-bg {
  background: #e2e8f0;
}
.pec-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #fc4c02, #f59e0b);
  border-radius: 999rpx;
}
.pec-dim-desc {
  font-size: 20rpx;
  color: #94a3b8;
  line-height: 1.4;
}
.pec-showcase,
.pec-tips-box {
  padding: 20rpx;
  border-radius: 20rpx;
  background: rgba(255, 255, 255, 0.03);
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.pec-light .pec-showcase,
.pec-light .pec-tips-box {
  background: #f8fafc;
}
.pec-showcase-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pec-showcase-title,
.pec-tips-title {
  font-size: 24rpx;
  font-weight: 800;
  color: #ffffff;
}
.pec-light .pec-showcase-title,
.pec-light .pec-tips-title {
  color: #0f172a;
}
.pec-showcase-sigma {
  font-size: 22rpx;
  font-weight: 800;
  color: #10b981;
}
.pec-showcase-meta,
.pec-tip-line {
  font-size: 22rpx;
  color: #cbd5e1;
  line-height: 1.45;
}
.pec-light .pec-showcase-meta,
.pec-light .pec-tip-line {
  color: #475569;
}
.pec-ai-box {
  padding: 22rpx;
  border-radius: 22rpx;
  background: rgba(252, 76, 2, 0.08);
  border: 1rpx solid rgba(252, 76, 2, 0.3);
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.pec-ai-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
}
.pec-ai-title {
  display: block;
  font-size: 25rpx;
  font-weight: 800;
  color: #ffffff;
}
.pec-light .pec-ai-title {
  color: #0f172a;
}
.pec-ai-sub {
  display: block;
  font-size: 20rpx;
  color: #94a3b8;
  margin-top: 4rpx;
}
.pec-ai-btn {
  padding: 12rpx 22rpx;
  border-radius: 16rpx;
  background: #fc4c02;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 800;
  flex-shrink: 0;
}
.pec-ai-content {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}
.pec-ai-strat {
  font-size: 22rpx;
  color: #10b981;
  line-height: 1.45;
}
.pec-ai-plan,
.pec-ai-bio {
  padding: 18rpx;
  border-radius: 16rpx;
  background: rgba(0, 0, 0, 0.25);
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.pec-light .pec-ai-plan,
.pec-light .pec-ai-bio {
  background: #ffffff;
}
.pec-ai-bio-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pec-ai-sec-lbl {
  font-size: 23rpx;
  font-weight: 800;
  color: #fc4c02;
}
.pec-copy-pill {
  font-size: 21rpx;
  font-weight: 700;
  color: #ffffff;
  background: #fc4c02;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
}
.pec-ai-text {
  font-size: 22rpx;
  color: #e2e8f0;
  line-height: 1.55;
  white-space: pre-wrap;
}
.pec-light .pec-ai-text {
  color: #1e293b;
}
.pec-light .pec-chip-label,
.pec-light .pec-matrix-rec,
.pec-light .pec-rec-star,
.pec-light .pec-priv-score,
.pec-light .pec-showcase-sigma,
.pec-light .pec-ai-strat {
  color: #047857;
}
.pec-light .pec-lsd-tip,
.pec-light .pec-dim-score {
  color: #b45309;
}
</style>
