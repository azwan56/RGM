"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import apiClient from "@/lib/apiClient";
import { useUiFeedback } from "@/components/ui/UiFeedbackProvider";
import {
  Megaphone,
  CheckCircle2,
  Users,
  Sparkles,
  UserPlus,
  Compass,
  Award,
  X,
  Trophy,
  Send,
  Calendar,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface ClubPulsePanelProps {
  uid: string;
  clubId?: string | null;
  isLeader?: boolean;
  defaultCollapsed?: boolean;
  onClubJoined?: () => void;
}

const CHEER_PILLS = [
  { key: "steady_aerobic", label: "👏 有氧真稳" },
  { key: "high_intensity", label: "🔥 强度拉满" },
  { key: "stretch_recover", label: "🦵 注意排酸拉伸" },
  { key: "weekend_run", label: "🏃 周末约起" },
];

export default function ClubPulsePanel({
  uid,
  clubId,
  isLeader = false,
  defaultCollapsed = true,
  onClubJoined,
}: ClubPulsePanelProps) {
  const { showToast } = useUiFeedback();
  const router = useRouter();
  const pathname = usePathname();
  const [pulseData, setPulseData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [broadcastCollapsed, setBroadcastCollapsed] = useState(false);
  const [pulseCollapsed, setPulseCollapsed] = useState(defaultCollapsed);
  const [selectedClubId, setSelectedClubId] = useState<string>("");

  // Composer modal (Leader/Coach broadcast)
  const [showComposer, setShowComposer] = useState(false);
  const [bCategory, setBCategory] = useState("notice");
  const [bTitle, setBTitle] = useState("");
  const [bContent, setBContent] = useState("");
  const [bAudience, setBAudience] = useState("all");
  const [bSending, setBSending] = useState(false);

  // Weekly PK modal & homepage visibility toggle (default OFF)
  const HOME_BUDDY_PK_STORAGE_KEY = "rgm_home_show_buddy_pk";
  const [showHomeBuddyPk, setShowHomeBuddyPk] = useState(false);
  const [pkData, setPkData] = useState<any>(null);
  const [pkLoading, setPkLoading] = useState(false);

  useEffect(() => {
    const syncPref = () => {
      try {
        const raw = localStorage.getItem(HOME_BUDDY_PK_STORAGE_KEY);
        setShowHomeBuddyPk(raw === "1" || raw === "true");
      } catch {
        setShowHomeBuddyPk(false);
      }
    };
    syncPref();
    window.addEventListener("storage", syncPref);
    window.addEventListener("rgm-home-pk-pref-changed", syncPref);
    return () => {
      window.removeEventListener("storage", syncPref);
      window.removeEventListener("rgm-home-pk-pref-changed", syncPref);
    };
  }, []);

  function toggleHomeBuddyPk(nextVal?: boolean) {
    const flag = typeof nextVal === "boolean" ? nextVal : !showHomeBuddyPk;
    setShowHomeBuddyPk(flag);
    try {
      localStorage.setItem(HOME_BUDDY_PK_STORAGE_KEY, flag ? "1" : "0");
      window.dispatchEvent(new Event("rgm-home-pk-pref-changed"));
    } catch {}
    showToast(flag ? "已开启首页搭子周 PK" : "已关闭首页搭子周 PK（保留寻搭子与选团展厅）", "info");
  }

  const loadPulse = useCallback(async () => {
    if (!uid) return;
    try {
      const q = new URLSearchParams({ viewer_uid: uid, tab: activeTab, limit: "15" });
      if (selectedClubId) {
        q.set("club_id", selectedClubId);
      } else if (clubId) {
        q.set("preferred_club_id", clubId);
      }
      const res = await apiClient.get(`/api/community/home-pulse?${q.toString()}`);
      setPulseData(res.data);
    } catch {
      // Keep quiet on passive refresh
    } finally {
      setLoading(false);
    }
  }, [uid, clubId, selectedClubId, activeTab]);

  function handleEnterClubFeed(cid?: string) {
    const targetCid = String(cid || pulseData?.club_id || clubId || "").trim();
    if (targetCid) {
      if (typeof window !== "undefined") {
        localStorage.setItem("rgm_active_club_id", targetCid);
      }
      router.push(`/dashboard/team?club_id=${encodeURIComponent(targetCid)}&tab=leaderboard`);
    } else {
      router.push("/dashboard/team");
    }
  }

  function handleSwitchClub(cid: string) {
    if (!cid || cid === pulseData?.club_id) return;
    setSelectedClubId(cid);
    if (typeof window !== "undefined") {
      localStorage.setItem("rgm_active_club_id", cid);
    }
  }

  useEffect(() => {
    loadPulse();
  }, [loadPulse]);

  async function handleAckBroadcast(broadcastId: string) {
    try {
      await apiClient.post(`/api/community/broadcasts/${broadcastId}/ack`, { user_id: uid });
      showToast("已确认收到置顶广播 ✓");
      loadPulse();
    } catch (e: any) {
      showToast("确认失败：" + (e?.message || "网络异常"), "error");
    }
  }

  async function handlePublishBroadcast(e: React.FormEvent) {
    e.preventDefault();
    const targetCid = clubId || pulseData?.club_id;
    if (!targetCid) {
      showToast("请先选择要发布的跑团", "error");
      return;
    }
    if (!bTitle.trim() || !bContent.trim()) {
      showToast("请填写广播标题和正文", "error");
      return;
    }
    setBSending(true);
    try {
      await apiClient.post(`/api/community/clubs/${targetCid}/broadcasts`, {
        author_id: uid,
        category: bCategory,
        title: bTitle.trim(),
        content: bContent.trim(),
        target_audience: bAudience,
        pin_hours: 72,
      });
      showToast("📢 跑团置顶广播已发出，并已通知对应成员");
      setShowComposer(false);
      setBTitle("");
      setBContent("");
      loadPulse();
    } catch (err: any) {
      showToast("发布失败：" + (err?.message || "无权限"), "error");
    } finally {
      setBSending(false);
    }
  }

  async function handleMicroCheer(
    targetType: string,
    targetId: string,
    recipientId: string,
    cheerKey: string
  ) {
    try {
      await apiClient.post("/api/community/micro-cheer", {
        sender_id: uid,
        target_type: targetType,
        target_id: targetId,
        recipient_id: recipientId,
        cheer_key: cheerKey,
        club_id: clubId || pulseData?.club_id || "",
      });
      loadPulse();
    } catch (e: any) {
      showToast("互动失败：" + (e?.message || ""), "error");
    }
  }

  async function handleQuickFollow(targetUid: string, currentlyFollowing: boolean) {
    try {
      if (currentlyFollowing) {
        await apiClient.delete(`/api/community/follow/${encodeURIComponent(targetUid)}?follower_id=${encodeURIComponent(uid)}`);
        showToast("已取消关注");
      } else {
        const res = await apiClient.post("/api/community/follow", {
          follower_id: uid,
          target_uid: targetUid,
        });
        showToast(res.data?.is_mutual_buddy ? "⇄ 已互相关注成为跑搭子！" : "🤝 已关注，回关即可解锁周PK");
      }
      loadPulse();
    } catch (e: any) {
      showToast("操作失败：" + (e?.message || ""), "error");
    }
  }

  async function handleOpenPk(targetUid: string) {
    setPkLoading(true);
    setPkData({ loading: true });
    try {
      const res = await apiClient.get(
        `/api/community/buddies/${encodeURIComponent(targetUid)}/pk?viewer_uid=${encodeURIComponent(uid)}`
      );
      setPkData(res.data);
    } catch (e: any) {
      showToast("打开周PK失败：" + (e?.message || ""), "error");
      setPkData(null);
    } finally {
      setPkLoading(false);
    }
  }

  async function handleAcceptInvite(token: string, invitedClubId?: string) {
    try {
      const res = await apiClient.post(`/api/community/invites/${token}/respond`, {
        user_id: uid,
        action: "accept",
      });
      const targetClubId = res.data?.club_id || invitedClubId || "";
      if (typeof window !== "undefined" && targetClubId) {
        localStorage.setItem("rgm_active_club_id", targetClubId);
      }
      showToast(
        `🎉 已免码兼入【${res.data?.club_name || "新跑团"}】${
          res.data?.preassigned_group ? ` (${res.data.preassigned_group})` : ""
        }，正在进入跑团...`
      );
      onClubJoined?.();
      loadPulse();
      if (pathname !== "/dashboard/team") {
        router.push("/dashboard/team");
      }
    } catch (e: any) {
      showToast("接受邀请失败：" + (e?.message || ""), "error");
    }
  }

  const pinned = pulseData?.pinned_broadcast;
  const pendingInvites: any[] = pulseData?.pending_targeted_invites || [];
  const buddyRings: any[] = pulseData?.buddy_live_rings || [];
  const pkSummary = pulseData?.weekly_pk_summary;
  const pulseItems: any[] = pulseData?.pulse_items || [];
  const topActiveClubs: any[] = [...(pulseData?.clubs || [])]
    .sort((a: any, b: any) => {
      const sa = Number(a?.today_checkin_count || 0) * 10 + Number(a?.recent_7d_runs || 0);
      const sb = Number(b?.today_checkin_count || 0) * 10 + Number(b?.recent_7d_runs || 0);
      if (sb !== sa) return sb - sa;
      const td = Number(b?.today_checkin_count || 0) - Number(a?.today_checkin_count || 0);
      if (td !== 0) return td;
      const r7 = Number(b?.recent_7d_runs || 0) - Number(a?.recent_7d_runs || 0);
      if (r7 !== 0) return r7;
      return Number(b?.member_count || 0) - Number(a?.member_count || 0);
    })
    .slice(0, 3);

  function isDefaultClubLogo(url?: string): boolean {
    const s = String(url || "").trim().toLowerCase();
    return !s || s.includes("rgm-logo.png") || s.includes("logo-square.png");
  }

  return (
    <div className="space-y-4">
      {/* 1) Synthesized Clickable Club Invitation Card (One-Click Join & Enter Club) */}
      {pendingInvites.length > 0 && (() => {
        const inv = pendingInvites[0];
        const summary = inv.showcase_summary || inv;
        const stats = summary.verified_stats || {};
        const photos: any[] = summary.photos || [];
        const landmarks: string[] = summary.home_landmarks || [];
        const coaches: any[] = summary.coaching_team || [];
        const coverUrl = summary.hero_cover_url || photos[0]?.photo_url || inv.club_logo || "";

        return (
          <div
            role="button"
            tabIndex={0}
            onClick={() => handleAcceptInvite(inv.invite_token, inv.club_id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleAcceptInvite(inv.invite_token, inv.club_id);
              }
            }}
            className="group rounded-2xl border-2 border-amber-500/50 bg-[var(--rgm-amber-tint)] hover:border-[#FC4C02] transition-all overflow-hidden cursor-pointer shadow-lg"
          >
            <div className="p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              {/* Left: Club Cover/Logo + Main Info + Photos Strip */}
              <div className="flex flex-col sm:flex-row items-start gap-3.5 min-w-0 flex-1">
                {coverUrl ? (
                  <div className="w-full sm:w-28 h-24 rounded-xl overflow-hidden bg-[var(--rgm-card)] border border-amber-500/30 shrink-0 relative">
                    <img src={coverUrl} alt={inv.club_name} className="w-full h-full object-cover group-hover:scale-105 transition" />
                    <span className="absolute bottom-1 left-1 px-1.5 py-0.5 rounded bg-black/70 text-white text-[10px] font-bold">
                      📍 {inv.club_city || "同城"}
                    </span>
                  </div>
                ) : (
                  <div className="w-12 h-12 rounded-xl bg-[#FC4C02]/15 border border-[#FC4C02]/40 flex items-center justify-center shrink-0">
                    <Sparkles className="w-6 h-6 text-[#FC4C02]" />
                  </div>
                )}

                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2 py-0.5 rounded-full bg-[#FC4C02] text-white text-[10px] font-black">
                      ✨ 跑团特邀卡 · 点击卡片直接入团
                    </span>
                    {inv.preassigned_group && (
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-500 border border-emerald-500/30 text-[10px] font-black">
                        预编入 {inv.preassigned_group}
                      </span>
                    )}
                  </div>

                  <div className="text-sm sm:text-base font-black text-[var(--rgm-text)] group-hover:text-[#FC4C02] transition">
                    【{inv.club_name}】{inv.inviter_name} 诚邀您加入
                  </div>

                  <div className="text-xs text-[var(--rgm-text-2)] line-clamp-1">
                    {summary.slogan || inv.reason_tag || "跑团之间无排他性，支持多团并行共享手表跑量"}
                  </div>

                  {/* Synthesized Club Core Metrics & Landmarks */}
                  <div className="flex items-center gap-1.5 flex-wrap pt-0.5 text-[11px]">
                    <span className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card)] border border-[var(--rgm-border)] font-bold text-[var(--rgm-text)]">
                      👥 {stats.member_count ?? 1} 位队员
                    </span>
                    {(stats.month_total_km ?? 0) > 0 && (
                      <span className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card)] border border-[var(--rgm-border)] font-bold text-[var(--rgm-text)]">
                        🏃 本月 {stats.month_total_km} km
                      </span>
                    )}
                    {(stats.sub330_count ?? 0) > 0 && (
                      <span className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card)] border border-[var(--rgm-border)] font-bold text-emerald-500">
                        ⌚ 破330 {stats.sub330_count} 人
                      </span>
                    )}
                    {landmarks.slice(0, 2).map((lm: string) => (
                      <span key={lm} className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-[var(--rgm-text-2)]">
                        📍 {lm}
                      </span>
                    ))}
                    {summary.schedule_summary && (
                      <span className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-[var(--rgm-text-2)] truncate max-w-[200px]">
                        🗓️ {summary.schedule_summary}
                      </span>
                    )}
                    {coaches.length > 0 && (
                      <span className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-amber-500 font-bold">
                        🎖️ 教练 {coaches[0].display_name}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Right: Photo Thumbnails + Direct Join CTA */}
              <div className="flex items-center justify-between lg:justify-end gap-3 shrink-0">
                {photos.length > 1 && (
                  <div className="hidden sm:flex items-center -space-x-2">
                    {photos.slice(0, 3).map((p: any, idx: number) => (
                      <img
                        key={p.id || idx}
                        src={p.photo_url}
                        alt={p.caption || "跑团实拍"}
                        className="w-11 h-11 rounded-xl object-cover border-2 border-[var(--rgm-card)] shadow"
                      />
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <Link
                    href={`/join/${inv.invite_token}`}
                    onClick={(e) => e.stopPropagation()}
                    className="px-3 py-2 rounded-xl border border-amber-500/40 bg-[var(--rgm-card)] text-xs font-bold text-[var(--rgm-text)] hover:opacity-80"
                  >
                    详情展厅
                  </Link>
                  <span className="px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-black group-hover:opacity-90 shadow-md">
                    点击直接进跑团 ›
                  </span>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* 2) Club Pinned Broadcast Top Strip */}
      {(pinned || isLeader) && (
        <div className="rgm-bento-card px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {pinned ? (
            <div className="flex items-start gap-2.5 min-w-0 flex-1">
              <div className="p-2 rounded-xl bg-[var(--rgm-brand-tint)] text-[#FC4C02] shrink-0">
                <Megaphone className="w-4 h-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-[#FC4C02] text-white">
                    置顶广播
                  </span>
                  <span className="text-xs font-black text-[var(--rgm-text)] truncate">{pinned.title}</span>
                  <span className="text-[11px] text-[var(--rgm-text-muted)]">
                    · {pinned.author_name} · 已收到 {pinned.ack_count}/{pinned.member_count}
                  </span>
                </div>
                {!broadcastCollapsed && (
                  <p className="text-xs text-[var(--rgm-text-2)] mt-1 leading-relaxed">{pinned.content}</p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-xs text-[var(--rgm-text-2)]">
              <Megaphone className="w-4 h-4 text-[#FC4C02]" />
              <span>当前暂无置顶广播，团长/教练可发布 72 小时全团/分组置顶通知</span>
            </div>
          )}

          <div className="flex items-center gap-2 shrink-0">
            {pinned && (
              <>
                <button
                  type="button"
                  onClick={() => setBroadcastCollapsed(!broadcastCollapsed)}
                  className="px-2.5 py-1 rounded-lg text-[11px] font-semibold text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] border border-[var(--rgm-border)] cursor-pointer"
                >
                  {broadcastCollapsed ? "展开" : "收起"}
                </button>
                <button
                  type="button"
                  onClick={() => handleAckBroadcast(pinned.id)}
                  disabled={pinned.viewer_acked}
                  className={`px-3 py-1 rounded-xl text-xs font-bold flex items-center gap-1 cursor-pointer ${
                    pinned.viewer_acked
                      ? "bg-[var(--rgm-green-tint)] text-emerald-500 border border-emerald-500/30"
                      : "bg-[#FC4C02] text-white"
                  }`}
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  {pinned.viewer_acked ? "已收到" : "收到 ✓"}
                </button>
              </>
            )}
            {isLeader && (
              <button
                type="button"
                onClick={() => setShowComposer(true)}
                className="px-3 py-1 rounded-xl border border-[var(--rgm-border)] bg-[var(--rgm-card-2)] text-xs font-bold text-[var(--rgm-text)] hover:border-[#FC4C02]/50 cursor-pointer"
              >
                + 发广播
              </button>
            )}
          </div>
        </div>
      )}

      {/* 3) Minimalist Top-3 Active Clubs Avatar Strip & Collapsible Pulse (default collapsed) */}
      <div className={`rgm-bento-card transition-all ${pulseCollapsed ? "px-5 py-3.5" : "p-5 space-y-4"}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          {pulseData?.has_club && topActiveClubs.length > 0 ? (
            <div className="flex items-center gap-4 flex-wrap min-w-0 flex-1">
              <button
                type="button"
                onClick={() => setPulseCollapsed((prev) => !prev)}
                className="text-xs font-extrabold text-[var(--rgm-text-2)] hover:text-[#FC4C02] transition cursor-pointer shrink-0"
              >
                活跃跑团
              </button>
              <div className="flex items-center gap-4 sm:gap-5 flex-wrap">
                {topActiveClubs.map((c: any) => {
                  const todayCnt = Number(c?.today_checkin_count || 0);
                  const isDefault = isDefaultClubLogo(c?.logo_url);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => handleEnterClubFeed(c.id)}
                      title={`${c.name} · 今日 ${todayCnt} 人打卡`}
                      className="flex flex-col items-center gap-1 group cursor-pointer shrink-0"
                    >
                      <div
                        className={`relative w-11 h-11 rounded-xl p-0.5 bg-[var(--rgm-card-2)] border-2 transition group-hover:border-[#FC4C02] ${
                          todayCnt > 0 ? "border-[#FC4C02]" : "border-[var(--rgm-border)]"
                        }`}
                      >
                        <img
                          src={c.logo_url || "/icon.png"}
                          alt={c.name}
                          className="w-full h-full rounded-[10px] object-cover"
                        />
                        {todayCnt > 0 && (
                          <span className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 rounded-full bg-[#FC4C02] text-white text-[10px] font-black leading-[18px] text-center border-2 border-[var(--rgm-card)] tabular-nums">
                            {todayCnt}
                          </span>
                        )}
                        {isDefault && (
                          <span className="absolute inset-x-0.5 bottom-0.5 px-1 py-[1px] rounded-b-[9px] bg-black/70 text-[8px] font-bold text-white truncate text-center">
                            {c.name}
                          </span>
                        )}
                      </div>
                      <span
                        className={`text-[10px] tabular-nums whitespace-nowrap ${
                          todayCnt > 0 ? "font-extrabold text-emerald-500" : "font-semibold text-[var(--rgm-text-3)]"
                        }`}
                      >
                        今日 {todayCnt} 人打卡
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setPulseCollapsed((prev) => !prev)}
              className="flex items-center gap-2.5 text-left min-w-0 flex-1 cursor-pointer group"
            >
              <span className="text-base shrink-0">🏆</span>
              <div className="min-w-0">
                <h3 className="text-sm font-black text-[var(--rgm-text)] group-hover:text-[#FC4C02] transition truncate">
                  活跃跑团与同频搭子
                </h3>
                <p className="text-[11px] text-[var(--rgm-text-2)] truncate">
                  {(showHomeBuddyPk && pkSummary?.summary_text) || "加入跑团后展示最活跃跑团头像与今日打卡"}
                </p>
              </div>
            </button>
          )}

          <div className="flex items-center gap-2 flex-wrap shrink-0">
            <Link
              href="/dashboard/discover"
              className="px-3 py-1.5 rounded-xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/30 text-xs font-bold text-[#FC4C02] flex items-center gap-1 hover:opacity-90 whitespace-nowrap"
            >
              <Compass className="w-3.5 h-3.5" />
              寻搭子
            </Link>
            <Link
              href="/dashboard/plaza"
              className="px-3 py-1.5 rounded-xl border border-[var(--rgm-border)] bg-[var(--rgm-card-2)] text-xs font-bold text-[var(--rgm-text)] flex items-center gap-1 hover:border-[#FC4C02]/40 whitespace-nowrap"
            >
              <Award className="w-3.5 h-3.5 text-amber-500" />
              选团展厅
            </Link>
            <button
              type="button"
              onClick={() => setPulseCollapsed((prev) => !prev)}
              aria-expanded={!pulseCollapsed}
              className="px-3 py-1.5 rounded-xl border border-[var(--rgm-border)] bg-[var(--rgm-card-2)] text-xs font-bold text-[var(--rgm-text)] flex items-center gap-1 hover:border-[#FC4C02]/45 cursor-pointer whitespace-nowrap"
            >
              {pulseCollapsed ? (
                <>
                  <span>展开</span>
                  <ChevronDown className="w-3.5 h-3.5 text-[var(--rgm-text-2)]" />
                </>
              ) : (
                <>
                  <span>收起</span>
                  <ChevronUp className="w-3.5 h-3.5 text-[var(--rgm-text-2)]" />
                </>
              )}
            </button>
          </div>
        </div>

        {!pulseCollapsed && (
          <>
            {/* Multi-Club Quick Switcher (sorted by most frequently followed) */}
            {(pulseData?.clubs || []).length > 1 && (
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                <span className="text-[11px] font-bold text-[var(--rgm-text-muted)] shrink-0">常看跑团：</span>
                {(pulseData.clubs || []).map((c: any) => {
                  const isAct = c.id === pulseData?.club_id;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => handleSwitchClub(c.id)}
                      className={`px-3 py-1 rounded-full text-xs font-bold shrink-0 transition cursor-pointer flex items-center gap-1.5 ${
                        isAct
                          ? "bg-[#FC4C02] text-white"
                          : "bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
                      }`}
                    >
                      <span>{c.name}</span>
                      {c.today_checkin_count > 0 && (
                        <span className={`text-[10px] px-1.5 rounded-full ${isAct ? "bg-white/20 text-white" : "bg-[var(--rgm-green-tint)] text-emerald-500"}`}>
                          {c.today_checkin_count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Buddy Live Rings Row (Weekly PK — default OFF, toggleable) */}
        {showHomeBuddyPk && buddyRings.length > 0 && (
          <div className="flex items-center gap-3 overflow-x-auto pb-1">
            {buddyRings.map((b: any) => {
              const ringCls = b.ran_today
                ? "ring-2 ring-emerald-500"
                : b.is_newcomer_14d
                ? "ring-2 ring-amber-500"
                : b.joined_upcoming_run
                ? "ring-2 ring-sky-500"
                : "ring-1 ring-[var(--rgm-border)]";
              return (
                <button
                  key={b.user_id}
                  type="button"
                  onClick={() => handleOpenPk(b.user_id)}
                  className="flex flex-col items-center gap-1 min-w-[64px] shrink-0 group cursor-pointer"
                >
                  <div className={`w-11 h-11 rounded-full p-0.5 ${ringCls} bg-[var(--rgm-card-2)] overflow-hidden`}>
                    {b.avatar_url ? (
                      <img src={b.avatar_url} alt={b.display_name} className="w-full h-full rounded-full object-cover" />
                    ) : (
                      <div className="w-full h-full rounded-full flex items-center justify-center text-xs font-black text-[var(--rgm-text)]">
                        {String(b.display_name || "跑").slice(0, 1)}
                      </div>
                    )}
                  </div>
                  <span className="text-[11px] font-bold text-[var(--rgm-text)] truncate max-w-[62px] group-hover:text-[#FC4C02]">
                    {b.display_name}
                  </span>
                  <span className="text-[10px] tabular-nums text-[var(--rgm-text-muted)]">
                    {b.ran_today ? `今日 ${b.today_km}k` : `周 ${b.week_km}k`}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* 4-in-1 Pulse Tabs + Buddy PK Toggle */}
        <div className="flex items-center justify-between gap-2 pb-1 border-b border-[var(--rgm-divider)]">
          <div className="flex items-center gap-1.5 overflow-x-auto">
          {[
            { key: "all", label: "🔥 全部脉搏" },
            { key: "broadcasts", label: "📢 广播/活动" },
            { key: "newcomers", label: "👋 新人破冰" },
            { key: "buddies", label: "🤝 关注搭子" },
          ].map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              className={`px-3 py-1.5 rounded-t-xl text-xs font-bold shrink-0 transition cursor-pointer ${
                activeTab === t.key
                  ? "bg-[#FC4C02] text-white"
                  : "text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
              }`}
            >
              {t.label}
            </button>
          ))}
          </div>
          <button
            type="button"
            onClick={() => toggleHomeBuddyPk()}
            className={`px-2.5 py-1 rounded-full text-[11px] font-bold shrink-0 transition cursor-pointer border flex items-center gap-1 ${
              showHomeBuddyPk
                ? "bg-[var(--rgm-brand-tint)] border-[#FC4C02]/40 text-[#FC4C02]"
                : "bg-[var(--rgm-card-2)] border-[var(--rgm-border)] text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
            }`}
            title="开启或关闭首页搭子周 PK 展示（默认关闭）"
          >
            <Trophy className="w-3 h-3" />
            <span>搭子PK：{showHomeBuddyPk ? "开" : "关"}</span>
          </button>
        </div>

        {/* Pulse Feed Items */}
        {loading ? (
          <div className="py-6 text-center text-xs text-[var(--rgm-text-muted)]">加载社交脉搏中...</div>
        ) : pulseItems.length === 0 ? (
          <div className="py-6 text-center space-y-2">
            <Users className="w-7 h-7 text-[var(--rgm-text-muted)] mx-auto" />
            <div className="text-xs text-[var(--rgm-text-2)]">暂无更多动态，去发掘同频跑友或探索精选跑团吧</div>
          </div>
        ) : (
          <div className="space-y-3">
            {pulseItems.slice(0, 6).map((item: any) => {
              if (item.kind === "newcomer_icebreaker") {
                const patCount = item.micro_cheers?.counts_by_key?.welcome_pat || 0;
                const patted = (item.micro_cheers?.viewer_cheered_keys || []).includes("welcome_pat");
                return (
                  <div
                    key={item.item_id}
                    className="p-3.5 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] space-y-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-[var(--rgm-amber-tint)] text-amber-500 shrink-0">
                          👋 新人破冰
                        </span>
                        <span className="text-xs font-black text-[var(--rgm-text)] truncate">{item.display_name}</span>
                        <span className="text-[11px] text-[var(--rgm-text-muted)] shrink-0">
                          {item.age_group} · {item.vdot_band}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleQuickFollow(item.user_id, Boolean(item.is_following))}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-bold shrink-0 cursor-pointer ${
                          item.is_following
                            ? "bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-[var(--rgm-text-2)]"
                            : "bg-[var(--rgm-brand-tint)] text-[#FC4C02]"
                        }`}
                      >
                        {item.is_following ? "已关注" : "+ 关注结伴"}
                      </button>
                    </div>
                    <div className="text-[11px] text-[var(--rgm-text-2)] flex items-center justify-between gap-2 flex-wrap">
                      <span>
                        📍 {item.city || "同城"}{" "}
                        {(item.running_landmarks || []).length > 0 ? `· 常跑 ${(item.running_landmarks || []).join("/")}` : ""}
                        {item.training_group ? ` · 编入 ${item.training_group}` : ""}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleMicroCheer("newcomer", item.item_id, item.user_id, "welcome_pat")}
                        className={`px-2.5 py-1 rounded-full text-[11px] font-bold transition cursor-pointer ${
                          patted
                            ? "bg-[#FC4C02] text-white"
                            : "bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-[var(--rgm-text)]"
                        }`}
                      >
                        👋 拍肩欢迎 {patCount > 0 ? patCount : ""}
                      </button>
                    </div>
                  </div>
                );
              }

              if (item.kind === "broadcast_event" && item.event) {
                return (
                  <div
                    key={item.item_id}
                    className="p-3.5 rounded-2xl bg-[var(--rgm-blue-tint)] border border-sky-500/25 flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-xs font-black text-[var(--rgm-text)]">
                        <Calendar className="w-3.5 h-3.5 text-sky-500 shrink-0" />
                        <span className="truncate">{item.event.title}</span>
                      </div>
                      <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5">
                        {item.event.meet_time || "周末晨跑"} · {item.event.location || "跑团据点"} · 已报 {item.event.participant_count} 人
                      </div>
                    </div>
                    <Link
                      href="/dashboard/team?tab=events"
                      className="px-3 py-1 rounded-xl bg-sky-500 text-white text-[11px] font-bold shrink-0"
                    >
                      约跑详情 ›
                    </Link>
                  </div>
                );
              }

              if (item.kind === "activity_checkin" && item.activity) {
                const a = item.activity;
                const cheers = item.micro_cheers || { counts_by_key: {}, viewer_cheered_keys: [] };
                return (
                  <div
                    key={item.item_id}
                    onClick={() => handleEnterClubFeed(a.club_id || pulseData?.club_id)}
                    className="p-3.5 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-[#FC4C02]/45 transition cursor-pointer space-y-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {a.avatar_url ? (
                          <img src={a.avatar_url} alt={a.display_name} className="w-6 h-6 rounded-full object-cover shrink-0" />
                        ) : (
                          <div className="w-6 h-6 rounded-full bg-[var(--rgm-card)] border border-[var(--rgm-border)] flex items-center justify-center text-[10px] font-black text-[var(--rgm-text)] shrink-0">
                            {String(a.display_name || "跑").slice(0, 1)}
                          </div>
                        )}
                        <span className="text-xs font-black text-[var(--rgm-text)] truncate">{a.display_name}</span>
                        {a.has_coach_critique && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--rgm-green-tint)] text-emerald-500 text-[10px] font-bold shrink-0">
                            已点评
                          </span>
                        )}
                        <span className="text-[11px] text-[var(--rgm-text-2)] truncate">{a.name}</span>
                      </div>
                      <div className="text-xs font-black tabular-nums text-[#FC4C02] shrink-0">
                        {a.distance_km} km · {a.avg_pace_str || "--"}
                      </div>
                    </div>
                    {a.ai_journal && !a.is_critique_hidden && (
                      <p className="text-[11px] text-[var(--rgm-text-2)] line-clamp-2">{a.ai_journal}</p>
                    )}
                    <div className="flex items-center justify-between gap-2 flex-wrap pt-0.5">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {CHEER_PILLS.map((cp) => {
                          const cnt = cheers.counts_by_key?.[cp.key] || 0;
                          const active = (cheers.viewer_cheered_keys || []).includes(cp.key);
                          return (
                            <button
                              key={cp.key}
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleMicroCheer("activity", a.id, a.user_id, cp.key);
                              }}
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold transition cursor-pointer ${
                                active
                                  ? "bg-[#FC4C02] text-white"
                                  : "bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
                              }`}
                            >
                              {cp.label} {cnt > 0 ? cnt : ""}
                            </button>
                          );
                        })}
                      </div>
                      <span className="text-[10px] font-bold text-[#FC4C02]">进团浏览详情 ›</span>
                    </div>
                  </div>
                );
              }
              return null;
            })}
          </div>
        )}
          </>
        )}
      </div>

      {/* Leader Broadcast Composer Modal */}
      {showComposer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <form
            onSubmit={handlePublishBroadcast}
            className="rgm-bento-card max-w-lg w-full p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-base font-black text-[var(--rgm-text)] flex items-center gap-2">
                <Megaphone className="w-4 h-4 text-[#FC4C02]" />
                发布跑团 72h 置顶广播
              </h3>
              <button
                type="button"
                onClick={() => setShowComposer(false)}
                className="p-1 text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">广播类别</label>
                <select
                  value={bCategory}
                  onChange={(e) => setBCategory(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                >
                  <option value="notice">全团公告</option>
                  <option value="group_run">合练召集</option>
                  <option value="pb_news">PB 喜报</option>
                  <option value="welcome">迎新须知</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">触达人群</label>
                <select
                  value={bAudience}
                  onChange={(e) => setBAudience(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                >
                  <option value="all">全部团员</option>
                  <option value="group_a">A组（破330/竞速）</option>
                  <option value="group_b">B组（进阶有氧）</option>
                  <option value="group_c">C组（健康跑/新手）</option>
                  <option value="newcomers_14d">近14天新人</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">广播标题</label>
              <input
                type="text"
                value={bTitle}
                onChange={(e) => setBTitle(e.target.value)}
                placeholder="例如：本周六 06:00 世纪公园 24km 梯队合练集结"
                className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                maxLength={80}
              />
            </div>

            <div>
              <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">正文说明</label>
              <textarea
                rows={4}
                value={bContent}
                onChange={(e) => setBContent(e.target.value)}
                placeholder="写清集合点、官兔配速带队分工或赛前注意事项..."
                className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                maxLength={600}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowComposer(false)}
                className="px-4 py-2 rounded-xl border border-[var(--rgm-border)] text-xs font-bold text-[var(--rgm-text-2)] cursor-pointer"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={bSending}
                className="px-5 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-black flex items-center gap-1.5 cursor-pointer disabled:opacity-60"
              >
                <Send className="w-3.5 h-3.5" />
                {bSending ? "发送中..." : "发布并置顶"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Mutual Buddy Weekly PK Modal */}
      {pkData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="rgm-bento-card max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-black text-[var(--rgm-text)] flex items-center gap-2">
                <Trophy className="w-4 h-4 text-amber-500" />
                跑搭子本周跑量友好 PK
              </h3>
              <button
                type="button"
                onClick={() => setPkData(null)}
                className="p-1 text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {pkLoading || pkData.loading ? (
              <div className="py-8 text-center text-xs text-[var(--rgm-text-muted)]">统计本周同频数据中...</div>
            ) : (
              <div className="space-y-4">
                <div className="text-[11px] text-[var(--rgm-text-muted)] text-center">
                  周期：{pkData.week_range}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3.5 rounded-2xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/30 text-center">
                    <div className="text-xs font-bold text-[var(--rgm-text)]">{pkData.viewer?.display_name || "我"}</div>
                    <div className="text-2xl font-black tabular-nums text-[#FC4C02] mt-1">
                      {pkData.viewer?.week_km ?? 0} <span className="text-xs font-bold">km</span>
                    </div>
                    <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5">
                      本周 {pkData.viewer?.week_runs ?? 0} 跑 · 月 {pkData.viewer?.month_km ?? 0} km
                    </div>
                  </div>
                  <div className="p-3.5 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-center">
                    <div className="text-xs font-bold text-[var(--rgm-text)]">{pkData.buddy?.display_name}</div>
                    <div className="text-2xl font-black tabular-nums text-[var(--rgm-text)] mt-1">
                      {pkData.buddy?.week_km ?? 0} <span className="text-xs font-bold">km</span>
                    </div>
                    <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5">
                      本周 {pkData.buddy?.week_runs ?? 0} 跑 · {pkData.buddy?.age_group}
                    </div>
                  </div>
                </div>
                {(pkData.buddy?.running_landmarks || []).length > 0 && (
                  <div className="text-xs text-[var(--rgm-text-2)]">
                    📍 对方常跑地标：{(pkData.buddy.running_landmarks || []).join(" · ")}
                  </div>
                )}
                <div className="flex justify-end gap-2">
                  <Link
                    href="/dashboard/team?tab=events"
                    onClick={() => setPkData(null)}
                    className="px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-black flex items-center gap-1"
                  >
                    <UserPlus className="w-3.5 h-3.5" />
                    去约一次周末合练 ›
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
