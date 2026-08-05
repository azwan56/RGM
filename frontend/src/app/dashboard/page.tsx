"use client";

import { useEffect, useState, useCallback, useRef } from "react";
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

  // Sync states
  const [garminSyncing, setGarminSyncing] = useState(false);
  const [stravaSyncing, setStravaSyncing] = useState(false);
  const [fullSyncing, setFullSyncing] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [syncMsg, setSyncMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const dropdownRef = useRef<HTMLDivElement>(null);

  // Pre-fetched data from combined endpoint
  const [dashboardData, setDashboardData] = useState<any>(null);

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  // Fetch all dashboard data in ONE request
  const fetchDashboard = useCallback(async (uid: string, month: number) => {
    try {
      const res = await axios.get(`${backendUrl}/api/data/dashboard/${uid}`, {
        params: { period: "monthly", month, _t: Date.now() },
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

  // Click outside to close history dropdown
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
      setGarminMsg("✓ 验证并绑定成功！已拉取 Garmin 生理与健康数据...");
      setTimeout(async () => {
        setShowGarminModal(false);
        setGarminMsg("");
        setGarminPassword("");
        await fetchDashboard(user.uid, activityMonth);
      }, 1000);
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

  // Handle Garmin Sync
  const handleGarminSync = async () => {
    if (!user || garminSyncing) return;
    setGarminSyncing(true);
    setSyncMsg(null);
    try {
      await axios.post(`${backendUrl}/api/sync/trigger`, { uid: user.uid });
      await fetchDashboard(user.uid, activityMonth);
      setSyncMsg({ text: "✓ Garmin 生理与跑步数据同步成功！", type: "success" });
    } catch (e: any) {
      console.error("Garmin sync error:", e);
      const detail = e.response?.data?.detail;
      if (detail && detail.includes("未检测到 Garmin 绑定账号")) {
        setShowGarminModal(true);
      } else {
        setSyncMsg({ text: detail || "Garmin 同步失败，请检查佳明账号、密码或选区 (garmin.cn vs garmin.com)。", type: "error" });
      }
    } finally {
      setGarminSyncing(false);
      setTimeout(() => setSyncMsg(null), 5000);
    }
  };

  // Handle Strava Current Period Sync
  const handleStravaSync = async () => {
    if (!user || stravaSyncing) return;
    setStravaSyncing(true);
    setSyncMsg(null);
    try {
      await axios.post(`${backendUrl}/api/sync/trigger`, { uid: user.uid });
      await fetchDashboard(user.uid, activityMonth);
      setSyncMsg({ text: "✓ Strava 数据同步成功！", type: "success" });
    } catch (e) {
      console.error("Strava sync error:", e);
      setSyncMsg({ text: "Strava 同步失败，请稍后重试", type: "error" });
    } finally {
      setStravaSyncing(false);
      setTimeout(() => setSyncMsg(null), 4000);
    }
  };

  // Handle Strava Full History Sync
  const handleFullSync = async (sinceDate = "2025-01-01") => {
    if (!user || fullSyncing) return;
    setFullSyncing(true);
    setSyncMsg(null);
    try {
      await axios.post(`${backendUrl}/api/sync/full`, { uid: user.uid, since_date: sinceDate }, { timeout: 15000 });
      setSyncMsg({ text: "历史同步已启动，正在后台拉取 Strava 历史数据...", type: "success" });

      const poll = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${backendUrl}/api/sync/full-status?uid=${user.uid}`, { timeout: 8000 });
          const s = statusRes.data;
          if (s.state === "done") {
            clearInterval(poll);
            setFullSyncing(false);
            setSyncMsg({ text: `✓ 历史同步完成！共导入 ${s.saved} 次 Strava 跑步记录`, type: "success" });
            fetchDashboard(user.uid, activityMonth);
            setTimeout(() => setSyncMsg(null), 8000);
          } else if (s.state === "error") {
            clearInterval(poll);
            setFullSyncing(false);
            setSyncMsg({ text: `同步出错：${s.error || "未知错误"}`, type: "error" });
            setTimeout(() => setSyncMsg(null), 6000);
          }
        } catch { /* noop */ }
      }, 3000);
    } catch (err) {
      setSyncMsg({ text: "历史同步启动失败，请检查网络连接。", type: "error" });
      setFullSyncing(false);
      setTimeout(() => setSyncMsg(null), 6000);
    }
  };

  const statusSubtitle = () => {
    const isGarmin = dashboardData?.garmin_connected;
    const isStrava = dashboardData?.strava_connected;
    if (isGarmin && isStrava) return "Garmin & Strava 双源直连 ✓";
    if (isGarmin) return "Garmin 佳明直连已启用 ✓";
    if (isStrava) return "Strava 数据已连接 ✓";
    return "点击底部“数据源连接设置”进行绑定与同步";
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

        {/* Running Stats Panel */}
        {user && (
          <RunningStatsPanel uid={user.uid} initialStats={dashboardData?.stats} />
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
            health={dashboardData?.latest_health ?? dashboardData?.health}
            vo2Max={dashboardData?.profile?.vo2_max}
            isGarminConnected={dashboardData?.garmin_connected}
            onSync={handleGarminSync}
          />
        )}

        {/* Feedback Alert Toast */}
        {syncMsg && (
          <div className={`p-4 rounded-2xl text-xs font-semibold flex items-center justify-between shadow-xl backdrop-blur-md animate-in fade-in ${syncMsg.type === "success" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" : "bg-rose-500/20 text-rose-300 border border-rose-500/30"}`}>
            <span>{syncMsg.text}</span>
            <button onClick={() => setSyncMsg(null)} className="opacity-70 hover:opacity-100">✕</button>
          </div>
        )}

        {/* ── Data Source Connection & Dedicated Sync Section ── */}
        <div className="bg-white/3 border border-white/10 rounded-3xl p-5 md:p-6 space-y-5 backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <span>🔗</span> 数据源连接与独立同步设置 (Data Sources & Sync)
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                独立管理 Garmin 佳明直连与 Strava 授权，各自配备专属的“Sync 数据同步”按键。
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 1. Garmin Connection & Dedicated Sync Card */}
            <div className="bg-white/4 border border-white/8 rounded-2xl p-4.5 flex flex-col justify-between min-h-[170px] space-y-4">
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

              <div className="space-y-2.5">
                {dashboardData?.garmin_connected ? (
                  <>
                    <div className="flex items-center justify-between gap-2 text-xs text-zinc-400">
                      <span className="truncate">{dashboardData?.profile?.garmin_email || "已绑定 Garmin 账号"}</span>
                      <button
                        onClick={handleGarminUnbind}
                        className="text-xs text-rose-400 hover:text-rose-300 underline font-medium shrink-0"
                      >
                        断开链接
                      </button>
                    </div>
                    <button
                      onClick={handleGarminSync}
                      disabled={garminSyncing}
                      className="w-full h-11 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold text-xs rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
                    >
                      {garminSyncing ? (
                        <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> 正在同步 Garmin...</>
                      ) : (
                        "⌚ Sync Garmin 数据"
                      )}
                    </button>
                  </>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => setShowGarminModal(true)}
                      className="h-11 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl transition flex items-center justify-center gap-1 shadow-lg shadow-blue-600/20"
                    >
                      <span>⌚</span> 绑定 Garmin
                    </button>
                    <button
                      onClick={handleGarminSync}
                      disabled={garminSyncing}
                      className="h-11 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/40 text-blue-400 hover:text-white font-bold text-xs rounded-xl transition flex items-center justify-center gap-1.5"
                    >
                      {garminSyncing ? (
                        <div className="w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        "🔄 Sync Garmin"
                      )}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* 2. Strava Connection & Dedicated Sync Card */}
            <div className="bg-white/4 border border-white/8 rounded-2xl p-4.5 flex flex-col justify-between min-h-[170px] space-y-4">
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

              <div className="space-y-2.5">
                {dashboardData?.strava_connected ? (
                  <>
                    <div className="flex items-center justify-between gap-2 text-xs text-zinc-400">
                      <span className="truncate">{dashboardData?.profile?.strava_name || "已授权 Strava 账号"}</span>
                      <button
                        onClick={handleStravaUnbind}
                        className="text-xs text-rose-400 hover:text-rose-300 underline font-medium shrink-0"
                      >
                        断开链接
                      </button>
                    </div>
                    <div className="grid grid-cols-5 gap-2">
                      <button
                        onClick={handleStravaSync}
                        disabled={stravaSyncing || fullSyncing}
                        className="col-span-3 h-11 bg-[#FC4C02] hover:bg-[#e04400] disabled:opacity-50 text-white font-bold text-xs rounded-xl transition flex items-center justify-center gap-1.5 shadow-lg shadow-[#FC4C02]/20"
                      >
                        <svg className={`w-3.5 h-3.5 ${stravaSyncing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        {stravaSyncing ? "同步中..." : "Sync Strava"}
                      </button>

                      {/* Full history dropdown */}
                      <div className="col-span-2 relative" ref={dropdownRef}>
                        <button
                          onClick={() => setHistoryOpen((o) => !o)}
                          disabled={stravaSyncing || fullSyncing}
                          className="w-full h-11 bg-white/5 hover:bg-white/10 border border-white/10 disabled:opacity-50 text-zinc-300 font-bold text-xs rounded-xl transition flex items-center justify-center gap-1"
                        >
                          <svg className={`w-3.5 h-3.5 ${fullSyncing ? "animate-spin" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          {fullSyncing ? "同步中" : "历史数据"}
                          <svg className={`w-3 h-3 transition-transform ${historyOpen ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                        {historyOpen && (
                          <div className="absolute right-0 bottom-full mb-1 bg-zinc-900 border border-white/10 rounded-xl shadow-2xl z-50 min-w-[150px]">
                            {[
                              { label: "2025年至今",  date: "2025-01-01" },
                              { label: "2024年至今",  date: "2024-01-01" },
                              { label: "所有历史数据", date: "2020-01-01" },
                            ].map(({ label, date }) => (
                              <button
                                key={date}
                                onClick={() => { setHistoryOpen(false); handleFullSync(date); }}
                                className="w-full text-left px-3.5 py-2.5 text-xs text-zinc-300 hover:text-white hover:bg-white/5 transition-colors first:rounded-t-xl last:rounded-b-xl"
                              >
                                {label}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <StravaConnectBtn />
                      <button
                        onClick={handleStravaSync}
                        disabled={stravaSyncing}
                        className="h-11 bg-[#FC4C02]/20 hover:bg-[#FC4C02]/30 border border-[#FC4C02]/40 text-[#FC4C02] hover:text-white font-bold text-xs rounded-xl transition flex items-center justify-center gap-1.5"
                      >
                        {stravaSyncing ? (
                          <div className="w-3.5 h-3.5 border-2 border-[#FC4C02] border-t-transparent rounded-full animate-spin" />
                        ) : (
                          "⚡ Sync Strava"
                        )}
                      </button>
                    </div>
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
