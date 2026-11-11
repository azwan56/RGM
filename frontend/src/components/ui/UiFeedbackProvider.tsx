"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { usePathname } from "next/navigation";
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from "lucide-react";
import { trackWebPageView } from "@/lib/telemetry";

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

export interface ConfirmDialogOptions {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}

interface PendingConfirmRequest {
  options: Required<ConfirmDialogOptions>;
  resolve: (confirmed: boolean) => void;
}

interface UiFeedbackContextValue {
  showToast: (message: string, variant?: ToastVariant, durationMs?: number) => void;
  askConfirm: (input: string | ConfirmDialogOptions) => Promise<boolean>;
}

const UiFeedbackContext = createContext<UiFeedbackContextValue | null>(null);

let _imperativeToast: ((message: string, variant?: ToastVariant, durationMs?: number) => void) | null = null;
let _imperativeConfirm: ((input: string | ConfirmDialogOptions) => Promise<boolean>) | null = null;

function inferToastVariant(msg: string): ToastVariant {
  const s = msg.trim();
  if (
    s.includes("❌") ||
    s.includes("失败") ||
    s.includes("错误") ||
    s.includes("异常") ||
    s.includes("无权") ||
    s.includes("拒绝")
  ) {
    return "error";
  }
  if (
    s.includes("⚠️") ||
    s.includes("请先") ||
    s.includes("请输入") ||
    s.includes("请选择") ||
    s.includes("不能") ||
    s.includes("无法") ||
    s.includes("尚未") ||
    s.includes("上限")
  ) {
    return "warning";
  }
  if (
    s.includes("✅") ||
    s.includes("🎉") ||
    s.includes("成功") ||
    s.includes("已保存") ||
    s.includes("已复制") ||
    s.includes("已发布") ||
    s.includes("已撤回") ||
    s.includes("已解除") ||
    s.includes("已生成") ||
    s.includes("已更新")
  ) {
    return "success";
  }
  return "info";
}

function normalizeConfirmOptions(input: string | ConfirmDialogOptions): Required<ConfirmDialogOptions> {
  if (typeof input === "string") {
    const msg = input.trim();
    const isDanger =
      msg.includes("删除") ||
      msg.includes("解除") ||
      msg.includes("移交") ||
      msg.includes("撤回") ||
      msg.includes("清空") ||
      msg.includes("注销");
    return {
      title: isDanger ? "请确认此操作" : "操作确认",
      message: msg,
      confirmText: isDanger ? "确认执行" : "确定",
      cancelText: "取消",
      danger: isDanger,
    };
  }
  const msg = String(input.message || "").trim();
  const isDanger =
    input.danger ??
    (msg.includes("删除") ||
      msg.includes("解除") ||
      msg.includes("移交") ||
      msg.includes("撤回") ||
      msg.includes("清空"));
  return {
    title: input.title || (isDanger ? "请确认此操作" : "操作确认"),
    message: msg,
    confirmText: input.confirmText || (isDanger ? "确认执行" : "确定"),
    cancelText: input.cancelText || "取消",
    danger: isDanger,
  };
}

/**
 * Imperative non-blocking Toast notification (safe drop-in replacement for window.alert)
 */
export function showToast(message: string, variant?: ToastVariant, durationMs?: number): void {
  const clean = String(message ?? "").trim();
  if (!clean) return;
  if (_imperativeToast) {
    _imperativeToast(clean, variant, durationMs);
    return;
  }
  if (typeof window !== "undefined") {
    console.info("[Toast]", clean);
  }
}

/**
 * Imperative non-blocking async Confirm dialog (safe replacement for window.confirm)
 */
export function askConfirm(input: string | ConfirmDialogOptions): Promise<boolean> {
  if (_imperativeConfirm) {
    return _imperativeConfirm(input);
  }
  if (typeof window !== "undefined" && typeof window.confirm === "function") {
    const msg = typeof input === "string" ? input : input.message;
    return Promise.resolve(window.confirm(msg));
  }
  return Promise.resolve(false);
}

export function useUiFeedback(): UiFeedbackContextValue {
  const ctx = useContext(UiFeedbackContext);
  if (ctx) return ctx;
  return { showToast, askConfirm };
}

export default function UiFeedbackProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [activeConfirm, setActiveConfirm] = useState<PendingConfirmRequest | null>(null);
  const confirmQueueRef = useRef<PendingConfirmRequest[]>([]);

  useEffect(() => {
    if (pathname) {
      trackWebPageView(pathname);
    }
  }, [pathname]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    (message: string, variant?: ToastVariant, durationMs?: number) => {
      const clean = String(message ?? "").trim();
      if (!clean) return;
      const resolvedVariant = variant || inferToastVariant(clean);
      const id = `t_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
      const autoMs =
        durationMs ??
        (resolvedVariant === "error" || clean.includes("\n") || clean.length > 42 ? 5200 : 3600);

      setToasts((prev) => [...prev.slice(-3), { id, message: clean, variant: resolvedVariant }]);
      setTimeout(() => {
        dismissToast(id);
      }, autoMs);
    },
    [dismissToast]
  );

  const enqueueConfirm = useCallback((input: string | ConfirmDialogOptions): Promise<boolean> => {
    const options = normalizeConfirmOptions(input);
    return new Promise<boolean>((resolve) => {
      const req: PendingConfirmRequest = { options, resolve };
      setActiveConfirm((curr) => {
        if (!curr) return req;
        confirmQueueRef.current.push(req);
        return curr;
      });
    });
  }, []);

  const settleActiveConfirm = useCallback((confirmed: boolean) => {
    setActiveConfirm((curr) => {
      if (curr) {
        try {
          curr.resolve(confirmed);
        } catch {}
      }
      const next = confirmQueueRef.current.shift() || null;
      return next;
    });
  }, []);

  useEffect(() => {
    _imperativeToast = pushToast;
    _imperativeConfirm = enqueueConfirm;

    // Non-blocking fallback bridge in case any dynamic script still calls window.alert
    const origAlert = typeof window !== "undefined" ? window.alert : undefined;
    if (typeof window !== "undefined") {
      window.alert = (msg?: any) => {
        pushToast(String(msg ?? ""));
      };
    }

    return () => {
      _imperativeToast = null;
      _imperativeConfirm = null;
      if (typeof window !== "undefined" && origAlert) {
        window.alert = origAlert;
      }
    };
  }, [pushToast, enqueueConfirm]);

  useEffect(() => {
    if (!activeConfirm) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        settleActiveConfirm(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeConfirm, settleActiveConfirm]);

  return (
    <UiFeedbackContext.Provider value={{ showToast: pushToast, askConfirm: enqueueConfirm }}>
      {children}

      {/* Non-Blocking Toast Stack */}
      {toasts.length > 0 && (
        <div
          aria-live="polite"
          className="fixed top-4 right-4 left-4 sm:left-auto sm:w-[400px] z-[99999] flex flex-col gap-2.5 pointer-events-none"
        >
          {toasts.map((t) => {
            const borderTone =
              t.variant === "success"
                ? "border-emerald-500/40"
                : t.variant === "error"
                ? "border-rose-500/45"
                : t.variant === "warning"
                ? "border-amber-500/45"
                : "border-[#FC4C02]/40";
            return (
              <div
                key={t.id}
                role="status"
                className={`pointer-events-auto flex items-start gap-3 px-4 py-3.5 rounded-2xl bg-[var(--rgm-card)] border ${borderTone} text-[var(--rgm-text)] shadow-2xl backdrop-blur-xl transition-all duration-200`}
              >
                <div className="mt-0.5 shrink-0">
                  {t.variant === "success" ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                  ) : t.variant === "error" ? (
                    <XCircle className="w-5 h-5 text-rose-500" />
                  ) : t.variant === "warning" ? (
                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                  ) : (
                    <Info className="w-5 h-5 text-[#FC4C02]" />
                  )}
                </div>
                <div className="flex-1 text-xs sm:text-sm font-medium leading-relaxed whitespace-pre-line break-words">
                  {t.message}
                </div>
                <button
                  type="button"
                  onClick={() => dismissToast(t.id)}
                  aria-label="关闭通知"
                  className="shrink-0 p-1 rounded-lg text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] hover:bg-white/10 transition cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Accessible Non-Blocking Confirm Dialog */}
      {activeConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-[99998] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          onClick={() => settleActiveConfirm(false)}
        >
          <div
            className="w-full max-w-md rounded-3xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] p-6 shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <span
                  className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
                    activeConfirm.options.danger
                      ? "bg-rose-500/15 text-rose-500"
                      : "bg-[#FC4C02]/15 text-[#FC4C02]"
                  }`}
                >
                  <AlertTriangle className="w-4 h-4" />
                </span>
                <h3 className="text-base font-bold text-[var(--rgm-text)]">
                  {activeConfirm.options.title}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => settleActiveConfirm(false)}
                className="p-1 rounded-lg text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs sm:text-sm text-[var(--rgm-text-2)] leading-relaxed whitespace-pre-line break-words">
              {activeConfirm.options.message}
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => settleActiveConfirm(false)}
                className="px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold bg-[var(--rgm-card-2)] hover:opacity-90 border border-[var(--rgm-border)] text-[var(--rgm-text-2)] transition cursor-pointer"
              >
                {activeConfirm.options.cancelText}
              </button>
              <button
                type="button"
                autoFocus
                onClick={() => settleActiveConfirm(true)}
                className={`px-5 py-2 rounded-xl text-xs sm:text-sm font-bold text-white shadow-lg transition cursor-pointer ${
                  activeConfirm.options.danger
                    ? "bg-rose-600 hover:bg-rose-500"
                    : "bg-[#FC4C02] hover:bg-[#e54400]"
                }`}
              >
                {activeConfirm.options.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
    </UiFeedbackContext.Provider>
  );
}
