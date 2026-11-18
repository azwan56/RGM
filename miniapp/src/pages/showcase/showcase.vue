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
      <view class="back-row" @click="clubDetail = null">‹ 返回展厅列表</view>
      <view class="rgm-card hero-card">
        <image
          v-if="clubDetail.showcase?.hero_cover_url"
          :src="resolveAssetUrl(clubDetail.showcase.hero_cover_url)"
          class="hero-cover"
          mode="aspectFill"
        />
        <view class="hero-body">
          <text class="hero-name">{{ clubDetail.club?.name }}</text>
          <text class="hero-slogan">{{ clubDetail.showcase?.slogan }}</text>
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
          <view v-if="clubDetail.can_edit" class="edit-row">
            <button class="sec-btn" @click="openClubStudio(clubDetail.club.id)">🎨 装修主页与相册传图</button>
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
      <view class="back-row" @click="coachDetail = null">‹ 返回</view>
      <view class="rgm-card sec-card">
        <view class="row-between">
          <view>
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
        <button v-if="coachDetail.can_edit" class="primary-btn" style="margin-top: 18rpx;" @click="openCoachStudio(coachDetail.coach_profile.user_id)">
          🎨 编辑我的资历与传照
        </button>
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
              <text class="plaza-name">{{ c.name }}</text>
              <text class="plaza-badge">📸 {{ c.photo_count }}张</text>
            </view>
            <text class="plaza-slogan">{{ c.slogan }}</text>
            <text class="plaza-stats">{{ c.verified_stats?.member_count ?? 0 }}人 · 破330 {{ c.verified_stats?.sub330_count ?? 0 }}人 · 看相册与教练 ›</text>
          </view>
        </view>
      </view>

      <view v-else>
        <view v-for="ch in plazaCoaches" :key="ch.user_id" class="rgm-card sec-card" @click="openCoachDetail(ch.user_id)">
          <view class="row-between">
            <text class="plaza-name">{{ ch.display_name }}</text>
            <text v-if="ch.watch_verified" class="verify-pill">⌚ 手表核验</text>
          </view>
          <text class="plaza-slogan">{{ ch.headline }}</text>
          <text class="plaza-stats">全马PB {{ ch.verified_marathon_pb || '教练认证' }} · 官兔 ×{{ ch.official_pacer_count }} · 风采照 {{ ch.photo_count }} 张 ›</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad, onShow } from "@dcloudio/uni-app";
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import PrivacyPopup from "../../components/PrivacyPopup.vue";
import {
  chooseAndUploadShowcasePhotos,
  getStoredUser,
  request,
  resolveAssetUrl,
  wechatLogin,
} from "../../utils/api";

const viewMode = ref<"plaza" | "studio" | "coach_studio">("plaza");
const plazaTab = ref<"clubs" | "coaches">("clubs");
const plazaClubs = ref<any[]>([]);
const plazaCoaches = ref<any[]>([]);
const clubDetail = ref<any>(null);
const coachDetail = ref<any>(null);

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
  const u = getStoredUser();
  const q = u?.id ? `?viewer_uid=${encodeURIComponent(u.id)}` : "";
  clubDetail.value = await request(`/api/community/showcase/clubs/${encodeURIComponent(cid)}${q}`);
  coachDetail.value = null;
}

async function openCoachDetail(cuid: string) {
  const u = getStoredUser();
  const q = u?.id ? `?viewer_uid=${encodeURIComponent(u.id)}` : "";
  coachDetail.value = await request(`/api/community/showcase/coaches/${encodeURIComponent(cuid)}${q}`);
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
.plaza-name { font-size: 30rpx; font-weight: 900; color: var(--rgm-text); }
.plaza-badge { font-size: 20rpx; font-weight: 800; color: var(--rgm-brand); }
.plaza-slogan { font-size: 24rpx; color: var(--rgm-text-2); display: block; margin-top: 8rpx; }
.plaza-stats { font-size: 21rpx; color: var(--rgm-text-3); display: block; margin-top: 10rpx; }
.hero-card { overflow: hidden; padding: 0; margin-bottom: 20rpx; }
.hero-cover { width: 100%; height: 280rpx; }
.hero-body { padding: 24rpx; }
.hero-name { font-size: 34rpx; font-weight: 900; color: var(--rgm-text); display: block; }
.hero-slogan { font-size: 24rpx; font-weight: 700; color: var(--rgm-brand); display: block; margin-top: 6rpx; }
.stat-grid { display: flex; gap: 12rpx; margin-top: 18rpx; }
.stat-box { flex: 1; padding: 16rpx; border-radius: 16rpx; background: var(--rgm-card-2); text-align: center; }
.stat-v { font-size: 26rpx; font-weight: 900; color: var(--rgm-text); display: block; }
.stat-l { font-size: 19rpx; color: var(--rgm-text-2); display: block; margin-top: 4rpx; }
.sched-txt { font-size: 22rpx; color: var(--rgm-text-2); display: block; margin-top: 16rpx; }
.edit-row { margin-top: 18rpx; }
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
