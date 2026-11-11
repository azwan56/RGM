<template>
  <view class="dashboard-page" :class="themeClass">
    <!-- 首屏骨架屏：首次进入时盖住尚未加载的数据，避免先闪示例数据 -->
    <PageSkeleton v-if="firstLoadPending" overlay />
    <!-- Header: User Greeting & Avatar -->
    <view class="header-card">
      <view class="user-info">
        <image class="avatar" :src="dashboardData?.user?.avatar_url || user?.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" @click="goToQuickEditProfile" />
        <view class="text-group">
          <text class="greeting">欢迎回来，</text>
          <view style="display: flex; align-items: center; gap: 10rpx; flex-wrap: wrap;">
            <text class="user-name">{{ dashboardData?.user?.display_name || user?.display_name || "跑者" }}</text>
            <text
              v-if="isDefaultNickname"
              style="font-size: 20rpx; font-weight: 700; padding: 4rpx 12rpx; border-radius: 999rpx; background: rgba(252, 76, 2, 0.14); color: #fc4c02; border: 1rpx solid rgba(252, 76, 2, 0.35);"
              @click.stop="goToQuickEditProfile"
            >
              ✏️ 改昵称
            </text>
          </view>
          <view v-if="dashboardData?.fitness_form && hasRunningData" class="user-fitness-sub" @click="goToBodyData">
            <text
              class="uf-tag"
              :style="currentTheme === 'volt'
                ? {
                    color: '#059669',
                    backgroundColor: '#ECFDF5',
                    borderColor: 'rgba(16, 185, 129, 0.35)'
                  }
                : {
                    color: dashboardData?.fitness_form?.status_color || '#38bdf8',
                    backgroundColor: (dashboardData?.fitness_form?.status_color || '#38bdf8') + '22',
                    borderColor: (dashboardData?.fitness_form?.status_color || '#38bdf8') + '44'
                  }"
            >
              ● 今日状态：{{ dashboardData?.fitness_form?.status_label || "训练中" }}{{ currentVdot != null ? ` · VDOT ${currentVdot}` : '' }}
            </text>
          </view>
        </view>
      </view>
      <view class="header-right-actions">
        <view class="layout-order-pill" @click="openLayoutOrderModal">
          <text class="layout-order-pill-txt">↕️ 排版</text>
        </view>
        <view class="garmin-badge" :class="{ active: isDeviceConnected }" @click="goToDeviceBinding">
          <view class="pulse-dot" />
          <text class="badge-text">{{ isDeviceConnected ? deviceConnectedText : '绑表 ›' }}</text>
        </view>
        <view class="notif-bell-btn" @click="openNotificationsModal">
          <text class="bell-icon">🔔</text>
          <view v-if="unreadNotifCount > 0" class="notif-badge">
            <text class="notif-badge-text">{{ unreadNotifCount > 99 ? '99+' : unreadNotifCount }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- ── ✅ 新手任务清单（替代原「设定向导」横幅：按真实状态逐项勾选，全部完成后自动消失）── -->
    <view v-if="showStarterTasks" id="rgm-mod-starter" class="starter-card">
      <view class="sc-head" @click="starterCollapsed = !starterCollapsed">
        <view class="sc-head-left">
          <text class="sc-title">新手任务</text>
          <text class="sc-count">{{ starterDoneCount }}/{{ starterTasks.length }}</text>
        </view>
        <view class="sc-head-right">
          <text class="sc-toggle">{{ starterCollapsed ? '展开 ▾' : '收起 ▴' }}</text>
          <text class="sc-close" @click.stop="dismissOnboardBanner">✕</text>
        </view>
      </view>
      <view class="sc-progress">
        <view class="sc-progress-fill" :style="{ width: (starterDoneCount / starterTasks.length * 100) + '%' }"></view>
      </view>
      <view v-if="!starterCollapsed" class="sc-list">
        <view
          v-for="task in starterTasks"
          :key="task.key"
          class="sc-item"
          :class="{ done: task.done }"
          @click="runStarterTask(task.key, task.done)"
        >
          <text class="sc-check">{{ task.done ? '✓' : '' }}</text>
          <view class="sc-item-meta">
            <text class="sc-item-title">{{ task.title }}</text>
          </view>
          <text v-if="!task.done" class="sc-item-go">{{ task.cta }} ›</text>
        </view>
        <text class="sc-footer-link" @click="goToOnboarding">打开完整设定向导 ›</text>
      </view>
    </view>

    <!-- ── 大群必填资料待完善醒目提醒横幅 (若有) ── -->
    <view
      v-if="pendingOrgReminder?.hasReminder"
      class="org-reminder-banner"
      :class="pendingOrgReminder.type === 'suspended' ? 'banner-suspended' : 'banner-temporary'"
      @click="goToFillRequiredFields"
    >
      <view class="orb-icon">{{ pendingOrgReminder.type === 'suspended' ? '🚫' : '⏳' }}</view>
      <view class="orb-text-col">
        <view class="orb-title-row">
          <text class="orb-title">
            {{ pendingOrgReminder.type === 'suspended' ? '大群访问已被暂停' : '大群档案待完善' }}
          </text>
          <text class="orb-badge" v-if="pendingOrgReminder.remainingDays !== undefined && pendingOrgReminder.remainingDays !== null">
            剩余 {{ pendingOrgReminder.remainingDays }} 天
          </text>
        </view>
        <text class="orb-desc">
          {{ pendingOrgReminder.missingLabels ? '缺少必填项：' + pendingOrgReminder.missingLabels : '请尽快补齐实名资料以获管理员审核' }}
        </text>
      </view>
      <view class="orb-action-btn">
        <text class="orb-btn-label">立即填写</text>
        <text class="orb-arrow">›</text>
      </view>
    </view>

    <!-- ── 首页核心板块容器（支持用户自定义显示次序，基于 Flex order 无损重排） ── -->
    <view class="home-modules-container">
    <!-- ── 🏃 我的下一场约跑：已报名且未结束时显示（汇总所有已加入跑团） ── -->
    <view
      v-if="myNextRun"
      id="rgm-mod-nextrun"
      class="next-run-card"
      :style="{ order: getModuleOrder('nextrun') }"
      @click="openGroupRunDetail(myNextRun.club_id, myNextRun.id)"
    >
      <view class="nr-header">
        <view class="nr-badge">
          <view class="nr-pulse" />
          <text class="nr-badge-text">我报名的约跑</text>
        </view>
        <text class="nr-countdown">{{ getCountdownText(myNextRun.meet_time || myNextRun.start_date) }}</text>
      </view>
      <text class="nr-title">{{ myNextRun.title }}</text>
      <view class="nr-meta-row">
        <text class="nr-meta highlight">⏰ {{ formatMeetTime(myNextRun.meet_time || myNextRun.start_date) }}</text>
      </view>
      <view class="nr-meta-row">
        <text class="nr-meta">📍 {{ myNextRun.location || '跑团集合点' }}</text>
      </view>
      <view class="nr-meta-row">
        <text class="nr-meta dim">🏃 {{ myNextRun.club_name || '跑团' }} · 目标 {{ myNextRun.target_km || 10 }} km{{ myNextRun.pace_requirement ? ' · 配速 ' + myNextRun.pace_requirement : '' }}</text>
      </view>
      <view class="nr-actions">
        <button class="nr-btn" @click.stop="addRunToCalendar(myNextRun)">🔔 日历</button>
        <button class="nr-btn" open-type="share" :data-share-type="'group_run'" @click.stop>💬 转发</button>
        <button class="nr-btn primary" @click.stop="openGroupRunDetail(myNextRun.club_id, myNextRun.id, isGroupRunPostStage(myNextRun) ? 'post' : 'pre')">{{ isGroupRunPostStage(myNextRun) ? '🏆 战报' : '📣 详情' }}</button>
      </view>
    </view>

    <!-- ── 🔥 跑团打卡动态快捷入口（置于今日课表之上，展示最新打卡数与教练点评数） ── -->
    <view
      id="rgm-mod-feed"
      class="home-feed-shortcut-bar home-feed-top-card"
      :style="{ order: getModuleOrder('feed') }"
      @click="goToClubFeed"
    >
      <view class="hfs-left">
        <view
          v-if="dashboardData?.club_feed_summary?.latest_checkins && dashboardData.club_feed_summary.latest_checkins.length > 0"
          class="hfs-avatar-stack"
        >
          <image
            v-for="(ck, cIdx) in dashboardData.club_feed_summary.latest_checkins.slice(0, 3)"
            :key="ck.id || cIdx"
            class="hfs-avatar"
            :style="{ zIndex: 5 - Number(cIdx) }"
            :src="ck.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
            mode="aspectFill"
          />
        </view>
        <text v-else class="hfs-fire-icon">🔥</text>

        <view class="hfs-text-col">
          <view class="hfs-title-row">
            <text class="hfs-title">🔥 打卡动态</text>
            <text class="hfs-stat-pill checkin">
              {{ (dashboardData?.club_feed_summary?.today_checkin_count || 0) > 0
                ? `今日 ${dashboardData.club_feed_summary.today_checkin_count} 打卡`
                : `本周 ${dashboardData?.club_feed_summary?.week_checkin_count || dashboardData?.club_feed_summary?.month_checkin_count || 0} 打卡` }}
            </text>
            <text class="hfs-stat-pill critique">
              🎯 {{ dashboardData?.club_feed_summary?.coach_critique_count || 0 }} 点评
            </text>
          </view>
          <text
            v-if="dashboardData?.club_feed_summary?.latest_checkins && dashboardData.club_feed_summary.latest_checkins.length > 0"
            class="hfs-sub-line"
          >
            最新：{{ dashboardData.club_feed_summary.latest_checkins[0].display_name }} 打卡 {{ dashboardData.club_feed_summary.latest_checkins[0].distance_km }}km
          </text>
        </view>
      </view>
      <view class="hfs-cta">
        <text class="hfs-cta-text">进入 ›</text>
      </view>
    </view>

    <!-- ── 📅 今日训练课表独立板块（与周/月目标完成度分开，支持独立排序） ── -->
    <view id="rgm-mod-today" class="today-standalone-card" :style="{ order: getModuleOrder('today') }">
      <view
        v-if="dashboardData?.today_workout"
        class="get-main-box standalone"
        :class="{ 'is-completed': dashboardData.today_workout.completed, 'is-volt': currentTheme === 'volt' }"
      >
        <view class="get-main-row">
          <view class="get-info-col" @click="goToCoachPage">
            <view class="get-meta-row">
              <text class="get-label">📅 今日课表</text>
              <text class="tw-badge" :class="getWorkoutBadgeClass(dashboardData.today_workout.workout_type)">
                {{ getWorkoutTypeLabel(dashboardData.today_workout.workout_type) }}
              </text>
              <text
                v-if="dashboardData.today_workout.workout_type !== 'rest' && dashboardData.today_workout.distance_km"
                class="get-dist-txt"
              >
                {{ dashboardData.today_workout.distance_km }}km
              </text>
              <text
                v-if="dashboardData.today_workout.workout_type !== 'rest' && dashboardData.today_workout.target_pace && dashboardData.today_workout.target_pace !== '—'"
                class="get-pace-txt"
              >
                · {{ dashboardData.today_workout.target_pace }}
              </text>
              <text class="get-more-link">详情 ›</text>
            </view>
            <text class="get-title-txt">{{ dashboardData.today_workout.title }}</text>
          </view>

          <view class="get-action-col">
            <button
              class="get-checkin-btn"
              :class="{ completed: dashboardData.today_workout.completed }"
              :loading="togglingWorkout"
              @click.stop="handleTodayWorkoutToggle"
            >
              <text class="get-checkin-btn-txt">
                {{ dashboardData.today_workout.completed ? (dashboardData.today_workout.actual_distance_km ? `✅ ${dashboardData.today_workout.actual_distance_km}k` : '✅ 已打卡') : '打卡' }}
              </text>
            </button>
            <view
              v-if="dashboardData.today_workout.completed"
              class="get-log-icon-btn"
              :class="{ filled: hasTodayCheckinLog }"
              @click.stop="openCheckinLogModal"
            >
              <text class="get-log-icon-txt">{{ hasTodayCheckinLog ? '✏️ 感受' : '📝 感受' }}</text>
            </view>
          </view>
        </view>

        <!-- 1-line Coach Notes preview if present -->
        <view
          v-if="dashboardData.today_workout.coach_notes"
          class="get-sub-note coach"
          @click="goToCoachPage"
        >
          <text class="get-sub-note-txt">👨‍🏫 教练批注：{{ dashboardData.today_workout.coach_notes }}</text>
        </view>

        <!-- 1-line Check-in Feeling/Photo summary if logged -->
        <view
          v-if="dashboardData.today_workout.completed && hasTodayCheckinLog"
          class="get-sub-note feeling"
          @click.stop="openCheckinLogModal"
        >
          <text class="get-sub-note-txt">{{ todayCheckinSummaryText }}</text>
          <text class="get-sub-edit-arrow">编辑 ›</text>
        </view>
      </view>

      <view
        v-else
        class="get-empty-bar standalone"
        :class="{ 'is-volt': currentTheme === 'volt' }"
        @click="goToCoachPage"
      >
        <text class="get-empty-left">📅 今日课表 · 暂无训练安排</text>
        <text class="get-empty-right">定制课表 ›</text>
      </view>
    </view>

    <!-- ── 🎯 周 / 月目标完成度独立板块（同屏双饼图 + 7日打卡条） ── -->
    <view id="rgm-mod-goal" class="hero-progress-card" :style="{ order: getModuleOrder('goal') }">
      <!-- 一页同屏：左侧「本周完成度饼图」 + 右侧「当月完成度饼图」 -->
      <view class="dual-pie-overview-grid">
        <!-- 左侧：本周进度饼图卡 -->
        <view class="dpo-card week-card" @click="openGoalSheet('week')">
          <view class="dpo-card-head">
            <text class="dpo-period-title">🏃 {{ shortWeekTitle }}</text>
            <text class="dpo-period-pct text-emerald">{{ dashboardData?.weekly_progress?.progress_pct ?? 0 }}%</text>
          </view>

          <view class="dpo-pie-stage">
            <view class="goal-pie-chart dpo-pie week-pie" :style="weekPieStyle">
              <view class="pie-start-spoke" />
              <view class="pie-origin-dot" />
            </view>
          </view>

          <view class="dpo-km-ratio">
            <text class="dpo-km-done text-emerald">{{ dashboardData?.weekly_progress?.current_week_km ?? 0 }}</text>
            <text class="dpo-km-sep">/</text>
            <text class="dpo-km-target">{{ dashboardData?.weekly_progress?.target_week_km ?? 50 }}</text>
            <text class="dpo-km-unit">km</text>
          </view>
          <text class="dpo-km-caption">
            周完成/计划 · 剩 {{ dashboardData?.weekly_progress?.remaining_km ?? 0 }}k
          </text>
        </view>

        <!-- 右侧：当月进度饼图卡 -->
        <view class="dpo-card month-card" @click="openGoalSheet('month')">
          <view class="dpo-card-head">
            <text class="dpo-period-title">📅 {{ currentMonth }}月</text>
            <text class="dpo-period-pct primary-text">{{ dashboardData?.progress?.progress_pct || 0 }}%</text>
          </view>

          <view class="dpo-pie-stage">
            <view class="goal-pie-chart dpo-pie month-pie" :style="monthPieStyle">
              <view class="pie-start-spoke" />
              <view class="pie-origin-dot" />
            </view>
          </view>

          <view class="dpo-km-ratio">
            <text class="dpo-km-done primary-text">{{ dashboardData?.progress?.current_month_km || 0 }}</text>
            <text class="dpo-km-sep">/</text>
            <text class="dpo-km-target">{{ dashboardData?.progress?.target_month_km || 200 }}</text>
            <text class="dpo-km-unit">km</text>
          </view>
          <text class="dpo-km-caption">
            月完成/计划 · 剩 {{ dashboardData?.progress?.remaining_km || 0 }}k
          </text>
        </view>
      </view>

      <!-- 7-Day Mon-Sun Weekday Strip -->
      <view class="week-days-strip">
        <view
          v-for="(day, idx) in (dashboardData?.weekly_progress?.daily_breakdown || defaultWeeklyDays)"
          :key="idx"
          class="day-strip-col"
          :class="{ 'is-today': day.is_today, 'has-run': day.distance_km > 0 }"
        >
          <text class="d-name">{{ day.day_name || ('周' + day.short_day) }}</text>
          <text class="d-date">{{ formatShortDayDate(day.date) }}</text>
          <view class="d-val-pill" :class="{ 'active-run': day.distance_km > 0 }">
            <text v-if="day.distance_km > 0" class="d-km-num">{{ day.distance_km }}</text>
            <text v-else-if="day.is_past" class="d-km-dash">—</text>
            <text v-else class="d-km-dash">0</text>
          </view>
        </view>
      </view>

      <!-- Instant Sync, Personal Report & Share Card Action Buttons -->
      <view class="sync-action-box" style="display: flex; gap: 12rpx;">
        <button class="sync-btn" style="flex: 1.3; margin: 0; font-size: 26rpx; padding: 0 14rpx;" :loading="syncing" :disabled="syncing" @click="handleInstantSync">
          <text class="btn-icon" style="font-size: 26rpx;">🔄</text>
          <text style="white-space: nowrap;">{{ compactSyncLabel }}</text>
        </button>
        <button
          class="sync-btn"
          :style="currentTheme === 'volt'
            ? 'flex: 0.95; margin: 0; padding: 0 12rpx; background: #FFF5EE; border: 1rpx solid rgba(252, 76, 2, 0.32); color: #C23800; font-size: 25rpx;'
            : 'flex: 0.95; margin: 0; padding: 0 12rpx; background: linear-gradient(135deg, rgba(16,185,129,0.22) 0%, rgba(5,150,105,0.28) 100%); border: 1rpx solid rgba(16,185,129,0.55); color: #34d399; font-size: 25rpx;'"
          @click="openPersonalReportModal(isMonthlyReportWindow && !isWeeklyReportWindow ? 'month' : 'week')"
        >
          <text class="btn-icon" style="font-size: 26rpx;">📊</text>
          <text style="white-space: nowrap;">周/月报</text>
        </button>
        <button
          class="sync-btn"
          :style="currentTheme === 'volt'
            ? 'flex: 0.85; margin: 0; padding: 0 12rpx; background: #F1F5F9; border: 1rpx solid rgba(15, 23, 42, 0.12); color: #334155; font-size: 25rpx;'
            : 'flex: 0.85; margin: 0; padding: 0 12rpx; background: rgba(255,255,255,0.06); border: 1rpx solid rgba(255,255,255,0.14); color: #e4e4e7; font-size: 25rpx;'"
          @click="openPersonalShareCard()"
        >
          <text class="btn-icon" style="font-size: 26rpx;">📸</text>
          <text style="white-space: nowrap;">分享卡</text>
        </button>
      </view>
    </view>

    <!-- ── 合并减负卡片：身体状态与负荷横条 (一键直达完整生理与VDOT诊断) ── -->
    <view id="rgm-mod-status" class="section-container" :style="{ order: getModuleOrder('status') }">
      <view class="fitness-chart-card readiness-compact-card">
        <view class="fitness-header-top">
          <view class="title-with-desc" style="flex: 0 0 auto;">
            <view class="title-row-with-icon" style="white-space: nowrap;">
              <text class="zap-icon">🔋</text>
              <text class="section-title" style="white-space: nowrap;">状态</text>
              <text class="term-info" @click.stop="explainTerm('fitness')">ⓘ</text>
            </view>
          </view>
          <view class="readiness-header-actions" style="flex-shrink: 0;">
            <view
              class="fitness-status-badge"
              :style="{
                color: fitnessStatusColor,
                backgroundColor: fitnessStatusColor + '24'
              }"
              @click="toggleFitnessChart"
            >
              <text class="fsb-text">{{ fitnessStatusLabel }} · TSB {{ formatTsbVal(dashboardData?.fitness_form?.tsb) }} {{ showFitnessChart ? '▴' : '▾' }}</text>
            </view>
            <text class="sub-date see-all-link" style="white-space: nowrap;" @click="goToBodyData">📊 VDOT ›</text>
          </view>
        </view>

        <!-- 紧凑 4 维核心生理与跑力横条（含实时 VDOT 数值，同时保留右上角快捷键） -->
        <view class="metrics-pill-group metrics-pill-4" @click="goToBodyData">
          <view class="metric-pill">
            <text class="pill-label">🔋 {{ isCorosOnly ? '睡眠' : '电量' }}</text>
            <text class="pill-val text-amber">{{ sleepOrBatteryVal }}</text>
            <text class="pill-sub">{{ sleepOrBatterySub }}</text>
          </view>
          <view class="metric-pill">
            <text class="pill-label">🧬 HRV</text>
            <text class="pill-val text-cyan">{{ dashboardData?.today_health?.hrv_ms != null ? (dashboardData.today_health.hrv_ms + 'ms') : '—' }}</text>
            <text class="pill-sub">{{ dashboardData?.today_health?.hrv_weekly_avg != null ? ('周均 ' + dashboardData.today_health.hrv_weekly_avg + 'ms') : '神经恢复' }}</text>
          </view>
          <view class="metric-pill">
            <text class="pill-label">💓 静息</text>
            <text class="pill-val text-rose">{{ currentRestingHr != null ? (currentRestingHr + 'bpm') : '—' }}</text>
            <text class="pill-sub">{{ dashboardData?.today_health?.night_wear_missing ? '未戴表缺失' : '清晨基线' }}</text>
          </view>
          <view class="metric-pill metric-pill-vdot">
            <text class="pill-label">⚡ VDOT</text>
            <text class="pill-val text-vdot">{{ currentVdot != null ? currentVdot : '—' }}</text>
            <text class="pill-sub">{{ (dashboardData?.fitness_form?.is_recovery_phase && dashboardData?.fitness_form?.peak_vdot) ? ('巅峰 ' + dashboardData.fitness_form.peak_vdot + ' ›') : (currentVo2Max ? ('VO2 ' + currentVo2Max + ' ›') : '跑力诊断 ›') }}</text>
          </view>
        </view>

        <!-- 夜间未佩戴手表 · 恢复数据缺失预警横幅（精简一行 + ⓘ 隐藏说明） -->
        <view
          v-if="dashboardData?.today_health?.night_wear_missing"
          style="margin-top: 12rpx; padding: 12rpx 18rpx; border-radius: 14rpx; background: rgba(245, 158, 11, 0.14); border: 1rpx solid rgba(245, 158, 11, 0.45); display: flex; align-items: center; justify-content: space-between;"
          @click.stop="explainTerm('watch_wear')"
        >
          <text style="font-size: 22rpx; font-weight: 700; color: #b45309;">
            ⚠️ {{ dashboardData?.today_health?.recovery_status_label || '夜间未佩戴 · 恢复数据缺失' }}
          </text>
          <text style="font-size: 21rpx; font-weight: 700; color: #b45309; flex-shrink: 0; margin-left: 12rpx;">ⓘ 详情</text>
        </view>

        <!-- 28天 CTL/ATL/TSB 负荷图：默认收起，点击状态徽章按需展开 -->
        <template v-if="showFitnessChart">
          <view class="metrics-pill-group" style="margin-top: 16rpx;">
            <view class="metric-pill">
              <text class="pill-label">CTL 体能</text>
              <text class="pill-val" style="color: #3b82f6;">{{ formatMetricOneDec(dashboardData?.fitness_form?.ctl) }}</text>
            </view>
            <view class="metric-pill">
              <text class="pill-label">ATL 疲劳</text>
              <text class="pill-val" style="color: #f43f5e;">{{ formatMetricOneDec(dashboardData?.fitness_form?.atl) }}</text>
            </view>
            <view class="metric-pill">
              <text class="pill-label">TSB 状况</text>
              <text class="pill-val" :style="{ color: fitnessStatusColor }">
                {{ formatTsbVal(dashboardData?.fitness_form?.tsb) }}
              </text>
            </view>
          </view>

          <template v-if="fitnessMiniBars.length > 0">
            <view v-if="activeTooltip" class="chart-tooltip" @click="activeTooltip = null">
              <text class="tip-date">{{ activeTooltip.short_date || activeTooltip.date }}</text>
              <text class="tip-val" style="color: #3b82f6;">CTL {{ formatMetricOneDec(activeTooltip.ctl) }}</text>
              <text class="tip-val" style="color: #f43f5e;">ATL {{ formatMetricOneDec(activeTooltip.atl) }}</text>
              <text class="tip-val" :style="{ color: activeTooltip.tsb >= 5 ? '#10b981' : (activeTooltip.tsb >= -30 ? '#3b82f6' : '#f59e0b') }">
                TSB {{ formatTsbVal(activeTooltip.tsb) }}
              </text>
            </view>

            <view class="ios-fitness-mini-chart">
              <view
                v-for="(pt, idx) in fitnessMiniBars"
                :key="pt.date || idx"
                class="ios-bar-col"
                :class="{ 'is-selected': activeTooltip?.date === pt.date }"
                @click="selectFitnessBar(pt)"
              >
                <view class="ios-bar-stack">
                  <view class="ios-bar-atl" :style="{ height: pt.atlPct + '%' }" />
                  <view class="ios-bar-ctl" :style="{ height: pt.ctlPct + '%' }" />
                </view>
              </view>
            </view>

            <view class="ios-fitness-legend">
              <view class="ios-legend-item">
                <view class="ios-legend-dot" style="background-color: #3b82f6;" />
                <text class="ios-legend-label">CTL (体能)</text>
              </view>
              <view class="ios-legend-item">
                <view class="ios-legend-dot" style="background-color: #f43f5e;" />
                <text class="ios-legend-label">ATL (疲劳)</text>
              </view>
              <view class="ios-legend-item">
                <view class="ios-legend-dot" style="background-color: #10b981;" />
                <text class="ios-legend-label">+5 巅峰</text>
              </view>
              <view class="ios-legend-item">
                <view class="ios-legend-dot" style="background-color: #f59e0b;" />
                <text class="ios-legend-label">-30 疲劳</text>
              </view>
            </view>
          </template>
        </template>
      </view>
    </view>

    <!-- ── CARD 2: 最新 1 场运动记录（更多跳转全部记录页） ── -->
    <view id="rgm-mod-recent" class="section-container" :style="{ order: getModuleOrder('recent') }">
      <view class="section-header-row">
        <view class="title-with-pill">
          <text class="section-title">🏃 最新跑步</text>
          <text class="month-active-badge">本月 {{ monthActivitiesList.length }} 次</text>
        </view>
        <text class="sub-date see-all-link" @click="goToAllActivities">全部记录 ›</text>
      </view>

      <view v-if="displayedActivities.length" class="activity-list">
        <view
          v-for="act in displayedActivities"
          :key="act.id"
          class="activity-card"
        >
          <view class="act-top">
            <view class="act-name-group">
              <text class="act-name">{{ act.name }}</text>
              <text v-if="act.workout_effective_vdot" class="act-vdot-tag">⚡ VDOT {{ act.workout_effective_vdot }}</text>
              <text v-if="act.elevation_gain_meters && act.elevation_gain_meters > 0" class="act-elev-tag">⛰️ +{{ Math.round(act.elevation_gain_meters) }}m</text>
            </view>
            <text class="act-time">{{ formatTime(act.start_time) }}</text>
          </view>
          <view class="act-data-row">
            <view class="act-col">
              <text class="act-main-val">{{ act.distance_km }} <text class="unit">km</text></text>
              <text class="act-sub-label">距离</text>
            </view>
            <view class="act-col">
              <text class="act-sub-val">{{ act.avg_pace_str }}</text>
              <text class="act-sub-label">配速</text>
            </view>
            <view class="act-col">
              <text class="act-sub-val">{{ act.average_heartrate || '—' }} <text class="unit">bpm</text></text>
              <text class="act-sub-label">心率</text>
            </view>
            <view class="act-col">
              <text class="act-sub-val text-amber">{{ act.trimp || '—' }}</text>
              <text class="act-sub-label">负荷</text>
            </view>
          </view>

          <!-- GPS Track & Moments Share Card Action Row -->
          <view class="act-track-row act-dual-actions">
            <view
              v-if="act.has_gps_track || act.map_image_url || act.id?.startsWith('garmin_') || act.id?.startsWith('coros_')"
              class="act-track-btn"
              @click.stop="openTrackModal(act)"
            >
              <text class="act-track-icon">🗺️</text>
              <text class="act-track-text">轨迹与分段</text>
              <text class="act-track-arrow">›</text>
            </view>
            <view
              class="act-share-card-btn"
              @click.stop="openPersonalShareCard(act.id)"
            >
              <text class="act-track-icon">📸</text>
              <text class="act-share-text">分享卡</text>
            </view>
          </view>
        </view>

        <!-- 首页只展示最新 1 场，更多记录跳到「全部跑步记录」页 -->
        <view v-if="monthActivitiesList.length > 1" class="expand-acts-toggle" @click="goToAllActivities">
          <text class="expand-acts-text">
            查看本月全部 {{ monthActivitiesList.length }} 次记录 ›
          </text>
        </view>
      </view>
      <view v-else class="empty-act-box">
        <text class="empty-act-text">{{ isDeviceConnected ? '本月暂无记录，跑完后点同步即可' : '绑定手表后自动同步跑步记录' }}</text>
        <button v-if="!isDeviceConnected" class="rgm-empty-cta" @click="goToDeviceBinding">⌚ 绑定手表</button>
        <button v-else class="rgm-empty-cta ghost" :loading="syncing" @click="handleInstantSync">🔄 同步</button>
      </view>
    </view>

    <!-- ── CARD 1.5: 年度跑量统计图表 (Yearly Running Mileage Chart) ── -->
    <view id="rgm-mod-yearly" class="section-container yearly-section" :style="{ order: getModuleOrder('yearly') }">
      <view class="section-header-row year-toggle-row" @click="showYearDetail = !showYearDetail">
        <view class="title-with-desc">
          <text class="section-title">🏆 {{ dashboardData?.yearly_stats?.year || currentYear }} 年度统计</text>
          <text class="sub-formula">
            <template v-if="dashboardData?.yearly_stats?.target_year_km">
              目标 {{ dashboardData.yearly_stats.target_year_km }}k · 月均 {{ dashboardData?.yearly_stats?.monthly_target_km || 0 }}k
            </template>
            <template v-else>未设目标</template>
          </text>
        </view>
        <view class="year-pct-badge">
          <text class="year-pct-num">{{ dashboardData?.yearly_stats?.progress_pct || 0 }}%</text>
          <text class="year-pct-sub">{{ showYearDetail ? '收起 ▴' : '展开 ▾' }}</text>
        </view>
      </view>

      <!-- 年度统计默认折叠：首页优先展示今天和本周 -->
      <view v-if="showYearDetail" class="year-card-body">
        <!-- 1. 年度累计进度条 -->
        <view class="year-progress-box">
          <view class="year-progress-labels">
            <text class="progress-left-label">
              已累计完成 <text class="highlight-val">{{ dashboardData?.yearly_stats?.total_km || 0 }}</text> km
            </text>
            <text v-if="dashboardData?.yearly_stats?.target_year_km" class="progress-right-label">
              剩余 {{ Math.max(0, Math.round(((dashboardData?.yearly_stats?.target_year_km || 0) - (dashboardData?.yearly_stats?.total_km || 0)) * 10) / 10) }} km
            </text>
          </view>
          <view class="year-progress-track">
            <view
              class="year-progress-fill"
              :style="{ width: Math.min(100, dashboardData?.yearly_stats?.progress_pct || 0) + '%' }"
            />
          </view>
        </view>

        <!-- 2. 12 个月跑量柱状图 (12-Month Mileage Bar Chart) -->
        <view class="monthly-chart-box">
          <!-- 选中或交互提示 -->
          <view class="selected-month-tip" v-if="selectedYearMonth">
            <text class="tip-dot">📍</text>
            <text class="tip-text">
              {{ selectedYearMonth.month_label }}：跑量 <text class="tip-hl">{{ selectedYearMonth.distance_km }} km</text> · {{ selectedYearMonth.runs_count }} 次跑步
              <text v-if="selectedYearMonth.is_current" class="tip-tag current">（当前月）</text>
            </text>
          </view>
          <view class="selected-month-tip placeholder" v-else>
            <text class="tip-text-dim">💡 点击柱状图查看</text>
          </view>

          <!-- 12 根立柱 -->
          <view class="months-bar-flex">
            <view
              v-for="m in (dashboardData?.yearly_stats?.monthly_breakdown || defaultMonthlyBreakdown)"
              :key="m.month"
              class="month-bar-col"
              :class="{
                'is-current': m.is_current,
                'is-selected': selectedYearMonth?.month === m.month,
                'is-past': m.is_past && !m.is_current
              }"
              @click="selectYearMonth(m)"
            >
              <!-- 柱顶公里数 (大于等于1km显示) -->
              <view class="bar-val-top">
                <text v-if="m.distance_km >= 1" class="bar-km-text">{{ Math.round(m.distance_km) }}</text>
                <text v-else class="bar-km-empty"></text>
              </view>

              <!-- 立柱轨道与柱体 -->
              <view class="bar-pillar-track">
                <view
                  class="bar-pillar-fill"
                  :style="{ height: getBarHeight(m.distance_km) }"
                  :class="{
                    'current-fill': m.is_current,
                    'past-fill': m.is_past && !m.is_current && m.distance_km > 0,
                    'zero-fill': m.distance_km <= 0
                  }"
                />
              </view>

              <!-- 月份标签 -->
              <view class="bar-month-label">
                <text class="month-name">{{ m.month }}月</text>
                <view v-if="m.is_current" class="current-indicator-dot" />
              </view>
            </view>
          </view>
        </view>

        <!-- 3. 年度 3 维关键指标 -->
        <view class="year-metrics-row">
          <view class="year-metric-tile">
            <view class="m-top">
              <text class="m-icon">🏃</text>
              <text class="m-label">总跑次</text>
            </view>
            <view class="m-val-box">
              <text class="m-val">{{ dashboardData?.yearly_stats?.total_runs || 0 }}</text>
              <text class="m-unit">次</text>
            </view>
          </view>

          <view class="year-metric-tile">
            <view class="m-top">
              <text class="m-icon">📅</text>
              <text class="m-label">月均跑量</text>
            </view>
            <view class="m-val-box">
              <text class="m-val">{{ dashboardData?.yearly_stats?.avg_monthly_km || 0 }}</text>
              <text class="m-unit">km</text>
            </view>
          </view>

          <view class="year-metric-tile">
            <view class="m-top">
              <text class="m-icon">🎯</text>
              <text class="m-label">年终推算</text>
            </view>
            <view class="m-val-box">
              <text class="m-val text-emerald">{{ dashboardData?.yearly_stats?.projected_year_km || 0 }}</text>
              <text class="m-unit">km</text>
            </view>
          </view>
        </view>

        <!-- 4. 年度最佳月份横幅 -->
        <view class="year-best-banner">
          <text class="best-badge">🏅 年度最佳月份</text>
          <text class="best-info">
            {{ dashboardData?.yearly_stats?.best_month?.name || "—" }} · 
            <text class="best-km">{{ dashboardData?.yearly_stats?.best_month?.distance_km || 0 }} km</text>
            <text class="best-pace" v-if="dashboardData?.yearly_stats?.best_month?.avg_pace">（配速 {{ dashboardData?.yearly_stats?.best_month?.avg_pace }}）</text>
          </text>
        </view>
      </view>
    </view>

    <!-- ── 底部「自定义首页板块顺序」常驻入口横条 ── -->
    <view class="home-layout-customize-bar" style="order: 99;" @click="openLayoutOrderModal">
      <text class="hlc-left">↕️ 自定义首页板块显示次序</text>
      <text class="hlc-right">调整顺序 ›</text>
    </view>
    </view>

    <!-- ── 进入小程序首先弹窗：微信跑者授权登录专属弹窗 ── -->
    <view v-if="showAuthModal" class="modal-mask auth-modal-mask" @click="closeAuthModal">
      <view class="modal-content auth-modal-content" @click.stop="noop">
        <view class="modal-header">
          <text class="modal-title">微信跑者授权登录</text>
          <view class="close-hit" @click="closeAuthModal">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <scroll-view scroll-y class="auth-scroll-body">
          <view class="modal-body">
          <view class="wx-brand-hero">
            <image class="wx-hero-logo" src="/static/logo-square.png" mode="aspectFit" />
            <text class="wx-hero-title">万跑跑团助手</text>
            <text class="wx-hero-desc">科学耐力训练 · Garmin 数据直连 · 独立跑者档案</text>
          </view>

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

          <!-- 模式 1: 微信授权登录 -->
          <view v-if="authTab === 'wechat'" class="auth-flow-box">
            <view class="auth-intro-box">
              <text class="auth-intro-title">🛡️ 微信授权安全登录</text>
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
              🟢 微信一键授权安全登录
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
        </scroll-view>
      </view>
    </view>

    <!-- ── 统一周计划/月计划二合一设定半屏弹窗 ── -->
    <GoalSheetModal
      :visible="showWeeklyGoalModal"
      :default-tab="goalSheetDefaultTab"
      :user-id="user?.id"
      :initial-goal="dashboardData?.goal"
      :current-week-locked-km="dashboardData?.weekly_progress?.target_week_km"
      :current-month-locked-km="dashboardData?.progress?.target_month_km"
      :next-week-label="dashboardData?.weekly_progress?.next_week_label"
      @close="closeWeeklyGoalModal"
      @saved="handleHomeGoalSaved"
    />

    <!-- ── 🔔 Canova教练与系统消息中心 Modal ── -->
    <view v-if="showNotificationsModal" class="modal-mask notif-mask" @click="showNotificationsModal = false" @touchmove.stop.prevent>
      <view class="modal-content notif-center-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">🔔 教练与系统通知</text>
            <text v-if="unreadNotifCount > 0" class="notif-count-pill">{{ unreadNotifCount }} 条未读</text>
          </view>
          <view class="header-actions-row">
            <text v-if="unreadNotifCount > 0" class="btn-read-all" @click="handleReadAllNotifications">全部已读</text>
            <text class="close-btn" @click="showNotificationsModal = false">✕</text>
          </view>
        </view>

        <scroll-view scroll-y class="modal-body notif-modal-body">
          <view v-if="loadingNotifications" class="notif-loading-box">
            <text class="loading-text">加载消息中...</text>
          </view>
          <view v-else-if="notificationsList.length === 0" class="notif-empty-box">
            <text class="empty-icon">📭</text>
            <text class="empty-title">暂无新通知</text>
            <text class="empty-desc">跑后点评将在此送达</text>
          </view>
          <view v-else class="notif-list">
            <view
              v-for="item in notificationsList"
              :key="item.id"
              class="notif-card-item"
              :class="{ 'is-unread': !item.is_read }"
              @click="handleNotificationClick(item)"
            >
              <view class="notif-card-top">
                <view class="notif-title-row">
                  <view v-if="!item.is_read" class="unread-dot" />
                  <text class="notif-item-title">{{ item.title }}</text>
                </view>
                <text class="notif-time-tag">{{ formatNotifTime(item.created_at) }}</text>
              </view>
              <text class="notif-content-preview">{{ item.content }}</text>
              <view class="notif-footer-row">
                <text class="notif-action-hint">查看详情 →</text>
              </view>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── 🎯 Canova教练跑后深度点评 / 系统与跑团通知详情 Modal ── -->
    <view
      v-if="selectedCritiqueNotif"
      class="modal-mask critique-detail-mask"
      @click="selectedCritiqueNotif = null"
      @touchmove.stop.prevent
    >
      <view class="modal-content critique-detail-modal" @click.stop>
        <view class="modal-header">
          <view class="critique-header-title-box">
            <view class="critique-header-row">
              <text class="critique-header-icon">{{ isWorkoutCritiqueNotif(selectedCritiqueNotif) ? '🎯' : '🔔' }}</text>
              <text class="modal-title">{{ isWorkoutCritiqueNotif(selectedCritiqueNotif) ? 'Canova教练专属复盘' : '系统与跑团通知' }}</text>
              <text v-if="isWorkoutCritiqueNotif(selectedCritiqueNotif)" class="ai-header-badge">生理量化</text>
            </view>
            <text class="critique-header-sub">{{ isWorkoutCritiqueNotif(selectedCritiqueNotif) ? '仅供参考' : formatNotifTime(selectedCritiqueNotif.created_at) }}</text>
          </view>
          <view class="close-hit" @click="selectedCritiqueNotif = null">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <scroll-view scroll-y class="modal-body critique-detail-body">
          <!-- 关联跑步记录卡片（仅在关联真实训练且有有效距离时展示） -->
          <view
            v-if="hasValidCritiqueActivity"
            class="critique-run-summary-card"
            @click="handleOpenTrackFromCritique"
          >
            <view class="run-sum-top">
              <view class="run-sum-name-row">
                <text class="run-sum-badge">🏃 关联训练</text>
                <text class="run-sum-name">{{ selectedCritiqueActivity?.name || selectedCritiqueNotif.title }}</text>
              </view>
              <text class="run-sum-time">{{ formatNotifTime(selectedCritiqueActivity?.start_time || selectedCritiqueNotif.created_at) }}</text>
            </view>
            <view class="run-sum-metrics">
              <view class="run-metric-item">
                <text class="m-val text-emerald">{{ selectedCritiqueActivity?.distance_km || getDistFromNotif(selectedCritiqueNotif) }} <text class="m-unit">km</text></text>
                <text class="m-lbl">跑步距离</text>
              </view>
              <view class="run-metric-item" v-if="selectedCritiqueActivity?.avg_pace_str">
                <text class="m-val">{{ selectedCritiqueActivity.avg_pace_str }}</text>
                <text class="m-lbl">平均配速</text>
              </view>
              <view class="run-metric-item" v-if="selectedCritiqueActivity?.average_heartrate">
                <text class="m-val text-rose">{{ selectedCritiqueActivity.average_heartrate }} <text class="m-unit">bpm</text></text>
                <text class="m-lbl">平均心率</text>
              </view>
              <view class="run-metric-item" v-if="selectedCritiqueActivity?.elevation_gain_meters">
                <text class="m-val text-amber">+{{ Math.round(selectedCritiqueActivity.elevation_gain_meters) }} <text class="m-unit">m</text></text>
                <text class="m-lbl">累计爬升</text>
              </view>
            </view>
            <view class="run-track-pill-hint">
              <text class="pill-icon">🗺️</text>
              <text class="pill-text">轨迹详情</text>
              <text class="pill-arr">›</text>
            </view>
          </view>

          <!-- 教练评语分块正文 / 系统通知内容 -->
          <view class="critique-sections-list">
            <template v-if="isWorkoutCritiqueNotif(selectedCritiqueNotif)">
              <view
                v-for="(sec, sIdx) in parseCritiqueParagraphs(selectedCritiqueNotif.content)"
                :key="sIdx"
                class="critique-section-card"
                :class="sec.type"
              >
                <view class="sec-header">
                  <text class="sec-icon">{{ sec.icon }}</text>
                  <text class="sec-title">{{ sec.title }}</text>
                </view>
                <text class="sec-text">{{ sec.text }}</text>
              </view>
            </template>
            <view v-else class="critique-section-card general">
              <view class="sec-header">
                <text class="sec-title">{{ selectedCritiqueNotif.title || '通知详情' }}</text>
              </view>
              <text class="sec-text">{{ selectedCritiqueNotif.content }}</text>
            </view>
          </view>

          <!-- 底部操作按钮（精简标识，确保 iOS / Android 单行居中对齐） -->
          <view class="critique-actions-row">
            <template v-if="isWorkoutCritiqueNotif(selectedCritiqueNotif)">
              <button
                v-if="isRealActivityId(selectedCritiqueNotif.activity_id)"
                class="critique-action-btn track-btn"
                @click="handleOpenTrackFromCritique"
              >
                🗺️ 轨迹详情
              </button>
              <button class="critique-action-btn coach-btn" @click="handleGoToCoachFromCritique">
                📅 训练课表
              </button>
            </template>
            <template v-else>
              <button class="critique-action-btn coach-btn" @click="selectedCritiqueNotif = null">
                知道了
              </button>
              <button
                class="critique-action-btn track-btn"
                @click="handleSystemNotifPrimaryAction(selectedCritiqueNotif)"
              >
                {{ getSystemNotifPrimaryLabel(selectedCritiqueNotif) }}
              </button>
            </template>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── GPS 轨迹与高程剖面弹窗 ── -->
    <GpsTrackModal
      :visible="Boolean(selectedTrackActivity)"
      :activity-id="selectedTrackActivity?.id"
      :initial-activity="selectedTrackActivity"
      @close="selectedTrackActivity = null"
      @share-card="handleShareCardFromTrack"
    />

    <!-- ── 个人打卡分享朋友圈卡片弹窗 ── -->
    <PersonalShareCardModal
      :visible="showPersonalShareModal"
      :activity-id="shareCardActivityId"
      @close="showPersonalShareModal = false"
    />

    <!-- ── 个人跑步周报与月报海报/文案弹窗 ── -->
    <PersonalReportModal
      :visible="showPersonalReportModal"
      :default-period-type="personalReportDefaultPeriod"
      @close="showPersonalReportModal = false"
    />

    <!-- ── 📝 今日打卡：训练感受 · 备注 · 照片弹窗 ── -->
    <view
      v-if="showCheckinLogModal"
      class="modal-mask checkin-log-mask"
      @click="showCheckinLogModal = false"
      @touchmove.stop.prevent
    >
      <view class="modal-content checkin-log-modal" @click.stop>
        <view class="modal-header">
          <view style="display: flex; flex-direction: column; gap: 4rpx;">
            <text class="modal-title">📝 训练打卡感受与照片</text>
            <text style="font-size: 20rpx; color: var(--rgm-text-3, #8e8e93);">
              {{ dashboardData?.today_workout?.date || '今日' }} · {{ dashboardData?.today_workout?.title || '今日训练' }}
            </text>
          </view>
          <text class="close-btn" @click="showCheckinLogModal = false">✕</text>
        </view>

        <scroll-view scroll-y class="checkin-log-body">
          <!-- 1. 训练感受标签 -->
          <view class="checkin-field-group">
            <text class="checkin-field-label">😊 今日训练感受</text>
            <view class="checkin-feel-grid">
              <view
                v-for="tag in FEELING_TAG_OPTIONS"
                :key="tag"
                class="checkin-feel-chip"
                :class="{ active: checkinForm.feeling_tag === tag }"
                @click="checkinForm.feeling_tag = checkinForm.feeling_tag === tag ? '' : tag"
              >
                <text class="checkin-feel-txt">{{ tag }}</text>
              </view>
            </view>
          </view>

          <!-- 2. 主观疲劳度 RPE (1-10) -->
          <view class="checkin-field-group">
            <view style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10rpx;">
              <text class="checkin-field-label" style="margin-bottom: 0;">🔥 主观体感强度 (RPE 1-10)</text>
              <text style="font-size: 20rpx; color: var(--rgm-text-3, #8e8e93);">1-3轻松 · 4-6适中 · 7-8吃力 · 9-10极限</text>
            </view>
            <view class="checkin-rpe-row">
              <view
                v-for="n in 10"
                :key="n"
                class="checkin-rpe-pill"
                :class="{
                  active: checkinForm.rpe === n,
                  easy: checkinForm.rpe === n && n <= 3,
                  mod: checkinForm.rpe === n && n >= 4 && n <= 6,
                  hard: checkinForm.rpe === n && n >= 7 && n <= 8,
                  max: checkinForm.rpe === n && n >= 9
                }"
                @click="checkinForm.rpe = checkinForm.rpe === n ? null : n"
              >
                <text>{{ n }}</text>
              </view>
            </view>
          </view>

          <!-- 3. 训练备注与心得 -->
          <view class="checkin-field-group">
            <text class="checkin-field-label">💬 训练备注与心得</text>
            <textarea
              v-model="checkinForm.athlete_notes"
              class="checkin-notes-textarea"
              placeholder="记录配速体感、心率波动、补给状态、天气路况或小腿/膝踝反应..."
              maxlength="300"
            />
          </view>

          <!-- 4. 训练打卡照片 (最多 3 张) -->
          <view class="checkin-field-group">
            <view style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12rpx;">
              <text class="checkin-field-label" style="margin-bottom: 0;">📸 打卡照片（最多 3 张）</text>
              <text style="font-size: 20rpx; color: var(--rgm-text-3, #8e8e93);">
                {{ checkinForm.workout_photos.length + checkinForm.new_photos_preview.length }}/3
              </text>
            </view>
            <view class="checkin-photo-uploader-grid">
              <!-- 已保存照片 -->
              <view
                v-for="(url, idx) in checkinForm.workout_photos"
                :key="'saved_' + idx"
                class="checkin-photo-item"
              >
                <image
                  :src="url"
                  mode="aspectFill"
                  class="checkin-photo-img"
                  @click="previewWorkoutPhotos([...checkinForm.workout_photos, ...checkinForm.new_photos_preview], Number(idx))"
                />
                <view class="checkin-photo-del" @click.stop="removeSavedWorkoutPhoto(Number(idx))">✕</view>
              </view>

              <!-- 新选择待上传照片 -->
              <view
                v-for="(pUrl, nIdx) in checkinForm.new_photos_preview"
                :key="'new_' + nIdx"
                class="checkin-photo-item"
              >
                <image
                  :src="pUrl"
                  mode="aspectFill"
                  class="checkin-photo-img"
                  @click="previewWorkoutPhotos([...checkinForm.workout_photos, ...checkinForm.new_photos_preview], checkinForm.workout_photos.length + Number(nIdx))"
                />
                <view class="checkin-photo-del" @click.stop="removeNewWorkoutPhoto(Number(nIdx))">✕</view>
              </view>

              <!-- 添加按钮 -->
              <view
                v-if="checkinForm.workout_photos.length + checkinForm.new_photos_preview.length < 3"
                class="checkin-photo-add"
                @click="handleChooseWorkoutPhoto"
              >
                <text class="add-plus">📷</text>
                <text class="add-txt">添加照片</text>
              </view>
            </view>
          </view>
        </scroll-view>

        <view class="checkin-modal-footer">
          <button class="checkin-cancel-btn" @click="showCheckinLogModal = false">取消</button>
          <button class="checkin-save-btn" :loading="savingCheckinLog" @click="saveCheckinLog">
            💾 保存打卡
          </button>
        </view>
      </view>
    </view>

    <!-- ── ↕️ 自定义首页板块显示次序弹窗 (User-Customizable Homepage Module Order) ── -->
    <view v-if="showLayoutOrderModal" class="modal-mask layout-order-mask" @click="showLayoutOrderModal = false">
      <view class="modal-content layout-order-modal" @click.stop="noop">
        <view class="modal-header">
          <text class="modal-title">↕️ 自定义首页板块顺序</text>
          <view class="close-hit" @click="showLayoutOrderModal = false">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="layout-order-body">
          <text class="layout-order-desc">
            自由调整首页 7 大核心板块的上下显示次序，保存后立即生效并自动记忆在您的手机上。
          </text>

          <view class="layout-order-list">
            <view
              v-for="(modKey, idx) in homeModuleOrderDraft"
              :key="modKey"
              class="layout-order-item"
            >
              <view class="loi-left">
                <view class="loi-rank-badge">{{ idx + 1 }}</view>
                <text class="loi-icon">{{ getModuleMeta(modKey).icon }}</text>
                <view class="loi-text-col">
                  <text class="loi-title">{{ getModuleMeta(modKey).title }}</text>
                  <text class="loi-sub">{{ getModuleMeta(modKey).desc }}</text>
                </view>
              </view>

              <view class="loi-actions">
                <view
                  v-if="idx > 0"
                  class="loi-btn top-btn"
                  @click="pinModuleToTop(Number(idx))"
                >
                  <text class="loi-btn-txt">置顶</text>
                </view>
                <view
                  class="loi-btn arrow-btn"
                  :class="{ disabled: idx === 0 }"
                  @click="moveModuleOrder(Number(idx), -1)"
                >
                  <text class="loi-btn-txt">↑</text>
                </view>
                <view
                  class="loi-btn arrow-btn"
                  :class="{ disabled: idx === homeModuleOrderDraft.length - 1 }"
                  @click="moveModuleOrder(Number(idx), 1)"
                >
                  <text class="loi-btn-txt">↓</text>
                </view>
              </view>
            </view>
          </view>

          <view class="layout-order-footer">
            <button class="loi-footer-btn reset" @click="resetHomeModuleOrder">恢复默认</button>
            <button class="loi-footer-btn save" @click="saveHomeModuleOrder">✓ 保存顺序</button>
          </view>
        </view>
      </view>
    </view>

    <!-- 微信隐私保护指引授权弹窗 -->
    <PrivacyPopup proactive />
  </view>
</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme, chartPalette } from "../../utils/theme";
import { explainTerm } from "../../utils/glossary";
import { trackClick, trackModal, observeModuleExposures, getCurrentSessionId } from "../../utils/telemetry";
import PrivacyPopup from "../../components/PrivacyPopup.vue";
import PageSkeleton from "../../components/PageSkeleton.vue";
import GoalSheetModal from "../../components/GoalSheetModal.vue";
import { ref, computed, onMounted, onUnmounted, getCurrentInstance, nextTick, watch } from "vue";
import { onPullDownRefresh, onShow, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import GpsTrackModal from "../../components/GpsTrackModal.vue";
import PersonalShareCardModal from "../../components/PersonalShareCardModal.vue";
import PersonalReportModal from "../../components/PersonalReportModal.vue";
import {
  fetchMyNextGroupRun,
  formatMeetTime,
  getCountdownText,
  addRunToCalendar,
  openRunLocation,
  openTeamEvents,
  openGroupRunDetail,
  isGroupRunPostStage,
  buildGroupRunSharePayload,
} from "../../utils/groupRun";
import {
  request,
  getStoredUser,
  authenticateWechatUser,
  deviceLogin,
  uploadAvatarFile,
  chooseAndImportTrackFile,
  chooseAndImportScreenshot,
  UserProfile,
  syncTabBarIndex,
  checkAndPromptOrgReminder,
  navigateToProfileRequiredFields,
  navigateToDeviceBinding,
  OrgReminderInfo,
  formatBeijingTime,
} from "../../utils/api";

const pendingOrgReminder = ref<OrgReminderInfo | null>(null);

// ── 我的下一场约跑（首页卡片） ──
const myNextRun = ref<any>(null);
async function loadMyNextRun(explicitUid?: string) {
  const uid = explicitUid || user.value?.id || getStoredUser()?.id;
  if (!uid) {
    myNextRun.value = null;
    return;
  }
  try {
    myNextRun.value = await fetchMyNextGroupRun(uid);
  } catch (e) {
    // 约跑卡片是附加信息，失败时静默隐藏
    myNextRun.value = null;
  }
}
function goToFillRequiredFields() {
  navigateToProfileRequiredFields();
}

// ── 🚀 新手跑者设定向导 ──
const onboardStatus = ref<any>(null);
const showOnboardReminder = ref(false);
// 关闭后 7 天内不再出现（原先只存在内存，每次启动都会重新弹出）
const ONBOARD_DISMISS_KEY = "rgm_onboard_banner_dismissed_at";
const ONBOARD_DISMISS_MS = 7 * 24 * 3600 * 1000;
const onboardDismissed = ref(
  (() => {
    try {
      const ts = Number(uni.getStorageSync(ONBOARD_DISMISS_KEY) || 0);
      return ts > 0 && Date.now() - ts < ONBOARD_DISMISS_MS;
    } catch (_) {
      return false;
    }
  })()
);
function dismissOnboardBanner() {
  onboardDismissed.value = true;
  try {
    uni.setStorageSync(ONBOARD_DISMISS_KEY, Date.now());
  } catch (_) {}
}

// ── ✅ 新手任务清单 ──
// 每一项都按「真实完成状态」判断（不看向导里的“跳过”标记），全部完成后卡片自动消失；
// 点 ✕ 后 7 天内不再出现（沿用 ONBOARD_DISMISS_KEY）。
const starterCollapsed = ref(false);
const starterTasks = computed(() => {
  const st = onboardStatus.value || {};
  const steps = st.steps || {};
  const details = st.details || {};
  const deviceBound = !!(
    details.garmin_connected ||
    details.coros_connected ||
    details.apple_watch_connected ||
    details.huawei_connected ||
    details.suunto_connected ||
    isDeviceConnected.value
  );
  const u = dashboardData.value?.user || user.value;
  const isTrackWatchOnly =
    !(details.garmin_connected || details.coros_connected || u?.garmin_connected || u?.coros_connected) &&
    !!(details.huawei_connected || details.apple_watch_connected || details.suunto_connected || u?.huawei_connected || u?.apple_watch_connected || u?.suunto_connected);
  const monthActs = dashboardData.value?.current_month_activities;
  const hasActivities = Number(details.activity_count || 0) > 0 || (Array.isArray(monthActs) && monthActs.length > 0);
  const syncDone = hasActivities || !!steps.history || !!details.history_skipped;
  const syncDesc = !deviceBound
    ? "绑定手表后即可同步"
    : isTrackWatchOnly
      ? "选运动截图一键导入（支持苹果健康多日列表）或导入 FIT/GPX 轨迹"
      : "一键导入你的历史跑步记录";
  return [
    { key: "device", title: "绑定运动手表", desc: "支持佳明 / 高驰 / 苹果 / 华为 / 颂拓手表直连与导入", cta: "去绑定", done: deviceBound },
    { key: "sync", title: "完成首次同步", desc: syncDesc, cta: deviceBound ? (isTrackWatchOnly ? "去导入" : "去同步") : "先绑定", done: syncDone },
    { key: "goal", title: "设定周跑量目标", desc: "首页会按目标显示每周进度", cta: "去设定", done: !!steps.goals },
    { key: "club", title: "加入一个跑团", desc: "和跑友一起打卡、看排行榜", cta: "去看看", done: !!steps.club },
    { key: "plan", title: "生成我的训练课表", desc: "设定目标赛事，Canova 教练定制每日课表", cta: "去生成", done: !!dashboardData.value?.today_workout },
  ];
});
const starterDoneCount = computed(() => starterTasks.value.filter((t) => t.done).length);
const showStarterTasks = computed(
  () => !!onboardStatus.value && !onboardDismissed.value && starterDoneCount.value < starterTasks.value.length
);
function runStarterTask(key: string, done: boolean) {
  if (done) return;
  switch (key) {
    case "device":
      goToDeviceBinding();
      break;
    case "sync":
      // 未绑定时 handleInstantSync 会自动引导到绑定页
      handleInstantSync();
      break;
    case "goal":
      openWeeklyGoalModal();
      break;
    case "club":
      uni.switchTab({ url: "/pages/team/team" });
      break;
    case "plan":
      goToCoachPage();
      break;
  }
}

// 右上角设备徽章 / 空状态"去绑定手表"
function goToDeviceBinding(brand?: "garmin" | "coros", autoOpenModal: boolean = false) {
  trackClick("home_go_bind_device", "首页点击「绑表/设备状态」", { brand: brand || "any" });
  const u = dashboardData.value?.user || user.value;
  if (!brand && u?.coros_connected && u?.coros_needs_reauth) {
    navigateToDeviceBinding("coros", true);
    return;
  }
  navigateToDeviceBinding(brand, autoOpenModal);
}

// 当月运动记录 → 全部跑步记录页
function goToAllActivities() {
  trackClick("home_go_all_activities", "首页点击「全部跑步记录」");
  uni.navigateTo({ url: "/pages/activities/activities" });
}

// 生理与恢复 → 身体数据与跑力分析（原【深度分析】Tab）
function goToBodyData() {
  trackClick("home_go_body_analysis", "首页点击「身体数据与跑力分析」");
  uni.navigateTo({ url: "/pages/analysis/analysis" });
}

function goToOnboarding() {
  trackClick("home_go_onboarding", "首页点击「新手设定向导」");
  uni.navigateTo({
    url: "/pages/onboarding/onboarding",
  });
}

// ── 🚀 小程序开启页状态 ──

const selectedTrackActivity = ref<any>(null);
function openTrackModal(act: any) {
  selectedTrackActivity.value = act;
}

const showPersonalShareModal = ref(false);
const shareCardActivityId = ref<string>("");

function openPersonalShareCard(actId?: string) {
  shareCardActivityId.value = actId || "";
  showPersonalShareModal.value = true;
}

function handleShareCardFromTrack(actId?: string) {
  selectedTrackActivity.value = null;
  openPersonalShareCard(actId);
}


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
const agreedTerms = ref(false);
const confirmingLogin = ref(false);

const showNotificationsModal = ref(false);
const notificationsList = ref<any[]>([]);
const unreadNotifCount = ref(0);
const loadingNotifications = ref(false);

const selectedCritiqueNotif = ref<any>(null);
const selectedCritiqueActivity = ref<any>(null);

function getDistFromNotif(notif: any): string {
  if (!notif) return "";
  const match = (notif.title || "").match(/([\d\.]+)km/i);
  return match ? match[1] : "";
}

function isRealActivityId(actId?: string | null): boolean {
  if (!actId || typeof actId !== "string") return false;
  const trimmed = actId.trim();
  if (!trimmed) return false;
  if (
    trimmed.startsWith("org_") ||
    trimmed.startsWith("club_") ||
    trimmed.includes(":review:") ||
    trimmed.includes(":d")
  ) {
    return false;
  }
  return true;
}

function isWorkoutCritiqueNotif(notif: any): boolean {
  if (!notif) return false;
  const nType = String(notif.type || "").toLowerCase();
  if (nType.startsWith("org_") || nType.startsWith("club_") || nType === "system") {
    return false;
  }
  const titleStr = String(notif.title || "");
  if (titleStr.includes("待审核") || titleStr.includes("恢复资格") || titleStr.includes("资料")) {
    return false;
  }
  if (nType === "coach_critique" || nType === "ai_critique") {
    return true;
  }
  return isRealActivityId(notif.activity_id);
}

const hasValidCritiqueActivity = computed(() => {
  const notif = selectedCritiqueNotif.value;
  if (!notif || !isWorkoutCritiqueNotif(notif)) return false;
  if (selectedCritiqueActivity.value && Number(selectedCritiqueActivity.value.distance_km) > 0) {
    return true;
  }
  const parsedDist = getDistFromNotif(notif);
  return Boolean(parsedDist && Number(parsedDist) > 0);
});

function getSystemNotifPrimaryLabel(notif: any): string {
  const nType = String(notif?.type || "").toLowerCase();
  const titleStr = String(notif?.title || "");
  if (nType.includes("onboarding_reminder")) {
    return "⚙️ 绑表 / 定目标";
  }
  if (nType.includes("profile")) {
    return "📝 补齐资料";
  }
  if (nType === "club_new_member" && titleStr.includes("新队员入团")) {
    return "🌱 查看新队员状态";
  }
  return "👥 前往跑团";
}

function handleSystemNotifPrimaryAction(notif: any) {
  const nType = String(notif?.type || "").toLowerCase();
  const titleStr = String(notif?.title || "");
  selectedCritiqueNotif.value = null;
  if (nType.includes("onboarding_reminder")) {
    uni.navigateTo({ url: "/pages/onboarding/onboarding" });
    return;
  }
  if (nType.includes("profile")) {
    syncTabBarIndex(4);
    uni.switchTab({ url: "/pages/profile/profile" });
    return;
  }
  if (nType === "club_new_member" && titleStr.includes("新队员入团")) {
    try {
      uni.setStorageSync("rgm_team_open_section", "new_members");
    } catch (_) {}
  }
  syncTabBarIndex(2);
  uni.switchTab({ url: "/pages/team/team" });
}

interface CritiqueSection {
  type: "special" | "advice" | "target" | "general";
  icon: string;
  title: string;
  text: string;
}

function parseCritiqueParagraphs(raw: string): CritiqueSection[] {
  if (!raw) return [];
  const text = raw.trim();
  const sections: CritiqueSection[] = [];

  const adviceIdx = text.indexOf("💡");
  const targetIdx = text.indexOf("⚡");

  if (adviceIdx !== -1) {
    const part1 = text.slice(0, adviceIdx).trim();
    if (part1) {
      let title = "专项负荷与能力刺激诊断";
      let body = part1;
      const bracketMatch = part1.match(/^【(.*?)】/);
      if (bracketMatch) {
        title = bracketMatch[1];
        body = part1.slice(bracketMatch[0].length).trim();
      }
      sections.push({
        type: "special",
        icon: "🎯",
        title: title || "专项负荷诊断",
        text: body || part1,
      });
    }

    if (targetIdx !== -1 && targetIdx > adviceIdx) {
      const part2 = text.slice(adviceIdx, targetIdx).trim();
      const body2 = part2.replace(/^💡\s*(教练建议[:：]?\s*)?/, "").trim();
      sections.push({
        type: "advice",
        icon: "💡",
        title: "恢复与肌筋膜调理建议",
        text: body2,
      });

      const part3 = text.slice(targetIdx).trim();
      const body3 = part3.replace(/^⚡\s*/, "").trim();
      sections.push({
        type: "target",
        icon: "⚡",
        title: "下阶段边际增益策略",
        text: body3,
      });
    } else {
      const part2 = text.slice(adviceIdx).trim();
      const body2 = part2.replace(/^💡\s*(教练建议[:：]?\s*)?/, "").trim();
      sections.push({
        type: "advice",
        icon: "💡",
        title: "恢复与肌筋膜调理建议",
        text: body2,
      });
    }
  } else if (targetIdx !== -1) {
    const part1 = text.slice(0, targetIdx).trim();
    if (part1) {
      sections.push({
        type: "special",
        icon: "🎯",
        title: "Canova 专项诊断",
        text: part1,
      });
    }
    const part2 = text.slice(targetIdx).trim().replace(/^⚡\s*/, "");
    sections.push({
      type: "target",
      icon: "⚡",
      title: "下阶段边际增益策略",
      text: part2,
    });
  } else {
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length > 1) {
      lines.forEach((l, idx) => {
        sections.push({
          type: "general",
          icon: idx === 0 ? "🎯" : "💬",
          title: idx === 0 ? "Canova 专项诊断" : `复盘要点 ${idx + 1}`,
          text: l,
        });
      });
    } else {
      sections.push({
        type: "general",
        icon: "🎯",
        title: "Canova 教练专属复盘",
        text,
      });
    }
  }

  return sections;
}

async function loadNotifications() {
  const u = user.value || getStoredUser();
  if (!u?.id) return;
  try {
    const res = await request(`/api/notifications?user_id=${u.id}&limit=20`);
    if (res?.success) {
      notificationsList.value = res.notifications || [];
      unreadNotifCount.value = res.unread_count || 0;
    }
  } catch (e) {
    console.error("Load notifications error:", e);
  }
}

function openNotificationsModal() {
  showNotificationsModal.value = true;
  loadingNotifications.value = true;
  loadNotifications().finally(() => {
    loadingNotifications.value = false;
  });
}

async function handleNotificationClick(item: any) {
  const u = user.value || getStoredUser();
  if (u?.id && !item.is_read) {
    item.is_read = 1;
    unreadNotifCount.value = Math.max(0, unreadNotifCount.value - 1);
    request(`/api/notifications/${item.id}/read?user_id=${u.id}`, "POST").catch(() => {});
  }
  showNotificationsModal.value = false;

  // Open the critique detail modal to display full commentary
  selectedCritiqueNotif.value = item;
  selectedCritiqueActivity.value = null;

  if (isWorkoutCritiqueNotif(item) && isRealActivityId(item.activity_id)) {
    const cached = dashboardData.value?.recent_activities?.find(
      (a: any) => a.id === item.activity_id
    );
    if (cached) {
      selectedCritiqueActivity.value = cached;
    } else {
      try {
        const res: any = await request(`/api/miniapp/activities/${item.activity_id}/track`);
        if (res?.success && res.activity) {
          selectedCritiqueActivity.value = {
            ...res.activity,
            has_gps_track: res.has_track,
            map_image_url: res.map_image_url,
          };
        }
      } catch (e) {
        console.warn("Fetch activity for critique modal failed:", e);
      }
    }
  }
}

function handleOpenTrackFromCritique() {
  const notif = selectedCritiqueNotif.value;
  const act =
    selectedCritiqueActivity.value ||
    (notif?.activity_id
      ? {
          id: notif.activity_id,
          name: notif.title,
          ai_journal: notif.content,
        }
      : null);

  if (act) {
    selectedCritiqueNotif.value = null;
    openTrackModal(act);
  }
}

function handleGoToCoachFromCritique() {
  selectedCritiqueNotif.value = null;
  syncTabBarIndex(1);
  uni.switchTab({ url: "/pages/coach/coach" });
}

onLoad(async (options: any) => {
  initShareMenu();
  if (options?.activity_id) {
    const actId = options.activity_id;
    try {
      const res: any = await request(`/api/miniapp/activities/${actId}/track`);
      if (res?.success && res.activity) {
        const act = {
          ...res.activity,
          has_gps_track: res.has_track,
          map_image_url: res.map_image_url,
        };
        if (act.ai_journal) {
          selectedCritiqueNotif.value = {
            id: `notif_${actId}`,
            activity_id: actId,
            title: act.name || "Canova 训练点评",
            content: act.ai_journal,
            created_at: act.start_time || new Date().toISOString(),
          };
          selectedCritiqueActivity.value = act;
        } else {
          openTrackModal(act);
        }
      }
    } catch (e) {
      console.warn("Load activity from onLoad query error:", e);
    }
  }
});

onShareAppMessage((res: any) => {
  const dataset = res?.target?.dataset || {};
  const shareType = dataset.shareType || dataset["share-type"];
  if (shareType === "group_run" && myNextRun.value) {
    return buildGroupRunSharePayload(
      myNextRun.value,
      myNextRun.value.club_name,
      user.value?.id || getStoredUser()?.id
    );
  }
  return getUnifiedShareAppMessage();
});

onShareTimeline(() => {
  return getUnifiedShareTimeline();
});

async function handleReadAllNotifications() {
  const u = user.value || getStoredUser();
  if (!u?.id) return;
  try {
    await request("/api/notifications/read-all", "POST", { user_id: u.id });
    notificationsList.value.forEach((n) => (n.is_read = 1));
    unreadNotifCount.value = 0;
    uni.showToast({ title: "全部已读", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "操作失败", icon: "none" });
  }
}

function formatNotifTime(timeStr: string) {
  return formatBeijingTime(timeStr, false);
}
const defaultAvatar =
  "https://thirdwx.qlogo.cn/mmopen/vi_32/POgEwh4mIHO4nibH0KlMECNjjGxQUq24ZEaGT4poC6icRiccVGKSyXwibcPq4ozAawiaYbCQTvDVxp4UMxN5UulpDixA/132";

// ── 无数据时的占位结构：全部根据当前日期生成，避免写死年份/月份误导新用户 ──
const _now = new Date();
const currentYear = _now.getFullYear();
const _curMonth = _now.getMonth() + 1; // 1-12
const _todayIdx = (_now.getDay() + 6) % 7; // 周一=0
const _weekNames = ["一", "二", "三", "四", "五", "六", "日"];

const defaultWeeklyDays = _weekNames.map((d, i) => ({
  day_idx: i,
  day_name: `周${d}`,
  short_day: d,
  date: "--/--",
  distance_km: 0,
  runs_count: 0,
  is_today: i === _todayIdx,
  is_past: i < _todayIdx,
}));

function buildRecentMonths(count: number) {
  const out: any[] = [];
  for (let k = count - 1; k >= 0; k--) {
    const d = new Date(currentYear, _curMonth - 1 - k, 1);
    out.push({
      month_label: `${d.getFullYear()}/${d.getMonth() + 1}月`,
      distance_km: 0.0,
      count: 0,
      is_current: k === 0,
    });
  }
  return out;
}

function buildYearBreakdown() {
  return Array.from({ length: 12 }, (_, i) => {
    const m = i + 1;
    return {
      month: m,
      month_label: `${m}月`,
      distance_km: 0,
      runs_count: 0,
      is_current: m === _curMonth,
      is_past: m < _curMonth,
    };
  });
}

const emptyData = {
  user: {
    display_name: "微信跑者",
    garmin_connected: false,
    coros_connected: false,
    resting_heart_rate: null,
    max_heart_rate: null,
    vo2max: null,
  },
  fitness_form: {
    ctl: 0.0,
    atl: 0.0,
    tsb: 0.0,
    status_label: "未连接",
    status_color: "#6b7280",
    history: [],
  },
  weekly_progress: {
    week_number: 1,
    week_label: "本周",
    week_start: "",
    week_end: "",
    current_week_km: 0.0,
    target_week_km: 50.0,
    total_runs: 0,
    progress_pct: 0.0,
    remaining_km: 50.0,
    days_left_in_week: 7,
    daily_required_km: 7.1,
    daily_breakdown: defaultWeeklyDays,
  },
  progress: {
    current_month_km: 0.0,
    target_month_km: 200.0,
    progress_pct: 0.0,
    remaining_km: 200.0,
    days_left_in_month: 28,
    daily_required_km: 0.0,
  },
  monthly_trend: {
    trend: buildRecentMonths(6),
    current_month_km: 0.0,
    prev_month_km: 0.0,
    pct_change: 0.0,
    recent_3_months: buildRecentMonths(3).map(({ is_current, ...rest }) => rest),
  },
  yearly_stats: {
    year: currentYear,
    total_km: 0.0,
    total_runs: 0,
    avg_monthly_km: 0.0,
    projected_year_km: 0.0,
    // 未加载/未设定时不展示虚构目标
    target_year_km: 0,
    monthly_target_km: 0,
    progress_pct: 0.0,
    best_month: {
      name: "—",
      distance_km: 0.0,
      avg_pace: "—",
    },
    monthly_breakdown: buildYearBreakdown(),
  },
  today_health: null,
  recent_activities: [],
  ai_coach_tip: "欢迎使用万跑跑团助手！请在【我的】页面登录微信并绑定佳明设备以开启科学耐力训练分析。",
};

const defaultMonthlyBreakdown = buildYearBreakdown();

function readCachedDashboardSnapshot(uid?: string): any | null {
  if (!uid) return null;
  try {
    const cached = uni.getStorageSync(`rgm_dashboard_cache_${uid}`);
    if (cached && typeof cached === "object" && cached.progress) {
      return cached;
    }
  } catch (_) {}
  return null;
}

function writeCachedDashboardSnapshot(uid: string, data: any) {
  if (!uid || !data || !data.progress) return;
  try {
    const slimActs = (arr: any[]) =>
      Array.isArray(arr)
        ? arr.slice(0, 12).map((a: any) => {
            if (!a || typeof a !== "object") return a;
            const { gps_track_data, laps_data, splits_data, segment_analysis_json, ...rest } = a;
            return rest;
          })
        : arr;
    const slim = {
      ...data,
      current_month_activities: slimActs(data.current_month_activities),
      recent_activities: slimActs(data.recent_activities),
    };
    uni.setStorageSync(`rgm_dashboard_cache_${uid}`, slim);
  } catch (_) {}
}

const initialStoredUser = getStoredUser();
const initialCachedDashboard = readCachedDashboardSnapshot(initialStoredUser?.id);
if (initialStoredUser?.id) {
  try {
    const cachedOnboard = uni.getStorageSync(`rgm_onboard_status_${initialStoredUser.id}`);
    if (cachedOnboard && typeof cachedOnboard === "object") {
      onboardStatus.value = cachedOnboard;
      showOnboardReminder.value = !(cachedOnboard.is_completed ?? cachedOnboard.is_fully_completed);
    }
  } catch (_) {}
}

const user = ref<UserProfile | null>(initialStoredUser || null);
const dashboardData = ref<any>(initialCachedDashboard || emptyData);
// 若本地已有上次快照则首屏 0ms 直接上屏（跳过骨架屏），后台静默刷新
const firstLoadPending = ref(!initialCachedDashboard);
const dashboardLoadError = ref(false);
let lastDashboardFetchAt = 0;
let fitnessChartTimer: ReturnType<typeof setTimeout> | null = null;

function scheduleFitnessChart(delayMs: number = 140) {
  if (fitnessChartTimer) {
    clearTimeout(fitnessChartTimer);
  }
  fitnessChartTimer = setTimeout(() => {
    fitnessChartTimer = null;
    drawFitnessChart();
  }, delayMs);
}

const showAllMonthActs = ref(false);
const monthActivitiesList = computed(() => {
  return dashboardData.value?.current_month_activities || dashboardData.value?.recent_activities || [];
});
// 首页精简：只展示最新 1 场跑步记录（月初尚无当月记录时回退展示最近 1 场历史记录）
const displayedActivities = computed(() => {
  if (monthActivitiesList.value.length > 0) {
    return monthActivitiesList.value.slice(0, 1);
  }
  const recent = dashboardData.value?.recent_activities;
  return Array.isArray(recent) && recent.length > 0 ? recent.slice(0, 1) : [];
});

// 年度统计：默认折叠（仅当用户主动展开过记为 "1" 时展开，大幅缩短首屏滚动高度）；体能曲线默认折叠
const storedYearExpanded = uni.getStorageSync("rgm_home_year_expanded");
const showYearDetail = ref(storedYearExpanded === 1 || storedYearExpanded === "1");
const showFitnessChart = ref(!!uni.getStorageSync("rgm_home_fitness_expanded"));
watch(showYearDetail, (v) => uni.setStorageSync("rgm_home_year_expanded", v ? "1" : "0"));
function toggleFitnessChart() {
  showFitnessChart.value = !showFitnessChart.value;
  uni.setStorageSync("rgm_home_fitness_expanded", showFitnessChart.value ? 1 : "");
  if (showFitnessChart.value) {
    nextTick(() => setTimeout(drawFitnessChart, 150));
  }
}

const activeGoalTab = ref<'week' | 'month'>('week');
const goalSheetDefaultTab = ref<'week' | 'month'>('week');

// ── ↕️ 首页板块自定义显示次序 + 周/月完成度饼图样式 ──
type HomeModuleKey = 'nextrun' | 'feed' | 'today' | 'goal' | 'status' | 'recent' | 'yearly';
const HOME_MODULE_STORAGE_KEY = 'rgm_home_module_order_v1';
const DEFAULT_HOME_MODULE_ORDER: HomeModuleKey[] = [
  'nextrun',
  'feed',
  'today',
  'goal',
  'status',
  'recent',
  'yearly',
];
const HOME_MODULE_META: Record<HomeModuleKey, { icon: string; title: string; desc: string }> = {
  nextrun: { icon: '🏃', title: '我的下一场约跑', desc: '已报名且未结束的跑团约跑活动提醒' },
  feed: { icon: '🔥', title: '跑团打卡动态', desc: '跑友最新打卡与教练点评快捷入口' },
  today: { icon: '📅', title: '今日训练课表', desc: '今日教练训练安排、一键打卡与感受照片记录' },
  goal: { icon: '🎯', title: '周/月目标完成度', desc: '周/月同屏完成度饼图、7日打卡条与同步分享' },
  status: { icon: '🔋', title: '生理状态与跑力诊断', desc: '电量/睡眠、HRV、静息心率与 VDOT' },
  recent: { icon: '👟', title: '最新跑步记录', desc: '最近一场跑步详情、轨迹分段与分享卡' },
  yearly: { icon: '🏆', title: '年度跑量统计', desc: '12个月跑量柱状图与年终推算' },
};

function sanitizeModuleOrder(raw: unknown): HomeModuleKey[] {
  if (!Array.isArray(raw)) return [...DEFAULT_HOME_MODULE_ORDER];
  const valid = raw.filter(
    (k): k is HomeModuleKey => typeof k === 'string' && (DEFAULT_HOME_MODULE_ORDER as string[]).includes(k)
  );
  const unique = Array.from(new Set(valid));
  if (!unique.includes('today')) {
    const goalIdx = unique.indexOf('goal');
    if (goalIdx >= 0) {
      unique.splice(goalIdx, 0, 'today');
    } else {
      unique.push('today');
    }
  }
  for (const defKey of DEFAULT_HOME_MODULE_ORDER) {
    if (!unique.includes(defKey)) unique.push(defKey);
  }
  return unique;
}

const homeModuleOrder = ref<HomeModuleKey[]>(
  (() => {
    try {
      const saved = uni.getStorageSync(HOME_MODULE_STORAGE_KEY);
      if (saved) {
        const parsed = typeof saved === 'string' ? JSON.parse(saved) : saved;
        return sanitizeModuleOrder(parsed);
      }
    } catch (_) {}
    return [...DEFAULT_HOME_MODULE_ORDER];
  })()
);
const homeModuleOrderDraft = ref<HomeModuleKey[]>([...homeModuleOrder.value]);
const showLayoutOrderModal = ref(false);

function getModuleOrder(key: HomeModuleKey): number {
  const idx = homeModuleOrder.value.indexOf(key);
  return idx >= 0 ? idx + 1 : 10;
}

function getModuleMeta(key: HomeModuleKey) {
  return HOME_MODULE_META[key] || { icon: '📌', title: key, desc: '' };
}

function openLayoutOrderModal() {
  trackClick('home_open_layout_order', '首页点击「自定义首页板块顺序」');
  homeModuleOrderDraft.value = [...homeModuleOrder.value];
  showLayoutOrderModal.value = true;
}

function moveModuleOrder(idx: number, delta: number) {
  const targetIdx = idx + delta;
  if (targetIdx < 0 || targetIdx >= homeModuleOrderDraft.value.length) return;
  const list = [...homeModuleOrderDraft.value];
  const [moved] = list.splice(idx, 1);
  list.splice(targetIdx, 0, moved);
  homeModuleOrderDraft.value = list;
}

function pinModuleToTop(idx: number) {
  if (idx <= 0 || idx >= homeModuleOrderDraft.value.length) return;
  const list = [...homeModuleOrderDraft.value];
  const [moved] = list.splice(idx, 1);
  list.unshift(moved);
  homeModuleOrderDraft.value = list;
}

function resetHomeModuleOrder() {
  homeModuleOrderDraft.value = [...DEFAULT_HOME_MODULE_ORDER];
}

function saveHomeModuleOrder() {
  const clean = sanitizeModuleOrder(homeModuleOrderDraft.value);
  homeModuleOrder.value = clean;
  try {
    uni.setStorageSync(HOME_MODULE_STORAGE_KEY, JSON.stringify(clean));
  } catch (_) {}
  showLayoutOrderModal.value = false;
  trackClick('home_save_layout_order', '保存首页板块自定义顺序', { order: clean.join(',') });
  uni.showToast({ title: '首页顺序已保存', icon: 'success' });
}

const shortWeekTitle = computed(() => {
  const raw = String(dashboardData.value?.weekly_progress?.week_label || '本周').trim();
  return raw.split(/\s*\(/)[0] || '本周';
});

const weekPieStyle = computed(() => {
  const rawPct = Number(dashboardData.value?.weekly_progress?.progress_pct ?? 0);
  const clamped = Math.max(0, Math.min(100, isNaN(rawPct) ? 0 : rawPct));
  const deg = Math.round(clamped * 3.6 * 10) / 10;
  const remainColor = currentTheme.value === 'volt' ? '#E2E8F0' : 'rgba(255, 255, 255, 0.13)';
  return {
    background: `conic-gradient(#10b981 0deg ${deg}deg, ${remainColor} ${deg}deg 360deg)`,
  };
});

const monthPieStyle = computed(() => {
  const rawPct = Number(dashboardData.value?.progress?.progress_pct ?? 0);
  const clamped = Math.max(0, Math.min(100, isNaN(rawPct) ? 0 : rawPct));
  const deg = Math.round(clamped * 3.6 * 10) / 10;
  const remainColor = currentTheme.value === 'volt' ? '#E2E8F0' : 'rgba(255, 255, 255, 0.13)';
  return {
    background: `conic-gradient(#fc4c02 0deg ${deg}deg, ${remainColor} ${deg}deg 360deg)`,
  };
});
const isWeeklyReportWindow = computed(() => {
  const day = new Date().getDay();
  return day === 0 || day === 6;
});
const isMonthlyReportWindow = computed(() => {
  const left = Number(dashboardData.value?.progress?.days_left_in_month ?? 99);
  return left >= 0 && left <= 3;
});
const showPersonalReportModal = ref(false);
const personalReportDefaultPeriod = ref<'week' | 'month'>('week');
function openPersonalReportModal(period: 'week' | 'month' = 'week') {
  personalReportDefaultPeriod.value = period === 'month' ? 'month' : 'week';
  showPersonalReportModal.value = true;
}
const syncing = ref(false);
const currentMonth = ref(new Date().getMonth() + 1);
const activeTooltip = ref<any>(null);
const selectedYearMonth = ref<any>(null);
const showWeeklyGoalModal = ref(false);
const togglingWorkout = ref(false);

const hasTodayCheckinLog = computed(() => {
  const tw = dashboardData.value?.today_workout;
  if (!tw) return false;
  return !!(
    tw.feeling_tag ||
    tw.rpe ||
    tw.athlete_notes ||
    (Array.isArray(tw.workout_photos) && tw.workout_photos.length > 0)
  );
});

const isGoalReportHighlight = computed(() => {
  return isWeeklyReportWindow.value || isMonthlyReportWindow.value;
});

const goalPrimaryCtaLabel = computed(() => {
  if (isWeeklyReportWindow.value) {
    return "📅 报下周 ›";
  }
  if (isMonthlyReportWindow.value) {
    return "📅 报下月 ›";
  }
  return "🎯 定目标 ›";
});

const todayCheckinSummaryText = computed(() => {
  const tw = dashboardData.value?.today_workout;
  if (!tw) return "";
  const parts: string[] = [];
  if (tw.feeling_tag) parts.push(String(tw.feeling_tag));
  if (tw.rpe) parts.push(`RPE ${tw.rpe}/10`);
  if (Array.isArray(tw.workout_photos) && tw.workout_photos.length > 0) {
    parts.push(`📷 ${tw.workout_photos.length}张照片`);
  }
  if (tw.athlete_notes) parts.push(String(tw.athlete_notes));
  return parts.join(" · ");
});

const compactSyncLabel = computed(() => {
  if (!isDeviceConnected.value) return "绑定手表 ›";
  if (syncing.value) return "同步中...";
  const u = dashboardData.value?.user || user.value;
  const names: string[] = [];
  if (u?.garmin_connected) names.push("佳明");
  if (u?.coros_connected) names.push("高驰");
  if (u?.apple_watch_connected) names.push("苹果");
  if (u?.huawei_connected) names.push("华为");
  if (u?.suunto_connected) names.push("颂拓");
  if (names.length === 1) return `同步${names[0]}`;
  return "同步手表";
});

const isCorosOnly = computed(() => {
  const u = dashboardData.value?.user || user.value;
  return !!u?.coros_connected && !u?.garmin_connected;
});

const isDeviceConnected = computed(() => {
  const u = dashboardData.value?.user || user.value;
  return !!(u?.garmin_connected || u?.coros_connected || u?.apple_watch_connected || u?.huawei_connected || u?.suunto_connected);
});

const hasRunningData = computed(() => {
  return (
    isDeviceConnected.value ||
    monthActivitiesList.value.length > 0 ||
    Number(dashboardData.value?.yearly_stats?.total_runs || 0) > 0 ||
    Number(dashboardData.value?.progress?.current_month_km || 0) > 0
  );
});

const isDefaultNickname = computed(() => {
  const u = dashboardData.value?.user || user.value;
  if (!u?.id) return false;
  const name = String(u.display_name || "").trim();
  return (
    !name ||
    name === "微信跑者" ||
    name === "微信用户" ||
    name === "跑者" ||
    name.startsWith("跑者_") ||
    name.startsWith("新跑友") ||
    name.startsWith("Apple跑者_")
  );
});

function goToQuickEditProfile() {
  const uid = user.value?.id || dashboardData.value?.user?.id || getStoredUser()?.id;
  if (!uid) {
    openAuthModal();
    return;
  }
  trackClick("home.header.quick_edit_nickname", "首页点击快捷修改头像/昵称");
  try {
    uni.setStorageSync("auto_open_edit_profile", "1");
  } catch (_) {}
  uni.switchTab({ url: "/pages/profile/profile" });
}

const deviceConnectedText = computed(() => {
  const u = dashboardData.value?.user || user.value;
  if (u?.coros_connected && u?.coros_needs_reauth && !u?.garmin_connected) {
    return "高驰待短信验证";
  }
  const names: string[] = [];
  if (u?.garmin_connected) names.push("佳明");
  if (u?.coros_connected) names.push("高驰");
  if (u?.apple_watch_connected) names.push("苹果");
  if (u?.huawei_connected) names.push("华为");
  if (u?.suunto_connected) names.push("颂拓");
  return names.length ? `${names.join("/")}已连接` : "未绑定手表";
});

const syncDeviceName = computed(() => {
  const u = dashboardData.value?.user || user.value;
  const names: string[] = [];
  if (u?.garmin_connected) names.push("Garmin");
  if (u?.coros_connected) names.push("高驰 (COROS)");
  if (u?.apple_watch_connected) names.push("Apple Watch");
  if (u?.huawei_connected) names.push("华为手表");
  if (u?.suunto_connected) names.push("颂拓 Suunto");
  return names.length ? names.join(" & ") : "运动手表";
});

const healthCardTitle = computed(() => {
  const u = dashboardData.value?.user || user.value;
  if (u?.garmin_connected && u?.coros_connected) return "佳明 & 高驰 生理与状态指标";
  if (isCorosOnly.value) return "高驰 COROS 生理与状态指标";
  if (u?.apple_watch_connected && !u?.garmin_connected) return "Apple Watch 生理与恢复指标";
  if (u?.huawei_connected && !u?.garmin_connected) return "华为运动健康 生理与恢复指标";
  if (u?.suunto_connected && !u?.garmin_connected) return "颂拓 Suunto 生理与恢复指标";
  return "Garmin 生理与恢复指标";
});

const currentRestingHr = computed(() => {
  if (dashboardData.value?.today_health?.recovery_data_available === false) {
    return null;
  }
  return dashboardData.value?.today_health?.resting_heart_rate ?? null;
});

const currentVo2Max = computed(() => {
  return (
    dashboardData.value?.today_health?.vo2_max ??
    dashboardData.value?.user?.vo2max ??
    user.value?.vo2max ??
    null
  );
});

const currentVdot = computed(() => {
  const raw =
    dashboardData.value?.vdot ??
    dashboardData.value?.fitness_form?.vdot;
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? Number(n.toFixed(1)) : null;
});

const corosSleepScore = computed(() => {
  const hrv = Number(dashboardData.value?.today_health?.hrv_ms);
  const base = Number(dashboardData.value?.today_health?.hrv_weekly_avg || 66);
  if (!hrv || !base || base <= 0) return null;
  const ratio = hrv / base;
  let score = Math.round(85 * Math.pow(ratio, 0.7));
  return Math.max(45, Math.min(99, score));
});

const sleepOrBatteryVal = computed(() => {
  const th = dashboardData.value?.today_health;
  if (!th) return "—";
  if (!isCorosOnly.value && th.body_battery_max != null) {
    return `${th.body_battery_max}%`;
  }
  if (th.sleep_score != null) {
    return `${th.sleep_score}分`;
  }
  if (corosSleepScore.value != null) {
    return `${corosSleepScore.value}分`;
  }
  return "—";
});

const sleepOrBatterySub = computed(() => {
  const th = dashboardData.value?.today_health;
  if (th?.sleep_duration_text) return th.sleep_duration_text;
  return "30天趋势 ›";
});

function goToCoachPage() {
  uni.switchTab({
    url: "/pages/coach/coach",
    fail: () => {
      uni.navigateTo({ url: "/pages/coach/coach" });
    }
  });
}

function goToClubFeed() {
  uni.navigateTo({
    url: "/pages/rank/rank?section=feed",
    fail: () => {
      uni.switchTab({ url: "/pages/team/team" });
    }
  });
}

function getWorkoutTypeLabel(type: string): string {
  const map: Record<string, string> = {
    easy_run: "轻松跑",
    tempo: "门槛跑",
    interval: "间歇跑",
    long_run: "长距离",
    trail_climb: "越野爬坡",
    cross_training: "交叉力量",
    race: "🏁 比赛日",
    rest: "☕ 休息日"
  };
  return map[type] || "跑步";
}

function getWorkoutBadgeClass(type: string): string {
  const map: Record<string, string> = {
    easy_run: "tw-badge-easy",
    tempo: "tw-badge-tempo",
    interval: "tw-badge-interval",
    long_run: "tw-badge-long",
    trail_climb: "tw-badge-trail",
    cross_training: "tw-badge-cross",
    race: "tw-badge-race",
    rest: "tw-badge-rest"
  };
  return map[type] || "tw-badge-rest";
}

function getTodayWorkoutBorderClass(type: string): string {
  if (type === "race") return "tw-border-race";
  return "";
}

const FEELING_TAG_OPTIONS = [
  "🤩 状态极佳",
  "😊 轻松舒适",
  "💪 正常发挥",
  "😮‍💨 略感吃力",
  "🥵 疲惫掉速",
  "🦵 肌肉酸紧",
];

const showCheckinLogModal = ref(false);
const savingCheckinLog = ref(false);
const checkinForm = ref<{
  feeling_tag: string;
  rpe: number | null;
  athlete_notes: string;
  workout_photos: string[];
  new_photos_preview: string[];
  new_photos_base64: string[];
}>({
  feeling_tag: "",
  rpe: null,
  athlete_notes: "",
  workout_photos: [],
  new_photos_preview: [],
  new_photos_base64: [],
});

function openCheckinLogModal() {
  const tw = dashboardData.value?.today_workout;
  if (!tw) return;
  trackModal("checkin_log", "打开今日训练感受与照片打卡弹窗", "open");
  checkinForm.value = {
    feeling_tag: tw.feeling_tag || "",
    rpe: tw.rpe != null ? Number(tw.rpe) : null,
    athlete_notes: tw.athlete_notes || "",
    workout_photos: Array.isArray(tw.workout_photos) ? [...tw.workout_photos] : (tw.photo_url ? [tw.photo_url] : []),
    new_photos_preview: [],
    new_photos_base64: [],
  };
  showCheckinLogModal.value = true;
}

function previewWorkoutPhotos(urls: string[], currentIdx: number = 0) {
  if (!urls || !urls.length) return;
  uni.previewImage({
    urls,
    current: urls[currentIdx] || urls[0],
  });
}

function removeSavedWorkoutPhoto(idx: number) {
  checkinForm.value.workout_photos.splice(idx, 1);
}

function removeNewWorkoutPhoto(idx: number) {
  checkinForm.value.new_photos_preview.splice(idx, 1);
  checkinForm.value.new_photos_base64.splice(idx, 1);
}

function handleChooseWorkoutPhoto() {
  const currentTotal = checkinForm.value.workout_photos.length + checkinForm.value.new_photos_preview.length;
  const remain = Math.max(0, 3 - currentTotal);
  if (remain <= 0) {
    uni.showToast({ title: "最多上传 3 张照片", icon: "none" });
    return;
  }
  uni.chooseImage({
    count: remain,
    sizeType: ["compressed"],
    sourceType: ["album", "camera"],
    success: (res) => {
      const paths = res.tempFilePaths || [];
      const fs = uni.getFileSystemManager ? uni.getFileSystemManager() : null;
      paths.forEach((p: string) => {
        const readAsB64 = (filePath: string) => {
          if (!fs) return;
          fs.readFile({
            filePath,
            encoding: "base64",
            success: (fRes) => {
              const b64 = typeof fRes.data === "string" ? fRes.data : "";
              if (b64) {
                checkinForm.value.new_photos_preview.push(filePath);
                checkinForm.value.new_photos_base64.push(`data:image/jpeg;base64,${b64}`);
              }
            },
          });
        };
        if (uni.compressImage) {
          uni.compressImage({
            src: p,
            quality: 78,
            success: (cRes) => readAsB64(cRes.tempFilePath || p),
            fail: () => readAsB64(p),
          });
        } else {
          readAsB64(p);
        }
      });
    },
  });
}

async function saveCheckinLog() {
  const tw = dashboardData.value?.today_workout;
  if (!tw || !tw.plan_id) return;
  savingCheckinLog.value = true;
  try {
    const res: any = await request(`/api/coach/plan/${tw.plan_id}/workout`, "PATCH", {
      week_index: tw.week_index,
      day_index: tw.day_index,
      completed: true,
      feeling_tag: checkinForm.value.feeling_tag,
      rpe: checkinForm.value.rpe,
      athlete_notes: checkinForm.value.athlete_notes,
      workout_photos: checkinForm.value.workout_photos,
      new_photos_base64: checkinForm.value.new_photos_base64,
      operator_uid: user.value?.id || getStoredUser()?.id || "athlete",
    });
    if (res?.success) {
      trackModal("checkin_log", "提交保存训练打卡感受与照片", "submit", {
        rpe: checkinForm.value.rpe,
        photos_count: checkinForm.value.workout_photos.length + checkinForm.value.new_photos_base64.length,
      });
      showCheckinLogModal.value = false;
      uni.showToast({ title: "打卡感受与照片已同步！", icon: "success" });
      await loadDashboard();
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || "保存失败，请重试", icon: "none" });
  } finally {
    savingCheckinLog.value = false;
  }
}

async function handleTodayWorkoutToggle() {
  const tw = dashboardData.value?.today_workout;
  if (!tw || !tw.plan_id) return;
  togglingWorkout.value = true;
  try {
    const newCompleted = !tw.completed;
    const res = await request(`/api/coach/plan/${tw.plan_id}/workout`, "PATCH", {
      week_index: tw.week_index,
      day_index: tw.day_index,
      completed: newCompleted,
      operator_uid: user.value?.id || getStoredUser()?.id || "athlete"
    });
    if (res?.success) {
      tw.completed = newCompleted;
      if (newCompleted) {
        uni.showToast({ title: "今日已打卡！可补充感受与照片", icon: "success" });
        openCheckinLogModal();
      } else {
        uni.showToast({ title: "已取消打卡", icon: "none" });
      }
      // Refresh dashboard to sync weekly mileage progress
      await loadDashboard();
    }
  } catch (e: any) {
    console.error("Toggle workout error:", e);
    uni.showToast({ title: e?.message || "打卡失败，请重试", icon: "none" });
  } finally {
    togglingWorkout.value = false;
  }
}

function openGoalSheet(tab: 'week' | 'month' = 'week') {
  const uid = user.value?.id || dashboardData.value?.user?.id || getStoredUser()?.id;
  if (!uid) {
    openAuthModal();
    return;
  }
  goalSheetDefaultTab.value = tab === 'month' ? 'month' : 'week';
  showWeeklyGoalModal.value = true;
}

function openWeeklyGoalModal() {
  openGoalSheet('week');
}

function closeWeeklyGoalModal() {
  showWeeklyGoalModal.value = false;
}

async function handleHomeGoalSaved(savedGoal: any) {
  if (dashboardData.value) {
    dashboardData.value.goal = {
      ...(dashboardData.value.goal || {}),
      ...(savedGoal || {}),
    };
    if (dashboardData.value.weekly_progress) {
      const nextWk = Number(savedGoal?.next_weekly_target ?? savedGoal?.weekly_target);
      if (Number.isFinite(nextWk) && nextWk > 0) {
        dashboardData.value.weekly_progress.next_week_target_km = nextWk;
      }
      if (savedGoal?.current_week_target) {
        dashboardData.value.weekly_progress.target_week_km = Number(savedGoal.current_week_target);
      }
    }
  }
  if (onboardStatus.value?.steps) {
    onboardStatus.value.steps.goals = true;
  }
  showWeeklyGoalModal.value = false;
  await loadDashboard();
}

function formatShortDayDate(dateStr?: string) {
  if (!dateStr || dateStr === "--/--") return "--";
  const parts = dateStr.split("/");
  if (parts.length === 2) {
    const m = parseInt(parts[0], 10);
    const d = parseInt(parts[1], 10);
    return `${m}/${d}`;
  }
  return dateStr;
}

function selectYearMonth(m: any) {
  if (selectedYearMonth.value?.month === m.month) {
    selectedYearMonth.value = null;
  } else {
    selectedYearMonth.value = m;
  }
}

function getBarHeight(km: number) {
  if (!km || km <= 0) return "6rpx";
  const breakdown = dashboardData.value?.yearly_stats?.monthly_breakdown || defaultMonthlyBreakdown;
  const maxVal = Math.max(...breakdown.map((b: any) => b.distance_km || 0), 100);
  const pct = Math.max(12, Math.min(100, Math.round((km / maxVal) * 100)));
  return `${pct}%`;
}

const fitnessStatusColor = computed(() => {
  const tsb = Number(dashboardData.value?.fitness_form?.tsb ?? 0);
  if (tsb >= 5) return "#10b981";
  if (tsb >= -30) return "#3b82f6";
  if (tsb >= -50) return "#f59e0b";
  return "#ef4444";
});

const fitnessStatusLabel = computed(() => {
  const raw = dashboardData.value?.fitness_form?.status_label;
  if (raw && raw !== "未连接") return raw;
  const tsb = Number(dashboardData.value?.fitness_form?.tsb ?? 0);
  if (tsb >= 5) return "状态巅峰";
  if (tsb >= -30) return "训练中";
  if (tsb >= -50) return "注意疲劳";
  return "严重疲劳";
});

const fitnessMiniBars = computed(() => {
  const fullHistory = dashboardData.value?.fitness_form?.history || [];
  const slice = fullHistory.slice(-28);
  if (!slice.length) return [];
  const maxVal = Math.max(
    ...slice.map((pt: any) => Math.max(Number(pt.ctl) || 0, Number(pt.atl) || 0)),
    100
  );
  return slice.map((pt: any) => {
    const ctl = Number(pt.ctl) || 0;
    const atl = Number(pt.atl) || 0;
    return {
      ...pt,
      ctlPct: Math.max(5, Math.min(100, Math.round((ctl / maxVal) * 100))),
      atlPct: Math.max(5, Math.min(100, Math.round((atl / maxVal) * 100))),
    };
  });
});

function formatMetricOneDec(v: any): string {
  const num = Number(v);
  if (isNaN(num)) return "0.0";
  return num.toFixed(1);
}

function formatTsbVal(v: any): string {
  const num = Number(v);
  if (isNaN(num)) return "0.0";
  return (num > 0 ? "+" : "") + num.toFixed(1);
}

function selectFitnessBar(pt: any) {
  if (activeTooltip.value?.date === pt.date) {
    activeTooltip.value = null;
  } else {
    activeTooltip.value = pt;
  }
}

function drawFitnessChart() {
  // Using iOS-style pure DOM stacked bar chart; canvas drawing no longer needed.
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
    content:
      "万跑跑团助手严格遵循法律法规保护用户隐私：(1) 您的运动手表账号、跑步轨迹、心率等生理指标仅在您主动授权绑定或导入后同步；(2) 为排查报错并优化界面体验，小程序仅在第一方服务器记录页面访问、功能点击与接口耗时，已关闭第三方统计插件且绝不对外共享个人数据。",
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

    await loadDashboard();
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
    await loadDashboard();
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

async function loadDashboard() {
  user.value = getStoredUser();
  if (!user.value || !user.value.id) {
    try {
      const logged = await authenticateWechatUser();
      if (logged && logged.id) {
        user.value = logged;
      }
    } catch (e) {
      console.warn("Silent login fallback:", e);
    }
  }
  if (!user.value || !user.value.id) {
    openAuthModal();
    return;
  }
  const uid = user.value.id;
  loadMyNextRun(uid);

  try {
    const data = await request(`/api/miniapp/dashboard/${uid}`);
    if (data && data.progress) {
      dashboardData.value = data;
      lastDashboardFetchAt = Date.now();
      writeCachedDashboardSnapshot(uid, data);
      try {
        uni.removeStorageSync("rgm_dashboard_dirty");
      } catch (_) {}
      if (data.user) {
        if (!user.value) user.value = {} as any;
        if (data.user.id) user.value.id = data.user.id;
        if (data.user.avatar_url) user.value.avatar_url = data.user.avatar_url;
        if (data.user.display_name) user.value.display_name = data.user.display_name;
        if (data.user.coros_connected !== undefined) user.value.coros_connected = data.user.coros_connected;
        if (data.user.garmin_connected !== undefined) user.value.garmin_connected = data.user.garmin_connected;
        if (data.user.apple_watch_connected !== undefined) user.value.apple_watch_connected = data.user.apple_watch_connected;
        if (data.user.huawei_connected !== undefined) user.value.huawei_connected = data.user.huawei_connected;
        if (data.user.huawei_account !== undefined) user.value.huawei_account = data.user.huawei_account;
        if (data.user.suunto_connected !== undefined) user.value.suunto_connected = data.user.suunto_connected;
        if (data.user.suunto_account !== undefined) user.value.suunto_account = data.user.suunto_account;
        if (data.user.resting_heart_rate !== undefined) user.value.resting_heart_rate = data.user.resting_heart_rate;
        if (data.user.vo2max !== undefined) user.value.vo2max = data.user.vo2max;
        uni.setStorageSync("rgm_user", user.value);
      }
      nextTick(() => {
        scheduleFitnessChart(120);
      });
      loadNotifications();
      request(`/api/profile/${uid}/onboarding-status`).then((st: any) => {
        if (st) {
          onboardStatus.value = st;
          // 后端字段为 is_completed（旧代码读 is_fully_completed 恒为 undefined，导致横幅对所有人常驻）
          showOnboardReminder.value = !(st.is_completed ?? st.is_fully_completed);
          try {
            uni.setStorageSync(`rgm_onboard_status_${uid}`, st);
          } catch (_) {}
        }
      }).catch((e: any) => {
        console.warn("Onboarding status check:", e);
      });
      checkAndPromptOrgReminder(uid).then((rem) => {
        if (rem && rem.hasReminder) {
          pendingOrgReminder.value = rem;
        } else {
          pendingOrgReminder.value = null;
        }
      });
    }
  } catch (e) {
    console.warn("Dashboard fetch fallback:", e);
    dashboardLoadError.value = true;
    return false;
  }
  dashboardLoadError.value = false;
  return true;
}

async function handleInstantSync() {
  trackClick("home_instant_sync", "首页点击「立即同步手表」");
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  // 未绑定手表时，同步没有意义，直接引导去绑定
  if (!isDeviceConnected.value) {
    goToDeviceBinding();
    return;
  }
  const u = dashboardData.value?.user || user.value;
  const hasCloudWatch = !!(u?.garmin_connected || u?.coros_connected);
  const hasHealthWatch = !!(u?.apple_watch_connected || u?.huawei_connected || u?.suunto_connected);
  if (!hasCloudWatch && hasHealthWatch) {
    const brand: "apple_watch" | "huawei" | "suunto" = u?.suunto_connected
      ? "suunto"
      : u?.huawei_connected
      ? "huawei"
      : "apple_watch";
    const brandLabel =
      brand === "suunto"
        ? "颂拓 Suunto"
        : brand === "huawei"
        ? "华为手表"
        : "Apple Watch";
    uni.showActionSheet({
      itemList: [
        "📸 选运动截图一键导入（支持苹果健康多日列表）",
        `📂 从微信导入 ${brandLabel} FIT/GPX/TCX 轨迹`,
        "🔄 刷新云端已同步数据",
        "⏭️ 稍后导入（完成此步）",
      ],
      success: async (sheetRes) => {
        if (sheetRes.tapIndex === 0) {
          await triggerWechatScreenshotImport(uid, brand, brandLabel);
        } else if (sheetRes.tapIndex === 1) {
          await triggerWechatTrackImport(uid, brand, brandLabel);
        } else if (sheetRes.tapIndex === 2) {
          await executeCloudSync(uid, brand, brandLabel);
        } else if (sheetRes.tapIndex === 3) {
          await markSkipHistoryStep(uid);
        }
      },
    });
    return;
  }
  await executeCloudSync(uid);
}

async function triggerWechatScreenshotImport(
  uid: string,
  brand: "apple_watch" | "huawei" | "suunto",
  brandLabel: string
) {
  try {
    const importRes = await chooseAndImportScreenshot(uid, brand);
    if (importRes?.success) {
      if (onboardStatus.value?.steps) onboardStatus.value.steps.history = true;
      await loadDashboard();
      const recs: any[] = importRes.records || [];
      const previewLines = recs
        .slice(0, 6)
        .map((r: any) => `• ${r.date}：${r.distance_km} km`)
        .join("\n");
      const moreLine = recs.length > 6 ? `\n…等共 ${recs.length} 条记录` : "";
      uni.showModal({
        title: "🎉 运动截图导入成功",
        content: previewLines ? `${importRes.message}\n\n${previewLines}${moreLine}` : (importRes.message || "截图识别导入成功！"),
        showCancel: false,
        confirmText: "太棒了",
      });
    }
  } catch (err: any) {
    if (err?.message === "CANCEL" || err?.message === "__CANCEL__") return;
    const guideText = "支持截取「iPhone 苹果健康 → 步行+跑步距离 → 所有已记录的数据」列表图（一次可识别十余天记录），或「Suunto / 华为运动健康」单次跑步详情截图。";
    uni.showModal({
      title: `${brandLabel} 截图导入说明`,
      content: err?.message ? `${err.message}\n\n${guideText}` : guideText,
      showCancel: true,
      cancelText: "稍后导入",
      confirmText: "重新选图",
      success: async (mRes) => {
        if (mRes.confirm) {
          await triggerWechatScreenshotImport(uid, brand, brandLabel);
        } else if (mRes.cancel) {
          await markSkipHistoryStep(uid);
        }
      },
    });
  }
}

async function triggerWechatTrackImport(
  uid: string,
  brand: "apple_watch" | "huawei" | "suunto",
  brandLabel: string
) {
  try {
    const importRes = await chooseAndImportTrackFile(uid, brand);
    if (importRes?.success) {
      if (onboardStatus.value?.steps) onboardStatus.value.steps.history = true;
      uni.showToast({ title: importRes.message || "轨迹导入成功！", icon: "success" });
      await loadDashboard();
    }
  } catch (err: any) {
    if (err?.message === "CANCEL" || err?.message === "__CANCEL__") return;
    const guideText = "请先将运动 App 导出的 FIT、GPX 或 TCX 轨迹文件发送到微信聊天（如「文件传输助手」），再点击导入。";
    uni.showModal({
      title: `${brandLabel} 轨迹导入说明`,
      content: err?.message && !err.message.includes("未能打开") ? `${err.message}\n\n${guideText}` : guideText,
      showCancel: true,
      cancelText: "稍后导入",
      confirmText: "我知道了",
      success: async (mRes) => {
        if (mRes.cancel) {
          await markSkipHistoryStep(uid);
        }
      },
    });
  }
}

async function markSkipHistoryStep(uid: string) {
  try {
    await request(`/api/profile/${uid}/onboarding-action`, "POST", { action: "skip_history" });
    if (onboardStatus.value?.steps) onboardStatus.value.steps.history = true;
    if (onboardStatus.value?.details) onboardStatus.value.details.history_skipped = true;
    uni.showToast({ title: "已标记稍后导入", icon: "none" });
  } catch (e) {}
}

async function executeCloudSync(
  uid: string,
  healthBrand?: "apple_watch" | "huawei" | "suunto",
  healthBrandLabel?: string
) {
  syncing.value = true;
  uni.showLoading({ title: `同步 ${syncDeviceName.value} 中...` });
  try {
    const res = await request("/api/sync/trigger", "POST", { uid });
    uni.hideLoading();
    if (
      (res?.watch_mode === "huawei" || res?.watch_mode === "apple_watch" || res?.watch_mode === "suunto") &&
      Number(res?.synced_activities || 0) === 0
    ) {
      const bMode: "apple_watch" | "huawei" | "suunto" = healthBrand || res.watch_mode;
      const bLabel =
        healthBrandLabel ||
        (bMode === "suunto"
          ? "颂拓 Suunto"
          : bMode === "huawei"
          ? "华为手表"
          : "Apple Watch");
      const howTo = `因微信小程序无法直接读取手机本地「苹果健康 / 华为运动健康 / Suunto App」数据库，推荐直接截取「苹果健康 → 所有已记录的数据」列表图或单次跑步截图，点击【📸 选截图导入】一键批量识别入库！`;
      uni.showModal({
        title: `如何导入 ${bLabel} 跑步数据`,
        content: howTo,
        cancelText: "稍后(跳过)",
        confirmText: "📸 选截图导入",
        success: async (mRes) => {
          if (mRes.confirm) {
            await triggerWechatScreenshotImport(uid, bMode, bLabel);
          } else if (mRes.cancel) {
            await markSkipHistoryStep(uid);
          }
        },
      });
    } else if (res?.success === false) {
      const errMsg = res?.error || `${syncDeviceName.value}连接中，请稍后刷新重试`;
      const shouldRebind = !!(res?.needs_rebind || errMsg.includes("重新授权") || errMsg.includes("重新绑定") || errMsg.includes("验证码"));
      uni.showModal({
        title: "同步提示",
        content: errMsg,
        showCancel: shouldRebind,
        cancelText: "稍后",
        confirmText: shouldRebind ? "去验证" : "确定",
        success: (mRes) => {
          if (shouldRebind && mRes.confirm) {
            const isCorosErr = errMsg.includes("高驰") || errMsg.toLowerCase().includes("coros");
            const isGarminErr = errMsg.includes("佳明") || errMsg.toLowerCase().includes("garmin");
            goToDeviceBinding(isCorosErr ? "coros" : isGarminErr ? "garmin" : undefined, true);
          }
        },
      });
    } else {
      if (onboardStatus.value?.steps && Number(res?.synced_activities || 0) > 0) {
        onboardStatus.value.steps.history = true;
      }
      uni.showToast({ title: "同步成功", icon: "success" });
    }
    await loadDashboard();
  } catch (e: any) {
    uni.hideLoading();
    uni.showModal({
      title: "同步失败",
      content: e?.message || e?.data?.detail || "网络请求失败，请稍后重试",
      showCancel: false,
    });
  } finally {
    syncing.value = false;
  }
}

function formatTime(isoStr?: string): string {
  if (!isoStr) return "";
  try {
    const s = isoStr.replace("T", " ");
    if (s.length >= 16) {
      return s.slice(5, 16);
    }
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return s;
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    const h = String(d.getHours()).padStart(2, "0");
    const min = String(d.getMinutes()).padStart(2, "0");
    return `${m}-${day} ${h}:${min}`;
  } catch {
    return isoStr || "";
  }
}


const pageVmProxy = getCurrentInstance()?.proxy;
let cleanupModuleObservers: (() => void) | null = null;
let lastObserverSig = "";
let observerTimer: ReturnType<typeof setTimeout> | null = null;
const HOME_EXPOSURE_TARGETS = [
  { selector: "#rgm-mod-starter", key: "home.starter_tasks", label: "首页-新手任务卡片" },
  { selector: "#rgm-mod-nextrun", key: "home.next_group_run", label: "首页-下一场约跑卡片" },
  { selector: "#rgm-mod-feed", key: "home.club_feed_bar", label: "首页-跑友动态入口条" },
  { selector: "#rgm-mod-today", key: "home.today_workout", label: "首页-今日课表卡片" },
  { selector: "#rgm-mod-goal", key: "home.goal_progress", label: "首页-周/月目标进度卡" },
  { selector: "#rgm-mod-status", key: "home.fitness_health", label: "首页-生理与体能状态卡" },
  { selector: "#rgm-mod-recent", key: "home.recent_runs", label: "首页-近期跑步记录卡" },
  { selector: "#rgm-mod-yearly", key: "home.yearly_stats", label: "首页-年度跑量统计卡" },
];

function ensureHomeModuleObservers() {
  if (!pageVmProxy || firstLoadPending.value) return;
  const sid = getCurrentSessionId();
  if (!sid) return;
  const sig = `${sid}|${Boolean(myNextRun.value)}|${Boolean(showStarterTasks.value)}`;
  if (cleanupModuleObservers && sig === lastObserverSig) return;
  if (cleanupModuleObservers) {
    cleanupModuleObservers();
    cleanupModuleObservers = null;
  }
  lastObserverSig = sig;
  cleanupModuleObservers = observeModuleExposures(pageVmProxy, HOME_EXPOSURE_TARGETS);
}

function scheduleHomeModuleObservers(delayMs = 260) {
  if (observerTimer) clearTimeout(observerTimer);
  observerTimer = setTimeout(() => {
    observerTimer = null;
    ensureHomeModuleObservers();
  }, delayMs);
}

watch(
  [() => firstLoadPending.value, () => Boolean(myNextRun.value), () => Boolean(showStarterTasks.value)],
  ([pending]) => {
    if (!pending) {
      nextTick(() => scheduleHomeModuleObservers(260));
    }
  }
);

onMounted(() => {
  if (initialCachedDashboard) {
    nextTick(() => {
      scheduleFitnessChart(120);
    });
  }
  if (!firstLoadPending.value) {
    scheduleHomeModuleObservers(350);
  }
});

onUnmounted(() => {
  if (observerTimer) {
    clearTimeout(observerTimer);
    observerTimer = null;
  }
  if (cleanupModuleObservers) {
    cleanupModuleObservers();
    cleanupModuleObservers = null;
  }
  lastObserverSig = "";
});

onShow(() => {
  applySystemTheme(currentTheme.value);
  syncTabBarIndex(0);
  if (!firstLoadPending.value) {
    scheduleHomeModuleObservers(280);
  }
  const storedNow = getStoredUser();
  const uidChanged = Boolean(storedNow?.id && storedNow.id !== user.value?.id);
  let isDirty = false;
  try {
    isDirty = Boolean(uni.getStorageSync("rgm_dashboard_dirty"));
  } catch (_) {}

  const shouldRefresh =
    firstLoadPending.value ||
    uidChanged ||
    isDirty ||
    lastDashboardFetchAt === 0 ||
    Date.now() - lastDashboardFetchAt >= 45000;

  if (!shouldRefresh) {
    nextTick(() => {
      scheduleFitnessChart(120);
    });
    return;
  }

  const first = firstLoadPending.value;
  const p = loadDashboard();
  if (first) {
    const timer = setTimeout(() => (firstLoadPending.value = false), 8000);
    Promise.resolve(p)
      .catch(() => {})
      .finally(() => {
        clearTimeout(timer);
        firstLoadPending.value = false;
      });
  }
});

onPullDownRefresh(async () => {
  try {
    loadMyNextRun();
    const ok = await loadDashboard();
    if (ok === false) {
      uni.showToast({ title: "刷新失败，请检查网络后重试", icon: "none" });
    } else if (ok === true) {
      uni.showToast({ title: "数据已更新", icon: "success" });
    }
  } catch (e) {
    uni.showToast({ title: "刷新失败，请稍后重试", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});
</script>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  padding: 24rpx 28rpx calc(130rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(130rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── ✅ 新手任务清单 ── */
.starter-card {
  padding: 24rpx 26rpx;
  border-radius: 24rpx;
  margin-bottom: 20rpx;
  background: var(--rgm-card, linear-gradient(135deg, rgba(255, 107, 0, 0.14) 0%, rgba(20, 20, 24, 0.96) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(255, 107, 0, 0.4));
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.25));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.sc-head {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}
.sc-head-left,
.sc-head-right {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 14rpx;
}
.sc-title {
  font-size: 28rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #ff8533);
}
.sc-count {
  font-size: 20rpx;
  color: var(--rgm-text, #ffffff);
  background: var(--rgm-brand-tint, rgba(255, 107, 0, 0.35));
  padding: 2rpx 12rpx;
  border-radius: 12rpx;
  font-weight: 600;
}
.sc-toggle {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}
.sc-close {
  font-size: 26rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 4rpx 8rpx;
}
.sc-progress {
  height: 8rpx;
  margin-top: 18rpx;
  border-radius: 8rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  overflow: hidden;
}
.sc-progress-fill {
  height: 100%;
  border-radius: 8rpx;
  background: var(--rgm-brand, #ff6b00);
  transition: width 0.3s ease;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}
.sc-list {
  margin-top: 12rpx;
}
.sc-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 18rpx;
  padding: 18rpx 0;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
}
.sc-item:active {
  opacity: 0.75;
}
.sc-check {
  width: 36rpx;
  height: 36rpx;
  line-height: 36rpx;
  text-align: center;
  border-radius: 50%;
  border: 2rpx solid #52525b;
  font-size: 22rpx;
  color: #0b0b0d;
  flex-shrink: 0;
}
.sc-item.done .sc-check {
  background: #22c55e;
  border-color: #22c55e;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}
.sc-item-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.sc-item-title {
  font-size: 26rpx;
  color: var(--rgm-text, #f4f4f5);
  font-weight: 600;
}
.sc-item.done .sc-item-title {
  color: var(--rgm-text-3, #71717a);
  text-decoration: line-through;
  font-weight: 400;
}
.sc-item-go {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #ff8533);
  font-weight: 600;
  flex-shrink: 0;
}
.sc-footer-link {
  display: block;
  margin-top: 16rpx;
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  text-align: center;
}

/* ── Onboarding Banner ── */
.onboard-index-banner {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding: 22rpx 26rpx;
  border-radius: 24rpx;
  margin-bottom: 28rpx;
  cursor: pointer;
  background: var(--rgm-card, linear-gradient(135deg, rgba(255, 107, 0, 0.16) 0%, rgba(20, 20, 24, 0.96) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(255, 107, 0, 0.4));
  box-shadow: 0 8rpx 24rpx var(--rgm-shadow, rgba(0, 0, 0, 0.25));
  transition: opacity 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.onboard-index-banner:active {
  opacity: 0.85;
}

.oib-left {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16rpx;
  flex: 1;
  min-width: 0;
}

.oib-icon {
  font-size: 38rpx;
  flex-shrink: 0;
}

.oib-meta {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  min-width: 0;
  flex: 1;
}

.oib-title-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12rpx;
}

.oib-title {
  font-size: 27rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #ff8533);
}

.oib-tag {
  font-size: 20rpx;
  color: var(--rgm-text, #ffffff);
  background: var(--rgm-brand-tint, rgba(255, 107, 0, 0.35));
  padding: 2rpx 12rpx;
  border-radius: 12rpx;
  font-weight: 600;
}

.oib-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.oib-actions {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 14rpx;
  flex-shrink: 0;
}

.oib-btn {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #ff8533);
  background: var(--rgm-brand-tint, rgba(255, 107, 0, 0.18));
  border: 1rpx solid var(--rgm-brand-line, rgba(255, 107, 0, 0.4));
  padding: 8rpx 18rpx;
  border-radius: 20rpx;
}

.oib-close {
  font-size: 24rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 8rpx;
  line-height: 1;
}

/* ── Org Reminder Banner ── */
.org-reminder-banner {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16rpx;
  padding: 22rpx 26rpx;
  border-radius: 24rpx;
  margin-bottom: 28rpx;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.org-reminder-banner:active {
  opacity: 0.85;
}

.banner-temporary {
  background: var(--rgm-card, linear-gradient(135deg, rgba(245, 158, 11, 0.16) 0%, rgba(20, 20, 24, 0.95) 100%));
  border: 1rpx solid rgba(245, 158, 11, 0.45);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.banner-suspended {
  background: var(--rgm-card, linear-gradient(135deg, rgba(239, 68, 68, 0.18) 0%, rgba(20, 20, 24, 0.95) 100%));
  border: 1rpx solid rgba(239, 68, 68, 0.5);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.orb-icon {
  font-size: 38rpx;
  flex-shrink: 0;
}

.orb-text-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  min-width: 0;
}

.orb-title-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12rpx;
}

.orb-title {
  font-size: 27rpx;
  font-weight: 700;
  color: var(--rgm-amber, #f59e0b);
}

.banner-suspended .orb-title {
  color: var(--rgm-red, #ef4444);
}

.orb-badge {
  font-size: 20rpx;
  color: var(--rgm-text, #ffffff);
  background: rgba(245, 158, 11, 0.35);
  padding: 2rpx 12rpx;
  border-radius: 12rpx;
  font-weight: 600;
}

.banner-suspended .orb-badge {
  background: rgba(239, 68, 68, 0.35);
}

.orb-desc {
  font-size: 23rpx;
  color: var(--rgm-text-2, #d4d4d8);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.orb-action-btn {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4rpx;
  flex-shrink: 0;
  background: rgba(245, 158, 11, 0.2);
  padding: 10rpx 18rpx;
  border-radius: 20rpx;
  border: 1rpx solid rgba(245, 158, 11, 0.4);
}

.banner-suspended .orb-action-btn {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.4);
}

.orb-btn-label {
  font-size: 22rpx;
  font-weight: 600;
  color: var(--rgm-amber, #f59e0b);
}

.banner-suspended .orb-btn-label {
  color: var(--rgm-red, #ef4444);
}

.orb-arrow {
  font-size: 24rpx;
  color: var(--rgm-amber, #f59e0b);
}

.banner-suspended .orb-arrow {
  color: var(--rgm-red, #ef4444);
}

.header-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 16rpx;
  min-width: 0;
  flex: 1;
}

.avatar {
  width: 88rpx;
  height: 88rpx;
  border-radius: 44rpx;
  flex-shrink: 0;
  border: 2rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
}

.text-group {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  flex: 1;
}

.greeting {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  white-space: nowrap;
}

.user-name {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260rpx;
}

.user-fitness-sub {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8rpx;
  margin-top: 6rpx;
}

.uf-tag {
  font-size: 20rpx;
  font-weight: 600;
  padding: 2rpx 12rpx;
  border-radius: 12rpx;
  border: 1rpx solid;
  line-height: 1.35;
  white-space: nowrap;
  flex-shrink: 0;
}

.uf-metric {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-blue, #38bdf8);
  background: rgba(56, 189, 248, 0.12);
  border: 1rpx solid rgba(56, 189, 248, 0.3);
  padding: 2rpx 10rpx;
  border-radius: 12rpx;
  line-height: 1.35;
  white-space: nowrap;
}

.fitness-section-top {
  margin-bottom: 36rpx;
}

.header-right-actions {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-shrink: 0;
}

.theme-toggle-pill {
  display: flex;
  align-items: center;
  gap: 6rpx;
  padding: 8rpx 14rpx;
  border-radius: 30rpx;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.theme-toggle-pill:active {
  opacity: 0.75;
}

.ttp-icon {
  font-size: 20rpx;
  line-height: 1;
}

.ttp-text {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
}

.notif-bell-btn {
  position: relative;
  width: 56rpx;
  height: 56rpx;
  border-radius: 28rpx;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.bell-icon {
  font-size: 26rpx;
}

.notif-badge {
  position: absolute;
  top: -6rpx;
  right: -6rpx;
  background-color: #ff3b30;
  border-radius: 16rpx;
  min-width: 30rpx;
  height: 30rpx;
  padding: 0 6rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2rpx solid var(--rgm-line-solid, #0b0b0d);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.notif-badge-text {
  font-size: 18rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  line-height: 1;
}

.garmin-badge {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 8rpx 14rpx;
  border-radius: 30rpx;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.pulse-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 5rpx;
  background-color: #636366;
  flex-shrink: 0;
}

.garmin-badge.active .pulse-dot {
  background-color: #34c759;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.badge-text {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  white-space: nowrap;
}

.garmin-badge.active .badge-text {
  color: var(--rgm-green, #34c759);
}

.hero-progress-card {
  background: var(--rgm-card, linear-gradient(135deg, #1c1c1e 0%, #141416 100%));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.35));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.goal-top-bar {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 24rpx;
}

.goal-tab-header {
  flex: 1;
  min-width: 0;
  display: flex;
  background-color: var(--rgm-card, #121214);
  border-radius: 20rpx;
  padding: 6rpx;
  gap: 8rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.goal-set-primary-btn {
  flex-shrink: 0;
  height: 72rpx;
  padding: 0 24rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(252, 76, 2, 0.22) 0%, rgba(252, 76, 2, 0.12) 100%);
  border: 1.5rpx solid rgba(252, 76, 2, 0.62);
  box-shadow: 0 4rpx 14rpx rgba(252, 76, 2, 0.16);
}

.goal-set-primary-btn.is-volt {
  background: #FFF3EC;
  border-color: rgba(252, 76, 2, 0.45);
}

.goal-set-primary-btn.is-report-window {
  background: linear-gradient(135deg, #fc4c02 0%, #e04100 100%);
  border-color: #fc4c02;
  box-shadow: 0 6rpx 18rpx rgba(252, 76, 2, 0.35);
}

.goal-set-primary-txt {
  font-size: 25rpx;
  font-weight: 800;
  color: #ff6a2b;
  white-space: nowrap;
}

.goal-set-primary-btn.is-volt .goal-set-primary-txt {
  color: #c23800;
}

.goal-set-primary-btn.is-report-window .goal-set-primary-txt {
  color: #ffffff;
}

.goal-tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  padding: 16rpx 0;
  border-radius: 16rpx;
  transition: all 0.2s ease;
}

.goal-tab-btn.active {
  background-color: var(--rgm-card-3, #2c2c2e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  box-shadow: 0 4rpx 12rpx var(--rgm-shadow, rgba(0, 0, 0, 0.35));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tab-icon {
  font-size: 24rpx;
}

.tab-text {
  font-size: 24rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
}

.goal-tab-btn.active .tab-text {
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

.tab-achieved-dot {
  width: 10rpx;
  height: 10rpx;
  background-color: #34d399;
  border-radius: 50%;
  margin-left: 4rpx;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.goal-header-block {
  margin-bottom: 22rpx;
}

.goal-header-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12rpx;
}

.goal-main-title {
  font-size: 32rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  letter-spacing: 0.5rpx;
}

.goal-top-pct {
  font-size: 42rpx;
  font-weight: 900;
  line-height: 1;
}

.goal-header-sub {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 44rpx;
}

.cycle-summary-chip {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  font-weight: 500;
}

.quick-set-trigger {
  background-color: rgba(16, 185, 129, 0.12);
  border: 1rpx solid rgba(16, 185, 129, 0.4);
  border-radius: 14rpx;
  padding: 6rpx 18rpx;
  display: flex;
  align-items: center;
  transition: all 0.2s ease;
}

.quick-set-icon {
  font-size: 20rpx;
  color: var(--rgm-green, #34d399);
  font-weight: bold;
}

.clickable-stat {
  cursor: pointer;
}

.stat-val-with-edit {
  display: flex;
  align-items: center;
  gap: 4rpx;
}

.edit-badge {
  font-size: 18rpx;
  opacity: 0.8;
}

/* Quick Weekly Goal Modal */
.weekly-goal-modal {
  width: 680rpx;
}

.w-modal-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.45;
  margin-bottom: 24rpx;
}

.w-target-display-card {
  background: rgba(16, 185, 129, 0.1);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
  border-radius: 20rpx;
  padding: 24rpx 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 24rpx;
}

.w-target-num-row {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
}

.w-target-big-num {
  font-size: 56rpx;
  font-weight: 900;
  color: var(--rgm-green, #34d399);
  line-height: 1;
}

.w-target-big-unit {
  font-size: 24rpx;
  color: var(--rgm-green, #34d399);
  font-weight: bold;
}

.w-target-equiv-label {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  margin-top: 8rpx;
}

.w-pills-label {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  display: block;
  margin-bottom: 12rpx;
  font-weight: 600;
}

.w-modal-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 24rpx;
}

.w-modal-pill {
  padding: 10rpx 22rpx;
  background-color: var(--rgm-card-3, #242429);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 14rpx;
  font-size: 22rpx;
  color: var(--rgm-text-2, #d4d4d8);
  font-weight: 600;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.w-modal-pill.active {
  background-color: var(--rgm-brand, #10b981);
  border-color: var(--rgm-brand, #10b981);
  color: var(--rgm-text, #ffffff);
  box-shadow: 0 4rpx 12rpx rgba(16, 185, 129, 0.4);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.w-modal-slider-box {
  margin-bottom: 32rpx;
}

.w-slider-extremes {
  display: flex;
  justify-content: space-between;
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 0 10rpx;
  margin-top: 4rpx;
}

.w-modal-action-row {
  display: flex;
  gap: 16rpx;
  margin-top: 10rpx;
}

.w-cancel-btn {
  flex: 1;
  height: 84rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
  white-space: nowrap;
  background-color: var(--rgm-card-3, #242429);
  color: var(--rgm-text-2, #a1a1aa);
  font-size: 26rpx;
  font-weight: 600;
  border-radius: 20rpx;
  border: none;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.w-save-btn {
  flex: 2;
  height: 84rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
  white-space: nowrap;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #10b981 0%, #059669 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 20rpx;
  border: none;
  box-shadow: 0 6rpx 20rpx rgba(16, 185, 129, 0.4);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.progress-bar-bg {
  width: 100%;
  height: 16rpx;
  background-color: var(--rgm-card-3, #2c2c2e);
  border-radius: 8rpx;
  overflow: hidden;
  margin-bottom: 32rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.progress-bar-fill {
  height: 100%;
  background: var(--rgm-brand-grad, linear-gradient(90deg, #fc4c02 0%, #ff833a 100%));
  border-radius: 8rpx;
  transition: width 0.3s ease;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.progress-bar-fill.fill-emerald {
  background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.week-days-strip {
  display: flex;
  justify-content: space-between;
  gap: 8rpx;
  margin-bottom: 26rpx;
  padding: 16rpx 10rpx;
  background-color: var(--rgm-card, #121214);
  border-radius: 20rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.04));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.day-strip-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8rpx 4rpx;
  border-radius: 14rpx;
  border: 1rpx solid transparent;
  transition: all 0.2s ease;
}

.day-strip-col.is-today {
  background-color: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.38);
}

.d-name {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
  font-weight: 600;
  margin-bottom: 4rpx;
}

.day-strip-col.is-today .d-name {
  color: var(--rgm-green, #34d399);
}

.d-date {
  font-size: 16rpx;
  color: var(--rgm-text-3, #52525b);
  margin-bottom: 10rpx;
}

.day-strip-col.is-today .d-date {
  color: var(--rgm-text-2, #a1a1aa);
}

.d-val-pill {
  min-width: 42rpx;
  height: 38rpx;
  padding: 0 6rpx;
  border-radius: 10rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--rgm-card-2, #1a1a1e);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.d-val-pill.active-run {
  background-color: rgba(16, 185, 129, 0.2);
  border: 1rpx solid #10b981;
}

.d-km-num {
  font-size: 18rpx;
  font-weight: 800;
  color: var(--rgm-green, #34d399);
}

.d-km-dash {
  font-size: 16rpx;
  color: var(--rgm-text-3, #52525b);
}

/* ── TODAY'S WORKOUT PLAN CARD (IN WEEK VIEW) ── */
.today-workout-container {
  margin-top: 10rpx;
  margin-bottom: 20rpx;
}

/* ── 我的下一场约跑 ── */
.next-run-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(252, 76, 2, 0.18) 0%, #151518 70%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));
  border-radius: 28rpx;
  padding: 26rpx 28rpx;
  margin-bottom: 28rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.nr-header { display: flex; flex-direction: row; justify-content: space-between; align-items: center; margin-bottom: 14rpx; }
.nr-badge { display: flex; flex-direction: row; align-items: center; gap: 10rpx; }
.nr-pulse { width: 14rpx; height: 14rpx; border-radius: 50%; background: var(--rgm-brand, #fc4c02); box-shadow: 0 0 12rpx var(--rgm-brand, #fc4c02);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2); }
.nr-badge-text { font-size: 24rpx; color: var(--rgm-brand-text, #fc4c02); font-weight: 700; }
.nr-countdown { font-size: 24rpx; color: var(--rgm-amber, #fbbf24); font-weight: 600; }
.nr-title { display: block; font-size: 32rpx; font-weight: 800; color: var(--rgm-text, #ffffff); margin-bottom: 12rpx; }
.nr-meta-row { margin-bottom: 6rpx; }
.nr-meta { font-size: 25rpx; color: var(--rgm-text, #e4e4e7); }
.nr-meta.highlight { color: var(--rgm-text, #ffffff); font-weight: 600; }
.nr-meta.dim { color: var(--rgm-text-2, #a1a1aa); font-size: 23rpx; }
.nr-actions { display: flex; flex-direction: row; gap: 16rpx; margin-top: 18rpx; }
.nr-btn {
  flex: 1;
  min-width: 0;
  height: 68rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  border-radius: 9999rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  margin: 0;
  padding: 0 12rpx;
  white-space: nowrap;
}
.nr-btn::after { border: none; }
.nr-btn.primary { background: var(--rgm-brand, #fc4c02); border-color: var(--rgm-brand, #fc4c02); font-weight: 700;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2); }

/* 今日训练课移到首页第一屏 */
.home-today {
  margin-top: 0;
  margin-bottom: 22rpx;
}

.fitness-toggle-row {
  margin-top: 20rpx;
  padding: 18rpx 0 6rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  text-align: center;
}

.fitness-toggle-text {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.year-toggle-row {
  margin-bottom: 0;
}

.today-workout-card {
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 24rpx 20rpx;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.today-workout-card.is-completed {
  border-color: rgba(48, 209, 88, 0.4);
  background-color: rgba(48, 209, 88, 0.03);
}

.today-workout-card.tw-border-race {
  border-color: rgba(255, 45, 85, 0.45);
  background: var(--rgm-card, linear-gradient(180deg, rgba(255, 45, 85, 0.08) 0%, rgba(26, 26, 30, 0.95) 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tw-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14rpx;
}

.tw-header-left {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.tw-icon {
  font-size: 26rpx;
}

.tw-section-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.tw-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
}

.tw-badge-easy { background: rgba(48, 209, 88, 0.15); color: var(--rgm-green, #30d158); }
.tw-badge-tempo { background: rgba(10, 132, 255, 0.15); color: var(--rgm-blue, #0a84ff); }
.tw-badge-interval { background: rgba(255, 159, 10, 0.15); color: var(--rgm-amber, #ff9f0a); }
.tw-badge-long { background: var(--rgm-brand-tint, rgba(175, 82, 222, 0.15)); color: var(--rgm-brand-text, #af52de); }
.tw-badge-trail { background: rgba(94, 92, 230, 0.15); color: var(--rgm-blue, #5e5ce6); }
.tw-badge-cross { background: rgba(255, 55, 95, 0.15); color: var(--rgm-red, #ff375f); }
.tw-badge-race { background: rgba(255, 45, 85, 0.25); color: var(--rgm-red, #ff375f); border: 1rpx solid rgba(255, 45, 85, 0.4); font-weight: bold; }
.tw-badge-rest { background: rgba(142, 142, 147, 0.15); color: var(--rgm-text-3, #8e8e93); }

.tw-header-right {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.tw-actual-badge {
  font-size: 18rpx;
  font-weight: bold;
  padding: 4rpx 10rpx;
  border-radius: 10rpx;
  background: rgba(48, 209, 88, 0.15);
  color: var(--rgm-green, #30d158);
  border: 1rpx solid rgba(48, 209, 88, 0.3);
}

.tw-link {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.tw-body {
  margin-bottom: 16rpx;
}

.tw-title-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12rpx;
  margin-bottom: 10rpx;
}

.tw-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #f4f4f5);
  flex: 1;
}

.tw-dist {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.tw-dist-num {
  font-size: 38rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.tw-dist-unit {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.tw-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 12rpx;
}

.tw-metric-tag {
  font-size: 20rpx;
  font-weight: 500;
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
}

.tw-metric-tag.pace-tag {
  background-color: var(--rgm-card-2, #1c1c1e);
  color: var(--rgm-brand-text, #af52de);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tw-metric-tag.hr-tag {
  background-color: var(--rgm-card-2, #1c1c1e);
  color: var(--rgm-green, #30d158);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tw-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  margin-bottom: 10rpx;
}

.tw-coach-notes {
  background-color: rgba(255, 159, 10, 0.1);
  border: 1rpx solid rgba(255, 159, 10, 0.25);
  border-radius: 16rpx;
  padding: 12rpx 16rpx;
  margin-bottom: 12rpx;
}

.tw-coach-title {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-amber, #ff9f0a);
  display: block;
  margin-bottom: 4rpx;
}

.tw-coach-text {
  font-size: 20rpx;
  color: var(--rgm-amber, #ffe0b2);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

/* ── Post-Check-In Runner Feeling, Notes & Photos Box ── */
.tw-checkin-log-box {
  margin-top: 12rpx;
  margin-bottom: 6rpx;
}

.tw-checkin-filled {
  background-color: var(--rgm-card-2, rgba(16, 185, 129, 0.08));
  border: 1rpx solid rgba(16, 185, 129, 0.3);
  border-radius: 16rpx;
  padding: 14rpx 18rpx;
}

.tw-checkin-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.tw-checkin-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10rpx;
}

.tw-feel-pill {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
}

.tw-rpe-pill {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-amber, #f59e0b);
  background: rgba(245, 158, 11, 0.15);
  border: 1rpx solid rgba(245, 158, 11, 0.35);
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
}

.tw-checkin-lbl {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #a1a1aa);
}

.tw-checkin-edit-btn {
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  flex-shrink: 0;
}

.tw-checkin-edit-txt {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-text, #f4f4f5);
}

.tw-athlete-notes-text {
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.45;
  display: block;
  margin-top: 6rpx;
}

.tw-photos-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-top: 12rpx;
}

.tw-photo-thumb {
  width: 116rpx;
  height: 116rpx;
  border-radius: 14rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  background-color: var(--rgm-card, #18181b);
}

.tw-checkin-empty-cta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14rpx 18rpx;
  border-radius: 16rpx;
  background: rgba(16, 185, 129, 0.08);
  border: 1rpx dashed rgba(16, 185, 129, 0.45);
}

.tw-cta-left {
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  font-weight: 600;
}

.tw-cta-right {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-green, #10b981);
  flex-shrink: 0;
}

/* ── Check-in Log Modal ── */
.checkin-log-mask {
  z-index: 1050;
}

.checkin-log-modal {
  width: 92%;
  max-width: 680rpx;
  max-height: 84vh;
  background-color: var(--rgm-card, #16161a);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 32rpx;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.checkin-log-body {
  padding: 24rpx 28rpx;
  max-height: 62vh;
  box-sizing: border-box;
}

.checkin-field-group {
  margin-bottom: 26rpx;
}

.checkin-field-label {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #f4f4f5);
  display: block;
  margin-bottom: 14rpx;
}

.checkin-feel-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
}

.checkin-feel-chip {
  padding: 14rpx 10rpx;
  border-radius: 16rpx;
  background-color: var(--rgm-card-2, #222228);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  text-align: center;
}

.checkin-feel-chip.active {
  background-color: rgba(16, 185, 129, 0.18);
  border-color: #10b981;
}

.checkin-feel-txt {
  font-size: 23rpx;
  font-weight: 600;
  color: var(--rgm-text, #e4e4e7);
}

.checkin-feel-chip.active .checkin-feel-txt {
  color: var(--rgm-green, #10b981);
  font-weight: 800;
}

.checkin-rpe-row {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 8rpx;
}

.checkin-rpe-pill {
  height: 56rpx;
  border-radius: 12rpx;
  background-color: var(--rgm-card-2, #222228);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #a1a1aa);
}

.checkin-rpe-pill.active.easy {
  background-color: #10b981;
  border-color: #10b981;
  color: #ffffff;
}
.checkin-rpe-pill.active.mod {
  background-color: #3b82f6;
  border-color: #3b82f6;
  color: #ffffff;
}
.checkin-rpe-pill.active.hard {
  background-color: #f59e0b;
  border-color: #f59e0b;
  color: #ffffff;
}
.checkin-rpe-pill.active.max {
  background-color: #ef4444;
  border-color: #ef4444;
  color: #ffffff;
}

.checkin-notes-textarea {
  width: 100%;
  min-height: 150rpx;
  padding: 18rpx 20rpx;
  box-sizing: border-box;
  border-radius: 18rpx;
  background-color: var(--rgm-card-2, #222228);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  font-size: 24rpx;
  color: var(--rgm-text, #f4f4f5);
  line-height: 1.5;
}

.checkin-photo-uploader-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.checkin-photo-item {
  width: 156rpx;
  height: 156rpx;
  border-radius: 18rpx;
  position: relative;
  overflow: hidden;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
}

.checkin-photo-img {
  width: 100%;
  height: 100%;
}

.checkin-photo-del {
  position: absolute;
  top: 6rpx;
  right: 6rpx;
  width: 38rpx;
  height: 38rpx;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.68);
  color: #ffffff;
  font-size: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.checkin-photo-add {
  width: 156rpx;
  height: 156rpx;
  border-radius: 18rpx;
  background-color: var(--rgm-card-2, #222228);
  border: 2rpx dashed var(--rgm-line, rgba(255, 255, 255, 0.22));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
}

.add-plus {
  font-size: 38rpx;
}

.add-txt {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 600;
}

.checkin-modal-footer {
  display: flex;
  gap: 18rpx;
  padding: 20rpx 28rpx 28rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.checkin-cancel-btn {
  flex: 1;
  height: 76rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
  white-space: nowrap;
  border-radius: 18rpx;
  background-color: var(--rgm-card-2, #242429);
  color: var(--rgm-text-2, #a1a1aa);
  font-size: 26rpx;
  font-weight: 600;
}

.checkin-save-btn {
  flex: 2;
  height: 76rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
  white-space: nowrap;
  border-radius: 18rpx;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 700;
}

.tw-actions {
  display: flex;
  gap: 14rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  padding-top: 16rpx;
}

.tw-complete-btn {
  flex: 1;
  height: 60rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 12rpx;
  white-space: nowrap;
  border-radius: 14rpx;
  background-color: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  font-size: 24rpx;
  color: var(--rgm-text, #e4e4e7);
  font-weight: 600;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tw-complete-btn.completed {
  background-color: rgba(48, 209, 88, 0.2);
  border-color: #30d158;
  color: var(--rgm-green, #30d158);
  font-weight: bold;
}

.tw-detail-btn {
  height: 60rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24rpx;
  white-space: nowrap;
  border-radius: 14rpx;
  background-color: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  font-size: 22rpx;
  color: var(--rgm-brand-text, #af52de);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.today-workout-card.empty-card {
  padding: 24rpx 20rpx;
}

.empty-tw-content {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.empty-tw-icon {
  font-size: 34rpx;
}

.empty-tw-texts {
  display: flex;
  flex-direction: column;
}

.empty-tw-title {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--rgm-text, #e4e4e7);
}

.empty-tw-sub {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
  margin-top: 4rpx;
}

.stats-grid {
  display: flex;
  justify-content: space-between;
  background-color: var(--rgm-card, #121214);
  border-radius: 24rpx;
  padding: 26rpx 12rpx;
  margin-bottom: 26rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-item.divider {
  border-right: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
}

.stat-val {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.primary-text {
  color: var(--rgm-brand-text, #fc4c02);
}

.accent-text {
  color: var(--rgm-amber, #ff9f0a);
}

.stat-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 6rpx;
}

.goal-embedded-today {
  margin-top: 16rpx;
  margin-bottom: 16rpx;
}

.get-main-box {
  padding: 16rpx 18rpx;
  border-radius: 20rpx;
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
}

.get-main-box.is-completed {
  border-color: rgba(16, 185, 129, 0.38);
  background: rgba(16, 185, 129, 0.06);
}

.get-main-box.is-volt {
  background: #f8fafc;
  border-color: rgba(15, 23, 42, 0.08);
}

.get-main-box.is-volt.is-completed {
  background: #ecfdf5;
  border-color: rgba(16, 185, 129, 0.35);
}

.get-main-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
}

.get-info-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.get-meta-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-wrap: nowrap;
  min-width: 0;
}

.get-label {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #d4d4d8);
  flex-shrink: 0;
}

.get-dist-txt {
  font-size: 21rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  flex-shrink: 0;
}

.get-pace-txt {
  font-size: 20rpx;
  color: var(--rgm-text-3, #a1a1aa);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.get-more-link {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
  margin-left: auto;
  flex-shrink: 0;
}

.get-title-txt {
  font-size: 25rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.get-action-col {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.get-checkin-btn {
  margin: 0;
  padding: 0 20rpx;
  height: 58rpx;
  line-height: 1.25;
  border-radius: 16rpx;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}

.get-checkin-btn::after {
  border: none;
}

.get-checkin-btn.completed {
  background: rgba(16, 185, 129, 0.16);
  border: 1rpx solid rgba(16, 185, 129, 0.5);
}

.get-checkin-btn-txt {
  font-size: 22rpx;
  font-weight: 800;
  color: #ffffff;
  white-space: nowrap;
}

.get-checkin-btn.completed .get-checkin-btn-txt {
  color: #10b981;
}

.get-log-icon-btn {
  height: 58rpx;
  padding: 0 14rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-3, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  display: flex;
  align-items: center;
  justify-content: center;
}

.get-log-icon-btn.filled {
  border-color: rgba(16, 185, 129, 0.4);
  background: rgba(16, 185, 129, 0.12);
}

.get-log-icon-txt {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #e4e4e7);
  white-space: nowrap;
}

.get-sub-note {
  margin-top: 10rpx;
  padding-top: 10rpx;
  border-top: 1rpx dashed var(--rgm-line, rgba(255, 255, 255, 0.08));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10rpx;
}

.get-sub-note-txt {
  flex: 1;
  min-width: 0;
  font-size: 21rpx;
  color: var(--rgm-text-2, #d4d4d8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.get-sub-note.coach .get-sub-note-txt {
  color: var(--rgm-amber, #fbbf24);
}

.get-sub-edit-arrow {
  flex-shrink: 0;
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-green, #10b981);
}

.get-empty-bar {
  padding: 16rpx 20rpx;
  border-radius: 18rpx;
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.04));
  border: 1rpx dashed var(--rgm-line, rgba(255, 255, 255, 0.14));
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.get-empty-bar.is-volt {
  background: #f8fafc;
  border-color: rgba(15, 23, 42, 0.14);
}

.get-empty-left {
  font-size: 23rpx;
  font-weight: 600;
  color: var(--rgm-text-2, #a1a1aa);
}

.get-empty-right {
  font-size: 23rpx;
  font-weight: 700;
  color: #fc4c02;
}

.sync-action-box {
  margin-top: 8rpx;
}

.sync-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  height: 84rpx;
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.btn-icon {
  font-size: 30rpx;
}

/* Sections & Spacings */
.section-container {
  margin-bottom: 30rpx;
}

.section-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.section-title {
  font-size: 30rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.title-with-pill {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.month-active-badge {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  padding: 2rpx 12rpx;
  border-radius: 16rpx;
}

.expand-acts-toggle {
  text-align: center;
  padding: 20rpx 0 8rpx 0;
}

.expand-acts-text {
  font-size: 24rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 500;
}

.sub-date {
  font-size: 22rpx;
  color: var(--rgm-text-3, #636366);
}

.see-all-link {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 600;
  padding: 8rpx 0 8rpx 16rpx;
}

.health-grid-4 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22rpx;
}

.health-tile {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 28rpx;
  padding: 28rpx 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tile-top {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 14rpx;
}

.tile-icon {
  font-size: 26rpx;
}

.tile-name {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.tile-val-row {
  display: flex;
  align-items: baseline;
  gap: 6rpx;
}

.tile-main-val {
  font-size: 38rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.tile-unit {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.text-rose {
  color: var(--rgm-red, #ff453a);
}

.text-amber {
  color: var(--rgm-amber, #ffd60a);
}

.text-cyan {
  color: var(--rgm-green, #30d158);
}

.tile-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #636366);
  margin-top: 10rpx;
}

.mini-progress-bg {
  width: 100%;
  height: 8rpx;
  background-color: var(--rgm-card-3, #2c2c2e);
  border-radius: 4rpx;
  margin-top: 16rpx;
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.mini-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ffd60a 0%, #30d158 100%);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

/* Fitness & Form Card Styles (Matching iOS DashboardView minimalist layout) */
.fitness-chart-card {
  background-color: var(--rgm-card, #141418);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 28rpx 24rpx 24rpx;
  margin-bottom: 20rpx;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.35));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.fitness-header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.title-row-with-icon {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.zap-icon {
  font-size: 26rpx;
  color: var(--rgm-brand, #fc4c02);
}

.title-with-desc {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.sub-formula {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
  margin-top: 6rpx;
}

.fitness-status-badge {
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.fsb-text {
  font-size: 20rpx;
  font-weight: 800;
  line-height: 1.1;
}

.metrics-pill-group {
  display: flex;
  align-items: stretch;
  gap: 16rpx;
}

.metrics-pill-4 {
  gap: 12rpx;
}

.metrics-pill-4 .metric-pill {
  padding: 18rpx 14rpx;
  gap: 6rpx;
}

.metrics-pill-4 .pill-label {
  font-size: 19rpx;
}

.metrics-pill-4 .pill-val {
  font-size: 31rpx;
}

.metrics-pill-4 .pill-sub {
  font-size: 17rpx;
}

.text-vdot {
  color: var(--rgm-brand-text, #fc4c02);
}

.metric-pill {
  flex: 1;
  background-color: var(--rgm-card-2, #1c1c21);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  border-radius: 20rpx;
  padding: 20rpx 20rpx;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8rpx;
  min-width: 0;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.pill-label {
  display: block;
  width: 100%;
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 700;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pill-val {
  display: block;
  width: 100%;
  font-size: 38rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pill-sub {
  display: block;
  width: 100%;
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chart-tooltip {
  background-color: var(--rgm-card-2, #1c1c21);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  border-radius: 16rpx;
  padding: 10rpx 18rpx;
  display: flex;
  gap: 18rpx;
  align-items: center;
  justify-content: space-between;
  font-size: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tip-date {
  color: var(--rgm-text, #ffffff);
  font-weight: 800;
}

.tip-val {
  font-weight: 700;
}

.ios-fitness-mini-chart {
  height: 112rpx;
  padding: 14rpx 16rpx;
  background-color: var(--rgm-card-2, #1c1c21);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 18rpx;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 4rpx;
  box-sizing: border-box;
}

.ios-bar-col {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  border-radius: 6rpx;
  transition: background-color 0.15s ease;
}

.ios-bar-col.is-selected {
  background-color: rgba(59, 130, 246, 0.16);
}

.ios-bar-stack {
  position: relative;
  width: 8rpx;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.ios-bar-atl {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 8rpx;
  border-radius: 4rpx;
  background-color: rgba(244, 63, 94, 0.62);
  transition: height 0.25s ease;
}

.ios-bar-ctl {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 8rpx;
  border-radius: 4rpx;
  background-color: #3b82f6;
  transition: height 0.25s ease;
}

.ios-fitness-legend {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  padding: 0 4rpx;
}

.ios-legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.ios-legend-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  flex-shrink: 0;
}

.ios-legend-label {
  font-size: 19rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 500;
}

/* Recent Activities Styles */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.empty-act-box {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 24rpx;
  padding: 40rpx 24rpx;
  text-align: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.empty-act-text {
  font-size: 24rpx;
  color: var(--rgm-text-3, #636366);
}

.activity-card {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.25));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.act-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.act-name-group {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.act-name {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.readiness-header-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.act-vdot-tag {
  font-size: 20rpx;
  color: #f97316;
  background-color: rgba(249, 115, 22, 0.14);
  border: 1rpx solid rgba(249, 115, 22, 0.32);
  border-radius: 10rpx;
  padding: 2rpx 10rpx;
  font-weight: 800;
  font-family: monospace;
}

.act-elev-tag {
  font-size: 20rpx;
  color: var(--rgm-green, #30d158);
  background-color: rgba(48, 209, 88, 0.12);
  border: 1rpx solid rgba(48, 209, 88, 0.25);
  border-radius: 10rpx;
  padding: 2rpx 10rpx;
  font-weight: bold;
}

.act-time {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.act-data-row {
  display: flex;
  justify-content: space-between;
}

.act-col {
  display: flex;
  flex-direction: column;
}

.act-main-val {
  font-size: 36rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #fc4c02);
}

.act-sub-val {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.act-sub-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #636366);
  margin-top: 6rpx;
}

.unit {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  font-weight: normal;
}

.text-amber {
  color: var(--rgm-amber, #ffd60a);
}

.act-track-row {
  margin-top: 18rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.act-dual-actions {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.act-track-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.08));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
  border-radius: 14rpx;
  padding: 10rpx 18rpx;
}

.act-share-card-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(56, 189, 248, 0.1);
  border: 1rpx solid rgba(56, 189, 248, 0.32);
  border-radius: 14rpx;
  padding: 10rpx 18rpx;
}

.act-share-text {
  font-size: 22rpx;
  color: #38bdf8;
  font-weight: 700;
}

.share-card-entry-btn {
  background: rgba(56, 189, 248, 0.14) !important;
  border: 1rpx solid rgba(56, 189, 248, 0.4) !important;
  color: #38bdf8 !important;
}

.empty-share-pill {
  padding: 10rpx 20rpx;
  border-radius: 999rpx;
  background: rgba(56, 189, 248, 0.14);
  border: 1rpx solid rgba(56, 189, 248, 0.4);
  color: #38bdf8;
  font-size: 22rpx;
  font-weight: 700;
  line-height: 1.3;
  margin: 0;
  flex-shrink: 0;
}

.act-track-icon {
  font-size: 24rpx;
  margin-right: 10rpx;
}

.act-track-text {
  flex: 1;
  font-size: 22rpx;
  color: var(--rgm-brand-text, #FC4C02);
  font-weight: 600;
}

.act-track-arrow {
  font-size: 24rpx;
  color: var(--rgm-brand-text, #FC4C02);
  font-weight: bold;
}


/* ── Auth Modal in Index ── */
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

.modal-mask.auth-modal-mask {
  padding-top: 0;
  align-items: center;
}

.modal-content {
  width: 670rpx;
  background-color: var(--rgm-card, #18181c);
  border-radius: 36rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  box-shadow: 0 20rpx 60rpx var(--rgm-shadow, rgba(0, 0, 0, 0.8));
  overflow: hidden;
  margin-bottom: 80rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-content.auth-modal-content {
  max-height: 86vh;
  display: flex;
  flex-direction: column;
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

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 36rpx 36rpx 20rpx;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
}

.modal-title {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.close-hit {
  width: 60rpx;
  height: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn {
  font-size: 32rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.modal-body {
  padding: 32rpx 36rpx 44rpx;
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
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24rpx;
  white-space: nowrap;
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

.field-label {
  font-size: 24rpx;
  color: var(--rgm-text-2, #aeaeb2);
  margin-top: 12rpx;
  margin-bottom: 6rpx;
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

.placeholder-style {
  color: var(--rgm-text-3, #636366);
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
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24rpx;
  white-space: nowrap;
  background-color: var(--rgm-brand, #07c160);
  color: var(--rgm-text, #ffffff);
  font-size: 30rpx;
  font-weight: bold;
  border-radius: 24rpx;
  border: none;
  margin-top: 10rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── 2026 Yearly Running Mileage Card ── */
.yearly-section {
  margin-bottom: 48rpx;
}

.year-pct-badge {
  background: linear-gradient(135deg, rgba(244, 63, 94, 0.16) 0%, rgba(251, 113, 133, 0.08) 100%);
  border: 1rpx solid rgba(244, 63, 94, 0.35);
  border-radius: 20rpx;
  padding: 8rpx 20rpx;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.year-pct-num {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-red, #f43f5e);
  line-height: 1.1;
}

.year-pct-sub {
  font-size: 18rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.year-card-body {
  margin-top: 20rpx;
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 32rpx;
  padding: 32rpx 28rpx;
  box-shadow: 0 10rpx 30rpx var(--rgm-shadow, rgba(0, 0, 0, 0.4));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.year-progress-box {
  margin-bottom: 24rpx;
}

.year-progress-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.highlight-val {
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  font-size: 28rpx;
}

.progress-right-label {
  color: var(--rgm-text-3, #71717a);
}

.year-progress-track {
  width: 100%;
  height: 16rpx;
  background-color: var(--rgm-card-3, #242429);
  border-radius: 8rpx;
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.year-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #f43f5e 0%, #fb7185 60%, #f59e0b 100%);
  border-radius: 8rpx;
  transition: width 0.4s ease;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

/* 12-Month Bar Chart */
.monthly-chart-box {
  background-color: var(--rgm-card, #17171b);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 24rpx;
  padding: 20rpx 16rpx 16rpx 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.selected-month-tip {
  background-color: var(--rgm-card-2, #202026);
  border-radius: 14rpx;
  padding: 10rpx 16rpx;
  margin-bottom: 16rpx;
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.selected-month-tip.placeholder {
  background-color: transparent;
  padding: 4rpx 0 12rpx 4rpx;
}

.tip-dot {
  font-size: 22rpx;
}

.tip-text {
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
}

.tip-hl {
  font-weight: bold;
  color: var(--rgm-red, #f43f5e);
}

.tip-tag.current {
  color: var(--rgm-green, #34d399);
  font-weight: bold;
  font-size: 20rpx;
  margin-left: 6rpx;
}

.tip-text-dim {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

.months-bar-flex {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  height: 250rpx;
  padding: 10rpx 4rpx 0 4rpx;
}

.month-bar-col {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  cursor: pointer;
  padding: 0 2rpx;
}

.bar-val-top {
  height: 32rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bar-km-text {
  font-size: 16rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 600;
  text-align: center;
}

.bar-km-empty {
  font-size: 16rpx;
}

.bar-pillar-track {
  width: 22rpx;
  height: 160rpx;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border-radius: 12rpx;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  overflow: hidden;
  position: relative;
  transition: all 0.2s ease;
}

.month-bar-col.is-selected .bar-pillar-track {
  border: 2rpx solid #38bdf8;
  box-shadow: 0 0 12rpx rgba(56, 189, 248, 0.8);
}

.bar-pillar-fill {
  width: 100%;
  border-radius: 12rpx;
  transition: height 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.current-fill {
  background: linear-gradient(180deg, #34d399 0%, #059669 100%);
  box-shadow: 0 0 12rpx rgba(16, 185, 129, 0.6);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.past-fill {
  background: linear-gradient(180deg, #fb7185 0%, #e11d48 100%);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.zero-fill {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
}

.bar-month-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 10rpx;
}

.month-name {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
}

.month-bar-col.is-current .month-name {
  color: var(--rgm-green, #34d399);
  font-weight: bold;
}

.month-bar-col.is-selected .month-name {
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

.current-indicator-dot {
  width: 6rpx;
  height: 6rpx;
  border-radius: 3rpx;
  background-color: #34d399;
  margin-top: 4rpx;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

/* 3 Metric Tiles */
.year-metrics-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16rpx;
  margin-top: 24rpx;
}

.year-metric-tile {
  background-color: var(--rgm-card, #17171b);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-radius: 20rpx;
  padding: 20rpx 16rpx;
  display: flex;
  flex-direction: column;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.m-top {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 8rpx;
}

.m-icon {
  font-size: 22rpx;
}

.m-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.m-val-box {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.m-val {
  font-size: 30rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.m-unit {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
}


.text-emerald {
  color: var(--rgm-green, #34d399) !important;
}

/* Best Month Banner */
.year-best-banner {
  background: linear-gradient(90deg, rgba(245, 158, 11, 0.12) 0%, rgba(245, 158, 11, 0.04) 100%);
  border: 1rpx solid rgba(245, 158, 11, 0.25);
  border-radius: 20rpx;
  padding: 18rpx 24rpx;
  margin-top: 20rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.best-badge {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-amber, #f59e0b);
}

.best-info {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d4d4d8);
}

.best-km {
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.best-pace {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

/* Empty Chart State */
.empty-chart-box {
  padding: 60rpx 40rpx;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.empty-chart-icon {
  font-size: 52rpx;
  margin-bottom: 16rpx;
  display: block;
}

.empty-chart-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 12rpx;
  display: block;
}

.empty-chart-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.6;
  max-width: 500rpx;
  display: block;
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
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── 🔔 Notification Center Modal ── */
.notif-center-modal {
  max-width: 680rpx;
  width: 92%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.title-with-pill {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.notif-count-pill {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #fc4c02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  padding: 2rpx 14rpx;
  border-radius: 12rpx;
  font-weight: bold;
}

.header-actions-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.btn-read-all {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  padding: 6rpx 14rpx;
  border-radius: 8rpx;
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.06));
}

.notif-modal-body {
  max-height: 60vh;
  box-sizing: border-box;
}

.notif-loading-box, .notif-empty-box {
  padding: 60rpx 30rpx;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.empty-icon {
  font-size: 64rpx;
  margin-bottom: 16rpx;
}

.empty-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 10rpx;
}

.empty-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
  line-height: 1.5;
  padding: 0 20rpx;
}

.notif-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  padding: 10rpx 0;
}

.notif-card-item {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 18rpx;
  padding: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  transition: all 0.2s;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.notif-card-item.is-unread {
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
  background: var(--rgm-card, linear-gradient(135deg, rgba(252, 76, 2, 0.06) 0%, #1a1a1e 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.notif-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.notif-title-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.unread-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 6rpx;
  background-color: var(--rgm-brand, #fc4c02);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.notif-item-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.notif-time-tag {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

.notif-content-preview {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d4d4d8);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

.notif-footer-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-top: 8rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
}


.notif-action-hint {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

/* ── 🎯 Canova Critique Detail Modal ── */
.critique-detail-modal {
  max-width: 680rpx;
  width: 92%;
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  background: var(--rgm-card, #141418);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 28rpx;
  box-shadow: 0 20rpx 60rpx var(--rgm-shadow, rgba(0, 0, 0, 0.65));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.critique-header-title-box {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.critique-header-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.ai-header-badge {
  font-size: 18rpx;
  color: var(--rgm-blue, #38bdf8);
  background: rgba(56, 189, 248, 0.12);
  border: 1rpx solid rgba(56, 189, 248, 0.3);
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  font-weight: 500;
}

.critique-header-icon {
  font-size: 32rpx;
}

.critique-header-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

.ai-prominent-notice-banner-inline {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: rgba(56, 189, 248, 0.1);
  border: 1rpx solid rgba(56, 189, 248, 0.28);
  border-radius: 12rpx;
  padding: 10rpx 18rpx;
  margin-bottom: 16rpx;
}

.ai-prominent-notice-banner-inline .ai-notice-robot {
  font-size: 24rpx;
}

.ai-prominent-notice-banner-inline .ai-notice-txt {
  font-size: 22rpx;
  color: var(--rgm-blue, #7dd3fc);
  font-weight: 500;
  letter-spacing: 0.5rpx;
}

.critique-detail-body {
  max-height: 68vh;
  box-sizing: border-box;
  padding: 10rpx 0 20rpx 0;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

/* 关联训练卡片 */
.critique-run-summary-card {
  background: var(--rgm-card-2, #1c1c22);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  cursor: pointer;
  transition: all 0.2s;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.critique-run-summary-card:active {
  background: var(--rgm-card-3, #24242c);
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.run-sum-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.run-sum-name-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.run-sum-badge {
  font-size: 18rpx;
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.12);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: 600;
}

.run-sum-name {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  max-width: 320rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-sum-time {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

.run-sum-metrics {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 12rpx 0;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 14rpx;
}

.run-metric-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4rpx;
}

.run-metric-item .m-val {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #f4f4f5);
  line-height: 1.1;
}

.run-metric-item .m-val .m-unit {
  font-size: 18rpx;
  font-weight: normal;
  color: var(--rgm-text-2, #a1a1aa);
  margin-left: 4rpx;
}

.m-lbl {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
}

.run-track-pill-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  padding: 8rpx 0;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.1));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
  border-radius: 12rpx;
}

.pill-icon {
  font-size: 22rpx;
}

.pill-text {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 600;
}

.pill-arr {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #fc4c02);
}

/* 评语卡片列表 */
.critique-sections-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.critique-section-card {
  border-radius: 20rpx;
  padding: 22rpx 20rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.critique-section-card.special {
  background: var(--rgm-card, linear-gradient(145deg, rgba(16, 185, 129, 0.08) 0%, rgba(20, 20, 24, 0.9) 100%));
  border: 1rpx solid rgba(16, 185, 129, 0.25);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.critique-section-card.special .sec-title {
  color: var(--rgm-green, #34d399);
}

.critique-section-card.advice {
  background: var(--rgm-card, linear-gradient(145deg, rgba(251, 191, 36, 0.08) 0%, rgba(20, 20, 24, 0.9) 100%));
  border: 1rpx solid rgba(251, 191, 36, 0.25);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.critique-section-card.advice .sec-title {
  color: var(--rgm-amber, #fbbf24);
}

.critique-section-card.target {
  background: var(--rgm-card, linear-gradient(145deg, rgba(249, 115, 22, 0.08) 0%, rgba(20, 20, 24, 0.9) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(249, 115, 22, 0.25));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.critique-section-card.target .sec-title {
  color: var(--rgm-brand-text, #fb923c);
}

.critique-section-card.general {
  background: var(--rgm-card-2, #1a1a1f);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.critique-section-card.general .sec-title {
  color: var(--rgm-text, #f4f4f5);
}

.sec-header {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.sec-icon {
  font-size: 28rpx;
}

.sec-title {
  font-size: 26rpx;
  font-weight: 700;
  line-height: 1.3;
}

.sec-text {
  font-size: 24rpx;
  color: var(--rgm-text-2, #d4d4d8);
  line-height: 1.65;
  letter-spacing: 0.5rpx;
}

/* 底部操作按钮 */
.critique-actions-row {
  display: flex;
  gap: 16rpx;
  padding-top: 8rpx;
  padding-bottom: 16rpx;
}

.critique-action-btn {
  flex: 1;
  min-width: 0;
  height: 80rpx;
  line-height: 1.25;
  padding: 0 16rpx;
  margin: 0;
  border-radius: 16rpx;
  font-size: 25rpx;
  font-weight: 600;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  box-sizing: border-box;
}

.critique-action-btn::after {
  border: none;
}

.critique-action-btn.track-btn {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  color: var(--rgm-brand-text, #fc4c02);
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
}

.critique-action-btn.track-btn:active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.3));
}

.critique-action-btn.coach-btn {
  background: var(--rgm-card-3, #27272a);
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.critique-action-btn.coach-btn:active {
  background: var(--rgm-card-3, #3f3f46);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── 首页「跑团打卡动态」快捷入口条（位于今日课表上方） ── */
.home-feed-shortcut-bar {
  margin-top: 6rpx;
  margin-bottom: 20rpx;
  padding: 20rpx 24rpx;
  border-radius: 26rpx;
  background: var(--rgm-card, linear-gradient(135deg, rgba(252, 76, 2, 0.14) 0%, #16161a 85%));
  border: 1.5rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.36));
  box-shadow: 0 8rpx 24rpx var(--rgm-shadow, rgba(0, 0, 0, 0.28));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
  --rgm-text: var(--rgm-ink);
  --rgm-text-2: var(--rgm-ink-2);
  --rgm-text-3: var(--rgm-ink-3);
}

.hfs-left {
  display: flex;
  align-items: center;
  gap: 14rpx;
  flex: 1;
  min-width: 0;
}

.hfs-avatar-stack {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.hfs-avatar {
  width: 44rpx;
  height: 44rpx;
  border-radius: 22rpx;
  border: 2rpx solid var(--rgm-card, #18181b);
  margin-left: -12rpx;
}

.hfs-avatar:first-child {
  margin-left: 0;
}

.hfs-fire-icon {
  font-size: 36rpx;
  flex-shrink: 0;
}

.hfs-text-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.hfs-title-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-wrap: wrap;
}

.hfs-title {
  font-size: 25rpx;
  font-weight: 800;
  color: var(--rgm-text, #f4f4f5);
}

.hfs-stat-pill {
  font-size: 19rpx;
  font-weight: 700;
  padding: 2rpx 10rpx;
  border-radius: 14rpx;
}

.hfs-stat-pill.checkin {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16));
  color: var(--rgm-brand-text, #fc4c02);
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
}

.hfs-stat-pill.critique {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text-2, #a1a1aa);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
}

.hfs-sub-line {
  font-size: 21rpx;
  color: var(--rgm-text-2, #a1a1aa);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hfs-cta {
  flex-shrink: 0;
  background: var(--rgm-brand, #fc4c02);
  padding: 8rpx 18rpx;
  border-radius: 22rpx;
}

.hfs-cta-text {
  font-size: 21rpx;
  font-weight: 700;
  color: #ffffff;
}

/* ── 首页核心板块 Flex 容器（支持用户自定义显示次序） ── */
.home-modules-container {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.home-modules-container .yearly-section {
  margin-bottom: 24rpx;
}

/* 顶部快捷「↕️ 排版」胶囊按钮 */
.layout-order-pill {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.07));
  border: 1rpx solid var(--rgm-line-2, rgba(255, 255, 255, 0.14));
}

.layout-order-pill:active {
  opacity: 0.78;
}

.layout-order-pill-txt {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #d4d4d8);
  white-space: nowrap;
}

/* 底部常驻「自定义首页板块显示次序」入口条 */
.home-layout-customize-bar {
  margin-top: 4rpx;
  margin-bottom: 48rpx;
  padding: 20rpx 26rpx;
  border-radius: 22rpx;
  background: var(--rgm-card, rgba(255, 255, 255, 0.04));
  border: 1rpx dashed var(--rgm-line-2, rgba(255, 255, 255, 0.16));
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.home-layout-customize-bar:active {
  opacity: 0.8;
}

.hlc-left {
  font-size: 23rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #a1a1aa);
}

.hlc-right {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

/* ── 独立「今日训练课表」板块卡片 ── */
.today-standalone-card {
  margin-bottom: 20rpx;
  border-radius: 24rpx;
  background: var(--rgm-card, #141418);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.22));
  overflow: hidden;
  --rgm-text: var(--rgm-ink);
  --rgm-text-2: var(--rgm-ink-2);
  --rgm-text-3: var(--rgm-ink-3);
}

.get-main-box.standalone {
  padding: 24rpx 24rpx;
  border-radius: 24rpx;
  background: var(--rgm-card, #141418);
  border: none;
}

.get-main-box.standalone.is-completed {
  background: rgba(16, 185, 129, 0.08);
}

.get-main-box.standalone.is-volt {
  background: #ffffff;
}

.get-main-box.standalone.is-volt.is-completed {
  background: #ecfdf5;
}

.get-empty-bar.standalone {
  padding: 24rpx 26rpx;
  border-radius: 28rpx;
  border: none;
  background: var(--rgm-card, #141418);
}

.get-empty-bar.standalone.is-volt {
  background: #ffffff;
}

/* ── 周/月完成度：同屏双饼图卡片（无需在周/月间跳选，饼图下直接展示 完成/计划 km） ── */
.goal-unified-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
  min-width: 0;
}

.goal-unified-title {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  line-height: 1.25;
}

.goal-unified-sub {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
}

.dual-pie-overview-grid {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 18rpx;
  margin-bottom: 20rpx;
}

.dpo-card {
  flex: 1;
  min-width: 0;
  padding: 20rpx 18rpx 18rpx;
  border-radius: 24rpx;
  background: var(--rgm-card-2, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  display: flex;
  flex-direction: column;
  align-items: center;
}

.dpo-card:active {
  opacity: 0.86;
}

.dpo-card-head {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8rpx;
  margin-bottom: 16rpx;
}

.dpo-period-title {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-text-2, #d4d4d8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.dpo-period-pct {
  font-size: 26rpx;
  font-weight: 900;
  line-height: 1;
  flex-shrink: 0;
}

.dpo-pie-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 4rpx 0 16rpx;
}

.goal-pie-chart {
  width: 136rpx;
  height: 136rpx;
  border-radius: 50%;
  position: relative;
  box-shadow: inset 0 0 0 2rpx var(--rgm-line, rgba(255, 255, 255, 0.12)), 0 6rpx 18rpx rgba(0, 0, 0, 0.2);
}

.pie-start-spoke {
  position: absolute;
  top: 0;
  left: 50%;
  width: 2rpx;
  height: 50%;
  margin-left: -1rpx;
  background-color: var(--rgm-card-2, #18181c);
  opacity: 0.8;
}

.pie-origin-dot {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 12rpx;
  height: 12rpx;
  margin-top: -6rpx;
  margin-left: -6rpx;
  border-radius: 50%;
  background-color: var(--rgm-card-2, #18181c);
  border: 2rpx solid rgba(255, 255, 255, 0.55);
}

.dpo-km-ratio {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 6rpx;
  line-height: 1.15;
}

.dpo-km-done {
  font-size: 36rpx;
  font-weight: 900;
}

.dpo-km-sep {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text-3, #8e8e93);
}

.dpo-km-target {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.dpo-km-unit {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-text-3, #8e8e93);
  margin-left: 2rpx;
}

.dpo-km-caption {
  margin-top: 6rpx;
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
  white-space: nowrap;
}

/* ── 自定义首页板块显示次序弹窗 ── */
.layout-order-modal {
  width: 680rpx;
  max-height: 84vh;
  margin-bottom: 0;
}

.layout-order-body {
  padding: 24rpx 28rpx 32rpx;
}

.layout-order-desc {
  display: block;
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.45;
  margin-bottom: 20rpx;
}

.layout-order-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  margin-bottom: 28rpx;
}

.layout-order-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
  padding: 18rpx 20rpx;
  border-radius: 20rpx;
  background: var(--rgm-card-2, #1c1c21);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.loi-left {
  display: flex;
  align-items: center;
  gap: 14rpx;
  flex: 1;
  min-width: 0;
}

.loi-rank-badge {
  width: 38rpx;
  height: 38rpx;
  border-radius: 12rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.36));
  color: var(--rgm-brand-text, #fc4c02);
  font-size: 21rpx;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.loi-icon {
  font-size: 32rpx;
  flex-shrink: 0;
}

.loi-text-col {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
  flex: 1;
  min-width: 0;
}

.loi-title {
  font-size: 25rpx;
  font-weight: 800;
  color: var(--rgm-text, #f4f4f5);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.loi-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.loi-actions {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-shrink: 0;
}

.loi-btn {
  height: 52rpx;
  padding: 0 16rpx;
  border-radius: 14rpx;
  background: var(--rgm-card-3, #27272a);
  border: 1rpx solid var(--rgm-line-2, rgba(255, 255, 255, 0.14));
  display: flex;
  align-items: center;
  justify-content: center;
}

.loi-btn.arrow-btn {
  width: 52rpx;
  padding: 0;
}

.loi-btn.top-btn {
  background: rgba(16, 185, 129, 0.14);
  border-color: rgba(16, 185, 129, 0.35);
}

.loi-btn.top-btn .loi-btn-txt {
  color: var(--rgm-green, #10b981);
  font-size: 20rpx;
}

.loi-btn.disabled {
  opacity: 0.32;
}

.loi-btn-txt {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--rgm-text, #f4f4f5);
  line-height: 1;
}

.layout-order-footer {
  display: flex;
  align-items: center;
  gap: 18rpx;
}

.loi-footer-btn {
  flex: 1;
  height: 80rpx;
  border-radius: 22rpx;
  font-size: 26rpx;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
}

.loi-footer-btn.reset {
  background: var(--rgm-card-3, #27272a);
  border: 1rpx solid var(--rgm-line-2, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text-2, #d4d4d8);
}

.loi-footer-btn.save {
  background: linear-gradient(135deg, #fc4c02 0%, #ff6b2b 100%);
  color: #ffffff;
  border: none;
}

</style>
