"use client";

import { useEffect, useState } from "react";
import axios from "@/lib/apiClient";

interface MonthData {
  month: string;
  month_name: string;
  target_km: number;
  actual_km: number;
  run_count: number;
  completion_pct: number;
  is_current: boolean;
  achieved: boolean;
}

interface HistoryData {
  year: number;
  monthly_target: number;
  annual_target: number;
  months: MonthData[];
  ytd_km: number;
  ytd_runs: number;
}

interface AnnualData {
  year: number;
  annual_target_km: number;
  total_km: number;
  total_runs: number;
  completion_pct: number;
  avg_monthly_km: number;
  projected_km: number;
  best_month: string | null;
  best_month_km: number;
  avg_pace: string;
}

function pctColor(pct: number): string {
  if (pct >= 100) return "#10b981";   // emerald
  if (pct >= 75)  return "#f59e0b";   // amber
  if (pct >= 50)  return "#FC4C02";   // strava orange
  return "#ef4444";                   // red
}

const MONTHS_SHORT = ["1月","2月","3月","4月","5月","6月",
                      "7月","8月","9月","10月","11月","12月"];

export default function GoalHistoryPanel({ uid }: { uid: string }) {
  const backendUrl  = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const [history,  setHistory]  = useState<HistoryData | null>(null);
  const [annual,   setAnnual]   = useState<AnnualData  | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!uid) return;
    Promise.all([
      axios.get(`${backendUrl}/api/sync/history/${uid}`),
      axios.get(`${backendUrl}/api/sync/annual/${uid}`),
    ]).then(([h, a]) => {
      setHistory(h.data);
      setAnnual(a.data);
    }).catch(console.error)
      .finally(() => setLoading(false));
  }, [uid, backendUrl]);

  if (loading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-3xl p-6 animate-pulse h-48" />
    );
  }
  if (!history || !annual) return null;

  // Circular ring progress
  const annualPct   = Math.min(annual.completion_pct, 100);
  const radius      = 52;
  const circ        = 2 * Math.PI * radius;
  const strokeDash  = (annualPct / 100) * circ;

  return (
    <div className="space-y-5">

      {/* ── Annual Summary Card ─────────────────────────────────────────── */}
      <div className="bg-white/5 border border-white/10 rounded-3xl p-6 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-40 h-40 bg-[#FC4C02]/10 blur-3xl pointer-events-none" />

        <div className="flex items-center justify-between mb-5 relative z-10">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <svg className="w-5 h-5 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              {annual.year} 年度统计
            </h2>
            <p className="text-zinc-500 text-xs mt-0.5">目标 {annual.annual_target_km} km · 月均目标 {history.monthly_target} km</p>
          </div>
          {/* Completion badge */}
          <div className="text-right">
            <p className="text-2xl font-black" style={{ color: pctColor(annual.completion_pct) }}>
              {annual.completion_pct.toFixed(1)}%
            </p>
            <p className="text-zinc-500 text-xs">完成度</p>
          </div>
        </div>

        {/* Main stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 relative z-10">
          {/* Ring + km */}
          <div className="col-span-2 sm:col-span-1 flex items-center gap-4">
            <div className="relative flex-shrink-0">
              <svg width="124" height="124" className="-rotate-90">
                <circle cx="62" cy="62" r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
                <circle
                  cx="62" cy="62" r={radius} fill="none"
                  stroke={pctColor(annual.completion_pct)}
                  strokeWidth="10" strokeLinecap="round"
                  strokeDasharray={`${strokeDash} ${circ}`}
                  style={{ transition: "stroke-dasharray 1s ease" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <p className="text-xl font-black text-white leading-none">{annual.total_km}</p>
                <p className="text-[10px] text-zinc-500">km</p>
              </div>
            </div>
          </div>

          {[
            { label: "总跑次",    value: `${annual.total_runs} 次`,      icon: "🏃" },
            { label: "月均跑量",  value: `${annual.avg_monthly_km} km`, icon: "📅" },
            { label: "年终预测",  value: `${annual.projected_km} km`,   icon: "🎯" },
          ].map(({ label, value, icon }) => (
            <div key={label} className="bg-white/5 border border-white/8 rounded-2xl p-4 flex flex-col justify-center">
              <p className="text-lg mb-0.5">{icon}</p>
              <p className="text-base font-black text-white leading-tight">{value}</p>
              <p className="text-[10px] text-zinc-500 mt-0.5">{label}</p>
            </div>
          ))}
        </div>

        {/* Annual progress bar */}
        <div className="mt-4 relative z-10">
          <div className="flex justify-between text-[10px] text-zinc-500 mb-1.5">
            <span>0 km</span>
            <span className="text-white font-semibold">{annual.total_km} / {annual.annual_target_km} km</span>
            <span>{annual.annual_target_km} km</span>
          </div>
          <div className="h-2 bg-white/8 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{
                width: `${Math.min(annualPct, 100)}%`,
                background: `linear-gradient(90deg, ${pctColor(annual.completion_pct)}, ${pctColor(annual.completion_pct)}cc)`,
              }}
            />
          </div>
          {annual.best_month && (
            <p className="text-[10px] text-zinc-500 mt-1.5">
              🏆 最佳月份：{MONTHS_SHORT[parseInt(annual.best_month.split("-")[1], 10) - 1]}（{annual.best_month_km} km）
              &nbsp;·&nbsp; 平均配速 {annual.avg_pace}
            </p>
          )}
        </div>
      </div>

      {/* ── Monthly History Grid ────────────────────────────────────────── */}
      <div className="bg-white/5 border border-white/10 rounded-3xl p-6 relative overflow-hidden">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <svg className="w-5 h-5 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            月度目标达成
          </h2>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-zinc-400 hover:text-white transition-colors flex items-center gap-1"
          >
            {expanded ? "收起" : "展开详情"}
            <svg className={`w-3 h-3 transition-transform ${expanded ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>

        {/* Compact month dots row (always visible) */}
        <div className="flex gap-2 flex-wrap">
          {history.months.map((m, i) => {
            const col = pctColor(m.completion_pct);
            return (
              <div key={m.month} className="flex flex-col items-center gap-1.5">
                {/* Mini bar */}
                <div className="w-10 h-16 bg-white/8 rounded-xl overflow-hidden relative flex flex-col justify-end">
                  <div
                    className="w-full rounded-xl transition-all duration-700"
                    style={{
                      height: `${Math.min(m.completion_pct, 100)}%`,
                      background: m.is_current
                        ? `linear-gradient(180deg, ${col}aa, ${col})`
                        : col,
                    }}
                  />
                  {m.is_current && (
                    <div className="absolute top-1 left-0 right-0 flex justify-center">
                      <div className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                    </div>
                  )}
                </div>
                <span className="text-[10px] text-zinc-500">{MONTHS_SHORT[i]}</span>
              </div>
            );
          })}
        </div>

        {/* Expanded detail rows */}
        {expanded && (
          <div className="mt-5 space-y-2">
            {history.months.map((m) => (
              <div
                key={m.month}
                className={`flex items-center gap-3 p-3 rounded-2xl transition-colors ${
                  m.is_current
                    ? "bg-[#FC4C02]/10 border border-[#FC4C02]/25"
                    : m.achieved
                    ? "bg-emerald-500/8 border border-emerald-500/15"
                    : "bg-white/3 border border-white/6"
                }`}
              >
                {/* Month label */}
                <div className="w-12 flex-shrink-0">
                  <p className="text-xs font-bold text-white">{m.month_name}</p>
                  {m.is_current && (
                    <span className="text-[9px] bg-[#FC4C02]/25 text-[#FC4C02] px-1.5 py-0.5 rounded-full font-semibold">本月</span>
                  )}
                </div>

                {/* Progress bar */}
                <div className="flex-1">
                  <div className="flex justify-between text-[10px] text-zinc-500 mb-1">
                    <span>{m.actual_km} km</span>
                    <span>目标 {m.target_km} km</span>
                  </div>
                  <div className="h-1.5 bg-white/8 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(m.completion_pct, 100)}%`,
                        background: pctColor(m.completion_pct),
                      }}
                    />
                  </div>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-3 text-right flex-shrink-0">
                  <div>
                    <p className="text-xs font-bold" style={{ color: pctColor(m.completion_pct) }}>
                      {m.completion_pct}%
                    </p>
                    <p className="text-[9px] text-zinc-600">{m.run_count} 跑</p>
                  </div>
                  {m.achieved ? (
                    <span className="text-base">✅</span>
                  ) : m.is_current ? (
                    <span className="text-base">🏃</span>
                  ) : (
                    <span className="text-base grayscale opacity-40">❌</span>
                  )}
                </div>
              </div>
            ))}

            {/* YTD footer */}
            <div className="flex items-center justify-between pt-3 border-t border-white/8 text-sm">
              <span className="text-zinc-500">年初至今</span>
              <span className="font-black text-white">{history.ytd_km} km &nbsp;·&nbsp; {history.ytd_runs} 次</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
