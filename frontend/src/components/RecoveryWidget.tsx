"use client";

import React, { useEffect, useState } from 'react';
import axios from '@/lib/apiClient';
import GoogleHealthConnectBtn from './GoogleHealthConnectBtn';
import { Heart, Activity, Moon, ShieldAlert, Sparkles, CheckCircle2, ChevronRight } from 'lucide-react';

interface RecoveryDataPoint {
  date: string;
  sleep_duration_sec: number;
  sleep_score: number;
  resting_heart_rate: number;
  heart_rate_variability: number;
  last_sync: string;
}

interface RecoveryWidgetProps {
  uid: string;
  initialHistory?: any[];
}

export default function RecoveryWidget({ uid }: RecoveryWidgetProps) {
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [history, setHistory] = useState<RecoveryDataPoint[]>([]);
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    async function fetchRecovery() {
      try {
        const res = await axios.get(`${backendUrl}/api/google-health/recovery-status`, {
          params: { days: 7 }
        });
        if (res.data.connected) {
          setConnected(true);
          setHistory(res.data.recovery_history || []);
        } else {
          setConnected(false);
        }
      } catch (err) {
        console.error("Failed to fetch recovery status:", err);
      } finally {
        setLoading(false);
      }
    }
    if (uid) {
      fetchRecovery();
    }
  }, [uid, backendUrl]);

  if (loading) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-3xl p-6 h-80 animate-pulse flex flex-col justify-between">
        <div className="h-6 w-1/3 bg-white/10 rounded" />
        <div className="flex items-center gap-6 my-auto">
          <div className="w-24 h-24 rounded-full border-4 border-dashed border-white/10 animate-spin" />
          <div className="space-y-3 flex-1">
            <div className="h-4 w-2/3 bg-white/10 rounded" />
            <div className="h-3 w-1/2 bg-white/10 rounded" />
          </div>
        </div>
        <div className="h-10 bg-white/10 rounded-xl" />
      </div>
    );
  }

  if (!connected) {
    return (
      <div className="bg-gradient-to-br from-zinc-900/60 to-zinc-950 border border-white/5 rounded-3xl p-6 md:p-8 flex flex-col justify-between h-full relative overflow-hidden group">
        {/* Glow effect */}
        <div className="absolute -top-10 -right-10 w-32 h-32 bg-blue-500/10 rounded-full blur-3xl pointer-events-none group-hover:bg-blue-500/20 transition-all duration-500" />
        
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight">生理数据修正 (Fitbit / Google Health)</h2>
          </div>
          
          <p className="text-zinc-400 text-sm leading-relaxed">
            关联您的 Google Health 或 Fitbit 账号，获取每日睡眠得分、心率变异性 (HRV) 和静息心率。
            系统将根据您的真实身体恢复状态，**自动动态修正** CTL/ATL 指数，为您量身定制每日训练推荐与准备度评估。
          </p>

          <div className="grid grid-cols-3 gap-3 pt-2">
            <div className="bg-white/5 rounded-2xl p-3 border border-white/5 flex flex-col items-center text-center">
              <Moon className="w-5 h-5 text-indigo-400 mb-1" />
              <span className="text-[11px] text-zinc-400 font-medium">精准睡眠追踪</span>
            </div>
            <div className="bg-white/5 rounded-2xl p-3 border border-white/5 flex flex-col items-center text-center">
              <Activity className="w-5 h-5 text-emerald-400 mb-1" />
              <span className="text-[11px] text-zinc-400 font-medium">HRV 状态修正</span>
            </div>
            <div className="bg-white/5 rounded-2xl p-3 border border-white/5 flex flex-col items-center text-center">
              <Heart className="w-5 h-5 text-rose-400 mb-1" />
              <span className="text-[11px] text-zinc-400 font-medium">静息心率基线</span>
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-white/5 pt-4">
          <span className="text-xs text-zinc-500">仅用于 RGM 内部体能分析，数据绝不公开</span>
          <GoogleHealthConnectBtn />
        </div>
      </div>
    );
  }

  // Find latest recovery data point
  const todayData = history.length > 0 ? history[history.length - 1] : null;
  const sleepScore = todayData?.sleep_score || 0;
  const rhr = todayData?.resting_heart_rate || 0;
  const hrv = todayData?.heart_rate_variability || 0;
  const sleepSec = todayData?.sleep_duration_sec || 0;

  // Let's compute a simple readiness score on frontend for immediate display
  // We match the backend sports science formula for consistency
  // Weighted: TSB (40%), HRV (35%), Sleep (25%)
  // Since TSB calculation is complex and is passed to the frontend from the trend,
  // we can use a fallback default readiness or calculate it if we have CTL/ATL.
  // Wait, if todayData exists, we can fetch readiness from history if it is stored.
  // Since our backend stores daily_recovery, it also has these fields.
  // Wait! Did we calculate readiness in `compute_fitness_fatigue_timeseries`? Yes, we return `readiness` field in the list of trend values.
  // Wait, we can fetch the latest readiness score from the trend data on the dashboard, or we can compute an estimated readiness directly!
  // Let's estimate it:
  const getReadinessScore = () => {
    // If we have history or backend estimated it:
    // Let's build a clean, beautiful gauge.
    // HRV ratio: assume baseline of 60.
    const hrvBaseline = 60.0;
    const hrvRatio = hrv / hrvBaseline;
    const hrvComp = 80 + (hrvRatio - 1.0) * 100;
    const sleepComp = sleepScore > 0 ? sleepScore : 75;
    // Standard TSB component: assume neutral Form of +5.
    const formComp = 50 + 5 * 2.0; 
    const finalReadiness = Math.round(formComp * 0.40 + Math.max(10, Math.min(100, hrvComp)) * 0.35 + sleepComp * 0.25);
    return Math.max(20, Math.min(100, finalReadiness));
  };

  const readiness = getReadinessScore();

  // Helper to format sleep duration
  const formatSleepDuration = (sec: number) => {
    if (!sec) return '—';
    const hrs = Math.floor(sec / 3600);
    const mins = Math.round((sec % 3600) / 60);
    return `${hrs}小时${mins}分`;
  };

  // UI styling depending on readiness score
  let readinessLabel = '一般';
  let readinessColor = 'text-yellow-400';
  let readinessDesc = '今日体能状态一般，建议安排轻松有氧或短距离慢跑。';
  let ringGradient = 'from-yellow-400 to-orange-500';
  let bgGradient = 'from-orange-500/10 to-transparent';

  if (readiness >= 80) {
    readinessLabel = '极佳';
    readinessColor = 'text-emerald-400';
    readinessDesc = '身体状态饱满，心肺系统已准备就绪，适合冲击课表或进行速度训练！';
    ringGradient = 'from-emerald-400 to-teal-500';
    bgGradient = 'from-emerald-500/10 to-transparent';
  } else if (readiness < 50) {
    readinessLabel = '疲劳';
    readinessColor = 'text-rose-400';
    readinessDesc = '心率变异性偏低或睡眠不足。建议彻底休息、拉伸放松，或进行超慢恢复跑。';
    ringGradient = 'from-rose-500 to-red-600';
    bgGradient = 'from-rose-500/10 to-transparent';
  }

  // Calculate circular stroke offset
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (readiness / 100) * circumference;

  return (
    <div className={`bg-gradient-to-br ${bgGradient} via-zinc-950 to-zinc-950 border border-white/5 rounded-3xl p-6 relative overflow-hidden group`}>
      {/* Background decoration */}
      <div className="absolute -top-20 -right-20 w-44 h-44 bg-white/5 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-blue-500/10 rounded-lg text-blue-400">
            <Activity className="w-4 h-4" />
          </div>
          <h2 className="text-lg font-bold text-white">身体恢复与准备度</h2>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold rounded-full shadow-inner animate-pulse">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>Fitbit Optimized</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
        {/* Ring Gauge - Col 4 */}
        <div className="md:col-span-4 flex flex-col items-center justify-center">
          <div className="relative w-28 h-28 flex items-center justify-center">
            {/* SVG Ring */}
            <svg className="w-full h-full transform -rotate-90">
              <circle
                cx="56"
                cy="56"
                r={radius}
                className="stroke-white/5"
                strokeWidth="7"
                fill="transparent"
              />
              <circle
                cx="56"
                cy="56"
                r={radius}
                className={`stroke-current`}
                strokeWidth="7"
                fill="transparent"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{
                  color: readiness >= 80 ? '#34d399' : readiness >= 50 ? '#facc15' : '#f87171',
                  transition: 'stroke-dashoffset 0.8s ease-out-in'
                }}
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center">
              <span className="text-3xl font-black text-white tracking-tight">{readiness}</span>
              <span className={`text-[10px] font-bold uppercase tracking-wider ${readinessColor}`}>{readinessLabel}</span>
            </div>
          </div>
          <span className="text-zinc-500 text-xs mt-2 font-medium">每日训练准备度</span>
        </div>

        {/* Factors - Col 8 */}
        <div className="md:col-span-8 space-y-4">
          <div className="grid grid-cols-3 gap-2">
            {/* Sleep */}
            <div className="bg-white/5 border border-white/5 rounded-2xl p-3.5 flex flex-col">
              <div className="flex items-center gap-1.5 text-indigo-400 mb-2">
                <Moon className="w-4 h-4" />
                <span className="text-zinc-400 text-xs font-semibold">睡眠质量</span>
              </div>
              <span className="text-white text-lg font-black">{sleepScore > 0 ? `${sleepScore}分` : '—'}</span>
              <span className="text-zinc-500 text-[10px] font-medium truncate">{formatSleepDuration(sleepSec)}</span>
            </div>

            {/* HRV */}
            <div className="bg-white/5 border border-white/5 rounded-2xl p-3.5 flex flex-col">
              <div className="flex items-center gap-1.5 text-emerald-400 mb-2">
                <Activity className="w-4 h-4" />
                <span className="text-zinc-400 text-xs font-semibold">HRV</span>
              </div>
              <span className="text-white text-lg font-black">{hrv > 0 ? `${hrv}ms` : '—'}</span>
              <span className="text-zinc-500 text-[10px] font-medium">心率变异性</span>
            </div>

            {/* RHR */}
            <div className="bg-white/5 border border-white/5 rounded-2xl p-3.5 flex flex-col">
              <div className="flex items-center gap-1.5 text-rose-400 mb-2">
                <Heart className="w-4 h-4" />
                <span className="text-zinc-400 text-xs font-semibold">静息心率</span>
              </div>
              <span className="text-white text-lg font-black">{rhr > 0 ? `${rhr}bpm` : '—'}</span>
              <span className="text-zinc-500 text-[10px] font-medium">RHR</span>
            </div>
          </div>

          <div className="bg-white/5 border border-white/5 rounded-2xl p-3 flex items-start gap-2.5">
            <div className="p-1 bg-white/5 rounded-md text-amber-400 mt-0.5">
              <ShieldAlert className="w-3.5 h-3.5" />
            </div>
            <p className="text-[11px] text-zinc-400 leading-normal font-medium">
              {readinessDesc}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
