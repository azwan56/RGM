"use client";

import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

interface HealthTrendItem {
  date: string;
  resting_heart_rate?: number;
  sleep_score?: number;
  sleep_duration_seconds?: number;
  hrv_last_night?: number;
  hrv_weekly_avg?: number;
  body_battery_max?: number;
}

interface GarminHealthTrendChartProps {
  data?: HealthTrendItem[];
}

export default function GarminHealthTrendChart({ data = [] }: GarminHealthTrendChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-white/3 border border-white/8 rounded-3xl p-6 text-center text-zinc-500">
        <p className="text-sm">暂无 Garmin 日常恢复历史数据。绑定 Garmin 并持续同步后，将在此展示 30 天恢复趋势。</p>
      </div>
    );
  }

  // Format data for chart
  const chartData = data.map((item) => ({
    date: item.date ? item.date.slice(5) : "", // MM-DD
    rhr: item.resting_heart_rate || null,
    hrv: item.hrv_last_night || item.hrv_weekly_avg || null,
    sleep: item.sleep_score || null,
    battery: item.body_battery_max || null,
  }));

  return (
    <div className="bg-white/3 border border-white/8 rounded-3xl p-5 md:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <span>📊</span> 生理恢复与健康历史趋势 (30天)
          </h3>
          <p className="text-xs text-zinc-500">对比夜间 HRV、静息心率 (RHR) 与睡眠质量波动</p>
        </div>
      </div>

      {/* Chart 1: HRV & RHR Trend */}
      <div className="space-y-2">
        <h4 className="text-xs font-semibold text-zinc-400">🫀 夜间 HRV (ms) 与 静息心率 RHR (bpm) 趋势图</h4>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
              <XAxis dataKey="date" stroke="#71717a" fontSize={11} />
              <YAxis yAxisId="left" stroke="#f43f5e" fontSize={11} domain={["dataMin - 3", "dataMax + 3"]} />
              <YAxis yAxisId="right" orientation="right" stroke="#22d3ee" fontSize={11} domain={["dataMin - 5", "dataMax + 5"]} />
              <Tooltip
                contentStyle={{ backgroundColor: "#18181b", borderColor: "#27272a", borderRadius: "12px", color: "#fff", fontSize: "12px" }}
              />
              <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }} />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="rhr"
                name="静息心率 (RHR bpm)"
                stroke="#f43f5e"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="hrv"
                name="夜间 HRV (ms)"
                stroke="#22d3ee"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Sleep & Body Battery */}
      <div className="space-y-2 pt-2 border-t border-white/5">
        <h4 className="text-xs font-semibold text-zinc-400">⚡ 身体电量 (%) 与 睡眠质量得分</h4>
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
              <XAxis dataKey="date" stroke="#71717a" fontSize={11} />
              <YAxis stroke="#fbbf24" fontSize={11} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ backgroundColor: "#18181b", borderColor: "#27272a", borderRadius: "12px", color: "#fff", fontSize: "12px" }}
              />
              <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }} />
              <Line
                type="monotone"
                dataKey="battery"
                name="身体电量 Max (%)"
                stroke="#fbbf24"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="sleep"
                name="睡眠得分"
                stroke="#818cf8"
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
