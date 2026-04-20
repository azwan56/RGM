"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/firebase";
import axios from "@/lib/apiClient";
import Link from "next/link";
import dynamic from "next/dynamic";

const RunnerPersona = dynamic(() => import("@/components/RunnerPersona"), { ssr: false });

// ── Helper: seconds ↔ HH:MM:SS ───────────────────────────────────────────────
function secsToTime(s: number): string {
  if (!s || s <= 0) return "";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function timeToSecs(t: string): number {
  if (!t) return 0;
  const parts = t.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

// ── Sub-components ────────────────────────────────────────────────────────────
function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-bold uppercase tracking-widest text-zinc-500 mb-4 flex items-center gap-2">
      <div className="w-3 h-px bg-zinc-600" />
      {children}
    </h3>
  );
}

function Field({
  label, children, hint
}: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <label className="block text-xs text-zinc-500 mb-1.5 font-medium">{label}</label>
      {children}
      {hint && <p className="text-[10px] text-zinc-600 mt-1">{hint}</p>}
    </div>
  );
}

const inputCls = "w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm outline-none focus:border-[#FC4C02]/60 focus:bg-white/8 transition-all placeholder:text-zinc-600";
const selectCls = "w-full bg-[#18181b] border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm outline-none focus:border-[#FC4C02]/60 transition-all";

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function ProfilePage() {
  const router = useRouter();
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const [uid, setUid]             = useState<string | null>(null);
  const [email, setEmail]         = useState("");
  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);
  const [saved, setSaved]         = useState(false);
  const [persona, setPersona]     = useState<any>(null);
  const [personaLoading, setPersonaLoading] = useState(false);
  const [importingPBs, setImportingPBs]     = useState(false);
  const [pbSources, setPbSources]           = useState<Record<string, string>>({});
  const [importResult, setImportResult]     = useState<string | null>(null);

  // Form state
  const [form, setForm] = useState({
    display_name:    "",
    phone:           "",
    date_of_birth:   "",   // YYYY-MM-DD
    gender:          "",
    years_running:   "",
    height_cm:       "",
    weight_kg:       "",
    training_goal:   "",
    bio:             "",
    marathon_pb:     "",  // HH:MM:SS string
    half_pb:         "",
    ten_k_pb:        "",
    five_k_pb:       "",
    discord_webhook_url: "",
    wecom_webhook_url:   "",
  });

  // Race plan — separate state, up to 3 races
  interface RaceEntry { name: string; type: string; date: string; target_time: string }
  const emptyRace = (): RaceEntry => ({ name: "", type: "", date: "", target_time: "" });
  const [races, setRaces] = useState<RaceEntry[]>([]);

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  // Load profile
  useEffect(() => {
    const unsub = auth.onAuthStateChanged(async (user) => {
      if (!user) { router.push("/"); return; }
      setUid(user.uid);
      setEmail(user.email || "");
      // Pre-fill phone from Firebase auth if signed-in via phone
      if (user.phoneNumber && !user.email) {
        setForm(f => ({ ...f, phone: f.phone || user.phoneNumber || "" }));
      }

      try {
        const res = await axios.get(`${backendUrl}/api/profile/${user.uid}`);
        const p = res.data;
        setForm({
          display_name:  p.display_name || p.strava_name || "",
          phone:         p.phone || "",
          date_of_birth: p.date_of_birth || "",
          gender:        p.gender || "",
          years_running: p.years_running?.toString() || "",
          height_cm:     p.height_cm?.toString() || "",
          weight_kg:     p.weight_kg?.toString() || "",
          training_goal: p.training_goal || "",
          bio:           p.bio || "",
          marathon_pb:   secsToTime(p.marathon_pb_sec),
          half_pb:       secsToTime(p.half_pb_sec),
          ten_k_pb:      secsToTime(p.ten_k_pb_sec),
          five_k_pb:     secsToTime(p.five_k_pb_sec),
          discord_webhook_url: p.discord_webhook_url || "",
          wecom_webhook_url:   p.wecom_webhook_url || "",
        });
        // Load races — filter out past ones
        const savedRaces = (p.upcoming_races || []).filter((r: any) => {
          if (!r.date) return true;
          return new Date(r.date).getTime() >= Date.now() - 86400000;
        });
        setRaces(savedRaces);
      } catch { /* user might be new */ }

      setLoading(false);

      // Load persona (separate, lazy)
      setPersonaLoading(true);
      try {
        const pr = await axios.get(`${backendUrl}/api/profile/${user.uid}/persona`);
        setPersona(pr.data);
      } catch { setPersona(null); }
      setPersonaLoading(false);
    });
    return () => unsub();
  }, [backendUrl, router]);

  // Save
  const handleSave = useCallback(async () => {
    if (!uid) return;
    setSaving(true);
    try {
      await axios.post(`${backendUrl}/api/profile/update`, {
        uid,
        display_name:   form.display_name || undefined,
        phone:          form.phone || undefined,
        date_of_birth:  form.date_of_birth || undefined,
        gender:         form.gender || undefined,
        years_running:  form.years_running ? parseInt(form.years_running) : undefined,
        height_cm:      form.height_cm ? parseFloat(form.height_cm) : undefined,
        weight_kg:      form.weight_kg ? parseFloat(form.weight_kg) : undefined,
        training_goal:  form.training_goal || undefined,
        bio:            form.bio || undefined,
        marathon_pb_sec: timeToSecs(form.marathon_pb) || undefined,
        half_pb_sec:    timeToSecs(form.half_pb) || undefined,
        ten_k_pb_sec:   timeToSecs(form.ten_k_pb) || undefined,
        five_k_pb_sec:  timeToSecs(form.five_k_pb) || undefined,
        upcoming_races: races.filter(r => r.type),  // only send non-empty races
        discord_webhook_url: form.discord_webhook_url || undefined,
        wecom_webhook_url:   form.wecom_webhook_url || undefined,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      // Refresh persona
      const pr = await axios.get(`${backendUrl}/api/profile/${uid}/persona`);
      setPersona(pr.data);
    } catch { alert("保存失败，请重试"); }
    setSaving(false);
  }, [uid, form, races, backendUrl]);

  // Import PBs from Strava
  const handleImportPBs = useCallback(async () => {
    if (!uid) return;
    setImportingPBs(true);
    setImportResult(null);
    try {
      const res = await axios.get(`${backendUrl}/api/profile/${uid}/strava-pbs`);
      const { pbs, auto_saved } = res.data;

      const newSources: Record<string, string> = {};
      const sourceLabel: Record<string, string> = {
        strava_best_effort:    "Strava PR 段落成绩",
        strava_activity:       "Strava 跑步记录",
        estimated_from_pace:   "配速估算",
      };

      setForm(f => ({
        ...f,
        marathon_pb: pbs.marathon ? secsToTime(pbs.marathon.seconds) : f.marathon_pb,
        half_pb:     pbs.half     ? secsToTime(pbs.half.seconds)     : f.half_pb,
        ten_k_pb:    pbs.ten_k    ? secsToTime(pbs.ten_k.seconds)    : f.ten_k_pb,
        five_k_pb:   pbs.five_k   ? secsToTime(pbs.five_k.seconds)   : f.five_k_pb,
      }));

      if (pbs.marathon) newSources["marathon_pb"] = sourceLabel[pbs.marathon.source] || pbs.marathon.source;
      if (pbs.half)     newSources["half_pb"]     = sourceLabel[pbs.half.source]     || pbs.half.source;
      if (pbs.ten_k)    newSources["ten_k_pb"]    = sourceLabel[pbs.ten_k.source]    || pbs.ten_k.source;
      if (pbs.five_k)   newSources["five_k_pb"]   = sourceLabel[pbs.five_k.source]   || pbs.five_k.source;
      setPbSources(newSources);

      const count = [pbs.marathon, pbs.half, pbs.ten_k, pbs.five_k].filter(Boolean).length;
      setImportResult(`✓ 已导入 ${count} 项 PB${auto_saved.length ? "（并自动保存）" : "，请确认后保存"}`);
    } catch {
      setImportResult("导入失败，请确认 Strava 已连接");
    }
    setImportingPBs(false);
  }, [uid, backendUrl]);

  // ── Strava connection status ────────────────────────────────────────────────
  const [stravaConnected, setStravaConnected] = useState(false);
  const [stravaName, setStravaName]           = useState("");

  useEffect(() => {
    if (!uid) return;
    axios.get(`${backendUrl}/api/profile/${uid}`)
      .then(r => {
        setStravaConnected(!!r.data.strava_expires_at);
        setStravaName(r.data.strava_name || "");
      }).catch(() => {});
  }, [uid, backendUrl]);

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
              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 hover:bg-white/12 border border-white/8 hover:border-white/20 text-zinc-300 hover:text-white transition-all text-sm font-medium"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              返回 Dashboard
            </Link>
            <h1 className="text-base font-bold text-white">跑者档案</h1>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-xl text-sm font-semibold transition-all flex items-center gap-2 disabled:opacity-50"
            style={{ background: saved ? "#10b981" : "#FC4C02" }}
          >
            {saving ? (
              <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> 保存中</>
            ) : saved ? (
              <><svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg> 已保存</>
            ) : "保存档案"}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">

        {/* ── Persona Card ─────────────────────────────────────────────────── */}
        <RunnerPersona persona={persona!} loading={personaLoading || !persona} />

        {/* ── Account Info ─────────────────────────────────────────────────── */}
        <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-5">
          <SectionTitle>账号信息</SectionTitle>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="显示名称 / 昵称">
              <input className={inputCls} placeholder="你的跑步江湖名号" value={form.display_name} onChange={set("display_name")} />
            </Field>
            {email && (
              <Field label="注册邮箱" hint="由 Firebase 验证，不可更改">
                <input className={inputCls} value={email} disabled style={{ opacity: 0.5, cursor: "not-allowed" }} />
              </Field>
            )}
            <Field label="手机号码" hint={!email ? "由 Firebase 短信验证，不可更改" : undefined}>
              <input
                className={inputCls}
                placeholder="+86 138..."
                value={form.phone}
                onChange={set("phone")}
                disabled={!email}
                style={!email ? { opacity: 0.5, cursor: "not-allowed" } : {}}
              />
            </Field>
            <Field label="Strava 账号">
              <div className={`${inputCls} flex items-center gap-2 cursor-default`} style={{ opacity: stravaConnected ? 1 : 0.5 }}>
                <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill={stravaConnected ? "#FC4C02" : "#6b7280"}>
                  <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066l-2.084 4.116z"/>
                  <path d="M7.698 13.828l4.806-9.6 4.807 9.6h3.066L11.504 0 4.633 13.828h3.065z"/>
                </svg>
                <span className="text-sm">{stravaConnected ? stravaName || "已连接" : "未连接"}</span>
              </div>
            </Field>
          </div>
        </div>

        {/* ── Runner Profile ────────────────────────────────────────────────── */}
        <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-5">
          <SectionTitle>跑者信息</SectionTitle>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Field label="出生日期">
              <input className={inputCls} type="date" value={form.date_of_birth} onChange={set("date_of_birth")} />
              {form.date_of_birth && (
                <p className="text-[10px] text-zinc-500 mt-1">
                  {(() => {
                    const born = new Date(form.date_of_birth);
                    const today = new Date();
                    let age = today.getFullYear() - born.getFullYear();
                    if (today.getMonth() < born.getMonth() || (today.getMonth() === born.getMonth() && today.getDate() < born.getDate())) age--;
                    return `${age} 岁`;
                  })()}
                </p>
              )}
            </Field>
            <Field label="性别">
              <select className={selectCls} value={form.gender} onChange={set("gender")}>
                <option value="">请选择</option>
                <option value="male">男</option>
                <option value="female">女</option>
                <option value="other">其他</option>
              </select>
            </Field>
            <Field label="身高 (cm)">
              <input className={inputCls} type="number" placeholder="175" min={100} max={250} step={0.1} value={form.height_cm} onChange={set("height_cm")} />
            </Field>
            <Field label="体重 (kg)" hint={form.weight_kg ? undefined : "连接 Strava 可自动导入"}>
              <input className={inputCls} type="number" placeholder="70" min={30} max={200} step={0.1} value={form.weight_kg} onChange={set("weight_kg")} />
            </Field>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="跑龄（年）">
              <input className={inputCls} type="number" placeholder="3" min={0} max={50} value={form.years_running} onChange={set("years_running")} />
            </Field>
          </div>
          <Field label="训练目标">
            <select className={selectCls} value={form.training_goal} onChange={set("training_goal")}>
              <option value="">请选择</option>
              <option value="fitness">保持健康 / 减脂塑形</option>
              <option value="finish_marathon">完成人生第一场马拉松</option>
              <option value="sub4">全马 Sub-4:00</option>
              <option value="sub3_30">全马 Sub-3:30</option>
              <option value="sub3">全马 Sub-3:00（精英挑战）</option>
              <option value="ultra">超马 / 越野挑战</option>
              <option value="pb">持续破 PB</option>
            </select>
          </Field>
          <Field label="跑步简介 / 签名">
            <textarea
              className={`${inputCls} resize-none h-20`}
              placeholder="一句话介绍你的跑步故事..."
              value={form.bio}
              onChange={set("bio")}
            />
          </Field>
        </div>

        {/* ── Race Plan ─────────────────────────────────────────────────────────── */}
        <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-5">
          <div className="flex items-center justify-between">
            <SectionTitle>🏁 比赛计划</SectionTitle>
            {races.length < 3 && (
              <button
                onClick={() => setRaces(r => [...r, emptyRace()])}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-[#FC4C02] text-white hover:bg-[#FC4C02]/80 transition-all"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
                添加比赛
              </button>
            )}
          </div>

          {races.length === 0 && (
            <div className="text-center py-8">
              <p className="text-zinc-500 text-sm">暂无比赛计划</p>
              <p className="text-zinc-600 text-xs mt-1">添加一场比赛，AI 教练会据此定制训练建议</p>
            </div>
          )}

          {races.map((race, idx) => {
            const days = race.date ? Math.ceil((new Date(race.date).getTime() - Date.now()) / 86400000) : null;
            const isPast = days !== null && days < 0;
            if (isPast) return null;

            const raceEmoji: Record<string, string> = {
              "10k": "🏃", "half_marathon": "🥈", "full_marathon": "🏆",
              "gobi": "🏜️", "trail_50k": "⛰️", "trail_100k": "🏔️", "trail_100m": "🔥"
            };
            const raceLabel: Record<string, string> = {
              "10k": "10K 路跑赛", "half_marathon": "半程马拉松", "full_marathon": "全程马拉松",
              "gobi": "戈壁挑战赛 (3天 120K)", "trail_50k": "越野跑 50K",
              "trail_100k": "越野跑 100K", "trail_100m": "越野跑 100英里"
            };

            const updateRace = (field: string, value: string) => {
              setRaces(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));
            };

            return (
              <div key={idx} className={`rounded-2xl p-5 border space-y-4 ${
                race.type === "gobi"
                  ? "bg-gradient-to-r from-amber-500/10 to-red-500/10 border-amber-500/20"
                  : "bg-white/5 border-white/8"
              }`}>
                {/* Race header with delete button */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{raceEmoji[race.type] || "🏁"}</span>
                    <span className="text-sm font-bold text-white">比赛 {idx + 1}</span>
                    {days !== null && days >= 0 && (
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        days <= 30 ? "bg-red-500/20 text-red-400" : days <= 90 ? "bg-amber-500/20 text-amber-400" : "bg-zinc-700/50 text-zinc-400"
                      }`}>
                        {days === 0 ? "今天！" : `${days} 天`}
                        {days > 0 && days <= 30 && " 冲刺"}
                        {days > 30 && days <= 90 && " 关键期"}
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => setRaces(prev => prev.filter((_, i) => i !== idx))}
                    className="w-7 h-7 rounded-lg bg-white/5 hover:bg-red-500/20 border border-white/10 hover:border-red-500/30 flex items-center justify-center transition-all group"
                    title="删除此比赛"
                  >
                    <svg className="w-3.5 h-3.5 text-zinc-500 group-hover:text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* Race fields */}
                <div className="grid sm:grid-cols-2 gap-3">
                  <Field label="比赛名称">
                    <input className={inputCls} placeholder="如：上海马拉松" value={race.name} onChange={e => updateRace("name", e.target.value)} />
                  </Field>
                  <Field label="比赛类型">
                    <select className={selectCls} value={race.type} onChange={e => updateRace("type", e.target.value)}>
                      <option value="">请选择</option>
                      <option value="10k">10K 路跑赛</option>
                      <option value="half_marathon">半程马拉松 (21.0975K)</option>
                      <option value="full_marathon">全程马拉松 (42.195K)</option>
                      <option value="gobi">戈壁挑战赛 (3天 120K)</option>
                      <option value="trail_50k">越野跑 50K</option>
                      <option value="trail_100k">越野跑 100K</option>
                      <option value="trail_100m">越野跑 100英里</option>
                    </select>
                  </Field>
                  <Field label="比赛日期">
                    <input className={inputCls} type="date" value={race.date} onChange={e => updateRace("date", e.target.value)} />
                  </Field>
                  <Field label="目标成绩" hint="如 3:45:00 或 1:50:00">
                    <input className={inputCls} placeholder="H:MM:SS" value={race.target_time} onChange={e => updateRace("target_time", e.target.value)} pattern="[0-9:]*" />
                  </Field>
                </div>

                {/* Gobi special note */}
                {race.type === "gobi" && (
                  <p className="text-amber-400 text-xs flex items-center gap-1.5">
                    <span>☢️</span> 连续3天共120K的竞技性赛事，训练要求激进，需大量耐力储备与越野适应
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* ── Personal Bests ────────────────────────────────────────────────── */}
        <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-5">
          {/* Header row with import button */}
          <div className="flex items-center justify-between">
            <SectionTitle>个人最佳成绩 (PB)</SectionTitle>
            <button
              onClick={handleImportPBs}
              disabled={importingPBs || !stravaConnected}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all disabled:opacity-40"
              style={{ background: "#FC4C02", color: "white" }}
              title={stravaConnected ? "从 Strava 历史记录中自动计算最佳成绩" : "请先连接 Strava"}
            >
              {importingPBs ? (
                <><div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> 分析中...</>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066l-2.084 4.116z"/>
                    <path d="M7.698 13.828l4.806-9.6 4.807 9.6h3.066L11.504 0 4.633 13.828h3.065z"/>
                  </svg>
                  从 Strava 导入
                </>
              )}
            </button>
          </div>

          {/* Import result banner */}
          {importResult && (
            <div className={`text-xs px-3 py-2 rounded-xl flex items-center gap-2 ${
              importResult.startsWith("✓") ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
            }`}>
              {importResult}
            </div>
          )}

          <p className="text-zinc-600 text-xs">格式：H:MM:SS 或 MM:SS &nbsp;·&nbsp; 例如 3:45:30 或 45:10 &nbsp;·&nbsp; 可手动修改导入值</p>

          <div className="grid sm:grid-cols-2 gap-4">
            {[
              { key: "marathon_pb", label: "🏆 全马 PB (42.195km)", placeholder: "3:45:30" },
              { key: "half_pb",     label: "🥈 半马 PB (21.0975km)", placeholder: "1:45:00" },
              { key: "ten_k_pb",   label: "🏅 10K PB",              placeholder: "45:30" },
              { key: "five_k_pb",  label: "⚡ 5K PB",               placeholder: "22:00" },
            ].map(({ key, label, placeholder }) => (
              <Field key={key} label={label}>
                <div className="relative">
                  <input
                    className={inputCls}
                    placeholder={placeholder}
                    value={(form as any)[key]}
                    onChange={set(key)}
                    pattern="[0-9:]*"
                  />
                  {(form as any)[key] && (
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-500">
                      {timeToSecs((form as any)[key]) > 0 ? `${timeToSecs((form as any)[key])}秒` : ""}
                    </span>
                  )}
                </div>
                {/* Source badge — appears after Strava import */}
                {pbSources[key] && (
                  <p className="text-[10px] text-emerald-500 mt-1 flex items-center gap-1">
                    <svg className="w-2.5 h-2.5" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066l-2.084 4.116z"/>
                      <path d="M7.698 13.828l4.806-9.6 4.807 9.6h3.066L11.504 0 4.633 13.828h3.065z"/>
                    </svg>
                    {pbSources[key]}
                  </p>
                )}
              </Field>
            ))}
          </div>

          {/* PB Display Cards */}
          {(form.marathon_pb || form.half_pb || form.ten_k_pb || form.five_k_pb) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
              {[
                { key: "marathon_pb", dist: "全马", color: "#FC4C02" },
                { key: "half_pb",     dist: "半马", color: "#f59e0b" },
                { key: "ten_k_pb",    dist: "10K",  color: "#10b981" },
                { key: "five_k_pb",   dist: "5K",   color: "#3b82f6" },
              ].filter(r => (form as any)[r.key]).map(({ key, dist, color }) => (
                <div key={key} className="bg-white/5 border border-white/8 rounded-2xl p-3 text-center">
                  <p className="text-[10px] text-zinc-500 uppercase tracking-wide">{dist}</p>
                  <p className="text-lg font-black mt-0.5" style={{ color }}>{(form as any)[key]}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        </div>

        {/* ── Notification Webhooks ───────────────────────────────────────────── */}
        <div className="bg-white/3 border border-white/8 rounded-3xl p-6 space-y-5">
          <SectionTitle>🔔 跑步通知</SectionTitle>
          <p className="text-zinc-500 text-xs">
            每次 Strava 同步到新跑步记录后，自动发送通知到你的频道。
          </p>
          <div className="space-y-4">
            {/* Discord */}
            <Field
              label="Discord Webhook URL"
              hint="在你的 Discord 频道设置 → 整合 → Webhook 里创建，粘贴 URL 到这里"
            >
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-lg select-none">🎮</span>
                <input
                  className={`${inputCls} pl-9`}
                  placeholder="https://discord.com/api/webhooks/..."
                  value={form.discord_webhook_url}
                  onChange={set("discord_webhook_url")}
                />
              </div>
              {form.discord_webhook_url && (
                <p className="text-[10px] text-emerald-500 mt-1">✓ 已配置 — 保存后生效</p>
              )}
            </Field>

            {/* WeCom — coming soon */}
            <Field
              label="企业微信机器人 Webhook URL"
              hint="在企业微信群 → 群机器人 → 添加机器人 里创建，粘贴 URL 到这里（功能开发中）"
            >
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-lg select-none">💬</span>
                <input
                  className={`${inputCls} pl-9 opacity-50 cursor-not-allowed`}
                  placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=... （即将上线）"
                  value={form.wecom_webhook_url}
                  onChange={set("wecom_webhook_url")}
                  disabled
                />
              </div>
            </Field>
          </div>
        </div>

        {/* Bottom save */}
        <div className="flex justify-end pb-8">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-8 py-3 rounded-2xl text-sm font-bold transition-all disabled:opacity-50 flex items-center gap-2"
            style={{ background: "#FC4C02" }}
          >
            {saving ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> 保存中...</> : "💾 保存所有修改"}
          </button>
        </div>
      </main>
    </div>
  );
}
