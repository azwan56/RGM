"use client";

import { useState, useEffect } from "react";
import axios from "@/lib/apiClient";

interface Challenge {
  challenge_id: string;
  title: string;
  type: string;
  target_value: number;
  start_date: string;
  end_date: string;
  status: string;
  participant_count: number;
  description?: string;
  team_name?: string;
}

interface LeaderboardEntry {
  uid: string;
  display_name: string;
  current_value: number;
  rank: number;
}

const TYPE_META: Record<string, { icon: string; unit: string; label: string; color: string }> = {
  total_km:     { icon: "🏃", unit: "km",  label: "总跑量", color: "#FC4C02" },
  run_count:    { icon: "🔢", unit: "次",  label: "跑步次数", color: "#3b82f6" },
  avg_pace:     { icon: "⚡", unit: "min/km", label: "平均配速", color: "#f59e0b" },
  streak_days:  { icon: "🔥", unit: "天",  label: "连续打卡", color: "#ef4444" },
};

export default function ChallengeCard({ challenge, uid }: { challenge: Challenge; uid: string }) {
  const [expanded, setExpanded] = useState(false);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [lbLoading, setLbLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [myValue, setMyValue] = useState<number | null>(null);

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const meta = TYPE_META[challenge.type] || TYPE_META.total_km;

  // Calculate days remaining
  const endDate = new Date(challenge.end_date);
  const today = new Date();
  const daysLeft = Math.max(0, Math.ceil((endDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24)));
  const isEnded = challenge.status === "ended";
  const isUpcoming = challenge.status === "upcoming";

  const fetchLeaderboard = async () => {
    setLbLoading(true);
    try {
      const res = await axios.get(`${backendUrl}/api/team/challenge/${challenge.challenge_id}/leaderboard`);
      setLeaderboard(res.data.leaderboard || []);
      const mine = res.data.leaderboard?.find((e: LeaderboardEntry) => e.uid === uid);
      if (mine) setMyValue(mine.current_value);
    } catch { /* noop */ }
    setLbLoading(false);
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await axios.post(`${backendUrl}/api/team/challenge/${challenge.challenge_id}/sync`, {
        uid, challenge_id: challenge.challenge_id,
      });
      setMyValue(res.data.current_value);
      fetchLeaderboard();
    } catch { /* noop */ }
    setSyncing(false);
  };

  const handleJoin = async () => {
    try {
      await axios.post(`${backendUrl}/api/team/challenge/${challenge.challenge_id}/join`, {
        uid, challenge_id: challenge.challenge_id,
      });
      fetchLeaderboard();
    } catch { /* noop */ }
  };

  useEffect(() => {
    if (expanded) fetchLeaderboard();
  }, [expanded]);

  const progress = myValue != null && challenge.target_value > 0
    ? Math.min(100, (myValue / challenge.target_value) * 100)
    : 0;

  const statusBadge = isEnded
    ? { text: "已结束", cls: "bg-zinc-700/50 text-zinc-500" }
    : isUpcoming
    ? { text: "未开始", cls: "bg-blue-500/10 text-blue-400" }
    : { text: `${daysLeft}天`, cls: "bg-emerald-500/10 text-emerald-400" };

  return (
    <div className={`bg-white/5 border rounded-2xl overflow-hidden transition-all ${
      isEnded ? "border-white/5 opacity-70" : "border-white/10 hover:border-white/20"
    }`}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-5 text-left"
      >
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">{meta.icon}</span>
            <div>
              <h4 className="text-sm font-bold text-white">{challenge.title}</h4>
              <p className="text-[10px] text-zinc-500">{meta.label} · {challenge.participant_count} 人参与</p>
            </div>
          </div>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${statusBadge.cls}`}>
            {statusBadge.text}
          </span>
        </div>

        {/* Progress bar */}
        <div className="mt-3">
          <div className="flex justify-between text-xs mb-1.5">
            <span className="text-zinc-400">
              {myValue != null ? `${myValue} / ${challenge.target_value} ${meta.unit}` : "点击查看"}
            </span>
            <span className="text-zinc-500">{progress.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{ width: `${progress}%`, background: `linear-gradient(90deg, ${meta.color}, ${meta.color}cc)` }}
            />
          </div>
        </div>

        {/* Date range */}
        <p className="text-[10px] text-zinc-600 mt-2">
          {challenge.start_date} → {challenge.end_date}
        </p>
      </button>

      {/* Expanded: leaderboard */}
      {expanded && (
        <div className="border-t border-white/5 px-5 pb-5">
          <div className="flex items-center justify-between pt-4 pb-3">
            <p className="text-xs font-bold text-zinc-400 uppercase">排行榜</p>
            <div className="flex gap-2">
              <button onClick={handleJoin}
                className="text-[10px] px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/8 text-zinc-400 hover:text-white transition-all">
                加入
              </button>
              <button onClick={handleSync} disabled={syncing}
                className="text-[10px] px-2 py-1 rounded-lg bg-[#FC4C02]/10 hover:bg-[#FC4C02]/20 border border-[#FC4C02]/20 text-[#FC4C02] transition-all font-bold">
                {syncing ? "同步中..." : "同步我的数据"}
              </button>
            </div>
          </div>

          {lbLoading ? (
            <div className="space-y-2">
              {[1,2,3].map(i => <div key={i} className="h-10 bg-white/3 rounded-xl animate-pulse" />)}
            </div>
          ) : leaderboard.length === 0 ? (
            <p className="text-xs text-zinc-600 text-center py-4">暂无参与者，点击「加入」参加挑战</p>
          ) : (
            <div className="space-y-1.5">
              {leaderboard.map((entry, idx) => {
                const isMe = entry.uid === uid;
                const entryProgress = challenge.target_value > 0
                  ? Math.min(100, (entry.current_value / challenge.target_value) * 100)
                  : 0;
                return (
                  <div key={entry.uid}
                    className={`flex items-center gap-3 py-2 px-3 rounded-xl ${
                      isMe ? "bg-[#FC4C02]/8 border border-[#FC4C02]/20" : "bg-white/3"
                    }`}>
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      idx === 0 ? "bg-yellow-500/20 text-yellow-400" :
                      idx === 1 ? "bg-zinc-400/20 text-zinc-300" :
                      idx === 2 ? "bg-amber-700/20 text-amber-600" :
                      "bg-white/5 text-zinc-500"
                    }`}>
                      {entry.rank}
                    </span>
                    <span className="text-xs font-medium text-white flex-1 truncate">
                      {entry.display_name} {isMe && <span className="text-[#FC4C02]">（我）</span>}
                    </span>
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-white/5 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${entryProgress}%`, background: meta.color }} />
                      </div>
                      <span className="text-xs font-bold text-white min-w-[50px] text-right">
                        {entry.current_value} {meta.unit}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
