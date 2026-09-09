<template>
  <view class="rank-page">
    <!-- ── 顶部导航栏 / 跑团与榜单快速切换胶囊 ── -->
    <view class="top-nav-capsule">
      <view class="nav-segment active">
        <text class="nav-icon">🥇</text>
        <text class="nav-text">英雄榜与动态</text>
      </view>
      <view class="nav-segment" @click="goToTeamPage">
        <text class="nav-icon">🏃</text>
        <text class="nav-text">跑团大本营 ›</text>
      </view>
    </view>

    <!-- If user belongs to a club -->
    <view v-if="currentClub" class="rank-content">
      <!-- ── 跑团简要上下文横幅与切换 ── -->
      <view class="club-context-bar">
        <image
          class="club-logo-mini"
          :src="currentClub.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'"
          mode="aspectFill"
          @click="goToTeamPage"
        />
        <view class="club-meta" @click="goToTeamPage">
          <view class="club-name-row">
            <text class="club-title">{{ currentClub.name }}</text>
            <text class="role-badge" :class="'role-' + currentRole">
              {{ currentRole === "owner" ? "👑 主理人" : currentRole === "coach" ? "🧢 教练" : "🏃 队员" }}
            </text>
          </view>
          <text class="club-subtitle">本月跑量风云榜 · 动态互动社区</text>
        </view>
        <view v-if="userClubs.length > 1" class="switch-club-pill" @click="showSwitchModal = true">
          <text class="switch-icon">⇄</text>
          <text class="switch-text">切换跑团</text>
        </view>
        <view v-else class="enter-team-hint" @click="goToTeamPage">
          <text class="hint-text">跑团主页</text>
          <text class="arrow">›</text>
        </view>
      </view>

      <!-- ── SECTION 1: 🥇 本月跑团英雄榜 ── -->
      <view class="section-card">
        <view class="card-header-row">
          <view class="title-with-icon">
            <text class="icon">🥇</text>
            <text class="card-title">本月跑团英雄榜</text>
          </view>
          <view class="header-right-meta">
            <text class="sub-tip">按当月实跑里程排名</text>
          </view>
        </view>

        <view v-if="leaderboard.length" class="leaderboard-list">
          <view
            v-for="item in leaderboard"
            :key="item.user_id"
            class="rank-item"
            :class="{ 'top-three': item.rank <= 3, 'rank-gold': item.rank === 1, 'rank-silver': item.rank === 2, 'rank-bronze': item.rank === 3 }"
          >
            <view class="rank-left">
              <view class="rank-badge-box">
                <text class="rank-num" :class="'rank-' + item.rank">
                  {{ item.rank === 1 ? '🥇' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : '#' + item.rank }}
                </text>
              </view>
              <image
                class="user-avatar"
                :src="item.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                mode="aspectFill"
              />
              <view class="user-info">
                <view class="name-badge-row">
                  <text class="user-name">{{ item.display_name }}</text>
                  <text v-if="item.role === 'owner'" class="mini-role-tag owner">团长</text>
                  <text v-else-if="item.role === 'coach'" class="mini-role-tag coach">教练</text>
                </view>
                <text class="progress-sub">完成度 {{ item.progress_pct }}% · 目标 {{ item.target_km }}km</text>
              </view>
            </view>

            <view class="rank-right">
              <text class="km-val">{{ item.distance_km }} <text class="unit">km</text></text>
              <view class="progress-bar-bg">
                <view
                  class="progress-bar-fill"
                  :style="{ width: Math.min(100, item.progress_pct) + '%' }"
                />
              </view>
            </view>
          </view>
        </view>
        <view v-else class="empty-box">
          <text class="empty-icon">🏃</text>
          <text class="empty-text">本月暂无成员打卡数据，快去拔得头筹！</text>
        </view>
      </view>

      <!-- ── SECTION 2: 🔥 跑团打卡动态 · AI点评与跑友互动 ── -->
      <view class="section-card">
        <view class="card-header-row">
          <view class="title-with-icon">
            <text class="icon">🔥</text>
            <text class="card-title">跑团打卡动态 · AI点评与互动</text>
          </view>
          <text class="sub-tip">实战记录 · 互相激励</text>
        </view>

        <view v-if="feed.length" class="feed-list">
          <view v-for="act in feed" :key="act.id" class="feed-card">
            <!-- Member & Run Header -->
            <view class="feed-header">
              <image
                class="feed-avatar"
                :src="act.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                mode="aspectFill"
              />
              <view class="feed-user-meta">
                <text class="feed-author">{{ act.display_name }}</text>
                <text class="feed-act-name">
                  {{ act.name }} · 配速 {{ act.avg_pace_str }} · 心率 {{ act.average_heartrate || '—' }} bpm · TRIMP {{ act.trimp || 50 }}
                </text>
              </view>
              <view class="feed-distance">
                <text class="feed-km">{{ (act.distance_meters / 1000).toFixed(1) }}</text>
                <text class="feed-unit">km</text>
              </view>
            </view>

            <!-- AI Coach Critique Bubble -->
            <view class="coach-bubble">
              <view class="coach-badge-row">
                <text class="coach-robot-icon">🤖</text>
                <text class="coach-badge-title">Canova教练专属点评</text>
              </view>
              <text class="coach-comment-text">
                {{ act.ai_journal || "基于 Canova 耐力生理模型生成中..." }}
              </text>
            </view>

            <!-- Social Actions (Like & Comment buttons) -->
            <view class="social-bar">
              <view
                class="like-btn"
                :class="{ liked: act.has_liked }"
                @click="handleToggleLike(act)"
              >
                <text class="heart-icon">{{ act.has_liked ? '❤️' : '🤍' }}</text>
                <text class="like-text">
                  {{ act.has_liked ? '已点赞' : '点赞' }} ({{ act.likes_count || 0 }})
                </text>
              </view>
              <view class="comment-trigger-btn" @click="handleOpenCommentModal(act)">
                <text class="cmt-icon">💬</text>
                <text class="cmt-text">留言 ({{ act.comments?.length || 0 }})</text>
              </view>
            </view>

            <!-- Comments List -->
            <view v-if="act.comments && act.comments.length > 0" class="comments-box">
              <view v-for="c in act.comments" :key="c.id" class="cmt-item">
                <text class="cmt-author">{{ c.author_name }}: </text>
                <text class="cmt-content">{{ c.content }}</text>
              </view>
            </view>
          </view>
        </view>
        <view v-else class="empty-box">
          <text class="empty-icon">👟</text>
          <text class="empty-text">暂无队员近期打卡，快去完成今日跑步吧！</text>
        </view>
      </view>
    </view>

    <!-- ── Unjoined Empty State (未加入任何跑团) ── -->
    <view v-else class="unjoined-view">
      <view class="unjoined-card">
        <text class="unjoined-icon">🏅</text>
        <text class="unjoined-title">尚未加入跑团</text>
        <text class="unjoined-desc">
          英雄榜与打卡互动仅对跑团队员开放。加入跑团后，即可与队友共同争夺月跑量排名、接收 Canova教练打卡点评并互相激励！
        </text>
        <button class="goto-team-btn" @click="goToTeamPage">
          前往跑团大本营加入跑团
        </button>
      </view>
    </view>

    <!-- ── Write Comment Modal (互动留言弹窗) ── -->
    <view
      v-if="showCommentModal"
      class="modal-mask"
      @click="showCommentModal = false"
      @touchmove.stop.prevent
    >
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">跑友留言鼓励</text>
          <text class="close-btn" @click="showCommentModal = false">✕</text>
        </view>
        <view class="modal-body">
          <textarea
            class="textarea-input"
            :adjust-position="true"
            :cursor-spacing="30"
            placeholder="为队友加油、讨论训练配速或心率心得..."
            v-model="commentTextInput"
          />
          <button
            class="submit-btn"
            :loading="submittingComment"
            @click="handleSendComment"
          >
            发送留言
          </button>
        </view>
      </view>
    </view>

    <!-- ── Switch Club Modal (切换已加入的跑团) ── -->
    <view v-if="showSwitchModal" class="modal-mask" @click="showSwitchModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">切换当前跑团榜单</text>
            <text class="count-pill">{{ userClubs.length }} 个跑团</text>
          </view>
          <text class="close-btn" @click="showSwitchModal = false">✕</text>
        </view>

        <view class="modal-body modal-scroll">
          <view class="modal-clubs-list">
            <view
              v-for="c in userClubs"
              :key="c.id"
              class="modal-club-card"
              :class="{ 'is-current': currentClub?.id === c.id }"
              @click="handleSwitchClub(c)"
            >
              <image class="mcc-logo" :src="c.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="mcc-info">
                <view class="mcc-name-row">
                  <text class="mcc-name">{{ c.name }}</text>
                  <text class="mcc-city">📍 {{ c.city || '上海' }}</text>
                </view>
                <view class="mcc-meta">
                  <text class="mcc-role-tag" :class="'role-' + c.role">
                    {{ c.role === 'owner' ? '👑 团长' : c.role === 'coach' ? '🧢 教练' : '🏃 团员' }}
                  </text>
                </view>
              </view>
              <view class="mcc-action">
                <text v-if="currentClub?.id === c.id" class="mcc-current-tag">当前榜单 ✓</text>
                <button v-else class="mcc-switch-btn" @click.stop="handleSwitchClub(c)">
                  ⇄ 切换
                </button>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import {
  request,
  getStoredUser,
  checkAndAutoLogin,
  UserProfile,
  getActiveClubId,
  setActiveClubId,
  resolveActiveClub,
  syncTabBarIndex,
} from "../../utils/api";

const user = ref<UserProfile | null>(null);
const currentClub = ref<any>(null);
const currentRole = ref("member");
const userClubs = ref<any[]>([]);
const showSwitchModal = ref(false);

const leaderboard = ref<any[]>([]);
const feed = ref<any[]>([]);

const showCommentModal = ref(false);
const activeCommentActivityId = ref<string | null>(null);
const commentTextInput = ref("");
const submittingComment = ref(false);

function goToTeamPage() {
  uni.navigateTo({
    url: "/pages/team/team",
  });
}

async function loadRankData(preferredClubId?: string) {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    const res = await request(`/api/team/my-clubs/${uid}`);
    const clubs = res?.clubs || [];
    userClubs.value = clubs;

    if (clubs.length > 0) {
      let targetClub: any = null;
      if (preferredClubId) {
        targetClub = clubs.find((c: any) => c.id === preferredClubId);
      }
      if (!targetClub) {
        targetClub = resolveActiveClub(clubs);
      } else {
        setActiveClubId(targetClub.id);
      }

      currentClub.value = targetClub;
      currentRole.value = targetClub.role || "member";
      const clubId = targetClub.id;

      // Only fetch leaderboard and feed for high performance
      const [lbRes, feedRes] = await Promise.all([
        request(`/api/team/${clubId}/leaderboard`),
        request(`/api/team/${clubId}/feed?uid=${uid}`),
      ]);

      leaderboard.value = lbRes?.leaderboard || [];
      feed.value = feedRes?.feed || [];
    } else {
      setActiveClubId("");
      currentClub.value = null;
      currentRole.value = "member";
      leaderboard.value = [];
      feed.value = [];
    }
  } catch (e) {
    console.warn("Load rank data error:", e);
  }
}

function handleSwitchClub(club: any) {
  if (!club || !club.id) return;
  setActiveClubId(club.id);
  showSwitchModal.value = false;
  uni.showToast({
    title: `已切换至【${club.name}】榜单`,
    icon: "success",
  });
  loadRankData(club.id);
}

async function handleToggleLike(act: any) {
  const uid = user.value?.id;
  if (!uid) return;
  try {
    const res = await request(`/api/team/activities/${act.id}/like`, "POST", {
      user_id: uid,
    });
    act.has_liked = res.liked;
    act.likes_count = res.likes_count;
  } catch (e: any) {
    uni.showToast({ title: "点赞失败", icon: "none" });
  }
}

function handleOpenCommentModal(act: any) {
  activeCommentActivityId.value = act.id;
  commentTextInput.value = "";
  showCommentModal.value = true;
}

async function handleSendComment() {
  if (!commentTextInput.value.trim() || !activeCommentActivityId.value) return;
  const uid = user.value?.id;
  if (!uid) return;
  submittingComment.value = true;
  try {
    const res = await request(
      `/api/team/activities/${activeCommentActivityId.value}/comments`,
      "POST",
      {
        user_id: uid,
        content: commentTextInput.value.trim(),
        author_name: user.value?.display_name || user.value?.email?.split("@")[0] || "跑友",
        author_avatar:
          user.value?.avatar_url ||
          "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80",
      }
    );

    const targetAct = feed.value.find((a) => a.id === activeCommentActivityId.value);
    if (targetAct) {
      if (!targetAct.comments) targetAct.comments = [];
      targetAct.comments.push(res.comment);
    }
    showCommentModal.value = false;
    uni.showToast({ title: "评论成功！", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: "评论失败", icon: "none" });
  } finally {
    submittingComment.value = false;
  }
}

onShow(() => {
  syncTabBarIndex(3);
  loadRankData();
});

onPullDownRefresh(async () => {
  await loadRankData();
  uni.stopPullDownRefresh();
});
</script>

<style scoped>
.rank-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  color: #f4f4f5;
  padding: 24rpx;
  padding-bottom: 80rpx;
  box-sizing: border-box;
}

/* ── 顶部导航胶囊切换条 ── */
.top-nav-capsule {
  display: flex;
  background-color: #16161a;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 40rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
}

.nav-segment {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  padding: 16rpx 0;
  border-radius: 34rpx;
  transition: all 0.25s ease;
}

.nav-segment.active {
  background: linear-gradient(135deg, #fc4c02 0%, #ff7300 100%);
  box-shadow: 0 4rpx 16rpx rgba(252, 76, 2, 0.35);
}

.nav-icon {
  font-size: 26rpx;
}

.nav-text {
  font-size: 26rpx;
  font-weight: bold;
  color: #a1a1aa;
}

.nav-segment.active .nav-text {
  color: #ffffff;
}

/* ── 跑团上下文横幅 ── */
.club-context-bar {
  display: flex;
  align-items: center;
  background: linear-gradient(135deg, #18181b 0%, #121214 100%);
  border: 1rpx solid rgba(252, 76, 2, 0.2);
  border-radius: 24rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
  gap: 16rpx;
}

.club-logo-mini {
  width: 72rpx;
  height: 72rpx;
  border-radius: 20rpx;
  border: 2rpx solid rgba(252, 76, 2, 0.4);
}

.club-meta {
  flex: 1;
  min-width: 0;
}

.club-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.club-title {
  font-size: 28rpx;
  font-weight: 900;
  color: #ffffff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-badge {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.role-badge.role-owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: #ff9f0a;
  border: 1rpx solid rgba(255, 159, 10, 0.4);
}

.role-badge.role-coach {
  background-color: rgba(191, 90, 242, 0.2);
  color: #bf5af2;
  border: 1rpx solid rgba(191, 90, 242, 0.4);
}

.role-badge.role-member {
  background-color: rgba(10, 132, 255, 0.15);
  color: #0a84ff;
}

.club-subtitle {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
  display: block;
}

.enter-team-hint {
  display: flex;
  align-items: center;
  gap: 4rpx;
}

.hint-text {
  font-size: 22rpx;
  color: #fc4c02;
  font-weight: bold;
}

.arrow {
  font-size: 26rpx;
  color: #fc4c02;
  font-weight: bold;
}

.switch-club-pill {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background: rgba(252, 76, 2, 0.15);
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  padding: 10rpx 18rpx;
  border-radius: 20rpx;
}

.switch-icon {
  font-size: 24rpx;
  color: #fc4c02;
  font-weight: bold;
}

.switch-text {
  font-size: 22rpx;
  color: #fc4c02;
  font-weight: bold;
}

/* Modal styles for club switching in rank.vue */
.modal-scroll {
  max-height: 60vh;
  overflow-y: auto;
}

.modal-clubs-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.modal-club-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 20rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
}

.modal-club-card.is-current {
  border-color: rgba(252, 76, 2, 0.4);
  background: rgba(252, 76, 2, 0.06);
}

.mcc-logo {
  width: 72rpx;
  height: 72rpx;
  border-radius: 16rpx;
  flex-shrink: 0;
}

.mcc-info {
  flex: 1;
  min-width: 0;
}

.mcc-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6rpx;
}

.mcc-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcc-city {
  font-size: 20rpx;
  color: #a1a1aa;
}

.mcc-meta {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.mcc-role-tag {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.mcc-role-tag.role-owner {
  background: rgba(255, 159, 10, 0.2);
  color: #ff9f0a;
}

.mcc-role-tag.role-coach {
  background: rgba(10, 132, 255, 0.2);
  color: #0a84ff;
}

.mcc-role-tag.role-member {
  background: rgba(255, 255, 255, 0.1);
  color: #a1a1aa;
}

.mcc-action {
  flex-shrink: 0;
  margin-left: 12rpx;
}

.mcc-current-tag {
  font-size: 22rpx;
  color: #fc4c02;
  font-weight: bold;
  padding: 6rpx 16rpx;
  background: rgba(252, 76, 2, 0.15);
  border-radius: 12rpx;
}

.mcc-switch-btn {
  background: #27272a;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 500;
  padding: 0 24rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 12rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  margin: 0;
}

/* ── 通用卡片容器 ── */
.section-card {
  background-color: #121214;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 28rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.title-with-icon .icon {
  font-size: 32rpx;
}

.card-title {
  font-size: 30rpx;
  font-weight: 900;
  color: #ffffff;
}

.sub-tip {
  font-size: 20rpx;
  color: #8e8e93;
}

/* ── 英雄榜列表 ── */
.leaderboard-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.rank-item {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 20rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1rpx solid transparent;
  transition: all 0.2s ease;
}

.rank-item.top-three {
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.rank-item.rank-gold {
  background: linear-gradient(90deg, rgba(255, 215, 0, 0.1) 0%, #1a1a1e 70%);
  border-color: rgba(255, 215, 0, 0.35);
}

.rank-item.rank-silver {
  background: linear-gradient(90deg, rgba(192, 192, 192, 0.1) 0%, #1a1a1e 70%);
  border-color: rgba(192, 192, 192, 0.3);
}

.rank-item.rank-bronze {
  background: linear-gradient(90deg, rgba(205, 127, 50, 0.1) 0%, #1a1a1e 70%);
  border-color: rgba(205, 127, 50, 0.3);
}

.rank-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.rank-badge-box {
  width: 44rpx;
  text-align: center;
}

.rank-num {
  font-size: 32rpx;
  font-weight: 900;
  color: #8e8e93;
}

.user-avatar {
  width: 76rpx;
  height: 76rpx;
  border-radius: 38rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.1);
}

.user-info {
  display: flex;
  flex-direction: column;
}

.name-badge-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.user-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.mini-role-tag {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
}

.mini-role-tag.owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: #ff9f0a;
}

.mini-role-tag.coach {
  background-color: rgba(191, 90, 242, 0.2);
  color: #bf5af2;
}

.progress-sub {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
}

.rank-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.km-val {
  font-size: 32rpx;
  font-weight: 900;
  color: #fc4c02;
  font-family: monospace;
}

.km-val .unit {
  font-size: 20rpx;
  font-weight: normal;
  color: #8e8e93;
}

.progress-bar-bg {
  width: 140rpx;
  height: 6rpx;
  background-color: #2c2c2e;
  border-radius: 3rpx;
  margin-top: 8rpx;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #fc4c02, #ff7300);
}

/* ── 动态列表 ── */
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.feed-card {
  background-color: #1a1a1e;
  border-radius: 24rpx;
  padding: 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
}

.feed-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.feed-avatar {
  width: 76rpx;
  height: 76rpx;
  border-radius: 38rpx;
}

.feed-user-meta {
  flex: 1;
}

.feed-author {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
  display: block;
}

.feed-act-name {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
  display: block;
  line-height: 1.4;
}

.feed-distance {
  text-align: right;
}

.feed-km {
  font-size: 38rpx;
  font-weight: 900;
  color: #fc4c02;
  font-family: monospace;
}

.feed-unit {
  font-size: 20rpx;
  color: #8e8e93;
  margin-left: 4rpx;
}

/* AI Coach Bubble */
.coach-bubble {
  background: linear-gradient(135deg, rgba(191, 90, 242, 0.12) 0%, rgba(10, 132, 255, 0.08) 100%);
  border: 1rpx solid rgba(191, 90, 242, 0.25);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 16rpx;
}

.coach-badge-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 8rpx;
}

.coach-robot-icon {
  font-size: 22rpx;
}

.coach-badge-title {
  font-size: 20rpx;
  font-weight: bold;
  color: #bf5af2;
}

.coach-comment-text {
  font-size: 22rpx;
  color: #e4e4e7;
  line-height: 1.5;
  display: block;
}

/* Social Bar */
.social-bar {
  display: flex;
  gap: 20rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
  padding-top: 16rpx;
}

.like-btn,
.comment-trigger-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background-color: #242428;
  padding: 8rpx 20rpx;
  border-radius: 12rpx;
}

.like-btn.liked {
  background-color: rgba(255, 69, 58, 0.15);
}

.like-btn.liked .like-text {
  color: #ff453a;
}

.like-text,
.cmt-text {
  font-size: 22rpx;
  color: #a1a1aa;
}

/* Comments Box */
.comments-box {
  margin-top: 16rpx;
  background-color: #242428;
  border-radius: 14rpx;
  padding: 12rpx 16rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.cmt-item {
  font-size: 20rpx;
  line-height: 1.4;
}

.cmt-author {
  font-weight: bold;
  color: #0a84ff;
}

.cmt-content {
  color: #d4d4d8;
}

/* Empty State */
.empty-box {
  padding: 48rpx 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.empty-icon {
  font-size: 48rpx;
  margin-bottom: 12rpx;
}

.empty-text {
  font-size: 24rpx;
  color: #71717a;
}

/* Unjoined View */
.unjoined-view {
  padding: 60rpx 20rpx;
}

.unjoined-card {
  background-color: #121214;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 48rpx 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.unjoined-icon {
  font-size: 72rpx;
  margin-bottom: 20rpx;
}

.unjoined-title {
  font-size: 34rpx;
  font-weight: 900;
  color: #ffffff;
  margin-bottom: 16rpx;
}

.unjoined-desc {
  font-size: 24rpx;
  color: #8e8e93;
  line-height: 1.6;
  margin-bottom: 36rpx;
}

.goto-team-btn {
  background: linear-gradient(135deg, #fc4c02 0%, #ff7300 100%);
  color: #ffffff;
  font-size: 26rpx;
  font-weight: bold;
  padding: 0 40rpx;
  height: 80rpx;
  line-height: 80rpx;
  border-radius: 40rpx;
}

/* Modal */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 30rpx;
}

.modal-content {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 28rpx;
  width: 100%;
  max-width: 600rpx;
  padding: 30rpx;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.modal-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #ffffff;
}

.close-btn {
  font-size: 32rpx;
  color: #8e8e93;
  padding: 10rpx;
}

.textarea-input {
  width: 100%;
  height: 180rpx;
  background-color: #121214;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
  padding: 16rpx;
  box-sizing: border-box;
  font-size: 24rpx;
  color: #ffffff;
  margin-bottom: 24rpx;
}

.submit-btn {
  background: linear-gradient(135deg, #fc4c02 0%, #ff7300 100%);
  color: #ffffff;
  font-size: 26rpx;
  font-weight: bold;
  height: 72rpx;
  line-height: 72rpx;
  border-radius: 36rpx;
}
</style>
