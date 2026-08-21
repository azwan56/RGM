<template>
  <view class="profile-page">
    <!-- User Card -->
    <view class="user-card" @click="!user?.id && (showAuthModal = true)">
      <image class="avatar" :src="user?.avatar_url || '/static/default_avatar.png'" mode="aspectFill" />
      <view class="user-meta">
        <text class="user-name">{{ user?.display_name || "点击登录" }}</text>
        <text class="user-id">{{ user?.id ? `ID: ${user.id.substring(0, 10)}` : "未登录 / 点击登录或切换账号" }}</text>
      </view>
    </view>

    <!-- Garmin Connection Status Card -->
    <view class="section-card">
      <view class="card-title-row">
        <text class="card-title">Garmin (佳明) 数据直连</text>
        <text class="conn-status" :class="{ connected: garminConnected }">
          {{ garminConnected ? "已连接 ✓" : "未连接" }}
        </text>
      </view>

      <text class="desc-text">
        {{ garminConnected
            ? `已绑定佳明账号：${garminEmail} (${garminDomain})`
            : "连接佳明账号后，系统将自动同步手表中的所有跑步、心率、睡眠与体能指标。" }}
      </text>

      <button
        v-if="!garminConnected"
        class="garmin-btn"
        @click="showGarminModal = true"
      >
        绑定佳明账号
      </button>

      <button
        v-else
        class="unbind-btn"
        :loading="unbinding"
        @click="handleUnbindGarmin"
      >
        解除佳明绑定
      </button>
    </view>

    <!-- ── CARD 1: 比赛计划 (Race Plans) ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🏁</text>
          <text class="card-title">比赛计划与倒计时</text>
        </view>
      </view>

      <view v-if="races.length" class="race-list">
        <view v-for="(race, idx) in races" :key="race.id || idx" class="race-item">
          <view class="race-top">
            <text class="race-name">{{ race.name }}</text>
            <view class="race-badge" :class="{ urgent: race.days_left < 30 }">
              <text class="badge-text">{{ race.days_left }} 天{{ race.days_left < 30 ? " 冲刺" : "" }}</text>
            </view>
          </view>
          <view class="race-meta-row">
            <text class="race-type-tag">{{ race.race_type }}</text>
            <text class="race-date">{{ race.race_date }}</text>
            <text class="race-target">目标: {{ race.target_time }}</text>
          </view>
        </view>
      </view>
      <view v-else class="empty-race">
        <text class="desc-text">暂无比赛计划，可在网页端控制台添加赛事。</text>
      </view>
    </view>

    <!-- ── CARD 2: 个人最佳成绩 (PB) - 从 Garmin 导入 ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">⚡</text>
          <text class="card-title">个人最佳成绩 (PB)</text>
        </view>
        <button
          class="import-garmin-btn"
          :loading="importingGarmin"
          :disabled="importingGarmin"
          @click="handleImportGarminPb"
        >
          从 Garmin 导入
        </button>
      </view>

      <view class="pb-grid">
        <view class="pb-item">
          <text class="pb-label">全马 (42.195k)</text>
          <text class="pb-val">{{ formatSecs(profile?.marathon_pb) }}</text>
        </view>
        <view class="pb-item">
          <text class="pb-label">半马 (21.0975k)</text>
          <text class="pb-val">{{ formatSecs(profile?.half_pb) }}</text>
        </view>
        <view class="pb-item">
          <text class="pb-label">10公里</text>
          <text class="pb-val">{{ formatSecs(profile?.ten_k_pb) }}</text>
        </view>
        <view class="pb-item">
          <text class="pb-label">5公里</text>
          <text class="pb-val">{{ formatSecs(profile?.five_k_pb) }}</text>
        </view>
      </view>
    </view>

    <!-- Logout / Switch Account Action -->
    <view class="logout-box">
      <button class="logout-btn" @click="handleLogout">退出登录 / 切换账号</button>
    </view>

    <!-- Large & Modern Login / Switch Account Modal -->
    <view v-if="showAuthModal" class="modal-mask" @click="showAuthModal = false">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">登录 / 切换账号</text>
          <view class="close-hit" @click="showAuthModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="modal-body">
          <view class="auth-tabs">
            <view
              class="auth-tab"
              :class="{ active: authTab === 'email' }"
              @click="authTab = 'email'"
            >
              网页邮箱登录
            </view>
            <view
              class="auth-tab"
              :class="{ active: authTab === 'wechat' }"
              @click="authTab = 'wechat'"
            >
              微信一键登录
            </view>
          </view>

          <!-- Email Login Tab -->
          <view v-if="authTab === 'email'" class="tab-pane">
            <text class="auth-desc">输入网页端注册的邮箱与密码，即可一键同步已绑定的 Garmin 国际版数据与训练周报</text>
            
            <text class="field-label">账号邮箱</text>
            <input
              class="large-input"
              type="text"
              placeholder="请输入账号邮箱"
              placeholder-class="placeholder-style"
              v-model="loginEmail"
            />

            <text class="field-label">登录密码</text>
            <input
              class="large-input"
              type="password"
              placeholder="请输入登录密码"
              placeholder-class="placeholder-style"
              v-model="loginPassword"
            />

            <button class="large-primary-btn" :loading="loggingIn" @click="handleEmailLogin">
              立即登录
            </button>
          </view>

          <!-- WeChat Login Tab -->
          <view v-else class="tab-pane">
            <text class="auth-desc">使用当前微信账号快速授权，即刻开启独立运动管理</text>
            <button class="large-wx-btn" :loading="loggingIn" @click="handleWxLogin">
              🟢 微信一键快速登录
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- Large & Modern Garmin Bind Modal -->
    <view v-if="showGarminModal" class="modal-mask" @click="showGarminModal = false">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">绑定 Garmin 佳明账号</text>
          <view class="close-hit" @click="showGarminModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="modal-body">
          <text class="field-label">佳明账号所属区域</text>
          <view class="domain-selector">
            <view
              class="domain-btn"
              :class="{ active: inputDomain === 'garmin.com' }"
              @click="inputDomain = 'garmin.com'"
            >
              国际版 (garmin.com)
            </view>
            <view
              class="domain-btn"
              :class="{ active: inputDomain === 'garmin.cn' }"
              @click="inputDomain = 'garmin.cn'"
            >
              中国版 (garmin.cn)
            </view>
          </view>

          <text class="field-label">佳明注册邮箱 / 账号</text>
          <input
            class="large-input"
            type="text"
            placeholder="例如 user@example.com"
            placeholder-class="placeholder-style"
            v-model="inputEmail"
          />

          <text class="field-label">佳明登录密码</text>
          <input
            class="large-input"
            type="password"
            placeholder="请输入您的 Garmin Connect 密码"
            placeholder-class="placeholder-style"
            v-model="inputPassword"
          />

          <button class="large-primary-btn" :loading="binding" @click="handleBindGarmin">
            确认连接并立即同步
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { request, getStoredUser, clearSession, wechatLogin, emailLogin, UserProfile } from "../../utils/api";

const defaultProfile = {
  marathon_pb: 0,
  half_pb: 0,
  ten_k_pb: 0,
  five_k_pb: 0,
  garmin_connected: false,
  garmin_email: "",
  garmin_domain: "garmin.cn",
};

const user = ref<UserProfile | null>(null);
const profile = ref<any>(defaultProfile);
const races = ref<any[]>([]);

const garminConnected = ref(false);
const garminEmail = ref("");
const garminDomain = ref("garmin.cn");

const showAuthModal = ref(false);
const authTab = ref<"email" | "wechat">("email");
const loginEmail = ref("");
const loginPassword = ref("");
const loggingIn = ref(false);

const showGarminModal = ref(false);
const inputEmail = ref("");
const inputPassword = ref("");
const inputDomain = ref("garmin.cn");
const binding = ref(false);
const unbinding = ref(false);
const importingGarmin = ref(false);

async function loadProfileData() {
  user.value = getStoredUser();
  if (!user.value || !user.value.id) {
    garminConnected.value = false;
    garminEmail.value = "";
    garminDomain.value = "garmin.cn";
    return;
  }

  try {
    const res = await request(`/api/profile/${user.value.id}`);
    if (res?.profile) {
      profile.value = res.profile;
      garminConnected.value = !!res.profile.garmin_connected;
      garminEmail.value = res.profile.garmin_email || "";
      garminDomain.value = res.profile.garmin_domain || "garmin.cn";
      inputDomain.value = garminDomain.value;
    } else {
      garminConnected.value = false;
    }
    if (res?.races) {
      races.value = res.races;
    }
  } catch (e) {
    console.error("Fetch profile failed:", e);
  }
}

async function handleImportGarminPb() {
  if (!user.value || !user.value.id) {
    uni.showToast({ title: "请先登录", icon: "none" });
    showAuthModal.value = true;
    return;
  }
  if (!garminConnected.value) {
    uni.showToast({ title: "请先绑定佳明账号", icon: "none" });
    return;
  }

  importingGarmin.value = true;
  uni.showLoading({ title: "同步 Garmin PR..." });
  try {
    const res = await request(`/api/profile/${user.value.id}/import-garmin-pb`, "POST");
    uni.hideLoading();
    if (res?.success) {
      uni.showToast({ title: "PB 同步成功！", icon: "success" });
      await loadProfileData();
    } else {
      uni.showToast({ title: res?.detail || "导入失败", icon: "none" });
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: e?.message || "导入失败", icon: "none" });
  } finally {
    importingGarmin.value = false;
  }
}

async function handleEmailLogin() {
  if (!loginEmail.value.trim() || !loginPassword.value.trim()) {
    uni.showToast({ title: "请输入邮箱和密码", icon: "none" });
    return;
  }
  loggingIn.value = true;
  try {
    const u = await emailLogin(loginEmail.value.trim(), loginPassword.value.trim());
    user.value = u;
    showAuthModal.value = false;
    uni.showToast({ title: "登录成功", icon: "success" });
    await loadProfileData();
  } catch (e: any) {
    uni.showModal({
      title: "登录失败",
      content: e?.message || "邮箱或密码错误",
      showCancel: false,
    });
  } finally {
    loggingIn.value = false;
  }
}

async function handleWxLogin() {
  loggingIn.value = true;
  try {
    const u = await wechatLogin();
    user.value = u;
    showAuthModal.value = false;
    uni.showToast({ title: "登录成功", icon: "success" });
    await loadProfileData();
  } catch (e: any) {
    uni.showModal({
      title: "微信登录失败",
      content: e?.message || "无法获取微信授权",
      showCancel: false,
    });
  } finally {
    loggingIn.value = false;
  }
}

async function handleBindGarmin() {
  if (!user.value || !user.value.id) {
    uni.showToast({ title: "请先登录账号", icon: "none" });
    showGarminModal.value = false;
    showAuthModal.value = true;
    return;
  }
  if (!inputEmail.value.trim() || !inputPassword.value.trim()) {
    uni.showToast({ title: "请输入佳明账号与密码", icon: "none" });
    return;
  }
  binding.value = true;
  uni.showLoading({ title: "正在连接佳明..." });
  try {
    const res = await request("/api/auth/garmin/bind", "POST", {
      uid: user.value.id,
      email: inputEmail.value.trim(),
      password: inputPassword.value.trim(),
      domain: inputDomain.value,
    });
    uni.hideLoading();
    if (res?.success || res?.connected || res?.message) {
      showGarminModal.value = false;
      uni.showToast({ title: res?.message || "佳明绑定成功", icon: "success" });
      await loadProfileData();
    } else {
      uni.showModal({
        title: "绑定失败",
        content: res?.error || res?.detail || "账号或密码错误，请检查所属区域",
        showCancel: false,
      });
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showModal({
      title: "绑定失败",
      content: e?.message || "连接异常，请检查网络与佳明账号密码",
      showCancel: false,
    });
  } finally {
    binding.value = false;
  }
}

async function handleUnbindGarmin() {
  if (!user.value || !user.value.id) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  uni.showModal({
    title: "解除绑定",
    content: "确定解除佳明账号绑定吗？解除后将停止自动同步运动数据。",
    success: async (res) => {
      if (res.confirm) {
        unbinding.value = true;
        try {
          await request("/api/auth/garmin/unbind", "POST", { uid: user.value?.id });
          uni.showToast({ title: "已解除绑定", icon: "success" });
          await loadProfileData();
        } catch (e: any) {
          uni.showToast({ title: e?.message || "解除失败", icon: "none" });
        } finally {
          unbinding.value = false;
        }
      }
    },
  });
}

function handleLogout() {
  clearSession();
  user.value = null;
  profile.value = null;
  garminConnected.value = false;
  showAuthModal.value = true;
}

function formatSecs(secs?: number): string {
  if (!secs || secs <= 0) return "—";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

onShow(() => {
  loadProfileData();
});
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx 30rpx 80rpx 30rpx;
  box-sizing: border-box;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 24rpx;
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
}

.avatar {
  width: 110rpx;
  height: 110rpx;
  border-radius: 55rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.1);
}

.user-meta {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: 36rpx;
  font-weight: bold;
  color: #ffffff;
}

.user-id {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 6rpx;
}

.section-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
}

.card-title-row {
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

.title-icon {
  font-size: 28rpx;
}

.card-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #ffffff;
}

.conn-status {
  font-size: 24rpx;
  color: #ff3b30;
}

.conn-status.connected {
  color: #34c759;
}

.desc-text {
  font-size: 24rpx;
  color: #8e8e93;
  line-height: 1.5;
  margin-bottom: 24rpx;
  display: block;
}

.garmin-btn {
  background: linear-gradient(135deg, #007aff 0%, #0056b3 100%);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 20rpx;
  height: 80rpx;
  border: none;
}

.unbind-btn {
  background-color: #2c2c2e;
  color: #ff453a;
  font-size: 28rpx;
  border-radius: 20rpx;
  height: 80rpx;
  border: none;
}

.import-garmin-btn {
  background: linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%);
  color: #ffffff;
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 18rpx;
  padding: 8rpx 20rpx;
  height: 56rpx;
  line-height: 40rpx;
  border: none;
}

/* Race List */
.race-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.race-item {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
}

.race-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.race-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.race-badge {
  background-color: #2c2c2e;
  padding: 4rpx 16rpx;
  border-radius: 20rpx;
}

.race-badge.urgent {
  background-color: rgba(255, 59, 48, 0.2);
}

.badge-text {
  font-size: 22rpx;
  font-weight: bold;
  color: #fc4c02;
}

.race-badge.urgent .badge-text {
  color: #ff3b30;
}

.race-meta-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  font-size: 22rpx;
  color: #8e8e93;
}

.race-type-tag {
  color: #30d158;
  background-color: rgba(48, 209, 88, 0.1);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

/* PB Grid */
.pb-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}

.pb-item {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 20rpx;
  display: flex;
  flex-direction: column;
}

.pb-label {
  font-size: 22rpx;
  color: #8e8e93;
}

.pb-val {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
  margin-top: 8rpx;
}

/* Logout */
.logout-box {
  margin-top: 40rpx;
}

.logout-btn {
  background-color: #1c1c1e;
  color: #8e8e93;
  font-size: 28rpx;
  border-radius: 24rpx;
  height: 88rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
}

/* Modal */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

.modal-content {
  width: 670rpx;
  background-color: #18181c;
  border-radius: 36rpx;
  padding: 44rpx 40rpx;
  box-sizing: border-box;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30rpx;
}

.modal-title {
  font-size: 34rpx;
  font-weight: bold;
  color: #ffffff;
}

.close-btn {
  font-size: 36rpx;
  color: #8e8e93;
}

.auth-tabs {
  display: flex;
  background-color: #121214;
  border-radius: 20rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
}

.auth-tab {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  font-size: 26rpx;
  color: #8e8e93;
  border-radius: 16rpx;
}

.auth-tab.active {
  background-color: #2c2c2e;
  color: #ffffff;
  font-weight: bold;
}

.auth-desc {
  font-size: 24rpx;
  color: #8e8e93;
  margin-bottom: 24rpx;
  line-height: 1.4;
  display: block;
}

.field-label {
  font-size: 24rpx;
  color: #aeaeb2;
  margin-top: 16rpx;
  margin-bottom: 8rpx;
  display: block;
}

.large-input {
  width: 100%;
  height: 96rpx;
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 20rpx;
  padding: 0 28rpx;
  font-size: 30rpx;
  color: #ffffff;
  box-sizing: border-box;
  margin-bottom: 12rpx;
}

.placeholder-style {
  color: #636366;
}

.large-primary-btn {
  width: 100%;
  height: 96rpx;
  background: linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%);
  color: #ffffff;
  font-size: 32rpx;
  font-weight: bold;
  border-radius: 24rpx;
  margin-top: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
}

.large-wx-btn {
  width: 100%;
  height: 96rpx;
  background-color: #07c160;
  color: #ffffff;
  font-size: 32rpx;
  font-weight: bold;
  border-radius: 24rpx;
  margin-top: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
}

.domain-selector {
  display: flex;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.domain-btn {
  flex: 1;
  height: 80rpx;
  line-height: 80rpx;
  text-align: center;
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 18rpx;
  font-size: 24rpx;
  color: #8e8e93;
}

.domain-btn.active {
  background-color: #007aff;
  color: #ffffff;
  font-weight: bold;
  border-color: #007aff;
}
</style>
