<template>
  <view v-if="visible" class="psc-mask" :class="[themeClass, { 'psc-light': isVolt }]" @click="handleClose" @touchmove.stop.prevent>
    <view class="psc-dialog" @click.stop>
      <!-- Top Header -->
      <view class="psc-header">
        <view class="psc-title-wrap">
          <text class="psc-title">{{ cardMode === 'race' ? '🏅 完赛分享卡' : '📸 打卡分享卡' }}</text>
        </view>
        <view class="psc-close" @click="handleClose">✕</view>
      </view>

      <!-- Scrollable Controls + Live Poster Preview -->
      <scroll-view scroll-y class="psc-scroll">
        <!-- 1. Photo & Overlay Toolbar -->
        <view class="psc-controls-card">
          <!-- Mode Switcher: Daily Workout vs Completed Race -->
          <view v-if="completedRaces.length > 0" class="psc-control-group">
            <text class="psc-ctrl-label">🏆 类型：</text>
            <view class="psc-pill-row">
              <view
                class="psc-pill"
                :class="{ active: cardMode === 'workout' }"
                @click="handleSwitchCardMode('workout')"
              >
                🏃 日常训练打卡
              </view>
              <view
                class="psc-pill race-pill"
                :class="{ active: cardMode === 'race' }"
                @click="handleSwitchCardMode('race')"
              >
                🏅 完赛战报 ({{ completedRaces.length }})
              </view>
            </view>
          </view>

          <!-- Completed Races Selector (when in race mode) -->
          <view v-if="cardMode === 'race' && completedRaces.length > 0" class="psc-control-group">
            <text class="psc-ctrl-label">🏅 选择赛事：</text>
            <scroll-view scroll-x class="psc-runs-scroll">
              <view class="psc-runs-row">
                <view
                  v-for="rc in completedRaces"
                  :key="rc.id"
                  class="psc-run-chip race-chip"
                  :class="{ active: currentRaceId === String(rc.id) }"
                  @click="handleSelectRace(String(rc.id))"
                >
                  {{ rc.label }}
                </view>
              </view>
            </scroll-view>
          </view>

          <!-- Recent Runs Selector (when in workout mode) -->
          <view v-if="cardMode === 'workout' && recentRuns.length > 1" class="psc-control-group">
            <text class="psc-ctrl-label">🏃 跑步记录：</text>
            <scroll-view scroll-x class="psc-runs-scroll">
              <view class="psc-runs-row">
                <view
                  v-for="r in recentRuns"
                  :key="r.id"
                  class="psc-run-chip"
                  :class="{ active: currentActivityId === r.id }"
                  @click="handleSelectRun(r.id)"
                >
                  {{ r.label }}
                </view>
              </view>
            </scroll-view>
          </view>

          <!-- Daily Plan / Pre-race Target Visibility Switcher -->
          <view class="psc-control-group">
            <view class="psc-label-between">
              <text class="psc-ctrl-label">
                📋 {{ cardMode === 'race' ? '赛前目标：' : '当日计划：' }}
              </text>
            </view>
            <view class="psc-pill-row">
              <view
                class="psc-pill"
                :class="{ active: showDailyPlan }"
                @click="setShowDailyPlan(true)"
              >
                {{ cardMode === 'race' ? '🏁 显示赛前目标' : '📋 显示当日计划' }}
              </view>
              <view
                class="psc-pill"
                :class="{ active: !showDailyPlan }"
                @click="setShowDailyPlan(false)"
              >
                {{ cardMode === 'race' ? '🙈 不显示赛前目标' : '🙈 不显示当日计划' }}
              </view>
            </view>
          </view>

          <!-- Photo Picker Row -->
          <view class="psc-photo-bar">
            <button class="psc-photo-btn primary" @click="handleChoosePhoto">
              <text class="btn-ic">🖼️</text>
              <text>{{ userPhotoPath ? "更换照片" : "选择照片 / 拍照" }}</text>
            </button>
            <button v-if="userPhotoPath" class="psc-photo-btn ghost" @click="handleClearPhoto">
              默认背景
            </button>
          </view>

          <!-- Smart Face Centering & Vertical Framing Controls (visible when user photo is loaded) -->
          <view v-if="userPhotoPath" class="psc-control-group psc-face-box">
            <view class="psc-label-between">
              <text class="psc-ctrl-label">
                🎯 构图：
                <text class="psc-face-status">
                  {{ detectingFace ? "正在识别人脸位置..." : (faceDetected ? "✨ 已识别人脸" : "✨ 已锁定头部") }}
                </text>
              </text>
            </view>
            <view class="psc-pill-row">
              <view
                class="psc-pill"
                :class="{ active: focusPreset === 'auto' }"
                @click="applyFocusPreset('auto')"
              >
                🤖 自动人脸置中
              </view>
              <view
                class="psc-pill"
                :class="{ active: focusPreset === 'top' }"
                @click="applyFocusPreset('top')"
              >
                ⬆️ 露头顶
              </view>
              <view
                class="psc-pill"
                :class="{ active: focusPreset === 'upper' }"
                @click="applyFocusPreset('upper')"
              >
                👤 头部黄金位
              </view>
              <view
                class="psc-pill"
                :class="{ active: focusPreset === 'center' }"
                @click="applyFocusPreset('center')"
              >
                ⏺️ 几何正中
              </view>
              <view
                class="psc-pill"
                :class="{ active: focusPreset === 'bottom' }"
                @click="applyFocusPreset('bottom')"
              >
                ⬇️ 偏下全身
              </view>
            </view>
            <!-- Smooth Vertical Fine-Tune Slider -->
            <view class="psc-slider-row">
              <text class="psc-slider-lbl">上下微调</text>
              <slider
                class="psc-slider"
                :value="Math.round(photoFocusY * 100)"
                min="0"
                max="100"
                step="2"
                activeColor="#d0fd3e"
                backgroundColor="rgba(255,255,255,0.14)"
                block-color="#d0fd3e"
                block-size="18"
                @change="handleFocusSliderChange"
              />
              <text class="psc-slider-val">{{ Math.round(photoFocusY * 100) }}%</text>
            </view>
          </view>

          <!-- Overlay Mode Switcher (Map + Elevation on Photo) -->
          <view class="psc-control-group">
            <text class="psc-ctrl-label">🗺️ 叠加图层：</text>
            <view class="psc-pill-row">
              <view
                class="psc-pill"
                :class="{ active: overlayMode === 'both' }"
                @click="setOverlayMode('both')"
              >
                🗺️+⛰️ 轨迹+海拔
              </view>
              <view
                class="psc-pill"
                :class="{ active: overlayMode === 'map' }"
                @click="setOverlayMode('map')"
              >
                🗺️ 仅轨迹地图
              </view>
              <view
                class="psc-pill"
                :class="{ active: overlayMode === 'elevation' }"
                @click="setOverlayMode('elevation')"
              >
                ⛰️ 仅海拔曲线
              </view>
            </view>
          </view>

          <!-- Track Position Switcher -->
          <view v-if="overlayMode !== 'elevation'" class="psc-control-group">
            <text class="psc-ctrl-label">📍 轨迹位置：</text>
            <view class="psc-pill-row">
              <view
                class="psc-pill"
                :class="{ active: trackPosition === 'corner' }"
                @click="setTrackPosition('corner')"
              >
                右上角
              </view>
              <view
                class="psc-pill"
                :class="{ active: trackPosition === 'center' }"
                @click="setTrackPosition('center')"
              >
                居中大图
              </view>
            </view>
          </view>

          <!-- Canova Commentary Switcher -->
          <view class="psc-control-group">
            <view class="psc-label-between">
              <text class="psc-ctrl-label">👨‍🏫 Canova 点评：</text>
              <text class="psc-edit-toggle" @click="showCustomEdit = !showCustomEdit">
                {{ showCustomEdit ? "收起编辑 ▴" : "✍️ 微调文字" }}
              </text>
            </view>
            <view class="psc-pill-row">
              <view
                v-for="opt in commentaryOptions"
                :key="opt.key"
                class="psc-pill"
                :class="{ active: activeCommentaryKey === opt.key }"
                @click="handleSelectCommentary(opt)"
              >
                {{ opt.label }}
              </view>
            </view>
            <textarea
              v-if="showCustomEdit"
              v-model="customCommentary"
              class="psc-commentary-input"
              maxlength="160"
              placeholder="微调点评文字..."
              @blur="renderPosterCanvas"
            />
          </view>
        </view>

        <!-- 2. Generated Poster Image Preview -->
        <view class="psc-preview-container">
          <view v-if="loading || rendering" class="psc-loading-box">
            <view class="psc-spinner" />
            <text class="psc-loading-text">{{ loading ? "正在加载数据..." : "正在生成卡片..." }}</text>
          </view>

          <image
            v-if="posterImageUrl"
            :src="posterImageUrl"
            class="psc-poster-img"
            mode="widthFix"
            :show-menu-by-longpress="true"
            @click="handlePreviewFullImage"
          />

          <text v-if="posterImageUrl" class="psc-preview-hint">
            点击放大 · 长按转发/保存
          </text>
        </view>
      </scroll-view>

      <!-- Bottom Action Bar -->
      <view class="psc-footer">
        <button class="psc-action-btn share-btn" :disabled="!posterImageUrl || rendering" @click="handleShareImage">
          📲 转发
        </button>
        <button class="psc-action-btn save-btn" :disabled="!posterImageUrl || rendering" @click="handleSaveToAlbum">
          💾 保存
        </button>
      </view>

      <!-- Offscreen High-Res Canvas (750 x 1460) -->
      <canvas
        canvas-id="personalSharePosterCanvas"
        id="personalSharePosterCanvas"
        class="psc-hidden-canvas"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, getCurrentInstance, onBeforeUnmount } from "vue";
import { request, getStoredUser, getActiveClubId, setTabBarHidden } from "../utils/api";
import { isVolt, themeClass } from "../utils/theme";
import { trackModal, trackClick } from "../utils/telemetry";

const props = defineProps<{
  visible: boolean;
  activityId?: string;
  targetDate?: string;
  raceId?: string;
  targetUid?: string;
}>();

const emit = defineEmits(["close"]);
const instance = getCurrentInstance();

const loading = ref(false);
const rendering = ref(false);
const shareData = ref<any>(null);

watch(
  () => props.visible,
  (val, oldVal) => {
    if (val && !oldVal) {
      trackModal("share_card", "打开朋友圈打卡战报卡片", "open", {
        activity_id: props.activityId || undefined,
        race_id: props.raceId || undefined,
      });
    } else if (!val && oldVal) {
      trackModal("share_card", "关闭朋友圈打卡战报卡片", "close");
    }
  }
);

// Workout vs Completed Race Mode
const cardMode = ref<"workout" | "race">("workout");
const recentRuns = ref<any[]>([]);
const completedRaces = ref<any[]>([]);
const currentActivityId = ref<string>("");
const currentRaceId = ref<string>("");

// User Photo & Smart Face Focus State
const userPhotoPath = ref<string>("");
const userPhotoWidth = ref<number>(0);
const userPhotoHeight = ref<number>(0);
const photoFocusX = ref<number>(0.5);
const photoFocusY = ref<number>(0.18);
const autoFocusX = ref<number>(0.5);
const autoFocusY = ref<number>(0.18);
const faceDetected = ref<boolean>(false);
const detectingFace = ref<boolean>(false);
const focusPreset = ref<"auto" | "top" | "upper" | "center" | "bottom">("auto");
const hasCustomSelectedPhoto = ref<boolean>(false);

// Overlay Controls
const overlayMode = ref<"both" | "map" | "elevation">("both");
const trackPosition = ref<"corner" | "center">("corner");
const showDailyPlan = ref<boolean>(true);

// Canova Commentary State
const commentaryOptions = ref<Array<{ key: string; label: string; text: string }>>([]);
const activeCommentaryKey = ref<string>("exec");
const customCommentary = ref<string>("");
const showCustomEdit = ref(false);

// Generated Poster Temp File Path
const posterImageUrl = ref<string>("");

watch(
  () => [props.visible, props.raceId, props.activityId, props.targetUid],
  async ([val]) => {
    setTabBarHidden(Boolean(val), "share_card");
    if (val) {
      if (props.raceId) {
        cardMode.value = "race";
        currentRaceId.value = String(props.raceId);
        currentActivityId.value = "";
        await fetchShareCardData("", undefined, currentRaceId.value);
      } else {
        cardMode.value = "workout";
        currentRaceId.value = "";
        currentActivityId.value = props.activityId || "";
        await fetchShareCardData(currentActivityId.value, props.targetDate, "");
      }
    }
  },
  { immediate: true }
);

watch(isVolt, () => {
  if (props.visible && shareData.value) {
    renderPosterCanvas();
  }
});

function handleClose() {
  setTabBarHidden(false, "share_card");
  emit("close");
}

onBeforeUnmount(() => {
  setTabBarHidden(false, "share_card");
});

function setOverlayMode(mode: "both" | "map" | "elevation") {
  overlayMode.value = mode;
  renderPosterCanvas();
}

function setTrackPosition(pos: "corner" | "center") {
  trackPosition.value = pos;
  renderPosterCanvas();
}

function setShowDailyPlan(val: boolean) {
  if (showDailyPlan.value === val) return;
  showDailyPlan.value = val;
  if (!val && activeCommentaryKey.value === "exec") {
    const execOpt = commentaryOptions.value.find((o) => o.key === "exec");
    const physOpt = commentaryOptions.value.find((o) => o.key === "phys");
    if (physOpt && (!customCommentary.value || customCommentary.value === execOpt?.text)) {
      activeCommentaryKey.value = "phys";
      customCommentary.value = physOpt.text;
    }
  } else if (val && activeCommentaryKey.value === "phys") {
    const execOpt = commentaryOptions.value.find((o) => o.key === "exec");
    const physOpt = commentaryOptions.value.find((o) => o.key === "phys");
    if (execOpt && (!customCommentary.value || customCommentary.value === physOpt?.text)) {
      activeCommentaryKey.value = "exec";
      customCommentary.value = execOpt.text;
    }
  }
  renderPosterCanvas();
}

async function handleSwitchCardMode(mode: "workout" | "race") {
  if (mode === cardMode.value) return;
  cardMode.value = mode;
  if (mode === "race") {
    const firstRaceId = currentRaceId.value || (completedRaces.value[0]?.id ? String(completedRaces.value[0].id) : "");
    currentRaceId.value = firstRaceId;
    await fetchShareCardData("", undefined, firstRaceId);
  } else {
    currentRaceId.value = "";
    const actId = currentActivityId.value || (recentRuns.value[0]?.id ? String(recentRuns.value[0].id) : "");
    await fetchShareCardData(actId, props.targetDate, "");
  }
}

async function handleSelectRun(actId: string) {
  if (!actId || (actId === currentActivityId.value && cardMode.value === "workout")) return;
  cardMode.value = "workout";
  currentActivityId.value = actId;
  currentRaceId.value = "";
  await fetchShareCardData(actId, undefined, "");
}

async function handleSelectRace(rId: string) {
  if (!rId || (rId === currentRaceId.value && cardMode.value === "race")) return;
  cardMode.value = "race";
  currentRaceId.value = rId;
  hasCustomSelectedPhoto.value = false;
  await fetchShareCardData("", undefined, rId);
}

function handleSelectCommentary(opt: { key: string; label: string; text: string }) {
  activeCommentaryKey.value = opt.key;
  customCommentary.value = opt.text;
  renderPosterCanvas();
}

function applyFocusPreset(preset: "auto" | "top" | "upper" | "center" | "bottom") {
  focusPreset.value = preset;
  if (preset === "auto") {
    photoFocusX.value = autoFocusX.value;
    photoFocusY.value = autoFocusY.value;
  } else if (preset === "top") {
    photoFocusY.value = 0.06;
  } else if (preset === "upper") {
    photoFocusY.value = 0.18;
  } else if (preset === "center") {
    photoFocusY.value = 0.5;
  } else if (preset === "bottom") {
    photoFocusY.value = 0.78;
  }
  renderPosterCanvas();
}

function handleFocusSliderChange(e: any) {
  const val = Number(e?.detail?.value ?? 18);
  focusPreset.value = "upper";
  photoFocusY.value = Math.max(0, Math.min(1, val / 100));
  renderPosterCanvas();
}

/**
 * Reads local image file as base64 and calls backend OpenCV face focus detector
 */
function detectFaceFocusFromLocalPath(localPath: string, imgW: number, imgH: number) {
  // Set immediate smart portrait default (0.18 for vertical portrait photos so head is never cropped)
  const initialY = imgH > imgW * 1.05 ? 0.16 : 0.26;
  photoFocusX.value = 0.5;
  photoFocusY.value = initialY;
  autoFocusX.value = 0.5;
  autoFocusY.value = initialY;
  faceDetected.value = false;
  focusPreset.value = "auto";

  // #ifdef MP-WEIXIN
  try {
    if (typeof wx !== "undefined" && wx.getFileSystemManager) {
      detectingFace.value = true;
      const fs = wx.getFileSystemManager();
      fs.readFile({
        filePath: localPath,
        encoding: "base64",
        success: async (fileRes: any) => {
          try {
            const b64 = fileRes.data;
            if (!b64) {
              detectingFace.value = false;
              return;
            }
            const res: any = await request("/api/miniapp/detect-face-focus", {
              method: "POST",
              data: { image_base64: b64 },
            });
            detectingFace.value = false;
            if (res && res.success) {
              autoFocusX.value = typeof res.focus_x === "number" ? res.focus_x : 0.5;
              autoFocusY.value = typeof res.focus_y === "number" ? res.focus_y : initialY;
              faceDetected.value = !!res.face_detected;
              if (focusPreset.value === "auto") {
                photoFocusX.value = autoFocusX.value;
                photoFocusY.value = autoFocusY.value;
                renderPosterCanvas();
              }
            }
          } catch (_) {
            detectingFace.value = false;
          }
        },
        fail: () => {
          detectingFace.value = false;
        },
      });
    }
  } catch (_) {
    detectingFace.value = false;
  }
  // #endif
}

function handleChoosePhoto() {
  uni.chooseImage({
    count: 1,
    sizeType: ["compressed", "original"],
    sourceType: ["album", "camera"],
    success: (res) => {
      const path = res.tempFilePaths?.[0];
      if (!path) return;
      hasCustomSelectedPhoto.value = true;
      uni.getImageInfo({
        src: path,
        success: (info) => {
          const finalPath = info.path || path;
          const w = info.width || 800;
          const h = info.height || 1000;
          userPhotoPath.value = finalPath;
          userPhotoWidth.value = w;
          userPhotoHeight.value = h;
          detectFaceFocusFromLocalPath(finalPath, w, h);
          renderPosterCanvas();
        },
        fail: () => {
          userPhotoPath.value = path;
          userPhotoWidth.value = 800;
          userPhotoHeight.value = 1000;
          detectFaceFocusFromLocalPath(path, 800, 1000);
          renderPosterCanvas();
        },
      });
    },
  });
}

function handleClearPhoto() {
  hasCustomSelectedPhoto.value = false;
  userPhotoPath.value = "";
  userPhotoWidth.value = 0;
  userPhotoHeight.value = 0;
  faceDetected.value = false;
  renderPosterCanvas();
}

async function fetchShareCardData(actId?: string, dateStr?: string, rId?: string) {
  const u = getStoredUser();
  const uid = props.targetUid || u?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录账号", icon: "none" });
    return;
  }

  loading.value = true;
  try {
    let envVer = "release";
    // #ifdef MP-WEIXIN
    try {
      if (typeof wx !== "undefined" && wx.getAccountInfoSync) {
        const acc = wx.getAccountInfoSync();
        envVer = acc?.miniProgram?.envVersion || "release";
      }
    } catch (_) {}
    // #endif

    const activeClubId = getActiveClubId() || "";
    const qs: string[] = [`env_version=${encodeURIComponent(envVer)}`];
    const viewerUid = getStoredUser()?.id || "";
    if (viewerUid) qs.push(`viewer_uid=${encodeURIComponent(viewerUid)}`);
    if (rId) {
      qs.push(`race_id=${encodeURIComponent(rId)}`);
    } else {
      if (actId) qs.push(`activity_id=${encodeURIComponent(actId)}`);
      if (dateStr) qs.push(`target_date=${encodeURIComponent(dateStr)}`);
    }
    if (activeClubId) qs.push(`club_id=${encodeURIComponent(activeClubId)}`);

    const res: any = await request(`/api/miniapp/personal-share-card/${encodeURIComponent(uid)}?${qs.join("&")}`);
    if (res && res.success) {
      shareData.value = res;
      recentRuns.value = res.recent_runs || [];
      completedRaces.value = res.completed_races || [];
      if (res.card_mode === "race" && res.selected_race?.id) {
        cardMode.value = "race";
        currentRaceId.value = String(res.selected_race.id);
      } else {
        cardMode.value = "workout";
        if (res.actual_data?.id) {
          currentActivityId.value = res.actual_data.id;
        }
      }

      // If in race mode and race has a saved photo (and user hasn't picked a manual override photo), auto-load it with face focus!
      if (res.card_mode === "race" && res.default_photo_base64 && !hasCustomSelectedPhoto.value) {
        const localRacePhoto = await writeBase64ToLocalFile(res.default_photo_base64, "psc_race_photo");
        if (localRacePhoto) {
          userPhotoPath.value = localRacePhoto;
          const df = res.default_photo_focus || {};
          userPhotoWidth.value = df.width || 800;
          userPhotoHeight.value = df.height || 1000;
          autoFocusX.value = typeof df.focus_x === "number" ? df.focus_x : 0.5;
          autoFocusY.value = typeof df.focus_y === "number" ? df.focus_y : 0.18;
          photoFocusX.value = autoFocusX.value;
          photoFocusY.value = autoFocusY.value;
          faceDetected.value = !!df.face_detected;
          focusPreset.value = "auto";
        }
      }

      const opts = res.commentary_options || [];
      commentaryOptions.value = opts;
      const defaultKey = showDailyPlan.value ? "exec" : "phys";
      const matchedOpt = opts.find((o: any) => o.key === defaultKey) || opts[0];
      activeCommentaryKey.value = matchedOpt?.key || "exec";
      customCommentary.value = matchedOpt?.text || res.canova_commentary || "";
      loading.value = false;
      await nextTick();
      setTimeout(() => {
        renderPosterCanvas();
      }, 80);
    } else {
      loading.value = false;
      uni.showToast({ title: "获取分享卡数据失败", icon: "none" });
    }
  } catch (e: any) {
    loading.value = false;
    console.error("fetchShareCardData error:", e);
    uni.showToast({ title: "加载分享数据失败", icon: "none" });
  }
}

function writeBase64ToLocalFile(b64: string, prefix: string): Promise<string> {
  return new Promise((resolve) => {
    if (!b64) {
      resolve("");
      return;
    }
    const cleanB64 = b64.replace(/^data:image\/\w+;base64,/, "").replace(/\s/g, "");
    // #ifdef MP-WEIXIN
    try {
      if (typeof wx !== "undefined" && wx.getFileSystemManager && wx.base64ToArrayBuffer) {
        const fs = wx.getFileSystemManager();
        const filePath = `${wx.env.USER_DATA_PATH}/${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}.jpg`;
        const buffer = wx.base64ToArrayBuffer(cleanB64);
        fs.writeFile({
          filePath,
          data: buffer,
          encoding: "binary",
          success: () => resolve(filePath),
          fail: () => resolve(""),
        });
        return;
      }
    } catch (_) {}
    // #endif
    resolve(`data:image/jpeg;base64,${cleanB64}`);
  });
}

function drawRoundedRect(
  ctx: any,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
  fillStyle?: string,
  strokeStyle?: string,
  lineWidth: number = 1
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
  if (fillStyle) {
    ctx.setFillStyle(fillStyle);
    ctx.fill();
  }
  if (strokeStyle) {
    ctx.setLineWidth(lineWidth);
    ctx.setStrokeStyle(strokeStyle);
    ctx.stroke();
  }
}

/**
 * Computes conservative visual width of text at a given fontSize so CJK/Emoji/ASCII never overflow on any device font.
 */
function getTextVisualWidth(ctx: any, text: string, fontSize: number): number {
  if (!text) return 0;
  let heuristicW = 0;
  for (const ch of Array.from(text)) {
    const code = ch.codePointAt(0) || 0;
    if (code > 0xffff) {
      heuristicW += fontSize * 1.22;
    } else if (
      (code >= 0x2e80 && code <= 0x9fff) ||
      (code >= 0xf900 && code <= 0xfaff) ||
      (code >= 0xff00 && code <= 0xffef) ||
      (code >= 0x3000 && code <= 0x303f)
    ) {
      heuristicW += fontSize * 1.03;
    } else {
      heuristicW += fontSize * 0.58;
    }
  }
  try {
    ctx.setFontSize(fontSize);
    const m = ctx.measureText(text);
    if (m && typeof m.width === "number" && m.width > 0) {
      return Math.max(m.width * 1.05, heuristicW);
    }
  } catch (_) {}
  return heuristicW;
}

/**
 * Automatically shrinks fontSize (from maxFontSize down to minFontSize) so `text` fits within `maxWidth`.
 * If still wider than `maxWidth` at `minFontSize`, cleanly truncates with "…" so text NEVER overflows its box.
 */
function drawFittedText(
  ctx: any,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  maxFontSize: number,
  minFontSize: number = 12
) {
  const clean = String(text || "").trim();
  if (!clean || maxWidth <= 10) return;

  let chosenSize = maxFontSize;
  while (chosenSize > minFontSize) {
    if (getTextVisualWidth(ctx, clean, chosenSize) <= maxWidth) {
      break;
    }
    chosenSize -= 1;
  }

  ctx.setFontSize(chosenSize);
  if (getTextVisualWidth(ctx, clean, chosenSize) <= maxWidth) {
    ctx.fillText(clean, x, y);
    return;
  }

  const chars = Array.from(clean);
  let out = "";
  for (let i = 0; i < chars.length; i++) {
    const candidate = out + chars[i];
    if (getTextVisualWidth(ctx, candidate + "…", chosenSize) > maxWidth) {
      break;
    }
    out = candidate;
  }
  ctx.fillText((out || chars[0] || "") + "…", x, y);
}

/**
 * Draws a right-aligned pill badge with horizontally centered text and returns the pill's left X coordinate.
 */
function drawRightAlignedPill(
  ctx: any,
  rightEdgeX: number,
  y: number,
  h: number,
  text: string,
  fontSize: number,
  bgFill: string,
  borderStroke: string,
  textColor: string,
  minW: number = 124
): number {
  const textW = getTextVisualWidth(ctx, text, fontSize);
  const pillW = Math.max(minW, Math.ceil(textW + 28));
  const pillX = rightEdgeX - pillW;
  drawRoundedRect(ctx, pillX, y, pillW, h, h / 2, bgFill, borderStroke, 1);
  ctx.setFontSize(fontSize);
  ctx.setFillStyle(textColor);
  const textX = pillX + Math.max(10, (pillW - textW) / 2);
  ctx.fillText(text, textX, y + h * 0.68);
  return pillX;
}

function drawWrappedText(
  ctx: any,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines: number = 5,
  fontSize: number = 19
): number {
  if (!text) return y;
  ctx.setFontSize(fontSize);
  const chars = Array.from(text);
  let line = "";
  let lineCount = 0;
  let curY = y;

  for (let i = 0; i < chars.length; i++) {
    const ch = chars[i];
    if (ch === "\n") {
      ctx.fillText(line, x, curY);
      line = "";
      curY += lineHeight;
      lineCount++;
      if (lineCount >= maxLines) return curY;
      continue;
    }
    const testLine = line + ch;
    const w = getTextVisualWidth(ctx, testLine, fontSize);
    if (w > maxWidth && line.length > 0) {
      if (lineCount === maxLines - 1) {
        ctx.fillText(line.slice(0, Math.max(1, line.length - 1)) + "…", x, curY);
        return curY + lineHeight;
      }
      ctx.fillText(line, x, curY);
      line = ch;
      curY += lineHeight;
      lineCount++;
    } else {
      line = testLine;
    }
  }
  if (line) {
    ctx.fillText(line, x, curY);
    curY += lineHeight;
  }
  return curY;
}

/**
 * Draws the GPS route polyline onto the canvas inside (boxX, boxY, boxW, boxH)
 */
function drawGpsRouteOnPhoto(
  ctx: any,
  rawPoints: Array<{ lat: number; lng: number }>,
  boxX: number,
  boxY: number,
  boxW: number,
  boxH: number,
  withHudCard: boolean,
  isLightBackdrop: boolean = false
) {
  if (!rawPoints || rawPoints.length < 2) return;

  if (withHudCard) {
    drawRoundedRect(
      ctx,
      boxX,
      boxY,
      boxW,
      boxH,
      18,
      isLightBackdrop ? "rgba(255, 255, 255, 0.90)" : "rgba(10, 14, 23, 0.58)",
      isLightBackdrop ? "rgba(252, 76, 2, 0.32)" : "rgba(208, 253, 62, 0.42)",
      1.5
    );
    ctx.setFontSize(15);
    ctx.setFillStyle(isLightBackdrop ? "#C23800" : "#d0fd3e");
    ctx.fillText("🗺️ GPS 运动轨迹", boxX + 14, boxY + 24);
  }

  const padL = withHudCard ? 18 : 30;
  const padR = withHudCard ? 18 : 30;
  const padT = withHudCard ? 36 : 30;
  const padB = withHudCard ? 18 : 30;

  const plotX = boxX + padL;
  const plotY = boxY + padT;
  const plotW = boxW - padL - padR;
  const plotH = boxH - padT - padB;

  const lats = rawPoints.map((p) => p.lat);
  const lngs = rawPoints.map((p) => p.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);

  const midLatRad = (((minLat + maxLat) / 2) * Math.PI) / 180;
  const cosLat = Math.max(0.4, Math.cos(midLatRad));

  const spanLat = Math.max(0.0005, maxLat - minLat);
  const spanLng = Math.max(0.0005, (maxLng - minLng) * cosLat);

  const scale = Math.min(plotW / spanLng, plotH / spanLat);
  const renderedW = spanLng * scale;
  const renderedH = spanLat * scale;
  const offsetX = plotX + (plotW - renderedW) / 2;
  const offsetY = plotY + (plotH - renderedH) / 2;

  const pts = rawPoints.map((p) => ({
    x: offsetX + (p.lng - minLng) * cosLat * scale,
    y: offsetY + (maxLat - p.lat) * scale,
  }));

  if (pts.length < 2) return;

  ctx.save();
  ctx.beginPath();
  pts.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.setLineCap("round");
  ctx.setLineJoin("round");
  ctx.setLineWidth(withHudCard ? 8 : 13);
  ctx.setStrokeStyle("rgba(252, 76, 2, 0.34)");
  ctx.stroke();

  ctx.beginPath();
  pts.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.setLineWidth(withHudCard ? 3.8 : 6);
  ctx.setStrokeStyle("#fc4c02");
  ctx.stroke();

  ctx.beginPath();
  pts.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.setLineWidth(withHudCard ? 1.4 : 2.2);
  ctx.setStrokeStyle("#d0fd3e");
  ctx.stroke();

  const startPt = pts[0];
  const endPt = pts[pts.length - 1];

  ctx.beginPath();
  ctx.arc(startPt.x, startPt.y, withHudCard ? 5 : 7.5, 0, Math.PI * 2);
  ctx.setFillStyle("#10b981");
  ctx.fill();
  ctx.setLineWidth(2);
  ctx.setStrokeStyle("#ffffff");
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(endPt.x, endPt.y, withHudCard ? 5.5 : 8, 0, Math.PI * 2);
  ctx.setFillStyle("#fc4c02");
  ctx.fill();
  ctx.setLineWidth(2);
  ctx.setStrokeStyle("#ffffff");
  ctx.stroke();
  ctx.restore();
}

/**
 * Draws the Elevation Profile mountain curve at the bottom of the Hero Photo
 */
function drawElevationOnPhoto(
  ctx: any,
  elevProfile: Array<{ dist_km: number; elevation_m: number }>,
  elevGainM: number,
  boxX: number,
  boxY: number,
  boxW: number,
  boxH: number,
  isLightBackdrop: boolean = false
) {
  if (!elevProfile || elevProfile.length < 2) return;

  const elevs = elevProfile.map((e) => e.elevation_m);
  const minE = Math.min(...elevs);
  const maxE = Math.max(...elevs);
  const diffE = Math.max(8, maxE - minE);
  const totalDist = Math.max(0.1, elevProfile[elevProfile.length - 1].dist_km || 1);

  ctx.setFontSize(15);
  ctx.setFillStyle(isLightBackdrop ? "#0369a1" : "#38bdf8");
  ctx.fillText(
    `⛰️ 海拔剖面 · 累计爬升 +${Math.round(elevGainM)}m · 最高 ${Math.round(maxE)}m`,
    boxX + 16,
    boxY + 20
  );

  const chartL = boxX + 16;
  const chartR = boxX + boxW - 16;
  const chartT = boxY + 32;
  const chartB = boxY + boxH - 22;
  const chartW = chartR - chartL;
  const chartH = chartB - chartT;

  let peakPt = { x: chartL, y: chartT, elev: elevProfile[0].elevation_m };
  const pts = elevProfile.map((item, idx) => {
    const ratioX = totalDist > 0 ? item.dist_km / totalDist : idx / (elevProfile.length - 1);
    const x = chartL + Math.max(0, Math.min(1, ratioX)) * chartW;
    const y = chartB - ((item.elevation_m - minE) / diffE) * chartH;
    if (item.elevation_m >= peakPt.elev) {
      peakPt = { x, y, elev: item.elevation_m };
    }
    return { x, y };
  });

  ctx.save();
  ctx.beginPath();
  ctx.moveTo(pts[0].x, chartB);
  pts.forEach((p) => ctx.lineTo(p.x, p.y));
  ctx.lineTo(pts[pts.length - 1].x, chartB);
  ctx.closePath();
  const grad = ctx.createLinearGradient(0, chartT, 0, chartB);
  grad.addColorStop(0, isLightBackdrop ? "rgba(2, 132, 199, 0.28)" : "rgba(56, 189, 248, 0.42)");
  grad.addColorStop(1, isLightBackdrop ? "rgba(2, 132, 199, 0.03)" : "rgba(56, 189, 248, 0.04)");
  ctx.setFillStyle(grad);
  ctx.fill();

  ctx.beginPath();
  pts.forEach((p, idx) => {
    if (idx === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.setLineWidth(3);
  ctx.setLineCap("round");
  ctx.setLineJoin("round");
  ctx.setStrokeStyle(isLightBackdrop ? "#0284c7" : "#38bdf8");
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(peakPt.x, peakPt.y, 4.5, 0, Math.PI * 2);
  ctx.setFillStyle(isLightBackdrop ? "#FC4C02" : "#d0fd3e");
  ctx.fill();
  ctx.setLineWidth(1.5);
  ctx.setStrokeStyle(isLightBackdrop ? "#ffffff" : "#090b10");
  ctx.stroke();

  const peakLabelX = Math.max(chartL + 36, Math.min(chartR - 36, peakPt.x));
  ctx.setFontSize(14);
  ctx.setFillStyle(isLightBackdrop ? "#C23800" : "#d0fd3e");
  ctx.fillText(`▲${Math.round(peakPt.elev)}m`, peakLabelX - 24, Math.max(chartT + 12, peakPt.y - 8));

  ctx.setFontSize(14);
  ctx.setFillStyle(isLightBackdrop ? "#4b5667" : "rgba(255, 255, 255, 0.72)");
  ctx.fillText("0 km", chartL, boxY + boxH - 4);
  ctx.fillText(`${(totalDist / 2).toFixed(1)} km`, chartL + chartW / 2 - 22, boxY + boxH - 4);
  ctx.fillText(`${totalDist.toFixed(2)} km`, chartR - 56, boxY + boxH - 4);
  ctx.restore();
}

async function renderPosterCanvas() {
  if (!shareData.value) return;
  rendering.value = true;

  try {
    const d = shareData.value;
    const usr = d.user || {};
    const plan = d.day_plan || {};
    const act = d.actual_data || {};
    const trk = d.track_overlay || {};
    const isRace = !!(plan.is_race || d.card_mode === "race");

    const [qrLocalPath, avatarLocalPath] = await Promise.all([
      writeBase64ToLocalFile(d.qrcode_base64 || "", "psc_qr"),
      writeBase64ToLocalFile(usr.avatar_base64 || "", "psc_av"),
    ]);

    const W = 750;
    const H = 1460;
    const isLight = isVolt.value;
    const isLightHero = isLight && !userPhotoPath.value;
    const ctx = uni.createCanvasContext("personalSharePosterCanvas", instance?.proxy);

    // 0. Full Poster Background
    ctx.setFillStyle(isLight ? "#F6F8FA" : "#090B10");
    ctx.fillRect(0, 0, W, H);

    // Subtle Top Ambient Glow
    const bgGrad = ctx.createLinearGradient(0, 0, W, 420);
    if (isLight) {
      bgGrad.addColorStop(0, isRace ? "#FEF3C7" : "#FFF5EE");
      bgGrad.addColorStop(0.5, "#F8FAFC");
      bgGrad.addColorStop(1, "#F6F8FA");
    } else {
      bgGrad.addColorStop(0, isRace ? "#261b0e" : "#1c1318");
      bgGrad.addColorStop(0.5, "#101624");
      bgGrad.addColorStop(1, "#090B10");
    }
    ctx.setFillStyle(bgGrad);
    ctx.fillRect(0, 0, W, 420);

    // Outer Card Border Frame
    drawRoundedRect(
      ctx,
      24,
      24,
      W - 48,
      H - 48,
      30,
      isLight ? "#ffffff" : "#0E1118",
      isLight
        ? "#E2E8F0"
        : isRace
        ? "rgba(251, 191, 36, 0.25)"
        : "rgba(255, 255, 255, 0.12)",
      1.5
    );

    // ── SECTION 1: Runner & Club Header (Y: 46 -> 122) ──
    const avX = 52;
    const avY = 48;
    const avSize = 64;
    if (avatarLocalPath) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(avX + avSize / 2, avY + avSize / 2, avSize / 2, 0, Math.PI * 2);
      ctx.clip();
      ctx.drawImage(avatarLocalPath, avX, avY, avSize, avSize);
      ctx.restore();
      ctx.beginPath();
      ctx.arc(avX + avSize / 2, avY + avSize / 2, avSize / 2, 0, Math.PI * 2);
      ctx.setLineWidth(2);
      ctx.setStrokeStyle(isRace ? (isLight ? "#d97706" : "#fbbf24") : "#fc4c02");
      ctx.stroke();
    } else {
      drawRoundedRect(ctx, avX, avY, avSize, avSize, 32, isRace ? "#f59e0b" : "#fc4c02");
      ctx.setFontSize(28);
      ctx.setFillStyle("#ffffff");
      const firstChar = String(usr.display_name || "跑").slice(0, 1);
      ctx.fillText(firstChar, avX + 18, avY + 42);
    }

    // Runner Name & Club Pill
    const runnerName = String(usr.display_name || "跑者").slice(0, 10);
    ctx.setFontSize(26);
    ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
    ctx.fillText(runnerName, 132, 76);

    const clubName = String(usr.club_name || "万跑跑团助手").slice(0, 14);
    const clubLabel = `${isRace ? "🏅" : "🏃"} ${clubName}`;
    const nameW = Math.min(200, Math.ceil(getTextVisualWidth(ctx, runnerName, 26) + 18));
    const clubTextW = getTextVisualWidth(ctx, clubLabel, 15);
    const clubPillW = Math.min(250, Math.ceil(clubTextW + 28));
    const clubPillX = 132 + nameW;
    drawRoundedRect(
      ctx,
      clubPillX,
      50,
      clubPillW,
      32,
      16,
      isRace
        ? isLight
          ? "#fef3c7"
          : "rgba(251, 191, 36, 0.16)"
        : isLight
        ? "#FFF5EE"
        : "rgba(252, 76, 2, 0.16)",
      isRace
        ? isLight
          ? "rgba(217, 119, 6, 0.45)"
          : "rgba(251, 191, 36, 0.48)"
        : isLight
        ? "rgba(252, 76, 2, 0.32)"
        : "rgba(252, 76, 2, 0.45)",
      1
    );
    ctx.setFillStyle(isRace ? (isLight ? "#b45309" : "#fbbf24") : isLight ? "#C23800" : "#fc4c02");
    drawFittedText(ctx, clubLabel, clubPillX + 14, 72, clubPillW - 24, 15, 12);

    ctx.setFontSize(18);
    ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
    ctx.fillText(
      isRace ? "万跑跑团助手 · 官方完赛纪念战报" : "万跑跑团助手 · 每日运动打卡",
      132,
      106
    );

    // Date Badge on Top Right
    const dateLabel = String(act.date || plan.date || "").replace(/-/g, ".");
    ctx.setFontSize(20);
    ctx.setFillStyle(isRace ? (isLight ? "#b45309" : "#fbbf24") : isLight ? "#FC4C02" : "#d0fd3e");
    ctx.fillText(dateLabel, W - 168, 78);
    ctx.setFontSize(15);
    ctx.setFillStyle(isRace ? (isLight ? "#d97706" : "#f59e0b") : isLight ? "#64748b" : "#71717a");
    ctx.fillText(isRace ? "🏅 完赛荣誉" : "训练日志", W - 134, 104);

    // ── SECTION 2: User Photo + Smart Face Centering + GPS Map & Elevation Overlay ──
    const pX = 52;
    const pY = 130;
    const pW = W - 104; // 646
    const pH = showDailyPlan.value ? 480 : 586;

    ctx.save();
    drawRoundedRect(ctx, pX, pY, pW, pH, 24, isLightHero ? "#F8FAFC" : "#141926");
    ctx.clip();

    if (userPhotoPath.value) {
      // Smart Face-Centered AspectFill Cropping:
      // Aligns detected face / head focus point (photoFocusX, photoFocusY) to the clear upper-middle sweet spot (0.48, 0.28)
      // of the Hero Box so vertical portrait photos never cut off the runner's head!
      let drawX = pX;
      let drawY = pY;
      let drawW = pW;
      let drawH = pH;
      if (userPhotoWidth.value > 0 && userPhotoHeight.value > 0) {
        const scale = Math.max(pW / userPhotoWidth.value, pH / userPhotoHeight.value);
        drawW = userPhotoWidth.value * scale;
        drawH = userPhotoHeight.value * scale;
        const targetBoxX = 0.48;
        const targetBoxY = 0.28;
        const idealDrawX = pX + pW * targetBoxX - drawW * photoFocusX.value;
        const idealDrawY = pY + pH * targetBoxY - drawH * photoFocusY.value;
        drawX = Math.min(pX, Math.max(pX + pW - drawW, idealDrawX));
        drawY = Math.min(pY, Math.max(pY + pH - drawH, idealDrawY));
      }
      ctx.drawImage(userPhotoPath.value, drawX, drawY, drawW, drawH);
    } else {
      // Default Sleek Athletic Stadium Hero Backdrop
      const heroGrad = ctx.createLinearGradient(pX, pY, pX + pW, pY + pH);
      if (isLightHero) {
        heroGrad.addColorStop(0, isRace ? "#FEF3C7" : "#FFF5EE");
        heroGrad.addColorStop(0.55, "#F8FAFC");
        heroGrad.addColorStop(1, "#F1F5F9");
      } else {
        heroGrad.addColorStop(0, isRace ? "#271e12" : "#192236");
        heroGrad.addColorStop(0.5, "#111827");
        heroGrad.addColorStop(1, "#1e152a");
      }
      ctx.setFillStyle(heroGrad);
      ctx.fillRect(pX, pY, pW, pH);

      ctx.setStrokeStyle(isLightHero ? "rgba(15, 23, 42, 0.04)" : "rgba(255, 255, 255, 0.04)");
      ctx.setLineWidth(1);
      for (let gx = pX + 60; gx < pX + pW; gx += 80) {
        ctx.beginPath();
        ctx.moveTo(gx, pY);
        ctx.lineTo(gx, pY + pH);
        ctx.stroke();
      }
      for (let gy = pY + 60; gy < pY + pH; gy += 80) {
        ctx.beginPath();
        ctx.moveTo(pX, gy);
        ctx.lineTo(pX + pW, gy);
        ctx.stroke();
      }
    }

    // Subtle Top & Bottom Gradient Vignettes on Photo for HUD Readability
    if (!isLightHero) {
      const topVig = ctx.createLinearGradient(0, pY, 0, pY + 100);
      topVig.addColorStop(0, userPhotoPath.value ? "rgba(9, 11, 16, 0.42)" : "rgba(9, 11, 16, 0.72)");
      topVig.addColorStop(1, "rgba(9, 11, 16, 0.0)");
      ctx.setFillStyle(topVig);
      ctx.fillRect(pX, pY, pW, 100);

      const botVig = ctx.createLinearGradient(0, pY + pH - 235, 0, pY + pH);
      botVig.addColorStop(0, "rgba(9, 11, 16, 0.0)");
      botVig.addColorStop(0.45, "rgba(9, 11, 16, 0.64)");
      botVig.addColorStop(1, "rgba(9, 11, 16, 0.92)");
      ctx.setFillStyle(botVig);
      ctx.fillRect(pX, pY + pH - 235, pW, 235);
    }

    // Top-Left Compact Pill: Activity / Race Title
    const titleLabelStr = `${isRace ? "🏅" : "🏃"} ${String(act.name || "户外跑步").slice(0, 18)}`;
    const actPillTextW = getTextVisualWidth(ctx, titleLabelStr, 15);
    const actPillW = Math.min(340, Math.max(120, Math.ceil(actPillTextW + 30)));
    drawRoundedRect(
      ctx,
      pX + 18,
      pY + 18,
      actPillW,
      34,
      17,
      isLightHero ? "rgba(255, 255, 255, 0.92)" : "rgba(15, 18, 28, 0.62)",
      isLightHero
        ? isRace
          ? "rgba(217, 119, 6, 0.45)"
          : "#E2E8F0"
        : isRace
        ? "rgba(251, 191, 36, 0.35)"
        : "rgba(255, 255, 255, 0.18)",
      1
    );
    ctx.setFillStyle(isLightHero ? (isRace ? "#b45309" : "#0F172A") : isRace ? "#fde68a" : "#ffffff");
    drawFittedText(ctx, titleLabelStr, pX + 32, pY + 40, actPillW - 26, 15, 12);

    // Position the Big Distance + Pace Stamp so that when a portrait photo is loaded, the upper-left/center face region stays 100% clear!
    const hasBottomElev =
      (overlayMode.value === "both" || overlayMode.value === "elevation") &&
      Array.isArray(trk.elevation_profile) &&
      trk.elevation_profile.length >= 2;
    const stampBaseY = userPhotoPath.value
      ? (hasBottomElev ? pY + pH - 168 : pY + pH - 52)
      : pY + 122;

    ctx.setFontSize(64);
    ctx.setFillStyle(isLightHero ? (isRace ? "#b45309" : "#FC4C02") : isRace ? "#fbbf24" : "#d0fd3e");
    const distStr = Number(act.distance_km || 0).toFixed(2);
    ctx.fillText(distStr, pX + 22, stampBaseY);
    const distTextW = distStr.length * 38;
    ctx.setFontSize(22);
    ctx.setFillStyle(isLightHero ? "#0F172A" : "#ffffff");
    ctx.fillText("KM", pX + 26 + distTextW, stampBaseY - 2);

    ctx.setFillStyle(isLightHero ? "#475569" : "rgba(255, 255, 255, 0.92)");
    const subMetricLine = isRace
      ? `完赛净成绩 ${act.duration_str || "—"}  ·  平均配速 ${act.avg_pace_str || "—"}/km`
      : `平均配速 ${act.avg_pace_str || "—"}/km  ·  用时 ${act.duration_str || "00:00"}`;
    drawFittedText(ctx, subMetricLine, pX + 24, stampBaseY + 28, pW - 48, 18, 13);

    // Overlay GPS Track Map on Photo
    if (overlayMode.value === "both" || overlayMode.value === "map") {
      if (trackPosition.value === "corner" && overlayMode.value === "both") {
        // Compact floating HUD card in top-right (leaves center portrait & face completely clear)
        drawGpsRouteOnPhoto(ctx, trk.points || [], pX + pW - 214, pY + 18, 196, 178, true, isLightHero);
      } else if (trackPosition.value === "corner" && overlayMode.value === "map") {
        drawGpsRouteOnPhoto(ctx, trk.points || [], pX + pW - 246, pY + 20, 226, 216, true, isLightHero);
      } else {
        const extraHeroH = showDailyPlan.value ? 0 : 70;
        drawGpsRouteOnPhoto(
          ctx,
          trk.points || [],
          pX + 120,
          pY + (overlayMode.value === "both" ? 130 : 155),
          pW - 240,
          (overlayMode.value === "both" ? 210 : 280) + extraHeroH,
          false,
          isLightHero
        );
      }
    }

    // Overlay Elevation Profile Curve on Bottom of Photo
    if (overlayMode.value === "both" || overlayMode.value === "elevation") {
      const elevBoxH = overlayMode.value === "elevation" ? 160 : 132;
      drawElevationOnPhoto(
        ctx,
        trk.elevation_profile || [],
        Number(act.elevation_gain_meters || trk.elevation_gain_m || 0),
        pX + 8,
        pY + pH - elevBoxH - 6,
        pW - 16,
        elevBoxH,
        isLightHero
      );
    }

    ctx.restore();
    // Photo Outer Border
    drawRoundedRect(
      ctx,
      pX,
      pY,
      pW,
      pH,
      24,
      undefined,
      isLight
        ? "#E2E8F0"
        : isRace
        ? "rgba(251, 191, 36, 0.28)"
        : "rgba(255, 255, 255, 0.16)",
      1.5
    );

    // ── SECTION 3A: Today's Plan OR Race Target (Optional via showDailyPlan) ──
    if (showDailyPlan.value) {
      const planY = 626;
      const planH = 122;
      const planAccent = isRace ? (isLight ? "#b45309" : "#fbbf24") : isLight ? "#FC4C02" : "#38bdf8";

      ctx.save();
      drawRoundedRect(
        ctx,
        pX,
        planY,
        pW,
        planH,
        18,
        isLight ? "#F8FAFC" : "#121826",
        isLight
          ? "#E2E8F0"
          : isRace
          ? "rgba(251, 191, 36, 0.42)"
          : "rgba(56, 189, 248, 0.38)",
        1.5
      );
      ctx.clip();
      drawRoundedRect(ctx, pX, planY + 18, 6, planH - 36, 3, planAccent);

      // Completion Rate / Race Achievement Badge on Right of Plan Card (drawn first to get exact left boundary)
      const compPct = Number(act.completion_pct || 0);
      const rightBadgeText = isRace && plan.badge_text ? String(plan.badge_text) : `达成率 ${compPct}%`;
      const badgeColor = isRace
        ? isLight ? "#b45309" : "#fbbf24"
        : isLight
        ? "#059669"
        : compPct >= 95
        ? "#10b981"
        : compPct >= 70
        ? "#38bdf8"
        : "#f59e0b";
      const badgeBg = isRace
        ? "rgba(251, 191, 36, 0.16)"
        : isLight
        ? "#ECFDF5"
        : compPct >= 95
        ? "rgba(16, 185, 129, 0.16)"
        : compPct >= 70
        ? "rgba(56, 189, 248, 0.16)"
        : "rgba(245, 158, 11, 0.16)";
      const badgeLeftX = drawRightAlignedPill(
        ctx,
        pX + pW - 18,
        planY + 16,
        34,
        rightBadgeText,
        15,
        badgeBg,
        isLight ? "rgba(16, 185, 129, 0.35)" : badgeColor,
        badgeColor,
        122
      );

      const rawPlanTitle = String(plan.title || (isRace ? "马拉松赛事" : "有氧耐力跑")).trim();
      const headerPrefix = plan.card_header_label || (isRace ? "🏁 赛前目标" : "📋 当天计划");
      const planTitleText = `${headerPrefix}：${rawPlanTitle}`;
      ctx.setFillStyle(isLight ? "#0F172A" : planAccent);
      drawFittedText(ctx, planTitleText, pX + 24, planY + 41, badgeLeftX - (pX + 24) - 14, 21, 14);

      // Plan Targets Row (smartly compact long descriptive pace/HR strings & auto-fit width inside box)
      let cleanPace = String(plan.target_pace || "稳态有氧")
        .replace(/^(目标配速|配速|执行)[:：\s]*/g, "")
        .trim();
      if (cleanPace.length > 14 && /[，,；;]/.test(cleanPace)) {
        cleanPace = cleanPace.split(/[，,；;]/)[0].trim();
      }
      let cleanHrZone = String(plan.target_hr_zone || "Zone 2")
        .replace(/^(目标心率|心率|控制在)[:：\s]*/g, "")
        .trim();
      if (cleanHrZone.length > 14 && /[，,；;]/.test(cleanHrZone)) {
        cleanHrZone = cleanHrZone.split(/[，,；;]/)[0].trim();
      }

      const planSpecs = isRace
        ? `赛程距离 ${plan.distance_km || 0} km  |  ${plan.target_pace || "目标完赛"}  |  ${plan.target_hr_zone || ""}`
        : `目标距离 ${plan.distance_km || 0} km  |  目标配速 ${cleanPace}  |  心率 ${cleanHrZone}`;
      ctx.setFillStyle(isLight ? "#334155" : "#d4d4d8");
      drawFittedText(ctx, planSpecs, pX + 24, planY + 79, pW - 48, 17, 12);

      // Plan Subtitle Row (deduplicate phase/week_title and auto-fit without mid-word cutoffs)
      const pTitleStr = String(plan.plan_title || "").trim();
      const pPhaseStr = String(plan.phase || "").trim();
      const pWeekStr = String(plan.week_title || "").trim();
      let planDescFull = pTitleStr;
      if (pPhaseStr && !pWeekStr.includes(pPhaseStr) && !pTitleStr.includes(pPhaseStr)) {
        planDescFull += ` · ${pPhaseStr}`;
      }
      if (pWeekStr && !pTitleStr.includes(pWeekStr)) {
        planDescFull += ` · ${pWeekStr}`;
      }
      ctx.setFillStyle(isLight ? "#64748B" : "#9ca3af");
      drawFittedText(ctx, planDescFull, pX + 24, planY + 107, pW - 48, 15, 11);
      ctx.restore();
    }

    // ── SECTION 3B: Actual Completed Data (⚡ 实际完成数据 / 🏅 完赛核心数据) ──
    const actY = showDailyPlan.value ? 762 : 732;
    const actH = showDailyPlan.value ? 180 : 184;
    ctx.save();
    drawRoundedRect(
      ctx,
      pX,
      actY,
      pW,
      actH,
      18,
      isLight ? "#F8FAFC" : "#151621",
      isLight ? "#E2E8F0" : "rgba(252, 76, 2, 0.35)",
      1.5
    );
    ctx.clip();

    ctx.setFontSize(20);
    ctx.setFillStyle(isLight ? "#C23800" : "#fc4c02");
    ctx.fillText(isRace ? "🏅 完赛核心战绩" : "⚡ 实际完成数据", pX + 22, actY + 36);

    const trimpLabel = isRace
      ? `完赛净时 ${act.duration_str || "—"}`
      : act.trimp
      ? `TRIMP 训练负荷 ${act.trimp}`
      : `消耗 ${act.calories || "—"} kcal`;
    const trimpW = getTextVisualWidth(ctx, trimpLabel, 15);
    ctx.setFontSize(15);
    ctx.setFillStyle(isLight ? "#64748B" : "#9ca3af");
    ctx.fillText(trimpLabel, pX + pW - 22 - trimpW, actY + 36);

    // 4-Column Metric Grid
    const colW = (pW - 44 - 36) / 4;
    const metrics = [
      {
        label: isRace ? "完赛距离" : "实际距离",
        val: `${Number(act.distance_km || 0).toFixed(2)}`,
        unit: "km",
        color: isLight ? "#FC4C02" : "#d0fd3e",
      },
      {
        label: "平均配速",
        val: `${act.avg_pace_str || "—"}`,
        unit: "/km",
        color: isLight ? "#0F172A" : "#ffffff",
      },
      {
        label: "平均心率",
        val: `${act.average_heartrate || "—"}`,
        unit: "bpm",
        color: isLight ? "#0F172A" : "#fb7185",
      },
      {
        label: "累计爬升",
        val: `+${Math.round(Number(act.elevation_gain_meters || 0))}`,
        unit: "m",
        color: isLight ? "#0F172A" : "#38bdf8",
      },
    ];

    metrics.forEach((m, idx) => {
      const mx = pX + 22 + idx * (colW + 12);
      const my = actY + 52;
      drawRoundedRect(
        ctx,
        mx,
        my,
        colW,
        110,
        14,
        isLight ? "#ffffff" : "#1C1E2B",
        isLight ? "#e2e8f0" : "rgba(255, 255, 255, 0.06)",
        1
      );
      ctx.setFontSize(15);
      ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
      ctx.fillText(m.label, mx + 14, my + 30);

      ctx.setFillStyle(m.color);
      drawFittedText(ctx, m.val, mx + 14, my + 74, colW - 24, 28, 18);

      ctx.setFontSize(14);
      ctx.setFillStyle(isLight ? "#94A3B8" : "#71717a");
      ctx.fillText(m.unit, mx + 14, my + 98);
    });
    ctx.restore();

    // ── SECTION 4: Canova Coach's Commentary (👨‍🏫 Canova 教练点评) ──
    const cY = showDailyPlan.value ? 956 : 932;
    const cH = showDailyPlan.value ? 254 : 276;
    ctx.save();
    drawRoundedRect(
      ctx,
      pX,
      cY,
      pW,
      cH,
      20,
      isLight ? "#F8FAFC" : "#171426",
      isLight ? "#E2E8F0" : "rgba(191, 90, 242, 0.45)",
      1.5
    );
    ctx.clip();

    const verdictText = String(d.verdict_badge || (isRace ? "荣耀完赛 · 科学兑现" : "科学耐力周期复盘")).slice(0, 12);
    const verdictLeftX = drawRightAlignedPill(
      ctx,
      pX + pW - 18,
      cY + 16,
      32,
      verdictText,
      14,
      isLight ? "#FFF5EE" : "rgba(192, 132, 252, 0.15)",
      isLight ? "rgba(252, 76, 2, 0.30)" : "rgba(192, 132, 252, 0.35)",
      isLight ? "#C23800" : "#e9d5ff",
      148
    );

    ctx.setFillStyle(isLight ? "#0F172A" : "#c084fc");
    drawFittedText(
      ctx,
      isRace ? "👨‍🏫 Canova 教练完赛点评" : "👨‍🏫 Canova 教练点评",
      pX + 24,
      cY + 40,
      verdictLeftX - (pX + 24) - 14,
      22,
      16
    );

    const finalCommentary = (customCommentary.value || d.canova_commentary || "").trim();
    if (finalCommentary) {
      ctx.setFillStyle(isLight ? "#334155" : "#e4e4e7");
      drawWrappedText(ctx, `“${finalCommentary}”`, pX + 24, cY + 80, pW - 52, 33, showDailyPlan.value ? 5 : 6, 18);
    } else if (d.is_critique_hidden) {
      ctx.setFillStyle(isLight ? "#64748B" : "#94a3b8");
      drawWrappedText(
        ctx,
        "🔒 该跑者已将 Canova 教练评语设为仅自己或特定范围可见",
        pX + 24,
        cY + 84,
        pW - 52,
        33,
        2,
        18
      );
    }
    ctx.restore();

    // ── SECTION 5: Invitation QR Code Footer (邀请二维码, Y: 1224 -> 1412, H: 188) ──
    const fY = 1224;
    const fH = 188;
    ctx.save();
    drawRoundedRect(
      ctx,
      pX,
      fY,
      pW,
      fH,
      22,
      isLight ? "#f8fafc" : "#121622",
      isLight ? "#e2e8f0" : "rgba(255, 255, 255, 0.12)",
      1.5
    );
    ctx.clip();

    const qrBoxX = pX + pW - 162;
    const qrBoxY = fY + 18;
    const qrBoxSize = 132;
    const footerLeftMaxW = qrBoxX - (pX + 24) - 16;

    ctx.setFillStyle(isLight ? "#FC4C02" : "#fc4c02");
    drawFittedText(ctx, "🏅 万跑跑团助手 · 科学耐力训练系统", pX + 24, fY + 40, footerLeftMaxW, 18, 14);

    ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
    drawFittedText(ctx, `${runnerName} 邀你一起科学奔跑`, pX + 24, fY + 80, footerLeftMaxW, 25, 18);

    ctx.setFillStyle(isLight ? "#475569" : "#a1a1aa");
    drawFittedText(ctx, `长按识别小程序码 · 加入【${clubName}】`, pX + 24, fY + 116, footerLeftMaxW, 18, 13);

    ctx.setFillStyle(isLight ? "#64748B" : "#38bdf8");
    drawFittedText(ctx, "⌚ 佳明/高驰手表自动同步  ·  📈 Canova 专属计划", pX + 24, fY + 152, footerLeftMaxW, 16, 12);

    // Right QR Code Container
    drawRoundedRect(ctx, qrBoxX, qrBoxY, qrBoxSize, qrBoxSize, 14, "#ffffff", isLight ? "#e2e8f0" : undefined);

    if (qrLocalPath) {
      ctx.drawImage(qrLocalPath, qrBoxX + 6, qrBoxY + 6, qrBoxSize - 12, qrBoxSize - 12);
    } else {
      ctx.setFontSize(16);
      ctx.setFillStyle("#18181b");
      ctx.fillText("万跑跑团助手", qrBoxX + 18, qrBoxY + 70);
    }

    ctx.setFontSize(14);
    ctx.setFillStyle(isLight ? "#C23800" : "#d0fd3e");
    const qrCap = "长按扫码受邀入团";
    const qrCapW = getTextVisualWidth(ctx, qrCap, 14);
    ctx.fillText(qrCap, qrBoxX + Math.max(0, (qrBoxSize - qrCapW) / 2), fY + 172);
    ctx.restore();

    ctx.draw(false, () => {
      setTimeout(() => {
        uni.canvasToTempFilePath(
          {
            canvasId: "personalSharePosterCanvas",
            destWidth: W * 2,
            destHeight: H * 2,
            fileType: "jpg",
            quality: 0.92,
            success: (res) => {
              posterImageUrl.value = res.tempFilePath;
              rendering.value = false;
            },
            fail: (err) => {
              console.error("canvasToTempFilePath error:", err);
              rendering.value = false;
              uni.showToast({ title: "生成卡片失败，请重试", icon: "none" });
            },
          },
          instance?.proxy
        );
      }, 220);
    });
  } catch (e) {
    console.error("renderPosterCanvas error:", e);
    rendering.value = false;
  }
}

function handlePreviewFullImage() {
  if (!posterImageUrl.value) return;
  uni.previewImage({
    current: posterImageUrl.value,
    urls: [posterImageUrl.value],
  });
}

function handleSaveToAlbum() {
  if (!posterImageUrl.value) return;
  trackModal("share_card", "保存朋友圈战报海报到相册", "submit", { mode: cardMode.value });
  uni.showLoading({ title: "正在保存到相册..." });
  uni.saveImageToPhotosAlbum({
    filePath: posterImageUrl.value,
    success: () => {
      uni.hideLoading();
      uni.showToast({
        title: "已保存到相册，快去发朋友圈吧！",
        icon: "success",
        duration: 2800,
      });
    },
    fail: () => {
      uni.hideLoading();
      uni.previewImage({
        current: posterImageUrl.value,
        urls: [posterImageUrl.value],
      });
      uni.showToast({
        title: "请长按图片保存到手机相册",
        icon: "none",
        duration: 3000,
      });
    },
  });
}

function handleShareImage() {
  if (!posterImageUrl.value) return;
  // #ifdef MP-WEIXIN
  if (typeof wx !== "undefined" && (wx as any).showShareImageMenu) {
    (wx as any).showShareImageMenu({
      path: posterImageUrl.value,
      fail: () => {
        handlePreviewFullImage();
      },
    });
    return;
  }
  // #endif
  handlePreviewFullImage();
}
</script>

<style scoped>
.psc-mask {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.82);
  z-index: 10050;
  display: flex;
  align-items: center;
  align-items: center;
  justify-content: center;
  padding: 24rpx;
}

.psc-dialog {
  width: 100%;
  max-width: 700rpx;
  max-height: 85vh;
  background: #12151e;
  border: 1rpx solid rgba(255, 255, 255, 0.14);
  border-radius: 32rpx;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24rpx 64rpx rgba(0, 0, 0, 0.65);
}

.psc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 28rpx 18rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
}

.psc-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}

.psc-title {
  font-size: 30rpx;
  font-weight: 800;
  color: #ffffff;
}

.psc-close {
  width: 56rpx;
  height: 56rpx;
  border-radius: 28rpx;
  background: rgba(255, 255, 255, 0.08);
  color: #d4d4d8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28rpx;
}

.psc-scroll {
  flex: 1;
  min-height: 0;
  max-height: 62vh;
  padding: 20rpx 24rpx;
  box-sizing: border-box;
}

.psc-controls-card {
  background: #181c28;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 22rpx;
  padding: 20rpx;
  margin-bottom: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.psc-photo-bar {
  display: flex;
  gap: 16rpx;
}

.psc-photo-btn {
  flex: 1;
  height: 72rpx;
  border-radius: 16rpx;
  font-size: 25rpx;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  margin: 0;
}

.psc-photo-btn.primary {
  background: linear-gradient(135deg, #fc4c02, #ff7a00);
  color: #ffffff;
  border: none;
}

.psc-photo-btn.ghost {
  flex: 0.42;
  background: rgba(255, 255, 255, 0.08);
  color: #d4d4d8;
  border: 1rpx solid rgba(255, 255, 255, 0.15);
  font-size: 23rpx;
}

.psc-control-group {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}

.psc-face-box {
  background: rgba(208, 253, 62, 0.05);
  border: 1rpx solid rgba(208, 253, 62, 0.22);
  border-radius: 16rpx;
  padding: 14rpx 16rpx;
}

.psc-face-status {
  color: #d0fd3e;
  font-weight: 700;
  font-size: 21rpx;
}

.psc-slider-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 4rpx;
}

.psc-slider-lbl {
  font-size: 20rpx;
  color: #a1a1aa;
  white-space: nowrap;
}

.psc-slider {
  flex: 1;
  margin: 0 8rpx;
}

.psc-slider-val {
  font-size: 20rpx;
  color: #d0fd3e;
  font-weight: 700;
  width: 58rpx;
  text-align: right;
}

.psc-label-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.psc-ctrl-label {
  font-size: 22rpx;
  font-weight: 600;
  color: #a1a1aa;
}

.psc-edit-toggle {
  font-size: 22rpx;
  color: #38bdf8;
  font-weight: 600;
}

.psc-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.psc-pill {
  padding: 10rpx 20rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.06);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  color: #d4d4d8;
  font-size: 22rpx;
  font-weight: 600;
}

.psc-pill.active {
  background: rgba(208, 253, 62, 0.16);
  border-color: #d0fd3e;
  color: #d0fd3e;
}

.psc-pill.race-pill.active {
  background: rgba(251, 191, 36, 0.18);
  border-color: #fbbf24;
  color: #fbbf24;
}

.psc-runs-scroll {
  width: 100%;
  white-space: nowrap;
}

.psc-runs-row {
  display: inline-flex;
  gap: 12rpx;
  padding-bottom: 4rpx;
}

.psc-run-chip {
  padding: 10rpx 20rpx;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.05);
  border: 1rpx solid rgba(255, 255, 255, 0.1);
  color: #a1a1aa;
  font-size: 22rpx;
}

.psc-run-chip.active {
  background: rgba(56, 189, 248, 0.16);
  border-color: #38bdf8;
  color: #38bdf8;
  font-weight: 700;
}

.psc-run-chip.race-chip.active {
  background: rgba(251, 191, 36, 0.18);
  border-color: #fbbf24;
  color: #fbbf24;
  font-weight: 700;
}

.psc-commentary-input {
  width: 100%;
  min-height: 120rpx;
  background: #0e1118;
  border: 1rpx solid rgba(192, 132, 252, 0.4);
  border-radius: 14rpx;
  padding: 16rpx;
  font-size: 23rpx;
  color: #ffffff;
  box-sizing: border-box;
  margin-top: 6rpx;
}

.psc-preview-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 520rpx;
  padding-bottom: 16rpx;
}

.psc-loading-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80rpx 0;
  gap: 20rpx;
}

.psc-spinner {
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  border: 5rpx solid rgba(208, 253, 62, 0.2);
  border-top-color: #d0fd3e;
  animation: pscSpin 0.9s linear infinite;
}

@keyframes pscSpin {
  to {
    transform: rotate(360deg);
  }
}

.psc-loading-text {
  font-size: 24rpx;
  color: #a1a1aa;
}

.psc-poster-img {
  width: 100%;
  border-radius: 24rpx;
  box-shadow: 0 16rpx 48rpx rgba(0, 0, 0, 0.6);
}

.psc-preview-hint {
  margin-top: 14rpx;
  font-size: 21rpx;
  color: #71717a;
}

.psc-footer {
  display: flex;
  gap: 18rpx;
  padding: 20rpx 28rpx calc(20rpx + env(safe-area-inset-bottom));
  background: #161924;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
}

.psc-action-btn {
  flex: 1;
  height: 82rpx;
  border-radius: 20rpx;
  font-size: 26rpx;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
}

.psc-action-btn.share-btn {
  background: rgba(56, 189, 248, 0.16);
  color: #38bdf8;
  border: 1rpx solid rgba(56, 189, 248, 0.45);
}

.psc-action-btn.save-btn {
  flex: 1.25;
  background: linear-gradient(135deg, #d0fd3e, #a3e635);
  color: #090b10;
  border: none;
}

.psc-hidden-canvas {
  width: 750px;
  height: 1460px;
  position: fixed;
  left: -9999px;
  top: -9999px;
  pointer-events: none;
}

/* Light (Volt v3.0) Theme Overrides — 60-30-10 统一色彩规范 */
.psc-light.psc-mask {
  background: rgba(15, 23, 42, 0.55);
}

.psc-light .psc-dialog {
  background: #ffffff;
  border-color: #e2e8f0;
  box-shadow: 0 24rpx 64rpx rgba(15, 23, 42, 0.18);
}

.psc-light .psc-header {
  border-bottom-color: #e2e8f0;
}

.psc-light .psc-title {
  color: #0F172A;
}

.psc-light .psc-close {
  background: #f1f5f9;
  color: #475569;
}

.psc-light .psc-controls-card {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.psc-light .psc-photo-btn.ghost {
  background: #ffffff;
  color: #475569;
  border-color: #cbd5e1;
}

.psc-light .psc-face-box {
  background: #FFF5EE;
  border-color: rgba(252, 76, 2, 0.32);
}

.psc-light .psc-face-status,
.psc-light .psc-slider-val {
  color: #C23800;
}

.psc-light .psc-slider-lbl,
.psc-light .psc-ctrl-label {
  color: #475569;
}

.psc-light .psc-edit-toggle {
  color: #C23800;
}

.psc-light .psc-pill {
  background: #ffffff;
  border-color: #e2e8f0;
  color: #475569;
}

.psc-light .psc-pill.active,
.psc-light .psc-pill.race-pill.active {
  background: #FFF5EE;
  border-color: rgba(252, 76, 2, 0.36);
  color: #C23800;
}

.psc-light .psc-run-chip {
  background: #ffffff;
  border-color: #e2e8f0;
  color: #475569;
}

.psc-light .psc-run-chip.active,
.psc-light .psc-run-chip.race-chip.active {
  background: #FFF5EE;
  border-color: rgba(252, 76, 2, 0.36);
  color: #C23800;
}

.psc-light .psc-commentary-input {
  background: #ffffff;
  border-color: rgba(252, 76, 2, 0.36);
  color: #0F172A;
}

.psc-light .psc-loading-text,
.psc-light .psc-preview-hint {
  color: #475569;
}

.psc-light .psc-spinner {
  border-color: #e2e8f0;
  border-top-color: #FC4C02;
}

.psc-light .psc-poster-img {
  box-shadow: 0 12rpx 36rpx rgba(15, 23, 42, 0.12);
}

.psc-light .psc-footer {
  background: #f8fafc;
  border-top-color: #e2e8f0;
}

.psc-light .psc-action-btn.share-btn {
  background: #FFF5EE;
  color: #C23800;
  border-color: rgba(252, 76, 2, 0.36);
}

.psc-light .psc-action-btn.save-btn {
  background: linear-gradient(135deg, #FC4C02, #EA580C);
  color: #FFFFFF;
}
</style>
