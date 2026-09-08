<template>
  <view class="team-page">
    <!-- ── 顶部导航栏 / 跑团与榜单快速切换胶囊 ── -->
    <view class="top-nav-capsule">
      <view class="nav-segment" @click="goToRankPage">
        <text class="nav-icon">‹ 🥇</text>
        <text class="nav-text">英雄榜与动态</text>
      </view>
      <view class="nav-segment active">
        <text class="nav-icon">🏃</text>
        <text class="nav-text">跑团大本营</text>
      </view>
    </view>

    <!-- ── 跑团快速切换横向标签栏 (仅在加入跑团后显示) ── -->
    <view v-if="userClubs.length > 0" class="clubs-switcher-wrap">
      <scroll-view scroll-x class="clubs-switcher-scroll" :show-scrollbar="false">
        <view class="clubs-switcher-inner">
          <view
            v-for="c in userClubs"
            :key="c.id"
            class="club-tab-pill"
            :class="{ active: currentClub?.id === c.id }"
            @click="handleSwitchClub(c)"
          >
            <image
              class="tab-club-logo"
              :src="c.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'"
              mode="aspectFill"
            />
            <text class="tab-club-name">{{ c.name }}</text>
            <text v-if="currentClub?.id === c.id" class="tab-active-check">✓</text>
          </view>
          <view class="club-tab-pill tab-browse-btn" @click="openAllClubsModal">
            <text class="tab-browse-icon">＋ 发现跑团</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- If user belongs to a club -->
    <view v-if="currentClub">
      <!-- ── Header: Club Hero ── -->
      <view class="club-hero-card">
        <view class="hero-top">
          <image class="club-logo" :src="currentClub.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
          <view class="club-text">
            <view class="name-row">
              <text class="club-name">{{ currentClub.name }}</text>
              <text class="role-tag" :class="'role-' + currentRole">
                {{ currentRole === "owner" ? "👑 跑团主理人" : currentRole === "coach" ? "🧢 认证教练" : "🏃 核心团员" }}
              </text>
            </view>
            <text class="club-desc">{{ currentClub.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。" }}</text>
            <view class="browse-all-btn" @click="openAllClubsModal">
              <text class="browse-text">⇄ 切换跑团 ({{ userClubs.length }}) / 发现跑团 ›</text>
            </view>
          </view>
        </view>
      </view>

      <!-- ── 跑团英雄榜与打卡动态直通卡 ── -->
      <view class="rank-banner-card" @click="goToRankPage">
        <view class="banner-left">
          <view class="banner-badge-row">
            <text class="banner-badge">🥇 英雄风云榜</text>
            <text class="banner-hint-pill">独立专页 ›</text>
          </view>
          <text class="banner-title">本月跑团英雄榜 · 打卡动态与 AI 点评</text>
          <text class="banner-desc">查看全团队员跑量排名、达标进度与 Canova AI 动态互动</text>
        </view>
        <view class="banner-arrow-box">
          <text class="banner-arrow">→</text>
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
    </view>

    <!-- ── Unjoined State: List all created clubs for user to choose & join ── -->
    <view v-else class="unjoined-club-view">
      <view class="unjoined-hero-box">
        <view class="unjoined-badge">🏃 跑团中心</view>
        <text class="unjoined-hero-title">欢迎加入跑团</text>
        <text class="unjoined-hero-sub">请在下方浏览平台所有已创建跑团并选择加入，与队友共同打卡月度挑战、查看团队英雄榜与教练负荷监控！</text>
        <view class="unjoined-btn-row">
          <button class="unjoined-action-btn secondary-invite" @click="showJoinModal = true">
            🔑 输入邀请码加入
          </button>
        </view>
      </view>

      <!-- All Created Clubs List -->
      <view class="section-card all-clubs-sec">
        <view class="sec-title-row">
          <view class="title-left">
            <text class="sec-title">🏆 平台跑团列表</text>
            <text class="count-tag">{{ allClubs.length }} 个跑团</text>
          </view>
          <text class="sec-hint">选择心仪跑团一键加入</text>
        </view>

        <view v-if="allClubs.length === 0" class="empty-clubs-text">
          平台暂无已创建跑团，请联系平台管理员创建！
        </view>

        <view v-else class="clubs-list-wrap">
          <view v-for="club in allClubs" :key="club.id" class="club-select-card">
            <image class="csc-logo" :src="club.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
            <view class="csc-body">
              <view class="csc-title-row">
                <text class="csc-name">{{ club.name }}</text>
                <text class="csc-city">📍 {{ club.city || "上海" }}</text>
              </view>
              <text class="csc-desc">{{ club.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。" }}</text>
              <view class="csc-meta-row">
                <text class="csc-meta">团长: {{ club.owner_name || "平台指定" }}</text>
                <text class="csc-dot">·</text>
                <text class="csc-meta highlight">{{ club.member_count || 1 }} 位成员</text>
              </view>
            </view>
            <button class="csc-join-btn" :loading="joiningClubId === club.id" @click="handleJoinClubDirect(club.id)">
              加入
            </button>
          </view>
        </view>
      </view>

      <view class="section-card unjoined-highlights">
        <text class="unjoined-sec-title">加入跑团即可解锁：</text>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🥇</text>
          <view class="uh-content">
            <text class="uh-title">跑团月度跑量英雄榜</text>
            <text class="uh-desc">自动汇总全体团员月跑量与排名，良性竞逐突破个人 PB</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🏆</text>
          <view class="uh-content">
            <text class="uh-title">专属跑量挑战赛与活动</text>
            <text class="uh-desc">团长发起目标里程挑战，团员打卡达标解锁专属荣誉</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">💬</text>
          <view class="uh-content">
            <text class="uh-title">跑友圈动态与 AI 互动</text>
            <text class="uh-desc">同步跑步记录自动生成 AI 战报与点评，队友点赞留言互勉</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🧢</text>
          <view class="uh-content">
            <text class="uh-title">教练学员体能罗盘</text>
            <text class="uh-desc">科学监控学员 CTL/ATL/TSB 负荷与状态，预防过度训练与伤病</text>
          </view>
        </view>
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


    <!-- ── Join Club Modal (加入跑团弹窗) ── -->
    <view v-if="showJoinModal" class="modal-mask" @click="showJoinModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">加入跑团</text>
          <text class="close-btn" @click="showJoinModal = false">✕</text>
        </view>

        <view class="modal-body">
          <text class="input-label">跑团专属 6 位邀请码</text>
          <input
            class="text-input"
            type="text"
            maxlength="10"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="例如: RGM888"
            v-model="inviteCodeInput"
          />
          <button class="submit-btn" :loading="joiningClub" @click="handleJoinClub">
            立即加入
          </button>
        </view>
      </view>
    </view>

    <!-- ── All Clubs Modal (浏览与切换全部跑团) ── -->
    <view v-if="showAllClubsModal" class="modal-mask" @click="showAllClubsModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">跑团切换与浏览</text>
            <text class="count-pill">{{ userClubs.length }} 个已加入</text>
          </view>
          <text class="close-btn" @click="showAllClubsModal = false">✕</text>
        </view>

        <!-- Segmented Tab Switcher in Modal -->
        <view class="modal-tab-row" v-if="userClubs.length > 0">
          <view
            class="modal-tab-segment"
            :class="{ active: clubModalTab === 'joined' }"
            @click="clubModalTab = 'joined'"
          >
            我的跑团 ({{ userClubs.length }})
          </view>
          <view
            class="modal-tab-segment"
            :class="{ active: clubModalTab === 'all' }"
            @click="clubModalTab = 'all'"
          >
            平台全部 ({{ allClubs.length }})
          </view>
        </view>

        <view class="modal-body modal-scroll">
          <view v-if="displayedClubs.length === 0" class="empty-clubs-text">
            {{ clubModalTab === 'joined' ? '您尚未加入任何跑团，请切换至“平台全部”选择加入！' : '平台暂无其他已创建跑团。' }}
          </view>
          <view v-else class="modal-clubs-list">
            <view
              v-for="c in displayedClubs"
              :key="c.id"
              class="modal-club-card"
              :class="{ 'is-current': currentClub?.id === c.id }"
              @click="c.is_member ? handleSwitchClub(c) : null"
            >
              <image class="mcc-logo" :src="c.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="mcc-info">
                <view class="mcc-name-row">
                  <text class="mcc-name">{{ c.name }}</text>
                  <text class="mcc-city">📍 {{ c.city || '上海' }}</text>
                </view>
                <text class="mcc-desc">{{ c.description || '精英跑者联盟，追求 PB 突破与健康长久奔跑。' }}</text>
                <view class="mcc-meta">
                  <text>团长: {{ c.owner_name || '平台指定' }}</text>
                  <text class="mcc-dot">·</text>
                  <text class="highlight">{{ c.member_count || 1 }} 位成员</text>
                  <text v-if="c.role" class="mcc-role-tag" :class="'role-' + c.role">
                    {{ c.role === 'owner' ? '👑 团长' : c.role === 'coach' ? '🧢 教练' : '🏃 团员' }}
                  </text>
                </view>
              </view>
              <view class="mcc-action" @click.stop>
                <text v-if="currentClub?.id === c.id" class="mcc-current-tag">当前使用中 ✓</text>
                <button
                  v-else-if="c.is_member"
                  class="mcc-switch-btn"
                  @click="handleSwitchClub(c)"
                >
                  ⇄ 切换
                </button>
                <button
                  v-else
                  class="mcc-join-btn"
                  :loading="joiningClubId === c.id"
                  @click="handleJoinClubDirect(c.id)"
                >
                  + 加入
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
import { ref, computed } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import {
  request,
  getStoredUser,
  checkAndAutoLogin,
  UserProfile,
  getActiveClubId,
  setActiveClubId,
  resolveActiveClub,
} from "../../utils/api";

const user = ref<UserProfile | null>(null);
const currentClub = ref<any>(null);
const currentRole = ref("member");

const events = ref<any[]>([]);
const members = ref<any[]>([]);
const coachCockpit = ref<any>(null);

const showMembersModal = ref(false);
const memberSearchQuery = ref("");

const showEventModal = ref(false);
const showJoinModal = ref(false);
const showAllClubsModal = ref(false);

const inviteCodeInput = ref("");
const joiningClub = ref(false);
const joiningClubId = ref<string | null>(null);

const allClubs = ref<any[]>([]);
const userClubs = ref<any[]>([]);
const clubModalTab = ref<"joined" | "all">("joined");

function openAllClubsModal() {
  clubModalTab.value = userClubs.value.length > 0 ? "joined" : "all";
  showAllClubsModal.value = true;
}

const displayedClubs = computed(() => {
  if (clubModalTab.value === "joined") {
    return allClubs.value.filter((c) => c.is_member);
  }
  return allClubs.value;
});

const editingEventId = ref<string | null>(null);
const eventTitle = ref("");
const eventTargetKm = ref<number | string>(200);
const eventRules = ref("");

const savingEvent = ref(false);

function goToRankPage() {
  uni.switchTab({
    url: "/pages/team/rank"
  });
}

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

async function loadClubData(preferredClubId?: string) {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    const [myRes, allRes] = await Promise.all([
      request(`/api/team/my-clubs/${uid}`),
      request(`/api/team/all-clubs?user_id=${uid}`)
    ]);

    const clubs = myRes?.clubs || [];
    userClubs.value = clubs;
    allClubs.value = allRes?.clubs || [];

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

      // Load events, members, coach cockpit
      const [evtRes, memRes, coachRes] = await Promise.all([
        request(`/api/team/${clubId}/events`),
        request(`/api/team/${clubId}/members`),
        request(`/api/team/${clubId}/coach-cockpit?coach_uid=${uid}`),
      ]);

      events.value = evtRes?.events || [];
      members.value = memRes?.members || [];
      coachCockpit.value = coachRes || null;
    } else {
      setActiveClubId("");
      currentClub.value = null;
      currentRole.value = "member";
      events.value = [];
      members.value = [];
      coachCockpit.value = null;
    }
  } catch (e) {
    console.warn("Load club data error:", e);
  }
}

function handleSwitchClub(club: any) {
  if (!club || !club.id) return;
  setActiveClubId(club.id);
  showAllClubsModal.value = false;
  uni.showToast({
    title: `已切换至【${club.name}】`,
    icon: "success"
  });
  loadClubData(club.id);
}

async function handleJoinClubDirect(clubId: string) {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  joiningClubId.value = clubId;
  try {
    const res = await request("/api/team/join-club", "POST", {
      user_id: uid,
      club_id: clubId,
    });
    setActiveClubId(clubId);
    showAllClubsModal.value = false;
    uni.showToast({ title: res?.message || "加入跑团成功！", icon: "success" });
    await loadClubData(clubId);
  } catch (e: any) {
    uni.showToast({ title: e?.message || "加入失败", icon: "none" });
  } finally {
    joiningClubId.value = null;
  }
}

async function handleJoinClub() {
  if (!inviteCodeInput.value.trim()) {
    uni.showToast({ title: "请输入邀请码", icon: "none" });
    return;
  }
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  joiningClub.value = true;
  try {
    const res = await request("/api/team/join", "POST", {
      user_id: uid,
      invite_code: inviteCodeInput.value.trim().toUpperCase(),
    });
    uni.showToast({ title: res?.message || "加入成功！", icon: "success" });
    showJoinModal.value = false;
    inviteCodeInput.value = "";
    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: e.message || "加入失败，请核对邀请码", icon: "none" });
  } finally {
    joiningClub.value = false;
  }
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

/* ── 跑团英雄榜与动态直通卡 ── */
.rank-banner-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(255, 159, 10, 0.08) 100%);
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(252, 76, 2, 0.12);
  transition: all 0.2s ease;
}

.rank-banner-card:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.banner-left {
  flex: 1;
  min-width: 0;
}

.banner-badge-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.banner-badge {
  font-size: 20rpx;
  font-weight: bold;
  color: #fc4c02;
  background-color: rgba(252, 76, 2, 0.18);
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
}

.banner-hint-pill {
  font-size: 18rpx;
  color: #ff9f0a;
  background-color: rgba(255, 159, 10, 0.15);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.banner-title {
  font-size: 28rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
  margin-bottom: 4rpx;
}

.banner-desc {
  font-size: 20rpx;
  color: #a1a1aa;
  display: block;
  line-height: 1.4;
}

.banner-arrow-box {
  width: 56rpx;
  height: 56rpx;
  border-radius: 28rpx;
  background-color: rgba(252, 76, 2, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 16rpx;
}

.banner-arrow {
  font-size: 32rpx;
  color: #fc4c02;
  font-weight: bold;
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

/* Unjoined State Styles */
.unjoined-club-view {
  display: flex;
  flex-direction: column;
  gap: 30rpx;
}

.unjoined-hero-box {
  background: linear-gradient(135deg, #18181c 0%, #121215 100%);
  border-radius: 36rpx;
  padding: 50rpx 40rpx;
  text-align: center;
  border: 1rpx solid rgba(252, 76, 2, 0.25);
  box-shadow: 0 16rpx 40rpx rgba(0, 0, 0, 0.4);
}

.unjoined-badge {
  display: inline-block;
  font-size: 22rpx;
  font-weight: bold;
  color: #fc4c02;
  background: rgba(252, 76, 2, 0.15);
  padding: 6rpx 20rpx;
  border-radius: 20rpx;
  margin-bottom: 24rpx;
}

.unjoined-hero-title {
  font-size: 38rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
  margin-bottom: 16rpx;
}

.unjoined-hero-sub {
  font-size: 24rpx;
  color: #8e8e93;
  line-height: 1.6;
  display: block;
  margin-bottom: 40rpx;
  padding: 0 10rpx;
}

.unjoined-btn-row {
  display: flex;
  gap: 20rpx;
  justify-content: center;
}

.unjoined-action-btn {
  flex: 1;
  height: 84rpx;
  line-height: 84rpx;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 24rpx;
  border: none;
}

.unjoined-action-btn.primary-join {
  background: #fc4c02;
  color: #ffffff;
  box-shadow: 0 8rpx 20rpx rgba(252, 76, 2, 0.3);
}

.unjoined-action-btn.secondary-invite {
  background: #242429;
  color: #ffffff;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.browse-all-btn {
  display: inline-flex;
  align-items: center;
  margin-top: 14rpx;
  padding: 8rpx 18rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 20rpx;
}

.browse-text {
  font-size: 22rpx;
  color: #a1a1aa;
  font-weight: 500;
}

/* 平台所有跑团列表 */
.all-clubs-sec {
  margin-top: 24rpx;
}

.sec-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.count-tag {
  font-size: 20rpx;
  background: rgba(252, 76, 2, 0.15);
  color: #fc4c02;
  padding: 2rpx 12rpx;
  border-radius: 12rpx;
  font-weight: bold;
}

.sec-hint {
  font-size: 22rpx;
  color: #71717a;
}

.empty-clubs-text {
  text-align: center;
  padding: 40rpx 20rpx;
  font-size: 24rpx;
  color: #71717a;
}

.clubs-list-wrap {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.club-select-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 20rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
}

.csc-logo {
  width: 90rpx;
  height: 90rpx;
  border-radius: 18rpx;
  flex-shrink: 0;
}

.csc-body {
  flex: 1;
  min-width: 0;
}

.csc-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6rpx;
}

.csc-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.csc-city {
  font-size: 20rpx;
  color: #a1a1aa;
  flex-shrink: 0;
}

.csc-desc {
  font-size: 22rpx;
  color: #71717a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 8rpx;
  display: block;
}

.csc-meta-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.csc-meta {
  font-size: 20rpx;
  color: #a1a1aa;
}

.csc-meta.highlight {
  color: #fc4c02;
  font-weight: bold;
}

.csc-dot {
  font-size: 20rpx;
  color: #52525b;
}

.csc-join-btn {
  background: #fc4c02;
  color: #ffffff;
  font-size: 24rpx;
  font-weight: bold;
  padding: 0 28rpx;
  height: 60rpx;
  line-height: 60rpx;
  border-radius: 14rpx;
  border: none;
  flex-shrink: 0;
  margin: 0;
}

/* 弹窗中的所有跑团列表 */
.modal-scroll {
  max-height: 65vh;
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
  width: 80rpx;
  height: 80rpx;
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
  margin-bottom: 4rpx;
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
  flex-shrink: 0;
}

.mcc-desc {
  font-size: 20rpx;
  color: #71717a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 6rpx;
  display: block;
}

.mcc-meta {
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 20rpx;
  color: #a1a1aa;
}

.mcc-meta .highlight {
  color: #fc4c02;
  font-weight: bold;
}

.mcc-dot {
  font-size: 20rpx;
  color: #52525b;
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

.mcc-join-btn {
  background: #fc4c02;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: bold;
  padding: 0 24rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 12rpx;
  border: none;
  margin: 0;
}

/* 顶部横向跑团切换条 */
.clubs-switcher-wrap {
  margin-bottom: 24rpx;
}

.clubs-switcher-scroll {
  width: 100%;
  white-space: nowrap;
}

.clubs-switcher-inner {
  display: inline-flex;
  align-items: center;
  gap: 16rpx;
  padding: 4rpx 2rpx;
}

.club-tab-pill {
  display: inline-flex;
  align-items: center;
  gap: 12rpx;
  background: rgba(255, 255, 255, 0.05);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  padding: 10rpx 20rpx;
  border-radius: 30rpx;
  transition: all 0.2s ease;
}

.club-tab-pill.active {
  background: rgba(252, 76, 2, 0.18);
  border-color: #fc4c02;
  box-shadow: 0 4rpx 14rpx rgba(252, 76, 2, 0.25);
}

.tab-club-logo {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
}

.tab-club-name {
  font-size: 24rpx;
  font-weight: bold;
  color: #d4d4d8;
  max-width: 220rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.club-tab-pill.active .tab-club-name {
  color: #ffffff;
}

.tab-active-check {
  font-size: 22rpx;
  color: #fc4c02;
  font-weight: 900;
}

.club-tab-pill.tab-browse-btn {
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx dashed rgba(255, 255, 255, 0.2);
}

.tab-browse-icon {
  font-size: 22rpx;
  color: #a1a1aa;
}

/* 弹窗分栏标签 */
.modal-tab-row {
  display: flex;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 6rpx;
  margin: 0 30rpx 20rpx 30rpx;
  gap: 8rpx;
}

.modal-tab-segment {
  flex: 1;
  text-align: center;
  font-size: 24rpx;
  font-weight: bold;
  color: #a1a1aa;
  padding: 12rpx 0;
  border-radius: 16rpx;
  transition: all 0.2s ease;
}

.modal-tab-segment.active {
  background: #27272a;
  color: #fc4c02;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.3);
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

.unjoined-highlights {
  padding: 36rpx;
}

.unjoined-sec-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
  margin-bottom: 30rpx;
  display: block;
}

.unjoined-highlight-item {
  display: flex;
  align-items: flex-start;
  gap: 24rpx;
  margin-bottom: 32rpx;
}

.unjoined-highlight-item:last-child {
  margin-bottom: 0;
}

.uh-icon {
  font-size: 38rpx;
  line-height: 1;
  margin-top: 4rpx;
}

.uh-content {
  flex: 1;
}

.uh-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
  margin-bottom: 6rpx;
  display: block;
}

.uh-desc {
  font-size: 22rpx;
  color: #8e8e93;
  line-height: 1.5;
  display: block;
}
</style>
