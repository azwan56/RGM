"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[RGM App Error]", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--rgm-bg)] text-[var(--rgm-text)] px-4">
      <div className="max-w-md w-full rounded-2xl border border-[var(--rgm-border)] bg-[var(--rgm-card)] p-6 text-center space-y-4">
        <div className="text-3xl">🏃</div>
        <h2 className="text-lg font-black">页面加载遇到临时波动</h2>
        <p className="text-xs text-[var(--rgm-text-muted)] leading-relaxed">
          请点击下方按钮重试；若持续出现，请刷新浏览器或重新登录。
        </p>
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => reset()}
            className="px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-bold hover:opacity-90 cursor-pointer"
          >
            重新加载
          </button>
          <a
            href="/"
            className="px-4 py-2 rounded-xl border border-[var(--rgm-border)] text-xs font-bold hover:bg-white/5"
          >
            返回首页
          </a>
        </div>
      </div>
    </div>
  );
}
