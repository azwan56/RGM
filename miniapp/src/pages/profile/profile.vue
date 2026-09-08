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
      <button class="switch-user-btn" @click.stop="handleConfirmLogout">退出登录</button>
    </view>

    <!-- ── CARD 1: 我的跑团与管理 (Running Club Card) ── -->
    <view class="section-card club-card-highlight">
      <view class="card-title-row">
        <view class="title-with-icon">
          <text class="title-icon">🏃</text>
          <text class="card-title">我的跑团与管理</text>
        </view>
        <text v-if="userClub" class="club-role-tag" :class="'role-' + (userClub.role || 'member')">
          {{ userClub.role === 'owner' ? '👑 跑团主理人' : userClub.role === 'coach' ? '🧢 认证教练' : '🏃 核心团员' }}
        </text>
        <text v-else class="club-role-tag role-none">
          未加入跑团
        </text>
      </view>

      <!-- Joined Club Summary -->
      <view v-if="userClub" class="joined-club-box">
        <view class="club-mini-info">
          <image class="mini-logo" :src="userClub.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
          <view class="mini-texts">
            <view class="club-title-row">
              <text class="club-title-text">{{ userClub.name }}</text>
              <text v-if="userClubs.length > 1" class="multi-club-badge">{{ userClubs.length }}个跑团</text>
            </view>
            <text class="club-desc-text">{{ userClub.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。" }}</text>
          </view>
        </view>
      </view>

      <!-- Unjoined Empty State -->
      <view v-else class="joined-club-box empty-club-box" style="padding: 28rpx; text-align: center;">
        <text style="font-size: 26rpx; color: #ffffff; font-weight: bold; display: block; margin-bottom: 8rpx;">尚未加入任何跑团</text>
        <text style="font-size: 22rpx; color: #8e8e93; display: block; line-height: 1.5;">前往跑团大本营浏览平台跑团并选择加入，与队友共同训练打卡！</text>
      </view>

      <!-- Club Action Buttons -->
      <view class="club-btn-grid">
        <button class="club-act-btn join-btn" @click="goToTeamPage">
          {{ userClubs.length > 1 ? `⇄ 切换跑团 (${userClubs.length})` : userClub ? '🏃 查看当前跑团' : '🏃 浏览与加入跑团' }}
        </button>
        <button class="club-act-btn create-btn" @click="showJoinModal = true">
          🔑 邀请码加入
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
            <view class="race-name-group">
              <text class="race-name">{{ race.name }}</text>
              <text class="race-priority-tag" :class="`p-tag-${race.priority == 1 || race.priority === 'A' ? 'a' : race.priority == 2 || race.priority === 'B' ? 'b' : 'c'}`">
                {{ race.priority == 1 || race.priority === 'A' ? 'A 标' : race.priority == 2 || race.priority === 'B' ? 'B 标' : 'C 标' }}
              </text>
            </view>
            <view class="race-badge" :class="{ urgent: race.days_left < 30 }">
              <text class="badge-text">{{ race.days_left }} 天{{ race.days_left < 30 ? " 冲刺" : "" }}</text>
            </view>
          </view>
          <view class="race-meta-row">
            <text class="race-type-tag">{{ race.race_type }}</text>
            <text class="race-date">{{ race.race_date }}</text>
            <text class="race-target">目标: {{ race.target_time }}</text>
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
        <button
          class="import-garmin-btn"
          :loading="syncingDeviceProfile"
          :disabled="syncingDeviceProfile || (!garminConnected && !corosConnected)"
          @click="handleSyncDeviceProfile"
        >
          从手表同步指标
        </button>
      </view>

      <text class="desc-text" style="margin-bottom: 20rpx;">
        Canova 教练根据年龄、性别、静息心率与最大摄氧量 (VO2Max) 智能自适应训练配速区间与超量恢复。
      </text>

      <view class="form-grid-2">
        <!-- 出生日期 & 动态年龄 -->
        <view class="form-group full-width-group">
          <view class="label-with-tag">
            <text class="label">出生日期 (Date of Birth)</text>
            <text v-if="displayAge !== null" class="age-badge-pill">
              {{ displayAge }} 岁 · {{ displayAge >= 50 ? '大师组 (50+)' : displayAge >= 40 ? '壮年大师组 (40+)' : '黄金年龄组' }}
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

        <!-- 生理性别 -->
        <view class="form-group">
          <text class="label">生理性别</text>
          <view class="gender-pill-group">
            <view
              class="gender-pill"
              :class="{ active: (profile?.gender || 'male') === 'male' }"
              @click="onGenderSelect('male')"
            >
              <text>♂ 男 (Male)</text>
            </view>
            <view
              class="gender-pill"
              :class="{ active: profile?.gender === 'female' }"
              @click="onGenderSelect('female')"
            >
              <text>♀ 女 (Female)</text>
            </view>
          </view>
        </view>

        <!-- 最大摄氧量 VO2Max -->
        <view class="form-group">
          <view class="label-with-tag">
            <text class="label">最大摄氧量 (VO2Max)</text>
            <text class="estimate-pill-btn" @click="handleEstimateVo2max">⚡ 依据 PB 测算</text>
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
      <button class="logout-btn" @click="handleConfirmLogout">退出登录</button>
    </view>

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
            <text class="wx-hero-icon">🏃</text>
            <text class="wx-hero-title">RGM 跑团助手</text>
            <text class="wx-hero-desc">科学耐力训练 · Garmin / COROS 手表直连</text>
          </view>

          <!-- 1. 当前已登录会话简况 -->
          <view v-if="user" class="wx-account-status-card">
            <view class="status-top-row">
              <view class="status-user-info">
                <text class="status-title">当前登录跑者：</text>
                <text class="status-val bold">{{ profile?.display_name || user.display_name || "微信跑者" }}</text>
                <text class="status-sub">({{ user.id }})</text>
              </view>
              <button class="status-logout-btn" @click="handleConfirmLogout">退出登录</button>
            </view>
            <view class="status-row" style="margin-top: 16rpx;">
              <text class="status-label">手表连接: </text>
              <text class="status-val text-green" v-if="garminConnected">佳明已绑定 ({{ garminEmail || '账号' }})</text>
              <text class="status-val text-green" v-else-if="corosConnected">高驰已绑定 ({{ corosAccount || '账号' }})</text>
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
                <text class="auth-intro-title">🛡️ 微信独立授权登录</text>
                <text class="auth-intro-desc">
                  系统将使用您当前的微信账号建立专属独立跑者档案。每个微信号独立隔离，绝不混淆他人数据。
                </text>
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
                🟢 授权并创建新跑者身份
              </button>
            </view>

            <!-- 模式 2: 已有手表账号验证登录 / 档案恢复 -->
            <view v-else class="auth-flow-box device-login-box">
              <view class="auth-intro-box">
                <text class="auth-intro-title">🔐 运动手表安全验证登录</text>
                <text class="auth-intro-desc">
                  已在平台拥有训练数据的跑者，可直接输入绑定的佳明或高驰手表账号密码。官方验证通过后，将自动恢复您的独立跑者档案。
                </text>
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
                    :class="{ active: deviceDomain === 'garmin.com' }"
                    @click="deviceDomain = 'garmin.com'"
                  >
                    <text>国际区 (.com)</text>
                  </view>
                  <view
                    class="domain-chip"
                    :class="{ active: deviceDomain === 'garmin.cn' }"
                    @click="deviceDomain = 'garmin.cn'"
                  >
                    <text>中国区 (.cn)</text>
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
                    :placeholder="deviceBrand === 'garmin' ? '例如 azwan56@hotmail.com' : '请输入高驰账号'"
                    placeholder-class="placeholder-style"
                    @input="deviceAccount = $event.detail.value"
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
              </view>

              <!-- 登录按钮 -->
              <button
                class="confirm-auth-btn device-confirm-btn"
                :loading="deviceLoggingIn"
                @click="doDeviceLogin"
              >
                🔐 验证账号并恢复跑者档案
              </button>
            </view>
          </view>
        </view>
        </scroll-view>
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
import { ref, computed } from "vue";
import { onShow } from "@dcloudio/uni-app";
import {
  request,
  getStoredUser,
  clearSession,
  authenticateWechatUser,
  deviceLogin,
  uploadAvatarFile,
  API_BASE_URL,
  UserProfile,
  bindCoros,
  unbindCoros,
  resolveActiveClub,
  setActiveClubId,
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
  gender: "male",
  date_of_birth: "",
  vo2max: null,
  years_running: 3,
  height: 175,
  weight: 65,
  max_heart_rate: 190,
  resting_heart_rate: 56,
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
const authTab = ref<"wechat" | "device">("wechat");
const deviceBrand = ref<"garmin" | "coros">("garmin");
const deviceAccount = ref("");
const devicePassword = ref("");
const deviceDomain = ref("garmin.com");
const deviceLoggingIn = ref(false);
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
const inviteCodeInput = ref("");
const joiningClub = ref(false);
const userClubs = ref<any[]>([]);

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
  showAuthModal.value = true;
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

async function doDeviceLogin() {
  const acc = deviceAccount.value.trim();
  const pwd = devicePassword.value.trim();
  if (!acc || !pwd) {
    uni.showToast({ title: "请输入手表账号和密码", icon: "none" });
    return;
  }
  deviceLoggingIn.value = true;
  uni.showLoading({ title: "正在验证手表账号...", mask: true });
  try {
    const domain = deviceBrand.value === "garmin" ? deviceDomain.value : "teamcnapi.coros.com";
    const logged = await deviceLogin({
      brand: deviceBrand.value,
      account: acc,
      password: pwd,
      domain: domain,
    });
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
    userClubs.value = clubs;
    userClub.value = resolveActiveClub(clubs);
  } catch (err) {
    console.error("Failed to load profile:", err);
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

function goToTeamPage() {
  uni.switchTab({
    url: "/pages/team/rank",
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
    await request(`/api/profile/${uid}`, "PUT", {
      max_heart_rate: profile.value?.max_heart_rate,
      resting_heart_rate: profile.value?.resting_heart_rate,
      height_cm: profile.value?.height || profile.value?.height_cm,
      weight_kg: profile.value?.weight || profile.value?.weight_kg,
      gender: profile.value?.gender,
      date_of_birth: profile.value?.date_of_birth,
      vo2max: profile.value?.vo2max !== undefined && profile.value?.vo2max !== null && profile.value?.vo2max !== "" ? Number(profile.value.vo2max) : null,
      years_running: profile.value?.years_running,
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

    uni.showToast({ title: "个人资料与目标已保存", icon: "success" });
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

.club-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 4rpx;
}

.multi-club-badge {
  font-size: 18rpx;
  color: #fc4c02;
  background: rgba(252, 76, 2, 0.15);
  border: 1rpx solid rgba(252, 76, 2, 0.3);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
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
  color: #fb7185;
  border: 1rpx solid rgba(244, 63, 94, 0.35);
}

.p-tag-b {
  background-color: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
  border: 1rpx solid rgba(56, 189, 248, 0.35);
}

.p-tag-c {
  background-color: rgba(161, 161, 170, 0.2);
  color: #d4d4d8;
  border: 1rpx solid rgba(161, 161, 170, 0.35);
}

.race-priority-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 14rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
}

.race-priority-lbl {
  font-size: 20rpx;
  color: #8e8e93;
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
  color: #a1a1aa;
  background-color: rgba(255, 255, 255, 0.05);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 8rpx;
}

.min-p-btn::after {
  border: none;
}

.min-p-btn.active:nth-child(1) {
  background-color: rgba(244, 63, 94, 0.25);
  color: #fb7185;
  border-color: #f43f5e;
  font-weight: bold;
}

.min-p-btn.active:nth-child(2) {
  background-color: rgba(56, 189, 248, 0.25);
  color: #38bdf8;
  border-color: #38bdf8;
  font-weight: bold;
}

.min-p-btn.active:nth-child(3) {
  background-color: rgba(161, 161, 170, 0.25);
  color: #e4e4e7;
  border-color: #a1a1aa;
  font-weight: bold;
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
  color: #fc4c02;
  background-color: rgba(252, 76, 2, 0.15);
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  border: 1rpx solid rgba(252, 76, 2, 0.3);
}

.estimate-pill-btn {
  font-size: 20rpx;
  color: #fc4c02;
  font-weight: bold;
  padding: 2rpx 8rpx;
}

.picker-input-box {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  height: 72rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16rpx;
  font-size: 26rpx;
  color: #ffffff;
}

.placeholder-text {
  color: #636366;
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
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  font-size: 24rpx;
  color: #8e8e93;
}

.gender-pill.active {
  background-color: rgba(252, 76, 2, 0.15);
  border-color: #fc4c02;
  color: #fc4c02;
  font-weight: bold;
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
  color: #ffb300;
}

.acc-badge.coach {
  background-color: rgba(0, 210, 190, 0.2);
  color: #00d2be;
}

.current-acc-tag {
  font-size: 22rpx;
  color: #10b981;
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
  color: #8e8e93;
}

.status-logout-btn {
  font-size: 22rpx;
  color: #ff453a;
  background: rgba(255, 69, 58, 0.12);
  border: 1rpx solid rgba(255, 69, 58, 0.3);
  border-radius: 12rpx;
  padding: 6rpx 16rpx;
  line-height: 1.4;
  margin: 0;
}

.recover-acc-box {
  background-color: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 18rpx 20rpx;
  margin-top: 16rpx;
  margin-bottom: 8rpx;
}

.recover-title {
  font-size: 22rpx;
  color: #aeaeb2;
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
  background-color: #1a1a1f;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 14rpx;
  padding: 0 16rpx;
  font-size: 24rpx;
  color: #ffffff;
}

.recover-btn {
  height: 68rpx;
  line-height: 68rpx;
  padding: 0 24rpx;
  font-size: 24rpx;
  color: #ffffff;
  background-color: #00d2be;
  border-radius: 14rpx;
  font-weight: bold;
  margin: 0;
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

/* Auth Modal Tabs & Device Login */
.auth-tab-row {
  display: flex;
  background: rgba(255, 255, 255, 0.06);
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
  color: #8e8e93;
  border-radius: 12rpx;
  transition: all 0.2s;
}

.auth-tab-item.active {
  background: #1c1c1e;
  color: #00d2be;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.3);
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
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #aeaeb2;
  border-radius: 14rpx;
}

.brand-tab-btn.active {
  border-color: #00d2be;
  background: rgba(0, 210, 190, 0.12);
  color: #00d2be;
}

.domain-select-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}

.domain-label {
  font-size: 22rpx;
  color: #8e8e93;
}

.domain-btn-wrap {
  display: flex;
  gap: 12rpx;
}

.domain-chip {
  padding: 8rpx 18rpx;
  font-size: 22rpx;
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}

.domain-chip.active {
  background: rgba(0, 210, 190, 0.15);
  border-color: #00d2be;
  color: #00d2be;
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
  background: linear-gradient(135deg, #00d2be, #00a896) !important;
  margin-top: 24rpx;
  margin-bottom: 24rpx;
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
</style>
