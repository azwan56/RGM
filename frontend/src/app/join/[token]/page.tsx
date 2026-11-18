"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import AuthModal from "@/components/AuthModal";
import { ClubShowcaseDetail } from "@/components/community/ShowcaseViews";
import apiClient from "@/lib/apiClient";
import { supabase } from "@/lib/supabase";
import { useUiFeedback } from "@/components/ui/UiFeedbackProvider";
import { Sparkles, CheckCircle2, ShieldCheck, ArrowRight } from "lucide-react";

export default function TargetedInviteJoinPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const router = useRouter();
  const { showToast } = useUiFeedback();

  const [viewerUid, setViewerUid] = useState<string>("");
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(async ({ data }) => {
      const uid = data?.session?.user?.id || "";
      if (active) setViewerUid(uid);
      try {
        const q = uid ? `?viewer_uid=${encodeURIComponent(uid)}` : "";
        const res = await apiClient.get(`/api/community/invites/${encodeURIComponent(token)}${q}`);
        if (active) setPreview(res.data);
      } catch (e: any) {
        if (active) setErrorMsg(e?.message || "特邀函链接无效或已过期");
      } finally {
        if (active) setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [token]);

  async function handleRespond(action: "accept" | "decline") {
    if (!viewerUid) {
      if (typeof window !== "undefined") {
        localStorage.setItem("rgm_pending_targeted_invite_token", token);
      }
      setAuthOpen(true);
      return;
    }
    setSubmitting(true);
    try {
      const res = await apiClient.post(`/api/community/invites/${encodeURIComponent(token)}/respond`, {
        user_id: viewerUid,
        action,
      });
      if (action === "accept") {
        if (typeof window !== "undefined" && res.data?.club_id) {
          localStorage.setItem("rgm_active_club_id", res.data.club_id);
          localStorage.removeItem("rgm_pending_targeted_invite_token");
        }
        showToast(
          `🎉 已免码兼入【${res.data?.club_name}】${res.data?.preassigned_group ? ` · 已编入 ${res.data.preassigned_group}` : ""}`
        );
        router.push("/dashboard/team");
      } else {
        showToast("已婉拒本次邀约（90天内不会重复打扰）");
        router.push("/dashboard");
      }
    } catch (e: any) {
      showToast("操作失败：" + (e?.message || ""), "error");
    } finally {
      setSubmitting(false);
    }
  }

  const inv = preview?.invite;

  return (
    <div className="min-h-screen bg-[var(--rgm-bg)] text-[var(--rgm-text)]">
      <Navbar />
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {loading ? (
          <div className="rgm-bento-card p-12 text-center text-xs text-[var(--rgm-text-muted)]">
            正在展开金色定向特邀函与跑团品牌展厅...
          </div>
        ) : errorMsg ? (
          <div className="rgm-bento-card p-10 text-center space-y-3">
            <div className="text-base font-black text-[var(--rgm-text)]">{errorMsg}</div>
            <Link href="/dashboard/plaza" className="inline-block px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-bold">
              逛逛精选跑团展厅 ›
            </Link>
          </div>
        ) : inv ? (
          <>
            {/* Golden Invitation Hero Banner */}
            <div className="rgm-bento-card p-6 sm:p-8 border-2 border-amber-500/45 bg-[var(--rgm-amber-tint)] space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1.5">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FC4C02] text-white text-xs font-black">
                    <Sparkles className="w-3.5 h-3.5" />
                    金色定向兼团特邀函 · 免输入邀请码
                  </div>
                  <h1 className="text-xl sm:text-2xl font-black text-[var(--rgm-text)]">
                    【{inv.club_name}】{inv.inviter_name} 诚邀您加入
                    {inv.preassigned_group ? `（预编入 ${inv.preassigned_group}）` : ""}
                  </h1>
                  <p className="text-xs sm:text-sm text-[var(--rgm-text-2)]">
                    {inv.reason_tag || "跑力与日常打卡时段高度同频"}
                    {inv.custom_message ? ` — “${inv.custom_message}”` : ""}
                  </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                  {preview?.viewer_already_member ? (
                    <Link
                      href="/dashboard/team"
                      className="px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-black flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-4 h-4" /> 已是该团成员 · 进入跑团 ›
                    </Link>
                  ) : (
                    <>
                      {viewerUid && (
                        <button
                          type="button"
                          disabled={submitting}
                          onClick={() => handleRespond("decline")}
                          className="px-3.5 py-2.5 rounded-xl border border-[var(--rgm-border)] bg-[var(--rgm-card)] text-xs font-bold text-[var(--rgm-text-2)] cursor-pointer"
                        >
                          暂不加入
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => handleRespond("accept")}
                        className="px-5 py-2.5 rounded-xl bg-[#FC4C02] text-white text-xs font-black flex items-center gap-1.5 shadow-lg cursor-pointer hover:opacity-90"
                      >
                        {viewerUid
                          ? `免码一键兼团${inv.preassigned_group ? `并编入 ${inv.preassigned_group}` : ""}`
                          : "登录并一键免码兼团"}
                        <ArrowRight className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text-2)] flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
                <span>{preview?.non_exclusive_notice}</span>
              </div>
            </div>

            {/* Embedded W13.2 Club Brand Showcase & Photo Gallery */}
            {inv.attach_showcase && (
              <ClubShowcaseDetail
                clubId={inv.club_id}
                viewerUid={viewerUid || undefined}
                inviteToken={token}
              />
            )}
          </>
        ) : null}
      </main>
      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} initialTab="wechat" />
    </div>
  );
}
