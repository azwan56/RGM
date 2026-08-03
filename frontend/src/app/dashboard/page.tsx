"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

import { auth } from "@/lib/firebase";
import axios from "@/lib/apiClient";
import StravaConnectBtn from "@/components/StravaConnectBtn";
import GarminHealthCard from "@/components/GarminHealthCard";
import RunningStatsPanel from "@/components/RunningStatsPanel";
import ActivityList from "@/components/ActivityList";
import LeaderboardWidget from "@/components/LeaderboardWidget";
import dynamic from "next/dynamic";
import PageNav from "@/components/PageNav";

const FitnessChart = dynamic(() => import("@/components/FitnessChart"), {
  loading: () => <div className="h-80 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />,
  ssr: false,
});

export default function Dashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);
  const [period, setPeriod] = useState<"weekly" | "monthly">("monthly");
  const [displayName, setDisplayName] = useState("");
  const [activityMonth, setActivityMonth] = useState(new Date().getMonth());

  // Garmin bind modal state
  const [showGarminModal, setShowGarminModal] = useState(false);
  const [garminEmail, setGarminEmail] = useState("");
  const [garminPassword, setGarminPassword] = useState("");
  const [garminDomain, setGarminDomain] = useState<"garmin.cn" | "garmin.com">("garmin.cn");
  const [garminLoading, setGarminLoading] = useState(false);
  const [garminMsg, setGarminMsg] = useState("");

  // Sync loading state
  const [syncing, setSyncing] = useState(false);

  // Pre-fetched data from combined endpoint
  const [dashboardData, setDashboardData] = useState<any>(null);

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  // Fetch all dashboard data in ONE request
  const fetchDashboard = useCallback(async (uid: string, month: number) => {
    try {
      const res = await axios.get(`${backendUrl}/api/data/dashboard/${uid}`, {
        params: { period: "monthly", month },
      });
      const d = res.data;
      setDashboardData(d);
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

  // Handle Garmin Binding
  const handleGarminBind = async () => {
    if (!user) return;
    if (!garminEmail || !garminPassword) {
      setGarminMsg("请输入 Garmin 账号邮箱与密码");
      return;
    }
    setGarminLoading(true);
    setGarminMsg("");
    try {
      await axios.post(`${backendUrl}/api/auth/garmin/bind`, {
        uid: user.uid,
        email: garminEmail,
        password: garminPassword,
        domain: garminDomain,
      });
      setGarminMsg("✓ 绑定成功！已开始自动同步佳明数据...");
      setTimeout(async () => {
        setShowGarminModal(false);
        setGarminMsg("");
        setGarminPassword("");
        await fetchDashboard(user.uid, activityMonth);
      }, 1200);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setGarminMsg(detail || "绑定失败，请检查账号、密码及选择的佳明区域（中国版 vs 国际版）。");
    } finally {
      setGarminLoading(false);
    }
  };

  // Handle Garmin Unbinding
  const handleGarminUnbind = async () => {
    if (!user || !confirm("确定解绑 Garmin 佳明账号吗？")) return;
    try {
      await axios.post(`${backendUrl}/api/auth/garmin/unbind`, { uid: user.uid });
      await fetchDashboard(user.uid, activityMonth);
    } catch (err) {
      alert("解绑失败，请重试");
    }
  };

  // Handle Strava Unbinding
  const handleStravaUnbind = async () => {
    if (!user || !confirm("确定解除 Strava 账号授权吗？")) return;
    try {
      await axios.post(`${backendUrl}/api/auth/strava/unbind`, { uid: user.uid });
      await fetchDashboard(user.uid, activityMonth);
    } catch (err) {
      alert("解绑失败，请重试");
    }
  };

  // Handle manual sync trigger
  const handleSyncAll = async () => {
    if (!user || syncing) return;
    setSyncing(true);
    try {
      await axios.post(`${backendUrl}/api/sync/trigger`, { uid: user.uid });
      await fetchDashboard(user.uid, activityMonth);
    } catch (e) {
      console.error("Sync error:", e);
    } finally {
      setSyncing(false);
    }
  };

  const statusSubtitle = () => {
    const isGarmin = dashboardData?.garmin_connected;
    const isStrava = dashboardData?.strava_connected;
    if (isGarmin && isStrava) return "Garmin & Strava 双源直连 ✓";
    if (isGarmin) return "Garmin 佳明直连已启用 ✓";
    if (isStrava) return "Strava 数据已连接 ✓";
    return "点击底部绑定 Garmin 或 Strava 记录";
  };

  const syncBtnLabel = () => {
    const isGarmin = dashboardData?.garmin_connected;
    const isStrava = dashboardData?.strava_connected;
    if (isGarmin && isStrava) return "🔄 同步全量数据";
    if (isGarmin) return "⌚ 同步 Garmin 数据";
    if (isStrava) return " Connect Strava";
    return "🔄 同步数据";
  };

  if (loading) {
    const userName = user?.displayName || user?.email?.split('@')[0] || "跑者";
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex flex-col items-center justify-center relative overflow-hidden">
        <div className="absolute top-0 right-0 w-[40%] h-[40%] rounded-full bg-[#FC4C02]/15 blur-[160px] pointer-events-none animate-pulse" />
        <div className="absolute bottom-0 left-0 w-[30%] h-[30%] rounded-full bg-blue-600/10 blur-[120px] pointer-events-none animate-pulse" style={{ animationDelay: "1s" }} />
        
        <div className="z-10 flex flex-col items-center gap-8 px-6 text-center animate-in fade-in zoom-in duration-700">
          <div className="relative">
            <img 
              src="/icons/icon-512x512.png" 
              alt="RGM Logo" 
              className="w-24 h-24 md:w-32 md:h-32 rounded-3xl shadow-2xl drop-shadow-[0_0_20px_rgba(252,76,2,0.3)] animate-bounce" 
            />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl md:text-2xl font-bold text-white tracking-wide">
              正在同步数据...
            </h2>
            <p className="text-zinc-500 text-sm">
              欢迎回来，{userName}
            </p>
          </div>
          <div className="w-48 h-1 bg-white/10 rounded-full overflow-hidden">
            <div className="w-full h-full bg-gradient-to-r from-[#FC4C02] via-orange-400 to-[#FC4C02] animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white pt-20 md:pt-24 px-4 md:px-6 pb-16 md:pb-20 relative">
      <div className="absolute top-0 right-0 w-[40%] h-[40%] rounded-full bg-orange-600/10 blur-[160px] pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[30%] h-[30%] rounded-full bg-blue-600/5 blur-[120px] pointer-events-none" />

      <main className="max-w-5xl mx-auto space-y-6 md:space-y-8 relative z-10">

        {/* Header */}
        <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-black text-white mb-1">Dashboard</h1>
            <p className="text-zinc-500 text-sm">
              {user?.email || user?.phoneNumber || user?.displayName || "已登录"} &mdash; {statusSubtitle()}
            </p>
          </div>
          <PageNav />
        </header>

        {/* Sync control & Running Stats Panel */}
        {user && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-500 font-medium">数据控制面板</span>
              <button
                onClick={handleSyncAll}
                disabled={syncing}
                className="px-4 py-2 bg-gradient-to-r from-[#FC4C02] to-orange-500 hover:from-orange-500 hover:to-[#FC4C02] disabled:opacity-50 text-white font-bold text-xs rounded-xl transition shadow-md flex items-center gap-2"
              >
                {syncing ? (
                  <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> 正在同步...</>
                ) : (
                  syncBtnLabel()
                )}
              </button>
            </div>
            <RunningStatsPanel uid={user.uid} initialStats={dashboardData?.stats} />
          </div>
        )}

        {/* Leaderboard + Activity List — side by side */}
        {user && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Leaderboard */}
            <div className="flex flex-col" style={{ height: "520px" }}>
              <div className="flex-1 overflow-hidden">
                <LeaderboardWidget currentUid={user.uid} fixedHeight="520px" initialEntries={dashboardData?.leaderboard?.entries} />
              </div>
            </div>

            {/* Activity List */}
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

        {/* Fitness & Form Chart */}
        {user && (
          <FitnessChart uid={user.uid} />
        )}

        {/* Garmin Health Card */}
        {user && (
          <GarminHealthCard
            health={dashboardData?.latest_health}
            vo2Max={dashboardData?.profile?.vo2_max}
            isGarminConnected={dashboardData?.garmin_connected}
            onSync={handleSyncAll}
          />
        )}

        {/* ── Data Source Connection Section (Placed at the VERY BOTTOM as requested) ── */}
        <div className="bg-white/3 border border-white/10 rounded-3xl p-5 md:p-6 space-y-4 backdrop-blur-md">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span>🔗</span> 数据源连接设置 (Data Sources)
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                实时连接 Garmin 佳明账号或 Strava，自动同步全量跑步与身体恢复数据。
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 1. Garmin Connection Card */}
            <div className="bg-white/4 border border-white/8 rounded-2xl p-4.5 flex flex-col justify-between h-36">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="text-2xl">⌚</span>
                  <div>
                    <h4 className="text-sm font-bold text-white">Garmin 佳明直连</h4>
                    <p className="text-[11px] text-zinc-400">支持中国版 (garmin.cn) / 国际版 (garmin.com)</p>
                  </div>
                </div>
                {dashboardData?.garmin_connected ? (
                  <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    ✓ 已连接
                  </span>
                ) : (
                  <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-white/10 text-zinc-400">
                    未连接
                  </span>
                )}
              </div>

              <div>
                {dashboardData?.garmin_connected ? (
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs text-zinc-400 truncate">
                      {dashboardData?.profile?.garmin_email || "已绑定 Garmin 账号"}
                    </span>
                    <button
                      onClick={handleGarminUnbind}
                      className="h-11 px-5 text-xs font-semibold text-rose-400 hover:text-white bg-rose-500/10 hover:bg-rose-600/30 border border-rose-500/30 rounded-xl transition flex items-center justify-center"
                    >
                      断开链接
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowGarminModal(true)}
                    className="w-full h-11 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
                  >
                    <span>⌚</span> 绑定 Garmin 佳明账号
                  </button>
                )}
              </div>
            </div>

            {/* 2. Strava Connection Card */}
            <div className="bg-white/4 border border-white/8 rounded-2xl p-4.5 flex flex-col justify-between h-36">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="text-2xl"></span>
                  <div>
                    <h4 className="text-sm font-bold text-white">Strava 账号授权</h4>
                    <p className="text-[11px] text-zinc-400">通过 Strava OAuth 自动同步跑步记录</p>
                  </div>
                </div>
                {dashboardData?.strava_connected ? (
                  <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    ✓ 已连接
                  </span>
                ) : (
                  <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-white/10 text-zinc-400">
                    未连接
                  </span>
                )}
              </div>

              <div>
                {dashboardData?.strava_connected ? (
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-xs text-zinc-400 truncate">
                      {dashboardData?.profile?.strava_name || "已授权 Strava 账号"}
                    </span>
                    <button
                      onClick={handleStravaUnbind}
                      className="h-11 px-5 text-xs font-semibold text-rose-400 hover:text-white bg-rose-500/10 hover:bg-rose-600/30 border border-rose-500/30 rounded-xl transition flex items-center justify-center"
                    >
                      断开链接
                    </button>
                  </div>
                ) : (
                  <div className="w-full h-11">
                    <StravaConnectBtn />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 mb-4 text-center">
          <p className="text-zinc-500 text-sm font-medium">RGM Running Intelligence Platform</p>
        </div>

      </main>

      {/* Garmin Bind Modal */}
      {showGarminModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
          <div className="bg-[#121215] border border-white/15 rounded-3xl p-6 max-w-md w-full space-y-5 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <span>⌚</span> 绑定 Garmin 佳明账号
              </h3>
              <button
                type="button"
                onClick={() => setShowGarminModal(false)}
                className="text-zinc-400 hover:text-white text-lg"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1.5">选择佳明服务器区域</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setGarminDomain("garmin.cn")}
                    className={`py-2.5 px-3 rounded-xl border text-xs font-semibold transition ${
                      garminDomain === "garmin.cn"
                        ? "bg-blue-600/20 border-blue-500 text-blue-400 shadow-md"
                        : "bg-white/5 border-white/10 text-zinc-400 hover:bg-white/10"
                    }`}
                  >
                    🇨🇳 中国版 (garmin.cn)
                  </button>
                  <button
                    type="button"
                    onClick={() => setGarminDomain("garmin.com")}
                    className={`py-2.5 px-3 rounded-xl border text-xs font-semibold transition ${
                      garminDomain === "garmin.com"
                        ? "bg-blue-600/20 border-blue-500 text-blue-400 shadow-md"
                        : "bg-white/5 border-white/10 text-zinc-400 hover:bg-white/10"
                    }`}
                  >
                    🌐 国际版 (garmin.com)
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1.5">Garmin 登录邮箱</label>
                <input
                  type="email"
                  placeholder="your-garmin-email@example.com"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                  value={garminEmail}
                  onChange={(e) => setGarminEmail(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-400 mb-1.5">Garmin 登录密码</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                  value={garminPassword}
                  onChange={(e) => setGarminPassword(e.target.value)}
                />
                <p className="text-[10px] text-zinc-500 mt-1">🔒 密码经 AES 高强度加密后安全存储，仅用于与 Garmin 服务器连接同步。</p>
              </div>

              {garminMsg && (
                <div className={`p-3 rounded-xl text-xs ${garminMsg.includes("✓") ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-rose-500/10 text-rose-400 border border-rose-500/20"}`}>
                  {garminMsg}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
              <button
                type="button"
                onClick={() => setShowGarminModal(false)}
                className="px-4 py-2 text-xs font-medium text-zinc-400 hover:text-white"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleGarminBind}
                disabled={garminLoading}
                className="px-5 py-2.5 text-xs font-bold bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl transition flex items-center gap-2"
              >
                {garminLoading ? (
                  <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> 验证并绑定中...</>
                ) : (
                  "验证并绑定 Garmin"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
