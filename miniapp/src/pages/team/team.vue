<template>
  <view class="team-page">
    <view class="page-header">
      <view class="header-text">
        <text class="title">跑团与排行榜</text>
        <text class="subtitle">与队友同行，用数据见证每一步进化</text>
      </view>
      <view class="actions">
        <button class="join-btn" @click="showJoinModal = true">+ 加入团队</button>
      </view>
    </view>

    <!-- Leaderboard Card -->
    <view class="leaderboard-card">
      <view class="lb-header">
        <text class="lb-title">本月跑团排行榜</text>
        <text class="lb-sort">按目标完成率排序</text>
      </view>

      <view v-if="leaderboard.length" class="lb-list">
        <view
          v-for="item in leaderboard"
          :key="item.user_id"
          class="lb-row"
          :class="{ 'top-three': item.rank <= 3 }"
        >
          <!-- Rank Badge -->
          <view class="rank-col">
            <text class="rank-num" :class="'rank-' + item.rank">{{ item.rank }}</text>
          </view>

          <!-- User Info -->
          <view class="user-col">
            <image class="avatar" :src="item.avatar_url || '/static/default_avatar.png'" mode="aspectFill" />
            <view class="name-box">
              <text class="name">{{ item.display_name }}</text>
              <text class="dist-target">{{ item.distance_km }}km / 目标 {{ item.target_km }}km</text>
            </view>
          </view>

          <!-- Progress -->
          <view class="pct-col">
            <text class="pct-val">{{ item.progress_pct }}%</text>
            <view class="mini-bar">
              <view class="mini-fill" :style="{ width: Math.min(100, item.progress_pct) + '%' }" />
            </view>
          </view>
        </view>
      </view>

      <view v-else class="empty-box">
        <text class="empty-text">暂无排行榜数据</text>
      </view>
    </view>

    <!-- Join Team Modal -->
    <view v-if="showJoinModal" class="modal-mask" @click="showJoinModal = false">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">加入跑团</text>
          <text class="close-btn" @click="showJoinModal = false">✕</text>
        </view>

        <view class="modal-body">
          <text class="input-hint">请输入跑友分享的 6 位团队专属邀请码：</text>
          <input
            class="code-input"
            type="text"
            maxlength="6"
            placeholder="例如: RGM888"
            v-model="inviteCode"
          />

          <button class="submit-btn" :loading="joining" @click="handleJoinTeam">立即加入</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { onPullDownRefresh } from "@dcloudio/uni-app";
import { request, getStoredUser } from "../../utils/api";

const leaderboard = ref<any[]>([]);
const showJoinModal = ref(false);
const inviteCode = ref("");
const joining = ref(false);

async function loadLeaderboard() {
  try {
    const data = await request("/api/team/leaderboard");
    leaderboard.value = data || [];
  } catch (e) {
    console.error("Load leaderboard error:", e);
  }
}

async function handleJoinTeam() {
  if (!inviteCode.value.trim()) {
    uni.showToast({ title: "请输入邀请码", icon: "none" });
    return;
  }

  const user = getStoredUser();
  if (!user) return;

  joining.value = true;
  try {
    await request("/api/team/join", "POST", {
      invite_code: inviteCode.value.trim(),
      user_id: user.id,
    });
    uni.showToast({ title: "加入成功！", icon: "success" });
    showJoinModal.value = false;
    inviteCode.value = "";
    loadLeaderboard();
  } catch (e) {
    // Handled by api client
  } finally {
    joining.value = false;
  }
}

onPullDownRefresh(async () => {
  await loadLeaderboard();
  uni.stopPullDownRefresh();
});

onMounted(() => {
  loadLeaderboard();
});
</script>

<style scoped>
.team-page {
  padding: 32rpx;
  background-color: #0a0a0a;
  min-height: 100vh;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
  margin-top: 4rpx;
  display: block;
}
.join-btn {
  background-color: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 16rpx;
  height: 64rpx;
  line-height: 64rpx;
  padding: 0 24rpx;
}

.leaderboard-card {
  background-color: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 28rpx;
}
.lb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}
.lb-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #ffffff;
}
.lb-sort {
  font-size: 22rpx;
  color: #71717a;
}

.lb-row {
  display: flex;
  align-items: center;
  padding: 20rpx 0;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.05);
}
.rank-col {
  width: 50rpx;
  text-align: center;
}
.rank-num {
  font-size: 30rpx;
  font-weight: 800;
  color: #71717a;
}
.rank-1 { color: #f59e0b; }
.rank-2 { color: #94a3b8; }
.rank-3 { color: #d97706; }

.user-col {
  flex: 1;
  display: flex;
  align-items: center;
  margin-left: 20rpx;
}
.avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background-color: #27272a;
  margin-right: 16rpx;
}
.name-box {
  display: flex;
  flex-direction: column;
}
.name {
  font-size: 26rpx;
  font-weight: 600;
  color: #ffffff;
}
.dist-target {
  font-size: 20rpx;
  color: #71717a;
  margin-top: 4rpx;
}

.pct-col {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  width: 140rpx;
}
.pct-val {
  font-size: 32rpx;
  font-weight: 800;
  color: #FC4C02;
  margin-bottom: 6rpx;
}
.mini-bar {
  width: 100%;
  height: 8rpx;
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 4rpx;
  overflow: hidden;
}
.mini-fill {
  height: 100%;
  background: linear-gradient(90deg, #FC4C02, #f97316);
}

.empty-box {
  padding: 80rpx 0;
  text-align: center;
}
.empty-text {
  font-size: 26rpx;
  color: #71717a;
}

/* Modal */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40rpx;
  z-index: 999;
}
.modal-content {
  width: 100%;
  background-color: #18181b;
  border: 1rpx solid rgba(255, 255, 255, 0.15);
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
  font-size: 32rpx;
  color: #a1a1aa;
}
.input-hint {
  font-size: 24rpx;
  color: #a1a1aa;
  margin-bottom: 20rpx;
  display: block;
}
.code-input {
  background-color: rgba(255, 255, 255, 0.05);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  height: 88rpx;
  border-radius: 20rpx;
  padding: 0 24rpx;
  color: #ffffff;
  font-size: 32rpx;
  letter-spacing: 4rpx;
  text-transform: uppercase;
  margin-bottom: 32rpx;
}
.submit-btn {
  background: linear-gradient(90deg, #FC4C02 0%, #ea580c 100%);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  height: 84rpx;
  line-height: 84rpx;
  border-radius: 20rpx;
}
</style>
