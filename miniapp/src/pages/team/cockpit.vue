<template>
  <view class="cockpit-page">
    <!-- ── Permission Check: Only Owner / Coach ── -->
    <view v-if="!loading && !isAuthorized" class="unauthorized-card">
      <text class="lock-icon">🔒</text>
      <text class="unauth-title">访问受限</text>
      <text class="unauth-desc">
        教练体能监控罗盘仅对【跑团主理人】与【认证教练】开放，用于全队跑者的负荷跟踪与伤病风险预防。
      </text>
      <button class="back-btn" @click="goBack">返回跑团页面</button>
    </view>

    <!-- ── Authorized Cockpit View ── -->
    <view v-else-if="!loading" class="cockpit-content">
      <!-- Top Club Header -->
      <view class="top-club-bar">
        <view class="club-info" @click="userClubs.length > 1 ? (showSwitchModal = true) : null">
          <view class="title-with-arrow">
            <text class="club-title">{{ currentClub?.name || "跑团罗盘" }}</text>
            <text v-if="userClubs.length > 1" class="switch-arrow">▾</text>
          </view>
          <text class="sub-text">全队跑者生理负荷、疲劳与跑量监控罗盘</text>
        </view>
        <view class="top-right-group">
          <text class="role-badge" :class="'role-' + userRole">
            {{ userRole === 'owner' ? '👑 跑团主理人' : '🧢 认证教练' }}
          </text>
          <text v-if="userClubs.length > 1" class="switch-link-pill" @click="showSwitchModal = true">
            ⇄ 切换
          </text>
        </view>
      </view>

      <!-- 4-Grid Status Overview -->
      <view class="status-summary-grid">
        <view
          class="status-card green"
          :class="{ active: filterStatus === 'peak' }"
          @click="setFilter('peak')"
        >
          <view class="status-top">
            <text class="status-dot">🟢</text>
            <text class="status-name">巅峰状态</text>
          </view>
          <text class="status-count">{{ summary?.peak_count || 0 }} <text class="unit">人</text></text>
          <text class="status-desc">TSB +5以上 · 适宜测速与比赛</text>
        </view>

        <view
          class="status-card blue"
          :class="{ active: filterStatus === 'optimal' }"
          @click="setFilter('optimal')"
        >
          <view class="status-top">
            <text class="status-dot">🔵</text>
            <text class="status-name">专项适应</text>
          </view>
          <text class="status-count">{{ summary?.optimal_count || 0 }} <text class="unit">人</text></text>
          <text class="status-desc">TSB -30~+5 · 推进主课</text>
        </view>

        <view
          class="status-card yellow"
          :class="{ active: filterStatus === 'tired' }"
          @click="setFilter('tired')"
        >
          <view class="status-top">
            <text class="status-dot">🟡</text>
            <text class="status-name">疲劳积累</text>
          </view>
          <text class="status-count">{{ summary?.tired_count || 0 }} <text class="unit">人</text></text>
          <text class="status-desc">TSB -50~-30 · 穿插排酸</text>
        </view>

        <view
          class="status-card red"
          :class="{ active: filterStatus === 'danger' }"
          @click="setFilter('danger')"
        >
          <view class="status-top">
            <text class="status-dot">🔴</text>
            <text class="status-name">伤病预警</text>
          </view>
          <text class="status-count">{{ summary?.danger_count || 0 }} <text class="unit">人</text></text>
          <text class="status-desc">TSB -50以下 · 强制休整</text>
        </view>
      </view>

      <!-- Search & Filter Bar -->
      <view class="search-filter-bar">
        <input
          class="student-search-input"
          type="text"
          :adjust-position="false"
          :cursor-spacing="30"
          placeholder="🔍 搜索学员姓名 / 账号..."
          v-model="searchQuery"
        />
        <view class="filter-chip-row">
          <view
            class="filter-chip"
            :class="{ active: filterStatus === 'all' }"
            @click="setFilter('all')"
          >
            全部成员 ({{ students.length }})
          </view>
          <view
            v-if="filterStatus !== 'all'"
            class="clear-filter"
            @click="setFilter('all')"
          >
            ✕ 重置
          </view>
        </view>
      </view>

      <!-- Student Cards List -->
      <view class="students-list">
        <view
          v-for="s in filteredStudents"
          :key="s.user_id"
          class="student-card"
          :class="'border-' + s.status_level"
        >
          <!-- Student Top Row -->
          <view class="student-header">
            <view class="student-profile">
              <image
                class="student-avatar"
                :src="s.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                mode="aspectFill"
              />
              <view class="student-name-box">
                <view class="name-row">
                  <text class="student-name">{{ s.display_name }}</text>
                  <text v-if="s.role === 'owner'" class="mini-tag owner">团长</text>
                  <text v-else-if="s.role === 'coach'" class="mini-tag coach">教练</text>
                </view>
                <text class="student-month-km">9月累计跑量: <text class="highlight">{{ s.month_km }} km</text></text>
              </view>
            </view>

            <!-- Status Level Badge -->
            <view class="status-badge" :class="'badge-' + s.status_level">
              {{ s.status_level === 'peak' ? '🟢 巅峰' : s.status_level === 'optimal' ? '🔵 适应' : s.status_level === 'tired' ? '🟡 疲劳' : '🔴 预警' }}
            </view>
          </view>

          <!-- Metrics 6-Grid -->
          <view class="metrics-grid">
            <view class="metric-cell">
              <text class="m-label">CTL 体能</text>
              <text class="m-val text-blue">{{ s.ctl }}</text>
            </view>
            <view class="metric-cell">
              <text class="m-label">ATL 疲劳</text>
              <text class="m-val text-purple">{{ s.atl }}</text>
            </view>
            <view class="metric-cell">
              <text class="m-label">TSB 状况</text>
              <text class="m-val" :class="s.ctl > 0 || s.atl > 0 ? (s.tsb >= 0 ? 'text-green' : 'text-yellow') : 'text-muted'">
                {{ (s.ctl > 0 || s.atl > 0) ? (s.tsb > 0 ? '+' + s.tsb : s.tsb) : '—' }}
              </text>
            </view>
            <view class="metric-cell">
              <text class="m-label">静息心率</text>
              <text class="m-val text-rose">{{ s.resting_heart_rate ? s.resting_heart_rate : '—' }} <text class="m-unit" v-if="s.resting_heart_rate">bpm</text></text>
            </view>
            <view class="metric-cell">
              <text class="m-label">夜间 HRV</text>
              <text class="m-val text-cyan">{{ s.hrv_ms ? s.hrv_ms : '—' }} <text class="m-unit" v-if="s.hrv_ms">ms</text></text>
            </view>
            <view class="metric-cell">
              <text class="m-label">睡眠恢复</text>
              <text class="m-val text-emerald">{{ s.sleep_score ? s.sleep_score : '—' }} <text class="m-unit" v-if="s.sleep_score">分</text></text>
            </view>
          </view>

          <!-- Coach Advice Box -->
          <view class="advice-box">
            <text class="advice-icon">💡</text>
            <text class="advice-text">{{ s.status_text }}</text>
          </view>

          <!-- Owner Role Action Row -->
          <view v-if="userRole === 'owner' && s.role !== 'owner'" class="card-role-bar">
            <text class="role-bar-tip">团长管理：</text>
            <button
              v-if="s.role !== 'coach'"
              class="role-mini-btn coach"
              @click="handleAssignRole(s.user_id, 'coach')"
            >
              🧢 指定为认证教练
            </button>
            <button
              v-else
              class="role-mini-btn member"
              @click="handleAssignRole(s.user_id, 'member')"
            >
              🏃 恢复普通团员
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── Switch Club Modal (教练切换管理的跑团) ── -->
    <view v-if="showSwitchModal" class="modal-mask" @click="showSwitchModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">切换体能罗盘跑团</text>
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
                <text v-if="currentClub?.id === c.id" class="mcc-current-tag">当前罗盘 ✓</text>
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
const userRole = ref("member");
const userClubs = ref<any[]>([]);
const showSwitchModal = ref(false);
const loading = ref(true);

const summary = ref<any>(null);
const students = ref<any[]>([]);
const filterStatus = ref("all");
const searchQuery = ref("");

const isAuthorized = computed(() => {
  if (!user.value || !currentClub.value) return false;
  return (
    userRole.value === "owner" ||
    userRole.value === "coach" ||
    currentClub.value.owner_id === user.value.id
  );
});

const filteredStudents = computed(() => {
  let list = students.value;
  if (filterStatus.value !== "all") {
    list = list.filter((s) => s.status_level === filterStatus.value);
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase();
    list = list.filter(
      (s) =>
        (s.display_name || "").toLowerCase().includes(q) ||
        (s.user_id || "").toLowerCase().includes(q)
    );
  }
  return list;
});

function setFilter(status: string) {
  if (filterStatus.value === status) {
    filterStatus.value = "all";
  } else {
    filterStatus.value = status;
  }
}

function goBack() {
  uni.navigateBack();
}

async function loadCockpitData(preferredClubId?: string) {
  loading.value = true;
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) {
    loading.value = false;
    return;
  }
  const uid = user.value.id;

  try {
    const clubRes = await request(`/api/team/my-clubs/${uid}`);
    const clubs = clubRes?.clubs || [];
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
      userRole.value = targetClub.role || "member";
      const clubId = targetClub.id;

      const res = await request(`/api/team/${clubId}/coach-cockpit?coach_uid=${uid}`);
      summary.value = res?.summary || null;
      students.value = res?.students || [];
    } else {
      setActiveClubId("");
      currentClub.value = null;
      userRole.value = "member";
      summary.value = null;
      students.value = [];
    }
  } catch (err) {
    console.error("Load cockpit error:", err);
  } finally {
    loading.value = false;
  }
}

function handleSwitchClub(club: any) {
  if (!club || !club.id) return;
  setActiveClubId(club.id);
  showSwitchModal.value = false;
  uni.showToast({
    title: `已切换至【${club.name}】罗盘`,
    icon: "success",
  });
  loadCockpitData(club.id);
}

async function handleAssignRole(targetUid: string, role: string) {
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
      title: `已成功设为【${role === "coach" ? "认证教练" : "普通团员"}】`,
      icon: "success",
    });
    await loadCockpitData();
  } catch (e: any) {
    uni.showToast({ title: e.message || "设置失败", icon: "none" });
  }
}

onShow(() => {
  loadCockpitData();
});

onPullDownRefresh(async () => {
  try {
    await loadCockpitData();
    uni.showToast({ title: "罗盘数据已刷新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});
</script>

<style scoped>
.cockpit-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
}

.unauthorized-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 69, 58, 0.2);
  border-radius: 32rpx;
  padding: 60rpx 40rpx;
  text-align: center;
  margin-top: 100rpx;
}

.lock-icon {
  font-size: 64rpx;
  margin-bottom: 20rpx;
  display: block;
}

.unauth-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #ff453a;
  display: block;
  margin-bottom: 16rpx;
}

.unauth-desc {
  font-size: 24rpx;
  color: #8e8e93;
  line-height: 1.5;
  margin-bottom: 30rpx;
  display: block;
}

.back-btn {
  background-color: #242429;
  color: #ffffff;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 76rpx;
  line-height: 76rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.top-club-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #1c1c20 0%, #131316 100%);
  border: 1rpx solid rgba(191, 90, 242, 0.3);
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
}

.title-with-arrow {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.switch-arrow {
  font-size: 24rpx;
  color: #bf5af2;
}

.top-right-group {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.switch-link-pill {
  font-size: 20rpx;
  color: #bf5af2;
  font-weight: bold;
  background: rgba(191, 90, 242, 0.15);
  border: 1rpx solid rgba(191, 90, 242, 0.3);
  padding: 6rpx 14rpx;
  border-radius: 12rpx;
}

.club-title {
  font-size: 30rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
}

/* Modal styles for cockpit.vue */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: flex-end;
  z-index: 999;
  backdrop-filter: blur(4px);
}

.modal-content {
  width: 100%;
  background-color: #161619;
  border-radius: 36rpx 36rpx 0 0;
  padding: 36rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.title-with-pill {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.modal-title {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
}

.count-pill {
  font-size: 20rpx;
  color: #bf5af2;
  background: rgba(191, 90, 242, 0.15);
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
  font-weight: bold;
}

.close-btn {
  font-size: 36rpx;
  color: #71717a;
  padding: 10rpx;
}

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
  border-color: rgba(191, 90, 242, 0.4);
  background: rgba(191, 90, 242, 0.06);
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
  color: #bf5af2;
  font-weight: bold;
  padding: 6rpx 16rpx;
  background: rgba(191, 90, 242, 0.15);
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

.sub-text {
  font-size: 20rpx;
  color: #bf5af2;
  margin-top: 4rpx;
  display: block;
}

.role-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 6rpx 16rpx;
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

/* 4 Status Grid */
.status-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.status-card {
  background-color: #151518;
  border-radius: 24rpx;
  padding: 20rpx;
  border: 2rpx solid transparent;
  transition: all 0.2s;
}

.status-card.active {
  background-color: #1f1f24;
}

.status-card.green { border-color: rgba(48, 209, 88, 0.3); }
.status-card.green.active { border-color: #30d158; box-shadow: 0 0 16rpx rgba(48, 209, 88, 0.3); }

.status-card.blue { border-color: rgba(10, 132, 255, 0.3); }
.status-card.blue.active { border-color: #0a84ff; box-shadow: 0 0 16rpx rgba(10, 132, 255, 0.3); }

.status-card.yellow { border-color: rgba(255, 214, 10, 0.3); }
.status-card.yellow.active { border-color: #ffd60a; box-shadow: 0 0 16rpx rgba(255, 214, 10, 0.3); }

.status-card.red { border-color: rgba(255, 69, 58, 0.3); }
.status-card.red.active { border-color: #ff453a; box-shadow: 0 0 16rpx rgba(255, 69, 58, 0.3); }

.status-top {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.status-dot {
  font-size: 20rpx;
}

.status-name {
  font-size: 24rpx;
  font-weight: bold;
  color: #ffffff;
}

.status-count {
  font-size: 36rpx;
  font-weight: 900;
  color: #ffffff;
  margin-top: 6rpx;
  display: block;
}

.status-count .unit {
  font-size: 20rpx;
  font-weight: normal;
  color: #8e8e93;
}

.status-desc {
  font-size: 18rpx;
  color: #8e8e93;
  margin-top: 6rpx;
  display: block;
}

/* Search & Filter Bar */
.search-filter-bar {
  margin-bottom: 20rpx;
}

.student-search-input {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 18rpx;
  height: 76rpx;
  padding: 0 24rpx;
  font-size: 24rpx;
  color: #ffffff;
  margin-bottom: 14rpx;
}

.filter-chip-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.filter-chip {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  color: #8e8e93;
  font-size: 22rpx;
  padding: 8rpx 20rpx;
  border-radius: 14rpx;
}

.filter-chip.active {
  background-color: #bf5af2;
  color: #ffffff;
  font-weight: bold;
  border-color: #bf5af2;
}

.clear-filter {
  font-size: 20rpx;
  color: #ff453a;
}

/* Student Cards */
.students-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.student-card {
  background-color: #151518;
  border-radius: 24rpx;
  padding: 24rpx;
  border-left: 8rpx solid transparent;
}

.student-card.border-peak { border-left-color: #30d158; }
.student-card.border-optimal { border-left-color: #0a84ff; }
.student-card.border-tired { border-left-color: #ffd60a; }
.student-card.border-danger { border-left-color: #ff453a; }

.student-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
}

.student-profile {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.student-avatar {
  width: 76rpx;
  height: 76rpx;
  border-radius: 38rpx;
}

.student-name-box {
  display: flex;
  flex-direction: column;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.student-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.mini-tag {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
}

.mini-tag.owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: #ff9f0a;
}

.mini-tag.coach {
  background-color: rgba(191, 90, 242, 0.2);
  color: #bf5af2;
}

.student-month-km {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
}

.student-month-km .highlight {
  color: #fc4c02;
  font-weight: bold;
}

.status-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
}

.badge-peak { background: rgba(48, 209, 88, 0.2); color: #30d158; }
.badge-optimal { background: rgba(10, 132, 255, 0.2); color: #0a84ff; }
.badge-tired { background: rgba(255, 214, 10, 0.2); color: #ffd60a; }
.badge-danger { background: rgba(255, 69, 58, 0.2); color: #ff453a; }

/* 6-Grid Metrics */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  background-color: #1c1c20;
  border-radius: 18rpx;
  padding: 16rpx;
  margin-bottom: 16rpx;
}

.metric-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.m-label {
  font-size: 18rpx;
  color: #8e8e93;
}

.m-val {
  font-size: 26rpx;
  font-weight: 900;
  margin-top: 4rpx;
  font-family: monospace;
}

.m-unit {
  font-size: 16rpx;
  font-weight: normal;
  color: #8e8e93;
}

.text-blue { color: #0a84ff; }
.text-purple { color: #bf5af2; }
.text-green { color: #30d158; }
.text-yellow { color: #ffd60a; }
.text-rose { color: #ff375f; }
.text-cyan { color: #64d2ff; }
.text-emerald { color: #30d158; }

.advice-box {
  display: flex;
  gap: 12rpx;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 14rpx;
  padding: 14rpx 16rpx;
}

.advice-icon {
  font-size: 22rpx;
}

.advice-text {
  font-size: 20rpx;
  color: #d1d1d6;
  line-height: 1.4;
  flex: 1;
}

.card-role-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12rpx;
  margin-top: 16rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
}

.role-bar-tip {
  font-size: 20rpx;
  color: #8e8e93;
}

.role-mini-btn {
  font-size: 20rpx;
  font-weight: bold;
  height: 48rpx;
  line-height: 48rpx;
  border-radius: 12rpx;
  padding: 0 16rpx;
  border: none;
}

.role-mini-btn.coach {
  background: rgba(191, 90, 242, 0.25);
  color: #bf5af2;
}

.role-mini-btn.member {
  background: rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}
</style>
