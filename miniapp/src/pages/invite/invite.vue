<template>
  <view class="sub-page" :class="themeClass">
    <view v-if="loading" class="rgm-card box center-txt">正在展开金色定向特邀函...</view>
    <view v-else-if="errMsg" class="rgm-card box center-txt">
      <text class="err-txt">{{ errMsg }}</text>
    </view>
    <template v-else-if="preview?.invite">
      <form @submit="onAcceptFormSubmit">
        <!-- 新用户首次入团置顶昵称卡（原生 form submit 确保点选微信昵称后一次提交生效，避免出现“跑者_xxxx”） -->
        <view v-if="needsWechatNickname && !preview.viewer_already_member" class="rgm-card nick-card" :class="{ 'nick-card-err': !!nickError }">
          <text class="nick-badge">👤 首次入团 · 请先选用您的微信昵称 *</text>
          <input
            type="nickname"
            name="nickname"
            class="nick-input"
            v-model="runnerNickname"
            :focus="nickFocus"
            placeholder="点这里 → 键盘上方一键选微信昵称"
            @input="onNickSync"
            @change="onNickSync"
            @blur="onNickSync"
          />
          <text v-if="nickError" class="nick-err-txt">⚠️ {{ nickError }}</text>
        </view>

        <!-- Unified Synthesized Club Invitation Card (Click Card to Join & Enter Club Directly) -->
        <view class="rgm-card unified-invite-card" @click="onCardClick">
        <image
          v-if="heroCoverUrl"
          :src="resolveAssetUrl(heroCoverUrl)"
          class="hero-cover-img"
          mode="aspectFill"
        />
        <view class="invite-hero-body">
          <view class="pill-top-row">
            <text class="gold-pill">✨ 跑团特邀卡 · 点击卡片直接进跑团</text>
            <text v-if="preview.invite.preassigned_group" class="group-tag">
              预编组：{{ preview.invite.preassigned_group }}
            </text>
          </view>

          <view class="club-head-row">
            <image
              v-if="preview.invite.club_logo"
              :src="resolveAssetUrl(preview.invite.club_logo)"
              class="club-logo-img"
              mode="aspectFill"
            />
            <view class="club-head-info">
              <text class="hero-title">
                【{{ preview.invite.club_name }}】{{ preview.invite.inviter_name }} 诚邀加入
              </text>
              <text class="club-slogan">
                {{ showcaseData?.slogan || preview.invite.reason_tag || preview.non_exclusive_notice }}
              </text>
            </view>
          </view>

          <view class="meta-chips-row">
            <text class="st-pill">📍 {{ preview.invite.club_city || '上海' }}</text>
            <text
              v-for="lm in (showcaseData?.home_landmarks || []).slice(0, 3)"
              :key="lm"
              class="st-pill"
            >
              {{ lm }}
            </text>
            <text v-if="showcaseData?.schedule_summary" class="st-pill sched-pill">
              🗓️ {{ showcaseData.schedule_summary }}
            </text>
          </view>

          <!-- Synthesized Verified Stats Grid -->
          <view class="stat-grid-row">
            <view class="stat-cell">
              <text class="stat-val">{{ verifiedStats?.member_count ?? 1 }}人</text>
              <text class="stat-lbl">活跃队员</text>
            </view>
            <view class="stat-cell">
              <text class="stat-val brand-val">{{ verifiedStats?.month_total_km ?? 0 }}km</text>
              <text class="stat-lbl">本月实跑</text>
            </view>
            <view class="stat-cell">
              <text class="stat-val green-val">{{ verifiedStats?.sub330_count ?? 0 }}人</text>
              <text class="stat-lbl">⌚ 破330</text>
            </view>
            <view class="stat-cell">
              <text class="stat-val">{{ verifiedStats?.official_pacer_races_count ?? 0 }}场</text>
              <text class="stat-lbl">🐰 认证官兔</text>
            </view>
          </view>

          <!-- Core Coaches Strip -->
          <view v-if="coachesList.length" class="coach-strip">
            <text class="coach-strip-lbl">🎖️ 核心教练：</text>
            <text
              v-for="ch in coachesList.slice(0, 2)"
              :key="ch.user_id"
              class="coach-chip"
            >
              {{ ch.display_name }}{{ ch.verified_marathon_pb ? ` (PB ${ch.verified_marathon_pb})` : '' }}
            </text>
          </view>

          <!-- Synthesized Showcase Photos Strip -->
          <scroll-view v-if="photosList.length" scroll-x class="photo-strip" @click.stop>
            <image
              v-for="(p, idx) in photosList.slice(0, 6)"
              :key="p.id || idx"
              :src="resolveAssetUrl(p.photo_url)"
              class="strip-img"
              mode="aspectFill"
              @click.stop="onCardClick"
            />
          </scroll-view>

          <view class="non-excl-box">
            <text class="non-excl-txt">🛡️ {{ preview.non_exclusive_notice }}</text>
            <text class="click-hint-txt">
              {{ needsWechatNickname && !preview.viewer_already_member ? '👆 在上方选用微信昵称后，点下方按钮即可免码进团 ›' : '👆 点击本邀请卡任意区域即可免码直接进跑团 ›' }}
            </text>
          </view>
        </view>
      </view>

      <!-- Action Footer -->
      <view class="action-bar">
        <button class="decline-btn" :disabled="submitting" @click="respond('decline')">暂不加入</button>
        <button class="accept-btn" form-type="submit" :disabled="submitting">
          {{ preview.viewer_already_member ? '已在该团 · 直接进入跑团 ›' : `一键免码进跑团${preview.invite.preassigned_group ? ` (${preview.invite.preassigned_group})` : ''}` }}
        </button>
      </view>
      </form>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import {
  authenticateWechatUser,
  getStoredUser,
  request,
  resolveAssetUrl,
  setActiveClubId,
  silentCheckExistingWechatUser,
} from "../../utils/api";

const token = ref("");
const preview = ref<any>(null);
const loading = ref(true);
const errMsg = ref("");
const submitting = ref(false);
const currentUser = ref<any>(getStoredUser());
const runnerNickname = ref("");
const nickError = ref("");
const nickFocus = ref(false);

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

const needsWechatNickname = computed(() => isGenericRunnerName(currentUser.value?.display_name));

function onNickSync(e: any) {
  const val = String(e?.detail?.value ?? "").trim();
  if (val) {
    runnerNickname.value = val;
    if (!isGenericRunnerName(val)) nickError.value = "";
  }
}

function triggerNickFocus(msg?: string) {
  if (msg) nickError.value = msg;
  nickFocus.value = false;
  setTimeout(() => {
    nickFocus.value = true;
  }, 60);
}

function onCardClick() {
  if (needsWechatNickname.value && !preview.value?.viewer_already_member && isGenericRunnerName(runnerNickname.value)) {
    triggerNickFocus("请先点击上方昵称框选用微信昵称");
    uni.showToast({ title: "请先选用微信昵称", icon: "none" });
    return;
  }
  respond("accept");
}

function onAcceptFormSubmit(e: any) {
  const fromForm = String(e?.detail?.value?.nickname ?? "").trim();
  if (fromForm) {
    runnerNickname.value = fromForm;
    nickError.value = "";
  }
  respond("accept", fromForm || runnerNickname.value.trim());
}

const showcaseData = computed(() => preview.value?.showcase_summary || preview.value?.showcase_preview?.showcase || preview.value?.invite || {});
const verifiedStats = computed(() => preview.value?.showcase_summary?.verified_stats || preview.value?.showcase_preview?.verified_stats || preview.value?.invite?.verified_stats || {});
const photosList = computed<any[]>(() => preview.value?.showcase_summary?.photos || preview.value?.showcase_preview?.photos || preview.value?.invite?.photos || []);
const coachesList = computed<any[]>(() => preview.value?.showcase_summary?.coaching_team || preview.value?.showcase_preview?.coaching_team || preview.value?.invite?.coaching_team || []);
const heroCoverUrl = computed(() => showcaseData.value?.hero_cover_url || photosList.value[0]?.photo_url || "");

onShow(() => {
  applySystemTheme(currentTheme.value);
});

onLoad(async (opts?: any) => {
  token.value = decodeURIComponent(String(opts?.token || "")).trim();
  if (!token.value) {
    errMsg.value = "缺少特邀函令牌";
    loading.value = false;
    return;
  }
  try {
    const existing = getStoredUser() || (await silentCheckExistingWechatUser());
    if (existing) currentUser.value = existing;
    const q = existing?.id ? `?viewer_uid=${encodeURIComponent(existing.id)}` : "";
    preview.value = await request(`/api/community/invites/${encodeURIComponent(token.value)}${q}`);

    // 若从微信特邀卡点击进入 (auto_join=1) 且老用户已拥有真实昵称，直接自动入团并进入跑团主页
    if (String(opts?.auto_join || "") === "1" && existing?.id && !isGenericRunnerName(existing.display_name) && preview.value?.invite) {
      await respond("accept");
      return;
    }
    if (needsWechatNickname.value && !preview.value?.viewer_already_member) {
      triggerNickFocus();
    }
  } catch (e: any) {
    errMsg.value = e?.message || "特邀函已失效";
  } finally {
    loading.value = false;
  }
});

async function respond(action: "accept" | "decline", submittedNick?: string) {
  if (action === "accept" && preview.value?.viewer_already_member) {
    setActiveClubId(preview.value.invite.club_id);
    uni.switchTab({ url: "/pages/team/team" });
    return;
  }
  const finalNick = String(submittedNick ?? runnerNickname.value ?? "").trim();
  if (action === "accept" && needsWechatNickname.value && isGenericRunnerName(finalNick)) {
    triggerNickFocus("请先点击上方昵称框，一键选用您的微信昵称（不能为默认代号）");
    uni.showToast({ title: "请先选用微信昵称", icon: "none" });
    return;
  }
  submitting.value = true;
  try {
    let u = getStoredUser() || (await silentCheckExistingWechatUser());
    if (!u?.id) {
      u = await authenticateWechatUser({ agreeTerms: true, nickName: finalNick || undefined });
    }
    if (u) currentUser.value = u;
    if (action === "accept" && finalNick && !isGenericRunnerName(finalNick) && isGenericRunnerName(u.display_name)) {
      try {
        await request(`/api/profile/${encodeURIComponent(u.id)}`, "PUT", { display_name: finalNick });
        u.display_name = finalNick;
        uni.setStorageSync("rgm_user", JSON.stringify(u));
      } catch (_) {}
    }
    const res: any = await request(`/api/community/invites/${encodeURIComponent(token.value)}/respond`, "POST", {
      user_id: u.id,
      action,
    });
    if (action === "accept") {
      setActiveClubId(res?.club_id || preview.value.invite.club_id);
      uni.showToast({ title: "🎉 已免码兼团加入！", icon: "success" });
      setTimeout(() => {
        uni.switchTab({ url: "/pages/team/team" });
      }, 600);
    } else {
      uni.switchTab({ url: "/pages/index/index" });
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || "操作失败", icon: "none" });
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.sub-page {
  min-height: 100vh;
  padding: 24rpx 28rpx 120rpx;
  background-color: var(--rgm-bg, #0b0b0e);
  color: var(--rgm-text, #f4f4f6);
  --rgm-text: var(--rgm-ink);
  --rgm-text-2: var(--rgm-ink-2);
  --rgm-text-3: var(--rgm-ink-3);
}
.box { margin-top: 20rpx; padding: 24rpx; }
.center-txt { text-align: center; font-size: 24rpx; color: var(--rgm-text-2); padding: 60rpx 24rpx; }
.err-txt { color: var(--rgm-red); font-weight: 800; }
.nick-card { padding: 22rpx 24rpx; margin-bottom: 18rpx; border: 2rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.45)); }
.nick-card-err { border-color: #ef4444; background: rgba(239, 68, 68, 0.08); }
.nick-badge { display: block; font-size: 23rpx; font-weight: 900; color: var(--rgm-brand); margin-bottom: 12rpx; }
.nick-input { height: 74rpx; padding: 0 22rpx; border-radius: 16rpx; background: var(--rgm-card-2); border: 1rpx solid var(--rgm-line-strong, rgba(255,255,255,0.2)); color: var(--rgm-text); font-size: 27rpx; font-weight: 700; }
.nick-err-txt { display: block; font-size: 21rpx; font-weight: 700; color: #f87171; margin-top: 8rpx; }
.unified-invite-card { overflow: hidden; padding: 0; background: var(--rgm-amber-tint); border: 2rpx solid var(--rgm-amber-line); }
.hero-cover-img { width: 100%; height: 280rpx; background: var(--rgm-card-2); }
.invite-hero-body { padding: 26rpx; }
.pill-top-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12rpx; }
.gold-pill { display: inline-block; padding: 6rpx 16rpx; border-radius: 999rpx; background: var(--rgm-brand); color: #fff; font-size: 20rpx; font-weight: 900; }
.group-tag { display: inline-block; padding: 6rpx 14rpx; border-radius: 999rpx; background: var(--rgm-green-tint); color: var(--rgm-green); font-size: 20rpx; font-weight: 800; }
.club-head-row { display: flex; align-items: center; gap: 18rpx; margin-top: 16rpx; }
.club-logo-img { width: 96rpx; height: 96rpx; border-radius: 20rpx; flex-shrink: 0; border: 2rpx solid var(--rgm-brand); }
.club-head-info { flex: 1; min-width: 0; }
.hero-title { font-size: 32rpx; font-weight: 900; color: var(--rgm-text); display: block; }
.club-slogan { font-size: 23rpx; color: var(--rgm-brand); font-weight: 700; display: block; margin-top: 6rpx; }
.meta-chips-row { display: flex; flex-wrap: wrap; gap: 10rpx; margin-top: 14rpx; }
.st-pill { padding: 6rpx 14rpx; border-radius: 10rpx; background: var(--rgm-card); font-size: 20rpx; color: var(--rgm-text); font-weight: 700; }
.sched-pill { color: var(--rgm-brand); }
.stat-grid-row { display: flex; gap: 10rpx; margin-top: 16rpx; }
.stat-cell { flex: 1; padding: 14rpx 8rpx; border-radius: 14rpx; background: var(--rgm-card); text-align: center; }
.stat-val { font-size: 24rpx; font-weight: 900; color: var(--rgm-text); display: block; }
.brand-val { color: var(--rgm-brand); }
.green-val { color: var(--rgm-green); }
.stat-lbl { font-size: 18rpx; color: var(--rgm-text-2); display: block; margin-top: 4rpx; }
.coach-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 10rpx; margin-top: 14rpx; }
.coach-strip-lbl { font-size: 20rpx; font-weight: 800; color: var(--rgm-text); }
.coach-chip { font-size: 20rpx; padding: 4rpx 12rpx; border-radius: 10rpx; background: var(--rgm-card); color: var(--rgm-text-2); font-weight: 700; }
.photo-strip { white-space: nowrap; margin-top: 16rpx; }
.strip-img { display: inline-block; width: 190rpx; height: 140rpx; border-radius: 14rpx; margin-right: 12rpx; }
.non-excl-box { margin-top: 16rpx; padding: 14rpx 18rpx; border-radius: 16rpx; background: var(--rgm-card); }
.non-excl-txt { font-size: 20rpx; color: var(--rgm-text-2); line-height: 1.45; display: block; }
.click-hint-txt { font-size: 21rpx; font-weight: 900; color: var(--rgm-brand); display: block; margin-top: 6rpx; }
.action-bar { display: flex; gap: 16rpx; margin-top: 28rpx; }
.decline-btn { flex: 1; height: 82rpx; line-height: 82rpx; border-radius: 20rpx; background: var(--rgm-card-2); color: var(--rgm-text-2); font-size: 26rpx; font-weight: 800; margin: 0; }
.accept-btn { flex: 2; height: 82rpx; line-height: 82rpx; border-radius: 20rpx; background: var(--rgm-brand); color: #fff; font-size: 26rpx; font-weight: 900; margin: 0; }
</style>
