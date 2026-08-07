"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import axios from "@/lib/apiClient";
import StatsCard from "./StatsCard";

interface Stats {
  total_distance_km: number;
  total_elevation_gain?: number;
  avg_pace: string;
  avg_heart_rate: number;
  goal_completion_percentage: number;
  run_count: number;
  period: "weekly" | "monthly";
  period_start: string | null;
  last_sync: string | null;
}

const EMPTY_STATS: Stats = {
  total_distance_km: 0,
  avg_pace: "—",
  avg_heart_rate: 0,
  goal_completion_percentage: 0,
  run_count: 0,
  period: "monthly",
  period_start: null,
  last_sync: null,
};

function formatSyncTime(iso: string | null) {
  if (!iso) return "Never synced";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatPeriodLabel(period: "weekly" | "monthly", periodStart: string | null): string {
  if (!periodStart) return period === "weekly" ? "This Week" : "This Month";
  const start = new Date(periodStart);
  const now = new Date();
  if (period === "weekly") {
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return `${start.getMonth() + 1}/${start.getDate()} – ${end.getMonth() + 1}/${end.getDate()}`;
  } else {
    return `${now.getFullYear()}年${now.getMonth() + 1}月`;
  }
}

export default function RunningStatsPanel({ uid, initialStats }: { uid: string; initialStats?: any }) {
  const [stats, setStats] = useState<Stats>(initialStats ? { ...EMPTY_STATS, ...initialStats } : EMPTY_STATS);
  const [syncing, setSyncing] = useState(false);
  const [fullSyncing, setFullSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);
  const backendUrl = "";

  // Fetch stats from backend API (not direct Firestore — faster in China)
  const fetchStats = useCallback(async () => {
    try {
      const res = await axios.get(`${backendUrl}/api/data/stats/${uid}`);
      if (res.data && res.data.total_distance_km !== undefined) {
        setStats({ ...EMPTY_STATS, ...res.data });
      }
    } catch (err) {
      console.error("Stats fetch error:", err);
    }
  }, [uid, backendUrl]);

  useEffect(() => {
    if (initialStats && Object.keys(initialStats).length > 0) {
      setStats({ ...EMPTY_STATS, ...initialStats });
    } else {
      fetchStats();
    }
  }, [fetchStats, initialStats]);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      await axios.post(`${backendUrl}/api/sync/trigger`, { uid });
      setSyncMsg({ text: "Sync successful! Data updated.", type: "success" });
      // Refresh stats after sync
      await fetchStats();
    } catch (err: any) {
      console.error("Sync trigger error:", err?.message || err);
      setSyncMsg({ text: "Sync failed. Please try again.", type: "error" });
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMsg(null), 4000);
    }
  }, [uid, backendUrl, fetchStats]);

  const handleFullSync = useCallback(async (sinceDate = "2025-01-01") => {
    setFullSyncing(true);
    setSyncMsg(null);

    try {
      // 1. Kick off background sync (returns immediately)
      await axios.post(`${backendUrl}/api/sync/full`, { uid, since_date: sinceDate }, { timeout: 15000 });
      setSyncMsg({ text: "历史同步已启动，正在后台拉取数据...", type: "success" });

      // 2. Poll /full-status every 3 seconds
      const poll = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${backendUrl}/api/sync/full-status?uid=${uid}`, { timeout: 8000 });
          const s = statusRes.data;
          if (s.state === "done") {
            clearInterval(poll);
            setFullSyncing(false);
            setSyncMsg({ text: `✓ 历史同步完成！共导入 ${s.saved} 次跑步 (${sinceDate} 至今)`, type: "success" });
            fetchStats(); // Refresh stats
            setTimeout(() => setSyncMsg(null), 8000);
          } else if (s.state === "error") {
            clearInterval(poll);
            setFullSyncing(false);
            setSyncMsg({ text: `同步出错：${s.error || "未知错误"}`, type: "error" });
            setTimeout(() => setSyncMsg(null), 6000);
          } else if (s.state === "running") {
            setSyncMsg({ text: `同步中… 已保存 ${s.saved} 条 (第 ${s.pages} 页)`, type: "success" });
          }
        } catch { /* noop */ }
      }, 3000);

    } catch (err: any) {
      console.error("Full sync error:", err?.message || err);
      setSyncMsg({ text: "历史同步启动失败，请检查网络连接。", type: "error" });
      setFullSyncing(false);
      setTimeout(() => setSyncMsg(null), 6000);
    }
  }, [uid, backendUrl, fetchStats]);

  // ── History dropdown: click-toggle (mobile-friendly) ──
  const [historyOpen, setHistoryOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!historyOpen) return;
    function handleClickOutside(e: MouseEvent | TouchEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setHistoryOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [historyOpen]);

  const pct = Math.min(stats.goal_completion_percentage, 100);

  return (
    <section className="space-y-5">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-bold text-white">
              {stats.period === "weekly" ? "本周跑量" : "本月跑量"}
            </h2>
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-white/10 text-zinc-400">
              {formatPeriodLabel(stats.period, stats.period_start)}
            </span>
            {stats.run_count > 0 && (
              <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-[#FC4C02]/15 text-[#FC4C02]">
                {stats.run_count} runs
              </span>
            )}
          </div>
          <p className="text-zinc-500 text-sm">
            {stats.last_sync ? `Last synced: ${formatSyncTime(stats.last_sync)}` : "No data yet — sync to get started"}
          </p>
        </div>
      </div>

      {/* Feedback message */}
      {syncMsg && (
        <div className={`px-4 py-2.5 rounded-xl text-sm font-medium ${syncMsg.type === "success" ? "bg-green-500/15 text-green-400 border border-green-500/20" : "bg-red-500/15 text-red-400 border border-red-500/20"}`}>
          {syncMsg.text}
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatsCard
          title="Total Distance"
          value={stats.total_distance_km > 0 ? stats.total_distance_km.toFixed(1) : 0}
          unit="km"
          color="orange"
          icon={
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          }
        />
        <StatsCard
          title="Total Elevation"
          value={stats.total_elevation_gain ? stats.total_elevation_gain.toFixed(0) : 0}
          unit="m"
          color="emerald"
          icon={
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          }
        />
        <StatsCard
          title="Avg Pace"
          value={stats.avg_pace !== "0:00" ? stats.avg_pace : 0}
          unit="/ km"
          color="blue"
          icon={
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
        />
        <StatsCard
          title="Avg Heart Rate"
          value={stats.avg_heart_rate || 0}
          unit="bpm"
          color="purple"
          subtext={stats.avg_heart_rate === 0 ? "Requires heart rate data" : undefined}
          icon={
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
          }
        />
        <StatsCard
          title="Goal Progress"
          value={pct > 0 ? pct : 0}
          unit="%"
          color="green"
          subtext={pct === 0 ? "Set a goal to track progress" : undefined}
          icon={
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
            </svg>
          }
        />
      </div>

      {/* Goal progress bar */}
      {pct > 0 && (
        <div className="bg-white/5 border border-white/10 rounded-2xl p-5">
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-medium text-zinc-300">Goal Completion</span>
            <span className="text-sm font-bold text-white">{pct}%</span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2.5 overflow-hidden">
            <div
              className="h-2.5 rounded-full bg-gradient-to-r from-[#FC4C02] to-orange-400 transition-all duration-700 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-zinc-500 text-xs mt-2">
            {pct >= 100 ? "🎉 Goal achieved! Great work!" : `${100 - pct}% to go — keep it up!`}
          </p>
        </div>
      )}
    </section>
  );
}
