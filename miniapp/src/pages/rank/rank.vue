<template>
  <view class="rank-page" :class="themeClass">
    <!-- 首屏骨架屏：首次进入时盖住尚未加载的数据 -->
    <PageSkeleton v-if="firstLoadPending" overlay />
    <!-- 已改为跑团 Tab 下的二级页，使用原生返回键，不再需要顶部切换胶囊 -->

    <!-- If user belongs to a club -->
    <view v-if="currentClub" class="rank-content">
      <!-- ── 跑团简要上下文横幅与切换 ── -->
      <view class="club-context-bar">
        <image
          class="club-logo-mini"
          :src="currentClub.logo_url || '/static/logo-square.png'"
          mode="aspectFill"
          @click="goToTeamPage"
        />
        <view class="club-meta" @click="goToTeamPage">
          <view class="club-name-row">
            <text class="club-title">{{ currentClub.name }}</text>
            <text class="role-badge" :class="'role-' + currentRole">
              {{ currentRole === "owner" ? "👑 团长" : currentRole === "coach" ? "🧢 教练" : "🏃 团员" }}
            </text>
          </view>
        </view>
        <view v-if="userClubs.length > 1" class="switch-club-pill" @click="showSwitchModal = true">
          <text class="switch-icon">⇄</text>
          <text class="switch-text">切换跑团</text>
        </view>
        <view v-else class="enter-team-hint" @click="goToTeamPage">
          <text class="hint-text">跑团主页</text>
          <text class="arrow">›</text>
        </view>
      </view>

      <!-- ── 🚫 跑团访问权限已暂停阻断屏 ── -->
      <view v-if="currentClub.is_access_suspended || isRankSuspended" class="section-card club-suspended-block-card">
        <view class="csb-icon-box">
          <text class="csb-icon">🚫</text>
        </view>
        <text class="csb-title">大群访问权限已暂停</text>
        <text class="csb-desc">
          跑团【{{ currentClub.name }}】隶属于【{{ currentClub.org_name || '大群' }}】。{{ rankSuspensionReason || '临时访问期已过，请补齐必填资料并等待审核。' }}
        </text>
        <view class="csb-btn-row">
          <button class="csb-btn primary" @click="goToProfilePage">
            📝 补齐必填资料
          </button>
          <button v-if="userClubs.length > 1" class="csb-btn secondary" @click="showSwitchModal = true">
            ⇄ 切换至其他跑团
          </button>
        </view>
      </view>

      <!-- 正常榜单与动态 -->
      <view v-else>
        <!-- ── SECTION 0: 🏃 跑团近期约跑与拉练 (置顶卡片 · 一键参加) ── -->
        <view v-if="featuredGroupRun" class="group-run-hero-card">
          <!-- 卡片头部：状态与倒计时 -->
          <view class="grh-header-row">
            <view class="grh-badge-box">
              <view class="grh-pulse-dot" />
              <text class="grh-badge-title">🏃 最新约跑</text>
              <text v-if="featuredGroupRun.repeat_rule === 'weekly'" class="grh-repeat-pill">🔄 每周例跑</text>
            </view>
            <view class="grh-header-right" @click="goToTeamEvents">
              <text class="grh-countdown">{{ getCountdownText(featuredGroupRun.meet_time || featuredGroupRun.start_date) }}</text>
              <text class="grh-arrow">全部活动 ›</text>
            </view>
          </view>

          <!-- 卡片主体：封面图与核心信息 -->
          <view class="grh-main" @click="goToTeamEvents">
            <image
              class="grh-cover-image"
              :src="featuredGroupRun.cover_image || 'https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=800&auto=format&fit=crop&q=80'"
              mode="aspectFill"
            />
            <view class="grh-info-col">
              <view class="grh-title-row">
                <text class="grh-title">{{ featuredGroupRun.title }}</text>
                <text v-if="featuredGroupRun.is_joined" class="grh-joined-status-tag">✓ 已报名</text>
              </view>

              <!-- 时间 -->
              <view class="grh-detail-line">
                <text class="gdl-icon">⏰</text>
                <text class="gdl-text highlight">{{ formatMeetTime(featuredGroupRun.meet_time || featuredGroupRun.start_date) }}</text>
              </view>

              <!-- 地点 -->
              <view class="grh-detail-line" @click.stop="handleOpenMap(featuredGroupRun)">
                <text class="gdl-icon">📍</text>
                <text class="gdl-text">{{ featuredGroupRun.location || '跑团集合点' }}</text>
                <text class="gdl-nav-hint">导航 ›</text>
              </view>

              <!-- 目标与配速 -->
              <view class="grh-tags-row">
                <view class="grh-tag orange">
                  <text class="gt-icon">🎯</text>
                  <text class="gt-text">目标 {{ featuredGroupRun.target_km || 10 }} km</text>
                </view>
                <view class="grh-tag dark" v-if="featuredGroupRun.pace_requirement">
                  <text class="gt-icon">⚡</text>
                  <text class="gt-text">{{ featuredGroupRun.pace_requirement }}</text>
                </view>
              </view>
            </view>
          </view>

          <!-- 发起人与已报名跑友动态条 -->
          <view class="grh-meta-strip">
            <view class="grh-organizer">
              <image
                class="grh-org-avatar"
                :src="featuredGroupRun.creator_avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                mode="aspectFill"
              />
              <text class="grh-org-name">{{ featuredGroupRun.creator_name || '发起人' }}</text>
              <text class="grh-org-badge" :class="featuredGroupRun.creator_role === '团长' ? 'role-owner' : (featuredGroupRun.creator_role === '教练' ? 'role-coach' : 'role-creator')">
                {{ featuredGroupRun.creator_role || '发起人' }}
              </text>
            </view>

            <view class="grh-participants-preview" @click="goToTeamEvents">
              <view class="grh-avatar-stack" v-if="featuredGroupRun.participants && featuredGroupRun.participants.length > 0">
                <image
                  v-for="(p, idx) in featuredGroupRun.participants.slice(0, 4)"
                  :key="p.user_id || idx"
                  class="grh-stack-avatar"
                  :style="{ zIndex: 10 - idx }"
                  :src="p.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                  mode="aspectFill"
                />
              </view>
              <text class="grh-part-count-text">
                {{ featuredGroupRun.participant_count > 0 ? `${featuredGroupRun.participant_count} 人已报名` : '暂无报名 · 抢先加入' }}
              </text>
            </view>
          </view>

          <!-- 底部操作按钮：一键报名 + 转发 vs 已报名操作 -->
          <view class="grh-actions-box">
            <view v-if="!featuredGroupRun.is_joined" style="display: flex; gap: 12rpx; width: 100%;">
              <button
                class="grh-join-btn"
                style="flex: 1.4;"
                :loading="joiningEventId === featuredGroupRun.id"
                :disabled="joiningEventId === featuredGroupRun.id"
                @click.stop="handleJoinGroupRun(featuredGroupRun)"
              >
                🏃 一键报名
              </button>
              <button
                class="grh-sub-btn calendar"
                style="flex: 1;"
                open-type="share"
                :data-share-type="'group_run'"
                @click.stop
              >
                💬 转发
              </button>
            </view>
            <view v-else class="grh-joined-actions">
              <view class="grh-joined-pill">
                <text class="gjp-icon">✓</text>
                <text class="gjp-text">已报名</text>
              </view>
              <button class="grh-sub-btn calendar" open-type="share" :data-share-type="'group_run'" @click.stop>
                💬 转发
              </button>
              <button class="grh-sub-btn calendar" @click.stop="handleAddToCalendar(featuredGroupRun)">
                🔔 日历
              </button>
              <button class="grh-sub-btn leave" @click.stop="handleLeaveGroupRun(featuredGroupRun)">
                退出
              </button>
            </view>
          </view>

          <!-- 若有后续多场约跑，显示快捷入口 -->
          <view v-if="upcomingGroupRuns.length > 1" class="grh-more-runs-bar" @click="goToTeamEvents">
            <text class="gmr-text">📅 还有 {{ upcomingGroupRuns.length - 1 }} 场约跑</text>
            <text class="gmr-link">查看全部活动 ›</text>
          </view>
        </view>

        <!-- ── SECTION 1: 🥇 本月英雄榜（默认展示前三，点击展开 10人/页 完整榜单） ── -->
        <view class="section-card" id="rank-section">
          <view class="card-header-row rank-header-row">
            <view class="title-with-icon">
              <text class="icon">🥇</text>
              <text class="card-title">本月英雄榜</text>
              <text v-if="leaderboard.length" class="count-badge">({{ leaderboard.length }}人)</text>
            </view>
            <view class="header-right-meta">
              <view v-if="myRankItem" class="my-rank-pill" @click="jumpToMyRank">
                <text class="mrp-icon">📍</text>
                <text class="mrp-text">我的排名 #{{ myRankItem.rank }} · {{ myRankItem.distance_km }}km ›</text>
              </view>
            </view>
          </view>

          <view v-if="leaderboard.length" class="leaderboard-list">
            <view
              v-for="item in paginatedLeaderboard"
              :key="item.user_id"
              class="rank-item"
              :class="{
                'top-three': item.rank <= 3,
                'rank-gold': item.rank === 1,
                'rank-silver': item.rank === 2,
                'rank-bronze': item.rank === 3,
                'is-me': item.user_id === user?.id
              }"
            >
              <view class="rank-left">
                <view class="rank-badge-box">
                  <text class="rank-num" :class="'rank-' + item.rank">
                    {{ item.rank === 1 ? '🥇' : item.rank === 2 ? '🥈' : item.rank === 3 ? '🥉' : '#' + item.rank }}
                  </text>
                </view>
                <image
                  class="user-avatar"
                  :src="item.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                  mode="aspectFill"
                />
                <view class="user-info">
                  <view class="name-badge-row">
                    <text class="user-name">{{ item.display_name }}</text>
                    <text v-if="item.user_id === user?.id" class="mini-me-tag">我</text>
                    <text v-if="item.role === 'owner'" class="mini-role-tag owner">团长</text>
                    <text v-else-if="item.role === 'coach'" class="mini-role-tag coach">教练</text>
                  </view>
                  <text class="progress-sub">完成度 {{ item.progress_pct }}% · 目标 {{ item.target_km }}km</text>
                </view>
              </view>

              <view class="rank-right">
                <text class="km-val">{{ item.distance_km }} <text class="unit">km</text></text>
                <view class="progress-bar-bg">
                  <view
                    class="progress-bar-fill"
                    :style="{ width: Math.min(100, item.progress_pct) + '%' }"
                  />
                </view>
              </view>
            </view>

            <!-- 默认收起态：点击展开 10人/页 完整榜单 -->
            <view
              v-if="!isRankExpanded && leaderboard.length > 3"
              class="rank-expand-bar"
              @click="handleExpandRank"
            >
              <text class="reb-text">
                展开完整榜单（共 {{ leaderboard.length }} 人{{ leaderboard.length > rankPageSize ? ` · ${rankPageSize}人/页` : '' }}）
              </text>
              <text class="reb-arrow">▾</text>
            </view>

            <!-- 展开态：10人/页 分页画面 + 收起按钮 -->
            <view v-if="isRankExpanded && leaderboard.length > 3" class="pagination-container">
              <view v-if="totalRankPages > 1" class="pagination-row">
                <button
                  class="page-nav-btn"
                  :class="{ disabled: currentRankPage === 1 }"
                  :disabled="currentRankPage === 1"
                  @click="handleRankPrevPage"
                >
                  ‹ 上一页
                </button>

                <view class="page-pills-row">
                  <view
                    v-for="p in visibleRankPageNumbers"
                    :key="p"
                    class="page-pill"
                    :class="{ active: currentRankPage === p, dots: p === -1 }"
                    @click="p !== -1 && handleRankSetPage(p)"
                  >
                    <text>{{ p === -1 ? '...' : p }}</text>
                  </view>
                </view>

                <button
                  class="page-nav-btn"
                  :class="{ disabled: currentRankPage === totalRankPages }"
                  :disabled="currentRankPage === totalRankPages"
                  @click="handleRankNextPage"
                >
                  下一页 ›
                </button>
              </view>

              <view class="pagination-footer-bar">
                <text class="page-summary-text">
                  第 {{ currentRankPage }} / {{ totalRankPages }} 页 · 展示第 {{ (currentRankPage - 1) * rankPageSize + 1 }} ~ {{ Math.min(currentRankPage * rankPageSize, leaderboard.length) }} 名
                </text>
                <text class="expand-toggle-btn" @click="handleCollapseRank">
                  收起至前三 ▴
                </text>
              </view>
            </view>
          </view>
          <view v-else class="empty-box">
            <text class="empty-icon">🏃</text>
            <text class="empty-text">本月暂无打卡数据</text>
          </view>
        </view>

      <!-- ── SECTION 2: 🔥 跑团打卡动态 · 跑步记录与AI点评 ── -->
      <view class="section-card" id="feed-section">
        <view class="card-header-row">
          <view class="title-with-icon">
            <text class="icon">🔥</text>
            <text class="card-title">打卡动态</text>
            <text v-if="feed.length" class="count-badge">({{ feed.length }})</text>
          </view>
        </view>

        <!-- 方便浏览的筛选分类 Chips -->
        <view v-if="feed.length" class="feed-filter-scroll">
          <view
            class="feed-filter-chip"
            :class="{ active: activeFeedFilter === 'all' }"
            @click="setFeedFilter('all')"
          >
            <text class="ffc-text">全部 ({{ feed.length }})</text>
          </view>
          <view
            v-if="gpsFeedCount > 0"
            class="feed-filter-chip"
            :class="{ active: activeFeedFilter === 'gps' }"
            @click="setFeedFilter('gps')"
          >
            <text class="ffc-text">🗺️ 含GPS轨迹 ({{ gpsFeedCount }})</text>
          </view>
          <view
            v-if="lsdFeedCount > 0"
            class="feed-filter-chip"
            :class="{ active: activeFeedFilter === 'lsd' }"
            @click="setFeedFilter('lsd')"
          >
            <text class="ffc-text">⚡ 长距离≥10km ({{ lsdFeedCount }})</text>
          </view>
          <view
            v-if="coachFeedCount > 0"
            class="feed-filter-chip"
            :class="{ active: activeFeedFilter === 'coach' }"
            @click="setFeedFilter('coach')"
          >
            <text class="ffc-text">🎯 教练精评 ({{ coachFeedCount }})</text>
          </view>
        </view>

        <view v-if="filteredFeed.length" class="feed-list">
          <view v-for="act in paginatedFeed" :key="act.id" class="feed-card">
            <!-- Member & Run Header -->
            <view class="feed-header">
              <image
                class="feed-avatar"
                :src="act.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                mode="aspectFill"
              />
              <view class="feed-user-meta">
                <view class="feed-author-row">
                  <text class="feed-author">{{ act.display_name }}</text>
                  <text v-if="act.start_time" class="feed-date-chip">{{ formatFeedDate(act.start_time) }}</text>
                </view>
                <text class="feed-act-name">
                  {{ act.name }} · 配速 {{ act.avg_pace_str }} · {{ act.is_biometrics_hidden ? '🔒 心率已保密（仅教练与师傅可见）' : `心率 ${act.average_heartrate || '—'} bpm · TRIMP ${act.trimp || 50}` }}{{ (act.elevation_gain_meters && act.elevation_gain_meters > 0) ? ` · ⛰️ +${Math.round(act.elevation_gain_meters)}m` : '' }}
                </text>
              </view>
              <view class="feed-distance">
                <text class="feed-km">{{ (act.distance_meters / 1000).toFixed(1) }}</text>
                <text class="feed-unit">km</text>
              </view>
            </view>

            <!-- Map Preview or GPS Action Button -->
            <view
              v-if="act.is_gps_hidden"
              style="margin: 12rpx 0 8rpx; padding: 14rpx 20rpx; border-radius: 14rpx; background: var(--rgm-tint, rgba(255,255,255,0.03)); border: 1rpx dashed var(--rgm-line, rgba(255,255,255,0.12)); display: flex; align-items: center; gap: 10rpx;"
            >
              <text style="font-size: 22rpx;">🔒</text>
              <text style="font-size: 21rpx; color: var(--rgm-text-3, #71717a);">轨迹与分段已设为保密</text>
            </view>
            <view
              v-else-if="getRoutePreview(act)"
              class="feed-map-card"
              @click.stop="openTrackModal(act)"
            >
              <image
                class="feed-map-thumb"
                :class="{ 'coros-filter': Boolean(act.map_image_url) }"
                :src="getRoutePreview(act)"
                mode="aspectFit"
              />
              <view class="feed-map-overlay">
                <text class="feed-map-pill">🗺️ 轨迹与分段复盘</text>
              </view>
            </view>
            <view
              v-else-if="!act.is_segment_hidden && (act.has_gps_track || act.id?.startsWith('garmin_') || act.id?.startsWith('coros_'))"
              class="feed-track-action-bar"
              @click.stop="openTrackModal(act)"
            >
              <text class="feed-track-icon">🗺️</text>
              <text class="feed-track-lbl">轨迹与分段复盘</text>
              <text class="feed-track-arr">›</text>
            </view>

            <!-- Coach Critique Bubble -->
            <view
              v-if="!act.is_critique_hidden && (act.ai_journal || act.user_id === user?.id)"
              class="coach-bubble"
            >
              <view class="coach-badge-row">
                <view class="coach-badge-left">
                  <text class="coach-robot-icon">🎯</text>
                  <text class="coach-badge-title">Canova教练点评</text>
                </view>
                <text class="ai-comment-tip">仅供参考</text>
              </view>
              <text class="coach-comment-text">
                {{ act.ai_journal || "点评生成中..." }}
              </text>
            </view>

            <!-- Social Actions (Like & Comment buttons) -->
            <view class="social-bar">
              <view
                class="like-btn"
                :class="{ liked: act.has_liked }"
                @click="handleToggleLike(act)"
              >
                <text class="heart-icon">{{ act.has_liked ? '❤️' : '🤍' }}</text>
                <text class="like-text">
                  {{ act.has_liked ? '已点赞' : '点赞' }} ({{ act.likes_count || 0 }})
                </text>
              </view>
              <view class="comment-trigger-btn" @click="handleOpenCommentModal(act)">
                <text class="cmt-icon">💬</text>
                <text class="cmt-text">留言 ({{ act.comments?.length || 0 }})</text>
              </view>
            </view>

            <!-- Likers Strip (显示点赞者及头像) -->
            <view v-if="act.likers && act.likers.length > 0" class="likers-box">
              <text class="likers-heart">❤️</text>
              <view class="likers-list">
                <view
                  v-for="(lk, lkIdx) in act.likers"
                  :key="lk.user_id || lkIdx"
                  class="liker-chip"
                >
                  <image
                    class="liker-avatar"
                    :src="lk.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                    mode="aspectFill"
                  />
                  <text class="liker-name">{{ lk.display_name || '跑友' }}</text>
                </view>
                <text class="likers-suffix">等 {{ act.likers.length }} 人点赞</text>
              </view>
            </view>

            <!-- Threaded Comments List (跑友留言产生 Thread) -->
            <view v-if="act.comments && act.comments.length > 0" class="comments-box">
              <view
                v-for="thread in getCommentThreads(act.comments)"
                :key="thread.id"
                class="cmt-thread-group"
              >
                <!-- Root Comment -->
                <view class="cmt-root-row" @click="handleOpenCommentModal(act, thread)">
                  <image
                    class="cmt-avatar"
                    :src="thread.author_avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                    mode="aspectFill"
                  />
                  <view class="cmt-body">
                    <view class="cmt-meta-row">
                      <text class="cmt-author">{{ thread.author_name }}</text>
                      <text v-if="thread.created_at" class="cmt-time">{{ formatCommentDate(thread.created_at) }}</text>
                      <view class="cmt-actions">
                        <text class="cmt-reply-link" @click.stop="handleOpenCommentModal(act, thread)">回复</text>
                        <text
                          v-if="thread.user_id === user?.id || currentRole === 'owner'"
                          class="cmt-del-link"
                          @click.stop="handleDeleteComment(act, thread.id)"
                        >删除</text>
                      </view>
                    </view>
                    <text class="cmt-content">{{ thread.content }}</text>
                  </view>
                </view>

                <!-- Child Replies Thread -->
                <view v-if="thread.replies && thread.replies.length > 0" class="cmt-replies-list">
                  <view
                    v-for="rep in thread.replies"
                    :key="rep.id"
                    class="cmt-reply-row"
                    @click="handleOpenCommentModal(act, rep)"
                  >
                    <image
                      class="cmt-avatar mini"
                      :src="rep.author_avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'"
                      mode="aspectFill"
                    />
                    <view class="cmt-body">
                      <view class="cmt-meta-row">
                        <view class="cmt-reply-names">
                          <text class="cmt-author">{{ rep.author_name }}</text>
                          <template v-if="rep.reply_to_name">
                            <text class="cmt-reply-verb">回复</text>
                            <text class="cmt-reply-target">@{{ rep.reply_to_name }}</text>
                          </template>
                        </view>
                        <text v-if="rep.created_at" class="cmt-time">{{ formatCommentDate(rep.created_at) }}</text>
                        <view class="cmt-actions">
                          <text class="cmt-reply-link" @click.stop="handleOpenCommentModal(act, rep)">回复</text>
                          <text
                            v-if="rep.user_id === user?.id || currentRole === 'owner'"
                            class="cmt-del-link"
                            @click.stop="handleDeleteComment(act, rep.id)"
                          >删除</text>
                        </view>
                      </view>
                      <text class="cmt-content">{{ rep.content }}</text>
                    </view>
                  </view>
                </view>
              </view>
            </view>
          </view>

          <!-- 动态分页控制器 -->
          <view v-if="filteredFeed.length > feedPageSize" class="pagination-container feed-pagination">
            <view class="pagination-row">
              <button
                class="page-nav-btn"
                :class="{ disabled: currentFeedPage === 1 }"
                :disabled="currentFeedPage === 1"
                @click="handleFeedPrevPage"
              >
                ‹ 上一页
              </button>

              <view class="page-pills-row">
                <view
                  v-for="p in visibleFeedPageNumbers"
                  :key="p"
                  class="page-pill"
                  :class="{ active: currentFeedPage === p, dots: p === -1 }"
                  @click="p !== -1 && handleFeedSetPage(p)"
                >
                  <text>{{ p === -1 ? '...' : p }}</text>
                </view>
              </view>

              <button
                class="page-nav-btn"
                :class="{ disabled: currentFeedPage === totalFeedPages }"
                :disabled="currentFeedPage === totalFeedPages"
                @click="handleFeedNextPage"
              >
                下一页 ›
              </button>
            </view>

            <view class="pagination-footer-bar center">
              <text class="page-summary-text">
                第 {{ currentFeedPage }} / {{ totalFeedPages }} 页 · 展示第 {{ (currentFeedPage - 1) * feedPageSize + 1 }} ~ {{ Math.min(currentFeedPage * feedPageSize, filteredFeed.length) }} 条（共 {{ filteredFeed.length }} 条记录）
              </text>
            </view>
          </view>

          <!-- 跨月历史加载入口 -->
          <view v-if="hasMoreFeed" class="older-feed-box">
            <button
              class="load-more-btn older-feed-btn"
              :loading="loadingMoreFeed"
              :disabled="loadingMoreFeed"
              @click="handleLoadMoreFeed"
            >
              {{ loadingMoreFeed ? '加载中...' : `📅 加载更早打卡（共 ${feedTotal} 条）` }}
            </button>
          </view>
          <view v-else class="no-more-text">
            ✓ 已全部展示（共 {{ filteredFeed.length }} 条）
          </view>
        </view>
        <view v-else class="empty-box">
          <text class="empty-icon">👟</text>
          <text class="empty-text">当前筛选分类暂无打卡记录</text>
        </view>
      </view>
    </view>
    </view>

    <!-- ── Unjoined Empty State (未加入任何跑团) ── -->
    <view v-else class="unjoined-view">
      <view class="unjoined-card">
        <text class="unjoined-icon">🏅</text>
        <text class="unjoined-title">尚未加入跑团</text>
        <text class="unjoined-desc">
          加入跑团后即可查看榜单
        </text>
        <button class="goto-team-btn" @click="goToTeamPage">
          去加入跑团
        </button>
      </view>
    </view>

    <!-- ── Write Comment Modal (互动留言/回复 Thread 弹窗) ── -->
    <view
      v-if="showCommentModal"
      class="modal-mask"
      @click="showCommentModal = false"
      @touchmove.stop.prevent
    >
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">
            {{ replyTargetComment ? `回复 @${replyTargetComment.author_name}` : '留言' }}
          </text>
          <text class="close-btn" @click="showCommentModal = false">✕</text>
        </view>
        <view class="modal-body">
          <!-- Reply Target Banner -->
          <view v-if="replyTargetComment" class="reply-target-banner">
            <view class="rtb-left">
              <text class="rtb-label">正在回复 @{{ replyTargetComment.author_name }}：</text>
              <text class="rtb-quote">{{ replyTargetComment.content }}</text>
            </view>
            <text class="rtb-cancel" @click="replyTargetComment = null">取消回复</text>
          </view>

          <!-- Quick Comment Presets -->
          <view class="quick-cmt-chips">
            <view
              v-for="(preset, pIdx) in quickCommentPresets"
              :key="pIdx"
              class="qcc-pill"
              @click="commentTextInput = preset"
            >
              <text class="qcc-text">{{ preset }}</text>
            </view>
          </view>

          <textarea
            class="textarea-input"
            :adjust-position="true"
            :cursor-spacing="30"
            :placeholder="replyTargetComment ? `回复 @${replyTargetComment.author_name}：聊聊配速、心率或互动交流...` : '为队友加油、讨论训练配速或心率心得...'"
            v-model="commentTextInput"
          />
          <button
            class="submit-btn"
            :loading="submittingComment"
            @click="handleSendComment"
          >
            {{ replyTargetComment ? '发送回复' : '发送留言' }}
          </button>
        </view>
      </view>
    </view>

    <!-- ── Switch Club Modal (切换已加入的跑团) ── -->
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
                <text v-if="currentClub?.id === c.id" class="mcc-current-tag">当前榜单 ✓</text>
                <button v-else class="mcc-switch-btn" @click.stop="handleSwitchClub(c)">
                  ⇄ 切换
                </button>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- ── GPS 轨迹与高程剖面弹窗 ── -->
    <GpsTrackModal
      :visible="Boolean(selectedTrackActivity)"
      :activity-id="selectedTrackActivity?.id || selectedTrackActivity?.activity_id"
      :initial-activity="selectedTrackActivity"
      @close="selectedTrackActivity = null"
      @share-card="handleShareCardFromTrack"
    />

    <!-- ── 个人打卡分享朋友圈卡片弹窗 ── -->
    <PersonalShareCardModal
      :visible="showPersonalShareModal"
      :activity-id="shareCardActivityId"
      :target-uid="shareCardTargetUid"
      @close="showPersonalShareModal = false"
    />
    <!-- 微信隐私保护指引授权弹窗 -->
    <PrivacyPopup />
  </view>
</template>

<script setup lang="ts">
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import PageSkeleton from "../../components/PageSkeleton.vue";
import PrivacyPopup from "../../components/PrivacyPopup.vue";
import { ref, computed } from "vue";
import { onShow, onPullDownRefresh, onLoad, onShareAppMessage, onShareTimeline } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import { buildGroupRunSharePayload } from "../../utils/groupRun";
import GpsTrackModal from "../../components/GpsTrackModal.vue";
import PersonalShareCardModal from "../../components/PersonalShareCardModal.vue";
import { trackClick, trackModal, trackSubView, trackFunnelStep } from "../../utils/telemetry";
import {
  request,
  getStoredUser,
  checkAndAutoLogin,
  UserProfile,
  getActiveClubId,
  setActiveClubId,
  resolveActiveClub,
  navigateToProfileRequiredFields,
  formatBeijingTime,
} from "../../utils/api";

const selectedTrackActivity = ref<any>(null);
const showPersonalShareModal = ref(false);
const shareCardActivityId = ref<string>("");
const shareCardTargetUid = ref<string>("");

function openTrackModal(act: any) {
  selectedTrackActivity.value = act;
}

function handleShareCardFromTrack(actId?: string) {
  const curAct = selectedTrackActivity.value;
  const resolvedActId = actId || curAct?.id || curAct?.activity_id || "";
  const resolvedUid = curAct?.user_id || user.value?.id || getStoredUser()?.id || "";
  selectedTrackActivity.value = null;
  shareCardActivityId.value = resolvedActId;
  shareCardTargetUid.value = resolvedUid;
  showPersonalShareModal.value = true;
}

const user = ref<UserProfile | null>(null);

const b64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
function base64Encode(str: string): string {
  const utf8Bytes = encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (_, p1) => {
    return String.fromCharCode(parseInt(p1, 16));
  });
  let output = "";
  for (let i = 0; i < utf8Bytes.length; i += 3) {
    const a = utf8Bytes.charCodeAt(i);
    const b = utf8Bytes.charCodeAt(i + 1);
    const c = utf8Bytes.charCodeAt(i + 2);
    output += b64chars.charAt(a >> 2);
    output += b64chars.charAt(((a & 3) << 4) | (b >> 4));
    output += isNaN(b) ? "=" : b64chars.charAt(((b & 15) << 2) | (c >> 6));
    output += isNaN(b) || isNaN(c) ? "=" : b64chars.charAt(c & 63);
  }
  return output;
}

const routeSvgCache = new Map<string, string>();

function getRoutePreview(act: any): string | null {
  if (act.map_image_url) return act.map_image_url;
  if (!act.gps_track_data) return null;

  try {
    let track = act.gps_track_data;
    if (typeof track === "string") {
      track = JSON.parse(track);
    }
    const points = track?.points;
    if (!points || points.length < 2) return null;

    const actId = act.id || "";
    const cacheKey = actId ? `${actId}_${points.length}` : "";
    if (cacheKey && routeSvgCache.has(cacheKey)) {
      return routeSvgCache.get(cacheKey)!;
    }

    const W = 320;
    const H = 140;
    const pad = 16;

    const lats = points.map((p: any) => p.latitude);
    const lngs = points.map((p: any) => p.longitude);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);

    const midLatRad = ((minLat + maxLat) / 2) * (Math.PI / 180);
    const cosLat = Math.cos(midLatRad);
    const dLng = (maxLng - minLng) * cosLat;
    const dLat = maxLat - minLat;

    const availW = W - pad * 2;
    const availH = H - pad * 2;
    const scale = Math.min(availW / (dLng || 1e-6), availH / (dLat || 1e-6));

    const shapeW = dLng * scale;
    const shapeH = dLat * scale;
    const offsetX = pad + (availW - shapeW) / 2;
    const offsetY = pad + (availH - shapeH) / 2;

    const projected = points.map((p: any) => {
      const x = Math.round((offsetX + (p.longitude - minLng) * cosLat * scale) * 10) / 10;
      const y = Math.round((offsetY + (maxLat - p.latitude) * scale) * 10) / 10;
      return { x, y };
    });

    let totalPathPx = 0;
    for (let i = 1; i < projected.length; i++) {
      totalPathPx += Math.hypot(projected[i].x - projected[i - 1].x, projected[i].y - projected[i - 1].y);
    }
    const isMultiLap = totalPathPx / Math.max(shapeW + shapeH, 40) > 5;
    const strokeW = isMultiLap ? 1.6 : 2.5;
    const strokeOp = isMultiLap ? 0.85 : 1;

    const pathD = projected.reduce((acc: string, pt: { x: number; y: number }, idx: number) => {
      return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`;
    }, "");

    const startPt = projected[0];
    const endPt = projected[projected.length - 1];

    const safeId = (actId || "trk").replace(/[^a-zA-Z0-9_]/g, "_");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"><defs><filter id="glow_${safeId}" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="0" stdDeviation="${isMultiLap ? 1.4 : 2}" flood-color="#FC4C02" flood-opacity="0.6"/></filter></defs><rect width="${W}" height="${H}" fill="#121215" rx="10"/><path d="${pathD}" fill="none" stroke="#FC4C02" stroke-width="${strokeW}" stroke-opacity="${strokeOp}" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow_${safeId})"/><circle cx="${startPt.x}" cy="${startPt.y}" r="3.5" fill="#10B981" stroke="#ffffff" stroke-width="1"/><circle cx="${endPt.x}" cy="${endPt.y}" r="3.5" fill="#FC4C02" stroke="#ffffff" stroke-width="1"/></svg>`;

    const dataUri = "data:image/svg+xml;base64," + base64Encode(svg);
    if (cacheKey) {
      routeSvgCache.set(cacheKey, dataUri);
    }
    return dataUri;
  } catch (e) {
    return null;
  }
}

const currentClub = ref<any>(null);
const currentRole = ref("member");
const userClubs = ref<any[]>([]);
const showSwitchModal = ref(false);

const leaderboard = ref<any[]>([]);
const feed = ref<any[]>([]);
const feedTotal = ref(0);
const hasMoreFeed = ref(false);
const loadingMoreFeed = ref(false);

// ── 英雄榜折叠与分页状态（默认展示前三，点击展开 10人/页） ──
const rankPageSize = ref(10);
const currentRankPage = ref(1);
const isRankExpanded = ref(false);

const totalRankPages = computed(() => {
  if (!leaderboard.value.length) return 1;
  return Math.ceil(leaderboard.value.length / rankPageSize.value);
});

const paginatedLeaderboard = computed(() => {
  if (!isRankExpanded.value) {
    return leaderboard.value.slice(0, 3);
  }
  const start = (currentRankPage.value - 1) * rankPageSize.value;
  return leaderboard.value.slice(start, start + rankPageSize.value);
});

const myRankItem = computed(() => {
  const uid = user.value?.id;
  if (!uid || !leaderboard.value.length) return null;
  return leaderboard.value.find((item: any) => item.user_id === uid) || null;
});

const visibleRankPageNumbers = computed(() => {
  const total = totalRankPages.value;
  const curr = currentRankPage.value;
  if (total <= 6) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages: number[] = [];
  if (curr <= 3) {
    pages.push(1, 2, 3, 4, -1, total);
  } else if (curr >= total - 2) {
    pages.push(1, -1, total - 3, total - 2, total - 1, total);
  } else {
    pages.push(1, -1, curr - 1, curr, curr + 1, -1, total);
  }
  return pages;
});

function handleExpandRank() {
  isRankExpanded.value = true;
  currentRankPage.value = 1;
  trackClick("rank_expand_leaderboard", "展开完整英雄榜", {
    club_id: currentClub.value?.id,
  });
}

function handleCollapseRank() {
  isRankExpanded.value = false;
  currentRankPage.value = 1;
  scrollToSection("#rank-section");
}

function jumpToMyRank() {
  if (!myRankItem.value) return;
  isRankExpanded.value = true;
  const page = Math.ceil(myRankItem.value.rank / rankPageSize.value);
  currentRankPage.value = Math.max(1, Math.min(page, totalRankPages.value));
  trackClick("rank_jump_my_rank", `定位至我的排名（第 ${myRankItem.value.rank} 名）`, {
    rank: myRankItem.value.rank,
  });
  uni.showToast({
    title: `已定位至第 ${myRankItem.value.rank} 名（第 ${currentRankPage.value} 页）`,
    icon: "none"
  });
  scrollToSection("#rank-section");
}

function handleRankPrevPage() {
  if (currentRankPage.value > 1) {
    currentRankPage.value--;
    scrollToSection("#rank-section");
  }
}

function handleRankNextPage() {
  if (currentRankPage.value < totalRankPages.value) {
    currentRankPage.value++;
    scrollToSection("#rank-section");
  }
}

function handleRankSetPage(p: number) {
  if (p >= 1 && p <= totalRankPages.value) {
    currentRankPage.value = p;
    scrollToSection("#rank-section");
  }
}

// ── 跑步记录 / 打卡动态分页与分类浏览状态 ──
const feedPageSize = ref(6);
const currentFeedPage = ref(1);
const activeFeedFilter = ref<"all" | "gps" | "lsd" | "coach">("all");

const gpsFeedCount = computed(() => {
  return feed.value.filter((a: any) => Boolean(getRoutePreview(a) || a.has_gps_track || a.id?.startsWith("garmin_"))).length;
});

const lsdFeedCount = computed(() => {
  return feed.value.filter((a: any) => (a.distance_meters || 0) >= 10000).length;
});

const coachFeedCount = computed(() => {
  return feed.value.filter((a: any) => Boolean(a.ai_journal && a.ai_journal.length > 20 && !a.ai_journal.includes("生成中"))).length;
});

const filteredFeed = computed(() => {
  const f = activeFeedFilter.value;
  if (f === "gps") {
    return feed.value.filter((a: any) => Boolean(getRoutePreview(a) || a.has_gps_track || a.id?.startsWith("garmin_")));
  }
  if (f === "lsd") {
    return feed.value.filter((a: any) => (a.distance_meters || 0) >= 10000);
  }
  if (f === "coach") {
    return feed.value.filter((a: any) => Boolean(a.ai_journal && a.ai_journal.length > 20 && !a.ai_journal.includes("生成中")));
  }
  return feed.value;
});

const totalFeedPages = computed(() => {
  if (!filteredFeed.value.length) return 1;
  return Math.ceil(filteredFeed.value.length / feedPageSize.value);
});

const paginatedFeed = computed(() => {
  const start = (currentFeedPage.value - 1) * feedPageSize.value;
  return filteredFeed.value.slice(start, start + feedPageSize.value);
});

const visibleFeedPageNumbers = computed(() => {
  const total = totalFeedPages.value;
  const curr = currentFeedPage.value;
  if (total <= 6) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages: number[] = [];
  if (curr <= 3) {
    pages.push(1, 2, 3, 4, -1, total);
  } else if (curr >= total - 2) {
    pages.push(1, -1, total - 3, total - 2, total - 1, total);
  } else {
    pages.push(1, -1, curr - 1, curr, curr + 1, -1, total);
  }
  return pages;
});

function setFeedFilter(f: "all" | "gps" | "lsd" | "coach") {
  activeFeedFilter.value = f;
  currentFeedPage.value = 1;
  const labelMap: Record<string, string> = {
    all: "全部动态",
    gps: "含GPS轨迹",
    lsd: "10K+长距离",
    coach: "教练点评",
  };
  trackSubView(`rank_feed_${f}`, `切换打卡动态筛选：${labelMap[f] || f}`);
}

function handleFeedPrevPage() {
  if (currentFeedPage.value > 1) {
    currentFeedPage.value--;
    scrollToSection("#feed-section");
  }
}

function handleFeedNextPage() {
  if (currentFeedPage.value < totalFeedPages.value) {
    currentFeedPage.value++;
    scrollToSection("#feed-section");
  }
}

function handleFeedSetPage(p: number) {
  if (p >= 1 && p <= totalFeedPages.value) {
    currentFeedPage.value = p;
    scrollToSection("#feed-section");
  }
}

function scrollToSection(selector: string) {
  try {
    const query = uni.createSelectorQuery();
    query.select(selector).boundingClientRect();
    query.selectViewport().scrollOffset();
    query.exec((res: any) => {
      if (res && res[0] && res[1]) {
        const top = res[1].scrollTop + res[0].top - 20;
        uni.pageScrollTo({
          scrollTop: Math.max(0, top),
          duration: 250
        });
      }
    });
  } catch (_) {}
}

const showCommentModal = ref(false);
const activeCommentActivityId = ref<string | null>(null);
const replyTargetComment = ref<any>(null);
const commentTextInput = ref("");
const submittingComment = ref(false);
const quickCommentPresets = [
  "🔥 配速太稳了，课表执行力满分！",
  "💪 有氧心率控制得真好，继续保持！",
  "👏 主课强度顶住了，向你学习！",
  "⚡ 一步一个脚印，科学备赛加油！"
];

function getCommentThreads(comments?: any[]) {
  if (!comments || !Array.isArray(comments) || comments.length === 0) return [];
  const rootMap = new Map<string, any>();
  const roots: any[] = [];
  for (const c of comments) {
    if (!c.parent_id) {
      const node = { ...c, replies: [] };
      rootMap.set(c.id, node);
      roots.push(node);
    }
  }
  for (const c of comments) {
    if (c.parent_id) {
      const parent = rootMap.get(c.parent_id);
      if (parent) {
        parent.replies.push(c);
      } else {
        const orphanNode = { ...c, replies: [] };
        rootMap.set(c.id, orphanNode);
        roots.push(orphanNode);
      }
    }
  }
  return roots;
}

const events = ref<any[]>([]);
const joiningEventId = ref<string | null>(null);

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

const upcomingGroupRuns = computed(() => {
  if (!events.value || events.value.length === 0) return [];
  const now = Date.now();
  return events.value
    .filter((e: any) => {
      if (e.event_type !== "group_run" && !e.meet_time) return false;
      const cleanStr = sanitizeMeetTimeStr(e.meet_time || e.start_date || "");
      if (!cleanStr) return true;
      const t = new Date(cleanStr.replace(/-/g, "/")).getTime();
      return isNaN(t) || t > (now - 4 * 3600 * 1000);
    })
    .sort((a: any, b: any) => {
      const cleanA = sanitizeMeetTimeStr(a.meet_time || a.start_date || "");
      const cleanB = sanitizeMeetTimeStr(b.meet_time || b.start_date || "");
      const tA = new Date(cleanA.replace(/-/g, "/")).getTime();
      const tB = new Date(cleanB.replace(/-/g, "/")).getTime();
      return (isNaN(tA) ? 0 : tA) - (isNaN(tB) ? 0 : tB);
    });
});

const featuredGroupRun = computed(() => {
  return upcomingGroupRuns.value.length > 0 ? upcomingGroupRuns.value[0] : null;
});

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

function handleAddToCalendar(evt: any) {
  if (!evt) return;
  const startTime = parseMeetTimeToSeconds(evt.meet_time || evt.start_date);
  const locationStr = evt.location || "跑团指定地点";
  const descStr = `【跑团约跑】${evt.title}\n集合时间: ${formatMeetTime(evt.meet_time || evt.start_date)}\n地点: ${locationStr}\n建议配速: ${evt.pace_requirement || '不限'}\n目标跑量: ${evt.target_km || 10}km\n${evt.rules || ''}`;

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
      alarmOffset: 1800,
      success: () => {
        uni.showToast({ title: "已加入手机日历提醒！", icon: "success" });
      },
      fail: (err: any) => {
        console.warn("addPhoneCalendar fail:", err);
        if (String(err?.errMsg).includes("cancel")) {
          // user cancelled
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
    trackFunnelStep("group_run_join_success", `在榜单页报名约跑：${evt.title}`, {
      club_id: currentClub.value.id,
      event_id: evt.id,
    });

    evt.is_joined = true;
    if (!evt.participants) evt.participants = [];
    if (!evt.participants.some((p: any) => p.user_id === uid)) {
      evt.participants.push({
        user_id: uid,
        display_name: user.value?.display_name || user.value?.real_name || "跑友",
        avatar_url: user.value?.avatar_url || ""
      });
      evt.participant_count = (evt.participant_count || 0) + 1;
    }

    uni.showModal({
      title: "🎉 报名成功！",
      content: `您已成功加入【${evt.title}】！\n⏰ 时间：${formatMeetTime(evt.meet_time || evt.start_date)}\n📍 地点：${evt.location || '跑团集合点'}\n\n是否立即将约跑添加到手机系统日历（支持提前30分钟响铃提醒）？`,
      confirmText: "同步到日历",
      cancelText: "稍后设置",
      success: (mRes) => {
        if (mRes.confirm) {
          handleAddToCalendar(evt);
        }
      }
    });

    refreshEvents();
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
          evt.is_joined = false;
          if (evt.participants) {
            evt.participants = evt.participants.filter((p: any) => p.user_id !== uid);
            evt.participant_count = Math.max(0, (evt.participant_count || 1) - 1);
          }
          uni.showToast({ title: "已取消报名", icon: "none" });
          refreshEvents();
        } catch (e: any) {
          uni.showToast({ title: e?.message || "取消失败", icon: "none" });
        } finally {
          joiningEventId.value = null;
        }
      }
    }
  });
}

async function refreshEvents() {
  if (!currentClub.value?.id || !user.value?.id) return;
  try {
    const res = await request(`/api/team/${currentClub.value.id}/events?user_id=${user.value.id}`);
    events.value = res?.events || [];
  } catch (e) {
    console.warn("Refresh events fail:", e);
  }
}

// 跑团首页已是 Tab 页：switchTab 会关闭当前二级页回到跑团
function goToTeamPage() {
  uni.switchTab({
    url: "/pages/team/team",
  });
}

function goToTeamEvents() {
  uni.setStorageSync("team_open_section", "events");
  goToTeamPage();
}

function goToProfilePage() {
  navigateToProfileRequiredFields();
}

const isRankSuspended = ref(false);
const rankSuspensionReason = ref("");

async function loadRankData(preferredClubId?: string) {
  user.value = getStoredUser();
  if (!user.value) {
    user.value = await checkAndAutoLogin();
  }
  if (!user.value || !user.value.id) return;
  const uid = user.value.id;

  try {
    const guessedClubId = preferredClubId || currentClub.value?.id || getActiveClubId();
    const fetchBundleForClub = (cid: string) =>
      Promise.all([
        request(`/api/team/${cid}/leaderboard?user_id=${uid}`).catch((e: any) => ({ error: e })),
        request(`/api/team/${cid}/feed?uid=${uid}`).catch((e: any) => ({ error: e })),
        request(`/api/team/${cid}/events?user_id=${uid}`).catch((e: any) => ({ error: e })),
      ]);

    // Single-RTT parallel fetch when active club is already known locally
    const [res, speculatedBundle] = await Promise.all([
      request(`/api/team/my-clubs/${uid}`),
      guessedClubId ? fetchBundleForClub(guessedClubId) : Promise.resolve(null),
    ]);
    const clubs = res?.clubs || [];
    userClubs.value = clubs;

    if (clubs.length > 0) {
      const prevClubId = currentClub.value?.id;
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
      const clubChanged = Boolean(prevClubId && prevClubId !== clubId);

      if (targetClub.is_access_suspended) {
        isRankSuspended.value = true;
        rankSuspensionReason.value = targetClub.suspension_reason || "";
      } else {
        isRankSuspended.value = false;
        rankSuspensionReason.value = "";
      }

      // Reuse speculated single-RTT bundle if targetClub matches guessedClubId; otherwise fetch for resolved clubId
      try {
        const [lbRes, feedRes, eventsRes] =
          speculatedBundle && clubId === guessedClubId
            ? speculatedBundle
            : await fetchBundleForClub(clubId);

        if (lbRes?.error && (lbRes.error?.statusCode === 403 || String(lbRes.error?.message).includes("暂停"))) {
          isRankSuspended.value = true;
          rankSuspensionReason.value = lbRes.error.message;
        } else if (feedRes?.error && (feedRes.error?.statusCode === 403 || String(feedRes.error?.message).includes("暂停"))) {
          isRankSuspended.value = true;
          rankSuspensionReason.value = feedRes.error.message;
        } else {
          leaderboard.value = lbRes?.leaderboard || [];
          const newFeed = feedRes?.feed || [];
          feed.value = newFeed;
          feedTotal.value = feedRes?.total ?? newFeed.length;
          hasMoreFeed.value = feedRes?.has_more ?? false;
          events.value = eventsRes?.events || [];
          try {
            const slimFeed = newFeed.slice(0, 10).map((a: any) => {
              if (!a || typeof a !== "object") return a;
              const { laps_data, splits_data, segment_analysis_json, ...rest } = a;
              return rest;
            });
            uni.setStorageSync(`rgm_rank_cache_${clubId}`, {
              club: targetClub,
              role: currentRole.value,
              leaderboard: leaderboard.value.slice(0, 15),
              feed: slimFeed,
              feedTotal: feedTotal.value,
              hasMoreFeed: hasMoreFeed.value,
              events: (events.value || []).slice(0, 3),
            });
          } catch (_) {}
        }
      } catch (err: any) {
        if (err?.statusCode === 403 || String(err?.message).includes("暂停")) {
          isRankSuspended.value = true;
          rankSuspensionReason.value = err.message;
        }
      }
      if (clubChanged) {
        currentRankPage.value = 1;
        currentFeedPage.value = 1;
        isRankExpanded.value = false;
      } else if (currentRankPage.value > totalRankPages.value) {
        currentRankPage.value = Math.max(1, totalRankPages.value);
      }
    } else {
      setActiveClubId("");
      currentClub.value = null;
      currentRole.value = "member";
      leaderboard.value = [];
      feed.value = [];
      feedTotal.value = 0;
      hasMoreFeed.value = false;
      currentRankPage.value = 1;
      currentFeedPage.value = 1;
      isRankExpanded.value = false;
      events.value = [];
    }
  } catch (e) {
    console.warn("Load rank data error:", e);
  }
}

async function handleLoadMoreFeed() {
  if (!currentClub.value?.id || loadingMoreFeed.value || !hasMoreFeed.value) return;
  const uid = user.value?.id;
  if (!uid) return;

  loadingMoreFeed.value = true;
  try {
    const res = await request(
      `/api/team/${currentClub.value.id}/feed?uid=${uid}&scope=all&limit=20&offset=${feed.value.length}`
    );
    const moreItems = res?.feed || [];
    feed.value = [...feed.value, ...moreItems];
    feedTotal.value = res?.total ?? feed.value.length;
    hasMoreFeed.value = res?.has_more ?? false;
  } catch (e) {
    console.warn("Load more feed error:", e);
  } finally {
    loadingMoreFeed.value = false;
  }
}

function handleSwitchClub(club: any) {
  if (!club || !club.id) return;
  trackClick("rank_switch_club", `切换榜单跑团：${club.name}`, { club_id: club.id });
  setActiveClubId(club.id);
  showSwitchModal.value = false;
  currentRankPage.value = 1;
  currentFeedPage.value = 1;
  isRankExpanded.value = false;
  activeFeedFilter.value = "all";
  uni.showToast({
    title: `已切换至【${club.name}】榜单`,
    icon: "success",
  });
  loadRankData(club.id);
}

async function handleToggleLike(act: any) {
  const uid = user.value?.id;
  if (!uid) return;
  try {
    const res = await request(`/api/team/activities/${act.id}/like`, "POST", {
      user_id: uid,
    });
    act.has_liked = res.liked;
    act.likes_count = res.likes_count;
    if (Array.isArray(res.likers)) {
      act.likers = res.likers;
    }
    trackClick("rank_like_activity", res.liked ? "点赞队友打卡动态" : "取消点赞打卡动态", {
      activity_id: act.id,
      liked: Boolean(res.liked),
    });
  } catch (e: any) {
    uni.showToast({ title: "点赞失败", icon: "none" });
  }
}

function handleOpenCommentModal(act: any, targetComment?: any) {
  activeCommentActivityId.value = act.id;
  replyTargetComment.value = targetComment || null;
  commentTextInput.value = "";
  showCommentModal.value = true;
  trackModal("rank_comment", "打开打卡互动留言弹窗", "open", {
    activity_id: act.id,
    is_reply: Boolean(targetComment),
  });
}

async function handleSendComment() {
  if (!commentTextInput.value.trim() || !activeCommentActivityId.value) return;
  const uid = user.value?.id;
  if (!uid) return;
  submittingComment.value = true;
  try {
    const payload: any = {
      user_id: uid,
      content: commentTextInput.value.trim(),
      author_name: user.value?.display_name || "跑友",
      author_avatar:
        user.value?.avatar_url ||
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80",
    };
    if (replyTargetComment.value) {
      payload.parent_id = replyTargetComment.value.parent_id || replyTargetComment.value.id;
      payload.reply_to_user_id = replyTargetComment.value.user_id;
      payload.reply_to_name = replyTargetComment.value.author_name;
    }
    const res = await request(
      `/api/team/activities/${activeCommentActivityId.value}/comments`,
      "POST",
      payload
    );

    const targetAct = feed.value.find((a) => a.id === activeCommentActivityId.value);
    if (targetAct) {
      if (!targetAct.comments) targetAct.comments = [];
      targetAct.comments.push(res.comment);
    }
    trackFunnelStep("rank_comment_submit", "发布打卡互动留言", {
      activity_id: activeCommentActivityId.value,
      is_reply: Boolean(replyTargetComment.value),
    });
    showCommentModal.value = false;
    replyTargetComment.value = null;
    uni.showToast({ title: "留言已发布！", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: "评论失败", icon: "none" });
  } finally {
    submittingComment.value = false;
  }
}

async function handleDeleteComment(act: any, commentId: string) {
  const uid = user.value?.id;
  if (!uid || !commentId) return;
  try {
    await request(
      `/api/team/activities/${act.id}/comments/${commentId}?user_id=${encodeURIComponent(uid)}`,
      "DELETE"
    );
    if (Array.isArray(act.comments)) {
      act.comments = act.comments.filter(
        (c: any) => c.id !== commentId && c.parent_id !== commentId
      );
    }
    uni.showToast({ title: "留言已删除", icon: "none" });
  } catch (e) {
    uni.showToast({ title: "删除失败", icon: "none" });
  }
}

function formatCommentDate(isoStr?: string): string {
  return formatBeijingTime(isoStr, false);
}

function formatFeedDate(isoStr?: string): string {
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

// 首屏骨架屏开关（若有上次跑团动态快照则 0ms 秒开，后台静默刷新）
let hydratedRankFromCache = false;
try {
  const cachedActiveClubId = uni.getStorageSync("rgm_active_club_id");
  if (cachedActiveClubId) {
    const snap = uni.getStorageSync(`rgm_rank_cache_${cachedActiveClubId}`);
    if (snap && typeof snap === "object" && snap.club) {
      currentClub.value = snap.club;
      currentRole.value = snap.role || "member";
      leaderboard.value = Array.isArray(snap.leaderboard) ? snap.leaderboard : [];
      feed.value = Array.isArray(snap.feed) ? snap.feed : [];
      feedTotal.value = snap.feedTotal ?? feed.value.length;
      hasMoreFeed.value = Boolean(snap.hasMoreFeed);
      events.value = Array.isArray(snap.events) ? snap.events : [];
      hydratedRankFromCache = true;
    }
  }
} catch (_) {}
const firstLoadPending = ref(!hydratedRankFromCache);

// 从跑团首页「打卡动态与教练点评」进入时，加载完成后定位到动态区
let pendingScrollToFeed = false;
function scrollToFeedIfNeeded() {
  if (!pendingScrollToFeed) return;
  pendingScrollToFeed = false;
  setTimeout(() => uni.pageScrollTo({ selector: "#feed-section", duration: 300 }), 200);
}

onShow(() => {
  applySystemTheme(currentTheme.value);
  // 首次进入显示骨架屏，首个请求结束（或 8 秒超时）后关闭
  if (firstLoadPending.value) {
    const timer = setTimeout(() => (firstLoadPending.value = false), 8000);
    Promise.resolve(loadRankData())
      .catch(() => {})
      .finally(() => {
        clearTimeout(timer);
        firstLoadPending.value = false;
        scrollToFeedIfNeeded();
      });
  } else {
    scrollToFeedIfNeeded();
    loadRankData();
  }
});

onPullDownRefresh(async () => {
  await loadRankData();
  uni.stopPullDownRefresh();
});

onLoad((options: any) => {
  initShareMenu();
  if (options?.section === "feed") pendingScrollToFeed = true;
});

onShareAppMessage((res: any) => {
  const dataset = res?.target?.dataset || {};
  const shareType = dataset.shareType || dataset["share-type"];
  if (shareType === "group_run" && featuredGroupRun.value) {
    return buildGroupRunSharePayload(
      { ...featuredGroupRun.value, club_id: featuredGroupRun.value.club_id || currentClub.value?.id },
      currentClub.value?.name,
      user.value?.id
    );
  }
  return getUnifiedShareAppMessage();
});

onShareTimeline(() => {
  return getUnifiedShareTimeline();
});
</script>

<style scoped>
.rank-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  color: var(--rgm-text, #f4f4f5);
  padding: 24rpx 28rpx calc(48rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

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

/* ── 跑团上下文横幅 ── */
.club-context-bar {
  display: flex;
  align-items: center;
  background: var(--rgm-card, linear-gradient(135deg, #18181b 0%, #121214 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.2));
  border-radius: 24rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 24rpx;
  gap: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.club-logo-mini {
  width: 72rpx;
  height: 72rpx;
  border-radius: 20rpx;
  border: 2rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
}

.club-meta {
  flex: 1;
  min-width: 0;
}

.club-name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.club-title {
  font-size: 28rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-badge {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.role-badge.role-owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: var(--rgm-amber, #ff9f0a);
  border: 1rpx solid rgba(255, 159, 10, 0.4);
}

.role-badge.role-coach {
  background-color: var(--rgm-brand-tint, rgba(191, 90, 242, 0.2));
  color: var(--rgm-brand-text, #bf5af2);
  border: 1rpx solid var(--rgm-brand-line, rgba(191, 90, 242, 0.4));
}

.role-badge.role-member {
  background-color: rgba(10, 132, 255, 0.15);
  color: var(--rgm-blue, #0a84ff);
}


.enter-team-hint {
  display: flex;
  align-items: center;
  gap: 4rpx;
}

.hint-text {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.arrow {
  font-size: 26rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.switch-club-pill {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  padding: 10rpx 18rpx;
  border-radius: 20rpx;
}

.switch-icon {
  font-size: 24rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.switch-text {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

/* Modal styles for club switching in rank.vue */
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
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.06));
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

/* ── 置顶约跑卡片 (英雄榜上方 · 一键参加) ── */
.group-run-hero-card {
  background: var(--rgm-card, linear-gradient(145deg, #1b1b22 0%, #131317 100%));
  border: 1.5rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  box-shadow: 0 8rpx 32rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.15)), 0 2rpx 8rpx var(--rgm-shadow, rgba(0, 0, 0, 0.4));
  border-radius: 28rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  position: relative;
  overflow: hidden;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.grh-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}

.grh-badge-box {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.grh-pulse-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background-color: #30d158;
  box-shadow: 0 0 10rpx #30d158;
  --rgm-text: var(--rgm-on-bright); --rgm-text-2: var(--rgm-on-bright-2); --rgm-text-3: var(--rgm-on-bright-2);
}

.grh-badge-title {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
  letter-spacing: 0.5rpx;
}

.grh-repeat-pill {
  font-size: 20rpx;
  padding: 4rpx 14rpx;
  background: rgba(48, 209, 88, 0.15);
  border: 1rpx solid rgba(48, 209, 88, 0.35);
  border-radius: 20rpx;
  color: var(--rgm-green, #30d158);
  font-weight: 600;
}

.grh-header-right {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.grh-countdown {
  font-size: 22rpx;
  color: var(--rgm-amber, #ff9f0a);
  font-weight: 600;
  background: rgba(255, 159, 10, 0.12);
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
}

.grh-arrow {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
}

.grh-main {
  display: flex;
  gap: 20rpx;
  margin-bottom: 20rpx;
}

.grh-cover-image {
  width: 168rpx;
  height: 168rpx;
  border-radius: 20rpx;
  flex-shrink: 0;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  background-color: var(--rgm-card-3, #27272a);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.grh-info-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
}

.grh-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.grh-title {
  font-size: 30rpx;
  font-weight: 800;
  color: var(--rgm-text, #ffffff);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.grh-joined-status-tag {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-green, #30d158);
  background: rgba(48, 209, 88, 0.15);
  padding: 2rpx 12rpx;
  border-radius: 12rpx;
  flex-shrink: 0;
}

.grh-detail-line {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 6rpx;
}

.gdl-icon {
  font-size: 24rpx;
  flex-shrink: 0;
}

.gdl-text {
  font-size: 24rpx;
  color: var(--rgm-text-2, #d4d4d8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.gdl-text.highlight {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 700;
}

.gdl-nav-hint {
  font-size: 20rpx;
  color: var(--rgm-blue, #0a84ff);
  font-weight: 600;
  flex-shrink: 0;
}

.grh-tags-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 10rpx;
  flex-wrap: wrap;
}

.grh-tag {
  display: flex;
  align-items: center;
  gap: 6rpx;
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
}

.grh-tag.orange {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
}

.grh-tag.orange .gt-text {
  color: var(--rgm-brand-text, #fc4c02);
  font-size: 22rpx;
  font-weight: 700;
}

.grh-tag.dark {
  background: var(--rgm-card-3, #27272a);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.grh-tag.dark .gt-text {
  color: var(--rgm-text, #e4e4e7);
  font-size: 22rpx;
  font-weight: 600;
}

.gt-icon {
  font-size: 20rpx;
}

.grh-meta-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 18rpx;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 18rpx;
  margin-bottom: 20rpx;
}

.grh-organizer {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.grh-org-avatar {
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.2));
}

.grh-org-name {
  font-size: 24rpx;
  color: var(--rgm-text, #f4f4f5);
  font-weight: 600;
  max-width: 140rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.grh-org-badge {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 10rpx;
  font-weight: 700;
}

.grh-org-badge.role-owner {
  background: rgba(255, 215, 0, 0.2);
  color: var(--rgm-amber, #ffd700);
  border: 1rpx solid rgba(255, 215, 0, 0.4);
}

.grh-org-badge.role-coach {
  background: rgba(0, 198, 255, 0.2);
  color: var(--rgm-blue, #00c6ff);
  border: 1rpx solid rgba(0, 198, 255, 0.4);
}

.grh-org-badge.role-creator {
  background: rgba(48, 209, 88, 0.18);
  color: var(--rgm-green, #30d158);
  border: 1rpx solid rgba(48, 209, 88, 0.35);
}

.grh-participants-preview {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.grh-avatar-stack {
  display: flex;
  align-items: center;
  margin-right: 4rpx;
}

.grh-stack-avatar {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  border: 2rpx solid var(--rgm-line-solid, #1c1c20);
  margin-left: -12rpx;
}

.grh-stack-avatar:first-child {
  margin-left: 0;
}

.grh-part-count-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

/* 按钮区域 */
.grh-actions-box {
  width: 100%;
}

.grh-join-btn {
  width: 100%;
  min-width: 0;
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff6b00 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 28rpx;
  font-weight: 800;
  border-radius: 24rpx;
  height: 84rpx;
  line-height: 1.25;
  padding: 0 16rpx;
  margin: 0;
  white-space: nowrap;
  text-align: center;
  border: none;
  box-shadow: 0 6rpx 20rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.35));
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 1rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.grh-join-btn::after {
  border: none;
}

.grh-join-btn:active {
  opacity: 0.88;
  transform: scale(0.985);
}

.grh-joined-actions {
  display: flex;
  align-items: center;
  gap: 14rpx;
  width: 100%;
}

.grh-joined-pill {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  background: rgba(48, 209, 88, 0.15);
  border: 1rpx solid rgba(48, 209, 88, 0.35);
  border-radius: 20rpx;
  height: 80rpx;
}

.gjp-icon {
  font-size: 26rpx;
  color: var(--rgm-green, #30d158);
  font-weight: 800;
}

.gjp-text {
  font-size: 26rpx;
  color: var(--rgm-green, #30d158);
  font-weight: 700;
}

.grh-sub-btn {
  min-width: 0;
  font-size: 24rpx;
  font-weight: 600;
  height: 80rpx;
  line-height: 1.25;
  border-radius: 20rpx;
  padding: 0 18rpx;
  margin: 0;
  white-space: nowrap;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
}

.grh-sub-btn::after {
  border: none;
}

.grh-sub-btn.calendar {
  background: var(--rgm-card-3, #27272a);
  color: var(--rgm-blue, #0a84ff);
  border: 1rpx solid rgba(10, 132, 255, 0.3);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.grh-sub-btn.leave {
  background: transparent;
  color: var(--rgm-text-3, #71717a);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  padding: 0 16rpx;
}

.grh-more-runs-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 18rpx;
  padding-top: 14rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
}

.gmr-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.gmr-link {
  font-size: 22rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: 600;
}

/* ── 通用卡片容器 ── */
.section-card {
  background-color: var(--rgm-card, #121214);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  border-radius: 28rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.rank-header-row {
  flex-wrap: wrap;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 8rpx;
  white-space: nowrap;
  flex-shrink: 0;
}

.title-with-icon .icon {
  font-size: 30rpx;
}

.card-title {
  font-size: 29rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  white-space: nowrap;
}

.count-badge {
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
  font-weight: normal;
  margin-left: 2rpx;
  white-space: nowrap;
}

.header-right-meta {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}


.my-rank-pill {
  display: flex;
  align-items: center;
  gap: 6rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45));
  border-radius: 999rpx;
  padding: 6rpx 16rpx;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s;
}

.my-rank-pill:active {
  transform: scale(0.96);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.25));
}

.mrp-icon {
  font-size: 20rpx;
}

.mrp-text {
  font-size: 20rpx;
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
  white-space: nowrap;
}

/* ── 英雄榜列表 ── */
.leaderboard-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.rank-item {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 20rpx;
  padding: 20rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1rpx solid transparent;
  transition: all 0.2s ease;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rank-item.top-three {
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
}

.rank-item.rank-gold {
  background: var(--rgm-card, linear-gradient(90deg, rgba(255, 215, 0, 0.1) 0%, #1a1a1e 70%));
  border-color: rgba(255, 215, 0, 0.35);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rank-item.rank-silver {
  background: var(--rgm-card, linear-gradient(90deg, rgba(192, 192, 192, 0.1) 0%, #1a1a1e 70%));
  border-color: rgba(192, 192, 192, 0.3);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rank-item.rank-bronze {
  background: var(--rgm-card, linear-gradient(90deg, rgba(205, 127, 50, 0.1) 0%, #1a1a1e 70%));
  border-color: var(--rgm-brand-line, rgba(205, 127, 50, 0.3));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.rank-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.rank-badge-box {
  width: 44rpx;
  text-align: center;
}

.rank-num {
  font-size: 32rpx;
  font-weight: 900;
  color: var(--rgm-text-3, #8e8e93);
}

.user-avatar {
  width: 76rpx;
  height: 76rpx;
  border-radius: 38rpx;
  border: 2rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
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

.mini-me-tag {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
  background: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.rank-item.is-me {
  border: 2rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.65)) !important;
  background: var(--rgm-card, linear-gradient(90deg, rgba(252, 76, 2, 0.14) 0%, #1a1a1e 75%)) !important;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
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
  font-size: 32rpx;
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
  background: var(--rgm-brand-grad, linear-gradient(90deg, #fc4c02, #ff7300));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── 英雄榜默认前三收起时的展开条 ── */
.rank-expand-bar {
  margin-top: 4rpx;
  padding: 18rpx 24rpx;
  border-radius: 18rpx;
  background: var(--rgm-card-2, #1a1a1e);
  border: 1rpx dashed var(--rgm-brand-line, rgba(252, 76, 2, 0.38));
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  cursor: pointer;
  transition: all 0.2s ease;
}

.rank-expand-bar:active {
  transform: scale(0.985);
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.14));
}

.reb-text {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

.reb-arrow {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

/* ── 分页控制器通用样式 ── */
.pagination-container {
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.pagination-container.feed-pagination {
  margin-top: 28rpx;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10rpx;
  width: 100%;
}

.page-nav-btn {
  background: var(--rgm-card-2, #1f1f23);
  color: var(--rgm-text, #ffffff);
  font-size: 24rpx;
  font-weight: 600;
  padding: 0 24rpx;
  height: 64rpx;
  line-height: 64rpx;
  border-radius: 32rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.12));
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.page-nav-btn.disabled {
  opacity: 0.35;
  background: var(--rgm-card, #141416);
  color: var(--rgm-text-3, #71717a);
  border-color: var(--rgm-line, rgba(255, 255, 255, 0.05));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.page-pills-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  flex: 1;
  flex-wrap: wrap;
}

.page-pill {
  min-width: 52rpx;
  height: 52rpx;
  border-radius: 26rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 600;
  transition: all 0.2s;
  padding: 0 8rpx;
  box-sizing: border-box;
}

.page-pill.active {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff7300 100%));
  color: var(--rgm-text, #ffffff);
  font-weight: bold;
  box-shadow: 0 4rpx 12rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.4));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.page-pill.dots {
  background: transparent;
  color: var(--rgm-text-3, #71717a);
}

.pagination-footer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 0 6rpx;
}

.pagination-footer-bar.center {
  justify-content: center;
  text-align: center;
}

.page-summary-text {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.expand-toggle-btn {
  color: var(--rgm-brand-text, #fc4c02);
  font-size: 22rpx;
  font-weight: 600;
  cursor: pointer;
  padding: 4rpx 8rpx;
}

/* ── 动态打卡分类筛选 Chips ── */
.feed-filter-scroll {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 20rpx;
  overflow-x: auto;
  white-space: nowrap;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 6rpx;
}

.feed-filter-chip {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.05));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 24rpx;
  padding: 10rpx 22rpx;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.feed-filter-chip.active {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.5));
}

.ffc-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
  font-weight: 600;
}

.feed-filter-chip.active .ffc-text {
  color: var(--rgm-brand-text, #fc4c02);
  font-weight: bold;
}

.older-feed-box {
  margin-top: 20rpx;
  width: 100%;
}

/* ── 动态列表 ── */
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.feed-card {
  background-color: var(--rgm-card-2, #1a1a1e);
  border-radius: 24rpx;
  padding: 24rpx;
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.05));
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

.feed-author-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.feed-author {
  font-size: 26rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.feed-date-chip {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
}

.feed-act-name {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-top: 4rpx;
  display: block;
  line-height: 1.4;
}

.feed-distance {
  text-align: right;
}

.feed-km {
  font-size: 38rpx;
  font-weight: 900;
  color: var(--rgm-brand-text, #fc4c02);
  font-family: monospace;
}

.feed-unit {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-left: 4rpx;
}

.feed-map-card {
  position: relative;
  width: 100%;
  height: 240rpx;
  border-radius: 18rpx;
  overflow: hidden;
  margin-bottom: 16rpx;
  background-color: var(--rgm-card, #121215);
  display: flex;
  align-items: center;
  justify-content: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.feed-map-thumb {
  height: 100%;
  max-width: 100%;
}

.feed-map-thumb.coros-filter {
  filter: hue-rotate(-52deg) saturate(1.25) contrast(1.08);
}

.feed-map-overlay {
  position: absolute;
  bottom: 12rpx;
  right: 12rpx;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.feed-map-pill {
  font-size: 20rpx;
  color: var(--rgm-text, #ffffff);
  font-weight: 500;
}

.feed-track-action-bar {
  display: flex;
  align-items: center;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.08));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
  border-radius: 14rpx;
  padding: 10rpx 16rpx;
  margin-bottom: 16rpx;
}

.feed-track-icon {
  font-size: 24rpx;
  margin-right: 10rpx;
}

.feed-track-lbl {
  flex: 1;
  font-size: 22rpx;
  color: var(--rgm-brand-text, #FC4C02);
  font-weight: 600;
}

.feed-track-arr {
  font-size: 24rpx;
  color: var(--rgm-brand-text, #FC4C02);
  font-weight: bold;
}

/* AI Coach Bubble */
.coach-bubble {
  background: var(--rgm-brand-tint, linear-gradient(135deg, rgba(191, 90, 242, 0.12) 0%, rgba(10, 132, 255, 0.08) 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(191, 90, 242, 0.25));
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 16rpx;
}

.coach-badge-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8rpx;
}

.coach-badge-left {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.coach-robot-icon {
  font-size: 22rpx;
}

.coach-badge-title {
  font-size: 20rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #bf5af2);
}


.ai-comment-tip {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
}

.coach-comment-text {
  font-size: 22rpx;
  color: var(--rgm-text, #e4e4e7);
  line-height: 1.5;
  display: block;
}

/* Social Bar */
.social-bar {
  display: flex;
  gap: 20rpx;
  border-top: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  padding-top: 16rpx;
}

.like-btn,
.comment-trigger-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background-color: var(--rgm-card-3, #242428);
  padding: 8rpx 20rpx;
  border-radius: 12rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.like-btn.liked {
  background-color: rgba(255, 69, 58, 0.15);
}

.like-btn.liked .like-text {
  color: var(--rgm-red, #ff453a);
}

.like-text,
.cmt-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

/* Likers Strip (显示点赞者及头像) */
.likers-box {
  margin-top: 14rpx;
  background-color: var(--rgm-card-3, #242428);
  border-radius: 14rpx;
  padding: 12rpx 16rpx;
  display: flex;
  align-items: flex-start;
  gap: 10rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.likers-heart {
  font-size: 22rpx;
  line-height: 36rpx;
  flex-shrink: 0;
}

.likers-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10rpx;
  flex: 1;
}

.liker-chip {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 4rpx 12rpx 4rpx 6rpx;
}

.liker-avatar {
  width: 28rpx;
  height: 28rpx;
  border-radius: 14rpx;
  flex-shrink: 0;
}

.liker-name {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-text, #f4f4f5);
}

.likers-suffix {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
  margin-left: 4rpx;
}

/* Threaded Comments Box */
.comments-box {
  margin-top: 14rpx;
  background-color: var(--rgm-card-3, #242428);
  border-radius: 14rpx;
  padding: 14rpx 16rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.cmt-thread-group {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.cmt-root-row {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
}

.cmt-avatar {
  width: 38rpx;
  height: 38rpx;
  border-radius: 19rpx;
  flex-shrink: 0;
  margin-top: 2rpx;
}

.cmt-avatar.mini {
  width: 30rpx;
  height: 30rpx;
  border-radius: 15rpx;
}

.cmt-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.cmt-meta-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-wrap: wrap;
}

.cmt-author {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

.cmt-reply-names {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
}

.cmt-reply-verb {
  font-size: 20rpx;
  color: var(--rgm-text-3, #8e8e93);
}

.cmt-reply-target {
  font-size: 21rpx;
  font-weight: 600;
  color: var(--rgm-text-2, #a1a1aa);
}

.cmt-time {
  font-size: 18rpx;
  color: var(--rgm-text-3, #71717a);
}

.cmt-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.cmt-reply-link {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-brand-text, #fc4c02);
}

.cmt-del-link {
  font-size: 20rpx;
  color: var(--rgm-text-3, #71717a);
}

.cmt-content {
  font-size: 22rpx;
  line-height: 1.45;
  color: var(--rgm-text, #e4e4e7);
  word-break: break-word;
}

.cmt-replies-list {
  margin-left: 36rpx;
  padding-left: 16rpx;
  border-left: 3rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  margin-top: 4rpx;
}

.cmt-reply-row {
  display: flex;
  align-items: flex-start;
  gap: 10rpx;
}

.reply-target-banner {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.1));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  border-radius: 14rpx;
  padding: 12rpx 16rpx;
  margin-bottom: 16rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.rtb-left {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.rtb-label {
  font-size: 21rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

.rtb-quote {
  font-size: 20rpx;
  color: var(--rgm-text-2, #a1a1aa);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rtb-cancel {
  font-size: 20rpx;
  font-weight: 600;
  color: var(--rgm-text-3, #8e8e93);
  flex-shrink: 0;
  padding: 4rpx 10rpx;
}

.quick-cmt-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 16rpx;
}

.qcc-pill {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.06));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 20rpx;
  padding: 6rpx 16rpx;
}

.qcc-text {
  font-size: 20rpx;
  color: var(--rgm-text-2, #d4d4d8);
}

/* Empty State */
.empty-box {
  padding: 48rpx 24rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.empty-icon {
  font-size: 48rpx;
  margin-bottom: 12rpx;
}

.empty-text {
  font-size: 24rpx;
  color: var(--rgm-text-3, #71717a);
}

/* Unjoined View */
.unjoined-view {
  padding: 60rpx 20rpx;
}

.unjoined-card {
  background-color: var(--rgm-card, #121214);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 28rpx;
  padding: 48rpx 32rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.unjoined-icon {
  font-size: 72rpx;
  margin-bottom: 20rpx;
}

.unjoined-title {
  font-size: 34rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 16rpx;
}

.unjoined-desc {
  font-size: 24rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.6;
  margin-bottom: 36rpx;
}

.goto-team-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff7300 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  padding: 0 40rpx;
  height: 80rpx;
  line-height: 80rpx;
  border-radius: 40rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* Modal */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: 30rpx;
  --rgm-text: var(--rgm-on-deep); --rgm-text-2: var(--rgm-on-deep-2); --rgm-text-3: var(--rgm-on-deep-2);
}

.modal-content {
  background-color: var(--rgm-card-2, #1a1a1e);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 28rpx;
  width: 100%;
  max-width: 600rpx;
  padding: 30rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.modal-title {
  font-size: 30rpx;
  font-weight: bold;
  color: var(--rgm-text, #ffffff);
}

.close-btn {
  font-size: 32rpx;
  color: var(--rgm-text-3, #8e8e93);
  padding: 10rpx;
}

.textarea-input {
  width: 100%;
  height: 180rpx;
  background-color: var(--rgm-card, #121214);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  border-radius: 16rpx;
  padding: 16rpx;
  box-sizing: border-box;
  font-size: 24rpx;
  color: var(--rgm-text, #ffffff);
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.submit-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff7300 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: bold;
  height: 72rpx;
  line-height: 72rpx;
  border-radius: 36rpx;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

.feed-load-more-box {
  padding-top: 16rpx;
  padding-bottom: 12rpx;
}

.load-more-btn {
  background-color: var(--rgm-card, #16161a);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.1));
  color: var(--rgm-text, #e4e4e7);
  font-size: 24rpx;
  font-weight: bold;
  height: 76rpx;
  line-height: 76rpx;
  border-radius: 38rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.no-more-text {
  text-align: center;
  font-size: 22rpx;
  color: var(--rgm-text-3, #71717a);
  padding: 16rpx 0;
}

.expand-month-btn {
  background: var(--rgm-card, #141416);
  border-color: var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
  color: var(--rgm-brand-text, #ff6426);
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.month-expanded-container,
.month-complete-container {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.month-summary-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 20rpx;
  padding: 16rpx 24rpx;
}

.month-summary-text {
  font-size: 22rpx;
  color: var(--rgm-text-2, #a1a1aa);
}

.collapse-action {
  font-size: 24rpx;
  font-weight: bold;
  color: var(--rgm-brand-text, #fc4c02);
  padding: 4rpx 10rpx;
}

.older-feed-btn {
  background-color: var(--rgm-card, #121214);
  color: var(--rgm-text-3, #71717a);
  font-size: 22rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
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
</style>
