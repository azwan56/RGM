"use client";

import { useEffect, useState } from "react";
import axios from "@/lib/apiClient";

interface VdotEntry {
  activity_id: number;
  name: string;
  date: string;
  distance_km: number;
  avg_pace: string;
  avg_heart_rate: number;
  vdot: number;
  vdot_r2: number;
}

function formatDate(iso: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export default function VdotTrend({ uid, currentActivityId }: { uid: string; currentActivityId?: number }) {
  const [entries, setEntries] = useState<VdotEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    axios.get(`${backendUrl}/api/sync/vdot-trend/${uid}?limit=10`)
      .then(r => {
        // Reverse to show oldest→newest (left→right)
        setEntries((r.data.entries || []).reverse());
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [uid]);

  if (loading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-2xl p-6 h-64 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-[#FC4C02] border-t-transparent rounded-full animate-spin" />
          <p className="text-zinc-500 text-xs">加载 VDOT 趋势...</p>
        </div>
      </div>
    );
  }

  if (entries.length < 2) {
    return null; // Not enough data for a trend
  }

  // Calculate stats
  const vdots = entries.map(e => e.vdot);
  const minV = Math.min(...vdots);
  const maxV = Math.max(...vdots);
  const range = maxV - minV || 2;
  const padMin = minV - range * 0.15;
  const padMax = maxV + range * 0.15;
  const padRange = padMax - padMin;
  const latest = entries[entries.length - 1];
  const prev = entries[entries.length - 2];
  const delta = latest.vdot - prev.vdot;
  const avgVdot = (vdots.reduce((a, b) => a + b, 0) / vdots.length).toFixed(1);

  // Trend direction
  const trendUp = delta > 0;
  const trendFlat = Math.abs(delta) < 0.5;

  return (
    <div className="bg-gradient-to-br from-white/5 to-black/20 border border-white/10 rounded-2xl p-6 space-y-5 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute -bottom-10 -left-10 w-40 h-40 bg-emerald-500/8 rounded-full blur-[80px] pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between relative z-10">
        <div>
          <h3 className="text-white font-bold text-lg flex items-center gap-2">
            📈 VDOT 趋势
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">
            最近 {entries.length} 次有效训练的跑力变化
          </p>
        </div>
        <div className="text-right">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-black text-[#FC4C02]">{latest.vdot}</span>
            <span className={`text-sm font-bold flex items-center gap-0.5 ${
              trendFlat ? "text-zinc-400" : trendUp ? "text-emerald-400" : "text-red-400"
            }`}>
              {trendFlat ? "→" : trendUp ? "↑" : "↓"}
              {!trendFlat && ` ${Math.abs(delta).toFixed(1)}`}
            </span>
          </div>
          <p className="text-[10px] text-zinc-500">均 {avgVdot}</p>
        </div>
      </div>

      {/* SVG Chart */}
      <div className="relative z-10" style={{ height: 160 }}>
        <svg width="100%" height="100%" viewBox={`0 0 ${entries.length * 80} 160`} preserveAspectRatio="none">
          {/* Grid lines */}
          {[0.25, 0.5, 0.75].map(pct => {
            const y = 160 - pct * 140 - 10;
            const val = (padMin + pct * padRange).toFixed(0);
            return (
              <g key={pct}>
                <line x1="0" y1={y} x2={entries.length * 80} y2={y} stroke="#ffffff08" strokeWidth={1} />
                <text x="4" y={y - 3} fill="#52525b" fontSize="9">{val}</text>
              </g>
            );
          })}

          {/* Line path */}
          <polyline
            points={entries.map((e, i) => {
              const x = i * 80 + 40;
              const y = 150 - ((e.vdot - padMin) / padRange) * 140;
              return `${x},${y}`;
            }).join(" ")}
            fill="none"
            stroke="url(#vdotGrad)"
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Gradient fill under the line */}
          <polygon
            points={[
              ...entries.map((e, i) => {
                const x = i * 80 + 40;
                const y = 150 - ((e.vdot - padMin) / padRange) * 140;
                return `${x},${y}`;
              }),
              `${(entries.length - 1) * 80 + 40},155`,
              `40,155`,
            ].join(" ")}
            fill="url(#vdotFill)"
          />

          {/* Data points */}
          {entries.map((e, i) => {
            const x = i * 80 + 40;
            const y = 150 - ((e.vdot - padMin) / padRange) * 140;
            const isCurrent = e.activity_id === currentActivityId;
            return (
              <g key={i}>
                <circle cx={x} cy={y} r={isCurrent ? 6 : 4} fill={isCurrent ? "#FC4C02" : "#10b981"} stroke={isCurrent ? "#FC4C02" : "#10b98180"} strokeWidth={isCurrent ? 2 : 1} />
                <text x={x} y={y - 10} textAnchor="middle" fill={isCurrent ? "#FC4C02" : "#d4d4d8"} fontSize="11" fontWeight="bold">
                  {e.vdot}
                </text>
                <text x={x} y={158} textAnchor="middle" fill="#52525b" fontSize="9">
                  {formatDate(e.date)}
                </text>
              </g>
            );
          })}

          {/* Gradients */}
          <defs>
            <linearGradient id="vdotGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#FC4C02" />
            </linearGradient>
            <linearGradient id="vdotFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b98115" />
              <stop offset="100%" stopColor="#10b98100" />
            </linearGradient>
          </defs>
        </svg>
      </div>

      {/* Comparison table — last 3 */}
      <div className="relative z-10 border-t border-white/5 pt-4">
        <p className="text-[10px] text-zinc-500 uppercase tracking-widest mb-3 font-bold">近期对比</p>
        <div className="grid gap-2">
          {entries.slice(-3).reverse().map((e, idx) => {
            const isCurrent = e.activity_id === currentActivityId;
            return (
              <div
                key={e.activity_id}
                className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs ${
                  isCurrent ? "bg-[#FC4C02]/10 border border-[#FC4C02]/20" : "bg-white/3 border border-white/5"
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`font-black text-lg ${isCurrent ? "text-[#FC4C02]" : "text-white"}`}>{e.vdot}</span>
                  <div className="min-w-0">
                    <p className="text-white font-medium truncate">{e.name}</p>
                    <p className="text-zinc-500">{e.date} · {e.distance_km}km · {e.avg_pace}/km</p>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  {e.avg_heart_rate > 0 && (
                    <p className="text-zinc-400">❤️ {e.avg_heart_rate}</p>
                  )}
                  <p className="text-zinc-600">R²={e.vdot_r2}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
