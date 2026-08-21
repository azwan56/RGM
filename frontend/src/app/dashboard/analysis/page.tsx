"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import { LineChart, Trophy, Zap, Activity, Heart, Moon, BatteryCharging } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart as RechartsLine,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";

export default function AnalysisPage() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [scienceData, setScienceData] = useState<any>(null);
  const [healthTrend, setHealthTrend] = useState<any[]>([]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadScienceAndHealth(u.id);
      }
    });
  }, []);

  async function loadScienceAndHealth(uid: string) {
    try {
      const [sciRes, healthRes] = await Promise.all([
        apiClient.get(`/api/science/metrics/${uid}`),
        apiClient.get(`/api/science/health-trend/${uid}`),
      ]);
      setScienceData(sciRes.data);
      setHealthTrend(healthRes.data?.trend || []);
    } catch (e) {
      console.error("Load science & health error:", e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">跑步科学与体能深度分析</h1>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1">
            CTL/ATL/TSB 负荷模型 · 30天生理健康趋势 · Jack Daniels VDOT 跑力诊断 · Canova 专项配速矩阵
          </p>
        </div>

        {/* ── CARD 1: 生理恢复与健康历史趋势 (30天双图表) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-8">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="text-xl">📊</span>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                生理恢复与健康历史趋势 (30天)
              </h2>
            </div>
            <p className="text-xs text-zinc-400 mt-1">
              对比夜间 HRV、静息心率 (RHR) 与睡眠质量波动
            </p>
          </div>

          {/* Sub-Chart 1: HRV vs RHR (Dual Y-Axis) */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
              <Heart className="w-4 h-4 text-rose-500" />
              <span>夜间 HRV (ms) 与 静息心率 RHR (bpm) 趋势图</span>
            </div>

            <div className="h-[240px] sm:h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RechartsLine data={healthTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="#1f1f24" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date_label" stroke="#666" fontSize={11} tickLine={false} />
                  <YAxis
                    yAxisId="left"
                    stroke="#ef4444"
                    fontSize={11}
                    tickLine={false}
                    domain={["dataMin - 3", "dataMax + 3"]}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#06b6d4"
                    fontSize={11}
                    tickLine={false}
                    domain={["dataMin - 5", "dataMax + 5"]}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#16161a",
                      borderColor: "rgba(255,255,255,0.15)",
                      borderRadius: "14px",
                      fontSize: "12px",
                    }}
                    formatter={(val: any, name: any) => {
                      if (name === "resting_heart_rate") return [`${val} bpm`, "静息心率 (RHR)"];
                      if (name === "hrv") return [`${val} ms`, "夜间 HRV"];
                      return [val, name];
                    }}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="resting_heart_rate"
                    name="resting_heart_rate"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#ef4444" }}
                    activeDot={{ r: 5 }}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="hrv"
                    name="hrv"
                    stroke="#06b6d4"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#06b6d4" }}
                    activeDot={{ r: 5 }}
                  />
                </RechartsLine>
              </ResponsiveContainer>
            </div>

            <div className="flex items-center justify-center gap-6 text-xs text-zinc-400">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#06b6d4]" />
                <span className="text-cyan-400">夜间 HRV (ms)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#ef4444]" />
                <span className="text-rose-400">静息心率 (RHR bpm)</span>
              </div>
            </div>
          </div>

          {/* Sub-Chart 2: Body Battery vs Sleep Score (0-100 Dual Line) */}
          <div className="space-y-3 pt-6 border-t border-white/5">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300">
              <BatteryCharging className="w-4 h-4 text-amber-400" />
              <span>身体电量 (%) 与 睡眠质量得分</span>
            </div>

            <div className="h-[240px] sm:h-[280px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RechartsLine data={healthTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="#1f1f24" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date_label" stroke="#666" fontSize={11} tickLine={false} />
                  <YAxis stroke="#666" fontSize={11} tickLine={false} domain={[0, 100]} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#16161a",
                      borderColor: "rgba(255,255,255,0.15)",
                      borderRadius: "14px",
                      fontSize: "12px",
                    }}
                    formatter={(val: any, name: any) => {
                      if (name === "sleep_score") return [`${val} 分`, "睡眠得分"];
                      if (name === "body_battery") return [`${val} %`, "身体电量 Max"];
                      return [val, name];
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="sleep_score"
                    name="sleep_score"
                    stroke="#818cf8"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#818cf8" }}
                    activeDot={{ r: 5 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="body_battery"
                    name="body_battery"
                    stroke="#eab308"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#eab308" }}
                    activeDot={{ r: 5 }}
                  />
                </RechartsLine>
              </ResponsiveContainer>
            </div>

            <div className="flex items-center justify-center gap-6 text-xs text-zinc-400">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#818cf8]" />
                <span className="text-indigo-300">睡眠得分</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#eab308]" />
                <span className="text-amber-300">身体电量 Max (%)</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── CARD 2: VDOT & Race Predictions ── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-[#121215] border border-[#FC4C02]/30 rounded-3xl p-6 flex flex-col justify-between shadow-2xl">
            <div>
              <div className="flex items-center gap-2 text-[#FC4C02] text-xs font-bold uppercase tracking-wider">
                <Zap className="w-4 h-4" />
                Jack Daniels VDOT
              </div>
              <div className="text-4xl sm:text-5xl font-black text-white mt-3">
                {scienceData?.vdot || 52.5}
              </div>
              <p className="text-xs text-zinc-400 mt-2">
                基于近期最佳跑步配速与心率区间综合计算的跑力值。
              </p>
            </div>
            <div className="mt-4 pt-4 border-t border-white/5 text-xs text-zinc-500">
              评估等级: <span className="text-emerald-400 font-semibold">进阶马拉松跑者</span>
            </div>
          </div>

          <div className="md:col-span-2 bg-[#121215] border border-white/[0.08] rounded-3xl p-6 shadow-2xl">
            <div className="flex items-center gap-2 text-xs font-bold text-zinc-300 mb-4">
              <Trophy className="w-4 h-4 text-amber-400" />
              基于当前跑力的各距离成绩预测 (Race Predictions)
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-[#18181c] p-4 rounded-2xl border border-white/5">
                <span className="text-xs text-zinc-500 block">5 公里</span>
                <span className="text-lg font-black text-white mt-1 block">
                  {scienceData?.race_predictions?.five_k || "19:45"}
                </span>
              </div>
              <div className="bg-[#18181c] p-4 rounded-2xl border border-white/5">
                <span className="text-xs text-zinc-500 block">10 公里</span>
                <span className="text-lg font-black text-white mt-1 block">
                  {scienceData?.race_predictions?.ten_k || "41:10"}
                </span>
              </div>
              <div className="bg-[#18181c] p-4 rounded-2xl border border-white/5">
                <span className="text-xs text-zinc-500 block">半程马拉松</span>
                <span className="text-lg font-black text-white mt-1 block">
                  {scienceData?.race_predictions?.half_marathon || "1:31:30"}
                </span>
              </div>
              <div className="bg-[#18181c] p-4 rounded-2xl border border-white/5">
                <span className="text-xs text-zinc-500 block">全程马拉松</span>
                <span className="text-lg font-black text-rose-400 mt-1 block">
                  {scienceData?.race_predictions?.marathon || "3:10:45"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── CARD 3: Renato Canova 配速矩阵 ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="mb-6">
            <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
              Renato Canova 马拉松专项配速矩阵 (Pace Zones)
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              世界顶级中长跑教练卡诺瓦的核心分期训练区间
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {scienceData?.canova_zones &&
              Object.entries(scienceData.canova_zones).map(([key, zone]: [string, any]) => (
                <div key={key} className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
                  <div>
                    <span className="text-xs font-bold text-amber-400 block mb-1">
                      {zone.name}
                    </span>
                    <span className="text-xl font-black text-white block my-2">
                      {zone.range}
                    </span>
                    <p className="text-xs text-zinc-400 leading-relaxed">{zone.desc}</p>
                  </div>
                </div>
              ))}
          </div>
        </div>
      </main>
    </div>
  );
}
