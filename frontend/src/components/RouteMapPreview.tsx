"use client";

import React, { useState, useMemo } from "react";
import { Maximize2, X, Compass, Mountain, MapPin } from "lucide-react";

interface RouteMapPreviewProps {
  trackData?: any;
  mapImageUrl?: string;
  activityName?: string;
  distanceMeters?: number;
  elevationGain?: number;
  avgPace?: string;
}

export default function RouteMapPreview({
  trackData: rawTrack,
  mapImageUrl,
  activityName,
  distanceMeters,
  elevationGain,
  avgPace,
}: RouteMapPreviewProps) {
  const [activeTab, setActiveTab] = useState<"map" | "elevation">("map");
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Parse track data if passed as JSON string
  const track = useMemo(() => {
    if (!rawTrack) return null;
    if (typeof rawTrack === "string") {
      try {
        return JSON.parse(rawTrack);
      } catch {
        return null;
      }
    }
    return rawTrack;
  }, [rawTrack]);

  const points = useMemo(() => {
    return track?.points || [];
  }, [track]);

  const elevationProfile = useMemo(() => {
    return track?.elevation_profile || [];
  }, [track]);

  const distanceKm = useMemo(() => {
    if (distanceMeters) return (distanceMeters / 1000).toFixed(2);
    return "0.00";
  }, [distanceMeters]);

  // Project GPS points to 2D SVG canvas (Mercator aspect-ratio preserved)
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

  // Elevation calculation
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

  // If no GPS track and no map image, render nothing
  if (!mapImageUrl && (!points || points.length < 2)) {
    return null;
  }

  return (
    <>
      <div className="rounded-2xl overflow-hidden border border-white/10 bg-[#121215] shadow-xl transition hover:border-white/20">
        {/* Header Switcher if both map and elevation are available */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-white/[0.03] border-b border-white/5 text-xs">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab("map")}
              className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
                activeTab === "map"
                  ? "bg-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/20"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <span>🗺️</span>
              <span>GPS 路线轨迹</span>
            </button>
            {elevationProfile && elevationProfile.length > 1 && (
              <button
                onClick={() => setActiveTab("elevation")}
                className={`px-2.5 py-1 rounded-lg font-medium transition flex items-center gap-1.5 ${
                  activeTab === "elevation"
                    ? "bg-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/20"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Mountain className="w-3.5 h-3.5" />
                <span>海拔剖面 ({maxElev}m)</span>
              </button>
            )}
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            className="text-zinc-400 hover:text-white transition p-1 rounded-md hover:bg-white/10 flex items-center gap-1 text-[11px]"
            title="放大查看全图"
          >
            <Maximize2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">全屏详情</span>
          </button>
        </div>

        {/* Content Body */}
        <div
          className="relative cursor-pointer group"
          onClick={() => setIsModalOpen(true)}
        >
          {activeTab === "map" ? (
            mapImageUrl ? (
              <div className="relative h-52 overflow-hidden bg-black/40">
                <img
                  src={mapImageUrl}
                  alt="官方跑步地图切片"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
                <div className="absolute bottom-2.5 right-2.5 px-2.5 py-1 rounded-lg text-xs bg-black/80 text-zinc-200 backdrop-blur-md border border-white/10 flex items-center gap-1.5 shadow-lg">
                  <span>🗺️ COROS 官方地图实景</span>
                </div>
              </div>
            ) : (
              <div className="relative h-56 w-full bg-gradient-to-b from-[#16161b] to-[#0d0d10] overflow-hidden flex items-center justify-center">
                {/* SVG Vector Route */}
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

                  {/* Grid Background */}
                  <rect width="600" height="220" fill="url(#grid)" />

                  {/* Polyline Path */}
                  <path
                    d={pathD}
                    fill="none"
                    stroke="#FC4C02"
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    filter="url(#routeGlow)"
                  />

                  {/* Start Point Marker */}
                  {startPt && (
                    <g transform={`translate(${startPt.x}, ${startPt.y})`}>
                      <circle r="7" fill="#10B981" stroke="#ffffff" strokeWidth="2" />
                      <circle r="2.5" fill="#ffffff" />
                      <text x="12" y="4" fill="#10B981" fontSize="11" fontWeight="bold">起点</text>
                    </g>
                  )}

                  {/* End Point Marker */}
                  {endPt && (
                    <g transform={`translate(${endPt.x}, ${endPt.y})`}>
                      <circle r="7" fill="#FC4C02" stroke="#ffffff" strokeWidth="2" />
                      <circle r="2.5" fill="#ffffff" />
                      <text x="12" y="4" fill="#FC4C02" fontSize="11" fontWeight="bold">终点</text>
                    </g>
                  )}
                </svg>

                {/* Floating Meta Badges */}
                <div className="absolute bottom-2.5 right-2.5 px-2.5 py-1 rounded-lg text-[11px] bg-black/75 text-zinc-300 backdrop-blur-md border border-white/10 flex items-center gap-1.5 shadow-lg">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>GCJ-02 火星坐标已纠偏 · {points.length} 轨迹采样点</span>
                </div>

                <div className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-md text-[10px] bg-white/5 border border-white/10 text-zinc-400 flex items-center gap-1">
                  <Compass className="w-3 h-3 text-zinc-400" />
                  <span>正北朝上</span>
                </div>
              </div>
            )
          ) : (
            /* Elevation Tab */
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

              {/* Elevation Area SVG */}
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
                <span className="text-lg">🗺️</span>
                <h3 className="font-bold text-white text-base">
                  {activityName || "跑步轨迹地图与高程剖面"}
                </h3>
              </div>
              <button
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
              <div className="rounded-2xl overflow-hidden border border-white/10 bg-[#0d0d10] p-4">
                <div className="text-xs font-semibold text-zinc-400 mb-2 flex items-center justify-between">
                  <span>GPS 航迹路线图</span>
                  <span className="text-[10px] text-zinc-500">纠偏坐标系 (GCJ-02)</span>
                </div>
                {mapImageUrl ? (
                  <img src={mapImageUrl} alt="地图详情" className="w-full rounded-xl object-contain max-h-96" />
                ) : (
                  <div className="h-80 w-full flex items-center justify-center">
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
