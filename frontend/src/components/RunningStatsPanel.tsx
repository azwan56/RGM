"use client";

import { useState, useEffect, useCallback } from "react";
import { db } from "@/lib/firebase";
import { doc, onSnapshot } from "firebase/firestore";
import axios from "@/lib/apiClient";
import StatsCard from "./StatsCard";

interface Stats {
  total_distance_km: number;
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

export default function RunningStatsPanel({ uid }: { uid: string }) {
  const [stats, setStats] = useState<Stats>(EMPTY_STATS);
  const [syncing, setSyncing] = useState(false);
  const [fullSyncing, setFullSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Real-time listener on leaderboard/{uid}
  useEffect(() => {
    const ref = doc(db, "leaderboard", uid);
    const unsub = onSnapshot(ref, (snap) => {
      if (snap.exists()) {
        setStats({ ...EMPTY_STATS, ...snap.data() } as Stats);
      }
    });
    return () => unsub();
  }, [uid]);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      await axios.post(`${backendUrl}/api/sync/trigger`, { uid });
      setSyncMsg({ text: "Sync successful! Data updated.", type: "success" });
    } catch (err: any) {
      console.error("Sync trigger error:", err?.message || err);
      setSyncMsg({ text: "Sync failed. Please try again.", type: "error" });
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMsg(null), 4000);
    }
  }, [uid]);

  const handleFullSync = useCallback(async (sinceDate = "2025-01-01") => {
    setFullSyncing(true);
    setSyncMsg(null);
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

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
            setTimeout(() => setSyncMsg(null), 8000);
          } else if (s.state === "error") {
            clearInterval(poll);
            setFullSyncing(false);
            setSyncMsg({ text: `同步出错：${s.error || "未知错误"}`, type: "error" });
            setTimeout(() => setSyncMsg(null), 6000);
          } else if (s.state === "running") {
            setSyncMsg({ text: `同步中… 已保存 ${s.saved} 条 (第 ${s.pages} 页)`, type: "success" });
          }
        } catch (_) {}
      }, 3000);

    } catch (err: any) {
      console.error("Full sync error:", err?.message || err);
      setSyncMsg({ text: "历史同步启动失败，请检查网络连接。", type: "error" });
      setFullSyncing(false);
      setTimeout(() => setSyncMsg(null), 6000);
    }
  }, [uid]);

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
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleSync}
            disabled={syncing || fullSyncing}
            className="flex items-center gap-2 px-4 py-2 bg-[#FC4C02] hover:bg-orange-500 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-all shadow-lg shadow-[#FC4C02]/20"
          >
            <svg
              className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`}
              viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {syncing ? "Syncing..." : "Sync Strava"}
          </button>

          {/* Full history sync dropdown */}
          <div className="relative group">
            <button
              disabled={syncing || fullSyncing}
              className="flex items-center gap-1.5 px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 disabled:opacity-50 text-zinc-400 hover:text-white text-sm font-semibold rounded-xl transition-all"
            >
              <svg className={`w-4 h-4 ${fullSyncing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {fullSyncing ? "同步中..." : "历史数据"}
              <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {/* Dropdown */}
            <div className="absolute right-0 top-full mt-1 bg-zinc-900 border border-white/10 rounded-xl shadow-2xl z-50 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all min-w-[160px]">
              {[
                { label: "2025年至今",  date: "2025-01-01" },
                { label: "2024年至今",  date: "2024-01-01" },
                { label: "所有历史数据", date: "2020-01-01" },
              ].map(({ label, date }) => (
                <button
                  key={date}
                  onClick={() => handleFullSync(date)}
                  className="w-full text-left px-4 py-2.5 text-sm text-zinc-300 hover:text-white hover:bg-white/5 transition-colors first:rounded-t-xl last:rounded-b-xl"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Feedback message */}
      {syncMsg && (
        <div className={`px-4 py-2.5 rounded-xl text-sm font-medium ${syncMsg.type === "success" ? "bg-green-500/15 text-green-400 border border-green-500/20" : "bg-red-500/15 text-red-400 border border-red-500/20"}`}>
          {syncMsg.text}
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
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
