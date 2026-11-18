"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Bot,
  Calendar,
  CheckCircle2,
  Clock,
  Flame,
  Heart,
  Send,
  Sparkles,
  UserCheck,
  Zap,
} from "lucide-react";
import apiClient from "@/lib/apiClient";
import { showToast } from "@/components/ui/UiFeedbackProvider";

interface BatchCritiqueCockpitProps {
  feed: any[];
  students: any[];
  currentUser: any;
  userProfile: any;
  onSelectStudentForPlan?: (student: any) => void;
  onCommentPosted?: (activityId: string, newComment: any) => void;
}

const PRESET_CHIPS = [
  {
    label: "👏 有氧稳健",
    text: "🧢 教练点评：本次有氧配速与心率控制非常扎实，继续保持这个跑感与步频稳定性！",
  },
  {
    label: "⚠️ 心率飘移·排酸",
    text: "🧢 教练点评：后程心率略微飘移，建议明后天改为低心率 E 跑或主动休息排酸，保证睡眠恢复。",
  },
  {
    label: "🔥 阈值课高质量",
    text: "🧢 教练点评：核心强度课完成质量很高！跑后务必认真拉伸髋臀与小腿，及时补充碳水和蛋白质。",
  },
  {
    label: "💧 LSD 补给节奏佳",
    text: "🧢 教练点评：长距离耐力输出在线，请坚持每 5km/30min 补水补胶习惯，严防前程冲太快。",
  },
  {
    label: "🛌 明日完全休息",
    text: "🧢 教练点评：结合近期疲劳积累，建议明日安排完全休息或 20 分钟轻松拉伸，给超量恢复留足窗口。",
  },
  {
    label: "🎯 赛前减量保持",
    text: "🧢 教练点评：赛前减量阶段切忌贪量，维持短距离轻快跑唤醒神经肌肉即可，信心满满迎赛！",
  },
];

export default function BatchCritiqueCockpit({
  feed,
  students,
  currentUser,
  userProfile,
  onSelectStudentForPlan,
  onCommentPosted,
}: BatchCritiqueCockpitProps) {
  const [queueFilter, setQueueFilter] = useState<"unreviewed" | "all">("unreviewed");
  const [selectedActivityId, setSelectedActivityId] = useState<string>("");
  const [draftComment, setDraftComment] = useState<string>("");
  const [autoAdvance, setAutoAdvance] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const isActReviewedByMe = (act: any) =>
    (act?.comments || []).some(
      (c: any) =>
        (currentUser?.id && c.user_id === currentUser.id) ||
        String(c.content || "").includes("教练点评")
    );

  const reviewedCount = useMemo(
    () => (feed || []).filter((act) => isActReviewedByMe(act)).length,
    [feed, currentUser?.id]
  );

  const queueItems = useMemo(() => {
    const list = Array.isArray(feed) ? [...feed] : [];
    const sorted = list.sort((a, b) => {
      const aDone = isActReviewedByMe(a) ? 1 : 0;
      const bDone = isActReviewedByMe(b) ? 1 : 0;
      return aDone - bDone;
    });
    if (queueFilter === "unreviewed") {
      const pending = sorted.filter((a) => !isActReviewedByMe(a));
      return pending.length > 0 ? pending : sorted;
    }
    return sorted;
  }, [feed, queueFilter, currentUser?.id]);

  useEffect(() => {
    if (!queueItems.length) {
      setSelectedActivityId("");
      return;
    }
    const stillExists = queueItems.some((a) => String(a.id) === selectedActivityId);
    if (!stillExists) {
      setSelectedActivityId(String(queueItems[0].id));
    }
  }, [queueItems, selectedActivityId]);

  const selectedAct = useMemo(
    () => queueItems.find((a) => String(a.id) === selectedActivityId) || queueItems[0] || null,
    [queueItems, selectedActivityId]
  );

  const matchedStudent = useMemo(() => {
    if (!selectedAct?.user_id || !Array.isArray(students)) return null;
    return (
      students.find(
        (s) => s.user_id === selectedAct.user_id || s.id === selectedAct.user_id
      ) || null
    );
  }, [selectedAct?.user_id, students]);

  async function handleSubmitCritique() {
    if (!selectedAct?.id || !currentUser?.id || !draftComment.trim() || submitting) return;
    setSubmitting(true);
    try {
      const payload = {
        user_id: currentUser.id,
        content: draftComment.trim(),
        author_name: userProfile?.display_name || "认证教练",
        author_avatar: userProfile?.avatar_url || "",
      };
      const res = await apiClient.post(
        `/api/team/activities/${selectedAct.id}/comments`,
        payload
      );
      const newComment = res.data?.comment || {
        id: `local-${Date.now()}`,
        user_id: currentUser.id,
        content: payload.content,
        author_name: payload.author_name,
        author_avatar: payload.author_avatar,
        created_at: new Date().toISOString(),
      };
      onCommentPosted?.(selectedAct.id, newComment);
      showToast(`✅ 已向「${selectedAct.display_name || "队员"}」发送教练点评`);
      setDraftComment("");

      if (autoAdvance) {
        const nextPending = (feed || []).find(
          (a) => String(a.id) !== String(selectedAct.id) && !isActReviewedByMe(a)
        );
        if (nextPending) {
          setSelectedActivityId(String(nextPending.id));
        }
      }
    } catch (err: any) {
      showToast(err?.response?.data?.detail || "发送教练点评失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  const distKm = selectedAct
    ? ((Number(selectedAct.distance_meters) || 0) / 1000).toFixed(2)
    : "0.00";

  return (
    <section
      aria-label="5 秒连续批阅打卡三联工作台"
      className="space-y-4"
    >
      {/* Top Cockpit Status Strip */}
      <div className="rgm-bento-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#FC4C02]/15 text-[#FC4C02] flex items-center justify-center shrink-0">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-black text-white flex items-center gap-2">
              <span>⚡ 5 秒连续批阅工作台</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                已批阅 {reviewedCount} / {feed?.length || 0} 条打卡
              </span>
            </div>
            <div className="text-[11px] text-zinc-400">
              左侧选学员 → 中部看心率/TRIMP/Canova 摘要 → 右侧点击短语按 Enter 秒发并自动跳下一位
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setQueueFilter("unreviewed")}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition ${
              queueFilter === "unreviewed"
                ? "bg-[#FC4C02] text-white border-[#FC4C02]"
                : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
            }`}
          >
            优先未批阅
          </button>
          <button
            type="button"
            onClick={() => setQueueFilter("all")}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition ${
              queueFilter === "all"
                ? "bg-[#FC4C02] text-white border-[#FC4C02]"
                : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
            }`}
          >
            全部 ({feed?.length || 0})
          </button>
        </div>
      </div>

      {!selectedAct ? (
        <div className="rgm-bento-card p-10 text-center space-y-2">
          <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
          <div className="text-base font-bold text-white">当前跑团暂无待批阅训练打卡</div>
          <p className="text-xs text-zinc-400">
            当队员通过佳明/高驰手表或小程序同步新的跑步记录后，将自动进入此连续批阅队列。
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
          {/* ── LEFT PANE (xl:col-span-3): 待点评队列 ── */}
          <div className="xl:col-span-3 rgm-bento-card p-3.5 space-y-2.5 max-h-[600px] overflow-y-auto">
            <div className="flex items-center justify-between px-1 pb-2 border-b border-white/10">
              <span className="text-xs font-bold text-zinc-300">打卡批阅队列</span>
              <span className="text-[10px] text-zinc-500 font-mono">
                {queueItems.length} 项
              </span>
            </div>

            <div className="space-y-1.5">
              {queueItems.map((act) => {
                const active = String(act.id) === String(selectedAct.id);
                const done = isActReviewedByMe(act);
                const km = ((Number(act.distance_meters) || 0) / 1000).toFixed(1);
                return (
                  <button
                    key={act.id}
                    type="button"
                    onClick={() => setSelectedActivityId(String(act.id))}
                    className={`w-full text-left p-2.5 rounded-2xl border transition flex items-center justify-between gap-2 ${
                      active
                        ? "bg-[#FC4C02]/15 border-[#FC4C02] shadow-sm"
                        : "bg-white/[0.02] hover:bg-white/[0.05] border-white/10"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <img
                        src={
                          act.avatar_url ||
                          "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                        }
                        alt={act.display_name || "跑者"}
                        className="w-8 h-8 rounded-full object-cover border border-white/10 shrink-0"
                      />
                      <div className="min-w-0">
                        <div className="text-xs font-bold text-white truncate">
                          {act.display_name || "跑友"}
                        </div>
                        <div className="text-[10px] text-zinc-400 truncate">
                          {km} km · {act.avg_pace_str || "—"}
                        </div>
                      </div>
                    </div>

                    <span
                      className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold shrink-0 ${
                        done
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-amber-500/20 text-amber-300"
                      }`}
                    >
                      {done ? "✓ 已评" : "待评"}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── CENTER PANE (xl:col-span-5): 训练遥测 & Canova AI 诊断 ── */}
          <div className="xl:col-span-5 rgm-bento-card p-5 space-y-4">
            <div className="flex items-start justify-between gap-3 pb-3 border-b border-white/10">
              <div className="flex items-center gap-3 min-w-0">
                <img
                  src={
                    selectedAct.avatar_url ||
                    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                  }
                  alt={selectedAct.display_name || "跑者"}
                  className="w-11 h-11 rounded-full object-cover border border-white/15 shrink-0"
                />
                <div className="min-w-0">
                  <div className="text-sm font-black text-white truncate">
                    {selectedAct.display_name || "跑友"} · {selectedAct.name || "训练打卡"}
                  </div>
                  <div className="text-[11px] text-zinc-400 flex items-center gap-2 mt-0.5">
                    <Clock className="w-3 h-3" />
                    <span>
                      {selectedAct.start_time?.slice(0, 16)?.replace("T", " ") || "近期同步"}
                    </span>
                  </div>
                </div>
              </div>

              {matchedStudent && onSelectStudentForPlan && (
                <button
                  type="button"
                  onClick={() => onSelectStudentForPlan(matchedStudent)}
                  className="px-2.5 py-1.5 rounded-xl bg-purple-500/15 hover:bg-purple-500/25 border border-purple-500/30 text-[11px] font-bold text-purple-200 flex items-center gap-1 shrink-0 transition"
                >
                  <Calendar className="w-3.5 h-3.5" />
                  <span>调整周课表</span>
                </button>
              )}
            </div>

            {/* 4 Key Telemetry KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="p-3 rounded-2xl bg-white/[0.03] border border-white/10">
                <div className="text-[10px] text-zinc-400 flex items-center gap-1">
                  <Activity className="w-3 h-3 text-[#FC4C02]" /> 距离
                </div>
                <div className="text-lg font-black text-[#FC4C02] mt-0.5">
                  {distKm} <span className="text-[10px] text-zinc-400">km</span>
                </div>
              </div>
              <div className="p-3 rounded-2xl bg-white/[0.03] border border-white/10">
                <div className="text-[10px] text-zinc-400">平均配速</div>
                <div className="text-lg font-black text-white mt-0.5">
                  {selectedAct.avg_pace_str || "—"}
                </div>
              </div>
              <div className="p-3 rounded-2xl bg-white/[0.03] border border-white/10">
                <div className="text-[10px] text-zinc-400 flex items-center gap-1">
                  <Heart className="w-3 h-3 text-rose-400" /> 心率
                </div>
                <div className="text-lg font-black text-rose-400 mt-0.5">
                  {selectedAct.is_biometrics_hidden
                    ? "受保护"
                    : selectedAct.average_heartrate || "—"}
                  {!selectedAct.is_biometrics_hidden && selectedAct.average_heartrate && (
                    <span className="text-[10px] text-zinc-400 ml-0.5">bpm</span>
                  )}
                </div>
              </div>
              <div className="p-3 rounded-2xl bg-white/[0.03] border border-white/10">
                <div className="text-[10px] text-zinc-400 flex items-center gap-1">
                  <Flame className="w-3 h-3 text-amber-400" /> TRIMP
                </div>
                <div className="text-lg font-black text-amber-400 mt-0.5">
                  {selectedAct.trimp || 50}
                </div>
              </div>
            </div>

            {/* Canova AI Pre-Diagnosis */}
            <div className="p-4 rounded-2xl bg-purple-500/10 border border-purple-500/25 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-purple-300">
                <Bot className="w-4 h-4 text-purple-400" />
                <span>Canova 模型辅助预诊断</span>
              </div>
              <p className="text-xs text-zinc-300 leading-relaxed max-h-36 overflow-y-auto">
                {selectedAct.ai_journal ||
                  "该条训练记录尚未附带 AI 日报文本，请直接结合心率与配速给予人工批注。"}
              </p>
            </div>

            {/* Existing Comments Preview */}
            {(selectedAct.comments || []).length > 0 && (
              <div className="space-y-1.5 pt-1">
                <div className="text-[11px] font-bold text-zinc-400">
                  已有留言 ({selectedAct.comments.length})
                </div>
                <div className="space-y-1.5 max-h-32 overflow-y-auto">
                  {selectedAct.comments.map((cm: any, idx: number) => (
                    <div
                      key={cm.id || idx}
                      className="px-3 py-2 rounded-xl bg-white/[0.03] border border-white/10 text-[11px] text-zinc-300"
                    >
                      <strong className="text-white">{cm.author_name || "跑友"}：</strong>
                      <span>{cm.content}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── RIGHT PANE (xl:col-span-4): 5 秒极速评语发射台 ── */}
          <div className="xl:col-span-4 rgm-bento-card p-5 space-y-4">
            <div className="flex items-center justify-between gap-2 pb-2 border-b border-white/10">
              <div className="flex items-center gap-2 text-sm font-black text-white">
                <Sparkles className="w-4 h-4 text-[#FC4C02]" />
                <span>一键批阅短语 & 秒发</span>
              </div>
              <button
                type="button"
                onClick={() => setAutoAdvance((v) => !v)}
                className={`px-2 py-0.5 rounded-full text-[10px] font-bold border transition flex items-center gap-1 ${
                  autoAdvance
                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                    : "bg-white/5 text-zinc-400 border-white/10"
                }`}
              >
                <UserCheck className="w-3 h-3" />
                <span>{autoAdvance ? "发送后自动下一条" : "停留在当前条"}</span>
              </button>
            </div>

            {/* 6 Preset Quick Chips */}
            <div className="flex flex-wrap gap-1.5">
              {PRESET_CHIPS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => setDraftComment(preset.text)}
                  className="px-2.5 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-[11px] font-bold text-amber-300 transition text-left"
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Composer Textarea */}
            <div className="space-y-2">
              <textarea
                rows={4}
                value={draftComment}
                onChange={(e) => setDraftComment(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmitCritique();
                  }
                }}
                placeholder={`输入给「${selectedAct.display_name || "跑友"}」的教练批注（按 Enter 立即发送，Shift+Enter 换行）...`}
                className="w-full rounded-2xl bg-[#101015] border border-white/15 px-3.5 py-3 text-xs text-white placeholder:text-zinc-500 focus:outline-none focus:border-[#FC4C02] resize-none"
              />

              <button
                type="button"
                disabled={submitting || !draftComment.trim()}
                onClick={handleSubmitCritique}
                className="w-full py-2.5 px-4 rounded-xl bg-[#FC4C02] hover:brightness-110 disabled:opacity-45 text-white text-xs font-black flex items-center justify-center gap-2 transition shadow-lg shadow-[#FC4C02]/25"
              >
                <Send className="w-3.5 h-3.5" />
                <span>
                  {submitting
                    ? "正在下达点评..."
                    : autoAdvance
                    ? "发送点评并跳下一位 (Enter)"
                    : "发送教练点评 (Enter)"}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
