"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import TrainingTabSwitcher from "@/components/TrainingTabSwitcher";
import PacerEvaluationCard from "@/components/PacerEvaluationCard";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import { Trophy, Zap, Heart, BatteryCharging, ArrowLeft, Compass, ShieldAlert, Flame } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart as RechartsLine,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export default function AnalysisPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [targetUid, setTargetUid] = useState<string>("");
  const [activeRunnerUid, setActiveRunnerUid] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [scienceData, setScienceData] = useState<any>(null);
  const [healthTrend, setHealthTrend] = useState<any[]>([]);
  const [activeTaperKey, setActiveTaperKey] = useState<string>("taper_50");
  const [showCanovaZones, setShowCanovaZones] = useState<boolean>(false);

  useEffect(() => {
    let queryTarget = "";
    if (typeof window !== "undefined") {
      const sp = new URLSearchParams(window.location.search);
      queryTarget = (sp.get("student_user_id") || sp.get("target_uid") || "").trim();
      if (queryTarget) {
        setTargetUid(queryTarget);
      }
    }

    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      let currentUid = u?.id || "";
      if (!currentUid && typeof window !== "undefined") {
        try {
          const cached = localStorage.getItem("rgm_cached_user");
          if (cached) currentUid = JSON.parse(cached)?.id || "";
        } catch {}
      }
      if (u) setUser(u);
      const effectiveTarget = queryTarget || currentUid;
      if (!effectiveTarget) {
        setLoading(false);
        router.push("/login");
        return;
      }
      setActiveRunnerUid(effectiveTarget);
      loadScienceAndHealth(effectiveTarget, currentUid || effectiveTarget);
    });
  }, [router]);

  async function loadScienceAndHealth(uid: string, viewerUid: string) {
    setLoading(true);
    try {
      const viewerQuery = viewerUid && viewerUid !== uid ? `?viewer_uid=${encodeURIComponent(viewerUid)}` : "";
      const [sciRes, healthRes] = await Promise.all([
        apiClient.get(`/api/science/metrics/${uid}${viewerQuery}`),
        apiClient.get(`/api/science/health-trend/${uid}${viewerQuery}`),
      ]);
      const sData = sciRes.data;
      setScienceData(sData);
      if (sData?.taper_simulation?.recommended_strategy) {
        setActiveTaperKey(sData.taper_simulation.recommended_strategy);
      }
      setHealthTrend(healthRes.data?.trend || []);
    } catch (e) {
      console.error("Load science & health error:", e);
    } finally {
      setLoading(false);
    }
  }

  const isInspectingOther = Boolean(targetUid && user?.id && targetUid !== user.id) || Boolean(targetUid);
  const activeTaperScenario =
    scienceData?.taper_simulation?.scenarios?.find((s: any) => s.key === activeTaperKey) ||
    scienceData?.taper_simulation?.scenarios?.[0] ||
    null;

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Coach / Mentor Inspection Banner */}
        {isInspectingOther && (
          <div className="flex flex-wrap items-center justify-between gap-4 bg-gradient-to-r from-emerald-500/15 via-cyan-500/10 to-transparent border border-emerald-500/35 rounded-2xl px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-extrabold">
                🔍 教练 / 师傅跨视角调阅
              </span>
              <div>
                <div className="text-sm sm:text-base font-bold text-white">
                  正在查看：{scienceData?.student_profile?.display_name || "跑团成员"}
                  {scienceData?.student_profile?.class_name && (
                    <span className="text-xs text-zinc-400 font-normal ml-2">
                      ({scienceData.student_profile.class_name})
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-400">
                  展示该队员的有效 VDOT、耐力保持系数、Canova 五维矩阵、30 天生理恢复与赛前减量推演
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                if (typeof window !== "undefined" && window.history.length > 1) {
                  window.history.back();
                } else {
                  window.location.href = "/dashboard/team";
                }
              }}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-xs font-bold text-white transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              返回跑团与教练工作台
            </button>
          </div>
        )}

        {isInspectingOther ? (
          <h1 className="text-2xl font-black tracking-tight">
            {scienceData?.basic_status_only ? "跑友基本状态名片" : "身体数据与跑力"}
          </h1>
        ) : (
          /* 与小程序「训练」页一致的三段切换：课表 / 诊断 / 身体数据与跑力 */
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-black">训练</h1>
            <TrainingTabSwitcher active="analysis" />
          </div>
        )}

        {scienceData?.basic_status_only ? (
          <div className="bg-[#121215] border border-cyan-500/35 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <img
                  src={
                    scienceData?.basic_status?.avatar_url ||
                    scienceData?.student_profile?.avatar_url ||
                    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                  }
                  alt={scienceData?.basic_status?.display_name || "跑友"}
                  className="w-16 h-16 rounded-full object-cover border-2 border-cyan-500/40"
                />
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-xl font-black text-white">
                      {scienceData?.basic_status?.display_name || scienceData?.student_profile?.display_name || "跑友"}
                    </h2>
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                      {(scienceData?.basic_status?.club_names || []).length > 0
                        ? `所属跑团：${scienceData.basic_status.club_names.join(" / ")}`
                        : "🌍 自由跑友（暂未入团）"}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1">
                    ⏰ 注册时间：{scienceData?.basic_status?.joined_at_display || "近期"}
                  </p>
                </div>
              </div>
              <span className="px-3 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 text-xs font-bold">
                🔒 跨跑团 / 未入团隐私保护模式
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div
                className={`p-4 rounded-2xl border ${
                  scienceData?.basic_status?.watch_bound
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-amber-500/10 border-amber-500/30"
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400 font-bold">⌚ 手表绑定</span>
                  <span
                    className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                      scienceData?.basic_status?.watch_bound
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-amber-500/20 text-amber-300"
                    }`}
                  >
                    {scienceData?.basic_status?.watch_bound ? "已绑定" : "未绑定"}
                  </span>
                </div>
                <div className="text-sm font-black text-white mt-2">
                  {scienceData?.basic_status?.watch_bound_label || "未绑定"}
                </div>
                <div className="text-[11px] text-zinc-400 mt-1">
                  {scienceData?.basic_status?.watch_status_detail || "尚未绑定运动手表"}
                </div>
              </div>

              <div
                className={`p-4 rounded-2xl border ${
                  scienceData?.basic_status?.goal_configured
                    ? "bg-emerald-500/10 border-emerald-500/30"
                    : "bg-amber-500/10 border-amber-500/30"
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400 font-bold">🎯 目标设定</span>
                  <span
                    className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                      scienceData?.basic_status?.goal_configured
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-amber-500/20 text-amber-300"
                    }`}
                  >
                    {scienceData?.basic_status?.goal_configured_label || "默认目标"}
                  </span>
                </div>
                <div className="text-sm font-black text-white mt-2">
                  月目标 {scienceData?.basic_status?.target_km ?? 100} km
                </div>
                <div className="text-[11px] text-zinc-400 mt-1">
                  {scienceData?.basic_status?.goal_status_detail || "周 50km · 月 100km"}
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#18181c] border border-white/10">
                <span className="text-xs text-zinc-400 font-bold block">📊 本月跑量进度</span>
                <div className="text-xl font-black text-white font-mono mt-2">
                  {scienceData?.basic_status?.month_km ?? 0} / {scienceData?.basic_status?.target_km ?? 100} km
                </div>
                <div className="text-[11px] text-zinc-400 mt-1">
                  完成度 {scienceData?.basic_status?.completion_rate ?? 0}% · 累计打卡{" "}
                  {scienceData?.basic_status?.month_run_count ?? 0} 次
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-[#18181c] border border-white/10">
                <span className="text-xs text-zinc-400 font-bold block">⚡ 有效跑力 (VDOT)</span>
                <div className="text-xl font-black text-[#FC4C02] font-mono mt-2">
                  {scienceData?.vdot ?? "—"}
                </div>
                <div className="text-[11px] text-zinc-400 mt-1">
                  手表 VO2Max: {scienceData?.vo2max ?? "—"}
                </div>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-cyan-500/10 border border-cyan-500/25 text-xs text-cyan-200 leading-relaxed">
              🔒 <strong>跨跑团 / 自由跑友隐私说明：</strong>
              {scienceData?.privacy_notice ||
                "不在同一个跑团的用户之间仅可互相查看基本状态（手表绑定、目标设定、月跑量进度与跑力等级），不能相互查看具体单次运动记录、配速分段、GPS轨迹与详细生理恢复曲线。"}
            </div>
          </div>
        ) : (
          <>
        {/* ── CARD 1: 有效 VDOT + 耐力保持特征 + Canova 五维矩阵 ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left 5 cols: Effective VDOT & Race Predictions */}
          <div className="lg:col-span-5 bg-[#121215] border border-[#FC4C02]/30 rounded-3xl p-6 flex flex-col justify-between shadow-2xl space-y-6">
            <div>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[#FC4C02] text-xs font-bold uppercase tracking-wider">
                  <Zap className="w-4 h-4" />
                  有效 VDOT (心率配速效率)
                </div>
                {scienceData?.canova_matrix?.runner_type_label && (
                  <span className="px-2.5 py-1 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-xs font-bold">
                    🧬 {scienceData.canova_matrix.runner_type_label}
                  </span>
                )}
              </div>

              <div className="flex flex-wrap items-baseline gap-4 mt-3">
                <div className="text-5xl font-black text-white font-mono">
                  {scienceData?.vdot ?? "—"}
                </div>
                {(scienceData?.canova_matrix?.watch_vo2max || scienceData?.vo2max) && (
                  <div className="text-xs text-zinc-400">
                    手表 VO2Max:{" "}
                    <span className="text-sky-400 font-bold font-mono">
                      {scienceData?.canova_matrix?.watch_vo2max ?? scienceData?.vo2max}
                    </span>
                  </div>
                )}
                {scienceData?.canova_matrix?.endurance_retention_ratio && (
                  <div className="text-xs text-zinc-400">
                    耐力保持系数:{" "}
                    <span className="text-amber-400 font-bold font-mono">
                      {scienceData.canova_matrix.endurance_retention_ratio}
                    </span>
                  </div>
                )}
              </div>

              {scienceData?.canova_matrix?.recovery_phase_label && (
                <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500/15 border border-amber-500/35 text-amber-300 text-xs font-bold">
                  {scienceData.canova_matrix.recovery_phase_label}
                </div>
              )}

              {scienceData?.canova_matrix?.canova_one_line_summary ? (
                <div className="mt-4 p-3.5 rounded-2xl bg-white/[0.03] border-l-4 border-[#FC4C02] text-xs text-zinc-200 leading-relaxed">
                  💡 {scienceData.canova_matrix.canova_one_line_summary}
                </div>
              ) : (
                <p className="text-xs text-zinc-400 mt-2">
                  结合坡度修正距离 (Grade-Adjusted Distance) 与储备心率百分比 (%HRR) 推算的真实有氧跑力。
                </p>
              )}
            </div>

            {/* Race Predictions Grid */}
            <div className="pt-4 border-t border-white/10">
              <div className="flex items-center gap-2 text-xs font-bold text-zinc-300 mb-3">
                <Trophy className="w-4 h-4 text-amber-400" />
                各距离专项成绩预测 (含耐力衰减修正)
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                  <span className="text-[11px] text-zinc-500 block">5 公里</span>
                  <span className="text-base font-black text-white font-mono mt-0.5 block">
                    {scienceData?.race_predictions?.five_k || "—"}
                  </span>
                </div>
                <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                  <span className="text-[11px] text-zinc-500 block">10 公里</span>
                  <span className="text-base font-black text-white font-mono mt-0.5 block">
                    {scienceData?.race_predictions?.ten_k || "—"}
                  </span>
                </div>
                <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                  <span className="text-[11px] text-zinc-500 block">半程马拉松</span>
                  <span className="text-base font-black text-[#FC4C02] font-mono mt-0.5 block">
                    {scienceData?.race_predictions?.half_marathon || "—"}
                  </span>
                </div>
                <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                  <span className="text-[11px] text-zinc-500 block">全程马拉松</span>
                  <span className="text-base font-black text-rose-400 font-mono mt-0.5 block">
                    {scienceData?.race_predictions?.marathon || "—"}
                  </span>
                </div>
              </div>
              {scienceData?.race_predictions?.endurance_note && (
                <p className="text-[11px] text-zinc-400 mt-2.5 leading-relaxed">
                  {scienceData.race_predictions.endurance_note}
                </p>
              )}
            </div>
          </div>

          {/* Right 7 cols: Canova 5-Dimension Matrix */}
          <div className="lg:col-span-7 bg-[#121215] border border-white/[0.08] rounded-3xl p-6 shadow-2xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Compass className="w-5 h-5 text-amber-400" />
                  <h2 className="text-base sm:text-lg font-bold text-white">
                    Canova 专项五维能力矩阵
                  </h2>
                </div>
                <span className="px-3 py-1 rounded-full bg-amber-500/15 text-amber-300 text-xs font-extrabold">
                  综合评分 {scienceData?.canova_matrix?.overall_score ?? "—"} / 100
                </span>
              </div>

              <div className="space-y-4">
                {(scienceData?.canova_matrix?.dimensions || []).map((dim: any) => (
                  <div key={dim.key} className="bg-[#18181c] border border-white/5 rounded-2xl p-3.5">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-bold text-white">{dim.label}</span>
                      <span className="font-mono text-zinc-300">
                        {dim.display_value} · <strong className="text-amber-400">{dim.score}分</strong>
                      </span>
                    </div>
                    <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden mb-1.5">
                      <div
                        className="h-full bg-gradient-to-r from-[#FC4C02] to-amber-400 rounded-full transition-all"
                        style={{ width: `${Math.min(100, Math.max(8, dim.score || 0))}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-zinc-400">{dim.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── CARD 1.5: 马拉松官方配速员（官兔）六维胜任度评估 ── */}
        {activeRunnerUid && (
          <PacerEvaluationCard uid={activeRunnerUid} viewerUid={user?.id} />
        )}

        {/* ── CARD 2: 赛前 7 天减量 (Taper) 状态推演模拟器 ── */}
        {scienceData?.taper_simulation?.scenarios?.length > 0 && (
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Flame className="w-5 h-5 text-emerald-400" />
                  <h2 className="text-lg sm:text-xl font-bold text-white">
                    赛前 7 天减量 (Taper) 状态推演模拟器
                  </h2>
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 text-xs font-bold">
                    推荐：{scienceData.taper_simulation.recommended_strategy_label}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  {scienceData.taper_simulation.recommendation_summary}
                </p>
              </div>
              <div className="text-xs text-zinc-400 font-mono">
                当前基线：CTL {scienceData.taper_simulation.current_ctl} · ATL {scienceData.taper_simulation.current_atl} · TSB{" "}
                <strong className="text-white">
                  {scienceData.taper_simulation.current_tsb > 0
                    ? `+${scienceData.taper_simulation.current_tsb}`
                    : scienceData.taper_simulation.current_tsb}
                </strong>
              </div>
            </div>

            {/* 3 Scenario Selector Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {scienceData.taper_simulation.scenarios.map((sc: any) => {
                const isSelected = sc.key === activeTaperScenario?.key;
                const isRec = sc.key === scienceData.taper_simulation.recommended_strategy;
                return (
                  <button
                    key={sc.key}
                    onClick={() => setActiveTaperKey(sc.key)}
                    className={`text-left p-4 rounded-2xl border transition ${
                      isSelected
                        ? "bg-emerald-500/10 border-emerald-500/50 shadow-lg"
                        : "bg-[#18181c] border-white/5 hover:border-white/15"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-bold text-white">{sc.label}</span>
                      {isRec && (
                        <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px] font-bold">
                          最佳匹配
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400 mb-3">
                      {sc.subtitle} · 预计日均 TRIMP {sc.daily_trimp}
                    </p>
                    <div className="flex items-center justify-between pt-2 border-t border-white/5 text-xs font-mono">
                      <span className="text-zinc-400">7天后比赛日 TSB:</span>
                      <span className={sc.projected_day7_tsb >= 5 ? "text-emerald-400 font-bold" : "text-cyan-400 font-bold"}>
                        {sc.projected_day7_tsb > 0 ? `+${sc.projected_day7_tsb}` : sc.projected_day7_tsb} ({sc.readiness_label})
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* 7-Day Projected TSB & CTL/ATL Curve */}
            {activeTaperScenario?.days?.length > 0 && (
              <div className="h-[220px] w-full pt-2">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsLine data={activeTaperScenario.days} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="#1f1f24" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="date_label" stroke="#71717a" fontSize={11} tickLine={false} />
                    <YAxis stroke="#71717a" width={40} fontSize={11} tickLine={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#16161a",
                        borderColor: "rgba(255,255,255,0.15)",
                        borderRadius: "14px",
                        fontSize: "12px",
                      }}
                    />
                    <Line type="monotone" dataKey="tsb" name="预测状态 TSB" stroke="#10b981" strokeWidth={2.5} dot={{ r: 4 }} />
                    <Line type="monotone" dataKey="ctl" name="预测体能 CTL" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="atl" name="预测疲劳 ATL" stroke="#f43f5e" strokeWidth={2} dot={{ r: 3 }} />
                  </RechartsLine>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {/* ── CARD 3: 生理恢复与健康历史趋势 (30天双图表) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-8">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="text-xl">📊</span>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                生理恢复与健康历史趋势 (30天)
              </h2>
            </div>
            <p className="text-xs text-zinc-400 mt-1">
              对比夜间 HRV、静息心率 (RHR) 与睡眠质量波动
            </p>
          </div>

          {scienceData?.biometrics_confidential ? (
            <div className="py-12 text-center space-y-2 bg-[#18181c] rounded-2xl border border-white/5">
              <ShieldAlert className="w-8 h-8 text-amber-400 mx-auto" />
              <div className="text-sm font-bold text-white">该队员已将生理恢复数据设为保密</div>
              <p className="text-xs text-zinc-400">
                HRV、静息心率与睡眠恢复详情仅对跑者本人、跑团认证教练及结对师傅开放。
              </p>
            </div>
          ) : (
            <>
              {/* Sub-Chart 1: HRV vs RHR (Dual Y-Axis) */}
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
                  <Heart className="w-4 h-4 text-rose-500" />
                  <span>夜间 HRV (ms) 与 静息心率 RHR (bpm) 趋势图</span>
                </div>

                <div className="h-[240px] sm:h-[280px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsLine data={healthTrend} syncId="healthTrendSync" margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="#1f1f24" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="date_label" stroke="#666" fontSize={11} tickLine={false} />
                      <YAxis
                        yAxisId="left"
                        stroke="#ef4444"
                        width={42}
                        fontSize={11}
                        tickLine={false}
                        domain={["dataMin - 3", "dataMax + 3"]}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        stroke="#06b6d4"
                        width={42}
                        fontSize={11}
                        tickLine={false}
                        domain={["dataMin - 5", "dataMax + 5"]}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#16161a",
                          borderColor: "rgba(255,255,255,0.15)",
                          borderRadius: "14px",
                          fontSize: "12px",
                        }}
                        formatter={(val: any, name: any) => {
                          if (name === "resting_heart_rate") return [val != null ? `${val} bpm` : "—", "静息心率 (RHR)"];
                          if (name === "hrv") return [val != null ? `${val} ms` : "—", "夜间 HRV"];
                          return [val, name];
                        }}
                      />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="resting_heart_rate"
                        name="resting_heart_rate"
                        stroke="#ef4444"
                        strokeWidth={2}
                        dot={{ r: 3, fill: "#ef4444" }}
                        activeDot={{ r: 5 }}
                        connectNulls={true}
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="hrv"
                        name="hrv"
                        stroke="#06b6d4"
                        strokeWidth={2}
                        dot={{ r: 3, fill: "#06b6d4" }}
                        activeDot={{ r: 5 }}
                        connectNulls={true}
                      />
                    </RechartsLine>
                  </ResponsiveContainer>
                </div>

                <div className="flex items-center justify-center gap-6 text-xs text-zinc-400">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#06b6d4]" />
                    <span className="text-cyan-400">夜间 HRV (ms)</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444]" />
                    <span className="text-rose-400">静息心率 (RHR bpm)</span>
                  </div>
                </div>
              </div>

              {/* Sub-Chart 2: Body Battery vs Sleep Score (0-100 Dual Line) */}
              <div className="space-y-3 pt-6 border-t border-white/5">
                <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
                  <BatteryCharging className="w-4 h-4 text-amber-400" />
                  <span>身体电量 (%) 与 睡眠质量得分</span>
                </div>

                <div className="h-[240px] sm:h-[280px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsLine data={healthTrend} syncId="healthTrendSync" margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="#1f1f24" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="date_label" stroke="#666" fontSize={11} tickLine={false} />
                      <YAxis
                        yAxisId="left"
                        stroke="#818cf8"
                        width={42}
                        fontSize={11}
                        tickLine={false}
                        domain={[0, 100]}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        stroke="#eab308"
                        width={42}
                        fontSize={11}
                        tickLine={false}
                        domain={[0, 100]}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#16161a",
                          borderColor: "rgba(255,255,255,0.15)",
                          borderRadius: "14px",
                          fontSize: "12px",
                        }}
                        formatter={(val: any, name: any) => {
                          if (name === "sleep_score") return [val != null ? `${val} 分` : "—", "睡眠得分"];
                          if (name === "body_battery") return [val != null ? `${val} %` : "—", "身体电量 Max"];
                          return [val, name];
                        }}
                      />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="sleep_score"
                        name="sleep_score"
                        stroke="#818cf8"
                        strokeWidth={2}
                        dot={{ r: 3, fill: "#818cf8" }}
                        activeDot={{ r: 5 }}
                        connectNulls={true}
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="body_battery"
                        name="body_battery"
                        stroke="#eab308"
                        strokeWidth={2}
                        dot={{ r: 3, fill: "#eab308" }}
                        activeDot={{ r: 5 }}
                        connectNulls={true}
                      />
                    </RechartsLine>
                  </ResponsiveContainer>
                </div>

                <div className="flex items-center justify-center gap-6 text-xs text-zinc-400">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#818cf8]" />
                    <span className="text-indigo-300">睡眠得分</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-[#eab308]" />
                    <span className="text-amber-300">身体电量 Max (%)</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* ── CARD 4: Renato Canova 配速矩阵 (默认折叠，按需展开) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div
            className="flex items-center justify-between cursor-pointer"
            onClick={() => setShowCanovaZones(!showCanovaZones)}
          >
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                Renato Canova 马拉松专项配速矩阵 (Pace Zones)
              </h2>
              <p className="text-xs text-zinc-400 mt-1">
                基于当前有效 VDOT 动态推算的个性化训练配速区间
              </p>
            </div>
            <span className="px-3.5 py-1.5 rounded-full bg-[#FC4C02]/15 text-[#FC4C02] text-xs font-bold">
              {showCanovaZones ? "收起配速表 ▴" : "展开配速表 ▾"}
            </span>
          </div>

          {showCanovaZones && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
              {scienceData?.canova_zones &&
                Object.entries(scienceData.canova_zones).map(([key, zone]: [string, any]) => (
                  <div key={key} className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
                    <div>
                      <span className="text-xs font-bold text-amber-400 block mb-1">
                        {zone.name}
                      </span>
                      <span className="text-xl font-black text-white block my-2 font-mono">
                        {zone.range}
                      </span>
                      <p className="text-xs text-zinc-400 leading-relaxed">{zone.desc}</p>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
          </>
        )}
      </main>
    </div>
  );
}
