"use client";

import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[RGM Dashboard Error]", error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full rounded-2xl border border-[var(--rgm-border)] bg-[var(--rgm-card)] p-6 text-center space-y-4">
        <div className="text-3xl">📊</div>
        <h2 className="text-lg font-black text-[var(--rgm-text)]">驾驶舱视图渲染异常</h2>
        <p className="text-xs text-[var(--rgm-text-muted)] leading-relaxed">
          {error?.message || "数据加载中断，您的训练记录与手表连接状态安全无损。"}
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => reset()}
            className="px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-bold hover:opacity-90 cursor-pointer"
          >
            重试视图
          </button>
          <a
            href="/dashboard"
            className="px-4 py-2 rounded-xl border border-[var(--rgm-border)] text-xs font-bold text-[var(--rgm-text)]"
          >
            回到工作台
          </a>
        </div>
      </div>
    </div>
  );
}
