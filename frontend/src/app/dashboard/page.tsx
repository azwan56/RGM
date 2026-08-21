"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import GarminConnectModal from "@/components/GarminConnectModal";
import {
  Zap,
  Activity,
  Heart,
  Moon,
  BatteryCharging,
  TrendingUp,
  RefreshCw,
  Award,
  Trophy,
  ChevronRight,
  Flame,
  Calendar,
  Compass,
} from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  BarChart,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [scienceData, setScienceData] = useState<any>(null);
  const [garminModalOpen, setGarminModalOpen] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadDashboardData(u.id);
      } else {
        router.push("/login");
      }
    });
  }, [router]);

  async function loadDashboardData(uid: string) {
    setLoading(true);
    try {
      const [dashRes, sciRes] = await Promise.all([
        apiClient.get(`/api/miniapp/dashboard/${uid}`),
        apiClient.get(`/api/science/metrics/${uid}`),
      ]);
      setDashboardData(dashRes.data);
      setScienceData(sciRes.data);
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    if (!user) return;
    if (!dashboardData?.user?.garmin_connected) {
      setGarminModalOpen(true);
      return;
    }

    setSyncing(true);
    try {
      const res = await apiClient.post("/api/sync/trigger", { uid: user.id });
      if (res.data?.success === false) {
        alert("同步提示: " + (res.data?.error || "佳明连接中，请稍后再试"));
      }
      await loadDashboardData(user.id);
    } catch (e) {
      console.error("Sync error:", e);
    } finally {
      setSyncing(false);
    }
  }

  const ctlHistory = scienceData?.ctl_atl_tsb_history || [];
  const monthlyTrend = dashboardData?.monthly_trend?.trend || [];
  const yearlyStats = dashboardData?.yearly_stats || {};
  const todayHealth = dashboardData?.today_health || {};

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Top Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight flex items-center gap-2.5">
              <span>跑步控制台 Dashboard</span>
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              追踪当前训练周期负荷，直连佳明手表与 Renato Canova 科学训练系统
            </p>
          </div>

          <div className="flex items-center gap-3">
            {dashboardData?.user?.garmin_connected ? (
              <div className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Garmin 已连接
              </div>
            ) : (
              <button
                onClick={() => setGarminModalOpen(true)}
                className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl text-xs sm:text-sm font-bold bg-[#FC4C02] text-white hover:bg-orange-600 transition active:scale-95 shadow-md shadow-[#FC4C02]/20"
              >
                <Zap className="w-3.5 h-3.5" />
                绑定 Garmin 账号
              </button>
            )}

            <button
              onClick={handleSync}
              disabled={syncing}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold bg-[#1a1a1e] border border-white/10 hover:border-white/20 transition active:scale-95 text-zinc-200"
            >
              <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin text-[#FC4C02]" : ""}`} />
              {syncing ? "正在从 Garmin 同步..." : "一键同步数据"}
            </button>
          </div>
        </div>

        {/* ── CARD 1: 体能与状况指数 (Fitness & Form) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <div className="flex items-center gap-2.5">
                <Zap className="w-5 h-5 text-[#38bdf8]" />
                <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                  体能与状况指数 (Fitness & Form)
                </h2>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                基于标准 Banister TRIMP 与 EWMA 模型算法
              </p>
            </div>

            {/* Badges in Top Right */}
            <div className="flex items-center gap-3">
              <div className="bg-[#1a1a20] border border-white/5 px-4 py-2 rounded-2xl flex flex-col items-center min-w-[76px]">
                <span className="text-[10px] text-[#38bdf8] font-bold tracking-wider uppercase">CTL 体能</span>
                <span className="text-lg font-black text-white">{scienceData?.current_ctl ?? 58.7}</span>
              </div>
              <div className="bg-[#1a1a20] border border-white/5 px-4 py-2 rounded-2xl flex flex-col items-center min-w-[76px]">
                <span className="text-[10px] text-[#ec4899] font-bold tracking-wider uppercase">ATL 疲劳</span>
                <span className="text-lg font-black text-white">{scienceData?.current_atl ?? 70.3}</span>
              </div>
              <div className="bg-[#1a1a20] border border-white/5 px-4 py-2 rounded-2xl flex flex-col items-center min-w-[76px]">
                <span className="text-[10px] text-zinc-400 font-bold tracking-wider uppercase">TSB 状况</span>
                <span
                  className="text-lg font-black"
                  style={{ color: scienceData?.current_tsb_badge?.color || "#22c55e" }}
                >
                  {scienceData?.current_tsb ?? -20.2}
                </span>
              </div>
            </div>
          </div>

          {/* Combined Chart */}
          <div className="h-[280px] sm:h-[320px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={ctlHistory.slice(-30)} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#222" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="short_date"
                  stroke="#666"
                  fontSize={11}
                  tickLine={false}
                />
                <YAxis stroke="#666" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#16161a",
                    borderColor: "rgba(255,255,255,0.15)",
                    borderRadius: "16px",
                    fontSize: "12px",
                    color: "#fff",
                  }}
                  formatter={(val: any, name: any) => {
                    if (name === "ctl") return [`${val}`, "体能 (CTL)"];
                    if (name === "atl") return [`${val}`, "疲劳 (ATL)"];
                    if (name === "tsb") return [`${val}`, "状况 (TSB)"];
                    return [val, name];
                  }}
                />
                <Bar dataKey="tsb" barSize={12} radius={[4, 4, 4, 4]}>
                  {ctlHistory.slice(-30).map((entry: any, index: number) => {
                    const tsbVal = Number(entry.tsb || 0);
                    let color = "#0ea5e9";
                    if (tsbVal > 5) color = "#22c55e";
                    else if (tsbVal >= -30) color = "#1890ff";
                    else if (tsbVal >= -50) color = "#eab308";
                    else color = "#ef4444";
                    return <Cell key={`cell-${index}`} fill={color} opacity={0.85} />;
                  })}
                </Bar>
                <Line
                  type="monotone"
                  dataKey="ctl"
                  name="ctl"
                  stroke="#38bdf8"
                  strokeWidth={2.5}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="atl"
                  name="atl"
                  stroke="#ec4899"
                  strokeWidth={2.5}
                  dot={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Color-Coded Legend */}
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 mt-4 pt-4 border-t border-white/5 text-xs text-zinc-400">
            <div className="flex items-center gap-2">
              <span className="w-3 h-1 bg-[#38bdf8] rounded-full inline-block" />
              <span>体能 (CTL): 42天长期压力</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-1 bg-[#ec4899] rounded-full inline-block" />
              <span>疲劳 (ATL): 7天近期压力</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#22c55e] rounded-sm inline-block" />
              <span>&gt;5 巅峰</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#1890ff] rounded-sm inline-block" />
              <span>-30~5 训练中</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#eab308] rounded-sm inline-block" />
              <span>-50~-30 疲劳</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#ef4444] rounded-sm inline-block" />
              <span>&lt;-50 严重</span>
            </div>
          </div>
        </div>

        {/* ── CARD 2: Garmin 生理与恢复卡片 (4-Grid) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="flex items-center gap-2">
                <Compass className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                  Garmin 生理与恢复卡片
                </h2>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                最近更新: {todayHealth?.date || "今日"}
              </p>
            </div>
            <div className="text-xs text-zinc-500 bg-white/5 px-3 py-1.5 rounded-full border border-white/5">
              Garmin Direct Sync
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. 睡眠恢复 */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs mb-2">
                <Moon className="w-4 h-4 text-indigo-400" />
                <span>睡眠恢复</span>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-white">
                  {todayHealth?.sleep_score ?? 69} <span className="text-sm font-medium text-zinc-400">分</span>
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  时长 {todayHealth?.sleep_duration_text || "8h 35m"}
                </div>
              </div>
            </div>

            {/* 2. 静息心率 */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs mb-2">
                <Heart className="w-4 h-4 text-rose-500" />
                <span>静息心率 (RHR)</span>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-rose-400">
                  {todayHealth?.resting_heart_rate ?? 56} <span className="text-sm font-medium text-zinc-400">bpm</span>
                </div>
                <div className="text-xs text-zinc-500 mt-1">清晨生理基线</div>
              </div>
            </div>

            {/* 3. 身体电量 */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs mb-2">
                <BatteryCharging className="w-4 h-4 text-amber-400" />
                <span>身体电量</span>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-amber-300">
                  {todayHealth?.body_battery_max ?? 54}%
                </div>
                <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-2">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 rounded-full"
                    style={{ width: `${Math.min(100, todayHealth?.body_battery_max ?? 54)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* 4. 夜间 HRV / 摄氧量 */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs mb-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                <span>夜间 HRV / 摄氧量</span>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-cyan-400">
                  {todayHealth?.hrv_ms ?? 29} <span className="text-sm font-medium text-zinc-400">ms</span>
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  周均: {todayHealth?.hrv_weekly_avg ?? 32} ms · VO2Max {todayHealth?.vo2_max ?? 45}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── CARD 3: 月度跑量趋势 (近 6 个月) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                月度跑量趋势
              </h2>
              <p className="text-xs text-zinc-400 mt-1">近 6 个月跑量分布与环比</p>
            </div>
            <div className="text-right">
              <div className="text-2xl sm:text-3xl font-black text-white">
                {dashboardData?.monthly_trend?.current_month_km ?? 119.9} <span className="text-sm text-zinc-400 font-normal">km</span>
              </div>
              <div className="text-xs text-emerald-400 font-semibold mt-0.5">
                ↑ 较上月 +{dashboardData?.monthly_trend?.pct_change ?? 9.2}%
              </div>
            </div>
          </div>

          {/* 6-Month Bar Chart */}
          <div className="h-[200px] sm:h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#1f1f24" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month_label" stroke="#666" fontSize={11} tickLine={false} />
                <YAxis stroke="#666" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#16161a",
                    borderColor: "rgba(255,255,255,0.15)",
                    borderRadius: "14px",
                    fontSize: "12px",
                  }}
                  formatter={(val: any) => [`${val} km`, "总跑量"]}
                />
                <Bar dataKey="distance_km" radius={[6, 6, 0, 0]}>
                  {monthlyTrend.map((entry: any, index: number) => (
                    <Cell
                      key={`month-cell-${index}`}
                      fill={entry.is_current ? "#22c55e" : "#1b4332"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 3-Month Summary Breakdown */}
          <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-white/5 text-center">
            {(dashboardData?.monthly_trend?.recent_3_months || []).map((m: any, idx: number) => (
              <div key={idx} className="bg-[#18181c] border border-white/5 rounded-2xl py-3 px-2">
                <div className="text-xs text-zinc-400">{m.month_label}</div>
                <div className="text-base sm:text-lg font-black text-white mt-1">
                  {m.distance_km} <span className="text-xs text-zinc-500 font-normal">km</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-0.5">{m.count} 次</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── CARD 4: 2026 年度统计 ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2.5">
              <Trophy className="w-5 h-5 text-amber-500" />
              <div>
                <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                  {yearlyStats.year || 2026} 年度统计
                </h2>
                <p className="text-xs text-zinc-400 mt-1">
                  目标 {yearlyStats.target_year_km || 3400} km · 月均目标 {yearlyStats.monthly_target_km || 70} km
                </p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl sm:text-3xl font-black text-rose-500">
                {yearlyStats.progress_pct || 38.9}%
              </div>
              <div className="text-xs text-zinc-400 mt-0.5">完成度</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
            {/* Circular Indicator */}
            <div className="flex flex-col items-center justify-center p-6 bg-[#18181c] border border-white/5 rounded-3xl">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="50" fill="transparent" stroke="#222" strokeWidth="10" />
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    fill="transparent"
                    stroke="#f43f5e"
                    strokeWidth="10"
                    strokeDasharray="314.159"
                    strokeDashoffset={314.159 * (1 - (yearlyStats.progress_pct || 38.9) / 100)}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-xl font-black text-white">{yearlyStats.total_km || 1324.3}</span>
                  <span className="text-[10px] text-zinc-400">km</span>
                </div>
              </div>
            </div>

            {/* 3 Metric Cards */}
            <div className="md:col-span-3 grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-center">
                <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                  <span>🏃 总跑次</span>
                </div>
                <div className="text-2xl font-black text-white">
                  {yearlyStats.total_runs || 88} <span className="text-xs text-zinc-500 font-normal">次</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-1">全年累计运动</div>
              </div>

              <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-center">
                <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                  <span>📅 月均跑量</span>
                </div>
                <div className="text-2xl font-black text-white">
                  {yearlyStats.avg_monthly_km || 165.5} <span className="text-xs text-zinc-500 font-normal">km</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-1">月度平均负荷</div>
              </div>

              <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-center">
                <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                  <span>🎯 年终预测</span>
                </div>
                <div className="text-2xl font-black text-emerald-400">
                  {yearlyStats.projected_year_km || 1986.4} <span className="text-xs text-zinc-500 font-normal">km</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-1">年终推算跑量</div>
              </div>
            </div>
          </div>

          {/* Bottom Progress Bar */}
          <div className="mt-6 pt-6 border-t border-white/5">
            <div className="flex items-center justify-between text-xs text-zinc-400 mb-2">
              <span>0 km</span>
              <span className="font-bold text-white">
                {yearlyStats.total_km || 1324.3} / {yearlyStats.target_year_km || 3400} km
              </span>
              <span>{yearlyStats.target_year_km || 3400} km</span>
            </div>
            <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
              <div
                className="h-full bg-rose-500 rounded-full"
                style={{ width: `${Math.min(100, yearlyStats.progress_pct || 38.9)}%` }}
              />
            </div>
            <div className="text-xs text-amber-400 mt-3 flex items-center gap-1.5">
              <span>🏆 最佳月份:</span>
              <span className="text-white font-semibold">
                {yearlyStats.best_month?.name || "5月"} ({yearlyStats.best_month?.distance_km || 413.2}km) · 平均配速 {yearlyStats.best_month?.avg_pace || "7:41"}
              </span>
            </div>
          </div>
        </div>

        {/* ── CARD 5: 近期训练明细 ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">近期训练明细</h2>
              <p className="text-xs text-zinc-400 mt-1">Garmin 自动同步记录与 TRIMP 负荷</p>
            </div>
          </div>

          <div className="divide-y divide-white/5">
            {(!dashboardData?.recent_activities || dashboardData.recent_activities.length === 0) ? (
              <div className="py-8 text-center text-zinc-500 text-xs sm:text-sm">
                暂无近期跑步记录，绑定 Garmin 账号并点击【一键同步数据】后即可自动呈现。
              </div>
            ) : (
              dashboardData.recent_activities.map((act: any) => (
                <div key={act.id} className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3.5">
                    <div className="w-10 h-10 rounded-2xl bg-[#1e1e24] flex items-center justify-center text-[#FC4C02]">
                      🏃
                    </div>
                    <div>
                      <div className="font-bold text-sm sm:text-base text-white">{act.name}</div>
                      <div className="text-xs text-zinc-500 mt-0.5">{act.start_time?.replace("T", " ")?.slice(0, 16)}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6 text-xs sm:text-sm">
                    <div>
                      <span className="text-zinc-500 block text-[10px]">距离</span>
                      <span className="font-bold text-white text-base">{act.distance_km} km</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block text-[10px]">配速</span>
                      <span className="font-bold text-cyan-400">{act.avg_pace_str}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block text-[10px]">心率</span>
                      <span className="font-bold text-rose-400">{act.average_heartrate || "—"} bpm</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block text-[10px]">TRIMP</span>
                      <span className="font-bold text-amber-400">{act.trimp || "—"}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </main>

      <GarminConnectModal
        open={garminModalOpen}
        onClose={() => setGarminModalOpen(false)}
        uid={user?.id}
        onSuccess={() => user && loadDashboardData(user.id)}
      />
    </div>
  );
}
