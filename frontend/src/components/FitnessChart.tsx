"use client";

import { useEffect, useState } from "react";
import axios from "@/lib/apiClient";
import {
  ComposedChart, Area, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell
} from "recharts";

interface FitnessPoint {
  date: string;
  trimp_today: number;
  ctl: number;
  atl: number;
  tsb: number;
}

export default function FitnessChart({ uid }: { uid: string }) {
  const [data, setData] = useState<FitnessPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        const res = await axios.post(`${backendUrl}/api/science/fitness-trend`, { uid, days: 30 });
        setData(res.data.data || []);
      } catch (err: any) {
        console.error("Fitness trend fetch error", err?.message);
        setError(true);
      }
      setLoading(false);
    };
    fetchData();
  }, [uid]);

  if (loading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-3xl p-6 h-80 flex flex-col items-center justify-center relative overflow-hidden">
        <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-zinc-500 text-sm">正在计算生理指数...</p>
      </div>
    );
  }

  if (error || data.length === 0) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-3xl p-6 h-64 flex items-center justify-center">
        <p className="text-zinc-500 text-sm">暂无足够的生理模型数据</p>
      </div>
    );
  }

  const latest = data[data.length - 1];

  return (
    <div className="bg-white/5 border border-white/10 rounded-3xl p-6 space-y-6 relative overflow-hidden h-full">
      {/* Background glow */}
      <div className="absolute top-0 left-10 w-48 h-48 bg-blue-500/10 blur-3xl pointer-events-none rounded-full" />
      
      {/* Header Stats */}
      <div className="relative z-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            体能与状况指数 (Fitness & Form)
          </h2>
          <p className="text-sm text-zinc-400">基于 TRIMP 与 EWMA 算法</p>
        </div>
        
        {latest && (
          <div className="flex gap-4">
            <div className="bg-black/30 px-4 py-2 rounded-xl border border-white/5">
              <p className="text-[10px] text-blue-400 uppercase font-bold tracking-wider mb-0.5">CTL 体能</p>
              <p className="text-lg font-black text-white leading-none">{latest.ctl}</p>
            </div>
            <div className="bg-black/30 px-4 py-2 rounded-xl border border-white/5">
              <p className="text-[10px] text-pink-400 uppercase font-bold tracking-wider mb-0.5">ATL 疲劳</p>
              <p className="text-lg font-black text-white leading-none">{latest.atl}</p>
            </div>
            <div className="bg-black/30 px-4 py-2 rounded-xl border border-white/5">
              <p className="text-[10px] text-yellow-400 uppercase font-bold tracking-wider mb-0.5">TSB 状况</p>
              <p className={`text-lg font-black leading-none ${latest.tsb >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {latest.tsb > 0 ? '+' : ''}{latest.tsb}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="relative z-10">
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart data={data} margin={{ top: 10, right: 0, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff0f" vertical={false} />
            <XAxis 
              dataKey="date" 
              tickFormatter={(val) => val.slice(5)} 
              tick={{ fill: "#71717a", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            {/* Left Y Axis for CTL/ATL */}
            <YAxis yAxisId="left" domain={[0, 'dataMax + 20']} orientation="left" hide />
            {/* Right Y Axis for TSB (Positive/Negative) */}
            <YAxis yAxisId="right" orientation="right" hide domain={['dataMin - 20', 'dataMax + 20']} />

            <Tooltip 
              contentStyle={{ backgroundColor: '#18181b', borderColor: '#ffffff20', borderRadius: '12px', fontSize: '12px' }}
              itemStyle={{ fontWeight: 600 }}
              labelStyle={{ color: '#a1a1aa', marginBottom: '4px' }}
            />

            {/* Zero Line for TSB */}
            <ReferenceLine y={0} yAxisId="right" stroke="#ffffff20" strokeDasharray="3 3" />

            {/* TSB - Bar Chart */}
            <Bar dataKey="tsb" yAxisId="right" fill="#eab308" name="状况 (TSB)" radius={[2, 2, 0, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.tsb >= 0 ? "#10b98180" : "#ef444480"} />
              ))}
            </Bar>

            {/* CTL - Blue Area */}
            <Area 
              type="monotone" 
              dataKey="ctl" 
              yAxisId="left" 
              fill="#3b82f640" 
              stroke="#3b82f6" 
              strokeWidth={2}
              name="体能 (CTL)"
              isAnimationActive={true}
            />
            
            {/* ATL - Pink Line */}
            <Line 
              type="monotone" 
              dataKey="atl" 
              yAxisId="left" 
              stroke="#ec4899" 
              strokeWidth={2} 
              dot={false}
              name="疲劳 (ATL)"
              isAnimationActive={true}
            />

          </ComposedChart>
        </ResponsiveContainer>
      </div>
      
      {/* Legend / Guide */}
      <div className="relative z-10 flex flex-wrap gap-x-6 gap-y-2 pt-4 border-t border-white/5 text-xs text-zinc-400">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-blue-500/50" />
          <span>体能 (CTL): 42天长期压力</span>
        </div>
        <div className="flex items-center gap-2">
           <span className="w-3 h-0.5 bg-pink-500" />
           <span>疲劳 (ATL): 7天近期压力</span>
        </div>
        <div className="flex items-center gap-2">
           <span className="w-3 h-3 rounded-sm bg-green-500/50" />
           <span className="w-3 h-3 rounded-sm bg-red-500/50 -ml-1.5" />
           <span>状况 (TSB): 比赛准备度</span>
        </div>
      </div>
    </div>
  );
}
