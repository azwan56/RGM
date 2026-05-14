"use client";

import { useState, useEffect } from "react";
import axios from "@/lib/apiClient";

interface RaceAnalysis {
  race_name: string;
  race_type: string;
  difficulty_level: string;
  total_distance: string;
  elevation_gain: string;
  key_demands: string[];
  climate_notes: string;
  recommended_weekly_km: string;
  fitness_gap: string;
  readiness_score: number;
}

interface CoachFeedback {
  status: string;
  summary: string;
  encouragement?: string;
  actionable_tips: string[];
  training_principles?: { title: string; detail: string }[];
  weekly_cycle?: {
    week: number;
    week_label?: string;
    is_current?: boolean;
    status?: string;
    phase: string;
    focus: string;
    key_session: string;
    volume_note: string;
    tips?: string[];
  }[];
  key_metrics?: Record<string, string>;
  race_analysis?: RaceAnalysis;
}

const difficultyColors: Record<string, string> = {
  "初级": "text-green-400 bg-green-500/15 border-green-500/20",
  "中级": "text-blue-400 bg-blue-500/15 border-blue-500/20",
  "高级": "text-orange-400 bg-orange-500/15 border-orange-500/20",
  "极限": "text-red-400 bg-red-500/15 border-red-500/20",
};

const metricLabels: Record<string, string> = {
  recommended_weekly_km: "建议周跑量",
  easy_run_pace: "轻松跑配速",
  tempo_pace: "节奏跑配速",
  long_run_distance: "长跑距离",
  maf_heart_rate: "MAF心率",
  target_long_run_pct: "长距离占比",
  easy_run_pct: "轻松跑占比",
  max_weekly_increase: "最大跑量增幅"
};

const CACHE_KEY = (uid: string) => `coach_feedback_${uid}`;
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

export default function AiCoachWidget({ uid }: { uid: string }) {
  const [feedback, setFeedback] = useState<CoachFeedback | null>(null);
  const [errorStr, setErrorStr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  useEffect(() => {
    const fetchFeedback = async () => {
      // — Check session cache first —
      try {
        const cached = sessionStorage.getItem(CACHE_KEY(uid));
        if (cached) {
          const { data, ts } = JSON.parse(cached);
          if (Date.now() - ts < CACHE_TTL_MS) {
            setFeedback(data);
            setLoading(false);
            return;
          }
        }
      } catch (_) {}

      // — Fetch from backend cache —
      try {
        const res = await axios.get(`${backendUrl}/api/coach/cache/${uid}`);
        if (res.data && res.data.feedback) {
          setFeedback(res.data.feedback);
          setLoading(false);
          // Update session storage
          try { sessionStorage.setItem(CACHE_KEY(uid), JSON.stringify({ data: res.data.feedback, ts: Date.now() })); } catch (_) {}
          return;
        }
      } catch (err) {
        console.warn("[AiCoach] Backend cache fetch failed:", err);
      }

      // Do NOT auto-generate on mount. Prompt user to click button.
      setErrorStr("点击下方按钮进行 AI 智能分析与数据同步。");
      setLoading(false);
    };
    fetchFeedback();
  }, [uid, backendUrl]);

  const triggerSync = async () => {
    setLoading(true);
    setErrorStr(null);
    try {
      await axios.post(`${backendUrl}/api/sync/trigger`, { uid });
      const res = await axios.post(`${backendUrl}/api/coach/analyze`, { uid, force_refresh: true });
      if (typeof res.data.feedback === "string") {
        setErrorStr(res.data.feedback);
      } else {
        setFeedback(res.data.feedback);
        try { sessionStorage.setItem(CACHE_KEY(uid), JSON.stringify({ data: res.data.feedback, ts: Date.now() })); } catch (_) {}
      }
    } catch (err: any) {
      console.error("Sync API error:", err?.message || err);
      setErrorStr("同步失败，请确认 Strava 已连接且网络稳定。");
    }
    setLoading(false);
  };


  // Determine badge color based on status
  const getBadgeColor = (status: string) => {
    const s = status;
    if (s.includes("冲刺") || s.includes("🔥") || s.includes("倒计时") || s.includes("⏳")) return "bg-red-500/20 text-red-400 border-red-500/30";
    if (s.includes("出色") || s.includes("💪")) return "bg-green-500/20 text-green-400 border-green-500/30";
    if (s.includes("提升") || s.includes("📈") || s.includes("专项")) return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    if (s.includes("调整") || s.includes("📋") || s.includes("储备")) return "bg-purple-500/20 text-purple-400 border-purple-500/30";
    if (s.includes("休息") || s.includes("😴") || s.includes("恢复")) return "bg-yellow-500/20 text-yellow-500 border-yellow-500/30";
    if (s.includes("加油") || s.includes("🏃")) return "bg-[#FC4C02]/20 text-[#FC4C02] border-[#FC4C02]/30";
    return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
  };

  return (
    <div className="bg-white/5 border border-white/10 backdrop-blur-md p-6 lg:p-7 rounded-3xl min-h-[340px] flex flex-col relative overflow-hidden h-full">
      {/* Background Glow */}
      <div className="absolute -top-20 -right-20 w-64 h-64 bg-blue-600/10 rounded-full blur-[100px] pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-5 z-10 relative">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-xl flex items-center justify-center border border-blue-500/20 shadow-lg">
            <svg className="w-5 h-5 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 className="text-white font-bold text-lg">AI 智能分析</h3>
        </div>
        
        {feedback && !loading && (
          <span className={`px-3 py-1 rounded-full text-xs font-bold border whitespace-nowrap ${getBadgeColor(feedback.status)}`}>
            {feedback.status}
          </span>
        )}
      </div>

      {loading ? (
        // Skeleton loader
        <div className="space-y-4 flex-1 z-10 relative">
          <div className="h-16 bg-white/5 rounded-2xl animate-pulse w-full" />
          <div className="space-y-2">
             <div className="h-4 bg-white/5 rounded animate-pulse w-full" />
             <div className="h-4 bg-white/5 rounded animate-pulse w-5/6" />
             <div className="h-4 bg-white/5 rounded animate-pulse w-4/6" />
          </div>
        </div>
      ) : errorStr ? (
        // Error state
        <div className="flex-1 flex flex-col items-center justify-center text-center space-y-3 z-10 relative">
          <p className="text-zinc-500 text-sm max-w-xs">{errorStr}</p>
        </div>
      ) : feedback ? (
        // Rich Content
        <div className="flex-1 flex flex-col space-y-5 z-10 relative">
          {/* Encouragement Banner */}
          {feedback.encouragement && (
            <div className="bg-gradient-to-r from-[#FC4C02]/10 to-orange-500/5 border border-[#FC4C02]/20 p-3.5 rounded-2xl">
              <p className="text-[#FC4C02] text-sm font-semibold text-center">
                {feedback.encouragement}
              </p>
            </div>
          )}

          {/* Race Analysis Section */}
          {feedback.race_analysis && (
            <div className="space-y-4">
              <h4 className="text-xs font-semibold text-zinc-500 tracking-wider">🏔️ 赛事深度分析</h4>
              <div className="bg-gradient-to-br from-white/[0.04] to-white/[0.01] border border-white/10 p-5 rounded-2xl space-y-4">
                {/* Race header */}
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <h5 className="text-white font-bold text-base">{feedback.race_analysis.race_name}</h5>
                    <p className="text-zinc-500 text-xs mt-0.5">{feedback.race_analysis.race_type}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${difficultyColors[feedback.race_analysis.difficulty_level] || 'text-zinc-400 bg-white/5 border-white/10'}`}>
                      {feedback.race_analysis.difficulty_level}
                    </span>
                    <div className="flex items-center gap-1.5 bg-white/5 border border-white/10 px-2.5 py-1 rounded-lg">
                      <span className="text-[10px] text-zinc-500">就绪</span>
                      <span className="text-sm font-bold text-white">{feedback.race_analysis.readiness_score}</span>
                      <span className="text-[10px] text-zinc-500">/10</span>
                    </div>
                  </div>
                </div>

                {/* Race stats */}
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5">
                  <div className="bg-black/20 rounded-xl p-2.5 text-center">
                    <span className="text-[10px] text-zinc-500 block">总距离</span>
                    <span className="text-sm font-bold text-white">{feedback.race_analysis.total_distance}</span>
                  </div>
                  <div className="bg-black/20 rounded-xl p-2.5 text-center">
                    <span className="text-[10px] text-zinc-500 block">累计爬升</span>
                    <span className="text-sm font-bold text-white">{feedback.race_analysis.elevation_gain}</span>
                  </div>
                  <div className="bg-black/20 rounded-xl p-2.5 text-center">
                    <span className="text-[10px] text-zinc-500 block">建议周跑量</span>
                    <span className="text-sm font-bold text-orange-400">{feedback.race_analysis.recommended_weekly_km}</span>
                  </div>
                </div>

                {/* Key demands */}
                <div>
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider">核心能力要求</span>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {feedback.race_analysis.key_demands.map((d, i) => (
                      <span key={i} className="px-2 py-1 bg-blue-500/10 text-blue-300 text-[11px] rounded-md border border-blue-500/10">{d}</span>
                    ))}
                  </div>
                </div>

                {/* Climate notes */}
                {feedback.race_analysis.climate_notes && (
                  <div className="flex gap-2 items-start bg-yellow-500/5 border border-yellow-500/10 p-3 rounded-xl">
                    <span className="text-yellow-500 text-sm flex-shrink-0">⚠️</span>
                    <p className="text-xs text-yellow-200/70 leading-relaxed">{feedback.race_analysis.climate_notes}</p>
                  </div>
                )}

                {/* Fitness gap */}
                <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/15 p-3.5 rounded-xl">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider block mb-1">体能差距评估</span>
                  <p className="text-sm text-zinc-200 leading-relaxed">{feedback.race_analysis.fitness_gap}</p>
                </div>
              </div>
            </div>
          )}

          {/* Summary Quote */}
          <div className="relative bg-black/20 border border-white/5 p-4 rounded-2xl text-zinc-300 text-sm leading-relaxed">
            <svg className="w-6 h-6 text-white/10 absolute -top-2 -left-2" fill="currentColor" viewBox="0 0 24 24">
              <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
            </svg>
            <span className="relative z-10 ml-2">{feedback.summary}</span>
          </div>

          {/* Key Metrics */}
          {feedback.key_metrics && Object.keys(feedback.key_metrics).length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(feedback.key_metrics).map(([key, value]) => (
                <div key={key} className="bg-white/5 border border-white/5 p-3 rounded-xl flex flex-col justify-center items-center text-center">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">{metricLabels[key] || key}</span>
                  <span className="text-sm font-bold text-white">{value}</span>
                </div>
              ))}
            </div>
          )}

          {/* Actionable Tips */}
          <div className="space-y-2.5">
            <h4 className="text-xs font-semibold text-zinc-500 tracking-wider mb-3">📋 本周重点建议</h4>
            {feedback.actionable_tips.map((tip, idx) => (
              <div key={idx} className="flex gap-3 items-start group">
                <div className="w-5 h-5 rounded-full bg-emerald-500/10 flex items-center justify-center flex-shrink-0 mt-0.5 group-hover:bg-emerald-500/20 transition-colors">
                  <svg className="w-3 h-3 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <p className="text-sm text-zinc-300 group-hover:text-white transition-colors leading-snug">{tip}</p>
              </div>
            ))}
          </div>

          {/* Training Principles */}
          {feedback.training_principles && feedback.training_principles.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-zinc-500 tracking-wider">🧠 核心训练原则</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {feedback.training_principles.map((p, idx) => (
                  <div key={idx} className="bg-white/5 border border-white/5 p-3.5 rounded-xl">
                    <h5 className="text-sm font-bold text-blue-400 mb-1.5">{p.title}</h5>
                    <p className="text-xs text-zinc-400 leading-relaxed">{p.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Weekly Cycle */}
          {feedback.weekly_cycle && feedback.weekly_cycle.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-zinc-500 tracking-wider">📅 周期性训练规划</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {feedback.weekly_cycle.map((w, idx) => (
                  <div key={idx} className={`bg-black/20 border p-4 rounded-xl flex flex-col gap-2.5 relative overflow-hidden group transition-colors ${
                    w.is_current 
                      ? 'border-[#FC4C02]/40 ring-1 ring-[#FC4C02]/20' 
                      : w.status === 'completed'
                        ? 'border-emerald-500/20 opacity-75'
                        : 'border-white/5 hover:border-white/10'
                  }`}>
                    <div className={`absolute top-0 left-0 w-1 h-full bg-gradient-to-b ${
                      w.is_current ? 'from-[#FC4C02] to-orange-600' 
                      : w.status === 'completed' ? 'from-emerald-500 to-emerald-600 opacity-70'
                      : 'from-blue-500 to-purple-500 opacity-50'
                    }`} />
                    
                    <div className="flex items-center justify-between z-10">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-white">第 {w.week} 周</span>
                        {w.week_label && (
                          <span className="text-[10px] text-zinc-500">{w.week_label}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5">
                        {w.status === 'completed' && (
                          <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">✓ 已完成</span>
                        )}
                        {w.is_current && (
                          <span className="text-[10px] font-bold text-[#FC4C02] bg-[#FC4C02]/10 px-1.5 py-0.5 rounded">当前</span>
                        )}
                        <span className="text-xs font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-md">{w.phase}期</span>
                      </div>
                    </div>
                    
                    <div className="z-10 space-y-1">
                      <p className="text-xs text-zinc-300 leading-snug"><strong className="text-zinc-500 font-normal">重点：</strong>{w.focus}</p>
                      <p className="text-xs text-zinc-300 leading-snug"><strong className="text-zinc-500 font-normal">关键课：</strong>{w.key_session}</p>
                      <p className="text-xs text-zinc-300 leading-snug"><strong className="text-zinc-500 font-normal">跑量：</strong><span className="text-orange-400">{w.volume_note}</span></p>
                    </div>

                    {w.tips && w.tips.length > 0 && (
                      <ul className="text-[10px] text-zinc-500 list-disc list-inside mt-1 z-10">
                        {w.tips.map((t, i) => <li key={i} className="truncate">{t}</li>)}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {/* Action Button */}
      <div className="mt-6 z-10 relative">
        <button 
          onClick={triggerSync}
          disabled={loading}
          className="w-full py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-white disabled:opacity-50 text-sm font-semibold rounded-xl transition-all flex items-center justify-center gap-2 group"
        >
          {loading ? (
             <svg className="w-4 h-4 animate-spin text-zinc-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
               <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
             </svg>
          ) : (
            <svg className="w-4 h-4 text-zinc-400 group-hover:text-white transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          {loading ? "分析中..." : "同步数据并刷新分析"}
        </button>
      </div>
    </div>
  );
}
