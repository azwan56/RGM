<template>
  <view class="sub-page" :class="themeClass">
    <PrivacyPopup />

    <!-- Mode 4: Studio (Club Showcase OR Coach Resume + 9-Photo wx.chooseMedia Upload) -->
    <template v-if="viewMode === 'studio' || viewMode === 'coach_studio'">
      <view class="sub-header">
        <text class="sub-title">
          {{ viewMode === 'coach_studio' ? '🏅 编辑我的教练资历与相册' : '🎨 装修跑团品牌主页与相册' }}
        </text>
        <text class="sub-sub">合练结束即可手机相册 1 次选 9 张大片上传，挂载至微信定向特邀卡</text>
      </view>

      <view class="rgm-card form-card">
        <template v-if="viewMode === 'studio'">
          <text class="lbl">品牌 Slogan / 核心宣言</text>
          <input v-model="clubSlogan" class="inp" placeholder="例如：张江科学长跑 · 严肃破330特训" />
          <text class="lbl">合练地标（逗号分隔）</text>
          <input v-model="clubLandmarks" class="inp" placeholder="世纪公园、徐汇滨江" />
          <text class="lbl">固定合练排期</text>
          <input v-model="clubSchedule" class="inp" placeholder="周六 06:00 世纪公园 7 号门 A/B/C 三组领跑" />
        </template>
        <template v-else>
          <text class="lbl">个人头衔标语</text>
          <input v-model="coachHeadline" class="inp" placeholder="上马破三教练 · AHA急救官" />
          <text class="lbl">专业资质证书（逗号分隔）</text>
          <input v-model="coachCerts" class="inp" placeholder="中国田协教练证、AHA急救证" />
          <text class="lbl">执教履历简介</text>
          <textarea v-model="coachStory" class="tarea" placeholder="讲述您的科学带训经验（手表核验PB与官兔次数由系统防伪生成）" />
        </template>
        <button class="primary-btn" :disabled="saving" @click="saveStudioProfile">
          {{ saving ? '发布中...' : '保存并发布主页' }}
        </button>
      </view>

      <view class="rgm-card form-card">
        <view class="row-between">
          <text class="sec-title">📸 照片墙 ({{" "}}{{ studioPhotos.length }}/36)</text>
          <picker :range="catLabels" @change="onPickCategory">
            <text class="cat-pill">{{ catLabels[catIdx] }} ▾</text>
          </picker>
        </view>
        <input v-model="photoCaption" class="inp" style="margin-top: 14rpx;" placeholder="选填照片说明（如 世纪公园30km拉练）" />
        <button class="upload-btn" :disabled="uploading" @click="uploadPhotosMobile">
          {{ uploading ? '正在压缩上传...' : '📱 从手机相册批量选图上墙（最多9张）' }}
        </button>

        <view class="photo-grid">
          <view v-for="p in studioPhotos" :key="p.id" class="photo-tile">
            <image :src="resolveAssetUrl(p.photo_url)" class="tile-img" mode="aspectFill" @click="previewPhoto(p.photo_url)" />
            <text v-if="p.is_cover" class="cover-badge">封面</text>
            <text class="del-badge" @click.stop="deletePhoto(p.id)">删</text>
          </view>
        </view>
      </view>
    </template>

    <!-- Mode 2: Club Brand Detail -->
    <template v-else-if="clubDetail">
      <view class="back-row" @click="handleBackFromClub">
        {{ returnCoachUid ? '‹ 返回教练展示页' : '‹ 返回展厅列表' }}
      </view>
      <view class="rgm-card hero-card">
        <image
          v-if="clubDetail.showcase?.hero_cover_url"
          :src="resolveAssetUrl(clubDetail.showcase.hero_cover_url)"
          class="hero-cover"
          mode="aspectFill"
        />
        <view class="hero-body">
          <view class="hero-title-row">
            <text class="hero-name">{{ clubDetail.club?.name }}</text>
            <text v-if="clubDetail.viewer_membership?.status === 'active'" class="member-pill">✓ 已加入</text>
          </view>
          <view class="meta-badge-row">
            <text class="scope-pill" :class="isOrgClub(clubDetail.club) ? 'is-org' : 'is-free'">
              {{ formatOrgBadge(clubDetail.club) }}
            </text>
            <text class="status-pill" :class="'is-' + getClubStatusBadge(clubDetail.club).tone">
              {{ getClubStatusBadge(clubDetail.club).text }}
            </text>
            <text v-if="clubDetail.club?.city" class="city-pill">📍 {{ clubDetail.club.city }}</text>
          </view>
          <text v-if="clubDetail.showcase?.slogan" class="hero-slogan">{{ clubDetail.showcase?.slogan }}</text>
          <view class="stat-grid">
            <view class="stat-box">
              <text class="stat-v">{{ clubDetail.verified_stats?.member_count ?? 0 }}人</text>
              <text class="stat-l">活跃队员</text>
            </view>
            <view class="stat-box">
              <text class="stat-v">{{ clubDetail.verified_stats?.sub330_count ?? 0 }}人</text>
              <text class="stat-l">⌚核验破330</text>
            </view>
            <view class="stat-box">
              <text class="stat-v">{{ clubDetail.verified_stats?.month_total_km ?? 0 }}k</text>
              <text class="stat-l">本月全团跑量</text>
            </view>
          </view>
          <text v-if="clubDetail.showcase?.schedule_summary" class="sched-txt">
            🗓️ {{ clubDetail.showcase.schedule_summary }}
          </text>
          <view class="hero-actions-col">
            <button
              v-if="clubDetail.viewer_membership?.status === 'active'"
              class="joined-enter-btn"
              @click="enterClubHome(clubDetail.club.id)"
            >
              ✓ 已加入本跑团 · 进入跑团主页 ›
            </button>
            <button
              v-else-if="isClubJoinDisabled(clubDetail.club)"
              class="disabled-join-btn"
              disabled
            >
              {{ getClubStatusBadge(clubDetail.club).text }} · 暂不开放加入
            </button>
            <button
              v-else
              class="primary-btn hero-join-btn"
              :loading="joiningClubId === clubDetail.club?.id"
              @click="handleJoinClubClick({ ...clubDetail.club, is_member: false })"
            >
              {{ clubDetail.club?.join_mode === 'invite' ? '🔑 凭邀请码加入跑团' : '+ 加入跑团（支持多团兼入）' }}
            </button>
            <button v-if="clubDetail.can_edit" class="sec-btn" @click="openClubStudio(clubDetail.club.id)">
              🎨 装修主页与相册传图
            </button>
          </view>
        </view>
      </view>

      <!-- Coaching Roster -->
      <view v-if="(clubDetail.coaching_team || []).length" class="rgm-card sec-card">
        <text class="sec-title">🎖️ 团长与教练天团</text>
        <view v-for="ch in clubDetail.coaching_team" :key="ch.user_id" class="coach-row" @click="openCoachDetail(ch.user_id)">
          <view class="coach-left">
            <text class="coach-name">{{ ch.display_name }}</text>
            <text class="coach-hl">{{ ch.headline }}</text>
          </view>
          <text class="coach-pb">{{ ch.verified_marathon_pb ? `PB ${ch.verified_marathon_pb}` : '查看资历 ›' }}</text>
        </view>
      </view>

      <!-- Photo Wall -->
      <view class="rgm-card sec-card">
        <text class="sec-title">📸 实拍风采照片墙 ({{ (clubDetail.photos || []).length }})</text>
        <view class="photo-grid">
          <view v-for="p in clubDetail.photos || []" :key="p.id" class="photo-tile">
            <image :src="resolveAssetUrl(p.photo_url)" class="tile-img" mode="aspectFill" @click="previewPhoto(p.photo_url)" />
          </view>
        </view>
      </view>
    </template>

    <!-- Mode 3: Coach Verified Resume Detail -->
    <template v-else-if="coachDetail">
      <view class="back-row" @click="handleBackFromCoach">‹ 返回</view>
      <view class="rgm-card sec-card">
        <view class="row-between">
          <view class="coach-head-col">
            <text class="hero-name">{{ coachDetail.coach_profile?.display_name }}</text>
            <text class="hero-slogan">{{ coachDetail.resume?.headline }}</text>
          </view>
          <text v-if="coachDetail.verified_achievements?.watch_verified" class="verify-pill">⌚ 手表核验</text>
        </view>
        <view class="stat-grid">
          <view class="stat-box">
            <text class="stat-v">{{ coachDetail.verified_achievements?.verified_pbs?.marathon_pb || '--' }}</text>
            <text class="stat-l">核验全马PB</text>
          </view>
          <view class="stat-box">
            <text class="stat-v">{{ coachDetail.verified_achievements?.official_pacer_count ?? 0 }} 场</text>
            <text class="stat-l">🐰 官兔履历</text>
          </view>
          <view class="stat-box">
            <text class="stat-v">{{ coachDetail.coaching_impact?.total_coached_runners ?? 0 }}人</text>
            <text class="stat-l">带训学员</text>
          </view>
        </view>
        <text v-if="coachDetail.resume?.bio_story" class="coach-bio-txt">{{ coachDetail.resume.bio_story }}</text>
        <button v-if="coachDetail.can_edit" class="primary-btn" style="margin-top: 18rpx;" @click="openCoachStudio(coachDetail.coach_profile.user_id)">
          🎨 编辑我的资历与传照
        </button>
      </view>

      <!-- Coached Clubs Roster (all currently coached clubs with 大群/自由团/状态 + quick join) -->
      <view class="rgm-card sec-card">
        <view class="row-between" style="margin-bottom: 14rpx;">
          <text class="sec-title" style="margin-bottom: 0;">
            🏛️ 当前执教跑团 ({{ (coachDetail.coaching_impact?.coached_clubs || []).length }})
          </text>
          <text class="sec-sub-hint">点击看跑团主页</text>
        </view>
        <view v-if="!(coachDetail.coaching_impact?.coached_clubs || []).length" class="empty-inline-txt">
          暂无当前可见执教跑团
        </view>
        <view
          v-for="cl in coachDetail.coaching_impact?.coached_clubs || []"
          :key="cl.id"
          class="coached-club-item"
          @click="openClubDetailFromCoach(cl.id)"
        >
          <view class="coached-club-main">
            <view class="coached-club-name-row">
              <text class="coached-club-name">{{ cl.name }}</text>
              <text class="role-pill">{{ cl.role === 'owner' ? '团长' : '教练' }}</text>
            </view>
            <view class="meta-badge-row compact">
              <text class="scope-pill" :class="isOrgClub(cl) ? 'is-org' : 'is-free'">
                {{ formatOrgBadge(cl) }}
              </text>
              <text class="status-pill" :class="'is-' + getClubStatusBadge(cl).tone">
                {{ getClubStatusBadge(cl).text }}
              </text>
              <text v-if="cl.is_member" class="member-pill">✓ 已加入</text>
            </view>
            <text class="coached-club-sub">
              {{ cl.city || '同城' }} · {{ cl.member_cnt ?? 0 }} 位队员
            </text>
          </view>
          <view class="coached-club-right" @click.stop>
            <button
              class="mini-join-btn"
              :class="{
                'is-joined': cl.is_member,
                'is-invite': !cl.is_member && !isClubJoinDisabled(cl) && cl.join_mode === 'invite',
                'is-disabled': !cl.is_member && isClubJoinDisabled(cl),
              }"
              :loading="joiningClubId === cl.id"
              :disabled="!cl.is_member && isClubJoinDisabled(cl)"
              @click.stop="handleJoinClubClick(cl)"
            >
              {{ getClubJoinActionLabel(cl, !!cl.is_member) }}
            </button>
          </view>
        </view>
      </view>

      <view class="rgm-card sec-card">
        <text class="sec-title">📸 执教风采与证书墙 ({{ (coachDetail.photos || []).length }})</text>
        <view class="photo-grid">
          <view v-for="p in coachDetail.photos || []" :key="p.id" class="photo-tile">
            <image :src="resolveAssetUrl(p.photo_url)" class="tile-img" mode="aspectFill" @click="previewPhoto(p.photo_url)" />
          </view>
        </view>
      </view>
    </template>

    <!-- Mode 1: Showcase Plaza List -->
    <template v-else>
      <view class="sub-header">
        <text class="sub-title">🏛️ 选团与名帅风采展厅</text>
        <text class="sub-sub">先看合练实拍与手表防伪战绩，支持无排他多团兼入</text>
      </view>

      <view class="rgm-seg-bar">
        <view class="rgm-seg-item" :class="{ active: plazaTab === 'clubs' }" @click="plazaTab = 'clubs'">🏛️ 跑团展厅</view>
        <view class="rgm-seg-item" :class="{ active: plazaTab === 'coaches' }" @click="plazaTab = 'coaches'">🎖️ 认证教练</view>
      </view>

      <view v-if="plazaTab === 'clubs'">
        <view v-for="c in plazaClubs" :key="c.club_id" class="rgm-card plaza-card" @click="openClubDetail(c.club_id)">
          <image v-if="c.hero_cover_url" :src="resolveAssetUrl(c.hero_cover_url)" class="plaza-cover" mode="aspectFill" />
          <view class="plaza-body">
            <view class="row-between">
              <view class="plaza-title-wrap">
                <text class="plaza-name">{{ c.name }}</text>
                <text v-if="c.is_decorated" class="deco-pill">✨ 已装修</text>
              </view>
              <text class="plaza-badge" :class="{ muted: !c.photo_count }">📸 {{ c.photo_count }}张</text>
            </view>
            <view class="meta-badge-row compact">
              <text class="scope-pill" :class="isOrgClub(c) ? 'is-org' : 'is-free'">
                {{ formatOrgBadge(c) }}
              </text>
              <text class="status-pill" :class="'is-' + getClubStatusBadge(c).tone">
                {{ getClubStatusBadge(c).text }}
              </text>
              <text v-if="c.city" class="city-pill">📍 {{ c.city }}</text>
              <text v-if="c.is_member" class="member-pill">✓ 已加入</text>
            </view>
            <text class="plaza-slogan">{{ c.slogan }}</text>
            <view class="plaza-foot-row">
              <text class="plaza-stats">
                {{ c.verified_stats?.member_count ?? 0 }}人 · 近30天 {{ c.verified_stats?.recent_30d_checkins ?? 0 }}次打卡{{ (c.verified_stats?.recent_30d_events ?? 0) > 0 ? ` · ${c.verified_stats.recent_30d_events}场活动` : '' }}
              </text>
              <button
                class="mini-join-btn"
                :class="{
                  'is-joined': c.is_member,
                  'is-invite': !c.is_member && !isClubJoinDisabled(c) && c.join_mode === 'invite',
                  'is-disabled': !c.is_member && isClubJoinDisabled(c),
                }"
                :loading="joiningClubId === c.club_id"
                :disabled="!c.is_member && isClubJoinDisabled(c)"
                @click.stop="handleJoinClubClick(c)"
              >
                {{ getClubJoinActionLabel(c, !!c.is_member) }}
              </button>
            </view>
          </view>
        </view>
      </view>

      <view v-else>
        <view v-for="ch in plazaCoaches" :key="ch.user_id" class="rgm-card sec-card" @click="openCoachDetail(ch.user_id)">
          <view class="row-between">
            <view class="plaza-title-wrap">
              <text class="plaza-name">{{ ch.display_name }}</text>
              <text v-if="ch.is_decorated" class="deco-pill">✨ 已装修</text>
            </view>
            <text v-if="ch.watch_verified" class="verify-pill">⌚ 手表核验</text>
          </view>
          <text class="plaza-slogan">{{ ch.headline }}</text>
          <text class="plaza-stats">
            全马PB {{ ch.verified_marathon_pb || '教练认证' }} · 执教 {{ ch.coached_clubs_count || 1 }} 个跑团 · 近30天打卡 {{ ch.recent_30d_checkins ?? 0 }}次 ›
          </text>
        </view>
      </view>
    </template>

    <!-- Join Club Modal (Invite Code & Mandatory Real WeChat Nickname Gate) -->
    <view v-if="joinModalClub" class="modal-mask" @click="closeJoinModal" @touchmove.stop.prevent>
      <view class="modal-box" @click.stop>
        <view class="row-between" style="margin-bottom: 12rpx;">
          <text class="modal-title">加入【{{ joinModalClub.name }}】</text>
          <text class="modal-close" @click="closeJoinModal">✕</text>
        </view>
        <view class="meta-badge-row compact" style="margin-bottom: 18rpx;">
          <text class="scope-pill" :class="isOrgClub(joinModalClub) ? 'is-org' : 'is-free'">
            {{ formatOrgBadge(joinModalClub) }}
          </text>
          <text class="status-pill" :class="'is-' + getClubStatusBadge(joinModalClub).tone">
            {{ getClubStatusBadge(joinModalClub).text }}
          </text>
        </view>

        <form @submit="submitJoinClubModal">
          <view v-if="joinModalNeedsNick" class="join-nick-card" :class="{ 'has-err': !!joinNickError }">
            <text class="lbl" style="margin-top: 0;">请先选用您的微信昵称 *（告别「跑者_xxxx」）</text>
            <input
              type="nickname"
              name="nickname"
              class="inp"
              v-model="joinNicknameInput"
              :focus="joinNickFocus"
              placeholder="点这里 → 键盘上方一键选微信昵称"
              @input="onJoinNickChange"
              @change="onJoinNickChange"
              @blur="onJoinNickChange"
            />
            <text v-if="joinNickError" class="err-hint">⚠️ {{ joinNickError }}</text>
          </view>

          <view v-if="joinModalClub.join_mode === 'invite'" style="margin-top: 14rpx;">
            <text class="lbl" style="margin-top: 0;">跑团专属邀请码 *</text>
            <input
              name="invite_code"
              class="inp"
              v-model="joinCodeInput"
              placeholder="请输入团长分享的邀请码"
            />
          </view>

          <view class="modal-btn-row">
            <button class="sec-btn modal-half-btn" @click="closeJoinModal">取消</button>
            <button
              class="primary-btn modal-half-btn"
              style="margin-top: 0;"
              form-type="submit"
              :loading="joiningClubId === joinModalClub.id"
            >
              确认加入
            </button>
          </view>
        </form>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, nextTick } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import PrivacyPopup from "../../components/PrivacyPopup.vue";
import {
  chooseAndUploadShowcasePhotos,
  getStoredUser,
  getToken,
  request,
  resolveAssetUrl,
  setActiveClubId,
  setSession,
  wechatLogin,
} from "../../utils/api";

const viewMode = ref<"plaza" | "studio" | "coach_studio">("plaza");
const plazaTab = ref<"clubs" | "coaches">("clubs");
const plazaClubs = ref<any[]>([]);
const plazaCoaches = ref<any[]>([]);
const clubDetail = ref<any>(null);
const coachDetail = ref<any>(null);
const returnCoachUid = ref<string>("");

// Join club state (supports free direct join, invite-code join, and mandatory real nickname gate)
const joiningClubId = ref<string | null>(null);
const joinModalClub = ref<any>(null);
const joinModalNeedsNick = ref(false);
const joinNicknameInput = ref("");
const joinCodeInput = ref("");
const joinNickError = ref("");
const joinNickFocus = ref(false);

// Studio edit state
const targetOwnerId = ref("");
const studioPhotos = ref<any[]>([]);
const clubSlogan = ref("");
const clubLandmarks = ref("");
const clubSchedule = ref("");
const coachHeadline = ref("");
const coachCerts = ref("");
const coachStory = ref("");
const saving = ref(false);
const uploading = ref(false);
const catIdx = ref(0);
const catKeys = ["group_run", "race_highlight", "certificate", "team_event"];
const catLabels = ["合练实拍", "赛场高光", "证书奖项", "补给团建"];
const photoCaption = ref("");

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

function isOrgClub(club: any): boolean {
  return Boolean(club?.org_id || club?.is_org_club || String(club?.org_name || "").trim());
}

function formatOrgBadge(club: any): string {
  const orgName = String(club?.org_name || "").trim();
  if (isOrgClub(club)) {
    if (!orgName) return "🏛️ 大群分团";
    return orgName.endsWith("大群") ? `🏛️ ${orgName}` : `🏛️ ${orgName}大群`;
  }
  return "自由团";
}

function getClubStatusBadge(club: any): { text: string; tone: "free" | "invite" | "paused" | "locked" } {
  const st = String(club?.status || "active").toLowerCase();
  if (st === "locked") return { text: "🔒 已锁定", tone: "locked" };
  if (st === "paused") return { text: "⏸️ 已暂停", tone: "paused" };
  if (String(club?.join_mode || "free").toLowerCase() === "invite") {
    return { text: "🔑 需邀请码", tone: "invite" };
  }
  return { text: "🟢 自由入团", tone: "free" };
}

function isClubJoinDisabled(club: any): boolean {
  const st = String(club?.status || "active").toLowerCase();
  return st === "locked" || st === "paused";
}

function getClubJoinActionLabel(club: any, isMember: boolean): string {
  if (isMember) return "已加入 ›";
  const st = String(club?.status || "active").toLowerCase();
  if (st === "locked") return "已锁定";
  if (st === "paused") return "已暂停";
  if (String(club?.join_mode || "free").toLowerCase() === "invite") return "凭码加入";
  return "+ 加入";
}

onShow(() => {
  applySystemTheme(currentTheme.value);
});

onLoad(async (opts?: any) => {
  let u = getStoredUser();
  if (!u) u = await wechatLogin();
  if (opts?.mode === "studio" && opts?.club_id) {
    await openClubStudio(opts.club_id);
  } else if (opts?.mode === "coach_studio") {
    await openCoachStudio(opts.coach_uid || u?.id || "");
  } else if (opts?.club_id) {
    await openClubDetail(opts.club_id);
  } else if (opts?.coach_uid) {
    await openCoachDetail(opts.coach_uid);
  } else {
    if (opts?.tab === "coaches") plazaTab.value = "coaches";
    await loadPlaza();
  }
});

async function loadPlaza() {
  viewMode.value = "plaza";
  const u = getStoredUser();
  const q = u?.id ? `?viewer_uid=${encodeURIComponent(u.id)}` : "";
  const res: any = await request(`/api/community/showcase/plaza${q}`);
  plazaClubs.value = res?.clubs || [];
  plazaCoaches.value = res?.coaches || [];
}

async function openClubDetail(cid: string) {
  returnCoachUid.value = "";
  const u = getStoredUser();
  const q = u?.id ? `?viewer_uid=${encodeURIComponent(u.id)}` : "";
  clubDetail.value = await request(`/api/community/showcase/clubs/${encodeURIComponent(cid)}${q}`);
  coachDetail.value = null;
}

async function openClubDetailFromCoach(cid: string) {
  const prevCoachUid = String(coachDetail.value?.coach_profile?.user_id || "").trim();
  const u = getStoredUser();
  const q = u?.id ? `?viewer_uid=${encodeURIComponent(u.id)}` : "";
  try {
    clubDetail.value = await request(`/api/community/showcase/clubs/${encodeURIComponent(cid)}${q}`);
    returnCoachUid.value = prevCoachUid;
    coachDetail.value = null;
  } catch (e: any) {
    uni.showToast({ title: e?.message || "无法查看该跑团宣传页", icon: "none" });
  }
}

async function handleBackFromClub() {
  const backCoach = returnCoachUid.value;
  clubDetail.value = null;
  returnCoachUid.value = "";
  if (backCoach) {
    await openCoachDetail(backCoach);
  } else if (plazaClubs.value.length === 0) {
    await loadPlaza();
  }
}

async function handleBackFromCoach() {
  coachDetail.value = null;
  if (plazaClubs.value.length === 0 && plazaCoaches.value.length === 0) {
    await loadPlaza();
  }
}

async function openCoachDetail(cuid: string) {
  const u = getStoredUser();
  const q = u?.id ? `?viewer_uid=${encodeURIComponent(u.id)}` : "";
  coachDetail.value = await request(`/api/community/showcase/coaches/${encodeURIComponent(cuid)}${q}`);
  clubDetail.value = null;
}

function enterClubHome(clubId: string) {
  if (!clubId) return;
  setActiveClubId(clubId);
  uni.switchTab({ url: "/pages/team/team" });
}

function triggerJoinNickFocus(errMsg?: string) {
  if (errMsg) joinNickError.value = errMsg;
  joinNickFocus.value = false;
  nextTick(() => {
    setTimeout(() => {
      joinNickFocus.value = true;
    }, 60);
  });
}

function onJoinNickChange(e: any) {
  const v = String(e?.detail?.value ?? "").trim();
  if (v) {
    joinNicknameInput.value = v;
    if (!isGenericRunnerName(v)) joinNickError.value = "";
  }
}

function closeJoinModal() {
  joinModalClub.value = null;
  joinCodeInput.value = "";
  joinNickError.value = "";
  joinNickFocus.value = false;
}

async function handleJoinClubClick(rawClub: any) {
  const clubId = String(rawClub?.club_id || rawClub?.id || "").trim();
  if (!clubId) return;
  if (rawClub?.is_member) {
    enterClubHome(clubId);
    return;
  }
  const st = String(rawClub?.status || "active").toLowerCase();
  if (st === "locked") {
    uni.showToast({ title: "该跑团已锁定，暂不开放加入", icon: "none" });
    return;
  }
  if (st === "paused") {
    uni.showToast({ title: "该跑团已暂停招募", icon: "none" });
    return;
  }

  let u = getStoredUser();
  if (!u?.id) {
    u = await wechatLogin();
  }
  if (!u?.id) {
    uni.showToast({ title: "请先登录后加入跑团", icon: "none" });
    return;
  }

  const needsNick = isGenericRunnerName(u.display_name);
  const joinMode = String(rawClub?.join_mode || "free").toLowerCase();
  if (joinMode === "invite" || needsNick) {
    joinModalClub.value = {
      id: clubId,
      name: rawClub?.name || "跑团",
      org_id: rawClub?.org_id || null,
      org_name: rawClub?.org_name || "",
      is_org_club: isOrgClub(rawClub),
      join_mode: joinMode,
      status: st,
    };
    joinModalNeedsNick.value = needsNick;
    joinNicknameInput.value = needsNick ? "" : String(u.display_name || "");
    joinCodeInput.value = "";
    joinNickError.value = "";
    if (needsNick) triggerJoinNickFocus();
    return;
  }

  await executeJoinClub(clubId);
}

async function submitJoinClubModal(e?: any) {
  if (!joinModalClub.value?.id) return;
  const formNick = String(e?.detail?.value?.nickname ?? "").trim();
  const finalNick = formNick || joinNicknameInput.value.trim();
  if (formNick) joinNicknameInput.value = formNick;

  if (joinModalNeedsNick.value && isGenericRunnerName(finalNick)) {
    triggerJoinNickFocus("请先点击上方昵称框，一键选用您的微信昵称（不能为默认代号）");
    uni.showToast({ title: "请先点击昵称框选用微信昵称", icon: "none" });
    return;
  }

  const formCode = String(e?.detail?.value?.invite_code ?? "").trim();
  if (formCode) joinCodeInput.value = formCode;
  const code = joinCodeInput.value.trim().toUpperCase();
  if (joinModalClub.value.join_mode === "invite" && !code) {
    uni.showToast({ title: "请输入跑团专属邀请码", icon: "none" });
    return;
  }

  const ok = await executeJoinClub(
    joinModalClub.value.id,
    code || undefined,
    joinModalNeedsNick.value ? finalNick : undefined
  );
  if (ok) {
    closeJoinModal();
  }
}

async function executeJoinClub(clubId: string, inviteCode?: string, displayName?: string): Promise<boolean> {
  let u = getStoredUser();
  if (!u?.id) u = await wechatLogin();
  if (!u?.id) {
    uni.showToast({ title: "登录中，请稍后重试", icon: "none" });
    return false;
  }
  joiningClubId.value = clubId;
  try {
    const payload: any = {
      user_id: u.id,
      club_id: clubId,
      privacy_consent: true,
    };
    if (inviteCode) payload.invite_code = inviteCode;
    if (displayName && !isGenericRunnerName(displayName)) {
      payload.display_name = displayName;
    }
    const res: any = await request("/api/team/join-club", "POST", payload);
    const updatedName = String(res?.user?.display_name || displayName || "").trim();
    if (updatedName && !isGenericRunnerName(updatedName)) {
      setSession(getToken(), { ...u, display_name: updatedName });
    }
    setActiveClubId(clubId);
    try {
      uni.setStorageSync("rgm_dashboard_dirty", "1");
    } catch (_) {}

    // Optimistically update local lists & refresh active view
    plazaClubs.value = plazaClubs.value.map((c) =>
      c.club_id === clubId ? { ...c, is_member: true } : c
    );
    if (clubDetail.value?.club?.id === clubId) {
      const savedBackCoach = returnCoachUid.value;
      await openClubDetail(clubId);
      returnCoachUid.value = savedBackCoach;
    } else if (coachDetail.value?.coach_profile?.user_id) {
      await openCoachDetail(coachDetail.value.coach_profile.user_id);
    }
    uni.showToast({ title: res?.message || "加入跑团成功！", icon: "success" });
    return true;
  } catch (e: any) {
    uni.showModal({
      title: "无法加入跑团",
      content: e?.message || e?.data?.detail || "加入失败，请核对邀请码或准入条件",
      showCancel: false,
    });
    return false;
  } finally {
    joiningClubId.value = null;
  }
}

async function openClubStudio(cid: string) {
  const u = getStoredUser();
  const q = u?.id ? `?viewer_uid=${encodeURIComponent(u.id)}` : "";
  const res: any = await request(`/api/community/showcase/clubs/${encodeURIComponent(cid)}${q}`);
  if (!res?.can_edit) {
    uni.showToast({ title: "仅本跑团主理人/团长可编辑", icon: "none" });
    clubDetail.value = res || null;
    coachDetail.value = null;
    viewMode.value = "plaza";
    return;
  }
  targetOwnerId.value = cid;
  viewMode.value = "studio";
  clubSlogan.value = res?.showcase?.slogan || "";
  clubLandmarks.value = (res?.showcase?.home_landmarks || []).join("、");
  clubSchedule.value = res?.showcase?.schedule_summary || "";
  studioPhotos.value = res?.photos || [];
}

async function openCoachStudio(cuid: string) {
  const u = getStoredUser();
  const q = u?.id ? `?viewer_uid=${encodeURIComponent(u.id)}` : "";
  const res: any = await request(`/api/community/showcase/coaches/${encodeURIComponent(cuid)}${q}`);
  if (!res?.can_edit) {
    uni.showToast({ title: "仅教练/团长本人可编辑", icon: "none" });
    coachDetail.value = res || null;
    clubDetail.value = null;
    viewMode.value = "plaza";
    return;
  }
  targetOwnerId.value = cuid;
  viewMode.value = "coach_studio";
  coachHeadline.value = res?.resume?.headline || "";
  coachCerts.value = (res?.resume?.certifications || []).map((c: any) => c.title || c).join("、");
  coachStory.value = res?.resume?.bio_story || "";
  studioPhotos.value = res?.photos || [];
}

function splitList(raw: string): string[] {
  return raw.split(/[,，、;\n]+/).map((s) => s.trim()).filter(Boolean);
}

async function saveStudioProfile() {
  const u = getStoredUser();
  if (!u?.id) return;
  saving.value = true;
  try {
    if (viewMode.value === "studio") {
      await request(`/api/community/showcase/clubs/${encodeURIComponent(targetOwnerId.value)}`, "PUT", {
        operator_uid: u.id,
        slogan: clubSlogan.value.trim(),
        home_landmarks: splitList(clubLandmarks.value),
        schedule_summary: clubSchedule.value.trim(),
        is_published: true,
      });
    } else {
      await request(`/api/community/showcase/coaches/${encodeURIComponent(targetOwnerId.value)}`, "PUT", {
        operator_uid: u.id,
        headline: coachHeadline.value.trim(),
        certifications: splitList(coachCerts.value).map((t) => ({ title: t, verified: false })),
        bio_story: coachStory.value.trim(),
        is_published: true,
      });
    }
    uni.showToast({ title: "宣传页已保存发布", icon: "success" });
  } catch (e: any) {
    uni.showToast({ title: e?.message || "保存失败", icon: "none" });
  } finally {
    saving.value = false;
  }
}

function onPickCategory(e: any) {
  catIdx.value = Number(e?.detail?.value || 0);
}

async function uploadPhotosMobile() {
  const u = getStoredUser();
  if (!u?.id || !targetOwnerId.value) return;
  uploading.value = true;
  try {
    const added = await chooseAndUploadShowcasePhotos({
      ownerType: viewMode.value === "coach_studio" ? "coach" : "club",
      ownerId: targetOwnerId.value,
      uploaderUid: u.id,
      category: catKeys[catIdx.value] || "group_run",
      caption: photoCaption.value.trim(),
      maxCount: 9,
      setFirstAsCover: studioPhotos.value.length === 0,
    });
    if (added.length) {
      studioPhotos.value = [...added, ...studioPhotos.value];
      photoCaption.value = "";
      uni.showToast({ title: `成功上传 ${added.length} 张大图`, icon: "success" });
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || "上传失败", icon: "none" });
  } finally {
    uploading.value = false;
  }
}

async function deletePhoto(photoId: string) {
  const u = getStoredUser();
  if (!u?.id) return;
  try {
    await request(`/api/community/showcase/photos/${photoId}?operator_uid=${encodeURIComponent(u.id)}`, "DELETE");
    studioPhotos.value = studioPhotos.value.filter((p) => p.id !== photoId);
    uni.showToast({ title: "已移除", icon: "none" });
  } catch (e: any) {
    uni.showToast({ title: e?.message || "删除失败", icon: "none" });
  }
}

function previewPhoto(url: string) {
  const abs = resolveAssetUrl(url);
  if (!abs) return;
  uni.previewImage({ current: abs, urls: [abs] });
}
</script>

<style scoped>
.sub-page {
  min-height: 100vh;
  padding: 24rpx 28rpx 80rpx;
  background-color: var(--rgm-bg, #0b0b0e);
  color: var(--rgm-text, #f4f4f6);
  --rgm-text: var(--rgm-ink);
  --rgm-text-2: var(--rgm-ink-2);
  --rgm-text-3: var(--rgm-ink-3);
}
.sub-header { margin-bottom: 20rpx; }
.sub-title { font-size: 36rpx; font-weight: 900; display: block; color: var(--rgm-text); }
.sub-sub { font-size: 22rpx; color: var(--rgm-text-2); display: block; margin-top: 6rpx; }
.back-row { font-size: 26rpx; font-weight: 800; color: var(--rgm-brand); margin-bottom: 16rpx; }
.plaza-card { margin-top: 20rpx; overflow: hidden; padding: 0; }
.plaza-cover { width: 100%; height: 240rpx; background: var(--rgm-card-2); }
.plaza-body { padding: 22rpx 24rpx; }
.plaza-title-wrap { display: flex; align-items: center; gap: 10rpx; min-width: 0; flex: 1; flex-wrap: wrap; }
.plaza-name { font-size: 30rpx; font-weight: 900; color: var(--rgm-text); }
.org-pill { font-size: 18rpx; font-weight: 800; padding: 4rpx 12rpx; border-radius: 999rpx; background: rgba(59, 130, 246, 0.16); color: #60a5fa; flex-shrink: 0; }
.deco-pill { font-size: 18rpx; font-weight: 800; padding: 4rpx 12rpx; border-radius: 999rpx; background: rgba(252, 76, 2, 0.16); color: var(--rgm-brand); flex-shrink: 0; }
.plaza-badge { font-size: 20rpx; font-weight: 800; color: var(--rgm-brand); flex-shrink: 0; margin-left: 12rpx; }
.plaza-badge.muted { color: var(--rgm-text-3); font-weight: 600; }
.plaza-slogan { font-size: 24rpx; color: var(--rgm-text-2); display: block; margin-top: 8rpx; }
.plaza-stats { font-size: 21rpx; color: var(--rgm-text-3); display: block; margin-top: 10rpx; }
.plaza-foot-row { display: flex; align-items: center; justify-content: space-between; gap: 12rpx; margin-top: 14rpx; padding-top: 14rpx; border-top: 1rpx solid var(--rgm-line); }
.plaza-foot-row .plaza-stats { margin-top: 0; flex: 1; min-width: 0; }
.meta-badge-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10rpx; margin-top: 12rpx; }
.meta-badge-row.compact { margin-top: 10rpx; gap: 8rpx; }
.scope-pill { font-size: 19rpx; font-weight: 800; padding: 4rpx 14rpx; border-radius: 999rpx; flex-shrink: 0; }
.scope-pill.is-org { background: rgba(59, 130, 246, 0.16); color: #3b82f6; border: 1rpx solid rgba(59, 130, 246, 0.32); }
.scope-pill.is-free { background: rgba(16, 185, 129, 0.14); color: #10b981; border: 1rpx solid rgba(16, 185, 129, 0.3); }
.status-pill { font-size: 19rpx; font-weight: 800; padding: 4rpx 14rpx; border-radius: 999rpx; flex-shrink: 0; }
.status-pill.is-free { background: var(--rgm-green-tint, rgba(16, 185, 129, 0.14)); color: var(--rgm-green, #10b981); }
.status-pill.is-invite { background: var(--rgm-amber-tint, rgba(245, 158, 11, 0.16)); color: var(--rgm-amber, #f59e0b); }
.status-pill.is-paused { background: rgba(148, 163, 184, 0.18); color: var(--rgm-text-2); }
.status-pill.is-locked { background: rgba(244, 63, 94, 0.14); color: #f43f5e; }
.city-pill { font-size: 19rpx; font-weight: 700; padding: 4rpx 12rpx; border-radius: 999rpx; background: var(--rgm-card-2); color: var(--rgm-text-2); flex-shrink: 0; }
.member-pill { font-size: 19rpx; font-weight: 800; padding: 4rpx 14rpx; border-radius: 999rpx; background: var(--rgm-green-tint, rgba(16, 185, 129, 0.15)); color: var(--rgm-green, #10b981); flex-shrink: 0; }
.role-pill { font-size: 18rpx; font-weight: 800; padding: 2rpx 12rpx; border-radius: 999rpx; background: rgba(252, 76, 2, 0.14); color: var(--rgm-brand); flex-shrink: 0; }
.hero-card { overflow: hidden; padding: 0; margin-bottom: 20rpx; }
.hero-cover { width: 100%; height: 280rpx; }
.hero-body { padding: 24rpx; }
.hero-title-row { display: flex; align-items: center; justify-content: space-between; gap: 12rpx; }
.hero-name { font-size: 34rpx; font-weight: 900; color: var(--rgm-text); display: block; }
.hero-slogan { font-size: 24rpx; font-weight: 700; color: var(--rgm-brand); display: block; margin-top: 10rpx; }
.stat-grid { display: flex; gap: 12rpx; margin-top: 18rpx; }
.stat-box { flex: 1; padding: 16rpx; border-radius: 16rpx; background: var(--rgm-card-2); text-align: center; }
.stat-v { font-size: 26rpx; font-weight: 900; color: var(--rgm-text); display: block; }
.stat-l { font-size: 19rpx; color: var(--rgm-text-2); display: block; margin-top: 4rpx; }
.sched-txt { font-size: 22rpx; color: var(--rgm-text-2); display: block; margin-top: 16rpx; }
.hero-actions-col { margin-top: 18rpx; display: flex; flex-direction: column; gap: 12rpx; }
.hero-join-btn { margin-top: 0; width: 100%; }
.joined-enter-btn { width: 100%; height: 76rpx; line-height: 76rpx; border-radius: 18rpx; background: var(--rgm-green-tint, rgba(16, 185, 129, 0.14)); color: var(--rgm-green, #10b981); border: 1rpx solid var(--rgm-green-line, rgba(16, 185, 129, 0.35)); font-size: 25rpx; font-weight: 900; }
.disabled-join-btn { width: 100%; height: 74rpx; line-height: 74rpx; border-radius: 18rpx; background: var(--rgm-card-2); color: var(--rgm-text-3); border: 1rpx solid var(--rgm-line); font-size: 24rpx; font-weight: 700; }
.mini-join-btn { margin: 0; padding: 0 22rpx; height: 56rpx; line-height: 56rpx; border-radius: 999rpx; background: var(--rgm-brand); color: #fff; font-size: 22rpx; font-weight: 800; flex-shrink: 0; }
.mini-join-btn::after, .primary-btn::after, .sec-btn::after, .joined-enter-btn::after, .disabled-join-btn::after { border: none; }
.mini-join-btn.is-invite { background: var(--rgm-amber-tint, rgba(245, 158, 11, 0.18)); color: var(--rgm-amber, #d97706); border: 1rpx solid var(--rgm-amber-line, rgba(245, 158, 11, 0.4)); }
.mini-join-btn.is-joined { background: var(--rgm-green-tint, rgba(16, 185, 129, 0.14)); color: var(--rgm-green, #10b981); border: 1rpx solid var(--rgm-green-line, rgba(16, 185, 129, 0.35)); }
.mini-join-btn.is-disabled { background: var(--rgm-card-2); color: var(--rgm-text-3); border: 1rpx solid var(--rgm-line); }
.coach-head-col { flex: 1; min-width: 0; padding-right: 12rpx; }
.coach-bio-txt { display: block; margin-top: 16rpx; padding: 16rpx 18rpx; border-radius: 14rpx; background: var(--rgm-card-2); font-size: 22rpx; color: var(--rgm-text-2); line-height: 1.5; }
.sec-sub-hint { font-size: 20rpx; color: var(--rgm-text-3); }
.empty-inline-txt { font-size: 22rpx; color: var(--rgm-text-3); padding: 14rpx 0; text-align: center; }
.coached-club-item { display: flex; align-items: center; justify-content: space-between; gap: 14rpx; padding: 18rpx 0; border-bottom: 1rpx solid var(--rgm-line); }
.coached-club-item:last-child { border-bottom: none; padding-bottom: 4rpx; }
.coached-club-main { flex: 1; min-width: 0; }
.coached-club-name-row { display: flex; align-items: center; gap: 10rpx; flex-wrap: wrap; }
.coached-club-name { font-size: 27rpx; font-weight: 900; color: var(--rgm-text); }
.coached-club-sub { font-size: 20rpx; color: var(--rgm-text-3); display: block; margin-top: 8rpx; }
.coached-club-right { flex-shrink: 0; }
.modal-mask { position: fixed; inset: 0; z-index: 999; background: rgba(0, 0, 0, 0.65); display: flex; align-items: center; justify-content: center; padding: 32rpx; box-sizing: border-box; }
.modal-box { width: 100%; max-width: 640rpx; border-radius: 26rpx; padding: 28rpx; background: var(--rgm-card, #141418); border: 1rpx solid var(--rgm-line, rgba(255,255,255,0.1)); box-sizing: border-box; }
.modal-title { font-size: 30rpx; font-weight: 900; color: var(--rgm-text); }
.modal-close { font-size: 30rpx; color: var(--rgm-text-3); padding: 6rpx 10rpx; }
.join-nick-card { padding: 16rpx; border-radius: 16rpx; background: var(--rgm-card-2); border: 1rpx solid var(--rgm-line); }
.join-nick-card.has-err { border-color: #f43f5e; }
.err-hint { display: block; margin-top: 8rpx; font-size: 21rpx; color: #f43f5e; font-weight: 700; }
.modal-btn-row { display: flex; gap: 14rpx; margin-top: 24rpx; }
.modal-half-btn { flex: 1; height: 76rpx; line-height: 76rpx; }
.sec-card { margin-top: 20rpx; padding: 24rpx; }
.sec-title { font-size: 28rpx; font-weight: 900; color: var(--rgm-text); display: block; margin-bottom: 14rpx; }
.coach-row { display: flex; align-items: center; justify-content: space-between; padding: 16rpx 0; border-bottom: 1rpx solid var(--rgm-line); }
.coach-name { font-size: 26rpx; font-weight: 800; color: var(--rgm-text); display: block; }
.coach-hl { font-size: 21rpx; color: var(--rgm-text-2); display: block; margin-top: 2rpx; }
.coach-pb { font-size: 22rpx; font-weight: 800; color: var(--rgm-brand); }
.verify-pill { font-size: 20rpx; padding: 6rpx 14rpx; border-radius: 999rpx; background: var(--rgm-green-tint); color: var(--rgm-green); font-weight: 800; }
.photo-grid { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 16rpx; }
.photo-tile { position: relative; width: 204rpx; height: 204rpx; border-radius: 16rpx; overflow: hidden; background: var(--rgm-card-2); }
.tile-img { width: 100%; height: 100%; }
.cover-badge { position: absolute; top: 8rpx; left: 8rpx; padding: 2rpx 10rpx; border-radius: 8rpx; background: var(--rgm-brand); color: #fff; font-size: 18rpx; font-weight: 800; }
.del-badge { position: absolute; bottom: 8rpx; right: 8rpx; padding: 4rpx 12rpx; border-radius: 8rpx; background: rgba(0,0,0,0.75); color: #fda4af; font-size: 20rpx; font-weight: 800; }
.form-card { margin-top: 20rpx; padding: 24rpx; }
.lbl { font-size: 22rpx; font-weight: 700; color: var(--rgm-text-2); display: block; margin: 16rpx 0 8rpx; }
.inp { height: 72rpx; padding: 0 20rpx; border-radius: 16rpx; background: var(--rgm-card-2); border: 1rpx solid var(--rgm-line); color: var(--rgm-text); font-size: 24rpx; }
.tarea { width: 100%; min-height: 140rpx; padding: 16rpx 20rpx; border-radius: 16rpx; background: var(--rgm-card-2); border: 1rpx solid var(--rgm-line); color: var(--rgm-text); font-size: 24rpx; box-sizing: border-box; }
.primary-btn { margin-top: 22rpx; height: 78rpx; line-height: 78rpx; border-radius: 18rpx; background: var(--rgm-brand); color: #fff; font-size: 26rpx; font-weight: 900; }
.sec-btn { height: 72rpx; line-height: 72rpx; border-radius: 16rpx; background: var(--rgm-card-2); color: var(--rgm-text); border: 1rpx solid var(--rgm-line); font-size: 24rpx; font-weight: 800; }
.upload-btn { margin-top: 16rpx; height: 74rpx; line-height: 74rpx; border-radius: 18rpx; background: var(--rgm-green-tint); color: var(--rgm-green); border: 1rpx solid var(--rgm-green-line); font-size: 24rpx; font-weight: 800; }
.row-between { display: flex; justify-content: space-between; align-items: center; }
.cat-pill { font-size: 22rpx; padding: 6rpx 16rpx; border-radius: 999rpx; background: var(--rgm-card-2); color: var(--rgm-brand); font-weight: 800; }
</style>
