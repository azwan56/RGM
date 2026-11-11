<template>
  <view class="profile-page" :class="themeClass">
    <!-- ── 「我的」首页头部：进入子页面时隐藏，减少滚动长度 ── -->
    <template v-if="!activeSection">
    <!-- ── 顶部用户卡（无论登录与否始终显示在最顶部）── -->
    <view v-if="!user" class="login-hero-card">
      <view class="login-hero-left">
        <view class="hero-icon-circle">
          <text class="hero-wx-icon">🟢</text>
        </view>
        <view class="hero-text-wrap">
          <text class="hero-title">微信跑者一键登录</text>
        </view>
      </view>
      <!-- 用 button open-type 保证最高优先级点击响应 -->
      <button class="hero-login-btn-native" @click="openAuthModal">
        🟢 微信一键快速登录
      </button>
      <!-- #ifdef APP-PLUS -->
      <button class="hero-login-btn-apple" @click="handleAppleLogin" style="margin-top: 16rpx; background: var(--rgm-card-2, #1c1c1e); color: var(--rgm-text, #ffffff); border: 1px solid var(--rgm-line, rgba(255,255,255,0.25)); border-radius: 9999rpx; font-size: 28rpx; height: 80rpx; line-height: 80rpx; display: flex; align-items: center; justify-content: center; font-weight: 600; width: 100%;   --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3); ">
         通过 Apple 快速登录
      </button>
      <!-- #endif -->
    </view>

    <!-- ── 已登录状态：展示跑者卡片与修改资料/切换账号 ── -->
    <view v-else class="user-card" @click="openEditProfileModal">
      <view class="avatar-wrap">
        <image class="avatar" :src="profile?.avatar_url || user?.avatar_url || defaultAvatar" mode="aspectFill" />
        <view class="avatar-camera-pill">
          <text class="camera-icon">📷</text>
        </view>
      </view>
      <view class="user-meta">
        <view class="user-name-row">
          <text class="user-name">{{ profile?.display_name || user?.display_name || "微信跑者" }}</text>
          <text class="edit-pill">✏️ 编辑资料</text>
        </view>
        <text v-if="userClub?.name" class="user-id">{{ userClub.name }}</text>
      </view>
      <button class="switch-user-btn" @click.stop="handleConfirmLogout">退出</button>
    </view>

    <!-- ── 🚀 设定向导：仅在未完成时显示；完成后入口移到页面底部「帮助与设置」 ── -->
    <view v-if="onboardingStatus && !onboardingStatus.is_completed" class="onboard-guide-card" @click="goToOnboarding(1)">
      <view class="ogc-left">
        <view class="ogc-icon-circle">🚀</view>
        <view class="ogc-meta">
          <view class="ogc-title-row">
            <text class="ogc-title">设定向导</text>
            <text class="ogc-progress-tag" :class="{ completed: onboardingStatus?.is_completed }">
              {{ onboardingStatus?.is_completed ? '100%' : `${onboardingStatus?.percent || 0}%` }}
            </text>
          </view>
        </view>
      </view>
      <view class="ogc-right">
        <text class="ogc-action-txt">{{ onboardingStatus?.is_completed ? '重设 ›' : '去完善 ›' }}</text>
      </view>
    </view>

    <!-- ── 快捷入口：常用的低频功能统一放在顶部一行，避免沉到长页面底部 ── -->
    <view class="quick-grid">
      <view class="qg-item" @click="goToOnboarding(1)">
        <view class="qg-icon-wrap">
          <text class="qg-icon">🚀</text>
          <view v-if="onboardingStatus && !onboardingStatus.is_completed" class="qg-dot" />
        </view>
        <text class="qg-label">向导</text>
      </view>
      <view class="qg-item" @click="scrollToDeviceCard">
        <view class="qg-icon-wrap">
          <text class="qg-icon">⌚</text>
          <view v-if="!garminConnected && !corosConnected && !appleWatchConnected && !huaweiConnected && !suuntoConnected" class="qg-dot" />
        </view>
        <text class="qg-label">{{ garminConnected || corosConnected || appleWatchConnected || huaweiConnected || suuntoConnected ? '已绑表' : '绑表' }}</text>
      </view>
      <view class="qg-item" @click="goToSharePage">
        <view class="qg-icon-wrap"><text class="qg-icon">📢</text></view>
        <text class="qg-label">分享</text>
      </view>
      <view class="qg-item" @click="goToManual">
        <view class="qg-icon-wrap"><text class="qg-icon">📖</text></view>
        <text class="qg-label">帮助</text>
      </view>
    </view>

    </template>

    <!-- ── 子页面返回栏：拆分后每个子页面顶部固定显示「‹ 我的」 ── -->
    <view v-if="activeSection" class="section-back-bar">
      <view class="sbb-back" @click="closeSection">
        <text class="sbb-arrow">‹</text>
        <text class="sbb-back-txt">我的</text>
      </view>
      <text class="sbb-title">{{ activeSectionTitle }}</text>
      <view class="sbb-placeholder" />
    </view>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!-- TAB 1: 个人资料与账号 (Profile & Account)                     -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <!-- 首页：大群状态 + 跑团 + 功能菜单 -->
    <template v-if="!activeSection">
      <!-- ── CARD: 大群体成员认证与审核状态卡 (Grand Org Membership & Expiry Status) ── -->
    <view v-if="userOrgs && userOrgs.length > 0" class="section-card org-status-section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🏫</text>
          <text class="card-title">大群认证状态</text>
        </view>
        <text class="security-chip" style="background: rgba(245, 158, 11, 0.15); color: var(--rgm-amber, #fbbf24); border-color: rgba(245, 158, 11, 0.3);">
          2周实名核验制
        </text>
      </view>

      <view v-for="org in userOrgs" :key="org.id" class="org-status-item" :class="'org-state-' + (org.status || 'temporary')">
        <view class="org-status-header">
          <view class="org-name-wrap">
            <text class="org-item-name">{{ org.name }}</text>
          </view>
          <view class="org-status-badge" :class="'badge-' + (org.status || 'temporary')">
            <text v-if="org.status === 'confirmed'">🏅 正式成员 · 已核验</text>
            <text v-else-if="org.status === 'expired' || org.status === 'suspended' || org.is_suspended">🚫 访问已暂停</text>
            <text v-else-if="org.status === 'pending'">📋 待管理员核验 · 余{{ org.days_remaining !== null && org.days_remaining !== undefined ? org.days_remaining : 14 }}天</text>
            <text v-else>⏳ 临时状态 · 余{{ org.days_remaining !== null && org.days_remaining !== undefined ? org.days_remaining : 14 }}天</text>
          </view>
        </view>

        <!-- Status Details -->
        <view v-if="org.status === 'confirmed'" class="org-status-desc desc-confirmed">
          <button class="org-action-btn btn-secondary" @click="scrollToRequiredFields({ message: '已为您展开大群实名认证资料与个人参数' })">
            ✏️ 查看/修改认证资料
          </button>
        </view>
        <view v-else-if="org.status === 'expired' || org.status === 'suspended' || org.is_suspended" class="org-status-desc desc-suspended">
          <text class="org-desc-text warning-text">⚠️ 临时访问期已到期，大群内容已暂停访问</text>
          <button class="org-action-btn btn-danger" @click="scrollToRequiredFields({ message: '请在下方补齐必填项' })">📝 去补齐必填项</button>
        </view>
        <view v-else-if="org.status === 'pending'" class="org-status-desc desc-pending">
          <button class="org-action-btn btn-secondary" @click="scrollToRequiredFields({ message: '已为您展开待审核实名认证资料' })">
            ✏️ 查看/修改资料
          </button>
        </view>
        <view v-else class="org-status-desc desc-temporary">
          <text class="org-desc-text">⏳ 请在 {{ org.days_remaining }} 天内补齐必填项，超期将暂停访问</text>
          <view v-if="org.missing_fields && org.missing_fields.length" class="missing-fields-box">
            <text class="missing-title">待补齐必填项：</text>
            <text class="missing-labels">{{ org.missing_fields.map((f: any) => f.label).join('、') }}</text>
          </view>
          <button class="org-action-btn" @click="scrollToRequiredFields({ message: '请在下方补齐必填字段' })">📝 去补齐必填项</button>
        </view>
      </view>
    </view>

      <!-- ── CARD 1: 我的跑团与管理 (Running Club Card) ── -->
    <view class="section-card club-card-highlight">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🏃</text>
          <text class="card-title">我的跑团</text>
        </view>
        <text v-if="userClub" class="club-role-tag" :class="'role-' + (userClub.role || 'member')">
          {{ userClub.role === 'owner' ? '👑 团长' : userClub.role === 'coach' ? '🧢 教练' : '🏃 团员' }}
        </text>
        <text v-else class="club-role-tag role-none">
          未入团
        </text>
      </view>

      <!-- Joined Club Summary -->
      <view v-if="userClub" class="joined-club-box">
        <view class="club-mini-info">
          <image class="mini-logo" :src="userClub.logo_url || '/static/logo-square.png'" mode="aspectFill" />
          <view class="mini-texts">
            <view class="club-title-row">
              <text class="club-title-text">{{ userClub.name }}</text>
              <text v-if="userClubs.length > 1" class="multi-club-badge">{{ userClubs.length }}个跑团</text>
            </view>
            <text v-if="userClub.description" class="club-desc-text">{{ userClub.description }}</text>
          </view>
        </view>
      </view>

      <!-- Unjoined Empty State -->
      <view v-else class="joined-club-box empty-club-box" style="padding: 28rpx; text-align: center;">
        <text style="font-size: 26rpx; color: var(--rgm-text, #ffffff); font-weight: bold; display: block; margin-bottom: 8rpx;">尚未加入跑团</text>
        <text style="font-size: 22rpx; color: var(--rgm-text-3, #8e8e93); display: block; line-height: 1.5;">浏览跑团或凭邀请码加入</text>
      </view>

      <!-- Club Action Buttons -->
      <view class="club-btn-grid">
        <button class="club-act-btn join-btn" @click="goToTeamPage">
          {{ userClubs.length > 1 ? `⇄ 切换(${userClubs.length})` : userClub ? '🏃 跑团' : '🏃 发现' }}
        </button>
        <button class="club-act-btn create-btn" @click="showJoinModal = true">
          🔑 凭码入团
        </button>
        <button class="club-act-btn self-create-btn" @click="goToCreateMyClub">
          ✨ 自建跑团
        </button>
      </view>
    </view>

    <!-- ── 功能菜单：原来平铺的长表单拆成 4 个子页面，按需进入 ── -->
    <view class="section-card profile-menu-card">
      <view class="pm-item" @click="openSection('device')">
        <text class="pm-icon">⌚</text>
        <view class="pm-meta">
          <text class="pm-title">手表连接</text>
        </view>
        <text class="pm-status" :class="{ ok: garminConnected || corosConnected || appleWatchConnected || huaweiConnected || suuntoConnected, warn: !garminConnected && !corosConnected && !appleWatchConnected && !huaweiConnected && !suuntoConnected }">{{ deviceStatusText }}</text>
        <text class="pm-arrow">›</text>
      </view>
      <view class="pm-item" @click="openSection('personal')">
        <text class="pm-icon">👤</text>
        <view class="pm-meta">
          <text class="pm-title">个人资料</text>
        </view>
        <text v-if="personalNeedsAttention" class="pm-status warn">待补齐</text>
        <text class="pm-arrow">›</text>
      </view>
      <view class="pm-item" @click="openSection('training')">
        <text class="pm-icon">🏃</text>
        <view class="pm-meta">
          <text class="pm-title">训练档案</text>
        </view>
        <text class="pm-arrow">›</text>
      </view>
      <view class="pm-item" @click="openSection('privacy')">
        <text class="pm-icon">🔔</text>
        <view class="pm-meta">
          <text class="pm-title">通知与隐私</text>
        </view>
        <text class="pm-status" :class="{ ok: wechatSubscribeEnabled }">{{ wechatSubscribeEnabled ? '已开启' : '未开启' }}</text>
        <text class="pm-arrow">›</text>
      </view>
      <view class="pm-item pm-item-last" @click="openSection('support')">
        <text class="pm-icon">💬</text>
        <view class="pm-meta">
          <text class="pm-title">帮助与支持</text>
        </view>
        <text class="pm-status" :class="{ ok: hasSupportReply }">{{ hasSupportReply ? '已回复' : '在线' }}</text>
        <text class="pm-arrow">›</text>
      </view>
    </view>

    <!-- ── 外观与字号调节 ── -->
    <view class="section-card profile-menu-card appearance-card">
      <view class="pm-item">
        <text class="pm-icon">🔤</text>
        <view class="pm-meta">
          <text class="pm-title">字号大小</text>
        </view>
        <view class="app-seg-group">
          <view
            v-for="opt in FONT_SCALE_OPTIONS"
            :key="opt.key"
            class="app-seg-pill"
            :class="{ active: currentFontScale === opt.key }"
            @click="setFontScale(opt.key)"
          >{{ opt.label }}</view>
        </view>
      </view>
      <view class="pm-item pm-item-last">
        <text class="pm-icon">🎨</text>
        <view class="pm-meta">
          <text class="pm-title">界面主题</text>
        </view>
        <view class="app-seg-group">
          <view
            class="app-seg-pill"
            :class="{ active: currentTheme === 'dark' }"
            @click="setTheme('dark')"
          >🌑 暗黑</view>
          <view
            class="app-seg-pill"
            :class="{ active: currentTheme === 'volt' }"
            @click="setTheme('volt')"
          >☀️ 亮色</view>
        </view>
      </view>
    </view>

    <!-- 底部退出登录（仅登录后显示） -->
    <view v-if="user" class="logout-box">
      <button class="logout-btn" @click="handleConfirmLogout">退出登录</button>
    </view>
    </template>

    <!-- 子页面：手表连接与同步 -->
    <template v-if="activeSection === 'device'">
      <!-- ── CARD 2: Device Connection Status Card (Garmin · COROS · Apple Watch · HUAWEI · SUUNTO) ── -->
    <view id="device-connect-card" class="section-card" :class="{ 'highlight-pulse': isDeviceCardHighlighted }">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">⌚</text>
          <text class="card-title">手表连接与同步</text>
        </view>
      </view>

      <!-- 24小时全天佩戴手表重要提示横幅（精简 + ⓘ 隐藏说明） -->
      <view
        style="background: rgba(245, 158, 11, 0.14); border: 1rpx solid rgba(245, 158, 11, 0.45); border-radius: 14rpx; padding: 14rpx 20rpx; margin-bottom: 20rpx; display: flex; align-items: center; justify-content: space-between;"
        @click.stop="explainTerm('watch_wear')"
      >
        <text style="font-size: 23rpx; font-weight: 700; color: #b45309;">
          ⌚ 请 24 小时佩戴手表（含睡眠）
        </text>
        <text style="font-size: 21rpx; font-weight: 700; color: #b45309; flex-shrink: 0; margin-left: 10rpx;">ⓘ 说明</text>
      </view>

      <!-- 1. Garmin Status Block -->
      <view class="device-status-item">
        <view class="device-item-header">
          <view class="device-name-wrap">
            <text class="device-badge garmin-badge">GARMIN</text>
            <text class="device-name-text">佳明 Garmin</text>
          </view>
          <text class="conn-status" :class="{ connected: garminConnected }">
            {{ garminConnected ? "已连接 ✓" : "未连接" }}
          </text>
        </view>
        <text v-if="garminConnected" class="desc-text" style="margin: 8rpx 0 16rpx 0;">
          {{ `已绑定：${garminEmail} (${garminDomain})` }}
        </text>
        <button
          v-if="!garminConnected"
          class="garmin-btn"
          style="margin-bottom: 20rpx;"
          @click="openDeviceModal('garmin')"
        >
          绑定佳明账号
        </button>
        <button
          v-else
          class="unbind-btn"
          style="margin-bottom: 20rpx;"
          :loading="unbinding"
          @click="handleUnbindGarmin"
        >
          解除佳明绑定
        </button>
      </view>

      <!-- 2. COROS Status Block -->
      <view class="device-status-item" style="border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08)); padding-top: 20rpx;">
        <view class="device-item-header">
          <view class="device-name-wrap">
            <text class="device-badge coros-badge">COROS</text>
            <text class="device-name-text">高驰 COROS</text>
          </view>
          <text
            class="conn-status"
            :class="{ connected: corosConnected && !corosNeedsReauth }"
            :style="corosConnected && corosNeedsReauth ? 'color: #f59e0b; font-weight: 700;' : ''"
          >
            {{ !corosConnected ? "未连接" : corosNeedsReauth ? "⚠️ 待短信验证" : "已连接 ✓" }}
          </text>
        </view>
        <text v-if="corosConnected" class="desc-text" style="margin: 8rpx 0 12rpx 0;">
          {{ `已绑定：${corosAccount} (${corosDomain})` }}
        </text>
        <text
          v-if="corosConnected && corosNeedsReauth"
          class="desc-text"
          style="display: block; color: #f59e0b; margin: 0 0 16rpx 0;"
        >
          {{ corosAuthError || "高驰安全授权已到期，点击下方按钮免密获取短信验证码即可恢复同步" }}
        </text>
        <button
          v-if="!corosConnected"
          class="garmin-btn coros-btn"
          style="margin-bottom: 20rpx;"
          @click="openDeviceModal('coros')"
        >
          绑定高驰账号
        </button>
        <view v-else class="btn-group-row" style="display: flex; gap: 16rpx; margin-top: 8rpx; margin-bottom: 20rpx;">
          <button
            class="garmin-btn coros-btn"
            style="flex: 1; margin: 0;"
            @click="openDeviceModal('coros')"
          >
            {{ corosNeedsReauth ? "📱 获取验证码恢复连接" : "🔑 重新授权/改密" }}
          </button>
          <button
            class="unbind-btn"
            style="flex: 1; margin: 0;"
            :loading="unbindingCoros"
            @click="handleUnbindCoros"
          >
            解除绑定
          </button>
        </view>
      </view>

      <!-- 3. 苹果 / 华为 / 颂拓（非直连 · 截图与轨迹导入） -->
      <view class="device-status-item" style="border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08)); padding-top: 20rpx;">
        <view class="device-item-header">
          <view class="device-name-wrap">
            <text class="device-badge apple-badge">苹果 / 华为 / 颂拓</text>
            <text class="device-name-text">截图/轨迹导入</text>
          </view>
          <text class="conn-status" :class="{ connected: appleWatchConnected || huaweiConnected || suuntoConnected }">
            {{ (appleWatchConnected || huaweiConnected || suuntoConnected) ? "已连接 ✓" : "未连接" }}
          </text>
        </view>
        <button
          class="garmin-btn apple-watch-btn"
          style="width: 100%; margin: 0 0 14rpx 0;"
          :loading="!!importingScreenshotBrand"
          @click="handleImportWatchScreenshot(activeHealthWatchBrand)"
        >
          📸 选运动截图导入
        </button>
        <view v-if="!(appleWatchConnected || huaweiConnected || suuntoConnected)" class="btn-group-row" style="display: flex; gap: 16rpx;">
          <button
            class="track-import-outline-btn apple-outline"
            style="flex: 1; margin: 0;"
            @click="openDeviceModal('apple_watch')"
          >
            ⌚ 连接与教程
          </button>
          <button
            class="track-import-outline-btn apple-outline"
            style="flex: 1; margin: 0;"
            :loading="!!importingTrackBrand"
            @click="handleImportWatchTrack(activeHealthWatchBrand)"
          >
            📂 导入 FIT/GPX/TCX
          </button>
        </view>
        <view v-else class="btn-group-row" style="display: flex; gap: 16rpx;">
          <button
            class="track-import-outline-btn apple-outline"
            style="flex: 1.4; margin: 0;"
            :loading="!!importingTrackBrand"
            @click="handleImportWatchTrack(activeHealthWatchBrand)"
          >
            📂 导入 FIT/GPX/TCX
          </button>
          <button
            class="unbind-btn"
            style="flex: 1; margin: 0;"
            :loading="unbindingAppleWatch || unbindingHuawei || unbindingSuunto"
            @click="handleUnbindHealthWatch(activeHealthWatchBrand)"
          >
            解除绑定
          </button>
        </view>
      </view>

      <!-- 手表绑定遇到问题快捷入口 -->
      <view class="device-support-quick-bar" @click="openSection('support')">
        <text class="dsq-text">💬 遇到问题？联系客服 ›</text>
      </view>
    </view>

    </template>

    <!-- 子页面：个人资料与实名信息（实名与大群资料放一起，便于补齐必填项） -->
    <template v-if="activeSection === 'personal'">
      <!-- ── CARD: 个人实名身份与敏感信息 (AES-256 加密保护) ── -->
    <view id="required-personal-fields" class="section-card section-card-runner-info" :class="{ 'highlight-pulse': isFieldHighlighted }">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🔒</text>
          <text class="card-title">实名身份信息</text>
        </view>
        <text class="security-chip">AES-256 加密存储</text>
      </view>

      <view class="form-grid-2">
        <!-- 出生日期 & 动态年龄 -->
        <view class="form-group full-width-group">
          <view class="label-with-tag">
            <view class="label-with-sec">
              <text class="label">出生日期<text class="required-star"> *</text></text>
              <text class="field-sec-tag req-tag">大群必填</text>
              <text class="field-sec-tag">🔒 AES-256 加密存储</text>
            </view>
            <text v-if="displayAge !== null" class="age-badge-pill">
              {{ displayAge }} 岁 · {{ profile?.date_of_birth ? profile.date_of_birth.substring(0, 4) + '年 · ' : '' }}{{ displayAge >= 50 ? '大师组' : displayAge >= 40 ? '壮年组' : displayAge >= 30 ? '中坚组' : '青年组' }}
            </text>
          </view>
          <picker
            mode="date"
            :value="profile?.date_of_birth || '1990-01-01'"
            start="1940-01-01"
            :end="todayDateStr"
            @change="onDateOfBirthChange"
          >
            <view class="picker-input-box">
              <text :class="{ 'placeholder-text': !profile?.date_of_birth }">
                {{ profile?.date_of_birth || '请选择出生年月日 (YYYY-MM-DD)' }}
              </text>
              <text class="picker-arrow">📅</text>
            </view>
          </picker>
        </view>

        <!-- 真实姓名 -->
        <view class="form-group">
          <view class="label-with-tag">
            <text class="label">真实姓名<text class="required-star"> *</text></text>
            <text class="field-sec-tag req-tag">大群必填</text>
            <text class="field-sec-tag">🔒 加密存储</text>
          </view>
          <input
            class="form-input"
            type="text"
            placeholder="戈友实名认证姓名"
            :value="profile?.real_name || ''"
            @input="onInputRealName"
          />
        </view>

        <!-- 联系手机 -->
        <view class="form-group">
          <view class="label-with-tag">
            <text class="label">联系手机</text>
            <text class="field-sec-tag">🔒 加密存储</text>
          </view>
          <input
            class="form-input"
            type="number"
            maxlength="11"
            placeholder="紧急联络手机"
            :value="profile?.phone || ''"
            @input="onInputPhone"
          />
        </view>

        <!-- 身份证号码 / 证件号 -->
        <view class="form-group full-width-group">
          <view class="label-with-tag">
            <text class="label">身份证号码 / 证件号 (选填)</text>
            <text class="field-sec-tag">🔒 密文存储 · 仅本人可见</text>
          </view>
          <input
            class="form-input"
            type="text"
            maxlength="18"
            placeholder="用于赛事保险投保与参赛资格核验"
            :value="profile?.id_card || ''"
            @input="onInputIdCard"
          />
        </view>

        <!-- 生理性别 -->
        <view class="form-group">
          <view class="label-with-tag">
            <text class="label">生理性别<text class="required-star"> *</text></text>
            <text class="field-sec-tag req-tag">大群必填</text>
          </view>
          <view class="gender-pill-group">
            <view
              class="gender-pill"
              :class="{ active: (profile?.gender || 'male') === 'male' }"
              @click="onGenderSelect('male')"
            >
              <text>♂ 男</text>
            </view>
            <view
              class="gender-pill"
              :class="{ active: profile?.gender === 'female' }"
              @click="onGenderSelect('female')"
            >
              <text>♀ 女</text>
            </view>
          </view>
        </view>
      </view>
    </view>

      <!-- ── 渐进式资料：未加入大群时折叠商学院 / 赛事装备资料，避免吓跑普通跑者 ── -->
    <view v-if="!hasOrgs" class="section-card extra-fields-toggle" @click="showOrgExtraFields = !showOrgExtraFields">
      <view class="eft-meta">
        <text class="eft-title">🎓 商学院 / 赛事装备资料</text>
      </view>
      <text class="eft-arrow">{{ showOrgExtraFields ? '收起 ▴' : '展开 ▾' }}</text>
    </view>
    <view v-if="hasOrgs || showOrgExtraFields">
      <!-- ── CARD: 商学院项目与戈友认证 ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🏫</text>
          <text class="card-title">商学院与戈友认证</text>
        </view>
        <text class="security-chip" style="background: rgba(245, 158, 11, 0.15); color: var(--rgm-amber, #fbbf24); border-color: rgba(245, 158, 11, 0.3);">
          大群自动同步
        </text>
      </view>

      <view class="form-grid-2">
        <!-- 所属项目 -->
        <view class="form-group full-width-group">
          <view class="label-with-tag">
            <text class="label">商学院项目<text class="required-star"> *</text></text>
            <text class="field-sec-tag req-tag">大群必填</text>
          </view>
          <view class="program-pill-grid">
            <view
              v-for="prog in ORG_PROGRAM_OPTIONS"
              :key="prog"
              class="program-pill"
              :class="{ active: profile?.program === prog }"
              @click="onSelectProgram(prog)"
            >
              <text>{{ prog }}</text>
            </view>
          </view>
        </view>

        <!-- 班级 / 届别 -->
        <view class="form-group full-width-group">
          <view class="label-with-tag">
            <text class="label">所在班级 / 届别 (自由输入)<text class="required-star"> *</text></text>
            <text class="field-sec-tag req-tag">大群必填</text>
          </view>
          <input
            class="form-input"
            type="text"
            placeholder="例如: 23春、21级、18班、2022秋"
            :value="profile?.class_detail || ''"
            @input="onInputClassDetail"
          />
          <text v-if="profile?.program && profile?.class_detail" class="field-privacy-subtip" style="color: var(--rgm-amber, #fbbf24);">
            名册组合预览：{{ profile.program }} {{ profile.class_detail }}
          </text>
        </view>

        <!-- 戈壁经历 -->
        <view class="form-group full-width-group">
          <view class="label-with-tag">
            <text class="label">戈壁经历 (戈赛经验)</text>
            <text class="field-sec-tag">{{ gobiType === 'new' ? '🌱 新戈' : `🏅 ${gobiEdition} ${gobiGroup}` }}</text>
          </view>

          <view class="gobi-type-selector">
            <view
              class="gobi-type-btn"
              :class="{ active: gobiType === 'new' }"
              @click="onSelectGobiType('new')"
            >
              <text class="gobi-icon">🌱</text>
              <view class="gobi-info">
                <text class="gobi-main-title">新戈跑者</text>
              </view>
            </view>
            <view
              class="gobi-type-btn"
              :class="{ active: gobiType === 'vet' }"
              @click="onSelectGobiType('vet')"
            >
              <text class="gobi-icon">🏅</text>
              <view class="gobi-info">
                <text class="gobi-main-title">往届老戈友</text>
              </view>
            </view>
          </view>

          <!-- 往届老戈友详情选择 -->
          <view v-if="gobiType === 'vet'" class="gobi-vet-box">
            <view class="vet-row">
              <text class="vet-label">参加届数：</text>
              <picker
                mode="selector"
                :range="GOBI_EDITIONS"
                :value="GOBI_EDITIONS.indexOf(gobiEdition) >= 0 ? GOBI_EDITIONS.indexOf(gobiEdition) : 0"
                @change="onGobiEditionChange"
                class="vet-picker-flex"
              >
                <view class="picker-input-box">
                  <text>{{ gobiEdition || '请选择届数' }}</text>
                  <text class="picker-arrow">▼</text>
                </view>
              </picker>
            </view>

            <view class="vet-row" style="margin-top: 16rpx;">
              <text class="vet-label">参赛组别：</text>
              <view class="grp-pill-group">
                <view
                  v-for="grp in GOBI_GROUPS"
                  :key="grp"
                  class="grp-pill"
                  :class="{ active: gobiGroup === grp }"
                  @click="onSelectGobiGroup(grp)"
                >
                  <text>{{ grp }}</text>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

      <!-- ── CARD: 赛事活动与装备保障 ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🎽</text>
          <text class="card-title">赛事与装备</text>
        </view>
        <text class="security-chip" style="background: rgba(99, 102, 241, 0.15); color: var(--rgm-blue, #a5b4fc); border-color: rgba(99, 102, 241, 0.3);">
          物资发放 · 保险
        </text>
      </view>

      <view class="form-grid-2">
        <!-- 紧急联系人及电话 -->
        <view class="form-group full-width-group">
          <text class="label">紧急联系人及电话</text>
          <input
            class="form-input"
            type="text"
            placeholder="例如: 张三 13900001111"
            :value="profile?.emergency_contact || ''"
            @input="onInputEmergencyContact"
          />
        </view>

        <!-- 队服尺码 -->
        <view class="form-group">
          <text class="label">队服尺码 (Clothing)</text>
          <picker
            mode="selector"
            :range="CLOTHING_SIZES"
            :value="CLOTHING_SIZES.indexOf(profile?.clothing_size) >= 0 ? CLOTHING_SIZES.indexOf(profile?.clothing_size) : 0"
            @change="onClothingSizeChange"
          >
            <view class="picker-input-box">
              <text :class="{ 'placeholder-text': !profile?.clothing_size }">
                {{ profile?.clothing_size || '请选择尺码' }}
              </text>
              <text class="picker-arrow">▼</text>
            </view>
          </picker>
        </view>

        <!-- 跑鞋尺码 -->
        <view class="form-group">
          <text class="label">跑鞋尺码 (Shoe EUR)</text>
          <input
            class="form-input"
            type="text"
            placeholder="例如 42 或 42.5"
            :value="profile?.shoe_size || ''"
            @input="onInputShoeSize"
          />
        </view>

        <!-- 急救 / 医护资质认证 (选填 · 用于官兔评估加权) -->
        <view class="form-group full-width-group">
          <text class="label">🚑 急救 / 医护资质（选填 · 马拉松官兔优先项）</text>
          <picker
            mode="selector"
            :range="FIRST_AID_CERT_LABELS"
            :value="firstAidPickerIndex"
            @change="onFirstAidCertChange"
          >
            <view class="picker-input-box">
              <text :class="{ 'placeholder-text': !profile?.first_aid_cert_type }">
                {{ FIRST_AID_CERT_LABELS[firstAidPickerIndex] || '暂未持有急救证书' }}
              </text>
              <text class="picker-arrow">▼</text>
            </view>
          </picker>
        </view>

        <!-- 健康状况声明 -->
        <view class="form-group full-width-group">
          <view
            class="health-decl-box"
            :class="{ active: profile?.health_declaration !== false }"
            @click="onToggleHealthDeclaration"
          >
            <view class="health-checkbox">
              <text class="check-mark">{{ profile?.health_declaration !== false ? '✓' : '' }}</text>
            </view>
            <view class="health-decl-texts">
              <text class="health-title">健康状况与免责声明确认</text>
              <text class="health-desc">
                本人身体健康，无高血压、心脑血管疾病、糖尿病或其他不适宜参加长距离剧烈耐力跑之疾病，具备参加跑步训练及马拉松、戈壁越野拉练的身体条件。自愿遵从教练团队安全指引与急救规范。
              </text>
            </view>
          </view>
        </view>
      </view>
    </view>

    </view>

    </template>

    <!-- 子页面：通知与隐私 -->
    <template v-if="activeSection === 'privacy'">
      <!-- ── CARD: 🔔 微信接收 Canova教练跑后点评推送 ── -->
    <view class="section-card wechat-notif-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🔔</text>
          <text class="card-title">教练点评推送</text>
        </view>
        <view class="notif-status-badge" :class="{ enabled: wechatSubscribeEnabled }">
          <text class="status-dot" />
          <text class="status-text">{{ wechatSubscribeEnabled ? '已开启提醒' : '未授权' }}</text>
        </view>
      </view>

      <view class="wechat-notif-actions">
        <button class="enable-subscribe-btn" @click="handleRequestSubscribe">
          📲 开启微信提醒
        </button>
        <button class="test-subscribe-btn" :loading="testingPush" @click="handleTestWechatPush">
          🧪 测试推送
        </button>
      </view>
    </view>

      <!-- ── CARD: 🔒 跑团训练与身体数据保密设定（仅对教练和师傅开放） ── -->
    <view v-if="user" class="section-card privacy-guard-card" style="margin-bottom: 24rpx;">
      <view class="card-title-row">
        <view class="title-with-badge">
          <text class="card-title">🔒 数据保密设置</text>
          <text class="security-chip" style="background: rgba(16, 185, 129, 0.14); color: var(--rgm-green, #34d399); border-color: rgba(16, 185, 129, 0.35);">仅对教练与师傅开放</text>
        </view>
      </view>

      <view style="display: flex; align-items: center; justify-content: space-between; padding: 20rpx; background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16rpx; margin-bottom: 16rpx;">
        <view style="flex: 1; padding-right: 20rpx;">
          <text style="font-size: 27rpx; font-weight: 700; color: var(--rgm-text, #ffffff); display: block; margin-bottom: 6rpx;">
            🗺️ GPS 路线保密
          </text>
        </view>
        <switch
          :checked="!!profile?.hide_gps_route"
          color="#10b981"
          @change="(e: any) => handleToggleDataConfidentiality('hide_gps_route', !!e.detail.value)"
        />
      </view>

      <view style="display: flex; align-items: center; justify-content: space-between; padding: 20rpx; background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16rpx;">
        <view style="flex: 1; padding-right: 20rpx;">
          <text style="font-size: 27rpx; font-weight: 700; color: var(--rgm-text, #ffffff); display: block; margin-bottom: 6rpx;">
            💓 心率/HRV/睡眠数据保密
          </text>
        </view>
        <switch
          :checked="!!profile?.hide_biometrics"
          color="#10b981"
          @change="(e: any) => handleToggleDataConfidentiality('hide_biometrics', !!e.detail.value)"
        />
      </view>
    </view>

      <!-- ── CARD: 🛡️ 个人隐私与数据安全保障 ── -->
    <view v-if="user" class="section-card privacy-guard-card">
      <view class="card-title-row">
        <view class="title-with-badge">
          <text class="card-title">🛡️ 隐私与数据安全</text>
          <text class="security-chip">AES-256 加密保护</text>
        </view>
      </view>

      <view class="privacy-statement-box">
        <view class="privacy-rule-item">
          <text class="privacy-rule-icon">🔒</text>
          <view class="privacy-rule-content">
            <text class="privacy-rule-title">敏感信息 AES-256 加密存储</text>
          </view>
        </view>

        <view class="privacy-rule-item">
          <text class="privacy-rule-icon">👁️</text>
          <view class="privacy-rule-content">
            <text class="privacy-rule-title">名册自动脱敏</text>
          </view>
        </view>

        <view class="privacy-rule-item">
          <text class="privacy-rule-icon">🧹</text>
          <view class="privacy-rule-content">
            <text class="privacy-rule-title">可随时清除个人隐私</text>
          </view>
        </view>
      </view>

      <view class="privacy-actions-row">
        <button class="purge-privacy-btn" :loading="purgingPrivacy" @click="handleConfirmPurgePrivacy">
          🧹 清除个人隐私数据
        </button>
      </view>
    </view>

    </template>

    <!-- 子页面：帮助与技术支持 -->
    <template v-if="activeSection === 'support'">
      <!-- 1. 微信一对一在线客服卡片 -->
      <view class="section-card support-card">
        <view class="card-title-row">
          <view class="title-with-icon">
            <text class="title-icon">💬</text>
            <text class="card-title">在线客服</text>
          </view>
        </view>

        <!-- 账号与设备诊断摘要（一键复制，方便粘贴给客服） -->
        <view class="support-diag-box" @click="handleCopyDiagnosticInfo">
          <view class="sdiag-left">
            <text class="sdiag-label">诊断信息</text>
            <text class="sdiag-val">跑者：{{ profile?.display_name || user?.display_name || '微信跑者' }}</text>
            <text class="sdiag-val">手表：{{ deviceStatusText }}</text>
          </view>
          <view class="sdiag-copy-pill">
            <text>📋 复制</text>
          </view>
        </view>

        <button
          class="support-contact-btn"
          open-type="contact"
          :session-from="supportSessionFrom"
          send-message-title="万跑跑团助手 · 技术支持"
        >
          💬 联系客服
        </button>
      </view>

      <!-- 2. 站内问题反馈留言表单（自动携带诊断信息） -->
      <view class="section-card support-card">
        <view class="card-title-row">
          <view class="title-with-icon">
            <text class="title-icon">📝</text>
            <text class="card-title">问题留言</text>
          </view>
        </view>

        <view class="support-cat-row">
          <view
            v-for="cat in SUPPORT_CATEGORIES"
            :key="cat.value"
            class="support-cat-chip"
            :class="{ active: supportCategory === cat.value }"
            @click="supportCategory = cat.value"
          >
            <text>{{ cat.label }}</text>
          </view>
        </view>

        <textarea
          class="support-textarea"
          placeholder="请详细描述您遇到的问题（例如：绑定佳明时提示密码错误、某次跑步轨迹未显示等）..."
          :maxlength="500"
          v-model="supportContent"
        />

        <input
          class="form-input support-contact-input"
          type="text"
          placeholder="选填：您的微信号或手机号（方便必要时联系您）"
          v-model="supportContact"
        />

        <button
          class="support-submit-btn"
          :loading="submittingTicket"
          :disabled="submittingTicket"
          @click="handleSubmitSupportTicket"
        >
          📨 提交问题留言
        </button>
      </view>

      <!-- 3. 我的反馈记录与管理员回复 -->
      <view v-if="mySupportTickets.length > 0" class="section-card support-card">
        <view class="card-title-row">
          <view class="title-with-icon">
            <text class="title-icon">📋</text>
            <text class="card-title">我的反馈记录 ({{ mySupportTickets.length }})</text>
          </view>
        </view>

        <view class="support-ticket-list">
          <view v-for="tkt in mySupportTickets" :key="tkt.id" class="support-ticket-item">
            <view class="stkt-header">
              <text class="stkt-cat">{{ getSupportCatLabel(tkt.category) }}</text>
              <text class="stkt-status" :class="{ resolved: tkt.status === 'resolved' || !!tkt.admin_reply }">
                {{ (tkt.status === 'resolved' || tkt.admin_reply) ? '✓ 已回复/已解决' : '⏳ 待处理' }}
              </text>
            </view>
            <text class="stkt-content">{{ tkt.content }}</text>
            <text class="stkt-time">提交于 {{ formatSupportTime(tkt.created_at) }}</text>

            <view v-if="tkt.admin_reply" class="stkt-reply-box">
              <text class="stkt-reply-title">👨‍💻 技术支持回复：</text>
              <text class="stkt-reply-text">{{ tkt.admin_reply }}</text>
            </view>
          </view>
        </view>
      </view>
    </template>

    <!-- 子页面「个人资料」专属保存按钮 -->
    <template v-if="activeSection === 'personal'">
          <!-- Tab 1 专属保存设置 -->
    <view v-if="user" class="save-box">
      <button class="save-btn" :loading="saving" @click="handleSaveAll">
        💾 保存个人资料
      </button>
    </view>

    </template>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!-- TAB 2: 训练档案与赛事 (Training Metrics & Races)              -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <!-- 子页面：训练档案与赛事 -->
    <template v-if="activeSection === 'training'">
      <!-- ── CARD 2: 个人最佳成绩 (PB) ── -->
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

      <!-- ── CARD 3: 运动体能与生理指标 ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">💓</text>
          <text class="card-title">生理指标</text>
        </view>
        <button
          class="import-garmin-btn"
          :loading="syncingDeviceProfile"
          :disabled="syncingDeviceProfile || (!garminConnected && !corosConnected)"
          @click="handleSyncDeviceProfile"
        >
          从手表同步指标
        </button>
      </view>

      <view class="form-grid-2">
        <!-- 最大摄氧量 VO2Max -->
        <view class="form-group">
          <view class="label-with-tag">
            <text class="label">最大摄氧量 (VO2Max)</text>
            <text v-if="(garminConnected || corosConnected || appleConnected || huaweiConnected) && profile?.vo2max" class="estimate-pill-btn" style="color: #059669; background: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.3);">⌚ 手表实测直读</text>
            <text v-else class="estimate-pill-btn" @click="handleEstimateVo2max">⚡ 依据 PB 测算</text>
          </view>
          <input
            class="form-input"
            type="digit"
            placeholder="例如 54.0"
            :value="profile?.vo2max || ''"
            @input="onInputVo2max"
          />
        </view>

        <!-- 身高 -->
        <view class="form-group">
          <text class="label">身高 (cm)</text>
          <input
            class="form-input"
            type="number"
            placeholder="175"
            :value="profile?.height || profile?.height_cm || ''"
            @input="onInputHeight"
          />
        </view>

        <!-- 体重 -->
        <view class="form-group">
          <text class="label">体重 (kg)</text>
          <input
            class="form-input"
            type="digit"
            placeholder="68.0"
            :value="profile?.weight || profile?.weight_kg || ''"
            @input="onInputWeight"
          />
        </view>

        <!-- 最大心率 -->
        <view class="form-group">
          <text class="label">最大心率 (Max HR)</text>
          <input
            class="form-input"
            type="number"
            placeholder="190"
            :value="profile?.max_heart_rate || ''"
            @input="onInputMaxHr"
          />
        </view>

        <!-- 静息心率 -->
        <view class="form-group">
          <text class="label">静息心率 (Rest HR)</text>
          <input
            class="form-input"
            type="number"
            placeholder="56"
            :value="profile?.resting_heart_rate || ''"
            @input="onInputRestHr"
          />
        </view>

        <!-- 跑龄 (年) -->
        <view class="form-group full-width-group">
          <text class="label">跑龄 (年)</text>
          <input
            class="form-input"
            type="number"
            placeholder="3"
            :value="profile?.years_running || ''"
            @input="onInputYearsRunning"
          />
        </view>
      </view>
    </view>

      <!-- ── CARD 4: 个人2026年度跑量规划 ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🎯</text>
          <text class="card-title">跑量目标 (2026)</text>
        </view>
        <view class="target-badge" :class="{ locked: goalMode === 'custom' }">
          {{ goalMode === 'custom' ? '按月自定义' : `全年统一: ${targetDistance} km/月` }}
        </view>
      </view>

      <!-- Goal Mode Switcher -->
      <view class="goal-mode-selector">
        <view
          class="goal-mode-btn"
          :class="{ active: goalMode === 'uniform' }"
          @click="setGoalMode('uniform')"
        >
          全年统一均值
        </view>
        <view
          class="goal-mode-btn"
          :class="{ active: goalMode === 'custom' }"
          @click="setGoalMode('custom')"
        >
          按月自定义
        </view>
      </view>

      <!-- Uniform Slider Controller -->
      <view class="slider-wrapper" :class="{ disabled: goalMode === 'custom' }">
        <slider
          :value="targetDistance"
          :min="50"
          :max="600"
          :step="10"
          :disabled="goalMode === 'custom'"
          activeColor="#fc4c02"
          backgroundColor="#2c2c2e"
          block-size="20"
          @change="(e: any) => onTargetSliderChange(e.detail.value)"
        />
        <text v-if="goalMode !== 'custom'" class="uniform-tip">
          每月 {{ targetDistance }} km
        </text>
      </view>

      <!-- 12 Months Grid -->
      <view class="custom-months-section">
        <view class="custom-months-header">
          <text class="cm-title">各月跑量 (km · 🔒1~{{ currentCalendarMonth }}月已锁定)</text>
          <text v-if="goalMode === 'custom'" class="sync-uniform-action" @click="syncUniformToAll">
            未开始月份设为 {{ targetDistance }}km
          </text>
        </view>

        <view class="months-grid">
          <view
            v-for="m in 12"
            :key="m"
            class="month-cell"
            :class="{ 'month-locked': m <= currentCalendarMonth }"
            @click="m <= currentCalendarMonth ? handleLockedMonthTap(m) : noop()"
          >
            <text class="month-label">{{ m }}月 {{ m <= currentCalendarMonth ? '🔒' : '✏️' }}</text>
            <input
              class="month-input"
              :class="{ 'month-input-disabled': m <= currentCalendarMonth }"
              type="number"
              :disabled="m <= currentCalendarMonth"
              :value="monthlyTargets[m - 1]"
              @input="(e: any) => onMonthTargetInput(m - 1, e.detail.value)"
            />
          </view>
        </view>
      </view>

      <!-- ── 周跑量常规计划 (Weekly Target Plan) ── -->
      <view class="weekly-plan-section">
        <view class="custom-months-header">
          <view class="title-with-icon">
            <text class="cm-title">🏃 周跑量计划</text>
          </view>
          <text class="weekly-target-badge">下周计划 {{ weeklyTarget }} km / 周</text>
        </view>
        <text class="weekly-desc-tip">
          🔒 本周 {{ currentWeekLockedTarget }} km 已锁定，修改自下周生效
        </text>

        <!-- Quick selection pills -->
        <view class="weekly-quick-pills">
          <view
            v-for="km in [30, 40, 50, 60, 70, 80, 100]"
            :key="km"
            class="weekly-pill"
            :class="{ active: weeklyTarget === km }"
            @click="setWeeklyTarget(km)"
          >
            {{ km }}k
          </view>
        </view>

        <!-- Weekly Slider -->
        <view class="slider-wrapper">
          <slider
            :value="weeklyTarget"
            :min="10"
            :max="160"
            :step="5"
            activeColor="#10b981"
            backgroundColor="#2c2c2e"
            block-size="20"
            @change="(e: any) => onWeeklySliderChange(e.detail.value)"
          />
          <text class="uniform-tip">
            {{ weeklyTarget }} km/周 ≈ 月均 {{ Math.round(weeklyTarget * 4.3) }} km
          </text>
        </view>

        <view class="weekly-save-action">
          <button class="save-weekly-btn" :loading="savingWeekly" @click="handleSaveWeeklyOnly">
            保存周计划 ({{ weeklyTarget }}km)
          </button>
        </view>
      </view>
    </view>

    <!-- Tab 2 专属保存设置 (置于跑量目标配置下方，一目了然触手可及) -->
    <view v-if="user" class="save-box">
      <button class="save-btn" :loading="saving" @click="handleSaveAll">
        🎯 保存训练档案
      </button>
    </view>

    <!-- ── CARD 1: 比赛计划 (Race Plans) ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🏁</text>
          <text class="card-title">比赛计划</text>
        </view>
        <button class="add-race-header-btn" @click="openAddRaceModal">+ 添加比赛</button>
      </view>

      <view v-if="races.length" class="race-list">
        <view v-for="(race, idx) in races" :key="race.id || idx" class="race-item">
          <view class="race-top">
            <view class="race-name-group">
              <text class="race-name">{{ race.name }}</text>
              <text class="race-priority-tag" :class="`p-tag-${race.priority == 1 || race.priority === 'A' ? 'a' : race.priority == 2 || race.priority === 'B' ? 'b' : 'c'}`">
                {{ race.priority == 1 || race.priority === 'A' ? 'A 标' : race.priority == 2 || race.priority === 'B' ? 'B 标' : 'C 标' }}
              </text>
            </view>
            <view class="race-top-right">
              <view v-if="race.status === 'completed' || race.is_completed" class="race-badge completed-badge">
                <text class="badge-text">🏅 已完赛</text>
              </view>
              <view v-else class="race-badge" :class="{ urgent: race.days_left < 30 }">
                <text class="badge-text">{{ race.days_left }} 天{{ race.days_left < 30 ? " 冲刺" : "" }}</text>
              </view>
              <view class="race-quick-actions">
                <view
                  v-if="race.status === 'completed' || race.is_completed"
                  class="race-action-pill share-race-pill"
                  @click.stop="openCompletedRaceShareCard(race)"
                >
                  <text class="pill-text">📸 完赛分享卡</text>
                </view>
                <view class="race-action-pill edit-pill" @click.stop="openEditRaceModal(race)">
                  <text class="pill-text">{{ (race.status === 'completed' || race.is_completed) ? '🏅 记录' : '✏️ 编辑' }}</text>
                </view>
                <view class="race-action-pill del-pill" @click.stop="handleDeleteRace(race)">
                  <text class="pill-text">🗑️</text>
                </view>
              </view>
            </view>
          </view>
          <view class="race-meta-row">
            <text class="race-type-tag">{{ race.race_type }}</text>
            <text class="race-date">{{ race.race_date }}</text>
            <text class="race-target">目标: {{ race.target_time }}</text>
            <text v-if="race.finish_time" class="race-finish-time-tag">完赛: {{ race.finish_time }}</text>
          </view>

          <!-- Completed Race Summary Banner in Card -->
          <view v-if="race.status === 'completed' || race.is_completed" class="race-completed-card-banner">
            <view class="completed-summary-row">
              <text class="comp-badge-tag">{{ race.performance_badge || '顺利完赛' }}</text>
              <text v-if="race.diff_str" class="comp-diff-text">比目标 {{ race.diff_str }}</text>
              <view class="comp-share-card-btn" @click.stop="openCompletedRaceShareCard(race)">
                <text class="comp-share-card-txt">📸 完赛分享卡</text>
              </view>
            </view>
            <text v-if="race.finish_notes" class="comp-notes-text">“{{ race.finish_notes }}”</text>
            <!-- Photos row in card -->
            <view class="card-photos-scroll">
              <image
                v-for="(pUrl, pIdx) in (race.photos || [])"
                :key="pIdx"
                class="card-photo-thumb"
                :src="pUrl"
                mode="aspectFill"
                @click.stop="handlePreviewImage(pUrl, race.photos)"
                @longpress.stop="handleCardPhotoAction(pUrl, race)"
              />
              <view class="card-add-photo-btn" @click.stop="handleCardQuickUploadPhoto(race)">
                <text class="card-add-icon">📷</text>
                <text class="card-add-txt">加照片</text>
              </view>
            </view>
          </view>
          <view v-else-if="race.is_past" class="race-past-tip" @click.stop="openEditRaceModal(race)">
            <text class="past-tip-text">⚠️ 比赛日已过，去填报成绩 ➔</text>
          </view>
          <view class="race-priority-row">
            <text class="race-priority-lbl">定位调整:</text>
            <view class="priority-actions">
              <button
                class="min-p-btn"
                :class="{ active: race.priority == 1 || race.priority === 'A' }"
                @click="handleUpdateRacePriority(race.id || race.name, 1)"
              >A 标 (核心)</button>
              <button
                class="min-p-btn"
                :class="{ active: race.priority == 2 || race.priority === 'B' }"
                @click="handleUpdateRacePriority(race.id || race.name, 2)"
              >B 标 (代练)</button>
              <button
                class="min-p-btn"
                :class="{ active: race.priority == 3 || race.priority === 'C' }"
                @click="handleUpdateRacePriority(race.id || race.name, 3)"
              >C 标 (拉练)</button>
            </view>
          </view>

          <!-- ── Race Intelligence Collapsible Panel ── -->
          <view class="race-info-toggle-row">
            <view class="race-info-toggle-trigger" @click="toggleRaceInfo(getRaceKey(race, idx))">
              <text class="race-info-toggle-label">
                {{ hasRaceInfo(race) ? '📋 赛事情报 · 已填' : '📋 赛事情报 · 未填' }}
              </text>
              <text class="race-info-toggle-arrow">{{ expandedRaceInfo[getRaceKey(race, idx)] ? '▲' : '▼' }}</text>
            </view>
            <button
              class="race-ai-fetch-btn"
              :loading="searchingRaceInfo[getRaceKey(race, idx)]"
              :disabled="searchingRaceInfo[getRaceKey(race, idx)]"
              @click.stop="handleAutoFetchRaceInfo(race)"
            >⚡ 自动填情报</button>
          </view>

          <view v-if="expandedRaceInfo[getRaceKey(race, idx)]" class="race-info-panel">


            <!-- ── 越野赛专属字段 ── -->
            <template v-if="isTrail(race.race_type)">
              <text class="race-info-section-title">🏔️ 越野赛情报</text>


              <view class="race-info-row">
                <text class="race-info-label">报名赛程 (km)</text>
                <input
                  class="race-info-input"
                  type="digit"
                  placeholder="如 50 / 100"
                  :value="getRaceInfoVal(race, 'race_distance_km')"
                  @input="(e: any) => setRaceInfoVal(race, 'race_distance_km', parseFloat(e.detail.value) || null)"
                />
              </view>
              <view class="race-info-row">
                <text class="race-info-label">累计爬升 D+ (m)</text>
                <input
                  class="race-info-input"
                  type="digit"
                  placeholder="如 2800"
                  :value="getRaceInfoVal(race, 'elevation_gain_m')"
                  @input="(e: any) => setRaceInfoVal(race, 'elevation_gain_m', parseFloat(e.detail.value) || null)"
                />
              </view>
              <view class="race-info-row">
                <text class="race-info-label">累计下降 D- (m)</text>
                <input
                  class="race-info-input"
                  type="digit"
                  placeholder="如 2600"
                  :value="getRaceInfoVal(race, 'elevation_loss_m')"
                  @input="(e: any) => setRaceInfoVal(race, 'elevation_loss_m', parseFloat(e.detail.value) || null)"
                />
              </view>
              <view class="race-info-row">
                <text class="race-info-label">最高海拔 (m)</text>
                <input
                  class="race-info-input"
                  type="digit"
                  placeholder="如 1918"
                  :value="getRaceInfoVal(race, 'max_altitude_m')"
                  @input="(e: any) => setRaceInfoVal(race, 'max_altitude_m', parseFloat(e.detail.value) || null)"
                />
              </view>

              <view class="race-info-row">
                <text class="race-info-label">难度等级</text>
                <picker
                  mode="selector"
                  :range="difficultyOptions"
                  :value="difficultyOptions.indexOf(getRaceInfoVal(race, 'difficulty_level') || '')"
                  @change="(e: any) => setRaceInfoVal(race, 'difficulty_level', difficultyOptions[e.detail.value])"
                >
                  <view class="race-info-picker">
                    <text>{{ getRaceInfoVal(race, 'difficulty_level') || '请选择' }}</text>
                    <text class="picker-arrow-sm">▾</text>
                  </view>
                </picker>
              </view>

              <view class="race-info-row">
                <text class="race-info-label">地形类型</text>
                <picker
                  mode="selector"
                  :range="trailTerrainOptions"
                  :value="trailTerrainOptions.indexOf(getRaceInfoVal(race, 'terrain_type') || '')"
                  @change="(e: any) => setRaceInfoVal(race, 'terrain_type', trailTerrainOptions[e.detail.value])"
                >
                  <view class="race-info-picker">
                    <text>{{ getRaceInfoVal(race, 'terrain_type') || '请选择' }}</text>
                    <text class="picker-arrow-sm">▾</text>
                  </view>
                </picker>
              </view>

              <view class="race-info-row">
                <text class="race-info-label">气候带</text>
                <picker
                  mode="selector"
                  :range="climateZoneOptions"
                  :value="climateZoneOptions.indexOf(getRaceInfoVal(race, 'climate_zone') || '')"
                  @change="(e: any) => setRaceInfoVal(race, 'climate_zone', climateZoneOptions[e.detail.value])"
                >
                  <view class="race-info-picker">
                    <text>{{ getRaceInfoVal(race, 'climate_zone') || '请选择' }}</text>
                    <text class="picker-arrow-sm">▾</text>
                  </view>
                </picker>
              </view>

              <view class="race-info-row">
                <text class="race-info-label">强制装备要求</text>
                <input
                  class="race-info-input"
                  placeholder="如: 头灯、1.5L水、急救毯"
                  :value="getRaceInfoVal(race, 'mandatory_gear')"
                  @input="(e: any) => setRaceInfoVal(race, 'mandatory_gear', e.detail.value)"
                />
              </view>
              <view class="race-info-row">
                <text class="race-info-label">关门时间说明</text>
                <input
                  class="race-info-input"
                  placeholder="如: 总关门 20小时，中途补给站 4个"
                  :value="getRaceInfoVal(race, 'cutoff_notes')"
                  @input="(e: any) => setRaceInfoVal(race, 'cutoff_notes', e.detail.value)"
                />
              </view>
            </template>

            <!-- ── 公路赛通用字段（全马/半马/10K/5K）── -->
            <template v-else>
              <text class="race-info-section-title">🏅 赛事情报</text>

              <view class="race-info-row">
                <text class="race-info-label">赛事等级</text>
                <picker
                  mode="selector"
                  :range="raceLevelOptions"
                  :value="raceLevelOptions.indexOf(getRaceInfoVal(race, 'race_level') || '')"
                  @change="(e: any) => setRaceInfoVal(race, 'race_level', raceLevelOptions[e.detail.value])"
                >
                  <view class="race-info-picker">
                    <text>{{ getRaceInfoVal(race, 'race_level') || '请选择' }}</text>
                    <text class="picker-arrow-sm">▾</text>
                  </view>
                </picker>
              </view>

              <view class="race-info-row">
                <text class="race-info-label">赛道特点</text>
                <picker
                  mode="selector"
                  :range="courseProfileOptions"
                  :value="courseProfileOptions.indexOf(getRaceInfoVal(race, 'course_profile') || '')"
                  @change="(e: any) => setRaceInfoVal(race, 'course_profile', courseProfileOptions[e.detail.value])"
                >
                  <view class="race-info-picker">
                    <text>{{ getRaceInfoVal(race, 'course_profile') || '请选择' }}</text>
                    <text class="picker-arrow-sm">▾</text>
                  </view>
                </picker>
              </view>

              <view class="race-info-row">
                <text class="race-info-label">路面材质</text>
                <picker
                  mode="selector"
                  :range="courseSurfaceOptions"
                  :value="courseSurfaceOptions.indexOf(getRaceInfoVal(race, 'course_surface') || '')"
                  @change="(e: any) => setRaceInfoVal(race, 'course_surface', courseSurfaceOptions[e.detail.value])"
                >
                  <view class="race-info-picker">
                    <text>{{ getRaceInfoVal(race, 'course_surface') || '请选择' }}</text>
                    <text class="picker-arrow-sm">▾</text>
                  </view>
                </picker>
              </view>

              <view class="race-info-row">
                <text class="race-info-label">报名赛程 (km)</text>
                <input
                  class="race-info-input"
                  type="digit"
                  placeholder="如 42.195 / 21.0975 / 10"
                  :value="getRaceInfoVal(race, 'race_distance_km')"
                  @input="(e: any) => setRaceInfoVal(race, 'race_distance_km', parseFloat(e.detail.value) || null)"
                />
              </view>
              <view class="race-info-row">
                <text class="race-info-label">累计爬升 D+ (m)</text>
                <input
                  class="race-info-input"
                  type="digit"
                  placeholder="如 50"
                  :value="getRaceInfoVal(race, 'elevation_gain_m') || getRaceInfoVal(race, 'net_elevation_gain_m')"
                  @input="(e: any) => { const v = parseFloat(e.detail.value) || null; setRaceInfoVal(race, 'elevation_gain_m', v); setRaceInfoVal(race, 'net_elevation_gain_m', v); }"
                />
              </view>
              <view class="race-info-row">
                <text class="race-info-label">累计下降 D- (m)</text>
                <input
                  class="race-info-input"
                  type="digit"
                  placeholder="如 50"
                  :value="getRaceInfoVal(race, 'elevation_loss_m')"
                  @input="(e: any) => setRaceInfoVal(race, 'elevation_loss_m', parseFloat(e.detail.value) || null)"
                />
              </view>
              <view class="race-info-row">
                <text class="race-info-label">关门时间说明</text>
                <input
                  class="race-info-input"
                  placeholder="如: 全马6小时15分"
                  :value="getRaceInfoVal(race, 'cutoff_notes')"
                  @input="(e: any) => setRaceInfoVal(race, 'cutoff_notes', e.detail.value)"
                />
              </view>
            </template>

            <!-- ── 通用天气与规模字段 ── -->
            <text class="race-info-section-title" style="margin-top: 18rpx;">🌤️ 天气 & 规模</text>
            <view class="race-info-row">
              <text class="race-info-label">历史平均气温 (℃)</text>
              <input
                class="race-info-input"
                type="digit"
                placeholder="如 12"
                :value="getRaceInfoVal(race, 'avg_temp_c')"
                @input="(e: any) => setRaceInfoVal(race, 'avg_temp_c', parseFloat(e.detail.value) || null)"
              />
            </view>
            <view v-if="!isTrail(race.race_type)" class="race-info-row">
              <text class="race-info-label">历史平均湿度 (%)</text>
              <input
                class="race-info-input"
                type="digit"
                placeholder="如 65"
                :value="getRaceInfoVal(race, 'humidity_pct')"
                @input="(e: any) => setRaceInfoVal(race, 'humidity_pct', parseFloat(e.detail.value) || null)"
              />
            </view>
            <view class="race-info-row">
              <text class="race-info-label">天气情况备注</text>
              <input
                class="race-info-input"
                placeholder="如: 秋季举办，通常干燥清凉"
                :value="getRaceInfoVal(race, 'weather_notes')"
                @input="(e: any) => setRaceInfoVal(race, 'weather_notes', e.detail.value)"
              />
            </view>
            <view class="race-info-row">
              <text class="race-info-label">大致参赛人数</text>
              <input
                class="race-info-input"
                type="digit"
                placeholder="如 10000"
                :value="getRaceInfoVal(race, 'typical_participants')"
                @input="(e: any) => setRaceInfoVal(race, 'typical_participants', parseInt(e.detail.value) || null)"
              />
            </view>
            <view class="race-info-row">
              <text class="race-info-label">其他备注</text>
              <input
                class="race-info-input"
                placeholder="其他补充说明"
                :value="getRaceInfoVal(race, 'custom_notes')"
                @input="(e: any) => setRaceInfoVal(race, 'custom_notes', e.detail.value)"
              />
            </view>

            <button
              class="race-info-save-btn"
              :loading="savingRaceInfo[getRaceKey(race, idx)]"
              :disabled="savingRaceInfo[getRaceKey(race, idx)]"
              @click="handleSaveRaceInfo(race)"
            >保存赛事情报</button>
          </view>
          <!-- ── End Race Intelligence Panel ── -->
        </view>
      </view>
      <view v-else class="empty-race">
        <text class="desc-text">暂无比赛计划</text>
        <button class="add-race-empty-btn" @click="openAddRaceModal">+ 添加比赛</button>
      </view>
    </view>

    <!-- Tab 2 专属保存设置（底部备用） -->
    <view v-if="user" class="save-box save-box-bottom">
      <button class="save-btn" :loading="saving" @click="handleSaveAll">
        🎯 保存训练档案
      </button>
    </view>
    </template>

    <!-- ── 微信授权登录专属弹窗 (Pure WeChat Login Modal) ── -->
    <view v-if="showAuthModal" class="modal-mask auth-modal-mask" @click="closeAuthModal">
      <view class="modal-content auth-modal-content" @click.stop="noop">
        <view class="modal-header">
          <text class="modal-title">{{ user ? "微信跑者账号管理" : "微信一键授权登录" }}</text>
          <view class="close-hit" @click="closeAuthModal">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <scroll-view scroll-y class="auth-scroll-body">
          <view class="modal-body">
          <view class="wx-brand-hero">
            <image class="wx-hero-logo" src="/static/logo-square.png" mode="aspectFit" />
            <text class="wx-hero-title">万跑跑团助手</text>
          </view>

          <!-- 1. 当前已登录会话简况 -->
          <view v-if="user" class="wx-account-status-card">
            <view class="status-top-row">
              <view class="status-user-info">
                <text class="status-title">当前登录跑者：</text>
                <text class="status-val bold">{{ profile?.display_name || user.display_name || "微信跑者" }}</text>
              </view>
              <button class="status-logout-btn" @click="handleConfirmLogout">退出登录</button>
            </view>
            <view class="status-row" style="margin-top: 16rpx;">
              <text class="status-label">手表连接: </text>
              <text class="status-val text-green" v-if="garminConnected">佳明已绑定 ({{ garminEmail || '账号' }})</text>
              <text class="status-val text-green" v-else-if="corosConnected">高驰已绑定 ({{ corosAccount || '账号' }})</text>
              <text class="status-val text-green" v-else-if="appleWatchConnected || huaweiConnected || suuntoConnected">苹果 / 华为 / 颂拓已激活</text>
              <text class="status-val text-muted" v-else>未绑定运动设备</text>
            </view>
          </view>

          <!-- 未登录状态：展示登录切换 Tab 与登录表单 -->
          <view v-else>
            <!-- 登录模式切换 Tab -->
            <view class="auth-tab-row">
              <view
                class="auth-tab-item"
                :class="{ active: authTab === 'wechat' }"
                @click="authTab = 'wechat'"
              >
                <text>新跑者微信授权</text>
              </view>
              <view
                class="auth-tab-item"
                :class="{ active: authTab === 'device' }"
                @click="authTab = 'device'"
              >
                <text>🔐 已有手表账号登录</text>
              </view>
            </view>

            <!-- 模式 1: 微信独立授权登录 -->
            <view v-if="authTab === 'wechat'" class="auth-flow-box">
              <view class="auth-intro-box">
                <text class="auth-intro-title">🛡️ 微信授权登录</text>
              </view>

              <!-- 微信原生头像与微信昵称快捷获取 -->
              <view class="custom-user-form">
                <view class="avatar-nickname-flex">
                  <button
                    class="wx-avatar-btn"
                    open-type="chooseAvatar"
                    @chooseavatar="onChooseAvatar"
                  >
                    <image
                      class="wx-avatar-preview"
                      :src="runnerAvatar || defaultAvatar"
                      mode="aspectFill"
                    />
                    <text class="avatar-badge-tip">选微信头像</text>
                  </button>

                  <view class="nickname-input-box">
                    <text class="field-label">微信昵称</text>
                    <input
                      type="nickname"
                      class="large-input nickname-input"
                      :value="runnerNickName"
                      placeholder="点击此处，从键盘快捷填入"
                      placeholder-class="placeholder-style"
                      @blur="onNicknameBlur"
                      @input="onNicknameInput"
                    />
                  </view>
                </view>
              </view>

              <!-- 用户协议与隐私条款勾选 (必须勾选) -->
              <view class="terms-check-row" @click="agreedTerms = !agreedTerms">
                <text class="checkbox-icon">{{ agreedTerms ? '☑️' : '⬜' }}</text>
                <view class="terms-text-wrap">
                  <text class="terms-text">我已阅读并同意 </text>
                  <text class="terms-link" @click.stop="showTermsModal">《用户服务条款》</text>
                  <text class="terms-text"> 与 </text>
                  <text class="terms-link" @click.stop="showPrivacyModal">《隐私政策》</text>
                </view>
              </view>

              <!-- 确认登录大按钮 -->
              <button
                class="confirm-auth-btn"
                :loading="confirmingLogin"
                @click="doConfirmLogin"
              >
                🟢 授权并创建新跑者身份
              </button>

              <!-- #ifdef APP-PLUS -->
              <button
                class="apple-auth-modal-btn"
                @click="handleAppleLogin"
                style="margin-top: 20rpx; background: #000000; color: #ffffff; border: 1px solid var(--rgm-line, rgba(255,255,255,0.25)); border-radius: 12rpx; font-size: 28rpx; height: 84rpx; line-height: 84rpx; display: flex; align-items: center; justify-content: center; font-weight: 600;   --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2); "
              >
                 通过 Apple 登录 (Sign in with Apple)
              </button>
              <!-- #endif -->
            </view>

            <!-- 模式 2: 已有手表账号验证登录 / 档案恢复 -->
            <view v-else class="auth-flow-box device-login-box">
              <view class="auth-intro-box">
                <text class="auth-intro-title">🔐 手表账号验证恢复档案</text>
              </view>

              <!-- 品牌切换 -->
              <view class="brand-tab-group">
                <view
                  class="brand-tab-btn"
                  :class="{ active: deviceBrand === 'garmin' }"
                  @click="deviceBrand = 'garmin'"
                >
                  <text> Garmin 佳明</text>
                </view>
                <view
                  class="brand-tab-btn"
                  :class="{ active: deviceBrand === 'coros' }"
                  @click="deviceBrand = 'coros'"
                >
                  <text> COROS 高驰</text>
                </view>
              </view>

              <!-- Garmin 区域选择 -->
              <view v-if="deviceBrand === 'garmin'" class="domain-select-box">
                <text class="domain-label">佳明账号服务器：</text>
                <view class="domain-btn-wrap">
                  <view
                    class="domain-chip"
                    :class="{ active: deviceDomain === 'garmin.cn' }"
                    @click="deviceDomain = 'garmin.cn'"
                  >
                    <text>中国区 (.cn)</text>
                  </view>
                  <view
                    class="domain-chip"
                    :class="{ active: deviceDomain === 'garmin.com' }"
                    @click="deviceDomain = 'garmin.com'"
                  >
                    <text>国际区 (.com)</text>
                  </view>
                </view>
              </view>

              <!-- 账号密码表单 -->
              <view class="device-form">
                <view class="device-form-item">
                  <text class="field-label">{{ deviceBrand === 'garmin' ? '佳明注册邮箱' : '高驰账号 / 手机号' }}</text>
                  <input
                    class="large-input"
                    :value="deviceAccount"
                    :placeholder="deviceBrand === 'garmin' ? '例如 runner@example.com' : '请输入高驰账号'"
                    placeholder-class="placeholder-style"
                    @input="deviceAccount = $event.detail.value; deviceNeedsMfa = false"
                  />
                </view>

                <view class="device-form-item">
                  <text class="field-label">密码</text>
                  <input
                    type="password"
                    class="large-input"
                    :value="devicePassword"
                    placeholder="请输入手表账号密码"
                    placeholder-class="placeholder-style"
                    @input="devicePassword = $event.detail.value"
                  />
                </view>

                <view v-if="deviceNeedsMfa" class="device-form-item">
                  <text class="field-label" style="color: #fbbf24;">📱 6位安全验证码（短信 / 邮箱）</text>
                  <input
                    type="number"
                    maxlength="6"
                    class="large-input"
                    :value="deviceMfaCode"
                    placeholder="请输入收到的 6 位安全验证码"
                    placeholder-class="placeholder-style"
                    @input="deviceMfaCode = $event.detail.value"
                  />
                  <text v-if="deviceMfaHint" style="font-size: 21rpx; color: #fbbf24; margin-top: 6rpx; display: block;">
                    {{ deviceMfaHint }}
                  </text>
                </view>
              </view>

              <!-- 登录按钮 -->
              <button
                class="confirm-auth-btn device-confirm-btn"
                :loading="deviceLoggingIn"
                @click="doDeviceLogin"
              >
                {{ deviceNeedsMfa ? "✅ 提交验证码并登录" : "🔐 验证账号并恢复跑者档案" }}
              </button>
            </view>
          </view>
        </view>
        </scroll-view>
      </view>
    </view>

    <!-- Large & Modern Device Bind Modal (Garmin · COROS · Apple Watch · HUAWEI) -->
    <view v-if="showGarminModal" class="modal-mask" @click="showGarminModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">连接手表</text>
          <view class="close-hit" @click="showGarminModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <!-- 弹窗内 24 小时佩戴提示 -->
        <view style="background: rgba(245, 158, 11, 0.14); border: 1rpx solid rgba(245, 158, 11, 0.45); border-radius: 14rpx; padding: 16rpx 20rpx; margin: 0 0 20rpx 0;">
          <text style="display: block; font-size: 24rpx; font-weight: 700; color: #b45309;">
            ⚠️ 请保持 24 小时佩戴手表（含夜间睡眠）
          </text>
        </view>

        <!-- 3-Group Brand Switcher Grid -->
        <view class="brand-switch-grid-4">
          <view
            class="brand-switch-btn brand-garmin"
            :class="{ active: selectedBrand === 'garmin' }"
            @click="selectedBrand = 'garmin'"
          >
            Garmin 佳明
          </view>
          <view
            class="brand-switch-btn brand-coros"
            :class="{ active: selectedBrand === 'coros' }"
            @click="selectedBrand = 'coros'"
          >
            COROS 高驰
          </view>
          <view
            class="brand-switch-btn brand-apple"
            style="grid-column: span 2;"
            :class="{ active: selectedBrand === 'apple_watch' || selectedBrand === 'huawei' || selectedBrand === 'suunto' }"
            @click="selectedBrand = 'apple_watch'"
          >
            ⌚ 苹果 / 华为 / 颂拓
          </view>
        </view>

        <view class="modal-body">
          <!-- ── GARMIN TAB ── -->
          <view v-if="selectedBrand === 'garmin'">
            <!-- MFA Verification Step -->
            <view v-if="needsMfa" class="mfa-section">
              <view class="mfa-alert-box">
                <text class="mfa-alert-title">🔒 佳明安全验证</text>
                <text class="mfa-alert-desc">验证码已发送至您的注册邮箱或手机</text>
              </view>
              <text class="field-label">6 位安全验证码</text>
              <input
                class="large-input center-input"
                type="number"
                maxlength="6"
                :adjust-position="false"
                :cursor-spacing="30"
                placeholder="请输入 6 位验证码"
                placeholder-class="placeholder-style"
                v-model="inputMfaCode"
              />
              <button class="large-primary-btn" :loading="binding" @click="handleBindGarmin">
                确认绑定
              </button>
              <button class="text-cancel-btn" @click="needsMfa = false">
                返回修改账号
              </button>
            </view>

            <!-- Standard Garmin Credential Step -->
            <view v-else>
              <text class="field-label">佳明账号所属区域</text>
              <view class="domain-selector">
                <view
                  class="domain-btn"
                  :class="{ active: inputDomain === 'garmin.cn' }"
                  @click="inputDomain = 'garmin.cn'"
                >
                  中国区 (garmin.cn)
                </view>
                <view
                  class="domain-btn"
                  :class="{ active: inputDomain === 'garmin.com' }"
                  @click="inputDomain = 'garmin.com'"
                >
                  国际区 (garmin.com)
                </view>
              </view>

              <text class="field-label">佳明注册邮箱 / 账号</text>
              <input
                class="large-input"
                type="text"
                :adjust-position="false"
                :cursor-spacing="30"
                placeholder="例如 user@example.com"
                placeholder-class="placeholder-style"
                v-model="inputEmail"
              />

              <text class="field-label">佳明登录密码</text>
              <input
                class="large-input"
                type="password"
                :adjust-position="false"
                :cursor-spacing="30"
                placeholder="请输入您的 Garmin Connect 密码"
                placeholder-class="placeholder-style"
                v-model="inputPassword"
              />

              <button class="large-primary-btn" :loading="binding" @click="handleBindGarmin">
                连接佳明
              </button>
            </view>
          </view>

          <!-- ── COROS TAB ── -->
          <view v-else-if="selectedBrand === 'coros'">
            <!-- COROS 2FA Verification Step -->
            <view v-if="needsCoros2fa" class="mfa-section">
              <view class="mfa-alert-box coros-mfa-box">
                <text class="mfa-alert-title">🔒 高驰安全验证</text>
                <text class="mfa-alert-desc">验证码已发送至您的注册手机</text>
              </view>
              <text class="field-label">6 位手机验证码</text>
              <input
                class="large-input center-input"
                type="number"
                maxlength="6"
                :adjust-position="false"
                :cursor-spacing="30"
                placeholder="请输入 6 位短信验证码"
                placeholder-class="placeholder-style"
                v-model="inputCoros2faCode"
              />
              <button class="large-primary-btn coros-primary-btn" :loading="bindingCoros" @click="handleBindCoros">
                确认绑定
              </button>
              <button class="text-cancel-btn" @click="needsCoros2fa = false">
                返回修改账号
              </button>
            </view>

            <!-- Standard COROS Credential Step -->
            <view v-else>
              <text class="field-label">高驰账号所属区域</text>
              <view class="domain-selector">
                <view
                  class="domain-btn"
                  :class="{ active: inputCorosDomain === 'teamcnapi.coros.com' }"
                  @click="inputCorosDomain = 'teamcnapi.coros.com'"
                >
                  中国区 (teamcnapi)
                </view>
                <view
                  class="domain-btn"
                  :class="{ active: inputCorosDomain === 'teamapi.coros.com' }"
                  @click="inputCorosDomain = 'teamapi.coros.com'"
                >
                  国际区 (teamapi)
                </view>
              </view>

              <text class="field-label">高驰注册账号（手机号或邮箱）</text>
              <input
                class="large-input"
                type="text"
                :adjust-position="false"
                :cursor-spacing="30"
                placeholder="例如 13800000000 或 user@email.com"
                placeholder-class="placeholder-style"
                v-model="inputCorosAccount"
              />

              <text class="field-label">
                {{
                  corosConnected && corosHasSavedPassword && inputCorosAccount.trim().toLowerCase() === corosAccount.trim().toLowerCase()
                    ? "高驰登录密码（未改密可留空，直接获取短信验证码）"
                    : "高驰登录密码"
                }}
              </text>
              <input
                class="large-input"
                type="password"
                :adjust-position="false"
                :cursor-spacing="30"
                :placeholder="
                  corosConnected && corosHasSavedPassword && inputCorosAccount.trim().toLowerCase() === corosAccount.trim().toLowerCase()
                    ? '留空自动使用已存密码，改密则填新密码'
                    : '请输入您的 COROS 密码'
                "
                placeholder-class="placeholder-style"
                v-model="inputCorosPassword"
              />

              <button class="large-primary-btn coros-primary-btn" :loading="bindingCoros" @click="handleBindCoros">
                {{
                  corosConnected && corosHasSavedPassword && !inputCorosPassword.trim() && inputCorosAccount.trim().toLowerCase() === corosAccount.trim().toLowerCase()
                    ? "📱 发送短信验证码（免输密码）"
                    : "连接高驰"
                }}
              </button>
            </view>
          </view>

          <!-- ── 苹果 / 华为 / 颂拓 统一免密导入 TAB ── -->
          <view v-else class="watch-guide-pane">
            <view class="watch-guide-card apple-guide-card">
              <text class="watch-guide-title">⌚ 苹果 / 华为 / 颂拓 · 导入方式</text>
              <view class="watch-step-list">
                <text class="watch-step-item">📸 截图：「苹果健康 → 步行+跑步距离 → 所有已记录的数据」列表，或各运动 App 跑步详情图</text>
                <text class="watch-step-item">📂 轨迹：从运动 App 导出 FIT/GPX/TCX 文件到微信后导入</text>
              </view>
            </view>

            <button
              class="large-primary-btn apple-primary-btn"
              style="margin-bottom: 16rpx;"
              :loading="!!importingScreenshotBrand"
              @click="handleImportWatchScreenshot(activeHealthWatchBrand, true)"
            >
              📸 选运动截图导入
            </button>

            <button
              class="modal-outline-btn apple-modal-outline"
              style="margin-bottom: 16rpx;"
              :loading="!!importingTrackBrand"
              @click="handleImportWatchTrack(activeHealthWatchBrand, true)"
            >
              📂 导入 FIT/GPX/TCX
            </button>

            <button
              class="modal-outline-btn apple-modal-outline"
              :loading="bindingHealthWatch"
              @click="handleBindHealthWatch(activeHealthWatchBrand)"
            >
              {{ (appleWatchConnected || huaweiConnected || suuntoConnected) ? '✓ 已激活（刷新）' : '⌚ 标记已连接' }}
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── Join Club Modal ── -->
    <view v-if="showJoinModal" class="modal-mask" @click="showJoinModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">加入跑团</text>
          <view class="close-hit" @click="showJoinModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="modal-body">
          <text class="field-label">跑团专属邀请码</text>
          <input
            class="large-input center-input"
            type="text"
            maxlength="12"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="请输入跑团邀请码"
            placeholder-class="placeholder-style"
            v-model="inviteCodeInput"
          />
          <button class="large-primary-btn" :loading="joiningClub" @click="handleJoinClub">
            立即加入
          </button>
        </view>
      </view>
    </view>


    <!-- ── Edit Profile Modal (修改个人资料与身体参数) ── -->
    <view v-if="showEditProfileModal" class="modal-mask" @click="showEditProfileModal = false" @touchmove.stop.prevent>
      <view class="modal-content edit-profile-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title">编辑资料</text>
          <view class="close-hit" @click="showEditProfileModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <scroll-view scroll-y class="modal-body modal-scroll" style="max-height: 72vh;">
          <!-- 1. 头像选择与上传 -->
          <view class="avatar-edit-box">
            <image
              class="avatar-preview-lg"
              :src="editAvatarUrl || profile?.avatar_url || user?.avatar_url || defaultAvatar"
              mode="aspectFill"
            />
            <view class="avatar-actions-row">
              <button
                class="avatar-sub-btn wx-pick"
                open-type="chooseAvatar"
                @chooseavatar="onEditChooseAvatar"
              >
                🟢 选微信头像
              </button>
              <button
                class="avatar-sub-btn album-pick"
                @click="chooseFromAlbum"
              >
                🖼️ 相册 / 拍照
              </button>
            </view>
          </view>

          <!-- 2. 昵称编辑 -->
          <view class="edit-field-wrap">
            <text class="field-label">跑者昵称 *</text>
            <input
              type="nickname"
              class="large-input edit-name-input"
              :value="editDisplayName"
              placeholder="请输入您的跑者昵称"
              placeholder-class="placeholder-style"
              @blur="onEditNameBlur"
              @input="onEditNameInput"
            />
          </view>

          <!-- 3. 生理性别 -->
          <view class="edit-field-wrap">
            <text class="field-label">生理性别 *</text>
            <view class="modal-gender-row">
              <view
                class="gender-pill"
                :class="{ active: editGender === 'male' }"
                @click="editGender = 'male'"
              >
                <text class="gender-pill-txt">🚹 男跑者</text>
              </view>
              <view
                class="gender-pill"
                :class="{ active: editGender === 'female' }"
                @click="editGender = 'female'"
              >
                <text class="gender-pill-txt">🚺 女跑者</text>
              </view>
            </view>
          </view>

          <!-- 4. 出生日期 -->
          <view class="edit-field-wrap">
            <text class="field-label">出生日期 *</text>
            <picker mode="date" :value="editDob || '1990-01-01'" start="1940-01-01" :end="todayDateStr" @change="onEditDobChange">
              <view class="modal-picker-box">
                <text class="modal-picker-val">{{ editDob || "请选择出生日期" }}</text>
                <text class="modal-picker-arrow">📅 ›</text>
              </view>
            </picker>
          </view>

          <!-- 5. 身高与体重 -->
          <view class="modal-row-2">
            <view class="modal-col-half">
              <text class="field-label">身高 (cm)</text>
              <input
                class="large-input"
                type="digit"
                placeholder="175"
                placeholder-class="placeholder-style"
                v-model="editHeight"
              />
            </view>
            <view class="modal-col-half">
              <text class="field-label">体重 (kg)</text>
              <input
                class="large-input"
                type="digit"
                placeholder="65"
                placeholder-class="placeholder-style"
                v-model="editWeight"
              />
            </view>
          </view>

          <!-- 6. 跑龄 -->
          <view class="edit-field-wrap" style="margin-top: 14rpx;">
            <text class="field-label">跑步年限 (年)</text>
            <input
              class="large-input"
              type="number"
              placeholder="2"
              placeholder-class="placeholder-style"
              v-model="editYearsRunning"
            />
          </view>

          <!-- 7. 快捷导航直达 -->
          <view class="modal-direct-links">
            <view class="direct-link-card" @click="jumpToFullProfileFromModal">
              <text class="dlc-icon">📜</text>
              <view class="dlc-texts">
                <text class="dlc-title">实名认证、手表绑定与目标</text>
              </view>
              <text class="dlc-arrow">›</text>
            </view>
            <view class="direct-link-card secondary" @click="jumpToOnboardingFromModal">
              <text class="dlc-icon">🚀</text>
              <view class="dlc-texts">
                <text class="dlc-title">跑者设定向导</text>
              </view>
              <text class="dlc-arrow">›</text>
            </view>
          </view>

          <!-- 8. 保存按钮 -->
          <button
            class="large-primary-btn save-profile-btn"
            :loading="savingProfile"
            @click="handleSaveProfile"
          >
            保存
          </button>
          <view style="height: 20rpx;"></view>
        </scroll-view>
      </view>
    </view>

    <!-- ── Add / Edit Race Modal (添加与编辑比赛) ── -->
    <view v-if="showRaceModal" class="modal-mask" @click="showRaceModal = false" @touchmove.stop.prevent>
      <view class="modal-content race-modal-card" @click.stop>
        <view class="modal-header">
          <text class="modal-title">{{ raceModalMode === 'add' ? '🏁 添加比赛计划' : '✏️ 编辑比赛计划' }}</text>
          <view class="close-hit" @click="showRaceModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <scroll-view scroll-y class="race-modal-scroll">
          <!-- 1. 比赛名称 & 自动快速填充 -->
          <view class="m-field-wrap">
            <text class="m-field-lbl">比赛名称</text>
            <view class="m-input-ai-row">
              <input
                class="m-input-txt flex-1"
                type="text"
                v-model="raceForm.name"
                placeholder="如: 无锡马拉松 / 崇礼168"
                placeholder-class="placeholder-style"
              />
              <button
                class="m-ai-fill-btn"
                :loading="modalSearchingRaceInfo"
                :disabled="modalSearchingRaceInfo"
                @click="handleModalAutoFetchRaceInfo"
              >⚡ 自动填情报</button>
            </view>
          </view>

          <!-- 2. 比赛类型 -->
          <view class="m-field-wrap">
            <text class="m-field-lbl">比赛类型</text>
            <picker
              mode="selector"
              :range="raceTypeOptions"
              :value="raceTypeOptions.indexOf(raceForm.race_type) >= 0 ? raceTypeOptions.indexOf(raceForm.race_type) : 0"
              @change="(e: any) => raceForm.race_type = raceTypeOptions[e.detail.value]"
            >
              <view class="m-picker-box">
                <text class="m-picker-txt">{{ raceForm.race_type || '请选择比赛类型' }}</text>
                <text class="m-picker-arrow">▼</text>
              </view>
            </picker>
          </view>

          <!-- 3. 比赛日期 & 目标成绩 -->
          <view class="m-row-2">
            <view class="m-field-wrap flex-1">
              <text class="m-field-lbl">比赛日期</text>
              <picker
                mode="date"
                :value="raceForm.race_date"
                @change="(e: any) => raceForm.race_date = e.detail.value"
              >
                <view class="m-picker-box">
                  <text class="m-picker-txt">{{ raceForm.race_date || '选择日期' }}</text>
                  <text class="m-picker-arrow">📅</text>
                </view>
              </picker>
            </view>

            <view class="m-field-wrap flex-1">
              <text class="m-field-lbl">目标成绩 (HH:MM:SS)</text>
              <input
                class="m-input-txt"
                type="text"
                v-model="raceForm.target_time"
                placeholder="如: 3:30:00"
                placeholder-class="placeholder-style"
              />
            </view>
          </view>

          <!-- 4. 赛事定位分级 -->
          <view class="m-field-wrap">
            <text class="m-field-lbl">赛事分级</text>
            <view class="priority-segmented">
              <view
                class="seg-item"
                :class="{ active: raceForm.priority == 1 || raceForm.priority === 'A' }"
                @click="raceForm.priority = 1"
              >A 标 (核心)</view>
              <view
                class="seg-item"
                :class="{ active: raceForm.priority == 2 || raceForm.priority === 'B' }"
                @click="raceForm.priority = 2"
              >B 标 (代练)</view>
              <view
                class="seg-item"
                :class="{ active: raceForm.priority == 3 || raceForm.priority === 'C' }"
                @click="raceForm.priority = 3"
              >C 标 (拉练)</view>
            </view>
          </view>

          <!-- 5. 完赛状态与成绩回填 -->
          <view class="m-field-wrap">
            <text class="m-field-lbl">赛事状态</text>
            <view class="status-segmented">
              <view
                class="status-seg-item"
                :class="{ active: raceForm.status !== 'completed' }"
                @click="raceForm.status = 'upcoming'"
              >🟢 备战中</view>
              <view
                class="status-seg-item completed-item"
                :class="{ active: raceForm.status === 'completed' }"
                @click="raceForm.status = 'completed'"
              >🏅 已完赛</view>
            </view>
          </view>

          <!-- 完赛详情面板（当选择已完赛时展开） -->
          <view v-if="raceForm.status === 'completed'" class="m-completion-section">
            <view class="m-completion-header">
              <text class="comp-sec-title">🏅 完赛记录</text>
              <view style="display:flex; gap:12rpx;">
                <button
                  v-if="raceForm.id"
                  class="m-auto-match-btn"
                  style="background:var(--rgm-brand-tint, rgba(251,191,36,0.18)); border-color:var(--rgm-brand-line, #fbbf24); color:var(--rgm-brand-text, #fbbf24);"
                  @click="openCompletedRaceShareCard(raceForm)"
                >📸 完赛分享卡</button>
                <button
                  class="m-auto-match-btn"
                  :loading="matchingWatchActivity"
                  :disabled="matchingWatchActivity"
                  @click="handleModalMatchActivity"
                >⚡ 从手表提取</button>
              </view>
            </view>

            <view class="m-field-wrap">
              <view class="finish-time-lbl-row">
                <text class="m-field-lbl">实际完成时间 (HH:MM:SS)</text>
                <text v-if="calcModalDiff" class="finish-time-diff-badge" :class="calcModalDiff.isFaster ? 'faster' : 'slower'">
                  {{ calcModalDiff.badge }} {{ calcModalDiff.str }}
                </text>
              </view>
              <input
                class="m-input-txt font-mono"
                type="text"
                v-model="raceForm.finish_time"
                placeholder="如: 3:24:15 或 08:12:00"
                placeholder-class="placeholder-style"
              />
            </view>

            <view class="m-field-wrap">
              <text class="m-field-lbl">完赛心得 / 感言</text>
              <input
                class="m-input-txt"
                type="text"
                v-model="raceForm.finish_notes"
                placeholder="如: 补给充分，下坡控速理想，超额达成目标！"
                placeholder-class="placeholder-style"
              />
            </view>

            <!-- 担任官方配速员（官兔）履历标记 -->
            <view class="m-field-wrap" style="padding: 16rpx 20rpx; border-radius: 18rpx; background: rgba(252, 76, 2, 0.08); border: 1rpx solid rgba(252, 76, 2, 0.25);">
              <view style="display: flex; align-items: center; justify-content: space-between;">
                <text style="font-size: 24rpx; font-weight: 700; color: #fc4c02;">🐰 本场担任官方配速员（官兔）</text>
                <switch
                  :checked="Boolean(raceForm.was_official_pacer)"
                  color="#FC4C02"
                  style="transform: scale(0.8);"
                  @change="onToggleRaceOfficialPacer"
                />
              </view>
              <view v-if="raceForm.was_official_pacer" style="margin-top: 12rpx;">
                <text class="m-field-lbl">官兔领跑组别目标时间 (HH:MM:SS)</text>
                <input
                  class="m-input-txt font-mono"
                  type="text"
                  v-model="raceForm.pacer_target_time"
                  placeholder="如: 03:30:00"
                  placeholder-class="placeholder-style"
                />
              </view>
            </view>

            <view class="m-field-wrap">
              <view class="m-photo-lbl-row">
                <text class="m-field-lbl">完赛照片 / 证书 / 奖牌</text>
                <button
                  class="m-upload-photo-btn"
                  :loading="uploadingModalPhoto"
                  :disabled="uploadingModalPhoto"
                  @click="handleChooseRacePhoto"
                >📷 上传照片</button>
              </view>
              <view v-if="raceForm.photos && raceForm.photos.length" class="modal-photo-grid">
                <view v-for="(pUrl, pIdx) in raceForm.photos" :key="pIdx" class="modal-photo-thumb-wrap">
                  <image
                    class="modal-photo-img"
                    :src="pUrl"
                    mode="aspectFill"
                    @click="handlePreviewImage(pUrl, raceForm.photos)"
                  />
                  <view class="modal-photo-del" @click.stop="handleDeleteModalPhoto(pUrl)">✕</view>
                </view>
              </view>
              <view v-else class="modal-photo-empty" @click="handleChooseRacePhoto">
                <text class="empty-photo-text">点击上传证书、奖牌或冲线照 📸</text>
              </view>
            </view>
          </view>

          <!-- 6. 赛事情报客观数据（可折叠查看/编辑） -->
          <view class="m-race-info-block">
            <view class="m-race-info-header" @click="modalExpandRaceInfo = !modalExpandRaceInfo">
              <text class="m-info-title">
                📋 {{ isTrail(raceForm.race_type) ? '越野赛客观情报' : '公路赛客观情报' }}
                {{ Object.values(raceForm.race_info || {}).some(v => v !== null && v !== undefined && v !== '') ? '(已填录)' : '(点击填写)' }}
              </text>
              <text class="m-info-arrow">{{ modalExpandRaceInfo ? '▲' : '▼' }}</text>
            </view>

            <view v-if="modalExpandRaceInfo" class="m-race-info-fields">
              <!-- 越野赛专属字段 -->
              <template v-if="isTrail(raceForm.race_type)">
                <view class="m-row-2">
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">报名赛程 (km)</text>
                    <input
                      class="m-subinput"
                      type="digit"
                      placeholder="如 50"
                      :value="raceForm.race_info?.race_distance_km ?? ''"
                      @input="(e: any) => raceForm.race_info.race_distance_km = parseFloat(e.detail.value) || null"
                    />
                  </view>
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">累计爬升 D+ (m)</text>
                    <input
                      class="m-subinput"
                      type="digit"
                      placeholder="如 2800"
                      :value="raceForm.race_info?.elevation_gain_m ?? ''"
                      @input="(e: any) => raceForm.race_info.elevation_gain_m = parseFloat(e.detail.value) || null"
                    />
                  </view>
                </view>

                <view class="m-row-2">
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">累计下降 D- (m)</text>
                    <input
                      class="m-subinput"
                      type="digit"
                      placeholder="如 2800"
                      :value="raceForm.race_info?.elevation_loss_m ?? ''"
                      @input="(e: any) => raceForm.race_info.elevation_loss_m = parseFloat(e.detail.value) || null"
                    />
                  </view>
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">最高海拔 (m)</text>
                    <input
                      class="m-subinput"
                      type="digit"
                      placeholder="如 2100"
                      :value="raceForm.race_info?.max_altitude_m ?? ''"
                      @input="(e: any) => raceForm.race_info.max_altitude_m = parseFloat(e.detail.value) || null"
                    />
                  </view>
                </view>

                <view class="m-row-2">
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">难度等级</text>
                    <picker
                      mode="selector"
                      :range="difficultyOptions"
                      :value="difficultyOptions.indexOf(raceForm.race_info?.difficulty_level) >= 0 ? difficultyOptions.indexOf(raceForm.race_info?.difficulty_level) : 0"
                      @change="(e: any) => raceForm.race_info.difficulty_level = difficultyOptions[e.detail.value]"
                    >
                      <view class="m-subpicker">
                        <text>{{ raceForm.race_info?.difficulty_level || '选择难度' }}</text>
                      </view>
                    </picker>
                  </view>
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">地形类型</text>
                    <picker
                      mode="selector"
                      :range="trailTerrainOptions"
                      :value="trailTerrainOptions.indexOf(raceForm.race_info?.terrain_type) >= 0 ? trailTerrainOptions.indexOf(raceForm.race_info?.terrain_type) : 0"
                      @change="(e: any) => raceForm.race_info.terrain_type = trailTerrainOptions[e.detail.value]"
                    >
                      <view class="m-subpicker">
                        <text>{{ raceForm.race_info?.terrain_type || '选择地形' }}</text>
                      </view>
                    </picker>
                  </view>
                </view>

                <view class="m-field-wrap">
                  <text class="m-sublbl">强制装备要求</text>
                  <input
                    class="m-subinput"
                    placeholder="如: 双头灯、急救毯、1.5L水、保暖防风衣"
                    :value="raceForm.race_info?.mandatory_gear ?? ''"
                    @input="(e: any) => raceForm.race_info.mandatory_gear = e.detail.value"
                  />
                </view>
              </template>

              <!-- 公路赛专属字段 -->
              <template v-else>
                <view class="m-row-2">
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">赛事等级</text>
                    <picker
                      mode="selector"
                      :range="raceLevelOptions"
                      :value="raceLevelOptions.indexOf(raceForm.race_info?.race_level) >= 0 ? raceLevelOptions.indexOf(raceForm.race_info?.race_level) : 0"
                      @change="(e: any) => raceForm.race_info.race_level = raceLevelOptions[e.detail.value]"
                    >
                      <view class="m-subpicker">
                        <text>{{ raceForm.race_info?.race_level || '选择等级' }}</text>
                      </view>
                    </picker>
                  </view>
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">赛道特点</text>
                    <picker
                      mode="selector"
                      :range="courseProfileOptions"
                      :value="courseProfileOptions.indexOf(raceForm.race_info?.course_profile) >= 0 ? courseProfileOptions.indexOf(raceForm.race_info?.course_profile) : 0"
                      @change="(e: any) => raceForm.race_info.course_profile = courseProfileOptions[e.detail.value]"
                    >
                      <view class="m-subpicker">
                        <text>{{ raceForm.race_info?.course_profile || '选择特点' }}</text>
                      </view>
                    </picker>
                  </view>
                </view>

                <view class="m-row-2">
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">路面材质</text>
                    <picker
                      mode="selector"
                      :range="courseSurfaceOptions"
                      :value="courseSurfaceOptions.indexOf(raceForm.race_info?.course_surface) >= 0 ? courseSurfaceOptions.indexOf(raceForm.race_info?.course_surface) : 0"
                      @change="(e: any) => raceForm.race_info.course_surface = courseSurfaceOptions[e.detail.value]"
                    >
                      <view class="m-subpicker">
                        <text>{{ raceForm.race_info?.course_surface || '选择材质' }}</text>
                      </view>
                    </picker>
                  </view>
                  <view class="m-field-wrap flex-1">
                    <text class="m-sublbl">累计净爬升 (m)</text>
                    <input
                      class="m-subinput"
                      type="digit"
                      placeholder="如 45"
                      :value="raceForm.race_info?.net_elevation_gain_m ?? ''"
                      @input="(e: any) => raceForm.race_info.net_elevation_gain_m = parseFloat(e.detail.value) || null"
                    />
                  </view>
                </view>
              </template>

              <!-- 通用天气与参赛规模 -->
              <view class="m-row-2">
                <view class="m-field-wrap flex-1">
                  <text class="m-sublbl">历史平均气温 (℃)</text>
                  <input
                    class="m-subinput"
                    type="digit"
                    placeholder="如 14"
                    :value="raceForm.race_info?.avg_temp_c ?? ''"
                    @input="(e: any) => raceForm.race_info.avg_temp_c = parseFloat(e.detail.value) || null"
                  />
                </view>
                <view class="m-field-wrap flex-1">
                  <text class="m-sublbl">大致参赛规模 (人)</text>
                  <input
                    class="m-subinput"
                    type="digit"
                    placeholder="如 30000"
                    :value="raceForm.race_info?.typical_participants ?? ''"
                    @input="(e: any) => raceForm.race_info.typical_participants = parseInt(e.detail.value) || null"
                  />
                </view>
              </view>
            </view>
          </view>

          <!-- 操作按钮栏 -->
          <view class="m-actions-row">
            <button class="m-cancel-btn" @click="showRaceModal = false">取消</button>
            <button
              class="m-save-btn"
              :loading="savingRace"
              :disabled="savingRace"
              @click="handleSaveRaceModal"
            >
              {{ raceModalMode === 'add' ? '确认添加比赛' : '保存修改' }}
            </button>
          </view>

          <view v-if="raceModalMode === 'edit'" class="m-del-row" @click="handleDeleteRace(raceForm)">
            <text class="m-del-txt">🗑️ 删除此比赛计划</text>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── Privacy Purge Confirmation Modal (一键彻底清除隐私数据防误删弹窗) ── -->
    <view v-if="showPurgeConfirmModal" class="modal-mask purge-modal-mask" @click="showPurgeConfirmModal = false" @touchmove.stop.prevent>
      <view class="modal-content purge-modal-content" @click.stop>
        <view class="modal-header purge-modal-header">
          <view class="title-with-pill">
            <text class="modal-title text-red">⚠️ 彻底清除个人隐私数据？</text>
          </view>
          <text class="close-btn" @click="showPurgeConfirmModal = false">✕</text>
        </view>

        <view class="modal-body purge-modal-body">
          <view class="purge-warning-banner">
            <text class="purge-warn-icon">🚨</text>
            <view class="purge-warn-text-wrap">
              <text class="purge-warn-title">请谨慎确认，清除后不可撤销！</text>
              <text class="purge-warn-desc">
                为防止误删，请仔细阅读以下清除与保留规则：
              </text>
            </view>
          </view>

          <view class="purge-details-box">
            <text class="purge-detail-header red-header">将被彻底物理抹除的隐私（不可恢复）：</text>
            <view class="purge-detail-item red-item">
              <text class="purge-dot red-dot">✕</text>
              <text class="purge-item-text">真实姓名、身份证号码、出生年月日</text>
            </view>
            <view class="purge-detail-item red-item">
              <text class="purge-dot red-dot">✕</text>
              <text class="purge-item-text">紧急联系手机号、个人邮箱、简介与头像</text>
            </view>
            <view class="purge-detail-item red-item">
              <text class="purge-dot red-dot">✕</text>
              <text class="purge-item-text">已绑定的 Garmin / 高驰手表授权密码与令牌</text>
            </view>
            <view class="purge-detail-item red-item">
              <text class="purge-dot red-dot">✕</text>
              <text class="purge-item-text">各大跑团/大群花名册中的实名认证登记</text>
            </view>

            <view class="purge-divider"></view>

            <text class="purge-detail-header green-header">将被安全保留的信息（匿名化）：</text>
            <view class="purge-detail-item green-item">
              <text class="purge-dot green-dot">✓</text>
              <text class="purge-item-text">历史跑步里程、活动与打卡记录（显示为匿名跑者）</text>
            </view>
            <view class="purge-detail-item green-item">
              <text class="purge-dot green-dot">✓</text>
              <text class="purge-item-text">所在跑团队伍历史总里程与数据统计不受影响</text>
            </view>
          </view>

          <view class="purge-modal-actions">
            <button class="purge-cancel-btn" @click="showPurgeConfirmModal = false">
              取消返回
            </button>
            <button class="purge-execute-btn" :loading="purgingPrivacy" @click="executePurgePrivacy">
              确认彻底清除
            </button>
          </view>
        </view>
      </view>
    </view>
    <!-- 个人打卡 & 已完赛赛事分享朋友圈卡片弹窗 -->
    <PersonalShareCardModal
      :visible="showRaceShareCard"
      :race-id="activeShareRaceId"
      @close="showRaceShareCard = false"
    />

    <!-- 微信隐私保护指引授权弹窗 -->
    <PrivacyPopup />
  </view>
</template>

<script setup lang="ts">
import {
  currentTheme,
  themeClass,
  setTheme,
  applySystemTheme,
  currentFontScale,
  setFontScale,
  FONT_SCALE_OPTIONS,
  type ThemeMode,
} from "../../utils/theme";
import { explainTerm } from "../../utils/glossary";
import { trackClick, trackModal, trackFunnelStep } from "../../utils/telemetry";
import PrivacyPopup from "../../components/PrivacyPopup.vue";
import PersonalShareCardModal from "../../components/PersonalShareCardModal.vue";
import { ref, computed, watch } from "vue";
import { onShow, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";

import {
  request,
  getStoredUser,
  clearSession,
  authenticateWechatUser,
  authenticateAppleUser,
  deviceLogin,
  uploadAvatarFile,
  uploadRacePhoto,
  deleteRacePhoto,
  API_BASE_URL,
  UserProfile,
  bindCoros,
  unbindCoros,
  bindHealthWatch,
  unbindHealthWatch,
  chooseAndImportTrackFile,
  chooseAndImportScreenshot,
  resolveActiveClub,
  setActiveClubId,
  syncTabBarIndex,
  submitSupportTicket,
  fetchMySupportTickets,
  formatBeijingTime,
  type SupportTicket,
} from "../../utils/api";

const defaultProfile = {
  marathon_pb: 0,
  half_pb: 0,
  ten_k_pb: 0,
  five_k_pb: 0,
  garmin_connected: false,
  garmin_email: "",
  garmin_domain: "garmin.cn",
  coros_connected: false,
  coros_account: "",
  coros_domain: "teamcnapi.coros.com",
  apple_watch_connected: false,
  huawei_connected: false,
  huawei_account: "",
  suunto_connected: false,
  suunto_account: "",
  gender: "male",
  date_of_birth: "",
  real_name: "",
  phone: "",
  id_card: "",
  program: "",
  class_detail: "",
  class_name: "",
  gobi_experience: "新戈",
  emergency_contact: "",
  clothing_size: "",
  shoe_size: "",
  first_aid_cert_type: "",
  health_declaration: true,
  vo2max: null,
  years_running: 3,
  height: 175,
  weight: 65,
  max_heart_rate: 190,
  resting_heart_rate: 56,
  hide_gps_route: false,
  hide_biometrics: false,
};

const ORG_PROGRAM_OPTIONS = ["中文EMBA", "台大班", "复旦-BI（挪威）", "奥林班", "港大班"];
const GOBI_EDITIONS = Array.from({ length: 21 }, (_, i) => `戈${21 - i}`);
const GOBI_GROUPS = ["A组", "B组", "C组"];
const CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"];
const FIRST_AID_CERT_CODES = ["", "red_cross", "aha", "medical_pro"];
const FIRST_AID_CERT_LABELS = [
  "暂未持有急救证书",
  "红十字会救护员证 (CPR/AED)",
  "AHA HeartSaver 急救证",
  "执业医师 / 护士医护资质",
];
const firstAidPickerIndex = computed(() => {
  const code = String(profile.value?.first_aid_cert_type || "");
  const idx = FIRST_AID_CERT_CODES.indexOf(code);
  return idx >= 0 ? idx : 0;
});

const user = ref<UserProfile | null>(null);
const profile = ref<any>(defaultProfile);
const races = ref<any[]>([]);
const userClub = ref<any>(null);
const userOrgs = ref<any[]>([]);
// 渐进式资料：已加入大群才默认展开商学院 / 赛事装备资料
const hasOrgs = computed(() => (userOrgs.value?.length || 0) > 0);
const showOrgExtraFields = ref(false);
const purgingPrivacy = ref(false);
const showDob = ref(false);
const showRealName = ref(false);
const showPhone = ref(false);
const showIdCard = ref(false);
const showPurgeConfirmModal = ref(false);

// 「我的」页拆分为首页 + 子页面（页内切换，共用同一份状态与保存逻辑，弹窗不受影响）
type ProfileSection = "" | "device" | "personal" | "training" | "privacy" | "support";
const activeSection = ref<ProfileSection>("");
const SECTION_TITLES: Record<string, string> = {
  device: "手表连接与同步",
  personal: "个人资料与实名信息",
  training: "训练档案与赛事",
  privacy: "通知与隐私",
  support: "帮助与技术支持",
};
const activeSectionTitle = computed(() => SECTION_TITLES[activeSection.value] || "");
const activeHealthWatchBrand = computed<"apple_watch" | "huawei" | "suunto">(() => {
  if (suuntoConnected.value) return "suunto";
  if (huaweiConnected.value) return "huawei";
  return "apple_watch";
});
const deviceStatusText = computed(() => {
  const names: string[] = [];
  if (garminConnected.value) names.push("佳明");
  if (corosConnected.value) names.push("高驰");
  if (appleWatchConnected.value || huaweiConnected.value || suuntoConnected.value) {
    names.push("苹果/华为/颂拓");
  }
  return names.length ? `${names.join("、")}已连接` : "未连接";
});
// 有大群且未提交/已过期时，在菜单上提示补齐资料
const personalNeedsAttention = computed(() =>
  (userOrgs.value || []).some((o: any) => o.status !== "confirmed" && o.status !== "pending")
);

// ── 帮助与技术支持 (Support & Feedback) 状态 ──
const SUPPORT_CATEGORIES = [
  { value: "device_sync", label: "⌚ 手表绑定/同步" },
  { value: "club_org", label: "🏕️ 跑团/大群认证" },
  { value: "training_data", label: "📊 训练数据/配速" },
  { value: "other", label: "💡 其他问题建议" },
];
const supportCategory = ref("device_sync");
const supportContent = ref("");
const supportContact = ref("");
const submittingTicket = ref(false);
const mySupportTickets = ref<SupportTicket[]>([]);

const hasSupportReply = computed(() =>
  mySupportTickets.value.some((t) => !!t.admin_reply)
);

const supportSessionFrom = computed(() => {
  const uid = user.value?.id || "guest";
  const name = profile.value?.display_name || user.value?.display_name || "跑者";
  return `uid=${uid}|name=${name}|watch=${deviceStatusText.value}`;
});

function getSupportCatLabel(catVal: string): string {
  const found = SUPPORT_CATEGORIES.find((c) => c.value === catVal);
  return found ? found.label : "💬 问题反馈";
}

function formatSupportTime(iso?: string): string {
  return formatBeijingTime(iso, true);
}

async function loadMySupportTickets() {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) return;
  try {
    const list = await fetchMySupportTickets(uid);
    mySupportTickets.value = list;
  } catch (e) {
    // ignore background fetch error
  }
}

function handleCopyDiagnosticInfo() {
  const uid = user.value?.id || "未登录";
  const name = profile.value?.display_name || user.value?.display_name || "微信跑者";
  const clubNames = (userClubs.value || []).map((c: any) => c.name).join("、") || "暂未加入";
  let sysStr = "";
  try {
    const sys = uni.getSystemInfoSync();
    sysStr = `${sys.brand || ""} ${sys.model || ""} (${sys.system || ""})`.trim();
  } catch (e) {}
  const text = `【万跑跑团助手 · 诊断信息】\n跑者昵称：${name}\n跑者ID：${uid}\n绑定手表：${deviceStatusText.value}\n所属跑团：${clubNames}${sysStr ? `\n手机型号：${sysStr}` : ""}`;
  uni.setClipboardData({
    data: text,
    success: () => {
      uni.showToast({
        title: "诊断信息已复制，可直接粘贴给客服",
        icon: "none",
        duration: 2500,
      });
    },
  });
}

async function handleSubmitSupportTicket() {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) {
    openAuthModal();
    return;
  }
  const content = supportContent.value.trim();
  if (content.length < 2) {
    uni.showToast({ title: "请填写您遇到的具体问题", icon: "none" });
    return;
  }
  submittingTicket.value = true;
  try {
    let sysInfo: Record<string, any> = {};
    try {
      const sys = uni.getSystemInfoSync();
      sysInfo = {
        brand: sys.brand,
        model: sys.model,
        system: sys.system,
        platform: sys.platform,
        SDKVersion: (sys as any).SDKVersion,
      };
    } catch (e) {}
    sysInfo.watch_status = deviceStatusText.value;
    sysInfo.clubs = (userClubs.value || []).map((c: any) => c.name);

    const res = await submitSupportTicket({
      user_id: uid,
      category: supportCategory.value,
      content,
      contact_info: supportContact.value.trim(),
      device_info: sysInfo,
    });
    supportContent.value = "";
    await loadMySupportTickets();
    uni.showModal({
      title: "✅ 留言已提交",
      content: res?.message || "我们已收到您的问题反馈（已自动附带跑者 ID 与手表状态），技术支持核查后将在此页面回复您。如需发送截图，也可点击上方「微信一对一在线客服」。",
      showCancel: false,
      confirmText: "好的",
    });
  } catch (err: any) {
    uni.showToast({ title: err?.message || "提交失败，请稍后重试", icon: "none" });
  } finally {
    submittingTicket.value = false;
  }
}

function openSection(key: ProfileSection) {
  if (!user.value && key !== "support") {
    openAuthModal();
    return;
  }
  activeSection.value = key;
  if (key === "support") {
    loadMySupportTickets();
  }
  uni.pageScrollTo({ scrollTop: 0, duration: 0 });
}
function closeSection() {
  activeSection.value = "";
  uni.pageScrollTo({ scrollTop: 0, duration: 0 });
}
// 退出登录后回到「我的」首页
watch(user, (u) => {
  if (!u) activeSection.value = "";
});
const isFieldHighlighted = ref(false);

function scrollToRequiredFields(options?: { message?: string }) {
  activeSection.value = "personal";
  setTimeout(() => {
    try {
      uni.createSelectorQuery()
        .selectViewport().scrollOffset()
        .select("#required-personal-fields").boundingClientRect()
        .exec((res: any) => {
          const scrollInfo = res?.[0];
          const rect = res?.[1];
          if (rect && scrollInfo) {
            const targetTop = Math.max(0, scrollInfo.scrollTop + rect.top - 20);
            uni.pageScrollTo({ scrollTop: targetTop, duration: 400 });
          } else {
            uni.pageScrollTo({ selector: "#required-personal-fields", duration: 400 });
          }
        });
    } catch (e) {
      uni.pageScrollTo({ selector: "#required-personal-fields", duration: 400 });
    }
    isFieldHighlighted.value = true;
    uni.showToast({
      title: options?.message || "已定位至个人资料编辑区，可直接修改",
      icon: "none",
      duration: 2200
    });
    setTimeout(() => {
      isFieldHighlighted.value = false;
    }, 3200);
  }, 220);
}

function goToManual() {
  uni.navigateTo({
    url: "/pages/manual/manual",
  });
}

const onboardingStatus = ref<any>(null);

function goToOnboarding(step: number = 1) {
  uni.navigateTo({
    url: `/pages/onboarding/onboarding?step=${step}`,
  });
}

function goToSharePage() {
  uni.navigateTo({
    url: "/pages/share/share",
  });
}

const gobiType = ref<"new" | "vet">("new");
const gobiEdition = ref("戈21");
const gobiGroup = ref("A组");

// ── WeChat Subscribe Message State & Handlers ──
const WECHAT_SUBSCRIBE_TEMPLATE_ID = "I8K67iHNWQB0on15Z01rxKinP18DAuIPgaz7LSXIqT0";
const wechatSubscribeEnabled = ref(uni.getStorageSync("rgm_wechat_subscribe_enabled") || false);
const testingPush = ref(false);

function getMiniappEnvState(): string {
  try {
    const accountInfo = (uni as any).getAccountInfoSync?.();
    const env = accountInfo?.miniProgram?.envVersion;
    if (env === "develop") return "developer";
    if (env === "trial") return "trial";
    return "formal";
  } catch (e) {
    return "formal";
  }
}

function handleRequestSubscribe(): Promise<boolean> {
  return new Promise((resolve) => {
    // #ifdef MP-WEIXIN
    if (typeof uni.requestSubscribeMessage === "function") {
      uni.requestSubscribeMessage({
        tmplIds: [WECHAT_SUBSCRIBE_TEMPLATE_ID],
        success: (res: any) => {
          const status = res[WECHAT_SUBSCRIBE_TEMPLATE_ID];
          if (status === "accept") {
            wechatSubscribeEnabled.value = true;
            uni.setStorageSync("rgm_wechat_subscribe_enabled", true);
            uni.showToast({ title: "已开启微信手机推送 🔔", icon: "success" });
            resolve(true);
          } else if (status === "reject") {
            uni.showToast({ title: "已取消授权，您仍可在端内查看点评", icon: "none" });
            resolve(false);
          } else {
            resolve(false);
          }
        },
        fail: (err: any) => {
          console.warn("[requestSubscribeMessage] fail:", err);
          if (err?.errCode === 20004) {
            uni.showModal({
              title: "订阅消息提醒",
              content: "微信服务通知已被系统关闭。如需在手机微信接收点评，请点击右上角【···】->【设置】->【通知管理】开启通知。",
              showCancel: false,
            });
          } else {
            uni.showToast({ title: "订阅授权暂未开启", icon: "none" });
          }
          resolve(false);
        }
      });
      return;
    }
    // #endif
    uni.showToast({ title: "当前环境不支持订阅消息", icon: "none" });
    resolve(false);
  });
}

async function handleTestWechatPush() {
  const u = user.value || getStoredUser();
  if (!u?.id) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }

  // In WeChat Mini Programs, each push requires at least 1 subscription authorization quota.
  // Prompting native requestSubscribeMessage here guarantees user has a valid quota for this test push!
  try {
    await new Promise((resolve) => {
      // #ifdef MP-WEIXIN
      if (typeof uni.requestSubscribeMessage === "function") {
        uni.requestSubscribeMessage({
          tmplIds: [WECHAT_SUBSCRIBE_TEMPLATE_ID],
          complete: () => resolve(true),
        });
        return;
      }
      // #endif
      resolve(true);
    });
  } catch (e) {}

  testingPush.value = true;
  uni.showLoading({ title: "正在发送微信推送..." });
  try {
    const envState = getMiniappEnvState();
    const res = await request("/api/notifications/test-push", "POST", {
      user_id: u.id,
      activity_name: "测试 12.5km 公路跑",
      distance_km: 12.5,
      critique: "【稳态专项有氧进阶】配速稳定心率理想，已同步生成超量恢复提示！",
      miniprogram_state: envState,
    });
    uni.hideLoading();
    if (res?.success) {
      if (res.wechat_sent === 1) {
        wechatSubscribeEnabled.value = true;
        uni.setStorageSync("rgm_wechat_subscribe_enabled", true);
        uni.showModal({
          title: "🎉 微信推送成功！",
          content: "Canova教练跑后点评已下发至您的手机微信！请前往微信聊天列表中的「服务通知」查看。",
          showCancel: false
        });
      } else {
        const detailMsg = res.wechat_errmsg || "微信下发受限，已保存在端内通知中心";
        uni.showModal({
          title: "推送已记录",
          content: `${detailMsg}。\n\n提示：若需在手机微信收到卡片，请点击左侧【开启微信手机消息提醒】并选择【允许】。`,
          showCancel: false
        });
      }
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: "推送测试触发完成", icon: "none" });
  } finally {
    testingPush.value = false;
  }
}

// ── Race Management & Intelligence State ──
const showRaceModal = ref(false);
const raceModalMode = ref<"add" | "edit">("add");
const savingRace = ref(false);
const modalSearchingRaceInfo = ref(false);
const modalExpandRaceInfo = ref(true);

const raceTypeOptions = [
  "全马 (42.195K)",
  "半马 (21.0975K)",
  "10公里",
  "5公里",
  "越野跑 50K",
  "越野跑 100K",
  "越野跑 100英里",
  "其他公路跑",
  "其他越野跑",
];

const raceForm = ref<{
  id: string;
  name: string;
  race_type: string;
  race_date: string;
  target_time: string;
  priority: number | string;
  status?: string;
  finish_time?: string;
  finish_notes?: string;
  photo_url?: string;
  photos?: string[];
  was_official_pacer?: boolean;
  pacer_target_time?: string;
  race_info: Record<string, any>;
}>({
  id: "",
  name: "",
  race_type: "全马 (42.195K)",
  race_date: "",
  target_time: "3:30:00",
  priority: 1,
  was_official_pacer: false,
  pacer_target_time: "",
  race_info: {},
});

const expandedRaceInfo = ref<Record<string, boolean>>({});
const savingRaceInfo = ref<Record<string, boolean>>({});
// Stores per-race draft edits before save: { [raceId]: { fieldKey: value } }
const raceInfoDrafts = ref<Record<string, Record<string, any>>>({});

// Picker options
const raceLevelOptions = [
  '世界白金标', '国际金标', 'IAAF 银标', 'IAAF 铜标', '国内 A 类认证', '普通大众认证', '品牌邀请赛'
];
const courseProfileOptions = [
  '极速平坦 (破 PB 首选)', '轻微起伏', '中等坡度', '丘陵赛道', '多爬升挑战赛道'
];
const courseSurfaceOptions = ['柏油路', '石板路', '混合路面（柏油+石板）', '碎石路'];
const difficultyOptions = ['入门级', '进阶级', '精英级', '极限级'];
const trailTerrainOptions = [
  '山地跑道', '高原草甸', '丛林密林', '岩石峭壁', '沙漠戈壁', '混合地形'
];
const climateZoneOptions = [
  '温带大陆性', '亚热带季风', '高寒高原', '热带季风', '温带海洋性'
];


const garminConnected = ref(false);
const garminEmail = ref("");
const garminDomain = ref("garmin.cn");

const corosConnected = ref(false);
const corosAccount = ref("");
const corosDomain = ref("teamcnapi.coros.com");
const corosNeedsReauth = ref(false);
const corosAuthError = ref("");
const corosHasSavedPassword = ref(false);

const appleWatchConnected = ref(false);
const huaweiConnected = ref(false);
const huaweiAccount = ref("");
const inputHuaweiAccount = ref("");
const suuntoConnected = ref(false);
const suuntoAccount = ref("");
const inputSuuntoAccount = ref("");
const bindingHealthWatch = ref(false);
const unbindingAppleWatch = ref(false);
const unbindingHuawei = ref(false);
const unbindingSuunto = ref(false);
const importingTrackBrand = ref<"" | "apple_watch" | "huawei" | "suunto">("");
const importingScreenshotBrand = ref<"" | "apple_watch" | "huawei" | "suunto">("");

const selectedBrand = ref<"garmin" | "coros" | "apple_watch" | "huawei" | "suunto">("garmin");
const inputCorosAccount = ref("");
const inputCorosPassword = ref("");
const inputCorosDomain = ref("teamcnapi.coros.com");
const bindingCoros = ref(false);
const unbindingCoros = ref(false);
const needsCoros2fa = ref(false);
const inputCoros2faCode = ref("");

const loggingIn = ref(false);

const showAuthModal = ref(false);
const authTab = ref<"wechat" | "device">("wechat");
const deviceBrand = ref<"garmin" | "coros">("garmin");
const deviceAccount = ref("");
const devicePassword = ref("");
const deviceDomain = ref("garmin.cn");
const deviceLoggingIn = ref(false);
const deviceNeedsMfa = ref(false);
const deviceMfaCode = ref("");
const deviceMfaHint = ref("");
const runnerNickName = ref("");
const runnerAvatar = ref("");
const recentAccounts = ref<any[]>([]);
const agreedTerms = ref(false);
const confirmingLogin = ref(false);
const defaultAvatar =
  "https://thirdwx.qlogo.cn/mmopen/vi_32/POgEwh4mIHO4nibH0KlMECNjjGxQUq24ZEaGT4poC6icRiccVGKSyXwibcPq4ozAawiaYbCQTvDVxp4UMxN5UulpDixA/132";

const showEditProfileModal = ref(false);
const editDisplayName = ref("");
const editAvatarUrl = ref("");
const editGender = ref("male");
const editDob = ref("");
const editHeight = ref<number | string>("");
const editWeight = ref<number | string>("");
const editYearsRunning = ref<number | string>("");
const savingProfile = ref(false);

function openEditProfileModal() {
  editDisplayName.value = profile.value?.display_name || user.value?.display_name || "";
  editAvatarUrl.value = profile.value?.avatar_url || user.value?.avatar_url || "";
  editGender.value = profile.value?.gender || "male";
  editDob.value = profile.value?.date_of_birth || "";
  editHeight.value = profile.value?.height_cm || profile.value?.height || "";
  editWeight.value = profile.value?.weight_kg || profile.value?.weight || "";
  editYearsRunning.value = profile.value?.years_running !== undefined && profile.value?.years_running !== null ? profile.value?.years_running : 2;
  showEditProfileModal.value = true;
}

function onEditDobChange(e: any) {
  editDob.value = e.detail?.value || "";
}

function jumpToFullProfileFromModal() {
  showEditProfileModal.value = false;
  setTimeout(() => {
    scrollToRequiredFields({ message: "已为您展开大群实名认证与个人档案区域" });
  }, 120);
}

function jumpToOnboardingFromModal() {
  showEditProfileModal.value = false;
  setTimeout(() => {
    goToOnboarding(1);
  }, 120);
}

function onEditNameBlur(e: any) {
  const val = e.detail?.value;
  if (val) editDisplayName.value = val;
}

function onEditNameInput(e: any) {
  editDisplayName.value = e.detail?.value || "";
}

async function uploadAvatarToServer(tempFilePath: string) {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  uni.showLoading({ title: "正在上传头像...", mask: true });
  try {
    const avatarUrl = await uploadAvatarFile(uid, tempFilePath);
    uni.hideLoading();
    editAvatarUrl.value = avatarUrl;
    if (profile.value) profile.value.avatar_url = avatarUrl;
    if (user.value) {
      user.value.avatar_url = avatarUrl;
      uni.setStorageSync("rgm_user", user.value);
      recordRecentUser(user.value);
    }
    uni.showToast({ title: "头像已上传 🎉", icon: "success" });
    return avatarUrl;
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: err?.message || "头像上传失败", icon: "none" });
    throw err;
  }
}

async function onEditChooseAvatar(e: any) {
  const avatarUrl = e.detail?.avatarUrl;
  if (avatarUrl) {
    await uploadAvatarToServer(avatarUrl);
  }
}

function chooseFromAlbum() {
  uni.chooseImage({
    count: 1,
    sizeType: ["compressed"],
    sourceType: ["album", "camera"],
    success: async (res) => {
      if (res.tempFilePaths && res.tempFilePaths[0]) {
        await uploadAvatarToServer(res.tempFilePaths[0]);
      }
    },
  });
}

async function handleSaveProfile() {
  const uid = user.value?.id;
  if (!uid) return;
  const name = editDisplayName.value.trim();
  if (!name) {
    uni.showToast({ title: "昵称不能为空", icon: "none" });
    return;
  }
  savingProfile.value = true;
  try {
    const payload: any = {
      display_name: name,
      gender: editGender.value,
      date_of_birth: editDob.value,
      height_cm: editHeight.value ? Number(editHeight.value) : undefined,
      weight_kg: editWeight.value ? Number(editWeight.value) : undefined,
      years_running: editYearsRunning.value !== "" && editYearsRunning.value !== null ? Number(editYearsRunning.value) : undefined,
    };
    if (editAvatarUrl.value) {
      payload.avatar_url = editAvatarUrl.value;
    }
    await request(`/api/profile/${encodeURIComponent(uid)}`, "PUT", payload);
    if (profile.value) {
      profile.value.display_name = name;
      if (editAvatarUrl.value) profile.value.avatar_url = editAvatarUrl.value;
      profile.value.gender = editGender.value;
      profile.value.date_of_birth = editDob.value;
      if (editHeight.value) {
        profile.value.height_cm = Number(editHeight.value);
        profile.value.height = Number(editHeight.value);
      }
      if (editWeight.value) {
        profile.value.weight_kg = Number(editWeight.value);
        profile.value.weight = Number(editWeight.value);
      }
      if (editYearsRunning.value !== "" && editYearsRunning.value !== null) {
        profile.value.years_running = Number(editYearsRunning.value);
      }
    }
    if (user.value) {
      user.value.display_name = name;
      if (editAvatarUrl.value) user.value.avatar_url = editAvatarUrl.value;
      uni.setStorageSync("rgm_user", user.value);
      recordRecentUser(user.value);
    }
    uni.showToast({ title: "资料与身体参数已更新 🎉", icon: "success" });
    showEditProfileModal.value = false;
  } catch (err: any) {
    uni.showToast({ title: err?.message || "保存失败", icon: "none" });
  } finally {
    savingProfile.value = false;
  }
}

const showGarminModal = ref(false);
const inputEmail = ref("");
const inputPassword = ref("");
const inputDomain = ref("garmin.cn");
const needsMfa = ref(false);
const inputMfaCode = ref("");
const binding = ref(false);
const unbinding = ref(false);
const importingGarmin = ref(false);

const showJoinModal = ref(false);
const inviteCodeInput = ref("");
const joiningClub = ref(false);
const userClubs = ref<any[]>([]);

const currentCalendarMonth = new Date().getMonth() + 1;
const targetDistance = ref(200);
const weeklyTarget = ref(50);
const currentWeekLockedTarget = ref(50);
const savingWeekly = ref(false);
const monthlyTargets = ref<number[]>(Array(12).fill(200));
const goalMode = ref<"uniform" | "custom">("uniform");
const saving = ref(false);

function handleLockedMonthTap(m: number) {
  uni.showToast({
    title: `${m}月计划已开始，锁定不可更改（仅可修改未开始的月份）`,
    icon: "none",
  });
}

function setGoalMode(mode: "uniform" | "custom") {
  goalMode.value = mode;
  if (mode === "uniform") {
    monthlyTargets.value = monthlyTargets.value.map((oldVal, idx) =>
      idx + 1 <= currentCalendarMonth ? oldVal : Number(targetDistance.value)
    );
  }
}

function onTargetSliderChange(val: number) {
  if (goalMode.value === "custom") return;
  targetDistance.value = val;
  monthlyTargets.value = monthlyTargets.value.map((oldVal, idx) =>
    idx + 1 <= currentCalendarMonth ? oldVal : Number(val)
  );
}

function setWeeklyTarget(km: number) {
  weeklyTarget.value = km;
}

function onWeeklySliderChange(val: number) {
  weeklyTarget.value = Number(val) || 50;
}

async function handleSaveWeeklyOnly() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  savingWeekly.value = true;
  try {
    const res: any = await request(`/api/profile/${encodeURIComponent(uid)}/goal`, "PUT", {
      weekly_target: Number(weeklyTarget.value),
      next_weekly_target: Number(weeklyTarget.value),
      target_period: "next_week",
      enforce_started_lock: true,
    });
    if (res?.data?.current_week_target) {
      currentWeekLockedTarget.value = Number(res.data.current_week_target);
    }
    uni.showToast({ title: `下周计划已设为 ${weeklyTarget.value}km（本周已锁定不变）`, icon: "none" });
  } catch (err: any) {
    uni.showToast({ title: err?.message || "保存失败", icon: "none" });
  } finally {
    savingWeekly.value = false;
  }
}

function syncUniformToAll() {
  monthlyTargets.value = monthlyTargets.value.map((oldVal, idx) =>
    idx + 1 <= currentCalendarMonth ? oldVal : Number(targetDistance.value)
  );
  uni.showToast({ title: `已将未开始月份设为 ${targetDistance.value}km（已开始月份锁定不变）`, icon: "none" });
}

function noop() {}

function loadRecentAccounts() {
  try {
    const list = uni.getStorageSync("rgm_recent_users") || [];
    recentAccounts.value = list;
  } catch (e) {
    recentAccounts.value = [];
  }
}

function recordRecentUser(u: any) {
  if (!u || !u.id) return;
  try {
    let recents: any[] = uni.getStorageSync("rgm_recent_users") || [];
    recents = recents.filter((item: any) => item.id !== u.id);
    recents.unshift({
      id: u.id,
      display_name: u.display_name || "微信跑者",
      avatar_url: u.avatar_url || "",
      garmin_connected: !!u.garmin_connected,
      garmin_email: u.garmin_email || "",
      garmin_domain: u.garmin_domain || "garmin.cn",
    });
    recents = recents.slice(0, 4);
    uni.setStorageSync("rgm_recent_users", recents);
    recentAccounts.value = recents;
  } catch (e) {}
}

function onChooseAvatar(e: any) {
  const avatarUrl = e.detail?.avatarUrl;
  if (avatarUrl) {
    runnerAvatar.value = avatarUrl;
  }
}

function onNicknameBlur(e: any) {
  const val = e.detail?.value;
  if (val) {
    runnerNickName.value = val;
  }
}

function onNicknameInput(e: any) {
  runnerNickName.value = e.detail?.value || "";
}

function openAuthModal() {
  showAuthModal.value = true;
}

function closeAuthModal() {
  showAuthModal.value = false;
}

function showTermsModal() {
  uni.showModal({
    title: "用户服务协议",
    content: "欢迎使用万跑跑团助手。本小程序提供科学耐力训练、心率与体能分析及跑团互动服务。我们承诺严格保护您的个人运动健康隐私，数据仅用于训练分析与展示。",
    showCancel: false,
  });
}

function showPrivacyModal() {
  uni.showModal({
    title: "隐私政策",
    content: "万跑跑团助手严格遵循法律法规保护用户隐私。您的 Garmin 账号、跑步轨迹、心率等生理指标仅在您主动授权绑定后同步，绝不对外共享。",
    showCancel: false,
  });
}

async function doConfirmLogin() {
  if (!agreedTerms.value) {
    uni.showToast({
      title: "请先勾选同意用户服务条款与隐私政策",
      icon: "none",
      duration: 2500,
    });
    return;
  }

  confirmingLogin.value = true;
  uni.showLoading({ title: "安全授权登录中...", mask: true });
  try {
    const logged = await authenticateWechatUser({
      nickName: runnerNickName.value.trim() || undefined,
      avatarUrl: runnerAvatar.value.trim() || undefined,
      agreeTerms: true,
    });
    user.value = logged;
    recordRecentUser(logged);
    showAuthModal.value = false;
    uni.hideLoading();
    uni.showToast({ title: "微信登录成功 🎉", icon: "success", duration: 2000 });

    if (runnerAvatar.value && logged?.id && (runnerAvatar.value.startsWith("wxfile://") || runnerAvatar.value.includes("tmp"))) {
      uploadAvatarFile(logged.id, runnerAvatar.value).then((permUrl) => {
        if (permUrl) {
          logged.avatar_url = permUrl;
          if (user.value) user.value.avatar_url = permUrl;
          uni.setStorageSync("rgm_user", user.value);
          recordRecentUser(user.value);
        }
      }).catch((e) => console.warn("Background avatar upload:", e));
    }

    await loadProfileData();
  } catch (err: any) {
    uni.hideLoading();
    uni.showModal({
      title: "登录失败",
      content: err.message || "微信授权失败，请稍后重试",
      showCancel: false,
    });
  } finally {
    confirmingLogin.value = false;
  }
}

async function handleAppleLogin() {
  uni.showLoading({ title: "正在连接 Apple 登录...", mask: true });
  try {
    const logged = await authenticateAppleUser();
    user.value = logged;
    recordRecentUser(logged);
    showAuthModal.value = false;
    uni.hideLoading();
    uni.showToast({ title: `欢迎回来，${logged.display_name}！`, icon: "success", duration: 2000 });
    await loadProfileData();
  } catch (err: any) {
    uni.hideLoading();
    uni.showModal({
      title: "Apple 登录提示",
      content: err?.message || "登录未完成，请重试",
      showCancel: false,
    });
  }
}

async function doDeviceLogin() {
  const acc = deviceAccount.value.trim();
  const pwd = devicePassword.value.trim();
  if (!acc || !pwd) {
    uni.showToast({ title: "请输入手表账号和密码", icon: "none" });
    return;
  }
  if (deviceNeedsMfa.value && !deviceMfaCode.value.trim()) {
    uni.showToast({ title: "请输入 6 位安全验证码", icon: "none" });
    return;
  }
  deviceLoggingIn.value = true;
  uni.showLoading({ title: "正在验证手表账号...", mask: true });
  try {
    const domain = deviceBrand.value === "garmin" ? deviceDomain.value : "teamcnapi.coros.com";
    const logged: any = await deviceLogin({
      brand: deviceBrand.value,
      account: acc,
      password: pwd,
      domain: domain,
      mfa_code: deviceNeedsMfa.value ? deviceMfaCode.value.trim() : undefined,
    });
    if (logged?.needs_2fa || logged?.needs_mfa) {
      uni.hideLoading();
      deviceNeedsMfa.value = true;
      deviceMfaHint.value = logged.message || "官方已发送 6 位安全验证码，请输入后再次点击登录";
      uni.showToast({ title: "请输入安全验证码", icon: "none", duration: 2500 });
      return;
    }
    deviceNeedsMfa.value = false;
    deviceMfaCode.value = "";
    deviceMfaHint.value = "";
    user.value = logged;
    recordRecentUser(logged);
    showAuthModal.value = false;
    uni.hideLoading();
    uni.showToast({ title: `欢迎回来，${logged.display_name}！`, icon: "success", duration: 2500 });
    await loadProfileData();
  } catch (err: any) {
    uni.hideLoading();
    uni.showModal({
      title: "登录失败",
      content: err?.message || "账号或密码错误，请核对后重试",
      showCancel: false,
    });
  } finally {
    deviceLoggingIn.value = false;
  }
}

function handleLogout() {
  openAuthModal();
}

function handleConfirmLogout() {
  uni.showModal({
    title: "退出登录",
    content: "确定要退出当前微信跑者账号吗？",
    success: async (res) => {
      if (res.confirm) {
        clearSession();
        user.value = null;
        profile.value = defaultProfile;
        garminConnected.value = false;
        corosConnected.value = false;
        appleWatchConnected.value = false;
        huaweiConnected.value = false;
        huaweiAccount.value = "";
        suuntoConnected.value = false;
        suuntoAccount.value = "";
        userClub.value = null;
        races.value = [];
        uni.showToast({ title: "已退出登录", icon: "none" });
      }
    }
  });
}

function formatSecs(secs?: number): string {
  if (!secs || secs <= 0) return "—";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

async function loadProfileData() {
  user.value = getStoredUser();
  if (!user.value || !user.value.id) {
    try {
      const logged = await authenticateWechatUser();
      if (logged && logged.id) {
        user.value = logged;
      }
    } catch (e) {
      console.warn("Silent login fallback in profile:", e);
    }
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    const [res, clubRes, orgRes, onboardRes] = await Promise.all([
      request(`/api/profile/${uid}`),
      request(`/api/team/my-clubs/${uid}`),
      request(`/api/org/my-orgs/${uid}`),
      request(`/api/profile/${uid}/onboarding-status`).catch(() => null),
    ]);

    if (onboardRes) {
      onboardingStatus.value = onboardRes;
    }

    userOrgs.value = orgRes?.organizations || [];

    if (res?.profile) {
      profile.value = res.profile;
      if (res.profile.gobi_experience) {
        if (res.profile.gobi_experience === "新戈") {
          gobiType.value = "new";
        } else {
          gobiType.value = "vet";
          const parts = res.profile.gobi_experience.split(" ");
          if (parts[0]) gobiEdition.value = parts[0];
          if (parts[1]) gobiGroup.value = parts[1];
        }
      }
      if (!user.value) user.value = {} as any;
      user.value.id = res.profile.id || uid;
      if (res.profile.avatar_url) user.value.avatar_url = res.profile.avatar_url;
      if (res.profile.display_name) user.value.display_name = res.profile.display_name;
      user.value.garmin_connected = !!res.profile.garmin_connected;
      user.value.coros_connected = !!res.profile.coros_connected;
      user.value.apple_watch_connected = !!res.profile.apple_watch_connected;
      user.value.huawei_connected = !!res.profile.huawei_connected;
      user.value.huawei_account = res.profile.huawei_account || "";
      user.value.suunto_connected = !!res.profile.suunto_connected;
      user.value.suunto_account = res.profile.suunto_account || "";
      uni.setStorageSync("rgm_user", user.value);
      garminConnected.value = !!res.profile.garmin_connected;
      garminEmail.value = res.profile.garmin_email || "";
      garminDomain.value = res.profile.garmin_domain || "garmin.cn";
      inputDomain.value = garminDomain.value;
      corosConnected.value = !!res.profile.coros_connected;
      corosAccount.value = res.profile.coros_account || "";
      corosDomain.value = res.profile.coros_domain || "teamcnapi.coros.com";
      corosNeedsReauth.value = !!res.profile.coros_needs_reauth;
      corosAuthError.value = res.profile.coros_auth_error || "";
      corosHasSavedPassword.value = !!res.profile.coros_has_saved_password;
      inputCorosDomain.value = corosDomain.value;
      appleWatchConnected.value = !!res.profile.apple_watch_connected;
      huaweiConnected.value = !!res.profile.huawei_connected;
      huaweiAccount.value = res.profile.huawei_account || "";
      if (huaweiAccount.value) {
        inputHuaweiAccount.value = huaweiAccount.value;
      }
      suuntoConnected.value = !!res.profile.suunto_connected;
      suuntoAccount.value = res.profile.suunto_account || "";
      if (suuntoAccount.value) {
        inputSuuntoAccount.value = suuntoAccount.value;
      }
    } else {
      garminConnected.value = false;
      corosConnected.value = false;
      corosNeedsReauth.value = false;
      corosAuthError.value = "";
      corosHasSavedPassword.value = false;
      appleWatchConnected.value = false;
      huaweiConnected.value = false;
      huaweiAccount.value = "";
      suuntoConnected.value = false;
      suuntoAccount.value = "";
    }

    if (res?.goal) {
      targetDistance.value = res.goal.target_distance || 200;
      const fallbackWk = Math.round((res.goal.target_distance || 200) / 4) || 50;
      weeklyTarget.value = res.goal.next_weekly_target || res.goal.weekly_target || fallbackWk;
      currentWeekLockedTarget.value = res.goal.current_week_target || res.goal.weekly_target || fallbackWk;
      if (res.goal.monthly_targets && Array.isArray(res.goal.monthly_targets)) {
        monthlyTargets.value = res.goal.monthly_targets;
        const allSame = res.goal.monthly_targets.every((v: number) => v === res.goal.target_distance);
        goalMode.value = allSame ? "uniform" : "custom";
      } else {
        monthlyTargets.value = Array(12).fill(targetDistance.value);
        goalMode.value = "uniform";
      }
    }

    if (res?.races) {
      races.value = res.races;
    }

    const clubs = clubRes?.clubs || [];
    userClubs.value = clubs;
    userClub.value = resolveActiveClub(clubs);

    loadMySupportTickets();

    // ── Check if user has temporary or suspended org memberships → show reminder ──
    checkOrgMembershipReminder(uid, userOrgs.value);
  } catch (err) {
    console.error("Failed to load profile:", err);
  }
}

// Popup reminder: if user belongs to any org with 'suspended' or 'temporary' status
async function checkOrgMembershipReminder(uid: string, orgsList?: any[]) {
  try {
    const orgs: any[] = orgsList || (await request(`/api/org/my-orgs/${uid}`))?.organizations || [];
    const suspendedMemberships = orgs.filter((o: any) => o.status === "expired" || o.status === "suspended" || o.is_suspended);
    if (suspendedMemberships.length > 0) {
      const firstOrg = suspendedMemberships[0];
      uni.showModal({
        title: "⚠️ 大群访问已被暂停",
        content: `您在【${firstOrg.name}】的2周临时访问期已过。由于超期未完成必填字段并获管理员审核确认，已暂停浏览使用该大群及其分队的一切内容和活动！请立即补齐必填资料并联系管理员核验。`,
        confirmText: "立即补齐",
        cancelText: "知道了",
        confirmColor: "#ef4444",
        success: (res) => {
          if (res.confirm) {
            scrollToRequiredFields();
          }
        }
      });
      return;
    }

    const incompleteMemberships = orgs.filter((o: any) => o.status === "temporary");
    if (incompleteMemberships.length > 0) {
      const firstOrg = incompleteMemberships[0];
      const missingLabels = (firstOrg.missing_fields || []).map((f: any) => f.label).join("、");
      const orgCount = incompleteMemberships.length;
      const orgNames = incompleteMemberships.map((o: any) => o.name).join("、");
      const remainingDays = firstOrg.days_remaining !== undefined && firstOrg.days_remaining !== null ? firstOrg.days_remaining : 14;
      const contentText = orgCount > 1
        ? `您在 ${orgCount} 个大群（${orgNames}）中有必填资料尚未完成（临时访问期还剩 ${remainingDays} 天）。请在2周内补齐并获得管理员审核批准，超期将被暂停大群及分队的浏览与活动！`
        : `您在【${firstOrg.name}】中${missingLabels ? '还缺少：' + missingLabels + '。' : '有必填资料尚未完成。'}（临时访问期还剩 ${remainingDays} 天）请在2周内补齐并获得管理员审核批准，超期将被暂停大群及分队的浏览与活动！`;
      uni.showModal({
        title: "📋 跑者档案待完善",
        content: contentText,
        confirmText: "立即填写",
        cancelText: "稍后再说",
        confirmColor: "#f59e0b",
        success: (res) => {
          if (res.confirm) {
            scrollToRequiredFields();
          }
        }
      });
    }
  } catch (e) {
    // Silent fail – reminder is optional
  }
}

async function handleUpdateRacePriority(raceIdOrName: string, priority: number) {
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;
  try {
    uni.showLoading({ title: "更新赛事定位..." });
    await request(`/api/profile/${uid}/races/${raceIdOrName}/priority`, "POST", { priority });
    uni.hideLoading();
    uni.showToast({ title: "已更新赛事定位", icon: "success" });
    const found = races.value.find((r: any) => r.id === raceIdOrName || r.name === raceIdOrName);
    if (found) {
      found.priority = priority;
    }
  } catch (e) {
    uni.hideLoading();
    uni.showToast({ title: "更新失败", icon: "none" });
  }
}

// ── Race Management & Intelligence Helper Functions ──

function getRaceKey(race: any, idx?: number): string {
  if (race?.id) return String(race.id);
  if (race?.name) return String(race.name);
  return String(idx ?? "unknown");
}

const matchingWatchActivity = ref(false);
const uploadingModalPhoto = ref(false);

function parseTimeToSec(tStr: string): number | null {
  if (!tStr) return null;
  const parts = tStr.trim().split(":");
  try {
    if (parts.length === 3) return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
    if (parts.length === 2) return parseInt(parts[0]) * 60 + parseInt(parts[1]);
  } catch {}
  return null;
}

function formatSecToTime(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const calcModalDiff = computed(() => {
  if (!raceForm.value.finish_time || !raceForm.value.target_time) return null;
  const tSec = parseTimeToSec(raceForm.value.target_time);
  const fSec = parseTimeToSec(raceForm.value.finish_time);
  if (!tSec || !fSec) return null;
  const diff = fSec - tSec;
  if (diff < 0) {
    return {
      isFaster: true,
      str: `-${formatSecToTime(Math.abs(diff))}`,
      badge: "超额达标 🎉",
    };
  } else if (diff === 0) {
    return {
      isFaster: true,
      str: "精准达标",
      badge: "精准达标 🎯",
    };
  } else {
    return {
      isFaster: false,
      str: `+${formatSecToTime(diff)}`,
      badge: "顺利完赛 🏅",
    };
  }
});

async function handleModalMatchActivity() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  if (!raceForm.value.race_date) {
    uni.showToast({ title: "请先选择比赛日期", icon: "none" });
    return;
  }
  matchingWatchActivity.value = true;
  uni.showLoading({ title: "正在匹配记录..." });
  try {
    const raceId = raceForm.value.id || "temp";
    const res = await request(`/api/profile/${uid}/races/${raceId}/matched-activity?race_date=${raceForm.value.race_date}`);
    uni.hideLoading();
    if (res?.matched && res?.activity) {
      const act = res.activity;
      raceForm.value.status = "completed";
      raceForm.value.finish_time = act.formatted_time || "";
      if (!raceForm.value.finish_notes) {
        raceForm.value.finish_notes = `匹配手表记录【${act.name}】(${act.distance_km}km, 配速 ${act.avg_pace_str})`;
      }
      uni.showToast({
        title: `已匹配用时: ${act.formatted_time}`,
        icon: "success"
      });
    } else {
      uni.showToast({
        title: res?.message || "未在比赛日找到匹配记录",
        icon: "none"
      });
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: "检索失败: " + (e?.message || e), icon: "none" });
  } finally {
    matchingWatchActivity.value = false;
  }
}

function choosePhotoFromDevice(): Promise<string> {
  return new Promise((resolve, reject) => {
    // #ifdef MP-WEIXIN
    if (typeof uni.chooseMedia === "function") {
      uni.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        sizeType: ["compressed"],
        success: (res: any) => {
          const file = res.tempFiles?.[0];
          if (file && file.tempFilePath) {
            resolve(file.tempFilePath);
          } else {
            reject(new Error("未获取到图片"));
          }
        },
        fail: (err: any) => {
          if (err?.errMsg && err.errMsg.includes("cancel")) {
            reject(new Error("CANCEL"));
          } else {
            console.warn("chooseMedia failed, fallback to chooseImage:", err);
            fallbackChooseImage(resolve, reject);
          }
        }
      });
      return;
    }
    // #endif
    fallbackChooseImage(resolve, reject);
  });
}

function fallbackChooseImage(resolve: (p: string) => void, reject: (e: any) => void) {
  uni.chooseImage({
    count: 1,
    sizeType: ["compressed"],
    sourceType: ["album", "camera"],
    success: (res: any) => {
      if (res.tempFilePaths && res.tempFilePaths[0]) {
        resolve(res.tempFilePaths[0]);
      } else {
        reject(new Error("未获取到图片"));
      }
    },
    fail: (err: any) => {
      if (err?.errMsg && err.errMsg.includes("cancel")) {
        reject(new Error("CANCEL"));
      } else {
        reject(new Error(err?.errMsg || "选择图片失败"));
      }
    }
  });
}

async function handleChooseRacePhoto() {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  const raceId = raceForm.value.id || `race_${Date.now()}`;
  if (!raceForm.value.id) {
    raceForm.value.id = raceId;
  }

  let tempFilePath = "";
  try {
    tempFilePath = await choosePhotoFromDevice();
  } catch (e: any) {
    if (e?.message !== "CANCEL") {
      uni.showToast({ title: e?.message || "选择图片失败", icon: "none" });
    }
    return;
  }

  uploadingModalPhoto.value = true;
  uni.showLoading({ title: "正在压缩上传..." });
  try {
    const photoUrl = await uploadRacePhoto(uid, raceId, tempFilePath);
    uni.hideLoading();
    if (!raceForm.value.photos) raceForm.value.photos = [];
    if (!raceForm.value.photos.includes(photoUrl)) {
      raceForm.value.photos = [...raceForm.value.photos, photoUrl];
    }
    raceForm.value.photo_url = photoUrl;
    raceForm.value = { ...raceForm.value };
    // Synchronize card list immediately if this race exists
    const curRaceId = raceForm.value.id || raceForm.value.name;
    if (curRaceId && races.value) {
      races.value = races.value.map((r: any) =>
        (r.id === curRaceId || r.name === curRaceId)
          ? { ...r, photo_url: photoUrl, photos: [...raceForm.value.photos] }
          : r
      );
    }
    uni.showToast({ title: "照片上传成功 📸", icon: "success" });
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: err?.message || "上传失败", icon: "none" });
  } finally {
    uploadingModalPhoto.value = false;
  }
}

async function handleCardQuickUploadPhoto(race: any) {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  const raceId = race.id || race.name;

  let tempFilePath = "";
  try {
    tempFilePath = await choosePhotoFromDevice();
  } catch (e: any) {
    if (e?.message !== "CANCEL") {
      uni.showToast({ title: e?.message || "选择图片失败", icon: "none" });
    }
    return;
  }

  uni.showLoading({ title: "正在压缩上传..." });
  try {
    const photoUrl = await uploadRacePhoto(uid, raceId, tempFilePath);
    uni.hideLoading();
    if (!race.photos) race.photos = [];
    if (!race.photos.includes(photoUrl)) {
      race.photos = [...race.photos, photoUrl];
    }
    race.photo_url = photoUrl;

    // Force reactive UI update on MiniProgram by replacing array reference
    races.value = races.value.map((r: any) =>
      (r.id === raceId || r.name === raceId)
        ? { ...r, photo_url: photoUrl, photos: [...race.photos] }
        : r
    );
    uni.showToast({ title: "完赛照片上传成功 📸", icon: "success" });

    // Request authoritative data from backend to ensure persistent sync
    try {
      const res: any = await request(`/api/profile/${uid}/races`);
      if (res && res.races) {
        races.value = res.races;
      }
    } catch (fetchErr) {
      console.warn("fetch races after photo upload error:", fetchErr);
    }
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: err?.message || "上传失败", icon: "none" });
  }
}

const showRaceShareCard = ref(false);
const activeShareRaceId = ref("");

function openCompletedRaceShareCard(race: any) {
  if (!race) return;
  activeShareRaceId.value = String(race.id || race.name || "");
  showRaceShareCard.value = true;
}

function handleCardPhotoAction(photoUrl: string, race: any) {
  uni.showActionSheet({
    itemList: ["放大查看大图 🔍", "删除此照片 🗑️"],
    success: async (res) => {
      if (res.tapIndex === 0) {
        handlePreviewImage(photoUrl, race.photos);
      } else if (res.tapIndex === 1) {
        uni.showModal({
          title: "确认删除照片",
          content: "确定要从该比赛中删除这张完赛照片吗？",
          confirmText: "删除",
          confirmColor: "#ef4444",
          success: async (confirmRes) => {
            if (confirmRes.confirm) {
              const uid = user.value?.id || getStoredUser()?.id;
              const raceId = race.id || race.name;
              if (uid && raceId) {
                try {
                  uni.showLoading({ title: "正在删除..." });
                  await deleteRacePhoto(uid, raceId, photoUrl);
                  uni.hideLoading();
                  if (race.photos) {
                    race.photos = race.photos.filter((p: string) => p !== photoUrl);
                    race.photo_url = race.photos[0] || "";
                  }
                  races.value = races.value.map((r: any) =>
                    (r.id === raceId || r.name === raceId)
                      ? { ...r, photo_url: race.photo_url, photos: race.photos ? [...race.photos] : [] }
                      : r
                  );
                  uni.showToast({ title: "照片已删除", icon: "success" });
                  try {
                    const rRes: any = await request(`/api/profile/${uid}/races`);
                    if (rRes?.races) races.value = rRes.races;
                  } catch (e) {}
                } catch (err: any) {
                  uni.hideLoading();
                  uni.showToast({ title: err?.message || "删除失败", icon: "none" });
                }
              }
            }
          },
        });
      }
    },
  });
}

async function handleDeleteModalPhoto(photoUrl: string) {
  if (!raceForm.value.photos) return;
  raceForm.value.photos = raceForm.value.photos.filter((p: string) => p !== photoUrl);
  raceForm.value.photo_url = raceForm.value.photos[0] || "";
  raceForm.value = { ...raceForm.value };

  const curRaceId = raceForm.value.id || raceForm.value.name;
  if (curRaceId && races.value) {
    races.value = races.value.map((r: any) =>
      (r.id === curRaceId || r.name === curRaceId)
        ? { ...r, photo_url: raceForm.value.photo_url, photos: [...raceForm.value.photos] }
        : r
    );
  }

  // If the race already exists on server, trigger backend deletion in background
  const uid = user.value?.id || getStoredUser()?.id;
  const raceId = raceForm.value.id;
  if (uid && raceId) {
    try {
      await deleteRacePhoto(uid, raceId, photoUrl);
    } catch (e) {
      console.warn("delete race photo err:", e);
    }
  }
}

function handlePreviewImage(current: string, urls?: string[]) {
  uni.previewImage({
    current,
    urls: urls && urls.length ? urls : [current],
  });
}

function openAddRaceModal() {
  const future = new Date();
  future.setDate(future.getDate() + 60);
  const dateStr = future.toISOString().slice(0, 10);
  raceForm.value = {
    id: "",
    name: "",
    race_type: "全马 (42.195K)",
    race_date: dateStr,
    target_time: "3:30:00",
    priority: 1,
    status: "upcoming",
    finish_time: "",
    finish_notes: "",
    photo_url: "",
    photos: [],
    was_official_pacer: false,
    pacer_target_time: "",
    race_info: {},
  };
  raceModalMode.value = "add";
  modalExpandRaceInfo.value = true;
  showRaceModal.value = true;
}

function openEditRaceModal(race: any) {
  raceForm.value = {
    id: race.id || "",
    name: race.name || "",
    race_type: race.race_type || "全马 (42.195K)",
    race_date: race.race_date || "",
    target_time: race.target_time || "3:30:00",
    priority: race.priority || 1,
    status: race.status || (race.is_completed ? "completed" : "upcoming"),
    finish_time: race.finish_time || "",
    finish_notes: race.finish_notes || "",
    photo_url: race.photo_url || "",
    photos: race.photos ? [...race.photos] : [],
    was_official_pacer: Boolean(race.was_official_pacer),
    pacer_target_time: race.pacer_target_time || race.target_time || "",
    race_info: { ...(race.race_info || {}) },
  };
  raceModalMode.value = "edit";
  modalExpandRaceInfo.value = true;
  showRaceModal.value = true;
}

async function handleSaveRaceModal() {
  if (!raceForm.value.name.trim()) {
    uni.showToast({ title: "请输入比赛名称", icon: "none" });
    return;
  }
  if (!raceForm.value.race_date) {
    uni.showToast({ title: "请选择比赛日期", icon: "none" });
    return;
  }
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }

  savingRace.value = true;
  uni.showLoading({ title: "正在保存赛事..." });
  try {
    const payload = {
      id: raceForm.value.id || undefined,
      name: raceForm.value.name.trim(),
      race_type: raceForm.value.race_type,
      race_date: raceForm.value.race_date,
      target_time: raceForm.value.target_time.trim() || "3:30:00",
      priority: raceForm.value.priority,
      status: raceForm.value.status || "upcoming",
      finish_time: raceForm.value.finish_time ? raceForm.value.finish_time.trim() : undefined,
      finish_notes: raceForm.value.finish_notes ? raceForm.value.finish_notes.trim() : undefined,
      photo_url: raceForm.value.photo_url || undefined,
      photos: raceForm.value.photos || [],
      was_official_pacer: Boolean(raceForm.value.was_official_pacer),
      pacer_target_time: raceForm.value.was_official_pacer
        ? (raceForm.value.pacer_target_time || raceForm.value.target_time || "").trim()
        : "",
      race_info: raceForm.value.race_info,
    };
    const res = await request(`/api/profile/${uid}/races`, "POST", payload);
    uni.hideLoading();
    if (res?.races) {
      races.value = res.races;
    }
    showRaceModal.value = false;
    uni.showToast({
      title: raceModalMode.value === "add" ? "赛事添加成功 🎉" : "赛事保存成功 ✓",
      icon: "success",
    });
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: err?.message || "保存失败，请重试", icon: "none" });
  } finally {
    savingRace.value = false;
  }
}

function handleDeleteRace(race: any) {
  const uid = user.value?.id;
  if (!uid) return;
  const raceId = race.id || race.name;
  uni.showModal({
    title: "删除比赛计划",
    content: `确定要删除「${race.name}」吗？`,
    confirmText: "删除",
    confirmColor: "#ff4d4f",
    success: async (res) => {
      if (res.confirm) {
        try {
          uni.showLoading({ title: "正在删除..." });
          const delRes = await request(
            `/api/profile/${uid}/races/${encodeURIComponent(raceId)}`,
            "DELETE"
          );
          uni.hideLoading();
          if (delRes?.races) {
            races.value = delRes.races;
          } else {
            races.value = races.value.filter((r) => (r.id || r.name) !== raceId);
          }
          if (showRaceModal.value) {
            showRaceModal.value = false;
          }
          uni.showToast({ title: "赛事已删除", icon: "success" });
        } catch (e: any) {
          uni.hideLoading();
          uni.showToast({ title: e?.message || "删除失败", icon: "none" });
        }
      }
    },
  });
}

async function handleModalAutoFetchRaceInfo() {
  if (!raceForm.value.name.trim()) {
    uni.showToast({ title: "请先输入比赛名称", icon: "none" });
    return;
  }
  modalSearchingRaceInfo.value = true;
  uni.showLoading({ title: "检索赛事情报中..." });
  try {
    const res = await request("/api/profile/race-intel-lookup", "POST", {
      race_name: raceForm.value.name.trim(),
      race_type: raceForm.value.race_type,
      target_time: raceForm.value.target_time,
      race_date: raceForm.value.race_date,
      race_id: raceForm.value.id,
      user_id: user.value?.id,
    });
    uni.hideLoading();
    if (res?.success && res?.race_info) {
      raceForm.value.race_info = {
        ...raceForm.value.race_info,
        ...res.race_info,
      };
      if (res.race_category === "trail" && !raceForm.value.race_type.includes("越野")) {
        const dist = res.race_info.race_distance_km ? `${res.race_info.race_distance_km}K` : "50K";
        raceForm.value.race_type = `越野跑 ${dist}`;
      }
      modalExpandRaceInfo.value = true;
      uni.showToast({ title: "已自动填充赛事情报 ✓", icon: "success" });
    } else {
      uni.showToast({ title: res?.message || "未检索到，可手动填写", icon: "none" });
    }
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: "检索失败，可手动填写", icon: "none" });
  } finally {
    modalSearchingRaceInfo.value = false;
  }
}

function isTrail(raceType: string): boolean {
  if (!raceType) return false;
  const t = raceType.toLowerCase();
  return t.includes("trail") || t.includes("越野") || t.includes("山地");
}

function hasRaceInfo(race: any): boolean {
  const ri = race?.race_info || {};
  return Object.values(ri).some((v) => v !== null && v !== undefined && v !== "");
}

function toggleRaceInfo(raceKey: string) {
  expandedRaceInfo.value = {
    ...expandedRaceInfo.value,
    [raceKey]: !expandedRaceInfo.value[raceKey],
  };
}

function getRaceInfoVal(race: any, field: string): any {
  const raceKey = getRaceKey(race);
  if (raceInfoDrafts.value[raceKey] && field in raceInfoDrafts.value[raceKey]) {
    const v = raceInfoDrafts.value[raceKey][field];
    return v === null ? "" : v;
  }
  const v = (race?.race_info || {})[field];
  return v === null || v === undefined ? "" : v;
}

function setRaceInfoVal(race: any, field: string, value: any) {
  const raceKey = getRaceKey(race);
  if (!raceInfoDrafts.value[raceKey]) {
    raceInfoDrafts.value[raceKey] = {};
  }
  raceInfoDrafts.value[raceKey][field] = value;
}

async function handleSaveRaceInfo(race: any) {
  const uid = user.value?.id;
  if (!uid) return;
  const raceKey = getRaceKey(race);
  const raceId = race.id || race.name;
  savingRaceInfo.value = { ...savingRaceInfo.value, [raceKey]: true };
  try {
    const merged = {
      ...(race.race_info || {}),
      ...(raceInfoDrafts.value[raceKey] || {}),
    };
    const cleaned: Record<string, any> = {};
    for (const [k, v] of Object.entries(merged)) {
      if (v !== null && v !== undefined && v !== "") {
        cleaned[k] = v;
      }
    }
    const res = await request(
      `/api/profile/${uid}/races/${encodeURIComponent(raceId)}/info`,
      "PATCH",
      { race_info: cleaned }
    );
    if (res?.races) {
      races.value = res.races;
    } else {
      const found = races.value.find((r: any) => (r.id || r.name) === raceId);
      if (found) found.race_info = cleaned;
    }
    const { [raceKey]: _, ...rest } = raceInfoDrafts.value;
    raceInfoDrafts.value = rest;
    uni.showToast({ title: "赛事情报已保存 ✓", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "保存失败，请重试", icon: "none" });
  } finally {
    savingRaceInfo.value = { ...savingRaceInfo.value, [raceKey]: false };
  }
}

const searchingRaceInfo = ref<Record<string, boolean>>({});

async function handleAutoFetchRaceInfo(race: any) {
  if (!race.name || !race.name.trim()) {
    uni.showToast({ title: "请先输入比赛名称", icon: "none" });
    return;
  }
  const raceKey = getRaceKey(race);
  searchingRaceInfo.value = { ...searchingRaceInfo.value, [raceKey]: true };
  uni.showLoading({ title: "检索赛事情报中..." });
  try {
    const res = await request("/api/profile/race-intel-lookup", "POST", {
      race_name: race.name.trim(),
      race_type: race.race_type,
      target_time: race.target_time,
      race_date: race.race_date,
      race_id: race.id,
      user_id: user.value?.id,
    });
    uni.hideLoading();
    if (res?.success && res?.race_info) {
      race.race_info = {
        ...(race.race_info || {}),
        ...res.race_info,
      };
      raceInfoDrafts.value[raceKey] = {
        ...(raceInfoDrafts.value[raceKey] || {}),
        ...res.race_info,
      };
      expandedRaceInfo.value[raceKey] = true;
      uni.showToast({ title: "已同步官方赛事情报 ✓", icon: "success" });
    } else {
      uni.showToast({ title: res?.message || "未能检索到，请手动填写", icon: "none" });
    }
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: "检索超时，请稍后重试", icon: "none" });
  } finally {
    searchingRaceInfo.value = { ...searchingRaceInfo.value, [raceKey]: false };
  }
}



function goToTeamPage() {
  uni.switchTab({
    url: "/pages/team/team",
  });
}

function goToCreateMyClub() {
  uni.setStorageSync("team_open_create_club", true);
  uni.switchTab({
    url: "/pages/team/team",
  });
}

async function handleJoinClub() {
  if (!inviteCodeInput.value.trim()) return;
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
    await loadProfileData();
  } catch (e: any) {
    const msg = e.message || "加入失败，请核对邀请码";
    if (msg.includes("大群体") || msg.includes("戈友")) {
      uni.showModal({
        title: "大群认证提示",
        content: msg,
        confirmText: "前往认证",
        cancelText: "知道了",
        success: (modalRes) => {
          if (modalRes.confirm) {
            showJoinModal.value = false;
            // 跑团首页已是 Tab 页，只能用 switchTab
            uni.switchTab({ url: "/pages/team/team" });
          }
        }
      });
    } else {
      uni.showToast({ title: msg, icon: "none" });
    }
  } finally {
    joiningClub.value = false;
  }
}

function onMonthTargetInput(idx: number, val: string) {
  if (idx + 1 <= currentCalendarMonth) {
    uni.showToast({
      title: `${idx + 1}月计划已开始，锁定不可更改！`,
      icon: "none",
    });
    return;
  }
  const num = parseInt(val, 10) || 0;
  monthlyTargets.value[idx] = num;
  monthlyTargets.value = [...monthlyTargets.value];
}

function onInputMaxHr(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.max_heart_rate = parseInt(e.detail.value, 10) || 0;
}

function onInputRestHr(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.resting_heart_rate = parseInt(e.detail.value, 10) || 0;
}

function onInputHeight(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.height = parseFloat(e.detail.value) || 0;
  profile.value.height_cm = profile.value.height;
}

function onInputWeight(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.weight = parseFloat(e.detail.value) || 0;
  profile.value.weight_kg = profile.value.weight;
}

const syncingDeviceProfile = ref(false);

const todayDateStr = computed(() => {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
});

function computeAge(dobStr?: string): number | null {
  if (!dobStr) return null;
  try {
    const parts = String(dobStr).slice(0, 10).split("-");
    if (parts.length < 3) return null;
    const y = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10) - 1;
    const d = parseInt(parts[2], 10);
    const dob = new Date(y, m, d);
    if (isNaN(dob.getTime())) return null;
    const today = new Date();
    let a = today.getFullYear() - dob.getFullYear();
    const monthDiff = today.getMonth() - dob.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
      a--;
    }
    return Math.max(0, a);
  } catch {
    return null;
  }
}

const displayAge = computed(() => {
  if (profile.value?.age !== undefined && profile.value?.age !== null) {
    return profile.value.age;
  }
  return computeAge(profile.value?.date_of_birth);
});

function onDateOfBirthChange(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.date_of_birth = e.detail?.value || "";
  profile.value.age = computeAge(profile.value.date_of_birth);
}

function onGenderSelect(g: string) {
  if (!profile.value) profile.value = {};
  profile.value.gender = g;
}

function onInputVo2max(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.vo2max = e.detail?.value ? parseFloat(e.detail.value) : null;
}

function onInputYearsRunning(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.years_running = e.detail?.value ? parseInt(e.detail.value, 10) : null;
}

function onInputRealName(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.real_name = e.detail?.value || "";
}

function onInputPhone(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.phone = e.detail?.value || "";
}

function onInputIdCard(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.id_card = e.detail?.value || "";
}

function onSelectProgram(prog: string) {
  if (!profile.value) profile.value = {};
  profile.value.program = prog;
}

function onInputClassDetail(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.class_detail = e.detail?.value || "";
}

function onSelectGobiType(type: "new" | "vet") {
  gobiType.value = type;
}

function onGobiEditionChange(e: any) {
  const idx = Number(e.detail?.value);
  if (!isNaN(idx) && GOBI_EDITIONS[idx]) {
    gobiEdition.value = GOBI_EDITIONS[idx];
  }
}

function onSelectGobiGroup(grp: string) {
  gobiGroup.value = grp;
}

function onInputEmergencyContact(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.emergency_contact = e.detail?.value || "";
}

function onClothingSizeChange(e: any) {
  const idx = Number(e.detail?.value);
  if (!isNaN(idx) && CLOTHING_SIZES[idx]) {
    if (!profile.value) profile.value = {};
    profile.value.clothing_size = CLOTHING_SIZES[idx];
  }
}

function onInputShoeSize(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.shoe_size = e.detail?.value || "";
}

function onFirstAidCertChange(e: any) {
  const idx = Number(e.detail?.value || 0);
  if (!profile.value) profile.value = {};
  profile.value.first_aid_cert_type = FIRST_AID_CERT_CODES[idx] ?? "";
}

function onToggleRaceOfficialPacer(e: any) {
  const checked = Boolean(e.detail?.value);
  raceForm.value.was_official_pacer = checked;
  if (checked && !raceForm.value.pacer_target_time && raceForm.value.target_time) {
    raceForm.value.pacer_target_time = raceForm.value.target_time;
  }
}

function onToggleHealthDeclaration() {
  if (!profile.value) profile.value = {};
  profile.value.health_declaration = !(profile.value.health_declaration !== false);
}

async function handleSyncDeviceProfile() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  if (!garminConnected.value && !corosConnected.value) {
    uni.showToast({ title: "请先连接 Garmin 或高驰", icon: "none" });
    return;
  }
  syncingDeviceProfile.value = true;
  try {
    uni.showLoading({ title: "同步手表身体数据..." });
    const res = await request(`/api/profile/${uid}/sync-device-profile`, "POST");
    uni.hideLoading();
    if (res?.success && res?.profile) {
      profile.value = { ...profile.value, ...res.profile };
      if (res.profile.avatar_url && !user.value?.avatar_url) {
        user.value.avatar_url = res.profile.avatar_url;
      }
      if (res.profile.display_name && (!user.value?.display_name || user.value.display_name === "微信跑者")) {
        user.value.display_name = res.profile.display_name;
      }
      uni.showToast({ title: res.message || "同步成功！", icon: "success" });
    } else {
      uni.showToast({ title: res?.message || "未能获取到手表数据", icon: "none" });
    }
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: err?.message || "同步失败，请检查手表连接", icon: "none" });
  } finally {
    syncingDeviceProfile.value = false;
  }
}

const estimatingVo2 = ref(false);

async function handleEstimateVo2max() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  estimatingVo2.value = true;
  try {
    uni.showLoading({ title: "依据成绩测算中..." });
    const res = await request(`/api/profile/${uid}/estimate-vo2max`, "POST", {
      five_k_pb: profile.value?.five_k_pb,
      ten_k_pb: profile.value?.ten_k_pb,
      half_pb: profile.value?.half_pb,
      marathon_pb: profile.value?.marathon_pb,
      max_heart_rate: profile.value?.max_heart_rate,
      resting_heart_rate: profile.value?.resting_heart_rate,
      save: false,
    });
    uni.hideLoading();
    if (res?.success && res?.estimated_vo2max) {
      if (!profile.value) profile.value = {};
      profile.value.vo2max = res.estimated_vo2max;
      uni.showModal({
        title: "VO2Max 测算成功",
        content: `${res.message}\n\n已自动填入输入框，点击页面下方“保存个人资料与目标”即可正式生效。`,
        showCancel: false,
        confirmText: "我知道了"
      });
    } else {
      uni.showToast({ title: res?.message || "未能测算出数值，请确认已填入 PB 成绩", icon: "none" });
    }
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: err?.message || "推算失败", icon: "none" });
  } finally {
    estimatingVo2.value = false;
  }
}

async function handleSaveAll() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  saving.value = true;
  try {
    const effGobiExp = gobiType.value === "new" ? "新戈" : `${gobiEdition.value} ${gobiGroup.value}`;
    const effClassName = profile.value?.program
      ? `${profile.value.program} ${profile.value?.class_detail || ""}`.trim()
      : (profile.value?.class_name?.trim() || null);

    await request(`/api/profile/${uid}`, "PUT", {
      max_heart_rate: profile.value?.max_heart_rate,
      resting_heart_rate: profile.value?.resting_heart_rate,
      height_cm: profile.value?.height || profile.value?.height_cm,
      weight_kg: profile.value?.weight || profile.value?.weight_kg,
      gender: profile.value?.gender,
      date_of_birth: profile.value?.date_of_birth,
      real_name: profile.value?.real_name,
      phone: profile.value?.phone,
      id_card: profile.value?.id_card,
      program: profile.value?.program || null,
      class_detail: profile.value?.class_detail || null,
      class_name: effClassName,
      gobi_experience: effGobiExp,
      emergency_contact: profile.value?.emergency_contact || null,
      clothing_size: profile.value?.clothing_size || null,
      shoe_size: profile.value?.shoe_size || null,
      first_aid_cert_type: profile.value?.first_aid_cert_type ?? "",
      health_declaration: profile.value?.health_declaration !== undefined ? profile.value?.health_declaration : true,
      vo2max: profile.value?.vo2max !== undefined && profile.value?.vo2max !== null && profile.value?.vo2max !== "" ? Number(profile.value.vo2max) : null,
      years_running: profile.value?.years_running,
      hide_gps_route: !!profile.value?.hide_gps_route,
      hide_biometrics: !!profile.value?.hide_biometrics,
    });

    const finalMonthlyTargets = monthlyTargets.value.map((v, idx) => {
      if (idx + 1 <= currentCalendarMonth) return Number(v) || 0;
      return goalMode.value === "uniform" ? Number(targetDistance.value) : (Number(v) || 0);
    });

    const goalRes: any = await request(`/api/profile/${encodeURIComponent(uid)}/goal`, "PUT", {
      target_distance: Number(targetDistance.value),
      weekly_target: Number(weeklyTarget.value),
      next_weekly_target: Number(weeklyTarget.value),
      period_type: "monthly",
      monthly_targets: finalMonthlyTargets,
      enforce_started_lock: true,
    });
    if (goalRes?.data?.monthly_targets) {
      monthlyTargets.value = goalRes.data.monthly_targets;
    }
    if (goalRes?.data?.current_week_target) {
      currentWeekLockedTarget.value = Number(goalRes.data.current_week_target);
    }

    uni.showToast({ title: "个人资料与未开始周/月计划已保存", icon: "success" });
  } catch (err: any) {
    uni.showToast({ title: err?.message || "保存失败", icon: "none" });
  } finally {
    saving.value = false;
  }
}

async function handleToggleDataConfidentiality(
  field: "hide_gps_route" | "hide_biometrics",
  val: boolean
) {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  if (!profile.value) profile.value = {};
  profile.value[field] = val;
  try {
    await request(`/api/profile/${uid}`, "PUT", {
      [field]: val,
    });
    uni.showToast({
      title: val ? "已设为仅对教练和师傅开放 🔒" : "已恢复对跑团公开 ✓",
      icon: "none",
    });
  } catch (err: any) {
    uni.showToast({ title: err?.message || "保存保密设置失败", icon: "none" });
  }
}

function handleConfirmPurgePrivacy() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  showPurgeConfirmModal.value = true;
}

async function executePurgePrivacy() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }

  purgingPrivacy.value = true;
  uni.showLoading({ title: "正在彻底清除隐私..." });
  try {
    const purgeRes = await request(`/api/profile/${uid}/purge-privacy`, "POST");
    uni.hideLoading();
    showPurgeConfirmModal.value = false;
    uni.showModal({
      title: "🛡️ 清除成功",
      content: purgeRes?.message || "所有个人隐私数据（真实姓名、身份证、生日、手机号及第三方手表账号凭证）已彻底安全清除！",
      showCancel: false,
      confirmText: "我知道了",
      success: () => {
        if (purgeRes?.anonymized_display_name) {
          if (user.value) user.value.display_name = purgeRes.anonymized_display_name;
          if (profile.value) {
            profile.value.display_name = purgeRes.anonymized_display_name;
            profile.value.real_name = "";
            profile.value.id_card = "";
            profile.value.phone = "";
            profile.value.date_of_birth = "";
            profile.value.garmin_connected = false;
            profile.value.coros_connected = false;
          }
        }
        loadProfileData();
      }
    });
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: err?.message || "清除失败，请重试", icon: "none" });
  } finally {
    purgingPrivacy.value = false;
  }
}

async function handleBindGarmin() {
  if (!inputEmail.value.trim() || !inputPassword.value.trim()) {
    uni.showToast({ title: "请输入账号和密码", icon: "none" });
    return;
  }
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  binding.value = true;
  try {
    const payload: any = {
      uid: uid,
      email: inputEmail.value.trim(),
      password: inputPassword.value.trim(),
      domain: inputDomain.value,
      inviter_uid: uni.getStorageSync("rgm_pending_inviter_uid") || undefined,
    };
    if (needsMfa.value && inputMfaCode.value.trim()) {
      payload.mfa_code = inputMfaCode.value.trim();
    }

    const res = await request(`/api/auth/garmin/bind`, "POST", payload);

    if (res?.needs_mfa) {
      needsMfa.value = true;
      uni.showToast({ title: "请输入邮箱中的验证码", icon: "none" });
      return;
    }

    // If backend linked this Garmin email to an existing profile (e.g. Zhong Wan returning)
    if (res?.uid && user.value && res.uid !== user.value.id) {
      user.value.id = res.uid;
      user.value.garmin_connected = true;
      user.value.garmin_email = inputEmail.value.trim();
      uni.setStorageSync("rgm_user", user.value);
      if (res?.token) {
        uni.setStorageSync("rgm_token", res.token);
      }
    }
    showGarminModal.value = false;
    trackFunnelStep("bind_garmin_success", "成功绑定佳明手表", { domain: inputDomain.value });
    needsMfa.value = false;
    inputMfaCode.value = "";
    inputPassword.value = "";
    await loadProfileData();
    uni.showModal({
      title: "⌚ 佳明绑定成功 · 佩戴提醒",
      content: "为确保小程序获取夜间 HRV、晨起静息心率与睡眠恢复等必要数据，请保持 24 小时全天（含夜间睡眠）佩戴手表！若夜间不佩戴导致恢复数据缺失，系统与教练将无法给出正确的训练建议。",
      showCancel: false,
      confirmText: "我知道了",
    });
  } catch (err: any) {
    uni.showModal({
      title: "绑定提示",
      content: err.message || "绑定失败，请检查账号密码及所属区域",
      showCancel: false,
    });
  } finally {
    binding.value = false;
  }
}

async function handleUnbindGarmin() {
  const uid = user.value?.id;
  if (!uid) return;
  unbinding.value = true;
  try {
    await request(`/api/auth/garmin/unbind`, "POST", { uid: uid });
    uni.showToast({ title: "已解除佳明绑定", icon: "success" });
    await loadProfileData();
  } catch (err: any) {
    uni.showToast({ title: "解除失败", icon: "none" });
  } finally {
    unbinding.value = false;
  }
}

function openDeviceModal(brand: "garmin" | "coros" | "apple_watch" | "huawei" | "suunto" = "garmin") {
  const brandNames: Record<string, string> = {
    garmin: "佳明 Garmin",
    coros: "高驰 COROS",
    apple_watch: "Apple Watch",
    huawei: "华为运动健康",
    suunto: "颂拓 Suunto",
  };
  trackModal("device_bind", `打开设备绑定弹窗：${brandNames[brand] || brand}`, "open", { brand });
  selectedBrand.value = brand;
  needsMfa.value = false;
  inputMfaCode.value = "";
  needsCoros2fa.value = false;
  inputCoros2faCode.value = "";
  if (brand === "coros") {
    if (corosAccount.value) {
      inputCorosAccount.value = corosAccount.value;
    }
    inputCorosPassword.value = "";
    if (corosDomain.value) {
      inputCorosDomain.value = corosDomain.value;
    }
  } else if (brand === "huawei") {
    if (huaweiAccount.value) {
      inputHuaweiAccount.value = huaweiAccount.value;
    }
  } else if (brand === "suunto") {
    if (suuntoAccount.value) {
      inputSuuntoAccount.value = suuntoAccount.value;
    }
  }
  showGarminModal.value = true;
}

async function handleBindHealthWatch(brand: "apple_watch" | "huawei" | "suunto") {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  bindingHealthWatch.value = true;
  try {
    const acc =
      brand === "huawei"
        ? (inputHuaweiAccount.value.trim() || "华为运动健康")
        : brand === "suunto"
        ? (inputSuuntoAccount.value.trim() || "Suunto App")
        : "Apple Health";
    const res = await bindHealthWatch(uid, brand, acc);
    uni.showToast({
      title:
        res?.message ||
        (brand === "apple_watch"
          ? "Apple Watch 已连接 ✓"
          : brand === "suunto"
          ? "颂拓手表已绑定 ✓"
          : "华为手表已绑定 ✓"),
      icon: "success",
    });
    showGarminModal.value = false;
    trackFunnelStep("bind_health_watch_success", "成功连接健康手表", { brand });
    await loadProfileData();
    uni.showModal({
      title: "⌚ 手表连接成功 · 佩戴提醒",
      content: "为确保小程序获取夜间 HRV、晨起静息心率与睡眠恢复等必要数据，请保持 24 小时全天（含夜间睡眠）佩戴手表！若夜间不佩戴导致恢复数据缺失，系统与教练将无法给出正确的训练建议。",
      showCancel: false,
      confirmText: "我知道了",
    });
  } catch (err: any) {
    uni.showModal({
      title: "绑定提示",
      content: err?.message || "连接失败，请稍后重试",
      showCancel: false,
    });
  } finally {
    bindingHealthWatch.value = false;
  }
}

async function handleUnbindHealthWatch(brand: "apple_watch" | "huawei" | "suunto") {
  const uid = user.value?.id;
  if (!uid) return;
  unbindingAppleWatch.value = true;
  unbindingHuawei.value = true;
  unbindingSuunto.value = true;
  try {
    const tasks: Promise<any>[] = [];
    if (appleWatchConnected.value) tasks.push(unbindHealthWatch(uid, "apple_watch"));
    if (huaweiConnected.value) tasks.push(unbindHealthWatch(uid, "huawei"));
    if (suuntoConnected.value) tasks.push(unbindHealthWatch(uid, "suunto"));
    if (tasks.length === 0) tasks.push(unbindHealthWatch(uid, brand));
    await Promise.all(tasks);
    uni.showToast({
      title: "已解除手表绑定",
      icon: "success",
    });
    await loadProfileData();
  } catch (err: any) {
    uni.showToast({ title: "解除失败", icon: "none" });
  } finally {
    unbindingAppleWatch.value = false;
    unbindingHuawei.value = false;
    unbindingSuunto.value = false;
  }
}

async function handleImportWatchTrack(brand: "apple_watch" | "huawei" | "suunto", closeModalAfter: boolean = false) {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  importingTrackBrand.value = brand;
  try {
    const res = await chooseAndImportTrackFile(uid, brand);
    if (res?.success) {
      trackFunnelStep("import_track_file_success", "成功导入运动轨迹文件", { brand });
      if (closeModalAfter) {
        showGarminModal.value = false;
      }
      await loadProfileData();
      const act = res.activity;
      const summary = act
        ? `${res.message}\n\n配速：${act.avg_pace_str || "—"} /km\n用时：${Math.round((act.duration_sec || 0) / 60)} 分钟\n平均心率：${act.avg_hr || "—"} bpm`
        : (res.message || "轨迹导入成功！");
      uni.showModal({
        title: "🎉 轨迹导入成功",
        content: summary,
        showCancel: false,
        confirmText: "太棒了",
      });
    }
  } catch (err: any) {
    if (err?.message === "CANCEL" || err?.message === "__CANCEL__") return;
    uni.showModal({
      title: "轨迹导入提示",
      content: err?.message || "请先将 FIT、GPX 或 TCX 轨迹文件发送到微信聊天（如「文件传输助手」），再点击导入选择该文件。",
      showCancel: false,
    });
  } finally {
    importingTrackBrand.value = "";
  }
}

async function handleImportWatchScreenshot(brand: "apple_watch" | "huawei" | "suunto", closeModalAfter: boolean = false) {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  importingScreenshotBrand.value = brand;
  try {
    const res = await chooseAndImportScreenshot(uid, brand);
    if (res?.success) {
      trackFunnelStep("import_screenshot_success", "成功导入运动截图", { brand, count: (res.records || []).length });
      if (closeModalAfter) {
        showGarminModal.value = false;
      }
      await loadProfileData();
      const recs: any[] = res.records || [];
      const previewLines = recs
        .slice(0, 6)
        .map((r: any) => `• ${r.date}：${r.distance_km} km${r.avg_hr ? ` · ${r.avg_hr}bpm` : ""}`)
        .join("\n");
      const moreLine = recs.length > 6 ? `\n…等共 ${recs.length} 条记录` : "";
      const summary = previewLines
        ? `${res.message}\n\n${previewLines}${moreLine}`
        : (res.message || "截图识别导入成功！");
      uni.showModal({
        title: "🎉 运动截图导入成功",
        content: summary,
        showCancel: false,
        confirmText: "太棒了",
      });
    }
  } catch (err: any) {
    if (err?.message === "CANCEL" || err?.message === "__CANCEL__") return;
    uni.showModal({
      title: "运动截图导入提示",
      content:
        err?.message ||
        "请上传清晰的运动截图（支持「苹果健康 → 步行+跑步距离 → 所有已记录的数据」列表截图，或「华为运动健康」单次跑步详情截图）。",
      showCancel: false,
    });
  } finally {
    importingScreenshotBrand.value = "";
  }
}

async function handleBindCoros() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  const acc = inputCorosAccount.value.trim();
  const pwd = inputCorosPassword.value.trim();
  const canReuseSavedPwd =
    corosConnected.value &&
    corosHasSavedPassword.value &&
    !!corosAccount.value &&
    acc.toLowerCase() === corosAccount.value.trim().toLowerCase();
  if (!acc || (!pwd && !canReuseSavedPwd)) {
    uni.showToast({ title: "请输入高驰账号与密码", icon: "none" });
    return;
  }
  if (needsCoros2fa.value && !inputCoros2faCode.value.trim()) {
    uni.showToast({ title: "请输入 6 位短信验证码", icon: "none" });
    return;
  }

  bindingCoros.value = true;
  try {
    const payload: any = {
      uid: uid,
      account: acc,
      password: pwd,
      domain: inputCorosDomain.value,
    };
    if (needsCoros2fa.value && inputCoros2faCode.value.trim()) {
      payload.code = inputCoros2faCode.value.trim();
    }

    const res = await bindCoros(payload);

    if (res?.needs_2fa) {
      needsCoros2fa.value = true;
      trackFunnelStep("bind_coros_2fa_prompt", "高驰绑定触发短信两步验证");
      uni.showToast({ title: "已向手机发送验证码", icon: "none" });
      return;
    }

    trackFunnelStep("bind_coros_success", "成功绑定高驰手表", { domain: inputCorosDomain.value });

    if (res?.uid && user.value && res.uid !== user.value.id) {
      user.value.id = res.uid;
      user.value.coros_connected = true;
      user.value.coros_account = acc;
      uni.setStorageSync("rgm_user", user.value);
      if (res?.token) {
        uni.setStorageSync("rgm_token", res.token);
      }
    }
    showGarminModal.value = false;
    needsCoros2fa.value = false;
    inputCoros2faCode.value = "";
    inputCorosPassword.value = "";
    await loadProfileData();
    uni.showModal({
      title: "⌚ 高驰绑定成功 · 佩戴提醒",
      content: "为确保小程序获取夜间 HRV、晨起静息心率与睡眠恢复等必要数据，请保持 24 小时全天（含夜间睡眠）佩戴手表！若夜间不佩戴导致恢复数据缺失，系统与教练将无法给出正确的训练建议。",
      showCancel: false,
      confirmText: "我知道了",
    });
  } catch (err: any) {
    uni.showModal({
      title: "高驰绑定提示",
      content: err?.message || "绑定失败，请检查账号密码及所属区域",
      showCancel: false,
    });
  } finally {
    bindingCoros.value = false;
  }
}

async function handleUnbindCoros() {
  const uid = user.value?.id;
  if (!uid) return;
  unbindingCoros.value = true;
  try {
    await unbindCoros(uid);
    uni.showToast({ title: "已解除高驰绑定", icon: "success" });
    await loadProfileData();
  } catch (err: any) {
    uni.showToast({ title: "解除失败", icon: "none" });
  } finally {
    unbindingCoros.value = false;
  }
}

async function handleImportGarminPb() {
  const uid = user.value?.id;
  if (!uid) return;
  importingGarmin.value = true;
  try {
    const res = await request(`/api/profile/${uid}/import-garmin-pb`, "POST");
    if (res?.profile) {
      profile.value.marathon_pb = res.profile.marathon_pb;
      profile.value.half_pb = res.profile.half_pb;
      profile.value.ten_k_pb = res.profile.ten_k_pb;
      profile.value.five_k_pb = res.profile.five_k_pb;
    }
    uni.showToast({ title: "PB 导入成功", icon: "success" });
  } catch (err: any) {
    uni.showToast({ title: err.message || "导入失败", icon: "none" });
  } finally {
    importingGarmin.value = false;
  }
}

onShow(() => {
  applySystemTheme(currentTheme.value);
  syncTabBarIndex(4);
  const autoBrand = uni.getStorageSync("auto_open_device_brand");
  if (autoBrand) {
    uni.removeStorageSync("auto_open_device_brand");
  }
  const profilePromise = loadProfileData();
  if (uni.getStorageSync("auto_open_edit_profile")) {
    uni.removeStorageSync("auto_open_edit_profile");
    activeSection.value = "";
    Promise.resolve(profilePromise).finally(() => {
      openEditProfileModal();
    });
  } else if (uni.getStorageSync("auto_open_support")) {
    uni.removeStorageSync("auto_open_support");
    activeSection.value = "support";
    setTimeout(() => {
      loadMySupportTickets();
    }, 300);
  } else if (uni.getStorageSync("auto_scroll_to_required_fields")) {
    uni.removeStorageSync("auto_scroll_to_required_fields");
    activeSection.value = "personal";
    setTimeout(() => {
      scrollToRequiredFields();
    }, 450);
  } else if (uni.getStorageSync("auto_scroll_to_device") || autoBrand) {
    uni.removeStorageSync("auto_scroll_to_device");
    scrollToDeviceCard();
    if (autoBrand) {
      Promise.resolve(profilePromise).finally(() => {
        openDeviceModal(autoBrand as any);
      });
    }
  }
});

// ── 从各页面"去绑定手表"跳转过来时，定位并高亮手表直连卡片 ──
const isDeviceCardHighlighted = ref(false);
function scrollToDeviceCard() {
  activeSection.value = "device";
  setTimeout(() => {
    uni.pageScrollTo({ selector: "#device-connect-card", duration: 400 });
    isDeviceCardHighlighted.value = true;
    setTimeout(() => {
      isDeviceCardHighlighted.value = false;
    }, 2600);
  }, 450);
}
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
/* 顶部快捷入口宫格 */
.quick-grid {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  padding: 24rpx 12rpx;
  margin-bottom: 24rpx;
  border-radius: 24rpx;
  background: var(--rgm-card, #141418);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.qg-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10rpx;
}
.qg-item:active {
  opacity: 0.7;
}
.qg-icon-wrap {
  position: relative;
  width: 84rpx;
  height: 84rpx;
  border-radius: 24rpx;
  background: var(--rgm-brand-tint, rgba(255, 107, 0, 0.12));
  display: flex;
  align-items: center;
  justify-content: center;
}
.qg-icon {
  font-size: 40rpx;
}
.qg-dot {
  position: absolute;
  top: 6rpx;
  right: 6rpx;
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
  background: #ef4444;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}
.qg-label {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d4d4d8);
}

/* 渐进式资料折叠入口 */
.extra-fields-toggle {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}
.eft-meta {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  flex: 1;
  min-width: 0;
}
.eft-title {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--rgm-text, #f4f4f5);
}
.eft-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}
.eft-arrow {
  font-size: 24rpx;
  color: var(--rgm-brand-text, #ff8533);
  flex-shrink: 0;
}

/* ── Pulse Animation for Required Fields Focus ── */
.highlight-pulse {
  animation: fieldPulse 1.2s ease-in-out 2 !important;
}

@keyframes fieldPulse {
  0%, 100% {
    box-shadow: 0 0 0 rgba(245, 158, 11, 0);
    border-color: rgba(255, 255, 255, 0.08);
  }
  50% {
    box-shadow: 0 0 35rpx rgba(245, 158, 11, 0.65);
    border-color: #f59e0b !important;
  }
}

/* ── 🚀 Onboard Guide Card ── */
.onboard-guide-card {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(168, 85, 247, 0.15) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 24rpx;
  padding: 22rpx 26rpx;
  margin-bottom: 24rpx;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 6rpx 20rpx var(--rgm-shadow, rgba(0, 0, 0, 0.25));
}

.ogc-left {
  display: flex;
  align-items: center;
  gap: 18rpx;
  flex: 1;
}

.ogc-icon-circle {
  width: 68rpx;
  height: 68rpx;
  border-radius: 18rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34rpx;
  flex-shrink: 0;
}

.ogc-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.ogc-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.ogc-title {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.ogc-progress-tag {
  font-size: 18rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #f97316);
  background: var(--rgm-brand-tint, rgba(249, 115, 22, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(249, 115, 22, 0.3));
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.ogc-progress-tag.completed {
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.3);
}

.ogc-desc {
  font-size: 20rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.4;
}

.ogc-right {
  margin-left: 16rpx;
  flex-shrink: 0;
}

.ogc-action-txt {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  padding: 8rpx 18rpx;
  border-radius: 16rpx;
}

/* ── Manual Entry Banner ── */
.manual-entry-banner {
  background: var(--rgm-brand-tint, linear-gradient(90deg, rgba(252, 76, 2, 0.12) 0%, rgba(255, 255, 255, 0.03) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.28));
  border-radius: 24rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.manual-entry-left {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16rpx;
  flex: 1;
}

.manual-entry-icon {
  font-size: 36rpx;
}

.manual-entry-meta {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.manual-entry-title {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.manual-entry-desc {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a0a0a5);
}

.manual-entry-arrow {
  font-size: 32rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.share-entry-banner {
  background: linear-gradient(90deg, rgba(52, 199, 89, 0.14) 0%, rgba(255, 255, 255, 0.03) 100%);
  border: 1rpx solid rgba(52, 199, 89, 0.35);
}

.share-banner-actions {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12rpx;
}

.share-badge-btn {
  font-size: 22rpx;
  color: var(--rgm-text, #ffffff);
  background: var(--rgm-brand, #10b981);
  border-radius: 9999rpx;
  padding: 4rpx 16rpx;
  height: 48rpx;
  line-height: 48rpx;
  border: none;
  font-weight: 600;
  margin: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.share-badge-btn::after {
  border: none;
}

.share-badge-pill {
  font-size: 24rpx;
  color: var(--rgm-green, #34c759);
  font-weight: 600;
  background: rgba(52, 199, 89, 0.15);
  border: 1rpx solid rgba(52, 199, 89, 0.3);
  border-radius: 9999rpx;
  padding: 6rpx 18rpx;
  white-space: nowrap;
}

/* ── 「我的」功能菜单 ── */
.profile-menu-card {
  padding: 8rpx 28rpx;
}

.pm-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  padding: 28rpx 0;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  gap: 20rpx;
}

.pm-item-last {
  border-bottom: none;
}

.pm-icon {
  font-size: 40rpx;
  width: 56rpx;
  text-align: center;
}

.pm-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  min-width: 0;
}

.pm-title {
  font-size: 29rpx;
  font-weight: 600;
  color: var(--rgm-text, #ffffff);
}


.pm-status {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  white-space: nowrap;
}

.pm-status.ok {
  color: var(--rgm-green, #34c759);
}

.pm-status.warn {
  color: var(--rgm-red, #f87171);
}

.pm-arrow {
  font-size: 36rpx;
  color: var(--rgm-text-3, #48484a);
}

.appearance-card .pm-item {
  padding: 22rpx 0;
}

.app-seg-group {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6rpx;
  padding: 6rpx;
  border-radius: 18rpx;
  background: var(--rgm-card-3, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  flex-shrink: 0;
}

.app-seg-pill {
  padding: 10rpx 20rpx;
  border-radius: 13rpx;
  font-size: 24rpx;
  font-weight: 600;
  line-height: 1.2;
  color: var(--rgm-text-2, #a1a1aa);
  white-space: nowrap;
  transition: all 0.15s ease;
}

.app-seg-pill.active {
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-on-brand, #ffffff);
  font-weight: 700;
  box-shadow: 0 4rpx 12rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.28));
}

/* ── 子页面返回栏 ── */
.section-back-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  margin: -30rpx -30rpx 24rpx -30rpx;
  padding: 24rpx 30rpx;
  background: var(--rgm-bg, rgba(11, 11, 13, 0.96));
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.sbb-back {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 6rpx;
  width: 140rpx;
}

.sbb-arrow {
  font-size: 44rpx;
  line-height: 1;
  color: var(--rgm-brand-text, #fc4c02);
}

.sbb-back-txt {
  font-size: 28rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 600;
}

.sbb-title {
  font-size: 30rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.sbb-placeholder {
  width: 140rpx;
}

/* ── Segmented Profile Tabs Nav ── */
.profile-tabs-nav {
  display: flex;
  flex-direction: row;
  align-items: center;
  background: var(--rgm-card, #151518);
  border-radius: 24rpx;
  padding: 8rpx;
  margin-bottom: 28rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.profile-tab-item {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  padding: 20rpx 0;
  border-radius: 18rpx;
  transition: all 0.2s ease;
  gap: 12rpx;
}

.profile-tab-item-active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));
}

.profile-tab-icon {
  font-size: 30rpx;
}

.profile-tab-title {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
}

.profile-tab-title-active {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 700;
}

.profile-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  padding: 24rpx 28rpx calc(130rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(130rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* Required field asterisk */
.required-star {
  color: var(--rgm-red, #f87171);
  font-size: inherit;
  font-weight: bold;
}

.login-hero-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(7, 193, 96, 0.22) 0%, #151518 100%));
  border: 1rpx solid rgba(7, 193, 96, 0.45);
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.22));
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.login-hero-left {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.hero-icon-circle {
  width: 80rpx;
  height: 80rpx;
  border-radius: 40rpx;
  background-color: rgba(7, 193, 96, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero-wx-icon {
  font-size: 38rpx;
}

.hero-text-wrap {
  flex: 1;
}

.hero-title {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.hero-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a0a0a5);
  margin-top: 6rpx;
  display: block;
  line-height: 1.4;
}

.hero-login-btn,
.hero-login-btn-native {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background-color: var(--rgm-brand, #07c160);
  color: var(--rgm-text, #ffffff);
  font-size: 30rpx;
  font-weight: bold;
  border-radius: 20rpx;
  border: none;
  text-align: center;
  margin-top: 4rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.hero-login-btn-text,
.modal-wx-btn-text {
  color: var(--rgm-text, #ffffff);
  font-size: 30rpx;
  font-weight: bold;
}

.switch-user-btn {
  padding: 0 20rpx;
  background-color: var(--rgm-card-3, #242429);
  color: var(--rgm-text-3, #8e8e93);
  font-size: 24rpx;
  border-radius: 16rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  height: 56rpx;
  line-height: 56rpx;
  margin: 0;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.user-card {
  background: var(--rgm-card, linear-gradient(135deg, #1c1c20 0%, #131316 100%));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.22));
  display: flex;
  align-items: center;
  gap: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.avatar {
  width: 100rpx;
  height: 100rpx;
  border-radius: 50rpx;
  border: 2rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
}

.user-meta {
  flex: 1;
}

.user-name {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.user-id {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 6rpx;
  display: block;
}

.wechat-quick-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(7, 193, 96, 0.15) 0%, #151518 100%));
  border: 1rpx solid rgba(7, 193, 96, 0.3);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.wx-tip-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.wx-icon {
  font-size: 36rpx;
}

.wx-tip-text {
  flex: 1;
}

.wx-tip-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.wx-tip-sub {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
  display: block;
}

.wx-login-action-btn {
  background: var(--rgm-brand, #07c160);
  color: var(--rgm-text, #ffffff);
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 80rpx;
  line-height: 80rpx;
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.section-card {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.22));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.title-icon {
  font-size: 28rpx;
}

.card-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.conn-status {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text-3, #8e8e93);
}

.conn-status.connected {
  color: var(--rgm-green, #30d158);
}

/* ── Wechat Notification Card ── */
.wechat-notif-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(252, 82, 0, 0.08) 0%, #151518 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 82, 0, 0.25));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.notif-status-badge {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.06));
}

.notif-status-badge.enabled {
  background-color: rgba(48, 209, 88, 0.15);
}

.notif-status-badge .status-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 6rpx;
  background-color: #8e8e93;
}

.notif-status-badge.enabled .status-dot {
  background-color: #30d158;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.notif-status-badge .status-text {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  font-weight: bold;
}

.notif-status-badge.enabled .status-text {
  color: var(--rgm-green, #30d158);
}

.wechat-notif-desc {
  font-size: 24rpx;
  color: var(--rgm-text-2, #a0a0a5);
  line-height: 1.5;
  display: block;
  margin-bottom: 20rpx;
}

.wechat-notif-actions {
  display: flex;
  gap: 16rpx;
}

.enable-subscribe-btn {
  flex: 2;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc5200 0%, #e04800 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  height: 72rpx;
  line-height: 72rpx;
  border-radius: 18rpx;
  border: none;
  text-align: center;
  margin: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.test-subscribe-btn {
  flex: 1;
  background-color: var(--rgm-card-3, #242429);
  color: var(--rgm-brand-text, #fc5200);
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 82, 0, 0.4));
  font-size: 24rpx;
  font-weight: bold;
  height: 72rpx;
  line-height: 72rpx;
  border-radius: 18rpx;
  text-align: center;
  margin: 0;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.desc-text {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.4;
  margin-bottom: 20rpx;
  display: block;
}

.garmin-btn {
  background-color: var(--rgm-brand, #0a84ff);
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.unbind-btn {
  background-color: rgba(255, 69, 58, 0.15);
  color: var(--rgm-red, #ff453a);
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
}

/* Club Management Card */
.club-card-highlight {
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  background: var(--rgm-card, linear-gradient(135deg, rgba(252, 76, 2, 0.08) 0%, #151518 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.club-role-tag {
  font-size: 22rpx;
  font-weight: bold;
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
}

.role-owner {
  background-color: rgba(255, 159, 10, 0.25);
  color: var(--rgm-amber, #ff9f0a);
}

.role-coach {
  background-color: var(--rgm-brand-tint, rgba(191, 90, 242, 0.25));
  color: var(--rgm-brand-text, #bf5af2);
}

.role-member {
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-3, #8e8e93);
}

.joined-club-box {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.club-mini-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.mini-logo {
  width: 80rpx;
  height: 80rpx;
  border-radius: 18rpx;
  flex-shrink: 0;
}

.mini-texts {
  flex: 1;
  min-width: 0;
}

.club-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 6rpx;
  flex-wrap: wrap;
}

.multi-club-badge {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.mini-club-name,
.club-title-text {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.mini-club-desc,
.club-desc-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #8e8e93);
  margin-top: 6rpx;
  display: block;
  line-height: 1.45;
}

.invite-copy-row {
  display: flex;
  align-items: center;
  font-size: 24rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  padding-top: 14rpx;
}

.invite-lbl {
  color: var(--rgm-text-3, #8e8e93);
}

.invite-code {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
  font-family: monospace;
  font-size: 26rpx;
  margin-left: 6rpx;
}

.copy-action {
  color: var(--rgm-blue, #0a84ff);
  font-size: 22rpx;
  margin-left: 8rpx;
}

.empty-club-box {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.club-btn-grid {
  display: flex;
  gap: 14rpx;
}

.club-act-btn {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 0 10rpx;
  height: 76rpx;
  line-height: 1.25;
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  box-sizing: border-box;
}

.club-act-btn::after {
  border: none;
}

.club-act-btn.join-btn {
  background-color: var(--rgm-card-3, #242429);
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.club-act-btn.create-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%));
  color: var(--rgm-text, #ffffff);
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.club-act-btn.self-create-btn {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  color: var(--rgm-brand-text, #fc4c02);
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
}

/* Races */
.add-race-header-btn {
  margin: 0;
  padding: 0 20rpx;
  height: 52rpx;
  line-height: 52rpx;
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%));
  border-radius: 14rpx;
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.add-race-header-btn::after {
  border: none;
}

.add-race-empty-btn {
  margin-top: 16rpx;
  width: 100%;
  height: 72rpx;
  line-height: 72rpx;
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  border-radius: 16rpx;
}

.add-race-empty-btn::after {
  border: none;
}

.race-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.race-item {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.race-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.race-top-right {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.race-quick-actions {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.race-action-pill {
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.edit-pill {
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
}

.del-pill {
  background-color: rgba(255, 69, 58, 0.1);
  border: 1rpx solid rgba(255, 69, 58, 0.25);
}

.pill-text {
  font-size: 18rpx;
  color: var(--rgm-text, #e4e4e7);
  font-weight: 500;
}

.del-pill .pill-text {
  color: var(--rgm-red, #ff453a);
}

.race-name {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.race-badge {
  background-color: rgba(10, 132, 255, 0.15);
  color: var(--rgm-blue, #0a84ff);
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
  font-size: 20rpx;
  font-weight: bold;
}

.race-badge.urgent {
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  color: var(--rgm-brand-text, #fc4c02);
}

.race-badge.completed-badge {
  background-color: rgba(52, 199, 89, 0.2);
  color: var(--rgm-green, #34c759);
  border: 1rpx solid rgba(52, 199, 89, 0.35);
}

.race-finish-time-tag {
  color: var(--rgm-blue, #38bdf8);
  font-weight: bold;
}

.race-completed-card-banner {
  margin-top: 14rpx;
  padding: 14rpx 16rpx;
  background-color: rgba(52, 199, 89, 0.08);
  border: 1rpx solid rgba(52, 199, 89, 0.2);
  border-radius: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.completed-summary-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}

.comp-badge-tag {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-green, #34c759);
  background-color: rgba(52, 199, 89, 0.15);
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
}

.comp-diff-text {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-amber, #fbbf24);
}

.comp-notes-text {
  font-size: 20rpx;
  color: var(--rgm-text-2, #d4d4d8);
  font-style: italic;
}

.card-photos-scroll {
  display: flex;
  gap: 12rpx;
  overflow-x: auto;
  padding-top: 4rpx;
}

.card-photo-thumb {
  width: 100rpx;
  height: 100rpx;
  border-radius: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  flex-shrink: 0;
}

.card-add-photo-btn {
  width: 100rpx;
  height: 100rpx;
  border-radius: 12rpx;
  border: 2rpx dashed var(--rgm-brand-line, rgba(255, 107, 0, 0.5));
  background: var(--rgm-brand-tint, rgba(255, 107, 0, 0.08));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
}

.card-add-photo-btn:active {
  background: var(--rgm-brand-tint, rgba(255, 107, 0, 0.2));
}

.card-add-photo-btn .card-add-icon {
  font-size: 28rpx;
  line-height: 1;
}

.card-add-photo-btn .card-add-txt {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #ff6b00);
  font-weight: 600;
  margin-top: 4rpx;
  line-height: 1;
}

.card-photo-hint {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
  margin-top: 6rpx;
  display: block;
}

.race-past-tip {
  margin-top: 10rpx;
  padding: 8rpx 14rpx;
  background-color: rgba(251, 191, 36, 0.1);
  border: 1rpx solid rgba(251, 191, 36, 0.2);
  border-radius: 10rpx;
}

.past-tip-text {
  font-size: 20rpx;
  color: var(--rgm-amber, #fbbf24);
  font-weight: 500;
}

/* Status Segmented in Modal */
.status-segmented {
  display: flex;
  background-color: var(--rgm-card-3, #242429);
  border-radius: 14rpx;
  padding: 6rpx;
  gap: 8rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.status-seg-item {
  flex: 1;
  text-align: center;
  font-size: 22rpx;
  font-weight: 600;
  padding: 14rpx 0;
  border-radius: 10rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.status-seg-item.active {
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text, #ffffff);
}

.status-seg-item.completed-item.active {
  background: linear-gradient(135deg, rgba(52, 199, 89, 0.3) 0%, rgba(52, 199, 89, 0.5) 100%);
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid rgba(52, 199, 89, 0.4);
}

/* Modal Completion Section */
.m-completion-section {
  background-color: rgba(52, 199, 89, 0.05);
  border: 1rpx solid rgba(52, 199, 89, 0.2);
  border-radius: 18rpx;
  padding: 18rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.m-completion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.comp-sec-title {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-green, #34c759);
}

.m-auto-match-btn {
  margin: 0;
  padding: 0 16rpx;
  height: 48rpx;
  line-height: 48rpx;
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  border-radius: 10rpx;
}

.m-auto-match-btn::after {
  border: none;
}

.finish-time-lbl-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.finish-time-diff-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
}

.finish-time-diff-badge.faster {
  color: var(--rgm-green, #34c759);
  background-color: rgba(52, 199, 89, 0.15);
}

.finish-time-diff-badge.slower {
  color: var(--rgm-blue, #38bdf8);
  background-color: rgba(56, 189, 248, 0.15);
}

.m-photo-lbl-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.m-upload-photo-btn {
  margin: 0;
  padding: 0 18rpx;
  height: 46rpx;
  line-height: 46rpx;
  font-size: 20rpx;
  font-weight: 500;
  color: var(--rgm-text, #e4e4e7);
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  border-radius: 10rpx;
}

.m-upload-photo-btn::after {
  border: none;
}

.modal-photo-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-top: 8rpx;
}

.modal-photo-thumb-wrap {
  position: relative;
  width: 120rpx;
  height: 120rpx;
  border-radius: 14rpx;
  overflow: hidden;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.2));
}

.modal-photo-img {
  width: 100%;
  height: 100%;
}

.modal-photo-del {
  position: absolute;
  top: 4rpx;
  right: 4rpx;
  width: 32rpx;
  height: 32rpx;
  line-height: 30rpx;
  text-align: center;
  background-color: rgba(0, 0, 0, 0.7);
  color: #ff453a;
  border-radius: 50%;
  font-size: 20rpx;
  font-weight: bold;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.modal-photo-empty {
  padding: 20rpx;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.02));
  border: 1rpx dashed var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 14rpx;
  text-align: center;
}

.empty-photo-text {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}


.race-type-tag {
  color: var(--rgm-brand-text, #fc4c02);
}

.race-name-group {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.race-priority-tag {
  font-size: 18rpx;
  font-weight: bold;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.p-tag-a {
  background-color: rgba(244, 63, 94, 0.2);
  color: var(--rgm-red, #fb7185);
  border: 1rpx solid rgba(244, 63, 94, 0.35);
}

.p-tag-b {
  background-color: rgba(56, 189, 248, 0.2);
  color: var(--rgm-blue, #38bdf8);
  border: 1rpx solid rgba(56, 189, 248, 0.35);
}

.p-tag-c {
  background-color: rgba(161, 161, 170, 0.2);
  color: var(--rgm-text-2, #d4d4d8);
  border: 1rpx solid rgba(161, 161, 170, 0.35);
}

.race-priority-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 14rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
}

.race-priority-lbl {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.priority-actions {
  display: flex;
  gap: 8rpx;
}

.min-p-btn {
  margin: 0;
  padding: 2rpx 12rpx;
  height: 40rpx;
  line-height: 40rpx;
  font-size: 18rpx;
  color: var(--rgm-text-2, #a1a1aa);
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 8rpx;
}

.min-p-btn::after {
  border: none;
}

.min-p-btn.active:nth-child(1) {
  background-color: rgba(244, 63, 94, 0.25);
  color: var(--rgm-red, #fb7185);
  border-color: #f43f5e;
  font-weight: bold;
}

.min-p-btn.active:nth-child(2) {
  background-color: rgba(56, 189, 248, 0.25);
  color: var(--rgm-blue, #38bdf8);
  border-color: #38bdf8;
  font-weight: bold;
}

.min-p-btn.active:nth-child(3) {
  background-color: rgba(161, 161, 170, 0.25);
  color: var(--rgm-text, #e4e4e7);
  border-color: #a1a1aa;
  font-weight: bold;
}

/* ── Race Intelligence Panel ── */
.race-info-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16rpx;
  gap: 12rpx;
}

.race-info-toggle-trigger {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12rpx 16rpx;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border-radius: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.07));
}

.race-info-toggle-label {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.race-info-toggle-arrow {
  font-size: 20rpx;
  color: var(--rgm-text-3, #636366);
}

.race-ai-fetch-btn {
  margin: 0;
  padding: 0 16rpx;
  height: 60rpx;
  line-height: 60rpx;
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #c084fc);
  background-color: var(--rgm-brand-tint, rgba(168, 85, 247, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(168, 85, 247, 0.35));
  border-radius: 12rpx;
  white-space: nowrap;
}

.race-ai-fetch-btn::after {
  border: none;
}

.race-info-panel-hint {
  padding: 8rpx 12rpx;
  margin-bottom: 12rpx;
  background-color: var(--rgm-brand-tint, rgba(168, 85, 247, 0.08));
  border-radius: 8rpx;
}

.panel-hint-text {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #c084fc);
}

.race-info-panel {
  margin-top: 12rpx;
  padding: 18rpx 16rpx;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border-radius: 16rpx;

  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.07));
}

.race-info-section-title {
  display: block;
  font-size: 22rpx;
  font-weight: 600;
  color: var(--rgm-text-2, #a1a1aa);
  margin-bottom: 12rpx;
  letter-spacing: 0.5rpx;
}

.race-info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
  gap: 12rpx;
}

.race-info-label {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  flex: 0 0 auto;
  min-width: 180rpx;
}

.race-info-input {
  flex: 1;
  height: 56rpx;
  line-height: 56rpx;
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 10rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 0 16rpx;
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.race-info-picker {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56rpx;
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 10rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 0 16rpx;
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.picker-arrow-sm {
  color: var(--rgm-text-3, #636366);
  font-size: 20rpx;
  margin-left: 8rpx;
}

.race-info-save-btn {
  margin-top: 16rpx;
  width: 100%;
  height: 72rpx;
  line-height: 72rpx;
  font-size: 26rpx;
  font-weight: 600;
  color: var(--rgm-text, #ffffff);
  background: var(--rgm-brand-grad, linear-gradient(135deg, #1c7ed6 0%, #339af0 100%));
  border-radius: 16rpx;
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.race-info-save-btn::after {
  border: none;
}

/* ── Race Management Modal (Add/Edit) ── */
.race-modal-card {
  max-height: 86vh;
  display: flex;
  flex-direction: column;
}

.race-modal-scroll {
  max-height: 72vh;
  box-sizing: border-box;
}

.m-field-wrap {
  margin-bottom: 24rpx;
}

.m-field-lbl {
  display: block;
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-bottom: 10rpx;
  font-weight: 500;
}

.m-input-ai-row {
  display: flex;
  gap: 12rpx;
  align-items: center;
}

.m-input-txt {
  height: 72rpx;
  line-height: 72rpx;
  background-color: var(--rgm-card-2, #202026);
  border-radius: 16rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 0 20rpx;
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.m-ai-fill-btn {
  margin: 0;
  padding: 0 20rpx;
  height: 72rpx;
  line-height: 72rpx;
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #c084fc);
  background-color: var(--rgm-brand-tint, rgba(168, 85, 247, 0.18));
  border: 1rpx solid var(--rgm-brand-line, rgba(168, 85, 247, 0.4));
  border-radius: 16rpx;
  white-space: nowrap;
}

.m-ai-fill-btn::after {
  border: none;
}

.m-picker-box {
  height: 72rpx;
  background-color: var(--rgm-card-2, #202026);
  border-radius: 16rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 0 20rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.m-picker-txt {
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
}

.m-picker-arrow {
  font-size: 20rpx;
  color: var(--rgm-text-3, #636366);
}

.m-row-2 {
  display: flex;
  gap: 16rpx;
}

.flex-1 {
  flex: 1;
}

.priority-segmented {
  display: flex;
  background-color: var(--rgm-card-2, #202026);
  border-radius: 16rpx;
  padding: 6rpx;
  gap: 6rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.seg-item {
  flex: 1;
  text-align: center;
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  padding: 14rpx 0;
  border-radius: 12rpx;
  transition: all 0.2s;
}

.seg-item.active {
  background-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.m-race-info-block {
  margin: 10rpx 0 24rpx;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border-radius: 20rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  overflow: hidden;
}

.m-race-info-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18rpx 20rpx;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.04));
}

.m-info-title {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #c084fc);
}

.m-info-arrow {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.m-race-info-fields {
  padding: 20rpx;
}

.m-sublbl {
  display: block;
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
  margin-bottom: 8rpx;
}

.m-subinput {
  height: 60rpx;
  line-height: 60rpx;
  background-color: var(--rgm-card, #16161a);
  border-radius: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  padding: 0 16rpx;
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.m-subpicker {
  height: 60rpx;
  background-color: var(--rgm-card, #16161a);
  border-radius: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  padding: 0 16rpx;
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  display: flex;
  align-items: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.m-actions-row {
  display: flex;
  gap: 16rpx;
  margin-top: 30rpx;
}

.m-cancel-btn {
  flex: 1;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 26rpx;
  color: var(--rgm-text-3, #8e8e93);
  background-color: var(--rgm-card-3, #242429);
  border-radius: 20rpx;
  border: none;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.m-cancel-btn::after {
  border: none;
}

.m-save-btn {
  flex: 2;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%));
  border-radius: 20rpx;
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.m-save-btn::after {
  border: none;
}

.m-del-row {
  display: flex;
  justify-content: center;
  padding: 24rpx 0 8rpx;
}

.m-del-txt {
  font-size: 22rpx;
  color: var(--rgm-red, #ff453a);
}

/* PB Grid */


.pb-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}

.pb-item {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.pb-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  display: block;
}

.pb-val {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  font-family: monospace;
  margin-top: 6rpx;
  display: block;
}

.import-garmin-btn {
  font-size: 20rpx;
  font-weight: bold;
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text, #ffffff);
  padding: 0 16rpx;
  height: 48rpx;
  line-height: 48rpx;
  border-radius: 12rpx;
}

/* Physiological Parameters */
.form-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-bottom: 8rpx;
}

.form-input {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  height: 72rpx;
  line-height: 72rpx;
  padding: 0 16rpx;
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.full-width-group {
  grid-column: span 2;
}

.label-with-tag {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8rpx;
}

.age-badge-pill {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
}

.estimate-pill-btn {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
  padding: 2rpx 8rpx;
}

.picker-input-box {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  height: 72rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16rpx;
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.placeholder-text {
  color: var(--rgm-text-3, #636366);
}

.picker-arrow {
  font-size: 24rpx;
}

.gender-pill-group {
  display: flex;
  gap: 12rpx;
  height: 72rpx;
}

.gender-pill {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gender-pill.active {
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

/* 商学院项目选择 Pills */
.program-pill-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-top: 8rpx;
}

.program-pill {
  padding: 12rpx 20rpx;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  transition: all 0.2s;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.program-pill.active {
  background-color: var(--rgm-brand, #f59e0b);
  border-color: var(--rgm-brand, #f59e0b);
  color: #000000;
  font-weight: bold;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* 戈壁经历选择卡片 */
.gobi-type-selector {
  display: flex;
  gap: 16rpx;
  margin-top: 8rpx;
}

.gobi-type-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 18rpx;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gobi-type-btn.active {
  background-color: rgba(245, 158, 11, 0.15);
  border-color: rgba(245, 158, 11, 0.5);
}

.gobi-icon {
  font-size: 36rpx;
}

.gobi-info {
  display: flex;
  flex-direction: column;
}

.gobi-main-title {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.gobi-sub-title {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
}

/* 往届老戈友展开框 */
.gobi-vet-box {
  background-color: var(--rgm-card, #141416);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 20rpx;
  margin-top: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.vet-row {
  display: flex;
  align-items: center;
}

.vet-label {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  width: 140rpx;
  shrink: 0;
}

.vet-picker-flex {
  flex: 1;
}

.grp-pill-group {
  display: flex;
  gap: 12rpx;
  flex: 1;
}

.grp-pill {
  flex: 1;
  text-align: center;
  padding: 12rpx 0;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 14rpx;
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.grp-pill.active {
  background-color: var(--rgm-brand, #f59e0b);
  border-color: var(--rgm-brand, #f59e0b);
  color: #000000;
  font-weight: bold;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* 健康状况声明勾选卡片 */
.health-decl-box {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 20rpx;
  background-color: var(--rgm-card, #141416);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.health-decl-box.active {
  border-color: rgba(99, 102, 241, 0.4);
  background-color: rgba(99, 102, 241, 0.05);
}

.health-checkbox {
  width: 36rpx;
  height: 36rpx;
  border-radius: 8rpx;
  border: 2rpx solid var(--rgm-line, rgba(255, 255, 255, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 4rpx;
  flex-shrink: 0;
}

.health-decl-box.active .health-checkbox {
  background-color: #6366f1;
  border-color: #6366f1;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.check-mark {
  color: var(--rgm-text, #ffffff);
  font-size: 24rpx;
  font-weight: bold;
}

.health-decl-texts {
  display: flex;
  flex-direction: column;
}

.health-title {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 6rpx;
}

.health-desc {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.4;
}

/* Target & Goal Planning */
.target-badge {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.1));
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
}

.target-badge.locked {
  color: var(--rgm-blue, #06b6d4);
  background-color: rgba(6, 182, 212, 0.1);
}

.goal-mode-selector {
  display: flex;
  background-color: var(--rgm-card, #121214);
  border-radius: 18rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
  gap: 8rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.goal-mode-btn {
  flex: 1;
  text-align: center;
  padding: 14rpx 0;
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  border-radius: 14rpx;
  transition: all 0.2s ease;
}

.goal-mode-btn.active {
  background-color: var(--rgm-card-3, #242428);
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.slider-wrapper {
  margin-bottom: 20rpx;
}

.locked-tip {
  font-size: 20rpx;
  color: var(--rgm-blue, #06b6d4);
  margin-top: 10rpx;
  text-align: center;
  display: block;
}

.uniform-tip {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 10rpx;
  text-align: center;
  display: block;
}

.custom-months-section {
  background-color: var(--rgm-card, #121214);
  border-radius: 20rpx;
  padding: 20rpx;
  margin-top: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.custom-months-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.cm-title {
  font-size: 22rpx;
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

.sync-uniform-action {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #fc4c02);
}

.months-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
}

.month-cell {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 14rpx;
  padding: 10rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.month-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-bottom: 4rpx;
}

.month-input {
  width: 100%;
  text-align: center;
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

/* Weekly Plan Section */
.weekly-plan-section {
  background-color: var(--rgm-card, #121214);
  border-radius: 20rpx;
  padding: 24rpx 20rpx;
  margin-top: 24rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.weekly-target-badge {
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
  color: var(--rgm-green, #34d399);
  font-size: 22rpx;
  font-weight: bold;
  border-radius: 12rpx;
  padding: 4rpx 14rpx;
}

.weekly-desc-tip {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.5;
  margin: 10rpx 0 16rpx 0;
  display: block;
}

.weekly-quick-pills {
  display: flex;
  gap: 12rpx;
  flex-wrap: wrap;
  margin-bottom: 16rpx;
}

.weekly-pill {
  padding: 8rpx 20rpx;
  border-radius: 14rpx;
  background: var(--rgm-card-2, #1c1c20);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  font-size: 22rpx;
  font-weight: 600;
  color: var(--rgm-text-2, #a1a1aa);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.weekly-pill.active {
  background: var(--rgm-brand, #10b981);
  border-color: var(--rgm-brand, #10b981);
  color: var(--rgm-text, #ffffff);
  box-shadow: 0 4rpx 12rpx rgba(16, 185, 129, 0.4);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.weekly-save-action {
  margin-top: 20rpx;
  display: flex;
  justify-content: flex-end;
}

.save-weekly-btn {
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.4);
  color: var(--rgm-green, #34d399);
  font-size: 22rpx;
  font-weight: bold;
  border-radius: 14rpx;
  padding: 12rpx 28rpx;
  line-height: 1.4;
  margin: 0;
}

.save-box {
  margin-top: 36rpx;
  margin-bottom: 24rpx;
}

.save-box-bottom {
  margin-top: 36rpx;
  margin-bottom: calc(50rpx + env(safe-area-inset-bottom));
}

.save-btn {
  width: 100%;
  height: 92rpx;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 30rpx;
  font-weight: bold;
  border-radius: 22rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  box-shadow: 0 8rpx 24rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.3));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.logout-box {
  margin-top: 40rpx;
  margin-bottom: calc(50rpx + env(safe-area-inset-bottom));
}

.logout-btn {
  background-color: var(--rgm-card-2, #1c1c1e);
  color: var(--rgm-text-3, #8e8e93);
  font-size: 28rpx;
  border-radius: 24rpx;
  height: 88rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* Modals */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 100rpx;
  z-index: 99999 !important;
  box-sizing: border-box;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.garmin-fast-link {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24rpx 0 8rpx;
  text-align: center;
}

.garmin-link-txt {
  font-size: 24rpx;
  color: var(--rgm-blue, #0a84ff);
}

.modal-content {
  width: 670rpx;
  background-color: var(--rgm-card, #18181c);
  border-radius: 36rpx;
  padding: 44rpx 40rpx;
  box-sizing: border-box;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  margin-bottom: 60rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
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
  color: var(--rgm-text, #ffffff);
}

.close-btn {
  font-size: 36rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.auth-tabs {
  display: flex;
  background-color: var(--rgm-card, #121214);
  border-radius: 20rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.auth-tab {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  font-size: 26rpx;
  color: var(--rgm-text-3, #8e8e93);
  border-radius: 16rpx;
}

.auth-tab.active {
  background-color: var(--rgm-card-3, #2c2c2e);
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.auth-desc {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-bottom: 24rpx;
  line-height: 1.4;
  display: block;
}

.field-label {
  font-size: 24rpx;
  color: var(--rgm-text-2, #aeaeb2);
  margin-top: 16rpx;
  margin-bottom: 8rpx;
  display: block;
}

.large-input {
  width: 100%;
  height: 96rpx;
  background-color: var(--rgm-card-3, #242429);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 20rpx;
  padding: 0 28rpx;
  font-size: 30rpx;
  color: var(--rgm-text, #ffffff);
  box-sizing: border-box;
  margin-bottom: 12rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.center-input {
  text-align: center;
  font-size: 36rpx;
  font-family: monospace;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  letter-spacing: 6rpx;
}

.large-textarea {
  width: 100%;
  height: 150rpx;
  background-color: var(--rgm-card-3, #242429);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 20rpx;
  padding: 20rpx 28rpx;
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  box-sizing: border-box;
  margin-bottom: 12rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.placeholder-style {
  color: var(--rgm-text-3, #636366);
}

.domain-selector {
  display: flex;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.domain-btn {
  flex: 1;
  text-align: center;
  padding: 20rpx 0;
  font-size: 26rpx;
  border-radius: 20rpx;
  background-color: var(--rgm-card-3, #242429);
  color: var(--rgm-text-3, #8e8e93);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.domain-btn.active {
  background-color: var(--rgm-brand, #0a84ff);
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  border-color: var(--rgm-brand, #0a84ff);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* Multi-device & Brand Switcher Styling */
.device-brands-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  font-weight: 500;
}

.brand-switch-row {
  display: flex;
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 18rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.brand-switch-grid-4 {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12rpx;
  margin-bottom: 24rpx;
}

.brand-switch-btn {
  flex: 1;
  text-align: center;
  padding: 18rpx 12rpx;
  font-size: 25rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  transition: all 0.2s ease;
}

.brand-switch-btn.active {
  background-color: var(--rgm-card-3, #2c2c30);
  color: var(--rgm-text, #ffffff);
  box-shadow: 0 2rpx 8rpx var(--rgm-shadow, rgba(0, 0, 0, 0.4));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.brand-switch-btn.brand-garmin.active {
  background: rgba(0, 122, 195, 0.16);
  border-color: #007AC3;
  color: #007AC3;
}

.brand-switch-btn.brand-coros.active {
  background: rgba(230, 0, 18, 0.14);
  border-color: #E60012;
  color: #E60012;
}

.brand-switch-btn.brand-apple.active {
  background: rgba(16, 185, 129, 0.16);
  border-color: #10b981;
  color: #10b981;
}

.brand-switch-btn.brand-huawei.active {
  background: rgba(207, 10, 44, 0.16);
  border-color: #CF0A2C;
  color: #CF0A2C;
}

.brand-switch-btn.brand-suunto.active {
  background: rgba(245, 158, 11, 0.16);
  border-color: #f59e0b;
  color: #f59e0b;
}

.device-status-item {
  display: flex;
  flex-direction: column;
}

.device-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.device-name-wrap {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.device-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.garmin-badge {
  background: rgba(0, 122, 255, 0.15);
  color: var(--rgm-blue, #0a84ff);
  border: 1rpx solid rgba(0, 122, 255, 0.3);
}

.coros-badge {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  color: var(--rgm-brand-text, #fc4c02);
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
}

.apple-badge {
  background: rgba(16, 185, 129, 0.16);
  color: #10b981;
  border: 1rpx solid rgba(16, 185, 129, 0.35);
}

.huawei-badge {
  background: rgba(207, 10, 44, 0.16);
  color: #CF0A2C;
  border: 1rpx solid rgba(207, 10, 44, 0.35);
}

.suunto-badge {
  background: rgba(245, 158, 11, 0.16);
  color: #f59e0b;
  border: 1rpx solid rgba(245, 158, 11, 0.35);
}

.device-name-text {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.coros-btn {
  background-color: var(--rgm-brand, #fc4c02) !important;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.coros-primary-btn {
  background-color: var(--rgm-brand, #fc4c02) !important;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.apple-watch-btn,
.apple-primary-btn {
  background-color: #10b981 !important;
  color: #ffffff !important;
}

.huawei-watch-btn,
.huawei-primary-btn {
  background-color: #CF0A2C !important;
  color: #ffffff !important;
}

.suunto-watch-btn,
.suunto-primary-btn {
  background-color: #d97706 !important;
  color: #ffffff !important;
}

.track-import-outline-btn {
  background-color: var(--rgm-card-2, #1a1a1e);
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
  padding: 0 12rpx;
}

.track-import-outline-btn::after {
  border: none;
}

.track-import-outline-btn.apple-outline {
  color: #10b981;
  border: 1rpx solid rgba(16, 185, 129, 0.45);
}

.track-import-outline-btn.huawei-outline {
  color: #CF0A2C;
  border: 1rpx solid rgba(207, 10, 44, 0.45);
}

.track-import-outline-btn.suunto-outline {
  color: #f59e0b;
  border: 1rpx solid rgba(245, 158, 11, 0.45);
}

.watch-guide-pane {
  display: flex;
  flex-direction: column;
}

.watch-guide-card {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.watch-guide-card.apple-guide-card {
  border-color: rgba(16, 185, 129, 0.35);
}

.watch-guide-card.huawei-guide-card {
  border-color: rgba(207, 10, 44, 0.35);
}

.watch-guide-card.suunto-guide-card {
  border-color: rgba(245, 158, 11, 0.35);
}

.watch-guide-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
  margin-bottom: 10rpx;
}

.watch-guide-desc {
  font-size: 23rpx;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.5;
  display: block;
  margin-bottom: 16rpx;
}

.watch-step-list {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.watch-step-item {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d4d4d8);
  line-height: 1.45;
  display: block;
}

.apple-modal-outline {
  color: #10b981 !important;
  border-color: rgba(16, 185, 129, 0.4) !important;
}

.huawei-modal-outline {
  color: #CF0A2C !important;
  border-color: rgba(207, 10, 44, 0.4) !important;
}

.suunto-modal-outline {
  color: #f59e0b !important;
  border-color: rgba(245, 158, 11, 0.4) !important;
}

.large-primary-btn {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  background-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-size: 30rpx;
  font-weight: bold;
  border-radius: 24rpx;
  margin-top: 24rpx;
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.large-wx-btn {
  width: 100%;
  height: 96rpx;
  background-color: var(--rgm-brand, #07c160);
  border-radius: 24rpx;
  margin-top: 24rpx;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.bottom-wx-login-btn {
  width: 100%;
  height: 88rpx;
  background-color: rgba(7, 193, 96, 0.15);
  border: 1rpx solid #07c160;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bottom-btn-text {
  color: var(--rgm-green, #07c160);
  font-size: 28rpx;
  font-weight: bold;
}

.wx-brand-hero {
  text-align: center;
  padding: 10rpx 0 28rpx;
}

.wx-hero-icon {
  font-size: 64rpx;
  display: block;
  margin-bottom: 8rpx;
}

.wx-hero-logo {
  width: 112rpx;
  height: 112rpx;
  border-radius: 24rpx;
  background-color: #ffffff;
  display: block;
  margin: 0 auto 14rpx;
  box-shadow: 0 8rpx 24rpx rgba(252, 76, 2, 0.25);
}

.wx-hero-title {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.wx-hero-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 8rpx;
  display: block;
  line-height: 1.4;
}

.wx-account-status-card {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.status-title {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-bottom: 12rpx;
  display: block;
}

.status-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8rpx;
  font-size: 24rpx;
}

.status-label {
  color: var(--rgm-text-3, #636366);
}

.status-val {
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

.text-green {
  color: var(--rgm-green, #07c160) !important;
}

.text-muted {
  color: var(--rgm-text-3, #8e8e93) !important;
}

.wx-feature-bullets {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.bullet-item {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.bullet-check {
  font-size: 20rpx;
}

.bullet-text {
  font-size: 24rpx;
  color: var(--rgm-text-2, #d1d1d6);
}

.modal-outline-btn {
  width: 100%;
  height: 84rpx;
  line-height: 84rpx;
  background-color: transparent;
  color: var(--rgm-text-3, #8e8e93);
  font-size: 26rpx;
  border-radius: 20rpx;
  margin-top: 20rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
}

.user-badge-right {
  padding: 8rpx 16rpx;
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border-radius: 12rpx;
}

.badge-text-right {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #ff6b35);
  font-weight: bold;
}

/* ── Auth Flow Modal Styling ── */
.auth-flow-box {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.recent-accounts-section {
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
}

.recent-title {
  font-size: 24rpx;
  color: var(--rgm-text-2, #aeaeb2);
  margin-bottom: 14rpx;
  display: block;
}

.recent-accounts-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.recent-acc-card {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background-color: var(--rgm-card-2, #222227);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  border-radius: 16rpx;
  padding: 14rpx 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.recent-acc-avatar {
  width: 64rpx;
  height: 64rpx;
  border-radius: 32rpx;
}

.recent-acc-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.recent-acc-name {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.recent-acc-meta {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.recent-acc-card.current-acc {
  border-color: rgba(16, 185, 129, 0.4);
  background-color: rgba(16, 185, 129, 0.08);
}

.acc-name-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.acc-badge {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.acc-badge.owner {
  background-color: rgba(255, 179, 0, 0.2);
  color: var(--rgm-amber, #ffb300);
}

.acc-badge.coach {
  background-color: rgba(0, 210, 190, 0.2);
  color: var(--rgm-blue, #00d2be);
}

.current-acc-tag {
  font-size: 22rpx;
  color: var(--rgm-green, #10b981);
  font-weight: bold;
}

.status-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-user-info {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  flex-wrap: wrap;
}

.status-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.status-logout-btn {
  font-size: 22rpx;
  color: var(--rgm-red, #ff453a);
  background: rgba(255, 69, 58, 0.12);
  border: 1rpx solid rgba(255, 69, 58, 0.3);
  border-radius: 12rpx;
  padding: 6rpx 16rpx;
  line-height: 1.4;
  margin: 0;
}

.recover-acc-box {
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 18rpx 20rpx;
  margin-top: 16rpx;
  margin-bottom: 8rpx;
}

.recover-title {
  font-size: 22rpx;
  color: var(--rgm-text-2, #aeaeb2);
  display: block;
  margin-bottom: 12rpx;
  font-weight: 500;
}

.recover-input-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.recover-input {
  flex: 1;
  height: 68rpx;
  background-color: var(--rgm-card-2, #1a1a1f);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 14rpx;
  padding: 0 16rpx;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.recover-btn {
  height: 68rpx;
  line-height: 68rpx;
  padding: 0 24rpx;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  background-color: var(--rgm-brand, #00d2be);
  border-radius: 14rpx;
  font-weight: bold;
  margin: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.recent-acc-action {
  font-size: 22rpx;
  color: var(--rgm-blue, #00d2be);
  font-weight: 500;
}

.divider-line-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-top: 20rpx;
  margin-bottom: 4rpx;
}

.divider-line {
  flex: 1;
  height: 1rpx;
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
}

.divider-text {
  font-size: 20rpx;
  color: var(--rgm-text-3, #636366);
}

.avatar-nickname-flex {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background-color: var(--rgm-card-2, #1a1a1f);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.wx-avatar-btn {
  width: 110rpx;
  height: 110rpx;
  border-radius: 55rpx;
  padding: 0;
  margin: 0;
  background-color: var(--rgm-card-3, #2c2c34);
  border: 2rpx dashed rgba(7, 193, 96, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  line-height: normal;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.wx-avatar-btn::after {
  border: none;
}

.wx-avatar-preview {
  width: 100%;
  height: 100%;
  border-radius: 55rpx;
}

.avatar-badge-tip {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.65);
  font-size: 16rpx;
  color: #07c160;
  text-align: center;
  padding: 2rpx 0;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.nickname-input-box {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.nickname-input {
  margin-bottom: 0 !important;
}

.auth-intro-box {
  background-color: rgba(7, 193, 96, 0.08);
  border: 1rpx solid rgba(7, 193, 96, 0.25);
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
}

.auth-intro-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-green, #07c160);
  display: block;
  margin-bottom: 8rpx;
}

.auth-intro-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.5;
  display: block;
}

.custom-user-form {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.terms-check-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 12rpx 0;
}

.checkbox-icon {
  font-size: 32rpx;
}

.terms-text-wrap {
  flex: 1;
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.4;
}

.terms-text {
  color: var(--rgm-text-3, #8e8e93);
}

.terms-link {
  color: var(--rgm-blue, #0a84ff);
  text-decoration: underline;
}

.confirm-auth-btn {
  width: 100%;
  height: 92rpx;
  line-height: 92rpx;
  background-color: var(--rgm-brand, #07c160);
  color: var(--rgm-text, #ffffff);
  font-size: 30rpx;
  font-weight: bold;
  border-radius: 24rpx;
  border: none;
  margin-top: 10rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* MFA Verification Styles */
.mfa-section {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.mfa-alert-box {
  background-color: rgba(255, 159, 10, 0.12);
  border: 1rpx solid rgba(255, 159, 10, 0.3);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 12rpx;
}

.mfa-alert-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-amber, #ff9f0a);
  display: block;
  margin-bottom: 8rpx;
}

.mfa-alert-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d1d6);
  line-height: 1.4;
  display: block;
}

.coros-mfa-box {
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
}

.coros-mfa-box .mfa-alert-title {
  color: var(--rgm-brand-text, #fc4c02);
}

.text-cancel-btn {
  background: transparent;
  color: var(--rgm-text-3, #8e8e93);
  font-size: 24rpx;
  text-align: center;
  margin-top: 16rpx;
  border: none;
}

/* Edit Profile Modal & Trigger Styles */
.avatar-wrap {
  position: relative;
  width: 96rpx;
  height: 96rpx;
  margin-right: 20rpx;
  flex-shrink: 0;
}

.avatar-camera-pill {
  position: absolute;
  bottom: -4rpx;
  right: -4rpx;
  background: var(--rgm-brand, #fc4c02);
  border: 2rpx solid var(--rgm-line-solid, #141416);
  border-radius: 50%;
  width: 36rpx;
  height: 36rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.camera-icon {
  font-size: 20rpx;
  line-height: 1;
}

.user-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}

.edit-pill {
  font-size: 20rpx;
  background: rgba(10, 132, 255, 0.15);
  color: var(--rgm-blue, #0a84ff);
  border: 1rpx solid rgba(10, 132, 255, 0.3);
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  font-weight: 600;
}

.edit-profile-modal {
  width: 660rpx;
  background-color: var(--rgm-card, #161619);
  border-radius: 36rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.avatar-edit-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 30rpx;
}

.avatar-preview-lg {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  border: 4rpx solid var(--rgm-brand, #fc4c02);
  box-shadow: 0 8rpx 24rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.25));
  margin-bottom: 24rpx;
}

.avatar-actions-row {
  display: flex;
  gap: 20rpx;
  width: 100%;
  margin-bottom: 12rpx;
}

.avatar-sub-btn {
  flex: 1;
  height: 76rpx;
  line-height: 76rpx;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 20rpx;
  text-align: center;
}

.avatar-sub-btn.wx-pick {
  background: rgba(7, 193, 96, 0.15);
  color: var(--rgm-green, #07c160);
  border: 1rpx solid rgba(7, 193, 96, 0.35);
}

.avatar-sub-btn.album-pick {
  background: rgba(10, 132, 255, 0.15);
  color: var(--rgm-blue, #0a84ff);
  border: 1rpx solid rgba(10, 132, 255, 0.35);
}

.avatar-hint {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  text-align: center;
  margin-top: 4rpx;
}

.edit-field-wrap {
  margin-bottom: 32rpx;
}

.edit-name-input {
  margin-top: 8rpx;
}


.save-profile-btn {
  margin-top: 10rpx;
  background-color: var(--rgm-brand, #fc4c02);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.modal-gender-row {
  display: flex;
  gap: 20rpx;
  margin-top: 8rpx;
}

.gender-pill {
  flex: 1;
  height: 76rpx;
  background: var(--rgm-card-2, #222226);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gender-pill.active {
  border-color: var(--rgm-brand, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
}

.gender-pill-txt {
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  font-weight: 500;
}

.modal-picker-box {
  height: 84rpx;
  background: var(--rgm-card-2, #222226);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  padding: 0 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-picker-val {
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
}

.modal-picker-arrow {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.modal-row-2 {
  display: flex;
  gap: 20rpx;
  margin-top: 10rpx;
}

.modal-col-half {
  flex: 1;
}

.modal-direct-links {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  margin: 24rpx 0 20rpx;
}

.direct-link-card {
  background: rgba(10, 132, 255, 0.08);
  border: 1rpx solid rgba(10, 132, 255, 0.25);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.direct-link-card.secondary {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.08));
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
}

.dlc-icon {
  font-size: 30rpx;
}

.dlc-texts {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.dlc-title {
  font-size: 24rpx;
  font-weight: 600;
  color: var(--rgm-text, #ffffff);
}


.dlc-arrow {
  font-size: 26rpx;
  color: var(--rgm-text-3, #8e8e93);
}

/* Auth Modal Tabs & Device Login */
.auth-tab-row {
  display: flex;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border-radius: 16rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
  gap: 8rpx;
}

.auth-tab-item {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  font-size: 24rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
  border-radius: 12rpx;
  transition: all 0.2s;
}

.auth-tab-item.active {
  background: var(--rgm-card-2, #1c1c1e);
  color: var(--rgm-blue, #00d2be);
  box-shadow: 0 2rpx 8rpx var(--rgm-shadow, rgba(0, 0, 0, 0.3));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.brand-tab-group {
  display: flex;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.brand-tab-btn {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  font-size: 24rpx;
  font-weight: bold;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  color: var(--rgm-text-2, #aeaeb2);
  border-radius: 14rpx;
}

.brand-tab-btn.active {
  border-color: #00d2be;
  background: rgba(0, 210, 190, 0.12);
  color: var(--rgm-blue, #00d2be);
}

.domain-select-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}

.domain-label {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.domain-btn-wrap {
  display: flex;
  gap: 12rpx;
}

.domain-chip {
  padding: 8rpx 18rpx;
  font-size: 22rpx;
  border-radius: 10rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-3, #8e8e93);
}

.domain-chip.active {
  background: rgba(0, 210, 190, 0.15);
  border-color: #00d2be;
  color: var(--rgm-blue, #00d2be);
  font-weight: bold;
}

.device-form {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.device-form-item {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.device-confirm-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #00d2be, #00a896)) !important;
  margin-top: 24rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.modal-mask.auth-modal-mask {
  padding-top: 0;
  align-items: center;
}

.modal-content.auth-modal-content {
  width: 670rpx;
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  margin-bottom: 0;
}

.auth-scroll-body {
  max-height: calc(86vh - 120rpx);
  width: 100%;
  box-sizing: border-box;
}

.auth-modal-content .modal-body {
  padding: 24rpx 36rpx 48rpx;
  box-sizing: border-box;
}

/* ── Privacy Guard Card & Privacy Controls ── */
.privacy-guard-card {
  border: 1rpx solid rgba(16, 185, 129, 0.25) !important;
  background: var(--rgm-card, linear-gradient(180deg, rgba(16, 185, 129, 0.04) 0%, rgba(18, 18, 20, 0.95) 100%));
  margin-top: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.security-chip {
  font-size: 20rpx;
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.12);
  border: 1rpx solid rgba(16, 185, 129, 0.25);
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
  font-family: monospace;
}

.privacy-statement-box {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border-radius: 20rpx;
  padding: 24rpx;
  margin: 16rpx 0 24rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
}

.privacy-rule-item {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
}

.privacy-rule-icon {
  font-size: 30rpx;
  margin-top: 4rpx;
}

.privacy-rule-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.privacy-rule-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #e5e7eb);
}

.privacy-rule-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #9ca3af);
  line-height: 1.5;
}

.privacy-actions-row {
  margin-top: 8rpx;
}

.purge-privacy-btn {
  width: 100%;
  height: 84rpx;
  background: rgba(239, 68, 68, 0.12);
  border: 1rpx solid rgba(239, 68, 68, 0.35);
  color: var(--rgm-red, #f87171);
  font-size: 26rpx;
  font-weight: 600;
  border-radius: 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.purge-privacy-btn:active {
  background: rgba(239, 68, 68, 0.25);
}

.label-with-sec {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.field-sec-tag {
  font-size: 18rpx;
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.12);
  border: 1rpx solid rgba(16, 185, 129, 0.25);
  padding: 2rpx 8rpx;
  border-radius: 8rpx;
}

.field-sec-tag.req-tag {
  color: var(--rgm-red, #f87171) !important;
  background: rgba(239, 68, 68, 0.15) !important;
  border-color: rgba(239, 68, 68, 0.35) !important;
  font-weight: bold;
}

/* ── Grand Org Status Section Card ── */
.org-status-section-card {
  border-left: 6rpx solid #f59e0b;
}

.org-status-item {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 24rpx;
  margin-top: 16rpx;
}

.org-state-confirmed {
  border-color: rgba(16, 185, 129, 0.3);
  background: rgba(16, 185, 129, 0.05);
}

.org-state-expired,
.org-state-suspended {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.08);
}

.org-state-pending {
  border-color: rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.05);
}

.org-state-temporary {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.05);
}

.org-status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14rpx;
}

.org-name-wrap {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.org-item-name {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.org-status-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
}

.badge-confirmed {
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
}

.badge-pending {
  color: var(--rgm-blue, #60a5fa);
  background: rgba(59, 130, 246, 0.15);
  border: 1rpx solid rgba(59, 130, 246, 0.3);
}

.badge-temporary {
  color: var(--rgm-amber, #fbbf24);
  background: rgba(245, 158, 11, 0.15);
  border: 1rpx solid rgba(245, 158, 11, 0.3);
}

.badge-expired,
.badge-suspended {
  color: var(--rgm-red, #f87171);
  background: rgba(239, 68, 68, 0.18);
  border: 1rpx solid rgba(239, 68, 68, 0.4);
}

.org-status-desc {
  margin-top: 10rpx;
}

.org-desc-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.5;
  display: block;
}

.warning-text {
  color: var(--rgm-red, #fca5a5) !important;
  font-weight: 500;
}

.missing-fields-box {
  margin-top: 12rpx;
  padding: 12rpx 16rpx;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 12rpx;
  border: 1rpx solid rgba(245, 158, 11, 0.2);
}

.missing-title {
  font-size: 20rpx;
  color: var(--rgm-amber, #fbbf24);
  font-weight: bold;
}

.missing-labels {
  font-size: 20rpx;
  color: var(--rgm-text, #fef3c7);
}

.org-action-btn {
  margin-top: 16rpx;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #f59e0b, #d97706));
  color: #000000;
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 12rpx 28rpx;
  line-height: 1.4;
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.org-action-btn.btn-danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.org-action-btn.btn-secondary {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-blue, #38bdf8);
  border: 1rpx solid rgba(56, 189, 248, 0.35);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.field-privacy-subtip {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
  margin-top: 8rpx;
  line-height: 1.4;
  display: block;
}

/* ── Secure Input & Eye Toggle in Profile ── */
.secure-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}

.secure-input {
  flex: 1;
  padding-right: 76rpx !important;
}

.eye-toggle-btn {
  position: absolute;
  right: 12rpx;
  top: 50%;
  transform: translateY(-50%);
  width: 60rpx;
  height: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.eye-icon {
  font-size: 32rpx;
  opacity: 0.85;
}

.eye-toggle-btn:active .eye-icon {
  opacity: 1;
  transform: scale(1.1);
}

.secure-picker-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  width: 100%;
}

.secure-picker-flex {
  flex: 1;
}

.secure-picker-row .eye-toggle-btn {
  position: static;
  transform: none;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 16rpx;
  width: 80rpx;
  height: 80rpx;
}

/* ── Custom Privacy Purge Modal ── */
.purge-modal-mask {
  align-items: center !important;
  padding-top: 0 !important;
}

.purge-modal-content {
  width: 90% !important;
  max-width: 640rpx !important;
  background: var(--rgm-card, #141416) !important;
  border-radius: 32rpx !important;
  border: 1rpx solid rgba(239, 68, 68, 0.3) !important;
  padding: 0 !important;
  overflow: hidden;
  box-shadow: 0 16rpx 48rpx var(--rgm-shadow, rgba(0, 0, 0, 0.7));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.purge-modal-header {
  padding: 32rpx 36rpx 20rpx;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.text-red {
  color: var(--rgm-red, #ef4444) !important;
}

.purge-modal-body {
  padding: 28rpx 36rpx 36rpx !important;
}

.purge-warning-banner {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  background: rgba(239, 68, 68, 0.1);
  border: 1rpx solid rgba(239, 68, 68, 0.25);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
}

.purge-warn-icon {
  font-size: 36rpx;
}

.purge-warn-text-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.purge-warn-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-red, #fca5a5);
}

.purge-warn-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.5;
}

.purge-details-box {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 32rpx;
}

.purge-detail-header {
  font-size: 24rpx;
  font-weight: bold;
  margin-bottom: 14rpx;
  display: block;
}

.red-header {
  color: var(--rgm-red, #f87171);
}

.green-header {
  color: var(--rgm-green, #10b981);
}

.purge-detail-item {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  margin-bottom: 10rpx;
}

.purge-dot {
  font-size: 22rpx;
  font-weight: bold;
  width: 28rpx;
  line-height: 1.4;
}

.red-dot {
  color: var(--rgm-red, #ef4444);
}

.green-dot {
  color: var(--rgm-green, #10b981);
}

.purge-item-text {
  flex: 1;
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.4;
}

.purge-divider {
  height: 1rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  margin: 18rpx 0;
}

.purge-modal-actions {
  display: flex;
  gap: 20rpx;
}

.purge-cancel-btn {
  flex: 1;
  height: 84rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  color: var(--rgm-text, #e5e7eb);
  font-size: 26rpx;
  font-weight: 600;
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.purge-execute-btn {
  flex: 1;
  height: 84rpx;
  background: linear-gradient(135deg, #ef4444, #dc2626) !important;
  color: var(--rgm-text, #ffffff) !important;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 16rpx rgba(239, 68, 68, 0.35);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

/* ── 帮助与技术支持 (Support & Feedback) 样式 ── */
.device-support-quick-bar {
  margin-top: 20rpx;
  padding: 18rpx 22rpx;
  border-radius: 18rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.08));
  border: 1rpx dashed var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.dsqb-text {
  font-size: 23rpx;
  color: var(--rgm-text-2, #d4d4d8);
}

.dsqb-link {
  font-size: 23rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
  flex-shrink: 0;
}

.support-diag-box {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.sdiag-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.sdiag-label {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

.sdiag-val {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.sdiag-copy-pill {
  padding: 10rpx 20rpx;
  border-radius: 999rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
  flex-shrink: 0;
}

.support-contact-btn {
  width: 100%;
  height: 88rpx;
  border-radius: 22rpx;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  box-shadow: 0 6rpx 20rpx rgba(16, 185, 129, 0.3);
  --rgm-text: var(--rgm-on-bright);
}

.support-cat-row {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-bottom: 20rpx;
}

.support-cat-chip {
  padding: 12rpx 22rpx;
  border-radius: 16rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  font-size: 23rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.support-cat-chip.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16));
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 700;
}

.support-textarea {
  width: 100%;
  min-height: 180rpx;
  box-sizing: border-box;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 20rpx;
  padding: 20rpx 22rpx;
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 18rpx;
  line-height: 1.5;
}

.support-contact-input {
  margin-bottom: 22rpx;
}

.support-submit-btn {
  width: 100%;
  height: 86rpx;
  border-radius: 22rpx;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ea580c 100%));
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  --rgm-text: var(--rgm-on-brand);
}

.support-ticket-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.support-ticket-item {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.09));
  border-radius: 20rpx;
  padding: 22rpx 24rpx;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.stkt-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.stkt-cat {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

.stkt-status {
  font-size: 21rpx;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: var(--rgm-brand-tint, rgba(245, 158, 11, 0.15));
  color: var(--rgm-brand-text, #fbbf24);
  font-weight: 600;
}

.stkt-status.resolved {
  background: rgba(16, 185, 129, 0.14);
  color: var(--rgm-green, #34d399);
}

.stkt-content {
  font-size: 25rpx;
  color: var(--rgm-text, #f4f4f5);
  line-height: 1.5;
}

.stkt-time {
  font-size: 21rpx;
  color: var(--rgm-text-3, #71717a);
}

.stkt-reply-box {
  margin-top: 8rpx;
  padding: 16rpx 20rpx;
  border-radius: 16rpx;
  background: rgba(16, 185, 129, 0.1);
  border: 1rpx solid rgba(16, 185, 129, 0.28);
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.stkt-reply-title {
  font-size: 22rpx;
  font-weight: 700;
  color: #10b981;
}

.stkt-reply-text {
  font-size: 24rpx;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.5;
}

.share-race-pill {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(251, 191, 36, 0.22), rgba(252, 76, 2, 0.22)));
  border: 1rpx solid var(--rgm-brand-line, rgba(251, 191, 36, 0.55));
  color: var(--rgm-brand-text, #fbbf24);
}

.comp-share-card-btn {
  margin-left: auto;
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #fbbf24, #fc4c02);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 14rpx rgba(252, 76, 2, 0.35);
}

.comp-share-card-txt {
  font-size: 21rpx;
  font-weight: 800;
  color: #090b10;
}

</style>

