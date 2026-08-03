"use client";

import React from "react";

interface GarminHealthCardProps {
  health?: {
    date?: string;
    resting_heart_rate?: number;
    sleep_score?: number;
    sleep_duration_seconds?: number;
    hrv_status?: string;
    hrv_weekly_avg?: number;
    hrv_last_night?: number;
    body_battery_max?: number;
    source?: string;
  };
  vo2Max?: number;
}

export default function GarminHealthCard({ health, vo2Max }: GarminHealthCardProps) {
  if (!health && !vo2Max) return null;

  const rhr = health?.resting_heart_rate;
  const sleepScore = health?.sleep_score;
  const sleepSec = health?.sleep_duration_seconds;
  const hrvStatus = health?.hrv_status;
  const hrvWeekly = health?.hrv_weekly_avg;
  const hrvNight = health?.hrv_last_night;
  const bodyBattery = health?.body_battery_max;

  // Format sleep duration
  const sleepStr = sleepSec
    ? `${Math.floor(sleepSec / 3600)}h ${Math.floor((sleepSec % 3600) / 60)}m`
    : "—";

  // HRV status badge styling
  const hrvBadge = () => {
    if (!hrvStatus) return null;
    const statusUpper = hrvStatus.toUpperCase();
    if (statusUpper.includes("BALANCED")) {
      return <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">✓ 平衡 (Balanced)</span>;
    } else if (statusUpper.includes("UNBALANCED") || statusUpper.includes("LOW")) {
      return <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-amber-500/20 text-amber-400 border border-amber-500/30">⚠️ 偏低/波动</span>;
    }
    return <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-white/10 text-zinc-300">{hrvStatus}</span>;
  };

  return (
    <div className="bg-white/3 border border-white/8 rounded-3xl p-5 md:p-6 space-y-4 relative overflow-hidden backdrop-blur-md">
      <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/10 rounded-full blur-2xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-xl">⌚</span>
          <div>
            <h3 className="text-base font-bold text-white leading-tight">Garmin 生理与恢复卡片</h3>
            <p className="text-xs text-zinc-500">
              {health?.date ? `最近更新: ${health.date}` : "来自 Garmin 佳明同步"}
            </p>
          </div>
        </div>
        {hrvBadge()}
      </div>

      {/* 4 Grid Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {/* 1. Sleep */}
        <div className="bg-white/4 border border-white/6 rounded-2xl p-3.5 flex flex-col justify-between">
          <span className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
            <span>🛌</span> 睡眠恢复
          </span>
          <div className="mt-2">
            <div className="text-xl md:text-2xl font-black text-white">
              {sleepScore ? `${sleepScore} 分` : sleepStr}
            </div>
            <p className="text-[11px] text-zinc-500 mt-0.5">
              {sleepScore ? `时长 ${sleepStr}` : "质量评级"}
            </p>
          </div>
        </div>

        {/* 2. Resting HR */}
        <div className="bg-white/4 border border-white/6 rounded-2xl p-3.5 flex flex-col justify-between">
          <span className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
            <span>💓</span> 静息心率 (RHR)
          </span>
          <div className="mt-2">
            <div className="text-xl md:text-2xl font-black text-rose-400">
              {rhr ? `${rhr} bpm` : "—"}
            </div>
            <p className="text-[11px] text-zinc-500 mt-0.5">清息生理基线</p>
          </div>
        </div>

        {/* 3. Body Battery */}
        <div className="bg-white/4 border border-white/6 rounded-2xl p-3.5 flex flex-col justify-between">
          <span className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
            <span>⚡</span> 身体电量
          </span>
          <div className="mt-2 space-y-1.5">
            <div className="text-xl md:text-2xl font-black text-amber-400">
              {bodyBattery ? `${bodyBattery}%` : "—"}
            </div>
            {bodyBattery && (
              <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 rounded-full"
                  style={{ width: `${Math.min(100, bodyBattery)}%` }}
                />
              </div>
            )}
          </div>
        </div>

        {/* 4. HRV / VO2 Max */}
        <div className="bg-white/4 border border-white/6 rounded-2xl p-3.5 flex flex-col justify-between">
          <span className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
            <span>🫀</span> 夜间 HRV / 摄氧量
          </span>
          <div className="mt-2">
            <div className="text-xl md:text-2xl font-black text-cyan-400">
              {hrvNight ? `${hrvNight} ms` : (vo2Max ? `${vo2Max}` : "—")}
            </div>
            <p className="text-[11px] text-zinc-500 mt-0.5">
              {hrvWeekly ? `周均: ${hrvWeekly} ms` : (vo2Max ? "VO2 Max (ml/kg/min)" : "神经恢复数位")}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
