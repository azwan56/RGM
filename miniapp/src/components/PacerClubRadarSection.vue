<template>
  <view class="pcr-card" :class="[themeClass, { 'pcr-light': isVolt }]">
    <view class="pcr-header" @click="toggleExpand">
      <view class="pcr-head-left">
        <text class="pcr-icon">🐰</text>
        <view>
          <view class="pcr-title-row">
            <text class="pcr-title">全团选兔雷达 · 官兔与领跑兔</text>
            <text class="pcr-badge">六维筛选</text>
          </view>
          <text class="pcr-sub">扫描全团硬实力、控速节拍与证书，支持一键指派约跑领跑兔</text>
        </view>
      </view>
      <view class="pcr-toggle-btn">{{ expanded ? "收起 ▴" : "展开 ▾" }}</view>
    </view>

    <view v-if="expanded" class="pcr-body">
      <!-- Mode Tabs -->
      <view class="pcr-mode-tabs">
        <view
          v-for="t in modeTabs"
          :key="t.key"
          class="pcr-mode-tab"
          :class="{ active: distanceType === t.key }"
          @click="switchMode(t.key)"
        >
          {{ t.label }}
        </view>
      </view>

      <!-- Event / Custom LSD Controls -->
      <view v-if="distanceType !== 'custom'" class="pcr-ctrl-box">
        <scroll-view scroll-x class="pcr-h-scroll" show-scrollbar="false">
          <view class="pcr-ev-row">
            <view
              v-for="ev in hotEvents"
              :key="ev"
              class="pcr-ev-chip"
              :class="{ active: eventName === ev }"
              @click="selectEvent(ev)"
            >
              {{ ev }}
            </view>
          </view>
        </scroll-view>
        <view class="pcr-search-row">
          <input
            v-model="customEventQuery"
            class="pcr-input"
            placeholder="输入其他赛事名称检索规程..."
            confirm-type="search"
            @confirm="searchCustomEvent"
          />
          <view class="pcr-mini-btn" @click="searchCustomEvent">校准</view>
        </view>
      </view>

      <view v-else class="pcr-ctrl-box">
        <view class="pcr-custom-row">
          <view class="pcr-col">
            <text class="pcr-lbl">拉练距离(km)</text>
            <input v-model="customDistKm" type="number" class="pcr-input" />
          </view>
          <view class="pcr-col">
            <text class="pcr-lbl">领跑配速(分:秒)</text>
            <input v-model="customPaceStr" class="pcr-input" placeholder="5:00" />
          </view>
          <view class="pcr-mini-btn primary" @click="loadRadar(false)">筛选</view>
        </view>
      </view>

      <!-- Toolbar: Copy Roster -->
      <view v-if="radarData" class="pcr-toolbar">
        <text class="pcr-stat">已评估活跃队员 {{ radarData.total_members_evaluated || 0 }} 人</text>
        <text class="pcr-copy-link" @click="copyRecommendedRoster">📋 复制微信群推荐名单</text>
      </view>

      <view v-if="loading" class="pcr-loading">正在批量计算全团选兔排名...</view>
      <template v-else-if="groupsRanking.length > 0">
        <!-- Group Buckets Strip -->
        <scroll-view v-if="distanceType !== 'custom'" scroll-x class="pcr-h-scroll" show-scrollbar="false">
          <view class="pcr-grp-row">
            <view
              v-for="grp in groupsRanking"
              :key="grp.group_code"
              class="pcr-grp-pill"
              :class="{ active: activeBucket?.group_code === grp.group_code }"
              @click="activeGroupCode = grp.group_code"
            >
              <text class="pcr-grp-name">{{ grp.group_label }}</text>
              <text class="pcr-grp-sub">{{ grp.target_pace_str }} · 适任{{ grp.qualified_count }}人</text>
            </view>
          </view>
        </scroll-view>

        <!-- Candidate Cards -->
        <view v-if="activeBucket?.candidates?.length" class="pcr-cand-list">
          <view
            v-for="(cand, idx) in activeBucket.candidates.slice(0, 10)"
            :key="cand.uid"
            class="pcr-cand-card"
          >
            <view class="pcr-cand-top">
              <view class="pcr-cand-left" @click="inspectStudent(cand)">
                <text class="pcr-rank" :class="{ top: idx < 3 }">#{{ idx + 1 }}</text>
                <view>
                  <view class="pcr-name-row">
                    <text class="pcr-cand-name">{{ cand.display_name }} ↗</text>
                    <text v-if="cand.first_aid_cert_label" class="pcr-fa-tag">🚑急救</text>
                  </view>
                  <text class="pcr-cand-meta">
                    当期 {{ cand.pred_finish_str }} · 证书 {{ cand.cert_finish_str }}
                    {{ cand.sigma_avg_sec != null ? ` · ±${cand.sigma_avg_sec}s` : "" }}
                  </text>
                </view>
              </view>
              <view class="pcr-cand-right">
                <text class="pcr-cand-score" :style="{ color: adaptTone(cand.verdict_color) }">
                  {{ cand.overall_score }}分
                </text>
                <text class="pcr-cand-grade">{{ cand.grade }}级</text>
              </view>
            </view>

            <view class="pcr-cand-btm">
              <view class="pcr-verdict-wrap">
                <text class="pcr-verdict" :style="{ color: adaptTone(cand.verdict_color) }">
                  {{ cand.verdict_label }}
                </text>
                <text v-if="cand.cert_gate_status === 'missing_cert'" class="pcr-priv-txt">
                  (私兔{{ cand.private_pacer_score }}分)
                </text>
              </view>
              <view class="pcr-assign-btn" @click="openAssignModal(cand)">
                🐰 指派领跑兔
              </view>
            </view>
          </view>
        </view>
      </template>
    </view>

    <!-- Assign Event Pacer Modal -->
    <view v-if="assignCand" class="pcr-modal-mask" @click="assignCand = null" @touchmove.stop.prevent>
      <view class="pcr-modal" @click.stop>
        <text class="pcr-modal-title">🐰 指派【{{ assignCand.display_name }}】担任领跑兔</text>

        <view v-if="assignableEvents.length === 0" class="pcr-empty-tip">
          当前跑团暂无进行中的约跑/拉练活动。请先在「约跑」页签发起一场周末活动，即可一键指派领跑兔并下发站内邀请通知。
        </view>
        <template v-else>
          <view class="pcr-field">
            <text class="pcr-lbl">选择跑团约跑活动</text>
            <picker
              mode="selector"
              :range="eventPickerLabels"
              :value="selectedEventIdx"
              @change="onEventPickerChange"
            >
              <view class="pcr-picker-box">
                {{ eventPickerLabels[selectedEventIdx] || "请选择活动" }} ▾
              </view>
            </picker>
          </view>

          <view class="pcr-field">
            <text class="pcr-lbl">领跑配速组别</text>
            <input v-model="assignPaceGroup" class="pcr-input" placeholder="如：5:00/km 稳态领跑组" />
          </view>

          <view class="pcr-field">
            <text class="pcr-lbl">受邀寄语</text>
            <input v-model="assignNote" class="pcr-input" />
          </view>

          <view class="pcr-modal-actions">
            <view class="pcr-m-btn ghost" @click="assignCand = null">取消</view>
            <view class="pcr-m-btn primary" @click="confirmAssign">
              {{ assigning ? "提交中..." : "确认指派并通知" }}
            </view>
          </view>
        </template>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { request } from "../utils/api";
import { isVolt, themeClass } from "../utils/theme";

const props = defineProps<{
  clubId: string;
  operatorUid: string;
  clubName?: string;
}>();

const modeTabs = [
  { key: "fm", label: "全马官兔" },
  { key: "hm", label: "半马官兔" },
  { key: "10k", label: "10K官兔" },
  { key: "custom", label: "内部拉练兔" },
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

const expanded = ref<boolean>(false);
const distanceType = ref<"fm" | "hm" | "10k" | "custom">("fm");
const eventName = ref<string>("上海马拉松");
const customEventQuery = ref<string>("");
const customDistKm = ref<string>("30");
const customPaceStr = ref<string>("5:00");

const radarData = ref<any>(null);
const activeGroupCode = ref<string>("330");
const loading = ref<boolean>(false);

// Assign modal
const assignCand = ref<any>(null);
const selectedEventIdx = ref<number>(0);
const assignPaceGroup = ref<string>("");
const assignNote = ref<string>("");
const assigning = ref<boolean>(false);

const groupsRanking = computed(() => radarData.value?.groups_ranking || []);
const activeBucket = computed(
  () => groupsRanking.value.find((g: any) => g.group_code === activeGroupCode.value) || groupsRanking.value[0] || null
);
const assignableEvents = computed(() => radarData.value?.assignable_events || []);
const eventPickerLabels = computed(() =>
  assignableEvents.value.map(
    (ev: any) => `${ev.title} (${String(ev.meet_time || ev.start_date || "").slice(0, 10)})`
  )
);

function toggleExpand() {
  expanded.value = !expanded.value;
  if (expanded.value && !radarData.value) {
    loadRadar(false);
  }
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

async function loadRadar(allowWeb = false) {
  if (!props.clubId || !props.operatorUid) return;
  loading.value = true;
  try {
    const qs: string[] = [
      `operator_uid=${encodeURIComponent(props.operatorUid)}`,
      `distance_type=${encodeURIComponent(distanceType.value)}`,
      `allow_web_search=${allowWeb ? "true" : "false"}`,
    ];
    if (distanceType.value !== "custom" && eventName.value) {
      qs.push(`event_name=${encodeURIComponent(eventName.value)}`);
    }
    if (distanceType.value === "custom") {
      qs.push(`custom_distance_km=${encodeURIComponent(customDistKm.value || "30")}`);
      qs.push(`custom_target_pace=${encodeURIComponent(customPaceStr.value || "5:00")}`);
    }
    const res: any = await request(
      `/api/team/${encodeURIComponent(props.clubId)}/pacer-radar?${qs.join("&")}`
    );
    if (res) {
      radarData.value = res;
      const grps = res.groups_ranking || [];
      if (grps.length > 0 && !grps.some((g: any) => g.group_code === activeGroupCode.value)) {
        const q = grps.find((g: any) => g.qualified_count > 0) || grps[0];
        activeGroupCode.value = q.group_code;
      }
    }
  } catch (e) {
    console.error("MiniApp pacer radar failed:", e);
  } finally {
    loading.value = false;
  }
}

function switchMode(m: "fm" | "hm" | "10k" | "custom") {
  distanceType.value = m;
  loadRadar(false);
}

function selectEvent(ev: string) {
  eventName.value = ev;
  loadRadar(false);
}

function searchCustomEvent() {
  const q = customEventQuery.value.trim();
  if (!q) return;
  eventName.value = q;
  loadRadar(true);
}

function inspectStudent(cand: any) {
  uni.navigateTo({
    url: `/pages/analysis/analysis?student_user_id=${encodeURIComponent(cand.uid)}&student_name=${encodeURIComponent(
      cand.display_name || "队员"
    )}`,
  });
}

function copyRecommendedRoster() {
  if (!radarData.value) return;
  const evTitle = radarData.value.event_calibration?.event_name || eventName.value;
  const lines: string[] = [`🐰【${props.clubName || "跑团"} · ${evTitle} 推荐领跑兔名单】`];
  for (const grp of groupsRanking.value) {
    const cands = (grp.candidates || [])
      .filter((c: any) => c.overall_score >= 68 || c.private_pacer_score >= 75)
      .slice(0, 3);
    if (!cands.length) continue;
    const names = cands
      .map(
        (c: any) =>
          `${c.display_name}(${c.overall_score}分${
            c.cert_gate_status === "missing_cert" ? `·私兔${c.private_pacer_score}分` : ""
          })`
      )
      .join("、");
    lines.push(`• ${grp.group_label} (${grp.target_pace_str})：${names}`);
  }
  if (lines.length === 1) {
    lines.push("当前组别暂无 ≥68 分候选人，可切换低一档配速组或拉练模式查看。");
  }
  uni.setClipboardData({
    data: lines.join("\n"),
    success: () => {
      uni.showToast({ title: "推荐名单已复制", icon: "success" });
    },
  });
}

function openAssignModal(cand: any) {
  assignCand.value = cand;
  selectedEventIdx.value = 0;
  assignPaceGroup.value = activeBucket.value
    ? `${activeBucket.value.group_label} (${activeBucket.value.target_pace_str})`
    : "5:00/km 领跑组";
  assignNote.value = `经跑团选兔雷达评估（胜任度 ${cand.overall_score} 分），特邀担任本场活动领跑兔！`;
}

function onEventPickerChange(e: any) {
  selectedEventIdx.value = Number(e.detail?.value || 0);
}

async function confirmAssign() {
  const ev = assignableEvents.value[selectedEventIdx.value];
  if (!ev || !assignCand.value || assigning.value) return;
  assigning.value = true;
  try {
    const res: any = await request(
      `/api/team/${encodeURIComponent(props.clubId)}/events/${encodeURIComponent(ev.id)}/assign-pacer`,
      "POST",
      {
        operator_uid: props.operatorUid,
        target_uid: assignCand.value.uid,
        pace_group: assignPaceGroup.value,
        note: assignNote.value,
      }
    );
    if (res?.success) {
      uni.showToast({ title: "已指派并通知队员", icon: "success" });
      assignCand.value = null;
    }
  } catch (e: any) {
    uni.showToast({ title: "指派失败，请重试", icon: "none" });
  } finally {
    assigning.value = false;
  }
}

watch(
  () => props.clubId,
  () => {
    if (expanded.value) loadRadar(false);
    else radarData.value = null;
  }
);
</script>

<style scoped>
.pcr-card {
  min-height: auto;
  box-sizing: border-box;
  margin: 20rpx 0;
  padding: 24rpx;
  border-radius: 28rpx;
  background: linear-gradient(145deg, #18151f, #121319);
  border: 1rpx solid rgba(252, 76, 2, 0.38);
}
.pcr-light.pcr-card {
  background: #ffffff;
  border-color: rgba(252, 76, 2, 0.3);
  box-shadow: 0 8rpx 24rpx rgba(15, 23, 42, 0.05);
}
.pcr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}
.pcr-head-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
}
.pcr-icon {
  font-size: 40rpx;
}
.pcr-title-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-wrap: wrap;
}
.pcr-title {
  font-size: 28rpx;
  font-weight: 800;
  color: #ffffff;
}
.pcr-light .pcr-title {
  color: #0f172a;
}
.pcr-badge {
  font-size: 19rpx;
  font-weight: 700;
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(252, 76, 2, 0.16);
  color: #fc4c02;
}
.pcr-sub {
  display: block;
  font-size: 21rpx;
  color: #94a3b8;
  margin-top: 4rpx;
}
.pcr-toggle-btn {
  padding: 10rpx 20rpx;
  border-radius: 999rpx;
  background: #fc4c02;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 800;
  flex-shrink: 0;
}
.pcr-body {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}
.pcr-mode-tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10rpx;
}
.pcr-mode-tab {
  text-align: center;
  padding: 12rpx 4rpx;
  border-radius: 16rpx;
  font-size: 22rpx;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.05);
  color: #cbd5e1;
}
.pcr-light .pcr-mode-tab {
  background: #f1f5f9;
  color: #334155;
}
.pcr-mode-tab.active {
  background: #fc4c02;
  color: #ffffff;
}
.pcr-ctrl-box {
  background: rgba(255, 255, 255, 0.03);
  padding: 18rpx;
  border-radius: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}
.pcr-light .pcr-ctrl-box {
  background: #f8fafc;
}
.pcr-h-scroll {
  width: 100%;
  white-space: nowrap;
}
.pcr-ev-row,
.pcr-grp-row {
  display: inline-flex;
  gap: 12rpx;
}
.pcr-ev-chip {
  padding: 8rpx 18rpx;
  border-radius: 12rpx;
  font-size: 22rpx;
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
}
.pcr-light .pcr-ev-chip {
  background: #e2e8f0;
  color: #475569;
}
.pcr-ev-chip.active {
  background: rgba(252, 76, 2, 0.2);
  color: #fc4c02;
  font-weight: 700;
}
.pcr-search-row,
.pcr-custom-row {
  display: flex;
  align-items: flex-end;
  gap: 12rpx;
}
.pcr-col {
  flex: 1;
}
.pcr-lbl {
  display: block;
  font-size: 20rpx;
  color: #94a3b8;
  margin-bottom: 6rpx;
}
.pcr-input {
  flex: 1;
  height: 62rpx;
  background: rgba(0, 0, 0, 0.28);
  border-radius: 14rpx;
  padding: 0 18rpx;
  font-size: 23rpx;
  color: #ffffff;
}
.pcr-light .pcr-input {
  background: #ffffff;
  color: #0f172a;
  border: 1rpx solid #cbd5e1;
}
.pcr-mini-btn {
  height: 62rpx;
  line-height: 62rpx;
  padding: 0 24rpx;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
  font-size: 23rpx;
  font-weight: 700;
}
.pcr-light .pcr-mini-btn {
  background: #0f172a;
  color: #ffffff;
}
.pcr-mini-btn.primary,
.pcr-light .pcr-mini-btn.primary {
  background: #fc4c02;
  color: #ffffff;
}
.pcr-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 22rpx;
}
.pcr-stat {
  color: #94a3b8;
}
.pcr-copy-link {
  color: #fc4c02;
  font-weight: 700;
}
.pcr-loading {
  padding: 40rpx 0;
  text-align: center;
  font-size: 24rpx;
  color: #94a3b8;
}
.pcr-grp-pill {
  padding: 14rpx 20rpx;
  border-radius: 18rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.pcr-light .pcr-grp-pill {
  background: #f8fafc;
  border-color: #e2e8f0;
}
.pcr-grp-pill.active {
  border-color: #fc4c02;
  background: rgba(252, 76, 2, 0.15);
}
.pcr-grp-name {
  font-size: 24rpx;
  font-weight: 800;
  color: #ffffff;
}
.pcr-light .pcr-grp-name {
  color: #0f172a;
}
.pcr-grp-sub {
  font-size: 20rpx;
  color: #94a3b8;
}
.pcr-cand-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}
.pcr-cand-card {
  padding: 20rpx;
  border-radius: 20rpx;
  background: rgba(255, 255, 255, 0.04);
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}
.pcr-light .pcr-cand-card {
  background: #f8fafc;
}
.pcr-cand-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pcr-cand-left {
  display: flex;
  align-items: center;
  gap: 14rpx;
  flex: 1;
}
.pcr-rank {
  width: 48rpx;
  height: 48rpx;
  line-height: 48rpx;
  text-align: center;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.08);
  font-size: 22rpx;
  font-weight: 800;
  color: #cbd5e1;
}
.pcr-light .pcr-rank {
  background: #e2e8f0;
  color: #334155;
}
.pcr-rank.top,
.pcr-light .pcr-rank.top {
  background: #f59e0b;
  color: #000000;
}
.pcr-name-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.pcr-cand-name {
  font-size: 26rpx;
  font-weight: 800;
  color: #ffffff;
}
.pcr-light .pcr-cand-name {
  color: #0f172a;
}
.pcr-fa-tag {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(244, 63, 94, 0.16);
  color: #fb7185;
}
.pcr-cand-meta {
  display: block;
  font-size: 20rpx;
  color: #94a3b8;
  margin-top: 4rpx;
}
.pcr-cand-right {
  text-align: right;
}
.pcr-cand-score {
  display: block;
  font-size: 30rpx;
  font-weight: 900;
}
.pcr-cand-grade {
  font-size: 20rpx;
  color: #94a3b8;
}
.pcr-cand-btm {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
}
.pcr-verdict {
  font-size: 21rpx;
  font-weight: 700;
}
.pcr-priv-txt {
  font-size: 20rpx;
  color: #10b981;
  margin-left: 6rpx;
}
.pcr-light .pcr-priv-txt {
  color: #047857;
}
.pcr-light .pcr-fa-tag {
  color: #be123c;
}
.pcr-light .pcr-body,
.pcr-light .pcr-cand-btm {
  border-top-color: #e2e8f0;
}
.pcr-light .pcr-empty-tip {
  color: #b45309;
}
.pcr-light .pcr-m-btn.ghost {
  background: #f1f5f9;
  color: #334155;
}
.pcr-assign-btn {
  padding: 8rpx 20rpx;
  border-radius: 14rpx;
  background: rgba(252, 76, 2, 0.18);
  color: #fc4c02;
  font-size: 22rpx;
  font-weight: 800;
}
.pcr-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 36rpx;
}
.pcr-modal {
  width: 100%;
  background: #161822;
  border-radius: 28rpx;
  padding: 32rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.pcr-light .pcr-modal {
  background: #ffffff;
}
.pcr-modal-title {
  font-size: 28rpx;
  font-weight: 800;
  color: #ffffff;
}
.pcr-light .pcr-modal-title {
  color: #0f172a;
}
.pcr-empty-tip {
  font-size: 24rpx;
  color: #f59e0b;
  line-height: 1.5;
}
.pcr-field {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.pcr-picker-box {
  height: 68rpx;
  line-height: 68rpx;
  padding: 0 20rpx;
  border-radius: 14rpx;
  background: rgba(0, 0, 0, 0.3);
  color: #ffffff;
  font-size: 24rpx;
}
.pcr-light .pcr-picker-box {
  background: #f1f5f9;
  color: #0f172a;
}
.pcr-modal-actions {
  display: flex;
  gap: 18rpx;
  margin-top: 8rpx;
}
.pcr-m-btn {
  flex: 1;
  height: 76rpx;
  line-height: 76rpx;
  text-align: center;
  border-radius: 18rpx;
  font-size: 25rpx;
  font-weight: 800;
}
.pcr-m-btn.ghost {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}
.pcr-m-btn.primary {
  background: #fc4c02;
  color: #ffffff;
}
</style>
