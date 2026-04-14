"use client";

import { useMemo } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Line, ComposedChart, ReferenceLine
} from "recharts";

interface VdotAnalysis {
  vdot: number;
  r_squared: number;
  max_aerobic_pace_sec: number;
  max_aerobic_vel: number;
  scatter: { hrr: number; gap: number }[];
  regression_line: { x: number[]; y: number[] };
  error?: string;
  low_confidence?: boolean;
}

interface Props {
  data: VdotAnalysis;
}

const formatPace = (m_s: number) => {
  if (!m_s || m_s <= 0) return "—";
  const sec = 1000 / m_s;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}'${String(s).padStart(2, "0")}"`;
};

export default function VdotChart({ data }: Props) {
  
  // Guard: data may be an error response
  if (!data || data.error || !data.scatter || !data.regression_line) {
    const msg = data?.error || "数据不足，无法计算跑力值。";
    const isR2 = msg.includes("R^") || msg.includes("scattered");
    return (
      <div className="bg-white/5 border border-white/10 rounded-2xl p-6 flex flex-col items-center justify-center gap-3 min-h-[200px]">
        <svg className="w-8 h-8 text-zinc-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <p className="text-zinc-500 text-sm text-center max-w-xs">
          {isR2 ? "心率与配速相关性不足，无法拟合跑力值。" : msg}
        </p>
        <p className="text-zinc-600 text-xs text-center">
          {isR2 ? "建议选择一次有稳定心率和配速的轻松跑或长距离跑。" : ""}
        </p>
      </div>
    );
  }

  if (data.r_squared < 0.2) {
    return (
       <div className="bg-white/5 border border-white/10 rounded-2xl p-6 flex items-center justify-center h-full">
         <p className="text-zinc-500 text-sm">单次数据波动过大，无法拟合跑力值。</p>
       </div>
    );
  }
  
  const chartData = useMemo(() => {
    // We need to merge scatter data and the regression line for ComposedChart
    const combined = data.scatter.map(p => ({
      hrr: p.hrr,
      scatter_gap: p.gap,
      line_gap: p.hrr >= data.regression_line.x[0] && p.hrr <= data.regression_line.x[1] 
        ? data.regression_line.y[0] + 
          (p.hrr - data.regression_line.x[0]) * 
          (data.regression_line.y[1] - data.regression_line.y[0]) / 
          (data.regression_line.x[1] - data.regression_line.x[0])
        : null
    }));
    return combined.sort((a, b) => a.hrr - b.hrr);
  }, [data]);


  // Find min and max for Y axis pacing
  const minGap = Math.min(...data.scatter.map(d => d.gap));
  const maxGap = Math.max(...data.scatter.map(d => d.gap));
  const minPace = Math.max(1, minGap - 0.5); // padding

  return (
    <div className="bg-gradient-to-br from-white/5 to-black/20 border border-white/10 rounded-2xl p-6 h-full flex flex-col relative overflow-hidden">
      
      {/* Background decor */}
      <div className="absolute -top-10 -right-10 w-40 h-40 bg-[#FC4C02]/10 rounded-full blur-[80px] pointer-events-none" />

      {/* Header Stat */}
      <div className="flex justify-between items-start mb-6 z-10 relative">
        <div>
           <h3 className="text-white font-bold text-lg mb-1 flex items-center gap-2">
              <svg className="w-5 h-5 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              单场跑力诊断
           </h3>
           <p className="text-xs text-zinc-400">
              心率储备 (%HRR) 与 等价平地配速 (GAP) 拟合分析
           </p>
        </div>
        
        <div className="text-right">
           <div className="inline-flex items-baseline gap-1">
              <span className="text-3xl font-black text-[#FC4C02] leading-none">{data.vdot.toFixed(1)}</span>
              <span className="text-xs text-zinc-500 font-bold uppercase">VDOT</span>
           </div>
           <p className="text-[10px] text-zinc-500 mt-1">
             R² = {data.r_squared.toFixed(2)}
           </p>
           {data.low_confidence && (
             <p className="text-[10px] text-amber-400/70 mt-0.5">⚠ 参考值（配速波动较大）</p>
           )}
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 w-full min-h-[220px] z-10 relative">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, bottom: 20, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
            
            <XAxis 
              dataKey="hrr" 
              type="number" 
              domain={['dataMin - 5', 100]} 
              tick={{ fill: "#a1a1aa", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            >
               {/* Label doesn't support easy positioning in recharts XAxis, so we rely on tooltips/legend */}
            </XAxis>
            
            <YAxis 
               dataKey="scatter_gap" 
               type="number" 
               domain={[minPace, "dataMax + 0.5"]} 
               tickFormatter={formatPace}
               tick={{ fill: "#a1a1aa", fontSize: 10 }}
               axisLine={false}
               tickLine={false}
            />
            
            <Tooltip 
               contentStyle={{ backgroundColor: '#18181b', borderColor: '#ffffff20', borderRadius: '12px' }}
               itemStyle={{ fontSize: '12px' }}
               labelStyle={{ display: 'none' }}
               formatter={(value: any, name: any) => {
                 if (name === "scatter_gap") return [formatPace(value) + " /km", "等价配速"];
                 if (name === "line_gap") return [formatPace(value) + " /km", "回归预测"];
                 return [value, name];
               }}
            />

            {/* Regression Line */}
            <Line 
               type="monotone" 
               dataKey="line_gap" 
               stroke="#FC4C02" 
               strokeWidth={2} 
               dot={false}
               activeDot={false}
               isAnimationActive={false}
            />

            {/* Scatter points */}
            <Scatter 
               dataKey="scatter_gap" 
               fill="#3b82f640" 
               isAnimationActive={true}
            />

            {/* Reference Line for 100% HRR (Max Aerobic) */}
            <ReferenceLine x={100} stroke="#ef444450" strokeDasharray="3 3" />

          </ComposedChart>
        </ResponsiveContainer>
        
        {/* X-axis custom label */}
        <div className="absolute bottom-0 right-0 text-[10px] text-zinc-500 font-medium bg-black/40 px-2 py-0.5 rounded">
           % 心率储备 (HRR)
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-4 pt-4 border-t border-white/5 flex justify-between items-center z-10 relative">
        <div className="text-xs">
           <span className="text-zinc-500">有氧极速预估: </span>
           <span className="text-white font-bold">{formatPace(data.max_aerobic_vel)} /km</span>
        </div>
        <div className="flex gap-3 text-[10px] text-zinc-500">
           <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-[#3b82f640]" /> 清洗数据</span>
           <span className="flex items-center gap-1"><div className="w-2 h-[2px] bg-[#FC4C02]" /> 趋势拟合</span>
        </div>
      </div>

    </div>
  );
}
