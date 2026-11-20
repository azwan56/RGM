<template>
  <view class="sub-page" :class="themeClass">
    <view class="sub-header">
      <text class="sub-title">🎯 团长广播与多维靶向纳新</text>
      <text class="sub-sub">跑团之间无排他性 · 支持同大群兼团校友免码预编组特邀</text>
    </view>

    <view class="rgm-seg-bar">
      <view class="rgm-seg-item" :class="{ active: mode === 'recruit' }" @click="mode = 'recruit'">🎯 靶向筛人与发卡</view>
      <view class="rgm-seg-item" :class="{ active: mode === 'broadcast' }" @click="mode = 'broadcast'">📢 发布置顶广播</view>
    </view>

    <!-- Broadcast Composer -->
    <view v-if="mode === 'broadcast'" class="rgm-card box">
      <text class="lbl">广播标题</text>
      <input v-model="bTitle" class="inp" placeholder="如：周六 06:00 世纪公园 24km 合练" />
      <text class="lbl">广播正文</text>
      <textarea v-model="bContent" class="tarea" placeholder="集合门岗、领跑配速与注意事项..." />
      <text class="lbl">触达人群</text>
      <picker :range="audLabels" @change="(e: any) => audIdx = Number(e?.detail?.value || 0)">
        <view class="inp picker-line">{{ audLabels[audIdx] }} ▾</view>
      </picker>
      <button class="primary-btn" :disabled="sending" @click="sendBroadcast">
        {{ sending ? '发布中...' : '📢 发布 72 小时置顶广播' }}
      </button>
    </view>

    <!-- Recruit Radar + Funnel + Native Share Card -->
    <template v-else>
      <view v-if="funnel" class="rgm-card box funnel-box">
        <text class="funnel-txt">
          📊 招募漏斗：发函 {{ funnel.sent_count }} → 查看 {{ funnel.viewed_count }} → 兼团入组 {{ funnel.accepted_count }} → 首周出勤 {{ funnel.first_week_run_count }}
        </text>
      </view>

      <view class="rgm-card box">
        <view class="chip-row">
          <view class="f-chip" :class="{ active: pool === 'same_org' }" @click="switchPool('same_org')">🏛️ 同大群校友(兼团)</view>
          <view class="f-chip" :class="{ active: pool === 'public_city' }" @click="switchPool('public_city')">🌏 同城开放跑友</view>
        </view>
        <view class="chip-row" style="margin-top: 12rpx;">
          <view v-for="pr in presets" :key="pr.k" class="f-chip" :class="{ active: preset === pr.k }" @click="selectPreset(pr.k)">
            {{ pr.l }}
          </view>
        </view>
      </view>

      <view v-if="candidates.length === 0 && emptyReason" class="rgm-card box">
        <text class="cand-sub">{{ emptyReason }}</text>
      </view>

      <view v-for="cand in candidates" :key="cand.user_id" class="rgm-card cand-box" @click="toggleSelect(cand.user_id)">
        <view class="row-between">
          <view>
            <text class="cand-name">{{ selected.includes(cand.user_id) ? '☑ ' : '☐ ' }}{{ cand.display_name }}</text>
            <text class="cand-sub">{{ cand.age_group }} · {{ cand.vdot_band }} · 30日 {{ cand.monthly_km_30d }} km</text>
          </view>
          <text v-if="cand.other_clubs_count > 0" class="multi-badge">已加{{ cand.other_clubs_count }}团(可兼入)</text>
        </view>
      </view>

      <view class="rgm-card box">
        <text class="lbl">特邀卡预览（综合跑团主要信息与图片 · 对方点击直接进跑团）</text>
        <view v-if="clubShareInfo" class="preview-card-mini">
          <image
            v-if="clubShareInfo.hero_cover_url || clubShareInfo.logo_url"
            :src="resolveAssetUrl(clubShareInfo.hero_cover_url || clubShareInfo.logo_url)"
            class="preview-cover-mini"
            mode="aspectFill"
          />
          <view class="preview-info-mini">
            <text class="cand-name">【{{ clubShareInfo.name }}】预编入 {{ groupLabels[grpIdx] }}</text>
            <text class="cand-sub">
              📍 {{ clubShareInfo.city || '上海' }} · {{ clubShareInfo.verified_stats?.member_count ?? clubShareInfo.member_count ?? 1 }}人 · 本月 {{ clubShareInfo.verified_stats?.month_total_km ?? 0 }}km · ⌚破330 {{ clubShareInfo.verified_stats?.sub330_count ?? 0 }}人
            </text>
          </view>
        </view>
        <text class="lbl" style="margin-top: 14rpx;">预编组别 & 推荐理由</text>
        <picker :range="groupLabels" @change="(e: any) => grpIdx = Number(e?.detail?.value || 0)">
          <view class="inp picker-line">{{ groupLabels[grpIdx] }} ▾</view>
        </picker>
        <input v-model="reasonTag" class="inp" style="margin-top: 12rpx;" placeholder="如：同属大群校友 · 常跑世纪公园" />
        <view class="btn-row">
          <button class="primary-btn flex-1" :disabled="sending || selected.length === 0" @click="sendTargetedBatch">
            发出特邀函 ({{ selected.length }})
          </button>
          <button class="wx-btn flex-1" open-type="share">
            💬 微信发特邀卡
          </button>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad, onShow, onShareAppMessage } from "@dcloudio/uni-app";
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import { getActiveClubId, getStoredUser, request, resolveAssetUrl } from "../../utils/api";

const clubId = ref("");
const mode = ref<"recruit" | "broadcast">("recruit");
const pool = ref<"same_org" | "public_city">("same_org");
const preset = ref("");
const candidates = ref<any[]>([]);
const emptyReason = ref("");
const clubShareInfo = ref<any>(null);
const selected = ref<string[]>([]);
const funnel = ref<any>(null);
const sending = ref(false);

const bTitle = ref("");
const bContent = ref("");
const audIdx = ref(0);
const audKeys = ["all", "group_a", "group_b", "group_c", "newcomers_14d"];
const audLabels = ["全部团员", "A组（竞速/破330）", "B组（进阶有氧）", "C组（健康跑）", "近14天新人"];

const grpIdx = ref(0);
const groupLabels = ["A组", "B组", "C组"];
const reasonTag = ref("同属大群校友 · 配速同频诚邀兼团");
const shareToken = ref("");

const presets = [
  { k: "", l: "全部候选" },
  { k: "female_gobi", l: "🎯 女子戈赛" },
  { k: "pacer_330", l: "🐰 330官兔" },
  { k: "cross_club_elite", l: "🤝 跨团联训" },
];

onShow(() => {
  applySystemTheme(currentTheme.value);
});

onLoad(async (opts?: any) => {
  clubId.value = String(opts?.club_id || getActiveClubId() || "");
  if (opts?.tab === "broadcast") mode.value = "broadcast";
  await loadRecruitData();
  await ensureShareToken();
});

async function loadRecruitData() {
  const u = getStoredUser();
  if (!u?.id || !clubId.value) return;
  try {
    const q = `operator_uid=${encodeURIComponent(u.id)}&pool=${pool.value}${preset.value ? `&preset=${preset.value}` : ""}`;
    const [cRes, fRes, sRes]: any = await Promise.all([
      request(`/api/community/clubs/${encodeURIComponent(clubId.value)}/recruit-candidates?${q}`),
      request(`/api/community/clubs/${encodeURIComponent(clubId.value)}/recruit-funnel?operator_uid=${encodeURIComponent(u.id)}`),
      request(`/api/team/${encodeURIComponent(clubId.value)}/share-info?user_id=${encodeURIComponent(u.id)}`).catch(() => null),
    ]);
    candidates.value = cRes?.candidates || [];
    emptyReason.value = cRes?.empty_reason || "";
    funnel.value = fRes?.funnel || null;
    if (sRes) clubShareInfo.value = sRes;
  } catch (e: any) {
    uni.showToast({ title: e?.message || "加载候选池失败", icon: "none" });
  }
}

async function ensureShareToken() {
  const u = getStoredUser();
  if (!u?.id || !clubId.value) return;
  try {
    const res: any = await request(`/api/community/clubs/${encodeURIComponent(clubId.value)}/targeted-invites`, "POST", {
      inviter_uid: u.id,
      target_user_ids: [],
      preassigned_group: groupLabels[grpIdx.value],
      reason_tag: reasonTag.value,
      attach_showcase: true,
    });
    shareToken.value = res?.share_token || "";
  } catch {}
}

onShareAppMessage(() => {
  const cName = clubShareInfo.value?.name || "跑团";
  const mCnt = clubShareInfo.value?.verified_stats?.member_count ?? clubShareInfo.value?.member_count ?? 0;
  const bestImg =
    clubShareInfo.value?.share_card_image_url ||
    clubShareInfo.value?.hero_cover_url ||
    clubShareInfo.value?.photos?.[0]?.photo_url ||
    clubShareInfo.value?.logo_url ||
    "";
  return {
    title: `✨【${cName}】诚邀免码入团（预编入 ${groupLabels[grpIdx.value]}）${mCnt ? ` · ${mCnt}人同跑` : ""} · 点击直接进跑团`,
    path: shareToken.value
      ? `/pages/invite/invite?token=${encodeURIComponent(shareToken.value)}&auto_join=1`
      : `/pages/team/team?club_id=${encodeURIComponent(clubId.value)}&action=join_club&auto_join=1`,
    imageUrl: bestImg ? resolveAssetUrl(bestImg) : "/static/logo-square.png",
  };
});

function switchPool(p: "same_org" | "public_city") {
  pool.value = p;
  selected.value = [];
  loadRecruitData();
}

function selectPreset(k: string) {
  preset.value = k;
  loadRecruitData();
}

function toggleSelect(uid: string) {
  if (selected.value.includes(uid)) {
    selected.value = selected.value.filter((x) => x !== uid);
  } else if (selected.value.length < 20) {
    selected.value = [...selected.value, uid];
  }
}

async function sendBroadcast() {
  const u = getStoredUser();
  if (!u?.id || !clubId.value || !bTitle.value.trim() || !bContent.value.trim()) {
    uni.showToast({ title: "请填写标题与正文", icon: "none" });
    return;
  }
  sending.value = true;
  try {
    await request(`/api/community/clubs/${encodeURIComponent(clubId.value)}/broadcasts`, "POST", {
      author_id: u.id,
      category: "notice",
      title: bTitle.value.trim(),
      content: bContent.value.trim(),
      target_audience: audKeys[audIdx.value] || "all",
      pin_hours: 72,
    });
    uni.showToast({ title: "📢 置顶广播已发送", icon: "success" });
    bTitle.value = "";
    bContent.value = "";
  } catch (e: any) {
    uni.showToast({ title: e?.message || "发送失败", icon: "none" });
  } finally {
    sending.value = false;
  }
}

async function sendTargetedBatch() {
  const u = getStoredUser();
  if (!u?.id || !clubId.value || selected.value.length === 0) return;
  sending.value = true;
  try {
    const res: any = await request(`/api/community/clubs/${encodeURIComponent(clubId.value)}/targeted-invites`, "POST", {
      inviter_uid: u.id,
      target_user_ids: selected.value,
      preassigned_group: groupLabels[grpIdx.value],
      reason_tag: reasonTag.value,
      attach_showcase: true,
    });
    uni.showToast({ title: `已向 ${res?.created_count || 0} 人发送特邀函`, icon: "success" });
    selected.value = [];
    loadRecruitData();
  } catch (e: any) {
    uni.showToast({ title: e?.message || "发送失败", icon: "none" });
  } finally {
    sending.value = false;
  }
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
.box { margin-top: 18rpx; padding: 24rpx; }
.funnel-box { background: var(--rgm-amber-tint); }
.funnel-txt { font-size: 22rpx; font-weight: 800; color: var(--rgm-text); }
.chip-row { display: flex; flex-wrap: wrap; gap: 10rpx; }
.f-chip { padding: 10rpx 18rpx; border-radius: 999rpx; font-size: 22rpx; font-weight: 700; background: var(--rgm-card-2); color: var(--rgm-text-2); border: 1rpx solid var(--rgm-line); }
.f-chip.active { background: var(--rgm-brand-tint); color: var(--rgm-brand); border-color: var(--rgm-brand); }
.cand-box { margin-top: 14rpx; padding: 20rpx 24rpx; }
.row-between { display: flex; justify-content: space-between; align-items: center; gap: 12rpx; }
.cand-name { font-size: 26rpx; font-weight: 900; color: var(--rgm-text); display: block; }
.cand-sub { font-size: 21rpx; color: var(--rgm-text-2); display: block; margin-top: 4rpx; }
.multi-badge { font-size: 19rpx; padding: 4rpx 12rpx; border-radius: 10rpx; background: var(--rgm-blue-tint); color: var(--rgm-blue); font-weight: 800; }
.lbl { font-size: 22rpx; font-weight: 700; color: var(--rgm-text-2); display: block; margin-bottom: 8rpx; }
.inp { height: 72rpx; padding: 0 20rpx; border-radius: 16rpx; background: var(--rgm-card-2); border: 1rpx solid var(--rgm-line); color: var(--rgm-text); font-size: 24rpx; }
.picker-line { display: flex; align-items: center; }
.tarea { width: 100%; min-height: 150rpx; padding: 16rpx 20rpx; border-radius: 16rpx; background: var(--rgm-card-2); border: 1rpx solid var(--rgm-line); color: var(--rgm-text); font-size: 24rpx; box-sizing: border-box; margin-bottom: 16rpx; }
.btn-row { display: flex; gap: 14rpx; margin-top: 18rpx; }
.flex-1 { flex: 1; }
.preview-card-mini { display: flex; align-items: center; gap: 16rpx; padding: 14rpx; border-radius: 16rpx; background: var(--rgm-card-2); border: 1rpx solid var(--rgm-line); }
.preview-cover-mini { width: 96rpx; height: 96rpx; border-radius: 14rpx; flex-shrink: 0; }
.preview-info-mini { flex: 1; min-width: 0; }
.primary-btn { margin-top: 18rpx; height: 76rpx; line-height: 76rpx; border-radius: 18rpx; background: var(--rgm-brand); color: #fff; font-size: 24rpx; font-weight: 900; margin-left: 0; margin-right: 0; }
.wx-btn { margin-top: 18rpx; height: 76rpx; line-height: 76rpx; border-radius: 18rpx; background: #07c160; color: #fff; font-size: 24rpx; font-weight: 900; margin-left: 0; margin-right: 0; }
</style>
