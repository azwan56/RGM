<template>
  <view :class="['page-container', themeClass]">
    <!-- Loading State -->
    <view v-if="loading && !event" class="loading-box">
      <text class="loading-text">加载中...</text>
    </view>

    <block v-else-if="event">
      <!-- 1. Hero Header Card -->
      <view class="hero-card">
        <image class="hero-bg" :src="event.cover_image" mode="aspectFill" />
        <view class="hero-mask"></view>
        <view class="hero-content">
          <view class="hero-top-row">
            <view class="club-pill" @tap="goToClubHome">
              <text class="club-pill-icon">🏅</text>
              <text class="club-pill-text">{{ event.club_name || '跑团约跑' }} · 进跑团 ›</text>
            </view>
            <view class="status-pill" :class="isOngoingOrPast ? 'done' : 'upcoming'">
              <text>{{ countdownLabel }}</text>
            </view>
          </view>

          <text class="hero-title">{{ event.title }}</text>

          <view class="hero-meta-grid">
            <view class="hero-meta-item">
              <text class="meta-label">⏰ 集合时间</text>
              <text class="meta-val">{{ formatMeetTime(event.meet_time || event.start_date) }}</text>
            </view>
            <view class="hero-meta-item" @tap="openRunLocation(event)">
              <text class="meta-label">📍 集合地点</text>
              <text class="meta-val link">{{ event.location || '跑团指定集合点' }} ❯</text>
            </view>
          </view>

          <view class="hero-Specs-row">
            <view class="spec-badge accent">🎯 目标 {{ event.target_km || 10 }} km</view>
            <view class="spec-badge">⚡ 建议配速 {{ event.pace_requirement || '全配速友好' }}</view>
            <view class="spec-badge">👥 已报 {{ event.participant_count || 0 }}<text v-if="event.max_participants > 0">/{{ event.max_participants }}</text> 人</view>
          </view>

          <!-- 活动路线与说明（打开邀请链接即可直接完整查看） -->
          <view v-if="event.location_detail || event.rules" class="hero-desc-box">
            <view v-if="event.location_detail" class="hero-desc-line">
              <text class="hero-desc-tag">🚩 路线：</text>
              <text class="hero-desc-txt">{{ event.location_detail }}</text>
            </view>
            <view v-if="event.rules" class="hero-desc-line">
              <text class="hero-desc-tag">💡 活动内容：</text>
              <text class="hero-desc-txt">{{ event.rules }}</text>
            </view>
          </view>

          <view class="hero-organizer-row">
            <view class="org-left">
              <image v-if="event.creator_avatar" :src="event.creator_avatar" class="org-avatar" mode="aspectFill" />
              <view v-else class="org-avatar-fallback">{{ (event.creator_name || '团')[0] }}</view>
              <text class="org-text">发起人：{{ event.creator_name || '跑团管理员' }}</text>
            </view>
            <view class="hero-quick-btns">
              <button class="hero-share-wx-btn" open-type="share">💬 转发</button>
              <view class="hero-poster-btn" @tap="openPosterModal">
                <text>🖼️ 海报</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- 🗺️ 集合地点地图标注卡片（对所有受邀访客直接开放查看） -->
      <view
        v-if="event.latitude && event.longitude"
        style="margin-bottom: 24rpx; border-radius: 20rpx; overflow: hidden; border: 1rpx solid rgba(59, 130, 246, 0.35); background: rgba(15, 23, 42, 0.6);"
      >
        <view style="display: flex; align-items: center; justify-content: space-between; padding: 14rpx 20rpx;">
          <view style="flex: 1; overflow: hidden;">
            <text style="display: block; font-size: 24rpx; font-weight: 700; color: #f8fafc;">
              📍 集合地点：{{ event.location || '约跑集合点' }}
            </text>
            <text v-if="event.location_detail" style="display: block; font-size: 21rpx; color: #94a3b8; margin-top: 2rpx;">
              {{ event.location_detail }}
            </text>
          </view>
          <view
            style="padding: 8rpx 18rpx; border-radius: 999rpx; background: #2563eb; color: #ffffff; font-size: 22rpx; font-weight: 700; margin-left: 14rpx;"
            @tap="openRunLocation(event)"
          >
            🗺️ 地图导航 ›
          </view>
        </view>
        <map
          style="width: 100%; height: 220rpx;"
          :latitude="Number(event.latitude)"
          :longitude="Number(event.longitude)"
          :scale="16"
          :markers="eventDetailMapMarkers"
          @tap="openRunLocation(event)"
        />
      </view>

      <!-- ── 已完成归档状态提示条 ── -->
      <view v-if="isEventArchived" class="archived-banner-card">
        <text class="abc-icon">📁</text>
        <view class="abc-body">
          <text class="abc-title">本场约跑已完成并归档</text>
          <text class="abc-sub">活动已从进行中列表归档，仍可浏览本场完赛战报与成员成绩</text>
        </view>
      </view>

      <!-- ── 受邀报名卡片：一键免填表直接参团报名（老用户自动关联档案，新用户直接入团、资料后续补齐） ── -->
      <view v-else-if="!event.is_joined" class="newcomer-club-card">
        <view class="ncc-top">
          <view class="ncc-badge">{{ !event.is_club_member ? '📩 约跑邀请 · 一键入团报名' : '🏃 本团约跑集结中' }}</view>
          <text class="ncc-city" v-if="event.club_city">📍 {{ event.club_city }}</text>
        </view>
        <text class="ncc-title">{{ !event.is_club_member ? `欢迎参加【${event.club_name || '万跑跑团'}】约跑` : `报名【${event.title}】` }}</text>
        <text class="ncc-desc">
          {{ !event.is_club_member
            ? '老用户将直接关联您的个人资料并将约跑显示在首页；新用户将直接加入跑团，个人资料可后续补齐'
            : '报名后本场约跑将自动显示在您的首页，支持一键同步手机日历提醒' }}
        </text>
        <view class="ncc-actions">
          <button class="ncc-btn primary" :loading="joiningDirect" @tap="handleOneTapJoin">
            🏃 一键报名
          </button>
          <button class="ncc-btn ghost" @tap="openJoinOrCheckinModal">
            ⚙️ 选配速分组
          </button>
        </view>
      </view>

      <!-- ── 已报名确认卡：直达首页查看约跑 + 资料后续补齐轻提示 ── -->
      <view v-else class="joined-home-sync-card">
        <view class="jhsc-top">
          <view class="jhsc-badge">✅ 您已报名本场约跑</view>
          <text class="jhsc-sync-tag">已同步至首页</text>
        </view>
        <view class="jhsc-actions">
          <button class="jhsc-btn primary" @tap="goToHomePage">🏠 首页查看</button>
          <button class="jhsc-btn ghost" @tap="addRunToCalendar(event)">🔔 日历</button>
          <button class="jhsc-btn share" open-type="share">💬 转发</button>
        </view>
        <view v-if="showDeferredProfileTip" class="jhsc-profile-tip" @tap="goToMyProfile">
          <text class="jhsc-tip-txt">💡 已直接将您添加至【{{ event.club_name || '跑团' }}】，个人资料可随时点此后续补齐 ›</text>
        </view>
      </view>

      <!-- ── 阶段导航：约跑前（集结分队）/ 约跑后（完赛战报），吸顶显示 ── -->
      <view class="stage-nav">
        <view :class="['stage-tab', activeStage === 'pre' ? 'active' : '']" @tap="switchStage('pre')">
          <text class="stage-step">STEP 1 · 约跑前</text>
          <text class="stage-name">📣 集结与分队</text>
          <text class="stage-hint">{{ event.participant_count || 0 }} 人已报名</text>
        </view>
        <view class="stage-arrow">›</view>
        <view :class="['stage-tab', activeStage === 'post' ? 'active' : '']" @tap="switchStage('post')">
          <text class="stage-step">STEP 2 · 约跑后</text>
          <text class="stage-name">🏆 完赛战报</text>
          <text class="stage-hint">{{ isPostStage ? (socialSummary.completed_count || 0) + ' 人已完赛' : '开跑后解锁' }}</text>
        </view>
      </view>

      <!-- 2. 页面开放范围（约跑后战报页顶部显示，可由发起人配置） -->
      <view v-if="activeStage === 'post'" class="visibility-card">
        <view class="vis-header">
          <view class="vis-title-row">
            <text class="vis-icon">{{ visibilityBadge.icon }}</text>
            <view>
              <text class="vis-title">{{ visibilityBadge.title }}</text>
            </view>
          </view>
        </view>

        <!-- Organizer / Admin 1-click Visibility Switcher -->
        <view v-if="event.can_manage" class="vis-switch-bar">
          <view
            v-for="opt in visibilityOptions"
            :key="opt.value"
            :class="['vis-opt-pill', event.visibility_mode === opt.value ? 'active' : '']"
            @tap="changeVisibility(opt.value)"
          >
            <text class="vis-opt-label">{{ opt.label }}</text>
          </view>
        </view>
      </view>

      <!-- 3. Locked View when visibility_mode === 'registered_only' and viewer hasn't joined -->
      <view v-if="!event.can_view_roster" class="locked-roster-card">
        <view class="lock-icon-circle">🔒</view>
        <text class="lock-title">名单与战报仅报名者可见</text>
        <text class="lock-subtitle">
          已有 {{ event.participant_count || 0 }} 位跑友报名
        </text>
        <view class="masked-avatars-row" v-if="event.participants && event.participants.length">
          <view v-for="(mp, idx) in event.participants" :key="idx" class="masked-user-chip">
            <view class="masked-avatar">{{ (mp.display_name || '跑')[0] }}</view>
            <text class="masked-name">{{ mp.display_name }}</text>
            <text class="masked-group">{{ mp.pace_group }}</text>
          </view>
        </view>
        <button v-if="!isEventArchived" class="unlock-join-btn" :loading="joiningDirect" @tap="handleOneTapJoin">
          🏃 一键报名解锁
        </button>
      </view>

      <!-- 4. Full Unlocked Social & Performance Experience -->
      <block v-else>
        <!-- ════════════ STAGE 1 · 约跑前：集结与分队 ════════════ -->
        <block v-if="activeStage === 'pre'">
          <!-- ① 我的报名 -->
          <view class="stage-sec-label"><text class="ssl-num">1</text><text class="ssl-text">我的报名</text></view>
          <view class="my-status-card">
            <view v-if="!event.is_joined" class="not-joined-box">
              <view class="nj-info">
                <text class="nj-title">{{ isEventArchived ? '📁 活动已归档结束' : '👋 尚未报名' }}</text>
              </view>
              <button v-if="!isEventArchived" class="join-cta-btn" :loading="joiningDirect" @tap="handleOneTapJoin">一键报名</button>
            </view>
            <view v-else class="joined-box">
              <view class="jb-top">
                <view class="jb-left">
                  <view class="jb-badge">✅ 已报名</view>
                  <view class="jb-tag">{{ event.my_participation?.pace_group || '🏃 有氧组' }}</view>
                  <view class="jb-tag role">{{ event.my_participation?.runner_role || '🏃 跟跑团员' }}</view>
                </view>
                <view v-if="!isEventArchived" class="jb-actions">
                  <text class="jb-edit-btn" @tap="openJoinOrCheckinModal">修改分队</text>
                  <text class="jb-leave-btn" @tap="handleLeaveEvent">取消报名</text>
                </view>
              </view>
              <view class="pre-quick-row">
                <view class="pre-quick-btn" @tap="addRunToCalendar(event)">📅 加入日历提醒</view>
                <view class="pre-quick-btn" @tap="openRunLocation(event)">📍 导航到集合点</view>
                <view class="pre-quick-btn accent" @tap="openPosterModal">🖼️ 约跑海报</view>
              </view>
            </view>
          </view>

          <!-- ② 配速列车分队名单 -->
          <view class="stage-sec-label"><text class="ssl-num">2</text><text class="ssl-text">配速分队（{{ (event.participants || []).length }} 人）</text></view>
          <view class="roster-card">
            <view v-if="!preTrainGroups.length" class="empty-comment-hint">暂无报名</view>
            <view v-for="grp in preTrainGroups" :key="grp.name" class="train-group">
              <view class="tg-head">
                <text class="tg-name">{{ grp.name }}</text>
                <text class="tg-count">{{ grp.members.length }} 人</text>
              </view>
              <view class="tg-members">
                <view v-for="(m, mi) in grp.members" :key="m.user_id || mi" class="tg-member">
                  <image v-if="m.avatar_url" :src="m.avatar_url" class="tg-avatar" mode="aspectFill" />
                  <view v-else class="tg-avatar tg-avatar-fb">{{ (m.display_name || '跑')[0] }}</view>
                  <view class="tg-meta">
                    <text class="tg-mname">{{ m.display_name }}</text>
                    <text class="tg-msub">{{ m.runner_role || '🏃 跟跑团员' }} · 近30天 {{ m.display_pace_str || '--' }}/km</text>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </block>

        <!-- ════════════ STAGE 2 · 约跑后：完赛战报 ════════════ -->
        <block v-if="activeStage === 'post'">
        <!-- 未开跑提示 -->
        <view v-if="!isPostStage" class="post-locked-tip">
          <text class="plt-icon">⏳</text>
          <text class="plt-text">约跑尚未开始，开跑后可登记成绩</text>
        </view>

        <!-- ① 我的成绩 -->
        <view class="stage-sec-label"><text class="ssl-num">1</text><text class="ssl-text">我的成绩</text></view>
        <view class="my-status-card">
          <view v-if="!event.is_joined" class="not-joined-box">
            <view class="nj-info">
              <text class="nj-title">你未报名本场约跑</text>
            </view>
            <button class="join-cta-btn" @tap="openJoinOrCheckinModal">补报名</button>
          </view>
          <view v-else class="joined-box">
            <view class="jb-stats-strip">
              <view class="jb-stat">
                <text class="jb-stat-lbl">状态</text>
                <text class="jb-stat-val highlight">{{ event.my_participation?.has_completed_run ? '🏆 已完赛' : '⏳ 待登记' }}</text>
              </view>
              <view class="jb-stat">
                <text class="jb-stat-lbl">距离</text>
                <text class="jb-stat-val">{{ event.my_participation?.has_completed_run ? event.my_participation?.display_distance_km : '--' }} km</text>
              </view>
              <view class="jb-stat">
                <text class="jb-stat-lbl">配速</text>
                <text class="jb-stat-val">{{ event.my_participation?.has_completed_run ? event.my_participation?.display_pace_str : '--' }}/km</text>
              </view>
              <view class="jb-stat" @tap="openJoinOrCheckinModal">
                <text class="jb-stat-lbl">手表记录</text>
                <text class="jb-stat-val link">{{ event.my_participation?.has_completed_run ? '修改 ❯' : '关联 ❯' }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- ② 团队战报 -->
        <view class="stage-sec-label"><text class="ssl-num">2</text><text class="ssl-text">团队战报</text></view>
        <view class="summary-card">
          <view class="sec-header">
            <text class="sec-title">📊 战报总览</text>
          </view>

          <view class="team-kpi-grid">
            <view class="kpi-box">
              <text class="kpi-num">{{ socialSummary.participant_count || 0 }}<text class="kpi-unit">人</text></text>
              <text class="kpi-label">集结团员</text>
            </view>
            <view class="kpi-box">
              <text class="kpi-num">{{ socialSummary.completed_count || 0 }}<text class="kpi-unit">人</text></text>
              <text class="kpi-label">完赛打卡 ({{ socialSummary.completion_rate || 0 }}%)</text>
            </view>
            <view class="kpi-box">
              <text class="kpi-num accent">
                {{ (socialSummary.total_actual_km > 0 ? socialSummary.total_actual_km : socialSummary.total_target_km) || 0 }}
                <text class="kpi-unit">km</text>
              </text>
              <text class="kpi-label">{{ socialSummary.total_actual_km > 0 ? '团队实跑总里程' : '预计团队总里程' }}</text>
            </view>
            <view class="kpi-box">
              <text class="kpi-num">{{ socialSummary.team_avg_pace_str || '--' }}</text>
              <text class="kpi-label">团队平均配速</text>
            </view>
          </view>

          <!-- MVP Honor Badges -->
          <view class="mvp-row" v-if="socialSummary.mvp_longest || socialSummary.mvp_fastest || socialSummary.mvp_earliest">
            <view class="mvp-chip" v-if="socialSummary.mvp_longest">
              <text class="mvp-icon">🏆</text>
              <view class="mvp-info">
                <text class="mvp-tag">里程担当</text>
                <text class="mvp-name">{{ socialSummary.mvp_longest.display_name }}</text>
                <text class="mvp-val">{{ socialSummary.mvp_longest.value_label }}</text>
              </view>
            </view>
            <view class="mvp-chip" v-if="socialSummary.mvp_fastest">
              <text class="mvp-icon">⚡</text>
              <view class="mvp-info">
                <text class="mvp-tag">破风先锋</text>
                <text class="mvp-name">{{ socialSummary.mvp_fastest.display_name }}</text>
                <text class="mvp-val">{{ socialSummary.mvp_fastest.value_label }}/km</text>
              </view>
            </view>
            <view class="mvp-chip" v-if="socialSummary.mvp_earliest">
              <text class="mvp-icon">🌅</text>
              <view class="mvp-info">
                <text class="mvp-tag">早鸟一号</text>
                <text class="mvp-name">{{ socialSummary.mvp_earliest.display_name }}</text>
                <text class="mvp-val">{{ socialSummary.mvp_earliest.value_label }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- ③ 最终参与人员与成绩榜 -->
        <view class="stage-sec-label"><text class="ssl-num">3</text><text class="ssl-text">完赛成绩榜</text></view>
        <view class="roster-card">
          <view class="sec-header">
            <view>
              <text class="sec-title">👟 参与人员 ({{ filteredParticipants.length }}人)</text>
            </view>
          </view>

          <!-- Pace Train Grouping Filter Bar -->
          <scroll-view scroll-x class="pace-train-scroll">
            <view class="pace-train-row">
              <view
                :class="['train-chip', activePaceFilter === 'ALL' ? 'active' : '']"
                @tap="activePaceFilter = 'ALL'"
              >
                全部 ({{ (event.participants || []).length }})
              </view>
              <view
                v-for="pg in socialSummary.pace_groups_summary || []"
                :key="pg.pace_group"
                :class="['train-chip', activePaceFilter === pg.pace_group ? 'active' : '']"
                @tap="activePaceFilter = pg.pace_group"
              >
                {{ pg.pace_group }} ({{ pg.count }})
              </view>
            </view>
          </scroll-view>

          <!-- Sort Tabs -->
          <view class="roster-sort-bar">
            <text class="sort-label">排序方式：</text>
            <view class="sort-pills">
              <text :class="['sort-pill', sortBy === 'distance' ? 'active' : '']" @tap="sortBy = 'distance'">按距离</text>
              <text :class="['sort-pill', sortBy === 'pace' ? 'active' : '']" @tap="sortBy = 'pace'">按配速</text>
              <text :class="['sort-pill', sortBy === 'join_order' ? 'active' : '']" @tap="sortBy = 'join_order'">按报名序</text>
            </view>
          </view>

          <!-- Participant Rows -->
          <view class="roster-list">
            <view v-for="(runner, idx) in filteredParticipants" :key="runner.user_id || idx" class="runner-row">
              <view class="runner-rank" :class="idx < 3 ? 'top-' + (idx + 1) : ''">
                {{ idx + 1 }}
              </view>

              <view class="runner-avatar-wrap">
                <image v-if="runner.avatar_url" :src="runner.avatar_url" class="runner-avatar" mode="aspectFill" />
                <view v-else class="runner-avatar-fallback">{{ (runner.display_name || '跑')[0] }}</view>
              </view>

              <view class="runner-main">
                <view class="runner-name-line">
                  <text class="runner-name">{{ runner.display_name }}</text>
                  <text class="role-badge">{{ runner.runner_role || '🏃 跟跑团员' }}</text>
                  <text class="group-badge">{{ runner.pace_group || '🏃 有氧组' }}</text>
                </view>

                <!-- MVP Badges if any -->
                <view class="runner-badges-line" v-if="runner.badges && runner.badges.length">
                  <text v-for="b in runner.badges" :key="b" class="honor-tag">{{ b }}</text>
                </view>

                <!-- Distance / Pace / Duration / HR Metrics -->
                <view class="runner-metrics-bar">
                  <view class="metric-cell">
                    <text class="m-lbl">{{ runner.has_completed_run ? '实跑距离' : '目标距离' }}</text>
                    <text class="m-val highlight">{{ runner.display_distance_km }} <text class="m-unit">km</text></text>
                  </view>
                  <view class="metric-cell">
                    <text class="m-lbl">{{ runner.has_completed_run ? '平均配速' : '参考配速' }}</text>
                    <text class="m-val">{{ runner.display_pace_str }}<text class="m-unit">/km</text></text>
                  </view>
                  <view class="metric-cell" v-if="runner.has_completed_run && runner.actual_duration_str !== '--'">
                    <text class="m-lbl">完赛用时</text>
                    <text class="m-val">{{ runner.actual_duration_str }}</text>
                  </view>
                  <view class="metric-cell" v-else>
                    <text class="m-lbl">月跑量</text>
                    <text class="m-val">{{ runner.recent_30d_km || 0 }}<text class="m-unit">km</text></text>
                  </view>
                  <view class="metric-cell" v-if="runner.actual_heartrate">
                    <text class="m-lbl">平均心率</text>
                    <text class="m-val">{{ runner.actual_heartrate }}<text class="m-unit">bpm</text></text>
                  </view>
                </view>

                <view class="runner-source-line">
                  <text class="source-tag" :class="runner.data_source">
                    {{
                      runner.data_source === 'watch_sync'
                        ? '⌚ 手表同步'
                        : runner.data_source === 'manual_checkin'
                        ? '✍️ 手动打卡'
                        : '📈 近30天参考配速'
                    }}
                  </text>
                  <text v-if="runner.checkin_note" class="runner-note">“{{ runner.checkin_note }}”</text>
                </view>
              </view>

              <!-- High-Five Social Button -->
              <view class="highfive-btn" @tap="handleHighfive(runner)">
                <text class="hf-emoji">👏</text>
                <text class="hf-count">{{ runner.likes_count || 0 }}</text>
              </view>
            </view>
          </view>
        </view>
        </block>

        <!-- 文案生成：按阶段只展示一种内容（约跑前=群接龙；约跑后=完赛战报） -->
        <view class="stage-sec-label">
          <text class="ssl-num">{{ activeStage === 'pre' ? 3 : 4 }}</text>
          <text class="ssl-text">{{ activeStage === 'pre' ? '分享群接龙' : '分享战报' }}</text>
        </view>
        <view class="generator-card">
          <view class="copy-preview-box">
            <text selectable class="copy-preview-text">{{ activeStage === 'pre' ? socialSummary.share_solitaire_text : socialSummary.share_battle_report_text }}</text>
          </view>
          <view class="gen-btn-row">
            <button class="gen-action-btn" @tap="copyGeneratedText">
              📑 复制{{ activeStage === 'pre' ? '接龙文案' : '战报文案' }}
            </button>
            <button class="gen-action-btn accent" @tap="openPosterModal">
              🖼️ {{ activeStage === 'pre' ? '约跑海报' : '战报海报' }}
            </button>
          </view>
        </view>

        <!-- 留言墙：约跑前=集结喊话；约跑后=跑后感言 -->
        <view class="stage-sec-label">
          <text class="ssl-num">{{ activeStage === 'pre' ? 4 : 5 }}</text>
          <text class="ssl-text">{{ activeStage === 'pre' ? '集结喊话' : '跑后感言' }}</text>
        </view>
        <view class="comments-card">
          <view class="sec-header">
            <text class="sec-title">💬 {{ activeStage === 'pre' ? '集结留言' : '跑后感言' }} ({{ (event.comments || []).length }})</text>
          </view>

          <!-- Quick phrase chips -->
          <scroll-view scroll-x class="quick-phrases-scroll">
            <view class="quick-phrases-row">
              <view
                v-for="phrase in quickPhrases"
                :key="phrase"
                class="phrase-chip"
                @tap="useQuickPhrase(phrase)"
              >
                {{ phrase }}
              </view>
            </view>
          </scroll-view>

          <view class="comment-input-row">
            <input
              v-model="newComment"
              class="comment-input"
              placeholder="喊话队友、约配速、或分享跑后感受..."
              confirm-type="send"
              @confirm="submitComment"
            />
            <button class="comment-send-btn" @tap="submitComment">发送</button>
          </view>

          <view v-if="event.comments && event.comments.length" class="comment-list">
            <view v-for="c in event.comments" :key="c.id" class="comment-item">
              <view class="c-avatar">{{ (c.display_name || '跑')[0] }}</view>
              <view class="c-body">
                <view class="c-top">
                  <text class="c-name">{{ c.display_name }}</text>
                  <text class="c-time">{{ formatShortTime(c.created_at) }}</text>
                </view>
                <text class="c-text">{{ c.content }}</text>
              </view>
            </view>
          </view>
          <view v-else class="empty-comment-hint">
            暂无留言
          </view>
        </view>
      </block>

      <!-- ── 底部固定操作栏：按阶段只给出该阶段的主操作 ── -->
      <view class="bottom-bar-spacer"></view>
      <view class="bottom-action-bar">
        <block v-if="activeStage === 'pre'">
          <button class="bab-btn ghost" open-type="share">💬 转发</button>
          <button class="bab-btn ghost" @tap="openPosterModal">🖼️ 海报</button>
          <button v-if="isEventArchived" class="bab-btn primary" @tap="switchStage('post')">🏆 看战报</button>
          <button v-else-if="!event.is_joined" class="bab-btn primary" :loading="joiningDirect" @tap="handleOneTapJoin">🏃 一键报名</button>
          <button v-else class="bab-btn primary" @tap="goToHomePage">🏠 首页查看</button>
        </block>
        <block v-else>
          <button class="bab-btn ghost" open-type="share">💬 转发</button>
          <button class="bab-btn ghost" @tap="openPosterModal">🖼️ 海报</button>
          <button class="bab-btn primary" @tap="openJoinOrCheckinModal">{{ event.my_participation?.has_completed_run ? '✏️ 改成绩' : '✍️ 登成绩' }}</button>
        </block>
      </view>
    </block>

    <view v-else class="loading-box">
      <text class="loading-text">正在跳转...</text>
      <button class="ncc-btn primary" style="margin-top: 28rpx; width: 420rpx;" @tap="goToClubHome">
        🏅 进入跑团
      </button>
    </view>

    <!-- Modal 1: Join / Newcomer Account Activation / Role / Performance Check-in Modal -->
    <view v-if="showCheckinModal" class="modal-mask" @tap="showCheckinModal = false">
      <view class="modal-panel" @tap.stop>
        <view class="modal-header">
          <view class="modal-title-wrap">
            <text class="modal-title">{{ activeStage === 'post' ? '✍️ 登记完赛成绩' : (event?.is_joined ? '⚙️ 修改分队与角色' : (!event?.is_club_member ? '🎉 入团并报名约跑' : '🏃 报名本场约跑')) }}</text>
            <text class="modal-subtitle">{{ event?.title || '跑团约跑集结' }}</text>
          </view>
          <view class="modal-close-btn" @tap="showCheckinModal = false">✕</view>
        </view>

        <!-- 新人开通账号与自动加入跑团区块（选填，绝不强制拦截报名） -->
        <view v-if="!event?.is_club_member || (!event?.is_joined && isNewAccount)" class="newcomer-modal-box">
          <view class="nmb-head">
            <text class="nmb-badge">{{ isNewAccount ? '🆕 新跑友直通入团（资料可后续补齐）' : '🏅 自动加入跑团' }}</text>
          </view>
          <view class="nmb-input-row">
            <text class="nmb-lbl">跑者昵称（选填）</text>
            <input
              v-model="formNickname"
              type="nickname"
              class="nmb-input"
              placeholder="选填，也可稍后在「我的」补齐"
              @blur="onNicknameBlur"
            />
          </view>
          <view v-if="!event?.is_club_member" class="nmb-club-toggle" @tap="formAutoJoinClub = !formAutoJoinClub">
            <text class="nmb-check">{{ formAutoJoinClub ? '✅' : '⬜' }}</text>
            <view class="nmb-club-info">
              <text class="nmb-club-title">同步加入【{{ event?.club_name || '本跑团' }}】</text>
            </view>
          </view>
        </view>

        <view class="form-group">
          <text class="form-label">1. 选择配速分组</text>
          <view class="option-grid">
            <view
              v-for="pg in paceGroupChoices"
              :key="pg"
              :class="['opt-chip', formPaceGroup === pg ? 'active' : '']"
              @tap="formPaceGroup = pg"
            >
              <text class="opt-chip-text">{{ pg }}</text>
              <text v-if="formPaceGroup === pg" class="opt-chip-check">✓</text>
            </view>
          </view>
        </view>

        <view class="form-group">
          <text class="form-label">2. 选择角色</text>
          <view class="option-grid">
            <view
              v-for="rl in roleChoices"
              :key="rl"
              :class="['opt-chip', formRole === rl ? 'active' : '']"
              @tap="formRole = rl"
            >
              <text class="opt-chip-text">{{ rl }}</text>
              <text v-if="formRole === rl" class="opt-chip-check">✓</text>
            </view>
          </view>
        </view>

        <view class="form-group" v-if="activeStage === 'post' && event?.my_recent_activities && event.my_recent_activities.length">
          <text class="form-label">3. 关联手表记录（可选）</text>
          <scroll-view scroll-y class="act-pick-list">
            <view
              v-for="act in event.my_recent_activities"
              :key="act.id"
              :class="['act-pick-item', formActivityId === act.id ? 'active' : '']"
              @tap="selectRecentActivity(act)"
            >
              <view>
                <text class="act-name">{{ act.name || '跑步记录' }} ({{ act.date_label }})</text>
                <text class="act-metrics">{{ act.distance_km }}km · 配速 {{ act.avg_pace_str || '--' }} · 用时 {{ act.duration_str }}</text>
              </view>
              <text class="act-check">{{ formActivityId === act.id ? '✅' : '○' }}</text>
            </view>
          </scroll-view>
        </view>

        <view class="form-group" v-if="activeStage === 'post'">
          <text class="form-label">或手动填写完赛成绩</text>
          <view class="dual-inputs">
            <input
              v-model="formManualKm"
              type="digit"
              class="modal-input"
              placeholder="完赛距离 (如 10.5)"
            />
            <input
              v-model="formManualPace"
              class="modal-input"
              placeholder="平均配速 (如 5:15/km)"
            />
          </view>
        </view>

        <view class="form-group">
          <text class="form-label">{{ activeStage === 'post' ? '跑后感言' : '参团宣言（选填）' }}</text>
          <input
            v-model="formNote"
            class="modal-input"
            placeholder="例如：准时到！跑完一起去喝咖啡～"
          />
        </view>

        <button class="modal-submit-btn" @tap="submitJoinOrCheckin">
          {{ activeStage === 'post' ? '💾 保存完赛成绩' : (event?.is_joined ? '💾 保存分队与角色' : (!event?.is_club_member ? '🚀 入团并报名' : '🚀 确认报名')) }}
        </button>
      </view>
    </view>

    <!-- Modal 2: Group Run Poster Modal (支持 约跑前集结招募海报 & 约跑后完赛战报海报，含跑团大图与小程序码) -->
    <view v-if="showPosterModal && event" class="modal-mask" @tap="showPosterModal = false">
      <view class="poster-modal-wrap" @tap.stop>
        <!-- 海报主题切换栏 -->
        <view class="poster-mode-tabs">
          <view
            :class="['pm-tab', posterMode === 'pre' ? 'active' : '']"
            @tap="switchPosterMode('pre')"
          >
            📣 集结海报
          </view>
          <view
            :class="['pm-tab', posterMode === 'post' ? 'active' : '']"
            @tap="switchPosterMode('post')"
          >
            🏆 战报海报
          </view>
        </view>

        <!-- 高清 Canvas 生成图片预览（支持微信内直接长按识别小程序码或转发） -->
        <view v-if="posterImageUrl" class="poster-img-box">
          <image
            :src="posterImageUrl"
            class="poster-rendered-img"
            mode="widthFix"
            show-menu-by-longpress
          />
        </view>

        <!-- 生成中或兜底预览卡片（不含人员名单，突出跑团图片与小程序码） -->
        <view v-else class="poster-card">
          <view class="poster-top-badge">
            {{ posterMode === 'pre' ? '📣 万跑跑团助手 · 约跑召集令' : '🏆 万跑跑团助手 · 官方认证战报' }}
          </view>
          <view class="poster-club-row">
            <image
              v-if="event.club_logo"
              :src="event.club_logo"
              class="poster-club-logo"
              mode="aspectFill"
            />
            <text class="poster-club">🏅 {{ event.club_name || '跑团约跑' }} · {{ event.club_city || '上海' }}</text>
          </view>

          <!-- 跑团/约跑主题大图 -->
          <view class="poster-hero-img-wrap">
            <image
              :src="posterHeroImage"
              class="poster-hero-img"
              mode="aspectFill"
            />
            <view class="poster-hero-caption">
              <text class="phc-text">{{ formatPosterClubSlogan(event) }}</text>
            </view>
          </view>

          <text class="poster-title">{{ event.title }}</text>
          <text class="poster-meta">⏰ {{ formatMeetTime(event.meet_time || event.start_date) }}</text>
          <text class="poster-meta">📍 {{ event.location || '跑团指定集合点' }}</text>

          <view v-if="posterMode === 'pre'" class="poster-stats-box">
            <view class="p-stat">
              <text class="p-val accent">{{ event.target_km || 10 }} km</text>
              <text class="p-lbl">目标距离</text>
            </view>
            <view class="p-stat">
              <text class="p-val">{{ formatPosterPace(event.pace_requirement) }}</text>
              <text class="p-lbl">建议配速</text>
            </view>
            <view class="p-stat">
              <text class="p-val">{{ event.participant_count || 0 }} 人</text>
              <text class="p-lbl">已集结跑友</text>
            </view>
          </view>
          <view v-else class="poster-stats-box">
            <view class="p-stat">
              <text class="p-val">{{ socialSummary.participant_count || 0 }} 人</text>
              <text class="p-lbl">集结跑者</text>
            </view>
            <view class="p-stat">
              <text class="p-val accent">
                {{ (socialSummary.total_actual_km > 0 ? socialSummary.total_actual_km : socialSummary.total_target_km) || 0 }} km
              </text>
              <text class="p-lbl">团队总里程</text>
            </view>
            <view class="p-stat">
              <text class="p-val">{{ socialSummary.team_avg_pace_str || '--' }}</text>
              <text class="p-lbl">平均配速</text>
            </view>
          </view>

          <view class="poster-qr-bar">
            <view class="pqr-left">
              <text class="pqr-title">👉 长按图片 · 识别右侧小程序码</text>
              <text class="pqr-sub">🏃 一键报名本场约跑 · 导航集合点</text>
              <text class="pqr-sub">🎉 新人扫码直接开通万跑账号</text>
              <text class="pqr-sub">🏅 免邀请码加入【{{ event.club_name || '本跑团' }}】</text>
            </view>
            <view class="pqr-right-box" v-if="qrcodeDataUri || qrcodeUrl">
              <image :src="qrcodeDataUri || qrcodeUrl" class="pqr-img" mode="aspectFit" />
              <text class="pqr-cap">长按识别进入</text>
            </view>
          </view>
        </view>

        <!-- 海报操作区：保存相册发朋友圈 / 转发图片(长按识别) / 转发可点击小程序卡片 -->
        <view class="poster-footer">
          <text class="pf-hint">
            {{ posterGenerating ? '⏳ 海报生成中...' : '💡 长按识别小程序码即可报名' }}
          </text>
          <view class="pf-btns">
            <button class="pf-btn primary" :disabled="posterGenerating" @tap="savePosterToAlbum">
              💾 保存
            </button>
            <button class="pf-btn share" :disabled="posterGenerating" @tap="sharePosterImage">
              📲 转发
            </button>
          </view>
          <view class="pf-btns second-row">
            <button class="pf-btn card-share" open-type="share">
              📤 转发卡片
            </button>
            <button class="pf-btn ghost" @tap="copyBattleReportFromPoster">📋 复制配文</button>
            <button class="pf-btn close" @tap="showPosterModal = false">关闭</button>
          </view>
        </view>
      </view>
    </view>

    <!-- Hidden Canvas for 2x High-Res Group Run Poster Generation -->
    <canvas
      canvas-id="groupRunPosterCanvas"
      id="groupRunPosterCanvas"
      style="width: 750px; height: 1320px; position: fixed; left: -9999px; top: -9999px; pointer-events: none;"
    ></canvas>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { onLoad, onShow, onPullDownRefresh, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import {
  request,
  getStoredUser,
  authenticateWechatUser,
  silentCheckExistingWechatUser,
  setPendingInviterUid,
  setActiveClubId,
  formatBeijingTime,
} from "../../utils/api";
import { themeClass, applySystemTheme } from "../../utils/theme";
import { trackClick, trackModal, trackSubView, trackFunnelStep } from "../../utils/telemetry";
import {
  formatMeetTime,
  getCountdownText,
  addRunToCalendar,
  openRunLocation,
  isGroupRunPostStage,
  isGroupRunArchived,
  buildGroupRunSharePayload,
} from "../../utils/groupRun";

declare const wx: any;

/** 读取当前已登录用户 ID（游客态返回空串，绝不误用演示账号 runner_001） */
function getViewerUid(): string {
  const u = getStoredUser();
  if (u?.id && u.id !== "runner_001") {
    return u.id;
  }
  return "";
}

/** 报名/互动操作时确保获取真实微信用户身份：老用户自动关联既有资料，新用户一键开通账号 */
async function resolveCurrentUid(): Promise<string> {
  const existingUid = getViewerUid();
  if (existingUid) return existingUid;
  const authUser = await authenticateWechatUser();
  return authUser.id;
}

const clubId = ref("");
const eventId = ref("");
const inviterUid = ref("");
const loading = ref(true);
const joiningDirect = ref(false);
const profileIncompleteFlag = ref(false);
const event = ref<any>(null);

const isEventArchived = computed(() => isGroupRunArchived(event.value));
const showDeferredProfileTip = computed(() => {
  if (profileIncompleteFlag.value) return true;
  const vp = event.value?.viewer_profile;
  if (vp && vp.is_new_account) return true;
  const u = getStoredUser();
  const nm = (u?.display_name || "").trim();
  return !nm || nm === "微信跑者" || nm === "微信用户" || nm.startsWith("跑者_") || nm.startsWith("微信跑者_");
});

const activePaceFilter = ref("ALL");
const sortBy = ref<"distance" | "pace" | "join_order">("distance");
const copyTab = ref<"solitaire" | "battle">("solitaire");

// 阶段：pre = 约跑前（集结与分队）；post = 约跑后（完赛战报）
const activeStage = ref<"pre" | "post">("pre");
const stageFromQuery = ref<"" | "pre" | "post">("");
const isPostStage = computed(() => isGroupRunPostStage(event.value));

function switchStage(stage: "pre" | "post") {
  activeStage.value = stage;
  copyTab.value = stage === "pre" ? "solitaire" : "battle";
  trackSubView(
    `group_run_stage_${stage}`,
    stage === "pre" ? "切换至约跑集结阶段" : "切换至完赛战报阶段",
    { event_id: eventId.value }
  );
  uni.pageScrollTo({ scrollTop: 0, duration: 200 });
}

/** 约跑前：按配速列车分组展示报名名单 */
const preTrainGroups = computed(() => {
  const order = ["🚀 破风组", "⚡ 进阶组", "🏃 有氧组", "🌱 养生组"];
  const map: Record<string, any[]> = {};
  (event.value?.participants || []).forEach((p: any) => {
    const raw = String(p.pace_group || "🏃 有氧组");
    const key = order.find((o) => raw.startsWith(o)) || raw;
    (map[key] = map[key] || []).push(p);
  });
  return Object.keys(map)
    .sort((a, b) => {
      const ia = order.indexOf(a), ib = order.indexOf(b);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    })
    .map((name) => ({ name, members: map[name] }));
});

// Modals & Form state
const showCheckinModal = ref(false);
const showPosterModal = ref(false);
const posterMode = ref<"pre" | "post">("pre");
const posterImageUrl = ref("");
const posterGenerating = ref(false);
const qrcodeUrl = ref("");
const qrcodeDataUri = ref("");
const posterAssetsCache = ref<any>(null);

const paceGroupChoices = [
  "🚀 破风组 (430内)",
  "⚡ 进阶组 (430-515)",
  "🏃 有氧组 (515-600)",
  "🌱 养生组 (600+)",
];
const roleChoices = [
  "🐰 领跑兔",
  "📸 摄影担当",
  "🍉 补给担当",
  "🏃 跟跑团员",
];

const formNickname = ref("");
const formAutoJoinClub = ref(true);
const formPaceGroup = ref("🏃 有氧组 (515-600)");
const formRole = ref("🏃 跟跑团员");
const formActivityId = ref("");
const formManualKm = ref("");
const formManualPace = ref("");
const formNote = ref("");

const eventDetailMapMarkers = computed(() => {
  if (!event.value?.latitude || !event.value?.longitude) return [];
  return [
    {
      id: 1,
      latitude: Number(event.value.latitude),
      longitude: Number(event.value.longitude),
      title: event.value.location || "约跑集合点",
      width: 28,
      height: 36,
      callout: {
        content: `📍 ${event.value.location || "约跑集合点"}`,
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

const isNewAccount = computed(() => {
  if (event.value?.is_club_member || event.value?.is_joined) {
    return false;
  }
  if (event.value?.viewer_profile && typeof event.value.viewer_profile.is_new_account === "boolean") {
    return event.value.viewer_profile.is_new_account;
  }
  const u = getStoredUser();
  const name = (u?.display_name || "").trim();
  if (!name || name === "微信跑者" || name === "微信用户" || name === "跑者" || name.startsWith("跑者_") || name.startsWith("微信跑者_")) {
    return true;
  }
  return false;
});

function onNicknameBlur(e: any) {
  const val = e?.detail?.value;
  if (val && typeof val === "string" && val.trim()) {
    formNickname.value = val.trim();
  }
}

const newComment = ref("");
const quickPhrases = [
  "🔥 准时赴约，不见不散！",
  "🐰 今晚我来领跑破风！",
  "📸 我带运动相机给大家拍大片",
  "🍉 跑完一起拉伸喝冰美式！",
  "💪 状态拉满，冲个PB！",
];

const visibilityOptions = [
  { value: "registered_only", label: "🔒 仅报名团员可见" },
  { value: "club_members", label: "👥 跑团全员可见" },
  { value: "public", label: "🌐 公开战报页" },
];

const socialSummary = computed(() => event.value?.social_summary || {});

const countdownLabel = computed(() => {
  if (!event.value) return "";
  return getCountdownText(event.value.meet_time || event.value.start_date) || "火热集结中";
});

const isOngoingOrPast = computed(() => {
  return countdownLabel.value.includes("已结束") || countdownLabel.value.includes("进行中");
});

const visibilityBadge = computed(() => {
  const mode = event.value?.visibility_mode || "registered_only";
  if (mode === "registered_only") {
    return {
      icon: "🔒",
      title: "页面名单与战报：仅对报名本场约跑的团员开放",
      desc: "保护参团跑友隐私，报名后即可查看全员配速、距离与完赛战报",
    };
  }
  if (mode === "club_members") {
    return {
      icon: "👥",
      title: "页面名单与战报：对本跑团全体成员开放",
      desc: "本跑团成员均可浏览参团人员列表与跑后完赛数据",
    };
  }
  return {
    icon: "🌐",
    title: "页面名单与战报：公开战报模式",
    desc: "所有人通过分享链接均可查看本场约跑荣耀战报",
  };
});

const filteredParticipants = computed(() => {
  const list = [...(event.value?.participants || [])];
  const filtered =
    activePaceFilter.value === "ALL"
      ? list
      : list.filter((p) => p.pace_group === activePaceFilter.value);

  return filtered.sort((a, b) => {
    if (sortBy.value === "distance") {
      const diff = (Number(b.display_distance_km) || 0) - (Number(a.display_distance_km) || 0);
      if (diff !== 0) return diff;
    } else if (sortBy.value === "pace") {
      const pa = a.pace_seconds || 9999;
      const pb = b.pace_seconds || 9999;
      if (pa !== pb) return pa - pb;
    }
    return (a.join_order || 0) - (b.join_order || 0);
  });
});

async function loadEventDetail() {
  if (!eventId.value) return;
  const reqClub = clubId.value || "auto";
  loading.value = true;
  try {
    const uid = getViewerUid();
    const uidQuery = uid ? `?user_id=${encodeURIComponent(uid)}` : "";
    let detail: any = null;
    try {
      const res: any = await request(
        `/api/team/${reqClub}/events/${eventId.value}${uidQuery}`
      );
      detail = res?.event || null;
    } catch (err) {
      detail = await buildFallbackDetail(uid);
    }
    if (detail) {
      const firstLoad = !event.value;
      if (detail.club_id) {
        clubId.value = detail.club_id;
      }
      event.value = detail;
      const vpName = detail.viewer_profile?.display_name || getStoredUser()?.display_name || "";
      if (vpName && vpName !== "微信跑者" && !vpName.startsWith("跑者_")) {
        formNickname.value = vpName;
      }
      if (firstLoad) {
        const stage = detail.is_archived
          ? "post"
          : stageFromQuery.value || (isGroupRunPostStage(detail) ? "post" : "pre");
        activeStage.value = stage;
        copyTab.value = stage === "pre" ? "solitaire" : "battle";
      }
    } else if (!event.value) {
      uni.showToast({ title: "约跑不存在或已删除", icon: "none" });
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || "加载约跑详情失败", icon: "none" });
  } finally {
    loading.value = false;
    uni.stopPullDownRefresh();
  }
}

/** 兜底：基于 GET /events 列表 + 月度榜单合成详情（名单/分组/文案） */
async function buildFallbackDetail(uid: string): Promise<any | null> {
  const uidPart = uid ? `&user_id=${encodeURIComponent(uid)}` : "";
  const [evRes, lbRes]: any[] = await Promise.all([
    request(`/api/team/${clubId.value}/events?include_archived=true${uidPart}`).catch(() => null),
    request(`/api/team/${clubId.value}/leaderboard?time_range=month${uidPart}`).catch(() => null),
  ]);
  const evt = (evRes?.events || []).find((e: any) => String(e.id) === String(eventId.value));
  if (!evt) return null;
  const lbMap: Record<string, any> = {};
  (lbRes?.leaderboard || lbRes?.items || []).forEach((r: any) => { lbMap[r.user_id] = r; });
  const local = uni.getStorageSync(`gr_local_${eventId.value}`) || {};
  const participants = (evt.participants || []).map((p: any, i: number) => {
    const lb = lbMap[p.user_id] || {};
    const mine = p.user_id === uid ? local.my || {} : {};
    const done = Boolean(mine.manual_distance_km);
    return {
      ...p,
      join_order: i + 1,
      pace_group: mine.pace_group || p.pace_group || "🏃 有氧组 (515-600)",
      runner_role: mine.runner_role || p.runner_role || (p.user_id === evt.creator_id ? "🐰 领跑兔" : "🏃 跟跑团员"),
      has_completed_run: done,
      display_distance_km: done ? mine.manual_distance_km : evt.target_km || 10,
      display_pace_str: done ? mine.manual_pace_str : lb.avg_pace_str || "--",
      recent_30d_km: lb.distance_km || 0,
      data_source: done ? "manual_checkin" : "reference",
      likes_count: 0,
    };
  });
  const mine = participants.find((p: any) => p.user_id === uid) || null;
  const completed = participants.filter((p: any) => p.has_completed_run);
  const totalKm = completed.reduce((s: number, p: any) => s + Number(p.display_distance_km || 0), 0);
  const timeStr = formatMeetTime(evt.meet_time || evt.start_date);
  const names = participants.map((p: any, i: number) => `${i + 1}. ${p.display_name}  ${p.pace_group.split(" ")[0]}${p.pace_group.split(" ")[1] || ""}`).join("\n");
  return {
    ...evt,
    club_id: clubId.value,
    participants,
    is_joined: Boolean(evt.is_joined || mine),
    my_participation: mine,
    visibility_mode: local.visibility_mode || evt.visibility_mode || "registered_only",
    can_view_roster: true,
    can_manage: evt.creator_id === uid,
    comments: local.comments || [],
    completed_count: completed.length,
    social_summary: {
      participant_count: participants.length,
      completed_count: completed.length,
      completion_rate: participants.length ? Math.round((completed.length / participants.length) * 100) : 0,
      total_actual_km: Math.round(totalKm * 10) / 10,
      total_target_km: (evt.target_km || 10) * participants.length,
      team_avg_pace_str: "--",
      pace_groups_summary: [],
      share_solitaire_text: `🏃【${evt.title}】\n⏰ ${timeStr}\n📍 ${evt.location || "跑团集合点"}\n🎯 ${evt.target_km || 10}km · ${evt.pace_requirement || "配速不限"}\n\n报名接龙：\n${names || "1. "}`,
      share_battle_report_text: `🏆【${evt.title}】完赛战报\n${timeStr}\n集结 ${participants.length} 人 · 完赛 ${completed.length} 人 · 总里程 ${Math.round(totalKm * 10) / 10}km\n\n${completed.map((p: any, i: number) => `${i + 1}. ${p.display_name} ${p.display_distance_km}km ${p.display_pace_str}/km`).join("\n") || "等待队友登记成绩…"}`,
    },
  };
}

function openJoinOrCheckinModal() {
  const myPart = event.value?.my_participation;
  if (myPart) {
    formPaceGroup.value = myPart.pace_group || "🏃 有氧组 (515-600)";
    formRole.value = myPart.runner_role || "🏃 跟跑团员";
    formActivityId.value = myPart.activity_id || "";
    formManualKm.value = myPart.manual_distance_km ? String(myPart.manual_distance_km) : "";
    formManualPace.value = myPart.manual_pace_str || "";
    formNote.value = myPart.checkin_note || "";
  }
  const u = getStoredUser();
  const vpName = event.value?.viewer_profile?.display_name || u?.display_name || "";
  if (!formNickname.value && vpName && vpName !== "微信跑者" && !vpName.startsWith("跑者_")) {
    formNickname.value = vpName;
  }
  formAutoJoinClub.value = true;
  showCheckinModal.value = true;
  trackModal("group_run_checkin", "打开约跑报名/完赛打卡弹窗", "open", {
    event_id: eventId.value,
  });
}

function selectRecentActivity(act: any) {
  if (formActivityId.value === act.id) {
    formActivityId.value = "";
    return;
  }
  formActivityId.value = act.id;
  formManualKm.value = String(act.distance_km || "");
  formManualPace.value = act.avg_pace_str || "";
}

function syncLocalUserAndClub(res: any) {
  const effClub = res?.club_id || event.value?.club_id || clubId.value;
  if (effClub && effClub !== "auto") {
    clubId.value = effClub;
    setActiveClubId(effClub);
  }
  if (typeof res?.is_profile_incomplete === "boolean") {
    profileIncompleteFlag.value = res.is_profile_incomplete;
  }
  const newName = (res?.display_name || formNickname.value || "").trim();
  if (newName) {
    const stored = getStoredUser();
    if (stored) {
      stored.display_name = newName;
      uni.setStorageSync("rgm_user", stored);
    }
  }
  try {
    uni.setStorageSync("rgm_dashboard_dirty", 1);
  } catch (_) {}
}

function goToHomePage() {
  try {
    uni.setStorageSync("rgm_dashboard_dirty", 1);
  } catch (_) {}
  uni.switchTab({ url: "/pages/index/index" });
}

function goToMyProfile() {
  uni.switchTab({ url: "/pages/my/my" });
}

/**
 * 微信群邀请一键直接报名：
 * - 已有账号：自动关联既有用户资料并报名，约跑直接同步显示在用户首页
 * - 新用户：无需前置填写繁琐资料，一键直接加入跑团并报名，个人资料可后续补齐
 */
async function handleOneTapJoin() {
  if (joiningDirect.value) return;
  if (isEventArchived.value) {
    uni.showToast({ title: "该约跑活动已完成归档", icon: "none" });
    return;
  }
  joiningDirect.value = true;
  try {
    if (inviterUid.value) {
      setPendingInviterUid(inviterUid.value);
    }
    const uid = await resolveCurrentUid();
    const reqClub = clubId.value || event.value?.club_id || "auto";
    const joinRes: any = await request(`/api/team/${reqClub}/events/${eventId.value}/join`, "POST", {
      user_id: uid,
      pace_group: formPaceGroup.value,
      runner_role: formRole.value,
      display_name: formNickname.value.trim() || undefined,
      auto_join_club: true,
      join_event: true,
      inviter_uid: inviterUid.value || undefined,
    });
    trackFunnelStep("group_run_join_success", "微信群邀请一键报名约跑成功", {
      club_id: clubId.value || reqClub,
      event_id: eventId.value,
      auto_joined_club: Boolean(joinRes?.auto_joined_club),
    });
    syncLocalUserAndClub(joinRes);

    try {
      // #ifdef MP-WEIXIN
      if (typeof wx !== "undefined" && wx.requestSubscribeMessage) {
        wx.requestSubscribeMessage({
          tmplIds: ["I8K67iHNWQB0on15Z01rxKinP18DAuIPgaz7LSXIqT0"],
          complete: () => {},
        });
      }
      // #endif
    } catch (_) {}

    await loadEventDetail();
    uni.showToast({
      title: joinRes?.auto_joined_club
        ? `🎉 已入团并报名！约跑已同步至首页`
        : "🎉 报名成功！约跑已同步至首页",
      icon: "none",
      duration: 2400,
    });
  } catch (e: any) {
    uni.showToast({ title: e?.message || "报名失败，请稍后重试", icon: "none" });
  } finally {
    joiningDirect.value = false;
  }
}

async function handleQuickJoinClubOnly() {
  const uid = await resolveCurrentUid();
  const reqClub = clubId.value || event.value?.club_id || "auto";
  try {
    const res: any = await request(`/api/team/${reqClub}/events/${eventId.value}/join`, "POST", {
      user_id: uid,
      display_name: formNickname.value.trim() || undefined,
      auto_join_club: true,
      join_event: false,
      inviter_uid: inviterUid.value || undefined,
    });
    trackFunnelStep("club_join_success", "通过约跑页一键加入跑团", {
      club_id: clubId.value || reqClub,
      event_id: eventId.value,
    });
    syncLocalUserAndClub(res);
    uni.showToast({
      title: `🎉 已加入【${res?.club_name || event.value?.club_name || "跑团"}】！`,
      icon: "success",
    });
    await loadEventDetail();
  } catch (e: any) {
    uni.showToast({ title: e?.message || "加入跑团失败", icon: "none" });
  }
}

async function submitJoinOrCheckin() {
  const uid = await resolveCurrentUid();
  const reqClub = clubId.value || event.value?.club_id || "auto";
  try {
    let joinRes: any = null;
    if (!event.value?.is_joined || !event.value?.is_club_member || formNickname.value.trim()) {
      joinRes = await request(`/api/team/${reqClub}/events/${eventId.value}/join`, "POST", {
        user_id: uid,
        pace_group: formPaceGroup.value,
        runner_role: formRole.value,
        checkin_note: formNote.value,
        display_name: formNickname.value.trim() || undefined,
        auto_join_club: formAutoJoinClub.value,
        join_event: true,
        inviter_uid: inviterUid.value || undefined,
      });
      syncLocalUserAndClub(joinRes);
    }
    await request(`/api/team/${clubId.value || reqClub}/events/${eventId.value}/checkin`, "POST", {
      user_id: uid,
      pace_group: formPaceGroup.value,
      runner_role: formRole.value,
      checkin_note: formNote.value,
      activity_id: formActivityId.value || null,
      manual_distance_km: formManualKm.value ? Number(formManualKm.value) : null,
      manual_pace_str: formManualPace.value || null,
      post_to_wall: Boolean(formNote.value),
    }).catch(() => {
      const key = `gr_local_${eventId.value}`;
      const local = uni.getStorageSync(key) || {};
      local.my = {
        pace_group: formPaceGroup.value,
        runner_role: formRole.value,
        manual_distance_km: formManualKm.value ? Number(formManualKm.value) : null,
        manual_pace_str: formManualPace.value || null,
        checkin_note: formNote.value,
      };
      uni.setStorageSync(key, local);
    });
    showCheckinModal.value = false;
    trackFunnelStep("group_run_checkin_submit", "提交约跑分队/完赛成绩登记", {
      club_id: clubId.value || reqClub,
      event_id: eventId.value,
      pace_group: formPaceGroup.value,
    });
    uni.showToast({
      title: joinRes?.auto_joined_club
        ? `🎉 已加入【${joinRes.club_name || "跑团"}】并报名成功！`
        : "已更新参团名片与战报数据！",
      icon: "success",
    });
    await loadEventDetail();
  } catch (e: any) {
    uni.showToast({ title: e?.message || "操作失败", icon: "none" });
  }
}

async function handleLeaveEvent() {
  uni.showModal({
    title: "取消报名",
    content: "确定要取消本场约跑报名吗？",
    success: async (res) => {
      if (!res.confirm) return;
      try {
        const uid = await resolveCurrentUid();
        await request(`/api/team/${clubId.value}/events/${eventId.value}/leave`, "POST", {
          user_id: uid,
        });
        uni.showToast({ title: "已取消报名", icon: "none" });
        await loadEventDetail();
      } catch (e: any) {
        uni.showToast({ title: e?.message || "取消失败", icon: "none" });
      }
    },
  });
}

async function changeVisibility(mode: string) {
  if (!event.value || event.value.visibility_mode === mode) return;
  try {
    const uid = await resolveCurrentUid();
    const res: any = await request(
      `/api/team/${clubId.value}/events/${eventId.value}/visibility`,
      "POST",
      {
        operator_uid: uid,
        visibility_mode: mode,
      }
    );
    event.value.visibility_mode = mode;
    uni.showToast({ title: res?.message || "权限已更新", icon: "none" });
    await loadEventDetail();
  } catch (e: any) {
    uni.showToast({ title: e?.message || "修改失败", icon: "none" });
  }
}

async function handleHighfive(runner: any) {
  try {
    const uid = await resolveCurrentUid();
    const res: any = await request(
      `/api/team/${clubId.value}/events/${eventId.value}/highfive`,
      "POST",
      {
        from_user_id: uid,
        target_user_id: runner.user_id,
      }
    );
    runner.likes_count = res?.likes_count ?? (runner.likes_count || 0) + 1;
    trackClick("group_run_highfive", `向队友击掌：${runner.display_name || "跑友"}`, {
      event_id: eventId.value,
      target_uid: runner.user_id,
    });
    uni.showToast({ title: `👏 已向 ${runner.display_name} 击掌！`, icon: "none" });
  } catch (e) {
    uni.showToast({ title: "击掌失败", icon: "none" });
  }
}

function copyGeneratedText() {
  const isPre = activeStage.value === "pre";
  const text = isPre
    ? socialSummary.value.share_solitaire_text
    : socialSummary.value.share_battle_report_text;
  if (!text) return;
  trackClick("group_run_copy_text", isPre ? "复制约跑群接龙文案" : "复制约跑完赛战报文案", {
    event_id: eventId.value,
    stage: activeStage.value,
  });
  uni.setClipboardData({
    data: text,
    success: () => {
      uni.showToast({
        title: isPre ? "群接龙文案已复制！" : "完赛战报已复制！",
        icon: "success",
      });
    },
  });
}

function goToClubHome() {
  const cId = event.value?.club_id || clubId.value;
  if (cId && cId !== "auto") {
    setActiveClubId(cId);
  }
  uni.switchTab({
    url: "/pages/team/team",
  });
}

function writeBase64ToLocalFile(b64: string, prefix: string): string {
  if (!b64) return "";
  try {
    if (typeof wx !== "undefined" && typeof wx.getFileSystemManager === "function" && wx.env?.USER_DATA_PATH) {
      const fs = wx.getFileSystemManager();
      const safeId = String(eventId.value || "evt").replace(/[^a-zA-Z0-9_-]/g, "");
      const filePath = `${wx.env.USER_DATA_PATH}/${prefix}_v2_${safeId}.jpg`;
      fs.writeFileSync(filePath, b64, "base64");
      return filePath;
    }
  } catch (e) {
    // ignore fs error
  }
  return "";
}

async function fetchEventPosterAssets(): Promise<{ localQr: string; localCover: string; localLogo: string }> {
  if (posterAssetsCache.value) return posterAssetsCache.value;
  let localQr = "";
  let localCover = "";
  let localLogo = "";
  try {
    const reqClub = clubId.value || event.value?.club_id || "auto";
    const res: any = await request(`/api/team/${reqClub}/events/${eventId.value}/qrcode`);
    if (res?.qrcode_url) {
      qrcodeUrl.value = res.qrcode_url;
    }
    if (res?.qrcode_base64) {
      qrcodeDataUri.value = `data:image/jpeg;base64,${res.qrcode_base64}`;
      localQr = writeBase64ToLocalFile(res.qrcode_base64, "qr");
    }
    if (!localQr && res?.qrcode_url) {
      localQr = await downloadImageLocal(res.qrcode_url);
    }
    if (res?.cover_base64) {
      localCover = writeBase64ToLocalFile(res.cover_base64, "cover");
    }
    if (!localCover && (event.value?.cover_image || event.value?.club_logo)) {
      localCover = await downloadImageLocal(event.value.cover_image || event.value.club_logo);
    }
    if (res?.logo_base64) {
      localLogo = writeBase64ToLocalFile(res.logo_base64, "logo");
    }
    if (!localLogo && event.value?.club_logo) {
      localLogo = await downloadImageLocal(event.value.club_logo);
    }
  } catch (e) {
    // ignore asset error
  }
  const result = { localQr, localCover, localLogo };
  if (localQr) {
    posterAssetsCache.value = result;
  }
  return result;
}

function downloadImageLocal(url: string): Promise<string> {
  if (!url) return Promise.resolve("");
  return new Promise((resolve) => {
    uni.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode === 200 && res.tempFilePath) resolve(res.tempFilePath);
        else resolve("");
      },
      fail: () => resolve(""),
    });
  });
}

const posterHeroImage = computed(() => {
  const ev = event.value;
  if (!ev) return "";
  const cov = String(ev.cover_image || "");
  if (ev.club_logo && (!cov || cov.includes("images.unsplash.com"))) {
    return ev.club_logo;
  }
  return cov || ev.club_logo || "";
});

function formatPosterClubSlogan(ev: any): string {
  const fallback = `欢迎加入【${ev?.club_name || "万跑跑团"}】，科学训练 · 无伤畅跑！`;
  const raw = String(ev?.club_description || "").trim();
  if (!raw) return fallback;
  if (raw.length <= 26) return raw;
  const parts = raw
    .split(/[，,。；;！!\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length > 0 && parts[0].length <= 26) {
    let acc = parts[0];
    for (let i = 1; i < parts.length; i++) {
      if (acc.length + 3 + parts[i].length <= 26) {
        acc += " · " + parts[i];
      } else {
        break;
      }
    }
    return acc;
  }
  return raw.slice(0, 25) + "…";
}

function formatPosterPace(rawPace: any): string {
  const s = String(rawPace || "全配速")
    .trim()
    .replace(/\s*([-~～/、,，])\s*/g, "$1");
  return s || "全配速";
}

function getImageDimensions(src: string): Promise<{ width: number; height: number }> {
  if (!src) return Promise.resolve({ width: 0, height: 0 });
  return new Promise((resolve) => {
    uni.getImageInfo({
      src,
      success: (info) => resolve({ width: info.width || 0, height: info.height || 0 }),
      fail: () => resolve({ width: 0, height: 0 }),
    });
  });
}

function traceRoundedRect(ctx: any, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawRoundedBox(ctx: any, x: number, y: number, w: number, h: number, r: number, fill: string, stroke = "") {
  traceRoundedRect(ctx, x, y, w, h, r);
  if (fill) {
    ctx.setFillStyle(fill);
    ctx.fill();
  }
  if (stroke) {
    ctx.setStrokeStyle(stroke);
    ctx.setLineWidth(2);
    ctx.stroke();
  }
}

async function generateGroupRunPosterCanvas() {
  if (!event.value) return;
  posterGenerating.value = true;
  posterImageUrl.value = "";
  try {
    const { localQr, localCover, localLogo } = await fetchEventPosterAssets();
    const ev = event.value;
    const isPre = posterMode.value === "pre";
    const W = 750;
    const H = 1320;
    const ctx = uni.createCanvasContext("groupRunPosterCanvas");

    // 1. Background
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    bgGrad.addColorStop(0, "#0F172A");
    bgGrad.addColorStop(0.5, "#0B0D13");
    bgGrad.addColorStop(1, "#111827");
    ctx.setFillStyle(bgGrad);
    ctx.fillRect(0, 0, W, H);

    // Outer neon border
    drawRoundedBox(ctx, 24, 24, W - 48, H - 48, 32, "rgba(17,24,39,0.92)", "#D0FD3E");

    // 2. Top Badge & Club Header
    drawRoundedBox(ctx, 56, 56, isPre ? 334 : 348, 46, 23, "#D0FD3E");
    ctx.setFillStyle("#0B0D13");
    ctx.setFontSize(22);
    ctx.fillText(isPre ? "📣 万跑跑团助手 · 约跑召集令" : "🏆 万跑跑团助手 · 官方认证战报", 76, 87);

    let clubTextX = 56;
    if (localLogo) {
      const logoDim = await getImageDimensions(localLogo);
      ctx.save();
      traceRoundedRect(ctx, 56, 118, 44, 44, 22);
      ctx.clip();
      if (logoDim.width > 0 && logoDim.height > 0) {
        const lScale = Math.max(44 / logoDim.width, 44 / logoDim.height);
        const lW = Math.round(logoDim.width * lScale);
        const lH = Math.round(logoDim.height * lScale);
        ctx.drawImage(localLogo, 56 + Math.round((44 - lW) / 2), 118 + Math.round((44 - lH) / 2), lW, lH);
      } else {
        ctx.drawImage(localLogo, 56, 118, 44, 44);
      }
      ctx.restore();
      clubTextX = 112;
    }
    ctx.setFillStyle("#E2E8F0");
    ctx.setFontSize(26);
    ctx.fillText(`🏅 ${ev.club_name || "万跑跑团"} · ${ev.club_city || "上海"}`, clubTextX, 149);

    // 3. Prominent Club / Event Hero Image (跑团/约跑主题大图 - 优先展示跑团实景/主题图并按比例裁剪)
    const imgX = 56;
    const imgY = 178;
    const imgW = W - 112;
    const imgH = 400;
    drawRoundedBox(ctx, imgX, imgY, imgW, imgH, 24, "#1E293B", "rgba(208,253,62,0.4)");
    const rawCov = String(ev.cover_image || "");
    const preferClubImg = localLogo && (!rawCov || rawCov.includes("images.unsplash.com"));
    const heroSrc = preferClubImg ? localLogo : localCover || localLogo;
    if (heroSrc) {
      const heroDim = await getImageDimensions(heroSrc);
      ctx.save();
      traceRoundedRect(ctx, imgX, imgY, imgW, imgH, 24);
      ctx.clip();
      if (heroDim.width > 0 && heroDim.height > 0) {
        const scale = Math.max(imgW / heroDim.width, imgH / heroDim.height);
        const drawW = Math.round(heroDim.width * scale);
        const drawH = Math.round(heroDim.height * scale);
        const drawX = imgX + Math.round((imgW - drawW) / 2);
        const drawY = imgY + Math.round((imgH - drawH) * 0.38);
        ctx.drawImage(heroSrc, drawX, drawY, drawW, drawH);
      } else {
        ctx.drawImage(heroSrc, imgX, imgY, imgW, imgH);
      }
      // Bottom gradient overlay on the hero photo
      const imgOverlay = ctx.createLinearGradient(0, imgY + imgH - 120, 0, imgY + imgH);
      imgOverlay.addColorStop(0, "rgba(11,13,19,0)");
      imgOverlay.addColorStop(1, "rgba(11,13,19,0.90)");
      ctx.setFillStyle(imgOverlay);
      ctx.fillRect(imgX, imgY + imgH - 120, imgW, 120);
      ctx.restore();
    }
    // Club slogan inside hero photo bottom (complete clause, never truncated mid-word)
    ctx.setFillStyle("#D0FD3E");
    ctx.setFontSize(22);
    const slogan = formatPosterClubSlogan(ev);
    ctx.fillText(slogan, imgX + 24, imgY + imgH - 24);

    // 4. Event Title, Time & Location
    ctx.setFillStyle("#FFFFFF");
    ctx.setFontSize(42);
    const titleStr = String(ev.title || "跑团例跑集结").slice(0, 15);
    ctx.fillText(titleStr, 56, 636);

    ctx.setFillStyle("#CBD5E1");
    ctx.setFontSize(24);
    const timeStr = formatMeetTime(ev.meet_time || ev.start_date);
    const locStr = String(ev.location || "跑团指定集合点").slice(0, 20);
    ctx.fillText(`⏰ 集合时间：${timeStr}`, 56, 682);
    ctx.fillText(`📍 集合地点：${locStr}`, 56, 720);

    // 5. Core Metrics Box (自适应字号，完整显示建议配速如 5:30-6:00)
    drawRoundedBox(ctx, 56, 748, W - 112, 148, 24, "rgba(255,255,255,0.06)", "rgba(208,253,62,0.35)");
    const colW = (W - 112) / 3;
    const stats = isPre
      ? [
          { val: `${ev.target_km || 10} km`, lbl: "目标距离", accent: true },
          { val: formatPosterPace(ev.pace_requirement), lbl: "建议配速", accent: false },
          { val: `${ev.participant_count || 0} 人`, lbl: "已集结跑友", accent: false },
        ]
      : [
          { val: `${socialSummary.value.participant_count || 0} 人`, lbl: "集结跑者", accent: false },
          {
            val: `${(socialSummary.value.total_actual_km > 0 ? socialSummary.value.total_actual_km : socialSummary.value.total_target_km) || 0} km`,
            lbl: "团队总里程",
            accent: true,
          },
          { val: String(socialSummary.value.team_avg_pace_str || "--"), lbl: "团队均速", accent: false },
        ];
    stats.forEach((st, i) => {
      const cx = 56 + colW * i + colW / 2;
      const valStr = String(st.val || "");
      const valFontSize = valStr.length <= 7 ? 36 : valStr.length <= 10 ? 31 : valStr.length <= 13 ? 26 : 22;
      ctx.setTextAlign("center");
      ctx.setFillStyle(st.accent ? "#D0FD3E" : "#FFFFFF");
      ctx.setFontSize(valFontSize);
      ctx.fillText(valStr, cx, 814);
      ctx.setFillStyle("#94A3B8");
      ctx.setFontSize(22);
      ctx.fillText(st.lbl, cx, 860);
    });
    ctx.setTextAlign("left");

    // 6. Bottom QR Code & Newcomer Onboarding Callout (左右严格分栏，杜绝白框压字或超出底边)
    drawRoundedBox(ctx, 56, 924, W - 112, 304, 24, "rgba(208,253,62,0.10)", "#D0FD3E");
    ctx.setFillStyle("#D0FD3E");
    ctx.setFontSize(24);
    ctx.fillText("👉 长按图片 · 识别右侧小程序码", 78, 978);

    ctx.setFillStyle("#FFFFFF");
    ctx.setFontSize(21);
    ctx.fillText(isPre ? "🏃 一键报名本场约跑 · 导航集合点" : "🏆 查看本场约跑完整战报与动态", 78, 1030);
    ctx.fillText("🎉 新人扫码直接开通万跑账号", 78, 1074);
    ctx.fillText(`🏅 免邀请码加入【${String(ev.club_name || "本跑团").slice(0, 8)}】`, 78, 1118);

    ctx.setFillStyle("#94A3B8");
    ctx.setFontSize(19);
    ctx.fillText("万跑跑团助手 · Canova 马拉松科学教练", 78, 1184);

    // Right side white box with Official WeChat Mini Program Code (vertically centered in 924..1228)
    const qrBoxX = 480;
    const qrBoxY = 952;
    const qrBoxW = 192;
    const qrBoxH = 248;
    const qrCenterX = qrBoxX + qrBoxW / 2;
    drawRoundedBox(ctx, qrBoxX, qrBoxY, qrBoxW, qrBoxH, 20, "#FFFFFF");
    if (localQr) {
      ctx.drawImage(localQr, qrBoxX + 18, qrBoxY + 14, 156, 156);
    }
    ctx.setTextAlign("center");
    ctx.setFillStyle("#0B0D13");
    ctx.setFontSize(19);
    ctx.fillText("长按图片识别进入", qrCenterX, qrBoxY + 198);
    ctx.setFillStyle("#475569");
    ctx.setFontSize(16);
    ctx.fillText("报名约跑 · 自动入团", qrCenterX, qrBoxY + 224);
    ctx.setTextAlign("left");

    ctx.draw(false, () => {
      setTimeout(() => {
        uni.canvasToTempFilePath({
          canvasId: "groupRunPosterCanvas",
          destWidth: W * 2,
          destHeight: H * 2,
          fileType: "jpg",
          quality: 0.92,
          success: (res) => {
            posterImageUrl.value = res.tempFilePath;
            posterGenerating.value = false;
          },
          fail: () => {
            posterGenerating.value = false;
          },
        });
      }, 280);
    });
  } catch (e) {
    posterGenerating.value = false;
  }
}

function openPosterModal() {
  posterMode.value = activeStage.value === "post" ? "post" : "pre";
  showPosterModal.value = true;
  generateGroupRunPosterCanvas();
}

function switchPosterMode(mode: "pre" | "post") {
  if (posterMode.value === mode && posterImageUrl.value) return;
  posterMode.value = mode;
  generateGroupRunPosterCanvas();
}

function copyBattleReportFromPoster() {
  const text =
    posterMode.value === "pre"
      ? socialSummary.value.share_solitaire_text
      : socialSummary.value.share_battle_report_text || socialSummary.value.share_solitaire_text;
  if (!text) return;
  uni.setClipboardData({
    data: text,
    success: () => uni.showToast({ title: "朋友圈配文已复制！", icon: "success" }),
  });
}

function savePosterToAlbum() {
  if (!posterImageUrl.value) {
    uni.showToast({ title: "海报正在生成中，请稍候", icon: "none" });
    return;
  }
  const text =
    posterMode.value === "pre"
      ? socialSummary.value.share_solitaire_text
      : socialSummary.value.share_battle_report_text || socialSummary.value.share_solitaire_text;
  if (text) {
    uni.setClipboardData({ data: text });
  }
  uni.saveImageToPhotosAlbum({
    filePath: posterImageUrl.value,
    success: () => {
      uni.showModal({
        title: "🎉 海报已保存到手机相册",
        content: "朋友圈配文也已自动复制！现在打开微信朋友圈，从相册选择刚保存的海报并粘贴文字即可发布。",
        showCancel: false,
        confirmText: "去发朋友圈",
      });
    },
    fail: () => {
      uni.previewImage({ urls: [posterImageUrl.value] });
    },
  });
}

function sharePosterImage() {
  if (!posterImageUrl.value) {
    uni.showToast({ title: "海报正在生成中，请稍候", icon: "none" });
    return;
  }
  if (typeof wx !== "undefined" && typeof wx.showShareImageMenu === "function") {
    wx.showShareImageMenu({
      path: posterImageUrl.value,
      fail: () => {
        uni.previewImage({ urls: [posterImageUrl.value] });
      },
    });
  } else {
    uni.previewImage({ urls: [posterImageUrl.value] });
  }
}

function useQuickPhrase(phrase: string) {
  newComment.value = phrase;
  submitComment();
}

async function submitComment() {
  const text = newComment.value.trim();
  if (!text) return;
  try {
    const uid = await resolveCurrentUid();
    const res: any = await request(
      `/api/team/${clubId.value}/events/${eventId.value}/comments`,
      "POST",
      {
        user_id: uid,
        content: text,
      }
    );
    newComment.value = "";
    if (res?.comment && event.value) {
      event.value.comments = [res.comment, ...(event.value.comments || [])];
    }
    uni.showToast({ title: "留言已发布", icon: "none" });
  } catch (e: any) {
    uni.showToast({ title: e?.message || "发送失败", icon: "none" });
  }
}

function formatShortTime(isoStr: string): string {
  return formatBeijingTime(isoStr, false);
}

onShow(() => {
  applySystemTheme();
});

onLoad((query: any) => {
  applySystemTheme();
  if (typeof wx !== "undefined" && typeof wx.showShareMenu === "function") {
    wx.showShareMenu({
      withShareTicket: true,
      menus: ["shareAppMessage", "shareTimeline"],
    });
  }
  clubId.value = query?.club_id || "";
  eventId.value = query?.event_id || "";
  inviterUid.value = query?.inviter_uid || "";
  if (query?.scene) {
    const rawScene = decodeURIComponent(String(query.scene));
    rawScene.split("&").forEach((pair) => {
      const [k, v] = pair.split("=");
      if ((k === "e" || k === "event_id") && v) eventId.value = v;
      if ((k === "c" || k === "club_id") && v) clubId.value = v;
      if ((k === "u" || k === "inviter_uid") && v) inviterUid.value = v;
    });
    if (!clubId.value && eventId.value) {
      clubId.value = "auto";
    }
  }
  if (inviterUid.value) {
    setPendingInviterUid(inviterUid.value);
  }
  if (query?.stage === "pre" || query?.stage === "post") stageFromQuery.value = query.stage;

  const hadLocalUser = Boolean(getViewerUid());
  loadEventDetail().then(() => {
    if (query?.poster === "1" && event.value) {
      openPosterModal();
    }
  });

  // 若本地无登录态但微信用户已是老用户，静默识别并自动关联用户资料
  if (!hadLocalUser) {
    silentCheckExistingWechatUser().then((existingUser) => {
      if (existingUser?.id) {
        loadEventDetail();
      }
    });
  }
});

onPullDownRefresh(() => {
  loadEventDetail();
});

onShareAppMessage(() => {
  const effEvt = {
    ...(event.value || {}),
    id: eventId.value || event.value?.id,
    club_id: event.value?.club_id || clubId.value,
  };
  return buildGroupRunSharePayload(
    effEvt,
    event.value?.club_name,
    getViewerUid(),
    activeStage.value,
    posterImageUrl.value || undefined
  );
});

onShareTimeline(() => {
  const isPre = activeStage.value === "pre";
  const uid = getViewerUid();
  const inviterParam = uid ? `&inviter_uid=${encodeURIComponent(uid)}` : "";
  const effClub = event.value?.club_id || clubId.value;
  return {
    title: `${isPre ? "📣 约跑召集·新人一键入团报名" : "🏆 完赛荣耀战报"}｜【${event.value?.club_name || "万跑跑团"}】${event.value?.title || "跑团约跑"}`,
    query: `club_id=${effClub}&event_id=${eventId.value}&stage=${activeStage.value}&invite=1${inviterParam}`,
    imageUrl: posterImageUrl.value || event.value?.cover_image || undefined,
  };
});
</script>

<style scoped>
/* ── 主题色彩与表面变量（默认暗黑 + 竞技亮色模式全覆盖，杜绝背景透明穿透） ── */
.page-container {
  --rgm-bg: #0B0B0E;
  --rgm-card: #141418;
  --rgm-card-sub: #1B1B22;
  --rgm-border: rgba(255, 255, 255, 0.08);
  --rgm-text: #F4F4F6;
  --rgm-text-sub: #A1A1AA;
  --rgm-accent: #FC4C02;
  --rgm-accent-fg: #FFFFFF;

  min-height: 100vh;
  background-color: var(--rgm-bg);
  color: var(--rgm-text);
  padding: 24rpx 28rpx calc(140rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(140rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
}

.page-container.theme-volt {
  --rgm-bg: #F6F8FA;
  --rgm-card: #FFFFFF;
  --rgm-card-sub: #F8FAFC;
  --rgm-border: #E2E8F0;
  --rgm-text: #0F172A;
  --rgm-text-sub: #475569;
  --rgm-accent: #FC4C02;
  --rgm-accent-fg: #FFFFFF;
}

.page-container.theme-volt .stage-tab.active,
.page-container.theme-volt .bab-btn.primary,
.page-container.theme-volt .join-cta-btn,
.page-container.theme-volt .opt-chip.active,
.page-container.theme-volt .modal-submit-btn,
.page-container.theme-volt .ncc-btn.primary {
  background: linear-gradient(135deg, #FC4C02 0%, #EA580C 100%);
  color: #FFFFFF;
  border-color: #FC4C02;
  box-shadow: 0 6rpx 18rpx rgba(252, 76, 2, 0.22);
}

.page-container.theme-volt .stage-tab.active .stage-step,
.page-container.theme-volt .stage-tab.active .stage-name,
.page-container.theme-volt .stage-tab.active .stage-hint,
.page-container.theme-volt .ssl-num {
  color: #FFFFFF;
}

.page-container.theme-volt .tg-count,
.page-container.theme-volt .jb-tag.role,
.page-container.theme-volt .jb-edit-btn,
.page-container.theme-volt .role-badge,
.page-container.theme-volt .act-pick-item.active {
  background: #FFF5EE;
  border-color: rgba(252, 76, 2, 0.32);
  color: #C23800;
}

/* ── 阶段导航（吸顶） ── */
.stage-nav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 10rpx;
  padding: 12rpx;
  margin: 0 0 24rpx;
  border-radius: 24rpx;
  background: var(--rgm-card, #141418);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.12));
  box-shadow: 0 10rpx 28rpx rgba(0, 0, 0, 0.32);
}
.stage-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16rpx 20rpx;
  border-radius: 18rpx;
  background: var(--rgm-card-sub, #1B1B22);
  border: 1px solid transparent;
  opacity: 0.78;
}
.stage-tab.active {
  opacity: 1;
  background: linear-gradient(135deg, #FC4C02 0%, #FF6B2B 100%);
  box-shadow: 0 6rpx 18rpx rgba(252, 76, 2, 0.22);
}
.stage-tab.active .stage-step,
.stage-tab.active .stage-name,
.stage-tab.active .stage-hint {
  color: #FFFFFF;
}
.stage-step { font-size: 18rpx; font-weight: 700; letter-spacing: 1rpx; color: var(--rgm-text-sub, #94a3b8); }
.stage-name { font-size: 28rpx; font-weight: 800; color: var(--rgm-text, #f8fafc); margin: 4rpx 0; white-space: nowrap; }
.stage-hint { font-size: 20rpx; color: var(--rgm-text-sub, #94a3b8); }
.stage-arrow { font-size: 32rpx; color: var(--rgm-text-sub, #94a3b8); padding: 0 2rpx; }

/* ── 编号分节标题 ── */
.stage-sec-label {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin: 12rpx 4rpx 14rpx;
}
.ssl-num {
  width: 38rpx;
  height: 38rpx;
  line-height: 38rpx;
  text-align: center;
  border-radius: 50%;
  font-size: 21rpx;
  font-weight: 800;
  background: var(--rgm-accent, #FC4C02);
  color: #FFFFFF;
}
.ssl-text { font-size: 27rpx; font-weight: 800; color: var(--rgm-text, #f8fafc); }

/* ── 约跑前快捷操作 ── */
.pre-quick-row { display: flex; gap: 14rpx; margin-top: 18rpx; }
.pre-quick-btn {
  flex: 1;
  text-align: center;
  padding: 16rpx 8rpx;
  border-radius: 16rpx;
  font-size: 23rpx;
  font-weight: 600;
  background: var(--rgm-card-sub, #1B1B22);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.11));
  color: var(--rgm-text, #f8fafc);
}

/* ── 配速列车分组名单 ── */
.train-group { padding: 18rpx 0; border-bottom: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.1)); }
.train-group:last-child { border-bottom: none; padding-bottom: 4rpx; }
.tg-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14rpx; }
.tg-name { font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #f8fafc); }
.tg-count { font-size: 22rpx; font-weight: 600; color: var(--rgm-accent, #FC4C02); background: rgba(252, 76, 2, 0.14); padding: 2rpx 14rpx; border-radius: 999rpx; }
.tg-members { display: flex; flex-direction: column; gap: 14rpx; }
.tg-member {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 14rpx 16rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-sub, #1B1B22);
}
.tg-avatar { width: 60rpx; height: 60rpx; border-radius: 50%; flex-shrink: 0; }
.tg-avatar-fb {
  display: flex; align-items: center; justify-content: center;
  background: #334155; color: #fff; font-size: 24rpx; font-weight: 700;
}
.tg-meta { display: flex; flex-direction: column; gap: 4rpx; overflow: hidden; }
.tg-mname { font-size: 26rpx; font-weight: 700; color: var(--rgm-text, #f8fafc); }
.tg-msub { font-size: 21rpx; color: var(--rgm-text-sub, #94a3b8); }

/* ── 约跑后未开跑提示 ── */
.post-locked-tip {
  display: flex;
  gap: 12rpx;
  padding: 18rpx 20rpx;
  margin-bottom: 20rpx;
  border-radius: 16rpx;
  background: rgba(250, 204, 21, 0.12);
  border: 1px solid rgba(250, 204, 21, 0.35);
}
.plt-icon { font-size: 28rpx; }
.plt-text { flex: 1; font-size: 22rpx; line-height: 1.5; color: var(--rgm-text, #f8fafc); }

/* ── 底部固定操作栏 ── */
.bottom-bar-spacer { height: 150rpx; }
.bottom-action-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: flex;
  gap: 14rpx;
  padding: 18rpx 24rpx calc(18rpx + env(safe-area-inset-bottom));
  background: var(--rgm-card, #141418);
  border-top: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.12));
  box-shadow: 0 -10rpx 32rpx rgba(0, 0, 0, 0.45);
}
.bab-btn {
  flex: 1;
  min-width: 0;
  margin: 0;
  height: 84rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 20rpx;
  font-size: 25rpx;
  font-weight: 700;
  padding: 0 12rpx;
  white-space: nowrap;
}
.bab-btn::after { border: none; }
.bab-btn.ghost {
  background: var(--rgm-card-sub, #1B1B22);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text, #f8fafc);
}
.bab-btn.primary {
  flex: 1.5;
  background: linear-gradient(135deg, #FC4C02 0%, #FF6B2B 100%);
  color: #FFFFFF;
  font-weight: 800;
  box-shadow: 0 6rpx 20rpx rgba(252, 76, 2, 0.25);
}

.loading-box {
  padding: 120rpx 32rpx;
  text-align: center;
}
.loading-text {
  color: var(--rgm-text-sub);
  font-size: 28rpx;
}

/* 1. Hero Card */
.hero-card {
  position: relative;
  border-radius: 28rpx;
  overflow: hidden;
  margin-bottom: 24rpx;
  border: 1px solid var(--rgm-border);
  background: var(--rgm-card);
}
.hero-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0.32;
}
.hero-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, rgba(11, 13, 19, 0.45) 0%, rgba(11, 13, 19, 0.92) 100%);
}
.hero-content {
  position: relative;
  z-index: 2;
  padding: 30rpx 28rpx;
  color: #ffffff;
}
.hero-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.club-pill {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  padding: 6rpx 18rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.14);
  font-size: 22rpx;
}
.status-pill {
  padding: 6rpx 18rpx;
  border-radius: 999rpx;
  font-size: 22rpx;
  font-weight: 600;
  background: rgba(208, 253, 62, 0.2);
  color: #FC4C02;
}
.hero-title {
  display: block;
  font-size: 40rpx;
  font-weight: 800;
  margin-bottom: 20rpx;
  line-height: 1.3;
}
.hero-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
  background: rgba(255, 255, 255, 0.08);
  padding: 18rpx 20rpx;
  border-radius: 18rpx;
  margin-bottom: 20rpx;
}
.meta-label {
  display: block;
  font-size: 20rpx;
  color: rgba(255, 255, 255, 0.65);
  margin-bottom: 6rpx;
}
.meta-val {
  font-size: 24rpx;
  font-weight: 600;
  color: #ffffff;
}
.meta-val.link {
  color: #FC4C02;
}
.hero-Specs-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 22rpx;
}
.spec-badge {
  padding: 6rpx 16rpx;
  border-radius: 10rpx;
  font-size: 22rpx;
  background: rgba(255, 255, 255, 0.12);
  color: #f1f5f9;
}
.spec-badge.accent {
  background: #FC4C02;
  color: #FFFFFF;
  font-weight: 700;
}
.hero-organizer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16rpx;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}
.org-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.org-avatar,
.org-avatar-fallback {
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  background: #334155;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  font-weight: 700;
}
.org-text {
  font-size: 22rpx;
  color: rgba(255, 255, 255, 0.85);
}
.hero-quick-btns {
  display: flex;
  gap: 12rpx;
}
.mini-Quick-btn {
  padding: 8rpx 18rpx;
  border-radius: 999rpx;
  font-size: 22rpx;
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
}
.mini-Quick-btn.primary {
  background: #FC4C02;
  color: #FFFFFF;
  font-weight: 700;
}

/* 2. Visibility Card */
.visibility-card {
  background: var(--rgm-card);
  border: 1px solid var(--rgm-border);
  border-radius: 22rpx;
  padding: 22rpx 24rpx;
  margin-bottom: 24rpx;
}
.vis-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12rpx;
}
.vis-title-row {
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
  flex: 1;
}
.vis-icon {
  font-size: 34rpx;
}
.vis-title {
  display: block;
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text);
}
.vis-switch-bar {
  display: flex;
  gap: 12rpx;
  margin-top: 18rpx;
}
.vis-opt-pill {
  flex: 1;
  text-align: center;
  padding: 12rpx 8rpx;
  border-radius: 14rpx;
  font-size: 22rpx;
  background: var(--rgm-card-sub);
  color: var(--rgm-text-sub);
  border: 1px solid var(--rgm-border);
}
.vis-opt-pill.active {
  background: var(--rgm-accent);
  color: var(--rgm-accent-fg);
  font-weight: 700;
  border-color: var(--rgm-accent);
}

/* 3. Locked View */
.locked-roster-card {
  background: var(--rgm-card);
  border: 1px solid var(--rgm-border);
  border-radius: 24rpx;
  padding: 48rpx 32rpx;
  text-align: center;
  margin-bottom: 24rpx;
}
.lock-icon-circle {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  background: var(--rgm-card-sub);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 46rpx;
  margin: 0 auto 20rpx;
}
.lock-title {
  display: block;
  font-size: 32rpx;
  font-weight: 800;
  margin-bottom: 12rpx;
}
.lock-subtitle {
  display: block;
  font-size: 24rpx;
  color: var(--rgm-text-sub);
  line-height: 1.6;
  margin-bottom: 28rpx;
}
.masked-avatars-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 14rpx;
  margin-bottom: 32rpx;
}
.masked-user-chip {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-sub);
  font-size: 22rpx;
}
.masked-avatar {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background: var(--rgm-accent);
  color: var(--rgm-accent-fg);
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20rpx;
}
.masked-group {
  color: var(--rgm-text-sub);
  font-size: 20rpx;
}
.unlock-join-btn {
  background: var(--rgm-accent);
  color: var(--rgm-accent-fg);
  font-weight: 800;
  font-size: 28rpx;
  border-radius: 999rpx;
  padding: 10rpx 32rpx;
}

/* 4A. My Participation Card */
.my-status-card {
  background: var(--rgm-card, #141418);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.11));
  border-radius: 24rpx;
  padding: 26rpx 24rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.22);
}
.not-joined-box {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20rpx;
}
.nj-title {
  display: block;
  font-size: 28rpx;
  font-weight: 700;
  margin-bottom: 6rpx;
}
.join-cta-btn {
  background: linear-gradient(135deg, #FC4C02 0%, #FF6B2B 100%);
  color: #FFFFFF;
  font-size: 26rpx;
  font-weight: 800;
  border-radius: 999rpx;
  padding: 6rpx 30rpx;
  white-space: nowrap;
}
.join-cta-btn::after {
  border: none;
}
.jb-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
  flex-wrap: wrap;
  gap: 12rpx;
}
.jb-left {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-wrap: wrap;
}
.jb-badge {
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  background: rgba(16, 185, 129, 0.18);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #10b981;
  font-size: 22rpx;
  font-weight: 700;
}
.jb-tag {
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-sub, #1B1B22);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.1));
  font-size: 22rpx;
  font-weight: 600;
  color: var(--rgm-text, #f8fafc);
}
.jb-tag.role {
  background: rgba(208, 253, 62, 0.14);
  border-color: rgba(208, 253, 62, 0.35);
  color: var(--rgm-accent, #FC4C02);
  font-weight: 700;
}
.jb-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.jb-edit-btn {
  font-size: 22rpx;
  color: var(--rgm-accent, #FC4C02);
  font-weight: 700;
  padding: 6rpx 18rpx;
  border-radius: 999rpx;
  background: rgba(252, 76, 2, 0.14);
  border: 1px solid rgba(208, 253, 62, 0.35);
}
.jb-leave-btn {
  font-size: 22rpx;
  color: var(--rgm-text-sub, #94a3b8);
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-sub, #1B1B22);
}
.jb-stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
  background: var(--rgm-card-sub);
  padding: 16rpx;
  border-radius: 16rpx;
}
.jb-stat-lbl {
  display: block;
  font-size: 20rpx;
  color: var(--rgm-text-sub);
  margin-bottom: 4rpx;
}
.jb-stat-val {
  font-size: 24rpx;
  font-weight: 700;
}
.jb-stat-val.highlight,
.jb-stat-val.link {
  color: var(--rgm-accent);
}

/* 4B. Summary Card */
.summary-card,
.roster-card,
.generator-card,
.comments-card {
  background: var(--rgm-card);
  border: 1px solid var(--rgm-border);
  border-radius: 24rpx;
  padding: 26rpx 24rpx;
  margin-bottom: 24rpx;
}
.sec-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}
.sec-title {
  display: block;
  font-size: 30rpx;
  font-weight: 800;
}
.team-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
  margin-bottom: 20rpx;
}
.kpi-box {
  background: var(--rgm-card-sub);
  padding: 18rpx 12rpx;
  border-radius: 16rpx;
  text-align: center;
}
.kpi-num {
  display: block;
  font-size: 32rpx;
  font-weight: 800;
}
.kpi-num.accent {
  color: var(--rgm-accent);
}
.kpi-unit {
  font-size: 20rpx;
  margin-left: 2rpx;
}
.kpi-label {
  display: block;
  font-size: 20rpx;
  color: var(--rgm-text-sub);
  margin-top: 6rpx;
}
.mvp-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
}
.mvp-chip {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: var(--rgm-card-sub);
  border: 1px solid var(--rgm-border);
  border-radius: 16rpx;
  padding: 14rpx 12rpx;
}
.mvp-icon {
  font-size: 34rpx;
}
.mvp-tag {
  display: block;
  font-size: 18rpx;
  color: var(--rgm-text-sub);
}
.mvp-name {
  display: block;
  font-size: 24rpx;
  font-weight: 700;
}
.mvp-val {
  display: block;
  font-size: 20rpx;
  color: var(--rgm-accent);
  font-weight: 600;
}

/* 4C. Roster */
.pace-train-scroll {
  white-space: nowrap;
  margin-bottom: 18rpx;
}
.pace-train-row {
  display: inline-flex;
  gap: 12rpx;
}
.train-chip {
  padding: 10rpx 22rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-sub);
  color: var(--rgm-text-sub);
  font-size: 22rpx;
  border: 1px solid var(--rgm-border);
}
.train-chip.active {
  background: var(--rgm-accent);
  color: var(--rgm-accent-fg);
  font-weight: 700;
  border-color: var(--rgm-accent);
}
.roster-sort-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
}
.sort-label {
  font-size: 22rpx;
  color: var(--rgm-text-sub);
}
.sort-pills {
  display: flex;
  gap: 12rpx;
}
.sort-pill {
  font-size: 22rpx;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-sub);
  color: var(--rgm-text-sub);
}
.sort-pill.active {
  background: var(--rgm-accent);
  color: var(--rgm-accent-fg);
  font-weight: 700;
}
.roster-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.runner-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  padding: 20rpx;
  border-radius: 20rpx;
  background: var(--rgm-card-sub);
  border: 1px solid var(--rgm-border);
}
.runner-rank {
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: var(--rgm-card);
  color: var(--rgm-text-sub);
  font-size: 22rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 6rpx;
}
.runner-rank.top-1 {
  background: #f59e0b;
  color: #ffffff;
}
.runner-rank.top-2 {
  background: #94a3b8;
  color: #ffffff;
}
.runner-rank.top-3 {
  background: #d97706;
  color: #ffffff;
}
.runner-avatar,
.runner-avatar-fallback {
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  background: var(--rgm-card);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  font-weight: 700;
  flex-shrink: 0;
}
.runner-main {
  flex: 1;
  min-width: 0;
}
.runner-name-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 8rpx;
}
.runner-name {
  font-size: 28rpx;
  font-weight: 800;
}
.role-badge {
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
  background: rgba(208, 253, 62, 0.16);
  color: var(--rgm-accent);
  font-weight: 600;
}
.group-badge {
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
  background: var(--rgm-card);
  color: var(--rgm-text-sub);
}
.runner-badges-line {
  display: flex;
  gap: 8rpx;
  margin-bottom: 10rpx;
}
.honor-tag {
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(245, 158, 11, 0.18);
  color: #f59e0b;
  font-weight: 700;
}
.runner-metrics-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
  padding: 12rpx 16rpx;
  border-radius: 14rpx;
  background: var(--rgm-card);
  margin-bottom: 10rpx;
}
.m-lbl {
  display: block;
  font-size: 18rpx;
  color: var(--rgm-text-sub);
}
.m-val {
  font-size: 26rpx;
  font-weight: 800;
}
.m-val.highlight {
  color: var(--rgm-accent);
}
.m-unit {
  font-size: 18rpx;
  font-weight: 500;
  margin-left: 2rpx;
}
.runner-source-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12rpx;
}
.source-tag {
  font-size: 20rpx;
  color: var(--rgm-text-sub);
}
.source-tag.watch_sync {
  color: #10b981;
  font-weight: 600;
}
.runner-note {
  font-size: 22rpx;
  color: var(--rgm-text);
  font-style: italic;
}
.highfive-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 10rpx 14rpx;
  border-radius: 16rpx;
  background: var(--rgm-card);
  border: 1px solid var(--rgm-border);
  flex-shrink: 0;
}
.hf-emoji {
  font-size: 28rpx;
}
.hf-count {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-accent);
}

/* 4D. Generator Card */
.gen-tab-row {
  display: flex;
  gap: 12rpx;
  margin-bottom: 16rpx;
}
.gen-tab {
  flex: 1;
  text-align: center;
  padding: 14rpx;
  border-radius: 14rpx;
  background: var(--rgm-card-sub);
  color: var(--rgm-text-sub);
  font-size: 24rpx;
  font-weight: 600;
}
.gen-tab.active {
  background: var(--rgm-accent);
  color: var(--rgm-accent-fg);
  font-weight: 700;
}
.copy-preview-box {
  background: var(--rgm-card-sub);
  border: 1px dashed var(--rgm-border);
  border-radius: 16rpx;
  padding: 20rpx;
  margin-bottom: 18rpx;
  max-height: 320rpx;
  overflow-y: auto;
}
.copy-preview-text {
  font-size: 23rpx;
  line-height: 1.65;
  white-space: pre-wrap;
  color: var(--rgm-text);
}
.gen-btn-row {
  display: flex;
  gap: 16rpx;
}
.gen-action-btn {
  flex: 1;
  font-size: 25rpx;
  font-weight: 700;
  border-radius: 999rpx;
  background: var(--rgm-card-sub);
  color: var(--rgm-text);
  border: 1px solid var(--rgm-border);
}
.gen-action-btn.accent {
  background: var(--rgm-accent);
  color: var(--rgm-accent-fg);
  border-color: var(--rgm-accent);
}

/* 4E. Comments Wall */
.quick-phrases-scroll {
  white-space: nowrap;
  margin-bottom: 16rpx;
}
.quick-phrases-row {
  display: inline-flex;
  gap: 12rpx;
}
.phrase-chip {
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-sub);
  font-size: 22rpx;
  color: var(--rgm-text-sub);
  border: 1px solid var(--rgm-border);
}
.comment-input-row {
  display: flex;
  gap: 12rpx;
  margin-bottom: 20rpx;
}
.comment-input {
  flex: 1;
  height: 72rpx;
  padding: 0 22rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-sub);
  color: var(--rgm-text);
  font-size: 24rpx;
}
.comment-send-btn {
  height: 72rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 32rpx;
  white-space: nowrap;
  border-radius: 999rpx;
  background: var(--rgm-accent);
  color: var(--rgm-accent-fg);
  font-size: 24rpx;
  font-weight: 700;
}
.comment-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.comment-item {
  display: flex;
  gap: 14rpx;
  padding: 16rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-sub);
}
.c-avatar {
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  background: var(--rgm-card);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  font-weight: 700;
  flex-shrink: 0;
}
.c-body {
  flex: 1;
}
.c-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6rpx;
}
.c-name {
  font-size: 24rpx;
  font-weight: 700;
}
.c-time {
  font-size: 20rpx;
  color: var(--rgm-text-sub);
}
.c-text {
  font-size: 24rpx;
  line-height: 1.5;
}
.empty-comment-hint {
  text-align: center;
  padding: 24rpx;
  font-size: 23rpx;
  color: var(--rgm-text-sub);
}

/* Modals */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(5, 7, 13, 0.85);
  backdrop-filter: blur(10px);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28rpx;
}
.modal-panel {
  width: 100%;
  max-height: 86vh;
  overflow-y: auto;
  background: var(--rgm-card, #141418);
  border: 1.5px solid rgba(208, 253, 62, 0.35);
  border-radius: 32rpx;
  padding: 36rpx 30rpx;
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.78);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 26rpx;
  padding-bottom: 20rpx;
  border-bottom: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.1));
}
.modal-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  flex: 1;
}
.modal-title {
  font-size: 32rpx;
  font-weight: 800;
  color: var(--rgm-text, #f8fafc);
}
.modal-subtitle {
  font-size: 22rpx;
  color: var(--rgm-text-sub, #94a3b8);
}
.modal-close-btn {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  background: var(--rgm-card-sub, #1B1B22);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.12));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
  color: var(--rgm-text-sub, #94a3b8);
  flex-shrink: 0;
  margin-left: 16rpx;
}
.form-group {
  margin-bottom: 26rpx;
}
.form-label {
  display: block;
  font-size: 25rpx;
  font-weight: 800;
  color: var(--rgm-text, #f8fafc);
  margin-bottom: 14rpx;
}
.option-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14rpx;
}
.opt-chip {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 18rpx;
  border-radius: 18rpx;
  background: var(--rgm-card-sub, #1B1B22);
  border: 2rpx solid var(--rgm-border, rgba(255, 255, 255, 0.12));
  font-size: 23rpx;
  font-weight: 600;
  color: var(--rgm-text, #f8fafc);
}
.opt-chip-text {
  flex: 1;
  line-height: 1.35;
}
.opt-chip-check {
  width: 34rpx;
  height: 34rpx;
  border-radius: 50%;
  background: #0b0d13;
  color: #FC4C02;
  font-size: 20rpx;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-left: 8rpx;
}
.opt-chip.active {
  background: linear-gradient(135deg, #FC4C02 0%, #FF6B2B 100%);
  color: #FFFFFF;
  font-weight: 800;
  border-color: #FC4C02;
  box-shadow: 0 6rpx 18rpx rgba(208, 253, 62, 0.24);
}
.act-pick-list {
  max-height: 240rpx;
}
.act-pick-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 20rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-sub, #1B1B22);
  border: 1.5px solid var(--rgm-border, rgba(255, 255, 255, 0.12));
  margin-bottom: 12rpx;
}
.act-pick-item.active {
  border-color: var(--rgm-accent, #FC4C02);
  background: rgba(208, 253, 62, 0.1);
}
.act-name {
  display: block;
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #f8fafc);
}
.act-metrics {
  display: block;
  font-size: 21rpx;
  color: var(--rgm-text-sub, #94a3b8);
  margin-top: 4rpx;
}
.dual-inputs {
  display: flex;
  gap: 14rpx;
}
.modal-input {
  width: 100%;
  flex: 1;
  height: 82rpx;
  padding: 0 22rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-sub, #1B1B22);
  border: 1.5px solid var(--rgm-border, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text, #f8fafc);
  font-size: 25rpx;
}
.modal-submit-btn {
  width: 100%;
  height: 88rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24rpx;
  white-space: nowrap;
  background: linear-gradient(135deg, #FC4C02 0%, #FF6B2B 100%);
  color: #FFFFFF;
  font-size: 28rpx;
  font-weight: 800;
  border-radius: 999rpx;
  margin-top: 16rpx;
  box-shadow: 0 10rpx 28rpx rgba(208, 253, 62, 0.28);
}
.modal-submit-btn::after {
  border: none;
}

/* Poster Modal */
.poster-card {
  width: 100%;
  background: linear-gradient(160deg, #111827 0%, #0b0d13 100%);
  color: #ffffff;
  border: 2px solid #FC4C02;
  border-radius: 32rpx;
  padding: 36rpx 30rpx;
}
.poster-top-badge {
  display: inline-block;
  padding: 6rpx 18rpx;
  border-radius: 999rpx;
  background: #FC4C02;
  color: #FFFFFF;
  font-size: 20rpx;
  font-weight: 800;
  margin-bottom: 14rpx;
}
.poster-club {
  display: block;
  font-size: 24rpx;
  color: #94a3b8;
}
.poster-title {
  display: block;
  font-size: 38rpx;
  font-weight: 900;
  margin: 8rpx 0;
}
.poster-meta {
  display: block;
  font-size: 22rpx;
  color: #cbd5e1;
  margin-bottom: 24rpx;
}
.poster-stats-box {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  background: rgba(255, 255, 255, 0.07);
  padding: 20rpx;
  border-radius: 20rpx;
  text-align: center;
  margin-bottom: 24rpx;
}
.p-val {
  display: block;
  font-size: 34rpx;
  font-weight: 900;
}
.p-val.accent {
  color: #FC4C02;
}
.p-lbl {
  font-size: 20rpx;
  color: #94a3b8;
}
.poster-roster-preview {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 18rpx;
  padding: 18rpx 20rpx;
  margin-bottom: 24rpx;
}
.pr-header {
  display: block;
  font-size: 22rpx;
  font-weight: 700;
  color: #FC4C02;
  margin-bottom: 12rpx;
}
.pr-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 22rpx;
  padding: 8rpx 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.pr-rank {
  color: #FC4C02;
  font-weight: 700;
  width: 48rpx;
}
.pr-name {
  flex: 1;
  font-weight: 600;
}
.pr-role {
  color: #94a3b8;
  margin-right: 16rpx;
}
.pr-data {
  font-weight: 700;
}
.pf-hint {
  display: block;
  text-align: center;
  font-size: 21rpx;
  color: #cbd5e1;
  margin-bottom: 14rpx;
}
.pf-btns {
  display: flex;
  gap: 14rpx;
}
.pf-btns.second-row {
  margin-top: 12rpx;
}
.pf-btn {
  flex: 1;
  min-width: 0;
  height: 76rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 12rpx;
  white-space: nowrap;
  background: #FC4C02;
  color: #FFFFFF;
  font-size: 24rpx;
  font-weight: 800;
  border-radius: 999rpx;
}
.pf-btn.share {
  background: #22c55e;
  color: #ffffff;
}
.pf-btn.ghost {
  background: rgba(255, 255, 255, 0.12);
  color: #e2e8f0;
  border: 1px solid rgba(255, 255, 255, 0.22);
}
.pf-btn.close {
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
}

/* Hero Poster Button */
.hero-poster-btn {
  padding: 10rpx 22rpx;
  border-radius: 999rpx;
  background: rgba(208, 253, 62, 0.2);
  border: 1px solid #FC4C02;
  color: #FC4C02;
  font-size: 22rpx;
  font-weight: 800;
}
.pre-quick-btn.accent {
  border-color: var(--rgm-accent);
  color: var(--rgm-accent);
  font-weight: 700;
}

/* Newcomer Onboarding & Auto-Join Club Card */
.newcomer-club-card {
  margin-bottom: 24rpx;
  padding: 26rpx 28rpx;
  border-radius: 26rpx;
  background: linear-gradient(135deg, rgba(208, 253, 62, 0.16) 0%, var(--rgm-card, #141418) 100%);
  border: 1.5px solid var(--rgm-accent, #FC4C02);
}
.ncc-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}
.ncc-badge {
  display: inline-block;
  padding: 4rpx 16rpx;
  border-radius: 999rpx;
  background: var(--rgm-accent, #FC4C02);
  color: var(--rgm-accent-fg, #0b0d13);
  font-size: 20rpx;
  font-weight: 800;
}
.ncc-city {
  font-size: 22rpx;
  color: var(--rgm-text-sub, #94a3b8);
}
.ncc-title {
  display: block;
  font-size: 30rpx;
  font-weight: 900;
  color: var(--rgm-text, #f8fafc);
  margin-bottom: 8rpx;
}
.ncc-actions {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}
.ncc-btn {
  width: 100%;
  height: 78rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 20rpx;
  white-space: nowrap;
  border-radius: 999rpx;
  font-size: 25rpx;
  font-weight: 800;
}
.ncc-btn::after {
  border: none;
}
.ncc-btn.primary {
  background: linear-gradient(135deg, #FC4C02 0%, #FF6B2B 100%);
  color: #FFFFFF;
}
.ncc-btn.ghost {
  background: var(--rgm-card-sub, #1B1B22);
  color: var(--rgm-text, #f8fafc);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.14));
  font-size: 23rpx;
}

/* Newcomer Section inside Modal 1 */
.newcomer-modal-box {
  margin-bottom: 24rpx;
  padding: 20rpx 22rpx;
  border-radius: 20rpx;
  background: var(--rgm-card-sub, #1B1B22);
  border: 1px solid rgba(208, 253, 62, 0.45);
}
.nmb-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14rpx;
}
.nmb-badge {
  font-size: 23rpx;
  font-weight: 800;
  color: var(--rgm-accent, #FC4C02);
}
.nmb-input-row {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 14rpx;
}
.nmb-lbl {
  font-size: 24rpx;
  font-weight: 700;
  white-space: nowrap;
  color: var(--rgm-text, #f8fafc);
}
.nmb-input {
  flex: 1;
  height: 68rpx;
  padding: 0 18rpx;
  border-radius: 12rpx;
  background: var(--rgm-card, #141418);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text, #f8fafc);
  font-size: 24rpx;
}
.nmb-club-toggle {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  padding-top: 12rpx;
  border-top: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.1));
}
.nmb-check {
  font-size: 28rpx;
  line-height: 1.2;
}
.nmb-club-info {
  flex: 1;
}
.nmb-club-title {
  display: block;
  font-size: 23rpx;
  font-weight: 700;
  color: var(--rgm-text);
}

/* Poster Modal Wrap & Tabs */
.poster-modal-wrap {
  width: 100%;
  max-height: 92vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.poster-mode-tabs {
  display: flex;
  gap: 12rpx;
  background: rgba(15, 23, 42, 0.9);
  padding: 8rpx;
  border-radius: 999rpx;
  border: 1px solid rgba(255, 255, 255, 0.16);
}
.pm-tab {
  flex: 1;
  text-align: center;
  padding: 14rpx 12rpx;
  border-radius: 999rpx;
  font-size: 23rpx;
  font-weight: 700;
  color: #cbd5e1;
}
.pm-tab.active {
  background: #FC4C02;
  color: #FFFFFF;
  font-weight: 900;
}
.poster-img-box {
  width: 100%;
  border-radius: 28rpx;
  overflow: hidden;
  border: 2px solid #FC4C02;
  background: #0b0d13;
}
.poster-rendered-img {
  width: 100%;
  display: block;
}
.poster-qr-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
  padding: 18rpx 20rpx;
  border-radius: 20rpx;
  background: rgba(252, 76, 2, 0.14);
  border: 1px solid rgba(208, 253, 62, 0.45);
}
.pqr-left {
  flex: 1;
}
.pqr-title {
  display: block;
  font-size: 24rpx;
  font-weight: 800;
  color: #FC4C02;
  margin-bottom: 6rpx;
}
.pqr-sub {
  display: block;
  font-size: 20rpx;
  color: #e2e8f0;
  line-height: 1.4;
}
.pqr-right-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
  flex-shrink: 0;
}
.pqr-img {
  width: 124rpx;
  height: 124rpx;
  border-radius: 16rpx;
  background: #ffffff;
  padding: 6rpx;
  flex-shrink: 0;
}
.pqr-cap {
  font-size: 18rpx;
  font-weight: 800;
  color: #FC4C02;
}
.poster-club-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 14rpx;
}
.poster-club-logo {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  border: 1.5px solid #FC4C02;
  background: #1e293b;
}
.poster-hero-img-wrap {
  position: relative;
  width: 100%;
  height: 280rpx;
  border-radius: 22rpx;
  overflow: hidden;
  margin-bottom: 20rpx;
  border: 1px solid rgba(208, 253, 62, 0.45);
}
.poster-hero-img {
  width: 100%;
  height: 100%;
  display: block;
}
.poster-hero-caption {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 20rpx 22rpx 14rpx;
  background: linear-gradient(180deg, rgba(11, 13, 19, 0) 0%, rgba(11, 13, 19, 0.88) 100%);
  font-size: 21rpx;
  font-weight: 700;
  color: #f8fafc;
}
.pf-btn.card-share {
  background: #3b82f6;
  color: #ffffff;
}
.poster-footer {
  background: rgba(15, 23, 42, 0.94);
  padding: 20rpx 24rpx;
  border-radius: 24rpx;
  border: 1px solid rgba(255, 255, 255, 0.14);
}

/* ── 活动详情说明条 + 转发微信群 + 已报名同步首页提示卡 ── */
.hero-desc-box {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.hero-desc-line {
  display: flex;
  align-items: flex-start;
  font-size: 23rpx;
  line-height: 1.5;
}
.hero-desc-tag {
  color: rgba(255, 255, 255, 0.72);
  font-weight: 600;
  flex-shrink: 0;
}
.hero-desc-txt {
  color: #f8fafc;
  flex: 1;
}
.hero-share-wx-btn {
  margin: 0;
  padding: 0 20rpx;
  height: 52rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  border-radius: 999rpx;
  font-size: 22rpx;
  font-weight: 700;
  background: #07c160;
  color: #ffffff;
  border: none;
}
.hero-share-wx-btn::after {
  border: none;
}
.ncc-desc {
  display: block;
  font-size: 22rpx;
  line-height: 1.5;
  color: var(--rgm-text-sub, #94a3b8);
  margin: 8rpx 0 18rpx;
}
.archived-banner-card {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 22rpx 24rpx;
  margin-bottom: 24rpx;
  border-radius: 22rpx;
  background: var(--rgm-card, #141418);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.14));
}
.abc-icon {
  font-size: 36rpx;
}
.abc-body {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.abc-title {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #f8fafc);
}
.abc-sub {
  font-size: 22rpx;
  color: var(--rgm-text-sub, #94a3b8);
}
.joined-home-sync-card {
  padding: 24rpx;
  margin-bottom: 24rpx;
  border-radius: 24rpx;
  background: var(--rgm-card, #141418);
  border: 1px solid rgba(16, 185, 129, 0.4);
}
.jhsc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18rpx;
}
.jhsc-badge {
  font-size: 26rpx;
  font-weight: 800;
  color: #10b981;
}
.jhsc-sync-tag {
  font-size: 21rpx;
  font-weight: 700;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}
.jhsc-actions {
  display: flex;
  gap: 12rpx;
}
.jhsc-btn {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 0 10rpx;
  height: 72rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  border-radius: 16rpx;
  font-size: 23rpx;
  font-weight: 700;
}
.jhsc-btn::after {
  border: none;
}
.jhsc-btn.primary {
  flex: 1.35;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: #ffffff;
}
.jhsc-btn.ghost {
  background: var(--rgm-card-sub, #1B1B22);
  color: var(--rgm-text, #f8fafc);
  border: 1px solid var(--rgm-border, rgba(255, 255, 255, 0.14));
}
.jhsc-btn.share {
  background: rgba(7, 193, 96, 0.16);
  color: #07c160;
  border: 1px solid rgba(7, 193, 96, 0.38);
}
.jhsc-profile-tip {
  margin-top: 16rpx;
  padding: 14rpx 18rpx;
  border-radius: 14rpx;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.28);
}
.jhsc-tip-txt {
  font-size: 22rpx;
  line-height: 1.45;
  color: #d97706;
}
</style>
