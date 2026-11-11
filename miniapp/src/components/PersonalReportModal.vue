<template>
  <view v-if="visible" class="prm-mask" :class="[themeClass, { 'prm-light': isVolt }]" @click="handleClose" @touchmove.stop.prevent>
    <view class="prm-dialog" @click.stop>
      <!-- Top Header -->
      <view class="prm-header">
        <view class="prm-title-wrap">
          <view class="prm-title-row">
            <text class="prm-title">📊 个人周报与月报</text>
          </view>
        </view>
        <view class="prm-close" @click="handleClose">✕</view>
      </view>

      <!-- Controls Bar -->
      <view class="prm-controls">
        <!-- Row 1: Period Type & Offset -->
        <view class="prm-period-grid">
          <view
            class="prm-period-btn"
            :class="{ active: periodType === 'week' }"
            @click="handleSwitchPeriod('week')"
          >
            📅 个人周报
          </view>
          <view
            class="prm-period-btn"
            :class="{ active: periodType === 'month' }"
            @click="handleSwitchPeriod('month')"
          >
            🗓️ 个人月报
          </view>
          <view
            class="prm-offset-btn"
            :class="{ active: periodOffset === 0 }"
            @click="handleSwitchOffset(0)"
          >
            {{ periodType === 'week' ? '本周' : '本月' }}
          </view>
          <view
            class="prm-offset-btn"
            :class="{ active: periodOffset === -1 }"
            @click="handleSwitchOffset(-1)"
          >
            {{ periodType === 'week' ? '上周' : '上月' }}
          </view>
        </view>

        <!-- Row 2: Trail Running Filter -->
        <view class="prm-filter-box">
          <view class="prm-filter-head">
            <text class="prm-filter-title">🏔️ 越野跑统计</text>
            <text
              v-if="reportData && Number(reportData.trail_activities_count || 0) > 0"
              class="prm-trail-hint"
            >
              本周期含越野 {{ reportData.trail_activities_count }} 次 ({{ reportData.trail_distance_km }} km)
            </text>
          </view>
          <view class="prm-trail-tabs">
            <view
              class="prm-trail-tab"
              :class="{ active: trailMode === 'include' }"
              @click="handleSwitchTrailMode('include')"
            >
              含越野(默认)
            </view>
            <view
              class="prm-trail-tab"
              :class="{ active: trailMode === 'exclude_pace' }"
              @click="handleSwitchTrailMode('exclude_pace')"
            >
              仅去越野配速
            </view>
            <view
              class="prm-trail-tab"
              :class="{ active: trailMode === 'exclude_all' }"
              @click="handleSwitchTrailMode('exclude_all')"
            >
              去越野跑量/配速
            </view>
          </view>
        </view>

        <!-- Row 3: Cover Theme & Custom Photo Picker -->
        <view class="prm-filter-box">
          <view class="prm-filter-head">
            <text class="prm-filter-title">🖼️ 封面主题</text>
            <view class="prm-photo-actions">
              <view class="prm-upload-pill" @click="handleChooseCustomPhoto">
                📷 {{ customPhotoPath ? '更换照片' : '上传我的照片' }}
              </view>
              <text
                v-if="customPhotoPath"
                class="prm-reset-photo"
                @click="handleResetCustomPhoto"
              >
                恢复预设图
              </text>
            </view>
          </view>
          <scroll-view scroll-x class="prm-theme-scroll">
            <view class="prm-theme-row">
              <view
                v-for="theme in presetThemes"
                :key="theme.id"
                class="prm-theme-chip"
                :class="{ active: !customPhotoPath && selectedPresetId === theme.id }"
                @click="handleSelectPreset(theme.id)"
              >
                {{ theme.name }}
              </view>
            </view>
          </scroll-view>
        </view>

        <!-- Row 4: View Mode Switcher -->
        <view class="prm-view-tabs">
          <view
            class="prm-view-tab"
            :class="{ active: viewMode === 'poster' }"
            @click="viewMode = 'poster'"
          >
            🎨 海报
          </view>
          <view
            class="prm-view-tab"
            :class="{ active: viewMode === 'text' }"
            @click="viewMode = 'text'"
          >
            💬 转发文案
          </view>
        </view>
      </view>

      <!-- Main Scroll Body -->
      <view v-if="loading" class="prm-loading">
        <text class="prm-loading-icon">⏳</text>
        <text class="prm-loading-txt">正在生成...</text>
      </view>

      <scroll-view v-else-if="reportData" scroll-y class="prm-scroll-body">
        <!-- Poster Card View -->
        <view v-if="viewMode === 'poster'" class="prm-poster-card">
          <!-- Cover Banner -->
          <view
            class="prm-cover-banner"
            :style="{
              background: customPhotoPath
                ? (isVolt ? '#e2e8f0' : '#0f172a')
                : `linear-gradient(135deg, ${isVolt ? activePreset.lightC1 : activePreset.c1} 0%, ${isVolt ? activePreset.lightC2 : activePreset.c2} 100%)`
            }"
          >
            <image
              v-if="customPhotoPath"
              :src="customPhotoPath"
              mode="aspectFill"
              class="prm-cover-img"
            />
            <view class="prm-cover-overlay" />
            <view class="prm-cover-top">
              <text class="prm-cover-tag">🏃 个人运动战报</text>
              <text
                v-if="reportData.trail_mode && reportData.trail_mode !== 'include'"
                class="prm-cover-trail-tag"
              >
                {{ reportData.trail_mode === 'exclude_pace' ? '⏱️ 均速已去除越野跑' : '🛣️ 已去除越野跑量与配速' }}
              </text>
            </view>
            <view class="prm-cover-bottom">
              <text class="prm-runner-name">{{ reportData.display_name || '跑者' }}</text>
              <text class="prm-period-str">{{ reportData.period_label }} · {{ reportData.date_range_str }}</text>
            </view>
          </view>

          <!-- Card Body -->
          <view class="prm-card-inner">
            <!-- Hero Mileage & Target Progress -->
            <view class="prm-hero-box">
              <view class="prm-hero-top">
                <view>
                  <text class="prm-hero-lbl">本周期累计奔跑里程</text>
                  <view class="prm-hero-num-row">
                    <text class="prm-hero-num">{{ reportData.total_distance_km }}</text>
                    <text class="prm-hero-unit">KM</text>
                  </view>
                </view>
                <view class="prm-hero-right">
                  <text class="prm-target-lbl">周期目标 {{ reportData.target_km }} km</text>
                  <text class="prm-target-pct">完成 {{ reportData.completion_rate }}%</text>
                </view>
              </view>
              <view class="prm-prog-bg">
                <view
                  class="prm-prog-fill"
                  :style="{ width: Math.min(100, reportData.completion_rate || 0) + '%' }"
                />
              </view>
              <view class="prm-hero-meta">
                <text class="prm-meta-txt">累计用时 {{ reportData.total_moving_time_str || '—' }}</text>
                <text v-if="reportData.remaining_km > 0" class="prm-meta-txt">差 {{ reportData.remaining_km }} km 达标</text>
                <text v-else class="prm-meta-ok">✓ 已达成周期目标</text>
              </view>
            </view>

            <!-- 4-Grid Stats -->
            <view class="prm-stats-grid">
              <view class="prm-stat-cell">
                <text class="prm-stat-label">⏱️ 出勤打卡</text>
                <text class="prm-stat-val">{{ reportData.total_activities_count }}次 / {{ reportData.active_days_count }}天</text>
              </view>
              <view class="prm-stat-cell">
                <text class="prm-stat-label">⚡ 平均配速</text>
                <text class="prm-stat-val font-mono">{{ reportData.avg_pace_str }}</text>
              </view>
              <view class="prm-stat-cell">
                <text class="prm-stat-label">❤️ 平均心率</text>
                <text class="prm-stat-val">{{ reportData.avg_heartrate ? reportData.avg_heartrate + ' bpm' : '—' }}</text>
              </view>
              <view class="prm-stat-cell">
                <text class="prm-stat-label">⛰️ 累计爬升</text>
                <text class="prm-stat-val">+{{ reportData.total_elevation_gain_m }} m</text>
              </view>
            </view>

            <!-- Highlights: Longest Run & Fastest Run -->
            <view v-if="reportData.longest_run || reportData.fastest_run" class="prm-highlights">
              <view v-if="reportData.longest_run" class="prm-hl-card sky">
                <text class="prm-hl-tag sky">🚀 单次最长距离</text>
                <text class="prm-hl-main">{{ reportData.longest_run.distance_km }} km · {{ reportData.longest_run.avg_pace_str }}</text>
                <text class="prm-hl-sub">{{ reportData.longest_run.start_time }} · {{ reportData.longest_run.activity_name }}</text>
              </view>
              <view v-if="reportData.fastest_run" class="prm-hl-card amber">
                <text class="prm-hl-tag amber">⚡ 最佳配速课 (≥3km)</text>
                <text class="prm-hl-main">{{ reportData.fastest_run.avg_pace_str }} · {{ reportData.fastest_run.distance_km }} km</text>
                <text class="prm-hl-sub">{{ reportData.fastest_run.start_time }} · {{ reportData.fastest_run.activity_name }}</text>
              </view>
            </view>

            <!-- Practical Coach Critique -->
            <view class="prm-critique-box">
              <text class="prm-critique-title">💡 教练周期实战复盘与建议</text>
              <text class="prm-critique-txt">{{ reportData.canova_critique }}</text>
            </view>

            <!-- Footer QR Code (Pure Miniapp QR, no club invite) -->
            <view class="prm-footer-qr">
              <view class="prm-fq-left">
                <text class="prm-fq-brand">🏃 万跑跑团助手 · 科学耐力训练系统</text>
                <text class="prm-fq-main">微信扫码打开万跑跑团助手小程序</text>
                <text class="prm-fq-sub">佳明/高驰手表自动同步 · 科学耐力训练与周期复盘</text>
              </view>
              <view v-if="qrDisplaySrc" class="prm-fq-right">
                <view class="prm-qr-frame">
                  <image :src="qrDisplaySrc" mode="aspectFit" class="prm-qr-img" />
                </view>
                <text class="prm-qr-cap">微信扫码体验</text>
              </view>
            </view>
          </view>
        </view>

        <!-- Text View -->
        <view v-else class="prm-text-box">
          <view class="prm-text-head">
            <text class="prm-text-title">💬 文案预览</text>
            <text class="prm-text-hint">可长按选择或一键复制</text>
          </view>
          <view class="prm-text-card">
            <text class="prm-text-content" :selectable="true">{{ reportData.forward_text }}</text>
          </view>
        </view>
      </scroll-view>

      <!-- Hidden Canvas for 2x Retina Poster Export -->
      <canvas
        canvas-id="personalReportPosterCanvas"
        id="personalReportPosterCanvas"
        style="width: 750px; height: 1380px; position: fixed; left: -9999px; top: -9999px;"
      />

      <!-- Footer Action Buttons -->
      <view v-if="reportData" class="prm-footer-actions">
        <template v-if="viewMode === 'poster'">
          <button class="prm-btn primary" @click="handlePreviewPoster">
            📤 转发
          </button>
          <button class="prm-btn save" @click="handleSavePosterToAlbum">
            💾 保存
          </button>
        </template>
        <template v-else>
          <button class="prm-btn copy" @click="handleCopyText">
            📋 复制文案
          </button>
        </template>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, getCurrentInstance, onBeforeUnmount } from "vue";
import { request, getStoredUser, setTabBarHidden } from "../utils/api";
import { isVolt, themeClass } from "../utils/theme";
import { trackModal } from "../utils/telemetry";

const props = defineProps<{
  visible: boolean;
  userId?: string;
  defaultPeriodType?: "week" | "month";
}>();

const emit = defineEmits(["close"]);
const instance = getCurrentInstance();

watch(
  () => props.visible,
  (val, oldVal) => {
    if (val && !oldVal) {
      trackModal("personal_report", `打开个人${props.defaultPeriodType === "month" ? "月度" : "周度"}战报`, "open", {
        period: props.defaultPeriodType || "week",
      });
    } else if (!val && oldVal) {
      trackModal("personal_report", "关闭个人周月战报", "close");
    }
  }
);

interface PresetTheme {
  id: string;
  name: string;
  accent: string;
  c1: string;
  c2: string;
  lightC1: string;
  lightC2: string;
  bgGradient: [string, string, string];
  lightBgGradient: [string, string, string];
  motif: "dawn" | "night" | "mountain" | "track" | "forest" | "minimal";
}

const presetThemes: PresetTheme[] = [
  {
    id: "dawn",
    name: "🌅 晨曦破晓",
    accent: "#fc4c02",
    c1: "#3b170e",
    c2: "#131829",
    lightC1: "#ea580c",
    lightC2: "#fbbf24",
    bgGradient: ["#1c1210", "#141622", "#0b0d13"],
    lightBgGradient: ["#fffaf5", "#ffffff", "#f8fafc"],
    motif: "dawn",
  },
  {
    id: "night",
    name: "🌃 城市夜跑",
    accent: "#38bdf8",
    c1: "#0f2442",
    c2: "#171430",
    lightC1: "#0284c7",
    lightC2: "#4f46e5",
    bgGradient: ["#0d1526", "#131728", "#090b12"],
    lightBgGradient: ["#f0f9ff", "#ffffff", "#f8fafc"],
    motif: "night",
  },
  {
    id: "mountain",
    name: "🏔️ 山野之巅",
    accent: "#f59e0b",
    c1: "#292111",
    c2: "#111827",
    lightC1: "#d97706",
    lightC2: "#059669",
    bgGradient: ["#171510", "#131722", "#0a0c12"],
    lightBgGradient: ["#fffbeb", "#ffffff", "#f8fafc"],
    motif: "mountain",
  },
  {
    id: "track",
    name: "🏟️ 热血跑道",
    accent: "#f43f5e",
    c1: "#381220",
    c2: "#131626",
    lightC1: "#e11d48",
    lightC2: "#f97316",
    bgGradient: ["#211018", "#151622", "#0b0c12"],
    lightBgGradient: ["#fff1f2", "#ffffff", "#f8fafc"],
    motif: "track",
  },
  {
    id: "forest",
    name: "🌲 森系绿道",
    accent: "#10b981",
    c1: "#0d2e24",
    c2: "#111827",
    lightC1: "#059669",
    lightC2: "#10b981",
    bgGradient: ["#0d1f1a", "#121822", "#0a0d12"],
    lightBgGradient: ["#f8fafc", "#ffffff", "#f1f5f9"],
    motif: "forest",
  },
  {
    id: "minimal",
    name: "🖤 黑金荣耀",
    accent: "#eab308",
    c1: "#241f12",
    c2: "#10121a",
    lightC1: "#475569",
    lightC2: "#b45309",
    bgGradient: ["#181611", "#12141c", "#090a0f"],
    lightBgGradient: ["#f8fafc", "#ffffff", "#f1f5f9"],
    motif: "minimal",
  },
];

const periodType = ref<"week" | "month">(props.defaultPeriodType || "week");
const periodOffset = ref<number>(0);
const trailMode = ref<"include" | "exclude_pace" | "exclude_all">("include");
const viewMode = ref<"poster" | "text">("poster");
const reportData = ref<any>(null);
const loading = ref<boolean>(false);

const selectedPresetId = ref<string>("dawn");
const customPhotoPath = ref<string>("");
const customPhotoWidth = ref<number>(800);
const customPhotoHeight = ref<number>(600);

const activePreset = computed(
  () => presetThemes.find((t) => t.id === selectedPresetId.value) || presetThemes[0]
);

const qrDisplaySrc = computed(() => {
  const rep = reportData.value;
  if (!rep) return "";
  if (rep.qrcode_base64) {
    return rep.qrcode_base64.startsWith("data:")
      ? rep.qrcode_base64
      : `data:image/jpeg;base64,${rep.qrcode_base64}`;
  }
  return rep.qrcode_url || "";
});

watch(
  () => [props.visible, props.defaultPeriodType],
  ([vis, defType]) => {
    setTabBarHidden(Boolean(vis));
    if (vis) {
      if (defType === "week" || defType === "month") {
        periodType.value = defType;
      }
      periodOffset.value = 0;
      fetchPersonalReport();
    }
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  setTabBarHidden(false);
});

function handleClose() {
  setTabBarHidden(false);
  emit("close");
}

async function fetchPersonalReport() {
  const uid = props.userId || getStoredUser()?.id;
  if (!uid) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  loading.value = true;
  try {
    let url = `/api/science/personal-report/${encodeURIComponent(uid)}?period_type=${periodType.value}&trail_mode=${trailMode.value}`;
    if (periodOffset.value === -1) {
      const now = new Date();
      if (periodType.value === "week") {
        const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const target = new Date(d.valueOf());
        const dayNr = (d.getDay() + 6) % 7;
        target.setDate(target.getDate() - dayNr + 3);
        const firstThursday = target.valueOf();
        target.setMonth(0, 1);
        if (target.getDay() !== 4) {
          target.setMonth(0, 1 + (((4 - target.getDay()) + 7) % 7));
        }
        const weekNum = 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
        url += `&year=${d.getFullYear()}&period_index=${weekNum}`;
      } else {
        const prevMonth = now.getMonth() === 0 ? 12 : now.getMonth();
        const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
        url += `&year=${prevYear}&period_index=${prevMonth}`;
      }
    }
    const res = await request(url);
    reportData.value = res;
  } catch (err: any) {
    console.error("fetchPersonalReport error:", err);
    uni.showToast({ title: err?.message || "加载个人战报失败", icon: "none" });
  } finally {
    loading.value = false;
  }
}

function handleSwitchPeriod(type: "week" | "month") {
  if (periodType.value === type) return;
  periodType.value = type;
  periodOffset.value = 0;
  fetchPersonalReport();
}

function handleSwitchOffset(offset: number) {
  if (periodOffset.value === offset) return;
  periodOffset.value = offset;
  fetchPersonalReport();
}

function handleSwitchTrailMode(mode: "include" | "exclude_pace" | "exclude_all") {
  if (trailMode.value === mode) return;
  trailMode.value = mode;
  fetchPersonalReport();
}

function handleSelectPreset(id: string) {
  customPhotoPath.value = "";
  selectedPresetId.value = id;
}

function handleChooseCustomPhoto() {
  uni.chooseImage({
    count: 1,
    sizeType: ["compressed", "original"],
    sourceType: ["album", "camera"],
    success: (res) => {
      const path = res.tempFilePaths?.[0];
      if (!path) return;
      uni.getImageInfo({
        src: path,
        success: (info) => {
          customPhotoPath.value = info.path || path;
          customPhotoWidth.value = info.width || 800;
          customPhotoHeight.value = info.height || 600;
        },
        fail: () => {
          customPhotoPath.value = path;
          customPhotoWidth.value = 800;
          customPhotoHeight.value = 600;
        },
      });
    },
  });
}

function handleResetCustomPhoto() {
  customPhotoPath.value = "";
}

function handleCopyText() {
  const txt = reportData.value?.forward_text;
  if (!txt) return;
  uni.setClipboardData({
    data: txt,
    success: () => {
      uni.showToast({ title: "已复制分享文案，可粘贴发群或朋友圈！", icon: "success", duration: 2500 });
    },
  });
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
  width: number,
  height: number,
  radius: number,
  fillStyle?: string,
  strokeStyle?: string
) {
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

function drawWrappedText(
  ctx: any,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines: number = 6
) {
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
        const suffix = "...";
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

function generatePersonalPosterImage(): Promise<string> {
  return new Promise(async (resolve, reject) => {
    if (!reportData.value) {
      reject(new Error("暂无战报数据"));
      return;
    }
    const rep = reportData.value;
    const preset = activePreset.value;
    const W = 750;
    const H = 1380;
    const isLight = isVolt.value;
    const ctx = uni.createCanvasContext("personalReportPosterCanvas", instance?.proxy);

    // 1. Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    const bgStops = isLight ? preset.lightBgGradient : preset.bgGradient;
    bgGrad.addColorStop(0, bgStops[0]);
    bgGrad.addColorStop(0.5, bgStops[1]);
    bgGrad.addColorStop(1, bgStops[2]);
    ctx.setFillStyle(bgGrad);
    ctx.fillRect(0, 0, W, H);

    if (isLight) {
      drawRoundedRect(ctx, 16, 16, W - 32, H - 32, 24, undefined, "#E2E8F0");
    }

    // 2. Top Cover Box (40, 40, W-80, 320)
    const cX = 40;
    const cY = 40;
    const cW = W - 80;
    const cH = 320;
    ctx.save();
    drawRoundedRect(ctx, cX, cY, cW, cH, 24);
    ctx.clip();

    if (customPhotoPath.value) {
      const imgW = customPhotoWidth.value || 800;
      const imgH = customPhotoHeight.value || 600;
      const scale = Math.max(cW / imgW, cH / imgH);
      const drawW = imgW * scale;
      const drawH = imgH * scale;
      const dx = cX + (cW - drawW) / 2;
      const dy = cY + (cH - drawH) * 0.25;
      ctx.drawImage(customPhotoPath.value, dx, dy, drawW, drawH);
    } else {
      const covGrad = ctx.createLinearGradient(cX, cY, cX + cW, cY + cH);
      covGrad.addColorStop(0, isLight ? preset.lightC1 : preset.c1);
      covGrad.addColorStop(1, isLight ? preset.lightC2 : preset.c2);
      ctx.setFillStyle(covGrad);
      ctx.fillRect(cX, cY, cW, cH);

      // Decorative motif accent circle
      ctx.beginPath();
      ctx.arc(cX + cW - 110, cY + 95, 85, 0, Math.PI * 2);
      ctx.setFillStyle(isLight ? "rgba(255, 255, 255, 0.22)" : "rgba(252, 76, 2, 0.22)");
      ctx.fill();
    }

    const imgOverlay = ctx.createLinearGradient(0, cY, 0, cY + cH);
    if (isLight) {
      imgOverlay.addColorStop(0, "rgba(15, 23, 42, 0.08)");
      imgOverlay.addColorStop(0.55, "rgba(15, 23, 42, 0.30)");
      imgOverlay.addColorStop(1, "rgba(15, 23, 42, 0.76)");
    } else {
      imgOverlay.addColorStop(0, "rgba(10, 12, 18, 0.2)");
      imgOverlay.addColorStop(0.55, "rgba(10, 12, 18, 0.45)");
      imgOverlay.addColorStop(1, "rgba(10, 12, 18, 0.92)");
    }
    ctx.setFillStyle(imgOverlay);
    ctx.fillRect(cX, cY, cW, cH);
    ctx.restore();

    drawRoundedRect(ctx, cX, cY, cW, cH, 24, undefined, isLight ? "rgba(15, 23, 42, 0.14)" : "rgba(255, 255, 255, 0.16)");

    drawRoundedRect(ctx, 64, 64, 190, 40, 20, "rgba(0, 0, 0, 0.48)", "rgba(255, 255, 255, 0.28)");
    ctx.setFontSize(18);
    ctx.setFillStyle("#fde68a");
    ctx.fillText("🏃 个人运动战报", 82, 90);

    ctx.setFontSize(34);
    ctx.setFillStyle("#ffffff");
    ctx.fillText(rep.display_name || "跑者", 64, 290);

    const trailTag =
      rep.trail_mode === "exclude_pace"
        ? " · 仅去越野配速"
        : rep.trail_mode === "exclude_all"
        ? " · 去越野跑量/配速"
        : "";
    ctx.setFontSize(20);
    ctx.setFillStyle("#fde68a");
    ctx.fillText(`${rep.period_label} · ${rep.date_range_str}${trailTag}`, 64, 330);

    // 3. Hero Mileage & Target Progress Box
    drawRoundedRect(
      ctx,
      40,
      385,
      W - 80,
      165,
      22,
      isLight ? "#F8FAFC" : "#151824",
      isLight ? "#E2E8F0" : "rgba(252, 76, 2, 0.35)"
    );
    ctx.setFontSize(20);
    ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
    ctx.fillText("本周期累计奔跑里程", 68, 425);

    ctx.setFontSize(68);
    ctx.setFillStyle("#fc4c02");
    ctx.fillText(`${rep.total_distance_km}`, 68, 502);

    const kmW = ctx.measureText(`${rep.total_distance_km}`).width;
    ctx.setFontSize(28);
    ctx.setFillStyle(isLight ? "#0F172A" : "#fbbf24");
    ctx.fillText("KM", 68 + kmW + 12, 498);

    ctx.setFontSize(19);
    ctx.setFillStyle(isLight ? "#0F172A" : "#e4e4e7");
    ctx.fillText(`目标 ${rep.target_km} km · 完成 ${rep.completion_rate}%`, W - 355, 430);

    drawRoundedRect(ctx, W - 355, 450, 285, 16, 8, isLight ? "#F1F5F9" : "rgba(255,255,255,0.08)");
    const progW = Math.max(12, Math.min(285, Math.round(((rep.completion_rate || 0) / 100) * 285)));
    drawRoundedRect(ctx, W - 355, 450, progW, 16, 8, "#fc4c02");

    ctx.setFontSize(18);
    ctx.setFillStyle(isLight ? "#475569" : "#a1a1aa");
    ctx.fillText(`累计用时 ${rep.total_moving_time_str || "—"}`, W - 355, 502);

    // 4. 4-Grid Key Metrics
    const gW = (W - 80 - 18) / 2;
    const gH = 92;
    const cellBg = isLight ? "#F8FAFC" : "#151722";
    const cellBorder = isLight ? "#e2e8f0" : "rgba(255,255,255,0.08)";
    const cellLblColor = isLight ? "#475569" : "#9ca3af";
    const cellValColor = isLight ? "#0F172A" : "#ffffff";

    drawRoundedRect(ctx, 40, 570, gW, gH, 16, cellBg, cellBorder);
    ctx.setFontSize(19);
    ctx.setFillStyle(cellLblColor);
    ctx.fillText("出勤打卡", 58, 602);
    ctx.setFontSize(26);
    ctx.setFillStyle(cellValColor);
    ctx.fillText(`${rep.total_activities_count} 次 / ${rep.active_days_count} 天`, 58, 642);

    drawRoundedRect(ctx, 40 + gW + 18, 570, gW, gH, 16, cellBg, cellBorder);
    ctx.setFontSize(19);
    ctx.setFillStyle(cellLblColor);
    ctx.fillText("平均配速", 58 + gW + 18, 602);
    ctx.setFontSize(26);
    ctx.setFillStyle(cellValColor);
    ctx.fillText(`${rep.avg_pace_str}`, 58 + gW + 18, 642);

    drawRoundedRect(ctx, 40, 678, gW, gH, 16, cellBg, cellBorder);
    ctx.setFontSize(19);
    ctx.setFillStyle(cellLblColor);
    ctx.fillText("平均心率", 58, 710);
    ctx.setFontSize(26);
    ctx.setFillStyle(cellValColor);
    ctx.fillText(rep.avg_heartrate ? `${rep.avg_heartrate} bpm` : "—", 58, 750);

    drawRoundedRect(ctx, 40 + gW + 18, 678, gW, gH, 16, cellBg, cellBorder);
    ctx.setFontSize(19);
    ctx.setFillStyle(cellLblColor);
    ctx.fillText("累计爬升", 58 + gW + 18, 710);
    ctx.setFontSize(26);
    ctx.setFillStyle(cellValColor);
    ctx.fillText(`+${rep.total_elevation_gain_m} m`, 58 + gW + 18, 750);

    // 5. Highlights (Longest Run & Best Pace)
    const hY = 790;
    drawRoundedRect(
      ctx,
      40,
      hY,
      gW,
      95,
      16,
      isLight ? "#F8FAFC" : "#151722",
      isLight ? "#E2E8F0" : "rgba(56, 189, 248, 0.28)"
    );
    ctx.setFontSize(18);
    ctx.setFillStyle(isLight ? "#C23800" : "#38bdf8");
    ctx.fillText("🚀 单次最长距离", 58, hY + 30);
    ctx.setFontSize(24);
    ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
    ctx.fillText(rep.longest_run ? `${rep.longest_run.distance_km} km` : "暂无", 58, hY + 62);
    ctx.setFontSize(15);
    ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
    ctx.fillText(
      rep.longest_run ? `配速 ${rep.longest_run.avg_pace_str} · ${rep.longest_run.start_time}` : "期待开启长距离",
      58,
      hY + 84
    );

    drawRoundedRect(
      ctx,
      40 + gW + 18,
      hY,
      gW,
      95,
      16,
      isLight ? "#F8FAFC" : "#151722",
      isLight ? "#E2E8F0" : "rgba(251, 191, 36, 0.28)"
    );
    ctx.setFontSize(18);
    ctx.setFillStyle(isLight ? "#C23800" : "#fbbf24");
    ctx.fillText("⚡ 最佳配速课 (≥3km)", 58 + gW + 18, hY + 30);
    ctx.setFontSize(24);
    ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
    ctx.fillText(rep.fastest_run ? `${rep.fastest_run.avg_pace_str}` : "暂无", 58 + gW + 18, hY + 62);
    ctx.setFontSize(15);
    ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
    ctx.fillText(
      rep.fastest_run ? `单次 ${rep.fastest_run.distance_km} km · ${rep.fastest_run.start_time}` : "期待刷新配速",
      58 + gW + 18,
      hY + 84
    );

    // 6. Practical Coach Critique Box
    const crY = 905;
    drawRoundedRect(
      ctx,
      40,
      crY,
      W - 80,
      265,
      20,
      isLight ? "#F8FAFC" : "#181624",
      isLight ? "#E2E8F0" : "rgba(191, 90, 242, 0.38)"
    );
    ctx.setFontSize(22);
    ctx.setFillStyle(isLight ? "#0F172A" : "#c084fc");
    ctx.fillText("💡 教练周期实战复盘与建议", 62, crY + 38);

    ctx.setFontSize(18);
    ctx.setFillStyle(isLight ? "#334155" : "#e4e4e7");
    drawWrappedText(ctx, rep.canova_critique || "", 62, crY + 74, W - 124, 30, 6);

    // 7. Footer with Pure Mini-Program QR Code
    const fY = 1190;
    drawRoundedRect(
      ctx,
      40,
      fY,
      W - 80,
      150,
      20,
      isLight ? "#f8fafc" : "#121520",
      isLight ? "#e2e8f0" : "rgba(255, 255, 255, 0.1)"
    );

    ctx.setFontSize(18);
    ctx.setFillStyle("#fc4c02");
    ctx.fillText("🏃 万跑跑团助手 · 科学耐力训练系统", 64, fY + 42);

    ctx.setFontSize(24);
    ctx.setFillStyle(isLight ? "#0F172A" : "#ffffff");
    ctx.fillText("微信扫码打开万跑跑团助手小程序", 64, fY + 80);

    ctx.setFontSize(16);
    ctx.setFillStyle(isLight ? "#475569" : "#9ca3af");
    ctx.fillText("佳明/高驰手表自动同步 · 科学耐力训练与周期复盘", 64, fY + 114);

    if (rep.qrcode_base64) {
      const qrLocalPath = await writeBase64ToLocalFile(rep.qrcode_base64, "prm_qr");
      if (qrLocalPath) {
        const qrBoxX = W - 40 - 134;
        const qrBoxY = fY + 15;
        drawRoundedRect(ctx, qrBoxX, qrBoxY, 120, 120, 14, "#ffffff", isLight ? "#e2e8f0" : undefined);
        ctx.drawImage(qrLocalPath, qrBoxX + 6, qrBoxY + 6, 108, 108);
      }
    }

    ctx.draw(false, () => {
      setTimeout(() => {
        uni.canvasToTempFilePath(
          {
            canvasId: "personalReportPosterCanvas",
            x: 0,
            y: 0,
            width: W,
            height: H,
            destWidth: W * 2,
            destHeight: H * 2,
            fileType: "jpg",
            quality: 0.92,
            success: (res) => resolve(res.tempFilePath),
            fail: (err) => reject(err),
          },
          instance?.proxy
        );
      }, 240);
    });
  });
}

async function handlePreviewPoster() {
  uni.showLoading({ title: "正在生成战报海报..." });
  try {
    const tempPath = await generatePersonalPosterImage();
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
    uni.previewImage({ current: tempPath, urls: [tempPath] });
    uni.showToast({ title: "长按图片可直接转发朋友圈或微信群", icon: "none", duration: 3000 });
  } catch (err) {
    uni.hideLoading();
    console.error("handlePreviewPoster error:", err);
    uni.showToast({ title: "生成海报失败，请重试", icon: "none" });
  }
}

async function handleSavePosterToAlbum() {
  trackModal("personal_report", "保存个人周月战报海报到相册", "submit");
  uni.showLoading({ title: "正在生成并保存..." });
  try {
    const tempPath = await generatePersonalPosterImage();
    uni.saveImageToPhotosAlbum({
      filePath: tempPath,
      success: () => {
        uni.hideLoading();
        uni.showToast({ title: "个人战报已保存到相册！", icon: "success", duration: 2500 });
      },
      fail: () => {
        uni.hideLoading();
        uni.previewImage({ current: tempPath, urls: [tempPath] });
        uni.showToast({ title: "长按图片即可直接保存到相册", icon: "none", duration: 3000 });
      },
    });
  } catch (err) {
    uni.hideLoading();
    uni.showToast({ title: "保存失败，请重试", icon: "none" });
  }
}
</script>

<style scoped>
.prm-mask {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.82);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20rpx 20rpx calc(36rpx + env(safe-area-inset-bottom)) 20rpx;
  box-sizing: border-box;
}
.prm-dialog {
  width: 100%;
  max-width: 710rpx;
  max-height: 84vh;
  background: #131419;
  border: 2rpx solid rgba(245, 158, 11, 0.35);
  border-radius: 32rpx;
  padding: 22rpx;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow: hidden;
}
.prm-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12rpx;
  margin-bottom: 12rpx;
  flex-shrink: 0;
}
.prm-title-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  flex-wrap: wrap;
}
.prm-title {
  font-size: 30rpx;
  font-weight: 900;
  color: #ffffff;
}
.prm-close {
  width: 52rpx;
  height: 52rpx;
  border-radius: 26rpx;
  background: rgba(255, 255, 255, 0.08);
  color: #a1a1aa;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26rpx;
  flex-shrink: 0;
}
.prm-controls {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  margin-bottom: 10rpx;
  flex-shrink: 0;
}
.prm-period-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8rpx;
}
.prm-period-btn,
.prm-offset-btn {
  text-align: center;
  padding: 10rpx 6rpx;
  border-radius: 14rpx;
  font-size: 21rpx;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.05);
  color: #a1a1aa;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}
.prm-period-btn.active {
  background: #f59e0b;
  color: #09090b;
  border-color: #f59e0b;
}
.prm-offset-btn.active {
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
  border-color: rgba(245, 158, 11, 0.45);
}
.prm-filter-box {
  background: rgba(255, 255, 255, 0.03);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 18rpx;
  padding: 10rpx 14rpx;
}
.prm-filter-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8rpx;
}
.prm-filter-title {
  font-size: 21rpx;
  font-weight: 700;
  color: #d4d4d8;
}
.prm-trail-hint {
  font-size: 19rpx;
  color: #fbbf24;
}
.prm-trail-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10rpx;
}
.prm-trail-tab {
  text-align: center;
  padding: 10rpx 6rpx;
  border-radius: 14rpx;
  font-size: 20rpx;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.05);
  color: #a1a1aa;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}
.prm-trail-tab.active {
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
  border-color: rgba(245, 158, 11, 0.45);
}
.prm-photo-actions {
  display: flex;
  align-items: center;
  gap: 14rpx;
}
.prm-upload-pill {
  padding: 6rpx 16rpx;
  border-radius: 12rpx;
  background: rgba(252, 76, 2, 0.2);
  border: 1rpx solid rgba(252, 76, 2, 0.45);
  color: #fc4c02;
  font-size: 20rpx;
  font-weight: 700;
}
.prm-reset-photo {
  font-size: 19rpx;
  color: #a1a1aa;
  text-decoration: underline;
}
.prm-theme-scroll {
  width: 100%;
  white-space: nowrap;
}
.prm-theme-row {
  display: inline-flex;
  gap: 10rpx;
}
.prm-theme-chip {
  padding: 10rpx 18rpx;
  border-radius: 14rpx;
  font-size: 20rpx;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.05);
  color: #a1a1aa;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}
.prm-theme-chip.active {
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
  border-color: rgba(245, 158, 11, 0.5);
}
.prm-view-tabs {
  display: flex;
  gap: 10rpx;
  background: rgba(0, 0, 0, 0.4);
  padding: 6rpx;
  border-radius: 16rpx;
}
.prm-view-tab {
  flex: 1;
  text-align: center;
  padding: 12rpx 0;
  border-radius: 12rpx;
  font-size: 22rpx;
  font-weight: 700;
  color: #a1a1aa;
}
.prm-view-tab.active {
  background: linear-gradient(90deg, #f59e0b, #d97706);
  color: #09090b;
  font-weight: 900;
}
.prm-loading {
  padding: 90rpx 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14rpx;
}
.prm-loading-icon {
  font-size: 44rpx;
}
.prm-loading-txt {
  font-size: 23rpx;
  color: #9ca3af;
}
.prm-scroll-body {
  flex: 1;
  min-height: 0;
  max-height: 39vh;
  overflow: hidden;
}
.prm-poster-card {
  --rgm-fs: 1;
  background: linear-gradient(180deg, #131622 0%, #151824 55%, #0c0d14 100%);
  border: 2rpx solid rgba(245, 158, 11, 0.35);
  border-radius: 28rpx;
  overflow: hidden;
}
.prm-cover-banner {
  position: relative;
  height: 250rpx;
  width: 100%;
  overflow: hidden;
}
.prm-cover-img {
  width: 100%;
  height: 100%;
}
.prm-cover-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(10, 12, 18, 0.2) 0%, rgba(19, 22, 34, 0.92) 100%);
}
.prm-cover-top {
  position: absolute;
  top: 20rpx;
  left: 24rpx;
  right: 24rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.prm-cover-tag {
  padding: 6rpx 18rpx;
  border-radius: 999rpx;
  background: rgba(0, 0, 0, 0.6);
  color: #fcd34d;
  font-size: 20rpx;
  font-weight: 800;
  border: 1rpx solid rgba(255, 255, 255, 0.2);
}
.prm-cover-trail-tag {
  padding: 5rpx 14rpx;
  border-radius: 999rpx;
  background: rgba(245, 158, 11, 0.22);
  color: #fde68a;
  font-size: 18rpx;
  font-weight: 700;
  border: 1rpx solid rgba(245, 158, 11, 0.45);
}
.prm-cover-bottom {
  position: absolute;
  bottom: 20rpx;
  left: 24rpx;
  right: 24rpx;
}
.prm-runner-name {
  font-size: 36rpx;
  font-weight: 900;
  color: #ffffff;
  display: block;
}
.prm-period-str {
  font-size: 22rpx;
  font-weight: 700;
  color: #fcd34d;
  margin-top: 4rpx;
  display: block;
}
.prm-card-inner {
  padding: 24rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.prm-hero-box {
  background: rgba(252, 76, 2, 0.1);
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  border-radius: 22rpx;
  padding: 22rpx;
}
.prm-hero-top {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 12rpx;
}
.prm-hero-lbl {
  font-size: 21rpx;
  color: #9ca3af;
  font-weight: 700;
  display: block;
}
.prm-hero-num-row {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  margin-top: 4rpx;
}
.prm-hero-num {
  font-size: 56rpx;
  font-weight: 900;
  color: #fc4c02;
}
.prm-hero-unit {
  font-size: 26rpx;
  font-weight: 900;
  color: #fbbf24;
}
.prm-hero-right {
  text-align: right;
}
.prm-target-lbl {
  font-size: 21rpx;
  color: #d4d4d8;
  display: block;
}
.prm-target-pct {
  font-size: 24rpx;
  font-weight: 900;
  color: #fbbf24;
  margin-top: 4rpx;
  display: block;
}
.prm-prog-bg {
  width: 100%;
  height: 14rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
  margin-bottom: 10rpx;
}
.prm-prog-fill {
  height: 100%;
  background: linear-gradient(90deg, #fc4c02, #fbbf24);
  border-radius: 999rpx;
}
.prm-hero-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.prm-meta-txt {
  font-size: 20rpx;
  color: #a1a1aa;
}
.prm-meta-ok {
  font-size: 20rpx;
  font-weight: 700;
  color: #34d399;
}
.prm-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14rpx;
}
.prm-stat-cell {
  background: rgba(255, 255, 255, 0.04);
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 18rpx;
  padding: 18rpx;
}
.prm-stat-label {
  font-size: 20rpx;
  color: #9ca3af;
  display: block;
}
.prm-stat-val {
  font-size: 27rpx;
  font-weight: 800;
  color: #ffffff;
  margin-top: 6rpx;
  display: block;
}
.prm-highlights {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14rpx;
}
.prm-hl-card {
  padding: 18rpx;
  border-radius: 18rpx;
}
.prm-hl-card.sky {
  background: rgba(56, 189, 248, 0.07);
  border: 1rpx solid rgba(56, 189, 248, 0.28);
}
.prm-hl-card.amber {
  background: rgba(245, 158, 11, 0.07);
  border: 1rpx solid rgba(245, 158, 11, 0.28);
}
.prm-hl-tag {
  font-size: 19rpx;
  font-weight: 700;
  display: block;
}
.prm-hl-tag.sky {
  color: #38bdf8;
}
.prm-hl-tag.amber {
  color: #fbbf24;
}
.prm-hl-main {
  font-size: 24rpx;
  font-weight: 800;
  color: #ffffff;
  margin-top: 6rpx;
  display: block;
}
.prm-hl-sub {
  font-size: 18rpx;
  color: #9ca3af;
  margin-top: 4rpx;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.prm-critique-box {
  background: #181624;
  border: 1rpx solid rgba(192, 132, 252, 0.38);
  border-radius: 22rpx;
  padding: 20rpx;
}
.prm-critique-title {
  font-size: 23rpx;
  font-weight: 800;
  color: #c084fc;
  display: block;
  margin-bottom: 8rpx;
}
.prm-critique-txt {
  font-size: 22rpx;
  color: #e4e4e7;
  line-height: 1.55;
  display: block;
}
.prm-footer-qr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding-top: 18rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.1);
}
.prm-fq-left {
  flex: 1;
}
.prm-fq-brand {
  font-size: 20rpx;
  font-weight: 700;
  color: #fc4c02;
  display: block;
}
.prm-fq-main {
  font-size: 24rpx;
  font-weight: 900;
  color: #ffffff;
  margin-top: 4rpx;
  display: block;
}
.prm-fq-sub {
  font-size: 19rpx;
  color: #9ca3af;
  margin-top: 4rpx;
  display: block;
}
.prm-fq-right {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4rpx;
  flex-shrink: 0;
}
.prm-qr-frame {
  background: #ffffff;
  padding: 8rpx;
  border-radius: 16rpx;
}
.prm-qr-img {
  width: 108rpx;
  height: 108rpx;
}
.prm-qr-cap {
  font-size: 17rpx;
  color: #9ca3af;
}
.prm-text-box {
  background: #0e0e11;
  border: 1rpx solid rgba(16, 185, 129, 0.35);
  border-radius: 24rpx;
  padding: 22rpx;
}
.prm-text-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12rpx;
}
.prm-text-title {
  font-size: 23rpx;
  font-weight: 800;
  color: #34d399;
}
.prm-text-hint {
  font-size: 19rpx;
  color: #71717a;
}
.prm-text-card {
  background: rgba(0, 0, 0, 0.55);
  border-radius: 18rpx;
  padding: 20rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.06);
}
.prm-text-content {
  font-size: 22rpx;
  color: #e4e4e7;
  line-height: 1.6;
  white-space: pre-wrap;
}
.prm-footer-actions {
  display: flex;
  gap: 12rpx;
  padding-top: 14rpx;
  margin-top: 10rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}
.prm-btn {
  margin: 0;
  min-width: 0;
  height: 76rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  border-radius: 20rpx;
  font-size: 23rpx;
  font-weight: 800;
  padding: 0 20rpx;
}
.prm-btn::after {
  border: none;
}
.prm-btn.primary {
  flex: 1;
  background: linear-gradient(90deg, #f59e0b, #d97706);
  color: #09090b;
  font-size: 26rpx;
}
.prm-btn.save {
  flex: 1;
  background: rgba(252, 76, 2, 0.2);
  color: #fc4c02;
  border: 1rpx solid rgba(252, 76, 2, 0.45);
  font-size: 26rpx;
}
.prm-btn.copy {
  flex: 1;
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1rpx solid rgba(16, 185, 129, 0.45);
}

/* ── ☀️ 明亮主题 (Volt v3.0 / Light Mode) 60-30-10 适配 ── */
.prm-light .prm-dialog {
  background: #ffffff;
  border-color: #e2e8f0;
  box-shadow: 0 24rpx 64rpx rgba(15, 23, 42, 0.18);
}
.prm-light .prm-title {
  color: #0F172A;
}
.prm-light .prm-close {
  background: #f1f5f9;
  color: #475569;
}
.prm-light .prm-period-btn,
.prm-light .prm-offset-btn {
  background: #F8FAFC;
  color: #475569;
  border-color: #e2e8f0;
}
.prm-light .prm-period-btn.active {
  background: #FC4C02;
  color: #FFFFFF;
  border-color: #FC4C02;
}
.prm-light .prm-offset-btn.active {
  background: #FFF5EE;
  color: #C23800;
  border-color: rgba(252, 76, 2, 0.36);
}
.prm-light .prm-filter-box {
  background: #f8fafc;
  border-color: #e2e8f0;
}
.prm-light .prm-filter-title {
  color: #0F172A;
}
.prm-light .prm-trail-hint {
  color: #059669;
}
.prm-light .prm-trail-tab,
.prm-light .prm-theme-chip {
  background: #ffffff;
  color: #475569;
  border-color: #e2e8f0;
}
.prm-light .prm-trail-tab.active,
.prm-light .prm-theme-chip.active {
  background: #FFF5EE;
  color: #C23800;
  border-color: rgba(252, 76, 2, 0.36);
}
.prm-light .prm-upload-pill {
  background: #FFF5EE;
  border-color: rgba(252, 76, 2, 0.36);
  color: #C23800;
}
.prm-light .prm-reset-photo {
  color: #64748b;
}
.prm-light .prm-view-tabs {
  background: #f1f5f9;
}
.prm-light .prm-view-tab {
  color: #475569;
}
.prm-light .prm-view-tab.active {
  background: linear-gradient(135deg, #FC4C02 0%, #EA580C 100%);
  color: #FFFFFF;
}
.prm-light .prm-loading-txt {
  color: #475569;
}
.prm-light .prm-poster-card {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-color: #e2e8f0;
  box-shadow: 0 8rpx 28rpx rgba(15, 23, 42, 0.06);
}
.prm-light .prm-cover-overlay {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.08) 0%, rgba(15, 23, 42, 0.72) 100%);
}
.prm-light .prm-hero-box {
  background: #F8FAFC;
  border-color: #E2E8F0;
}
.prm-light .prm-hero-lbl {
  color: #475569;
}
.prm-light .prm-hero-num {
  color: #FC4C02;
}
.prm-light .prm-hero-unit {
  color: #0F172A;
}
.prm-light .prm-target-lbl {
  color: #475569;
}
.prm-light .prm-target-pct {
  color: #C23800;
}
.prm-light .prm-prog-bg {
  background: #F1F5F9;
}
.prm-light .prm-prog-fill {
  background: linear-gradient(90deg, #FC4C02, #EA580C);
}
.prm-light .prm-meta-txt {
  color: #475569;
}
.prm-light .prm-meta-ok {
  color: #059669;
}
.prm-light .prm-stat-cell {
  background: #F8FAFC;
  border-color: #e2e8f0;
}
.prm-light .prm-stat-label {
  color: #475569;
}
.prm-light .prm-stat-val {
  color: #0F172A;
}
.prm-light .prm-hl-card.sky,
.prm-light .prm-hl-card.amber {
  background: #F8FAFC;
  border-color: #E2E8F0;
}
.prm-light .prm-hl-tag.sky,
.prm-light .prm-hl-tag.amber {
  color: #C23800;
}
.prm-light .prm-hl-main {
  color: #0F172A;
}
.prm-light .prm-hl-sub {
  color: #475569;
}
.prm-light .prm-critique-box {
  background: #F8FAFC;
  border-color: #E2E8F0;
}
.prm-light .prm-critique-title {
  color: #0F172A;
}
.prm-light .prm-critique-txt {
  color: #334155;
}
.prm-light .prm-footer-qr {
  border-top-color: #e2e8f0;
}
.prm-light .prm-fq-brand {
  color: #FC4C02;
}
.prm-light .prm-fq-main {
  color: #0F172A;
}
.prm-light .prm-fq-sub,
.prm-light .prm-qr-cap {
  color: #475569;
}
.prm-light .prm-qr-frame {
  border: 1rpx solid #e2e8f0;
}
.prm-light .prm-text-box {
  background: #f8fafc;
  border-color: #e2e8f0;
}
.prm-light .prm-text-title {
  color: #0F172A;
}
.prm-light .prm-text-hint {
  color: #64748b;
}
.prm-light .prm-text-card {
  background: #ffffff;
  border-color: #e2e8f0;
}
.prm-light .prm-text-content {
  color: #1e293b;
}
.prm-light .prm-footer-actions {
  border-top-color: #e2e8f0;
}
.prm-light .prm-btn.primary {
  background: linear-gradient(135deg, #FC4C02 0%, #EA580C 100%);
  color: #FFFFFF;
}
.prm-light .prm-btn.save {
  background: #FFF5EE;
  color: #C23800;
  border: 1rpx solid rgba(252, 76, 2, 0.36);
}
.prm-light .prm-btn.copy {
  background: linear-gradient(135deg, #FC4C02 0%, #EA580C 100%);
  color: #ffffff;
  border: none;
}
</style>
