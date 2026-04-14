"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { auth } from "@/lib/firebase";
import axios from "@/lib/apiClient";
import ChallengeCard from "@/components/ChallengeCard";

interface Member { uid: string; display_name: string; }
interface Challenge {
  challenge_id: string; title: string; type: string; target_value: number;
  start_date: string; end_date: string; status: string; participant_count: number;
  description?: string; team_name?: string;
}

export default function TeamDetailPage() {
  const router = useRouter();
  const params = useParams();
  const teamId = params.teamId as string;
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const [uid, setUid] = useState<string | null>(null);
  const [teamName, setTeamName] = useState("");
  const [teamDesc, setTeamDesc] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [loading, setLoading] = useState(true);

  // Create challenge form
  const [showForm, setShowForm] = useState(false);
  const [cTitle, setCTitle] = useState("");
  const [cType, setCType] = useState("total_km");
  const [cTarget, setCTarget] = useState(100);
  const [cStart, setCStart] = useState(new Date().toISOString().slice(0, 10));
  const [cEnd, setCEnd] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() + 30);
    return d.toISOString().slice(0, 10);
  });
  const [cDesc, setCDesc]   = useState("");
  const [creating, setCreating] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchData = useCallback(async (userId: string) => {
    try {
      const [teamRes, challengeRes] = await Promise.all([
        axios.get(`${backendUrl}/api/team/${teamId}`),
        axios.get(`${backendUrl}/api/team/${teamId}/challenges`),
      ]);
      const t = teamRes.data;
      setTeamName(t.name || "");
      setTeamDesc(t.description || "");
      setInviteCode(t.invite_code || "");
      setMembers(t.members_info || []);
      setChallenges(challengeRes.data.challenges || []);
    } catch { /* noop */ }
    setLoading(false);
  }, [backendUrl, teamId]);

  useEffect(() => {
    const unsub = auth.onAuthStateChanged((user) => {
      if (!user) { router.push("/"); return; }
      setUid(user.uid);
      fetchData(user.uid);
    });
    return () => unsub();
  }, [router, fetchData]);

  const handleCreate = async () => {
    if (!uid || !cTitle.trim()) return;
    setCreating(true);
    try {
      await axios.post(`${backendUrl}/api/team/${teamId}/challenge`, {
        uid, team_id: teamId, title: cTitle.trim(), type: cType,
        target_value: cTarget, start_date: cStart, end_date: cEnd,
        description: cDesc.trim(),
      });
      setShowForm(false);
      setCTitle("");
      fetchData(uid);
    } catch { /* noop */ }
    setCreating(false);
  };

  const copyInvite = () => {
    navigator.clipboard.writeText(inviteCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const TYPE_OPTIONS = [
    { value: "total_km",     label: "总跑量 (km)" },
    { value: "run_count",    label: "跑步次数" },
    { value: "avg_pace",     label: "平均配速" },
    { value: "streak_days",  label: "连续打卡天数" },
  ];

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
      <header className="sticky top-0 z-40 border-b border-white/5 bg-[#09090b]/90 backdrop-blur-xl">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push("/dashboard/team")}
              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 hover:bg-white/12 border border-white/8 text-zinc-300 hover:text-white transition-all text-sm font-medium">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              返回
            </button>
            <h1 className="text-base font-bold text-white">{teamName}</h1>
          </div>
          <button onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 rounded-xl text-sm font-semibold transition-all" style={{ background: "#FC4C02" }}>
            创建挑战
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">

        {/* Team info */}
        <div className="bg-white/5 border border-white/10 rounded-3xl p-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <h2 className="text-2xl font-black text-white mb-1">{teamName}</h2>
              {teamDesc && <p className="text-zinc-400 text-sm">{teamDesc}</p>}
            </div>
            <div className="flex items-center gap-3">
              <div className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl">
                <p className="text-[10px] text-zinc-500 uppercase mb-0.5">邀请码</p>
                <p className="text-lg font-mono font-bold tracking-wider text-white">{inviteCode}</p>
              </div>
              <button onClick={copyInvite}
                className="px-3 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-all">
                <span className="text-xs">{copied ? "✅" : "📋"}</span>
              </button>
            </div>
          </div>

          {/* Members */}
          <div className="mt-6 pt-4 border-t border-white/5">
            <p className="text-xs text-zinc-500 font-bold uppercase mb-3">成员 ({members.length})</p>
            <div className="flex flex-wrap gap-2">
              {members.map(m => (
                <div key={m.uid}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border ${
                    m.uid === uid ? "bg-[#FC4C02]/10 border-[#FC4C02]/30 text-[#FC4C02]"
                                 : "bg-white/5 border-white/10 text-zinc-300"
                  }`}>
                  {m.display_name} {m.uid === uid && "（我）"}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Create challenge form */}
        {showForm && (
          <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-zinc-300">创建新挑战</h3>
            <input className={inputCls} placeholder="挑战名称" value={cTitle} onChange={e => setCTitle(e.target.value)} />
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">挑战类型</label>
                <select className={inputCls} value={cType} onChange={e => setCType(e.target.value)}>
                  {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">目标值</label>
                <input type="number" className={inputCls} value={cTarget} onChange={e => setCTarget(Number(e.target.value))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">开始日期</label>
                <input type="date" className={inputCls} value={cStart} onChange={e => setCStart(e.target.value)} />
              </div>
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">结束日期</label>
                <input type="date" className={inputCls} value={cEnd} onChange={e => setCEnd(e.target.value)} />
              </div>
            </div>
            <input className={inputCls} placeholder="描述（可选）" value={cDesc} onChange={e => setCDesc(e.target.value)} />
            <button onClick={handleCreate} disabled={creating || !cTitle.trim()}
              className="px-6 py-2.5 rounded-xl text-sm font-bold disabled:opacity-50" style={{ background: "#FC4C02" }}>
              {creating ? "创建中..." : "创建挑战"}
            </button>
          </div>
        )}

        {/* Challenges */}
        <div>
          <h3 className="text-sm font-bold text-zinc-400 uppercase mb-4">团队挑战</h3>
          {challenges.length === 0 ? (
            <div className="text-center py-16 text-zinc-600 text-sm">
              暂无挑战，点击右上角创建一个吧！
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {challenges.map(c => (
                <ChallengeCard key={c.challenge_id} challenge={c} uid={uid!} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
