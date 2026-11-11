"use client";

import React, { useEffect, useRef, useState } from "react";
import apiClient from "@/lib/apiClient";
import {
  Sparkles,
  Send,
  RefreshCw,
  Activity,
  Calendar,
  HeartPulse,
  MessageSquare,
  CheckCircle2,
  X,
  Minimize2,
  Maximize2,
  Move,
  Loader2,
} from "lucide-react";

interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  timestamp: string;
  reactionTag?: string;
  rpe?: number;
}

interface CoachChatBoxProps {
  uid: string;
  onPlanUpdated?: () => void;
}

interface WindowRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

type ResizeDir = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

const MIN_W = 360;
const MIN_H = 420;
const DEFAULT_W = 520;
const DEFAULT_H = 620;

const BODY_REACTION_TAGS = [
  { label: "😊 体感轻松", value: "体感轻松，呼吸与步频顺畅", defaultRpe: 4 },
  { label: "🔥 状态极佳", value: "状态极佳，肌肉弹性充沛", defaultRpe: 3 },
  { label: "😮‍💨 略感疲惫", value: "略感疲惫，双腿有些沉重", defaultRpe: 6 },
  { label: "🦵 肌肉酸痛紧绷", value: "小腿或大腿肌肉酸痛紧绷", defaultRpe: 7 },
  { label: "💓 心率偏高漂移", value: "同样配速下心率偏高、易漂移", defaultRpe: 7 },
  { label: "🛌 昨晚睡眠欠佳", value: "昨晚睡眠欠佳，晨起困倦恢复慢", defaultRpe: 6 },
  { label: "🩹 关节/足底微痛", value: "膝踝或足底存在轻微不适反应", defaultRpe: 8 },
];

const QUICK_QUESTIONS = [
  "🩺 结合我最近的训练、本周计划与身体反应，今天课表怎么执行最科学？",
  "📊 评估我本周课表执行率与当前体能负荷 (CTL/ATL/TSB) 状态",
  "🦵 最近跑后感觉腿部有些酸沉，接下来两天的课表需要降速或减量吗？",
  "🎯 根据我近期的训练配速与心率表现，目标比赛配速该如何卡控？",
];

export default function CoachChatBox({ uid, onPlanUpdated }: CoachChatBoxProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [rect, setRect] = useState<WindowRect>({ x: 0, y: 0, w: DEFAULT_W, h: DEFAULT_H });
  const [rectInitialized, setRectInitialized] = useState(false);

  const [contextData, setContextData] = useState<any>(null);
  const [loadingContext, setLoadingContext] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [selectedReaction, setSelectedReaction] = useState<string>("");
  const [selectedRpe, setSelectedRpe] = useState<number | null>(null);
  const [syncToPlan, setSyncToPlan] = useState(true);
  const [sending, setSending] = useState(false);
  const [syncingNote, setSyncingNote] = useState<string>("");
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const dragStateRef = useRef<{
    type: "move" | "resize";
    dir?: ResizeDir;
    startX: number;
    startY: number;
    startRect: WindowRect;
  } | null>(null);

  // Initialize default window position at bottom-right (or restore from localStorage)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const initW = Math.min(DEFAULT_W, vw - 24);
    const initH = Math.min(DEFAULT_H, vh - 40);
    let nextRect: WindowRect = {
      x: Math.max(12, vw - initW - 24),
      y: Math.max(16, vh - initH - 24),
      w: initW,
      h: initH,
    };
    try {
      const saved = localStorage.getItem("rgm_coach_dialog_rect");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && typeof parsed.x === "number" && typeof parsed.w === "number") {
          const w = Math.min(Math.max( MIN_W, parsed.w), vw - 16);
          const h = Math.min(Math.max(MIN_H, parsed.h), vh - 16);
          const x = Math.min(Math.max(8, parsed.x), Math.max(8, vw - w - 8));
          const y = Math.min(Math.max(8, parsed.y), Math.max(8, vh - h - 8));
          nextRect = { x, y, w, h };
        }
      }
    } catch {}
    setRect(nextRect);
    setRectInitialized(true);
  }, []);

  // Keep window inside viewport on browser resize
  useEffect(() => {
    if (typeof window === "undefined" || !rectInitialized) return;
    function handleWindowResize() {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      setRect((prev) => {
        const w = Math.min(Math.max(MIN_W, prev.w), Math.max(MIN_W, vw - 16));
        const h = Math.min(Math.max(MIN_H, prev.h), Math.max(MIN_H, vh - 16));
        const x = Math.min(Math.max(8, prev.x), Math.max(8, vw - w - 8));
        const y = Math.min(Math.max(8, prev.y), Math.max(8, vh - h - 8));
        return { x, y, w, h };
      });
    }
    window.addEventListener("resize", handleWindowResize);
    return () => window.removeEventListener("resize", handleWindowResize);
  }, [rectInitialized]);

  // Global mouse/touch listeners for dragging & resizing
  useEffect(() => {
    function onPointerMove(e: MouseEvent | TouchEvent) {
      const st = dragStateRef.current;
      if (!st) return;
      const clientX = "touches" in e ? e.touches[0]?.clientX ?? 0 : e.clientX;
      const clientY = "touches" in e ? e.touches[0]?.clientY ?? 0 : e.clientY;
      const dx = clientX - st.startX;
      const dy = clientY - st.startY;
      const vw = window.innerWidth;
      const vh = window.innerHeight;

      if (st.type === "move") {
        const nextX = Math.min(Math.max(8, st.startRect.x + dx), Math.max(8, vw - st.startRect.w - 8));
        const nextY = Math.min(Math.max(8, st.startRect.y + dy), Math.max(8, vh - st.startRect.h - 8));
        setRect((prev) => ({ ...prev, x: nextX, y: nextY }));
      } else if (st.type === "resize" && st.dir) {
        let { x, y, w, h } = st.startRect;
        const dir = st.dir;

        if (dir.includes("e")) {
          w = Math.min(Math.max(MIN_W, st.startRect.w + dx), vw - x - 8);
        }
        if (dir.includes("s")) {
          h = Math.min(Math.max(MIN_H, st.startRect.h + dy), vh - y - 8);
        }
        if (dir.includes("w")) {
          const maxDeltaX = st.startRect.w - MIN_W;
          const clampedDx = Math.max(-(st.startRect.x - 8), Math.min(dx, maxDeltaX));
          x = st.startRect.x + clampedDx;
          w = st.startRect.w - clampedDx;
        }
        if (dir.includes("n")) {
          const maxDeltaY = st.startRect.h - MIN_H;
          const clampedDy = Math.max(-(st.startRect.y - 8), Math.min(dy, maxDeltaY));
          y = st.startRect.y + clampedDy;
          h = st.startRect.h - clampedDy;
        }
        setRect({ x, y, w, h });
      }
    }

    function onPointerUp() {
      if (dragStateRef.current) {
        dragStateRef.current = null;
        document.body.style.userSelect = "";
        setRect((latest) => {
          try {
            localStorage.setItem("rgm_coach_dialog_rect", JSON.stringify(latest));
          } catch {}
          return latest;
        });
      }
    }

    window.addEventListener("mousemove", onPointerMove);
    window.addEventListener("mouseup", onPointerUp);
    window.addEventListener("touchmove", onPointerMove, { passive: false });
    window.addEventListener("touchend", onPointerUp);
    return () => {
      window.removeEventListener("mousemove", onPointerMove);
      window.removeEventListener("mouseup", onPointerUp);
      window.removeEventListener("touchmove", onPointerMove);
      window.removeEventListener("touchend", onPointerUp);
    };
  }, []);

  function startMove(e: React.MouseEvent | React.TouchEvent) {
    if (isMaximized) return;
    const target = e.target as HTMLElement;
    if (target.closest("button")) return;
    const clientX = "touches" in e ? e.touches[0]?.clientX ?? 0 : e.clientX;
    const clientY = "touches" in e ? e.touches[0]?.clientY ?? 0 : e.clientY;
    document.body.style.userSelect = "none";
    dragStateRef.current = {
      type: "move",
      startX: clientX,
      startY: clientY,
      startRect: { ...rect },
    };
  }

  function startResize(dir: ResizeDir, e: React.MouseEvent | React.TouchEvent) {
    e.stopPropagation();
    if (isMaximized) setIsMaximized(false);
    const clientX = "touches" in e ? e.touches[0]?.clientX ?? 0 : e.clientX;
    const clientY = "touches" in e ? e.touches[0]?.clientY ?? 0 : e.clientY;
    document.body.style.userSelect = "none";
    dragStateRef.current = {
      type: "resize",
      dir,
      startX: clientX,
      startY: clientY,
      startRect: { ...rect },
    };
  }

  function handleToggleMaximize() {
    if (typeof window === "undefined") return;
    if (!isMaximized) {
      setIsMaximized(true);
    } else {
      setIsMaximized(false);
    }
  }

  // Pre-fetch lightweight context when uid changes or when dialog opens
  useEffect(() => {
    if (uid && isOpen && !contextData && !loadingContext) {
      fetchCoachContext(uid);
    }
  }, [uid, isOpen]);

  useEffect(() => {
    if (isOpen && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [messages, sending, isOpen]);

  async function fetchCoachContext(userId: string) {
    setLoadingContext(true);
    try {
      const res = await apiClient.get(`/api/coach/chat-context/${encodeURIComponent(userId)}`);
      if (res.data) {
        setContextData(res.data);
        if (res.data.proactive_feedback && messages.length === 0) {
          setMessages([
            {
              id: "init-briefing",
              role: "assistant",
              content: res.data.proactive_feedback,
              timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
            },
          ]);
        }
      }
    } catch (e) {
      console.warn("Failed to load coach chat context:", e);
    } finally {
      setLoadingContext(false);
    }
  }

  async function handleRefreshBriefing() {
    if (!uid || loadingContext) return;
    setLoadingContext(true);
    try {
      const res = await apiClient.get(`/api/coach/chat-context/${encodeURIComponent(uid)}`);
      if (res.data) {
        setContextData(res.data);
        if (res.data.proactive_feedback) {
          setMessages((prev) => {
            const withoutInit = prev.filter((m) => m.id !== "init-briefing");
            return [
              {
                id: "init-briefing",
                role: "assistant",
                content: res.data.proactive_feedback,
                timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
              },
              ...withoutInit,
            ];
          });
        }
      }
    } catch (e) {
      console.warn("Failed to refresh coach chat context:", e);
    } finally {
      setLoadingContext(false);
    }
  }

  async function maybeSyncBodyReactionToTodayPlan(reactionText: string, rpeVal: number | null) {
    if (!syncToPlan || !reactionText) return;
    const planId = contextData?.plan_status?.plan_id;
    const weekIdx = contextData?.plan_status?.current_week_index;
    const todayDate = contextData?.plan_status?.today_workout?.date;
    const todayDow = contextData?.plan_status?.today_workout?.day_of_week;
    const days = contextData?.plan_status?.week_days || [];
    if (!planId || !weekIdx || days.length === 0) return;

    const dayIdx = days.findIndex(
      (d: any) => (todayDate && d.date === todayDate) || (todayDow && d.day_of_week === todayDow)
    );
    if (dayIdx < 0) return;

    try {
      await apiClient.put(`/api/coach/plan/${encodeURIComponent(planId)}/workout`, {
        operator_uid: uid,
        week_index: weekIdx,
        day_index: dayIdx,
        rpe: rpeVal ?? undefined,
        runner_feel_notes: reactionText,
      });
      setSyncingNote("✓ 已同步至今日课表体感记录");
      setTimeout(() => setSyncingNote(""), 4000);
      if (onPlanUpdated) onPlanUpdated();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("rgm-coach-plan-updated"));
      }
    } catch (e) {
      console.warn("Failed to sync body reaction to plan:", e);
    }
  }

  async function handleSendMessage(customQuestion?: string, reactionOverride?: string, rpeOverride?: number | null) {
    if (!uid || sending) return;
    const activeReaction = reactionOverride !== undefined ? reactionOverride : selectedReaction;
    const activeRpe = rpeOverride !== undefined ? rpeOverride : selectedRpe;
    const rawQ = (customQuestion !== undefined ? customQuestion : input).trim();

    if (!rawQ && !activeReaction) return;

    const finalQuestion =
      rawQ ||
      `我今天的身体反应是「${activeReaction}」${activeRpe ? `（自评 RPE ${activeRpe}/10）` : ""}，请结合我近期的训练情况和当前训练计划，给出今日与本周的专业反馈及课表调整建议。`;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: finalQuestion,
      timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
      reactionTag: activeReaction || undefined,
      rpe: activeRpe ?? undefined,
    };

    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    if (customQuestion === undefined) {
      setInput("");
    }
    setSending(true);

    if (activeReaction) {
      maybeSyncBodyReactionToTodayPlan(activeReaction, activeRpe);
    }

    try {
      const historyPayload = nextMessages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const res = await apiClient.post("/api/coach/chat", {
        uid,
        message: finalQuestion,
        body_reaction_tag: activeReaction || undefined,
        rpe: activeRpe ?? undefined,
        history: historyPayload,
      });

      const replyText =
        res.data?.reply ||
        "教练已收到您的训练与身体反应反馈。建议今日以心率平稳为第一准则，有氧段控制在 Zone 2 区间。";
      if (res.data?.context) {
        setContextData((prev: any) => ({
          ...prev,
          ...res.data.context,
        }));
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: replyText,
          timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (e) {
      console.error("Coach chat request failed:", e);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content:
            "教练服务瞬时繁忙，已基于您当前的本地负荷与课表为您校准：请优先关注晨起静息心率与腿部肌肉弹性，若感疲惫可将今日配速下调 15-20 秒/km。",
          timestamp: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  const tStat = contextData?.training_status;
  const pStat = contextData?.plan_status;
  const bReact = contextData?.body_reaction;
  const todayWorkout = pStat?.today_workout;

  // ── 1. 浮标状态 (Floating Launcher Badge) ──
  if (!isOpen) {
    return (
      <div className="fixed bottom-6 right-5 sm:right-6 z-50">
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          title="点击打开 Canova 科学教练对话舱（基于您的训练情况、训练计划与身体反应给出专业反馈）"
          className="group flex items-center gap-3 pl-3 pr-4 py-2.5 rounded-full bg-gradient-to-r from-purple-600 via-indigo-600 to-[#FC4C02] text-white shadow-2xl shadow-purple-600/35 hover:scale-105 active:scale-95 transition-all duration-200 border border-white/20 cursor-pointer"
        >
          <div className="relative w-9 h-9 rounded-full bg-black/25 flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5 text-white" />
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 ring-2 ring-purple-700 animate-pulse" />
          </div>
          <div className="text-left">
            <div className="text-xs font-black tracking-tight flex items-center gap-1 text-white">
              <span>🧢 Canova 教练</span>
            </div>
            <div className="text-[10px] text-white/85 font-medium hidden sm:block">
              训练 · 课表 · 身体反应反馈
            </div>
          </div>
        </button>
      </div>
    );
  }

  // Compute inline window style (draggable & resizable on desktop, full/tall sheet when maximized)
  const windowStyle: React.CSSProperties = isMaximized
    ? {
        left: 16,
        top: 16,
        width: "calc(100vw - 32px)",
        height: "calc(100vh - 32px)",
      }
    : {
        left: rect.x,
        top: rect.y,
        width: rect.w,
        height: rect.h,
      };

  // ── 2. 弹出式可拖拽、可缩放对话框窗口 (Draggable & Resizable Floating Window) ──
  return (
    <div
      style={windowStyle}
      className="fixed z-50 flex flex-col bg-[#121215] border border-purple-500/45 rounded-3xl shadow-2xl overflow-hidden"
    >
      {/* 8-Direction Invisible Resize Handles (Edges + Corners) */}
      {!isMaximized && (
        <>
          {/* Top / Bottom / Left / Right Edges */}
          <div
            onMouseDown={(e) => startResize("n", e)}
            onTouchStart={(e) => startResize("n", e)}
            className="absolute top-0 left-3 right-3 h-1.5 cursor-n-resize z-30"
          />
          <div
            onMouseDown={(e) => startResize("s", e)}
            onTouchStart={(e) => startResize("s", e)}
            className="absolute bottom-0 left-3 right-3 h-1.5 cursor-s-resize z-30"
          />
          <div
            onMouseDown={(e) => startResize("w", e)}
            onTouchStart={(e) => startResize("w", e)}
            className="absolute left-0 top-3 bottom-3 w-1.5 cursor-w-resize z-30"
          />
          <div
            onMouseDown={(e) => startResize("e", e)}
            onTouchStart={(e) => startResize("e", e)}
            className="absolute right-0 top-3 bottom-3 w-1.5 cursor-e-resize z-30"
          />
          {/* 4 Corners */}
          <div
            onMouseDown={(e) => startResize("nw", e)}
            onTouchStart={(e) => startResize("nw", e)}
            className="absolute top-0 left-0 w-3.5 h-3.5 cursor-nw-resize z-40"
          />
          <div
            onMouseDown={(e) => startResize("ne", e)}
            onTouchStart={(e) => startResize("ne", e)}
            className="absolute top-0 right-0 w-3.5 h-3.5 cursor-ne-resize z-40"
          />
          <div
            onMouseDown={(e) => startResize("sw", e)}
            onTouchStart={(e) => startResize("sw", e)}
            className="absolute bottom-0 left-0 w-3.5 h-3.5 cursor-sw-resize z-40"
          />
          {/* Bottom-Right Visible Resize Grip */}
          <div
            onMouseDown={(e) => startResize("se", e)}
            onTouchStart={(e) => startResize("se", e)}
            title="拖拽右下角可自由调整窗口尺寸"
            className="absolute bottom-0 right-0 w-5 h-5 cursor-se-resize z-40 flex items-end justify-end p-1 text-zinc-500 hover:text-purple-400"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" className="opacity-70">
              <path d="M9 1L1 9M9 5L5 9M9 9L9 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
        </>
      )}

      {/* Draggable Dialog Top Header */}
      <div
        onMouseDown={startMove}
        onTouchStart={startMove}
        onDoubleClick={handleToggleMaximize}
        title="按住顶部标题栏可自由拖动窗口位置（双击可最大化/还原）"
        className={`px-4 py-3 bg-gradient-to-r from-purple-950/60 via-[#18181c] to-[#18181c] border-b border-white/10 flex items-center justify-between gap-2 shrink-0 select-none ${
          isMaximized ? "cursor-default" : "cursor-move"
        }`}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-2xl bg-gradient-to-br from-purple-600 to-[#FC4C02] flex items-center justify-center text-white shadow-md shrink-0">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <h2 className="text-sm font-black text-white truncate">Canova 科学教练对话舱</h2>
              <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center gap-1">
                <Move className="w-2.5 h-2.5" /> 可拖拽 / 调尺寸
              </span>
            </div>
            <p className="text-[11px] text-zinc-400 truncate">
              按住标题栏拖动位置 · 拖拽四边或右下角调整大小
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={handleRefreshBriefing}
            disabled={loadingContext}
            className="p-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 transition cursor-pointer disabled:opacity-50"
            title="重新读取最新训练记录、课表与身体反应"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingContext ? "animate-spin text-purple-400" : ""}`} />
          </button>
          <button
            type="button"
            onClick={handleToggleMaximize}
            className="p-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 hover:text-white transition cursor-pointer"
            title={isMaximized ? "还原窗口尺寸" : "最大化窗口"}
          >
            {isMaximized ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="p-1.5 rounded-xl bg-white/5 hover:bg-rose-500/20 border border-white/10 text-zinc-400 hover:text-rose-300 transition cursor-pointer"
            title="收起为右下角浮标"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 3-Pillar Real-Time Context Strip (训练情况 / 训练计划 / 身体反应) */}
      {tStat && (
        <div className="px-3.5 pt-2.5 pb-2 grid grid-cols-3 gap-2 border-b border-white/5 bg-[#141418] shrink-0">
          {/* Pillar 1: 训练情况 */}
          <div className="bg-[#18181c] border border-white/10 rounded-xl p-2">
            <div className="flex items-center justify-between text-[10px] text-cyan-300 font-bold">
              <span className="flex items-center gap-1 truncate">
                <Activity className="w-3 h-3 shrink-0" /> 训练情况
              </span>
              <span className="font-mono text-zinc-400">{tStat.recent_7d_km}k</span>
            </div>
            <div className="mt-1 text-[11px] text-white font-bold truncate">
              {tStat.latest_run
                ? `${tStat.latest_run.date.slice(5)} ${tStat.latest_run.distance_km}k`
                : `近7天 ${tStat.recent_7d_runs}练`}
            </div>
            <div className="mt-0.5 text-[10px] text-zinc-400 font-mono truncate">
              CTL {tStat.ctl} · TSB {tStat.tsb_sign}
            </div>
          </div>

          {/* Pillar 2: 训练计划 */}
          <div className="bg-[#18181c] border border-white/10 rounded-xl p-2">
            <div className="flex items-center justify-between text-[10px] text-purple-300 font-bold">
              <span className="flex items-center gap-1 truncate">
                <Calendar className="w-3 h-3 shrink-0" /> 训练计划
              </span>
              {pStat?.has_plan && (
                <span className="font-mono text-emerald-300">{pStat.completion_pct}%</span>
              )}
            </div>
            <div className="mt-1 text-[11px] text-white font-bold truncate">
              {todayWorkout
                ? `${todayWorkout.title}`
                : pStat?.has_plan
                ? `第 ${pStat.current_week_index} 周课表`
                : "未激活计划"}
            </div>
            <div className="mt-0.5 text-[10px] text-zinc-400 truncate">
              {todayWorkout && todayWorkout.distance_km > 0
                ? `今日 ${todayWorkout.distance_km}km · ${todayWorkout.target_pace || "稳态"}`
                : pStat?.has_plan
                ? `周 ${pStat.actual_weekly_km}/${pStat.planned_weekly_km}km`
                : "可在训练页生成"}
            </div>
          </div>

          {/* Pillar 3: 身体反应 */}
          <div className="bg-[#18181c] border border-white/10 rounded-xl p-2">
            <div className="flex items-center justify-between text-[10px] text-emerald-300 font-bold">
              <span className="flex items-center gap-1 truncate">
                <HeartPulse className="w-3 h-3 shrink-0" /> 身体反应
              </span>
              {bReact?.avg_rpe && (
                <span className="font-mono text-amber-300">RPE {bReact.avg_rpe}</span>
              )}
            </div>
            <div className="mt-1 text-[11px] font-bold text-white truncate">
              {bReact?.badge_text?.replace(/^[🟢🟡🔴]\s*/, "") || "反应良好"}
            </div>
            <div className="mt-0.5 text-[10px] text-zinc-400 truncate" title={bReact?.watch_summary_line}>
              {bReact?.has_injury_alert
                ? `⚠️ ${bReact.injury_note}`
                : bReact?.hrv
                ? `HRV ${Math.round(bReact.hrv)}ms · 静心 ${bReact.rhr || "—"}`
                : "点击下方标签反馈"}
            </div>
          </div>
        </div>
      )}

      {/* Scrollable Chat Messages Stream */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-3.5 space-y-3 bg-[#121215] min-h-[160px]"
      >
        {loadingContext && messages.length === 0 ? (
          <div className="py-12 text-center text-xs text-zinc-400 flex flex-col items-center justify-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
            <span>Canova 教练正在读取您的近期训练记录、当前周课表与生理恢复指标...</span>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[92%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
                  msg.role === "user"
                    ? "bg-purple-600 text-white"
                    : "bg-[#18181c] border border-white/10 text-zinc-200"
                }`}
              >
                <div className="flex items-center justify-between gap-3 mb-1 text-[10px] opacity-75">
                  <span className="font-bold">
                    {msg.role === "user" ? "🏃 我的提问 / 身体反馈" : "🧢 Canova 科学教练反馈"}
                  </span>
                  <span>{msg.timestamp}</span>
                </div>
                {msg.reactionTag && (
                  <div className="mb-1.5 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-white/15 text-[10px] font-bold">
                    <span>🫀 身体反应：{msg.reactionTag}</span>
                    {msg.rpe && <span>· RPE {msg.rpe}/10</span>}
                  </div>
                )}
                <div className="whitespace-pre-wrap">{msg.content}</div>
              </div>
            </div>
          ))
        )}

        {sending && (
          <div className="flex justify-start">
            <div className="bg-[#18181c] border border-white/10 rounded-2xl px-3.5 py-2.5 text-xs text-zinc-300 flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
              <span>Canova 教练正在结合您的训练负荷、当周课表与身体反应深度推理...</span>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Interactive Controls: Body Reaction Pills + Quick Prompts + Input */}
      <div className="p-3 bg-[#16161b] border-t border-white/10 space-y-2 shrink-0">
        {/* Body Reaction Selector Row */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] font-black text-zinc-300 flex items-center gap-1.5">
              <span>🫀 点选今日身体反应（即刻获取教练反馈）：</span>
              {syncingNote && (
                <span className="text-[10px] font-bold text-emerald-400 flex items-center gap-0.5">
                  <CheckCircle2 className="w-3 h-3" /> {syncingNote}
                </span>
              )}
            </span>
            {pStat?.has_plan && (
              <label className="flex items-center gap-1 text-[10px] text-zinc-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={syncToPlan}
                  onChange={(e) => setSyncToPlan(e.target.checked)}
                  className="rounded accent-[#FC4C02]"
                />
                <span>同步至课表</span>
              </label>
            )}
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
            {BODY_REACTION_TAGS.map((tag) => {
              const isSelected = selectedReaction === tag.value;
              return (
                <button
                  key={tag.label}
                  type="button"
                  disabled={sending}
                  onClick={() => {
                    const nextVal = isSelected ? "" : tag.value;
                    const nextRpe = isSelected ? null : tag.defaultRpe;
                    setSelectedReaction(nextVal);
                    setSelectedRpe(nextRpe);
                    if (nextVal) {
                      handleSendMessage(
                        `我今天的身体反应是「${nextVal}」（自评 RPE ${tag.defaultRpe}/10），请结合我近期的训练情况和当前训练计划，给出专业反馈与今日课表执行建议。`,
                        nextVal,
                        tag.defaultRpe
                      );
                    }
                  }}
                  className={`shrink-0 px-2.5 py-1 rounded-xl text-[11px] font-bold border transition cursor-pointer ${
                    isSelected
                      ? "bg-[#FC4C02] text-white border-[#FC4C02] shadow-sm"
                      : "bg-white/5 hover:bg-white/10 text-zinc-300 border-white/10"
                  }`}
                >
                  {tag.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Preset Quick Prompt Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 no-scrollbar">
          {QUICK_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              disabled={sending}
              onClick={() => handleSendMessage(q)}
              className="shrink-0 px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-purple-600/20 border border-white/10 hover:border-purple-500/40 text-[10px] text-zinc-400 hover:text-zinc-200 transition cursor-pointer disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2 pr-2"
        >
          <div className="relative flex-1">
            <MessageSquare className="w-3.5 h-3.5 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="向 Canova 教练提问（如：今天跑完小腿发紧，周四课表怎么调？）..."
              className="w-full bg-[#121215] border border-white/15 focus:border-purple-500 rounded-xl pl-8 pr-3 py-2 text-xs text-white placeholder-zinc-500 outline-none transition"
            />
          </div>
          <button
            type="submit"
            disabled={sending || (!input.trim() && !selectedReaction)}
            className="px-3.5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-[#FC4C02] hover:opacity-95 text-white text-xs font-black transition flex items-center gap-1 shrink-0 cursor-pointer disabled:opacity-40 shadow-md"
          >
            <Send className="w-3.5 h-3.5" />
            <span>发送</span>
          </button>
        </form>
      </div>
    </div>
  );
}
