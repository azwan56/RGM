<template>
  <view class="coach-page" :class="themeClass">
    <!-- Header -->
    <view class="coach-header">
      <view class="header-left">
        <view class="title-row">
          <text class="title-icon">⚡</text>
          <text class="page-title">训练</text>
          <text class="term-info" @click.stop="explainTerm('canova_model')">ⓘ</text>
        </view>
      </view>

      <view style="display: flex; align-items: center; gap: 12rpx;">
        <button class="re-analyze-btn" @click="openCoachChatModal">
          <text class="btn-text">💬 问教练</text>
        </button>
        <button v-if="activeTab === 'analysis'" class="re-analyze-btn" :loading="loading" :disabled="loading" @click="handleReAnalyze">
          <text class="btn-text">{{ loading ? "测算中..." : "🔄 重算" }}</text>
        </button>
      </view>
    </view>

    <!-- ── 分段切换：课表 / 教练诊断 / 身体数据 ── -->
    <view class="coach-tab-bar">
      <view
        class="coach-tab-item"
        :class="{ active: activeTab === 'plan' }"
        @click="activeTab = 'plan'"
      >
        <text class="tab-icon">📅</text>
        <text class="tab-title">课表</text>
      </view>
      <view
        class="coach-tab-item"
        :class="{ active: activeTab === 'analysis' }"
        @click="activeTab = 'analysis'"
      >
        <text class="tab-icon">🎯</text>
        <text class="tab-title">诊断</text>
      </view>
      <view class="coach-tab-item" @click="goToBodyData">
        <text class="tab-icon">📊</text>
        <text class="tab-title">数据 ›</text>
      </view>
    </view>

    <!-- ── PLAN TAB CONTENT ── -->
    <view v-if="activeTab === 'plan'" class="plan-tab-section">
      <!-- 夜间未佩戴手表 · 恢复数据缺失预警横幅（精简一行 + ⓘ 隐藏说明） -->
      <view
        v-if="recoveryDataAvailability?.night_wear_missing || analysis?.recovery_data_availability?.night_wear_missing"
        style="margin: 0 0 18rpx 0; padding: 14rpx 20rpx; border-radius: 14rpx; background: rgba(245, 158, 11, 0.14); border: 1rpx solid rgba(245, 158, 11, 0.45); display: flex; align-items: center; justify-content: space-between;"
        @click.stop="explainTerm('watch_wear')"
      >
        <text style="font-size: 23rpx; font-weight: 700; color: #b45309;">
          ⚠️ {{ recoveryDataAvailability?.recovery_status_label || analysis?.recovery_data_availability?.recovery_status_label || '夜间未佩戴 · 恢复数据缺失' }}
        </text>
        <text style="font-size: 21rpx; font-weight: 700; color: #b45309; flex-shrink: 0; margin-left: 12rpx;">ⓘ 详情</text>
      </view>
      <!-- Top Bar -->
      <view class="plan-top-bar">
        <view class="plan-title-box">
          <view style="display: flex; align-items: center; gap: 8rpx;">
            <text class="plan-main-title">{{ plan ? plan.title : '周期训练课表' }}</text>
            <text class="term-info" @click.stop="explainTerm('canova_model')">ⓘ</text>
          </view>
          <view v-if="plan" class="plan-status-pills-row">
            <text class="plan-status-pill">{{ plan.weeks_count }}周周期</text>
            <text
              v-if="plan.review_status === 'published' || plan.reviewed_by_name || (plan.schedule_data && plan.schedule_data.coach_review)"
              class="plan-coach-verified-pill"
            >
              🧢 {{ plan.reviewed_by_name || (plan.schedule_data && plan.schedule_data.coach_review && plan.schedule_data.coach_review.reviewed_by_name) || '教练' }}已审
            </text>
          </view>
        </view>
        <view style="display: flex; align-items: center; gap: 10rpx; flex-shrink: 0;">
          <button
            v-if="planBackups.length > 0 && !isPreviewPlan"
            class="plan-config-toggle-btn"
            :loading="rollingBackPlan"
            @click="handleRollbackUserPlan"
          >
            <text class="btn-text">↩ 回退</text>
          </button>
          <button
            class="plan-config-toggle-btn"
            @click="showCoachPersonalReport = true"
          >
            <text class="btn-text">📊 周报/月报</text>
          </button>
          <button class="plan-config-toggle-btn" @click="showPlanConfig = !showPlanConfig">
            <text class="btn-text">{{ showPlanConfig ? '收起' : (plan ? '⚙️ 定制' : '✨ 定制') }}</text>
          </button>
        </view>
      </view>

      <!-- 🏆 Target Race Completed Switch Banner -->
      <view v-if="plan && isTargetRaceCompleted && recommendedRace" class="plan-switch-banner">
        <view class="banner-top-row">
          <text class="banner-badge">🏆 原目标已完赛</text>
          <text class="banner-sub">建议切换至核心 A 标</text>
        </view>
        <text class="banner-desc">
          「{{ plan.target_race_name }}」已完赛，建议切换下一核心目标「{{ recommendedRace.name }}」（{{ recommendedRace.race_date }}）。
        </text>
        <view style="display:flex; gap:14rpx; margin-top:8rpx;">
          <button
            class="banner-switch-btn"
            style="flex:0.85; background:var(--rgm-brand-tint, rgba(251,191,36,0.18)); border:1rpx solid var(--rgm-brand-line, #fbbf24); color:var(--rgm-brand-text, #fbbf24);"
            @click="openCompletedTargetRaceShareCard"
          >
            📸 生成完赛分享卡
          </button>
          <button class="banner-switch-btn" style="flex:1.15;" @click="handleApplyRecommendedRace">
            切换为「{{ recommendedRace.name }}」 ➔
          </button>
        </view>
      </view>

      <!-- Plan Setup Panel -->
      <view v-if="showPlanConfig || !plan" class="plan-setup-card">
        <view class="card-title-row">
          <text class="section-icon">🎯</text>
          <text class="card-title">计划参数</text>
          <text class="term-info" @click.stop="explainTerm('canova_model')">ⓘ</text>
        </view>

        <!-- Goal Type Toggle -->
        <view class="goal-type-toggle-row">
          <view
            class="goal-type-btn"
            :class="{ active: planGoalType === 'race_prep' }"
            @click="planGoalType = 'race_prep'"
          >
            <text class="goal-btn-title">🏅 赛事备战</text>
          </view>
          <view
            class="goal-type-btn"
            :class="{ active: planGoalType === 'fitness_maintenance' }"
            @click="planGoalType = 'fitness_maintenance'"
          >
            <text class="goal-btn-title">🏔️ 日常进阶</text>
          </view>
        </view>

        <!-- If Race: Quick Select & Inputs -->
        <view v-if="planGoalType === 'race_prep'" class="race-setup-inputs">
          <view v-if="userRaces.length" class="registered-races-row">
            <text class="registered-label">🚩 已登记赛事：</text>
            <view class="registered-chips">
              <view
                v-for="r in userRaces"
                :key="r.id || r.name"
                class="reg-chip"
                :class="{
                  active: planRaceName === r.name,
                  'is-done': r.status === 'completed' || r.is_completed,
                  'is-a': (r.priority == 1 || r.priority === 'A') && r.status !== 'completed'
                }"
                @click="handleSelectPlanRace(r)"
              >
                <text class="reg-chip-tier tier-done" v-if="r.status === 'completed' || r.is_completed">🏁 已完赛</text>
                <text class="reg-chip-tier tier-a" v-else-if="r.priority == 1 || r.priority === 'A'">⭐ A标核心</text>
                <text class="reg-chip-tier tier-b" v-else-if="r.priority == 2 || r.priority === 'B'">⚡ B标代练</text>
                <text class="reg-chip-name">{{ r.name }}</text>
              </view>
            </view>
          </view>

          <view class="inputs-row">
            <view class="input-col flex-2">
              <text class="input-label">目标赛事</text>
              <input v-model="planRaceName" placeholder="如: 上海马拉松" class="setup-input" />
            </view>
            <view class="input-col flex-1">
              <text class="input-label">目标成绩</text>
              <input v-model="planTargetTime" placeholder="3:09:30" class="setup-input" />
            </view>
          </view>
        </view>

        <!-- If Non-Race: Focus Options -->
        <view v-else class="maintenance-options-row">
          <text class="input-label">专项强化方向</text>
          <view class="maint-chips-grid">
            <view
              v-for="m in maintenanceList"
              :key="m.id"
              class="maint-chip"
              :class="{ active: planMaintenanceFocus === m.id }"
              @click="planMaintenanceFocus = m.id"
            >
              <text class="maint-name">{{ m.name }}</text>
            </view>
          </view>
        </view>

        <!-- Weeks & Days Wheel Picker + Stepper -->
        <view class="picker-row">
          <view class="picker-col">
            <text class="input-label">周期总周数</text>
            <view class="wheel-stepper-box">
              <view class="ws-step-btn" @click.stop="stepPlanWeeks(-1)">−</view>
              <picker
                mode="selector"
                class="ws-picker-mid"
                :range="planWeekOptionLabels"
                :value="Math.max(0, planWeekOptions.indexOf(planWeeksCount))"
                @change="(e: any) => planWeeksCount = planWeekOptions[Number(e.detail.value)] || 8"
              >
                <view class="ws-picker-val-wrap">
                  <text class="ws-picker-val">{{ planWeeksCount }} 周</text>
                  <text class="ws-picker-caret">▾</text>
                </view>
              </picker>
              <view class="ws-step-btn" @click.stop="stepPlanWeeks(1)">+</view>
            </view>
          </view>

          <view class="picker-col">
            <text class="input-label">每周跑步天数</text>
            <view class="wheel-stepper-box">
              <view class="ws-step-btn" @click.stop="stepPlanDays(-1)">−</view>
              <picker
                mode="selector"
                class="ws-picker-mid"
                :range="planDayOptionLabels"
                :value="Math.max(0, planDayOptions.indexOf(planDaysPerWeek))"
                @change="(e: any) => planDaysPerWeek = planDayOptions[Number(e.detail.value)] || 4"
              >
                <view class="ws-picker-val-wrap">
                  <text class="ws-picker-val">{{ planDaysPerWeek }} 天/周</text>
                  <text class="ws-picker-caret">▾</text>
                </view>
              </picker>
              <view class="ws-step-btn" @click.stop="stepPlanDays(1)">+</view>
            </view>
          </view>
        </view>

        <!-- Goal Anchor Hint in Miniapp (Clickable to open unified GoalSheetModal) -->
        <view class="goal-anchor-box" @click="openCoachGoalSheet('week')">
          <text class="anchor-icon">🎯</text>
          <text class="anchor-text">周目标基准：{{ userGoal?.next_weekly_target || userGoal?.weekly_target || 50 }} km/周</text>
          <text style="margin-left: auto; font-size: 22rpx; font-weight: 700; color: #fc4c02;">调整 ›</text>
        </view>

        <button class="primary-btn" :loading="generatingPlan" @click="handleGeneratePlan">
          <text class="btn-text">{{ generatingPlan ? '推演中...' : '✨ 生成课表预览' }}</text>
        </button>
      </view>

      <!-- Active Plan Details -->
      <view v-if="plan && plan.schedule_data" class="plan-body">
        <!-- Pending Confirmation Banner for Newly Generated Preview Plan -->
        <view
          v-if="isPreviewPlan"
          style="margin-bottom:24rpx;padding:20rpx 22rpx;border-radius:22rpx;background:var(--rgm-brand-tint, rgba(245,158,11,0.18));border:2rpx solid var(--rgm-brand-line, rgba(245,158,11,0.5));"
        >
          <view style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8rpx;">
            <text style="font-size:25rpx;font-weight:800;color:var(--rgm-brand-text, #fbbf24);">🛡️ 预览待确认（未写入）</text>
            <text style="font-size:20rpx;font-weight:700;padding:4rpx 14rpx;border-radius:999rpx;background:var(--rgm-tint-2, rgba(245,158,11,0.25));color:var(--rgm-text, #fde68a);">预览</text>
          </view>
          <text style="font-size:22rpx;color:var(--rgm-text-2, #fde68a);line-height:1.45;display:block;margin-bottom:14rpx;">
            请审阅下方各周安排，点击「确认启用」后正式覆盖原计划。
          </text>
          <view style="display:flex;gap:16rpx;">
            <button
              style="flex:1;margin:0;height:68rpx;line-height:68rpx;border-radius:16rpx;font-size:24rpx;font-weight:700;background:var(--rgm-card, rgba(255,255,255,0.12));color:var(--rgm-text, #e4e4e7);border:1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.2));"
              @click="handleDiscardGeneratedPlan"
            >
              ✕ 放弃
            </button>
            <button
              style="flex:1.6;margin:0;height:68rpx;line-height:68rpx;border-radius:16rpx;font-size:24rpx;font-weight:800;background:linear-gradient(135deg, #10b981, #059669);color:#ffffff;"
              :loading="confirmingPlan"
              @click="handleConfirmGeneratedPlan"
            >
              ✅ 确认启用
            </button>
          </view>
        </view>
        <!-- Baseline Snapshot Card -->
        <view v-if="plan.schedule_data.current_fitness_snapshot" class="snapshot-card">
          <view class="snap-item">
            <text class="snap-label">跑者组别</text>
            <text class="snap-val">{{ (plan.schedule_data.current_fitness_snapshot.age && plan.schedule_data.current_fitness_snapshot.age >= 50) ? '大师组' : plan.schedule_data.current_fitness_snapshot.age ? `${plan.schedule_data.current_fitness_snapshot.age} 岁` : '—' }}</text>
            <text class="snap-sub">{{ (plan.schedule_data.current_fitness_snapshot.age && plan.schedule_data.current_fitness_snapshot.age >= 50) ? '72-96h 恢复律' : '正常恢复' }}</text>
          </view>
          <view class="snap-item">
            <text class="snap-label">VO2Max</text>
            <text class="snap-val text-purple">{{ plan.schedule_data.current_fitness_snapshot.vo2max || '—' }}</text>
            <text class="snap-sub">{{ plan.schedule_data.current_fitness_snapshot.vo2max_source === 'watch' ? '手表实测' : '生理基准' }}</text>
          </view>
          <view class="snap-item">
            <text class="snap-label">体能 / 状态 <text class="term-info" @click.stop="explainTerm('fitness')">ⓘ</text></text>
            <text class="snap-val text-cyan">{{ plan.schedule_data.current_fitness_snapshot.ctl || 0 }} / {{ plan.schedule_data.current_fitness_snapshot.tsb || 0 }}</text>
          </view>
          <view class="snap-item">
            <text class="snap-label">18m最长跑</text>
            <text class="snap-val text-amber">{{ plan.schedule_data.current_fitness_snapshot.max_long_run_18m_km || '—' }} km</text>
          </view>
        </view>

        <!-- Coach Review Note Box -->
        <view
          v-if="plan.coach_review_note || (plan.schedule_data && plan.schedule_data.coach_review && plan.schedule_data.coach_review.coach_review_note)"
          class="coach-review-note-box"
        >
          <text class="crn-icon">👨‍🏫</text>
          <view class="crn-content">
            <text class="crn-title">教练【{{ plan.reviewed_by_name || (plan.schedule_data && plan.schedule_data.coach_review && plan.schedule_data.coach_review.reviewed_by_name) || '跑团教练' }}】执行叮嘱：</text>
            <text class="crn-text">{{ plan.coach_review_note || (plan.schedule_data && plan.schedule_data.coach_review && plan.schedule_data.coach_review.coach_review_note) }}</text>
          </view>
        </view>

        <!-- Canova Overview Quote & Macro Roadmap -->
        <view v-if="plan.overview_summary || (plan.schedule_data && plan.schedule_data.macro_roadmap)" class="overview-box">
          <view v-if="plan.overview_summary" style="display:flex;align-items:flex-start;gap:12rpx;">
            <text class="overview-icon">🎯</text>
            <text class="overview-text">{{ plan.overview_summary }}</text>
          </view>
          <view v-if="plan.schedule_data && plan.schedule_data.macro_roadmap" style="margin-top:14rpx;padding:16rpx;background:var(--rgm-card-2, rgba(0,0,0,0.28));border-radius:16rpx;border:1rpx solid var(--rgm-line-solid, rgba(175,82,222,0.3));">
            <text style="font-size:22rpx;font-weight:800;color:var(--rgm-brand-text, #d8b4fe);display:block;margin-bottom:6rpx;">🗺️ 阶段宏观周期大纲 (教练规划)：</text>
            <text style="font-size:22rpx;color:var(--rgm-text-2, #e4e4e7);line-height:1.5;white-space:pre-wrap;">{{ plan.schedule_data.macro_roadmap }}</text>
          </view>
        </view>

        <!-- Horizontal Week Scroll -->
        <scroll-view
          scroll-x
          class="week-scroll-view"
          show-scrollbar="false"
          :scroll-into-view="scrollIntoWeek"
          :scroll-with-animation="true"
        >
          <view class="week-chips-row">
            <view
              v-for="w in (plan.schedule_data.weeks || [])"
              :key="w.week_index"
              :id="'week-chip-' + w.week_index"
              class="week-chip"
              :class="{
                active: selectedWeekIdx === w.week_index,
                'is-current-week': currentWeekIndex === w.week_index
              }"
              @click="selectWeek(w.week_index)"
            >
              <view class="chip-title-row">
                <text class="week-chip-title">第 {{ w.week_index }} 周</text>
                <text v-if="currentWeekIndex === w.week_index" class="current-week-tag">本周</text>
              </view>
              <text class="week-chip-sub">{{ w.weekly_mileage_km || 0 }}km · {{ (w.phase || '训练').split(' ')[0] }}</text>
            </view>
          </view>
        </scroll-view>

        <!-- Active Week Card Header -->
        <view v-if="activeMiniWeek" class="active-week-header">
          <view class="active-week-left">
            <view class="active-week-title-row">
              <text class="active-week-title">{{ activeMiniWeek.week_title || `第 ${activeMiniWeek.week_index} 周` }}</text>
              <text class="phase-tag">{{ activeMiniWeek.phase }}</text>
            </view>
            <text class="focus-text">重点：{{ activeMiniWeek.key_focus }}</text>
            <text class="week-summary-banner-line">
              📊 {{ activeMiniWeek.summary_banner_text || `周跑量：${activeMiniWeek.weekly_mileage_km || 0}公里。执行：${activeMiniWeek.actual_mileage_km || 0}公里，完成度${activeMiniWeek.compliance_rate || 0}%；力量：${activeMiniWeek.strength_sessions_done || 0}次。` }}
            </text>
          </view>
          <view class="active-week-right">
            <text class="mileage-val">{{ activeMiniWeek.weekly_mileage_km || 0 }} km</text>
            <text class="mileage-label">周跑量</text>
          </view>
        </view>

        <!-- Week Alignment & Sync Bar in Miniapp -->
        <view v-if="activeMiniWeek" class="week-alignment-bar">
          <view class="align-pill" :class="getAlignmentPillClass(activeMiniWeek)">
            <text class="align-icon">{{ getAlignmentIcon(activeMiniWeek) }}</text>
            <text class="align-status-title">{{ getAlignmentLabel(activeMiniWeek) }}</text>
            <text class="align-status-detail">课表 {{ activeMiniWeek.weekly_mileage_km || 0 }}k / 目标 {{ userGoal?.weekly_target || 50 }}k ({{ getAlignmentRatio(activeMiniWeek) }}%)</text>
          </view>
          <button class="sync-goal-mini-btn" :loading="syncingGoal" @click="handleSyncToGoals">
            <text class="sync-mini-btn-text">同步</text>
          </button>
        </view>

        <!-- 7 Daily Workout Cards -->
        <view v-if="activeMiniWeek" class="daily-cards-list">
          <view
            v-for="(day, dIdx) in (activeMiniWeek.days || [])"
            :key="dIdx"
            class="daily-card"
            :class="[getWorkoutBorderClass(day.workout_type), { 'is-completed': day.completed, 'is-missed': isDayMissed(day) }]"
          >
            <view class="daily-card-top">
              <view class="day-date-box">
                <text class="day-name">{{ day.day_of_week }}</text>
                <text class="day-date">{{ day.date ? day.date.substring(5) : '' }}</text>
                <text v-if="day.swapped_from" class="swap-pill">🔁 与{{ day.swapped_from }}对换</text>
              </view>
              <view class="badge-group">
                <text v-if="day.feeling_tag" class="rpe-pill" style="background:rgba(16,185,129,0.16);color:#10b981;border:1rpx solid rgba(16,185,129,0.35);">{{ day.feeling_tag }}</text>
                <text v-if="day.rpe != null" class="rpe-pill">RPE {{ day.rpe }}</text>
                <text
                  v-if="day.recovery_pct != null"
                  class="rec-pill"
                  :class="day.recovery_pct >= 67 ? 'rec-good' : day.recovery_pct >= 34 ? 'rec-mid' : 'rec-low'"
                >恢复 {{ day.recovery_pct }}%</text>
                <text v-if="isDayMissed(day)" class="missed-badge">✗ 缺跑</text>
                <text v-if="day.completed && day.actual_distance_km" class="actual-km-badge">实跑 {{ day.actual_distance_km }}k</text>
                <text class="type-badge" :class="getWorkoutBadgeClass(day.workout_type)">
                  {{ getWorkoutTypeLabel(day.workout_type) }}
                </text>
              </view>
            </view>

            <view class="daily-card-body">
              <text class="workout-title">{{ day.title }}</text>
              <view v-if="day.workout_type !== 'rest'" class="dist-row">
                <text class="dist-val">{{ day.distance_km || 0 }}</text>
                <text class="dist-unit">km</text>
              </view>

              <!-- Pace & Heart Rate & Biometrics -->
              <view class="metrics-row" style="flex-wrap:wrap;">
                <text v-if="day.workout_type !== 'rest' && day.target_pace && day.target_pace !== '—'" class="metric-pill">⏱️ {{ day.target_pace }}</text>
                <text v-if="day.workout_type !== 'rest' && day.target_hr_zone && day.target_hr_zone !== '—'" class="metric-pill hr-pill">❤️ {{ day.target_hr_zone }}</text>
                <text v-if="day.biometrics_text" class="metric-pill" :class="{ 'bio-warn-pill': day.low_hrv_alert }">💓 指标 {{ day.biometrics_text }}</text>
                <text v-if="day.actual_execution_text" class="metric-pill exec-pill">🏃 执行: {{ day.actual_execution_text }}</text>
              </view>

              <text class="workout-desc">{{ day.description }}</text>

              <!-- Athlete Self-Feel Notes & Photos -->
              <view
                v-if="day.feeling_tag || day.athlete_notes || (day.workout_photos && day.workout_photos.length)"
                class="athlete-notes-box"
              >
                <view style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4rpx;">
                  <text class="athlete-notes-title">💬 训练感受与备注：</text>
                  <text v-if="day.feeling_tag" style="font-size:20rpx;font-weight:700;color:#10b981;">{{ day.feeling_tag }}</text>
                </view>
                <text v-if="day.athlete_notes" class="athlete-notes-content">{{ day.athlete_notes }}</text>
                <view
                  v-if="day.workout_photos && day.workout_photos.length"
                  style="display:flex;flex-wrap:wrap;gap:12rpx;margin-top:10rpx;"
                >
                  <image
                    v-for="(pUrl, pIdx) in day.workout_photos"
                    :key="pIdx"
                    :src="pUrl"
                    mode="aspectFill"
                    style="width:112rpx;height:112rpx;border-radius:14rpx;border:1rpx solid rgba(255,255,255,0.15);"
                    @click.stop="previewCoachWorkoutPhotos(day.workout_photos, Number(pIdx))"
                  />
                </view>
              </view>

              <!-- Coach Notes -->
              <view v-if="day.coach_notes" class="coach-notes-box">
                <text class="coach-notes-title">👨‍🏫 跑团教练批注：</text>
                <text class="coach-notes-content">{{ day.coach_notes }}</text>
              </view>
            </view>

            <!-- Card Bottom Actions -->
            <view class="daily-card-actions">
              <button
                class="action-complete-btn"
                :class="{ completed: day.completed, missed: isDayMissed(day) }"
                @click="handleToggleComplete(activeMiniWeek.week_index, dIdx, day)"
              >
                <text class="btn-text">
                  {{ day.completed ? (day.actual_distance_km ? `✅ 已打卡 ${day.actual_distance_km}k` : '✅ 已完成') : (isDayMissed(day) ? '❌ 补卡' : '打卡') }}
                </text>
              </button>
              <button
                class="action-edit-btn"
                @click="openEditWorkoutModal(activeMiniWeek.week_index, dIdx, day)"
              >
                <text class="btn-text">{{ day.completed ? '📝 感受/备注/照片' : '📝 记录/调休' }}</text>
              </button>
            </view>
          </view>
        </view>

        <!-- ── Weekly Summary & Injury Self-Report Box (默认折叠，教练评语常驻) ── -->
        <view v-if="activeMiniWeek" style="margin-top:20rpx;padding:24rpx;border-radius:24rpx;background:var(--rgm-card, rgba(255,255,255,0.03));border:1rpx solid var(--rgm-line, rgba(255,255,255,0.1));">
          <view
            style="display:flex;align-items:center;justify-content:space-between;"
            @click="showWeekSummaryForm = !showWeekSummaryForm"
          >
            <view style="display:flex;flex-direction:column;gap:4rpx;">
              <text style="font-size:26rpx;font-weight:800;color:var(--rgm-text, #ffffff);">📝 第 {{ activeMiniWeek.week_index }} 周反馈</text>
              <text v-if="weekInjuryNote || weekAthleteSummary || weekTravelNote" style="font-size:20rpx;color:var(--rgm-text-2, #a1a1aa);">
                已填反馈
              </text>
            </view>
            <text style="font-size:22rpx;font-weight:700;color:var(--rgm-brand-text, #f97316);background:var(--rgm-brand-tint, rgba(249,115,22,0.14));padding:8rpx 20rpx;border-radius:999rpx;white-space:nowrap;flex-shrink:0;">
              {{ showWeekSummaryForm ? '收起 ▴' : '填写 ▾' }}
            </text>
          </view>

          <view v-if="activeMiniWeek.coach_weekly_diagnosis" style="margin-top:16rpx;padding:16rpx;border-radius:16rpx;background:rgba(168,85,247,0.12);border:1rpx solid rgba(168,85,247,0.3);">
            <text style="font-size:21rpx;font-weight:800;color:var(--rgm-purple, #d8b4fe);display:block;margin-bottom:4rpx;">🧢 教练复盘：</text>
            <text style="font-size:21rpx;color:var(--rgm-text, #f3e8ff);line-height:1.4;">{{ activeMiniWeek.coach_weekly_diagnosis }}</text>
          </view>

          <view v-if="showWeekSummaryForm" style="margin-top:18rpx;padding-top:18rpx;border-top:1rpx solid var(--rgm-line, rgba(255,255,255,0.08));">
            <view class="modal-input-group" style="margin-bottom:14rpx;">
              <text class="modal-label" style="color:var(--rgm-red, #fda4af);">🚨 伤痛上报 (无则填无)</text>
              <input v-model="weekInjuryNote" class="modal-input" placeholder="如：无，或右脚跟腱跑后轻微酸胀" />
            </view>

            <view class="modal-input-group" style="margin-bottom:14rpx;">
              <text class="modal-label" style="color:var(--rgm-amber, #fcd34d);">💬 本周小结</text>
              <input v-model="weekAthleteSummary" class="modal-input" placeholder="如：周二间歇完成顺利，周末长距离后程略掉速" />
            </view>

            <view class="modal-input-group" style="margin-bottom:16rpx;">
              <text class="modal-label">✈️ 出差/请假/比赛报备</text>
              <input v-model="weekTravelNote" class="modal-input" placeholder="如：下周三至周五出差，仅能安排晨跑" />
            </view>

            <button class="primary-btn" :loading="savingWeekSummary" @click="handleSaveRunnerWeekSummary">
              <text class="btn-text">{{ savingWeekSummary ? '提交中...' : '💾 提交周反馈' }}</text>
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── ANALYSIS TAB CONTENT ── -->
    <view v-else class="analysis-tab-section">
      <!-- ── ATHLETE PROFILE & TSB FORM CARD ── -->
      <view class="profile-card">
      <view class="profile-top">
        <view class="profile-name-box">
          <text class="profile-name">{{ athleteInfo.name || "跑者" }}</text>
          <text class="profile-meta">
            {{ athleteInfo.gender === 'female' ? '♀ 女' : '♂ 男' }} · 
            {{ (athleteInfo.age && athleteInfo.age >= 50) ? '大师组' : athleteInfo.age ? `${athleteInfo.age} 岁` : '未录入年龄' }} · 
            跑龄 {{ athleteInfo.years_running || 2 }} 年
          </text>
        </view>
        <view class="tsb-badge" :class="tsbClass">
          <text class="tsb-badge-text">{{ tsbMetrics.status || "平衡稳健" }}</text>
        </view>
      </view>

      <view class="tsb-grid">
        <view class="tsb-item">
          <text class="tsb-label">体能 CTL</text>
          <text class="tsb-val text-cyan">{{ tsbMetrics.ctl || 0 }}</text>
        </view>
        <view class="tsb-item">
          <text class="tsb-label">疲劳 ATL</text>
          <text class="tsb-val text-amber">{{ tsbMetrics.atl || 0 }}</text>
        </view>
        <view class="tsb-item">
          <text class="tsb-label">状态 TSB <text class="term-info" @click.stop="explainTerm('tsb')">ⓘ</text></text>
          <text class="tsb-val" :class="tsbMetrics.tsb >= 0 ? 'text-green' : 'text-purple'">
            {{ tsbMetrics.tsb > 0 ? `+${tsbMetrics.tsb}` : (tsbMetrics.tsb || 0) }}
          </text>
        </view>
      </view>

      <view v-if="tsbMetrics.risk_warning" class="risk-box">
        <text class="risk-icon">⚠️</text>
        <text class="risk-text">{{ tsbMetrics.risk_warning }}</text>
      </view>
      <view
        v-if="recoveryDataAvailability?.night_wear_missing || analysis?.recovery_data_availability?.night_wear_missing"
        style="margin-top: 14rpx; padding: 12rpx 18rpx; border-radius: 14rpx; background: rgba(245, 158, 11, 0.14); border: 1rpx solid rgba(245, 158, 11, 0.45); display: flex; align-items: center; justify-content: space-between;"
        @click.stop="explainTerm('watch_wear')"
      >
        <text style="font-size: 22rpx; font-weight: 700; color: #b45309;">
          ⚠️ 夜间未佩戴 · 恢复数据缺失
        </text>
        <text style="font-size: 21rpx; font-weight: 700; color: #b45309; flex-shrink: 0; margin-left: 12rpx;">ⓘ 详情</text>
      </view>
    </view>

    <!-- ── TARGET RACE CUSTOMIZATION CARD (紧凑条 + 按需展开，消除与课表页重复表单) ── -->
    <view class="race-setup-card">
      <view
        style="display:flex;align-items:center;justify-content:space-between;"
        @click="showAnalysisRaceSetup = !showAnalysisRaceSetup"
      >
        <view style="display:flex;flex-direction:column;gap:4rpx;">
          <view class="card-title-row" style="margin-bottom:0;">
            <text class="section-icon">🎯</text>
            <text class="card-title">备赛：{{ targetRace || '未设定' }}</text>
          </view>
          <text style="font-size:22rpx;color:#a1a1aa;">
            目标 {{ targetTime || '—' }} · {{ raceType === 'half' ? '半马' : raceType === 'trail' ? '越野' : raceType === '10k' ? '10K' : '全马' }}
          </text>
        </view>
        <text style="font-size:22rpx;font-weight:700;color:#f97316;background:rgba(249,115,22,0.14);padding:8rpx 20rpx;border-radius:999rpx;">
          {{ showAnalysisRaceSetup ? '收起 ▴' : '切换 ▾' }}
        </text>
      </view>

      <view v-if="showAnalysisRaceSetup" style="margin-top:20rpx;padding-top:20rpx;border-top:1rpx solid rgba(255,255,255,0.08);">
        <!-- Registered User Races Quick Selector -->
        <view v-if="userRaces.length" class="registered-races-row">
          <text class="registered-label">🚩 已登记赛事：</text>
          <view class="registered-chips">
            <view
              v-for="r in userRaces"
              :key="r.id || r.name"
              class="reg-chip"
              :class="{ active: targetRace === r.name || targetRace.includes(r.name) || r.name.includes(targetRace) }"
              @click="handleSelectRegisteredRace(r)"
            >
              <text class="reg-chip-tier" :class="`tier-${r.priority == 1 || r.priority === 'A' ? 'a' : r.priority == 2 || r.priority === 'B' ? 'b' : 'c'}`">
                {{ r.priority == 1 || r.priority === 'A' ? 'A标' : r.priority == 2 || r.priority === 'B' ? 'B标' : 'C标' }}
              </text>
              <text class="reg-chip-name">{{ r.name }}</text>
              <text v-if="r.days_left !== undefined" class="reg-chip-days">{{ r.days_left }}天</text>
            </view>
          </view>
        </view>

        <view class="inputs-row">
          <view class="input-col flex-2">
            <text class="input-label">目标赛事</text>
            <input
              v-model="targetRace"
              placeholder="如: 上海马拉松 / 武功山 50K"
              class="setup-input"
              @input="onRaceNameInput"
            />
          </view>
          <view class="input-col flex-1">
            <text class="input-label">目标时间</text>
            <input
              v-model="targetTime"
              placeholder="3:15:00"
              class="setup-input"
            />
          </view>
        </view>

        <!-- Race Category Pills -->
        <view class="race-type-pills-row">
          <text class="input-label">专项分类：</text>
          <view class="type-pills">
            <view
              class="type-pill"
              :class="{ active: raceType === 'marathon' }"
              @click="setCategory('marathon')"
            >
              <text class="pill-text">🏅 全马</text>
            </view>
            <view
              class="type-pill"
              :class="{ active: raceType === 'half' }"
              @click="setCategory('half')"
            >
              <text class="pill-text">⚡ 半马</text>
            </view>
            <view
              class="type-pill"
              :class="{ active: raceType === 'trail' }"
              @click="setCategory('trail')"
            >
              <text class="pill-text">🏔️ 越野</text>
            </view>
            <view
              class="type-pill"
              :class="{ active: raceType === '10k' || raceType === '5k' }"
              @click="setCategory('10k')"
            >
              <text class="pill-text">🏃 10K</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- Main Content -->
    <view v-if="analysis" class="content-box">
      <!-- ── CARD 1: 当前阶段与核心评价 ── -->
      <view class="hero-card">
        <view class="phase-badge" @click.stop="explainTerm('canova_model')">
          <text class="sparkle">✨</text>
          <text class="phase-text">阶段：{{ analysis.periodization_phase || "专项准备期" }} ⓘ</text>
        </view>

        <text class="summary-title">{{ analysis.summary }}</text>
        <text class="fitness-detail">{{ analysis.fitness_status }}</text>
      </view>

      <!-- ── CARD 1.2: 多赛事宏观统筹与战术推演 (Multi-Race Strategy) ── -->
      <view v-if="analysis.multi_race_strategy" class="section-card multi-race-card">
        <view class="multi-race-header">
          <view class="multi-race-header-titles">
            <view class="card-title-row">
              <text class="section-icon">📅</text>
              <text class="card-title">多赛事统筹</text>
            </view>
          </view>
          <view class="total-races-badge">
            <text class="sparkle-icon">✨</text>
            <text class="total-races-text">{{ (analysis.multi_race_strategy.race_timeline_advice || []).length }} 场赛事</text>
          </view>
        </view>

        <!-- Macrocycle Overview -->
        <view class="macrocycle-box">
          <view class="macrocycle-header">
            <text class="macrocycle-icon">🏆</text>
            <text class="macrocycle-label">赛季宏观周期统筹：</text>
          </view>
          <text class="macrocycle-text">{{ analysis.multi_race_strategy.macro_cycle_overview }}</text>
        </view>

        <!-- Timeline Section -->
        <view class="timeline-section">
          <view class="timeline-section-header">
            <text class="timeline-section-title">赛事日历与专项执行规程</text>
          </view>

          <!-- Race Timeline List -->
          <view class="race-timeline-list">
            <view
              v-for="(r, idx) in (analysis.multi_race_strategy.race_timeline_advice || [])"
              :key="r.id || idx"
              class="race-item"
              :class="`tier-${(r.tier || 'B').toLowerCase()}`"
            >
              <view class="race-item-header">
                <view class="race-title-row">
                  <view class="race-title-left">
                    <view class="race-tier-badge" :class="`badge-${(r.tier || 'B').toLowerCase()}`">
                      <text class="badge-text">{{ r.tactical_role || `${r.tier || 'B'} 标` }}</text>
                    </view>
                    <text class="race-item-name">{{ r.race_name }}</text>
                  </view>
                  <text v-if="r.days_left !== undefined" class="race-days-countdown">
                    倒计时 <text class="days-num">{{ r.days_left }}</text> 天
                  </text>
                </view>

                <!-- Interactive A/B/C Priority Switcher -->
                <view class="priority-switch-row">
                  <view class="priority-left-group">
                    <text class="switch-tip-lbl">调整级别:</text>
                    <view class="priority-btns">
                      <button
                        class="p-btn p-btn-a"
                        :class="{ active: (r.tier || '').toUpperCase() === 'A' }"
                        :disabled="updatingPriority === (r.id || r.race_name)"
                        @click.stop="handleUpdatePriority(r.id || r.race_name, 'A')"
                      >A 标 (核心)</button>
                      <button
                        class="p-btn p-btn-b"
                        :class="{ active: (r.tier || '').toUpperCase() === 'B' }"
                        :disabled="updatingPriority === (r.id || r.race_name)"
                        @click.stop="handleUpdatePriority(r.id || r.race_name, 'B')"
                      >B 标 (代练)</button>
                      <button
                        class="p-btn p-btn-c"
                        :class="{ active: (r.tier || '').toUpperCase() === 'C' }"
                        :disabled="updatingPriority === (r.id || r.race_name)"
                        @click.stop="handleUpdatePriority(r.id || r.race_name, 'C')"
                      >C 标 (拉练)</button>
                    </view>
                  </view>

                  <button
                    class="set-target-btn"
                    :class="{ 'is-active-target': isCurrentTarget(r) }"
                    @click.stop="handleSelectTargetRace(r)"
                  >
                    {{ isCurrentTarget(r) ? "🎯 当前主备赛" : "设为主目标" }}
                  </button>
                </view>
              </view>

              <!-- Two Execution Boxes: Pacing Strategy & Taper/Recovery Rules -->
              <view class="race-execution-boxes">
                <view class="exec-box">
                  <view class="exec-box-title">
                    <text class="exec-icon">🎯</text>
                    <text class="exec-label">目标配速与心率战术</text>
                  </view>
                  <text class="exec-desc">{{ r.pacing_strategy }}</text>
                </view>

                <view class="exec-box">
                  <view class="exec-box-title">
                    <text class="exec-icon">⏳</text>
                    <text class="exec-label">减量规程与超量恢复</text>
                  </view>
                  <text class="exec-desc">{{ r.taper_recovery_rule }}</text>
                </view>
              </view>
            </view>
          </view>
        </view>

        <!-- Conflict & Strategic Diagnostics Banner -->
        <view v-if="analysis.multi_race_strategy.conflict_resolution" class="conflict-box">
          <view class="conflict-title-row">
            <text class="conflict-icon">⚠️</text>
            <text class="conflict-title">战术规避与周期协同要点：</text>
          </view>
          <text class="conflict-desc">{{ analysis.multi_race_strategy.conflict_resolution }}</text>
        </view>
      </view>

      <!-- ── CARD 1.5: CANOVA 比赛专项刺激区间 ── -->
      <view v-if="analysis.race_zones" class="section-card">
        <view class="card-title-row">
          <text class="section-icon">⚡</text>
          <text class="card-title">专项配速区间 ({{ targetRace }})</text>
        </view>

        <view class="zones-list">
          <view
            v-for="(z, key) in analysis.race_zones"
            :key="key"
            class="zone-item"
          >
            <view class="zone-header">
              <text class="zone-name">{{ z.name }}</text>
              <text class="zone-range">{{ z.range }}</text>
            </view>
          </view>
        </view>
      </view>

      <!-- ── CARD 2: 本周核心关键课 ── -->
      <view class="section-card workout-card">
        <view class="card-title-row">
          <text class="section-icon">🎯</text>
          <text class="card-title">本周关键课</text>
        </view>
        <view class="workout-box">
          <text class="workout-text">{{ formatWorkout(analysis.focus_workout_of_the_week) }}</text>
        </view>
      </view>

      <!-- ── CARD 3: 生理恢复与超量恢复指导 ── -->
      <view class="section-card recovery-card">
        <view class="card-title-row">
          <text class="section-icon">🌿</text>
          <text class="card-title">恢复指导</text>
        </view>
        <view class="recovery-box">
          <text class="recovery-text">{{ formatAdvice(analysis.recovery_advice) }}</text>
        </view>
      </view>

      <!-- ── CARD 4: Canova 专项训练执行要点 ── -->
      <view class="section-card">
        <view class="card-title-row">
          <text class="section-icon">📋</text>
          <text class="card-title">执行要点</text>
        </view>

        <view class="suggestions-list">
          <view
            v-for="(item, idx) in (analysis.key_suggestions || [])"
            :key="idx"
            class="sugg-item"
          >
            <text class="sugg-badge">重点 0{{ idx + 1 }}</text>
            <text class="sugg-text">{{ item }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Empty / Fallback State -->
    <view v-else class="empty-card">
      <text class="empty-icon">⚡</text>
      <text class="empty-title">Canova教练就绪</text>
      <text class="empty-desc">配置目标赛事后即可生成训练诊断</text>
      <button class="primary-btn" :loading="loading" @click="handleReAnalyze">生成训练诊断</button>
    </view>
    </view>

    <!-- ── EDIT WORKOUT & RUNNER DAILY SELF-REPORT MODAL ── -->
    <view v-if="editModalOpen" class="modal-mask">
      <view class="modal-card">
        <view class="modal-header">
          <text class="modal-title">训练记录与调休</text>
          <text class="modal-close" @click="editModalOpen = false">✕</text>
        </view>

        <scroll-view scroll-y class="modal-scroll-body">
          <!-- Feeling Tag Quick Selector -->
          <view class="modal-input-group">
            <text class="modal-label" style="color:var(--rgm-green, #10b981);font-weight:800;">😊 当日训练感受标签</text>
            <view style="display:grid;grid-template-columns:repeat(3,1fr);gap:10rpx;margin-top:8rpx;">
              <view
                v-for="tag in COACH_FEELING_TAGS"
                :key="tag"
                @click="editFeelingTag = editFeelingTag === tag ? '' : tag"
                style="padding:12rpx 8rpx;border-radius:14rpx;text-align:center;font-size:21rpx;font-weight:700;border:1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.12));"
                :style="editFeelingTag === tag ? 'background:rgba(16,185,129,0.16);border-color:var(--rgm-green, #10b981);color:var(--rgm-green, #10b981);' : 'background:var(--rgm-card-2, rgba(255,255,255,0.05));color:var(--rgm-text, #d4d4d8);'"
              >
                <text>{{ tag }}</text>
              </view>
            </view>
          </view>

          <!-- RPE 1-10 Selector -->
          <view class="modal-input-group">
            <text class="modal-label" style="color:var(--rgm-brand-text, #fb923c);font-weight:800;">🔥 当日训练主观疲劳度 RPE (1=轻松 ~ 10=极限)</text>
            <view style="display:flex;flex-wrap:wrap;gap:8rpx;margin-top:8rpx;">
              <view
                v-for="num in [1,2,3,4,5,6,7,8,9,10]"
                :key="num"
                @click="editRpe = editRpe === String(num) ? '' : String(num)"
                style="width:52rpx;height:52rpx;border-radius:12rpx;display:flex;align-items:center;justify-content:center;font-size:22rpx;font-weight:800;border:1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.12));"
                :style="Number(editRpe) === num ? (num >= 8 ? 'background:#f43f5e;color:#fff;' : num >= 5 ? 'background:#f59e0b;color:#000;' : 'background:#10b981;color:#000;') : 'background:var(--rgm-card-2, rgba(255,255,255,0.05));color:var(--rgm-text-2, #a1a1aa);'"
              >
                <text>{{ num }}</text>
              </view>
            </view>
          </view>

          <view class="modal-row">
            <view class="modal-input-group flex-1">
              <text class="modal-label">🏃 计划执行情况</text>
              <input v-model="editExecutionText" class="modal-input" placeholder="如 15km*602, hr132" />
            </view>
            <view class="modal-input-group flex-1">
              <text class="modal-label">💬 训练感受与备注</text>
              <input v-model="editAthleteNotes" class="modal-input" placeholder="如 体感轻快 / 小腿微酸" />
            </view>
          </view>

          <!-- Workout Photos Uploader (Max 3) -->
          <view class="modal-input-group">
            <view style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8rpx;">
              <text class="modal-label" style="margin-bottom:0;color:var(--rgm-brand-text, #38bdf8);font-weight:800;">📸 打卡照片（最多 3 张）</text>
              <text style="font-size:20rpx;color:var(--rgm-text-2, #a1a1aa);">{{ editWorkoutPhotos.length + editNewPhotosPreview.length }}/3</text>
            </view>
            <view style="display:flex;flex-wrap:wrap;gap:14rpx;">
              <view
                v-for="(url, idx) in editWorkoutPhotos"
                :key="'saved_' + idx"
                style="width:140rpx;height:140rpx;border-radius:16rpx;position:relative;overflow:hidden;border:1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.15));"
              >
                <image
                  :src="url"
                  mode="aspectFill"
                  style="width:100%;height:100%;"
                  @click="previewCoachWorkoutPhotos([...editWorkoutPhotos, ...editNewPhotosPreview], Number(idx))"
                />
                <view
                  @click.stop="editWorkoutPhotos.splice(Number(idx), 1)"
                  style="position:absolute;top:6rpx;right:6rpx;width:36rpx;height:36rpx;border-radius:50%;background:rgba(0,0,0,0.7);color:#fff;font-size:20rpx;display:flex;align-items:center;justify-content:center;"
                >✕</view>
              </view>

              <view
                v-for="(pUrl, nIdx) in editNewPhotosPreview"
                :key="'new_' + nIdx"
                style="width:140rpx;height:140rpx;border-radius:16rpx;position:relative;overflow:hidden;border:1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.15));"
              >
                <image
                  :src="pUrl"
                  mode="aspectFill"
                  style="width:100%;height:100%;"
                  @click="previewCoachWorkoutPhotos([...editWorkoutPhotos, ...editNewPhotosPreview], editWorkoutPhotos.length + Number(nIdx))"
                />
                <view
                  @click.stop="removeCoachNewPhoto(Number(nIdx))"
                  style="position:absolute;top:6rpx;right:6rpx;width:36rpx;height:36rpx;border-radius:50%;background:rgba(0,0,0,0.7);color:#fff;font-size:20rpx;display:flex;align-items:center;justify-content:center;"
                >✕</view>
              </view>

              <view
                v-if="editWorkoutPhotos.length + editNewPhotosPreview.length < 3"
                @click="handleChooseCoachWorkoutPhoto"
                style="width:140rpx;height:140rpx;border-radius:16rpx;background:var(--rgm-card-2, rgba(255,255,255,0.04));border:2rpx dashed var(--rgm-line-solid, rgba(255,255,255,0.22));display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6rpx;"
              >
                <text style="font-size:34rpx;">📷</text>
                <text style="font-size:19rpx;color:var(--rgm-text-2, #a1a1aa);font-weight:600;">添加照片</text>
              </view>
            </view>
          </view>

          <!-- Morning Biometrics -->
          <view class="modal-input-group">
            <text class="modal-label">💓 晨起身体指标 (HRV / 静息心率 / 恢复%)</text>
            <view class="modal-row">
              <view class="flex-1">
                <input v-model="editHrv" type="number" class="modal-input" placeholder="HRV (如 39)" />
              </view>
              <view class="flex-1">
                <input v-model="editRestingHr" type="number" class="modal-input" placeholder="静心 (如 50)" />
              </view>
              <view class="flex-1">
                <input v-model="editRecoveryPct" type="number" class="modal-input" placeholder="恢复% (如 78)" />
              </view>
            </view>
          </view>

          <!-- Day Swap & Strength Toggle -->
          <view class="modal-input-group">
            <view style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8rpx;">
              <text class="modal-label" style="color:var(--rgm-text, #93c5fd);">🔁 与本周其他天对换课表</text>
              <view
                v-if="editIsSwapped"
                @click="handleUndoSwapWorkout"
                style="padding:8rpx 18rpx;border-radius:12rpx;background:rgba(244,63,94,0.16);border:1rpx solid rgba(244,63,94,0.5);color:var(--rgm-red, #fda4af);font-size:21rpx;font-weight:800;"
              >
                <text>↩️ 取消对换 · 恢复原课表{{ editSwappedFrom ? `（原与${editSwappedFrom}对换）` : '' }}</text>
              </view>
            </view>
            <view style="display:flex;flex-wrap:wrap;gap:8rpx;margin-top:8rpx;">
              <view
                @click="editSwapDayIdx = -1"
                style="padding:8rpx 14rpx;border-radius:10rpx;font-size:20rpx;font-weight:700;"
                :style="editSwapDayIdx === -1 ? 'background:#3b82f6;color:#fff;' : 'background:var(--rgm-card-2, rgba(255,255,255,0.06));color:var(--rgm-text-2, #a1a1aa);border:1rpx solid var(--rgm-line-solid, transparent);'"
              >
                <text>不对换</text>
              </view>
              <view
                v-for="(lbl, sIdx) in ['周一','周二','周三','周四','周五','周六','周日']"
                :key="sIdx"
                v-show="sIdx !== editDayIdx"
                @click="editSwapDayIdx = sIdx"
                style="padding:8rpx 14rpx;border-radius:10rpx;font-size:20rpx;font-weight:700;"
                :style="editSwapDayIdx === sIdx ? 'background:#3b82f6;color:#fff;' : 'background:var(--rgm-card-2, rgba(255,255,255,0.06));color:var(--rgm-text-2, #a1a1aa);border:1rpx solid var(--rgm-line-solid, transparent);'"
              >
                <text>换{{ lbl }}</text>
              </view>
            </view>
          </view>

          <view style="display:flex;align-items:center;gap:16rpx;margin-bottom:16rpx;">
            <view
              @click="editCompleted = !editCompleted"
              style="flex:1;padding:14rpx;border-radius:14rpx;text-align:center;font-size:22rpx;font-weight:800;"
              :style="editCompleted ? 'background:rgba(16,185,129,0.16);color:var(--rgm-green, #6ee7b7);border:1rpx solid rgba(16,185,129,0.5);' : 'background:var(--rgm-card-2, rgba(255,255,255,0.05));color:var(--rgm-text-2, #a1a1aa);border:1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.1));'"
            >
              <text>{{ editCompleted ? '✅ 今日跑步课已完成' : '⬜ 标记跑步已完成' }}</text>
            </view>
            <view
              @click="editStrengthDone = !editStrengthDone"
              style="flex:1;padding:14rpx;border-radius:14rpx;text-align:center;font-size:22rpx;font-weight:800;"
              :style="editStrengthDone ? 'background:var(--rgm-brand-tint, rgba(168,85,247,0.25));color:var(--rgm-brand-text, #d8b4fe);border:1rpx solid var(--rgm-brand-line, rgba(168,85,247,0.5));' : 'background:var(--rgm-card-2, rgba(255,255,255,0.05));color:var(--rgm-text-2, #a1a1aa);border:1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.1));'"
            >
              <text>{{ editStrengthDone ? '💪 今日力量已打卡' : '⬜ 标记力量已打卡' }}</text>
            </view>
          </view>

          <view
            v-if="isEditingStartedWeek"
            style="margin-bottom:14rpx;padding:14rpx 18rpx;border-radius:14rpx;background:var(--rgm-brand-tint, rgba(245,158,11,0.12));border:1rpx solid var(--rgm-brand-line, rgba(245,158,11,0.35));"
          >
            <text style="font-size:21rpx;color:var(--rgm-brand-text, #fbbf24);font-weight:700;line-height:1.45;display:block;">
              🔒 第 {{ editWeekIdx }} 周已开始，课表处方已锁定；仍可记录打卡、体感或调休对换。
            </text>
          </view>

          <view class="modal-input-group">
            <text class="modal-label">课目标题 {{ isEditingStartedWeek ? '🔒' : '' }}</text>
            <input v-model="editTitle" :disabled="isEditingStartedWeek" class="modal-input" :style="isEditingStartedWeek ? 'opacity:0.55;' : ''" placeholder="输入课目标题" />
          </view>

          <view class="modal-row">
            <view class="modal-input-group flex-1">
              <text class="modal-label">计划跑量 (km) {{ isEditingStartedWeek ? '🔒' : '' }}</text>
              <input v-model="editDistanceKm" :disabled="isEditingStartedWeek" type="digit" class="modal-input" :style="isEditingStartedWeek ? 'opacity:0.55;' : ''" />
            </view>
            <view class="modal-input-group flex-1">
              <text class="modal-label">目标配速 {{ isEditingStartedWeek ? '🔒' : '' }}</text>
              <input v-model="editTargetPace" :disabled="isEditingStartedWeek" class="modal-input" :style="isEditingStartedWeek ? 'opacity:0.55;' : ''" placeholder="如 5:15 - 5:25 /km" />
            </view>
          </view>

          <view class="modal-input-group">
            <text class="modal-label">课表安排与热身冷身说明 {{ isEditingStartedWeek ? '🔒' : '' }}</text>
            <textarea v-model="editDescription" :disabled="isEditingStartedWeek" class="modal-textarea" :style="isEditingStartedWeek ? 'opacity:0.55;' : ''" maxlength="300" />
          </view>
        </scroll-view>

        <view class="modal-footer">
          <button class="modal-cancel-btn" @click="editModalOpen = false">取消</button>
          <button class="modal-save-btn" :loading="savingWorkout" @click="handleSaveWorkout">保存打卡与体感</button>
        </view>
      </view>
    </view>

    <!-- ── 底部运动生理算法免责声明 ── -->
    <view class="ai-legal-disclaimer">
      <text class="ai-legal-text">基于运动生理模型推算，仅供参考，不作医疗诊断依据。</text>
    </view>

    <!-- 个人打卡 & 已完赛赛事分享朋友圈卡片弹窗 -->
    <PersonalShareCardModal
      :visible="showCoachShareCard"
      :race-id="activeCoachShareRaceId"
      @close="showCoachShareCard = false"
    />

    <!-- 个人跑步周报与月报弹窗 -->
    <PersonalReportModal
      :visible="showCoachPersonalReport"
      @close="showCoachPersonalReport = false"
    />

    <!-- 💬 AI 科学教练实时问答抽屉 -->
    <view
      v-if="showCoachChatModal"
      class="modal-overlay"
      @click="showCoachChatModal = false"
      @touchmove.stop.prevent
    >
      <view
        class="modal-card"
        style="max-height: 82vh; display: flex; flex-direction: column;"
        @click.stop
      >
        <view class="modal-header">
          <text class="modal-title">💬 咨询 Canova 科学教练</text>
          <text class="modal-close" @click="showCoachChatModal = false">✕</text>
        </view>

        <view style="padding: 12rpx 24rpx; display: flex; flex-wrap: wrap; gap: 10rpx; border-bottom: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));">
          <view
            v-for="qp in ['今天状态偏累怎么调课？', '如何提升马拉松有氧配速？', '本周长距离该怎么配速？']"
            :key="qp"
            style="padding: 8rpx 16rpx; border-radius: 999rpx; background: var(--rgm-brand-tint, rgba(252,76,2,0.14)); border: 1rpx solid var(--rgm-brand-line, rgba(252,76,2,0.35));"
            @click="sendCoachChatMessage(qp)"
          >
            <text style="font-size: 21rpx; color: var(--rgm-brand-text, #fb923c); font-weight: 700;">{{ qp }}</text>
          </view>
        </view>

        <scroll-view scroll-y style="flex: 1; min-height: 360rpx; max-height: 52vh; padding: 20rpx 24rpx; box-sizing: border-box;">
          <view
            v-for="(msg, mIdx) in coachChatMessages"
            :key="mIdx"
            :style="msg.role === 'user' ? 'display:flex;justify-content:flex-end;margin-bottom:18rpx;' : 'display:flex;justify-content:flex-start;margin-bottom:18rpx;'"
          >
            <view
              :style="msg.role === 'user'
                ? 'max-width:84%;padding:16rpx 22rpx;border-radius:20rpx 20rpx 6rpx 20rpx;background:#fc4c02;color:#fff;'
                : 'max-width:90%;padding:18rpx 22rpx;border-radius:20rpx 20rpx 20rpx 6rpx;background:var(--rgm-card-2, rgba(255,255,255,0.07));border:1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.1));color:var(--rgm-text, #f4f4f5);'"
            >
              <text style="font-size: 25rpx; line-height: 1.55; white-space: pre-wrap;">{{ msg.content }}</text>
            </view>
          </view>
          <view v-if="sendingCoachChat" style="padding: 10rpx 4rpx;">
            <text style="font-size: 22rpx; color: var(--rgm-text-2, #a1a1aa);">🎯 教练正在结合您的 CTL/ATL 负荷与课表推演建议...</text>
          </view>
        </scroll-view>

        <view style="padding: 16rpx 24rpx; display: flex; align-items: center; gap: 12rpx; border-top: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));">
          <input
            v-model="coachChatInput"
            class="modal-input"
            style="flex: 1; margin: 0;"
            placeholder="输入训练、配速、心率或伤痛恢复问题..."
            confirm-type="send"
            @confirm="sendCoachChatMessage()"
          />
          <button
            class="modal-save-btn"
            style="flex: 0 0 auto; width: auto; padding: 0 28rpx; height: 72rpx; line-height: 72rpx; margin: 0;"
            :loading="sendingCoachChat"
            :disabled="sendingCoachChat"
            @click="sendCoachChatMessage()"
          >
            发送
          </button>
        </view>
      </view>
    </view>

    <GoalSheetModal
      :visible="showCoachGoalSheet"
      :default-tab="coachGoalSheetTab"
      :user-id="user?.id"
      :initial-goal="userGoal"
      @close="showCoachGoalSheet = false"
      @saved="handleCoachGoalSaved"
    />
  </view>
</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import { explainTerm } from "../../utils/glossary";
import { trackClick, trackSubView, trackFunnelStep } from "../../utils/telemetry";
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { onShow, onPullDownRefresh, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import { request, getStoredUser, checkAndAutoLogin, UserProfile, syncTabBarIndex } from "../../utils/api";
import PersonalShareCardModal from "../../components/PersonalShareCardModal.vue";
import PersonalReportModal from "../../components/PersonalReportModal.vue";
import GoalSheetModal from "../../components/GoalSheetModal.vue";

const showCoachGoalSheet = ref(false);
const coachGoalSheetTab = ref<"week" | "month">("week");
function openCoachGoalSheet(tab: "week" | "month" = "week") {
  coachGoalSheetTab.value = tab;
  showCoachGoalSheet.value = true;
}
function handleCoachGoalSaved(savedGoal: any) {
  userGoal.value = { ...(userGoal.value || {}), ...(savedGoal || {}) };
}

const activeTab = ref<"plan" | "analysis">("plan");
watch(activeTab, (tab) => {
  trackSubView(`coach_${tab}`, `训练页切换：${tab === "analysis" ? "跑力与生理分析" : "周期训练课表"}`);
});
const showCoachShareCard = ref(false);
const showCoachPersonalReport = ref(false);
const activeCoachShareRaceId = ref("");

function openCompletedTargetRaceShareCard() {
  const targetName = plan.value?.target_race_name;
  const matched = (userRaces.value || []).find(
    (r: any) => r.name === targetName || (r.status === "completed" || r.is_completed)
  );
  activeCoachShareRaceId.value = matched ? String(matched.id || matched.name) : String(targetName || "");
  showCoachShareCard.value = true;
}

// 原【深度分析】Tab 已并入【训练】，以二级页面打开
function goToBodyData() {
  uni.navigateTo({ url: "/pages/analysis/analysis" });
}

// Training Plan State
const plan = ref<any>(null);
const planBackups = ref<any[]>([]);
const rollingBackPlan = ref(false);
const savedPlanBackup = ref<any>(null);
const isPreviewPlan = ref(false);
const confirmingPlan = ref(false);

// AI Coach Chat State
const showCoachChatModal = ref(false);
const coachChatInput = ref("");
const sendingCoachChat = ref(false);
const coachChatMessages = ref<Array<{ role: "user" | "assistant"; content: string }>>([
  {
    role: "assistant",
    content: "您好！我是您的 Canova 科学耐力教练。我已同步您的近期跑量、负荷曲线（CTL/ATL/TSB）与当前周期课表，随时可向我咨询今日调课、目标配速或伤痛恢复方案。",
  },
]);

function openCoachChatModal() {
  trackClick("coach_open_ai_chat", "训练页打开AI科学教练咨询");
  showCoachChatModal.value = true;
}

async function sendCoachChatMessage(presetQuestion?: string) {
  const q = String(presetQuestion ?? coachChatInput.value ?? "").trim();
  if (!q || sendingCoachChat.value) return;
  if (!presetQuestion) coachChatInput.value = "";

  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value?.id) return;

  const historySnapshot = coachChatMessages.value.slice(-4);
  coachChatMessages.value.push({ role: "user", content: q });
  sendingCoachChat.value = true;
  try {
    const res = await request("/api/coach/chat", "POST", {
      uid: user.value.id,
      message: q,
      history: historySnapshot,
    });
    const reply = String(res?.reply || "教练已收到问题，建议先保持有氧稳态跑并关注晨起静息心率与体感反馈。");
    coachChatMessages.value.push({ role: "assistant", content: reply });
  } catch (err: any) {
    coachChatMessages.value.push({
      role: "assistant",
      content: err?.message || "网络连接稍有波动，请稍后再试。",
    });
  } finally {
    sendingCoachChat.value = false;
  }
}
const planLoading = ref(false);
const generatingPlan = ref(false);
const showPlanConfig = ref(false);
const showWeekSummaryForm = ref(false);
const showAnalysisRaceSetup = ref(false);
const selectedWeekIdx = ref(1);
const scrollIntoWeek = ref("");

function scrollToWeek(wk: number) {
  scrollIntoWeek.value = "";
  nextTick(() => {
    setTimeout(() => {
      scrollIntoWeek.value = "week-chip-" + wk;
    }, 120);
  });
}

function selectWeek(idx: number) {
  selectedWeekIdx.value = idx;
  scrollToWeek(idx);
}

const currentWeekIndex = computed(() => {
  if (plan.value?.current_week_index) {
    return Number(plan.value.current_week_index);
  }
  return computeCurrentWeekIndex(plan.value);
});

watch(
  () => plan.value,
  (newPlan) => {
    if (newPlan) {
      const curWk = Number(newPlan.current_week_index) || computeCurrentWeekIndex(newPlan);
      if (curWk) {
        selectedWeekIdx.value = curWk;
        scrollToWeek(curWk);
      }
    }
  },
  { immediate: true }
);

function computeCurrentWeekIndex(planData: any): number {
  if (!planData) return 1;
  const weeks = planData.schedule_data?.weeks || [];
  if (!weeks.length) return 1;

  // Format today in Beijing time (YYYY-MM-DD)
  const now = new Date();
  const beijingTime = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000);
  const y = beijingTime.getFullYear();
  const m = String(beijingTime.getMonth() + 1).padStart(2, "0");
  const d = String(beijingTime.getDate()).padStart(2, "0");
  const todayStr = `${y}-${m}-${d}`;

  for (const w of weeks) {
    const days = w.days || [];
    if (days.some((day: any) => day.date === todayStr)) {
      return w.week_index || 1;
    }
    const dates = days.map((day: any) => day.date).filter(Boolean);
    if (dates.length && dates[0] <= todayStr && todayStr <= dates[dates.length - 1]) {
      return w.week_index || 1;
    }
  }

  // If today is before first week
  const firstDays = weeks[0]?.days || [];
  const firstDates = firstDays.map((day: any) => day.date).filter(Boolean);
  if (firstDates.length && todayStr < firstDates[0]) {
    return weeks[0].week_index || 1;
  }

  // If today is after last week
  const lastDays = weeks[weeks.length - 1]?.days || [];
  const lastDates = lastDays.map((day: any) => day.date).filter(Boolean);
  if (lastDates.length && todayStr > lastDates[lastDates.length - 1]) {
    return weeks[weeks.length - 1].week_index || weeks.length;
  }

  return 1;
}

const planGoalType = ref<"race_prep" | "fitness_maintenance">("race_prep");
const planRaceName = ref("");
const planTargetTime = ref("3:09:30");
const planMaintenanceFocus = ref("aerobic_base");
const planWeeksCount = ref(8);
const planDaysPerWeek = ref(4);
const planWeekOptions = [4, 6, 8, 10, 12, 16];
const planWeekOptionLabels = [
  "4 周 · 冲刺微周期",
  "6 周 · 标准进阶",
  "8 周 · 经典备战",
  "10 周 · 进阶周期",
  "12 周 · 完整周期",
  "16 周 · 长线备赛",
];
const planDayOptions = [3, 4, 5, 6];
const planDayOptionLabels = [
  "3 天/周 · 轻量均衡",
  "4 天/周 · 经典推荐",
  "5 天/周 · 进阶强化",
  "6 天/周 · 严肃跑者",
];
function stepPlanWeeks(delta: number) {
  const curIdx = planWeekOptions.indexOf(planWeeksCount.value);
  const baseIdx = curIdx >= 0 ? curIdx : 2;
  const nextIdx = Math.min(planWeekOptions.length - 1, Math.max(0, baseIdx + delta));
  planWeeksCount.value = planWeekOptions[nextIdx];
}
function stepPlanDays(delta: number) {
  const curIdx = planDayOptions.indexOf(planDaysPerWeek.value);
  const baseIdx = curIdx >= 0 ? curIdx : 1;
  const nextIdx = Math.min(planDayOptions.length - 1, Math.max(0, baseIdx + delta));
  planDaysPerWeek.value = planDayOptions[nextIdx];
}
const userGoal = ref<any>(null);
const syncingGoal = ref(false);
const recoveryDataAvailability = ref<any>(null);

const recommendedRace = computed(() => {
  if (!userRaces.value || userRaces.value.length === 0) return null;
  const upcomingRaces = userRaces.value.filter(
    (r: any) => r.status !== "completed" && !r.is_completed && !r.is_past
  );
  const candidates = upcomingRaces.length > 0 ? upcomingRaces : userRaces.value;
  const aRace = candidates.find(
    (r: any) => r.priority == 1 || r.priority === "A" || r.priority === "1"
  );
  if (aRace) return aRace;
  const bRace = candidates.find(
    (r: any) => r.priority == 2 || r.priority === "B" || r.priority === "2"
  );
  if (bRace) return bRace;
  return candidates[0] || userRaces.value[0];
});

const isTargetRaceCompleted = computed(() => {
  if (!plan.value || !userRaces.value || userRaces.value.length === 0) return false;
  const targetName = plan.value.target_race_name;
  const matched = userRaces.value.find(
    (r: any) =>
      r.name === targetName || (plan.value.title && plan.value.title.includes(r.name))
  );
  return Boolean(
    matched &&
      (matched.status === "completed" ||
        matched.is_completed ||
        matched.is_past)
  );
});

function handleApplyRecommendedRace() {
  if (!recommendedRace.value) return;
  const rec = recommendedRace.value;
  planRaceName.value = rec.name;
  if (rec.target_time) planTargetTime.value = rec.target_time;
  showPlanConfig.value = true;
}

function handleSelectPlanRace(r: any) {
  if (r.status === "completed" || r.is_completed) {
    uni.showToast({ title: "该比赛已完赛，请选择未完赛的目标", icon: "none" });
    return;
  }
  planRaceName.value = r.name;
  if (r.target_time) planTargetTime.value = r.target_time;
}

function getAlignmentRatio(week: any): number {
  const target = Number(userGoal.value?.weekly_target) || 50;
  const planned = Number(week?.weekly_mileage_km) || 0;
  return target > 0 ? Math.round((planned / target) * 100) : 100;
}

function getAlignmentPillClass(week: any): string {
  const hasRace = (week?.days || []).some((d: any) => d.workout_type === "race");
  if (hasRace) return "align-race";
  const isDownWeek = (week?.phase || "").includes("减量") || (week?.week_title || "").includes("减量");
  if (isDownWeek) return "align-down";
  const ratio = getAlignmentRatio(week);
  if (ratio >= 88 && ratio <= 112) return "align-good";
  return "align-climb";
}

function getAlignmentIcon(week: any): string {
  const hasRace = (week?.days || []).some((d: any) => d.workout_type === "race");
  if (hasRace) return "🏁";
  const isDownWeek = (week?.phase || "").includes("减量") || (week?.week_title || "").includes("减量");
  if (isDownWeek) return "🌊";
  const ratio = getAlignmentRatio(week);
  if (ratio >= 88 && ratio <= 112) return "🎯";
  return "⚡";
}

function getAlignmentLabel(week: any): string {
  const hasRace = (week?.days || []).some((d: any) => d.workout_type === "race");
  if (hasRace) return "实战周";
  const isDownWeek = (week?.phase || "").includes("减量") || (week?.week_title || "").includes("减量");
  if (isDownWeek) return "减量恢复";
  const ratio = getAlignmentRatio(week);
  if (ratio >= 88 && ratio <= 112) return "科学对齐";
  return "渐进爬坡";
}

const maintenanceList = [
  { id: "aerobic_base", name: "🏃 基础有氧耐力扩容", desc: "Zone 2 低心率 · 慢肌毛细血管网" },
  { id: "lactate_threshold", name: "⚡ 乳酸阈值耐力提升", desc: "LT2 巡航间歇 · 提高抗乳酸稳态" },
  { id: "vo2max_speed", name: "🚀 VO2Max 速度储备", desc: "800~1500m 间歇 · 步频神经刚性" },
  { id: "trail_climbing", name: "🏔️ 山地越野爬坡抗阻", desc: "手杖爬升 D+ · 股四头肌离心耐受" },
  { id: "general_maintenance", name: "🛡️ 综合体能维持", desc: "平衡跑量 · 核心稳定与防伤" }
];

const activeMiniWeek = computed(() => {
  const weeks = plan.value?.schedule_data?.weeks || [];
  return weeks.find((w: any) => w.week_index === selectedWeekIdx.value) || weeks[0];
});

const COACH_FEELING_TAGS = [
  "🤩 状态极佳",
  "😊 轻松舒适",
  "💪 正常发挥",
  "😮‍💨 略感吃力",
  "🥵 疲惫掉速",
  "🦵 肌肉酸紧",
];

// Edit modal & runner daily self-report state
const editModalOpen = ref(false);
const editWeekIdx = ref(1);
const editDayIdx = ref(0);
const editWorkoutType = ref("easy_run");
const editTitle = ref("");
const editDistanceKm = ref<number | string>(0);
const editTargetPace = ref("");
const editTargetHrZone = ref("");
const editDescription = ref("");
const editCompleted = ref(false);
const editCoachNotes = ref("");
const editFeelingTag = ref("");
const editRpe = ref("");
const editExecutionText = ref("");
const editAthleteNotes = ref("");
const editWorkoutPhotos = ref<string[]>([]);
const editNewPhotosPreview = ref<string[]>([]);
const editNewPhotosBase64 = ref<string[]>([]);
const editHrv = ref("");
const editRestingHr = ref("");
const editRecoveryPct = ref("");
const editStrengthDone = ref(false);
const editSwapDayIdx = ref(-1);
const editIsSwapped = ref(false);
const editSwappedFrom = ref("");
const savingWorkout = ref(false);

function previewCoachWorkoutPhotos(urls: string[], currentIdx: number = 0) {
  if (!urls || !urls.length) return;
  uni.previewImage({
    urls,
    current: urls[currentIdx] || urls[0],
  });
}

function removeCoachNewPhoto(idx: number) {
  editNewPhotosPreview.value.splice(idx, 1);
  editNewPhotosBase64.value.splice(idx, 1);
}

function handleChooseCoachWorkoutPhoto() {
  const total = editWorkoutPhotos.value.length + editNewPhotosPreview.value.length;
  const remain = Math.max(0, 3 - total);
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
                editNewPhotosPreview.value.push(filePath);
                editNewPhotosBase64.value.push(`data:image/jpeg;base64,${b64}`);
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

const isEditingStartedWeek = computed(() => {
  if (isPreviewPlan.value) return false;
  return Number(editWeekIdx.value) <= Number(currentWeekIndex.value || 1);
});

// Weekly summary & injury report state
const weekInjuryNote = ref("");
const weekAthleteSummary = ref("");
const weekTravelNote = ref("");
const savingWeekSummary = ref(false);

watch(
  () => [activeMiniWeek.value?.week_index, plan.value?.updated_at],
  () => {
    if (activeMiniWeek.value) {
      weekInjuryNote.value = activeMiniWeek.value.injury_note || "";
      weekAthleteSummary.value = activeMiniWeek.value.athlete_weekly_summary || "";
      weekTravelNote.value = activeMiniWeek.value.travel_or_leave_note || "";
    }
  },
  { immediate: true }
);

function getWorkoutTypeLabel(type: string): string {
  const map: Record<string, string> = {
    easy_run: "轻松跑",
    tempo: "门槛跑",
    interval: "间歇跑",
    long_run: "长距离",
    trail_climb: "越野爬坡",
    cross_training: "交叉力量",
    race: "🏁 比赛日",
    rest: "休息日"
  };
  return map[type] || "跑步";
}

function getWorkoutBadgeClass(type: string): string {
  const map: Record<string, string> = {
    easy_run: "badge-easy",
    tempo: "badge-tempo",
    interval: "badge-interval",
    long_run: "badge-long",
    trail_climb: "badge-trail",
    cross_training: "badge-cross",
    race: "badge-race",
    rest: "badge-rest"
  };
  return map[type] || "badge-rest";
}

function getWorkoutBorderClass(type: string): string {
  const map: Record<string, string> = {
    easy_run: "border-easy",
    tempo: "border-tempo",
    interval: "border-interval",
    long_run: "border-long",
    trail_climb: "border-trail",
    cross_training: "border-cross",
    race: "border-race",
    rest: "border-rest"
  };
  return map[type] || "border-rest";
}

function isDayMissed(day: any): boolean {
  if (!day) return false;
  if (day.is_missed !== undefined) return Boolean(day.is_missed);
  if (day.completed) return false;
  if (day.workout_type === "rest") return false;
  if (!day.date) return false;
  const todayStr = new Date().toLocaleDateString("en-CA");
  return day.date < todayStr && (Number(day.distance_km) || 0) > 0;
}

async function loadUserPlan() {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  planLoading.value = true;
  try {
    const res = await request(`/api/coach/plan/user/${user.value.id}`);
    planBackups.value = Array.isArray(res?.backups) ? res.backups : [];
    if (res?.active_plan) {
      const curWk = Number(res.active_plan.current_week_index) || computeCurrentWeekIndex(res.active_plan);
      selectedWeekIdx.value = curWk;
      plan.value = res.active_plan;
      showPlanConfig.value = false;
      scrollToWeek(curWk);
    } else {
      showPlanConfig.value = true;
    }
    if (res?.user_goal) {
      userGoal.value = res.user_goal;
    }
    if (res?.recovery_data_availability) {
      recoveryDataAvailability.value = res.recovery_data_availability;
    }
  } catch (err) {
    console.warn("Load plan error:", err);
  } finally {
    planLoading.value = false;
  }
}

async function handleSyncToGoals() {
  user.value = getStoredUser();
  if (!user.value || !user.value.id || !plan.value?.id) return;

  uni.showModal({
    title: "同步课表至个人目标",
    content: "确定将当前周期课表的周跑量与月度目标同步为您的个人目标吗？首页打卡进度环将直接跟踪该计划。",
    confirmText: "立即同步",
    confirmColor: "#af52de",
    success: async (mRes) => {
      if (!mRes.confirm) return;
      syncingGoal.value = true;
      try {
        const res = await request(`/api/coach/plan/${plan.value.id}/sync-to-goals`, "POST", {
          user_id: user.value.id
        });
        if (res?.success) {
          if (userGoal.value) {
            userGoal.value.weekly_target = res.weekly_target;
            userGoal.value.target_distance = res.monthly_target;
            userGoal.value.monthly_targets = res.monthly_targets;
          } else {
            userGoal.value = {
              weekly_target: res.weekly_target,
              target_distance: res.monthly_target,
              monthly_targets: res.monthly_targets
            };
          }
          uni.showToast({
            title: `已同步！周目标: ${res.weekly_target}k`,
            icon: "success",
            duration: 2500
          });
        }
      } catch (err) {
        console.error("Sync goals error:", err);
        uni.showToast({ title: "同步失败，请稍后重试", icon: "none" });
      } finally {
        syncingGoal.value = false;
      }
    }
  });
}

async function handleGeneratePlan() {
  trackClick("coach_generate_plan", "点击「生成周期训练课表」", {
    goal_type: planGoalType.value,
    weeks: planWeeksCount.value,
  });
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  generatingPlan.value = true;
  try {
    if (!isPreviewPlan.value && plan.value) {
      savedPlanBackup.value = JSON.parse(JSON.stringify(plan.value));
    }
    const payload = {
      athlete_uid: user.value.id,
      goal_type: planGoalType.value,
      target_race_name: planRaceName.value,
      target_time: planTargetTime.value,
      maintenance_focus: planMaintenanceFocus.value,
      weeks_count: planWeeksCount.value,
      days_per_week: planDaysPerWeek.value,
      operator_uid: user.value.id,
      user_weekly_target: userGoal.value?.weekly_target ? Number(userGoal.value.weekly_target) : undefined,
      preview_only: true
    };
    const res = await request("/api/coach/plan/generate", "POST", payload);
    if (res?.success && res?.plan) {
      trackFunnelStep("coach_generate_plan_preview", "生成新训练课表预览", {
        weeks_count: planWeeksCount.value,
        days_per_week: planDaysPerWeek.value,
      });
      plan.value = res.plan;
      isPreviewPlan.value = true;
      const curWk = res.plan.current_week_index || computeCurrentWeekIndex(res.plan);
      selectedWeekIdx.value = curWk;
      showPlanConfig.value = false;
      uni.showModal({
        title: "已生成课表预览（尚未写入）",
        content: "新训练课表已生成预览。您可以先审阅各周安排，或立即点击「确认更新并启用」正式写入生效；若不确认则不会覆盖原计划。",
        confirmText: "立即确认启用",
        cancelText: "先审阅预览",
        confirmColor: "#10b981",
        success: (mRes) => {
          if (mRes.confirm) {
            doConfirmGeneratedPlan();
          }
        }
      });
    }
  } catch (err) {
    console.error("Generate plan error:", err);
    uni.showToast({ title: "生成课表失败", icon: "none" });
  } finally {
    generatingPlan.value = false;
  }
}

async function doConfirmGeneratedPlan() {
  if (!plan.value || !user.value?.id) return;
  confirmingPlan.value = true;
  try {
    const res = await request("/api/coach/plan/confirm", "POST", {
      plan_payload: plan.value,
      operator_uid: user.value.id
    });
    if (res?.success && res?.plan) {
      trackFunnelStep("coach_confirm_plan_success", "确认启用新周期训练课表");
      plan.value = res.plan;
      isPreviewPlan.value = false;
      savedPlanBackup.value = null;
      uni.showToast({ title: "已确认更新并启用计划！", icon: "success" });
      await loadUserPlan();
    }
  } catch (err: any) {
    uni.showToast({ title: err?.message || "确认更新失败", icon: "none" });
  } finally {
    confirmingPlan.value = false;
  }
}

function handleRollbackUserPlan() {
  if (!user.value?.id || !planBackups.value.length || rollingBackPlan.value) return;
  const latestBackup = planBackups.value[0];
  uni.showModal({
    title: "恢复上一版课表",
    content: "确定将当前周期课表回退至上一版备份快照吗？已记录的跑步活动不会被删除。",
    confirmText: "确认回退",
    cancelText: "取消",
    confirmColor: "#f59e0b",
    success: async (mRes) => {
      if (!mRes.confirm || !user.value?.id) return;
      rollingBackPlan.value = true;
      try {
        const res = await request(`/api/coach/plan/user/${user.value.id}/rollback`, "POST", {
          operator_uid: user.value.id,
          backup_id: latestBackup?.id,
        });
        if (res?.active_plan) {
          plan.value = res.active_plan;
          const curWk = Number(res.active_plan.current_week_index) || computeCurrentWeekIndex(res.active_plan);
          selectedWeekIdx.value = curWk;
          scrollToWeek(curWk);
        }
        if (Array.isArray(res?.backups)) {
          planBackups.value = res.backups;
        } else {
          await loadUserPlan();
        }
        uni.showToast({ title: "已恢复上一版课表！", icon: "success" });
      } catch (err: any) {
        uni.showToast({ title: err?.message || "回退课表失败", icon: "none" });
      } finally {
        rollingBackPlan.value = false;
      }
    },
  });
}

function handleConfirmGeneratedPlan() {
  uni.showModal({
    title: "确认更新训练计划",
    content: "确定启用这套新生成的周期训练课表并正式写入更新现有计划吗？",
    confirmText: "确认更新",
    cancelText: "再看看",
    confirmColor: "#10b981",
    success: (mRes) => {
      if (mRes.confirm) {
        doConfirmGeneratedPlan();
      }
    }
  });
}

function handleDiscardGeneratedPlan() {
  uni.showModal({
    title: "放弃此次排课预览",
    content: "放弃后本次生成的预览课表将不会写入，保持原训练计划不变。确认放弃吗？",
    confirmText: "确认放弃",
    cancelText: "继续查看",
    confirmColor: "#ef4444",
    success: (mRes) => {
      if (mRes.confirm) {
        plan.value = savedPlanBackup.value;
        isPreviewPlan.value = false;
        savedPlanBackup.value = null;
        if (!plan.value) {
          showPlanConfig.value = true;
        }
        uni.showToast({ title: "已放弃预览，未写入更改", icon: "none" });
      }
    }
  });
}

function openEditWorkoutModal(wIdx: number, dIdx: number, day: any) {
  editWeekIdx.value = wIdx;
  editDayIdx.value = dIdx;
  editWorkoutType.value = day.workout_type || "easy_run";
  editTitle.value = day.title || "";
  editDistanceKm.value = day.distance_km || 0;
  editTargetPace.value = day.target_pace || "";
  editTargetHrZone.value = day.target_hr_zone || "";
  editDescription.value = day.description || "";
  editCompleted.value = Boolean(day.completed);
  editCoachNotes.value = day.coach_notes || "";
  editFeelingTag.value = day.feeling_tag || "";
  editRpe.value = day.rpe != null ? String(day.rpe) : "";
  editExecutionText.value = day.actual_execution_text || "";
  editAthleteNotes.value = day.athlete_notes || "";
  editWorkoutPhotos.value = Array.isArray(day.workout_photos) ? [...day.workout_photos] : (day.photo_url ? [day.photo_url] : []);
  editNewPhotosPreview.value = [];
  editNewPhotosBase64.value = [];
  editHrv.value = day.hrv != null ? String(day.hrv) : "";
  editRestingHr.value = day.resting_hr != null ? String(day.resting_hr) : "";
  editRecoveryPct.value = day.recovery_pct != null ? String(day.recovery_pct) : "";
  editStrengthDone.value = Boolean(day.strength_completed);
  editSwapDayIdx.value = -1;
  const noteStr = String(day.athlete_notes || "");
  const execStr = String(day.actual_execution_text || "");
  editIsSwapped.value = Boolean(
    day.is_swapped ||
      day.swapped_from ||
      noteStr.includes("对换课表") ||
      (execStr.startsWith("跑休") && execStr.includes("对换"))
  );
  editSwappedFrom.value = day.swapped_from || "";
  editModalOpen.value = true;
}

async function handleUndoSwapWorkout() {
  if (!plan.value?.id || !user.value?.id) return;
  savingWorkout.value = true;
  try {
    const payload: any = {
      week_index: editWeekIdx.value,
      day_index: editDayIdx.value,
      undo_swap: true,
      operator_uid: user.value.id
    };
    if (isPreviewPlan.value) {
      payload.preview_only = true;
      payload.plan_payload = plan.value;
      payload.schedule_data = plan.value?.schedule_data;
    }
    const res = await request(`/api/coach/plan/${plan.value.id}/workout`, "PATCH", payload);
    if (res?.success && res?.plan) {
      plan.value = res.plan;
      editModalOpen.value = false;
      uni.showToast({ title: "已取消对换并恢复原课表", icon: "success" });
    }
  } catch (err) {
    console.error("Undo swap workout error:", err);
    uni.showToast({ title: "取消对换失败", icon: "none" });
  } finally {
    savingWorkout.value = false;
  }
}

async function handleSaveWorkout() {
  if (!plan.value?.id || !user.value?.id) return;
  savingWorkout.value = true;
  try {
    const payload: any = {
      week_index: editWeekIdx.value,
      day_index: editDayIdx.value,
      workout_type: editWorkoutType.value,
      title: editTitle.value,
      distance_km: parseFloat(String(editDistanceKm.value)) || 0,
      target_pace: editTargetPace.value,
      target_hr_zone: editTargetHrZone.value,
      description: editDescription.value,
      completed: editCompleted.value,
      coach_notes: editCoachNotes.value,
      feeling_tag: editFeelingTag.value,
      athlete_notes: editAthleteNotes.value,
      workout_photos: editWorkoutPhotos.value,
      new_photos_base64: editNewPhotosBase64.value,
      actual_execution_text: editExecutionText.value,
      strength_completed: editStrengthDone.value,
      operator_uid: user.value.id
    };
    if (String(editRpe.value).trim() !== "") payload.rpe = Number(editRpe.value);
    if (String(editHrv.value).trim() !== "") payload.hrv = Number(editHrv.value);
    if (String(editRestingHr.value).trim() !== "") payload.resting_hr = Number(editRestingHr.value);
    if (String(editRecoveryPct.value).trim() !== "") payload.recovery_pct = Number(editRecoveryPct.value);
    if (editSwapDayIdx.value >= 0 && editSwapDayIdx.value !== editDayIdx.value) {
      payload.swap_with_day_index = editSwapDayIdx.value;
    }
    if (isPreviewPlan.value) {
      payload.preview_only = true;
      payload.plan_payload = plan.value;
      payload.schedule_data = plan.value?.schedule_data;
    }
    const res = await request(`/api/coach/plan/${plan.value.id}/workout`, "PATCH", payload);
    if (res?.success && res?.plan) {
      trackFunnelStep("coach_save_workout_rpe", "保存课表打卡与体感反馈");
      plan.value = res.plan;
      editModalOpen.value = false;
      uni.showToast({ title: "打卡与体感已保存", icon: "success" });
    }
  } catch (err) {
    console.error("Save workout error:", err);
    uni.showToast({ title: "保存失败", icon: "none" });
  } finally {
    savingWorkout.value = false;
  }
}

async function handleSaveRunnerWeekSummary() {
  if (!plan.value?.id || !user.value?.id || !activeMiniWeek.value) return;
  savingWeekSummary.value = true;
  try {
    const res = await request(`/api/coach/plan/${plan.value.id}/week-summary`, "POST", {
      operator_uid: user.value.id,
      week_index: activeMiniWeek.value.week_index || selectedWeekIdx.value,
      injury_note: weekInjuryNote.value,
      athlete_weekly_summary: weekAthleteSummary.value,
      travel_or_leave_note: weekTravelNote.value,
    });
    if (res?.plan) {
      plan.value = res.plan;
      uni.showToast({ title: "周小结与伤痛已提交", icon: "success" });
    }
  } catch (err) {
    uni.showToast({ title: "提交周小结失败", icon: "none" });
  } finally {
    savingWeekSummary.value = false;
  }
}

async function handleToggleComplete(wIdx: number, dIdx: number, day: any) {
  if (!plan.value?.id || !user.value?.id) return;
  try {
    const newCompleted = !day.completed;
    const payload = {
      week_index: wIdx,
      day_index: dIdx,
      completed: newCompleted,
      operator_uid: user.value.id
    };
    const res = await request(`/api/coach/plan/${plan.value.id}/workout`, "PATCH", payload);
    if (res?.success && res?.plan) {
      if (newCompleted) {
        trackFunnelStep("coach_workout_checkin", "完成单日训练课表打卡");
      }
      plan.value = res.plan;
      if (newCompleted) {
        uni.showToast({ title: "已打卡！可补充训练感受与照片", icon: "success" });
        const updatedWeek = (res.plan?.schedule_data?.weeks || []).find((w: any) => w.week_index === wIdx);
        const updatedDay = updatedWeek?.days?.[dIdx] || { ...day, completed: true };
        openEditWorkoutModal(wIdx, dIdx, updatedDay);
      } else {
        uni.showToast({ title: "已取消打卡", icon: "none" });
      }
    }
  } catch (err) {
    console.error("Toggle complete error:", err);
  }
}

const racePresets = [
  { label: "🏔️ 武功山 50K", race: "武功山 50K", time: "8:00:00", type: "trail" },
  { label: "🏅 无锡全马", race: "无锡马拉松", time: "3:15:00", type: "marathon" },
  { label: "⚡ 上海半马", race: "上海半程马拉松", time: "1:35:00", type: "half" },
  { label: "🏃 10K 速度", race: "日常 10公里 突破", time: "42:00", type: "10k" },
];

const targetRace = ref("武功山 50K");
const targetTime = ref("8:00:00");
const raceType = ref("trail");

function autoDetectRaceType(name: string): string | null {
  const lower = (name || "").toLowerCase();
  if (lower.includes("越野") || lower.includes("trail") || lower.includes("ultra") || lower.includes("50k") || lower.includes("100k") || lower.includes("武功山") || lower.includes("崇礼") || lower.includes("柴古") || lower.includes("utmb") || lower.includes("160")) {
    return "trail";
  } else if (lower.includes("半马") || lower.includes("半程") || lower.includes("half")) {
    return "half";
  } else if (lower.includes("10k") || lower.includes("10公里")) {
    return "10k";
  } else if (lower.includes("5k") || lower.includes("5公里")) {
    return "5k";
  } else if (lower.includes("马拉松") || lower.includes("全马") || lower.includes("全程") || lower.includes("marathon")) {
    return "marathon";
  }
  return null;
}

function onRaceNameInput() {
  const detected = autoDetectRaceType(targetRace.value);
  if (detected) {
    raceType.value = detected;
  }
}

function setCategory(type: string) {
  raceType.value = type;
}

function applyPreset(p: any) {
  targetRace.value = p.race;
  targetTime.value = p.time;
  raceType.value = p.type;
}

const defaultAnalysis = {
  summary: "欢迎来到 Canova教练专区！绑定 Garmin 或高驰手表后将自动生成您的专属报告。",
  fitness_status: "系统将基于您的每日配速、静息心率与夜间 HRV 恢复状态，智能量化评估专项耐力与疲劳水平。",
  periodization_phase: "准备启动期 (Preparation)",
  key_suggestions: [
    "在【我的】页面绑定您的 Garmin 或高驰账号，开启历史运动与每日生理指标同步。",
    "以轻松跑 (Zone 2) 为主积累有氧基线，建立慢肌纤维毛细血管网。",
    "保持科学作息，长跑后注意水分电解质补充与睡眠恢复。"
  ],
  focus_workout_of_the_week: "基础有氧建立：轻松跑 30~45 分钟，心率控制在最大心率的 65%~75% 之间。",
  recovery_advice: "夜间保证 7~8 小时高质量睡眠，观察晨起静息心率变化，建立稳定生理基线。",
  multi_race_strategy: {
    macro_cycle_overview: "基于您的赛季目标与生理恢复基线，系统已构建多维度宏观备赛周期。核心原则是保 A 标突破、用 B 标实战质检、用 C 标作为基础有氧模拟拉练。",
    race_timeline_advice: [
      {
        id: "race-1",
        race_name: "武功山 50K",
        days_left: 60,
        tier: "A",
        tactical_role: "A 标核心突破 (Goal Race)",
        pacing_strategy: "前程爬升克制在有氧阈值 (Zone 2) 75% 心率上限以内，杜绝乳酸过早堆积；中后程山脊跑段切换巡航配速，下坡注意技术动作缓冲与股四头肌离心负荷控制。",
        taper_recovery_rule: "赛前 21 天开启阶段性减量：倒数第 3 周总跑量削减 20%，倒数第 2 周削减 40%，赛前周仅保留低心率调整跑与短冲刺神经激活，超量补偿碳水糖原储量。"
      }
    ],
    conflict_resolution: "若多场赛事间隔小于 3 周，严禁连续安排高强度全力拼搏；B/C 标赛事后必须安排 5~7 天低心率恢复窗口，避免神经肌肉系统累积隐性疲劳。"
  }
};

const user = ref<UserProfile | null>(null);
const analysis = ref<any>(defaultAnalysis);
const loading = ref(false);
const updatingPriority = ref<string>("");
const userRaces = ref<any[]>([]);

const athleteInfo = computed(() => analysis.value?.athlete_snapshot || {});
const tsbMetrics = computed(() => analysis.value?.tsb_metrics || {});

const tsbClass = computed(() => {
  const val = tsbMetrics.value?.tsb ?? 0;
  if (val > 15) return "tsb-fresh";
  if (val >= -10) return "tsb-neutral";
  if (val >= -30) return "tsb-optimal";
  if (val >= -45) return "tsb-fatigued";
  return "tsb-danger";
});

function isCurrentTarget(r: any): boolean {
  if (!r) return false;
  const name = r.race_name || r.name;
  if (!name || !targetRace.value) return false;
  return targetRace.value === name || targetRace.value.includes(name) || name.includes(targetRace.value);
}

async function loadLatestReport() {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    const rRes = await request(`/api/profile/${uid}/races`);
    if (Array.isArray(rRes)) {
      userRaces.value = rRes;
    } else if (rRes && Array.isArray(rRes.races)) {
      userRaces.value = rRes.races;
    }
  } catch (e) {
    console.warn("Fetch user races fallback:", e);
  }

  try {
    const res = await request(`/api/coach/latest/${uid}`);
    if (res && res.summary) {
      if (!res.multi_race_strategy) {
        res.multi_race_strategy = { ...defaultAnalysis.multi_race_strategy };
      }
      analysis.value = res;
      if (res.athlete_snapshot?.target_race) {
        targetRace.value = res.athlete_snapshot.target_race;
      }
      if (res.athlete_snapshot?.target_time) {
        targetTime.value = res.athlete_snapshot.target_time;
      }
      if (res.athlete_snapshot?.race_category) {
        raceType.value = res.athlete_snapshot.race_category;
      }
    }
  } catch (e) {
    console.warn("Fetch coach report fallback:", e);
  }

  // Ensure race_timeline_advice is populated if user has registered races
  if (analysis.value && analysis.value.multi_race_strategy) {
    const advice = analysis.value.multi_race_strategy.race_timeline_advice;
    if ((!advice || advice.length === 0) && userRaces.value.length > 0) {
      analysis.value.multi_race_strategy.race_timeline_advice = userRaces.value.map((r: any) => {
        const isA = r.priority == 1 || r.priority === 'A';
        const isB = r.priority == 2 || r.priority === 'B';
        const tier = isA ? 'A' : isB ? 'B' : 'C';
        return {
          id: r.id || r.name,
          race_name: r.name,
          days_left: r.days_left,
          tier,
          tactical_role: isA ? 'A 标核心突破 (Goal Race)' : isB ? 'B 标以赛代练 (Tune-up Test)' : 'C 标模拟拉练 (Training Run)',
          pacing_strategy: isA ? '前程严格控制在目标配速/心率储备 75% 内，杜绝乳酸过早堆积，后程根据体能稳步释放。' : isB ? '以 98%~100% 目标巡航配速实战质检，检验补给与心率门槛，无需拼尽全力。' : '作为周末长距离有氧基础跑，完全以轻松安全完赛为主，低生理负荷。',
          taper_recovery_rule: isA ? '赛前 14~21 天开启阶段性阶梯减量，大幅削减跑量保持强度，超量补偿糖原。' : isB ? '赛前微调减量 3 天，赛后安排 4~5 天低心率慢跑排酸。' : '赛前无需深度减量，赛后正常拉伸休息即可。'
        };
      });
    }
  }

  if (recommendedRace.value) {
    if (
      !planRaceName.value ||
      userRaces.value.find((r: any) => r.name === planRaceName.value)?.status ===
        "completed"
    ) {
      planRaceName.value = recommendedRace.value.name;
      if (recommendedRace.value.target_time) {
        planTargetTime.value = recommendedRace.value.target_time;
      }
    }
  }
}

function handleSelectRegisteredRace(r: any) {
  targetRace.value = r.name;
  if (r.target_time) {
    targetTime.value = r.target_time;
  }
  if (r.race_type) {
    const rt = (r.race_type || "").toLowerCase();
    if (rt.includes("trail") || rt.includes("越野")) raceType.value = "trail";
    else if (rt.includes("half") || rt.includes("半")) raceType.value = "half";
    else if (rt.includes("10k")) raceType.value = "10k";
    else raceType.value = "marathon";
  }
}

function handleSelectTargetRace(r: any) {
  const raceName = r.race_name || r.name;
  if (!raceName) return;
  targetRace.value = raceName;
  const matching = userRaces.value.find((ur: any) => ur.name === raceName || ur.race_name === raceName);
  if (matching) {
    if (matching.target_time) targetTime.value = matching.target_time;
    if (matching.race_type) {
      const rt = String(matching.race_type).toLowerCase();
      if (rt.includes("越野") || rt.includes("trail") || rt.includes("50k") || rt.includes("100k") || rt.includes("160")) {
        raceType.value = "trail";
      } else if (rt.includes("半")) {
        raceType.value = "half";
      } else if (rt.includes("10")) {
        raceType.value = "10k";
      } else if (rt.includes("5")) {
        raceType.value = "5k";
      } else {
        raceType.value = "marathon";
      }
    }
  }
  handleReAnalyze();
}

async function handleUpdatePriority(raceIdentifier: string, priority: string) {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  updatingPriority.value = raceIdentifier;
  uni.showLoading({ title: "战术重排推演中..." });
  try {
    const res = await request("/api/coach/race-priority", "POST", {
      uid,
      race_identifier: raceIdentifier,
      priority,
      target_race: targetRace.value
    });
    uni.hideLoading();
    if (res && res.multi_race_strategy) {
      analysis.value = {
        ...analysis.value,
        multi_race_analysis: res.multi_race_analysis,
        multi_race_strategy: res.multi_race_strategy,
      };
      if (res.races) {
        userRaces.value = res.races;
      }
      uni.showToast({ title: "战术推演已重排", icon: "success" });
    } else {
      uni.showToast({ title: "已更新赛事定位", icon: "success" });
    }
  } catch (err) {
    uni.hideLoading();
    uni.showToast({ title: "更新失败", icon: "none" });
  } finally {
    updatingPriority.value = "";
  }
}

async function handleReAnalyze() {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) {
    uni.showToast({ title: "请先在【我的】页面登录", icon: "none" });
    return;
  }
  const uid = user.value.id;

  loading.value = true;
  uni.showLoading({ title: "生理模型测算中..." });

  try {
    const res = await request("/api/coach/analysis", "POST", {
      uid,
      target_race: targetRace.value,
      target_time: targetTime.value,
      race_type: raceType.value
    });
    uni.hideLoading();
    if (res && res.summary) {
      analysis.value = res;
      uni.showToast({ title: "诊断报告已更新", icon: "success" });
    } else {
      uni.showToast({ title: "暂未生成诊断，请稍后重试", icon: "none" });
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: e?.message || "诊断生成失败，请检查网络后重试", icon: "none" });
  } finally {
    loading.value = false;
  }
}

function formatWorkout(w: any): string {
  if (!w) return "暂无个性化关键课建议（同步更多跑步记录后可生成）";
  if (typeof w === "string") return w;
  if (typeof w === "object") {
    return Object.entries(w).map(([k, v]) => `【${k}】${v}`).join("\n");
  }
  return String(w);
}

function formatAdvice(w: any): string {
  if (!w) return "暂无个性化恢复建议（同步更多跑步记录后可生成）";
  if (typeof w === "string") return w;
  if (typeof w === "object") {
    return Object.entries(w).map(([k, v]) => `【${k}】${typeof v === "object" ? JSON.stringify(v) : v}`).join("\n");
  }
  return String(w);
}

onMounted(() => {
  loadUserPlan();
});

onShow(() => {
  applySystemTheme(currentTheme.value);
  syncTabBarIndex(1);
  loadLatestReport();
  loadUserPlan();
});

onPullDownRefresh(async () => {
  try {
    await Promise.all([loadLatestReport(), loadUserPlan()]);
    uni.showToast({ title: "数据已刷新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新状态", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});

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
/* ── 微信审核合规：显著标注 AI 生成内容（符合《人工智能生成合成内容标识办法》规范） ── */
.ai-prominent-notice-banner {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 9999rpx;
  padding: 12rpx 28rpx;
  margin: 0 auto 28rpx;
  width: fit-content;
}

.ai-notice-robot {
  font-size: 26rpx;
}

.ai-notice-txt {
  font-size: 24rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 500;
  letter-spacing: 0.5rpx;
}

.ai-content-indicator {
  display: inline-flex;
  align-items: center;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 9999rpx;
  padding: 6rpx 20rpx;
  margin-bottom: 20rpx;
}

.ai-indicator-text {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 600;
}

.ai-legal-disclaimer {
  padding: 32rpx 24rpx 60rpx;
  text-align: center;
}

.ai-legal-text {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
  line-height: 1.6;
}

.coach-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  padding: 24rpx 28rpx calc(130rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(130rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.coach-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.header-left {
  flex: 1;
  margin-right: 20rpx;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.title-icon {
  font-size: 36rpx;
  color: var(--rgm-brand-text, #bf5af2);
}

.page-title {
  font-size: 34rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}


.re-analyze-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #af52de 0%, #8e44ad 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 24rpx;
  font-weight: bold;
  padding: 0 24rpx;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 32rpx;
  border: none;
  box-shadow: 0 6rpx 16rpx var(--rgm-brand-glow, rgba(175, 82, 222, 0.3));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.btn-text {
  font-size: 24rpx;
}

.content-box {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

/* ── PROFILE & TSB CARD ── */
.profile-card {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.25));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.profile-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.profile-name {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.profile-meta {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
  display: block;
}

.tsb-badge {
  padding: 6rpx 18rpx;
  border-radius: 24rpx;
  border: 1rpx solid transparent;
}

.tsb-badge-text {
  font-size: 20rpx;
  font-weight: bold;
}

.tsb-fresh {
  background-color: rgba(48, 209, 88, 0.15);
  border-color: rgba(48, 209, 88, 0.3);
  color: var(--rgm-green, #30d158);
}

.tsb-neutral {
  background-color: rgba(100, 210, 255, 0.15);
  border-color: rgba(100, 210, 255, 0.3);
  color: var(--rgm-blue, #64d2ff);
}

.tsb-optimal {
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.15));
  border-color: var(--rgm-brand-line, rgba(175, 82, 222, 0.3));
  color: var(--rgm-brand-text, #d084f7);
}

.tsb-fatigued {
  background-color: rgba(255, 159, 10, 0.15);
  border-color: rgba(255, 159, 10, 0.3);
  color: var(--rgm-amber, #ff9f0a);
}

.tsb-danger {
  background-color: rgba(255, 69, 58, 0.15);
  border-color: rgba(255, 69, 58, 0.3);
  color: var(--rgm-red, #ff453a);
}

.tsb-grid {
  display: flex;
  gap: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
}

.tsb-item {
  flex: 1;
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 18rpx;
  padding: 16rpx 12rpx;
  text-align: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tsb-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  display: block;
  margin-bottom: 4rpx;
}

.tsb-val {
  font-size: 28rpx;
  font-weight: 900;
  display: block;
}

.text-cyan { color: var(--rgm-blue, #64d2ff); }
.text-amber { color: var(--rgm-amber, #ff9f0a); }
.text-green { color: var(--rgm-green, #30d158); }
.text-purple { color: var(--rgm-brand-text, #bf5af2); }

.risk-box {
  margin-top: 18rpx;
  background-color: rgba(255, 69, 58, 0.1);
  border: 1rpx solid rgba(255, 69, 58, 0.25);
  border-radius: 18rpx;
  padding: 16rpx;
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
}

.risk-icon {
  font-size: 24rpx;
}

.risk-text {
  font-size: 22rpx;
  color: var(--rgm-red, #ffb4ab);
  line-height: 1.4;
  flex: 1;
}

/* ── RACE SETUP CARD ── */
.race-setup-card {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.25));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.presets-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.preset-chip {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  padding: 8rpx 20rpx;
  border-radius: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.preset-chip.active {
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.25));
  border-color: var(--rgm-brand, #af52de);
}

.chip-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #c7c7cc);
}

.preset-chip.active .chip-text {
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

/* 🏆 Target Race Completed Switch Banner */
.plan-switch-banner {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(251, 191, 36, 0.12) 0%, rgba(175, 82, 222, 0.12) 100%));
  border: 1rpx solid rgba(251, 191, 36, 0.35);
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.banner-top-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.banner-badge {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-amber, #fbbf24);
  background: rgba(251, 191, 36, 0.2);
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
}

.banner-sub {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #c084fc);
  font-weight: 600;
}

.banner-desc {
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.5;
}

.banner-switch-btn {
  background: var(--rgm-brand, #9333ea);
  color: var(--rgm-text, #ffffff);
  font-size: 22rpx;
  font-weight: bold;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 14rpx;
  border: none;
  margin-top: 6rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.banner-switch-btn:active {
  background: var(--rgm-brand, #7e22ce);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* Registered User Races */
.registered-races-row {
  margin-top: 14rpx;
  margin-bottom: 18rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.registered-label {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  display: block;
  margin-bottom: 10rpx;
}

.registered-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.reg-chip {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.reg-chip.is-done {
  opacity: 0.45;
  text-decoration: line-through;
}

.reg-chip.is-a {
  border-color: rgba(251, 191, 36, 0.4);
  background: rgba(251, 191, 36, 0.08);
}

.reg-chip.active {
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.2));
  border-color: var(--rgm-brand, #af52de);
}

.reg-chip-tier {
  font-size: 18rpx;
  font-weight: bold;
  padding: 2rpx 8rpx;
  border-radius: 8rpx;
}

.reg-chip-tier.tier-done {
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text-3, #71717a);
}

.reg-chip-tier.tier-a {
  background-color: rgba(251, 191, 36, 0.25);
  color: var(--rgm-amber, #fbbf24);
}

.reg-chip-tier.tier-b {
  background-color: rgba(56, 189, 248, 0.25);
  color: var(--rgm-blue, #38bdf8);
}

.reg-chip-tier.tier-c {
  background-color: rgba(161, 161, 170, 0.25);
  color: var(--rgm-text-2, #d4d4d8);
}

.reg-chip-name {
  font-size: 22rpx;
  color: var(--rgm-text, #f3f4f6);
}

.reg-chip.active .reg-chip-name {
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

.reg-chip-days {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #c084fc);
}

.inputs-row {
  display: flex;
  gap: 16rpx;
}

.input-col {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.flex-2 { flex: 2; }
.flex-1 { flex: 1; }

.input-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.setup-input {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  height: 64rpx;
  padding: 0 16rpx;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.race-type-pills-row {
  margin-top: 16rpx;
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.type-pills {
  display: flex;
  gap: 10rpx;
  flex: 1;
}

.type-pill {
  flex: 1;
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 14rpx;
  padding: 10rpx 0;
  text-align: center;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.type-pill.active {
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.25));
  border-color: var(--rgm-brand, #af52de);
}

.type-pill .pill-text {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 500;
}

.type-pill.active .pill-text {
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
}

/* ── ZONES LIST ── */
.zones-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.zone-item {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 18rpx;
  padding: 18rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.zone-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6rpx;
}

.zone-name {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-text, #e5e5ea);
}

.zone-range {
  font-size: 24rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #d084f7);
}


.hero-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(175, 82, 222, 0.2) 0%, #151518 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.3));
  border-radius: 28rpx;
  padding: 32rpx;
  box-shadow: 0 10rpx 30rpx var(--rgm-shadow, rgba(0, 0, 0, 0.5));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.phase-badge {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.2));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.3));
  padding: 6rpx 18rpx;
  border-radius: 20rpx;
  margin-bottom: 20rpx;
}

.sparkle {
  font-size: 20rpx;
}

.phase-text {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #d084f7);
}

.summary-title {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  line-height: 1.4;
  margin-bottom: 16rpx;
  display: block;
}

.fitness-detail {
  font-size: 24rpx;
  color: var(--rgm-text-2, #c7c7cc);
  line-height: 1.6;
  display: block;
}

.section-card {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  border-radius: 28rpx;
  padding: 28rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.section-icon {
  font-size: 28rpx;
}

.card-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.workout-box {
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.1));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.2));
  border-radius: 20rpx;
  padding: 22rpx;
}

.workout-text {
  font-size: 26rpx;
  color: var(--rgm-text-2, #e5c9f9);
  line-height: 1.5;
}

.recovery-box {
  background-color: rgba(48, 209, 88, 0.1);
  border: 1rpx solid rgba(48, 209, 88, 0.2);
  border-radius: 20rpx;
  padding: 22rpx;
}

.recovery-text {
  font-size: 26rpx;
  color: var(--rgm-text, #bdf2cc);
  line-height: 1.5;
}

.tip-footnote {
  font-size: 20rpx;
  color: var(--rgm-text-3, #636366);
  margin-top: 14rpx;
  display: block;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.sugg-item {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 18rpx;
  padding: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.sugg-badge {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #bf5af2);
  margin-bottom: 8rpx;
  display: block;
}

.sugg-text {
  font-size: 24rpx;
  color: var(--rgm-text, #e5e5ea);
  line-height: 1.5;
}

.multi-race-card {
  border-left: 6rpx solid var(--rgm-brand, #bf5af2);
  border-color: var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.multi-race-header {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  padding-bottom: 20rpx;
  margin-bottom: 22rpx;
}


.total-races-badge {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.12));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.25));
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  align-self: flex-start;
}

.sparkle-icon {
  font-size: 20rpx;
}

.total-races-text {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #d8b4fe);
  font-weight: 600;
}

.macrocycle-box {
  background: var(--rgm-card, linear-gradient(135deg, rgba(88, 28, 135, 0.3) 0%, rgba(24, 24, 28, 0.95) 50%, rgba(49, 46, 129, 0.25) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(191, 90, 242, 0.25));
  border-radius: 20rpx;
  padding: 22rpx;
  margin-bottom: 26rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.macrocycle-header {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 8rpx;
}

.macrocycle-icon {
  font-size: 24rpx;
}

.macrocycle-label {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #d8b4fe);
}

.macrocycle-text {
  font-size: 24rpx;
  color: var(--rgm-text, #f3f4f6);
  line-height: 1.6;
  display: block;
}

.timeline-section {
  margin-bottom: 20rpx;
}

.timeline-section-title {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text-2, #a1a1aa);
  letter-spacing: 1rpx;
  text-transform: uppercase;
  margin-bottom: 16rpx;
  display: block;
}

.race-timeline-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.race-item {
  background-color: var(--rgm-card, #18181c);
  border-radius: 24rpx;
  padding: 22rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  transition: all 0.3s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.race-item.tier-a {
  border-color: rgba(244, 63, 94, 0.45);
  background-color: var(--rgm-card, rgba(32, 18, 24, 0.95));
  box-shadow: 0 6rpx 24rpx rgba(244, 63, 94, 0.1);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.race-item.tier-b {
  border-color: rgba(56, 189, 248, 0.35);
  background-color: var(--rgm-card, rgba(18, 26, 32, 0.95));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.race-item.tier-c {
  border-color: var(--rgm-line, rgba(255, 255, 255, 0.08));
  background-color: var(--rgm-card, #18181c);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.race-item-header {
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  padding-bottom: 16rpx;
  margin-bottom: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.race-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10rpx;
}

.race-title-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}

.race-tier-badge {
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  font-size: 20rpx;
  font-weight: 900;
  border: 1rpx solid transparent;
}

.badge-a {
  background-color: rgba(244, 63, 94, 0.2);
  color: var(--rgm-red, #fda4af);
  border-color: rgba(244, 63, 94, 0.45);
}

.badge-b {
  background-color: rgba(56, 189, 248, 0.2);
  color: var(--rgm-blue, #7dd3fc);
  border-color: rgba(56, 189, 248, 0.4);
}

.badge-c {
  background-color: rgba(161, 161, 170, 0.2);
  color: var(--rgm-text-2, #d4d4d8);
  border-color: rgba(161, 161, 170, 0.4);
}

.badge-text {
  font-size: 20rpx;
}

.race-item-name {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.race-days-countdown {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 500;
}

.days-num {
  color: var(--rgm-brand-text, #d8b4fe);
  font-weight: 900;
}

.priority-switch-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  background-color: var(--rgm-card, #121215);
  padding: 10rpx 14rpx;
  border-radius: 16rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.priority-left-group {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-wrap: wrap;
}

.switch-tip-lbl {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
  font-weight: bold;
}

.priority-btns {
  display: flex;
  gap: 8rpx;
}

.p-btn {
  margin: 0;
  padding: 4rpx 14rpx;
  height: 44rpx;
  line-height: 44rpx;
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-text-2, #a1a1aa);
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 10rpx;
}

.p-btn::after {
  border: none;
}

.p-btn-a.active {
  background-color: #f43f5e;
  color: var(--rgm-text, #ffffff);
  border-color: #fb7185;
  box-shadow: 0 2rpx 10rpx rgba(244, 63, 94, 0.4);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.p-btn-b.active {
  background-color: var(--rgm-brand, #0284c7);
  color: var(--rgm-text, #ffffff);
  border-color: var(--rgm-brand, #38bdf8);
  box-shadow: 0 2rpx 10rpx rgba(56, 189, 248, 0.4);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.p-btn-c.active {
  background-color: #52525b;
  color: var(--rgm-text, #ffffff);
  border-color: #71717a;
  box-shadow: 0 2rpx 10rpx rgba(113, 113, 122, 0.4);
}

.set-target-btn {
  margin: 0;
  padding: 4rpx 14rpx;
  height: 44rpx;
  line-height: 44rpx;
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-text-2, #a1a1aa);
  background-color: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 12rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.set-target-btn::after {
  border: none;
}

.set-target-btn.is-active-target {
  background-color: var(--rgm-brand-tint, rgba(147, 51, 234, 0.25));
  color: var(--rgm-text, #e9d5ff);
  border-color: var(--rgm-brand, #a855f7);
}

.race-execution-boxes {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.exec-box {
  background-color: var(--rgm-card, #121215);
  padding: 16rpx 18rpx;
  border-radius: 16rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.exec-box-title {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 6rpx;
}

.exec-icon {
  font-size: 22rpx;
}

.exec-label {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text-2, #a1a1aa);
}

.exec-desc {
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.5;
  font-weight: 300;
  display: block;
}

.conflict-box {
  background-color: rgba(245, 158, 11, 0.08);
  border: 1rpx solid rgba(245, 158, 11, 0.3);
  border-radius: 20rpx;
  padding: 20rpx;
}

.conflict-title-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 8rpx;
}

.conflict-icon {
  font-size: 24rpx;
}

.conflict-title {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-amber, #fbbf24);
}

.conflict-desc {
  font-size: 22rpx;
  color: var(--rgm-text, #fef3c7);
  line-height: 1.5;
  font-weight: 300;
  display: block;
}

.empty-card {
  background-color: var(--rgm-card, #151518);
  border-radius: 28rpx;
  padding: 60rpx 40rpx;
  text-align: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.empty-icon {
  font-size: 60rpx;
  margin-bottom: 20rpx;
  display: block;
}

.empty-title {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 12rpx;
  display: block;
}

.empty-desc {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.5;
  margin-bottom: 30rpx;
  display: block;
}

.primary-btn {
  background-color: var(--rgm-brand, #af52de);
  color: var(--rgm-text, #ffffff);
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 24rpx;
  height: 80rpx;
  line-height: 80rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── TAB BAR ── */
.coach-tab-bar {
  display: flex;
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 8rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.coach-tab-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  padding: 16rpx 0;
  border-radius: 16rpx;
  transition: all 0.2s ease;
}

.coach-tab-item.active {
  background-color: var(--rgm-brand, #af52de);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.coach-tab-item .tab-icon {
  font-size: 28rpx;
}

.coach-tab-item .tab-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text-3, #8e8e93);
}

.coach-tab-item.active .tab-title {
  color: var(--rgm-text, #ffffff);
}

/* ── PLAN TOP BAR ── */
.plan-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
  gap: 16rpx;
}

.plan-title-box {
  flex: 1;
}

.plan-main-title {
  font-size: 30rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.plan-status-pills-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 6rpx;
}

.plan-status-pill {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-green, #30d158);
  background-color: rgba(48, 209, 88, 0.15);
  border: 1rpx solid rgba(48, 209, 88, 0.3);
  border-radius: 12rpx;
  padding: 2rpx 10rpx;
  display: inline-block;
}

.plan-coach-verified-pill {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-amber, #fbbf24);
  background-color: rgba(251, 191, 36, 0.15);
  border: 1rpx solid rgba(251, 191, 36, 0.4);
  border-radius: 12rpx;
  padding: 2rpx 12rpx;
  display: inline-block;
}

.coach-review-note-box {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.12) 0%, rgba(252, 76, 2, 0.08) 100%);
  border: 1rpx solid rgba(251, 191, 36, 0.35);
  border-radius: 20rpx;
  padding: 18rpx 20rpx;
  margin-bottom: 20rpx;
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
}

.crn-icon {
  font-size: 32rpx;
  flex-shrink: 0;
}

.crn-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.crn-title {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-amber, #fbbf24);
}

.crn-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #e4e4e7);
  line-height: 1.5;
}

.plan-config-toggle-btn {
  background-color: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 18rpx;
  padding: 0 20rpx;
  height: 60rpx;
  line-height: 60rpx;
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d1d6);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── PLAN SETUP CARD ── */
.plan-setup-card {
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.3));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.25));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.setup-hint {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #af52de);
  margin-bottom: 20rpx;
  display: block;
}

.goal-type-toggle-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.goal-type-btn {
  flex: 1;
  background-color: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 18rpx 14rpx;
  text-align: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.goal-type-btn.active {
  border-color: var(--rgm-brand, #af52de);
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.15));
}

.goal-btn-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}


.maint-chips-grid {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-top: 10rpx;
  margin-bottom: 20rpx;
}

.maint-chip {
  background-color: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  padding: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.maint-chip.active {
  background-color: rgba(48, 209, 88, 0.15);
  border-color: #30d158;
}

.maint-name {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.maint-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
  display: block;
}

.picker-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.picker-col {
  flex: 1;
  min-width: 0;
}

.wheel-stepper-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 16rpx;
  height: 76rpx;
  margin-top: 8rpx;
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.ws-step-btn {
  width: 68rpx;
  height: 76rpx;
  line-height: 76rpx;
  text-align: center;
  font-size: 32rpx;
  font-weight: 800;
  color: var(--rgm-brand-text, #af52de);
  background-color: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  flex-shrink: 0;
}

.ws-step-btn:active {
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.2));
}

.ws-picker-mid {
  flex: 1;
  height: 76rpx;
}

.ws-picker-val-wrap {
  height: 76rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
}

.ws-picker-val {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
}

.ws-picker-caret {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

/* ── SNAPSHOT CARD ── */
.snapshot-card {
  display: flex;
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  justify-content: space-between;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.snap-item {
  flex: 1;
  text-align: center;
}

.snap-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  display: block;
}

.snap-val {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin: 4rpx 0;
  display: block;
}

.snap-sub {
  font-size: 18rpx;
  color: var(--rgm-text-3, #636366);
  display: block;
}

.overview-box {
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.08));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.2));
  border-radius: 20rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 20rpx;
  display: flex;
  gap: 10rpx;
}

.overview-icon {
  font-size: 28rpx;
}

.overview-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d1d6);
  line-height: 1.5;
  flex: 1;
}

/* ── WEEK SCROLL VIEW ── */
.week-scroll-view {
  white-space: nowrap;
  margin-bottom: 20rpx;
}

.week-chips-row {
  display: inline-flex;
  gap: 14rpx;
}

.week-chip {
  display: inline-flex;
  flex-direction: column;
  padding: 16rpx 22rpx;
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  min-width: 160rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.week-chip.active {
  background-color: var(--rgm-brand, #af52de);
  border-color: var(--rgm-brand, #af52de);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.week-chip.is-current-week:not(.active) {
  border-color: var(--rgm-brand-line, rgba(175, 82, 222, 0.5));
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.08));
}

.chip-title-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.current-week-tag {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #af52de);
  background: var(--rgm-brand-tint, rgba(175, 82, 222, 0.16));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.35));
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: 700;
  line-height: 1.2;
}

.week-chip.active .current-week-tag {
  color: var(--rgm-text, #ffffff);
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.25));
  border-color: rgba(255, 255, 255, 0.4);
}

.week-chip-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.week-chip-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
}

.week-chip.active .week-chip-sub {
  color: var(--rgm-text-2, #e5c5f8);
}

/* ── ACTIVE WEEK HEADER ── */
.active-week-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.active-week-left {
  flex: 1;
}

.active-week-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.active-week-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.phase-tag {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #af52de);
  background-color: var(--rgm-brand-tint, rgba(175, 82, 222, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.3));
  border-radius: 10rpx;
  padding: 2rpx 8rpx;
}

.focus-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #aeaeb2);
  margin-top: 6rpx;
  display: block;
}

.week-summary-banner-line {
  font-size: 21rpx;
  color: var(--rgm-green, #34d399);
  margin-top: 6rpx;
  display: block;
  font-weight: 700;
}

.active-week-right {
  text-align: right;
}

.mileage-val {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.mileage-label {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
  display: block;
}

/* ── DAILY CARDS LIST ── */
.daily-cards-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.daily-card {
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.daily-card.is-completed {
  border-color: rgba(48, 209, 88, 0.4);
  background-color: rgba(48, 209, 88, 0.03);
}

.daily-card.is-missed {
  border-color: rgba(255, 69, 58, 0.45);
  background: var(--rgm-card, linear-gradient(180deg, rgba(255, 69, 58, 0.1) 0%, rgba(20, 16, 18, 0.95) 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.badge-group {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-wrap: wrap;
}

.swap-pill {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 8rpx;
  background: rgba(59, 130, 246, 0.16);
  color: var(--rgm-blue, #93c5fd);
  border: 1rpx solid rgba(59, 130, 246, 0.32);
  margin-left: 6rpx;
  font-weight: 700;
  white-space: nowrap;
}

.rpe-pill {
  font-size: 19rpx;
  padding: 4rpx 10rpx;
  border-radius: 10rpx;
  background: rgba(245, 158, 11, 0.18);
  color: var(--rgm-amber, #fcd34d);
  border: 1rpx solid rgba(245, 158, 11, 0.35);
  font-weight: 800;
  white-space: nowrap;
}

.rec-pill {
  font-size: 19rpx;
  padding: 4rpx 10rpx;
  border-radius: 10rpx;
  font-weight: 800;
  white-space: nowrap;
}

.rec-pill.rec-good {
  background: rgba(16, 185, 129, 0.16);
  color: var(--rgm-green, #6ee7b7);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
}

.rec-pill.rec-mid {
  background: rgba(245, 158, 11, 0.18);
  color: var(--rgm-amber, #fcd34d);
  border: 1rpx solid rgba(245, 158, 11, 0.38);
}

.rec-pill.rec-low {
  background: rgba(244, 63, 94, 0.16);
  color: var(--rgm-red, #fda4af);
  border: 1rpx solid rgba(244, 63, 94, 0.35);
}

.missed-badge {
  font-size: 18rpx;
  font-weight: bold;
  padding: 4rpx 10rpx;
  border-radius: 10rpx;
  background: rgba(255, 69, 58, 0.2);
  color: var(--rgm-red, #ff453a);
  border: 1rpx solid rgba(255, 69, 58, 0.4);
}

.actual-km-badge {
  font-size: 18rpx;
  font-weight: bold;
  padding: 4rpx 10rpx;
  border-radius: 10rpx;
  background: rgba(48, 209, 88, 0.15);
  color: var(--rgm-green, #30d158);
  border: 1rpx solid rgba(48, 209, 88, 0.3);
}

.daily-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.day-date-box {
  display: flex;
  align-items: baseline;
  gap: 10rpx;
}

.day-name {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.day-date {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.type-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
}

.badge-easy { background: rgba(48, 209, 88, 0.15); color: var(--rgm-green, #30d158); }
.badge-tempo { background: rgba(10, 132, 255, 0.15); color: var(--rgm-blue, #0a84ff); }
.badge-interval { background: rgba(255, 159, 10, 0.15); color: var(--rgm-amber, #ff9f0a); }
.badge-long { background: var(--rgm-brand-tint, rgba(175, 82, 222, 0.15)); color: var(--rgm-brand-text, #af52de); }
.badge-trail { background: rgba(94, 92, 230, 0.15); color: var(--rgm-blue, #5e5ce6); }
.badge-cross { background: rgba(255, 55, 95, 0.15); color: var(--rgm-red, #ff375f); }
.badge-race { background: rgba(255, 45, 85, 0.25); color: var(--rgm-red, #ff375f); border: 1rpx solid rgba(255, 45, 85, 0.4); font-weight: bold; }
.badge-rest { background: rgba(142, 142, 147, 0.15); color: var(--rgm-text-3, #8e8e93); }

.border-race { border-color: rgba(255, 45, 85, 0.45); background: var(--rgm-card, linear-gradient(180deg, rgba(255, 45, 85, 0.12) 0%, rgba(26, 26, 30, 0.95) 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3); }

.workout-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #e5e5ea);
  margin-bottom: 8rpx;
  display: block;
}

.dist-row {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
  margin-bottom: 10rpx;
}

.dist-val {
  font-size: 36rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.dist-unit {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.metrics-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 12rpx;
}

.metric-pill {
  font-size: 20rpx;
  font-weight: 500;
  color: var(--rgm-brand-text, #af52de);
  background-color: var(--rgm-card-2, #1c1c1e);
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.metric-pill.hr-pill {
  color: var(--rgm-green, #30d158);
}

.metric-pill.bio-warn-pill {
  background-color: rgba(244, 63, 94, 0.16);
  color: var(--rgm-red, #fda4af);
  border: 1rpx solid rgba(244, 63, 94, 0.35);
  font-weight: 700;
}

.metric-pill.exec-pill {
  background-color: rgba(16, 185, 129, 0.16);
  color: var(--rgm-green, #6ee7b7);
  border: 1rpx solid rgba(16, 185, 129, 0.38);
  font-weight: 700;
  max-width: 100%;
  box-sizing: border-box;
  word-break: break-word;
  line-height: 1.45;
}

.athlete-notes-box {
  margin-top: 10rpx;
  margin-bottom: 14rpx;
  padding: 12rpx 16rpx;
  border-radius: 14rpx;
  background-color: rgba(245, 158, 11, 0.12);
  border: 1rpx solid rgba(245, 158, 11, 0.28);
}

.athlete-notes-title {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-amber, #fcd34d);
}

.athlete-notes-content {
  font-size: 21rpx;
  color: var(--rgm-text, #fef3c7);
}

.workout-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #aeaeb2);
  line-height: 1.4;
  margin-bottom: 14rpx;
  display: block;
}

.coach-notes-box {
  background-color: rgba(255, 159, 10, 0.1);
  border: 1rpx solid rgba(255, 159, 10, 0.25);
  border-radius: 16rpx;
  padding: 12rpx 16rpx;
  margin-bottom: 14rpx;
}

.coach-notes-title {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-amber, #ff9f0a);
  display: block;
  margin-bottom: 4rpx;
}

.coach-notes-content {
  font-size: 20rpx;
  color: var(--rgm-amber, #ffe0b2);
  line-height: 1.3;
  display: block;
}

.daily-card-actions {
  display: flex;
  gap: 12rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  padding-top: 14rpx;
}

.action-complete-btn {
  flex: 1;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 14rpx;
  background-color: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.action-complete-btn.completed {
  background-color: rgba(48, 209, 88, 0.2);
  border-color: #30d158;
  color: var(--rgm-green, #30d158);
  font-weight: bold;
}

.action-complete-btn.missed {
  background-color: rgba(255, 69, 58, 0.18);
  border-color: rgba(255, 69, 58, 0.5);
  color: var(--rgm-red, #ff453a);
  font-weight: bold;
}

.action-edit-btn {
  height: 56rpx;
  line-height: 56rpx;
  padding: 0 24rpx;
  border-radius: 14rpx;
  background-color: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  font-size: 22rpx;
  color: var(--rgm-brand-text, #af52de);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── MODAL MASK & CARD ── */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 30rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.modal-card {
  background-color: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 32rpx;
  width: 100%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  padding: 30rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  padding-bottom: 16rpx;
  margin-bottom: 20rpx;
}

.modal-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.modal-close {
  font-size: 32rpx;
  color: var(--rgm-text-3, #8e8e93);
  padding: 0 10rpx;
}

.modal-scroll-body {
  max-height: 55vh;
  margin-bottom: 20rpx;
}

.modal-input-group {
  margin-bottom: 18rpx;
}

.modal-label {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-bottom: 8rpx;
  display: block;
}

.modal-input {
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  height: 64rpx;
  padding: 0 18rpx;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-row {
  display: flex;
  gap: 16rpx;
}

.modal-textarea {
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  width: 100%;
  height: 120rpx;
  padding: 14rpx 18rpx;
  font-size: 22rpx;
  color: var(--rgm-text, #ffffff);
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.coach-notes-group {
  background-color: rgba(255, 159, 10, 0.06);
  border: 1rpx solid rgba(255, 159, 10, 0.2);
  border-radius: 20rpx;
  padding: 16rpx;
}

.coach-textarea {
  color: var(--rgm-amber, #ffe0b2);
}

.modal-footer {
  display: flex;
  gap: 16rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  padding-top: 20rpx;
}

.modal-cancel-btn {
  flex: 1;
  background-color: var(--rgm-card-2, #1c1c1e);
  color: var(--rgm-text-3, #8e8e93);
  font-size: 26rpx;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-save-btn {
  flex: 2;
  background-color: var(--rgm-brand, #af52de);
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── GOAL ALIGNMENT & SYNC STYLES ── */
.goal-anchor-box {
  background: var(--rgm-brand-tint, rgba(175, 82, 222, 0.1));
  border: 1rpx solid var(--rgm-brand-line, rgba(175, 82, 222, 0.25));
  border-radius: 20rpx;
  padding: 16rpx 20rpx;
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 24rpx;
}
.anchor-icon {
  font-size: 28rpx;
}
.anchor-text {
  font-size: 22rpx;
  color: var(--rgm-text, #e9d5ff);
  line-height: 1.4;
}

.week-alignment-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14rpx;
  margin-bottom: 20rpx;
  gap: 16rpx;
}

.align-pill {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 10rpx 16rpx;
  border-radius: 20rpx;
  font-size: 20rpx;
  border-width: 1rpx;
  border-style: solid;
}

.align-good {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.3);
  color: var(--rgm-green, #6ee7b7);
}

.align-down {
  background: rgba(14, 165, 233, 0.12);
  border-color: rgba(14, 165, 233, 0.3);
  color: var(--rgm-blue, #7dd3fc);
}

.align-race {
  background: rgba(244, 63, 94, 0.12);
  border-color: rgba(244, 63, 94, 0.35);
  color: var(--rgm-red, #fda4af);
}

.align-climb {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.3);
  color: var(--rgm-amber, #fcd34d);
}

.align-icon {
  font-size: 22rpx;
}

.align-status-title {
  font-weight: bold;
}

.align-status-detail {
  font-size: 18rpx;
  opacity: 0.85;
}

.sync-goal-mini-btn {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(147, 51, 234, 0.3), rgba(79, 70, 229, 0.3)));
  border: 1rpx solid var(--rgm-brand-line, rgba(168, 85, 247, 0.4));
  border-radius: 20rpx;
  height: 52rpx;
  line-height: 52rpx;
  padding: 0 18rpx;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sync-mini-btn-text {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #d8b4fe);
}

</style>
