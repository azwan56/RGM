<template>
  <view class="dashboard-page">
    <!-- Header: User Greeting & Avatar -->
    <view class="header-card">
      <view class="user-info">
        <image class="avatar" :src="dashboardData?.user?.avatar_url || user?.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
        <view class="text-group">
          <text class="greeting">欢迎回来，</text>
          <text class="user-name">{{ dashboardData?.user?.display_name || user?.display_name || "跑者" }}</text>
        </view>
      </view>
      <view class="garmin-badge" :class="{ active: isDeviceConnected }">
        <view class="pulse-dot" />
        <text class="badge-text">{{ deviceConnectedText }}</text>
      </view>
    </view>

    <!-- Goal Progress Hero Card (Dual View: Week / Month) -->
    <view class="hero-progress-card">
      <!-- Period Segmented Switcher -->
      <view class="goal-tab-header">
        <view
          class="goal-tab-btn"
          :class="{ active: activeGoalTab === 'week' }"
          @click="activeGoalTab = 'week'"
        >
          <text class="tab-icon">🏃</text>
          <text class="tab-text">本周跑量</text>
          <view v-if="(dashboardData?.weekly_progress?.progress_pct || 0) >= 100" class="tab-achieved-dot" />
        </view>
        <view
          class="goal-tab-btn"
          :class="{ active: activeGoalTab === 'month' }"
          @click="activeGoalTab = 'month'"
        >
          <text class="tab-icon">📅</text>
          <text class="tab-text">当月跑量</text>
          <view v-if="(dashboardData?.progress?.progress_pct || 0) >= 100" class="tab-achieved-dot" />
        </view>
      </view>

      <!-- Week View -->
      <view v-if="activeGoalTab === 'week'" class="goal-tab-content">
        <!-- Two-Level Spacious Header -->
        <view class="goal-header-block">
          <view class="goal-header-top">
            <text class="goal-main-title">本周跑量进度</text>
            <text class="goal-top-pct text-emerald">
              {{ dashboardData?.weekly_progress?.progress_pct ?? 0 }}%
            </text>
          </view>
          <view class="goal-header-sub">
            <text class="cycle-summary-chip">{{ dashboardData?.weekly_progress?.week_label || '本周' }}</text>
            <view class="quick-set-trigger" @click="openWeeklyGoalModal">
              <text class="quick-set-icon">⚙️ 调整周目标</text>
            </view>
          </view>
        </view>

        <view class="progress-bar-bg">
          <view
            class="progress-bar-fill fill-emerald"
            :style="{ width: Math.min(100, dashboardData?.weekly_progress?.progress_pct || 0) + '%' }"
          />
        </view>

        <view class="stats-grid">
          <view class="stat-item">
            <text class="stat-val text-emerald">{{ dashboardData?.weekly_progress?.current_week_km ?? 0 }}</text>
            <text class="stat-label">已跑 (km)</text>
          </view>
          <view class="stat-item divider clickable-stat" @click="openWeeklyGoalModal">
            <view class="stat-val-with-edit">
              <text class="stat-val">{{ dashboardData?.weekly_progress?.target_week_km ?? 50 }}</text>
              <text class="edit-badge">✏️</text>
            </view>
            <text class="stat-label">目标 (km)</text>
          </view>
          <view class="stat-item divider">
            <text class="stat-val">{{ dashboardData?.weekly_progress?.remaining_km ?? 0 }}</text>
            <text class="stat-label">剩余 (km)</text>
          </view>
          <view class="stat-item">
            <text class="stat-val accent-text">{{ dashboardData?.weekly_progress?.daily_required_km ?? 0 }}</text>
            <text class="stat-label">日均需跑 (km)</text>
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

        <!-- ── 今日训练课目 (Today's Scheduled Workout) ── -->
        <view class="today-workout-container">
          <view
            v-if="dashboardData?.today_workout"
            class="today-workout-card"
            :class="[getTodayWorkoutBorderClass(dashboardData.today_workout.workout_type), { 'is-completed': dashboardData.today_workout.completed }]"
          >
            <view class="tw-header">
              <view class="tw-header-left">
                <text class="tw-icon">📅</text>
                <text class="tw-section-title">今日训练课目</text>
                <text class="tw-badge" :class="getWorkoutBadgeClass(dashboardData.today_workout.workout_type)">
                  {{ getWorkoutTypeLabel(dashboardData.today_workout.workout_type) }}
                </text>
              </view>
              <view class="tw-header-right" @click="goToCoachPage">
                <text v-if="dashboardData.today_workout.completed && dashboardData.today_workout.actual_distance_km" class="tw-actual-badge">
                  实跑 {{ dashboardData.today_workout.actual_distance_km }}k
                </text>
                <text class="tw-link">完整课表 ›</text>
              </view>
            </view>

            <view class="tw-body">
              <view class="tw-title-row">
                <text class="tw-title">{{ dashboardData.today_workout.title }}</text>
                <view v-if="dashboardData.today_workout.workout_type !== 'rest'" class="tw-dist">
                  <text class="tw-dist-num">{{ dashboardData.today_workout.distance_km || 0 }}</text>
                  <text class="tw-dist-unit">km</text>
                </view>
              </view>

              <!-- Target Pace & HR Zone -->
              <view
                v-if="dashboardData.today_workout.workout_type !== 'rest' && (dashboardData.today_workout.target_pace || dashboardData.today_workout.target_hr_zone)"
                class="tw-metrics"
              >
                <text v-if="dashboardData.today_workout.target_pace && dashboardData.today_workout.target_pace !== '—'" class="tw-metric-tag pace-tag">
                  ⏱️ {{ dashboardData.today_workout.target_pace }}
                </text>
                <text v-if="dashboardData.today_workout.target_hr_zone && dashboardData.today_workout.target_hr_zone !== '—'" class="tw-metric-tag hr-tag">
                  ❤️ {{ dashboardData.today_workout.target_hr_zone }}
                </text>
              </view>

              <!-- Description -->
              <text class="tw-desc">{{ dashboardData.today_workout.description }}</text>

              <!-- Coach Notes -->
              <view v-if="dashboardData.today_workout.coach_notes" class="tw-coach-notes">
                <text class="tw-coach-title">👨‍🏫 教练批注：</text>
                <text class="tw-coach-text">{{ dashboardData.today_workout.coach_notes }}</text>
              </view>
            </view>

            <!-- Bottom Actions -->
            <view class="tw-actions">
              <button
                class="tw-complete-btn"
                :class="{ completed: dashboardData.today_workout.completed }"
                :loading="togglingWorkout"
                @click="handleTodayWorkoutToggle"
              >
                <text class="btn-text">
                  {{ dashboardData.today_workout.completed ? (dashboardData.today_workout.actual_distance_km ? `✅ 今日已打卡 ${dashboardData.today_workout.actual_distance_km}km` : '✅ 今日课表已完成') : '今日打卡' }}
                </text>
              </button>
              <button class="tw-detail-btn" @click="goToCoachPage">
                <text class="btn-text">查看 12 周课表</text>
              </button>
            </view>
          </view>

          <!-- Fallback when no active plan is scheduled for today -->
          <view v-else class="today-workout-card empty-card" @click="goToCoachPage">
            <view class="empty-tw-content">
              <text class="empty-tw-icon">💡</text>
              <view class="empty-tw-texts">
                <text class="empty-tw-title">今日暂无专属计划课表</text>
                <text class="empty-tw-sub">点击前往「AI教练」，定制科学周期训练课表 ›</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- Month View -->
      <view v-else class="goal-tab-content">
        <view class="goal-header-block">
          <view class="goal-header-top">
            <text class="goal-main-title">当月跑量目标</text>
            <text class="goal-top-pct primary-text">{{ dashboardData?.progress?.progress_pct || 0 }}%</text>
          </view>
          <view class="goal-header-sub">
            <text class="cycle-summary-chip">{{ currentMonth }}月进度 · 剩 {{ dashboardData?.progress?.days_left_in_month ?? 0 }} 天</text>
          </view>
        </view>

        <view class="progress-bar-bg">
          <view
            class="progress-bar-fill"
            :style="{ width: Math.min(100, dashboardData?.progress?.progress_pct || 0) + '%' }"
          />
        </view>

        <view class="stats-grid">
          <view class="stat-item">
            <text class="stat-val primary-text">{{ dashboardData?.progress?.current_month_km || 0 }}</text>
            <text class="stat-label">已跑 (km)</text>
          </view>
          <view class="stat-item divider">
            <text class="stat-val">{{ dashboardData?.progress?.target_month_km || 200 }}</text>
            <text class="stat-label">目标 (km)</text>
          </view>
          <view class="stat-item divider">
            <text class="stat-val">{{ dashboardData?.progress?.remaining_km || 0 }}</text>
            <text class="stat-label">剩余 (km)</text>
          </view>
          <view class="stat-item">
            <text class="stat-val accent-text">{{ dashboardData?.progress?.daily_required_km || 0 }}</text>
            <text class="stat-label">日均需跑 (km)</text>
          </view>
        </view>
      </view>

      <!-- Instant Sync Action Button (Garmin / COROS) -->
      <view class="sync-action-box">
        <button class="sync-btn" :loading="syncing" :disabled="syncing" @click="handleInstantSync">
          <text class="btn-icon">⚡</text>
          <text>{{ syncing ? ("正在从 " + syncDeviceName + " 同步...") : ("一键同步 " + syncDeviceName + " 数据") }}</text>
        </button>
      </view>
    </view>

    <!-- ── CARD 0: 体能与状况指数 (Fitness & Form) ── -->
    <view class="section-container">
      <view class="section-header-row">
        <view class="title-with-desc">
          <text class="section-title">⚡ 体能与状况指数 (Fitness & Form)</text>
          <text class="sub-formula">基于标准 Banister TRIMP 与 EWMA 模型算法</text>
        </view>
        <view class="metrics-pill-group">
          <view class="metric-pill">
            <text class="pill-label">CTL 体能</text>
            <text class="pill-val text-cyan">{{ dashboardData?.fitness_form?.ctl ?? 0 }}</text>
          </view>
          <view class="metric-pill">
            <text class="pill-label">ATL 疲劳</text>
            <text class="pill-val text-pink">{{ dashboardData?.fitness_form?.atl ?? 0 }}</text>
          </view>
          <view class="metric-pill">
            <text class="pill-label">TSB 状况</text>
            <text
              class="pill-val"
              :style="{ color: dashboardData?.fitness_form?.status_color || '#6b7280' }"
            >
              {{ (dashboardData?.fitness_form?.tsb ?? 0) > 0 ? '+' : '' }}{{ dashboardData?.fitness_form?.tsb ?? 0 }}
            </text>
          </view>
        </view>
      </view>

      <view class="fitness-chart-card">
        <template v-if="dashboardData?.fitness_form?.history && dashboardData.fitness_form.history.length > 0">
          <!-- Tooltip Bubble when tapped -->
          <view v-if="activeTooltip" class="chart-tooltip">
            <text class="tip-date">{{ activeTooltip.short_date || activeTooltip.date }}</text>
            <text class="tip-val text-cyan">CTL: {{ activeTooltip.ctl }}</text>
            <text class="tip-val text-pink">ATL: {{ activeTooltip.atl }}</text>
            <text class="tip-val" :style="{ color: activeTooltip.tsb_color || '#0ea5e9' }">
              TSB: {{ activeTooltip.tsb > 0 ? '+' : '' }}{{ activeTooltip.tsb }} ({{ activeTooltip.tsb_label || '训练中' }})
            </text>
          </view>

          <!-- Native Canvas Fitness & Form Chart (Supported across all MiniApp platforms) -->
          <canvas
            canvas-id="fitnessChartCanvas"
            id="fitnessChartCanvas"
            class="fitness-chart-canvas"
            @touchstart="handleCanvasTouch"
            @touchmove="handleCanvasTouch"
          />

          <!-- Color-Coded Legend (matching Web) -->
          <view class="chart-legend-row">
            <view class="legend-item">
              <view class="line-dot cyan" />
              <text class="legend-text">体能 (CTL): 42天长期压力</text>
            </view>
            <view class="legend-item">
              <view class="line-dot pink" />
              <text class="legend-text">疲劳 (ATL): 7天近期压力</text>
            </view>
          </view>
          <view class="chart-legend-row tsb-tags-row">
            <view class="legend-item">
              <view class="rect-dot green" />
              <text class="legend-text">+5以上 巅峰</text>
            </view>
            <view class="legend-item">
              <view class="rect-dot blue" />
              <text class="legend-text">-30~+5 训练中</text>
            </view>
            <view class="legend-item">
              <view class="rect-dot yellow" />
              <text class="legend-text">-50~-30 疲劳</text>
            </view>
            <view class="legend-item">
              <view class="rect-dot red" />
              <text class="legend-text">-50以下 严重</text>
            </view>
          </view>
        </template>
        <view v-else class="empty-chart-box">
          <text class="empty-chart-icon">📊</text>
          <text class="empty-chart-title">暂无体能负荷数据</text>
          <text class="empty-chart-desc">在【我的】页面绑定 Garmin 或高驰手表并同步跑步记录后，将基于 Banister TRIMP 模型自动生成 42 天 CTL/ATL/TSB 趋势分析。</text>
        </view>
      </view>
    </view>

    <!-- ── CARD 1: 生理与恢复 4 格卡片 (Garmin / COROS 自适应) ── -->
    <view class="section-container">
      <view class="section-header-row">
        <text class="section-title">{{ healthCardTitle }}</text>
        <text class="sub-date">更新于: {{ dashboardData?.today_health?.date || "今日" }}</text>
      </view>

      <view class="health-grid-4">
        <!-- 1. 睡眠恢复 -->
        <view class="health-tile">
          <view class="tile-top">
            <text class="tile-icon">🛏️</text>
            <text class="tile-name">睡眠恢复</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val">{{ dashboardData?.today_health?.sleep_score != null ? dashboardData.today_health.sleep_score : '—' }}</text>
            <text class="tile-unit" v-if="dashboardData?.today_health?.sleep_score != null">分</text>
          </view>
          <text class="tile-sub">{{ dashboardData?.today_health?.sleep_duration_text ? ('时长 ' + dashboardData.today_health.sleep_duration_text) : (isCorosOnly ? '需高驰App端查看' : '未同步睡眠') }}</text>
        </view>

        <!-- 2. 静息心率 -->
        <view class="health-tile">
          <view class="tile-top">
            <text class="tile-icon">💓</text>
            <text class="tile-name">静息心率 (RHR)</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val text-rose">{{ currentRestingHr != null ? currentRestingHr : '—' }}</text>
            <text class="tile-unit" v-if="currentRestingHr != null">bpm</text>
          </view>
          <text class="tile-sub">{{ isCorosOnly ? '高驰清晨生理基线' : '清晨生理基线' }}</text>
        </view>

        <!-- 3. 身体电量 (Garmin) 或 体能储备 (COROS / Banister TSB) -->
        <view class="health-tile" v-if="!isCorosOnly">
          <view class="tile-top">
            <text class="tile-icon">⚡</text>
            <text class="tile-name">身体电量</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val text-amber">{{ dashboardData?.today_health?.body_battery_max != null ? (dashboardData.today_health.body_battery_max + '%') : '—' }}</text>
          </view>
          <view class="mini-progress-bg" v-if="dashboardData?.today_health?.body_battery_max != null">
            <view
              class="mini-progress-fill"
              :style="{ width: Math.min(100, dashboardData.today_health.body_battery_max) + '%' }"
            />
          </view>
          <text class="tile-sub" v-else>电量监控</text>
        </view>
        <view class="health-tile" v-else>
          <view class="tile-top">
            <text class="tile-icon">⚡</text>
            <text class="tile-name">体能储备 (TSB)</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val" :style="{ color: dashboardData?.fitness_form?.status_color || '#22c55e' }">
              {{ dashboardData?.fitness_form?.tsb != null ? ((dashboardData.fitness_form.tsb > 0 ? '+' : '') + dashboardData.fitness_form.tsb.toFixed(1)) : '—' }}
            </text>
          </view>
          <text class="tile-sub">{{ dashboardData?.fitness_form?.status_label ? ('状态: ' + dashboardData.fitness_form.status_label) : 'Banister 状态平衡' }}</text>
        </view>

        <!-- 4. 夜间 HRV 或 VO2Max (COROS) -->
        <view class="health-tile" v-if="!isCorosOnly || (dashboardData?.today_health?.hrv_ms != null)">
          <view class="tile-top">
            <text class="tile-icon">🫀</text>
            <text class="tile-name">夜间 HRV</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val text-cyan">{{ dashboardData?.today_health?.hrv_ms != null ? dashboardData.today_health.hrv_ms : '—' }}</text>
            <text class="tile-unit" v-if="dashboardData?.today_health?.hrv_ms != null">ms</text>
          </view>
          <text class="tile-sub">{{ dashboardData?.today_health?.hrv_weekly_avg != null ? ('周均: ' + dashboardData.today_health.hrv_weekly_avg + ' ms') : '夜间自主神经' }}</text>
        </view>
        <view class="health-tile" v-else>
          <view class="tile-top">
            <text class="tile-icon">🫁</text>
            <text class="tile-name">最大摄氧量</text>
          </view>
          <view class="tile-val-row">
            <text class="tile-main-val text-cyan">{{ currentVo2Max != null ? currentVo2Max : '—' }}</text>
            <text class="tile-unit" v-if="currentVo2Max != null">ml/kg</text>
          </view>
          <text class="tile-sub">EvoLab 耐力潜能</text>
        </view>
      </view>
    </view>

    <!-- ── CARD 1.5: 2026 年度跑量统计图表 (Yearly Running Mileage Chart) ── -->
    <view class="section-container yearly-section">
      <view class="section-header-row">
        <view class="title-with-desc">
          <text class="section-title">🏆 {{ dashboardData?.yearly_stats?.year || 2026 }} 年度跑量统计</text>
          <text class="sub-formula">
            年度目标 {{ dashboardData?.yearly_stats?.target_year_km || 3560 }} km · 月均目标 {{ dashboardData?.yearly_stats?.monthly_target_km || 296.7 }} km
          </text>
        </view>
        <view class="year-pct-badge">
          <text class="year-pct-num">{{ dashboardData?.yearly_stats?.progress_pct || 0 }}%</text>
          <text class="year-pct-sub">完成度</text>
        </view>
      </view>

      <view class="year-card-body">
        <!-- 1. 年度累计进度条 -->
        <view class="year-progress-box">
          <view class="year-progress-labels">
            <text class="progress-left-label">
              已累计完成 <text class="highlight-val">{{ dashboardData?.yearly_stats?.total_km || 0 }}</text> km
            </text>
            <text class="progress-right-label">
              剩余 {{ Math.max(0, Math.round(((dashboardData?.yearly_stats?.target_year_km || 3560) - (dashboardData?.yearly_stats?.total_km || 0)) * 10) / 10) }} km
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
            <text class="tip-text-dim">💡 点击单月柱状图可查看当月里程与跑次</text>
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
            <text class="m-desc">全年累计运动</text>
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
            <text class="m-desc">已过月份均值</text>
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
            <text class="m-desc">按当前趋势预测</text>
          </view>
        </view>

        <!-- 4. 年度最佳月份横幅 -->
        <view class="year-best-banner">
          <text class="best-badge">🏅 年度最佳月份</text>
          <text class="best-info">
            {{ dashboardData?.yearly_stats?.best_month?.name || "5月" }} · 
            <text class="best-km">{{ dashboardData?.yearly_stats?.best_month?.distance_km || 0 }} km</text>
            <text class="best-pace" v-if="dashboardData?.yearly_stats?.best_month?.avg_pace">（配速 {{ dashboardData?.yearly_stats?.best_month?.avg_pace }}）</text>
          </text>
        </view>
      </view>
    </view>

    <!-- ── CARD 2: 近期跑步记录 (最近 3 次) ── -->
    <view class="section-container">
      <view class="section-header-row">
        <text class="section-title">近期跑步记录</text>
        <text class="sub-date">最近 3 次训练</text>
      </view>

      <view v-if="dashboardData?.recent_activities?.length" class="activity-list">
        <view
          v-for="act in dashboardData.recent_activities.slice(0, 3)"
          :key="act.id"
          class="activity-card"
        >
          <view class="act-top">
            <text class="act-name">{{ act.name }}</text>
            <text class="act-time">{{ formatTime(act.start_time) }}</text>
          </view>
          <view class="act-data-row">
            <view class="act-col">
              <text class="act-main-val">{{ act.distance_km }} <text class="unit">km</text></text>
              <text class="act-sub-label">跑步距离</text>
            </view>
            <view class="act-col">
              <text class="act-sub-val">{{ act.avg_pace_str }}</text>
              <text class="act-sub-label">平均配速</text>
            </view>
            <view class="act-col">
              <text class="act-sub-val">{{ act.average_heartrate || '—' }} <text class="unit">bpm</text></text>
              <text class="act-sub-label">平均心率</text>
            </view>
            <view class="act-col">
              <text class="act-sub-val text-amber">{{ act.trimp || '—' }}</text>
              <text class="act-sub-label">TRIMP负荷</text>
            </view>
          </view>
        </view>
      </view>
      <view v-else class="empty-act-box">
        <text class="empty-act-text">暂无运动记录，请在【我的】页面绑定 Garmin 或高驰手表自动同步</text>
      </view>
    </view>

    <!-- ── 进入小程序首先弹窗：微信跑者授权登录专属弹窗 ── -->
    <view v-if="showAuthModal" class="modal-mask" @click="closeAuthModal" @touchmove.stop.prevent>
      <view class="modal-content auth-modal-content" @click.stop="noop">
        <view class="modal-header">
          <text class="modal-title">微信跑者授权登录</text>
          <view class="close-hit" @click="closeAuthModal">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="modal-body">
          <view class="wx-brand-hero">
            <text class="wx-hero-icon">🏃</text>
            <text class="wx-hero-title">RGM 跑团助手</text>
            <text class="wx-hero-desc">科学耐力训练 · Garmin 数据直连 · 独立跑者档案</text>
          </view>

          <view class="auth-flow-box">
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

    <!-- ── 快速调整周跑量目标弹窗 ── -->
    <view v-if="showWeeklyGoalModal" class="modal-mask" @click="closeWeeklyGoalModal" @touchmove.stop.prevent>
      <view class="modal-content weekly-goal-modal" @click.stop="noop">
        <view class="modal-header">
          <view class="title-with-icon">
            <text class="title-icon">🏃</text>
            <text class="modal-title">设定每周常规跑量目标</text>
          </view>
          <view class="close-hit" @click="closeWeeklyGoalModal">
            <text class="close-btn">✕</text>
          </view>
        </view>

        <view class="modal-body">
          <view class="w-modal-desc">
            <text>设定适合您的常规每周跑量，自动应用于全年的每周训练进度与 7 天分布追踪，可随时单独调整。</text>
          </view>

          <!-- Current Target Banner -->
          <view class="w-target-display-card">
            <view class="w-target-num-row">
              <text class="w-target-big-num">{{ editWeeklyTarget }}</text>
              <text class="w-target-big-unit">km / 周</text>
            </view>
            <text class="w-target-equiv-label">相当于月均约 {{ Math.round(editWeeklyTarget * 4.3) }} km 跑步负荷</text>
          </view>

          <!-- Quick selection pills -->
          <text class="w-pills-label">常用周跑量快捷选择：</text>
          <view class="w-modal-pills">
            <view
              v-for="km in [30, 40, 50, 60, 70, 80, 100]"
              :key="km"
              class="w-modal-pill"
              :class="{ active: editWeeklyTarget === km }"
              @click="editWeeklyTarget = km"
            >
              {{ km }}k
            </view>
          </view>

          <!-- Slider -->
          <view class="w-modal-slider-box">
            <slider
              :value="editWeeklyTarget"
              :min="10"
              :max="160"
              :step="5"
              activeColor="#10b981"
              backgroundColor="#2c2c2e"
              block-size="22"
              @change="(e: any) => editWeeklyTarget = Number(e.detail.value) || 50"
            />
            <view class="w-slider-extremes">
              <text>10 km</text>
              <text>160 km</text>
            </view>
          </view>

          <!-- Action Buttons -->
          <view class="w-modal-action-row">
            <button class="w-cancel-btn" @click="closeWeeklyGoalModal">取消</button>
            <button class="w-save-btn" :loading="savingWeeklyModal" @click="saveWeeklyGoalModal">
              保存并立即生效
            </button>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from "vue";
import { onPullDownRefresh, onShow } from "@dcloudio/uni-app";
import {
  request,
  getStoredUser,
  authenticateWechatUser,
  switchAccount,
  uploadAvatarFile,
  UserProfile,
} from "../../utils/api";

const showAuthModal = ref(false);
const runnerNickName = ref("");
const runnerAvatar = ref("");
const recentAccounts = ref<any[]>([]);
const agreedTerms = ref(false);
const confirmingLogin = ref(false);
const defaultAvatar =
  "https://thirdwx.qlogo.cn/mmopen/vi_32/POgEwh4mIHO4nibH0KlMECNjjGxQUq24ZEaGT4poC6icRiccVGKSyXwibcPq4ozAawiaYbCQTvDVxp4UMxN5UulpDixA/132";

const defaultWeeklyDays = [
  { day_idx: 0, day_name: "周一", short_day: "一", date: "--/--", distance_km: 0, runs_count: 0, is_today: false, is_past: true },
  { day_idx: 1, day_name: "周二", short_day: "二", date: "--/--", distance_km: 0, runs_count: 0, is_today: false, is_past: true },
  { day_idx: 2, day_name: "周三", short_day: "三", date: "--/--", distance_km: 0, runs_count: 0, is_today: false, is_past: true },
  { day_idx: 3, day_name: "周四", short_day: "四", date: "--/--", distance_km: 0, runs_count: 0, is_today: false, is_past: true },
  { day_idx: 4, day_name: "周五", short_day: "五", date: "--/--", distance_km: 0, runs_count: 0, is_today: false, is_past: false },
  { day_idx: 5, day_name: "周六", short_day: "六", date: "--/--", distance_km: 0, runs_count: 0, is_today: false, is_past: false },
  { day_idx: 6, day_name: "周日", short_day: "日", date: "--/--", distance_km: 0, runs_count: 0, is_today: false, is_past: false },
];

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
    trend: [
      { month_label: "2026/4月", distance_km: 0.0, count: 0, is_current: false },
      { month_label: "2026/5月", distance_km: 0.0, count: 0, is_current: false },
      { month_label: "2026/6月", distance_km: 0.0, count: 0, is_current: false },
      { month_label: "2026/7月", distance_km: 0.0, count: 0, is_current: false },
      { month_label: "2026/8月", distance_km: 0.0, count: 0, is_current: false },
      { month_label: "2026/9月", distance_km: 0.0, count: 0, is_current: true },
    ],
    current_month_km: 0.0,
    prev_month_km: 0.0,
    pct_change: 0.0,
    recent_3_months: [
      { month_label: "2026/7月", distance_km: 0.0, count: 0 },
      { month_label: "2026/8月", distance_km: 0.0, count: 0 },
      { month_label: "2026/9月", distance_km: 0.0, count: 0 },
    ],
  },
  yearly_stats: {
    year: 2026,
    total_km: 0.0,
    total_runs: 0,
    avg_monthly_km: 0.0,
    projected_year_km: 0.0,
    target_year_km: 3560.0,
    monthly_target_km: 296.7,
    progress_pct: 0.0,
    best_month: {
      name: "—",
      distance_km: 0.0,
      avg_pace: "—",
    },
    monthly_breakdown: [
      { month: 1, month_label: "1月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
      { month: 2, month_label: "2月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
      { month: 3, month_label: "3月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
      { month: 4, month_label: "4月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
      { month: 5, month_label: "5月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
      { month: 6, month_label: "6月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
      { month: 7, month_label: "7月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
      { month: 8, month_label: "8月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
      { month: 9, month_label: "9月", distance_km: 0, runs_count: 0, is_current: true, is_past: false },
      { month: 10, month_label: "10月", distance_km: 0, runs_count: 0, is_current: false, is_past: false },
      { month: 11, month_label: "11月", distance_km: 0, runs_count: 0, is_current: false, is_past: false },
      { month: 12, month_label: "12月", distance_km: 0, runs_count: 0, is_current: false, is_past: false },
    ],
  },
  today_health: null,
  recent_activities: [],
  ai_coach_tip: "欢迎使用 RGM 跑团助手！请在【我的】页面登录微信并绑定佳明设备以开启科学耐力训练分析。",
};

const defaultMonthlyBreakdown = [
  { month: 1, month_label: "1月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
  { month: 2, month_label: "2月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
  { month: 3, month_label: "3月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
  { month: 4, month_label: "4月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
  { month: 5, month_label: "5月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
  { month: 6, month_label: "6月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
  { month: 7, month_label: "7月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
  { month: 8, month_label: "8月", distance_km: 0, runs_count: 0, is_current: false, is_past: true },
  { month: 9, month_label: "9月", distance_km: 0, runs_count: 0, is_current: true, is_past: false },
  { month: 10, month_label: "10月", distance_km: 0, runs_count: 0, is_current: false, is_past: false },
  { month: 11, month_label: "11月", distance_km: 0, runs_count: 0, is_current: false, is_past: false },
  { month: 12, month_label: "12月", distance_km: 0, runs_count: 0, is_current: false, is_past: false },
];

const user = ref<UserProfile | null>(null);
const dashboardData = ref<any>(emptyData);
const activeGoalTab = ref<'week' | 'month'>('week');
const syncing = ref(false);
const currentMonth = ref(new Date().getMonth() + 1);
const activeTooltip = ref<any>(null);
const selectedYearMonth = ref<any>(null);
const showWeeklyGoalModal = ref(false);
const editWeeklyTarget = ref(50);
const savingWeeklyModal = ref(false);
const togglingWorkout = ref(false);

const isCorosOnly = computed(() => {
  const u = dashboardData.value?.user || user.value;
  return !!u?.coros_connected && !u?.garmin_connected;
});

const isDeviceConnected = computed(() => {
  const u = dashboardData.value?.user || user.value;
  return !!(u?.garmin_connected || u?.coros_connected);
});

const deviceConnectedText = computed(() => {
  const u = dashboardData.value?.user || user.value;
  if (u?.garmin_connected && u?.coros_connected) return "佳明/高驰已连接";
  if (u?.coros_connected) return "高驰已连接";
  if (u?.garmin_connected) return "佳明已连接";
  return "未绑定手表";
});

const syncDeviceName = computed(() => {
  const u = dashboardData.value?.user || user.value;
  if (u?.garmin_connected && u?.coros_connected) return "佳明与高驰";
  if (u?.coros_connected) return "高驰 (COROS)";
  if (u?.garmin_connected) return "Garmin";
  return "运动手表";
});

const healthCardTitle = computed(() => {
  if (isCorosOnly.value) return "高驰 COROS 生理与状态指标";
  const u = dashboardData.value?.user || user.value;
  if (u?.garmin_connected && u?.coros_connected) return "佳明 & 高驰 生理与状态指标";
  return "Garmin 生理与恢复指标";
});

const currentRestingHr = computed(() => {
  return (
    dashboardData.value?.today_health?.resting_heart_rate ??
    dashboardData.value?.user?.resting_heart_rate ??
    user.value?.resting_heart_rate ??
    null
  );
});

const currentVo2Max = computed(() => {
  return (
    dashboardData.value?.today_health?.vo2_max ??
    dashboardData.value?.user?.vo2max ??
    user.value?.vo2max ??
    null
  );
});

function goToCoachPage() {
  uni.switchTab({
    url: "/pages/coach/coach",
    fail: () => {
      uni.navigateTo({ url: "/pages/coach/coach" });
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
        uni.showToast({ title: "今日已打卡！", icon: "success" });
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

function openWeeklyGoalModal() {
  editWeeklyTarget.value = dashboardData.value?.weekly_progress?.target_week_km || 50;
  showWeeklyGoalModal.value = true;
}

function closeWeeklyGoalModal() {
  showWeeklyGoalModal.value = false;
}

async function saveWeeklyGoalModal() {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  savingWeeklyModal.value = true;
  try {
    const tgt = Number(editWeeklyTarget.value) || 50;
    await request(`/api/profile/${encodeURIComponent(uid)}/goal`, "PUT", {
      weekly_target: tgt,
    });

    if (dashboardData.value?.weekly_progress) {
      const curKm = Number(dashboardData.value.weekly_progress.current_week_km) || 0;
      dashboardData.value.weekly_progress.target_week_km = tgt;
      dashboardData.value.weekly_progress.progress_pct = tgt > 0 ? Math.round((curKm / tgt) * 1000) / 10 : 0;
      dashboardData.value.weekly_progress.remaining_km = Math.max(0, Math.round((tgt - curKm) * 10) / 10);
      const daysLeft = dashboardData.value.weekly_progress.days_left_in_week || 1;
      dashboardData.value.weekly_progress.daily_required_km = Math.round((dashboardData.value.weekly_progress.remaining_km / daysLeft) * 10) / 10;
    }

    showWeeklyGoalModal.value = false;
    uni.showToast({ title: `周跑量目标已设为 ${tgt}km`, icon: "success" });
  } catch (err: any) {
    uni.showToast({ title: err?.message || "保存失败", icon: "none" });
  } finally {
    savingWeeklyModal.value = false;
  }
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

function drawFitnessChart() {
  const ctx = uni.createCanvasContext("fitnessChartCanvas");
  if (!ctx) return;

  const history = dashboardData.value?.fitness_form?.history || [];
  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const W = Math.min(350, screenW - 40);
  const H = 190;

  if (!history.length) {
    ctx.clearRect(0, 0, W, H);
    ctx.draw();
    return;
  }
  const padL = 30;
  const padR = 8;
  const padT = 18;
  const padB = 24;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const minY = -45;
  const maxY = 135;

  const getY = (val: number) => {
    const clamped = Math.max(minY, Math.min(maxY, val));
    return padT + (plotH * (maxY - clamped)) / (maxY - minY);
  };

  const getX = (idx: number) => {
    if (history.length <= 1) return padL;
    return padL + (idx / (history.length - 1)) * plotW;
  };

  const yZero = getY(0);

  // Clear
  ctx.clearRect(0, 0, W, H);

  // 1. Gridlines & Y-Axis Labels
  const gridVals = [135, 90, 45, 0, -45];
  gridVals.forEach((val) => {
    const y = getY(val);
    ctx.setStrokeStyle(val === 0 ? "#383842" : "#1e1e24");
    ctx.setLineWidth(1);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();

    ctx.setFontSize(9);
    ctx.setFillStyle(val === 0 ? "#8e8e93" : "#55555c");
    ctx.setTextAlign("right");
    ctx.fillText(String(val), padL - 4, y + 3);
  });

  // 2. TSB Bars
  const barW = Math.max(2.5, Math.min(6, (plotW / history.length) * 0.45));
  history.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const yVal = getY(item.tsb);
    const barX = x - barW / 2;
    const barY = Math.min(yZero, yVal);
    const barH = Math.max(2, Math.abs(yVal - yZero));

    let color = item.tsb_color;
    if (!color) {
      if (item.tsb > 5) color = "#22c55e";
      else if (item.tsb >= -30) color = "#1890ff";
      else if (item.tsb >= -50) color = "#eab308";
      else color = "#ef4444";
    }

    ctx.setFillStyle(color);
    ctx.fillRect(barX, barY, barW, barH);
  });

  // 3. CTL Curve (Cyan #38bdf8)
  ctx.setStrokeStyle("#38bdf8");
  ctx.setLineWidth(2.5);
  ctx.setLineCap("round");
  ctx.setLineJoin("round");
  ctx.beginPath();
  history.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const y = getY(item.ctl);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // 4. ATL Curve (Pink #ec4899)
  ctx.setStrokeStyle("#ec4899");
  ctx.setLineWidth(2.5);
  ctx.setLineCap("round");
  ctx.setLineJoin("round");
  ctx.beginPath();
  history.forEach((item: any, idx: number) => {
    const x = getX(idx);
    const y = getY(item.atl);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // 5. X-Axis Date Labels
  ctx.setFontSize(8.5);
  ctx.setFillStyle("#66666e");
  ctx.setTextAlign("center");
  const step = Math.max(1, Math.floor(history.length / 5));
  for (let i = 0; i < history.length; i += step) {
    const x = getX(i);
    const text = history[i].short_date || history[i].date?.slice(5) || "";
    ctx.fillText(text, x, H - 4);
  }
  if (history.length > 0) {
    const lastIdx = history.length - 1;
    const text = history[lastIdx].short_date || history[lastIdx].date?.slice(5) || "";
    ctx.fillText(text, getX(lastIdx), H - 4);
  }

  // 6. Draw active indicator line if touched
  if (activeTooltip.value) {
    const activeIdx = history.findIndex((h: any) => h.date === activeTooltip.value.date);
    if (activeIdx >= 0) {
      const activeX = getX(activeIdx);
      ctx.setStrokeStyle("rgba(255,255,255,0.4)");
      ctx.setLineWidth(1);
      ctx.beginPath();
      ctx.moveTo(activeX, padT);
      ctx.lineTo(activeX, H - padB);
      ctx.stroke();
    }
  }

  ctx.draw();
}

function handleCanvasTouch(e: any) {
  const history = dashboardData.value?.fitness_form?.history || [];
  if (!history.length || !e.touches || !e.touches[0]) return;
  const touchX = e.touches[0].x;
  const sysInfo = uni.getSystemInfoSync();
  const screenW = sysInfo.windowWidth || 375;
  const W = Math.min(350, screenW - 40);
  const padL = 30;
  const padR = 8;
  const plotW = W - padL - padR;

  const relX = Math.max(0, Math.min(plotW, touchX - padL));
  const idx = Math.round((relX / plotW) * (history.length - 1));
  if (idx >= 0 && idx < history.length) {
    activeTooltip.value = history[idx];
    drawFitnessChart();
  }
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
    await loadDashboard();
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

async function loadDashboard() {
  user.value = getStoredUser();
  if (!user.value || !user.value.id) {
    openAuthModal();
    return;
  }
  const uid = user.value.id;

  try {
    const data = await request(`/api/miniapp/dashboard/${uid}`);
    if (data && data.progress) {
      dashboardData.value = data;
      if (data.user) {
        if (!user.value) user.value = {} as any;
        if (data.user.avatar_url) user.value.avatar_url = data.user.avatar_url;
        if (data.user.display_name) user.value.display_name = data.user.display_name;
        if (data.user.coros_connected !== undefined) user.value.coros_connected = data.user.coros_connected;
        if (data.user.garmin_connected !== undefined) user.value.garmin_connected = data.user.garmin_connected;
        if (data.user.resting_heart_rate !== undefined) user.value.resting_heart_rate = data.user.resting_heart_rate;
        if (data.user.vo2max !== undefined) user.value.vo2max = data.user.vo2max;
        uni.setStorageSync("rgm_user", user.value);
      }
      nextTick(() => {
        setTimeout(drawFitnessChart, 150);
      });
    }
  } catch (e) {
    console.warn("Dashboard fetch fallback:", e);
  }
}

async function handleInstantSync() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  syncing.value = true;
  uni.showLoading({ title: `同步 ${syncDeviceName.value} 中...` });
  try {
    const res = await request("/api/sync/trigger", "POST", { uid });
    uni.hideLoading();
    if (res?.success === false) {
      uni.showModal({
        title: "同步提示",
        content: res?.error || `${syncDeviceName.value}连接中，请稍后刷新重试`,
        showCancel: false,
      });
    } else {
      uni.showToast({ title: "同步成功", icon: "success" });
    }
    await loadDashboard();
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: "同步已触发", icon: "success" });
  } finally {
    syncing.value = false;
  }
}

function formatTime(isoStr?: string): string {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${m}-${day} ${h}:${min}`;
}

function goToActivities() {
  uni.switchTab({ url: "/pages/activities/activities" });
}

onMounted(() => {
  nextTick(() => {
    setTimeout(drawFitnessChart, 200);
  });
});

onShow(() => {
  loadDashboard();
  nextTick(() => {
    setTimeout(drawFitnessChart, 250);
  });
});

onPullDownRefresh(async () => {
  try {
    await loadDashboard();
    uni.showToast({ title: "数据已更新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新数据", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});
</script>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 36rpx 28rpx 90rpx 28rpx;
  box-sizing: border-box;
}

.header-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 38rpx;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
}

.avatar {
  width: 96rpx;
  height: 96rpx;
  border-radius: 48rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.12);
}

.text-group {
  display: flex;
  flex-direction: column;
}

.greeting {
  font-size: 24rpx;
  color: #8e8e93;
}

.user-name {
  font-size: 34rpx;
  font-weight: bold;
  color: #ffffff;
}

.garmin-badge {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 10rpx 22rpx;
  border-radius: 30rpx;
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.pulse-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 6rpx;
  background-color: #636366;
}

.garmin-badge.active .pulse-dot {
  background-color: #34c759;
}

.badge-text {
  font-size: 22rpx;
  color: #8e8e93;
}

.garmin-badge.active .badge-text {
  color: #34c759;
}

.hero-progress-card {
  background: linear-gradient(135deg, #1c1c1e 0%, #141416 100%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 36rpx 32rpx;
  margin-bottom: 46rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.5);
}

.goal-tab-header {
  display: flex;
  background-color: #121214;
  border-radius: 20rpx;
  padding: 6rpx;
  margin-bottom: 28rpx;
  gap: 10rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
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
  background-color: #2c2c2e;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 4rpx 12rpx rgba(0, 0, 0, 0.35);
}

.tab-icon {
  font-size: 24rpx;
}

.tab-text {
  font-size: 24rpx;
  font-weight: 600;
  color: #8e8e93;
}

.goal-tab-btn.active .tab-text {
  color: #ffffff;
  font-weight: bold;
}

.tab-achieved-dot {
  width: 10rpx;
  height: 10rpx;
  background-color: #34d399;
  border-radius: 50%;
  margin-left: 4rpx;
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
  color: #ffffff;
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
  color: #a1a1aa;
  background-color: rgba(255, 255, 255, 0.08);
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
  color: #34d399;
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
  color: #8e8e93;
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
  color: #34d399;
  line-height: 1;
}

.w-target-big-unit {
  font-size: 24rpx;
  color: #34d399;
  font-weight: bold;
}

.w-target-equiv-label {
  font-size: 20rpx;
  color: #a1a1aa;
  margin-top: 8rpx;
}

.w-pills-label {
  font-size: 22rpx;
  color: #a1a1aa;
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
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 14rpx;
  font-size: 22rpx;
  color: #d4d4d8;
  font-weight: 600;
  transition: all 0.2s ease;
}

.w-modal-pill.active {
  background-color: #10b981;
  border-color: #10b981;
  color: #ffffff;
  box-shadow: 0 4rpx 12rpx rgba(16, 185, 129, 0.4);
}

.w-modal-slider-box {
  margin-bottom: 32rpx;
}

.w-slider-extremes {
  display: flex;
  justify-content: space-between;
  font-size: 18rpx;
  color: #71717a;
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
  line-height: 84rpx;
  background-color: #242429;
  color: #a1a1aa;
  font-size: 26rpx;
  font-weight: 600;
  border-radius: 20rpx;
  border: none;
}

.w-save-btn {
  flex: 2;
  height: 84rpx;
  line-height: 84rpx;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #ffffff;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 20rpx;
  border: none;
  box-shadow: 0 6rpx 20rpx rgba(16, 185, 129, 0.4);
}

.progress-bar-bg {
  width: 100%;
  height: 16rpx;
  background-color: #2c2c2e;
  border-radius: 8rpx;
  overflow: hidden;
  margin-bottom: 32rpx;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #fc4c02 0%, #ff833a 100%);
  border-radius: 8rpx;
  transition: width 0.3s ease;
}

.progress-bar-fill.fill-emerald {
  background: linear-gradient(90deg, #10b981 0%, #34d399 100%);
}

.week-days-strip {
  display: flex;
  justify-content: space-between;
  gap: 8rpx;
  margin-bottom: 26rpx;
  padding: 16rpx 10rpx;
  background-color: #121214;
  border-radius: 20rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.04);
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
  color: #71717a;
  font-weight: 600;
  margin-bottom: 4rpx;
}

.day-strip-col.is-today .d-name {
  color: #34d399;
}

.d-date {
  font-size: 16rpx;
  color: #52525b;
  margin-bottom: 10rpx;
}

.day-strip-col.is-today .d-date {
  color: #a1a1aa;
}

.d-val-pill {
  min-width: 42rpx;
  height: 38rpx;
  padding: 0 6rpx;
  border-radius: 10rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #1a1a1e;
}

.d-val-pill.active-run {
  background-color: rgba(16, 185, 129, 0.2);
  border: 1rpx solid #10b981;
}

.d-km-num {
  font-size: 18rpx;
  font-weight: 800;
  color: #34d399;
}

.d-km-dash {
  font-size: 16rpx;
  color: #52525b;
}

/* ── TODAY'S WORKOUT PLAN CARD (IN WEEK VIEW) ── */
.today-workout-container {
  margin-top: 10rpx;
  margin-bottom: 20rpx;
}

.today-workout-card {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 24rpx 20rpx;
  transition: all 0.2s ease;
}

.today-workout-card.is-completed {
  border-color: rgba(48, 209, 88, 0.4);
  background-color: rgba(48, 209, 88, 0.03);
}

.today-workout-card.tw-border-race {
  border-color: rgba(255, 45, 85, 0.45);
  background: linear-gradient(180deg, rgba(255, 45, 85, 0.08) 0%, rgba(26, 26, 30, 0.95) 100%);
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
  color: #ffffff;
}

.tw-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
}

.tw-badge-easy { background: rgba(48, 209, 88, 0.15); color: #30d158; }
.tw-badge-tempo { background: rgba(10, 132, 255, 0.15); color: #0a84ff; }
.tw-badge-interval { background: rgba(255, 159, 10, 0.15); color: #ff9f0a; }
.tw-badge-long { background: rgba(175, 82, 222, 0.15); color: #af52de; }
.tw-badge-trail { background: rgba(94, 92, 230, 0.15); color: #5e5ce6; }
.tw-badge-cross { background: rgba(255, 55, 95, 0.15); color: #ff375f; }
.tw-badge-race { background: rgba(255, 45, 85, 0.25); color: #ff375f; border: 1rpx solid rgba(255, 45, 85, 0.4); font-weight: bold; }
.tw-badge-rest { background: rgba(142, 142, 147, 0.15); color: #8e8e93; }

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
  color: #30d158;
  border: 1rpx solid rgba(48, 209, 88, 0.3);
}

.tw-link {
  font-size: 22rpx;
  color: #a1a1aa;
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
  color: #f4f4f5;
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
  color: #ffffff;
}

.tw-dist-unit {
  font-size: 22rpx;
  color: #a1a1aa;
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
  background-color: #1c1c1e;
  color: #af52de;
}

.tw-metric-tag.hr-tag {
  background-color: #1c1c1e;
  color: #30d158;
}

.tw-desc {
  font-size: 22rpx;
  color: #a1a1aa;
  line-height: 1.45;
  display: block;
  margin-bottom: 12rpx;
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
  color: #ff9f0a;
  display: block;
  margin-bottom: 4rpx;
}

.tw-coach-text {
  font-size: 20rpx;
  color: #ffe0b2;
  line-height: 1.35;
  display: block;
}

.tw-actions {
  display: flex;
  gap: 14rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
  padding-top: 16rpx;
}

.tw-complete-btn {
  flex: 1;
  height: 60rpx;
  line-height: 60rpx;
  border-radius: 14rpx;
  background-color: #1c1c1e;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  font-size: 24rpx;
  color: #e4e4e7;
  font-weight: 600;
}

.tw-complete-btn.completed {
  background-color: rgba(48, 209, 88, 0.2);
  border-color: #30d158;
  color: #30d158;
  font-weight: bold;
}

.tw-detail-btn {
  height: 60rpx;
  line-height: 60rpx;
  padding: 0 24rpx;
  border-radius: 14rpx;
  background-color: #1c1c1e;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  font-size: 22rpx;
  color: #af52de;
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
  color: #e4e4e7;
}

.empty-tw-sub {
  font-size: 22rpx;
  color: #71717a;
  margin-top: 4rpx;
}

.stats-grid {
  display: flex;
  justify-content: space-between;
  background-color: #121214;
  border-radius: 24rpx;
  padding: 26rpx 12rpx;
  margin-bottom: 26rpx;
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-item.divider {
  border-right: 1rpx solid rgba(255, 255, 255, 0.05);
}

.stat-val {
  font-size: 32rpx;
  font-weight: bold;
  color: #ffffff;
}

.primary-text {
  color: #fc4c02;
}

.accent-text {
  color: #ff9f0a;
}

.stat-label {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 6rpx;
}

.sync-action-box {
  margin-top: 12rpx;
}

.sync-btn {
  background: linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
  height: 88rpx;
  border: none;
}

.btn-icon {
  font-size: 30rpx;
}

/* Sections & Spacings */
.section-container {
  margin-bottom: 48rpx;
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
  color: #ffffff;
}

.sub-date {
  font-size: 22rpx;
  color: #636366;
}

.health-grid-4 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 22rpx;
}

.health-tile {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 28rpx;
  padding: 28rpx 24rpx;
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
  color: #8e8e93;
}

.tile-val-row {
  display: flex;
  align-items: baseline;
  gap: 6rpx;
}

.tile-main-val {
  font-size: 38rpx;
  font-weight: bold;
  color: #ffffff;
}

.tile-unit {
  font-size: 20rpx;
  color: #8e8e93;
}

.text-rose {
  color: #ff453a;
}

.text-amber {
  color: #ffd60a;
}

.text-cyan {
  color: #30d158;
}

.tile-sub {
  font-size: 20rpx;
  color: #636366;
  margin-top: 10rpx;
}

.mini-progress-bg {
  width: 100%;
  height: 8rpx;
  background-color: #2c2c2e;
  border-radius: 4rpx;
  margin-top: 16rpx;
  overflow: hidden;
}

.mini-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ffd60a 0%, #30d158 100%);
}

/* Fitness & Form Card Styles */
.title-with-desc {
  display: flex;
  flex-direction: column;
}

.sub-formula {
  font-size: 20rpx;
  color: #71717a;
  margin-top: 4rpx;
}

.metrics-pill-group {
  display: flex;
  gap: 12rpx;
}

.metric-pill {
  background-color: #1a1a1e;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 8rpx 16rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pill-label {
  font-size: 16rpx;
  color: #8e8e93;
  font-weight: bold;
  text-transform: uppercase;
}

.pill-val {
  font-size: 26rpx;
  font-weight: 900;
  margin-top: 2rpx;
}

.text-cyan {
  color: #38bdf8;
}

.text-pink {
  color: #ec4899;
}

.fitness-chart-card {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 24rpx 20rpx 20rpx;
  position: relative;
}

.chart-tooltip {
  background-color: rgba(22, 22, 26, 0.95);
  border: 1rpx solid rgba(255, 255, 255, 0.2);
  border-radius: 16rpx;
  padding: 10rpx 16rpx;
  display: flex;
  gap: 14rpx;
  align-items: center;
  margin-bottom: 12rpx;
  font-size: 20rpx;
}

.tip-date {
  color: #ffffff;
  font-weight: bold;
}

.tip-val {
  font-weight: bold;
}

.fitness-chart-canvas {
  width: 100%;
  height: 380rpx;
  display: block;
}

.chart-legend-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24rpx;
  margin-top: 14rpx;
}

.chart-legend-row.tsb-tags-row {
  gap: 20rpx;
  margin-top: 8rpx;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.line-dot {
  width: 20rpx;
  height: 6rpx;
  border-radius: 4rpx;
}

.line-dot.cyan {
  background-color: #38bdf8;
}

.line-dot.pink {
  background-color: #ec4899;
}

.rect-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 4rpx;
}

.rect-dot.green { background-color: #22c55e; }
.rect-dot.blue { background-color: #1890ff; }
.rect-dot.yellow { background-color: #eab308; }
.rect-dot.red { background-color: #ef4444; }

.legend-text {
  font-size: 18rpx;
  color: #8e8e93;
}

/* Recent Activities Styles */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.empty-act-box {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 24rpx;
  padding: 40rpx 24rpx;
  text-align: center;
}

.empty-act-text {
  font-size: 24rpx;
  color: #636366;
}

.activity-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 28rpx;
  padding: 28rpx 24rpx;
}

.act-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.act-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.act-time {
  font-size: 22rpx;
  color: #8e8e93;
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
  color: #fc4c02;
}

.act-sub-val {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.act-sub-label {
  font-size: 20rpx;
  color: #636366;
  margin-top: 6rpx;
}

.unit {
  font-size: 20rpx;
  color: #8e8e93;
  font-weight: normal;
}

.text-amber {
  color: #ffd60a;
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
}

.modal-content {
  width: 670rpx;
  background-color: #18181c;
  border-radius: 36rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 20rpx 60rpx rgba(0, 0, 0, 0.8);
  overflow: hidden;
  margin-bottom: 80rpx;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 36rpx 36rpx 20rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
}

.modal-title {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
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
  color: #8e8e93;
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

.field-label {
  font-size: 24rpx;
  color: #aeaeb2;
  margin-top: 12rpx;
  margin-bottom: 6rpx;
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
  color: #f43f5e;
  line-height: 1.1;
}

.year-pct-sub {
  font-size: 18rpx;
  color: #a1a1aa;
}

.year-card-body {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 32rpx 28rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.4);
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
  color: #a1a1aa;
}

.highlight-val {
  font-weight: 900;
  color: #ffffff;
  font-size: 28rpx;
}

.progress-right-label {
  color: #71717a;
}

.year-progress-track {
  width: 100%;
  height: 16rpx;
  background-color: #242429;
  border-radius: 8rpx;
  overflow: hidden;
}

.year-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #f43f5e 0%, #fb7185 60%, #f59e0b 100%);
  border-radius: 8rpx;
  transition: width 0.4s ease;
}

/* 12-Month Bar Chart */
.monthly-chart-box {
  background-color: #17171b;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 24rpx;
  padding: 20rpx 16rpx 16rpx 16rpx;
}

.selected-month-tip {
  background-color: #202026;
  border-radius: 14rpx;
  padding: 10rpx 16rpx;
  margin-bottom: 16rpx;
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 22rpx;
  color: #e4e4e7;
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
  color: #e4e4e7;
}

.tip-hl {
  font-weight: bold;
  color: #f43f5e;
}

.tip-tag.current {
  color: #34d399;
  font-weight: bold;
  font-size: 20rpx;
  margin-left: 6rpx;
}

.tip-text-dim {
  font-size: 20rpx;
  color: #71717a;
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
  color: #a1a1aa;
  font-weight: 600;
  text-align: center;
}

.bar-km-empty {
  font-size: 16rpx;
}

.bar-pillar-track {
  width: 22rpx;
  height: 160rpx;
  background-color: rgba(255, 255, 255, 0.04);
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
}

.past-fill {
  background: linear-gradient(180deg, #fb7185 0%, #e11d48 100%);
}

.zero-fill {
  background: rgba(255, 255, 255, 0.08);
}

.bar-month-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 10rpx;
}

.month-name {
  font-size: 18rpx;
  color: #71717a;
}

.month-bar-col.is-current .month-name {
  color: #34d399;
  font-weight: bold;
}

.month-bar-col.is-selected .month-name {
  color: #ffffff;
  font-weight: bold;
}

.current-indicator-dot {
  width: 6rpx;
  height: 6rpx;
  border-radius: 3rpx;
  background-color: #34d399;
  margin-top: 4rpx;
}

/* 3 Metric Tiles */
.year-metrics-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16rpx;
  margin-top: 24rpx;
}

.year-metric-tile {
  background-color: #17171b;
  border: 1rpx solid rgba(255, 255, 255, 0.05);
  border-radius: 20rpx;
  padding: 20rpx 16rpx;
  display: flex;
  flex-direction: column;
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
  color: #8e8e93;
}

.m-val-box {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.m-val {
  font-size: 30rpx;
  font-weight: 900;
  color: #ffffff;
}

.m-unit {
  font-size: 18rpx;
  color: #71717a;
}

.m-desc {
  font-size: 18rpx;
  color: #52525b;
  margin-top: 4rpx;
}

.text-emerald {
  color: #34d399 !important;
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
  color: #f59e0b;
}

.best-info {
  font-size: 22rpx;
  color: #d4d4d8;
}

.best-km {
  font-weight: 800;
  color: #ffffff;
}

.best-pace {
  font-size: 20rpx;
  color: #a1a1aa;
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
  color: #ffffff;
  margin-bottom: 12rpx;
  display: block;
}

.empty-chart-desc {
  font-size: 22rpx;
  color: #8e8e93;
  line-height: 1.6;
  max-width: 500rpx;
  display: block;
}
</style>
