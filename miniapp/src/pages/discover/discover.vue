<template>
  <view class="sub-page" :class="themeClass">
    <view class="sub-header">
      <text class="sub-title">🤝 六维同频寻搭子</text>
      <text class="sub-sub">5岁年龄段与公园地标脱敏匹配 · 互关解锁每周跑量 PK</text>
    </view>

    <!-- 3 Search Scopes -->
    <view class="rgm-seg-bar">
      <view class="rgm-seg-item" :class="{ active: scope === 'org' }" @click="switchScope('org')">🏛️ 同大群校友</view>
      <view class="rgm-seg-item" :class="{ active: scope === 'club' }" @click="switchScope('club')">🏃 本跑团队友</view>
      <view class="rgm-seg-item" :class="{ active: scope === 'public' }" @click="switchScope('public')">🌏 同城公开</view>
    </view>

    <!-- Filter Chips -->
    <view class="rgm-card filter-card">
      <view class="filter-row">
        <view class="f-chip" :class="{ active: matchMyVdot }" @click="toggleVdotMatch">
          ⚡ 与我同频 ±2{{ viewerVdot ? ` (${viewerVdot})` : '' }}
        </view>
        <view class="f-chip" :class="{ active: gender === 'female' }" @click="toggleGender('female')">👩 女跑友</view>
        <view class="f-chip" :class="{ active: gender === 'male' }" @click="toggleGender('male')">👨 男跑友</view>
        <picker :range="ageLabels" @change="onPickAge">
          <view class="f-chip" :class="{ active: !!ageGroup }">{{ ageGroup || '年龄段 ▾' }}</view>
        </picker>
        <picker :range="kmLabels" @change="onPickKm">
          <view class="f-chip" :class="{ active: !!monthlyKmMin }">{{ monthlyKmMin ? `≥${monthlyKmMin}km ▾` : '30日跑量 ▾' }}</view>
        </picker>
      </view>
      <view class="search-line">
        <input
          v-model="landmark"
          class="lm-input"
          placeholder="输入常跑公园地标（如 世纪公园 / 徐汇滨江）..."
          @confirm="loadCandidates"
        />
        <button class="search-btn" @click="loadCandidates">检索</button>
      </view>
    </view>

    <!-- Results -->
    <view v-if="loading" class="empty-box">正在按六维同频检索中...</view>
    <view v-else-if="candidates.length === 0" class="rgm-card empty-box">
      <text class="empty-txt">当前条件下暂无匹配的公开跑友，可尝试关闭 ±2 限制或切换检索范围</text>
    </view>

    <view v-for="cand in candidates" :key="cand.user_id" class="rgm-card cand-card">
      <view class="cand-top">
        <image v-if="cand.avatar_url" :src="resolveAssetUrl(cand.avatar_url)" class="cand-avatar" mode="aspectFill" />
        <view v-else class="cand-avatar cand-avatar-fallback">{{ String(cand.display_name || '跑').slice(0, 1) }}</view>
        <view class="cand-meta">
          <view class="cand-name-row">
            <text class="cand-name">{{ cand.display_name }}</text>
            <text class="match-pill">{{ cand.match_score }}% 同频</text>
          </view>
          <text class="cand-sub">{{ cand.age_group }} · {{ cand.gender === 'female' ? '女' : cand.gender === 'male' ? '男' : '跑者' }} · {{ cand.city || '同城' }}</text>
        </view>
      </view>

      <view class="cand-metrics">
        <text class="metric-tag">{{ cand.vdot_band }}</text>
        <text class="metric-tag">30日 {{ cand.monthly_km_30d }} km</text>
        <text v-for="lm in (cand.running_landmarks || []).slice(0, 2)" :key="lm" class="metric-tag">📍 {{ lm }}</text>
      </view>

      <view class="cand-actions">
        <button
          class="follow-btn"
          :class="{ mutual: cand.is_mutual_buddy, following: cand.is_following && !cand.is_mutual_buddy }"
          @click="toggleFollow(cand)"
        >
          {{ cand.is_mutual_buddy ? '⇄ 互关跑搭子' : cand.is_following ? '已关注' : cand.is_followed_by ? '回关成搭子' : '+ 关注结伴' }}
        </button>
        <button v-if="cand.is_mutual_buddy || cand.shared_club" class="pk-btn" @click="openPk(cand.user_id)">
          🏆 周PK
        </button>
      </view>
    </view>

    <!-- Weekly PK Modal -->
    <view v-if="pkData" class="pk-mask" @click="pkData = null">
      <view class="rgm-card pk-sheet" @click.stop>
        <view class="pk-head">
          <text class="pk-title">🏆 跑搭子周跑量友好 PK</text>
          <text class="pk-close" @click="pkData = null">✕</text>
        </view>
        <view class="pk-grid">
          <view class="pk-col is-me">
            <text class="pk-who">{{ pkData.viewer?.display_name || '我' }}</text>
            <text class="pk-val">{{ pkData.viewer?.week_km ?? 0 }} km</text>
            <text class="pk-sub">本月 {{ pkData.viewer?.month_km ?? 0 }} km</text>
          </view>
          <view class="pk-col">
            <text class="pk-who">{{ pkData.buddy?.display_name }}</text>
            <text class="pk-val">{{ pkData.buddy?.week_km ?? 0 }} km</text>
            <text class="pk-sub">本月 {{ pkData.buddy?.month_km ?? 0 }} km</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad, onShow, onPullDownRefresh } from "@dcloudio/uni-app";
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import { getStoredUser, request, resolveAssetUrl, wechatLogin } from "../../utils/api";

const scope = ref<"org" | "club" | "public">("org");
const ageGroup = ref("");
const gender = ref("");
const matchMyVdot = ref(true);
const monthlyKmMin = ref("");
const landmark = ref("");
const viewerVdot = ref<number | null>(null);
const candidates = ref<any[]>([]);
const loading = ref(true);
const pkData = ref<any>(null);

const ageLabels = ["全部年龄", "U30", "30-34", "35-39", "40-44", "45-49", "50+"];
const kmLabels = ["不限跑量", "≥ 50 km", "≥ 100 km", "≥ 180 km", "≥ 250 km"];
const kmValues = ["", "50", "100", "180", "250"];

onShow(() => {
  applySystemTheme(currentTheme.value);
});

onLoad(async (opts?: any) => {
  if (opts?.scope && ["org", "club", "public"].includes(opts.scope)) {
    scope.value = opts.scope;
  }
  await loadCandidates();
});

onPullDownRefresh(async () => {
  await loadCandidates();
  uni.stopPullDownRefresh();
});

async function loadCandidates() {
  loading.value = true;
  try {
    let u = getStoredUser();
    if (!u) u = await wechatLogin();
    if (!u?.id) return;
    const qs: string[] = [`viewer_uid=${encodeURIComponent(u.id)}`, `scope=${scope.value}`, `limit=40`];
    if (ageGroup.value) qs.push(`age_group=${encodeURIComponent(ageGroup.value)}`);
    if (gender.value) qs.push(`gender=${encodeURIComponent(gender.value)}`);
    if (matchMyVdot.value) qs.push(`match_my_vdot=1`);
    if (monthlyKmMin.value) qs.push(`monthly_km_min=${encodeURIComponent(monthlyKmMin.value)}`);
    if (landmark.value.trim()) qs.push(`landmark=${encodeURIComponent(landmark.value.trim())}`);

    const res: any = await request(`/api/community/discover?${qs.join("&")}`);
    candidates.value = res?.candidates || [];
    viewerVdot.value = res?.viewer_vdot ?? null;
  } catch (e: any) {
    uni.showToast({ title: e?.message || "加载失败", icon: "none" });
  } finally {
    loading.value = false;
  }
}

function switchScope(s: "org" | "club" | "public") {
  scope.value = s;
  loadCandidates();
}

function toggleVdotMatch() {
  matchMyVdot.value = !matchMyVdot.value;
  loadCandidates();
}

function toggleGender(g: "female" | "male") {
  gender.value = gender.value === g ? "" : g;
  loadCandidates();
}

function onPickAge(e: any) {
  const idx = Number(e?.detail?.value || 0);
  ageGroup.value = idx === 0 ? "" : ageLabels[idx];
  loadCandidates();
}

function onPickKm(e: any) {
  const idx = Number(e?.detail?.value || 0);
  monthlyKmMin.value = kmValues[idx] || "";
  loadCandidates();
}

async function toggleFollow(cand: any) {
  const u = getStoredUser();
  if (!u?.id) return;
  try {
    if (cand.is_following) {
      await request(
        `/api/community/follow/${encodeURIComponent(cand.user_id)}?follower_id=${encodeURIComponent(u.id)}`,
        "DELETE"
      );
      uni.showToast({ title: "已取消关注", icon: "none" });
    } else {
      const res: any = await request("/api/community/follow", "POST", {
        follower_id: u.id,
        target_uid: cand.user_id,
      });
      uni.showToast({
        title: res?.is_mutual_buddy ? "⇄ 已互关成为跑搭子" : "🤝 已关注",
        icon: "none",
      });
    }
    loadCandidates();
  } catch (e: any) {
    uni.showToast({ title: e?.message || "操作失败", icon: "none" });
  }
}

async function openPk(targetUid: string) {
  const u = getStoredUser();
  if (!u?.id) return;
  try {
    const res = await request(
      `/api/community/buddies/${encodeURIComponent(targetUid)}/pk?viewer_uid=${encodeURIComponent(u.id)}`
    );
    pkData.value = res;
  } catch (e: any) {
    uni.showToast({ title: e?.message || "互关后可开启周PK", icon: "none" });
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
.filter-card { margin-top: 18rpx; padding: 20rpx; }
.filter-row { display: flex; flex-wrap: wrap; gap: 12rpx; }
.f-chip { padding: 10rpx 18rpx; border-radius: 999rpx; font-size: 22rpx; font-weight: 700; background: var(--rgm-card-2); color: var(--rgm-text-2); border: 1rpx solid var(--rgm-line); }
.f-chip.active { background: var(--rgm-brand-tint); color: var(--rgm-brand); border-color: var(--rgm-brand); }
.search-line { display: flex; align-items: center; gap: 12rpx; margin-top: 16rpx; }
.lm-input { flex: 1; height: 68rpx; padding: 0 20rpx; border-radius: 16rpx; background: var(--rgm-card-2); border: 1rpx solid var(--rgm-line); font-size: 24rpx; color: var(--rgm-text); }
.search-btn { height: 68rpx; line-height: 68rpx; padding: 0 28rpx; border-radius: 16rpx; background: var(--rgm-brand); color: #fff; font-size: 24rpx; font-weight: 800; margin: 0; }
.cand-card { margin-top: 20rpx; padding: 24rpx; }
.cand-top { display: flex; align-items: center; gap: 20rpx; }
.cand-avatar { width: 84rpx; height: 84rpx; border-radius: 24rpx; background: var(--rgm-card-2); flex-shrink: 0; }
.cand-avatar-fallback { display: flex; align-items: center; justify-content: center; font-size: 32rpx; font-weight: 900; color: var(--rgm-text); }
.cand-meta { flex: 1; min-width: 0; }
.cand-name-row { display: flex; align-items: center; justify-content: space-between; gap: 12rpx; }
.cand-name { font-size: 28rpx; font-weight: 900; color: var(--rgm-text); }
.match-pill { font-size: 20rpx; font-weight: 900; padding: 4rpx 14rpx; border-radius: 999rpx; background: var(--rgm-brand-tint); color: var(--rgm-brand); }
.cand-sub { font-size: 22rpx; color: var(--rgm-text-2); display: block; margin-top: 4rpx; }
.cand-metrics { display: flex; flex-wrap: wrap; gap: 10rpx; margin-top: 16rpx; }
.metric-tag { font-size: 20rpx; padding: 6rpx 14rpx; border-radius: 12rpx; background: var(--rgm-card-2); color: var(--rgm-text-2); border: 1rpx solid var(--rgm-line); }
.cand-actions { display: flex; gap: 14rpx; margin-top: 18rpx; }
.follow-btn { flex: 1; height: 68rpx; line-height: 68rpx; border-radius: 16rpx; font-size: 24rpx; font-weight: 800; background: var(--rgm-brand); color: #fff; margin: 0; }
.follow-btn.mutual { background: var(--rgm-green-tint); color: var(--rgm-green); border: 1rpx solid var(--rgm-green-line); }
.follow-btn.following { background: var(--rgm-card-2); color: var(--rgm-text-2); border: 1rpx solid var(--rgm-line); }
.pk-btn { height: 68rpx; line-height: 68rpx; padding: 0 26rpx; border-radius: 16rpx; font-size: 24rpx; font-weight: 800; background: var(--rgm-card-2); color: var(--rgm-text); border: 1rpx solid var(--rgm-line); margin: 0; }
.empty-box { padding: 48rpx 24rpx; text-align: center; margin-top: 24rpx; font-size: 24rpx; color: var(--rgm-text-2); }
.pk-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.72); z-index: 999; display: flex; align-items: flex-end; }
.pk-sheet { width: 100%; border-radius: 32rpx 32rpx 0 0; padding: 32rpx 28rpx 56rpx; }
.pk-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24rpx; }
.pk-title { font-size: 30rpx; font-weight: 900; color: var(--rgm-text); }
.pk-close { font-size: 32rpx; color: var(--rgm-text-2); padding: 8rpx; }
.pk-grid { display: flex; gap: 16rpx; }
.pk-col { flex: 1; padding: 24rpx; border-radius: 20rpx; background: var(--rgm-card-2); text-align: center; }
.pk-col.is-me { background: var(--rgm-brand-tint); }
.pk-who { font-size: 22rpx; font-weight: 700; color: var(--rgm-text); display: block; }
.pk-val { font-size: 40rpx; font-weight: 900; color: var(--rgm-brand); display: block; margin: 10rpx 0 6rpx; }
.pk-sub { font-size: 20rpx; color: var(--rgm-text-2); display: block; }
</style>
