"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { X, Camera, Download, RefreshCw, MapPin, Mountain, Sparkles, Trophy } from "lucide-react";
import apiClient from "@/lib/apiClient";

interface PersonalShareCardModalProps {
  open: boolean;
  onClose: () => void;
  uid?: string;
  activityId?: string;
  raceId?: string;
}

export default function PersonalShareCardModal({
  open,
  onClose,
  uid,
  activityId,
  raceId,
}: PersonalShareCardModalProps) {
  const [loading, setLoading] = useState(false);
  const [shareData, setShareData] = useState<any>(null);
  const [cardMode, setCardMode] = useState<"workout" | "race">(raceId ? "race" : "workout");
  const [recentRuns, setRecentRuns] = useState<any[]>([]);
  const [completedRaces, setCompletedRaces] = useState<any[]>([]);
  const [selectedActId, setSelectedActId] = useState<string>(activityId || "");
  const [selectedRaceId, setSelectedRaceId] = useState<string>(raceId || "");

  const [overlayMode, setOverlayMode] = useState<"both" | "map" | "elevation">("both");
  const [trackPosition, setTrackPosition] = useState<"corner" | "center">("corner");
  const [showDailyPlan, setShowDailyPlan] = useState<boolean>(true);

  const [commentaryOptions, setCommentaryOptions] = useState<Array<{ key: string; label: string; text: string }>>([]);
  const [activeCommKey, setActiveCommKey] = useState<string>("exec");
  const [customCommentary, setCustomCommentary] = useState<string>("");

  const [userPhotoDataUrl, setUserPhotoDataUrl] = useState<string>("");
  const [photoFocusX, setPhotoFocusX] = useState<number>(0.5);
  const [photoFocusY, setPhotoFocusY] = useState<number>(0.18);
  const [autoFocusX, setAutoFocusX] = useState<number>(0.5);
  const [autoFocusY, setAutoFocusY] = useState<number>(0.18);
  const [faceDetected, setFaceDetected] = useState<boolean>(false);
  const [detectingFace, setDetectingFace] = useState<boolean>(false);
  const [focusPreset, setFocusPreset] = useState<"auto" | "top" | "upper" | "center" | "bottom">("auto");
  const [hasCustomPhoto, setHasCustomPhoto] = useState<boolean>(false);

  const [posterDataUrl, setPosterDataUrl] = useState<string>("");
  const [isLightTheme, setIsLightTheme] = useState<boolean>(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const syncTheme = () => {
      setIsLightTheme(document.documentElement.classList.contains("theme-light"));
    };
    syncTheme();
    const observer = new MutationObserver(syncTheme);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, [open]);

  const fetchCardData = useCallback(
    async (actId?: string, rId?: string) => {
      if (!uid) return;
      setLoading(true);
      try {
        const qs = new URLSearchParams();
        if (rId) {
          qs.set("race_id", rId);
        } else if (actId) {
          qs.set("activity_id", actId);
        }
        const res = await apiClient.get(`/api/miniapp/personal-share-card/${encodeURIComponent(uid)}?${qs.toString()}`);
        const data = res.data;
        if (data?.success) {
          setShareData(data);
          setRecentRuns(data.recent_runs || []);
          setCompletedRaces(data.completed_races || []);
          if (data.card_mode === "race" && data.selected_race?.id) {
            setCardMode("race");
            setSelectedRaceId(String(data.selected_race.id));
            if (data.default_photo_base64 && !hasCustomPhoto) {
              setUserPhotoDataUrl(`data:image/jpeg;base64,${data.default_photo_base64}`);
              const df = data.default_photo_focus || {};
              const fx = typeof df.focus_x === "number" ? df.focus_x : 0.5;
              const fy = typeof df.focus_y === "number" ? df.focus_y : 0.18;
              setAutoFocusX(fx);
              setAutoFocusY(fy);
              setPhotoFocusX(fx);
              setPhotoFocusY(fy);
              setFaceDetected(!!df.face_detected);
              setFocusPreset("auto");
            }
          } else {
            setCardMode("workout");
            if (data.actual_data?.id) {
              setSelectedActId(data.actual_data.id);
            }
          }
          const opts: Array<{ key: string; label: string; text: string }> = data.commentary_options || [];
          setCommentaryOptions(opts);
          const defaultKey = showDailyPlan ? "exec" : "phys";
          const matchedOpt = opts.find((o) => o.key === defaultKey) || opts[0];
          setActiveCommKey(matchedOpt?.key || "exec");
          setCustomCommentary(matchedOpt?.text || data.canova_commentary || "");
        }
      } catch (e) {
        console.error("Failed to fetch personal share card data:", e);
      } finally {
        setLoading(false);
      }
    },
    [uid, hasCustomPhoto]
  );

  useEffect(() => {
    if (open && uid) {
      if (raceId) {
        setCardMode("race");
        setSelectedRaceId(raceId);
        fetchCardData(undefined, raceId);
      } else {
        setCardMode("workout");
        setSelectedActId(activityId || "");
        fetchCardData(activityId, undefined);
      }
    }
  }, [open, uid, activityId, raceId, fetchCardData]);

  const detectFaceFocus = async (dataUrl: string) => {
    setDetectingFace(true);
    try {
      const res = await fetch("/api/miniapp/detect-face-focus", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_base64: dataUrl }),
      });
      const data = await res.json();
      if (data?.success) {
        const fx = typeof data.focus_x === "number" ? data.focus_x : 0.5;
        const fy = typeof data.focus_y === "number" ? data.focus_y : 0.18;
        setAutoFocusX(fx);
        setAutoFocusY(fy);
        setPhotoFocusX(fx);
        setPhotoFocusY(fy);
        setFaceDetected(!!data.face_detected);
        setFocusPreset("auto");
      }
    } catch (_) {
    } finally {
      setDetectingFace(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        setHasCustomPhoto(true);
        setUserPhotoDataUrl(reader.result);
        setPhotoFocusX(0.5);
        setPhotoFocusY(0.18);
        setAutoFocusX(0.5);
        setAutoFocusY(0.18);
        setFocusPreset("auto");
        detectFaceFocus(reader.result);
      }
    };
    reader.readAsDataURL(file);
  };

  const applyFocusPreset = (preset: "auto" | "top" | "upper" | "center" | "bottom") => {
    setFocusPreset(preset);
    if (preset === "auto") {
      setPhotoFocusX(autoFocusX);
      setPhotoFocusY(autoFocusY);
    } else if (preset === "top") {
      setPhotoFocusY(0.06);
    } else if (preset === "upper") {
      setPhotoFocusY(0.18);
    } else if (preset === "center") {
      setPhotoFocusY(0.5);
    } else if (preset === "bottom") {
      setPhotoFocusY(0.78);
    }
  };

  useEffect(() => {
    if (!open || !shareData) return;

    const loadImage = (src: string): Promise<HTMLImageElement | null> => {
      return new Promise((resolve) => {
        if (!src) return resolve(null);
        const img = new Image();
        img.crossOrigin = "anonymous";
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = src;
      });
    };

    const drawRoundRect = (
      ctx: CanvasRenderingContext2D,
      x: number,
      y: number,
      w: number,
      h: number,
      r: number,
      fill?: string,
      stroke?: string,
      lineWidth = 1.5
    ) => {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
      if (fill) {
        ctx.fillStyle = fill;
        ctx.fill();
      }
      if (stroke) {
        ctx.lineWidth = lineWidth;
        ctx.strokeStyle = stroke;
        ctx.stroke();
      }
    };

    const drawWrappedText = (
      ctx: CanvasRenderingContext2D,
      text: string,
      x: number,
      y: number,
      maxWidth: number,
      lineHeight: number,
      maxLines = 5
    ) => {
      const chars = Array.from(text || "");
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
          if (lineCount >= maxLines) return;
          continue;
        }
        const testLine = line + ch;
        if (ctx.measureText(testLine).width > maxWidth && line.length > 0) {
          if (lineCount === maxLines - 1) {
            ctx.fillText(line.slice(0, Math.max(1, line.length - 1)) + "…", x, curY);
            return;
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
      }
    };

    const render = async () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const W = 750;
      const H = 1460;
      canvas.width = W;
      canvas.height = H;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const d = shareData;
      const usr = d.user || {};
      const plan = d.day_plan || {};
      const act = d.actual_data || {};
      const trk = d.track_overlay || {};
      const isRace = !!(plan.is_race || d.card_mode === "race");

      const [photoImg, qrImg, avatarImg] = await Promise.all([
        loadImage(userPhotoDataUrl),
        loadImage(d.qrcode_base64 ? `data:image/jpeg;base64,${d.qrcode_base64}` : d.qrcode_url || ""),
        loadImage(usr.avatar_base64 ? `data:image/jpeg;base64,${usr.avatar_base64}` : usr.avatar_url || ""),
      ]);

      // Background (Theme-aware: Light Mode -> Pure Alabaster/White, Dark Mode -> Deep Obsidian)
      const isLight = isLightTheme;
      ctx.fillStyle = isLight ? "#F1F5F9" : "#090B10";
      ctx.fillRect(0, 0, W, H);
      drawRoundRect(
        ctx,
        24,
        24,
        W - 48,
        H - 48,
        30,
        isLight ? "#FFFFFF" : "#0E1118",
        isLight
          ? isRace
            ? "rgba(217,119,6,0.35)"
            : "rgba(15,23,42,0.09)"
          : isRace
          ? "rgba(251,191,36,0.28)"
          : "rgba(255,255,255,0.12)",
        1.5
      );

      // Section 1: Header
      const avX = 52;
      const avY = 48;
      const avSize = 64;
      if (avatarImg) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(avX + avSize / 2, avY + avSize / 2, avSize / 2, 0, Math.PI * 2);
        ctx.clip();
        ctx.drawImage(avatarImg, avX, avY, avSize, avSize);
        ctx.restore();
      } else {
        drawRoundRect(ctx, avX, avY, avSize, avSize, 32, isRace ? "#f59e0b" : "#fc4c02");
        ctx.font = "bold 28px sans-serif";
        ctx.fillStyle = "#ffffff";
        ctx.fillText(String(usr.display_name || "跑").slice(0, 1), avX + 18, avY + 42);
      }

      const runnerName = String(usr.display_name || "跑者").slice(0, 10);
      ctx.font = "bold 26px sans-serif";
      ctx.fillStyle = isLight ? "#0F172A" : "#ffffff";
      ctx.fillText(runnerName, 132, 76);

      const clubName = String(usr.club_name || "万跑跑团助手").slice(0, 14);
      const nameW = Math.min(220, ctx.measureText(runnerName).width + 20);
      drawRoundRect(
        ctx,
        132 + nameW,
        50,
        Math.min(240, clubName.length * 18 + 38),
        34,
        17,
        isLight
          ? isRace
            ? "#FEF3C7"
            : "#FFF3ED"
          : isRace
          ? "rgba(251,191,36,0.16)"
          : "rgba(252,76,2,0.16)",
        isLight
          ? isRace
            ? "rgba(217,119,6,0.4)"
            : "rgba(252,76,2,0.35)"
          : isRace
          ? "rgba(251,191,36,0.48)"
          : "rgba(252,76,2,0.45)",
        1
      );
      ctx.font = "bold 16px sans-serif";
      ctx.fillStyle = isLight ? (isRace ? "#B45309" : "#C23800") : isRace ? "#fbbf24" : "#fc4c02";
      ctx.fillText(`${isRace ? "🏅" : "🏃"} ${clubName}`, 146 + nameW, 72);

      ctx.font = "18px sans-serif";
      ctx.fillStyle = isLight ? "#64748B" : "#9ca3af";
      ctx.fillText(
        isRace ? "万跑跑团助手 · 官方完赛纪念战报" : "万跑跑团助手 · 每日运动打卡",
        132,
        106
      );

      ctx.font = "bold 20px monospace";
      ctx.fillStyle = isLight ? (isRace ? "#B45309" : "#FC4C02") : isRace ? "#fbbf24" : "#FC4C02";
      ctx.fillText(String(act.date || plan.date || "").replace(/-/g, "."), W - 168, 78);

      // Section 2: Hero Photo + Smart Face Centering + GPS Map & Elevation Overlay
      const pX = 52;
      const pY = 130;
      const pW = W - 104;
      const pH = showDailyPlan ? 480 : 586;
      const isHeroLight = isLight && !photoImg;

      ctx.save();
      drawRoundRect(ctx, pX, pY, pW, pH, 24, isHeroLight ? "#F8FAFC" : "#141926");
      ctx.clip();

      if (photoImg) {
        const scale = Math.max(pW / photoImg.width, pH / photoImg.height);
        const drawW = photoImg.width * scale;
        const drawH = photoImg.height * scale;
        const targetBoxX = 0.48;
        const targetBoxY = 0.28;
        const idealDrawX = pX + pW * targetBoxX - drawW * photoFocusX;
        const idealDrawY = pY + pH * targetBoxY - drawH * photoFocusY;
        const drawX = Math.min(pX, Math.max(pX + pW - drawW, idealDrawX));
        const drawY = Math.min(pY, Math.max(pY + pH - drawH, idealDrawY));
        ctx.drawImage(photoImg, drawX, drawY, drawW, drawH);

        // Dark vignettes over real photo for text legibility
        const topVig = ctx.createLinearGradient(0, pY, 0, pY + 100);
        topVig.addColorStop(0, "rgba(9,11,16,0.42)");
        topVig.addColorStop(1, "rgba(9,11,16,0)");
        ctx.fillStyle = topVig;
        ctx.fillRect(pX, pY, pW, 100);

        const botVig = ctx.createLinearGradient(0, pY + pH - 235, 0, pY + pH);
        botVig.addColorStop(0, "rgba(9,11,16,0)");
        botVig.addColorStop(0.45, "rgba(9,11,16,0.64)");
        botVig.addColorStop(1, "rgba(9,11,16,0.92)");
        ctx.fillStyle = botVig;
        ctx.fillRect(pX, pY + pH - 235, pW, 235);
      } else if (isHeroLight) {
        // High-Aesthetic Light Mode Hero Surface
        const heroGrad = ctx.createLinearGradient(pX, pY, pX + pW, pY + pH);
        heroGrad.addColorStop(0, isRace ? "#FFFBEB" : "#FFF7ED");
        heroGrad.addColorStop(0.55, "#F8FAFC");
        heroGrad.addColorStop(1, "#F0F9FF");
        ctx.fillStyle = heroGrad;
        ctx.fillRect(pX, pY, pW, pH);
      } else {
        const heroGrad = ctx.createLinearGradient(pX, pY, pX + pW, pY + pH);
        heroGrad.addColorStop(0, isRace ? "#271e12" : "#192236");
        heroGrad.addColorStop(0.5, "#111827");
        heroGrad.addColorStop(1, "#1e152a");
        ctx.fillStyle = heroGrad;
        ctx.fillRect(pX, pY, pW, pH);

        const topVig = ctx.createLinearGradient(0, pY, 0, pY + 100);
        topVig.addColorStop(0, "rgba(9,11,16,0.72)");
        topVig.addColorStop(1, "rgba(9,11,16,0)");
        ctx.fillStyle = topVig;
        ctx.fillRect(pX, pY, pW, 100);

        const botVig = ctx.createLinearGradient(0, pY + pH - 235, 0, pY + pH);
        botVig.addColorStop(0, "rgba(9,11,16,0)");
        botVig.addColorStop(0.45, "rgba(9,11,16,0.64)");
        botVig.addColorStop(1, "rgba(9,11,16,0.92)");
        ctx.fillStyle = botVig;
        ctx.fillRect(pX, pY + pH - 235, pW, 235);
      }

      // Top-Left Compact Pill on Hero
      drawRoundRect(
        ctx,
        pX + 18,
        pY + 18,
        290,
        34,
        17,
        isHeroLight ? "rgba(255,255,255,0.92)" : "rgba(15,18,28,0.62)",
        isHeroLight
          ? "rgba(15,23,42,0.1)"
          : isRace
          ? "rgba(251,191,36,0.35)"
          : "rgba(255,255,255,0.18)",
        1
      );
      ctx.font = "bold 16px sans-serif";
      ctx.fillStyle = isHeroLight ? "#0F172A" : isRace ? "#fde68a" : "#ffffff";
      ctx.fillText(`${isRace ? "🏅" : "🏃"} ${String(act.name || "户外跑步").slice(0, 15)}`, pX + 32, pY + 41);

      const hasBottomElev = overlayMode === "both" || overlayMode === "elevation";
      const stampBaseY = photoImg ? (hasBottomElev ? pY + pH - 168 : pY + pH - 52) : pY + 122;

      const distStr = Number(act.distance_km || 0).toFixed(2);
      ctx.font = "900 64px sans-serif";
      ctx.fillStyle = isHeroLight
        ? isRace
          ? "#D97706"
          : "#FC4C02"
        : isRace
        ? "#fbbf24"
        : "#FC4C02";
      ctx.fillText(distStr, pX + 22, stampBaseY);
      const distW = ctx.measureText(distStr).width;
      ctx.font = "bold 22px sans-serif";
      ctx.fillStyle = isHeroLight ? "#0F172A" : "#ffffff";
      ctx.fillText("KM", pX + 28 + distW, stampBaseY - 2);

      ctx.font = "18px sans-serif";
      ctx.fillStyle = isHeroLight ? "#334155" : "rgba(255,255,255,0.92)";
      ctx.fillText(
        isRace
          ? `完赛净成绩 ${act.duration_str || "—"}  ·  平均配速 ${act.avg_pace_str || "—"}/km`
          : `平均配速 ${act.avg_pace_str || "—"}/km  ·  用时 ${act.duration_str || "00:00"}`,
        pX + 24,
        stampBaseY + 28
      );

      // Draw GPS Route on Photo / Hero
      if (overlayMode === "both" || overlayMode === "map") {
        const withHud = trackPosition === "corner";
        const boxX = withHud ? pX + pW - 214 : pX + 120;
        const boxY = withHud ? pY + 18 : pY + (overlayMode === "both" ? 130 : 155);
        const boxW = withHud ? 196 : pW - 240;
        const extraHeroH = showDailyPlan ? 0 : 70;
        const boxH = withHud ? 178 : (overlayMode === "both" ? 210 : 280) + extraHeroH;

        if (withHud) {
          drawRoundRect(
            ctx,
            boxX,
            boxY,
            boxW,
            boxH,
            18,
            isHeroLight ? "rgba(255,255,255,0.94)" : "rgba(10,14,23,0.62)",
            isHeroLight ? "rgba(252,76,2,0.3)" : "rgba(252,76,2,0.45)",
            1.5
          );
          ctx.font = "bold 15px sans-serif";
          ctx.fillStyle = isHeroLight ? "#C23800" : "#FF7A45";
          ctx.fillText("🗺️ GPS 运动轨迹", boxX + 14, boxY + 24);
        }

        const padL = withHud ? 18 : 30;
        const padT = withHud ? 36 : 30;
        const plotW = boxW - padL * 2;
        const plotH = boxH - padT - 20;
        const rawPoints: Array<{ lat: number; lng: number }> = trk.points || [];
        let pts: Array<{ x: number; y: number }> = [];

        if (rawPoints.length >= 2) {
          const lats = rawPoints.map((p) => p.lat);
          const lngs = rawPoints.map((p) => p.lng);
          const minLat = Math.min(...lats);
          const maxLat = Math.max(...lats);
          const minLng = Math.min(...lngs);
          const maxLng = Math.max(...lngs);
          const cosLat = Math.max(0.4, Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180));
          const spanLat = Math.max(0.0005, maxLat - minLat);
          const spanLng = Math.max(0.0005, (maxLng - minLng) * cosLat);
          const scale = Math.min(plotW / spanLng, plotH / spanLat);
          const offsetX = boxX + padL + (plotW - spanLng * scale) / 2;
          const offsetY = boxY + padT + (plotH - spanLat * scale) / 2;
          pts = rawPoints.map((p) => ({
            x: offsetX + (p.lng - minLng) * cosLat * scale,
            y: offsetY + (maxLat - p.lat) * scale,
          }));
        } else {
          const cx = boxX + padL + plotW / 2;
          const cy = boxY + padT + plotH / 2;
          for (let i = 0; i <= 48; i++) {
            const ang = (i / 48) * Math.PI * 2;
            pts.push({ x: cx + Math.cos(ang) * plotW * 0.42, y: cy + Math.sin(ang) * plotH * 0.36 });
          }
        }

        if (pts.length >= 2) {
          ctx.save();
          ctx.lineCap = "round";
          ctx.lineJoin = "round";
          ctx.beginPath();
          pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
          ctx.lineWidth = withHud ? 8 : 13;
          ctx.strokeStyle = isHeroLight ? "rgba(252,76,2,0.2)" : "rgba(252,76,2,0.34)";
          ctx.stroke();

          ctx.lineWidth = withHud ? 4 : 6;
          ctx.strokeStyle = "#fc4c02";
          ctx.stroke();

          ctx.lineWidth = withHud ? 1.4 : 2.2;
          ctx.strokeStyle = isHeroLight ? "#FFF7ED" : "#FDBA74";
          ctx.stroke();

          const sPt = pts[0];
          const ePt = pts[pts.length - 1];
          ctx.beginPath();
          ctx.arc(sPt.x, sPt.y, 5, 0, Math.PI * 2);
          ctx.fillStyle = "#10b981";
          ctx.fill();
          ctx.beginPath();
          ctx.arc(ePt.x, ePt.y, 5.5, 0, Math.PI * 2);
          ctx.fillStyle = "#fc4c02";
          ctx.fill();
          ctx.restore();
        }
      }

      // Draw Elevation Profile on Photo / Hero
      if ((overlayMode === "both" || overlayMode === "elevation") && (trk.elevation_profile || []).length >= 2) {
        const elevList: Array<{ dist_km: number; elevation_m: number }> = trk.elevation_profile;
        const elevBoxH = overlayMode === "elevation" ? 160 : 132;
        const boxX = pX + 8;
        const boxY = pY + pH - elevBoxH - 6;
        const boxW = pW - 16;

        const elevs = elevList.map((e) => e.elevation_m);
        const minE = Math.min(...elevs);
        const maxE = Math.max(...elevs);
        const diffE = Math.max(8, maxE - minE);
        const totalDist = Math.max(0.1, elevList[elevList.length - 1].dist_km || 1);

        ctx.font = "bold 15px sans-serif";
        ctx.fillStyle = isHeroLight ? "#0369A1" : "#38bdf8";
        ctx.fillText(
          `⛰️ 海拔剖面 · 累计爬升 +${Math.round(Number(act.elevation_gain_meters || 0))}m · 最高 ${Math.round(maxE)}m`,
          boxX + 16,
          boxY + 20
        );

        const chartL = boxX + 16;
        const chartR = boxX + boxW - 16;
        const chartT = boxY + 32;
        const chartB = boxY + elevBoxH - 22;
        const chartW = chartR - chartL;
        const chartH = chartB - chartT;

        const pts = elevList.map((item, idx) => ({
          x: chartL + (totalDist > 0 ? item.dist_km / totalDist : idx / (elevList.length - 1)) * chartW,
          y: chartB - ((item.elevation_m - minE) / diffE) * chartH,
        }));

        ctx.beginPath();
        ctx.moveTo(pts[0].x, chartB);
        pts.forEach((p) => ctx.lineTo(p.x, p.y));
        ctx.lineTo(pts[pts.length - 1].x, chartB);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, chartT, 0, chartB);
        grad.addColorStop(0, isHeroLight ? "rgba(2,132,199,0.26)" : "rgba(56,189,248,0.42)");
        grad.addColorStop(1, isHeroLight ? "rgba(2,132,199,0.02)" : "rgba(56,189,248,0.04)");
        ctx.fillStyle = grad;
        ctx.fill();

        ctx.beginPath();
        pts.forEach((p, idx) => (idx === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
        ctx.lineWidth = 3;
        ctx.strokeStyle = isHeroLight ? "#0284C7" : "#38bdf8";
        ctx.stroke();
      }

      ctx.restore();
      drawRoundRect(
        ctx,
        pX,
        pY,
        pW,
        pH,
        24,
        undefined,
        isHeroLight
          ? "rgba(15,23,42,0.09)"
          : isRace
          ? "rgba(251,191,36,0.28)"
          : "rgba(255,255,255,0.16)",
        1.5
      );

      const drawFittedText = (
        text: string,
        x: number,
        y: number,
        maxWidth: number,
        maxFont: number,
        minFont = 12,
        bold = false
      ) => {
        const clean = String(text || "").trim();
        if (!clean || maxWidth <= 10) return;
        let sz = maxFont;
        while (sz > minFont) {
          ctx.font = `${bold ? "bold " : ""}${sz}px sans-serif`;
          if (ctx.measureText(clean).width <= maxWidth) break;
          sz -= 1;
        }
        ctx.font = `${bold ? "bold " : ""}${sz}px sans-serif`;
        if (ctx.measureText(clean).width <= maxWidth) {
          ctx.fillText(clean, x, y);
          return;
        }
        const chars = Array.from(clean);
        let out = "";
        for (let i = 0; i < chars.length; i++) {
          if (ctx.measureText(out + chars[i] + "…").width > maxWidth) break;
          out += chars[i];
        }
        ctx.fillText((out || chars[0] || "") + "…", x, y);
      };

      // Section 3A: Today's Plan OR Race Target (Optional via showDailyPlan)
      if (showDailyPlan) {
        const planY = 626;
        const planH = 122;
        const planAccent = isLight ? "#0F172A" : isRace ? "#fbbf24" : "#38bdf8";
        ctx.save();
        drawRoundRect(
          ctx,
          pX,
          planY,
          pW,
          planH,
          18,
          isLight ? "#F8FAFC" : "#121826",
          isLight ? "#E2E8F0" : isRace ? "rgba(251,191,36,0.42)" : "rgba(56,189,248,0.38)",
          1.5
        );
        ctx.clip();
        drawRoundRect(ctx, pX, planY + 18, 6, planH - 36, 3, isLight ? "#FC4C02" : planAccent);

        const compPct = Number(act.completion_pct || 0);
        const rightBadgeText = isRace && plan.badge_text ? String(plan.badge_text) : `达成率 ${compPct}%`;
        ctx.font = "bold 15px sans-serif";
        const badgeTextW = ctx.measureText(rightBadgeText).width;
        const badgeW = Math.max(128, Math.ceil(badgeTextW + 28));
        const badgeX = pX + pW - badgeW - 18;
        drawRoundRect(
          ctx,
          badgeX,
          planY + 16,
          badgeW,
          34,
          17,
          isLight ? "#ECFDF5" : isRace ? "rgba(251,191,36,0.16)" : "rgba(16,185,129,0.16)",
          isLight ? "#10B981" : isRace ? "#fbbf24" : "#10b981",
          1
        );
        ctx.fillStyle = isLight ? "#059669" : isRace ? "#fbbf24" : "#10b981";
        ctx.fillText(rightBadgeText, badgeX + (badgeW - badgeTextW) / 2, planY + 39);

        const rawPlanTitle = String(plan.title || (isRace ? "马拉松赛事" : "有氧耐力跑")).trim();
        ctx.fillStyle = planAccent;
        drawFittedText(
          `${plan.card_header_label || (isRace ? "🏁 赛前目标" : "📋 当天计划")}：${rawPlanTitle}`,
          pX + 24,
          planY + 41,
          badgeX - (pX + 24) - 14,
          21,
          14,
          true
        );

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

        ctx.fillStyle = isLight ? "#1E293B" : "#d4d4d8";
        drawFittedText(
          isRace
            ? `赛程距离 ${plan.distance_km || 0} km  |  ${plan.target_pace || "目标完赛"}  |  ${plan.target_hr_zone || ""}`
            : `目标距离 ${plan.distance_km || 0} km  |  目标配速 ${cleanPace}  |  心率 ${cleanHrZone}`,
          pX + 24,
          planY + 79,
          pW - 48,
          17,
          12
        );

        const pTitleStr = String(plan.plan_title || "Canova 科学耐力计划").trim();
        const pPhaseStr = String(plan.phase || "").trim();
        const pWeekStr = String(plan.week_title || "").trim();
        let planDescFull = pTitleStr;
        if (pPhaseStr && !pWeekStr.includes(pPhaseStr) && !pTitleStr.includes(pPhaseStr)) {
          planDescFull += ` · ${pPhaseStr}`;
        }
        if (pWeekStr && !pTitleStr.includes(pWeekStr)) {
          planDescFull += ` · ${pWeekStr}`;
        }
        ctx.fillStyle = isLight ? "#64748B" : "#9ca3af";
        drawFittedText(planDescFull, pX + 24, planY + 107, pW - 48, 15, 11);
        ctx.restore();
      }

      // Section 3B: Actual Completed Data
      const actY = showDailyPlan ? 762 : 732;
      const actH = showDailyPlan ? 180 : 184;
      ctx.save();
      drawRoundRect(
        ctx,
        pX,
        actY,
        pW,
        actH,
        18,
        isLight ? "#F8FAFC" : "#151621",
        isLight ? "#E2E8F0" : "rgba(252,76,2,0.35)",
        1.5
      );
      ctx.clip();
      ctx.font = "bold 20px sans-serif";
      ctx.fillStyle = isLight ? "#0F172A" : "#fc4c02";
      ctx.fillText(isRace ? "🏅 完赛核心战绩" : "⚡ 实际完成数据", pX + 22, actY + 36);

      const colW = (pW - 44 - 36) / 4;
      const metrics = [
        {
          label: isRace ? "完赛距离" : "实际距离",
          val: `${Number(act.distance_km || 0).toFixed(2)}`,
          unit: "km",
          color: "#FC4C02",
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
        drawRoundRect(
          ctx,
          mx,
          my,
          colW,
          110,
          14,
          isLight ? "#FFFFFF" : "#1C1E2B",
          isLight ? "#E2E8F0" : "rgba(255,255,255,0.06)",
          1
        );
        ctx.font = "16px sans-serif";
        ctx.fillStyle = isLight ? "#64748B" : "#9ca3af";
        ctx.fillText(m.label, mx + 14, my + 30);
        ctx.fillStyle = m.color;
        drawFittedText(m.val, mx + 14, my + 74, colW - 24, 28, 18, true);
        ctx.font = "14px sans-serif";
        ctx.fillStyle = isLight ? "#94A3B8" : "#71717a";
        ctx.fillText(m.unit, mx + 14, my + 98);
      });
      ctx.restore();

      // Section 4: Canova Commentary
      const cY = showDailyPlan ? 956 : 932;
      const cH = showDailyPlan ? 254 : 276;
      ctx.save();
      drawRoundRect(
        ctx,
        pX,
        cY,
        pW,
        cH,
        20,
        isLight ? "#F8FAFC" : "#171426",
        isLight ? "#E2E8F0" : "rgba(191,90,242,0.45)",
        1.5
      );
      ctx.clip();
      if (isLight) {
        drawRoundRect(ctx, pX, cY + 20, 6, cH - 40, 3, "#FC4C02");
      }
      ctx.font = "bold 22px sans-serif";
      ctx.fillStyle = isLight ? "#0F172A" : "#c084fc";
      ctx.fillText(isRace ? "👨‍🏫 Canova 教练完赛点评" : "👨‍🏫 Canova 教练点评", pX + 24, cY + 40);

      ctx.font = "18px sans-serif";
      ctx.fillStyle = isLight ? "#334155" : "#e4e4e7";
      drawWrappedText(
        ctx,
        `“${(customCommentary || d.canova_commentary || "").trim()}”`,
        pX + 24,
        cY + 80,
        pW - 52,
        33,
        showDailyPlan ? 5 : 6
      );
      ctx.restore();

      // Section 5: Invite QR Code
      const fY = 1224;
      const fH = 188;
      ctx.save();
      drawRoundRect(
        ctx,
        pX,
        fY,
        pW,
        fH,
        22,
        isLight ? "#F8FAFC" : "#121622",
        isLight ? "#E2E8F0" : "rgba(255,255,255,0.12)",
        1.5
      );
      ctx.clip();
      const qrBoxX = pX + pW - 162;
      const qrBoxY = fY + 18;
      const footerLeftMaxW = qrBoxX - (pX + 24) - 16;

      ctx.fillStyle = "#fc4c02";
      drawFittedText("🏅 万跑跑团助手 · 科学耐力训练", pX + 24, fY + 40, footerLeftMaxW, 18, 14, true);
      ctx.fillStyle = isLight ? "#0F172A" : "#ffffff";
      drawFittedText(`${runnerName} 邀你一起科学奔跑`, pX + 24, fY + 80, footerLeftMaxW, 25, 18, true);
      ctx.fillStyle = isLight ? "#475569" : "#a1a1aa";
      drawFittedText(`长按识别小程序码 · 加入【${clubName}】`, pX + 24, fY + 116, footerLeftMaxW, 18, 13);
      ctx.fillStyle = isLight ? "#64748B" : "#38bdf8";
      drawFittedText("⌚ 佳明/高驰手表自动同步  ·  📈 Canova 专属计划", pX + 24, fY + 152, footerLeftMaxW, 16, 12);
      drawRoundRect(
        ctx,
        qrBoxX,
        qrBoxY,
        132,
        132,
        14,
        "#ffffff",
        isLight ? "#E2E8F0" : undefined,
        1
      );
      if (qrImg) {
        ctx.drawImage(qrImg, qrBoxX + 6, qrBoxY + 6, 120, 120);
      }
      ctx.font = "bold 15px sans-serif";
      ctx.fillStyle = isLight ? "#059669" : "#10B981";
      ctx.fillText("长按扫码受邀入团", qrBoxX + 6, fY + 172);
      ctx.restore();

      setPosterDataUrl(canvas.toDataURL("image/jpeg", 0.92));
    };

    render();
  }, [
    open,
    shareData,
    userPhotoDataUrl,
    photoFocusX,
    photoFocusY,
    overlayMode,
    trackPosition,
    showDailyPlan,
    customCommentary,
    isLightTheme,
  ]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl max-h-[92vh] bg-[#12151e] border border-white/15 rounded-3xl flex flex-col overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <span>{cardMode === "race" ? "🏅 赛事完赛纪念分享卡" : "📸 个人打卡分享朋友圈卡片"}</span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              包含当天计划/赛前目标 · 实际完成数据 · Canova 教练点评 · 智能人脸置中 · 轨迹/海拔叠加 · 邀请码
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-zinc-300 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          {/* Left Controls */}
          <div className="md:col-span-5 space-y-4">
            {/* Mode Switcher */}
            {completedRaces.length > 0 && (
              <div className="bg-[#181c28] border border-white/10 rounded-2xl p-4 space-y-2.5">
                <div className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                  <Trophy className="w-4 h-4 text-amber-400" />
                  <span>切换分享卡模式</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => {
                      setCardMode("workout");
                      fetchCardData(selectedActId || recentRuns[0]?.id, undefined);
                    }}
                    className={`py-2 px-3 rounded-xl text-xs font-bold border transition ${
                      cardMode === "workout"
                        ? "bg-[#FC4C02] border-[#FC4C02] text-white shadow-sm"
                        : "bg-white/5 border-white/10 text-zinc-400"
                    }`}
                  >
                    🏃 日常训练打卡
                  </button>
                  <button
                    onClick={() => {
                      const rId = selectedRaceId || completedRaces[0]?.id;
                      setCardMode("race");
                      setSelectedRaceId(String(rId));
                      fetchCardData(undefined, String(rId));
                    }}
                    className={`py-2 px-3 rounded-xl text-xs font-bold border transition ${
                      cardMode === "race"
                        ? "bg-amber-500/20 border-amber-400 text-amber-300"
                        : "bg-white/5 border-white/10 text-zinc-400"
                    }`}
                  >
                    🏅 已完赛赛事 ({completedRaces.length})
                  </button>
                </div>

                {cardMode === "race" && (
                  <select
                    value={selectedRaceId}
                    onChange={(e) => {
                      setSelectedRaceId(e.target.value);
                      setHasCustomPhoto(false);
                      fetchCardData(undefined, e.target.value);
                    }}
                    className="w-full bg-[#0e1118] border border-amber-400/40 rounded-xl px-3 py-2 text-xs text-amber-200 mt-1"
                  >
                    {completedRaces.map((rc) => (
                      <option key={rc.id} value={rc.id}>
                        {rc.label}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {/* Toggle: Show or Hide Daily Plan / Pre-race Target */}
            <div className="bg-[#181c28] border border-white/10 rounded-2xl p-4 space-y-2.5">
              <div className="text-xs font-bold text-zinc-300 flex items-center justify-between">
                <span>📋 {cardMode === "race" ? "赛前目标模块显示" : "当日计划模块显示"}</span>
                <span className="text-[11px] font-normal text-zinc-400">
                  {showDailyPlan ? "显示计划与达成率" : "已隐藏计划，放大照片区"}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => {
                    setShowDailyPlan(true);
                    if (activeCommKey === "phys") {
                      const execOpt = commentaryOptions.find((o) => o.key === "exec");
                      const physOpt = commentaryOptions.find((o) => o.key === "phys");
                      if (execOpt && (!customCommentary || customCommentary === physOpt?.text)) {
                        setActiveCommKey("exec");
                        setCustomCommentary(execOpt.text);
                      }
                    }
                  }}
                  className={`py-2 px-3 rounded-xl text-xs font-bold border transition cursor-pointer ${
                    showDailyPlan
                      ? "bg-[#FC4C02] border-[#FC4C02] text-white shadow-sm"
                      : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                  }`}
                >
                  {cardMode === "race" ? "🏁 显示赛前目标" : "📋 显示当日计划"}
                </button>
                <button
                  onClick={() => {
                    setShowDailyPlan(false);
                    if (activeCommKey === "exec") {
                      const execOpt = commentaryOptions.find((o) => o.key === "exec");
                      const physOpt = commentaryOptions.find((o) => o.key === "phys");
                      if (physOpt && (!customCommentary || customCommentary === execOpt?.text)) {
                        setActiveCommKey("phys");
                        setCustomCommentary(physOpt.text);
                      }
                    }
                  }}
                  className={`py-2 px-3 rounded-xl text-xs font-bold border transition cursor-pointer ${
                    !showDailyPlan
                      ? "bg-[#FC4C02] border-[#FC4C02] text-white shadow-sm"
                      : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                  }`}
                >
                  {cardMode === "race" ? "🙈 不显示赛前目标" : "🙈 不显示当日计划"}
                </button>
              </div>
            </div>

            {/* Photo Picker + Smart Face Focus */}
            <div className="bg-[#181c28] border border-white/10 rounded-2xl p-4 space-y-3">
              <div className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                <Camera className="w-4 h-4 text-[#FC4C02]" />
                <span>1. 选择跑步/完赛照片（自动人脸置中）</span>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
              />
              <div className="flex gap-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-[#FC4C02] to-[#ff7a00] text-white text-xs font-bold hover:opacity-95 transition"
                >
                  {userPhotoDataUrl ? "🖼️ 更换照片 (智能人脸置中)" : "📸 选择照片 (智能人脸置中)"}
                </button>
                {userPhotoDataUrl && (
                  <button
                    onClick={() => {
                      setHasCustomPhoto(false);
                      setUserPhotoDataUrl("");
                    }}
                    className="py-2.5 px-3 rounded-xl bg-white/10 text-zinc-300 text-xs hover:bg-white/15 transition"
                  >
                    默认背景
                  </button>
                )}
              </div>

              {userPhotoDataUrl && (
                <div className="bg-[#0e1118] border border-emerald-500/30 rounded-xl p-3 space-y-2">
                  <div className="text-[11px] text-emerald-400 font-semibold">
                    🎯 {detectingFace ? "正在识别人脸位置..." : faceDetected ? "✨ 已自动识别人脸并置中" : "✨ 已智能锁定人像头部置中"}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      { k: "auto", l: "🤖 自动人脸" },
                      { k: "top", l: "⬆️ 露头顶" },
                      { k: "upper", l: "👤 头部黄金位" },
                      { k: "center", l: "⏺️ 几何正中" },
                      { k: "bottom", l: "⬇️ 偏下全身" },
                    ].map((p) => (
                      <button
                        key={p.k}
                        onClick={() => applyFocusPreset(p.k as any)}
                        className={`px-2 py-1 rounded-lg text-[11px] font-semibold border transition ${
                          focusPreset === p.k
                            ? "bg-emerald-600 border-emerald-600 text-white"
                            : "bg-white/5 border-white/10 text-zinc-400"
                        }`}
                      >
                        {p.l}
                      </button>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 pt-1">
                    <span className="text-[11px] text-zinc-400">上下微调</span>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={Math.round(photoFocusY * 100)}
                      onChange={(e) => {
                        setFocusPreset("upper");
                        setPhotoFocusY(Number(e.target.value) / 100);
                      }}
                      className="flex-1 accent-[#FC4C02]"
                    />
                    <span className="text-[11px] text-[#FC4C02] font-mono font-bold w-9 text-right">
                      {Math.round(photoFocusY * 100)}%
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Overlay Mode */}
            <div className="bg-[#181c28] border border-white/10 rounded-2xl p-4 space-y-3">
              <div className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                <MapPin className="w-4 h-4 text-[#FC4C02]" />
                <span>2. 地图轨迹 / 海拔叠加模式</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { key: "both", label: "轨迹+海拔" },
                  { key: "map", label: "仅轨迹图" },
                  { key: "elevation", label: "仅海拔线" },
                ].map((m) => (
                  <button
                    key={m.key}
                    onClick={() => setOverlayMode(m.key as any)}
                    className={`py-2 px-2 rounded-xl text-xs font-bold border transition ${
                      overlayMode === m.key
                        ? "bg-[#FC4C02] border-[#FC4C02] text-white shadow-sm"
                        : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>

              {overlayMode !== "elevation" && (
                <div className="pt-2 space-y-2">
                  <div className="text-[11px] text-zinc-400">轨迹在照片上的位置：</div>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setTrackPosition("corner")}
                      className={`py-1.5 px-2 rounded-xl text-xs font-semibold border transition ${
                        trackPosition === "corner"
                          ? "bg-[#FC4C02]/15 border-[#FC4C02] text-[#FC4C02]"
                          : "bg-white/5 border-white/10 text-zinc-400"
                      }`}
                    >
                      右上悬浮窗 (不挡人像)
                    </button>
                    <button
                      onClick={() => setTrackPosition("center")}
                      className={`py-1.5 px-2 rounded-xl text-xs font-semibold border transition ${
                        trackPosition === "center"
                          ? "bg-[#FC4C02]/15 border-[#FC4C02] text-[#FC4C02]"
                          : "bg-white/5 border-white/10 text-zinc-400"
                      }`}
                    >
                      居中大轨迹 (Strava风)
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Run Switcher (Workout mode) */}
            {cardMode === "workout" && recentRuns.length > 1 && (
              <div className="bg-[#181c28] border border-white/10 rounded-2xl p-4 space-y-2.5">
                <div className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                  <Mountain className="w-4 h-4 text-[#FC4C02]" />
                  <span>3. 切换打卡跑步记录</span>
                </div>
                <select
                  value={selectedActId}
                  onChange={(e) => {
                    setSelectedActId(e.target.value);
                    fetchCardData(e.target.value, undefined);
                  }}
                  className="w-full bg-[#0e1118] border border-white/15 rounded-xl px-3 py-2 text-xs text-white"
                >
                  {recentRuns.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label} - {r.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Canova Commentary */}
            <div className="bg-[#181c28] border border-white/10 rounded-2xl p-4 space-y-3">
              <div className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-[#FC4C02]" />
                <span>4. Canova 教练点评</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {commentaryOptions.map((opt) => (
                  <button
                    key={opt.key}
                    onClick={() => {
                      setActiveCommKey(opt.key);
                      setCustomCommentary(opt.text);
                    }}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition ${
                      activeCommKey === opt.key
                        ? "bg-[#FC4C02]/15 border-[#FC4C02] text-[#FC4C02]"
                        : "bg-white/5 border-white/10 text-zinc-400"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
              <textarea
                value={customCommentary}
                onChange={(e) => setCustomCommentary(e.target.value)}
                rows={4}
                className="w-full bg-[#0e1118] border border-white/10 rounded-xl p-2.5 text-xs text-zinc-200 leading-relaxed focus:outline-none focus:border-[#FC4C02]"
              />
            </div>

            {/* Download Action */}
            {posterDataUrl && (
              <a
                href={posterDataUrl}
                download={`RGM_${cardMode === "race" ? "完赛分享卡" : "打卡分享卡"}_${shareData?.actual_data?.date || "today"}.jpg`}
                className="w-full py-3 px-4 rounded-2xl bg-gradient-to-r from-[#FC4C02] to-[#EA580C] text-white font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg shadow-[#FC4C02]/25 hover:opacity-95 transition"
              >
                <Download className="w-4 h-4" />
                <span>下载高清分享卡片 (发朋友圈)</span>
              </a>
            )}
          </div>

          {/* Right Live Poster Preview */}
          <div className="md:col-span-7 flex flex-col items-center justify-center bg-[#0b0d13] border border-white/5 rounded-2xl p-4">
            {loading ? (
              <div className="py-24 flex flex-col items-center gap-3 text-zinc-400 text-xs">
                <RefreshCw className="w-6 h-6 text-[#FC4C02] animate-spin" />
                <span>正在合成分享卡片...</span>
              </div>
            ) : posterDataUrl ? (
              <img
                src={posterDataUrl}
                alt="Personal Moments Share Card"
                className="w-full max-w-[380px] rounded-2xl shadow-2xl border border-white/10"
              />
            ) : null}
            <canvas ref={canvasRef} className="hidden" />
          </div>
        </div>
      </div>
    </div>
  );
}
