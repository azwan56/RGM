"use client";

import { useState, useEffect } from "react";
import axios from "@/lib/apiClient";
import RacePredictor from "./RacePredictor";
import TrainingZones from "./TrainingZones";

export default function RaceDashboard({ uid }: { uid: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    axios
      .post(`${backendUrl}/api/science/race-predictor`, { uid })
      .then((r) => {
        if (r.data.error) setError(r.data.error);
        else setData(r.data);
      })
      .catch(() => setError("无法加载跑力数据"))
      .finally(() => setLoading(false));
  }, [uid]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {[0, 1].map((i) => (
          <div key={i} className="bg-white/5 border border-white/10 rounded-3xl p-6 h-64 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-3xl p-6 flex flex-col items-center justify-center gap-3 min-h-[180px]">
        <svg className="w-10 h-10 text-zinc-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <p className="text-zinc-500 text-sm text-center max-w-xs">{error}</p>
        <p className="text-zinc-600 text-xs text-center">先打开一次跑步记录的详情页，系统会自动计算你的跑力指数</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-5">
      {/* Section header */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 border border-green-500/20 flex items-center justify-center">
          <svg className="w-5 h-5 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <h2 className="text-white font-bold text-xl">跑力分析</h2>
          <p className="text-zinc-500 text-xs">VDOT {data.race_times.vdot} · 基于最近训练数据动态计算</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <RacePredictor data={data.race_times} />
        <TrainingZones zones={data.zones} vdot={data.race_times.vdot} />
      </div>
    </div>
  );
}
