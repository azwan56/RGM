"use client";

import { useEffect, useState, useMemo } from "react";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

interface StreamPoint {
  distance: number;
  pace: number | null;
  heartRate: number | null;
  cadence: number | null;
  elevation: number | null;
}

interface Props {
  activityId: number;
  uid: string;
  avgPace?: string;
  avgHeartRate?: number;
  avgCadence?: number;
  initialPoints?: StreamPoint[];
}

type MetricKey = "pace" | "heartRate" | "cadence";

const METRICS: { key: MetricKey; label: string; color: string; unit: string }[] = [
  { key: "pace",      label: "配速",    color: "#3b82f6", unit: "/km" },
  { key: "heartRate", label: "心率",    color: "#ef4444", unit: "bpm" },
  { key: "cadence",   label: "步频",    color: "#ec4899", unit: "spm" },
];

/** Format pace decimal (min/km) → "M:SS" */
function paceLabel(val: number) {
  const m = Math.floor(val);
  const s = Math.round((val - m) * 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function normalize(val: number, min: number, max: number, invert = false) {
  if (max === min) return 50;
  const pct = ((val - min) / (max - min)) * 80 + 10;
  return invert ? 100 - pct : pct;
}

/** Custom tooltip shown when hovering over the chart */
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const raw = payload[0]?.payload as StreamPoint & { __norm: any };

  return (
    <div className="bg-zinc-900 border border-white/10 rounded-xl px-3 py-2 text-xs shadow-xl min-w-[140px]">
      <p className="text-zinc-400 mb-1.5 font-medium">{Number(label).toFixed(2)} km</p>
      {raw.elevation != null && (
        <div className="flex justify-between gap-4">
          <span className="text-zinc-500">高程</span>
          <span className="text-white font-semibold">{raw.elevation} m</span>
        </div>
      )}
      {raw.pace != null && (
        <div className="flex justify-between gap-4">
          <span className="text-blue-400">配速</span>
          <span className="text-white font-semibold">{paceLabel(raw.pace)} /km</span>
        </div>
      )}
      {raw.heartRate != null && (
        <div className="flex justify-between gap-4">
          <span className="text-red-400">心率</span>
          <span className="text-white font-semibold">{raw.heartRate} bpm</span>
        </div>
      )}
      {raw.cadence != null && (
        <div className="flex justify-between gap-4">
          <span className="text-pink-400">步频</span>
          <span className="text-white font-semibold">{raw.cadence} spm</span>
        </div>
      )}
    </div>
  );
}

export default function ActivityChart({ activityId, uid, avgPace, avgHeartRate, avgCadence, initialPoints }: Props) {
  const hasInitialPoints = (initialPoints?.length ?? 0) > 0;
  const [points, setPoints] = useState<StreamPoint[]>(hasInitialPoints ? initialPoints! : []);
  const [loading, setLoading] = useState(!hasInitialPoints);
  const [error, setError] = useState(false);
  const [active, setActive] = useState<Set<MetricKey>>(new Set(["pace", "heartRate", "cadence"]));

  useEffect(() => {
    if (hasInitialPoints) return; // already seeded with real data
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    import("@/lib/apiClient").then(({ default: api }) => {
      api.get(`${backendUrl}/api/sync/activity/${activityId}/streams?uid=${uid}`)
        .then((r) => { setPoints(r.data.points || []); setLoading(false); })
        .catch(() => { setError(true); setLoading(false); });
    });
  }, [activityId, uid, hasInitialPoints]);

  // Compute min/max for normalization
  const ranges = useMemo(() => {
    const get = (key: keyof StreamPoint) =>
      points.map((p) => p[key] as number).filter((v) => v != null && !isNaN(v));
    return {
      elevation: { min: Math.min(...get("elevation")), max: Math.max(...get("elevation")) },
      pace:      { min: Math.min(...get("pace")),      max: Math.max(...get("pace")) },
      heartRate: { min: Math.min(...get("heartRate")), max: Math.max(...get("heartRate")) },
      cadence:   { min: Math.min(...get("cadence")),   max: Math.max(...get("cadence")) },
    };
  }, [points]);

  // Build normalized data
  const chartData = useMemo(() =>
    points.map((p) => ({
      ...p,
      elevNorm: p.elevation != null ? normalize(p.elevation, ranges.elevation.min, ranges.elevation.max) : null,
      paceNorm: p.pace != null      ? normalize(p.pace,      ranges.pace.min,      ranges.pace.max, true) : null, // inverted: faster=up
      hrNorm:   p.heartRate != null ? normalize(p.heartRate, ranges.heartRate.min, ranges.heartRate.max) : null,
      cadNorm:  p.cadence != null   ? normalize(p.cadence,   ranges.cadence.min,   ranges.cadence.max) : null,
    })),
    [points, ranges]
  );

  const toggle = (key: MetricKey) => {
    setActive((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-2xl p-6 animate-pulse h-64 flex items-center justify-center">
        <p className="text-zinc-500 text-sm">加载图表数据...</p>
      </div>
    );
  }

  if (error || points.length === 0) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-2xl p-6 flex flex-col items-center justify-center h-40 gap-2">
        <svg className="w-5 h-5 text-zinc-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
        <p className="text-zinc-500 text-sm">{error ? "无法获取流数据，请稍后重试" : "此活动无详细流数据（Strava 未记录）"}</p>
      </div>
    );
  }

  // Average pace as normalized Y for reference line
  const avgPaceVal = avgPace ? (() => {
    const [m, s] = avgPace.split(":").map(Number);
    return m + s / 60;
  })() : null;
  const avgPaceNorm = avgPaceVal ? normalize(avgPaceVal, ranges.pace.min, ranges.pace.max, true) : null;

  return (
    <div className="bg-white/5 border border-white/10 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-white font-bold text-lg">配速 · 心率 · 步频</h3>
        <div className="flex gap-2 flex-wrap">
          {METRICS.map(({ key, label, color }) => (
            <button
              key={key}
              onClick={() => toggle(key)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border transition-all ${
                active.has(key)
                  ? "border-transparent text-white"
                  : "border-white/10 text-zinc-500 bg-transparent"
              }`}
              style={active.has(key) ? { backgroundColor: color + "33", borderColor: color + "88" } : {}}
            >
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: active.has(key) ? color : "#555" }} />
              {label}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff0f" vertical={false} />
          <XAxis
            dataKey="distance"
            tickFormatter={(v) => `${Number(v).toFixed(1)}`}
            tick={{ fill: "#71717a", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            unit=" km"
          />
          <YAxis domain={[0, 100]} hide />

          {/* Elevation — always shown as gray area */}
          <Area
            dataKey="elevNorm"
            fill="#ffffff08"
            stroke="#ffffff1a"
            strokeWidth={1}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />

          {/* Avg pace reference line */}
          {active.has("pace") && avgPaceNorm != null && (
            <ReferenceLine
              y={avgPaceNorm}
              stroke="#3b82f680"
              strokeDasharray="4 3"
              label={{ value: `均速 ${avgPace}`, fill: "#3b82f6", fontSize: 10, position: "insideTopRight" }}
            />
          )}
          {active.has("heartRate") && avgHeartRate && (
            <ReferenceLine
              y={normalize(avgHeartRate, ranges.heartRate.min, ranges.heartRate.max)}
              stroke="#ef444480"
              strokeDasharray="4 3"
              label={{ value: `均心率 ${avgHeartRate}`, fill: "#ef4444", fontSize: 10, position: "insideTopRight" }}
            />
          )}
          {active.has("cadence") && avgCadence && (
            <ReferenceLine
              y={normalize(avgCadence, ranges.cadence.min, ranges.cadence.max)}
              stroke="#ec4899"
              strokeDasharray="4 3"
              label={{ value: `均步频 ${avgCadence}`, fill: "#ec4899", fontSize: 10, position: "insideTopRight" }}
            />
          )}

          {active.has("pace") && (
            <Line dataKey="paceNorm" stroke="#3b82f6" strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls />
          )}
          {active.has("heartRate") && (
            <Line dataKey="hrNorm" stroke="#ef4444" strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls />
          )}
          {active.has("cadence") && (
            <Line dataKey="cadNorm" stroke="#ec4899" strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls />
          )}

          <Tooltip content={<CustomTooltip />} cursor={{ stroke: "#ffffff20", strokeWidth: 1 }} />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend / averages row */}
      <div className="flex gap-6 flex-wrap text-xs text-zinc-400 border-t border-white/5 pt-4">
        {active.has("pace") && avgPace && (
          <div className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-blue-500 rounded-full inline-block" />
            <span>均速 <strong className="text-white">{avgPace} /km</strong></span>
          </div>
        )}
        {active.has("heartRate") && avgHeartRate ? (
          <div className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-red-500 rounded-full inline-block" />
            <span>均心率 <strong className="text-white">{avgHeartRate} bpm</strong></span>
          </div>
        ) : null}
        {active.has("cadence") && avgCadence ? (
          <div className="flex items-center gap-2">
            <span className="w-3 h-0.5 bg-pink-500 rounded-full inline-block" />
            <span>均步频 <strong className="text-white">{avgCadence} spm</strong></span>
          </div>
        ) : null}
        <div className="flex items-center gap-2">
          <span className="w-3 h-2 bg-white/5 border border-white/10 rounded-sm inline-block" />
          <span>高程（背景）</span>
        </div>
      </div>
    </div>
  );
}
