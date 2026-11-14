<template>
  <view class="activities-page" :class="themeClass">
    <view class="page-header">
      <text class="title">跑步记录与教练点评</text>
    </view>

    <!-- Activity list -->
    <view v-if="activities.length" class="list-box">
      <view
        v-for="act in activities"
        :key="act.id"
        class="activity-card"
        :class="{ 'is-excluded-card': act.exclude_mode === 'excluded' }"
        @click="openDetail(act)"
      >
        <view class="card-top">
          <view class="card-name-wrap">
            <text class="act-name">{{ act.name }}</text>
            <text v-if="act.workout_effective_vdot && (!act.exclude_mode || act.exclude_mode === 'normal')" class="vdot-eff-pill">
              ⚡ 等效VDOT {{ act.workout_effective_vdot }}
            </text>
            <text v-else-if="act.exclude_mode === 'ignore_vdot'" class="mode-status-pill warn">
              🤝 陪跑不计VDOT
            </text>
            <text v-else-if="act.exclude_mode === 'excluded'" class="mode-status-pill muted">
              🚫 已忽略重复/异常
            </text>
          </view>
          <text class="act-date">{{ formatDateTime(act.start_time) }}</text>
        </view>

        <view class="stats-row">
          <view class="stat">
            <text class="num primary">{{ act.distance_km || (act.distance_meters ? (act.distance_meters / 1000).toFixed(2) : '0.00') }}</text>
            <text class="sub">公里</text>
          </view>
          <view class="stat">
            <text class="num">{{ act.avg_pace_str || '—' }}</text>
            <text class="sub">配速</text>
          </view>
          <view class="stat">
            <text class="num">{{ formatDuration(act.moving_time_seconds) }}</text>
            <text class="sub">时长</text>
          </view>
          <view class="stat">
            <text class="num">{{ act.average_heartrate || '—' }}</text>
            <text class="sub">心率</text>
          </view>
        </view>

        <!-- GPS Track, Moments Share Card & Exclude Mode Pills -->
        <view class="track-badge-row">
          <text
            v-if="act.has_gps_track || act.map_image_url || act.id?.startsWith('garmin_') || act.id?.startsWith('coros_')"
            class="track-pill"
          >
            🗺️ 轨迹与分段复盘 ›
          </text>
          <text
            class="share-card-pill"
            @click.stop="openPersonalShareCard(act.id)"
          >
            📸 朋友圈分享卡
          </text>
          <text
            class="exclude-mode-pill"
            @click.stop="openExcludeModeMenu(act)"
          >
            ⚙️ {{ getExcludeModeShortLabel(act.exclude_mode) }}
          </text>
        </view>

        <!-- Coach Journal preview tag if available -->
        <view v-if="act.ai_journal?.evaluation || (typeof act.ai_journal === 'string' && act.ai_journal)" class="journal-preview">
          <view class="journal-tag-box">
            <text class="journal-tag">教练点评</text>
            <text class="journal-compliance">仅供参考</text>
          </view>
          <text class="journal-text">{{ act.ai_journal?.evaluation || act.ai_journal }}</text>
        </view>

        <!-- Public Club Captain Cheer -->
        <view v-if="act.captain_cheer" class="journal-preview captain-journal-preview">
          <view class="journal-tag-box">
            <text class="journal-tag captain-journal-tag">📣 {{ act.captain_cheer_meta?.captain_title || "团长加油" }}</text>
            <text class="journal-compliance">全员可见</text>
          </view>
          <text class="journal-text">{{ act.captain_cheer }}</text>
        </view>
      </view>
    </view>

    <view v-else-if="loading" class="empty-state">
      <text class="empty-text">正在加载跑步记录…</text>
    </view>

    <view v-else-if="loadError" class="empty-state">
      <text class="empty-text">加载失败，请检查网络后重试</text>
      <button class="rgm-empty-cta" @click="loadActivities">重新加载</button>
    </view>

    <view v-else class="empty-state">
      <text class="empty-text">还没有跑步记录</text>
      <button class="rgm-empty-cta" @click="goBindWatch">去绑定手表</button>
    </view>

    <!-- GPS Track & Canova Evaluation Modal -->
    <GpsTrackModal
      :visible="Boolean(selectedActivity)"
      :activity-id="selectedActivity?.id"
      :initial-activity="selectedActivity"
      @close="selectedActivity = null"
      @share-card="handleShareCardFromTrack"
    />

    <!-- Personal Moments Share Card Modal -->
    <PersonalShareCardModal
      :visible="showPersonalShareModal"
      :activity-id="shareCardActivityId"
      @close="showPersonalShareModal = false"
    />
  </view>

</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import { ref } from "vue";
import { onShow, onPullDownRefresh, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import { request, getStoredUser } from "../../utils/api";
import GpsTrackModal from "../../components/GpsTrackModal.vue";
import PersonalShareCardModal from "../../components/PersonalShareCardModal.vue";
import { trackClick } from "../../utils/telemetry";

const activities = ref<any[]>([]);
const selectedActivity = ref<any>(null);
const showPersonalShareModal = ref(false);
const shareCardActivityId = ref<string>("");
const loading = ref(false);
const loadError = ref(false);

function openPersonalShareCard(actId?: string) {
  shareCardActivityId.value = actId || "";
  showPersonalShareModal.value = true;
}

function handleShareCardFromTrack(actId?: string) {
  selectedActivity.value = null;
  openPersonalShareCard(actId);
}

async function loadActivities() {
  const user = getStoredUser();
  const uid = user?.id;
  // 未登录时不要回退到 "u_default"，否则可能展示无关数据
  if (!uid) {
    activities.value = [];
    return;
  }

  loading.value = activities.value.length === 0;
  loadError.value = false;
  try {
    const data = await request(`/api/miniapp/activities/${uid}`);
    if (data?.activities && Array.isArray(data.activities)) {
      activities.value = data.activities;
    } else {
      const dash = await request(`/api/miniapp/dashboard/${uid}`);
      activities.value = dash.recent_activities || [];
    }
  } catch (e) {
    console.error("Load activities error:", e);
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}

function goBindWatch() {
  uni.switchTab({ url: "/pages/profile/profile" });
}

function openDetail(act: any) {
  selectedActivity.value = act;
}

function getExcludeModeShortLabel(mode?: string): string {
  if (mode === "ignore_vdot") return "陪跑不计VDOT";
  if (mode === "excluded") return "已忽略记录";
  return "统计设定";
}

function openExcludeModeMenu(act: any) {
  const user = getStoredUser();
  if (!user?.id || !act?.id) return;
  const itemList = [
    "✅ 正常计入跑量与有效VDOT",
    "🤝 陪跑/慢摇（计跑量，不拉低有效VDOT）",
    "🚫 忽略此记录（多表重复或异常，不计跑量）"
  ];
  const modeValues = ["normal", "ignore_vdot", "excluded"];
  uni.showActionSheet({
    itemList,
    success: async (res) => {
      const nextMode = modeValues[res.tapIndex];
      if (!nextMode) return;
      try {
        const resp = await request(`/api/science/activities/${act.id}/exclude-mode`, "POST", {
          uid: user.id,
          exclude_mode: nextMode
        });
        if (resp?.success) {
          act.exclude_mode = nextMode;
          if (nextMode !== "normal") {
            act.workout_effective_vdot = null;
          }
          trackClick("activity_change_exclude_mode", `修改跑步记录统计模式：${nextMode}`, {
            activity_id: act.id,
            exclude_mode: nextMode,
          });
          uni.showToast({ title: resp.message || "已更新统计状态", icon: "none" });
          loadActivities();
        } else {
          uni.showToast({ title: resp?.error || "操作失败", icon: "none" });
        }
      } catch (e: any) {
        uni.showToast({ title: e?.message || "网络异常", icon: "none" });
      }
    }
  });
}

function formatDateTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function formatDuration(sec: number): string {
  if (!sec) return "0:00";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return `${h}:${String(remM).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

onShow(() => {
  applySystemTheme(currentTheme.value);
  loadActivities();
});

onPullDownRefresh(async () => {
  await loadActivities();
  uni.stopPullDownRefresh();
});

onLoad(() => {
  initShareMenu();
});

onShareAppMessage(() => {
  return getUnifiedShareAppMessage();
});

onShareTimeline(() => {
  return getUnifiedShareTimeline();
});
</script>

<style scoped>
.activities-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  padding: 24rpx 28rpx calc(48rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.page-header {
  margin-bottom: 20rpx;
}

.title {
  font-size: 36rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.list-box {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.activity-card {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.22));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.activity-card.is-excluded-card {
  opacity: 0.62;
  border-style: dashed;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.card-name-wrap {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
}

.act-name {
  font-size: 30rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.vdot-eff-pill {
  font-size: 20rpx;
  font-weight: 800;
  color: #f97316;
  background-color: rgba(249, 115, 22, 0.14);
  border: 1rpx solid rgba(249, 115, 22, 0.32);
  padding: 2rpx 12rpx;
  border-radius: 10rpx;
  font-family: monospace;
}

.mode-status-pill {
  font-size: 18rpx;
  font-weight: 700;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.mode-status-pill.warn {
  color: #eab308;
  background-color: rgba(234, 179, 8, 0.15);
}

.mode-status-pill.muted {
  color: #a1a1aa;
  background-color: rgba(161, 161, 170, 0.15);
}

.act-date {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.stats-row {
  display: flex;
  justify-content: space-between;
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 20rpx 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.num {
  font-size: 30rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.num.primary {
  color: var(--rgm-brand-text, #fc4c02);
}

.sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
}

.journal-preview {
  margin-top: 20rpx;
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.05));
  border-radius: 16rpx;
  padding: 16rpx;
  display: flex;
  gap: 12rpx;
}

.journal-tag-box {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4rpx;
  flex-shrink: 0;
}

.journal-tag {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  white-space: nowrap;
}

.journal-compliance {
  font-size: 16rpx;
  color: var(--rgm-text-3, #71717a);
  white-space: nowrap;
}

.journal-text {
  font-size: 22rpx;
  color: var(--rgm-text, #e5e5ea);
  line-height: 1.4;
}

.captain-journal-preview {
  flex-direction: column;
  gap: 6rpx;
  background-color: rgba(245, 158, 11, 0.08);
  border: 1rpx solid rgba(245, 158, 11, 0.22);
}

.captain-journal-preview .journal-tag-box {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.captain-journal-tag {
  color: #f59e0b;
  white-space: normal;
}

.empty-state {
  margin-top: 100rpx;
  text-align: center;
}

.empty-text {
  font-size: 26rpx;
  color: var(--rgm-text-3, #636366);
}

/* Modal */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.modal-content {
  width: 640rpx;
  background-color: var(--rgm-card-2, #1c1c1e);
  border-radius: 32rpx;
  padding: 36rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.modal-title {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.close-btn {
  font-size: 36rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.act-modal-name {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  display: block;
}

.act-modal-date {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 6rpx;
  margin-bottom: 20rpx;
  display: block;
}

.track-badge-row {
  margin-top: 14rpx;
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.track-pill {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #FC4C02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  border: 1px solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  font-weight: 600;
}

.share-card-pill {
  font-size: 22rpx;
  color: #38bdf8;
  background-color: rgba(56, 189, 248, 0.12);
  border: 1px solid rgba(56, 189, 248, 0.35);
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  font-weight: 700;
}

.exclude-mode-pill {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d4d4d8);
  background-color: var(--rgm-card-2, rgba(255, 255, 255, 0.06));
  border: 1px solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  font-weight: 600;
}

.ai-box {
  background-color: var(--rgm-card, #121214);
  border-radius: 20rpx;
  padding: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.ai-desc {
  font-size: 26rpx;
  color: var(--rgm-text, #e5e5ea);
  line-height: 1.6;
}
</style>
