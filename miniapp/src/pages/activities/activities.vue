<template>
  <view class="activities-page">
    <view class="page-header">
      <text class="title">跑步记录与 AI 点评</text>
    </view>

    <!-- Activity list -->
    <view v-if="activities.length" class="list-box">
      <view v-for="act in activities" :key="act.id" class="activity-card" @click="openDetail(act)">
        <view class="card-top">
          <text class="act-name">{{ act.name }}</text>
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

        <!-- AI Journal preview tag if available -->
        <view v-if="act.ai_journal?.evaluation" class="journal-preview">
          <text class="journal-tag">AI 点评</text>
          <text class="journal-text">{{ act.ai_journal.evaluation }}</text>
        </view>
      </view>
    </view>

    <view v-else class="empty-state">
      <text class="empty-text">暂无运动记录，请前往首页点击同步 Garmin 数据。</text>
    </view>

    <!-- AI Evaluation Modal -->
    <view v-if="activeModal" class="modal-mask" @click="activeModal = null">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">Canova AI 教练单次点评</text>
          <text class="close-btn" @click="activeModal = null">✕</text>
        </view>
        <view class="modal-body">
          <text class="act-modal-name">{{ activeModal.name }} ({{ activeModal.distance_km || (activeModal.distance_meters ? (activeModal.distance_meters / 1000).toFixed(2) : '0') }} km)</text>
          <text class="act-modal-date">{{ formatDateTime(activeModal.start_time) }}</text>

          <view class="ai-box">
            <text class="ai-desc">
              {{ activeModal.ai_journal?.evaluation || "本次训练配速与心率控制平稳，符合 Renato Canova 有氧基础期训练负荷。" }}
            </text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import { request, getStoredUser } from "../../utils/api";

const activities = ref<any[]>([]);
const activeModal = ref<any>(null);

async function loadActivities() {
  const user = getStoredUser();
  const uid = user?.id || "u_default";

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
  }
}

function openDetail(act: any) {
  activeModal.value = act;
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
  loadActivities();
});

onPullDownRefresh(async () => {
  await loadActivities();
  uni.stopPullDownRefresh();
});
</script>

<style scoped>
.activities-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx;
  box-sizing: border-box;
}

.page-header {
  margin-bottom: 30rpx;
}

.title {
  font-size: 36rpx;
  font-weight: 900;
  color: #ffffff;
}

.list-box {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.activity-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 28rpx;
  padding: 28rpx;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.act-name {
  font-size: 30rpx;
  font-weight: bold;
  color: #ffffff;
}

.act-date {
  font-size: 22rpx;
  color: #8e8e93;
}

.stats-row {
  display: flex;
  justify-content: space-between;
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 20rpx 16rpx;
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
  color: #ffffff;
}

.num.primary {
  color: #fc4c02;
}

.sub {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
}

.journal-preview {
  margin-top: 20rpx;
  background-color: rgba(252, 76, 2, 0.05);
  border-radius: 16rpx;
  padding: 16rpx;
  display: flex;
  gap: 12rpx;
}

.journal-tag {
  font-size: 20rpx;
  font-weight: bold;
  color: #fc4c02;
  white-space: nowrap;
}

.journal-text {
  font-size: 22rpx;
  color: #e5e5ea;
  line-height: 1.4;
}

.empty-state {
  margin-top: 100rpx;
  text-align: center;
}

.empty-text {
  font-size: 26rpx;
  color: #636366;
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
}

.modal-content {
  width: 640rpx;
  background-color: #1c1c1e;
  border-radius: 32rpx;
  padding: 36rpx;
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
  color: #ffffff;
}

.close-btn {
  font-size: 36rpx;
  color: #8e8e93;
}

.act-modal-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #fc4c02;
  display: block;
}

.act-modal-date {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 6rpx;
  margin-bottom: 20rpx;
  display: block;
}

.ai-box {
  background-color: #121214;
  border-radius: 20rpx;
  padding: 24rpx;
}

.ai-desc {
  font-size: 26rpx;
  color: #e5e5ea;
  line-height: 1.6;
}
</style>
