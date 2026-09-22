<template>
  <view class="team-page">
    <!-- ── 顶部导航栏 / 跑团与榜单快速切换胶囊 ── -->
    <view class="top-nav-capsule">
      <view class="nav-segment" @click="goToRankPage">
        <text class="nav-icon">‹ 🥇</text>
        <text class="nav-text">英雄榜与动态</text>
      </view>
      <view class="nav-segment active">
        <text class="nav-icon">🏃</text>
        <text class="nav-text">跑团大本营</text>
      </view>
    </view>

    <!-- ── 🏛️ 大群体组织铭牌 (若已认证加入复旦戈等大组织) ── -->
    <view v-if="currentOrg" class="org-banner-card">
      <view class="org-banner-top">
        <view class="org-badge-box">
          <text class="org-badge-icon">🏛️</text>
          <text class="org-badge-title">{{ currentOrg.name }} 大群体</text>
          <text class="org-auth-status" :class="currentOrg.status">
            {{ currentOrg.status === 'confirmed' ? '✓ 戈友已认证' : currentOrg.status === 'temporary' ? `⚠️ 临时人员 (剩${currentOrg.remaining_days ?? 14}天)` : currentOrg.status === 'pending' ? `⏳ 待审核 (剩${currentOrg.remaining_days ?? 14}天)` : currentOrg.status === 'expired' ? '🚫 已过期' : '⏳ 待核对' }}
          </text>
        </view>
        <view class="org-right-actions">
          <view class="subclubs-tag-btn" @click="openSubClubsModal">
            <text class="subclubs-tag-text">下属分队 ({{ orgSubClubs.length }}) ›</text>
          </view>
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
          <text class="osas-title">⚠️ 临时人员状态（2周到期倒计时剩余 {{ currentOrg.remaining_days ?? 14 }} 天）</text>
          <text class="osas-desc">
            {{ currentOrg.missing_required_fields && currentOrg.missing_required_fields.length > 0 
                ? '尚缺必填项：' + currentOrg.missing_required_fields.join('、') + '。完成所有必须字段并经审核后方可加入下属跑团，逾期将禁止进入大群。'
                : '必填资料未完成，请尽快补齐资料并等待管理员审核批准以加入下属跑团。' }}
          </text>
        </view>
        <button class="osas-btn" @click="openOrgEditProfileModal">✏️ 补齐必填资料</button>
      </view>
      <view v-else-if="currentOrg.status === 'pending'" class="org-status-alert-strip pending-strip">
        <view class="osas-left">
          <text class="osas-title">⏳ 必填资料已齐，等待管理员审核批准（剩余 {{ currentOrg.remaining_days ?? 14 }} 天）</text>
          <text class="osas-desc">管理员审核批准后，您即可自由加入【{{ currentOrg.name }}】下属各分跑团。</text>
        </view>
        <button class="osas-btn outline" @click="openOrgEditProfileModal">修改资料</button>
      </view>
      <view v-else-if="currentOrg.status === 'expired'" class="org-status-alert-strip expired-strip">
        <view class="osas-left">
          <text class="osas-title">🚫 临时状态已超 14 天到期</text>
          <text class="osas-desc">未在有效期内获得管理员批准，已被禁止访问大群。请重新凭邀请码认证申请或联系管理员。</text>
        </view>
      </view>
    </view>

    <!-- ── 🏛️ 未加入大组织认证入口 (选填，支持多大群体) ── -->
    <view v-if="!currentOrg" class="grand-org-prompt-card">
      <view class="gop-badge-row">
        <text class="gop-badge">🏛️ 高校戈友 / 联盟大群体认证</text>
        <text class="gop-code-pill">凭组织专属码验证</text>
      </view>
      <text class="gop-title">加入高校戈友 / 商学院大群体架构</text>
      <text class="gop-desc">汇聚各大高校戈友会及商学院跑者。请向您所属群体的管理员索取专属邀请码，凭码实名登记姓名、班级与生日完成认证，解锁下属分队备战与花名册！（自由独立跑者可跳过）</text>
      <button class="gop-join-btn" @click="openOrgJoinModal">
        🔑 凭专属邀请码实名认证加入 (选填)
      </button>
    </view>


    <!-- ── 🚩 已加入大群体但未加入任何下属跑团时 ── -->
    <view v-if="currentOrg && userClubs.length === 0" class="subclubs-entry-section">
      <view class="section-card choose-subclub-card">
        <view class="csc-header-row">
          <view class="title-with-icon">
            <text class="icon">🚩</text>
            <text class="card-title">选择加入【{{ currentOrg.name }}】下属跑团</text>
          </view>
        </view>
        <text class="csc-intro-text">您已成功认证为【{{ currentOrg.class_name }}】{{ currentOrg.real_name }}，请在下方选择加入所属分跑团：</text>
        <view v-if="orgSubClubs.length === 0" class="empty-clubs-text">
          大群体下暂无已创建分跑团，请联系管理员创建！
        </view>
        <view v-else class="subclubs-grid-list">
          <view v-for="sc in orgSubClubs" :key="sc.id" class="subclub-item-box">
            <image class="sc-logo-img" :src="sc.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
            <view class="sc-content-box">
              <view class="sc-name-line">
                <text class="sc-name-title">{{ sc.name }}</text>
                <text class="mode-badge-pill" :class="sc.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                  {{ sc.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                </text>
                <text class="sc-city-tag">📍 {{ sc.city || '上海' }}</text>
              </view>
              <text class="sc-desc-line">{{ sc.description || '戈友备战与日常训练打卡分跑团' }}</text>
              <text class="sc-meta-line">团长: {{ sc.owner_name || '平台指定' }} · {{ sc.member_count || 1 }} 位队员</text>
            </view>
            <button class="sc-join-action-btn" :class="{ 'btn-invite-mode': sc.join_mode === 'invite' }" :loading="joiningClubId === sc.id" @click="handleJoinClubWithCheck(sc)">
              {{ sc.join_mode === 'invite' ? '🔑 凭码加入' : '+ 自由加入' }}
            </button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── 跑团快速切换横向标签栏 (仅在加入跑团后显示) ── -->
    <view v-if="userClubs.length > 0" class="clubs-switcher-wrap">
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
              :src="c.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'"
              mode="aspectFill"
            />
            <text class="tab-club-name">{{ c.name }}</text>
            <text v-if="currentClub?.id === c.id" class="tab-active-check">✓</text>
          </view>
          <view class="club-tab-pill tab-browse-btn" @click="openAllClubsModal">
            <text class="tab-browse-icon">＋ 发现跑团</text>
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- If user belongs to a club -->
    <view v-if="currentClub">
      <!-- ── Header: Club Hero ── -->
      <view class="club-hero-card">
        <view class="hero-top">
          <image class="club-logo" :src="currentClub.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
          <view class="club-text">
            <view class="name-row">
              <text class="club-name">{{ currentClub.name }}</text>
              <text class="role-tag" :class="'role-' + currentRole">
                {{ currentRole === "owner" ? "👑 跑团主理人" : currentRole === "coach" ? "🧢 认证教练" : "🏃 核心团员" }}
              </text>
            </view>
            <text class="club-desc">{{ currentClub.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。" }}</text>
            <view class="browse-all-btn" @click="openAllClubsModal">
              <text class="browse-text">⇄ 切换跑团 ({{ userClubs.length }}) / 发现跑团 ›</text>
            </view>
          </view>
        </view>
      </view>

      <!-- ── 🚫 跑团访问权限已暂停阻断屏 ── -->
      <view v-if="currentClub.is_access_suspended || isCurrentClubSuspended" class="section-card club-suspended-block-card">
        <view class="csb-icon-box">
          <text class="csb-icon">🚫</text>
        </view>
        <text class="csb-title">大团访问权限已暂停</text>
        <text class="csb-desc">
          跑团【{{ currentClub.name }}】隶属于【{{ currentClub.org_name || '大群体' }}】。{{ currentSuspensionReason || '您在大群体的2周临时访问期已过。由于超期未完成所有必填字段填写并获管理员审核确认，已暂停浏览使用该大团及其从属跑团的一切内容和活动！' }}
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
        <!-- ── 跑团英雄榜与打卡动态直通卡 ── -->
        <view class="rank-banner-card" @click="goToRankPage">
          <view class="banner-left">
            <view class="banner-badge-row">
              <text class="banner-badge">🥇 英雄风云榜</text>
              <text class="banner-hint-pill">独立专页 ›</text>
            </view>
            <text class="banner-title">本月跑团英雄榜 · 打卡动态与 Canova教练点评</text>
            <text class="banner-desc">查看全团队员跑量排名、达标进度与 Canova教练动态互动</text>
          </view>
          <view class="banner-arrow-box">
            <text class="banner-arrow">→</text>
          </view>
        </view>

    <!-- ── CARD 1: 👑 团长管理中心 (Only visible to Owner) ── -->
    <view v-if="currentRole === 'owner' || isOwnerOrDev" class="section-card owner-panel-card">
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">👑</text>
          <text class="card-title">跑团主理人管理中心</text>
        </view>
        <text class="owner-pill">团长权限</text>
      </view>

      <view class="owner-actions-grid">
        <view class="owner-tool-item" @click="handleOpenMembersModal">
          <view class="tool-icon-box bg-purple">
            <text class="tool-icon">👥</text>
          </view>
          <view class="tool-content">
            <text class="tool-main-title">跑团成员与指定教练</text>
            <text class="tool-sub-desc">管理成员身份、指定或撤销认证教练 ({{ members.length }}人)</text>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view class="owner-tool-item" @click="handleOpenCreateEvent">
          <view class="tool-icon-box bg-orange">
            <text class="tool-icon">🏆</text>
          </view>
          <view class="tool-content">
            <text class="tool-main-title">发起跑团挑战赛</text>
            <text class="tool-sub-desc">创建跑量挑战活动与奖励规则 ({{ events.length }}个进行中)</text>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view v-if="currentOrg" class="owner-tool-item" @click="openOrgMembersModal">
          <view class="tool-icon-box bg-blue">
            <text class="tool-icon">🏛️</text>
          </view>
          <view class="tool-content">
            <text class="tool-main-title">{{ currentOrg.name }} 大群体花名册</text>
            <text class="tool-sub-desc">核对全体戈友班级、实名认证与归属 ({{ orgMembers.length }}人)</text>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view class="owner-tool-item" @click="openJoinModeModal">
          <view class="tool-icon-box bg-green">
            <text class="tool-icon">⚙️</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">入团门槛规则设置</text>
              <text class="mode-badge-pill" :class="currentClub?.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                {{ currentClub?.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
              </text>
            </view>
            <text class="tool-sub-desc">
              {{ currentClub?.join_mode === 'invite' ? '已开启专属邀请码入团，点击管理或切换为自由入团' : '已开启自由入团，戈友与跑者可直接点击加入' }}
            </text>
          </view>
          <text class="arrow-right">›</text>
        </view>

        <view class="owner-tool-item" @click="openReportModal">
          <view class="tool-icon-box bg-gold">
            <text class="tool-icon">📊</text>
          </view>
          <view class="tool-content">
            <view class="tool-title-row">
              <text class="tool-main-title">跑团周报与月报</text>
              <text class="mode-badge-pill mode-report">专属战报</text>
            </view>
            <text class="tool-sub-desc">
              生成本周/本月团队战报与Canova复盘，一键复制微信群转发格式并下载
            </text>
          </view>
          <text class="arrow-right">›</text>
        </view>
      </view>
    </view>

    <!-- ── CARD 2: 🧢 教练学员体能罗盘 (Visible to Owner & Coach) ── -->
    <view
      v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev"
      class="section-card coach-preview-card"
      @click="goToCockpitPage"
    >
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">🧢</text>
          <text class="card-title">教练学员负荷监控大盘</text>
        </view>
        <text class="sub-link">进入全队体能罗盘 ›</text>
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
    </view>

    <!-- ── CARD 3: 跑团挑战赛与活动 ── -->
    <view class="section-card">
      <view class="card-header-row">
        <view class="title-with-icon">
          <text class="icon">🏆</text>
          <text class="card-title">跑团挑战赛与活动 ({{ events.length }})</text>
        </view>
        <button
          v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev"
          class="mini-action-btn"
          @click="handleOpenCreateEvent"
        >
          + 发起挑战
        </button>
      </view>

      <view v-if="events.length" class="events-list">
        <view v-for="evt in events" :key="evt.id" class="event-card">
          <view class="evt-top">
            <text class="evt-tag">月度挑战</text>
            <view v-if="currentRole === 'owner' || currentRole === 'coach' || isOwnerOrDev" class="evt-actions">
              <text class="evt-btn edit" @click="handleOpenEditEvent(evt)">编辑</text>
              <text class="evt-btn del" @click="handleDeleteEvent(evt.id)">删除</text>
            </view>
          </view>
          <text class="evt-title">{{ evt.title }}</text>
          <text class="evt-rules">{{ evt.rules }}</text>
          <view class="evt-footer">
            <text class="evt-target">目标: <text class="highlight">{{ evt.target_km }} km</text></text>
            <text class="evt-status">进行中</text>
          </view>
        </view>
      </view>
      <view v-else class="empty-box">
        <text class="empty-text">暂无进行中的跑团活动</text>
      </view>
    </view>
    </view>
    </view>

    <!-- ── Unjoined State: Free / Solo Runner View + Club Options ── -->
    <view v-else class="unjoined-club-view">
      <!-- ── 🏃 自由跑者独立训练模式专属卡片 ── -->
      <view class="solo-runner-card">
        <view class="src-top-row">
          <view class="src-badge-box">
            <text class="src-badge-icon">🏃</text>
            <text class="src-badge-text">自由跑者独立训练中</text>
            <text class="src-status-pill">免入团畅享全功能</text>
          </view>
        </view>
        <text class="src-title">无需入团，即可畅享科技跑步全功能</text>
        <text class="src-desc">您当前处于自由独立训练模式。佳明与高驰手表运动直连同步、Canova AI 私教深度对话、CTL/ATL/TSB 负荷体能罗盘以及个人跑量与 PB 目标设定均对您 100% 开放，完全无门槛！</text>
        <view class="src-actions-row">
          <button class="src-btn outline" @click="goToIndexPage">
            ⌚ 首页打卡与手表同步
          </button>
          <button class="src-btn primary" @click="goToCoachPage">
            💬 咨询 Canova教练
          </button>
        </view>
      </view>

      <view class="unjoined-hero-box">
        <view class="unjoined-badge">🤝 寻找跑团与队友</view>
        <text class="unjoined-hero-title">想要与队友合练备战？</text>
        <text class="unjoined-hero-sub">在下方浏览平台跑团或输入专属码加入，与队友共同打卡月度挑战、查看团队英雄榜与教练负荷监控！（自由跑者选填）</text>
        <view class="unjoined-btn-row">
          <button class="unjoined-action-btn secondary-invite" @click="showJoinModal = true">
            🔑 输入跑团邀请码加入
          </button>
        </view>
      </view>

      <!-- All Created Clubs List -->
      <view class="section-card all-clubs-sec">
        <view class="sec-title-row">
          <view class="title-left">
            <text class="sec-title">🏆 平台跑团列表 (选填)</text>
            <text class="count-tag">{{ allClubs.length }} 个跑团</text>
          </view>
          <text class="sec-hint">自由入团或凭专属码入团</text>
        </view>

        <view v-if="allClubs.length === 0" class="empty-clubs-text">
          平台暂无已创建跑团，请联系平台管理员创建！
        </view>

        <view v-else class="clubs-list-wrap">
          <view v-for="club in allClubs" :key="club.id" class="club-select-card">
            <image class="csc-logo" :src="club.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
            <view class="csc-body">
              <view class="csc-title-row">
                <text class="csc-name">{{ club.name }}</text>
                <text v-if="club.org_name" class="org-tag-pill">🏛️ {{ club.org_name }}</text>
                <text v-else class="org-tag-pill free-tag">🍃 独立跑团</text>
                <text class="mode-badge-pill" :class="club.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                  {{ club.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                </text>
                <text class="csc-city">📍 {{ club.city || "上海" }}</text>
              </view>
              <text class="csc-desc">{{ club.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。" }}</text>
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

      <view class="section-card unjoined-highlights">
        <text class="unjoined-sec-title">加入跑团即可解锁：</text>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🥇</text>
          <view class="uh-content">
            <text class="uh-title">跑团月度跑量英雄榜</text>
            <text class="uh-desc">自动汇总全体团员月跑量与排名，良性竞逐突破个人 PB</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🏆</text>
          <view class="uh-content">
            <text class="uh-title">专属跑量挑战赛与活动</text>
            <text class="uh-desc">团长发起目标里程挑战，团员打卡达标解锁专属荣誉</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">💬</text>
          <view class="uh-content">
            <text class="uh-title">跑友圈动态与 Canova教练互动</text>
            <text class="uh-desc">同步跑步记录自动生成 Canova教练战报与点评，队友点赞留言互勉</text>
          </view>
        </view>
        <view class="unjoined-highlight-item">
          <text class="uh-icon">🧢</text>
          <view class="uh-content">
            <text class="uh-title">教练学员体能罗盘</text>
            <text class="uh-desc">科学监控学员 CTL/ATL/TSB 负荷与状态，预防过度训练与伤病</text>
          </view>
        </view>
      </view>
    </view>

    <!-- ── Member & Coach Management Modal (跑团成员与指定教练管理) ── -->
    <view v-if="showMembersModal" class="modal-mask" @click="showMembersModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">跑团成员与指定教练</text>
            <text class="count-pill">{{ members.length }}人</text>
          </view>
          <text class="close-btn" @click="showMembersModal = false">✕</text>
        </view>

        <text class="modal-intro">💡 团长可在此任命【认证教练】协助指导学员体能负荷，或调整成员权限。</text>

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
            <view v-if="m.role !== 'owner'" class="m-actions">
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
                @click="handleRemoveMember(m.user_id, m.display_name)"
              >
                移出
              </button>
            </view>
            <view v-else class="owner-static-tag">
              <text class="owner-tag-text">跑团主理人</text>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- ── Create / Edit Event Modal ── -->
    <view v-if="showEventModal" class="modal-mask" @click="showEventModal = false" @touchmove.stop.prevent>
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">{{ editingEventId ? '编辑跑团活动' : '发起跑团挑战赛' }}</text>
          <text class="close-btn" @click="showEventModal = false">✕</text>
        </view>

        <view class="modal-body">
          <text class="input-label">活动标题</text>
          <input
            class="text-input"
            type="text"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="例如: 9月 200km 破风进阶挑战"
            v-model="eventTitle"
          />

          <text class="input-label">目标跑量 (km)</text>
          <input
            class="text-input"
            type="number"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="200"
            v-model="eventTargetKm"
          />

          <text class="input-label">挑战规则与奖励说明</text>
          <textarea
            class="textarea-input"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="完赛即可解锁专属电子勋章与跑团定制奖章..."
            v-model="eventRules"
          />

          <button class="submit-btn" :loading="savingEvent" @click="handleSaveEvent">
            {{ editingEventId ? '保存修改' : '立即发布' }}
          </button>
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
          <text class="input-label">跑团专属 6 位邀请码</text>
          <input
            class="text-input"
            type="text"
            maxlength="10"
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

    <!-- ── All Clubs Modal (浏览与切换全部跑团) ── -->
    <view v-if="showAllClubsModal" class="modal-mask" @click="showAllClubsModal = false" @touchmove.stop.prevent>
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

        <view class="modal-body modal-scroll">
          <view v-if="displayedClubs.length === 0" class="empty-clubs-text">
            {{ clubModalTab === 'joined' ? '您尚未加入任何跑团，请切换至“平台全部”选择加入！' : '平台暂无其他已创建跑团。' }}
          </view>
          <view v-else class="modal-clubs-list">
            <view
              v-for="c in displayedClubs"
              :key="c.id"
              class="modal-club-card"
              :class="{ 'is-current': currentClub?.id === c.id }"
              @click="c.is_member ? handleSwitchClub(c) : null"
            >
              <image class="mcc-logo" :src="c.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="mcc-info">
                <view class="mcc-name-row">
                  <text class="mcc-name">{{ c.name }}</text>
                  <text class="mode-badge-pill" :class="c.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                    {{ c.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                  </text>
                  <text class="mcc-city">📍 {{ c.city || '上海' }}</text>
                </view>
                <text class="mcc-desc">{{ c.description || '精英跑者联盟，追求 PB 突破与健康长久奔跑。' }}</text>
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
      </view>
    </view>

    <!-- ── 1. Join Grand Organization Modal (大群体实名认证资料弹窗) ── -->
    <view v-if="showOrgJoinModal" class="modal-mask" @click="showOrgJoinModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">{{ isUpdatingOrgProfile ? "补全 / 修改大群体资料" : "加入大群体 · 戈友实名认证" }}</text>
            <text class="count-pill">{{ isUpdatingOrgProfile ? (currentOrg?.name || "大群体") : "凭专属码认证" }}</text>
          </view>
          <text class="close-btn" @click="showOrgJoinModal = false">✕</text>
        </view>

        <view class="modal-body org-form-body">
          <view class="privacy-security-notice">
            <view class="privacy-badge-row">
              <text class="privacy-badge-icon">🛡️</text>
              <text class="privacy-badge-title">个人隐私与数据安全保障</text>
              <text class="privacy-badge-tag">AES-256 加密</text>
            </view>
            <text class="privacy-security-desc">
              真实姓名、证件号、出生日期及手机号均在数据库底层采用 AES-256 密文存储，非必要不暴露，仅用于戈赛资格核验与分组合规。普通跑友无法查看您的明文隐私，且支持随时一键彻底清除。
            </text>
          </view>

          <view v-if="!isUpdatingOrgProfile" class="form-group">
            <text class="input-label">大群体专属邀请码 <text class="req-star">*</text></text>
            <input
              class="text-input"
              type="text"
              placeholder="请输入大群体专属邀请码"
              v-model="orgJoinForm.invite_code"
            />
          </view>

          <view class="form-group">
            <view class="label-with-icon-row">
              <text class="input-label">真实姓名 <text class="req-star">*</text></text>
              <text class="field-security-pill">🔒 加密存储</text>
            </view>
            <view class="secure-input-wrapper">
              <input
                class="text-input secure-input"
                :password="!showOrgRealName"
                type="text"
                placeholder="请填写真实姓名以便管理员核实"
                v-model="orgJoinForm.real_name"
              />
              <view class="eye-toggle-btn" @click="showOrgRealName = !showOrgRealName">
                <text class="eye-icon">{{ showOrgRealName ? '👁️' : '🙈' }}</text>
              </view>
            </view>
          </view>

          <view class="form-group">
            <text class="input-label">性别 <text class="req-star">*</text></text>
            <view class="gender-segmented-row">
              <view
                class="gender-pill"
                :class="{ active: orgJoinForm.gender === 'male' }"
                @click="orgJoinForm.gender = 'male'"
              >
                🚹 男
              </view>
              <view
                class="gender-pill"
                :class="{ active: orgJoinForm.gender === 'female' }"
                @click="orgJoinForm.gender = 'female'"
              >
                🚺 女
              </view>
            </view>
          </view>

          <view class="form-group">
            <view class="label-with-icon-row">
              <text class="input-label">出生日期 <text class="req-star">*</text></text>
              <text class="field-security-pill">🔒 密文分级</text>
            </view>
            <view class="secure-picker-row">
              <picker mode="date" :value="orgJoinForm.date_of_birth" @change="onOrgDobChange" class="secure-picker-flex">
                <view class="picker-display-box">
                  <text class="picker-value">
                    {{ showOrgDob ? (orgJoinForm.date_of_birth || '请选择出生日期') : (orgJoinForm.date_of_birth ? '****-**-**' : '请选择出生日期') }}
                  </text>
                  <text class="picker-arrow">📅 选择 ›</text>
                </view>
              </picker>
              <view class="eye-toggle-btn" @click.stop="showOrgDob = !showOrgDob">
                <text class="eye-icon">{{ showOrgDob ? '👁️' : '🙈' }}</text>
              </view>
            </view>
            <text class="field-hint">点击眼睛符号显示/隐藏。对外仅展示组别脱敏保护隐私</text>
          </view>

          <view class="form-group">
            <view class="label-with-icon-row">
              <text class="input-label">身份证号码 / 证件号 (选填)</text>
              <text class="field-security-pill">🔒 密文存储</text>
            </view>
            <view class="secure-input-wrapper">
              <input
                class="text-input secure-input"
                :password="!showOrgIdCard"
                type="text"
                maxlength="18"
                placeholder="用于赛事保险投保与参赛资格核验"
                v-model="orgJoinForm.id_card"
              />
              <view class="eye-toggle-btn" @click="showOrgIdCard = !showOrgIdCard">
                <text class="eye-icon">{{ showOrgIdCard ? '👁️' : '🙈' }}</text>
              </view>
            </view>
            <text class="field-hint">默认以 *** 隐藏，点击眼睛符号才完整显示。非必要绝不向第三方暴露</text>
          </view>

          <!-- 商学院项目与自由班级 -->
          <view class="form-group">
            <text class="input-label">商学院项目 <text class="req-star">*</text></text>
            <view class="program-chips-grid">
              <view
                v-for="p in ORG_PROGRAM_OPTIONS"
                :key="p"
                class="program-chip"
                :class="{ active: orgJoinForm.program === p }"
                @click="orgJoinForm.program = p"
              >
                {{ p }}
              </view>
            </view>
          </view>

          <view class="form-group">
            <text class="input-label">所在班级 / 届别 (自由输入) <text class="req-star">*</text></text>
            <input
              class="text-input"
              type="text"
              placeholder="例如: 23春 / 21级 / 18班 / 2022秋"
              v-model="orgJoinForm.class_detail"
            />
            <text v-if="orgJoinForm.program && orgJoinForm.class_detail" class="field-preview-tag">
              班级组合预览：{{ orgJoinForm.program }} {{ orgJoinForm.class_detail }}
            </text>
          </view>

          <!-- 戈壁经历体系 (新戈 / 戈1-戈21 + A/B/C组) -->
          <view class="form-group">
            <view class="label-with-icon-row">
              <text class="input-label">戈壁经历 (戈赛经验) <text class="req-star">*</text></text>
              <text class="field-security-pill">🏅 戈友身份</text>
            </view>
            <view class="gobi-type-segmented-row">
              <view
                class="gobi-type-pill"
                :class="{ active: orgJoinForm.gobi_type === 'new' }"
                @click="orgJoinForm.gobi_type = 'new'"
              >
                🌱 新戈 (首次参赛)
              </view>
              <view
                class="gobi-type-pill"
                :class="{ active: orgJoinForm.gobi_type === 'vet' }"
                @click="orgJoinForm.gobi_type = 'vet'"
              >
                🏅 往届戈友 (老戈)
              </view>
            </view>

            <!-- 老戈友届数与组别选择器 -->
            <view v-if="orgJoinForm.gobi_type === 'vet'" class="vet-gobi-box">
              <view class="vet-row">
                <text class="vet-label">参赛届数：</text>
                <picker
                  mode="selector"
                  :range="GOBI_EDITION_OPTIONS"
                  :value="selectedGobiEditionIndex"
                  @change="onGobiEditionChange"
                  class="vet-picker"
                >
                  <view class="vet-picker-box">
                    <text class="vpb-value">{{ orgJoinForm.gobi_edition || '选择届数' }}</text>
                    <text class="vpb-arrow">▼</text>
                  </view>
                </picker>
              </view>

              <view class="vet-row">
                <text class="vet-label">参赛组别：</text>
                <view class="group-pills-row">
                  <view
                    v-for="grp in GOBI_GROUP_OPTIONS"
                    :key="grp"
                    class="grp-pill"
                    :class="{ active: orgJoinForm.gobi_group === grp }"
                    @click="orgJoinForm.gobi_group = grp"
                  >
                    {{ grp }}
                  </view>
                </view>
              </view>

              <view class="vet-summary-row">
                <text class="vet-summary-text">
                  经历勋章：<text class="vst-badge">🏅 {{ orgJoinForm.gobi_edition }} {{ orgJoinForm.gobi_group }}</text>
                </text>
              </view>
            </view>
          </view>

          <view class="form-group">
            <view class="label-with-icon-row">
              <text class="input-label">联系手机 (选填)</text>
              <text class="field-security-pill">🔒 保密</text>
            </view>
            <view class="secure-input-wrapper">
              <input
                class="text-input secure-input"
                :password="!showOrgPhone"
                type="number"
                maxlength="11"
                placeholder="便于紧急联络与赛事活动通知"
                v-model="orgJoinForm.phone"
              />
              <view class="eye-toggle-btn" @click="showOrgPhone = !showOrgPhone">
                <text class="eye-icon">{{ showOrgPhone ? '👁️' : '🙈' }}</text>
              </view>
            </view>
          </view>

          <view class="form-group">
            <text class="input-label">紧急联系人与电话 (选填)</text>
            <input
              class="text-input"
              type="text"
              placeholder="例如: 张三 13800000000"
              v-model="orgJoinForm.emergency_contact"
            />
          </view>

          <view class="form-group">
            <text class="input-label">跑鞋尺码 (EUR, 选填)</text>
            <input
              class="text-input"
              type="text"
              placeholder="例如: 42 / 42.5"
              v-model="orgJoinForm.running_shoe_size"
            />
          </view>

          <view class="form-group">
            <text class="input-label">队服尺码 (选填)</text>
            <input
              class="text-input"
              type="text"
              placeholder="例如: M / L / XL / 2XL"
              v-model="orgJoinForm.jersey_size"
            />
          </view>

          <view class="form-group">
            <text class="input-label">全马最好成绩 (PB, 选填)</text>
            <input
              class="text-input"
              type="text"
              placeholder="例如: 3:25:00"
              v-model="orgJoinForm.full_marathon_pb"
            />
          </view>

          <view class="form-group">
            <text class="input-label">健康与参赛声明 (选填)</text>
            <input
              class="text-input"
              type="text"
              placeholder="本人确认身体健康，无不适合高强度跑步的疾病"
              v-model="orgJoinForm.health_declaration"
            />
          </view>

          <button class="submit-btn org-submit-btn" :loading="joiningOrg" @click="submitOrgJoin">
            {{ isUpdatingOrgProfile ? "保存并提交审核" : "提交认证资料并加入大群体" }}
          </button>
        </view>
      </view>
    </view>

    <!-- ── 2. Sub Clubs Modal (下属跑团列表弹窗) ── -->
    <view v-if="showSubClubsModal" class="modal-mask" @click="showSubClubsModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">【{{ currentOrg?.name || '大组织' }}】下属分跑团</text>
            <text class="count-pill">{{ orgSubClubs.length }} 个分队</text>
          </view>
          <text class="close-btn" @click="showSubClubsModal = false">✕</text>
        </view>

        <view class="modal-body modal-scroll">
          <view v-if="orgSubClubs.length === 0" class="empty-clubs-text">
            该大群体下暂无分跑团，请联系平台管理员创建！
          </view>
          <view v-else class="modal-clubs-list">
            <view
              v-for="c in orgSubClubs"
              :key="c.id"
              class="modal-club-card"
              :class="{ 'is-current': currentClub?.id === c.id }"
              @click="c.is_member ? handleSwitchClub(c) : null"
            >
              <image class="mcc-logo" :src="c.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="mcc-info">
                <view class="mcc-name-row">
                  <text class="mcc-name">{{ c.name }}</text>
                  <text class="mode-badge-pill" :class="c.join_mode === 'invite' ? 'mode-invite' : 'mode-free'">
                    {{ c.join_mode === 'invite' ? '🔒 需邀请码' : '🟢 自由入团' }}
                  </text>
                  <text v-if="c.is_member" class="mcc-joined-badge">已加入</text>
                </view>
                <text class="mcc-desc">{{ c.description || '戈友备战与日常训练打卡分跑团' }}</text>
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
        </view>
      </view>
    </view>

    <!-- ── 3. Grand Community Roster Modal (大群体戈友花名册) ── -->
    <view v-if="showOrgMembersModal" class="modal-mask" @click="showOrgMembersModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">【{{ currentOrg?.name }}】戈友花名册</text>
            <text class="count-pill">{{ orgMembers.length }} 人</text>
          </view>
          <text class="close-btn" @click="showOrgMembersModal = false">✕</text>
        </view>

        <text class="modal-intro">💡 汇总大组织全体戈友的实名、班级与认证状态，管理员可核对确认。</text>

        <input
          class="search-member-input"
          type="text"
          :adjust-position="false"
          :cursor-spacing="30"
          placeholder="🔍 搜索戈友姓名、班级或戈壁经历(如戈20/新戈)..."
          v-model="orgMemberSearch"
        />

        <scroll-view scroll-y class="members-scroll">
          <view v-for="m in filteredOrgMembers" :key="m.user_id" class="member-row">
            <view class="m-left">
              <image class="m-avatar" :src="m.avatar_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80'" mode="aspectFill" />
              <view class="m-info">
                <view class="m-name-line">
                  <text class="m-name">{{ m.real_name || m.display_name }}</text>
                  <text class="m-class-tag">{{ m.class_name || '未设班级' }}</text>
                  <text v-if="m.gobi_experience" class="m-gobi-tag" :class="{ 'is-new': m.gobi_experience === '新戈' }">
                    {{ m.gobi_experience === '新戈' ? '🌱 新戈' : '🏅 ' + m.gobi_experience }}
                  </text>
                  <text class="m-status-pill" :class="m.status">{{ m.status === 'confirmed' ? '已核验' : (m.status === 'pending' ? '待审核' : '资料待补') }}</text>
                </view>
                <text class="m-sub-text">
                  {{ m.gender === 'female' ? '女' : '男' }} · {{ m.age_group || getAgeGroup(m.date_of_birth) }} · 分队: {{ m.sub_clubs && m.sub_clubs.length ? m.sub_clubs.map((s: any) => s.name).join('、') : '暂未入队' }}
                </text>
                <text v-if="m.status === 'temporary' && ((m.missing_required_fields && m.missing_required_fields.length) || (m.missing_fields && m.missing_fields.length))" class="m-missing-text" style="font-size: 20rpx; color: #f43f5e; display: block; margin-top: 4rpx;">
                  缺: {{ (m.missing_required_fields || m.missing_fields.map((f: any) => f.label || f.field)).join('、') }}
                </text>
              </view>
            </view>

            <view class="m-actions">
              <button
                v-if="m.status === 'pending'"
                class="act-pill coach-pill"
                @click="handleConfirmOrgMember(m.user_id)"
              >
                ✓ 核对通过
              </button>
              <text v-else-if="m.status === 'temporary'" class="incomplete-label" style="font-size: 22rpx; color: #f59e0b; padding: 6rpx 14rpx;">
                资料待补
              </text>
              <text v-else class="confirmed-label">✓ 已确认</text>
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
            <text class="modal-title">⚙️ 入团门槛规则设置</text>
            <text class="count-pill">{{ currentClub?.name }}</text>
          </view>
          <text class="close-btn" @click="showJoinModeModal = false">✕</text>
        </view>

        <view class="modal-body">
          <text class="jm-subtitle">请选择跑友加入【{{ currentClub?.name }}】的准入规则：</text>

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
                <text class="jm-opt-desc">
                  戈友与跑者无需输入邀请码，直接点击即可加入本跑团。适合日常公开吸纳跑友、班级跑团自由建队。
                </text>
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
                <text class="jm-opt-desc">
                  跑友必须输入本跑团专属邀请码才能加入。适合封闭式备战集训营、特定参赛梯队或私密跑团。
                </text>
              </view>
            </view>
          </view>

          <!-- Invite code display & copy if in invite mode -->
          <view v-if="selectedJoinMode === 'invite'" class="jm-code-box">
            <view class="jm-code-left">
              <text class="jm-code-label">本跑团专属 6 位邀请码：</text>
              <text class="jm-code-val">{{ currentClub?.invite_code || '生成中...' }}</text>
            </view>
            <button class="jm-copy-btn" @click="handleCopyClubInviteCode">
              复制邀请码
            </button>
          </view>

          <view class="modal-btn-row">
            <button class="btn-cancel" @click="showJoinModeModal = false">取消</button>
            <button class="btn-submit" :loading="savingJoinMode" @click="saveClubJoinMode">保存入团规则</button>
          </view>
        </view>
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
          <text class="prompt-hint-text">
            该跑团团长已设置【凭邀请码入团】，请输入团长分享的 6 位跑团专属邀请码：
          </text>

          <input
            class="club-code-input"
            type="text"
            maxlength="6"
            :adjust-position="false"
            :cursor-spacing="30"
            placeholder="请输入 6 位跑团邀请码"
            v-model="clubJoinCodeInput"
          />

          <view class="modal-btn-row">
            <button class="btn-cancel" @click="showClubCodeModal = false">取消</button>
            <button class="btn-submit" :loading="joiningClubId === targetClubForCodeJoin?.id" @click="submitClubCodeJoin">立即验证并加入</button>
          </view>
        </view>
      </view>
    </view>

    <!-- ── 6. Club Periodic Report Modal (跑团周报/月报专属战报弹窗) ── -->
    <view v-if="showReportModal" class="modal-mask" @click="showReportModal = false" @touchmove.stop.prevent>
      <view class="modal-content large-modal report-modal-content" @click.stop>
        <view class="modal-header">
          <view class="title-with-pill">
            <text class="modal-title">📊 跑团战报与复盘</text>
            <text class="count-pill report-owner-pill">👑 团长专属</text>
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
            📅 周报 (Weekly)
          </view>
          <view
            class="modal-tab-segment"
            :class="{ active: reportPeriodType === 'month' }"
            @click="handleSwitchReportPeriod('month')"
          >
            🗓️ 月报 (Monthly)
          </view>
        </view>

        <!-- Period selector: 本周/本月 vs 上周/上月 -->
        <view class="report-sub-tabs">
          <view
            class="report-sub-tab"
            :class="{ active: reportPeriodOffset === 0 }"
            @click="handleSwitchReportOffset(0)"
          >
            {{ reportPeriodType === 'week' ? '本周战报' : '本月战报' }}
          </view>
          <view
            class="report-sub-tab"
            :class="{ active: reportPeriodOffset === -1 }"
            @click="handleSwitchReportOffset(-1)"
          >
            {{ reportPeriodType === 'week' ? '上周战报' : '上月战报' }}
          </view>
        </view>

        <!-- View mode tabs: 🎨 战报海报图片 vs 💬 微信群文本 -->
        <view class="report-view-mode-tabs">
          <view
            class="report-view-tab"
            :class="{ active: reportViewMode === 'poster' }"
            @click="reportViewMode = 'poster'"
          >
            🎨 战报海报图片样式
          </view>
          <view
            class="report-view-tab"
            :class="{ active: reportViewMode === 'text' }"
            @click="reportViewMode = 'text'"
          >
            💬 微信群转发文本
          </view>
        </view>

        <!-- Loading State -->
        <view v-if="loadingReport" class="report-loading-box">
          <text class="loading-spinner">⏳</text>
          <text class="loading-text">正在汇算团队跑步大数据...</text>
        </view>

        <!-- Report Body -->
        <scroll-view v-else-if="reportData" scroll-y class="modal-body modal-scroll report-scroll-body">
          <!-- ── POSTER VIEW (图片海报样式) ── -->
          <view v-if="reportViewMode === 'poster'" class="poster-card-wrapper">
            <view class="report-poster-card">
              <!-- Top Branding Header -->
              <view class="poster-card-header">
                <view class="poster-brand-row">
                  <image
                    class="poster-club-logo"
                    :src="currentClub?.logo_url || 'https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=200&auto=format&fit=crop&q=80'"
                    mode="aspectFill"
                  />
                  <view class="poster-club-titles">
                    <text class="poster-club-name">{{ reportData.club_name || currentClub?.name }}</text>
                    <text class="poster-tagline">👑 跑团官方战报 · 荣誉榜</text>
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
                  <text class="pfs-slogan">跑者成长矩阵 · 科学耐力训练与跑团系统</text>
                </view>
                <view class="pfs-stamp-badge">
                  <text class="pfs-stamp-txt">认证战报</text>
                </view>
              </view>
            </view>
          </view>

          <!-- ── TEXT VIEW (微信群纯文本预览) ── -->
          <view v-else class="text-mode-container">
            <view class="report-section-box forward-box">
              <view class="forward-header">
                <text class="forward-title">💬 微信群转发排版预览</text>
                <text class="forward-hint">包含完整Emoji排版</text>
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
          style="width: 750px; height: 1340px; position: fixed; left: -9999px; top: -9999px;"
        ></canvas>

        <!-- Footer Actions -->
        <view class="report-footer-actions" v-if="reportData">
          <template v-if="reportViewMode === 'poster'">
            <button class="btn-preview-poster" @click="handlePreviewPosterImage">
              🖼️ 预览/转发海报
            </button>
            <button class="btn-save-album" @click="handleSavePosterToAlbum">
              💾 保存到相册
            </button>
            <button class="btn-sub-copy" @click="handleCopyReportForwardText">
              📋 复制文本
            </button>
          </template>
          <template v-else>
            <button class="btn-copy-forward" @click="handleCopyReportForwardText">
              📋 一键复制微信群转发文本
            </button>
            <button class="btn-download-report" @click="handleDownloadReportFile">
              📥 下载战报文本
            </button>
          </template>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import {
  request,
  getStoredUser,
  checkAndAutoLogin,
  UserProfile,
  getActiveClubId,
  setActiveClubId,
  resolveActiveClub,
} from "../../utils/api";

const user = ref<UserProfile | null>(null);
const currentClub = ref<any>(null);
const currentRole = ref("member");

const events = ref<any[]>([]);
const members = ref<any[]>([]);
const coachCockpit = ref<any>(null);

const showMembersModal = ref(false);
const memberSearchQuery = ref("");

const showEventModal = ref(false);
const showJoinModal = ref(false);
const showAllClubsModal = ref(false);

const inviteCodeInput = ref("");
const joiningClub = ref(false);
const joiningClubId = ref<string | null>(null);

// ── Grand Community / Organization State ──
const userOrgs = ref<any[]>([]);
const currentOrg = ref<any>(null);
const orgSubClubs = ref<any[]>([]);
const orgMembers = ref<any[]>([]);

const showOrgJoinModal = ref(false);
const showOrgMembersModal = ref(false);
const showSubClubsModal = ref(false);
const orgMemberSearch = ref("");
const joiningOrg = ref(false);

// ── Club Join Mode & Specific Code Prompt State ──
const showJoinModeModal = ref(false);
const selectedJoinMode = ref<"free" | "invite">("free");
const savingJoinMode = ref(false);

const showClubCodeModal = ref(false);
const targetClubForCodeJoin = ref<any>(null);
const clubJoinCodeInput = ref("");

// ── Club Periodic Report State ──
const showReportModal = ref(false);
const reportPeriodType = ref<"week" | "month">("week");
const reportPeriodOffset = ref(0);
const reportViewMode = ref<"poster" | "text">("poster");
const loadingReport = ref(false);
const reportData = ref<any>(null);

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

function openOrgJoinModal() {
  isUpdatingOrgProfile.value = false;
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
  showOrgJoinModal.value = true;
}

function openOrgEditProfileModal() {
  if (!currentOrg.value) return;
  isUpdatingOrgProfile.value = true;
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

async function submitOrgJoin() {
  const uid = user.value?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  if (!isUpdatingOrgProfile.value && !orgJoinForm.value.invite_code.trim()) {
    uni.showToast({ title: "请输入邀请码", icon: "none" });
    return;
  }

  const computedGobi = orgJoinForm.value.gobi_type === "new" ? "新戈" : `${orgJoinForm.value.gobi_edition} ${orgJoinForm.value.gobi_group}`;
  const computedClass = orgJoinForm.value.program
    ? `${orgJoinForm.value.program} ${orgJoinForm.value.class_detail}`.trim()
    : orgJoinForm.value.class_name.trim();

  if (!computedClass) {
    uni.showToast({ title: "请填写班级信息", icon: "none" });
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
        running_shoe_size: orgJoinForm.value.running_shoe_size.trim(),
        jersey_size: orgJoinForm.value.jersey_size.trim(),
        full_marathon_pb: orgJoinForm.value.full_marathon_pb.trim(),
        health_declaration: orgJoinForm.value.health_declaration.trim()
      });
      uni.showModal({
        title: "资料提交成功",
        content: res?.message || "大群体资料已成功更新！",
        showCancel: false
      });
    } else {
      const res = await request("/api/org/join", "POST", {
        user_id: uid,
        invite_code: orgJoinForm.value.invite_code.trim().toUpperCase(),
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
        running_shoe_size: orgJoinForm.value.running_shoe_size.trim(),
        jersey_size: orgJoinForm.value.jersey_size.trim(),
        full_marathon_pb: orgJoinForm.value.full_marathon_pb.trim(),
        health_declaration: orgJoinForm.value.health_declaration.trim()
      });
      uni.showModal({
        title: res?.status === "temporary" ? "临时人员已加入" : "加入申请已提交",
        content: res?.message || "加入大群体成功！",
        showCancel: false
      });
    }

    showOrgJoinModal.value = false;
    await loadClubData();
    if (orgSubClubs.value.length > 0 && userClubs.value.length === 0) {
      showSubClubsModal.value = true;
    }
  } catch (e: any) {
    uni.showModal({
      title: "操作提示",
      content: e?.message || e?.data?.detail || "认证操作失败，请核对后重试",
      showCancel: false
    });
  } finally {
    joiningOrg.value = false;
  }
}

function openSubClubsModal() {
  showSubClubsModal.value = true;
}

function openOrgMembersModal() {
  orgMemberSearch.value = "";
  showOrgMembersModal.value = true;
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

function openAllClubsModal() {
  clubModalTab.value = userClubs.value.length > 0 ? "joined" : "all";
  showAllClubsModal.value = true;
}

const displayedClubs = computed(() => {
  if (clubModalTab.value === "joined") {
    return allClubs.value.filter((c) => c.is_member);
  }
  return allClubs.value;
});

const editingEventId = ref<string | null>(null);
const eventTitle = ref("");
const eventTargetKm = ref<number | string>(200);
const eventRules = ref("");

const savingEvent = ref(false);

function goToRankPage() {
  uni.switchTab({
    url: "/pages/team/rank"
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


const isOwnerOrDev = computed(() => {
  if (!user.value || !currentClub.value) return false;
  return (
    currentRole.value === "owner" ||
    currentClub.value.owner_id === user.value.id
  );
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
    // 1. Fetch user organizations
    try {
      const orgRes = await request(`/api/org/my-orgs/${uid}`);
      userOrgs.value = orgRes?.organizations || [];
      if (userOrgs.value.length > 0) {
        currentOrg.value = userOrgs.value[0];
        const subRes = await request(`/api/org/${currentOrg.value.id}/sub-clubs?user_id=${uid}`);
        orgSubClubs.value = subRes?.sub_clubs || [];
        const memRes = await request(`/api/org/${currentOrg.value.id}/members?operator_uid=${uid}`);
        orgMembers.value = memRes?.members || [];
      } else {
        currentOrg.value = null;
        orgSubClubs.value = [];
        orgMembers.value = [];
      }
    } catch (err) {
      console.warn("Failed to load organizations:", err);
    }

    const [myRes, allRes] = await Promise.all([
      request(`/api/team/my-clubs/${uid}`),
      request(`/api/team/all-clubs?user_id=${uid}`)
    ]);

    const clubs = myRes?.clubs || [];
    userClubs.value = clubs;
    allClubs.value = allRes?.clubs || [];

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
        const [evtRes, memRes, coachRes] = await Promise.all([
          request(`/api/team/${clubId}/events?user_id=${uid}`).catch((e: any) => ({ error: e })),
          request(`/api/team/${clubId}/members?user_id=${uid}`).catch((e: any) => ({ error: e })),
          request(`/api/team/${clubId}/coach-cockpit?coach_uid=${uid}`).catch((e: any) => ({ error: e })),
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
          coachCockpit.value = coachRes || null;
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
      coachCockpit.value = null;
    }
  } catch (e) {
    console.warn("Load club data error:", e);
  }
}

function handleSwitchClub(club: any) {
  if (!club || !club.id) return;
  setActiveClubId(club.id);
  showAllClubsModal.value = false;
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
      title: "下属跑团准入限制",
      content: club.join_restriction_reason || "该跑团属于大群体架构，只有完成所有必须字段并获得管理员审核批准的正式成员方可加入。",
      showCancel: false
    });
    return;
  }
  if (club.join_mode === "invite") {
    targetClubForCodeJoin.value = club;
    clubJoinCodeInput.value = "";
    showClubCodeModal.value = true;
  } else {
    handleJoinClubDirect(club.id);
  }
}

async function submitClubCodeJoin() {
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
    };
    if (inviteCode) {
      payload.invite_code = inviteCode;
    }
    const res = await request("/api/team/join-club", "POST", payload);
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
  showJoinModeModal.value = true;
}

function handleCopyClubInviteCode() {
  const code = currentClub.value?.invite_code;
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

  savingJoinMode.value = true;
  try {
    const res = await request(`/api/team/${clubId}/join-mode`, "POST", {
      operator_uid: uid,
      join_mode: selectedJoinMode.value
    });
    if (currentClub.value) {
      currentClub.value.join_mode = selectedJoinMode.value;
    }
    uni.showToast({
      title: res?.message || "入团规则已更新",
      icon: "success"
    });
    showJoinModeModal.value = false;
    await loadClubData(clubId);
  } catch (err: any) {
    uni.showToast({
      title: err?.message || "设置失败，请重试",
      icon: "none"
    });
  } finally {
    savingJoinMode.value = false;
  }
}

// ── Club Periodic Report Handlers ──
function openReportModal() {
  if (!isOwnerOrDev.value) {
    uni.showToast({ title: "仅跑团团长有权查看与导出战报", icon: "none" });
    return;
  }
  reportPeriodType.value = "week";
  reportPeriodOffset.value = 0;
  showReportModal.value = true;
  fetchClubReport();
}

async function fetchClubReport() {
  const clubId = currentClub.value?.id;
  const uid = user.value?.id;
  if (!clubId || !uid) return;

  loadingReport.value = true;
  try {
    let url = `/api/team/${clubId}/reports?operator_uid=${uid}&period_type=${reportPeriodType.value}`;
    
    if (reportPeriodOffset.value === -1) {
      const now = new Date();
      if (reportPeriodType.value === "week") {
        // Compute last week's ISO week
        const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const target = new Date(d.valueOf());
        const dayNr = (d.getDay() + 6) % 7;
        target.setDate(target.getDate() - dayNr + 3);
        const firstThursday = target.valueOf();
        target.setMonth(0, 1);
        if (target.getDay() !== 4) {
          target.setMonth(0, 1 + ((4 - target.getDay()) + 7) % 7);
        }
        const weekNum = 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
        url += `&year=${d.getFullYear()}&period_index=${weekNum}`;
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

function handleCopyReportForwardText() {
  const text = reportData.value?.forward_text;
  if (!text) {
    uni.showToast({ title: "战报内容为空", icon: "none" });
    return;
  }
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

  const url = `https://rgm.vanpower.net/api/team/${clubId}/reports/export?operator_uid=${uid}&period_type=${reportPeriodType.value}`;
  
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

function generatePosterImage(): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!reportData.value) {
      reject(new Error("战报数据为空"));
      return;
    }

    const rep = reportData.value;
    const ctx = uni.createCanvasContext("reportPosterCanvas");

    const W = 750;
    const H = 1340;

    // 1. Background
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    bgGrad.addColorStop(0, "#0e1017");
    bgGrad.addColorStop(0.5, "#131620");
    bgGrad.addColorStop(1, "#0a0b10");
    ctx.setFillStyle(bgGrad);
    ctx.fillRect(0, 0, W, H);

    // Outer decorative border
    drawRoundedRect(ctx, 16, 16, W - 32, H - 32, 24, undefined, "rgba(255, 215, 0, 0.25)");

    // 2. Header Area
    drawRoundedRect(ctx, 40, 42, 190, 42, 21, "rgba(255, 215, 0, 0.15)", "rgba(255, 215, 0, 0.4)");
    ctx.setFontSize(20);
    ctx.setFillStyle("#ffd700");
    ctx.fillText("👑 跑团专属战报", 52, 71);

    // Club Name
    ctx.setFontSize(36);
    ctx.setFillStyle("#ffffff");
    ctx.fillText(rep.club_name || "跑团战报", 40, 130);

    // Period Label & Date range
    ctx.setFontSize(22);
    ctx.setFillStyle("#ffd700");
    ctx.fillText(`${rep.period_label} · ${rep.date_range_str}`, 40, 172);

    // Decorative separator line
    ctx.beginPath();
    ctx.moveTo(40, 195);
    ctx.lineTo(W - 40, 195);
    ctx.setStrokeStyle("rgba(255, 255, 255, 0.12)");
    ctx.stroke();

    // 3. Hero Total Distance Box
    drawRoundedRect(ctx, 40, 215, W - 80, 155, 20, "#181b26", "rgba(252, 76, 2, 0.35)");
    ctx.setFontSize(22);
    ctx.setFillStyle("#9ca3af");
    ctx.fillText("全团累计奔跑总里程", 64, 252);

    ctx.setFontSize(72);
    ctx.setFillStyle("#fc4c02");
    ctx.fillText(`${rep.total_distance_km}`, 64, 326);

    const kmWidth = ctx.measureText(`${rep.total_distance_km}`).width;
    ctx.setFontSize(30);
    ctx.setFillStyle("#9ca3af");
    ctx.fillText("KM", 64 + kmWidth + 12, 324);

    ctx.setFontSize(18);
    ctx.setFillStyle("#71717a");
    ctx.fillText("汇聚全员热血汗水 · 每一步都在突破极限", 64, 355);

    // 4. 4-Metrics Grid
    const gW = (W - 80 - 18) / 2;
    const gH = 92;

    // Item 1: 出勤率
    drawRoundedRect(ctx, 40, 390, gW, gH, 16, "#151722", "rgba(255, 255, 255, 0.08)");
    ctx.setFontSize(20);
    ctx.setFillStyle("#9ca3af");
    ctx.fillText("队员出勤率", 56, 422);
    ctx.setFontSize(30);
    ctx.setFillStyle("#ffffff");
    ctx.fillText(`${rep.attendance_rate_pct}%`, 56, 462);
    ctx.setFontSize(18);
    ctx.setFillStyle("#6b7280");
    ctx.fillText(`(${rep.active_members_count}/${rep.total_members_count}人)`, 160, 460);

    // Item 2: 全团均速
    drawRoundedRect(ctx, 40 + gW + 18, 390, gW, gH, 16, "#151722", "rgba(255, 255, 255, 0.08)");
    ctx.setFontSize(20);
    ctx.setFillStyle("#9ca3af");
    ctx.fillText("全团平均配速", 56 + gW + 18, 422);
    ctx.setFontSize(30);
    ctx.setFillStyle("#ffffff");
    ctx.fillText(`${rep.avg_pace_str}`, 56 + gW + 18, 462);

    // Item 3: 累计爬升
    drawRoundedRect(ctx, 40, 498, gW, gH, 16, "#151722", "rgba(255, 255, 255, 0.08)");
    ctx.setFontSize(20);
    ctx.setFillStyle("#9ca3af");
    ctx.fillText("累计爬升克服", 56, 530);
    ctx.setFontSize(30);
    ctx.setFillStyle("#ffffff");
    ctx.fillText(`+${rep.total_elevation_gain_m}m`, 56, 570);

    // Item 4: 打卡人次
    drawRoundedRect(ctx, 40 + gW + 18, 498, gW, gH, 16, "#151722", "rgba(255, 255, 255, 0.08)");
    ctx.setFontSize(20);
    ctx.setFillStyle("#9ca3af");
    ctx.fillText("累计打卡总人次", 56 + gW + 18, 530);
    ctx.setFontSize(30);
    ctx.setFillStyle("#ffffff");
    ctx.fillText(`${rep.total_activities_count} 次`, 56 + gW + 18, 570);

    // 5. 🏆 Top 3 Podium
    drawRoundedRect(ctx, 40, 606, W - 80, 235, 20, "#151722", "rgba(255, 215, 0, 0.3)");
    ctx.setFontSize(24);
    ctx.setFillStyle("#ffd700");
    ctx.fillText("🏆 荣誉榜单 Top 3", 60, 642);

    const podium = rep.podium || [];
    const medals = ["🥇 冠军", "🥈 亚军", "🥉 季军"];
    const medalBgs = ["rgba(255, 215, 0, 0.12)", "rgba(192, 192, 192, 0.10)", "rgba(205, 127, 50, 0.10)"];
    const medalStrokes = ["rgba(255, 215, 0, 0.35)", "rgba(192, 192, 192, 0.3)", "rgba(205, 127, 50, 0.3)"];

    for (let i = 0; i < 3; i++) {
      const pY = 660 + i * 55;
      if (podium[i]) {
        drawRoundedRect(ctx, 60, pY, W - 120, 48, 12, medalBgs[i], medalStrokes[i]);
        ctx.setFontSize(22);
        ctx.setFillStyle("#ffd700");
        ctx.fillText(medals[i], 76, pY + 32);

        ctx.setFontSize(22);
        ctx.setFillStyle("#ffffff");
        ctx.fillText(podium[i].display_name || "跑者", 185, pY + 32);

        ctx.setFontSize(22);
        ctx.setFillStyle("#fc4c02");
        ctx.fillText(`${podium[i].distance_km} km`, W - 250, pY + 32);

        ctx.setFontSize(18);
        ctx.setFillStyle("#9ca3af");
        ctx.fillText(podium[i].avg_pace_str || "—", W - 145, pY + 32);
      } else {
        ctx.setFontSize(18);
        ctx.setFillStyle("#52525b");
        ctx.fillText(`席位待定`, 76, pY + 32);
      }
    }

    // 6. 🌟 Highlights Row
    const hY = 858;
    const hW = (W - 80 - 18) / 2;
    if (rep.hardcore_runner) {
      drawRoundedRect(ctx, 40, hY, hW, 82, 14, "#151722", "rgba(56, 189, 248, 0.25)");
      ctx.setFontSize(18);
      ctx.setFillStyle("#38bdf8");
      ctx.fillText("🌟 毅力先锋", 54, hY + 28);
      ctx.setFontSize(20);
      ctx.setFillStyle("#ffffff");
      ctx.fillText(`${rep.hardcore_runner.display_name}`, 54, hY + 54);
      ctx.setFontSize(16);
      ctx.setFillStyle("#9ca3af");
      ctx.fillText(`打卡 ${rep.hardcore_runner.runs_count} 次 · ${rep.hardcore_runner.distance_km}km`, 54, hY + 74);
    }
    if (rep.longest_run) {
      drawRoundedRect(ctx, 40 + hW + 18, hY, hW, 82, 14, "#151722", "rgba(56, 189, 248, 0.25)");
      ctx.setFontSize(18);
      ctx.setFillStyle("#38bdf8");
      ctx.fillText("🚀 最长突破", 54 + hW + 18, hY + 28);
      ctx.setFontSize(20);
      ctx.setFillStyle("#ffffff");
      ctx.fillText(`${rep.longest_run.runner_name}`, 54 + hW + 18, hY + 54);
      ctx.setFontSize(16);
      ctx.setFillStyle("#9ca3af");
      ctx.fillText(`单次 ${rep.longest_run.distance_km}km · ${rep.longest_run.avg_pace_str}`, 54 + hW + 18, hY + 74);
    }

    // 7. 💡 Renato Canova Coach Critique Box
    const cY = 955;
    drawRoundedRect(ctx, 40, cY, W - 80, 225, 18, "#181624", "rgba(191, 90, 242, 0.35)");
    ctx.setFontSize(22);
    ctx.setFillStyle("#bf5af2");
    ctx.fillText("💡 Renato Canova 科学耐力团队复盘", 58, cY + 34);

    ctx.setFontSize(17);
    ctx.setFillStyle("#d1d5db");
    drawWrappedText(ctx, `“${rep.canova_critique}”`, 58, cY + 68, W - 116, 26, 5);

    // 8. Bottom Brand Stamp
    const fY = 1205;
    ctx.beginPath();
    ctx.moveTo(40, fY);
    ctx.lineTo(W - 40, fY);
    ctx.setStrokeStyle("rgba(255, 255, 255, 0.1)");
    ctx.stroke();

    ctx.setFontSize(22);
    ctx.setFillStyle("#ffffff");
    ctx.fillText("万跑跑团助手", 40, fY + 40);

    ctx.setFontSize(16);
    ctx.setFillStyle("#71717a");
    ctx.fillText("跑者成长矩阵 · 科学耐力训练与跑团系统 · 官方认证战报", 40, fY + 68);

    drawRoundedRect(ctx, W - 160, fY + 20, 120, 48, 12, "rgba(255, 215, 0, 0.15)", "rgba(255, 215, 0, 0.4)");
    ctx.setFontSize(18);
    ctx.setFillStyle("#ffd700");
    ctx.fillText("官方战报", W - 138, fY + 50);

    // Draw and export
    ctx.draw(false, () => {
      setTimeout(() => {
        uni.canvasToTempFilePath({
          canvasId: "reportPosterCanvas",
          destWidth: 1500, // 2x retina
          destHeight: 2640,
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
  uni.showLoading({ title: "正在渲染长图海报..." });
  try {
    const tempPath = await generatePosterImage();
    uni.hideLoading();
    uni.previewImage({
      current: tempPath,
      urls: [tempPath]
    });
    uni.showToast({ title: "长按图片可直接发送给朋友或保存", icon: "none", duration: 3500 });
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

async function handleJoinClub() {
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
    });
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
        title: "戈友大群体认证提示",
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
  uni.navigateTo({
    url: "/pages/team/cockpit"
  });
}

function handleOpenMembersModal() {
  memberSearchQuery.value = "";
  showMembersModal.value = true;
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
    uni.showToast({
      title: `已设为【${role === "coach" ? "认证教练" : role === "owner" ? "团长" : "普通团员"}】`,
      icon: "success",
    });
    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: e.message || "角色修改失败", icon: "none" });
  }
}

async function handleRemoveMember(targetUid: string, displayName: string) {
  if (!currentClub.value) return;
  const uid = user.value?.id;
  if (!uid) return;
  uni.showModal({
    title: "移出跑团",
    content: `确定要将【${displayName || "该成员"}】移出跑团吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await request(
            `/api/team/${currentClub.value.id}/members/${targetUid}?operator_uid=${uid}`,
            "DELETE"
          );
          uni.showToast({ title: "成员已移出", icon: "success" });
          await loadClubData();
        } catch (e: any) {
          uni.showToast({ title: "移出失败", icon: "none" });
        }
      }
    }
  });
}


function handleOpenCreateEvent() {
  editingEventId.value = null;
  eventTitle.value = "";
  eventTargetKm.value = 200;
  eventRules.value = "";
  showEventModal.value = true;
}

function handleOpenEditEvent(evt: any) {
  editingEventId.value = evt.id;
  eventTitle.value = evt.title || "";
  eventTargetKm.value = evt.target_km || 200;
  eventRules.value = evt.rules || "";
  showEventModal.value = true;
}

async function handleDeleteEvent(eventId: string) {
  if (!currentClub.value) return;
  uni.showModal({
    title: "确认删除",
    content: "确定要删除该跑团活动吗？",
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

async function handleSaveEvent() {
  if (!currentClub.value || !eventTitle.value.trim()) {
    uni.showToast({ title: "请输入活动标题", icon: "none" });
    return;
  }
  const uid = user.value?.id;
  if (!uid) return;
  savingEvent.value = true;
  try {
    if (editingEventId.value) {
      await request(`/api/team/${currentClub.value.id}/events/${editingEventId.value}`, "PUT", {
        operator_uid: uid,
        title: eventTitle.value.trim(),
        target_km: Number(eventTargetKm.value) || 200,
        rules: eventRules.value.trim()
      });
      uni.showToast({ title: "修改成功！", icon: "success" });
    } else {
      await request(`/api/team/${currentClub.value.id}/events`, "POST", {
        operator_uid: uid,
        title: eventTitle.value.trim(),
        target_km: Number(eventTargetKm.value) || 200,
        rules: eventRules.value.trim()
      });
      uni.showToast({ title: "发布成功！", icon: "success" });
    }
    showEventModal.value = false;
    await loadClubData();
  } catch (e: any) {
    uni.showToast({ title: "操作失败", icon: "none" });
  } finally {
    savingEvent.value = false;
  }
}

onShow(() => {
  loadClubData();
});

onPullDownRefresh(async () => {
  try {
    await loadClubData();
    uni.showToast({ title: "跑团数据已更新", icon: "success" });
  } catch (e) {
    uni.showToast({ title: "已是最新数据", icon: "none" });
  } finally {
    uni.stopPullDownRefresh();
  }
});
</script>

<style scoped>
.team-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 30rpx 30rpx 60rpx 30rpx;
  box-sizing: border-box;
}

/* ── 顶部导航胶囊切换条 ── */
.top-nav-capsule {
  display: flex;
  background-color: #16161a;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 40rpx;
  padding: 6rpx;
  margin-bottom: 24rpx;
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
  background: linear-gradient(135deg, #fc4c02 0%, #ff7300 100%);
  box-shadow: 0 4rpx 16rpx rgba(252, 76, 2, 0.35);
}

.nav-icon {
  font-size: 26rpx;
}

.nav-text {
  font-size: 26rpx;
  font-weight: bold;
  color: #a1a1aa;
}

.nav-segment.active .nav-text {
  color: #ffffff;
}

/* ── 跑团英雄榜与动态直通卡 ── */
.rank-banner-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(255, 159, 10, 0.08) 100%);
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(252, 76, 2, 0.12);
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
  color: #fc4c02;
  background-color: rgba(252, 76, 2, 0.18);
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
}

.banner-hint-pill {
  font-size: 18rpx;
  color: #ff9f0a;
  background-color: rgba(255, 159, 10, 0.15);
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.banner-title {
  font-size: 28rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
  margin-bottom: 4rpx;
}

.banner-desc {
  font-size: 20rpx;
  color: #a1a1aa;
  display: block;
  line-height: 1.4;
}

.banner-arrow-box {
  width: 56rpx;
  height: 56rpx;
  border-radius: 28rpx;
  background-color: rgba(252, 76, 2, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 16rpx;
}

.banner-arrow {
  font-size: 32rpx;
  color: #fc4c02;
  font-weight: bold;
}

.club-hero-card {
  background: linear-gradient(135deg, #1c1c20 0%, #131316 100%);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 32rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 0, 0, 0.5);
}

.hero-top {
  display: flex;
  gap: 24rpx;
}

.club-logo {
  width: 120rpx;
  height: 120rpx;
  border-radius: 24rpx;
  border: 2rpx solid rgba(252, 76, 2, 0.4);
}

.club-text {
  flex: 1;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.club-name {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
}

.role-tag {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
}

.role-owner {
  background-color: rgba(255, 159, 10, 0.25);
  color: #ff9f0a;
}

.role-coach {
  background-color: rgba(191, 90, 242, 0.25);
  color: #bf5af2;
}

.role-member {
  background-color: rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}

.club-desc {
  font-size: 22rpx;
  color: #8e8e93;
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
  color: #636366;
}

.invite-val {
  color: #fc4c02;
  font-weight: bold;
  font-family: monospace;
}

.copy-hint {
  color: #0a84ff;
  font-size: 20rpx;
}

.section-card {
  background-color: #151518;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 28rpx;
  padding: 28rpx;
  margin-bottom: 24rpx;
}

/* 👑 Owner Panel */
.owner-panel-card {
  background: linear-gradient(135deg, rgba(255, 159, 10, 0.1) 0%, #151518 100%);
  border: 1rpx solid rgba(255, 159, 10, 0.3);
}

.owner-pill {
  font-size: 20rpx;
  font-weight: bold;
  color: #ff9f0a;
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
  background-color: #1c1c20;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  transition: all 0.2s;
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
  background-color: rgba(191, 90, 242, 0.2);
}

.tool-icon-box.bg-orange {
  background-color: rgba(252, 76, 2, 0.2);
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
  color: #ffffff;
  display: block;
}

.tool-sub-desc {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
  display: block;
}

.arrow-right {
  font-size: 26rpx;
  color: #636366;
}

/* 🧢 Coach Preview */
.coach-preview-card {
  border: 1rpx solid rgba(191, 90, 242, 0.3);
  background: linear-gradient(135deg, rgba(191, 90, 242, 0.08) 0%, #151518 100%);
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
  color: #ffffff;
}

.sub-link {
  font-size: 22rpx;
  color: #bf5af2;
  font-weight: bold;
}

.sub-tip {
  font-size: 20rpx;
  color: #8e8e93;
}

.cockpit-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
}

.cockpit-tile {
  background-color: #1a1a1e;
  border-radius: 18rpx;
  padding: 16rpx 10rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1rpx solid transparent;
}

.cockpit-tile.green { border-color: rgba(48, 209, 88, 0.3); }
.cockpit-tile.blue { border-color: rgba(10, 132, 255, 0.3); }
.cockpit-tile.yellow { border-color: rgba(255, 214, 10, 0.3); }
.cockpit-tile.red { border-color: rgba(255, 69, 58, 0.3); }

.c-val {
  font-size: 28rpx;
  font-weight: 900;
  color: #ffffff;
}

.c-label {
  font-size: 18rpx;
  color: #8e8e93;
  margin-top: 6rpx;
}

/* Events */
.mini-action-btn {
  font-size: 22rpx;
  font-weight: bold;
  background: #fc4c02;
  color: #ffffff;
  padding: 0 18rpx;
  height: 52rpx;
  line-height: 52rpx;
  border-radius: 14rpx;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.event-card {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 22rpx;
}

.evt-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}

.evt-tag {
  font-size: 20rpx;
  color: #0a84ff;
  background-color: rgba(10, 132, 255, 0.15);
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.evt-actions {
  display: flex;
  gap: 16rpx;
}

.evt-btn {
  font-size: 22rpx;
}

.evt-btn.edit { color: #0a84ff; }
.evt-btn.del { color: #ff453a; }

.evt-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
  display: block;
}

.evt-rules {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 8rpx;
  display: block;
}

.evt-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
}

.evt-target {
  font-size: 22rpx;
  color: #8e8e93;
}

.evt-target .highlight {
  color: #fc4c02;
  font-weight: bold;
}

.evt-status {
  font-size: 20rpx;
  color: #30d158;
}

/* Leaderboard */
.leaderboard-list {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.rank-item {
  background-color: #1a1a1e;
  border-radius: 20rpx;
  padding: 18rpx 20rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rank-item.top-three {
  border: 1rpx solid rgba(255, 255, 255, 0.08);
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
  color: #8e8e93;
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
  color: #ffffff;
}

.mini-role-tag {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
}

.mini-role-tag.owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: #ff9f0a;
}

.mini-role-tag.coach {
  background-color: rgba(191, 90, 242, 0.2);
  color: #bf5af2;
}

.progress-sub {
  font-size: 20rpx;
  color: #8e8e93;
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
  color: #fc4c02;
  font-family: monospace;
}

.km-val .unit {
  font-size: 20rpx;
  font-weight: normal;
  color: #8e8e93;
}

.progress-bar-bg {
  width: 140rpx;
  height: 6rpx;
  background-color: #2c2c2e;
  border-radius: 3rpx;
  margin-top: 8rpx;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background-color: #fc4c02;
}

/* Feed */
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.feed-card {
  background-color: #1a1a1e;
  border-radius: 24rpx;
  padding: 24rpx;
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
  color: #ffffff;
  display: block;
}

.feed-act-name {
  font-size: 20rpx;
  color: #8e8e93;
  margin-top: 4rpx;
  display: block;
}

.feed-distance {
  text-align: right;
}

.feed-km {
  font-size: 36rpx;
  font-weight: 900;
  color: #fc4c02;
  font-family: monospace;
}

.feed-unit {
  font-size: 20rpx;
  color: #8e8e93;
  margin-left: 4rpx;
}

.coach-bubble {
  background: linear-gradient(135deg, rgba(191, 90, 242, 0.12) 0%, rgba(10, 132, 255, 0.08) 100%);
  border: 1rpx solid rgba(191, 90, 242, 0.25);
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
  color: #bf5af2;
}

.coach-comment-text {
  font-size: 22rpx;
  color: #e5e5ea;
  line-height: 1.4;
  display: block;
}

.social-bar {
  display: flex;
  gap: 24rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.05);
}

.like-btn, .comment-trigger-btn {
  display: flex;
  align-items: center;
  gap: 8rpx;
  padding: 6rpx 14rpx;
  border-radius: 10rpx;
  background-color: #242428;
}

.heart-icon, .cmt-icon {
  font-size: 22rpx;
}

.like-text, .cmt-text {
  font-size: 22rpx;
  color: #8e8e93;
}

.like-btn.liked .like-text {
  color: #ff3b30;
  font-weight: bold;
}

.comments-box {
  margin-top: 14rpx;
  background-color: #242428;
  border-radius: 14rpx;
  padding: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.cmt-item {
  font-size: 22rpx;
  line-height: 1.4;
}

.cmt-author {
  color: #0a84ff;
  font-weight: bold;
}

.cmt-content {
  color: #d1d1d6;
}

.empty-box {
  padding: 40rpx;
  text-align: center;
}

.empty-text {
  font-size: 24rpx;
  color: #636366;
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
}

.modal-content {
  width: 670rpx;
  background-color: #18181c;
  border-radius: 36rpx;
  padding: 40rpx;
  box-sizing: border-box;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  margin-bottom: 60rpx;
}

.modal-content.large-modal {
  max-height: 80vh;
  display: flex;
  flex-direction: column;
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
  color: #ffffff;
}

.count-pill {
  font-size: 20rpx;
  color: #bf5af2;
  background: rgba(191, 90, 242, 0.2);
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
}

.close-btn {
  font-size: 34rpx;
  color: #8e8e93;
}

.modal-intro {
  font-size: 22rpx;
  color: #8e8e93;
  margin-bottom: 20rpx;
  display: block;
}

.search-member-input {
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  height: 72rpx;
  padding: 0 20rpx;
  font-size: 24rpx;
  color: #ffffff;
  margin-bottom: 20rpx;
}

.members-scroll {
  max-height: 520rpx;
  display: flex;
  flex-direction: column;
}

.member-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.05);
}

.m-left {
  display: flex;
  align-items: center;
  gap: 16rpx;
  flex: 1;
}

.m-avatar {
  width: 72rpx;
  height: 72rpx;
  border-radius: 36rpx;
}

.m-info {
  flex: 1;
}

.m-name-line {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.m-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
}

.m-role-tag {
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  font-weight: bold;
}

.tag-owner {
  background-color: rgba(255, 159, 10, 0.2);
  color: #ff9f0a;
}

.tag-coach {
  background-color: rgba(191, 90, 242, 0.2);
  color: #bf5af2;
}

.tag-member {
  background-color: rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}

.m-sub-text {
  font-size: 20rpx;
  color: #636366;
  margin-top: 4rpx;
  display: block;
}

.m-actions {
  display: flex;
  gap: 10rpx;
}

.act-pill {
  font-size: 20rpx;
  font-weight: bold;
  padding: 0 14rpx;
  height: 48rpx;
  line-height: 48rpx;
  border-radius: 12rpx;
  border: none;
}

.coach-pill {
  background: rgba(191, 90, 242, 0.25);
  color: #bf5af2;
}

.member-pill {
  background: rgba(255, 255, 255, 0.1);
  color: #8e8e93;
}

.del-pill {
  background: rgba(255, 69, 58, 0.15);
  color: #ff453a;
}

.owner-static-tag {
  font-size: 20rpx;
  color: #ff9f0a;
  font-weight: bold;
}

.input-label {
  font-size: 24rpx;
  color: #8e8e93;
  margin-top: 16rpx;
  margin-bottom: 8rpx;
  display: block;
}

.input-hint {
  font-size: 22rpx;
  color: #8e8e93;
  margin-bottom: 16rpx;
  display: block;
}

.text-input {
  width: 100%;
  height: 80rpx;
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 0 20rpx;
  font-size: 26rpx;
  color: #ffffff;
  box-sizing: border-box;
}

.textarea-input {
  width: 100%;
  height: 140rpx;
  background-color: #242429;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  font-size: 24rpx;
  color: #ffffff;
  box-sizing: border-box;
}

.submit-btn {
  width: 100%;
  height: 84rpx;
  line-height: 84rpx;
  background: #fc4c02;
  color: #ffffff;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 20rpx;
  margin-top: 24rpx;
  border: none;
}

/* Unjoined State Styles */
.unjoined-club-view {
  display: flex;
  flex-direction: column;
  gap: 30rpx;
}

.unjoined-hero-box {
  background: linear-gradient(135deg, #18181c 0%, #121215 100%);
  border-radius: 36rpx;
  padding: 50rpx 40rpx;
  text-align: center;
  border: 1rpx solid rgba(252, 76, 2, 0.25);
  box-shadow: 0 16rpx 40rpx rgba(0, 0, 0, 0.4);
}

.unjoined-badge {
  display: inline-block;
  font-size: 22rpx;
  font-weight: bold;
  color: #fc4c02;
  background: rgba(252, 76, 2, 0.15);
  padding: 6rpx 20rpx;
  border-radius: 20rpx;
  margin-bottom: 24rpx;
}

.unjoined-hero-title {
  font-size: 38rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
  margin-bottom: 16rpx;
}

.unjoined-hero-sub {
  font-size: 24rpx;
  color: #8e8e93;
  line-height: 1.6;
  display: block;
  margin-bottom: 40rpx;
  padding: 0 10rpx;
}

.unjoined-btn-row {
  display: flex;
  gap: 20rpx;
  justify-content: center;
}

.unjoined-action-btn {
  flex: 1;
  height: 84rpx;
  line-height: 84rpx;
  font-size: 28rpx;
  font-weight: bold;
  border-radius: 24rpx;
  border: none;
}

.unjoined-action-btn.primary-join {
  background: #fc4c02;
  color: #ffffff;
  box-shadow: 0 8rpx 20rpx rgba(252, 76, 2, 0.3);
}

.unjoined-action-btn.secondary-invite {
  background: #242429;
  color: #ffffff;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}

.browse-all-btn {
  display: inline-flex;
  align-items: center;
  margin-top: 14rpx;
  padding: 8rpx 18rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 20rpx;
}

.browse-text {
  font-size: 22rpx;
  color: #a1a1aa;
  font-weight: 500;
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
  background: rgba(252, 76, 2, 0.15);
  color: #fc4c02;
  padding: 2rpx 12rpx;
  border-radius: 12rpx;
  font-weight: bold;
}

.sec-hint {
  font-size: 22rpx;
  color: #71717a;
}

.empty-clubs-text {
  text-align: center;
  padding: 40rpx 20rpx;
  font-size: 24rpx;
  color: #71717a;
}

.clubs-list-wrap {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.club-select-card {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 20rpx;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
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
  justify-content: space-between;
  margin-bottom: 6rpx;
}

.csc-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.csc-city {
  font-size: 20rpx;
  color: #a1a1aa;
  flex-shrink: 0;
}

.csc-desc {
  font-size: 22rpx;
  color: #71717a;
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
  color: #a1a1aa;
}

.csc-meta.highlight {
  color: #fc4c02;
  font-weight: bold;
}

.csc-dot {
  font-size: 20rpx;
  color: #52525b;
}

.csc-join-btn {
  background: #fc4c02;
  color: #ffffff;
  font-size: 24rpx;
  font-weight: bold;
  padding: 0 28rpx;
  height: 60rpx;
  line-height: 60rpx;
  border-radius: 14rpx;
  border: none;
  flex-shrink: 0;
  margin: 0;
}

/* 弹窗中的所有跑团列表 */
.modal-scroll {
  max-height: 65vh;
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
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 20rpx;
}

.modal-club-card.is-current {
  border-color: rgba(252, 76, 2, 0.4);
  background: rgba(252, 76, 2, 0.06);
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
  justify-content: space-between;
  margin-bottom: 4rpx;
}

.mcc-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #ffffff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcc-city {
  font-size: 20rpx;
  color: #a1a1aa;
  flex-shrink: 0;
}

.mcc-desc {
  font-size: 20rpx;
  color: #71717a;
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
  color: #a1a1aa;
}

.mcc-meta .highlight {
  color: #fc4c02;
  font-weight: bold;
}

.mcc-dot {
  font-size: 20rpx;
  color: #52525b;
}

.mcc-action {
  flex-shrink: 0;
  margin-left: 12rpx;
}

.mcc-current-tag {
  font-size: 22rpx;
  color: #fc4c02;
  font-weight: bold;
  padding: 6rpx 16rpx;
  background: rgba(252, 76, 2, 0.15);
  border-radius: 12rpx;
}

.mcc-switch-btn {
  background: #27272a;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: 500;
  padding: 0 24rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 12rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  margin: 0;
}

.mcc-join-btn {
  background: #fc4c02;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: bold;
  padding: 0 24rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 12rpx;
  border: none;
  margin: 0;
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
  background: rgba(255, 255, 255, 0.05);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  padding: 10rpx 20rpx;
  border-radius: 30rpx;
  transition: all 0.2s ease;
}

.club-tab-pill.active {
  background: rgba(252, 76, 2, 0.18);
  border-color: #fc4c02;
  box-shadow: 0 4rpx 14rpx rgba(252, 76, 2, 0.25);
}

.tab-club-logo {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
}

.tab-club-name {
  font-size: 24rpx;
  font-weight: bold;
  color: #d4d4d8;
  max-width: 220rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.club-tab-pill.active .tab-club-name {
  color: #ffffff;
}

.tab-active-check {
  font-size: 22rpx;
  color: #fc4c02;
  font-weight: 900;
}

.club-tab-pill.tab-browse-btn {
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx dashed rgba(255, 255, 255, 0.2);
}

.tab-browse-icon {
  font-size: 22rpx;
  color: #a1a1aa;
}

/* 弹窗分栏标签 */
.modal-tab-row {
  display: flex;
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
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
  color: #a1a1aa;
  padding: 12rpx 0;
  border-radius: 16rpx;
  transition: all 0.2s ease;
}

.modal-tab-segment.active {
  background: #27272a;
  color: #fc4c02;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.3);
}

.mcc-role-tag {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  font-weight: bold;
}

.mcc-role-tag.role-owner {
  background: rgba(255, 159, 10, 0.2);
  color: #ff9f0a;
}

.mcc-role-tag.role-coach {
  background: rgba(10, 132, 255, 0.2);
  color: #0a84ff;
}

.mcc-role-tag.role-member {
  background: rgba(255, 255, 255, 0.1);
  color: #a1a1aa;
}

.unjoined-highlights {
  padding: 36rpx;
}

.unjoined-sec-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
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
  color: #ffffff;
  margin-bottom: 6rpx;
  display: block;
}

.uh-desc {
  font-size: 22rpx;
  color: #8e8e93;
  line-height: 1.5;
  display: block;
}
/* ── 🏛️ 大群体组织铭牌 ── */
.org-banner-card {
  background: linear-gradient(135deg, rgba(30, 27, 46, 0.95) 0%, rgba(20, 20, 28, 0.95) 100%);
  border: 1rpx solid rgba(139, 92, 246, 0.3);
  border-radius: 28rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.35);
}

.org-banner-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16rpx;
}

.org-badge-box {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.org-badge-icon {
  font-size: 32rpx;
}

.org-badge-title {
  font-size: 28rpx;
  font-weight: 900;
  color: #ffffff;
  letter-spacing: 0.5rpx;
}

.org-auth-status {
  font-size: 20rpx;
  font-weight: bold;
  padding: 4rpx 14rpx;
  border-radius: 20rpx;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1rpx solid rgba(16, 185, 129, 0.3);
}

.org-auth-status.pending {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  border-color: rgba(59, 130, 246, 0.3);
}

.org-auth-status.temporary {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.35);
}

.org-auth-status.expired {
  background: rgba(244, 63, 94, 0.15);
  color: #fb7185;
  border-color: rgba(244, 63, 94, 0.35);
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
  color: #ffffff;
}

.osas-desc {
  font-size: 21rpx;
  color: #d1d5db;
  line-height: 1.5;
}

.osas-btn {
  align-self: flex-start;
  padding: 8rpx 26rpx;
  background: #f59e0b;
  color: #000000;
  font-size: 22rpx;
  font-weight: 800;
  border-radius: 16rpx;
  border: none;
  line-height: 1.6;
}

.osas-btn.outline {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  border: 1rpx solid rgba(255, 255, 255, 0.25);
}

.org-right-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.subclubs-tag-btn {
  padding: 8rpx 18rpx;
  background: rgba(139, 92, 246, 0.15);
  border: 1rpx solid rgba(139, 92, 246, 0.35);
  border-radius: 20rpx;
}

.subclubs-tag-text {
  font-size: 22rpx;
  font-weight: bold;
  color: #c4b5fd;
}

.org-meta-pill-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12rpx;
}

.org-meta-pill {
  font-size: 22rpx;
  color: #d1d5db;
  background: rgba(255, 255, 255, 0.06);
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.org-meta-pill.highlight {
  color: #ff9f0a;
  background: rgba(255, 159, 10, 0.12);
  border-color: rgba(255, 159, 10, 0.3);
  font-weight: bold;
}

.org-meta-pill.gobi-pill {
  color: #34c759;
  background: rgba(52, 199, 89, 0.12);
  border-color: rgba(52, 199, 89, 0.3);
  font-weight: bold;
}

.org-meta-pill.gobi-pill.veteran {
  color: #ff9f0a;
  background: rgba(255, 159, 10, 0.12);
  border-color: rgba(255, 159, 10, 0.3);
  font-weight: bold;
}

/* ── 🏃 自由跑者独立训练模式专属卡片 ── */
.solo-runner-card {
  background: linear-gradient(135deg, rgba(16, 36, 26, 0.95) 0%, rgba(14, 24, 20, 0.95) 100%);
  border: 1rpx solid rgba(52, 199, 89, 0.35);
  border-radius: 28rpx;
  padding: 30rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 30rpx rgba(52, 199, 89, 0.08);
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
  color: #34c759;
  background: rgba(52, 199, 89, 0.12);
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  border: 1rpx solid rgba(52, 199, 89, 0.25);
}

.src-status-pill {
  font-size: 20rpx;
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.08);
  padding: 4rpx 14rpx;
  border-radius: 14rpx;
}

.src-title {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
  margin-bottom: 12rpx;
  display: block;
}

.src-desc {
  font-size: 23rpx;
  color: #a1a1aa;
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
  background: linear-gradient(135deg, #34c759 0%, #30b74e 100%);
  color: #ffffff;
  box-shadow: 0 6rpx 20rpx rgba(52, 199, 89, 0.25);
}

.src-btn.outline {
  background: rgba(255, 255, 255, 0.08);
  color: #e4e4e7;
  border: 1rpx solid rgba(255, 255, 255, 0.15);
}

.org-tag-pill {
  font-size: 20rpx;
  padding: 2rpx 10rpx;
  border-radius: 10rpx;
  background: rgba(255, 159, 10, 0.15);
  color: #ff9f0a;
  border: 1rpx solid rgba(255, 159, 10, 0.3);
  font-weight: bold;
}

.org-tag-pill.free-tag {
  background: rgba(52, 199, 89, 0.12);
  color: #34c759;
  border-color: rgba(52, 199, 89, 0.25);
}

/* ── 🏛️ 未加入大组织提示卡片 ── */
.grand-org-prompt-card {
  background: linear-gradient(135deg, rgba(26, 26, 36, 0.95) 0%, rgba(18, 18, 22, 0.95) 100%);
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  border-radius: 28rpx;
  padding: 30rpx 28rpx;
  margin-bottom: 24rpx;
  box-shadow: 0 10rpx 30rpx rgba(252, 76, 2, 0.1);
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
  color: #fc4c02;
  background: rgba(252, 76, 2, 0.12);
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
  border: 1rpx solid rgba(252, 76, 2, 0.25);
}

.gop-code-pill {
  font-size: 20rpx;
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.06);
  padding: 4rpx 14rpx;
  border-radius: 14rpx;
}

.gop-title {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
  margin-bottom: 12rpx;
  display: block;
}

.gop-desc {
  font-size: 23rpx;
  color: #a1a1aa;
  line-height: 1.6;
  margin-bottom: 24rpx;
  display: block;
}

.gop-join-btn {
  background: linear-gradient(135deg, #fc4c02 0%, #ff6426 100%);
  color: #ffffff;
  font-size: 26rpx;
  font-weight: bold;
  height: 76rpx;
  line-height: 76rpx;
  border-radius: 22rpx;
  border: none;
  box-shadow: 0 6rpx 20rpx rgba(252, 76, 2, 0.35);
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
  color: #9ca3af;
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
  background: #18181c;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 22rpx;
  gap: 20rpx;
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
  color: #ffffff;
}

.sc-city-tag {
  font-size: 20rpx;
  color: #a1a1aa;
}

.sc-desc-line {
  font-size: 21rpx;
  color: #71717a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 6rpx;
  display: block;
}

.sc-meta-line {
  font-size: 20rpx;
  color: #9ca3af;
  display: block;
}

.sc-join-action-btn {
  height: 60rpx;
  line-height: 60rpx;
  padding: 0 28rpx;
  background: #fc4c02;
  color: #ffffff;
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 18rpx;
  border: none;
  flex-shrink: 0;
}

/* ── Modal Form Enhancements ── */
.req-star {
  color: #ef4444;
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
  background: #18181c;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 18rpx;
  color: #a1a1aa;
  font-size: 26rpx;
  font-weight: bold;
  transition: all 0.2s ease;
}

.gender-pill.active {
  background: rgba(252, 76, 2, 0.15);
  border-color: #fc4c02;
  color: #fc4c02;
}

.picker-display-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #18181c;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 18rpx;
  padding: 20rpx 24rpx;
}

.picker-value {
  font-size: 26rpx;
  color: #ffffff;
}

.picker-arrow {
  font-size: 24rpx;
  color: #9ca3af;
}

.field-hint {
  font-size: 20rpx;
  color: #71717a;
  margin-top: 8rpx;
  display: block;
}

.org-submit-btn {
  margin-top: 36rpx;
  background: linear-gradient(135deg, #fc4c02 0%, #ff6426 100%);
  box-shadow: 0 8rpx 24rpx rgba(252, 76, 2, 0.35);
}

.m-class-tag {
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: 10rpx;
  background: rgba(255, 159, 10, 0.15);
  color: #ff9f0a;
  font-weight: bold;
}

.m-gobi-tag {
  font-size: 18rpx;
  font-weight: bold;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(255, 159, 10, 0.15);
  color: #ff9f0a;
  border: 1rpx solid rgba(255, 159, 10, 0.3);
  margin-left: 6rpx;
}

.m-gobi-tag.is-new {
  background: rgba(52, 199, 89, 0.15);
  color: #34c759;
  border-color: rgba(52, 199, 89, 0.3);
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
  background: #18181c;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  color: #a1a1aa;
  font-size: 23rpx;
  font-weight: 500;
  transition: all 0.2s ease;
}

.program-chip.active {
  background: rgba(255, 159, 10, 0.15);
  border-color: #ff9f0a;
  color: #ff9f0a;
  font-weight: bold;
}

.field-preview-tag {
  font-size: 21rpx;
  color: #ff9f0a;
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
  background: #18181c;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  border-radius: 18rpx;
  color: #a1a1aa;
  font-size: 24rpx;
  font-weight: bold;
}

.gobi-type-pill.active {
  background: rgba(252, 76, 2, 0.15);
  border-color: #fc4c02;
  color: #fc4c02;
}

.vet-gobi-box {
  background: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 18rpx;
  padding: 18rpx;
  margin-top: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.vet-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.vet-label {
  font-size: 23rpx;
  color: #d1d5db;
  font-weight: 500;
}

.vet-picker-box {
  display: flex;
  align-items: center;
  gap: 10rpx;
  background: #1c1c22;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  padding: 8rpx 18rpx;
  border-radius: 12rpx;
}

.vpb-value {
  font-size: 24rpx;
  color: #ff9f0a;
  font-weight: bold;
}

.vpb-arrow {
  font-size: 18rpx;
  color: #9ca3af;
}

.group-pills-row {
  display: flex;
  gap: 10rpx;
}

.grp-pill {
  padding: 8rpx 20rpx;
  border-radius: 12rpx;
  background: #1c1c22;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  color: #9ca3af;
  font-size: 22rpx;
  font-weight: bold;
}

.grp-pill.active {
  background: rgba(255, 159, 10, 0.2);
  border-color: #ff9f0a;
  color: #ff9f0a;
}

.vet-summary-row {
  border-top: 1rpx dashed rgba(255, 255, 255, 0.1);
  padding-top: 10rpx;
}

.vet-summary-text {
  font-size: 21rpx;
  color: #9ca3af;
}

.vst-badge {
  color: #ff9f0a;
  font-weight: bold;
}

.m-status-pill {
  font-size: 18rpx;
  padding: 2rpx 10rpx;
  border-radius: 8rpx;
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

.m-status-pill.pending {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.confirmed-label {
  font-size: 22rpx;
  color: #10b981;
  font-weight: bold;
}

.bg-blue {
  background: rgba(14, 165, 233, 0.15);
  color: #0ea5e9;
  border: 1rpx solid rgba(14, 165, 233, 0.3);
}

.bg-green {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
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
  color: #10b981;
  border: 1rpx solid rgba(16, 185, 129, 0.3);
}

.mode-badge-pill.mode-invite {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
  border: 1rpx solid rgba(245, 158, 11, 0.3);
}

.btn-invite-mode {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
  color: #ffffff !important;
}

/* ── Join Mode Setting Modal ── */
.join-mode-modal {
  width: 90%;
  max-width: 660rpx;
  background: #141416;
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  padding: 36rpx;
}

.jm-subtitle {
  font-size: 24rpx;
  color: #9ca3af;
  margin-bottom: 24rpx;
  display: block;
}

.jm-options-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  margin-bottom: 24rpx;
}

.jm-option-card {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
  background: #1c1c20;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 24rpx;
  padding: 24rpx;
  transition: all 0.2s ease;
}

.jm-option-card.is-selected {
  border-color: #fc4c02;
  background: rgba(252, 76, 2, 0.08);
}

.jm-opt-radio {
  font-size: 28rpx;
  margin-top: 4rpx;
}

.jm-radio-dot {
  color: #fc4c02;
}

.jm-radio-circle {
  color: #71717a;
}

.jm-opt-content {
  flex: 1;
}

.jm-opt-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.jm-opt-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #ffffff;
}

.jm-rec-tag {
  font-size: 18rpx;
  font-weight: bold;
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
  border: 1rpx solid rgba(16, 185, 129, 0.4);
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
}

.jm-opt-desc {
  font-size: 22rpx;
  color: #a1a1aa;
  line-height: 1.5;
  display: block;
}

.jm-code-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #18181c;
  border: 1rpx solid rgba(245, 158, 11, 0.3);
  border-radius: 20rpx;
  padding: 20rpx 24rpx;
  margin-bottom: 28rpx;
}

.jm-code-left {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.jm-code-label {
  font-size: 20rpx;
  color: #9ca3af;
}

.jm-code-val {
  font-size: 32rpx;
  font-weight: 900;
  font-family: monospace;
  color: #f59e0b;
  letter-spacing: 4rpx;
}

.jm-copy-btn {
  font-size: 22rpx;
  font-weight: bold;
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
  border: 1rpx solid rgba(245, 158, 11, 0.3);
  border-radius: 14rpx;
  padding: 8rpx 20rpx;
  line-height: 1.4;
  margin: 0;
}

/* ── Club Code Prompt Modal ── */
.club-code-prompt-modal {
  width: 88%;
  max-width: 620rpx;
  background: #141416;
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  padding: 36rpx;
}

.prompt-target-banner {
  display: flex;
  align-items: center;
  gap: 8rpx;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 16rpx;
  padding: 16rpx 20rpx;
  margin-bottom: 16rpx;
}

.ptb-label {
  font-size: 22rpx;
  color: #9ca3af;
}

.ptb-name {
  font-size: 24rpx;
  font-weight: bold;
  color: #ffffff;
}

.prompt-hint-text {
  font-size: 22rpx;
  color: #a1a1aa;
  line-height: 1.5;
  display: block;
  margin-bottom: 24rpx;
}

.club-code-input {
  width: 100%;
  height: 88rpx;
  background: #1c1c20;
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  border-radius: 20rpx;
  color: #ffffff;
  font-size: 36rpx;
  font-weight: bold;
  text-align: center;
  font-family: monospace;
  letter-spacing: 6rpx;
  margin-bottom: 32rpx;
  box-sizing: border-box;
}

.club-code-input:focus {
  border-color: #fc4c02;
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
  color: #10b981;
}

.privacy-badge-tag {
  font-size: 20rpx;
  color: #10b981;
  background: rgba(16, 185, 129, 0.15);
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
  font-family: monospace;
}

.privacy-security-desc {
  font-size: 22rpx;
  color: #d1d5db;
  line-height: 1.6;
}

.label-with-icon-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8rpx;
}

.field-security-pill {
  font-size: 20rpx;
  color: #10b981;
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
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  border-radius: 16rpx;
  width: 80rpx;
  height: 80rpx;
}

/* ── Club Report Modal Styles ── */
.tool-icon-box.bg-gold {
  background-color: rgba(255, 215, 0, 0.2);
}

.mode-badge-pill.mode-report {
  color: #ffd700;
  background: rgba(255, 215, 0, 0.15);
  border: 1rpx solid rgba(255, 215, 0, 0.4);
}

.count-pill.report-owner-pill {
  color: #ffd700;
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
  color: #9ca3af;
  background: #1c1c1e;
  border-radius: 12rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.report-sub-tab.active {
  color: #ffd700;
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
  color: #9ca3af;
}

.report-scroll-body {
  max-height: 56vh;
  padding-right: 4rpx;
}

.report-period-banner {
  background: linear-gradient(135deg, rgba(255, 215, 0, 0.12) 0%, rgba(252, 76, 2, 0.08) 100%);
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
  color: #ffffff;
}

.rpb-dates {
  font-size: 20rpx;
  color: #ffd700;
}

.report-metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14rpx;
  margin-bottom: 20rpx;
}

.rmg-card {
  background: #18181b;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 14rpx;
  padding: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.rmg-label {
  font-size: 20rpx;
  color: #9ca3af;
}

.rmg-val-row {
  display: flex;
  align-items: baseline;
  gap: 6rpx;
}

.rmg-val {
  font-size: 32rpx;
  font-weight: 900;
  color: #ffffff;
}

.rmg-val.highlight {
  color: #fc4c02;
}

.rmg-unit {
  font-size: 20rpx;
  color: #71717a;
}

.report-section-box {
  background: #18181b;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 16rpx;
  padding: 18rpx;
  margin-bottom: 20rpx;
}

.rsb-title {
  font-size: 24rpx;
  font-weight: bold;
  color: #ffd700;
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
  background: #202024;
  border-radius: 12rpx;
  padding: 12rpx 16rpx;
  border-left: 6rpx solid #71717a;
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
  border-left-color: #cd7f32;
  background: rgba(205, 127, 50, 0.06);
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
  color: #ffffff;
}

.podium-sub {
  font-size: 18rpx;
  color: #9ca3af;
}

.podium-right {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.podium-km {
  font-size: 28rpx;
  font-weight: 800;
  color: #ffffff;
}

.podium-km-unit {
  font-size: 18rpx;
  color: #71717a;
}

.empty-podium-text {
  font-size: 20rpx;
  color: #71717a;
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
  background: #18181b;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 14rpx;
  padding: 14rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.hc-tag {
  font-size: 18rpx;
  color: #38bdf8;
  font-weight: bold;
}

.hc-name {
  font-size: 22rpx;
  font-weight: bold;
  color: #ffffff;
}

.hc-detail {
  font-size: 18rpx;
  color: #9ca3af;
}

.canova-box {
  border-color: rgba(191, 90, 242, 0.3);
  background: linear-gradient(135deg, rgba(191, 90, 242, 0.06) 0%, #18181b 100%);
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
  color: #bf5af2;
}

.canova-critique-text {
  font-size: 20rpx;
  color: #d1d5db;
  line-height: 1.6;
}

.forward-box {
  border-color: rgba(34, 197, 94, 0.3);
  background: #121214;
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
  color: #22c55e;
}

.forward-hint {
  font-size: 18rpx;
  color: #71717a;
}

.forward-preview-card {
  background: #0a0a0c;
  border-radius: 12rpx;
  padding: 16rpx;
  border: 1rpx dashed rgba(255, 255, 255, 0.15);
}

.forward-preview-text {
  font-size: 20rpx;
  color: #e4e4e7;
  line-height: 1.6;
  white-space: pre-wrap;
  font-family: monospace;
}

.report-footer-actions {
  display: flex;
  gap: 12rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
}

.btn-copy-forward {
  flex: 1.8;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: #ffffff;
  font-size: 24rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: none;
  line-height: 1.4;
}

.btn-download-report {
  flex: 1;
  background: #27272a;
  color: #e4e4e7;
  font-size: 22rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  line-height: 1.4;
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
  color: #9ca3af;
  background: #18181c;
  border-radius: 12rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
}

.report-view-tab.active {
  color: #000000;
  background: linear-gradient(135deg, #ffd700 0%, #f59e0b 100%);
  border-color: #f59e0b;
  box-shadow: 0 4rpx 14rpx rgba(245, 158, 11, 0.25);
}

.poster-card-wrapper {
  padding: 8rpx 0 20rpx 0;
}

.report-poster-card {
  background: linear-gradient(180deg, #11141d 0%, #151824 50%, #0c0d14 100%);
  border: 2rpx solid rgba(255, 215, 0, 0.35);
  border-radius: 28rpx;
  padding: 30rpx 26rpx;
  box-shadow: 0 12rpx 36rpx rgba(0, 0, 0, 0.6), inset 0 0 40rpx rgba(255, 215, 0, 0.04);
}

.poster-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
  padding-bottom: 18rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.1);
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
  color: #ffffff;
}

.poster-tagline {
  font-size: 18rpx;
  color: #ffd700;
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
  color: #ffffff;
}

.poster-period-date {
  font-size: 18rpx;
  color: #9ca3af;
  font-family: monospace;
}

/* Hero Mileage */
.poster-hero-mileage {
  background: linear-gradient(135deg, rgba(252, 76, 2, 0.15) 0%, rgba(245, 158, 11, 0.08) 100%);
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  border-radius: 22rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  text-align: center;
}

.phm-label {
  font-size: 20rpx;
  color: #9ca3af;
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
  color: #fc4c02;
  line-height: 1;
  font-family: monospace;
}

.phm-unit {
  font-size: 32rpx;
  font-weight: 900;
  color: #f59e0b;
}

.phm-sub {
  font-size: 18rpx;
  color: #71717a;
}

/* 4-Metrics Bar */
.poster-grid-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12rpx;
  margin-bottom: 20rpx;
}

.pg-item {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.07);
  border-radius: 16rpx;
  padding: 16rpx;
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.pg-label {
  font-size: 18rpx;
  color: #9ca3af;
}

.pg-val {
  font-size: 28rpx;
  font-weight: 900;
  color: #ffffff;
}

.pg-sub {
  font-size: 16rpx;
  color: #71717a;
}

/* Podium Cards */
.poster-podium-box {
  background: rgba(255, 255, 255, 0.03);
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
  color: #ffd700;
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
  border: 1rpx solid rgba(255, 255, 255, 0.08);
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
  background: rgba(205, 127, 50, 0.06);
  border-color: rgba(205, 127, 50, 0.3);
}

.ppc-rank-badge {
  font-size: 20rpx;
  font-weight: 900;
  min-width: 80rpx;
  color: #ffd700;
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
  color: #ffffff;
}

.ppc-detail {
  font-size: 16rpx;
  color: #9ca3af;
}

.ppc-km-col {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.ppc-km {
  font-size: 26rpx;
  font-weight: 900;
  color: #fc4c02;
  font-family: monospace;
}

.ppc-km-u {
  font-size: 16rpx;
  color: #71717a;
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
  color: #38bdf8;
  font-weight: bold;
}

.phb-name {
  font-size: 20rpx;
  font-weight: bold;
  color: #ffffff;
}

.phb-sub {
  font-size: 16rpx;
  color: #9ca3af;
}

/* Canova Quote */
.poster-canova-quote {
  background: linear-gradient(135deg, rgba(191, 90, 242, 0.1) 0%, rgba(191, 90, 242, 0.03) 100%);
  border: 1rpx solid rgba(191, 90, 242, 0.35);
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
  color: #bf5af2;
}

.pcq-text {
  font-size: 18rpx;
  color: #d1d5db;
  line-height: 1.6;
  font-style: italic;
}

/* Bottom Stamp */
.poster-footer-stamp {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.1);
}

.pfs-left {
  display: flex;
  flex-direction: column;
}

.pfs-brand {
  font-size: 18rpx;
  font-weight: 900;
  color: #ffffff;
  letter-spacing: 2rpx;
}

.pfs-slogan {
  font-size: 14rpx;
  color: #71717a;
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
  color: #ffd700;
  letter-spacing: 2rpx;
}

/* Buttons in Poster View */
.btn-preview-poster {
  flex: 1.5;
  background: linear-gradient(135deg, #ffd700 0%, #f59e0b 100%);
  color: #000000;
  font-size: 24rpx;
  font-weight: 900;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: none;
  line-height: 1.4;
  box-shadow: 0 4rpx 14rpx rgba(245, 158, 11, 0.3);
}

.btn-save-album {
  flex: 1.3;
  background: #16a34a;
  color: #ffffff;
  font-size: 22rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: none;
  line-height: 1.4;
}

.btn-sub-copy {
  flex: 1;
  background: #27272a;
  color: #e4e4e7;
  font-size: 20rpx;
  font-weight: bold;
  border-radius: 16rpx;
  padding: 16rpx 0;
  text-align: center;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  line-height: 1.4;
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
  color: #f87171;
  display: block;
  margin-bottom: 16rpx;
}

.csb-desc {
  font-size: 24rpx;
  color: #e5e7eb;
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
  color: #ffffff;
  box-shadow: 0 6rpx 20rpx rgba(239, 68, 68, 0.3);
}

.csb-btn.secondary {
  background: rgba(255, 255, 255, 0.08);
  color: #e5e7eb;
  border: 1rpx solid rgba(255, 255, 255, 0.15);
}
</style>
