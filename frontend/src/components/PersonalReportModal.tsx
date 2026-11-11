"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Calendar,
  Image as ImageIcon,
  MessageCircle,
  Loader2,
  Sparkles,
  Copy,
  Check,
  Upload,
  Trophy,
  Zap,
  Mountain,
  Clock,
  Activity,
} from "lucide-react";
import apiClient from "@/lib/apiClient";

interface PersonalReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
  defaultPeriodType?: "week" | "month";
}

interface PresetTheme {
  id: string;
  name: string;
  subtitle: string;
  accent: string;
  bgGradient: [string, string, string];
  coverSvgDataUrl: string;
}

function makeSvgCover(
  c1: string,
  c2: string,
  accent: string,
  motif: "dawn" | "night" | "mountain" | "track" | "forest" | "minimal"
): string {
  let shapes = "";
  if (motif === "dawn") {
    shapes = `
      <circle cx="580" cy="120" r="95" fill="${accent}" fill-opacity="0.28"/>
      <circle cx="580" cy="120" r="55" fill="${accent}" fill-opacity="0.45"/>
      <path d="M0 240 Q 220 170 420 210 T 750 185 L 750 320 L 0 320 Z" fill="#0f172a" fill-opacity="0.65"/>
      <path d="M0 270 Q 300 210 550 245 T 750 230 L 750 320 L 0 320 Z" fill="#090d16" fill-opacity="0.88"/>
    `;
  } else if (motif === "night") {
    shapes = `
      <rect x="70" y="90" width="38" height="190" fill="#38bdf8" fill-opacity="0.12"/>
      <rect x="125" y="65" width="48" height="215" fill="#818cf8" fill-opacity="0.15"/>
      <rect x="190" y="110" width="35" height="170" fill="#38bdf8" fill-opacity="0.1"/>
      <rect x="510" y="75" width="52" height="205" fill="#f43f5e" fill-opacity="0.14"/>
      <rect x="580" y="105" width="42" height="175" fill="#38bdf8" fill-opacity="0.14"/>
      <path d="M0 255 Q 260 220 520 250 T 750 235 L 750 320 L 0 320 Z" fill="#090d16" fill-opacity="0.9"/>
    `;
  } else if (motif === "mountain") {
    shapes = `
      <polygon points="60,280 230,85 395,280" fill="#1e293b" fill-opacity="0.75"/>
      <polygon points="260,280 465,55 660,280" fill="${accent}" fill-opacity="0.24"/>
      <polygon points="430,280 595,105 740,280" fill="#0f172a" fill-opacity="0.8"/>
      <path d="M0 265 L 750 265 L 750 320 L 0 320 Z" fill="#090d16" fill-opacity="0.92"/>
    `;
  } else if (motif === "track") {
    shapes = `
      <path d="M-40 290 Q 260 120 790 80" stroke="${accent}" stroke-width="18" stroke-opacity="0.22" fill="none"/>
      <path d="M-20 315 Q 280 145 790 110" stroke="${accent}" stroke-width="10" stroke-opacity="0.35" fill="none"/>
      <path d="M0 340 Q 300 170 790 140" stroke="#ffffff" stroke-width="4" stroke-opacity="0.18" fill="none"/>
    `;
  } else if (motif === "forest") {
    shapes = `
      <circle cx="140" cy="180" r="85" fill="#10b981" fill-opacity="0.16"/>
      <circle cx="260" cy="150" r="105" fill="#059669" fill-opacity="0.18"/>
      <circle cx="580" cy="165" r="95" fill="#10b981" fill-opacity="0.15"/>
      <path d="M0 250 Q 240 195 490 235 T 750 215 L 750 320 L 0 320 Z" fill="#090d16" fill-opacity="0.9"/>
    `;
  } else {
    shapes = `
      <circle cx="620" cy="95" r="120" fill="${accent}" fill-opacity="0.14"/>
      <circle cx="120" cy="240" r="140" fill="${accent}" fill-opacity="0.08"/>
    `;
  }

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="750" height="320" viewBox="0 0 750 320">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="${c1}"/>
        <stop offset="100%" stop-color="${c2}"/>
      </linearGradient>
    </defs>
    <rect width="750" height="320" fill="url(#g)"/>
    ${shapes}
  </svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const PRESET_THEMES: PresetTheme[] = [
  {
    id: "dawn",
    name: "🌅 晨曦破晓",
    subtitle: "第一缕晨光下的有氧征途",
    accent: "#fc4c02",
    bgGradient: ["#1c1210", "#141622", "#0b0d13"],
    coverSvgDataUrl: makeSvgCover("#3b170e", "#131829", "#fc4c02", "dawn"),
  },
  {
    id: "night",
    name: "🌃 城市夜跑",
    subtitle: "霓虹晚风里的节奏巡航",
    accent: "#38bdf8",
    bgGradient: ["#0d1526", "#131728", "#090b12"],
    coverSvgDataUrl: makeSvgCover("#0f2442", "#171430", "#38bdf8", "night"),
  },
  {
    id: "mountain",
    name: "🏔️ 山野之巅",
    subtitle: "翻越山脊与爬升的自由",
    accent: "#f59e0b",
    bgGradient: ["#171510", "#131722", "#0a0c12"],
    coverSvgDataUrl: makeSvgCover("#292111", "#111827", "#f59e0b", "mountain"),
  },
  {
    id: "track",
    name: "🏟️ 热血跑道",
    subtitle: "间歇与配速的精准刻度",
    accent: "#f43f5e",
    bgGradient: ["#211018", "#151622", "#0b0c12"],
    coverSvgDataUrl: makeSvgCover("#381220", "#131626", "#f43f5e", "track"),
  },
  {
    id: "forest",
    name: "🌲 森系绿道",
    subtitle: "林间富氧慢跑的呼吸律动",
    accent: "#10b981",
    bgGradient: ["#0d1f1a", "#121822", "#0a0d12"],
    coverSvgDataUrl: makeSvgCover("#0d2e24", "#111827", "#10b981", "forest"),
  },
  {
    id: "minimal",
    name: "🖤 黑金荣耀",
    subtitle: "纯粹数据与耐力美学",
    accent: "#eab308",
    bgGradient: ["#181611", "#12141c", "#090a0f"],
    coverSvgDataUrl: makeSvgCover("#241f12", "#10121a", "#eab308", "minimal"),
  },
];

export default function PersonalReportModal({
  isOpen,
  onClose,
  userId,
  defaultPeriodType = "week",
}: PersonalReportModalProps) {
  const [periodType, setPeriodType] = useState<"week" | "month">(defaultPeriodType);
  const [periodOffset, setPeriodOffset] = useState<number>(0);
  const [trailMode, setTrailMode] = useState<"include" | "exclude_pace" | "exclude_all">("include");
  const [viewMode, setViewMode] = useState<"poster" | "text">("poster");
  const [reportData, setReportData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  // Image selection state
  const [selectedPresetId, setSelectedPresetId] = useState<string>("dawn");
  const [customImageDataUrl, setCustomImageDataUrl] = useState<string | null>(null);
  const [customImageName, setCustomImageName] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activePreset = PRESET_THEMES.find((t) => t.id === selectedPresetId) || PRESET_THEMES[0];
  const activeCoverUrl = customImageDataUrl || activePreset.coverSvgDataUrl;

  useEffect(() => {
    if (isOpen && userId) {
      fetchPersonalReport(periodType, periodOffset, trailMode);
    }
  }, [isOpen, userId]);

  async function fetchPersonalReport(
    pType: "week" | "month" = periodType,
    offset: number = periodOffset,
    tMode: "include" | "exclude_pace" | "exclude_all" = trailMode
  ) {
    if (!userId) return;
    setLoading(true);
    try {
      let url = `/api/science/personal-report/${encodeURIComponent(userId)}?period_type=${pType}&trail_mode=${tMode}`;
      if (offset === -1) {
        const now = new Date();
        if (pType === "week") {
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
      const res = await apiClient.get(url);
      setReportData(res.data);
    } catch (err: any) {
      console.error("fetchPersonalReport error:", err);
    } finally {
      setLoading(false);
    }
  }

  function handleSwitchPeriod(type: "week" | "month") {
    setPeriodType(type);
    setPeriodOffset(0);
    fetchPersonalReport(type, 0, trailMode);
  }

  function handleSwitchOffset(offset: number) {
    setPeriodOffset(offset);
    fetchPersonalReport(periodType, offset, trailMode);
  }

  function handleSwitchTrailMode(mode: "include" | "exclude_pace" | "exclude_all") {
    setTrailMode(mode);
    fetchPersonalReport(periodType, periodOffset, mode);
  }

  function handleUploadCustomImage(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setCustomImageDataUrl(reader.result);
        setCustomImageName(file.name);
      }
    };
    reader.readAsDataURL(file);
  }

  function handleCopyText() {
    if (!reportData?.forward_text) return;
    navigator.clipboard.writeText(reportData.forward_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  function drawRoundedRect(
    ctx: CanvasRenderingContext2D,
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
      ctx.fillStyle = fillStyle;
      ctx.fill();
    }
    if (strokeStyle) {
      ctx.strokeStyle = strokeStyle;
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawWrappedText(
    ctx: CanvasRenderingContext2D,
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

  async function handleDownloadPoster() {
    if (!reportData) return;
    const canvas = document.createElement("canvas");
    const W = 750;
    const H = 1380;
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rep = reportData;
    const isLight =
      typeof document !== "undefined" &&
      document.documentElement.classList.contains("theme-light");

    // 1. Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    if (isLight) {
      bgGrad.addColorStop(0, "#F8FAFC");
      bgGrad.addColorStop(0.5, "#FFFFFF");
      bgGrad.addColorStop(1, "#F1F5F9");
    } else {
      bgGrad.addColorStop(0, activePreset.bgGradient[0]);
      bgGrad.addColorStop(0.5, activePreset.bgGradient[1]);
      bgGrad.addColorStop(1, activePreset.bgGradient[2]);
    }
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // 2. Draw user-selected cover image at top
    await new Promise<void>((resolve) => {
      const img = new Image();
      img.onload = () => {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(40 + 24, 40);
        ctx.lineTo(W - 40 - 24, 40);
        ctx.arcTo(W - 40, 40, W - 40, 40 + 24, 24);
        ctx.lineTo(W - 40, 360 - 24);
        ctx.arcTo(W - 40, 360, W - 40 - 24, 360, 24);
        ctx.lineTo(40 + 24, 360);
        ctx.arcTo(40, 360, 40, 360 - 24, 24);
        ctx.lineTo(40, 40 + 24);
        ctx.arcTo(40, 40, 40 + 24, 40, 24);
        ctx.closePath();
        ctx.clip();

        // Object-cover calculation
        const targetW = W - 80;
        const targetH = 320;
        const scale = Math.max(targetW / img.width, targetH / img.height);
        const drawW = img.width * scale;
        const drawH = img.height * scale;
        const dx = 40 + (targetW - drawW) / 2;
        const dy = 40 + (targetH - drawH) / 2;
        ctx.drawImage(img, dx, dy, drawW, drawH);

        // Dark gradient overlay on image for text legibility
        const imgOverlay = ctx.createLinearGradient(0, 40, 0, 360);
        imgOverlay.addColorStop(0, "rgba(10, 12, 18, 0.25)");
        imgOverlay.addColorStop(0.55, "rgba(10, 12, 18, 0.45)");
        imgOverlay.addColorStop(1, "rgba(10, 12, 18, 0.92)");
        ctx.fillStyle = imgOverlay;
        ctx.fillRect(40, 40, targetW, targetH);
        ctx.restore();
        resolve();
      };
      img.onerror = () => resolve();
      img.src = activeCoverUrl;
    });

    // Cover border & header text inside cover
    drawRoundedRect(
      ctx,
      40,
      40,
      W - 80,
      320,
      24,
      undefined,
      isLight ? "rgba(15, 23, 42, 0.12)" : "rgba(255, 255, 255, 0.16)"
    );

    drawRoundedRect(ctx, 64, 64, 185, 38, 19, "rgba(0, 0, 0, 0.55)", "rgba(255, 255, 255, 0.25)");
    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = "#fbbf24";
    ctx.fillText("🏃 个人运动战报", 82, 89);

    ctx.font = "900 34px sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(rep.display_name || "跑者", 64, 290);

    const trailTag =
      rep.trail_mode === "exclude_pace"
        ? " · 仅去越野配速"
        : rep.trail_mode === "exclude_all"
        ? " · 去越野跑量/配速"
        : "";
    ctx.font = "bold 20px sans-serif";
    ctx.fillStyle = "#fcd34d";
    ctx.fillText(`${rep.period_label} · ${rep.date_range_str}${trailTag}`, 64, 330);

    // 3. Hero Mileage & Target Progress Box
    drawRoundedRect(
      ctx,
      40,
      385,
      W - 80,
      165,
      22,
      isLight ? "#FFF7ED" : "#151824",
      isLight ? "rgba(252, 76, 2, 0.3)" : "rgba(252, 76, 2, 0.35)"
    );
    ctx.font = "bold 20px sans-serif";
    ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
    ctx.fillText("本周期累计奔跑里程", 68, 425);

    ctx.font = "900 72px monospace";
    ctx.fillStyle = "#fc4c02";
    ctx.fillText(`${rep.total_distance_km}`, 68, 502);

    const kmW = ctx.measureText(`${rep.total_distance_km}`).width;
    ctx.font = "900 28px sans-serif";
    ctx.fillStyle = isLight ? "#b45309" : "#fbbf24";
    ctx.fillText("KM", 68 + kmW + 12, 498);

    ctx.font = "bold 20px sans-serif";
    ctx.fillStyle = isLight ? "#0f172a" : "#e4e4e7";
    ctx.fillText(`周期目标 ${rep.target_km} km · 完成度 ${rep.completion_rate}%`, W - 365, 430);

    // Progress bar
    drawRoundedRect(
      ctx,
      W - 365,
      450,
      295,
      16,
      8,
      isLight ? "rgba(15, 23, 42, 0.08)" : "rgba(255,255,255,0.08)"
    );
    const progW = Math.max(12, Math.min(295, Math.round((rep.completion_rate / 100) * 295)));
    drawRoundedRect(ctx, W - 365, 450, progW, 16, 8, "#fc4c02");

    ctx.font = "18px sans-serif";
    ctx.fillStyle = isLight ? "#64748b" : "#a1a1aa";
    ctx.fillText(`累计用时 ${rep.total_moving_time_str || "—"}`, W - 365, 502);

    // 4. 4-Grid Key Metrics
    const gW = (W - 80 - 18) / 2;
    const gH = 92;
    const metricCardBg = isLight ? "#FFFFFF" : "#151722";
    const metricCardStroke = isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255,255,255,0.08)";
    const metricLabelColor = isLight ? "#64748b" : "#9ca3af";
    const metricValColor = isLight ? "#0f172a" : "#ffffff";

    drawRoundedRect(ctx, 40, 570, gW, gH, 16, metricCardBg, metricCardStroke);
    ctx.font = "19px sans-serif";
    ctx.fillStyle = metricLabelColor;
    ctx.fillText("出勤打卡", 58, 602);
    ctx.font = "bold 28px sans-serif";
    ctx.fillStyle = metricValColor;
    ctx.fillText(`${rep.total_activities_count} 次 / ${rep.active_days_count} 天`, 58, 642);

    drawRoundedRect(ctx, 40 + gW + 18, 570, gW, gH, 16, metricCardBg, metricCardStroke);
    ctx.font = "19px sans-serif";
    ctx.fillStyle = metricLabelColor;
    ctx.fillText("平均配速", 58 + gW + 18, 602);
    ctx.font = "bold 28px monospace";
    ctx.fillStyle = metricValColor;
    ctx.fillText(`${rep.avg_pace_str}`, 58 + gW + 18, 642);

    drawRoundedRect(ctx, 40, 678, gW, gH, 16, metricCardBg, metricCardStroke);
    ctx.font = "19px sans-serif";
    ctx.fillStyle = metricLabelColor;
    ctx.fillText("平均心率", 58, 710);
    ctx.font = "bold 28px sans-serif";
    ctx.fillStyle = metricValColor;
    ctx.fillText(rep.avg_heartrate ? `${rep.avg_heartrate} bpm` : "—", 58, 750);

    drawRoundedRect(ctx, 40 + gW + 18, 678, gW, gH, 16, metricCardBg, metricCardStroke);
    ctx.font = "19px sans-serif";
    ctx.fillStyle = metricLabelColor;
    ctx.fillText("累计爬升", 58 + gW + 18, 710);
    ctx.font = "bold 28px sans-serif";
    ctx.fillStyle = metricValColor;
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
      isLight ? "#FFFFFF" : "#151722",
      isLight ? "#E2E8F0" : "rgba(56, 189, 248, 0.28)"
    );
    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = isLight ? "#0f172a" : "#38bdf8";
    ctx.fillText("🚀 单次最长距离", 58, hY + 30);
    ctx.font = "bold 24px monospace";
    ctx.fillStyle = metricValColor;
    ctx.fillText(rep.longest_run ? `${rep.longest_run.distance_km} km` : "暂无", 58, hY + 62);
    ctx.font = "16px sans-serif";
    ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
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
      isLight ? "#FFFFFF" : "#151722",
      isLight ? "#E2E8F0" : "rgba(251, 191, 36, 0.28)"
    );
    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = isLight ? "#0f172a" : "#fbbf24";
    ctx.fillText("⚡ 最佳配速表现 (≥3km)", 58 + gW + 18, hY + 30);
    ctx.font = "bold 24px monospace";
    ctx.fillStyle = metricValColor;
    ctx.fillText(rep.fastest_run ? `${rep.fastest_run.avg_pace_str}` : "暂无", 58 + gW + 18, hY + 62);
    ctx.font = "16px sans-serif";
    ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
    ctx.fillText(
      rep.fastest_run ? `单次 ${rep.fastest_run.distance_km} km · ${rep.fastest_run.start_time}` : "期待刷新配速",
      58 + gW + 18,
      hY + 84
    );

    // 6. Practical Coach Critique Box
    const cY = 905;
    drawRoundedRect(
      ctx,
      40,
      cY,
      W - 80,
      265,
      20,
      isLight ? "#FFFFFF" : "#181624",
      isLight ? "#E2E8F0" : "rgba(191, 90, 242, 0.38)"
    );
    if (isLight) {
      drawRoundedRect(ctx, 40, cY + 20, 6, 225, 3, "#fc4c02");
    }
    ctx.font = "bold 22px sans-serif";
    ctx.fillStyle = isLight ? "#0f172a" : "#c084fc";
    ctx.fillText("💡 教练周期实战复盘与建议", 62, cY + 38);

    ctx.font = "18px sans-serif";
    ctx.fillStyle = isLight ? "#334155" : "#e4e4e7";
    drawWrappedText(ctx, rep.canova_critique || "", 62, cY + 74, W - 124, 30, 6);

    // 7. Footer with Pure Mini-Program QR Code (no club invite)
    const fY = 1190;
    drawRoundedRect(
      ctx,
      40,
      fY,
      W - 80,
      150,
      20,
      isLight ? "#FFFFFF" : "#121520",
      isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.1)"
    );

    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = "#fc4c02";
    ctx.fillText("🏃 万跑跑团助手 · 科学耐力训练系统", 64, fY + 42);

    ctx.font = "900 24px sans-serif";
    ctx.fillStyle = metricValColor;
    ctx.fillText("微信扫码打开万跑跑团助手小程序", 64, fY + 80);

    ctx.font = "16px sans-serif";
    ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
    ctx.fillText("佳明/高驰手表自动同步 · Canova 科学训练与周期复盘", 64, fY + 114);

    const qrSrc = rep.qrcode_base64
      ? `data:image/jpeg;base64,${rep.qrcode_base64}`
      : rep.qrcode_url || "";
    if (qrSrc) {
      await new Promise<void>((resolve) => {
        const qrImg = new Image();
        qrImg.crossOrigin = "anonymous";
        qrImg.onload = () => {
          const qrBoxX = W - 40 - 134;
          const qrBoxY = fY + 15;
          drawRoundedRect(ctx, qrBoxX, qrBoxY, 120, 120, 14, "#ffffff");
          ctx.drawImage(qrImg, qrBoxX + 6, qrBoxY + 6, 108, 108);
          resolve();
        };
        qrImg.onerror = () => resolve();
        qrImg.src = qrSrc;
      });
    }

    const dataUrl = canvas.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `${rep.display_name || "跑者"}_${rep.period_label || "个人战报"}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-md">
      <div className="relative w-full max-w-2xl bg-[#131419] border border-amber-500/30 rounded-3xl p-5 sm:p-6 shadow-2xl space-y-4 max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#fc4c02]/25 to-amber-500/15 border border-[#fc4c02]/40 flex items-center justify-center text-[#fc4c02]">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base sm:text-lg font-black text-white flex items-center gap-2">
                个人跑步周报与月报
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#fc4c02]/15 text-[#fc4c02] border border-[#fc4c02]/30">
                  支持自选照片海报
                </span>
              </h3>
              <p className="text-xs text-zinc-400">可自由选择主题图或上传个人跑步照片，一键生成专属战报长图</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-white/10 text-zinc-400 hover:text-white transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Controls */}
        <div className="space-y-2.5">
          {/* Period Type & Offset */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <button
              onClick={() => handleSwitchPeriod("week")}
              className={`py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer border ${
                periodType === "week"
                  ? "bg-amber-500 text-black border-amber-500 shadow-md"
                  : "bg-white/5 text-zinc-400 border-white/10 hover:text-white"
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>个人周报</span>
            </button>
            <button
              onClick={() => handleSwitchPeriod("month")}
              className={`py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer border ${
                periodType === "month"
                  ? "bg-amber-500 text-black border-amber-500 shadow-md"
                  : "bg-white/5 text-zinc-400 border-white/10 hover:text-white"
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>个人月报</span>
            </button>
            <button
              onClick={() => handleSwitchOffset(0)}
              className={`py-2 rounded-xl text-xs font-bold border transition cursor-pointer ${
                periodOffset === 0
                  ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                  : "bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10"
              }`}
            >
              {periodType === "week" ? "本周" : "本月"}
            </button>
            <button
              onClick={() => handleSwitchOffset(-1)}
              className={`py-2 rounded-xl text-xs font-bold border transition cursor-pointer ${
                periodOffset === -1
                  ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                  : "bg-white/5 text-zinc-400 border-white/10 hover:bg-white/10"
              }`}
            >
              {periodType === "week" ? "上周" : "上月"}
            </button>
          </div>

          {/* Trail Running Filter */}
          <div className="p-2 bg-white/[0.03] rounded-2xl border border-white/10 space-y-1.5">
            <div className="flex items-center justify-between px-1">
              <span className="text-[11px] font-bold text-zinc-300">🏔️ 越野跑统计口径</span>
              {reportData && Number(reportData.trail_activities_count || 0) > 0 && (
                <span className="text-[10px] text-amber-400 font-mono">
                  本周期含越野 {reportData.trail_activities_count} 次 ({reportData.trail_distance_km} km)
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              <button
                onClick={() => handleSwitchTrailMode("include")}
                className={`py-1.5 px-2 rounded-xl text-[11px] font-bold border transition cursor-pointer ${
                  trailMode === "include"
                    ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                    : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10 hover:text-white"
                }`}
              >
                包含越野 (默认)
              </button>
              <button
                onClick={() => handleSwitchTrailMode("exclude_pace")}
                className={`py-1.5 px-2 rounded-xl text-[11px] font-bold border transition cursor-pointer ${
                  trailMode === "exclude_pace"
                    ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                    : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10 hover:text-white"
                }`}
              >
                仅去除越野配速
              </button>
              <button
                onClick={() => handleSwitchTrailMode("exclude_all")}
                className={`py-1.5 px-2 rounded-xl text-[11px] font-bold border transition cursor-pointer ${
                  trailMode === "exclude_all"
                    ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                    : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10 hover:text-white"
                }`}
              >
                去除越野跑量/配速
              </button>
            </div>
          </div>

          {/* Image Picker Row */}
          <div className="p-2.5 bg-white/[0.03] rounded-2xl border border-white/10 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-zinc-300 flex items-center gap-1.5">
                <ImageIcon className="w-3.5 h-3.5 text-amber-400" />
                选择战报封面图（或上传您的跑步照片）
              </span>
              <div className="flex items-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleUploadCustomImage}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-2.5 py-1 rounded-lg bg-[#fc4c02]/20 hover:bg-[#fc4c02]/30 text-[#fc4c02] border border-[#fc4c02]/40 text-[11px] font-bold flex items-center gap-1 transition cursor-pointer"
                >
                  <Upload className="w-3 h-3" />
                  <span>{customImageDataUrl ? "更换照片" : "上传我的照片"}</span>
                </button>
                {customImageDataUrl && (
                  <button
                    onClick={() => {
                      setCustomImageDataUrl(null);
                      setCustomImageName("");
                    }}
                    className="text-[10px] text-zinc-400 hover:text-white underline cursor-pointer"
                  >
                    恢复预设图
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
              {PRESET_THEMES.map((theme) => {
                const isSelected = !customImageDataUrl && selectedPresetId === theme.id;
                return (
                  <button
                    key={theme.id}
                    onClick={() => {
                      setCustomImageDataUrl(null);
                      setSelectedPresetId(theme.id);
                    }}
                    className={`py-1.5 px-2 rounded-xl text-[11px] font-bold border transition truncate cursor-pointer ${
                      isSelected
                        ? "bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-sm"
                        : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    {theme.name}
                  </button>
                );
              })}
            </div>
            {customImageName && (
              <div className="text-[10px] text-emerald-400 px-1">
                ✓ 已选用自定义照片：{customImageName}
              </div>
            )}
          </div>

          {/* View Mode Switcher */}
          <div className="flex gap-2 p-1 bg-black/40 rounded-xl border border-white/5">
            <button
              onClick={() => setViewMode("poster")}
              className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                viewMode === "poster"
                  ? "bg-gradient-to-r from-amber-500 to-amber-600 text-black font-black"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <ImageIcon className="w-3.5 h-3.5" />
              <span>🎨 个人战报海报视图</span>
            </button>
            <button
              onClick={() => setViewMode("text")}
              className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                viewMode === "text"
                  ? "bg-gradient-to-r from-amber-500 to-amber-600 text-black font-black"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <MessageCircle className="w-3.5 h-3.5" />
              <span>💬 朋友圈/跑群转发文案</span>
            </button>
          </div>
        </div>

        {/* Main Content */}
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-3">
            <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
            <span className="text-xs text-zinc-400">正在生成个人运动战报...</span>
          </div>
        ) : reportData ? (
          <div className="flex-1 overflow-y-auto space-y-4 pr-1 custom-scrollbar">
            {viewMode === "poster" ? (
              <div className="bg-gradient-to-b from-[#131622] via-[#151824] to-[#0c0d14] border-2 border-amber-500/35 rounded-3xl overflow-hidden shadow-2xl">
                {/* Cover Image Banner */}
                <div className="relative h-48 sm:h-56 w-full overflow-hidden rgm-photo-overlay">
                  <img
                    src={activeCoverUrl}
                    alt="战报封面"
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/35 to-black/15" />
                  <div className="absolute top-4 left-5 right-5 flex items-center justify-between">
                    <span className="px-3 py-1 rounded-full text-[11px] font-black bg-black/60 text-amber-300 border border-white/15 backdrop-blur-md">
                      🏃 个人运动战报
                    </span>
                    {reportData.trail_mode && reportData.trail_mode !== "include" && (
                      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-200 border border-amber-500/40 backdrop-blur-md">
                        {reportData.trail_mode === "exclude_pace"
                          ? "⏱️ 均速已去除越野跑"
                          : "🛣️ 已去除越野跑量与配速"}
                      </span>
                    )}
                  </div>
                  <div className="absolute bottom-4 left-5 right-5 flex items-end justify-between">
                    <div>
                      <h4 className="text-xl sm:text-2xl font-black text-white drop-shadow">
                        {reportData.display_name}
                      </h4>
                      <p className="text-xs font-bold text-amber-300">
                        {reportData.period_label} · {reportData.date_range_str}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="p-5 sm:p-6 space-y-5">
                  {/* Hero Mileage & Goal Progress */}
                  <div className="bg-gradient-to-br from-[#fc4c02]/15 via-amber-500/10 to-transparent border border-[#fc4c02]/30 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <span className="text-[11px] font-bold text-zinc-400">本周期累计奔跑里程</span>
                      <div className="flex items-baseline gap-2 mt-0.5">
                        <span className="text-4xl sm:text-5xl font-black text-[#fc4c02] font-mono tracking-tight">
                          {reportData.total_distance_km}
                        </span>
                        <span className="text-xl font-black text-amber-400">KM</span>
                      </div>
                    </div>
                    <div className="sm:w-56 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">周期目标 {reportData.target_km} km</span>
                        <span className="font-black text-amber-400">{reportData.completion_rate}%</span>
                      </div>
                      <div className="w-full h-2.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-[#fc4c02] to-amber-400 rounded-full"
                          style={{ width: `${Math.min(100, reportData.completion_rate || 0)}%` }}
                        />
                      </div>
                      <div className="text-[11px] text-zinc-400 flex items-center justify-between">
                        <span>累计用时 {reportData.total_moving_time_str}</span>
                        {reportData.remaining_km > 0 ? (
                          <span>差 {reportData.remaining_km} km 达标</span>
                        ) : (
                          <span className="text-emerald-400 font-bold">✓ 已达成目标</span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* 4 Key Stats */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    <div className="bg-white/[0.04] border border-white/[0.07] rounded-xl p-3 space-y-0.5">
                      <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                        <Clock className="w-3 h-3 text-amber-400" /> 出勤打卡
                      </span>
                      <div className="text-base font-black text-white">
                        {reportData.total_activities_count} 次 / {reportData.active_days_count} 天
                      </div>
                    </div>
                    <div className="bg-white/[0.04] border border-white/[0.07] rounded-xl p-3 space-y-0.5">
                      <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                        <Zap className="w-3 h-3 text-sky-400" /> 平均配速
                      </span>
                      <div className="text-base font-black text-white font-mono">
                        {reportData.avg_pace_str}
                      </div>
                    </div>
                    <div className="bg-white/[0.04] border border-white/[0.07] rounded-xl p-3 space-y-0.5">
                      <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                        <Activity className="w-3 h-3 text-rose-400" /> 平均心率
                      </span>
                      <div className="text-base font-black text-white">
                        {reportData.avg_heartrate ? `${reportData.avg_heartrate} bpm` : "—"}
                      </div>
                    </div>
                    <div className="bg-white/[0.04] border border-white/[0.07] rounded-xl p-3 space-y-0.5">
                      <span className="text-[10px] text-zinc-400 flex items-center gap-1">
                        <Mountain className="w-3 h-3 text-emerald-400" /> 累计爬升
                      </span>
                      <div className="text-base font-black text-white">
                        +{reportData.total_elevation_gain_m} m
                      </div>
                    </div>
                  </div>

                  {/* Highlights: Longest Run & Fastest Run */}
                  {(reportData.longest_run || reportData.fastest_run) && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {reportData.longest_run && (
                        <div className="bg-sky-500/[0.06] border border-sky-500/25 rounded-xl p-3 space-y-0.5">
                          <span className="text-[10px] font-bold text-sky-400">🚀 单次最长距离</span>
                          <div className="text-sm font-black text-white font-mono">
                            {reportData.longest_run.distance_km} km · {reportData.longest_run.avg_pace_str}
                          </div>
                          <div className="text-[10px] text-zinc-400 truncate">
                            {reportData.longest_run.start_time} · {reportData.longest_run.activity_name}
                          </div>
                        </div>
                      )}
                      {reportData.fastest_run && (
                        <div className="bg-amber-500/[0.06] border border-amber-500/25 rounded-xl p-3 space-y-0.5">
                          <span className="text-[10px] font-bold text-amber-400">⚡ 最佳配速课 (≥3km)</span>
                          <div className="text-sm font-black text-white font-mono">
                            {reportData.fastest_run.avg_pace_str} · {reportData.fastest_run.distance_km} km
                          </div>
                          <div className="text-[10px] text-zinc-400 truncate">
                            {reportData.fastest_run.start_time} · {reportData.fastest_run.activity_name}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Practical Coach Critique */}
                  <div className="bg-gradient-to-br from-purple-500/10 via-[#181624] to-[#181624] border border-purple-500/35 rounded-2xl p-4 space-y-1.5">
                    <div className="text-xs font-bold text-purple-400 flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4" />
                      <span>教练周期实战复盘与建议</span>
                    </div>
                    <p className="text-xs text-zinc-200 leading-relaxed">{reportData.canova_critique}</p>
                  </div>

                  {/* Bottom Mini-Program QR Code Footer (Pure QR, no club invite) */}
                  <div className="flex items-center justify-between gap-4 pt-4 border-t border-white/10">
                    <div className="space-y-1">
                      <div className="text-[11px] font-bold text-[#fc4c02]">
                        🏃 万跑跑团助手 · 科学耐力训练系统
                      </div>
                      <div className="text-sm font-black text-white">
                        微信扫码打开万跑跑团助手小程序
                      </div>
                      <div className="text-[11px] text-zinc-400">
                        佳明/高驰手表自动同步 · 科学耐力训练与周期复盘
                      </div>
                    </div>
                    {(reportData.qrcode_base64 || reportData.qrcode_url) && (
                      <div className="shrink-0 flex flex-col items-center gap-1">
                        <div className="p-1.5 bg-white rounded-xl shadow-md">
                          <img
                            src={
                              reportData.qrcode_base64
                                ? `data:image/jpeg;base64,${reportData.qrcode_base64}`
                                : reportData.qrcode_url
                            }
                            alt="万跑跑团小程序码"
                            className="w-16 h-16 sm:w-20 sm:h-20 object-contain"
                          />
                        </div>
                        <span className="text-[10px] text-zinc-400 font-medium">微信扫码体验</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-[#0e0e11] border border-emerald-500/30 rounded-2xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                    <MessageCircle className="w-4 h-4" />
                    个人周报/月报分享文案预览
                  </span>
                  <span className="text-[10px] text-zinc-500 font-mono">支持直接复制</span>
                </div>
                <pre className="p-3 bg-black/60 rounded-xl text-[11px] text-zinc-200 font-mono whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto custom-scrollbar border border-white/5">
                  {reportData.forward_text}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <div className="py-12 text-center text-xs text-zinc-500">暂无个人战报数据</div>
        )}

        {/* Footer Actions */}
        <div className="flex flex-col sm:flex-row gap-2.5 pt-3 border-t border-white/10">
          <button
            onClick={handleDownloadPoster}
            disabled={!reportData}
            className="flex-1 py-3 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-black rounded-2xl text-xs font-black transition shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2 cursor-pointer"
          >
            <ImageIcon className="w-4 h-4" />
            <span>🖼️ 下载个人战报海报 (PNG)</span>
          </button>
          <button
            onClick={handleCopyText}
            disabled={!reportData}
            className="py-3 px-5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 rounded-2xl text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer"
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            <span>{copied ? "已复制文案！" : "📋 复制分享文案"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
