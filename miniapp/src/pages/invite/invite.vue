<template>
  <view class="sub-page" :class="themeClass">
    <view v-if="loading" class="rgm-card box center-txt">正在展开金色定向特邀函...</view>
    <view v-else-if="errMsg" class="rgm-card box center-txt">
      <text class="err-txt">{{ errMsg }}</text>
    </view>
    <template v-else-if="preview?.invite">
      <!-- Golden Invite Banner -->
      <view class="rgm-card invite-hero">
        <text class="gold-pill">✨ 免输入邀请码 · 定向兼团特邀函</text>
        <text class="hero-title">
          【{{ preview.invite.club_name }}】{{ preview.invite.inviter_name }} 诚邀加入
        </text>
        <text v-if="preview.invite.preassigned_group" class="group-tag">
          预编组：{{ preview.invite.preassigned_group }}
        </text>
        <text class="hero-desc">{{ preview.invite.reason_tag || preview.non_exclusive_notice }}</text>
        <view class="non-excl-box">
          <text class="non-excl-txt">🛡️ {{ preview.non_exclusive_notice }}</text>
        </view>
      </view>

      <!-- Embedded Club Showcase & Photos Preview -->
      <view v-if="preview.showcase_preview" class="rgm-card box">
        <text class="sec-title">🏛️ 跑团品牌宣传与实拍相册</text>
        <text class="club-slogan">{{ preview.showcase_preview.showcase?.slogan }}</text>
        <view class="stat-row">
          <text class="st-pill">{{ preview.showcase_preview.verified_stats?.member_count ?? 0 }} 位队友</text>
          <text class="st-pill">⌚ 破330 {{ preview.showcase_preview.verified_stats?.sub330_count ?? 0 }} 人</text>
          <text class="st-pill">📸 {{ (preview.showcase_preview.photos || []).length }} 张大片</text>
        </view>
        <scroll-view v-if="(preview.showcase_preview.photos || []).length" scroll-x class="photo-strip">
          <image
            v-for="p in preview.showcase_preview.photos.slice(0, 6)"
            :key="p.id"
            :src="resolveAssetUrl(p.photo_url)"
            class="strip-img"
            mode="aspectFill"
          />
        </scroll-view>
      </view>

      <!-- Action Footer -->
      <view class="action-bar">
        <button class="decline-btn" :disabled="submitting" @click="respond('decline')">暂不加入</button>
        <button class="accept-btn" :disabled="submitting" @click="respond('accept')">
          {{ preview.viewer_already_member ? '已在该团 · 进入跑团 ›' : `免码一键兼入${preview.invite.preassigned_group ? ` (${preview.invite.preassigned_group})` : ''}` }}
        </button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
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
    const q = existing?.id ? `?viewer_uid=${encodeURIComponent(existing.id)}` : "";
    preview.value = await request(`/api/community/invites/${encodeURIComponent(token.value)}${q}`);
  } catch (e: any) {
    errMsg.value = e?.message || "特邀函已失效";
  } finally {
    loading.value = false;
  }
});

async function respond(action: "accept" | "decline") {
  if (action === "accept" && preview.value?.viewer_already_member) {
    setActiveClubId(preview.value.invite.club_id);
    uni.switchTab({ url: "/pages/team/team" });
    return;
  }
  submitting.value = true;
  try {
    let u = getStoredUser() || (await silentCheckExistingWechatUser());
    if (!u?.id) {
      u = await authenticateWechatUser({ agreeTerms: true });
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
.invite-hero { padding: 28rpx; background: var(--rgm-amber-tint); border: 1rpx solid var(--rgm-amber-line); }
.gold-pill { display: inline-block; padding: 6rpx 16rpx; border-radius: 999rpx; background: var(--rgm-brand); color: #fff; font-size: 20rpx; font-weight: 900; }
.hero-title { font-size: 34rpx; font-weight: 900; color: var(--rgm-text); display: block; margin-top: 14rpx; }
.group-tag { display: inline-block; margin-top: 10rpx; padding: 4rpx 14rpx; border-radius: 10rpx; background: var(--rgm-green-tint); color: var(--rgm-green); font-size: 22rpx; font-weight: 800; }
.hero-desc { font-size: 24rpx; color: var(--rgm-text-2); display: block; margin-top: 10rpx; }
.non-excl-box { margin-top: 16rpx; padding: 14rpx 18rpx; border-radius: 16rpx; background: var(--rgm-card); }
.non-excl-txt { font-size: 21rpx; color: var(--rgm-text-2); line-height: 1.45; }
.sec-title { font-size: 28rpx; font-weight: 900; color: var(--rgm-text); display: block; }
.club-slogan { font-size: 24rpx; color: var(--rgm-brand); font-weight: 700; display: block; margin-top: 8rpx; }
.stat-row { display: flex; flex-wrap: wrap; gap: 10rpx; margin-top: 14rpx; }
.st-pill { padding: 6rpx 14rpx; border-radius: 10rpx; background: var(--rgm-card-2); font-size: 20rpx; color: var(--rgm-text); font-weight: 700; }
.photo-strip { white-space: nowrap; margin-top: 16rpx; }
.strip-img { display: inline-block; width: 200rpx; height: 150rpx; border-radius: 14rpx; margin-right: 12rpx; }
.action-bar { display: flex; gap: 16rpx; margin-top: 28rpx; }
.decline-btn { flex: 1; height: 82rpx; line-height: 82rpx; border-radius: 20rpx; background: var(--rgm-card-2); color: var(--rgm-text-2); font-size: 26rpx; font-weight: 800; margin: 0; }
.accept-btn { flex: 2; height: 82rpx; line-height: 82rpx; border-radius: 20rpx; background: var(--rgm-brand); color: #fff; font-size: 26rpx; font-weight: 900; margin: 0; }
</style>
