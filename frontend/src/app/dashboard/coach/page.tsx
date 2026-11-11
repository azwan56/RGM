"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import TrainingPlanView from "@/components/TrainingPlanView";
import TrainingTabSwitcher from "@/components/TrainingTabSwitcher";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import { showToast } from "@/components/ui/UiFeedbackProvider";
import {
  Zap,
  Sparkles,
  Target,
  RefreshCw,
  CheckCircle2,
  ShieldAlert,
  Trophy,
  Flame,
  Mountain,
  Timer,
  Activity,
  User,
  Heart,
  Calendar,
  AlertTriangle
} from "lucide-react";

export default function CoachPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"plan" | "report">("plan");
  const [analysis, setAnalysis] = useState<any>(null);
  const [targetRace, setTargetRace] = useState("武功山 50K");
  const [targetTime, setTargetTime] = useState("8:00:00");
  const [raceType, setRaceType] = useState("trail");
  const [userRaces, setUserRaces] = useState<any[]>([]);
  const [updatingPriority, setUpdatingPriority] = useState<string | null>(null);
  const [isCoachOrOwner, setIsCoachOrOwner] = useState(false);
  const [showRaceSetup, setShowRaceSetup] = useState(false);

  // 支持 ?tab=report 深链（与「训练」三段切换器联动）
  useEffect(() => {
    if (typeof window === "undefined") return;
    const t = new URLSearchParams(window.location.search).get("tab");
    if (t === "report" || t === "plan") setActiveTab(t);
  }, []);

  function switchTab(k: "plan" | "report") {
    setActiveTab(k);
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `/dashboard/coach?tab=${k}`);
    }
  }

  const racePresets = [
    { label: "🏔️ 武功山 50K (越野)", race: "武功山 50K", time: "8:00:00", type: "trail" },
    { label: "🏅 无锡马拉松 (全马)", race: "无锡马拉松", time: "3:15:00", type: "marathon" },
    { label: "⚡ 上海半马 (半马)", race: "上海半程马拉松", time: "1:35:00", type: "half" },
    { label: "🏃 10K 速度突破", race: "日常 10公里 突破", time: "42:00", type: "10k" },
  ];

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadLatestAnalysis(u.id);
        if (u.is_coach_or_owner || u.is_admin || u.id === "admin" || u.id === "super_admin") {
          setIsCoachOrOwner(true);
        } else {
          apiClient.get(`/api/team/my-clubs/${encodeURIComponent(u.id)}`).then((res) => {
            const clubs = res.data?.clubs || [];
            setIsCoachOrOwner(
              clubs.some((c: any) => c.role === "owner" || c.role === "coach" || c.role === "admin")
            );
          }).catch(() => {});
        }
      } else {
        router.push("/login");
      }
    });
  }, [router]);

  function getRecommendedTargetRace(races: any[]): any | null {
    if (!races || races.length === 0) return null;
    const upcomingRaces = races.filter(
      (r) => r.status !== "completed" && !r.is_completed && !r.is_past
    );
    const candidates = upcomingRaces.length > 0 ? upcomingRaces : races;
    const aRace = candidates.find(
      (r) => r.priority === 1 || r.priority === "A" || r.priority === "1"
    );
    if (aRace) return aRace;
    const bRace = candidates.find(
      (r) => r.priority === 2 || r.priority === "B" || r.priority === "2"
    );
    if (bRace) return bRace;
    return candidates[0] || races[0];
  }

  async function loadLatestAnalysis(uid: string) {
    try {
      // 1. Fetch user registered race plans
      let realRaces: any[] = [];
      try {
        const rRes = await apiClient.get(`/api/profile/${uid}/races`);
        if (rRes.data?.races) {
          realRaces = rRes.data.races;
          setUserRaces(realRaces);
        }
      } catch (err) {
        console.warn("User races fetch error:", err);
      }

      const recRace = getRecommendedTargetRace(realRaces);

      // 2. Fetch coach report
      const res = await apiClient.get(`/api/coach/latest/${uid}`);
      if (res.data && res.data.summary) {
        setAnalysis(res.data);
        const savedTarget = res.data.athlete_snapshot?.target_race;
        const savedRaceObj = realRaces.find((r) => r.name === savedTarget);
        const isSavedTargetCompleted =
          savedRaceObj &&
          (savedRaceObj.status === "completed" ||
            savedRaceObj.is_completed ||
            savedRaceObj.is_past);

        // If saved target is already finished, automatically advance to upcoming A-race!
        if (savedTarget && !isSavedTargetCompleted) {
          setTargetRace(savedTarget);
        } else if (recRace) {
          setTargetRace(recRace.name);
          if (recRace.target_time) setTargetTime(recRace.target_time);
          if (recRace.race_type) setRaceType(recRace.race_type);
        }

        if (res.data.athlete_snapshot?.target_time && !isSavedTargetCompleted) {
          setTargetTime(res.data.athlete_snapshot.target_time);
        }
        if (res.data.athlete_snapshot?.race_category && !isSavedTargetCompleted) {
          setRaceType(res.data.athlete_snapshot.race_category);
        }
      } else if (recRace) {
        setTargetRace(recRace.name);
        if (recRace.target_time) setTargetTime(recRace.target_time);
        if (recRace.race_type) setRaceType(recRace.race_type);
      }
    } catch (e) {
      console.error("Latest coach report fetch error:", e);
    }
  }

  async function handleUpdateRacePriority(raceIdOrName: string, priority: "A" | "B" | "C") {
    if (!user?.id) return;
    setUpdatingPriority(raceIdOrName);
    try {
      const res = await apiClient.post("/api/coach/race-priority", {
        uid: user.id,
        race_id: raceIdOrName,
        priority,
      });
      if (res.data?.success) {
        setAnalysis((prev: any) => ({
          ...prev,
          multi_race_analysis: res.data.multi_race_analysis,
          multi_race_strategy: res.data.multi_race_strategy,
        }));
        if (res.data.races) {
          setUserRaces(res.data.races);
        }
      }
    } catch (e: any) {
      console.error("Failed to update race priority:", e);
      showToast("调整赛事定位失败: " + (e.response?.data?.detail || e.message));
    } finally {
      setUpdatingPriority(null);
    }
  }

  async function handleGenerateAnalysis() {
    if (!user?.id) return;
    setLoading(true);
    try {
      const res = await apiClient.post("/api/coach/analysis", {
        uid: user.id,
        target_race: targetRace,
        target_time: targetTime,
        race_type: raceType,
      });
      if (res.data) {
        setAnalysis(res.data);
      }
    } catch (e) {
      console.error("Coach generation failed:", e);
      showToast("AI 分析生成提示: 正在使用最近一次训练诊断缓存");
    } finally {
      setLoading(false);
    }
  }

  const tsb = analysis?.tsb_metrics?.tsb ?? 0;
  const ctl = analysis?.tsb_metrics?.ctl ?? 0;
  const atl = analysis?.tsb_metrics?.atl ?? 0;
  const statusLabel = analysis?.tsb_metrics?.status ?? "平衡稳健";
  const riskWarning = analysis?.tsb_metrics?.risk_warning;
  const athlete = analysis?.athlete_snapshot;
  const zones = analysis?.race_zones;

  const getTsbColor = (val: number) => {
    if (val > 15) return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
    if (val >= -10) return "text-cyan-400 border-cyan-500/30 bg-cyan-500/10";
    if (val >= -30) return "text-purple-400 border-purple-500/30 bg-purple-500/10";
    if (val >= -45) return "text-amber-400 border-amber-500/30 bg-amber-500/10";
    return "text-red-400 border-red-500/30 bg-red-500/10";
  };

  const formatAdviceContent = (content: any): string => {
    if (!content) return "";
    if (typeof content === "string") return content;
    if (typeof content === "object") {
      return Object.entries(content)
        .map(([k, v]) => `【${k}】${typeof v === "object" ? JSON.stringify(v) : v}`)
        .join("\n");
    }
    return String(content);
  };

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Title Header — 与小程序「训练」页一致：标题 + 三段切换 */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-black">训练</h1>
            <TrainingTabSwitcher active={activeTab} onChange={(k) => k !== "analysis" && switchTab(k)} />
          </div>
          {isCoachOrOwner && (
            <button
              onClick={() => router.push("/dashboard/team-coach")}
              className="self-start md:self-auto flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 text-amber-300 text-xs font-bold transition"
            >
              🧢 跑团教练工作台 ›
            </button>
          )}
        </div>

        {activeTab === "plan" ? (
          <TrainingPlanView
            user={user}
            userRaces={userRaces}
            initialTargetRace={targetRace}
            initialTargetTime={targetTime}
          />
        ) : (
          <>
            {/* 紧凑备赛摘要条（原「跑者档案 + 目标赛事」双大卡收纳为一行 + 可展开抽屉） */}
            <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-4 sm:p-5 space-y-3">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                <div className="flex items-center gap-2 flex-wrap text-xs">
                  <span className="text-sm font-bold text-white">🎯 {targetRace || "未设定目标赛事"}</span>
                  {targetTime && <span className="text-zinc-400">目标 {targetTime}</span>}
                  <span className={`font-bold px-2 py-0.5 rounded-full border ${getTsbColor(tsb)}`}>{statusLabel}</span>
                  <span className="text-zinc-500">
                    体能 <b className="text-cyan-400">{ctl}</b> · 疲劳 <b className="text-amber-400">{atl}</b> · 状态{" "}
                    <b className={tsb >= 0 ? "text-emerald-400" : "text-purple-400"}>{tsb > 0 ? `+${tsb}` : tsb}</b>
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => setShowRaceSetup(!showRaceSetup)}
                    className="px-3 py-2 rounded-xl text-xs font-semibold bg-[#18181c] border border-white/10 hover:border-white/20 text-zinc-300 transition"
                  >
                    ⚙️ 切换目标赛事 {showRaceSetup ? "▴" : "▾"}
                  </button>
                  <button
                    onClick={handleGenerateAnalysis}
                    disabled={loading}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition active:scale-95 disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                    {loading ? "推理中..." : analysis ? "重新诊断" : "启动诊断"}
                  </button>
                </div>
              </div>

              {riskWarning && (
                <div className="p-2.5 bg-red-950/40 border border-red-500/30 rounded-xl flex items-start gap-2 text-xs text-red-200">
                  <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                  <span className="leading-snug">{riskWarning}</span>
                </div>
              )}

              {showRaceSetup && (
                <div className="pt-3 border-t border-white/5 space-y-3">
            {/* User Registered Races Quick Selector */}
            {userRaces.length > 0 && (
              <div className="space-y-1.5 pb-3 border-b border-white/5">
                <div className="text-[11px] text-zinc-400 font-bold flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-purple-300">
                    <span>🚩</span> 您已登记的备赛日程（点击切换当前分析主目标）：
                  </span>
                  <span className="text-[10px] text-zinc-500 font-normal">
                    共 {userRaces.length} 场
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {userRaces.map((r: any) => {
                    const isSelected = targetRace === r.name;
                    const rawPri = String(r.priority || 1).toUpperCase();
                    const tier = (rawPri === "2" || rawPri === "B") ? "B" : ((rawPri === "3" || rawPri === "C") ? "C" : "A");
                    const tierBadgeClass = tier === "A"
                      ? "bg-rose-500/20 text-rose-300 border-rose-500/30"
                      : tier === "B"
                      ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/30"
                      : "bg-zinc-800 text-zinc-300 border-zinc-700";

                    return (
                      <button
                        key={r.id || r.name}
                        onClick={() => {
                          setTargetRace(r.name);
                          if (r.target_time) setTargetTime(r.target_time);
                          if (r.race_type) {
                            const rt = String(r.race_type).toLowerCase();
                            if (rt.includes("越野") || rt.includes("trail") || rt.includes("50k") || rt.includes("100k") || rt.includes("160")) {
                              setRaceType("trail");
                            } else if (rt.includes("半")) {
                              setRaceType("half");
                            } else if (rt.includes("10")) {
                              setRaceType("10k");
                            } else if (rt.includes("5")) {
                              setRaceType("5k");
                            } else {
                              setRaceType("marathon");
                            }
                          }
                        }}
                        className={`text-xs px-3 py-1.5 rounded-xl border transition-all flex items-center gap-2 ${
                          isSelected
                            ? "bg-purple-600 border-purple-500 text-white font-bold shadow-lg shadow-purple-600/30 ring-2 ring-purple-400"
                            : "bg-[#18181c] border-white/10 text-zinc-300 hover:border-purple-500/50 hover:text-white"
                        }`}
                      >
                        <span>{r.race_type?.includes("越野") ? "🏔️" : "🏅"}</span>
                        <span>{r.name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${tierBadgeClass}`}>
                          {tier} 标
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div>
                <label className="text-[11px] text-zinc-400 block mb-1">目标赛事名称</label>
                <input
                  type="text"
                  value={targetRace}
                  onChange={(e) => {
                    const val = e.target.value;
                    setTargetRace(val);
                    const lower = val.toLowerCase();
                    if (lower.includes("越野") || lower.includes("trail") || lower.includes("ultra") || lower.includes("50k") || lower.includes("100k") || lower.includes("武功山") || lower.includes("崇礼") || lower.includes("柴古") || lower.includes("utmb") || lower.includes("160")) {
                      setRaceType("trail");
                    } else if (lower.includes("半马") || lower.includes("半程") || lower.includes("half")) {
                      setRaceType("half");
                    } else if (lower.includes("10k") || lower.includes("10公里")) {
                      setRaceType("10k");
                    } else if (lower.includes("5k") || lower.includes("5公里")) {
                      setRaceType("5k");
                    } else if (lower.includes("马拉松") || lower.includes("全马") || lower.includes("全程") || lower.includes("marathon")) {
                      setRaceType("marathon");
                    }
                  }}
                  placeholder="例如: 武功山 50K / 无锡马拉松 / 上海马拉松"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="text-[11px] text-zinc-400 block mb-1">专项赛事类型</label>
                <select
                  value={raceType}
                  onChange={(e) => setRaceType(e.target.value)}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500"
                >
                  <option value="trail">越野超马 (山地爬升 D+ / 时间负荷)</option>
                  <option value="marathon">全程马拉松 (100% MP 配速收敛)</option>
                  <option value="half">半程马拉松 (LT2 乳酸门槛巡航)</option>
                  <option value="10k">10公里场地/路跑 (VO2max 峰值刺激)</option>
                  <option value="5k">5公里竞速 (乳酸耐受极限)</option>
                </select>
              </div>

              <div>
                <label className="text-[11px] text-zinc-400 block mb-1">目标完赛成绩 (HH:MM:SS)</label>
                <input
                  type="text"
                  value={targetTime}
                  onChange={(e) => setTargetTime(e.target.value)}
                  placeholder="例如: 8:00:00 或 3:15:00"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>
                </div>
              )}
            </div>

        {/* Coach Analysis Result Display */}
        {analysis ? (
          <div className="space-y-6">
            {/* Summary Hero Card */}
            <div className="bg-gradient-to-br from-purple-900/30 via-[#121215] to-[#16161a] border border-purple-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl">
              <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-purple-500/20 text-purple-300 text-xs font-bold mb-4 border border-purple-500/30">
                <Sparkles className="w-3.5 h-3.5" />
                当前训练阶段：{analysis.periodization_phase || "专项准备期"}
              </div>
              <h2 className="text-xl sm:text-2xl font-black text-white mb-3">
                {analysis.summary}
              </h2>
              <p className="text-sm text-zinc-300 leading-relaxed font-light">
                {analysis.fitness_status}
              </p>
            </div>

            {/* Canova Multi-Race Strategic Periodization Roadmap */}
            {analysis.multi_race_strategy && (
              <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-4">
                  <div>
                    <h3 className="text-base font-black text-white flex items-center gap-2">
                      <Calendar className="w-5 h-5 text-purple-400" />
                      Canova 多赛事宏观统筹与战术推演 (Multi-Race Strategy)
                    </h3>
                    <p className="text-xs text-zinc-400 mt-1">
                      A/B/C 梯队科学分级 · 规避过密疲劳冲突 · 黄金以赛代练配对 · 跨赛道专项切换
                    </p>
                  </div>
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-semibold">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    共统筹 {(analysis.multi_race_strategy.race_timeline_advice || []).length} 场目标赛事
                  </div>
                </div>

                {/* Macrocycle Overview */}
                <div className="p-4 rounded-2xl bg-gradient-to-r from-purple-950/40 via-[#18181c] to-indigo-950/30 border border-purple-500/20">
                  <div className="text-xs font-bold text-purple-300 mb-1 flex items-center gap-1.5">
                    <span>🏆</span> 赛季宏观周期统筹：
                  </div>
                  <div className="text-xs sm:text-sm text-zinc-200 leading-relaxed font-normal">
                    {analysis.multi_race_strategy.macro_cycle_overview}
                  </div>
                </div>

                {/* Race Timeline Cards */}
                <div className="space-y-3">
                  <div className="text-xs font-bold text-zinc-400 tracking-wider uppercase">
                    赛事日历与专项执行规程
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    {(analysis.multi_race_strategy.race_timeline_advice || []).map((r: any, idx: number) => {
                      const isA = r.tier === "A";
                      const isB = r.tier === "B";
                      const tierBadgeClass = isA
                        ? "bg-rose-500/20 border-rose-500/40 text-rose-300"
                        : isB
                        ? "bg-cyan-500/20 border-cyan-500/40 text-cyan-300"
                        : "bg-zinc-800 border-zinc-700 text-zinc-300";

                      return (
                        <div
                          key={idx}
                          className={`p-4 sm:p-5 rounded-2xl border transition-all ${
                            isA
                              ? "bg-[#18181f] border-rose-500/30 shadow-lg shadow-rose-950/10"
                              : isB
                              ? "bg-[#16181d] border-cyan-500/20"
                              : "bg-[#18181c] border-white/5"
                          }`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3 pb-3 border-b border-white/5">
                            <div className="flex items-center gap-2.5 flex-wrap">
                              <span className={`text-[11px] font-black px-2.5 py-0.5 rounded-full border ${tierBadgeClass}`}>
                                {r.tactical_role || `${r.tier} 标`}
                              </span>
                              <span className="text-sm sm:text-base font-black text-white">
                                {r.race_name}
                              </span>
                              {r.days_left !== undefined && (
                                <span className="text-xs text-zinc-400 font-medium">
                                  倒计时 <strong className="text-purple-300 font-bold">{r.days_left}</strong> 天
                                </span>
                              )}
                            </div>

                            {/* Interactive A/B/C Priority Switcher */}
                            <div className="flex items-center gap-2 flex-wrap">
                              <div className="flex items-center gap-1 bg-[#121215] p-1 rounded-xl border border-white/5">
                                <span className="text-[10px] text-zinc-500 font-bold px-1">调整级别:</span>
                                <button
                                  type="button"
                                  disabled={updatingPriority === (r.id || r.race_name)}
                                  onClick={() => handleUpdateRacePriority(r.id || r.race_name, "A")}
                                  className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${
                                    r.tier === "A"
                                      ? "bg-rose-500 text-white shadow-sm shadow-rose-500/50 ring-1 ring-rose-300"
                                      : "text-zinc-400 hover:text-white hover:bg-white/5"
                                  }`}
                                  title="A 标：核心目标之战，安排最高优先级与深度赛前减量"
                                >
                                  A 标 (核心)
                                </button>
                                <button
                                  type="button"
                                  disabled={updatingPriority === (r.id || r.race_name)}
                                  onClick={() => handleUpdateRacePriority(r.id || r.race_name, "B")}
                                  className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${
                                    r.tier === "B"
                                      ? "bg-cyan-500 text-white shadow-sm shadow-cyan-500/50 ring-1 ring-cyan-300"
                                      : "text-zinc-400 hover:text-white hover:bg-white/5"
                                  }`}
                                  title="B 标：以赛代练，门槛巡航检验补给，无需深度减量"
                                >
                                  B 标 (代练)
                                </button>
                                <button
                                  type="button"
                                  disabled={updatingPriority === (r.id || r.race_name)}
                                  onClick={() => handleUpdateRacePriority(r.id || r.race_name, "C")}
                                  className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all ${
                                    r.tier === "C"
                                      ? "bg-zinc-600 text-white shadow-sm shadow-zinc-600/50 ring-1 ring-zinc-400"
                                      : "text-zinc-400 hover:text-white hover:bg-white/5"
                                  }`}
                                  title="C 标：模拟拉练，作为长距离基础跑，低负荷安全完赛"
                                >
                                  C 标 (拉练)
                                </button>
                              </div>

                              <button
                                type="button"
                                onClick={() => {
                                  setTargetRace(r.race_name);
                                  // Update zones & auto-fill
                                  const matchingUserRace = userRaces.find((ur: any) => ur.name === r.race_name);
                                  if (matchingUserRace) {
                                    if (matchingUserRace.target_time) setTargetTime(matchingUserRace.target_time);
                                    if (matchingUserRace.race_type) {
                                      const rt = String(matchingUserRace.race_type).toLowerCase();
                                      if (rt.includes("越野") || rt.includes("trail") || rt.includes("50k") || rt.includes("100k") || rt.includes("160")) {
                                        setRaceType("trail");
                                      } else if (rt.includes("半")) {
                                        setRaceType("half");
                                      } else if (rt.includes("10")) {
                                        setRaceType("10k");
                                      } else if (rt.includes("5")) {
                                        setRaceType("5k");
                                      } else {
                                        setRaceType("marathon");
                                      }
                                    }
                                  }
                                }}
                                className={`px-2.5 py-1 text-[11px] font-bold rounded-xl border transition-all ${
                                  targetRace === r.race_name
                                    ? "bg-purple-600/30 border-purple-500 text-purple-200"
                                    : "bg-[#18181c] border-white/10 text-zinc-400 hover:text-white hover:border-purple-500/50"
                                }`}
                                title="设为当前专项深度分析的单一聚焦点"
                              >
                                {targetRace === r.race_name ? "当前主备赛" : "设为主目标"}
                              </button>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                            <div className="bg-[#121215] p-3 rounded-xl border border-white/5">
                              <div className="text-zinc-400 font-bold mb-1 flex items-center gap-1">
                                <span>🎯</span> 目标配速与心率战术
                              </div>
                              <p className="text-zinc-300 leading-relaxed font-light">
                                {r.pacing_strategy}
                              </p>
                            </div>

                            <div className="bg-[#121215] p-3 rounded-xl border border-white/5">
                              <div className="text-zinc-400 font-bold mb-1 flex items-center gap-1">
                                <span>⏳</span> 减量规程与超量恢复
                              </div>
                              <p className="text-zinc-300 leading-relaxed font-light">
                                {r.taper_recovery_rule}
                              </p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Conflict & Strategic Diagnostics Banner */}
                {analysis.multi_race_strategy.conflict_resolution && (
                  <div className="p-4 rounded-2xl bg-[#18181c] border border-amber-500/30 text-xs space-y-2">
                    <div className="font-bold text-amber-300 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                      战术规避与周期协同要点：
                    </div>
                    <div className="text-zinc-300 leading-relaxed whitespace-pre-line font-light">
                      {analysis.multi_race_strategy.conflict_resolution}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Specificity Training Zones (Canova Zones for Target Race) */}
            {zones && (
              <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
                <h3 className="text-sm font-bold uppercase tracking-wider text-purple-400 mb-4 flex items-center gap-2">
                  <Activity className="w-4 h-4" /> Canova 比赛专项刺激区间参考 ({targetRace})
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                  {Object.entries(zones).map(([k, z]: [string, any]) => (
                    <div key={k} className="bg-[#18181c] border border-white/5 p-3.5 rounded-2xl flex flex-col justify-between">
                      <div>
                        <div className="text-[11px] font-bold text-zinc-400 mb-1">{z.name}</div>
                        <div className="text-sm font-black text-purple-300 tracking-tight">{z.range}</div>
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-2 leading-tight">{z.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Key Suggestions & Focus Workout */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Focus Workout */}
              <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl flex flex-col justify-between">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-purple-400 mb-4 flex items-center gap-2">
                    <Target className="w-4 h-4" /> 本周核心专项关键课
                  </h3>
                  <div className="p-4 bg-purple-950/20 border border-purple-500/20 rounded-2xl text-sm font-medium text-purple-100 leading-relaxed whitespace-pre-line">
                    {formatAdviceContent(analysis.focus_workout_of_the_week) || "热身 3km + 3 × 4000m @ 专项配速 + 2km 冷身"}
                  </div>
                </div>
                <p className="text-xs text-zinc-500 mt-4">
                  * 建议在充分热身与休息充沛状态下执行此课表。
                </p>
              </div>

              {/* Recovery Advice */}
              <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl flex flex-col justify-between">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-emerald-400 mb-4 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" /> 生理恢复与超量恢复指导
                  </h3>
                  <div className="p-4 bg-emerald-950/20 border border-emerald-500/20 rounded-2xl text-sm font-medium text-emerald-100 leading-relaxed whitespace-pre-line">
                    {formatAdviceContent(analysis.recovery_advice) || "大课后 30 分钟内补充高碳水与适量蛋白质，夜间保证 8 小时深度睡眠，监控晨起 HRV 恢复基准。"}
                  </div>
                </div>
                <p className="text-xs text-zinc-500 mt-4">
                  * 密切关注晨起静息心率与睡眠质量得分。
                </p>
              </div>
            </div>

            {/* Detailed Key Suggestions List */}
            <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
              <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
                <span>🎯</span> Canova 专项训练执行要点
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {(analysis.key_suggestions || []).map((sugg: string, idx: number) => (
                  <div key={idx} className="bg-[#18181c] border border-white/5 p-4 rounded-2xl">
                    <span className="text-xs font-bold text-purple-400 block mb-1.5">
                      重点 0{idx + 1}
                    </span>
                    <p className="text-xs text-zinc-300 leading-relaxed">{sugg}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-20 bg-[#121215] border border-white/[0.08] rounded-3xl p-8 shadow-2xl">
            <div className="w-16 h-16 rounded-3xl bg-purple-500/10 text-purple-400 flex items-center justify-center mx-auto mb-4">
              <Zap className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Canova教练就绪</h3>
            <p className="text-xs text-zinc-400 max-w-sm mx-auto mb-6">
              配置您的目标赛事，点击上方“启动 Canova 专项推理”，Canova教练将基于您的近期 Garmin / 高驰训练与生理负荷生成专属报告。
            </p>
            <button
              onClick={handleGenerateAnalysis}
              disabled={loading}
              className="px-6 py-3 rounded-2xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition shadow-lg shadow-purple-600/30"
            >
              生成最新训练诊断
            </button>
          </div>
        )}
        </>
        )}
      </main>
    </div>
  );
}

