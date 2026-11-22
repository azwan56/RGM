"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import ComplianceFooter from "@/components/ComplianceFooter";
import AuthCockpitPanel from "@/components/web3/AuthCockpitPanel";
import { supabase } from "@/lib/supabase";
import { ShieldCheck, Sparkles, UserPlus, Watch } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [initialTab, setInitialTab] = useState<"wechat" | "watch" | "email">("watch");
  const [pendingInvite, setPendingInvite] = useState<{ club_id?: string; invite_code?: string } | null>(null);

  function getPostLoginRedirect(): string {
    if (typeof window !== "undefined") {
      const targetedTok = localStorage.getItem("rgm_pending_targeted_invite_token");
      if (targetedTok) {
        return `/join/${encodeURIComponent(targetedTok)}`;
      }
      if (localStorage.getItem("rgm_pending_club_invite")) {
        return "/dashboard/team";
      }
    }
    return "/dashboard";
  }

  useEffect(() => {
    if (typeof window !== "undefined") {
      const mode = new URLSearchParams(window.location.search).get("mode");
      if (mode === "wechat" || mode === "watch" || mode === "email") {
        setInitialTab(mode);
      }
      try {
        const rawInv = localStorage.getItem("rgm_pending_club_invite");
        if (rawInv) {
          const parsed = JSON.parse(rawInv);
          if (parsed?.club_id) setPendingInvite(parsed);
        }
      } catch {}
    }
    supabase.auth.getSession().then(({ data }) => {
      if (data?.session?.user) {
        router.push(getPostLoginRedirect());
      }
    });
  }, [router]);

  return (
    <div className="min-h-screen bg-[var(--rgm-bg)] text-[var(--rgm-text)] flex flex-col">
      <Navbar />

      <main className="flex-1 flex items-center justify-center px-4 sm:px-6 py-10">
        <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Context & Incoming Invite Card */}
          <div className="lg:col-span-6 space-y-5">
            {pendingInvite && (
              <div className="p-4 rounded-2xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/40 flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#FC4C02] text-white flex items-center justify-center shrink-0">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <div className="text-xs font-black text-[#FC4C02]">
                    已暂存你的跑团入团邀请 {pendingInvite.invite_code ? `(${pendingInvite.invite_code})` : ""}
                  </div>
                  <p className="text-xs text-[var(--rgm-text-2)] leading-relaxed">
                    完成登录后将自动回跳跑团邀请落地页并保留邀请人关联，无需重新扫码或重复输入邀请码。
                  </p>
                </div>
              </div>
            )}

            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <img
                  src="/logo.png"
                  alt="万跑跑团助手 Logo"
                  width={48}
                  height={48}
                  className="w-12 h-12 rounded-2xl object-contain bg-white shadow-md"
                />
                <div>
                  <h1 className="text-2xl sm:text-3xl font-black text-[var(--rgm-text)]">
                    万跑跑团助手 · Web 3.0
                  </h1>
                  <p className="text-xs text-[var(--rgm-text-muted)]">
                    微信小程序与桌面端同一跑者身份档案，毫秒级同步
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="rgm-bento-card p-4 space-y-1.5">
                <Watch className="w-4 h-4 text-[#FC4C02]" />
                <div className="text-xs font-bold text-[var(--rgm-text)]">佳明双区直连</div>
                <div className="text-[11px] text-[var(--rgm-text-muted)]">支持 garmin.cn 与国际区及 MFA</div>
              </div>
              <div className="rgm-bento-card p-4 space-y-1.5">
                <Sparkles className="w-4 h-4 text-sky-500" />
                <div className="text-xs font-bold text-[var(--rgm-text)]">Canova 双栏舱</div>
                <div className="text-[11px] text-[var(--rgm-text-muted)]">左看周期矩阵 · 右测对话调课</div>
              </div>
              <div className="rgm-bento-card p-4 space-y-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-500" />
                <div className="text-xs font-bold text-[var(--rgm-text)]">4 级隐私脱敏</div>
                <div className="text-[11px] text-[var(--rgm-text-muted)]">AES-256 实名加密底账保护</div>
              </div>
            </div>
          </div>

          {/* Right Auth Cockpit */}
          <div className="lg:col-span-6">
            <AuthCockpitPanel
              initialTab={initialTab}
              onSuccess={() => router.push(getPostLoginRedirect())}
            />
          </div>
        </div>
      </main>
      <ComplianceFooter />
    </div>
  );
}
