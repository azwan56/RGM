"use client";

import React, { useState, useMemo, useEffect, useCallback } from "react";
import { Maximize2, X, Compass, Mountain, Loader2, Lock } from "lucide-react";
import apiClient from "@/lib/apiClient";

interface RouteMapPreviewProps {
  activityId?: string;
  trackData?: any;
  mapImageUrl?: string;
  activityName?: string;
  distanceMeters?: number;
  elevationGain?: number;
  avgPace?: string;
  eagerFetch?: boolean;
  isSegmentHiddenHint?: boolean;
  clubId?: string;
  captainCheer?: string | null;
  captainCheerMeta?: {
    club_id?: string;
    club_name?: string;
    captain_name?: string;
    captain_title?: string;
    scenario?: string;
  } | null;
}

function resolveClientViewerUid(): string {
  if (typeof window === "undefined") return "";
  try {
    const raw = localStorage.getItem("rgm_auth_session");
    if (raw) {
      const sess = JSON.parse(raw);
      const id = sess?.user?.id || sess?.uid || "";
      if (id) return String(id);
    }
  } catch {}
  return "";
}

export default function RouteMapPreview({
  activityId,
  trackData: rawTrack,
  mapImageUrl,
  activityName,
  distanceMeters,
  elevationGain,
  avgPace,
  eagerFetch = false,
  isSegmentHiddenHint = false,
  clubId,
  captainCheer,
  captainCheerMeta,
}: RouteMapPreviewProps) {
  const [activeTab, setActiveTab] = useState<"map" | "segments" | "elevation">("map");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [onDemandTrack, setOnDemandTrack] = useState<any>(null);
  const [segmentAnalysis, setSegmentAnalysis] = useState<any>(null);
  const [isSegmentHidden, setIsSegmentHidden] = useState<boolean>(Boolean(isSegmentHiddenHint));
  const [segmentHiddenMessage, setSegmentHiddenMessage] = useState<string>("");
  const [fetchedCaptainCheer, setFetchedCaptainCheer] = useState<string | null>(null);
  const [fetchedCaptainMeta, setFetchedCaptainMeta] = useState<any>(null);
  const [hasFetchedDetail, setHasFetchedDetail] = useState(false);
  const [isLoadingTrack, setIsLoadingTrack] = useState(false);

  const track = useMemo(() => {
    const src = onDemandTrack || rawTrack;
    if (!src) return null;
    if (typeof src === "string") {
      try {
        return JSON.parse(src);
      } catch {
        return null;
      }
    }
    return src;
  }, [rawTrack, onDemandTrack]);

  const fetchActivityDetail = useCallback(async () => {
    if (!activityId || isLoadingTrack || hasFetchedDetail) return;
    setIsLoadingTrack(true);
    try {
      const viewerUid = resolveClientViewerUid();
      const params = new URLSearchParams();
      if (viewerUid) params.set("viewer_uid", viewerUid);
      if (clubId) params.set("club_id", clubId);
      const qs = params.toString();
      const q = qs ? `?${qs}` : "";
      const res = await apiClient.get(`/api/miniapp/activities/${activityId}/track${q}`);
      if (res.data?.success) {
        if (res.data?.track?.points?.length > 1) {
          setOnDemandTrack(res.data.track);
        }
        setIsSegmentHidden(Boolean(res.data?.is_segment_hidden));
        setSegmentHiddenMessage(res.data?.segment_hidden_message || res.data?.message || "");
        if (res.data?.captain_cheer !== undefined) {
          setFetchedCaptainCheer(res.data.captain_cheer);
          setFetchedCaptainMeta(res.data.captain_cheer_meta || null);
        }
        if (res.data?.segment_analysis) {
          setSegmentAnalysis(res.data.segment_analysis);
          const hasPts = (res.data?.track?.points?.length || track?.points?.length || 0) > 1;
          if (!hasPts && !mapImageUrl) {
            setActiveTab("segments");
          }
        }
      }
    } catch {
      // Ignore transient network errors
    } finally {
      setHasFetchedDetail(true);
      setIsLoadingTrack(false);
    }
  }, [activityId, isLoadingTrack, hasFetchedDetail, track, mapImageUrl, clubId]);

  // Eagerly fetch when explicitly expanded on personal dashboard
  useEffect(() => {
    if (!eagerFetch || !activityId || hasFetchedDetail) return;
    fetchActivityDetail();
  }, [eagerFetch, activityId, hasFetchedDetail, fetchActivityDetail]);

  const handleSwitchTab = (tab: "map" | "segments" | "elevation") => {
    setActiveTab(tab);
    if (tab === "segments" && !hasFetchedDetail) {
      fetchActivityDetail();
    }
  };

  const handleOpenModal = () => {
    setIsModalOpen(true);
    if (!hasFetchedDetail) {
      fetchActivityDetail();
    }
  };

  const points = useMemo(() => track?.points || [], [track]);
  const elevationProfile = useMemo(() => track?.elevation_profile || [], [track]);

  const distanceKm = useMemo(() => {
    if (distanceMeters) return (distanceMeters / 1000).toFixed(2);
    return "0.00";
  }, [distanceMeters]);

  const { pathD, startPt, endPt } = useMemo(() => {
    if (!points || points.length < 2) {
      return { pathD: "", startPt: null, endPt: null };
    }
    const lats = points.map((p: any) => p.latitude);
    const lngs = points.map((p: any) => p.longitude);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);

    const midLatRad = ((minLat + maxLat) / 2) * (Math.PI / 180);
    const cosLat = Math.cos(midLatRad);
    const dLng = (maxLng - minLng) * cosLat;
    const dLat = maxLat - minLat;

    const pad = 24;
    const availW = 600 - pad * 2;
    const availH = 220 - pad * 2;
    const scale = Math.min(availW / (dLng || 1e-6), availH / (dLat || 1e-6));

    const shapeW = dLng * scale;
    const shapeH = dLat * scale;
    const offsetX = pad + (availW - shapeW) / 2;
    const offsetY = pad + (availH - shapeH) / 2;

    const projected = points.map((p: any) => {
      const x = offsetX + (p.longitude - minLng) * cosLat * scale;
      const y = offsetY + (maxLat - p.latitude) * scale;
      return { x: Math.round(x * 10) / 10, y: Math.round(y * 10) / 10 };
    });

    const path = projected.reduce((acc: string, pt: { x: number; y: number }, idx: number) => {
      return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`;
    }, "");

    return {
      pathD: path,
      startPt: projected[0],
      endPt: projected[projected.length - 1],
    };
  }, [points]);

  const { elevPathLine, elevPathArea, minElev, maxElev } = useMemo(() => {
    if (!elevationProfile || elevationProfile.length < 2) {
      return { elevPathLine: "", elevPathArea: "", minElev: 0, maxElev: 0 };
    }
    const elevs = elevationProfile.map((p: any) => p.elevation_m);
    const minE = Math.min(...elevs);
    const maxE = Math.max(...elevs);
    const diffE = Math.max(10, maxE - minE);
    const totalDist = elevationProfile[elevationProfile.length - 1].dist_km || 1;

    const coords = elevationProfile.map((item: any) => {
      const x = Math.round(((item.dist_km / totalDist) * 560 + 20) * 10) / 10;
      const normH = (item.elevation_m - minE) / diffE;
      const y = Math.round((140 - normH * 110) * 10) / 10;
      return { x, y };
    });

    const line = coords.reduce((acc: string, pt: { x: number; y: number }, idx: number) => {
      return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`;
    }, "");

    const first = coords[0];
    const last = coords[coords.length - 1];
    const area = `${line} L ${last.x} 150 L ${first.x} 150 Z`;

    return {
      elevPathLine: line,
      elevPathArea: area,
      minElev: Math.round(minE),
      maxElev: Math.round(maxE),
    };
  }, [elevationProfile]);

  const phaseBlocks = useMemo(() => {
    const phases = segmentAnalysis?.phases || [];
    if (!phases.length) return [];
    const totalKm = Math.max(
      0.1,
      phases.reduce((acc: number, p: any) => acc + Number(p.distance_km || 0), 0)
    );
    return phases.map((p: any) => {
      const pt = String(p.phase_type || "cruise");
      let bgClass = "bg-[#FC4C02]";
      if (pt === "warmup" || pt === "cooldown" || pt === "start_control") bgClass = "bg-sky-500";
      else if (pt === "intervals" || pt === "progression" || pt === "final_kick") bgClass = "bg-rose-500";
      else if (pt === "fade" || pt === "wall_zone") bgClass = "bg-amber-500";
      const cleanLbl = String(p.label || "").replace(/^[^\u4e00-\u9fa5A-Za-z0-9]+/, "").split(" ")[0];
      return {
        shortLabel: cleanLbl || "分段",
        distance_km: p.distance_km,
        widthPct: Math.max(8, Math.round((Number(p.distance_km || 0) / totalKm) * 100)),
        bgClass,
      };
    });
  }, [segmentAnalysis]);

  const splitBars = useMemo(() => {
    const splits = segmentAnalysis?.km_splits || [];
    if (!splits.length) return [];
    const paces = splits.map((s: any) => Number(s.pace_sec || 0)).filter((v: number) => v > 0);
    const fastest = paces.length ? Math.min(...paces) : 300;
    const slowest = paces.length ? Math.max(...paces) : 420;
    const span = Math.max(25, slowest - fastest);
    return splits.map((s: any, idx: number) => {
      const pSec = Number(s.pace_sec || fastest);
      const ratio = Math.max(0, Math.min(1, (slowest - pSec) / span));
      const barPct = Math.round(56 + ratio * 44);
      const dKm = Number(s.distance_m || 1000) / 1000;
      const lbl = Math.abs(dKm - 1.0) <= 0.12 ? `${idx + 1}km` : `${dKm.toFixed(2)}k`;
      return {
        label: lbl,
        paceShort: String(s.pace_str || "—").replace("/km", ""),
        avg_hr: s.avg_hr || null,
        barPct,
        isFastest: paces.length >= 2 && pSec === fastest,
      };
    });
  }, [segmentAnalysis]);

  const renderSegmentDiagnosisBlock = (compact = false) => {
    if (isLoadingTrack && !segmentAnalysis) {
      return (
        <div className="p-5 flex items-center justify-center gap-2 text-xs text-zinc-400">
          <Loader2 className="w-4 h-4 animate-spin text-[#FC4C02]" />
          <span>正在拉取手表分段与时序数据并生成教练诊断...</span>
        </div>
      );
    }

    if (isSegmentHidden) {
      return (
        <div className="p-4 rounded-xl bg-zinc-900/70 border border-dashed border-white/10 text-xs text-zinc-400 flex items-center gap-2">
          <Lock className="w-4 h-4 text-zinc-400 shrink-0" />
          <span>{segmentHiddenMessage || "该跑者已开启运动隐私保护，分段诊断仅对本人、师傅及教练开放"}</span>
        </div>
      );
    }

    if (!segmentAnalysis) {
      return (
        <div className="p-4 text-center text-xs text-zinc-500">
          暂无细粒度分段记录
        </div>
      );
    }

    return (
      <div className={compact ? "p-4 space-y-3" : "space-y-4"}>
        {/* Mode & Title */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="px-2.5 py-0.5 rounded-md text-[11px] font-bold bg-[#FC4C02]/15 text-[#fb923c] border border-[#FC4C02]/30">
              {segmentAnalysis.mode_label}
            </span>
            {segmentAnalysis.is_track_run && (
              <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-sky-500/15 text-sky-300 border border-sky-500/25">
                🏟️ 田径场训练
              </span>
            )}
            <span className="text-sm font-extrabold text-white">{segmentAnalysis.summary_title}</span>
          </div>
        </div>

        {/* Proportional Phase Bar */}
        {phaseBlocks.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex w-full h-2.5 rounded-full overflow-hidden gap-0.5 bg-white/5">
              {phaseBlocks.map((blk: any, bi: number) => (
                <div
                  key={bi}
                  className={`h-full ${blk.bgClass}`}
                  style={{ width: `${blk.widthPct}%` }}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-zinc-400">
              {phaseBlocks.map((blk: any, bi: number) => (
                <span key={bi} className="inline-flex items-center gap-1">
                  <span className={`w-2 h-2 rounded-full ${blk.bgClass}`} />
                  <span>
                    {blk.shortLabel} {blk.distance_km}k
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Preset Race Highlight */}
        {segmentAnalysis.race_diagnosis && (
          <div className="rounded-xl bg-[#FC4C02]/10 border border-[#FC4C02]/30 p-3 space-y-1.5 text-xs">
            <div className="font-bold text-white">{segmentAnalysis.race_diagnosis.goal_verdict}</div>
            {segmentAnalysis.race_diagnosis.half_split && (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-bold text-[#fb923c]">
                  {segmentAnalysis.race_diagnosis.half_split.split_label}
                </span>
                <span className="text-[11px] text-zinc-400">
                  前半 {segmentAnalysis.race_diagnosis.half_split.first_half_pace} · 后半{" "}
                  {segmentAnalysis.race_diagnosis.half_split.second_half_pace}
                </span>
              </div>
            )}
            <div className="text-zinc-200 leading-relaxed">{segmentAnalysis.race_diagnosis.cause_title}</div>
          </div>
        )}

        {/* Planned Workout Comparison KPIs */}
        {!segmentAnalysis.race_diagnosis && segmentAnalysis.plan_comparison && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-xl bg-white/[0.03] border border-white/10 p-2.5">
              <div className="text-[10px] text-zinc-400">
                {segmentAnalysis.plan_comparison.has_wucd_structure ? "主课达成" : "课表达成"}
              </div>
              <div className="text-sm font-black text-[#FC4C02]">
                {segmentAnalysis.plan_comparison.compliance_pct}%
              </div>
              <div className="text-[10px] text-zinc-500">
                {segmentAnalysis.plan_comparison.actual_main_km}/{segmentAnalysis.plan_comparison.planned_main_km}km
              </div>
            </div>
            <div className="rounded-xl bg-white/[0.03] border border-white/10 p-2.5">
              <div className="text-[10px] text-zinc-400">主课配速</div>
              <div className="text-sm font-bold text-white">
                {segmentAnalysis.plan_comparison.actual_main_pace_str}
              </div>
              <div className="text-[10px] text-zinc-500">
                目标 {segmentAnalysis.plan_comparison.target_pace_str}
              </div>
            </div>
            <div className="rounded-xl bg-white/[0.03] border border-white/10 p-2.5">
              <div className="text-[10px] text-zinc-400">稳态心率</div>
              <div className="text-sm font-bold text-rose-400">
                {segmentAnalysis.plan_comparison.actual_main_steady_hr
                  ? `${segmentAnalysis.plan_comparison.actual_main_steady_hr}bpm`
                  : "—"}
              </div>
              <div className="text-[10px] text-zinc-500">
                {segmentAnalysis.plan_comparison.aerobic_decoupling_pct !== null &&
                segmentAnalysis.plan_comparison.aerobic_decoupling_pct !== undefined
                  ? `解耦率 ${segmentAnalysis.plan_comparison.aerobic_decoupling_pct}%`
                  : segmentAnalysis.plan_comparison.target_hr_str || "生理稳态"}
              </div>
            </div>
          </div>
        )}

        {/* Phase-by-Phase Cards */}
        <div className="grid grid-cols-1 gap-2">
          {(segmentAnalysis.phases || []).map((ph: any, pidx: number) => (
            <div
              key={pidx}
              className="rounded-xl bg-white/[0.03] border border-white/10 px-3 py-2.5 text-xs space-y-1"
            >
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-baseline gap-2">
                  <span className="font-bold text-white">{ph.label}</span>
                  <span className="text-[11px] text-zinc-500">
                    {ph.range_str} · {ph.distance_km}km
                  </span>
                </div>
                {ph.status_tag && (
                  <span
                    className={`text-[11px] font-bold ${
                      String(ph.status_tag).includes("⚠️") ? "text-amber-400" : "text-emerald-400"
                    }`}
                  >
                    {ph.status_tag}
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-3 text-[11px] text-zinc-300 font-medium">
                <span>⏱️ {ph.pace_str}</span>
                <span>⌛ {ph.duration_str}</span>
                {ph.steady_hr && <span className="text-rose-400">❤️ 稳态 {ph.steady_hr}bpm</span>}
                {ph.elev_gain_m >= 8 && <span className="text-emerald-400">⛰️ +{Math.round(ph.elev_gain_m)}m</span>}
              </div>
              {ph.comment && <div className="text-[11px] text-zinc-400 leading-relaxed">{ph.comment}</div>}
            </div>
          ))}
        </div>

        {/* Per-Km Splits Bar Table (shown in full modal or when compact has room) */}
        {!compact && splitBars.length > 1 && (
          <div className="rounded-xl bg-[#0d0d10] border border-white/10 p-3 space-y-1.5">
            <div className="text-[11px] font-semibold text-zinc-400 pb-1 border-b border-white/5 flex justify-between">
              <span>逐公里 / 计圈分段配速</span>
              <span>最快分段绿色高亮</span>
            </div>
            <div className="max-h-52 overflow-y-auto space-y-1 pr-1">
              {splitBars.map((sp: any, si: number) => (
                <div key={si} className="flex items-center gap-2 text-[11px]">
                  <span className="w-11 text-zinc-400 font-semibold shrink-0">{sp.label}</span>
                  <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className={`h-full rounded-full ${sp.isFastest ? "bg-emerald-500" : "bg-[#FC4C02]"}`}
                      style={{ width: `${sp.barPct}%` }}
                    />
                  </div>
                  <span className="w-12 text-right font-bold text-zinc-200 shrink-0">{sp.paceShort}</span>
                  <span className="w-11 text-right text-rose-400 font-medium shrink-0">
                    {sp.avg_hr ? `${sp.avg_hr}` : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Coach Advice */}
        {segmentAnalysis.coach_advice && (
          <div className="text-xs text-zinc-300 pt-2 border-t border-white/10 leading-relaxed">
            💡 {segmentAnalysis.coach_advice}
          </div>
        )}
      </div>
    );
  };

  if (isLoadingTrack && !points.length && !mapImageUrl && !segmentAnalysis) {
    return (
      <div className="rounded-2xl border border-white/5 bg-[#121215]/60 p-4 text-xs text-zinc-400 flex items-center justify-center gap-2 animate-pulse my-2">
        <Loader2 className="w-3.5 h-3.5 animate-spin text-[#FC4C02]" />
        <span>正在加载 GPS 航迹与智能分段复盘...</span>
      </div>
    );
  }

  const hasMapVisual = Boolean(mapImageUrl || (points && points.length >= 2));
  const canOnDemandLoad =
    !hasFetchedDetail &&
    !isSegmentHidden &&
    Boolean(activityId && (activityId.startsWith("garmin_") || activityId.startsWith("coros_")));

  if (!hasMapVisual && !segmentAnalysis && !isSegmentHidden) {
    if (canOnDemandLoad) {
      return (
        <button
          type="button"
          onClick={handleOpenModal}
          className="w-full rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.06] px-4 py-2.5 text-xs text-zinc-300 flex items-center justify-between transition"
        >
          <span className="flex items-center gap-2 font-medium">
            <span>🗺️</span>
            <span>点击查看 GPS 轨迹与智能分段复盘</span>
          </span>
          <span className="text-[#FC4C02] font-bold">展开 ›</span>
        </button>
      );
    }
    return null;
  }

  return (
    <>
      <div className="rounded-2xl overflow-hidden border border-white/10 bg-[#121215] shadow-xl transition hover:border-white/20">
        {/* Header Switcher */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-white/[0.03] border-b border-white/5 text-xs flex-wrap gap-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            {hasMapVisual && (
              <button
                type="button"
                onClick={() => handleSwitchTab("map")}
                className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
                  activeTab === "map"
                    ? "bg-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/20"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <span>🗺️</span>
                <span>GPS 路线</span>
              </button>
            )}
            {(!isSegmentHidden || eagerFetch) && (
              <button
                type="button"
                onClick={() => handleSwitchTab("segments")}
                className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
                  activeTab === "segments" || (!hasMapVisual && activeTab === "map")
                    ? "bg-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/20"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <span>⏱️</span>
                <span>分段复盘</span>
              </button>
            )}
            {elevationProfile && elevationProfile.length > 1 && (
              <button
                type="button"
                onClick={() => handleSwitchTab("elevation")}
                className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
                  activeTab === "elevation"
                    ? "bg-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/20"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Mountain className="w-3.5 h-3.5" />
                <span>海拔 ({maxElev}m)</span>
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={handleOpenModal}
            className="text-zinc-400 hover:text-white transition p-1 rounded-md hover:bg-white/10 flex items-center gap-1 text-[11px]"
            title="放大查看完整轨迹与分段报告"
          >
            <Maximize2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">全屏详情</span>
          </button>
        </div>

        {/* Content Body */}
        {activeTab === "segments" || !hasMapVisual ? (
          <div className="bg-gradient-to-b from-[#16161b] to-[#0d0d10]">
            {renderSegmentDiagnosisBlock(true)}
          </div>
        ) : (
          <div className="relative cursor-pointer group" onClick={handleOpenModal}>
            {activeTab === "map" ? (
              mapImageUrl && points.length < 2 ? (
                <div className="relative h-56 w-full bg-[#121215] overflow-hidden flex items-center justify-center group">
                  <div
                    className="absolute inset-0 opacity-20 scale-125 pointer-events-none"
                    style={{
                      backgroundImage: `url(${mapImageUrl})`,
                      backgroundPosition: "center",
                      backgroundSize: "cover",
                      filter: "blur(24px) hue-rotate(-52deg) saturate(1.4)",
                    }}
                  />
                  <img
                    src={mapImageUrl}
                    alt="跑步路线地图"
                    className="relative z-10 max-h-full max-w-full object-contain transition-transform duration-300 group-hover:scale-105"
                    style={{
                      filter: "hue-rotate(-52deg) saturate(1.25) contrast(1.08)",
                    }}
                  />
                  <div className="absolute bottom-2.5 right-2.5 px-2.5 py-1 rounded-lg text-xs bg-black/80 text-zinc-200 backdrop-blur-md border border-white/10 flex items-center gap-1.5 shadow-lg z-20">
                    <span className="w-2 h-2 rounded-full bg-[#FC4C02]" />
                    <span>🗺️ GPS 航迹路线</span>
                  </div>
                </div>
              ) : (
                <div className="relative h-56 w-full bg-gradient-to-b from-[#16161b] to-[#0d0d10] overflow-hidden flex items-center justify-center">
                  <svg
                    viewBox="0 0 600 220"
                    className="w-full h-full p-2"
                    preserveAspectRatio="xMidYMid meet"
                  >
                    <defs>
                      <filter id="routeGlow" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#FC4C02" floodOpacity="0.6" />
                      </filter>
                      <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                        <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                      </pattern>
                    </defs>
                    <rect width="600" height="220" fill="url(#grid)" />
                    <path
                      d={pathD}
                      fill="none"
                      stroke="#FC4C02"
                      strokeWidth="3.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      filter="url(#routeGlow)"
                    />
                    {startPt && (
                      <g transform={`translate(${startPt.x}, ${startPt.y})`}>
                        <circle r="7" fill="#10B981" stroke="#ffffff" strokeWidth="2" />
                        <circle r="2.5" fill="#ffffff" />
                        <text x="12" y="4" fill="#10B981" fontSize="11" fontWeight="bold">起点</text>
                      </g>
                    )}
                    {endPt && (
                      <g transform={`translate(${endPt.x}, ${endPt.y})`}>
                        <circle r="7" fill="#FC4C02" stroke="#ffffff" strokeWidth="2" />
                        <circle r="2.5" fill="#ffffff" />
                        <text x="12" y="4" fill="#FC4C02" fontSize="11" fontWeight="bold">终点</text>
                      </g>
                    )}
                  </svg>

                  <div className="absolute bottom-2.5 right-2.5 px-2.5 py-1 rounded-lg text-[11px] bg-black/75 text-zinc-300 backdrop-blur-md border border-white/10 flex items-center gap-1.5 shadow-lg">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span>GCJ-02 纠偏 · 点击查看分段复盘</span>
                  </div>

                  <div className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-md text-[10px] bg-white/5 border border-white/10 text-zinc-400 flex items-center gap-1">
                    <Compass className="w-3 h-3 text-zinc-400" />
                    <span>正北朝上</span>
                  </div>
                </div>
              )
            ) : (
              <div className="p-4 bg-gradient-to-b from-[#16161b] to-[#0d0d10] h-56 flex flex-col justify-between">
                <div className="flex items-center justify-around text-xs border-b border-white/5 pb-2">
                  <div className="text-center">
                    <div className="text-[10px] text-zinc-400">最低海拔</div>
                    <div className="text-sm font-bold text-blue-400">{minElev} m</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-zinc-400">最高海拔</div>
                    <div className="text-sm font-bold text-[#FC4C02]">{maxElev} m</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[10px] text-zinc-400">累计爬升</div>
                    <div className="text-sm font-bold text-emerald-400">+{Math.round(elevationGain || 0)} m</div>
                  </div>
                </div>

                <div className="relative w-full h-32">
                  <svg viewBox="0 0 600 160" className="w-full h-full" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="elevAreaGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#FC4C02" stopOpacity="0.5" />
                        <stop offset="100%" stopColor="#FC4C02" stopOpacity="0.05" />
                      </linearGradient>
                    </defs>
                    <path d={elevPathArea} fill="url(#elevAreaGrad)" />
                    <path d={elevPathLine} fill="none" stroke="#FC4C02" strokeWidth="2.5" strokeLinecap="round" />
                  </svg>
                </div>

                <div className="flex justify-between text-[10px] text-zinc-500 px-2 pt-1 border-t border-white/5">
                  <span>0 km</span>
                  <span>{(Number(distanceKm) / 2).toFixed(1)} km</span>
                  <span>{distanceKm} km</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* When eagerly expanded on personal dashboard, also render Segment Diagnosis directly below map */}
        {eagerFetch && hasMapVisual && activeTab !== "segments" && (segmentAnalysis || isSegmentHidden) && (
          <div className="border-t border-white/10 bg-[#151519]">
            {renderSegmentDiagnosisBlock(false)}
          </div>
        )}
      </div>

      {/* Full-Screen Enlarged Modal */}
      {isModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setIsModalOpen(false)}
        >
          <div
            className="bg-[#18181c] border border-white/15 rounded-3xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
              <div className="flex items-center gap-2">
                <span className="text-lg">{segmentAnalysis?.mode === "race" ? "🏆" : "🗺️"}</span>
                <h3 className="font-bold text-white text-base">
                  {activityName || "跑步轨迹与智能分段复盘"}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center text-zinc-300 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Quick Metrics */}
            <div className="grid grid-cols-4 gap-2 px-6 py-3 bg-white/[0.02] border-b border-white/5 text-center text-xs">
              <div>
                <div className="text-zinc-400 text-[10px]">跑步距离</div>
                <div className="text-base font-black text-[#FC4C02]">{distanceKm} km</div>
              </div>
              <div>
                <div className="text-zinc-400 text-[10px]">平均配速</div>
                <div className="text-base font-bold text-white">{avgPace || "—"}</div>
              </div>
              <div>
                <div className="text-zinc-400 text-[10px]">累计爬升</div>
                <div className="text-base font-bold text-emerald-400">+{Math.round(elevationGain || 0)} m</div>
              </div>
              <div>
                <div className="text-zinc-400 text-[10px]">最高海拔</div>
                <div className="text-base font-bold text-amber-400">{maxElev || "—"} m</div>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6">
              {/* Route Map */}
              {hasMapVisual && (
                <div className="rounded-2xl overflow-hidden border border-white/10 bg-[#0d0d10] p-4">
                  <div className="text-xs font-semibold text-zinc-400 mb-2 flex items-center justify-between">
                    <span>GPS 航迹路线图</span>
                    <span className="text-[10px] text-zinc-500">纠偏坐标系 (GCJ-02)</span>
                  </div>
                  {mapImageUrl && points.length < 2 ? (
                    <div className="flex items-center justify-center bg-[#121215] rounded-xl overflow-hidden p-3">
                      <img
                        src={mapImageUrl}
                        alt="地图详情"
                        className="max-h-96 w-auto object-contain rounded-lg"
                        style={{
                          filter: "hue-rotate(-52deg) saturate(1.25) contrast(1.08)",
                        }}
                      />
                    </div>
                  ) : (
                    <div className="h-72 w-full flex items-center justify-center">
                      <svg viewBox="0 0 600 220" className="w-full h-full" preserveAspectRatio="xMidYMid meet">
                        <defs>
                          <filter id="modalGlow" x="-20%" y="-20%" width="140%" height="140%">
                            <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#FC4C02" floodOpacity="0.7" />
                          </filter>
                          <pattern id="modalGrid" width="30" height="30" patternUnits="userSpaceOnUse">
                            <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
                          </pattern>
                        </defs>
                        <rect width="600" height="220" fill="url(#modalGrid)" />
                        <path
                          d={pathD}
                          fill="none"
                          stroke="#FC4C02"
                          strokeWidth="4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          filter="url(#modalGlow)"
                        />
                        {startPt && (
                          <g transform={`translate(${startPt.x}, ${startPt.y})`}>
                            <circle r="8" fill="#10B981" stroke="#ffffff" strokeWidth="2.5" />
                            <circle r="3" fill="#ffffff" />
                            <text x="14" y="4" fill="#10B981" fontSize="12" fontWeight="bold">起点</text>
                          </g>
                        )}
                        {endPt && (
                          <g transform={`translate(${endPt.x}, ${endPt.y})`}>
                            <circle r="8" fill="#FC4C02" stroke="#ffffff" strokeWidth="2.5" />
                            <circle r="3" fill="#ffffff" />
                            <text x="14" y="4" fill="#FC4C02" fontSize="12" fontWeight="bold">终点</text>
                          </g>
                        )}
                      </svg>
                    </div>
                  )}
                </div>
              )}

              {/* Segment & Preset-Race Diagnosis Section */}
              <div className="rounded-2xl overflow-hidden border border-white/10 bg-[#121216] p-5">
                {renderSegmentDiagnosisBlock(false)}
              </div>

              {/* Public Club Captain Cheer */}
              {(fetchedCaptainCheer ?? captainCheer) && (
                <div className="rounded-2xl border border-amber-500/25 bg-gradient-to-r from-amber-950/30 via-[#221c15] to-orange-950/25 p-4 space-y-1.5">
                  <div className="flex items-center justify-between gap-2 text-xs font-bold text-amber-300">
                    <span>
                      📣 {(fetchedCaptainMeta ?? captainCheerMeta)?.captain_title || "团长加油"}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30">
                      全员可见
                    </span>
                  </div>
                  <p className="text-xs text-amber-100/90 leading-relaxed">
                    {fetchedCaptainCheer ?? captainCheer}
                  </p>
                </div>
              )}

              {/* Elevation Section */}
              {elevationProfile && elevationProfile.length > 1 && (
                <div className="rounded-2xl overflow-hidden border border-white/10 bg-[#0d0d10] p-4">
                  <div className="text-xs font-semibold text-zinc-400 mb-3 flex items-center justify-between">
                    <span>全程海拔高程剖面</span>
                    <span className="text-emerald-400 text-xs">最低 {minElev}m · 最高 {maxElev}m</span>
                  </div>
                  <div className="h-44 w-full">
                    <svg viewBox="0 0 600 160" className="w-full h-full" preserveAspectRatio="none">
                      <path d={elevPathArea} fill="url(#elevAreaGrad)" />
                      <path d={elevPathLine} fill="none" stroke="#FC4C02" strokeWidth="3" strokeLinecap="round" />
                    </svg>
                  </div>
                  <div className="flex justify-between text-[11px] text-zinc-500 pt-2 border-t border-white/5">
                    <span>0.00 km</span>
                    <span>{(Number(distanceKm) / 2).toFixed(2)} km</span>
                    <span>{distanceKm} km</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
