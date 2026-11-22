"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Compass,
  Loader2,
  Lock,
  Mic,
  MicOff,
  Navigation,
  RefreshCw,
  Send,
  Sparkles,
  Volume2,
  X,
  Zap,
} from "lucide-react";
import apiClient from "@/lib/apiClient";
import { showToast } from "@/components/ui/UiFeedbackProvider";
import {
  QUICK_INTENT_CHIPS,
  UserRoleFlags,
  WORKFLOW_BY_ID,
  WorkflowEntry,
  hasWorkflowPermission,
  matchWorkflowsLocally,
} from "@/lib/workflowCatalog";
import { VoiceCaptureSession } from "@/lib/voiceRecorder";
import { dispatchRgmNavIntent } from "./CommandPaletteModal";

const ARRIVAL_STORAGE_KEY = "rgm_ops_arrival_guide";
const PENDING_AFTER_LOGIN_KEY = "rgm_ops_pending_after_login";
const AUTO_JUMP_PREF_KEY = "rgm_ops_auto_jump";
const ARRIVAL_UPDATED_EVENT = "rgm-ops-arrival-updated";

export function openAiOperationAssistant(detail?: {
  query?: string;
  autoVoice?: boolean;
}) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("rgm-open-ops-assistant", { detail: detail || {} }));
}

interface AiOperationAssistantProps {
  user: any;
  isCoachOrOwner: boolean;
  isSuperAdmin: boolean;
  hasManagedOrg: boolean;
  themeMode: "dark" | "light";
  onToggleTheme: () => void;
  onOpenAuth: () => void;
}

interface AssistantNavResult {
  query: string;
  primary: WorkflowEntry;
  alternatives: WorkflowEntry[];
  reply: string;
  confidence: number;
  autoNavigate: boolean;
  permissionOk: boolean;
  requiresAuth: boolean;
  engine: string;
}

const ROLE_BADGE_MAP: Record<WorkflowEntry["roleRequired"], string> = {
  public: "全站公开",
  runner: "跑者流程",
  leader: "团长 / 教练",
  org_admin: "大群管理",
  super_admin: "平台超管",
};

export default function AiOperationAssistant({
  user,
  isCoachOrOwner,
  isSuperAdmin,
  hasManagedOrg,
  onToggleTheme,
  onOpenAuth,
}: AiOperationAssistantProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [loadingNav, setLoadingNav] = useState(false);
  const [result, setResult] = useState<AssistantNavResult | null>(null);
  const [autoJump, setAutoJump] = useState<boolean>(true);
  const [countdownProgress, setCountdownProgress] = useState<number>(0);
  const [countdownActive, setCountdownActive] = useState<boolean>(false);

  // Voice capture states
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceLevels, setVoiceLevels] = useState<number[]>(Array(12).fill(0.18));
  const [voiceElapsed, setVoiceElapsed] = useState(0);
  const [interimText, setInterimText] = useState("");
  const [voiceError, setVoiceError] = useState("");

  // Arrival guide banner state (persists across route navigation via sessionStorage)
  const [arrivalGuide, setArrivalGuide] = useState<WorkflowEntry | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const voiceSessionRef = useRef<VoiceCaptureSession | null>(null);
  const stopVoiceRef = useRef<() => Promise<void>>(async () => {});
  const autoJumpTimerRef = useRef<number | null>(null);
  const countdownRafRef = useRef<number | null>(null);

  const roleFlags: UserRoleFlags = useMemo(
    () => ({
      loggedIn: Boolean(user?.id),
      isCoachOrOwner,
      hasManagedOrg,
      isSuperAdmin,
    }),
    [user?.id, isCoachOrOwner, hasManagedOrg, isSuperAdmin]
  );

  // Load auto-jump preference
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = localStorage.getItem(AUTO_JUMP_PREF_KEY);
      if (saved === "0") setAutoJump(false);
    } catch {}
  }, []);

  const toggleAutoJump = () => {
    setAutoJump((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(AUTO_JUMP_PREF_KEY, next ? "1" : "0");
      } catch {}
      return next;
    });
  };

  const cancelAutoJumpCountdown = useCallback(() => {
    if (autoJumpTimerRef.current !== null) {
      window.clearTimeout(autoJumpTimerRef.current);
      autoJumpTimerRef.current = null;
    }
    if (countdownRafRef.current !== null) {
      window.cancelAnimationFrame(countdownRafRef.current);
      countdownRafRef.current = null;
    }
    setCountdownActive(false);
    setCountdownProgress(0);
  }, []);

  const syncArrivalBannerFromStorage = useCallback(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = sessionStorage.getItem(ARRIVAL_STORAGE_KEY);
      if (!raw) {
        setArrivalGuide(null);
        return;
      }
      const parsed = JSON.parse(raw);
      const ts = Number(parsed?.ts || 0);
      if (!parsed?.workflowId || Date.now() - ts > 15 * 60 * 1000) {
        sessionStorage.removeItem(ARRIVAL_STORAGE_KEY);
        setArrivalGuide(null);
        return;
      }
      const wf = WORKFLOW_BY_ID[parsed.workflowId];
      setArrivalGuide(wf || null);
    } catch {
      setArrivalGuide(null);
    }
  }, []);

  useEffect(() => {
    syncArrivalBannerFromStorage();
    const onUpdated = () => syncArrivalBannerFromStorage();
    window.addEventListener(ARRIVAL_UPDATED_EVENT, onUpdated);
    return () => window.removeEventListener(ARRIVAL_UPDATED_EVENT, onUpdated);
  }, [pathname, syncArrivalBannerFromStorage]);

  const executeWorkflow = useCallback(
    (wf: WorkflowEntry) => {
      cancelAutoJumpCountdown();

      if (wf.actionType === "toggle-theme") {
        onToggleTheme();
        setOpen(false);
        showToast("已为您切换界面主题配色");
        return;
      }

      if (wf.actionType === "open-auth") {
        setOpen(false);
        onOpenAuth();
        return;
      }

      // Require login first if protected route and user is anonymous
      if (wf.roleRequired !== "public" && !user?.id) {
        try {
          sessionStorage.setItem(
            PENDING_AFTER_LOGIN_KEY,
            JSON.stringify({ workflowId: wf.id, ts: Date.now() })
          );
        } catch {}
        setOpen(false);
        showToast(`请先登录，登录后将自动为您前往「${wf.title}」`);
        onOpenAuth();
        return;
      }

      if (!hasWorkflowPermission(wf, roleFlags)) {
        showToast(`「${wf.title}」需要 ${ROLE_BADGE_MAP[wf.roleRequired]} 权限`);
        return;
      }

      // Persist arrival guide across route transition
      try {
        sessionStorage.setItem(
          ARRIVAL_STORAGE_KEY,
          JSON.stringify({ workflowId: wf.id, ts: Date.now() })
        );
        window.dispatchEvent(new CustomEvent(ARRIVAL_UPDATED_EVENT));
      } catch {}

      setOpen(false);

      if (wf.actionType === "open-coach-chat") {
        if (!pathname?.startsWith("/dashboard")) {
          dispatchRgmNavIntent("/dashboard", "runner");
          router.push("/dashboard");
          setTimeout(() => {
            window.dispatchEvent(new CustomEvent("rgm-open-coach-chat"));
          }, 420);
        } else {
          window.dispatchEvent(new CustomEvent("rgm-open-coach-chat"));
        }
        return;
      }

      if (wf.href) {
        if (wf.perspective) {
          try {
            localStorage.setItem("rgm_role_perspective", wf.perspective);
          } catch {}
        }
        dispatchRgmNavIntent(wf.href, wf.perspective);
        router.push(wf.href);
      }
    },
    [
      cancelAutoJumpCountdown,
      onToggleTheme,
      onOpenAuth,
      user?.id,
      roleFlags,
      pathname,
      router,
    ]
  );

  // Resume pending navigation right after login completes
  useEffect(() => {
    if (!user?.id || typeof window === "undefined") return;
    try {
      const raw = sessionStorage.getItem(PENDING_AFTER_LOGIN_KEY);
      if (!raw) return;
      sessionStorage.removeItem(PENDING_AFTER_LOGIN_KEY);
      const parsed = JSON.parse(raw);
      if (Date.now() - Number(parsed?.ts || 0) > 10 * 60 * 1000) return;
      const wf = WORKFLOW_BY_ID[parsed?.workflowId];
      if (wf) {
        setTimeout(() => executeWorkflow(wf), 120);
      }
    } catch {}
  }, [user?.id, executeWorkflow]);

  const startAutoJumpCountdown = useCallback(
    (wf: WorkflowEntry) => {
      cancelAutoJumpCountdown();
      const durationMs = 1200;
      const startedAt = performance.now();
      setCountdownActive(true);
      setCountdownProgress(0);

      const step = (now: number) => {
        const pct = Math.min(100, ((now - startedAt) / durationMs) * 100);
        setCountdownProgress(pct);
        if (pct < 100) {
          countdownRafRef.current = window.requestAnimationFrame(step);
        }
      };
      countdownRafRef.current = window.requestAnimationFrame(step);

      autoJumpTimerRef.current = window.setTimeout(() => {
        executeWorkflow(wf);
      }, durationMs);
    },
    [cancelAutoJumpCountdown, executeWorkflow]
  );

  const handleAskAssistant = useCallback(
    async (rawQuery: string) => {
      const q = rawQuery.trim();
      if (!q) return;
      cancelAutoJumpCountdown();
      setVoiceError("");
      setLoadingNav(true);

      let resolved: AssistantNavResult | null = null;
      try {
        const res = await apiClient.post("/api/assistant/navigate", {
          query: q,
          current_path: pathname || "/",
          user_roles: {
            logged_in: Boolean(user?.id),
            is_coach_or_owner: isCoachOrOwner,
            has_managed_org: hasManagedOrg,
            is_super_admin: isSuperAdmin,
          },
        });
        const data = res.data;
        const primary = WORKFLOW_BY_ID[data?.primary_id];
        if (primary) {
          const alternatives = (Array.isArray(data?.alternative_ids) ? data.alternative_ids : [])
            .map((id: string) => WORKFLOW_BY_ID[id])
            .filter((item: WorkflowEntry | undefined): item is WorkflowEntry => Boolean(item));
          resolved = {
            query: q,
            primary,
            alternatives,
            reply: data.reply || primary.desc,
            confidence: Number(data.confidence ?? 0.9),
            autoNavigate: Boolean(data.auto_navigate),
            permissionOk: data.permission_ok !== false,
            requiresAuth: Boolean(data.requires_auth),
            engine: data.engine || "llm",
          };
        }
      } catch {
        // Silent graceful fallback to instant local matcher
      }

      if (!resolved) {
        const localMatches = matchWorkflowsLocally(q, roleFlags, 3);
        const primary = localMatches[0] || WORKFLOW_BY_ID["manual-guide"];
        const alternatives = localMatches.slice(1, 3);
        const permOk = hasWorkflowPermission(primary, roleFlags);
        resolved = {
          query: q,
          primary,
          alternatives,
          reply: permOk
            ? primary.desc
            : `「${primary.title}」需要 ${ROLE_BADGE_MAP[primary.roleRequired]} 权限。`,
          confidence: localMatches.length > 0 ? 0.8 : 0.35,
          autoNavigate: permOk && localMatches.length > 0,
          permissionOk: permOk,
          requiresAuth: primary.roleRequired !== "public" && !user?.id,
          engine: "local",
        };
      }

      setResult(resolved);
      setLoadingNav(false);

      if (
        autoJump &&
        resolved.autoNavigate &&
        resolved.permissionOk &&
        !resolved.requiresAuth
      ) {
        startAutoJumpCountdown(resolved.primary);
      }
    },
    [
      cancelAutoJumpCountdown,
      pathname,
      user?.id,
      isCoachOrOwner,
      hasManagedOrg,
      isSuperAdmin,
      roleFlags,
      autoJump,
      startAutoJumpCountdown,
    ]
  );

  const handleStartVoice = useCallback(async () => {
    if (recording || transcribing) return;
    cancelAutoJumpCountdown();
    setVoiceError("");
    setInterimText("");
    setVoiceElapsed(0);
    setVoiceLevels(Array(12).fill(0.2));

    const session = new VoiceCaptureSession();
    voiceSessionRef.current = session;
    try {
      setRecording(true);
      await session.start({
        onLevels: (bars) => setVoiceLevels(bars),
        onInterimText: (txt) => setInterimText(txt),
        onElapsed: (sec) => setVoiceElapsed(sec),
        onAutoStop: () => {
          void stopVoiceRef.current();
        },
      });
    } catch (err: any) {
      setRecording(false);
      voiceSessionRef.current = null;
      const msg =
        err?.name === "NotAllowedError"
          ? "未获得麦克风权限，请在浏览器地址栏允许麦克风访问或直接输入文字"
          : err?.message || "无法启动麦克风录音，请直接输入文字说明目的";
      setVoiceError(msg);
    }
  }, [recording, transcribing, cancelAutoJumpCountdown]);

  const handleStopVoiceAndRecognize = useCallback(async () => {
    const session = voiceSessionRef.current;
    if (!session) return;
    voiceSessionRef.current = null;
    setRecording(false);
    setTranscribing(true);

    try {
      const captured = await session.stop();
      let recognizedText = "";
      let specificErr = "";

      if (captured.wavBlob && captured.wavBlob.size > 44) {
        try {
          const fd = new FormData();
          const bType = String(captured.wavBlob.type || "audio/wav").toLowerCase();
          const audioExt = bType.includes("webm") ? "webm" : bType.includes("ogg") ? "ogg" : bType.includes("mp4") ? "m4a" : "wav";
          fd.append("audio", captured.wavBlob, `voice.${audioExt}`);
          const res = await apiClient.post("/api/assistant/transcribe", fd);
          if (res.data?.success && res.data?.text) {
            recognizedText = String(res.data.text).trim();
          } else if (captured.browserTranscript) {
            recognizedText = captured.browserTranscript;
          } else if (res.data?.detail) {
            specificErr = String(res.data.detail);
          }
        } catch (err: any) {
          if (captured.browserTranscript) {
            recognizedText = captured.browserTranscript;
          } else {
            specificErr = String(
              err?.response?.data?.detail || "语音识别请求失败，请重试或改用文字输入"
            );
          }
        }
      } else if (captured.browserTranscript) {
        recognizedText = captured.browserTranscript;
      }

      if (recognizedText) {
        setQuery(recognizedText);
        setInterimText("");
        setTranscribing(false);
        await handleAskAssistant(recognizedText);
        return;
      }

      setVoiceError(
        specificErr || "未检测到清晰语音，请靠近麦克风说一句（例如“我要绑定佳明手表”）"
      );
    } finally {
      setTranscribing(false);
    }
  }, [handleAskAssistant]);

  stopVoiceRef.current = handleStopVoiceAndRecognize;

  const handleCancelVoice = useCallback(() => {
    if (voiceSessionRef.current) {
      voiceSessionRef.current.cancel();
      voiceSessionRef.current = null;
    }
    setRecording(false);
    setTranscribing(false);
    setInterimText("");
  }, []);

  const handleCloseModal = useCallback(() => {
    handleCancelVoice();
    cancelAutoJumpCountdown();
    setOpen(false);
  }, [handleCancelVoice, cancelAutoJumpCountdown]);

  // Listen to global open events + Cmd+/ shortcut + Esc
  useEffect(() => {
    if (typeof window === "undefined") return;
    const onOpenEvent = (e: Event) => {
      const detail = (e as CustomEvent)?.detail || {};
      cancelAutoJumpCountdown();
      setVoiceError("");
      setOpen(true);
      if (typeof detail.query === "string" && detail.query.trim()) {
        const initQ = detail.query.trim();
        setQuery(initQ);
        void handleAskAssistant(initQ);
      } else {
        setTimeout(() => inputRef.current?.focus(), 60);
      }
      if (detail.autoVoice) {
        setTimeout(() => {
          void handleStartVoice();
        }, 120);
      }
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        setOpen((prev) => {
          const next = !prev;
          if (next) setTimeout(() => inputRef.current?.focus(), 60);
          else {
            handleCancelVoice();
            cancelAutoJumpCountdown();
          }
          return next;
        });
      } else if (e.key === "Escape" && open) {
        e.preventDefault();
        handleCloseModal();
      }
    };

    window.addEventListener("rgm-open-ops-assistant", onOpenEvent);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("rgm-open-ops-assistant", onOpenEvent);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, cancelAutoJumpCountdown, handleAskAssistant, handleStartVoice, handleCancelVoice, handleCloseModal]);

  const instantMatches = useMemo(() => {
    if (!query.trim()) return [];
    return matchWorkflowsLocally(query, roleFlags, 3);
  }, [query, roleFlags]);

  const dismissArrivalGuide = () => {
    try {
      sessionStorage.removeItem(ARRIVAL_STORAGE_KEY);
    } catch {}
    setArrivalGuide(null);
  };

  return (
    <>
      {/* ── 1. Center Modal Assistant ── */}
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="AI 操作助手"
          onClick={handleCloseModal}
          className="fixed inset-0 z-[99995] bg-black/70 backdrop-blur-sm flex items-start justify-center pt-[6vh] sm:pt-[9vh] px-3 sm:px-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-2xl rounded-3xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] shadow-2xl overflow-hidden flex flex-col max-h-[86vh]"
          >
            {/* Header */}
            <div className="px-5 py-4 border-b border-[var(--rgm-border)] bg-[var(--rgm-card-2)] flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#FC4C02] to-amber-500 flex items-center justify-center text-white shadow-lg shadow-[#FC4C02]/25 shrink-0">
                  <Compass className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-sm sm:text-base font-black text-[var(--rgm-text)]">
                      AI 操作助手 · 语音 / 文字直达入口
                    </h2>
                    <span className="px-2 py-0.5 rounded-full bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/30 text-[10px] font-extrabold text-[#FC4C02]">
                      ⌘/ 随时呼出
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--rgm-text-muted)] truncate mt-0.5">
                    告诉我你想做什么（如“绑定佳明手表”“补齐实名”“导入Excel课表”），直接带你到对应入口
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={toggleAutoJump}
                  title="开启后，AI 识别到高匹配流程入口将在 1.2 秒后自动为您跳转"
                  className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl border text-[11px] font-bold transition cursor-pointer ${
                    autoJump
                      ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-500"
                      : "bg-[var(--rgm-card-3)] border-[var(--rgm-border)] text-[var(--rgm-text-muted)]"
                  }`}
                >
                  <Zap className="w-3 h-3" />
                  <span>{autoJump ? "识别后自动直达：开" : "仅推荐不自动跳"}</span>
                </button>
                <button
                  type="button"
                  onClick={handleCloseModal}
                  aria-label="关闭 AI 操作助手"
                  className="p-1.5 rounded-xl bg-[var(--rgm-card-3)] border border-[var(--rgm-border)] text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] transition cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="overflow-y-auto p-4 sm:p-5 space-y-4">
              {/* Input + Voice Controls */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void handleAskAssistant(query);
                }}
                className="space-y-2.5"
              >
                <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] focus-within:border-[#FC4C02] transition">
                  <Sparkles className="w-4 h-4 text-[#FC4C02] ml-2.5 shrink-0" />
                  <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      cancelAutoJumpCountdown();
                    }}
                    placeholder="输入你的操作目的，或点右侧麦克风直接说话..."
                    className="flex-1 bg-transparent py-2 text-sm text-[var(--rgm-text)] placeholder:text-[var(--rgm-text-muted)] outline-none min-w-0"
                  />

                  {!recording ? (
                    <button
                      type="button"
                      disabled={transcribing}
                      onClick={() => void handleStartVoice()}
                      title="按住或点击用语音说出你想去的功能"
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/35 text-[#FC4C02] hover:bg-[#FC4C02] hover:text-white text-xs font-extrabold transition shrink-0 cursor-pointer disabled:opacity-50"
                    >
                      {transcribing ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>转写中</span>
                        </>
                      ) : (
                        <>
                          <Mic className="w-3.5 h-3.5" />
                          <span>语音输入</span>
                        </>
                      )}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => void handleStopVoiceAndRecognize()}
                      className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-extrabold transition shrink-0 cursor-pointer animate-pulse"
                    >
                      <MicOff className="w-3.5 h-3.5" />
                      <span>说完了</span>
                    </button>
                  )}

                  <button
                    type="submit"
                    disabled={!query.trim() || loadingNav || recording}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#FC4C02] hover:bg-orange-600 text-white text-xs font-black transition shrink-0 cursor-pointer disabled:opacity-45"
                  >
                    {loadingNav ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Send className="w-3.5 h-3.5" />
                    )}
                    <span className="hidden sm:inline">引导直达</span>
                  </button>
                </div>

                {/* Live Voice Recording HUD */}
                {recording && (
                  <div className="rounded-2xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/45 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex items-end gap-1 h-7 px-2 py-1 rounded-xl bg-black/20 shrink-0">
                        {voiceLevels.map((lv, idx) => (
                          <span
                            key={idx}
                            style={{ height: `${Math.round(lv * 100)}%` }}
                            className="w-1 rounded-full bg-[#FC4C02] transition-all duration-75"
                          />
                        ))}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 text-xs font-black text-[#FC4C02]">
                          <Volume2 className="w-3.5 h-3.5 shrink-0" />
                          <span>正在聆听中文语音... ({voiceElapsed}s / 25s)</span>
                        </div>
                        <div className="text-[11px] text-[var(--rgm-text-2)] truncate mt-0.5">
                          {interimText
                            ? `实时识别：${interimText}`
                            : "请说出操作目的，例如“我要绑定佳明手表”或“导入本周Excel课表”"}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={handleCancelVoice}
                        className="px-3 py-1.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs font-bold text-[var(--rgm-text-2)] cursor-pointer"
                      >
                        取消
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleStopVoiceAndRecognize()}
                        className="px-3.5 py-1.5 rounded-xl bg-[#FC4C02] text-white text-xs font-black cursor-pointer shadow-md"
                      >
                        说完了 · 立即识别
                      </button>
                    </div>
                  </div>
                )}

                {transcribing && (
                  <div className="rounded-2xl bg-[var(--rgm-blue-tint)] border border-sky-500/35 px-4 py-2.5 flex items-center gap-2 text-xs font-bold text-sky-500">
                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                    <span>正在通过阿里云百炼语音引擎识别您的指令...</span>
                  </div>
                )}

                {voiceError && (
                  <div className="rounded-2xl bg-[var(--rgm-amber-tint)] border border-amber-500/35 px-4 py-2.5 flex items-center justify-between gap-2 text-xs text-amber-500">
                    <span className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>{voiceError}</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => setVoiceError("")}
                      className="text-[11px] font-bold underline shrink-0 cursor-pointer"
                    >
                      关闭
                    </button>
                  </div>
                )}

                {/* Instant Local Autocomplete Pills while typing */}
                {!recording && instantMatches.length > 0 && !loadingNav && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                    <span className="text-[10px] font-bold text-[var(--rgm-text-muted)]">
                      ⚡ 秒速匹配：
                    </span>
                    {instantMatches.map((wf) => (
                      <button
                        key={wf.id}
                        type="button"
                        onClick={() => executeWorkflow(wf)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--rgm-card-2)] hover:border-[#FC4C02]/50 border border-[var(--rgm-border)] text-[11px] font-bold text-[var(--rgm-text-2)] hover:text-[#FC4C02] transition cursor-pointer"
                      >
                        <span>{wf.title}</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    ))}
                  </div>
                )}
              </form>

              {/* AI Guidance Result Card */}
              {loadingNav && (
                <div className="rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] p-6 flex items-center justify-center gap-2.5 text-xs font-bold text-[var(--rgm-text-2)]">
                  <Loader2 className="w-4 h-4 animate-spin text-[#FC4C02]" />
                  <span>正在匹配最佳流程入口与页面定位...</span>
                </div>
              )}

              {!loadingNav && result && (
                <div className="space-y-3">
                  {/* Primary Recommended Entry */}
                  <div className="rounded-2xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/45 p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#FC4C02] text-white text-[10px] font-black">
                            <Navigation className="w-2.5 h-2.5" />
                            最佳入口匹配
                          </span>
                          <span className="px-2 py-0.5 rounded-full bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-[10px] font-bold text-[var(--rgm-text-2)]">
                            {ROLE_BADGE_MAP[result.primary.roleRequired]}
                          </span>
                          <span className="text-[10px] text-[var(--rgm-text-muted)] font-mono">
                            匹配度 {Math.round(result.confidence * 100)}%
                          </span>
                        </div>
                        <h3 className="text-base font-black text-[var(--rgm-text)]">
                          {result.primary.title}
                        </h3>
                        <div className="text-[11px] font-bold text-[#FC4C02]">
                          路径：{result.primary.breadcrumb}
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-[var(--rgm-text-2)] leading-relaxed">
                      {result.reply}
                    </p>

                    {!result.permissionOk && (
                      <div className="rounded-xl bg-[var(--rgm-amber-tint)] border border-amber-500/35 px-3 py-2 text-[11px] text-amber-500 flex items-center gap-2">
                        <Lock className="w-3.5 h-3.5 shrink-0" />
                        <span>当前账号暂无该高级角色权限，已为您保留在当前页并提供替代入口。</span>
                      </div>
                    )}

                    {/* Micro-steps preview */}
                    <div className="rounded-xl bg-[var(--rgm-card)]/85 border border-[var(--rgm-border)] p-3 space-y-1.5">
                      <div className="text-[10px] font-extrabold uppercase tracking-wider text-[var(--rgm-text-muted)]">
                        进入后操作指引
                      </div>
                      {result.primary.steps.map((st, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-2 text-xs text-[var(--rgm-text-2)]"
                        >
                          <span className="w-4 h-4 rounded-full bg-[#FC4C02]/15 text-[#FC4C02] text-[10px] font-black flex items-center justify-center shrink-0 mt-0.5">
                            {idx + 1}
                          </span>
                          <span>{st}</span>
                        </div>
                      ))}
                    </div>

                    {/* Auto-Jump Progress Bar */}
                    {countdownActive && (
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between text-[11px] font-bold text-[#FC4C02]">
                          <span>🚀 即将自动为您直达该流程入口...</span>
                          <button
                            type="button"
                            onClick={cancelAutoJumpCountdown}
                            className="underline hover:opacity-80 cursor-pointer"
                          >
                            留在此页
                          </button>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-[var(--rgm-card)] overflow-hidden">
                          <div
                            style={{ width: `${countdownProgress}%` }}
                            className="h-full bg-[#FC4C02] transition-none"
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-2 pt-1">
                      {result.permissionOk && (
                        <button
                          type="button"
                          onClick={() => executeWorkflow(result.primary)}
                          className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#FC4C02] hover:bg-orange-600 text-white text-xs sm:text-sm font-black shadow-lg shadow-[#FC4C02]/25 transition cursor-pointer"
                        >
                          {result.requiresAuth ? (
                            <>
                              <Lock className="w-4 h-4" />
                              <span>登录后自动直达此入口</span>
                            </>
                          ) : (
                            <>
                              <ArrowRight className="w-4 h-4" />
                              <span>立即前往此流程入口</span>
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Alternative Workflows */}
                  {result.alternatives.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[11px] font-extrabold text-[var(--rgm-text-muted)] px-1">
                        你可能还想找这些相关入口
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {result.alternatives.map((alt) => {
                          const perm = hasWorkflowPermission(alt, roleFlags);
                          return (
                            <button
                              key={alt.id}
                              type="button"
                              disabled={!perm}
                              onClick={() => executeWorkflow(alt)}
                              className="text-left p-3 rounded-2xl bg-[var(--rgm-card-2)] hover:border-[#FC4C02]/45 border border-[var(--rgm-border)] transition flex items-center justify-between gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              <div className="min-w-0">
                                <div className="text-xs font-bold text-[var(--rgm-text)] truncate">
                                  {alt.title}
                                </div>
                                <div className="text-[10px] text-[var(--rgm-text-muted)] truncate mt-0.5">
                                  {alt.breadcrumb}
                                </div>
                              </div>
                              <ArrowRight className="w-3.5 h-3.5 text-[#FC4C02] shrink-0" />
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Grouped Quick Intent Chips (shown when idle or below result) */}
              <div className="space-y-3 pt-1">
                {QUICK_INTENT_CHIPS.map((grp) => (
                  <div key={grp.groupLabel} className="space-y-1.5">
                    <div className="text-[11px] font-extrabold text-[var(--rgm-text-muted)] px-0.5">
                      {grp.groupLabel}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {grp.items.map((chip) => (
                        <button
                          key={chip.label}
                          type="button"
                          onClick={() => {
                            setQuery(chip.query);
                            void handleAskAssistant(chip.query);
                          }}
                          className="px-3 py-1.5 rounded-xl bg-[var(--rgm-card-2)] hover:bg-[var(--rgm-brand-tint)] border border-[var(--rgm-border)] hover:border-[#FC4C02]/40 text-[11px] font-bold text-[var(--rgm-text-2)] hover:text-[#FC4C02] transition cursor-pointer"
                        >
                          {chip.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Footer */}
            <div className="px-5 py-2.5 border-t border-[var(--rgm-border)] bg-[var(--rgm-card-2)] flex items-center justify-between text-[11px] text-[var(--rgm-text-muted)]">
              <span>支持中文口语提问 · 阿里云百炼 ASR 语音直达</span>
              <button
                type="button"
                onClick={toggleAutoJump}
                className="sm:hidden font-bold text-[#FC4C02] cursor-pointer"
              >
                {autoJump ? "自动跳转：开" : "自动跳转：关"}
              </button>
              <span className="hidden sm:inline">Esc 关闭 · Enter 引导</span>
            </div>
          </div>
        </div>
      )}

      {/* ── 2. Cross-Page Persistent Arrival Step Guide Banner (Bottom-Left, avoids bottom-right CoachChatBox) ── */}
      {arrivalGuide && !open && (
        <aside
          aria-label="AI 流程落地指引"
          className="fixed bottom-20 lg:bottom-6 left-4 lg:left-[88px] xl:left-[240px] z-[60] w-[calc(100vw-2rem)] max-w-sm rounded-2xl bg-[var(--rgm-card)] border border-[#FC4C02]/45 shadow-2xl p-4 space-y-2.5"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="inline-flex items-center gap-1.5 text-[10px] font-black uppercase tracking-wider text-[#FC4C02]">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>AI 操作向导 · 已定位入口</span>
              </div>
              <div className="text-xs sm:text-sm font-black text-[var(--rgm-text)] mt-0.5 truncate">
                {arrivalGuide.title}
              </div>
              <div className="text-[10px] text-[var(--rgm-text-muted)] truncate">
                {arrivalGuide.breadcrumb}
              </div>
            </div>
            <button
              type="button"
              onClick={dismissArrivalGuide}
              aria-label="关闭步骤指引"
              className="p-1 rounded-lg text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] cursor-pointer shrink-0"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-1.5 pt-1 border-t border-[var(--rgm-divider)]">
            {arrivalGuide.steps.map((st, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 text-[11px] text-[var(--rgm-text-2)] leading-snug"
              >
                <span className="w-4 h-4 rounded-full bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/30 text-[#FC4C02] text-[10px] font-black flex items-center justify-center shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <span>{st}</span>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between gap-2 pt-1">
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => openAiOperationAssistant()}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-[11px] font-bold text-[var(--rgm-text-2)] hover:text-[#FC4C02] transition cursor-pointer"
              >
                <Mic className="w-3 h-3" />
                换个目的
              </button>
              {arrivalGuide.href && (
                <button
                  type="button"
                  onClick={() => {
                    dispatchRgmNavIntent(arrivalGuide.href!, arrivalGuide.perspective);
                    router.push(arrivalGuide.href!);
                  }}
                  title="如果刚关掉了弹窗，可点此重新展开"
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/30 text-[11px] font-bold text-[#FC4C02] hover:opacity-90 transition cursor-pointer"
                >
                  <RefreshCw className="w-3 h-3" />
                  重新定位
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={dismissArrivalGuide}
              className="px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-500 text-[11px] font-extrabold hover:bg-emerald-500/25 transition cursor-pointer"
            >
              知道了
            </button>
          </div>
        </aside>
      )}
    </>
  );
}
