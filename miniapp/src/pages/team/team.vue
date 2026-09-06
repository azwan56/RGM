<template>
  <view class="team-page">
    <!-- ── Header: Club Hero ── -->
    <view class="club-hero-card">
      <view class="hero-top">
        <image class="club-logo" :src="currentClub?.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
        <view class="club-text">
          <view class="name-row">
            <text class="club-name">{{ currentClub?.name || "RGM 巅峰先锋跑团" }}</text>
            <text class="role-tag" :class="'role-' + currentRole">
              {{ currentRole === "owner" ? "👑 跑团主理人" : currentRole === "coach" ? "🧢 认证教练" : "🏃 核心团员" }}
            </text>
          </view>
          <text class="club-desc">{{ currentClub?.description || "基于科学耐力训练与 Renato Canova 哲学的精英跑者联盟" }}</text>
          <view class="invite-row" @click="handleCopyInvite">
            <text class="invite-label">跑团邀请码: </text>
            <text class="invite-val">{{ currentClub?.invite_code || "RGM888" }}</text>
            <text class="copy-hint"> (点击复制)</text>
          </view>
        </view>
      </view>
    </view>

    <!-- ── CARD 1: 👑 团长管理中心 (Only visible to Owner) ── -->
    <view v-if="currentRole === 'owner' || isOwnerOrDev" class="section-card owner-panel-card">
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">👑</text>
          <text class="card-title">跑团主理人管理中心</text>
        </view>
        <text class="owner-pill">团长权限</text>
      </view>

      <view class="owner-actions-grid">
        <view class="owner-tool-item" @click="handleOpenMembersModal">
          <view class="tool-icon-box bg-purple">
            <text class="tool-icon">👥</text>
          </view>
          <view class="tool-content">
            <text class="tool-main-title">跑团成员与指定教练</text>
            <text class="tool-sub-desc">管理成员身份、指定或撤销认证教练 ({{ members.length }}人)</text>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view class="owner-tool-item" @click="handleOpenCreateEvent">
          <view class="tool-icon-box bg-orange">
            <text class="tool-icon">🏆</text>
          </view>
          <view class="tool-content">
            <text class="tool-main-title">发起跑团挑战赛</text>
            <text class="tool-sub-desc">创建跑量挑战活动与奖励规则 ({{ events.length }}个进行中)</text>
          </view>
          <text class="arrow-right">›</text>
        </view>
      </view>
    </view>

    <!-- ── CARD 2: 🧢 教练学员体能罗盘 (Visible to Owner & Coach) ── -->
    <view
      v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev"
      class="section-card coach-preview-card"
      @click="goToCockpitPage"
    >
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">🧢</text>
          <text class="card-title">教练学员负荷监控大盘</text>
        </view>
        <text class="sub-link">进入全队体能罗盘 ›</text>
      </view>

      <view class="cockpit-summary-grid">
        <view class="cockpit-tile green">
          <text class="c-val">{{ coachCockpit?.summary?.peak_count || 0 }}人</text>
          <text class="c-label">🟢 巅峰状态</text>
        </view>
        <view class="cockpit-tile blue">
          <text class="c-val">{{ coachCockpit?.summary?.optimal_count || 1 }}人</text>
          <text class="c-label">🔵 专项适应</text>
        </view>
        <view class="cockpit-tile yellow">
          <text class="c-val">{{ coachCockpit?.summary?.tired_count || 0 }}人</text>
          <text class="c-label">🟡 疲劳积累</text>
        </view>
        <view class="cockpit-tile red">
          <text class="c-val">{{ coachCockpit?.summary?.danger_count || 0 }}人</text>
          <text class="c-label">🔴 伤病预警</text>
        </view>
      </view>
    </view>

    <!-- ── CARD 3: 跑团挑战赛与活动 ── -->
    <view class="section-card">
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">🏆</text>
          <text class="card-title">跑团挑战赛与活动 ({{ events.length }})</text>
        </view>
        <button
          v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev"
          class="mini-action-btn"
          @click="handleOpenCreateEvent"
        >
          + 发起挑战
        </button>
      </view>

      <view v-if="events.length" class="events-list">
        <view v-for="evt in events" :key="evt.id" class="event-card">
          <view class="evt-top">
            <text class="evt-tag">月度挑战</text>
            <view v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev" class="evt-actions">
              <text class="evt-btn edit" @click="handleOpenEditEvent(evt)">编辑</text>
              <text class="evt-btn del" @click="handleDeleteEvent(evt.id)">删除</text>
            </view>
          </view>
          <text class="evt-title">{{ evt.title }}</text>
          <text class="evt-rules">{{ evt.rules }}</text>
          <view class="evt-footer">
            <text class="evt-target">目标: <text class="highlight">{{ evt.target_km }} km</text></text>
            <text class="evt-status">进行中</text>
          </view>
        </view>
      </view>
      <view v-else class="empty-box">
        <text class="empty-text">暂无进行中的跑团活动</text>
      </view>
    </view>

    <!-- ── CARD 4: 跑团月度英雄榜 ── -->
    <view class="section-card">
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">🥇</text>
          <text class="card-title">本月跑团英雄榜</text>
        </view>
        <text class="sub-tip">按当月跑量排名</text>
      </view>

      <view v-if="leaderboard.length" class="leaderboard-list">
        <view
          v-for="item in leaderboard"
          :key="item.user_id"
          class="rank-item"
          :class="{ 'top-three': item.rank <= 3 }"
        >
          <view class="rank-left">
            <text class="rank-num" :class="'rank-' + item.rank">
              {{ item.rank === 1 ? '🥇' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : '#' + item.rank }}
            </text>
            <image class="user-avatar" :src="item.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
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
              <view class="progress-bar-fill" :style="{ width: Math.min(100, item.progress_pct) + '%' }" />
            </view>
          </view>
        </view>
      </view>
      <view v-else class="empty-box">
        <text class="empty-text">暂无成员打卡数据</text>
      </view>
    </view>

    <!-- ── CARD 5: 跑团打卡动态 · AI点评与跑友互动 ── -->
    <view class="section-card">
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">🔥</text>
          <text class="card-title">跑团打卡动态 · AI点评与跑友互动</text>
        </view>
      </view>

      <view v-if="feed.length" class="feed-list">
        <view v-for="act in feed" :key="act.id" class="feed-card">
          <!-- Member & Run Header -->
          <view class="feed-header">
            <image class="feed-avatar" :src="act.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
            <view class="feed-user-meta">
              <text class="feed-author">{{ act.display_name }}</text>
              <text class="feed-act-name">{{ act.name }} · 配速 {{ act.avg_pace_str }} · 心率 {{ act.average_heartrate || '—' }} bpm · TRIMP {{ act.trimp || 50 }}</text>
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
              <text class="coach-badge-title">Renato Canova AI 教练专属点评</text>
            </view>
            <text class="coach-comment-text">{{ act.ai_journal || "基于 Canova 耐力生理模型生成中..." }}</text>
          </view>

          <!-- Social Actions (Like & Comment buttons) -->
          <view class="social-bar">
            <view class="like-btn" :class="{ liked: act.has_liked }" @click="handleToggleLike(act)">
              <text class="heart-icon">{{ act.has_liked ? '❤️' : '🤍' }}</text>
              <text class="like-text">{{ act.has_liked ? '已点赞' : '点赞' }} ({{ act.likes_count || 0 }})</text>
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
        <text class="empty-text">暂无队员近期打卡，快去完成今日跑步吧！</text>
      </view>
    </view>

    <!-- ── Member & Coach Management Modal (跑团成员与指定教练管理) ── -->
    <view v-if="showMembersModal" class="modal-mask" @click="showMembersModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">跑团成员与指定教练</text>
            <text class="count-pill">{{ members.length }}人</text>
          </view>
          <text class="close-btn" @click="showMembersModal = false">✕</text>
        </view>

        <text class="modal-intro">💡 团长可在此任命【认证教练】协助指导学员体能负荷，或调整成员权限。</text>

        <input
          class="search-member-input"
          type="text"
          :adjust-position="false"
          :cursor-spacing="30"
          placeholder="🔍 搜索成员昵称..."
          v-model="memberSearchQuery"
        />

        <scroll-view scroll-y class="members-scroll">
          <view v-for="m in filteredMembers" :key="m.user_id" class="member-row">
            <view class="m-left">
              <image class="m-avatar" :src="m.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="m-info">
                <view class="m-name-line">
                  <text class="m-name">{{ m.display_name || '跑友' }}</text>
                  <text class="m-role-tag" :class="'tag-' + m.role">
                    {{ m.role === 'owner' ? '👑 团长' : m.role === 'coach' ? '🧢 教练' : '🏃 团员' }}
                  </text>
                </view>
                <text class="m-sub-text">当月跑量: {{ m.month_km || 0 }} km · 加入时间: {{ (m.joined_at || '').substring(0, 10) }}</text>
              </view>
            </view>

            <!-- Action buttons for Owner -->
            <view v-if="m.role !== 'owner'" class="m-actions">
              <button
                v-if="m.role !== 'coach'"
                class="act-pill coach-pill"
                @click="handleChangeRole(m.user_id, 'coach')"
              >
                🧢 指定教练
              </button>
              <button
                v-else
                class="act-pill member-pill"
                @click="handleChangeRole(m.user_id, 'member')"
              >
                🏃 取消教练
              </button>
              <button
                class="act-pill del-pill"
                @click="handleRemoveMember(m.user_id, m.display_name)"
              >
                移出
              </button>
            </view>
            <view v-else class="owner-static-tag">
              <text class="owner-tag-text">跑团主理人</text>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── Create / Edit Event Modal ── -->
    <view v-if="showEventModal" class="modal-mask" @click="showEventModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">{{ editingEventId ? '编辑跑团活动' : '发起跑团挑战赛' }}</text>
          <text class="close-btn" @click="showEventModal = false">✕</text>
        </view>

        <view class="modal-body">
          <text class="input-label">活动标题</text>
          <input
            class="text-input"
            type="text"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="例如: 9月 200km 破风进阶挑战"
            v-model="eventTitle"
          />

          <text class="input-label">目标跑量 (km)</text>
          <input
            class="text-input"
            type="number"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="200"
            v-model="eventTargetKm"
          />

          <text class="input-label">挑战规则与奖励说明</text>
          <textarea
            class="textarea-input"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="完赛即可解锁专属电子勋章与跑团定制奖章..."
            v-model="eventRules"
          />

          <button class="submit-btn" :loading="savingEvent" @click="handleSaveEvent">
            {{ editingEventId ? '保存修改' : '立即发布' }}
          </button>
        </view>
      </view>
    </view>

    <!-- ── Comment Modal (跑友留言输入弹窗) ── -->
    <view v-if="showCommentModal" class="modal-mask" @click="showCommentModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">发表跑友留言</text>
          <text class="close-btn" @click="showCommentModal = false">✕</text>
        </view>

        <view class="modal-body">
          <text class="input-hint">在 AI 教练评语后给队友鼓励或写句评语：</text>
          <textarea
            class="textarea-input"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="太棒了，配速和心率控制非常稳！..."
            v-model="commentTextInput"
          />
          <button class="submit-btn" :loading="submittingComment" @click="handleSendComment">发送留言</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import { request, getStoredUser, checkAndAutoLogin, UserProfile } from "../../utils/api";

const user = ref<UserProfile | null>(null);
const currentClub = ref<any>(null);
const currentRole = ref("member");

const events = ref<any[]>([]);
const leaderboard = ref<any[]>([]);
const members = ref<any[]>([]);
const coachCockpit = ref<any>(null);
const feed = ref<any[]>([]);

const showMembersModal = ref(false);
const memberSearchQuery = ref("");

const showEventModal = ref(false);
const showCommentModal = ref(false);

const editingEventId = ref<string | null>(null);
const eventTitle = ref("");
const eventTargetKm = ref<number | string>(200);
const eventRules = ref("");

const activeCommentActivityId = ref<string | null>(null);
const commentTextInput = ref("");

const savingEvent = ref(false);
const submittingComment = ref(false);

const isOwnerOrDev = computed(() => {
  if (!user.value || !currentClub.value) return false;
  return (
    currentRole.value === "owner" ||
    currentClub.value.owner_id === user.value.id
  );
});

const filteredMembers = computed(() => {
  if (!memberSearchQuery.value.trim()) return members.value;
  const q = memberSearchQuery.value.trim().toLowerCase();
  return members.value.filter(
    (m) =>
      (m.display_name || "").toLowerCase().includes(q) ||
      (m.user_id || "").toLowerCase().includes(q)
  );
});

async function loadClubData() {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    const res = await request(`/api/team/my-clubs/${uid}`);
    const clubs = res?.clubs || [];
    if (clubs.length > 0) {
      currentClub.value = clubs[0];
      currentRole.value = clubs[0].role || "member";
      const clubId = clubs[0].id;

      // Load events, leaderboard, members, coach cockpit, feed
      const [evtRes, lbRes, memRes, coachRes, feedRes] = await Promise.all([
        request(`/api/team/${clubId}/events`),
        request(`/api/team/${clubId}/leaderboard`),
        request(`/api/team/${clubId}/members`),
        request(`/api/team/${clubId}/coach-cockpit?coach_uid=${uid}`),
        request(`/api/team/${clubId}/feed?uid=${uid}`),
      ]);

      events.value = evtRes?.events || [];
      leaderboard.value = lbRes?.leaderboard || [];
      members.value = memRes?.members || [];
      coachCockpit.value = coachRes || null;
      feed.value = feedRes?.feed || [];
    }
  } catch (e) {
    console.warn("Load club data error:", e);
  }
}

function handleCopyInvite() {
  if (!currentClub.value?.invite_code) return;
  uni.setClipboardData({
    data: currentClub.value.invite_code,
    success: () => {
      uni.showToast({ title: "跑团邀请码已复制", icon: "success" });
    }
  });
}

function goToCockpitPage() {
  uni.navigateTo({
    url: "/pages/team/cockpit"
  });
}

function handleOpenMembersModal() {
  memberSearchQuery.value = "";
  showMembersModal.value = true;
}

async function handleChangeRole(targetUid: string, role: string) {
  if (!currentClub.value) return;
  const uid = user.value?.id;
  if (!uid) return;
  try {
    await request(`/api/team/${currentClub.value.id}/role`, "POST", {
      operator_uid: uid,
      target_uid: targetUid,
      role: role,
    });
    uni.showToast({
      title: `已设为【${role === "coach" ? "认证教练" : role === "owner" ? "团长" : "普通团员"}】`,
      icon: "success",
    });
    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: e.message || "角色修改失败", icon: "none" });
  }
}

async function handleRemoveMember(targetUid: string, displayName: string) {
  if (!currentClub.value) return;
  const uid = user.value?.id;
  if (!uid) return;
  uni.showModal({
    title: "移出跑团",
    content: `确定要将【${displayName || "该成员"}】移出跑团吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await request(
            `/api/team/${currentClub.value.id}/members/${targetUid}?operator_uid=${uid}`,
            "DELETE"
          );
          uni.showToast({ title: "成员已移出", icon: "success" });
          await loadClubData();
        } catch (e: any) {
          uni.showToast({ title: "移出失败", icon: "none" });
        }
      }
    }
  });
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
    const res = await request(`/api/team/activities/${activeCommentActivityId.value}/comments`, "POST", {
      user_id: uid,
      content: commentTextInput.value.trim(),
      author_name: user.value?.display_name || user.value?.email?.split("@")[0] || "跑友",
      author_avatar: user.value?.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80",
    });

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

function handleOpenCreateEvent() {
  editingEventId.value = null;
  eventTitle.value = "";
  eventTargetKm.value = 200;
  eventRules.value = "";
  showEventModal.value = true;
}

function handleOpenEditEvent(evt: any) {
  editingEventId.value = evt.id;
  eventTitle.value = evt.title || "";
  eventTargetKm.value = evt.target_km || 200;
  eventRules.value = evt.rules || "";
  showEventModal.value = true;
}

async function handleDeleteEvent(eventId: string) {
  if (!currentClub.value) return;
  uni.showModal({
    title: "确认删除",
    content: "确定要删除该跑团活动吗？",
    success: async (res) => {
      if (res.confirm) {
        try {
          await request(`/api/team/${currentClub.value.id}/events/${eventId}`, "DELETE");
          uni.showToast({ title: "活动已删除", icon: "success" });
          await loadClubData();
        } catch (e: any) {
          uni.showToast({ title: "删除失败", icon: "none" });
        }
      }
    }
  });
}

async function handleSaveEvent() {
  if (!currentClub.value || !eventTitle.value.trim()) {
    uni.showToast({ title: "请输入活动标题", icon: "none" });
    return;
  }
  const uid = user.value?.id;
  if (!uid) return;
  savingEvent.value = true;
  try {
    if (editingEventId.value) {
      await request(`/api/team/${currentClub.value.id}/events/${editingEventId.value}`, "PUT", {
        operator_uid: uid,
        title: eventTitle.value.trim(),
        target_km: Number(eventTargetKm.value) || 200,
        rules: eventRules.value.trim()
      });
      uni.showToast({ title: "修改成功！", icon: "success" });
    } else {
      await request(`/api/team/${currentClub.value.id}/events`, "POST", {
        operator_uid: uid,
        title: eventTitle.value.trim(),
        target_km: Number(eventTargetKm.value) || 200,
        rules: eventRules.value.trim()
      });
      uni.showToast({ title: "发布成功！", icon: "success" });
    }
    showEventModal.value = false;
    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: "操作失败", icon: "none" });
  } finally {
    savingEvent.value = false;
  }
}

onShow(() => {
  loadClubData();
});

onPullDownRefresh(async () => {
  try {
    await loadClubData();
    uni.showToast({ title: "跑团数据已更新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新数据", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});
</script>

<style scoped>
.team-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
}

.club-hero-card {
  background: linear-gradient(135deg, #1c1c20 0%, #131316 100%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.5);
}

.hero-top {
  display: flex;
  gap: 24rpx;
}

.club-logo {
  width: 120rpx;
  height: 120rpx;
  border-radius: 24rpx;
  border: 2rpx solid rgba(252, 76, 2, 0.4);
}

.club-text {
  flex: 1;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.club-name {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
}

.role-tag {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
}

.role-owner {
  background-color: rgba(255, 159, 10, 0.25);
  color: #ff9f0a;
}

.role-coach {
  background-color: rgba(191, 90, 242, 0.25);
  color: #bf5af2;
}

.role-member {
  background-color: rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}

.club-desc {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 8rpx;
  display: block;
  line-height: 1.4;
}

.invite-row {
  display: flex;
  align-items: center;
  margin-top: 12rpx;
  font-size: 22rpx;
}

.invite-label {
  color: #636366;
}

.invite-val {
  color: #fc4c02;
  font-weight: bold;
  font-family: monospace;
}

.copy-hint {
  color: #0a84ff;
  font-size: 20rpx;
}

.section-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
}

/* 👑 Owner Panel */
.owner-panel-card {
  background: linear-gradient(135deg, rgba(255, 159, 10, 0.1) 0%, #151518 100%);
  border: 1rpx solid rgba(255, 159, 10, 0.3);
}

.owner-pill {
  font-size: 20rpx;
  font-weight: bold;
  color: #ff9f0a;
  background-color: rgba(255, 159, 10, 0.2);
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
}

.owner-actions-grid {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-top: 10rpx;
}

.owner-tool-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background-color: #1c1c20;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  transition: all 0.2s;
}

.tool-icon-box {
  width: 68rpx;
  height: 68rpx;
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tool-icon-box.bg-purple {
  background-color: rgba(191, 90, 242, 0.2);
}

.tool-icon-box.bg-orange {
  background-color: rgba(252, 76, 2, 0.2);
}

.tool-icon {
  font-size: 32rpx;
}

.tool-content {
  flex: 1;
}

.tool-main-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
  display: block;
}

.tool-sub-desc {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
  display: block;
}

.arrow-right {
  font-size: 26rpx;
  color: #636366;
}

/* 🧢 Coach Preview */
.coach-preview-card {
  border: 1rpx solid rgba(191, 90, 242, 0.3);
  background: linear-gradient(135deg, rgba(191, 90, 242, 0.08) 0%, #151518 100%);
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

.icon {
  font-size: 30rpx;
}

.card-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.sub-link {
  font-size: 22rpx;
  color: #bf5af2;
  font-weight: bold;
}

.sub-tip {
  font-size: 20rpx;
  color: #8e8e93;
}

.cockpit-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
}

.cockpit-tile {
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 16rpx 10rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1rpx solid transparent;
}

.cockpit-tile.green { border-color: rgba(48, 209, 88, 0.3); }
.cockpit-tile.blue { border-color: rgba(10, 132, 255, 0.3); }
.cockpit-tile.yellow { border-color: rgba(255, 214, 10, 0.3); }
.cockpit-tile.red { border-color: rgba(255, 69, 58, 0.3); }

.c-val {
  font-size: 28rpx;
  font-weight: 900;
  color: #ffffff;
}

.c-label {
  font-size: 18rpx;
  color: #8e8e93;
  margin-top: 6rpx;
}

/* Events */
.mini-action-btn {
  font-size: 22rpx;
  font-weight: bold;
  background: #fc4c02;
  color: #ffffff;
  padding: 0 18rpx;
  height: 52rpx;
  line-height: 52rpx;
  border-radius: 14rpx;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.event-card {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 22rpx;
}

.evt-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.evt-tag {
  font-size: 20rpx;
  color: #0a84ff;
  background-color: rgba(10, 132, 255, 0.15);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.evt-actions {
  display: flex;
  gap: 16rpx;
}

.evt-btn {
  font-size: 22rpx;
}

.evt-btn.edit { color: #0a84ff; }
.evt-btn.del { color: #ff453a; }

.evt-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
  display: block;
}

.evt-rules {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 8rpx;
  display: block;
}

.evt-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
}

.evt-target {
  font-size: 22rpx;
  color: #8e8e93;
}

.evt-target .highlight {
  color: #fc4c02;
  font-weight: bold;
}

.evt-status {
  font-size: 20rpx;
  color: #30d158;
}

/* Leaderboard */
.leaderboard-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.rank-item {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 18rpx 20rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rank-item.top-three {
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.rank-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.rank-num {
  font-size: 32rpx;
  font-weight: 900;
  width: 44rpx;
  text-align: center;
  color: #8e8e93;
}

.user-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 36rpx;
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
  font-size: 30rpx;
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
  background-color: #fc4c02;
}

/* Feed */
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.feed-card {
  background-color: #1a1a1e;
  border-radius: 24rpx;
  padding: 24rpx;
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
}

.feed-distance {
  text-align: right;
}

.feed-km {
  font-size: 36rpx;
  font-weight: 900;
  color: #fc4c02;
  font-family: monospace;
}

.feed-unit {
  font-size: 20rpx;
  color: #8e8e93;
  margin-left: 4rpx;
}

.coach-bubble {
  background: linear-gradient(135deg, rgba(191, 90, 242, 0.12) 0%, rgba(10, 132, 255, 0.08) 100%);
  border: 1rpx solid rgba(191, 90, 242, 0.25);
  border-radius: 18rpx;
  padding: 16rpx;
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
  color: #e5e5ea;
  line-height: 1.4;
  display: block;
}

.social-bar {
  display: flex;
  gap: 24rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
}

.like-btn, .comment-trigger-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background-color: #242428;
}

.heart-icon, .cmt-icon {
  font-size: 22rpx;
}

.like-text, .cmt-text {
  font-size: 22rpx;
  color: #8e8e93;
}

.like-btn.liked .like-text {
  color: #ff3b30;
  font-weight: bold;
}

.comments-box {
  margin-top: 14rpx;
  background-color: #242428;
  border-radius: 14rpx;
  padding: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.cmt-item {
  font-size: 22rpx;
  line-height: 1.4;
}

.cmt-author {
  color: #0a84ff;
  font-weight: bold;
}

.cmt-content {
  color: #d1d1d6;
}

.empty-box {
  padding: 40rpx;
  text-align: center;
}

.empty-text {
  font-size: 24rpx;
  color: #636366;
}

/* Modals */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 80rpx;
  z-index: 999;
  overflow-y: auto;
}

.modal-content {
  width: 670rpx;
  background-color: #18181c;
  border-radius: 36rpx;
  padding: 40rpx;
  box-sizing: border-box;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  margin-bottom: 60rpx;
}

.modal-content.large-modal {
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.title-with-pill {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.modal-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
}

.count-pill {
  font-size: 20rpx;
  color: #bf5af2;
  background: rgba(191, 90, 242, 0.2);
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
}

.close-btn {
  font-size: 34rpx;
  color: #8e8e93;
}

.modal-intro {
  font-size: 22rpx;
  color: #8e8e93;
  margin-bottom: 20rpx;
  display: block;
}

.search-member-input {
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  height: 72rpx;
  padding: 0 20rpx;
  font-size: 24rpx;
  color: #ffffff;
  margin-bottom: 20rpx;
}

.members-scroll {
  max-height: 520rpx;
  display: flex;
  flex-direction: column;
}

.member-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.05);
}

.m-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
}

.m-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 36rpx;
}

.m-info {
  flex: 1;
}

.m-name-line {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.m-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.m-role-tag {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
}

.tag-owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: #ff9f0a;
}

.tag-coach {
  background-color: rgba(191, 90, 242, 0.2);
  color: #bf5af2;
}

.tag-member {
  background-color: rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}

.m-sub-text {
  font-size: 20rpx;
  color: #636366;
  margin-top: 4rpx;
  display: block;
}

.m-actions {
  display: flex;
  gap: 10rpx;
}

.act-pill {
  font-size: 20rpx;
  font-weight: bold;
  padding: 0 14rpx;
  height: 48rpx;
  line-height: 48rpx;
  border-radius: 12rpx;
  border: none;
}

.coach-pill {
  background: rgba(191, 90, 242, 0.25);
  color: #bf5af2;
}

.member-pill {
  background: rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}

.del-pill {
  background: rgba(255, 69, 58, 0.15);
  color: #ff453a;
}

.owner-static-tag {
  font-size: 20rpx;
  color: #ff9f0a;
  font-weight: bold;
}

.input-label {
  font-size: 24rpx;
  color: #8e8e93;
  margin-top: 16rpx;
  margin-bottom: 8rpx;
  display: block;
}

.input-hint {
  font-size: 22rpx;
  color: #8e8e93;
  margin-bottom: 16rpx;
  display: block;
}

.text-input {
  width: 100%;
  height: 80rpx;
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 0 20rpx;
  font-size: 26rpx;
  color: #ffffff;
  box-sizing: border-box;
}

.textarea-input {
  width: 100%;
  height: 140rpx;
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  font-size: 24rpx;
  color: #ffffff;
  box-sizing: border-box;
}

.submit-btn {
  width: 100%;
  height: 84rpx;
  line-height: 84rpx;
  background: #fc4c02;
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 20rpx;
  margin-top: 24rpx;
  border: none;
}
</style>
