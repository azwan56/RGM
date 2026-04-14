"use client";

import { useState, useEffect } from "react";
import axios from "@/lib/apiClient";

interface CoachFeedback {
  status: string;
  summary: string;
  encouragement?: string;
  actionable_tips: string[];
}

const CACHE_KEY = (uid: string) => `coach_feedback_${uid}`;
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes

export default function AiCoachWidget({ uid }: { uid: string }) {
  const [feedback, setFeedback] = useState<CoachFeedback | null>(null);
  const [errorStr, setErrorStr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
            return; // skip network call
          }
        }
      } catch (_) {}

      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        const res = await axios.post(`${backendUrl}/api/coach/analyze`, { uid });
        
        if (typeof res.data.feedback === "string") {
          setErrorStr(res.data.feedback);
        } else {
          setFeedback(res.data.feedback);
          // — Write to session cache —
          try { sessionStorage.setItem(CACHE_KEY(uid), JSON.stringify({ data: res.data.feedback, ts: Date.now() })); } catch (_) {}
        }
      } catch (error: any) {
        console.error("Coach API error:", error?.message || error);
        setErrorStr("请先连接 Strava 并同步数据，即可获得 AI 教练的专属建议。");
      }
      setLoading(false);
    };
    fetchFeedback();
  }, [uid]);

  const triggerSync = async () => {
     setLoading(true);
     setErrorStr(null);
     try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
        await axios.post(`${backendUrl}/api/sync/trigger`, { uid });
        const res = await axios.post(`${backendUrl}/api/coach/analyze`, { uid });
        if (typeof res.data.feedback === "string") {
          setErrorStr(res.data.feedback);
        } else {
          setFeedback(res.data.feedback);
          // Bust and rewrite cache on manual sync
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
    if (s.includes("出色") || s.includes("🔥")) return "bg-green-500/20 text-green-400 border-green-500/30";
    if (s.includes("提升") || s.includes("📈") || s.includes("扎实") || s.includes("💪")) return "bg-blue-500/20 text-blue-400 border-blue-500/30";
    if (s.includes("休息") || s.includes("😴") || s.includes("离线")) return "bg-yellow-500/20 text-yellow-500 border-yellow-500/30";
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

          {/* Summary Quote */}
          <div className="relative bg-black/20 border border-white/5 p-4 rounded-2xl text-zinc-300 text-sm leading-relaxed">
            <svg className="w-6 h-6 text-white/10 absolute -top-2 -left-2" fill="currentColor" viewBox="0 0 24 24">
              <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
            </svg>
            <span className="relative z-10 ml-2">{feedback.summary}</span>
          </div>

          {/* Actionable Tips */}
          <div className="space-y-2.5 flex-1">
            <h4 className="text-xs font-semibold text-zinc-500 tracking-wider mb-3">📋 训练建议</h4>
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
