"use client";

import { useState } from "react";
import axios from "@/lib/apiClient";

interface DayPlan {
  day: number;
  type: string;
  title: string;
  distance_km: number;
  pace_target: string | null;
  hr_zone: string | null;
  duration_min: number;
  description: string;
  intensity: number;
}

interface TrainingPlan {
  plan_summary: string;
  weekly_km: number;
  days: DayPlan[];
}

const TYPE_CONFIG: Record<string, { icon: string; color: string; bg: string }> = {
  Easy:           { icon: "🏃", color: "#3b82f6", bg: "#3b82f620" },
  Tempo:          { icon: "⚡", color: "#f59e0b", bg: "#f59e0b20" },
  Interval:       { icon: "🔥", color: "#ef4444", bg: "#ef444420" },
  "Long Run":     { icon: "🦘", color: "#8b5cf6", bg: "#8b5cf620" },
  Recovery:       { icon: "💆", color: "#10b981", bg: "#10b98120" },
  Rest:           { icon: "😴", color: "#6b7280", bg: "#6b728020" },
  "Cross Training": { icon: "🏊", color: "#06b6d4", bg: "#06b6d420" },
};

function getTypeConfig(type: string) {
  return TYPE_CONFIG[type] || TYPE_CONFIG["Easy"];
}

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function IntensityDots({ level }: { level: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <div
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${i <= level ? "bg-current" : "bg-white/10"}`}
        />
      ))}
    </div>
  );
}

export default function TrainingPlanWidget({ uid }: { uid: string }) {
  const [plan, setPlan] = useState<TrainingPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`${backendUrl}/api/coach/training-plan`, { uid });
      if (res.data.error) {
        setError(res.data.error);
      } else {
        setPlan(res.data.plan);
        setExpanded(true);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || "生成训练计划失败，请重试");
    }
    setLoading(false);
  };

  if (!expanded && !plan) {
    return (
      <button
        onClick={generate}
        disabled={loading}
        className="w-full py-4 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-500/30 text-zinc-400 hover:text-white rounded-2xl transition-all flex items-center justify-center gap-3 group"
      >
        {loading ? (
          <>
            <div className="w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
            <span className="font-semibold text-sm">AI 正在生成训练计划...</span>
          </>
        ) : (
          <>
            <svg className="w-5 h-5 text-emerald-400 group-hover:scale-110 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
            <span className="font-semibold text-sm">生成个性化 7 天训练计划 (AI)</span>
          </>
        )}
      </button>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-5 text-center">
        <p className="text-red-400 text-sm mb-3">{error}</p>
        <button onClick={generate} className="text-xs text-zinc-400 hover:text-white underline underline-offset-2">
          重新生成
        </button>
      </div>
    );
  }

  if (!plan) return null;

  // Get tomorrow's date as start
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);

  return (
    <div className="bg-white/5 border border-white/10 rounded-3xl overflow-hidden">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <svg className="w-5 h-5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            本周训练计划
          </h2>
          <p className="text-zinc-400 text-sm mt-1">{plan.plan_summary}</p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="text-right">
            <p className="text-2xl font-black text-white">{plan.weekly_km}</p>
            <p className="text-[10px] text-zinc-500 uppercase">总公里</p>
          </div>
          <button
            onClick={generate}
            disabled={loading}
            className="w-8 h-8 rounded-xl bg-white/5 hover:bg-white/10 border border-white/8 flex items-center justify-center text-zinc-400 hover:text-white transition-all"
            title="重新生成"
          >
            {loading ? (
              <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* 7-day grid */}
      <div className="px-6 pb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
        {plan.days.map((day, idx) => {
          const cfg = getTypeConfig(day.type);
          const dayDate = new Date(tomorrow);
          dayDate.setDate(tomorrow.getDate() + idx);
          const isToday = idx === 0;
          const dayOfWeek = WEEKDAYS[dayDate.getDay() === 0 ? 6 : dayDate.getDay() - 1];

          return (
            <div
              key={day.day}
              className={`rounded-2xl p-3.5 border transition-all hover:scale-[1.02] ${
                isToday
                  ? "border-emerald-500/40 bg-emerald-500/8"
                  : "border-white/8 bg-white/3"
              }`}
            >
              {/* Day header */}
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-lg">{cfg.icon}</span>
                  <div>
                    <p className="text-[10px] text-zinc-500 font-medium leading-none">{dayOfWeek}</p>
                    <p className="text-xs text-zinc-400 leading-none mt-0.5">
                      {dayDate.getMonth() + 1}/{dayDate.getDate()}
                    </p>
                  </div>
                </div>
                {isToday && (
                  <span className="text-[8px] bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded-full font-bold uppercase">
                    明天
                  </span>
                )}
              </div>

              {/* Type badge */}
              <div
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold mb-2"
                style={{ background: cfg.bg, color: cfg.color }}
              >
                {day.title}
              </div>

              {/* Stats */}
              {day.distance_km > 0 ? (
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between text-zinc-300">
                    <span>{day.distance_km}km</span>
                    <span className="text-zinc-500">{day.duration_min}分钟</span>
                  </div>
                  {day.pace_target && (
                    <p className="text-zinc-500">配速 {day.pace_target}</p>
                  )}
                  {day.hr_zone && (
                    <p className="text-zinc-500">{day.hr_zone}</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-zinc-600">休息日</p>
              )}

              {/* Intensity */}
              <div className="mt-2 flex items-center gap-2" style={{ color: cfg.color }}>
                <IntensityDots level={day.intensity} />
              </div>

              {/* Description tooltip */}
              {day.description && (
                <p className="text-[10px] text-zinc-600 mt-2 line-clamp-2 leading-tight">
                  {day.description}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
