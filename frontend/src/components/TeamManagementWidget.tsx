"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import axios from "@/lib/apiClient";

interface Team {
  team_id: string;
  name: string;
  description: string;
  member_count: number;
  invite_code: string;
}

export default function TeamManagementWidget({ uid }: { uid: string }) {
  const router = useRouter();
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState<Team[]>([]);

  // Create team form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  // Join team
  const [showJoin, setShowJoin] = useState(false);
  const [joinCode, setJoinCode] = useState("");
  const [joining, setJoining] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const fetchTeams = useCallback(async () => {
    if (!uid) return;
    try {
      const res = await axios.get(`${backendUrl}/api/team/my-teams/${uid}`);
      setTeams(res.data.teams || []);
    } catch { /* noop */ }
    setLoading(false);
  }, [backendUrl, uid]);

  useEffect(() => {
    fetchTeams();
  }, [fetchTeams]);

  const handleCreate = async () => {
    if (!uid || !newName.trim()) return;
    setCreating(true);
    try {
      const res = await axios.post(`${backendUrl}/api/team/create`, {
        uid, name: newName.trim(), description: newDesc.trim(),
      });
      setMessage({ text: `团队创建成功！邀请码：${res.data.invite_code}`, type: "success" });
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
      fetchTeams();
    } catch (e: any) {
      setMessage({ text: e?.response?.data?.detail || "创建失败", type: "error" });
    }
    setCreating(false);
  };

  const handleJoin = async () => {
    if (!uid || !joinCode.trim()) return;
    setJoining(true);
    try {
      const res = await axios.post(`${backendUrl}/api/team/join`, {
        uid, invite_code: joinCode.trim().toUpperCase(),
      });
      setMessage({ text: res.data.message, type: "success" });
      setShowJoin(false);
      setJoinCode("");
      fetchTeams();
    } catch (e: any) {
      setMessage({ text: e?.response?.data?.detail || "加入失败", type: "error" });
    }
    setJoining(false);
  };

  const inputCls = "w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm outline-none focus:border-[#FC4C02]/60 transition-all placeholder:text-zinc-600";

  if (loading) {
    return (
      <div className="bg-white/3 border border-white/8 rounded-3xl p-6 flex justify-center items-center h-48">
        <div className="w-8 h-8 border-2 border-[#FC4C02] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-2">
          <div className="w-3 h-px bg-zinc-600" />
          👥 我的团队
        </h3>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowJoin(!showJoin); setShowCreate(false); }}
            className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-white/5 border border-white/10 hover:bg-white/10 transition-all"
          >
            加入团队
          </button>
          <button
            onClick={() => { setShowCreate(!showCreate); setShowJoin(false); }}
            className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
            style={{ background: "#FC4C02" }}
          >
            创建团队
          </button>
        </div>
      </div>

      {message && (
        <div className={`px-4 py-3 rounded-xl text-xs font-medium flex items-center justify-between ${
          message.type === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                     : "bg-red-500/10 text-red-400 border border-red-500/20"
        }`}>
          {message.text}
          <button onClick={() => setMessage(null)} className="opacity-60 hover:opacity-100">✕</button>
        </div>
      )}

      {showCreate && (
        <div className="bg-black/20 border border-white/5 rounded-2xl p-4 space-y-3">
          <h4 className="text-xs font-bold text-zinc-300">创建新团队</h4>
          <input className={inputCls} placeholder="团队名称" value={newName} onChange={e => setNewName(e.target.value)} />
          <input className={inputCls} placeholder="描述（可选）" value={newDesc} onChange={e => setNewDesc(e.target.value)} />
          <button onClick={handleCreate} disabled={creating || !newName.trim()}
            className="px-6 py-2 rounded-xl text-xs font-bold disabled:opacity-50 transition-all"
            style={{ background: "#FC4C02" }}>
            {creating ? "创建中..." : "创建"}
          </button>
        </div>
      )}

      {showJoin && (
        <div className="bg-black/20 border border-white/5 rounded-2xl p-4 space-y-3">
          <h4 className="text-xs font-bold text-zinc-300">输入邀请码加入团队</h4>
          <input
            className={`${inputCls} text-center text-lg tracking-[0.3em] uppercase font-mono`}
            placeholder="ABC123"
            maxLength={6}
            value={joinCode}
            onChange={e => setJoinCode(e.target.value.toUpperCase())}
          />
          <button onClick={handleJoin} disabled={joining || joinCode.length < 4}
            className="px-6 py-2 rounded-xl text-xs font-bold disabled:opacity-50 transition-all bg-white/10 hover:bg-white/15 border border-white/10">
            {joining ? "加入中..." : "加入团队"}
          </button>
        </div>
      )}

      {teams.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-zinc-500 text-sm">还没有加入任何团队</p>
          <p className="text-zinc-600 text-xs mt-1">创建一个团队或使用邀请码加入</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {teams.map(team => (
            <button
              key={team.team_id}
              onClick={() => router.push(`/dashboard/team/${team.team_id}`)}
              className="bg-white/5 border border-white/10 hover:border-[#FC4C02]/30 hover:bg-white/8 rounded-2xl p-5 text-left transition-all group"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-base font-bold text-white group-hover:text-[#FC4C02] transition-colors">
                    {team.name}
                  </h3>
                  {team.description && (
                    <p className="text-zinc-500 text-xs mt-1">{team.description}</p>
                  )}
                </div>
                <div className="bg-[#FC4C02]/10 text-[#FC4C02] px-2 py-0.5 rounded flex-shrink-0 text-[10px] font-bold">
                  {team.member_count} 人
                </div>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
                <span>邀请码：</span>
                <span className="font-mono bg-white/5 px-1.5 py-0.5 rounded text-zinc-300">{team.invite_code}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
