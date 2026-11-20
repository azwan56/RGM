<template>
  <view class="coach-page coach-v3" :class="[themeClass, { 'has-preview-bar': isPreviewPlan }]">
    <!-- ── 极简顶栏二合一：[ 课表 | 体能 ] + 定制滑块 ── -->
    <view class="c3-topbar">
      <view class="rgm-seg-bar c3-seg">
        <view class="rgm-seg-item" :class="{ active: activeTab === 'plan' }" @click="activeTab = 'plan'">
          <text>课表</text>
        </view>
        <view class="rgm-seg-item" :class="{ active: activeTab === 'analysis' }" @click="activeTab = 'analysis'">
          <text>体能</text>
        </view>
      </view>

      <view class="c3-top-actions">
        <view class="rgm-icon-btn" :class="{ active: showPlanConfig }" @click="showPlanConfig = !showPlanConfig">
          <RgmIcon name="sliders" :size="32" :color="showPlanConfig ? 'brand' : 'text2'" />
        </view>
      </view>
    </view>

    <!-- ── PLAN TAB CONTENT ── -->
    <view v-if="activeTab === 'plan'" class="plan-tab-section">
      <!-- 夜间未佩戴手表单行提示 -->
      <view
        v-if="recoveryDataAvailability?.night_wear_missing || analysis?.recovery_data_availability?.night_wear_missing"
        class="c3-wear-warn"
        @click.stop="explainTerm('watch_wear')"
      >
        <view class="c3-wear-left">
          <RgmIcon name="alert" :size="24" color="amber" />
          <text class="c3-wear-txt">{{ recoveryDataAvailability?.recovery_status_label || analysis?.recovery_data_availability?.recovery_status_label || '夜间未佩戴 · 恢复数据缺失' }}</text>
        </view>
        <text class="c3-wear-more">ⓘ</text>
      </view>

      <!-- 原目标已完赛提示条 -->
      <view v-if="plan && isTargetRaceCompleted && recommendedRace" class="c3-switch-banner">
        <view class="c3-sb-row">
          <text class="c3-sb-title">{{ plan.target_race_name }} 已完赛</text>
          <view class="c3-sb-actions">
            <text class="c3-sb-link" @click="openCompletedTargetRaceShareCard">喜报卡 ›</text>
            <text class="c3-sb-cta" @click="handleApplyRecommendedRace">切换 {{ recommendedRace.name }} ›</text>
          </view>
        </view>
      </view>

      <!-- 定制滑块抽屉（含回退、周月报与周期参数表单，默认收起） -->
      <view v-if="showPlanConfig || !plan" class="rgm-card c3-config-drawer">
        <view class="c3-cd-head">
          <view class="c3-cd-title-row">
            <text class="c3-cd-title">计划定制与工具</text>
            <text class="term-info" @click.stop="explainTerm('canova_model')">ⓘ</text>
          </view>
          <view class="c3-cd-tools">
            <text
              v-if="planBackups.length > 0 && !isPreviewPlan"
              class="c3-cd-pill"
              @click="handleRollbackUserPlan"
            >{{ rollingBackPlan ? '回退中' : '回退上版' }}</text>
            <text class="c3-cd-pill" @click="showCoachPersonalReport = true">周/月报</text>
            <text class="c3-cd-pill" @click="goToBodyData">体能档案 ›</text>
          </view>
        </view>

        <!-- Goal Type Toggle -->
        <view class="goal-type-toggle-row">
          <view
            class="goal-type-btn"
            :class="{ active: planGoalType === 'race_prep' }"
            @click="planGoalType = 'race_prep'"
          >
            <text class="goal-btn-title">赛事备战</text>
          </view>
          <view
            class="goal-type-btn"
            :class="{ active: planGoalType === 'fitness_maintenance' }"
            @click="planGoalType = 'fitness_maintenance'"
          >
            <text class="goal-btn-title">日常进阶</text>
          </view>
        </view>

        <view v-if="planGoalType === 'race_prep'" class="race-setup-inputs">
          <view v-if="userRaces.length" class="registered-races-row">
            <text class="registered-label">已登记赛事</text>
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
                <text class="reg-chip-tier tier-done" v-if="r.status === 'completed' || r.is_completed">已完赛</text>
                <text class="reg-chip-tier tier-a" v-else-if="r.priority == 1 || r.priority === 'A'">A标</text>
                <text class="reg-chip-tier tier-b" v-else-if="r.priority == 2 || r.priority === 'B'">B标</text>
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

        <view class="goal-anchor-box" @click="openCoachGoalSheet('week')">
          <RgmIcon name="gauge" :size="26" color="brand" />
          <text class="anchor-text">周目标基准：{{ userGoal?.next_weekly_target || userGoal?.weekly_target || 50 }} km/周</text>
          <text class="c3-anchor-edit">调整 ›</text>
        </view>

        <button class="primary-btn" :loading="generatingPlan" @click="handleGeneratePlan">
          <text class="btn-text">{{ generatingPlan ? '推演中...' : '生成新课表预览（AI生成）' }}</text>
        </button>
        <text class="ai-compliance-banner">✨ 提示：训练课表由 AI 生成（人工智能生成），仅供参考，请结合自身状态调整。</text>
      </view>

      <!-- Active Plan Body (L1 Tabs-1: 首卡目标微环 + 次卡8周阶梯柱 + 7日紧凑课表) -->
      <view v-if="plan && plan.schedule_data" class="c3-plan-body">
        <view class="ai-notice-strip">
          <text class="ai-notice-tag">AI生成</text>
          <text class="ai-notice-txt">本训练课表及复盘建议由人工智能（AI）生成，仅供参考</text>
        </view>
        <!-- 首卡：备赛目标 + 右侧空心进度环 -->
        <view class="rgm-card c3-goal-hero">
          <view class="c3-gh-left">
            <view class="c3-gh-top">
              <text class="c3-tier-tag">{{ heroTargetRaceInfo.tier }}</text>
              <text class="c3-race-title">{{ heroTargetRaceInfo.name }}</text>
              <text v-if="heroTargetRaceInfo.daysBadge" class="c3-days-pill">{{ heroTargetRaceInfo.daysBadge }}</text>
            </view>
            <view class="c3-gh-sub-row">
              <view class="c3-green-dot" />
              <text class="c3-gh-sub">
                {{ heroTargetRaceInfo.phase }}
                {{ heroTargetRaceInfo.targetTime ? ` · ${heroTargetRaceInfo.targetTime}` : '' }}
                {{ (plan.review_status === 'published' || plan.reviewed_by_name) ? ' · 教练已审' : '' }}
              </text>
            </view>
          </view>
          <view class="c3-ring-outer" :style="activeWeekRingStyle">
            <view class="c3-ring-hole">
              <text class="c3-ring-pct">{{ activeWeekCompliancePct }}%</text>
            </view>
          </view>
        </view>

        <!-- 次卡：8 周周期负荷阶梯柱（点选周次） -->
        <view class="rgm-card c3-ladder-card">
          <view class="c3-ladder-head">
            <text class="c3-ladder-title">周期负荷阶梯</text>
            <view class="c3-ladder-right">
              <text class="c3-ladder-km">W{{ selectedWeekIdx }} · {{ activeMiniWeek?.weekly_mileage_km || 0 }} km</text>
              <text class="c3-sync-chip" @click="handleSyncToGoals">{{ syncingGoal ? '同步中' : '同步目标' }}</text>
            </view>
          </view>

          <view class="c3-ladder-bars">
            <view
              v-for="wk in planWeeksLadder"
              :key="wk.week_index"
              class="c3-ladder-col"
              @click="selectWeek(wk.week_index)"
            >
              <view class="c3-ladder-stage">
                <view
                  class="c3-ladder-bar"
                  :class="wk.kind"
                  :style="{ height: wk.barHeightRpx + 'rpx' }"
                />
              </view>
              <text class="c3-ladder-lbl" :class="{ active: wk.week_index === selectedWeekIdx }">W{{ wk.week_index }}</text>
            </view>
          </view>

          <!-- 1 行教练叮嘱 / 复盘高亮条（若有） -->
          <view
            v-if="activeMiniWeek?.coach_weekly_diagnosis || plan.coach_review_note"
            class="rgm-coach-box c3-coach-line"
          >
            <text class="ai-notice-tag">AI生成</text>
            <text class="c3-coach-line-txt">
              {{ activeMiniWeek?.coach_weekly_diagnosis || plan.coach_review_note }}
            </text>
          </view>
        </view>

        <!-- 全周 7 日紧凑课表同屏一览 -->
        <view v-if="activeMiniWeek" class="c3-week-days">
          <template v-for="(day, dIdx) in (activeMiniWeek.days || [])" :key="dIdx">
            <!-- 今日课表：高对比翡翠绿聚焦卡 -->
            <view
              v-if="isTodayWorkout(day)"
              class="c3-day-today"
              :class="{ completed: day.completed }"
              @click="openEditWorkoutModal(activeMiniWeek.week_index, Number(dIdx), day)"
            >
              <view class="c3-dt-left">
                <view class="c3-dt-top">
                  <text class="c3-dt-badge">{{ day.day_of_week }} · {{ getWorkoutTypeLabel(day.workout_type) }}</text>
                  <text v-if="day.target_pace && day.target_pace !== '—'" class="c3-dt-pace">
                    {{ day.target_pace }}{{ day.target_hr_zone && day.target_hr_zone !== '—' ? ` · ${day.target_hr_zone}` : '' }}
                  </text>
                </view>
                <text class="c3-dt-km">
                  {{ day.workout_type === 'rest' ? day.title : `${day.distance_km || 0} km` }}
                </text>
                <text class="c3-dt-sub">{{ day.title }}</text>
              </view>
              <view
                class="c3-dt-check"
                :class="{ checked: day.completed }"
                @click.stop="handleToggleComplete(activeMiniWeek.week_index, Number(dIdx), day)"
              >
                <RgmIcon name="check" :size="34" :color="day.completed ? 'white' : 'green'" :stroke-width="2.4" />
              </view>
            </view>

            <!-- 其他日（已完赛 / 休息 / 未来）：单行紧凑条 -->
            <view
              v-else
              class="rgm-card c3-day-row"
              :class="{ completed: day.completed, missed: isDayMissed(day), isrest: day.workout_type === 'rest' }"
              @click="openEditWorkoutModal(activeMiniWeek.week_index, Number(dIdx), day)"
            >
              <view class="c3-dr-left">
                <text class="c3-dr-day">{{ day.day_of_week }}</text>
                <view class="c3-dr-dot" :class="getWorkoutBadgeClass(day.workout_type)" />
                <text class="c3-dr-type" :class="getWorkoutBadgeClass(day.workout_type)">{{ getWorkoutTypeLabel(day.workout_type) }}</text>
                <text class="c3-dr-title">
                  {{ day.workout_type === 'rest' ? day.title : `${day.distance_km || 0} km${day.target_pace && day.target_pace !== '—' ? ' · ' + day.target_pace : ''}` }}
                </text>
              </view>
              <view class="c3-dr-right">
                <text v-if="day.completed && day.actual_distance_km" class="c3-dr-actual">{{ day.actual_distance_km }}k</text>
                <RgmIcon v-else-if="day.completed" name="check" :size="24" color="green" :stroke-width="2.4" />
                <text v-else-if="isDayMissed(day)" class="c3-dr-missed">补卡</text>
                <text v-else-if="day.rpe != null" class="c3-dr-rpe">RPE {{ day.rpe }}</text>
                <RgmIcon v-else name="chevron-right" :size="22" color="muted" />
              </view>
            </view>
          </template>
        </view>

        <!-- 周反馈与伤痛报备折叠条 -->
        <view v-if="activeMiniWeek" class="rgm-card c3-feedback-box">
          <view class="c3-fb-head" @click="showWeekSummaryForm = !showWeekSummaryForm">
            <text class="c3-fb-title">第 {{ activeMiniWeek.week_index }} 周小结与伤痛报备</text>
            <text class="c3-fb-toggle">{{ showWeekSummaryForm ? '收起 ▴' : (weekInjuryNote || weekAthleteSummary ? '已填 · 改 ▾' : '填写 ▾') }}</text>
          </view>
          <view v-if="showWeekSummaryForm" class="c3-fb-form">
            <view class="modal-input-group">
              <text class="modal-label">伤痛上报（无则留空或填无）</text>
              <input v-model="weekInjuryNote" class="modal-input" placeholder="如：右脚跟腱跑后轻微酸胀" />
            </view>
            <view class="modal-input-group">
              <text class="modal-label">本周训练小结</text>
              <input v-model="weekAthleteSummary" class="modal-input" placeholder="如：周二间歇顺畅，周末拉练后程稳" />
            </view>
            <view class="modal-input-group">
              <text class="modal-label">出差 / 比赛行程报备</text>
              <input v-model="weekTravelNote" class="modal-input" placeholder="如：下周三出差仅晨跑" />
            </view>
            <button class="primary-btn" :loading="savingWeekSummary" @click="handleSaveRunnerWeekSummary">
              <text class="btn-text">{{ savingWeekSummary ? '提交中...' : '提交周反馈' }}</text>
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── ANALYSIS TAB CONTENT (体能切页) ── -->
    <view v-else class="analysis-tab-section">
      <!-- 直达完整 A1 跑力与 30 天生理趋势页 -->
      <view class="rgm-card c3-body-shortcut" @click="goToBodyData">
        <view class="c3-bs-left">
          <RgmIcon name="gauge" :size="34" color="purple" />
          <view class="c3-bs-text">
            <text class="c3-bs-title">完整 VDOT 雷达与 30 天生理趋势</text>
            <text class="c3-bs-sub">查看 HRV、静息心率与赛后评估</text>
          </view>
        </view>
        <RgmIcon name="chevron-right" :size="26" color="muted" />
      </view>

      <!-- Athlete Profile & TSB Card -->
      <view class="profile-card">
        <view class="profile-top">
          <view class="profile-name-box">
            <text class="profile-name">{{ athleteInfo.name || "跑者" }}</text>
            <text class="profile-meta">
              {{ athleteInfo.gender === 'female' ? '女' : '男' }} ·
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
          <RgmIcon name="alert" :size="24" color="amber" />
          <text class="risk-text">{{ tsbMetrics.risk_warning }}</text>
        </view>
      </view>

      <!-- 备赛诊断开关 + 重算按钮 -->
      <view class="race-setup-card">
        <view class="c3-race-setup-head" @click="showAnalysisRaceSetup = !showAnalysisRaceSetup">
          <view class="c3-rs-left">
            <text class="card-title">诊断目标：{{ targetRace || '未设定' }}</text>
            <text class="c3-rs-sub">
              目标 {{ targetTime || '—' }} · {{ raceType === 'half' ? '半马' : raceType === 'trail' ? '越野' : raceType === '10k' ? '10K' : '全马' }}
            </text>
          </view>
          <view class="c3-rs-right">
            <text class="c3-reanalyze-pill" @click.stop="handleReAnalyze">{{ loading ? '测算中...' : '重算' }}</text>
            <text class="c3-switch-pill">{{ showAnalysisRaceSetup ? '收起 ▴' : '切换 ▾' }}</text>
          </view>
        </view>

        <view v-if="showAnalysisRaceSetup" class="c3-rs-expand">
          <view v-if="userRaces.length" class="registered-races-row">
            <text class="registered-label">已登记赛事</text>
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
              <input v-model="targetRace" placeholder="如: 上海马拉松" class="setup-input" @input="onRaceNameInput" />
            </view>
            <view class="input-col flex-1">
              <text class="input-label">目标时间</text>
              <input v-model="targetTime" placeholder="3:15:00" class="setup-input" />
            </view>
          </view>

          <view class="race-type-pills-row">
            <text class="input-label">专项分类</text>
            <view class="type-pills">
              <view class="type-pill" :class="{ active: raceType === 'marathon' }" @click="setCategory('marathon')"><text class="pill-text">全马</text></view>
              <view class="type-pill" :class="{ active: raceType === 'half' }" @click="setCategory('half')"><text class="pill-text">半马</text></view>
              <view class="type-pill" :class="{ active: raceType === 'trail' }" @click="setCategory('trail')"><text class="pill-text">越野</text></view>
              <view class="type-pill" :class="{ active: raceType === '10k' || raceType === '5k' }" @click="setCategory('10k')"><text class="pill-text">10K</text></view>
            </view>
          </view>
        </view>
      </view>

      <!-- Main Diagnosis Cards -->
      <view v-if="analysis" class="content-box">
        <view class="ai-notice-strip">
          <text class="ai-notice-tag">AI生成</text>
          <text class="ai-notice-txt">以下训练诊断、备赛战术、关键课与恢复指导由人工智能（AI）生成，仅供参考</text>
        </view>
        <view class="hero-card">
          <view class="phase-badge" @click.stop="explainTerm('canova_model')">
            <text class="phase-text">阶段：{{ analysis.periodization_phase || "专项准备期" }} · AI生成 ⓘ</text>
          </view>
          <text class="summary-title">{{ analysis.summary }}</text>
          <text class="fitness-detail">{{ analysis.fitness_status }}</text>
        </view>

        <!-- Multi-Race Strategy (长文默认折叠，仅留2行摘要) -->
        <view v-if="analysis.multi_race_strategy" class="section-card multi-race-card">
          <view class="multi-race-header">
            <text class="card-title">多赛事统筹</text>
            <text class="total-races-text">{{ (analysis.multi_race_strategy.race_timeline_advice || []).length }} 场备赛</text>
          </view>

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
                      <text class="badge-text">{{ (r.tier || 'B').toUpperCase() }} 标</text>
                    </view>
                    <text class="race-item-name">{{ r.race_name }}</text>
                  </view>
                  <text v-if="r.days_left !== undefined" class="race-days-countdown">
                    <text class="days-num">{{ r.days_left }}</text> 天
                  </text>
                </view>

                <view class="priority-switch-row">
                  <view class="priority-btns">
                    <button
                      class="p-btn p-btn-a"
                      :class="{ active: (r.tier || '').toUpperCase() === 'A' }"
                      :disabled="updatingPriority === (r.id || r.race_name)"
                      @click.stop="handleUpdatePriority(r.id || r.race_name, 'A')"
                    >A标</button>
                    <button
                      class="p-btn p-btn-b"
                      :class="{ active: (r.tier || '').toUpperCase() === 'B' }"
                      :disabled="updatingPriority === (r.id || r.race_name)"
                      @click.stop="handleUpdatePriority(r.id || r.race_name, 'B')"
                    >B标</button>
                    <button
                      class="p-btn p-btn-c"
                      :class="{ active: (r.tier || '').toUpperCase() === 'C' }"
                      :disabled="updatingPriority === (r.id || r.race_name)"
                      @click.stop="handleUpdatePriority(r.id || r.race_name, 'C')"
                    >C标</button>
                  </view>
                  <button
                    class="set-target-btn"
                    :class="{ 'is-active-target': isCurrentTarget(r) }"
                    @click.stop="handleSelectTargetRace(r)"
                  >
                    {{ isCurrentTarget(r) ? "主备赛" : "设为主目标" }}
                  </button>
                </view>
              </view>

              <view class="c3-strategy-compact" @click="toggleStrategyExpand(String(r.id || r.race_name || idx))">
                <text class="c3-strategy-txt" :class="{ clamped: !expandedStrategyIds[String(r.id || r.race_name || idx)] }">
                  配速：{{ r.pacing_strategy }}
                </text>
                <text v-if="expandedStrategyIds[String(r.id || r.race_name || idx)]" class="c3-strategy-taper">
                  减量：{{ r.taper_recovery_rule }}
                </text>
                <text class="c3-strategy-more">{{ expandedStrategyIds[String(r.id || r.race_name || idx)] ? '收起 ▴' : '展开战术 ▾' }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- Canova 专项配速区间 -->
        <view v-if="analysis.race_zones" class="section-card">
          <text class="card-title">专项配速区间 ({{ targetRace }})</text>
          <view class="zones-list">
            <view v-for="(z, key) in analysis.race_zones" :key="key" class="zone-item">
              <view class="zone-header">
                <text class="zone-name">{{ z.name }}</text>
                <text class="zone-range">{{ z.range }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 本周关键课 & 恢复指导 & 要点 -->
        <view class="section-card workout-card">
          <text class="card-title">本周关键课</text>
          <view class="workout-box">
            <text class="workout-text">{{ formatWorkout(analysis.focus_workout_of_the_week) }}</text>
          </view>
        </view>

        <view class="section-card recovery-card">
          <text class="card-title">恢复指导</text>
          <view class="recovery-box">
            <text class="recovery-text">{{ formatAdvice(analysis.recovery_advice) }}</text>
          </view>
        </view>
      </view>

      <view v-else class="empty-card">
        <RgmIcon name="zap" :size="48" color="brand" />
        <text class="empty-title">Canova 教练就绪</text>
        <text class="empty-desc">配置目标赛事后即可生成训练诊断（AI生成，人工智能生成仅供参考）</text>
        <button class="primary-btn" :loading="loading" @click="handleReAnalyze">生成训练诊断（AI生成）</button>
      </view>
    </view>

    <!-- ── A6 训练体感记录与调休弹窗 ── -->
    <view v-if="editModalOpen" class="modal-mask" @touchmove.stop.prevent>
      <view class="modal-card">
        <view class="modal-header">
          <text class="modal-title">训练体感打卡与调休</text>
          <text class="modal-close" @click="editModalOpen = false">✕</text>
        </view>

        <scroll-view scroll-y class="modal-scroll-body">
          <!-- RPE 1-10 Selector -->
          <view class="modal-input-group">
            <text class="modal-label">主观疲劳度 RPE (1轻松 ~ 10极限)</text>
            <view class="c3-rpe-grid">
              <view
                v-for="num in [1,2,3,4,5,6,7,8,9,10]"
                :key="num"
                class="c3-rpe-pill"
                :class="{
                  active: Number(editRpe) === num,
                  easy: Number(editRpe) === num && num <= 3,
                  mod: Number(editRpe) === num && num >= 4 && num <= 6,
                  hard: Number(editRpe) === num && num >= 7 && num <= 8,
                  max: Number(editRpe) === num && num >= 9
                }"
                @click="editRpe = editRpe === String(num) ? '' : String(num)"
              >
                <text>{{ num }}</text>
              </view>
            </view>
          </view>

          <!-- Feeling Tag Quick Selector -->
          <view class="modal-input-group">
            <text class="modal-label">快捷体感标签</text>
            <view class="c3-feel-grid">
              <view
                v-for="tag in COACH_FEELING_TAGS"
                :key="tag"
                class="c3-feel-chip"
                :class="{ active: editFeelingTag === tag }"
                @click="editFeelingTag = editFeelingTag === tag ? '' : tag"
              >
                <text>{{ tag }}</text>
              </view>
            </view>
          </view>

          <view class="modal-row">
            <view class="modal-input-group flex-1">
              <text class="modal-label">执行情况</text>
              <input v-model="editExecutionText" class="modal-input" placeholder="如 15km, hr132" />
            </view>
            <view class="modal-input-group flex-1">
              <text class="modal-label">训练备注</text>
              <input v-model="editAthleteNotes" class="modal-input" placeholder="如 体感轻快" />
            </view>
          </view>

          <!-- Workout Photos Uploader (Max 3) -->
          <view class="modal-input-group">
            <view class="c3-photo-head">
              <text class="modal-label">打卡照片（{{ editWorkoutPhotos.length + editNewPhotosPreview.length }}/3）</text>
            </view>
            <view class="c3-photo-grid">
              <view v-for="(url, idx) in editWorkoutPhotos" :key="'saved_' + idx" class="c3-photo-item">
                <image :src="url" mode="aspectFill" class="c3-photo-img" @click="previewCoachWorkoutPhotos([...editWorkoutPhotos, ...editNewPhotosPreview], Number(idx))" />
                <view class="c3-photo-del" @click.stop="editWorkoutPhotos.splice(Number(idx), 1)">✕</view>
              </view>
              <view v-for="(pUrl, nIdx) in editNewPhotosPreview" :key="'new_' + nIdx" class="c3-photo-item">
                <image :src="pUrl" mode="aspectFill" class="c3-photo-img" @click="previewCoachWorkoutPhotos([...editWorkoutPhotos, ...editNewPhotosPreview], editWorkoutPhotos.length + Number(nIdx))" />
                <view class="c3-photo-del" @click.stop="removeCoachNewPhoto(Number(nIdx))">✕</view>
              </view>
              <view v-if="editWorkoutPhotos.length + editNewPhotosPreview.length < 3" class="c3-photo-add" @click="handleChooseCoachWorkoutPhoto">
                <RgmIcon name="camera" :size="32" color="muted" />
                <text class="c3-photo-add-txt">添加</text>
              </view>
            </view>
          </view>

          <!-- Day Swap & Toggles -->
          <view class="modal-input-group">
            <view class="c3-swap-head">
              <text class="modal-label">与本周其他天对换课表</text>
              <text v-if="editIsSwapped" class="c3-undo-swap" @click="handleUndoSwapWorkout">恢复原课表</text>
            </view>
            <view class="c3-swap-chips">
              <view class="c3-swap-chip" :class="{ active: editSwapDayIdx === -1 }" @click="editSwapDayIdx = -1"><text>不对换</text></view>
              <view
                v-for="(lbl, sIdx) in ['一','二','三','四','五','六','日']"
                :key="sIdx"
                v-show="sIdx !== editDayIdx"
                class="c3-swap-chip"
                :class="{ active: editSwapDayIdx === sIdx }"
                @click="editSwapDayIdx = sIdx"
              >
                <text>换周{{ lbl }}</text>
              </view>
            </view>
          </view>

          <view class="c3-toggle-row">
            <view class="c3-toggle-pill" :class="{ on: editCompleted }" @click="editCompleted = !editCompleted">
              <text>{{ editCompleted ? '跑步已完成 ✓' : '标记跑步完成' }}</text>
            </view>
            <view class="c3-toggle-pill" :class="{ on: editStrengthDone }" @click="editStrengthDone = !editStrengthDone">
              <text>{{ editStrengthDone ? '力量已完成 ✓' : '标记力量完成' }}</text>
            </view>
          </view>

          <view class="modal-row">
            <view class="modal-input-group flex-1">
              <text class="modal-label">晨起 HRV</text>
              <input v-model="editHrv" type="number" class="modal-input" placeholder="如 62" />
            </view>
            <view class="modal-input-group flex-1">
              <text class="modal-label">静息心率</text>
              <input v-model="editRestingHr" type="number" class="modal-input" placeholder="如 48" />
            </view>
            <view class="modal-input-group flex-1">
              <text class="modal-label">恢复%</text>
              <input v-model="editRecoveryPct" type="number" class="modal-input" placeholder="如 86" />
            </view>
          </view>

          <view v-if="isEditingStartedWeek" class="c3-locked-note">
            <RgmIcon name="lock" :size="22" color="amber" />
            <text class="c3-locked-txt">第 {{ editWeekIdx }} 周已开始，处方已锁定；仍可记录体感或调休。</text>
          </view>

          <view class="modal-input-group">
            <text class="modal-label">课目标题</text>
            <input v-model="editTitle" :disabled="isEditingStartedWeek" class="modal-input" :class="{ disabled: isEditingStartedWeek }" />
          </view>
          <view class="modal-row">
            <view class="modal-input-group flex-1">
              <text class="modal-label">计划跑量 (km)</text>
              <input v-model="editDistanceKm" :disabled="isEditingStartedWeek" type="digit" class="modal-input" :class="{ disabled: isEditingStartedWeek }" />
            </view>
            <view class="modal-input-group flex-1">
              <text class="modal-label">目标配速</text>
              <input v-model="editTargetPace" :disabled="isEditingStartedWeek" class="modal-input" :class="{ disabled: isEditingStartedWeek }" />
            </view>
          </view>
          <view class="modal-input-group">
            <text class="modal-label">课表说明</text>
            <textarea v-model="editDescription" :disabled="isEditingStartedWeek" class="modal-textarea" :class="{ disabled: isEditingStartedWeek }" maxlength="300" />
          </view>
        </scroll-view>

        <view class="modal-footer">
          <button class="modal-cancel-btn" @click="editModalOpen = false">取消</button>
          <button class="modal-save-btn" :loading="savingWorkout" @click="handleSaveWorkout">保存打卡与体感</button>
        </view>
      </view>
    </view>

    <view class="ai-legal-disclaimer">
      <text class="ai-legal-text">基于运动生理模型推算，仅供参考，不作医疗诊断依据。</text>
    </view>

    <PersonalShareCardModal
      :visible="showCoachShareCard"
      :race-id="activeCoachShareRaceId"
      @close="showCoachShareCard = false"
    />

    <PersonalReportModal
      :visible="showCoachPersonalReport"
      @close="showCoachPersonalReport = false"
    />

    <GoalSheetModal
      :visible="showCoachGoalSheet"
      :default-tab="coachGoalSheetTab"
      :user-id="user?.id"
      :initial-goal="userGoal"
      @close="showCoachGoalSheet = false"
      @saved="handleCoachGoalSaved"
    />

    <!-- Sticky Floating Preview Confirmation Bar (保留既有无阻塞确认) -->
    <view v-if="isPreviewPlan" class="preview-sticky-bar">
      <view class="preview-sticky-info">
        <text class="preview-sticky-title">预览待确认 · 尚未覆盖原计划</text>
        <text class="preview-sticky-sub">核对周跑量与日常安排后点击启用</text>
      </view>
      <view class="preview-sticky-actions">
        <button class="psb-btn discard" :disabled="confirmingPlan" @click="handleDiscardGeneratedPlan">放弃</button>
        <button class="psb-btn confirm" :loading="confirmingPlan" :disabled="confirmingPlan" @click="handleConfirmGeneratedPlan">
          立即启用此课表
        </button>
      </view>
    </view>
    <PrivacyPopup />
  </view>
</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme, isVolt } from "../../utils/theme";
import PrivacyPopup from "../../components/PrivacyPopup.vue";
import { explainTerm } from "../../utils/glossary";
import { trackClick, trackSubView, trackFunnelStep } from "../../utils/telemetry";
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { onShow, onPullDownRefresh, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import { request, getStoredUser, checkAndAutoLogin, UserProfile, syncTabBarIndex, setTabBarHidden } from "../../utils/api";
import PersonalShareCardModal from "../../components/PersonalShareCardModal.vue";
import PersonalReportModal from "../../components/PersonalReportModal.vue";
import GoalSheetModal from "../../components/GoalSheetModal.vue";
import RgmIcon from "../../components/RgmIcon.vue";

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
  if (hasRace) return "赛";
  const isDownWeek = (week?.phase || "").includes("减量") || (week?.week_title || "").includes("减量");
  if (isDownWeek) return "减";
  const ratio = getAlignmentRatio(week);
  if (ratio >= 88 && ratio <= 112) return "稳";
  return "升";
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
  { id: "aerobic_base", name: "基础有氧耐力", desc: "Zone 2 低心率 · 慢肌毛细血管网" },
  { id: "lactate_threshold", name: "乳酸阈值提升", desc: "LT2 巡航间歇 · 提高抗乳酸稳态" },
  { id: "vo2max_speed", name: "VO2Max 速度储备", desc: "800~1500m 间歇 · 步频神经刚性" },
  { id: "trail_climbing", name: "山地越野爬坡", desc: "手杖爬升 D+ · 股四头肌离心耐受" },
  { id: "general_maintenance", name: "综合体能维持", desc: "平衡跑量 · 核心稳定与防伤" }
];

const activeMiniWeek = computed(() => {
  const weeks = plan.value?.schedule_data?.weeks || [];
  return weeks.find((w: any) => w.week_index === selectedWeekIdx.value) || weeks[0];
});

const todayBeijingStr = computed(() => {
  const now = new Date();
  const bj = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000);
  const y = bj.getFullYear();
  const m = String(bj.getMonth() + 1).padStart(2, "0");
  const d = String(bj.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
});

function isTodayWorkout(day: any): boolean {
  if (!day) return false;
  if (day.date && day.date === todayBeijingStr.value) return true;
  if (day.is_today) return true;
  return false;
}

const activeWeekCompliancePct = computed(() => {
  const w = activeMiniWeek.value;
  if (!w) return 0;
  if (w.compliance_rate != null) {
    return Math.min(100, Math.max(0, Math.round(Number(w.compliance_rate) || 0)));
  }
  const planned = Number(w.weekly_mileage_km || 0);
  const actual = Number(w.actual_mileage_km || 0);
  if (planned <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((actual / planned) * 100)));
});

const activeWeekRingStyle = computed(() => {
  const pct = activeWeekCompliancePct.value;
  const deg = Math.round(pct * 3.6);
  const fillCol = isVolt.value ? "#059669" : "#10B981";
  const trackCol = isVolt.value ? "#E2E8F0" : "#23232C";
  return {
    background: `conic-gradient(${fillCol} 0deg ${deg}deg, ${trackCol} ${deg}deg 360deg)`,
  };
});

const planWeeksLadder = computed(() => {
  const weeks: any[] = plan.value?.schedule_data?.weeks || [];
  if (!weeks.length) return [];
  let windowWeeks = weeks;
  if (weeks.length > 8) {
    const selIdx = Math.max(0, weeks.findIndex((w: any) => Number(w.week_index) === Number(selectedWeekIdx.value)));
    const start = Math.max(0, Math.min(weeks.length - 8, selIdx - 3));
    windowWeeks = weeks.slice(start, start + 8);
  }
  const maxKm = Math.max(...windowWeeks.map((w: any) => Number(w.weekly_mileage_km || 0)), 30);
  return windowWeeks.map((w: any) => {
    const wIdx = Number(w.week_index);
    const curIdx = Number(currentWeekIndex.value || 1);
    const isSel = wIdx === Number(selectedWeekIdx.value);
    const isTaper = String(w.phase || w.week_title || "").includes("减量");
    const kind = isSel ? "selected" : wIdx < curIdx ? "past" : isTaper ? "taper" : "future";
    const km = Number(w.weekly_mileage_km || 0);
    const barHeightRpx = Math.max(24, Math.min(82, Math.round((km / maxKm) * 82)));
    return {
      ...w,
      kind,
      barHeightRpx,
      shortPhase: String(w.phase || "训练").split(/[\s(（]/)[0],
    };
  });
});

const heroTargetRaceInfo = computed(() => {
  const name = plan.value?.target_race_name || recommendedRace.value?.name || planRaceName.value || "周期科学训练";
  const matched = (userRaces.value || []).find(
    (r: any) => r.name === name || (name && String(r.name || "").includes(name))
  ) || recommendedRace.value;
  const daysLeft = matched?.days_left;
  const tier = matched ? (matched.priority == 1 || matched.priority === "A" ? "A标" : matched.priority == 2 || matched.priority === "B" ? "B标" : "C标") : "目标";
  return {
    name,
    tier,
    daysBadge: daysLeft != null && Number(daysLeft) >= 0 ? `D-${daysLeft}` : "",
    targetTime: plan.value?.target_time || matched?.target_time || "",
    phase: activeMiniWeek.value?.phase || "周期训练期",
  };
});

const expandedStrategyIds = ref<Record<string, boolean>>({});
function toggleStrategyExpand(key: string) {
  expandedStrategyIds.value = {
    ...expandedStrategyIds.value,
    [key]: !expandedStrategyIds.value[key],
  };
}

const COACH_FEELING_TAGS = [
  "状态极佳",
  "轻松舒适",
  "正常发挥",
  "略感吃力",
  "疲惫掉速",
  "肌肉酸紧",
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
    interval: "间歇",
    long_run: "LSD",
    trail_climb: "越野爬坡",
    cross_training: "力量",
    race: "比赛日",
    rest: "休息"
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
    confirmColor: "#FC4C02",
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
      uni.showToast({
        title: "课表预览已生成，请在底部点击启用",
        icon: "none",
        duration: 2400,
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
  if (confirmingPlan.value) return;
  doConfirmGeneratedPlan();
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
    const res = await request(`/api/coach/plan/${plan.value.id}/workout`, "PUT", payload);
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
    const res = await request(`/api/coach/plan/${plan.value.id}/workout`, "PUT", payload);
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
    const res = await request(`/api/coach/plan/${plan.value.id}/workout`, "PUT", payload);
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

  const [racesRes, reportRes] = await Promise.all([
    request(`/api/profile/${uid}/races`).catch((e) => {
      console.warn("Fetch user races fallback:", e);
      return null;
    }),
    request(`/api/coach/latest/${uid}`).catch((e) => {
      console.warn("Fetch coach report fallback:", e);
      return null;
    }),
  ]);

  if (Array.isArray(racesRes)) {
    userRaces.value = racesRes;
  } else if (racesRes && Array.isArray(racesRes.races)) {
    userRaces.value = racesRes.races;
  }

  if (reportRes && reportRes.summary) {
    if (!reportRes.multi_race_strategy) {
      reportRes.multi_race_strategy = { ...defaultAnalysis.multi_race_strategy };
    }
    analysis.value = reportRes;
    if (reportRes.athlete_snapshot?.target_race) {
      targetRace.value = reportRes.athlete_snapshot.target_race;
    }
    if (reportRes.athlete_snapshot?.target_time) {
      targetTime.value = reportRes.athlete_snapshot.target_time;
    }
    if (reportRes.athlete_snapshot?.race_category) {
      raceType.value = reportRes.athlete_snapshot.race_category;
    }
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

let lastCoachLoadedAt = 0;

onShow(() => {
  applySystemTheme(currentTheme.value);
  syncTabBarIndex();

  const storedNow = getStoredUser();
  const uidChanged = Boolean(storedNow?.id && storedNow.id !== user.value?.id);
  let mutTs = 0;
  let isDirty = false;
  try {
    mutTs = Number(uni.getStorageSync("rgm_last_mutation_ts") || 0);
    isDirty = Boolean(uni.getStorageSync("rgm_dashboard_dirty"));
  } catch (_) {}

  if (
    lastCoachLoadedAt > 0 &&
    !uidChanged &&
    !isDirty &&
    mutTs <= lastCoachLoadedAt &&
    Date.now() - lastCoachLoadedAt < 30000
  ) {
    return;
  }

  lastCoachLoadedAt = Date.now();
  Promise.all([loadLatestReport(), loadUserPlan()]);
});

const isAnyCoachPageModalOpen = computed(() => Boolean(editModalOpen.value));
watch(isAnyCoachPageModalOpen, (open) => setTabBarHidden(open, "coach_page"));

onPullDownRefresh(async () => {
  try {
    lastCoachLoadedAt = Date.now();
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

.coach-page.has-preview-bar {
  padding-bottom: calc(230rpx + constant(safe-area-inset-bottom));
  padding-bottom: calc(230rpx + env(safe-area-inset-bottom));
}

.preview-sticky-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 95;
  padding: 18rpx 26rpx calc(20rpx + constant(safe-area-inset-bottom)) 26rpx;
  padding: 18rpx 26rpx calc(20rpx + env(safe-area-inset-bottom)) 26rpx;
  background: var(--rgm-card, #141418);
  border-top: 2rpx solid rgba(16, 185, 129, 0.45);
  box-shadow: 0 -10rpx 32rpx rgba(0, 0, 0, 0.38);
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.preview-sticky-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.preview-sticky-title {
  font-size: 23rpx;
  font-weight: 800;
  color: #10b981;
  white-space: nowrap;
}

.preview-sticky-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #9ca3af);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-sticky-actions {
  display: flex;
  gap: 16rpx;
}

.psb-btn {
  margin: 0;
  height: 74rpx;
  line-height: 74rpx;
  border-radius: 18rpx;
  font-size: 25rpx;
  font-weight: 800;
}

.psb-btn.discard {
  flex: 1;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text, #e4e4e7);
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.2));
}

.psb-btn.confirm {
  flex: 2;
  background: linear-gradient(135deg, #10b981, #059669);
  color: #ffffff;
}

/* ── Coach v3 Minimal Graphical System ── */
.coach-v3 {
  padding: 20rpx 28rpx calc(140rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 20rpx 28rpx calc(140rpx + env(safe-area-inset-bottom)) 28rpx;
}

.c3-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 22rpx;
}

.c3-seg {
  width: 280rpx;
}

.c3-top-actions {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.rgm-icon-btn.active {
  border-color: var(--rgm-brand);
  background: var(--rgm-brand-tint);
}

.c3-wear-warn {
  margin-bottom: 18rpx;
  padding: 14rpx 20rpx;
  border-radius: 20rpx;
  background: var(--rgm-amber-tint);
  border: 1rpx solid var(--rgm-amber-line);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.c3-wear-left {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex: 1;
  min-width: 0;
}

.c3-wear-txt {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-amber);
}

.c3-wear-more {
  font-size: 22rpx;
  color: var(--rgm-amber);
}

.c3-switch-banner {
  margin-bottom: 18rpx;
  padding: 16rpx 20rpx;
  border-radius: 22rpx;
  background: var(--rgm-amber-tint);
  border: 1rpx solid var(--rgm-amber-line);
}

.c3-sb-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.c3-sb-title {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--rgm-text);
}

.c3-sb-actions {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.c3-sb-link {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
}

.c3-sb-cta {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-brand-text);
}

.c3-config-drawer {
  padding: 24rpx;
  margin-bottom: 22rpx;
}

.c3-cd-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.c3-cd-title-row {
  display: flex;
  align-items: center;
  gap: 6rpx;
}

.c3-cd-title {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--rgm-text);
}

.c3-cd-tools {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.c3-cd-pill {
  font-size: 21rpx;
  font-weight: 700;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line-solid);
  color: var(--rgm-text-2);
}

.c3-anchor-edit {
  margin-left: auto;
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand);
}

.c3-plan-body {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.c3-goal-hero {
  padding: 24rpx 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
}

.c3-gh-left {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.c3-gh-top {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-wrap: nowrap;
}

.c3-tier-tag {
  font-size: 19rpx;
  font-weight: 800;
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
  background: var(--rgm-brand-tint);
  border: 1rpx solid var(--rgm-brand-line);
  color: var(--rgm-brand-text);
  flex-shrink: 0;
}

.c3-race-title {
  font-size: 30rpx;
  font-weight: 900;
  color: var(--rgm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.c3-days-pill {
  font-size: 20rpx;
  font-weight: 800;
  color: var(--rgm-brand-text);
  flex-shrink: 0;
}

.c3-gh-sub-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.c3-green-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 50%;
  background: var(--rgm-green);
  flex-shrink: 0;
}

.c3-gh-sub {
  font-size: 22rpx;
  color: var(--rgm-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.c3-ring-outer {
  width: 108rpx;
  height: 108rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.c3-ring-hole {
  width: 86rpx;
  height: 86rpx;
  border-radius: 50%;
  background: var(--rgm-card);
  display: flex;
  align-items: center;
  justify-content: center;
}

.c3-ring-pct {
  font-size: 24rpx;
  font-weight: 900;
  color: var(--rgm-green);
}

.c3-ladder-card {
  padding: 22rpx 22rpx 20rpx;
}

.c3-ladder-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18rpx;
}

.c3-ladder-title {
  font-size: 23rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
}

.c3-ladder-right {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.c3-ladder-km {
  font-size: 23rpx;
  font-weight: 800;
  color: var(--rgm-brand-text);
}

.c3-sync-chip {
  font-size: 20rpx;
  font-weight: 700;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: var(--rgm-brand-tint);
  border: 1rpx solid var(--rgm-brand-line);
  color: var(--rgm-brand-text);
}

.c3-ladder-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 10rpx;
  height: 116rpx;
}

.c3-ladder-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
}

.c3-ladder-stage {
  height: 84rpx;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  width: 100%;
}

.c3-ladder-bar {
  width: 28rpx;
  border-radius: 10rpx;
  background: var(--rgm-card-3);
}

.c3-ladder-bar.past {
  background: var(--rgm-green);
}

.c3-ladder-bar.taper {
  background: var(--rgm-blue);
}

.c3-ladder-bar.selected {
  background: var(--rgm-brand);
  box-shadow: 0 4rpx 14rpx var(--rgm-brand-glow);
}

.c3-ladder-lbl {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-text-3);
}

.c3-ladder-lbl.active {
  color: var(--rgm-brand);
  font-weight: 800;
}

.c3-coach-line {
  margin-top: 16rpx;
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.c3-coach-line-txt {
  font-size: 22rpx;
  color: var(--rgm-text);
  line-height: 1.4;
  flex: 1;
}

.c3-week-days {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.c3-day-today {
  background: var(--rgm-green-tint);
  border: 1.5rpx solid var(--rgm-green);
  border-radius: 28rpx;
  padding: 22rpx 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.c3-dt-left {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.c3-dt-top {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.c3-dt-badge {
  font-size: 20rpx;
  font-weight: 800;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: var(--rgm-green);
  color: #ffffff;
}

.c3-dt-pace {
  font-size: 22rpx;
  color: var(--rgm-text-2);
  font-weight: 600;
}

.c3-dt-km {
  font-size: 40rpx;
  font-weight: 900;
  color: var(--rgm-text);
  line-height: 1.1;
}

.c3-dt-sub {
  font-size: 22rpx;
  color: var(--rgm-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.c3-dt-check {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  background: var(--rgm-card);
  border: 3rpx solid var(--rgm-green);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.c3-dt-check.checked {
  background: var(--rgm-green);
}

.c3-day-row {
  min-height: 82rpx;
  padding: 14rpx 22rpx;
  border-radius: 22rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.c3-day-row.isrest {
  opacity: 0.78;
}

.c3-dr-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex: 1;
  min-width: 0;
}

.c3-dr-day {
  font-size: 23rpx;
  font-weight: 700;
  color: var(--rgm-text-2);
  width: 54rpx;
  flex-shrink: 0;
}

.c3-dr-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 50%;
  background: var(--rgm-text-3);
  flex-shrink: 0;
}

.c3-dr-dot.badge-easy { background: var(--rgm-green); }
.c3-dr-dot.badge-tempo { background: var(--rgm-brand); }
.c3-dr-dot.badge-interval { background: var(--rgm-blue); }
.c3-dr-dot.badge-long { background: var(--rgm-purple); }
.c3-dr-dot.badge-race { background: var(--rgm-red); }

.c3-dr-type {
  font-size: 20rpx;
  font-weight: 800;
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
  flex-shrink: 0;
}

.c3-dr-title {
  font-size: 23rpx;
  font-weight: 600;
  color: var(--rgm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.c3-dr-right {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-shrink: 0;
}

.c3-dr-actual {
  font-size: 23rpx;
  font-weight: 800;
  color: var(--rgm-green);
}

.c3-dr-missed {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-red);
}

.c3-dr-rpe {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-brand-text);
}

.c3-feedback-box {
  padding: 20rpx 22rpx;
}

.c3-fb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.c3-fb-title {
  font-size: 25rpx;
  font-weight: 800;
  color: var(--rgm-text);
}

.c3-fb-toggle {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text);
  background: var(--rgm-brand-tint);
  padding: 6rpx 18rpx;
  border-radius: 999rpx;
}

.c3-fb-form {
  margin-top: 18rpx;
  padding-top: 18rpx;
  border-top: 1rpx solid var(--rgm-line);
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.c3-body-shortcut {
  padding: 22rpx 24rpx;
  margin-bottom: 18rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
}

.c3-bs-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
  min-width: 0;
}

.c3-bs-text {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.c3-bs-title {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text);
}

.c3-bs-sub {
  font-size: 21rpx;
  color: var(--rgm-text-3);
}

.c3-race-setup-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.c3-rs-left {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.c3-rs-sub {
  font-size: 22rpx;
  color: var(--rgm-text-2);
}

.c3-rs-right {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.c3-reanalyze-pill {
  font-size: 22rpx;
  font-weight: 700;
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line-solid);
  color: var(--rgm-text);
}

.c3-switch-pill {
  font-size: 22rpx;
  font-weight: 700;
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
  background: var(--rgm-brand-tint);
  color: var(--rgm-brand-text);
}

.c3-rs-expand {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid var(--rgm-line);
}

.c3-strategy-compact {
  margin-top: 12rpx;
  padding: 14rpx 16rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-2);
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.c3-strategy-txt {
  font-size: 22rpx;
  color: var(--rgm-text-2);
  line-height: 1.45;
}

.c3-strategy-txt.clamped {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.c3-strategy-taper {
  font-size: 22rpx;
  color: var(--rgm-text-2);
  line-height: 1.45;
}

.c3-strategy-more {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-brand-text);
  align-self: flex-end;
}

.c3-rpe-grid {
  display: flex;
  gap: 8rpx;
  margin-top: 8rpx;
}

.c3-rpe-pill {
  flex: 1;
  height: 54rpx;
  border-radius: 12rpx;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line-solid);
  color: var(--rgm-text-2);
  font-size: 22rpx;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.c3-rpe-pill.easy { background: var(--rgm-green); border-color: var(--rgm-green); color: #ffffff; }
.c3-rpe-pill.mod { background: var(--rgm-brand); border-color: var(--rgm-brand); color: #ffffff; }
.c3-rpe-pill.hard { background: var(--rgm-amber); border-color: var(--rgm-amber); color: #ffffff; }
.c3-rpe-pill.max { background: var(--rgm-red); border-color: var(--rgm-red); color: #ffffff; }

.c3-feel-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10rpx;
  margin-top: 8rpx;
}

.c3-feel-chip {
  padding: 14rpx 8rpx;
  border-radius: 14rpx;
  text-align: center;
  font-size: 22rpx;
  font-weight: 700;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line-solid);
  color: var(--rgm-text);
}

.c3-feel-chip.active {
  background: var(--rgm-green-tint);
  border-color: var(--rgm-green);
  color: var(--rgm-green);
}

.c3-photo-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8rpx;
}

.c3-photo-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}

.c3-photo-item {
  width: 132rpx;
  height: 132rpx;
  border-radius: 16rpx;
  position: relative;
  overflow: hidden;
  border: 1rpx solid var(--rgm-line-solid);
}

.c3-photo-img {
  width: 100%;
  height: 100%;
}

.c3-photo-del {
  position: absolute;
  top: 6rpx;
  right: 6rpx;
  width: 34rpx;
  height: 34rpx;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.7);
  color: #ffffff;
  font-size: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.c3-photo-add {
  width: 132rpx;
  height: 132rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-2);
  border: 2rpx dashed var(--rgm-line-2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
}

.c3-photo-add-txt {
  font-size: 19rpx;
  color: var(--rgm-text-2);
  font-weight: 600;
}

.c3-swap-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.c3-undo-swap {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-red);
}

.c3-swap-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-top: 8rpx;
}

.c3-swap-chip {
  padding: 8rpx 16rpx;
  border-radius: 12rpx;
  font-size: 21rpx;
  font-weight: 700;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line-solid);
  color: var(--rgm-text-2);
}

.c3-swap-chip.active {
  background: var(--rgm-blue);
  border-color: var(--rgm-blue);
  color: #ffffff;
}

.c3-toggle-row {
  display: flex;
  gap: 14rpx;
  margin-bottom: 16rpx;
}

.c3-toggle-pill {
  flex: 1;
  padding: 14rpx;
  border-radius: 16rpx;
  text-align: center;
  font-size: 22rpx;
  font-weight: 700;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line-solid);
  color: var(--rgm-text-2);
}

.c3-toggle-pill.on {
  background: var(--rgm-green-tint);
  border-color: var(--rgm-green);
  color: var(--rgm-green);
}

.c3-locked-note {
  margin-bottom: 14rpx;
  padding: 12rpx 16rpx;
  border-radius: 14rpx;
  background: var(--rgm-amber-tint);
  border: 1rpx solid var(--rgm-amber-line);
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.c3-locked-txt {
  font-size: 21rpx;
  color: var(--rgm-amber);
  font-weight: 600;
}

.modal-input.disabled,
.modal-textarea.disabled {
  opacity: 0.55;
}

.ai-notice-strip {
  display: flex;
  align-items: center;
  gap: 10rpx;
  padding: 12rpx 18rpx;
  margin-bottom: 16rpx;
  border-radius: 14rpx;
  background: var(--rgm-brand-tint);
  border: 1rpx solid var(--rgm-brand-line);
}
.ai-notice-tag {
  flex-shrink: 0;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  background: var(--rgm-brand);
  color: #ffffff;
  font-size: 19rpx;
  font-weight: 800;
}
.ai-notice-txt {
  font-size: 21rpx;
  line-height: 1.4;
  color: var(--rgm-text-2);
}
.ai-compliance-banner {
  display: block;
  margin-top: 12rpx;
  font-size: 20rpx;
  line-height: 1.45;
  color: var(--rgm-text-3);
  text-align: center;
}

</style>
