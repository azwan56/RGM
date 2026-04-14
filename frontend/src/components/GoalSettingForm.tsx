"use client";

import { useState, useEffect } from "react";
import { auth, db } from "@/lib/firebase";
import { doc, getDoc, setDoc } from "firebase/firestore";

const MONTHS_CN = ["1月","2月","3月","4月","5月","6月",
                   "7月","8月","9月","10月","11月","12月"];

// Returns a default monthly target array from overall target (12 values)
function defaultMonthlyTargets(overall: number): number[] {
  return Array(12).fill(overall);
}

export default function GoalSettingForm() {
  const [loading, setLoading] = useState(false);

  // Goals
  const [period,   setPeriod]   = useState<"weekly" | "monthly">("monthly");
  const [distance, setDistance] = useState<number | "">(300);
  const [pace,     setPace]     = useState("");

  // Per-month targets (1–12 index, stored 0-based)
  const [monthlyTargets, setMonthlyTargets] = useState<number[]>(defaultMonthlyTargets(300));
  const [showMonthly,    setShowMonthly]    = useState(false);

  // Physiology
  const [maxHr,  setMaxHr]  = useState<number | "">(190);
  const [restHr, setRestHr] = useState<number | "">(60);

  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Load
  useEffect(() => {
    const fetchData = async () => {
      const user = auth.currentUser;
      if (!user) return;

      const goalRef  = doc(db, "users", user.uid, "goals", "current");
      const goalSnap = await getDoc(goalRef);
      if (goalSnap.exists()) {
        const data = goalSnap.data();
        setPeriod(data.period || "monthly");
        const overall = data.target_distance || 300;
        setDistance(overall);
        setPace(data.target_pace || "");
        // Load per-month targets if stored, else derive from overall
        if (data.monthly_targets && Array.isArray(data.monthly_targets)) {
          setMonthlyTargets(data.monthly_targets);
        } else {
          setMonthlyTargets(defaultMonthlyTargets(overall));
        }
      }

      const userRef  = doc(db, "users", user.uid);
      const userSnap = await getDoc(userRef);
      if (userSnap.exists()) {
        const udata = userSnap.data();
        if (udata.max_heart_rate)    setMaxHr(udata.max_heart_rate);
        if (udata.resting_heart_rate) setRestHr(udata.resting_heart_rate);
      }
    };
    fetchData();
  }, []);

  // When overall distance changes, sync all months that still equal the old value
  const handleOverallChange = (val: number | "") => {
    setDistance(val);
    if (val && !showMonthly) {
      setMonthlyTargets(defaultMonthlyTargets(Number(val)));
    }
  };

  const setMonthTarget = (idx: number, val: string) => {
    const n = val === "" ? 0 : Math.max(0, parseInt(val, 10) || 0);
    setMonthlyTargets(prev => prev.map((v, i) => (i === idx ? n : v)));
  };

  // Apply same value to all remaining months (from current month onward)
  const applyToRemaining = (fromIdx: number, val: number) => {
    const nowMonth = new Date().getMonth(); // 0-based
    setMonthlyTargets(prev => prev.map((v, i) => (i >= Math.max(fromIdx, nowMonth) ? val : v)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!auth.currentUser) return;

    setLoading(true);
    setMessage(null);

    try {
      const uid     = auth.currentUser.uid;
      const goalRef = doc(db, "users", uid, "goals", "current");
      await setDoc(goalRef, {
        period,
        target_distance:  Number(distance),
        monthly_targets:  monthlyTargets,
        target_pace:      pace,
        updated_at:       new Date().toISOString(),
      }, { merge: true });

      const userRef = doc(db, "users", uid);
      await setDoc(userRef, {
        max_heart_rate:    Number(maxHr),
        resting_heart_rate: Number(restHr),
      }, { merge: true });

      setMessage({ text: "设置已保存！", type: "success" });
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      console.error(error);
      setMessage({ text: "保存失败，请重试", type: "error" });
    }
    setLoading(false);
  };

  const nowMonth = new Date().getMonth(); // 0-based
  const totalAnnual = monthlyTargets.reduce((a, b) => a + b, 0);

  return (
    <div className="bg-white/5 border border-white/10 backdrop-blur-md p-6 rounded-3xl w-full">
      <h2 className="text-xl font-bold text-white mb-6">训练目标设置</h2>

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* ── Tracking Period ─────────────────────────────────────────── */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-zinc-300 border-b border-white/10 pb-2">统计周期</h3>
          <div className="flex gap-4">
            {(["weekly", "monthly"] as const).map(p => (
              <label key={p} className="flex-1 cursor-pointer">
                <input type="radio" value={p} checked={period === p} onChange={() => setPeriod(p)} className="sr-only peer" />
                <div className="text-center py-2 rounded-xl text-sm border border-white/10 text-zinc-400 peer-checked:bg-white/10 peer-checked:text-white peer-checked:border-white/30 transition-all">
                  {p === "weekly" ? "每周" : "每月"}
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* ── Distance Goal ────────────────────────────────────────────── */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-zinc-300 border-b border-white/10 pb-2">跑量目标</h3>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-zinc-400 text-xs font-medium mb-2">
                {period === "weekly" ? "周目标 (km)" : "月默认目标 (km)"}
              </label>
              <input
                type="number" required min="1"
                value={distance}
                onChange={e => handleOverallChange(e.target.value ? Number(e.target.value) : "")}
                className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-[#FC4C02]/60 transition-all"
              />
            </div>
            <div>
              <label className="block text-zinc-400 text-xs font-medium mb-2">目标配速 (/km)</label>
              <input
                type="text" value={pace} onChange={e => setPace(e.target.value)}
                placeholder="5:30"
                className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-[#FC4C02]/60 transition-all"
              />
            </div>
          </div>

          {/* Per-month targets — only show for monthly period */}
          {period === "monthly" && (
            <div>
              <button
                type="button"
                onClick={() => setShowMonthly(!showMonthly)}
                className="flex items-center gap-2 text-xs font-semibold text-[#FC4C02] hover:text-orange-400 transition-colors"
              >
                <svg className={`w-3.5 h-3.5 transition-transform ${showMonthly ? "rotate-90" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
                按月份独立设置跑量目标
                {showMonthly && <span className="text-zinc-500 font-normal">年合计 {totalAnnual} km</span>}
              </button>

              {showMonthly && (
                <div className="mt-3 grid grid-cols-3 sm:grid-cols-4 gap-2">
                  {MONTHS_CN.map((name, idx) => {
                    const isPast    = idx < nowMonth;
                    const isCurrent = idx === nowMonth;
                    return (
                      <div
                        key={idx}
                        className={`rounded-2xl p-2.5 border ${
                          isCurrent
                            ? "border-[#FC4C02]/40 bg-[#FC4C02]/8"
                            : isPast
                            ? "border-white/5 bg-white/3 opacity-60"
                            : "border-white/8 bg-white/3"
                        }`}
                      >
                        <p className="text-[10px] font-bold mb-1.5 flex items-center justify-between">
                          <span className={isCurrent ? "text-[#FC4C02]" : "text-zinc-400"}>{name}</span>
                          {isCurrent && <span className="text-[8px] bg-[#FC4C02]/20 text-[#FC4C02] px-1 rounded">本月</span>}
                        </p>
                        <div className="flex items-center gap-1">
                          <input
                            type="number"
                            min="0"
                            value={monthlyTargets[idx] || ""}
                            onChange={e => setMonthTarget(idx, e.target.value)}
                            className="w-full bg-black/30 border border-white/10 rounded-lg px-2 py-1 text-white text-xs focus:outline-none focus:border-[#FC4C02]/60 transition-all"
                          />
                          <span className="text-[10px] text-zinc-600 flex-shrink-0">km</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Physiology ───────────────────────────────────────────────── */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-zinc-300 border-b border-white/10 pb-2">生理参数</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-zinc-400 text-xs font-medium mb-2">最大心率 (bpm)</label>
              <input
                type="number" required min="100" max="230" value={maxHr}
                onChange={e => setMaxHr(e.target.value ? Number(e.target.value) : "")}
                className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-pink-500 transition-all"
              />
            </div>
            <div>
              <label className="block text-zinc-400 text-xs font-medium mb-2">静息心率 (bpm)</label>
              <input
                type="number" required min="30" max="100" value={restHr}
                onChange={e => setRestHr(e.target.value ? Number(e.target.value) : "")}
                className="w-full bg-black/20 border border-white/10 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-pink-500 transition-all"
              />
            </div>
          </div>
          <p className="text-[10px] text-zinc-500">精确的 TRIMP / 训练状况计算需要此数据</p>
        </div>

        {message && (
          <div className={`p-3 rounded-xl text-xs font-medium ${
            message.type === "success" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
          }`}>
            {message.text}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 rounded-xl text-sm font-bold transition-all border border-white/10 mt-6 disabled:opacity-50"
          style={{ background: loading ? "rgba(255,255,255,0.08)" : "#FC4C02" }}
        >
          {loading ? "保存中..." : "💾 保存设置"}
        </button>
      </form>
    </div>
  );
}
