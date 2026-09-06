"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
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
  Heart
} from "lucide-react";

export default function CoachPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [targetRace, setTargetRace] = useState("武功山 50K");
  const [targetTime, setTargetTime] = useState("8:00:00");
  const [raceType, setRaceType] = useState("trail");

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
      } else {
        router.push("/login");
      }
    });
  }, [router]);

  async function loadLatestAnalysis(uid: string) {
    try {
      const res = await apiClient.get(`/api/coach/latest/${uid}`);
      if (res.data && res.data.summary) {
        setAnalysis(res.data);
        if (res.data.athlete_snapshot?.target_race) {
          setTargetRace(res.data.athlete_snapshot.target_race);
        }
        if (res.data.athlete_snapshot?.target_time) {
          setTargetTime(res.data.athlete_snapshot.target_time);
        }
        if (res.data.athlete_snapshot?.race_category) {
          setRaceType(res.data.athlete_snapshot.race_category);
        }
      }
    } catch (e) {
      console.error("Latest coach report fetch error:", e);
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
      alert("AI 分析生成提示: 正在使用最近一次训练诊断缓存");
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


  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Title Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black flex items-center gap-2.5">
              <Zap className="w-7 h-7 text-purple-400" />
              Renato Canova AI 智能耐力教练
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              世界级专项化训练哲学 · 5K/半马/全马/越野因赛制宜 · 动态 TSB 负荷与年龄自适应
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerateAnalysis}
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition-all shadow-lg shadow-purple-600/25 active:scale-95 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              {loading ? "AI 深度推理中..." : "启动 AI 专项推理"}
            </button>
          </div>
        </div>

        {/* Top Control Bar: Athlete Profile & Race Setup */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Athlete Profile & Physiological Form */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-purple-400" /> 跑者生理档案
              </span>
              <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${getTsbColor(tsb)}`}>
                {statusLabel}
              </span>
            </div>

            <div className="space-y-2">
              <div className="text-lg font-black text-white">
                {athlete?.name || "跑者"}
                <span className="ml-2 text-xs font-medium text-zinc-400">
                  {athlete?.gender === "female" ? "♀ 女性" : "♂ 男性"}
                </span>
              </div>
              <div className="text-xs text-zinc-400 flex items-center gap-3">
                <span>周岁: <strong className="text-purple-300">{athlete?.age ? `${athlete.age} 岁` : "未登记"}</strong></span>
                <span>跑龄: <strong className="text-purple-300">{athlete?.years_running || 2} 年</strong></span>
              </div>
            </div>

            {/* TSB Metric Indicators */}
            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/5">
              <div className="bg-[#18181c] p-2.5 rounded-xl text-center">
                <div className="text-[10px] text-zinc-400">体能 CTL</div>
                <div className="text-sm font-black text-cyan-400 mt-0.5">{ctl}</div>
              </div>
              <div className="bg-[#18181c] p-2.5 rounded-xl text-center">
                <div className="text-[10px] text-zinc-400">疲劳 ATL</div>
                <div className="text-sm font-black text-amber-400 mt-0.5">{atl}</div>
              </div>
              <div className="bg-[#18181c] p-2.5 rounded-xl text-center">
                <div className="text-[10px] text-zinc-400">状态 TSB</div>
                <div className={`text-sm font-black mt-0.5 ${tsb >= 0 ? "text-emerald-400" : "text-purple-400"}`}>
                  {tsb > 0 ? `+${tsb}` : tsb}
                </div>
              </div>
            </div>

            {riskWarning && (
              <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-2xl flex items-start gap-2 text-xs text-red-200">
                <ShieldAlert className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                <span className="leading-snug">{riskWarning}</span>
              </div>
            )}
          </div>

          {/* Interactive Target Race & Type Customization */}
          <div className="lg:col-span-2 bg-[#121215] border border-white/[0.08] rounded-3xl p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5" /> 目标赛事与专项类型设定
              </span>
              <span className="text-xs text-zinc-500">
                Canova 哲学核心：专项性依赛事而变
              </span>
            </div>

            {/* Quick Presets */}
            <div className="flex flex-wrap gap-2">
              {racePresets.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setTargetRace(p.race);
                    setTargetTime(p.time);
                    setRaceType(p.type);
                  }}
                  className={`text-xs px-3 py-1.5 rounded-xl border transition-all ${
                    targetRace === p.race
                      ? "bg-purple-600/30 border-purple-500 text-purple-200 font-bold"
                      : "bg-[#18181c] border-white/5 text-zinc-400 hover:text-white"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
              <div>
                <label className="text-[11px] text-zinc-400 block mb-1">目标赛事名称</label>
                <input
                  type="text"
                  value={targetRace}
                  onChange={(e) => setTargetRace(e.target.value)}
                  placeholder="例如: 武功山 50K / 无锡马拉松"
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
                    {typeof analysis.focus_workout_of_the_week === "object" && analysis.focus_workout_of_the_week
                      ? Object.entries(analysis.focus_workout_of_the_week).map(([k, v]) => `【${k}】${v}`).join("\n")
                      : String(analysis.focus_workout_of_the_week || "热身 3km + 3 × 4000m @ 专项配速 + 2km 冷身")}
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
                  <div className="p-4 bg-emerald-950/20 border border-emerald-500/20 rounded-2xl text-sm font-medium text-emerald-100 leading-relaxed">
                    {analysis.recovery_advice}
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
            <h3 className="text-lg font-bold text-white mb-2">Canova AI 教练就绪</h3>
            <p className="text-xs text-zinc-400 max-w-sm mx-auto mb-6">
              配置您的目标赛事，点击上方“启动 AI 专项推理”，AI 教练将基于您的近期 Garmin / 高驰训练与生理负荷生成专属报告。
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
      </main>
    </div>
  );
}

