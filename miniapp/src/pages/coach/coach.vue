<template>
  <view class="coach-page">
    <!-- Header -->
    <view class="coach-header">
      <view class="header-left">
        <view class="title-row">
          <text class="title-icon">⚡</text>
          <text class="page-title">Canova AI 智能耐力教练</text>
        </view>
        <text class="page-subtitle">世界级专项化哲学 · 5K/半马/全马/越野因赛制宜 · 动态 TSB 与年龄自适应</text>
      </view>

      <button class="re-analyze-btn" :loading="loading" :disabled="loading" @click="handleReAnalyze">
        <text class="btn-text">{{ loading ? "AI 推理中..." : "启动专项推理" }}</text>
      </button>
    </view>

    <!-- ── TAB BAR: PLAN VS ANALYSIS ── -->
    <view class="coach-tab-bar">
      <view
        class="coach-tab-item"
        :class="{ active: activeTab === 'plan' }"
        @click="activeTab = 'plan'"
      >
        <text class="tab-icon">📅</text>
        <text class="tab-title">科学周期课表</text>
      </view>
      <view
        class="coach-tab-item"
        :class="{ active: activeTab === 'analysis' }"
        @click="activeTab = 'analysis'"
      >
        <text class="tab-icon">⚡</text>
        <text class="tab-title">AI 专项诊断</text>
      </view>
    </view>

    <!-- ── PLAN TAB CONTENT ── -->
    <view v-if="activeTab === 'plan'" class="plan-tab-section">
      <!-- Top Bar -->
      <view class="plan-top-bar">
        <view class="plan-title-box">
          <text class="plan-main-title">{{ plan ? plan.title : '个人科学周期训练课表' }}</text>
          <text v-if="plan" class="plan-status-pill">执行中 · {{ plan.weeks_count }}周周期</text>
        </view>
        <button class="plan-config-toggle-btn" @click="showPlanConfig = !showPlanConfig">
          <text class="btn-text">{{ showPlanConfig ? '收起定制' : (plan ? '重新制定计划' : '制定训练计划') }}</text>
        </button>
      </view>

      <!-- Plan Setup Panel -->
      <view v-if="showPlanConfig || !plan" class="plan-setup-card">
        <view class="card-title-row">
          <text class="section-icon">🎯</text>
          <text class="card-title">设定训练目标与周期参数</text>
        </view>
        <text class="setup-hint">系统将结合您的周岁年龄、TSB状态与近 18 个月比赛表现科学推演</text>

        <!-- Goal Type Toggle -->
        <view class="goal-type-toggle-row">
          <view
            class="goal-type-btn"
            :class="{ active: planGoalType === 'race_prep' }"
            @click="planGoalType = 'race_prep'"
          >
            <text class="goal-btn-title">🏅 赛事突破备战</text>
            <text class="goal-btn-sub">全马/半马/越野倒排周期</text>
          </view>
          <view
            class="goal-type-btn"
            :class="{ active: planGoalType === 'fitness_maintenance' }"
            @click="planGoalType = 'fitness_maintenance'"
          >
            <text class="goal-btn-title">🏔️ 非赛期体能进阶</text>
            <text class="goal-btn-sub">有氧/门槛/速度/爬坡强化</text>
          </view>
        </view>

        <!-- If Race: Quick Select & Inputs -->
        <view v-if="planGoalType === 'race_prep'" class="race-setup-inputs">
          <view v-if="userRaces.length" class="registered-races-row">
            <text class="registered-label">🚩 点击已登记赛历快速套用：</text>
            <view class="registered-chips">
              <view
                v-for="r in userRaces"
                :key="r.id || r.name"
                class="reg-chip"
                :class="{ active: planRaceName === r.name }"
                @click="planRaceName = r.name; if(r.target_time) planTargetTime = r.target_time;"
              >
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
          <text class="input-label">选择当前周期专项强化方向：</text>
          <view class="maint-chips-grid">
            <view
              v-for="m in maintenanceList"
              :key="m.id"
              class="maint-chip"
              :class="{ active: planMaintenanceFocus === m.id }"
              @click="planMaintenanceFocus = m.id"
            >
              <text class="maint-name">{{ m.name }}</text>
              <text class="maint-desc">{{ m.desc }}</text>
            </view>
          </view>
        </view>

        <!-- Weeks & Days Selectors -->
        <view class="picker-row">
          <view class="picker-col">
            <text class="input-label">周期总周数：</text>
            <view class="options-pills">
              <view
                v-for="w in [4, 6, 8, 12]"
                :key="w"
                class="opt-pill"
                :class="{ active: planWeeksCount === w }"
                @click="planWeeksCount = w"
              >
                <text class="pill-text">{{ w }}周</text>
              </view>
            </view>
          </view>

          <view class="picker-col">
            <text class="input-label">每周跑步天数：</text>
            <view class="options-pills">
              <view
                v-for="d in [3, 4, 5, 6]"
                :key="d"
                class="opt-pill"
                :class="{ active: planDaysPerWeek === d }"
                @click="planDaysPerWeek = d"
              >
                <text class="pill-text">{{ d }}天/周</text>
              </view>
            </view>
          </view>
        </view>

        <!-- Goal Anchor Hint in Miniapp -->
        <view class="goal-anchor-box">
          <text class="anchor-icon">🎯</text>
          <text class="anchor-text">当前自定周目标：{{ userGoal?.weekly_target || 50 }} km/周 (系统将自动以此为基准)</text>
        </view>

        <button class="primary-btn" :loading="generatingPlan" @click="handleGeneratePlan">
          <text class="btn-text">{{ generatingPlan ? 'AI 耐力推演生成中...' : '生成科学定制训练课表' }}</text>
        </button>
      </view>

      <!-- Active Plan Details -->
      <view v-if="plan && plan.schedule_data" class="plan-body">
        <!-- Baseline Snapshot Card -->
        <view v-if="plan.schedule_data.current_fitness_snapshot" class="snapshot-card">
          <view class="snap-item">
            <text class="snap-label">跑者周岁</text>
            <text class="snap-val">{{ plan.schedule_data.current_fitness_snapshot.age ? `${plan.schedule_data.current_fitness_snapshot.age} 岁` : '—' }}</text>
            <text class="snap-sub">{{ plan.schedule_data.current_fitness_snapshot.age >= 50 ? '72-96h 恢复律' : '正常' }}</text>
          </view>
          <view class="snap-item">
            <text class="snap-label">VO2Max</text>
            <text class="snap-val text-purple">{{ plan.schedule_data.current_fitness_snapshot.vo2max || '—' }}</text>
            <text class="snap-sub">VDOT基准</text>
          </view>
          <view class="snap-item">
            <text class="snap-label">CTL / TSB</text>
            <text class="snap-val text-cyan">{{ plan.schedule_data.current_fitness_snapshot.ctl || 0 }} / {{ plan.schedule_data.current_fitness_snapshot.tsb || 0 }}</text>
            <text class="snap-sub">即时负荷</text>
          </view>
          <view class="snap-item">
            <text class="snap-label">18m最长跑</text>
            <text class="snap-val text-amber">{{ plan.schedule_data.current_fitness_snapshot.max_long_run_18m_km || '—' }} km</text>
            <text class="snap-sub">实战上限</text>
          </view>
        </view>

        <!-- Canova Overview Quote -->
        <view v-if="plan.overview_summary" class="overview-box">
          <text class="overview-icon">🎯</text>
          <text class="overview-text">{{ plan.overview_summary }}</text>
        </view>

        <!-- Horizontal Week Scroll -->
        <scroll-view scroll-x class="week-scroll-view" show-scrollbar="false">
          <view class="week-chips-row">
            <view
              v-for="w in (plan.schedule_data.weeks || [])"
              :key="w.week_index"
              class="week-chip"
              :class="{ active: selectedWeekIdx === w.week_index }"
              @click="selectedWeekIdx = w.week_index"
            >
              <text class="week-chip-title">第 {{ w.week_index }} 周</text>
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
          </view>
          <view class="active-week-right">
            <text class="mileage-val">{{ activeMiniWeek.weekly_mileage_km || 0 }} km</text>
            <text class="mileage-label">本周总跑量</text>
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
            <text class="sync-mini-btn-text">同步至目标</text>
          </button>
        </view>

        <!-- 7 Daily Workout Cards -->
        <view v-if="activeMiniWeek" class="daily-cards-list">
          <view
            v-for="(day, dIdx) in (activeMiniWeek.days || [])"
            :key="dIdx"
            class="daily-card"
            :class="[getWorkoutBorderClass(day.workout_type), { 'is-completed': day.completed }]"
          >
            <view class="daily-card-top">
              <view class="day-date-box">
                <text class="day-name">{{ day.day_of_week }}</text>
                <text class="day-date">{{ day.date ? day.date.substring(5) : '' }}</text>
              </view>
              <text class="type-badge" :class="getWorkoutBadgeClass(day.workout_type)">
                {{ getWorkoutTypeLabel(day.workout_type) }}
              </text>
            </view>

            <view class="daily-card-body">
              <text class="workout-title">{{ day.title }}</text>
              <view v-if="day.workout_type !== 'rest'" class="dist-row">
                <text class="dist-val">{{ day.distance_km || 0 }}</text>
                <text class="dist-unit">km</text>
              </view>

              <!-- Pace & Heart Rate -->
              <view v-if="day.workout_type !== 'rest' && (day.target_pace || day.target_hr_zone)" class="metrics-row">
                <text v-if="day.target_pace && day.target_pace !== '—'" class="metric-pill">⏱️ {{ day.target_pace }}</text>
                <text v-if="day.target_hr_zone && day.target_hr_zone !== '—'" class="metric-pill hr-pill">❤️ {{ day.target_hr_zone }}</text>
              </view>

              <text class="workout-desc">{{ day.description }}</text>

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
                :class="{ completed: day.completed }"
                @click="handleToggleComplete(activeMiniWeek.week_index, dIdx, day)"
              >
                <text class="btn-text">{{ day.completed ? '✅ 已打卡' : '打卡' }}</text>
              </button>
              <button
                class="action-edit-btn"
                @click="openEditWorkoutModal(activeMiniWeek.week_index, dIdx, day)"
              >
                <text class="btn-text">微调/批注</text>
              </button>
            </view>
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
            {{ athleteInfo.age ? `${athleteInfo.age} 岁` : '未录入年龄' }} · 
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
          <text class="tsb-label">状态 TSB</text>
          <text class="tsb-val" :class="tsbMetrics.tsb >= 0 ? 'text-green' : 'text-purple'">
            {{ tsbMetrics.tsb > 0 ? `+${tsbMetrics.tsb}` : (tsbMetrics.tsb || 0) }}
          </text>
        </view>
      </view>

      <view v-if="tsbMetrics.risk_warning" class="risk-box">
        <text class="risk-icon">⚠️</text>
        <text class="risk-text">{{ tsbMetrics.risk_warning }}</text>
      </view>
    </view>

    <!-- ── TARGET RACE CUSTOMIZATION CARD ── -->
    <view class="race-setup-card">
      <view class="card-title-row">
        <text class="section-icon">🎯</text>
        <text class="card-title">目标赛事与专项设定</text>
      </view>

      <!-- Preset Chips -->
      <view class="presets-row">
        <view
          v-for="(p, idx) in racePresets"
          :key="idx"
          class="preset-chip"
          :class="{ active: targetRace === p.race }"
          @click="applyPreset(p)"
        >
          <text class="chip-text">{{ p.label }}</text>
        </view>
      </view>

      <!-- Registered User Races Quick Selector -->
      <view v-if="userRaces.length" class="registered-races-row">
        <text class="registered-label">🚩 您已登记的备赛日程 (点击直接切换为当前备赛)：</text>
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

    <!-- Main Content -->
    <view v-if="analysis" class="content-box">
      <!-- ── CARD 1: 当前阶段与核心评价 ── -->
      <view class="hero-card">
        <view class="phase-badge">
          <text class="sparkle">✨</text>
          <text class="phase-text">当前阶段：{{ analysis.periodization_phase || "专项准备期 (Special Period)" }}</text>
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
              <text class="card-title">Canova 多赛事宏观统筹与战术推演</text>
            </view>
            <text class="multi-race-subtitle">
              A/B/C 梯队科学分级 · 规避过密疲劳冲突 · 黄金以赛代练配对 · 跨赛道专项切换
            </text>
          </view>
          <view class="total-races-badge">
            <text class="sparkle-icon">✨</text>
            <text class="total-races-text">共统筹 {{ (analysis.multi_race_strategy.race_timeline_advice || []).length }} 场目标赛事</text>
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
          <text class="card-title">Canova 比赛专项刺激区间 ({{ targetRace }})</text>
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
            <text class="zone-desc">{{ z.desc }}</text>
          </view>
        </view>
      </view>

      <!-- ── CARD 2: 本周核心关键课 ── -->
      <view class="section-card workout-card">
        <view class="card-title-row">
          <text class="section-icon">🎯</text>
          <text class="card-title">本周核心专项关键课</text>
        </view>
        <view class="workout-box">
          <text class="workout-text">{{ formatWorkout(analysis.focus_workout_of_the_week) }}</text>
        </view>
        <text class="tip-footnote">* 建议在充分热身与休息充沛状态下执行此课表。</text>
      </view>

      <!-- ── CARD 3: 生理恢复与超量恢复指导 ── -->
      <view class="section-card recovery-card">
        <view class="card-title-row">
          <text class="section-icon">🌿</text>
          <text class="card-title">生理恢复与超量恢复指导</text>
        </view>
        <view class="recovery-box">
          <text class="recovery-text">{{ formatAdvice(analysis.recovery_advice) }}</text>
        </view>
        <text class="tip-footnote">* 密切关注晨起静息心率与睡眠质量得分。</text>
      </view>

      <!-- ── CARD 4: Canova 专项训练执行要点 ── -->
      <view class="section-card">
        <view class="card-title-row">
          <text class="section-icon">📋</text>
          <text class="card-title">Canova 专项训练执行要点</text>
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
      <text class="empty-title">Canova AI 教练就绪</text>
      <text class="empty-desc">配置您的目标赛事，点击下方按钮，AI 教练将基于您的近期 Garmin / 高驰训练与生理负荷生成专属报告。</text>
      <button class="primary-btn" :loading="loading" @click="handleReAnalyze">生成最新训练诊断</button>
    </view>
    </view>

    <!-- ── EDIT WORKOUT MODAL ── -->
    <view v-if="editModalOpen" class="modal-mask">
      <view class="modal-card">
        <view class="modal-header">
          <text class="modal-title">微调训练课目与教练指导</text>
          <text class="modal-close" @click="editModalOpen = false">✕</text>
        </view>

        <scroll-view scroll-y class="modal-scroll-body">
          <view class="modal-input-group">
            <text class="modal-label">课目标题</text>
            <input v-model="editTitle" class="modal-input" placeholder="输入课目标题" />
          </view>

          <view class="modal-row">
            <view class="modal-input-group flex-1">
              <text class="modal-label">计划跑量 (km)</text>
              <input v-model="editDistanceKm" type="digit" class="modal-input" />
            </view>
            <view class="modal-input-group flex-1">
              <text class="modal-label">目标配速</text>
              <input v-model="editTargetPace" class="modal-input" placeholder="如 5:15 - 5:25 /km" />
            </view>
          </view>

          <view class="modal-input-group">
            <text class="modal-label">目标心率区间</text>
            <input v-model="editTargetHrZone" class="modal-input" placeholder="如 135-145 bpm" />
          </view>

          <view class="modal-input-group">
            <text class="modal-label">课表安排与热身冷身说明</text>
            <textarea v-model="editDescription" class="modal-textarea" maxlength="300" />
          </view>

          <view class="modal-input-group coach-notes-group">
            <text class="modal-label text-amber">👨‍🏫 跑团教练寄语与指导批注 (Coach Notes)</text>
            <textarea
              v-model="editCoachNotes"
              class="modal-textarea coach-textarea"
              placeholder="在此输入教练微调说明或鼓励指导..."
              maxlength="200"
            />
          </view>
        </scroll-view>

        <view class="modal-footer">
          <button class="modal-cancel-btn" @click="editModalOpen = false">取消</button>
          <button class="modal-save-btn" :loading="savingWorkout" @click="handleSaveWorkout">保存修改</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import { request, getStoredUser, checkAndAutoLogin, UserProfile } from "../../utils/api";

const activeTab = ref<"plan" | "analysis">("plan");

// Training Plan State
const plan = ref<any>(null);
const planLoading = ref(false);
const generatingPlan = ref(false);
const showPlanConfig = ref(false);
const selectedWeekIdx = ref(1);

const planGoalType = ref<"race_prep" | "fitness_maintenance">("race_prep");
const planRaceName = ref("上海马拉松");
const planTargetTime = ref("3:09:30");
const planMaintenanceFocus = ref("aerobic_base");
const planWeeksCount = ref(8);
const planDaysPerWeek = ref(4);
const userGoal = ref<any>(null);
const syncingGoal = ref(false);

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

// Edit modal state
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
const savingWorkout = ref(false);

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

async function loadUserPlan() {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  planLoading.value = true;
  try {
    const res = await request(`/api/coach/plan/user/${user.value.id}`);
    if (res?.active_plan) {
      plan.value = res.active_plan;
      showPlanConfig.value = false;
    } else {
      showPlanConfig.value = true;
    }
    if (res?.user_goal) {
      userGoal.value = res.user_goal;
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
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  generatingPlan.value = true;
  try {
    const payload = {
      athlete_uid: user.value.id,
      goal_type: planGoalType.value,
      target_race_name: planRaceName.value,
      target_time: planTargetTime.value,
      maintenance_focus: planMaintenanceFocus.value,
      weeks_count: planWeeksCount.value,
      days_per_week: planDaysPerWeek.value,
      operator_uid: user.value.id,
      user_weekly_target: userGoal.value?.weekly_target ? Number(userGoal.value.weekly_target) : undefined
    };
    const res = await request("/api/coach/plan/generate", "POST", payload);
    if (res?.success && res?.plan) {
      plan.value = res.plan;
      selectedWeekIdx.value = 1;
      showPlanConfig.value = false;
      uni.showToast({ title: "课表生成成功！", icon: "success" });
    }
  } catch (err) {
    console.error("Generate plan error:", err);
    uni.showToast({ title: "生成课表失败", icon: "none" });
  } finally {
    generatingPlan.value = false;
  }
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
  editModalOpen.value = true;
}

async function handleSaveWorkout() {
  if (!plan.value?.id || !user.value?.id) return;
  savingWorkout.value = true;
  try {
    const payload = {
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
      operator_uid: user.value.id
    };
    const res = await request(`/api/coach/plan/${plan.value.id}/workout`, "PATCH", payload);
    if (res?.success && res?.plan) {
      plan.value = res.plan;
      editModalOpen.value = false;
      uni.showToast({ title: "课表已保存", icon: "success" });
    }
  } catch (err) {
    console.error("Save workout error:", err);
    uni.showToast({ title: "保存失败", icon: "none" });
  } finally {
    savingWorkout.value = false;
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
      plan.value = res.plan;
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
  summary: "欢迎来到 Renato Canova AI 耐力教练专区！绑定 Garmin 或高驰手表后将自动生成您的专属报告。",
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
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  loading.value = true;
  uni.showLoading({ title: "AI 深度推理中..." });

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
    }
  } catch (e) {
    uni.hideLoading();
    uni.showToast({ title: "已加载最新分析", icon: "success" });
  } finally {
    loading.value = false;
  }
}

function formatWorkout(w: any): string {
  if (!w) return "热身 3km + 3 × 4000m @ 专项配速 (间歇 1000m 漂浮跑) + 2km 冷身";
  if (typeof w === "string") return w;
  if (typeof w === "object") {
    return Object.entries(w).map(([k, v]) => `【${k}】${v}`).join("\n");
  }
  return String(w);
}

function formatAdvice(w: any): string {
  if (!w) return "大课后 30 分钟内补充高碳水与适量蛋白质，夜间保证 8 小时深度睡眠，监控晨起 HRV 恢复基准。";
  if (typeof w === "string") return w;
  if (typeof w === "object") {
    return Object.entries(w).map(([k, v]) => `【${k}】${typeof v === "object" ? JSON.stringify(v) : v}`).join("\n");
  }
  return String(w);
}

onShow(() => {
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

</script>

<style scoped>
.coach-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
}

.coach-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30rpx;
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
  color: #bf5af2;
}

.page-title {
  font-size: 34rpx;
  font-weight: 900;
  color: #ffffff;
}

.page-subtitle {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 6rpx;
  display: block;
}

.re-analyze-btn {
  background: linear-gradient(135deg, #af52de 0%, #8e44ad 100%);
  color: #ffffff;
  font-size: 24rpx;
  font-weight: bold;
  padding: 0 24rpx;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 32rpx;
  border: none;
  box-shadow: 0 6rpx 16rpx rgba(175, 82, 222, 0.3);
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
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
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
  color: #ffffff;
  display: block;
}

.profile-meta {
  font-size: 22rpx;
  color: #8e8e93;
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
  color: #30d158;
}

.tsb-neutral {
  background-color: rgba(100, 210, 255, 0.15);
  border-color: rgba(100, 210, 255, 0.3);
  color: #64d2ff;
}

.tsb-optimal {
  background-color: rgba(175, 82, 222, 0.15);
  border-color: rgba(175, 82, 222, 0.3);
  color: #d084f7;
}

.tsb-fatigued {
  background-color: rgba(255, 159, 10, 0.15);
  border-color: rgba(255, 159, 10, 0.3);
  color: #ff9f0a;
}

.tsb-danger {
  background-color: rgba(255, 69, 58, 0.15);
  border-color: rgba(255, 69, 58, 0.3);
  color: #ff453a;
}

.tsb-grid {
  display: flex;
  gap: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
}

.tsb-item {
  flex: 1;
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 16rpx 12rpx;
  text-align: center;
}

.tsb-label {
  font-size: 20rpx;
  color: #8e8e93;
  display: block;
  margin-bottom: 4rpx;
}

.tsb-val {
  font-size: 28rpx;
  font-weight: 900;
  display: block;
}

.text-cyan { color: #64d2ff; }
.text-amber { color: #ff9f0a; }
.text-green { color: #30d158; }
.text-purple { color: #bf5af2; }

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
  color: #ffb4ab;
  line-height: 1.4;
  flex: 1;
}

/* ── RACE SETUP CARD ── */
.race-setup-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
}

.presets-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.preset-chip {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  padding: 8rpx 20rpx;
  border-radius: 20rpx;
}

.preset-chip.active {
  background-color: rgba(175, 82, 222, 0.25);
  border-color: #af52de;
}

.chip-text {
  font-size: 22rpx;
  color: #c7c7cc;
}

.preset-chip.active .chip-text {
  color: #ffffff;
  font-weight: bold;
}

/* Registered User Races */
.registered-races-row {
  margin-top: 14rpx;
  margin-bottom: 18rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
}

.registered-label {
  font-size: 20rpx;
  color: #a1a1aa;
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
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
}

.reg-chip.active {
  background-color: rgba(175, 82, 222, 0.2);
  border-color: #af52de;
}

.reg-chip-tier {
  font-size: 18rpx;
  font-weight: bold;
  padding: 2rpx 8rpx;
  border-radius: 8rpx;
}

.reg-chip-tier.tier-a {
  background-color: rgba(244, 63, 94, 0.25);
  color: #fb7185;
}

.reg-chip-tier.tier-b {
  background-color: rgba(56, 189, 248, 0.25);
  color: #38bdf8;
}

.reg-chip-tier.tier-c {
  background-color: rgba(161, 161, 170, 0.25);
  color: #d4d4d8;
}

.reg-chip-name {
  font-size: 22rpx;
  color: #f3f4f6;
}

.reg-chip.active .reg-chip-name {
  color: #ffffff;
  font-weight: bold;
}

.reg-chip-days {
  font-size: 18rpx;
  color: #c084fc;
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
  color: #8e8e93;
}

.setup-input {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
  height: 64rpx;
  padding: 0 16rpx;
  font-size: 24rpx;
  color: #ffffff;
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
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 14rpx;
  padding: 10rpx 0;
  text-align: center;
  transition: all 0.2s ease;
}

.type-pill.active {
  background-color: rgba(175, 82, 222, 0.25);
  border-color: #af52de;
}

.type-pill .pill-text {
  font-size: 20rpx;
  color: #a1a1aa;
  font-weight: 500;
}

.type-pill.active .pill-text {
  color: #ffffff;
  font-weight: bold;
}

/* ── ZONES LIST ── */
.zones-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.zone-item {
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 18rpx;
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
  color: #e5e5ea;
}

.zone-range {
  font-size: 24rpx;
  font-weight: 900;
  color: #d084f7;
}

.zone-desc {
  font-size: 20rpx;
  color: #8e8e93;
  line-height: 1.4;
}

.hero-card {
  background: linear-gradient(135deg, rgba(175, 82, 222, 0.2) 0%, #151518 100%);
  border: 1rpx solid rgba(175, 82, 222, 0.3);
  border-radius: 28rpx;
  padding: 32rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.5);
}

.phase-badge {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  background-color: rgba(175, 82, 222, 0.2);
  border: 1rpx solid rgba(175, 82, 222, 0.3);
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
  color: #d084f7;
}

.summary-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
  line-height: 1.4;
  margin-bottom: 16rpx;
  display: block;
}

.fitness-detail {
  font-size: 24rpx;
  color: #c7c7cc;
  line-height: 1.6;
  display: block;
}

.section-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 28rpx;
  padding: 28rpx;
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
  color: #ffffff;
}

.workout-box {
  background-color: rgba(175, 82, 222, 0.1);
  border: 1rpx solid rgba(175, 82, 222, 0.2);
  border-radius: 20rpx;
  padding: 22rpx;
}

.workout-text {
  font-size: 26rpx;
  color: #e5c9f9;
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
  color: #bdf2cc;
  line-height: 1.5;
}

.tip-footnote {
  font-size: 20rpx;
  color: #636366;
  margin-top: 14rpx;
  display: block;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.sugg-item {
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 20rpx;
}

.sugg-badge {
  font-size: 20rpx;
  font-weight: bold;
  color: #bf5af2;
  margin-bottom: 8rpx;
  display: block;
}

.sugg-text {
  font-size: 24rpx;
  color: #e5e5ea;
  line-height: 1.5;
}

.multi-race-card {
  border-left: 6rpx solid #bf5af2;
  border-color: rgba(255, 255, 255, 0.08);
}

.multi-race-header {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
  padding-bottom: 20rpx;
  margin-bottom: 22rpx;
}

.multi-race-subtitle {
  font-size: 20rpx;
  color: #a1a1aa;
  line-height: 1.4;
  margin-top: 4rpx;
  display: block;
}

.total-races-badge {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  background-color: rgba(175, 82, 222, 0.12);
  border: 1rpx solid rgba(175, 82, 222, 0.25);
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  align-self: flex-start;
}

.sparkle-icon {
  font-size: 20rpx;
}

.total-races-text {
  font-size: 20rpx;
  color: #d8b4fe;
  font-weight: 600;
}

.macrocycle-box {
  background: linear-gradient(135deg, rgba(88, 28, 135, 0.3) 0%, rgba(24, 24, 28, 0.95) 50%, rgba(49, 46, 129, 0.25) 100%);
  border: 1rpx solid rgba(191, 90, 242, 0.25);
  border-radius: 20rpx;
  padding: 22rpx;
  margin-bottom: 26rpx;
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
  color: #d8b4fe;
}

.macrocycle-text {
  font-size: 24rpx;
  color: #f3f4f6;
  line-height: 1.6;
  display: block;
}

.timeline-section {
  margin-bottom: 20rpx;
}

.timeline-section-title {
  font-size: 22rpx;
  font-weight: bold;
  color: #a1a1aa;
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
  background-color: #18181c;
  border-radius: 24rpx;
  padding: 22rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  transition: all 0.3s ease;
}

.race-item.tier-a {
  border-color: rgba(244, 63, 94, 0.45);
  background-color: rgba(32, 18, 24, 0.95);
  box-shadow: 0 6rpx 24rpx rgba(244, 63, 94, 0.1);
}

.race-item.tier-b {
  border-color: rgba(56, 189, 248, 0.35);
  background-color: rgba(18, 26, 32, 0.95);
}

.race-item.tier-c {
  border-color: rgba(255, 255, 255, 0.08);
  background-color: #18181c;
}

.race-item-header {
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
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
  color: #fda4af;
  border-color: rgba(244, 63, 94, 0.45);
}

.badge-b {
  background-color: rgba(56, 189, 248, 0.2);
  color: #7dd3fc;
  border-color: rgba(56, 189, 248, 0.4);
}

.badge-c {
  background-color: rgba(161, 161, 170, 0.2);
  color: #d4d4d8;
  border-color: rgba(161, 161, 170, 0.4);
}

.badge-text {
  font-size: 20rpx;
}

.race-item-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.race-days-countdown {
  font-size: 22rpx;
  color: #a1a1aa;
  font-weight: 500;
}

.days-num {
  color: #d8b4fe;
  font-weight: 900;
}

.priority-switch-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  background-color: #121215;
  padding: 10rpx 14rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
}

.priority-left-group {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-wrap: wrap;
}

.switch-tip-lbl {
  font-size: 20rpx;
  color: #71717a;
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
  color: #a1a1aa;
  background-color: rgba(255, 255, 255, 0.05);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 10rpx;
}

.p-btn::after {
  border: none;
}

.p-btn-a.active {
  background-color: #f43f5e;
  color: #ffffff;
  border-color: #fb7185;
  box-shadow: 0 2rpx 10rpx rgba(244, 63, 94, 0.4);
}

.p-btn-b.active {
  background-color: #0284c7;
  color: #ffffff;
  border-color: #38bdf8;
  box-shadow: 0 2rpx 10rpx rgba(56, 189, 248, 0.4);
}

.p-btn-c.active {
  background-color: #52525b;
  color: #ffffff;
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
  color: #a1a1aa;
  background-color: #18181c;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 12rpx;
}

.set-target-btn::after {
  border: none;
}

.set-target-btn.is-active-target {
  background-color: rgba(147, 51, 234, 0.25);
  color: #e9d5ff;
  border-color: #a855f7;
}

.race-execution-boxes {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.exec-box {
  background-color: #121215;
  padding: 16rpx 18rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
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
  color: #a1a1aa;
}

.exec-desc {
  font-size: 22rpx;
  color: #e4e4e7;
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
  color: #fbbf24;
}

.conflict-desc {
  font-size: 22rpx;
  color: #fef3c7;
  line-height: 1.5;
  font-weight: 300;
  display: block;
}

.empty-card {
  background-color: #151518;
  border-radius: 28rpx;
  padding: 60rpx 40rpx;
  text-align: center;
}

.empty-icon {
  font-size: 60rpx;
  margin-bottom: 20rpx;
  display: block;
}

.empty-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
  margin-bottom: 12rpx;
  display: block;
}

.empty-desc {
  font-size: 24rpx;
  color: #8e8e93;
  line-height: 1.5;
  margin-bottom: 30rpx;
  display: block;
}

.primary-btn {
  background-color: #af52de;
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 24rpx;
  height: 80rpx;
  line-height: 80rpx;
}

/* ── TAB BAR ── */
.coach-tab-bar {
  display: flex;
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 8rpx;
  margin-bottom: 24rpx;
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
  background-color: #af52de;
}

.coach-tab-item .tab-icon {
  font-size: 28rpx;
}

.coach-tab-item .tab-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #8e8e93;
}

.coach-tab-item.active .tab-title {
  color: #ffffff;
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
  color: #ffffff;
  display: block;
}

.plan-status-pill {
  font-size: 20rpx;
  font-weight: bold;
  color: #30d158;
  background-color: rgba(48, 209, 88, 0.15);
  border: 1rpx solid rgba(48, 209, 88, 0.3);
  border-radius: 12rpx;
  padding: 2rpx 10rpx;
  margin-top: 6rpx;
  display: inline-block;
}

.plan-config-toggle-btn {
  background-color: #1c1c1e;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 18rpx;
  padding: 0 20rpx;
  height: 60rpx;
  line-height: 60rpx;
  font-size: 22rpx;
  color: #d1d1d6;
}

/* ── PLAN SETUP CARD ── */
.plan-setup-card {
  background-color: #121215;
  border: 1rpx solid rgba(175, 82, 222, 0.3);
  border-radius: 28rpx;
  padding: 24rpx;
  margin-bottom: 30rpx;
}

.setup-hint {
  font-size: 22rpx;
  color: #af52de;
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
  background-color: #1c1c1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 18rpx 14rpx;
  text-align: center;
}

.goal-type-btn.active {
  border-color: #af52de;
  background-color: rgba(175, 82, 222, 0.15);
}

.goal-btn-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
  display: block;
}

.goal-btn-sub {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
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
  background-color: #1c1c1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 16rpx;
}

.maint-chip.active {
  background-color: rgba(48, 209, 88, 0.15);
  border-color: #30d158;
}

.maint-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
  display: block;
}

.maint-desc {
  font-size: 22rpx;
  color: #8e8e93;
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
}

.options-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 8rpx;
}

.opt-pill {
  padding: 8rpx 18rpx;
  background-color: #1c1c1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 14rpx;
}

.opt-pill.active {
  background-color: #af52de;
  border-color: #af52de;
}

.opt-pill .pill-text {
  font-size: 22rpx;
  color: #ffffff;
}

/* ── SNAPSHOT CARD ── */
.snapshot-card {
  display: flex;
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  justify-content: space-between;
}

.snap-item {
  flex: 1;
  text-align: center;
}

.snap-label {
  font-size: 20rpx;
  color: #8e8e93;
  display: block;
}

.snap-val {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
  margin: 4rpx 0;
  display: block;
}

.snap-sub {
  font-size: 18rpx;
  color: #636366;
  display: block;
}

.overview-box {
  background-color: rgba(175, 82, 222, 0.08);
  border: 1rpx solid rgba(175, 82, 222, 0.2);
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
  color: #d1d1d6;
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
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  min-width: 160rpx;
  box-sizing: border-box;
}

.week-chip.active {
  background-color: #af52de;
  border-color: #af52de;
}

.week-chip-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.week-chip-sub {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
}

.week-chip.active .week-chip-sub {
  color: #e5c5f8;
}

/* ── ACTIVE WEEK HEADER ── */
.active-week-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
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
  color: #ffffff;
}

.phase-tag {
  font-size: 20rpx;
  font-weight: bold;
  color: #af52de;
  background-color: rgba(175, 82, 222, 0.15);
  border: 1rpx solid rgba(175, 82, 222, 0.3);
  border-radius: 10rpx;
  padding: 2rpx 8rpx;
}

.focus-text {
  font-size: 22rpx;
  color: #aeaeb2;
  margin-top: 6rpx;
  display: block;
}

.active-week-right {
  text-align: right;
}

.mileage-val {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
  display: block;
}

.mileage-label {
  font-size: 18rpx;
  color: #8e8e93;
  display: block;
}

/* ── DAILY CARDS LIST ── */
.daily-cards-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.daily-card {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 20rpx;
}

.daily-card.is-completed {
  border-color: rgba(48, 209, 88, 0.4);
  background-color: rgba(48, 209, 88, 0.03);
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
  color: #ffffff;
}

.day-date {
  font-size: 20rpx;
  color: #8e8e93;
}

.type-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
}

.badge-easy { background: rgba(48, 209, 88, 0.15); color: #30d158; }
.badge-tempo { background: rgba(10, 132, 255, 0.15); color: #0a84ff; }
.badge-interval { background: rgba(255, 159, 10, 0.15); color: #ff9f0a; }
.badge-long { background: rgba(175, 82, 222, 0.15); color: #af52de; }
.badge-trail { background: rgba(94, 92, 230, 0.15); color: #5e5ce6; }
.badge-cross { background: rgba(255, 55, 95, 0.15); color: #ff375f; }
.badge-race { background: rgba(255, 45, 85, 0.25); color: #ff375f; border: 1rpx solid rgba(255, 45, 85, 0.4); font-weight: bold; }
.badge-rest { background: rgba(142, 142, 147, 0.15); color: #8e8e93; }

.border-race { border-color: rgba(255, 45, 85, 0.45); background: linear-gradient(180deg, rgba(255, 45, 85, 0.12) 0%, rgba(26, 26, 30, 0.95) 100%); }

.workout-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #e5e5ea;
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
  color: #ffffff;
}

.dist-unit {
  font-size: 22rpx;
  color: #8e8e93;
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
  color: #af52de;
  background-color: #1c1c1e;
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
}

.metric-pill.hr-pill {
  color: #30d158;
}

.workout-desc {
  font-size: 22rpx;
  color: #aeaeb2;
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
  color: #ff9f0a;
  display: block;
  margin-bottom: 4rpx;
}

.coach-notes-content {
  font-size: 20rpx;
  color: #ffe0b2;
  line-height: 1.3;
  display: block;
}

.daily-card-actions {
  display: flex;
  gap: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
  padding-top: 14rpx;
}

.action-complete-btn {
  flex: 1;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 14rpx;
  background-color: #1c1c1e;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  font-size: 22rpx;
  color: #8e8e93;
}

.action-complete-btn.completed {
  background-color: rgba(48, 209, 88, 0.2);
  border-color: #30d158;
  color: #30d158;
  font-weight: bold;
}

.action-edit-btn {
  height: 56rpx;
  line-height: 56rpx;
  padding: 0 24rpx;
  border-radius: 14rpx;
  background-color: #1c1c1e;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  font-size: 22rpx;
  color: #af52de;
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
}

.modal-card {
  background-color: #18181c;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 32rpx;
  width: 100%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  padding: 30rpx;
  box-sizing: border-box;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
  padding-bottom: 16rpx;
  margin-bottom: 20rpx;
}

.modal-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.modal-close {
  font-size: 32rpx;
  color: #8e8e93;
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
  color: #8e8e93;
  margin-bottom: 8rpx;
  display: block;
}

.modal-input {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
  height: 64rpx;
  padding: 0 18rpx;
  font-size: 24rpx;
  color: #ffffff;
}

.modal-row {
  display: flex;
  gap: 16rpx;
}

.modal-textarea {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 16rpx;
  width: 100%;
  height: 120rpx;
  padding: 14rpx 18rpx;
  font-size: 22rpx;
  color: #ffffff;
  box-sizing: border-box;
}

.coach-notes-group {
  background-color: rgba(255, 159, 10, 0.06);
  border: 1rpx solid rgba(255, 159, 10, 0.2);
  border-radius: 20rpx;
  padding: 16rpx;
}

.coach-textarea {
  color: #ffe0b2;
}

.modal-footer {
  display: flex;
  gap: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
  padding-top: 20rpx;
}

.modal-cancel-btn {
  flex: 1;
  background-color: #1c1c1e;
  color: #8e8e93;
  font-size: 26rpx;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
}

.modal-save-btn {
  flex: 2;
  background-color: #af52de;
  color: #ffffff;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 72rpx;
  line-height: 72rpx;
}

/* ── GOAL ALIGNMENT & SYNC STYLES ── */
.goal-anchor-box {
  background: rgba(175, 82, 222, 0.1);
  border: 1rpx solid rgba(175, 82, 222, 0.25);
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
  color: #e9d5ff;
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
  color: #6ee7b7;
}

.align-down {
  background: rgba(14, 165, 233, 0.12);
  border-color: rgba(14, 165, 233, 0.3);
  color: #7dd3fc;
}

.align-race {
  background: rgba(244, 63, 94, 0.12);
  border-color: rgba(244, 63, 94, 0.35);
  color: #fda4af;
}

.align-climb {
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.3);
  color: #fcd34d;
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
  background: linear-gradient(135deg, rgba(147, 51, 234, 0.3), rgba(79, 70, 229, 0.3));
  border: 1rpx solid rgba(168, 85, 247, 0.4);
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
  color: #d8b4fe;
}
</style>
