"use client";

import { useState, useEffect, useCallback } from "react";
import axios from "@/lib/apiClient";

interface ActivitySnapshot {
  name: string;
  distance_km: number;
  avg_pace: string;
  avg_heart_rate: number;
  total_elevation_gain: number;
  duration_str: string;
}

interface WeeklyProgress {
  week_km: number;
  week_runs: number;
  target_km: number;
  completion_pct: number;
}

interface NextWeekPlan {
  focus: string;
  target_km: string;
  key_sessions: string[];
  adjustments: string;
}

interface JournalEntry {
  date: string;
  entry_type: "daily" | "weekly_summary";
  activity_id?: string;
  activity_snapshot?: ActivitySnapshot;
  ai_comment?: string;
  fatigue_level?: string;
  performance_note?: string;
  tomorrow_suggestion?: string;
  training_type?: string;
  weekly_progress?: WeeklyProgress;
  // Weekly summary fields
  summary?: string;
  achievements?: string[];
  concerns?: string[];
  next_week_plan?: NextWeekPlan;
  weekly_score?: number;
  week_stats?: { total_km: number; total_runs: number; total_elevation: number };
}

interface Journal {
  title: string;
  race_type: string;
  race_date: string;
  status: string;
  journal_id: string;
}

const fatigueBadge: Record<string, { label: string; cls: string }> = {
  low: { label: "低疲劳", cls: "bg-green-500/15 text-green-400 border-green-500/20" },
  moderate: { label: "中等", cls: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20" },
  high: { label: "高疲劳", cls: "bg-red-500/15 text-red-400 border-red-500/20" },
};

export default function TrainingJournal({ uid }: { uid: string }) {
  const [journal, setJournal] = useState<Journal | null>(null);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [logging, setLogging] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [backfilling, setBackfilling] = useState<string>("");
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const fetchJournal = useCallback(async () => {
    try {
      const res = await axios.get(`${backendUrl}/api/coach/journal?uid=${uid}`);
      setJournal(res.data.journal);
      setEntries(res.data.entries || []);
    } catch (err) {
      console.error("Journal fetch error:", err);
    }
    setLoading(false);
  }, [uid, backendUrl]);

  useEffect(() => { fetchJournal(); }, [fetchJournal]);

  const logLatestActivity = async () => {
    setLogging(true);
    try {
      await axios.post(`${backendUrl}/api/coach/journal/log`, { uid, force: true });
      await fetchJournal();
    } catch (err) {
      console.error("Journal log error:", err);
    }
    setLogging(false);
  };

  const triggerWeeklyReview = async () => {
    setReviewing(true);
    try {
      await axios.post(`${backendUrl}/api/coach/journal/weekly-review`, { uid });
      await fetchJournal();
    } catch (err) {
      console.error("Weekly review error:", err);
    }
    setReviewing(false);
  };

  // Group entries by week
  const groupedByWeek = entries.reduce<Record<string, JournalEntry[]>>((acc, e) => {
    // Parse as UTC to avoid local timezone offset issues
    const dateStr = e.date.split("T")[0];
    const d = new Date(dateStr + "T00:00:00Z");
    const weekStart = new Date(d);
    const day = d.getUTCDay();
    const diff = d.getUTCDate() - day + (day === 0 ? -6 : 1); // Monday is start of week
    weekStart.setUTCDate(diff);
    const key = weekStart.toISOString().slice(0, 10);
    if (!acc[key]) acc[key] = [];
    acc[key].push(e);
    return acc;
  }, {});

  return (
    <div className="bg-white/5 border border-white/10 backdrop-blur-md p-6 lg:p-7 rounded-3xl relative overflow-hidden">
      {/* Background */}
      <div className="absolute -top-20 -left-20 w-64 h-64 bg-purple-600/10 rounded-full blur-[100px] pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between mb-5 z-10 relative">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-xl flex items-center justify-center border border-purple-500/20 shadow-lg">
            <svg className="w-5 h-5 text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <div>
            <h3 className="text-white font-bold text-lg">训练日志</h3>
            {journal && <p className="text-zinc-500 text-xs">{journal.title}</p>}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          <div className="h-20 bg-white/5 rounded-2xl animate-pulse" />
          <div className="h-16 bg-white/5 rounded-2xl animate-pulse" />
          <div className="h-16 bg-white/5 rounded-2xl animate-pulse" />
        </div>
      ) : entries.length === 0 ? (
        <div className="text-center py-10 space-y-3">
          <p className="text-zinc-500 text-sm">暂无训练日志，点击下方记录你的最新训练</p>
        </div>
      ) : (
        <div className="space-y-6 z-10 relative max-h-[600px] overflow-y-auto pr-1 custom-scrollbar">
          {Object.entries(groupedByWeek).sort(([a], [b]) => b.localeCompare(a)).map(([weekKey, weekEntries]) => {
            const weeklySummary = weekEntries.find(e => e.entry_type === "weekly_summary");
            const dailyEntries = weekEntries.filter(e => e.entry_type === "daily").sort((a, b) => b.date.localeCompare(a.date));
            const weekLabel = `${weekKey} 周`;

            return (
              <div key={weekKey} className="space-y-3">
                {/* Week header */}
                <div className="flex items-center gap-3">
                  <div className="h-px flex-1 bg-white/10" />
                  <span className="text-xs text-zinc-500 font-semibold whitespace-nowrap">{weekLabel}</span>
                  <div className="h-px flex-1 bg-white/10" />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
                  {/* Left Column: Weekly Summary */}
                  <div className="space-y-3">
                    {weeklySummary && (
                      <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/5 border border-purple-500/15 p-4 rounded-2xl space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="text-sm font-bold text-purple-300">📊 周度总结</h4>
                          {weeklySummary.weekly_score && (
                            <span className="text-xs font-bold text-white bg-purple-500/20 border border-purple-500/30 px-2 py-0.5 rounded-lg">
                              {weeklySummary.weekly_score}/10
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-zinc-300 leading-relaxed">{weeklySummary.summary}</p>

                        {weeklySummary.week_stats && (
                          <div className="grid grid-cols-3 gap-2">
                            <div className="bg-black/20 rounded-xl p-2 text-center">
                              <span className="text-[10px] text-zinc-500 block">总里程</span>
                              <span className="text-sm font-bold text-white">{weeklySummary.week_stats.total_km}km</span>
                            </div>
                            <div className="bg-black/20 rounded-xl p-2 text-center">
                              <span className="text-[10px] text-zinc-500 block">训练次数</span>
                              <span className="text-sm font-bold text-white">{weeklySummary.week_stats.total_runs}</span>
                            </div>
                            <div className="bg-black/20 rounded-xl p-2 text-center">
                              <span className="text-[10px] text-zinc-500 block">累计爬升</span>
                              <span className="text-sm font-bold text-white">{weeklySummary.week_stats.total_elevation}m</span>
                            </div>
                          </div>
                        )}

                        {weeklySummary.achievements && weeklySummary.achievements.length > 0 && (
                          <div className="space-y-1">
                            {weeklySummary.achievements.map((a, i) => (
                              <div key={i} className="flex items-start gap-2 text-xs text-green-400">
                                <span>✅</span><span>{a}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {weeklySummary.concerns && weeklySummary.concerns.length > 0 && (
                          <div className="space-y-1">
                            {weeklySummary.concerns.map((c, i) => (
                              <div key={i} className="flex items-start gap-2 text-xs text-yellow-400">
                                <span>⚠️</span><span>{c}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {weeklySummary.next_week_plan && (
                          <div className="bg-black/20 border border-white/5 p-3 rounded-xl space-y-1.5">
                            <span className="text-[10px] text-zinc-500 uppercase tracking-wider">下周计划调整</span>
                            <p className="text-xs text-zinc-300"><strong className="text-blue-400">重点：</strong>{weeklySummary.next_week_plan.focus}</p>
                            <p className="text-xs text-zinc-300"><strong className="text-blue-400">跑量：</strong>{weeklySummary.next_week_plan.target_km}</p>
                            {weeklySummary.next_week_plan.adjustments && (
                              <p className="text-xs text-orange-300/80">{weeklySummary.next_week_plan.adjustments}</p>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Right Column: Daily entries */}
                  <div className="space-y-3">
                    {dailyEntries.map((entry, idx) => {
                      const snap = entry.activity_snapshot;
                      const fb = fatigueBadge[entry.fatigue_level || "moderate"] || fatigueBadge.moderate;
                      const prog = entry.weekly_progress;

                      return (
                        <div key={idx} className="bg-black/20 border border-white/5 p-4 rounded-2xl space-y-3 hover:border-white/10 transition-colors group">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-bold text-white">{entry.date}</span>
                              {snap && <span className="text-xs text-zinc-500">{snap.name}</span>}
                              {entry.training_type && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500/15 text-blue-400 border border-blue-500/20">
                                  {entry.training_type}
                                </span>
                              )}
                            </div>
                            <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${fb.cls} shrink-0`}>{fb.label}</span>
                          </div>

                          {/* Activity stats row */}
                          {snap && (
                            <div className="flex flex-wrap gap-3 text-xs">
                              <span className="text-white font-semibold">{snap.distance_km}km</span>
                              <span className="text-zinc-400">⏱ {snap.duration_str}</span>
                              <span className="text-zinc-400">🏃 {snap.avg_pace}/km</span>
                              <span className="text-zinc-400">❤️ {snap.avg_heart_rate}bpm</span>
                              {snap.total_elevation_gain > 0 && <span className="text-zinc-400">⛰ {snap.total_elevation_gain}m</span>}
                            </div>
                          )}

                          {/* Weekly progress bar */}
                          {prog && (
                            <div className="space-y-1">
                              <div className="flex justify-between text-[10px] text-zinc-500">
                                <span>本周 {prog.week_km}km / {prog.target_km}km</span>
                                <span>{prog.completion_pct}%</span>
                              </div>
                              <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                                <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all"
                                     style={{ width: `${Math.min(100, prog.completion_pct)}%` }} />
                              </div>
                            </div>
                          )}

                          {/* AI comment */}
                          {entry.ai_comment && (
                            <p className="text-sm text-zinc-300 leading-relaxed border-l-2 border-purple-500/30 pl-3">
                              {entry.ai_comment}
                            </p>
                          )}

                          {/* Performance note + tomorrow */}
                          <div className="flex flex-col gap-1">
                            {entry.performance_note && (
                              <p className="text-xs text-blue-400">💡 {entry.performance_note}</p>
                            )}
                            {entry.tomorrow_suggestion && (
                              <p className="text-xs text-emerald-400/70">→ 明日：{entry.tomorrow_suggestion}</p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-5 space-y-3 z-10 relative">
        <div className="flex gap-3">
          <button onClick={logLatestActivity} disabled={logging}
            className="flex-1 py-2.5 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 text-purple-300 disabled:opacity-50 text-sm font-semibold rounded-xl transition-all flex items-center justify-center gap-2">
            {logging ? (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            ) : "📝"} {logging ? "记录中..." : "记录最新训练"}
          </button>
          <button onClick={triggerWeeklyReview} disabled={reviewing}
            className="flex-1 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-white disabled:opacity-50 text-sm font-semibold rounded-xl transition-all flex items-center justify-center gap-2">
            {reviewing ? (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            ) : "📊"} {reviewing ? "生成中..." : "生成周总结"}
          </button>
        </div>

        {/* Backfill button */}
        {!backfilling && entries.length <= 3 && (
          <button
            onClick={async () => {
              if (!confirm("将为3月以来的所有训练生成AI评语（后台运行，约2-3分钟）")) return;
              setBackfilling("启动中...");
              try {
                const res = await axios.post(`${backendUrl}/api/coach/journal/backfill`, {
                  uid, since_date: "2026-03-01", journal_title: "UTMB 备赛日志"
                });
                setBackfilling(`${res.data.message} — 后台生成中...`);
                // Poll progress
                const poll = setInterval(async () => {
                  try {
                    const s = await axios.get(`${backendUrl}/api/coach/journal/backfill-status?uid=${uid}`);
                    const d = s.data;
                    if (d.state === "done") {
                      clearInterval(poll);
                      setBackfilling(`✅ 完成！${d.done}条日志已生成`);
                      await fetchJournal();
                      setTimeout(() => setBackfilling(""), 5000);
                    } else if (d.state === "error") {
                      clearInterval(poll);
                      setBackfilling(`❌ 错误: ${d.error_msg || "unknown"}`);
                      setTimeout(() => setBackfilling(""), 8000);
                    } else if (d.state === "running") {
                      setBackfilling(`⏳ 进度: ${d.done}/${d.total}${d.errors ? ` (${d.errors}失败)` : ""}`);
                    }
                  } catch { /* ignore poll errors */ }
                }, 5000);
              } catch (err: unknown) {
                const msg = err instanceof Error ? err.message : "未知错误";
                const axErr = err as { response?: { data?: { detail?: string }, status?: number } };
                const detail = axErr?.response?.data?.detail || axErr?.response?.status || msg;
                setBackfilling(`回填失败: ${detail}`);
                setTimeout(() => setBackfilling(""), 6000);
              }
            }}
            className="w-full py-2 bg-gradient-to-r from-orange-500/10 to-amber-500/10 hover:from-orange-500/15 hover:to-amber-500/15 border border-orange-500/20 text-orange-300 text-xs font-semibold rounded-xl transition-all flex items-center justify-center gap-2"
          >
            🔄 回填历史日志（3月至今）
          </button>
        )}
        {backfilling && (
          <div className="text-center py-2 text-xs text-orange-400 animate-pulse">{backfilling}</div>
        )}
      </div>
    </div>
  );
}
