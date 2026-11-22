"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import ComplianceFooter from "@/components/ComplianceFooter";
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
        if (active) {
          setPreview(res.data);
          // If opened with auto_join=1 or returning from pending login, auto-accept & enter the club directly
          const sp = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
          const pendingToken = typeof window !== "undefined" ? localStorage.getItem("rgm_pending_targeted_invite_token") : "";
          const shouldAutoJoin = Boolean(uid && (sp?.get("auto_join") === "1" || pendingToken === token));
          if (shouldAutoJoin && res.data?.invite) {
            if (res.data.viewer_already_member) {
              localStorage.setItem("rgm_active_club_id", res.data.invite.club_id);
              localStorage.removeItem("rgm_pending_targeted_invite_token");
              router.push("/dashboard/team");
            } else {
              try {
                const joinRes = await apiClient.post(`/api/community/invites/${encodeURIComponent(token)}/respond`, {
                  user_id: uid,
                  action: "accept",
                });
                if (joinRes.data?.club_id) {
                  localStorage.setItem("rgm_active_club_id", joinRes.data.club_id);
                  localStorage.removeItem("rgm_pending_targeted_invite_token");
                }
                showToast(
                  `🎉 已免码直入【${joinRes.data?.club_name || res.data.invite.club_name}】${
                    joinRes.data?.preassigned_group ? ` · 已编入 ${joinRes.data.preassigned_group}` : ""
                  }`
                );
                router.push("/dashboard/team");
              } catch {
                // Fall back to interactive card if auto-join fails
              }
            }
          }
        }
      } catch (e: any) {
        if (active) {
          setErrorMsg(
            e?.response?.data?.detail || "特邀函链接无效或已失效，请联系跑团团长重新发起邀约"
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [token, router, showToast]);

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
      showToast("操作失败：" + (e?.response?.data?.detail || e?.message || ""), "error");
    } finally {
      setSubmitting(false);
    }
  }

  const inv = preview?.invite;
  const sc = preview?.showcase_summary || preview?.showcase_preview?.showcase || inv || {};
  const st = preview?.showcase_summary?.verified_stats || preview?.showcase_preview?.verified_stats || inv?.verified_stats || {};
  const photos: any[] = preview?.showcase_summary?.photos || preview?.showcase_preview?.photos || inv?.photos || [];
  const coaches: any[] = preview?.showcase_summary?.coaching_team || preview?.showcase_preview?.coaching_team || inv?.coaching_team || [];
  const landmarks: string[] = sc.home_landmarks || inv?.home_landmarks || [];
  const coverUrl = sc.hero_cover_url || inv?.hero_cover_url || photos[0]?.photo_url || inv?.club_logo || "";

  function handleCardClick() {
    if (submitting) return;
    if (preview?.viewer_already_member) {
      if (typeof window !== "undefined" && inv?.club_id) {
        localStorage.setItem("rgm_active_club_id", inv.club_id);
      }
      router.push("/dashboard/team");
      return;
    }
    handleRespond("accept");
  }

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
            {/* Unified Synthesized Club Invitation Card (Click Card to Join & Enter Club Directly) */}
            <div
              role="button"
              tabIndex={0}
              onClick={handleCardClick}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleCardClick();
                }
              }}
              className="group rgm-bento-card overflow-hidden border-2 border-amber-500/50 hover:border-[#FC4C02] bg-[var(--rgm-amber-tint)] transition-all cursor-pointer shadow-xl"
            >
              {/* Top Visual Banner: Hero Cover + Photo Collage Strip */}
              {(coverUrl || photos.length > 0) && (
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-1.5 bg-black/20 p-1.5">
                  <div className={`${photos.length > 1 ? "sm:col-span-7" : "sm:col-span-12"} h-48 sm:h-56 relative rounded-2xl overflow-hidden bg-[var(--rgm-card-2)]`}>
                    <img
                      src={coverUrl || photos[0]?.photo_url}
                      alt={inv.club_name}
                      className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/25 to-transparent" />
                    <div className="absolute top-3 left-3 flex items-center gap-2 flex-wrap">
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FC4C02] text-white text-xs font-black shadow">
                        <Sparkles className="w-3.5 h-3.5" />
                        金色定向兼团特邀卡 · 点击卡片直接进跑团
                      </span>
                      {inv.preassigned_group && (
                        <span className="px-2.5 py-1 rounded-full bg-emerald-500 text-black text-xs font-black shadow">
                          预编入 {inv.preassigned_group}
                        </span>
                      )}
                    </div>
                    <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-2">
                      <div>
                        <div className="text-lg sm:text-2xl font-black text-white drop-shadow">
                          {inv.club_name}
                        </div>
                        <div className="text-xs text-orange-200 font-bold line-clamp-1">
                          {sc.slogan || inv.reason_tag || "科学耐力训练 · 队友同频共进"}
                        </div>
                      </div>
                      <span className="px-2.5 py-1 rounded-full bg-black/70 text-white text-[11px] font-bold shrink-0">
                        📍 {inv.club_city || "上海"}
                      </span>
                    </div>
                  </div>

                  {photos.length > 1 && (
                    <div className="sm:col-span-5 grid grid-cols-2 gap-1.5 h-48 sm:h-56">
                      {photos.slice(0, 4).map((p: any, idx: number) => (
                        <div key={p.id || idx} className="relative rounded-xl overflow-hidden bg-[var(--rgm-card-2)]">
                          <img
                            src={p.photo_url}
                            alt={p.caption || "跑团风采"}
                            className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                          />
                          {p.caption && (
                            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-2 py-1 text-[10px] text-white truncate">
                              {p.caption}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Card Body: Synthesized Club Info, Verified Telemetry, Coaches & Direct Join Action */}
              <div className="p-6 sm:p-7 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1.5">
                    {!coverUrl && photos.length === 0 && (
                      <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FC4C02] text-white text-xs font-black">
                        <Sparkles className="w-3.5 h-3.5" />
                        金色定向兼团特邀卡 · 点击卡片直接进跑团
                      </div>
                    )}
                    <h1 className="text-xl sm:text-2xl font-black text-[var(--rgm-text)] group-hover:text-[#FC4C02] transition">
                      【{inv.club_name}】{inv.inviter_name} 诚邀您加入
                      {inv.preassigned_group ? `（预编入 ${inv.preassigned_group}）` : ""}
                    </h1>
                    <p className="text-xs sm:text-sm text-[var(--rgm-text-2)]">
                      {inv.reason_tag || sc.slogan || "跑力与日常打卡时段高度同频"}
                      {inv.custom_message ? ` — “${inv.custom_message}”` : ""}
                    </p>
                    <div className="flex items-center gap-2 flex-wrap pt-1 text-[11px] text-[var(--rgm-text-2)]">
                      <span>📍 {inv.club_city || "上海"}</span>
                      {landmarks.map((lm: string) => (
                        <span key={lm} className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card)] border border-[var(--rgm-border)] font-bold">
                          {lm}
                        </span>
                      ))}
                      {sc.schedule_summary && (
                        <span className="px-2.5 py-0.5 rounded-lg bg-[var(--rgm-card)] border border-[var(--rgm-border)] font-bold text-[var(--rgm-text)]">
                          🗓️ {sc.schedule_summary}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                    {preview?.viewer_already_member ? (
                      <button
                        type="button"
                        onClick={handleCardClick}
                        className="px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-xs font-black flex items-center gap-1.5 cursor-pointer"
                      >
                        <CheckCircle2 className="w-4 h-4" /> 已是该团成员 · 直接进入跑团 ›
                      </button>
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
                            ? `一键免码进跑团${inv.preassigned_group ? ` (${inv.preassigned_group})` : ""}`
                            : "登录并一键进跑团"}
                          <ArrowRight className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Synthesized 4 Verified Telemetry Tiles inside the Invite Card */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <div className="p-3 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)]">
                    <div className="text-[11px] text-[var(--rgm-text-muted)]">活跃队员</div>
                    <div className="text-sm font-black text-[var(--rgm-text)] mt-0.5 tabular-nums">
                      {st.member_count ?? 1} 人
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)]">
                    <div className="text-[11px] text-[var(--rgm-text-muted)]">本月全团实跑</div>
                    <div className="text-sm font-black text-[#FC4C02] mt-0.5 tabular-nums">
                      {st.month_total_km ?? 0} km
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)]">
                    <div className="text-[11px] text-[var(--rgm-text-muted)]">⌚ 手表核验破330</div>
                    <div className="text-sm font-black text-emerald-500 mt-0.5 tabular-nums">
                      {st.sub330_count ?? 0} 人 (破3 {st.sub300_count ?? 0} 人)
                    </div>
                  </div>
                  <div className="p-3 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)]">
                    <div className="text-[11px] text-[var(--rgm-text-muted)]">🐰 平台认证官兔</div>
                    <div className="text-sm font-black text-amber-500 mt-0.5 tabular-nums">
                      {st.official_pacer_races_count ?? 0} 场次
                    </div>
                  </div>
                </div>

                {/* Core Coaching Roster Strip inside the Invite Card */}
                {coaches.length > 0 && (
                  <div className="flex items-center gap-2 flex-wrap pt-1">
                    <span className="text-xs font-black text-[var(--rgm-text)]">🎖️ 核心团长/教练：</span>
                    {coaches.slice(0, 3).map((ch: any) => (
                      <span
                        key={ch.user_id}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-xs font-bold text-[var(--rgm-text)]"
                      >
                        <span>{ch.display_name}</span>
                        <span className="text-[11px] text-[var(--rgm-text-2)]">· {ch.headline}</span>
                        {ch.verified_marathon_pb && (
                          <span className="text-[11px] text-[#FC4C02] font-black">PB {ch.verified_marathon_pb}</span>
                        )}
                      </span>
                    ))}
                  </div>
                )}

                <div className="p-3 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text-2)] flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
                    <span>{preview?.non_exclusive_notice}</span>
                  </div>
                  <span className="text-xs font-black text-[#FC4C02]">👆 点击本邀请卡任意区域即可直接进跑团 ›</span>
                </div>
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
      <ComplianceFooter />
      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} initialTab="wechat" />
    </div>
  );
}
