"use client";

import { useEffect, useState } from "react";
import axios from "@/lib/apiClient";

interface LeaderboardEntry {
  uid: string;
  email: string;
  display_name?: string;
  total_distance_km: number;
  avg_pace: string;
  avg_heart_rate: number;
  goal_completion_percentage: number;
  run_count: number;
  period: "weekly" | "monthly";
}

interface YearlyEntry {
  uid: string;
  display_name?: string;
  email: string;
  total_distance_km: number;
  run_count: number;
  avg_pace: string;
  year: number;
}

type Tab = "monthly" | "weekly" | "yearly";

export default function LeaderboardWidget({ currentUid, fixedHeight }: { currentUid: string; fixedHeight?: string }) {
  // Default: monthly ranking
  const [tab, setTab]               = useState<Tab>("monthly");
  const [entries, setEntries]       = useState<LeaderboardEntry[]>([]);
  const [yearly,  setYearly]        = useState<YearlyEntry[]>([]);
  const [loading, setLoading]       = useState(true);
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  // ── Monthly / Weekly — backend API (not direct Firestore) ─────────────────
  useEffect(() => {
    if (tab === "yearly") return;
    setLoading(true);
    axios.get(`${backendUrl}/api/data/leaderboard`, { params: { period: tab, limit_n: 20 } })
      .then((res) => {
        setEntries(res.data.entries || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [tab, backendUrl]);

  // ── Yearly — backend REST (aggregated from leaderboard_yearly collection) ─
  useEffect(() => {
    if (tab !== "yearly") return;
    setLoading(true);
    const year = new Date().getFullYear();
    axios.get(`${backendUrl}/api/sync/yearly-leaderboard`, { params: { year } })
      .then(r => {
        setYearly(r.data.entries || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [tab, backendUrl]);

  // ── Helpers ────────────────────────────────────────────────────────────────
  const rankBadge = (i: number) =>
    i === 0 ? "bg-yellow-500/20 text-yellow-400" :
    i === 1 ? "bg-zinc-300/20 text-zinc-300" :
    i === 2 ? "bg-amber-700/20 text-amber-600" :
              "bg-black/40 text-zinc-500";

  const nameOf = (e: any) =>
    e.display_name || e.email?.split("@")[0] || `Runner #${e.uid?.slice(0,6)}`;

  const tabs: { key: Tab; label: string }[] = [
    { key: "monthly", label: "月榜" },
    { key: "weekly",  label: "周榜" },
    { key: "yearly",  label: "年榜" },
  ];

  const currentYear = new Date().getFullYear();

  const containerStyle = fixedHeight ? { height: fixedHeight } : {};

  return (
    <div
      className="bg-white/5 border border-white/10 rounded-3xl relative overflow-hidden flex flex-col"
      style={containerStyle}
    >
      <div className="absolute top-0 right-0 w-32 h-32 bg-[#FC4C02]/10 blur-3xl pointer-events-none" />

      {/* Header & Tabs — fixed */}
      <div className="flex items-center justify-between px-6 pt-6 pb-4 flex-shrink-0 relative z-10">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <svg className="w-5 h-5 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
          </svg>
          排行榜
          {tab === "yearly" && (
            <span className="text-xs font-normal text-zinc-500">{currentYear}</span>
          )}
        </h2>

        <div className="flex bg-black/40 rounded-full p-1 border border-white/5">
          {tabs.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => { setTab(key); setLoading(true); }}
              className={`px-3 py-1 text-xs font-semibold rounded-full transition-colors ${
                tab === key ? "bg-[#FC4C02] text-white shadow-lg" : "text-zinc-400 hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* List — scrollable area */}
      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-3 relative z-10">
        {loading ? (
          [1, 2, 3].map(i => (
            <div key={i} className="h-14 bg-white/5 rounded-2xl animate-pulse" />
          ))
        ) : tab !== "yearly" ? (
          // Monthly / Weekly
          entries.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-zinc-500 text-sm">暂无{tab === "monthly" ? "本月" : "本周"}跑步数据</p>
            </div>
          ) : entries.map((entry, index) => {
            const isMe = entry.uid === currentUid;
            return (
              <div
                key={entry.uid}
                className={`flex items-center gap-4 p-3 rounded-2xl transition-colors ${
                  isMe
                    ? "bg-[#FC4C02]/10 border border-[#FC4C02]/30"
                    : "bg-white/5 border border-white/5 hover:bg-white/10"
                }`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${rankBadge(index)}`}>
                  {index + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate flex items-center gap-2">
                    {nameOf(entry)}
                    {isMe && <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold bg-[#FC4C02]/20 text-[#FC4C02]">我</span>}
                  </p>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-zinc-500">
                    <span>{entry.run_count} 次</span>
                    <span>配速 {entry.avg_pace}</span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-lg font-black text-white leading-none">
                    {entry.total_distance_km.toFixed(1)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-0.5">km</p>
                </div>
              </div>
            );
          })
        ) : (
          // Yearly
          yearly.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-zinc-500 text-sm">暂无 {currentYear} 年度数据</p>
              <p className="text-zinc-600 text-xs mt-1">同步一次数据后自动生成年榜</p>
            </div>
          ) : yearly.map((entry, index) => {
            const isMe = entry.uid === currentUid;
            return (
              <div
                key={entry.uid}
                className={`flex items-center gap-4 p-3 rounded-2xl transition-colors ${
                  isMe
                    ? "bg-[#FC4C02]/10 border border-[#FC4C02]/30"
                    : "bg-white/5 border border-white/5 hover:bg-white/10"
                }`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${rankBadge(index)}`}>
                  {index + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate flex items-center gap-2">
                    {nameOf(entry)}
                    {isMe && <span className="px-1.5 py-0.5 rounded text-[10px] uppercase font-bold bg-[#FC4C02]/20 text-[#FC4C02]">我</span>}
                  </p>
                  <div className="flex items-center gap-3 mt-0.5 text-xs text-zinc-500">
                    <span>{entry.run_count} 次</span>
                    <span>配速 {entry.avg_pace}</span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-lg font-black text-white leading-none">
                    {entry.total_distance_km.toFixed(1)}
                  </p>
                  <p className="text-xs text-zinc-500 mt-0.5">km/{currentYear}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
