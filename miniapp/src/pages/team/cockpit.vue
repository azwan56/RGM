<template>
  <view class="cockpit-page" :class="themeClass">
    <!-- 加载中骨架屏（原先加载时整页空白） -->
    <PageSkeleton v-if="loading" :header="false" />
    <!-- ── Permission Check: Only Owner / Coach ── -->
    <view v-if="!loading && !isAuthorized" class="unauthorized-card">
      <text class="lock-icon">🧢</text>
      <text class="unauth-title">跑团教练工作台</text>
      <text class="unauth-desc">仅限认证教练与团长，请联系团长授权</text>
      <view style="display: flex; gap: 16rpx; justify-content: center; margin-top: 12rpx;">
        <button class="back-btn" style="flex: 1;" @click="goToPersonalTrain">🏃 个人训练课表</button>
        <button class="back-btn" style="flex: 1;" @click="goBack">🏆 前往跑团中心</button>
      </view>
    </view>

    <!-- ── Authorized Cockpit View ── -->
    <view v-else-if="!loading" class="cockpit-content">
      <!-- Top Club Header -->
      <view class="top-club-bar">
        <view class="club-info" @click="userClubs.length > 1 ? (showSwitchModal = true) : null">
          <view class="title-with-arrow">
            <text class="club-title">{{ currentClub?.name || "教练工作台" }}</text>
            <text v-if="userClubs.length > 1" class="switch-arrow">▾</text>
          </view>
        </view>
        <view class="top-right-group">
          <text class="role-badge" :class="'role-' + userRole">
            {{ userRole === 'owner' ? '👑 团长' : '🧢 教练' }}
          </text>
          <text v-if="userClubs.length > 1" class="switch-link-pill" @click="showSwitchModal = true">
            ⇄ 切换
          </text>
        </view>
      </view>

      <!-- Multi-Club Quick Pill Switcher (if coach belongs to >1 club) -->
      <scroll-view v-if="coachedClubs.length > 1" scroll-x class="coach-clubs-strip" show-scrollbar="false">
        <view class="coach-clubs-inner">
          <text class="ccs-label">执教跑团:</text>
          <view
            v-for="cc in coachedClubs"
            :key="cc.id"
            class="ccs-pill"
            :class="{ active: currentClub?.id === cc.id }"
            @click="handleSwitchClub(cc)"
          >
            {{ cc.name }} ({{ cc.role === 'owner' ? '团长' : '教练' }})
          </view>
        </view>
      </scroll-view>

      <!-- ── Centralized 4-Module Coach Workbench Sub-Navigation ── -->
      <view class="coach-workbench-tabs">
        <view
          class="cwt-tab"
          :class="{ active: coachBenchTab === 'cockpit' }"
          @click="switchBenchTab('cockpit')"
        >
          <text class="cwt-icon">🧭</text>
          <text class="cwt-label">罗盘</text>
        </view>
        <view
          class="cwt-tab"
          :class="{ active: coachBenchTab === 'feed' }"
          @click="switchBenchTab('feed')"
        >
          <text class="cwt-icon">💬</text>
          <text class="cwt-label">点评</text>
        </view>
        <view
          class="cwt-tab"
          :class="{ active: coachBenchTab === 'events' }"
          @click="switchBenchTab('events')"
        >
          <text class="cwt-icon">🏃</text>
          <text class="cwt-label">约跑</text>
        </view>
        <view
          class="cwt-tab"
          :class="{ active: coachBenchTab === 'report_manage' }"
          @click="switchBenchTab('report_manage')"
        >
          <text class="cwt-icon">📊</text>
          <text class="cwt-label">战报</text>
        </view>
      </view>

      <!-- ==================== MODULE 1: 排课与全队体能罗盘 ==================== -->
      <view v-if="coachBenchTab === 'cockpit'">
      <!-- 4-Grid Status Overview -->
      <view class="status-summary-grid">
        <view
          class="status-card green"
          :class="{ active: filterStatus === 'peak' }"
          @click="setFilter('peak')"
        >
          <view class="status-top">
            <text class="status-dot">🟢</text>
            <text class="status-name">巅峰</text>
          </view>
          <text class="status-count">{{ summary?.peak_count || 0 }} <text class="unit">人</text></text>
        </view>

        <view
          class="status-card blue"
          :class="{ active: filterStatus === 'optimal' }"
          @click="setFilter('optimal')"
        >
          <view class="status-top">
            <text class="status-dot">🔵</text>
            <text class="status-name">适应</text>
          </view>
          <text class="status-count">{{ summary?.optimal_count || 0 }} <text class="unit">人</text></text>
        </view>

        <view
          class="status-card yellow"
          :class="{ active: filterStatus === 'tired' }"
          @click="setFilter('tired')"
        >
          <view class="status-top">
            <text class="status-dot">🟡</text>
            <text class="status-name">疲劳</text>
          </view>
          <text class="status-count">{{ summary?.tired_count || 0 }} <text class="unit">人</text></text>
        </view>

        <view
          class="status-card red"
          :class="{ active: filterStatus === 'danger' }"
          @click="setFilter('danger')"
        >
          <view class="status-top">
            <text class="status-dot">🔴</text>
            <text class="status-name">预警</text>
          </view>
          <text class="status-count">{{ summary?.danger_count || 0 }} <text class="unit">人</text></text>
        </view>
      </view>

      <!-- ── 全团选兔雷达 · 官方配速员与拉练领跑兔选拔 ── -->
      <PacerClubRadarSection
        v-if="currentClub?.id && user?.id"
        :club-id="currentClub.id"
        :operator-uid="user.id"
        :club-name="currentClub.name"
      ></PacerClubRadarSection>

      <!-- ── Coach Training Plan & Execution Management Hub (教练排课与执行管理台) ── -->
      <view class="coach-plan-hub-card">
        <view class="cph-header">
          <view class="cph-badge-row">
            <view style="display: flex; align-items: center; gap: 8rpx;">
              <text class="cph-pill">🧢 排课管理</text>
              <text class="term-info" @click.stop="explainTerm('coach_hub')">ⓘ</text>
            </view>
            <text class="cph-compliance">周达成 {{ summary?.avg_week_compliance || 0 }}%</text>
          </view>
        </view>

        <!-- 2x2 Symmetrical Batch Action Grid -->
        <view class="cph-actions-grid">
          <button
            class="cph-batch-btn pipeline"
            :disabled="filteredStudents.length === 0"
            @click="startPipelineReview"
          >
            🚀 流水线 ({{ filteredStudents.length }})
          </button>
          <button
            class="cph-batch-btn template-btn"
            @click="openTemplateAssignModal()"
          >
            📚 模版库
          </button>
          <button
            class="cph-batch-btn broadcast"
            @click="showBroadcastModal = true"
          >
            📢 合练派课
          </button>
          <button
            class="cph-batch-btn primary"
            :disabled="batchGenerating"
            @click="handleBatchGenerateDrafts(true)"
          >
            {{ batchGenerating ? '生成中...' : '✨ 批量排草案' }}
          </button>
        </view>

        <!-- Concise Plan Status Filter Chips -->
        <view class="cph-filter-row">
          <view
            class="cph-filter-chip"
            :class="{ active: filterPlanState === 'all' && filterStatus === 'all' && filterGroupCode === 'all' }"
            @click="resetAllFilters"
          >
            全部 ({{ students.length }})
          </view>
          <view
            class="cph-filter-chip draft"
            :class="{ active: filterPlanState === 'draft_pending' }"
            @click="filterPlanState = filterPlanState === 'draft_pending' ? 'all' : 'draft_pending'"
          >
            🟠 待审 ({{ summary?.plans_draft_count || 0 }})
          </view>
          <view
            class="cph-filter-chip pub"
            :class="{ active: filterPlanState === 'published' }"
            @click="filterPlanState = filterPlanState === 'published' ? 'all' : 'published'"
          >
            🟢 执行 ({{ summary?.plans_published_count || 0 }})
          </view>
          <view
            class="cph-filter-chip none"
            :class="{ active: filterPlanState === 'none' }"
            @click="filterPlanState = filterPlanState === 'none' ? 'all' : 'none'"
          >
            ⚪ 未排 ({{ summary?.plans_none_count || 0 }})
          </view>
          <view
            class="cph-filter-chip injury"
            :class="{ active: filterPlanState === 'injury_alert' }"
            @click="filterPlanState = filterPlanState === 'injury_alert' ? 'all' : 'injury_alert'"
          >
            🚨 预警 ({{ injuryAlertCount }})
          </view>
        </view>

        <!-- Integrated Search & Sort Row -->
        <view class="cph-search-sort-row">
          <input
            class="student-search-input"
            type="text"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="🔍 搜索学员..."
            v-model="searchQuery"
          />
          <view class="sort-chip-group">
            <view
              class="sort-chip"
              :class="{ active: sortBy === 'danger_first' }"
              @click="setSortBy('danger_first')"
            >
              🔴 预警↓
            </view>
            <view
              class="sort-chip"
              :class="{ active: sortBy === 'peak_first' }"
              @click="setSortBy('peak_first')"
            >
              🟢 巅峰↓
            </view>
            <text class="term-info" @click.stop="explainTerm('tsb')">ⓘ</text>
          </view>
        </view>
      </view>

      <!-- Student Cards List -->
      <view class="students-list">
        <view
          v-for="s in filteredStudents"
          :key="s.user_id"
          class="student-card"
          :class="['border-' + s.status_level, s.plan_info?.plan_state === 'draft_pending' ? 'card-has-draft' : '']"
        >
          <!-- Student Top Row -->
          <view class="student-header">
            <view class="student-profile">
              <image
                class="student-avatar"
                :src="s.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                mode="aspectFill"
              />
              <view class="student-name-box">
                <view class="name-row">
                  <text class="student-name">{{ s.display_name }}</text>
                  <text v-if="s.role === 'owner'" class="mini-tag owner">团长</text>
                  <text v-else-if="s.role === 'coach'" class="mini-tag coach">教练</text>
                  <text v-if="s.plan_info?.plan_state === 'draft_pending'" class="mini-tag draft-tag">🟠 草案待审</text>
                  <text v-else-if="s.plan_info?.plan_state === 'published'" class="mini-tag pub-tag">🟢 教练已发布</text>
                  <text v-else-if="s.plan_info?.plan_state === 'self_active'" class="mini-tag self-tag">🔵 个人计划</text>
                  <text v-if="s.gender_label || s.age" class="mini-tag self-tag">
                    {{ s.gender_label ? s.gender_label : '' }}{{ s.age ? (s.gender_label ? '·' : '') + s.age + '岁' : '' }}
                  </text>
                  <text
                    v-if="s.plan_info?.template_group_code"
                    class="mini-tag tpl-tag"
                    @click.stop="openTemplateAssignModal(s.plan_info.template_id, s.user_id)"
                  >
                    📚 {{ s.plan_info.template_group_code }}
                  </text>
                  <text
                    v-else-if="s.recommended_group"
                    class="mini-tag tpl-rec-tag"
                    @click.stop="openTemplateAssignModal(s.recommended_group.template_id, s.user_id)"
                  >
                    🎯 荐:{{ s.recommended_group.group_code }}{{ s.recommended_group.recommended_scale && s.recommended_group.recommended_scale < 1 ? '(' + Math.round(s.recommended_group.recommended_scale * 100) + '%量)' : '' }}
                  </text>
                </view>
                <view class="student-sub-meta">
                  <text class="student-month-km">当月跑量: <text class="highlight">{{ s.month_km }} / {{ s.target_km || 200 }} km</text></text>
                  <text v-if="s.marathon_pb" class="student-month-km">全马PB: <text class="highlight">{{ s.marathon_pb }}</text></text>
                  <text v-if="s.goal_race" class="student-race-pill">🏁 {{ s.goal_race.name }}{{ (s.goal_race.days_until ?? s.goal_race.days_left) != null ? ` (${s.goal_race.days_until ?? s.goal_race.days_left}天)` : '' }}</text>
                </view>
                <view v-if="s.recommended_group?.reason" class="student-rec-reason-line">
                  <text class="student-rec-reason-txt">🧭 {{ s.recommended_group.reason }}</text>
                </view>
              </view>
            </view>

            <!-- Status Level Badge -->
            <view class="status-badge" :class="'badge-' + s.status_level">
              {{ s.status_level === 'peak' ? '🟢 巅峰' : s.status_level === 'optimal' ? '🔵 适应' : s.status_level === 'tired' ? '🟡 疲劳' : '🔴 预警' }}
            </view>
          </view>

          <!-- Metrics 6-Grid -->
          <view class="metrics-grid">
            <view class="metric-cell">
              <text class="m-label">CTL 体能</text>
              <text class="m-val text-blue">{{ s.ctl }}</text>
            </view>
            <view class="metric-cell">
              <text class="m-label">ATL 疲劳</text>
              <text class="m-val text-purple">{{ s.atl }}</text>
            </view>
            <view class="metric-cell">
              <text class="m-label">TSB 状况</text>
              <text class="m-val" :class="s.ctl > 0 || s.atl > 0 ? (s.tsb >= 0 ? 'text-green' : 'text-yellow') : 'text-muted'">
                {{ (s.ctl > 0 || s.atl > 0) ? (s.tsb > 0 ? '+' + s.tsb : s.tsb) : '—' }}
              </text>
            </view>
            <view class="metric-cell">
              <text class="m-label">静息心率</text>
              <text class="m-val text-rose">{{ s.resting_heart_rate ? s.resting_heart_rate : '—' }} <text class="m-unit" v-if="s.resting_heart_rate">bpm</text></text>
            </view>
            <view class="metric-cell">
              <text class="m-label">夜间 HRV <text class="term-info" @click.stop="explainTerm('hrv')">ⓘ</text></text>
              <text class="m-val text-cyan">{{ s.hrv_ms ? s.hrv_ms : '—' }} <text class="m-unit" v-if="s.hrv_ms">ms</text></text>
            </view>
            <view class="metric-cell">
              <text class="m-label">睡眠恢复</text>
              <text class="m-val text-emerald">{{ s.sleep_score ? s.sleep_score : '—' }} <text class="m-unit" v-if="s.sleep_score">分</text></text>
            </view>
          </view>

          <!-- 夜间未佩戴手表 · 恢复数据缺失预警（教练端精简一行 + ⓘ 说明） -->
          <view
            v-if="s.night_wear_missing"
            style="margin: 10rpx 0 14rpx 0; padding: 10rpx 16rpx; border-radius: 12rpx; background: rgba(245, 158, 11, 0.14); border: 1rpx solid rgba(245, 158, 11, 0.45); display: flex; align-items: center; justify-content: space-between;"
            @click.stop="explainTerm('watch_wear')"
          >
            <text style="font-size: 21rpx; font-weight: 700; color: #b45309;">
              ⚠️ 夜间未佩戴 · 恢复数据缺失（暂停强度建议）
            </text>
            <text style="font-size: 20rpx; font-weight: 700; color: #b45309; flex-shrink: 0; margin-left: 10rpx;">ⓘ</text>
          </view>

          <!-- ── NEW: Weekly Training Plan & 7-Day Execution Strip ── -->
          <view v-if="s.plan_info?.week_execution" class="student-plan-exec-box" @click="openStudentPlanModal(s)">
            <view class="spe-top-row">
              <view class="spe-title-col">
                <text class="spe-plan-title">📋 {{ s.plan_info.title || '周期训练课表' }}</text>
                <text class="spe-week-sub">
                  W{{ s.plan_info.week_execution.week_number }} · {{ s.plan_info.week_execution.theme }}
                </text>
              </view>
              <view class="spe-stats-col">
                <text class="spe-km-text">
                  <text class="spe-actual">{{ s.plan_info.week_execution.actual_km }}</text>
                  /{{ s.plan_info.week_execution.planned_km }}km
                </text>
                <text class="spe-rate-pill" :class="s.plan_info.week_execution.compliance_rate >= 80 ? 'good' : 'normal'">
                  完成度 {{ s.plan_info.week_execution.compliance_rate }}% · 力量{{ s.plan_info.week_execution.strength_count || 0 }}次
                </text>
              </view>
            </view>

            <!-- W19 Summary Banner & Injury/Self-Summary Alerts -->
            <view v-if="s.plan_info.week_execution.summary_banner_text" class="spe-w19-banner">
              <text class="spe-w19-text">📊 {{ s.plan_info.week_execution.summary_banner_text }}</text>
            </view>
            <view v-if="s.plan_info.week_execution.injury_note || s.plan_info.week_execution.athlete_weekly_summary" class="spe-feedback-row">
              <text v-if="s.plan_info.week_execution.injury_note && s.plan_info.week_execution.injury_note !== '无'" class="spe-injury-pill">
                🩹 伤痛: {{ s.plan_info.week_execution.injury_note }}
              </text>
              <text v-if="s.plan_info.week_execution.athlete_weekly_summary" class="spe-summary-pill">
                💬 体感: {{ s.plan_info.week_execution.athlete_weekly_summary }}
              </text>
            </view>

            <!-- 7-Day Mini Execution Strip -->
            <view v-if="s.plan_info.week_execution.days_brief?.length" class="spe-days-strip">
              <view
                v-for="(d, dIdx) in s.plan_info.week_execution.days_brief"
                :key="dIdx"
                class="spe-day-cell"
                :class="['day-' + d.status, d.hrv_warning ? 'hrv-warn' : '']"
              >
                <text class="spe-day-name">{{ d.day_of_week.replace('周', '') }}{{ d.swapped_from ? '⇄' : '' }}</text>
                <text class="spe-day-icon">
                  {{ d.status === 'completed' ? '✅' : d.status === 'missed' ? '⚠️' : d.status === 'rest' ? '🛌' : '⏳' }}
                </text>
                <text class="spe-day-km">
                  {{ d.status === 'rest' ? '休' : (d.status === 'completed' ? (d.actual_km || d.planned_km) + 'k' : d.planned_km + 'k') }}
                </text>
                <text v-if="d.rpe" class="spe-day-rpe">R{{ d.rpe }}</text>
              </view>
            </view>
          </view>
          <view v-else class="student-no-plan-bar" @click="openStudentPlanModal(s)">
            <text class="snp-text">⚪ 未排课表</text>
            <text class="snp-link">去排课 ›</text>
          </view>

          <!-- Coach Advice Box (skip duplicate paragraph when night_wear_missing banner is already shown above) -->
          <view v-if="!s.night_wear_missing" class="advice-box">
            <text class="advice-icon">💡</text>
            <text class="advice-text">{{ s.coach_diagnosis || s.status_text }}</text>
          </view>

          <!-- Primary Coach Plan Review & Action Row -->
          <view class="student-action-footer" style="display:flex;gap:14rpx;">
            <button
              class="coach-plan-action-btn"
              style="flex:1.6;"
              :class="s.plan_info?.plan_state === 'draft_pending' ? 'btn-draft' : s.plan_info?.has_active_plan ? 'btn-active' : 'btn-create'"
              @click="openStudentPlanModal(s)"
            >
              {{
                s.plan_info?.plan_state === 'draft_pending'
                  ? '🟠 审核微调'
                  : s.plan_info?.has_active_plan
                  ? '📋 调课/打卡'
                  : '✨ 定制课表'
              }}
            </button>
            <button
              class="coach-plan-action-btn"
              style="flex:1;background:rgba(6,182,212,0.14);border:1rpx solid rgba(6,182,212,0.38);color:var(--rgm-blue, #22d3ee);font-weight:700;white-space:nowrap;"
              @click.stop="openStudentScienceAnalysis(s)"
            >
              📊 VDOT ›
            </button>
          </view>
        </view>

        <!-- Empty State for Filtered Students -->
        <view v-if="filteredStudents.length === 0" class="cockpit-empty-card">
          <text class="cec-icon">👥</text>
          <text class="cec-title">暂无符合条件的队员</text>
          <text class="cec-sub">可尝试切换顶部体能状态或排课状态筛选</text>
        </view>
      </view>
      </view>

      <!-- ==================== MODULE 2: 队员打卡动态与教练点评台 ==================== -->
      <view v-else-if="coachBenchTab === 'feed'" class="cwb-module-box">
        <view class="cwb-sec-header">
          <view>
            <text class="cwb-sec-title">💬 打卡点评</text>
          </view>
          <button class="cwb-mini-btn" @click="loadClubCoachExtras(currentClub?.id)">↻ 刷新</button>
        </view>

        <view v-if="loadingFeed" class="pm-loading-box">
          <text class="pm-loading-text">加载中...</text>
        </view>
        <view v-else-if="clubFeed.length === 0" class="empty-box">
          <text class="empty-text">暂无打卡记录</text>
        </view>
        <view v-else class="cwb-feed-list">
          <view v-for="act in clubFeed" :key="act.id" class="cwb-feed-card">
            <view class="cwb-fc-top">
              <view class="cwb-fc-user">
                <image
                  class="cwb-fc-avatar"
                  :src="act.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                  mode="aspectFill"
                />
                <view>
                  <view class="cwb-fc-name-row">
                    <text class="cwb-fc-name">{{ act.display_name }}</text>
                    <text class="cwb-fc-time">{{ (act.start_time || '').slice(5, 16).replace('T', ' ') }}</text>
                  </view>
                  <text class="cwb-fc-actname">{{ act.name || '日常耐力训练' }}</text>
                </view>
              </view>
              <view class="cwb-fc-dist">
                <text class="cwb-fc-km">{{ formatMetersToKm(act.distance_meters) }}</text>
                <text class="cwb-fc-unit">km</text>
              </view>
            </view>

            <view class="cwb-fc-metrics">
              <text class="cwb-fcm-pill">⏱ 配速 {{ act.avg_pace_str || '—' }}</text>
              <text class="cwb-fcm-pill">❤️ 心率 {{ act.average_heartrate || '—' }}bpm</text>
              <text class="cwb-fcm-pill">⚡ 负荷 {{ act.trimp || 50 }}</text>
              <text v-if="Number(act.elevation_gain_meters || act.total_elevation_gain || 0) > 0" class="cwb-fcm-pill">
                ⛰ 爬升 +{{ Math.round(Number(act.elevation_gain_meters || act.total_elevation_gain || 0)) }}m
              </text>
            </view>

            <view v-if="formatAiJournal(act.ai_journal)" class="cwb-fc-canova">
              <text class="cwb-fcc-label">🧬 生理复盘：</text>
              <text class="cwb-fcc-text">{{ formatAiJournal(act.ai_journal) }}</text>
            </view>

            <!-- Existing Comments -->
            <view v-if="act.comments && act.comments.length > 0" class="cwb-fc-comments">
              <view v-for="cmt in act.comments" :key="cmt.id" class="cwb-fcc-item">
                <text class="cwb-fcc-author">{{ cmt.author_name }}：</text>
                <text class="cwb-fcc-content">{{ cmt.content }}</text>
              </view>
            </view>

            <!-- Quick Coach Critique Presets -->
            <view class="cwb-preset-row">
              <text
                v-for="(pTxt, pIdx) in coachQuickComments"
                :key="pIdx"
                class="cwb-preset-chip"
                @click="applyQuickCoachComment(act.id, pTxt)"
              >
                {{ pTxt.label }}
              </text>
            </view>

            <!-- Coach Comment Input & Like -->
            <view class="cwb-comment-bar">
              <view
                class="cwb-like-btn"
                :class="{ liked: act.has_liked }"
                @click="handleToggleFeedLike(act)"
              >
                ❤️ {{ act.likes_count || 0 }}
              </view>
              <input
                class="cwb-comment-input"
                type="text"
                :adjust-position="false"
                v-model="feedCommentInputs[act.id]"
                placeholder="输入教练专业点评或鼓励..."
              />
              <button
                class="cwb-send-btn"
                :disabled="!feedCommentInputs[act.id] || submittingFeedComment[act.id]"
                @click="handlePostCoachComment(act)"
              >
                点评
              </button>
            </view>
          </view>
        </view>
      </view>

      <!-- ==================== MODULE 3: 跑团合练、约跑与拉练活动管理 ==================== -->
      <view v-else-if="coachBenchTab === 'events'" class="cwb-module-box">
        <view class="cwb-sec-header">
          <view>
            <text class="cwb-sec-title">🏃 合练与约跑</text>
          </view>
        </view>

        <view class="cph-actions-row" style="margin-bottom: 20rpx;">
          <button class="cph-batch-btn broadcast" @click="showBroadcastModal = true">
            📢 全员派课
          </button>
          <button class="cph-batch-btn pipeline" @click="showNewEventForm = !showNewEventForm">
            {{ showNewEventForm ? '▲ 收起表单' : '+ 发起约跑' }}
          </button>
        </view>

        <!-- Inline Create Group Run / Challenge Form -->
        <view v-if="showNewEventForm" class="pm-roll-panel" style="margin-bottom: 24rpx;">
          <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12rpx;">
            <text class="pm-roll-title" style="margin-bottom: 0;">🏃 发起约跑</text>
            <text
              style="font-size: 22rpx; font-weight: 700; color: #059669; background: rgba(16, 185, 129, 0.12); border: 1rpx solid rgba(16, 185, 129, 0.35); padding: 6rpx 16rpx; border-radius: 999rpx;"
              @click="handleSaveCurrentAsEventTemplate"
            >
              💾 存为本团模版
            </text>
          </view>

          <!-- 📑 约跑活动模版库（一键套用） -->
          <view style="margin-bottom: 16rpx; padding: 14rpx 16rpx; border-radius: 14rpx; background: rgba(16, 185, 129, 0.06); border: 1rpx solid rgba(16, 185, 129, 0.22);">
            <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10rpx;">
              <text style="font-size: 22rpx; font-weight: 700; color: #065f46;">📑 活动模版</text>
              <text v-if="selectedEvtTplId" style="font-size: 20rpx; color: #059669;">已套用 ✓</text>
            </view>
            <view style="display: flex; flex-wrap: wrap; gap: 10rpx;">
              <view
                v-for="tpl in allGroupRunTemplates"
                :key="tpl.id"
                style="display: inline-flex; align-items: center; gap: 6rpx; padding: 8rpx 16rpx; border-radius: 999rpx; font-size: 22rpx; font-weight: 600;"
                :style="selectedEvtTplId === tpl.id
                  ? 'background: #10b981; color: #ffffff; border: 1rpx solid #059669;'
                  : (tpl.is_custom ? 'background: rgba(245, 158, 11, 0.14); color: #b45309; border: 1rpx solid rgba(245, 158, 11, 0.4);' : 'background: #ffffff; color: #1e293b; border: 1rpx solid #cbd5e1;')"
                @click="applyGroupRunTemplate(tpl)"
              >
                <text>{{ tpl.is_custom ? '⭐ ' + tpl.name : tpl.name }}</text>
                <text
                  v-if="tpl.is_custom"
                  style="margin-left: 4rpx; font-size: 22rpx; opacity: 0.8; padding: 0 4rpx;"
                  @click.stop="handleDeleteCustomEventTemplate(tpl)"
                >
                  ×
                </text>
              </view>
            </view>
          </view>

          <view class="pm-editor-col">
            <text class="pm-ed-label">活动/合练标题</text>
            <input class="pm-ed-input" v-model="newEvtTitle" placeholder="例如：周日世纪公园 22km 分组 LSD 合练" />
          </view>

          <view class="pm-editor-row" style="margin-top: 10rpx;">
            <view class="pm-editor-col flex-1">
              <text class="pm-ed-label">目标里程 (km)</text>
              <input class="pm-ed-input" type="digit" v-model="newEvtTargetKm" placeholder="22" />
            </view>
            <view class="pm-editor-col flex-1">
              <text class="pm-ed-label">集合日期</text>
              <picker mode="date" :value="newEvtMeetDate" @change="(e: any) => newEvtMeetDate = e.detail.value">
                <view class="pm-ed-input" style="display: flex; align-items: center; justify-content: space-between;">
                  <text>{{ newEvtMeetDate || '选择日期' }}</text>
                  <text style="font-size: 20rpx; opacity: 0.6;">▼</text>
                </view>
              </picker>
            </view>
            <view class="pm-editor-col flex-1">
              <text class="pm-ed-label">集合时间</text>
              <picker mode="time" :value="newEvtMeetTime" @change="(e: any) => newEvtMeetTime = e.detail.value">
                <view class="pm-ed-input" style="display: flex; align-items: center; justify-content: space-between;">
                  <text>{{ newEvtMeetTime || '06:30' }}</text>
                  <text style="font-size: 20rpx; opacity: 0.6;">▼</text>
                </view>
              </picker>
            </view>
          </view>

          <!-- 📍 集合地点与地图标注 -->
          <view class="pm-editor-col" style="margin-top: 12rpx;">
            <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6rpx;">
              <text class="pm-ed-label" style="margin-bottom: 0;">集合地点</text>
              <text
                style="font-size: 22rpx; font-weight: 700; color: #2563eb; background: rgba(37, 99, 235, 0.12); border: 1rpx solid rgba(37, 99, 235, 0.35); padding: 6rpx 16rpx; border-radius: 999rpx;"
                @click="handleChooseNewEvtLocation"
              >
                📍 地图选点
              </text>
            </view>
            <input
              class="pm-ed-input"
              v-model="newEvtLocation"
              confirm-type="search"
              placeholder="输入地点（如：闵行文化公园）"
              @blur="onNewEvtLocationBlur"
              @confirm="onNewEvtLocationBlur"
            />

            <input
              class="pm-ed-input"
              style="margin-top: 10rpx;"
              v-model="newEvtLocationDetail"
              placeholder="详细地址或路线说明（如：7号门存包热身，顺时针外圈）"
            />

            <!-- 🗺️ 实时地图标注预览卡片（支持直接点击微调大头针或弹出选点地图） -->
            <view
              v-if="newEvtLatitude && newEvtLongitude"
              style="margin-top: 12rpx; border-radius: 14rpx; overflow: hidden; border: 1rpx solid rgba(37, 99, 235, 0.3); background: #f8fafc;"
            >
              <view style="display: flex; align-items: center; justify-content: space-between; padding: 10rpx 14rpx; background: rgba(37, 99, 235, 0.08);">
                <text style="font-size: 21rpx; font-weight: 700; color: #1e40af; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  📌 已标注：{{ newEvtLocation || '集合点' }} ({{ Number(newEvtLatitude).toFixed(4) }}, {{ Number(newEvtLongitude).toFixed(4) }})
                </text>
                <text
                  style="font-size: 21rpx; font-weight: 700; color: #2563eb; margin-left: 12rpx;"
                  @click="handleChooseNewEvtLocation"
                >
                  🎯 调整大头针 ›
                </text>
              </view>
              <map
                style="width: 100%; height: 240rpx;"
                :latitude="Number(newEvtLatitude)"
                :longitude="Number(newEvtLongitude)"
                :scale="16"
                :markers="newEvtMapMarkers"
                @tap="onInlineNewEvtMapTap"
              />
              <view style="display: flex; align-items: center; justify-content: flex-end; padding: 8rpx 14rpx; background: #eff6ff;">
                <text
                  style="font-size: 20rpx; font-weight: 700; color: #2563eb;"
                  @click="previewNewEvtLocationOnMap"
                >
                  🧭 导航预览 ›
                </text>
              </view>
            </view>
          </view>

          <view class="pm-editor-col" style="margin-top: 10rpx;">
            <text class="pm-ed-label">配速分组与训练要求</text>
            <textarea
              class="pm-overview-textarea"
              v-model="newEvtRules"
              placeholder="例如：240/A组配速415，B组配速450，C组配速530，每5km集体补水..."
            />
          </view>
          <button
            class="pm-publish-main-btn"
            style="margin-top: 12rpx;"
            :loading="creatingEvent"
            :disabled="creatingEvent"
            @click="handleCreateClubEventFromCoach"
          >
            🚀 发布活动
          </button>
        </view>

        <view v-if="clubEvents.length === 0" class="empty-box">
          <text class="empty-text">暂无约跑活动</text>
        </view>
        <view v-else class="cwb-feed-list">
          <view v-for="ev in clubEvents" :key="ev.id" class="cwb-feed-card" @click="goToEventDetail(ev)">
            <view class="cwb-fc-top">
              <view style="flex: 1;">
                <text class="cwb-fc-name">{{ ev.title }}</text>
                <text class="cwb-fc-actname" style="margin-top: 6rpx; display: block;">
                  🎯 目标里程：{{ ev.target_km || 10 }} km · 参与人数：{{ ev.participants_count || ev.participant_count || 1 }} 人
                </text>
                <view v-if="ev.meet_time || ev.location" style="display: flex; flex-wrap: wrap; align-items: center; gap: 12rpx; margin-top: 8rpx;">
                  <text v-if="ev.meet_time" style="font-size: 21rpx; color: #475569;">
                    ⏰ {{ formatMeetTime(ev.meet_time) }}
                  </text>
                  <text
                    v-if="ev.location"
                    style="font-size: 21rpx; font-weight: 700; color: #2563eb; background: rgba(37, 99, 235, 0.1); padding: 4rpx 12rpx; border-radius: 999rpx;"
                    @click.stop="openRunLocation(ev)"
                  >
                    📍 {{ ev.location }}{{ ev.latitude ? ' · 地图导航 ›' : '' }}
                  </text>
                </view>
              </view>
              <text class="crb-btn">查看详情 ›</text>
            </view>
            <text v-if="ev.rules" class="cwb-fcc-text" style="margin-top: 10rpx; display: block;">
              📋 {{ ev.rules }}
            </text>
          </view>
        </view>
      </view>

      <!-- ==================== MODULE 4: 跑团周报/月报战报与成员/邀请码管理 ==================== -->
      <view v-else-if="coachBenchTab === 'report_manage'" class="cwb-module-box">
        <!-- Section A: Club Weekly & Monthly Report -->
        <view class="cwb-feed-card" style="margin-bottom: 24rpx;">
          <view class="cwb-sec-header" style="margin-bottom: 16rpx;">
            <view>
              <text class="cwb-sec-title">📊 跑团周报与月报</text>
            </view>
          </view>

          <view class="pm-pill-selector" style="margin-bottom: 12rpx;">
            <view
              class="pm-mini-pill"
              :class="{ active: coachRepPeriod === 'week' && coachRepOffset === 0 }"
              @click="loadCoachClubReport('week', 0, coachRepTrailMode)"
            >本周周报</view>
            <view
              class="pm-mini-pill"
              :class="{ active: coachRepPeriod === 'week' && coachRepOffset === -1 }"
              @click="loadCoachClubReport('week', -1, coachRepTrailMode)"
            >上周周报</view>
            <view
              class="pm-mini-pill"
              :class="{ active: coachRepPeriod === 'month' && coachRepOffset === 0 }"
              @click="loadCoachClubReport('month', 0, coachRepTrailMode)"
            >本月月报</view>
            <view
              class="pm-mini-pill"
              :class="{ active: coachRepPeriod === 'month' && coachRepOffset === -1 }"
              @click="loadCoachClubReport('month', -1, coachRepTrailMode)"
            >上月月报</view>
          </view>

          <view class="pm-pill-selector" style="margin-bottom: 16rpx;">
            <view
              class="pm-mini-pill"
              :class="{ active: coachRepTrailMode === 'include' }"
              @click="loadCoachClubReport(coachRepPeriod, coachRepOffset, 'include')"
            >🏔️ 含越野</view>
            <view
              class="pm-mini-pill"
              :class="{ active: coachRepTrailMode === 'exclude_pace' }"
              @click="loadCoachClubReport(coachRepPeriod, coachRepOffset, 'exclude_pace')"
            >⏱️ 仅去越野配速</view>
            <view
              class="pm-mini-pill"
              :class="{ active: coachRepTrailMode === 'exclude_all' }"
              @click="loadCoachClubReport(coachRepPeriod, coachRepOffset, 'exclude_all')"
            >🛣️ 去越野跑量/配速</view>
          </view>

          <view v-if="loadingCoachReport" class="pm-loading-box">
            <text class="pm-loading-text">加载中...</text>
          </view>
          <view v-else-if="coachReportData" class="cwb-report-box">
            <view class="cwb-rep-hero">
              <view>
                <text class="cwb-rep-period">{{ coachReportData.period_label }} · {{ coachReportData.date_range_str }}</text>
                <text class="cwb-rep-km">{{ coachReportData.total_distance_km }} <text style="font-size: 24rpx;">KM</text></text>
              </view>
              <view class="cwb-rep-stats">
                <text class="cwb-rep-stat">出勤率: {{ coachReportData.attendance_rate_pct }}% ({{ coachReportData.active_members_count }}/{{ coachReportData.total_members_count }}人)</text>
                <text class="cwb-rep-stat">全团均速: {{ coachReportData.avg_pace_str }} · 打卡 {{ coachReportData.total_activities_count }} 次</text>
              </view>
            </view>

            <view v-if="coachReportData.canova_critique" class="cwb-fc-canova" style="margin-top: 14rpx;">
              <text class="cwb-fcc-label">💡 团队复盘：</text>
              <text class="cwb-fcc-text">{{ coachReportData.canova_critique }}</text>
            </view>

            <view class="cph-actions-row" style="margin-top: 16rpx;">
              <button class="cph-batch-btn pipeline" @click="copyCoachReportText">
                📋 复制战报文本
              </button>
              <button class="cph-batch-btn template-btn" @click="goToTeamReport">
                🖼️ 生成海报
              </button>
            </view>
          </view>
        </view>

        <!-- Section B: Quick Invite Code Share & Web Admin Offload -->
        <view class="cwb-feed-card" style="margin-bottom: 24rpx;">
          <view class="cwb-fc-top">
            <view>
              <text class="cwb-sec-title">🔑 邀请码</text>
              <text class="cwb-sec-sub">{{ currentClub?.join_mode === 'invite' ? '🔒 凭邀请码入团' : '🟢 自由入团' }}</text>
            </view>
            <view v-if="currentClub?.invite_code" class="cwb-invite-pill" @click="copyClubInviteCode">
              {{ currentClub.invite_code }} 📋
            </view>
          </view>
        </view>

        <!-- Section C: Low-Frequency Admin Tasks Offloaded to Web -->
        <view class="cwb-feed-card">
          <view style="display: flex; align-items: center; justify-content: space-between; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.28); border-radius: 14rpx; padding: 16rpx 20rpx;">
            <view style="display: flex; align-items: center; gap: 8rpx;" @click="explainTerm('web_admin')">
              <text style="font-size: 24rpx; font-weight: 700; color: #38bdf8;">💻 网页端后台 (rgm.vanpower.net)</text>
              <text class="term-info">ⓘ</text>
            </view>
            <button
              class="cwb-mini-btn"
              style="margin: 0; background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4);"
              @click="copyWebAdminUrl"
            >
              📋 复制网址
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── NEW: Coach Plan Review, Edit, Publish & Execution Modal (手机端教练排课审核工作台) ── -->
    <view v-if="showPlanModal && activeStudent" class="modal-mask plan-modal-mask" @click="closePlanModal" @touchmove.stop.prevent>
      <view class="modal-content plan-modal-content" @click.stop>
        <!-- 20-Athlete Continuous Pipeline Navigation Bar -->
        <view v-if="filteredStudents.length > 1" class="pm-pipeline-bar">
          <view
            class="pm-pipe-btn"
            :class="{ disabled: activeQueueIndex <= 0 }"
            @click="goPrevStudentInQueue"
          >
            ⬅ 上一位
          </view>
          <view class="pm-pipe-center">
            <text class="pm-pipe-title">📋 流水线 ({{ activeQueueIndex + 1 }}/{{ filteredStudents.length }})</text>
          </view>
          <view
            class="pm-pipe-btn"
            :class="{ disabled: activeQueueIndex >= filteredStudents.length - 1 }"
            @click="goNextStudentInQueue"
          >
            下一位 ➡
          </view>
        </view>

        <!-- Modal Header -->
        <view class="pm-header">
          <view class="pm-student-row">
            <image
              class="pm-avatar"
              :src="activeStudent.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
              mode="aspectFill"
            />
            <view class="pm-student-info">
              <view class="pm-name-line">
                <text class="pm-name">{{ activeStudent.display_name }}</text>
                <text class="pm-tsb-badge" :class="'badge-' + activeStudent.status_level">
                  TSB {{ activeStudent.tsb > 0 ? '+' + activeStudent.tsb : activeStudent.tsb }} · CTL {{ activeStudent.ctl }}
                </text>
              </view>
              <text class="pm-sub-meta">
                周目标 {{ studentGoal?.weekly_target || activeStudent.weekly_target || 50 }}km
                <text v-if="activeStudent.goal_race"> · 🏁 {{ activeStudent.goal_race.name }}{{ (activeStudent.goal_race.days_until ?? activeStudent.goal_race.days_left) != null ? ` (${activeStudent.goal_race.days_until ?? activeStudent.goal_race.days_left}天)` : '' }}</text>
              </text>
            </view>
          </view>
          <text class="close-btn" @click="closePlanModal">✕</text>
        </view>

        <!-- 3-Mode Tab Bar -->
        <view class="pm-tabs">
          <view
            class="pm-tab"
            :class="{ active: planModalTab === 'review' }"
            @click="planModalTab = 'review'"
          >
            📋 审核与调课
          </view>
          <view
            class="pm-tab"
            :class="{ active: planModalTab === 'execution' }"
            @click="planModalTab = 'execution'"
          >
            📊 执行打卡
          </view>
          <view
            class="pm-tab"
            :class="{ active: planModalTab === 'generate' }"
            @click="planModalTab = 'generate'"
          >
            ✨ 定制新草案
          </view>
        </view>

        <!-- Scrollable Body -->
        <scroll-view scroll-y class="pm-scroll-body">
          <!-- 教练排课弹窗内：队员夜间未佩戴手表预警 -->
          <view
            v-if="activeStudent?.night_wear_missing"
            style="margin: 12rpx 0 16rpx 0; padding: 14rpx 18rpx; border-radius: 14rpx; background: rgba(245, 158, 11, 0.15); border: 1rpx solid rgba(245, 158, 11, 0.48);"
          >
            <text style="display: block; font-size: 23rpx; font-weight: 700; color: #b45309; margin-bottom: 4rpx;">
              ⚠️ 夜间未佩戴手表 · 恢复数据缺失
            </text>
            <text style="display: block; font-size: 21rpx; line-height: 1.5; color: #92400e;">
              {{ activeStudent?.recovery_data_warning || '暂无法给出强度建议，请提醒队员佩戴手表' }}
            </text>
          </view>
          <view v-if="planLoading" class="pm-loading-box">
            <text class="pm-loading-text">加载中...</text>
          </view>

          <!-- TAB 1: REVIEW & EDIT & PUBLISH -->
          <view v-else-if="planModalTab === 'review'" class="pm-tab-body">
            <view v-if="!currentReviewPlan" class="pm-empty-box">
              <text class="pm-empty-icon">📋</text>
              <text class="pm-empty-title">暂无训练计划</text>
              <view class="pm-quick-tpl-row" style="margin: 16rpx 0; justify-content: center;">
                <view
                  v-for="qt in quickTemplateBarOptions"
                  :key="qt.id"
                  class="pm-qt-chip"
                  :class="{ rec: activeStudent?.recommended_group?.template_id === qt.id }"
                  @click="handleSingleQuickApplyTemplate(qt.id, 'full_plan')"
                >
                  {{ qt.label }}{{ activeStudent?.recommended_group?.template_id === qt.id ? ' ★荐' : '' }}
                </view>
              </view>
              <button class="pm-primary-btn" @click="planModalTab = 'generate'">
                ✨ 定制草案
              </button>
            </view>

            <view v-else class="pm-review-workspace">
              <!-- Unconfirmed Preview Banner -->
              <view
                v-if="hasUnconfirmedPlanChanges"
                style="margin-bottom: 18rpx; padding: 18rpx 22rpx; border-radius: 18rpx; background: linear-gradient(135deg, rgba(245, 158, 11, 0.22), rgba(234, 88, 12, 0.15)); border: 2rpx solid rgba(245, 158, 11, 0.65); display: flex; align-items: center; justify-content: space-between; gap: 16rpx;"
              >
                <view style="flex: 1;">
                  <text style="font-size: 24rpx; font-weight: 800; color: #fbbf24; display: block;">🛡️ 预览待确认（未写入）</text>
                </view>
                <button
                  style="margin: 0; padding: 0 20rpx; height: 56rpx; line-height: 56rpx; font-size: 22rpx; font-weight: 700; border-radius: 12rpx; background: rgba(255,255,255,0.14); color: #ffffff; border: 1rpx solid rgba(255,255,255,0.25); flex-shrink: 0;"
                  @click="discardUnconfirmedPlanChanges"
                >
                  ↩ 放弃更改
                </button>
              </view>

              <!-- Switcher if both draft & active exist -->
              <view v-if="studentDraftPlan && studentActivePlan" class="pm-plan-switcher">
                <view
                  class="pm-switch-pill"
                  :class="{ active: viewingDraft }"
                  @click="switchViewingPlan(true)"
                >
                  🟠 待审核草案
                </view>
                <view
                  class="pm-switch-pill"
                  :class="{ active: !viewingDraft }"
                  @click="switchViewingPlan(false)"
                >
                  🟢 执行中计划
                </view>
              </view>

              <!-- Plan Title & Status Banner -->
              <view class="pm-plan-banner" :class="currentReviewPlan.status === 'draft' ? 'is-draft' : 'is-active'">
                <view class="pm-banner-top">
                  <text class="pm-status-tag" :class="currentReviewPlan.status === 'draft' ? 'draft' : 'active'">
                    {{ currentReviewPlan.status === 'draft' ? '🟠 待审核草案' : '🟢 执行中' }}
                  </text>
                  <text class="pm-weeks-count">{{ currentReviewPlan.weeks_count || 4 }}周周期</text>
                </view>
                <input
                  class="pm-title-input"
                  v-model="editPlanTitle"
                  placeholder="输入训练计划标题..."
                />
                <textarea
                  class="pm-overview-textarea"
                  v-model="editPlanOverview"
                  :maxlength="400"
                  placeholder="周期宏观指导摘要..."
                />

                <!-- Quick Apply Group Template Bar inside Review Workspace -->
                <view class="pm-quick-tpl-box">
                  <view class="pm-qt-header">
                    <text class="pm-qt-title">📚 套用模版:</text>
                    <view class="pm-qt-scope-pills">
                      <text
                        class="pm-qt-scope"
                        :class="{ active: singleQuickScope === 'current_week' }"
                        @click="singleQuickScope = 'current_week'"
                      >仅第{{ selectedWeekIdx }}周</text>
                      <text
                        class="pm-qt-scope"
                        :class="{ active: singleQuickScope === 'full_plan' }"
                        @click="singleQuickScope = 'full_plan'"
                      >4周周期</text>
                    </view>
                  </view>
                  <view class="pm-quick-tpl-row">
                    <view
                      v-for="qt in quickTemplateBarOptions"
                      :key="qt.id"
                      class="pm-qt-chip"
                      :class="{
                        cur: currentReviewPlan.schedule_data?.template_id === qt.id,
                        rec: activeStudent?.recommended_group?.template_id === qt.id
                      }"
                      @click="handleSingleQuickApplyTemplate(qt.id)"
                    >
                      {{ qt.label }}{{ currentReviewPlan.schedule_data?.template_id === qt.id ? ' ✓' : (activeStudent?.recommended_group?.template_id === qt.id ? ' ★荐' : '') }}
                    </view>
                  </view>
                </view>
              </view>

              <!-- Week Selector Pills + Roll Next Week Trigger -->
              <view class="pm-week-header-row">
                <scroll-view scroll-x class="pm-week-scroll" show-scrollbar="false">
                  <view class="pm-week-row">
                    <view
                      v-for="w in (currentReviewPlan.schedule_data?.weeks || [])"
                      :key="w.week_index"
                      class="pm-week-pill"
                      :class="{ active: selectedWeekIdx === w.week_index }"
                      @click="onSelectWeekTab(w.week_index)"
                    >
                      <text class="pm-wp-num">W{{ w.week_index }}</text>
                      <text class="pm-wp-km">{{ w.planned_Actual_km || w.total_distance_km || 0 }}km · {{ w.theme }}</text>
                    </view>
                  </view>
                </scroll-view>
                <view
                  class="pm-roll-trigger-btn"
                  @click="showRollNextWeekPanel = !showRollNextWeekPanel"
                >
                  ⚡ 滚动生成 W{{ Number(selectedWeekIdx) + 1 }}
                </view>
              </view>

              <!-- 1-Click Rolling Next Week Generator Panel -->
              <view v-if="showRollNextWeekPanel" class="pm-roll-panel">
                <view class="pm-roll-top">
                  <text class="pm-roll-title">⚡ 滚动生成 W{{ Number(selectedWeekIdx) + 1 }}</text>
                </view>
                <view class="pm-pill-selector">
                  <view
                    v-for="sc in rollScaleOptions"
                    :key="sc.label"
                    class="pm-mini-pill"
                    :class="{ active: rollVolumeScale === sc.value }"
                    @click="rollVolumeScale = sc.value"
                  >
                    {{ sc.label }}
                  </view>
                </view>
                <view class="pm-editor-row">
                  <view class="pm-editor-col flex-1">
                    <text class="pm-ed-label">下周训练主题 (选填)</text>
                    <input class="pm-ed-input" v-model="rollWeekTheme" placeholder="如：混氧节奏强化 / 减量恢复周" />
                  </view>
                </view>
                <view class="pm-editor-col">
                  <text class="pm-ed-label">下周教练重点要求 / 合练安排</text>
                  <input class="pm-ed-input" v-model="rollCoachNote" placeholder="如：周二交大间歇课，周末LSD控制在20km..." />
                </view>
                <button
                  class="pm-roll-submit-btn"
                  :loading="rollingNextWeek"
                  :disabled="rollingNextWeek"
                  @click="handleRollNextWeek"
                >
                  {{ rollingNextWeek ? '生成中...' : '🚀 生成 W' + (Number(selectedWeekIdx) + 1) }}
                </button>
              </view>

              <!-- W19 Weekly Summary Banner -->
              <view v-if="currentSelectedWeek" class="pm-w19-summary-strip">
                <text class="pm-w19-summary-txt">
                  📊 {{ currentSelectedWeek.week_summary_text || ('周跑量：' + (currentSelectedWeek.planned_Actual_km || 0) + '公里。执行：' + (currentSelectedWeek.actual_run_km || 0) + '公里，完成度' + (currentSelectedWeek.compliance_rate || 0) + '%；力量：' + (currentSelectedWeek.strength_count || 0) + '次。') }}
                </text>
              </view>

              <!-- 1-Click Weekly Batch Adjustment Bar -->
              <view v-if="currentSelectedWeek" class="pm-batch-bar">
                <view class="pm-batch-header">
                  <text class="pm-batch-title">⚡ W{{ currentSelectedWeek.week_index }} 整周调课 ({{ currentSelectedWeek.planned_Actual_km || currentSelectedWeek.total_distance_km || 0 }} km)</text>
                </view>
                <view class="pm-batch-btns">
                  <button class="pm-adj-btn down" :disabled="savingPlan" @click="handleWeekBatchAdjust('scale_volume', 0.85)">
                    📉 跑量-15%
                  </button>
                  <button class="pm-adj-btn down" :disabled="savingPlan" @click="handleWeekBatchAdjust('scale_volume', 0.9)">
                    📉 跑量-10%
                  </button>
                  <button class="pm-adj-btn up" :disabled="savingPlan" @click="handleWeekBatchAdjust('scale_volume', 1.1)">
                    📈 跑量+10%
                  </button>
                  <button class="pm-adj-btn protect" :disabled="savingPlan" @click="handleWeekBatchAdjust('downgrade_intensity', 1.0)">
                    🛡️ 降强度
                  </button>
                </view>
              </view>

              <!-- 7-Day Workout Cards (W19 Full Columns) -->
              <view v-if="currentSelectedWeek" class="pm-days-list">
                <view
                  v-for="(day, dIdx) in (currentSelectedWeek.days || [])"
                  :key="day.day_index || dIdx"
                  class="pm-day-card"
                  :class="['type-' + (day.workout_type || 'easy_run'), day.completed ? 'is-done' : '', day.hrv_warning ? 'hrv-warn-card' : '']"
                >
                  <view class="pm-day-top">
                    <view class="pm-day-left">
                      <text class="pm-day-dow">{{ day.day_of_week }}</text>
                      <text v-if="day.date" class="pm-day-date">{{ day.date.slice(5) }}</text>
                      <text v-if="day.swapped_from" class="pm-swap-tag">⇄ 与{{ day.swapped_from }}对换</text>
                      <text class="pm-day-type-tag" :class="'tag-' + (day.workout_type || 'easy_run')">
                        {{ getWorkoutLabel(day.workout_type) }}
                      </text>
                      <text class="pm-day-title">{{ day.title }}</text>
                    </view>
                    <view class="pm-day-right">
                      <text v-if="day.workout_type !== 'rest'" class="pm-day-km-badge">{{ day.distance_km }} km</text>
                      <text v-if="day.completed" class="pm-day-done-badge">✅ 实跑 {{ day.actual_distance_km || day.distance_km }}km</text>
                    </view>
                  </view>

                  <view v-if="day.workout_type !== 'rest'" class="pm-day-meta">
                    <text v-if="day.target_pace">🎯 配速: {{ day.target_pace }}</text>
                    <text v-if="day.target_hr_zone">❤️ 心率: {{ day.target_hr_zone }}</text>
                  </view>
                  <text class="pm-day-desc">{{ day.description }}</text>

                  <!-- W19 Biometrics, Recovery%, RPE, Execution & Self-Feel Strip -->
                  <view
                    v-if="day.biometrics_text || day.recovery_pct || day.rpe || day.actual_execution_text || day.athlete_notes || day.strength_completed"
                    class="pm-w19-day-feedback"
                  >
                    <view class="pm-w19-badges-row">
                      <text
                        v-if="day.recovery_pct"
                        class="pm-rec-badge"
                        :class="'rec-' + (day.recovery_color || (day.recovery_pct >= 67 ? 'green' : day.recovery_pct >= 34 ? 'yellow' : 'red'))"
                      >
                        恢复 {{ day.recovery_pct }}%
                      </text>
                      <text v-if="day.biometrics_text" class="pm-bio-badge" :class="{ warn: day.hrv_warning }">
                        ❤️ {{ day.biometrics_text }}
                      </text>
                      <text v-if="day.rpe" class="pm-rpe-badge" :class="day.rpe >= 8 ? 'high' : day.rpe >= 6 ? 'mid' : 'low'">
                        RPE {{ day.rpe }}/10
                      </text>
                      <text v-if="day.strength_completed" class="pm-str-badge">💪 力量已练</text>
                    </view>
                    <text v-if="day.actual_execution_text" class="pm-exec-line">
                      🏃 执行情况: {{ day.actual_execution_text }}
                    </text>
                    <text v-if="day.athlete_notes" class="pm-feel-line">
                      💬 队员自我感受: {{ day.athlete_notes }}
                    </text>
                  </view>

                  <!-- Quick 1-Thumb Stepper & Edit Trigger -->
                  <view class="pm-day-actions">
                    <view v-if="day.workout_type !== 'rest'" class="pm-quick-steppers">
                      <view class="pm-step-btn" @click="handleQuickStepDay(day, -2)">-2k</view>
                      <view class="pm-step-btn" @click="handleQuickStepDay(day, -1)">-1k</view>
                      <view class="pm-step-btn plus" @click="handleQuickStepDay(day, 1)">+1k</view>
                      <view class="pm-step-btn plus" @click="handleQuickStepDay(day, 2)">+2k</view>
                      <view class="pm-step-btn rest" @click="handleQuickConvertRest(day)">转休息</view>
                    </view>
                    <view
                      class="pm-edit-toggle-btn"
                      @click="toggleEditDay(day)"
                    >
                      {{ editingDayIdx === day.day_index ? '收起编辑' : '✎ 调课/录入反馈' }}
                    </view>
                  </view>

                  <!-- Inline Day Editor (Prescription + W19 Biometrics / RPE / Day Swap) -->
                  <view v-if="editingDayIdx === day.day_index" class="pm-day-editor">
                    <view class="pm-type-selector">
                      <view
                        v-for="wt in workoutTypeList"
                        :key="wt.value"
                        class="pm-type-chip"
                        :class="{ active: editDayForm.workout_type === wt.value }"
                        @click="editDayForm.workout_type = wt.value"
                      >
                        {{ wt.label }}
                      </view>
                    </view>
                    <view class="pm-editor-row">
                      <view class="pm-editor-col flex-2">
                        <text class="pm-ed-label">课表名称</text>
                        <input class="pm-ed-input" v-model="editDayForm.title" />
                      </view>
                      <view v-if="editDayForm.workout_type !== 'rest'" class="pm-editor-col flex-1">
                        <text class="pm-ed-label">距离 (km)</text>
                        <input class="pm-ed-input" type="digit" v-model="editDayForm.distance_km" />
                      </view>
                    </view>
                    <view v-if="editDayForm.workout_type !== 'rest'" class="pm-editor-row">
                      <view class="pm-editor-col">
                        <text class="pm-ed-label">目标配速</text>
                        <input class="pm-ed-input" v-model="editDayForm.target_pace" placeholder="如 5:10-5:25/km" />
                      </view>
                      <view class="pm-editor-col">
                        <text class="pm-ed-label">心率区间</text>
                        <input class="pm-ed-input" v-model="editDayForm.target_hr_zone" placeholder="如 Zone 2" />
                      </view>
                    </view>
                    <view class="pm-editor-col">
                      <text class="pm-ed-label">训练处方</text>
                      <textarea class="pm-ed-textarea" v-model="editDayForm.description" :maxlength="300" />
                    </view>
                    <view class="pm-editor-col">
                      <text class="pm-ed-label">单日教练批注 (选填)</text>
                      <input class="pm-ed-input" v-model="editDayForm.athlete_notes" placeholder="如：前半程压心率，跑后注意拉伸..." />
                    </view>

                    <button class="pm-save-day-btn" :disabled="savingPlan" @click="handleSaveDayEdit(day.day_index)">
                      💾 保存本课微调
                    </button>
                  </view>
                </view>
              </view>

              <!-- Weekly Summary & Injury Review Card -->
              <view v-if="currentSelectedWeek" class="pm-week-summary-card">
                <text class="pm-pub-title">📝 第 {{ currentSelectedWeek.week_index }} 周小结</text>
                <view class="pm-runner-report-box">
                  <text class="pm-rr-item">
                    🩹 伤痛：<text class="pm-rr-val" :class="{ warn: currentSelectedWeek.injury_note && currentSelectedWeek.injury_note !== '无' }">{{ currentSelectedWeek.injury_note || '无' }}</text>
                  </text>
                  <text class="pm-rr-item">
                    💬 小结：<text class="pm-rr-val">{{ currentSelectedWeek.athlete_weekly_summary || '暂未填写' }}</text>
                  </text>
                  <text v-if="currentSelectedWeek.travel_or_leave_note" class="pm-rr-item">
                    ✈️ 请假：<text class="pm-rr-val">{{ currentSelectedWeek.travel_or_leave_note }}</text>
                  </text>
                </view>
                <view class="pm-editor-col">
                  <text class="pm-ed-label">周跑量备注 (选填)</text>
                  <input
                    class="pm-ed-input"
                    v-model="weekSummaryOverride"
                    placeholder="如：周跑量：56公里。执行：59公里，完成度105%；力量：1次。"
                  />
                </view>
                <view class="pm-editor-col">
                  <text class="pm-ed-label">👨‍🏫 教练周复盘</text>
                  <textarea
                    class="pm-note-textarea"
                    v-model="coachWeeklyDiagnosis"
                    :maxlength="300"
                    placeholder="如：本周59km超额完成但周四HRV偏低(32)，下周W20建议跑量维持56km，周二间歇控在410配速..."
                  />
                </view>
                <button
                  class="pm-save-summary-btn"
                  :disabled="savingWeekSummary"
                  @click="handleSaveCoachWeekSummary"
                >
                  {{ savingWeekSummary ? '保存中...' : '💾 保存周复盘' }}
                </button>
              </view>

              <!-- Coach Review Note & Publish Box -->
              <view class="pm-publish-card">
                <text class="pm-pub-title">👨‍🏫 教练叮嘱</text>
                <view class="pm-note-presets">
                  <view
                    v-for="(tpl, tIdx) in coachNoteTemplates"
                    :key="tIdx"
                    class="pm-note-chip"
                    @click="coachReviewNote = tpl"
                  >
                    + {{ tpl.slice(0, 14) }}...
                  </view>
                </view>
                <textarea
                  class="pm-note-textarea"
                  v-model="coachReviewNote"
                  :maxlength="300"
                  placeholder="输入对队员本周训练的重点叮嘱、配速控制要求或防伤病提醒..."
                />
                <view class="pm-publish-btn-group">
                  <button
                    class="pm-publish-main-btn"
                    :loading="publishingPlan"
                    :disabled="publishingPlan"
                    @click="handlePublishPlan(false)"
                  >
                    {{ currentReviewPlan.status === 'draft' ? '🚀 确认派发' : '✅ 确认更新' }}
                  </button>
                  <button
                    v-if="filteredStudents.length > 1 && activeQueueIndex < filteredStudents.length - 1"
                    class="pm-publish-next-btn"
                    :loading="publishingPlan"
                    :disabled="publishingPlan"
                    @click="handlePublishPlan(true)"
                  >
                    ⏭️ 派发并下一位 ({{ activeQueueIndex + 1 }}/{{ filteredStudents.length }})
                  </button>
                </view>
              </view>
            </view>
          </view>

          <!-- TAB 2: EXECUTION & COMPLIANCE TRACKING -->
          <view v-else-if="planModalTab === 'execution'" class="pm-tab-body">
            <view class="pm-exec-grid">
              <view class="pm-exec-stat">
                <text class="pm-es-label">本周计划里程</text>
                <text class="pm-es-val">{{ activeStudent.plan_info?.week_execution?.planned_km || 0 }} km</text>
              </view>
              <view class="pm-exec-stat">
                <text class="pm-es-label">本周已打卡</text>
                <text class="pm-es-val text-green">{{ activeStudent.plan_info?.week_execution?.actual_km || 0 }} km</text>
              </view>
              <view class="pm-exec-stat">
                <text class="pm-es-label">课表达成率</text>
                <text class="pm-es-val text-amber">{{ activeStudent.plan_info?.week_execution?.compliance_rate || 0 }}%</text>
              </view>
              <view class="pm-exec-stat">
                <text class="pm-es-label">力量训练打卡</text>
                <text class="pm-es-val text-cyan">{{ activeStudent.plan_info?.week_execution?.strength_count || 0 }} 次</text>
              </view>
            </view>

            <view v-if="activeStudent.plan_info?.week_execution?.days_brief?.length" class="pm-exec-days-card">
              <text class="pm-sec-title">📅 第 {{ activeStudent.plan_info?.week_execution?.week_index || selectedWeekIdx || 1 }} 周执行</text>
              <view
                v-for="(d, idx) in activeStudent.plan_info.week_execution.days_brief"
                :key="idx"
                class="pm-exec-day-row"
              >
                <view class="pm-edr-left">
                  <text class="pm-edr-dow">{{ d.day_of_week }}</text>
                  <text class="pm-edr-date">{{ d.date ? d.date.slice(5) : '' }}</text>
                  <view class="pm-edr-col">
                    <text class="pm-edr-title">{{ d.title }}</text>
                    <text v-if="d.biometrics_text" class="pm-edr-sub">❤️ {{ d.biometrics_text }} <text v-if="d.recovery_pct">· 恢复{{ d.recovery_pct }}%</text></text>
                    <text v-if="d.actual_execution_text" class="pm-edr-sub">🏃 {{ d.actual_execution_text }}</text>
                    <text v-if="d.athlete_notes" class="pm-edr-sub">💬 {{ d.athlete_notes }}</text>
                  </view>
                </view>
                <view class="pm-edr-right">
                  <text v-if="d.status === 'completed'" class="pm-edr-tag done">
                    ✅ {{ d.actual_km || d.planned_km }}km <text v-if="d.rpe">· RPE {{ d.rpe }}</text>
                  </text>
                  <text v-else-if="d.status === 'missed'" class="pm-edr-tag missed">
                    ⚠️ 缺勤 ({{ d.planned_km }}km)
                  </text>
                  <text v-else-if="d.status === 'rest'" class="pm-edr-tag rest">
                    🛌 休息日
                  </text>
                  <text v-else class="pm-edr-tag pending">
                    ⏳ 待执行 ({{ d.planned_km }}km)
                  </text>
                </view>
              </view>
            </view>

            <view v-if="activeStudent.recent_activities?.length" class="pm-exec-days-card">
              <text class="pm-sec-title">🏃 近期运动</text>
              <view
                v-for="(act, aIdx) in activeStudent.recent_activities"
                :key="aIdx"
                class="pm-exec-day-row"
              >
                <view class="pm-edr-left">
                  <text class="pm-edr-title">{{ act.name }}</text>
                  <text class="pm-edr-date">{{ act.start_time ? act.start_time.slice(0, 16).replace('T', ' ') : '' }}</text>
                </view>
                <view class="pm-edr-right">
                  <text class="pm-edr-tag done">{{ act.distance_km }}km · {{ act.duration_mins }}分钟</text>
                </view>
              </view>
            </view>
          </view>

          <!-- TAB 3: GENERATE NEW DRAFT -->
          <view v-else-if="planModalTab === 'generate'" class="pm-tab-body">
            <view class="pm-gen-card">
              <text class="pm-sec-title">✨ 为【{{ activeStudent.display_name }}】定制草案</text>

              <!-- Goal Type -->
              <view class="pm-gen-type-row">
                <view
                  class="pm-gen-type-btn"
                  :class="{ active: genGoalType === 'race_prep' }"
                  @click="genGoalType = 'race_prep'"
                >
                  🏅 赛事备战
                </view>
                <view
                  class="pm-gen-type-btn"
                  :class="{ active: genGoalType === 'fitness_maintenance' }"
                  @click="genGoalType = 'fitness_maintenance'"
                >
                  🏔️ 日常进阶
                </view>
              </view>

              <view v-if="genGoalType === 'race_prep'" class="pm-gen-section">
                <view v-if="studentUpcomingRaces.length" class="pm-race-chips">
                  <view
                    v-for="(r, rIdx) in studentUpcomingRaces"
                    :key="rIdx"
                    class="pm-race-chip"
                    :class="{ active: genRaceName === r.name }"
                    @click="selectStudentRaceForGen(r)"
                  >
                    🏁 {{ r.name }} ({{ r.race_date }})
                  </view>
                </view>
                <view class="pm-editor-row">
                  <view class="pm-editor-col flex-2">
                    <text class="pm-ed-label">目标赛事名称</text>
                    <input class="pm-ed-input" v-model="genRaceName" placeholder="如：上海马拉松 / 戈壁挑战赛" />
                  </view>
                  <view class="pm-editor-col flex-1">
                    <text class="pm-ed-label">目标完赛时间</text>
                    <input class="pm-ed-input" v-model="genTargetTime" placeholder="3:30:00" />
                  </view>
                </view>
              </view>

              <view class="pm-editor-row">
                <view class="pm-editor-col">
                  <text class="pm-ed-label">周期总周数</text>
                  <view class="pm-wheel-stepper">
                    <view class="pm-ws-btn" @click.stop="stepGenWeeks(-1)">−</view>
                    <picker
                      mode="selector"
                      class="pm-ws-mid"
                      :range="genWeekOptionLabels"
                      :value="Math.max(0, genWeekOptions.indexOf(genWeeks))"
                      @change="(e: any) => genWeeks = genWeekOptions[Number(e.detail.value)] || 4"
                    >
                      <view class="pm-ws-val-wrap">
                        <text class="pm-ws-val">{{ genWeeks }} 周</text>
                        <text class="pm-ws-caret">▾</text>
                      </view>
                    </picker>
                    <view class="pm-ws-btn" @click.stop="stepGenWeeks(1)">+</view>
                  </view>
                </view>
                <view class="pm-editor-col">
                  <text class="pm-ed-label">每周跑步天数</text>
                  <view class="pm-wheel-stepper">
                    <view class="pm-ws-btn" @click.stop="stepGenDays(-1)">−</view>
                    <picker
                      mode="selector"
                      class="pm-ws-mid"
                      :range="genDayOptionLabels"
                      :value="Math.max(0, genDayOptions.indexOf(genDaysPerWeek))"
                      @change="(e: any) => genDaysPerWeek = genDayOptions[Number(e.detail.value)] || 4"
                    >
                      <view class="pm-ws-val-wrap">
                        <text class="pm-ws-val">{{ genDaysPerWeek }} 天/周</text>
                        <text class="pm-ws-caret">▾</text>
                      </view>
                    </picker>
                    <view class="pm-ws-btn" @click.stop="stepGenDays(1)">+</view>
                  </view>
                </view>
              </view>

              <view class="pm-editor-col">
                <text class="pm-ed-label">👨‍🏫 特殊要求 (选填)</text>
                <textarea
                  class="pm-ed-textarea"
                  v-model="genCoachPrompt"
                  :maxlength="250"
                  placeholder="如：该队员近期左膝轻微不适，首周不安排间歇跑，长距离控制在18km以内..."
                />
              </view>

              <button
                class="pm-publish-main-btn"
                :loading="generatingSingleDraft"
                :disabled="generatingSingleDraft"
                @click="handleGenerateSingleDraft"
              >
                {{ generatingSingleDraft ? '生成中...' : '✨ 生成草案' }}
              </button>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── NEW: Club Group Workout Broadcast Modal (跑团公共合练课一键派发) ── -->
    <view v-if="showBroadcastModal" class="modal-mask" @click="showBroadcastModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">📢 合练派课</text>
            <text class="count-pill">全团</text>
          </view>
          <text class="close-btn" @click="showBroadcastModal = false">✕</text>
        </view>
        <scroll-view scroll-y class="modal-body modal-scroll">
          <view class="pm-gen-card">
            <view class="pm-note-presets">
              <view
                v-for="(preset, pIdx) in broadcastPresets"
                :key="pIdx"
                class="pm-note-chip"
                @click="applyBroadcastPreset(preset)"
              >
                ⚡ {{ preset.label }}
              </view>
            </view>
            <view class="pm-editor-col">
              <text class="pm-ed-label">选择合练星期</text>
              <view class="pm-pill-selector">
                <view
                  v-for="dow in [1, 2, 3, 4, 5, 6, 7]"
                  :key="dow"
                  class="pm-mini-pill"
                  :class="{ active: bcDayIndex === dow }"
                  @click="bcDayIndex = dow"
                >
                  {{ ['周一','周二','周三','周四','周五','周六','周日'][dow - 1] }}
                </view>
              </view>
            </view>
            <view class="pm-type-selector">
              <view
                v-for="wt in workoutTypeList"
                :key="wt.value"
                class="pm-type-chip"
                :class="{ active: bcWorkoutType === wt.value }"
                @click="bcWorkoutType = wt.value"
              >
                {{ wt.label }}
              </view>
            </view>
            <view class="pm-editor-row">
              <view class="pm-editor-col flex-2">
                <text class="pm-ed-label">合练课名称</text>
                <input class="pm-ed-input" v-model="bcTitle" placeholder="如：交大合练 间歇速度课" />
              </view>
              <view class="pm-editor-col flex-1">
                <text class="pm-ed-label">距离 (km)</text>
                <input class="pm-ed-input" type="digit" v-model="bcDistanceKm" />
              </view>
            </view>
            <view class="pm-editor-row">
              <view class="pm-editor-col">
                <text class="pm-ed-label">建议配速</text>
                <input class="pm-ed-input" v-model="bcTargetPace" placeholder="按A/B/C组配速执行" />
              </view>
              <view class="pm-editor-col">
                <text class="pm-ed-label">心率区间</text>
                <input class="pm-ed-input" v-model="bcTargetHrZone" placeholder="Zone 3 - Zone 4" />
              </view>
            </view>
            <view class="pm-editor-col">
              <text class="pm-ed-label">合练处方</text>
              <textarea
                class="pm-ed-textarea"
                v-model="bcDescription"
                :maxlength="300"
                placeholder="如：慢跑热身2km + 身训2组 + (400米×5组 间休1分20秒)×2大组..."
              />
            </view>
            <button
              class="pm-publish-main-btn"
              :loading="broadcastingWorkout"
              :disabled="broadcastingWorkout"
              @click="handleBroadcastClubWorkout"
            >
              {{ broadcastingWorkout ? '派发中...' : '🚀 派发至全团课表' }}
            </button>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── NEW: Coach Pace & Intensity Group Template Assignment Modal (配速与强度分组训练模版中心) ── -->
    <view v-if="showTemplateModal" class="modal-mask" @click="showTemplateModal = false" @touchmove.stop.prevent>
      <view class="modal-content plan-modal-content" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">📚 模版库</text>
          </view>
          <text class="close-btn" @click="showTemplateModal = false">✕</text>
        </view>
        <scroll-view scroll-y class="pm-scroll-body">
          <view class="pm-gen-card">
            <!-- Category Filter Pills -->
            <view class="tpl-cat-selector">
              <view
                v-for="cat in templateCategoryOptions"
                :key="cat.val"
                class="tpl-cat-pill"
                :class="{ active: templateCategoryFilter === cat.val }"
                @click="templateCategoryFilter = cat.val"
              >
                {{ cat.label }}
              </view>
            </view>

            <!-- Group Selector Cards -->
            <view class="tpl-group-cards">
              <view
                v-for="tpl in filteredCoachTemplates"
                :key="tpl.id"
                class="tpl-group-card"
                :class="{ active: selectedTemplateId === tpl.id }"
                @click="selectTemplateGroup(tpl.id)"
              >
                <view class="tgc-top">
                  <text class="tgc-name">{{ tpl.short_name }}</text>
                  <text class="tgc-rec">
                    {{ tpl.is_custom ? '🔒 仅我可见' : ('推荐 ' + getTemplateRecCount(tpl.id) + '人') }}
                  </text>
                </view>
                <text class="tgc-pb">{{ tpl.target_pb_label }} · {{ tpl.weekly_km }}km/周 ({{ tpl.days_per_week }}练)</text>
              </view>
            </view>

            <!-- Active Template Pace Zones & Scale/Scope + Custom Template Editor -->
            <view v-if="activeTemplateObj" class="tpl-detail-box">
              <view class="tdb-paces" v-if="activeTemplateObj.pace_zones">
                <text class="tdb-pace-item">🟢 有氧E: {{ activeTemplateObj.pace_zones.easy_pace }}</text>
                <text class="tdb-pace-item">🔵 马拉松M: {{ activeTemplateObj.pace_zones.marathon_pace }}</text>
                <text class="tdb-pace-item">🟠 乳酸阈T: {{ activeTemplateObj.pace_zones.threshold_pace }}</text>
                <text class="tdb-pace-item">🔴 间歇I: {{ activeTemplateObj.pace_zones.interval_pace }}</text>
              </view>

              <view class="pm-editor-col" style="margin-top: 12rpx;">
                <text class="pm-ed-label">跑量缩放 ({{ Math.round((activeTemplateObj.weekly_km || 50) * templateScaleFactor) }}km/周)</text>
                <view class="pm-pill-selector">
                  <view
                    v-for="sc in templateScaleOptions"
                    :key="sc.label"
                    class="pm-mini-pill"
                    :class="{ active: templateScaleFactor === sc.val }"
                    @click="templateScaleFactor = sc.val"
                  >
                    {{ sc.label }}
                  </view>
                </view>
              </view>

              <view class="pm-editor-col" style="margin-top: 10rpx;">
                <text class="pm-ed-label">套用范围</text>
                <view class="pm-pill-selector">
                  <view
                    v-for="scp in templateScopeOptions"
                    :key="scp.val"
                    class="pm-mini-pill"
                    :class="{ active: templateApplyScope === scp.val }"
                    @click="templateApplyScope = scp.val"
                  >
                    {{ scp.label }}
                  </view>
                </view>
              </view>

              <view v-if="templateApplyScope === 'full_plan'" class="pm-editor-col" style="margin-top: 10rpx;">
                <text class="pm-ed-label">周期长度</text>
                <view class="pm-pill-selector">
                  <view
                    v-for="wn in templateWeeksOptions"
                    :key="wn"
                    class="pm-mini-pill"
                    :class="{ active: templateWeeksCount === wn }"
                    @click="templateWeeksCount = wn"
                  >
                    {{ wn }}周
                  </view>
                </view>
              </view>

              <view class="tpl-canova-box">
                <view class="tpl-canova-head" @click="templateCanovaProgression = !templateCanovaProgression">
                  <text class="tpl-canova-title">🔄 Canova 逐周递进</text>
                  <switch
                    :checked="templateCanovaProgression"
                    color="#10b981"
                    style="transform: scale(0.7);"
                    @change.stop="templateCanovaProgression = $event.detail.value"
                  />
                </view>
                <view v-if="templateCanovaProgression" class="tpl-canova-chips">
                  <text v-for="(stg, sIdx) in templateCanovaOutline" :key="sIdx" class="tpl-canova-chip">{{ stg }}</text>
                </view>
              </view>

              <!-- 7-Day Standard Schedule Preview (Read-Only on Miniapp; Custom Template Creation on Web) -->
              <view class="tdb-days-list">
                <view class="tms-header" style="margin-bottom: 8rpx;">
                  <text class="pm-ed-label">📅 7日课表预览</text>
                </view>

                <view
                  v-for="(td, tdIdx) in templateCustomDays"
                  :key="tdIdx"
                  class="tdb-day-row"
                >
                  <text class="tdb-dow">{{ td.day_of_week }}</text>
                  <view class="tdb-main">
                    <text class="tdb-title">{{ td.title }} ({{ td.distance_km }}km · {{ td.target_pace }})</text>
                    <text class="tdb-desc">{{ td.description }}</text>
                  </view>
                </view>
              </view>
            </view>

            <!-- Member Selection -->
            <view class="tpl-members-section">
              <view class="tms-header">
                <text class="pm-ed-label">勾选队员 (已选 {{ selectedMemberIdsForTemplate.length }}人)</text>
                <view class="tms-quick-btns">
                  <text class="tms-qbtn" @click="selectRecMembersForCurrentTemplate">🎯 选本组推荐</text>
                  <text class="tms-qbtn" @click="selectUnscheduledMembers">⚪ 选未排课</text>
                  <text class="tms-qbtn" @click="selectAllMembersForTemplate">全选</text>
                  <text class="tms-qbtn" @click="selectedMemberIdsForTemplate = []">清空</text>
                </view>
              </view>

              <view class="tms-grid">
                <view
                  v-for="stu in students"
                  :key="stu.user_id"
                  class="tms-member-chip"
                  :class="{ checked: selectedMemberIdsForTemplate.includes(stu.user_id) }"
                  @click="toggleMemberForTemplate(stu.user_id)"
                >
                  <view class="tms-m-left">
                    <text class="tms-m-name">{{ stu.display_name }}</text>
                    <text class="tms-m-sub">
                      {{ stu.gender_label ? stu.gender_label : '' }}{{ stu.age ? (stu.gender_label ? '·' : '') + stu.age + '岁 · ' : (stu.gender_label ? ' · ' : '') }}{{ stu.recommended_group?.group_code || 'D组' }}{{ stu.recommended_group?.recommended_scale && stu.recommended_group.recommended_scale < 1 ? '(' + Math.round(stu.recommended_group.recommended_scale * 100) + '%)' : '' }} · CTL {{ stu.ctl || 0 }}
                    </text>
                  </view>
                  <text class="tms-m-check">
                    {{ selectedMemberIdsForTemplate.includes(stu.user_id) ? '☑️' : '⬜' }}
                  </text>
                </view>
              </view>
            </view>

            <!-- Action Buttons -->
            <view class="tpl-action-col">
              <button
                class="pm-publish-main-btn"
                :loading="assigningTemplate"
                :disabled="assigningTemplate || selectedMemberIdsForTemplate.length === 0"
                @click="handleAssignTemplateToMembers(true, true)"
              >
                🚀 分配并逐人微调 ({{ selectedMemberIdsForTemplate.length }}人)
              </button>
              <view class="tpl-sub-actions">
                <button
                  class="cph-batch-btn secondary"
                  :disabled="assigningTemplate || selectedMemberIdsForTemplate.length === 0"
                  @click="handleAssignTemplateToMembers(true, false)"
                >
                  🟠 存为草案
                </button>
                <button
                  class="cph-batch-btn pipeline"
                  :disabled="assigningTemplate || selectedMemberIdsForTemplate.length === 0"
                  @click="handleAssignTemplateToMembers(false, false)"
                >
                  🟢 直接发布
                </button>
              </view>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── Switch Club Modal (教练切换管理的跑团) ── -->
    <view v-if="showSwitchModal" class="modal-mask" @click="showSwitchModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">切换跑团</text>
            <text class="count-pill">{{ userClubs.length }} 个跑团</text>
          </view>
          <text class="close-btn" @click="showSwitchModal = false">✕</text>
        </view>

        <view class="modal-body modal-scroll">
          <view class="modal-clubs-list">
            <view
              v-for="c in userClubs"
              :key="c.id"
              class="modal-club-card"
              :class="{ 'is-current': currentClub?.id === c.id }"
              @click="handleSwitchClub(c)"
            >
              <image class="mcc-logo" :src="c.logo_url || '/static/logo-square.png'" mode="aspectFill" />
              <view class="mcc-info">
                <view class="mcc-name-row">
                  <text class="mcc-name">{{ c.name }}</text>
                  <text class="mcc-city">📍 {{ c.city || '上海' }}</text>
                </view>
                <view class="mcc-meta">
                  <text class="mcc-role-tag" :class="'role-' + c.role">
                    {{ c.role === 'owner' ? '👑 团长' : c.role === 'coach' ? '🧢 教练' : '🏃 团员' }}
                  </text>
                </view>
              </view>
              <view class="mcc-action">
                <text v-if="currentClub?.id === c.id" class="mcc-current-tag">当前 ✓</text>
                <button v-else class="mcc-switch-btn" @click.stop="handleSwitchClub(c)">
                  ⇄ 切换
                </button>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 地图选点与大头针精确定位弹窗 -->
    <MapPinPickerModal
      :visible="showCoachMapPinModal"
      :initialKeyword="newEvtLocation"
      :initialAddress="newEvtLocationDetail"
      :initialLat="newEvtLatitude"
      :initialLng="newEvtLongitude"
      @close="showCoachMapPinModal = false"
      @confirm="onCoachMapPinConfirm"
    />
  </view>
</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import PageSkeleton from "../../components/PageSkeleton.vue";
import MapPinPickerModal from "../../components/MapPinPickerModal.vue";
import PacerClubRadarSection from "../../components/PacerClubRadarSection.vue";
import { explainTerm } from "../../utils/glossary";
import { trackClick, trackModal, trackSubView, trackFunnelStep } from "../../utils/telemetry";
import { ref, computed } from "vue";
import { onShow, onPullDownRefresh, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import {
  request,
  getStoredUser,
  checkAndAutoLogin,
  UserProfile,
  getActiveClubId,
  setActiveClubId,
  resolveActiveClub,
  syncTabBarIndex,
} from "../../utils/api";
import {
  DEFAULT_GROUP_RUN_TEMPLATES,
  GroupRunTemplateItem,
  GroupRunVenuePreset,
  resolveNextWeekdayIso,
  searchGroupRunGeocode,
  openRunLocation,
  formatMeetTime,
} from "../../utils/groupRun";

const user = ref<UserProfile | null>(null);
const currentClub = ref<any>(null);
const userRole = ref("member");
const userClubs = ref<any[]>([]);
const showSwitchModal = ref(false);
const loading = ref(true);

function formatAiJournal(raw: any): string {
  if (!raw) return "";
  if (typeof raw === "object") {
    return String(raw.evaluation || raw.summary || raw.critique || raw.content || "");
  }
  const str = String(raw).trim();
  if (str.startsWith("{")) {
    try {
      const parsed = JSON.parse(str);
      if (parsed && typeof parsed === "object") {
        return String(parsed.evaluation || parsed.summary || parsed.critique || parsed.content || "");
      }
    } catch (_) {}
  }
  return str;
}

// Centralized 4-Module Coach Workbench States
const coachBenchTab = ref<"cockpit" | "feed" | "events" | "report_manage">("cockpit");
const clubFeed = ref<any[]>([]);
const loadingFeed = ref(false);
const feedCommentInputs = ref<Record<string, string>>({});
const submittingFeedComment = ref<Record<string, boolean>>({});
const clubEvents = ref<any[]>([]);
const showNewEventForm = ref(false);
const showCoachMapPinModal = ref(false);
const selectedEvtTplId = ref("");
const customGroupRunTemplates = ref<GroupRunTemplateItem[]>([]);
const newEvtTitle = ref("");
const newEvtTargetKm = ref("22");
const newEvtMeetDate = ref(resolveNextWeekdayIso(0));
const newEvtMeetTime = ref("06:30");
const newEvtLocation = ref("");
const newEvtLocationDetail = ref("");
const newEvtLatitude = ref<number | null>(null);
const newEvtLongitude = ref<number | null>(null);
const lastCoachGeocodedName = ref("");
const newEvtPaceReq = ref("A组4:15 / B组4:50 / C组5:30");
const newEvtRules = ref("");
const creatingEvent = ref(false);

const allGroupRunTemplates = computed<GroupRunTemplateItem[]>(() => {
  return [...customGroupRunTemplates.value, ...DEFAULT_GROUP_RUN_TEMPLATES];
});

const newEvtMapMarkers = computed(() => {
  if (!newEvtLatitude.value || !newEvtLongitude.value) return [];
  return [
    {
      id: 1,
      latitude: Number(newEvtLatitude.value),
      longitude: Number(newEvtLongitude.value),
      title: newEvtLocation.value || "约跑集合点",
      width: 28,
      height: 36,
      callout: {
        content: `📍 ${newEvtLocation.value || "约跑集合点"}`,
        color: "#ffffff",
        fontSize: 12,
        borderRadius: 8,
        bgColor: "#2563eb",
        padding: 6,
        display: "ALWAYS",
      },
    },
  ];
});
const coachRepPeriod = ref<"week" | "month">("week");
const coachRepOffset = ref<number>(0);
const coachRepTrailMode = ref<"include" | "exclude_pace" | "exclude_all">("include");
const coachReportData = ref<any>(null);
const loadingCoachReport = ref(false);

const coachedClubs = computed(() => {
  return userClubs.value.filter(
    (c: any) =>
      c.role === "owner" ||
      c.role === "coach" ||
      (user.value?.id && c.owner_id === user.value.id)
  );
});

const coachQuickComments = [
  { label: "👏 配速稳·有氧佳", text: "🧢 教练点评：本次配速与心率控制非常稳，有氧基础扎实，继续保持！" },
  { label: "⚠️ 心率偏高·排酸", text: "🧢 教练点评：本次心率偏高，明后天注意低心率排酸慢跑与保证充足睡眠恢复。" },
  { label: "🔥 间歇完成度高", text: "🧢 教练点评：核心强度课完成质量很高！跑后务必做好臀腿拉伸与蛋白质补充。" },
  { label: "💪 LSD耐力在线", text: "🧢 教练点评：长距离耐力在线，注意每5km补水补胶节奏，前半程严防起跑过快。" },
];

const summary = ref<any>(null);
const students = ref<any[]>([]);
const filterStatus = ref("all");
const filterPlanState = ref<"all" | "injury_alert" | "draft_pending" | "published" | "none">("all");
const filterGroupCode = ref("all");
const searchQuery = ref("");
const sortBy = ref<"danger_first" | "peak_first">("danger_first");
const batchGenerating = ref(false);

const groupFilterOptions = [
  { code: "240组", label: "👑 240组·精英" },
  { code: "A组", label: "🔥 A组·破三" },
  { code: "B组", label: "⚡ B组·破330" },
  { code: "C组", label: "🛡️ C组·破四" },
  { code: "D组", label: "🌱 D组·筑基" },
  { code: "E组", label: "🧘 E组·减量" },
  { code: "戈赛A组", label: "🏜️ 戈赛A组" },
  { code: "越野组", label: "⛰️ 越野组" },
];

const singleQuickScope = ref<"current_week" | "full_plan">("current_week");

function openStudentScienceAnalysis(s: any) {
  if (!s?.user_id) return;
  trackClick("cockpit_inspect_student_vdot", `教练查看学员VDOT档案：${s.display_name || "队员"}`, {
    target_uid: s.user_id,
  });
  const nameParam = encodeURIComponent(s.display_name || "队员");
  uni.navigateTo({
    url: `/pages/analysis/analysis?target_uid=${encodeURIComponent(s.user_id)}&target_name=${nameParam}`
  });
}

// Coach Group Template Batch Assignment & Custom Template States
const showTemplateModal = ref(false);
const coachTemplates = ref<any[]>([]);
const templateCategoryFilter = ref("all");
const selectedTemplateId = ref("group_b_sub330");
const templateCustomDays = ref<any[]>([]);
const editingTplDayIdx = ref<number>(-1);
const templateScaleFactor = ref(1.0);
const templateApplyScope = ref<"full_plan" | "current_week" | "next_week">("full_plan");
const selectedMemberIdsForTemplate = ref<string[]>([]);
const assigningTemplate = ref(false);

const showCustomTplEditor = ref(false);
const tplEditGroupCode = ref("");
const tplEditShortName = ref("");
const tplEditCategory = ref("marathon");
const tplEditTargetPb = ref("");
const tplEditPaceEasy = ref("");
const tplEditPaceMarathon = ref("");
const tplEditPaceInterval = ref("");
const savingCustomTemplate = ref(false);

const showSaveWeekTplBox = ref(false);
const saveWeekTplCode = ref("");
const saveWeekTplName = ref("");

const templateCategoryOptions = [
  { val: "all", label: "全部模版" },
  { val: "marathon", label: "🏃全马240/A~E" },
  { val: "gobi", label: "🏜️戈壁竞赛" },
  { val: "trail", label: "⛰️长距离越野" },
  { val: "custom", label: "🔒我的专属模版" },
];

const filteredCoachTemplates = computed(() => {
  if (templateCategoryFilter.value === "all") return coachTemplates.value;
  if (templateCategoryFilter.value === "custom") {
    return coachTemplates.value.filter((t: any) => t.is_custom);
  }
  return coachTemplates.value.filter(
    (t: any) => (t.category || "marathon") === templateCategoryFilter.value
  );
});

const quickTemplateBarOptions = computed(() => {
  if (coachTemplates.value.length > 0) {
    return coachTemplates.value.map((t: any) => ({
      id: t.id,
      label: `${t.short_name}(${t.weekly_km || 50}k)`,
    }));
  }
  return [
    { id: "group_s_sub240", label: "👑 240组·精英(98k)" },
    { id: "group_a_sub300", label: "🔥 A组·破三(76k)" },
    { id: "group_b_sub330", label: "⚡ B组·破330(56k)" },
    { id: "group_c_sub400", label: "🛡️ C组·破四(45k)" },
    { id: "group_d_base", label: "🌱 D组·筑基(32k)" },
    { id: "group_e_taper", label: "🧘 E组·减量(26k)" },
    { id: "group_gobi_a", label: "🏜️ 戈赛A组(88k)" },
    { id: "group_trail_ultra", label: "⛰️ 越野组(68k)" },
  ];
});

const templateScaleOptions = [
  { val: 0.85, label: "85%减量" },
  { val: 0.9, label: "90%" },
  { val: 1.0, label: "100%标准" },
  { val: 1.1, label: "110%强化" },
];

const templateScopeOptions = [
  { val: "full_plan", label: "生成周期计划" },
  { val: "current_week", label: "仅替换当前周" },
  { val: "next_week", label: "仅写入下一周" },
];

const templateWeeksOptions = [4, 6, 8, 12];
const templateWeeksCount = ref(8);
const templateCanovaProgression = ref(true);

const templateCanovaOutline = computed<string[]>(() => {
  const tpl = activeTemplateObj.value;
  const outline = tpl?.canova_outline?.[String(templateWeeksCount.value)];
  if (templateApplyScope.value !== "full_plan") {
    return ["按队员所处周次自动匹配对应阶段课表"];
  }
  return Array.isArray(outline) ? outline : [];
});

const activeTemplateObj = computed(() => {
  return (
    coachTemplates.value.find((t: any) => t.id === selectedTemplateId.value) ||
    coachTemplates.value[0] ||
    null
  );
});

function syncMiniTemplateEditorFields(tpl: any) {
  if (!tpl) return;
  templateCustomDays.value = JSON.parse(JSON.stringify(tpl.days_template || []));
  editingTplDayIdx.value = -1;
  tplEditGroupCode.value = tpl.group_code || "特训组";
  tplEditShortName.value = tpl.short_name || tpl.name || "教练自定义模版";
  tplEditCategory.value = tpl.category || "marathon";
  tplEditTargetPb.value = tpl.target_pb_label || tpl.target_level || "";
  const pz = tpl.pace_zones || {};
  tplEditPaceEasy.value = pz.easy_pace || pz.easy || "";
  tplEditPaceMarathon.value = pz.marathon_pace || pz.marathon || "";
  tplEditPaceInterval.value = pz.interval_pace || pz.interval || "";
}

function getGroupCount(code: string): number {
  return students.value.filter(
    (s: any) =>
      s.plan_info?.template_group_code === code || s.recommended_group?.group_code === code
  ).length;
}

function getTemplateRecCount(tplId: string): number {
  return students.value.filter((s: any) => s.recommended_group?.template_id === tplId).length;
}

// Coach Plan Review Modal States
const showPlanModal = ref(false);
const activeStudent = ref<any | null>(null);
const planModalTab = ref<"review" | "execution" | "generate">("review");
const planLoading = ref(false);
const studentActivePlan = ref<any | null>(null);
const studentDraftPlan = ref<any | null>(null);
const studentGoal = ref<any | null>(null);
const studentUpcomingRaces = ref<any[]>([]);
const viewingDraft = ref(true);
const selectedWeekIdx = ref(1);

const editPlanTitle = ref("");
const editPlanOverview = ref("");
const editMacroRoadmap = ref("");
const coachReviewNote = ref("");
const weekSummaryOverride = ref("");
const coachWeeklyDiagnosis = ref("");
const savingPlan = ref(false);
const savingWeekSummary = ref(false);
const publishingPlan = ref(false);
const hasUnconfirmedPlanChanges = ref(false);
const originalPlanBackup = ref<{ active: any; draft: any }>({ active: null, draft: null });

// Rolling W+1 Generator States
const showRollNextWeekPanel = ref(false);
const rollVolumeScale = ref<number | undefined>(undefined);
const rollWeekTheme = ref("");
const rollCoachNote = ref("");
const rollingNextWeek = ref(false);
const rollScaleOptions = [
  { label: "智能自适应", value: undefined },
  { label: "减量85%", value: 0.85 },
  { label: "维持100%", value: 1.0 },
  { label: "递增105%", value: 1.05 },
];

// Club Group Workout Broadcast States
const showBroadcastModal = ref(false);
const bcDayIndex = ref(2);
const bcWorkoutType = ref("interval");
const bcTitle = ref("交大操场间歇合练");
const bcDistanceKm = ref(12);
const bcTargetPace = ref("按A/B/C组配速执行");
const bcTargetHrZone = ref("Zone 4");
const bcDescription = ref("慢跑热身2km + 身训2组 + (400米×5组 间休1分20秒)×2大组 + 慢跑冷身2km");
const broadcastingWorkout = ref(false);

const broadcastPresets = [
  {
    label: "周二交大间歇速度课",
    day_index: 2,
    workout_type: "interval",
    title: "交大操场间歇合练",
    distance_km: 12,
    target_pace: "按A/B/C组配速执行",
    target_hr_zone: "Zone 4",
    description: "慢跑热身2km + 身训2组 + (400米×5组 间休1分20秒)×2大组 + 慢跑冷身2km",
  },
  {
    label: "周日有氧LSD长距离合练",
    day_index: 7,
    workout_type: "long_run",
    title: "跑团周末有氧LSD合练",
    distance_km: 22,
    target_pace: "5:15-5:40/km",
    target_hr_zone: "Zone 2",
    description: "世纪公园/徐汇滨江跑团集中补给合练，前半程严格压心率，每5km补水补胶。",
  },
  {
    label: "周四抗乳酸节奏合练",
    day_index: 4,
    workout_type: "tempo_run",
    title: "周四乳酸阈节奏跑合练",
    distance_km: 14,
    target_pace: "4:35-4:50/km",
    target_hr_zone: "Zone 3-4",
    description: "2km热身 + 8-10km乳酸阈巡航节奏跑 + 2km冷身慢跑。",
  },
];

const editingDayIdx = ref<number | null>(null);
const editDayForm = ref<any>({
  workout_type: "easy_run",
  title: "",
  distance_km: 8,
  duration_minutes: 48,
  target_pace: "",
  target_hr_zone: "",
  description: "",
  actual_execution_text: "",
  rpe: "",
  athlete_notes: "",
  hrv: "",
  resting_hr: "",
  recovery_pct: "",
  swap_with_day_index: 0,
});

// Generate Form States
const genGoalType = ref<"race_prep" | "fitness_maintenance">("race_prep");
const genRaceName = ref("");
const genTargetTime = ref("3:30:00");
const genWeeks = ref(4);
const genDaysPerWeek = ref(4);
const genWeekOptions = [4, 6, 8, 10, 12, 16];
const genWeekOptionLabels = [
  "4 周 · 冲刺微周期",
  "6 周 · 标准进阶",
  "8 周 · 经典备战",
  "10 周 · 进阶周期",
  "12 周 · 完整周期",
  "16 周 · 长线备赛",
];
const genDayOptions = [3, 4, 5, 6];
const genDayOptionLabels = [
  "3 天/周 · 轻量均衡",
  "4 天/周 · 经典推荐",
  "5 天/周 · 进阶强化",
  "6 天/周 · 严肃跑者",
];
function stepGenWeeks(delta: number) {
  const curIdx = genWeekOptions.indexOf(genWeeks.value);
  const baseIdx = curIdx >= 0 ? curIdx : 0;
  const nextIdx = Math.min(genWeekOptions.length - 1, Math.max(0, baseIdx + delta));
  genWeeks.value = genWeekOptions[nextIdx];
}
function stepGenDays(delta: number) {
  const curIdx = genDayOptions.indexOf(genDaysPerWeek.value);
  const baseIdx = curIdx >= 0 ? curIdx : 1;
  const nextIdx = Math.min(genDayOptions.length - 1, Math.max(0, baseIdx + delta));
  genDaysPerWeek.value = genDayOptions[nextIdx];
}
const genCoachPrompt = ref("");
const generatingSingleDraft = ref(false);

const workoutTypeList = [
  { value: "easy_run", label: "🍃 轻松跑" },
  { value: "long_run", label: "🏔️ 长距离" },
  { value: "tempo_run", label: "🔥 节奏跑" },
  { value: "interval", label: "⚡ 间歇跑" },
  { value: "race", label: "🏆 比赛日" },
  { value: "rest", label: "🛌 休息日" },
];

const coachNoteTemplates = [
  "按计划稳步推进，重点保证轻松跑低心率与跑后拉伸睡眠。",
  "近期疲劳指数偏高，已为你适度下调跑量，严禁盲目冲配速。",
  "本周重点是周末长距离有氧耐力课，注意前半程压住心率并做好补给。",
];

const currentReviewPlan = computed(() => {
  if (viewingDraft.value && studentDraftPlan.value) return studentDraftPlan.value;
  return studentActivePlan.value || studentDraftPlan.value || null;
});

const currentSelectedWeek = computed(() => {
  const weeks = currentReviewPlan.value?.schedule_data?.weeks || [];
  return weeks.find((w: any) => Number(w.week_index) === Number(selectedWeekIdx.value)) || weeks[0] || null;
});

function hasStudentInjuryOrHrvAlert(s: any): boolean {
  const we = s?.plan_info?.week_execution;
  if (we?.injury_note && we.injury_note !== "无") return true;
  if ((we?.days_brief || []).some((d: any) => d.hrv_warning)) return true;
  if (s?.status_level === "danger") return true;
  return false;
}

const injuryAlertCount = computed(() => {
  return students.value.filter((s) => hasStudentInjuryOrHrvAlert(s)).length;
});

const activeQueueIndex = computed(() => {
  if (!activeStudent.value) return -1;
  return filteredStudents.value.findIndex((s) => s.user_id === activeStudent.value.user_id);
});

function getWorkoutLabel(wType?: string): string {
  const found = workoutTypeList.find((w) => w.value === wType);
  return found ? found.label : "🍃 轻松跑";
}

const isAuthorized = computed(() => {
  if (!user.value || !currentClub.value) return false;
  return (
    userRole.value === "owner" ||
    userRole.value === "coach" ||
    currentClub.value.owner_id === user.value.id
  );
});

const filteredStudents = computed(() => {
  let list = [...students.value];
  if (filterStatus.value !== "all") {
    list = list.filter((s) => s.status_level === filterStatus.value);
  }
  if (filterGroupCode.value !== "all") {
    list = list.filter(
      (s) =>
        s.plan_info?.template_group_code === filterGroupCode.value ||
        s.recommended_group?.group_code === filterGroupCode.value
    );
  }
  if (filterPlanState.value !== "all") {
    list = list.filter((s) => {
      const pState = s.plan_info?.plan_state || "none";
      if (filterPlanState.value === "injury_alert") return hasStudentInjuryOrHrvAlert(s);
      if (filterPlanState.value === "draft_pending") return pState === "draft_pending" || s.plan_info?.has_draft_plan;
      if (filterPlanState.value === "published") return pState === "published" || pState === "self_active" || s.plan_info?.has_active_plan;
      if (filterPlanState.value === "none") return pState === "none";
      return true;
    });
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase();
    list = list.filter(
      (s) =>
        (s.display_name || "").toLowerCase().includes(q) ||
        (s.user_id || "").toLowerCase().includes(q)
    );
  }

  // 以 TSB 状态排序 (预警优先 vs 巅峰优先)
  const dangerFirstRanks: Record<string, number> = { danger: 1, tired: 2, optimal: 3, peak: 4, none: 5 };
  const peakFirstRanks: Record<string, number> = { peak: 1, optimal: 2, tired: 3, danger: 4, none: 5 };

  list.sort((a, b) => {
    const rankMap = sortBy.value === "peak_first" ? peakFirstRanks : dangerFirstRanks;
    const rankA = rankMap[a.status_level] ?? 99;
    const rankB = rankMap[b.status_level] ?? 99;
    if (rankA !== rankB) {
      return rankA - rankB;
    }
    const tsbA = typeof a.tsb === "number" ? a.tsb : 0;
    const tsbB = typeof b.tsb === "number" ? b.tsb : 0;
    if (sortBy.value === "peak_first") {
      return tsbB - tsbA;
    } else {
      return tsbA - tsbB;
    }
  });

  return list;
});

function setSortBy(order: "danger_first" | "peak_first") {
  sortBy.value = order;
}

function resetAllFilters() {
  filterStatus.value = "all";
  filterPlanState.value = "all";
  filterGroupCode.value = "all";
}

async function openTemplateAssignModal(presetGroupId?: string, preselectStudentId?: string) {
  showTemplateModal.value = true;
  templateCategoryFilter.value = "all";
  showCustomTplEditor.value = false;
  try {
    const res = await request(
      `/api/coach/plan/templates?club_id=${currentClub.value?.id || ""}&operator_uid=${user.value?.id || ""}`
    );
    coachTemplates.value = res?.templates || [];
  } catch (e) {
    console.error("Failed to load templates:", e);
  }
  const targetId = presetGroupId || selectedTemplateId.value || "group_b_sub330";
  selectedTemplateId.value = targetId;
  const tpl =
    coachTemplates.value.find((t: any) => t.id === targetId) || coachTemplates.value[0];
  if (tpl) {
    syncMiniTemplateEditorFields(tpl);
  }
  templateApplyScope.value = "full_plan";
  if (preselectStudentId) {
    selectedMemberIdsForTemplate.value = [preselectStudentId];
    const preStu = students.value.find((s: any) => s.user_id === preselectStudentId);
    templateScaleFactor.value = preStu?.recommended_group?.recommended_scale || 1.0;
  } else {
    templateScaleFactor.value = 1.0;
    selectRecMembersForCurrentTemplate();
  }
}

function selectTemplateGroup(tplId: string) {
  selectedTemplateId.value = tplId;
  const tpl = coachTemplates.value.find((t: any) => t.id === tplId);
  if (tpl) {
    syncMiniTemplateEditorFields(tpl);
  }
  selectRecMembersForCurrentTemplate();
}

async function handleSaveOrCloneCustomTemplate(overwriteCurrent: boolean) {
  if (!user.value?.id || !activeTemplateObj.value || savingCustomTemplate.value) return;
  const codeTrim = tplEditGroupCode.value.trim() || "特训组";
  const nameTrim = tplEditShortName.value.trim() || "教练专属定制模版";
  const computedKm = Math.round(
    templateCustomDays.value.reduce((acc: number, d: any) => acc + (Number(d.distance_km) || 0), 0)
  );
  const computedDays = templateCustomDays.value.filter(
    (d: any) => d.workout_type !== "rest" && (Number(d.distance_km) || 0) > 0
  ).length;

  savingCustomTemplate.value = true;
  try {
    const baseTpl = activeTemplateObj.value;
    const res = await request("/api/coach/plan/templates", "POST", {
      club_id: currentClub.value?.id || "",
      operator_uid: user.value.id,
      template_id: overwriteCurrent && baseTpl.is_custom ? baseTpl.id : undefined,
      base_template_id: baseTpl.id,
      group_code: codeTrim,
      name:
        overwriteCurrent || nameTrim !== baseTpl.short_name
          ? nameTrim
          : `${nameTrim} (定制)`,
      short_name:
        overwriteCurrent || nameTrim !== baseTpl.short_name
          ? nameTrim
          : `${nameTrim} (定制)`,
      category: tplEditCategory.value || "custom",
      target_level: tplEditTargetPb.value,
      weekly_km: computedKm || baseTpl.weekly_km || 60,
      days_per_week: computedDays || baseTpl.days_per_week || 5,
      pace_zones: {
        ...(baseTpl.pace_zones || {}),
        easy: tplEditPaceEasy.value,
        easy_pace: tplEditPaceEasy.value,
        marathon: tplEditPaceMarathon.value,
        marathon_pace: tplEditPaceMarathon.value,
        interval: tplEditPaceInterval.value,
        interval_pace: tplEditPaceInterval.value,
      },
      days_template: templateCustomDays.value,
    });
    if (res?.templates) {
      coachTemplates.value = res.templates;
    }
    if (res?.template?.id) {
      selectedTemplateId.value = res.template.id;
      syncMiniTemplateEditorFields(res.template);
    }
    showCustomTplEditor.value = false;
    uni.showToast({ title: "已存为专属模版 ✓", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: e.message || "保存模版失败", icon: "none" });
  } finally {
    savingCustomTemplate.value = false;
  }
}

async function handleDeleteCustomTemplate(tplId: string) {
  if (!user.value?.id || !tplId) return;
  uni.showModal({
    title: "删除自定义模版",
    content: "确定要删除这个教练自定义训练模版吗？",
    success: async (mRes) => {
      if (!mRes.confirm) return;
      try {
        const res = await request(
          `/api/coach/plan/templates/${tplId}?club_id=${currentClub.value?.id || ""}&operator_uid=${user.value?.id}`,
          "DELETE"
        );
        if (res?.templates) {
          coachTemplates.value = res.templates;
          const first = res.templates[0];
          if (first) {
            selectedTemplateId.value = first.id;
            syncMiniTemplateEditorFields(first);
          }
        }
        uni.showToast({ title: "已删除模版", icon: "success" });
      } catch (e: any) {
        uni.showToast({ title: e.message || "删除失败", icon: "none" });
      }
    },
  });
}

function openSaveWeekAsTemplateBox() {
  saveWeekTplCode.value =
    currentReviewPlan.value?.schedule_data?.template_group_code || "特训组";
  saveWeekTplName.value = `✨ ${activeStudent.value?.display_name || "专属"}W${selectedWeekIdx.value}定制模版`;
  showSaveWeekTplBox.value = !showSaveWeekTplBox.value;
}

async function handleSaveCurrentWeekAsTemplate() {
  const planObj = currentReviewPlan.value;
  if (!planObj?.id || !user.value?.id || savingCustomTemplate.value) return;
  savingCustomTemplate.value = true;
  try {
    const res = await request("/api/coach/plan/templates", "POST", {
      club_id: currentClub.value?.id || "",
      operator_uid: user.value.id,
      from_plan_id: planObj.id,
      from_week_index: selectedWeekIdx.value,
      group_code: saveWeekTplCode.value.trim() || "特训组",
      name: saveWeekTplName.value.trim() || "✨ 教练定制周模版",
      short_name: saveWeekTplName.value.trim() || "✨ 教练定制周模版",
      category: "custom",
      macro_roadmap: editMacroRoadmap.value,
      coach_review_note: coachReviewNote.value,
    });
    if (res?.templates) {
      coachTemplates.value = res.templates;
    }
    showSaveWeekTplBox.value = false;
    uni.showToast({ title: "已存为跑团新模版 ✓", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: e.message || "保存失败", icon: "none" });
  } finally {
    savingCustomTemplate.value = false;
  }
}

function selectRecMembersForCurrentTemplate() {
  const tplId = selectedTemplateId.value;
  selectedMemberIdsForTemplate.value = students.value
    .filter((s: any) => s.recommended_group?.template_id === tplId)
    .map((s: any) => s.user_id);
}

function selectUnscheduledMembers() {
  selectedMemberIdsForTemplate.value = students.value
    .filter((s: any) => (s.plan_info?.plan_state || "none") === "none")
    .map((s: any) => s.user_id);
}

function selectAllMembersForTemplate() {
  selectedMemberIdsForTemplate.value = students.value.map((s: any) => s.user_id);
}

function toggleMemberForTemplate(uid: string) {
  const idx = selectedMemberIdsForTemplate.value.indexOf(uid);
  if (idx >= 0) {
    selectedMemberIdsForTemplate.value.splice(idx, 1);
  } else {
    selectedMemberIdsForTemplate.value.push(uid);
  }
}

async function handleAssignTemplateToMembers(asDraft: boolean, openPipelineAfter: boolean) {
  if (!currentClub.value?.id || !user.value?.id || selectedMemberIdsForTemplate.value.length === 0 || assigningTemplate.value) {
    return;
  }
  const tplName = activeTemplateObj.value?.short_name || selectedTemplateId.value;
  const cnt = selectedMemberIdsForTemplate.value.length;
  uni.showModal({
    title: asDraft ? "确认分配待审草案" : "确认派发并更新计划",
    content: `确定将【${tplName}】${asDraft ? "作为待审草案分配" : "正式派发并更新"}给已选的 ${cnt} 名队员吗？确认后将写入数据库。`,
    confirmText: asDraft ? "确认分配草案" : "确认派发更新",
    cancelText: "取消",
    confirmColor: "#10b981",
    success: async (mRes) => {
      if (!mRes.confirm) return;
      assigningTemplate.value = true;
      uni.showLoading({ title: "正在分配训练模版...", mask: true });
      try {
        const res = await request("/api/coach/plan/assign-template", "POST", {
          club_id: currentClub.value.id,
          operator_uid: user.value!.id,
          template_id: selectedTemplateId.value,
          target_user_ids: selectedMemberIdsForTemplate.value,
          apply_scope: templateApplyScope.value,
          weeks_count: templateWeeksCount.value,
          canova_progression: templateCanovaProgression.value,
          as_draft: asDraft,
          scale_factor: templateScaleFactor.value,
          custom_days: templateCustomDays.value,
        });
        uni.hideLoading();
        trackFunnelStep("cockpit_assign_template", `教练批量分配训练模版：${tplName}`, {
          club_id: currentClub.value.id,
          count: cnt,
          as_draft: asDraft,
        });
        const assignedSet = new Set(selectedMemberIdsForTemplate.value);
        showTemplateModal.value = false;
        await loadCockpitData(currentClub.value.id);

        if (openPipelineAfter) {
          if (asDraft) {
            filterPlanState.value = "draft_pending";
          }
          const firstStu =
            students.value.find((s: any) => assignedSet.has(s.user_id)) || filteredStudents.value[0];
          if (firstStu) {
            await openStudentPlanModal(firstStu);
          }
        } else {
          uni.showModal({
            title: "模版分配完成",
            content: res?.message || "已成功批量分配组别训练模版！",
            showCancel: false,
          });
        }
      } catch (e: any) {
        uni.hideLoading();
        uni.showToast({ title: e.message || "分配训练模版失败", icon: "none" });
      } finally {
        assigningTemplate.value = false;
      }
    },
  });
}

async function handleSingleQuickApplyTemplate(templateId: string, scopeOverride?: "current_week" | "full_plan") {
  if (!activeStudent.value?.user_id || !user.value?.id) return;
  const effScope = scopeOverride || singleQuickScope.value;
  uni.showLoading({ title: "正在生成模版预览...", mask: true });
  try {
    const res = await request("/api/coach/plan/assign-template", "POST", {
      club_id: currentClub.value?.id || "",
      operator_uid: user.value.id,
      template_id: templateId,
      target_user_ids: [activeStudent.value.user_id],
      apply_scope: effScope,
      target_week_index: selectedWeekIdx.value,
      weeks_count: templateWeeksCount.value,
      canova_progression: templateCanovaProgression.value,
      as_draft: currentReviewPlan.value ? currentReviewPlan.value.status === "draft" : true,
      scale_factor: 1.0,
      preview_only: true,
      base_plan: currentReviewPlan.value || undefined,
    });
    uni.hideLoading();
    const previewPlan = res?.assigned_plans?.[0]?.plan;
    if (previewPlan) {
      if (!currentReviewPlan.value) {
        studentDraftPlan.value = previewPlan;
        viewingDraft.value = true;
      } else {
        syncUpdatedPlanState(previewPlan);
      }
      applyViewingPlanFields(previewPlan);
      hasUnconfirmedPlanChanges.value = true;
      planModalTab.value = "review";
      uni.showToast({ title: "已加载模版预览（点底部确认派发后写入）", icon: "none", duration: 2500 });
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: e.message || "套用模版失败", icon: "none" });
  }
}

function goToTeamReport() {
  const clubId = currentClub.value?.id || "";
  uni.setStorageSync("team_pending_report", { club_id: clubId });
  uni.switchTab({ url: "/pages/team/team" });
}

function setFilter(status: string) {
  if (filterStatus.value === status) {
    filterStatus.value = "all";
  } else {
    filterStatus.value = status;
  }
}

function goBack() {
  uni.switchTab({
    url: "/pages/team/team",
    fail: () => {
      uni.navigateBack();
    },
  });
}

function goToPersonalTrain() {
  uni.switchTab({
    url: "/pages/coach/coach",
    fail: () => {
      uni.navigateTo({ url: "/pages/coach/coach" });
    },
  });
}

function formatMetersToKm(meters?: number): string {
  if (!meters) return "0.0";
  return (Number(meters) / 1000.0).toFixed(1);
}

function switchBenchTab(tab: "cockpit" | "feed" | "events" | "report_manage") {
  coachBenchTab.value = tab;
  const tabLabels: Record<string, string> = {
    cockpit: "队员监控与排课",
    feed: "打卡点评",
    events: "合练与约跑",
    report_manage: "周月报与管理",
  };
  trackSubView(`cockpit_${tab}`, `教练工作台切换模块：${tabLabels[tab] || tab}`);
  if (currentClub.value?.id) {
    if (tab === "feed" && clubFeed.value.length === 0) {
      loadClubCoachExtras(currentClub.value.id);
    } else if (tab === "events" && clubEvents.value.length === 0) {
      loadClubCoachExtras(currentClub.value.id);
    } else if (tab === "report_manage" && !coachReportData.value) {
      loadCoachClubReport(coachRepPeriod.value, coachRepOffset.value);
    }
  }
}

async function loadClubCoachExtras(clubId?: string) {
  const cid = clubId || currentClub.value?.id;
  const uid = user.value?.id;
  if (!cid || !uid) return;
  loadingFeed.value = true;
  try {
    const [feedRes, evtRes, tplRes] = await Promise.all([
      request(`/api/team/${cid}/feed?uid=${uid}&user_id=${uid}&limit=20`).catch(() => ({ feed: [] })),
      request(`/api/team/${cid}/events?user_id=${uid}`).catch(() => ({ events: [] })),
      request(`/api/team/${cid}/event-templates`).catch(() => ({ custom_templates: [] })),
    ]);
    clubFeed.value = feedRes?.feed || [];
    clubEvents.value = evtRes?.events || [];
    if (Array.isArray(tplRes?.custom_templates)) {
      customGroupRunTemplates.value = tplRes.custom_templates;
    }
  } catch (e) {
    console.error("loadClubCoachExtras error:", e);
  } finally {
    loadingFeed.value = false;
  }
}

function applyGroupRunTemplate(tpl: GroupRunTemplateItem) {
  selectedEvtTplId.value = tpl.id;
  newEvtTitle.value = tpl.title || "";
  newEvtTargetKm.value = String(tpl.target_km || 15);
  newEvtMeetDate.value = resolveNextWeekdayIso(tpl.default_weekday ?? 0);
  newEvtMeetTime.value = tpl.meet_time_hm || "06:30";
  if (tpl.location) {
    newEvtLocation.value = tpl.location;
    newEvtLatitude.value = tpl.latitude ?? null;
    newEvtLongitude.value = tpl.longitude ?? null;
    lastCoachGeocodedName.value = tpl.location;
  }
  newEvtLocationDetail.value = tpl.location_detail || "";
  newEvtPaceReq.value = tpl.pace_requirement || "按分组配速";
  newEvtRules.value = tpl.rules || "";
  uni.showToast({ title: `已套用「${tpl.name}」`, icon: "none" });
}

async function onNewEvtLocationBlur() {
  const kw = newEvtLocation.value.trim();
  if (!kw) return;
  if (kw === lastCoachGeocodedName.value && newEvtLatitude.value && newEvtLongitude.value) {
    return;
  }
  const matches = await searchGroupRunGeocode(kw);
  if (matches.length > 0) {
    newEvtLatitude.value = matches[0].latitude;
    newEvtLongitude.value = matches[0].longitude;
    lastCoachGeocodedName.value = kw;
  }
}

function onInlineNewEvtMapTap(e: any) {
  const lat = Number(e?.detail?.latitude);
  const lng = Number(e?.detail?.longitude);
  if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
    newEvtLatitude.value = Number(lat.toFixed(6));
    newEvtLongitude.value = Number(lng.toFixed(6));
    uni.showToast({ title: "已移动大头针位置 ✓", icon: "none" });
  }
}

async function handleChooseNewEvtLocation() {
  showCoachMapPinModal.value = true;
}

function onCoachMapPinConfirm(picked: GroupRunVenuePreset) {
  showCoachMapPinModal.value = false;
  if (picked) {
    newEvtLocation.value = picked.name;
    if (picked.address && !newEvtLocationDetail.value) {
      newEvtLocationDetail.value = picked.address;
    }
    newEvtLatitude.value = picked.latitude;
    newEvtLongitude.value = picked.longitude;
    lastCoachGeocodedName.value = picked.name;
    uni.showToast({ title: "集合点大头针已标注 ✓", icon: "none" });
  }
}

function previewNewEvtLocationOnMap() {
  openRunLocation({
    location: newEvtLocation.value || "约跑集合点",
    location_detail: newEvtLocationDetail.value || "",
    latitude: newEvtLatitude.value,
    longitude: newEvtLongitude.value,
  });
}

async function handleSaveCurrentAsEventTemplate() {
  if (!currentClub.value?.id) return;
  if (!newEvtTitle.value.trim()) {
    uni.showToast({ title: "请先填写或修改活动标题再保存模版", icon: "none" });
    return;
  }
  const shortName = newEvtTitle.value.trim().slice(0, 8);
  try {
    const res: any = await request(`/api/team/${currentClub.value.id}/event-templates`, "POST", {
      operator_uid: user.value?.id,
      name: shortName,
      title: newEvtTitle.value.trim(),
      event_type: "group_run",
      target_km: Number(newEvtTargetKm.value) || 15,
      default_weekday: new Date((newEvtMeetDate.value || resolveNextWeekdayIso(0)).replace(/-/g, "/")).getDay() || 0,
      meet_time_hm: newEvtMeetTime.value || "06:30",
      location: newEvtLocation.value.trim(),
      location_detail: newEvtLocationDetail.value.trim(),
      latitude: newEvtLatitude.value,
      longitude: newEvtLongitude.value,
      pace_requirement: newEvtPaceReq.value.trim(),
      rules: newEvtRules.value.trim(),
    });
    if (Array.isArray(res?.custom_templates)) {
      customGroupRunTemplates.value = res.custom_templates;
    }
    if (res?.template?.id) {
      selectedEvtTplId.value = res.template.id;
    }
    uni.showToast({ title: "已存为本团约跑模版 ✓", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: e.message || "保存模版失败", icon: "none" });
  }
}

async function handleDeleteCustomEventTemplate(tpl: GroupRunTemplateItem) {
  if (!currentClub.value?.id || !tpl?.id) return;
  try {
    const res: any = await request(`/api/team/${currentClub.value.id}/event-templates/${tpl.id}`, "DELETE");
    if (Array.isArray(res?.custom_templates)) {
      customGroupRunTemplates.value = res.custom_templates;
    } else {
      customGroupRunTemplates.value = customGroupRunTemplates.value.filter((t) => t.id !== tpl.id);
    }
    uni.showToast({ title: "模版已移除", icon: "none" });
  } catch (e) {
    uni.showToast({ title: "删除模版失败", icon: "none" });
  }
}

function applyQuickCoachComment(actId: string, preset: { label: string; text: string }) {
  feedCommentInputs.value[actId] = preset.text;
}

async function handleToggleFeedLike(act: any) {
  if (!user.value?.id || !act?.id) return;
  try {
    const res = await request(`/api/team/activities/${act.id}/like`, "POST", {
      user_id: user.value.id,
    });
    act.has_liked = res?.liked;
    act.likes_count = res?.likes_count ?? act.likes_count;
  } catch (e) {
    console.error("Like error:", e);
  }
}

async function handlePostCoachComment(act: any) {
  if (!user.value?.id || !act?.id) return;
  const content = (feedCommentInputs.value[act.id] || "").trim();
  if (!content || submittingFeedComment.value[act.id]) return;
  submittingFeedComment.value[act.id] = true;
  try {
    const authorName = (user.value.display_name || "认证教练") + " (教练)";
    const authorAvatar =
      user.value.avatar_url ||
      "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80";
    const res = await request(`/api/team/activities/${act.id}/comments`, "POST", {
      user_id: user.value.id,
      content,
      author_name: authorName,
      author_avatar: authorAvatar,
    });
    if (res?.comment) {
      act.comments = [...(act.comments || []), res.comment];
    }
    trackFunnelStep("cockpit_post_comment", "教练发布打卡点评", {
      activity_id: act.id,
    });
    feedCommentInputs.value[act.id] = "";
    uni.showToast({ title: "教练点评已发布 ✓", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: e.message || "点评失败", icon: "none" });
  } finally {
    submittingFeedComment.value[act.id] = false;
  }
}

async function handleCreateClubEventFromCoach() {
  if (!currentClub.value?.id || !user.value?.id || creatingEvent.value) return;
  if (!newEvtTitle.value.trim()) {
    uni.showToast({ title: "请填写活动/合练标题", icon: "none" });
    return;
  }
  creatingEvent.value = true;
  try {
    if (newEvtLocation.value.trim()) {
      await onNewEvtLocationBlur();
    }
    const meetDate = newEvtMeetDate.value || resolveNextWeekdayIso(0);
    const meetTimeHm = newEvtMeetTime.value || "06:30";
    const fullMeetTime = `${meetDate} ${meetTimeHm}`.trim();
    await request(`/api/team/${currentClub.value.id}/events`, "POST", {
      operator_uid: user.value.id,
      title: newEvtTitle.value.trim(),
      event_type: "group_run",
      start_date: meetDate,
      end_date: meetDate,
      meet_time: fullMeetTime,
      location: newEvtLocation.value.trim() || "跑团指定集合点",
      location_detail: newEvtLocationDetail.value.trim(),
      latitude: newEvtLatitude.value,
      longitude: newEvtLongitude.value,
      target_km: Number(newEvtTargetKm.value) || 20,
      pace_requirement: newEvtPaceReq.value.trim() || "按分组配速",
      rules: newEvtRules.value.trim() || "按教练分组配速执行，注意补水与安全。",
    });
    trackFunnelStep(
      "group_run_publish_success",
      `教练工作台发布约跑活动：${newEvtTitle.value.trim()}`,
      { club_id: currentClub.value.id }
    );
    uni.showToast({ title: "跑团活动已发布 ✓", icon: "success" });
    showNewEventForm.value = false;
    selectedEvtTplId.value = "";
    newEvtTitle.value = "";
    newEvtLocation.value = "";
    newEvtLocationDetail.value = "";
    newEvtLatitude.value = null;
    newEvtLongitude.value = null;
    newEvtRules.value = "";
    await loadClubCoachExtras(currentClub.value.id);
  } catch (e: any) {
    uni.showToast({ title: e.message || "发布活动失败", icon: "none" });
  } finally {
    creatingEvent.value = false;
  }
}

function goToEventDetail(ev: any) {
  if (!ev?.id || !currentClub.value?.id) return;
  uni.navigateTo({
    url: `/pages/group-run/group-run?club_id=${currentClub.value.id}&event_id=${ev.id}`,
    fail: () => {
      uni.switchTab({ url: "/pages/team/team" });
    },
  });
}

async function loadCoachClubReport(
  periodType: "week" | "month",
  offset: number,
  trailMode: "include" | "exclude_pace" | "exclude_all" = coachRepTrailMode.value
) {
  if (!currentClub.value?.id || !user.value?.id) return;
  coachRepPeriod.value = periodType;
  coachRepOffset.value = offset;
  coachRepTrailMode.value = trailMode;
  loadingCoachReport.value = true;
  try {
    let url = `/api/team/${currentClub.value.id}/reports?operator_uid=${user.value.id}&period_type=${periodType}&trail_mode=${trailMode}`;
    if (offset === -1) {
      const now = new Date();
      if (periodType === "week") {
        const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const target = new Date(d.valueOf());
        const dayNr = (d.getDay() + 6) % 7;
        target.setDate(target.getDate() - dayNr + 3);
        const firstThursday = target.valueOf();
        target.setMonth(0, 1);
        if (target.getDay() !== 4) {
          target.setMonth(0, 1 + (((4 - target.getDay()) + 7) % 7));
        }
        const weekNum = 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
        url += `&year=${d.getFullYear()}&period_index=${weekNum}`;
      } else {
        const prevMonth = now.getMonth() === 0 ? 12 : now.getMonth();
        const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
        url += `&year=${prevYear}&period_index=${prevMonth}`;
      }
    }
    const res = await request(url);
    coachReportData.value = res || null;
  } catch (e: any) {
    uni.showToast({ title: e.message || "加载战报失败", icon: "none" });
  } finally {
    loadingCoachReport.value = false;
  }
}

function copyCoachReportText() {
  if (!coachReportData.value?.forward_text) return;
  uni.setClipboardData({
    data: coachReportData.value.forward_text,
    success: () => {
      uni.showToast({ title: "已复制微信群战报 ✓", icon: "success" });
    },
  });
}

function copyClubInviteCode() {
  if (!currentClub.value?.invite_code) return;
  uni.setClipboardData({
    data: String(currentClub.value.invite_code),
    success: () => {
      uni.showToast({ title: "邀请码已复制 ✓", icon: "success" });
    },
  });
}

function copyWebAdminUrl() {
  uni.setClipboardData({
    data: "https://rgm.vanpower.net",
    success: () => {
      uni.showToast({ title: "已复制管理台网址", icon: "success" });
    },
  });
}

async function handleUpdateClubJoinMode(mode: "free" | "invite") {
  if (!currentClub.value?.id || !user.value?.id) return;
  try {
    const res = await request(`/api/team/${currentClub.value.id}/join-mode`, "POST", {
      operator_uid: user.value.id,
      join_mode: mode,
    });
    currentClub.value = {
      ...currentClub.value,
      join_mode: mode,
      ...(res?.club?.invite_code ? { invite_code: res.club.invite_code } : {}),
    };
    uni.showToast({ title: "入团门槛已更新 ✓", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: e.message || "更新失败", icon: "none" });
  }
}

function startPipelineReview() {
  if (filteredStudents.value.length === 0) return;
  openStudentPlanModal(filteredStudents.value[0]);
}

function goPrevStudentInQueue() {
  const idx = activeQueueIndex.value;
  if (idx > 0) {
    openStudentPlanModal(filteredStudents.value[idx - 1]);
  }
}

function goNextStudentInQueue() {
  const idx = activeQueueIndex.value;
  if (idx >= 0 && idx < filteredStudents.value.length - 1) {
    openStudentPlanModal(filteredStudents.value[idx + 1]);
  }
}

function applyBroadcastPreset(preset: any) {
  bcDayIndex.value = preset.day_index;
  bcWorkoutType.value = preset.workout_type;
  bcTitle.value = preset.title;
  bcDistanceKm.value = preset.distance_km;
  bcTargetPace.value = preset.target_pace;
  bcTargetHrZone.value = preset.target_hr_zone;
  bcDescription.value = preset.description;
}

async function handleBroadcastClubWorkout() {
  if (!currentClub.value?.id || !user.value?.id || broadcastingWorkout.value) return;
  uni.showModal({
    title: "确认派发跑团合练课",
    content: `确定将【${bcTitle.value} (${bcDistanceKm.value}km)】同步派发并写入全团队员当周训练计划吗？`,
    confirmText: "确认派发",
    cancelText: "取消",
    confirmColor: "#10b981",
    success: async (mRes) => {
      if (!mRes.confirm) return;
      broadcastingWorkout.value = true;
      uni.showLoading({ title: "正在派发跑团合练课...", mask: true });
      try {
        const res = await request("/api/coach/plan/club-broadcast-workout", "POST", {
          club_id: currentClub.value.id,
          operator_uid: user.value!.id,
          day_index: Math.max(0, Number(bcDayIndex.value || 1) - 1),
          day_index_base: 0,
          workout_type: bcWorkoutType.value,
          title: bcTitle.value,
          distance_km: Number(bcDistanceKm.value || 10),
          duration_minutes: Math.round(Number(bcDistanceKm.value || 10) * 6),
          target_pace: bcTargetPace.value,
          target_hr_zone: bcTargetHrZone.value,
          description: bcDescription.value,
        });
        uni.hideLoading();
        trackFunnelStep("cockpit_broadcast_workout", `教练全员派发合练课：${bcTitle.value}`, {
          club_id: currentClub.value.id,
          distance_km: Number(bcDistanceKm.value || 10),
        });
        showBroadcastModal.value = false;
        uni.showModal({
          title: "跑团合练课已派发",
          content: res?.message || "已成功将合练课写入全团队员当周计划！",
          showCancel: false,
        });
        await loadCockpitData(currentClub.value.id);
      } catch (e: any) {
        uni.hideLoading();
        uni.showToast({ title: e.message || "派发合练课失败", icon: "none" });
      } finally {
        broadcastingWorkout.value = false;
      }
    },
  });
}

async function handleBatchGenerateDrafts(onlyWithoutPlan: boolean) {
  if (!currentClub.value?.id || !user.value?.id || batchGenerating.value) return;
  uni.showModal({
    title: "确认批量生成待审草案",
    content: `确定为跑团${onlyWithoutPlan ? "尚未排课的" : "全部"}队员批量生成训练计划待审草案吗？（草案需教练逐一确认发布后才会对队员生效）`,
    confirmText: "确认生成草案",
    cancelText: "取消",
    confirmColor: "#10b981",
    success: async (mRes) => {
      if (!mRes.confirm) return;
      batchGenerating.value = true;
      uni.showLoading({ title: "智能定制排课中...", mask: true });
      try {
        const res = await request("/api/coach/plan/club-batch-generate", "POST", {
          club_id: currentClub.value.id,
          operator_uid: user.value!.id,
          weeks: 4,
          only_without_plan: onlyWithoutPlan,
        });
        uni.hideLoading();
        uni.showModal({
          title: "排课草案已生成",
          content: res?.message || "已为队员生成个性化训练计划草案，请点击学员卡片进行审核与发布！",
          showCancel: false,
        });
        await loadCockpitData(currentClub.value.id);
        if ((res?.generated_count || 0) > 0) {
          filterPlanState.value = "draft_pending";
        }
      } catch (e: any) {
        uni.hideLoading();
        uni.showToast({ title: e.message || "批量排课失败", icon: "none" });
      } finally {
        batchGenerating.value = false;
      }
    },
  });
}

function syncWeekReviewFields(weekObj: any) {
  if (!weekObj) return;
  weekSummaryOverride.value = weekObj.week_summary_override || "";
  coachWeeklyDiagnosis.value = weekObj.coach_weekly_diagnosis || "";
}

function onSelectWeekTab(weekIndex: number) {
  selectedWeekIdx.value = weekIndex;
  editingDayIdx.value = null;
  const weeks = currentReviewPlan.value?.schedule_data?.weeks || [];
  const w = weeks.find((item: any) => Number(item.week_index) === Number(weekIndex));
  if (w) syncWeekReviewFields(w);
}

function applyViewingPlanFields(planObj: any) {
  if (!planObj) return;
  editPlanTitle.value = planObj.title || "";
  editPlanOverview.value = planObj.overview_summary || "";
  editMacroRoadmap.value = planObj.schedule_data?.macro_roadmap || "";
  coachReviewNote.value =
    planObj.coach_review_note ||
    planObj.schedule_data?.coach_review?.coach_review_note ||
    "";
  const weeks = planObj.schedule_data?.weeks || [];
  const todayStr = new Date().toISOString().slice(0, 10);
  let foundWeek = 1;
  for (const w of weeks) {
    for (const d of w.days || []) {
      if (d.date === todayStr) {
        foundWeek = Number(w.week_index || 1);
        break;
      }
    }
  }
  selectedWeekIdx.value = foundWeek;
  const wObj = weeks.find((item: any) => Number(item.week_index) === Number(foundWeek)) || weeks[0];
  if (wObj) syncWeekReviewFields(wObj);
}

function switchViewingPlan(isDraft: boolean) {
  viewingDraft.value = isDraft;
  editingDayIdx.value = null;
  const target = isDraft ? studentDraftPlan.value : studentActivePlan.value;
  if (target) applyViewingPlanFields(target);
}

async function openStudentPlanModal(s: any) {
  activeStudent.value = s;
  showPlanModal.value = true;
  trackModal(
    "cockpit_student_plan",
    `打开学员排课/调课弹窗：${s?.display_name || "队员"}`,
    "open",
    { target_uid: s?.user_id }
  );
  editingDayIdx.value = null;
  showRollNextWeekPanel.value = false;
  hasUnconfirmedPlanChanges.value = false;
  planLoading.value = true;
  try {
    const res = await request(`/api/coach/plan/user/${s.user_id}`);
    const active = res?.active_plan || null;
    const draft = res?.draft_plan || null;
    studentActivePlan.value = active;
    studentDraftPlan.value = draft;
    originalPlanBackup.value = {
      active: active ? JSON.parse(JSON.stringify(active)) : null,
      draft: draft ? JSON.parse(JSON.stringify(draft)) : null,
    };
    studentGoal.value = res?.user_goal || null;
    const races = res?.upcoming_races || s.upcoming_races || [];
    studentUpcomingRaces.value = races;

    if (races.length > 0) {
      genGoalType.value = "race_prep";
      genRaceName.value = races[0].name || "";
      genTargetTime.value = races[0].target_time || s.marathon_pb || "3:30:00";
    } else if (s.goal_race) {
      genGoalType.value = "race_prep";
      genRaceName.value = s.goal_race.name || "";
      genTargetTime.value = s.goal_race.target_time || s.marathon_pb || "3:30:00";
    } else {
      genGoalType.value = "fitness_maintenance";
    }

    if (draft) {
      viewingDraft.value = true;
      planModalTab.value = "review";
      applyViewingPlanFields(draft);
    } else if (active) {
      viewingDraft.value = false;
      planModalTab.value = "review";
      applyViewingPlanFields(active);
    } else {
      planModalTab.value = "generate";
    }
  } catch (e: any) {
    uni.showToast({ title: e.message || "加载计划失败", icon: "none" });
  } finally {
    planLoading.value = false;
  }
}

function discardUnconfirmedPlanChanges() {
  studentActivePlan.value = originalPlanBackup.value.active
    ? JSON.parse(JSON.stringify(originalPlanBackup.value.active))
    : null;
  studentDraftPlan.value = originalPlanBackup.value.draft
    ? JSON.parse(JSON.stringify(originalPlanBackup.value.draft))
    : null;
  hasUnconfirmedPlanChanges.value = false;
  editingDayIdx.value = null;
  const target = viewingDraft.value ? studentDraftPlan.value : studentActivePlan.value;
  if (target) applyViewingPlanFields(target);
  uni.showToast({ title: "已放弃未确认更改，恢复原计划", icon: "none" });
}

function closePlanModal() {
  if (hasUnconfirmedPlanChanges.value) {
    uni.showModal({
      title: "放弃未确认的排课更改？",
      content: "当前排课或调课仅处于预览状态，尚未点击「确认派发/更新」，直接关闭将不会写入数据库。确认放弃并关闭吗？",
      confirmText: "放弃并关闭",
      cancelText: "继续确认",
      confirmColor: "#ef4444",
      success: (mRes) => {
        if (mRes.confirm) {
          hasUnconfirmedPlanChanges.value = false;
          showPlanModal.value = false;
          activeStudent.value = null;
          editingDayIdx.value = null;
        }
      },
    });
    return;
  }
  showPlanModal.value = false;
  activeStudent.value = null;
  editingDayIdx.value = null;
}

function selectStudentRaceForGen(r: any) {
  genRaceName.value = r.name || "";
  if (r.target_time) genTargetTime.value = r.target_time;
}

async function handleGenerateSingleDraft() {
  if (!activeStudent.value || !user.value?.id || generatingSingleDraft.value) return;
  generatingSingleDraft.value = true;
  uni.showLoading({ title: "正在推演排课预览...", mask: true });
  try {
    const res = await request("/api/coach/plan/generate", "POST", {
      uid: activeStudent.value.user_id,
      operator_uid: user.value.id,
      goal_type: genGoalType.value,
      target_race_name: genGoalType.value === "race_prep" ? genRaceName.value : "非赛期体能周期强化",
      target_time: genTargetTime.value,
      weeks: genWeeks.value,
      days_per_week: genDaysPerWeek.value,
      maintenance_focus: "aerobic_base",
      as_draft: true,
      coach_notes_prompt: genCoachPrompt.value,
      preview_only: true,
    });
    uni.hideLoading();
    if (res?.plan) {
      studentDraftPlan.value = res.plan;
      viewingDraft.value = true;
      hasUnconfirmedPlanChanges.value = true;
      applyViewingPlanFields(res.plan);
      planModalTab.value = "review";
      uni.showToast({ title: "已生成课表预览，请确认派发后生效", icon: "none", duration: 2500 });
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: e.message || "生成草案失败", icon: "none" });
  } finally {
    generatingSingleDraft.value = false;
  }
}

function syncUpdatedPlanState(updated: any) {
  if (!updated) return;
  if (updated.status === "draft") {
    studentDraftPlan.value = updated;
  } else {
    studentActivePlan.value = updated;
  }
  const weeks = updated.schedule_data?.weeks || [];
  const wObj = weeks.find((item: any) => Number(item.week_index) === Number(selectedWeekIdx.value));
  if (wObj) syncWeekReviewFields(wObj);
}

async function handleSaveCoachWeekSummary() {
  const planObj = currentReviewPlan.value;
  if (!planObj || !user.value?.id || savingWeekSummary.value) return;
  savingWeekSummary.value = true;
  try {
    const res = await request(`/api/coach/plan/${planObj.id}/week-summary`, "POST", {
      operator_uid: user.value.id,
      week_index: selectedWeekIdx.value,
      week_summary_override: weekSummaryOverride.value,
      coach_weekly_diagnosis: coachWeeklyDiagnosis.value,
      macro_roadmap: editMacroRoadmap.value,
    });
    if (res?.plan) {
      syncUpdatedPlanState(res.plan);
      uni.showToast({ title: "周小结与复盘已保存 ✓", icon: "success" });
      await loadCockpitData(currentClub.value?.id);
    }
  } catch (e: any) {
    uni.showToast({ title: e.message || "保存周复盘失败", icon: "none" });
  } finally {
    savingWeekSummary.value = false;
  }
}

async function handleRollNextWeek() {
  const planObj = currentReviewPlan.value;
  if (!planObj || !user.value?.id || rollingNextWeek.value) return;
  rollingNextWeek.value = true;
  uni.showLoading({ title: "正在推演下周课表预览...", mask: true });
  try {
    const res = await request(`/api/coach/plan/${planObj.id}/roll-next-week`, "POST", {
      operator_uid: user.value.id,
      base_week_index: selectedWeekIdx.value,
      volume_scale: rollVolumeScale.value,
      next_week_theme: rollWeekTheme.value || undefined,
      coach_focus_note: rollCoachNote.value || coachWeeklyDiagnosis.value || undefined,
      preview_only: true,
      schedule_data: planObj.schedule_data,
      plan_payload: planObj,
    });
    uni.hideLoading();
    if (res?.plan) {
      syncUpdatedPlanState(res.plan);
      hasUnconfirmedPlanChanges.value = true;
      const nextIdx = Number(res.rolled_week?.week_index || Number(selectedWeekIdx.value) + 1);
      onSelectWeekTab(nextIdx);
      showRollNextWeekPanel.value = false;
      uni.showToast({ title: `已生成 W${nextIdx} 预览（点底部确认派发后写入）`, icon: "none", duration: 2500 });
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: e.message || "滚动生成失败", icon: "none" });
  } finally {
    rollingNextWeek.value = false;
  }
}

async function handleWeekBatchAdjust(action: "scale_volume" | "downgrade_intensity", scaleFactor: number) {
  const planObj = currentReviewPlan.value;
  if (!planObj || !user.value?.id || savingPlan.value) return;
  savingPlan.value = true;
  try {
    const res = await request(`/api/coach/plan/${planObj.id}/week-adjust`, "POST", {
      operator_uid: user.value.id,
      week_index: selectedWeekIdx.value,
      action,
      scale_factor: scaleFactor,
      preview_only: true,
      schedule_data: planObj.schedule_data,
      plan_payload: planObj,
    });
    if (res?.plan) {
      syncUpdatedPlanState(res.plan);
      hasUnconfirmedPlanChanges.value = true;
      uni.showToast({ title: "已微调预览（点底部确认更新后写入）", icon: "none" });
    }
  } catch (e: any) {
    uni.showToast({ title: e.message || "调课失败", icon: "none" });
  } finally {
    savingPlan.value = false;
  }
}

async function handleQuickStepDay(day: any, deltaKm: number) {
  const planObj = currentReviewPlan.value;
  if (!planObj || !user.value?.id || savingPlan.value) return;
  const newKm = Math.max(2, Math.round((Number(day.distance_km || 0) + deltaKm) * 2) / 2);
  const daysArr = currentSelectedWeek.value?.days || [];
  const dIdx0 = Math.max(0, daysArr.indexOf(day) >= 0 ? daysArr.indexOf(day) : Number(day.day_index || 1) - 1);
  savingPlan.value = true;
  try {
    const res = await request(`/api/coach/plan/${planObj.id}/workout`, "PUT", {
      operator_uid: user.value.id,
      week_index: selectedWeekIdx.value,
      day_index: dIdx0,
      date: day.date,
      workout_type: day.workout_type,
      title: day.title,
      distance_km: newKm,
      duration_minutes: Math.round(newKm * 6),
      target_pace: day.target_pace || "",
      target_hr_zone: day.target_hr_zone || "",
      description: day.description || "",
      is_coach_edit: true,
      preview_only: true,
      schedule_data: planObj.schedule_data,
      plan_payload: planObj,
    });
    if (res?.plan) {
      syncUpdatedPlanState(res.plan);
      hasUnconfirmedPlanChanges.value = true;
    }
  } catch (e: any) {
    uni.showToast({ title: e.message || "调整里程失败", icon: "none" });
  } finally {
    savingPlan.value = false;
  }
}

async function handleQuickConvertRest(day: any) {
  const planObj = currentReviewPlan.value;
  if (!planObj || !user.value?.id || savingPlan.value) return;
  const daysArr = currentSelectedWeek.value?.days || [];
  const dIdx0 = Math.max(0, daysArr.indexOf(day) >= 0 ? daysArr.indexOf(day) : Number(day.day_index || 1) - 1);
  savingPlan.value = true;
  try {
    const res = await request(`/api/coach/plan/${planObj.id}/workout`, "PUT", {
      operator_uid: user.value.id,
      week_index: selectedWeekIdx.value,
      day_index: dIdx0,
      date: day.date,
      workout_type: "rest",
      title: "休息与深度恢复",
      distance_km: 0,
      duration_minutes: 0,
      target_pace: "-",
      target_hr_zone: "Zone 1",
      description: "教练调整为休息日，保证充足睡眠与泡沫轴放松。",
      is_coach_edit: true,
      preview_only: true,
      schedule_data: planObj.schedule_data,
      plan_payload: planObj,
    });
    if (res?.plan) {
      syncUpdatedPlanState(res.plan);
      hasUnconfirmedPlanChanges.value = true;
      uni.showToast({ title: "已设为休息预览（点底部确认更新后写入）", icon: "none" });
    }
  } catch (e: any) {
    uni.showToast({ title: e.message || "调整失败", icon: "none" });
  } finally {
    savingPlan.value = false;
  }
}

function toggleEditDay(day: any) {
  if (editingDayIdx.value === day.day_index) {
    editingDayIdx.value = null;
    return;
  }
  editingDayIdx.value = day.day_index;
  editDayForm.value = {
    workout_type: day.workout_type || "easy_run",
    title: day.title || "",
    distance_km: Number(day.distance_km || 0),
    duration_minutes: Number(day.duration_minutes || 0),
    target_pace: day.target_pace || "",
    target_hr_zone: day.target_hr_zone || "",
    description: day.description || "",
    actual_execution_text: day.actual_execution_text || "",
    rpe: day.rpe ? String(day.rpe) : "",
    athlete_notes: day.athlete_notes || "",
    hrv: day.hrv ? String(day.hrv) : "",
    resting_hr: day.resting_hr ? String(day.resting_hr) : "",
    recovery_pct: day.recovery_pct ? String(day.recovery_pct) : "",
    swap_with_day_index: 0,
  };
}

async function handleSaveDayEdit(dayIndex: number) {
  const planObj = currentReviewPlan.value;
  if (!planObj || !user.value?.id || savingPlan.value) return;
  const isRest = editDayForm.value.workout_type === "rest";
  const distKm = isRest ? 0 : Number(editDayForm.value.distance_km || 0);
  const daysArr = currentSelectedWeek.value?.days || [];
  const matchedIdx = daysArr.findIndex((d: any) => d.day_index === dayIndex);
  const dIdx0 = matchedIdx >= 0 ? matchedIdx : Math.max(0, Number(dayIndex || 1) - 1);
  const targetDayObj = daysArr[dIdx0];
  savingPlan.value = true;
  try {
    const res = await request(`/api/coach/plan/${planObj.id}/workout`, "PUT", {
      operator_uid: user.value.id,
      week_index: selectedWeekIdx.value,
      day_index: dIdx0,
      date: targetDayObj?.date,
      workout_type: editDayForm.value.workout_type,
      title: editDayForm.value.title || (isRest ? "休息日" : "训练课"),
      distance_km: distKm,
      duration_minutes: isRest ? 0 : Math.round(distKm * 6),
      target_pace: isRest ? "-" : editDayForm.value.target_pace,
      target_hr_zone: isRest ? "Zone 1" : editDayForm.value.target_hr_zone,
      description: editDayForm.value.description,
      actual_execution_text: editDayForm.value.actual_execution_text || undefined,
      rpe: editDayForm.value.rpe !== "" ? Number(editDayForm.value.rpe) : undefined,
      athlete_notes: editDayForm.value.athlete_notes || undefined,
      hrv: editDayForm.value.hrv !== "" ? Number(editDayForm.value.hrv) : undefined,
      resting_hr: editDayForm.value.resting_hr !== "" ? Number(editDayForm.value.resting_hr) : undefined,
      recovery_pct: editDayForm.value.recovery_pct !== "" ? Number(editDayForm.value.recovery_pct) : undefined,
      swap_with_day_index: editDayForm.value.swap_with_day_index || undefined,
      is_coach_edit: true,
      preview_only: true,
      schedule_data: planObj.schedule_data,
      plan_payload: planObj,
    });
    if (res?.plan) {
      syncUpdatedPlanState(res.plan);
      hasUnconfirmedPlanChanges.value = true;
      editingDayIdx.value = null;
      uni.showToast({ title: "单日微调已加入预览（点底部确认更新后写入）", icon: "none" });
    }
  } catch (e: any) {
    uni.showToast({ title: e.message || "保存失败", icon: "none" });
  } finally {
    savingPlan.value = false;
  }
}

async function handlePublishPlan(jumpNext = false) {
  const planObj = currentReviewPlan.value;
  if (!planObj || !user.value?.id || publishingPlan.value) return;
  const nextStudent =
    jumpNext && activeQueueIndex.value >= 0 && activeQueueIndex.value < filteredStudents.value.length - 1
      ? filteredStudents.value[activeQueueIndex.value + 1]
      : null;

  const isDraft = planObj.status === "draft";
  const stuName = activeStudent.value?.display_name || "该队员";

  uni.showModal({
    title: isDraft ? "确认派发训练计划" : "确认更新训练计划",
    content: `确定将《${editPlanTitle.value || planObj.title}》正式${isDraft ? "派发" : "更新"}给队员【${stuName}】并写入数据库生效吗？`,
    confirmText: isDraft ? "确认派发" : "确认更新",
    cancelText: "再检查一下",
    confirmColor: "#10b981",
    success: async (mRes) => {
      if (!mRes.confirm) return;
      publishingPlan.value = true;
      uni.showLoading({ title: "正在确认写入并派发...", mask: true });
      try {
        const res = await request(`/api/coach/plan/${planObj.id}/publish`, "POST", {
          operator_uid: user.value!.id,
          coach_review_note: coachReviewNote.value,
          title: editPlanTitle.value,
          overview_summary: editPlanOverview.value,
          schedule_data: planObj.schedule_data,
          plan_payload: planObj,
        });
        if (res?.plan?.id && (editMacroRoadmap.value || coachWeeklyDiagnosis.value || weekSummaryOverride.value)) {
          const sumRes = await request(`/api/coach/plan/${res.plan.id}/week-summary`, "POST", {
            operator_uid: user.value!.id,
            week_index: selectedWeekIdx.value,
            week_summary_override: weekSummaryOverride.value,
            coach_weekly_diagnosis: coachWeeklyDiagnosis.value,
            macro_roadmap: editMacroRoadmap.value,
          });
          if (sumRes?.plan) {
            res.plan = sumRes.plan;
          }
        }
        uni.hideLoading();
        if (res?.plan) {
          studentActivePlan.value = res.plan;
          studentDraftPlan.value = null;
          viewingDraft.value = false;
          hasUnconfirmedPlanChanges.value = false;
          originalPlanBackup.value = {
            active: JSON.parse(JSON.stringify(res.plan)),
            draft: null,
          };
          uni.showToast({
            title: nextStudent ? `已确认派发，切至 ${nextStudent.display_name}` : "已确认派发/更新给队员 ✓",
            icon: "success",
          });
          await loadCockpitData(currentClub.value?.id);
          if (nextStudent) {
            await openStudentPlanModal(nextStudent);
          }
        }
      } catch (e: any) {
        uni.hideLoading();
        uni.showToast({ title: e.message || "派发失败", icon: "none" });
      } finally {
        publishingPlan.value = false;
      }
    },
  });
}

async function loadCockpitData(preferredClubId?: string) {
  loading.value = true;
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) {
    loading.value = false;
    return;
  }
  const uid = user.value.id;

  try {
    const clubRes = await request(`/api/team/my-clubs/${uid}`);
    const clubs = clubRes?.clubs || [];
    userClubs.value = clubs;

    if (clubs.length > 0) {
      let targetClub: any = null;
      if (preferredClubId) {
        targetClub = clubs.find((c: any) => c.id === preferredClubId);
      }
      if (!targetClub) {
        targetClub = resolveActiveClub(clubs);
      } else {
        setActiveClubId(targetClub.id);
      }

      // If current club is not one where user is coach/owner, auto-prioritize a coached club!
      if (
        targetClub &&
        targetClub.role !== "owner" &&
        targetClub.role !== "coach" &&
        targetClub.owner_id !== uid
      ) {
        const firstCoached = clubs.find(
          (c: any) => c.role === "owner" || c.role === "coach" || c.owner_id === uid
        );
        if (firstCoached) {
          targetClub = firstCoached;
          setActiveClubId(firstCoached.id);
        }
      }

      currentClub.value = targetClub;
      userRole.value = targetClub.role || "member";
      const clubId = targetClub.id;

      const res = await request(`/api/team/${clubId}/coach-cockpit?coach_uid=${uid}&sort_order=${sortBy.value}`);
      summary.value = res?.summary || null;
      students.value = res?.students || [];
      loadClubCoachExtras(clubId);
      if (coachBenchTab.value === "report_manage") {
        loadCoachClubReport(coachRepPeriod.value, coachRepOffset.value);
      }
      try {
        const tplRes = await request(`/api/coach/plan/templates?club_id=${clubId}&operator_uid=${uid}`);
        if (tplRes?.templates) {
          coachTemplates.value = tplRes.templates;
        }
      } catch (e) {
        // ignore template preload error
      }
    } else {
      setActiveClubId("");
      currentClub.value = null;
      userRole.value = "member";
      summary.value = null;
      students.value = [];
    }
  } catch (err) {
    console.error("Load cockpit error:", err);
  } finally {
    loading.value = false;
  }
}

function handleSwitchClub(club: any) {
  if (!club || !club.id) return;
  setActiveClubId(club.id);
  showSwitchModal.value = false;
  uni.showToast({
    title: `已切换至【${club.name}】罗盘`,
    icon: "success",
  });
  loadCockpitData(club.id);
}

async function handleAssignRole(targetUid: string, role: string) {
  if (!currentClub.value) return;
  const uid = user.value?.id;
  if (!uid) return;
  try {
    await request(`/api/team/${currentClub.value.id}/role`, "POST", {
      operator_uid: uid,
      target_uid: targetUid,
      role: role,
    });
    uni.showToast({
      title: `已成功设为【${role === "coach" ? "认证教练" : "团员"}】`,
      icon: "success",
    });
    await loadCockpitData();
  } catch (e: any) {
    uni.showToast({ title: e.message || "设置失败", icon: "none" });
  }
}

onShow(() => {
  applySystemTheme(currentTheme.value);
  syncTabBarIndex(3);
  loadCockpitData();
});

onPullDownRefresh(async () => {
  try {
    await loadCockpitData();
    uni.showToast({ title: "罗盘数据已刷新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新", icon: "none" });
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
.cockpit-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  padding: 24rpx 28rpx calc(130rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(130rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── Centralized Coach Workbench Sub-Navigation & Modules ── */
.coach-clubs-strip {
  width: 100%;
  white-space: nowrap;
  margin-bottom: 18rpx;
}

.coach-clubs-inner {
  display: inline-flex;
  align-items: center;
  gap: 12rpx;
  padding: 4rpx 2rpx;
}

.ccs-label {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text-3, #8e8e93);
}

.ccs-pill {
  padding: 10rpx 22rpx;
  border-radius: 999rpx;
  font-size: 22rpx;
  font-weight: 700;
  background: var(--rgm-card, #18181c);
  color: var(--rgm-text-2, #a1a1aa);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
}

.ccs-pill.active {
  background: linear-gradient(135deg, #fc4c02, #ea580c);
  color: #ffffff;
  font-weight: 900;
  border-color: #fc4c02;
}

.coach-workbench-tabs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
  margin-bottom: 24rpx;
  background: var(--rgm-card, #141418);
  padding: 10rpx;
  border-radius: 24rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.cwt-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 14rpx 6rpx;
  border-radius: 18rpx;
  transition: all 0.15s ease;
}

.cwt-tab.active {
  background: linear-gradient(135deg, rgba(252, 76, 2, 0.22), rgba(191, 90, 242, 0.22));
  border: 1rpx solid rgba(252, 76, 2, 0.45);
}

.cwt-icon {
  font-size: 28rpx;
  margin-bottom: 4rpx;
}

.cwt-label {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #a1a1aa);
}

.cwt-tab.active .cwt-label {
  color: var(--rgm-text, #ffffff);
  font-weight: 900;
}

.cwb-module-box {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.cwb-sec-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
}

.cwb-sec-title {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.cwb-sec-sub {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
  display: block;
}

.cwb-mini-btn {
  padding: 0 22rpx;
  height: 54rpx;
  line-height: 54rpx;
  font-size: 22rpx;
  font-weight: 700;
  border-radius: 14rpx;
  background: var(--rgm-card-3, #242429);
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  margin: 0;
}

.cwb-feed-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.cwb-feed-card {
  background: var(--rgm-card, #151519);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 26rpx;
  padding: 24rpx;
}

.cwb-fc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
}

.cwb-fc-user {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.cwb-fc-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  border: 1rpx solid rgba(252, 76, 2, 0.35);
}

.cwb-fc-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.cwb-fc-name {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.cwb-fc-time {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.cwb-fc-actname {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.cwb-fc-dist {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.cwb-fc-km {
  font-size: 36rpx;
  font-weight: 900;
  color: #fc4c02;
}

.cwb-fc-unit {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.cwb-fc-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 16rpx;
}

.cwb-fcm-pill {
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  font-size: 20rpx;
  font-weight: 600;
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.04));
  color: var(--rgm-text-2, #d4d4d8);
}

.cwb-fc-canova {
  margin-top: 14rpx;
  padding: 16rpx;
  border-radius: 16rpx;
  background: rgba(191, 90, 242, 0.1);
  border: 1rpx solid rgba(191, 90, 242, 0.28);
}

.cwb-fcc-label {
  font-size: 21rpx;
  font-weight: 800;
  color: #c084fc;
  display: block;
  margin-bottom: 4rpx;
}

.cwb-fcc-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #e4e4e7);
  line-height: 1.5;
}

.cwb-fc-comments {
  margin-top: 14rpx;
  padding: 12rpx 16rpx;
  border-radius: 14rpx;
  background: var(--rgm-card-2, rgba(0, 0, 0, 0.25));
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.cwb-fcc-item {
  font-size: 22rpx;
  line-height: 1.4;
}

.cwb-fcc-author {
  font-weight: 800;
  color: #fbbf24;
}

.cwb-fcc-content {
  color: var(--rgm-text, #f4f4f5);
}

.cwb-preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 14rpx;
}

.cwb-preset-chip {
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
  font-weight: 700;
  background: rgba(245, 158, 11, 0.14);
  color: #fbbf24;
  border: 1rpx solid rgba(245, 158, 11, 0.32);
}

.cwb-comment-bar {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 14rpx;
}

.cwb-like-btn {
  padding: 0 18rpx;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 14rpx;
  font-size: 22rpx;
  font-weight: 700;
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.05));
  color: var(--rgm-text-2, #a1a1aa);
}

.cwb-like-btn.liked {
  background: rgba(244, 63, 94, 0.16);
  color: #fb7185;
}

.cwb-comment-input {
  flex: 1;
  height: 64rpx;
  padding: 0 18rpx;
  border-radius: 14rpx;
  font-size: 22rpx;
  background: var(--rgm-card-2, #0e0e12);
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
}

.cwb-send-btn {
  height: 64rpx;
  line-height: 64rpx;
  padding: 0 24rpx;
  border-radius: 14rpx;
  font-size: 22rpx;
  font-weight: 800;
  background: #fc4c02;
  color: #ffffff;
  margin: 0;
}

.cwb-rep-hero {
  padding: 20rpx;
  border-radius: 18rpx;
  background: rgba(252, 76, 2, 0.1);
  border: 1rpx solid rgba(252, 76, 2, 0.3);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12rpx;
}

.cwb-rep-period {
  font-size: 22rpx;
  font-weight: 700;
  color: #fbbf24;
  display: block;
}

.cwb-rep-km {
  font-size: 44rpx;
  font-weight: 900;
  color: #fc4c02;
}

.cwb-rep-stats {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.cwb-rep-stat {
  font-size: 21rpx;
  color: var(--rgm-text-2, #d4d4d8);
}

.cwb-invite-pill {
  padding: 10rpx 18rpx;
  border-radius: 14rpx;
  background: rgba(245, 158, 11, 0.15);
  border: 1rpx solid rgba(245, 158, 11, 0.35);
  font-size: 22rpx;
  font-weight: 800;
  color: #fbbf24;
}

.cwb-member-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
}

.cwb-member-actions {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.cwb-role-tag {
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
  font-size: 19rpx;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.08);
  color: var(--rgm-text-2, #a1a1aa);
}

.cwb-role-tag.owner {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.cwb-role-tag.coach {
  background: rgba(191, 90, 242, 0.2);
  color: #c084fc;
}

.theme-volt .cwb-preset-chip,
.theme-volt .cwb-invite-pill {
  background: #FFF5EE;
  color: #C23800;
  border-color: rgba(252, 76, 2, 0.32);
}

.theme-volt .cwb-fcc-label {
  color: #0F172A;
}

.theme-volt .cwb-fcc-author {
  color: #C23800;
}

.unauthorized-card {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid rgba(255, 69, 58, 0.2);
  border-radius: 32rpx;
  padding: 60rpx 40rpx;
  text-align: center;
  margin-top: 100rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.lock-icon {
  font-size: 64rpx;
  margin-bottom: 20rpx;
  display: block;
}

.unauth-title {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-red, #ff453a);
  display: block;
  margin-bottom: 16rpx;
}

.unauth-desc {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.5;
  margin-bottom: 30rpx;
  display: block;
}

.back-btn {
  background-color: var(--rgm-card-3, #242429);
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 18rpx;
  height: 76rpx;
  line-height: 76rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.top-club-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--rgm-card, linear-gradient(135deg, #1c1c20 0%, #131316 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(191, 90, 242, 0.3));
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.title-with-arrow {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.switch-arrow {
  font-size: 24rpx;
  color: var(--rgm-brand-text, #bf5af2);
}

.top-right-group {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.switch-link-pill {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #bf5af2);
  font-weight: bold;
  background: var(--rgm-brand-tint, rgba(191, 90, 242, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(191, 90, 242, 0.3));
  padding: 6rpx 14rpx;
  border-radius: 12rpx;
}

.club-title {
  font-size: 30rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
}

/* Modal styles for cockpit.vue */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: flex-end;
  z-index: 999;
  backdrop-filter: blur(4px);
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.modal-content {
  width: 100%;
  background-color: var(--rgm-card, #161619);
  border-radius: 36rpx 36rpx 0 0;
  padding: 36rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.title-with-pill {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.modal-title {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.count-pill {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #bf5af2);
  background: var(--rgm-brand-tint, rgba(191, 90, 242, 0.15));
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
  font-weight: bold;
}

.close-btn {
  font-size: 36rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 10rpx;
}

.modal-scroll {
  max-height: 60vh;
  overflow-y: auto;
}

.modal-clubs-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.modal-club-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 20rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
}

.modal-club-card.is-current {
  border-color: var(--rgm-brand-line, rgba(191, 90, 242, 0.4));
  background: var(--rgm-brand-tint, rgba(191, 90, 242, 0.06));
}

.mcc-logo {
  width: 72rpx;
  height: 72rpx;
  border-radius: 16rpx;
  flex-shrink: 0;
}

.mcc-info {
  flex: 1;
  min-width: 0;
}

.mcc-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6rpx;
}

.mcc-name {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcc-city {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.mcc-meta {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.mcc-role-tag {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.mcc-role-tag.role-owner {
  background: rgba(255, 159, 10, 0.2);
  color: var(--rgm-amber, #ff9f0a);
}

.mcc-role-tag.role-coach {
  background: rgba(10, 132, 255, 0.2);
  color: var(--rgm-blue, #0a84ff);
}

.mcc-role-tag.role-member {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-2, #a1a1aa);
}

.mcc-action {
  flex-shrink: 0;
  margin-left: 12rpx;
}

.mcc-current-tag {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #bf5af2);
  font-weight: bold;
  padding: 6rpx 16rpx;
  background: var(--rgm-brand-tint, rgba(191, 90, 242, 0.15));
  border-radius: 12rpx;
}

.mcc-switch-btn {
  background: var(--rgm-card-3, #27272a);
  color: var(--rgm-text, #ffffff);
  font-size: 22rpx;
  font-weight: 500;
  padding: 0 24rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  margin: 0;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}


.role-badge {
  font-size: 20rpx;
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

/* 4 Status Grid */
.status-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.status-card {
  background-color: var(--rgm-card, #151518);
  border-radius: 24rpx;
  padding: 20rpx;
  border: 2rpx solid transparent;
  transition: all 0.2s;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.status-card.active {
  background-color: var(--rgm-card-2, #1f1f24);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.status-card.green { border-color: rgba(48, 209, 88, 0.3); }
.status-card.green.active { border-color: #30d158; box-shadow: 0 0 16rpx rgba(48, 209, 88, 0.3); }

.status-card.blue { border-color: rgba(10, 132, 255, 0.3); }
.status-card.blue.active { border-color: #0a84ff; box-shadow: 0 0 16rpx rgba(10, 132, 255, 0.3); }

.status-card.yellow { border-color: rgba(255, 214, 10, 0.3); }
.status-card.yellow.active { border-color: #ffd60a; box-shadow: 0 0 16rpx rgba(255, 214, 10, 0.3); }

.status-card.red { border-color: rgba(255, 69, 58, 0.3); }
.status-card.red.active { border-color: #ff453a; box-shadow: 0 0 16rpx rgba(255, 69, 58, 0.3); }

.status-top {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.status-dot {
  font-size: 20rpx;
}

.status-name {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.status-count {
  font-size: 36rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  margin-top: 6rpx;
  display: block;
}

.status-count .unit {
  font-size: 20rpx;
  font-weight: normal;
  color: var(--rgm-text-3, #8e8e93);
}


/* Search & Filter Bar */
.student-search-input {
  flex: 1;
  min-width: 0;
  background-color: var(--rgm-card, rgba(0, 0, 0, 0.28));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 14rpx;
  height: 64rpx;
  padding: 0 20rpx;
  font-size: 22rpx;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 0;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.cph-search-sort-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  padding-top: 4rpx;
}

.sort-chip-group {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex-shrink: 0;
}

.sort-chip {
  background-color: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  color: var(--rgm-text-2, #a1a1aa);
  font-size: 20rpx;
  padding: 10rpx 14rpx;
  border-radius: 12rpx;
  font-weight: 700;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.sort-chip.active {
  background: var(--rgm-brand-tint, rgba(191, 90, 242, 0.22));
  color: var(--rgm-brand-text, #d8b4fe);
  border-color: var(--rgm-brand-line, rgba(191, 90, 242, 0.5));
}

/* Student Cards */
.students-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.student-card {
  background-color: var(--rgm-card, #151518);
  border-radius: 24rpx;
  padding: 24rpx;
  border-left: 8rpx solid transparent;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.student-card.border-peak { border-left-color: #30d158; }
.student-card.border-optimal { border-left-color: #0a84ff; }
.student-card.border-tired { border-left-color: #ffd60a; }
.student-card.border-danger { border-left-color: #ff453a; }

.student-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.student-profile {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  flex: 1;
  min-width: 0;
}

.student-avatar {
  width: 76rpx;
  height: 76rpx;
  border-radius: 38rpx;
  flex-shrink: 0;
  margin-top: 4rpx;
}

.student-name-box {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8rpx;
  row-gap: 8rpx;
}

.student-name {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
  flex-shrink: 0;
}

.mini-tag {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  font-weight: bold;
  white-space: nowrap;
  flex-shrink: 0;
}

.mini-tag.owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: var(--rgm-amber, #ff9f0a);
}

.mini-tag.coach {
  background-color: var(--rgm-brand-tint, rgba(191, 90, 242, 0.2));
  color: var(--rgm-brand-text, #bf5af2);
}

.student-month-km {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
}

.student-month-km .highlight {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.status-badge {
  font-size: 20rpx;
  font-weight: bold;
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  white-space: nowrap;
  flex-shrink: 0;
}

.badge-peak { background: rgba(48, 209, 88, 0.2); color: var(--rgm-green, #30d158); }
.badge-optimal { background: rgba(10, 132, 255, 0.2); color: var(--rgm-blue, #0a84ff); }
.badge-tired { background: rgba(255, 214, 10, 0.2); color: var(--rgm-amber, #ffd60a); }
.badge-danger { background: rgba(255, 69, 58, 0.2); color: var(--rgm-red, #ff453a); }

/* 6-Grid Metrics */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  background-color: var(--rgm-card-2, #1c1c20);
  border-radius: 18rpx;
  padding: 16rpx;
  margin-bottom: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.metric-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.m-label {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.m-val {
  font-size: 26rpx;
  font-weight: 900;
  margin-top: 4rpx;
  font-family: monospace;
}

.m-unit {
  font-size: 16rpx;
  font-weight: normal;
  color: var(--rgm-text-3, #8e8e93);
}

.text-blue { color: var(--rgm-blue, #0a84ff); }
.text-purple { color: var(--rgm-brand-text, #bf5af2); }
.text-green { color: var(--rgm-green, #30d158); }
.text-yellow { color: var(--rgm-amber, #ffd60a); }
.text-rose { color: var(--rgm-red, #ff375f); }
.text-cyan { color: var(--rgm-blue, #64d2ff); }
.text-emerald { color: var(--rgm-green, #30d158); }

.advice-box {
  display: flex;
  gap: 12rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border-radius: 14rpx;
  padding: 14rpx 16rpx;
}

.advice-icon {
  font-size: 22rpx;
}

.advice-text {
  font-size: 20rpx;
  color: var(--rgm-text-2, #d1d1d6);
  line-height: 1.4;
  flex: 1;
}

.card-role-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12rpx;
  margin-top: 16rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
}

.role-bar-tip {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.role-mini-btn {
  font-size: 20rpx;
  font-weight: bold;
  height: 48rpx;
  line-height: 48rpx;
  border-radius: 12rpx;
  padding: 0 16rpx;
  border: none;
}

.role-mini-btn.coach {
  background: var(--rgm-brand-tint, rgba(191, 90, 242, 0.25));
  color: var(--rgm-brand-text, #bf5af2);
}

.role-mini-btn.member {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-3, #8e8e93);
}

/* ── Coach Plan Hub Card ── */
.coach-plan-hub-card {
  background: linear-gradient(135deg, rgba(252, 76, 2, 0.14) 0%, rgba(24, 22, 32, 0.96) 100%);
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  border-radius: 26rpx;
  padding: 22rpx;
  margin-bottom: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.cph-badge-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cph-pill {
  font-size: 20rpx;
  font-weight: 800;
  color: #fc4c02;
  background: rgba(252, 76, 2, 0.18);
  border: 1rpx solid rgba(252, 76, 2, 0.4);
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
}

.cph-compliance {
  font-size: 20rpx;
  font-weight: 800;
  color: #30d158;
  background: rgba(48, 209, 88, 0.14);
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
}

.cph-actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12rpx;
}

.cph-batch-btn {
  width: 100%;
  margin: 0;
  box-sizing: border-box;
  height: 68rpx;
  line-height: 68rpx;
  border-radius: 16rpx;
  font-size: 22rpx;
  font-weight: 800;
  padding: 0 14rpx;
  border: none;
  text-align: center;
}

.cph-batch-btn::after {
  border: none;
}

.cph-batch-btn.primary {
  background: linear-gradient(90deg, #fc4c02 0%, #ff6b2b 100%);
  color: #ffffff;
}

.cph-batch-btn.secondary {
  background: rgba(255, 255, 255, 0.08);
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
}

.cph-filter-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.cph-filter-chip {
  flex: 1;
  text-align: center;
  white-space: nowrap;
  font-size: 20rpx;
  font-weight: 700;
  padding: 10rpx 6rpx;
  border-radius: 12rpx;
  background: rgba(255, 255, 255, 0.06);
  color: var(--rgm-text-2, #a1a1aa);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.cph-filter-chip.active {
  background: #fc4c02;
  color: #ffffff;
  border-color: #fc4c02;
}

.cph-filter-chip.draft.active {
  background: #f59e0b;
  color: #111113;
  border-color: #f59e0b;
}

.cph-filter-chip.pub.active {
  background: #10b981;
  color: #111113;
  border-color: #10b981;
}

/* ── Student Card Plan & Execution Strip ── */
.student-card.card-has-draft {
  border-top: 2rpx solid rgba(245, 158, 11, 0.45);
  border-right: 2rpx solid rgba(245, 158, 11, 0.45);
  border-bottom: 2rpx solid rgba(245, 158, 11, 0.45);
}

.mini-tag.draft-tag {
  background: rgba(245, 158, 11, 0.18);
  color: var(--rgm-amber, #fbbf24);
  border: 1rpx solid rgba(245, 158, 11, 0.4);
}

.mini-tag.pub-tag {
  background: rgba(16, 185, 129, 0.16);
  color: var(--rgm-green, #34d399);
}

.mini-tag.self-tag {
  background: rgba(59, 130, 246, 0.16);
  color: var(--rgm-blue, #60a5fa);
}

.student-sub-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 4rpx;
}

.student-race-pill {
  font-size: 18rpx;
  font-weight: 700;
  color: #fc4c02;
  background: rgba(252, 76, 2, 0.15);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.student-plan-exec-box {
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.03));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 18rpx;
  padding: 16rpx;
  margin-bottom: 16rpx;
}

.spe-top-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12rpx;
  margin-bottom: 12rpx;
}

.spe-title-col {
  flex: 1;
  min-width: 0;
}

.spe-plan-title {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.spe-week-sub {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 2rpx;
  display: block;
}

.spe-stats-col {
  text-align: right;
  flex-shrink: 0;
}

.spe-km-text {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-family: monospace;
  display: block;
}

.spe-actual {
  color: #30d158;
  font-weight: 800;
}

.spe-rate-pill {
  font-size: 18rpx;
  font-weight: 700;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  margin-top: 4rpx;
  display: inline-block;
}

.spe-rate-pill.good {
  background: rgba(48, 209, 88, 0.18);
  color: #30d158;
}

.spe-rate-pill.normal {
  background: rgba(255, 255, 255, 0.08);
  color: var(--rgm-text-2, #d1d1d6);
}

.spe-days-strip {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 8rpx;
}

.spe-day-cell {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 12rpx;
  padding: 8rpx 4rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rpx;
}

.spe-day-cell.day-completed {
  background: rgba(16, 185, 129, 0.14);
  border-color: rgba(16, 185, 129, 0.35);
}

.spe-day-cell.day-missed {
  background: rgba(244, 63, 94, 0.14);
  border-color: rgba(244, 63, 94, 0.35);
}

.spe-day-cell.day-rest {
  opacity: 0.6;
}

.spe-day-name {
  font-size: 16rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.spe-day-icon {
  font-size: 18rpx;
}

.spe-day-km {
  font-size: 16rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  font-family: monospace;
}

.student-no-plan-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.02);
  border: 1rpx dashed rgba(255, 255, 255, 0.14);
  border-radius: 16rpx;
  padding: 14rpx 18rpx;
  margin-bottom: 16rpx;
}

.snp-text {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.snp-link {
  font-size: 20rpx;
  font-weight: 800;
  color: #fc4c02;
}

.student-action-footer {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-top: 16rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
}

.coach-plan-action-btn {
  flex: 1;
  margin: 0;
  height: 68rpx;
  line-height: 68rpx;
  border-radius: 16rpx;
  font-size: 24rpx;
  font-weight: 800;
  border: none;
}

.coach-plan-action-btn::after {
  border: none;
}

.coach-plan-action-btn.btn-draft {
  background: linear-gradient(90deg, #f59e0b 0%, #f97316 100%);
  color: #111113;
}

.coach-plan-action-btn.btn-active {
  background: linear-gradient(90deg, #fc4c02 0%, #ea580c 100%);
  color: #ffffff;
}

.coach-plan-action-btn.btn-create {
  background: rgba(252, 76, 2, 0.16);
  color: #fc4c02;
  border: 1rpx solid rgba(252, 76, 2, 0.4);
}

/* ── Coach Plan Review Modal ── */
.plan-modal-content {
  max-height: 90vh;
  height: 88vh;
  padding: 28rpx 26rpx 40rpx 26rpx;
}

.pm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 18rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
}

.pm-student-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
}

.pm-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 36rpx;
}

.pm-student-info {
  flex: 1;
  min-width: 0;
}

.pm-name-line {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-wrap: wrap;
}

.pm-name {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.pm-tsb-badge {
  font-size: 18rpx;
  font-weight: 800;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.pm-sub-meta {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
  display: block;
}

.pm-tabs {
  display: flex;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 18rpx;
  padding: 6rpx;
  margin: 18rpx 0;
}

.pm-tab {
  flex: 1;
  text-align: center;
  font-size: 22rpx;
  font-weight: 800;
  padding: 14rpx 0;
  border-radius: 14rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.pm-tab.active {
  background: #fc4c02;
  color: #ffffff;
}

.pm-scroll-body {
  flex: 1;
  height: 66vh;
  overflow-y: auto;
}

.pm-loading-box,
.pm-empty-box {
  padding: 80rpx 30rpx;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16rpx;
}

.pm-empty-icon {
  font-size: 64rpx;
}

.pm-empty-title {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}


.pm-primary-btn {
  margin-top: 16rpx;
  background: #fc4c02;
  color: #ffffff;
  font-size: 24rpx;
  font-weight: 800;
  border-radius: 18rpx;
  padding: 0 36rpx;
  height: 76rpx;
  line-height: 76rpx;
}

.pm-review-workspace {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  padding-bottom: 40rpx;
}

.pm-plan-switcher {
  display: flex;
  gap: 12rpx;
}

.pm-switch-pill {
  flex: 1;
  text-align: center;
  padding: 12rpx;
  border-radius: 14rpx;
  font-size: 22rpx;
  font-weight: 800;
  background: rgba(255, 255, 255, 0.05);
  color: var(--rgm-text-2, #a1a1aa);
}

.pm-switch-pill.active {
  background: rgba(252, 76, 2, 0.2);
  color: #fc4c02;
  border: 1rpx solid rgba(252, 76, 2, 0.45);
}

.pm-plan-banner {
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 20rpx;
  padding: 18rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.pm-plan-banner.is-draft {
  border-color: rgba(245, 158, 11, 0.4);
  background: rgba(245, 158, 11, 0.06);
}

.pm-banner-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pm-status-tag {
  font-size: 20rpx;
  font-weight: 800;
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
}

.pm-status-tag.draft {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
}

.pm-status-tag.active {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
}

.pm-weeks-count {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.pm-title-input {
  background: rgba(0, 0, 0, 0.3);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 14rpx;
  height: 68rpx;
  padding: 0 18rpx;
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.pm-overview-textarea {
  width: 100%;
  box-sizing: border-box;
  background: rgba(0, 0, 0, 0.3);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 14rpx;
  padding: 14rpx 18rpx;
  font-size: 22rpx;
  color: var(--rgm-text-2, #d4d4d8);
  height: 110rpx;
}

.pm-week-scroll {
  white-space: nowrap;
}

.pm-week-row {
  display: inline-flex;
  gap: 12rpx;
}

.pm-week-pill {
  display: inline-flex;
  flex-direction: column;
  padding: 14rpx 22rpx;
  border-radius: 16rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.pm-week-pill.active {
  background: #fc4c02;
  border-color: #fc4c02;
}

.pm-wp-num {
  font-size: 24rpx;
  font-weight: 800;
  color: #ffffff;
}

.pm-wp-km {
  font-size: 18rpx;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 2rpx;
}

.pm-batch-bar {
  background: rgba(191, 90, 242, 0.08);
  border: 1rpx solid rgba(191, 90, 242, 0.28);
  border-radius: 18rpx;
  padding: 16rpx;
}

.pm-batch-title {
  font-size: 22rpx;
  font-weight: 800;
  color: #ffffff;
  display: block;
}


.pm-batch-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
}

.pm-adj-btn {
  margin: 0;
  height: 54rpx;
  line-height: 54rpx;
  padding: 0 16rpx;
  border-radius: 12rpx;
  font-size: 20rpx;
  font-weight: 700;
  border: none;
}

.pm-adj-btn::after {
  border: none;
}

.pm-adj-btn.down {
  background: rgba(245, 158, 11, 0.18);
  color: #fbbf24;
}

.pm-adj-btn.up {
  background: rgba(16, 185, 129, 0.18);
  color: #34d399;
}

.pm-adj-btn.protect {
  background: rgba(59, 130, 246, 0.18);
  color: #60a5fa;
}

.pm-days-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.pm-day-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 18rpx;
  padding: 18rpx;
}

.pm-day-card.is-done {
  border-color: rgba(16, 185, 129, 0.35);
}

.pm-day-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10rpx;
}

.pm-day-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8rpx;
}

.pm-day-dow {
  font-size: 22rpx;
  font-weight: 800;
  color: #ffffff;
}

.pm-day-date {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
  font-family: monospace;
}

.pm-day-type-tag {
  font-size: 18rpx;
  font-weight: 700;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(255, 255, 255, 0.08);
  color: #e4e4e7;
}

.pm-day-title {
  font-size: 24rpx;
  font-weight: 800;
  color: #ffffff;
}

.pm-day-km-badge {
  font-size: 24rpx;
  font-weight: 900;
  color: #fc4c02;
  font-family: monospace;
}

.pm-day-done-badge {
  font-size: 18rpx;
  color: #34d399;
  margin-left: 8rpx;
}

.pm-day-meta {
  display: flex;
  gap: 16rpx;
  font-size: 20rpx;
  color: #a1a1aa;
  margin-top: 8rpx;
}

.pm-day-desc {
  font-size: 20rpx;
  color: var(--rgm-text-2, #d4d4d8);
  line-height: 1.45;
  margin-top: 8rpx;
  display: block;
}

.pm-day-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.06);
}

.pm-quick-steppers {
  display: flex;
  gap: 8rpx;
}

.pm-step-btn {
  font-size: 20rpx;
  font-weight: 700;
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.08);
  color: #e4e4e7;
}

.pm-step-btn.plus {
  background: rgba(16, 185, 129, 0.16);
  color: #34d399;
}

.pm-step-btn.rest {
  background: rgba(244, 63, 94, 0.14);
  color: #fda4af;
}

.pm-edit-toggle-btn {
  font-size: 20rpx;
  font-weight: 800;
  color: #fc4c02;
  padding: 6rpx 16rpx;
  border-radius: 10rpx;
  background: rgba(252, 76, 2, 0.14);
}

.pm-day-editor {
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx dashed rgba(255, 255, 255, 0.15);
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.pm-type-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
}

.pm-type-chip {
  font-size: 20rpx;
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.06);
  color: #a1a1aa;
}

.pm-type-chip.active {
  background: #fc4c02;
  color: #ffffff;
  font-weight: 800;
}

.pm-editor-row {
  display: flex;
  gap: 12rpx;
}

.pm-editor-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.pm-ed-label {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.pm-ed-input {
  background: rgba(0, 0, 0, 0.35);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 12rpx;
  height: 60rpx;
  padding: 0 14rpx;
  font-size: 22rpx;
  color: #ffffff;
}

.pm-ed-textarea {
  width: 100%;
  box-sizing: border-box;
  background: rgba(0, 0, 0, 0.35);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 12rpx;
  padding: 12rpx 14rpx;
  font-size: 22rpx;
  color: #ffffff;
  height: 110rpx;
}

.pm-save-day-btn {
  background: #fc4c02;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 800;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 14rpx;
}

.pm-publish-card {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(252, 76, 2, 0.1) 100%);
  border: 1rpx solid rgba(16, 185, 129, 0.35);
  border-radius: 22rpx;
  padding: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.pm-pub-title {
  font-size: 24rpx;
  font-weight: 800;
  color: #ffffff;
}

.pm-note-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
}

.pm-note-chip {
  font-size: 18rpx;
  color: #d4d4d8;
  background: rgba(255, 255, 255, 0.08);
  padding: 6rpx 12rpx;
  border-radius: 10rpx;
}

.pm-note-textarea {
  width: 100%;
  box-sizing: border-box;
  background: rgba(0, 0, 0, 0.35);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 14rpx;
  padding: 14rpx;
  font-size: 22rpx;
  color: #ffffff;
  height: 110rpx;
}

.pm-publish-main-btn {
  background: linear-gradient(90deg, #10b981 0%, #059669 100%);
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 900;
  height: 80rpx;
  line-height: 80rpx;
  border-radius: 18rpx;
  margin: 0;
}

.pm-exec-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14rpx;
  margin-bottom: 20rpx;
}

.pm-exec-stat {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 18rpx;
  padding: 20rpx;
  text-align: center;
}

.pm-es-label {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  display: block;
}

.pm-es-val {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
  margin-top: 6rpx;
  display: block;
  font-family: monospace;
}

.pm-exec-days-card,
.pm-gen-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.pm-sec-title {
  font-size: 26rpx;
  font-weight: 800;
  color: #ffffff;
}

.pm-exec-day-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12rpx 0;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.05);
}

.pm-edr-left {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.pm-edr-dow {
  font-size: 22rpx;
  font-weight: 800;
  color: #ffffff;
}

.pm-edr-date {
  font-size: 18rpx;
  color: #8e8e93;
}

.pm-edr-title {
  font-size: 22rpx;
  color: #e4e4e7;
}

.pm-edr-tag {
  font-size: 20rpx;
  font-weight: 700;
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
}

.pm-edr-tag.done {
  background: rgba(16, 185, 129, 0.18);
  color: #34d399;
}

.pm-edr-tag.missed {
  background: rgba(244, 63, 94, 0.18);
  color: #fda4af;
}

.pm-edr-tag.rest {
  color: #71717a;
}

.pm-edr-tag.pending {
  background: rgba(255, 255, 255, 0.06);
  color: #a1a1aa;
}


.pm-gen-type-row {
  display: flex;
  gap: 12rpx;
}

.pm-gen-type-btn {
  flex: 1;
  text-align: center;
  padding: 16rpx;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.05);
  font-size: 22rpx;
  font-weight: 800;
  color: #a1a1aa;
}

.pm-gen-type-btn.active {
  background: rgba(252, 76, 2, 0.2);
  color: #fc4c02;
  border: 1rpx solid #fc4c02;
}

.pm-race-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 10rpx;
}

.pm-race-chip {
  font-size: 20rpx;
  padding: 8rpx 16rpx;
  border-radius: 12rpx;
  background: rgba(255, 255, 255, 0.06);
  color: #d4d4d8;
}

.pm-race-chip.active {
  background: #fc4c02;
  color: #ffffff;
  font-weight: 800;
}

.pm-pill-selector {
  display: flex;
  gap: 8rpx;
}

.pm-mini-pill {
  flex: 1;
  text-align: center;
  padding: 10rpx 0;
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.06);
  font-size: 20rpx;
  color: #a1a1aa;
}

.pm-mini-pill.active {
  background: #fc4c02;
  color: #ffffff;
  font-weight: 800;
}

.pm-wheel-stepper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.14);
  border-radius: 14rpx;
  height: 70rpx;
  overflow: hidden;
}

.pm-ws-btn {
  width: 60rpx;
  height: 70rpx;
  line-height: 70rpx;
  text-align: center;
  font-size: 30rpx;
  font-weight: 800;
  color: #fc4c02;
  background: rgba(255, 255, 255, 0.04);
  flex-shrink: 0;
}

.pm-ws-btn:active {
  background: rgba(252, 76, 2, 0.2);
}

.pm-ws-mid {
  flex: 1;
  height: 70rpx;
}

.pm-ws-val-wrap {
  height: 70rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
}

.pm-ws-val {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
}

.pm-ws-caret {
  font-size: 18rpx;
  color: var(--rgm-text-3, #a1a1aa);
}

.theme-volt .pm-wheel-stepper {
  background: #ffffff;
  border-color: rgba(15, 23, 42, 0.16);
}

.theme-volt .pm-ws-btn {
  background: #f4f5f7;
}

.theme-volt .pm-ws-val {
  color: #111317;
}

.cph-batch-btn.pipeline {
  background: linear-gradient(90deg, #10b981 0%, #059669 100%);
  color: #ffffff;
  font-weight: 900;
}

.cph-batch-btn.broadcast {
  background: rgba(99, 102, 241, 0.2);
  border: 1rpx solid rgba(99, 102, 241, 0.45);
  color: #a5b4fc;
  font-weight: 800;
}

.cph-filter-chip.injury.active {
  background: rgba(244, 63, 94, 0.25);
  color: #fda4af;
  border-color: rgba(244, 63, 94, 0.55);
}

.spe-w19-banner {
  background: var(--rgm-bg-card-subtle, rgba(255, 255, 255, 0.04));
  border-radius: 10rpx;
  padding: 8rpx 12rpx;
  margin-bottom: 10rpx;
}

.spe-w19-text {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-text-2, #d4d4d8);
}

.spe-feedback-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-bottom: 10rpx;
}

.spe-injury-pill {
  font-size: 18rpx;
  padding: 4rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(244, 63, 94, 0.16);
  color: var(--rgm-red, #fda4af);
  font-weight: 700;
}

.spe-summary-pill {
  font-size: 18rpx;
  padding: 4rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(56, 189, 248, 0.14);
  color: var(--rgm-blue, #7dd3fc);
  font-weight: 700;
}

.spe-day-cell.hrv-warn {
  border-color: rgba(244, 63, 94, 0.55);
  background: rgba(244, 63, 94, 0.14);
}

.spe-day-rpe {
  font-size: 16rpx;
  color: var(--rgm-amber, #fbbf24);
  font-weight: 800;
}

.pm-pipeline-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(16, 185, 129, 0.12);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
  border-radius: 16rpx;
  padding: 10rpx 16rpx;
  margin-bottom: 16rpx;
}

.pm-pipe-btn {
  font-size: 20rpx;
  font-weight: 800;
  color: var(--rgm-green, #34d399);
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background: var(--rgm-bg-card-subtle, rgba(0, 0, 0, 0.25));
}

.pm-pipe-btn.disabled {
  opacity: 0.35;
}

.pm-pipe-title {
  font-size: 20rpx;
  font-weight: 800;
  color: var(--rgm-text, #ecfdf5);
}

.pm-roadmap-box {
  margin-top: 10rpx;
  padding-top: 10rpx;
  border-top: 1rpx dashed var(--rgm-border, rgba(255, 255, 255, 0.1));
}

.pm-week-header-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 14rpx;
}

.pm-roll-trigger-btn {
  flex-shrink: 0;
  background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  font-size: 20rpx;
  font-weight: 800;
  padding: 12rpx 16rpx;
  border-radius: 14rpx;
}

.pm-roll-panel {
  background: rgba(99, 102, 241, 0.12);
  border: 1rpx solid rgba(99, 102, 241, 0.35);
  border-radius: 18rpx;
  padding: 18rpx;
  margin-bottom: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.pm-roll-title {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-text, #e0e7ff);
  display: block;
}


.pm-roll-submit-btn {
  background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 800;
  height: 68rpx;
  line-height: 68rpx;
  border-radius: 14rpx;
  margin: 0;
}

.pm-w19-summary-strip {
  background: rgba(16, 185, 129, 0.1);
  border: 1rpx solid rgba(16, 185, 129, 0.25);
  border-radius: 14rpx;
  padding: 12rpx 16rpx;
  margin-bottom: 14rpx;
}

.pm-w19-summary-txt {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-green, #a7f3d0);
}

.pm-day-card.hrv-warn-card {
  border-color: rgba(244, 63, 94, 0.5);
}

.pm-swap-tag {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 8rpx;
  background: rgba(245, 158, 11, 0.18);
  color: var(--rgm-amber, #fcd34d);
  font-weight: 700;
}

.pm-w19-day-feedback {
  background: var(--rgm-bg-card-subtle, rgba(0, 0, 0, 0.25));
  border-radius: 12rpx;
  padding: 10rpx 12rpx;
  margin-top: 8rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.pm-w19-badges-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  align-items: center;
}

.pm-rec-badge {
  font-size: 18rpx;
  font-weight: 800;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.pm-rec-badge.rec-green {
  background: rgba(16, 185, 129, 0.18);
  color: var(--rgm-green, #34d399);
}

.pm-rec-badge.rec-yellow {
  background: rgba(245, 158, 11, 0.18);
  color: var(--rgm-amber, #fbbf24);
}

.pm-rec-badge.rec-red {
  background: rgba(244, 63, 94, 0.18);
  color: var(--rgm-red, #fda4af);
}

.pm-bio-badge {
  font-size: 18rpx;
  color: var(--rgm-text-2, #a1a1aa);
  background: var(--rgm-bg-card-subtle, rgba(255, 255, 255, 0.06));
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.pm-bio-badge.warn {
  background: rgba(244, 63, 94, 0.18);
  color: var(--rgm-red, #fda4af);
  font-weight: 700;
}

.pm-rpe-badge {
  font-size: 18rpx;
  font-weight: 800;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(245, 158, 11, 0.16);
  color: var(--rgm-amber, #fcd34d);
}

.pm-str-badge {
  font-size: 18rpx;
  color: var(--rgm-blue, #38bdf8);
  background: rgba(56, 189, 248, 0.15);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: 700;
}

.pm-exec-line {
  font-size: 20rpx;
  color: var(--rgm-text, #e4e4e7);
  font-weight: 600;
}

.pm-feel-line {
  font-size: 20rpx;
  color: var(--rgm-amber, #fcd34d);
  font-weight: 700;
}

.pm-editor-divider {
  margin-top: 8rpx;
  padding-top: 10rpx;
  border-top: 1rpx dashed var(--rgm-border, rgba(255, 255, 255, 0.12));
}

.pm-ed-sec-title {
  font-size: 20rpx;
  font-weight: 800;
  color: var(--rgm-amber, #fbbf24);
}

.pm-swap-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
}

.pm-swap-pill {
  font-size: 18rpx;
  padding: 6rpx 12rpx;
  border-radius: 8rpx;
  background: rgba(255, 255, 255, 0.06);
  color: #a1a1aa;
}

.pm-swap-pill.active {
  background: #f59e0b;
  color: #ffffff;
  font-weight: 800;
}

.pm-week-summary-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 18rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.pm-runner-report-box {
  background: var(--rgm-bg-card-subtle, rgba(0, 0, 0, 0.25));
  border-radius: 12rpx;
  padding: 12rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.pm-rr-item {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.pm-rr-val {
  color: var(--rgm-text, #ffffff);
  font-weight: 700;
}

.pm-rr-val.warn {
  color: var(--rgm-red, #fda4af);
}

.pm-save-summary-btn {
  background: var(--rgm-bg-card-subtle, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text, #ffffff);
  font-size: 22rpx;
  font-weight: 800;
  height: 68rpx;
  line-height: 68rpx;
  border-radius: 14rpx;
  margin: 0;
}

.pm-publish-btn-group {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.pm-publish-next-btn {
  background: linear-gradient(90deg, #fc4c02 0%, #f59e0b 100%);
  color: #ffffff;
  font-size: 25rpx;
  font-weight: 900;
  height: 78rpx;
  line-height: 78rpx;
  border-radius: 18rpx;
  margin: 0;
}

.pm-edr-col {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.pm-edr-sub {
  font-size: 18rpx;
  color: #a1a1aa;
}

.cph-batch-btn.template-btn {
  background: linear-gradient(90deg, #fbbf24 0%, #f97316 100%);
  color: #111827;
  font-weight: 900;
}

.cph-filter-chip.grp-chip.active {
  background: #fbbf24;
  color: #111827;
  border-color: #fbbf24;
  font-weight: 900;
}

.mini-tag.tpl-tag {
  background: rgba(251, 191, 36, 0.18);
  color: var(--rgm-amber, #fde68a);
  border: 1rpx solid rgba(251, 191, 36, 0.45);
}

.mini-tag.tpl-rec-tag {
  background: rgba(245, 158, 11, 0.14);
  color: var(--rgm-amber, #fcd34d);
  border: 1rpx dashed rgba(245, 158, 11, 0.45);
}

.pm-quick-tpl-box {
  margin-top: 16rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.1);
}

.pm-qt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10rpx;
}

.pm-qt-title {
  font-size: 21rpx;
  font-weight: 800;
  color: #fde68a;
}

.pm-qt-scope-pills {
  display: flex;
  gap: 8rpx;
}

.pm-qt-scope {
  font-size: 19rpx;
  padding: 4rpx 12rpx;
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.06);
  color: #a1a1aa;
}

.pm-qt-scope.active {
  background: #fbbf24;
  color: #111827;
  font-weight: 800;
}

.pm-quick-tpl-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
}

.pm-qt-chip {
  font-size: 20rpx;
  padding: 8rpx 16rpx;
  border-radius: 12rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  color: #e4e4e7;
  font-weight: 700;
}

.pm-qt-chip.rec {
  background: rgba(251, 191, 36, 0.18);
  border-color: rgba(251, 191, 36, 0.5);
  color: #fde68a;
}

.pm-qt-chip.cur {
  background: #fbbf24;
  border-color: #fbbf24;
  color: #111827;
  font-weight: 900;
}

.tpl-group-cards {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-top: 12rpx;
}

.tpl-group-card {
  padding: 18rpx 20rpx;
  border-radius: 18rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.tpl-group-card.active {
  background: rgba(251, 191, 36, 0.15);
  border-color: #fbbf24;
}

.tgc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tgc-name {
  font-size: 25rpx;
  font-weight: 900;
  color: #ffffff;
}

.tgc-rec {
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: 10rpx;
  background: rgba(251, 191, 36, 0.2);
  color: #fde68a;
  font-weight: 700;
}

.tgc-pb {
  font-size: 21rpx;
  color: #d4d4d8;
  margin-top: 4rpx;
  display: block;
}

.tpl-detail-box {
  background: rgba(0, 0, 0, 0.3);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 18rpx;
  padding: 18rpx;
  margin-top: 14rpx;
}

.tpl-canova-box {
  margin-top: 12rpx;
  padding: 12rpx 14rpx;
  border-radius: 14rpx;
  background: rgba(16, 185, 129, 0.08);
  border: 1rpx solid rgba(16, 185, 129, 0.25);
}

.tpl-canova-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tpl-canova-title {
  font-size: 22rpx;
  font-weight: 800;
  color: #34d399;
}

.tpl-canova-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-top: 8rpx;
}

.tpl-canova-chip {
  font-size: 19rpx;
  color: #d1fae5;
  background: rgba(16, 185, 129, 0.16);
  padding: 4rpx 10rpx;
  border-radius: 8rpx;
}


.tdb-paces {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.tdb-pace-item {
  font-size: 20rpx;
  color: #e4e4e7;
  background: rgba(255, 255, 255, 0.05);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.tdb-days-list {
  margin-top: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.tdb-day-row {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  padding: 8rpx 10rpx;
  border-radius: 10rpx;
  background: rgba(255, 255, 255, 0.03);
}

.tdb-dow {
  font-size: 21rpx;
  font-weight: 800;
  color: #fbbf24;
  width: 64rpx;
  flex-shrink: 0;
}

.tdb-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.tdb-title {
  font-size: 22rpx;
  font-weight: 700;
  color: #ffffff;
}

.tdb-desc {
  font-size: 19rpx;
  color: #a1a1aa;
}

.tpl-members-section {
  margin-top: 16rpx;
}

.tms-header {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  margin-bottom: 12rpx;
}

.tms-quick-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
}

.tms-qbtn {
  font-size: 20rpx;
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background: rgba(251, 191, 36, 0.15);
  color: #fde68a;
  border: 1rpx solid rgba(251, 191, 36, 0.35);
}

.tms-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10rpx;
  max-height: 360rpx;
  overflow-y: auto;
}

.tms-member-chip {
  padding: 12rpx 14rpx;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tms-member-chip.checked {
  background: rgba(251, 191, 36, 0.18);
  border-color: #fbbf24;
}

.tms-m-left {
  display: flex;
  flex-direction: column;
}

.tms-m-name {
  font-size: 23rpx;
  font-weight: 800;
  color: #ffffff;
}

.tms-m-sub {
  font-size: 18rpx;
  color: #a1a1aa;
}

.tms-m-check {
  font-size: 24rpx;
}

.tpl-action-col {
  margin-top: 18rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.tpl-sub-actions {
  display: flex;
  gap: 12rpx;
}

/* ── 模版库分类筛选（自动换行，避免文字被挤成两行） ── */
.tpl-cat-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 6rpx;
}

.tpl-cat-pill {
  font-size: 22rpx;
  font-weight: 700;
  padding: 10rpx 20rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.14);
  color: #e4e4e7;
  white-space: nowrap;
}

.tpl-cat-pill.active {
  background: #fc4c02;
  border-color: #fc4c02;
  color: #ffffff;
  font-weight: 900;
}

/* ───────── ☀️ 明亮主题 (Volt v3.0)：模版库 / 批阅弹窗 60-30-10 配色 ───────── */
.theme-volt .pm-gen-card,
.theme-volt .pm-exec-days-card,
.theme-volt .pm-week-summary-card,
.theme-volt .pm-plan-banner,
.theme-volt .pm-day-card,
.theme-volt .tpl-group-card,
.theme-volt .tms-member-chip,
.theme-volt .tdb-day-row {
  background: #F8FAFC;
  border-color: #E2E8F0;
}

.theme-volt .tpl-detail-box {
  background: #ffffff;
  border-color: #E2E8F0;
}

.theme-volt .tpl-group-card.active,
.theme-volt .tms-member-chip.checked {
  background: #FFF5EE;
  border-color: rgba(252, 76, 2, 0.36);
}


.theme-volt .tgc-name,
.theme-volt .tdb-title,
.theme-volt .tms-m-name,
.theme-volt .pm-sec-title,
.theme-volt .pm-day-title,
.theme-volt .pm-day-dow,
.theme-volt .pm-wp-num,
.theme-volt .pm-pub-title,
.theme-volt .pm-batch-title,
.theme-volt .pm-edr-dow,
.theme-volt .pm-es-val {
  color: #0F172A;
}

.theme-volt .tgc-pb,
.theme-volt .tdb-desc,
.theme-volt .tms-m-sub,
.theme-volt .pm-day-meta,
.theme-volt .pm-edr-title,
.theme-volt .pm-edr-date,
.theme-volt .pm-ed-label,
.theme-volt .pm-rr-item {
  color: #475569;
}

.theme-volt .tgc-rec,
.theme-volt .tms-qbtn {
  background: #FFF5EE;
  color: #C23800;
  border-color: rgba(252, 76, 2, 0.32);
}

.theme-volt .tdb-dow,
.theme-volt .pm-ed-sec-title {
  color: #C23800;
}

.theme-volt .tdb-pace-item {
  background: #F8FAFC;
  color: #0F172A;
  border: 1rpx solid #E2E8F0;
}

.theme-volt .tpl-cat-pill,
.theme-volt .pm-mini-pill,
.theme-volt .pm-type-chip,
.theme-volt .pm-note-chip,
.theme-volt .pm-race-chip,
.theme-volt .pm-qt-chip,
.theme-volt .pm-qt-scope,
.theme-volt .pm-swap-pill,
.theme-volt .pm-step-btn {
  background: #F1F5F9;
  border-color: #E2E8F0;
  color: #475569;
}

.theme-volt .tpl-cat-pill.active,
.theme-volt .pm-mini-pill.active,
.theme-volt .pm-type-chip.active,
.theme-volt .pm-race-chip.active {
  background: #FC4C02;
  border-color: #FC4C02;
  color: #ffffff;
}

.theme-volt .pm-qt-chip.cur,
.theme-volt .pm-qt-scope.active,
.theme-volt .pm-swap-pill.active {
  background: #FFF5EE;
  border-color: rgba(252, 76, 2, 0.36);
  color: #C23800;
}

.theme-volt .pm-ed-input,
.theme-volt .pm-ed-textarea,
.theme-volt .pm-note-textarea,
.theme-volt .pm-title-input,
.theme-volt .pm-overview-textarea {
  background: #ffffff;
  border-color: #CBD5E1;
  color: #0F172A;
}

.theme-volt .pm-roll-panel {
  background: #F8FAFC;
  border-color: #E2E8F0;
}

.theme-volt .pm-roll-title {
  color: #0F172A;
}


.theme-volt .cph-batch-btn.secondary {
  background: #F1F5F9;
  color: #0F172A;
  border-color: #E2E8F0;
}

.theme-volt .pm-qt-title {
  color: #C23800;
}

.student-rec-reason-line {
  margin-top: 8rpx;
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background: rgba(245, 158, 11, 0.08);
  border: 1rpx solid rgba(245, 158, 11, 0.2);
}

.student-rec-reason-txt {
  font-size: 21rpx;
  color: #fde68a;
  line-height: 1.4;
}

.theme-volt .student-rec-reason-line {
  background: #F8FAFC;
  border-color: #E2E8F0;
}

.theme-volt .student-rec-reason-txt {
  color: #475569;
}

/* ── Volt Light Mode Adaptation for Coach Plan Hub ── */
.theme-volt .coach-plan-hub-card {
  background: var(--rgm-card, #ffffff);
  border: 1rpx solid rgba(252, 76, 2, 0.28);
  box-shadow: 0 4rpx 16rpx rgba(15, 23, 42, 0.05);
}

.theme-volt .cph-batch-btn.pipeline {
  background: #f0f9ff;
  color: #0284c7;
  border-color: #bae6fd;
}

.theme-volt .cph-batch-btn.broadcast {
  background: #faf5ff;
  color: #7e22ce;
  border-color: #e9d5ff;
}

.theme-volt .cph-batch-btn.template-btn {
  background: #f0fdf4;
  color: #059669;
  border-color: #bbf7d0;
}

.theme-volt .cph-filter-chip {
  background: #f1f5f9;
  color: #475569;
  border-color: #e2e8f0;
}

.theme-volt .cph-filter-chip.active {
  background: #0f172a;
  color: #ffffff;
  border-color: #0f172a;
}

.theme-volt .student-search-input {
  background: #f8fafc;
  color: #0f172a;
  border: 1rpx solid #cbd5e1;
}

.theme-volt .sort-chip {
  background: #f1f5f9;
  color: #475569;
  border-color: #e2e8f0;
}

/* Cockpit Empty Card */
.cockpit-empty-card {
  padding: 60rpx 30rpx;
  text-align: center;
  border-radius: 24rpx;
  background: var(--rgm-card, #141418);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12rpx;
  margin-top: 16rpx;
}

.theme-volt .cockpit-empty-card {
  background: #ffffff;
  border-color: #e2e8f0;
  box-shadow: 0 4rpx 16rpx rgba(15, 23, 42, 0.04);
}

.cec-icon {
  font-size: 54rpx;
  margin-bottom: 6rpx;
}

.cec-title {
  font-size: 28rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.cec-sub {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
}
</style>


