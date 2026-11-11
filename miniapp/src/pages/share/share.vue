<template>
  <view class="share-landing-page" :class="themeClass">
    <!-- ── 电脑 / 网页版微信扫码登录确认卡片 (当 scene=wlogin_* 时优先展示) ── -->
    <view v-if="webLoginScene" class="brand-hero-card" style="margin-bottom: 28rpx; padding: 44rpx 32rpx;">
      <view class="invite-welcome-pill">
        <text class="invite-welcome-txt">💻 网页版安全扫码授权</text>
      </view>
      <view class="hero-logo-box" style="width: 140rpx; height: 140rpx;">
        <image class="hero-logo-img" src="/static/logo-square.png" mode="aspectFit" />
      </view>
      <text class="hero-brand-title" style="font-size: 38rpx;">登录万跑跑团助手网页版</text>

      <view
        v-if="webLoginUser"
        style="margin: 14rpx 0 22rpx 0; padding: 16rpx 26rpx; border-radius: 18rpx; background: rgba(255,255,255,0.06); border: 1rpx solid rgba(255,255,255,0.12); display: flex; align-items: center; gap: 16rpx;"
      >
        <image
          v-if="webLoginUser.avatar_url"
          :src="webLoginUser.avatar_url"
          mode="aspectFill"
          style="width: 64rpx; height: 64rpx; border-radius: 50%; background: #27272a;"
        />
        <view style="text-align: left;">
          <text style="font-size: 26rpx; font-weight: 700; color: var(--rgm-text, #fff); display: block;">
            {{ webLoginUser.display_name || "微信跑者" }}
          </text>
          <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa); display: block;">
            同步手表档案、周期课表与跑团身份
          </text>
        </view>
      </view>

      <view
        v-if="webLoginError"
        style="width: 100%; margin-bottom: 20rpx; padding: 16rpx 20rpx; border-radius: 14rpx; background: rgba(239,68,68,0.14); border: 1rpx solid rgba(239,68,68,0.4);"
      >
        <text style="font-size: 23rpx; color: #fca5a5;">{{ webLoginError }}</text>
      </view>

      <view
        v-if="webLoginConfirmed"
        style="width: 100%; margin-bottom: 24rpx; padding: 22rpx; border-radius: 16rpx; background: rgba(34,197,94,0.14); border: 1rpx solid rgba(34,197,94,0.45);"
      >
        <text style="font-size: 27rpx; font-weight: 800; color: #4ade80; display: block; margin-bottom: 6rpx;">
          ✅ 网页端已成功登录！
        </text>
        <text style="font-size: 22rpx; color: var(--rgm-text-2, #d4d4d8); display: block;">
          请返回电脑或平板浏览器继续查看您的数据大盘与教练工作台
        </text>
      </view>

      <button
        v-if="!webLoginConfirmed"
        class="hero-enter-btn"
        :loading="confirmingWebLogin"
        :disabled="confirmingWebLogin"
        @click="handleConfirmWebQrLogin"
      >
        <text class="btn-flash-icon">🔐</text>
        <text class="hero-btn-label">{{ confirmingWebLogin ? "正在安全授权..." : "确认授权登录网页版" }}</text>
      </button>

      <button
        v-if="webLoginConfirmed"
        class="hero-enter-btn"
        @click="goToHome"
      >
        <text class="btn-flash-icon">🚀</text>
        <text class="hero-btn-label">顺便进入小程序大厅</text>
      </button>

      <view
        v-if="!webLoginConfirmed"
        style="margin-top: 20rpx; padding: 10rpx 24rpx;"
        @click="handleDismissWebQrLogin"
      >
        <text style="font-size: 24rpx; color: var(--rgm-text-2, #a1a1aa);">暂不登录网页版，浏览小程序 ›</text>
      </view>
    </view>

    <!-- ── 顶部品牌 Hero 卡片 ── -->
    <view v-if="!webLoginScene" class="brand-hero-card">
      <view v-if="hasInviter" class="invite-welcome-pill">
        <text>🎉 跑友邀请你加入</text>
      </view>
      <view class="hero-logo-box">
        <image class="hero-logo-img" src="/static/logo-square.png" mode="aspectFit" />
      </view>
      <text class="hero-brand-title">万跑跑团助手</text>

      <!-- 支持的四大运动手表品牌展示条 -->
      <view class="watch-brands-strip" @click="goToProfile">
        <view class="wb-chip">
          <text class="wb-icon">⌚</text>
          <text class="wb-name">佳明 Garmin</text>
        </view>
        <view class="wb-chip">
          <text class="wb-icon">⌚</text>
          <text class="wb-name">高驰 COROS</text>
        </view>
        <view class="wb-chip">
          <text class="wb-icon wb-icon-apple"></text>
          <text class="wb-name">Apple Watch</text>
        </view>
        <view class="wb-chip">
          <text class="wb-icon">⌚</text>
          <text class="wb-name">华为 HUAWEI</text>
        </view>
      </view>

      <view class="hero-tag-pills">
        <text class="tag-pill">✨ 自建专属跑团</text>
        <text class="tag-pill">📣 约跑海报与战报</text>
        <text class="tag-pill">🎯 Canova 科学教练</text>
        <text class="tag-pill">📊 HRV与睡眠恢复</text>
        <text class="tag-pill">🔒 AES-256保护</text>
      </view>

      <!-- 首屏高转化行动按钮 (无需滑动，一秒直达) -->
      <button class="hero-enter-btn" @click="goToHome">
        <text class="btn-flash-icon">🚀</text>
        <text class="hero-btn-label">立即进入小程序</text>
      </button>
    </view>

    <!-- ── 快捷直达模块通道 ── -->
    <view class="quick-nav-grid">
      <view class="qnav-item" @click="goToCoach">
        <text class="qnav-icon">🎯</text>
        <text class="qnav-label">训练 · 科学教练</text>
      </view>
      <view class="qnav-item" @click="goToTeam">
        <text class="qnav-icon">🏆</text>
        <text class="qnav-label">跑团大本营</text>
      </view>
      <view class="qnav-item" @click="goToAnalysis">
        <text class="qnav-icon">📊</text>
        <text class="qnav-label">身体数据与跑力</text>
      </view>
      <view class="qnav-item" @click="goToManual">
        <text class="qnav-icon">📖</text>
        <text class="qnav-label">操作手册</text>
      </view>
    </view>

    <!-- ── 平台核心功能亮点 ── -->
    <view class="features-section">
      <view class="section-header-row">
        <text class="section-title">核心功能亮点</text>
      </view>

      <!-- 1. 四大主流手表生态全支持 -->
      <view class="feature-card" @click="goToProfile">
        <view class="feature-icon-wrap bg-blue">
          <text class="feature-icon">⌚</text>
        </view>
        <view class="feature-info">
          <view class="f-title-row">
            <text class="feature-title">四大跑表全支持</text>
            <text class="f-arrow">›</text>
          </view>
          <view class="f-mini-tags">
            <text class="f-mini-tag">Garmin 自动直连</text>
            <text class="f-mini-tag">COROS 自动直连</text>
            <text class="f-mini-tag">Apple Watch 导入/直连</text>
            <text class="f-mini-tag">华为运动健康导入</text>
          </view>
        </view>
      </view>

      <!-- 2. 自建专属跑团与多跑团管理 -->
      <view class="feature-card" @click="goToTeam">
        <view class="feature-icon-wrap bg-green">
          <text class="feature-icon">✨</text>
        </view>
        <view class="feature-info">
          <view class="f-title-row">
            <text class="feature-title">自建跑团 · 多跑团切换</text>
            <text class="f-arrow">›</text>
          </view>
          <view class="f-mini-tags">
            <text class="f-mini-tag">✨ 自由创建跑团</text>
            <text class="f-mini-tag">🔑 专属邀请码/公开入团</text>
            <text class="f-mini-tag">🧢 任命认证教练</text>
            <text class="f-mini-tag">🏛️ 戈友大群核验</text>
          </view>
        </view>
      </view>

      <!-- 3. 社交约跑集结与朋友圈战报海报 -->
      <view class="feature-card" @click="goToTeam">
        <view class="feature-icon-wrap bg-amber">
          <text class="feature-icon">📣</text>
        </view>
        <view class="feature-info">
          <view class="f-title-row">
            <text class="feature-title">约跑集结 · 招募与战报</text>
            <text class="f-arrow">›</text>
          </view>
          <view class="f-mini-tags">
            <text class="f-mini-tag">🚀 配速列车分队</text>
            <text class="f-mini-tag">🐰 领跑/摄影/补给角色</text>
            <text class="f-mini-tag">🖼️ 朋友圈海报生成</text>
          </view>
        </view>
      </view>

      <!-- 4. Canova 科学训练系统 -->
      <view class="feature-card" @click="goToCoach">
        <view class="feature-icon-wrap bg-orange">
          <text class="feature-icon">🎯</text>
        </view>
        <view class="feature-info">
          <view class="f-title-row">
            <text class="feature-title">Canova 科学教练与周期课表</text>
            <text class="f-arrow">›</text>
          </view>
        </view>
      </view>

      <!-- 5. 跑团英雄榜与银行级隐私保障 -->
      <view class="feature-card" @click="goToProfile">
        <view class="feature-icon-wrap bg-purple">
          <text class="feature-icon">🔒</text>
        </view>
        <view class="feature-info">
          <view class="f-title-row">
            <text class="feature-title">英雄榜 & AES-256 隐私保护</text>
            <text class="f-arrow">›</text>
          </view>
        </view>
      </view>
    </view>

    <!-- ── 底部留白，防止被悬浮操作栏遮挡 ── -->
    <view class="bottom-spacer"></view>

    <!-- ── 底部固定吸底悬浮栏 (保证任何时候大拇指一键触达) ── -->
    <view class="floating-bottom-bar">
      <!-- #ifdef MP-WEIXIN -->
      <button class="fbar-btn fbar-share-btn" open-type="share">
        <text class="fbar-icon">📢</text>
        <text class="fbar-label">转发跑友群</text>
      </button>
      <!-- #endif -->
      <button class="fbar-btn fbar-primary-btn" @click="goToHome">
        <text class="fbar-icon">🚀</text>
        <text class="fbar-label">进入大厅</text>
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import { onLoad, onShow, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import {
  getStoredUser,
  setPendingInviterUid,
  wechatLogin,
  scanWebQrLogin,
  confirmWebQrLogin,
  type UserProfile,
} from "../../utils/api";
import { trackClick } from "../../utils/telemetry";

const hasInviter = ref(false);
const webLoginScene = ref("");
const webLoginUser = ref<UserProfile | null>(null);
const confirmingWebLogin = ref(false);
const webLoginConfirmed = ref(false);
const webLoginError = ref("");

onShow(() => {
  applySystemTheme(currentTheme.value);
});

onLoad(async (options?: any) => {
  initShareMenu();
  const rawScene = decodeURIComponent(String(options?.scene || options?.web_login_scene || "")).trim();
  if (rawScene.startsWith("wlogin_")) {
    webLoginScene.value = rawScene;
    try {
      let u = getStoredUser();
      if (!u) {
        u = await wechatLogin();
      }
      webLoginUser.value = u;
      await scanWebQrLogin(rawScene, u?.display_name, u?.avatar_url);
    } catch (err: any) {
      webLoginError.value = err?.message || "二维码已过期，请在网页端点击刷新二维码后重新扫码";
    }
    return;
  }

  if (options?.inviter_uid || options?.from === "create_club") {
    hasInviter.value = true;
  }
  if (options?.inviter_uid) {
    setPendingInviterUid(options.inviter_uid);
    if (!getStoredUser()) {
      await wechatLogin();
    }
  }
});

async function handleConfirmWebQrLogin() {
  if (!webLoginScene.value || confirmingWebLogin.value) return;
  webLoginError.value = "";
  confirmingWebLogin.value = true;
  try {
    let u = webLoginUser.value || getStoredUser();
    if (!u) {
      u = await wechatLogin();
      webLoginUser.value = u;
    }
    await confirmWebQrLogin(webLoginScene.value, u?.display_name, u?.avatar_url);
    webLoginConfirmed.value = true;
    trackClick("web_qr_login_confirm", "小程序端确认授权登录网页版");
    uni.showToast({ title: "网页端登录成功！", icon: "success" });
  } catch (err: any) {
    webLoginError.value = err?.message || "授权确认失败，请在电脑网页端刷新二维码重试";
  } finally {
    confirmingWebLogin.value = false;
  }
}

function handleDismissWebQrLogin() {
  trackClick("web_qr_login_dismiss", "暂不登录网页版浏览小程序");
  webLoginScene.value = "";
}

onShareAppMessage(() => {
  return getUnifiedShareAppMessage();
});

onShareTimeline(() => {
  return getUnifiedShareTimeline();
});

async function goToHome() {
  trackClick("share_cta_home", "邀请落地页点击进入首页");
  if (!getStoredUser()) {
    await wechatLogin();
  }
  uni.switchTab({
    url: "/pages/index/index",
  });
}

function goToCoach() {
  trackClick("share_cta_coach", "邀请落地页点击进入训练页");
  uni.switchTab({
    url: "/pages/coach/coach",
  });
}

function goToTeam() {
  trackClick("share_cta_team", "邀请落地页点击进入跑团页");
  uni.switchTab({
    url: "/pages/team/team",
  });
}

function goToAnalysis() {
  trackClick("share_cta_analysis", "邀请落地页点击进入跑力分析页");
  // 深度分析已并入【训练】，不再是 Tab 页
  uni.navigateTo({
    url: "/pages/analysis/analysis",
  });
}

function goToProfile() {
  trackClick("share_cta_profile", "邀请落地页点击进入我的页面");
  uni.switchTab({
    url: "/pages/profile/profile",
  });
}

function goToManual() {
  trackClick("share_cta_manual", "邀请落地页点击进入使用手册");
  uni.navigateTo({
    url: "/pages/manual/manual",
  });
}
</script>

<style scoped>
.share-landing-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  padding: 24rpx 28rpx calc(48rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── 顶部品牌 Hero 卡片 ── */
.brand-hero-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(252, 76, 2, 0.22) 0%, #151518 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));
  border-radius: 24rpx;
  padding: 36rpx 28rpx;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.25));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.hero-logo-box {
  width: 180rpx;
  height: 180rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16rpx;
  background: transparent;
  box-sizing: border-box;
}

.invite-welcome-pill {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  padding: 6rpx 22rpx;
  border-radius: 9999rpx;
  margin-bottom: 14rpx;
}

.invite-welcome-txt {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

.hero-logo-img {
  width: 100%;
  height: 100%;
}

.hero-brand-title {
  font-size: 44rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  letter-spacing: 2rpx;
  margin-bottom: 12rpx;
}


/* 四大跑表品牌徽章条 */
.watch-brands-strip {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12rpx;
  width: 100%;
  margin-bottom: 20rpx;
}

.wb-chip {
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line-strong, rgba(255, 255, 255, 0.14));
  border-radius: 18rpx;
  height: 64rpx;
  padding: 0 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  box-sizing: border-box;
}

.wb-icon {
  width: 32rpx;
  height: 32rpx;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  line-height: 1;
  flex-shrink: 0;
}

.wb-icon-apple {
  font-size: 36rpx;
  color: var(--rgm-text, #111827);
  transform: translateY(-2rpx);
}

.wb-name {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
  line-height: 1;
}

.hero-tag-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  justify-content: center;
  margin-bottom: 28rpx;
}

.tag-pill {
  font-size: 21rpx;
  font-weight: 600;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  padding: 6rpx 16rpx;
  border-radius: 9999rpx;
}

/* 顶部高转化大按钮 */
.hero-enter-btn {
  width: 100%;
  height: 96rpx;
  border-radius: 28rpx;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff5e1a 100%));
  color: var(--rgm-text, #ffffff);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  border: none;
  box-shadow: 0 10rpx 30rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.45));
  margin-bottom: 14rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.hero-enter-btn::after {
  border: none;
}

.btn-flash-icon {
  font-size: 34rpx;
}

.hero-btn-label {
  font-size: 32rpx;
  font-weight: 800;
  letter-spacing: 1rpx;
}


/* ── 快捷直达 4 宫格 ── */
.quick-nav-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16rpx;
  margin-bottom: 36rpx;
}

.qnav-item {
  background: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 20rpx 10rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  transition: opacity 0.2s;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.qnav-item:active {
  opacity: 0.75;
}

.qnav-icon {
  font-size: 40rpx;
  margin-bottom: 10rpx;
}

.qnav-label {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #f4f4f5);
  margin-bottom: 4rpx;
  white-space: nowrap;
}


/* ── 功能亮点 ── */
.features-section {
  margin-bottom: 30rpx;
}

.section-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
  padding: 0 8rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}


.feature-card {
  background: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 24rpx;
  margin-bottom: 18rpx;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 20rpx;
  transition: transform 0.15s;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.feature-card:active {
  transform: scale(0.99);
}

.feature-icon-wrap {
  width: 76rpx;
  height: 76rpx;
  border-radius: 22rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.feature-icon {
  font-size: 38rpx;
}

.bg-blue {
  background: rgba(0, 122, 255, 0.15);
  border: 1rpx solid rgba(0, 122, 255, 0.3);
}

.bg-orange {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
}

.bg-green {
  background: rgba(52, 199, 89, 0.15);
  border: 1rpx solid rgba(52, 199, 89, 0.3);
}

.bg-amber {
  background: rgba(245, 158, 11, 0.16);
  border: 1rpx solid rgba(245, 158, 11, 0.35);
}

.bg-purple {
  background: var(--rgm-brand-tint, rgba(175, 82, 222, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.3));
}

.feature-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.f-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.feature-title {
  font-size: 28rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.f-arrow {
  font-size: 28rpx;
  color: var(--rgm-text-3, #71717a);
}


.f-mini-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-top: 4rpx;
}

.f-mini-tag {
  font-size: 19rpx;
  font-weight: 600;
  color: var(--rgm-text-2, #a0a0a5);
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 3rpx 12rpx;
  border-radius: 9999rpx;
}

.bottom-spacer {
  height: 100rpx;
}

/* ── 底部固定吸底悬浮栏 ── */
.floating-bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--rgm-card, rgba(18, 18, 20, 0.94));
  backdrop-filter: blur(20px);
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 16rpx 28rpx;
  padding-bottom: calc(16rpx + constant(safe-area-inset-bottom));
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16rpx;
  z-index: 100;
  box-shadow: 0 -8rpx 30rpx var(--rgm-shadow, rgba(0, 0, 0, 0.5));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.fbar-btn {
  height: 84rpx;
  border-radius: 9999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  border: none;
  box-sizing: border-box;
  margin: 0;
}

.fbar-btn::after {
  border: none;
}

.fbar-share-btn {
  flex: 2;
  background: rgba(16, 185, 129, 0.18);
  border: 1rpx solid rgba(16, 185, 129, 0.4);
  color: var(--rgm-green, #10b981);
}

.fbar-share-btn .fbar-label {
  font-size: 26rpx;
  font-weight: 700;
}

.fbar-primary-btn {
  flex: 3;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff5e1a 100%));
  color: var(--rgm-text, #ffffff);
  box-shadow: 0 6rpx 20rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.35));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.fbar-primary-btn .fbar-label {
  font-size: 28rpx;
  font-weight: 800;
  letter-spacing: 1rpx;
}

.fbar-icon {
  font-size: 32rpx;
}
</style>
