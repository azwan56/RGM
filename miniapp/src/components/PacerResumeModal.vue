<template>
  <view
    v-if="visible && evalData"
    class="prm-mask"
    :class="[themeClass, { 'prm-light': isVolt }]"
    @click="handleClose"
    @touchmove.stop.prevent
  >
    <view class="prm-dialog" @click.stop>
      <view class="prm-header">
        <text class="prm-title">🐰 官兔竞选履历与分享卡</text>
        <view class="prm-close" @click="handleClose">✕</view>
      </view>

      <scroll-view scroll-y class="prm-scroll">
        <view class="prm-controls">
          <!-- 版式切换 -->
          <view class="prm-row">
            <text class="prm-label">版式：</text>
            <view class="prm-pills">
              <view
                class="prm-pill"
                :class="{ active: posterMode === 'resume' }"
                @click="switchMode('resume')"
              >
                📋 竞选履历长图
              </view>
              <view
                class="prm-pill"
                :class="{ active: posterMode === 'social' }"
                @click="switchMode('social')"
              >
                📸 社交晒图海报
              </view>
            </view>
          </view>

          <!-- 署名切换 -->
          <view class="prm-row">
            <text class="prm-label">署名：</text>
            <view class="prm-pills">
              <view
                class="prm-pill"
                :class="{ active: !useRealName }"
                @click="toggleRealName(false)"
              >
                昵称展示
              </view>
              <view
                class="prm-pill"
                :class="{ active: useRealName, disabled: !hasRealName }"
                @click="hasRealName && toggleRealName(true)"
              >
                {{ hasRealName ? "实名展示" : "实名(未填)" }}
              </view>
            </view>
          </view>

          <!-- 底色或选照片 -->
          <view v-if="posterMode === 'resume'" class="prm-row">
            <text class="prm-label">底色：</text>
            <view class="prm-pills">
              <view
                class="prm-pill"
                :class="{ active: !posterLight }"
                @click="toggleTheme(false)"
              >
                曜石暗色
              </view>
              <view
                class="prm-pill"
                :class="{ active: posterLight }"
                @click="toggleTheme(true)"
              >
                清爽白底
              </view>
            </view>
          </view>
          <view v-else class="prm-row">
            <text class="prm-label">照片：</text>
            <view class="prm-pills">
              <view class="prm-pill active" @click="chooseSocialPhoto">
                🖼️ {{ userPhotoPath ? "更换赛道照" : "上传领跑/完赛照" }}
              </view>
              <view v-if="userPhotoPath" class="prm-pill" @click="clearSocialPhoto">
                默认渐变
              </view>
            </view>
          </view>
        </view>

        <view class="prm-preview-wrap">
          <view v-if="rendering" class="prm-loading">正在绘制高清履历海报...</view>
          <image
            v-else-if="posterUrl"
            :src="posterUrl"
            mode="widthFix"
            class="prm-preview-img"
            @click="previewFullImage"
          />
        </view>
      </scroll-view>

      <view class="prm-actions">
        <button class="prm-btn ghost" :disabled="!posterUrl" @click="shareImageToChat">
          📤 转发好友
        </button>
        <button class="prm-btn primary" :disabled="!posterUrl" @click="saveToAlbum">
          💾 保存到相册
        </button>
      </view>

      <canvas
        canvas-id="pacerResumeCanvas"
        id="pacerResumeCanvas"
        class="prm-hidden-canvas"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, getCurrentInstance } from "vue";
import { setTabBarHidden } from "../utils/api";
import { isVolt, themeClass } from "../utils/theme";

const props = defineProps<{
  visible: boolean;
  evalData: any;
}>();

const emit = defineEmits(["close"]);
const instance = getCurrentInstance();

const posterMode = ref<"resume" | "social">("resume");
const useRealName = ref<boolean>(false);
const posterLight = ref<boolean>(false);
const userPhotoPath = ref<string>("");
const posterUrl = ref<string>("");
const rendering = ref<boolean>(false);

const hasRealName = computed(() => Boolean(props.evalData?.runner?.real_name));

watch(
  () => props.visible,
  (val) => {
    setTabBarHidden(Boolean(val));
    if (val) {
      posterLight.value = Boolean(isVolt.value);
      nextTick(() => {
        setTimeout(() => drawPoster(), 100);
      });
    }
  }
);

function handleClose() {
  setTabBarHidden(false);
  emit("close");
}

function switchMode(m: "resume" | "social") {
  posterMode.value = m;
  nextTick(() => drawPoster());
}

function toggleRealName(v: boolean) {
  useRealName.value = v;
  nextTick(() => drawPoster());
}

function toggleTheme(v: boolean) {
  posterLight.value = v;
  nextTick(() => drawPoster());
}

function chooseSocialPhoto() {
  uni.chooseImage({
    count: 1,
    sizeType: ["compressed"],
    sourceType: ["album", "camera"],
    success: (res) => {
      const p = res.tempFilePaths?.[0];
      if (p) {
        userPhotoPath.value = p;
        nextTick(() => drawPoster());
      }
    },
  });
}

function clearSocialPhoto() {
  userPhotoPath.value = "";
  nextTick(() => drawPoster());
}

function fillRoundRect(ctx: any, x: number, y: number, w: number, h: number, r: number, color: string) {
  const rad = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rad, y);
  ctx.arcTo(x + w, y, x + w, y + h, rad);
  ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad);
  ctx.arcTo(x, y, x + w, y, rad);
  ctx.closePath();
  ctx.setFillStyle(color);
  ctx.fill();
}

function drawPoster() {
  if (!props.visible || !props.evalData) return;
  const ctx = uni.createCanvasContext("pacerResumeCanvas", instance?.proxy as any);
  if (!ctx) return;

  rendering.value = true;
  const W = 750;
  const H = posterMode.value === "resume" ? 1240 : 1080;

  const runner = props.evalData.runner || {};
  const cred = props.evalData.pacer_credentials_summary || {};
  const calib = props.evalData.event_calibration || {};
  const sel = props.evalData.selected_evaluation || {};
  const dims: any[] = sel.dimensions || [];
  const months: any[] = props.evalData.monthly_mileage_6m || [];
  const showcase = props.evalData.showcase_run || null;
  const races: any[] = (props.evalData.verified_races || []).slice(0, 3);

  const dispName =
    useRealName.value && runner.real_name ? String(runner.real_name) : String(runner.display_name || "RGM 跑者");
  const paceTxt = sel.target_pace_str
    ? String(sel.target_pace_str).endsWith("/km")
      ? sel.target_pace_str
      : `${sel.target_pace_str}/km`
    : "--";

  if (posterMode.value === "resume") {
    const light = posterLight.value;
    ctx.setFillStyle(light ? "#F4F6FA" : "#0B0C10");
    ctx.fillRect(0, 0, W, H);

    const textMain = light ? "#0F172A" : "#FFFFFF";
    const textSub = light ? "#64748B" : "#94A3B8";
    const cardBg = light ? "#FFFFFF" : "#151720";

    // Top badge
    fillRoundRect(ctx, 36, 36, 220, 36, 18, "#FC4C02");
    ctx.setFillStyle("#FFFFFF");
    ctx.setFontSize(17);
    ctx.fillText("🐰 官兔竞选履历卡", 54, 60);

    if (runner.watch_verified_label) {
      ctx.setFillStyle("#10B981");
      ctx.setFontSize(16);
      ctx.setTextAlign("right");
      ctx.fillText(`⌚ ${runner.watch_verified_label}`, W - 36, 60);
      ctx.setTextAlign("left");
    }

    // Event & Group Title
    ctx.setFillStyle(textMain);
    ctx.setFontSize(32);
    ctx.fillText(`${calib.event_name || "马拉松"} · ${sel.group_label || "官兔"}`.slice(0, 18), 36, 118);

    ctx.setFillStyle(textSub);
    ctx.setFontSize(17);
    ctx.fillText(
      `${calib.race_level || "认证赛事"} · 配速 ${paceTxt} · 误差要求 ±${calib.target_gun_error_sec || 45}s`,
      36,
      148
    );

    // Hero Identity + Score Card
    fillRoundRect(ctx, 36, 172, W - 72, 180, 22, cardBg);
    ctx.setFillStyle(textMain);
    ctx.setFontSize(26);
    ctx.fillText(dispName, 60, 218);

    const tags: string[] = [];
    if (runner.age) tags.push(`${runner.age}岁`);
    if (runner.first_aid_cert_type && runner.first_aid_cert_label) {
      tags.push(runner.first_aid_cert_label);
    }
    ctx.setFillStyle(textSub);
    ctx.setFontSize(16);
    ctx.fillText(tags.join(" · ") || "跑团认证队员", 60, 246);

    const kvs = [
      { k: "认证PB", v: sel.cert_finish_str || "待填" },
      { k: "当期预测", v: sel.pred_finish_str || "--" },
      { k: "领跑履历", v: `官兔${cred.official_pacer_count || 0}·领跑${cred.club_pacer_total_count || 0}` },
    ];
    kvs.forEach((it, idx) => {
      const bx = 60 + idx * 158;
      fillRoundRect(ctx, bx, 266, 146, 66, 12, light ? "#F1F5F9" : "#1E212D");
      ctx.setFillStyle(textSub);
      ctx.setFontSize(14);
      ctx.fillText(it.k, bx + 12, 290);
      ctx.setFillStyle(textMain);
      ctx.setFontSize(17);
      ctx.fillText(String(it.v).slice(0, 11), bx + 12, 318);
    });

    // Score circle on right
    const cx = W - 116;
    const cy = 262;
    ctx.beginPath();
    ctx.arc(cx, cy, 56, 0, Math.PI * 2);
    ctx.setStrokeStyle(sel.verdict_color || "#10B981");
    ctx.setLineWidth(8);
    ctx.stroke();

    ctx.setTextAlign("center");
    ctx.setFillStyle(textMain);
    ctx.setFontSize(34);
    ctx.fillText(`${sel.overall_score || 0}`, cx, cy + 8);
    ctx.setFillStyle(sel.verdict_color || "#10B981");
    ctx.setFontSize(15);
    ctx.fillText(`${sel.grade || "A"}级`, cx, cy + 32);
    ctx.setTextAlign("left");

    // 6-Dimension Card
    fillRoundRect(ctx, 36, 372, W - 72, 248, 22, cardBg);
    ctx.setFillStyle(textMain);
    ctx.setFontSize(20);
    ctx.fillText("📊 六维官兔胜任度评分", 60, 408);

    ctx.setTextAlign("right");
    ctx.setFillStyle(sel.verdict_color || "#10B981");
    ctx.setFontSize(16);
    ctx.fillText(String(sel.verdict_label || "").slice(0, 18), W - 60, 408);
    ctx.setTextAlign("left");

    dims.slice(0, 6).forEach((d, idx) => {
      const col = idx % 2;
      const row = Math.floor(idx / 2);
      const dx = 60 + col * 320;
      const dy = 440 + row * 58;
      const bw = 290;

      ctx.setFillStyle(textMain);
      ctx.setFontSize(16);
      ctx.fillText(d.label, dx, dy);

      ctx.setTextAlign("right");
      ctx.setFillStyle("#FC4C02");
      ctx.fillText(`${d.score}分`, dx + bw, dy);
      ctx.setTextAlign("left");

      fillRoundRect(ctx, dx, dy + 10, bw, 10, 5, light ? "#E2E8F0" : "#252836");
      const fw = Math.max(12, (bw * Math.min(100, Number(d.score || 0))) / 100);
      fillRoundRect(
        ctx,
        dx,
        dy + 10,
        fw,
        10,
        5,
        Number(d.score || 0) >= 80 ? "#10B981" : Number(d.score || 0) >= 65 ? "#F59E0B" : "#EF4444"
      );

      ctx.setFillStyle(textSub);
      ctx.setFontSize(13);
      ctx.fillText(String(d.display_value || "").slice(0, 20), dx, dy + 36);
    });

    // Dual Charts Row (6m Mileage + Showcase 1km Curve)
    const cy0 = 640;
    const ch = 260;
    const hw = (W - 72 - 18) / 2;

    fillRoundRect(ctx, 36, cy0, hw, ch, 22, cardBg);
    ctx.setFillStyle(textMain);
    ctx.setFontSize(18);
    ctx.fillText("🗓️ 近6个月跑量(km)", 56, cy0 + 36);

    if (months.length > 0) {
      const maxK = Math.max(80, ...months.map((m) => Number(m.km || 0)));
      const btm = cy0 + ch - 40;
      const step = (hw - 44) / months.length;
      months.forEach((m, idx) => {
        const kv = Number(m.km || 0);
        const bh = Math.max(6, (kv / maxK) * 140);
        const bx = 56 + idx * step;
        fillRoundRect(ctx, bx, btm - bh, 26, bh, 6, kv >= 180 ? "#10B981" : "#FC4C02");
        ctx.setTextAlign("center");
        ctx.setFillStyle(textMain);
        ctx.setFontSize(12);
        ctx.fillText(`${Math.round(kv)}`, bx + 13, btm - bh - 6);
        ctx.setFillStyle(textSub);
        ctx.fillText(m.short_label || "", bx + 13, btm + 20);
        ctx.setTextAlign("left");
      });
    }

    const rx = 36 + hw + 18;
    fillRoundRect(ctx, rx, cy0, hw, ch, 22, cardBg);
    ctx.setFillStyle(textMain);
    ctx.setFontSize(18);
    ctx.fillText("⏱️ 稳态巡航分段", rx + 20, cy0 + 36);

    if (showcase?.splits_series?.length >= 3) {
      ctx.setTextAlign("right");
      ctx.setFillStyle("#10B981");
      ctx.setFontSize(14);
      ctx.fillText(`±${showcase.sigma_gap_sec}s/km`, rx + hw - 20, cy0 + 36);
      ctx.setTextAlign("left");

      ctx.setFillStyle(textSub);
      ctx.setFontSize(13);
      ctx.fillText(`${showcase.distance_km}km · ${showcase.avg_pace_str}`, rx + 20, cy0 + 60);

      const sp = showcase.splits_series;
      const avgP = Number(showcase.avg_pace_sec || 300);
      const vals = sp.map((s: any) => Number(s.pace_sec || avgP));
      const minP = Math.min(avgP - 22, ...vals);
      const maxP = Math.max(avgP + 22, ...vals);
      const px0 = rx + 22;
      const pw = hw - 44;
      const py0 = cy0 + 84;
      const ph = 130;

      ctx.setStrokeStyle("#FC4C02");
      ctx.setLineWidth(2.5);
      ctx.beginPath();
      sp.forEach((pt: any, idx: number) => {
        const x = px0 + (idx / Math.max(1, sp.length - 1)) * pw;
        const y = py0 + ((Number(pt.pace_sec) - minP) / Math.max(1, maxP - minP)) * ph;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    } else {
      ctx.setFillStyle(textSub);
      ctx.setFontSize(14);
      ctx.fillText("同步12km+稳态跑后自动绘制", rx + 20, cy0 + 140);
    }

    // Verified Races Card
    const ry0 = 920;
    fillRoundRect(ctx, 36, ry0, W - 72, 236, 22, cardBg);
    ctx.setFillStyle(textMain);
    ctx.setFontSize(19);
    ctx.fillText("🏅 近期认证完赛与官兔记录", 60, ry0 + 38);

    if (races.length > 0) {
      races.forEach((r, idx) => {
        const yy = ry0 + 78 + idx * 48;
        ctx.setFillStyle(textMain);
        ctx.setFontSize(16);
        ctx.fillText(`${r.date || ""} ${String(r.name || "").slice(0, 13)}`, 60, yy);
        if (r.was_official_pacer) {
          ctx.setFillStyle("#FC4C02");
          ctx.fillText("🐰官兔", 430, yy);
        }
        ctx.setTextAlign("right");
        ctx.setFillStyle("#10B981");
        ctx.fillText(r.finish_time || "--", W - 60, yy);
        ctx.setTextAlign("left");
      });
    } else {
      ctx.setFillStyle(textSub);
      ctx.setFontSize(15);
      ctx.fillText("可在「我的 - 赛事计划」补充往届完赛与官兔经历", 60, ry0 + 120);
    }

    ctx.setFillStyle(textSub);
    ctx.setFontSize(15);
    ctx.fillText("万跑跑团助手 · 官兔胜任度量化评估系统", 36, H - 36);
  } else {
    // Social Mode (750 x 1080)
    ctx.setFillStyle("#090A0F");
    ctx.fillRect(0, 0, W, H);

    if (userPhotoPath.value) {
      ctx.drawImage(userPhotoPath.value, 0, 0, W, 620);
    } else {
      ctx.setFillStyle("#1F1638");
      ctx.fillRect(0, 0, W, 620);
    }

    // Dark overlay band
    ctx.setFillStyle("rgba(9,10,15,0.75)");
    ctx.fillRect(0, 440, W, 185);

    fillRoundRect(ctx, 36, 36, 240, 38, 19, "rgba(9,10,15,0.7)");
    ctx.setFillStyle("#FFFFFF");
    ctx.setFontSize(16);
    ctx.fillText("🐰 RGM 官兔胜任度报告", 54, 61);

    ctx.setFillStyle("#FC4C02");
    ctx.setFontSize(22);
    ctx.fillText(calib.event_name || "马拉松官方配速员评估", 44, 486);

    ctx.setFillStyle("#FFFFFF");
    ctx.setFontSize(46);
    ctx.fillText(`${sel.group_label || "官兔"} · ${sel.overall_score || 0}分`, 44, 546);

    ctx.setFillStyle(sel.verdict_color || "#10B981");
    ctx.setFontSize(20);
    ctx.fillText(`${dispName} | ${sel.verdict_label || ""}`.slice(0, 26), 44, 588);

    dims.slice(0, 6).forEach((d, idx) => {
      const col = idx % 3;
      const row = Math.floor(idx / 3);
      const gx = 36 + col * 230;
      const gy = 648 + row * 156;
      fillRoundRect(ctx, gx, gy, 218, 138, 18, "#151722");
      ctx.setFillStyle("#94A3B8");
      ctx.setFontSize(15);
      ctx.fillText(d.label, gx + 18, gy + 34);
      ctx.setFillStyle("#FFFFFF");
      ctx.setFontSize(34);
      ctx.fillText(`${d.score}`, gx + 18, gy + 84);
      ctx.setFillStyle("#CBD5E1");
      ctx.setFontSize(13);
      ctx.fillText(String(d.display_value || "").slice(0, 13), gx + 18, gy + 116);
    });

    ctx.setFillStyle("#94A3B8");
    ctx.setFontSize(16);
    ctx.fillText(`配速 ${paceTxt} · 当期实力 ${sel.pred_finish_str || "--"}`, 44, H - 42);
  }

  ctx.draw(false, () => {
    setTimeout(() => {
      uni.canvasToTempFilePath(
        {
          canvasId: "pacerResumeCanvas",
          width: W,
          height: H,
          destWidth: W * 2,
          destHeight: H * 2,
          success: (res) => {
            posterUrl.value = res.tempFilePath;
            rendering.value = false;
          },
          fail: () => {
            rendering.value = false;
          },
        },
        instance?.proxy as any
      );
    }, 180);
  });
}

function previewFullImage() {
  if (!posterUrl.value) return;
  uni.previewImage({ urls: [posterUrl.value] });
}

function shareImageToChat() {
  if (!posterUrl.value) return;
  const anyUni = uni as any;
  if (typeof anyUni.showShareImageMenu === "function") {
    anyUni.showShareImageMenu({ path: posterUrl.value });
  } else {
    previewFullImage();
  }
}

function saveToAlbum() {
  if (!posterUrl.value) return;
  uni.saveImageToPhotosAlbum({
    filePath: posterUrl.value,
    success: () => {
      uni.showToast({ title: "已保存到手机相册", icon: "success" });
    },
    fail: () => {
      uni.showToast({ title: "可点击图片长按保存", icon: "none" });
    },
  });
}
</script>

<style scoped>
.prm-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(0, 0, 0, 0.78);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24rpx;
}
.prm-dialog {
  width: 100%;
  max-height: 90vh;
  background: #14151c;
  border-radius: 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.prm-light .prm-dialog {
  background: #ffffff;
  border-color: rgba(15, 23, 42, 0.1);
}
.prm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 26rpx 30rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.08);
}
.prm-title {
  font-size: 30rpx;
  font-weight: 800;
  color: #ffffff;
}
.prm-light .prm-title {
  color: #0f172a;
}
.prm-close {
  font-size: 32rpx;
  color: #94a3b8;
  padding: 6rpx 12rpx;
}
.prm-scroll {
  flex: 1;
  max-height: 70vh;
}
.prm-controls {
  padding: 20rpx 28rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.prm-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.prm-label {
  font-size: 24rpx;
  color: #94a3b8;
  width: 84rpx;
  flex-shrink: 0;
}
.prm-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}
.prm-pill {
  padding: 10rpx 22rpx;
  border-radius: 999rpx;
  font-size: 23rpx;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
}
.prm-light .prm-pill {
  background: #f1f5f9;
  color: #334155;
}
.prm-pill.active {
  background: #fc4c02;
  color: #ffffff;
}
.prm-pill.disabled {
  opacity: 0.4;
}
.prm-preview-wrap {
  padding: 12rpx 28rpx 28rpx;
  display: flex;
  justify-content: center;
}
.prm-preview-img {
  width: 100%;
  border-radius: 20rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.1);
}
.prm-loading {
  padding: 80rpx 0;
  font-size: 26rpx;
  color: #94a3b8;
}
.prm-actions {
  display: flex;
  gap: 20rpx;
  padding: 20rpx 28rpx 28rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.08);
}
.prm-btn {
  flex: 1;
  min-width: 0;
  height: 80rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 16rpx;
  white-space: nowrap;
  border-radius: 20rpx;
  font-size: 26rpx;
  font-weight: 800;
}
.prm-btn::after {
  border: none;
}
.prm-btn.ghost {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}
.prm-light .prm-btn.ghost {
  background: #f1f5f9;
  color: #0f172a;
}
.prm-btn.primary {
  background: linear-gradient(135deg, #fc4c02, #f59e0b);
  color: #ffffff;
}
.prm-hidden-canvas {
  position: fixed;
  left: -9999px;
  top: -9999px;
  width: 750px;
  height: 1280px;
}
</style>
