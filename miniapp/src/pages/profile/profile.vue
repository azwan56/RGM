<template>
  <view class="profile-page">
    <!-- ── 顶部用户卡（无论登录与否始终显示在最顶部）── -->
    <view v-if="!user" class="login-hero-card">
      <view class="login-hero-left">
        <view class="hero-icon-circle">
          <text class="hero-wx-icon">🟢</text>
        </view>
        <view class="hero-text-wrap">
          <text class="hero-title">微信跑者一键登录</text>
          <text class="hero-desc">点击下方按钮，开启独立跑步档案与数据管理</text>
        </view>
      </view>
      <!-- 用 button open-type 保证最高优先级点击响应 -->
      <button class="hero-login-btn-native" @click="openAuthModal">
        🟢 微信一键快速登录
      </button>
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
          <text class="edit-pill">✏️ 修改资料</text>
        </view>
        <text class="user-id">{{ user?.id }} · 点击修改昵称与头像 ›</text>
      </view>
      <button class="switch-user-btn" @click.stop="handleLogout">退出切换</button>
    </view>

    <!-- ── CARD 1: 我的跑团与管理 (Running Club Card) ── -->
    <view class="section-card club-card-highlight">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🏃</text>
          <text class="card-title">我的跑团与管理</text>
        </view>
        <text class="club-role-tag" :class="'role-' + (userClub?.role || 'owner')">
          {{ userClub?.role === 'owner' ? '👑 跑团主理人' : userClub?.role === 'coach' ? '🧢 认证教练' : '🏃 核心团员' }}
        </text>
      </view>

      <!-- Joined Club Summary -->
      <view class="joined-club-box">
        <view class="club-mini-info">
          <image class="mini-logo" :src="userClub?.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
          <view class="mini-texts">
            <text class="club-title-text">{{ userClub?.name || "RGM 巅峰先锋跑团" }}</text>
            <text class="club-desc-text">{{ userClub?.description || "基于科学耐力训练与 Renato Canova 哲学的精英跑者联盟" }}</text>
          </view>
        </view>
        <view class="invite-copy-row" @click="handleCopyClubInvite">
          <text class="invite-lbl">跑团专属邀请码: </text>
          <text class="invite-code">{{ userClub?.invite_code || "RGM888" }}</text>
          <text class="copy-action"> (点击复制)</text>
        </view>
      </view>

      <!-- Club Action Buttons -->
      <view class="club-btn-grid">
        <button class="club-act-btn join-btn" @click="showJoinModal = true">
          ➕ 加入其他跑团
        </button>
        <button class="club-act-btn create-btn" @click="showCreateModal = true">
          🏆 创建新跑团
        </button>
      </view>
    </view>

    <!-- ── CARD 2: Device Connection Status Card (Garmin & COROS) ── -->
    <view class="section-card">
      <view class="card-title-row">
        <text class="card-title">运动手表数据直连</text>
      </view>

      <!-- Garmin Status Block -->
      <view class="device-status-item">
        <view class="device-item-header">
          <view class="device-name-wrap">
            <text class="device-badge garmin-badge">Garmin</text>
            <text class="device-name-text">佳明手表直连</text>
          </view>
          <text class="conn-status" :class="{ connected: garminConnected }">
            {{ garminConnected ? "已连接 ✓" : "未连接" }}
          </text>
        </view>
        <text class="desc-text" style="margin: 8rpx 0 16rpx 0;">
          {{ garminConnected
              ? `已绑定：${garminEmail} (${garminDomain})`
              : "自动同步跑步心率、配速、步频、HRV 与睡眠体能指标。" }}
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

      <!-- COROS Status Block -->
      <view class="device-status-item" style="border-top: 1rpx solid rgba(255, 255, 255, 0.08); padding-top: 20rpx;">
        <view class="device-item-header">
          <view class="device-name-wrap">
            <text class="device-badge coros-badge">COROS</text>
            <text class="device-name-text">高驰手表直连</text>
          </view>
          <text class="conn-status" :class="{ connected: corosConnected }">
            {{ corosConnected ? "已连接 ✓" : "未连接" }}
          </text>
        </view>
        <text class="desc-text" style="margin: 8rpx 0 16rpx 0;">
          {{ corosConnected
              ? `已绑定：${corosAccount} (${corosDomain})`
              : "自动同步高驰 Training Hub 跑步记录与训练负荷。" }}
        </text>
        <button
          v-if="!corosConnected"
          class="garmin-btn coros-btn"
          @click="openDeviceModal('coros')"
        >
          绑定高驰账号
        </button>
        <button
          v-else
          class="unbind-btn"
          :loading="unbindingCoros"
          @click="handleUnbindCoros"
        >
          解除高驰绑定
        </button>
      </view>
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

    <!-- ── CARD 3: 生理参数与身体指标 ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">💓</text>
          <text class="card-title">生理参数与身体指标</text>
        </view>
      </view>

      <view class="form-grid-2">
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
        <view class="form-group">
          <text class="label">身高 (cm)</text>
          <input
            class="form-input"
            type="number"
            placeholder="175"
            :value="profile?.height || ''"
            @input="onInputHeight"
          />
        </view>
        <view class="form-group">
          <text class="label">体重 (kg)</text>
          <input
            class="form-input"
            type="digit"
            placeholder="68.0"
            :value="profile?.weight || ''"
            @input="onInputWeight"
          />
        </view>
      </view>
    </view>

    <!-- ── CARD 4: 个人2026年度跑量规划 ── -->
    <view class="section-card">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🎯</text>
          <text class="card-title">个人跑量目标规划 (2026)</text>
        </view>
        <view class="target-badge" :class="{ locked: goalMode === 'custom' }">
          {{ goalMode === 'custom' ? '按月自定义' : `全年统一: ${targetDistance} km/月` }}
        </view>
      </view>

      <text class="desc-text">
        设定您个人的月跑量计划。支持全年统一均值设定，也可针对秋冬重点备赛期按月自定义递增规划。数据仅保存在您个人的跑者档案中。
      </text>

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
          按月自定义 (备赛期进阶)
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
        <text v-if="goalMode === 'custom'" class="locked-tip">
          💡 已开启按月自定义模式，下方可针对每个月份独立调整
        </text>
        <text v-else class="uniform-tip">
          拖动滑块即可一键将您的 1~12 月跑量目标统一设为 {{ targetDistance }} km
        </text>
      </view>

      <!-- 12 Months Grid -->
      <view class="custom-months-section">
        <view class="custom-months-header">
          <text class="cm-title">各月跑量细化目标 (km)</text>
          <text v-if="goalMode === 'custom'" class="sync-uniform-action" @click="syncUniformToAll">
            重置为统一 {{ targetDistance }}km
          </text>
        </view>

        <view class="months-grid">
          <view v-for="m in 12" :key="m" class="month-cell">
            <text class="month-label">{{ m }}月</text>
            <input
              class="month-input"
              type="number"
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
            <text class="cm-title">🏃 常规周跑量计划</text>
          </view>
          <text class="weekly-target-badge">{{ weeklyTarget }} km / 周</text>
        </view>
        <text class="weekly-desc-tip">
          周跑量计划无需按 52 周单独设定，设定常规周目标即可自动应用于全年的每周训练进度与负荷追踪。
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
            滑动调整每周常规跑步目标：{{ weeklyTarget }} km（相当于月均约 {{ Math.round(weeklyTarget * 4.3) }} km）
          </text>
        </view>

        <view class="weekly-save-action">
          <button class="save-weekly-btn" :loading="savingWeekly" @click="handleSaveWeeklyOnly">
            单独保存周跑量目标 ({{ weeklyTarget }}km)
          </button>
        </view>
      </view>

      <view class="save-box">
        <button class="save-btn" :loading="saving" @click="handleSaveAll">
          保存我的跑量目标与配置
        </button>
      </view>
    </view>

    <!-- 底部退出登录（仅登录后显示） -->
    <view v-if="user" class="logout-box">
      <button class="logout-btn" @click="handleLogout">退出登录 / 切换微信账号</button>
    </view>

    <!-- ── 微信授权登录专属弹窗 (Pure WeChat Login Modal) ── -->
    <view v-if="showAuthModal" class="modal-mask" @click="closeAuthModal" @touchmove.stop.prevent>
      <view class="modal-content auth-modal-content" @click.stop="noop">
        <view class="modal-header">
          <text class="modal-title">{{ user ? "微信跑者账号管理" : "微信一键授权登录" }}</text>
          <view class="close-hit" @click="closeAuthModal">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="modal-body">
          <view class="wx-brand-hero">
            <text class="wx-hero-icon">🏃</text>
            <text class="wx-hero-title">RGM 跑团助手</text>
            <text class="wx-hero-desc">科学耐力训练 · Garmin 数据直连 · 先锋跑团</text>
          </view>

          <!-- Current account status if logged in -->
          <view v-if="user" class="wx-account-status-card">
            <text class="status-title">当前微信跑者会话：</text>
            <view class="status-row">
              <text class="status-label">账号 UID: </text>
              <text class="status-val">{{ user.id }}</text>
            </view>
            <view class="status-row">
              <text class="status-label">跑者昵称: </text>
              <text class="status-val">{{ profile?.display_name || user.display_name || "微信跑者" }}</text>
            </view>
            <view class="status-row">
              <text class="status-label">佳明连接: </text>
              <text class="status-val text-green" v-if="garminConnected">已绑定 ({{ garminEmail || '佳明账号' }})</text>
              <text class="status-val text-muted" v-else>未连接佳明设备</text>
            </view>
          </view>

          <view v-else class="auth-flow-box">
            <view class="auth-intro-box">
              <text class="auth-intro-title">🛡️ 微信授权安全登录</text>
              <text class="auth-intro-desc">
                系统将使用您当前的微信账号建立专属独立跑者档案。每个微信号独立隔离，绝不混淆他人数据。
              </text>
            </view>

            <!-- 1. 本机多账号快速切换 (如果本机曾登录过 1 个或多个账号) -->
            <view v-if="recentAccounts && recentAccounts.length > 0" class="recent-accounts-section">
              <text class="recent-title">👥 本机已存跑者账号 (点击直接切换)</text>
              <view class="recent-accounts-list">
                <view
                  v-for="acc in recentAccounts"
                  :key="acc.id"
                  class="recent-acc-card"
                  @click="selectRecentAccount(acc)"
                >
                  <image
                    class="recent-acc-avatar"
                    :src="acc.avatar_url || defaultAvatar"
                    mode="aspectFill"
                  />
                  <view class="recent-acc-info">
                    <text class="recent-acc-name">{{ acc.display_name }}</text>
                    <text class="recent-acc-meta" v-if="acc.garmin_connected">佳明直连 ({{ acc.garmin_email || '已绑定' }})</text>
                    <text class="recent-acc-meta" v-else>未绑定佳明</text>
                  </view>
                  <text class="recent-acc-action">一键进入 ›</text>
                </view>
              </view>
              <view class="divider-line-row">
                <view class="divider-line" />
                <text class="divider-text">或以新微信身份授权登录</text>
                <view class="divider-line" />
              </view>
            </view>

            <!-- 2. 微信原生头像与微信昵称快捷获取 -->
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
                  <text class="field-label">微信昵称 (点击下方键盘可一键填入)</text>
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
              🟢 微信一键授权安全登录
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- Large & Modern Device Bind Modal (Garmin & COROS) -->
    <view v-if="showGarminModal" class="modal-mask" @click="showGarminModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">连接运动手表数据</text>
          <view class="close-hit" @click="showGarminModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <!-- Brand Switcher Tabs -->
        <view class="brand-switch-row">
          <view
            class="brand-switch-btn"
            :class="{ active: selectedBrand === 'garmin' }"
            @click="selectedBrand = 'garmin'"
          >
            Garmin 佳明
          </view>
          <view
            class="brand-switch-btn"
            :class="{ active: selectedBrand === 'coros' }"
            @click="selectedBrand = 'coros'"
          >
            COROS 高驰
          </view>
        </view>

        <view class="modal-body">
          <!-- ── GARMIN TAB ── -->
          <view v-if="selectedBrand === 'garmin'">
            <!-- MFA Verification Step -->
            <view v-if="needsMfa" class="mfa-section">
              <view class="mfa-alert-box">
                <text class="mfa-alert-title">🔒 佳明官方双重安全验证</text>
                <text class="mfa-alert-desc">佳明已向您的注册邮箱或手机发送了 6 位安全验证码，请输入以完成绑定：</text>
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
                确认验证码并完成绑定
              </button>
              <button class="text-cancel-btn" @click="needsMfa = false">
                返回修改账号与密码
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
                  中国版 (garmin.cn)
                </view>
                <view
                  class="domain-btn"
                  :class="{ active: inputDomain === 'garmin.com' }"
                  @click="inputDomain = 'garmin.com'"
                >
                  国际版 (garmin.com)
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
                确认连接佳明并立即同步
              </button>
            </view>
          </view>

          <!-- ── COROS TAB ── -->
          <view v-else-if="selectedBrand === 'coros'">
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

            <text class="field-label">高驰登录密码</text>
            <input
              class="large-input"
              type="password"
              :adjust-position="false"
              :cursor-spacing="30"
              placeholder="请输入您的 COROS 密码"
              placeholder-class="placeholder-style"
              v-model="inputCorosPassword"
            />

            <button class="large-primary-btn coros-primary-btn" :loading="bindingCoros" @click="handleBindCoros">
              确认连接高驰并立即同步
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
          <text class="field-label">跑团专属 6 位邀请码</text>
          <input
            class="large-input center-input"
            type="text"
            maxlength="6"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="例如: RGM888"
            placeholder-class="placeholder-style"
            v-model="inviteCodeInput"
          />
          <button class="large-primary-btn" :loading="joiningClub" @click="handleJoinClub">
            立即加入
          </button>
        </view>
      </view>
    </view>

    <!-- ── Create Club Modal ── -->
    <view v-if="showCreateModal" class="modal-mask" @click="showCreateModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">创建新跑团</text>
          <view class="close-hit" @click="showCreateModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="modal-body">
          <text class="field-label">跑团名称</text>
          <input
            class="large-input"
            type="text"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="例如: 世纪公园破风战队"
            placeholder-class="placeholder-style"
            v-model="newClubName"
          />

          <text class="field-label">跑团口号与简介</text>
          <textarea
            class="large-textarea"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="科学备赛，快乐奔跑..."
            placeholder-class="placeholder-style"
            v-model="newClubDesc"
          />

          <button class="large-primary-btn" :loading="creatingClub" @click="handleCreateClub">
            立即创建跑团
          </button>
        </view>
      </view>
    </view>

    <!-- ── Edit Profile Modal (修改昵称与头像) ── -->
    <view v-if="showEditProfileModal" class="modal-mask" @click="showEditProfileModal = false" @touchmove.stop.prevent>
      <view class="modal-content edit-profile-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title">修改个人资料与头像</text>
          <view class="close-hit" @click="showEditProfileModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="modal-body">
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
            <text class="avatar-hint">头像将同步展示于跑团花名册、大盘排行榜与教练视窗</text>
          </view>

          <!-- 2. 昵称编辑 -->
          <view class="edit-field-wrap">
            <text class="field-label">跑者昵称 (Display Name)</text>
            <input
              type="nickname"
              class="large-input edit-name-input"
              :value="editDisplayName"
              placeholder="请输入您的跑者昵称"
              placeholder-class="placeholder-style"
              @blur="onEditNameBlur"
              @input="onEditNameInput"
            />
            <text class="input-hint">可轻触输入框上方快捷气泡自动填入微信昵称，或直接输入</text>
          </view>

          <!-- 3. 保存按钮 -->
          <button
            class="large-primary-btn save-profile-btn"
            :loading="savingProfile"
            @click="handleSaveProfile"
          >
            保存并立即生效
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import {
  request,
  getStoredUser,
  clearSession,
  authenticateWechatUser,
  switchAccount,
  uploadAvatarFile,
  API_BASE_URL,
  UserProfile,
  bindCoros,
  unbindCoros,
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
};

const user = ref<UserProfile | null>(null);
const profile = ref<any>(defaultProfile);
const races = ref<any[]>([]);
const userClub = ref<any>(null);

const garminConnected = ref(false);
const garminEmail = ref("");
const garminDomain = ref("garmin.cn");

const corosConnected = ref(false);
const corosAccount = ref("");
const corosDomain = ref("teamcnapi.coros.com");

const selectedBrand = ref<"garmin" | "coros">("garmin");
const inputCorosAccount = ref("");
const inputCorosPassword = ref("");
const inputCorosDomain = ref("teamcnapi.coros.com");
const bindingCoros = ref(false);
const unbindingCoros = ref(false);

const loggingIn = ref(false);

const showAuthModal = ref(false);
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
const savingProfile = ref(false);

function openEditProfileModal() {
  editDisplayName.value = profile.value?.display_name || user.value?.display_name || "";
  editAvatarUrl.value = profile.value?.avatar_url || user.value?.avatar_url || "";
  showEditProfileModal.value = true;
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
    const payload: any = { display_name: name };
    if (editAvatarUrl.value) {
      payload.avatar_url = editAvatarUrl.value;
    }
    await request(`/api/profile/${encodeURIComponent(uid)}`, "PUT", payload);
    if (profile.value) {
      profile.value.display_name = name;
      if (editAvatarUrl.value) profile.value.avatar_url = editAvatarUrl.value;
    }
    if (user.value) {
      user.value.display_name = name;
      if (editAvatarUrl.value) user.value.avatar_url = editAvatarUrl.value;
      uni.setStorageSync("rgm_user", user.value);
      recordRecentUser(user.value);
    }
    uni.showToast({ title: "资料保存成功 🎉", icon: "success" });
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
const showCreateModal = ref(false);
const inviteCodeInput = ref("");
const newClubName = ref("");
const newClubDesc = ref("");
const joiningClub = ref(false);
const creatingClub = ref(false);

const targetDistance = ref(200);
const weeklyTarget = ref(50);
const savingWeekly = ref(false);
const monthlyTargets = ref<number[]>(Array(12).fill(200));
const goalMode = ref<"uniform" | "custom">("uniform");
const saving = ref(false);

function setGoalMode(mode: "uniform" | "custom") {
  goalMode.value = mode;
  if (mode === "uniform") {
    monthlyTargets.value = Array(12).fill(targetDistance.value);
  }
}

function onTargetSliderChange(val: number) {
  if (goalMode.value === "custom") return;
  targetDistance.value = val;
  monthlyTargets.value = Array(12).fill(val);
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
    await request(`/api/profile/${encodeURIComponent(uid)}/goal`, "PUT", {
      weekly_target: Number(weeklyTarget.value),
    });
    uni.showToast({ title: `周目标已单独生效 (${weeklyTarget.value}km)`, icon: "success" });
  } catch (err: any) {
    uni.showToast({ title: err?.message || "保存失败", icon: "none" });
  } finally {
    savingWeekly.value = false;
  }
}

function syncUniformToAll() {
  monthlyTargets.value = Array(12).fill(targetDistance.value);
  uni.showToast({ title: `已将全部月份统一设为 ${targetDistance.value}km`, icon: "none" });
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
  loadRecentAccounts();
  showAuthModal.value = true;
}

async function selectRecentAccount(acc: any) {
  try {
    uni.showLoading({ title: "正在切换...", mask: true });
    const u = await switchAccount(acc.id);
    user.value = u;
    recordRecentUser(u);
    showAuthModal.value = false;
    uni.hideLoading();
    uni.showToast({ title: `已切换至 ${u.display_name}`, icon: "success" });
    await loadProfileData();
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: err?.message || "切换失败", icon: "none" });
  }
}

function closeAuthModal() {
  showAuthModal.value = false;
}

function showTermsModal() {
  uni.showModal({
    title: "用户服务协议",
    content: "欢迎使用 RGM 跑团助手。本小程序提供科学耐力训练、心率与体能分析及跑团互动服务。我们承诺严格保护您的个人运动健康隐私，数据仅用于训练分析与展示。",
    showCancel: false,
  });
}

function showPrivacyModal() {
  uni.showModal({
    title: "隐私政策",
    content: "RGM 跑团助手严格遵循法律法规保护用户隐私。您的 Garmin 账号、跑步轨迹、心率等生理指标仅在您主动授权绑定后同步，绝不对外共享。",
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

function handleLogout() {
  uni.showModal({
    title: "退出登录",
    content: "确定要退出当前微信跑者账号吗？",
    success: async (res) => {
      if (res.confirm) {
        clearSession();
        user.value = null;
        profile.value = defaultProfile;
        garminConnected.value = false;
        userClub.value = null;
        races.value = [];
        showAuthModal.value = true;
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
  // Only restore from already-stored session; do NOT auto-login silently.
  // Users must tap the login button themselves.
  user.value = getStoredUser();
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    const [res, clubRes] = await Promise.all([
      request(`/api/profile/${uid}`),
      request(`/api/team/my-clubs/${uid}`),
    ]);

    if (res?.profile) {
      profile.value = res.profile;
      if (!user.value) user.value = {} as any;
      user.value.id = res.profile.id || uid;
      if (res.profile.avatar_url) user.value.avatar_url = res.profile.avatar_url;
      if (res.profile.display_name) user.value.display_name = res.profile.display_name;
      uni.setStorageSync("rgm_user", user.value);
      garminConnected.value = !!res.profile.garmin_connected;
      garminEmail.value = res.profile.garmin_email || "";
      garminDomain.value = res.profile.garmin_domain || "garmin.cn";
      inputDomain.value = garminDomain.value;
      corosConnected.value = !!res.profile.coros_connected;
      corosAccount.value = res.profile.coros_account || "";
      corosDomain.value = res.profile.coros_domain || "teamcnapi.coros.com";
      inputCorosDomain.value = corosDomain.value;
    } else {
      garminConnected.value = false;
      corosConnected.value = false;
    }

    if (res?.goal) {
      targetDistance.value = res.goal.target_distance || 200;
      weeklyTarget.value = res.goal.weekly_target || Math.round((res.goal.target_distance || 200) / 4) || 50;
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
    userClub.value = clubs.length > 0 ? clubs[0] : null;
  } catch (err) {
    console.error("Failed to load profile:", err);
  }
}

function handleCopyClubInvite() {
  if (!userClub.value?.invite_code) return;
  uni.setClipboardData({
    data: userClub.value.invite_code,
    success: () => {
      uni.showToast({ title: "跑团邀请码已复制", icon: "success" });
    }
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
    uni.showToast({ title: e.message || "加入失败，请核对邀请码", icon: "none" });
  } finally {
    joiningClub.value = false;
  }
}

async function handleCreateClub() {
  if (!newClubName.value.trim()) return;
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  creatingClub.value = true;
  try {
    await request("/api/team/clubs", "POST", {
      owner_id: uid,
      name: newClubName.value.trim(),
      description: newClubDesc.value.trim(),
      city: "上海"
    });
    uni.showToast({ title: "跑团创建成功！", icon: "success" });
    showCreateModal.value = false;
    newClubName.value = "";
    newClubDesc.value = "";
    await loadProfileData();
  } catch (e: any) {
    uni.showToast({ title: "创建失败", icon: "none" });
  } finally {
    creatingClub.value = false;
  }
}

function onMonthTargetInput(idx: number, val: string) {
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
}

function onInputWeight(e: any) {
  if (!profile.value) profile.value = {};
  profile.value.weight = parseFloat(e.detail.value) || 0;
}

async function handleSaveAll() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  saving.value = true;
  try {
    await request(`/api/profile/${uid}`, "PUT", {
      max_heart_rate: profile.value?.max_heart_rate,
      resting_heart_rate: profile.value?.resting_heart_rate,
      height_cm: profile.value?.height || profile.value?.height_cm,
      weight_kg: profile.value?.weight || profile.value?.weight_kg,
    });

    const finalMonthlyTargets = goalMode.value === "uniform"
      ? Array(12).fill(Number(targetDistance.value))
      : monthlyTargets.value.map((v) => Number(v) || 0);

    await request(`/api/profile/${encodeURIComponent(uid)}/goal`, "PUT", {
      target_distance: Number(targetDistance.value),
      weekly_target: Number(weeklyTarget.value),
      period_type: "monthly",
      monthly_targets: finalMonthlyTargets,
    });

    uni.showToast({ title: "个人跑量目标已保存", icon: "success" });
  } catch (err: any) {
    uni.showToast({ title: err?.message || "保存失败", icon: "none" });
  } finally {
    saving.value = false;
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
    uni.showToast({ title: "绑定并同步成功", icon: "success" });
    showGarminModal.value = false;
    needsMfa.value = false;
    inputMfaCode.value = "";
    inputPassword.value = "";
    await loadProfileData();
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

function openDeviceModal(brand: "garmin" | "coros" = "garmin") {
  selectedBrand.value = brand;
  showGarminModal.value = true;
}

async function handleBindCoros() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  const acc = inputCorosAccount.value.trim();
  const pwd = inputCorosPassword.value.trim();
  if (!acc || !pwd) {
    uni.showToast({ title: "请输入高驰账号与密码", icon: "none" });
    return;
  }
  bindingCoros.value = true;
  try {
    const res = await bindCoros({
      uid: uid,
      account: acc,
      password: pwd,
      domain: inputCorosDomain.value,
    });

    if (res?.uid && user.value && res.uid !== user.value.id) {
      user.value.id = res.uid;
      user.value.coros_connected = true;
      user.value.coros_account = acc;
      uni.setStorageSync("rgm_user", user.value);
      if (res?.token) {
        uni.setStorageSync("rgm_token", res.token);
      }
    }
    uni.showToast({ title: "高驰绑定并同步成功", icon: "success" });
    showGarminModal.value = false;
    inputCorosPassword.value = "";
    await loadProfileData();
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
  loadProfileData();
});
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
}

.login-hero-card {
  background: linear-gradient(135deg, rgba(7, 193, 96, 0.22) 0%, #151518 100%);
  border: 1rpx solid rgba(7, 193, 96, 0.45);
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
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
  color: #ffffff;
  display: block;
}

.hero-desc {
  font-size: 22rpx;
  color: #a0a0a5;
  margin-top: 6rpx;
  display: block;
  line-height: 1.4;
}

.hero-login-btn,
.hero-login-btn-native {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  background-color: #07c160;
  color: #ffffff;
  font-size: 30rpx;
  font-weight: bold;
  border-radius: 20rpx;
  border: none;
  text-align: center;
  margin-top: 4rpx;
}

.hero-login-btn-text,
.modal-wx-btn-text {
  color: #ffffff;
  font-size: 30rpx;
  font-weight: bold;
}

.switch-user-btn {
  padding: 0 20rpx;
  background-color: #242429;
  color: #8e8e93;
  font-size: 24rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  height: 56rpx;
  line-height: 56rpx;
  margin: 0;
}

.user-card {
  background: linear-gradient(135deg, #1c1c20 0%, #131316 100%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  display: flex;
  align-items: center;
  gap: 24rpx;
}

.avatar {
  width: 100rpx;
  height: 100rpx;
  border-radius: 50rpx;
  border: 2rpx solid rgba(252, 76, 2, 0.4);
}

.user-meta {
  flex: 1;
}

.user-name {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
}

.user-id {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 6rpx;
  display: block;
}

.wechat-quick-card {
  background: linear-gradient(135deg, rgba(7, 193, 96, 0.15) 0%, #151518 100%);
  border: 1rpx solid rgba(7, 193, 96, 0.3);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
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
  color: #ffffff;
  display: block;
}

.wx-tip-sub {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 4rpx;
  display: block;
}

.wx-login-action-btn {
  background: #07c160;
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 80rpx;
  line-height: 80rpx;
  border: none;
}

.section-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
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
  color: #ffffff;
}

.conn-status {
  font-size: 22rpx;
  font-weight: bold;
  color: #8e8e93;
}

.conn-status.connected {
  color: #30d158;
}

.desc-text {
  font-size: 22rpx;
  color: #8e8e93;
  line-height: 1.4;
  margin-bottom: 20rpx;
  display: block;
}

.garmin-btn {
  background-color: #0a84ff;
  color: #ffffff;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
}

.unbind-btn {
  background-color: rgba(255, 69, 58, 0.15);
  color: #ff453a;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
}

/* Club Management Card */
.club-card-highlight {
  border: 1rpx solid rgba(252, 76, 2, 0.3);
  background: linear-gradient(135deg, rgba(252, 76, 2, 0.08) 0%, #151518 100%);
}

.club-role-tag {
  font-size: 22rpx;
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

.role-member {
  background-color: rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}

.joined-club-box {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}

.club-mini-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-bottom: 16rpx;
}

.mini-logo {
  width: 80rpx;
  height: 80rpx;
  border-radius: 18rpx;
}

.mini-texts {
  flex: 1;
}

.mini-club-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
  display: block;
}

.mini-club-desc {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 6rpx;
  display: block;
  line-height: 1.3;
}

.invite-copy-row {
  display: flex;
  align-items: center;
  font-size: 24rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
  padding-top: 14rpx;
}

.invite-lbl {
  color: #8e8e93;
}

.invite-code {
  color: #fc4c02;
  font-weight: bold;
  font-family: monospace;
  font-size: 26rpx;
  margin-left: 6rpx;
}

.copy-action {
  color: #0a84ff;
  font-size: 22rpx;
  margin-left: 8rpx;
}

.empty-club-box {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}

.club-btn-grid {
  display: flex;
  gap: 20rpx;
}

.club-act-btn {
  flex: 1;
  height: 84rpx;
  line-height: 84rpx;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.club-act-btn.join-btn {
  background-color: #242429;
  color: #ffffff;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
}

.club-act-btn.create-btn {
  background: linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%);
  color: #ffffff;
  border: none;
}

/* Races */
.race-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.race-item {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 20rpx;
}

.race-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.race-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.race-badge {
  background-color: rgba(10, 132, 255, 0.15);
  color: #0a84ff;
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
  font-size: 20rpx;
  font-weight: bold;
}

.race-badge.urgent {
  background-color: rgba(252, 76, 2, 0.2);
  color: #fc4c02;
}

.race-meta-row {
  display: flex;
  gap: 16rpx;
  font-size: 20rpx;
  color: #8e8e93;
}

.race-type-tag {
  color: #fc4c02;
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
}

.pb-label {
  font-size: 20rpx;
  color: #8e8e93;
  display: block;
}

.pb-val {
  font-size: 28rpx;
  font-weight: bold;
  color: #fc4c02;
  font-family: monospace;
  margin-top: 6rpx;
  display: block;
}

.import-garmin-btn {
  font-size: 20rpx;
  font-weight: bold;
  background-color: rgba(255, 255, 255, 0.08);
  color: #ffffff;
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
  color: #8e8e93;
  margin-bottom: 8rpx;
}

.form-input {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  height: 72rpx;
  line-height: 72rpx;
  padding: 0 16rpx;
  font-size: 26rpx;
  color: #ffffff;
}

/* Target & Goal Planning */
.target-badge {
  font-size: 24rpx;
  font-weight: bold;
  color: #fc4c02;
  background-color: rgba(252, 76, 2, 0.1);
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
}

.target-badge.locked {
  color: #06b6d4;
  background-color: rgba(6, 182, 212, 0.1);
}

.goal-mode-selector {
  display: flex;
  background-color: #121214;
  border-radius: 18rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
  gap: 8rpx;
}

.goal-mode-btn {
  flex: 1;
  text-align: center;
  padding: 14rpx 0;
  font-size: 24rpx;
  color: #8e8e93;
  border-radius: 14rpx;
  transition: all 0.2s ease;
}

.goal-mode-btn.active {
  background-color: #242428;
  color: #ffffff;
  font-weight: bold;
}

.slider-wrapper {
  margin-bottom: 20rpx;
}

.locked-tip {
  font-size: 20rpx;
  color: #06b6d4;
  margin-top: 10rpx;
  text-align: center;
  display: block;
}

.uniform-tip {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 10rpx;
  text-align: center;
  display: block;
}

.custom-months-section {
  background-color: #121214;
  border-radius: 20rpx;
  padding: 20rpx;
  margin-top: 16rpx;
}

.custom-months-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.cm-title {
  font-size: 22rpx;
  color: #ffffff;
  font-weight: bold;
}

.sync-uniform-action {
  font-size: 20rpx;
  color: #fc4c02;
}

.months-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
}

.month-cell {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 14rpx;
  padding: 10rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.month-label {
  font-size: 20rpx;
  color: #8e8e93;
  margin-bottom: 4rpx;
}

.month-input {
  width: 100%;
  text-align: center;
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

/* Weekly Plan Section */
.weekly-plan-section {
  background-color: #121214;
  border-radius: 20rpx;
  padding: 24rpx 20rpx;
  margin-top: 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
}

.weekly-target-badge {
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
  color: #34d399;
  font-size: 22rpx;
  font-weight: bold;
  border-radius: 12rpx;
  padding: 4rpx 14rpx;
}

.weekly-desc-tip {
  font-size: 20rpx;
  color: #8e8e93;
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
  background: #1c1c20;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  font-size: 22rpx;
  font-weight: 600;
  color: #a1a1aa;
}

.weekly-pill.active {
  background: #10b981;
  border-color: #10b981;
  color: #ffffff;
  box-shadow: 0 4rpx 12rpx rgba(16, 185, 129, 0.4);
}

.weekly-save-action {
  margin-top: 20rpx;
  display: flex;
  justify-content: flex-end;
}

.save-weekly-btn {
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.4);
  color: #34d399;
  font-size: 22rpx;
  font-weight: bold;
  border-radius: 14rpx;
  padding: 12rpx 28rpx;
  line-height: 1.4;
  margin: 0;
}

.save-box {
  margin-top: 30rpx;
}

.save-btn {
  width: 100%;
  height: 84rpx;
  background: linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
}

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
  color: #0a84ff;
}

.modal-content {
  width: 670rpx;
  background-color: #18181c;
  border-radius: 36rpx;
  padding: 44rpx 40rpx;
  box-sizing: border-box;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  margin-bottom: 60rpx;
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

.center-input {
  text-align: center;
  font-size: 36rpx;
  font-family: monospace;
  font-weight: bold;
  color: #fc4c02;
  letter-spacing: 6rpx;
}

.large-textarea {
  width: 100%;
  height: 150rpx;
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 20rpx;
  padding: 20rpx 28rpx;
  font-size: 26rpx;
  color: #ffffff;
  box-sizing: border-box;
  margin-bottom: 12rpx;
}

.placeholder-style {
  color: #636366;
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
  background-color: #242429;
  color: #8e8e93;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
}

.domain-btn.active {
  background-color: #0a84ff;
  color: #ffffff;
  font-weight: bold;
  border-color: #0a84ff;
}

/* Multi-device & Brand Switcher Styling */
.brand-switch-row {
  display: flex;
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.brand-switch-btn {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  font-size: 26rpx;
  font-weight: 600;
  color: #8e8e93;
  border-radius: 14rpx;
  transition: all 0.2s ease;
}

.brand-switch-btn.active {
  background-color: #2c2c30;
  color: #ffffff;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.4);
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
  color: #0a84ff;
  border: 1rpx solid rgba(0, 122, 255, 0.3);
}

.coros-badge {
  background: rgba(252, 76, 2, 0.15);
  color: #fc4c02;
  border: 1rpx solid rgba(252, 76, 2, 0.3);
}

.device-name-text {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.coros-btn {
  background-color: #fc4c02 !important;
}

.coros-primary-btn {
  background-color: #fc4c02 !important;
}

.large-primary-btn {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  background-color: #fc4c02;
  color: #ffffff;
  font-size: 30rpx;
  font-weight: bold;
  border-radius: 24rpx;
  margin-top: 24rpx;
  border: none;
}

.large-wx-btn {
  width: 100%;
  height: 96rpx;
  background-color: #07c160;
  border-radius: 24rpx;
  margin-top: 24rpx;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
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
  color: #07c160;
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

.wx-hero-title {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
}

.wx-hero-desc {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 8rpx;
  display: block;
  line-height: 1.4;
}

.wx-account-status-card {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}

.status-title {
  font-size: 24rpx;
  color: #8e8e93;
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
  color: #636366;
}

.status-val {
  color: #ffffff;
  font-weight: bold;
}

.text-green {
  color: #07c160 !important;
}

.text-muted {
  color: #8e8e93 !important;
}

.wx-feature-bullets {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
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
  color: #d1d1d6;
}

.modal-outline-btn {
  width: 100%;
  height: 84rpx;
  line-height: 84rpx;
  background-color: transparent;
  color: #8e8e93;
  font-size: 26rpx;
  border-radius: 20rpx;
  margin-top: 20rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.user-badge-right {
  padding: 8rpx 16rpx;
  background-color: rgba(255, 255, 255, 0.08);
  border-radius: 12rpx;
}

.badge-text-right {
  font-size: 22rpx;
  color: #ff6b35;
  font-weight: bold;
}

/* ── Auth Flow Modal Styling ── */
.auth-flow-box {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.recent-accounts-section {
  background-color: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
}

.recent-title {
  font-size: 24rpx;
  color: #aeaeb2;
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
  background-color: #222227;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 16rpx;
  padding: 14rpx 20rpx;
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
  color: #ffffff;
}

.recent-acc-meta {
  font-size: 20rpx;
  color: #8e8e93;
}

.recent-acc-action {
  font-size: 22rpx;
  color: #00d2be;
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
  background-color: rgba(255, 255, 255, 0.1);
}

.divider-text {
  font-size: 20rpx;
  color: #636366;
}

.avatar-nickname-flex {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background-color: #1a1a1f;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 16rpx;
}

.wx-avatar-btn {
  width: 110rpx;
  height: 110rpx;
  border-radius: 55rpx;
  padding: 0;
  margin: 0;
  background-color: #2c2c34;
  border: 2rpx dashed rgba(7, 193, 96, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  line-height: normal;
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
  color: #07c160;
  display: block;
  margin-bottom: 8rpx;
}

.auth-intro-desc {
  font-size: 22rpx;
  color: #8e8e93;
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
  color: #8e8e93;
  line-height: 1.4;
}

.terms-text {
  color: #8e8e93;
}

.terms-link {
  color: #0a84ff;
  text-decoration: underline;
}

.confirm-auth-btn {
  width: 100%;
  height: 92rpx;
  line-height: 92rpx;
  background-color: #07c160;
  color: #ffffff;
  font-size: 30rpx;
  font-weight: bold;
  border-radius: 24rpx;
  border: none;
  margin-top: 10rpx;
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
  color: #ff9f0a;
  display: block;
  margin-bottom: 8rpx;
}

.mfa-alert-desc {
  font-size: 22rpx;
  color: #d1d1d6;
  line-height: 1.4;
  display: block;
}

.text-cancel-btn {
  background: transparent;
  color: #8e8e93;
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
  background: #fc4c02;
  border: 2rpx solid #141416;
  border-radius: 50%;
  width: 36rpx;
  height: 36rpx;
  display: flex;
  align-items: center;
  justify-content: center;
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
  color: #0a84ff;
  border: 1rpx solid rgba(10, 132, 255, 0.3);
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  font-weight: 600;
}

.edit-profile-modal {
  width: 660rpx;
  background-color: #161619;
  border-radius: 36rpx;
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
  border: 4rpx solid #fc4c02;
  box-shadow: 0 8rpx 24rpx rgba(252, 76, 2, 0.25);
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
  color: #07c160;
  border: 1rpx solid rgba(7, 193, 96, 0.35);
}

.avatar-sub-btn.album-pick {
  background: rgba(10, 132, 255, 0.15);
  color: #0a84ff;
  border: 1rpx solid rgba(10, 132, 255, 0.35);
}

.avatar-hint {
  font-size: 22rpx;
  color: #8e8e93;
  text-align: center;
  margin-top: 4rpx;
}

.edit-field-wrap {
  margin-bottom: 32rpx;
}

.edit-name-input {
  margin-top: 8rpx;
}

.input-hint {
  font-size: 22rpx;
  color: #636366;
  margin-top: 10rpx;
  display: block;
  line-height: 1.4;
}

.save-profile-btn {
  margin-top: 10rpx;
  background-color: #fc4c02;
}
</style>
