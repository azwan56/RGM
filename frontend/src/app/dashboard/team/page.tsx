"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/firebase";
import axios from "@/lib/apiClient";

interface Team {
  team_id: string;
  name: string;
  description: string;
  member_count: number;
  invite_code: string;
}

export default function TeamPage() {
  const router = useRouter();
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const [uid, setUid] = useState<string | null>(null);
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

  const fetchTeams = useCallback(async (userId: string) => {
    try {
      const res = await axios.get(`${backendUrl}/api/team/my-teams/${userId}`);
      setTeams(res.data.teams || []);
    } catch { /* noop */ }
    setLoading(false);
  }, [backendUrl]);

  useEffect(() => {
    const unsub = auth.onAuthStateChanged((user) => {
      if (!user) { router.push("/"); return; }
      setUid(user.uid);
      fetchTeams(user.uid);
    });
    return () => unsub();
  }, [router, fetchTeams]);

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
      fetchTeams(uid);
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
      fetchTeams(uid);
    } catch (e: any) {
      setMessage({ text: e?.response?.data?.detail || "加入失败", type: "error" });
    }
    setJoining(false);
  };

  const inputCls = "w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm outline-none focus:border-[#FC4C02]/60 transition-all placeholder:text-zinc-600";

  if (loading) {
    return (
      <div className="min-h-screen bg-[#09090b] flex items-center justify-center">
        <div className="w-10 h-10 border-2 border-[#FC4C02] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#09090b] text-white">
      {/* Top bar */}
      <header className="sticky top-0 z-40 border-b border-white/5 bg-[#09090b]/90 backdrop-blur-xl">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 hover:bg-white/12 border border-white/8 text-zinc-300 hover:text-white transition-all text-sm font-medium"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              返回
            </Link>
            <h1 className="text-base font-bold text-white flex items-center gap-2">
              <svg className="w-5 h-5 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              我的团队
            </h1>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => { setShowJoin(!showJoin); setShowCreate(false); }}
              className="px-4 py-2 rounded-xl text-sm font-semibold bg-white/5 border border-white/10 hover:bg-white/10 transition-all"
            >
              加入团队
            </button>
            <button
              onClick={() => { setShowCreate(!showCreate); setShowJoin(false); }}
              className="px-4 py-2 rounded-xl text-sm font-semibold transition-all"
              style={{ background: "#FC4C02" }}
            >
              创建团队
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">

        {/* Message banner */}
        {message && (
          <div className={`px-4 py-3 rounded-xl text-sm font-medium flex items-center justify-between ${
            message.type === "success" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                       : "bg-red-500/10 text-red-400 border border-red-500/20"
          }`}>
            {message.text}
            <button onClick={() => setMessage(null)} className="text-xs opacity-60 hover:opacity-100">✕</button>
          </div>
        )}

        {/* Create form */}
        {showCreate && (
          <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-zinc-300">创建新团队</h3>
            <input className={inputCls} placeholder="团队名称" value={newName} onChange={e => setNewName(e.target.value)} />
            <input className={inputCls} placeholder="描述（可选）" value={newDesc} onChange={e => setNewDesc(e.target.value)} />
            <button onClick={handleCreate} disabled={creating || !newName.trim()}
              className="px-6 py-2.5 rounded-xl text-sm font-bold disabled:opacity-50 transition-all"
              style={{ background: "#FC4C02" }}>
              {creating ? "创建中..." : "创建"}
            </button>
          </div>
        )}

        {/* Join form */}
        {showJoin && (
          <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-zinc-300">输入邀请码加入团队</h3>
            <input
              className={`${inputCls} text-center text-xl tracking-[0.3em] uppercase font-mono`}
              placeholder="ABC123"
              maxLength={6}
              value={joinCode}
              onChange={e => setJoinCode(e.target.value.toUpperCase())}
            />
            <button onClick={handleJoin} disabled={joining || joinCode.length < 4}
              className="px-6 py-2.5 rounded-xl text-sm font-bold disabled:opacity-50 transition-all bg-white/10 hover:bg-white/15 border border-white/10">
              {joining ? "加入中..." : "加入团队"}
            </button>
          </div>
        )}

        {/* Team list */}
        {teams.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-20 h-20 mx-auto mb-6 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center">
              <svg className="w-10 h-10 text-zinc-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <p className="text-zinc-400 font-semibold">还没有加入任何团队</p>
            <p className="text-zinc-600 text-sm mt-2">创建一个团队或使用邀请码加入</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {teams.map(team => (
              <button
                key={team.team_id}
                onClick={() => router.push(`/dashboard/team/${team.team_id}`)}
                className="bg-white/5 border border-white/10 hover:border-[#FC4C02]/30 hover:bg-white/8 rounded-3xl p-6 text-left transition-all group"
              >
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-[#FC4C02] transition-colors">
                      {team.name}
                    </h3>
                    {team.description && (
                      <p className="text-zinc-500 text-sm mt-1">{team.description}</p>
                    )}
                  </div>
                  <div className="bg-[#FC4C02]/10 text-[#FC4C02] px-3 py-1 rounded-full text-xs font-bold flex-shrink-0">
                    {team.member_count} 人
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-zinc-500">
                  <span>邀请码：</span>
                  <span className="font-mono bg-white/5 px-2 py-0.5 rounded text-zinc-300">{team.invite_code}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
