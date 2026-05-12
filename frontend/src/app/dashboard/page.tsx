"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/firebase";
import axios from "@/lib/apiClient";
import StravaConnectBtn from "@/components/StravaConnectBtn";
import RunningStatsPanel from "@/components/RunningStatsPanel";
import ActivityList from "@/components/ActivityList";
import LeaderboardWidget from "@/components/LeaderboardWidget";
import dynamic from "next/dynamic";

const FitnessChart = dynamic(() => import("@/components/FitnessChart"), {
  loading: () => <div className="h-80 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />,
  ssr: false,
});

export default function Dashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [isStravaConnected, setIsStravaConnected] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [period, setPeriod] = useState<"weekly" | "monthly">("monthly");
  const [displayName, setDisplayName] = useState("");
  const [activityMonth, setActivityMonth] = useState(new Date().getMonth());

  // Pre-fetched data from combined endpoint
  const [dashboardData, setDashboardData] = useState<any>(null);

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  // Fetch all dashboard data in ONE request (replaces 4 serial requests)
  const fetchDashboard = useCallback(async (uid: string, month: number) => {
    try {
      const res = await axios.get(`${backendUrl}/api/data/dashboard/${uid}`, {
        params: { period: "monthly", month },
      });
      const d = res.data;
      setDashboardData(d);
      if (d.strava_connected) setIsStravaConnected(true);
      setDisplayName(d.display_name || "");
      if (d.goal_period === "weekly" || d.goal_period === "monthly") {
        setPeriod(d.goal_period);
      }
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    }
  }, [backendUrl]);

  useEffect(() => {
    const unsubscribe = auth.onAuthStateChanged(async (u) => {
      if (!u) {
        router.push("/");
        return;
      }
      setUser(u);
      await fetchDashboard(u.uid, activityMonth);
      setLoading(false);

      // Background prefetch: warm up Coach cache while user views dashboard
      // This prevents cold-start delay when navigating to Coach page
      axios.post(`${backendUrl}/api/coach/analyze`, { uid: u.uid })
        .catch(() => {}); // Silent — don't block or show errors
    });
    return () => unsubscribe();
  }, [router, fetchDashboard, activityMonth, backendUrl]);

  // Refetch only activities when month changes
  const handleMonthChange = useCallback(async (newMonth: number) => {
    setActivityMonth(newMonth);
    if (user) {
      try {
        const year = new Date().getFullYear();
        const pad = (n: number) => String(n).padStart(2, "0");
        const start = `${year}-${pad(newMonth + 1)}-01T00:00:00`;
        const nextMonth = newMonth + 1;
        const endYear = nextMonth > 11 ? year + 1 : year;
        const endMon = nextMonth > 11 ? 0 : nextMonth;
        const end = `${endYear}-${pad(endMon + 1)}-01T00:00:00`;
        const res = await axios.get(`${backendUrl}/api/data/activities/${user.uid}`, {
          params: { start, end },
        });
        setDashboardData((prev: any) => prev ? { ...prev, activities: res.data } : prev);
      } catch (err) {
        console.error("Activities fetch error:", err);
      }
    }
  }, [user, backendUrl]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-[#FC4C02] border-t-transparent rounded-full animate-spin" />
          <p className="text-zinc-400 text-sm">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white pt-20 md:pt-24 px-4 md:px-6 pb-16 md:pb-20 relative">
      <div className="absolute top-0 right-0 w-[40%] h-[40%] rounded-full bg-[#FC4C02]/10 blur-[160px] pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[30%] h-[30%] rounded-full bg-blue-600/5 blur-[120px] pointer-events-none" />

      <main className="max-w-5xl mx-auto space-y-10 relative z-10">

        {/* Header */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-4xl md:text-5xl font-black mb-1">
              {displayName ? `你好，${displayName}` : "Welcome Back"}<span className="text-[#FC4C02]">.</span>
            </h1>
            <p className="text-zinc-400 text-sm md:text-base">
              {user?.email || user?.phoneNumber || user?.displayName || "已登录"} &mdash; {isStravaConnected ? "Strava 已连接 ✓" : "连接 Strava 开始记录"}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {/* Team button */}
            <button
              onClick={() => router.push("/dashboard/team")}
              className="flex-shrink-0 flex flex-col items-center gap-1 group"
              title="我的团队"
            >
              <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:bg-white/10 group-hover:border-white/20 transition-all">
                <svg className="w-6 h-6 text-zinc-300 group-hover:text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                 <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
              <span className="text-[10px] text-zinc-500 group-hover:text-zinc-400 transition-colors">我的团队</span>
            </button>
            {/* Profile button */}
            <button
              onClick={() => router.push("/dashboard/profile")}
              className="flex-shrink-0 flex flex-col items-center gap-1 group"
              title="跑者档案"
            >
              <div className="w-12 h-12 rounded-2xl bg-[#FC4C02]/15 border border-[#FC4C02]/30 flex items-center justify-center group-hover:bg-[#FC4C02]/25 transition-all">
                <svg className="w-6 h-6 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                  <circle cx="12" cy="8" r="4"/>
                  <path strokeLinecap="round" d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
                </svg>
              </div>
              <span className="text-[10px] text-zinc-500 group-hover:text-zinc-400 transition-colors">我的档案</span>
            </button>
          </div>
        </header>

        {/* Strava connect banner */}
        {!isStravaConnected && (
          <div className="bg-gradient-to-r from-[#FC4C02]/20 to-orange-500/10 border border-[#FC4C02]/30 p-4 md:p-6 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4 md:gap-6 backdrop-blur-sm">
            <div>
              <h3 className="text-xl font-bold mb-1">连接数据源</h3>
              <p className="text-zinc-400 text-sm">
                连接你的 Strava 账号，自动同步跑步记录并追踪进度。
              </p>
            </div>
            <StravaConnectBtn />
          </div>
        )}

        {/* Running Stats Panel — pass pre-fetched stats */}
        {isStravaConnected && user && (
          <RunningStatsPanel uid={user.uid} initialStats={dashboardData?.stats} />
        )}

        {/* Fitness & Form Chart */}
        {isStravaConnected && user && (
          <FitnessChart uid={user.uid} />
        )}

        {/* Leaderboard + Activity List — side by side, fixed height */}
        {isStravaConnected && user && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Leaderboard — first */}
            <div className="flex flex-col" style={{ height: "520px" }}>
              <div className="flex-1 overflow-hidden">
                <LeaderboardWidget currentUid={user.uid} fixedHeight="520px" initialEntries={dashboardData?.leaderboard?.entries} />
              </div>
            </div>

            {/* Activity List — with month selector */}
            <div className="flex flex-col bg-white/5 border border-white/10 rounded-3xl overflow-hidden" style={{ height: "520px" }}>
              <div className="px-5 pt-5 pb-3 flex-shrink-0 flex items-center justify-between">
                <h2 className="text-lg font-bold text-white">跑步记录</h2>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleMonthChange(Math.max(activityMonth - 1, 0))}
                    disabled={activityMonth <= 0}
                    className="w-7 h-7 flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 text-zinc-400 hover:text-white transition-all"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
                  </button>
                  <span className="text-sm font-medium text-zinc-300 min-w-[60px] text-center">
                    {new Date().getFullYear()}年{activityMonth + 1}月
                  </span>
                  <button
                    onClick={() => handleMonthChange(Math.min(activityMonth + 1, new Date().getMonth()))}
                    disabled={activityMonth >= new Date().getMonth()}
                    className="w-7 h-7 flex items-center justify-center rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 text-zinc-400 hover:text-white transition-all"
                  >
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-5 pb-5 scrollbar-thin">
                <ActivityList uid={user.uid} month={activityMonth} initialActivities={dashboardData?.activities?.activities} />
              </div>
            </div>
          </div>
        )}

        {/* Analysis + Coach — entry links */}
        {isStravaConnected && user && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link
              href="/dashboard/analysis"
              className="py-5 px-6 bg-gradient-to-r from-white/5 to-white/[0.02] hover:from-white/10 hover:to-white/5 border border-white/10 hover:border-[#FC4C02]/30 rounded-2xl transition-all group"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/15 flex items-center justify-center group-hover:bg-blue-500/25 transition-colors">
                    <svg className="w-5 h-5 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-white font-bold text-sm">深度分析</p>
                    <p className="text-zinc-500 text-xs">体能趋势 · 跑力诊断 · 月度统计</p>
                  </div>
                </div>
                <svg className="w-5 h-5 text-zinc-500 group-hover:text-[#FC4C02] transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </Link>

            <Link
              href="/dashboard/coach"
              className="py-5 px-6 bg-gradient-to-r from-white/5 to-white/[0.02] hover:from-white/10 hover:to-white/5 border border-white/10 hover:border-emerald-500/30 rounded-2xl transition-all group"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center group-hover:bg-emerald-500/25 transition-colors">
                    <svg className="w-5 h-5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-white font-bold text-sm">AI 教练</p>
                    <p className="text-zinc-500 text-xs">目标设定 · 训练建议 · 周计划</p>
                  </div>
                </div>
                <svg className="w-5 h-5 text-zinc-500 group-hover:text-emerald-400 transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </Link>
          </div>
        )}
        
        {/* Footer */}
        <div className="mt-12 mb-4 text-center">
          <p className="text-zinc-500 text-sm font-medium">Powered by Strava</p>
        </div>

      </main>
    </div>
  );
}
