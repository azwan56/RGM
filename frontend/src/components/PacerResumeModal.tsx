"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { X, Download, Camera, FileCheck2, Sparkles, ShieldCheck, UserCheck } from "lucide-react";

interface PacerResumeModalProps {
  open: boolean;
  onClose: () => void;
  evalData: any;
}

function roundRectPath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  const rad = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rad, y);
  ctx.arcTo(x + w, y, x + w, y + h, rad);
  ctx.arcTo(x + w, y + h, x, y + h, rad);
  ctx.arcTo(x, y + h, x, y, rad);
  ctx.arcTo(x, y, x + w, y, rad);
  ctx.closePath();
}

function fmtPaceFromSec(sec: number): string {
  if (!sec || sec <= 0) return "--";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}'${String(s).padStart(2, "0")}"`;
}

export default function PacerResumeModal({ open, onClose, evalData }: PacerResumeModalProps) {
  const [posterMode, setPosterMode] = useState<"resume" | "social">("resume");
  const [useRealName, setUseRealName] = useState<boolean>(false);
  const [posterLight, setPosterLight] = useState<boolean>(false);
  const [photoDataUrl, setPhotoDataUrl] = useState<string>("");
  const [focusY, setFocusY] = useState<number>(0.25);
  const [posterUrl, setPosterUrl] = useState<string>("");

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (typeof document !== "undefined") {
      setPosterLight(document.documentElement.classList.contains("theme-light"));
    }
  }, [open]);

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const res = ev.target?.result;
      if (typeof res === "string") {
        setPhotoDataUrl(res);
      }
    };
    reader.readAsDataURL(f);
  };

  const renderCanvas = useCallback(async () => {
    if (!open || !evalData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const W = 1080;
    const H = posterMode === "resume" ? 1620 : 1440;
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const runner = evalData.runner || evalData.runner_summary || {};
    const cred = evalData.pacer_credentials_summary || {};
    const calib = evalData.event_calibration || {};
    const sel = evalData.selected_evaluation || {};
    const dims: any[] = sel.dimensions || [];
    const months: any[] = evalData.monthly_mileage_6m || [];
    const showcase = evalData.showcase_run || null;
    const races: any[] = (evalData.verified_races || []).slice(0, 4);
    const fm24Cnt = (evalData.verified_races || []).filter((r: any) => !r.is_trail && Number(r.distance_km || 0) >= 40).length;
    const hm24Cnt = (evalData.verified_races || []).filter((r: any) => !r.is_trail && Number(r.distance_km || 0) >= 19.5 && Number(r.distance_km || 0) < 40).length;
    const paceLabel = sel.target_pace_str
      ? String(sel.target_pace_str).endsWith("/km")
        ? sel.target_pace_str
        : `${sel.target_pace_str}/km`
      : "--";
    const watchBadge = runner.watch_verified_label || runner.device_verified_label || "";
    const firstAidLabel = runner.first_aid_cert_label || runner.first_aid_label || "";

    const displayName =
      useRealName && runner.real_name
        ? String(runner.real_name)
        : String(runner.display_name || "RGM 跑者");

    const accent = "#FC4C02";
    const gold = "#F59E0B";
    const emerald = "#10B981";

    if (posterMode === "resume") {
      // ── MODE A: 竞选履历版 (Official Pacer Recruitment Resume) ──
      const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
      if (posterLight) {
        bgGrad.addColorStop(0, "#F8FAFC");
        bgGrad.addColorStop(1, "#EEF2F6");
      } else {
        bgGrad.addColorStop(0, "#0B0C10");
        bgGrad.addColorStop(0.5, "#11131A");
        bgGrad.addColorStop(1, "#090A0D");
      }
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, W, H);

      // Subtle top glow
      const glow = ctx.createRadialGradient(W * 0.82, 120, 20, W * 0.82, 120, 460);
      glow.addColorStop(0, posterLight ? "rgba(252,76,2,0.12)" : "rgba(252,76,2,0.22)");
      glow.addColorStop(1, "rgba(252,76,2,0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, W, 520);

      const textMain = posterLight ? "#0F172A" : "#FFFFFF";
      const textSub = posterLight ? "#475569" : "#94A3B8";
      const cardBg = posterLight ? "#FFFFFF" : "rgba(24, 26, 34, 0.92)";
      const cardBorder = posterLight ? "rgba(15, 23, 42, 0.09)" : "rgba(255, 255, 255, 0.09)";

      // Top Header Banner
      ctx.fillStyle = accent;
      roundRectPath(ctx, 56, 52, 268, 42, 21);
      ctx.fill();
      ctx.fillStyle = "#FFFFFF";
      ctx.font = "bold 21px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText("🐰 官方配速员竞选履历卡", 76, 80);

      if (watchBadge) {
        ctx.fillStyle = posterLight ? "rgba(16,185,129,0.12)" : "rgba(16,185,129,0.18)";
        roundRectPath(ctx, W - 360, 52, 304, 42, 21);
        ctx.fill();
        ctx.fillStyle = emerald;
        ctx.font = "bold 19px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(`⌚ ${watchBadge}`, W - 76, 80);
        ctx.textAlign = "left";
      }

      // Event & Target Group Title
      ctx.fillStyle = textMain;
      ctx.font = "900 46px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      const titleStr = `${calib.event_name || "马拉松赛事"} · ${sel.group_label || "官兔"}`;
      ctx.fillText(titleStr.slice(0, 20), 56, 154);

      ctx.fillStyle = textSub;
      ctx.font = "600 22px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      const subMeta = [
        calib.race_level || "认证路跑",
        `目标配速 ${paceLabel}`,
        `枪声误差标准 ±${calib.target_gun_error_sec || 45}s`,
      ].join("  ·  ");
      ctx.fillText(subMeta, 56, 194);

      // Runner Identity & Score Hero Card
      roundRectPath(ctx, 56, 224, W - 112, 240, 28);
      ctx.fillStyle = cardBg;
      ctx.fill();
      ctx.strokeStyle = cardBorder;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Left: Runner info & PBs
      ctx.fillStyle = textMain;
      ctx.font = "bold 36px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(displayName, 92, 286);

      const idTags: string[] = [];
      if (runner.gender === "female") idTags.push("女");
      else if (runner.gender === "male") idTags.push("男");
      if (runner.age) idTags.push(`${runner.age}岁`);
      if (runner.first_aid_cert_type && firstAidLabel) {
        idTags.push(firstAidLabel);
      }
      ctx.fillStyle = textSub;
      ctx.font = "600 21px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(idTags.join(" · ") || "跑团认证跑者", 92, 324);

      // Key Metrics Pills inside Hero
      const heroStats = [
        { k: "最佳证书/PB", v: sel.cert_finish_str || sel.certified_best_time_str || "待录入" },
        { k: "当期实力预测", v: sel.pred_finish_str || sel.predicted_time_str || "--" },
        { k: "近2年全/半马", v: `${fm24Cnt}全 / ${hm24Cnt}半` },
        {
          k: "领跑履历",
          v: `官兔${cred.official_pacer_count || 0}次 · 领跑${cred.club_pacer_total_count || 0}次`,
        },
      ];
      heroStats.forEach((st, idx) => {
        const bx = 92 + idx * 172;
        const by = 354;
        roundRectPath(ctx, bx, by, 160, 82, 16);
        ctx.fillStyle = posterLight ? "#F1F5F9" : "rgba(255,255,255,0.04)";
        ctx.fill();
        ctx.fillStyle = textSub;
        ctx.font = "500 17px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(st.k, bx + 14, by + 30);
        ctx.fillStyle = textMain;
        ctx.font = "bold 21px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(st.v, bx + 14, by + 63);
      });

      // Right: Score Circle
      const cx = W - 175;
      const cy = 344;
      ctx.beginPath();
      ctx.arc(cx, cy, 78, 0, Math.PI * 2);
      ctx.strokeStyle = posterLight ? "#E2E8F0" : "rgba(255,255,255,0.1)";
      ctx.lineWidth = 14;
      ctx.stroke();

      const scoreVal = Number(sel.overall_score || 0);
      const scoreColor = sel.verdict_color || emerald;
      ctx.beginPath();
      ctx.arc(cx, cy, 78, -Math.PI / 2, -Math.PI / 2 + (Math.PI * 2 * Math.min(100, scoreVal)) / 100);
      ctx.strokeStyle = scoreColor;
      ctx.lineWidth = 14;
      ctx.lineCap = "round";
      ctx.stroke();

      ctx.textAlign = "center";
      ctx.fillStyle = textMain;
      ctx.font = "900 50px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(`${scoreVal}`, cx, cy + 12);
      ctx.fillStyle = scoreColor;
      ctx.font = "bold 20px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(`${sel.grade || "A"}级胜任度`, cx, cy + 44);
      ctx.textAlign = "left";

      // 6-Dimension Quantitative Bars Card
      roundRectPath(ctx, 56, 488, W - 112, 304, 28);
      ctx.fillStyle = cardBg;
      ctx.fill();
      ctx.strokeStyle = cardBorder;
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.fillStyle = textMain;
      ctx.font = "bold 25px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText("📊 六维官兔胜任度拆解", 88, 536);

      ctx.textAlign = "right";
      ctx.fillStyle = scoreColor;
      ctx.font = "bold 21px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(sel.verdict_label || "", W - 88, 536);
      ctx.textAlign = "left";

      dims.slice(0, 6).forEach((d, i) => {
        const col = i % 2;
        const row = Math.floor(i / 2);
        const dx = 88 + col * 462;
        const dy = 572 + row * 72;
        const barW = 420;

        ctx.fillStyle = textMain;
        ctx.font = "bold 20px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(`${d.label} (${d.weight_pct}%)`, dx, dy);

        ctx.textAlign = "right";
        ctx.fillStyle = accent;
        ctx.font = "bold 21px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(`${d.score}分`, dx + barW, dy);
        ctx.textAlign = "left";

        roundRectPath(ctx, dx, dy + 12, barW, 12, 6);
        ctx.fillStyle = posterLight ? "#E2E8F0" : "rgba(255,255,255,0.09)";
        ctx.fill();

        const fillW = Math.max(16, (barW * Math.min(100, Number(d.score || 0))) / 100);
        roundRectPath(ctx, dx, dy + 12, fillW, 12, 6);
        ctx.fillStyle = Number(d.score || 0) >= 80 ? emerald : Number(d.score || 0) >= 65 ? gold : "#EF4444";
        ctx.fill();

        ctx.fillStyle = textSub;
        ctx.font = "500 16px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(String(d.display_value || "").slice(0, 26), dx, dy + 44);
      });

      // Middle Dual Charts Row: Left = 6-Month Mileage Bars, Right = Showcase Steady Run 1km Curve
      const chartY = 816;
      const chartH = 340;
      const halfW = (W - 112 - 24) / 2;

      // Left Chart: 6-Month Mileage
      roundRectPath(ctx, 56, chartY, halfW, chartH, 28);
      ctx.fillStyle = cardBg;
      ctx.fill();
      ctx.strokeStyle = cardBorder;
      ctx.stroke();

      ctx.fillStyle = textMain;
      ctx.font = "bold 23px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText("🗓️ 近 6 个月跑量实绩 (km)", 84, chartY + 46);

      const total6m = months.reduce((acc, m) => acc + Number(m.km || 0), 0);
      ctx.textAlign = "right";
      ctx.fillStyle = textSub;
      ctx.font = "600 18px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(`累计 ${Math.round(total6m)} km`, 56 + halfW - 28, chartY + 46);
      ctx.textAlign = "left";

      if (months.length > 0) {
        const maxKm = Math.max(100, ...months.map((m) => Number(m.km || 0)));
        const plotBottom = chartY + chartH - 52;
        const maxBarH = 185;
        const stepX = (halfW - 72) / months.length;
        months.forEach((m, idx) => {
          const kv = Number(m.km || 0);
          const bh = Math.max(8, (kv / maxKm) * maxBarH);
          const bx = 92 + idx * stepX;
          const by = plotBottom - bh;
          roundRectPath(ctx, bx, by, 38, bh, 8);
          ctx.fillStyle = kv >= 180 ? emerald : accent;
          ctx.fill();

          ctx.textAlign = "center";
          ctx.fillStyle = textMain;
          ctx.font = "bold 16px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
          ctx.fillText(`${Math.round(kv)}`, bx + 19, by - 8);

          ctx.fillStyle = textSub;
          ctx.font = "500 16px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
          ctx.fillText(m.short_label || "", bx + 19, plotBottom + 26);
          ctx.textAlign = "left";
        });
      }

      // Right Chart: Showcase 1km Steady Split Curve
      const rightX = 56 + halfW + 24;
      roundRectPath(ctx, rightX, chartY, halfW, chartH, 28);
      ctx.fillStyle = cardBg;
      ctx.fill();
      ctx.strokeStyle = cardBorder;
      ctx.stroke();

      ctx.fillStyle = textMain;
      ctx.font = "bold 23px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText("⏱️ 稳态巡航代表作分段", rightX + 28, chartY + 46);

      if (showcase && Array.isArray(showcase.splits_series) && showcase.splits_series.length >= 3) {
        ctx.textAlign = "right";
        ctx.fillStyle = emerald;
        ctx.font = "bold 18px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(`±${showcase.sigma_gap_sec}s/km`, rightX + halfW - 28, chartY + 46);
        ctx.textAlign = "left";

        ctx.fillStyle = textSub;
        ctx.font = "500 16px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(
          `${showcase.date} · ${showcase.distance_km}km · 均配 ${showcase.avg_pace_str}/km`,
          rightX + 28,
          chartY + 76
        );

        const sp = showcase.splits_series;
        const paces = sp.map((s: any) => Number(s.pace_sec || showcase.avg_pace_sec));
        const medPace = Number(showcase.avg_pace_sec || 300);
        const minP = Math.min(medPace - 25, ...paces);
        const maxP = Math.max(medPace + 25, ...paces);
        const px0 = rightX + 34;
        const pw = halfW - 68;
        const py0 = chartY + 108;
        const ph = 175;

        // Target reference band (±5s)
        const refY = py0 + ((medPace - minP) / Math.max(1, maxP - minP)) * ph;
        ctx.strokeStyle = posterLight ? "rgba(16,185,129,0.45)" : "rgba(16,185,129,0.4)";
        ctx.setLineDash([6, 6]);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(px0, refY);
        ctx.lineTo(px0 + pw, refY);
        ctx.stroke();
        ctx.setLineDash([]);

        // Split polyline
        ctx.strokeStyle = accent;
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        sp.forEach((pt: any, idx: number) => {
          const x = px0 + (idx / Math.max(1, sp.length - 1)) * pw;
          const y = py0 + ((Number(pt.pace_sec) - minP) / Math.max(1, maxP - minP)) * ph;
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();

        ctx.fillStyle = textSub;
        ctx.font = "500 15px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(`1km`, px0, py0 + ph + 28);
        ctx.textAlign = "center";
        ctx.fillText(`均配基准线 ${fmtPaceFromSec(medPace)}/km`, px0 + pw / 2, py0 + ph + 28);
        ctx.textAlign = "right";
        ctx.fillText(`${sp[sp.length - 1].km}km`, px0 + pw, py0 + ph + 28);
        ctx.textAlign = "left";
      } else {
        ctx.fillStyle = textSub;
        ctx.font = "500 19px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText("同步手表 12km+ 稳态长距离后自动绘制", rightX + 28, chartY + 180);
      }

      // Bottom Verified Race List Card
      const raceY = 1180;
      roundRectPath(ctx, 56, raceY, W - 112, 316, 28);
      ctx.fillStyle = cardBg;
      ctx.fill();
      ctx.strokeStyle = cardBorder;
      ctx.stroke();

      ctx.fillStyle = textMain;
      ctx.font = "bold 24px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText("🏅 近期认证完赛与官兔领跑履历", 88, raceY + 48);

      if (races.length > 0) {
        races.forEach((r, idx) => {
          const ry = raceY + 94 + idx * 52;
          ctx.fillStyle = textMain;
          ctx.font = "bold 20px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
          const rTitle = `${r.date || ""}  ${String(r.name || "马拉松").slice(0, 16)}`;
          ctx.fillText(rTitle, 88, ry);

          if (r.was_official_pacer) {
            ctx.fillStyle = "rgba(252,76,2,0.16)";
            roundRectPath(ctx, 520, ry - 24, 150, 32, 10);
            ctx.fill();
            ctx.fillStyle = accent;
            ctx.font = "bold 16px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
            const errTxt =
              r.pacer_error_sec !== null && r.pacer_error_sec !== undefined
                ? ` (${r.pacer_error_sec >= 0 ? "+" : ""}${r.pacer_error_sec}s)`
                : "";
            ctx.fillText(`🐰 官兔${errTxt}`, 532, ry - 2);
          } else {
            ctx.fillStyle = textSub;
            ctx.font = "500 17px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
            ctx.fillText(String(r.race_level || "完赛核验").slice(0, 10), 532, ry);
          }

          ctx.textAlign = "right";
          ctx.fillStyle = emerald;
          ctx.font = "900 22px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
          ctx.fillText(r.finish_time || "--", W - 88, ry);
          ctx.textAlign = "left";
        });
      } else {
        ctx.fillStyle = textSub;
        ctx.font = "500 20px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText("暂无已登记历史赛事，可在「个人档案 - 赛事计划」补充往届完赛与官兔经历", 88, raceY + 150);
      }

      // Footer Branding
      ctx.fillStyle = textSub;
      ctx.font = "600 19px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText("万跑跑团助手 · 官兔胜任度量化评估系统", 56, H - 46);
      ctx.textAlign = "right";
      ctx.fillText(new Date().toISOString().slice(0, 10), W - 56, H - 46);
      ctx.textAlign = "left";
    } else {
      // ── MODE B: 社交晒图版 (Social Runner Photo + Score Overlay) ──
      ctx.fillStyle = "#090A0F";
      ctx.fillRect(0, 0, W, H);

      if (photoDataUrl) {
        const img = await new Promise<HTMLImageElement | null>((resolve) => {
          const im = new Image();
          im.crossOrigin = "anonymous";
          im.onload = () => resolve(im);
          im.onerror = () => resolve(null);
          im.src = photoDataUrl;
        });
        if (img) {
          const heroH = 880;
          const imgRatio = img.width / img.height;
          const boxRatio = W / heroH;
          let sx = 0,
            sy = 0,
            sw = img.width,
            sh = img.height;
          if (imgRatio > boxRatio) {
            sw = img.height * boxRatio;
            sx = (img.width - sw) * 0.5;
          } else {
            sh = img.width / boxRatio;
            sy = Math.max(0, Math.min(img.height - sh, (img.height - sh) * focusY));
          }
          ctx.drawImage(img, sx, sy, sw, sh, 0, 0, W, heroH);
        }
      } else {
        const heroGrad = ctx.createLinearGradient(0, 0, W, 860);
        heroGrad.addColorStop(0, "#1E1B4B");
        heroGrad.addColorStop(0.5, "#31102F");
        heroGrad.addColorStop(1, "#090A0F");
        ctx.fillStyle = heroGrad;
        ctx.fillRect(0, 0, W, 880);
      }

      // Gradient fade into bottom data deck
      const fade = ctx.createLinearGradient(0, 420, 0, 890);
      fade.addColorStop(0, "rgba(9,10,15,0)");
      fade.addColorStop(0.75, "rgba(9,10,15,0.86)");
      fade.addColorStop(1, "#090A0F");
      ctx.fillStyle = fade;
      ctx.fillRect(0, 420, W, 480);

      // Top Pill
      roundRectPath(ctx, 56, 56, 310, 48, 24);
      ctx.fillStyle = "rgba(9,10,15,0.68)";
      ctx.fill();
      ctx.fillStyle = "#FFFFFF";
      ctx.font = "bold 22px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText("🐰 万跑跑团助手 · 官兔胜任度报告", 80, 88);

      // Floating Hero Title over bottom of photo
      ctx.fillStyle = accent;
      ctx.font = "900 30px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(calib.event_name || "马拉松官方配速员评估", 64, 675);

      ctx.fillStyle = "#FFFFFF";
      ctx.font = "900 68px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(`${sel.group_label || "官兔"} · ${sel.overall_score || 0}分`, 64, 758);

      ctx.fillStyle = sel.verdict_color || emerald;
      ctx.font = "bold 28px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(`${displayName}  |  ${sel.verdict_label || ""}`, 64, 812);

      // 6-Dimension Compact Grid
      dims.slice(0, 6).forEach((d, idx) => {
        const col = idx % 3;
        const row = Math.floor(idx / 3);
        const gx = 64 + col * 322;
        const gy = 875 + row * 185;
        roundRectPath(ctx, gx, gy, 302, 162, 24);
        ctx.fillStyle = "rgba(255,255,255,0.05)";
        ctx.fill();
        ctx.strokeStyle = "rgba(255,255,255,0.09)";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = "#94A3B8";
        ctx.font = "600 20px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(d.label, gx + 24, gy + 44);

        ctx.fillStyle = "#FFFFFF";
        ctx.font = "900 44px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(`${d.score}`, gx + 24, gy + 104);

        ctx.fillStyle = "#CBD5E1";
        ctx.font = "500 16px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
        ctx.fillText(String(d.display_value || "").slice(0, 16), gx + 24, gy + 138);
      });

      // Footer
      ctx.fillStyle = "#94A3B8";
      ctx.font = "600 20px -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif";
      ctx.fillText(
        `目标配速 ${paceLabel}  ·  当期实力 ${sel.pred_finish_str || sel.predicted_time_str || "--"}`,
        64,
        H - 64
      );
      ctx.textAlign = "right";
      ctx.fillStyle = accent;
      ctx.fillText("万跑跑团助手", W - 64, H - 64);
      ctx.textAlign = "left";
    }

    setPosterUrl(canvas.toDataURL("image/png"));
  }, [open, evalData, posterMode, useRealName, posterLight, photoDataUrl, focusY]);

  useEffect(() => {
    renderCanvas();
  }, [renderCanvas]);

  if (!open || !evalData) return null;

  const hasRealName = Boolean((evalData?.runner || evalData?.runner_summary)?.real_name);

  const handleDownload = () => {
    if (!posterUrl) return;
    const a = document.createElement("a");
    const gName = evalData?.selected_evaluation?.group_code || "pacer";
    a.href = posterUrl;
    a.download = `RGM_官兔${posterMode === "resume" ? "竞选履历" : "社交海报"}_${gName}.png`;
    a.click();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-[#121216] border border-white/10 rounded-3xl max-w-4xl w-full p-5 sm:p-6 shadow-2xl my-auto">
        <div className="flex items-center justify-between gap-3 pb-4 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <span className="text-xl">🐰</span>
            <div>
              <h3 className="text-base sm:text-lg font-black text-white">
                生成官兔竞选履历与社交分享卡
              </h3>
              <p className="text-xs text-zinc-400">
                支持组委会报名长图（含6个月跑量柱状图+稳态1km曲线）与朋友圈晒图双模式
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-5">
          {/* Left Controls */}
          <div className="lg:col-span-5 space-y-4">
            <div>
              <label className="text-xs font-bold text-zinc-400 block mb-2">选择海报版式</label>
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  onClick={() => setPosterMode("resume")}
                  className={`flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl border text-xs font-bold transition ${
                    posterMode === "resume"
                      ? "bg-[#FC4C02]/15 border-[#FC4C02] text-white"
                      : "bg-[#18181d] border-white/10 text-zinc-400 hover:text-white"
                  }`}
                >
                  <FileCheck2 className="w-4 h-4 text-[#FC4C02]" />
                  📋 竞选履历版
                </button>
                <button
                  onClick={() => setPosterMode("social")}
                  className={`flex items-center justify-center gap-1.5 py-2.5 px-3 rounded-xl border text-xs font-bold transition ${
                    posterMode === "social"
                      ? "bg-[#FC4C02]/15 border-[#FC4C02] text-white"
                      : "bg-[#18181d] border-white/10 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  📸 社交晒图版
                </button>
              </div>
            </div>

            {/* Identity Toggle */}
            <div className="bg-[#18181d] border border-white/5 rounded-2xl p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-zinc-200 flex items-center gap-1.5">
                  <UserCheck className="w-4 h-4 text-emerald-400" />
                  署名展示方式
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setUseRealName(false)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                      !useRealName ? "bg-emerald-500/20 text-emerald-300" : "bg-white/5 text-zinc-400"
                    }`}
                  >
                    昵称
                  </button>
                  <button
                    disabled={!hasRealName}
                    onClick={() => setUseRealName(true)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                      useRealName
                        ? "bg-emerald-500/20 text-emerald-300"
                        : hasRealName
                        ? "bg-white/5 text-zinc-400"
                        : "bg-white/5 text-zinc-600 cursor-not-allowed"
                    }`}
                  >
                    真实姓名
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-zinc-400">
                {hasRealName
                  ? "投递组委会官兔招募表时可切换为真实姓名，发朋友圈建议保持昵称保护隐私。"
                  : "当前未填写或无权查看真实姓名，默认使用跑者昵称署名。"}
              </p>
            </div>

            {posterMode === "resume" ? (
              <div className="bg-[#18181d] border border-white/5 rounded-2xl p-3.5 flex items-center justify-between">
                <span className="text-xs font-bold text-zinc-200">履历底色主题</span>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setPosterLight(false)}
                    className={`px-3 py-1 rounded-lg text-xs font-bold ${
                      !posterLight ? "bg-[#FC4C02] text-white" : "bg-white/5 text-zinc-400"
                    }`}
                  >
                    曜石暗色
                  </button>
                  <button
                    onClick={() => setPosterLight(true)}
                    className={`px-3 py-1 rounded-lg text-xs font-bold ${
                      posterLight ? "bg-white text-zinc-900" : "bg-white/5 text-zinc-400"
                    }`}
                  >
                    清爽白底
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-[#18181d] border border-white/5 rounded-2xl p-3.5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-zinc-200">上传赛道定妆照 / 领跑照</span>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#FC4C02]/20 hover:bg-[#FC4C02]/30 text-[#FC4C02] text-xs font-bold transition"
                  >
                    <Camera className="w-3.5 h-3.5" />
                    选择照片
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handlePhotoUpload}
                  />
                </div>
                {photoDataUrl && (
                  <div className="flex items-center justify-between text-xs text-zinc-400 pt-1">
                    <span>人物构图焦点：</span>
                    <div className="flex gap-1.5">
                      {[
                        { label: "偏上", v: 0.15 },
                        { label: "居中", v: 0.45 },
                        { label: "偏下", v: 0.75 },
                      ].map((opt) => (
                        <button
                          key={opt.label}
                          onClick={() => setFocusY(opt.v)}
                          className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            Math.abs(focusY - opt.v) < 0.1
                              ? "bg-amber-500/25 text-amber-300"
                              : "bg-white/5 text-zinc-400"
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/25 text-xs text-emerald-200 flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>
                履历数据由系统自动核验最近 90 天稳态长距离分段与 24 个月完赛记录，可直接作为上马、北马、厦马等赛事官兔报名附件。
              </span>
            </div>

            <button
              onClick={handleDownload}
              className="w-full py-3 rounded-2xl bg-gradient-to-r from-[#FC4C02] to-amber-500 hover:opacity-95 text-white font-black text-sm flex items-center justify-center gap-2 shadow-lg transition"
            >
              <Download className="w-4 h-4" />
              保存高清 PNG 海报 (1080P)
            </button>
          </div>

          {/* Right Live Preview */}
          <div className="lg:col-span-7 flex flex-col items-center justify-center bg-[#09090c] rounded-2xl p-4 border border-white/5">
            <canvas ref={canvasRef} className="hidden" />
            {posterUrl ? (
              <img
                src={posterUrl}
                alt="Pacer Resume Poster Preview"
                className="max-h-[540px] w-auto rounded-xl shadow-2xl border border-white/10 object-contain"
              />
            ) : (
              <div className="h-80 flex items-center justify-center text-xs text-zinc-500">
                正在渲染高清履历卡...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
