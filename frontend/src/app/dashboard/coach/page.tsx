"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import { Zap, Sparkles, Target, RefreshCw, CheckCircle2, ShieldAlert, Trophy, Flame } from "lucide-react";

export default function CoachPage() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [targetRace, setTargetRace] = useState("武功山 50K");
  const [targetTime, setTargetTime] = useState("8:00:00");

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadLatestAnalysis(u.id);
      } else {
        loadLatestAnalysis("u_df65d9a588c9");
      }
    });
  }, []);

  async function loadLatestAnalysis(uid: string) {
    try {
      const res = await apiClient.get(`/api/coach/latest/${uid}`);
      if (res.data && res.data.summary) {
        setAnalysis(res.data);
      }
    } catch (e) {
      console.error("Latest coach report fetch error:", e);
    }
  }

  async function handleGenerateAnalysis() {
    const uid = user?.id || "u_df65d9a588c9";
    setLoading(true);
    try {
      const res = await apiClient.post("/api/coach/analysis", {
        uid,
        target_race: targetRace,
        target_time: targetTime,
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

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black flex items-center gap-2.5">
              <Zap className="w-7 h-7 text-purple-400" />
              Renato Canova AI 智能教练
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              世界级马拉松专项化训练哲学 · 驱动个人最佳 PB 突破
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerateAnalysis}
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition-all shadow-lg shadow-purple-600/25 active:scale-95 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              {loading ? "AI 深度推理中..." : "重新分析当前状态"}
            </button>
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
              点击上方“重新分析当前状态”，AI 教练将基于您的近期 Garmin 训练与生理负荷生成专属报告。
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
