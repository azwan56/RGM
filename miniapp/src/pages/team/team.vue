<template>
  <page-meta :page-style="isAnyModalOpen ? 'overflow: hidden;' : ''" />
  <view class="team-page" :class="themeClass">
    <!-- 首屏骨架屏：首次进入时盖住尚未加载的数据 -->
    <PageSkeleton v-if="firstLoadPending" overlay />

    <!-- ── 子页面返回栏：跑团首页拆分后，每个子页面顶部固定显示「‹ 跑团」 ── -->
    <view v-if="activeSection" class="section-back-bar">
      <view class="sbb-back" @click="closeSection">
        <text class="sbb-arrow">‹</text>
        <text class="sbb-back-txt">跑团</text>
      </view>
      <text class="sbb-title">{{ activeSectionTitle }}</text>
      <view class="sbb-placeholder" />
    </view>

    <!-- ── 大群精简条：仅在未选择跑团，或当前跑团隶属于该大群时展示在顶部，避免独立跑团被误认为隶属大群 ── -->
    <view v-if="currentOrg && !activeSection && (!currentClub || currentClub.org_id === currentOrg.id)" class="org-compact-card" @click="openSection('org')">
      <view class="occ-left">
        <text class="occ-icon">🏛️</text>
        <view class="occ-meta">
          <view class="occ-title-row">
            <text class="occ-title">{{ currentOrg.name }} 大群</text>
            <text v-if="currentClub?.org_id === currentOrg.id" class="occ-rel-pill">当前跑团上级大群</text>
          </view>
          <text class="occ-desc">{{ orgStatusText }}</text>
        </view>
      </view>
      <text class="occ-action" :class="{ warn: currentOrg.status !== 'confirmed' }">{{ currentOrg.status === 'confirmed' ? '大群详情 ›' : (currentOrg.status === 'expired' ? '查看 ›' : '去处理 ›') }}</text>
    </view>

    <!-- ── 🚩 已加入大群体但未加入任何下属跑团时 ── -->
    <view v-if="currentOrg && userClubs.length === 0 && !activeSection" class="subclubs-entry-section">
      <view class="section-card choose-subclub-card">
        <view class="csc-header-row" style="display: flex; align-items: center; justify-content: space-between;">
          <view class="title-with-icon">
            <text class="icon">🚩</text>
            <text class="card-title">选择加入【{{ currentOrg.name }}】分队</text>
          </view>
          <view
            style="padding: 8rpx 20rpx; border-radius: 999rpx; background: rgba(252, 76, 2, 0.15); border: 1rpx solid rgba(252, 76, 2, 0.45); color: #fc4c02; font-size: 22rpx; font-weight: 700;"
            @click="openCreateClubModal"
          >
            ✨ 自建跑团
          </view>
        </view>
        <text class="csc-intro-text">已认证：{{ currentOrg.class_name }} {{ currentOrg.real_name }}</text>
        <view v-if="orgSubClubs.length === 0" class="empty-clubs-text">
          暂无分队
        </view>
        <view v-else class="subclubs-grid-list">
          <view v-for="sc in orgSubClubs" :key="sc.id" class="subclub-item-box">
            <image class="sc-logo-img" :src="sc.logo_url || '/static/logo-square.png'" mode="aspectFill" />
            <view class="sc-content-box">
              <view class="sc-name-line">
                <text class="sc-name-title">{{ sc.name }}</text>
                <text class="mode-badge-pill" :class="sc.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                  {{ sc.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                </text>
                <text class="sc-city-tag">📍 {{ sc.city || '上海' }}</text>
              </view>
              <text v-if="sc.description" class="sc-desc-line">{{ sc.description }}</text>
              <text class="sc-meta-line">团长: {{ sc.owner_name || '平台指定' }} · {{ sc.member_count || 1 }} 位团员</text>
            </view>
            <button class="sc-join-action-btn" :class="{ 'btn-invite-mode': sc.join_mode === 'invite' }" :loading="joiningClubId === sc.id" @click="handleJoinClubWithCheck(sc)">
              {{ sc.join_mode === 'invite' ? '🔑 凭码加入' : '+ 自由加入' }}
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── 跑团快速切换横向标签栏 (仅在加入跑团后显示) ── -->
    <view v-if="userClubs.length > 0 && !activeSection" class="clubs-switcher-wrap">
      <scroll-view scroll-x class="clubs-switcher-scroll" :show-scrollbar="false">
        <view class="clubs-switcher-inner">
          <view
            v-for="c in userClubs"
            :key="c.id"
            class="club-tab-pill"
            :class="{ active: currentClub?.id === c.id }"
            @click="handleSwitchClub(c)"
          >
            <image
              class="tab-club-logo"
              :src="c.logo_url || '/static/logo-square.png'"
              mode="aspectFill"
            />
            <text class="tab-club-aff-icon">{{ c.org_id ? '🏛️' : '🌐' }}</text>
            <text class="tab-club-name">{{ c.name }}</text>
            <text v-if="currentClub?.id === c.id" class="tab-active-check">✓</text>
          </view>
          <view class="club-tab-pill tab-browse-btn" @click="openAllClubsModal">
            <text class="tab-browse-icon">＋ 切换/发现</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- If user belongs to a club -->
    <view v-if="currentClub">
      <!-- ── Header: Club Hero ── -->
      <view v-if="!activeSection" class="club-hero-card">
        <view class="hero-top">
          <image class="club-logo" :src="currentClub.logo_url || '/static/logo-square.png'" mode="aspectFill" />
          <view class="club-text">
            <view class="name-row">
              <text class="club-name">{{ currentClub.name }}</text>
              <text class="role-tag" :class="'role-' + currentRole">
                {{ currentRole === "owner" ? "👑 团长" : currentRole === "coach" ? "🧢 教练" : "🏃 团员" }}
              </text>
              <text v-if="mentorshipData.my_mentees?.length > 0" class="role-tag role-member">
                🥋 师傅 ({{ mentorshipData.my_mentees.length }}/3)
              </text>
            </view>
            <view class="hero-affiliation-row">
              <view
                v-if="currentClub.org_id"
                class="hero-aff-pill is-org"
                @click.stop="openSection('org')"
              >
                <text class="hap-txt">🏛️ {{ currentClub.org_name || currentOrg?.name || '大群' }} · 分队 ›</text>
              </view>
              <view v-else class="hero-aff-pill is-indep">
                <text class="hap-txt">🌐 独立公开跑团</text>
              </view>
              <view class="hero-aff-pill" @click.stop="openAllClubsModal">
                <text class="hap-txt">⇄ 切换跑团 ({{ userClubs.length }}) ›</text>
              </view>
            </view>
            <text v-if="currentClub.description" class="club-desc">{{ currentClub.description }}</text>
            <view class="hero-action-buttons-row">
              <!-- #ifdef MP-WEIXIN -->
              <button class="club-share-invite-btn primary-btn" open-type="share" data-share-type="club" :data-club-id="currentClub?.id" :data-club-name="currentClub?.name" :data-invite-code="currentClub?.invite_code || ''">
                <text class="csib-icon">📤</text>
                <text class="csib-text">邀请入团</text>
              </button>
              <!-- #endif -->
              <button
                class="club-share-invite-btn secondary-btn"
                @click.stop="openReportModal"
              >
                <text class="csib-icon">📊</text>
                <text class="csib-text">战报海报</text>
              </button>
              <button
                class="club-share-invite-btn secondary-btn"
                @click.stop="openCreateClubModal"
              >
                <text class="csib-icon">✨</text>
                <text class="csib-text">自建跑团</text>
              </button>
            </view>
          </view>
        </view>
      </view>

      <!-- ── 🚫 跑团访问权限已暂停阻断屏 ── -->
      <view v-if="(currentClub.is_access_suspended || isCurrentClubSuspended) && activeSection !== 'org'" class="section-card club-suspended-block-card">
        <view class="csb-icon-box">
          <text class="csb-icon">🚫</text>
        </view>
        <text class="csb-title">大群访问权限已暂停</text>
        <text class="csb-desc">
          跑团【{{ currentClub.name }}】隶属于【{{ currentClub.org_name || '大群' }}】。{{ currentSuspensionReason || '2周临时访问期已过，请补齐必填资料并等待管理员审核。' }}
        </text>
        <view class="csb-btn-row">
          <button class="csb-btn primary" @click="goToProfilePage">
            📝 立即前往个人中心补齐必填资料
          </button>
          <button v-if="userClubs.length > 1" class="csb-btn secondary" @click="openAllClubsModal">
            ⇄ 切换至其他跑团
          </button>
        </view>
      </view>

      <!-- 正常访问内容容器 -->
      <view v-else>
        <!-- ── 🏃 我的即将参加约跑待办提醒卡片 (Upcoming Group Run Banner) ── -->
        <view v-if="nextUpcomingRun && !activeSection" class="upcoming-run-banner-card" @click="handleOpenMap(nextUpcomingRun)">
          <view class="urb-header">
            <view class="urb-badge">
              <view class="urb-badge-pulse" />
              <text class="urb-badge-text">🏃 即将参加的约跑</text>
            </view>
            <text class="urb-countdown">{{ getCountdownText(nextUpcomingRun.meet_time || nextUpcomingRun.start_date) }}</text>
          </view>
          <view class="urb-body">
            <image class="urb-thumb" :src="nextUpcomingRun.cover_image || 'https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=800&auto=format&fit=crop&q=80'" mode="aspectFill" />
            <view class="urb-info">
              <text class="urb-title">{{ nextUpcomingRun.title }}</text>
              <view class="urb-meta-row">
                <text class="urb-icon">⏰</text>
                <text class="urb-meta-text highlight">{{ formatMeetTime(nextUpcomingRun.meet_time || nextUpcomingRun.start_date) }}</text>
              </view>
              <view class="urb-meta-row">
                <text class="urb-icon">📍</text>
                <text class="urb-meta-text">{{ nextUpcomingRun.location || '跑团集合点' }}</text>
              </view>
            </view>
          </view>
          <view class="urb-actions-row">
            <button class="urb-action-btn reminder-btn" @click.stop="handleAddToCalendar(nextUpcomingRun)">
              🔔 设为手机日历提醒
            </button>
            <button class="urb-action-btn map-btn" @click.stop="handleOpenMap(nextUpcomingRun)">
              📍 导航集合点 ›
            </button>
          </view>
        </view>

        <template v-if="!activeSection">
        <!-- ── 🥇 本月英雄榜预览：我的排名 + 前三名，点击进入完整榜单与动态 ── -->
        <view class="section-card rank-teaser-card" @click="goToRankPage()">
          <view class="rt-header">
            <text class="rt-title">🥇 本月英雄榜</text>
            <text class="rt-link">完整榜单 ›</text>
          </view>
          <view class="rt-my-row">
            <template v-if="myRankItem">
              <text class="rt-my-rank">我的排名 #{{ myRankItem.rank }}</text>
              <text class="rt-my-meta">{{ myRankItem.distance_km }} km · 目标完成 {{ myRankItem.progress_pct || 0 }}%</text>
            </template>
            <text v-else class="rt-my-meta">本月暂无跑量记录</text>
          </view>
          <view v-if="topThree.length" class="rt-top-list">
            <view v-for="item in topThree" :key="item.user_id" class="rt-top-item" :class="{ 'is-me': item.user_id === user?.id }">
              <text class="rt-medal">{{ item.rank === 1 ? '🥇' : item.rank === 2 ? '🥈' : '🥉' }}</text>
              <image class="rt-avatar" :src="item.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <text class="rt-name">{{ item.display_name }}</text>
              <text class="rt-km">{{ item.distance_km }} km</text>
            </view>
          </view>
          <text v-else class="rt-empty">本月暂无团员打卡数据</text>
        </view>

        <!-- ── 🥋 我的师徒（1对1传帮带 · 最多带3位徒弟 · 同大群可跨跑团） ── -->
        <view class="section-card mentorship-card">
          <view class="rt-header" style="margin-bottom: 16rpx; display: flex; align-items: center; justify-content: space-between; gap: 10rpx; flex-wrap: nowrap;">
            <view style="display: flex; align-items: center; gap: 8rpx; flex-wrap: nowrap; min-width: 0; flex: 1;">
              <text class="rt-title" style="white-space: nowrap; flex-shrink: 0; font-size: 27rpx;">🥋 师徒</text>
              <text class="term-info" @click.stop="explainTerm('mentorship')">ⓘ</text>
              <text style="font-size: 19rpx; font-weight: 600; padding: 3rpx 12rpx; border-radius: 999rpx; background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08)); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14)); white-space: nowrap; flex-shrink: 0;">
                徒弟 {{ mentorshipData.my_mentees?.length || 0 }}/{{ mentorshipData.max_mentees || 3 }}
              </text>
              <text v-if="currentOrg" style="font-size: 19rpx; font-weight: 600; color: var(--rgm-text-2, #a1a1aa); background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08)); border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14)); padding: 3rpx 12rpx; border-radius: 999rpx; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 210rpx;">
                {{ currentOrg.name }}跨团
              </text>
            </view>
            <text class="rt-link" style="white-space: nowrap; flex-shrink: 0;" @click="openMentorshipModal">+ 结对 ›</text>
          </view>

          <!-- 我的师傅（最多 1 位） -->
          <view
            v-if="mentorshipData.my_mentor"
            style="display: flex; align-items: center; justify-content: space-between; padding: 16rpx 20rpx; border-radius: 18rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.12)); margin-bottom: 16rpx;"
          >
            <view style="display: flex; align-items: center; gap: 16rpx;">
              <image
                :src="mentorshipData.my_mentor.avatar_url || '/static/logo-square.png'"
                mode="aspectFill"
                style="width: 68rpx; height: 68rpx; border-radius: 50%; border: 2rpx solid var(--rgm-line, rgba(255,255,255,0.2));"
              />
              <view style="display: flex; flex-direction: column; gap: 4rpx;">
                <view style="display: flex; align-items: center; gap: 10rpx; flex-wrap: wrap;">
                  <text style="font-size: 25rpx; font-weight: 700; color: var(--rgm-text, #ffffff);">
                    我的师傅：{{ mentorshipData.my_mentor.display_name }}
                  </text>
                  <text style="font-size: 19rpx; color: var(--rgm-text-2, #a1a1aa); background: var(--rgm-tint-2, rgba(255,255,255,0.08)); padding: 2rpx 10rpx; border-radius: 8rpx; font-weight: 600;">
                    {{ mentorshipData.my_mentor.club_name || '同大群戈友' }}
                  </text>
                </view>
                <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa);">
                  已共享数据 · VDOT {{ mentorshipData.my_mentor.vdot || '—' }}
                </text>
              </view>
            </view>
            <text
              style="font-size: 21rpx; color: var(--rgm-text-3, #71717a); padding: 8rpx 12rpx; white-space: nowrap;"
              @click.stop="handleUnbindMentorship(mentorshipData.my_mentor.mentor_uid, user?.id, mentorshipData.my_mentor.display_name)"
            >
              解绑
            </text>
          </view>

          <!-- 我的徒弟列表（最多 3 位，展示训练与休息数据摘要） -->
          <view v-if="mentorshipData.my_mentees && mentorshipData.my_mentees.length > 0" style="display: flex; flex-direction: column; gap: 14rpx;">
            <view
              v-for="m in mentorshipData.my_mentees"
              :key="m.mentee_uid"
              style="padding: 20rpx; border-radius: 20rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.09));"
              @click="openMenteeDetailModal(m.mentee_uid)"
            >
              <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12rpx;">
                <view style="display: flex; align-items: center; gap: 14rpx;">
                  <image
                    :src="m.avatar_url || '/static/logo-square.png'"
                    mode="aspectFill"
                    style="width: 64rpx; height: 64rpx; border-radius: 50%; border: 2rpx solid var(--rgm-line, rgba(255,255,255,0.2));"
                  />
                  <view style="display: flex; flex-direction: column; gap: 2rpx;">
                    <view style="display: flex; align-items: center; gap: 10rpx; flex-wrap: wrap;">
                      <text style="font-size: 26rpx; font-weight: 700; color: var(--rgm-text, #ffffff);">{{ m.display_name }}</text>
                      <text style="font-size: 19rpx; color: var(--rgm-text-2, #a1a1aa); background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08)); padding: 2rpx 10rpx; border-radius: 8rpx; font-weight: 600;">
                        {{ m.club_name || '同大群跨团' }}
                      </text>
                    </view>
                    <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa);">
                      今日：{{ m.training?.today_workout?.type || '休息恢复' }} {{ m.training?.today_workout?.target_km ? m.training.today_workout.target_km + 'km' : '' }}
                      · {{ m.training?.today_workout?.completed ? '✅ 已打卡' : '⏳ 待完成' }}
                    </text>
                  </view>
                </view>
                <view style="display: flex; flex-direction: column; align-items: flex-end; gap: 4rpx;">
                  <text
                    style="font-size: 20rpx; font-weight: 700; padding: 4rpx 12rpx; border-radius: 999rpx; white-space: nowrap;"
                    :style="m.rest_and_recovery?.status_code === 'danger'
                      ? 'background: rgba(239,68,68,0.14); color: var(--rgm-red, #ef4444);'
                      : m.rest_and_recovery?.status_code === 'tired'
                        ? 'background: var(--rgm-tint-2, rgba(245,158,11,0.14)); color: var(--rgm-text-2, #fbbf24);'
                        : 'background: rgba(34,197,94,0.12); color: var(--rgm-green, #22c55e);'"
                  >
                    {{ m.rest_and_recovery?.status_label || '状态良好' }} (TSB {{ m.rest_and_recovery?.tsb ?? 0 }})
                  </text>
                  <text style="font-size: 20rpx; color: var(--rgm-brand-text, #fc4c02); font-weight: 600; white-space: nowrap;">详情 ›</text>
                </view>
              </view>

              <!-- 休息与恢复四维速览条 -->
              <view style="display: flex; justify-content: space-between; gap: 10rpx; padding-top: 12rpx; border-top: 1rpx dashed var(--rgm-line, rgba(255,255,255,0.08));">
                <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa);">
                  💓 静息心率 <text style="color: var(--rgm-text, #ffffff); font-weight: 700;">{{ m.rest_and_recovery?.resting_hr ? m.rest_and_recovery.resting_hr + 'bpm' : '—' }}</text>
                </text>
                <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa);">
                  🧬 HRV <text style="color: var(--rgm-text, #ffffff); font-weight: 700;">{{ m.rest_and_recovery?.hrv ? m.rest_and_recovery.hrv + 'ms' : '—' }}</text>
                </text>
                <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa);">
                  😴 睡眠 <text style="color: var(--rgm-text, #ffffff); font-weight: 700;">{{ m.rest_and_recovery?.sleep_score ? m.rest_and_recovery.sleep_score + '分' : (m.rest_and_recovery?.sleep_hours ? m.rest_and_recovery.sleep_hours + 'h' : '—') }}</text>
                </text>
                <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa);">
                  🔋 恢复 <text style="color: var(--rgm-green, #22c55e); font-weight: 700;">{{ m.rest_and_recovery?.recovery_pct ? m.rest_and_recovery.recovery_pct + '%' : '—' }}</text>
                </text>
              </view>
            </view>
          </view>

          <!-- 空状态提示 + 快捷入口 -->
          <view v-else-if="!mentorshipData.my_mentor" style="padding: 8rpx 6rpx 6rpx;">
            <view style="display: flex; gap: 14rpx;">
              <button
                style="flex: 1; margin: 0; height: 68rpx; line-height: 68rpx; font-size: 23rpx; font-weight: 700; border-radius: 16rpx; background: var(--rgm-card-2, #1f1f26); color: var(--rgm-text, #ffffff); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.14));"
                @click="openMentorshipModal"
              >
                🔍 团内结对
              </button>
              <!-- #ifdef MP-WEIXIN -->
              <button
                open-type="share"
                data-share-type="mentor"
                style="flex: 1; margin: 0; height: 68rpx; line-height: 68rpx; font-size: 23rpx; font-weight: 700; border-radius: 16rpx; background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));"
              >
                📤 微信邀请
              </button>
              <!-- #endif -->
            </view>
          </view>
        </view>

        <!-- ── 功能菜单：原来平铺的长列表拆成子页面，按需进入 ── -->
        <view class="section-card team-menu-card">
          <view v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev" class="pm-item" @click="goToCockpitPage">
            <text class="pm-icon">🧢</text>
            <view class="pm-meta">
              <text class="pm-title">教练工作台</text>
            </view>
            <text class="pm-status ok">进入</text>
            <text class="pm-arrow">›</text>
          </view>
          <view class="pm-item" @click="openSection('events')">
            <text class="pm-icon">🏃</text>
            <view class="pm-meta">
              <text class="pm-title">约跑与活动</text>
            </view>
            <text class="pm-status" :class="{ ok: events.length > 0 }">{{ events.length }} 场</text>
            <text class="pm-arrow">›</text>
          </view>
          <view class="pm-item" @click="goToRankPage('feed')">
            <text class="pm-icon">🔥</text>
            <view class="pm-meta">
              <text class="pm-title">打卡动态</text>
            </view>
            <text class="pm-arrow">›</text>
          </view>
          <view class="pm-item" @click="openReportModal">
            <text class="pm-icon">📊</text>
            <view class="pm-meta">
              <text class="pm-title">跑团周报 / 月报</text>
            </view>
            <text class="pm-status ok">海报</text>
            <text class="pm-arrow">›</text>
          </view>
          <view class="pm-item" @click="showPersonalReportModal = true">
            <text class="pm-icon">🖼️</text>
            <view class="pm-meta">
              <text class="pm-title">个人周报 / 月报</text>
            </view>
            <text class="pm-status ok">生成</text>
            <text class="pm-arrow">›</text>
          </view>
          <view v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev || isSuperAdmin" class="pm-item" @click="openNewMembersScope('club')">
            <text class="pm-icon">🌱</text>
            <view class="pm-meta">
              <text class="pm-title">新队员管理</text>
            </view>
            <text
              class="pm-status"
              :class="clubNewMembersSummary.pending_setup_count > 0 ? 'warn' : 'ok'"
            >
              {{ clubNewMembersSummary.new_7d_count > 0 ? `近7天 +${clubNewMembersSummary.new_7d_count}人` : (clubNewMembersSummary.pending_setup_count > 0 ? `${clubNewMembersSummary.pending_setup_count}人待设` : `${clubNewMembersSummary.total_members}人就绪`) }}
            </text>
            <text class="pm-arrow">›</text>
          </view>
          <view v-if="isSuperAdmin" class="pm-item" @click="openNewMembersScope('unaffiliated')">
            <text class="pm-icon">🌍</text>
            <view class="pm-meta">
              <text class="pm-title">未入团自由跑友 (超管)</text>
            </view>
            <text
              class="pm-status"
              :class="unaffiliatedSummary.pending_setup_count > 0 ? 'warn' : 'ok'"
            >
              {{ unaffiliatedSummary.total_members > 0 ? `${unaffiliatedSummary.total_members}人 · 绑表${unaffiliatedSummary.watch_bound_count}` : '查看名册' }}
            </text>
            <text class="pm-arrow">›</text>
          </view>
          <view v-if="isClubManager" class="pm-item" @click="openSection('manage')">
            <text class="pm-icon">👑</text>
            <view class="pm-meta">
              <text class="pm-title">{{ managerTitle }}</text>
            </view>
            <text class="pm-arrow">›</text>
          </view>
          <view
            v-if="(currentRole === 'owner' || isOwnerOrDev || isSuperAdmin) && !currentClub?.is_virtual_unaffiliated"
            class="pm-item"
            @click="handleOpenMembersModal"
          >
            <text class="pm-icon">👥</text>
            <view class="pm-meta">
              <text class="pm-title">队员管理与移出</text>
            </view>
            <text class="pm-status ok">{{ members.length }}人</text>
            <text class="pm-arrow">›</text>
          </view>
          <view class="pm-item" :class="{ 'pm-item-last': currentClub?.is_virtual_unaffiliated }" @click="openSection('org')">
            <text class="pm-icon">🏛️</text>
            <view class="pm-meta">
              <text class="pm-title">{{ currentOrg ? currentOrg.name + ' 大群' : '大群认证' }}</text>
            </view>
            <text v-if="currentOrg" class="pm-status" :class="{ ok: currentOrg.status === 'confirmed', warn: currentOrg.status !== 'confirmed' }">{{ orgStatusShort }}</text>
            <text class="pm-arrow">›</text>
          </view>
          <view
            v-if="currentClub && !currentClub.is_virtual_unaffiliated"
            class="pm-item pm-item-last"
            @click="openLeaveClubConfirmModal"
          >
            <text class="pm-icon">🚪</text>
            <view class="pm-meta">
              <text class="pm-title" style="color: #ef4444;">退出当前跑团</text>
            </view>
            <text class="pm-status warn">{{ currentRole === 'owner' ? '需先移交团长' : '防误触保护' }}</text>
            <text class="pm-arrow">›</text>
          </view>
        </view>
        </template>

        <!-- 子页面：管理中心（团长 / 教练 / 大群管理员 · 聚焦高频分享、战报、约跑与邀请） -->
        <template v-if="activeSection === 'manage'">
    <!-- ── CARD 1: 👑 团长/教练高频快捷中心 ── -->
    <view v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev || isOrgAdmin || isSuperAdmin" class="section-card owner-panel-card">
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">👑</text>
          <text class="card-title">{{ currentRole === 'owner' || isOwnerOrDev ? '团长快捷中心' : (currentRole === 'coach' ? '教练快捷中心' : '大群管理员快捷中心') }}</text>
        </view>
        <text class="owner-pill">{{ currentRole === 'owner' || isOwnerOrDev ? '团长权限' : (currentRole === 'coach' ? '教练权限' : '管理员权限') }}</text>
      </view>

      <view class="owner-actions-grid">
        <view v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev || isSuperAdmin" class="owner-tool-item" @click="openNewMembersScope('club')">
          <view class="tool-icon-box bg-green">
            <text class="tool-icon">🌱</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">新队员管理 (入团/绑表/目标)</text>
              <text class="mode-badge-pill" :class="clubNewMembersSummary.pending_setup_count > 0 ? 'mode-invite' : 'mode-free'">
                {{ clubNewMembersSummary.pending_setup_count > 0 ? `${clubNewMembersSummary.pending_setup_count}人待完善` : '全员已就绪' }}
              </text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view
          v-if="(currentRole === 'owner' || isOwnerOrDev || isSuperAdmin) && !currentClub?.is_virtual_unaffiliated"
          class="owner-tool-item"
          @click="handleOpenMembersModal"
        >
          <view class="tool-icon-box bg-orange">
            <text class="tool-icon">👥</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">队员管理与移除 ({{ members.length }}人)</text>
              <text class="mode-badge-pill mode-report">任免教练 / 防误触移出</text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="isSuperAdmin" class="owner-tool-item" @click="openNewMembersScope('unaffiliated')">
          <view class="tool-icon-box bg-blue">
            <text class="tool-icon">🌍</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">未入团自由跑友名册 (超管全局)</text>
              <text class="mode-badge-pill mode-invite">
                {{ unaffiliatedSummary.total_members }}人 ({{ unaffiliatedSummary.watch_bound_count }}绑表)
              </text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev" class="owner-tool-item" @click="openReportModal">
          <view class="tool-icon-box bg-gold">
            <text class="tool-icon">📊</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">跑团周报与月报</text>
              <text class="mode-badge-pill mode-report">高频分享</text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="currentRole === 'owner' || isOwnerOrDev || currentRole === 'coach'" class="owner-tool-item" @click="handleOpenCreateGroupRun">
          <view class="tool-icon-box bg-orange">
            <text class="tool-icon">🏃</text>
          </view>
          <view class="tool-content">
            <text class="tool-main-title">发起跑团约跑</text>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="currentRole === 'owner' || isOwnerOrDev" class="owner-tool-item" @click="handleOpenCreateEvent">
          <view class="tool-icon-box bg-yellow">
            <text class="tool-icon">🏆</text>
          </view>
          <view class="tool-content">
            <text class="tool-main-title">发起跑团挑战赛</text>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev" class="owner-tool-item" @click="handleCopyClubInviteCode">
          <view class="tool-icon-box bg-green">
            <text class="tool-icon">🔑</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">复制邀请码：{{ currentClub?.invite_code || '免码' }}</text>
              <text class="mode-badge-pill" :class="currentClub?.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                {{ currentClub?.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
              </text>
            </view>
          </view>
          <text class="arrow-right">📋</text>
        </view>

        <!-- 🏛️ 大群主理人 / 管理员专属快捷入口（无需超管权限） -->
        <view v-if="isOrgAdmin && currentOrg" class="owner-tool-item" @click="openOrgJoinModeModal">
          <view class="tool-icon-box bg-gold">
            <text class="tool-icon">⚙️</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">【{{ currentOrg.name }}】大群设定与邀请码</text>
              <text class="mode-badge-pill" :class="currentOrg.join_mode === 'free' ? 'mode-free' : 'mode-invite'">
                {{ currentOrg.join_mode === 'free' ? '🟢 自由入会' : '🔒 凭邀请码' }}
              </text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="isOrgAdmin && currentOrg" class="owner-tool-item" @click="openOrgFieldRulesModal">
          <view class="tool-icon-box bg-blue">
            <text class="tool-icon">🛡️</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">大群准入信息字段配置</text>
              <text class="mode-badge-pill mode-report">必填 / 选填 / 不显示</text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="isOrgAdmin && currentOrg" class="owner-tool-item" @click="openOrgReportModal">
          <view class="tool-icon-box bg-green">
            <text class="tool-icon">📊</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">【{{ currentOrg.name }}】大群全域报表与分团 PK</text>
              <text class="mode-badge-pill mode-free">跨团去重 / 分团对比</text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="isOrgAdmin && currentOrg" class="owner-tool-item" @click="openOrgEventsModal">
          <view class="tool-icon-box bg-purple">
            <text class="tool-icon">🚩</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">发起大群跨跑团联合活动 / 对抗赛</text>
              <text class="mode-badge-pill mode-report">多团联动合练</text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="isOrgAdmin && currentOrg" class="owner-tool-item" @click="openOrgMembersModal">
          <view class="tool-icon-box bg-orange">
            <text class="tool-icon">🏛️</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">大群花名册与资料审核 ({{ orgMembers.length }}人)</text>
              <text class="mode-badge-pill mode-free">审核 / 委派管理</text>
            </view>
          </view>
          <text class="arrow-right">›</text>
        </view>
      </view>

      <!-- 💻 低频重度管理业务已迁移至网页端工作台提示卡 -->
      <view
        style="margin-top: 20rpx; padding: 18rpx 22rpx; border-radius: 18rpx; background: var(--rgm-brand-tint, rgba(56, 189, 248, 0.08)); border: 1rpx solid var(--rgm-brand-line, rgba(56, 189, 248, 0.3)); display: flex; align-items: center; justify-content: space-between;"
      >
        <view style="display: flex; align-items: center; gap: 8rpx;" @click="explainTerm('web_admin')">
          <text style="font-size: 24rpx; font-weight: 700; color: var(--rgm-brand-text, #38bdf8);">💻 网页管理后台 rgm.vanpower.net</text>
          <text class="term-info">ⓘ</text>
        </view>
        <text
          style="font-size: 22rpx; font-weight: 700; color: var(--rgm-on-brand, #0b0d13); background: var(--rgm-brand, #38bdf8); padding: 6rpx 18rpx; border-radius: 999rpx; flex-shrink: 0;"
          @click="copyWebAdminUrl"
        >
          📋 复制网址
        </text>
      </view>
    </view>

    <!-- ── CARD 2: 🧢 教练排课审核与学员体能罗盘 (Visible to Owner & Coach) ── -->
    <view
      v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev"
      class="section-card coach-preview-card"
      @click="goToCockpitPage"
    >
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">🧢</text>
          <text class="card-title">排课审核与体能罗盘</text>
        </view>
        <text class="sub-link">进入 ›</text>
      </view>

      <view class="cockpit-summary-grid">
        <view class="cockpit-tile green">
          <text class="c-val">{{ coachCockpit?.summary?.peak_count || 0 }}人</text>
          <text class="c-label">🟢 巅峰状态</text>
        </view>
        <view class="cockpit-tile blue">
          <text class="c-val">{{ coachCockpit?.summary?.optimal_count || 1 }}人</text>
          <text class="c-label">🔵 专项适应</text>
        </view>
        <view class="cockpit-tile yellow">
          <text class="c-val">{{ coachCockpit?.summary?.tired_count || 0 }}人</text>
          <text class="c-label">🟡 疲劳积累</text>
        </view>
        <view class="cockpit-tile red">
          <text class="c-val">{{ coachCockpit?.summary?.danger_count || 0 }}人</text>
          <text class="c-label">🔴 伤病预警</text>
        </view>
      </view>

      <!-- Coach Plan & Execution Quick Strip -->
      <view
        style="margin-top: 16rpx; padding: 14rpx 18rpx; border-radius: 16rpx; background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12)); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35)); display: flex; align-items: center; justify-content: space-between;"
      >
        <view style="display: flex; align-items: center; gap: 14rpx; flex-wrap: wrap;">
          <text style="font-size: 20rpx; font-weight: 800; color: var(--rgm-brand-text, #fc4c02);">📋 训练计划</text>
          <text style="font-size: 20rpx; color: var(--rgm-text-2, #fbbf24); font-weight: 700;">
            待审核 {{ coachCockpit?.summary?.plans_draft_count || 0 }}人
          </text>
          <text style="font-size: 20rpx; color: var(--rgm-green, #34d399); font-weight: 700;">
            执行中 {{ coachCockpit?.summary?.plans_published_count || 0 }}人
          </text>
          <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa);">
            达成率 {{ coachCockpit?.summary?.avg_week_compliance || 0 }}%
          </text>
        </view>
        <text style="font-size: 20rpx; font-weight: 800; color: var(--rgm-brand-text, #fc4c02);">去审核 ›</text>
      </view>
    </view>

        </template>

        <!-- 子页面：约跑与拉练活动 -->
        <template v-if="activeSection === 'events'">
    <!-- ── CARD 3: 🏃 跑团约跑与拉练活动 ── -->
    <view class="section-card group-runs-section">
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">🏃</text>
          <text class="card-title">约跑与拉练 ({{ events.length }})</text>
        </view>
        <view class="header-btn-group">
          <button
            class="mini-action-btn highlight-btn"
            @click="handleOpenCreateGroupRun"
          >
            + 发起约跑
          </button>
        </view>
      </view>

      <view v-if="events.length" class="events-list">
        <view v-for="evt in events" :key="evt.id" class="group-run-card">
          <!-- 题头图 Cover Banner -->
          <view class="gr-cover-wrap">
            <image
              class="gr-cover-img"
              :src="evt.cover_image || 'https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=800&auto=format&fit=crop&q=80'"
              mode="aspectFill"
            />
            <view class="gr-cover-gradient" />
            <view class="gr-cover-top-badges">
              <text v-if="evt.is_org_event" class="gr-tag" style="background: rgba(245, 158, 11, 0.9); color: #000000; font-weight: 900;">🏛️ 大群联合</text>
              <text class="gr-tag">{{ evt.event_type === 'distance_challenge' ? '🏆 跑量挑战' : '🏃 线下约跑' }}</text>
              <text v-if="evt.is_joined" class="gr-joined-badge">✓ 我已报名</text>
              <text v-else-if="evt.lifecycle_status === 'ongoing'" class="gr-status-badge">🔥 进行中</text>
              <text v-else class="gr-status-badge">报名中</text>
            </view>
            <view class="gr-cover-bottom-info">
              <text class="gr-dist-pill">📏 目标 {{ evt.target_km || 10 }} km</text>
              <text v-if="evt.pace_requirement" class="gr-pace-pill">⚡ 配速 {{ evt.pace_requirement }}</text>
            </view>
          </view>

          <!-- 约跑详情主体 -->
          <view class="gr-content-box">
            <view class="gr-title-row">
              <text class="gr-title">{{ evt.title }}</text>
              <view v-if="canManageEvent(evt)" class="evt-manage-actions">
                <text class="evt-btn edit" @click.stop="handleOpenEditEvent(evt)">编辑</text>
                <text class="evt-btn archive" @click.stop="handleArchiveEvent(evt)">归档</text>
                <text class="evt-btn del" @click.stop="handleDeleteEvent(evt.id)">删除</text>
              </view>
            </view>

            <!-- 发起人与重复周期条 -->
            <view class="gr-organizer-strip">
              <view class="gr-org-left">
                <image
                  class="gr-org-avatar"
                  :src="evt.creator_avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=80&auto=format&fit=crop&q=80'"
                  mode="aspectFill"
                />
                <view class="gr-org-meta">
                  <text class="gr-org-role-tag">{{ evt.creator_role || '发起人' }}</text>
                  <text class="gr-org-name">{{ evt.creator_name || '跑团发起' }}</text>
                </view>
              </view>
              <view v-if="evt.repeat_rule === 'weekly'" class="gr-org-repeat-pill">
                <text class="gr-rep-icon">🔄</text>
                <text class="gr-rep-text">每周例跑</text>
              </view>
            </view>

            <!-- 时间与地点 -->
            <view class="gr-detail-strip">
              <view class="gr-detail-row">
                <text class="gdr-icon">⏰</text>
                <text class="gdr-label">时间：</text>
                <text class="gdr-val highlight">{{ formatMeetTime(evt.meet_time || evt.start_date) }}</text>
              </view>
              <view class="gr-detail-row location-row" @click.stop="handleOpenMap(evt)">
                <text class="gdr-icon">📍</text>
                <text class="gdr-label">地点：</text>
                <text class="gdr-val link">{{ evt.location || '跑团指定集合点' }}</text>
                <text class="gdr-link-arrow">导航/复制 ›</text>
              </view>
              <view v-if="evt.location_detail" class="gr-detail-row sub">
                <text class="gdr-icon">🚩</text>
                <text class="gdr-label">路线：</text>
                <text class="gdr-val">{{ evt.location_detail }}</text>
              </view>
              <view v-if="evt.rules" class="gr-detail-row sub">
                <text class="gdr-icon">💡</text>
                <text class="gdr-label">说明：</text>
                <text class="gdr-val">{{ evt.rules }}</text>
              </view>
            </view>

            <!-- 报名成员头像墙 + 完赛距离/配速数据入口 -->
            <view class="gr-participants-row" @click.stop="handleOpenGroupRunSpace(evt)">
              <view class="gr-part-left">
                <view style="display: flex; align-items: center; gap: 12rpx; flex-wrap: wrap;">
                  <text class="gr-part-title">👥 参团跑友 ({{ evt.participant_count || 0 }}人{{ evt.max_participants > 0 ? ' / 限' + evt.max_participants + '人' : '' }})</text>
                  <text style="font-size: 20rpx; padding: 2rpx 12rpx; border-radius: 999rpx; background: rgba(208, 253, 62, 0.14); color: var(--rgm-accent, #d0fd3e);">
                    {{ evt.visibility_mode === 'public' ? '🌐 公开战报' : evt.visibility_mode === 'club_members' ? '👥 全团可见' : '🔒 仅报名者可见' }}
                  </text>
                </view>
                <view v-if="evt.participants && evt.participants.length > 0" class="gr-avatars-stack">
                  <image
                    v-for="(p, pidx) in evt.participants.slice(0, 6)"
                    :key="pidx"
                    class="gr-stacked-avatar"
                    :src="p.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80'"
                    mode="aspectFill"
                  />
                  <view v-if="evt.participants.length > 6" class="gr-avatar-more">
                    <text class="gr-more-text">+{{ evt.participants.length - 6 }}</text>
                  </view>
                </view>
                <text v-else class="gr-no-part-text">暂无报名</text>
              </view>
              <text class="gr-view-parts-arrow">{{ isGroupRunPostStage(evt) ? '🏆 完赛战报 ›' : '📣 集结分队 ›' }}</text>
            </view>

            <!-- 阶段入口：约跑前集结 / 约跑后战报 / 朋友圈海报 -->
            <view class="gr-stage-entry-row">
              <view class="gr-stage-entry" :class="{ current: !isGroupRunPostStage(evt) }" @click.stop="handleOpenGroupRunSpace(evt, 'pre')">
                <text class="gse-step">约跑前</text>
                <text class="gse-name">📣 集结分队</text>
              </view>
              <view class="gr-stage-entry" :class="{ current: isGroupRunPostStage(evt) }" @click.stop="handleOpenGroupRunSpace(evt, 'post')">
                <text class="gse-step">约跑后</text>
                <text class="gse-name">🏆 完赛战报</text>
              </view>
              <view class="gr-stage-entry" @click.stop="handleOpenGroupRunSpace(evt, undefined, true)">
                <text class="gse-step">转发朋友圈</text>
                <text class="gse-name">🖼️ 约跑海报</text>
              </view>
            </view>

            <!-- 操作按钮栏 (一键报名 / 转发 / 日历 / 取消) -->
            <view class="gr-actions-bar">
              <view v-if="!evt.is_joined" style="display: flex; gap: 14rpx; width: 100%;">
                <button
                  class="gr-join-btn"
                  style="flex: 1.35;"
                  :loading="joiningEventId === evt.id"
                  @click="handleJoinGroupRun(evt)"
                >
                  🏃 一键报名
                </button>
                <button
                  class="gr-wechat-share-btn"
                  style="flex: 1;"
                  open-type="share"
                  :data-share-type="'group_run'"
                  :data-event-id="evt.id"
                  :data-club-id="evt.club_id || currentClub?.id"
                  :data-club-name="currentClub?.name || evt.club_name || '跑团'"
                  :data-event-title="evt.title"
                  :data-meet-time="evt.meet_time || evt.start_date || ''"
                  :data-cover-image="evt.cover_image || currentClub?.logo_url || ''"
                  @click.stop
                >
                  💬 转发
                </button>
              </view>
              <view v-else class="gr-joined-action-group">
                <button
                  class="gr-wechat-share-btn"
                  style="flex: 1;"
                  open-type="share"
                  :data-share-type="'group_run'"
                  :data-event-id="evt.id"
                  :data-club-id="evt.club_id || currentClub?.id"
                  :data-club-name="currentClub?.name || evt.club_name || '跑团'"
                  :data-event-title="evt.title"
                  :data-meet-time="evt.meet_time || evt.start_date || ''"
                  :data-cover-image="evt.cover_image || currentClub?.logo_url || ''"
                  @click.stop
                >
                  💬 转发
                </button>
                <button class="gr-reminder-btn" style="flex: 1;" @click="handleAddToCalendar(evt)">
                  🔔 日历
                </button>
                <button class="gr-leave-btn" style="flex: 0.8;" :loading="joiningEventId === evt.id" @click="handleLeaveGroupRun(evt)">
                  取消
                </button>
              </view>
            </view>
          </view>
        </view>
      </view>
      <view v-else class="empty-box">
        <text class="empty-text">暂无约跑活动</text>
      </view>
    </view>
        </template>
    </view>
    </view>

    <!-- ── Unjoined State: Free / Solo Runner View + Club Options ── -->
    <view v-else-if="!activeSection" class="unjoined-club-view">
      <view class="unjoined-hero-box">
        <view class="unjoined-badge">🤝 寻找跑团与队友</view>
        <text class="unjoined-hero-title">想要与队友合练备战？</text>
        <view class="unjoined-btn-row">
          <button class="unjoined-action-btn secondary-invite" @click="showJoinModal = true">
            🔑 邀请码入团
          </button>
          <button
            class="unjoined-action-btn primary-join"
            @click="openCreateClubModal"
          >
            ✨ 自建跑团 (满3人解锁)
          </button>
        </view>
      </view>

      <!-- 🌍 未入团自由跑友同伴 · 基本状态互看卡片 -->
      <view class="section-card unaffiliated-peers-card">
        <view class="card-header-row" style="margin-bottom: 14rpx;">
          <view class="title-with-icon">
            <text class="icon">🌍</text>
            <text class="card-title">{{ isSuperAdmin ? '未入团自由跑友名册 (超管)' : '自由跑友同伴 · 基本状态互看' }}</text>
          </view>
          <view
            class="mini-action-btn"
            style="padding: 8rpx 20rpx; border-radius: 999rpx; background: var(--rgm-brand-tint, rgba(252,76,2,0.14)); border: 1rpx solid var(--rgm-brand-line, rgba(252,76,2,0.4)); color: var(--rgm-brand-text, #fc4c02); font-size: 22rpx; font-weight: 700;"
            @click="openNewMembersScope('unaffiliated')"
          >
            查看全部 ({{ unaffiliatedSummary.total_members }}) ›
          </view>
        </view>

        <view
          style="padding: 14rpx 18rpx; border-radius: 14rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.08)); margin-bottom: 18rpx;"
        >
          <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa); line-height: 1.45; display: block;">
            🤝 未加入任何跑团的跑友之间可相互查看基本状态（绑表、目标设定与月跑量进度）；🔒 不在同一个跑团的用户之间不能相互查看具体运动记录。
          </text>
        </view>

        <!-- 汇总小指标 -->
        <view style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12rpx; margin-bottom: 18rpx;">
          <view class="nm-kpi-tile" style="padding: 14rpx 16rpx;" @click="openNewMembersScope('unaffiliated')">
            <text class="nm-kpi-val highlight" style="font-size: 30rpx;">{{ unaffiliatedSummary.total_members }}<text class="nm-kpi-unit">人</text></text>
            <text class="nm-kpi-label" style="font-size: 20rpx;">🌍 自由跑友</text>
          </view>
          <view class="nm-kpi-tile" style="padding: 14rpx 16rpx;" @click="openNewMembersScope('unaffiliated')">
            <text class="nm-kpi-val ok" style="font-size: 30rpx;">{{ unaffiliatedSummary.watch_bound_count }}<text class="nm-kpi-unit">人</text></text>
            <text class="nm-kpi-label" style="font-size: 20rpx;">⌚ 已绑表</text>
          </view>
          <view class="nm-kpi-tile" style="padding: 14rpx 16rpx;" @click="openNewMembersScope('unaffiliated')">
            <text class="nm-kpi-val" :class="unaffiliatedSummary.goal_set_count > 0 ? 'ok' : 'warn'" style="font-size: 30rpx;">{{ unaffiliatedSummary.goal_set_count }}<text class="nm-kpi-unit">人</text></text>
            <text class="nm-kpi-label" style="font-size: 20rpx;">🎯 已设目标</text>
          </view>
        </view>

        <!-- 前3位自由跑友同伴预览 -->
        <view v-if="unaffiliatedPreviewList.length > 0" style="display: flex; flex-direction: column; gap: 12rpx;">
          <view
            v-for="m in unaffiliatedPreviewList"
            :key="m.user_id"
            style="display: flex; align-items: center; justify-content: space-between; padding: 14rpx 18rpx; border-radius: 16rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.08));"
            @click="openMemberRunnerAnalysis(m)"
          >
            <view style="display: flex; align-items: center; gap: 14rpx; min-width: 0; flex: 1;">
              <image
                class="nm-avatar"
                style="width: 64rpx; height: 64rpx;"
                :src="m.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                mode="aspectFill"
              />
              <view style="display: flex; flex-direction: column; gap: 4rpx; min-width: 0; flex: 1;">
                <view style="display: flex; align-items: center; gap: 8rpx; flex-wrap: wrap;">
                  <text style="font-size: 25rpx; font-weight: 700; color: var(--rgm-text, #fff);">{{ m.display_name || '自由跑友' }}</text>
                  <text class="nm-status-tag" :class="m.watch_bound ? 'ok' : 'warn'" style="font-size: 18rpx;">
                    {{ m.watch_bound ? (m.watch_status_label || '已绑表') : '未绑表' }}
                  </text>
                  <text class="nm-status-tag" :class="m.goal_set ? 'ok' : 'warn'" style="font-size: 18rpx;">
                    {{ m.goal_set ? '已设目标' : '未设目标' }}
                  </text>
                </view>
                <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa);">
                  本月 {{ m.month_km || 0 }} / {{ m.monthly_target_km || 200 }} km · 周目标 {{ m.weekly_target_km || 50 }} km
                </text>
              </view>
            </view>
            <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa); margin-left: 10rpx;">基本状态 ›</text>
          </view>
        </view>
      </view>

      <!-- All Created Clubs List -->
      <view class="section-card all-clubs-sec">
        <view class="sec-title-row">
          <view class="title-left">
            <text class="sec-title">🏆 平台跑团列表</text>
            <text class="count-tag">{{ filteredClubs.length }} / {{ allClubs.length }} 个跑团</text>
          </view>
        </view>

        <!-- 跑团所在地搜索与城市快捷筛选 -->
        <view class="club-search-filter-box">
          <view class="club-search-bar">
            <text class="csb-search-icon">🔍</text>
            <input
              class="csb-input"
              type="text"
              placeholder="按城市(如上海/北京)或名称搜索跑团..."
              v-model="clubSearchText"
            />
            <text v-if="clubSearchText" class="csb-clear-icon" @click="clubSearchText = ''">✕</text>
          </view>

          <!-- 城市快捷标签横向滚动 -->
          <scroll-view scroll-x class="city-chips-scroll" :show-scrollbar="false">
            <view class="city-chips-row">
              <view
                v-for="ct in availableCities"
                :key="ct"
                class="city-chip"
                :class="{ active: selectedCityFilter === ct }"
                @click="selectedCityFilter = ct"
              >
                <text class="city-chip-text">{{ ct }}</text>
              </view>
            </view>
          </scroll-view>
        </view>

        <view v-if="filteredClubs.length === 0" class="empty-clubs-text">
          {{ clubSearchText || selectedCityFilter !== '全部' ? `未找到【${selectedCityFilter !== '全部' ? selectedCityFilter + ' ' : ''}${clubSearchText}】的相关跑团` : '暂无跑团' }}
        </view>

        <view v-else class="clubs-list-wrap">
          <!-- 1. 大群下属分队分组（仅已加入大群的用户可见） -->
          <view v-if="filteredOrgClubs.length > 0" class="club-group-block org-group-block">
            <view class="cgb-header org-header">
              <view class="cgb-title-row">
                <text class="cgb-title">🏛️ {{ currentOrg?.name || filteredOrgClubs[0]?.org_name || '大群' }} · 下属分队 ({{ filteredOrgClubs.length }})</text>
              </view>
            </view>
            <view v-for="club in filteredOrgClubs" :key="club.id" class="club-select-card is-org-subclub">
              <image class="csc-logo" :src="club.logo_url || '/static/logo-square.png'" mode="aspectFill" />
              <view class="csc-body">
                <view class="csc-title-row">
                  <text class="csc-name">{{ club.name }}</text>
                </view>
                <view class="csc-badges-row">
                  <text class="org-tag-pill">🏛️ {{ club.org_name || currentOrg?.name || '大群' }}分队</text>
                  <text class="mode-badge-pill" :class="club.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                    {{ club.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                  </text>
                  <text class="csc-city">📍 {{ club.city || "上海" }}</text>
                </view>
                <text v-if="club.description" class="csc-desc">{{ club.description }}</text>
                <view class="csc-meta-row">
                  <text class="csc-meta">团长: {{ club.owner_name || "平台指定" }}</text>
                  <text class="csc-dot">·</text>
                  <text class="csc-meta highlight">{{ club.member_count || 1 }} 位成员</text>
                </view>
              </view>
              <button class="csc-join-btn" :class="{ 'btn-invite-mode': club.join_mode === 'invite' }" :loading="joiningClubId === club.id" @click="handleJoinClubWithCheck(club)">
                {{ club.join_mode === 'invite' ? '🔑 凭码加入' : '加入' }}
              </button>
            </view>
          </view>

          <!-- 2. 独立公开跑团分组 -->
          <view v-if="filteredIndepClubs.length > 0" class="club-group-block indep-group-block">
            <view class="cgb-header indep-header">
              <view class="cgb-title-row">
                <text class="cgb-title">🌐 独立公开跑团 ({{ filteredIndepClubs.length }})</text>
              </view>
            </view>
            <view v-for="club in filteredIndepClubs" :key="club.id" class="club-select-card">
              <image class="csc-logo" :src="club.logo_url || '/static/logo-square.png'" mode="aspectFill" />
              <view class="csc-body">
                <view class="csc-title-row">
                  <text class="csc-name">{{ club.name }}</text>
                </view>
                <view class="csc-badges-row">
                  <text class="org-tag-pill free-tag">🌐 独立跑团</text>
                  <text class="mode-badge-pill" :class="club.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                    {{ club.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                  </text>
                  <text class="csc-city">📍 {{ club.city || "上海" }}</text>
                </view>
                <text v-if="club.description" class="csc-desc">{{ club.description }}</text>
                <view class="csc-meta-row">
                  <text class="csc-meta">团长: {{ club.owner_name || "平台指定" }}</text>
                  <text class="csc-dot">·</text>
                  <text class="csc-meta highlight">{{ club.member_count || 1 }} 位成员</text>
                </view>
              </view>
              <button class="csc-join-btn" :class="{ 'btn-invite-mode': club.join_mode === 'invite' }" :loading="joiningClubId === club.id" @click="handleJoinClubWithCheck(club)">
                {{ club.join_mode === 'invite' ? '🔑 凭码加入' : '加入' }}
              </button>
            </view>
          </view>
        </view>
      </view>

    </view>

    <!-- 子页面：新队员管理 & 未入团自由跑友名册（加入/注册时间、手表绑定状态、周/月目标设定状态） -->
    <template v-if="activeSection === 'new_members'">
      <view class="section-card new-members-section">
        <!-- 超管双视角切换：本团新队员 vs 未入团自由跑友 -->
        <view
          v-if="isSuperAdmin && currentClub"
          class="nm-filter-row"
          style="margin-bottom: 20rpx; padding-bottom: 16rpx; border-bottom: 1rpx solid var(--rgm-line, rgba(255,255,255,0.08));"
        >
          <view
            class="nm-filter-pill"
            :class="{ active: newMemberScope === 'club' }"
            @click="switchNewMemberScope('club')"
          >
            <text>🏃 本团新队员 ({{ clubNewMembersSummary.total_members }})</text>
          </view>
          <view
            class="nm-filter-pill"
            :class="{ active: newMemberScope === 'unaffiliated' }"
            @click="switchNewMemberScope('unaffiliated')"
          >
            <text>🌍 未入团自由跑友 ({{ unaffiliatedSummary.total_members }})</text>
          </view>
        </view>

        <view class="card-header-row">
          <view class="title-with-icon">
            <text class="icon">{{ newMemberScope === 'unaffiliated' ? '🌍' : '🌱' }}</text>
            <text class="card-title">
              {{ newMemberScope === 'unaffiliated' ? (isSuperAdmin ? `未入团自由跑友名册 (${newMembersSortedList.length})` : `自由跑友同伴 · 基本状态 (${newMembersSortedList.length})`) : `新队员与入团设定 (${newMembersSortedList.length})` }}
            </text>
          </view>
          <view class="header-btn-group">
            <button
              class="mini-action-btn"
              :loading="newMemberScope === 'unaffiliated' ? loadingUnaffiliated : loadingNewMembers"
              @click="newMemberScope === 'unaffiliated' ? fetchUnaffiliatedMembersStatus() : fetchNewMembersStatus()"
            >
              🔄 刷新
            </button>
          </view>
        </view>

        <!-- 未入团范围说明横幅 -->
        <view
          v-if="newMemberScope === 'unaffiliated'"
          style="padding: 14rpx 18rpx; border-radius: 14rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.08)); margin-bottom: 20rpx;"
        >
          <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa); line-height: 1.45; display: block;">
            {{ isSuperAdmin ? '👑 超级管理员全局名册：展示尚未加入任何跑团的注册用户及其绑表、周/月目标状态，支持一键提醒与查看档案。' : '🤝 自由跑友同伴互看：未入团用户之间可相互查看基本状态（绑表、目标设定与月跑量进度）；🔒 不在同一个跑团的用户之间不能相互查看具体运动记录。' }}
          </text>
        </view>

        <!-- 顶部4格核心状态汇总 -->
        <view class="nm-kpi-grid">
          <view class="nm-kpi-tile" @click="newMemberFilter = 'recent'">
            <text class="nm-kpi-val highlight">{{ newMembersSummary.new_7d_count }}<text class="nm-kpi-unit">人</text></text>
            <text class="nm-kpi-label">{{ newMemberScope === 'unaffiliated' ? '🌱 近7天新注册' : '🌱 近7天新入团' }}</text>
            <text class="nm-kpi-sub">近30天 {{ newMembersSummary.new_30d_count }}人</text>
          </view>
          <view class="nm-kpi-tile" @click="newMemberFilter = 'pending'">
            <text class="nm-kpi-val" :class="newMembersSummary.watch_unbound_count > 0 ? 'warn' : 'ok'">
              {{ newMembersSummary.watch_bound_count }}/{{ newMembersSummary.total_members }}
            </text>
            <text class="nm-kpi-label">⌚ 手表已绑定</text>
            <text class="nm-kpi-sub">{{ newMembersSummary.watch_unbound_count > 0 ? `未绑 ${newMembersSummary.watch_unbound_count}人` : '全员已绑表' }}</text>
          </view>
          <view class="nm-kpi-tile" @click="newMemberFilter = 'pending'">
            <text class="nm-kpi-val" :class="newMembersSummary.goal_unset_count > 0 ? 'warn' : 'ok'">
              {{ newMembersSummary.goal_set_count }}/{{ newMembersSummary.total_members }}
            </text>
            <text class="nm-kpi-label">🎯 目标已设定</text>
            <text class="nm-kpi-sub">{{ newMembersSummary.goal_unset_count > 0 ? `未设 ${newMembersSummary.goal_unset_count}人` : '全员已定目标' }}</text>
          </view>
          <view class="nm-kpi-tile" @click="newMemberFilter = 'pending'">
            <text class="nm-kpi-val" :class="newMembersSummary.pending_setup_count > 0 ? 'warn' : 'ok'">
              {{ newMembersSummary.pending_setup_count }}<text class="nm-kpi-unit">人</text>
            </text>
            <text class="nm-kpi-label">⚠️ 待完善设置</text>
            <text class="nm-kpi-sub">{{ (isSuperAdmin || newMemberScope === 'club') ? '可一键提醒跑友' : '绑表与目标状态' }}</text>
          </view>
        </view>

        <!-- 筛选胶囊与搜索栏 -->
        <view class="nm-filter-row">
          <view
            class="nm-filter-pill"
            :class="{ active: newMemberFilter === 'all' }"
            @click="newMemberFilter = 'all'"
          >
            <text>全部 ({{ newMembersSortedList.length }})</text>
          </view>
          <view
            class="nm-filter-pill"
            :class="{ active: newMemberFilter === 'recent' }"
            @click="newMemberFilter = 'recent'"
          >
            <text>🌱 近30天 ({{ newMembersSummary.new_30d_count }})</text>
          </view>
          <view
            class="nm-filter-pill"
            :class="{ active: newMemberFilter === 'pending' }"
            @click="newMemberFilter = 'pending'"
          >
            <text>⚠️ 待完善 ({{ newMembersSummary.pending_setup_count }})</text>
          </view>
          <view
            class="nm-filter-pill"
            :class="{ active: newMemberFilter === 'ready' }"
            @click="newMemberFilter = 'ready'"
          >
            <text>✅ 已配齐 ({{ Math.max(0, newMembersSummary.total_members - newMembersSummary.pending_setup_count) }})</text>
          </view>
        </view>

        <input
          v-if="newMembersSortedList.length > 5"
          class="nm-search-input"
          type="text"
          placeholder="🔍 搜索跑友昵称..."
          v-model="newMemberSearchQuery"
        />

        <!-- 队员/跑友入团与状态卡片列表（按加入/注册时间倒序） -->
        <view v-if="filteredNewMembersList.length > 0" class="nm-card-list">
          <view
            v-for="m in filteredNewMembersList"
            :key="m.user_id"
            class="nm-member-card"
            :class="{ 'is-pending': !m.watch_bound || !m.goal_set }"
          >
            <!-- 顶部：头像、姓名、角色、入团/注册时间标签 -->
            <view class="nm-card-top">
              <view class="nm-user-left">
                <image
                  class="nm-avatar"
                  :src="m.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                  mode="aspectFill"
                />
                <view class="nm-user-meta">
                  <view class="nm-name-row">
                    <text class="nm-name">{{ m.display_name || '新跑友' }}</text>
                    <text v-if="newMemberScope === 'unaffiliated'" class="m-role-tag tag-member">
                      {{ m.user_id === user?.id ? '🙋 我 · 自由跑友' : '🌍 自由跑友' }}
                    </text>
                    <text v-else class="m-role-tag" :class="'tag-' + (m.role || 'member')">
                      {{ m.role === 'owner' ? '👑 团长' : m.role === 'coach' ? '🧢 教练' : '🏃 队员' }}
                    </text>
                    <text v-if="m.is_new_7d" class="nm-new-badge">
                      {{ newMemberScope === 'unaffiliated' ? '🌱 新注册' : '🌱 新队员' }}
                    </text>
                  </view>
                  <text class="nm-join-time">
                    ⏰ {{ newMemberScope === 'unaffiliated' ? '注册时间' : '加入时间' }}：{{ m.joined_at_display || (m.joined_at || '').replace('T', ' ').substring(0, 16) || '早期注册' }}
                  </text>
                </view>
              </view>
              <text class="nm-rel-pill" :class="{ recent: m.is_new_7d }">
                {{ m.joined_relative_label || (newMemberScope === 'unaffiliated' ? '未入团' : '已入团') }}
              </text>
            </view>

            <!-- 中部：手表绑定状态 & 目标设定状态 双栏对照 -->
            <view class="nm-status-grid">
              <view class="nm-status-box" :class="m.watch_bound ? 'status-ok' : 'status-warn'">
                <view class="nm-status-head">
                  <text class="nm-status-title">⌚ 手表绑定</text>
                  <text class="nm-status-tag" :class="m.watch_bound ? 'ok' : 'warn'">
                    {{ m.watch_bound ? (m.watch_status_label || '已绑表') : '未绑定' }}
                  </text>
                </view>
                <text class="nm-status-desc">
                  {{ m.total_runs_count > 0 ? `累计 ${m.total_runs_count} 次 · 本月 ${m.month_km || 0}km` : (m.watch_bound ? `本月跑量 ${m.month_km || 0}km` : '尚未绑定佳明/高驰/苹果/华为') }}
                </text>
              </view>

              <view class="nm-status-box" :class="m.goal_set ? 'status-ok' : 'status-warn'">
                <view class="nm-status-head">
                  <text class="nm-status-title">🎯 目标设定</text>
                  <text class="nm-status-tag" :class="m.goal_set ? 'ok' : 'warn'">
                    {{ m.goal_set ? '已设定' : '未设目标' }}
                  </text>
                </view>
                <text class="nm-status-desc">
                  周 {{ m.weekly_target_km || 50 }}km · 月 {{ m.monthly_target_km || m.target_km || 200 }}km{{ m.has_training_plan ? ' · 📋已排课' : '' }}
                </text>
              </view>
            </view>

            <!-- 底部操作栏：提醒完善 / 查看跑力或基本状态名片 / 团长移出队员 -->
            <view class="nm-actions-row">
              <button
                v-if="(isSuperAdmin || (newMemberScope === 'club' && isClubManager)) && (!m.watch_bound || !m.goal_set) && m.user_id !== user?.id"
                class="nm-act-btn remind"
                :loading="remindingMemberUid === m.user_id"
                @click="handleRemindMemberSetup(m)"
              >
                🔔 提醒完善绑表/目标
              </button>
              <button
                class="nm-act-btn inspect"
                @click="openMemberRunnerAnalysis(m)"
              >
                {{ (isSuperAdmin || newMemberScope === 'club' || m.user_id === user?.id) ? '📊 查看跑力档案' : '👤 查看基本状态 · 🔒 运动记录保密' }}
              </button>
              <button
                v-if="newMemberScope === 'club' && !currentClub?.is_virtual_unaffiliated && (currentRole === 'owner' || isOwnerOrDev || isSuperAdmin) && m.role !== 'owner' && m.user_id !== user?.id"
                class="nm-act-btn remove"
                @click="openRemoveMemberConfirmModal(m)"
              >
                🚪 移出
              </button>
            </view>
          </view>
        </view>
        <view v-else class="empty-box">
          <text class="empty-text">暂无符合筛选条件的跑友记录</text>
        </view>
      </view>
    </template>

    <!-- 子页面：大群（铭牌、实名状态、分队与管理入口） -->
    <!-- ── 🏛️ 大群体组织铭牌 (若已认证加入复旦戈等大组织) ── -->
    <view v-if="currentOrg && activeSection === 'org'" class="org-banner-card">
      <view class="org-banner-top">
        <view class="org-badge-box">
          <text class="org-badge-icon">🏛️</text>
          <text class="org-badge-title">{{ currentOrg.name }} 大群</text>
          <text class="org-auth-status" :class="currentOrg.status">
            {{ currentOrg.status === 'confirmed' ? '✓ 戈友已认证' : currentOrg.status === 'temporary' ? `⚠️ 临时人员 (剩${currentOrg.remaining_days ?? 14}天)` : currentOrg.status === 'pending' ? `⏳ 待审核 (剩${currentOrg.remaining_days ?? 14}天)` : currentOrg.status === 'expired' ? '🚫 已过期' : '⏳ 待核对' }}
          </text>
        </view>
        <view class="org-right-actions">
          <!-- #ifdef MP-WEIXIN -->
          <button
            class="subclubs-tag-btn org-share-tag-btn"
            open-type="share"
            data-share-type="org"
            :data-org-id="currentOrg?.id"
            :data-org-name="currentOrg?.name"
            :data-invite-code="currentOrg?.invite_code || ''"
          >
            <text class="subclubs-tag-text">📢 邀请戈友 ›</text>
          </button>
          <!-- #endif -->
          <view class="subclubs-tag-btn" @click="openSubClubsModal">
            <text class="subclubs-tag-text">🏃 分队 ({{ orgSubClubs.length }}) ›</text>
          </view>
        </view>
      </view>

      <!-- 大群主理人 / 管理员专属管理胶囊网格（独立分行，彻底告别单行挤压竖排） -->
      <view v-if="isOrgAdmin" class="org-admin-pills-grid">
        <view class="org-admin-pill-item primary" @click="openOrgReportModal">
          <text class="oap-label">📊 全域报表与分团 PK</text>
          <text class="oap-arrow">›</text>
        </view>
        <view class="org-admin-pill-item" @click="openOrgEventsModal">
          <text class="oap-label">🚩 跨跑团联合活动</text>
          <text class="oap-arrow">›</text>
        </view>
        <view class="org-admin-pill-item" @click="openOrgJoinModeModal">
          <text class="oap-label">⚙️ 大群设定与邀请码</text>
          <text class="oap-arrow">›</text>
        </view>
        <view class="org-admin-pill-item" @click="openOrgFieldRulesModal">
          <text class="oap-label">🛡️ 准入字段(必/选/隐)</text>
          <text class="oap-arrow">›</text>
        </view>
        <view class="org-admin-pill-item span-2" @click="openOrgMembersModal">
          <text class="oap-label">👥 戈友花名册与审核管理 ({{ orgMembers.length }}人)</text>
          <text class="oap-arrow">查看 ›</text>
        </view>
      </view>

      <view class="org-meta-pill-row">
        <text class="org-meta-pill">👤 {{ currentOrg.real_name || '未填实名' }}</text>
        <text class="org-meta-pill highlight">🎓 {{ currentOrg.class_name || '商学院班级' }}</text>
        <text v-if="currentOrg.gobi_experience" class="org-meta-pill gobi-pill" :class="{ veteran: currentOrg.gobi_experience !== '新戈' }">
          {{ currentOrg.gobi_experience === '新戈' ? '🌱 新戈' : '🏅 ' + currentOrg.gobi_experience }}
        </text>
        <text class="org-meta-pill">🏅 {{ currentOrg.age_group || getAgeGroup(currentOrg.date_of_birth) }}</text>
        <text class="org-meta-pill">🚻 {{ currentOrg.gender === 'female' ? '女' : '男' }}</text>
      </view>

      <!-- 临时人员 / 待审核 / 过期 醒目标识栏 -->
      <view v-if="currentOrg.status === 'temporary'" class="org-status-alert-strip temp-strip">
        <view class="osas-left">
          <text class="osas-title">⏰ 请在 {{ currentOrg.remaining_days ?? 14 }} 天内补齐大群资料{{ formatDeadlineDate(currentOrg.deadline_at) ? `（截止 ${formatDeadlineDate(currentOrg.deadline_at)}）` : '' }}</text>
          <text class="osas-desc">
            {{ currentOrg.missing_required_fields && currentOrg.missing_required_fields.length > 0 
                ? '尚缺：' + currentOrg.missing_required_fields.join('、') + '，逾期将移出大群跑团'
                : '逾期未补齐将移出大群跑团' }}
          </text>
        </view>
        <button class="osas-btn" @click="openOrgEditProfileModal">✏️ 立即补填</button>
      </view>
      <view v-else-if="currentOrg.status === 'pending'" class="org-status-alert-strip pending-strip">
        <view class="osas-left">
          <text class="osas-title">⏳ 资料已提交，等待管理员审核（剩余 {{ currentOrg.remaining_days ?? 14 }} 天）</text>
        </view>
        <button class="osas-btn outline" @click="openOrgEditProfileModal">修改资料</button>
      </view>
      <view v-else-if="currentOrg.status === 'confirmed'" class="org-status-alert-strip confirmed-strip">
        <view class="osas-left">
          <text class="osas-title">🏅 正式成员</text>
        </view>
        <button class="osas-btn outline" @click="openOrgEditProfileModal">✏️ 查看/修改资料</button>
      </view>
      <view v-else-if="currentOrg.status === 'expired'" class="org-status-alert-strip expired-strip">
        <view class="osas-left">
          <text class="osas-title">🚫 资料补填期限（14 天）已过</text>
          <text class="osas-desc">已移出大群跑团，补齐资料后重新审核。</text>
        </view>
        <button class="osas-btn" @click="openOrgEditProfileModal">✏️ 补齐资料</button>
      </view>
    </view>

    <!-- ── 🏛️ 未加入大组织认证入口 (选填，支持多大群体) ── -->
    <!-- 未加入大群：在「大群」子页面显示；未加入跑团的用户也在首页跑团列表下方看到 -->
    <view v-if="!currentOrg && (activeSection === 'org' || (!activeSection && !currentClub))" class="grand-org-prompt-card">
      <view class="gop-badge-row">
        <text class="gop-badge">🏛️ 大群认证</text>
        <text class="gop-code-pill" :class="targetDefaultOrg?.join_mode === 'free' ? 'pill-free' : 'pill-invite'">
          {{ targetDefaultOrg?.join_mode === 'free' ? '🟢 自由入会' : '🔒 需邀请码' }}
        </text>
      </view>
      <text class="gop-title">加入【{{ targetDefaultOrg?.name || '高校戈友' }}】大群</text>
      <view class="gop-btn-group">
        <button class="gop-join-btn" :class="{ 'btn-free-mode': targetDefaultOrg?.join_mode === 'free' }" @click="openOrgJoinModal()">
          {{ targetDefaultOrg?.join_mode === 'free' ? '🟢 实名加入' : '🔑 凭码认证加入' }}
        </button>
      </view>
    </view>


    <!-- 未加入跑团：介绍类卡片放在跑团列表和大群提示之后 -->
    <view v-if="!currentClub && !activeSection" class="unjoined-extra">
      <view class="section-card unjoined-highlights">
        <text class="unjoined-sec-title">加入跑团即可解锁：</text>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🥇</text>
          <view class="uh-content">
            <text class="uh-title">跑团月度跑量英雄榜</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🏆</text>
          <view class="uh-content">
            <text class="uh-title">专属跑量挑战赛与活动</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">💬</text>
          <view class="uh-content">
            <text class="uh-title">跑友圈动态与 Canova教练互动</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🧢</text>
          <view class="uh-content">
            <text class="uh-title">全队体能罗盘</text>
          </view>
        </view>
      </view>
      <!-- ── 🚀 新手设定引导入口卡片 (快速一键配齐资料、跑团与手表) ── -->
      <view class="onboard-guide-banner" @click="goToOnboarding">
        <view class="ogb-left">
          <view class="ogb-icon-circle">🚀</view>
          <view class="ogb-meta">
            <view class="ogb-title-row">
              <text class="ogb-title">新手设定向导</text>
              <text class="ogb-tag">4 步向导</text>
            </view>
          </view>
        </view>
        <view class="ogb-action-pill">
          <text class="ogb-action-txt">开始设定 ›</text>
        </view>
      </view>

      <!-- ── 🏃 自由跑者独立训练模式专属卡片 ── -->
      <view class="solo-runner-card">
        <view class="src-top-row">
          <view class="src-badge-box">
            <text class="src-badge-icon">🏃</text>
            <text class="src-badge-text">自由跑者独立训练中</text>
          </view>
        </view>
        <text class="src-title">无需入团，全功能开放</text>
        <view class="src-actions-row">
          <button class="src-btn outline" @click="goToIndexPage">
            ⌚ 首页打卡与手表同步
          </button>
          <button class="src-btn primary" @click="goToCoachPage">
            💬 咨询 Canova教练
          </button>
        </view>
      </view>

    </view>

    <!-- ── Member & Coach Management Modal (跑团成员与指定教练管理) ── -->
    <view v-if="showMembersModal" class="modal-mask" @click="showMembersModal = false">
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">跑团成员与指定教练</text>
            <text class="count-pill">{{ members.length }}人</text>
          </view>
          <text class="close-btn" @click="showMembersModal = false">✕</text>
        </view>

        <input
          class="search-member-input"
          type="text"
          :adjust-position="false"
          :cursor-spacing="30"
          placeholder="🔍 搜索成员昵称..."
          v-model="memberSearchQuery"
        />

        <scroll-view scroll-y class="members-scroll">
          <view v-for="m in filteredMembers" :key="m.user_id" class="member-row">
            <view class="m-left">
              <image class="m-avatar" :src="m.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="m-info">
                <view class="m-name-line">
                  <text class="m-name">{{ m.display_name || '跑友' }}</text>
                  <text class="m-role-tag" :class="'tag-' + m.role">
                    {{ m.role === 'owner' ? '👑 团长' : m.role === 'coach' ? '🧢 教练' : '🏃 团员' }}
                  </text>
                </view>
                <text class="m-sub-text">当月跑量: {{ m.month_km || 0 }} km · 加入时间: {{ (m.joined_at || '').substring(0, 10) }}</text>
              </view>
            </view>

            <!-- Action buttons for Owner -->
            <view v-if="m.role !== 'owner' && (currentRole === 'owner' || isOwnerOrDev || isSuperAdmin)" class="m-actions">
              <button
                v-if="m.role !== 'coach'"
                class="act-pill coach-pill"
                @click="handleChangeRole(m.user_id, 'coach')"
              >
                🧢 指定教练
              </button>
              <button
                v-else
                class="act-pill member-pill"
                @click="handleChangeRole(m.user_id, 'member')"
              >
                🏃 取消教练
              </button>
              <button
                class="act-pill del-pill"
                @click="openRemoveMemberConfirmModal(m)"
              >
                移出
              </button>
            </view>
            <view v-else class="owner-static-tag">
              <text class="owner-tag-text">{{ m.role === 'owner' ? '团长' : (m.role === 'coach' ? '教练' : '团员') }}</text>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── 🛡️ 防误触：团长移出队员二次确认弹窗 (Anti-Misoperation Remove Member Modal) ── -->
    <view v-if="showRemoveMemberConfirmModal && targetMemberToRemove" class="modal-mask" @touchmove.stop.prevent>
      <view class="modal-content" style="max-width: 640rpx; border: 2rpx solid rgba(239, 68, 68, 0.45);" @click.stop>
        <view class="modal-header" style="border-bottom: 1rpx solid rgba(239, 68, 68, 0.2); padding-bottom: 20rpx;">
          <view style="display: flex; align-items: center; gap: 10rpx;">
            <text style="font-size: 34rpx;">⚠️</text>
            <text class="modal-title" style="color: #ef4444;">防误触 · 移出跑团成员确认</text>
          </view>
          <text class="close-btn" @click="closeRemoveMemberConfirmModal">✕</text>
        </view>

        <view style="padding: 24rpx 0; display: flex; flex-direction: column; gap: 20rpx;">
          <!-- 被移出队员身份核对卡 -->
          <view style="display: flex; align-items: center; gap: 20rpx; padding: 20rpx; border-radius: 20rpx; background: rgba(239, 68, 68, 0.08); border: 1rpx solid rgba(239, 68, 68, 0.28);">
            <image
              :src="targetMemberToRemove.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
              mode="aspectFill"
              style="width: 88rpx; height: 88rpx; border-radius: 50%; border: 2rpx solid rgba(239, 68, 68, 0.45); flex-shrink: 0;"
            />
            <view style="display: flex; flex-direction: column; gap: 6rpx; flex: 1; min-width: 0;">
              <view style="display: flex; align-items: center; gap: 10rpx; flex-wrap: wrap;">
                <text style="font-size: 30rpx; font-weight: 800; color: var(--rgm-text, #0f172a);">
                  {{ targetMemberToRemove.display_name || '该成员' }}
                </text>
                <text style="font-size: 20rpx; padding: 2rpx 12rpx; border-radius: 999rpx; background: rgba(239, 68, 68, 0.16); color: #ef4444; font-weight: 700;">
                  {{ targetMemberToRemove.role === 'coach' ? '🧢 教练' : '🏃 队员' }}
                </text>
              </view>
              <text style="font-size: 22rpx; color: var(--rgm-text-2, #475569);">
                加入时间：{{ (targetMemberToRemove.joined_at_display || targetMemberToRemove.joined_at || '近期').substring(0, 16) }} · 本月 {{ targetMemberToRemove.month_km || 0 }} km
              </text>
            </view>
          </view>

          <!-- 影响说明 -->
          <view style="padding: 20rpx; border-radius: 18rpx; background: var(--rgm-card-2, #f8fafc); border: 1rpx solid var(--rgm-line, #e2e8f0); display: flex; flex-direction: column; gap: 10rpx;">
            <text style="font-size: 23rpx; font-weight: 700; color: var(--rgm-text, #0f172a);">📌 移出说明（请仔细核对）：</text>
            <text style="font-size: 22rpx; color: var(--rgm-text-2, #475569); line-height: 1.55;">
              1. 移出后，【{{ targetMemberToRemove.display_name || '该成员' }}】将离开跑团【{{ currentClub?.name }}】，不再参与本团排行榜与打卡动态。
            </text>
            <text style="font-size: 22rpx; color: #059669; font-weight: 600; line-height: 1.55;">
              2. 🛡️ 该跑友个人的所有历史跑步记录、手表绑定与跑力档案 100% 完整保留，不受任何影响。
            </text>
          </view>

          <!-- 二次防误触勾选框 -->
          <view
            style="display: flex; align-items: center; gap: 14rpx; padding: 18rpx 20rpx; border-radius: 16rpx; cursor: pointer;"
            :style="removeMemberChecked
              ? 'background: rgba(239, 68, 68, 0.12); border: 2rpx solid #ef4444;'
              : 'background: var(--rgm-card-2, #f1f5f9); border: 2rpx dashed #94a3b8;'"
            @click="removeMemberChecked = !removeMemberChecked"
          >
            <text style="font-size: 32rpx;">{{ removeMemberChecked ? '☑️' : '⬜' }}</text>
            <text style="font-size: 24rpx; font-weight: 700; color: var(--rgm-text, #0f172a); line-height: 1.4;">
              我已核对【{{ targetMemberToRemove.display_name || '该成员' }}】身份，确认将其移出本跑团
            </text>
          </view>
        </view>

        <view style="display: flex; gap: 18rpx; margin-top: 8rpx;">
          <button
            style="flex: 1; height: 80rpx; line-height: 80rpx; border-radius: 18rpx; font-size: 26rpx; font-weight: 700; background: var(--rgm-card-2, #e2e8f0); color: var(--rgm-text, #334155); margin: 0;"
            @click="closeRemoveMemberConfirmModal"
          >
            取消，保留队员
          </button>
          <button
            :disabled="!removeMemberChecked || removeMemberCountdown > 0 || removingMemberLoading"
            :loading="removingMemberLoading"
            style="flex: 1.3; height: 80rpx; line-height: 80rpx; border-radius: 18rpx; font-size: 26rpx; font-weight: 800; margin: 0;"
            :style="(!removeMemberChecked || removeMemberCountdown > 0)
              ? 'background: #94a3b8; color: #ffffff; opacity: 0.65;'
              : 'background: #ef4444; color: #ffffff; box-shadow: 0 8rpx 20rpx rgba(239, 68, 68, 0.35);'"
            @click="confirmRemoveMemberExecution"
          >
            {{ removeMemberCountdown > 0 ? `请核对 (${removeMemberCountdown}s)` : (removeMemberChecked ? '确认移出该队员' : '请先勾选上方确认') }}
          </button>
        </view>
      </view>
    </view>

    <!-- ── 🛡️ 防误触：队员主动退出跑团二次确认弹窗 (Anti-Misoperation Leave Club Modal) ── -->
    <view v-if="showLeaveClubConfirmModal && currentClub" class="modal-mask" @touchmove.stop.prevent>
      <view class="modal-content" style="max-width: 640rpx; border: 2rpx solid rgba(239, 68, 68, 0.45);" @click.stop>
        <view class="modal-header" style="border-bottom: 1rpx solid rgba(239, 68, 68, 0.2); padding-bottom: 20rpx;">
          <view style="display: flex; align-items: center; gap: 10rpx;">
            <text style="font-size: 34rpx;">🚪</text>
            <text class="modal-title" style="color: #ef4444;">防误触 · 退出跑团确认</text>
          </view>
          <text class="close-btn" @click="closeLeaveClubConfirmModal">✕</text>
        </view>

        <view style="padding: 24rpx 0; display: flex; flex-direction: column; gap: 20rpx;">
          <!-- 即将退出的跑团信息卡 -->
          <view style="display: flex; align-items: center; gap: 20rpx; padding: 20rpx; border-radius: 20rpx; background: rgba(239, 68, 68, 0.08); border: 1rpx solid rgba(239, 68, 68, 0.28);">
            <image
              :src="currentClub.logo_url || '/static/logo-square.png'"
              mode="aspectFill"
              style="width: 88rpx; height: 88rpx; border-radius: 20rpx; border: 2rpx solid rgba(239, 68, 68, 0.45); flex-shrink: 0;"
            />
            <view style="display: flex; flex-direction: column; gap: 6rpx; flex: 1; min-width: 0;">
              <text style="font-size: 30rpx; font-weight: 800; color: var(--rgm-text, #0f172a);">
                {{ currentClub.name }}
              </text>
              <text style="font-size: 22rpx; color: var(--rgm-text-2, #475569);">
                📍 {{ currentClub.city || '上海' }} · 当前身份：{{ currentRole === 'coach' ? '🧢 认证教练' : '🏃 跑团成员' }}
              </text>
            </view>
          </view>

          <!-- 退出跑团说明 -->
          <view style="padding: 20rpx; border-radius: 18rpx; background: var(--rgm-card-2, #f8fafc); border: 1rpx solid var(--rgm-line, #e2e8f0); display: flex; flex-direction: column; gap: 10rpx;">
            <text style="font-size: 23rpx; font-weight: 700; color: var(--rgm-text, #0f172a);">📌 退出跑团说明：</text>
            <text style="font-size: 22rpx; color: var(--rgm-text-2, #475569); line-height: 1.55;">
              1. 退出后，您将离开【{{ currentClub.name }}】的月度英雄榜、跑友圈打卡动态与跑团约跑活动。
            </text>
            <text style="font-size: 22rpx; color: #059669; font-weight: 600; line-height: 1.55;">
              2. 🛡️ 您的所有个人跑步记录、手表连接、VDOT 跑力与个人训练计划 100% 完整保留，绝不丢失。
            </text>
            <text style="font-size: 22rpx; color: var(--rgm-text-2, #475569); line-height: 1.55;">
              3. 若本跑团开启了邀请码准入，后续重新加入需再次输入邀请码。
            </text>
          </view>

          <!-- 二次防误触勾选框 -->
          <view
            style="display: flex; align-items: center; gap: 14rpx; padding: 18rpx 20rpx; border-radius: 16rpx; cursor: pointer;"
            :style="leaveClubChecked
              ? 'background: rgba(239, 68, 68, 0.12); border: 2rpx solid #ef4444;'
              : 'background: var(--rgm-card-2, #f1f5f9); border: 2rpx dashed #94a3b8;'"
            @click="leaveClubChecked = !leaveClubChecked"
          >
            <text style="font-size: 32rpx;">{{ leaveClubChecked ? '☑️' : '⬜' }}</text>
            <text style="font-size: 24rpx; font-weight: 700; color: var(--rgm-text, #0f172a); line-height: 1.4;">
              我已了解退出影响，确认主动退出【{{ currentClub.name }}】
            </text>
          </view>
        </view>

        <view style="display: flex; gap: 18rpx; margin-top: 8rpx;">
          <button
            style="flex: 1; height: 80rpx; line-height: 80rpx; border-radius: 18rpx; font-size: 26rpx; font-weight: 700; background: var(--rgm-card-2, #e2e8f0); color: var(--rgm-text, #334155); margin: 0;"
            @click="closeLeaveClubConfirmModal"
          >
            我再想想
          </button>
          <button
            :disabled="!leaveClubChecked || leaveClubCountdown > 0 || leavingClubLoading"
            :loading="leavingClubLoading"
            style="flex: 1.3; height: 80rpx; line-height: 80rpx; border-radius: 18rpx; font-size: 26rpx; font-weight: 800; margin: 0;"
            :style="(!leaveClubChecked || leaveClubCountdown > 0)
              ? 'background: #94a3b8; color: #ffffff; opacity: 0.65;'
              : 'background: #ef4444; color: #ffffff; box-shadow: 0 8rpx 20rpx rgba(239, 68, 68, 0.35);'"
            @click="confirmLeaveClubExecution"
          >
            {{ leaveClubCountdown > 0 ? `请核对 (${leaveClubCountdown}s)` : (leaveClubChecked ? '确认退出跑团' : '请先勾选上方确认') }}
          </button>
        </view>
      </view>
    </view>

    <!-- ── 🏃 Create / Edit Group Run & Event Modal (发起/编辑约跑活动弹窗) ── -->
    <!-- 长表单：点遮罩不关闭，防止误触丢失已填内容 -->
    <view v-if="showGroupRunModal || showEventModal" class="modal-mask" @touchmove.stop.prevent>
      <view class="modal-content group-run-modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">{{ editingEventId ? '编辑跑团活动' : '发起跑团约跑' }}</text>
          <text class="close-btn" @click="showGroupRunModal = false; showEventModal = false;">✕</text>
        </view>

        <!-- 活动类型选择 -->
        <view class="evt-type-tabs">
          <view
            class="evt-type-tab"
            :class="{ active: eventType === 'group_run' }"
            @click="eventType = 'group_run'"
          >
            <text class="ett-icon">🏃</text>
            <text class="ett-text">线下集体约跑</text>
          </view>
          <view
            class="evt-type-tab"
            :class="{ active: eventType === 'distance_challenge' }"
            @click="eventType = 'distance_challenge'"
          >
            <text class="ett-icon">🏆</text>
            <text class="ett-text">跑量挑战赛</text>
          </view>
        </view>

        <scroll-view scroll-y class="group-run-form-scroll" :scroll-top="formScrollTop" :scroll-with-animation="true">
          <view class="modal-body">
            <!-- 👤 约跑发起人展示 -->
            <view class="ecp-creator-card" v-if="eventType === 'group_run'">
              <image class="ecp-avatar" :src="user?.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=80&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="ecp-info">
                <view class="ecp-line">
                  <text class="ecp-label">本次约跑发起人：</text>
                  <text class="ecp-name">{{ user?.display_name || user?.real_name || '我' }}</text>
                  <text class="ecp-role-tag">{{ currentRole === 'owner' ? '团长' : (currentRole === 'coach' ? '指定教练' : '跑团成员') }}</text>
                </view>
              </view>
            </view>

            <!-- 📑 约跑活动模版库（一键套用 + 存为本团模版） -->
            <view v-if="eventType === 'group_run'" style="margin-bottom: 18rpx; padding: 14rpx 16rpx; border-radius: 14rpx; background: rgba(16, 185, 129, 0.08); border: 1rpx solid rgba(16, 185, 129, 0.25);">
              <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10rpx;">
                <text style="font-size: 22rpx; font-weight: 700; color: #059669;">📑 约跑模版</text>
                <text
                  style="font-size: 21rpx; font-weight: 700; color: #059669; background: rgba(16, 185, 129, 0.14); border: 1rpx solid rgba(16, 185, 129, 0.35); padding: 4rpx 14rpx; border-radius: 999rpx;"
                  @click="handleSaveModalEventTemplate"
                >
                  💾 存为模版
                </text>
              </view>
              <view style="display: flex; flex-wrap: wrap; gap: 10rpx;">
                <view
                  v-for="tpl in allModalGroupRunTemplates"
                  :key="tpl.id"
                  style="display: inline-flex; align-items: center; gap: 6rpx; padding: 8rpx 16rpx; border-radius: 999rpx; font-size: 22rpx; font-weight: 600;"
                  :style="selectedModalTplId === tpl.id
                    ? 'background: #10b981; color: #ffffff; border: 1rpx solid #059669;'
                    : (tpl.is_custom ? 'background: rgba(245, 158, 11, 0.15); color: #d97706; border: 1rpx solid rgba(245, 158, 11, 0.4);' : 'background: rgba(255,255,255,0.9); color: #1e293b; border: 1rpx solid #cbd5e1;')"
                  @click="applyModalGroupRunTemplate(tpl)"
                >
                  <text>{{ tpl.is_custom ? '⭐ ' + tpl.name : tpl.name }}</text>
                  <text
                    v-if="tpl.is_custom"
                    style="margin-left: 4rpx; font-size: 22rpx; opacity: 0.8; padding: 0 4rpx;"
                    @click.stop="handleDeleteModalEventTemplate(tpl)"
                  >
                    ×
                  </text>
                </view>
              </view>
            </view>

            <!-- 活动标题 -->
            <text class="input-label">活动标题 *</text>
            <input
              class="text-input"
              type="text"
              :adjust-position="true"
              :cursor-spacing="50"
              :placeholder="eventType === 'group_run' ? '例如: 周六世纪公园 15km 轻松有氧 LSD' : '例如: 10月 200km 破风进阶挑战'"
              v-model="eventTitle"
            />

            <!-- 线下约跑特有字段 -->
            <template v-if="eventType === 'group_run'">
              <!-- 集合时间 (周历点选 + 时间选择) -->
              <view class="label-with-action-row">
                <text class="input-label">集合时间 *</text>
              </view>

              <!-- 🗓️ 周历横滑条 -->
              <view class="week-calendar-strip">
                <scroll-view scroll-x class="wc-scroll" :show-scrollbar="false">
                  <view class="wc-days-row">
                    <view
                      v-for="d in upcomingWeekDays"
                      :key="d.fullDate"
                      class="wc-day-cell"
                      :class="{ active: eventMeetDate === d.fullDate, 'is-weekend': d.isWeekend, 'is-today': d.isToday }"
                      @click="selectWeekDate(d.fullDate)"
                    >
                      <text class="wc-weekday">{{ d.isToday ? '今天' : d.weekDay }}</text>
                      <view class="wc-num-circle">
                        <text class="wc-daynum">{{ d.dayNum }}</text>
                      </view>
                      <text class="wc-subtag" v-if="d.isWeekend && !d.isToday">周末</text>
                      <text class="wc-subtag" v-else>{{ d.monthText }}</text>
                    </view>
                  </view>
                </scroll-view>
              </view>

              <!-- 已选日期提示与微调选择器 -->
              <view class="selected-time-summary">
                <view class="sts-left">
                  <text class="sts-icon">⏰</text>
                  <text class="sts-text">{{ formatSelectedMeetPreview(eventMeetDate, eventMeetTime) }}</text>
                </view>
                <view class="sts-pickers">
                  <picker mode="time" :value="eventMeetTime" @change="onTimeChange" class="sts-time-picker">
                    <view class="sts-picker-btn">
                      <text>{{ eventMeetTime }}</text>
                      <text class="sts-arrow">▼</text>
                    </view>
                  </picker>
                  <picker mode="date" :value="eventMeetDate" @change="onDateChange" class="sts-more-picker">
                    <view class="sts-more-btn">
                      <text>更多日期</text>
                    </view>
                  </picker>
                </view>
              </view>

              <!-- 🔄 重复约跑设置 -->
              <view class="repeat-group-section">
                <view class="label-with-action-row">
                  <text class="input-label">约跑频次与重复</text>
                  <text v-if="eventRepeatType === 'weekly'" class="repeat-badge-hint">🔄 每周固定例跑</text>
                </view>
                <view class="repeat-tabs">
                  <view
                    class="repeat-tab-btn"
                    :class="{ active: eventRepeatType === 'none' }"
                    @click="eventRepeatType = 'none'"
                  >
                    <text class="rt-icon">⚡</text>
                    <text class="rt-text">单次约跑</text>
                  </view>
                  <view
                    class="repeat-tab-btn"
                    :class="{ active: eventRepeatType === 'weekly' }"
                    @click="eventRepeatType = 'weekly'"
                  >
                    <text class="rt-icon">🔄</text>
                    <text class="rt-text">每周固定例跑</text>
                  </view>
                </view>

                <view v-if="eventRepeatType === 'weekly'" class="repeat-config-box">
                  <text class="rc-hint">每周{{ getWeekdayName(eventMeetDate) }} {{ eventMeetTime }}，连续创建：</text>
                  <view class="rc-weeks-row">
                    <view
                      v-for="w in [2, 4, 8]"
                      :key="w"
                      class="rc-week-pill"
                      :class="{ active: eventRepeatWeeks === w }"
                      @click="eventRepeatWeeks = w"
                    >
                      <text class="rc-week-title">连续 {{ w }} 周</text>
                      <text class="rc-week-sub" v-if="w === 4">推荐</text>
                    </view>
                  </view>
                  <view class="rc-preview-box">
                    <text class="rc-preview-label">🗓️ 排期预览：</text>
                    <text class="rc-preview-dates">{{ formatRepeatSchedulePreview(eventMeetDate, eventRepeatWeeks) }}</text>
                  </view>
                </view>
              </view>

              <!-- 集合地点 -->
              <view class="label-with-action-row">
                <text class="input-label">集合地点 *</text>
                <text class="choose-loc-btn" @click="handleChooseLocation">📍 微信地图选点</text>
              </view>
              <input
                class="text-input"
                type="text"
                :adjust-position="true"
                :cursor-spacing="50"
                confirm-type="search"
                placeholder="输入地点（如：闵行文化公园）后点击右上【📍微信地图选点】放置大头针"
                v-model="eventLocation"
                @blur="onEventLocationInputBlur"
                @confirm="onEventLocationInputBlur"
              />

              <!-- 🗺️ 实时地图标注预览卡片（支持直接点击微调大头针或弹出选点地图） -->
              <view
                v-if="eventLatitude && eventLongitude"
                style="margin: 0 0 18rpx 0; border-radius: 14rpx; overflow: hidden; border: 1rpx solid rgba(37, 99, 235, 0.35); background: #f8fafc;"
              >
                <view style="display: flex; align-items: center; justify-content: space-between; padding: 10rpx 14rpx; background: rgba(37, 99, 235, 0.1);">
                  <text style="font-size: 21rpx; font-weight: 700; color: #1e40af; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    📌 已标注：{{ eventLocation || '集合点' }} ({{ Number(eventLatitude).toFixed(4) }}, {{ Number(eventLongitude).toFixed(4) }})
                  </text>
                  <text
                    style="font-size: 21rpx; font-weight: 700; color: #2563eb; margin-left: 12rpx;"
                    @click="handleChooseLocation"
                  >
                    🎯 调整大头针 ›
                  </text>
                </view>
                <map
                  style="width: 100%; height: 240rpx;"
                  :latitude="Number(eventLatitude)"
                  :longitude="Number(eventLongitude)"
                  :scale="16"
                  :markers="eventModalMapMarkers"
                  @tap="onInlineEventMapTap"
                />
                <view style="display: flex; align-items: center; justify-content: space-between; padding: 8rpx 14rpx; background: #eff6ff;">
                  <text style="font-size: 20rpx; color: #1d4ed8;">💡 点地图移动大头针</text>
                  <text
                    style="font-size: 20rpx; font-weight: 700; color: #2563eb;"
                    @click="handleOpenMap({ location: eventLocation, location_detail: eventLocationDetail, latitude: eventLatitude, longitude: eventLongitude })"
                  >
                    🧭 导航预览 ›
                  </text>
                </view>
              </view>

              <!-- 详细路线/集合地标 -->
              <text class="input-label">详细路线 / 集合说明</text>
              <input
                class="text-input"
                type="text"
                :adjust-position="true"
                :cursor-spacing="50"
                placeholder="例如: 顺时针外圈5km × 3圈，跑完集合拉伸拍照"
                v-model="eventLocationDetail"
              />

              <!-- 预计跑量与配速要求 -->
              <view class="form-row-pair">
                <view class="form-col-half">
                  <text class="input-label">目标距离 (km)</text>
                  <input
                    class="text-input"
                    type="digit"
                    :adjust-position="true"
                    :cursor-spacing="50"
                    placeholder="10"
                    v-model="eventTargetKm"
                  />
                </view>
                <view class="form-col-half">
                  <text class="input-label">建议配速</text>
                  <input
                    class="text-input"
                    type="text"
                    :adjust-position="true"
                    :cursor-spacing="50"
                    placeholder="5:30 - 6:00 /km"
                    v-model="eventPace"
                  />
                </view>
              </view>

              <!-- 题头图选择 -->
              <view class="label-with-action-row">
                <text class="input-label">活动题头图 *</text>
                <text class="choose-loc-btn" @click="handleUploadCover">📷 自定义上传</text>
              </view>
              <!-- 预置题头图网格点选 -->
              <view class="preset-covers-grid">
                <view
                  v-for="pc in PRESET_COVERS"
                  :key="pc.id"
                  class="preset-cover-item"
                  :class="{ active: eventCoverImage === pc.url }"
                  @click="handleSelectPresetCover(pc.url)"
                >
                  <image class="pci-img" :src="pc.url" mode="aspectFill" />
                  <view class="pci-overlay">
                    <text class="pci-title">{{ pc.title }}</text>
                  </view>
                  <text v-if="eventCoverImage === pc.url" class="pci-check">✓</text>
                </view>
              </view>

              <!-- 人数上限 -->
              <text class="input-label">人数上限 (0 表示不限人数)</text>
              <input
                class="text-input"
                type="number"
                :adjust-position="true"
                :cursor-spacing="50"
                placeholder="0"
                v-model="eventMaxParticipants"
              />
            </template>

            <!-- 跑量挑战特有字段 -->
            <template v-else>
              <text class="input-label">目标跑量 (km)</text>
              <input
                class="text-input"
                type="number"
                :adjust-position="true"
                :cursor-spacing="50"
                placeholder="200"
                v-model="eventTargetKm"
              />
            </template>

            <!-- 补充说明 / 装备建议 -->
            <view class="label-with-action-row">
              <text class="input-label">{{ eventType === 'group_run' ? '装备与补给建议' : '挑战规则与奖励说明' }}</text>
              <text v-if="isRulesFocused" class="textarea-done-btn" @click="isRulesFocused = false">✓ 完成收起键盘</text>
            </view>
            <textarea
              class="textarea-input"
              :adjust-position="true"
              :cursor-spacing="140"
              show-confirm-bar="true"
              :placeholder="eventType === 'group_run' ? '自备饮用水与补给，遵守交通规则，健康安全第一！跑团提供跑后拉伸指导...' : '完赛即可解锁专属电子勋章与跑团定制奖章...'"
              v-model="eventRules"
              @focus="onRulesFocus"
              @blur="onRulesBlur"
            />

            <!-- 约跑最终参与名单与完赛数据页开放权限设定 -->
            <view style="margin-top: 24rpx; margin-bottom: 16rpx;">
              <text class="input-label">🛡️ 名单与数据可见范围</text>
              <view style="display: flex; gap: 12rpx; margin-top: 10rpx;">
                <view
                  v-for="vOpt in [
                    { val: 'registered_only', label: '🔒 仅报名团员可见' },
                    { val: 'club_members', label: '👥 全团成员可见' },
                    { val: 'public', label: '🌐 公开战报页' }
                  ]"
                  :key="vOpt.val"
                  @click="eventVisibilityMode = vOpt.val as any"
                  :style="{
                    flex: 1,
                    textAlign: 'center',
                    padding: '16rpx 8rpx',
                    borderRadius: '14rpx',
                    fontSize: '22rpx',
                    fontWeight: eventVisibilityMode === vOpt.val ? '700' : '500',
                    background: eventVisibilityMode === vOpt.val ? 'var(--rgm-accent, #d0fd3e)' : 'var(--rgm-card-2, #1c1f2b)',
                    color: eventVisibilityMode === vOpt.val ? 'var(--rgm-accent-fg, #0b0d13)' : 'var(--rgm-text-2, #94a3b8)',
                    border: '1rpx solid ' + (eventVisibilityMode === vOpt.val ? 'var(--rgm-accent, #d0fd3e)' : 'var(--rgm-line, rgba(255,255,255,0.12))')
                  }"
                >
                  {{ vOpt.label }}
                </view>
              </view>
              <text style="display: block; font-size: 21rpx; color: var(--rgm-text-3, #8e8e93); margin-top: 8rpx;">
                {{
                  eventVisibilityMode === 'registered_only'
                    ? '仅报名者可查看名单与配速'
                    : eventVisibilityMode === 'club_members'
                    ? '全团成员可查看名单与成绩'
                    : '任何人可通过分享卡片查看'
                }}
              </text>
            </view>

            <!-- 针对软键盘弹起时的防遮挡平滑伸缩空间 -->
            <view :style="{ height: isRulesFocused ? '520rpx' : '20rpx', transition: 'height 0.25s ease' }" />

            <button class="submit-btn" :loading="savingEvent" @click="handleSaveGroupRun">
              {{ editingEventId ? '保存修改' : '立即发布约跑' }}
            </button>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── 👥 Group Run Participants Modal (约跑报名成员名单弹窗) ── -->
    <view v-if="showParticipantsModal" class="modal-mask" @click="showParticipantsModal = false" @touchmove.stop.prevent>
      <view class="modal-content participants-modal-content" @click.stop>
        <view class="modal-header">
          <view class="pm-title-box">
            <text class="modal-title">🏃 约跑报名成员</text>
            <text class="pm-count-badge">{{ selectedEventForParticipants?.participant_count || 0 }}人已加入</text>
          </view>
          <text class="close-btn" @click="showParticipantsModal = false">✕</text>
        </view>

        <view class="pm-event-mini-bar">
          <text class="pm-evt-name">{{ selectedEventForParticipants?.title }}</text>
          <text class="pm-evt-sub">⏰ {{ formatMeetTime(selectedEventForParticipants?.meet_time || selectedEventForParticipants?.start_date) }} · 📍 {{ selectedEventForParticipants?.location || '跑团集合点' }}</text>
        </view>

        <!-- 发起人专属横幅 -->
        <view class="pm-creator-banner" v-if="selectedEventForParticipants?.creator_name">
          <image
            class="pm-cb-avatar"
            :src="selectedEventForParticipants?.creator_avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=80&auto=format&fit=crop&q=80'"
            mode="aspectFill"
          />
          <view class="pm-cb-meta">
            <view class="pm-cb-line">
              <text class="pm-cb-label">约跑发起人：</text>
              <text class="pm-cb-name">{{ selectedEventForParticipants?.creator_name }}</text>
              <text class="pm-cb-tag">{{ selectedEventForParticipants?.creator_role || '发起人' }}</text>
            </view>
            <text v-if="selectedEventForParticipants?.repeat_rule === 'weekly'" class="pm-cb-repeat">🔄 每周固定例跑</text>
          </view>
        </view>

        <scroll-view scroll-y class="pm-scroll-list">
          <view v-if="!selectedEventForParticipants?.participants || selectedEventForParticipants.participants.length === 0" class="pm-empty">
            <text class="pm-empty-text">暂无报名</text>
          </view>
          <view v-else class="pm-user-list">
            <view
              v-for="(p, pidx) in selectedEventForParticipants.participants"
              :key="pidx"
              class="pm-user-item"
            >
              <image class="pm-avatar" :src="p.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="pm-user-meta">
                <view class="pm-name-line">
                  <text class="pm-name">{{ p.display_name || p.real_name || '跑友' }}</text>
                  <text v-if="p.user_id === selectedEventForParticipants?.creator_id" class="pm-creator-tag">发起人</text>
                  <text v-if="p.user_id === user?.id" class="pm-me-tag">我</text>
                </view>
                <text class="pm-joined-time">加入时间: {{ formatJoinTime(p.joined_at) }}</text>
              </view>
            </view>
          </view>
        </scroll-view>

        <view class="pm-bottom-actions">
          <button class="pm-close-btn" @click="showParticipantsModal = false">关闭</button>
        </view>
      </view>
    </view>


    <!-- ── Join Club Modal (加入跑团弹窗) ── -->
    <view v-if="showJoinModal" class="modal-mask" @click="showJoinModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">加入跑团</text>
          <text class="close-btn" @click="showJoinModal = false">✕</text>
        </view>

        <view class="modal-body">
          <!-- 新用户一键同步微信昵称与头像 -->
          <view v-if="needsWechatNickname" class="join-wx-profile-card">
            <view class="jwp-head">
              <text class="jwp-badge">👤 入团名片</text>
            </view>
            <view class="jwp-row">
              <!-- #ifdef MP-WEIXIN -->
              <button class="jwp-avatar-btn" open-type="chooseAvatar" @chooseavatar="onJoinChooseAvatar">
                <image v-if="joinRunnerAvatar || user?.avatar_url" class="jwp-avatar-img" :src="joinRunnerAvatar || user?.avatar_url" mode="aspectFill" />
                <text v-else class="jwp-avatar-placeholder">📷</text>
                <text class="jwp-avatar-sub">微信头像</text>
              </button>
              <!-- #endif -->
              <view class="jwp-input-col">
                <text class="jwp-label">您的跑团昵称 *</text>
                <input
                  type="nickname"
                  class="jwp-nickname-input"
                  v-model="joinRunnerNickname"
                  placeholder="点击此处 · 一键填入微信昵称"
                  @blur="onJoinNicknameBlur"
                />
              </view>
            </view>
          </view>

          <text class="input-label">跑团专属邀请码</text>
          <input
            class="text-input"
            type="text"
            maxlength="12"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="请输入跑团专属邀请码"
            v-model="inviteCodeInput"
          />
          <button class="submit-btn" :loading="joiningClub" @click="handleJoinClub">
            立即加入
          </button>
        </view>
      </view>
    </view>

    <!-- ── 跑团受邀专属直达弹窗 (微信卡片受邀免输码直接加入) ── -->
    <view v-if="showClubInviteModal" class="modal-mask" @click="closeClubInviteModal" @touchmove.stop.prevent>
      <view class="modal-content club-invite-modal-box" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">🎉 跑团入团邀请</text>
            <text class="invite-badge-pill">微信专属</text>
          </view>
          <text class="close-btn" @click="closeClubInviteModal">✕</text>
        </view>

        <view class="modal-body invite-body">
          <view class="invite-club-card">
            <image class="invite-club-logo" :src="invitedClubInfo?.logo_url || '/static/logo-square.png'" mode="aspectFill" />
            <view class="invite-club-info">
              <text class="invite-club-name">{{ invitedClubInfo?.name }}</text>
              <view class="invite-meta-row">
                <text v-if="invitedClubInfo?.city" class="invite-pill">📍 {{ invitedClubInfo.city }}</text>
                <text class="invite-pill">👥 {{ invitedClubInfo?.member_count || 1 }} 位团员</text>
                <text v-if="invitedClubInfo?.org_name" class="invite-pill org-pill">🏛️ {{ invitedClubInfo.org_name }}</text>
              </view>
              <text v-if="invitedClubInfo?.description" class="invite-club-desc">{{ invitedClubInfo.description }}</text>
            </view>
          </view>

          <!-- 新用户一键同步微信昵称与头像（告别“跑者_xxxx”代号） -->
          <view v-if="needsWechatNickname" class="join-wx-profile-card">
            <view class="jwp-head">
              <text class="jwp-badge">👤 入团名片</text>
            </view>
            <view class="jwp-row">
              <!-- #ifdef MP-WEIXIN -->
              <button class="jwp-avatar-btn" open-type="chooseAvatar" @chooseavatar="onJoinChooseAvatar">
                <image v-if="joinRunnerAvatar || user?.avatar_url" class="jwp-avatar-img" :src="joinRunnerAvatar || user?.avatar_url" mode="aspectFill" />
                <text v-else class="jwp-avatar-placeholder">📷</text>
                <text class="jwp-avatar-sub">微信头像</text>
              </button>
              <!-- #endif -->
              <view class="jwp-input-col">
                <text class="jwp-label">跑团昵称 *</text>
                <input
                  type="nickname"
                  class="jwp-nickname-input"
                  v-model="joinRunnerNickname"
                  placeholder="点击此处 · 一键填入微信昵称"
                  @blur="onJoinNicknameBlur"
                />
              </view>
            </view>
          </view>

          <!-- 邀请码绑定核验状态 -->
          <view class="invite-status-strip">
            <text class="iss-icon">✓</text>
            <view class="iss-text-col">
              <text class="iss-title">{{ invitedClubOneClick ? '受邀直达 · 免码免审批' : (invitedClubInfo?.join_mode === 'invite' ? '邀请码已核验' : '自由入团') }}</text>
            </view>
          </view>

          <!-- 隶属大群：说明会同时以临时成员加入大群，资料可稍后补填 -->
          <view v-if="invitedClubInfo?.org_id && !invitedClubIsOrgMember" class="invite-status-strip org-notice-strip">
            <text class="iss-icon org-iss-icon">🏛️</text>
            <view class="iss-text-col">
              <text class="iss-title org-iss-title">将同时加入【{{ invitedClubInfo.org_name || '大群' }}】· 资料可稍后补填</text>
              <text class="iss-sub org-iss-sub">需在 {{ invitedClubDeadlineDays }} 天内补齐资料并通过审核，逾期将移出大群跑团</text>
            </view>
          </view>

          <view class="modal-btn-row">
            <button class="btn-cancel" @click="closeClubInviteModal">暂不加入</button>
            <button class="btn-submit" :loading="acceptingClubInvite" @click="handleAcceptClubInvite">
              ✓ 接受邀请
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── All Clubs Modal (浏览与切换全部跑团) ── -->
    <view v-if="showAllClubsModal" class="modal-mask" @click="showAllClubsModal = false">
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">跑团切换与浏览</text>
            <text class="count-pill">{{ userClubs.length }} 个已加入</text>
          </view>
          <text class="close-btn" @click="showAllClubsModal = false">✕</text>
        </view>

        <!-- Segmented Tab Switcher in Modal -->
        <view class="modal-tab-row" v-if="userClubs.length > 0">
          <view
            class="modal-tab-segment"
            :class="{ active: clubModalTab === 'joined' }"
            @click="clubModalTab = 'joined'"
          >
            我的跑团 ({{ userClubs.length }})
          </view>
          <view
            class="modal-tab-segment"
            :class="{ active: clubModalTab === 'all' }"
            @click="clubModalTab = 'all'"
          >
            平台全部 ({{ allClubs.length }})
          </view>
        </view>

        <!-- Search & City Filter (when viewing All clubs in modal) -->
        <view v-if="clubModalTab === 'all'" class="modal-search-filter-box">
          <view class="club-search-bar modal-search-bar">
            <text class="csb-search-icon">🔍</text>
            <input
              class="csb-input"
              type="text"
              placeholder="按城市或跑团名搜索..."
              v-model="clubSearchText"
            />
            <text v-if="clubSearchText" class="csb-clear-icon" @click="clubSearchText = ''">✕</text>
          </view>
          <scroll-view scroll-x class="city-chips-scroll" :show-scrollbar="false">
            <view class="city-chips-row">
              <view
                v-for="ct in availableCities"
                :key="ct"
                class="city-chip"
                :class="{ active: selectedCityFilter === ct }"
                @click="selectedCityFilter = ct"
              >
                <text class="city-chip-text">{{ ct }}</text>
              </view>
            </view>
          </scroll-view>
        </view>

        <scroll-view scroll-y class="modal-body modal-scroll">
          <view v-if="displayedClubs.length === 0" class="empty-clubs-text">
            {{ clubModalTab === 'joined' ? '尚未加入跑团' : (clubSearchText || selectedCityFilter !== '全部' ? `未找到【${selectedCityFilter !== '全部' ? selectedCityFilter + ' ' : ''}${clubSearchText}】的相关跑团` : '暂无其他跑团') }}
          </view>
          <view v-else class="modal-clubs-list">
            <!-- 分组 1：大群下属分队（仅已加入大群的用户可见） -->
            <view v-if="displayedOrgClubs.length > 0" class="modal-club-group-sec org-group-sec">
              <view class="mcgs-header is-org">
                <view class="mcgs-title-line">
                  <text class="mcgs-title">🏛️ {{ currentOrg?.name || displayedOrgClubs[0]?.org_name || '大群' }} · 下属分队 ({{ displayedOrgClubs.length }})</text>
                </view>
              </view>
              <view
                v-for="c in displayedOrgClubs"
                :key="c.id"
                class="modal-club-card is-org-card"
                :class="{ 'is-current': currentClub?.id === c.id }"
                @click="c.is_member ? handleSwitchClub(c) : null"
              >
                <image class="mcc-logo" :src="c.logo_url || '/static/logo-square.png'" mode="aspectFill" />
                <view class="mcc-info">
                  <view class="mcc-name-row">
                    <text class="mcc-name">{{ c.name }}</text>
                  </view>
                  <view class="mcc-badges-row">
                    <text class="mcc-aff-badge org-aff">🏛️ {{ c.org_name || currentOrg?.name || '大群' }}分队</text>
                    <text class="mode-badge-pill" :class="c.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                      {{ c.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                    </text>
                    <text class="mcc-city">📍 {{ c.city || '上海' }}</text>
                  </view>
                  <text v-if="c.description" class="mcc-desc">{{ c.description }}</text>
                  <view class="mcc-meta">
                    <text>团长: {{ c.owner_name || '平台指定' }}</text>
                    <text class="mcc-dot">·</text>
                    <text class="highlight">{{ c.member_count || 1 }} 位成员</text>
                    <text v-if="c.role" class="mcc-role-tag" :class="'role-' + c.role">
                      {{ c.role === 'owner' ? '👑 团长' : c.role === 'coach' ? '🧢 教练' : '🏃 团员' }}
                    </text>
                  </view>
                </view>
                <view class="mcc-action" @click.stop>
                  <text v-if="currentClub?.id === c.id" class="mcc-current-tag">当前使用中 ✓</text>
                  <button
                    v-else-if="c.is_member"
                    class="mcc-switch-btn"
                    @click="handleSwitchClub(c)"
                  >
                    ⇄ 切换
                  </button>
                  <button
                    v-else
                    class="mcc-join-btn"
                    :class="{ 'btn-invite-mode': c.join_mode === 'invite' }"
                    :loading="joiningClubId === c.id"
                    @click="handleJoinClubWithCheck(c)"
                  >
                    {{ c.join_mode === 'invite' ? '🔑 凭码加入' : '+ 自由加入' }}
                  </button>
                </view>
              </view>
            </view>

            <!-- 分组 2：独立公开跑团（不隶属于任何大群） -->
            <view v-if="displayedIndepClubs.length > 0" class="modal-club-group-sec indep-group-sec">
              <view class="mcgs-header is-indep">
                <view class="mcgs-title-line">
                  <text class="mcgs-title">🌐 独立公开跑团 ({{ displayedIndepClubs.length }})</text>
                </view>
              </view>
              <view
                v-for="c in displayedIndepClubs"
                :key="c.id"
                class="modal-club-card"
                :class="{ 'is-current': currentClub?.id === c.id }"
                @click="c.is_member ? handleSwitchClub(c) : null"
              >
                <image class="mcc-logo" :src="c.logo_url || '/static/logo-square.png'" mode="aspectFill" />
                <view class="mcc-info">
                  <view class="mcc-name-row">
                    <text class="mcc-name">{{ c.name }}</text>
                  </view>
                  <view class="mcc-badges-row">
                    <text class="mcc-aff-badge indep-aff">🌐 独立跑团</text>
                    <text class="mode-badge-pill" :class="c.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                      {{ c.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                    </text>
                    <text class="mcc-city">📍 {{ c.city || '上海' }}</text>
                  </view>
                  <text v-if="c.description" class="mcc-desc">{{ c.description }}</text>
                  <view class="mcc-meta">
                    <text>团长: {{ c.owner_name || '平台指定' }}</text>
                    <text class="mcc-dot">·</text>
                    <text class="highlight">{{ c.member_count || 1 }} 位成员</text>
                    <text v-if="c.role" class="mcc-role-tag" :class="'role-' + c.role">
                      {{ c.role === 'owner' ? '👑 团长' : c.role === 'coach' ? '🧢 教练' : '🏃 团员' }}
                    </text>
                  </view>
                </view>
                <view class="mcc-action" @click.stop>
                  <text v-if="currentClub?.id === c.id" class="mcc-current-tag">当前使用中 ✓</text>
                  <button
                    v-else-if="c.is_member"
                    class="mcc-switch-btn"
                    @click="handleSwitchClub(c)"
                  >
                    ⇄ 切换
                  </button>
                  <button
                    v-else
                    class="mcc-join-btn"
                    :class="{ 'btn-invite-mode': c.join_mode === 'invite' }"
                    :loading="joiningClubId === c.id"
                    @click="handleJoinClubWithCheck(c)"
                  >
                    {{ c.join_mode === 'invite' ? '🔑 凭码加入' : '+ 自由加入' }}
                  </button>
                </view>
              </view>
            </view>
          </view>
        </scroll-view>

        <!-- 底部快捷操作栏：输入邀请码 / 自建跑团 -->
        <view style="display: flex; gap: 16rpx; padding: 20rpx 28rpx 28rpx; border-top: 1rpx solid var(--rgm-line, rgba(255,255,255,0.08));">
          <button
            style="flex: 1; min-width: 0; margin: 0; padding: 0 16rpx; height: 76rpx; line-height: 1.25; display: flex; align-items: center; justify-content: center; font-size: 26rpx; font-weight: 600; border-radius: 20rpx; background: var(--rgm-card-2, #1f1f24); color: var(--rgm-text, #ffffff); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.12)); white-space: nowrap;"
            @click="showAllClubsModal = false; showJoinModal = true;"
          >
            🔑 邀请码入团
          </button>
          <button
            style="flex: 1; min-width: 0; margin: 0; padding: 0 16rpx; height: 76rpx; line-height: 1.25; display: flex; align-items: center; justify-content: center; font-size: 25rpx; font-weight: 700; border-radius: 20rpx; background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%)); color: #ffffff; border: none; white-space: nowrap;"
            @click="showAllClubsModal = false; openCreateClubModal();"
          >
            ✨ 自建跑团 (满3人解锁)
          </button>
        </view>
      </view>
    </view>

    <!-- ── 1. Join Grand Organization Modal (3-Step Guided Wizard) ── -->
    <!--
      架构：整个遮罩用 column flex 分两块，不重叠：
      1. org-dismiss-strip 顶部暗色条：点击/touchmove.stop.prevent 只在这里
      2. org-panel 底部面板：完全没有 catchtouchmove，scroll-view 可以自由滚动
    -->
    <view v-if="showOrgJoinModal" class="org-modal-root">
      <!-- 顶部关闭条（不重叠于面板） -->
      <view class="org-dismiss-strip" @touchmove.stop.prevent></view>

      <!-- 底部面板（无任何 catchtouchmove） -->
      <view class="org-panel">
        <!-- 头部 -->
        <view class="org-panel-head">
          <view class="drag-bar-wrap"><view class="drag-bar"></view></view>
          <view class="org-panel-title-row">
            <view class="title-with-pill">
              <text class="modal-title">{{ isUpdatingOrgProfile ? `补全 / 修改“${currentOrg?.name || '大群'}”资料` : `加入“${invitedOrgName || targetDefaultOrg?.name || '大群'}”大群` }}</text>
              <text class="count-pill">第 {{ orgWizardStep }}/3 步</text>
            </view>
            <view class="org-panel-close" @click="showOrgJoinModal = false">
              <text class="close-btn">✕</text>
            </view>
          </view>

          <!-- 3 步向导进度条 -->
          <view style="display: flex; gap: 12rpx; padding: 14rpx 28rpx 8rpx;">
            <view
              v-for="s in [
                { step: 1, label: '1. 戈友身份' },
                { step: 2, label: '2. 联络保障' },
                { step: 3, label: '3. 尺码确认' }
              ]"
              :key="s.step"
              style="flex: 1; padding: 10rpx 8rpx; border-radius: 14rpx; text-align: center; font-size: 22rpx; font-weight: 700;"
              :style="orgWizardStep === s.step
                ? 'background: var(--rgm-brand-tint, rgba(252,76,2,0.18)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252,76,2,0.45));'
                : orgWizardStep > s.step
                  ? 'background: rgba(34,197,94,0.14); color: #22c55e; border: 1rpx solid rgba(34,197,94,0.35);'
                  : 'background: var(--rgm-card-2, #18181f); color: var(--rgm-text-3, #71717a); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.08));'"
              @click="goToOrgWizardStep(s.step)"
            >
              {{ orgWizardStep > s.step ? '✓ ' + s.label : s.label }}
            </view>
          </view>
        </view>

        <!-- scroll-view：高度用 JS 真实 px 值注入 -->
        <scroll-view scroll-y :style="{ height: orgScrollHeight + 'px' }">
          <view class="org-form-body">
            <!-- ══════════ STEP 1: 校友与戈友身份 ══════════ -->
            <template v-if="orgWizardStep === 1">
              <view class="privacy-security-notice">
                <view class="privacy-badge-row">
                  <text class="privacy-badge-icon">🛡️</text>
                  <text class="privacy-badge-title">个人隐私与数据安全保障</text>
                  <text class="privacy-badge-tag">AES-256 加密</text>
                </view>
                <text class="privacy-security-desc">真实姓名、证件号、出生日期及手机号均在数据库底层采用 AES-256 密文存储，仅用于戈赛资格核验与分组合规。普通跑友无法查看您的明文隐私。</text>
              </view>

              <view v-if="!isUpdatingOrgProfile" class="form-group">
                <!-- 微信受邀（邀请卡片/小程序码）：免邀请码、免审批，资料可稍后补填 -->
                <view v-if="isInviteFromWechat && (orgJoinForm.invite_code || orgInviteOneClick)" class="org-invite-verified-banner">
                  <view class="ofj-header-row">
                    <text class="ofj-icon">🎉</text>
                    <text class="ofj-title">收到【{{ invitedOrgName || targetDefaultOrg?.name || '大群' }}】邀请 · 免码直接加入</text>
                  </view>
                </view>

                <view v-else-if="targetDefaultOrg?.join_mode === 'free' && !orgJoinForm.invite_code" class="org-free-join-banner">
                  <view class="ofj-header-row">
                    <text class="ofj-icon">🟢</text>
                    <text class="ofj-title">已开启自由入会（免专属码）</text>
                  </view>
                  <view class="ofj-switch-code" @click="showManualOrgCode = !showManualOrgCode">
                    <text class="ofj-switch-text">{{ showManualOrgCode ? '收起邀请码输入' : '持有特定邀请码？点击输入 ›' }}</text>
                  </view>
                </view>

                <view v-if="!(isInviteFromWechat && (orgJoinForm.invite_code || orgInviteOneClick)) && (targetDefaultOrg?.join_mode !== 'free' || showManualOrgCode)">
                  <text class="input-label">大群专属邀请码 <text v-if="targetDefaultOrg?.join_mode !== 'free'" class="req-star">*</text></text>
                  <input class="text-input" type="text" :adjust-position="true" :cursor-spacing="50" :placeholder="targetDefaultOrg?.join_mode === 'free' ? '选填：若有其他大群邀请码可输入' : '请输入大群专属邀请码'" v-model="orgJoinForm.invite_code" />
                </view>
              </view>

              <view v-if="isOrgFieldVisible('real_name')" class="form-group">
                <view class="label-with-icon-row">
                  <text class="input-label">真实姓名 <text v-if="isOrgFieldRequired('real_name')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;"> (选填)</text></text>
                  <text class="field-security-pill">🔒 加密存储</text>
                </view>
                <input class="text-input" type="text" :adjust-position="true" :cursor-spacing="50" placeholder="请填写真实姓名以便管理员核实" v-model="orgJoinForm.real_name" />
              </view>

              <template v-if="isOrgFieldVisible('class_name')">
                <view class="form-group">
                  <text class="input-label">商学院项目 <text v-if="isOrgFieldRequired('class_name')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;"> (选填)</text></text>
                  <view class="program-chips-grid">
                    <view v-for="p in ORG_PROGRAM_OPTIONS" :key="p" class="program-chip" :class="{ active: orgJoinForm.program === p }" @click="orgJoinForm.program = p">{{ p }}</view>
                  </view>
                </view>

                <view class="form-group">
                  <text class="input-label">所在班级 / 届别 <text v-if="isOrgFieldRequired('class_name')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;"> (选填)</text></text>
                  <input class="text-input" type="text" :adjust-position="true" :cursor-spacing="50" placeholder="例如: 23春 / 21级 / 18班" v-model="orgJoinForm.class_detail" />
                  <text v-if="orgJoinForm.program && orgJoinForm.class_detail" class="field-preview-tag">班级预览：{{ orgJoinForm.program }} {{ orgJoinForm.class_detail }}</text>
                </view>
              </template>

              <view v-if="isOrgFieldVisible('gobi_experience')" class="form-group">
                <view class="label-with-icon-row">
                  <text class="input-label">戈壁经历 <text v-if="isOrgFieldRequired('gobi_experience')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;"> (选填)</text></text>
                  <text class="field-security-pill">🏅 戈友身份</text>
                </view>
                <view class="gobi-type-segmented-row">
                  <view class="gobi-type-pill" :class="{ active: orgJoinForm.gobi_type === 'new' }" @click="orgJoinForm.gobi_type = 'new'">🌱 新戈 (首次参赛)</view>
                  <view class="gobi-type-pill" :class="{ active: orgJoinForm.gobi_type === 'vet' }" @click="orgJoinForm.gobi_type = 'vet'">🏅 往届戈友 (老戈)</view>
                </view>
                <view v-if="orgJoinForm.gobi_type === 'vet'" class="vet-gobi-box">
                  <view class="vet-row">
                    <text class="vet-label">参赛届数：</text>
                    <picker mode="selector" :range="GOBI_EDITION_OPTIONS" :value="selectedGobiEditionIndex" @change="onGobiEditionChange" class="vet-picker">
                      <view class="vet-picker-box"><text class="vpb-value">{{ orgJoinForm.gobi_edition || '选择届数' }}</text><text class="vpb-arrow">▼</text></view>
                    </picker>
                  </view>
                  <view class="vet-row">
                    <text class="vet-label">参赛组别：</text>
                    <view class="group-pills-row">
                      <view v-for="grp in GOBI_GROUP_OPTIONS" :key="grp" class="grp-pill" :class="{ active: orgJoinForm.gobi_group === grp }" @click="orgJoinForm.gobi_group = grp">{{ grp }}</view>
                    </view>
                  </view>
                </view>
              </view>

              <!-- 性别与出生日期（自动继承基本资料，可折叠微调） -->
              <view v-if="isOrgFieldVisible('gender') || isOrgFieldVisible('date_of_birth')" class="form-group">
                <view
                  style="padding: 18rpx 22rpx; border-radius: 16rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1)); display: flex; align-items: center; justify-content: space-between;"
                  @click="showOrgGenderDobAdjust = !showOrgGenderDobAdjust"
                >
                  <text style="font-size: 23rpx; color: var(--rgm-text-2, #a1a1aa);">
                    ✓ 已同步基本资料：<template v-if="isOrgFieldVisible('gender')">{{ orgJoinForm.gender === 'female' ? '🚺 女' : '🚹 男' }}</template><template v-if="isOrgFieldVisible('gender') && isOrgFieldVisible('date_of_birth')"> · </template><template v-if="isOrgFieldVisible('date_of_birth')">{{ getAgeGroup(orgJoinForm.date_of_birth) }}</template>
                  </text>
                  <text style="font-size: 22rpx; color: var(--rgm-brand-text, #fc4c02); font-weight: 600;">
                    {{ showOrgGenderDobAdjust ? '收起 ▲' : '修改 ▼' }}
                  </text>
                </view>
                <view v-if="showOrgGenderDobAdjust" style="margin-top: 16rpx;">
                  <view v-if="isOrgFieldVisible('gender')" class="gender-segmented-row" style="margin-bottom: 16rpx;">
                    <view class="gender-pill" :class="{ active: orgJoinForm.gender === 'male' }" @click="orgJoinForm.gender = 'male'">🚹 男</view>
                    <view class="gender-pill" :class="{ active: orgJoinForm.gender === 'female' }" @click="orgJoinForm.gender = 'female'">🚺 女</view>
                  </view>
                  <picker v-if="isOrgFieldVisible('date_of_birth')" mode="date" :value="orgJoinForm.date_of_birth" @change="onOrgDobChange">
                    <view class="picker-display-box">
                      <text class="picker-value">{{ orgJoinForm.date_of_birth || '请选择出生日期' }}</text>
                      <text class="picker-arrow">📅 选择出生日期 ›</text>
                    </view>
                  </picker>
                </view>
              </view>
            </template>

            <!-- ══════════ STEP 2: 联络与安全保障 ══════════ -->
            <template v-else-if="orgWizardStep === 2">
              <view v-if="isOrgFieldVisible('phone')" class="form-group">
                <view class="label-with-icon-row">
                  <text class="input-label">联系手机 <text v-if="isOrgFieldRequired('phone')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;">(选填)</text></text>
                  <text class="field-security-pill">🔒 AES-256 加密存储</text>
                </view>
                <input class="text-input" type="number" maxlength="11" :adjust-position="true" :cursor-spacing="50" placeholder="便于紧急联络与赛事活动通知" v-model="orgJoinForm.phone" />
              </view>

              <view v-if="isOrgFieldVisible('id_card')" class="form-group">
                <view class="label-with-icon-row">
                  <text class="input-label">身份证号码 / 证件号 <text v-if="isOrgFieldRequired('id_card')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;">(选填)</text></text>
                  <text class="field-security-pill">🔒 密文存储</text>
                </view>
                <input class="text-input" type="text" maxlength="18" :adjust-position="true" :cursor-spacing="50" placeholder="用于赛事保险投保与参赛资格核验" v-model="orgJoinForm.id_card" />
              </view>

              <view v-if="isOrgFieldVisible('emergency_contact')" class="form-group">
                <text class="input-label">紧急联系人与电话 <text v-if="isOrgFieldRequired('emergency_contact')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;">(选填)</text></text>
                <input class="text-input" type="text" :adjust-position="true" :cursor-spacing="50" placeholder="例如: 张三 13800000000" v-model="orgJoinForm.emergency_contact" />
              </view>
            </template>

            <!-- ══════════ STEP 3: 装备尺码与健康确认 ══════════ -->
            <template v-else>
              <view v-if="isOrgFieldVisible('clothing_size')" class="form-group">
                <text class="input-label">队服尺码 <text v-if="isOrgFieldRequired('clothing_size')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;">(选填)</text></text>
                <view class="program-chips-grid">
                  <view
                    v-for="js in ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL']"
                    :key="js"
                    class="program-chip"
                    :class="{ active: orgJoinForm.jersey_size === js }"
                    @click="orgJoinForm.jersey_size = js"
                  >
                    {{ js }}
                  </view>
                </view>
              </view>

              <view v-if="isOrgFieldVisible('shoe_size')" class="form-group">
                <text class="input-label">跑鞋尺码 (EUR) <text v-if="isOrgFieldRequired('shoe_size')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;">(选填)</text></text>
                <view class="program-chips-grid">
                  <view
                    v-for="ss in ['36', '37', '38', '39', '40', '41', '42', '42.5', '43', '44', '45']"
                    :key="ss"
                    class="program-chip"
                    :class="{ active: orgJoinForm.running_shoe_size === ss }"
                    @click="orgJoinForm.running_shoe_size = ss"
                  >
                    {{ ss }}
                  </view>
                </view>
              </view>

              <view v-if="isOrgFieldVisible('marathon_pb')" class="form-group">
                <text class="input-label">全马 PB <text v-if="isOrgFieldRequired('marathon_pb')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;">(选填)</text></text>
                <input class="text-input" type="text" :adjust-position="true" :cursor-spacing="50" placeholder="例如: 3:25:00" v-model="orgJoinForm.full_marathon_pb" />
              </view>

              <view v-if="isOrgFieldVisible('health_declaration')" class="form-group">
                <text class="input-label">参赛健康确认 <text v-if="isOrgFieldRequired('health_declaration')" class="req-star">*</text><text v-else style="font-size:22rpx;color:#71717a;">(选填)</text></text>
                <view
                  style="padding: 22rpx; border-radius: 18rpx; display: flex; align-items: flex-start; gap: 16rpx;"
                  :style="orgHealthChecked
                    ? 'background: rgba(34, 197, 94, 0.12); border: 1rpx solid rgba(34, 197, 94, 0.45);'
                    : 'background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.12));'"
                  @click="toggleOrgHealthDeclaration"
                >
                  <text style="font-size: 30rpx; line-height: 1.2;">{{ orgHealthChecked ? '✅' : '⬜' }}</text>
                  <text style="font-size: 24rpx; color: var(--rgm-text, #ffffff); line-height: 1.5; flex: 1;">
                    本人确认身体健康，无不适合高强度耐力跑步的疾病，自愿参加大群与分队训练活动。
                  </text>
                </view>
              </view>
            </template>

            <view style="height: 40rpx;"></view>
          </view>
        </scroll-view>

        <!-- 吸底分步按钮 -->
        <view class="org-panel-foot">
          <view style="display: flex; gap: 16rpx; width: 100%;">
            <button
              v-if="orgWizardStep > 1"
              style="flex: 0.4; margin: 0; height: 84rpx; line-height: 84rpx; border-radius: 22rpx; font-size: 26rpx; font-weight: 700; background: var(--rgm-card-2, #1f1f26); color: var(--rgm-text, #ffffff); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.14));"
              @click="orgWizardStep = orgWizardStep - 1"
            >
              ‹ 上一步
            </button>
            <button
              v-if="orgWizardStep < 3"
              class="submit-btn org-submit-btn"
              style="flex: 1; margin: 0;"
              @click="handleNextOrgWizardStep"
            >
              下一步（{{ orgWizardStep }}/3） ›
            </button>
            <button
              v-else
              class="submit-btn org-submit-btn"
              style="flex: 1; margin: 0;"
              :loading="joiningOrg"
              :disabled="quickJoiningOrg"
              @click="submitOrgJoin"
            >
              {{ isUpdatingOrgProfile ? "✓ 保存并提交审核" : `✓ 完成认证并加入` }}
            </button>
          </view>
          <button
            v-if="!isUpdatingOrgProfile"
            class="org-skip-later-btn"
            :loading="quickJoiningOrg"
            :disabled="joiningOrg"
            @click="submitOrgQuickJoin"
          >
            跳过，稍后再填（14 天内补齐）
          </button>
        </view>
      </view>
    </view>

        <!-- ── 2. Sub Clubs Modal (下属跑团列表弹窗) ── -->
    <view v-if="showSubClubsModal" class="modal-mask" @click="showSubClubsModal = false">
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">【{{ currentOrg?.name || '大群' }}】分队</text>
            <text class="count-pill">{{ orgSubClubs.length }} 个分队</text>
          </view>
          <text class="close-btn" @click="showSubClubsModal = false">✕</text>
        </view>

        <scroll-view scroll-y class="modal-body modal-scroll">
          <view v-if="orgSubClubs.length === 0" class="empty-clubs-text">
            该大群下暂无分队，请联系平台管理员创建！
          </view>
          <view v-else class="modal-clubs-list">
            <view
              v-for="c in orgSubClubs"
              :key="c.id"
              class="modal-club-card"
              :class="{ 'is-current': currentClub?.id === c.id }"
              @click="c.is_member ? handleSwitchClub(c) : null"
            >
              <image class="mcc-logo" :src="c.logo_url || '/static/logo-square.png'" mode="aspectFill" />
              <view class="mcc-info">
                <view class="mcc-name-row">
                  <text class="mcc-name">{{ c.name }}</text>
                </view>
                <view class="mcc-badges-row">
                  <text class="mcc-aff-badge org-aff">🏛️ {{ currentOrg?.name || '大群' }}分队</text>
                  <text class="mode-badge-pill" :class="c.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                    {{ c.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                  </text>
                  <text v-if="c.is_member" class="mcc-joined-badge">已加入</text>
                </view>
                <text v-if="c.description" class="mcc-desc">{{ c.description }}</text>
                <text class="mcc-meta">团长: {{ c.owner_name || '平台指定' }} · {{ c.member_count || 1 }} 位成员</text>
              </view>
              <view class="mcc-action" @click.stop>
                <text v-if="currentClub?.id === c.id" class="mcc-current-tag">当前使用中 ✓</text>
                <button
                  v-else-if="c.is_member"
                  class="mcc-switch-btn"
                  @click="handleSwitchClub(c)"
                >
                  ⇄ 切换
                </button>
                <button
                  v-else
                  class="mcc-join-btn"
                  :class="{ 'btn-invite-mode': c.join_mode === 'invite' }"
                  :loading="joiningClubId === c.id"
                  @click="handleJoinClubWithCheck(c)"
                >
                  {{ c.join_mode === 'invite' ? '🔑 凭码加入' : '+ 加入' }}
                </button>
              </view>
            </view>
          </view>
        </scroll-view>

        <!-- 底部快捷操作栏：自建大群分队或独立跑团 -->
        <view style="display: flex; gap: 16rpx; padding: 20rpx 28rpx 28rpx; border-top: 1rpx solid var(--rgm-line, rgba(255,255,255,0.08));">
          <button
            style="flex: 1; min-width: 0; margin: 0; padding: 0 16rpx; height: 76rpx; line-height: 1.25; display: flex; align-items: center; justify-content: center; font-size: 25rpx; font-weight: 700; border-radius: 20rpx; background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b22 100%)); color: #ffffff; border: none; white-space: nowrap;"
            @click="showSubClubsModal = false; openCreateClubModal();"
          >
            ✨ 自建分队 / 独立跑团 (满3人绑表解锁)
          </button>
        </view>
      </view>
    </view>

    <!-- ── 3. Grand Community Roster Modal (大群体戈友花名册) ── -->
    <view v-if="showOrgMembersModal" class="modal-mask" @click="showOrgMembersModal = false">
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">【{{ currentOrg?.name }}】戈友花名册</text>
            <text class="count-pill">{{ orgMembers.length }} 人</text>
          </view>
          <text class="close-btn" @click="showOrgMembersModal = false">✕</text>
        </view>

        <input
          class="search-member-input"
          type="text"
          :adjust-position="false"
          :cursor-spacing="30"
          placeholder="🔍 搜索戈友姓名、班级或戈壁经历(如戈20/新戈)..."
          v-model="orgMemberSearch"
        />

        <scroll-view scroll-y class="members-scroll">
          <view v-for="m in filteredOrgMembers" :key="m.user_id" class="member-row org-member-row">
            <view class="m-left">
              <image class="m-avatar" :src="m.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="m-info">
                <view class="m-name-line">
                  <text class="m-name">{{ m.real_name || m.display_name }}</text>
                  <text v-if="m.role === 'owner'" class="m-role-badge owner">👑 主理人</text>
                  <text v-else-if="m.role === 'admin'" class="m-role-badge admin">🛡️ 管理员</text>
                  <text
                    class="m-status-pill"
                    :class="m.status === 'pending' ? 'pending' : ((m.status === 'temporary' || !m.class_name) ? 'temporary' : 'confirmed')"
                  >
                    {{ m.status === 'pending' ? '⏳ 待审核' : ((m.status === 'temporary' || !m.class_name) ? '资料待补' : '✓ 已核验') }}
                  </text>
                </view>
                <view class="m-tags-line">
                  <text class="m-class-tag" :class="{ 'is-empty': !m.class_name }">{{ m.class_name || '未设班级' }}</text>
                  <text v-if="m.gobi_experience" class="m-gobi-tag" :class="{ 'is-new': m.gobi_experience === '新戈' }">
                    {{ m.gobi_experience === '新戈' ? '🌱 新戈' : '🏅 ' + m.gobi_experience }}
                  </text>
                </view>
                <text class="m-sub-text">
                  {{ m.gender === 'female' ? '女' : '男' }} · {{ m.age_group || getAgeGroup(m.date_of_birth) }} · 分队: {{ m.sub_clubs && m.sub_clubs.length ? m.sub_clubs.map((s: any) => s.name).join('、') : '暂未入队' }}
                </text>
                <text v-if="m.status === 'temporary' && ((m.missing_required_fields && m.missing_required_fields.length) || (m.missing_fields && m.missing_fields.length))" class="m-missing-text" style="font-size: 20rpx; color: var(--rgm-red, #f43f5e); display: block; margin-top: 4rpx;">
                  缺: {{ (m.missing_required_fields || m.missing_fields.map((f: any) => f.label || f.field)).join('、') }}
                </text>
              </view>
            </view>

            <view
              v-if="m.status === 'pending' || (isOrgOwner && m.role !== 'owner' && m.status === 'confirmed')"
              class="m-actions org-m-actions"
            >
              <button
                v-if="m.status === 'pending'"
                class="act-pill coach-pill"
                @click="handleConfirmOrgMember(m.user_id)"
              >
                ✓ 核对通过
              </button>
              <button
                v-if="isOrgOwner && m.role === 'admin'"
                class="act-pill revoke-admin-pill"
                @click="handleToggleOrgMemberRole(m, 'member')"
              >
                撤销管理
              </button>
              <button
                v-else-if="isOrgOwner && m.role !== 'owner' && m.status === 'confirmed'"
                class="act-pill appoint-admin-pill"
                @click="handleToggleOrgMemberRole(m, 'admin')"
              >
                委派管理
              </button>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── 4. Join Mode Setting Modal (团长设置入团规则) ── -->
    <view v-if="showJoinModeModal" class="modal-mask" @click="showJoinModeModal = false" @touchmove.stop.prevent>
      <view class="modal-content join-mode-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">⚙️ 入团规则设置</text>
            <text class="count-pill">{{ currentClub?.name }}</text>
          </view>
          <text class="close-btn" @click="showJoinModeModal = false">✕</text>
        </view>

        <view class="modal-body">
          <view class="jm-options-list">
            <!-- Option 1: 自由入团 -->
            <view
              class="jm-option-card"
              :class="{ 'is-selected': selectedJoinMode === 'free' }"
              @click="selectedJoinMode = 'free'"
            >
              <view class="jm-opt-radio">
                <text v-if="selectedJoinMode === 'free'" class="jm-radio-dot">●</text>
                <text v-else class="jm-radio-circle">○</text>
              </view>
              <view class="jm-opt-content">
                <view class="jm-opt-header">
                  <text class="jm-opt-title">🟢 自由入团（免邀请码）</text>
                  <text class="jm-rec-tag">推荐</text>
                </view>
              </view>
            </view>

            <!-- Option 2: 凭专属邀请码入团 -->
            <view
              class="jm-option-card"
              :class="{ 'is-selected': selectedJoinMode === 'invite' }"
              @click="selectedJoinMode = 'invite'"
            >
              <view class="jm-opt-radio">
                <text v-if="selectedJoinMode === 'invite'" class="jm-radio-dot">●</text>
                <text v-else class="jm-radio-circle">○</text>
              </view>
              <view class="jm-opt-content">
                <view class="jm-opt-header">
                  <text class="jm-opt-title">🔒 凭专属邀请码入团</text>
                </view>
              </view>
            </view>
          </view>

          <!-- Invite code display & editing section (only owner & coach) -->
          <view class="jm-code-manage-section">
            <view class="jm-section-title-row">
              <text class="jm-section-title">🔑 跑团专属邀请码</text>
            </view>

            <view class="jm-code-input-row">
              <input
                class="jm-code-input"
                type="text"
                placeholder="3-12位字母或数字(如 FD8888)"
                v-model="editInviteCode"
                maxlength="12"
              />
              <button class="jm-action-btn jm-gen-btn" @click="handleGenerateRandomCode">
                🎲 随机生成
              </button>
            </view>

            <view class="jm-code-actions-row">
              <button class="jm-action-btn jm-copy-btn" @click="handleCopyClubInviteCode">
                📋 复制邀请码
              </button>
              <!-- #ifdef MP-WEIXIN -->
              <button class="jm-action-btn jm-share-btn" open-type="share" data-share-type="club" :data-club-id="currentClub?.id" :data-club-name="currentClub?.name" :data-invite-code="currentClub?.invite_code || ''">
                📤 转发跑团卡片
              </button>
              <!-- #endif -->
            </view>
          </view>

          <view class="modal-btn-row">
            <button class="btn-cancel" @click="showJoinModeModal = false">取消</button>
            <button class="btn-submit" :loading="savingJoinMode" @click="saveClubJoinMode">保存设置</button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── 4.5 Org Join Mode & Basic Settings Modal (大群主理人/管理员设置大群信息与入会规则) ── -->
    <view v-if="showOrgJoinModeModal" class="modal-mask" @click="showOrgJoinModeModal = false" @touchmove.stop.prevent>
      <view class="modal-content join-mode-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">⚙️ 大群设定与入会规则</text>
            <text class="count-pill">{{ currentOrg?.name }}</text>
          </view>
          <text class="close-btn" @click="showOrgJoinModeModal = false">✕</text>
        </view>

        <view class="modal-body">
          <view class="jm-basic-info-section">
            <text class="jm-section-title" style="display: block; margin-bottom: 14rpx;">🏛️ 大群名称与简介</text>
            <input
              class="jm-text-input"
              type="text"
              placeholder="请输入大群名称"
              v-model="editOrgNameInput"
            />
            <input
              class="jm-text-input"
              type="text"
              placeholder="请输入大群简介（选填）"
              v-model="editOrgDescInput"
              style="margin-bottom: 0;"
            />
          </view>

          <view class="jm-options-list">
            <!-- Option 1: 自由入会 -->
            <view
              class="jm-option-card"
              :class="{ 'is-selected': selectedOrgJoinMode === 'free' }"
              @click="selectedOrgJoinMode = 'free'"
            >
              <view class="jm-opt-radio">
                <text v-if="selectedOrgJoinMode === 'free'" class="jm-radio-dot">●</text>
                <text v-else class="jm-radio-circle">○</text>
              </view>
              <view class="jm-opt-content">
                <view class="jm-opt-header" style="margin-bottom: 0;">
                  <text class="jm-opt-title">🟢 自由入会（免邀请码）</text>
                </view>
              </view>
            </view>

            <!-- Option 2: 凭专属邀请码入会 -->
            <view
              class="jm-option-card"
              :class="{ 'is-selected': selectedOrgJoinMode === 'invite' }"
              @click="selectedOrgJoinMode = 'invite'"
            >
              <view class="jm-opt-radio">
                <text v-if="selectedOrgJoinMode === 'invite'" class="jm-radio-dot">●</text>
                <text v-else class="jm-radio-circle">○</text>
              </view>
              <view class="jm-opt-content">
                <view class="jm-opt-header" style="margin-bottom: 0;">
                  <text class="jm-opt-title">🔒 凭专属邀请码入会</text>
                </view>
              </view>
            </view>
          </view>

          <!-- Invite code display & editing section (only org organizer) -->
          <view class="jm-code-manage-section">
            <view class="jm-section-title-row">
              <text class="jm-section-title">🔑 大群专属邀请码</text>
            </view>

            <view class="jm-code-input-row">
              <input
                class="jm-code-input"
                type="text"
                placeholder="4-16位字母或数字(如 FDGOBI)"
                v-model="editOrgInviteCode"
                maxlength="16"
              />
              <button class="jm-action-btn jm-gen-btn" @click="handleGenerateRandomOrgCode">
                🎲 随机生成
              </button>
            </view>

            <view class="jm-code-actions-row">
              <button class="jm-action-btn jm-copy-btn" @click="handleCopyOrgInviteCode">
                📋 复制邀请码
              </button>
              <!-- #ifdef MP-WEIXIN -->
              <button class="jm-action-btn jm-share-btn" open-type="share" data-share-type="org" :data-org-id="currentOrg?.id" :data-org-name="currentOrg?.name" :data-invite-code="currentOrg?.invite_code || ''">
                📢 转发大群卡片
              </button>
              <!-- #endif -->
            </view>
          </view>

          <view class="modal-btn-row">
            <button class="btn-cancel" @click="showOrgJoinModeModal = false">取消</button>
            <button class="btn-submit" :loading="savingOrgJoinMode" @click="saveOrgJoinMode">保存设置</button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── 4.6 Org Field Rules Modal (大群准入信息字段：必填 / 选填 / 不显示) ── -->
    <view v-if="showOrgFieldRulesModal" class="modal-mask" @click="showOrgFieldRulesModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">🛡️ 大群准入信息配置</text>
            <text class="count-pill">{{ currentOrg?.name }}</text>
          </view>
          <text class="close-btn" @click="showOrgFieldRulesModal = false">✕</text>
        </view>

        <view style="padding: 16rpx 22rpx; background: var(--rgm-card-2, rgba(168, 85, 247, 0.1)); border: 1rpx solid var(--rgm-line-solid, rgba(168, 85, 247, 0.25)); border-radius: 16rpx; margin-bottom: 16rpx;">
          <text style="font-size: 22rpx; color: var(--rgm-text-2, #d8b4fe); line-height: 1.5; display: block;">
            每个字段可设为【必填】、【选填】或【不显示】。设为“不显示”后将在入群及修改资料弹窗中隐藏且不纳入考核。
          </text>
        </view>

        <scroll-view scroll-y style="max-height: 55vh;">
          <view
            v-for="(rule, idx) in orgFieldRulesList"
            :key="rule.field || idx"
            style="display: flex; align-items: center; justify-content: space-between; gap: 16rpx; padding: 20rpx 20rpx; margin-bottom: 14rpx; border-radius: 20rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));"
          >
            <view style="flex: 1; min-width: 0; padding-right: 8rpx;">
              <text
                style="font-size: 26rpx; font-weight: 800; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
                :style="(rule.mode === 'hidden' || rule.hidden) ? 'color: var(--rgm-text-3, #71717a); text-decoration: line-through;' : 'color: var(--rgm-text, #ffffff);'"
              >
                {{ idx + 1 }}. {{ String(rule.label || '').split(/[（(]/)[0] }}
              </text>
              <text
                v-if="String(rule.label || '').includes('(') || String(rule.label || '').includes('（')"
                style="font-size: 20rpx; color: var(--rgm-text-3, #71717a); display: block; margin-top: 4rpx; white-space: nowrap;"
              >
                {{ String(rule.label || '').replace(/^[^（(]+[（(]/, '').replace(/[）)]$/, '') }}
              </text>
            </view>
            <view style="display: flex; align-items: center; gap: 10rpx; flex-shrink: 0; background: var(--rgm-card-3, rgba(255,255,255,0.04)); padding: 6rpx; border-radius: 16rpx; border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));">
              <view
                style="min-width: 78rpx; height: 52rpx; padding: 0 16rpx; border-radius: 12rpx; font-size: 22rpx; font-weight: 800; white-space: nowrap; display: flex; align-items: center; justify-content: center;"
                :style="getRuleMode(rule) === 'required' ? 'background: var(--rgm-brand, #fc4c02); color: #ffffff;' : 'background: transparent; color: var(--rgm-text-2, #a1a1aa);'"
                @click="setOrgRuleMode(idx, 'required')"
              >
                必填
              </view>
              <view
                style="min-width: 78rpx; height: 52rpx; padding: 0 16rpx; border-radius: 12rpx; font-size: 22rpx; font-weight: 800; white-space: nowrap; display: flex; align-items: center; justify-content: center;"
                :style="getRuleMode(rule) === 'optional' ? 'background: #059669; color: #ffffff;' : 'background: transparent; color: var(--rgm-text-2, #a1a1aa);'"
                @click="setOrgRuleMode(idx, 'optional')"
              >
                选填
              </view>
              <view
                style="min-width: 92rpx; height: 52rpx; padding: 0 16rpx; border-radius: 12rpx; font-size: 22rpx; font-weight: 800; white-space: nowrap; display: flex; align-items: center; justify-content: center;"
                :style="getRuleMode(rule) === 'hidden' ? 'background: #475569; color: #ffffff;' : 'background: transparent; color: var(--rgm-text-3, #71717a);'"
                @click="setOrgRuleMode(idx, 'hidden')"
              >
                不显示
              </view>
            </view>
          </view>
        </scroll-view>

        <view class="modal-btn-row" style="margin-top: 24rpx;">
          <button class="btn-cancel" @click="showOrgFieldRulesModal = false">取消</button>
          <button class="btn-submit" :loading="savingOrgFieldRules" @click="saveOrgFieldRules">保存准入规则</button>
        </view>
      </view>
    </view>

    <!-- ── 4.9 📊 大群全域跑量报表与下属分跑团 PK 榜弹窗 (大群主理人/管理员专属) ── -->
    <view v-if="showOrgReportModal" class="modal-mask" @click="showOrgReportModal = false" @touchmove.stop.prevent>
      <view class="modal-content org-members-modal" style="max-height: 86vh; display: flex; flex-direction: column;" @click.stop>
        <view class="modal-header">
          <view class="header-left-title">
            <text class="modal-title">📊 大群跑量报表与分团 PK</text>
            <text class="count-pill">{{ orgReportData?.org_name || currentOrg?.name }}</text>
          </view>
          <text class="close-btn" @click="showOrgReportModal = false">✕</text>
        </view>

        <!-- 周期切换栏 -->
        <view style="display: flex; align-items: center; justify-content: space-between; gap: 10rpx; margin-bottom: 12rpx; flex-wrap: wrap;">
          <view style="display: flex; gap: 8rpx; flex-wrap: nowrap;">
            <view
              v-for="p in [{ label: '本周', type: 'week', offset: 0 }, { label: '上周', type: 'week', offset: -1 }, { label: '本月', type: 'month', offset: 0 }, { label: '上月', type: 'month', offset: -1 }]"
              :key="p.label"
              style="padding: 10rpx 18rpx; border-radius: 14rpx; font-size: 22rpx; font-weight: 700; white-space: nowrap;"
              :style="(orgReportPeriodType === p.type && orgReportPeriodOffset === p.offset) ? 'background: var(--rgm-brand, #fc4c02); color: #ffffff; border: 1rpx solid var(--rgm-brand, #fc4c02);' : 'background: var(--rgm-card-3, rgba(255,255,255,0.06)); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));'"
              @click="switchOrgReportPeriod(p.type as any, p.offset)"
            >
              {{ p.label }}
            </view>
          </view>
          <view
            v-if="orgReportData?.wechat_summary_text"
            style="padding: 10rpx 20rpx; border-radius: 14rpx; font-size: 22rpx; font-weight: 800; background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16)); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4)); color: var(--rgm-brand-text, #fc4c02); white-space: nowrap;"
            @click="handleCopyOrgWechatReport"
          >
            📋 复制战报
          </view>
        </view>

        <!-- 当前统计周期与起止日期条 -->
        <view
          v-if="orgReportData?.period_label || orgReportData?.date_range_str"
          style="margin-bottom: 14rpx; padding: 10rpx 18rpx; border-radius: 14rpx; background: var(--rgm-card-2, rgba(255,255,255,0.04)); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08)); display: flex; align-items: center; justify-content: space-between; gap: 12rpx;"
        >
          <text style="font-size: 21rpx; font-weight: 800; color: var(--rgm-brand-text, #fc4c02); white-space: nowrap;">
            📅 {{ orgReportData.period_label }}
          </text>
          <text style="font-size: 20rpx; font-weight: 600; color: var(--rgm-text-2, #9ca3af); white-space: nowrap;">
            {{ orgReportData.date_range_str }}
          </text>
        </view>

        <!-- 顶部 2 格大群去重汇总 -->
        <view v-if="orgReportData?.summary" style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12rpx; margin-bottom: 16rpx;">
          <view style="padding: 18rpx; border-radius: 18rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.1));">
            <text style="font-size: 20rpx; font-weight: 700; color: var(--rgm-text-2, #a1a1aa); display: block;">🏃 全群去重总跑量 / 人均</text>
            <text style="font-size: 32rpx; font-weight: 900; color: var(--rgm-text, #ffffff); display: block; margin-top: 6rpx;">{{ orgReportData.summary.total_distance_km }} km</text>
            <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); display: block; margin-top: 4rpx;">人均 {{ orgReportData.summary.avg_distance_km }} km · {{ orgReportData.summary.total_runs }} 次打卡</text>
          </view>
          <view style="padding: 18rpx; border-radius: 18rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.1));">
            <text style="font-size: 20rpx; font-weight: 700; color: var(--rgm-text-2, #a1a1aa); display: block;">🏟️ 下属分跑团与出勤率</text>
            <text style="font-size: 32rpx; font-weight: 900; color: var(--rgm-text, #ffffff); display: block; margin-top: 6rpx;">{{ orgReportData.summary.sub_clubs_count }} 个分团 · {{ orgReportData.summary.attendance_rate }}%</text>
            <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); display: block; margin-top: 4rpx;">在册 {{ orgReportData.summary.total_members }}人 · 未入团 {{ orgReportData.summary.unaffiliated_count }}人</text>
          </view>
        </view>

        <!-- 子视图切换 Tab（等宽单行胶囊，不折行） -->
        <view style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10rpx; margin-bottom: 16rpx;">
          <view
            style="height: 64rpx; display: flex; align-items: center; justify-content: center; padding: 0 8rpx; border-radius: 16rpx; font-size: 22rpx; font-weight: 800; white-space: nowrap;"
            :style="orgReportTab === 'clubs_pk' ? 'background: var(--rgm-brand, #fc4c02); color: #ffffff; border: 1rpx solid var(--rgm-brand, #fc4c02);' : 'background: var(--rgm-card-3, rgba(255,255,255,0.06)); color: var(--rgm-text-2, #d4d4d8); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));'"
            @click="orgReportTab = 'clubs_pk'"
          >
            🏆 分团PK ({{ orgReportData?.sub_club_rankings?.length || 0 }})
          </view>
          <view
            style="height: 64rpx; display: flex; align-items: center; justify-content: center; padding: 0 8rpx; border-radius: 16rpx; font-size: 22rpx; font-weight: 800; white-space: nowrap;"
            :style="orgReportTab === 'members' ? 'background: var(--rgm-brand, #fc4c02); color: #ffffff; border: 1rpx solid var(--rgm-brand, #fc4c02);' : 'background: var(--rgm-card-3, rgba(255,255,255,0.06)); color: var(--rgm-text-2, #d4d4d8); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));'"
            @click="orgReportTab = 'members'"
          >
            👥 跨团全员 ({{ orgReportData?.member_rankings?.length || 0 }})
          </view>
          <view
            style="height: 64rpx; display: flex; align-items: center; justify-content: center; padding: 0 8rpx; border-radius: 16rpx; font-size: 22rpx; font-weight: 800; white-space: nowrap;"
            :style="orgReportTab === 'unaffiliated' ? 'background: #dc2626; color: #ffffff; border: 1rpx solid #dc2626;' : 'background: var(--rgm-card-3, rgba(255,255,255,0.06)); color: var(--rgm-text-2, #d4d4d8); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));'"
            @click="orgReportTab = 'unaffiliated'"
          >
            ⚠️ 未入团 ({{ orgReportData?.unaffiliated_members?.length || 0 }})
          </view>
        </view>

        <scroll-view scroll-y style="max-height: 46vh;">
          <view v-if="loadingOrgReport" style="padding: 40rpx 0; text-align: center;">
            <text style="font-size: 24rpx; color: var(--rgm-text-2, #a1a1aa);">正在汇总大群与下属分跑团跑量...</text>
          </view>

          <!-- Tab 1: 分跑团横向 PK 榜 -->
          <template v-else-if="orgReportTab === 'clubs_pk'">
            <view
              v-for="(sc, idx) in (orgReportData?.sub_club_rankings || [])"
              :key="sc.club_id"
              style="padding: 20rpx; margin-bottom: 12rpx; border-radius: 18rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));"
            >
              <view style="display: flex; align-items: center; justify-content: space-between; gap: 10rpx;">
                <view style="display: flex; align-items: center; gap: 10rpx; min-width: 0; flex: 1;">
                  <text
                    style="padding: 2rpx 12rpx; border-radius: 10rpx; font-size: 21rpx; font-weight: 900; flex-shrink: 0;"
                    :style="idx < 3 ? 'background: var(--rgm-brand, #fc4c02); color: #ffffff;' : 'background: var(--rgm-card-3, rgba(255,255,255,0.1)); color: var(--rgm-text-2, #a1a1aa);'"
                  >#{{ idx + 1 }}</text>
                  <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #ffffff); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{{ sc.club_name }}</text>
                  <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); flex-shrink: 0;">({{ sc.active_count }}/{{ sc.member_count }}人出勤)</text>
                </view>
                <text style="font-size: 26rpx; font-weight: 900; color: var(--rgm-brand-text, #fc4c02); flex-shrink: 0; white-space: nowrap;">人均 {{ sc.avg_distance_km }} km</text>
              </view>
              <view style="display: flex; align-items: center; justify-content: space-between; margin-top: 10rpx;">
                <text style="font-size: 22rpx; color: var(--rgm-text-2, #d4d4d8);">总跑量 {{ sc.total_distance_km }} km · 达标率 {{ sc.achievement_rate }}%</text>
                <text style="font-size: 21rpx; font-weight: 600; color: var(--rgm-text-2, #a1a1aa);">15k+拉练 {{ sc.lsd_15k_count }}次</text>
              </view>
            </view>
          </template>

          <!-- Tab 2: 跨跑团全员跑量榜 -->
          <template v-else-if="orgReportTab === 'members'">
            <view
              v-for="m in (orgReportData?.member_rankings || [])"
              :key="m.user_id"
              style="padding: 18rpx 20rpx; margin-bottom: 10rpx; border-radius: 16rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.06)); display: flex; align-items: center; justify-content: space-between; gap: 12rpx;"
            >
              <view style="flex: 1; min-width: 0;">
                <view style="display: flex; align-items: center; gap: 10rpx; flex-wrap: wrap;">
                  <text style="font-size: 22rpx; font-weight: 800; color: var(--rgm-text-2, #a1a1aa);">#{{ m.rank }}</text>
                  <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">{{ m.display_name }}</text>
                  <text v-if="m.is_unaffiliated" style="font-size: 19rpx; font-weight: 700; padding: 2rpx 10rpx; border-radius: 8rpx; background: rgba(220,38,38,0.12); color: var(--rgm-red, #ef4444); border: 1rpx solid rgba(220,38,38,0.28); white-space: nowrap;">未入分团</text>
                  <text v-else style="font-size: 19rpx; font-weight: 700; padding: 2rpx 10rpx; border-radius: 8rpx; background: var(--rgm-brand-tint, rgba(252,76,2,0.14)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252,76,2,0.3));">{{ (m.sub_club_names || []).join(' / ') }}</text>
                </view>
                <text style="font-size: 20rpx; color: var(--rgm-text-2, #71717a); display: block; margin-top: 4rpx;">
                  {{ m.class_name || '未填班级' }} · 打卡 {{ m.runs_count }}次 · 均速 {{ m.avg_pace }}
                </text>
              </view>
              <text style="font-size: 28rpx; font-weight: 900; color: var(--rgm-text, #ffffff); flex-shrink: 0; white-space: nowrap;">{{ m.distance_km }} km</text>
            </view>
          </template>

          <!-- Tab 3: 未入分跑团游离群员一键分团调配 -->
          <template v-else-if="orgReportTab === 'unaffiliated'">
            <view v-if="!(orgReportData?.unaffiliated_members?.length)" style="padding: 40rpx 0; text-align: center;">
              <text style="font-size: 24rpx; font-weight: 700; color: var(--rgm-green, #059669);">🎉 全体大群成员均已加入下属分跑团</text>
            </view>
            <view
              v-for="um in (orgReportData?.unaffiliated_members || [])"
              :key="um.user_id"
              style="padding: 20rpx; margin-bottom: 12rpx; border-radius: 18rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line-solid, rgba(244,63,94,0.25)); display: flex; align-items: center; justify-content: space-between; gap: 12rpx;"
            >
              <view style="flex: 1; min-width: 0;">
                <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #ffffff); display: block;">{{ um.display_name }} ({{ um.distance_km }} km)</text>
                <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); display: block; margin-top: 4rpx;">{{ um.class_name || '未填班级' }} · {{ um.gobi_experience || '未填戈赛经历' }}</text>
              </view>
              <button
                style="margin: 0; padding: 0 22rpx; height: 56rpx; line-height: 56rpx; border-radius: 14rpx; background: var(--rgm-brand, #fc4c02); color: #ffffff; font-size: 22rpx; font-weight: 800; flex-shrink: 0;"
                @click="promptAssignUnaffiliatedMember(um)"
              >
                ➕ 划入分跑团
              </button>
            </view>
          </template>
        </scroll-view>
      </view>
    </view>

    <!-- ── 4.10 🚩 大群跨跑团联合活动 / 分团对抗赛弹窗 ── -->
    <view v-if="showOrgEventsModal" class="modal-mask" @click="showOrgEventsModal = false" @touchmove.stop.prevent>
      <view class="modal-content org-members-modal" style="max-height: 86vh; display: flex; flex-direction: column;" @click.stop>
        <view class="modal-header">
          <view class="header-left-title">
            <text class="modal-title">🚩 跨跑团联合活动</text>
            <text class="count-pill">{{ currentOrg?.name }}</text>
          </view>
          <text class="close-btn" @click="showOrgEventsModal = false">✕</text>
        </view>

        <scroll-view scroll-y style="max-height: 70vh;">
          <!-- 发起新跨跑团活动表单 -->
          <view style="padding: 20rpx; border-radius: 20rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line-solid, rgba(168,85,247,0.35)); margin-bottom: 20rpx;">
            <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #ffffff); display: block; margin-bottom: 14rpx;">✨ 发起跨跑团联合约跑 / 里程挑战</text>
            <view style="display: flex; gap: 12rpx; margin-bottom: 14rpx;">
              <view
                style="flex: 1; text-align: center; padding: 14rpx 8rpx; border-radius: 14rpx; font-size: 22rpx; font-weight: 800; white-space: nowrap;"
                :style="orgEvtType === 'group_run' ? 'background: var(--rgm-brand, #fc4c02); color: #ffffff; border: 1rpx solid var(--rgm-brand, #fc4c02);' : 'background: var(--rgm-card-3, rgba(255,255,255,0.06)); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));'"
                @click="orgEvtType = 'group_run'"
              >
                📍 跨团联合合练
              </view>
              <view
                style="flex: 1; text-align: center; padding: 14rpx 8rpx; border-radius: 14rpx; font-size: 22rpx; font-weight: 800; white-space: nowrap;"
                :style="orgEvtType === 'distance_challenge' ? 'background: var(--rgm-brand, #fc4c02); color: #ffffff; border: 1rpx solid var(--rgm-brand, #fc4c02);' : 'background: var(--rgm-card-3, rgba(255,255,255,0.06)); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));'"
                @click="orgEvtType = 'distance_challenge'"
              >
                🏆 跨团里程对抗赛
              </view>
            </view>

            <input
              v-model="orgEvtTitle"
              placeholder="活动标题（如：周末全群20km联合拉练）"
              style="width: 100%; height: 68rpx; padding: 0 20rpx; border-radius: 14rpx; background: var(--rgm-card, rgba(0,0,0,0.35)); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.12)); color: var(--rgm-text, #ffffff); font-size: 24rpx; margin-bottom: 12rpx; box-sizing: border-box;"
            />
            <view style="display: flex; gap: 12rpx; margin-bottom: 12rpx;">
              <input
                v-model="orgEvtMeetTime"
                placeholder="时间 (如 2026-11-15 06:30)"
                style="flex: 1.4; height: 68rpx; padding: 0 18rpx; border-radius: 14rpx; background: var(--rgm-card, rgba(0,0,0,0.35)); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.12)); color: var(--rgm-text, #ffffff); font-size: 22rpx; box-sizing: border-box;"
              />
              <input
                v-model="orgEvtTargetKm"
                type="number"
                placeholder="目标km"
                style="flex: 0.8; height: 68rpx; padding: 0 18rpx; border-radius: 14rpx; background: var(--rgm-card, rgba(0,0,0,0.35)); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.12)); color: var(--rgm-text, #ffffff); font-size: 22rpx; box-sizing: border-box;"
              />
            </view>
            <input
              v-if="orgEvtType === 'group_run'"
              v-model="orgEvtLocation"
              placeholder="集合地点（如：世纪公园7号门 / 奥森南园）"
              style="width: 100%; height: 68rpx; padding: 0 20rpx; border-radius: 14rpx; background: var(--rgm-card, rgba(0,0,0,0.35)); border: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.12)); color: var(--rgm-text, #ffffff); font-size: 24rpx; margin-bottom: 12rpx; box-sizing: border-box;"
            />
            <button
              :loading="creatingOrgEvent"
              style="width: 100%; height: 72rpx; line-height: 72rpx; border-radius: 16rpx; background: var(--rgm-brand, #fc4c02); color: #ffffff; font-size: 25rpx; font-weight: 800; margin-top: 6rpx;"
              @click="handlePublishOrgEvent"
            >
              🚩 同步下发至全部下属分跑团
            </button>
          </view>

          <!-- 已发布跨跑团活动及各分跑团贡献榜 -->
          <text style="font-size: 24rpx; font-weight: 800; color: var(--rgm-text-2, #a1a1aa); display: block; margin-bottom: 12rpx;">
            📋 已发布的跨跑团活动 ({{ orgEventsList.length }})
          </text>
          <view
            v-for="ev in orgEventsList"
            :key="ev.id"
            style="padding: 20rpx; margin-bottom: 14rpx; border-radius: 18rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line-solid, rgba(245,158,11,0.3));"
          >
            <view style="display: flex; align-items: center; justify-content: space-between; gap: 10rpx;">
              <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">🏛️ {{ ev.title }}</text>
              <text style="font-size: 22rpx; font-weight: 800; color: var(--rgm-green, #059669); white-space: nowrap;">报名 {{ ev.participants_count || 0 }}人</text>
            </view>
            <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa); display: block; margin-top: 6rpx;">
              ⏰ {{ ev.meet_time || ev.start_date }} · 🎯 目标 {{ ev.target_km }}km
            </text>
            <view v-if="ev.club_breakdown && ev.club_breakdown.length" style="margin-top: 12rpx; padding-top: 10rpx; border-top: 1rpx solid var(--rgm-line-solid, rgba(255,255,255,0.08));">
              <view
                v-for="cb in ev.club_breakdown"
                :key="cb.club_id"
                style="display: flex; justify-content: space-between; font-size: 21rpx; color: var(--rgm-text-2, #d4d4d8); padding: 4rpx 0;"
              >
                <text>{{ cb.club_name }}</text>
                <text>报名 {{ cb.registered_count }}人 · 完赛 {{ cb.completed_count }}人 · {{ cb.total_km }}km</text>
              </view>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── 5. Specific Club Invite Code Prompt Modal (跑者加入凭码跑团弹窗) ── -->
    <view v-if="showClubCodeModal" class="modal-mask" @click="showClubCodeModal = false" @touchmove.stop.prevent>
      <view class="modal-content club-code-prompt-modal" @click.stop>
        <view class="modal-header">
          <text class="modal-title">🔒 凭邀请码加入跑团</text>
          <text class="close-btn" @click="showClubCodeModal = false">✕</text>
        </view>

        <view class="modal-body">
          <view class="prompt-target-banner">
            <text class="ptb-label">目标跑团：</text>
            <text class="ptb-name">{{ targetClubForCodeJoin?.name }}</text>
          </view>

          <!-- 新用户一键同步微信昵称与头像 -->
          <view v-if="needsWechatNickname" class="join-wx-profile-card" style="margin-bottom: 20rpx;">
            <view class="jwp-head">
              <text class="jwp-badge">👤 入团名片</text>
            </view>
            <view class="jwp-row">
              <!-- #ifdef MP-WEIXIN -->
              <button class="jwp-avatar-btn" open-type="chooseAvatar" @chooseavatar="onJoinChooseAvatar">
                <image v-if="joinRunnerAvatar || user?.avatar_url" class="jwp-avatar-img" :src="joinRunnerAvatar || user?.avatar_url" mode="aspectFill" />
                <text v-else class="jwp-avatar-placeholder">📷</text>
                <text class="jwp-avatar-sub">微信头像</text>
              </button>
              <!-- #endif -->
              <view class="jwp-input-col">
                <text class="jwp-label">跑团昵称 *</text>
                <input
                  type="nickname"
                  class="jwp-nickname-input"
                  v-model="joinRunnerNickname"
                  placeholder="点击此处 · 一键填入微信昵称"
                  @blur="onJoinNicknameBlur"
                />
              </view>
            </view>
          </view>

          <input
            class="club-code-input"
            type="text"
            maxlength="12"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="请输入跑团邀请码"
            v-model="clubJoinCodeInput"
          />

          <view class="modal-btn-row">
            <button class="btn-cancel" @click="showClubCodeModal = false">取消</button>
            <button class="btn-submit" :loading="joiningClubId === targetClubForCodeJoin?.id" @click="submitClubCodeJoin">立即加入</button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── 6. Club Periodic Report Modal (跑团周报/月报专属战报弹窗) ── -->
    <view v-if="showReportModal" class="modal-mask" @click="showReportModal = false">
      <view class="modal-content large-modal report-modal-content" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">📊 跑团周报与月报</text>
          </view>
          <text class="close-btn" @click="showReportModal = false">✕</text>
        </view>

        <!-- Period tabs: 周报 vs 月报 -->
        <view class="modal-tab-row">
          <view
            class="modal-tab-segment"
            :class="{ active: reportPeriodType === 'week' }"
            @click="handleSwitchReportPeriod('week')"
          >
            📅 周报
          </view>
          <view
            class="modal-tab-segment"
            :class="{ active: reportPeriodType === 'month' }"
            @click="handleSwitchReportPeriod('month')"
          >
            🗓️ 月报
          </view>
        </view>

        <!-- Period selector: 本周/本月 vs 上周/上月 -->
        <view class="report-sub-tabs">
          <view
            class="report-sub-tab"
            :class="{ active: reportPeriodOffset === 0 }"
            @click="handleSwitchReportOffset(0)"
          >
            {{ reportPeriodType === 'week' ? '本周' : '本月' }}
          </view>
          <view
            class="report-sub-tab"
            :class="{ active: reportPeriodOffset === -1 }"
            @click="handleSwitchReportOffset(-1)"
          >
            {{ reportPeriodType === 'week' ? '上周' : '上月' }}
          </view>
        </view>

        <!-- Trail running filter selector: 包含越野(默认) / 仅去除越野配速 / 去除越野跑量与配速 -->
        <view v-if="Number(reportData?.trail_activities_count || 0) > 0" style="display: flex; align-items: center; justify-content: space-between; padding: 0 32rpx; margin-bottom: 6rpx;">
          <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); font-weight: 700;">🏔️ 越野跑统计口径</text>
          <text style="font-size: 20rpx; color: var(--rgm-green, #34d399); font-weight: 700;">
            本周期含越野 {{ reportData.trail_activities_count }} 次 ({{ reportData.trail_distance_km }} km)
          </text>
        </view>
        <view class="report-sub-tabs" style="margin-top: -6rpx;">
          <view
            class="report-sub-tab"
            :class="{ active: reportTrailMode === 'include' }"
            @click="handleSwitchReportTrailMode('include')"
          >
            🏔️ 含越野(默认)
          </view>
          <view
            class="report-sub-tab"
            :class="{ active: reportTrailMode === 'exclude_pace' }"
            @click="handleSwitchReportTrailMode('exclude_pace')"
          >
            ⏱️ 仅去越野配速
          </view>
          <view
            class="report-sub-tab"
            :class="{ active: reportTrailMode === 'exclude_all' }"
            @click="handleSwitchReportTrailMode('exclude_all')"
          >
            🛣️ 去越野跑量/配速
          </view>
        </view>

        <!-- View mode tabs: 🎨 战报海报图片 vs 📋 全员目标列表 vs 💬 微信群文本 -->
        <view class="report-view-mode-tabs">
          <view
            class="report-view-tab"
            :class="{ active: reportViewMode === 'poster' }"
            @click="reportViewMode = 'poster'"
          >
            🎨 海报
          </view>
          <view
            class="report-view-tab"
            :class="{ active: reportViewMode === 'table' }"
            @click="reportViewMode = 'table'"
          >
            📋 全员达标榜
          </view>
          <view
            class="report-view-tab"
            :class="{ active: reportViewMode === 'text' }"
            @click="reportViewMode = 'text'"
          >
            💬 群文本
          </view>
        </view>

        <!-- Loading State -->
        <view v-if="loadingReport" class="report-loading-box">
          <text class="loading-spinner">⏳</text>
          <text class="loading-text">正在汇算团队跑步大数据...</text>
        </view>

        <!-- Report Body -->
        <scroll-view v-else-if="reportData" scroll-y class="modal-body modal-scroll report-scroll-body">
          <!-- ── 1. POSTER VIEW (图片海报样式) ── -->
          <view v-if="reportViewMode === 'poster'" class="poster-card-wrapper">
            <view class="report-poster-card">
              <!-- Top Branding Header -->
              <view class="poster-card-header">
                <view class="poster-brand-row">
                  <image
                    class="poster-club-logo"
                    :src="currentClub?.logo_url || '/static/logo-square.png'"
                    mode="aspectFill"
                  />
                  <view class="poster-club-titles">
                    <text class="poster-club-name">{{ reportData.club_name || currentClub?.name }}</text>
                    <text class="poster-tagline">👑 跑团官方战报 · 荣誉榜</text>
                    <text
                      v-if="reportData.trail_mode && reportData.trail_mode !== 'include'"
                      style="font-size: 18rpx; color: var(--rgm-green, #34d399); font-weight: 700; margin-top: 2rpx;"
                    >
                      {{ reportData.trail_mode === 'exclude_all' ? '🛣️ 已去除越野跑量与配速' : '⏱️ 均速已去除越野跑' }}
                    </text>
                  </view>
                </view>
                <view class="poster-period-pill">
                  <text class="poster-period-name">{{ reportData.period_label }}</text>
                  <text class="poster-period-date">{{ reportData.date_range_str }}</text>
                </view>
              </view>

              <!-- Hero Total Mileage Box -->
              <view class="poster-hero-mileage">
                <text class="phm-label">全团累计奔跑总里程</text>
                <view class="phm-num-row">
                  <text class="phm-num">{{ reportData.total_distance_km }}</text>
                  <text class="phm-unit">KM</text>
                </view>
                <text class="phm-sub">汇聚全员热血汗水 · 每一步都在突破极限</text>
              </view>

              <!-- 4-Tile Metrics Bar -->
              <view class="poster-grid-stats">
                <view class="pg-item">
                  <text class="pg-label">出勤率</text>
                  <text class="pg-val">{{ reportData.attendance_rate_pct }}%</text>
                  <text class="pg-sub">{{ reportData.active_members_count }}/{{ reportData.total_members_count }}人</text>
                </view>
                <view class="pg-item">
                  <text class="pg-label">全团均速</text>
                  <text class="pg-val font-mono">{{ reportData.avg_pace_str }}</text>
                  <text class="pg-sub">有效巡航</text>
                </view>
                <view class="pg-item">
                  <text class="pg-label">累计爬升</text>
                  <text class="pg-val">+{{ reportData.total_elevation_gain_m }}m</text>
                  <text class="pg-sub">克服重力</text>
                </view>
                <view class="pg-item">
                  <text class="pg-label">打卡人次</text>
                  <text class="pg-val">{{ reportData.total_activities_count }}次</text>
                  <text class="pg-sub">坚持印记</text>
                </view>
              </view>

              <!-- 🏆 Top 3 Podium Cards -->
              <view class="poster-podium-box">
                <view class="ppb-header">
                  <text class="ppb-icon">🏆</text>
                  <text class="ppb-title">荣誉三甲领奖台</text>
                </view>
                <view v-if="reportData.podium && reportData.podium.length > 0" class="poster-podium-cards">
                  <view
                    v-for="(p, idx) in reportData.podium"
                    :key="p.user_id"
                    class="ppc-row"
                    :class="'podium-rank-' + (idx + 1)"
                  >
                    <view class="ppc-rank-badge">{{ idx === 0 ? '🥇 冠军' : idx === 1 ? '🥈 亚军' : '🥉 季军' }}</view>
                    <image
                      class="ppc-avatar"
                      :src="p.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80'"
                      mode="aspectFill"
                    />
                    <view class="ppc-name-col">
                      <text class="ppc-name">{{ p.display_name }}</text>
                      <text class="ppc-detail">{{ p.runs_count }}次打卡 · 均速 {{ p.avg_pace_str }}</text>
                    </view>
                    <view class="ppc-km-col">
                      <text class="ppc-km">{{ p.distance_km }}</text>
                      <text class="ppc-km-u">km</text>
                    </view>
                  </view>
                </view>
                <view v-else class="empty-podium-text">本周期暂无打卡记录</view>
              </view>

              <!-- 🌟 Highlights (毅力先锋 & 最长突破) -->
              <view v-if="reportData.hardcore_runner || reportData.longest_run" class="poster-highlights-box">
                <view v-if="reportData.hardcore_runner" class="phb-item">
                  <text class="phb-tag">🌟 毅力先锋</text>
                  <text class="phb-name">{{ reportData.hardcore_runner.display_name }}</text>
                  <text class="phb-sub">打卡 {{ reportData.hardcore_runner.runs_count }} 次 · {{ reportData.hardcore_runner.distance_km }} km</text>
                </view>
                <view v-if="reportData.longest_run" class="phb-item">
                  <text class="phb-tag">🚀 最长突破</text>
                  <text class="phb-name">{{ reportData.longest_run.runner_name }}</text>
                  <text class="phb-sub">单次 {{ reportData.longest_run.distance_km }} km · {{ reportData.longest_run.avg_pace_str }}</text>
                </view>
              </view>

              <!-- 📋 Poster Member Progress Summary Section -->
              <view class="poster-member-progress-box">
                <view class="pmb-header">
                  <view class="pmb-title-left">
                    <text class="pmb-icon">📋</text>
                    <text class="pmb-title">全员跑量与目标达成</text>
                  </view>
                  <view class="pmb-rate-pill">
                    达标 {{ reportData.achieved_members_count || 0 }}/{{ reportData.total_members_count || 0 }}人
                  </view>
                </view>
                <view class="poster-progress-table">
                  <view class="ppt-head-row">
                    <text class="ppt-th th-member">团员</text>
                    <text class="ppt-th th-target">目标</text>
                    <text class="ppt-th th-actual">实际</text>
                    <text class="ppt-th th-rate">完成度</text>
                  </view>
                  <view
                    v-for="(item, idx) in (reportData.member_progress_list || []).slice(0, 8)"
                    :key="item.user_id"
                    class="ppt-body-row"
                  >
                    <view class="ppt-td td-member">
                      <text class="ppt-rank-num">{{ idx + 1 }}</text>
                      <image
                        class="ppt-mini-avatar"
                        :src="item.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80'"
                        mode="aspectFill"
                      />
                      <text class="ppt-name-text">{{ item.display_name }}</text>
                    </view>
                    <text class="ppt-td td-target font-mono">{{ item.target_km }}k</text>
                    <text class="ppt-td td-actual font-mono">{{ item.distance_km }}k</text>
                    <view class="ppt-td td-rate">
                      <text :class="item.is_achieved ? 'rate-achieved' : 'rate-pending'">{{ item.completion_rate }}%</text>
                    </view>
                  </view>
                  <view
                    v-if="(reportData.member_progress_list || []).length > 8"
                    class="ppt-more-btn"
                    @click="reportViewMode = 'table'"
                  >
                    查看全部 {{ (reportData.member_progress_list || []).length }} 位成员目标表格 ➔
                  </view>
                </view>
              </view>

              <!-- 💡 Canova Quote Card -->
              <view class="poster-canova-quote">
                <view class="pcq-header">
                  <text class="pcq-icon">💡</text>
                  <text class="pcq-title">Renato Canova 科学耐力团队复盘</text>
                </view>
                <text class="pcq-text">“{{ reportData.canova_critique }}”</text>
              </view>

              <!-- Bottom Watermark & Stamp -->
              <view class="poster-footer-stamp">
                <view class="pfs-left">
                  <text class="pfs-brand">万跑跑团助手</text>
                  <text class="pfs-slogan">微信扫码进入万跑跑团助手小程序 · 科学耐力训练与跑团系统</text>
                </view>
                <view style="display: flex; align-items: center; gap: 16rpx;">
                  <view
                    v-if="reportData.qrcode_base64 || reportData.qrcode_url"
                    style="background: #ffffff; padding: 8rpx; border-radius: 14rpx; display: flex; flex-direction: column; align-items: center; box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.3);"
                  >
                    <image
                      :src="reportData.qrcode_base64 ? (reportData.qrcode_base64.startsWith('data:') ? reportData.qrcode_base64 : 'data:image/jpeg;base64,' + reportData.qrcode_base64) : reportData.qrcode_url"
                      style="width: 92rpx; height: 92rpx; border-radius: 8rpx;"
                      mode="aspectFit"
                    />
                    <text style="font-size: 15rpx; font-weight: 700; color: #3f3f46; margin-top: 2rpx;">万跑小程序</text>
                  </view>
                  <view class="pfs-stamp-badge">
                    <text class="pfs-stamp-txt">认证战报</text>
                  </view>
                </view>
              </view>
            </view>
          </view>

          <!-- ── 2. TABLE VIEW (全员跑量与目标完成度完整表格) ── -->
          <view v-else-if="reportViewMode === 'table'" class="table-mode-container">
            <!-- Team Goal Overview Card -->
            <view class="team-goal-overview-card">
              <view class="tgoc-top">
                <view class="tgoc-stat-item">
                  <text class="tgoc-stat-label">团队目标跑量</text>
                  <text class="tgoc-stat-val font-mono">{{ reportData.total_target_km }} <text class="tgoc-u">KM</text></text>
                </view>
                <view class="tgoc-stat-divider"></view>
                <view class="tgoc-stat-item">
                  <text class="tgoc-stat-label">实际累计奔跑</text>
                  <text class="tgoc-stat-val val-orange font-mono">{{ reportData.total_distance_km }} <text class="tgoc-u">KM</text></text>
                </view>
                <view class="tgoc-stat-divider"></view>
                <view class="tgoc-stat-item">
                  <text class="tgoc-stat-label">全团完成度</text>
                  <text class="tgoc-stat-val val-green font-mono">{{ reportData.team_completion_rate }}%</text>
                </view>
              </view>

              <!-- Progress Bar -->
              <view class="tgoc-bar-row">
                <view class="tgoc-bar-bg">
                  <view
                    class="tgoc-bar-fill"
                    :style="{ width: Math.min(reportData.team_completion_rate || 0, 100) + '%' }"
                  ></view>
                </view>
                <text class="tgoc-bar-text">达标人数：{{ reportData.achieved_members_count || 0 }} / {{ reportData.total_members_count || 0 }} 人</text>
              </view>
            </view>

            <!-- Table Filter and Sort Bar -->
            <view class="table-controls-bar">
              <view class="table-filter-pills">
                <text
                  class="tf-pill"
                  :class="{ active: reportFilter === 'all' }"
                  @click="reportFilter = 'all'"
                >
                  全部 ({{ (reportData.member_progress_list || []).length }})
                </text>
                <text
                  class="tf-pill"
                  :class="{ active: reportFilter === 'achieved' }"
                  @click="reportFilter = 'achieved'"
                >
                  已达标 ({{ reportData.achieved_members_count || 0 }})
                </text>
                <text
                  class="tf-pill"
                  :class="{ active: reportFilter === 'pending' }"
                  @click="reportFilter = 'pending'"
                >
                  未达标 ({{ Math.max(0, (reportData.total_members_count || 0) - (reportData.achieved_members_count || 0)) }})
                </text>
              </view>

              <view class="table-controls-right">
                <view class="table-poster-action-pill" @click="handleSaveTablePosterToAlbum">
                  <text class="tpap-icon">📸</text>
                  <text class="tpap-text">存海报</text>
                </view>
                <view class="table-sort-switch" @click="toggleReportSort">
                  <text class="tss-label">排序: </text>
                  <text class="tss-val">{{ reportSortBy === 'completion' ? '完成度 ⬇️' : '实际跑量 ⬇️' }}</text>
                </view>
              </view>
            </view>

            <!-- Search input if many members -->
            <view v-if="(reportData.member_progress_list || []).length > 8" class="table-search-row">
              <input
                v-model="reportSearch"
                class="table-search-input"
                placeholder="🔍 搜索团员姓名..."
              />
            </view>

            <!-- Table Card -->
            <view class="member-table-card">
              <!-- Table Header -->
              <view class="mtc-header-row">
                <text class="mtc-th th-col-member">团员</text>
                <text class="mtc-th th-col-target">目标跑量</text>
                <text class="mtc-th th-col-actual">实际跑量</text>
                <text class="mtc-th th-col-progress">完成度</text>
              </view>

              <!-- Table Body -->
              <view v-if="filteredSortedMemberList.length > 0" class="mtc-body-list">
                <view
                  v-for="(m, idx) in filteredSortedMemberList"
                  :key="m.user_id"
                  class="mtc-row"
                  :class="{ 'row-achieved': m.is_achieved }"
                >
                  <!-- Member Info -->
                  <view class="mtc-td td-col-member">
                    <text class="mtc-rank-badge" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</text>
                    <image
                      class="mtc-avatar"
                      :src="m.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80'"
                      mode="aspectFill"
                    />
                    <view class="mtc-name-col">
                      <view class="mtc-name-row">
                        <text class="mtc-name">{{ m.display_name }}</text>
                        <text v-if="m.role === 'owner'" class="mtc-role-pill role-owner">团长</text>
                        <text v-else-if="m.role === 'coach'" class="mtc-role-pill role-coach">教练</text>
                      </view>
                      <text class="mtc-sub-detail">{{ m.runs_count > 0 ? (m.runs_count + '次打卡') : '未打卡' }}</text>
                    </view>
                  </view>

                  <!-- Target Mileage -->
                  <view class="mtc-td td-col-target font-mono">
                    <text class="mtc-target-val">{{ m.target_km }}</text>
                    <text class="mtc-km-unit">km</text>
                  </view>

                  <!-- Actual Mileage -->
                  <view class="mtc-td td-col-actual font-mono">
                    <text class="mtc-actual-val">{{ m.distance_km }}</text>
                    <text class="mtc-km-unit">km</text>
                  </view>

                  <!-- Completion Rate & Visual Bar -->
                  <view class="mtc-td td-col-progress">
                    <view class="mtc-rate-top">
                      <text
                        class="mtc-rate-pct font-mono"
                        :class="m.is_achieved ? 'text-green' : ((reportPeriodOffset === -1 || reportData?.is_past_period) ? 'text-red' : 'text-orange')"
                      >
                        {{ m.completion_rate }}%
                      </text>
                      <text
                        class="mtc-status-pill"
                        :class="m.is_achieved ? 'pill-achieved' : ((reportPeriodOffset === -1 || reportData?.is_past_period) ? 'pill-failed' : 'pill-pending')"
                      >
                        {{ m.is_achieved ? '已达标' : ((reportPeriodOffset === -1 || reportData?.is_past_period) ? '未达标' : '进行中') }}
                      </text>
                    </view>
                    <view class="mtc-mini-bar-bg">
                      <view
                        class="mtc-mini-bar-fill"
                        :class="m.is_achieved ? 'fill-green' : ((reportPeriodOffset === -1 || reportData?.is_past_period) ? 'fill-red' : 'fill-orange')"
                        :style="{ width: Math.min(m.completion_rate, 100) + '%' }"
                      ></view>
                    </view>
                  </view>
                </view>
              </view>
              <view v-else class="mtc-empty-row">
                <text class="mtc-empty-text">未找到符合条件的团员记录</text>
              </view>
            </view>
          </view>

          <!-- ── 3. TEXT VIEW (微信群纯文本预览) ── -->
          <view v-else class="text-mode-container">
            <view class="report-section-box forward-box">
              <view class="forward-header">
                <text class="forward-title">💬 微信群转发文本</text>
              </view>
              <view class="forward-preview-card">
                <text class="forward-preview-text" :selectable="true">{{ reportData.forward_text }}</text>
              </view>
            </view>
          </view>
        </scroll-view>

        <!-- Hidden Canvas for high-res 2x export -->
        <canvas
          canvas-id="reportPosterCanvas"
          id="reportPosterCanvas"
          style="width: 750px; height: 1360px; position: fixed; left: -9999px; top: -9999px;"
        ></canvas>

        <!-- Hidden Canvas for table list report poster (dynamic height) -->
        <canvas
          canvas-id="reportTablePosterCanvas"
          id="reportTablePosterCanvas"
          :style="{ width: '750px', height: tablePosterCanvasHeight + 'px', position: 'fixed', left: '-9999px', top: '-9999px' }"
        ></canvas>

        <!-- Footer Actions -->
        <view class="report-footer-actions" v-if="reportData">
          <template v-if="reportViewMode === 'poster'">
            <button class="btn-preview-poster" @click="handlePreviewPosterImage">
              📤 转发
            </button>
            <button class="btn-save-album" @click="handleSavePosterToAlbum">
              💾 保存
            </button>
          </template>
          <template v-else-if="reportViewMode === 'table'">
            <button class="btn-preview-poster" @click="handlePreviewTablePosterImage">
              📤 转发
            </button>
            <button class="btn-save-album" @click="handleSaveTablePosterToAlbum">
              💾 保存
            </button>
          </template>
          <template v-else>
            <button class="btn-copy-forward" @click="handleCopyReportForwardText">
              📋 复制转发文本
            </button>
            <button class="btn-download-report" @click="handleDownloadReportFile">
              📥 下载文本
            </button>
          </template>
        </view>
      </view>
    </view>

    <!-- ── ✨ Self-Service Club Creation Modal (自建跑团 · 邀请满5位新用户解锁) ── -->
    <view v-if="showCreateClubModal" class="modal-mask" @click="showCreateClubModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">✨ 自建专属跑团</text>
            <text
              class="count-pill"
              :style="referralStatus.can_create_club
                ? 'background: rgba(34,197,94,0.18); color: var(--rgm-green, #22c55e); border: 1rpx solid rgba(34,197,94,0.4);'
                : 'background: var(--rgm-brand-tint, rgba(252,76,2,0.15)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252,76,2,0.35));'"
            >
              {{ referralStatus.can_create_club ? '✓ 已解锁建团权益' : `已达标 ${referralStatus.invited_count}/${referralStatus.required_count || 3} 位` }}
            </text>
          </view>
          <text class="close-btn" @click="showCreateClubModal = false">✕</text>
        </view>

        <scroll-view scroll-y class="modal-body modal-scroll" style="max-height: 75vh;">
          <!-- 1. 3位新用户邀请并绑表解锁进度卡片 -->
          <view
            style="background: var(--rgm-card-2, #18181c); border: 1rpx solid var(--rgm-brand-line, rgba(252,76,2,0.35)); border-radius: 24rpx; padding: 28rpx; margin-bottom: 28rpx;"
          >
            <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14rpx;">
              <text style="font-size: 28rpx; font-weight: 700; color: var(--rgm-text, #ffffff);">
                {{ referralStatus.can_create_club ? '🎉 恭喜！您已获得自建跑团权益' : '🎁 邀请 3 位新跑友绑表解锁自建跑团' }}
              </text>
              <text
                style="font-size: 24rpx; color: var(--rgm-brand-text, #fc4c02); font-weight: 600;"
                @click="fetchCreationEligibility"
              >
                🔄 刷新进度
              </text>
            </view>

            <text style="font-size: 24rpx; color: var(--rgm-text-2, #a1a1aa); display: block; line-height: 1.5; margin-bottom: 20rpx;">
              {{ referralStatus.can_create_club
                ? '已解锁独立跑团创建权益'
                : `已达标 ${referralStatus.invited_count || 0}/3 位，还差 ${referralStatus.remaining_count} 位${referralStatus.pending_watch_count > 0 ? `（${referralStatus.pending_watch_count} 位待绑表）` : ''}` }}
            </text>

            <!-- 进度条 -->
            <view style="height: 16rpx; background: var(--rgm-line, rgba(255,255,255,0.1)); border-radius: 999rpx; overflow: hidden; margin-bottom: 22rpx;">
              <view
                :style="{
                  width: Math.min(100, Math.round((referralStatus.invited_count / (referralStatus.required_count || 3)) * 100)) + '%',
                  height: '100%',
                  background: referralStatus.can_create_club ? 'var(--rgm-green, #22c55e)' : 'var(--rgm-brand-grad, linear-gradient(90deg, #fc4c02, #ff7a00))',
                  borderRadius: '999rpx',
                  transition: 'width 0.3s ease'
                }"
              />
            </view>

            <!-- 3个席位展示 -->
            <view style="display: flex; justify-content: space-around; gap: 16rpx; margin-bottom: 22rpx;">
              <view
                v-for="slotIdx in [0, 1, 2]"
                :key="slotIdx"
                style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6rpx;"
              >
                <view
                  :style="referralStatus.invited_users?.[slotIdx]?.watch_connected
                    ? 'width: 84rpx; height: 84rpx; border-radius: 50%; border: 2rpx solid var(--rgm-green, #22c55e); background: rgba(34,197,94,0.15); display: flex; align-items: center; justify-content: center; overflow: hidden;'
                    : referralStatus.invited_users?.[slotIdx]
                    ? 'width: 84rpx; height: 84rpx; border-radius: 50%; border: 2rpx dashed #f59e0b; background: rgba(245,158,11,0.12); display: flex; align-items: center; justify-content: center; overflow: hidden;'
                    : 'width: 84rpx; height: 84rpx; border-radius: 50%; border: 2rpx dashed var(--rgm-line, rgba(255,255,255,0.22)); background: var(--rgm-bg, #111114); display: flex; align-items: center; justify-content: center;'"
                >
                  <image
                    v-if="referralStatus.invited_users?.[slotIdx]?.avatar_url"
                    :src="referralStatus.invited_users[slotIdx].avatar_url"
                    mode="aspectFill"
                    style="width: 100%; height: 100%;"
                  />
                  <text v-else-if="referralStatus.invited_users?.[slotIdx]?.watch_connected" style="font-size: 30rpx; color: var(--rgm-green, #22c55e); font-weight: 700;">✓</text>
                  <text v-else-if="referralStatus.invited_users?.[slotIdx]" style="font-size: 28rpx; color: #f59e0b; font-weight: 700;">⌚</text>
                  <text v-else style="font-size: 28rpx; color: var(--rgm-text-3, #71717a);">+{{ slotIdx + 1 }}</text>
                </view>
                <text
                  style="font-size: 22rpx; max-width: 150rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600;"
                  :style="{ color: referralStatus.invited_users?.[slotIdx] ? 'var(--rgm-text, #ffffff)' : 'var(--rgm-text-3, #71717a)' }"
                >
                  {{ referralStatus.invited_users?.[slotIdx]?.display_name || '待邀请新跑友' }}
                </text>
                <text
                  style="font-size: 19rpx; font-weight: 600;"
                  :style="{
                    color: referralStatus.invited_users?.[slotIdx]?.watch_connected
                      ? 'var(--rgm-green, #22c55e)'
                      : referralStatus.invited_users?.[slotIdx]
                      ? '#f59e0b'
                      : 'var(--rgm-text-3, #71717a)'
                  }"
                >
                  {{ referralStatus.invited_users?.[slotIdx]?.watch_connected ? '✓ 已绑定手表' : (referralStatus.invited_users?.[slotIdx] ? '⏳ 待绑定手表' : '注册并绑表生效') }}
                </text>
              </view>
            </view>

            <!-- #ifdef MP-WEIXIN -->
            <button
              v-if="!referralStatus.can_create_club"
              open-type="share"
              data-share-type="invite_new_user"
              style="width: 100%; margin: 0; padding: 0 20rpx; height: 80rpx; line-height: 1.25; display: flex; align-items: center; justify-content: center; border-radius: 20rpx; background: var(--rgm-brand-grad, linear-gradient(90deg, #fc4c02, #ff7a00)); color: var(--rgm-on-brand, #ffffff); font-size: 25rpx; font-weight: 700; border: none; white-space: nowrap;"
            >
              📤 微信邀请新跑友（还差 {{ referralStatus.remaining_count }} 人解锁）
            </button>
            <!-- #endif -->
          </view>

          <!-- 2. 自建跑团表单 -->
          <view :style="{ opacity: referralStatus.can_create_club ? 1 : 0.65 }">
            <text class="input-label">跑团名称 *</text>
            <input
              class="text-input"
              type="text"
              maxlength="30"
              :disabled="!referralStatus.can_create_club"
              placeholder="例如：浦东世纪公园晨光跑团"
              v-model="createClubForm.name"
            />

            <text class="input-label">所在城市 *</text>
            <input
              class="text-input"
              type="text"
              maxlength="16"
              :disabled="!referralStatus.can_create_club"
              placeholder="例如：上海 / 北京 / 深圳"
              v-model="createClubForm.city"
            />

            <template v-if="currentOrg">
              <text class="input-label">跑团归属</text>
              <view style="display: flex; flex-direction: column; gap: 14rpx; margin-bottom: 24rpx;">
                <view
                  style="padding: 20rpx 24rpx; border-radius: 16rpx; display: flex; flex-direction: column; gap: 4rpx;"
                  :style="!createClubForm.org_id
                    ? 'background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));'
                    : 'background: var(--rgm-card-2, #18181c); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));'"
                  @click="referralStatus.can_create_club && (createClubForm.org_id = '')"
                >
                  <text style="font-size: 25rpx; font-weight: 700;">🌐 独立公开跑团</text>
                </view>
                <view
                  style="padding: 20rpx 24rpx; border-radius: 16rpx; display: flex; flex-direction: column; gap: 4rpx;"
                  :style="createClubForm.org_id === currentOrg.id
                    ? 'background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));'
                    : 'background: var(--rgm-card-2, #18181c); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));'"
                  @click="referralStatus.can_create_club && (createClubForm.org_id = currentOrg.id)"
                >
                  <text style="font-size: 25rpx; font-weight: 700;">🏛️ 【{{ currentOrg.name }}】下属分队</text>
                </view>
              </view>
            </template>

            <text class="input-label">入团规则</text>
            <view style="display: flex; gap: 16rpx; margin-bottom: 24rpx;">
              <view
                style="flex: 1; padding: 20rpx; border-radius: 16rpx; text-align: center; font-size: 24rpx; font-weight: 600;"
                :style="createClubForm.join_mode === 'free'
                  ? 'background: var(--rgm-brand-tint, rgba(252,76,2,0.16)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252,76,2,0.45));'
                  : 'background: var(--rgm-card-2, #18181c); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));'"
                @click="referralStatus.can_create_club && (createClubForm.join_mode = 'free')"
              >
                🟢 自由入团（免码）
              </view>
              <view
                style="flex: 1; padding: 20rpx; border-radius: 16rpx; text-align: center; font-size: 24rpx; font-weight: 600;"
                :style="createClubForm.join_mode === 'invite'
                  ? 'background: var(--rgm-brand-tint, rgba(252,76,2,0.16)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252,76,2,0.45));'
                  : 'background: var(--rgm-card-2, #18181c); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));'"
                @click="referralStatus.can_create_club && (createClubForm.join_mode = 'invite')"
              >
                🔒 凭专属邀请码入团
              </view>
            </view>

            <text class="input-label">自定义专属邀请码 (选填，留空自动生成)</text>
            <input
              class="text-input"
              type="text"
              maxlength="12"
              :disabled="!referralStatus.can_create_club"
              placeholder="3-12位字母或数字，如 PD2026"
              v-model="createClubForm.invite_code"
            />

            <text class="input-label">跑团简介与口号</text>
            <textarea
              class="textarea-input"
              maxlength="200"
              :disabled="!referralStatus.can_create_club"
              placeholder="介绍跑团日常约跑地点、配速分组与团队理念..."
              v-model="createClubForm.description"
            />

            <button
              v-if="referralStatus.can_create_club"
              class="submit-btn"
              :loading="creatingClub"
              @click="handleSubmitCreateClub"
            >
              🚀 立即创建跑团并成为团长
            </button>
            <button
              v-else
              class="submit-btn"
              style="opacity: 0.7; font-size: 25rpx;"
              @click="handleLockedCreateClubTip"
            >
              🔒 邀满 3 位新用户绑表解锁 ({{ referralStatus.invited_count }}/3)
            </button>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── ⚙️ Club Owner Profile & Status Management Modal (团长跑团资料编辑与状态管理) ── -->
    <view v-if="showEditClubInfoModal" class="modal-mask" @click="showEditClubInfoModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">⚙️ 跑团资料与状态管理</text>
            <text class="count-pill">{{ currentClub?.name }}</text>
          </view>
          <text class="close-btn" @click="showEditClubInfoModal = false">✕</text>
        </view>

        <scroll-view scroll-y class="modal-body modal-scroll" style="max-height: 75vh;">
          <text class="input-label">跑团名称 *</text>
          <input
            class="text-input"
            type="text"
            maxlength="30"
            placeholder="请输入跑团名称"
            v-model="editClubInfoForm.name"
          />

          <text class="input-label">所在城市 *</text>
          <input
            class="text-input"
            type="text"
            maxlength="16"
            placeholder="例如：上海"
            v-model="editClubInfoForm.city"
          />

          <template v-if="currentOrg">
            <text class="input-label">跑团归属</text>
            <view style="display: flex; flex-direction: column; gap: 14rpx; margin-bottom: 24rpx;">
              <view
                style="padding: 20rpx 24rpx; border-radius: 16rpx; display: flex; flex-direction: column; gap: 4rpx;"
                :style="!editClubInfoForm.org_id
                  ? 'background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));'
                  : 'background: var(--rgm-card-2, #18181c); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));'"
                @click="editClubInfoForm.org_id = ''"
              >
                <text style="font-size: 25rpx; font-weight: 700;">🌐 独立公开跑团</text>
              </view>
              <view
                style="padding: 20rpx 24rpx; border-radius: 16rpx; display: flex; flex-direction: column; gap: 4rpx;"
                :style="editClubInfoForm.org_id === currentOrg.id
                  ? 'background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));'
                  : 'background: var(--rgm-card-2, #18181c); color: var(--rgm-text-2, #a1a1aa); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));'"
                @click="editClubInfoForm.org_id = currentOrg.id"
              >
                <text style="font-size: 25rpx; font-weight: 700;">🏛️ 【{{ currentOrg.name }}】下属分队</text>
              </view>
            </view>
          </template>

          <text class="input-label">跑团简介</text>
          <textarea
            class="textarea-input"
            maxlength="200"
            placeholder="请输入跑团简介..."
            v-model="editClubInfoForm.description"
          />

          <button class="submit-btn" :loading="savingClubInfo" @click="handleSaveClubInfo">
            💾 保存资料
          </button>

          <!-- 跑团运行状态与解散管理 (仅团长可见) -->
          <view
            v-if="currentRole === 'owner' || isOwnerOrDev"
            style="margin-top: 36rpx; padding-top: 28rpx; border-top: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));"
          >
            <text style="font-size: 26rpx; font-weight: 700; color: var(--rgm-text, #ffffff); display: block; margin-bottom: 12rpx;">
              🛡️ 状态管理
            </text>
            <text style="font-size: 22rpx; color: var(--rgm-text-3, #8e8e93); display: block; margin-bottom: 20rpx; line-height: 1.5;">
              暂停后外部跑友不可搜入；解散后成员个人数据完整保留。
            </text>
            <view style="display: flex; gap: 16rpx;">
              <button
                style="flex: 1; min-width: 0; margin: 0; padding: 0 16rpx; height: 76rpx; line-height: 1.25; display: flex; align-items: center; justify-content: center; font-size: 24rpx; font-weight: 600; border-radius: 16rpx; background: var(--rgm-card-2, #1f1f24); color: var(--rgm-text, #ffffff); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.15)); white-space: nowrap;"
                @click="handleToggleClubPauseStatus"
              >
                {{ currentClub?.status === 'paused' ? '🟢 恢复正常运行' : '⏸ 暂停跑团招募' }}
              </button>
              <button
                style="flex: 1; min-width: 0; margin: 0; padding: 0 16rpx; height: 76rpx; line-height: 1.25; display: flex; align-items: center; justify-content: center; font-size: 24rpx; font-weight: 600; border-radius: 16rpx; background: rgba(239,68,68,0.12); color: #ef4444; border: 1rpx solid rgba(239,68,68,0.35); white-space: nowrap;"
                @click="handleDissolveCurrentClub"
              >
                🗑️ 解散本跑团
              </button>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── 🥋 Mentorship Bind & Manage Modal (师徒结对 · 1对1 · 最多带3位队员 · 同大群可跨跑团) ── -->
    <view v-if="showMentorshipModal" class="modal-mask" @click="showMentorshipModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">🥋 师徒结对</text>
            <text class="count-pill">徒弟 {{ mentorshipData.my_mentees?.length || 0 }}/{{ mentorshipData.max_mentees || 3 }}</text>
          </view>
          <text class="close-btn" @click="showMentorshipModal = false">✕</text>
        </view>

        <scroll-view scroll-y class="modal-body modal-scroll" style="max-height: 75vh;">
          <!-- 规则与权限说明条 -->
          <view style="padding: 16rpx 22rpx; border-radius: 16rpx; background: var(--rgm-tint-2, rgba(255, 255, 255, 0.06)); border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12)); margin-bottom: 20rpx;">
            <text style="font-size: 22rpx; color: var(--rgm-text-2, #a1a1aa); line-height: 1.45; display: block;">
              每位队员可拜 1 师、带 3 徒（同大群可跨团），师傅可查看徒弟训练与恢复数据。
            </text>
          </view>

          <!-- 微信一键分享邀请结为师徒 -->
          <!-- #ifdef MP-WEIXIN -->
          <view style="display: flex; gap: 14rpx; margin-bottom: 24rpx;">
            <button
              open-type="share"
              data-share-type="mentor"
              data-mentor-role="mentor"
              style="flex: 1; margin: 0; height: 74rpx; line-height: 74rpx; border-radius: 18rpx; font-size: 23rpx; font-weight: 700; background: var(--rgm-brand-grad, linear-gradient(90deg, #fc4c02, #ff7a00)); color: #ffffff; border: none;"
            >
              📤 微信邀TA做我徒弟 ({{ mentorshipData.remaining_mentee_slots ?? 3 }}席)
            </button>
            <button
              v-if="!mentorshipData.my_mentor"
              open-type="share"
              data-share-type="mentor"
              data-mentor-role="mentee"
              style="flex: 1; margin: 0; height: 74rpx; line-height: 74rpx; border-radius: 18rpx; font-size: 23rpx; font-weight: 700; background: var(--rgm-card-2, #1f1f26); color: var(--rgm-text, #ffffff); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.16));"
            >
              🙇 微信请TA做我师傅
            </button>
          </view>
          <!-- #endif -->

          <!-- 搜索同大群 / 同跑团队友直接结对 -->
          <text class="input-label">🔍 搜索队友结对</text>
          <input
            class="text-input"
            type="text"
            placeholder="输入队友姓名、昵称或所属跑团筛选..."
            v-model="mentorCandidateSearch"
          />

          <view v-if="filteredMentorCandidates.length === 0" class="empty-clubs-text" style="padding: 36rpx 0;">
            暂无匹配队友
          </view>
          <view v-else style="display: flex; flex-direction: column; gap: 14rpx;">
            <view
              v-for="cand in filteredMentorCandidates"
              :key="cand.user_id"
              style="display: flex; align-items: center; justify-content: space-between; padding: 18rpx 20rpx; border-radius: 18rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.08));"
            >
              <view style="display: flex; align-items: center; gap: 14rpx; flex: 1; min-width: 0;">
                <image
                  :src="cand.avatar_url || '/static/logo-square.png'"
                  mode="aspectFill"
                  style="width: 64rpx; height: 64rpx; border-radius: 50%; flex-shrink: 0;"
                />
                <view style="display: flex; flex-direction: column; gap: 4rpx; min-width: 0;">
                  <view style="display: flex; align-items: center; gap: 8rpx; flex-wrap: wrap;">
                    <text style="font-size: 25rpx; font-weight: 700; color: var(--rgm-text, #ffffff);">
                      {{ cand.display_name }}
                    </text>
                    <text style="font-size: 19rpx; color: var(--rgm-text-2, #a1a1aa); background: var(--rgm-tint-2, rgba(255,255,255,0.08)); padding: 2rpx 10rpx; border-radius: 8rpx;">
                      {{ cand.club_name || '同大群队友' }}
                    </text>
                  </view>
                  <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa);">
                    跑力 VDOT {{ cand.vdot || '—' }} · 已带徒弟 {{ cand.mentee_count || 0 }}/3
                  </text>
                </view>
              </view>

              <view style="display: flex; gap: 10rpx; flex-shrink: 0;">
                <button
                  v-if="cand.can_be_mentee && (mentorshipData.remaining_mentee_slots ?? 3) > 0"
                  style="margin: 0; padding: 0 18rpx; height: 58rpx; line-height: 58rpx; font-size: 21rpx; font-weight: 700; border-radius: 14rpx; background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));"
                  :loading="bindingMentorshipUid === cand.user_id"
                  @click="handleBindMentorship(user?.id, cand.user_id, cand.display_name, '收徒')"
                >
                  + 收为徒弟
                </button>
                <button
                  v-if="!mentorshipData.my_mentor && cand.can_be_mentor"
                  style="margin: 0; padding: 0 18rpx; height: 58rpx; line-height: 58rpx; font-size: 21rpx; font-weight: 700; border-radius: 14rpx; background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08)); color: var(--rgm-text, #ffffff); border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.16));"
                  :loading="bindingMentorshipUid === cand.user_id"
                  @click="handleBindMentorship(cand.user_id, user?.id, cand.display_name, '拜师')"
                >
                  🙇 拜TA为师
                </button>
              </view>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── 🥋 Mentee Full Training & Rest Detail Modal (师傅查看徒弟全维训练与休息数据弹窗) ── -->
    <view v-if="showMenteeDetailModal" class="modal-mask" @click="showMenteeDetailModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">🥋 徒弟训练与休息档案</text>
            <text class="count-pill">{{ activeMenteeDetail?.display_name || '徒弟' }}</text>
          </view>
          <text class="close-btn" @click="showMenteeDetailModal = false">✕</text>
        </view>

        <scroll-view scroll-y class="modal-body modal-scroll" style="max-height: 78vh;">
          <view v-if="loadingMenteeDetail" class="empty-clubs-text" style="padding: 60rpx 0;">
            正在加载徒弟全维训练与休息恢复数据...
          </view>
          <view v-else-if="activeMenteeDetail">
            <!-- 顶部名片与解绑 -->
            <view style="display: flex; align-items: center; justify-content: space-between; padding: 20rpx; border-radius: 20rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1)); margin-bottom: 22rpx;">
              <view style="display: flex; align-items: center; gap: 16rpx;">
                <image
                  :src="activeMenteeDetail.avatar_url || '/static/logo-square.png'"
                  mode="aspectFill"
                  style="width: 80rpx; height: 80rpx; border-radius: 50%; border: 2rpx solid var(--rgm-line, rgba(255,255,255,0.2));"
                />
                <view style="display: flex; flex-direction: column; gap: 4rpx;">
                  <view style="display: flex; align-items: center; gap: 10rpx; flex-wrap: wrap;">
                    <text style="font-size: 28rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">{{ activeMenteeDetail.display_name }}</text>
                    <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08)); padding: 2rpx 12rpx; border-radius: 8rpx;">
                      {{ activeMenteeDetail.club_name || '同大群跨团' }}
                    </text>
                  </view>
                  <text style="font-size: 21rpx; color: var(--rgm-text-2, #a1a1aa);">
                    目标赛事：{{ activeMenteeDetail.target_race_name || '日常进阶' }} · 目标 {{ activeMenteeDetail.target_finish_time || '健康完赛' }}
                  </text>
                </view>
              </view>
              <text
                style="font-size: 22rpx; color: var(--rgm-red, #ef4444); padding: 8rpx 14rpx;"
                @click="handleUnbindMentorship(user?.id, activeMenteeDetail.mentee_uid, activeMenteeDetail.display_name)"
              >
                解除师徒
              </text>
            </view>

            <!-- 1. 休息与恢复数据面板 (Rest & Recovery) -->
            <view style="padding: 24rpx; border-radius: 22rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12)); margin-bottom: 22rpx;">
              <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16rpx;">
                <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">😴 休息与生理恢复</text>
                <text style="font-size: 21rpx; font-weight: 700; color: var(--rgm-green, #22c55e);">
                  {{ activeMenteeDetail.rest_and_recovery?.status_label }} (TSB {{ activeMenteeDetail.rest_and_recovery?.tsb ?? 0 }})
                </text>
              </view>

              <view style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 14rpx;">
                <view style="padding: 16rpx; border-radius: 16rpx; background: var(--rgm-tint-2, #14161f);">
                  <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); display: block;">💓 静息心率 (RHR)</text>
                  <text style="font-size: 30rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">
                    {{ activeMenteeDetail.rest_and_recovery?.resting_hr ? activeMenteeDetail.rest_and_recovery.resting_hr + ' bpm' : '未录入' }}
                  </text>
                </view>
                <view style="padding: 16rpx; border-radius: 16rpx; background: var(--rgm-tint-2, #14161f);">
                  <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); display: block;">🧬 心率变异性 (HRV)</text>
                  <text style="font-size: 30rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">
                    {{ activeMenteeDetail.rest_and_recovery?.hrv ? activeMenteeDetail.rest_and_recovery.hrv + ' ms' : '未同步' }}
                  </text>
                </view>
                <view style="padding: 16rpx; border-radius: 16rpx; background: var(--rgm-tint-2, #14161f);">
                  <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); display: block;">😴 睡眠质量与时长</text>
                  <text style="font-size: 30rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">
                    {{ activeMenteeDetail.rest_and_recovery?.sleep_score ? activeMenteeDetail.rest_and_recovery.sleep_score + ' 分' : '—' }}
                    <text v-if="activeMenteeDetail.rest_and_recovery?.sleep_hours" style="font-size: 22rpx; color: var(--rgm-text-2, #9ca3af);"> ({{ activeMenteeDetail.rest_and_recovery.sleep_hours }}h)</text>
                  </text>
                </view>
                <view style="padding: 16rpx; border-radius: 16rpx; background: var(--rgm-tint-2, #14161f);">
                  <text style="font-size: 20rpx; color: var(--rgm-text-2, #a1a1aa); display: block;">🔋 机体恢复度 / 负荷</text>
                  <text style="font-size: 30rpx; font-weight: 800; color: var(--rgm-green, #22c55e);">
                    {{ activeMenteeDetail.rest_and_recovery?.recovery_pct ? activeMenteeDetail.rest_and_recovery.recovery_pct + '%' : '—' }}
                    <text style="font-size: 20rpx; color: var(--rgm-text-2, #9ca3af);"> CTL {{ activeMenteeDetail.rest_and_recovery?.ctl ?? 0 }} / ATL {{ activeMenteeDetail.rest_and_recovery?.atl ?? 0 }}</text>
                  </text>
                </view>
              </view>

              <view v-if="activeMenteeDetail.rest_and_recovery?.injury_notes" style="margin-top: 14rpx; padding: 14rpx 18rpx; border-radius: 14rpx; background: rgba(239,68,68,0.12); border: 1rpx solid rgba(239,68,68,0.3);">
                <text style="font-size: 22rpx; color: var(--rgm-red, #fca5a5);">🩹 伤病/身体备注：{{ activeMenteeDetail.rest_and_recovery.injury_notes }}</text>
              </view>

              <button
                style="margin-top: 16rpx; height: 68rpx; line-height: 68rpx; font-size: 23rpx; font-weight: 700; border-radius: 16rpx; background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14)); color: var(--rgm-brand-text, #fc4c02); border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));"
                @click="openMenteeScienceAnalysis(activeMenteeDetail)"
              >
                📊 查看 VDOT 与五维分析 ›
              </button>
            </view>

            <!-- 2. 本周训练计划与执行进度 -->
            <view style="padding: 24rpx; border-radius: 22rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1)); margin-bottom: 22rpx;">
              <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14rpx;">
                <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">
                  📋 第 {{ activeMenteeDetail.training?.week_number || 1 }} 周训练计划与执行
                </text>
                <text style="font-size: 22rpx; font-weight: 700; color: var(--rgm-brand-text, #fc4c02);">
                  已完成 {{ activeMenteeDetail.training?.week_actual_km || 0 }} / {{ activeMenteeDetail.training?.week_planned_km || 0 }} km ({{ activeMenteeDetail.training?.week_compliance_pct || 0 }}%)
                </text>
              </view>

              <view v-if="activeMenteeDetail.training?.weekly_workouts?.length" style="display: flex; flex-direction: column; gap: 10rpx;">
                <view
                  v-for="(w, widx) in activeMenteeDetail.training.weekly_workouts"
                  :key="widx"
                  style="display: flex; align-items: center; justify-content: space-between; padding: 14rpx 16rpx; border-radius: 14rpx; background: var(--rgm-bg, #111116);"
                >
                  <view style="display: flex; align-items: center; gap: 12rpx;">
                    <text style="font-size: 22rpx; font-weight: 700; color: var(--rgm-text-2, #9ca3af); width: 64rpx;">{{ w.day || ('D' + (widx + 1)) }}</text>
                    <text style="font-size: 23rpx; font-weight: 700; color: var(--rgm-text, #ffffff);">{{ w.type || w.title || '常规训练' }}</text>
                    <text v-if="w.target_km" style="font-size: 22rpx; color: var(--rgm-brand-text, #fc4c02); font-weight: 700;">{{ w.target_km }}km</text>
                    <text v-if="w.target_pace" style="font-size: 20rpx; color: var(--rgm-text-2, #9ca3af);">@{{ w.target_pace }}</text>
                  </view>
                  <text style="font-size: 21rpx; font-weight: 700;" :style="{ color: w.completed ? 'var(--rgm-green, #22c55e)' : 'var(--rgm-text-3, #71717a)' }">
                    {{ w.completed ? `✅ 实跑 ${w.actual_km || w.target_km || ''}km` : '待执行' }}
                  </text>
                </view>
              </view>
            </view>

            <!-- 3. 近期跑步打卡与心率/轨迹数据（师傅拥有保密豁免权） -->
            <view style="padding: 24rpx; border-radius: 22rpx; background: var(--rgm-card-2, #18181f); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1));">
              <view style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14rpx;">
                <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-text, #ffffff);">🏃 近期打卡记录</text>
              </view>
              <view v-if="!activeMenteeDetail.recent_activities || activeMenteeDetail.recent_activities.length === 0" style="font-size: 23rpx; color: var(--rgm-text-3, #71717a); text-align: center; padding: 24rpx 0;">
                近期暂无跑步打卡记录
              </view>
              <view v-else style="display: flex; flex-direction: column; gap: 12rpx;">
                <view
                  v-for="act in activeMenteeDetail.recent_activities"
                  :key="act.id"
                  style="padding: 16rpx 18rpx; border-radius: 16rpx; background: var(--rgm-bg, #111116); display: flex; align-items: center; justify-content: space-between;"
                >
                  <view style="display: flex; flex-direction: column; gap: 4rpx;">
                    <text style="font-size: 24rpx; font-weight: 700; color: var(--rgm-text, #ffffff);">{{ act.name || '跑步训练' }}</text>
                    <text style="font-size: 20rpx; color: var(--rgm-text-2, #9ca3af);">{{ (act.start_date_local || '').substring(0, 16) }} · 配速 {{ act.avg_pace || '—' }}</text>
                  </view>
                  <view style="display: flex; flex-direction: column; align-items: flex-end; gap: 4rpx;">
                    <text style="font-size: 26rpx; font-weight: 800; color: var(--rgm-brand-text, #fc4c02);">{{ act.distance_km }} km</text>
                    <text style="font-size: 20rpx; color: var(--rgm-red, #f87171);">❤️ 均心 {{ act.average_heartrate ? Math.round(act.average_heartrate) + ' bpm' : '—' }}</text>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- 地图选点与大头针精确定位弹窗 -->
    <MapPinPickerModal
      :visible="showMapPinPickerModal"
      :initialKeyword="eventLocation"
      :initialAddress="eventLocationDetail"
      :initialLat="eventLatitude"
      :initialLng="eventLongitude"
      @close="showMapPinPickerModal = false"
      @confirm="onMapPinConfirm"
    />

    <!-- 个人跑步周报与月报海报/文案弹窗 -->
    <PersonalReportModal
      :visible="showPersonalReportModal"
      @close="showPersonalReportModal = false"
    />

    <!-- 微信隐私保护指引授权弹窗 -->
    <PrivacyPopup />
  </view>
</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import { explainTerm } from "../../utils/glossary";
import PrivacyPopup from "../../components/PrivacyPopup.vue";
import MapPinPickerModal from "../../components/MapPinPickerModal.vue";
import PersonalReportModal from "../../components/PersonalReportModal.vue";
import PageSkeleton from "../../components/PageSkeleton.vue";
import { trackClick, trackModal, trackSubView, trackFunnelStep } from "../../utils/telemetry";
import { isGroupRunPostStage, buildGroupRunSharePayload } from "../../utils/groupRun";
import { ref, computed, watch } from "vue";
import { onShow, onPullDownRefresh, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import {
  initShareMenu,
  getUnifiedShareAppMessage,
  getUnifiedShareTimeline,
  getClubShareAppMessage,
  getOrgShareAppMessage,
  getClubShareTimeline,
  getOrgShareTimeline,
  getInviteNewRunnerShareMessage,
} from "../../utils/share";
import {
  request,
  uploadAvatarFile,
  getStoredUser,
  checkAndAutoLogin,
  wechatLogin,
  setPendingInviterUid,
  UserProfile,
  getActiveClubId,
  setActiveClubId,
  resolveActiveClub,
  syncTabBarIndex,
  setTabBarHidden,
} from "../../utils/api";
import {
  DEFAULT_GROUP_RUN_TEMPLATES,
  GroupRunTemplateItem,
  GroupRunVenuePreset,
  resolveNextWeekdayIso,
  searchGroupRunGeocode,
} from "../../utils/groupRun";

const user = ref<UserProfile | null>(null);
const currentClub = ref<any>(null);
const currentRole = ref("member");

const events = ref<any[]>([]);
const members = ref<any[]>([]);
const coachCockpit = ref<any>(null);

const showMembersModal = ref(false);
const showPersonalReportModal = ref(false);
const memberSearchQuery = ref("");

const showEventModal = ref(false);
const showJoinModal = ref(false);
const showAllClubsModal = ref(false);
const showCreateClubModal = ref(false);
const showEditClubInfoModal = ref(false);

// ── 📨 WeChat Invite Direct Join State ──
const showClubInviteModal = ref(false);
const invitedClubInfo = ref<any>(null);
const invitedClubCode = ref("");
const acceptingClubInvite = ref(false);
const isInviteFromWechat = ref(false);
const invitedOrgName = ref("");
const pendingSubClubToJoin = ref<{ club_id: string; invite_code: string; club_name?: string } | null>(null);
// 一键入团：邀请人 uid（来自邀请卡片 / 小程序码），用于后端免邀请码、免审批校验
const invitedByUid = ref("");
const invitedClubOneClick = ref(false);
const invitedClubIsOrgMember = ref(false);
const invitedClubDeadlineDays = ref(14);
const orgInviteOneClick = ref(false);
const quickJoiningOrg = ref(false);

function formatDeadlineDate(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(String(iso));
  if (isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

/** 入团 / 入群成功后，若大群资料未补齐：提示截止时间，可「立即补填」或「稍后再填」 */
function promptOrgProfileLater(orgMembership: any, clubName?: string) {
  if (!orgMembership || !["temporary", "pending"].includes(orgMembership.status)) return false;
  const orgName = orgMembership.org_name || "大群";
  const days = orgMembership.days_remaining ?? 14;
  const dl = formatDeadlineDate(orgMembership.deadline_at);
  if (orgMembership.status === "pending") {
    uni.showToast({ title: clubName ? `已加入【${clubName}】` : `已加入【${orgName}】`, icon: "success" });
    return true;
  }
  const missing = (orgMembership.missing_fields || []).map((m: any) => m.label || m.field).slice(0, 5).join("、");
  uni.showModal({
    title: clubName ? `🎉 已加入【${clubName}】` : `🎉 已加入【${orgName}】`,
    content:
      `您已同时成为【${orgName}】临时成员，可直接参加跑团训练与活动。\n\n` +
      `请在 ${days} 天内${dl ? `（${dl}前）` : ""}补齐大群个人资料${missing ? `（${missing}等）` : ""}并通过审核，逾期将被自动移出【${orgName}】下全部跑团。`,
    confirmText: "立即补填",
    cancelText: "稍后再填",
    success: async (r) => {
      if (r.confirm) {
        await loadClubData();
        if (currentOrg.value) openOrgEditProfileModal();
      }
    },
  });
  return true;
}

// ── 👤 新用户入团一键同步微信昵称与头像（避免“跑者_xxxx”代号） ──
const joinRunnerNickname = ref("");
const joinRunnerAvatar = ref("");

function isGenericRunnerName(raw?: string): boolean {
  const n = (raw || "").trim();
  if (!n) return true;
  return (
    n === "微信跑者" ||
    n === "微信用户" ||
    n === "跑者" ||
    n.startsWith("跑者_") ||
    n.startsWith("微信跑者_") ||
    n.startsWith("微信用户_")
  );
}

const needsWechatNickname = computed(() => isGenericRunnerName(user.value?.display_name));

function onJoinNicknameBlur(e: any) {
  const val = e?.detail?.value;
  if (val && String(val).trim()) {
    joinRunnerNickname.value = String(val).trim();
  }
}

async function onJoinChooseAvatar(e: any) {
  const tempUrl = e?.detail?.avatarUrl;
  if (!tempUrl) return;
  joinRunnerAvatar.value = tempUrl;
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) return;
  try {
    const uploadedUrl = await uploadAvatarFile(uid, tempUrl);
    if (uploadedUrl) {
      joinRunnerAvatar.value = uploadedUrl;
      if (user.value) {
        user.value.avatar_url = uploadedUrl;
        uni.setStorageSync("rgm_user", JSON.stringify(user.value));
      }
    }
  } catch (err) {
    console.warn("onJoinChooseAvatar upload fail:", err);
  }
}

function syncUserNicknameAfterJoin(res?: any) {
  const newName = (res?.display_name || joinRunnerNickname.value || "").trim();
  const newAvatar = (res?.avatar_url || joinRunnerAvatar.value || "").trim();
  if (user.value) {
    if (newName) user.value.display_name = newName;
    if (newAvatar) user.value.avatar_url = newAvatar;
    uni.setStorageSync("rgm_user", JSON.stringify(user.value));
  }
}

// ── 🏃 Group Run & Event State ──
const PRESET_COVERS = [
  {
    id: "sunrise",
    title: "🌅 晨曦破晓",
    url: "https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=800&auto=format&fit=crop&q=80"
  },
  {
    id: "night",
    title: "🌃 滨江夜跑",
    url: "https://images.unsplash.com/photo-1513593771513-7b58b6c4af38?w=800&auto=format&fit=crop&q=80"
  },
  {
    id: "park",
    title: "🌳 绿道森林",
    url: "https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?w=800&auto=format&fit=crop&q=80"
  },
  {
    id: "track",
    title: "🏟️ 专业跑道",
    url: "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800&auto=format&fit=crop&q=80"
  },
  {
    id: "trail",
    title: "⛰️ 山野越野",
    url: "https://images.unsplash.com/photo-1486218119243-13883505764c?w=800&auto=format&fit=crop&q=80"
  },
  {
    id: "group",
    title: "🏃‍♂️ 跑团大合练",
    url: "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=800&auto=format&fit=crop&q=80"
  }
];

const showGroupRunModal = ref(false);
const showMapPinPickerModal = ref(false);
const selectedModalTplId = ref("");
const customModalTemplates = ref<GroupRunTemplateItem[]>([]);
const allModalGroupRunTemplates = computed<GroupRunTemplateItem[]>(() => {
  return [...customModalTemplates.value, ...DEFAULT_GROUP_RUN_TEMPLATES];
});
const editingEventId = ref<string | null>(null);
const eventType = ref<"group_run" | "distance_challenge">("group_run");
const eventTitle = ref("");
const eventMeetDate = ref("");
const eventMeetTime = ref("06:30");
const eventLocation = ref("");
const eventLocationDetail = ref("");
const eventLatitude = ref<number | null>(null);
const eventLongitude = ref<number | null>(null);
const lastGeocodedLocationName = ref("");

const eventModalMapMarkers = computed(() => {
  if (!eventLatitude.value || !eventLongitude.value) return [];
  return [
    {
      id: 1,
      latitude: Number(eventLatitude.value),
      longitude: Number(eventLongitude.value),
      title: eventLocation.value || "约跑集合点",
      width: 28,
      height: 36,
      callout: {
        content: `📍 ${eventLocation.value || "约跑集合点"}`,
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
const eventTargetKm = ref<number | string>(10);
const eventPace = ref("5:30 - 6:00 /km");
const eventMaxParticipants = ref<number | string>(0);
const eventCoverImage = ref(PRESET_COVERS[0].url);
const eventRules = ref("");
const eventRepeatType = ref<"none" | "weekly">("none");
const eventRepeatWeeks = ref<number>(4);
const eventVisibilityMode = ref<"registered_only" | "club_members" | "public">("registered_only");
const isRulesFocused = ref(false);
const formScrollTop = ref(0);

interface WeekCalendarDay {
  fullDate: string;
  dayNum: number;
  monthText: string;
  weekDay: string;
  isToday: boolean;
  isTomorrow: boolean;
  isWeekend: boolean;
}

const upcomingWeekDays = computed<WeekCalendarDay[]>(() => {
  const days: WeekCalendarDay[] = [];
  const weekdaysMap = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const now = new Date();
  for (let i = 0; i < 14; i++) {
    const cur = new Date();
    cur.setDate(now.getDate() + i);
    const y = cur.getFullYear();
    const m = cur.getMonth() + 1;
    const d = cur.getDate();
    const w = cur.getDay();
    const fullDate = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    days.push({
      fullDate,
      dayNum: d,
      monthText: `${m}月`,
      weekDay: weekdaysMap[w],
      isToday: i === 0,
      isTomorrow: i === 1,
      isWeekend: w === 0 || w === 6
    });
  }
  return days;
});

function selectWeekDate(dateStr: string) {
  eventMeetDate.value = dateStr;
}

function getWeekdayName(dateStr: string): string {
  if (!dateStr) return "该日";
  try {
    const d = new Date(dateStr.replace(/-/g, "/"));
    if (isNaN(d.getTime())) return "该日";
    const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    return weekdays[d.getDay()];
  } catch {
    return "该日";
  }
}

function formatSelectedMeetPreview(dateStr: string, timeStr: string): string {
  if (!dateStr) return "请在上方周历选择集合日期";
  try {
    const d = new Date(dateStr.replace(/-/g, "/"));
    const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    const w = weekdays[d.getDay()];
    const m = d.getMonth() + 1;
    const day = d.getDate();
    return `${m}月${day}日 (${w}) ${timeStr || '07:00'} 集合`;
  } catch {
    return `${dateStr} ${timeStr || ''}`;
  }
}

function formatRepeatSchedulePreview(dateStr: string, weeks: number): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr.replace(/-/g, "/"));
    if (isNaN(d.getTime())) return "";
    const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    const parts: string[] = [];
    for (let i = 0; i < weeks; i++) {
      const cur = new Date(d);
      cur.setDate(d.getDate() + 7 * i);
      const m = cur.getMonth() + 1;
      const day = cur.getDate();
      const w = weekdays[cur.getDay()];
      parts.push(`${m}/${day}(${w})`);
    }
    return parts.join("、");
  } catch {
    return "";
  }
}

function onRulesFocus() {
  isRulesFocused.value = true;
  setTimeout(() => {
    formScrollTop.value = 99999;
  }, 150);
}

function onRulesBlur() {
  isRulesFocused.value = false;
}

const savingEvent = ref(false);
const joiningEventId = ref<string | null>(null);

const showParticipantsModal = ref(false);
const selectedEventForParticipants = ref<any>(null);

const nextUpcomingRun = computed(() => {
  if (!events.value || events.value.length === 0) return null;
  // 只取已报名且未结束的约跑（开跑后 4 小时内仍算进行中），避免一直显示已结束的活动
  const cutoff = Date.now() - 4 * 3600 * 1000;
  const joinedRuns = events.value.filter(e => {
    if (!e.is_joined || !(e.event_type === 'group_run' || e.meet_time)) return false;
    const ts = new Date(sanitizeMeetTimeStr(e.meet_time || e.start_date || "").replace(/-/g, "/")).getTime();
    return isNaN(ts) || ts >= cutoff;
  });
  if (joinedRuns.length === 0) return null;
  const sorted = [...joinedRuns].sort((a, b) => {
    const tA = (a.meet_time || a.start_date || "").replace(/-/g, "/");
    const tB = (b.meet_time || b.start_date || "").replace(/-/g, "/");
    return new Date(tA).getTime() - new Date(tB).getTime();
  });
  return sorted[0];
});

const inviteCodeInput = ref("");
const joiningClub = ref(false);
const joiningClubId = ref<string | null>(null);

// ── Grand Community / Organization State ──
const userOrgs = ref<any[]>([]);
const currentOrg = ref<any>(null);
const orgSubClubs = ref<any[]>([]);
const orgMembers = ref<any[]>([]);
const allPlatformOrgs = ref<any[]>([]);
const targetDefaultOrg = computed(() => allPlatformOrgs.value[0] || null);
const showManualOrgCode = ref(false);

const showOrgJoinModal = ref(false);
const showOrgMembersModal = ref(false);
const showSubClubsModal = ref(false);
const orgMemberSearch = ref("");
const joiningOrg = ref(false);

// ── Org Join Mode & Field Rules State (大群组织者管理) ──
const showOrgJoinModeModal = ref(false);
const selectedOrgJoinMode = ref<"free" | "invite">("invite");
const savingOrgJoinMode = ref(false);
const editOrgInviteCode = ref("");
const editOrgNameInput = ref("");
const editOrgDescInput = ref("");

const showOrgFieldRulesModal = ref(false);
const orgFieldRulesList = ref<any[]>([]);
const savingOrgFieldRules = ref(false);

// ── 📊 Org Periodic Report & Sub-Club PK + 🚩 Cross-Club Joint Events State ──
const showOrgReportModal = ref(false);
const loadingOrgReport = ref(false);
const orgReportPeriodType = ref<"week" | "month">("week");
const orgReportPeriodOffset = ref(0);
const orgReportTab = ref<"clubs_pk" | "members" | "unaffiliated">("clubs_pk");
const orgReportData = ref<any>(null);

const showOrgEventsModal = ref(false);
const loadingOrgEvents = ref(false);
const creatingOrgEvent = ref(false);
const orgEventsList = ref<any[]>([]);
const orgEvtType = ref<"group_run" | "distance_challenge">("group_run");
const orgEvtTitle = ref("周末大群跨跑团联合LSD合练");
const orgEvtMeetTime = ref("2026-11-15 06:30");
const orgEvtTargetKm = ref<number | string>(18);
const orgEvtLocation = ref("世纪公园7号门集合");

// ── Club Join Mode & Specific Code Prompt State ──
const showJoinModeModal = ref(false);
const selectedJoinMode = ref<"free" | "invite">("free");
const savingJoinMode = ref(false);
const editInviteCode = ref("");

const showClubCodeModal = ref(false);
const targetClubForCodeJoin = ref<any>(null);
const clubJoinCodeInput = ref("");

// ── Club Periodic Report State ──
const showReportModal = ref(false);
const reportPeriodType = ref<"week" | "month">("week");
const reportPeriodOffset = ref(0);
const reportTrailMode = ref<"include" | "exclude_pace" | "exclude_all">("include");
const reportViewMode = ref<"poster" | "table" | "text">("poster");
const loadingReport = ref(false);
const reportData = ref<any>(null);
const reportSortBy = ref<"completion" | "distance">("completion");
const reportFilter = ref<"all" | "achieved" | "pending">("all");
const reportSearch = ref("");

const filteredSortedMemberList = computed(() => {
  const list = reportData.value?.member_progress_list || [];
  let res = [...list];

  if (reportSearch.value.trim()) {
    const q = reportSearch.value.trim().toLowerCase();
    res = res.filter(
      (m: any) => m.display_name && m.display_name.toLowerCase().includes(q)
    );
  }

  if (reportFilter.value === "achieved") {
    res = res.filter((m: any) => m.is_achieved);
  } else if (reportFilter.value === "pending") {
    res = res.filter((m: any) => !m.is_achieved);
  }

  if (reportSortBy.value === "completion") {
    res.sort(
      (a: any, b: any) =>
        (b.completion_rate || 0) - (a.completion_rate || 0) ||
        (b.distance_km || 0) - (a.distance_km || 0)
    );
  } else {
    res.sort(
      (a: any, b: any) =>
        (b.distance_km || 0) - (a.distance_km || 0) ||
        (b.completion_rate || 0) - (a.completion_rate || 0)
    );
  }

  return res;
});

const tablePosterCanvasHeight = computed(() => {
  const list =
    filteredSortedMemberList.value && filteredSortedMemberList.value.length > 0
      ? filteredSortedMemberList.value
      : reportData.value?.member_progress_list || [];
  const rows = Math.max(list.length, 1);
  return Math.max(415 + rows * 74 + 185, 860);
});

function toggleReportSort() {
  reportSortBy.value = reportSortBy.value === "completion" ? "distance" : "completion";
}

function handleCopyMemberProgressTable() {
  if (!reportData.value) return;
  const rep = reportData.value;
  const list = rep.member_progress_list || [];
  if (list.length === 0) {
    uni.showToast({ title: "暂无成员目标数据", icon: "none" });
    return;
  }

  const lines = [
    `🏃‍♂️ 【${rep.club_name}】${rep.period_label} 全员跑量目标与达成明细`,
    `━━━━━━━━━━━━━━━━━━`,
    `📅 统计周期：${rep.date_range_str}`,
    `📊 全团总跑量：${rep.total_distance_km} km`,
    `🎯 团队总目标：${rep.total_target_km} km (完成度 ${rep.team_completion_rate}%)`,
    `🏅 达标人数：${rep.achieved_members_count}/${rep.total_members_count} 人`,
    `━━━━━━━━━━━━━━━━━━`,
    `📋 【全员明细清单】`
  ];

  const isPast = reportPeriodOffset.value === -1 || rep.is_past_period;
  list.forEach((m: any, idx: number) => {
    const tag = m.is_achieved ? "✅ 已达标" : (isPast ? "未达标" : `进行中 (差 ${m.remaining_km}km)`);
    lines.push(
      `${idx + 1}. ${m.display_name}：实际 ${m.distance_km} km / 目标 ${m.target_km} km (完成度 ${m.completion_rate}% · ${tag})`
    );
  });

  lines.push(`━━━━━━━━━━━━━━━━━━`);
  lines.push(`数据由【万跑跑团助手】实时自动汇算生成。`);

  const text = lines.join("\n");
  uni.setClipboardData({
    data: text,
    success: () => {
      uni.showToast({ title: "全员目标明细已复制！", icon: "success", duration: 2500 });
    }
  });
}

// ── 🛡️ 防误触：团长移出队员 & 队员退出跑团 二次确认状态（提前声明，供 isAnyModalOpen 监听使用） ──
const showRemoveMemberConfirmModal = ref(false);
const targetMemberToRemove = ref<any | null>(null);
const removeMemberChecked = ref(false);
const removeMemberCountdown = ref(0);
const removingMemberLoading = ref(false);
let removeMemberTimer: any = null;

const showLeaveClubConfirmModal = ref(false);
const leaveClubChecked = ref(false);
const leaveClubCountdown = ref(0);
const leavingClubLoading = ref(false);
let leaveClubTimer: any = null;

const isAnyModalOpen = computed(() => {
  return (
    showClubInviteModal.value ||
    showOrgJoinModal.value ||
    showOrgJoinModeModal.value ||
    showOrgFieldRulesModal.value ||
    showOrgReportModal.value ||
    showOrgEventsModal.value ||
    showAllClubsModal.value ||
    showSubClubsModal.value ||
    showOrgMembersModal.value ||
    showMembersModal.value ||
    showEventModal.value ||
    showGroupRunModal.value ||
    showParticipantsModal.value ||
    showJoinModal.value ||
    showJoinModeModal.value ||
    showClubCodeModal.value ||
    showReportModal.value ||
    showPersonalReportModal.value ||
    showCreateClubModal.value ||
    showEditClubInfoModal.value ||
    showMentorshipModal.value ||
    showMenteeDetailModal.value ||
    showRemoveMemberConfirmModal.value ||
    showLeaveClubConfirmModal.value
  );
});

// ── 💻 Copy Web Workbench URL ──
function copyWebAdminUrl() {
  const url = "https://rgm.vanpower.net/dashboard/team";
  uni.setClipboardData({
    data: url,
    success: () => {
      uni.showModal({
        title: "💻 网页端工作台地址已复制",
        content: `已复制 ${url}\n\n请在电脑浏览器中打开并登录，即可使用跑团创建/编辑、成员与教练任免、大群花名册管理、排课模版库等完整高级管理功能。`,
        showCancel: false,
        confirmText: "知道了",
      });
    },
  });
}

// ── 🥋 师徒传帮带 (Mentorship · 1对1 · 最多带3位队员 · 同大群可跨跑团) ──
const showMentorshipModal = ref(false);
const showMenteeDetailModal = ref(false);
const loadingMenteeDetail = ref(false);
const activeMenteeDetail = ref<any>(null);
const mentorCandidateSearch = ref("");
const bindingMentorshipUid = ref("");
const mentorshipData = ref<any>({
  max_mentees: 3,
  my_mentor: null,
  my_mentees: [],
  remaining_mentee_slots: 3,
  eligible_candidates: [],
});

const filteredMentorCandidates = computed(() => {
  const list = mentorshipData.value?.eligible_candidates || mentorshipData.value?.candidates || [];
  const q = mentorCandidateSearch.value.trim().toLowerCase();
  if (!q) return list;
  return list.filter(
    (c: any) =>
      (c.display_name || "").toLowerCase().includes(q) ||
      (c.real_name || "").toLowerCase().includes(q) ||
      (c.club_name || "").toLowerCase().includes(q) ||
      (Array.isArray(c.clubs_names) ? c.clubs_names.join(" ").toLowerCase().includes(q) : false) ||
      (c.user_id || "").toLowerCase().includes(q)
  );
});

async function fetchMentorshipOverview() {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) return;
  try {
    const res = await request(`/api/team/mentorship/overview?user_id=${encodeURIComponent(uid)}`);
    if (res) {
      mentorshipData.value = {
        max_mentees: res.max_mentees ?? 3,
        my_mentor: res.my_mentor || null,
        my_mentees: res.my_mentees || [],
        remaining_mentee_slots: res.remaining_mentee_slots ?? res.remaining_slots ?? 3,
        eligible_candidates: res.eligible_candidates || res.candidates || [],
      };
    }
  } catch (e) {
    console.warn("fetchMentorshipOverview error:", e);
  }
}

async function openMentorshipModal() {
  mentorCandidateSearch.value = "";
  showMentorshipModal.value = true;
  trackModal("mentorship", "打开师徒结对中心弹窗", "open");
  await fetchMentorshipOverview();
}

async function openMenteeDetailModal(menteeUid: string) {
  if (!menteeUid) return;
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) return;
  showMenteeDetailModal.value = true;
  loadingMenteeDetail.value = true;
  try {
    const res = await request(
      `/api/team/mentorship/mentee/${encodeURIComponent(menteeUid)}/detail?user_id=${encodeURIComponent(uid)}`
    );
    activeMenteeDetail.value = res || null;
  } catch (e: any) {
    uni.showToast({ title: e?.message || "读取徒弟档案失败", icon: "none" });
    showMenteeDetailModal.value = false;
  } finally {
    loadingMenteeDetail.value = false;
  }
}

async function handleBindMentorship(
  mentorUid?: string,
  menteeUid?: string,
  targetName?: string,
  actionLabel: string = "结对"
) {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid || !mentorUid || !menteeUid) return;
  bindingMentorshipUid.value = mentorUid === uid ? menteeUid : mentorUid;
  try {
    const res = await request("/api/team/mentorship/bind", "POST", {
      mentor_uid: mentorUid,
      mentee_uid: menteeUid,
      operator_uid: uid,
    });
    trackFunnelStep("mentorship_bind_success", `师徒${actionLabel}成功`, {
      mentor_uid: mentorUid,
      mentee_uid: menteeUid,
    });
    uni.showToast({ title: res?.message || `${actionLabel}成功！`, icon: "success" });
    await fetchMentorshipOverview();
  } catch (e: any) {
    uni.showModal({
      title: "师徒结对提示",
      content: e?.message || e?.data?.detail || "结对失败，请确认双方在同一大群或同一跑团，且未超出名额上限",
      showCancel: false,
    });
  } finally {
    bindingMentorshipUid.value = "";
  }
}

function handleUnbindMentorship(mentorUid?: string, menteeUid?: string, targetName?: string) {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid || !mentorUid || !menteeUid) return;
  uni.showModal({
    title: "解除师徒关系",
    content: `确定要解除与【${targetName || "对方"}】的师徒结对关系吗？解除后师傅将不再查看徒弟的保密运动与休息数据。`,
    confirmColor: "#ef4444",
    success: async (mRes) => {
      if (mRes.confirm) {
        try {
          const res = await request("/api/team/mentorship/unbind", "POST", {
            mentor_uid: mentorUid,
            mentee_uid: menteeUid,
            operator_uid: uid,
          });
          trackClick("mentorship_unbind", "解除师徒结对关系", {
            mentor_uid: mentorUid,
            mentee_uid: menteeUid,
          });
          showMenteeDetailModal.value = false;
          uni.showToast({ title: res?.message || "已解除师徒关系", icon: "success" });
          await fetchMentorshipOverview();
        } catch (e: any) {
          uni.showToast({ title: e?.message || "解除失败", icon: "none" });
        }
      }
    },
  });
}

// ── ✨ Self-Service Club Creation & 3-Referral (Watch-Bound) State ──
const creatingClub = ref(false);
const referralStatus = ref<any>({
  invited_count: 0,
  registered_count: 0,
  pending_watch_count: 0,
  required_count: 3,
  remaining_count: 3,
  can_create_club: false,
  invited_users: [],
  owned_clubs: [],
});
const createClubForm = ref({
  name: "",
  city: "上海",
  join_mode: "free" as "free" | "invite",
  invite_code: "",
  description: "",
  org_id: "",
});

async function fetchCreationEligibility() {
  let u = user.value || getStoredUser();
  if (!u) {
    u = await wechatLogin();
    user.value = u;
  }
  const uid = u?.id;
  if (!uid) return;
  try {
    const res = await request(`/api/team/creation-eligibility/${encodeURIComponent(uid)}`);
    if (res) {
      referralStatus.value = {
        invited_count: res.invited_count ?? 0,
        registered_count: res.registered_count ?? 0,
        pending_watch_count: res.pending_watch_count ?? 0,
        required_count: res.required_count ?? 3,
        remaining_count: res.remaining_count ?? 3,
        can_create_club: Boolean(res.can_create_club),
        invited_users: res.invited_users || [],
        owned_clubs: res.owned_clubs || [],
      };
    }
  } catch (e) {
    console.warn("fetchCreationEligibility failed:", e);
  }
}

async function openCreateClubModal() {
  createClubForm.value.org_id = currentClub.value?.org_id || currentOrg.value?.id || "";
  showCreateClubModal.value = true;
  trackModal("create_club", "打开自建跑团弹窗", "open");
  await fetchCreationEligibility();
}

function handleLockedCreateClubTip() {
  const rem = referralStatus.value.remaining_count ?? 3;
  const pending = referralStatus.value.pending_watch_count ?? 0;
  uni.showModal({
    title: "解锁自建跑团权益",
    content: `累计邀请满 3 位新用户注册并成功绑定运动手表即可免费创建专属跑团并担任团长（当前已达标 ${referralStatus.value.invited_count || 0}/3 位，还差 ${rem} 位${pending > 0 ? `；另有 ${pending} 位受邀好友尚未绑定手表` : ''}）。请点击上方橙色按钮转发给微信好友或跑友群！`,
    showCancel: false,
    confirmText: "知道了",
  });
}

async function handleSubmitCreateClub() {
  if (!referralStatus.value.can_create_club) {
    handleLockedCreateClubTip();
    return;
  }
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  const name = createClubForm.value.name.trim();
  if (!name) {
    uni.showToast({ title: "请输入跑团名称", icon: "none" });
    return;
  }
  const city = createClubForm.value.city.trim() || "上海";
  const code = createClubForm.value.invite_code.trim().toUpperCase();
  if (code && (code.length < 3 || code.length > 12)) {
    uni.showToast({ title: "自定义邀请码长度需为 3-12 位", icon: "none" });
    return;
  }

  creatingClub.value = true;
  try {
    const res = await request("/api/team/clubs", "POST", {
      owner_id: uid,
      name,
      city,
      join_mode: createClubForm.value.join_mode,
      invite_code: code || undefined,
      description: createClubForm.value.description.trim() || undefined,
      org_id: createClubForm.value.org_id || undefined,
    });
    const newClub = res?.club;
    trackFunnelStep("club_create_success", `成功自建跑团：${newClub?.name || name}`, {
      club_id: newClub?.id,
      city,
    });
    showCreateClubModal.value = false;
    createClubForm.value = {
      name: "",
      city: "上海",
      join_mode: "free",
      invite_code: "",
      description: "",
      org_id: "",
    };
    if (newClub?.id) {
      setActiveClubId(newClub.id);
      await loadClubData(newClub.id);
    } else {
      await loadClubData();
    }
    uni.showModal({
      title: "🎉 跑团创建成功",
      content: `恭喜您成功创建【${newClub?.name || name}】并成为团长！专属邀请码：${newClub?.invite_code || ""}，快去邀请队友入团吧！`,
      showCancel: false,
    });
  } catch (e: any) {
    uni.showModal({
      title: "创建跑团提示",
      content: e?.message || e?.data?.detail || "创建失败，请稍后重试",
      showCancel: false,
    });
  } finally {
    creatingClub.value = false;
  }
}

// ── ⚙️ Club Owner Edit Info & Status State ──
const savingClubInfo = ref(false);
const editClubInfoForm = ref({
  name: "",
  city: "上海",
  description: "",
  org_id: "",
});

function openEditClubInfoModal() {
  if (!currentClub.value) return;
  editClubInfoForm.value = {
    name: currentClub.value.name || "",
    city: currentClub.value.city || "上海",
    description: currentClub.value.description || "",
    org_id: currentClub.value.org_id || "",
  };
  showEditClubInfoModal.value = true;
}

async function handleSaveClubInfo() {
  const clubId = currentClub.value?.id;
  const uid = user.value?.id;
  if (!clubId || !uid) return;
  const name = editClubInfoForm.value.name.trim();
  if (!name) {
    uni.showToast({ title: "跑团名称不能为空", icon: "none" });
    return;
  }
  savingClubInfo.value = true;
  try {
    const res = await request(`/api/team/${clubId}/info`, "PUT", {
      operator_uid: uid,
      name,
      city: editClubInfoForm.value.city.trim() || "上海",
      description: editClubInfoForm.value.description.trim(),
      org_id: editClubInfoForm.value.org_id || "",
    });
    showEditClubInfoModal.value = false;
    uni.showToast({ title: res?.message || "跑团资料已保存", icon: "success" });
    await loadClubData(clubId);
  } catch (e: any) {
    uni.showToast({ title: e?.message || "保存失败", icon: "none" });
  } finally {
    savingClubInfo.value = false;
  }
}

function handleToggleClubPauseStatus() {
  const club = currentClub.value;
  const uid = user.value?.id;
  if (!club || !uid) return;
  const nextStatus = club.status === "paused" ? "active" : "paused";
  const actionName = nextStatus === "paused" ? "暂停跑团招募" : "恢复正常运行";
  uni.showModal({
    title: `确认${actionName}？`,
    content: nextStatus === "paused"
      ? "暂停后，外部跑者将暂时在跑团广场看不到本跑团，已有团员不受影响。"
      : "恢复后，跑团将在广场正常展示并开放招募。",
    success: async (mRes) => {
      if (mRes.confirm) {
        try {
          const res = await request(`/api/team/${club.id}/status`, "POST", {
            operator_uid: uid,
            status: nextStatus,
          });
          uni.showToast({ title: res?.message || "状态已更新", icon: "success" });
          await loadClubData(club.id);
        } catch (e: any) {
          uni.showToast({ title: e?.message || "操作失败", icon: "none" });
        }
      }
    },
  });
}

function handleDissolveCurrentClub() {
  const club = currentClub.value;
  const uid = user.value?.id;
  if (!club || !uid) return;
  uni.showModal({
    title: `⚠️ 确认解散【${club.name}】？`,
    content: "解散后本跑团将被永久移除，但全体团员的个人运动历史与数据档案将 100% 完整保留。请确认是否继续？",
    confirmText: "确认解散",
    confirmColor: "#ef4444",
    success: async (mRes) => {
      if (mRes.confirm) {
        try {
          const res = await request(
            `/api/team/${encodeURIComponent(club.id)}?operator_uid=${encodeURIComponent(uid)}`,
            "DELETE"
          );
          showEditClubInfoModal.value = false;
          activeSection.value = "";
          setActiveClubId("");
          uni.showToast({ title: res?.message || "跑团已解散", icon: "success" });
          await loadClubData();
        } catch (e: any) {
          uni.showToast({ title: e?.message || "解散失败", icon: "none" });
        }
      }
    },
  });
}

// 微信小程序 scroll-view 必须用真实 px 数值驱动高度，vh/flex 无效
// 88% 屏高 - 顶部手柄(38rpx) - 标题栏(约96rpx) - 底部footer(约148rpx) = 可用滚动区域
const orgScrollHeight = ref(480);
function computeOrgScrollHeight(updatingProfile: boolean = false) {
  try {
    const res = uni.getSystemInfoSync();
    const screenH = res.windowHeight || 700;
    const rpxRatio = (res.windowWidth || 375) / 750;
    const sheetH = screenH * 0.88;
    const handleH = 38 * rpxRatio;
    const headerH = 96 * rpxRatio;
    const footerH = (updatingProfile ? 148 : 236) * rpxRatio;
    orgScrollHeight.value = Math.max(300, Math.floor(sheetH - handleH - headerH - footerH));
  } catch (e) {
    orgScrollHeight.value = 450;
  }
}
computeOrgScrollHeight();

const ORG_PROGRAM_OPTIONS = [
  "中文EMBA",
  "台大班",
  "复旦-BI（挪威）",
  "奥林班",
  "港大班"
];
const GOBI_EDITION_OPTIONS = Array.from({ length: 21 }, (_, i) => `戈${21 - i}`);
const GOBI_GROUP_OPTIONS = ["A组", "B组", "C组"];

const orgJoinForm = ref({
  org_id: "",
  invite_code: "",
  real_name: "",
  gender: "male",
  date_of_birth: "1988-08-08",
  program: "中文EMBA",
  class_detail: "",
  class_name: "",
  gobi_type: "new",
  gobi_edition: "戈20",
  gobi_group: "A组",
  gobi_experience: "新戈",
  phone: "",
  id_card: "",
  emergency_contact: "",
  running_shoe_size: "",
  jersey_size: "",
  full_marathon_pb: "",
  health_declaration: "本人确认身体健康，无不适合高强度跑步的疾病。"
});
const isUpdatingOrgProfile = ref(false);

const selectedGobiEditionIndex = computed(() => {
  const idx = GOBI_EDITION_OPTIONS.indexOf(orgJoinForm.value.gobi_edition);
  return idx >= 0 ? idx : 0;
});

function onGobiEditionChange(e: any) {
  const idx = parseInt(e.detail.value, 10);
  if (!isNaN(idx) && GOBI_EDITION_OPTIONS[idx]) {
    orgJoinForm.value.gobi_edition = GOBI_EDITION_OPTIONS[idx];
  }
}

const showOrgRealName = ref(false);
const showOrgDob = ref(false);
const showOrgIdCard = ref(false);
const showOrgPhone = ref(false);
const orgWizardStep = ref<number>(1);
const showOrgGenderDobAdjust = ref(false);
const orgHealthChecked = computed(() => Boolean((orgJoinForm.value.health_declaration || "").trim()));

function toggleOrgHealthDeclaration() {
  if (orgHealthChecked.value) {
    orgJoinForm.value.health_declaration = "";
  } else {
    orgJoinForm.value.health_declaration = "本人确认身体健康，无不适合高强度跑步的疾病。";
  }
}

const activeOrgFieldRules = computed<any[]>(() => {
  if (isUpdatingOrgProfile.value && currentOrg.value?.field_rules?.length) {
    return currentOrg.value.field_rules;
  }
  const codeVal = (orgJoinForm.value.invite_code || "").trim().toUpperCase();
  if (codeVal) {
    const matched = allPlatformOrgs.value.find(
      (o: any) => (o.invite_code || "").toUpperCase() === codeVal
    );
    if (matched?.field_rules?.length) return matched.field_rules;
  }
  if (orgJoinForm.value.org_id) {
    const matched = allPlatformOrgs.value.find((o: any) => o.id === orgJoinForm.value.org_id);
    if (matched?.field_rules?.length) return matched.field_rules;
  }
  if (targetDefaultOrg.value?.field_rules?.length) {
    return targetDefaultOrg.value.field_rules;
  }
  if (currentOrg.value?.field_rules?.length) {
    return currentOrg.value.field_rules;
  }
  return [];
});

function isOrgFieldVisible(fieldKey: string): boolean {
  const rules = activeOrgFieldRules.value;
  if (!rules || rules.length === 0) return true;
  const r = rules.find((item: any) => item.field_key === fieldKey);
  if (!r) return true;
  return !r.hidden && r.mode !== "hidden";
}

function isOrgFieldRequired(fieldKey: string): boolean {
  const rules = activeOrgFieldRules.value;
  if (!rules || rules.length === 0) {
    return ["real_name", "gender", "date_of_birth", "class_name", "gobi_experience"].includes(fieldKey);
  }
  const r = rules.find((item: any) => item.field_key === fieldKey);
  if (!r) return false;
  if (r.hidden || r.mode === "hidden") return false;
  return Boolean(r.required || r.mode === "required");
}

function goToOrgWizardStep(step: number) {
  if (step < orgWizardStep.value) {
    orgWizardStep.value = step;
    return;
  }
  if (step === 2 && orgWizardStep.value === 1) {
    handleNextOrgWizardStep();
  } else if (step === 3 && orgWizardStep.value <= 2) {
    handleNextOrgWizardStep();
  }
}

function handleNextOrgWizardStep() {
  if (orgWizardStep.value === 1) {
    const codeVal = orgJoinForm.value.invite_code.trim().toUpperCase();
    const defaultOrg = targetDefaultOrg.value;
    const trustedInvite = isInviteFromWechat.value && (orgInviteOneClick.value || Boolean(codeVal));
    if (!isUpdatingOrgProfile.value && !codeVal && !trustedInvite) {
      if (!defaultOrg || defaultOrg.join_mode !== "free") {
        uni.showToast({ title: "请输入大群专属邀请码", icon: "none" });
        return;
      }
    }
    if (isOrgFieldVisible("real_name") && isOrgFieldRequired("real_name") && !orgJoinForm.value.real_name.trim()) {
      uni.showToast({ title: "请填写真实姓名", icon: "none" });
      return;
    }
    if (
      isOrgFieldVisible("class_name") &&
      isOrgFieldRequired("class_name") &&
      !orgJoinForm.value.class_detail.trim() &&
      !orgJoinForm.value.class_name.trim()
    ) {
      uni.showToast({ title: "请填写所在班级/届别", icon: "none" });
      return;
    }
    if (isOrgFieldVisible("date_of_birth") && isOrgFieldRequired("date_of_birth") && !orgJoinForm.value.date_of_birth.trim()) {
      uni.showToast({ title: "请选择出生日期", icon: "none" });
      return;
    }
    const hasStep2Visible =
      isOrgFieldVisible("phone") || isOrgFieldVisible("id_card") || isOrgFieldVisible("emergency_contact");
    orgWizardStep.value = hasStep2Visible ? 2 : 3;
  } else if (orgWizardStep.value === 2) {
    if (isOrgFieldVisible("phone") && isOrgFieldRequired("phone") && !orgJoinForm.value.phone.trim()) {
      uni.showToast({ title: "请填写手机号", icon: "none" });
      return;
    }
    if (isOrgFieldVisible("id_card") && isOrgFieldRequired("id_card") && !orgJoinForm.value.id_card.trim()) {
      uni.showToast({ title: "请填写身份证号/护照号", icon: "none" });
      return;
    }
    if (
      isOrgFieldVisible("emergency_contact") &&
      isOrgFieldRequired("emergency_contact") &&
      !orgJoinForm.value.emergency_contact.trim()
    ) {
      uni.showToast({ title: "请填写紧急联系人及电话", icon: "none" });
      return;
    }
    orgWizardStep.value = 3;
  }
}

function getAgeGroup(dob?: string, fallbackGroup?: string): string {
  if (fallbackGroup) return fallbackGroup;
  if (!dob) return "青年组";
  const year = parseInt(dob.substring(0, 4), 10);
  if (isNaN(year) || year < 1920) return "青年组";
  const currentYear = new Date().getFullYear();
  const age = currentYear - year;
  if (age >= 50) return "大师组";
  if (age >= 40) return "壮年组";
  if (age >= 30) return "中坚组";
  return "青年组";
}

function openOrgJoinModal(presetCode?: string, presetOrgId?: string, presetOrgName?: string, fromInvite: boolean = false) {
  trackModal("org_join", `打开大群体入群弹窗：${presetOrgName || "大群"}`, "open", {
    from_invite: fromInvite,
    has_preset_code: Boolean(presetCode),
  });
  isUpdatingOrgProfile.value = false;
  orgWizardStep.value = 1;
  showOrgGenderDobAdjust.value = false;
  isInviteFromWechat.value = fromInvite || Boolean(presetCode);
  if (!fromInvite) orgInviteOneClick.value = false;
  invitedOrgName.value = presetOrgName || targetDefaultOrg.value?.name || "大群";
  computeOrgScrollHeight();
  const u = user.value || getStoredUser();
  if (u) {
    orgJoinForm.value.real_name =
      u.real_name || (u.display_name && u.display_name !== "跑者" && u.display_name !== "微信用户" ? u.display_name : "");
    orgJoinForm.value.gender = u.gender || "male";
    orgJoinForm.value.date_of_birth = u.date_of_birth || "1988-08-08";
    orgJoinForm.value.phone = u.phone || "";
    orgJoinForm.value.id_card = u.id_card || "";
    orgJoinForm.value.emergency_contact = "";
    orgJoinForm.value.running_shoe_size = "";
    orgJoinForm.value.jersey_size = "";
    orgJoinForm.value.full_marathon_pb = "";
    orgJoinForm.value.health_declaration = "本人确认身体健康，无不适合高强度跑步的疾病。";
    orgJoinForm.value.program = "中文EMBA";
    orgJoinForm.value.class_detail = "";
    orgJoinForm.value.class_name = "";
    orgJoinForm.value.gobi_type = "new";
    orgJoinForm.value.gobi_edition = "戈20";
    orgJoinForm.value.gobi_group = "A组";
    orgJoinForm.value.gobi_experience = "新戈";
  }
  orgJoinForm.value.invite_code = presetCode || "";
  orgJoinForm.value.org_id = presetOrgId || "";
  showOrgJoinModal.value = true;
}

function openOrgEditProfileModal() {
  if (!currentOrg.value) return;
  isUpdatingOrgProfile.value = true;
  orgWizardStep.value = 1;
  showOrgGenderDobAdjust.value = false;
  computeOrgScrollHeight(true);
  orgJoinForm.value.invite_code = currentOrg.value.invite_code || "";
  orgJoinForm.value.real_name = currentOrg.value.real_name || "";
  orgJoinForm.value.gender = currentOrg.value.gender || "male";
  orgJoinForm.value.date_of_birth = currentOrg.value.date_of_birth || "1988-08-08";

  const rawClass = currentOrg.value.class_name || "";
  const existingProg = currentOrg.value.program || ORG_PROGRAM_OPTIONS.find(p => rawClass.includes(p)) || "中文EMBA";
  orgJoinForm.value.program = existingProg;
  orgJoinForm.value.class_detail = currentOrg.value.class_detail || rawClass.replace(existingProg, "").trim();
  orgJoinForm.value.class_name = rawClass;

  const rawGobi = currentOrg.value.gobi_experience || "";
  if (!rawGobi || rawGobi === "新戈") {
    orgJoinForm.value.gobi_type = "new";
    orgJoinForm.value.gobi_edition = "戈20";
    orgJoinForm.value.gobi_group = "A组";
    orgJoinForm.value.gobi_experience = "新戈";
  } else {
    orgJoinForm.value.gobi_type = "vet";
    const parts = rawGobi.split(" ");
    orgJoinForm.value.gobi_edition = parts[0] || "戈20";
    orgJoinForm.value.gobi_group = parts[1] || "A组";
    orgJoinForm.value.gobi_experience = rawGobi;
  }

  orgJoinForm.value.phone = currentOrg.value.phone || "";
  orgJoinForm.value.id_card = currentOrg.value.id_card || "";
  orgJoinForm.value.emergency_contact = currentOrg.value.emergency_contact || "";
  orgJoinForm.value.running_shoe_size = currentOrg.value.running_shoe_size || "";
  orgJoinForm.value.jersey_size = currentOrg.value.jersey_size || "";
  orgJoinForm.value.full_marathon_pb = currentOrg.value.full_marathon_pb || "";
  orgJoinForm.value.health_declaration = currentOrg.value.health_declaration || "本人确认身体健康，无不适合高强度跑步的疾病。";
  showOrgJoinModal.value = true;
}

function onOrgDobChange(e: any) {
  orgJoinForm.value.date_of_birth = e.detail.value;
}

/** 跳过资料填写，一键加入大群（临时成员，14 天内补齐并通过审核） */
async function submitOrgQuickJoin() {
  let uid = user.value?.id;
  if (!uid) {
    const autologin = await checkAndAutoLogin();
    uid = autologin?.id;
  }
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  const codeVal = (orgJoinForm.value.invite_code || "").trim().toUpperCase();
  const defaultOrg = targetDefaultOrg.value;
  const orgId = orgJoinForm.value.org_id || defaultOrg?.id || "";
  const trustedInvite = isInviteFromWechat.value && (orgInviteOneClick.value || Boolean(codeVal));
  if (!codeVal && !trustedInvite && (!defaultOrg || defaultOrg.join_mode !== "free")) {
    uni.showToast({ title: "请输入大群专属邀请码", icon: "none" });
    return;
  }
  quickJoiningOrg.value = true;
  try {
    const payload: any = {
      user_id: uid,
      via_invite: isInviteFromWechat.value,
      inviter_uid: invitedByUid.value || undefined,
      skip_profile: true,
    };
    if (codeVal) payload.invite_code = codeVal;
    if (orgId) payload.org_id = orgId;
    const res = await request("/api/org/join", "POST", payload);
    trackFunnelStep("org_quick_join_success", "一键快速加入大群成功");
    showOrgJoinModal.value = false;
    await loadClubData();
    const m = res?.membership || {};
    await afterOrgJoined(uid, m);
  } catch (e: any) {
    const msg = e?.message || e?.data?.detail || "加入大群失败，请稍后重试";
    uni.showModal({ title: "操作提示", content: String(msg), showCancel: false });
  } finally {
    quickJoiningOrg.value = false;
  }
}

/** 入群后：自动加入待加入的跑团；若资料未补齐，提示截止时间（立即补填 / 稍后再填） */
async function afterOrgJoined(uid: string, membership: any) {
  let joinedClubName = "";
  if (pendingSubClubToJoin.value) {
    const pClub = pendingSubClubToJoin.value;
    pendingSubClubToJoin.value = null;
    try {
      await request("/api/team/join-club", "POST", {
        user_id: uid,
        club_id: pClub.club_id,
        invite_code: pClub.invite_code,
        privacy_consent: true,
        inviter_uid: invitedByUid.value || undefined,
        via_invite: true,
      });
      joinedClubName = pClub.club_name || "跑团";
      setActiveClubId(pClub.club_id);
      await loadClubData();
    } catch (err: any) {
      console.warn("Auto join subclub after org join failed:", err);
    }
  }
  const shown = promptOrgProfileLater(
    { ...membership, org_name: membership?.org_name || invitedOrgName.value },
    joinedClubName || undefined
  );
  if (!shown) {
    uni.showToast({ title: joinedClubName ? `成功加入【${joinedClubName}】！` : "加入成功！", icon: "success" });
  }
  if (!joinedClubName && orgSubClubs.value.length > 0 && userClubs.value.length === 0 && !shown) {
    showSubClubsModal.value = true;
  }
}

async function submitOrgJoin() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  const codeVal = orgJoinForm.value.invite_code.trim().toUpperCase();
  const defaultOrg = targetDefaultOrg.value;
  const trustedInvite = isInviteFromWechat.value && (orgInviteOneClick.value || Boolean(codeVal));
  if (!isUpdatingOrgProfile.value && !codeVal && !trustedInvite) {
    if (!defaultOrg || defaultOrg.join_mode !== "free") {
      uni.showToast({ title: "请输入大群专属邀请码", icon: "none" });
      return;
    }
  }
  if (isOrgFieldVisible("real_name") && isOrgFieldRequired("real_name") && !orgJoinForm.value.real_name.trim()) {
    uni.showToast({ title: "请填写真实姓名", icon: "none" });
    return;
  }
  if (isOrgFieldVisible("date_of_birth") && isOrgFieldRequired("date_of_birth") && !orgJoinForm.value.date_of_birth.trim()) {
    uni.showToast({ title: "请选择出生日期", icon: "none" });
    return;
  }

  const computedGobi = orgJoinForm.value.gobi_type === "new" ? "新戈" : `${orgJoinForm.value.gobi_edition} ${orgJoinForm.value.gobi_group}`;
  const computedClass = orgJoinForm.value.program
    ? `${orgJoinForm.value.program} ${orgJoinForm.value.class_detail}`.trim()
    : orgJoinForm.value.class_name.trim();

  if (
    isOrgFieldVisible("class_name") &&
    isOrgFieldRequired("class_name") &&
    (!computedClass || (orgJoinForm.value.program && !orgJoinForm.value.class_detail.trim()))
  ) {
    uni.showToast({ title: "请填写班级/届别", icon: "none" });
    return;
  }
  if (isOrgFieldVisible("phone") && isOrgFieldRequired("phone") && !orgJoinForm.value.phone.trim()) {
    uni.showToast({ title: "请填写手机号", icon: "none" });
    return;
  }
  if (isOrgFieldVisible("id_card") && isOrgFieldRequired("id_card") && !orgJoinForm.value.id_card.trim()) {
    uni.showToast({ title: "请填写身份证号/护照号", icon: "none" });
    return;
  }
  if (
    isOrgFieldVisible("emergency_contact") &&
    isOrgFieldRequired("emergency_contact") &&
    !orgJoinForm.value.emergency_contact.trim()
  ) {
    uni.showToast({ title: "请填写紧急联系人及电话", icon: "none" });
    return;
  }
  if (isOrgFieldVisible("clothing_size") && isOrgFieldRequired("clothing_size") && !orgJoinForm.value.jersey_size.trim()) {
    uni.showToast({ title: "请选择参赛服尺码", icon: "none" });
    return;
  }
  if (isOrgFieldVisible("shoe_size") && isOrgFieldRequired("shoe_size") && !orgJoinForm.value.running_shoe_size.trim()) {
    uni.showToast({ title: "请填写跑鞋尺码", icon: "none" });
    return;
  }
  if (isOrgFieldVisible("marathon_pb") && isOrgFieldRequired("marathon_pb") && !orgJoinForm.value.full_marathon_pb.trim()) {
    uni.showToast({ title: "请填写全马 PB", icon: "none" });
    return;
  }
  if (
    isOrgFieldVisible("health_declaration") &&
    isOrgFieldRequired("health_declaration") &&
    !orgJoinForm.value.health_declaration.trim()
  ) {
    uni.showToast({ title: "请勾选健康与安全确认", icon: "none" });
    return;
  }

  joiningOrg.value = true;
  try {
    if (isUpdatingOrgProfile.value && currentOrg.value) {
      const res = await request(`/api/org/${currentOrg.value.id}/members/update-profile`, "POST", {
        user_id: uid,
        real_name: orgJoinForm.value.real_name.trim(),
        gender: orgJoinForm.value.gender,
        date_of_birth: orgJoinForm.value.date_of_birth.trim(),
        class_name: computedClass,
        program: orgJoinForm.value.program,
        class_detail: orgJoinForm.value.class_detail.trim(),
        gobi_experience: computedGobi,
        phone: orgJoinForm.value.phone.trim(),
        id_card: orgJoinForm.value.id_card.trim(),
        emergency_contact: orgJoinForm.value.emergency_contact.trim(),
        clothing_size: orgJoinForm.value.jersey_size.trim(),
        jersey_size: orgJoinForm.value.jersey_size.trim(),
        shoe_size: orgJoinForm.value.running_shoe_size.trim(),
        running_shoe_size: orgJoinForm.value.running_shoe_size.trim(),
        marathon_pb: orgJoinForm.value.full_marathon_pb.trim(),
        full_marathon_pb: orgJoinForm.value.full_marathon_pb.trim(),
        health_declaration: orgJoinForm.value.health_declaration.trim()
      });
      uni.showModal({
        title: "资料提交成功",
        content: res?.message || "大群资料已成功更新！",
        showCancel: false
      });
    } else {
      const joinPayload: any = {
        user_id: uid,
        real_name: orgJoinForm.value.real_name.trim(),
        gender: orgJoinForm.value.gender,
        date_of_birth: orgJoinForm.value.date_of_birth.trim(),
        class_name: computedClass,
        program: orgJoinForm.value.program,
        class_detail: orgJoinForm.value.class_detail.trim(),
        gobi_experience: computedGobi,
        phone: orgJoinForm.value.phone.trim(),
        id_card: orgJoinForm.value.id_card.trim(),
        emergency_contact: orgJoinForm.value.emergency_contact.trim(),
        clothing_size: orgJoinForm.value.jersey_size.trim(),
        jersey_size: orgJoinForm.value.jersey_size.trim(),
        shoe_size: orgJoinForm.value.running_shoe_size.trim(),
        running_shoe_size: orgJoinForm.value.running_shoe_size.trim(),
        marathon_pb: orgJoinForm.value.full_marathon_pb.trim(),
        full_marathon_pb: orgJoinForm.value.full_marathon_pb.trim(),
        health_declaration: orgJoinForm.value.health_declaration.trim()
      };
      if (codeVal) {
        joinPayload.invite_code = codeVal;
      }
      if (orgJoinForm.value.org_id || defaultOrg?.id) {
        joinPayload.org_id = orgJoinForm.value.org_id || defaultOrg?.id;
      }
      joinPayload.via_invite = isInviteFromWechat.value;
      if (invitedByUid.value) joinPayload.inviter_uid = invitedByUid.value;
      const res = await request("/api/org/join", "POST", joinPayload);
      showOrgJoinModal.value = false;
      await loadClubData();
      await afterOrgJoined(uid, res?.membership || {});
      return;
    }

    showOrgJoinModal.value = false;
    await loadClubData();

    if (pendingSubClubToJoin.value) {
      const pClub = pendingSubClubToJoin.value;
      pendingSubClubToJoin.value = null;
      try {
        await request("/api/team/join-club", "POST", {
          user_id: uid,
          club_id: pClub.club_id,
          invite_code: pClub.invite_code,
          privacy_consent: true,
        });
        uni.showToast({ title: `成功加入【${pClub.club_name || '跑团'}】！`, icon: "success" });
        setActiveClubId(pClub.club_id);
        await loadClubData();
      } catch (err: any) {
        console.warn("Auto join subclub after org join postponed:", err);
      }
    } else if (orgSubClubs.value.length > 0 && userClubs.value.length === 0) {
      showSubClubsModal.value = true;
    }
  } catch (e: any) {
    let msg = e?.message;
    if (typeof msg === "object" || !msg) {
      if (e?.data?.detail) {
        msg = typeof e.data.detail === "string" ? e.data.detail : JSON.stringify(e.data.detail);
      } else {
        msg = "认证操作失败，请核对后重试";
      }
    }
    uni.showModal({
      title: "操作提示",
      content: String(msg),
      showCancel: false
    });
  } finally {
    joiningOrg.value = false;
  }
}

function openSubClubsModal() {
  showSubClubsModal.value = true;
}

async function openOrgMembersModal() {
  orgMemberSearch.value = "";
  showOrgMembersModal.value = true;
  if (currentOrg.value) {
    try {
      const uid = user.value?.id;
      const memRes = await request(`/api/org/${currentOrg.value.id}/members?operator_uid=${uid || ''}`);
      if (memRes?.members) {
        orgMembers.value = memRes.members;
      }
    } catch (e) {
      console.warn("Failed to refresh org members on open:", e);
    }
  }
}

async function handleConfirmOrgMember(targetUid: string) {
  if (!currentOrg.value) return;
  try {
    const uid = user.value?.id;
    await request(`/api/org/${currentOrg.value.id}/members/${targetUid}/confirm`, "POST", {
      operator_uid: uid
    });
    uni.showToast({ title: "已确认该戈友资料", icon: "success" });
    const memRes = await request(`/api/org/${currentOrg.value.id}/members?operator_uid=${uid || ''}`);
    orgMembers.value = memRes?.members || [];
  } catch (e: any) {
    uni.showToast({ title: e?.message || "确认失败", icon: "none" });
  }
}

async function handleToggleOrgMemberRole(targetMember: any, newRole: 'admin' | 'member') {
  if (!currentOrg.value || !targetMember) return;
  const actionText = newRole === 'admin' ? '委派为大群管理员' : '撤销大群管理员职务';
  const name = targetMember.real_name || targetMember.display_name || '该成员';

  uni.showModal({
    title: `确认${actionText}？`,
    content: newRole === 'admin'
      ? `委派【${name}】为大群管理员后，其将拥有查看全员未脱敏档案及审核戈友入群的权限。`
      : `撤销【${name}】的管理权限后，其将恢复为普通戈友成员。`,
    confirmText: '确认',
    confirmColor: newRole === 'admin' ? '#3b82f6' : '#ef4444',
    success: async (res) => {
      if (res.confirm) {
        try {
          uni.showLoading({ title: '处理中...' });
          const uid = user.value?.id;
          await request(`/api/org/${currentOrg.value.id}/members/${targetMember.user_id}/role`, 'POST', {
            operator_uid: uid,
            role: newRole
          });
          uni.hideLoading();
          uni.showToast({ title: `${actionText}成功`, icon: 'success' });
          const memRes = await request(`/api/org/${currentOrg.value.id}/members?operator_uid=${uid || ''}`);
          orgMembers.value = memRes?.members || [];
        } catch (e: any) {
          uni.hideLoading();
          uni.showModal({
            title: '操作失败',
            content: e?.message || e?.data?.detail || '权限变更失败，请重试',
            showCancel: false
          });
        }
      }
    }
  });
}

const filteredOrgMembers = computed(() => {
  if (!orgMemberSearch.value.trim()) return orgMembers.value;
  const q = orgMemberSearch.value.trim().toLowerCase();
  return orgMembers.value.filter((m: any) =>
    (m.real_name || "").toLowerCase().includes(q) ||
    (m.class_name || "").toLowerCase().includes(q) ||
    (m.program || "").toLowerCase().includes(q) ||
    (m.gobi_experience || "").toLowerCase().includes(q) ||
    (m.display_name || "").toLowerCase().includes(q)
  );
});

const allClubs = ref<any[]>([]);
const userClubs = ref<any[]>([]);
const clubModalTab = ref<"joined" | "all">("joined");
const selectedCityFilter = ref<string>("全部");
const clubSearchText = ref<string>("");
const availableCities = ref<string[]>([
  "全部", "上海", "北京", "深圳", "广州", "杭州", "南京", "成都", "武汉", "苏州", "厦门"
]);

function goToOnboarding() {
  uni.navigateTo({
    url: "/pages/onboarding/onboarding"
  });
}

function openMenteeScienceAnalysis(mentee: any) {
  const mUid = mentee?.mentee_uid || mentee?.user_id;
  if (!mUid) return;
  const nameParam = encodeURIComponent(mentee?.display_name || "徒弟");
  showMenteeDetailModal.value = false;
  uni.navigateTo({
    url: `/pages/analysis/analysis?target_uid=${encodeURIComponent(mUid)}&target_name=${nameParam}`
  });
}

function openAllClubsModal() {
  clubModalTab.value = userClubs.value.length > 0 ? "joined" : "all";
  showAllClubsModal.value = true;
}

function filterClubsList(rawList: any[]) {
  let list = rawList || [];
  const userOrgIdSet = new Set((userOrgs.value || []).map((o: any) => o.id));
  const isSuper = ["admin", "super_admin"].includes(user.value?.id);
  list = list.filter((c: any) => {
    if (c.org_id && !userOrgIdSet.has(c.org_id) && !isSuper) {
      return false;
    }
    return true;
  });

  if (selectedCityFilter.value && selectedCityFilter.value !== "全部") {
    const cf = selectedCityFilter.value.trim();
    list = list.filter((c: any) => (c.city || "").includes(cf) || cf.includes(c.city || ""));
  }

  if (clubSearchText.value && clubSearchText.value.trim()) {
    const q = clubSearchText.value.trim().toLowerCase();
    list = list.filter((c: any) =>
      (c.name || "").toLowerCase().includes(q) ||
      (c.city || "").toLowerCase().includes(q) ||
      (c.description || "").toLowerCase().includes(q) ||
      (c.org_name || "").toLowerCase().includes(q)
    );
  }

  return list;
}

const filteredClubs = computed(() => {
  return filterClubsList(allClubs.value);
});

const filteredOrgClubs = computed(() => {
  return filteredClubs.value.filter((c: any) => Boolean(c.org_id));
});

const filteredIndepClubs = computed(() => {
  return filteredClubs.value.filter((c: any) => !c.org_id);
});

const displayedClubs = computed(() => {
  if (clubModalTab.value === "joined") {
    const userOrgIdSet = new Set((userOrgs.value || []).map((o: any) => o.id));
    const isSuper = ["admin", "super_admin"].includes(user.value?.id);
    const joinedMap = new Map<string, any>();
    for (const uc of userClubs.value || []) {
      joinedMap.set(uc.id, { ...uc, is_member: true });
    }
    for (const ac of allClubs.value || []) {
      if (ac.is_member || joinedMap.has(ac.id)) {
        const existing = joinedMap.get(ac.id) || {};
        joinedMap.set(ac.id, { ...existing, ...ac, role: existing.role || ac.role, is_member: true });
      }
    }
    let joined = Array.from(joinedMap.values()).filter((c: any) => {
      if (c.org_id && !userOrgIdSet.has(c.org_id) && !isSuper) {
        return false;
      }
      return true;
    });
    if (clubSearchText.value && clubSearchText.value.trim()) {
      const q = clubSearchText.value.trim().toLowerCase();
      joined = joined.filter((c: any) =>
        (c.name || "").toLowerCase().includes(q) ||
        (c.city || "").toLowerCase().includes(q) ||
        (c.description || "").toLowerCase().includes(q) ||
        (c.org_name || "").toLowerCase().includes(q)
      );
    }
    return joined;
  }
  return filterClubsList(allClubs.value);
});

const displayedOrgClubs = computed(() => {
  return displayedClubs.value.filter((c: any) => Boolean(c.org_id));
});

const displayedIndepClubs = computed(() => {
  return displayedClubs.value.filter((c: any) => !c.org_id);
});


// 英雄榜与动态已改为二级页（带原生返回键）；section=feed 时直接定位到打卡动态
function goToRankPage(section?: string) {
  uni.navigateTo({
    url: section ? `/pages/rank/rank?section=${section}` : "/pages/rank/rank"
  });
}

function goToIndexPage() {
  uni.switchTab({
    url: "/pages/index/index"
  });
}

function goToCoachPage() {
  uni.switchTab({
    url: "/pages/coach/coach"
  });
}

function goToProfilePage() {
  uni.switchTab({
    url: "/pages/profile/profile"
  });
}

const isCurrentClubSuspended = ref(false);
const currentSuspensionReason = ref("");
const serverIsSuperAdmin = ref(false);

const SUPER_ADMIN_UIDS = ["admin", "super_admin"];
const isSuperAdmin = computed(() => {
  const uid = String(user.value?.id || "");
  if (SUPER_ADMIN_UIDS.includes(uid) || uid.startsWith("rgm_super_admin")) return true;
  if (user.value?.is_admin || user.value?.role === "admin" || user.value?.role === "super_admin") return true;
  return serverIsSuperAdmin.value;
});

const isOwnerOrDev = computed(() => {
  if (!user.value || !currentClub.value) return false;
  return (
    currentRole.value === "owner" ||
    currentClub.value.owner_id === user.value.id ||
    isSuperAdmin.value
  );
});

const isOrgAdmin = computed(() => {
  if (user.value?.role === "admin" || isSuperAdmin.value) return true;
  return !!currentOrg.value && ["owner", "admin"].includes(currentOrg.value.role);
});

// ── 跑团首页拆分：页内子页面（共用同一份数据与弹窗，避免拆文件带来的状态同步问题） ──
type TeamSection = "" | "events" | "manage" | "org" | "new_members";
const activeSection = ref<TeamSection>("");
const leaderboard = ref<any[]>([]);
const myRankItem = computed(() => leaderboard.value.find((i: any) => i.user_id === user.value?.id) || null);
const topThree = computed(() => leaderboard.value.filter((i: any) => i.rank <= 3).slice(0, 3));
const isClubManager = computed(
  () =>
    currentRole.value === "owner" ||
    currentRole.value === "coach" ||
    isOwnerOrDev.value ||
    isSuperAdmin.value ||
    (isOrgAdmin.value && (!currentClub.value || currentClub.value.org_id === currentOrg.value?.id))
);
const managerTitle = computed(() =>
  currentRole.value === "owner" || isOwnerOrDev.value
    ? "团长管理中心"
    : currentRole.value === "coach"
      ? "教练管理中心"
      : "大群管理中心"
);
const orgStatusShort = computed(() => {
  const st = currentOrg.value?.status;
  if (st === "confirmed") return "已认证";
  if (st === "pending") return "待审核";
  if (st === "expired") return "已过期";
  return "待补资料";
});
const orgStatusText = computed(() => {
  const o = currentOrg.value;
  if (!o) return "";
  const days = o.remaining_days ?? 14;
  if (o.status === "confirmed") return "✓ 正式成员 · 实名已认证";
  if (o.status === "pending") return `⏳ 资料已提交，等待审核（剩 ${days} 天）`;
  if (o.status === "expired") return "🚫 临时期已过，访问已暂停";
  return `⚠️ 请在 ${days} 天内补齐必填资料`;
});
const activeSectionTitle = computed(() => {
  if (activeSection.value === "events") return "约跑与拉练活动";
  if (activeSection.value === "new_members") {
    return newMemberScope.value === "unaffiliated"
      ? (isSuperAdmin.value ? "未入团自由跑友名册" : "自由跑友同伴状态")
      : "新队员管理";
  }
  if (activeSection.value === "manage") return managerTitle.value;
  if (activeSection.value === "org") return currentOrg.value ? `${currentOrg.value.name} 大群` : "大群认证";
  return "";
});

// ── 🌱 新队员与入团设定状态 & 🌍 未入团自由跑友名册 (New Members & Unaffiliated Users Status) ──
const newMemberScope = ref<"club" | "unaffiliated">("club");
const newMembersData = ref<any>(null);
const loadingNewMembers = ref(false);
const unaffiliatedData = ref<any>(null);
const loadingUnaffiliated = ref(false);
const remindingMemberUid = ref("");
const newMemberFilter = ref<"all" | "recent" | "pending" | "ready">("all");
const newMemberSearchQuery = ref("");

function normalizeNewMemberItem(rawItem: any, cockpitMap: Map<string, any>): any {
  const m = { ...(rawItem || {}) };
  const s = cockpitMap.get(String(m.user_id || "")) || null;
  if (s) {
    if (m.weekly_target_km == null && s.weekly_target != null) {
      m.weekly_target_km = Number(s.weekly_target);
    }
    if (m.monthly_target_km == null && s.target_km != null) {
      m.monthly_target_km = Number(s.target_km);
    }
    if (m.has_training_plan == null && s.plan_info) {
      m.has_training_plan = Boolean(s.plan_info.has_active_plan || s.plan_info.has_draft_plan);
    }
    if (m.total_runs_count == null && Array.isArray(s.recent_activities)) {
      m.total_runs_count = Math.max(s.recent_activities.length, Number(s.runs_7d_count || 0));
    }
  }
  const monthTarget = Number(m.monthly_target_km ?? m.target_km ?? 200);
  const weekTarget = Number(m.weekly_target_km ?? m.weekly_target ?? Math.round((monthTarget / 4) * 10) / 10 ?? 50);
  m.monthly_target_km = monthTarget;
  m.weekly_target_km = weekTarget;

  if (typeof m.watch_bound !== "boolean") {
    const hasActivityOrBio =
      Number(m.total_runs_count || 0) > 0 ||
      Number(m.month_km || 0) > 0 ||
      Boolean(s && (Number(s.ctl || 0) > 0 || Number(s.vo2max || 0) > 0 || (s.recent_activities && s.recent_activities.length > 0)));
    const hasFlag = Boolean(
      m.garmin_connected || m.coros_connected || m.apple_watch_connected || m.huawei_connected || m.suunto_connected
    );
    m.watch_bound = hasFlag || hasActivityOrBio;
    if (!m.watch_status_label) {
      m.watch_status_label = m.watch_bound ? "已绑表/同步" : "未绑定手表";
    }
  }

  if (typeof m.goal_set !== "boolean") {
    const hasCustomTarget = monthTarget !== 200 || weekTarget !== 50;
    m.goal_set = Boolean(hasCustomTarget || m.has_training_plan || Number(m.month_km || 0) > 0);
  }

  if (!m.joined_at_display && m.joined_at) {
    const dt = new Date(String(m.joined_at));
    if (!isNaN(dt.getTime())) {
      const bjMs = dt.getTime() + 8 * 3600 * 1000;
      const bj = new Date(bjMs);
      const y = bj.getUTCFullYear();
      const mo = String(bj.getUTCMonth() + 1).padStart(2, "0");
      const da = String(bj.getUTCDate()).padStart(2, "0");
      const hh = String(bj.getUTCHours()).padStart(2, "0");
      const mm = String(bj.getUTCMinutes()).padStart(2, "0");
      m.joined_at_display = `${y}-${mo}-${da} ${hh}:${mm}`;
      const diffDays = Math.max(0, Math.floor((Date.now() - dt.getTime()) / (24 * 3600 * 1000)));
      m.days_since_joined = diffDays;
      m.is_new_7d = diffDays <= 7;
      m.is_new_30d = diffDays <= 30;
      m.joined_relative_label =
        diffDays === 0 ? "今日入团" : diffDays === 1 ? "昨日入团" : diffDays <= 30 ? `${diffDays}天前入团` : `${y}-${mo}-${da}`;
    }
  }
  return m;
}

const clubNewMembersSortedList = computed<any[]>(() => {
  const cockpitStudents = coachCockpit.value?.students || [];
  const cockpitMap = new Map<string, any>();
  for (const s of cockpitStudents) {
    if (s?.user_id) cockpitMap.set(String(s.user_id), s);
  }
  const raw = newMembersData.value?.members?.length ? newMembersData.value.members : members.value;
  return (raw || [])
    .map((item: any) => normalizeNewMemberItem(item, cockpitMap))
    .sort((a: any, b: any) => {
      const tA = String(a?.joined_at || "");
      const tB = String(b?.joined_at || "");
      return tB.localeCompare(tA);
    });
});

const clubNewMembersSummary = computed(() => {
  if (newMembersData.value?.summary) {
    return newMembersData.value.summary;
  }
  const list = clubNewMembersSortedList.value;
  return {
    total_members: list.length,
    new_7d_count: list.filter((m: any) => m.is_new_7d).length,
    new_30d_count: list.filter((m: any) => m.is_new_30d).length,
    watch_bound_count: list.filter((m: any) => m.watch_bound).length,
    watch_unbound_count: list.filter((m: any) => !m.watch_bound).length,
    goal_set_count: list.filter((m: any) => m.goal_set).length,
    goal_unset_count: list.filter((m: any) => !m.goal_set).length,
    pending_setup_count: list.filter((m: any) => !m.watch_bound || !m.goal_set).length,
  };
});

const unaffiliatedSortedList = computed<any[]>(() => {
  const emptyMap = new Map<string, any>();
  const raw = unaffiliatedData.value?.members || [];
  return (raw || [])
    .map((item: any) => normalizeNewMemberItem(item, emptyMap))
    .sort((a: any, b: any) => {
      const tA = String(a?.joined_at || "");
      const tB = String(b?.joined_at || "");
      return tB.localeCompare(tA);
    });
});

const unaffiliatedSummary = computed(() => {
  if (unaffiliatedData.value?.summary) {
    return unaffiliatedData.value.summary;
  }
  const list = unaffiliatedSortedList.value;
  return {
    total_members: list.length,
    new_7d_count: list.filter((m: any) => m.is_new_7d).length,
    new_30d_count: list.filter((m: any) => m.is_new_30d).length,
    watch_bound_count: list.filter((m: any) => m.watch_bound).length,
    watch_unbound_count: list.filter((m: any) => !m.watch_bound).length,
    goal_set_count: list.filter((m: any) => m.goal_set).length,
    goal_unset_count: list.filter((m: any) => !m.goal_set).length,
    pending_setup_count: list.filter((m: any) => !m.watch_bound || !m.goal_set).length,
  };
});

const unaffiliatedPreviewList = computed<any[]>(() => {
  const list = unaffiliatedSortedList.value;
  // Prioritize showing peers who have bound watches or synced runs first in the 3-item preview
  return [...list]
    .sort((a: any, b: any) => {
      const scoreA = (a.watch_bound ? 2 : 0) + (a.goal_set ? 1 : 0);
      const scoreB = (b.watch_bound ? 2 : 0) + (b.goal_set ? 1 : 0);
      if (scoreB !== scoreA) return scoreB - scoreA;
      return Number(b.month_km || 0) - Number(a.month_km || 0);
    })
    .slice(0, 3);
});

const newMembersSortedList = computed<any[]>(() => {
  if (newMemberScope.value === "unaffiliated" || !currentClub.value) {
    return unaffiliatedSortedList.value;
  }
  return clubNewMembersSortedList.value;
});

const newMembersSummary = computed(() => {
  if (newMemberScope.value === "unaffiliated" || !currentClub.value) {
    return unaffiliatedSummary.value;
  }
  return clubNewMembersSummary.value;
});

const filteredNewMembersList = computed<any[]>(() => {
  let list = newMembersSortedList.value;
  if (newMemberFilter.value === "recent") {
    list = list.filter((m: any) => m.is_new_30d);
  } else if (newMemberFilter.value === "pending") {
    list = list.filter((m: any) => !m.watch_bound || !m.goal_set);
  } else if (newMemberFilter.value === "ready") {
    list = list.filter((m: any) => m.watch_bound && m.goal_set);
  }
  const q = newMemberSearchQuery.value.trim().toLowerCase();
  if (q) {
    list = list.filter(
      (m: any) =>
        (m.display_name || "").toLowerCase().includes(q) ||
        (m.user_id || "").toLowerCase().includes(q)
    );
  }
  return list;
});

async function fetchNewMembersStatus() {
  const clubId = currentClub.value?.id;
  const uid = user.value?.id || getStoredUser()?.id;
  if (!clubId || !uid) return;
  loadingNewMembers.value = true;
  try {
    const res = await request(
      `/api/team/${encodeURIComponent(clubId)}/new-members?user_id=${encodeURIComponent(uid)}`
    );
    if (res && Array.isArray(res.members)) {
      newMembersData.value = res;
    }
  } catch (e) {
    console.warn("fetchNewMembersStatus failed:", e);
  } finally {
    loadingNewMembers.value = false;
  }
}

async function fetchUnaffiliatedMembersStatus() {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid) return;
  loadingUnaffiliated.value = true;
  try {
    const res = await request(
      `/api/team/unaffiliated-members?user_id=${encodeURIComponent(uid)}`
    );
    if (res && Array.isArray(res.members)) {
      unaffiliatedData.value = res;
    }
  } catch (e) {
    console.warn("fetchUnaffiliatedMembersStatus failed:", e);
  } finally {
    loadingUnaffiliated.value = false;
  }
}

function openNewMembersScope(scope: "club" | "unaffiliated") {
  newMemberScope.value = scope;
  newMemberFilter.value = "all";
  newMemberSearchQuery.value = "";
  activeSection.value = "new_members";
  if (scope === "unaffiliated") {
    fetchUnaffiliatedMembersStatus();
    trackSubView("team_unaffiliated_members", "跑团页切换子视图：未入团自由跑友名册");
  } else {
    fetchNewMembersStatus();
    trackSubView("team_new_members", "跑团页切换子视图：新队员管理");
  }
  uni.pageScrollTo({ scrollTop: 0, duration: 0 });
}

function switchNewMemberScope(scope: "club" | "unaffiliated") {
  newMemberScope.value = scope;
  newMemberFilter.value = "all";
  trackSubView(
    scope === "unaffiliated" ? "team_unaffiliated_members" : "team_new_members",
    scope === "unaffiliated" ? "切换至未入团自由跑友名册" : "切换至本跑团新队员管理"
  );
  if (scope === "unaffiliated") {
    if (!unaffiliatedData.value) fetchUnaffiliatedMembersStatus();
  } else {
    if (!newMembersData.value) fetchNewMembersStatus();
  }
}

async function handleRemindMemberSetup(memberItem: any) {
  const uid = user.value?.id || getStoredUser()?.id;
  if (!uid || !memberItem?.user_id) return;
  const isUnaffiliatedScope = newMemberScope.value === "unaffiliated" || !currentClub.value?.id;
  const clubId = isUnaffiliatedScope ? "unaffiliated" : currentClub.value?.id;
  if (!clubId) return;
  trackClick("team_remind_member", `提醒完善绑表/目标：${memberItem.display_name || "跑友"}`, {
    scope: isUnaffiliatedScope ? "unaffiliated" : "club",
    target_uid: memberItem.user_id,
  });
  remindingMemberUid.value = memberItem.user_id;
  try {
    const endpoint = isUnaffiliatedScope
      ? `/api/team/unaffiliated/remind-member`
      : `/api/team/${encodeURIComponent(clubId)}/remind-member`;
    const res = await request(endpoint, "POST", {
      operator_uid: uid,
      target_uid: memberItem.user_id,
    });
    uni.showToast({
      title: res?.message || `已提醒【${memberItem.display_name || "该跑友"}】`,
      icon: "success",
      duration: 2400,
    });
  } catch (e: any) {
    uni.showToast({
      title: e?.message || e?.data?.detail || "发送提醒失败",
      icon: "none",
    });
  } finally {
    remindingMemberUid.value = "";
  }
}

function openMemberRunnerAnalysis(memberItem: any) {
  const targetUid = memberItem?.user_id;
  if (!targetUid) return;
  trackClick("team_inspect_member_profile", `查看队员/跑友跑力档案：${memberItem?.display_name || "跑友"}`, {
    target_uid: targetUid,
    scope: newMemberScope.value,
  });
  const nameParam = encodeURIComponent(memberItem?.display_name || "跑友");
  uni.navigateTo({
    url: `/pages/analysis/analysis?target_uid=${encodeURIComponent(targetUid)}&target_name=${nameParam}`,
  });
}

function openSection(key: TeamSection) {
  activeSection.value = key;
  if (key === "new_members") {
    if (!currentClub.value) {
      newMemberScope.value = "unaffiliated";
      fetchUnaffiliatedMembersStatus();
    } else if (newMemberScope.value === "unaffiliated") {
      fetchUnaffiliatedMembersStatus();
    } else {
      fetchNewMembersStatus();
    }
  }
  if (key) {
    const names: Record<string, string> = {
      events: "约跑与拉练活动",
      new_members: "新队员管理",
      manage: "跑团管理后台",
      org: "大群体主页与认证",
    };
    trackSubView(`team_${key}`, `跑团页切换子视图：${names[key] || key}`);
  }
  uni.pageScrollTo({ scrollTop: 0, duration: 0 });
}
function closeSection() {
  activeSection.value = "";
  uni.pageScrollTo({ scrollTop: 0, duration: 0 });
}
// 退出跑团 / 失去管理权限后，自动回到跑团首页（但未入团用户查看未入团同伴列表或超管查看除外）
watch([currentClub, isClubManager], () => {
  if (!currentClub.value && (activeSection.value === "events" || activeSection.value === "manage")) {
    activeSection.value = "";
  }
  if (activeSection.value === "manage" && !isClubManager.value) {
    activeSection.value = "";
  }
  if (
    activeSection.value === "new_members" &&
    newMemberScope.value === "club" &&
    (!currentClub.value || (!isClubManager.value && !isSuperAdmin.value))
  ) {
    activeSection.value = "";
  }
});
// 跑团页已是 Tab 页：自定义 TabBar 会盖住底部弹窗，弹窗打开时临时隐藏
watch(isAnyModalOpen, (open) => setTabBarHidden(!!open, "team_page"));
const firstLoadPending = ref(true);

const isOrgOwner = computed(() => {
  if (user.value?.role === "admin") return true;
  return !!currentOrg.value && currentOrg.value.role === "owner";
});

const filteredMembers = computed(() => {
  if (!memberSearchQuery.value.trim()) return members.value;
  const q = memberSearchQuery.value.trim().toLowerCase();
  return members.value.filter(
    (m) =>
      (m.display_name || "").toLowerCase().includes(q) ||
      (m.user_id || "").toLowerCase().includes(q)
  );
});

async function loadClubData(preferredClubId?: string) {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    // Parallelize orgs and clubs requests so first-screen rendering doesn't wait for sequential round-trips
    const [orgRes, allOrgsRes, myRes, allRes] = await Promise.all([
      request(`/api/org/my-orgs/${uid}`).catch(() => ({ organizations: [] })),
      request(`/api/org/all/list`).catch(() => ({ organizations: [] })),
      request(`/api/team/my-clubs/${uid}`),
      request(`/api/team/all-clubs?user_id=${uid}`),
    ]);

    userOrgs.value = orgRes?.organizations || [];
    allPlatformOrgs.value = allOrgsRes?.organizations || [];
    if (userOrgs.value.length > 0) {
      currentOrg.value = userOrgs.value[0];
      const orgId = currentOrg.value.id;
      // Non-blocking background fetch for org sub-clubs and org members
      Promise.all([
        request(`/api/org/${orgId}/sub-clubs?user_id=${uid}`).catch(() => ({ sub_clubs: [] })),
        request(`/api/org/${orgId}/members?operator_uid=${uid}`).catch(() => ({ members: [] })),
      ]).then(([subRes, memRes]) => {
        orgSubClubs.value = subRes?.sub_clubs || [];
        orgMembers.value = memRes?.members || [];
      });
    } else {
      currentOrg.value = null;
      orgSubClubs.value = [];
      orgMembers.value = [];
    }

    const clubs = myRes?.clubs || [];
    if (typeof myRes?.is_super_admin === "boolean") {
      serverIsSuperAdmin.value = myRes.is_super_admin;
    }
    userClubs.value = clubs;
    allClubs.value = allRes?.clubs || [];
    if (allRes?.cities && Array.isArray(allRes.cities) && allRes.cities.length > 0) {
      availableCities.value = allRes.cities;
    }

    // 超管或未入团用户：异步拉取未入团自由跑友名单与状态
    if (isSuperAdmin.value || clubs.length === 0) {
      fetchUnaffiliatedMembersStatus();
    }

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

      currentClub.value = targetClub;
      currentRole.value = targetClub.role || "member";
      const clubId = targetClub.id;

      if (targetClub.is_access_suspended) {
        isCurrentClubSuspended.value = true;
        currentSuspensionReason.value = targetClub.suspension_reason || "";
      } else {
        isCurrentClubSuspended.value = false;
        currentSuspensionReason.value = "";
      }

      // Load events, members, coach cockpit with user_id
      try {
        const [evtRes, memRes, coachRes, lbRes] = await Promise.all([
          request(`/api/team/${clubId}/events?user_id=${uid}`).catch((e: any) => ({ error: e })),
          request(`/api/team/${clubId}/members?user_id=${uid}`).catch((e: any) => ({ error: e })),
          request(`/api/team/${clubId}/coach-cockpit?coach_uid=${uid}`).catch((e: any) => ({ error: e })),
          // 首页排名预览（我的排名 + 前三名）
          request(`/api/team/${clubId}/leaderboard?user_id=${uid}`).catch((e: any) => ({ error: e })),
        ]);

        if (evtRes?.error && (evtRes.error?.statusCode === 403 || String(evtRes.error?.message).includes("暂停"))) {
          isCurrentClubSuspended.value = true;
          currentSuspensionReason.value = evtRes.error.message;
        } else if (memRes?.error && (memRes.error?.statusCode === 403 || String(memRes.error?.message).includes("暂停"))) {
          isCurrentClubSuspended.value = true;
          currentSuspensionReason.value = memRes.error.message;
        } else {
          events.value = evtRes?.events || [];
          members.value = memRes?.members || [];
          newMembersData.value = null;
          coachCockpit.value = coachRes || null;
          leaderboard.value = lbRes?.error ? [] : (lbRes?.leaderboard || []);
          if (
            activeSection.value === "new_members" ||
            currentRole.value === "owner" ||
            currentRole.value === "coach" ||
            isOwnerOrDev.value
          ) {
            fetchNewMembersStatus();
          }
        }
      } catch (err: any) {
        if (err?.statusCode === 403 || String(err?.message).includes("暂停")) {
          isCurrentClubSuspended.value = true;
          currentSuspensionReason.value = err.message;
        }
      }
    } else {
      setActiveClubId("");
      currentClub.value = null;
      currentRole.value = "member";
      events.value = [];
      members.value = [];
      newMembersData.value = null;
      coachCockpit.value = null;
      leaderboard.value = [];
    }

    // 异步刷新师徒结对概览（支持同大群跨跑团）
    fetchMentorshipOverview();
  } catch (e) {
    console.warn("Load club data error:", e);
    return false;
  }
  return true;
}

function handleSwitchClub(club: any) {
  if (!club || !club.id) return;
  trackClick("team_switch_club", `切换跑团：${club.name}`, { club_id: club.id });
  setActiveClubId(club.id);
  showAllClubsModal.value = false;
  activeSection.value = "";
  uni.showToast({
    title: `已切换至【${club.name}】`,
    icon: "success"
  });
  loadClubData(club.id);
}

function handleJoinClubWithCheck(club: any) {
  if (!club || !club.id) return;
  if (club.can_join === false) {
    uni.showModal({
      title: "分队准入限制",
      content: club.join_restriction_reason || "该跑团隶属大群，您的大群资料补填期限已过，请补齐资料并联系管理员恢复资格。",
      showCancel: false
    });
    return;
  }
  if (club.join_mode === "invite") {
    targetClubForCodeJoin.value = club;
    clubJoinCodeInput.value = "";
    showClubCodeModal.value = true;
  } else if (needsWechatNickname.value && !joinRunnerNickname.value.trim()) {
    // 新跑友昵称仍为“跑者_xxxx”时，弹出跑团名片确认弹窗，引导一键点选微信真实昵称后再入团
    invitedClubInfo.value = club;
    invitedClubCode.value = "";
    showClubInviteModal.value = true;
  } else {
    handleJoinClubDirect(club.id);
  }
}

async function submitClubCodeJoin() {
  if (needsWechatNickname.value && !joinRunnerNickname.value.trim()) {
    uni.showToast({ title: "请先点击昵称框，一键填入您的微信昵称", icon: "none" });
    return;
  }
  const code = clubJoinCodeInput.value.trim().toUpperCase();
  if (!code) {
    uni.showToast({ title: "请输入跑团专属邀请码", icon: "none" });
    return;
  }
  const clubId = targetClubForCodeJoin.value?.id;
  if (!clubId) return;
  await handleJoinClubDirect(clubId, code);
  showClubCodeModal.value = false;
}

async function handleJoinClubDirect(clubId: string, inviteCode?: string) {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  joiningClubId.value = clubId;
  try {
    const payload: any = {
      user_id: uid,
      club_id: clubId,
      display_name: joinRunnerNickname.value.trim() || undefined,
      avatar_url: joinRunnerAvatar.value || undefined,
    };
    if (inviteCode) {
      payload.invite_code = inviteCode;
    }
    const res = await request("/api/team/join-club", "POST", payload);
    trackFunnelStep("club_join_success", "加入跑团成功", {
      club_id: clubId,
      via: inviteCode ? "code" : "direct",
    });
    syncUserNicknameAfterJoin(res);
    setActiveClubId(clubId);
    showAllClubsModal.value = false;
    showSubClubsModal.value = false;
    uni.showToast({ title: res?.message || "加入跑团成功！", icon: "success" });
    await loadClubData(clubId);
  } catch (e: any) {
    uni.showModal({
      title: "无法加入跑团",
      content: e?.message || e?.data?.detail || "加入失败，请检查门槛与规则",
      showCancel: false
    });
  } finally {
    joiningClubId.value = null;
  }
}

function openJoinModeModal() {
  selectedJoinMode.value = (currentClub.value?.join_mode === "invite") ? "invite" : "free";
  editInviteCode.value = currentClub.value?.invite_code || "";
  showJoinModeModal.value = true;
}

function handleGenerateRandomCode() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let randomPart = "";
  for (let i = 0; i < 4; i++) {
    randomPart += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  editInviteCode.value = "FD" + randomPart;
  uni.showToast({ title: "已生成新码，请点击保存", icon: "none" });
}

function handleCopyClubInviteCode() {
  const code = editInviteCode.value.trim() || currentClub.value?.invite_code;
  if (!code) {
    uni.showToast({ title: "暂无邀请码", icon: "none" });
    return;
  }
  uni.setClipboardData({
    data: code,
    success: () => {
      uni.showToast({ title: "邀请码已复制到剪贴板", icon: "success" });
    }
  });
}

async function saveClubJoinMode() {
  const clubId = currentClub.value?.id;
  const uid = user.value?.id;
  if (!clubId || !uid) return;

  const codeVal = editInviteCode.value.trim().toUpperCase();
  if (selectedJoinMode.value === "invite" && !codeVal) {
    uni.showToast({ title: "需邀请码模式下，邀请码不能为空", icon: "none" });
    return;
  }

  savingJoinMode.value = true;
  try {
    const payload: any = {
      operator_uid: uid,
      join_mode: selectedJoinMode.value
    };
    if (codeVal) {
      payload.invite_code = codeVal;
    }
    const res = await request(`/api/team/${clubId}/join-mode`, "POST", payload);
    if (currentClub.value) {
      currentClub.value.join_mode = selectedJoinMode.value;
      if (res?.club?.invite_code) {
        currentClub.value.invite_code = res.club.invite_code;
      }
    }
    uni.showToast({
      title: res?.message || "入团规则与专属邀请码已更新",
      icon: "success"
    });
    showJoinModeModal.value = false;
    await loadClubData(clubId);
  } catch (err: any) {
    uni.showToast({
      title: err?.message || err?.data?.detail || "设置失败，请重试",
      icon: "none"
    });
  } finally {
    savingJoinMode.value = false;
  }
}

// ── Grand Community Org Join Mode & Field Rules Handlers (大群组织者专属) ──
function openOrgJoinModeModal() {
  if (!currentOrg.value) return;
  editOrgNameInput.value = currentOrg.value.name || "";
  editOrgDescInput.value = currentOrg.value.description || "";
  selectedOrgJoinMode.value = (currentOrg.value.join_mode === "free") ? "free" : "invite";
  editOrgInviteCode.value = currentOrg.value.invite_code || "";
  showOrgJoinModeModal.value = true;
}

function handleGenerateRandomOrgCode() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let randomPart = "";
  for (let i = 0; i < 4; i++) {
    randomPart += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  editOrgInviteCode.value = "FD" + randomPart;
  uni.showToast({ title: "已生成新码，请点击保存", icon: "none" });
}

function handleCopyOrgInviteCode() {
  const code = editOrgInviteCode.value.trim() || currentOrg.value?.invite_code;
  if (!code) {
    uni.showToast({ title: "暂无邀请码", icon: "none" });
    return;
  }
  uni.setClipboardData({
    data: code,
    success: () => {
      uni.showToast({ title: "大群邀请码已复制到剪贴板", icon: "success" });
    }
  });
}

async function saveOrgJoinMode() {
  const orgId = currentOrg.value?.id;
  const uid = user.value?.id;
  if (!orgId || !uid) return;

  const trimmedName = editOrgNameInput.value.trim();
  if (!trimmedName) {
    uni.showToast({ title: "大群名称不能为空", icon: "none" });
    return;
  }

  const codeVal = editOrgInviteCode.value.trim().toUpperCase();
  if (selectedOrgJoinMode.value === "invite" && !codeVal) {
    uni.showToast({ title: "需邀请码模式下，邀请码不能为空", icon: "none" });
    return;
  }

  savingOrgJoinMode.value = true;
  try {
    // 1. 更新大群基本信息（名称、简介、邀请码）
    await request(`/api/org/${orgId}`, "PUT", {
      operator_uid: uid,
      name: trimmedName,
      description: editOrgDescInput.value.trim(),
      invite_code: codeVal || undefined
    });

    // 2. 更新入群规则与邀请码
    const payload: any = {
      operator_uid: uid,
      join_mode: selectedOrgJoinMode.value
    };
    if (codeVal) {
      payload.invite_code = codeVal;
    }
    const res = await request(`/api/org/${orgId}/join-mode`, "POST", payload);
    if (currentOrg.value) {
      currentOrg.value.name = trimmedName;
      currentOrg.value.description = editOrgDescInput.value.trim();
      currentOrg.value.join_mode = selectedOrgJoinMode.value;
      if (res?.organization?.invite_code) {
        currentOrg.value.invite_code = res.organization.invite_code;
      }
    }
    uni.showToast({
      title: res?.message || "大群设定与入群规则已更新",
      icon: "success"
    });
    showOrgJoinModeModal.value = false;
    await loadClubData();
  } catch (err: any) {
    uni.showToast({
      title: err?.message || err?.data?.detail || "设置失败，请重试",
      icon: "none"
    });
  } finally {
    savingOrgJoinMode.value = false;
  }
}

function getRuleMode(rule: any): "required" | "optional" | "hidden" {
  if (rule?.mode === "hidden" || rule?.hidden) return "hidden";
  if (rule?.mode === "required" || rule?.required) return "required";
  return "optional";
}

function setOrgRuleMode(idx: number, mode: "required" | "optional" | "hidden") {
  const target = orgFieldRulesList.value[idx];
  if (!target) return;
  orgFieldRulesList.value[idx] = {
    ...target,
    mode,
    required: mode === "required",
    hidden: mode === "hidden"
  };
}

async function openOrgFieldRulesModal() {
  const orgId = currentOrg.value?.id;
  if (!orgId) return;
  try {
    const res = await request(`/api/org/${orgId}/field-rules`, "GET");
    orgFieldRulesList.value = (res?.field_rules || currentOrg.value?.field_rules || []).map((r: any) => ({
      ...r,
      mode: r.hidden || r.mode === "hidden" ? "hidden" : r.required || r.mode === "required" ? "required" : "optional",
      required: (r.hidden || r.mode === "hidden") ? false : Boolean(r.required || r.mode === "required"),
      hidden: Boolean(r.hidden || r.mode === "hidden")
    }));
    showOrgFieldRulesModal.value = true;
  } catch (err: any) {
    uni.showToast({ title: err?.message || "加载准入字段规则失败", icon: "none" });
  }
}

async function saveOrgFieldRules() {
  const orgId = currentOrg.value?.id;
  const uid = user.value?.id;
  if (!orgId || !uid) return;
  savingOrgFieldRules.value = true;
  try {
    const res = await request(`/api/org/${orgId}/field-rules`, "PUT", {
      operator_uid: uid,
      field_rules: orgFieldRulesList.value
    });
    if (currentOrg.value && res?.field_rules) {
      currentOrg.value.field_rules = res.field_rules;
    }
    uni.showToast({ title: "准入字段规则已保存", icon: "success" });
    showOrgFieldRulesModal.value = false;
    await loadClubData();
  } catch (err: any) {
    uni.showToast({
      title: err?.message || err?.data?.detail || "保存失败，请重试",
      icon: "none"
    });
  } finally {
    savingOrgFieldRules.value = false;
  }
}

async function fetchOrgReport(
  pType: "week" | "month" = orgReportPeriodType.value,
  pOffset: number = orgReportPeriodOffset.value
) {
  const orgId = currentOrg.value?.id;
  const uid = user.value?.id;
  if (!orgId || !uid) return;
  loadingOrgReport.value = true;
  try {
    let url = `/api/org/${encodeURIComponent(orgId)}/reports?operator_uid=${encodeURIComponent(uid)}&period_type=${pType}&period_offset=${pOffset}&trail_mode=exclude_pace`;
    if (pOffset === -1) {
      const now = new Date();
      if (pType === "week") {
        const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const target = new Date(d.valueOf());
        const dayNr = (d.getDay() + 6) % 7;
        target.setDate(target.getDate() - dayNr + 3);
        const isoYear = target.getFullYear();
        const firstThursday = target.valueOf();
        target.setMonth(0, 1);
        if (target.getDay() !== 4) {
          target.setMonth(0, 1 + ((4 - target.getDay()) + 7) % 7);
        }
        const weekNum = 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
        url += `&year=${isoYear}&period_index=${weekNum}`;
      } else {
        const prevMonth = now.getMonth() === 0 ? 12 : now.getMonth();
        const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
        url += `&year=${prevYear}&period_index=${prevMonth}`;
      }
    }
    const res = await request(url, "GET");
    orgReportData.value = res;
  } catch (err: any) {
    uni.showToast({ title: err?.message || "加载大群全域报表失败", icon: "none" });
  } finally {
    loadingOrgReport.value = false;
  }
}

async function openOrgReportModal() {
  if (!currentOrg.value?.id) return;
  orgReportTab.value = "clubs_pk";
  showOrgReportModal.value = true;
  await fetchOrgReport(orgReportPeriodType.value, orgReportPeriodOffset.value);
}

async function switchOrgReportPeriod(pType: "week" | "month", pOffset: number) {
  orgReportPeriodType.value = pType;
  orgReportPeriodOffset.value = pOffset;
  await fetchOrgReport(pType, pOffset);
}

function handleCopyOrgWechatReport() {
  const txt = orgReportData.value?.wechat_summary_text;
  if (!txt) return;
  uni.setClipboardData({
    data: txt,
    success: () => {
      uni.showToast({ title: "大群战报已复制，可粘贴发微信群！", icon: "success" });
    },
  });
}

function promptAssignUnaffiliatedMember(memberItem: any) {
  const subClubs = orgReportData.value?.sub_club_rankings || [];
  if (!subClubs.length) {
    uni.showToast({ title: "当前大群暂无下属分跑团", icon: "none" });
    return;
  }
  const itemList = subClubs.slice(0, 6).map((sc: any) => sc.club_name);
  uni.showActionSheet({
    itemList,
    success: async (res) => {
      const targetClub = subClubs[res.tapIndex];
      if (!targetClub || !currentOrg.value?.id || !user.value?.id) return;
      try {
        const apiRes = await request(
          `/api/org/${encodeURIComponent(currentOrg.value.id)}/members/${encodeURIComponent(memberItem.user_id)}/assign-club`,
          "POST",
          {
            operator_uid: user.value.id,
            club_id: targetClub.club_id,
          }
        );
        uni.showToast({ title: apiRes?.message || "已划入分跑团", icon: "success" });
        await fetchOrgReport(orgReportPeriodType.value, orgReportPeriodOffset.value);
      } catch (e: any) {
        uni.showToast({ title: e?.message || "调配失败", icon: "none" });
      }
    },
  });
}

async function fetchOrgEvents() {
  const orgId = currentOrg.value?.id;
  const uid = user.value?.id;
  if (!orgId || !uid) return;
  loadingOrgEvents.value = true;
  try {
    const res = await request(
      `/api/org/${encodeURIComponent(orgId)}/events?operator_uid=${encodeURIComponent(uid)}`,
      "GET"
    );
    orgEventsList.value = res?.org_events || [];
  } catch (err: any) {
    uni.showToast({ title: err?.message || "加载跨跑团活动失败", icon: "none" });
  } finally {
    loadingOrgEvents.value = false;
  }
}

async function openOrgEventsModal() {
  if (!currentOrg.value?.id) return;
  showOrgEventsModal.value = true;
  await fetchOrgEvents();
}

async function handlePublishOrgEvent() {
  const orgId = currentOrg.value?.id;
  const uid = user.value?.id;
  if (!orgId || !uid) return;
  if (!orgEvtTitle.value.trim()) {
    uni.showToast({ title: "请输入跨跑团活动标题", icon: "none" });
    return;
  }
  creatingOrgEvent.value = true;
  try {
    const res = await request(`/api/org/${encodeURIComponent(orgId)}/events`, "POST", {
      operator_uid: uid,
      title: orgEvtTitle.value.trim(),
      event_type: orgEvtType.value,
      meet_time: orgEvtMeetTime.value.trim() || undefined,
      start_date: orgEvtMeetTime.value.trim().split(" ")[0] || undefined,
      location: orgEvtLocation.value.trim() || "集合点",
      target_km: Number(orgEvtTargetKm.value) || 15,
      scope_club_ids: "all",
    });
    uni.showToast({ title: res?.message || "跨跑团活动已发布", icon: "success" });
    await fetchOrgEvents();
    await loadClubData();
  } catch (err: any) {
    uni.showToast({ title: err?.message || "发布失败", icon: "none" });
  } finally {
    creatingOrgEvent.value = false;
  }
}

// ── Club Periodic Report Handlers ──
function openReportModal() {
  if (!currentClub.value) {
    uni.showToast({ title: "请先选择跑团", icon: "none" });
    return;
  }
  reportPeriodType.value = "week";
  reportPeriodOffset.value = 0;
  reportTrailMode.value = "include";
  showReportModal.value = true;
  trackModal("club_report", "打开跑团周期战报弹窗", "open", { club_id: currentClub.value.id });
  fetchClubReport();
}

async function fetchClubReport() {
  const clubId = currentClub.value?.id;
  const uid = user.value?.id;
  if (!clubId || !uid) return;

  loadingReport.value = true;
  try {
    let url = `/api/team/${clubId}/reports?operator_uid=${uid}&period_type=${reportPeriodType.value}&period_offset=${reportPeriodOffset.value}&trail_mode=${reportTrailMode.value}`;
    
    if (reportPeriodOffset.value === -1) {
      const now = new Date();
      if (reportPeriodType.value === "week") {
        // Compute last week's ISO week
        const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const target = new Date(d.valueOf());
        const dayNr = (d.getDay() + 6) % 7;
        target.setDate(target.getDate() - dayNr + 3);
        const isoYear = target.getFullYear();
        const firstThursday = target.valueOf();
        target.setMonth(0, 1);
        if (target.getDay() !== 4) {
          target.setMonth(0, 1 + ((4 - target.getDay()) + 7) % 7);
        }
        const weekNum = 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
        url += `&year=${isoYear}&period_index=${weekNum}`;
      } else {
        // Last month
        const prevMonth = now.getMonth() === 0 ? 12 : now.getMonth();
        const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
        url += `&year=${prevYear}&period_index=${prevMonth}`;
      }
    }

    const res = await request(url);
    reportData.value = res;
  } catch (err: any) {
    console.error("fetchClubReport error:", err);
    uni.showToast({ title: err?.message || "获取战报失败", icon: "none" });
  } finally {
    loadingReport.value = false;
  }
}

function handleSwitchReportPeriod(type: "week" | "month") {
  if (reportPeriodType.value === type) return;
  reportPeriodType.value = type;
  reportPeriodOffset.value = 0;
  fetchClubReport();
}

function handleSwitchReportOffset(offset: number) {
  if (reportPeriodOffset.value === offset) return;
  reportPeriodOffset.value = offset;
  fetchClubReport();
}

function handleSwitchReportTrailMode(mode: "include" | "exclude_pace" | "exclude_all") {
  if (reportTrailMode.value === mode) return;
  reportTrailMode.value = mode;
  fetchClubReport();
}

function handleCopyReportForwardText() {
  const text = reportData.value?.forward_text;
  if (!text) {
    uni.showToast({ title: "战报内容为空", icon: "none" });
    return;
  }
  trackClick("club_report_copy_text", "复制跑团战报文案", { period_type: reportPeriodType.value });
  uni.setClipboardData({
    data: text,
    success: () => {
      uni.showToast({ title: "战报已复制，可直接粘贴发群！", icon: "success", duration: 2500 });
    }
  });
}

function handleDownloadReportFile() {
  const clubId = currentClub.value?.id;
  const uid = user.value?.id;
  if (!clubId || !uid) return;

  const url = `https://rgm.vanpower.net/api/team/${clubId}/reports/export?operator_uid=${uid}&period_type=${reportPeriodType.value}&period_offset=${reportPeriodOffset.value}&trail_mode=${reportTrailMode.value}`;
  
  // #ifdef MP-WEIXIN
  uni.showLoading({ title: "正在生成文件..." });
  uni.downloadFile({
    url: url,
    success: (res) => {
      uni.hideLoading();
      if (res.statusCode === 200) {
        uni.openDocument({
          filePath: res.tempFilePath,
          fileType: "txt",
          showMenu: true,
          success: () => {
            uni.showToast({ title: "战报已打开，右上角可转发或保存", icon: "none", duration: 3000 });
          },
          fail: (openErr) => {
            console.warn("openDocument fail:", openErr);
            handleCopyReportForwardText();
          }
        });
      } else {
        uni.showToast({ title: "下载失败", icon: "none" });
      }
    },
    fail: (dlErr) => {
      uni.hideLoading();
      console.warn("downloadFile fail:", dlErr);
      uni.showToast({ title: "下载失败，请直接点击一键复制", icon: "none" });
    }
  });
  // #endif

  // #ifndef MP-WEIXIN
  if (typeof window !== "undefined") {
    window.open(url, "_blank");
  } else {
    handleCopyReportForwardText();
  }
  // #endif
}

function drawRoundedRect(ctx: any, x: number, y: number, width: number, height: number, radius: number, fillStyle?: string, strokeStyle?: string) {
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.arcTo(x + width, y, x + width, y + radius, radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.arcTo(x + width, y + height, x + width - radius, y + height, radius);
  ctx.lineTo(x + radius, y + height);
  ctx.arcTo(x, y + height, x, y + height - radius, radius);
  ctx.lineTo(x, y + radius);
  ctx.arcTo(x, y, x + radius, y, radius);
  ctx.closePath();
  if (fillStyle) {
    ctx.setFillStyle(fillStyle);
    ctx.fill();
  }
  if (strokeStyle) {
    ctx.setStrokeStyle(strokeStyle);
    ctx.stroke();
  }
  ctx.restore();
}

function drawWrappedText(ctx: any, text: string, x: number, y: number, maxWidth: number, lineHeight: number, maxLines: number = 5) {
  let line = "";
  let lineCount = 0;
  for (let i = 0; i < text.length; i++) {
    const testLine = line + text[i];
    if (ctx.measureText(testLine).width > maxWidth && i > 0) {
      ctx.fillText(line, x, y);
      line = text[i];
      y += lineHeight;
      lineCount++;
      if (lineCount >= maxLines - 1) {
        const remaining = text.substring(i);
        let lastLine = "";
        const suffix = text.startsWith("“") ? "…”" : "...";
        for (let j = 0; j < remaining.length; j++) {
          if (ctx.measureText(lastLine + remaining[j] + suffix).width > maxWidth) {
            break;
          }
          lastLine += remaining[j];
        }
        ctx.fillText(lastLine + suffix, x, y);
        return y + lineHeight;
      }
    } else {
      line = testLine;
    }
  }
  ctx.fillText(line, x, y);
  return y + lineHeight;
}

function writeReportQrBase64ToLocalFile(base64Str: string): Promise<string | null> {
  return new Promise((resolve) => {
    try {
      // #ifdef MP-WEIXIN
      const wxObj = (globalThis as any).wx;
      const fs = wxObj?.getFileSystemManager?.();
      const userDataPath = wxObj?.env?.USER_DATA_PATH;
      if (fs && userDataPath && base64Str) {
        const cleanBase64 = base64Str.replace(/^data:image\/\w+;base64,/, "");
        const filePath = `${userDataPath}/club_rep_qr_${Date.now()}.jpg`;
        fs.writeFile({
          filePath,
          data: cleanBase64,
          encoding: "base64",
          success: () => resolve(filePath),
          fail: () => resolve(null),
        });
        return;
      }
      // #endif
      resolve(null);
    } catch {
      resolve(null);
    }
  });
}

function generatePosterImage(): Promise<string> {
  return new Promise(async (resolve, reject) => {
    if (!reportData.value) {
      reject(new Error("战报数据为空"));
      return;
    }

    const rep = reportData.value;
    let qrLocalPath: string | null = null;
    if (rep.qrcode_base64) {
      qrLocalPath = await writeReportQrBase64ToLocalFile(rep.qrcode_base64);
    }

    const ctx = uni.createCanvasContext("reportPosterCanvas");

    const W = 750;
    const H = 1360;
    const isLight = currentTheme.value === "volt";

    // 1. Background
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    if (isLight) {
      bgGrad.addColorStop(0, "#f8fafc");
      bgGrad.addColorStop(0.5, "#ffffff");
      bgGrad.addColorStop(1, "#f1f5f9");
    } else {
      bgGrad.addColorStop(0, "#0e1017");
      bgGrad.addColorStop(0.5, "#131620");
      bgGrad.addColorStop(1, "#0a0b10");
    }
    ctx.setFillStyle(bgGrad);
    ctx.fillRect(0, 0, W, H);

    // Outer decorative border
    drawRoundedRect(
      ctx,
      16,
      16,
      W - 32,
      H - 32,
      24,
      undefined,
      isLight ? "#E2E8F0" : "rgba(255, 215, 0, 0.25)"
    );

    // 2. Header Area
    drawRoundedRect(
      ctx,
      40,
      42,
      190,
      42,
      21,
      isLight ? "#FFF5EE" : "rgba(255, 215, 0, 0.15)",
      isLight ? "rgba(252, 76, 2, 0.32)" : "rgba(255, 215, 0, 0.4)"
    );
    ctx.setFontSize(20);
    ctx.setFillStyle(isLight ? "#C23800" : "#ffd700");
    ctx.fillText("👑 跑团专属战报", 52, 71);

    if (rep.trail_mode && rep.trail_mode !== "include") {
      const trailTxt = rep.trail_mode === "exclude_all" ? "🛣️ 已去除越野跑量与配速" : "⏱️ 均速已去除越野跑";
      drawRoundedRect(
        ctx,
        244,
        42,
        240,
        42,
        21,
        isLight ? "rgba(16, 185, 129, 0.12)" : "rgba(16, 185, 129, 0.16)",
        isLight ? "rgba(5, 150, 105, 0.4)" : "rgba(16, 185, 129, 0.45)"
      );
      ctx.setFontSize(18);
      ctx.setFillStyle(isLight ? "#059669" : "#34d399");
      ctx.fillText(trailTxt, 258, 70);
    }

    // Club Name
    ctx.setFontSize(36);
    ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
    ctx.fillText(rep.club_name || "跑团战报", 40, 130);

    // Period Label & Date range
    ctx.setFontSize(22);
    ctx.setFillStyle(isLight ? "#475569" : "#ffd700");
    ctx.fillText(`${rep.period_label} · ${rep.date_range_str}`, 40, 172);

    // Decorative separator line
    ctx.beginPath();
    ctx.moveTo(40, 195);
    ctx.lineTo(W - 40, 195);
    ctx.setStrokeStyle(isLight ? "rgba(15, 23, 42, 0.08)" : "rgba(255, 255, 255, 0.12)");
    ctx.stroke();

    // 3. Hero Total Distance Box
    drawRoundedRect(
      ctx,
      40,
      215,
      W - 80,
      155,
      20,
      isLight ? "#F8FAFC" : "#181b26",
      isLight ? "#E2E8F0" : "rgba(252, 76, 2, 0.35)"
    );
    ctx.setFontSize(22);
    ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
    ctx.fillText("全团累计奔跑总里程", 64, 252);

    ctx.setFontSize(72);
    ctx.setFillStyle("#fc4c02");
    ctx.fillText(`${rep.total_distance_km}`, 64, 326);

    const kmWidth = ctx.measureText(`${rep.total_distance_km}`).width;
    ctx.setFontSize(30);
    ctx.setFillStyle(isLight ? "#0F172A" : "#9ca3af");
    ctx.fillText("KM", 64 + kmWidth + 12, 324);

    ctx.setFontSize(18);
    ctx.setFillStyle(isLight ? "#64748B" : "#71717a");
    ctx.fillText("汇聚全员热血汗水 · 每一步都在突破极限", 64, 355);

    // 4. 4-Metrics Grid
    const gW = (W - 80 - 18) / 2;
    const gH = 92;
    const cellBg = isLight ? "#F8FAFC" : "#151722";
    const cellBorder = isLight ? "#e2e8f0" : "rgba(255, 255, 255, 0.08)";
    const cellLblColor = isLight ? "#475569" : "#9ca3af";
    const cellValColor = isLight ? "#0F172A" : "#ffffff";

    // Item 1: 出勤率
    drawRoundedRect(ctx, 40, 390, gW, gH, 16, cellBg, cellBorder);
    ctx.setFontSize(20);
    ctx.setFillStyle(cellLblColor);
    ctx.fillText("团员出勤率", 56, 422);
    ctx.setFontSize(30);
    ctx.setFillStyle(cellValColor);
    ctx.fillText(`${rep.attendance_rate_pct}%`, 56, 462);
    ctx.setFontSize(18);
    ctx.setFillStyle(isLight ? "#64748b" : "#6b7280");
    ctx.fillText(`(${rep.active_members_count}/${rep.total_members_count}人)`, 160, 460);

    // Item 2: 全团均速
    drawRoundedRect(ctx, 40 + gW + 18, 390, gW, gH, 16, cellBg, cellBorder);
    ctx.setFontSize(20);
    ctx.setFillStyle(cellLblColor);
    ctx.fillText("全团平均配速", 56 + gW + 18, 422);
    ctx.setFontSize(30);
    ctx.setFillStyle(cellValColor);
    ctx.fillText(`${rep.avg_pace_str}`, 56 + gW + 18, 462);

    // Item 3: 累计爬升
    drawRoundedRect(ctx, 40, 498, gW, gH, 16, cellBg, cellBorder);
    ctx.setFontSize(20);
    ctx.setFillStyle(cellLblColor);
    ctx.fillText("累计爬升克服", 56, 530);
    ctx.setFontSize(30);
    ctx.setFillStyle(cellValColor);
    ctx.fillText(`+${rep.total_elevation_gain_m}m`, 56, 570);

    // Item 4: 打卡人次
    drawRoundedRect(ctx, 40 + gW + 18, 498, gW, gH, 16, cellBg, cellBorder);
    ctx.setFontSize(20);
    ctx.setFillStyle(cellLblColor);
    ctx.fillText("累计打卡总人次", 56 + gW + 18, 530);
    ctx.setFontSize(30);
    ctx.setFillStyle(cellValColor);
    ctx.fillText(`${rep.total_activities_count} 次`, 56 + gW + 18, 570);

    // 5. 🏆 Top 3 Podium
    drawRoundedRect(
      ctx,
      40,
      606,
      W - 80,
      235,
      20,
      isLight ? "#f8fafc" : "#151722",
      isLight ? "#E2E8F0" : "rgba(255, 215, 0, 0.3)"
    );
    ctx.setFontSize(24);
    ctx.setFillStyle(isLight ? "#0F172A" : "#ffd700");
    ctx.fillText("🏆 荣誉榜单 Top 3", 60, 642);

    const podium = rep.podium || [];
    const medals = ["🥇 冠军", "🥈 亚军", "🥉 季军"];
    const medalBgs = isLight
      ? ["#FFFFFF", "#FFFFFF", "#FFFFFF"]
      : ["rgba(255, 215, 0, 0.12)", "rgba(192, 192, 192, 0.10)", "rgba(205, 127, 50, 0.10)"];
    const medalStrokes = isLight
      ? ["#E2E8F0", "#E2E8F0", "#E2E8F0"]
      : ["rgba(255, 215, 0, 0.35)", "rgba(192, 192, 192, 0.3)", "rgba(205, 127, 50, 0.3)"];

    for (let i = 0; i < 3; i++) {
      const pY = 660 + i * 55;
      if (podium[i]) {
        drawRoundedRect(ctx, 60, pY, W - 120, 48, 12, medalBgs[i], medalStrokes[i]);
        ctx.setFontSize(22);
        ctx.setFillStyle(isLight ? "#C23800" : "#ffd700");
        ctx.fillText(medals[i], 76, pY + 32);

        ctx.setFontSize(22);
        ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
        ctx.fillText(podium[i].display_name || "跑者", 185, pY + 32);

        ctx.setFontSize(22);
        ctx.setFillStyle("#fc4c02");
        ctx.fillText(`${podium[i].distance_km} km`, W - 250, pY + 32);

        ctx.setFontSize(18);
        ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
        ctx.fillText(podium[i].avg_pace_str || "—", W - 145, pY + 32);
      } else {
        ctx.setFontSize(18);
        ctx.setFillStyle(isLight ? "#94a3b8" : "#52525b");
        ctx.fillText(`席位待定`, 76, pY + 32);
      }
    }

    // 6. 🌟 Highlights Row
    const hY = 858;
    const hW = (W - 80 - 18) / 2;
    const hlBg = isLight ? "#F8FAFC" : "#151722";
    const hlBorder = isLight ? "#E2E8F0" : "rgba(56, 189, 248, 0.25)";
    const hlTagColor = isLight ? "#C23800" : "#38bdf8";
    if (rep.hardcore_runner) {
      drawRoundedRect(ctx, 40, hY, hW, 82, 14, hlBg, hlBorder);
      ctx.setFontSize(18);
      ctx.setFillStyle(hlTagColor);
      ctx.fillText("🌟 毅力先锋", 54, hY + 28);
      ctx.setFontSize(20);
      ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
      ctx.fillText(`${rep.hardcore_runner.display_name}`, 54, hY + 54);
      ctx.setFontSize(16);
      ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
      ctx.fillText(`打卡 ${rep.hardcore_runner.runs_count} 次 · ${rep.hardcore_runner.distance_km}km`, 54, hY + 74);
    }
    if (rep.longest_run) {
      drawRoundedRect(ctx, 40 + hW + 18, hY, hW, 82, 14, hlBg, hlBorder);
      ctx.setFontSize(18);
      ctx.setFillStyle(hlTagColor);
      ctx.fillText("🚀 最长突破", 54 + hW + 18, hY + 28);
      ctx.setFontSize(20);
      ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
      ctx.fillText(`${rep.longest_run.runner_name}`, 54 + hW + 18, hY + 54);
      ctx.setFontSize(16);
      ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
      ctx.fillText(`单次 ${rep.longest_run.distance_km}km · ${rep.longest_run.avg_pace_str}`, 54 + hW + 18, hY + 74);
    }

    // 7. 💡 Renato Canova Coach Critique Box
    const cY = 955;
    drawRoundedRect(
      ctx,
      40,
      cY,
      W - 80,
      225,
      18,
      isLight ? "#F8FAFC" : "#181624",
      isLight ? "#E2E8F0" : "rgba(191, 90, 242, 0.35)"
    );
    ctx.setFontSize(22);
    ctx.setFillStyle(isLight ? "#0F172A" : "#bf5af2");
    ctx.fillText("💡 Renato Canova 科学耐力团队复盘", 58, cY + 34);

    ctx.setFontSize(17);
    ctx.setFillStyle(isLight ? "#334155" : "#d1d5db");
    drawWrappedText(ctx, `“${rep.canova_critique}”`, 58, cY + 68, W - 116, 26, 5);

    // 8. Bottom Brand Stamp
    const fY = 1205;
    ctx.beginPath();
    ctx.moveTo(40, fY);
    ctx.lineTo(W - 40, fY);
    ctx.setStrokeStyle(isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.1)");
    ctx.stroke();

    ctx.setFontSize(22);
    ctx.setFillStyle(isLight ? "#111317" : "#ffffff");
    ctx.fillText("万跑跑团助手", 40, fY + 42);

    ctx.setFontSize(16);
    ctx.setFillStyle(isLight ? "#4b5667" : "#71717a");
    ctx.fillText("微信扫码进入万跑跑团助手小程序 · 科学耐力训练与跑团系统", 40, fY + 72);

    if (qrLocalPath) {
      drawRoundedRect(ctx, W - 134, fY + 14, 94, 94, 14, "#ffffff", isLight ? "#e2e8f0" : undefined);
      ctx.drawImage(qrLocalPath, W - 128, fY + 20, 82, 82);
    } else {
      drawRoundedRect(
        ctx,
        W - 160,
        fY + 20,
        120,
        48,
        12,
        isLight ? "rgba(245, 158, 11, 0.14)" : "rgba(255, 215, 0, 0.15)",
        isLight ? "rgba(217, 119, 6, 0.4)" : "rgba(255, 215, 0, 0.4)"
      );
      ctx.setFontSize(18);
      ctx.setFillStyle(isLight ? "#b45309" : "#ffd700");
      ctx.fillText("官方战报", W - 138, fY + 50);
    }

    // Draw and export
    ctx.draw(false, () => {
      setTimeout(() => {
        uni.canvasToTempFilePath({
          canvasId: "reportPosterCanvas",
          x: 0,
          y: 0,
          width: W,
          height: H,
          destWidth: W * 2, // 2x retina
          destHeight: H * 2,
          success: (res) => {
            resolve(res.tempFilePath);
          },
          fail: (err) => {
            reject(err);
          }
        });
      }, 250);
    });
  });
}

async function handlePreviewPosterImage() {
  uni.showLoading({ title: "正在生成战报海报..." });
  try {
    const tempPath = await generatePosterImage();
    uni.hideLoading();
    // #ifdef MP-WEIXIN
    const wxObj = (globalThis as any).wx;
    if (wxObj && typeof wxObj.showShareImageMenu === "function") {
      wxObj.showShareImageMenu({
        path: tempPath,
        fail: () => {
          uni.previewImage({ current: tempPath, urls: [tempPath] });
        },
      });
      return;
    }
    // #endif
    uni.previewImage({
      current: tempPath,
      urls: [tempPath]
    });
    uni.showToast({ title: "长按图片可直接转发朋友圈或微信群", icon: "none", duration: 3500 });
  } catch (err: any) {
    uni.hideLoading();
    console.error("handlePreviewPosterImage fail:", err);
    uni.showToast({ title: "渲染海报失败，请重试", icon: "none" });
  }
}

async function handleSavePosterToAlbum() {
  uni.showLoading({ title: "正在生成并保存..." });
  try {
    const tempPath = await generatePosterImage();
    uni.saveImageToPhotosAlbum({
      filePath: tempPath,
      success: () => {
        uni.hideLoading();
        uni.showToast({ title: "海报已成功保存到手机相册！", icon: "success", duration: 2500 });
      },
      fail: (saveErr) => {
        uni.hideLoading();
        console.warn("saveImageToPhotosAlbum fail:", saveErr);
        uni.previewImage({ current: tempPath, urls: [tempPath] });
        uni.showToast({ title: "长按图片即可直接保存到相册", icon: "none", duration: 3500 });
      }
    });
  } catch (err: any) {
    uni.hideLoading();
    console.error("handleSavePosterToAlbum fail:", err);
    uni.showToast({ title: "保存失败，请重试", icon: "none" });
  }
}

function generateTablePosterImage(): Promise<string> {
  return new Promise(async (resolve, reject) => {
    if (!reportData.value) {
      reject(new Error("战报数据为空"));
      return;
    }

    const rep = reportData.value;
    let qrLocalPath: string | null = null;
    if (rep.qrcode_base64) {
      qrLocalPath = await writeReportQrBase64ToLocalFile(rep.qrcode_base64);
    }
    const list: any[] = (filteredSortedMemberList.value && filteredSortedMemberList.value.length > 0)
      ? filteredSortedMemberList.value
      : (rep.member_progress_list || []);

    const W = 750;
    const startY = 415;
    const rH = 74;
    const footerH = 185;
    const dynamicH = Math.max(startY + Math.max(list.length, 1) * rH + footerH, 860);

    // Small delay to ensure uni-app / WeChat canvas view has updated its height in DOM
    await new Promise((r) => setTimeout(r, 80));

    const ctx = uni.createCanvasContext("reportTablePosterCanvas");
    const H = dynamicH;
    const isLight = currentTheme.value === "volt";

    // 1. Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    if (isLight) {
      bgGrad.addColorStop(0, "#f8fafc");
      bgGrad.addColorStop(0.3, "#ffffff");
      bgGrad.addColorStop(0.7, "#f8fafc");
      bgGrad.addColorStop(1, "#f1f5f9");
    } else {
      bgGrad.addColorStop(0, "#0c0e15");
      bgGrad.addColorStop(0.3, "#11141e");
      bgGrad.addColorStop(0.7, "#141724");
      bgGrad.addColorStop(1, "#0a0b10");
    }
    ctx.setFillStyle(bgGrad);
    ctx.fillRect(0, 0, W, H);

    // Outer decorative border
    drawRoundedRect(
      ctx,
      16,
      16,
      W - 32,
      H - 32,
      24,
      undefined,
      isLight ? "#E2E8F0" : "rgba(255, 215, 0, 0.25)"
    );

    // 2. Header Area
    // Pill tag
    drawRoundedRect(
      ctx,
      40,
      42,
      320,
      42,
      21,
      isLight ? "#FFF5EE" : "rgba(255, 215, 0, 0.15)",
      isLight ? "rgba(252, 76, 2, 0.32)" : "rgba(255, 215, 0, 0.4)"
    );
    ctx.setFontSize(20);
    ctx.setFillStyle(isLight ? "#C23800" : "#ffd700");
    ctx.fillText("👑 跑团专属战报 · 全员达成榜", 52, 71);

    if (rep.trail_mode && rep.trail_mode !== "include") {
      const trailTxt = rep.trail_mode === "exclude_all" ? "🛣️ 已去除越野跑量与配速" : "⏱️ 均速已去除越野跑";
      drawRoundedRect(
        ctx,
        374,
        42,
        240,
        42,
        21,
        isLight ? "rgba(16, 185, 129, 0.12)" : "rgba(16, 185, 129, 0.16)",
        isLight ? "rgba(5, 150, 105, 0.4)" : "rgba(16, 185, 129, 0.45)"
      );
      ctx.setFontSize(18);
      ctx.setFillStyle(isLight ? "#059669" : "#34d399");
      ctx.fillText(trailTxt, 388, 70);
    }

    // Club Name
    ctx.setFontSize(36);
    ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
    ctx.fillText(rep.club_name || "跑团战报", 40, 130);

    // Period Label & Date range
    ctx.setFontSize(22);
    ctx.setFillStyle(isLight ? "#475569" : "#ffd700");
    ctx.fillText(`${rep.period_label} · ${rep.date_range_str}`, 40, 172);

    // Decorative separator line
    ctx.beginPath();
    ctx.moveTo(40, 195);
    ctx.lineTo(W - 40, 195);
    ctx.setStrokeStyle(isLight ? "rgba(15, 23, 42, 0.08)" : "rgba(255, 255, 255, 0.12)");
    ctx.stroke();

    // 3. Team Goal & Progress Overview Card
    drawRoundedRect(
      ctx,
      40,
      215,
      W - 80,
      155,
      20,
      isLight ? "#F8FAFC" : "#181b26",
      isLight ? "#E2E8F0" : "rgba(252, 76, 2, 0.35)"
    );

    const ovLblColor = isLight ? "#4b5667" : "#9ca3af";
    const ovDivColor = isLight ? "rgba(15, 23, 42, 0.12)" : "rgba(255, 255, 255, 0.1)";

    // Stat 1: 团队目标跑量
    ctx.setFontSize(20);
    ctx.setFillStyle(ovLblColor);
    ctx.fillText("团队目标跑量", 65, 252);
    ctx.setFontSize(32);
    ctx.setFillStyle(isLight ? "#111317" : "#ffffff");
    ctx.fillText(`${rep.total_target_km || 0}`, 65, 294);
    const tw1 = ctx.measureText(`${rep.total_target_km || 0}`).width;
    ctx.setFontSize(18);
    ctx.setFillStyle(ovLblColor);
    ctx.fillText("KM", 65 + tw1 + 6, 292);

    // Divider 1
    ctx.beginPath();
    ctx.moveTo(270, 235);
    ctx.lineTo(270, 295);
    ctx.setStrokeStyle(ovDivColor);
    ctx.stroke();

    // Stat 2: 实际累计奔跑
    ctx.setFontSize(20);
    ctx.setFillStyle(ovLblColor);
    ctx.fillText("实际累计奔跑", 290, 252);
    ctx.setFontSize(32);
    ctx.setFillStyle(isLight ? "#ea580c" : "#fc4c02");
    ctx.fillText(`${rep.total_distance_km || 0}`, 290, 294);
    const tw2 = ctx.measureText(`${rep.total_distance_km || 0}`).width;
    ctx.setFontSize(18);
    ctx.setFillStyle(ovLblColor);
    ctx.fillText("KM", 290 + tw2 + 6, 292);

    // Divider 2
    ctx.beginPath();
    ctx.moveTo(490, 235);
    ctx.lineTo(490, 295);
    ctx.setStrokeStyle(ovDivColor);
    ctx.stroke();

    // Stat 3: 全团达成率
    ctx.setFontSize(20);
    ctx.setFillStyle(ovLblColor);
    ctx.fillText("全团达成率", 510, 252);
    ctx.setFontSize(32);
    ctx.setFillStyle(isLight ? "#16a34a" : "#22c55e");
    ctx.fillText(`${rep.team_completion_rate || 0}%`, 510, 294);

    // Progress bar inside overview card
    const teamPct = Math.min(rep.team_completion_rate || 0, 100);
    const maxBarW = 380;
    drawRoundedRect(ctx, 65, 326, maxBarW, 14, 7, isLight ? "rgba(15, 23, 42, 0.10)" : "rgba(255, 255, 255, 0.08)");
    if (teamPct > 0) {
      drawRoundedRect(ctx, 65, 326, Math.max((teamPct / 100) * maxBarW, 14), 14, 7, "#22c55e");
    }
    ctx.setFontSize(17);
    ctx.setFillStyle(isLight ? "#92400e" : "#ffd700");
    ctx.fillText(`达标人数：${rep.achieved_members_count || 0} / ${rep.total_members_count || 0} 人`, 465, 338);

    // 4. Table Header Row
    const thY = 385;
    drawRoundedRect(
      ctx,
      40,
      thY,
      W - 80,
      40,
      10,
      isLight ? "#f1f5f9" : "#191c28",
      isLight ? "#e2e8f0" : "rgba(255, 255, 255, 0.08)"
    );
    ctx.setFontSize(18);
    ctx.setFillStyle(isLight ? "#4b5667" : "#9ca3af");
    ctx.fillText("序号 · 团员", 58, thY + 26);
    ctx.fillText("目标跑量", 325, thY + 26);
    ctx.fillText("实际跑量", 430, thY + 26);
    ctx.fillText("完成度 · 状态", 545, thY + 26);

    // 5. Table Rows
    const isPast = reportPeriodOffset.value === -1 || rep.is_past_period;

    if (list.length === 0) {
      drawRoundedRect(ctx, 40, startY + 25, W - 80, 60, 10, isLight ? "#f8fafc" : "#14161f");
      ctx.setFontSize(20);
      ctx.setFillStyle(isLight ? "#64748b" : "#71717a");
      ctx.fillText("暂无符合条件的成员记录", 270, startY + 62);
    } else {
      list.forEach((m: any, idx: number) => {
        const rowY = startY + 20 + idx * rH;

        // Row background
        const rowBg = m.is_achieved
          ? isLight
            ? "rgba(34, 197, 94, 0.10)"
            : "rgba(34, 197, 94, 0.06)"
          : idx % 2 === 0
          ? isLight
            ? "#ffffff"
            : "#131620"
          : isLight
          ? "#f8fafc"
          : "#161924";
        const rowBorder = m.is_achieved
          ? isLight
            ? "rgba(22, 163, 74, 0.32)"
            : "rgba(34, 197, 94, 0.22)"
          : isLight
          ? "#e2e8f0"
          : "rgba(255, 255, 255, 0.05)";
        drawRoundedRect(ctx, 40, rowY, W - 80, 66, 12, rowBg, rowBorder);

        // Rank
        if (idx === 0) {
          ctx.setFontSize(22);
          ctx.setFillStyle("#ffd700");
          ctx.fillText("🥇", 54, rowY + 41);
        } else if (idx === 1) {
          ctx.setFontSize(22);
          ctx.setFillStyle("#e2e8f0");
          ctx.fillText("🥈", 54, rowY + 41);
        } else if (idx === 2) {
          ctx.setFontSize(22);
          ctx.setFillStyle("#f97316");
          ctx.fillText("🥉", 54, rowY + 41);
        } else {
          drawRoundedRect(ctx, 52, rowY + 20, 26, 26, 13, isLight ? "#e2e8f0" : "rgba(255, 255, 255, 0.06)");
          ctx.setFontSize(16);
          ctx.setFillStyle(isLight ? "#4b5667" : "#9ca3af");
          const rankStr = `${idx + 1}`;
          const rw = ctx.measureText(rankStr).width;
          ctx.fillText(rankStr, 52 + (26 - rw) / 2, rowY + 39);
        }

        // Circular Avatar Badge with Initial
        const avCenterX = 100;
        const avCenterY = rowY + 33;
        const avRadius = 18;
        const avBg = m.is_achieved ? "#15803d" : (idx < 3 ? "#854d0e" : "#374151");
        ctx.save();
        ctx.beginPath();
        ctx.arc(avCenterX, avCenterY, avRadius, 0, Math.PI * 2);
        ctx.setFillStyle(avBg);
        ctx.fill();
        ctx.restore();

        // Initial char
        const rawName = (m.display_name || "跑友").trim();
        const initial = rawName.charAt(0).toUpperCase();
        ctx.setFontSize(17);
        ctx.setFillStyle("#ffffff");
        const iw = ctx.measureText(initial).width;
        ctx.fillText(initial, avCenterX - iw / 2, avCenterY + 6);

        // Member Name
        let nameText = rawName;
        if (nameText.length > 5) {
          nameText = nameText.slice(0, 4) + "…";
        }
        ctx.setFontSize(19);
        ctx.setFillStyle(isLight ? "#111317" : "#ffffff");
        ctx.fillText(nameText, 126, rowY + 30);

        // Role Badge if owner/coach
        const nw = ctx.measureText(nameText).width;
        if (m.role === 'owner') {
          drawRoundedRect(
            ctx,
            126 + nw + 6,
            rowY + 16,
            38,
            18,
            5,
            isLight ? "rgba(245, 158, 11, 0.16)" : "rgba(255, 215, 0, 0.2)",
            isLight ? "rgba(217, 119, 6, 0.45)" : "rgba(255, 215, 0, 0.5)"
          );
          ctx.setFontSize(12);
          ctx.setFillStyle(isLight ? "#b45309" : "#ffd700");
          ctx.fillText("团长", 126 + nw + 11, rowY + 30);
        } else if (m.role === 'coach') {
          drawRoundedRect(
            ctx,
            126 + nw + 6,
            rowY + 16,
            38,
            18,
            5,
            isLight ? "rgba(2, 132, 199, 0.14)" : "rgba(96, 165, 250, 0.2)",
            isLight ? "rgba(2, 132, 199, 0.45)" : "rgba(96, 165, 250, 0.5)"
          );
          ctx.setFontSize(12);
          ctx.setFillStyle(isLight ? "#0369a1" : "#60a5fa");
          ctx.fillText("教练", 126 + nw + 11, rowY + 30);
        }

        // Subtext: runs count
        ctx.setFontSize(14);
        ctx.setFillStyle(isLight ? "#64748b" : "#71717a");
        ctx.fillText(m.runs_count > 0 ? `${m.runs_count}次打卡` : "未打卡", 126, rowY + 52);

        // Col 2: Target km
        ctx.setFontSize(20);
        ctx.setFillStyle(isLight ? "#334155" : "#d1d5db");
        ctx.fillText(`${m.target_km}`, 325, rowY + 41);
        const tkw = ctx.measureText(`${m.target_km}`).width;
        ctx.setFontSize(13);
        ctx.setFillStyle(isLight ? "#64748b" : "#71717a");
        ctx.fillText("km", 325 + tkw + 3, rowY + 41);

        // Col 3: Actual km
        ctx.setFontSize(22);
        ctx.setFillStyle(isLight ? "#ea580c" : "#fc4c02");
        ctx.fillText(`${m.distance_km}`, 430, rowY + 41);
        const akw = ctx.measureText(`${m.distance_km}`).width;
        ctx.setFontSize(13);
        ctx.setFillStyle(isLight ? "#64748b" : "#71717a");
        ctx.fillText("km", 430 + akw + 3, rowY + 41);

        // Col 4: Completion Rate + Status Pill + Mini progress bar
        const isDone = !!m.is_achieved;
        const statusText = isDone ? "已达标" : (isPast ? "未达标" : "进行中");
        const statusColor = isDone
          ? isLight ? "#16a34a" : "#22c55e"
          : isPast
          ? isLight ? "#dc2626" : "#ef4444"
          : isLight ? "#d97706" : "#f59e0b";
        const statusBg = isDone ? "rgba(34, 197, 94, 0.16)" : (isPast ? "rgba(239, 68, 68, 0.16)" : "rgba(245, 158, 11, 0.16)");
        const statusBorder = isDone ? "rgba(34, 197, 94, 0.4)" : (isPast ? "rgba(239, 68, 68, 0.4)" : "rgba(245, 158, 11, 0.4)");

        // Rate text
        ctx.setFontSize(20);
        ctx.setFillStyle(statusColor);
        ctx.fillText(`${m.completion_rate}%`, 545, rowY + 30);

        // Status pill
        drawRoundedRect(ctx, 624, rowY + 14, 64, 20, 6, statusBg, statusBorder);
        ctx.setFontSize(12);
        ctx.setFillStyle(statusColor);
        ctx.fillText(statusText, 630, rowY + 28);

        // Mini bar
        const miniBarMaxW = 143;
        const fillW = Math.max((Math.min(m.completion_rate || 0, 100) / 100) * miniBarMaxW, 0);
        drawRoundedRect(ctx, 545, rowY + 44, miniBarMaxW, 6, 3, isLight ? "#e2e8f0" : "rgba(255, 255, 255, 0.08)");
        if (fillW > 0) {
          drawRoundedRect(ctx, 545, rowY + 44, Math.max(fillW, 6), 6, 3, statusColor);
        }
      });
    }

    // 6. Bottom Brand Stamp
    const fY = startY + 20 + Math.max(list.length, 1) * rH + 15;
    ctx.beginPath();
    ctx.moveTo(40, fY);
    ctx.lineTo(W - 40, fY);
    ctx.setStrokeStyle(isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.1)");
    ctx.stroke();

    ctx.setFontSize(22);
    ctx.setFillStyle(isLight ? "#111317" : "#ffffff");
    ctx.fillText("万跑跑团助手", 40, fY + 42);

    ctx.setFontSize(16);
    ctx.setFillStyle(isLight ? "#4b5667" : "#71717a");
    ctx.fillText("微信扫码进入万跑跑团小程序 · 全员跑量目标追踪（纯小程序入口）", 40, fY + 72);

    if (qrLocalPath) {
      drawRoundedRect(ctx, W - 134, fY + 14, 94, 94, 14, "#ffffff", isLight ? "#e2e8f0" : undefined);
      ctx.drawImage(qrLocalPath, W - 128, fY + 20, 82, 82);
    } else {
      drawRoundedRect(
        ctx,
        W - 160,
        fY + 20,
        120,
        48,
        12,
        isLight ? "rgba(245, 158, 11, 0.14)" : "rgba(255, 215, 0, 0.15)",
        isLight ? "rgba(217, 119, 6, 0.4)" : "rgba(255, 215, 0, 0.4)"
      );
      ctx.setFontSize(18);
      ctx.setFillStyle(isLight ? "#b45309" : "#ffd700");
      ctx.fillText("官方战报", W - 138, fY + 50);
    }

    // Scale calculation
    const scale = H > 2500 ? 1.5 : 2;
    const destW = Math.round(W * scale);
    const destH = Math.round(H * scale);

    // Draw and export
    ctx.draw(false, () => {
      setTimeout(() => {
        uni.canvasToTempFilePath({
          canvasId: "reportTablePosterCanvas",
          x: 0,
          y: 0,
          width: W,
          height: H,
          destWidth: destW,
          destHeight: destH,
          success: (res) => {
            resolve(res.tempFilePath);
          },
          fail: (err) => {
            reject(err);
          }
        });
      }, 250);
    });
  });
}

async function handlePreviewTablePosterImage() {
  uni.showLoading({ title: "正在生成全员战报..." });
  try {
    const tempPath = await generateTablePosterImage();
    uni.hideLoading();
    // #ifdef MP-WEIXIN
    const wxObj = (globalThis as any).wx;
    if (wxObj && typeof wxObj.showShareImageMenu === "function") {
      wxObj.showShareImageMenu({
        path: tempPath,
        fail: () => {
          uni.previewImage({ current: tempPath, urls: [tempPath] });
        },
      });
      return;
    }
    // #endif
    uni.previewImage({
      current: tempPath,
      urls: [tempPath]
    });
    uni.showToast({ title: "长按图片可直接转发朋友圈或微信群", icon: "none", duration: 3500 });
  } catch (err: any) {
    uni.hideLoading();
    console.error("handlePreviewTablePosterImage fail:", err);
    uni.showToast({ title: "渲染海报失败，请重试", icon: "none" });
  }
}

async function handleSaveTablePosterToAlbum() {
  uni.showLoading({ title: "正在生成并保存..." });
  try {
    const tempPath = await generateTablePosterImage();
    uni.saveImageToPhotosAlbum({
      filePath: tempPath,
      success: () => {
        uni.hideLoading();
        uni.showToast({ title: "全员战报已成功保存到手机相册！", icon: "success", duration: 2500 });
      },
      fail: (saveErr) => {
        uni.hideLoading();
        console.warn("saveImageToPhotosAlbum fail:", saveErr);
        uni.previewImage({ current: tempPath, urls: [tempPath] });
        uni.showToast({ title: "长按图片即可直接保存到相册", icon: "none", duration: 3500 });
      }
    });
  } catch (err: any) {
    uni.hideLoading();
    console.error("handleSaveTablePosterToAlbum fail:", err);
    uni.showToast({ title: "保存失败，请重试", icon: "none" });
  }
}

function closeClubInviteModal() {
  showClubInviteModal.value = false;
  invitedClubInfo.value = null;
  invitedClubCode.value = "";
}

async function handleAcceptClubInvite() {
  if (!invitedClubInfo.value) return;
  if (needsWechatNickname.value && !joinRunnerNickname.value.trim()) {
    uni.showToast({ title: "请先点击昵称框，一键选用您的微信昵称", icon: "none" });
    return;
  }
  const targetClub = invitedClubInfo.value;
  const targetCode = invitedClubCode.value;
  let uid = user.value?.id;
  if (!uid) {
    const autologin = await checkAndAutoLogin();
    uid = autologin?.id;
  }
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }

  acceptingClubInvite.value = true;
  try {
    const res = await request("/api/team/join-club", "POST", {
      user_id: uid,
      club_id: targetClub.id,
      invite_code: targetCode,
      privacy_consent: true,
      display_name: joinRunnerNickname.value.trim() || undefined,
      avatar_url: joinRunnerAvatar.value || undefined,
      inviter_uid: invitedByUid.value || undefined,
      via_invite: true,
    });
    trackFunnelStep("club_join_success", `通过邀请加入跑团：${targetClub.name}`, {
      club_id: targetClub.id,
      via: "invite_card",
    });
    syncUserNicknameAfterJoin(res);
    closeClubInviteModal();
    setActiveClubId(targetClub.id);
    await loadClubData();
    if (!promptOrgProfileLater(res?.org_membership, targetClub.name)) {
      uni.showToast({ title: `成功加入【${targetClub.name}】！`, icon: "success" });
    }
  } catch (e: any) {
    const msg = e?.message || e?.data?.detail || e?.detail || "加入跑团失败";
    if (String(msg).includes("补填期限")) {
      closeClubInviteModal();
      uni.showModal({
        title: "大群资料已逾期",
        content: String(msg),
        confirmText: "去补齐资料",
        cancelText: "稍后",
        success: async (sm) => {
          if (sm.confirm) {
            await loadClubData();
            if (currentOrg.value) openOrgEditProfileModal();
          }
        }
      });
    } else {
      uni.showModal({
        title: "入团提示",
        content: String(msg),
        showCancel: false
      });
    }
  } finally {
    acceptingClubInvite.value = false;
  }
}

async function handleJoinClub() {
  if (needsWechatNickname.value && !joinRunnerNickname.value.trim()) {
    uni.showToast({ title: "请先点击昵称框，一键填入您的微信昵称", icon: "none" });
    return;
  }
  if (!inviteCodeInput.value.trim()) {
    uni.showToast({ title: "请输入邀请码", icon: "none" });
    return;
  }
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
      display_name: joinRunnerNickname.value.trim() || undefined,
      avatar_url: joinRunnerAvatar.value || undefined,
    });
    trackFunnelStep("club_join_success", "通过邀请码加入跑团", {
      via: "invite_code_modal",
    });
    syncUserNicknameAfterJoin(res);
    uni.showToast({ title: res?.message || "加入成功！", icon: "success" });
    showJoinModal.value = false;
    inviteCodeInput.value = "";
    await loadClubData();
  } catch (e: any) {
    const msg = e.message || "加入失败，请核对邀请码";
    if (msg.includes("大群体") || msg.includes("戈友")) {
      const code = inviteCodeInput.value.trim().toUpperCase();
      showJoinModal.value = false;
      openOrgJoinModal();
      orgJoinForm.value.invite_code = code;
      uni.showModal({
        title: "大群认证提示",
        content: msg,
        showCancel: false,
        confirmText: "去实名登记"
      });
    } else {
      uni.showToast({ title: msg, icon: "none" });
    }
  } finally {
    joiningClub.value = false;
  }
}

function goToCockpitPage() {
  uni.switchTab({
    url: "/pages/team/cockpit",
    fail: () => {
      uni.navigateTo({
        url: "/pages/team/cockpit"
      });
    }
  });
}

function handleOpenMembersModal() {
  memberSearchQuery.value = "";
  showMembersModal.value = true;
  trackModal("club_members_manage", "打开队员管理与移出弹窗", "open", {
    club_id: currentClub.value?.id,
  });
}

async function handleChangeRole(targetUid: string, role: string) {
  if (!currentClub.value) return;
  const uid = user.value?.id;
  if (!uid) return;
  try {
    await request(`/api/team/${currentClub.value.id}/role`, "POST", {
      operator_uid: uid,
      target_uid: targetUid,
      role: role,
    });
    trackClick("team_change_member_role", `修改队员角色为 ${role}`, {
      club_id: currentClub.value.id,
      target_uid: targetUid,
      role,
    });
    uni.showToast({
      title: `已设为【${role === "coach" ? "认证教练" : role === "owner" ? "团长" : "团员"}】`,
      icon: "success",
    });
    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: e.message || "角色修改失败", icon: "none" });
  }
}

// ── 🛡️ 防误触：团长移出队员 & 队员退出跑团 二次确认操作 ──
function openRemoveMemberConfirmModal(memberObj: any) {
  if (!currentClub.value || !memberObj) return;
  if (memberObj.role === "owner") {
    uni.showToast({ title: "团长不可被直接移出", icon: "none" });
    return;
  }
  targetMemberToRemove.value = memberObj;
  removeMemberChecked.value = false;
  removeMemberCountdown.value = 3;
  showRemoveMemberConfirmModal.value = true;
  trackModal(
    "remove_member_confirm",
    `打开移出队员防误触确认弹窗：${memberObj.display_name || "该成员"}`,
    "open",
    { club_id: currentClub.value.id, target_uid: memberObj.user_id }
  );
  if (removeMemberTimer) clearInterval(removeMemberTimer);
  removeMemberTimer = setInterval(() => {
    if (removeMemberCountdown.value > 0) {
      removeMemberCountdown.value -= 1;
    } else {
      clearInterval(removeMemberTimer);
      removeMemberTimer = null;
    }
  }, 1000);
}

function closeRemoveMemberConfirmModal() {
  if (showRemoveMemberConfirmModal.value) {
    trackModal("remove_member_confirm", "关闭移出队员确认弹窗", "close");
  }
  showRemoveMemberConfirmModal.value = false;
  targetMemberToRemove.value = null;
  removeMemberChecked.value = false;
  if (removeMemberTimer) {
    clearInterval(removeMemberTimer);
    removeMemberTimer = null;
  }
}

async function confirmRemoveMemberExecution() {
  if (!currentClub.value || !targetMemberToRemove.value) return;
  if (!removeMemberChecked.value || removeMemberCountdown.value > 0 || removingMemberLoading.value) return;
  const uid = user.value?.id;
  if (!uid) return;
  const targetUid = targetMemberToRemove.value.user_id;
  const targetName = targetMemberToRemove.value.display_name || "该成员";
  const clubId = currentClub.value.id;
  removingMemberLoading.value = true;
  try {
    await request(
      `/api/team/${clubId}/members/${encodeURIComponent(targetUid)}?operator_uid=${encodeURIComponent(uid)}`,
      "DELETE"
    );
    trackFunnelStep("team_remove_member_success", `团长确认移出队员：${targetName}`, {
      club_id: clubId,
      target_uid: targetUid,
    });
    uni.showToast({ title: `已将【${targetName}】移出跑团`, icon: "success" });
    showRemoveMemberConfirmModal.value = false;
    closeRemoveMemberConfirmModal();
    await loadClubData();
    if (activeSection.value === "new_members") {
      await fetchNewMembersStatus();
    }
  } catch (e: any) {
    uni.showToast({ title: e.message || "移出失败", icon: "none" });
  } finally {
    removingMemberLoading.value = false;
  }
}

function handleRemoveMember(targetUid: string, displayName: string) {
  const mObj = members.value.find((m: any) => m.user_id === targetUid) || {
    user_id: targetUid,
    display_name: displayName || "该成员",
    role: "member",
  };
  openRemoveMemberConfirmModal(mObj);
}

function openLeaveClubConfirmModal() {
  if (!currentClub.value || currentClub.value.is_virtual_unaffiliated) return;
  if (currentRole.value === "owner") {
    uni.showModal({
      title: "👑 团长退团提示",
      content: `您当前是【${currentClub.value.name}】的跑团团长。\n\n为防止跑团群龙无首，请先在「👥 队员管理与移出」或网页后台将团长身份移交给其他队员后再退出；若需停办跑团，可在管理中心选择解散跑团。`,
      showCancel: false,
      confirmText: "我知道了",
    });
    return;
  }
  leaveClubChecked.value = false;
  leaveClubCountdown.value = 3;
  showLeaveClubConfirmModal.value = true;
  trackModal(
    "leave_club_confirm",
    `打开退出跑团防误触确认弹窗：${currentClub.value.name}`,
    "open",
    { club_id: currentClub.value.id }
  );
  if (leaveClubTimer) clearInterval(leaveClubTimer);
  leaveClubTimer = setInterval(() => {
    if (leaveClubCountdown.value > 0) {
      leaveClubCountdown.value -= 1;
    } else {
      clearInterval(leaveClubTimer);
      leaveClubTimer = null;
    }
  }, 1000);
}

function closeLeaveClubConfirmModal() {
  if (showLeaveClubConfirmModal.value) {
    trackModal("leave_club_confirm", "关闭退出跑团确认弹窗", "close");
  }
  showLeaveClubConfirmModal.value = false;
  leaveClubChecked.value = false;
  if (leaveClubTimer) {
    clearInterval(leaveClubTimer);
    leaveClubTimer = null;
  }
}

async function confirmLeaveClubExecution() {
  if (!currentClub.value || !leaveClubChecked.value || leaveClubCountdown.value > 0 || leavingClubLoading.value) {
    return;
  }
  const uid = user.value?.id;
  if (!uid) return;
  const leavingClubName = currentClub.value.name;
  const leavingClubId = currentClub.value.id;
  leavingClubLoading.value = true;
  try {
    await request(`/api/team/${encodeURIComponent(leavingClubId)}/leave`, "POST", {
      user_id: uid,
    });
    trackFunnelStep("team_leave_club_success", `队员确认退出跑团：${leavingClubName}`, {
      club_id: leavingClubId,
    });
    showLeaveClubConfirmModal.value = false;
    closeLeaveClubConfirmModal();
    try {
      const savedActive = uni.getStorageSync("rgm_active_club_id");
      if (savedActive === leavingClubId) {
        uni.removeStorageSync("rgm_active_club_id");
      }
    } catch (_) {}
    uni.showToast({
      title: `已退出【${leavingClubName}】`,
      icon: "success",
      duration: 2500,
    });
    activeSection.value = "";
    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: e.message || "退出跑团失败", icon: "none" });
  } finally {
    leavingClubLoading.value = false;
  }
}


function sanitizeMeetTimeStr(meetTimeStr: string): string {
  if (!meetTimeStr) return "";
  let s = meetTimeStr.trim();
  if (!s.includes(":")) {
    s = `${s.split(" ")[0]} 06:30`;
  } else if (s.includes("00:00")) {
    s = s.replace("00:00", "06:30");
  }
  return s;
}

function formatMeetTime(meetTimeStr: string) {
  if (!meetTimeStr) return "待定";
  try {
    const cleanStr = sanitizeMeetTimeStr(meetTimeStr);
    const d = new Date(cleanStr.replace(/-/g, "/"));
    if (isNaN(d.getTime())) return meetTimeStr;
    const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    const month = d.getMonth() + 1;
    const date = d.getDate();
    const w = weekdays[d.getDay()];
    const hours = String(d.getHours()).padStart(2, "0");
    const minutes = String(d.getMinutes()).padStart(2, "0");
    return `${month}月${date}日 (${w}) ${hours}:${minutes}`;
  } catch (e) {
    return meetTimeStr;
  }
}

function formatJoinTime(isoStr: string) {
  if (!isoStr) return "刚刚";
  try {
    const d = new Date(isoStr.replace(/-/g, "/"));
    if (isNaN(d.getTime())) return isoStr;
    const m = d.getMonth() + 1;
    const day = d.getDate();
    const h = String(d.getHours()).padStart(2, "0");
    const min = String(d.getMinutes()).padStart(2, "0");
    return `${m}月${day}日 ${h}:${min}`;
  } catch (e) {
    return isoStr;
  }
}

function getCountdownText(meetTimeStr: string) {
  if (!meetTimeStr) return "";
  try {
    const cleanStr = sanitizeMeetTimeStr(meetTimeStr);
    const targetDate = new Date(cleanStr.replace(/-/g, "/"));
    const target = targetDate.getTime();
    if (isNaN(target)) return "";
    const nowDate = new Date();
    const diffMs = target - nowDate.getTime();
    if (diffMs < 0) {
      if (diffMs > -4 * 3600 * 1000) return "🔥 正在进行中";
      return "已结束";
    }
    const diffHours = Math.floor(diffMs / (3600 * 1000));
    const todayMidnight = new Date(nowDate.getFullYear(), nowDate.getMonth(), nowDate.getDate()).getTime();
    const targetMidnight = new Date(targetDate.getFullYear(), targetDate.getMonth(), targetDate.getDate()).getTime();
    const calendarDays = Math.round((targetMidnight - todayMidnight) / 86400000);

    if (calendarDays <= 0) {
      if (diffHours === 0) {
        const diffMins = Math.max(1, Math.floor(diffMs / (60 * 1000)));
        return `⚡ 还有 ${diffMins} 分钟开跑`;
      }
      return `⏰ 今天开跑 (还有${diffHours}小时)`;
    } else if (calendarDays === 1) {
      return diffHours < 24 ? `⏰ 明天开跑 (还有${diffHours}小时)` : "⏰ 明天开跑";
    } else if (calendarDays === 2) {
      return "⏰ 后天开跑";
    } else {
      return `⏰ 还有 ${calendarDays} 天开跑`;
    }
  } catch (e) {
    return "";
  }
}

function parseMeetTimeToSeconds(meetTimeStr: string): number {
  if (!meetTimeStr) return Math.floor(Date.now() / 1000) + 3600;
  const cleanStr = sanitizeMeetTimeStr(meetTimeStr).replace(/-/g, "/");
  const ts = new Date(cleanStr).getTime();
  if (isNaN(ts)) {
    return Math.floor(Date.now() / 1000) + 3600;
  }
  return Math.floor(ts / 1000);
}

function canManageEvent(evt: any): boolean {
  if (!evt) return false;
  if (currentRole.value === 'owner' || isOwnerOrDev.value || currentRole.value === 'coach') return true;
  if (evt.creator_id && user.value?.id && evt.creator_id === user.value.id) return true;
  return false;
}

function handleOpenCreateGroupRun() {
  editingEventId.value = null;
  eventType.value = "group_run";
  eventTitle.value = "";
  const d = new Date();
  const dayOfWeek = d.getDay();
  let daysUntilSaturday = (6 - dayOfWeek + 7) % 7;
  if (daysUntilSaturday === 0) daysUntilSaturday = 7;
  d.setDate(d.getDate() + daysUntilSaturday);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  eventMeetDate.value = `${year}-${month}-${day}`;
  eventMeetTime.value = "06:30";
  eventLocation.value = "";
  eventLocationDetail.value = "";
  eventLatitude.value = null;
  eventLongitude.value = null;
  lastGeocodedLocationName.value = "";
  eventTargetKm.value = 10;
  eventPace.value = "5:30 - 6:00 /km";
  eventMaxParticipants.value = 0;
  eventCoverImage.value = PRESET_COVERS[0].url;
  eventRules.value = "自备饮用水与补给，遵守交通规则，健康安全第一！";
  eventRepeatType.value = "none";
  eventRepeatWeeks.value = 4;
  eventVisibilityMode.value = "registered_only";
  isRulesFocused.value = false;
  selectedModalTplId.value = "";
  showGroupRunModal.value = true;
  trackModal("group_run_editor", "打开约跑发布弹窗", "open", {
    club_id: currentClub.value?.id,
  });
  if (currentClub.value?.id) {
    request(`/api/team/${currentClub.value.id}/event-templates`)
      .then((r: any) => {
        if (Array.isArray(r?.custom_templates)) {
          customModalTemplates.value = r.custom_templates;
        }
      })
      .catch(() => {});
  }
}

function applyModalGroupRunTemplate(tpl: GroupRunTemplateItem) {
  selectedModalTplId.value = tpl.id;
  eventTitle.value = tpl.title || "";
  eventTargetKm.value = tpl.target_km || 15;
  eventMeetDate.value = resolveNextWeekdayIso(tpl.default_weekday ?? 0);
  eventMeetTime.value = tpl.meet_time_hm || "06:30";
  if (tpl.location) {
    eventLocation.value = tpl.location;
    eventLatitude.value = tpl.latitude ?? null;
    eventLongitude.value = tpl.longitude ?? null;
    lastGeocodedLocationName.value = tpl.location;
  }
  eventLocationDetail.value = tpl.location_detail || "";
  eventPace.value = tpl.pace_requirement || "5:30 - 6:00 /km";
  eventRules.value = tpl.rules || "";
  uni.showToast({ title: `已套用「${tpl.name}」`, icon: "none" });
}

async function onEventLocationInputBlur() {
  const kw = eventLocation.value.trim();
  if (!kw) return;
  if (kw === lastGeocodedLocationName.value && eventLatitude.value && eventLongitude.value) {
    return;
  }
  const matches = await searchGroupRunGeocode(kw);
  if (matches.length > 0) {
    eventLatitude.value = matches[0].latitude;
    eventLongitude.value = matches[0].longitude;
    lastGeocodedLocationName.value = kw;
  }
}

function onInlineEventMapTap(e: any) {
  const lat = Number(e?.detail?.latitude);
  const lng = Number(e?.detail?.longitude);
  if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
    eventLatitude.value = Number(lat.toFixed(6));
    eventLongitude.value = Number(lng.toFixed(6));
    uni.showToast({ title: "已移动大头针位置 ✓", icon: "none" });
  }
}

function onMapPinConfirm(picked: GroupRunVenuePreset) {
  showMapPinPickerModal.value = false;
  if (picked) {
    eventLocation.value = picked.name;
    if (picked.address && !eventLocationDetail.value) {
      eventLocationDetail.value = picked.address;
    }
    eventLatitude.value = picked.latitude;
    eventLongitude.value = picked.longitude;
    lastGeocodedLocationName.value = picked.name;
    uni.showToast({ title: "集合点大头针已标注 ✓", icon: "none" });
  }
}

async function handleSaveModalEventTemplate() {
  if (!currentClub.value?.id) return;
  if (!eventTitle.value.trim()) {
    uni.showToast({ title: "请先填写活动标题再保存模版", icon: "none" });
    return;
  }
  const shortName = eventTitle.value.trim().slice(0, 8);
  try {
    const res: any = await request(`/api/team/${currentClub.value.id}/event-templates`, "POST", {
      operator_uid: user.value?.id,
      name: shortName,
      title: eventTitle.value.trim(),
      event_type: eventType.value,
      target_km: Number(eventTargetKm.value) || 15,
      default_weekday: new Date((eventMeetDate.value || resolveNextWeekdayIso(0)).replace(/-/g, "/")).getDay() || 0,
      meet_time_hm: eventMeetTime.value || "06:30",
      location: eventLocation.value.trim(),
      location_detail: eventLocationDetail.value.trim(),
      latitude: eventLatitude.value,
      longitude: eventLongitude.value,
      pace_requirement: eventPace.value.trim(),
      rules: eventRules.value.trim(),
    });
    if (Array.isArray(res?.custom_templates)) {
      customModalTemplates.value = res.custom_templates;
    }
    if (res?.template?.id) {
      selectedModalTplId.value = res.template.id;
    }
    uni.showToast({ title: "已存为跑团约跑模版 ✓", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: e.message || "保存模版失败", icon: "none" });
  }
}

async function handleDeleteModalEventTemplate(tpl: GroupRunTemplateItem) {
  if (!currentClub.value?.id || !tpl?.id) return;
  try {
    const res: any = await request(`/api/team/${currentClub.value.id}/event-templates/${tpl.id}`, "DELETE");
    if (Array.isArray(res?.custom_templates)) {
      customModalTemplates.value = res.custom_templates;
    } else {
      customModalTemplates.value = customModalTemplates.value.filter((t) => t.id !== tpl.id);
    }
    uni.showToast({ title: "模版已移除", icon: "none" });
  } catch (e) {
    uni.showToast({ title: "删除模版失败", icon: "none" });
  }
}

function handleOpenCreateEvent() {
  handleOpenCreateGroupRun();
}

function handleOpenEditEvent(evt: any) {
  editingEventId.value = evt.id;
  eventType.value = evt.event_type || (evt.meet_time ? "group_run" : "distance_challenge");
  eventTitle.value = evt.title || "";
  const mt = evt.meet_time || evt.start_date || "";
  if (mt.includes(" ") || mt.includes("T")) {
    const parts = mt.split(/[\sT]+/);
    eventMeetDate.value = parts[0] || "";
    let t = (parts[1] && parts[1].includes(":")) ? parts[1].slice(0, 5) : "06:30";
    if (t === "00:00") t = "06:30";
    eventMeetTime.value = t;
  } else {
    eventMeetDate.value = mt || "";
    eventMeetTime.value = "06:30";
  }
  eventLocation.value = evt.location || "";
  eventLocationDetail.value = evt.location_detail || "";
  eventLatitude.value = evt.latitude || null;
  eventLongitude.value = evt.longitude || null;
  eventTargetKm.value = evt.target_km || 10;
  eventPace.value = evt.pace_requirement || "5:30 - 6:00 /km";
  eventMaxParticipants.value = evt.max_participants || 0;
  eventCoverImage.value = evt.cover_image || PRESET_COVERS[0].url;
  eventRules.value = evt.rules || "";
  eventRepeatType.value = evt.repeat_rule === "weekly" ? "weekly" : "none";
  eventRepeatWeeks.value = 4;
  eventVisibilityMode.value = (evt.visibility_mode as any) || "registered_only";
  isRulesFocused.value = false;
  showGroupRunModal.value = true;
}

async function handleDeleteEvent(eventId: string) {
  if (!currentClub.value) return;
  uni.showModal({
    title: "确认删除",
    content: "确定要删除该跑团活动吗？删除后所有已报名成员记录将被清理。",
    confirmColor: "#ff453a",
    success: async (res) => {
      if (res.confirm) {
        try {
          await request(`/api/team/${currentClub.value.id}/events/${eventId}`, "DELETE");
          uni.showToast({ title: "活动已删除", icon: "success" });
          await loadClubData();
        } catch (e: any) {
          uni.showToast({ title: "删除失败", icon: "none" });
        }
      }
    }
  });
}

function handleSelectPresetCover(url: string) {
  eventCoverImage.value = url;
}

function handleUploadCover() {
  uni.chooseImage({
    count: 1,
    sizeType: ["compressed"],
    sourceType: ["album", "camera"],
    success: (res) => {
      const tempPath = res.tempFilePaths[0];
      if (!tempPath) return;
      uni.showLoading({ title: "上传题头图中..." });
      uni.uploadFile({
        url: "https://rgm.vanpower.net/api/team/upload-logo",
        filePath: tempPath,
        name: "file",
        success: (uploadRes) => {
          uni.hideLoading();
          try {
            const parsed = JSON.parse(uploadRes.data);
            if (parsed.logo_url || parsed.url) {
              eventCoverImage.value = parsed.logo_url || parsed.url;
              uni.showToast({ title: "题头图设置成功", icon: "success" });
            }
          } catch (e) {
            uni.showToast({ title: "解析响应失败", icon: "none" });
          }
        },
        fail: (err) => {
          uni.hideLoading();
          uni.showToast({ title: "上传失败", icon: "none" });
        }
      });
    }
  });
}

async function handleChooseLocation() {
  showMapPinPickerModal.value = true;
}

function handleOpenMap(evt: any) {
  if (!evt) return;
  if (evt.latitude && evt.longitude) {
    // #ifdef MP-WEIXIN
    if (typeof wx !== "undefined" && wx.openLocation) {
      wx.openLocation({
        latitude: Number(evt.latitude),
        longitude: Number(evt.longitude),
        name: evt.location || "约跑集合点",
        address: evt.location_detail || evt.location || "",
        scale: 16
      });
      return;
    }
    // #endif
  }

  const copyText = (evt.location || "") + (evt.location_detail ? ` (${evt.location_detail})` : "");
  if (copyText) {
    uni.setClipboardData({
      data: copyText,
      success: () => {
        uni.showToast({ title: "集合地点已复制到剪贴板", icon: "none" });
      }
    });
  } else {
    uni.showToast({ title: "暂无集合点坐标", icon: "none" });
  }
}

function handleOpenGroupRunSpace(evt: any, stage?: "pre" | "post", openPoster?: boolean) {
  const cId = currentClub.value?.id || evt?.club_id;
  if (!cId || !evt?.id) return;
  const s = stage || (isGroupRunPostStage(evt) ? "post" : "pre");
  const posterParam = openPoster ? "&poster=1" : "";
  uni.navigateTo({
    url: `/pages/group-run/group-run?club_id=${encodeURIComponent(cId)}&event_id=${encodeURIComponent(evt.id)}&stage=${s}${posterParam}`
  });
}

function handleOpenParticipants(evt: any) {
  handleOpenGroupRunSpace(evt);
}

function onDateChange(e: any) {
  eventMeetDate.value = e.detail.value;
}

function onTimeChange(e: any) {
  eventMeetTime.value = e.detail.value;
}

async function handleSaveGroupRun() {
  if (!currentClub.value) return;
  if (!eventTitle.value.trim()) {
    uni.showToast({ title: "请输入活动标题", icon: "none" });
    return;
  }
  if (eventType.value === "group_run" && !eventLocation.value.trim()) {
    uni.showToast({ title: "请输入集合地点", icon: "none" });
    return;
  }
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }

  savingEvent.value = true;
  try {
    if (eventType.value === "group_run" && eventLocation.value.trim()) {
      await onEventLocationInputBlur();
    }
    const finalTime = (eventMeetTime.value && eventMeetTime.value !== "00:00") ? eventMeetTime.value : "06:30";
    const fullMeetTime = eventType.value === "group_run" ? `${eventMeetDate.value} ${finalTime}`.trim() : eventMeetDate.value;
    const payload = {
      operator_uid: uid,
      title: eventTitle.value.trim(),
      event_type: eventType.value,
      start_date: eventMeetDate.value,
      end_date: eventMeetDate.value,
      meet_time: fullMeetTime,
      location: eventLocation.value.trim(),
      location_detail: eventLocationDetail.value.trim(),
      latitude: eventLatitude.value,
      longitude: eventLongitude.value,
      target_km: Number(eventTargetKm.value) || 10,
      pace_requirement: eventPace.value.trim(),
      cover_image: eventCoverImage.value,
      max_participants: Number(eventMaxParticipants.value) || 0,
      rules: eventRules.value.trim(),
      repeat_rule: eventRepeatType.value,
      repeat_weeks: eventRepeatWeeks.value,
      visibility_mode: eventVisibilityMode.value
    };

    if (editingEventId.value) {
      await request(`/api/team/${currentClub.value.id}/events/${editingEventId.value}`, "PUT", payload);
      trackFunnelStep(
        "group_run_update_success",
        `更新约跑活动：${eventTitle.value.trim()}`,
        { club_id: currentClub.value.id, event_id: editingEventId.value }
      );
      uni.showToast({ title: "约跑已更新！", icon: "success" });
    } else {
      await request(`/api/team/${currentClub.value.id}/events`, "POST", payload);
      trackFunnelStep(
        "group_run_publish_success",
        `发布约跑活动：${eventTitle.value.trim()}`,
        { club_id: currentClub.value.id, target_km: Number(eventTargetKm.value) || 10 }
      );
      uni.showToast({ title: "约跑发布成功！", icon: "success" });
    }
    showGroupRunModal.value = false;
    showEventModal.value = false;
    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: e?.message || "操作失败", icon: "none" });
  } finally {
    savingEvent.value = false;
  }
}

function handleSaveEvent() {
  handleSaveGroupRun();
}

function handleArchiveEvent(evt: any) {
  if (!currentClub.value || !evt?.id) return;
  uni.showModal({
    title: "归档约跑活动",
    content: `确定将【${evt.title}】归档吗？归档后将从活动列表隐藏，但历史完赛战报数据仍会保留。`,
    confirmText: "确认归档",
    success: async (mRes) => {
      if (!mRes.confirm) return;
      try {
        await request(`/api/team/${currentClub.value.id}/events/${evt.id}/archive`, "POST", {});
        uni.showToast({ title: "已归档隐藏", icon: "success" });
        await loadClubData();
      } catch (e: any) {
        uni.showToast({ title: e?.message || "归档失败", icon: "none" });
      }
    },
  });
}

async function handleJoinGroupRun(evt: any) {
  if (!currentClub.value || !evt?.id) return;
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }

  joiningEventId.value = evt.id;
  try {
    await request(`/api/team/${currentClub.value.id}/events/${evt.id}/join`, "POST", {
      user_id: uid
    });
    trackFunnelStep("group_run_join_success", `报名约跑活动：${evt.title}`, {
      club_id: currentClub.value.id,
      event_id: evt.id,
    });

    // Attempt WeChat subscribe message if available
    try {
      // #ifdef MP-WEIXIN
      if (typeof wx !== "undefined" && wx.requestSubscribeMessage) {
        wx.requestSubscribeMessage({
          tmplIds: ["I8K67iHNWQB0on15Z01rxKinP18DAuIPgaz7LSXIqT0"],
          complete: () => {}
        });
      }
      // #endif
    } catch (ignored) {}

    // Show prompt offering to add to phone calendar
    uni.showModal({
      title: "🎉 报名成功！",
      content: `已成功加入【${evt.title}】！\n已在小程序通知中心为您开启提醒。\n\n是否立即将约跑添加到手机系统日历（支持提前30分钟响铃闹钟）？`,
      confirmText: "同步到日历",
      cancelText: "稍后设置",
      success: (mRes) => {
        if (mRes.confirm) {
          handleAddToCalendar(evt);
        }
      }
    });

    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: e?.message || "报名失败", icon: "none" });
  } finally {
    joiningEventId.value = null;
  }
}

async function handleLeaveGroupRun(evt: any) {
  if (!currentClub.value || !evt?.id) return;
  const uid = user.value?.id;
  if (!uid) return;

  uni.showModal({
    title: "取消报名",
    content: `确定要退出【${evt.title}】的约跑活动吗？`,
    confirmColor: "#ff453a",
    success: async (mRes) => {
      if (mRes.confirm) {
        joiningEventId.value = evt.id;
        try {
          await request(`/api/team/${currentClub.value.id}/events/${evt.id}/leave`, "POST", {
            user_id: uid
          });
          uni.showToast({ title: "已取消报名", icon: "none" });
          await loadClubData();
        } catch (e: any) {
          uni.showToast({ title: e?.message || "取消失败", icon: "none" });
        } finally {
          joiningEventId.value = null;
        }
      }
    }
  });
}

function handleAddToCalendar(evt: any) {
  if (!evt) return;
  const startTime = parseMeetTimeToSeconds(evt.meet_time || evt.start_date);
  const locationStr = evt.location || "跑团指定地点";
  const descStr = `【跑团约跑】${evt.title}\n集合时间: ${evt.meet_time || evt.start_date || '请见跑团通知'}\n地点: ${locationStr}\n建议配速: ${evt.pace_requirement || '不限'}\n目标跑量: ${evt.target_km || 10}km\n${evt.rules || ''}`;

  // #ifdef MP-WEIXIN
  if (typeof wx !== "undefined" && wx.addPhoneCalendar) {
    wx.addPhoneCalendar({
      title: `【跑团约跑】${evt.title}`,
      startTime: startTime,
      endTime: startTime + 7200,
      allDay: false,
      location: locationStr,
      description: descStr,
      alarm: true,
      alarmOffset: 1800, // 提前 30 分钟手机闹钟提醒
      success: () => {
        uni.showToast({ title: "已加入手机日历提醒！", icon: "success" });
      },
      fail: (err: any) => {
        console.warn("addPhoneCalendar fail:", err);
        if (String(err?.errMsg).includes("cancel")) {
          // user tapped cancel
        } else {
          uni.showToast({ title: "已在小程序内开启提醒", icon: "success" });
        }
      }
    });
    return;
  }
  // #endif

  uni.showToast({ title: "已在小程序内开启提醒！", icon: "success" });
}

onShow(() => {
  applySystemTheme(currentTheme.value);
  syncTabBarIndex(2);
  // 从【我的】等页面点击“自建跑团”跳回时，自动弹出自建跑团弹窗
  const pendingCreateClub = uni.getStorageSync("team_open_create_club");
  if (pendingCreateClub) {
    uni.removeStorageSync("team_open_create_club");
    openCreateClubModal();
  } else if (showCreateClubModal.value) {
    fetchCreationEligibility();
  }
  // 从英雄榜或首页通知跳回时，可指定打开的子页面
  const pendingSection = uni.getStorageSync("team_open_section") || uni.getStorageSync("rgm_team_open_section");
  if (pendingSection) {
    uni.removeStorageSync("team_open_section");
    uni.removeStorageSync("rgm_team_open_section");
    activeSection.value = pendingSection;
  }
  // 体能罗盘「生成战报」：Tab 页不能带参数，改用缓存传递
  const pendingReport = uni.getStorageSync("team_pending_report");
  if (pendingReport) {
    uni.removeStorageSync("team_pending_report");
    activeSection.value = "manage";
    (async () => {
      if (pendingReport.club_id) setActiveClubId(pendingReport.club_id);
      await loadClubData(pendingReport.club_id);
      firstLoadPending.value = false;
      openReportModal();
    })();
    return;
  }
  if (firstLoadPending.value) {
    const timer = setTimeout(() => (firstLoadPending.value = false), 8000);
    Promise.resolve(loadClubData())
      .catch(() => {})
      .finally(() => {
        clearTimeout(timer);
        firstLoadPending.value = false;
      });
  } else {
    loadClubData();
  }
});

onPullDownRefresh(async () => {
  try {
    const ok = await loadClubData();
    if (ok === false) {
      uni.showToast({ title: "刷新失败，请检查网络后重试", icon: "none" });
    } else if (ok === true) {
      uni.showToast({ title: "跑团数据已更新", icon: "success" });
    }
  } catch (e) {
    uni.showToast({ title: "刷新失败，请稍后重试", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});

async function handleInviteFromWeChat(options: any) {
  if (!options) return;
  if (options.inviter_uid) {
    setPendingInviterUid(options.inviter_uid);
    if (!getStoredUser()) {
      user.value = await wechatLogin();
    }
  }
  const action = options.action;
  const clubId = options.club_id;
  const orgId = options.org_id;
  const code = (options.invite_code || "").trim();
  invitedByUid.value = String(options.inviter_uid || "").trim();
  const invParam = invitedByUid.value ? `&inviter_uid=${encodeURIComponent(invitedByUid.value)}` : "";

  // 0. Mentorship Invite (微信卡片师徒一键结对)
  if (action === "bind_mentor" && options.mentor_uid) {
    const u = user.value || getStoredUser() || (await wechatLogin());
    const uid = u?.id || "";
    const invUid = String(options.mentor_uid || "").trim();
    const invName = decodeURIComponent(String(options.mentor_name || "跑友"));
    const invRole = String(options.mentor_role || "mentor");
    if (uid && invUid && uid !== invUid) {
      await loadClubData();
      const isInviterMentor = invRole !== "mentee";
      uni.showModal({
        title: "🥋 收到师徒结对邀请",
        content: isInviterMentor
          ? `【${invName}】邀请您成为TA的徒弟（1对1指导，师傅可查看您的训练与休息恢复数据），是否立即确认结对？`
          : `【${invName}】诚邀您担任TA的师傅（最多同时带3位队员，可查看徒弟训练与休息数据），是否立即确认收徒？`,
        confirmText: "立即结对",
        cancelText: "稍后",
        success: async (mRes) => {
          if (mRes.confirm) {
            await handleBindMentorship(
              isInviterMentor ? invUid : uid,
              isInviterMentor ? uid : invUid,
              invName,
              "师徒结对"
            );
          }
        },
      });
    }
    return;
  }

  // 1. Club Invite (跑团受邀入团)
  //    注意：教练罗盘跳转报告时会带 ?action=report&club_id=，不能被当成入团邀请
  if (action === "join_club" || (clubId && !orgId && !action)) {
    uni.showLoading({ title: "正在读取跑团邀请...", mask: true });
    try {
      const u = user.value || getStoredUser() || (await wechatLogin());
      const uid = u?.id || "";
      const res = await request(
        `/api/team/${encodeURIComponent(clubId)}/invite-info?invite_code=${encodeURIComponent(code)}&user_id=${encodeURIComponent(uid)}${invParam}`
      );
      uni.hideLoading();
      if (res?.is_club_member) {
        uni.showToast({ title: `您已是【${res.club?.name}】团员`, icon: "none" });
        setActiveClubId(clubId);
        await loadClubData();
      } else if (res?.club) {
        invitedClubInfo.value = res.club;
        invitedClubCode.value = code;
        invitedClubOneClick.value = Boolean(res.one_click_join ?? res.is_code_valid);
        invitedClubIsOrgMember.value = Boolean(res.is_org_member && res.org_status !== "expired");
        invitedClubDeadlineDays.value = res.profile_deadline_days || 14;
        showClubInviteModal.value = true;
      }
    } catch (err: any) {
      uni.hideLoading();
      console.warn("fetch club invite fail:", err);
      if (code) {
        inviteCodeInput.value = code;
        showJoinModal.value = true;
      }
    }
    return;
  }

  // 2. Organization Invite (高校戈友大群受邀入会：免邀请码、资料可稍后补填)
  if (action === "join_org" || (orgId && action !== "join_club")) {
    uni.showLoading({ title: "正在读取大群邀请...", mask: true });
    try {
      const u = user.value || getStoredUser() || (await wechatLogin());
      const uid = u?.id || "";
      const res = await request(
        `/api/org/${encodeURIComponent(orgId)}/invite-info?invite_code=${encodeURIComponent(code)}&user_id=${encodeURIComponent(uid)}${invParam}`
      );
      uni.hideLoading();
      if (res?.is_member && res?.member_status !== "expired") {
        uni.showToast({ title: `您已是【${res.organization?.name}】成员`, icon: "none" });
        await loadClubData();
      } else {
        orgInviteOneClick.value = Boolean(res?.one_click_join ?? res?.is_code_valid);
        openOrgJoinModal(code, orgId, res?.organization?.name || "大群", true);
      }
    } catch (err: any) {
      uni.hideLoading();
      console.warn("fetch org invite fail:", err);
      orgInviteOneClick.value = Boolean(code || invitedByUid.value);
      openOrgJoinModal(code, orgId, "大群", true);
    }
    return;
  }

  // 3. Fallback pure invite_code without club_id or org_id
  if (code) {
    inviteCodeInput.value = code;
    showJoinModal.value = true;
  }
}

onLoad((options: any) => {
  initShareMenu();
  if (options?.inviter_uid) {
    setPendingInviterUid(options.inviter_uid);
  }
  if (options?.scene) {
    const rawScene = decodeURIComponent(String(options.scene));
    if (rawScene.includes("e=") || rawScene.includes("event_id=")) {
      uni.navigateTo({
        url: `/pages/group-run/group-run?scene=${encodeURIComponent(rawScene)}`,
      });
      return;
    }
    if (rawScene.startsWith("inv=")) {
      const invUid = rawScene.slice(4).trim();
      if (invUid) {
        options.inviter_uid = invUid;
        setPendingInviterUid(invUid);
      }
    }
  }
  if (options?.event_id) {
    const targetClub = options?.club_id || "auto";
    if (options?.club_id) {
      setActiveClubId(options.club_id);
    }
    uni.navigateTo({
      url: `/pages/group-run/group-run?club_id=${encodeURIComponent(targetClub)}&event_id=${encodeURIComponent(options.event_id)}`,
    });
    return;
  }
  if (options?.action === "report" || options?.openReport) {
    // 先切换到指定跑团并等待数据（含角色）加载完成，再打开战报，避免权限判断时数据未就绪
    (async () => {
      if (options?.club_id) setActiveClubId(options.club_id);
      await loadClubData(options?.club_id);
      openReportModal();
    })();
    return;
  }
  if (options?.club_id || options?.org_id || options?.invite_code || options?.action || options?.inviter_uid) {
    setTimeout(() => {
      handleInviteFromWeChat(options);
    }, 300);
  }
});

onShareAppMessage((res: any) => {
  const target = res?.target;
  const dataset = target?.dataset || {};
  const shareType = dataset.shareType || dataset["share-type"];

  if (shareType === "group_run") {
    const evtObj = {
      id: dataset.eventId || dataset["event-id"] || "",
      club_id: dataset.clubId || dataset["club-id"] || currentClub.value?.id || "",
      title: dataset.eventTitle || dataset["event-title"] || "跑团约跑",
      meet_time: dataset.meetTime || dataset["meet-time"] || "",
      cover_image: dataset.coverImage || dataset["cover-image"] || currentClub.value?.logo_url || "",
    };
    const clubNameStr = dataset.clubName || dataset["club-name"] || currentClub.value?.name || "万跑跑团";
    return buildGroupRunSharePayload(evtObj, clubNameStr, user.value?.id);
  }

  if (shareType === "invite_new_user") {
    return getInviteNewRunnerShareMessage(user.value);
  }

  if (shareType === "mentor") {
    const mentorRole = dataset.mentorRole || dataset["mentor-role"] || "mentor";
    const inviterName =
      user.value?.real_name ||
      (user.value?.display_name && user.value?.display_name !== "跑者" && user.value?.display_name !== "微信跑者"
        ? user.value.display_name
        : "跑友");
    const title =
      mentorRole === "mentee"
        ? `🙇 【${inviterName}】诚邀您担任跑步师傅 · 1对1传帮带`
        : `🥋 【${inviterName}】邀您结为师徒 · 科学耐力1对1传帮带`;
    return {
      title,
      path: `/pages/team/team?action=bind_mentor&mentor_uid=${encodeURIComponent(user.value?.id || "")}&mentor_name=${encodeURIComponent(inviterName)}&mentor_role=${encodeURIComponent(mentorRole)}&inviter_uid=${encodeURIComponent(user.value?.id || "")}`,
    };
  }

  if (shareType === "club" || (!shareType && currentClub.value)) {
    const club = {
      id: dataset.clubId || dataset["club-id"] || currentClub.value?.id,
      name: dataset.clubName || dataset["club-name"] || currentClub.value?.name,
      logo_url: currentClub.value?.logo_url,
      invite_code: dataset.inviteCode || dataset["invite-code"] || currentClub.value?.invite_code || "",
    };
    const inviter = user.value?.real_name || (user.value?.display_name !== "跑者" && user.value?.display_name !== "微信跑者" ? user.value?.display_name : "");
    return getClubShareAppMessage(club, inviter, user.value?.id);
  }

  if (shareType === "org" || (!shareType && currentOrg.value)) {
    const org = {
      id: dataset.orgId || dataset["org-id"] || currentOrg.value?.id,
      name: dataset.orgName || dataset["org-name"] || currentOrg.value?.name,
      logo_url: currentOrg.value?.logo_url,
      invite_code: dataset.inviteCode || dataset["invite-code"] || currentOrg.value?.invite_code || "",
    };
    const inviter = user.value?.real_name || (user.value?.display_name !== "跑者" && user.value?.display_name !== "微信跑者" ? user.value?.display_name : "");
    return getOrgShareAppMessage(org, inviter, user.value?.id);
  }

  return getUnifiedShareAppMessage(user.value?.id);
});

onShareTimeline(() => {
  if (currentClub.value) {
    return getClubShareTimeline(currentClub.value);
  }
  if (currentOrg.value) {
    return getOrgShareTimeline(currentOrg.value);
  }
  return getUnifiedShareTimeline();
});
</script>

<style scoped>
.team-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  /* 已是 Tab 页：底部给自定义 TabBar 留出空间 */
  padding: 24rpx 28rpx calc(130rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(130rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── 子页面返回栏 ── */
.section-back-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  margin: -24rpx -28rpx 20rpx -28rpx;
  padding: 24rpx 28rpx;
  background: var(--rgm-bg, rgba(11, 11, 13, 0.96));
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.sbb-back { display: flex; flex-direction: row; align-items: center; gap: 6rpx; width: 140rpx; }
.sbb-arrow { font-size: 44rpx; line-height: 1; color: var(--rgm-brand-text, #fc4c02); }
.sbb-back-txt { font-size: 28rpx; color: var(--rgm-brand-text, #fc4c02); font-weight: 600; }
.sbb-title { font-size: 30rpx; font-weight: 700; color: var(--rgm-text, #ffffff); }
.sbb-placeholder { width: 140rpx; }

/* ── 大群精简条 ── */
.org-compact-card {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-card, linear-gradient(135deg, rgba(245, 158, 11, 0.14) 0%, #151518 100%));
  border: 1rpx solid var(--rgm-line, rgba(245, 158, 11, 0.3));
  border-radius: 24rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.22));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}
.occ-left { display: flex; flex-direction: row; align-items: center; gap: 18rpx; flex: 1; min-width: 0; }
.occ-icon { font-size: 40rpx; }
.occ-meta { display: flex; flex-direction: column; gap: 6rpx; min-width: 0; }
.occ-title-row { display: flex; flex-direction: row; align-items: center; gap: 12rpx; flex-wrap: wrap; }
.occ-title { font-size: 28rpx; font-weight: 700; color: var(--rgm-text, #ffffff); }
.occ-rel-pill {
  font-size: 19rpx;
  font-weight: 600;
  color: var(--rgm-text-2, #a1a1aa);
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
}
.occ-desc { font-size: 22rpx; color: var(--rgm-text-2, #a1a1aa); }
.occ-action { font-size: 24rpx; color: var(--rgm-text-2, #a1a1aa); white-space: nowrap; margin-left: 16rpx; }
.occ-action.warn { color: var(--rgm-red, #f87171); font-weight: 600; }

/* ── 英雄榜预览 ── */
.rank-teaser-card { padding: 28rpx; }
.rt-header { display: flex; flex-direction: row; justify-content: space-between; align-items: center; margin-bottom: 18rpx; }
.rt-title { font-size: 30rpx; font-weight: 700; color: var(--rgm-text, #ffffff); }
.rt-link { font-size: 24rpx; color: var(--rgm-brand-text, #fc4c02); }
.rt-my-row {
  display: flex;
  flex-direction: row;
  align-items: baseline;
  gap: 16rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.1));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  border-radius: 16rpx;
  padding: 18rpx 22rpx;
  margin-bottom: 16rpx;
}
.rt-my-rank { font-size: 30rpx; font-weight: 800; color: var(--rgm-brand-text, #fc4c02); }
.rt-my-meta { font-size: 24rpx; color: var(--rgm-text-2, #d4d4d8); }
.rt-top-list { display: flex; flex-direction: column; gap: 12rpx; }
.rt-top-item { display: flex; flex-direction: row; align-items: center; gap: 16rpx; padding: 8rpx 4rpx; }
.rt-top-item.is-me .rt-name { color: var(--rgm-brand-text, #fc4c02); }
.rt-medal { font-size: 32rpx; width: 44rpx; text-align: center; }
.rt-avatar { width: 56rpx; height: 56rpx; border-radius: 50%; background: var(--rgm-card-3, #27272a);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3); }
.rt-name { flex: 1; font-size: 26rpx; color: var(--rgm-text, #ffffff); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rt-km { font-size: 26rpx; font-weight: 700; color: var(--rgm-text, #ffffff); }
.rt-empty { font-size: 24rpx; color: var(--rgm-text-3, #8e8e93); }

/* ── 功能菜单 ── */
.team-menu-card { padding: 8rpx 28rpx; }
.pm-item { display: flex; flex-direction: row; align-items: center; padding: 28rpx 0; border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06)); gap: 20rpx; }
.pm-item-last { border-bottom: none; }
.pm-icon { font-size: 40rpx; width: 56rpx; text-align: center; }
.pm-meta { flex: 1; display: flex; flex-direction: column; gap: 6rpx; min-width: 0; }
.pm-title { font-size: 29rpx; font-weight: 600; color: var(--rgm-text, #ffffff); }
.pm-status { font-size: 22rpx; color: var(--rgm-text-3, #8e8e93); white-space: nowrap; }
.pm-status.ok { color: var(--rgm-green, #34c759); }
.pm-status.warn { color: var(--rgm-red, #f87171); }
.pm-arrow { font-size: 36rpx; color: var(--rgm-text-3, #48484a); }

/* ── 顶部导航胶囊切换条 ── */
.top-nav-capsule {
  display: flex;
  background-color: var(--rgm-card, #16161a);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 40rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.nav-segment {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  padding: 16rpx 0;
  border-radius: 34rpx;
  transition: all 0.25s ease;
}

.nav-segment.active {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff7300 100%));
  box-shadow: 0 4rpx 16rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.35));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.nav-icon {
  font-size: 26rpx;
}

.nav-text {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text-2, #a1a1aa);
}

.nav-segment.active .nav-text {
  color: var(--rgm-text, #ffffff);
}

/* ── 跑团英雄榜与动态直通卡 ── */
.rank-banner-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(255, 159, 10, 0.08) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.12));
  transition: all 0.2s ease;
}

.rank-banner-card:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.banner-left {
  flex: 1;
  min-width: 0;
}

.banner-badge-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.banner-badge {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.18));
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
}

.banner-hint-pill {
  font-size: 18rpx;
  color: var(--rgm-amber, #ff9f0a);
  background-color: rgba(255, 159, 10, 0.15);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.banner-title {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
  margin-bottom: 4rpx;
}

.banner-desc {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  display: block;
  line-height: 1.4;
}

.banner-arrow-box {
  width: 56rpx;
  height: 56rpx;
  border-radius: 28rpx;
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 16rpx;
}

.banner-arrow {
  font-size: 32rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.club-hero-card {
  background: var(--rgm-card, linear-gradient(135deg, #1c1c20 0%, #131316 100%));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 30rpx var(--rgm-shadow, rgba(0, 0, 0, 0.5));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.hero-top {
  display: flex;
  gap: 24rpx;
}

.club-logo {
  width: 120rpx;
  height: 120rpx;
  border-radius: 24rpx;
  border: 2rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
}

.club-text {
  flex: 1;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}

.club-name {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.role-tag {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
}

.role-owner {
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  color: var(--rgm-brand-text, #fc4c02);
}

.role-coach {
  background-color: var(--rgm-brand-tint, rgba(191, 90, 242, 0.25));
  color: var(--rgm-brand-text, #bf5af2);
}

.role-member {
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-2, #8e8e93);
}

.hero-affiliation-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-wrap: wrap;
  margin-top: 8rpx;
}

.hero-aff-pill {
  display: inline-flex;
  align-items: center;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text-2, #a1a1aa);
}

.hero-aff-pill.is-org,
.hero-aff-pill.is-indep {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text-2, #a1a1aa);
}

.hap-txt {
  font-size: 20rpx;
  font-weight: 600;
}

.tab-club-aff-icon {
  font-size: 22rpx;
  margin-right: 4rpx;
}

.club-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 8rpx;
  display: block;
  line-height: 1.4;
}

.invite-row {
  display: flex;
  align-items: center;
  margin-top: 12rpx;
  font-size: 22rpx;
}

.invite-label {
  color: var(--rgm-text-3, #636366);
}

.invite-val {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
  font-family: monospace;
}

.copy-hint {
  color: var(--rgm-blue, #0a84ff);
  font-size: 20rpx;
}

.section-card {
  background-color: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.22));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* 👑 Owner Panel */
.owner-panel-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(255, 159, 10, 0.1) 0%, #151518 100%));
  border: 1rpx solid rgba(255, 159, 10, 0.3);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.owner-pill {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-amber, #ff9f0a);
  background-color: rgba(255, 159, 10, 0.2);
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
}

.owner-actions-grid {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-top: 10rpx;
}

.owner-tool-item {
  display: flex;
  align-items: center;
  gap: 20rpx;
  background-color: var(--rgm-card-2, #1c1c20);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  transition: all 0.2s;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tool-icon-box {
  width: 68rpx;
  height: 68rpx;
  border-radius: 18rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tool-icon-box.bg-purple {
  background-color: var(--rgm-brand-tint, rgba(191, 90, 242, 0.2));
}

.tool-icon-box.bg-orange {
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
}

.tool-icon {
  font-size: 32rpx;
}

.tool-content {
  flex: 1;
}

.tool-main-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}


.arrow-right {
  font-size: 26rpx;
  color: var(--rgm-text-3, #636366);
}

/* 🧢 Coach Preview */
.coach-preview-card {
  border: 1rpx solid var(--rgm-brand-line, rgba(191, 90, 242, 0.3));
  background: var(--rgm-card, linear-gradient(135deg, rgba(191, 90, 242, 0.08) 0%, #151518 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20rpx;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.icon {
  font-size: 30rpx;
}

.card-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.sub-link {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #bf5af2);
  font-weight: bold;
}

.sub-tip {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.cockpit-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
}

.cockpit-tile {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 18rpx;
  padding: 16rpx 10rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1rpx solid transparent;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.cockpit-tile.green { border-color: rgba(48, 209, 88, 0.3); }
.cockpit-tile.blue { border-color: rgba(10, 132, 255, 0.3); }
.cockpit-tile.yellow { border-color: rgba(255, 214, 10, 0.3); }
.cockpit-tile.red { border-color: rgba(255, 69, 58, 0.3); }

.c-val {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.c-label {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 6rpx;
}

/* Events */
.mini-action-btn {
  font-size: 22rpx;
  font-weight: bold;
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  padding: 0 18rpx;
  height: 52rpx;
  line-height: 52rpx;
  border-radius: 14rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── 🏃 Upcoming Run Banner Card ── */
.upcoming-run-banner-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(252, 76, 2, 0.18) 0%, #17171c 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));
  border-radius: 28rpx;
  padding: 24rpx 26rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 12rpx 36rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.15));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.urb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18rpx;
}

.urb-badge {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.urb-badge-pulse {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background-color: var(--rgm-brand, #fc4c02);
  box-shadow: 0 0 12rpx var(--rgm-brand, #fc4c02);
  animation: pulseDot 1.5s infinite;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

@keyframes pulseDot {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.7; }
}

.urb-badge-text {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #ff8c42);
  letter-spacing: 1rpx;
}

.urb-countdown {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16));
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
}

.urb-body {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-bottom: 20rpx;
}

.urb-thumb {
  width: 130rpx;
  height: 130rpx;
  border-radius: 20rpx;
  flex-shrink: 0;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
}

.urb-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  overflow: hidden;
}

.urb-title {
  font-size: 28rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.urb-meta-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.urb-icon {
  font-size: 22rpx;
}

.urb-meta-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a0a0a5);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.urb-meta-text.highlight {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 600;
}

.urb-actions-row {
  display: flex;
  gap: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.urb-action-btn {
  flex: 1;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 16rpx;
  font-size: 24rpx;
  font-weight: 700;
  text-align: center;
}

.urb-action-btn.reminder-btn {
  background: rgba(48, 209, 88, 0.16);
  border: 1rpx solid rgba(48, 209, 88, 0.4);
  color: var(--rgm-green, #30d158);
}

.urb-action-btn.map-btn {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  color: var(--rgm-text, #e5e5ea);
}

/* ── 🏃 Group Run Cards Section ── */
.events-list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

.group-run-card {
  background-color: var(--rgm-card, #151518);
  border-radius: 28rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  overflow: hidden;
  box-shadow: 0 12rpx 32rpx var(--rgm-shadow, rgba(0, 0, 0, 0.35));
  transition: transform 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gr-cover-wrap {
  position: relative;
  width: 100%;
  height: 280rpx;
}

.gr-cover-img {
  width: 100%;
  height: 100%;
}

.gr-cover-gradient {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 160rpx;
  background: var(--rgm-card, linear-gradient(to top, #151518 0%, rgba(21, 21, 24, 0.7) 50%, transparent 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gr-cover-top-badges {
  position: absolute;
  top: 18rpx;
  left: 18rpx;
  right: 18rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 2;
}

.gr-tag {
  font-size: 20rpx;
  font-weight: 700;
  color: #ffffff;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.2));
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.gr-joined-badge {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-green, #30d158);
  background: rgba(48, 209, 88, 0.2);
  backdrop-filter: blur(8px);
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(48, 209, 88, 0.5);
}

.gr-status-badge {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-amber, #ff9f0a);
  background: rgba(255, 159, 10, 0.2);
  backdrop-filter: blur(8px);
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(255, 159, 10, 0.4);
}

.gr-cover-bottom-info {
  position: absolute;
  bottom: 18rpx;
  left: 20rpx;
  display: flex;
  gap: 12rpx;
  z-index: 2;
}

.gr-dist-pill {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  background: rgba(252, 76, 2, 0.85);
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.gr-pace-pill {
  font-size: 22rpx;
  font-weight: 600;
  color: #ffffff;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.gr-content-box {
  padding: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.gr-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16rpx;
}

.gr-title {
  font-size: 32rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  line-height: 1.4;
  flex: 1;
}

.evt-manage-actions {
  display: flex;
  gap: 14rpx;
  flex-shrink: 0;
}

.evt-manage-actions .evt-btn {
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
}

.evt-manage-actions .evt-btn.edit {
  color: var(--rgm-blue, #0a84ff);
  border: 1rpx solid rgba(10, 132, 255, 0.3);
}

.evt-manage-actions .evt-btn.archive {
  color: #10b981;
  border: 1rpx solid rgba(16, 185, 129, 0.35);
}

.evt-manage-actions .evt-btn.del {
  color: var(--rgm-red, #ff453a);
  border: 1rpx solid rgba(255, 69, 58, 0.3);
}

.gr-detail-strip {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border-radius: 20rpx;
  padding: 18rpx 20rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.04));
}

.gr-detail-row {
  display: flex;
  align-items: center;
  font-size: 24rpx;
  line-height: 1.4;
}

.gr-detail-row.sub {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.gdr-icon {
  margin-right: 10rpx;
  font-size: 24rpx;
}

.gdr-label {
  color: var(--rgm-text-3, #8e8e93);
  width: 90rpx;
  flex-shrink: 0;
}

.gdr-val {
  color: var(--rgm-text, #e5e5ea);
  flex: 1;
}

.gdr-val.highlight {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 700;
}

.gdr-val.link {
  color: var(--rgm-blue, #5ac8fa);
  font-weight: 600;
}

.gdr-link-arrow {
  color: var(--rgm-blue, #5ac8fa);
  font-size: 22rpx;
  margin-left: 8rpx;
}

/* Participants Row */
.gr-participants-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12rpx 0;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
}

.gr-part-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.gr-part-title {
  font-size: 24rpx;
  font-weight: 600;
  color: var(--rgm-text-2, #a0a0a5);
}

.gr-avatars-stack {
  display: flex;
  align-items: center;
}

.gr-stacked-avatar {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  border: 2rpx solid var(--rgm-line-solid, #151518);
  margin-left: -12rpx;
}

.gr-stacked-avatar:first-child {
  margin-left: 0;
}

.gr-avatar-more {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: var(--rgm-card-3, #2c2c2e);
  border: 2rpx solid var(--rgm-line-solid, #151518);
  margin-left: -12rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gr-more-text {
  font-size: 18rpx;
  color: var(--rgm-text, #ffffff);
  font-weight: 700;
}

.gr-no-part-text {
  font-size: 22rpx;
  color: var(--rgm-text-3, #636366);
}

.gr-view-parts-arrow {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

/* 约跑阶段入口 */
.gr-stage-entry-row {
  display: flex;
  gap: 14rpx;
  margin-bottom: 18rpx;
}
.gr-stage-entry {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16rpx 20rpx;
  border-radius: 18rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.04));
}
.gr-stage-entry.current {
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.5));
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
}
.gse-step {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}
.gse-name {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  margin-top: 4rpx;
}

/* Action Buttons */
.gr-actions-bar {
  display: flex;
  width: 100%;
}

.gr-join-btn {
  width: 100%;
  min-width: 0;
  height: 80rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
  margin: 0;
  white-space: nowrap;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #e03e00 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 27rpx;
  font-weight: 800;
  border-radius: 20rpx;
  text-align: center;
  box-shadow: 0 10rpx 28rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.35));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.gr-join-btn::after {
  border: none;
}

.gr-joined-action-group {
  display: flex;
  width: 100%;
  gap: 16rpx;
}

.gr-reminder-btn {
  flex: 2;
  min-width: 0;
  height: 80rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 12rpx;
  margin: 0;
  white-space: nowrap;
  background: rgba(48, 209, 88, 0.16);
  border: 1rpx solid rgba(48, 209, 88, 0.5);
  color: var(--rgm-green, #30d158);
  font-size: 25rpx;
  font-weight: 700;
  border-radius: 20rpx;
  text-align: center;
}

.gr-reminder-btn::after {
  border: none;
}

.gr-leave-btn {
  flex: 1;
  min-width: 0;
  height: 80rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 12rpx;
  margin: 0;
  white-space: nowrap;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  color: var(--rgm-text-3, #8e8e93);
  font-size: 24rpx;
  border-radius: 20rpx;
  text-align: center;
}

.gr-leave-btn::after {
  border: none;
}

.gr-wechat-share-btn {
  min-width: 0;
  height: 80rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  white-space: nowrap;
  background: rgba(7, 193, 96, 0.16);
  border: 1rpx solid rgba(7, 193, 96, 0.48);
  color: #07c160;
  font-size: 25rpx;
  font-weight: 700;
  border-radius: 20rpx;
  text-align: center;
  padding: 0 12rpx;
}

.gr-wechat-share-btn::after {
  border: none;
}

/* Card Organizer Strip */
.gr-organizer-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  padding: 10rpx 16rpx;
  border-radius: 14rpx;
  margin-bottom: 14rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
}

.gr-org-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.gr-org-avatar {
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.2));
}

.gr-org-meta {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.gr-org-role-tag {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16));
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  font-weight: 700;
}

.gr-org-name {
  font-size: 22rpx;
  font-weight: 600;
  color: var(--rgm-text, #e5e5ea);
}

.gr-org-repeat-pill {
  display: flex;
  align-items: center;
  gap: 6rpx;
  background: rgba(48, 209, 88, 0.15);
  border: 1rpx solid rgba(48, 209, 88, 0.35);
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
}

.gr-rep-icon {
  font-size: 20rpx;
}

.gr-rep-text {
  font-size: 20rpx;
  font-weight: 700;
  color: var(--rgm-green, #30d158);
}

/* Creator Preview in Modal */
.ecp-creator-card {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.08));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
  padding: 16rpx 20rpx;
  border-radius: 18rpx;
  margin-bottom: 22rpx;
}

.ecp-avatar {
  width: 68rpx;
  height: 68rpx;
  border-radius: 50%;
  border: 2rpx solid var(--rgm-brand, #fc4c02);
}

.ecp-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.ecp-line {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.ecp-label {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a0a0a5);
}

.ecp-name {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.ecp-role-tag {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  font-weight: 700;
}

.ecp-desc {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

/* Week Calendar Strip */
.wc-tip-pill {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.week-calendar-strip {
  margin-bottom: 16rpx;
}

.wc-scroll {
  width: 100%;
  white-space: nowrap;
}

.wc-days-row {
  display: inline-flex;
  gap: 12rpx;
  padding: 6rpx 2rpx;
}

.wc-day-cell {
  width: 100rpx;
  padding: 14rpx 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
  background: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 18rpx;
  transition: all 0.2s ease;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.wc-day-cell.active {
  background: var(--rgm-brand, #fc4c02);
  border-color: var(--rgm-brand, #fc4c02);
  box-shadow: 0 4rpx 16rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.4));
  transform: translateY(-2rpx);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.wc-weekday {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  font-weight: 600;
}

.wc-day-cell.active .wc-weekday {
  color: var(--rgm-text, rgba(255, 255, 255, 0.9));
}

.wc-num-circle {
  width: 48rpx;
  height: 48rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.wc-daynum {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.wc-subtag {
  font-size: 18rpx;
  color: var(--rgm-text-3, #636366);
}

.wc-day-cell.is-weekend .wc-subtag {
  color: var(--rgm-amber, #ff9f0a);
  font-weight: 700;
}

.wc-day-cell.active .wc-subtag {
  color: var(--rgm-text, #ffffff);
}

.selected-time-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  padding: 14rpx 18rpx;
  margin-bottom: 22rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.sts-left {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex: 1;
}

.sts-icon {
  font-size: 28rpx;
}

.sts-text {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-green, #30d158);
}

.sts-pickers {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.sts-time-picker .sts-picker-btn {
  display: flex;
  align-items: center;
  gap: 6rpx;
  background: var(--rgm-card-3, #2c2c2e);
  padding: 8rpx 16rpx;
  border-radius: 12rpx;
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.sts-arrow {
  font-size: 18rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.sts-more-picker .sts-more-btn {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  padding: 8rpx 14rpx;
  border-radius: 12rpx;
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

/* Repeat Group Run Styles */
.repeat-group-section {
  margin-bottom: 22rpx;
}

.repeat-badge-hint {
  font-size: 20rpx;
  color: var(--rgm-green, #30d158);
  background: rgba(48, 209, 88, 0.12);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.repeat-tabs {
  display: flex;
  gap: 14rpx;
  margin-bottom: 12rpx;
}

.repeat-tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  padding: 16rpx 0;
  background: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  font-size: 24rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.repeat-tab-btn.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 800;
}

.repeat-config-box {
  background: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 18rpx;
  padding: 16rpx 18rpx;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rc-hint {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.4;
}

.rc-weeks-row {
  display: flex;
  gap: 12rpx;
}

.rc-week-pill {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 12rpx 0;
  background: var(--rgm-card-3, #2c2c2e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 14rpx;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rc-week-pill.active {
  background: var(--rgm-brand, #fc4c02);
  border-color: var(--rgm-brand, #fc4c02);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.rc-week-title {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.rc-week-sub {
  font-size: 18rpx;
  color: var(--rgm-text, rgba(255, 255, 255, 0.8));
}

.rc-preview-box {
  background: rgba(0, 0, 0, 0.25);
  padding: 12rpx 14rpx;
  border-radius: 12rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.rc-preview-label {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a0a0a5);
  font-weight: 600;
}

.rc-preview-dates {
  font-size: 22rpx;
  color: var(--rgm-green, #30d158);
  line-height: 1.4;
}

.textarea-done-btn {
  font-size: 22rpx;
  color: var(--rgm-green, #30d158);
  background: rgba(48, 209, 88, 0.15);
  padding: 4rpx 14rpx;
  border-radius: 8rpx;
  font-weight: 600;
}

/* Participants Modal Creator Banner */
.pm-creator-banner {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.1));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
  padding: 14rpx 18rpx;
  border-radius: 16rpx;
  margin-bottom: 16rpx;
}

.pm-cb-avatar {
  width: 60rpx;
  height: 60rpx;
  border-radius: 50%;
  border: 2rpx solid var(--rgm-brand, #fc4c02);
}

.pm-cb-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.pm-cb-line {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.pm-cb-label {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a0a0a5);
}

.pm-cb-name {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.pm-cb-tag {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: 700;
}

.pm-cb-repeat {
  font-size: 20rpx;
  color: var(--rgm-green, #30d158);
}

/* ── Group Run Modal Form Styles ── */
.group-run-modal-content {
  max-height: 88vh;
  display: flex;
  flex-direction: column;
}

.group-run-form-scroll {
  max-height: 72vh;
}

.evt-type-tabs {
  display: flex;
  background: var(--rgm-card-2, #1c1c1e);
  border-radius: 18rpx;
  padding: 6rpx;
  margin-bottom: 20rpx;
  gap: 8rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.evt-type-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  padding: 16rpx 0;
  border-radius: 14rpx;
  transition: all 0.2s ease;
}

.evt-type-tab.active {
  background: var(--rgm-brand, #fc4c02);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.evt-type-tab .ett-icon {
  font-size: 28rpx;
}

.evt-type-tab .ett-text {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.form-row-pair {
  display: flex;
  gap: 16rpx;
  margin-bottom: 20rpx;
}

.picker-flex-item {
  flex: 1;
}

.picker-trigger-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-card-2, #1c1c1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  height: 80rpx;
  padding: 0 20rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.pt-icon {
  font-size: 28rpx;
  margin-right: 12rpx;
}

.pt-val {
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  flex: 1;
}

.pt-arrow {
  font-size: 20rpx;
  color: var(--rgm-text-3, #636366);
}

.form-col-half {
  flex: 1;
}

.label-with-action-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.choose-loc-btn {
  font-size: 22rpx;
  color: var(--rgm-blue, #0a84ff);
  background: rgba(10, 132, 255, 0.12);
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  border: 1rpx solid rgba(10, 132, 255, 0.3);
}

/* Preset Covers Grid */
.preset-covers-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
  margin-bottom: 24rpx;
}

.preset-cover-item {
  position: relative;
  height: 120rpx;
  border-radius: 16rpx;
  overflow: hidden;
  border: 2rpx solid transparent;
  cursor: pointer;
}

.preset-cover-item.active {
  border-color: var(--rgm-brand, #fc4c02);
  box-shadow: 0 0 16rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.5));
}

.pci-img {
  width: 100%;
  height: 100%;
}

.pci-overlay {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  padding: 4rpx 6rpx;
  text-align: center;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.pci-title {
  font-size: 18rpx;
  color: var(--rgm-text, #ffffff);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pci-check {
  position: absolute;
  top: 8rpx;
  right: 8rpx;
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-size: 18rpx;
  width: 28rpx;
  height: 28rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── Participants Modal Styles ── */
.participants-modal-content {
  max-height: 75vh;
  display: flex;
  flex-direction: column;
}

.pm-title-box {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.pm-count-badge {
  font-size: 20rpx;
  color: var(--rgm-green, #30d158);
  background: rgba(48, 209, 88, 0.15);
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(48, 209, 88, 0.3);
}

.pm-event-mini-bar {
  background: var(--rgm-card-2, #1c1c1e);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.pm-evt-name {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  display: block;
  margin-bottom: 6rpx;
}

.pm-evt-sub {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.pm-scroll-list {
  max-height: 48vh;
}

.pm-empty {
  padding: 40rpx 0;
  text-align: center;
}

.pm-empty-text {
  font-size: 24rpx;
  color: var(--rgm-text-3, #636366);
}

.pm-user-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.pm-user-item {
  display: flex;
  align-items: center;
  gap: 18rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.02));
  padding: 16rpx;
  border-radius: 16rpx;
}

.pm-avatar {
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
}

.pm-user-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.pm-name-line {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.pm-name {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.pm-creator-tag {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16));
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  font-weight: 600;
}

.pm-me-tag {
  font-size: 18rpx;
  color: var(--rgm-green, #30d158);
  background: rgba(48, 209, 88, 0.16);
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  font-weight: 600;
}

.pm-joined-time {
  font-size: 20rpx;
  color: var(--rgm-text-3, #636366);
}

.pm-bottom-actions {
  padding-top: 20rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  margin-top: 16rpx;
}

.pm-close-btn {
  height: 72rpx;
  line-height: 72rpx;
  background: var(--rgm-card-3, #2c2c2e);
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  border-radius: 16rpx;
  text-align: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* Leaderboard */
.leaderboard-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.rank-item {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 18rpx 20rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rank-item.top-three {
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.rank-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.rank-num {
  font-size: 32rpx;
  font-weight: 900;
  width: 44rpx;
  text-align: center;
  color: var(--rgm-text-3, #8e8e93);
}

.user-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 36rpx;
}

.user-info {
  display: flex;
  flex-direction: column;
}

.name-badge-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.user-name {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.mini-role-tag {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
}

.mini-role-tag.owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: var(--rgm-amber, #ff9f0a);
}

.mini-role-tag.coach {
  background-color: var(--rgm-brand-tint, rgba(191, 90, 242, 0.2));
  color: var(--rgm-brand-text, #bf5af2);
}

.progress-sub {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
}

.rank-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.km-val {
  font-size: 30rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #fc4c02);
  font-family: monospace;
}

.km-val .unit {
  font-size: 20rpx;
  font-weight: normal;
  color: var(--rgm-text-3, #8e8e93);
}

.progress-bar-bg {
  width: 140rpx;
  height: 6rpx;
  background-color: var(--rgm-card-3, #2c2c2e);
  border-radius: 3rpx;
  margin-top: 8rpx;
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.progress-bar-fill {
  height: 100%;
  background-color: var(--rgm-brand, #fc4c02);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* Feed */
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.feed-card {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 24rpx;
  padding: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.feed-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}

.feed-avatar {
  width: 76rpx;
  height: 76rpx;
  border-radius: 38rpx;
}

.feed-user-meta {
  flex: 1;
}

.feed-author {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  display: block;
}

.feed-act-name {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
  display: block;
}

.feed-distance {
  text-align: right;
}

.feed-km {
  font-size: 36rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #fc4c02);
  font-family: monospace;
}

.feed-unit {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-left: 4rpx;
}

.coach-bubble {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(191, 90, 242, 0.12) 0%, rgba(10, 132, 255, 0.08) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(191, 90, 242, 0.25));
  border-radius: 18rpx;
  padding: 16rpx;
  margin-bottom: 16rpx;
}

.coach-badge-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 8rpx;
}

.coach-robot-icon {
  font-size: 22rpx;
}

.coach-badge-title {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #bf5af2);
}

.coach-comment-text {
  font-size: 22rpx;
  color: var(--rgm-text, #e5e5ea);
  line-height: 1.4;
  display: block;
}

.social-bar {
  display: flex;
  gap: 24rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
}

.like-btn, .comment-trigger-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background-color: var(--rgm-card-3, #242428);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.heart-icon, .cmt-icon {
  font-size: 22rpx;
}

.like-text, .cmt-text {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.like-btn.liked .like-text {
  color: var(--rgm-red, #ff3b30);
  font-weight: bold;
}

.comments-box {
  margin-top: 14rpx;
  background-color: var(--rgm-card-3, #242428);
  border-radius: 14rpx;
  padding: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.cmt-item {
  font-size: 22rpx;
  line-height: 1.4;
}

.cmt-author {
  color: var(--rgm-blue, #0a84ff);
  font-weight: bold;
}

.cmt-content {
  color: var(--rgm-text-2, #d1d1d6);
}

.empty-box {
  padding: 40rpx;
  text-align: center;
}

.empty-text {
  font-size: 24rpx;
  color: var(--rgm-text-3, #636366);
}

/* Modals */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.85);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 80rpx;
  z-index: 999;
  overflow-y: auto;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.modal-content {
  width: 670rpx;
  background-color: var(--rgm-card, #18181c);
  border-radius: 36rpx;
  padding: 40rpx;
  box-sizing: border-box;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  margin-bottom: 60rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-content.large-modal {
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Grand Org Join Modal (non-overlapping flex layout) ── */
.org-modal-root {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  flex-direction: column;
}

.org-dismiss-strip {
  flex: 1;
  background: rgba(0, 0, 0, 0.78);
  /* catchtouchmove 只在这里，与面板不重叠，不影响 scroll-view */;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.org-panel {
  /* 占底部固定比例，不用 vh，由 flex 自然分配 */
  background: var(--rgm-card, #18181c);
  border-radius: 36rpx 36rpx 0 0;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  box-shadow: 0 -12rpx 48rpx var(--rgm-shadow, rgba(0, 0, 0, 0.6));
  /* 绝对禁止 overflow:hidden！会阻断 scroll-view 滚动 */;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.org-panel-head {
  padding: 0 36rpx 16rpx;
}

.drag-bar-wrap {
  display: flex;
  justify-content: center;
  padding: 16rpx 0 12rpx;
}

.org-panel-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.org-panel-close {
  padding: 8rpx 8rpx 8rpx 24rpx;
}

.org-form-body {
  padding: 16rpx 36rpx 0;
  box-sizing: border-box;
}

.org-panel-foot {
  padding: 16rpx 36rpx calc(20rpx + env(safe-area-inset-bottom));
  background: var(--rgm-card-2, #1a1a1e);
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}

.title-with-pill {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.modal-title {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.count-pill {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #bf5af2);
  background: var(--rgm-brand-tint, rgba(191, 90, 242, 0.2));
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
}

.close-btn {
  font-size: 34rpx;
  color: var(--rgm-text-3, #8e8e93);
}


.search-member-input {
  background-color: var(--rgm-card-3, #242429);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  height: 72rpx;
  padding: 0 20rpx;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.members-scroll {
  max-height: 60vh;
  display: flex;
  flex-direction: column;
  padding-bottom: 16rpx;
  box-sizing: border-box;
}

.member-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
  padding: 22rpx 4rpx;
  border-bottom: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.06));
}

.m-left {
  display: flex;
  align-items: center;
  gap: 18rpx;
  flex: 1;
  min-width: 0;
}

.m-avatar {
  width: 80rpx;
  height: 80rpx;
  border-radius: 40rpx;
  flex-shrink: 0;
}

.m-info {
  flex: 1;
  min-width: 0;
}

.m-name-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
}

.m-tags-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-top: 8rpx;
}

.m-name {
  font-size: 27rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
  flex-shrink: 0;
}

.m-role-tag {
  font-size: 18rpx;
  padding: 4rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
  white-space: nowrap;
  flex-shrink: 0;
}

.tag-owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: var(--rgm-amber, #ff9f0a);
}

.tag-coach {
  background-color: var(--rgm-brand-tint, rgba(191, 90, 242, 0.2));
  color: var(--rgm-brand-text, #bf5af2);
}

.tag-member {
  background-color: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-3, #8e8e93);
}

.m-sub-text {
  font-size: 21rpx;
  color: var(--rgm-text-2, #8e8e93);
  margin-top: 8rpx;
  line-height: 1.4;
  display: block;
}

.m-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-shrink: 0;
}

.org-m-actions {
  flex-direction: column;
  align-items: flex-end;
  gap: 10rpx;
}

.act-pill {
  margin: 0;
  font-size: 21rpx;
  font-weight: 800;
  padding: 0 20rpx;
  height: 52rpx;
  line-height: 1.25;
  border-radius: 14rpx;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  flex-shrink: 0;
  box-sizing: border-box;
}

.act-pill::after {
  border: none;
}

.coach-pill {
  background: var(--rgm-brand-tint, rgba(191, 90, 242, 0.25));
  color: var(--rgm-brand-text, #bf5af2);
}

.member-pill {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-3, #8e8e93);
}

.del-pill {
  background: rgba(255, 69, 58, 0.15);
  color: var(--rgm-red, #ff453a);
}

.owner-static-tag {
  font-size: 20rpx;
  color: var(--rgm-amber, #ff9f0a);
  font-weight: bold;
}

.input-label {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 16rpx;
  margin-bottom: 8rpx;
  display: block;
}


.text-input {
  width: 100%;
  height: 80rpx;
  background-color: var(--rgm-card-3, #242429);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  padding: 0 20rpx;
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.textarea-input {
  width: 100%;
  height: 140rpx;
  background-color: var(--rgm-card-3, #242429);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.submit-btn {
  width: 100%;
  height: 84rpx;
  line-height: 1.25;
  padding: 0 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 20rpx;
  margin-top: 24rpx;
  border: none;
  box-sizing: border-box;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.submit-btn::after {
  border: none;
}

/* Unjoined State Styles */
.unjoined-club-view {
  display: flex;
  flex-direction: column;
  gap: 30rpx;
}

.unjoined-hero-box {
  background: var(--rgm-card, linear-gradient(135deg, #18181c 0%, #121215 100%));
  border-radius: 36rpx;
  padding: 50rpx 40rpx;
  text-align: center;
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
  box-shadow: 0 16rpx 40rpx var(--rgm-shadow, rgba(0, 0, 0, 0.4));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.unjoined-badge {
  display: inline-block;
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  padding: 6rpx 20rpx;
  border-radius: 20rpx;
  margin-bottom: 24rpx;
}

.unjoined-hero-title {
  font-size: 38rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  display: block;
  margin-bottom: 16rpx;
}

.unjoined-hero-sub {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.6;
  display: block;
  margin-bottom: 40rpx;
  padding: 0 10rpx;
}

.unjoined-btn-row {
  display: flex;
  gap: 16rpx;
  justify-content: center;
}

.unjoined-action-btn {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 0 14rpx;
  height: 80rpx;
  line-height: 1.25;
  font-size: 25rpx;
  font-weight: bold;
  border-radius: 22rpx;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  box-sizing: border-box;
}

.unjoined-action-btn::after {
  border: none;
}

.unjoined-action-btn.primary-join {
  background: var(--rgm-brand-grad, var(--rgm-brand, #fc4c02));
  color: var(--rgm-text, #ffffff);
  box-shadow: 0 8rpx 20rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.3));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.unjoined-action-btn.secondary-invite {
  background: var(--rgm-card-3, #242429);
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.browse-all-btn {
  display: inline-flex;
  align-items: center;
  margin-top: 14rpx;
  padding: 8rpx 18rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  border-radius: 20rpx;
}

.browse-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 500;
}

/* ── 🚀 新手设定引导横幅 ── */
.onboard-guide-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(168, 85, 247, 0.15) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 24rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 6rpx 24rpx var(--rgm-shadow, rgba(0, 0, 0, 0.3));
}

.ogb-left {
  display: flex;
  align-items: center;
  gap: 20rpx;
  flex: 1;
}

.ogb-icon-circle {
  width: 72rpx;
  height: 72rpx;
  border-radius: 20rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36rpx;
  flex-shrink: 0;
}

.ogb-meta {
  flex: 1;
}

.ogb-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 6rpx;
}

.ogb-title {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.ogb-tag {
  font-size: 18rpx;
  color: var(--rgm-brand-text, #f97316);
  background: var(--rgm-brand-tint, rgba(249, 115, 22, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(249, 115, 22, 0.3));
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.ogb-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.4;
  display: block;
}

.ogb-action-pill {
  background: var(--rgm-brand, #fc4c02);
  border-radius: 20rpx;
  padding: 10rpx 22rpx;
  margin-left: 16rpx;
  flex-shrink: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.ogb-action-txt {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

/* ── 跑团所在地搜索与城市过滤 ── */
.club-search-filter-box {
  margin-bottom: 24rpx;
}

.club-search-bar {
  display: flex;
  align-items: center;
  background: var(--rgm-card, #18181b);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 18rpx;
  padding: 14rpx 20rpx;
  margin-bottom: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.csb-search-icon {
  font-size: 26rpx;
  margin-right: 12rpx;
  opacity: 0.7;
}

.csb-input {
  flex: 1;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
}

.csb-clear-icon {
  font-size: 24rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 4rpx 12rpx;
}

.city-chips-scroll {
  white-space: nowrap;
  width: 100%;
}

.city-chips-row {
  display: inline-flex;
  gap: 12rpx;
  padding: 4rpx 0;
}

.city-chip {
  padding: 8rpx 22rpx;
  border-radius: 24rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  flex-shrink: 0;
  transition: all 0.2s ease;
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

.modal-search-filter-box {
  padding: 0 32rpx 16rpx 32rpx;
}

.modal-search-bar {
  background: var(--rgm-card, #141416);
  border-color: var(--rgm-line, rgba(255, 255, 255, 0.15));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* 平台所有跑团列表 */
.all-clubs-sec {
  margin-top: 24rpx;
}

.sec-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.count-tag {
  font-size: 20rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  color: var(--rgm-brand-text, #fc4c02);
  padding: 2rpx 12rpx;
  border-radius: 12rpx;
  font-weight: bold;
}

.sec-hint {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
}

.empty-clubs-text {
  text-align: center;
  padding: 40rpx 20rpx;
  font-size: 24rpx;
  color: var(--rgm-text-3, #71717a);
}

.clubs-list-wrap {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
}

.club-group-block {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.cgb-header {
  padding: 18rpx 22rpx;
  border-radius: 18rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.cgb-header.org-header {
  background: rgba(245, 158, 11, 0.12);
  border: 1rpx solid rgba(245, 158, 11, 0.35);
}

.cgb-header.indep-header {
  background: rgba(56, 189, 248, 0.1);
  border: 1rpx solid rgba(56, 189, 248, 0.28);
}

.cgb-title {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.cgb-sub {
  font-size: 21rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.club-select-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 20rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
}

.club-select-card.is-org-subclub {
  border-color: rgba(245, 158, 11, 0.25);
}

.csc-logo {
  width: 90rpx;
  height: 90rpx;
  border-radius: 18rpx;
  flex-shrink: 0;
}

.csc-body {
  flex: 1;
  min-width: 0;
}

.csc-title-row {
  display: flex;
  align-items: center;
  margin-bottom: 6rpx;
}

.csc-name {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  line-height: 1.3;
  word-break: break-all;
}

.csc-badges-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 8rpx;
}

.csc-city {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  flex-shrink: 0;
}

.csc-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 8rpx;
  display: block;
}

.csc-meta-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.csc-meta {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.csc-meta.highlight {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.csc-dot {
  font-size: 20rpx;
  color: var(--rgm-text-3, #52525b);
}

.csc-join-btn {
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-size: 24rpx;
  font-weight: bold;
  padding: 0 28rpx;
  height: 60rpx;
  line-height: 60rpx;
  border-radius: 14rpx;
  border: none;
  flex-shrink: 0;
  margin: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* 弹窗中的所有跑团列表 */
.modal-scroll {
  max-height: 65vh;
  overflow-y: auto;
}

.modal-clubs-list {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
}

.modal-club-group-sec {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.mcgs-header {
  padding: 18rpx 22rpx;
  border-radius: 18rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.mcgs-header.is-org {
  background: rgba(245, 158, 11, 0.14);
  border: 1rpx solid rgba(245, 158, 11, 0.38);
}

.mcgs-header.is-indep {
  background: rgba(56, 189, 248, 0.12);
  border: 1rpx solid rgba(56, 189, 248, 0.32);
}

.mcgs-title {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.mcgs-desc {
  font-size: 21rpx;
  color: var(--rgm-text-2, #a1a1aa);
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

.modal-club-card.is-org-card {
  border-color: rgba(245, 158, 11, 0.25);
}

.modal-club-card.is-current {
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.06));
}

.mcc-logo {
  width: 80rpx;
  height: 80rpx;
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
  margin-bottom: 6rpx;
}

.mcc-name {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  line-height: 1.3;
  word-break: break-all;
}

.mcc-badges-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 8rpx;
}

.mcc-aff-badge {
  font-size: 19rpx;
  font-weight: 700;
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
  flex-shrink: 0;
}

.mcc-aff-badge.org-aff,
.mcc-aff-badge.indep-aff {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text-2, #a1a1aa);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
}

.mcc-city {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  flex-shrink: 0;
}

.mcc-desc {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 6rpx;
  display: block;
}

.mcc-meta {
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.mcc-meta .highlight {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.mcc-dot {
  font-size: 20rpx;
  color: var(--rgm-text-3, #52525b);
}

.mcc-action {
  flex-shrink: 0;
  margin-left: 12rpx;
}

.mcc-current-tag {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
  padding: 6rpx 16rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
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

.mcc-join-btn {
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-size: 22rpx;
  font-weight: bold;
  padding: 0 24rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 12rpx;
  border: none;
  margin: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* 顶部横向跑团切换条 */
.clubs-switcher-wrap {
  margin-bottom: 24rpx;
}

.clubs-switcher-scroll {
  width: 100%;
  white-space: nowrap;
}

.clubs-switcher-inner {
  display: inline-flex;
  align-items: center;
  gap: 16rpx;
  padding: 4rpx 2rpx;
}

.club-tab-pill {
  display: inline-flex;
  align-items: center;
  gap: 12rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 10rpx 20rpx;
  border-radius: 30rpx;
  transition: all 0.2s ease;
}

.club-tab-pill.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.18));
  border-color: var(--rgm-brand, #fc4c02);
  box-shadow: 0 4rpx 14rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.25));
}

.tab-club-logo {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
}

.tab-club-name {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-text-2, #d4d4d8);
  max-width: 220rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.club-tab-pill.active .tab-club-name {
  color: var(--rgm-text, #ffffff);
}

.tab-active-check {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 900;
}

.club-tab-pill.tab-browse-btn {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border: 1rpx dashed var(--rgm-line, rgba(255, 255, 255, 0.2));
}

.tab-browse-icon {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

/* 弹窗分栏标签 */
.modal-tab-row {
  display: flex;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 6rpx;
  margin: 0 30rpx 20rpx 30rpx;
  gap: 8rpx;
}

.modal-tab-segment {
  flex: 1;
  text-align: center;
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-text-2, #a1a1aa);
  padding: 12rpx 0;
  border-radius: 16rpx;
  transition: all 0.2s ease;
}

.modal-tab-segment.active {
  background: var(--rgm-card-3, #27272a);
  color: var(--rgm-brand-text, #fc4c02);
  box-shadow: 0 2rpx 8rpx var(--rgm-shadow, rgba(0, 0, 0, 0.3));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
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

.unjoined-highlights {
  padding: 36rpx;
}

.unjoined-sec-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 30rpx;
  display: block;
}

.unjoined-highlight-item {
  display: flex;
  align-items: flex-start;
  gap: 24rpx;
  margin-bottom: 32rpx;
}

.unjoined-highlight-item:last-child {
  margin-bottom: 0;
}

.uh-icon {
  font-size: 38rpx;
  line-height: 1;
  margin-top: 4rpx;
}

.uh-content {
  flex: 1;
}

.uh-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 6rpx;
  display: block;
}

.uh-desc {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.5;
  display: block;
}
/* ── 🏛️ 大群体组织铭牌 ── */
.org-banner-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(30, 27, 46, 0.95) 0%, rgba(20, 20, 28, 0.95) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(139, 92, 246, 0.3));
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx var(--rgm-shadow, rgba(0, 0, 0, 0.35));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.org-banner-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.org-badge-box {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12rpx;
  min-width: 0;
}

.org-badge-icon {
  font-size: 32rpx;
  flex-shrink: 0;
}

.org-badge-title {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  letter-spacing: 0.5rpx;
  white-space: nowrap;
}

.org-auth-status {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  background: rgba(16, 185, 129, 0.14);
  color: var(--rgm-green, #059669);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
  white-space: nowrap;
  flex-shrink: 0;
}

.org-auth-status.pending {
  background: rgba(59, 130, 246, 0.14);
  color: var(--rgm-blue, #2563eb);
  border-color: rgba(59, 130, 246, 0.3);
}

.org-auth-status.temporary {
  background: rgba(245, 158, 11, 0.14);
  color: var(--rgm-brand-text, #d97706);
  border-color: rgba(245, 158, 11, 0.35);
}

.org-auth-status.expired {
  background: rgba(244, 63, 94, 0.14);
  color: var(--rgm-red, #dc2626);
  border-color: rgba(244, 63, 94, 0.35);
}

.org-admin-pills-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12rpx;
  margin-bottom: 18rpx;
}

.org-admin-pill-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14rpx 20rpx;
  border-radius: 18rpx;
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.12));
  min-width: 0;
}

.org-admin-pill-item.primary {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.38));
}

.org-admin-pill-item.span-2 {
  grid-column: span 2;
}

.oap-label {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.org-admin-pill-item.primary .oap-label,
.org-admin-pill-item.primary .oap-arrow {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 800;
}

.oap-arrow {
  font-size: 22rpx;
  color: var(--rgm-text-3, #94a3b8);
  flex-shrink: 0;
  margin-left: 8rpx;
}

.org-status-alert-strip {
  margin-top: 20rpx;
  padding: 18rpx 22rpx;
  border-radius: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.org-status-alert-strip.temp-strip {
  background: rgba(245, 158, 11, 0.1);
  border: 1rpx solid rgba(245, 158, 11, 0.35);
}

.org-status-alert-strip.pending-strip {
  background: rgba(59, 130, 246, 0.1);
  border: 1rpx solid rgba(59, 130, 246, 0.35);
}

.org-status-alert-strip.confirmed-strip {
  background: rgba(34, 197, 94, 0.08);
  border: 1rpx solid rgba(34, 197, 94, 0.28);
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.org-status-alert-strip.expired-strip {
  background: rgba(244, 63, 94, 0.1);
  border: 1rpx solid rgba(244, 63, 94, 0.35);
}

.osas-left {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.osas-title {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.osas-desc {
  font-size: 21rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.5;
}

.osas-btn {
  align-self: flex-start;
  margin: 0;
  padding: 8rpx 26rpx;
  background: var(--rgm-brand, #fc4c02);
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 800;
  border-radius: 16rpx;
  border: none;
  line-height: 1.6;
  white-space: nowrap;
  flex-shrink: 0;
}

.osas-btn.outline {
  --rgm-text: var(--rgm-ink, #ffffff);
  background: var(--rgm-card, rgba(255, 255, 255, 0.1));
  color: var(--rgm-ink, #ffffff);
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.25));
}

.org-right-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
}

.subclubs-tag-btn {
  margin: 0;
  padding: 8rpx 18rpx;
  height: auto;
  line-height: 1.4;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 20rpx;
  white-space: nowrap;
  flex-shrink: 0;
}

.subclubs-tag-text {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  white-space: nowrap;
}

.org-meta-pill-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10rpx;
}

.org-meta-pill {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d5db);
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.06));
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.08));
  white-space: nowrap;
}

.org-meta-pill.highlight {
  color: var(--rgm-text, #ffffff);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  font-weight: bold;
}

.org-meta-pill.gobi-pill {
  color: var(--rgm-green, #059669);
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.3);
  font-weight: bold;
}

.org-meta-pill.gobi-pill.veteran {
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  font-weight: bold;
}

/* ── 🏃 自由跑者独立训练模式专属卡片 ── */
.solo-runner-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(16, 36, 26, 0.95) 0%, rgba(14, 24, 20, 0.95) 100%));
  border: 1rpx solid rgba(52, 199, 89, 0.35);
  border-radius: 28rpx;
  padding: 30rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 30rpx rgba(52, 199, 89, 0.08);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.src-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14rpx;
}

.src-badge-box {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.src-badge-icon {
  font-size: 26rpx;
}

.src-badge-text {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-green, #34c759);
  background: rgba(52, 199, 89, 0.12);
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  border: 1rpx solid rgba(52, 199, 89, 0.25);
}

.src-status-pill {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  padding: 4rpx 14rpx;
  border-radius: 14rpx;
}

.src-title {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 12rpx;
  display: block;
}

.src-desc {
  font-size: 23rpx;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.6;
  margin-bottom: 24rpx;
  display: block;
}

.src-actions-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.src-btn {
  flex: 1;
  font-size: 24rpx;
  font-weight: bold;
  height: 72rpx;
  line-height: 72rpx;
  border-radius: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0;
}

.src-btn.primary {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #34c759 0%, #30b74e 100%));
  color: var(--rgm-text, #ffffff);
  box-shadow: 0 6rpx 20rpx rgba(52, 199, 89, 0.25);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.src-btn.outline {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text, #e4e4e7);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
}

.org-tag-pill {
  font-size: 20rpx;
  padding: 2rpx 10rpx;
  border-radius: 10rpx;
  background: rgba(255, 159, 10, 0.15);
  color: var(--rgm-amber, #ff9f0a);
  border: 1rpx solid rgba(255, 159, 10, 0.3);
  font-weight: bold;
}

.org-tag-pill.free-tag {
  background: rgba(52, 199, 89, 0.12);
  color: var(--rgm-green, #34c759);
  border-color: rgba(52, 199, 89, 0.25);
}

/* ── 🏛️ 未加入大组织提示卡片 ── */
.grand-org-prompt-card {
  background: var(--rgm-card, linear-gradient(135deg, rgba(26, 26, 36, 0.95) 0%, rgba(18, 18, 22, 0.95) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 28rpx;
  padding: 30rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 30rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.1));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gop-badge-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14rpx;
}

.gop-badge {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
}

.gop-code-pill {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  padding: 4rpx 14rpx;
  border-radius: 14rpx;
}

.gop-code-pill.pill-free {
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.15);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
  font-weight: bold;
}

.gop-code-pill.pill-invite {
  color: var(--rgm-amber, #f59e0b);
  background: rgba(245, 158, 11, 0.15);
  border: 1rpx solid rgba(245, 158, 11, 0.3);
}

.gop-title {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 12rpx;
  display: block;
}

.gop-desc {
  font-size: 23rpx;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.6;
  margin-bottom: 24rpx;
  display: block;
}

.gop-btn-group {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.gop-join-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6426 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  height: 76rpx;
  line-height: 76rpx;
  border-radius: 22rpx;
  border: none;
  box-shadow: 0 6rpx 20rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.35));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.gop-join-btn.btn-free-mode {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #10b981 0%, #059669 100%));
  box-shadow: 0 6rpx 20rpx rgba(16, 185, 129, 0.35);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── 🚩 已加入大组织但未加入下属跑团 ── */
.subclubs-entry-section {
  margin-bottom: 24rpx;
}

.choose-subclub-card {
  padding: 30rpx 28rpx;
}

.csc-intro-text {
  font-size: 23rpx;
  color: var(--rgm-text-2, #9ca3af);
  line-height: 1.5;
  margin-bottom: 24rpx;
  display: block;
}

.subclubs-grid-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.subclub-item-box {
  display: flex;
  align-items: center;
  background: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 22rpx;
  gap: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.sc-logo-img {
  width: 96rpx;
  height: 96rpx;
  border-radius: 20rpx;
  flex-shrink: 0;
}

.sc-content-box {
  flex: 1;
  min-width: 0;
}

.sc-name-line {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 6rpx;
}

.sc-name-title {
  font-size: 28rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.sc-city-tag {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.sc-desc-line {
  font-size: 21rpx;
  color: var(--rgm-text-3, #71717a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 6rpx;
  display: block;
}

.sc-meta-line {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
  display: block;
}

.sc-join-action-btn {
  height: 60rpx;
  line-height: 60rpx;
  padding: 0 28rpx;
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 18rpx;
  border: none;
  flex-shrink: 0;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── Modal Form Enhancements ── */
.req-star {
  color: var(--rgm-red, #ef4444);
  margin-left: 6rpx;
}

.gender-segmented-row {
  display: flex;
  gap: 20rpx;
}

.gender-pill {
  flex: 1;
  text-align: center;
  padding: 18rpx 0;
  background: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 18rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-size: 26rpx;
  font-weight: bold;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gender-pill.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-brand-text, #fc4c02);
}

.picker-display-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 18rpx;
  padding: 20rpx 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.picker-value {
  font-size: 26rpx;
  color: var(--rgm-text, #ffffff);
}

.picker-arrow {
  font-size: 24rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.field-hint {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
  margin-top: 8rpx;
  display: block;
}

.org-submit-btn {
  margin-top: 36rpx;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6426 100%));
  box-shadow: 0 8rpx 24rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.35));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.org-panel-foot .org-submit-btn {
  margin-top: 0;
}

.org-skip-later-btn {
  margin-top: 16rpx;
  height: 72rpx;
  line-height: 72rpx;
  border-radius: 999rpx;
  font-size: 26rpx;
  font-weight: 600;
  background: transparent;
  color: var(--rgm-text-2, #a1a1aa);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.16));
}

.org-skip-later-btn::after {
  border: none;
}

.m-class-tag {
  font-size: 20rpx;
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
  background: var(--rgm-brand-tint, rgba(255, 159, 10, 0.15));
  color: var(--rgm-brand-text, #ff9f0a);
  border: 1rpx solid var(--rgm-brand-line, rgba(255, 159, 10, 0.28));
  font-weight: 700;
  white-space: nowrap;
}

.m-class-tag.is-empty {
  background: var(--rgm-card-3, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text-2, #a1a1aa);
  border-color: var(--rgm-line-solid, rgba(255, 255, 255, 0.12));
}

.m-gobi-tag {
  font-size: 20rpx;
  font-weight: 700;
  padding: 4rpx 14rpx;
  border-radius: 10rpx;
  background: var(--rgm-brand-tint, rgba(255, 159, 10, 0.15));
  color: var(--rgm-brand-text, #ff9f0a);
  border: 1rpx solid var(--rgm-brand-line, rgba(255, 159, 10, 0.3));
  white-space: nowrap;
}

.m-gobi-tag.is-new {
  background: rgba(16, 185, 129, 0.14);
  color: var(--rgm-green, #10b981);
  border-color: rgba(16, 185, 129, 0.35);
}

.program-chips-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
  margin-top: 8rpx;
}

.program-chip {
  padding: 12rpx 20rpx;
  border-radius: 14rpx;
  background: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-2, #a1a1aa);
  font-size: 23rpx;
  font-weight: 500;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.program-chip.active {
  background: rgba(255, 159, 10, 0.15);
  border-color: #ff9f0a;
  color: var(--rgm-amber, #ff9f0a);
  font-weight: bold;
}

.field-preview-tag {
  font-size: 21rpx;
  color: var(--rgm-amber, #ff9f0a);
  margin-top: 8rpx;
  display: block;
}

.gobi-type-segmented-row {
  display: flex;
  gap: 16rpx;
  margin-top: 8rpx;
}

.gobi-type-pill {
  flex: 1;
  text-align: center;
  padding: 18rpx 0;
  background: var(--rgm-card, #18181c);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 18rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-size: 24rpx;
  font-weight: bold;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.gobi-type-pill.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-brand-text, #fc4c02);
}

.vet-gobi-box {
  background: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 18rpx;
  padding: 18rpx;
  margin-top: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.vet-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.vet-label {
  font-size: 23rpx;
  color: var(--rgm-text-2, #d1d5db);
  font-weight: 500;
}

.vet-picker-box {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: var(--rgm-card-2, #1c1c22);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  padding: 8rpx 18rpx;
  border-radius: 12rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.vpb-value {
  font-size: 24rpx;
  color: var(--rgm-amber, #ff9f0a);
  font-weight: bold;
}

.vpb-arrow {
  font-size: 18rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.group-pills-row {
  display: flex;
  gap: 10rpx;
}

.grp-pill {
  padding: 8rpx 20rpx;
  border-radius: 12rpx;
  background: var(--rgm-card-2, #1c1c22);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text-2, #9ca3af);
  font-size: 22rpx;
  font-weight: bold;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.grp-pill.active {
  background: rgba(255, 159, 10, 0.2);
  border-color: #ff9f0a;
  color: var(--rgm-amber, #ff9f0a);
}

.vet-summary-row {
  border-top: 1rpx dashed var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding-top: 10rpx;
}

.vet-summary-text {
  font-size: 21rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.vst-badge {
  color: var(--rgm-amber, #ff9f0a);
  font-weight: bold;
}

.m-status-pill {
  font-size: 19rpx;
  font-weight: 700;
  padding: 3rpx 12rpx;
  border-radius: 8rpx;
  background: rgba(16, 185, 129, 0.15);
  color: var(--rgm-green, #10b981);
  white-space: nowrap;
  flex-shrink: 0;
}

.m-status-pill.pending {
  background: rgba(245, 158, 11, 0.16);
  color: var(--rgm-brand-text, #f59e0b);
}

.m-status-pill.temporary {
  background: var(--rgm-card-3, rgba(245, 158, 11, 0.14));
  color: var(--rgm-text-2, #f59e0b);
  border: 1rpx solid var(--rgm-line-solid, rgba(245, 158, 11, 0.3));
}

.confirmed-label {
  font-size: 22rpx;
  color: var(--rgm-green, #10b981);
  font-weight: bold;
  white-space: nowrap;
}

.m-role-badge {
  font-size: 19rpx;
  font-weight: bold;
  padding: 3rpx 10rpx;
  border-radius: 8rpx;
  white-space: nowrap;
  flex-shrink: 0;
}

.m-role-badge.owner {
  background: rgba(245, 158, 11, 0.2);
  color: var(--rgm-brand-text, #fbbf24);
  border: 1rpx solid rgba(245, 158, 11, 0.4);
}

.m-role-badge.admin {
  background: rgba(59, 130, 246, 0.16);
  color: var(--rgm-text, #60a5fa);
  border: 1rpx solid rgba(59, 130, 246, 0.38);
}

.appoint-admin-pill {
  background: rgba(59, 130, 246, 0.16);
  color: var(--rgm-text, #60a5fa);
  border: 1rpx solid rgba(59, 130, 246, 0.38);
}

.revoke-admin-pill {
  background: rgba(239, 68, 68, 0.15);
  color: var(--rgm-red, #f87171);
  border: 1rpx solid rgba(239, 68, 68, 0.32);
}

.bg-blue {
  background: rgba(14, 165, 233, 0.15);
  color: var(--rgm-blue, #0ea5e9);
  border: 1rpx solid rgba(14, 165, 233, 0.3);
}

.bg-green {
  background: rgba(16, 185, 129, 0.15);
  color: var(--rgm-green, #10b981);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
}

/* ── Join Mode Badges & Buttons ── */
.mode-badge-pill {
  font-size: 18rpx;
  font-weight: bold;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  flex-shrink: 0;
}

.mode-badge-pill.mode-free {
  background: rgba(16, 185, 129, 0.15);
  color: var(--rgm-green, #10b981);
  border: 1rpx solid rgba(16, 185, 129, 0.3);
}

.mode-badge-pill.mode-invite {
  background: rgba(245, 158, 11, 0.15);
  color: var(--rgm-amber, #f59e0b);
  border: 1rpx solid rgba(245, 158, 11, 0.3);
}

.btn-invite-mode {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #f59e0b 0%, #d97706 100%)) !important;
  color: var(--rgm-text, #ffffff) !important;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── Join Mode Setting Modal ── */
.join-mode-modal {
  width: 92%;
  max-width: 670rpx;
  background: var(--rgm-card, #141416);
  border-radius: 32rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 36rpx 32rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.jm-basic-info-section {
  background: var(--rgm-card-2, #18181f);
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.08));
  border-radius: 22rpx;
  padding: 22rpx;
  margin-bottom: 22rpx;
}

.jm-text-input {
  width: 100%;
  height: 76rpx;
  background: var(--rgm-card, #0f0f12);
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.14));
  border-radius: 16rpx;
  padding: 0 22rpx;
  font-size: 26rpx;
  font-weight: 600;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 16rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink);
}

.jm-options-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  margin-bottom: 22rpx;
}

.jm-option-card {
  display: flex;
  align-items: center;
  gap: 18rpx;
  background: var(--rgm-card-2, #1c1c20);
  border: 1.5rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.08));
  border-radius: 22rpx;
  padding: 22rpx 24rpx;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.jm-option-card.is-selected {
  border-color: var(--rgm-brand, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.08));
}

.jm-opt-radio {
  font-size: 28rpx;
  line-height: 1;
  flex-shrink: 0;
}

.jm-radio-dot {
  color: var(--rgm-brand, #fc4c02);
}

.jm-radio-circle {
  color: var(--rgm-text-3, #71717a);
}

.jm-opt-content {
  flex: 1;
  min-width: 0;
}

.jm-opt-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.jm-opt-title {
  font-size: 27rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.jm-rec-tag {
  font-size: 18rpx;
  font-weight: bold;
  background: rgba(16, 185, 129, 0.16);
  color: var(--rgm-green, #10b981);
  border: 1rpx solid rgba(16, 185, 129, 0.38);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
}

.jm-code-manage-section {
  background: var(--rgm-card-2, #18181c);
  border: 1rpx solid var(--rgm-brand-line, rgba(245, 158, 11, 0.28));
  border-radius: 22rpx;
  padding: 22rpx;
  margin-bottom: 8rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.jm-section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14rpx;
}

.jm-section-title {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--rgm-text, #fbbf24);
}

.jm-code-input-row {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 16rpx;
}

.jm-code-actions-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.jm-code-input {
  flex: 1;
  min-width: 0;
  height: 76rpx;
  background: var(--rgm-card, #0f0f12);
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.15));
  border-radius: 16rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  font-family: monospace;
  font-weight: 800;
  color: var(--rgm-brand-text, #fbbf24);
  letter-spacing: 2rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.jm-action-btn {
  margin: 0;
  height: 72rpx;
  line-height: 1.25;
  padding: 0 22rpx;
  font-size: 23rpx;
  font-weight: 800;
  border-radius: 16rpx;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  flex-shrink: 0;
  box-sizing: border-box;
}

.jm-action-btn::after {
  border: none;
}

.jm-gen-btn {
  height: 76rpx;
  background: var(--rgm-card-3, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text, #e4e4e7);
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.15));
}

.jm-copy-btn {
  flex: 1;
  background: var(--rgm-brand-tint, rgba(245, 158, 11, 0.15));
  color: var(--rgm-brand-text, #f59e0b);
  border: 1rpx solid var(--rgm-brand-line, rgba(245, 158, 11, 0.35));
}

.jm-share-btn {
  flex: 1.25;
  background: rgba(16, 185, 129, 0.14);
  color: var(--rgm-green, #10b981);
  border: 1rpx solid rgba(16, 185, 129, 0.36);
}

/* ── Unified Modal Bottom Action Row (Cancel + Submit) ── */
.modal-btn-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-top: 28rpx;
}

.btn-cancel,
.btn-submit {
  margin: 0;
  height: 84rpx;
  line-height: 1.25;
  padding: 0 28rpx;
  border-radius: 22rpx;
  font-size: 27rpx;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  white-space: nowrap;
}

.btn-cancel::after,
.btn-submit::after {
  border: none;
}

.btn-cancel {
  flex: 1;
  background: var(--rgm-card-3, rgba(255, 255, 255, 0.08));
  color: var(--rgm-ink-2, #d4d4d8);
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.15));
  --rgm-text: var(--rgm-ink);
}

.btn-submit {
  flex: 1.65;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ea580c 100%));
  color: #ffffff;
  border: none;
  box-shadow: 0 8rpx 22rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.28));
  --rgm-text: var(--rgm-on-brand, #ffffff);
}


.jm-code-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-card, #18181c);
  border: 1rpx solid rgba(245, 158, 11, 0.3);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 28rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.jm-code-left {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.jm-code-label {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.jm-code-val {
  font-size: 32rpx;
  font-weight: 900;
  font-family: monospace;
  color: var(--rgm-amber, #f59e0b);
  letter-spacing: 4rpx;
}

/* ── Club Code Prompt Modal ── */
.club-code-prompt-modal {
  width: 88%;
  max-width: 620rpx;
  background: var(--rgm-card, #141416);
  border-radius: 32rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 36rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.prompt-target-banner {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 16rpx;
}

.ptb-label {
  font-size: 22rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.ptb-name {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}


.club-code-input {
  width: 100%;
  height: 88rpx;
  background: var(--rgm-card-2, #1c1c20);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
  border-radius: 20rpx;
  color: var(--rgm-text, #ffffff);
  font-size: 36rpx;
  font-weight: bold;
  text-align: center;
  font-family: monospace;
  letter-spacing: 6rpx;
  margin-bottom: 32rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.club-code-input:focus {
  border-color: var(--rgm-brand, #fc4c02);
}

/* ── Privacy Security Notice & Security Badges ── */
.privacy-security-notice {
  background: rgba(16, 185, 129, 0.08);
  border: 1rpx solid rgba(16, 185, 129, 0.25);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
}

.privacy-badge-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 10rpx;
}

.privacy-badge-icon {
  font-size: 28rpx;
}

.privacy-badge-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-green, #10b981);
}

.privacy-badge-tag {
  font-size: 20rpx;
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.15);
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
  font-family: monospace;
}

.privacy-security-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.6;
}

.org-free-join-banner {
  background: rgba(16, 185, 129, 0.08);
  border: 1rpx solid rgba(16, 185, 129, 0.25);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 20rpx;
}

.ofj-header-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 8rpx;
}

.ofj-icon {
  font-size: 26rpx;
}

.ofj-title {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-green, #10b981);
}

.ofj-desc {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.5;
  display: block;
  margin-bottom: 12rpx;
}

.ofj-switch-code {
  display: inline-block;
}

.ofj-switch-text {
  font-size: 22rpx;
  color: var(--rgm-blue, #60a5fa);
  text-decoration: underline;
}

.label-with-icon-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8rpx;
}

.field-security-pill {
  font-size: 20rpx;
  color: var(--rgm-green, #10b981);
  background: rgba(16, 185, 129, 0.12);
  border: 1rpx solid rgba(16, 185, 129, 0.25);
  padding: 2rpx 10rpx;
  border-radius: 10rpx;
}

/* ── Secure Privacy Input & Eye Toggle ── */
.secure-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}

.secure-input {
  flex: 1;
  padding-right: 76rpx !important;
}

.eye-toggle-btn {
  position: absolute;
  right: 12rpx;
  top: 50%;
  transform: translateY(-50%);
  width: 60rpx;
  height: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.eye-icon {
  font-size: 32rpx;
  opacity: 0.85;
}

.eye-toggle-btn:active .eye-icon {
  opacity: 1;
  transform: scale(1.1);
}

.secure-picker-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  width: 100%;
}

.secure-picker-flex {
  flex: 1;
}

.secure-picker-row .eye-toggle-btn {
  position: static;
  transform: none;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 16rpx;
  width: 80rpx;
  height: 80rpx;
}

/* ── Club Report Modal Styles ── */
.tool-icon-box.bg-gold {
  background-color: rgba(255, 215, 0, 0.2);
}

.mode-badge-pill.mode-report {
  color: var(--rgm-amber, #ffd700);
  background: rgba(255, 215, 0, 0.15);
  border: 1rpx solid rgba(255, 215, 0, 0.4);
}

.count-pill.report-owner-pill {
  color: var(--rgm-amber, #ffd700);
  background: rgba(255, 215, 0, 0.15);
  border: 1rpx solid rgba(255, 215, 0, 0.35);
}

.report-modal-content {
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.report-sub-tabs {
  display: flex;
  gap: 12rpx;
  margin-top: 14rpx;
  margin-bottom: 16rpx;
}

.report-sub-tab {
  flex: 1;
  text-align: center;
  padding: 12rpx 0;
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text-2, #9ca3af);
  background: var(--rgm-card-2, #1c1c1e);
  border-radius: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.report-sub-tab.active {
  color: var(--rgm-amber, #ffd700);
  background: rgba(255, 215, 0, 0.12);
  border-color: rgba(255, 215, 0, 0.4);
}

.report-loading-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60rpx 0;
  gap: 16rpx;
}

.loading-spinner {
  font-size: 40rpx;
}

.loading-text {
  font-size: 24rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.report-scroll-body {
  max-height: 64vh;
  padding-right: 4rpx;
}

.report-period-banner {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(255, 215, 0, 0.12) 0%, rgba(252, 76, 2, 0.08) 100%));
  border: 1rpx solid rgba(255, 215, 0, 0.25);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 20rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rpb-title {
  font-size: 26rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.rpb-dates {
  font-size: 20rpx;
  color: var(--rgm-amber, #ffd700);
}

.report-metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14rpx;
  margin-bottom: 20rpx;
}

.rmg-card {
  background: var(--rgm-card, #18181b);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 14rpx;
  padding: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rmg-label {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.rmg-val-row {
  display: flex;
  align-items: baseline;
  gap: 6rpx;
}

.rmg-val {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.rmg-val.highlight {
  color: var(--rgm-brand-text, #fc4c02);
}

.rmg-unit {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

.report-section-box {
  background: var(--rgm-card, #18181b);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 16rpx;
  padding: 18rpx;
  margin-bottom: 20rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rsb-title {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-amber, #ffd700);
  margin-bottom: 12rpx;
  display: block;
}

.podium-list {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.podium-item {
  display: flex;
  align-items: center;
  gap: 12rpx;
  background: var(--rgm-card-2, #202024);
  border-radius: 12rpx;
  padding: 12rpx 16rpx;
  border-left: 6rpx solid #71717a;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.podium-item.podium-1 {
  border-left-color: #ffd700;
  background: rgba(255, 215, 0, 0.06);
}

.podium-item.podium-2 {
  border-left-color: #c0c0c0;
  background: rgba(192, 192, 192, 0.06);
}

.podium-item.podium-3 {
  border-left-color: var(--rgm-brand, #cd7f32);
  background: var(--rgm-brand-tint, rgba(205, 127, 50, 0.06));
}

.podium-medal {
  font-size: 28rpx;
}

.podium-avatar {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
}

.podium-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.podium-name {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.podium-sub {
  font-size: 18rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.podium-right {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.podium-km {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.podium-km-unit {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
}

.empty-podium-text {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
  text-align: center;
  padding: 16rpx 0;
}

.report-highlights-row {
  display: flex;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.highlight-card {
  flex: 1;
  background: var(--rgm-card, #18181b);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 14rpx;
  padding: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.hc-tag {
  font-size: 18rpx;
  color: var(--rgm-blue, #38bdf8);
  font-weight: bold;
}

.hc-name {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.hc-detail {
  font-size: 18rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.canova-box {
  border-color: var(--rgm-brand-line, rgba(191, 90, 242, 0.3));
  background: var(--rgm-card, linear-gradient(135deg, rgba(191, 90, 242, 0.06) 0%, #18181b 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.canova-header {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 10rpx;
}

.canova-icon {
  font-size: 24rpx;
}

.canova-title {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #bf5af2);
}

.canova-critique-text {
  font-size: 20rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.6;
}

.forward-box {
  border-color: rgba(34, 197, 94, 0.3);
  background: var(--rgm-card, #121214);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.forward-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.forward-title {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-green, #22c55e);
}


.forward-preview-card {
  background: var(--rgm-bg, #0a0a0c);
  border-radius: 12rpx;
  padding: 16rpx;
  border: 1rpx dashed var(--rgm-line, rgba(255, 255, 255, 0.15));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.forward-preview-text {
  font-size: 20rpx;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.6;
  white-space: pre-wrap;
  font-family: monospace;
}

.report-footer-actions {
  display: flex;
  gap: 12rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.btn-copy-forward {
  flex: 1.8;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #22c55e 0%, #16a34a 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: none;
  line-height: 1.4;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.btn-download-report {
  flex: 1;
  background: var(--rgm-card-3, #27272a);
  color: var(--rgm-text, #e4e4e7);
  font-size: 22rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  line-height: 1.4;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── Poster Card & View Mode Styles ── */
.report-view-mode-tabs {
  display: flex;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.report-view-tab {
  flex: 1;
  text-align: center;
  padding: 12rpx 0;
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-text-2, #9ca3af);
  background: var(--rgm-card, #18181c);
  border-radius: 12rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.report-view-tab.active {
  color: #000000;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #ffd700 0%, #f59e0b 100%));
  border-color: var(--rgm-brand, #f59e0b);
  box-shadow: 0 4rpx 14rpx rgba(245, 158, 11, 0.25);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.poster-card-wrapper {
  padding: 8rpx 0 20rpx 0;
}

.report-poster-card {
  background: var(--rgm-card, linear-gradient(180deg, #11141d 0%, #151824 50%, #0c0d14 100%));
  border: 2rpx solid rgba(255, 215, 0, 0.35);
  border-radius: 28rpx;
  padding: 30rpx 26rpx;
  box-shadow: 0 12rpx 36rpx var(--rgm-shadow, rgba(0, 0, 0, 0.6)), inset 0 0 40rpx rgba(255, 215, 0, 0.04);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.poster-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
  padding-bottom: 18rpx;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
}

.poster-brand-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.poster-club-logo {
  width: 72rpx;
  height: 72rpx;
  border-radius: 50%;
  border: 2rpx solid #ffd700;
}

.poster-club-titles {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.poster-club-name {
  font-size: 30rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.poster-tagline {
  font-size: 18rpx;
  color: var(--rgm-amber, #ffd700);
  font-weight: bold;
}

.poster-period-pill {
  text-align: right;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.poster-period-name {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.poster-period-date {
  font-size: 18rpx;
  color: var(--rgm-text-2, #9ca3af);
  font-family: monospace;
}

/* Hero Mileage */
.poster-hero-mileage {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(245, 158, 11, 0.08) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 22rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  text-align: center;
}

.phm-label {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
  font-weight: bold;
  letter-spacing: 2rpx;
  text-transform: uppercase;
}

.phm-num-row {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 8rpx;
  margin: 6rpx 0;
}

.phm-num {
  font-size: 72rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #fc4c02);
  line-height: 1;
  font-family: monospace;
}

.phm-unit {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-amber, #f59e0b);
}

.phm-sub {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
}

/* 4-Metrics Bar */
.poster-grid-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.pg-item {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.07));
  border-radius: 16rpx;
  padding: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.pg-label {
  font-size: 18rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.pg-val {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.pg-sub {
  font-size: 16rpx;
  color: var(--rgm-text-3, #71717a);
}

/* Podium Cards */
.poster-podium-box {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border: 1rpx solid rgba(255, 215, 0, 0.25);
  border-radius: 20rpx;
  padding: 18rpx;
  margin-bottom: 20rpx;
}

.ppb-header {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 14rpx;
}

.ppb-icon {
  font-size: 24rpx;
}

.ppb-title {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-amber, #ffd700);
}

.poster-podium-cards {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.ppc-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  background: rgba(0, 0, 0, 0.35);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 14rpx;
  padding: 12rpx 16rpx;
}

.ppc-row.podium-rank-1 {
  background: rgba(255, 215, 0, 0.08);
  border-color: rgba(255, 215, 0, 0.4);
}

.ppc-row.podium-rank-2 {
  background: rgba(192, 192, 192, 0.06);
  border-color: rgba(192, 192, 192, 0.3);
}

.ppc-row.podium-rank-3 {
  background: var(--rgm-brand-tint, rgba(205, 127, 50, 0.06));
  border-color: var(--rgm-brand-line, rgba(205, 127, 50, 0.3));
}

.ppc-rank-badge {
  font-size: 20rpx;
  font-weight: 900;
  min-width: 80rpx;
  color: var(--rgm-amber, #ffd700);
}

.ppc-avatar {
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
}

.ppc-name-col {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.ppc-name {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.ppc-detail {
  font-size: 16rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.ppc-km-col {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.ppc-km {
  font-size: 26rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #fc4c02);
  font-family: monospace;
}

.ppc-km-u {
  font-size: 16rpx;
  color: var(--rgm-text-3, #71717a);
}

/* Highlights Box */
.poster-highlights-box {
  display: flex;
  gap: 10rpx;
  margin-bottom: 20rpx;
}

.phb-item {
  flex: 1;
  background: rgba(56, 189, 248, 0.06);
  border: 1rpx solid rgba(56, 189, 248, 0.25);
  border-radius: 16rpx;
  padding: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.phb-tag {
  font-size: 18rpx;
  color: var(--rgm-blue, #38bdf8);
  font-weight: bold;
}

.phb-name {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.phb-sub {
  font-size: 16rpx;
  color: var(--rgm-text-2, #9ca3af);
}

/* Canova Quote */
.poster-canova-quote {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(191, 90, 242, 0.1) 0%, rgba(191, 90, 242, 0.03) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(191, 90, 242, 0.35));
  border-radius: 18rpx;
  padding: 18rpx;
  margin-bottom: 20rpx;
}

.pcq-header {
  display: flex;
  align-items: center;
  gap: 8rpx;
  margin-bottom: 8rpx;
}

.pcq-icon {
  font-size: 22rpx;
}

.pcq-title {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #bf5af2);
}

.pcq-text {
  font-size: 18rpx;
  color: var(--rgm-text-2, #d1d5db);
  line-height: 1.6;
  font-style: italic;
}

/* Bottom Stamp */
.poster-footer-stamp {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
}

.pfs-left {
  display: flex;
  flex-direction: column;
}

.pfs-brand {
  font-size: 18rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  letter-spacing: 2rpx;
}

.pfs-slogan {
  font-size: 14rpx;
  color: var(--rgm-text-3, #71717a);
}

.pfs-stamp-badge {
  border: 2rpx solid #ffd700;
  border-radius: 8rpx;
  padding: 2rpx 10rpx;
  transform: rotate(-5deg);
}

.pfs-stamp-txt {
  font-size: 16rpx;
  font-weight: bold;
  color: var(--rgm-amber, #ffd700);
  letter-spacing: 2rpx;
}

/* Buttons in Poster View */
.btn-preview-poster {
  flex: 1;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #ffd700 0%, #f59e0b 100%));
  color: #000000;
  font-size: 26rpx;
  font-weight: 900;
  border-radius: 16rpx;
  padding: 18rpx 0;
  text-align: center;
  border: none;
  line-height: 1.4;
  box-shadow: 0 4rpx 14rpx rgba(245, 158, 11, 0.3);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.btn-save-album {
  flex: 1;
  background: var(--rgm-brand, #16a34a);
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: 800;
  border-radius: 16rpx;
  padding: 18rpx 0;
  text-align: center;
  border: none;
  line-height: 1.4;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.btn-sub-copy {
  flex: 1;
  background: var(--rgm-card-3, #27272a);
  color: var(--rgm-text, #e4e4e7);
  font-size: 20rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  line-height: 1.4;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── Poster Member Progress Box ── */
.poster-member-progress-box {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border: 1rpx solid rgba(255, 215, 0, 0.25);
  border-radius: 20rpx;
  padding: 18rpx;
  margin-bottom: 20rpx;
}

.pmb-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.pmb-title-left {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.pmb-icon {
  font-size: 24rpx;
}

.pmb-title {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-amber, #ffd700);
}

.pmb-rate-pill {
  font-size: 18rpx;
  font-weight: bold;
  color: var(--rgm-green, #22c55e);
  background: rgba(34, 197, 94, 0.12);
  border: 1rpx solid rgba(34, 197, 94, 0.3);
  border-radius: 20rpx;
  padding: 2rpx 12rpx;
}

.poster-progress-table {
  display: flex;
  flex-direction: column;
}

.ppt-head-row {
  display: flex;
  align-items: center;
  padding: 8rpx 10rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border-radius: 10rpx;
  margin-bottom: 6rpx;
}

.ppt-th {
  font-size: 18rpx;
  color: var(--rgm-text-2, #9ca3af);
  font-weight: bold;
}

.th-member {
  flex: 1.5;
}

.th-target {
  width: 90rpx;
  text-align: center;
}

.th-actual {
  width: 90rpx;
  text-align: center;
}

.th-rate {
  width: 100rpx;
  text-align: right;
}

.ppt-body-row {
  display: flex;
  align-items: center;
  padding: 10rpx;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
}

.ppt-td {
  font-size: 20rpx;
  color: var(--rgm-text, #e4e4e7);
}

.td-member {
  flex: 1.5;
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.ppt-rank-num {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
  min-width: 24rpx;
}

.ppt-mini-avatar {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
}

.ppt-name-text {
  font-size: 20rpx;
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150rpx;
}

.td-target {
  width: 90rpx;
  text-align: center;
  color: var(--rgm-text-2, #a1a1aa);
}

.td-actual {
  width: 90rpx;
  text-align: center;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.td-rate {
  width: 100rpx;
  text-align: right;
  font-weight: bold;
}

.rate-achieved {
  color: var(--rgm-green, #4ade80);
}

.rate-pending {
  color: var(--rgm-amber, #fbbf24);
}

.ppt-more-btn {
  text-align: center;
  font-size: 20rpx;
  color: var(--rgm-amber, #ffd700);
  padding: 14rpx 0 6rpx;
  font-weight: bold;
}

/* ── 2. Table Mode (全员列表界面) ── */
.table-mode-container {
  padding: 10rpx 0 20rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

/* Team Goal Overview Card */
.team-goal-overview-card {
  background: linear-gradient(135deg, rgba(255, 215, 0, 0.08) 0%, rgba(245, 158, 11, 0.03) 100%);
  border: 1rpx solid rgba(255, 215, 0, 0.3);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
}

.tgoc-top {
  display: flex;
  align-items: center;
  justify-content: space-around;
  margin-bottom: 16rpx;
}

.tgoc-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4rpx;
}

.tgoc-stat-label {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.tgoc-stat-val {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}

.tgoc-u {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

.val-orange {
  color: var(--rgm-brand-text, #fc4c02);
}

.val-green {
  color: var(--rgm-green, #4ade80);
}

.tgoc-stat-divider {
  width: 1rpx;
  height: 48rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.1));
}

.tgoc-bar-row {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.tgoc-bar-bg {
  width: 100%;
  height: 12rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border-radius: 6rpx;
  overflow: hidden;
}

.tgoc-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #f59e0b 0%, #22c55e 100%);
  border-radius: 6rpx;
  transition: width 0.4s ease;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.tgoc-bar-text {
  font-size: 20rpx;
  color: var(--rgm-amber, #ffd700);
  text-align: right;
  font-weight: bold;
}

/* Controls Bar */
.table-controls-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
}

.table-filter-pills {
  display: flex;
  gap: 10rpx;
}

.tf-pill {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
  background: var(--rgm-card-2, #1c1f2b);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 6rpx 16rpx;
  font-weight: bold;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.tf-pill.active {
  color: #000000;
  background: var(--rgm-brand, #ffd700);
  border-color: var(--rgm-brand, #ffd700);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.table-controls-right {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.table-poster-action-pill {
  display: flex;
  align-items: center;
  gap: 6rpx;
  background: rgba(255, 215, 0, 0.12);
  border: 1rpx solid rgba(255, 215, 0, 0.35);
  border-radius: 14rpx;
  padding: 6rpx 14rpx;
}

.table-poster-action-pill:active {
  opacity: 0.8;
  background: rgba(255, 215, 0, 0.22);
}

.tpap-icon {
  font-size: 18rpx;
}

.tpap-text {
  font-size: 19rpx;
  color: var(--rgm-amber, #ffd700);
  font-weight: bold;
}

.table-sort-switch {
  display: flex;
  align-items: center;
  gap: 4rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 14rpx;
  padding: 6rpx 14rpx;
}

.tss-label {
  font-size: 18rpx;
  color: var(--rgm-text-2, #9ca3af);
}

.tss-val {
  font-size: 20rpx;
  color: var(--rgm-amber, #ffd700);
  font-weight: bold;
}

.table-search-row {
  margin-top: -4rpx;
}

.table-search-input {
  background: var(--rgm-card-2, #181b26);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 14rpx;
  padding: 10rpx 18rpx;
  font-size: 22rpx;
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* Member Table Card */
.member-table-card {
  background: var(--rgm-card, #151824);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.mtc-header-row {
  display: flex;
  align-items: center;
  padding: 16rpx 16rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.04));
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.mtc-th {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
  font-weight: bold;
}

.th-col-member {
  flex: 1;
  min-width: 0;
}

.th-col-target {
  width: 90rpx;
  flex-shrink: 0;
  text-align: center;
}

.th-col-actual {
  width: 100rpx;
  flex-shrink: 0;
  text-align: center;
}

.th-col-progress {
  width: 180rpx;
  flex-shrink: 0;
  text-align: right;
}

.mtc-body-list {
  display: flex;
  flex-direction: column;
}

.mtc-row {
  display: flex;
  align-items: center;
  padding: 16rpx 16rpx;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.04));
  transition: background 0.2s;
}

.mtc-row.row-achieved {
  background: rgba(34, 197, 94, 0.03);
}

.td-col-member {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.mtc-rank-badge {
  font-size: 20rpx;
  font-weight: 900;
  width: 24rpx;
  text-align: center;
  color: var(--rgm-text-3, #71717a);
  flex-shrink: 0;
}

.mtc-rank-badge.rank-1 {
  color: var(--rgm-amber, #ffd700);
}

.mtc-rank-badge.rank-2 {
  color: var(--rgm-text-2, #c0c0c0);
}

.mtc-rank-badge.rank-3 {
  color: var(--rgm-brand-text, #cd7f32);
}

.mtc-avatar {
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  flex-shrink: 0;
}

.mtc-name-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2rpx;
  overflow: hidden;
}

.mtc-name-row {
  display: flex;
  align-items: center;
  gap: 6rpx;
  min-width: 0;
}

.mtc-name {
  font-size: 22rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 170rpx;
}

.mtc-role-pill {
  font-size: 16rpx;
  padding: 0 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
  white-space: nowrap;
  flex-shrink: 0;
}

.mtc-role-pill.role-owner {
  color: var(--rgm-amber, #ffd700);
  background: rgba(255, 215, 0, 0.15);
}

.mtc-role-pill.role-coach {
  color: var(--rgm-blue, #38bdf8);
  background: rgba(56, 189, 248, 0.15);
}

.mtc-sub-detail {
  font-size: 17rpx;
  color: var(--rgm-text-3, #71717a);
  white-space: nowrap;
  margin-top: 2rpx;
}

.td-col-target {
  width: 90rpx;
  flex-shrink: 0;
  text-align: center;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2rpx;
}

.mtc-target-val {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.td-col-actual {
  width: 100rpx;
  flex-shrink: 0;
  text-align: center;
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2rpx;
}

.mtc-actual-val {
  font-size: 24rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #fc4c02);
}

.mtc-km-unit {
  font-size: 16rpx;
  color: var(--rgm-text-3, #71717a);
}

.td-col-progress {
  width: 180rpx;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4rpx;
}

.mtc-rate-top {
  display: flex;
  align-items: center;
  gap: 6rpx;
  white-space: nowrap;
}

.mtc-rate-pct {
  font-size: 22rpx;
  font-weight: 900;
  white-space: nowrap;
}

.text-green {
  color: var(--rgm-green, #4ade80);
}

.text-orange {
  color: var(--rgm-amber, #fbbf24);
}

.text-red {
  color: var(--rgm-red, #f87171);
}

.mtc-status-pill {
  font-size: 16rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
  white-space: nowrap;
  flex-shrink: 0;
}

.pill-achieved {
  color: var(--rgm-green, #22c55e);
  background: rgba(34, 197, 94, 0.15);
  border: 1rpx solid rgba(34, 197, 94, 0.3);
}

.pill-pending {
  color: var(--rgm-amber, #f59e0b);
  background: rgba(245, 158, 11, 0.12);
  border: 1rpx solid rgba(245, 158, 11, 0.25);
}

.pill-failed {
  color: var(--rgm-red, #f87171);
  background: rgba(239, 68, 68, 0.12);
  border: 1rpx solid rgba(239, 68, 68, 0.3);
}

.mtc-mini-bar-bg {
  width: 100%;
  height: 6rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border-radius: 3rpx;
  overflow: hidden;
}

.mtc-mini-bar-fill {
  height: 100%;
  border-radius: 3rpx;
}

.fill-green {
  background: linear-gradient(90deg, #4ade80, #22c55e);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.fill-orange {
  background: var(--rgm-brand-grad, linear-gradient(90deg, #f59e0b, #fc4c02));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.fill-red {
  background: linear-gradient(90deg, #f87171, #ef4444);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.mtc-empty-row {
  padding: 40rpx 0;
  text-align: center;
}

.mtc-empty-text {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
}

/* Button in Table View */
.btn-copy-table {
  flex: 1.5;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #ffd700 0%, #f59e0b 100%));
  color: #000000;
  font-size: 24rpx;
  font-weight: 900;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: none;
  line-height: 1.4;
  box-shadow: 0 4rpx 14rpx rgba(245, 158, 11, 0.3);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── Club Suspended Access Block Screen ── */
.club-suspended-block-card {
  text-align: center;
  padding: 48rpx 32rpx;
  background: rgba(239, 68, 68, 0.08);
  border: 1rpx solid rgba(239, 68, 68, 0.35);
  border-radius: 28rpx;
  margin: 20rpx 0 30rpx;
}

.csb-icon-box {
  margin-bottom: 16rpx;
}

.csb-icon {
  font-size: 64rpx;
}

.csb-title {
  font-size: 32rpx;
  font-weight: bold;
  color: var(--rgm-red, #f87171);
  display: block;
  margin-bottom: 16rpx;
}

.csb-desc {
  font-size: 24rpx;
  color: var(--rgm-text, #e5e7eb);
  line-height: 1.6;
  display: block;
  margin-bottom: 32rpx;
  padding: 0 16rpx;
}

.csb-btn-row {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.csb-btn {
  width: 100%;
  font-size: 26rpx;
  font-weight: bold;
  border-radius: 20rpx;
  padding: 20rpx 0;
  text-align: center;
  border: none;
  line-height: 1.4;
}

.csb-btn.primary {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: var(--rgm-text, #ffffff);
  box-shadow: 0 6rpx 20rpx rgba(239, 68, 68, 0.3);
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.csb-btn.secondary {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text, #e5e7eb);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.15));
}

/* ── WeChat Invitation & Share Enhancements ── */
.org-share-tag-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: normal;
  padding: 8rpx 18rpx;
  border-radius: 20rpx;
  margin: 0;
}
.org-share-tag-btn::after {
  border: none;
}

.hero-action-buttons-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-wrap: nowrap;
  margin-top: 16rpx;
}

.club-share-invite-btn {
  flex: 1;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(252, 76, 2, 0.16) 0%, rgba(255, 115, 0, 0.24) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));
  color: var(--rgm-brand-text, #ff6b2b);
  padding: 10rpx 8rpx;
  border-radius: 22rpx;
  font-size: 21rpx;
  font-weight: 600;
  line-height: 1.3;
  margin: 0;
  white-space: nowrap;
}
.club-share-invite-btn.secondary-btn {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  border: 1rpx solid var(--rgm-line-solid, rgba(255, 255, 255, 0.14));
  color: var(--rgm-text, #ffffff);
}
.club-share-invite-btn::after {
  border: none;
}
.csib-icon {
  font-size: 22rpx;
  flex-shrink: 0;
}
.csib-text {
  font-size: 21rpx;
  white-space: nowrap;
}

.jm-share-btn {
  background: rgba(34, 197, 94, 0.15) !important;
  border: 1rpx solid rgba(34, 197, 94, 0.4) !important;
  color: var(--rgm-green, #4ade80) !important;
  font-size: 22rpx !important;
  padding: 0 20rpx !important;
  line-height: 64rpx !important;
  margin-left: 10rpx !important;
}
.jm-share-btn::after {
  border: none;
}

/* ── Club Invite Landing Modal ── */
.club-invite-modal-box {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 32rpx;
  width: 90%;
  max-width: 650rpx;
  overflow: hidden;
  box-shadow: 0 16rpx 48rpx var(--rgm-shadow, rgba(0, 0, 0, 0.75));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.invite-badge-pill {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  font-weight: 600;
}

.invite-body {
  padding: 30rpx;
}

.invite-club-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding-bottom: 24rpx;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.invite-club-logo {
  width: 140rpx;
  height: 140rpx;
  border-radius: 28rpx;
  border: 3rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
  margin-bottom: 18rpx;
  box-shadow: 0 6rpx 20rpx var(--rgm-shadow, rgba(0, 0, 0, 0.4));
}

.invite-club-name {
  font-size: 34rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 12rpx;
}

.invite-meta-row {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12rpx;
  margin-bottom: 16rpx;
}

.invite-pill {
  font-size: 20rpx;
  color: var(--rgm-text-2, #9ca3af);
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
}

.invite-pill.org-pill {
  color: var(--rgm-brand-text, #c084fc);
  background: var(--rgm-brand-tint, rgba(168, 85, 247, 0.15));
}

.invite-club-desc {
  font-size: 24rpx;
  color: var(--rgm-text-2, #9ca3af);
  line-height: 1.5;
  padding: 0 10rpx;
}

.invite-status-strip {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: rgba(16, 185, 129, 0.1);
  border: 1rpx solid rgba(16, 185, 129, 0.32);
  border-radius: 18rpx;
  padding: 20rpx 22rpx;
  margin: 20rpx 0 0 0;
}

.invite-status-strip.org-notice-strip {
  align-items: flex-start;
  background: var(--rgm-brand-tint, rgba(245, 158, 11, 0.1));
  border-color: var(--rgm-brand-line, rgba(245, 158, 11, 0.35));
  margin-top: 16rpx;
}

.iss-icon {
  font-size: 28rpx;
  color: var(--rgm-green, #4ade80);
  font-weight: bold;
  flex-shrink: 0;
  line-height: 1.2;
}

.iss-icon.org-iss-icon {
  width: 48rpx;
  height: 48rpx;
  border-radius: 12rpx;
  background: rgba(245, 158, 11, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  margin-top: 2rpx;
}

.iss-text-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.iss-title {
  font-size: 24rpx;
  font-weight: 800;
  color: var(--rgm-green, #4ade80);
  line-height: 1.4;
}

.iss-title.org-iss-title {
  color: var(--rgm-brand-text, #fbbf24);
}

.iss-sub {
  font-size: 21rpx;
  color: var(--rgm-green, #86efac);
  line-height: 1.45;
}

.iss-sub.org-iss-sub {
  color: var(--rgm-text-2, #fde68a);
}

/* ── Org Invite Verified Banner in Org Modal ── */
.org-invite-verified-banner {
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.12) 0%, rgba(16, 185, 129, 0.18) 100%);
  border: 1rpx solid rgba(34, 197, 94, 0.4);
  border-radius: 16rpx;
  padding: 20rpx;
  margin-bottom: 24rpx;
}

.invite-code-pill-row {
  display: flex;
  margin-top: 12rpx;
}

.verified-code-badge {
  font-size: 22rpx;
  font-weight: 600;
  color: var(--rgm-green, #22c55e);
  background: rgba(34, 197, 94, 0.2);
  padding: 4rpx 16rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(34, 197, 94, 0.35);
}

/* ── 新用户入团微信昵称与头像一键填写卡 ── */
.join-wx-profile-card {
  background: var(--rgm-card-2, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 20rpx;
  padding: 20rpx;
  margin-bottom: 22rpx;
}

.jwp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14rpx;
  gap: 10rpx;
}

.jwp-badge {
  font-size: 22rpx;
  font-weight: 800;
  color: var(--rgm-brand-text, #fc4c02);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  padding: 4rpx 14rpx;
  border-radius: 9999rpx;
  flex-shrink: 0;
}


.jwp-row {
  display: flex;
  align-items: center;
  gap: 18rpx;
}

.jwp-avatar-btn {
  width: 100rpx;
  height: 108rpx;
  padding: 0;
  margin: 0;
  background: var(--rgm-card, #151518);
  border: 1rpx dashed var(--rgm-line-strong, rgba(255, 255, 255, 0.25));
  border-radius: 18rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.jwp-avatar-btn::after {
  border: none;
}

.jwp-avatar-img {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  margin-bottom: 4rpx;
}

.jwp-avatar-placeholder {
  font-size: 36rpx;
  line-height: 1.2;
}

.jwp-avatar-sub {
  font-size: 18rpx;
  color: var(--rgm-text-2, #a0a0a5);
  line-height: 1.2;
}

.jwp-input-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.jwp-label {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.jwp-nickname-input {
  height: 68rpx;
  background: var(--rgm-card, #151518);
  border: 1rpx solid var(--rgm-line-strong, rgba(255, 255, 255, 0.18));
  border-radius: 14rpx;
  padding: 0 20rpx;
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

/* ── 🌱 新队员入团与状态管理页 (New Members Onboarding Status Page) ── */
.new-members-section {
  padding: 28rpx 24rpx;
}

.nm-kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
  margin-bottom: 24rpx;
}

.nm-kpi-tile {
  background: var(--rgm-card-2, #18181f);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 20rpx 22rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.nm-kpi-val {
  font-size: 36rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  line-height: 1.15;
}

.nm-kpi-val.highlight {
  color: var(--rgm-brand-text, #fc4c02);
}

.nm-kpi-val.ok {
  color: var(--rgm-green, #22c55e);
}

.nm-kpi-val.warn {
  color: #f59e0b;
}

.nm-kpi-unit {
  font-size: 22rpx;
  font-weight: 700;
  margin-left: 4rpx;
}

.nm-kpi-label {
  font-size: 23rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  margin-top: 2rpx;
}

.nm-kpi-sub {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.nm-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.nm-filter-pill {
  padding: 10rpx 20rpx;
  border-radius: 999rpx;
  background: var(--rgm-card-2, #18181f);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  font-size: 22rpx;
  font-weight: 600;
  color: var(--rgm-text-2, #a1a1aa);
}

.nm-filter-pill.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.16));
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.45));
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 700;
}

.nm-search-input {
  height: 72rpx;
  background: var(--rgm-card-2, #18181f);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  border-radius: 16rpx;
  padding: 0 24rpx;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 20rpx;
}

.nm-card-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.nm-member-card {
  background: var(--rgm-card-2, #18181f);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 22rpx;
  padding: 22rpx;
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.nm-member-card.is-pending {
  border-color: rgba(245, 158, 11, 0.35);
}

.nm-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14rpx;
}

.nm-user-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
  min-width: 0;
}

.nm-avatar {
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
  border: 2rpx solid var(--rgm-line, rgba(255, 255, 255, 0.18));
  flex-shrink: 0;
}

.nm-user-meta {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  min-width: 0;
  flex: 1;
}

.nm-name-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-wrap: wrap;
}

.nm-name {
  font-size: 28rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
}

.nm-new-badge {
  font-size: 19rpx;
  font-weight: 700;
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(16, 185, 129, 0.16);
  border: 1rpx solid rgba(16, 185, 129, 0.4);
  color: var(--rgm-green, #10b981);
}

.nm-join-time {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.nm-rel-pill {
  font-size: 20rpx;
  font-weight: 700;
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text-2, #a1a1aa);
  flex-shrink: 0;
}

.nm-rel-pill.recent {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
  color: var(--rgm-brand-text, #fc4c02);
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
}

.nm-status-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14rpx;
}

.nm-status-box {
  border-radius: 16rpx;
  padding: 16rpx 18rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  background: var(--rgm-bg, #111116);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
}

.nm-status-box.status-ok {
  border-color: rgba(34, 197, 94, 0.3);
  background: rgba(34, 197, 94, 0.06);
}

.nm-status-box.status-warn {
  border-color: rgba(245, 158, 11, 0.35);
  background: rgba(245, 158, 11, 0.06);
}

.nm-status-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8rpx;
}

.nm-status-title {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}

.nm-status-tag {
  font-size: 20rpx;
  font-weight: 700;
  padding: 2rpx 12rpx;
  border-radius: 999rpx;
}

.nm-status-tag.ok {
  background: rgba(34, 197, 94, 0.18);
  color: var(--rgm-green, #22c55e);
}

.nm-status-tag.warn {
  background: rgba(245, 158, 11, 0.18);
  color: #f59e0b;
}

.nm-status-desc {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.35;
}

.nm-actions-row {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.nm-act-btn {
  flex: 1;
  margin: 0;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 14rpx;
  font-size: 22rpx;
  font-weight: 700;
  padding: 0 16rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nm-act-btn::after {
  border: none;
}

.nm-act-btn.remind {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  color: var(--rgm-brand-text, #fc4c02);
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
}

.nm-act-btn.inspect {
  background: var(--rgm-tint-2, rgba(255, 255, 255, 0.08));
  color: var(--rgm-text, #ffffff);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.14));
}

.nm-act-btn.remove {
  flex: 0 0 auto;
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
  border: 1rpx solid rgba(239, 68, 68, 0.35);
  padding: 0 22rpx;
}

</style>
