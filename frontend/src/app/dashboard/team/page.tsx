"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import { Users, Trophy, Plus, UserPlus, Shield, Sparkles } from "lucide-react";

export default function TeamPage() {
  const [user, setUser] = useState<any>(null);
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [inviteCode, setInviteCode] = useState("");
  const [teamName, setTeamName] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showJoinModal, setShowJoinModal] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadLeaderboard();
      }
    });
  }, []);

  async function loadLeaderboard() {
    try {
      const res = await apiClient.get("/api/team/leaderboard");
      setLeaderboard(res.data || []);
    } catch (e) {
      console.error("Leaderboard load failed:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleJoin(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !inviteCode) return;

    try {
      await apiClient.post("/api/team/join", {
        invite_code: inviteCode,
        user_id: user.id,
      });
      alert("成功加入跑团！");
      setShowJoinModal(false);
      setInviteCode("");
      loadLeaderboard();
    } catch (err: any) {
      alert(err.response?.data?.detail || "加入失败，请检查邀请码");
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!user || !teamName) return;

    try {
      const res = await apiClient.post("/api/team/create", {
        name: teamName,
        owner_id: user.id,
      });
      alert(`跑团【${teamName}】创建成功！专属邀请码：${res.data.invite_code}`);
      setShowCreateModal(false);
      setTeamName("");
      loadLeaderboard();
    } catch (err: any) {
      alert(err.response?.data?.detail || "创建失败");
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black flex items-center gap-2.5">
              <Users className="w-7 h-7 text-[#FC4C02]" />
              跑团战队与排行榜
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              按月度目标完成率与跑量实时竞技，见证团队的共同成长
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowJoinModal(true)}
              className="flex items-center gap-1.5 px-4 py-2 bg-white/5 border border-white/10 hover:bg-white/10 text-white rounded-2xl text-xs font-bold transition-all"
            >
              <UserPlus className="w-4 h-4 text-[#FC4C02]" />
              输入邀请码加入
            </button>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#FC4C02] hover:bg-orange-600 text-white rounded-2xl text-xs font-bold transition-all shadow-md shadow-[#FC4C02]/20"
            >
              <Plus className="w-4 h-4" />
              创建新跑团
            </button>
          </div>
        </div>

        {/* Leaderboard Table */}
        <div className="bg-[#121214] border border-white/10 rounded-3xl p-6 sm:p-8">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
              <Trophy className="w-4 h-4 text-amber-400" /> 本月跑团成员完成率风云榜
            </h2>
            <span className="text-xs text-zinc-500">按完成率降序排列</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-white/10 text-xs text-zinc-500 font-medium uppercase">
                  <th className="py-3 px-4">排名</th>
                  <th className="py-3 px-4">跑者</th>
                  <th className="py-3 px-4">已跑跑量</th>
                  <th className="py-3 px-4">月度目标</th>
                  <th className="py-3 px-4">目标完成率</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {leaderboard.map((item) => (
                  <tr key={item.user_id} className="hover:bg-white/5 transition-all">
                    <td className="py-4 px-4 font-black text-base">
                      {item.rank === 1 ? "🥇 1" : item.rank === 2 ? "🥈 2" : item.rank === 3 ? "🥉 3" : `#${item.rank}`}
                    </td>
                    <td className="py-4 px-4 font-bold text-white">
                      {item.display_name}
                    </td>
                    <td className="py-4 px-4 font-bold text-[#FC4C02]">
                      {item.distance_km} km
                    </td>
                    <td className="py-4 px-4 text-zinc-400">
                      {item.target_km} km
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-3">
                        <span className="font-bold text-white w-12 text-right">{item.progress_pct}%</span>
                        <div className="w-28 h-2 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-[#FC4C02] to-orange-400 rounded-full"
                            style={{ width: `${Math.min(100, item.progress_pct)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Join Modal */}
        {showJoinModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-[#18181b] border border-white/10 rounded-3xl p-6 sm:p-8 max-w-sm w-full">
              <h3 className="text-lg font-bold text-white mb-2">加入跑团</h3>
              <p className="text-xs text-zinc-400 mb-4">输入由团队队长分享的 6 位大写邀请码：</p>
              <form onSubmit={handleJoin} className="space-y-4">
                <input
                  type="text"
                  required
                  placeholder="例如: RGM888"
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-mono tracking-widest text-center uppercase text-white focus:outline-none focus:border-[#FC4C02]"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowJoinModal(false)}
                    className="flex-1 py-2.5 bg-white/5 rounded-xl text-xs text-zinc-400 hover:text-white"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2.5 bg-[#FC4C02] rounded-xl text-xs font-bold text-white hover:bg-orange-600"
                  >
                    确认加入
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Create Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="bg-[#18181b] border border-white/10 rounded-3xl p-6 sm:p-8 max-w-sm w-full">
              <h3 className="text-lg font-bold text-white mb-2">创建跑团战队</h3>
              <p className="text-xs text-zinc-400 mb-4">创建后系统将自动为您生成专属 6 位邀请码：</p>
              <form onSubmit={handleCreate} className="space-y-4">
                <input
                  type="text"
                  required
                  placeholder="输入跑团名称 (例如: 巅峰先锋跑团)"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="flex-1 py-2.5 bg-white/5 rounded-xl text-xs text-zinc-400 hover:text-white"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-2.5 bg-[#FC4C02] rounded-xl text-xs font-bold text-white hover:bg-orange-600"
                  >
                    立即创建
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
