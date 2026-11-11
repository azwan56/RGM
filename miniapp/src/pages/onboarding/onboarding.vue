<template>
  <view class="onboarding-page" :class="themeClass">
    <!-- ── 顶部 4 步进度向导导航条 ── -->
    <view class="stepper-header">
      <view class="stepper-track">
        <view class="stepper-fill" :style="{ width: progressPercent + '%' }" />
      </view>
      <view class="steps-row">
        <view
          v-for="(st, idx) in stepTabs"
          :key="idx"
          class="step-item"
          :class="{ active: currentStep === idx + 1, completed: isStepCompleted(idx + 1) }"
          @click="canJumpTo(idx + 1) ? handleStepJump(idx + 1) : null"
        >
          <view class="step-circle">
            <text v-if="isStepCompleted(idx + 1) && currentStep !== idx + 1" class="check-icon">✓</text>
            <text v-else class="step-num">{{ idx + 1 }}</text>
          </view>
          <text class="step-label">{{ st }}</text>
        </view>
      </view>
      <view v-if="isAlreadyCompleted" class="stepper-edit-hint">
        <text class="seh-badge">✏️ 编辑模式</text>
        <text class="seh-text">点上方步骤可跳转修改</text>
      </view>
    </view>

    <!-- ── 步骤 1: 🏃 跑者名片与生理基线 (Profile & Identity) ── -->
    <view v-if="currentStep === 1" class="step-container">
      <view class="step-intro-box">
        <text class="step-badge">第 1 步 / 共 4 步</text>
        <text class="step-title">建立跑者名片</text>
      </view>

      <view class="form-card">
        <!-- 微信头像 + 微信昵称一键获取行 -->
        <view class="avatar-nick-row">
          <button
            class="wx-avatar-pick-btn"
            open-type="chooseAvatar"
            @chooseavatar="onChooseWechatAvatar"
          >
            <image
              class="wx-avatar-img"
              :src="profileForm.avatar_url || user?.avatar_url || defaultAvatar"
              mode="aspectFill"
            />
            <view class="wx-avatar-tag">📷 换头像</view>
          </button>

          <view class="nick-col">
            <text class="input-label">跑者昵称 *</text>
            <input
              class="text-input"
              type="nickname"
              placeholder="点击输入或选择微信昵称"
              placeholder-class="input-placeholder-class"
              v-model="profileForm.display_name"
              @blur="onNicknameBlur"
            />
          </view>
        </view>

        <!-- 性别选择 -->
        <view class="form-group">
          <text class="input-label">生理性别 *</text>
          <view class="segmented-control">
            <view
              class="seg-item"
              :class="{ active: profileForm.gender === 'male' }"
              @click="profileForm.gender = 'male'"
            >
              <text class="seg-txt">🚹 男跑者</text>
            </view>
            <view
              class="seg-item"
              :class="{ active: profileForm.gender === 'female' }"
              @click="profileForm.gender = 'female'"
            >
              <text class="seg-txt">🚺 女跑者</text>
            </view>
          </view>
        </view>

        <!-- 出生日期 -->
        <view class="form-group">
          <view class="label-row">
            <text class="input-label">出生日期 *</text>
            <text v-if="calculatedAge" class="sub-hint">
              {{ calculatedAge }} 岁 · {{ calculatedAgeGroup }} · 预估最大心率 {{ estimatedMaxHrByAge }} bpm
            </text>
          </view>
          <picker mode="date" :value="profileForm.date_of_birth || '1988-06-15'" @change="onDobChange">
            <view class="picker-display-box">
              <text class="picker-val">{{ profileForm.date_of_birth || "点击选择出生年月" }}</text>
              <text class="picker-arrow">📅 ›</text>
            </view>
          </picker>
        </view>

        <!-- 身高与体重（选填，默认折叠，减少首屏字段） -->
        <view v-if="!showBodyMetrics && !profileForm.height_cm && !profileForm.weight_kg" class="optional-toggle" @click="showBodyMetrics = true">
          <text class="optional-toggle-text">+ 补充身高 / 体重（选填）</text>
        </view>
        <view v-else class="form-row-2">
          <view class="form-group half">
            <text class="input-label">身高 (cm)</text>
            <input
              class="text-input"
              type="digit"
              placeholder="175"
              placeholder-class="input-placeholder-class"
              v-model="profileForm.height_cm"
            />
          </view>
          <view class="form-group half">
            <text class="input-label">体重 (kg)</text>
            <input
              class="text-input"
              type="digit"
              placeholder="65"
              placeholder-class="input-placeholder-class"
              v-model="profileForm.weight_kg"
            />
          </view>
        </view>
        <view v-if="calculatedBmi && (showBodyMetrics || profileForm.height_cm || profileForm.weight_kg)" class="bmi-badge-box">
          <text class="bmi-badge-text">BMI: {{ calculatedBmi }} ({{ bmiCategory }})</text>
        </view>
      </view>

      <view class="bottom-actions">
        <button v-if="isAlreadyCompleted" class="save-only-btn" :loading="savingStep1" @click="handleSaveStep1(false)">
          💾 仅保存本页修改
        </button>
        <button class="primary-step-btn" :loading="savingStep1" @click="handleSaveStep1(true)">
          下一步 ›
        </button>
      </view>
    </view>

    <!-- ── 步骤 2: ⚡ 跑力基线与心率 (Running Ability & Heart Rate) ── -->
    <view v-else-if="currentStep === 2" class="step-container">
      <view class="step-intro-box">
        <text class="step-badge">第 2 步 / 共 4 步</text>
        <text class="step-title">校准跑力与心率</text>
      </view>

      <view class="form-card">
        <!-- 跑步年限 / 经验 -->
        <view class="form-group">
          <text class="input-label">跑步经验</text>
          <view class="chips-selector">
            <view
              v-for="exp in experienceOptions"
              :key="exp.val"
              class="exp-chip"
              :class="{ active: profileForm.years_running === exp.val }"
              @click="profileForm.years_running = exp.val"
            >
              <text class="exp-title">{{ exp.label }}</text>
              <text class="exp-sub">{{ exp.sub }}</text>
            </view>
          </view>
        </view>

        <!-- 代表性最好成绩 (选填 1 项自动算 VDOT) -->
        <view class="form-group">
          <view class="label-row">
            <text class="input-label">最好成绩 PB（选填）</text>
          </view>
          <view class="chips-row" style="margin-bottom: 16rpx;">
            <view
              v-for="dt in pbDistanceTabs"
              :key="dt.key"
              class="target-chip"
              :class="{ active: activePbTab === dt.key }"
              @click="activePbTab = dt.key"
            >
              <text>{{ dt.label }}</text>
            </view>
          </view>

          <!-- 快捷成绩胶囊 -->
          <view class="chips-row" style="margin-bottom: 16rpx;">
            <view
              v-for="preset in currentPbPresets"
              :key="preset.val"
              class="pb-preset-pill"
              :class="{ active: currentPbInput === preset.val }"
              @click="applyPbPreset(preset.val)"
            >
              <text>{{ preset.label }}</text>
            </view>
          </view>

          <input
            class="text-input"
            type="text"
            :placeholder="currentPbPlaceholder"
            placeholder-class="input-placeholder-class"
            :value="currentPbInput"
            @input="onPbTextInput"
          />
        </view>

        <!-- 实时 VDOT 与有氧配速预览卡 -->
        <view v-if="estimatedVdotInfo" class="vdot-preview-card">
          <view class="vpc-left">
            <text class="vpc-badge">⚡ 跑力</text>
            <text class="vpc-vdot">VDOT {{ estimatedVdotInfo.vdot }}</text>
          </view>
          <view class="vpc-right">
            <text class="vpc-pace-lbl">轻松跑 E 配速</text>
            <text class="vpc-pace-val">{{ estimatedVdotInfo.easyPace }}</text>
          </view>
        </view>

        <!-- 静息心率与最大心率 -->
        <view class="form-row-2" style="margin-top: 10rpx;">
          <view class="form-group half">
            <text class="input-label">静息心率 (bpm)</text>
            <input
              class="text-input"
              type="number"
              placeholder="如 56 (选填)"
              placeholder-class="input-placeholder-class"
              v-model="profileForm.resting_heart_rate"
            />
          </view>
          <view class="form-group half">
            <text class="input-label">最大心率 (bpm)</text>
            <input
              class="text-input"
              type="number"
              :placeholder="String(estimatedMaxHrByAge)"
              placeholder-class="input-placeholder-class"
              v-model="profileForm.max_heart_rate"
            />
          </view>
        </view>
      </view>

      <view class="bottom-nav-row">
        <button class="nav-prev-btn" @click="currentStep = 1">‹ 上一步</button>
        <button class="nav-next-btn" :loading="savingStep2" @click="handleSaveStep2">
          下一步 ›
        </button>
      </view>
    </view>

    <!-- ── 步骤 3: ⌚ 手表连接与数据保密设置 (Watch & Privacy) ── -->
    <view v-else-if="currentStep === 3" class="step-container">
      <view class="step-intro-box">
        <text class="step-badge">第 3 步 / 共 4 步</text>
        <text class="step-title">连接手表与隐私设定</text>
      </view>

      <!-- 24小时全天佩戴手表重要提示 -->
      <view style="background: rgba(245, 158, 11, 0.14); border: 1rpx solid rgba(245, 158, 11, 0.45); border-radius: 16rpx; padding: 18rpx 22rpx; margin-bottom: 22rpx;">
        <text style="display: block; font-size: 25rpx; font-weight: 700; color: #b45309; margin-bottom: 6rpx;">
          ⌚ 请 24 小时佩戴手表（含睡眠）
        </text>
        <text style="display: block; font-size: 23rpx; line-height: 1.55; color: #92400e;">
          仅跑步时佩戴会缺失夜间 HRV 与睡眠恢复数据。
        </text>
      </view>

      <!-- ── Part A: 5 大运动手表品牌胶囊选择器（点选哪一个才展开对应卡片） ── -->
      <view class="watch-selector-card">
        <text class="wsc-title">⌚ 选择手表品牌（选填）</text>
        <view class="watch-brand-grid">
          <view
            v-for="wb in watchBrandTabs"
            :key="wb.key"
            class="watch-brand-pill"
            :class="{ active: selectedWatchBrand === wb.key, connected: isBrandConnected(wb.key) }"
            @click="selectedWatchBrand = wb.key"
          >
            <text class="wbp-name">{{ wb.label }}</text>
            <text v-if="isBrandConnected(wb.key)" class="wbp-sub">✓ 已连接</text>
          </view>
        </view>
      </view>

      <!-- 1. Garmin Connect 绑定卡片 -->
      <view v-if="selectedWatchBrand === 'garmin'" class="device-bind-card">
        <view class="dbc-header">
          <view class="dbc-left">
            <text class="device-brand-badge garmin">Garmin</text>
            <text class="dbc-title">佳明直连</text>
          </view>
          <text class="dbc-status" :class="{ connected: isGarminConnected }">
            {{ isGarminConnected ? '✓ 已直连' : '未连接' }}
          </text>
        </view>

        <view v-if="!isGarminConnected" class="dbc-body">
          <view class="form-group">
            <text class="input-label">佳明服务器区域</text>
            <view class="segmented-control mini">
              <view
                class="seg-item"
                :class="{ active: garminDomain === 'garmin.cn' }"
                @click="garminDomain = 'garmin.cn'"
              >
                <text class="seg-txt">中国区 (garmin.cn)</text>
              </view>
              <view
                class="seg-item"
                :class="{ active: garminDomain === 'garmin.com' }"
                @click="garminDomain = 'garmin.com'"
              >
                <text class="seg-txt">国际区 (garmin.com)</text>
              </view>
            </view>
          </view>
          <view class="form-group">
            <text class="input-label">佳明 Connect 登录邮箱</text>
            <input class="text-input" type="text" placeholder="例如: runner@garmin.cn" placeholder-class="input-placeholder-class" v-model="garminEmail" />
          </view>
          <view class="form-group">
            <text class="input-label">佳明 Connect 登录密码</text>
            <input class="text-input" password type="text" placeholder="请输入密码" placeholder-class="input-placeholder-class" v-model="garminPassword" />
          </view>
          <button class="dbc-bind-btn garmin-btn" :loading="bindingGarmin" @click="handleBindGarmin">
            一键直连 Garmin
          </button>
        </view>
        <view v-else class="dbc-connected-tip">
          <text class="tip-txt">✓ 已直连，数据将自动同步</text>
        </view>
      </view>

      <!-- 2. COROS 高驰绑定卡片 -->
      <view v-else-if="selectedWatchBrand === 'coros'" class="device-bind-card">
        <view class="dbc-header">
          <view class="dbc-left">
            <text class="device-brand-badge coros">COROS</text>
            <text class="dbc-title">高驰直连</text>
          </view>
          <text class="dbc-status" :class="{ connected: isCorosConnected }">
            {{ isCorosConnected ? '✓ 已直连' : '未连接' }}
          </text>
        </view>

        <view v-if="!isCorosConnected" class="dbc-body">
          <view class="form-group">
            <text class="input-label">高驰账号 (手机号或邮箱)</text>
            <input class="text-input" type="text" placeholder="请输入高驰账号" placeholder-class="input-placeholder-class" v-model="corosAccount" />
          </view>
          <view class="form-group">
            <text class="input-label">高驰登录密码</text>
            <input class="text-input" password type="text" placeholder="请输入密码" placeholder-class="input-placeholder-class" v-model="corosPassword" />
          </view>
          <button class="dbc-bind-btn coros-btn" :loading="bindingCoros" @click="handleBindCoros">
            一键直连 COROS
          </button>
        </view>
        <view v-else class="dbc-connected-tip">
          <text class="tip-txt">✓ 已直连，数据将自动同步</text>
        </view>
      </view>

      <!-- 3. 苹果 / 华为 / 颂拓（非直连 · 截图或轨迹导入） -->
      <view v-else class="device-bind-card">
        <view class="dbc-header">
          <view class="dbc-left">
            <text class="device-brand-badge apple">苹果 / 华为 / 颂拓</text>
            <text class="dbc-title">截图或轨迹导入</text>
          </view>
          <text class="dbc-status" :class="{ connected: isAppleWatchConnected || isHuaweiConnected || isSuuntoConnected }">
            {{ (isAppleWatchConnected || isHuaweiConnected || isSuuntoConnected) ? '✓ 已连接' : '未连接' }}
          </text>
        </view>

        <view v-if="!(isAppleWatchConnected || isHuaweiConnected || isSuuntoConnected)" class="dbc-body">
          <button
            class="dbc-bind-btn apple-btn"
            style="width: 100%; margin-bottom: 14rpx;"
            :loading="!!importingScreenshotBrand"
            @click="handleImportWatchScreenshot('apple_watch')"
          >
            📸 选运动截图一键导入
          </button>
          <view class="dbc-action-row">
            <button class="dbc-bind-btn secondary-btn flex-1" :loading="!!bindingHealthWatch" @click="handleBindHealthWatch('apple_watch')">
              ⌚ 标记连接
            </button>
            <button class="dbc-bind-btn secondary-btn flex-1" :loading="!!importingTrackBrand" @click="handleImportWatchTrack('apple_watch')">
              📂 微信导入 FIT/GPX/TCX
            </button>
          </view>
        </view>
        <view v-else class="dbc-connected-tip">
          <view class="dbc-tip-row">
            <text class="tip-txt">✓ 已激活</text>
            <button class="dbc-mini-import-btn" :loading="!!importingScreenshotBrand" @click="handleImportWatchScreenshot('apple_watch')">
              📸 选截图导入
            </button>
          </view>
        </view>
      </view>

      <!-- 已连接 Garmin/COROS：一键同步历史记录 -->
      <view v-if="isGarminConnected || isCorosConnected" class="sync-history-card">
        <view class="shc-header">
          <text class="shc-icon">🔄</text>
          <view class="shc-meta">
            <text class="shc-title">同步历史数据</text>
            <text class="shc-desc">已收录 {{ existingActivityCount }} 条</text>
          </view>
        </view>
        <view class="range-selector">
          <view
            v-for="r in syncRanges"
            :key="r.days"
            class="range-pill"
            :class="{ active: selectedRangeDays === r.days }"
            @click="selectedRangeDays = r.days"
          >
            <text>{{ r.label }}</text>
          </view>
        </view>
        <button class="sync-start-btn" :loading="syncingHistory" @click="handleStartHistorySync">
          {{ syncingHistory ? "同步中..." : "拉取历史数据" }}
        </button>
        <view v-if="syncedCount !== null" class="sync-result-badge">
          <text>✓ 已导入 {{ syncedCount }} 条</text>
        </view>
      </view>

      <!-- ── Part B: 🔒 数据保密与隐私开放权限（仅对教练和师傅开放） ── -->
      <view class="privacy-settings-card">
        <view class="psc-header">
          <text class="psc-title">🔒 数据保密设置</text>
          <text class="psc-badge">仅对教练和师傅开放</text>
        </view>

        <view class="privacy-toggle-row" @click="profileForm.hide_gps_route = !profileForm.hide_gps_route">
          <view class="ptr-left">
            <text class="ptr-title">🗺️ GPS 路线保密</text>
          </view>
          <switch
            :checked="profileForm.hide_gps_route"
            color="#FC4C02"
            @change="(e: any) => profileForm.hide_gps_route = Boolean(e.detail.value)"
            @click.stop
          />
        </view>

        <view class="privacy-toggle-row" style="border-top: 1rpx solid rgba(255,255,255,0.08); padding-top: 20rpx; margin-top: 16rpx;" @click="profileForm.hide_biometrics = !profileForm.hide_biometrics">
          <view class="ptr-left">
            <text class="ptr-title">💓 心率 / HRV / 睡眠数据保密</text>
          </view>
          <switch
            :checked="profileForm.hide_biometrics"
            color="#FC4C02"
            @change="(e: any) => profileForm.hide_biometrics = Boolean(e.detail.value)"
            @click.stop
          />
        </view>
      </view>

      <view class="bottom-nav-row">
        <button class="nav-prev-btn" @click="currentStep = 2">‹ 上一步</button>
        <button class="nav-next-btn" @click="handleFinishDeviceStep">
          下一步 ›
        </button>
      </view>
    </view>

    <!-- ── 步骤 4: 🎯 月跑量目标与重点赛事 (Goals & Target Race) ── -->
    <view v-else-if="currentStep === 4" class="step-container">
      <view class="step-intro-box">
        <text class="step-badge">第 4 步 / 共 4 步</text>
        <text class="step-title">设定跑量与赛事</text>
      </view>

      <view class="form-card">
        <!-- 月度跑量目标 -->
        <view class="form-group">
          <view class="label-row">
            <text class="input-label">月度跑量目标 (km) *</text>
            <text class="target-highlight">{{ targetKm }} km / 月</text>
          </view>
          <slider
            :value="targetKm"
            :min="50"
            :max="600"
            :step="10"
            activeColor="#FC4C02"
            backgroundColor="rgba(255,255,255,0.1)"
            block-color="#ffffff"
            block-size="20"
            @change="(e: any) => targetKm = e.detail.value"
          />
          <view class="chips-row">
            <view
              v-for="p in [100, 150, 200, 250, 300, 400]"
              :key="p"
              class="target-chip"
              :class="{ active: targetKm === p }"
              @click="targetKm = p"
            >
              <text>{{ p }}k</text>
            </view>
          </view>
        </view>

        <!-- 目标赛事快捷胶囊 + 输入 (可选) -->
        <view class="form-group" style="margin-top: 20rpx;">
          <text class="input-label">目标赛事（选填）</text>
          <view class="chips-row" style="margin-bottom: 14rpx;">
            <view
              v-for="rp in quickRacePresets"
              :key="rp.name"
              class="pb-preset-pill"
              :class="{ active: raceName === rp.name }"
              @click="applyQuickRacePreset(rp)"
            >
              <text>{{ rp.label }}</text>
            </view>
          </view>
          <input
            class="text-input"
            type="text"
            placeholder="例如: 第21届玄奘之路戈壁挑战赛 / 2026 上海马拉松"
            placeholder-class="input-placeholder-class"
            v-model="raceName"
          />
        </view>

        <view v-if="raceName.trim()" class="form-group">
          <text class="input-label">比赛类型</text>
          <view class="chips-row">
            <view
              v-for="t in onboardingRaceTypes"
              :key="t"
              class="target-chip"
              :class="{ active: raceType === t }"
              @click="raceType = t"
            >
              <text>{{ t }}</text>
            </view>
          </view>
        </view>

        <view class="form-row-2">
          <view class="form-group half">
            <text class="input-label">比赛日期</text>
            <picker mode="date" :value="raceDate" @change="(e: any) => raceDate = e.detail.value">
              <view class="picker-display-box mini">
                <text class="picker-val">{{ raceDate || "请选择" }}</text>
              </view>
            </picker>
          </view>
          <view class="form-group half">
            <text class="input-label">目标完赛时间 (选填)</text>
            <input
              class="text-input"
              type="text"
              placeholder="如 3:45:00"
              placeholder-class="input-placeholder-class"
              v-model="raceTargetTime"
            />
          </view>
        </view>
      </view>

      <view class="bottom-nav-row">
        <button class="nav-prev-btn" @click="currentStep = 3">‹ 上一步</button>
        <button class="nav-next-btn finish-btn" :loading="finishingAll" @click="handleFinishAll">
          🎉 完成设定
        </button>
      </view>
    </view>

    <!-- ── 完成页: 🏆 完成祝贺与概览卡片 (Success) ── -->
    <view v-else-if="currentStep === 5" class="step-container">
      <view class="success-card">
        <view class="confetti-icon">🏆</view>
        <text class="success-title">跑者档案已就绪</text>

        <view class="summary-box">
          <view class="summary-item">
            <text class="si-label">跑者昵称</text>
            <text class="si-val highlight">{{ profileForm.display_name }}</text>
          </view>
          <view v-if="estimatedVdotInfo" class="summary-item">
            <text class="si-label">跑力与轻松跑配速</text>
            <text class="si-val green">VDOT {{ estimatedVdotInfo.vdot }} · {{ estimatedVdotInfo.easyPace }}</text>
          </view>
          <view class="summary-item">
            <text class="si-label">手表连接</text>
            <text class="si-val" :class="{ green: isAnyWatchConnected }">
              {{ connectedWatchSummary }}
            </text>
          </view>
          <view class="summary-item">
            <text class="si-label">数据保密设定</text>
            <text class="si-val">
              {{ (profileForm.hide_gps_route || profileForm.hide_biometrics) ? '🔒 仅对教练和师傅开放' : '🌐 跑团内正常展示' }}
            </text>
          </view>
          <view class="summary-item">
            <text class="si-label">月跑量目标</text>
            <text class="si-val highlight">{{ targetKm }} km / 月</text>
          </view>
        </view>

        <view class="success-actions">
          <button class="success-btn primary" @click="goToTeam">
            {{ joinedClubName ? '🏃 进入我的跑团 ›' : '🏃 进入跑团 ›' }}
          </button>
          <button class="success-btn secondary" @click="goToHome">
            🏠 返回首页
          </button>
          <button class="success-btn tertiary" @click="currentStep = 1">
            ✏️ 修改资料
          </button>
        </view>
      </view>
    </view>

  </view>
</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme } from "@/utils/theme";
import { ref, computed, watch, onMounted } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import {
  request,
  getStoredUser,
  authenticateWechatUser,
  bindHealthWatch,
  chooseAndImportTrackFile,
  chooseAndImportScreenshot,
  uploadAvatarFile
} from "@/utils/api";
import { trackSubView, trackFunnelStep } from "@/utils/telemetry";

const defaultAvatar = "/static/logo-square.png";
const user = ref<any>(null);
const currentStep = ref<number>(1);
// 4 步分步引导：1.跑者名片 / 2.跑力心率 / 3.手表与隐私 / 4.目标赛事；第 5 屏为完成页
const stepTabs = ["跑者名片", "跑力心率", "手表与隐私", "目标赛事"];

watch(currentStep, (step) => {
  const stepNames: Record<number, string> = {
    1: "第1步：建立跑者名片",
    2: "第2步：跑力与心率基线",
    3: "第3步：连接运动手表与隐私",
    4: "第4步：跑量目标与备战赛事",
    5: "第5步：引导完成页",
  };
  trackSubView(`onboarding_step_${step}`, `新手引导 → ${stepNames[step] || `第${step}步`}`, { step });
});
const isAlreadyCompleted = ref(false);
const existingActivityCount = ref(0);

const progressPercent = computed(() => {
  return Math.min(100, Math.round(((currentStep.value - 1) / stepTabs.length) * 100));
});

const onboardingStepsState = ref<Record<string, boolean>>({
  profile: false,
  ability: false,
  club: false,
  device: false,
  history: false,
  goals: false
});
// 身高体重默认折叠（选填）
const showBodyMetrics = ref(false);

function isStepCompleted(stepNum: number) {
  const keyMap: Record<number, string> = {
    1: "profile",
    2: "ability",
    3: "device",
    4: "goals"
  };
  const key = keyMap[stepNum];
  if (key && onboardingStepsState.value[key]) return true;
  return currentStep.value > stepNum;
}

function canJumpTo(step: number) {
  if (step < 1 || step > stepTabs.length) return false;
  if (isAlreadyCompleted.value) return true;
  if (step <= currentStep.value) return true;
  if (step === currentStep.value + 1) return true;
  if (onboardingStepsState.value.profile) return true;
  return true;
}

function handleStepJump(step: number) {
  currentStep.value = step;
}

// ── Step 1 & Step 2: Profile & Running Ability State ──
const profileForm = ref({
  display_name: "",
  avatar_url: "",
  gender: "male",
  date_of_birth: "",
  height_cm: "" as number | string,
  weight_kg: "" as number | string,
  years_running: 2,
  resting_heart_rate: "" as number | string,
  max_heart_rate: "" as number | string,
  marathon_pb_str: "",
  half_pb_str: "",
  ten_k_pb_str: "",
  five_k_pb_str: "",
  hide_gps_route: false,
  hide_biometrics: false
});
const savingStep1 = ref(false);
const savingStep2 = ref(false);

const experienceOptions = [
  { val: 1, label: "跑步新手", sub: "< 1 年" },
  { val: 2, label: "稳定进阶", sub: "1 - 3 年" },
  { val: 3, label: "资深跑友", sub: "3 - 5 年" },
  { val: 5, label: "老戈/大神", sub: "> 5 年" }
];

const pbDistanceTabs = [
  { key: "marathon", label: "全马 PB" },
  { key: "half", label: "半马 PB" },
  { key: "10k", label: "10公里 PB" },
  { key: "5k", label: "5公里 PB" }
];
const activePbTab = ref<"marathon" | "half" | "10k" | "5k">("half");

const pbPresetsMap: Record<string, Array<{ label: string; val: string }>> = {
  marathon: [
    { label: "3:00 破三", val: "3:00:00" },
    { label: "3:30 精英", val: "3:30:00" },
    { label: "4:00 破四", val: "4:00:00" },
    { label: "4:30 完赛", val: "4:30:00" },
    { label: "5:00 关门内", val: "5:00:00" }
  ],
  half: [
    { label: "1:25 精英", val: "1:25:00" },
    { label: "1:40 进阶", val: "1:40:00" },
    { label: "1:55 破二", val: "1:55:00" },
    { label: "2:10 稳健", val: "2:10:00" },
    { label: "2:30 完赛", val: "2:30:00" }
  ],
  "10k": [
    { label: "40分", val: "40:00" },
    { label: "45分", val: "45:00" },
    { label: "50分", val: "50:00" },
    { label: "55分", val: "55:00" },
    { label: "60分", val: "1:00:00" }
  ],
  "5k": [
    { label: "19分", val: "19:00" },
    { label: "22分", val: "22:00" },
    { label: "25分", val: "25:00" },
    { label: "28分", val: "28:00" },
    { label: "30分", val: "30:00" }
  ]
};

const currentPbPresets = computed(() => pbPresetsMap[activePbTab.value] || []);
const currentPbPlaceholder = computed(() => {
  if (activePbTab.value === "marathon") return "如 3:45:00 (时:分:秒)";
  if (activePbTab.value === "half") return "如 1:48:00 (时:分:秒)";
  if (activePbTab.value === "10k") return "如 48:30 (分:秒)";
  return "如 23:30 (分:秒)";
});

const currentPbInput = computed(() => {
  if (activePbTab.value === "marathon") return profileForm.value.marathon_pb_str;
  if (activePbTab.value === "half") return profileForm.value.half_pb_str;
  if (activePbTab.value === "10k") return profileForm.value.ten_k_pb_str;
  return profileForm.value.five_k_pb_str;
});

function applyPbPreset(val: string) {
  if (activePbTab.value === "marathon") profileForm.value.marathon_pb_str = val;
  else if (activePbTab.value === "half") profileForm.value.half_pb_str = val;
  else if (activePbTab.value === "10k") profileForm.value.ten_k_pb_str = val;
  else profileForm.value.five_k_pb_str = val;
}

function onPbTextInput(e: any) {
  const val = e.detail?.value ?? "";
  applyPbPreset(val);
}

function parseTimeStrToSeconds(s: string): number {
  const clean = (s || "").trim();
  if (!clean) return 0;
  const parts = clean.split(":").map((p) => parseInt(p, 10));
  if (parts.some((n) => isNaN(n))) return 0;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

function secondsToTimeStr(sec: number): string {
  if (!sec || sec <= 0) return "";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatSecPerKm(secPerKm: number): string {
  const m = Math.floor(secPerKm / 60);
  const s = Math.round(secPerKm % 60);
  return `${m}'${String(s).padStart(2, "0")}"`;
}

const estimatedVdotInfo = computed(() => {
  const fmSec = parseTimeStrToSeconds(profileForm.value.marathon_pb_str);
  const hmSec = parseTimeStrToSeconds(profileForm.value.half_pb_str);
  const tenSec = parseTimeStrToSeconds(profileForm.value.ten_k_pb_str);
  const fiveSec = parseTimeStrToSeconds(profileForm.value.five_k_pb_str);

  let eqMarathonSec = 0;
  if (fmSec >= 7200) eqMarathonSec = fmSec;
  else if (hmSec >= 3300) eqMarathonSec = hmSec * 2.1;
  else if (tenSec >= 1500) eqMarathonSec = tenSec * 4.65;
  else if (fiveSec >= 720) eqMarathonSec = fiveSec * 9.75;
  if (!eqMarathonSec) return null;

  // Approximate Daniels VDOT from equivalent marathon seconds
  const mpSecPerKm = eqMarathonSec / 42.195;
  const vdot = Math.max(28, Math.min(82, Math.round((480 / mpSecPerKm) * 32.5 * 10) / 10));
  const easyFast = Math.round(mpSecPerKm + 38);
  const easySlow = Math.round(mpSecPerKm + 65);
  return {
    vdot: vdot.toFixed(1),
    easyPace: `${formatSecPerKm(easyFast)} ~ ${formatSecPerKm(easySlow)}/km`
  };
});

const calculatedAge = computed(() => {
  if (!profileForm.value.date_of_birth) return null;
  const birthYear = parseInt(profileForm.value.date_of_birth.substring(0, 4));
  if (isNaN(birthYear)) return null;
  return new Date().getFullYear() - birthYear;
});

const estimatedMaxHrByAge = computed(() => {
  const age = calculatedAge.value || 35;
  return Math.max(150, Math.min(205, 220 - age));
});

const calculatedAgeGroup = computed(() => {
  const a = calculatedAge.value;
  if (!a) return "";
  if (a < 30) return "青年组";
  if (a < 40) return "30+组";
  if (a < 50) return "40+组";
  return "50+大师组";
});

const calculatedBmi = computed(() => {
  const h = Number(profileForm.value.height_cm) / 100;
  const w = Number(profileForm.value.weight_kg);
  if (!h || !w || h <= 0 || w <= 0) return null;
  return (w / (h * h)).toFixed(1);
});

const bmiCategory = computed(() => {
  const bmi = Number(calculatedBmi.value);
  if (!bmi) return "";
  if (bmi < 18.5) return "偏瘦";
  if (bmi < 24) return "标准";
  if (bmi < 28) return "微胖";
  return "超重";
});

function onDobChange(e: any) {
  profileForm.value.date_of_birth = e.detail.value;
}

function onNicknameBlur(e: any) {
  const val = e.detail?.value;
  if (val && val.trim()) {
    profileForm.value.display_name = val.trim();
  }
}

async function onChooseWechatAvatar(e: any) {
  const tempPath = e.detail?.avatarUrl;
  if (!tempPath) return;
  profileForm.value.avatar_url = tempPath;
  const uid = user.value?.id;
  if (!uid) return;
  try {
    uni.showLoading({ title: "上传头像中...", mask: true });
    const uploadedUrl = await uploadAvatarFile(uid, tempPath);
    uni.hideLoading();
    if (uploadedUrl) {
      profileForm.value.avatar_url = uploadedUrl;
      if (user.value) {
        user.value.avatar_url = uploadedUrl;
        try {
          uni.setStorageSync("rgm_user", JSON.stringify(user.value));
        } catch (_) {}
      }
      uni.showToast({ title: "微信头像已同步", icon: "success" });
    }
  } catch (err: any) {
    uni.hideLoading();
    uni.showToast({ title: "头像已暂存", icon: "none" });
  }
}

async function handleSaveStep1(advance: boolean = true) {
  if (!profileForm.value.display_name.trim()) {
    uni.showToast({ title: "请填写跑者昵称", icon: "none" });
    return;
  }
  savingStep1.value = true;
  try {
    const uid = user.value?.id;
    if (uid) {
      const payload: Record<string, any> = {
        display_name: profileForm.value.display_name.trim(),
        gender: profileForm.value.gender,
        date_of_birth: profileForm.value.date_of_birth
      };
      if (profileForm.value.avatar_url && profileForm.value.avatar_url.startsWith("http")) {
        payload.avatar_url = profileForm.value.avatar_url;
      }
      const h = Number(profileForm.value.height_cm);
      const w = Number(profileForm.value.weight_kg);
      if (h > 0) payload.height_cm = h;
      if (w > 0) payload.weight_kg = w;
      await request(`/api/profile/${uid}`, "PUT", payload);
      if (user.value) {
        user.value.display_name = profileForm.value.display_name.trim();
        try {
          uni.setStorageSync("rgm_user", JSON.stringify(user.value));
        } catch (_) {}
      }
    }
    onboardingStepsState.value.profile = true;
    uni.showToast({ title: "跑者名片已保存", icon: "success" });
    if (advance) {
      currentStep.value = 2;
    }
  } catch (err: any) {
    uni.showToast({ title: err?.message || err?.detail || "保存资料失败", icon: "none" });
  } finally {
    savingStep1.value = false;
  }
}

async function handleSaveStep2() {
  savingStep2.value = true;
  try {
    const uid = user.value?.id;
    if (uid) {
      const payload: Record<string, any> = {};
      const y = Number(profileForm.value.years_running);
      if (y > 0) payload.years_running = y;

      const rhr = Number(profileForm.value.resting_heart_rate);
      const mhr = Number(profileForm.value.max_heart_rate) || estimatedMaxHrByAge.value;
      if (rhr > 30 && rhr < 120) payload.resting_heart_rate = rhr;
      if (mhr > 120 && mhr < 230) payload.max_heart_rate = mhr;

      const fmSec = parseTimeStrToSeconds(profileForm.value.marathon_pb_str);
      const hmSec = parseTimeStrToSeconds(profileForm.value.half_pb_str);
      const tenSec = parseTimeStrToSeconds(profileForm.value.ten_k_pb_str);
      const fiveSec = parseTimeStrToSeconds(profileForm.value.five_k_pb_str);
      if (fmSec > 0) payload.marathon_pb = fmSec;
      if (hmSec > 0) payload.half_pb = hmSec;
      if (tenSec > 0) payload.ten_k_pb = tenSec;
      if (fiveSec > 0) payload.five_k_pb = fiveSec;
      if (estimatedVdotInfo.value?.vdot) {
        payload.vo2max = Number(estimatedVdotInfo.value.vdot);
      }

      if (Object.keys(payload).length > 0) {
        await request(`/api/profile/${uid}`, "PUT", payload);
      }
    }
    onboardingStepsState.value.ability = true;
    currentStep.value = 3;
  } catch (err: any) {
    uni.showToast({ title: err?.message || err?.detail || "保存失败", icon: "none" });
  } finally {
    savingStep2.value = false;
  }
}

// ── 跑团（保留回填状态：完成页展示 / 提交 is_solo_runner）──
const isSoloRunnerSelected = ref(false);
const joinedClubId = ref<string | null>(null);
const joinedClubName = ref<string>("");

// ── Step 3: Device State & Data Confidentiality ──
const watchBrandTabs = [
  { key: "garmin", label: "Garmin 佳明", sub: "云端自动直连" },
  { key: "coros", label: "COROS 高驰", sub: "云端自动直连" },
  { key: "apple_watch", label: "苹果 / 华为 / 颂拓", sub: "截图/轨迹导入" },
];
const selectedWatchBrand = ref<string>("garmin");

function isBrandConnected(brandKey: string): boolean {
  if (brandKey === "garmin") return isGarminConnected.value;
  if (brandKey === "coros") return isCorosConnected.value;
  if (brandKey === "apple_watch" || brandKey === "huawei" || brandKey === "suunto") {
    return isAppleWatchConnected.value || isHuaweiConnected.value || isSuuntoConnected.value;
  }
  return false;
}

const isGarminConnected = ref(false);
const garminDomain = ref("garmin.cn");
const garminEmail = ref("");
const garminPassword = ref("");
const bindingGarmin = ref(false);

const isCorosConnected = ref(false);
const corosAccount = ref("");
const corosPassword = ref("");
const bindingCoros = ref(false);

const isAppleWatchConnected = ref(false);
const isHuaweiConnected = ref(false);
const huaweiAccount = ref("");
const isSuuntoConnected = ref(false);
const suuntoAccount = ref("");
const bindingHealthWatch = ref<"" | "apple_watch" | "huawei" | "suunto">("");
const importingTrackBrand = ref<"" | "apple_watch" | "huawei" | "suunto">("");
const importingScreenshotBrand = ref<"" | "apple_watch" | "huawei" | "suunto">("");

const isAnyWatchConnected = computed(() =>
  isGarminConnected.value ||
  isCorosConnected.value ||
  isAppleWatchConnected.value ||
  isHuaweiConnected.value ||
  isSuuntoConnected.value
);

const connectedWatchSummary = computed(() => {
  const brands: string[] = [];
  if (isGarminConnected.value) brands.push("Garmin");
  if (isCorosConnected.value) brands.push("COROS");
  if (isAppleWatchConnected.value) brands.push("Apple Watch");
  if (isHuaweiConnected.value) brands.push("华为手表");
  if (isSuuntoConnected.value) brands.push("颂拓 Suunto");
  if (brands.length > 0) return `${brands.join(" · ")} ✓`;
  return "手动打卡";
});

async function handleBindGarmin() {
  if (!garminEmail.value.trim() || !garminPassword.value.trim()) {
    uni.showToast({ title: "请输入佳明邮箱与密码", icon: "none" });
    return;
  }
  bindingGarmin.value = true;
  try {
    const uid = user.value?.id;
    const res = await request("/api/auth/garmin/bind", "POST", {
      uid: uid,
      email: garminEmail.value.trim(),
      password: garminPassword.value.trim(),
      domain: garminDomain.value
    });
    if (res?.connected || res?.success) {
      isGarminConnected.value = true;
      onboardingStepsState.value.device = true;
      autoStartHistorySync();
      uni.showModal({
        title: "⌚ 佳明直连成功 · 佩戴提醒",
        content: "请保持 24 小时全天（含夜间睡眠）佩戴手表，以确保小程序获取夜间 HRV、晨起静息心率与睡眠恢复等必要数据。若夜间不佩戴导致数据缺失，将无法给出正确的训练建议。",
        showCancel: false,
        confirmText: "我知道了",
      });
    } else {
      uni.showToast({ title: res?.error || "佳明连接失败，请检查账号密码", icon: "none" });
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || e?.detail || "佳明连接失败", icon: "none" });
  } finally {
    bindingGarmin.value = false;
  }
}

async function handleBindCoros() {
  if (!corosAccount.value.trim() || !corosPassword.value.trim()) {
    uni.showToast({ title: "请输入高驰账号与密码", icon: "none" });
    return;
  }
  bindingCoros.value = true;
  try {
    const uid = user.value?.id;
    const res = await request("/api/auth/coros/bind", "POST", {
      uid: uid,
      account: corosAccount.value.trim(),
      password: corosPassword.value.trim(),
      domain: "teamcnapi.coros.com"
    });
    if (res?.connected || res?.success) {
      isCorosConnected.value = true;
      onboardingStepsState.value.device = true;
      autoStartHistorySync();
      uni.showModal({
        title: "⌚ 高驰直连成功 · 佩戴提醒",
        content: "请保持 24 小时全天（含夜间睡眠）佩戴手表，以确保小程序获取夜间 HRV、晨起静息心率与睡眠恢复等必要数据。若夜间不佩戴导致数据缺失，将无法给出正确的训练建议。",
        showCancel: false,
        confirmText: "我知道了",
      });
    } else {
      uni.showToast({ title: res?.error || "高驰连接失败", icon: "none" });
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || e?.detail || "高驰连接失败", icon: "none" });
  } finally {
    bindingCoros.value = false;
  }
}

async function handleBindHealthWatch(brand: "apple_watch" | "huawei" | "suunto") {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先完成登录", icon: "none" });
    return;
  }
  bindingHealthWatch.value = brand;
  try {
    const acc = brand === "huawei" ? huaweiAccount.value.trim() : brand === "suunto" ? suuntoAccount.value.trim() : undefined;
    const res = await bindHealthWatch(uid, brand, acc);
    if (res?.connected || res?.status === "success") {
      if (brand === "apple_watch") {
        isAppleWatchConnected.value = true;
        if (user.value) user.value.apple_watch_connected = true;
        uni.showToast({ title: "Apple Watch 已连接", icon: "success" });
      } else if (brand === "suunto") {
        isSuuntoConnected.value = true;
        if (user.value) {
          user.value.suunto_connected = true;
          if (suuntoAccount.value.trim()) user.value.suunto_account = suuntoAccount.value.trim();
        }
        uni.showToast({ title: "颂拓手表已连接", icon: "success" });
      } else {
        isHuaweiConnected.value = true;
        if (user.value) {
          user.value.huawei_connected = true;
          if (huaweiAccount.value.trim()) user.value.huawei_account = huaweiAccount.value.trim();
        }
        uni.showToast({ title: "华为手表已连接", icon: "success" });
      }
      onboardingStepsState.value.device = true;
      try {
        uni.setStorageSync("rgm_user", JSON.stringify(user.value));
      } catch (_) {}
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || e?.detail || "连接失败", icon: "none" });
  } finally {
    bindingHealthWatch.value = "";
  }
}

async function handleImportWatchTrack(brand: "apple_watch" | "huawei" | "suunto") {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先完成登录", icon: "none" });
    return;
  }
  importingTrackBrand.value = brand;
  try {
    const res = await chooseAndImportTrackFile(uid, brand);
    if (res && (res.success || res.status === "success" || res.status === "duplicate")) {
      if (brand === "apple_watch") {
        isAppleWatchConnected.value = true;
        if (user.value) user.value.apple_watch_connected = true;
      } else if (brand === "suunto") {
        isSuuntoConnected.value = true;
        if (user.value) user.value.suunto_connected = true;
      } else {
        isHuaweiConnected.value = true;
        if (user.value) user.value.huawei_connected = true;
      }
      onboardingStepsState.value.device = true;
      onboardingStepsState.value.history = true;
      existingActivityCount.value = (existingActivityCount.value || 0) + (res.imported || 1);
      syncedCount.value = (syncedCount.value || 0) + (res.imported || 1);
      try {
        uni.setStorageSync("rgm_user", JSON.stringify(user.value));
      } catch (_) {}
      uni.showToast({
        title: res.message || `已导入 ${res.distance_km || ""} km 跑步轨迹`,
        icon: "success"
      });
    }
  } catch (e: any) {
    if (e?.message === "__CANCEL__" || (e?.errMsg && String(e.errMsg).includes("cancel"))) return;
    uni.showToast({ title: e?.message || e?.detail || "导入轨迹失败", icon: "none" });
  } finally {
    importingTrackBrand.value = "";
  }
}

async function handleImportWatchScreenshot(brand: "apple_watch" | "huawei" | "suunto") {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先完成登录", icon: "none" });
    return;
  }
  importingScreenshotBrand.value = brand;
  try {
    const res = await chooseAndImportScreenshot(uid, brand);
    if (res && res.success) {
      if (brand === "apple_watch") {
        isAppleWatchConnected.value = true;
        if (user.value) user.value.apple_watch_connected = true;
      } else if (brand === "suunto") {
        isSuuntoConnected.value = true;
        if (user.value) user.value.suunto_connected = true;
      } else {
        isHuaweiConnected.value = true;
        if (user.value) user.value.huawei_connected = true;
      }
      onboardingStepsState.value.device = true;
      onboardingStepsState.value.history = true;
      const addedCount = Number(res.imported || res.total_recognized || 1);
      existingActivityCount.value = (existingActivityCount.value || 0) + Number(res.imported || 0);
      syncedCount.value = (syncedCount.value || 0) + addedCount;
      try {
        uni.setStorageSync("rgm_user", JSON.stringify(user.value));
      } catch (_) {}
      uni.showModal({
        title: "🎉 运动截图导入成功",
        content: res.message || "已成功识别并导入跑步记录！",
        showCancel: false,
        confirmText: "太棒了"
      });
    }
  } catch (e: any) {
    if (e?.message === "__CANCEL__" || e?.message === "CANCEL" || (e?.errMsg && String(e.errMsg).includes("cancel"))) return;
    uni.showToast({ title: e?.message || e?.detail || "识别截图失败", icon: "none" });
  } finally {
    importingScreenshotBrand.value = "";
  }
}

// 连接手表与数据保密这一步的「下一步」
async function handleFinishDeviceStep() {
  const uid = user.value?.id;
  const connected = isAnyWatchConnected.value;
  if (uid) {
    // Save data confidentiality preferences
    request(`/api/profile/${uid}`, "PUT", {
      hide_gps_route: Boolean(profileForm.value.hide_gps_route),
      hide_biometrics: Boolean(profileForm.value.hide_biometrics)
    }).catch(() => {});

    if (!connected) {
      request(`/api/profile/${uid}/onboarding-action`, "POST", { action: "skip_device" }).catch(() => {});
      request(`/api/profile/${uid}/onboarding-action`, "POST", { action: "skip_history" }).catch(() => {});
    } else if (syncedCount.value === null && !syncingHistory.value) {
      request(`/api/profile/${uid}/onboarding-action`, "POST", { action: "skip_history" }).catch(() => {});
    }
  }
  currentStep.value = 4;
}

// ── 导入历史记录（并入连接手表步骤）──
const syncRanges = [
  { label: "近 30 天", days: 30 },
  { label: "近 90 天", days: 90 },
  { label: "近 1 年", days: 365 }
];
const selectedRangeDays = ref(90);
const syncingHistory = ref(false);
const syncedCount = ref<number | null>(null);

async function handleStartHistorySync() {
  syncingHistory.value = true;
  syncedCount.value = null;
  try {
    const uid = user.value?.id;
    const d = new Date();
    d.setDate(d.getDate() - selectedRangeDays.value);
    const startDateStr = d.toISOString().split("T")[0];

    const res = await request("/api/sync/trigger", "POST", {
      uid: uid,
      start_date: startDateStr
    });
    syncedCount.value = res?.synced_activities ?? 0;
    uni.showToast({ title: `成功同步 ${syncedCount.value} 条记录`, icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: e?.message || e?.detail || "同步失败，请稍后刷新", icon: "none" });
  } finally {
    syncingHistory.value = false;
  }
}

function autoStartHistorySync() {
  if (syncedCount.value === null && !syncingHistory.value) {
    handleStartHistorySync();
  }
}

// ── Step 4: Goals & Target Race ──
const targetKm = ref(200);
const raceName = ref("");
const raceDate = ref("");
const raceTargetTime = ref("");
const onboardingRaceTypes = ["全马 (42.195K)", "半马 (21.0975K)", "10公里", "5公里", "其他公路跑", "其他越野跑"];
const raceType = ref(onboardingRaceTypes[0]);
const prefilledRaceKey = ref("");
const finishingAll = ref(false);

const quickRacePresets = [
  { label: "🏜️ 戈21挑战赛", name: "第21届玄奘之路戈壁挑战赛", type: "其他越野跑", date: "2026-05-01" },
  { label: "🏃 上海马拉松", name: "2026 上海马拉松", type: "全马 (42.195K)", date: "2026-11-29" },
  { label: "🏃 北京马拉松", name: "2026 北京马拉松", type: "全马 (42.195K)", date: "2026-11-01" }
];

function applyQuickRacePreset(rp: { name: string; type: string; date: string }) {
  raceName.value = rp.name;
  raceType.value = rp.type;
  if (!raceDate.value) raceDate.value = rp.date;
}

async function handleFinishAll() {
  finishingAll.value = true;
  try {
    const uid = user.value?.id;
    if (uid) {
      // Save Confidentiality + Profile
      await request(`/api/profile/${uid}`, "PUT", {
        hide_gps_route: Boolean(profileForm.value.hide_gps_route),
        hide_biometrics: Boolean(profileForm.value.hide_biometrics)
      });

      // Save Goal
      await request(`/api/profile/${encodeURIComponent(uid)}/goal`, "PUT", {
        target_distance: targetKm.value,
        monthly_targets: Array(12).fill(Math.round(targetKm.value))
      });

      // Save Race if filled
      const raceKey = `${raceName.value.trim()}|${raceDate.value}`;
      if (raceName.value.trim() && raceDate.value && raceKey !== prefilledRaceKey.value) {
        await request(`/api/profile/${uid}/races`, "POST", {
          name: raceName.value.trim(),
          race_type: raceType.value,
          race_date: raceDate.value,
          target_time: raceTargetTime.value.trim(),
          priority: 1
        });
      }

      // Mark Onboarding Complete
      await request(`/api/profile/${uid}/onboarding-action`, "POST", {
        action: "complete_onboarding",
        payload: {
          onboarding_completed: 1,
          is_solo_runner: isSoloRunnerSelected.value ? 1 : 0,
          hide_gps_route: profileForm.value.hide_gps_route ? 1 : 0,
          hide_biometrics: profileForm.value.hide_biometrics ? 1 : 0
        }
      });
      trackFunnelStep("onboarding_complete", "完成全部新手4步设定引导", {
        watch_connected: isAnyWatchConnected.value,
      });
    }

    currentStep.value = 5;
  } catch (e: any) {
    uni.showToast({ title: e?.message || e?.detail || "保存目标失败", icon: "none" });
  } finally {
    finishingAll.value = false;
  }
}

function goToTeam() {
  uni.switchTab({ url: "/pages/team/team" });
}

function goToHome() {
  uni.switchTab({ url: "/pages/index/index" });
}

async function loadUserData() {
  user.value = getStoredUser();
  if (!user.value || !user.value.id) {
    try {
      const logged = await authenticateWechatUser();
      if (logged && logged.id) {
        user.value = logged;
      }
    } catch (e) {
      console.warn("Silent login fallback in onboarding:", e);
    }
  }
  const uid = user.value?.id;
  if (!uid) return;

  try {
    const [profileRes, clubsRes, st] = await Promise.all([
      request(`/api/profile/${uid}`).catch((err) => {
        console.warn("loadUserData profile fetch failed", err);
        return null;
      }),
      request(`/api/team/my-clubs/${uid}`).catch((err) => {
        console.warn("loadUserData my-clubs fetch failed", err);
        return null;
      }),
      request(`/api/profile/${uid}/onboarding-status`).catch((err) => {
        console.warn("loadUserData onboarding-status endpoint not reachable", err);
        return null;
      })
    ]);

    const p = profileRes?.profile || {};
    const goal = profileRes?.goal || {};
    const races = profileRes?.races || [];
    const details = st?.details || {};
    const userClubs = details.user_clubs || clubsRes?.clubs || [];

    if (st?.steps) {
      onboardingStepsState.value = { ...onboardingStepsState.value, ...st.steps };
    }

    if (st?.is_completed || details.onboarding_completed || p.onboarding_completed) {
      isAlreadyCompleted.value = true;
    }
    if (details.activity_count !== undefined) {
      existingActivityCount.value = Number(details.activity_count) || 0;
    }

    // ── Pre-fill Step 1 & Step 2: Profile & Ability ──
    const rawName = p.display_name || details.display_name || user.value?.display_name || "";
    const isGenericName = !rawName || rawName === "微信跑者" || rawName.startsWith("微信用户") || rawName.startsWith("跑者_");
    if (!isGenericName) {
      profileForm.value.display_name = rawName;
    } else if (p.real_name) {
      profileForm.value.display_name = p.real_name;
    } else if (user.value?.display_name && user.value.display_name !== "微信跑者") {
      profileForm.value.display_name = user.value.display_name;
    } else if (rawName) {
      profileForm.value.display_name = rawName;
    }

    if (p.avatar_url || details.avatar_url || user.value?.avatar_url) {
      profileForm.value.avatar_url = p.avatar_url || details.avatar_url || user.value?.avatar_url || "";
    }

    const g = p.gender || details.gender;
    if (g === "female" || g === "male") {
      profileForm.value.gender = g;
    }

    const dob = p.date_of_birth || details.date_of_birth || "";
    if (dob) {
      profileForm.value.date_of_birth = dob;
    }

    const h = p.height_cm || p.height || details.height_cm;
    if (h && Number(h) > 0) {
      profileForm.value.height_cm = Number(h);
    }

    const w = p.weight_kg || p.weight || details.weight_kg;
    if (w && Number(w) > 0) {
      profileForm.value.weight_kg = Number(w);
    }

    const yr = p.years_running ?? details.years_running;
    if (yr !== undefined && yr !== null && Number(yr) >= 0) {
      profileForm.value.years_running = Number(yr);
    }

    if (p.resting_heart_rate && Number(p.resting_heart_rate) > 0) {
      profileForm.value.resting_heart_rate = Number(p.resting_heart_rate);
    }
    if (p.max_heart_rate && Number(p.max_heart_rate) > 0) {
      profileForm.value.max_heart_rate = Number(p.max_heart_rate);
    }
    if (p.marathon_pb && Number(p.marathon_pb) > 0) {
      profileForm.value.marathon_pb_str = secondsToTimeStr(Number(p.marathon_pb));
      activePbTab.value = "marathon";
      onboardingStepsState.value.ability = true;
    }
    if (p.half_pb && Number(p.half_pb) > 0) {
      profileForm.value.half_pb_str = secondsToTimeStr(Number(p.half_pb));
      if (!profileForm.value.marathon_pb_str) activePbTab.value = "half";
      onboardingStepsState.value.ability = true;
    }
    if (p.ten_k_pb && Number(p.ten_k_pb) > 0) {
      profileForm.value.ten_k_pb_str = secondsToTimeStr(Number(p.ten_k_pb));
      onboardingStepsState.value.ability = true;
    }
    if (p.five_k_pb && Number(p.five_k_pb) > 0) {
      profileForm.value.five_k_pb_str = secondsToTimeStr(Number(p.five_k_pb));
      onboardingStepsState.value.ability = true;
    }

    profileForm.value.hide_gps_route = Boolean(p.hide_gps_route ?? details.hide_gps_route);
    profileForm.value.hide_biometrics = Boolean(p.hide_biometrics ?? details.hide_biometrics);

    // ── Pre-fill Club ──
    if (userClubs.length > 0) {
      joinedClubId.value = userClubs[0].id;
      joinedClubName.value = userClubs[0].name;
      isSoloRunnerSelected.value = false;
      onboardingStepsState.value.club = true;
    } else if (details.is_solo_runner || p.is_solo_runner) {
      isSoloRunnerSelected.value = true;
      onboardingStepsState.value.club = true;
    }

    // ── Pre-fill Step 3: Devices ──
    isGarminConnected.value = Boolean(p.garmin_connected ?? details.garmin_connected);
    if (p.garmin_email) garminEmail.value = p.garmin_email;
    if (p.garmin_domain) garminDomain.value = p.garmin_domain;

    isCorosConnected.value = Boolean(p.coros_connected ?? details.coros_connected);
    if (p.coros_account) corosAccount.value = p.coros_account;

    isAppleWatchConnected.value = Boolean(p.apple_watch_connected ?? details.apple_watch_connected);
    isHuaweiConnected.value = Boolean(p.huawei_connected ?? details.huawei_connected);
    if (p.huawei_account || details.huawei_account) {
      huaweiAccount.value = p.huawei_account || details.huawei_account;
    }
    isSuuntoConnected.value = Boolean(p.suunto_connected ?? details.suunto_connected);
    if (p.suunto_account || details.suunto_account) {
      suuntoAccount.value = p.suunto_account || details.suunto_account;
    }

    // Automatically focus the connected brand tab if any
    if (isGarminConnected.value) selectedWatchBrand.value = "garmin";
    else if (isCorosConnected.value) selectedWatchBrand.value = "coros";
    else if (isAppleWatchConnected.value || isHuaweiConnected.value || isSuuntoConnected.value) {
      selectedWatchBrand.value = "apple_watch";
    }

    if (isAnyWatchConnected.value) {
      onboardingStepsState.value.device = true;
    }

    // ── Pre-fill Step 4: Goals & Races ──
    const dist = goal.target_distance || details.target_distance;
    if (dist && Number(dist) > 0) {
      targetKm.value = Number(dist);
    }

    if (Array.isArray(races) && races.length > 0) {
      const upcoming = races.find((r: any) => !r.is_past && !r.is_completed) || races[0];
      if (upcoming?.name) raceName.value = upcoming.name;
      if (upcoming?.race_date) raceDate.value = upcoming.race_date;
      if (upcoming?.target_time) raceTargetTime.value = upcoming.target_time;
      if (upcoming?.race_type && onboardingRaceTypes.includes(upcoming.race_type)) raceType.value = upcoming.race_type;
      prefilledRaceKey.value = `${(upcoming?.name || "").trim()}|${upcoming?.race_date || ""}`;
      onboardingStepsState.value.goals = true;
    }
  } catch (e) {
    console.warn("loadUserData failed", e);
  }
}

onLoad((query: any) => {
  if (query?.step) {
    const s = parseInt(query.step);
    if (s >= 1 && s <= 5) {
      currentStep.value = s;
    }
  }
  loadUserData();
});

onShow(() => {
  applySystemTheme(currentTheme.value);
  loadUserData();
});

onMounted(async () => {
  await loadUserData();
});
</script>

<style scoped>
/* 选填字段折叠入口 */
.optional-toggle {
  padding: 22rpx 0;
}
.optional-toggle-text {
  font-size: 24rpx;
  color: var(--rgm-brand-text, #ff8533);
}
/* 连接手表步骤内的「导入历史记录」小标题 */
.history-inline-title {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  margin: 12rpx 0 16rpx;
}
.hit-title {
  font-size: 28rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}
.hit-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.onboarding-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  color: var(--rgm-text, #ffffff);
  padding: 24rpx 28rpx calc(48rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── 顶部步骤条 ── */
.stepper-header {
  position: relative;
  margin-bottom: 40rpx;
  padding-top: 10rpx;
}

.stepper-track {
  position: absolute;
  top: 36rpx;
  left: 40rpx;
  right: 40rpx;
  height: 4rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  border-radius: 4rpx;
  z-index: 1;
}

.stepper-fill {
  height: 100%;
  background: var(--rgm-brand-grad, linear-gradient(90deg, #fc4c02 0%, #a855f7 100%));
  border-radius: 4rpx;
  transition: width 0.3s ease;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.steps-row {
  position: relative;
  display: flex;
  justify-content: space-between;
  z-index: 2;
}

.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  cursor: pointer;
}

.step-circle {
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  background: var(--rgm-card, #18181c);
  border: 3rpx solid var(--rgm-line, rgba(255, 255, 255, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: bold;
  transition: all 0.25s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.step-item.active .step-circle {
  background: var(--rgm-brand, #fc4c02);
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  box-shadow: 0 0 16rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.5));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.step-item.completed .step-circle {
  background: #10b981;
  border-color: #10b981;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.step-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

.step-item.active .step-label {
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

.step-item.completed .step-label {
  color: var(--rgm-green, #10b981);
}

.stepper-edit-hint {
  margin-top: 24rpx;
  background: rgba(10, 132, 255, 0.08);
  border: 1rpx solid rgba(10, 132, 255, 0.25);
  border-radius: 16rpx;
  padding: 12rpx 20rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.seh-badge {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-blue, #38bdf8);
}

.seh-text {
  font-size: 20rpx;
  color: var(--rgm-text-2, #94a3b8);
}

.existing-records-badge {
  background: rgba(16, 185, 129, 0.1);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
  border-radius: 18rpx;
  padding: 16rpx 20rpx;
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.erb-icon {
  font-size: 28rpx;
}

.erb-text {
  font-size: 22rpx;
  color: var(--rgm-green, #6ee7b7);
  line-height: 1.4;
  flex: 1;
}

/* ── 步骤说明容器 ── */
.step-container {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
}

.step-intro-box {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.04) 0%, rgba(255, 255, 255, 0.01) 100%);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 28rpx;
}

.step-badge {
  font-size: 20rpx;
  font-weight: 800;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
  display: inline-block;
  margin-bottom: 12rpx;
}

.step-title {
  font-size: 34rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 10rpx;
  display: block;
}


/* ── 表单卡片 ── */
.form-card {
  background: var(--rgm-card, #141416);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 30rpx;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  width: 100%;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  width: 100%;
  box-sizing: border-box;
}

.form-group picker {
  width: 100%;
  display: block;
  box-sizing: border-box;
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.input-label {
  font-size: 26rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 600;
}

.sub-hint {
  font-size: 22rpx;
  color: var(--rgm-blue, #38bdf8);
}

.text-input {
  width: 100% !important;
  height: 88rpx !important;
  min-height: 88rpx !important;
  line-height: 88rpx !important;
  background: var(--rgm-card-2, #1f1f23);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 16rpx;
  padding: 0 24rpx !important;
  font-size: 28rpx;
  color: var(--rgm-text, #ffffff);
  box-sizing: border-box !important;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.input-placeholder-class {
  color: var(--rgm-text-3, #71717a) !important;
  font-size: 26rpx !important;
}

:deep(.input-placeholder-class),
:deep(.uni-input-placeholder) {
  color: var(--rgm-text-3, #71717a) !important;
  font-size: 26rpx !important;
}

.form-row-2 {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 20rpx;
  width: 100%;
  box-sizing: border-box;
}

.form-group.half {
  flex: 1 1 0;
  min-width: 0;
  width: 0;
  box-sizing: border-box;
}

.picker-display-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  height: 88rpx;
  min-height: 88rpx;
  line-height: 88rpx;
  background: var(--rgm-card-2, #1f1f23);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 16rpx;
  padding: 0 24rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.picker-display-box.mini {
  height: 88rpx;
  min-height: 88rpx;
  line-height: 88rpx;
  padding: 0 20rpx;
  box-sizing: border-box;
}

.picker-val {
  font-size: 28rpx;
  color: var(--rgm-text, #ffffff);
}

.picker-arrow {
  font-size: 26rpx;
  color: var(--rgm-text-3, #71717a);
}

.segmented-control {
  display: flex;
  gap: 16rpx;
  width: 100%;
  box-sizing: border-box;
}

.segmented-control.mini {
  gap: 12rpx;
}

.seg-item {
  flex: 1 1 0;
  min-width: 0;
  height: 88rpx;
  line-height: 88rpx;
  background: var(--rgm-card-2, #1f1f23);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 16rpx;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-sizing: border-box;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.seg-item.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border-color: var(--rgm-brand, #fc4c02);
}

.seg-txt {
  font-size: 26rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.seg-item.active .seg-txt {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.bmi-badge-box {
  background: rgba(56, 189, 248, 0.12);
  border: 1rpx solid rgba(56, 189, 248, 0.25);
  border-radius: 12rpx;
  padding: 10rpx 16rpx;
}

.bmi-badge-text {
  font-size: 22rpx;
  color: var(--rgm-blue, #38bdf8);
  font-weight: 600;
}

.chips-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14rpx;
}

.exp-chip {
  background: var(--rgm-card-2, #1f1f23);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  padding: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  cursor: pointer;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.exp-chip.active {
  border-color: var(--rgm-brand, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
}

.exp-title {
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

.exp-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

/* ── 跑团选择页 ── */
.solo-skip-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 20rpx;
  padding: 24rpx;
  cursor: pointer;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.solo-skip-card.selected {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.1);
}

.ssc-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
}

.ssc-icon {
  font-size: 38rpx;
}

.ssc-meta {
  flex: 1;
}

.ssc-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
  margin-bottom: 4rpx;
}

.ssc-desc {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
  line-height: 1.4;
  display: block;
}

.ssc-check {
  font-size: 22rpx;
  padding: 8rpx 20rpx;
  border-radius: 14rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text-2, #a1a1aa);
}

.ssc-check.checked {
  background: #10b981;
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.divider-line-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin: 10rpx 0;
}

.line {
  flex: 1;
  height: 1rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
}

.line-text {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
}

.club-search-filter-box {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.club-search-bar {
  display: flex;
  align-items: center;
  background: var(--rgm-card, #18181b);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 18rpx;
  padding: 0 24rpx;
  height: 88rpx;
  width: 100%;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.csb-search-icon {
  font-size: 28rpx;
  margin-right: 14rpx;
  opacity: 0.7;
  flex-shrink: 0;
}

.csb-input {
  flex: 1;
  min-width: 0;
  height: 88rpx;
  line-height: 88rpx;
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  box-sizing: border-box;
}

.csb-clear-icon {
  font-size: 26rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 8rpx 14rpx;
  flex-shrink: 0;
}

.city-chips-scroll {
  white-space: nowrap;
  width: 100%;
}

.city-chips-row {
  display: inline-flex;
  gap: 12rpx;
}

.city-chip {
  padding: 8rpx 22rpx;
  border-radius: 24rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  flex-shrink: 0;
}

.city-chip.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  border-color: var(--rgm-brand, #fc4c02);
}

.city-chip-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.city-chip.active .city-chip-text {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.clubs-cards-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.onboard-club-card {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: var(--rgm-card, #141416);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.onboard-club-card.is-joined {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.06);
}

.occ-logo {
  width: 88rpx;
  height: 88rpx;
  border-radius: 18rpx;
  background: var(--rgm-card-3, #27272a);
  flex-shrink: 0;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.occ-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.occ-title-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.occ-name {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.occ-city {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.occ-desc {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.occ-meta-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 4rpx;
}

.occ-members {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.occ-mode-tag {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.occ-mode-tag.mode-free {
  background: rgba(16, 185, 129, 0.15);
  color: var(--rgm-green, #10b981);
}

.occ-mode-tag.mode-invite {
  background: rgba(245, 158, 11, 0.15);
  color: var(--rgm-amber, #fbbf24);
}

.occ-join-btn {
  font-size: 22rpx;
  padding: 10rpx 24rpx;
  border-radius: 14rpx;
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  margin: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.occ-join-btn.joined {
  background: rgba(16, 185, 129, 0.2);
  color: var(--rgm-green, #10b981);
  border: 1rpx solid rgba(16, 185, 129, 0.4);
}

/* ── 手表直连卡片 ── */
.device-bind-card {
  background: var(--rgm-card, #141416);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 28rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.dbc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dbc-left {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.device-brand-badge {
  font-size: 20rpx;
  font-weight: 900;
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
}

.device-brand-badge.garmin {
  background: #007cc3;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.device-brand-badge.coros {
  background: #e11d48;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.device-brand-badge.apple {
  background: #10b981;
  color: #ffffff;
}

.device-brand-badge.huawei {
  background: #cf0a2c;
  color: #ffffff;
}

.device-brand-badge.suunto {
  background: #f59e0b;
  color: #000000;
}

.dbc-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.dbc-status {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
}

.dbc-status.connected {
  color: var(--rgm-green, #10b981);
  font-weight: bold;
}

.dbc-body {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-top: 10rpx;
}


.dbc-action-row {
  display: flex;
  gap: 14rpx;
  align-items: center;
}

.flex-1 {
  flex: 1;
}

.dbc-bind-btn {
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 16rpx;
  color: var(--rgm-text, #ffffff);
  margin-top: 10rpx;
}

.dbc-bind-btn.garmin-btn {
  background: var(--rgm-brand, #007cc3);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.dbc-bind-btn.coros-btn {
  background: #e11d48;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.dbc-bind-btn.apple-btn {
  background: #10b981;
  color: #ffffff;
}

.dbc-bind-btn.huawei-btn {
  background: #cf0a2c;
  color: #ffffff;
}

.dbc-bind-btn.suunto-btn {
  background: #f59e0b;
  color: #000000;
}

.dbc-bind-btn.secondary-btn {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text, #ffffff);
}

.dbc-connected-tip {
  padding: 16rpx;
  background: rgba(16, 185, 129, 0.1);
  border-radius: 14rpx;
}

.dbc-tip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.dbc-mini-import-btn {
  font-size: 20rpx;
  font-weight: bold;
  padding: 8rpx 18rpx;
  border-radius: 12rpx;
  background: rgba(16, 185, 129, 0.2);
  color: var(--rgm-green, #10b981);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
  margin: 0;
  flex-shrink: 0;
}

.tip-txt {
  font-size: 22rpx;
  color: var(--rgm-green, #10b981);
  flex: 1;
}

/* ── 历史记录同步 ── */
.sync-history-card, .manual-record-card {
  background: var(--rgm-card, #141416);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 30rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.shc-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.shc-icon {
  font-size: 40rpx;
}

.shc-meta {
  flex: 1;
}

.shc-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.shc-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #9ca3af);
  display: block;
}

.range-selector {
  display: flex;
  gap: 16rpx;
  margin: 10rpx 0;
}

.range-pill {
  flex: 1;
  text-align: center;
  padding: 14rpx 0;
  border-radius: 14rpx;
  background: var(--rgm-card-2, #1f1f23);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.range-pill.active {
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  font-weight: bold;
}

.sync-start-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6426 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  padding: 18rpx 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.sync-result-badge {
  text-align: center;
  padding: 14rpx;
  background: rgba(16, 185, 129, 0.15);
  color: var(--rgm-green, #10b981);
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 14rpx;
}

.mrc-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.mrc-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #9ca3af);
  line-height: 1.4;
}

/* ── 目标卡片 ── */
.target-highlight {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #fc4c02);
}

.chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-top: 14rpx;
}

.target-chip {
  padding: 8rpx 22rpx;
  background: var(--rgm-card-2, #1f1f23);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 14rpx;
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.target-chip.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

/* ── 成功完成卡片 ── */
.success-card {
  background: var(--rgm-card, #141416);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 28rpx;
  padding: 44rpx 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  box-shadow: 0 10rpx 30rpx var(--rgm-shadow, rgba(0, 0, 0, 0.4));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.confetti-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}

.success-title {
  font-size: 36rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 12rpx;
}

.success-subtitle {
  font-size: 24rpx;
  color: var(--rgm-text-2, #9ca3af);
  line-height: 1.5;
  margin-bottom: 36rpx;
}

.summary-box {
  width: 100%;
  background: var(--rgm-card-2, #1c1c20);
  border-radius: 20rpx;
  padding: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-bottom: 36rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.summary-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.si-label {
  font-size: 24rpx;
  color: var(--rgm-text-3, #71717a);
}

.si-val {
  font-size: 24rpx;
  color: var(--rgm-text, #e4e4e7);
  font-weight: 600;
}

.si-val.highlight {
  color: var(--rgm-brand-text, #fc4c02);
}

.si-val.green {
  color: var(--rgm-green, #10b981);
}

.success-actions {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.success-btn {
  font-size: 28rpx;
  font-weight: bold;
  height: 84rpx;
  line-height: 84rpx;
  border-radius: 20rpx;
  margin: 0;
}

.success-btn.primary {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6426 100%));
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.success-btn.secondary {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text, #e4e4e7);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
}

.success-btn.tertiary {
  background: rgba(10, 132, 255, 0.12);
  color: var(--rgm-blue, #38bdf8);
  border: 1rpx solid rgba(10, 132, 255, 0.3);
}

/* ── 底部操作栏 ── */
.bottom-actions {
  margin-top: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.save-only-btn {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.2));
  color: var(--rgm-text, #ffffff);
  border-radius: 22rpx;
  font-size: 28rpx;
  font-weight: 600;
  height: 88rpx;
  line-height: 88rpx;
  text-align: center;
  width: 100%;
}

.primary-step-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6426 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 28rpx;
  font-weight: bold;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 22rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.bottom-nav-row {
  display: flex;
  gap: 20rpx;
  margin-top: 20rpx;
}

.nav-prev-btn {
  flex: 1;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text-2, #a1a1aa);
  font-size: 26rpx;
  font-weight: 600;
  height: 84rpx;
  line-height: 84rpx;
  border-radius: 20rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  margin: 0;
}

.nav-next-btn, .nav-skip-btn {
  flex: 2;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6426 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  height: 84rpx;
  line-height: 84rpx;
  border-radius: 20rpx;
  margin: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.finish-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #10b981 0%, #059669 100%));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.empty-box, .loading-box {
  text-align: center;
  padding: 40rpx;
}

.empty-text, .loading-text {
  font-size: 24rpx;
  color: var(--rgm-text-3, #71717a);
}

/* ── Modal ── */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.modal-content {
  width: 85%;
  max-width: 600rpx;
  background: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  border-radius: 24rpx;
  padding: 32rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.modal-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.modal-close {
  font-size: 28rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 8rpx;
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.modal-sub {
  font-size: 24rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

/* ── 4 步向导新增样式：微信头像昵称一行、跑力测算卡、手表品牌胶囊、数据保密开关 ── */
.avatar-nick-row {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin-bottom: 24rpx;
}

.wx-avatar-pick-btn {
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  padding: 0;
  margin: 0;
  position: relative;
  overflow: hidden;
  border: 3rpx solid var(--rgm-brand, #fc4c02);
  background: var(--rgm-card-2, #18181c);
  flex-shrink: 0;
}

.wx-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
}

.wx-avatar-tag {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.72);
  color: #ffffff;
  font-size: 18rpx;
  line-height: 34rpx;
  text-align: center;
}

.nick-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.pb-preset-pill {
  padding: 10rpx 20rpx;
  border-radius: 999rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  font-size: 22rpx;
  color: var(--rgm-text-2, #d4d4d8);
}

.pb-preset-pill.active {
  background: rgba(252, 76, 2, 0.18);
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-brand-text, #ff8533);
  font-weight: 700;
}

.vdot-preview-card {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.14) 0%, rgba(56, 189, 248, 0.12) 100%);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.vpc-left, .vpc-right {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.vpc-right {
  align-items: flex-end;
}

.vpc-badge {
  font-size: 20rpx;
  color: #34d399;
  font-weight: 600;
}

.vpc-vdot {
  font-size: 32rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.vpc-pace-lbl {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.vpc-pace-val {
  font-size: 26rpx;
  font-weight: 700;
  color: #38bdf8;
}

.watch-selector-card {
  background: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 24rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}

.wsc-title {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  display: block;
  margin-bottom: 16rpx;
}

.watch-brand-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.watch-brand-pill {
  width: calc(50% - 8rpx);
  box-sizing: border-box;
  padding: 18rpx 20rpx;
  border-radius: 18rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border: 2rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.watch-brand-pill.active {
  background: rgba(252, 76, 2, 0.14);
  border-color: var(--rgm-brand, #fc4c02);
}

.watch-brand-pill.connected {
  border-color: #10b981;
}

.wbp-name {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.wbp-sub {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.watch-brand-pill.connected .wbp-sub {
  color: #34d399;
  font-weight: 600;
}

.privacy-settings-card {
  background: var(--rgm-card, #18181c);
  border: 1rpx solid rgba(56, 189, 248, 0.28);
  border-radius: 24rpx;
  padding: 26rpx;
  margin-bottom: 28rpx;
}

.psc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10rpx;
}

.psc-title {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.psc-badge {
  font-size: 20rpx;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
  font-weight: 600;
}


.privacy-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.ptr-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.ptr-title {
  font-size: 25rpx;
  font-weight: 600;
  color: var(--rgm-text, #ffffff);
}

.ptr-sub {
  font-size: 21rpx;
  color: var(--rgm-text-3, #9ca3af);
  line-height: 1.4;
}
</style>
