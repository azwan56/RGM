"use client";

import { useEffect, useState } from "react";
import axios from "@/lib/apiClient";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell
} from "recharts";

interface MonthPoint {
  month: string;
  label: string;
  distance_km: number;
  run_count: number;
  avg_pace: string;
}

export default function TrendChart({ uid }: { uid: string }) {
  const [data, setData] = useState<MonthPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
        const res = await axios.post(`${backendUrl}/api/science/monthly-trend`, { uid, months: 6 });
        setData(res.data.data || []);
      } catch (_) {}
      setLoading(false);
    };
    fetch();
  }, [uid]);

  if (loading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-3xl p-6 h-64 flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-zinc-500 text-sm">加载趋势数据...</span>
        </div>
      </div>
    );
  }

  const maxDist = Math.max(...data.map(d => d.distance_km), 1);

  // Compute trend label
  const nonEmpty = data.filter(d => d.distance_km > 0);
  let trendLabel = "";
  if (nonEmpty.length >= 2) {
    const last   = nonEmpty[nonEmpty.length - 1].distance_km;
    const second = nonEmpty[nonEmpty.length - 2].distance_km;
    const delta  = ((last - second) / second * 100).toFixed(0);
    trendLabel = last >= second
      ? `↑ 较上月 +${delta}%`
      : `↓ 较上月 ${delta}%`;
  }

  const currentMonth = data[data.length - 1];

  return (
    <div className="bg-white/5 border border-white/10 rounded-3xl p-6 space-y-5 relative overflow-hidden">
      <div className="absolute -top-8 -left-8 w-40 h-40 bg-green-500/5 blur-3xl rounded-full pointer-events-none" />

      {/* Header */}
      <div className="flex items-end justify-between z-10 relative">
        <div>
          <h3 className="text-white font-bold text-lg">月度跑量趋势</h3>
          <p className="text-zinc-500 text-xs mt-0.5">近 6 个月</p>
        </div>
        {currentMonth && (
          <div className="text-right">
            <div className="text-2xl font-black text-white leading-none">
              {currentMonth.distance_km.toFixed(0)}
              <span className="text-sm font-normal text-zinc-400 ml-1">km</span>
            </div>
            {trendLabel && (
              <div className={`text-xs font-semibold mt-0.5 ${trendLabel.startsWith("↑") ? "text-green-400" : "text-red-400"}`}>
                {trendLabel}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="h-52 z-10 relative">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 0, bottom: 0, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "#71717a", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis hide domain={[0, maxDist * 1.2]} />
            <Tooltip
              contentStyle={{ backgroundColor: "#18181b", borderColor: "#ffffff20", borderRadius: "12px", fontSize: "12px" }}
              labelStyle={{ color: "#a1a1aa", marginBottom: "4px" }}
              formatter={(value: number, name: string) => {
                if (name === "distance_km") return [`${value} km`, "跑量"];
                return [value, name];
              }}
            />
            <Bar dataKey="distance_km" radius={[6, 6, 0, 0]} name="跑量">
              {data.map((_, idx) => (
                <Cell
                  key={idx}
                  fill={idx === data.length - 1 ? "#22c55e" : "#22c55e40"}
                />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Monthly summary row */}
      <div className="grid grid-cols-3 gap-2 border-t border-white/5 pt-4">
        {data.slice(-3).map((m) => (
          <div key={m.month} className="text-center">
            <p className="text-[10px] text-zinc-500 mb-1">{m.label}</p>
            <p className="text-sm font-bold text-white">{m.distance_km > 0 ? `${m.distance_km}km` : "—"}</p>
            <p className="text-[10px] text-zinc-600">{m.run_count > 0 ? `${m.run_count} 次` : ""}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
