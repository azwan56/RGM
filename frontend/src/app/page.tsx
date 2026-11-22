"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import Navbar from "@/components/Navbar";
import ComplianceFooter from "@/components/ComplianceFooter";
import AuthCockpitPanel from "@/components/web3/AuthCockpitPanel";
import {
  Activity,
  ArrowRight,
  ClipboardCheck,
  Shield,
  Sparkles,
  Users,
  Watch,
} from "lucide-react";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data?.session?.user || null);
      setAuthLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null);
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  function getPostLoginRedirect(): string {
    if (typeof window !== "undefined" && localStorage.getItem("rgm_pending_club_invite")) {
      return "/dashboard/team";
    }
    return "/dashboard";
  }

  return (
    <div className="min-h-screen bg-[var(--rgm-bg)] text-[var(--rgm-text)] relative overflow-hidden">
      <Navbar />

      {/* Subtle Ambient Accent Orbs */}
      <div className="absolute -top-32 -left-32 w-[420px] h-[420px] rounded-full bg-[#FC4C02]/10 blur-[120px] pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-[460px] h-[460px] rounded-full bg-sky-500/10 blur-[140px] pointer-events-none" />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-10 lg:py-16 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-center">
          {/* Left 7 Cols: Brand Hero + 3 Bento Capability Cards + Community Proof Strip */}
          <div className="lg:col-span-7 space-y-8">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[var(--rgm-green-tint)] border border-emerald-500/35 text-xs font-bold text-emerald-500">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                佳明双区 · 高驰 · 苹果 · 华为 · 颂拓全生态直连
              </div>

              <h1 className="text-4xl sm:text-5xl xl:text-6xl font-black tracking-tight leading-tight text-[var(--rgm-text)]">
                记录. <span className="text-[#FC4C02]">竞争.</span> 进化.
              </h1>

              <div className="space-y-1.5 text-sm sm:text-base text-[var(--rgm-text-2)] max-w-2xl leading-relaxed">
                <p>专为严肃跑者、跑团教练与高校校友大群打造的大屏科学训练工作台。</p>
                <p className="text-xs sm:text-sm text-[var(--rgm-text-muted)]">
                  手表保存 1–3 分钟自动同步 · 微信小程序与 Web 毫秒级数据互通
                </p>
              </div>
            </div>

            {/* 3 Bento Value Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div
                id="ecosystem"
                className="rgm-bento-card p-5 space-y-3 hover:border-[#FC4C02]/45 transition"
              >
                <div className="w-10 h-10 rounded-xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/30 flex items-center justify-center text-[#FC4C02]">
                  <Watch className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-black text-[var(--rgm-text)]">双区手表直连</h3>
                  <p className="text-xs font-bold text-[#FC4C02]">garmin.cn / com + COROS</p>
                  <p className="text-[11px] text-[var(--rgm-text-2)] leading-relaxed">
                    自动抓取 GPS 分段、步频、心率与夜间 HRV/睡眠恢复
                  </p>
                </div>
                <div className="h-1 w-full rounded-full bg-[var(--rgm-card-3)] overflow-hidden">
                  <div className="h-full w-4/5 bg-[#FC4C02] rounded-full" />
                </div>
              </div>

              <div
                id="canova"
                className="rgm-bento-card p-5 space-y-3 hover:border-sky-500/45 transition"
              >
                <div className="w-10 h-10 rounded-xl bg-[var(--rgm-blue-tint)] border border-sky-500/30 flex items-center justify-center text-sky-500">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-black text-[var(--rgm-text)]">Canova AI 教练</h3>
                  <p className="text-xs font-bold text-sky-500">CTL / ATL / TSB 建模</p>
                  <p className="text-[11px] text-[var(--rgm-text-2)] leading-relaxed">
                    6 级专项配速区间、赛前 Taper 减量推演与实时调课
                  </p>
                </div>
                <div className="h-1 w-full rounded-full bg-[var(--rgm-card-3)] overflow-hidden">
                  <div className="h-full w-3/4 bg-sky-500 rounded-full" />
                </div>
              </div>

              <div
                id="clubs"
                className="rgm-bento-card p-5 space-y-3 hover:border-emerald-500/45 transition"
              >
                <div className="w-10 h-10 rounded-xl bg-[var(--rgm-green-tint)] border border-emerald-500/30 flex items-center justify-center text-emerald-500">
                  <Users className="w-5 h-5" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-sm font-black text-[var(--rgm-text)]">大群 &amp; 跑团协同</h3>
                  <p className="text-xs font-bold text-emerald-500">14天实名 + 选兔雷达</p>
                  <p className="text-[11px] text-[var(--rgm-text-2)] leading-relaxed">
                    教练 5 秒连续批阅、门岗约跑列车、分团 PK 战报一键发群
                  </p>
                </div>
                <div className="h-1 w-full rounded-full bg-[var(--rgm-card-3)] overflow-hidden">
                  <div className="h-full w-2/3 bg-emerald-500 rounded-full" />
                </div>
              </div>
            </div>

            {/* Bottom Live Ecosystem Strip */}
            <div className="rgm-bento-card p-4 sm:p-5 bg-[var(--rgm-card-2)] grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <div className="text-lg sm:text-xl font-black text-[var(--rgm-text)] tabular-nums">全生态</div>
                <div className="text-[11px] text-[var(--rgm-text-muted)]">跑团与校友大群协同</div>
              </div>
              <div>
                <div className="text-lg sm:text-xl font-black text-[#FC4C02] tabular-nums">Web 3.0</div>
                <div className="text-[11px] text-[var(--rgm-text-muted)]">暗黑 / 亮色双色系</div>
              </div>
              <div>
                <div className="text-lg sm:text-xl font-black text-emerald-500 tabular-nums">AES-256</div>
                <div className="text-[11px] text-[var(--rgm-text-muted)]">实名与口令脱敏隔离</div>
              </div>
              <div>
                <div className="text-lg sm:text-xl font-black text-sky-500 tabular-nums">3 视角</div>
                <div className="text-[11px] text-[var(--rgm-text-muted)]">跑者 / 团教 / 管理</div>
              </div>
            </div>
          </div>

          {/* Right 5 Cols: Floating 3-in-1 Auth Cockpit or Logged-in Role Launcher */}
          <div className="lg:col-span-5">
            {authLoading ? (
              <div className="rgm-bento-card p-8 space-y-4 animate-pulse">
                <div className="h-7 w-40 rounded-lg bg-[var(--rgm-card-3)]" />
                <div className="h-10 w-full rounded-xl bg-[var(--rgm-card-3)]" />
                <div className="h-48 w-full rounded-2xl bg-[var(--rgm-card-3)]" />
              </div>
            ) : user ? (
              <div className="rounded-3xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] border-t-[3px] border-t-[#FC4C02] p-6 sm:p-7 shadow-2xl space-y-5">
                <div className="space-y-1">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[var(--rgm-green-tint)] text-emerald-500 text-[11px] font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    账号已在线
                  </div>
                  <h2 className="text-xl font-black text-[var(--rgm-text)]">
                    欢迎回来，{user.display_name || user.user_metadata?.display_name || user.email || "跑友"}
                  </h2>
                  <p className="text-xs text-[var(--rgm-text-muted)]">
                    选择你的角色工作台入口，或进入桌面端使用 ⌘K 全局指令快速切换
                  </p>
                </div>

                <div className="space-y-2.5">
                  <Link
                    href="/dashboard"
                    className="flex items-center justify-between p-4 rounded-2xl bg-[#FC4C02] hover:bg-orange-600 text-white transition shadow-lg shadow-[#FC4C02]/25"
                  >
                    <div className="flex items-center gap-3">
                      <Activity className="w-5 h-5 shrink-0" />
                      <div>
                        <div className="text-sm font-black">普通跑者全息工作台</div>
                        <div className="text-[11px] opacity-90">今日 Canova 处方 · 课表 · 跑团 · 隐私中心</div>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 shrink-0" />
                  </Link>

                  <Link
                    href="/dashboard/team?tab=coach"
                    className="flex items-center justify-between p-4 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-sky-500/45 text-[var(--rgm-text)] transition"
                  >
                    <div className="flex items-center gap-3">
                      <ClipboardCheck className="w-5 h-5 text-sky-500 shrink-0" />
                      <div>
                        <div className="text-sm font-bold">团长与教练工作台</div>
                        <div className="text-[11px] text-[var(--rgm-text-muted)]">信号灯罗盘 · 5秒连续批阅 · 选兔雷达</div>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-[var(--rgm-text-muted)] shrink-0" />
                  </Link>

                  <Link
                    href="/dashboard/admin"
                    className="flex items-center justify-between p-4 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-amber-500/45 text-[var(--rgm-text)] transition"
                  >
                    <div className="flex items-center gap-3">
                      <Shield className="w-5 h-5 text-amber-500 shrink-0" />
                      <div>
                        <div className="text-sm font-bold">大群与平台超管控制塔</div>
                        <div className="text-[11px] text-[var(--rgm-text-muted)]">实名核验 · 组织拓扑 · 增长遥测 · 运维排障</div>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-[var(--rgm-text-muted)] shrink-0" />
                  </Link>
                </div>
              </div>
            ) : (
              <AuthCockpitPanel
                initialTab="watch"
                onSuccess={() => router.push(getPostLoginRedirect())}
              />
            )}
          </div>
        </div>
      </main>
      <ComplianceFooter />
    </div>
  );
}
