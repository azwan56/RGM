"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import RouteMapPreview from "@/components/RouteMapPreview";
import CoachPlanReviewModal from "@/components/CoachPlanReviewModal";
import CoachScheduleImportModal from "@/components/CoachScheduleImportModal";
import PersonalReportModal from "@/components/PersonalReportModal";
import PacerClubRadarPanel from "@/components/PacerClubRadarPanel";
import { supabase } from "@/lib/supabase";
import apiClient, { formatBeijingTime } from "@/lib/apiClient";
import {
  Users,
  Trophy,
  Plus,
  UserPlus,
  Shield,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Flame,
  Activity,
  Heart,
  Moon,
  AlertTriangle,
  Calendar,
  Award,
  Crown,
  Edit2,
  Trash2,
  MessageCircle,
  Send,
  Bot,
  FileText,
  X,
  Target,
  TrendingUp,
  UserMinus,
  ArrowRightLeft,
  Eye,
  EyeOff,
  Lock,
  Loader2,
  Clock,
  Download,
  BarChart3,
  Image as ImageIcon,
  Pause,
  Play,
  ClipboardCheck
} from "lucide-react";

const ORG_PROGRAM_OPTIONS = ["中文EMBA", "台大班", "复旦-BI（挪威）", "奥林班", "港大班"];
const GOBI_EDITIONS = Array.from({ length: 21 }, (_, i) => `戈${21 - i}`);
const GOBI_GROUPS = ["A组", "B组", "C组"];

export default function TeamView({ coachWorkbenchMode = false }: { coachWorkbenchMode?: boolean }) {
  const [user, setUser] = useState<any>(null);
  const [userProfile, setUserProfile] = useState<any>(null);
  const [clubs, setClubs] = useState<any[]>([]);
  const [currentClub, setCurrentClub] = useState<any>(null);
  const [currentRole, setCurrentRole] = useState<string>("member");
  const [clubSuspended, setClubSuspended] = useState(false);
  const [clubSuspensionReason, setClubSuspensionReason] = useState("");

  // Tab: 'leaderboard', 'president', 'coach', 'events'
  const [activeTab, setActiveTab] = useState<"leaderboard" | "president" | "coach" | "events">(
    coachWorkbenchMode ? "coach" : "leaderboard"
  );

  // Data states
  const [loading, setLoading] = useState(true);
  const [dashboardMetrics, setDashboardMetrics] = useState<any>(null);
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [members, setMembers] = useState<any[]>([]);
  const [coachCockpit, setCoachCockpit] = useState<any>(null);
  const [coachSortOrder, setCoachSortOrder] = useState<"danger_first" | "peak_first">("danger_first");
  const [coachStatusFilter, setCoachStatusFilter] = useState<string>("all");
  const [coachPlanFilter, setCoachPlanFilter] = useState<"all" | "draft_pending" | "published" | "none" | "alert">("all");
  const [coachGroupFilter, setCoachGroupFilter] = useState<string>("all");
  const [coachSearchQuery, setCoachSearchQuery] = useState<string>("");
  const [selectedStudentForPlan, setSelectedStudentForPlan] = useState<any | null>(null);
  const [batchGeneratingDrafts, setBatchGeneratingDrafts] = useState<boolean>(false);

  const sortedCoachStudents = useMemo(() => {
    let list = [...(coachCockpit?.students || [])];
    if (coachStatusFilter !== "all") {
      list = list.filter((s: any) => s.status_level === coachStatusFilter);
    }
    if (coachGroupFilter !== "all") {
      list = list.filter(
        (s: any) =>
          s.plan_info?.template_group_code === coachGroupFilter ||
          s.recommended_group?.group_code === coachGroupFilter
      );
    }
    if (coachPlanFilter !== "all") {
      list = list.filter((s: any) => {
        const pState = s.plan_info?.plan_state || "none";
        const wExec = s.plan_info?.week_execution || {};
        if (coachPlanFilter === "draft_pending") return pState === "draft_pending" || s.plan_info?.has_draft_plan;
        if (coachPlanFilter === "published") return pState === "published" || pState === "self_active" || s.plan_info?.has_active_plan;
        if (coachPlanFilter === "none") return pState === "none";
        if (coachPlanFilter === "alert") return Boolean(wExec.injury_note) || (wExec.low_hrv_days || 0) > 0 || (wExec.max_rpe || 0) >= 8;
        return true;
      });
    }
    if (coachSearchQuery.trim()) {
      const q = coachSearchQuery.trim().toLowerCase();
      list = list.filter(
        (s: any) =>
          (s.display_name || "").toLowerCase().includes(q) ||
          (s.user_id || "").toLowerCase().includes(q)
      );
    }

    const dangerFirstRanks: Record<string, number> = { danger: 1, tired: 2, optimal: 3, peak: 4, none: 5 };
    const peakFirstRanks: Record<string, number> = { peak: 1, optimal: 2, tired: 3, danger: 4, none: 5 };

    list.sort((a: any, b: any) => {
      if (coachSortOrder === "danger_first") {
        const aInj = a.plan_info?.week_execution?.injury_note ? 1 : 0;
        const bInj = b.plan_info?.week_execution?.injury_note ? 1 : 0;
        if (aInj !== bInj) return bInj - aInj;
        const aDraft = a.plan_info?.plan_state === "draft_pending" ? 1 : 0;
        const bDraft = b.plan_info?.plan_state === "draft_pending" ? 1 : 0;
        if (aDraft !== bDraft) return bDraft - aDraft;
      }
      const rankMap = coachSortOrder === "peak_first" ? peakFirstRanks : dangerFirstRanks;
      const rankA = rankMap[a.status_level] ?? 99;
      const rankB = rankMap[b.status_level] ?? 99;
      if (rankA !== rankB) {
        return rankA - rankB;
      }
      const tsbA = typeof a.tsb === "number" ? a.tsb : 0;
      const tsbB = typeof b.tsb === "number" ? b.tsb : 0;
      if (coachSortOrder === "peak_first") {
        return tsbB - tsbA;
      } else {
        return tsbA - tsbB;
      }
    });

    return list;
  }, [coachCockpit?.students, coachStatusFilter, coachGroupFilter, coachPlanFilter, coachSearchQuery, coachSortOrder]);
  const [events, setEvents] = useState<any[]>([]);
  const [feed, setFeed] = useState<any[]>([]);
  const [feedTotal, setFeedTotal] = useState<number>(0);
  const [hasMoreFeed, setHasMoreFeed] = useState<boolean>(false);
  const [loadingMoreFeed, setLoadingMoreFeed] = useState<boolean>(false);
  const [isFeedExpanded, setIsFeedExpanded] = useState<boolean>(false);
  const [feedMonthInfo, setFeedMonthInfo] = useState<any>(null);

  // Social interaction state
  const [commentInputs, setCommentInputs] = useState<Record<string, string>>({});
  const [submittingComment, setSubmittingComment] = useState<Record<string, boolean>>({});

  // Modals & form states
  const [showJoinModal, setShowJoinModal] = useState(false);
  const [showOrgJoinModal, setShowOrgJoinModal] = useState(false);
  const [showAllClubsModal, setShowAllClubsModal] = useState(false);
  const [showCreateEventModal, setShowCreateEventModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState<any>(null);
  const [selectedStudentForReport, setSelectedStudentForReport] = useState<any | null>(null);

  // Org Join Form States with Privacy Toggles
  const [orgJoining, setOrgJoining] = useState(false);
  const [orgInviteCode, setOrgInviteCode] = useState("");
  const [orgRealName, setOrgRealName] = useState("");
  const [orgGender, setOrgGender] = useState<"male" | "female">("male");
  const [orgDob, setOrgDob] = useState("");
  const [orgProgram, setOrgProgram] = useState("中文EMBA");
  const [orgClassDetail, setOrgClassDetail] = useState("");
  const [orgClassName, setOrgClassName] = useState("");
  const [orgGobiType, setOrgGobiType] = useState<"new" | "vet">("new");
  const [orgGobiEdition, setOrgGobiEdition] = useState("戈20");
  const [orgGobiGroup, setOrgGobiGroup] = useState("A组");
  const [orgPhone, setOrgPhone] = useState("");
  const [orgIdCard, setOrgIdCard] = useState("");
  const [orgEmergencyContact, setOrgEmergencyContact] = useState("");
  const [orgClothingSize, setOrgClothingSize] = useState("");
  const [orgShoeSize, setOrgShoeSize] = useState("");
  const [orgMarathonPb, setOrgMarathonPb] = useState("");
  const [orgHealthChecked, setOrgHealthChecked] = useState(true);
  const [joinOrgFieldRules, setJoinOrgFieldRules] = useState<any[]>([]);

  const [showOrgRealName, setShowOrgRealName] = useState(false);
  const [showOrgDob, setShowOrgDob] = useState(false);
  const [showOrgIdCard, setShowOrgIdCard] = useState(false);
  const [showOrgPhone, setShowOrgPhone] = useState(false);

  // Organization Organizer (大群主理人 / 管理员 — 无需超级管理员密码即可管理本大群) states
  const [userOrgs, setUserOrgs] = useState<any[]>([]);
  const [activeManagedOrg, setActiveManagedOrg] = useState<any | null>(null);
  const [showOrgSettingsModal, setShowOrgSettingsModal] = useState(false);
  const [editOrgName, setEditOrgName] = useState("");
  const [editOrgCity, setEditOrgCity] = useState("上海");
  const [editOrgDesc, setEditOrgDesc] = useState("");
  const [editOrgJoinMode, setEditOrgJoinMode] = useState<"free" | "invite">("invite");
  const [editOrgInviteCode, setEditOrgInviteCode] = useState("");
  const [savingOrgSettings, setSavingOrgSettings] = useState(false);

  const [showOrgFieldRulesModal, setShowOrgFieldRulesModal] = useState(false);
  const [orgFieldRules, setOrgFieldRules] = useState<any[]>([]);
  const [loadingOrgFieldRules, setLoadingOrgFieldRules] = useState(false);
  const [savingOrgFieldRules, setSavingOrgFieldRules] = useState(false);

  const [showOrgRosterModal, setShowOrgRosterModal] = useState(false);
  const [orgRosterMembers, setOrgRosterMembers] = useState<any[]>([]);
  const [orgRosterSearch, setOrgRosterSearch] = useState("");
  const [loadingOrgRoster, setLoadingOrgRoster] = useState(false);
  const [orgConfirmingUid, setOrgConfirmingUid] = useState<string | null>(null);
  const [orgUpdatingRoleUid, setOrgUpdatingRoleUid] = useState<string | null>(null);

  // Organization Cross-Club Report & Sub-Club PK (📊 大群全域报表与分跑团PK) states
  const [showOrgReportModal, setShowOrgReportModal] = useState(false);
  const [orgReportData, setOrgReportData] = useState<any | null>(null);
  const [loadingOrgReport, setLoadingOrgReport] = useState(false);
  const [orgReportPeriodType, setOrgReportPeriodType] = useState<"week" | "month">("week");
  const [orgReportPeriodOffset, setOrgReportPeriodOffset] = useState<number>(0); // 0 = current, -1 = previous
  const [orgReportTrailMode, setOrgReportTrailMode] = useState<"include" | "exclude_pace" | "exclude_all">("include");
  const [orgReportTab, setOrgReportTab] = useState<"clubs_pk" | "members" | "unaffiliated">("clubs_pk");
  const [orgClubPkSortBy, setOrgClubPkSortBy] = useState<"avg_km" | "total_km" | "attendance" | "achievement">("avg_km");
  const [orgReportClubFilter, setOrgReportClubFilter] = useState<string>("all");
  const [orgReportMemberSearch, setOrgReportMemberSearch] = useState<string>("");
  const [copiedOrgReportText, setCopiedOrgReportText] = useState(false);
  const [assigningMemberClubMap, setAssigningMemberClubMap] = useState<Record<string, string>>({});
  const [assigningMemberLoadingUid, setAssigningMemberLoadingUid] = useState<string | null>(null);

  // Organization Cross-Club Events (🚩 跨跑团联合活动：大合练 & 分跑团对抗赛) states
  const [showOrgEventsModal, setShowOrgEventsModal] = useState(false);
  const [orgEventsData, setOrgEventsData] = useState<any | null>(null);
  const [loadingOrgEvents, setLoadingOrgEvents] = useState(false);
  const [creatingOrgEvent, setCreatingOrgEvent] = useState(false);
  const [orgEvtType, setOrgEvtType] = useState<"group_run" | "distance_challenge">("group_run");
  const [orgEvtTitle, setOrgEvtTitle] = useState("");
  const [orgEvtMeetTime, setOrgEvtMeetTime] = useState("");
  const [orgEvtEndDate, setOrgEvtEndDate] = useState("");
  const [orgEvtLocation, setOrgEvtLocation] = useState("世纪公园音乐广场");
  const [orgEvtTargetKm, setOrgEvtTargetKm] = useState<number>(20);
  const [orgEvtPaceReq, setOrgEvtPaceReq] = useState("A组(430) / B组(500) / C组(530) / 健康组(600)");
  const [orgEvtRules, setOrgEvtRules] = useState("");
  const [orgEvtScopeMode, setOrgEvtScopeMode] = useState<"all" | "selected">("all");
  const [orgEvtSelectedClubs, setOrgEvtSelectedClubs] = useState<string[]>([]);

  const [allClubs, setAllClubs] = useState<any[]>([]);
  const [loadingAllClubs, setLoadingAllClubs] = useState(false);
  const [joiningClubId, setJoiningClubId] = useState<string | null>(null);

  // Club Report states (Owner only)
  const [showReportModal, setShowReportModal] = useState(false);
  const [showPersonalReportModal, setShowPersonalReportModal] = useState(false);
  const [reportPeriodType, setReportPeriodType] = useState<"week" | "month">("week");
  const [reportPeriodOffset, setReportPeriodOffset] = useState<number>(0);
  const [reportTrailMode, setReportTrailMode] = useState<"include" | "exclude_pace" | "exclude_all">("include");
  const [reportViewMode, setReportViewMode] = useState<"poster" | "text">("poster");
  const [reportData, setReportData] = useState<any>(null);
  const [loadingReport, setLoadingReport] = useState<boolean>(false);
  const [copiedReportText, setCopiedReportText] = useState<boolean>(false);

  const [inviteCodeInput, setInviteCodeInput] = useState("");

  // Club WeChat Invitation & Forwarding (网页版发出跑团邀请 · 转发微信联系人) states
  const [showClubInviteModal, setShowClubInviteModal] = useState(false);
  const [clubInviteShareData, setClubInviteShareData] = useState<any | null>(null);
  const [loadingClubInviteShare, setLoadingClubInviteShare] = useState(false);
  const [copiedInviteFlag, setCopiedInviteFlag] = useState<"" | "text" | "link" | "code" | "poster">("");
  const [generatingInvitePoster, setGeneratingInvitePoster] = useState(false);

  // Incoming Web Club Invitation Landing Modal (?invite_club_id=...&invite_code=...&inviter_uid=...)
  const [showReceivedInviteModal, setShowReceivedInviteModal] = useState(false);
  const [receivedInviteData, setReceivedInviteData] = useState<any | null>(null);
  const [loadingReceivedInvite, setLoadingReceivedInvite] = useState(false);
  const [acceptingReceivedInvite, setAcceptingReceivedInvite] = useState(false);

  // Mentorship (师傅 · 1对1传帮带 · 最多带3位队员 · 同大群可跨跑团) states
  const [mentorshipOverview, setMentorshipOverview] = useState<any>(null);
  const [showMentorshipBindModal, setShowMentorshipBindModal] = useState(false);
  const [mentorshipTargetUid, setMentorshipTargetUid] = useState("");
  const [mentorshipBindRole, setMentorshipBindRole] = useState<"as_mentee" | "as_mentor">("as_mentee");
  const [bindingMentorship, setBindingMentorship] = useState(false);
  const [selectedMenteeDetail, setSelectedMenteeDetail] = useState<any | null>(null);
  const [loadingMenteeDetail, setLoadingMenteeDetail] = useState(false);

  // Club Lifecycle Management states
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [showDissolveModal, setShowDissolveModal] = useState(false);
  const [dissolveConfirmName, setDissolveConfirmName] = useState("");
  const [dissolving, setDissolving] = useState(false);

  // New Members & Unaffiliated Peers Setup Status states
  const [newMembersStatus, setNewMembersStatus] = useState<any[]>([]);
  const [newMembersSummary, setNewMembersSummary] = useState<any>(null);
  const [newMembersFilter, setNewMembersFilter] = useState<"all" | "new_30d" | "needs_setup" | "ready">("all");
  const [remindingMemberUid, setRemindingMemberUid] = useState<string | null>(null);
  const [unaffiliatedPeers, setUnaffiliatedPeers] = useState<any[]>([]);
  const [unaffiliatedPeersSummary, setUnaffiliatedPeersSummary] = useState<any>(null);
  const [unaffiliatedPeerSearch, setUnaffiliatedPeerSearch] = useState<string>("");

  // Anti-Misoperation Modals: Remove Member (Owner) & Leave Club (Member)
  const [removeMemberTarget, setRemoveMemberTarget] = useState<any | null>(null);
  const [removeMemberChecked, setRemoveMemberChecked] = useState<boolean>(false);
  const [removeMemberCountdown, setRemoveMemberCountdown] = useState<number>(0);
  const [removingMemberLoading, setRemovingMemberLoading] = useState<boolean>(false);

  const [showLeaveClubModal, setShowLeaveClubModal] = useState<boolean>(false);
  const [leaveClubChecked, setLeaveClubChecked] = useState<boolean>(false);
  const [leaveClubCountdown, setLeaveClubCountdown] = useState<number>(0);
  const [leavingClubLoading, setLeavingClubLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!removeMemberTarget || removeMemberCountdown <= 0) return;
    const t = setTimeout(() => setRemoveMemberCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => clearTimeout(t);
  }, [removeMemberTarget, removeMemberCountdown]);

  useEffect(() => {
    if (!showLeaveClubModal || leaveClubCountdown <= 0) return;
    const t = setTimeout(() => setLeaveClubCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => clearTimeout(t);
  }, [showLeaveClubModal, leaveClubCountdown]);

  const [eventTitle, setEventTitle] = useState("");
  const [eventTargetKm, setEventTargetKm] = useState(200);
  const [eventRules, setEventRules] = useState("");


  const router = useRouter();

  useEffect(() => {
    let urlInvite: { club_id: string; invite_code?: string; inviter_uid?: string } | null = null;
    if (typeof window !== "undefined") {
      const sp = new URLSearchParams(window.location.search);
      const qClubId = sp.get("invite_club_id") || (sp.get("action") === "join_club" ? sp.get("club_id") : null);
      const qCode = sp.get("invite_code") || "";
      const qInviter = sp.get("inviter_uid") || "";
      if (qClubId) {
        urlInvite = { club_id: qClubId, invite_code: qCode, inviter_uid: qInviter };
        localStorage.setItem("rgm_pending_club_invite", JSON.stringify(urlInvite));
      } else {
        try {
          const cached = localStorage.getItem("rgm_pending_club_invite");
          if (cached) {
            const parsed = JSON.parse(cached);
            if (parsed?.club_id) urlInvite = parsed;
          }
        } catch {
          // ignore
        }
      }
    }

    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadUserProfile(u.id);
        loadUserClubs(u.id);
        loadAllClubs(u.id);
        loadUserOrgs(u.id);
        loadDefaultOrgFieldRules();
        if (urlInvite?.club_id) {
          loadIncomingClubInvite(urlInvite.club_id, urlInvite.invite_code, urlInvite.inviter_uid, u.id);
        }
      } else if (urlInvite?.club_id) {
        // 未登录微信访客点击邀请链接时，先展示跑团邀请函与小程序码，不强制立刻跳走
        setLoading(false);
        loadIncomingClubInvite(urlInvite.club_id, urlInvite.invite_code, urlInvite.inviter_uid, undefined);
      } else {
        router.push("/login");
      }
    });
  }, [router]);

  async function loadIncomingClubInvite(
    clubId: string,
    inviteCode?: string,
    inviterUid?: string,
    uid?: string
  ) {
    setLoadingReceivedInvite(true);
    setShowReceivedInviteModal(true);
    try {
      const q = new URLSearchParams();
      if (inviteCode) q.set("invite_code", inviteCode);
      if (inviterUid) q.set("inviter_uid", inviterUid);
      if (uid) q.set("user_id", uid);
      const res = await apiClient.get(`/api/team/${clubId}/invite-info?${q.toString()}`);
      setReceivedInviteData({
        ...(res.data || {}),
        raw_invite_code: inviteCode || "",
        raw_inviter_uid: inviterUid || "",
      });
    } catch (e: any) {
      console.error("Load incoming club invite error:", e);
      setReceivedInviteData(null);
      setShowReceivedInviteModal(false);
    } finally {
      setLoadingReceivedInvite(false);
    }
  }

  async function handleAcceptReceivedClubInvite() {
    const clubId = receivedInviteData?.club?.id;
    if (!clubId) return;
    if (!user?.id) {
      router.push("/login");
      return;
    }
    setAcceptingReceivedInvite(true);
    try {
      const payload: any = {
        user_id: user.id,
        club_id: clubId,
        privacy_consent: true,
        via_invite: true,
      };
      if (receivedInviteData?.raw_invite_code) {
        payload.invite_code = receivedInviteData.raw_invite_code;
      }
      if (receivedInviteData?.raw_inviter_uid) {
        payload.inviter_uid = receivedInviteData.raw_inviter_uid;
      }
      const res = await apiClient.post("/api/team/join-club", payload);
      if (typeof window !== "undefined") {
        localStorage.removeItem("rgm_pending_club_invite");
        localStorage.setItem("rgm_active_club_id", clubId);
      }
      setShowReceivedInviteModal(false);
      alert(res.data?.message || `🎉 成功加入【${receivedInviteData?.club?.name || "跑团"}】！`);
      await loadUserClubs(user.id);
      await loadAllClubs(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加入跑团失败，请稍后重试");
    } finally {
      setAcceptingReceivedInvite(false);
    }
  }

  async function openClubInviteModal(targetClub?: any) {
    const club = targetClub || currentClub;
    if (!club?.id) return;
    setCopiedInviteFlag("");
    const inviterName =
      userProfile?.real_name ||
      (userProfile?.display_name && userProfile.display_name !== "跑者" ? userProfile.display_name : "");
    const fallbackCode = club.invite_code || "";
    const fallbackUrl = `https://rgm.vanpower.net/dashboard/team?invite_club_id=${encodeURIComponent(club.id)}${
      fallbackCode ? `&invite_code=${encodeURIComponent(fallbackCode)}` : ""
    }${user?.id ? `&inviter_uid=${encodeURIComponent(user.id)}` : ""}`;
    const fallbackText =
      `🏃‍♂️ ${inviterName ? `【${inviterName}】` : "跑友"}诚邀你加入【${club.name}】跑团！\n` +
      (club.org_name ? `🏛️ 所属大群：${club.org_name}\n` : "") +
      `📍 所在城市：${club.city || "上海"}（已有 ${club.member_count || members.length || 1} 位跑友同行）\n` +
      (fallbackCode ? `🔑 专属入团邀请码：${fallbackCode}\n` : "🟢 入团方式：免邀请码 · 一键加入\n") +
      `👉 加入方式：\n` +
      `1️⃣ 微信打开「万跑跑团助手」小程序，在跑团页输入邀请码${fallbackCode ? `【${fallbackCode}】` : "一键入团"}；\n` +
      `2️⃣ 或直接点击下方链接一键加入：\n${fallbackUrl}`;

    setClubInviteShareData({
      club_id: club.id,
      name: club.name,
      logo_url: club.logo_url,
      city: club.city || "上海",
      description: club.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。",
      member_count: club.member_count || members.length || 1,
      join_mode: club.join_mode || "free",
      invite_code: fallbackCode,
      org_id: club.org_id,
      org_name: club.org_name,
      inviter_name: inviterName,
      qrcode_url: "",
      qrcode_base64: "",
      web_invite_url: fallbackUrl,
      share_text: fallbackText,
    });
    setShowClubInviteModal(true);
    setLoadingClubInviteShare(true);
    try {
      const res = await apiClient.get(
        `/api/team/${club.id}/share-info${user?.id ? `?user_id=${encodeURIComponent(user.id)}` : ""}`
      );
      if (res.data) {
        setClubInviteShareData((prev: any) => ({
          ...(prev || {}),
          ...res.data,
        }));
      }
    } catch (e) {
      console.error("Load club share info error:", e);
    } finally {
      setLoadingClubInviteShare(false);
    }
  }

  async function buildClubInvitePosterCanvas(): Promise<HTMLCanvasElement | null> {
    if (!clubInviteShareData) return null;
    const d = clubInviteShareData;
    const canvas = document.createElement("canvas");
    const W = 750;
    const H = 980;
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    // 1. Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, W, H);
    bgGrad.addColorStop(0, "#141118");
    bgGrad.addColorStop(0.5, "#0d0f17");
    bgGrad.addColorStop(1, "#121824");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // Top brand accent bar
    const topBarGrad = ctx.createLinearGradient(0, 0, W, 0);
    topBarGrad.addColorStop(0, "#FC4C02");
    topBarGrad.addColorStop(0.5, "#f59e0b");
    topBarGrad.addColorStop(1, "#10b981");
    ctx.fillStyle = topBarGrad;
    ctx.fillRect(0, 0, W, 10);

    // 2. Header badge
    drawRoundedRectWeb(ctx, 44, 42, 340, 44, 22, "rgba(252, 76, 2, 0.16)", "rgba(252, 76, 2, 0.45)");
    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = "#ff7a45";
    ctx.fillText("💌 万跑跑团助手 · 官方入团邀请函", 64, 70);

    // Inviter headline
    ctx.font = "900 30px sans-serif";
    ctx.fillStyle = "#ffffff";
    const inviterLabel = d.inviter_name ? `👋 跑友【${d.inviter_name}】诚邀您入团` : "👋 诚邀您加入我们的跑团";
    ctx.fillText(inviterLabel, 44, 138);

    ctx.font = "18px sans-serif";
    ctx.fillStyle = "#9ca3af";
    ctx.fillText("科学耐力训练 · 佳明/高驰数据直连 · 队友同频共进", 44, 172);

    // 3. Main Club Card
    drawRoundedRectWeb(ctx, 40, 204, W - 80, 500, 28, "#171923", "rgba(255, 255, 255, 0.12)");

    // Club Name
    ctx.font = "900 40px sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText((d.name || "万跑科学跑团").slice(0, 15), 76, 278);

    // Badges row (Parent Org + City + Member Count)
    let badgeX = 76;
    const badgeY = 302;
    if (d.org_name) {
      const orgTxt = `🏛️ ${d.org_name}`;
      ctx.font = "bold 17px sans-serif";
      const orgW = Math.min(ctx.measureText(orgTxt).width + 32, 320);
      drawRoundedRectWeb(ctx, badgeX, badgeY, orgW, 38, 12, "rgba(245, 158, 11, 0.18)", "rgba(245, 158, 11, 0.45)");
      ctx.fillStyle = "#fcd34d";
      ctx.fillText(orgTxt, badgeX + 16, badgeY + 25);
      badgeX += orgW + 14;
    }

    const metaTxt = `📍 ${d.city || "上海"} · ${d.member_count || 1} 位跑友同行`;
    ctx.font = "bold 17px sans-serif";
    const metaW = ctx.measureText(metaTxt).width + 32;
    drawRoundedRectWeb(ctx, badgeX, badgeY, metaW, 38, 12, "rgba(16, 185, 129, 0.16)", "rgba(16, 185, 129, 0.4)");
    ctx.fillStyle = "#6ee7b7";
    ctx.fillText(metaTxt, badgeX + 16, badgeY + 25);

    // Club Description
    ctx.font = "20px sans-serif";
    ctx.fillStyle = "#d1d5db";
    drawWrappedTextWeb(
      ctx,
      d.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。欢迎每一位热爱奔跑的伙伴加入！",
      76,
      384,
      W - 152,
      30,
      3
    );

    // Exclusive Invite Code Box
    drawRoundedRectWeb(
      ctx,
      72,
      490,
      W - 144,
      176,
      22,
      "rgba(252, 76, 2, 0.10)",
      "rgba(252, 76, 2, 0.40)"
    );
    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = "#fdba74";
    ctx.fillText(
      d.invite_code ? "🔑 跑团专属入团邀请码（小程序/网页通用）" : "🟢 本跑团已开启免码自由入团",
      102,
      534
    );

    ctx.font = "900 48px monospace";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(d.invite_code || "免码直入", 102, 598);

    ctx.font = "17px sans-serif";
    ctx.fillStyle = "#9ca3af";
    ctx.fillText(
      d.invite_code
        ? "微信扫码直接免输码入团，或在小程序「跑团 → 输入邀请码」填入"
        : "微信长按或扫描下方小程序码，即可一键加入跑团",
      102,
      638
    );

    // 4. Footer with Official WeChat Mini Program QR Code
    const fY = 740;
    drawRoundedRectWeb(ctx, 40, fY, W - 80, 190, 26, "#121520", "rgba(255, 255, 255, 0.12)");

    ctx.font = "bold 20px sans-serif";
    ctx.fillStyle = "#FC4C02";
    ctx.fillText("📱 微信扫码或长按识别 · 一键入团", 72, fY + 54);

    ctx.font = "900 28px sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText("打开「万跑跑团助手」小程序", 72, fY + 98);

    ctx.font = "17px sans-serif";
    ctx.fillStyle = "#9ca3af";
    ctx.fillText("直达跑团受邀页面 · 同步跑表解锁 AI 教练与团队排行榜", 72, fY + 140);

    const qrSrc = d.qrcode_base64
      ? d.qrcode_base64.startsWith("data:")
        ? d.qrcode_base64
        : `data:image/jpeg;base64,${d.qrcode_base64}`
      : d.qrcode_url || "";

    if (qrSrc) {
      await new Promise<void>((resolve) => {
        const qrImg = new Image();
        qrImg.crossOrigin = "anonymous";
        qrImg.onload = () => {
          const qrBoxX = W - 40 - 166;
          const qrBoxY = fY + 20;
          drawRoundedRectWeb(ctx, qrBoxX, qrBoxY, 150, 150, 18, "#ffffff");
          ctx.drawImage(qrImg, qrBoxX + 8, qrBoxY + 8, 134, 134);
          resolve();
        };
        qrImg.onerror = () => resolve();
        qrImg.src = qrSrc;
      });
    }

    return canvas;
  }

  async function handleCopyClubInvitePosterImage() {
    setGeneratingInvitePoster(true);
    try {
      const canvas = await buildClubInvitePosterCanvas();
      if (!canvas) return;
      const blob: Blob | null = await new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/png"));
      if (blob && typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
        await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        setCopiedInviteFlag("poster");
        setTimeout(() => setCopiedInviteFlag(""), 4000);
        return;
      }
      // Fallback: download PNG if browser blocks clipboard image write
      const dataUrl = canvas.toDataURL("image/png");
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${clubInviteShareData?.name || "跑团"}_微信入团邀请函.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setCopiedInviteFlag("poster");
      setTimeout(() => setCopiedInviteFlag(""), 4000);
    } catch (e) {
      console.error("Copy poster image error:", e);
      await handleDownloadClubInvitePoster();
    } finally {
      setGeneratingInvitePoster(false);
    }
  }

  async function handleDownloadClubInvitePoster() {
    setGeneratingInvitePoster(true);
    try {
      const canvas = await buildClubInvitePosterCanvas();
      if (!canvas) return;
      const dataUrl = canvas.toDataURL("image/png");
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${clubInviteShareData?.name || "跑团"}_微信入团邀请函.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } finally {
      setGeneratingInvitePoster(false);
    }
  }

  async function handleNativeShareClubInvite() {
    if (!clubInviteShareData) return;
    const nav: any = typeof navigator !== "undefined" ? navigator : null;
    if (nav?.share) {
      try {
        await nav.share({
          title: `诚邀加入【${clubInviteShareData.name}】跑团`,
          text: clubInviteShareData.share_text,
          url: clubInviteShareData.web_invite_url,
        });
        return;
      } catch {
        // user cancelled or unsupported
      }
    }
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(clubInviteShareData.share_text || "");
      setCopiedInviteFlag("text");
      setTimeout(() => setCopiedInviteFlag(""), 3000);
    }
  }

  async function loadUserProfile(uid: string) {
    try {
      const res = await apiClient.get(`/api/profile/${uid}`);
      if (res.data?.profile) {
        const p = res.data.profile;
        setUserProfile(p);
        if (p.real_name) setOrgRealName(p.real_name);
        if (p.gender === "female") setOrgGender("female");
        if (p.date_of_birth) setOrgDob(p.date_of_birth);
        if (p.phone) setOrgPhone(p.phone);
        if (p.id_card) setOrgIdCard(p.id_card);
      }
    } catch (e) {
      console.error("Load user profile error:", e);
    }
  }

  async function loadAllClubs(uid?: string) {
    const effUid = uid || user?.id;
    setLoadingAllClubs(true);
    try {
      const res = await apiClient.get(`/api/team/all-clubs${effUid ? `?user_id=${effUid}` : ""}`);
      setAllClubs(res.data?.clubs || []);
    } catch (e) {
      console.error("Fetch all clubs error:", e);
    } finally {
      setLoadingAllClubs(false);
    }
  }

  async function handleJoinClubDirect(clubId: string, inviteCode?: string) {
    if (!user?.id) return;
    setJoiningClubId(clubId);
    try {
      const payload: any = {
        user_id: user.id,
        club_id: clubId,
        privacy_consent: true,
      };
      if (inviteCode) {
        payload.invite_code = inviteCode;
      }
      const res = await apiClient.post("/api/team/join-club", payload);
      alert(res.data?.message || "成功加入跑团！");
      if (typeof window !== "undefined") {
        localStorage.setItem("rgm_active_club_id", clubId);
      }
      setShowAllClubsModal(false);
      setShowJoinModal(false);
      await loadUserClubs(user.id);
      await loadAllClubs(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加入跑团失败，请重试！");
    } finally {
      setJoiningClubId(null);
    }
  }

  async function loadUserOrgs(uid?: string) {
    const effUid = uid || user?.id;
    if (!effUid) return;
    try {
      const res = await apiClient.get(`/api/org/my-orgs/${effUid}`);
      const orgs = res.data?.organizations || [];
      setUserOrgs(orgs);
      const managed = orgs.find(
        (o: any) => o.is_organizer || o.role === "owner" || o.role === "admin" || o.owner_id === effUid
      );
      if (managed) {
        setActiveManagedOrg((prev: any) => {
          if (prev) {
            const updated = orgs.find((o: any) => o.id === prev.id);
            if (updated) return updated;
          }
          return managed;
        });
      }
      if (orgs.length > 0 && orgs[0]?.field_rules) {
        setJoinOrgFieldRules(orgs[0].field_rules);
      }
    } catch (e) {
      console.error("Load user orgs error:", e);
    }
  }

  async function loadDefaultOrgFieldRules() {
    try {
      const res = await apiClient.get("/api/org/all/list");
      const orgs = res.data?.organizations || [];
      if (orgs.length > 0 && orgs[0]?.field_rules) {
        setJoinOrgFieldRules((prev) => (prev.length > 0 ? prev : orgs[0].field_rules));
      }
    } catch (e) {
      // ignore
    }
  }

  async function verifyOrgCodeAndLoadRules(codeStr: string) {
    const clean = (codeStr || "").trim().toUpperCase();
    if (clean.length < 3) return;
    try {
      const res = await apiClient.post("/api/org/verify-code", { invite_code: clean });
      if (res.data?.field_rules) {
        setJoinOrgFieldRules(res.data.field_rules);
      }
    } catch (e) {
      // ignore invalid code while typing
    }
  }

  function isJoinFieldVisible(fieldKey: string): boolean {
    if (!joinOrgFieldRules || joinOrgFieldRules.length === 0) return true;
    const rule = joinOrgFieldRules.find((r: any) => (r.field || r.field_key) === fieldKey);
    if (!rule) return true;
    return !(rule.mode === "hidden" || rule.hidden === true || rule.visible === false);
  }

  function isJoinFieldRequired(fieldKey: string): boolean {
    if (!isJoinFieldVisible(fieldKey)) return false;
    if (!joinOrgFieldRules || joinOrgFieldRules.length === 0) {
      return ["real_name", "gender", "date_of_birth", "class_name"].includes(fieldKey);
    }
    const rule = joinOrgFieldRules.find((r: any) => (r.field || r.field_key) === fieldKey);
    if (!rule) return false;
    return rule.mode === "required" || (rule.mode !== "optional" && Boolean(rule.required));
  }

  function openOrgSettingsModalFor(org: any) {
    setActiveManagedOrg(org);
    setEditOrgName(org.name || "");
    setEditOrgCity(org.city || "上海");
    setEditOrgDesc(org.description || "");
    setEditOrgJoinMode(org.join_mode === "free" ? "free" : "invite");
    setEditOrgInviteCode(org.invite_code || "");
    setShowOrgSettingsModal(true);
  }

  async function handleSaveOrgSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!activeManagedOrg || !user?.id) return;
    if (!editOrgName.trim()) {
      alert("大群名称不能为空");
      return;
    }
    setSavingOrgSettings(true);
    try {
      const res = await apiClient.put(`/api/org/${activeManagedOrg.id}`, {
        name: editOrgName.trim(),
        city: editOrgCity.trim() || "上海",
        description: editOrgDesc.trim(),
        join_mode: editOrgJoinMode,
        invite_code: editOrgInviteCode.trim().toUpperCase() || undefined,
        operator_uid: user.id,
      });
      alert(res.data?.message || "大群设定保存成功！");
      setShowOrgSettingsModal(false);
      await loadUserOrgs(user.id);
      await loadUserClubs(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "保存大群设定失败");
    } finally {
      setSavingOrgSettings(false);
    }
  }

  async function openOrgFieldRulesModalFor(org: any) {
    setActiveManagedOrg(org);
    setShowOrgFieldRulesModal(true);
    setLoadingOrgFieldRules(true);
    try {
      const res = await apiClient.get(`/api/org/${org.id}/field-rules`);
      setOrgFieldRules(res.data?.field_rules || []);
    } catch (err: any) {
      alert("加载准入字段规则失败");
    } finally {
      setLoadingOrgFieldRules(false);
    }
  }

  async function handleSaveOrgFieldRules() {
    if (!activeManagedOrg || !user?.id) return;
    setSavingOrgFieldRules(true);
    try {
      const res = await apiClient.put(`/api/org/${activeManagedOrg.id}/field-rules`, {
        field_rules: orgFieldRules,
        operator_uid: user.id,
      });
      if (res.data?.field_rules) {
        setOrgFieldRules(res.data.field_rules);
        setJoinOrgFieldRules(res.data.field_rules);
      }
      alert(res.data?.message || "大群准入信息规则（必填/选填/不显示）已保存！");
      setShowOrgFieldRulesModal(false);
      await loadUserOrgs(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "保存大群准入规则失败");
    } finally {
      setSavingOrgFieldRules(false);
    }
  }

  async function openOrgRosterModalFor(org: any) {
    setActiveManagedOrg(org);
    setOrgRosterSearch("");
    setShowOrgRosterModal(true);
    setLoadingOrgRoster(true);
    try {
      const res = await apiClient.get(`/api/org/${org.id}/members?operator_uid=${encodeURIComponent(user?.id || "")}`);
      setOrgRosterMembers(res.data?.members || []);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加载大群花名册失败");
    } finally {
      setLoadingOrgRoster(false);
    }
  }

  async function handleOrgConfirmMember(targetUid: string) {
    if (!activeManagedOrg || !user?.id) return;
    setOrgConfirmingUid(targetUid);
    try {
      await apiClient.post(`/api/org/${activeManagedOrg.id}/members/${targetUid}/confirm`, {
        operator_uid: user.id,
      });
      setOrgRosterMembers((prev) =>
        prev.map((m) => (m.user_id === targetUid ? { ...m, status: "confirmed" } : m))
      );
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || "确认成员失败";
      const targetMember = orgRosterMembers.find((m) => m.user_id === targetUid);
      if (targetMember?.status === "expired" && errorMsg.includes("必填资料尚未补齐")) {
        if (window.confirm(`${errorMsg}\n\n是否为该队员重置 14 天临时访问宽限期？`)) {
          await apiClient.post(`/api/org/${activeManagedOrg.id}/members/${targetUid}/grace-period`);
          setOrgRosterMembers((prev) =>
            prev.map((m) => (m.user_id === targetUid ? { ...m, status: "temporary", days_remaining: 14 } : m))
          );
        }
      } else {
        alert(errorMsg);
      }
    } finally {
      setOrgConfirmingUid(null);
    }
  }

  async function handleOrgToggleMemberRole(targetUid: string, newRole: "admin" | "member") {
    if (!activeManagedOrg || !user?.id) return;
    setOrgUpdatingRoleUid(targetUid);
    try {
      await apiClient.post(`/api/org/${activeManagedOrg.id}/members/${targetUid}/role`, {
        role: newRole,
        operator_uid: user.id,
      });
      setOrgRosterMembers((prev) =>
        prev.map((m) => (m.user_id === targetUid ? { ...m, role: newRole } : m))
      );
    } catch (err: any) {
      alert(err.response?.data?.detail || "调整大群管理员角色失败");
    } finally {
      setOrgUpdatingRoleUid(null);
    }
  }

  async function fetchOrgReport(
    orgId: string,
    pType: "week" | "month" = orgReportPeriodType,
    pOffset: number = orgReportPeriodOffset,
    tMode: "include" | "exclude_pace" | "exclude_all" = orgReportTrailMode
  ) {
    if (!orgId || !user?.id) return;
    setLoadingOrgReport(true);
    try {
      const q = new URLSearchParams({
        operator_uid: user.id,
        period_type: pType,
        trail_mode: tMode,
      });
      if (pOffset === -1) {
        const now = new Date();
        if (pType === "month") {
          let y = now.getFullYear();
          let m = now.getMonth(); // 0-indexed, so current month - 1
          if (m === 0) {
            m = 12;
            y -= 1;
          }
          q.set("year", String(y));
          q.set("period_index", String(m));
        } else {
          const prev = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
          const d = new Date(Date.UTC(prev.getFullYear(), prev.getMonth(), prev.getDate()));
          const dayNum = d.getUTCDay() || 7;
          d.setUTCDate(d.getUTCDate() + 4 - dayNum);
          const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
          const weekNo = Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
          q.set("year", String(d.getUTCFullYear()));
          q.set("period_index", String(weekNo));
        }
      }
      const res = await apiClient.get(`/api/org/${orgId}/reports?${q.toString()}`);
      setOrgReportData(res.data || null);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加载大群全域报表失败");
    } finally {
      setLoadingOrgReport(false);
    }
  }

  function openOrgReportModalFor(org: any) {
    setActiveManagedOrg(org);
    setOrgReportTab("clubs_pk");
    setOrgReportClubFilter("all");
    setOrgReportMemberSearch("");
    setShowOrgReportModal(true);
    fetchOrgReport(org.id, orgReportPeriodType, orgReportPeriodOffset, orgReportTrailMode);
  }

  function handleExportOrgReportCsv() {
    if (!orgReportData) return;
    const rows: string[][] = [
      ["排名", "姓名", "所属分跑团", "商学院班级", "戈壁经历", "本期跑量(km)", "跑次", "平均配速", "单次最长(km)", "目标(km)", "完成率(%)", "全马PB", "手表绑定"],
    ];
    for (const m of orgReportData.member_rankings || []) {
      rows.push([
        String(m.rank || ""),
        m.display_name || "",
        (m.sub_club_names || []).join(" / ") || "未入分跑团",
        m.class_name || "",
        m.gobi_experience || "",
        String(m.distance_km ?? 0),
        String(m.runs_count ?? 0),
        m.avg_pace_str || "—",
        String(m.longest_run_km ?? 0),
        String(m.target_km ?? 0),
        String(m.completion_rate ?? 0),
        m.marathon_pb || "",
        m.watch_connected ? "已绑定" : "未绑定",
      ]);
    }
    const csvContent =
      "\uFEFF" +
      rows
        .map((r) => r.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
        .join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${orgReportData.org_name || "大群"}_${orgReportData.period_label || "报表"}_跨跑团全员明细.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function handleAssignOrgMemberToClub(targetUid: string, clubId?: string) {
    if (!activeManagedOrg || !user?.id) return;
    const effClubId =
      clubId ||
      assigningMemberClubMap[targetUid] ||
      orgReportData?.sub_club_rankings?.[0]?.club_id;
    if (!effClubId) {
      alert("请先选择要划入的下属分跑团");
      return;
    }
    setAssigningMemberLoadingUid(targetUid);
    try {
      const res = await apiClient.post(
        `/api/org/${activeManagedOrg.id}/members/${encodeURIComponent(targetUid)}/assign-club`,
        {
          operator_uid: user.id,
          club_id: effClubId,
        }
      );
      alert(res.data?.message || "已成功分配至下属跑团！");
      await fetchOrgReport(activeManagedOrg.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "分配跑团失败");
    } finally {
      setAssigningMemberLoadingUid(null);
    }
  }

  async function fetchOrgEvents(orgId: string) {
    if (!orgId) return;
    setLoadingOrgEvents(true);
    try {
      const res = await apiClient.get(
        `/api/org/${orgId}/events${user?.id ? `?user_id=${encodeURIComponent(user.id)}` : ""}`
      );
      setOrgEventsData(res.data || null);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加载跨跑团联合活动失败");
    } finally {
      setLoadingOrgEvents(false);
    }
  }

  function openOrgEventsModalFor(org: any) {
    setActiveManagedOrg(org);
    const tomorrow = new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 10);
    const nextMonth = new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString().slice(0, 10);
    setOrgEvtType("group_run");
    setOrgEvtTitle(`【${org.name}】周末跨跑团联合 LSD 大合练`);
    setOrgEvtMeetTime(`${tomorrow} 06:30`);
    setOrgEvtEndDate(nextMonth);
    setOrgEvtLocation("世纪公园 1号门音乐广场");
    setOrgEvtTargetKm(20);
    setOrgEvtPaceReq("A组(430) / B组(500) / C组(530) / 健康组(600)");
    setOrgEvtRules("大群跨跑团联合拉练，各分跑团成员均可一键报名，系统将自动按分跑团统计出勤人数与完赛总跑量！");
    setOrgEvtScopeMode("all");
    setOrgEvtSelectedClubs([]);
    setShowOrgEventsModal(true);
    fetchOrgEvents(org.id);
  }

  async function handleCreateOrgCrossClubEvent(e: React.FormEvent) {
    e.preventDefault();
    if (!activeManagedOrg || !user?.id) return;
    if (!orgEvtTitle.trim()) {
      alert("请输入跨跑团联合活动名称");
      return;
    }
    if (orgEvtScopeMode === "selected" && orgEvtSelectedClubs.length === 0) {
      alert("请至少勾选 1 个参与的下属分跑团，或切换为「大群下属全部跑团」");
      return;
    }
    setCreatingOrgEvent(true);
    try {
      const res = await apiClient.post(`/api/org/${activeManagedOrg.id}/events`, {
        operator_uid: user.id,
        title: orgEvtTitle.trim(),
        event_type: orgEvtType,
        meet_time: orgEvtMeetTime.trim() || undefined,
        start_date: orgEvtMeetTime.trim().split(" ")[0] || undefined,
        end_date: orgEvtType === "distance_challenge" ? orgEvtEndDate : undefined,
        location: orgEvtLocation.trim() || "集合点",
        target_km: Number(orgEvtTargetKm) || 15,
        pace_requirement: orgEvtPaceReq.trim(),
        rules: orgEvtRules.trim(),
        scope_club_ids: orgEvtScopeMode === "all" ? "all" : orgEvtSelectedClubs,
      });
      alert(res.data?.message || "跨跑团联合活动发布成功！");
      await fetchOrgEvents(activeManagedOrg.id);
      if (currentClub?.id) {
        await loadClubDetails(currentClub.id, user.id);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "发布跨跑团活动失败");
    } finally {
      setCreatingOrgEvent(false);
    }
  }

  async function handleOrgJoin(e: React.FormEvent) {
    e.preventDefault();
    if (!user?.id) return;
    if (!orgInviteCode.trim()) {
      alert("请输入大群体专属邀请码");
      return;
    }
    if (isJoinFieldRequired("real_name") && !orgRealName.trim()) {
      alert("请填写真实姓名以便管理员核对确认");
      return;
    }
    const finalClass = isJoinFieldVisible("class_name")
      ? orgProgram
        ? `${orgProgram} ${orgClassDetail}`.trim()
        : orgClassName.trim()
      : "";
    if (isJoinFieldRequired("class_name") && (!finalClass || (orgProgram && !orgClassDetail.trim()))) {
      alert("请选择商学院项目并填写具体班级（例如 23春、21级）");
      return;
    }
    if (isJoinFieldRequired("date_of_birth") && !orgDob.trim()) {
      alert("请选择出生日期");
      return;
    }
    if (isJoinFieldRequired("phone") && !orgPhone.trim()) {
      alert("请填写联系手机");
      return;
    }
    if (isJoinFieldRequired("id_card") && !orgIdCard.trim()) {
      alert("请填写证件号码");
      return;
    }
    if (isJoinFieldRequired("emergency_contact") && !orgEmergencyContact.trim()) {
      alert("请填写紧急联系人及电话");
      return;
    }
    if (isJoinFieldRequired("clothing_size") && !orgClothingSize.trim()) {
      alert("请选择队服尺码");
      return;
    }
    if (isJoinFieldRequired("shoe_size") && !orgShoeSize.trim()) {
      alert("请选择跑鞋尺码");
      return;
    }
    if (isJoinFieldRequired("marathon_pb") && !orgMarathonPb.trim()) {
      alert("请填写全马PB成绩");
      return;
    }
    if (isJoinFieldRequired("health_declaration") && !orgHealthChecked) {
      alert("请勾选参赛健康状况声明");
      return;
    }

    const finalGobi = isJoinFieldVisible("gobi_experience")
      ? orgGobiType === "new"
        ? "新戈"
        : `${orgGobiEdition} ${orgGobiGroup}`
      : "";

    setOrgJoining(true);
    try {
      const res = await apiClient.post("/api/org/join", {
        user_id: user.id,
        invite_code: orgInviteCode.trim().toUpperCase(),
        real_name: isJoinFieldVisible("real_name") ? orgRealName.trim() : undefined,
        gender: isJoinFieldVisible("gender") ? orgGender : "male",
        date_of_birth: isJoinFieldVisible("date_of_birth") ? orgDob.trim() : undefined,
        class_name: finalClass || undefined,
        program: isJoinFieldVisible("class_name") ? orgProgram : undefined,
        class_detail: isJoinFieldVisible("class_name") ? orgClassDetail.trim() : undefined,
        gobi_experience: finalGobi || undefined,
        phone: isJoinFieldVisible("phone") ? orgPhone.trim() : undefined,
        id_card: isJoinFieldVisible("id_card") ? orgIdCard.trim() : undefined,
        emergency_contact: isJoinFieldVisible("emergency_contact") ? orgEmergencyContact.trim() : undefined,
        clothing_size: isJoinFieldVisible("clothing_size") ? orgClothingSize.trim() : undefined,
        shoe_size: isJoinFieldVisible("shoe_size") ? orgShoeSize.trim() : undefined,
        marathon_pb: isJoinFieldVisible("marathon_pb") ? orgMarathonPb.trim() : undefined,
        health_declaration: isJoinFieldVisible("health_declaration") ? orgHealthChecked : undefined,
      });
      alert(res.data?.message || "实名认证登记成功，已加入大群体！");
      setShowOrgJoinModal(false);
      await loadUserOrgs(user.id);
      await loadUserClubs(user.id);
      await loadAllClubs(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加入大群体失败，请检查邀请码后重试！");
    } finally {
      setOrgJoining(false);
    }
  }

  async function handleUpdateJoinMode(mode: "free" | "invite") {
    if (!currentClub?.id || !user?.id) return;
    try {
      const res = await apiClient.post(`/api/team/${currentClub.id}/join-mode`, {
        operator_uid: user.id,
        join_mode: mode,
      });
      alert(res.data?.message || "入团规则已更新！");
      setCurrentClub((prev: any) => ({
        ...prev,
        join_mode: mode,
        ...(res.data?.club?.invite_code ? { invite_code: res.data.club.invite_code } : {})
      }));
    } catch (e: any) {
      alert(e.response?.data?.detail || "更新入团规则失败，请重试！");
    }
  }

  async function handleSetClubStatus(newStatus: "active" | "paused" | "locked") {
    if (!currentClub?.id || !user?.id) return;
    setStatusUpdating(true);
    try {
      const res = await apiClient.post(`/api/team/${currentClub.id}/status`, {
        operator_uid: user.id,
        status: newStatus,
      });
      alert(res.data?.message || "跑团运行状态已更新！");
      setCurrentClub((prev: any) => ({ ...prev, status: newStatus }));
      setClubs(clubs.map((c) => (c.id === currentClub.id ? { ...c, status: newStatus } : c)));
    } catch (e: any) {
      alert(e.response?.data?.detail || "更新跑团状态失败，请重试！");
    } finally {
      setStatusUpdating(false);
    }
  }

  async function handleDissolveClub(e: React.FormEvent) {
    e.preventDefault();
    if (!currentClub?.id || !user?.id) return;
    if (dissolveConfirmName.trim() !== currentClub.name.trim()) {
      alert("输入的跑团名称与当前跑团不一致，请核实后重试！");
      return;
    }
    setDissolving(true);
    try {
      const res = await apiClient.delete(`/api/team/${currentClub.id}?operator_uid=${user.id}`);
      alert(res.data?.message || "跑团已成功解散并清理，全体队员个人数据已完整保留！");
      setShowDissolveModal(false);
      setDissolveConfirmName("");
      // Refresh clubs list
      const rem = clubs.filter((c) => c.id !== currentClub.id);
      setClubs(rem);
      if (rem.length > 0) {
        handleSwitchClub(rem[0]);
      } else {
        setCurrentClub(null);
      }
    } catch (e: any) {
      alert(e.response?.data?.detail || "解散跑团失败，请重试！");
    } finally {
      setDissolving(false);
    }
  }


  async function fetchClubReport(
    periodType: "week" | "month" = reportPeriodType,
    offset: number = reportPeriodOffset,
    trailMode: "include" | "exclude_pace" | "exclude_all" = reportTrailMode
  ) {
    if (!currentClub?.id || !user?.id) return;
    setLoadingReport(true);
    try {
      let url = `/api/team/${currentClub.id}/reports?operator_uid=${user.id}&period_type=${periodType}&trail_mode=${trailMode}`;
      if (offset === -1) {
        const now = new Date();
        if (periodType === "week") {
          const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
          const target = new Date(d.valueOf());
          const dayNr = (d.getDay() + 6) % 7;
          target.setDate(target.getDate() - dayNr + 3);
          const firstThursday = target.valueOf();
          target.setMonth(0, 1);
          if (target.getDay() !== 4) {
            target.setMonth(0, 1 + ((4 - target.getDay()) + 7) % 7);
          }
          const weekNum = 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
          url += `&year=${d.getFullYear()}&period_index=${weekNum}`;
        } else {
          const prevMonth = now.getMonth() === 0 ? 12 : now.getMonth();
          const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
          url += `&year=${prevYear}&period_index=${prevMonth}`;
        }
      }
      const res = await apiClient.get(url);
      setReportData(res.data);
    } catch (err: any) {
      console.error("fetchClubReport error:", err);
      alert(err.response?.data?.detail || "获取跑团报表失败");
    } finally {
      setLoadingReport(false);
    }
  }

  const [showBroadcastModal, setShowBroadcastModal] = useState(false);
  const [bcastDayIndex, setBcastDayIndex] = useState(1); // default Tuesday
  const [bcastWeekMode, setBcastWeekMode] = useState<"current" | "next">("current");
  const [bcastWorkoutType, setBcastWorkoutType] = useState("interval");
  const [bcastTitle, setBcastTitle] = useState("交大合练：慢跑+身训+间歇速度课");
  const [bcastDistanceKm, setBcastDistanceKm] = useState<number>(12);
  const [bcastTargetPace, setBcastTargetPace] = useState("按A/B/C组配速");
  const [bcastDescription, setBcastDescription] = useState("慢跑热身4km + 臀腿核心身训2组 + 场地间歇速度训练");
  const [broadcastingWorkout, setBroadcastingWorkout] = useState(false);

  // Self-service club creation & group-run signup parity states
  const [showCreateClubModal, setShowCreateClubModal] = useState(false);
  const [newClubName, setNewClubName] = useState("");
  const [newClubCity, setNewClubCity] = useState("上海");
  const [newClubDesc, setNewClubDesc] = useState("");
  const [newClubJoinMode, setNewClubJoinMode] = useState<"free" | "invite">("free");
  const [creatingClub, setCreatingClub] = useState(false);
  const [togglingEventId, setTogglingEventId] = useState<string | null>(null);

  async function handleCreateSelfClub(e: React.FormEvent) {
    e.preventDefault();
    if (!user?.id || !newClubName.trim() || creatingClub) return;
    setCreatingClub(true);
    try {
      const res = await apiClient.post("/api/team/clubs", {
        owner_id: user.id,
        name: newClubName.trim(),
        city: newClubCity.trim() || "上海",
        description: newClubDesc.trim() || undefined,
        join_mode: newClubJoinMode,
      });
      const createdClub = res.data?.club;
      setShowCreateClubModal(false);
      setNewClubName("");
      setNewClubDesc("");
      alert(res.data?.message || "✅ 跑团创建成功！");
      if (createdClub?.id) {
        await loadClubDetails(createdClub.id, user.id);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "创建跑团失败，请检查邀请解锁条件后重试");
    } finally {
      setCreatingClub(false);
    }
  }

  async function handleToggleEventJoin(evt: any) {
    if (!user?.id || !evt?.id || togglingEventId) return;
    const targetClubId = evt.club_id || currentClub?.id;
    if (!targetClubId) return;
    setTogglingEventId(evt.id);
    try {
      if (evt.is_joined) {
        await apiClient.post(`/api/team/${encodeURIComponent(targetClubId)}/events/${encodeURIComponent(evt.id)}/leave`, {
          user_id: user.id,
        });
      } else {
        await apiClient.post(`/api/team/${encodeURIComponent(targetClubId)}/events/${encodeURIComponent(evt.id)}/join`, {
          user_id: user.id,
          auto_join_club: true,
        });
      }
      if (currentClub?.id) {
        await loadClubDetails(currentClub.id, user.id);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "操作失败，请稍后重试");
    } finally {
      setTogglingEventId(null);
    }
  }

  async function handleBroadcastClubWorkout() {
    if (!currentClub?.id || !user?.id || !bcastTitle.trim() || broadcastingWorkout) return;
    setBroadcastingWorkout(true);
    try {
      const res = await apiClient.post("/api/coach/plan/club-broadcast-workout", {
        club_id: currentClub.id,
        operator_uid: user.id,
        day_index: bcastDayIndex,
        day_index_base: 0,
        target_week_mode: bcastWeekMode,
        workout_type: bcastWorkoutType,
        title: bcastTitle.trim(),
        distance_km: Number(bcastDistanceKm) || 10,
        target_pace: bcastTargetPace,
        description: bcastDescription,
      });
      alert(res.data?.message || "已成功将跑团合练课表同步派发给全体队员！");
      setShowBroadcastModal(false);
      await loadClubDetails(currentClub.id, user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "派发跑团合练课表失败");
    } finally {
      setBroadcastingWorkout(false);
    }
  }

  async function handleBatchGenerateClubDrafts(onlyWithoutPlan: boolean = true) {
    if (!currentClub?.id || !user?.id || batchGeneratingDrafts) return;
    setBatchGeneratingDrafts(true);
    try {
      const res = await apiClient.post("/api/coach/plan/club-batch-generate", {
        club_id: currentClub.id,
        operator_uid: user.id,
        weeks: 4,
        only_without_plan: onlyWithoutPlan,
      });
      alert(res.data?.message || "已批量生成个性化训练计划草案，请点击学员卡片进行审核与发布！");
      await loadClubDetails(currentClub.id, user.id);
      if ((res.data?.generated_count || 0) > 0) {
        setCoachPlanFilter("draft_pending");
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "批量生成训练计划草案失败，请稍后重试");
    } finally {
      setBatchGeneratingDrafts(false);
    }
  }

  // ── Coach Pace & Intensity Group Templates State ──
  const [showTemplateAssignModal, setShowTemplateAssignModal] = useState(false);
  const [showScheduleImportModal, setShowScheduleImportModal] = useState(false);
  const [coachTemplates, setCoachTemplates] = useState<any[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [templateCategoryFilter, setTemplateCategoryFilter] = useState<string>("all");
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("group_b_sub330");
  const [templateCustomDays, setTemplateCustomDays] = useState<any[]>([]);
  const [templateScaleFactor, setTemplateScaleFactor] = useState<number>(1.0);
  const [templateApplyScope, setTemplateApplyScope] = useState<"full_plan" | "current_week" | "next_week">("full_plan");
  const [selectedMemberIdsForTemplate, setSelectedMemberIdsForTemplate] = useState<string[]>([]);
  const [assigningTemplate, setAssigningTemplate] = useState(false);

  // Custom Template Editor / Save-As State
  const [showTemplateMetaEditor, setShowTemplateMetaEditor] = useState(false);
  const [tplEditGroupCode, setTplEditGroupCode] = useState("");
  const [tplEditShortName, setTplEditShortName] = useState("");
  const [tplEditCategory, setTplEditCategory] = useState("marathon");
  const [tplEditTargetPb, setTplEditTargetPb] = useState("");
  const [tplEditIntensityBadge, setTplEditIntensityBadge] = useState("");
  const [tplEditDescription, setTplEditDescription] = useState("");
  const [tplEditMacroRoadmap, setTplEditMacroRoadmap] = useState("");
  const [tplEditPaceEasy, setTplEditPaceEasy] = useState("");
  const [tplEditPaceMarathon, setTplEditPaceMarathon] = useState("");
  const [tplEditPaceTempo, setTplEditPaceTempo] = useState("");
  const [tplEditPaceInterval, setTplEditPaceInterval] = useState("");
  const [tplEditPaceCore, setTplEditPaceCore] = useState("");
  const [savingCustomTemplate, setSavingCustomTemplate] = useState(false);

  // Distribution wizard settings (周期长度 / Canova 逐周递进 / 搜索 / 微调模式 / 全周期总览)
  const [templateWeeksCount, setTemplateWeeksCount] = useState<number>(8);
  const [templateCanovaProgression, setTemplateCanovaProgression] = useState<boolean>(true);
  const [templateSearchQuery, setTemplateSearchQuery] = useState<string>("");
  const [templateMemberSearch, setTemplateMemberSearch] = useState<string>("");
  const [templateEditMode, setTemplateEditMode] = useState<boolean>(false);
  const [templatePreviewWeeks, setTemplatePreviewWeeks] = useState<any[]>([]);
  const [loadingTemplatePreview, setLoadingTemplatePreview] = useState<boolean>(false);
  const [templateHasEditedWeeks, setTemplateHasEditedWeeks] = useState<boolean>(false);
  const [templatePlanViewTab, setTemplatePlanViewTab] = useState<"matrix" | number | "baseline">("matrix");
  const [editingMatrixCell, setEditingMatrixCell] = useState<{ weekIdx: number; dayIdx: number } | null>(null);

  /** Normalizes backend categories (road_marathon / gobi_desert / ultra_trail / custom) into UI tabs. */
  function getTemplateCategoryKey(tpl: any): "marathon" | "gobi" | "trail" | "custom" {
    if (tpl?.is_custom) return "custom";
    const cat = String(tpl?.category || "").toLowerCase();
    if (cat.includes("gobi")) return "gobi";
    if (cat.includes("trail")) return "trail";
    return "marathon";
  }

  const filteredCoachTemplates = useMemo(() => {
    const q = templateSearchQuery.trim().toLowerCase();
    return coachTemplates.filter((t: any) => {
      if (templateCategoryFilter !== "all" && getTemplateCategoryKey(t) !== templateCategoryFilter) return false;
      if (!q) return true;
      return [t.short_name, t.name, t.group_code, t.target_pb_label, t.intensity_badge]
        .filter(Boolean)
        .some((s: string) => String(s).toLowerCase().includes(q));
    });
  }, [coachTemplates, templateCategoryFilter, templateSearchQuery]);

  const templateRecCountMap = useMemo(() => {
    const m: Record<string, number> = {};
    (coachCockpit?.students || []).forEach((s: any) => {
      const tid = s.recommended_group?.template_id;
      if (tid) m[tid] = (m[tid] || 0) + 1;
    });
    return m;
  }, [coachCockpit?.students]);

  const activeTemplateObj = useMemo(() => {
    return coachTemplates.find((t: any) => t.id === selectedTemplateId) || coachTemplates[0] || null;
  }, [coachTemplates, selectedTemplateId]);

  const templateCanovaOutline: string[] = useMemo(() => {
    if (!activeTemplateObj) return [];
    return activeTemplateObj.canova_outline?.[String(templateWeeksCount)] || [];
  }, [activeTemplateObj, templateWeeksCount]);

  async function loadCoachTemplates(): Promise<any[]> {
    if (!user?.id) return coachTemplates;
    setLoadingTemplates(true);
    try {
      const res = await apiClient.get(
        `/api/coach/plan/templates?club_id=${currentClub?.id || ""}&operator_uid=${user.id}`
      );
      const list = res.data?.templates || [];
      setCoachTemplates(list);
      return list;
    } catch (err) {
      console.error("Failed to load coach templates:", err);
      return coachTemplates;
    } finally {
      setLoadingTemplates(false);
    }
  }

  // Preload the template library so the workbench can show it inline (no modal hunting)
  useEffect(() => {
    if (activeTab === "coach" && currentClub?.id && user?.id) {
      loadCoachTemplates();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, currentClub?.id, user?.id]);

  function syncTemplateEditorFields(tpl: any) {
    if (!tpl) return;
    setTemplateCustomDays(JSON.parse(JSON.stringify(tpl.days_template || [])));
    setTplEditGroupCode(tpl.group_code || "特训组");
    setTplEditShortName(tpl.short_name || tpl.name || "教练自定义模版");
    setTplEditCategory(tpl.category || "marathon");
    setTplEditTargetPb(tpl.target_pb_label || tpl.target_level || "");
    setTplEditIntensityBadge(tpl.intensity_badge || tpl.intensity_tag || "中高强度");
    setTplEditDescription(tpl.description || tpl.coach_review_note || "");
    setTplEditMacroRoadmap(tpl.macro_roadmap || "");
    const pz = tpl.pace_zones || {};
    setTplEditPaceEasy(pz.easy_pace || pz.easy || "");
    setTplEditPaceMarathon(pz.marathon_pace || pz.marathon || "");
    setTplEditPaceTempo(pz.threshold_pace || pz.tempo || "");
    setTplEditPaceInterval(pz.interval_pace || pz.interval || "");
    setTplEditPaceCore(pz.core_workout || pz.long_run || "");
  }

  async function openTemplateAssignModal(presetGroupId?: string, preselectStudentId?: string, categoryFilter: string = "all") {
    setShowTemplateAssignModal(true);
    setTemplateCategoryFilter(categoryFilter);
    setTemplateSearchQuery("");
    setTemplateMemberSearch("");
    setTemplateEditMode(false);
    setShowTemplateMetaEditor(false);
    const tplList = coachTemplates.length > 0 ? coachTemplates : await loadCoachTemplates();
    if (coachTemplates.length > 0) {
      // refresh silently in background (custom templates may have changed on another device)
      loadCoachTemplates();
    }
    const firstInCategory =
      categoryFilter !== "all" ? tplList.find((t: any) => getTemplateCategoryKey(t) === categoryFilter) : null;
    const targetId = presetGroupId || firstInCategory?.id || selectedTemplateId || "group_b_sub330";
    const tpl = tplList.find((t: any) => t.id === targetId) || tplList[0];
    setSelectedTemplateId(tpl?.id || targetId);
    if (tpl) {
      syncTemplateEditorFields(tpl);
    }
    setTemplateApplyScope("full_plan");
    if (preselectStudentId) {
      setSelectedMemberIdsForTemplate([preselectStudentId]);
      const preStu = (coachCockpit?.students || []).find((s: any) => s.user_id === preselectStudentId);
      setTemplateScaleFactor(preStu?.recommended_group?.recommended_scale || 1.0);
    } else if (tpl && coachCockpit?.students) {
      setTemplateScaleFactor(1.0);
      const recIds = (coachCockpit.students || [])
        .filter((s: any) => s.recommended_group?.template_id === tpl.id)
        .map((s: any) => s.user_id);
      setSelectedMemberIdsForTemplate(recIds);
    } else {
      setTemplateScaleFactor(1.0);
    }
  }

  function handleSelectTemplateGroup(tplId: string) {
    setSelectedTemplateId(tplId);
    setTemplateEditMode(false);
    const tpl = coachTemplates.find((t: any) => t.id === tplId);
    if (tpl) {
      syncTemplateEditorFields(tpl);
      const recIds = (coachCockpit?.students || [])
        .filter((s: any) => s.recommended_group?.template_id === tpl.id)
        .map((s: any) => s.user_id);
      setSelectedMemberIdsForTemplate(recIds);
    }
  }

  async function handleSaveOrCloneCustomTemplate(overwriteCurrent: boolean = false) {
    if (!user?.id || !activeTemplateObj || savingCustomTemplate) return;
    const shortNameTrim = tplEditShortName.trim();
    const groupCodeTrim = tplEditGroupCode.trim();
    if (!shortNameTrim || !groupCodeTrim) {
      alert("请填写模版组别代号与模版名称");
      return;
    }
    const computedWeeklyKm = Math.round(
      templateCustomDays.reduce((acc: number, d: any) => acc + (Number(d.distance_km) || 0), 0)
    );
    const computedDaysPerWeek = templateCustomDays.filter(
      (d: any) => d.workout_type !== "rest" && (Number(d.distance_km) || 0) > 0
    ).length;

    setSavingCustomTemplate(true);
    try {
      const payload: any = {
        club_id: currentClub?.id || "",
        operator_uid: user.id,
        template_id: overwriteCurrent && activeTemplateObj.is_custom ? activeTemplateObj.id : undefined,
        base_template_id: activeTemplateObj.id,
        group_code: groupCodeTrim,
        name: overwriteCurrent
          ? shortNameTrim
          : shortNameTrim === activeTemplateObj.short_name
          ? `${shortNameTrim} (教练定制版)`
          : shortNameTrim,
        short_name: overwriteCurrent
          ? shortNameTrim
          : shortNameTrim === activeTemplateObj.short_name
          ? `${shortNameTrim} (定制)`
          : shortNameTrim,
        category: tplEditCategory || "custom",
        target_level: tplEditTargetPb,
        intensity_tag: tplEditIntensityBadge,
        weekly_km: computedWeeklyKm || activeTemplateObj.weekly_km || 60,
        days_per_week: computedDaysPerWeek || activeTemplateObj.days_per_week || 5,
        macro_roadmap: tplEditMacroRoadmap,
        coach_review_note: tplEditDescription,
        pace_zones: {
          easy: tplEditPaceEasy,
          easy_pace: tplEditPaceEasy,
          marathon: tplEditPaceMarathon,
          marathon_pace: tplEditPaceMarathon,
          tempo: tplEditPaceTempo,
          threshold_pace: tplEditPaceTempo,
          interval: tplEditPaceInterval,
          interval_pace: tplEditPaceInterval,
          long_run: tplEditPaceCore,
          core_workout: tplEditPaceCore,
        },
        days_template: templateCustomDays,
      };
      const res = await apiClient.post("/api/coach/plan/templates", payload);
      const updatedList = res.data?.templates || [];
      const savedTpl = res.data?.template;
      if (updatedList.length > 0) {
        setCoachTemplates(updatedList);
      }
      if (savedTpl?.id) {
        setSelectedTemplateId(savedTpl.id);
        syncTemplateEditorFields(savedTpl);
      }
      setShowTemplateMetaEditor(false);
      alert(res.data?.message || "✅ 已成功保存为教练专属训练模版！");
    } catch (err: any) {
      alert(err.response?.data?.detail || "保存自定义模版失败");
    } finally {
      setSavingCustomTemplate(false);
    }
  }

  async function handleDeleteCustomTemplate(tplId: string) {
    if (!user?.id || !tplId) return;
    if (!confirm("确定要删除这个教练自定义训练模版吗？")) return;
    try {
      const res = await apiClient.delete(
        `/api/coach/plan/templates/${tplId}?club_id=${currentClub?.id || ""}&operator_uid=${user.id}`
      );
      const updatedList = res.data?.templates || [];
      setCoachTemplates(updatedList);
      const fallback = updatedList[0];
      if (fallback) {
        setSelectedTemplateId(fallback.id);
        syncTemplateEditorFields(fallback);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "删除自定义模版失败");
    }
  }

  async function fetchTemplateMultiWeekPreview(
    tplObj: any,
    weeksCnt: number = templateWeeksCount,
    scale: number = templateScaleFactor,
    canovaProg: boolean = templateCanovaProgression,
    baseDays?: any[]
  ) {
    if (!tplObj?.id) return;
    setLoadingTemplatePreview(true);
    try {
      const res = await apiClient.post("/api/coach/plan/assign-template", {
        club_id: currentClub?.id || "",
        operator_uid: user?.id || "coach_preview",
        template_id: tplObj.id,
        weeks_count: weeksCnt,
        scale_factor: scale,
        canova_progression: canovaProg,
        custom_days: baseDays && baseDays.length === 7 ? baseDays : tplObj.days_template,
        preview_only: true,
      });
      const wks =
        res.data?.preview_weeks ||
        res.data?.assigned_plans?.[0]?.plan?.schedule_data?.weeks ||
        [];
      if (wks.length > 0) {
        setTemplatePreviewWeeks(wks);
        setTemplateHasEditedWeeks(false);
        setEditingMatrixCell(null);
      }
    } catch (err) {
      console.error("Failed to fetch multi-week template preview:", err);
    } finally {
      setLoadingTemplatePreview(false);
    }
  }

  useEffect(() => {
    if (showTemplateAssignModal && activeTemplateObj?.id) {
      fetchTemplateMultiWeekPreview(
        activeTemplateObj,
        templateWeeksCount,
        templateScaleFactor,
        templateCanovaProgression,
        templateCustomDays.length === 7 ? templateCustomDays : activeTemplateObj.days_template
      );
      if (typeof templatePlanViewTab === "number" && templatePlanViewTab > templateWeeksCount) {
        setTemplatePlanViewTab("matrix");
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showTemplateAssignModal, activeTemplateObj?.id, templateWeeksCount, templateScaleFactor, templateCanovaProgression]);

  function handleUpdatePreviewWeekDay(weekIndex1Based: number, dayIdx0Based: number, patch: Record<string, any>) {
    setTemplatePreviewWeeks((prev) =>
      prev.map((wk: any, wIdx: number) => {
        const curWIdx = wk.week_index || wIdx + 1;
        if (curWIdx !== weekIndex1Based) return wk;
        const nextDays = (wk.days || []).map((d: any, dI: number) => {
          if (dI !== dayIdx0Based) return d;
          const merged = { ...d, ...patch };
          if (merged.workout_type === "rest") {
            merged.distance_km = 0;
          }
          return merged;
        });
        const totKm =
          Math.round(
            nextDays.reduce((acc: number, d: any) => acc + (d.workout_type === "rest" ? 0 : Number(d.distance_km) || 0), 0) * 10
          ) / 10;
        return {
          ...wk,
          days: nextDays,
          weekly_mileage_km: totKm,
          total_distance_km: totKm,
        };
      })
    );
    setTemplateHasEditedWeeks(true);
  }

  function handleScaleSinglePreviewWeek(weekIndex1Based: number, factor: number) {
    setTemplatePreviewWeeks((prev) =>
      prev.map((wk: any, wIdx: number) => {
        const curWIdx = wk.week_index || wIdx + 1;
        if (curWIdx !== weekIndex1Based) return wk;
        const nextDays = (wk.days || []).map((d: any) => {
          const raw = Number(d.distance_km) || 0;
          if (d.workout_type === "rest" || raw <= 0) return d;
          const scaled = Math.max(2, Math.round(raw * factor * 2) / 2);
          return { ...d, distance_km: scaled };
        });
        const totKm =
          Math.round(
            nextDays.reduce((acc: number, d: any) => acc + (d.workout_type === "rest" ? 0 : Number(d.distance_km) || 0), 0) * 10
          ) / 10;
        return {
          ...wk,
          days: nextDays,
          weekly_mileage_km: totKm,
          total_distance_km: totKm,
        };
      })
    );
    setTemplateHasEditedWeeks(true);
  }

  function handleApplyDayToAllPreviewWeeks(dayIdx0Based: number, srcDay: any) {
    setTemplatePreviewWeeks((prev) =>
      prev.map((wk: any) => {
        const nextDays = (wk.days || []).map((d: any, dI: number) => {
          if (dI !== dayIdx0Based) return d;
          return {
            ...d,
            workout_type: srcDay.workout_type,
            title: srcDay.title,
            distance_km: srcDay.workout_type === "rest" ? 0 : Number(srcDay.distance_km) || 0,
            target_pace: srcDay.target_pace,
            description: srcDay.description,
          };
        });
        const totKm =
          Math.round(
            nextDays.reduce((acc: number, d: any) => acc + (d.workout_type === "rest" ? 0 : Number(d.distance_km) || 0), 0) * 10
          ) / 10;
        return {
          ...wk,
          days: nextDays,
          weekly_mileage_km: totKm,
          total_distance_km: totKm,
        };
      })
    );
    setTemplateHasEditedWeeks(true);
  }

  function handleUpdateTemplateDayField(dayIdx: number, field: string, val: any) {
    setTemplateCustomDays((prev) =>
      prev.map((d, idx) => (idx === dayIdx ? { ...d, [field]: val } : d))
    );
  }

  function handleToggleMemberForTemplate(uid: string) {
    setSelectedMemberIdsForTemplate((prev) =>
      prev.includes(uid) ? prev.filter((id) => id !== uid) : [...prev, uid]
    );
  }

  async function handleAssignTemplateToMembers(asDraft: boolean, openPipelineAfter: boolean = false) {
    if (!currentClub?.id || !user?.id || !activeTemplateObj || selectedMemberIdsForTemplate.length === 0 || assigningTemplate) {
      return;
    }
    setAssigningTemplate(true);
    try {
      const res = await apiClient.post("/api/coach/plan/assign-template", {
        club_id: currentClub.id,
        operator_uid: user.id,
        template_id: activeTemplateObj.id,
        target_user_ids: selectedMemberIdsForTemplate,
        apply_scope: templateApplyScope,
        weeks_count: templateWeeksCount,
        canova_progression: templateCanovaProgression,
        as_draft: asDraft,
        scale_factor: templateScaleFactor,
        custom_days: templateCustomDays,
        custom_weeks:
          templateApplyScope === "full_plan" && templatePreviewWeeks.length > 0
            ? templatePreviewWeeks
            : undefined,
      });
      const assignedIds = new Set(selectedMemberIdsForTemplate);
      setShowTemplateAssignModal(false);
      await loadClubDetails(currentClub.id, user.id);

      if (openPipelineAfter) {
        if (asDraft) {
          setCoachPlanFilter("draft_pending");
        }
        const firstAssigned =
          (coachCockpit?.students || []).find((s: any) => assignedIds.has(s.user_id)) ||
          sortedCoachStudents[0];
        if (firstAssigned) {
          setSelectedStudentForPlan(firstAssigned);
        }
      } else {
        alert(res.data?.message || "已成功批量分配组别训练模版！");
      }
      await loadClubPlanBatches(currentClub.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "分配训练模版失败，请稍后重试");
    } finally {
      setAssigningTemplate(false);
    }
  }

  // Batch History & 1-Click Rollback States
  const [showBatchHistoryPanel, setShowBatchHistoryPanel] = useState(false);
  const [clubPlanBatches, setClubPlanBatches] = useState<any[]>([]);
  const [loadingClubBatches, setLoadingClubBatches] = useState(false);
  const [rollingBackBatchId, setRollingBackBatchId] = useState<string | null>(null);
  const [rollingBackUserUid, setRollingBackUserUid] = useState<string | null>(null);
  const [publishingDraftUid, setPublishingDraftUid] = useState<string | null>(null);

  async function loadClubPlanBatches(cid?: string) {
    const effClubId = cid || currentClub?.id;
    if (!effClubId) return;
    setLoadingClubBatches(true);
    try {
      const res = await apiClient.get(`/api/coach/plan/club-batches?club_id=${effClubId}&limit=15`);
      if (res.data?.batches) {
        setClubPlanBatches(res.data.batches);
      }
    } catch (err) {
      console.error("Failed to load club plan batches:", err);
    } finally {
      setLoadingClubBatches(false);
    }
  }

  async function handleRollbackClubBatch(batchId: string) {
    if (!batchId || !currentClub?.id || !user?.id || rollingBackBatchId) return;
    setRollingBackBatchId(batchId);
    try {
      const res = await apiClient.post(`/api/coach/plan/club-batches/${batchId}/rollback`, {
        operator_uid: user.id,
      });
      alert(res.data?.message || "✅ 已整批撤回该次课表派发，所有队员原课表已恢复！");
      await loadClubDetails(currentClub.id, user.id);
      await loadClubPlanBatches(currentClub.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "整批撤回失败，请稍后重试");
    } finally {
      setRollingBackBatchId(null);
    }
  }

  async function handleQuickRollbackStudentPlan(
    student: any,
    opts?: { discardDraftOnly?: boolean; backupId?: string; targetPlanId?: string }
  ) {
    if (!student?.user_id || !currentClub?.id || !user?.id || rollingBackUserUid) return;
    const pInfo = student.plan_info || {};
    const confirmMsg = opts?.discardDraftOnly
      ? `确认撤回并删除【${student.display_name}】的待审草案「${pInfo.draft_plan_title || "新草案"}」吗？\n（队员当前正在执行的「${pInfo.active_plan_title || pInfo.title || "原计划"}」将保持完好不变）`
      : `确认将【${student.display_name}】的训练计划回退到上一版本「${pInfo.latest_backup?.previous_plan_title || "原训练计划"}」吗？\n（队员已完成的日常打卡数据将 100% 保留）`;
    if (!window.confirm(confirmMsg)) return;

    setRollingBackUserUid(student.user_id);
    try {
      const res = await apiClient.post(`/api/coach/plan/user/${student.user_id}/rollback`, {
        operator_uid: user.id,
        discard_draft_only: Boolean(opts?.discardDraftOnly),
        backup_id: opts?.backupId,
        target_plan_id: opts?.targetPlanId,
      });
      alert(res.data?.message || "✅ 已成功回退队员训练计划！");
      await loadClubDetails(currentClub.id, user.id);
      await loadClubPlanBatches(currentClub.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "回退失败，请稍后重试");
    } finally {
      setRollingBackUserUid(null);
    }
  }

  async function handleQuickPublishStudentDraft(student: any) {
    const pInfo = student?.plan_info || {};
    const draftId = pInfo.draft_plan_id;
    if (!draftId || !currentClub?.id || !user?.id || publishingDraftUid) return;
    const hasActive = pInfo.has_active_plan;
    const confirmMsg = hasActive
      ? `🚀 确认将【${student.display_name}】的待审草案「${pInfo.draft_plan_title}」正式发布并生效吗？\n\n• 原生效计划「${pInfo.active_plan_title || pInfo.title}」将自动归档备份（历史打卡 100% 合并保留），之后仍可随时一键切回。`
      : `🚀 确认将【${student.display_name}】的待审草案「${pInfo.draft_plan_title}」正式发布给队员吗？`;
    if (!window.confirm(confirmMsg)) return;

    setPublishingDraftUid(student.user_id);
    try {
      await apiClient.post(`/api/coach/plan/${draftId}/publish`, {
        operator_uid: user.id,
        sync_to_goals: true,
      });
      await loadClubDetails(currentClub.id, user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "发布草案失败，请稍后重试");
    } finally {
      setPublishingDraftUid(null);
    }
  }

  function openClubReportModal() {
    setReportPeriodType("week");
    setReportPeriodOffset(0);
    setReportTrailMode("include");
    setShowReportModal(true);
    fetchClubReport("week", 0, "include");
  }

  function handleSwitchReportPeriod(type: "week" | "month") {
    setReportPeriodType(type);
    setReportPeriodOffset(0);
    fetchClubReport(type, 0, reportTrailMode);
  }

  function handleSwitchReportOffset(offset: number) {
    setReportPeriodOffset(offset);
    fetchClubReport(reportPeriodType, offset, reportTrailMode);
  }

  function handleSwitchReportTrailMode(mode: "include" | "exclude_pace" | "exclude_all") {
    setReportTrailMode(mode);
    fetchClubReport(reportPeriodType, reportPeriodOffset, mode);
  }

  function handleCopyReportText() {
    if (!reportData?.forward_text) return;
    navigator.clipboard.writeText(reportData.forward_text);
    setCopiedReportText(true);
    setTimeout(() => setCopiedReportText(false), 2500);
  }

  function handleExportReportFile() {
    if (!currentClub?.id || !user?.id) return;
    let url = `/api/team/${currentClub.id}/reports/export?operator_uid=${user.id}&period_type=${reportPeriodType}&trail_mode=${reportTrailMode}`;
    if (reportPeriodOffset === -1) {
      const now = new Date();
      if (reportPeriodType === "week") {
        const d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const target = new Date(d.valueOf());
        const dayNr = (d.getDay() + 6) % 7;
        target.setDate(target.getDate() - dayNr + 3);
        const firstThursday = target.valueOf();
        target.setMonth(0, 1);
        if (target.getDay() !== 4) {
          target.setMonth(0, 1 + ((4 - target.getDay()) + 7) % 7);
        }
        const weekNum = 1 + Math.ceil((firstThursday - target.valueOf()) / 604800000);
        url += `&year=${d.getFullYear()}&period_index=${weekNum}`;
      } else {
        const prevMonth = now.getMonth() === 0 ? 12 : now.getMonth();
        const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
        url += `&year=${prevYear}&period_index=${prevMonth}`;
      }
    }
    window.open(url, "_blank");
  }

  function drawRoundedRectWeb(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number, fillStyle?: string, strokeStyle?: string) {
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.arcTo(x + width, y, x + width, y + radius, radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.arcTo(x + width, y + height, x + width - radius, y + height, radius);
    ctx.lineTo(x + radius, y + height);
    ctx.arcTo(x, y + height, x, y + height - radius, radius);
    ctx.lineTo(x, y + radius);
    ctx.arcTo(x, y, x + radius, y, radius);
    ctx.closePath();
    if (fillStyle) {
      ctx.fillStyle = fillStyle;
      ctx.fill();
    }
    if (strokeStyle) {
      ctx.strokeStyle = strokeStyle;
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawWrappedTextWeb(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number, lineHeight: number, maxLines: number = 5) {
    let line = "";
    let lineCount = 0;
    for (let i = 0; i < text.length; i++) {
      const testLine = line + text[i];
      if (ctx.measureText(testLine).width > maxWidth && i > 0) {
        ctx.fillText(line, x, y);
        line = text[i];
        y += lineHeight;
        lineCount++;
        if (lineCount >= maxLines - 1) {
          const remaining = text.substring(i);
          let lastLine = "";
          const suffix = text.startsWith("“") ? "…”" : "...";
          for (let j = 0; j < remaining.length; j++) {
            if (ctx.measureText(lastLine + remaining[j] + suffix).width > maxWidth) {
              break;
            }
            lastLine += remaining[j];
          }
          ctx.fillText(lastLine + suffix, x, y);
          return y + lineHeight;
        }
      } else {
        line = testLine;
      }
    }
    ctx.fillText(line, x, y);
    return y + lineHeight;
  }

  const handleDownloadPosterImage = async () => {
    if (!reportData) return;
    const canvas = document.createElement("canvas");
    const W = 750;
    const H = 1380;
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rep = reportData;
    const isLight =
      typeof document !== "undefined" &&
      document.documentElement.classList.contains("theme-light");

    // Background gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    if (isLight) {
      bgGrad.addColorStop(0, "#F8FAFC");
      bgGrad.addColorStop(0.5, "#FFFFFF");
      bgGrad.addColorStop(1, "#F1F5F9");
    } else {
      bgGrad.addColorStop(0, "#0e1017");
      bgGrad.addColorStop(0.5, "#131620");
      bgGrad.addColorStop(1, "#0a0b10");
    }
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // Outer border
    drawRoundedRectWeb(
      ctx,
      16,
      16,
      W - 32,
      H - 32,
      24,
      undefined,
      isLight ? "rgba(217, 119, 6, 0.3)" : "rgba(255, 215, 0, 0.25)"
    );

    // Header
    drawRoundedRectWeb(
      ctx,
      40,
      42,
      190,
      42,
      21,
      isLight ? "rgba(245, 158, 11, 0.14)" : "rgba(255, 215, 0, 0.15)",
      isLight ? "rgba(217, 119, 6, 0.4)" : "rgba(255, 215, 0, 0.4)"
    );
    ctx.font = "bold 20px sans-serif";
    ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
    ctx.fillText("👑 跑团专属战报", 52, 71);

    ctx.font = "900 36px sans-serif";
    ctx.fillStyle = isLight ? "#0f172a" : "#ffffff";
    ctx.fillText(rep.club_name || "跑团战报", 40, 130);

    ctx.font = "bold 22px sans-serif";
    ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
    const trailTagCanvas =
      rep.trail_mode === "exclude_pace"
        ? " · 仅去除越野配速"
        : rep.trail_mode === "exclude_all"
        ? " · 去除越野跑量与配速"
        : "";
    ctx.fillText(`${rep.period_label} · ${rep.date_range_str}${trailTagCanvas}`, 40, 172);

    ctx.beginPath();
    ctx.moveTo(40, 195);
    ctx.lineTo(W - 40, 195);
    ctx.strokeStyle = isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.12)";
    ctx.stroke();

    // Hero Total Mileage
    drawRoundedRectWeb(
      ctx,
      40,
      215,
      W - 80,
      155,
      20,
      isLight ? "#FFF7ED" : "#181b26",
      isLight ? "rgba(252, 76, 2, 0.3)" : "rgba(252, 76, 2, 0.35)"
    );
    ctx.font = "bold 22px sans-serif";
    ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
    ctx.fillText("全团累计奔跑总里程", 64, 252);

    ctx.font = "900 72px monospace";
    ctx.fillStyle = "#fc4c02";
    ctx.fillText(`${rep.total_distance_km}`, 64, 326);

    const kmWidth = ctx.measureText(`${rep.total_distance_km}`).width;
    ctx.font = "900 30px sans-serif";
    ctx.fillStyle = isLight ? "#b45309" : "#f59e0b";
    ctx.fillText("KM", 64 + kmWidth + 12, 324);

    ctx.font = "20px sans-serif";
    ctx.fillStyle = isLight ? "#64748b" : "#71717a";
    ctx.fillText("汇聚全员热血汗水 · 每一步都在突破极限", 64, 355);

    // 4-Metrics Grid
    const gW = (W - 80 - 18) / 2;
    const gH = 92;
    const metricBg = isLight ? "#FFFFFF" : "#151722";
    const metricStroke = isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.08)";
    const metricLabel = isLight ? "#64748b" : "#9ca3af";
    const metricVal = isLight ? "#0f172a" : "#ffffff";

    drawRoundedRectWeb(ctx, 40, 390, gW, gH, 16, metricBg, metricStroke);
    ctx.font = "20px sans-serif";
    ctx.fillStyle = metricLabel;
    ctx.fillText("队员出勤率", 56, 422);
    ctx.font = "bold 30px sans-serif";
    ctx.fillStyle = metricVal;
    ctx.fillText(`${rep.attendance_rate_pct}%`, 56, 462);
    ctx.font = "18px sans-serif";
    ctx.fillStyle = isLight ? "#64748b" : "#6b7280";
    ctx.fillText(`(${rep.active_members_count}/${rep.total_members_count}人)`, 160, 460);

    drawRoundedRectWeb(ctx, 40 + gW + 18, 390, gW, gH, 16, metricBg, metricStroke);
    ctx.font = "20px sans-serif";
    ctx.fillStyle = metricLabel;
    ctx.fillText("全团平均配速", 56 + gW + 18, 422);
    ctx.font = "bold 30px monospace";
    ctx.fillStyle = metricVal;
    ctx.fillText(`${rep.avg_pace_str}`, 56 + gW + 18, 462);

    drawRoundedRectWeb(ctx, 40, 498, gW, gH, 16, metricBg, metricStroke);
    ctx.font = "20px sans-serif";
    ctx.fillStyle = metricLabel;
    ctx.fillText("累计爬升克服", 56, 530);
    ctx.font = "bold 30px sans-serif";
    ctx.fillStyle = metricVal;
    ctx.fillText(`+${rep.total_elevation_gain_m}m`, 56, 570);

    drawRoundedRectWeb(ctx, 40 + gW + 18, 498, gW, gH, 16, metricBg, metricStroke);
    ctx.font = "20px sans-serif";
    ctx.fillStyle = metricLabel;
    ctx.fillText("累计打卡总人次", 56 + gW + 18, 530);
    ctx.font = "bold 30px sans-serif";
    ctx.fillStyle = metricVal;
    ctx.fillText(`${rep.total_activities_count} 次`, 56 + gW + 18, 570);

    // Podium Top 3
    drawRoundedRectWeb(
      ctx,
      40,
      606,
      W - 80,
      235,
      20,
      isLight ? "#FFFBEB" : "#151722",
      isLight ? "rgba(217, 119, 6, 0.3)" : "rgba(255, 215, 0, 0.3)"
    );
    ctx.font = "bold 24px sans-serif";
    ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
    ctx.fillText("🏆 荣誉榜单 Top 3", 60, 642);

    const podium = rep.podium || [];
    const medals = ["🥇 冠军", "🥈 亚军", "🥉 季军"];
    const medalBgs = isLight
      ? ["#FFFFFF", "#FFFFFF", "#FFFFFF"]
      : ["rgba(255, 215, 0, 0.12)", "rgba(192, 192, 192, 0.10)", "rgba(205, 127, 50, 0.10)"];
    const medalStrokes = isLight
      ? ["rgba(217, 119, 6, 0.35)", "rgba(100, 116, 139, 0.25)", "rgba(180, 83, 9, 0.28)"]
      : ["rgba(255, 215, 0, 0.35)", "rgba(192, 192, 192, 0.3)", "rgba(205, 127, 50, 0.3)"];

    for (let i = 0; i < 3; i++) {
      const pY = 660 + i * 55;
      if (podium[i]) {
        drawRoundedRectWeb(ctx, 60, pY, W - 120, 48, 12, medalBgs[i], medalStrokes[i]);
        ctx.font = "bold 22px sans-serif";
        ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
        ctx.fillText(medals[i], 76, pY + 32);

        ctx.font = "bold 22px sans-serif";
        ctx.fillStyle = metricVal;
        ctx.fillText(podium[i].display_name || "跑者", 185, pY + 32);

        ctx.font = "900 22px monospace";
        ctx.fillStyle = "#fc4c02";
        ctx.fillText(`${podium[i].distance_km} km`, W - 250, pY + 32);

        ctx.font = "20px monospace";
        ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
        ctx.fillText(podium[i].avg_pace_str || "—", W - 145, pY + 32);
      }
    }

    // Highlights
    const hY = 858;
    const hW = (W - 80 - 18) / 2;
    if (rep.hardcore_runner) {
      drawRoundedRectWeb(
        ctx,
        40,
        hY,
        hW,
        82,
        14,
        isLight ? "#F0F9FF" : "#151722",
        isLight ? "rgba(2, 132, 199, 0.25)" : "rgba(56, 189, 248, 0.25)"
      );
      ctx.font = "bold 18px sans-serif";
      ctx.fillStyle = isLight ? "#0369a1" : "#38bdf8";
      ctx.fillText("🌟 毅力先锋", 54, hY + 28);
      ctx.font = "bold 20px sans-serif";
      ctx.fillStyle = metricVal;
      ctx.fillText(`${rep.hardcore_runner.display_name}`, 54, hY + 54);
      ctx.font = "16px sans-serif";
      ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
      ctx.fillText(`打卡 ${rep.hardcore_runner.runs_count} 次 · ${rep.hardcore_runner.distance_km}km`, 54, hY + 74);
    }
    if (rep.longest_run) {
      drawRoundedRectWeb(
        ctx,
        40 + hW + 18,
        hY,
        hW,
        82,
        14,
        isLight ? "#F0F9FF" : "#151722",
        isLight ? "rgba(2, 132, 199, 0.25)" : "rgba(56, 189, 248, 0.25)"
      );
      ctx.font = "bold 18px sans-serif";
      ctx.fillStyle = isLight ? "#0369a1" : "#38bdf8";
      ctx.fillText("🚀 最长突破", 54 + hW + 18, hY + 28);
      ctx.font = "bold 20px sans-serif";
      ctx.fillStyle = metricVal;
      ctx.fillText(`${rep.longest_run.runner_name}`, 54 + hW + 18, hY + 54);
      ctx.font = "16px sans-serif";
      ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
      ctx.fillText(`单次 ${rep.longest_run.distance_km}km · ${rep.longest_run.avg_pace_str}`, 54 + hW + 18, hY + 74);
    }

    // Canova Quote Box
    const cY = 955;
    drawRoundedRectWeb(
      ctx,
      40,
      cY,
      W - 80,
      225,
      18,
      isLight ? "#FAF5FF" : "#181624",
      isLight ? "rgba(147, 51, 234, 0.28)" : "rgba(191, 90, 242, 0.35)"
    );
    ctx.font = "bold 22px sans-serif";
    ctx.fillStyle = isLight ? "#6d28d9" : "#bf5af2";
    ctx.fillText("💡 Renato Canova 科学耐力团队复盘", 58, cY + 34);

    ctx.font = "italic 17px sans-serif";
    ctx.fillStyle = isLight ? "#1e293b" : "#d1d5db";
    drawWrappedTextWeb(ctx, `“${rep.canova_critique}”`, 58, cY + 68, W - 116, 26, 5);

    // Footer with Pure Mini-Program QR Code (no club invite)
    const fY = 1200;
    drawRoundedRectWeb(
      ctx,
      40,
      fY,
      W - 80,
      145,
      20,
      isLight ? "#FFFFFF" : "#121520",
      isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.1)"
    );

    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = "#fc4c02";
    ctx.fillText("🏃 万跑跑团助手 · 跑团官方认证战报", 64, fY + 42);

    ctx.font = "900 24px sans-serif";
    ctx.fillStyle = metricVal;
    ctx.fillText("微信扫码打开万跑跑团助手小程序", 64, fY + 78);

    ctx.font = "16px sans-serif";
    ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
    ctx.fillText("万跑跑团助手 · 科学耐力训练与跑团系统 · 官方认证战报", 64, fY + 112);

    const qrSrc = rep.qrcode_base64
      ? `data:image/jpeg;base64,${rep.qrcode_base64}`
      : rep.qrcode_url || "";
    if (qrSrc) {
      await new Promise<void>((resolve) => {
        const qrImg = new Image();
        qrImg.crossOrigin = "anonymous";
        qrImg.onload = () => {
          const qrBoxX = W - 40 - 134;
          const qrBoxY = fY + 14;
          drawRoundedRectWeb(ctx, qrBoxX, qrBoxY, 118, 118, 14, "#ffffff");
          ctx.drawImage(qrImg, qrBoxX + 6, qrBoxY + 6, 106, 106);
          resolve();
        };
        qrImg.onerror = () => resolve();
        qrImg.src = qrSrc;
      });
    } else {
      drawRoundedRectWeb(
        ctx,
        W - 160,
        fY + 48,
        100,
        44,
        12,
        isLight ? "rgba(245, 158, 11, 0.14)" : "rgba(255, 215, 0, 0.15)",
        isLight ? "rgba(217, 119, 6, 0.4)" : "rgba(255, 215, 0, 0.4)"
      );
      ctx.font = "bold 18px sans-serif";
      ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
      ctx.fillText("官方战报", W - 146, fY + 76);
    }

    // Download PNG
    const dataUrl = canvas.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `${rep.club_name || "跑团"}_${rep.period_label || "战报"}_海报.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  async function loadUserClubs(uid: string) {
    setLoading(true);
    try {
      const res = await apiClient.get(`/api/team/my-clubs/${uid}`);
      const clubList = res.data?.clubs || [];
      setClubs(clubList);

      if (clubList.length > 0) {
        let primary = clubList[0];
        const savedClubId = typeof window !== "undefined" ? localStorage.getItem("rgm_active_club_id") : null;
        if (savedClubId) {
          const matched = clubList.find((c: any) => c.id === savedClubId);
          if (matched) primary = matched;
        }
        if (
          coachWorkbenchMode &&
          primary.role !== "owner" &&
          primary.role !== "coach" &&
          primary.owner_id !== uid
        ) {
          const firstCoached = clubList.find(
            (c: any) => c.role === "owner" || c.role === "coach" || c.owner_id === uid
          );
          if (firstCoached) primary = firstCoached;
        }
        setCurrentClub(primary);
        setCurrentRole(primary.role || "member");
        if (typeof window !== "undefined") {
          localStorage.setItem("rgm_active_club_id", primary.id);
        }
        if (primary.is_access_suspended) {
          setClubSuspended(true);
          setClubSuspensionReason(primary.suspension_reason || "");
        } else {
          setClubSuspended(false);
          setClubSuspensionReason("");
          loadClubDetails(primary.id, uid);
        }
      } else {
        if (typeof window !== "undefined") {
          localStorage.removeItem("rgm_active_club_id");
        }
        setCurrentClub(null);
        setCurrentRole("member");
        setClubSuspended(false);
        setClubSuspensionReason("");
        setDashboardMetrics(null);
        setLeaderboard([]);
        setMembers([]);
        setCoachCockpit(null);
        setEvents([]);
        setFeed([]);
        setFeedTotal(0);
        setHasMoreFeed(false);
        loadUnaffiliatedPeers(uid);
      }
    } catch (e) {
      console.error("Fetch user clubs error:", e);
    } finally {
      setLoading(false);
    }
  }

  async function loadUnaffiliatedPeers(uid?: string) {
    const effUid = uid || user?.id;
    if (!effUid) return;
    try {
      const res = await apiClient.get(`/api/team/unaffiliated-members?user_id=${encodeURIComponent(effUid)}`);
      setUnaffiliatedPeers(res.data?.members || []);
      setUnaffiliatedPeersSummary(res.data?.summary || null);
    } catch (e) {
      console.warn("Load unaffiliated peers error:", e);
    }
  }

  async function handleRemindMemberSetup(targetUid: string, displayName: string) {
    if (!currentClub?.id || !user?.id || remindingMemberUid) return;
    setRemindingMemberUid(targetUid);
    try {
      const res = await apiClient.post(`/api/team/${currentClub.id}/remind-member`, {
        operator_uid: user.id,
        target_uid: targetUid,
      });
      alert(res.data?.message || `已向【${displayName}】发送绑定手表与设定目标提醒！`);
    } catch (e: any) {
      alert(e.response?.data?.detail || "发送提醒失败，请稍后重试");
    } finally {
      setRemindingMemberUid(null);
    }
  }

  async function loadClubDetails(clubId: string, uid?: string) {
    const effUid = uid || user?.id;
    if (!effUid) return;
    try {
      const [dashRes, lbRes, memRes, coachRes, evtRes, feedRes] = await Promise.all([
        apiClient.get(`/api/team/${clubId}/dashboard?user_id=${effUid}`),
        apiClient.get(`/api/team/${clubId}/leaderboard?user_id=${effUid}`),
        apiClient.get(`/api/team/${clubId}/members?user_id=${effUid}`),
        apiClient.get(`/api/team/${clubId}/coach-cockpit?coach_uid=${effUid}&user_id=${effUid}`),
        apiClient.get(`/api/team/${clubId}/events?user_id=${effUid}`),
        apiClient.get(`/api/team/${clubId}/feed?uid=${effUid}&user_id=${effUid}`),
      ]);

      setDashboardMetrics(dashRes.data?.metrics || null);
      setLeaderboard(lbRes.data?.leaderboard || []);
      setMembers(memRes.data?.members || []);
      setCoachCockpit(coachRes.data || null);
      setEvents(evtRes.data?.events || []);
      const newFeed = feedRes.data?.feed || [];
      setFeed(newFeed);
      setFeedTotal(feedRes.data?.total ?? newFeed.length);
      setHasMoreFeed(feedRes.data?.has_more ?? false);
      setIsFeedExpanded(false);
      setFeedMonthInfo({
        month_total: feedRes.data?.month_total ?? newFeed.length,
        month_label: feedRes.data?.month_label || "当月",
        is_current_month: feedRes.data?.is_current_month ?? true
      });
      setClubSuspended(false);
      setClubSuspensionReason("");
      try {
        const nmRes = await apiClient.get(`/api/team/${clubId}/new-members?user_id=${encodeURIComponent(effUid)}`);
        setNewMembersStatus(nmRes.data?.members || []);
        setNewMembersSummary(nmRes.data?.summary || null);
      } catch (nmErr) {
        console.warn("Load new members status error:", nmErr);
      }
      try {
        const mRes = await apiClient.get(`/api/team/mentorship/overview?user_id=${effUid}`);
        setMentorshipOverview(mRes.data || null);
      } catch (mErr) {
        console.warn("Mentorship overview load error:", mErr);
      }
    } catch (e: any) {
      console.error("Load club details error:", e);
      if (e?.response?.status === 403) {
        setClubSuspended(true);
        if (e.response?.data?.detail) {
          setClubSuspensionReason(e.response.data.detail);
        }
      }
    }
  }

  async function handleLoadMoreFeed() {
    if (!currentClub?.id || loadingMoreFeed || !hasMoreFeed) return;
    const effUid = user?.id;
    if (!effUid) return;

    setLoadingMoreFeed(true);
    try {
      const res = await apiClient.get(
        `/api/team/${currentClub.id}/feed?uid=${effUid}&user_id=${effUid}&scope=all&limit=20&offset=${feed.length}`
      );
      const moreItems = res.data?.feed || [];
      setFeed((prev) => [...prev, ...moreItems]);
      setFeedTotal(res.data?.total ?? (feed.length + moreItems.length));
      setHasMoreFeed(res.data?.has_more ?? false);
      setIsFeedExpanded(true);
    } catch (e) {
      console.error("Load more feed error:", e);
    } finally {
      setLoadingMoreFeed(false);
    }
  }

  function handleSwitchClub(club: any) {
    setCurrentClub(club);
    setCurrentRole(club.role || "member");
    if (typeof window !== "undefined") {
      localStorage.setItem("rgm_active_club_id", club.id);
    }
    if (club.is_access_suspended) {
      setClubSuspended(true);
      setClubSuspensionReason(club.suspension_reason || "");
    } else {
      setClubSuspended(false);
      setClubSuspensionReason("");
      loadClubDetails(club.id);
    }
  }

  const [replyTargets, setReplyTargets] = useState<Record<string, any>>({});

  function getCommentThreads(comments?: any[]) {
    if (!comments || !Array.isArray(comments) || comments.length === 0) return [];
    const rootMap = new Map<string, any>();
    const roots: any[] = [];
    for (const c of comments) {
      if (!c.parent_id) {
        const node = { ...c, replies: [] };
        rootMap.set(c.id, node);
        roots.push(node);
      }
    }
    for (const c of comments) {
      if (c.parent_id) {
        const parent = rootMap.get(c.parent_id);
        if (parent) {
          parent.replies.push(c);
        } else {
          const orphanNode = { ...c, replies: [] };
          rootMap.set(c.id, orphanNode);
          roots.push(orphanNode);
        }
      }
    }
    return roots;
  }

  async function handleToggleLike(activityId: string) {
    if (!user?.id) return;
    try {
      const res = await apiClient.post(`/api/team/activities/${activityId}/like`, {
        user_id: user.id,
      });
      setFeed((prev) =>
        prev.map((item) => {
          if (item.id === activityId) {
            return {
              ...item,
              has_liked: res.data.liked,
              likes_count: res.data.likes_count,
              likers: Array.isArray(res.data.likers) ? res.data.likers : item.likers,
            };
          }
          return item;
        })
      );
    } catch (e) {
      console.error("Like error:", e);
    }
  }

  async function handlePostComment(activityId: string) {
    const content = (commentInputs[activityId] || "").trim();
    if (!content || !user?.id) return;
    setSubmittingComment((prev) => ({ ...prev, [activityId]: true }));
    try {
      const authorName = userProfile?.display_name || user?.user_metadata?.display_name || "跑友";
      const authorAvatar = userProfile?.avatar_url || user?.user_metadata?.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80";
      const replyTarget = replyTargets[activityId];
      const payload: any = {
        user_id: user.id,
        content: content,
        author_name: authorName,
        author_avatar: authorAvatar,
      };
      if (replyTarget) {
        payload.parent_id = replyTarget.parent_id || replyTarget.id;
        payload.reply_to_user_id = replyTarget.user_id;
        payload.reply_to_name = replyTarget.author_name;
      }
      const res = await apiClient.post(`/api/team/activities/${activityId}/comments`, payload);

      const newCmt = res.data.comment;
      setFeed((prev) =>
        prev.map((item) => {
          if (item.id === activityId) {
            return {
              ...item,
              comments: [...(item.comments || []), newCmt],
            };
          }
          return item;
        })
      );
      setCommentInputs((prev) => ({ ...prev, [activityId]: "" }));
      setReplyTargets((prev) => ({ ...prev, [activityId]: null }));
    } catch (e) {
      alert("评论发布失败");
    } finally {
      setSubmittingComment((prev) => ({ ...prev, [activityId]: false }));
    }
  }

  async function handleDeleteComment(activityId: string, commentId: string) {
    if (!user?.id) return;
    try {
      await apiClient.delete(`/api/team/activities/${activityId}/comments/${commentId}?user_id=${user.id}`);
      setFeed((prev) =>
        prev.map((item) => {
          if (item.id === activityId) {
            return {
              ...item,
              comments: (item.comments || []).filter((c: any) => c.id !== commentId && c.parent_id !== commentId),
            };
          }
          return item;
        })
      );
    } catch (e) {
      alert("删除失败");
    }
  }

  async function handleJoinClub(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteCodeInput.trim() || !user?.id) return;
    try {
      const res = await apiClient.post("/api/team/join", {
        user_id: user.id,
        invite_code: inviteCodeInput.trim().toUpperCase(),
        privacy_consent: true,
      });
      alert(res.data.message || "加入跑团成功！");
      setShowJoinModal(false);
      setInviteCodeInput("");
      await loadUserClubs(user.id);
      await loadAllClubs(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加入失败，请核对邀请码！");
    }
  }

  async function handleUpdateMemberRole(targetUid: string, role: string) {
    if (!currentClub || !user?.id) return;
    try {
      await apiClient.post(`/api/team/${currentClub.id}/role`, {
        operator_uid: user.id,
        target_uid: targetUid,
        role: role,
      });
      alert(`已成功将该成员设为【${role === "coach" ? "认证教练" : role === "owner" ? "团长" : "普通跑者"}】`);
      loadClubDetails(currentClub.id);
    } catch (e: any) {
      alert("操作失败");
    }
  }

  function handleRemoveMember(targetUid: string, displayName: string) {
    if (!currentClub) return;
    const mObj =
      members.find((m: any) => m.user_id === targetUid) ||
      newMembersStatus.find((m: any) => m.user_id === targetUid) || {
        user_id: targetUid,
        display_name: displayName || "该成员",
        role: "member",
      };
    setRemoveMemberTarget(mObj);
    setRemoveMemberChecked(false);
    setRemoveMemberCountdown(3);
  }

  async function confirmRemoveMemberExecution() {
    if (!currentClub || !removeMemberTarget || !removeMemberChecked || removeMemberCountdown > 0 || removingMemberLoading) {
      return;
    }
    const targetUid = removeMemberTarget.user_id;
    const displayName = removeMemberTarget.display_name || "该成员";
    setRemovingMemberLoading(true);
    try {
      await apiClient.delete(
        `/api/team/${currentClub.id}/members/${encodeURIComponent(targetUid)}?operator_uid=${encodeURIComponent(user?.id || "")}`
      );
      setRemoveMemberTarget(null);
      setRemoveMemberChecked(false);
      alert(`已成功将【${displayName}】移出跑团`);
      await loadClubDetails(currentClub.id, user?.id);
    } catch (e: any) {
      alert(e.response?.data?.detail || "移除成员失败");
    } finally {
      setRemovingMemberLoading(false);
    }
  }

  function openLeaveClubModal() {
    if (!currentClub || currentClub.is_virtual_unaffiliated) return;
    if (currentRole === "owner") {
      alert(
        `您当前是【${currentClub.name}】的跑团团长。\n\n为防止跑团群龙无首，请先在「👥 跑团成员与管理」中将团长身份移交给其他成员后再退出；若需停办跑团，可在底部选择解散跑团。`
      );
      return;
    }
    setLeaveClubChecked(false);
    setLeaveClubCountdown(3);
    setShowLeaveClubModal(true);
  }

  async function confirmLeaveClubExecution() {
    if (!currentClub || !user?.id || !leaveClubChecked || leaveClubCountdown > 0 || leavingClubLoading) {
      return;
    }
    const leavingClubName = currentClub.name;
    const leavingClubId = currentClub.id;
    setLeavingClubLoading(true);
    try {
      await apiClient.post(`/api/team/${encodeURIComponent(leavingClubId)}/leave`, {
        user_id: user.id,
      });
      setShowLeaveClubModal(false);
      setLeaveClubChecked(false);
      if (typeof window !== "undefined") {
        const saved = localStorage.getItem("rgm_active_club_id");
        if (saved === leavingClubId) {
          localStorage.removeItem("rgm_active_club_id");
        }
      }
      alert(`您已成功退出跑团【${leavingClubName}】，个人运动历史与数据档案 100% 完整保留！`);
      await loadUserClubs(user.id);
      await loadAllClubs(user.id);
    } catch (e: any) {
      alert(e.response?.data?.detail || "退出跑团失败");
    } finally {
      setLeavingClubLoading(false);
    }
  }

  async function handleTransferOwner(targetUid: string, displayName: string) {
    if (!currentClub || !user?.id) return;
    if (!confirm(`确定要将跑团【${currentClub.name}】的团长身份移交给【${displayName}】吗？移交后您将转为认证教练身份。`)) return;
    try {
      await apiClient.post(`/api/team/${currentClub.id}/role`, {
        operator_uid: user.id,
        target_uid: targetUid,
        role: "owner",
      });
      alert(`已成功将团长身份移交给【${displayName}】！`);
      loadUserClubs(user.id);
    } catch (e: any) {
      alert(e.response?.data?.detail || "移交团长失败");
    }
  }

  function formatPb(seconds: any) {
    if (!seconds) return "—";
    const num = Number(seconds);
    if (isNaN(num) || num <= 0) return String(seconds);
    const h = Math.floor(num / 3600);
    const m = Math.floor((num % 3600) / 60);
    const s = num % 60;
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }

  function handleOpenEditEvent(evt: any) {
    setEditingEvent(evt);
    setEventTitle(evt.title || "");
    setEventTargetKm(evt.target_km || 200);
    setEventRules(evt.rules || "");
    setShowCreateEventModal(true);
  }

  async function handleDeleteEvent(eventId: string) {
    if (!currentClub) return;
    if (!confirm("确定要删除该跑团挑战赛活动吗？")) return;
    try {
      await apiClient.delete(`/api/team/${currentClub.id}/events/${eventId}`);
      alert("活动已成功删除");
      loadClubDetails(currentClub.id);
    } catch (e: any) {
      alert("删除失败");
    }
  }

  async function handleCreateOrEditEvent(e: React.FormEvent) {
    e.preventDefault();
    if (!currentClub || !eventTitle.trim() || !user?.id) return;
    try {
      if (editingEvent) {
        await apiClient.put(`/api/team/${currentClub.id}/events/${editingEvent.id}`, {
          operator_uid: user.id,
          title: eventTitle.trim(),
          target_km: Number(eventTargetKm),
          rules: eventRules.trim(),
        });
        alert("挑战赛修改成功！");
      } else {
        await apiClient.post(`/api/team/${currentClub.id}/events`, {
          operator_uid: user.id,
          title: eventTitle.trim(),
          target_km: Number(eventTargetKm),
          rules: eventRules.trim(),
        });
        alert("活动挑战发布成功！");
      }
      setShowCreateEventModal(false);
      setEditingEvent(null);
      setEventTitle("");
      setEventRules("");
      setActiveTab("events");
      loadClubDetails(currentClub.id);
    } catch (e: any) {
      alert("发布或修改失败");
    }
  }

  async function handleOpenMenteeDetail(menteeUid: string) {
    if (!user?.id || !menteeUid) return;
    setLoadingMenteeDetail(true);
    try {
      const res = await apiClient.get(
        `/api/team/mentorship/mentee/${encodeURIComponent(menteeUid)}/detail?viewer_uid=${encodeURIComponent(user.id)}`
      );
      setSelectedMenteeDetail(res.data || null);
    } catch (e: any) {
      alert(e.response?.data?.detail || "加载徒弟训练与休息数据失败");
    } finally {
      setLoadingMenteeDetail(false);
    }
  }

  async function handleBindMentorshipWeb(e: React.FormEvent) {
    e.preventDefault();
    if (!user?.id || !mentorshipTargetUid.trim() || bindingMentorship) return;
    setBindingMentorship(true);
    try {
      const target = mentorshipTargetUid.trim();
      const mentorUid = mentorshipBindRole === "as_mentee" ? target : user.id;
      const menteeUid = mentorshipBindRole === "as_mentee" ? user.id : target;
      const res = await apiClient.post("/api/team/mentorship/bind", {
        mentor_id: mentorUid,
        mentee_id: menteeUid,
        operator_uid: user.id,
      });
      alert(res.data?.message || "师徒结对成功！");
      setMentorshipTargetUid("");
      setShowMentorshipBindModal(false);
      if (currentClub?.id) {
        await loadClubDetails(currentClub.id, user.id);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "师徒结对失败");
    } finally {
      setBindingMentorship(false);
    }
  }

  async function handleUnbindMentorshipWeb(mentorUid: string, menteeUid: string, labelName: string) {
    if (!user?.id) return;
    if (!confirm(`确定要解除与【${labelName}】的 1对1 师徒关系吗？`)) return;
    try {
      const res = await apiClient.post("/api/team/mentorship/unbind", {
        mentor_id: mentorUid,
        mentee_id: menteeUid,
        operator_uid: user.id,
      });
      alert(res.data?.message || "已解除师徒关系");
      setSelectedMenteeDetail(null);
      if (currentClub?.id) {
        await loadClubDetails(currentClub.id, user.id);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || "解除失败");
    }
  }

  const visibleFeed = isFeedExpanded || feed.length <= 20 ? feed : feed.slice(0, 20);

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      {loading ? (
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-24 text-center text-zinc-500">
          <p>跑团数据加载中...</p>
        </div>
      ) : !currentClub ? (
        <main className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-10">
          {activeManagedOrg && (
            <div className="bg-gradient-to-r from-[#18181c] via-[#121215] to-[#18181c] border border-amber-500/35 rounded-3xl p-6 shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-5">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/35">
                    🏛️ {activeManagedOrg.role === "owner" || activeManagedOrg.owner_id === user?.id ? "大群主理人" : "大群管理员"}
                  </span>
                  <h2 className="text-lg sm:text-xl font-black text-white">
                    【{activeManagedOrg.name}】大群管理工作台
                  </h2>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/10 text-zinc-300">
                    {activeManagedOrg.join_mode === "free" ? "🟢 自由入会" : `🔒 邀请码: ${activeManagedOrg.invite_code || "已设"}`}
                  </span>
                </div>
                <p className="text-xs text-zinc-400">
                  无需超级管理员权限，可直接管理本大群基本设定、入会方式与邀请码、准入字段（必填 / 选填 / 不显示）及戈友花名册审核。
                </p>
              </div>
              <div className="flex items-center gap-2.5 flex-wrap shrink-0">
                <button
                  type="button"
                  onClick={() => openOrgReportModalFor(activeManagedOrg)}
                  className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-emerald-400 to-teal-500 hover:from-emerald-300 hover:to-teal-400 text-black text-xs font-black transition shadow-lg shadow-emerald-500/20"
                >
                  📊 大群报表与分团 PK
                </button>
                <button
                  type="button"
                  onClick={() => openOrgEventsModalFor(activeManagedOrg)}
                  className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-[#FC4C02] to-[#ff6426] hover:from-[#ff6426] hover:to-[#ff7a45] text-white text-xs font-black transition shadow-lg shadow-[#FC4C02]/25"
                >
                  🚩 跨跑团联合活动
                </button>
                <button
                  type="button"
                  onClick={() => openOrgSettingsModalFor(activeManagedOrg)}
                  className="px-4 py-2.5 rounded-2xl bg-amber-500 hover:bg-amber-400 text-black text-xs font-black transition shadow-lg shadow-amber-500/20"
                >
                  ⚙️ 大群设定与邀请码
                </button>
                <button
                  type="button"
                  onClick={() => openOrgFieldRulesModalFor(activeManagedOrg)}
                  className="px-4 py-2.5 rounded-2xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition shadow-lg shadow-purple-600/20"
                >
                  🛡️ 准入信息配置 (必填/选填/不显示)
                </button>
                <button
                  type="button"
                  onClick={() => openOrgRosterModalFor(activeManagedOrg)}
                  className="px-4 py-2.5 rounded-2xl bg-white/10 hover:bg-white/15 border border-white/15 text-white text-xs font-bold transition"
                >
                  👥 大群花名册与审核 ({activeManagedOrg.member_count ?? ""})
                </button>
              </div>
            </div>
          )}
          <div className="bg-gradient-to-b from-[#18181c] to-[#121215] border border-white/10 rounded-3xl p-8 sm:p-10 text-center shadow-2xl">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#FC4C02]/10 border border-[#FC4C02]/30 text-3xl mb-4">
              🏃‍♂️
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white mb-2">
              欢迎来到跑团中心
            </h1>
            <p className="text-sm text-zinc-400 max-w-xl mx-auto leading-relaxed mb-6">
              请在下方浏览平台所有已创建跑团并选择加入，与队友共同参加月度跑量挑战、查看英雄榜与教练负荷监控！
            </p>
            <div className="flex items-center justify-center gap-3 flex-wrap">
              <button
                onClick={() => setShowJoinModal(true)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-zinc-300 hover:text-white rounded-xl transition"
              >
                <UserPlus className="w-3.5 h-3.5 text-[#FC4C02]" />
                已有跑团邀请码？点此加入
              </button>
              <button
                onClick={() => setShowOrgJoinModal(true)}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-xs font-bold text-amber-300 rounded-xl transition shadow-lg shadow-amber-500/10"
              >
                <Shield className="w-3.5 h-3.5 text-amber-400" />
                加入大群体 · 戈友实名认证
              </button>
            </div>
          </div>

          {/* All Created Clubs Section */}
          <div className="space-y-5">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <span className="text-lg font-black text-white">🏆 平台所有跑团</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FC4C02]/20 text-[#FC4C02] border border-[#FC4C02]/30">
                  {allClubs.length} 个跑团
                </span>
              </div>
              <span className="text-xs text-zinc-400">选择您感兴趣的跑团，点击即可一键加入开启训练</span>
            </div>

            {loadingAllClubs ? (
              <div className="py-12 text-center text-xs text-zinc-500">正在加载跑团列表...</div>
            ) : allClubs.length === 0 ? (
              <div className="bg-[#141416] border border-white/5 rounded-3xl p-12 text-center text-zinc-400">
                平台暂无已创建跑团，请联系平台超级管理员创建！
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {allClubs.map((club) => (
                  <div
                    key={club.id}
                    className="bg-[#141416] hover:bg-[#18181c] border border-white/10 hover:border-[#FC4C02]/40 rounded-3xl p-6 transition flex flex-col justify-between shadow-xl"
                  >
                    <div>
                      <div className="flex items-start gap-4 mb-4">
                        <img
                          src={club.logo_url || "/logo.png"}
                          alt={club.name}
                          className="w-16 h-16 rounded-2xl object-cover border-2 border-[#FC4C02]/30 shrink-0 shadow-md"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="text-lg font-black text-white truncate">{club.name}</h3>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/10 text-zinc-300">
                              📍 {club.city || "上海"}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-400 mt-1.5 line-clamp-2 leading-relaxed">
                            {club.description || "科学耐力训练 · PB 突破与健康长久奔跑。"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 py-3 px-3.5 bg-black/30 rounded-2xl border border-white/5 text-xs text-zinc-400 mb-5">
                        <div>
                          <span className="text-zinc-500">团长: </span>
                          <span className="text-white font-semibold">{club.owner_name || "平台指定"}</span>
                        </div>
                        <div className="w-px h-3 bg-white/10" />
                        <div>
                          <span className="text-zinc-500">成员: </span>
                          <span className="text-[#FC4C02] font-bold">{club.member_count || 1} 人</span>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2">
                      <button
                        onClick={() => handleJoinClubDirect(club.id)}
                        disabled={joiningClubId === club.id}
                        className="w-full py-3 bg-[#FC4C02] hover:bg-[#ff6426] text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-[#FC4C02]/20 flex items-center justify-center gap-2"
                      >
                        <UserPlus className="w-4 h-4" />
                        {joiningClubId === club.id ? "正在加入..." : "选择参加此跑团"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Unaffiliated Peers Mutual Basic Status Section */}
          <div className="bg-[#141416] border border-cyan-500/25 rounded-3xl p-6 sm:p-8 space-y-5 shadow-2xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span className="text-lg font-black text-white">🌍 自由跑友同伴 · 基本状态互看</span>
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                    {unaffiliatedPeersSummary?.total_members ?? unaffiliatedPeers.length} 人
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  暂未加入跑团的跑友之间可互相查看手表绑定、目标设定与月跑量进度（出于隐私保护，不在同一跑团的用户之间不展示具体单次运动记录与GPS轨迹）
                </p>
              </div>
              <input
                type="text"
                value={unaffiliatedPeerSearch}
                onChange={(e) => setUnaffiliatedPeerSearch(e.target.value)}
                placeholder="搜索自由跑友昵称..."
                className="w-full sm:w-56 bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-cyan-500"
              />
            </div>

            {unaffiliatedPeers.length === 0 ? (
              <div className="py-8 text-center text-xs text-zinc-500">正在加载自由跑友基本状态...</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[540px] overflow-y-auto pr-1">
                {unaffiliatedPeers
                  .filter((p) => {
                    const q = unaffiliatedPeerSearch.trim().toLowerCase();
                    if (!q) return true;
                    return (p.display_name || "").toLowerCase().includes(q) || (p.user_id || "").toLowerCase().includes(q);
                  })
                  .slice(0, 60)
                  .map((p) => (
                    <div
                      key={p.user_id}
                      className="bg-[#18181c] border border-white/5 hover:border-cyan-500/30 rounded-2xl p-4 flex flex-col justify-between gap-3 transition"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <img
                              src={p.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                              alt={p.display_name}
                              className="w-10 h-10 rounded-full object-cover border border-white/10 shrink-0"
                            />
                            <div className="min-w-0">
                              <div className="font-bold text-white text-xs truncate">
                                {p.display_name}
                                {p.user_id === user?.id && (
                                  <span className="ml-1.5 px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 text-[10px]">我</span>
                                )}
                              </div>
                              <div className="text-[10px] text-zinc-500 mt-0.5">
                                ⏰ 注册：{p.joined_at_display || "近期"}
                              </div>
                            </div>
                          </div>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/5 text-zinc-300 shrink-0">
                            本月 {p.month_km || 0}km
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-[11px]">
                          <div className={`p-2 rounded-xl border ${p.watch_bound ? "bg-emerald-500/10 border-emerald-500/30" : "bg-amber-500/10 border-amber-500/30"}`}>
                            <div className="flex items-center justify-between">
                              <span className="text-zinc-400">⌚ 手表</span>
                              <span className={`font-bold text-[10px] ${p.watch_bound ? "text-emerald-300" : "text-amber-300"}`}>
                                {p.watch_bound ? "已绑定" : "未绑定"}
                              </span>
                            </div>
                            <div className="text-[10px] text-zinc-300 truncate mt-0.5">{p.watch_bound_label}</div>
                          </div>
                          <div className={`p-2 rounded-xl border ${p.goal_configured ? "bg-emerald-500/10 border-emerald-500/30" : "bg-amber-500/10 border-amber-500/30"}`}>
                            <div className="flex items-center justify-between">
                              <span className="text-zinc-400">🎯 目标</span>
                              <span className={`font-bold text-[10px] ${p.goal_configured ? "text-emerald-300" : "text-amber-300"}`}>
                                {p.goal_configured ? "已设定" : "默认"}
                              </span>
                            </div>
                            <div className="text-[10px] text-zinc-300 truncate mt-0.5">月目标 {p.target_km || 100}km</div>
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => router.push(`/dashboard/analysis?student_user_id=${encodeURIComponent(p.user_id)}`)}
                        className="w-full py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-[11px] font-bold text-zinc-200 transition"
                      >
                        📊 查看基本状态名片
                      </button>
                    </div>
                  ))}
              </div>
            )}
          </div>

          {/* Feature Highlights Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-[#141416] border border-white/5 rounded-2xl p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-xl shrink-0">
                🥇
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">跑团月度英雄榜</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  自动汇聚全体团员月跑量与配速排名，良性竞逐突破个人 PB。
                </p>
              </div>
            </div>

            <div className="bg-[#141416] border border-white/5 rounded-2xl p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-xl shrink-0">
                🏆
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">专属跑量挑战赛</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  团长与教练可随时发起公里数打卡挑战，团员达标点亮荣誉勋章。
                </p>
              </div>
            </div>

            <div className="bg-[#141416] border border-white/5 rounded-2xl p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-xl shrink-0">
                💬
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">跑友圈动态与 AI 点评</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  同步手表跑步记录后自动生成 AI 战报，支持队友点赞与留言互动。
                </p>
              </div>
            </div>

            <div className="bg-[#141416] border border-white/5 rounded-2xl p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-xl shrink-0">
                🧢
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">教练学员体能罗盘</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  科学监控全员 CTL/ATL/TSB 负荷与心率变异性，预防过度训练与伤病。
                </p>
              </div>
            </div>
          </div>
        </main>
      ) : (
        <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8">
          {activeManagedOrg && (
            <div className="bg-gradient-to-r from-[#18181c] via-[#121215] to-[#18181c] border border-amber-500/35 rounded-3xl p-5 sm:p-6 shadow-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/35">
                    🏛️ {activeManagedOrg.role === "owner" || activeManagedOrg.owner_id === user?.id ? "大群主理人" : "大群管理员"}
                  </span>
                  <h2 className="text-base sm:text-lg font-black text-white">
                    【{activeManagedOrg.name}】大群设定与准入管理
                  </h2>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/10 text-zinc-300">
                    {activeManagedOrg.join_mode === "free" ? "🟢 自由入会" : `🔒 邀请码: ${activeManagedOrg.invite_code || "已设"}`}
                  </span>
                  {userOrgs.filter((o: any) => o.is_organizer || o.role === "owner" || o.role === "admin" || o.owner_id === user?.id).length > 1 && (
                    <select
                      value={activeManagedOrg.id}
                      onChange={(e) => {
                        const found = userOrgs.find((o: any) => o.id === e.target.value);
                        if (found) setActiveManagedOrg(found);
                      }}
                      className="bg-black/40 border border-white/15 rounded-lg px-2 py-0.5 text-[11px] text-amber-300"
                    >
                      {userOrgs
                        .filter((o: any) => o.is_organizer || o.role === "owner" || o.role === "admin" || o.owner_id === user?.id)
                        .map((o: any) => (
                          <option key={o.id} value={o.id}>
                            切换大群: {o.name}
                          </option>
                        ))}
                    </select>
                  )}
                </div>
                <p className="text-xs text-zinc-400">
                  无需超级管理员权限，可直接管理大群设定、入会规则与邀请码、准入字段（必填 / 选填 / 不显示）及花名册审核。
                </p>
              </div>
              <div className="flex items-center gap-2.5 flex-wrap shrink-0">
                <button
                  type="button"
                  onClick={() => openOrgReportModalFor(activeManagedOrg)}
                  className="px-3.5 py-2 rounded-2xl bg-gradient-to-r from-emerald-400 to-teal-500 hover:from-emerald-300 hover:to-teal-400 text-black text-xs font-black transition shadow-lg shadow-emerald-500/20"
                >
                  📊 大群报表与分团 PK
                </button>
                <button
                  type="button"
                  onClick={() => openOrgEventsModalFor(activeManagedOrg)}
                  className="px-3.5 py-2 rounded-2xl bg-gradient-to-r from-[#FC4C02] to-[#ff6426] hover:from-[#ff6426] hover:to-[#ff7a45] text-white text-xs font-black transition shadow-lg shadow-[#FC4C02]/25"
                >
                  🚩 跨跑团联合活动
                </button>
                <button
                  type="button"
                  onClick={() => openOrgSettingsModalFor(activeManagedOrg)}
                  className="px-3.5 py-2 rounded-2xl bg-amber-500 hover:bg-amber-400 text-black text-xs font-black transition shadow-lg shadow-amber-500/20"
                >
                  ⚙️ 大群设定与邀请码
                </button>
                <button
                  type="button"
                  onClick={() => openOrgFieldRulesModalFor(activeManagedOrg)}
                  className="px-3.5 py-2 rounded-2xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition shadow-lg shadow-purple-600/20"
                >
                  🛡️ 准入信息配置 (必填/选填/不显示)
                </button>
                <button
                  type="button"
                  onClick={() => openOrgRosterModalFor(activeManagedOrg)}
                  className="px-3.5 py-2 rounded-2xl bg-white/10 hover:bg-white/15 border border-white/15 text-white text-xs font-bold transition"
                >
                  👥 大群花名册与审核 ({activeManagedOrg.member_count ?? ""})
                </button>
              </div>
            </div>
          )}
          {/* Header with Multi-Club Selector and Actions */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-gradient-to-r from-[#18181c] via-[#121215] to-[#18181c] border border-white/10 rounded-3xl p-6 shadow-2xl">
            <div className="flex items-center gap-4">
              <img
                src={currentClub.logo_url || "/logo.png"}
                alt="Club Logo"
                className="w-16 h-16 rounded-2xl object-cover border-2 border-[#FC4C02]/40 shadow-lg"
              />
              <div>
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h1 className="text-xl sm:text-2xl font-black text-white">
                    {currentClub.name}
                  </h1>
                  {currentClub.org_name && (
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                      🏛️ {currentClub.org_name}
                    </span>
                  )}
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#FC4C02]/20 text-[#FC4C02] border border-[#FC4C02]/30">
                    {currentRole === "owner" ? "👑 跑团主理人" : currentRole === "coach" ? "🧢 认证教练" : "🏃 核心团员"}
                  </span>
                  {currentClub.status === "paused" && (
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1">
                      <Pause className="w-2.5 h-2.5" /> 已暂停
                    </span>
                  )}
                  {currentClub.status === "locked" && (
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30 flex items-center gap-1">
                      <Lock className="w-2.5 h-2.5" /> 已锁定
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-400 mt-1 line-clamp-1 max-w-xl">
                  {currentClub.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。"}
                </p>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-[11px] text-zinc-500">📍 {currentClub.city || "上海"}</span>
                </div>
                {clubs.length > 1 && (
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <span className="text-[11px] text-zinc-400 font-medium">切换跑团:</span>
                    {clubs.map((c: any) => (
                      <button
                        key={c.id}
                        onClick={() => handleSwitchClub(c)}
                        className={`px-3 py-1 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                          currentClub.id === c.id
                            ? c.is_access_suspended
                              ? "bg-rose-600 text-white shadow-md shadow-rose-600/20 font-bold"
                              : "bg-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/20 font-bold"
                            : c.is_access_suspended
                            ? "bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            : "bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white border border-white/5"
                        }`}
                      >
                        <span>{c.name}</span>
                        {c.is_access_suspended && (
                          <span className="text-[10px] px-1 py-0.2 bg-rose-950/80 rounded text-rose-300 font-bold">受限</span>
                        )}
                        {currentClub.id === c.id && <span>✓</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Quick Action Buttons */}
            <div className="flex items-center gap-3 flex-wrap">
              {coachWorkbenchMode ? (
                <>
                  <button
                    onClick={() => setShowScheduleImportModal(true)}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-emerald-400 to-teal-500 hover:from-emerald-300 hover:to-teal-400 text-black rounded-2xl text-xs font-black transition shadow-lg shadow-emerald-500/20 cursor-pointer"
                    title="上传主教练周日发布的课表截图（支持A~E组或男女组拆解、体能a/b/c合并）并按组一键派发"
                  >
                    📸 识图导入周课表
                  </button>
                  <button
                    onClick={() => openTemplateAssignModal()}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-amber-400 to-orange-500 hover:from-amber-300 hover:to-orange-400 text-black rounded-2xl text-xs font-black transition shadow-lg shadow-amber-500/20 cursor-pointer"
                  >
                    📚 分组与专项模版库
                  </button>
                  <button
                    onClick={() => setShowBroadcastModal(true)}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-purple-600/25 hover:bg-purple-600/40 border border-purple-500/35 text-purple-200 rounded-2xl text-xs font-bold transition cursor-pointer"
                  >
                    📢 合练课派发
                  </button>
                  {!currentClub?.is_virtual_unaffiliated && (
                    <button
                      onClick={() => openClubInviteModal(currentClub)}
                      className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-[#22c55e] to-[#10b981] hover:from-[#4ade80] hover:to-[#34d399] text-black rounded-2xl text-xs font-black transition shadow-lg shadow-emerald-500/20 cursor-pointer"
                      title="生成跑团微信邀请函海报、小程序码与邀请口令，方便转发给微信联系人或微信群"
                    >
                      💌 邀请入团 · 转发微信
                    </button>
                  )}
                  <button
                    onClick={openClubReportModal}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-amber-300 rounded-2xl text-xs font-bold transition cursor-pointer"
                  >
                    <FileText className="w-4 h-4" />
                    跑团周报/月报
                  </button>
                  <button
                    onClick={() => setShowPersonalReportModal(true)}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-sky-300 rounded-2xl text-xs font-bold transition cursor-pointer"
                  >
                    <ImageIcon className="w-4 h-4" />
                    个人周报/月报
                  </button>
                  <button
                    onClick={() => router.push("/dashboard/team")}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-white/5 border border-white/10 hover:bg-white/10 text-zinc-300 rounded-2xl text-xs font-bold transition cursor-pointer"
                  >
                    <Trophy className="w-4 h-4 text-[#FC4C02]" />
                    跑团主页
                  </button>
                </>
              ) : (
                <>
                  {(currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
                    <>
                      <button
                        onClick={() => setShowScheduleImportModal(true)}
                        className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-emerald-400 to-teal-500 hover:from-emerald-300 hover:to-teal-400 text-black rounded-2xl text-xs font-black transition shadow-lg shadow-emerald-500/20 cursor-pointer"
                        title="上传主教练发布的课表截图（支持A~E组或男女组拆解、体能a/b/c合并）并按组一键派发"
                      >
                        📸 识图导入周课表
                      </button>
                      <button
                        onClick={() => router.push("/dashboard/team-coach")}
                        className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-2xl text-xs font-black transition shadow-lg shadow-purple-600/25 cursor-pointer"
                      >
                        <ClipboardCheck className="w-4 h-4" />
                        🧢 教练集中工作台
                      </button>
                    </>
                  )}
                  {!currentClub?.is_virtual_unaffiliated && (
                    <button
                      onClick={() => openClubInviteModal(currentClub)}
                      className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-r from-[#22c55e] to-[#10b981] hover:from-[#4ade80] hover:to-[#34d399] text-black rounded-2xl text-xs font-black transition shadow-lg shadow-emerald-500/20 cursor-pointer"
                      title="生成跑团微信邀请函海报、小程序码与邀请口令，方便转发给微信联系人或微信群"
                    >
                      💌 邀请入团 · 转发微信
                    </button>
                  )}
                  <button
                    onClick={openClubReportModal}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/35 text-amber-300 rounded-2xl text-xs font-bold transition cursor-pointer"
                  >
                    <FileText className="w-4 h-4 text-amber-400" />
                    跑团周报/月报
                  </button>
                  <button
                    onClick={() => setShowPersonalReportModal(true)}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/35 text-sky-300 rounded-2xl text-xs font-bold transition cursor-pointer"
                  >
                    <ImageIcon className="w-4 h-4 text-sky-400" />
                    个人周报/月报
                  </button>
                  <button
                    onClick={() => setShowAllClubsModal(true)}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-[#FC4C02] hover:bg-[#ff6426] text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-[#FC4C02]/20"
                  >
                    <Users className="w-4 h-4" />
                    浏览全部跑团 ({allClubs.length})
                  </button>
                  <button
                    onClick={() => setShowJoinModal(true)}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-white/5 border border-white/10 hover:bg-white/10 text-white rounded-2xl text-xs font-bold transition shadow-sm"
                  >
                    <UserPlus className="w-4 h-4 text-[#FC4C02]" />
                    输入邀请码
                  </button>
                  <button
                    onClick={() => setShowCreateClubModal(true)}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/35 text-emerald-300 rounded-2xl text-xs font-bold transition cursor-pointer"
                  >
                    <Plus className="w-4 h-4 text-emerald-400" />
                    自建跑团
                  </button>
                  {!currentClub?.is_virtual_unaffiliated && (
                    <button
                      onClick={openLeaveClubModal}
                      className="flex items-center gap-1.5 px-4 py-2.5 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 rounded-2xl text-xs font-bold transition"
                      title="主动退出当前跑团（含二次防误触保护）"
                    >
                      <UserMinus className="w-4 h-4 text-rose-400" />
                      退出跑团
                    </button>
                  )}
                  <button
                    onClick={() => setShowOrgJoinModal(true)}
                    className="flex items-center gap-1.5 px-4 py-2.5 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 rounded-2xl text-xs font-bold transition shadow-lg shadow-amber-500/10"
                  >
                    <Shield className="w-4 h-4 text-amber-400" />
                    加入大群体 · 戈友认证
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Status Warning Banners for Paused / Locked Clubs */}
          {currentClub.status === "paused" && (
            <div className="bg-amber-500/15 border border-amber-500/40 rounded-3xl p-4 sm:p-5 flex items-start gap-3.5 shadow-lg shadow-amber-500/5">
              <div className="p-2 rounded-2xl bg-amber-500/20 text-amber-400 shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-bold text-amber-300 flex items-center gap-2">
                  本跑团当前处于【暂停运行】状态
                </h3>
                <p className="text-xs text-amber-200/80 mt-1 leading-relaxed">
                  本跑团已暂停运行：暂停动态消息发布与活动、禁止新成员加入或移除队员、暂停团队数据更新，且对外完全隐藏。已有成员可继续查阅历史记录。如需恢复正常，请跑团团长前往【👥 跑团成员与管理】进行恢复。
                </p>
              </div>
            </div>
          )}
          {currentClub.status === "locked" && (
            <div className="bg-blue-500/15 border border-blue-500/40 rounded-3xl p-4 sm:p-5 flex items-start gap-3.5 shadow-lg shadow-blue-500/5">
              <div className="p-2 rounded-2xl bg-blue-500/20 text-blue-400 shrink-0">
                <Lock className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-bold text-blue-300 flex items-center gap-2">
                  本跑团当前处于【锁定归档】状态
                </h3>
                <p className="text-xs text-blue-200/80 mt-1 leading-relaxed">
                  本跑团已进入锁定归档状态：只读模式，不允许新队员加入或移除现有队员，对外隐藏。已有成员仍可正常浏览跑步数据与排行榜。
                </p>
              </div>
            </div>
          )}


        {(currentClub.is_access_suspended || clubSuspended) ? (
          <div className="bg-[#121215] border border-rose-500/30 rounded-3xl p-8 sm:p-12 text-center max-w-2xl mx-auto shadow-2xl space-y-6 my-8">
            <div className="w-16 h-16 rounded-3xl bg-rose-500/20 text-rose-400 flex items-center justify-center mx-auto text-3xl">
              🚫
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-black text-rose-300">
                跑团访问权限已暂停
              </h2>
              <p className="text-sm text-zinc-300 leading-relaxed">
                {clubSuspensionReason || currentClub.suspension_reason || "您在大群体/大组织的2周临时访问期已到期（超期未完成所有必填字段填写并获大团管理员确认）。根据群规，已暂停浏览使用该大团及其从属跑团的一切内容和活动！"}
              </p>
            </div>
            <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/5 text-left text-xs text-zinc-400 space-y-2">
              <div className="font-bold text-zinc-200">💡 如何恢复跑团访问？</div>
              <div>1. 前往【个人档案】补齐大群要求的所有必填字段（真实姓名、生理性别、出生日期、商学院项目与班级等）。</div>
              <div>2. 联系大团管理员在“大群体花名册”中核对并点击【确认转正】。</div>
              <div>3. 管理员审核确认后，将立即恢复大团及从属跑团的全部访问与活动参与权限！</div>
            </div>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              <button
                onClick={() => router.push("/dashboard/profile")}
                className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-[#FC4C02] to-amber-500 text-white font-bold text-sm shadow-lg shadow-orange-500/20 hover:opacity-90 transition active:scale-95 flex items-center justify-center gap-2"
              >
                <span>📝 立即前往个人档案补齐必填项</span>
              </button>
              {clubs.filter((c: any) => !c.is_access_suspended).length > 0 && (
                <button
                  onClick={() => {
                    const other = clubs.find((c: any) => c.id !== currentClub.id && !c.is_access_suspended);
                    if (other) {
                      handleSwitchClub(other);
                    }
                  }}
                  className="w-full sm:w-auto px-6 py-3 rounded-xl bg-white/10 hover:bg-white/15 text-white font-semibold text-sm border border-white/10 transition"
                >
                  切换其他未受限跑团
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* 4-Tab Navigation */}
            <div className="flex items-center gap-2 border-b border-white/10 pb-3 overflow-x-auto">
          {coachWorkbenchMode ? (
            <>
              <button
                onClick={() => setActiveTab("coach")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition cursor-pointer ${
                  activeTab === "coach"
                    ? "bg-purple-600 text-white shadow-lg shadow-purple-600/25"
                    : "bg-white/5 text-zinc-400 hover:text-white"
                }`}
              >
                <Activity className="w-4 h-4" />
                🧭 排课模版与全队体能罗盘
              </button>
              <button
                onClick={() => setActiveTab("leaderboard")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition cursor-pointer ${
                  activeTab === "leaderboard"
                    ? "bg-[#FC4C02] text-white shadow-lg shadow-[#FC4C02]/25"
                    : "bg-white/5 text-zinc-400 hover:text-white"
                }`}
              >
                <Flame className="w-4 h-4" />
                💬 队员打卡动态与教练点评台
              </button>
              <button
                onClick={() => setActiveTab("events")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition cursor-pointer ${
                  activeTab === "events"
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-600/25"
                    : "bg-white/5 text-zinc-400 hover:text-white"
                }`}
              >
                <Award className="w-4 h-4" />
                🏃 合练约跑与挑战赛管理 ({events.length})
              </button>
              <button
                onClick={() => setActiveTab("president")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition cursor-pointer ${
                  activeTab === "president"
                    ? "bg-amber-600 text-white shadow-lg shadow-amber-600/25"
                    : "bg-white/5 text-zinc-400 hover:text-white"
                }`}
              >
                <Users className="w-4 h-4" />
                📊 战报中心与成员/助教管理
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setActiveTab("leaderboard")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition ${
                  activeTab === "leaderboard"
                    ? "bg-[#FC4C02] text-white shadow-lg shadow-[#FC4C02]/25"
                    : "bg-white/5 text-zinc-400 hover:text-white"
                }`}
              >
                <Trophy className="w-4 h-4" />
                跑团总览与排行榜
              </button>

              {(currentRole === "owner" || currentRole === "coach") && (
                <button
                  onClick={() => setActiveTab("coach")}
                  className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition ${
                    activeTab === "coach"
                      ? "bg-purple-600 text-white shadow-lg shadow-purple-600/25"
                      : "bg-white/5 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Activity className="w-4 h-4" />
                  🧢 教练学员体能罗盘
                </button>
              )}

              {(currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
                <button
                  onClick={() => setActiveTab("president")}
                  className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition ${
                    activeTab === "president"
                      ? "bg-amber-600 text-white shadow-lg shadow-amber-600/25"
                      : "bg-white/5 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Users className="w-4 h-4" />
                  👥 跑团成员与管理
                </button>
              )}

              <button
                onClick={() => setActiveTab("events")}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition ${
                  activeTab === "events"
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-600/25"
                    : "bg-white/5 text-zinc-400 hover:text-white"
                }`}
              >
                <Award className="w-4 h-4" />
                🏆 跑团挑战赛与活动 ({events.length})
              </button>
            </>
          )}
        </div>

        {/* ── TAB 1: 跑团总览与排行榜 ── */}
        {activeTab === "leaderboard" && (
          <div className="space-y-8">
            {/* Top Stat Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-5">
                <span className="text-xs text-zinc-400 font-medium">🏃 本月跑团总里程</span>
                <div className="text-2xl font-black text-white mt-1">
                  {dashboardMetrics?.total_month_km || "16.0"} <span className="text-xs text-[#FC4C02]">km</span>
                </div>
              </div>
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-5">
                <span className="text-xs text-zinc-400 font-medium">👥 注册跑者人数</span>
                <div className="text-2xl font-black text-white mt-1">
                  {dashboardMetrics?.members_count || members.length || 1} <span className="text-xs text-zinc-500">人</span>
                </div>
              </div>
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-5">
                <span className="text-xs text-zinc-400 font-medium">🧢 认证专业教练</span>
                <div className="text-2xl font-black text-purple-400 mt-1">
                  {dashboardMetrics?.coaches_count || 1} <span className="text-xs text-zinc-500">位</span>
                </div>
              </div>
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-5">
                <span className="text-xs text-zinc-400 font-medium">🎯 进行中挑战赛</span>
                <div className="text-2xl font-black text-emerald-400 mt-1">
                  {dashboardMetrics?.active_events_count || events.length || 1} <span className="text-xs text-zinc-500">项</span>
                </div>
              </div>
            </div>

            {/* 桌面双栏：左侧「师徒传帮带 + 英雄榜」，右侧打卡动态（主内容流） */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              <div className="lg:col-span-5 space-y-6">
            {/* 🥋 师徒传帮带（紧凑版，位于英雄榜上方） */}
            <div className="bg-gradient-to-br from-emerald-950/25 via-[#121215] to-teal-950/20 border border-emerald-500/25 rounded-3xl p-5 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <h2
                  className="text-base font-black text-white flex items-center gap-2 cursor-help"
                  title={`每位队员可拜 1 位师傅，每位师傅最多同时带 ${mentorshipOverview?.max_mentees || 3} 位徒弟（同大群可跨跑团）。师傅可只读查看徒弟的训练课表、GPS 轨迹与静息心率 / HRV / 睡眠恢复数据。`}
                >
                  🥋 师徒传帮带
                  <span className="text-[11px] font-normal text-zinc-500">ⓘ</span>
                </h2>
                <button
                  onClick={() => setShowMentorshipBindModal(true)}
                  className="px-3 py-1.5 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 text-xs font-bold transition shrink-0"
                >
                  + 结对 {mentorshipOverview?.mentees_count || 0}/{mentorshipOverview?.max_mentees || 3}
                </button>
              </div>

              {/* 我的师傅（单行） */}
              <div className="flex items-center justify-between gap-2 bg-[#16181d] border border-white/10 rounded-2xl px-3 py-2.5">
                {mentorshipOverview?.my_mentor ? (
                  <>
                    <div className="flex items-center gap-2.5 min-w-0">
                      <img
                        src={
                          mentorshipOverview.my_mentor.avatar_url ||
                          "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                        }
                        alt={mentorshipOverview.my_mentor.display_name}
                        className="w-8 h-8 rounded-full object-cover border border-emerald-500/40 shrink-0"
                      />
                      <div className="min-w-0">
                        <div className="text-xs font-bold text-white truncate">
                          🙏 师傅 · {mentorshipOverview.my_mentor.display_name}
                        </div>
                        <div className="text-[10px] text-zinc-500 truncate">
                          {(mentorshipOverview.my_mentor.clubs || []).join(" · ") || "同大群师傅"} · 全马PB{" "}
                          {mentorshipOverview.my_mentor.marathon_pb_str || "—"}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        handleUnbindMentorshipWeb(
                          mentorshipOverview.my_mentor.mentor_id,
                          user?.id,
                          mentorshipOverview.my_mentor.display_name
                        )
                      }
                      className="text-[11px] text-zinc-500 hover:text-rose-400 transition shrink-0"
                    >
                      解除
                    </button>
                  </>
                ) : (
                  <span className="text-xs text-zinc-500">🙏 暂未拜师 · 点「+ 结对」输入师傅 ID</span>
                )}
              </div>

              {/* 我的徒弟（最多 3 位，紧凑行） */}
              {(mentorshipOverview?.my_mentees || []).length > 0 ? (
                <div className="space-y-1.5">
                  {(mentorshipOverview?.my_mentees || []).map((mt: any) => (
                    <div
                      key={mt.mentee_id}
                      onClick={() => handleOpenMenteeDetail(mt.mentee_id)}
                      title="查看徒弟完整训练与睡眠恢复档案"
                      className="flex items-center justify-between gap-2 bg-[#16181d] hover:bg-[#1c2026] border border-emerald-500/20 hover:border-emerald-400/50 rounded-2xl px-3 py-2 transition cursor-pointer"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <img
                          src={
                            mt.avatar_url ||
                            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                          }
                          alt={mt.display_name}
                          className="w-8 h-8 rounded-full object-cover border border-white/10 shrink-0"
                        />
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-white truncate">{mt.display_name}</div>
                          <div className="text-[10px] text-zinc-500 truncate">
                            7天 {mt.training_summary?.week_km || 0}km · 本月 {mt.training_summary?.month_km || 0}km · 静息{" "}
                            {mt.rest_summary?.latest_resting_hr || "—"} · HRV {mt.rest_summary?.latest_hrv || "—"}
                          </div>
                        </div>
                      </div>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold shrink-0 ${
                          mt.training_summary?.status_level === "danger"
                            ? "bg-rose-500/20 text-rose-300"
                            : mt.training_summary?.status_level === "tired"
                            ? "bg-amber-500/20 text-amber-300"
                            : "bg-emerald-500/20 text-emerald-300"
                        }`}
                      >
                        TSB {mt.training_summary?.tsb ?? 0}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-between text-xs text-zinc-500 px-1">
                  <span>还没有徒弟（最多 {mentorshipOverview?.max_mentees || 3} 位）</span>
                  <button
                    onClick={() => {
                      setMentorshipBindRole("as_mentor");
                      setShowMentorshipBindModal(true);
                    }}
                    className="text-emerald-300 font-bold hover:text-emerald-200"
                  >
                    立即收徒 ›
                  </button>
                </div>
              )}
            </div>
            {/* Leaderboard Table */}
            <div className="bg-[#121215] border border-white/5 rounded-3xl p-5 shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-black text-white flex items-center gap-2">
                    <Trophy className="w-5 h-5 text-amber-400" />
                    本月英雄榜
                  </h2>
                  <p className="text-xs text-zinc-400 mt-0.5">按当月累计跑量实时竞逐排名</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-white/5 text-zinc-300">
                  实时更新
                </span>
              </div>

              <div className="space-y-2 lg:max-h-[60vh] lg:overflow-y-auto lg:pr-1">
                {leaderboard.map((runner) => (
                  <div
                    key={runner.user_id}
                    className={`flex items-center justify-between gap-3 p-3 rounded-2xl border transition ${
                      runner.rank === 1
                        ? "bg-amber-500/10 border-amber-500/30"
                        : runner.rank === 2
                        ? "bg-zinc-400/10 border-zinc-400/20"
                        : runner.rank === 3
                        ? "bg-orange-500/10 border-orange-500/20"
                        : "bg-[#18181c] border-white/5"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-7 flex-shrink-0 flex items-center justify-center font-black text-base">
                        {runner.rank === 1 ? "🥇" : runner.rank === 2 ? "🥈" : runner.rank === 3 ? "🥉" : `#${runner.rank}`}
                      </div>
                      <img
                        src={runner.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                        alt={runner.display_name}
                        className="w-9 h-9 rounded-full object-cover border border-white/10 flex-shrink-0"
                      />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-white">{runner.display_name}</span>
                          {runner.role === "owner" && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-bold">团长</span>
                          )}
                          {runner.role === "coach" && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 font-bold">教练</span>
                          )}
                        </div>
                        <span className="text-xs text-zinc-400">
                          目标: {runner.target_km} km · 完成度 {runner.progress_pct}%
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-base font-black text-white whitespace-nowrap">
                        {runner.distance_km} <span className="text-xs text-[#FC4C02]">km</span>
                      </div>
                      <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden mt-1 ml-auto">
                        <div
                          className="h-full bg-gradient-to-r from-[#FC4C02] to-amber-400 rounded-full"
                          style={{ width: `${Math.min(100, runner.progress_pct)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

              </div>
              <div className="lg:col-span-7">
            {/* Recent Group Activities Feed with AI Coach Comments & Social Interaction */}
            <div className="bg-[#121215] border border-white/5 rounded-3xl p-5 sm:p-6 space-y-5">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-black text-white flex items-center gap-2">
                  <Flame className="w-5 h-5 text-[#FC4C02]" />
                  打卡动态
                </h2>
                <span className="text-xs text-zinc-500 hidden sm:inline">❤️ 点赞 · 💬 评论</span>
              </div>

              {feed.length > 0 ? (
                <div className="space-y-6">
                  {visibleFeed.map((act) => (
                    <div
                      key={act.id}
                      className="p-6 bg-[#18181c] border border-white/10 rounded-3xl space-y-4 hover:border-white/20 transition shadow-xl"
                    >
                      {/* Top: Runner & Activity Info */}
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <img
                            src={act.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                            alt={act.display_name}
                            className="w-12 h-12 rounded-full object-cover border border-white/10"
                          />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-bold text-white">{act.display_name}</span>
                              <span className="text-xs text-zinc-400">· {act.name}</span>
                            </div>
                            <div className="text-xs text-zinc-400 mt-0.5 flex items-center gap-2 flex-wrap">
                              <span>⏱️ 配速 <strong className="text-white">{act.avg_pace_str}</strong></span>
                              <span>·</span>
                              {act.is_biometrics_hidden ? (
                                <span className="text-emerald-400 font-semibold">🔒 心率/生理指标已保密（仅教练与师傅可见）</span>
                              ) : (
                                <>
                                  <span>❤️ 心率 <strong className="text-rose-400">{act.average_heartrate || "—"} bpm</strong></span>
                                  <span>·</span>
                                  <span>⚡ 负荷 TRIMP <strong className="text-amber-400">{act.trimp || 50}</strong></span>
                                </>
                              )}
                              {((act.elevation_gain_meters && Number(act.elevation_gain_meters) > 0) || (act.total_elevation_gain && Number(act.total_elevation_gain) > 0)) && (
                                <>
                                  <span>·</span>
                                  <span>⛰️ 爬升 <strong className="text-emerald-400">+{Math.round(Number(act.elevation_gain_meters || act.total_elevation_gain))} m</strong></span>
                                </>
                              )}
                              <span>·</span>
                              <span className="text-[11px] text-zinc-500">{act.start_time?.slice(0, 16)?.replace("T", " ")}</span>
                            </div>
                          </div>
                        </div>

                        <div className="text-right flex-shrink-0">
                          <div className="text-2xl font-black text-[#FC4C02]">
                            {roundKm(act.distance_meters)} <span className="text-xs text-zinc-400">km</span>
                          </div>
                        </div>
                      </div>

                      {/* GPS Route Map & Elevation Profile Preview (respects runner confidentiality) */}
                      {act.is_gps_hidden ? (
                        <div className="px-4 py-3 rounded-2xl bg-emerald-950/20 border border-emerald-500/25 text-xs text-emerald-300 flex items-center gap-2">
                          <Lock className="w-4 h-4 text-emerald-400 shrink-0" />
                          <span>该队员已将 GPS 跑步路线轨迹设为保密（仅对本人、认证教练和 1对1 师傅开放）</span>
                        </div>
                      ) : (
                        <RouteMapPreview
                          activityId={act.id}
                          trackData={act.gps_track_data}
                          mapImageUrl={act.map_image_url}
                          activityName={act.name}
                          distanceMeters={act.distance_meters}
                          elevationGain={act.elevation_gain_meters || act.total_elevation_gain}
                          avgPace={act.avg_pace_str}
                          isSegmentHiddenHint={Boolean(act.is_segment_hidden)}
                        />
                      )}

                      {/* AI Coach Critique Bubble */}
                      <div className="bg-gradient-to-r from-purple-950/30 via-[#1e1b2e] to-indigo-950/30 border border-purple-500/25 rounded-2xl p-4 text-xs leading-relaxed text-zinc-200">
                        <div className="flex items-center gap-2 font-bold text-purple-300 mb-1.5">
                          <Bot className="w-4 h-4 text-purple-400" />
                          <span>Canova教练专属点评</span>
                          <span className="text-[10px] px-2 py-0.2 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                            智能生成
                          </span>
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed font-sans">
                          {act.ai_journal || "正在基于 Canova 耐力生理模型生成点评..."}
                        </p>
                      </div>

                      {/* Social Actions: Like & Comment Counter */}
                      <div className="flex items-center justify-between pt-2 border-t border-white/5">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleToggleLike(act.id)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition border ${
                              act.has_liked
                                ? "bg-rose-500/15 border-rose-500/40 text-rose-400 shadow-sm"
                                : "bg-white/5 border-white/10 text-zinc-400 hover:text-white hover:bg-white/10"
                            }`}
                          >
                            <Heart className={`w-3.5 h-3.5 ${act.has_liked ? "fill-rose-500 text-rose-500" : ""}`} />
                            <span>{act.has_liked ? "已点赞" : "点赞"} ({act.likes_count || 0})</span>
                          </button>

                          <div className="flex items-center gap-1 text-xs text-zinc-400 font-medium">
                            <MessageCircle className="w-3.5 h-3.5 text-zinc-500" />
                            <span>{act.comments?.length || 0} 条跑友留言</span>
                          </div>
                        </div>
                      </div>

                      {/* Likers Strip (显示点赞者及头像) */}
                      {act.likers && act.likers.length > 0 && (
                        <div className="flex items-start gap-2.5 bg-[#121214] border border-white/5 rounded-2xl px-3.5 py-2.5">
                          <Heart className="w-3.5 h-3.5 fill-rose-500 text-rose-500 mt-1 shrink-0" />
                          <div className="flex flex-wrap items-center gap-1.5">
                            {act.likers.map((lk: any, lkIdx: number) => (
                              <span
                                key={lk.user_id || lkIdx}
                                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[11px] font-semibold text-zinc-200"
                              >
                                <img
                                  src={lk.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                                  alt={lk.display_name || "跑友"}
                                  className="w-4 h-4 rounded-full object-cover"
                                />
                                <span>{lk.display_name || "跑友"}</span>
                              </span>
                            ))}
                            <span className="text-[11px] text-zinc-500 ml-1">
                              等 {act.likers.length} 人点赞
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Comments Thread (跑友留言产生 Thread) */}
                      {act.comments && act.comments.length > 0 && (
                        <div className="space-y-3 bg-[#121214] border border-white/5 rounded-2xl p-4">
                          {getCommentThreads(act.comments).map((thread: any) => (
                            <div key={thread.id} className="space-y-2">
                              {/* Root Comment */}
                              <div className="flex items-start justify-between gap-3 text-xs">
                                <div className="flex items-start gap-2.5">
                                  <img
                                    src={thread.author_avatar || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                                    alt={thread.author_name}
                                    className="w-6 h-6 rounded-full object-cover mt-0.5 shrink-0"
                                  />
                                  <div>
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <span className="font-bold text-[#FC4C02] text-[11px]">{thread.author_name}</span>
                                      <span className="text-[10px] text-zinc-500">{formatBeijingTime(thread.created_at, false)}</span>
                                    </div>
                                    <p className="text-zinc-200 mt-0.5 text-xs leading-relaxed">{thread.content}</p>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2.5 shrink-0">
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setReplyTargets((prev) => ({ ...prev, [act.id]: thread }))
                                    }
                                    className="text-[11px] font-bold text-[#FC4C02] hover:text-[#ff6426] transition cursor-pointer"
                                  >
                                    回复
                                  </button>
                                  {(thread.user_id === user?.id || currentRole === "owner") && (
                                    <button
                                      type="button"
                                      onClick={() => handleDeleteComment(act.id, thread.id)}
                                      className="text-[10px] text-zinc-500 hover:text-rose-400 transition cursor-pointer"
                                    >
                                      删除
                                    </button>
                                  )}
                                </div>
                              </div>

                              {/* Child Replies */}
                              {thread.replies && thread.replies.length > 0 && (
                                <div className="ml-6 pl-3 border-l-2 border-[#FC4C02]/35 space-y-2 pt-0.5">
                                  {thread.replies.map((rep: any) => (
                                    <div key={rep.id} className="flex items-start justify-between gap-3 text-xs">
                                      <div className="flex items-start gap-2">
                                        <img
                                          src={rep.author_avatar || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                                          alt={rep.author_name}
                                          className="w-5 h-5 rounded-full object-cover mt-0.5 shrink-0"
                                        />
                                        <div>
                                          <div className="flex items-center gap-1.5 flex-wrap">
                                            <span className="font-bold text-[#FC4C02] text-[11px]">{rep.author_name}</span>
                                            {rep.reply_to_name && (
                                              <>
                                                <span className="text-[10px] text-zinc-500">回复</span>
                                                <span className="font-semibold text-zinc-300 text-[11px]">@{rep.reply_to_name}</span>
                                              </>
                                            )}
                                            <span className="text-[10px] text-zinc-500">{formatBeijingTime(rep.created_at, false)}</span>
                                          </div>
                                          <p className="text-zinc-300 mt-0.5 text-xs leading-relaxed">{rep.content}</p>
                                        </div>
                                      </div>

                                      <div className="flex items-center gap-2 shrink-0">
                                        <button
                                          type="button"
                                          onClick={() =>
                                            setReplyTargets((prev) => ({ ...prev, [act.id]: rep }))
                                          }
                                          className="text-[11px] font-bold text-[#FC4C02] hover:text-[#ff6426] transition cursor-pointer"
                                        >
                                          回复
                                        </button>
                                        {(rep.user_id === user?.id || currentRole === "owner") && (
                                          <button
                                            type="button"
                                            onClick={() => handleDeleteComment(act.id, rep.id)}
                                            className="text-[10px] text-zinc-500 hover:text-rose-400 transition cursor-pointer"
                                          >
                                            删除
                                          </button>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Reply Target Indicator Banner */}
                      {replyTargets[act.id] && (
                        <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-xl bg-[#FC4C02]/10 border border-[#FC4C02]/30 text-xs">
                          <span className="text-zinc-300 truncate">
                            正在回复 <strong className="text-[#FC4C02]">@{replyTargets[act.id].author_name}</strong>：{replyTargets[act.id].content}
                          </span>
                          <button
                            type="button"
                            onClick={() =>
                              setReplyTargets((prev) => ({ ...prev, [act.id]: null }))
                            }
                            className="text-[11px] text-zinc-400 hover:text-white shrink-0 cursor-pointer"
                          >
                            取消回复 ✕
                          </button>
                        </div>
                      )}

                      {/* Coach Quick Critique Presets (Visible to Coach & Owner) */}
                      {(currentRole === "owner" || currentRole === "coach") && (
                        <div className="flex items-center gap-1.5 flex-wrap pt-1">
                          <span className="text-[11px] font-bold text-amber-300">🧢 教练快捷点评:</span>
                          {[
                            { label: "👏 配速稳·有氧佳", text: "🧢 教练点评：本次配速与心率控制非常稳，有氧基础扎实，继续保持！" },
                            { label: "⚠️ 心率偏高·排酸", text: "🧢 教练点评：本次心率偏高，明后天注意低心率排酸慢跑与保证充足睡眠恢复。" },
                            { label: "🔥 间歇完成度高", text: "🧢 教练点评：核心强度课完成质量很高！跑后务必做好臀腿拉伸与蛋白质补充。" },
                            { label: "💪 LSD耐力在线", text: "🧢 教练点评：长距离耐力在线，注意每5km补水补胶节奏，前半程严防起跑过快。" },
                          ].map((preset, pIdx) => (
                            <button
                              key={pIdx}
                              type="button"
                              onClick={() =>
                                setCommentInputs((prev) => ({ ...prev, [act.id]: preset.text }))
                              }
                              className="px-2.5 py-1 rounded-full bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/35 text-amber-200 text-[11px] font-bold transition cursor-pointer"
                            >
                              {preset.label}
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Post Comment Input Form */}
                      <div className="flex items-center gap-2 pt-1">
                        <input
                          type="text"
                          value={commentInputs[act.id] || ""}
                          onChange={(e) =>
                            setCommentInputs((prev) => ({ ...prev, [act.id]: e.target.value }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handlePostComment(act.id);
                          }}
                          placeholder={
                            replyTargets[act.id]
                              ? `回复 @${replyTargets[act.id].author_name}：聊聊配速、心率或加油互动...`
                              : "在 Canova教练评语后给队友鼓励或写句评语..."
                          }
                          className="flex-1 bg-[#121214] border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02]"
                        />
                        <button
                          onClick={() => handlePostComment(act.id)}
                          disabled={submittingComment[act.id] || !(commentInputs[act.id] || "").trim()}
                          className="flex items-center gap-1 px-4 py-2 bg-[#FC4C02] hover:bg-[#ff6426] disabled:opacity-40 text-white rounded-xl text-xs font-bold transition shadow-md shadow-[#FC4C02]/20"
                        >
                          <Send className="w-3.5 h-3.5" />
                          {replyTargets[act.id] ? "回复" : "发送"}
                        </button>
                      </div>
                    </div>
                  ))}

                  {/* Load more / Pagination Footer */}
                  <div className="pt-2 pb-2 text-center space-y-3">
                    {!isFeedExpanded && feed.length > 20 ? (
                      <button
                        onClick={() => setIsFeedExpanded(true)}
                        className="w-full py-3.5 px-4 rounded-2xl bg-[#141416] hover:bg-[#1a1a1e] border border-white/10 hover:border-[#FC4C02]/40 text-xs font-bold text-zinc-300 hover:text-white transition flex items-center justify-center gap-2 shadow-lg shadow-black/20"
                      >
                        <Flame className="w-4 h-4 text-[#FC4C02]" />
                        <span>加载更多（展开当月全部打卡 · 还有 {feed.length - 20} 条）</span>
                      </button>
                    ) : isFeedExpanded && feed.length > 20 ? (
                      <div className="space-y-3">
                        <div className="py-3 px-4 rounded-2xl bg-white/[0.02] border border-white/5 text-[11px] text-zinc-400 flex items-center justify-between">
                          <span className="flex items-center gap-1.5">
                            <Check className="w-3.5 h-3.5 text-emerald-500/80" />
                            已展示当月全部打卡记录（共 {feed.length} 条）
                          </span>
                          <button
                            onClick={() => setIsFeedExpanded(false)}
                            className="text-[#FC4C02] hover:underline flex items-center gap-1 font-bold text-xs"
                          >
                            <ChevronUp className="w-3.5 h-3.5" />
                            收起折叠
                          </button>
                        </div>
                        {hasMoreFeed && (
                          <button
                            onClick={handleLoadMoreFeed}
                            disabled={loadingMoreFeed}
                            className="w-full py-3 px-4 rounded-2xl bg-[#141416] hover:bg-[#1a1a1e] border border-white/10 hover:border-[#FC4C02]/40 text-xs font-bold text-zinc-400 hover:text-white transition flex items-center justify-center gap-2"
                          >
                            {loadingMoreFeed ? (
                              <>
                                <Loader2 className="w-4 h-4 animate-spin text-[#FC4C02]" />
                                <span>正在加载更早历史打卡...</span>
                              </>
                            ) : (
                              <>
                                <Clock className="w-4 h-4 text-zinc-400" />
                                <span>加载更早历史月份打卡（跑团共 {feedTotal} 条记录）</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="py-3 px-4 rounded-2xl bg-white/[0.02] border border-white/5 text-[11px] text-zinc-500 flex items-center justify-center gap-1.5">
                          <Check className="w-3.5 h-3.5 text-emerald-500/80" />
                          <span>已展示当月全部打卡记录（共 {feed.length} 条）</span>
                        </div>
                        {hasMoreFeed && (
                          <button
                            onClick={handleLoadMoreFeed}
                            disabled={loadingMoreFeed}
                            className="w-full py-2.5 px-4 rounded-2xl bg-[#141416] hover:bg-[#1a1a1e] border border-white/10 hover:border-[#FC4C02]/40 text-xs font-medium text-zinc-400 hover:text-white transition flex items-center justify-center gap-2"
                          >
                            {loadingMoreFeed ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-[#FC4C02]" />
                                <span>正在加载更早历史打卡...</span>
                              </>
                            ) : (
                              <>
                                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                                <span>加载更早历史月份打卡（跑团共 {feedTotal} 条记录）</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-zinc-500 text-center py-8">暂无队员近期打卡，快去完成今日跑步吧！</p>
              )}
            </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 2: 👥 跑团成员与管理 ── */}
        {activeTab === "president" && (currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
          <div className="space-y-6">
            {/* Club Lifecycle & Status Management (Only Owner & Admin) */}
            {(currentRole === "owner" || user?.is_admin) && (
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black text-white flex items-center gap-2">
                      <Shield className="w-5 h-5 text-amber-400" />
                      跑团运行状态与生命周期治理
                    </h2>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      管理【{currentClub?.name}】的运行状态（正常/暂停/锁定）或解散跑团
                    </p>
                  </div>

                  {/* Status Toggle Buttons */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      disabled={statusUpdating}
                      onClick={() => handleSetClubStatus("active")}
                      className={`px-3.5 py-2 rounded-2xl text-xs font-bold transition flex items-center gap-1.5 ${
                        (currentClub?.status || "active") === "active"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-lg shadow-emerald-500/10"
                          : "bg-white/5 hover:bg-white/10 text-zinc-400 border border-white/10"
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>🟢 正常运行</span>
                      {(currentClub?.status || "active") === "active" && <span>✓</span>}
                    </button>

                    <button
                      disabled={statusUpdating}
                      onClick={() => handleSetClubStatus("paused")}
                      className={`px-3.5 py-2 rounded-2xl text-xs font-bold transition flex items-center gap-1.5 ${
                        currentClub?.status === "paused"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-lg shadow-amber-500/10"
                          : "bg-white/5 hover:bg-white/10 text-zinc-400 border border-white/10"
                      }`}
                    >
                      <Pause className="w-3.5 h-3.5" />
                      <span>⏸️ 暂停跑团</span>
                      {currentClub?.status === "paused" && <span>✓</span>}
                    </button>

                    <button
                      disabled={statusUpdating}
                      onClick={() => handleSetClubStatus("locked")}
                      className={`px-3.5 py-2 rounded-2xl text-xs font-bold transition flex items-center gap-1.5 ${
                        currentClub?.status === "locked"
                          ? "bg-blue-500/20 text-blue-300 border border-blue-500/40 shadow-lg shadow-blue-500/10"
                          : "bg-white/5 hover:bg-white/10 text-zinc-400 border border-white/10"
                      }`}
                    >
                      <Lock className="w-3.5 h-3.5" />
                      <span>🔒 锁定跑团</span>
                      {currentClub?.status === "locked" && <span>✓</span>}
                    </button>
                  </div>
                </div>

                {/* Status Detailed Explanation */}
                <div className="p-4 rounded-2xl bg-[#18181c] border border-white/5 text-xs space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-400 font-medium">当前状态机制说明:</span>
                    {(currentClub?.status || "active") === "active" && (
                      <span className="text-emerald-400 font-bold">🟢 正常运行中</span>
                    )}
                    {currentClub?.status === "paused" && (
                      <span className="text-amber-400 font-bold">⏸️ 暂停运行中</span>
                    )}
                    {currentClub?.status === "locked" && (
                      <span className="text-blue-400 font-bold">🔒 锁定归档中</span>
                    )}
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">
                    {(currentClub?.status || "active") === "active" &&
                      "跑团各项功能全部开放，支持新队员加入与退出，队员跑步打卡与周月报实时汇总更新，对外公开可见。"}
                    {currentClub?.status === "paused" &&
                      "暂停跑团动态消息发布与活动挑战、暂停队员增删（禁止新成员加入或移除现有队员）、暂停数据统计更新，对外完全不可见。已有成员仍可浏览历史数据。"}
                    {currentClub?.status === "locked" &&
                      "只读归档状态：不允许队员增删（禁止新成员加入或移除现有队员），对外完全不可见。已有成员可正常浏览跑步数据与排行榜。"}
                  </p>
                </div>

                {/* Danger Zone: Dissolve Club */}
                <div className="pt-3 border-t border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <span className="text-xs font-bold text-red-400 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                      高危操作区：解散并永久删除跑团
                    </span>
                    <p className="text-[11px] text-zinc-500 mt-0.5">
                      解散跑团将永久清理群结构。🛡️ <strong>系统严格保障：全体队员个人运动数据、历史打卡与个人档案 100% 完整保留。</strong>
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setDissolveConfirmName("");
                      setShowDissolveModal(true);
                    }}
                    className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 border border-red-500/20 rounded-2xl text-xs font-bold transition flex items-center justify-center gap-1.5 shrink-0"
                  >
                    <Trash2 className="w-4 h-4" />
                    解散跑团
                  </button>
                </div>
              </div>
            )}

            {/* Club WeChat Invitation & Forwarding Card (Available to All Club Members, Coaches & Owners) */}
            {!currentClub?.is_virtual_unaffiliated && (
              <div className="bg-gradient-to-r from-emerald-500/10 via-[#121215] to-[#18181c] border border-emerald-500/30 rounded-3xl p-6 sm:p-7 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xl">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-emerald-500/20 text-emerald-300 border border-emerald-500/35">
                      💌 微信邀请中心
                    </span>
                    <h2 className="text-base sm:text-lg font-black text-white">
                      邀请微信好友加入【{currentClub?.name}】
                    </h2>
                  </div>
                  <p className="text-xs text-zinc-400">
                    一键生成含微信小程序码的高清入团邀请海报（支持直接 Ctrl+V / Cmd+V 粘贴到微信聊天框）或复制微信邀请口令与直达链接。
                  </p>
                </div>
                <div className="flex items-center gap-2.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => openClubInviteModal(currentClub)}
                    className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-[#22c55e] to-[#10b981] hover:from-[#4ade80] hover:to-[#34d399] text-black text-xs font-black transition shadow-lg shadow-emerald-500/20 cursor-pointer"
                  >
                    💌 生成跑团微信邀请函
                  </button>
                </div>
              </div>
            )}

            {/* Club Join Rule Settings (Owner, Coach & Admin) */}
            {(currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black text-white flex items-center gap-2">
                      <Shield className="w-5 h-5 text-[#FC4C02]" />
                      入团规则与准入门槛
                    </h2>

                    <p className="text-xs text-zinc-400 mt-0.5">
                      设定成员加入【{currentClub?.name}】的方式，选择自由入团或凭专属邀请码入团
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleUpdateJoinMode("free")}
                      className={`px-4 py-2 rounded-2xl text-xs font-bold transition flex items-center gap-1.5 ${
                        currentClub?.join_mode !== "invite"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-lg shadow-emerald-500/10"
                          : "bg-white/5 hover:bg-white/10 text-zinc-400 border border-white/10"
                      }`}
                    >
                      <span>🟢 自由入团（免邀请码）</span>
                      {currentClub?.join_mode !== "invite" && <span>✓</span>}
                    </button>
                    <button
                      onClick={() => handleUpdateJoinMode("invite")}
                      className={`px-4 py-2 rounded-2xl text-xs font-bold transition flex items-center gap-1.5 ${
                        currentClub?.join_mode === "invite"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-lg shadow-amber-500/10"
                          : "bg-white/5 hover:bg-white/10 text-zinc-400 border border-white/10"
                      }`}
                    >
                      <span>🔒 凭专属邀请码入团</span>
                      {currentClub?.join_mode === "invite" && <span>✓</span>}
                    </button>
                  </div>
                </div>

                {currentClub?.join_mode === "invite" && (
                  <div className="flex items-center justify-between bg-[#18181c] border border-amber-500/30 rounded-2xl p-4">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-zinc-400">本跑团专属 6 位邀请码：</span>
                      <span className="font-mono text-base font-black text-amber-400 tracking-wider">
                        {currentClub.invite_code || "请刷新页面查看"}
                      </span>
                    </div>
                    {currentClub?.invite_code && (
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(currentClub.invite_code);
                          alert("跑团邀请码已复制到剪贴板！");
                        }}
                        className="px-3 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-xs font-bold rounded-xl border border-amber-500/20 transition flex items-center gap-1"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        复制邀请码
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Club Weekly & Monthly Report Center (Owner, Coach & Admin) */}
            {(currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
              <div className="bg-gradient-to-br from-amber-500/10 via-[#121215] to-[#121215] border border-amber-500/30 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="p-2 rounded-2xl bg-amber-500/20 text-amber-300">
                        <BarChart3 className="w-5 h-5 text-amber-400" />
                      </span>
                      <h2 className="text-lg font-black text-white">
                        跑团周报与月报 · 战报转发中心
                      </h2>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-black tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        {currentRole === "coach" ? "🧢 教练专属" : (currentRole === "owner" ? "👑 团长专属" : "👑 团长 & 教练专属")}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">
                      自动聚合全团跑量、队员出勤率、荣耀前三领奖台与 Renato Canova 科学复盘，支持一键复制微信群排版与下载文本
                    </p>
                  </div>
                  <button
                    onClick={openClubReportModal}
                    className="px-5 py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-black font-black text-xs rounded-2xl shadow-lg shadow-amber-500/20 transition flex items-center gap-2 cursor-pointer self-start sm:self-auto"
                  >
                    <FileText className="w-4 h-4" />
                    查看与生成战报
                  </button>
                </div>
              </div>
            )}

            {/* New Members Onboarding & Watch/Goal Setup Status Panel */}
            {(currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
              <div className="bg-[#121215] border border-emerald-500/25 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black text-white flex items-center gap-2">
                      🌱 新队员与入团设定状态（加入时间 / 手表绑定 / 目标设定）
                    </h2>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      追踪新入团队员的加入时间、佳明/高驰/苹果/华为手表绑定状态与周/月跑量目标设定，支持一键提醒待完善队员
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {[
                      { id: "all", label: `全部 (${newMembersStatus.length})` },
                      { id: "new_30d", label: `🌱 近30天新入团 (${newMembersSummary?.new_30d_count ?? 0})` },
                      { id: "needs_setup", label: `⚠️ 待完善 (${newMembersSummary?.needs_setup_count ?? 0})` },
                      { id: "ready", label: `✅ 已配齐` },
                    ].map((f) => (
                      <button
                        key={f.id}
                        onClick={() => setNewMembersFilter(f.id as any)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
                          newMembersFilter === f.id
                            ? "bg-emerald-500 text-black"
                            : "bg-white/5 text-zinc-300 hover:bg-white/10"
                        }`}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 4 KPI summary cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-[#18181c] border border-emerald-500/25 rounded-2xl p-3.5">
                    <span className="text-[11px] text-emerald-400 font-bold">🌱 近7天新入团</span>
                    <div className="text-xl font-black text-white mt-0.5">
                      {newMembersSummary?.new_7d_count ?? 0} <span className="text-xs text-zinc-500">人</span>
                    </div>
                  </div>
                  <div className="bg-[#18181c] border border-cyan-500/25 rounded-2xl p-3.5">
                    <span className="text-[11px] text-cyan-400 font-bold">⌚ 手表已绑定</span>
                    <div className="text-xl font-black text-white mt-0.5">
                      {newMembersSummary?.watch_bound_count ?? 0}{" "}
                      <span className="text-xs text-zinc-500">/ {newMembersSummary?.total_members ?? newMembersStatus.length}</span>
                    </div>
                  </div>
                  <div className="bg-[#18181c] border border-purple-500/25 rounded-2xl p-3.5">
                    <span className="text-[11px] text-purple-400 font-bold">🎯 目标已设定</span>
                    <div className="text-xl font-black text-white mt-0.5">
                      {newMembersSummary?.goal_configured_count ?? 0}{" "}
                      <span className="text-xs text-zinc-500">/ {newMembersSummary?.total_members ?? newMembersStatus.length}</span>
                    </div>
                  </div>
                  <div className="bg-[#18181c] border border-amber-500/25 rounded-2xl p-3.5">
                    <span className="text-[11px] text-amber-400 font-bold">⚠️ 待完善设置</span>
                    <div className="text-xl font-black text-amber-400 mt-0.5">
                      {newMembersSummary?.needs_setup_count ?? 0} <span className="text-xs text-zinc-500">人</span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[460px] overflow-y-auto pr-1">
                  {newMembersStatus
                    .filter((m) => {
                      if (newMembersFilter === "new_30d") return m.is_new_30d;
                      if (newMembersFilter === "needs_setup") return !m.watch_bound || !m.goal_configured;
                      if (newMembersFilter === "ready") return m.watch_bound && m.goal_configured;
                      return true;
                    })
                    .map((m) => (
                      <div
                        key={m.user_id}
                        className="bg-[#18181c] border border-white/5 rounded-2xl p-4 flex flex-col justify-between gap-3"
                      >
                        <div className="space-y-3">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-3 min-w-0">
                              <img
                                src={m.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                                alt={m.display_name}
                                className="w-10 h-10 rounded-full object-cover border border-white/10 shrink-0"
                              />
                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="font-bold text-white text-xs truncate">{m.display_name}</span>
                                  <span className="px-1.5 py-0.5 rounded bg-white/5 text-zinc-400 text-[10px]">
                                    {m.role === "owner" ? "👑 团长" : m.role === "coach" ? "🧢 教练" : "🏃 队员"}
                                  </span>
                                </div>
                                <div className="text-[11px] text-zinc-400 mt-0.5">
                                  ⏰ 加入时间：<span className="text-zinc-200 font-mono">{m.joined_at_display}</span>
                                </div>
                              </div>
                            </div>
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold shrink-0 ${
                                m.is_new_7d
                                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                  : m.is_new_30d
                                  ? "bg-cyan-500/15 text-cyan-300"
                                  : "bg-white/5 text-zinc-400"
                              }`}
                            >
                              {m.join_recency_label}
                            </span>
                          </div>

                          <div className="grid grid-cols-2 gap-2.5 text-xs">
                            <div
                              className={`p-2.5 rounded-xl border ${
                                m.watch_bound
                                  ? "bg-emerald-500/10 border-emerald-500/30"
                                  : "bg-amber-500/10 border-amber-500/30"
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="text-zinc-400 font-semibold">⌚ 手表绑定</span>
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    m.watch_bound ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
                                  }`}
                                >
                                  {m.watch_bound ? "已绑定" : "未绑定"}
                                </span>
                              </div>
                              <div className="text-[11px] text-zinc-200 mt-1 truncate">{m.watch_status_detail}</div>
                            </div>

                            <div
                              className={`p-2.5 rounded-xl border ${
                                m.goal_configured
                                  ? "bg-emerald-500/10 border-emerald-500/30"
                                  : "bg-amber-500/10 border-amber-500/30"
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="text-zinc-400 font-semibold">🎯 目标设定</span>
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    m.goal_configured ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
                                  }`}
                                >
                                  {m.goal_configured_label}
                                </span>
                              </div>
                              <div className="text-[11px] text-zinc-200 mt-1 truncate">{m.goal_status_detail}</div>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/5">
                          {(!m.watch_bound || !m.goal_configured) && (
                            <button
                              onClick={() => handleRemindMemberSetup(m.user_id, m.display_name)}
                              disabled={remindingMemberUid === m.user_id}
                              className="px-3 py-1.5 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-xs font-bold transition"
                            >
                              {remindingMemberUid === m.user_id ? "发送中..." : "🔔 提醒完善绑表/目标"}
                            </button>
                          )}
                          <button
                            onClick={() => router.push(`/dashboard/analysis?student_user_id=${encodeURIComponent(m.user_id)}`)}
                            className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-200 text-xs font-bold transition"
                          >
                            📊 查看跑力档案
                          </button>
                          {(currentRole === "owner" || user?.is_admin) &&
                            !currentClub?.is_virtual_unaffiliated &&
                            m.role !== "owner" &&
                            m.user_id !== user?.id && (
                              <button
                                onClick={() => handleRemoveMember(m.user_id, m.display_name)}
                                className="px-3 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs font-bold transition"
                              >
                                🚪 移出
                              </button>
                            )}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            <div className="bg-[#121215] border border-white/5 rounded-3xl p-6 sm:p-8">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-lg font-black text-white flex items-center gap-2">
                    <Users className="w-5 h-5 text-amber-400" />
                    跑团成员与权限管理
                  </h2>
                  <p className="text-xs text-zinc-400 mt-0.5">管理跑团跑者成员、指定/撤销认证教练、移交团长或移除成员</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-zinc-400">共 <strong className="text-white">{members.length}</strong> 位团员</span>
                  {(currentRole === "owner" || user?.is_admin) && (
                    <button
                      onClick={() => {
                        setEditingEvent(null);
                        setEventTitle("");
                        setEventTargetKm(200);
                        setEventRules("");
                        setShowCreateEventModal(true);
                      }}
                      className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-amber-600/20"
                    >
                      + 发起跑团挑战赛
                    </button>
                  )}
                </div>
              </div>

              {/* Members Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/10 text-[11px] font-bold text-zinc-400 uppercase">
                      <th className="py-3 px-4">跑者</th>
                      <th className="py-3 px-4">当前角色</th>
                      <th className="py-3 px-4">月跑量计划与完成度</th>
                      <th className="py-3 px-4">全马 PB</th>
                      <th className="py-3 px-4">加入时间</th>
                      <th className="py-3 px-4 text-right">管理操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-xs font-medium text-zinc-300">
                    {members.map((m) => (
                      <tr key={m.user_id} className="hover:bg-white/[0.02]">
                        <td className="py-3.5 px-4 flex items-center gap-3">
                          <img
                            src={m.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                            alt={m.display_name}
                            className="w-8 h-8 rounded-full object-cover"
                          />
                          <div>
                            <span className="font-bold text-white block">{m.display_name}</span>
                            <span className="text-[10px] text-zinc-500">{m.user_id}</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            m.role === "owner" ? "bg-amber-500/20 text-amber-300" : m.role === "coach" ? "bg-purple-500/20 text-purple-300" : "bg-zinc-800 text-zinc-400"
                          }`}>
                            {m.role === "owner" ? "👑 团长" : m.role === "coach" ? "🧢 教练" : "普通跑者"}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-white text-xs">{m.month_km || 0} / {m.target_km || 200} km</span>
                            <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold ${
                              (m.completion_rate || 0) >= 100 ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-zinc-400"
                            }`}>
                              {m.completion_rate || 0}%
                            </span>
                          </div>
                          <div className="w-32 bg-white/10 h-1.5 rounded-full overflow-hidden mt-1.5">
                            <div
                              className={`h-full rounded-full transition-all ${
                                (m.completion_rate || 0) >= 100 ? "bg-emerald-400" : "bg-[#FC4C02]"
                              }`}
                              style={{ width: `${Math.min(100, Math.max(2, m.completion_rate || 0))}%` }}
                            />
                          </div>
                        </td>
                        <td className="py-3.5 px-4 font-mono text-zinc-300">{formatPb(m.marathon_pb)}</td>
                        <td className="py-3.5 px-4 text-zinc-400">{m.joined_at?.slice(0, 10)}</td>
                        <td className="py-3.5 px-4 text-right space-x-2">
                          {(currentRole === "owner" || user?.is_admin) ? (
                            <>
                              {m.role !== "owner" ? (
                                <>
                                  {m.role !== "coach" ? (
                                    <button
                                      onClick={() => handleUpdateMemberRole(m.user_id, "coach")}
                                      className="px-2.5 py-1 bg-purple-600/30 hover:bg-purple-600 text-purple-200 hover:text-white rounded-lg text-[11px] font-bold transition"
                                      title="指定为认证教练"
                                    >
                                      设为教练
                                    </button>
                                  ) : (
                                    <button
                                      onClick={() => handleUpdateMemberRole(m.user_id, "member")}
                                      className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-[11px] font-bold transition"
                                      title="取消教练权限"
                                    >
                                      取消教练
                                    </button>
                                  )}

                                  <button
                                    onClick={() => handleTransferOwner(m.user_id, m.display_name)}
                                    className="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/25 text-amber-300 rounded-lg text-[11px] font-bold transition"
                                    title="移交团长身份"
                                  >
                                    移交团长
                                  </button>

                                  <button
                                    onClick={() => handleRemoveMember(m.user_id, m.display_name)}
                                    className="px-2.5 py-1 bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 hover:text-rose-300 rounded-lg text-[11px] font-bold transition inline-flex items-center gap-1"
                                    title="将该跑者移出跑团"
                                  >
                                    <UserMinus className="w-3 h-3" />
                                    移除
                                  </button>
                                </>
                              ) : (
                                <span className="text-[11px] text-amber-400 font-bold">最高管理者</span>
                              )}
                            </>
                          ) : (
                            <span className="text-[11px] text-zinc-500">仅团长可管理</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 3: 🧢 教练学员体能监控与计划罗盘 ── */}
        {activeTab === "coach" && currentRole !== "owner" && currentRole !== "coach" && !user?.is_admin && (
          <div className="bg-[#121215] border border-purple-500/30 rounded-3xl p-8 sm:p-12 text-center max-w-2xl mx-auto shadow-2xl space-y-5 my-4">
            <div className="w-16 h-16 rounded-3xl bg-purple-500/20 text-purple-300 flex items-center justify-center mx-auto text-3xl">
              🧢
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-black text-white">跑团教练集中工作台</h2>
              <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
                本工作台仅对跑团【认证教练】与【团长】开放，整合配速与专项分组模版库（240精英/A~E组/戈壁竞赛/长距离越野/教练跨跑团专属模版）、20人流水线排课审阅、全队体能罗盘、队员打卡点评与周/月战报。如需在【{currentClub?.name}】开通教练权限，请联系跑团团长在成员管理中为您授权。
              </p>
            </div>
            <div className="flex items-center justify-center gap-3 flex-wrap pt-2">
              <button
                onClick={() => router.push("/dashboard/coach")}
                className="px-5 py-2.5 rounded-xl bg-[#FC4C02] hover:bg-[#ff6426] text-white text-xs font-bold transition cursor-pointer"
              >
                🏃 前往我的个人训练课表
              </button>
              <button
                onClick={() => setActiveTab("leaderboard")}
                className="px-5 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-white text-xs font-bold transition cursor-pointer"
              >
                🏆 查看跑团英雄榜与打卡动态
              </button>
            </div>
          </div>
        )}
        {activeTab === "coach" && (currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
          <div className="space-y-6">
            {currentClub?.id && user?.id && (
              <PacerClubRadarPanel
                clubId={currentClub.id}
                operatorUid={user.id}
                clubName={currentClub.name}
              />
            )}
            {/* Status Summary Cards (Clickable Filters) */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div
                onClick={() => setCoachStatusFilter(coachStatusFilter === "peak" ? "all" : "peak")}
                className={`border rounded-3xl p-5 cursor-pointer transition ${
                  coachStatusFilter === "peak"
                    ? "bg-emerald-500/15 border-emerald-400 shadow-lg shadow-emerald-500/10"
                    : "bg-[#121215] border-emerald-500/30 hover:border-emerald-500/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-emerald-400 font-bold">🟢 巅峰状态 (TSB &gt; 5)</span>
                  {coachStatusFilter === "peak" && <span className="text-[10px] text-emerald-300 font-bold">✓ 筛选中</span>}
                </div>
                <div className="text-2xl font-black text-white mt-1">
                  {coachCockpit?.summary?.peak_count || 0} <span className="text-xs text-zinc-500">人</span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">适宜安排比赛测速或高强度课</p>
              </div>

              <div
                onClick={() => setCoachStatusFilter(coachStatusFilter === "optimal" ? "all" : "optimal")}
                className={`border rounded-3xl p-5 cursor-pointer transition ${
                  coachStatusFilter === "optimal"
                    ? "bg-blue-500/15 border-blue-400 shadow-lg shadow-blue-500/10"
                    : "bg-[#121215] border-blue-500/30 hover:border-blue-500/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-blue-400 font-bold">🔵 专项适应 (TSB -30~5)</span>
                  {coachStatusFilter === "optimal" && <span className="text-[10px] text-blue-300 font-bold">✓ 筛选中</span>}
                </div>
                <div className="text-2xl font-black text-white mt-1">
                  {coachCockpit?.summary?.optimal_count || 0} <span className="text-xs text-zinc-500">人</span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">身体良好吸收负荷，按计划推进</p>
              </div>

              <div
                onClick={() => setCoachStatusFilter(coachStatusFilter === "tired" ? "all" : "tired")}
                className={`border rounded-3xl p-5 cursor-pointer transition ${
                  coachStatusFilter === "tired"
                    ? "bg-amber-500/15 border-amber-400 shadow-lg shadow-amber-500/10"
                    : "bg-[#121215] border-amber-500/30 hover:border-amber-500/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-amber-400 font-bold">🟡 疲劳积累 (TSB -50~-30)</span>
                  {coachStatusFilter === "tired" && <span className="text-[10px] text-amber-300 font-bold">✓ 筛选中</span>}
                </div>
                <div className="text-2xl font-black text-white mt-1">
                  {coachCockpit?.summary?.tired_count || 0} <span className="text-xs text-zinc-500">人</span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">建议穿插低心率排酸轻松跑</p>
              </div>

              <div
                onClick={() => setCoachStatusFilter(coachStatusFilter === "danger" ? "all" : "danger")}
                className={`border rounded-3xl p-5 cursor-pointer transition ${
                  coachStatusFilter === "danger"
                    ? "bg-rose-500/15 border-rose-400 shadow-lg shadow-rose-500/10"
                    : "bg-[#121215] border-rose-500/30 hover:border-rose-500/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-rose-400 font-bold">🔴 伤病预警 (TSB &lt; -50)</span>
                  {coachStatusFilter === "danger" && <span className="text-[10px] text-rose-300 font-bold">✓ 筛选中</span>}
                </div>
                <div className="text-2xl font-black text-white mt-1">
                  {coachCockpit?.summary?.danger_count || 0} <span className="text-xs text-zinc-500">人</span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">过度训练风险，需强制休整</p>
              </div>
            </div>

            {/* ── Coach Workbench Hub: 模版货架 + 核心动作 + 精简筛选 ── */}
            <div className="bg-[#131318] border border-white/10 rounded-3xl p-5 sm:p-6 shadow-xl space-y-5">
              {/* Row 1: Title + Primary Actions */}
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="text-base sm:text-lg font-black text-white flex items-center gap-2">
                    🧢 排课工作台
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                      本周执行率 {coachCockpit?.summary?.avg_week_compliance || 0}%
                    </span>
                  </h3>
                  <p className="text-xs text-zinc-500 mt-1">① 选模版 → ② 选队员 → ③ 派发（草案可逐人微调后发布）</p>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => setShowScheduleImportModal(true)}
                    className="px-3.5 py-2 rounded-xl text-xs font-bold bg-[#FC4C02] hover:bg-[#ff5a14] text-white transition flex items-center gap-1.5 cursor-pointer"
                    title="助理教练/主教练上传周课表截图或Excel文字，自动拆解A~E组/男女组并一键派发给对应队员"
                  >
                    识图导入周课表
                  </button>
                  <button
                    onClick={() => openTemplateAssignModal()}
                    className="px-3.5 py-2 rounded-xl text-xs font-medium bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 transition flex items-center gap-1.5 cursor-pointer"
                  >
                    模版派发
                  </button>
                  {sortedCoachStudents.length > 0 && (
                    <button
                      onClick={() => setSelectedStudentForPlan(sortedCoachStudents[0])}
                      className="px-3.5 py-2 rounded-xl text-xs font-medium bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 transition flex items-center gap-1.5 cursor-pointer"
                      title="按当前筛选顺序逐个审核、微调并发布队员课表"
                    >
                      逐人批阅 ({sortedCoachStudents.length})
                    </button>
                  )}
                  <button
                    onClick={() => setShowBroadcastModal(true)}
                    className="px-3.5 py-2 rounded-xl text-xs font-medium bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 transition flex items-center gap-1.5 cursor-pointer"
                    title="把跑团公共合练课（如周二间歇课、周末长距离）同步写入全体队员当周课表"
                  >
                    合练课派发
                  </button>
                  <button
                    onClick={() => {
                      const next = !showBatchHistoryPanel;
                      setShowBatchHistoryPanel(next);
                      if (next) loadClubPlanBatches(currentClub?.id);
                    }}
                    className={`px-3.5 py-2 rounded-xl text-xs font-medium border transition flex items-center gap-1.5 cursor-pointer ${
                      showBatchHistoryPanel
                        ? "bg-[#FC4C02] text-white border-[#FC4C02] font-bold"
                        : "bg-white/5 hover:bg-white/10 text-zinc-200 border-white/10"
                    }`}
                    title="查看近期识图导入或模版批量派发记录，支持整批一键撤回并恢复队员原课表"
                  >
                    派发记录与回退
                  </button>
                  <div className="relative group">
                    <button
                      onClick={() => handleBatchGenerateClubDrafts(true)}
                      disabled={batchGeneratingDrafts}
                      className="px-3.5 py-2 rounded-xl text-xs font-medium bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                      title="根据每位未排课队员的目标赛事、周跑量与体能状态，自动生成个性化草案"
                    >
                      {batchGeneratingDrafts ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                      {batchGeneratingDrafts ? "生成中..." : "智能草案 (未排课)"}
                    </button>
                    {!batchGeneratingDrafts && (
                      <div className="absolute right-0 top-full pt-1 hidden group-hover:block z-20">
                        <button
                          onClick={() => {
                            if (confirm("为全团所有成员重新生成新周期待审草案？（不影响正在执行的计划，审核发布后才切换）")) {
                              handleBatchGenerateClubDrafts(false);
                            }
                          }}
                          className="whitespace-nowrap px-3 py-2 rounded-xl text-[11px] font-medium bg-[#18181c] hover:bg-white/10 text-zinc-300 border border-white/10 shadow-xl cursor-pointer"
                        >
                          ↻ 全团重制新周期草案
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Collapsible Batch Dispatch History & 1-Click Rollback Panel */}
              {showBatchHistoryPanel && (
                <div className="bg-[#18181c] border border-white/10 rounded-2xl p-4 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <h4 className="text-xs sm:text-sm font-bold text-white flex items-center gap-2">
                        跑团课表批量派发记录与一键撤回
                      </h4>
                      <p className="text-[11px] text-zinc-400 mt-0.5">
                        支持按批次撤回「识图导入周课表」或「模版批量派发」，自动清理误派发的草案并将队员正在执行的课表恢复至派发前状态（保留打卡记录）
                      </p>
                    </div>
                    <button
                      onClick={() => setShowBatchHistoryPanel(false)}
                      className="text-xs text-zinc-400 hover:text-white cursor-pointer shrink-0"
                    >
                      收起 ✕
                    </button>
                  </div>

                  {loadingClubBatches ? (
                    <div className="py-4 text-center text-xs text-zinc-400">正在加载最近派发批次...</div>
                  ) : clubPlanBatches.length === 0 ? (
                    <div className="py-4 text-center text-xs text-zinc-500">
                      暂无可撤回的批量派发批次（您也可以在下方每位队员卡片上直接点击【撤回此草案】或【回退上一版】）
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                      {clubPlanBatches.map((b: any) => (
                        <div
                          key={b.batch_id}
                          className="p-3 rounded-xl bg-[#121215] border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-white">{b.action_label || "批量派发课表"}</span>
                              <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 text-[10px] font-medium">
                                涉及 {b.affected_users_count} 人
                              </span>
                              <span className="text-[10px] text-zinc-500 font-mono">
                                {formatBeijingTime(b.created_at, true)}
                              </span>
                            </div>
                            <div className="text-[11px] text-zinc-400">
                              队员：{(b.affected_users || []).map((u: any) => `${u.display_name}`).join("、")}
                            </div>
                          </div>
                          <button
                            onClick={() => {
                              if (
                                window.confirm(
                                  `确认整批撤回「${b.action_label}」（共 ${b.affected_users_count} 位队员）吗？\n撤回后将自动移除本次草案或恢复队员派发前的原训练计划。`
                                )
                              ) {
                                handleRollbackClubBatch(b.batch_id);
                              }
                            }}
                            disabled={rollingBackBatchId === b.batch_id}
                            className="px-3.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-200 font-bold text-xs transition shrink-0 cursor-pointer disabled:opacity-50"
                          >
                            {rollingBackBatchId === b.batch_id ? "正在撤回..." : "整批撤回"}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Row 2: Template Shelf (all templates visible at a glance, one click to distribute) */}
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold text-zinc-300">训练模版</span>
                  <div className="flex items-center gap-3 text-[11px]">
                    <span className="text-zinc-500 hidden sm:inline">每周按 Canova 周期自动递进 · 点击卡片即可派发</span>
                    <button
                      onClick={() => openTemplateAssignModal(undefined, undefined, "custom")}
                      className="font-medium text-zinc-300 hover:text-white cursor-pointer"
                    >
                      我的模版 ({coachTemplates.filter((t: any) => t.is_custom).length}) →
                    </button>
                  </div>
                </div>
                {loadingTemplates && coachTemplates.length === 0 ? (
                  <div className="py-6 text-center text-xs text-zinc-500 flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-zinc-400" /> 正在加载模版...
                  </div>
                ) : (
                  <div className="flex gap-2.5 overflow-x-auto pb-1.5 snap-x">
                    {coachTemplates.map((tpl: any) => {
                      const rec = templateRecCountMap[tpl.id] || 0;
                      const inUse = (coachCockpit?.students || []).filter(
                        (s: any) => s.plan_info?.template_id === tpl.id || s.plan_info?.template_group_code === tpl.group_code
                      ).length;
                      return (
                        <button
                          key={tpl.id}
                          onClick={() => openTemplateAssignModal(tpl.id)}
                          className="snap-start shrink-0 w-48 text-left p-3 rounded-2xl bg-[#18181c] border border-white/10 hover:border-white/25 transition cursor-pointer group/tpl"
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span className="text-xs font-bold text-white truncate">{tpl.short_name}</span>
                            {tpl.is_custom && <span className="text-[9px] text-zinc-400 shrink-0">自建</span>}
                          </div>
                          <div className="text-[10px] text-zinc-400 mt-1 truncate">{tpl.target_pb_label}</div>
                          <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-zinc-400">
                            <span>{tpl.weekly_km}km · {tpl.days_per_week}练</span>
                            <span className="flex items-center gap-1">
                              {rec > 0 && <span className="px-1.5 rounded bg-white/5 text-zinc-300 font-medium">荐{rec}</span>}
                              {inUse > 0 && <span className="px-1.5 rounded bg-white/5 text-zinc-300">用{inUse}</span>}
                            </span>
                          </div>
                          <div className="mt-2 text-[10px] font-bold text-[#FC4C02] opacity-0 group-hover/tpl:opacity-100 transition">
                            派发给队员 →
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Row 3: Compact Filters */}
              <div className="pt-4 border-t border-white/10 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="flex items-center gap-1.5 flex-wrap">
                  {[
                    { key: "all", label: `全部 ${coachCockpit?.summary?.total_students || 0}` },
                    { key: "alert", label: `预警 ${(coachCockpit?.summary?.injury_alert_count || 0) + (coachCockpit?.summary?.low_hrv_alert_count || 0)}` },
                    { key: "draft_pending", label: `待审核 ${coachCockpit?.summary?.plans_draft_count || 0}` },
                    { key: "published", label: `执行中 ${coachCockpit?.summary?.plans_published_count || 0}` },
                    { key: "none", label: `未排课 ${coachCockpit?.summary?.plans_none_count || 0}` },
                  ].map((f) => (
                    <button
                      key={f.key}
                      onClick={() => setCoachPlanFilter(f.key === "all" || coachPlanFilter === f.key ? "all" : (f.key as any))}
                      className={`px-3 py-1.5 rounded-lg text-xs transition cursor-pointer ${
                        coachPlanFilter === f.key
                          ? "bg-[#FC4C02] text-white font-bold"
                          : "bg-white/5 text-zinc-400 border border-white/10 hover:text-white font-medium"
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <select
                    value={coachGroupFilter}
                    onChange={(e) => setCoachGroupFilter(e.target.value)}
                    className="bg-[#18181c] border border-white/10 rounded-xl px-2.5 py-1.5 text-xs text-white outline-none focus:border-white/25"
                    title="按组别筛选队员"
                  >
                    <option value="all">全部组别</option>
                    {Array.from(new Set(coachTemplates.map((t: any) => t.group_code).filter(Boolean))).map((code: any) => {
                      const cnt = (coachCockpit?.students || []).filter(
                        (s: any) => s.plan_info?.template_group_code === code || s.recommended_group?.group_code === code
                      ).length;
                      return (
                        <option key={code} value={code}>
                          {code} ({cnt})
                        </option>
                      );
                    })}
                  </select>
                  <input
                    type="text"
                    value={coachSearchQuery}
                    onChange={(e) => setCoachSearchQuery(e.target.value)}
                    placeholder="搜索队员"
                    className="bg-[#18181c] border border-white/10 rounded-xl px-3 py-1.5 text-xs text-white focus:border-white/25 outline-none w-32 sm:w-40"
                  />
                </div>
              </div>
            </div>

            {/* Students Matrix Table */}
            <div className="bg-[#121215] border border-white/5 rounded-3xl p-6 sm:p-8">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Shield className="w-5 h-5 text-zinc-400" />
                    全队学员训练计划审核、周执行打卡与生理负荷监控
                  </h2>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    点击【审核/管理训练计划】可查看或微调课表，支持整周加减量、单日配速/距离微调与一键发布给队员
                  </p>
                </div>

                {/* Right controls: Report button & TSB sort switcher */}
                <div className="flex items-center gap-3 flex-wrap">
                  <button
                    onClick={openClubReportModal}
                    className="px-3.5 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-200 font-medium text-xs rounded-xl transition flex items-center gap-1.5 cursor-pointer"
                  >
                    <FileText className="w-3.5 h-3.5" />
                    制作跑团周报/月报
                  </button>

                  <div className="flex items-center gap-1 p-1 bg-white/5 rounded-xl border border-white/10 text-xs">
                    <span className="text-[11px] text-zinc-400 pl-2">TSB排序:</span>
                    <button
                      onClick={() => setCoachSortOrder("danger_first")}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                        coachSortOrder === "danger_first"
                          ? "bg-[#FC4C02] text-white font-bold"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      预警优先
                    </button>
                    <button
                      onClick={() => setCoachSortOrder("peak_first")}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition ${
                        coachSortOrder === "peak_first"
                          ? "bg-[#FC4C02] text-white font-bold"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      巅峰优先
                    </button>
                  </div>

                  {(coachStatusFilter !== "all" || coachPlanFilter !== "all") && (
                    <button
                      onClick={() => {
                        setCoachStatusFilter("all");
                        setCoachPlanFilter("all");
                      }}
                      className="text-xs text-zinc-400 hover:text-white px-2 py-1 bg-white/5 rounded-lg border border-white/10"
                    >
                      ✕ 清除筛选
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-5">
                {sortedCoachStudents.map((student: any) => {
                  const pInfo = student.plan_info || {};
                  const weekExec = pInfo.week_execution;
                  const pState = pInfo.plan_state || "none";

                  return (
                    <div
                      key={student.user_id}
                      className="p-6 bg-[#18181c] border border-white/10 hover:border-white/20 rounded-2xl flex flex-col gap-4 transition shadow-lg"
                    >
                      {/* Top Row: Info + Badges */}
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                          <img
                            src={student.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                            alt={student.display_name}
                            className="w-12 h-12 rounded-full object-cover border border-white/10"
                          />
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-base font-bold text-white">{student.display_name}</span>
                              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                                {student.status_text}
                              </span>
                              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                                {student.canova_phase || "基础准备期"}
                              </span>
                              {/* Goal Race Pill */}
                              {student.goal_race && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                                  备战: {student.goal_race.name}
                                  {(student.goal_race.days_until ?? student.goal_race.days_left) != null ? ` (${student.goal_race.days_until ?? student.goal_race.days_left}天后)` : ""}
                                </span>
                              )}
                              {/* Plan Status Pill */}
                              {pState === "draft_pending" && (
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#FC4C02]/15 text-[#FC4C02] border border-[#FC4C02]/30">
                                  有待审草案
                                </span>
                              )}
                              {pState === "published" && (
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                                  已发布 ({pInfo.reviewed_by_name || "认证教练"})
                                </span>
                              )}
                              {pState === "self_active" && (
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                                  个人计划执行中
                                </span>
                              )}
                              {pState === "none" && (
                                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-zinc-400 border border-white/10">
                                  尚未排课
                                </span>
                              )}
                              {/* Demographic Age & Gender Badge */}
                              {(student.gender_label || student.age) && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                                  {student.gender_label === "女" ? "女" : student.gender_label === "男" ? "男" : ""}
                                  {student.age ? `${student.gender_label ? " · " : ""}${student.age}岁` : ""}
                                  {student.age && student.age >= 45 && student.age_group_label ? ` (${student.age_group_label})` : ""}
                                </span>
                              )}
                              {/* Template Group Pill (Assigned or Recommended) */}
                              {pInfo.template_group_code ? (
                                <button
                                  onClick={() => openTemplateAssignModal(pInfo.template_id, student.user_id)}
                                  className="px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 transition cursor-pointer"
                                  title="点击更换或重新分配配速组别训练模版"
                                >
                                  当前组别: {pInfo.template_group_code}
                                </button>
                              ) : student.recommended_group ? (
                                <button
                                  onClick={() => openTemplateAssignModal(student.recommended_group.template_id, student.user_id)}
                                  className="px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 transition cursor-pointer"
                                  title={`${student.recommended_group.reason || "智能推荐分组"} · 点击一键套用该组别标准训练模版`}
                                >
                                  推荐: {student.recommended_group.group_name}
                                  {student.recommended_group.recommended_scale && student.recommended_group.recommended_scale < 1
                                    ? ` (${Math.round(student.recommended_group.recommended_scale * 100)}%负荷)`
                                    : ""}
                                </button>
                              ) : null}
                            </div>
                            <div className="flex items-center gap-3 text-xs text-zinc-400 mt-1.5 flex-wrap">
                              <span>全马 PB: <strong className="text-white font-mono">{formatPb(student.marathon_pb)}</strong></span>
                              {student.half_pb && (
                                <>
                                  <span>·</span>
                                  <span>半马: <strong className="text-zinc-200 font-mono">{formatPb(student.half_pb)}</strong></span>
                                </>
                              )}
                              <span>·</span>
                              <span>周目标: <strong className="text-white font-mono">{student.weekly_target || Math.round((student.target_km || 200) / 4)} km</strong></span>
                              <span>·</span>
                              <span>静息心率: <strong className="text-zinc-300 font-mono">{student.resting_heart_rate ? `${student.resting_heart_rate} bpm` : "—"}</strong></span>
                              <span>·</span>
                              <span>夜间 HRV: <strong className="text-zinc-300 font-mono">{student.hrv_ms ? `${student.hrv_ms} ms` : "—"}</strong></span>
                            </div>
                            {student.recommended_group?.reason && (
                              <div className="mt-1.5 text-[11px] text-zinc-400 bg-white/[0.03] border border-white/10 rounded-lg px-2.5 py-1 leading-relaxed">
                                分组依据：{student.recommended_group.reason}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Right: CTL/ATL/TSB Badges + Plan Review & Report Triggers */}
                        <div className="flex items-center gap-2 self-start md:self-auto flex-wrap">
                          <div className="flex items-center gap-3 bg-[#121215] px-3.5 py-2 rounded-xl border border-white/10">
                            <div className="text-center">
                              <span className="text-[10px] text-zinc-500 block">CTL 体能</span>
                              <span className="text-xs font-bold text-zinc-200 font-mono">
                                {student.ctl > 0 ? student.ctl : "—"}
                              </span>
                            </div>
                            <div className="text-center">
                              <span className="text-[10px] text-zinc-500 block">ATL 疲劳</span>
                              <span className="text-xs font-bold text-zinc-200 font-mono">
                                {student.atl > 0 ? student.atl : "—"}
                              </span>
                            </div>
                            <div className="text-center">
                              <span className="text-[10px] text-zinc-500 block">TSB 状况</span>
                              <span className="text-xs font-bold text-zinc-200 font-mono">
                                {student.ctl > 0 || student.atl > 0 ? (student.tsb > 0 ? `+${student.tsb}` : student.tsb) : "—"}
                              </span>
                            </div>
                          </div>

                          {/* Primary Coach Action: Plan Review / Customize / Execution */}
                          <button
                            onClick={() => setSelectedStudentForPlan(student)}
                            className="px-3.5 py-2 rounded-xl text-xs font-bold bg-[#FC4C02] hover:bg-[#ff5a14] text-white transition flex items-center gap-1.5 cursor-pointer"
                          >
                            <ClipboardCheck className="w-3.5 h-3.5" />
                            {pState === "draft_pending"
                              ? "审核草案"
                              : pInfo.has_active_plan
                              ? "审阅调课"
                              : "制定课表"}
                          </button>

                          <button
                            onClick={() => setSelectedStudentForReport(student)}
                            className="px-3 py-2 bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white rounded-xl text-xs font-medium transition flex items-center gap-1.5 border border-white/10 cursor-pointer"
                          >
                            <FileText className="w-3.5 h-3.5" />
                            诊断报告
                          </button>

                          <button
                            onClick={() => router.push(`/dashboard/analysis?student_user_id=${encodeURIComponent(student.user_id)}`)}
                            className="px-3 py-2 bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white rounded-xl text-xs font-medium transition flex items-center gap-1.5 border border-white/10 cursor-pointer"
                            title="调阅该队员的有效 VDOT、耐力保持系数、Canova 五维矩阵与 30 天生理趋势"
                          >
                            生理与VDOT
                          </button>
                        </div>
                      </div>

                      {/* ── Pending Draft Confirmation / Rollback Strip (Strictly Isolated from Active Plan) ── */}
                      {pInfo.has_draft_plan && (
                        <div className="bg-[#121215] border border-white/10 rounded-xl px-4 py-3 flex flex-col lg:flex-row lg:items-center justify-between gap-3 text-xs">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#FC4C02]/15 text-[#FC4C02] border border-[#FC4C02]/30">
                                待审草案（未生效）
                              </span>
                              <span className="font-bold text-white">
                                {pInfo.draft_plan_title || "新派发待审草案"}
                              </span>
                              {pInfo.draft_source_label && (
                                <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[10px] font-medium text-zinc-300">
                                  {pInfo.draft_source_label}
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-zinc-400">
                              队员当前仍按下方正式课表「{pInfo.active_plan_title || pInfo.title || "当前计划"}」执行打卡，确认转正前不会覆盖原课表。
                            </p>
                          </div>

                          <div className="flex items-center gap-2 shrink-0 flex-wrap">
                            <button
                              onClick={() => setSelectedStudentForPlan(student)}
                              className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-200 font-medium text-xs border border-white/10 transition cursor-pointer"
                            >
                              对比 / 微调草案
                            </button>
                            <button
                              onClick={() => handleQuickPublishStudentDraft(student)}
                              disabled={publishingDraftUid === student.user_id}
                              className="px-3.5 py-1.5 rounded-lg bg-[#FC4C02] hover:bg-[#ff5a14] text-white font-bold text-xs transition cursor-pointer disabled:opacity-50"
                            >
                              {publishingDraftUid === student.user_id ? "生效中..." : "确认转正生效"}
                            </button>
                            <button
                              onClick={() => handleQuickRollbackStudentPlan(student, { discardDraftOnly: true })}
                              disabled={rollingBackUserUid === student.user_id}
                              className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white border border-white/10 font-medium text-xs transition cursor-pointer disabled:opacity-50"
                            >
                              {rollingBackUserUid === student.user_id ? "撤回中..." : "撤回草案"}
                            </button>
                          </div>
                        </div>
                      )}

                      {/* ── NEW: Weekly Training Plan & 7-Day Execution Strip ── */}
                      {weekExec ? (
                        <div className="bg-[#121216] border border-white/10 rounded-xl p-4 space-y-3">
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-white flex items-center gap-1.5">
                                {pInfo.active_plan_title || pInfo.title || "周期训练课表"}
                              </span>
                              {pInfo.active_source_label && (
                                <span className="px-2 py-0.5 rounded bg-white/5 text-zinc-300 border border-white/10 text-[10px] font-medium">
                                  {pInfo.active_source_label}
                                </span>
                              )}
                              <span className="px-2 py-0.5 rounded bg-white/5 text-zinc-300 text-[11px] font-medium">
                                第 {weekExec.week_number} 周 · {weekExec.theme}
                              </span>
                              {weekExec.today_workout && (
                                <span className="px-2 py-0.5 rounded bg-white/5 text-zinc-300 border border-white/10 text-[11px] font-medium">
                                  今日: {weekExec.today_workout.title}
                                  {weekExec.today_workout.distance_km > 0 ? ` (${weekExec.today_workout.distance_km}km)` : ""}
                                  {weekExec.today_workout.completed ? " · 已打卡" : ""}
                                </span>
                              )}
                              {weekExec.injury_note && (
                                <span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30 text-[11px] font-bold">
                                  伤痛: {weekExec.injury_note}
                                </span>
                              )}
                              {(weekExec.low_hrv_days || 0) > 0 && (
                                <span className="px-2 py-0.5 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30 text-[11px] font-medium">
                                  HRV偏低 ({weekExec.low_hrv_days}天)
                                </span>
                              )}
                            </div>

                            <div className="flex items-center gap-2.5 text-xs flex-wrap">
                              {pInfo.latest_backup && (
                                <button
                                  onClick={() =>
                                    handleQuickRollbackStudentPlan(student, {
                                      backupId: pInfo.latest_backup.id,
                                    })
                                  }
                                  disabled={rollingBackUserUid === student.user_id}
                                  className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 text-[11px] font-medium transition cursor-pointer"
                                  title={`回退到上一版本：${pInfo.latest_backup.previous_plan_title || "历史课表"}`}
                                >
                                  回退上一版
                                </button>
                              )}
                              <span className="text-zinc-300 font-medium">
                                {weekExec.summary_banner_text || (
                                  <>
                                    周跑量：{weekExec.planned_km}公里。执行：<strong className="text-white font-mono">{weekExec.actual_km}</strong>公里，完成度{weekExec.compliance_rate}%；力量：{weekExec.strength_sessions_done || 0}次。
                                  </>
                                )}
                              </span>
                              <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 font-medium text-[11px]">
                                打卡 {weekExec.workouts_completed}/{weekExec.workouts_total} 课
                              </span>
                            </div>
                          </div>

                          {/* Athlete Weekly Summary / Coach Weekly Diagnosis Quick Strip */}
                          {(weekExec.athlete_weekly_summary || weekExec.coach_weekly_diagnosis) && (
                            <div className="flex flex-col sm:flex-row gap-2 text-[11px]">
                              {weekExec.athlete_weekly_summary && (
                                <div className="flex-1 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 text-zinc-300">
                                  <strong className="text-white">队员周小结:</strong> {weekExec.athlete_weekly_summary}
                                </div>
                              )}
                              {weekExec.coach_weekly_diagnosis && (
                                <div className="flex-1 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 text-zinc-300">
                                  <strong className="text-white">教练周复盘:</strong> {weekExec.coach_weekly_diagnosis}
                                </div>
                              )}
                            </div>
                          )}

                          {/* 7-day Visual Execution Strip */}
                          {weekExec.days_brief && weekExec.days_brief.length > 0 && (
                            <div className="grid grid-cols-7 gap-1.5">
                              {weekExec.days_brief.map((d: any, dIdx: number) => (
                                <div
                                  key={dIdx}
                                  onClick={() => setSelectedStudentForPlan(student)}
                                  className={`p-2 rounded-lg border text-center cursor-pointer transition hover:border-white/30 ${
                                    d.status === "completed"
                                      ? "bg-emerald-950/25 border-emerald-500/35"
                                      : d.status === "missed"
                                      ? "bg-rose-950/25 border-rose-500/35"
                                      : d.status === "rest"
                                      ? "bg-zinc-900/50 border-white/5 opacity-60"
                                      : "bg-white/[0.02] border-white/10"
                                  }`}
                                >
                                  <div className="flex items-center justify-between text-[10px] text-zinc-400">
                                    <span className="font-bold">{d.day_of_week}</span>
                                    <span>
                                      {d.status === "completed"
                                        ? "✅"
                                        : d.status === "missed"
                                        ? "⚠️"
                                        : d.status === "rest"
                                        ? "🛌"
                                        : "⏳"}
                                    </span>
                                  </div>
                                  <div className="text-[11px] font-bold text-white truncate mt-0.5">
                                    {d.title}
                                  </div>
                                  <div className="text-[10px] font-mono text-zinc-400 mt-0.5">
                                    {d.status === "rest"
                                      ? "休息"
                                      : d.status === "completed"
                                      ? `${d.actual_km || d.planned_km}km`
                                      : `${d.planned_km}km`}
                                  </div>
                                  {(d.rpe || d.recovery_pct != null || d.swapped_from) && (
                                    <div className="flex items-center justify-center gap-1 mt-1 flex-wrap">
                                      {d.rpe != null && (
                                        <span className={`px-1 rounded text-[9px] font-bold ${
                                          d.rpe >= 8 ? "bg-rose-500/25 text-rose-300" : "bg-white/10 text-zinc-300"
                                        }`}>
                                          RPE{d.rpe}
                                        </span>
                                      )}
                                      {d.recovery_pct != null && (
                                        <span className={`px-1 rounded text-[9px] font-bold ${
                                          d.recovery_status === "green"
                                            ? "bg-emerald-500/20 text-emerald-300"
                                            : d.recovery_status === "yellow"
                                            ? "bg-amber-500/20 text-amber-300"
                                            : "bg-rose-500/25 text-rose-300"
                                        }`}>
                                          {d.recovery_pct}%
                                        </span>
                                      )}
                                      {d.swapped_from && (
                                        <span className="px-1 rounded text-[9px] bg-blue-500/20 text-blue-300">
                                          调
                                        </span>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="bg-[#121216] border border-dashed border-white/10 rounded-xl px-4 py-3 flex items-center justify-between text-xs">
                          <span className="text-zinc-400">
                            ⚪ 该队员当前尚未配置专属周训练课表，可根据其目标赛事与当前生理状态一键生成 AI 定制草案。
                          </span>
                          <button
                            onClick={() => setSelectedStudentForPlan(student)}
                            className="text-[#FC4C02] hover:underline font-bold shrink-0 ml-3 cursor-pointer"
                          >
                            立即为其排课 →
                          </button>
                        </div>
                      )}

                      {/* Middle Row: Monthly Running Plan Progress Bar */}
                      <div className="bg-[#121215] border border-white/5 rounded-xl p-4">
                        <div className="flex items-center justify-between text-xs mb-2">
                          <div className="flex items-center gap-2">
                            <Target className="w-4 h-4 text-[#FC4C02]" />
                            <span className="text-zinc-300 font-bold">月跑量目标计划:</span>
                            <span className="text-white font-mono font-bold text-sm">
                              {student.month_km} <span className="text-zinc-500 font-normal">/ {student.target_km || 200} km</span>
                            </span>
                            <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                              student.completion_rate >= 100
                                ? "bg-emerald-500/20 text-emerald-400"
                                : student.pacing_status === "ahead"
                                ? "bg-blue-500/20 text-blue-400"
                                : student.pacing_status === "lagging"
                                ? "bg-amber-500/20 text-amber-400"
                                : "bg-white/5 text-zinc-300"
                            }`}>
                              {student.completion_rate || 0}% ({student.pacing_text || "按计划推进"})
                            </span>
                          </div>
                          <div className="text-zinc-400 text-xs hidden sm:block">
                            剩余: <strong className="text-white font-mono">{student.remaining_km || 0} km</strong> · 建议日均: <strong className="text-[#FC4C02] font-mono">{student.suggested_daily_km || 0} km/天</strong>
                          </div>
                        </div>

                        {/* Progress Track */}
                        <div className="w-full bg-white/5 h-2.5 rounded-full overflow-hidden relative">
                          <div
                            className={`h-full rounded-full transition-all ${
                              student.completion_rate >= 100
                                ? "bg-emerald-400"
                                : student.pacing_status === "ahead"
                                ? "bg-blue-400"
                                : student.pacing_status === "lagging"
                                ? "bg-amber-400"
                                : "bg-[#FC4C02]"
                            }`}
                            style={{ width: `${Math.min(100, Math.max(2, student.completion_rate || 0))}%` }}
                          />
                        </div>

                        <div className="flex items-center justify-between text-[11px] text-zinc-500 mt-2">
                          <span>近7天完成: <strong className="text-zinc-300">{student.km_7d || 0} km</strong> ({student.runs_7d_count || 0}次训练)</span>
                          <span className="sm:hidden text-zinc-400">
                            剩余 {student.remaining_km || 0}km (日均 {student.suggested_daily_km || 0}km)
                          </span>
                        </div>
                      </div>

                      {/* Bottom Row: Coach Diagnosis Recommendation */}
                      <div className="text-xs text-zinc-300 bg-purple-950/20 border border-purple-500/20 rounded-xl px-4 py-3 flex items-start gap-2.5">
                        <span className="text-purple-400 font-bold shrink-0">💡 教练科学指导:</span>
                        <span className="text-zinc-300 leading-relaxed">{student.coach_diagnosis || "暂无具体诊断建议"}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ── Coach Plan Review, Edit & Execution Modal ── */}
        <CoachPlanReviewModal
          isOpen={!!selectedStudentForPlan}
          student={selectedStudentForPlan}
          coachUid={user?.id || ""}
          clubId={currentClub?.id}
          studentsQueue={sortedCoachStudents}
          onSelectStudent={(stu) => setSelectedStudentForPlan(stu)}
          onClose={() => setSelectedStudentForPlan(null)}
          onUpdated={() => {
            if (currentClub?.id && user?.id) {
              loadClubDetails(currentClub.id, user.id);
            }
          }}
        />

        {/* ── Template Distribution Modal (模版派发：左侧模版列表 · 右侧设置/预览/队员 · 底部派发) ── */}
        {showTemplateAssignModal && (
          <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-2 sm:p-4">
            <div className="bg-[#121218] border border-amber-500/30 rounded-3xl max-w-7xl w-full h-[94vh] flex flex-col shadow-2xl overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/10 shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                  <h3 className="text-base font-black text-white whitespace-nowrap">📚 模版派发</h3>
                  <div className="hidden md:flex items-center gap-1.5 text-[11px]">
                    {[
                      { n: 1, label: "选模版", done: !!activeTemplateObj },
                      { n: 2, label: "设置周期", done: !!activeTemplateObj },
                      { n: 3, label: "选队员", done: selectedMemberIdsForTemplate.length > 0 },
                    ].map((s, i) => (
                      <span key={s.n} className="flex items-center gap-1.5">
                        {i > 0 && <span className="text-zinc-600">›</span>}
                        <span className={`px-2 py-0.5 rounded-full font-bold ${s.done ? "bg-amber-400/20 text-amber-300" : "bg-white/5 text-zinc-500"}`}>
                          {s.done ? "✓" : s.n} {s.label}
                        </span>
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => {
                      setShowTemplateAssignModal(false);
                      setShowScheduleImportModal(true);
                    }}
                    className="px-3 py-1.5 rounded-xl text-xs font-black bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 transition cursor-pointer flex items-center gap-1"
                  >
                    📸 从课表截图智能导入 (支持A~E组/男女组) →
                  </button>
                  <button
                    onClick={() => setShowTemplateAssignModal(false)}
                    className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white cursor-pointer shrink-0"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {loadingTemplates && coachTemplates.length === 0 ? (
                <div className="flex-1 flex items-center justify-center text-zinc-400 text-xs gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-amber-400" /> 正在加载模版...
                </div>
              ) : (
                <div className="flex-1 min-h-0 flex flex-col md:flex-row">
                  {/* ── Left: Template List ── */}
                  <aside className="md:w-72 shrink-0 border-b md:border-b-0 md:border-r border-white/10 flex flex-col min-h-0 max-h-56 md:max-h-none">
                    <div className="p-3 space-y-2 border-b border-white/5">
                      <input
                        type="text"
                        value={templateSearchQuery}
                        onChange={(e) => setTemplateSearchQuery(e.target.value)}
                        placeholder="🔍 搜索模版 / 组别 / 目标成绩"
                        className="w-full bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs text-white outline-none focus:border-amber-400"
                      />
                      <div className="flex gap-1 flex-wrap">
                        {[
                          { id: "all", label: "全部" },
                          { id: "marathon", label: "🏃 路跑" },
                          { id: "gobi", label: "🏜️ 戈壁" },
                          { id: "trail", label: "⛰️ 越野" },
                          { id: "custom", label: "🔒 我的" },
                        ].map((cat) => {
                          const cnt =
                            cat.id === "all"
                              ? coachTemplates.length
                              : coachTemplates.filter((t: any) => getTemplateCategoryKey(t) === cat.id).length;
                          return (
                            <button
                              key={cat.id}
                              onClick={() => setTemplateCategoryFilter(cat.id)}
                              className={`px-2 py-1 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                                templateCategoryFilter === cat.id
                                  ? "bg-amber-400 text-black"
                                  : "bg-white/5 text-zinc-400 hover:text-white"
                              }`}
                            >
                              {cat.label} {cnt}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                      {filteredCoachTemplates.length === 0 && (
                        <div className="text-center text-[11px] text-zinc-500 py-6">
                          {templateCategoryFilter === "custom"
                            ? "还没有自建模版：选一个系统模版 → 微调 → 另存为"
                            : "没有匹配的模版"}
                        </div>
                      )}
                      {filteredCoachTemplates.map((tpl: any) => {
                        const isSelected = tpl.id === activeTemplateObj?.id;
                        const rec = templateRecCountMap[tpl.id] || 0;
                        return (
                          <button
                            key={tpl.id}
                            onClick={() => handleSelectTemplateGroup(tpl.id)}
                            className={`w-full text-left px-3 py-2.5 rounded-xl border transition cursor-pointer ${
                              isSelected
                                ? "bg-amber-500/15 border-amber-400"
                                : "bg-transparent border-transparent hover:bg-white/5"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className={`text-xs font-black truncate ${isSelected ? "text-amber-200" : "text-white"}`}>
                                {tpl.short_name}
                              </span>
                              {rec > 0 && (
                                <span className="px-1.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 shrink-0">
                                  荐{rec}
                                </span>
                              )}
                            </div>
                            <div className="text-[10px] text-zinc-500 mt-0.5 truncate">
                              {tpl.weekly_km}km/周 · {tpl.days_per_week}练 · {tpl.target_pb_label}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </aside>

                  {/* ── Right: Settings + Preview + Members ── */}
                  <main className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-5 space-y-4">
                    {activeTemplateObj && (
                      <>
                        {/* Template Header */}
                        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm sm:text-base font-black text-white">{activeTemplateObj.short_name}</span>
                              {activeTemplateObj.intensity_badge && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                  {activeTemplateObj.intensity_badge}
                                </span>
                              )}
                              {activeTemplateObj.is_custom && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-200">🔒 仅我可见</span>
                              )}
                            </div>
                            {activeTemplateObj.pace_zones && (
                              <div className="flex items-center gap-x-3 gap-y-1 flex-wrap text-[11px] text-zinc-400 mt-1.5">
                                <span>E <strong className="text-emerald-300 font-mono">{activeTemplateObj.pace_zones.easy_pace}</strong></span>
                                <span>M <strong className="text-blue-300 font-mono">{activeTemplateObj.pace_zones.marathon_pace}</strong></span>
                                <span>T <strong className="text-amber-300 font-mono">{activeTemplateObj.pace_zones.threshold_pace}</strong></span>
                                <span>I <strong className="text-rose-300 font-mono">{activeTemplateObj.pace_zones.interval_pace}</strong></span>
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              onClick={() => setShowTemplateMetaEditor(!showTemplateMetaEditor)}
                              className="px-3 py-1.5 rounded-xl bg-purple-500/15 hover:bg-purple-500/25 border border-purple-400/35 text-purple-200 text-[11px] font-bold cursor-pointer"
                            >
                              💾 另存为我的模版
                            </button>
                            {activeTemplateObj.is_custom && (
                              <button
                                onClick={() => handleDeleteCustomTemplate(activeTemplateObj.id)}
                                className="px-2.5 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 text-[11px] font-bold cursor-pointer"
                              >
                                🗑️
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Save-As Panel (collapsed by default) */}
                        {showTemplateMetaEditor && (
                          <div className="bg-purple-950/20 border border-purple-500/35 rounded-2xl p-4 space-y-3">
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 text-xs">
                              <div>
                                <label className="text-[11px] text-zinc-400 block mb-1">组别代号</label>
                                <input type="text" value={tplEditGroupCode} onChange={(e) => setTplEditGroupCode(e.target.value)} className="w-full bg-black/50 border border-white/15 rounded-xl px-2.5 py-1.5 text-white font-bold" />
                              </div>
                              <div>
                                <label className="text-[11px] text-zinc-400 block mb-1">模版名称</label>
                                <input type="text" value={tplEditShortName} onChange={(e) => setTplEditShortName(e.target.value)} className="w-full bg-black/50 border border-white/15 rounded-xl px-2.5 py-1.5 text-white font-bold" />
                              </div>
                              <div>
                                <label className="text-[11px] text-zinc-400 block mb-1">分类</label>
                                <select value={tplEditCategory} onChange={(e) => setTplEditCategory(e.target.value)} className="w-full bg-black/50 border border-white/15 rounded-xl px-2.5 py-1.5 text-white">
                                  <option value="marathon">🏃 路跑马拉松</option>
                                  <option value="gobi">🏜️ 戈壁挑战赛</option>
                                  <option value="trail">⛰️ 山地越野</option>
                                  <option value="custom">✨ 专属特训</option>
                                </select>
                              </div>
                              <div>
                                <label className="text-[11px] text-zinc-400 block mb-1">适用水平 / 目标成绩</label>
                                <input type="text" value={tplEditTargetPb} onChange={(e) => setTplEditTargetPb(e.target.value)} className="w-full bg-black/50 border border-white/15 rounded-xl px-2.5 py-1.5 text-amber-200" />
                              </div>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                              {[
                                { label: "🟢 有氧 E", val: tplEditPaceEasy, set: setTplEditPaceEasy, cls: "text-emerald-300" },
                                { label: "🔵 马拉松 M", val: tplEditPaceMarathon, set: setTplEditPaceMarathon, cls: "text-blue-300" },
                                { label: "🟠 乳酸阈 T", val: tplEditPaceTempo, set: setTplEditPaceTempo, cls: "text-amber-300" },
                                { label: "🔴 间歇 I", val: tplEditPaceInterval, set: setTplEditPaceInterval, cls: "text-rose-300" },
                                { label: "⚡ 周末大课", val: tplEditPaceCore, set: setTplEditPaceCore, cls: "text-white" },
                              ].map((f) => (
                                <div key={f.label}>
                                  <label className="text-[10px] text-zinc-400 block mb-1">{f.label}</label>
                                  <input type="text" value={f.val} onChange={(e) => f.set(e.target.value)} className={`w-full bg-black/50 border border-white/15 rounded-lg px-2 py-1 font-mono text-[11px] ${f.cls}`} />
                                </div>
                              ))}
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                              <div>
                                <label className="text-[11px] text-zinc-400 block mb-1">阶段大纲</label>
                                <input type="text" value={tplEditMacroRoadmap} onChange={(e) => setTplEditMacroRoadmap(e.target.value)} className="w-full bg-black/50 border border-white/15 rounded-xl px-2.5 py-1.5 text-zinc-200" />
                              </div>
                              <div>
                                <label className="text-[11px] text-zinc-400 block mb-1">教练要求与提示</label>
                                <input type="text" value={tplEditDescription} onChange={(e) => setTplEditDescription(e.target.value)} className="w-full bg-black/50 border border-white/15 rounded-xl px-2.5 py-1.5 text-zinc-200" />
                              </div>
                            </div>
                            <div className="flex items-center justify-end gap-2 flex-wrap">
                              <span className="text-[11px] text-zinc-500 mr-auto">仅您本人可见，在您执教的所有跑团通用；下方标准周的修改会一并保存</span>
                              {activeTemplateObj.is_custom && (
                                <button disabled={savingCustomTemplate} onClick={() => handleSaveOrCloneCustomTemplate(true)} className="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-black cursor-pointer disabled:opacity-50">
                                  {savingCustomTemplate ? "保存中..." : "更新当前模版"}
                                </button>
                              )}
                              <button disabled={savingCustomTemplate} onClick={() => handleSaveOrCloneCustomTemplate(false)} className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-amber-400 to-orange-500 text-black text-xs font-black cursor-pointer disabled:opacity-50">
                                {savingCustomTemplate ? "保存中..." : "另存为新模版"}
                              </button>
                            </div>
                          </div>
                        )}

                        {/* Step 2: Distribution Settings */}
                        <div className="bg-[#17171f] border border-white/10 rounded-2xl p-3.5 space-y-3">
                          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 text-xs">
                            <div>
                              <div className="text-[11px] text-zinc-400 mb-1.5">套用范围</div>
                              <div className="flex bg-black/40 rounded-xl p-0.5 border border-white/10">
                                {[
                                  { val: "full_plan", label: "新周期" },
                                  { val: "current_week", label: "替换本周" },
                                  { val: "next_week", label: "写入下周" },
                                ].map((o) => (
                                  <button
                                    key={o.val}
                                    onClick={() => setTemplateApplyScope(o.val as any)}
                                    className={`flex-1 px-2 py-1.5 rounded-lg text-[11px] font-bold cursor-pointer transition ${
                                      templateApplyScope === o.val ? "bg-amber-400 text-black" : "text-zinc-400 hover:text-white"
                                    }`}
                                  >
                                    {o.label}
                                  </button>
                                ))}
                              </div>
                            </div>
                            <div className={templateApplyScope === "full_plan" ? "" : "opacity-40 pointer-events-none"}>
                              <div className="text-[11px] text-zinc-400 mb-1.5">周期长度</div>
                              <div className="flex bg-black/40 rounded-xl p-0.5 border border-white/10">
                                {[4, 6, 8, 12].map((wn) => (
                                  <button
                                    key={wn}
                                    onClick={() => setTemplateWeeksCount(wn)}
                                    className={`flex-1 px-2 py-1.5 rounded-lg text-[11px] font-bold cursor-pointer transition ${
                                      templateWeeksCount === wn ? "bg-amber-400 text-black" : "text-zinc-400 hover:text-white"
                                    }`}
                                  >
                                    {wn}周
                                  </button>
                                ))}
                              </div>
                            </div>
                            <div>
                              <div className="text-[11px] text-zinc-400 mb-1.5">
                                跑量系数 · 约{" "}
                                <strong className="text-emerald-300 font-mono">
                                  {Math.round(
                                    (templateCustomDays.reduce((a: number, d: any) => a + (Number(d.distance_km) || 0), 0) ||
                                      activeTemplateObj.weekly_km ||
                                      50) * templateScaleFactor
                                  )}
                                  km/周
                                </strong>
                              </div>
                              <div className="flex bg-black/40 rounded-xl p-0.5 border border-white/10">
                                {[0.85, 0.9, 1.0, 1.1].map((sc) => (
                                  <button
                                    key={sc}
                                    onClick={() => setTemplateScaleFactor(sc)}
                                    className={`flex-1 px-2 py-1.5 rounded-lg text-[11px] font-bold cursor-pointer transition ${
                                      templateScaleFactor === sc ? "bg-amber-400 text-black" : "text-zinc-400 hover:text-white"
                                    }`}
                                  >
                                    {Math.round(sc * 100)}%
                                  </button>
                                ))}
                              </div>
                            </div>
                            <div>
                              <div className="text-[11px] text-zinc-400 mb-1.5">Canova 逐周递进</div>
                              <button
                                onClick={() => setTemplateCanovaProgression(!templateCanovaProgression)}
                                className={`w-full flex items-center justify-between px-3 py-1.5 rounded-xl border text-[11px] font-bold cursor-pointer transition ${
                                  templateCanovaProgression
                                    ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                                    : "bg-black/40 border-white/10 text-zinc-400"
                                }`}
                              >
                                <span>{templateCanovaProgression ? "🔄 已开启" : "已关闭 · 每周相同"}</span>
                                <span className={`w-8 h-4 rounded-full relative transition ${templateCanovaProgression ? "bg-emerald-500" : "bg-zinc-600"}`}>
                                  <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${templateCanovaProgression ? "left-4" : "left-0.5"}`} />
                                </span>
                              </button>
                            </div>
                          </div>
                          {templateApplyScope === "full_plan" ? (
                            <div className="flex items-center gap-1.5 flex-wrap pt-2 border-t border-white/5">
                              <button
                                type="button"
                                onClick={() => setTemplatePlanViewTab("matrix")}
                                className={`px-2.5 py-1 rounded-lg text-[11px] font-black border transition cursor-pointer flex items-center gap-1 ${
                                  templatePlanViewTab === "matrix"
                                    ? "bg-amber-400 text-black border-amber-300 shadow"
                                    : "bg-amber-500/15 text-amber-200 border-amber-500/30 hover:bg-amber-500/25"
                                }`}
                              >
                                📊 {templateWeeksCount}周全景总览 (整体调整)
                              </button>
                              {(templatePreviewWeeks.length > 0
                                ? templatePreviewWeeks.map((wk: any, idx: number) => ({
                                    weekIdx: wk.week_index || idx + 1,
                                    label:
                                      templateCanovaOutline[idx] ||
                                      `W${wk.week_index || idx + 1} ${wk.theme?.split("·").pop()?.trim() || wk.phase || ""}`,
                                    km: wk.weekly_mileage_km,
                                  }))
                                : templateCanovaOutline.map((stg, idx) => ({
                                    weekIdx: idx + 1,
                                    label: stg,
                                    km: null,
                                  }))
                              ).map((item) => {
                                const isActiveWk = templatePlanViewTab === item.weekIdx;
                                return (
                                  <button
                                    key={item.weekIdx}
                                    type="button"
                                    onClick={() => setTemplatePlanViewTab(item.weekIdx)}
                                    className={`px-2 py-1 rounded-lg text-[10px] font-bold border transition cursor-pointer ${
                                      isActiveWk
                                        ? "bg-emerald-400 text-black border-emerald-300 font-black"
                                        : "bg-emerald-500/10 text-emerald-200 border-emerald-500/25 hover:bg-emerald-500/20"
                                    }`}
                                  >
                                    {item.label}
                                    {item.km != null ? ` (${Math.round(item.km)}k)` : ""}
                                  </button>
                                );
                              })}
                              <button
                                type="button"
                                onClick={() => setTemplatePlanViewTab("baseline")}
                                className={`ml-auto px-2.5 py-1 rounded-lg text-[10px] font-bold border transition cursor-pointer ${
                                  templatePlanViewTab === "baseline"
                                    ? "bg-purple-500 text-white border-purple-300"
                                    : "bg-white/5 text-zinc-400 border-white/10 hover:text-white"
                                }`}
                              >
                                ⚙️ 模版基准周
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 flex-wrap pt-2 border-t border-white/5">
                              <span className="text-[10px] text-emerald-200">
                                按队员所处周次自动匹配对应阶段课表（下方可直接微调单周 7 日内容）
                              </span>
                            </div>
                          )}
                        </div>

                        {/* Multi-Week Panoramic Matrix / Single-Week Detail / Baseline Week Editor */}
                        {templateApplyScope === "full_plan" && templatePlanViewTab === "matrix" ? (
                          <div className="space-y-2.5">
                            <div className="flex items-center justify-between gap-2 flex-wrap">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-xs font-black text-white">
                                  📊 {templateWeeksCount}周全景训练计划总览与整体调整
                                </span>
                                <span className="text-[10px] text-zinc-400">
                                  点击任意单日即可修改课表名称/距离/配速，或对任意单周一键增减量
                                </span>
                                {templateHasEditedWeeks && (
                                  <span className="px-2 py-0.5 rounded-full bg-amber-400/20 text-amber-300 border border-amber-400/30 text-[10px] font-bold">
                                    ✨ 已含教练微调（派发时将按此 {templateWeeksCount} 周课表下发）
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-2 text-[11px]">
                                {templateHasEditedWeeks && (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      fetchTemplateMultiWeekPreview(
                                        activeTemplateObj,
                                        templateWeeksCount,
                                        templateScaleFactor,
                                        templateCanovaProgression,
                                        templateCustomDays
                                      )
                                    }
                                    className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 cursor-pointer"
                                  >
                                    ↺ 重置为默认 {templateWeeksCount} 周递进
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => setTemplatePlanViewTab(1)}
                                  className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-amber-300 font-bold cursor-pointer"
                                >
                                  ✏️ 逐周表格详编
                                </button>
                              </div>
                            </div>

                            {/* Inline Quick Day Editor when coach clicks any cell in the 8-week matrix */}
                            {editingMatrixCell && (() => {
                              const targetWk = templatePreviewWeeks.find(
                                (w: any, idx: number) => (w.week_index || idx + 1) === editingMatrixCell.weekIdx
                              );
                              const targetDay = targetWk?.days?.[editingMatrixCell.dayIdx];
                              if (!targetWk || !targetDay) return null;
                              return (
                                <div className="bg-amber-950/30 border border-amber-400/50 rounded-2xl p-3 space-y-2.5 shadow-lg">
                                  <div className="flex items-center justify-between gap-2 flex-wrap">
                                    <div className="flex items-center gap-2 text-xs font-black text-amber-200">
                                      <span>
                                        ✏️ 正在调整：第 {editingMatrixCell.weekIdx} 周 ({targetWk.theme?.split("·").pop()?.trim() || targetWk.phase}) · {targetDay.day_of_week}
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          handleApplyDayToAllPreviewWeeks(editingMatrixCell.dayIdx, targetDay);
                                        }}
                                        className="px-2.5 py-1 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 border border-purple-400/40 text-purple-200 text-[10px] font-bold cursor-pointer"
                                        title={`将当前 ${targetDay.day_of_week} 的课表同步复制到全部 ${templateWeeksCount} 周的 ${targetDay.day_of_week}`}
                                      >
                                        📋 同步至全部 {templateWeeksCount} 周的{targetDay.day_of_week}
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          handleUpdatePreviewWeekDay(editingMatrixCell.weekIdx, editingMatrixCell.dayIdx, {
                                            workout_type: "rest",
                                            title: "休息日",
                                            distance_km: 0,
                                            target_pace: "—",
                                          })
                                        }
                                        className="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 text-[10px] cursor-pointer"
                                      >
                                        🛌 设为休息
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => setEditingMatrixCell(null)}
                                        className="px-2.5 py-1 rounded-lg bg-amber-400 text-black text-[10px] font-black cursor-pointer"
                                      >
                                        ✓ 完成
                                      </button>
                                    </div>
                                  </div>
                                  <div className="grid grid-cols-1 sm:grid-cols-12 gap-2 text-xs">
                                    <div className="sm:col-span-2">
                                      <label className="text-[10px] text-zinc-400 block mb-0.5">训练类型</label>
                                      <select
                                        value={targetDay.workout_type || "easy_run"}
                                        onChange={(e) =>
                                          handleUpdatePreviewWeekDay(editingMatrixCell.weekIdx, editingMatrixCell.dayIdx, {
                                            workout_type: e.target.value,
                                          })
                                        }
                                        className="w-full bg-black/60 border border-white/15 rounded-lg px-2 py-1.5 text-xs text-white"
                                      >
                                        <option value="easy_run">轻松跑</option>
                                        <option value="interval">间歇跑</option>
                                        <option value="tempo_run">节奏/门槛跑</option>
                                        <option value="long_run">长距离</option>
                                        <option value="trail_climb">越野爬升</option>
                                        <option value="rest">休息/身训</option>
                                      </select>
                                    </div>
                                    <div className="sm:col-span-4">
                                      <label className="text-[10px] text-zinc-400 block mb-0.5">课表标题</label>
                                      <input
                                        type="text"
                                        value={targetDay.title || ""}
                                        onChange={(e) =>
                                          handleUpdatePreviewWeekDay(editingMatrixCell.weekIdx, editingMatrixCell.dayIdx, {
                                            title: e.target.value,
                                          })
                                        }
                                        className="w-full bg-black/60 border border-white/15 rounded-lg px-2.5 py-1.5 text-xs text-white font-bold"
                                      />
                                    </div>
                                    <div className="sm:col-span-2">
                                      <label className="text-[10px] text-zinc-400 block mb-0.5">距离 (km)</label>
                                      <input
                                        type="number"
                                        step="0.5"
                                        value={targetDay.distance_km ?? 0}
                                        onChange={(e) =>
                                          handleUpdatePreviewWeekDay(editingMatrixCell.weekIdx, editingMatrixCell.dayIdx, {
                                            distance_km: Number(e.target.value),
                                          })
                                        }
                                        className="w-full bg-black/60 border border-white/15 rounded-lg px-2.5 py-1.5 text-xs text-emerald-300 font-mono font-bold"
                                      />
                                    </div>
                                    <div className="sm:col-span-4">
                                      <label className="text-[10px] text-zinc-400 block mb-0.5">目标配速</label>
                                      <input
                                        type="text"
                                        value={targetDay.target_pace || ""}
                                        onChange={(e) =>
                                          handleUpdatePreviewWeekDay(editingMatrixCell.weekIdx, editingMatrixCell.dayIdx, {
                                            target_pace: e.target.value,
                                          })
                                        }
                                        className="w-full bg-black/60 border border-white/15 rounded-lg px-2.5 py-1.5 text-xs text-amber-200 font-mono"
                                      />
                                    </div>
                                    <div className="sm:col-span-12">
                                      <label className="text-[10px] text-zinc-400 block mb-0.5">具体执行要求说明</label>
                                      <input
                                        type="text"
                                        value={targetDay.description || ""}
                                        onChange={(e) =>
                                          handleUpdatePreviewWeekDay(editingMatrixCell.weekIdx, editingMatrixCell.dayIdx, {
                                            description: e.target.value,
                                          })
                                        }
                                        className="w-full bg-black/60 border border-white/15 rounded-lg px-2.5 py-1.5 text-xs text-zinc-200"
                                      />
                                    </div>
                                  </div>
                                </div>
                              );
                            })()}

                            {loadingTemplatePreview && templatePreviewWeeks.length === 0 ? (
                              <div className="py-10 text-center text-xs text-zinc-400 flex items-center justify-center gap-2 border border-white/10 rounded-2xl bg-black/20">
                                <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                                正在生成 {templateWeeksCount} 周 Canova 周期课表预览...
                              </div>
                            ) : (
                              <div className="overflow-x-auto border border-white/10 rounded-2xl bg-[#14141a]">
                                <table className="w-full text-left border-collapse text-xs min-w-[920px]">
                                  <thead>
                                    <tr className="border-b border-white/10 text-[11px] text-zinc-400 bg-black/40">
                                      <th className="py-2.5 px-3 w-40 border-r border-white/10">周次 / 阶段与周跑量</th>
                                      <th className="py-2.5 px-2 border-r border-white/5">周一 (恢复)</th>
                                      <th className="py-2.5 px-2 border-r border-white/5 text-rose-300">周二 (速度/间歇)</th>
                                      <th className="py-2.5 px-2 border-r border-white/5">周三 (有氧/力量)</th>
                                      <th className="py-2.5 px-2 border-r border-white/5 text-amber-300">周四 (门槛/专项)</th>
                                      <th className="py-2.5 px-2 border-r border-white/5">周五 (蓄能)</th>
                                      <th className="py-2.5 px-2 border-r border-white/5">周六 (唤醒)</th>
                                      <th className="py-2.5 px-2 text-blue-300">周日 (长距离大课)</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-white/10">
                                    {templatePreviewWeeks.map((wk: any, wIdx: number) => {
                                      const wNum = wk.week_index || wIdx + 1;
                                      const shortTheme = wk.theme?.split("·").pop()?.trim() || wk.phase || `第${wNum}周`;
                                      return (
                                        <tr key={wNum} className="hover:bg-white/[0.02] transition align-top">
                                          {/* Left Week Summary & Quick Scale Column */}
                                          <td className="p-2.5 border-r border-white/10 bg-black/25">
                                            <div className="flex items-center justify-between gap-1">
                                              <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-black text-[10px]">
                                                第{wNum}周
                                              </span>
                                              <span className="font-mono font-black text-emerald-300 text-xs">
                                                {wk.weekly_mileage_km}km
                                              </span>
                                            </div>
                                            <div className="font-black text-white text-[11px] mt-1 truncate" title={wk.theme}>
                                              {shortTheme}
                                            </div>
                                            <div className="text-[10px] text-zinc-500 truncate">{wk.phase}</div>
                                            <div className="flex items-center gap-1 mt-2">
                                              <button
                                                type="button"
                                                onClick={() => handleScaleSinglePreviewWeek(wNum, 0.9)}
                                                className="px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/15 text-zinc-300 text-[10px] font-mono cursor-pointer"
                                                title="本周跑量减 10%"
                                              >
                                                -10%
                                              </button>
                                              <button
                                                type="button"
                                                onClick={() => handleScaleSinglePreviewWeek(wNum, 1.1)}
                                                className="px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/15 text-zinc-300 text-[10px] font-mono cursor-pointer"
                                                title="本周跑量加 10%"
                                              >
                                                +10%
                                              </button>
                                              <button
                                                type="button"
                                                onClick={() => setTemplatePlanViewTab(wNum)}
                                                className="ml-auto px-1.5 py-0.5 rounded bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 text-[10px] font-bold cursor-pointer"
                                              >
                                                详编
                                              </button>
                                            </div>
                                          </td>

                                          {/* 7 Day Cells */}
                                          {(wk.days || []).map((d: any, dIdx: number) => {
                                            const isRest = d.workout_type === "rest" || !(Number(d.distance_km) > 0);
                                            const isEditingThis =
                                              editingMatrixCell?.weekIdx === wNum && editingMatrixCell?.dayIdx === dIdx;
                                            const cellTone: Record<string, string> = {
                                              interval: "border-rose-500/35 bg-rose-500/[0.06] hover:border-rose-400",
                                              tempo: "border-amber-500/35 bg-amber-500/[0.06] hover:border-amber-400",
                                              tempo_run: "border-amber-500/35 bg-amber-500/[0.06] hover:border-amber-400",
                                              long_run: "border-blue-500/35 bg-blue-500/[0.06] hover:border-blue-400",
                                              long: "border-blue-500/35 bg-blue-500/[0.06] hover:border-blue-400",
                                              trail_climb: "border-cyan-500/35 bg-cyan-500/[0.06] hover:border-cyan-400",
                                            };
                                            return (
                                              <td key={dIdx} className="p-1.5 border-r border-white/5 last:border-r-0 align-top">
                                                <div
                                                  onClick={() =>
                                                    setEditingMatrixCell(
                                                      isEditingThis ? null : { weekIdx: wNum, dayIdx: dIdx }
                                                    )
                                                  }
                                                  title={d.description ? `${d.title}\n${d.description}\n(点击直接修改)` : "点击修改此日课表"}
                                                  className={`p-2 rounded-xl border min-h-[82px] flex flex-col justify-between transition cursor-pointer ${
                                                    isEditingThis
                                                      ? "ring-2 ring-amber-400 border-amber-400 bg-amber-500/15"
                                                      : isRest
                                                      ? "border-white/5 bg-black/20 hover:border-white/20"
                                                      : cellTone[d.workout_type] || "border-white/10 bg-white/[0.02] hover:border-white/30"
                                                  }`}
                                                >
                                                  <div className="flex items-center justify-between gap-1">
                                                    {isRest ? (
                                                      <span className="text-[10px] text-zinc-600">休息</span>
                                                    ) : (
                                                      <>
                                                        <span className="font-mono font-black text-emerald-300 text-[11px]">
                                                          {d.distance_km}k
                                                        </span>
                                                        <div
                                                          className="flex items-center gap-0.5"
                                                          onClick={(e) => e.stopPropagation()}
                                                        >
                                                          <button
                                                            type="button"
                                                            onClick={() =>
                                                              handleUpdatePreviewWeekDay(wNum, dIdx, {
                                                                distance_km: Math.max(
                                                                  1,
                                                                  Math.round(((Number(d.distance_km) || 0) - 1) * 2) / 2
                                                                ),
                                                              })
                                                            }
                                                            className="px-1 rounded bg-black/40 hover:bg-white/15 text-zinc-400 hover:text-white text-[9px] font-mono cursor-pointer"
                                                          >
                                                            -1
                                                          </button>
                                                          <button
                                                            type="button"
                                                            onClick={() =>
                                                              handleUpdatePreviewWeekDay(wNum, dIdx, {
                                                                distance_km:
                                                                  Math.round(((Number(d.distance_km) || 0) + 1) * 2) / 2,
                                                              })
                                                            }
                                                            className="px-1 rounded bg-black/40 hover:bg-white/15 text-zinc-400 hover:text-white text-[9px] font-mono cursor-pointer"
                                                          >
                                                            +1
                                                          </button>
                                                        </div>
                                                      </>
                                                    )}
                                                  </div>
                                                  <div
                                                    className={`text-[11px] leading-snug line-clamp-2 my-1 ${
                                                      isRest ? "text-zinc-600" : "text-zinc-100 font-bold"
                                                    }`}
                                                  >
                                                    {isRest ? "休息恢复" : d.title}
                                                  </div>
                                                  {!isRest && d.target_pace && d.target_pace !== "—" && (
                                                    <div className="text-[9px] font-mono text-zinc-400 truncate">
                                                      {d.target_pace}
                                                    </div>
                                                  )}
                                                </div>
                                              </td>
                                            );
                                          })}
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        ) : templateApplyScope === "full_plan" && typeof templatePlanViewTab === "number" ? (
                          /* Single Week Detailed Table View (W1..W8) */
                          (() => {
                            const activeWk =
                              templatePreviewWeeks.find(
                                (w: any, idx: number) => (w.week_index || idx + 1) === templatePlanViewTab
                              ) || templatePreviewWeeks[0];
                            if (!activeWk) return null;
                            const wNum = activeWk.week_index || templatePlanViewTab;
                            return (
                              <div className="space-y-2.5">
                                <div className="flex items-center justify-between gap-2 flex-wrap">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <span className="px-2 py-0.5 rounded-lg bg-emerald-500/20 text-emerald-300 font-black text-xs">
                                      第 {wNum} 周
                                    </span>
                                    <span className="text-xs font-black text-white">
                                      {activeWk.week_title || activeWk.theme}
                                    </span>
                                    <span className="text-xs font-mono text-emerald-300 font-bold">
                                      周跑量 {activeWk.weekly_mileage_km}km
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-1.5 flex-wrap text-[11px]">
                                    <button
                                      type="button"
                                      disabled={wNum <= 1}
                                      onClick={() => setTemplatePlanViewTab(Math.max(1, wNum - 1))}
                                      className="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 disabled:opacity-30 cursor-pointer"
                                    >
                                      ◀ 上一周
                                    </button>
                                    <button
                                      type="button"
                                      disabled={wNum >= templateWeeksCount}
                                      onClick={() => setTemplatePlanViewTab(Math.min(templateWeeksCount, wNum + 1))}
                                      className="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 disabled:opacity-30 cursor-pointer"
                                    >
                                      下一周 ▶
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleScaleSinglePreviewWeek(wNum, 0.9)}
                                      className="px-2 py-1 rounded-lg bg-amber-500/15 text-amber-300 font-bold cursor-pointer"
                                    >
                                      📉 本周-10%
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleScaleSinglePreviewWeek(wNum, 1.1)}
                                      className="px-2 py-1 rounded-lg bg-blue-500/15 text-blue-300 font-bold cursor-pointer"
                                    >
                                      📈 本周+10%
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => setTemplatePlanViewTab("matrix")}
                                      className="px-2.5 py-1 rounded-lg bg-amber-400 text-black font-black cursor-pointer"
                                    >
                                      📊 返回 {templateWeeksCount}周全景表
                                    </button>
                                  </div>
                                </div>

                                {activeWk.key_focus && (
                                  <div className="text-[11px] text-emerald-200 bg-emerald-950/25 border border-emerald-500/25 rounded-xl px-3 py-1.5">
                                    🎯 本周训练重心：{activeWk.key_focus}
                                  </div>
                                )}

                                <div className="overflow-x-auto border border-white/10 rounded-xl">
                                  <table className="w-full text-left border-collapse text-xs">
                                    <thead>
                                      <tr className="border-b border-white/10 text-[11px] text-zinc-400 bg-white/[0.02]">
                                        <th className="py-2 px-2 w-14">星期</th>
                                        <th className="py-2 px-2 w-28">类型</th>
                                        <th className="py-2 px-2 w-52">标题</th>
                                        <th className="py-2 px-2 w-20">km</th>
                                        <th className="py-2 px-2 w-36">配速</th>
                                        <th className="py-2 px-2">执行要求</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                      {(activeWk.days || []).map((d: any, dIdx: number) => (
                                        <tr key={dIdx}>
                                          <td className="py-1.5 px-2 font-bold text-amber-300">{d.day_of_week}</td>
                                          <td className="py-1.5 px-2">
                                            <select
                                              value={d.workout_type || "easy_run"}
                                              onChange={(e) =>
                                                handleUpdatePreviewWeekDay(wNum, dIdx, { workout_type: e.target.value })
                                              }
                                              className="bg-black/40 border border-white/10 rounded-lg px-1.5 py-1 text-[11px] text-white w-full"
                                            >
                                              <option value="easy_run">轻松跑</option>
                                              <option value="interval">间歇跑</option>
                                              <option value="tempo_run">节奏跑</option>
                                              <option value="long_run">长距离</option>
                                              <option value="trail_climb">越野爬升</option>
                                              <option value="rest">休息/身训</option>
                                            </select>
                                          </td>
                                          <td className="py-1.5 px-2">
                                            <input
                                              type="text"
                                              value={d.title || ""}
                                              onChange={(e) =>
                                                handleUpdatePreviewWeekDay(wNum, dIdx, { title: e.target.value })
                                              }
                                              className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-white w-full"
                                            />
                                          </td>
                                          <td className="py-1.5 px-2">
                                            <input
                                              type="number"
                                              step="0.5"
                                              value={d.distance_km ?? 0}
                                              onChange={(e) =>
                                                handleUpdatePreviewWeekDay(wNum, dIdx, {
                                                  distance_km: Number(e.target.value),
                                                })
                                              }
                                              className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-emerald-300 font-mono w-16"
                                            />
                                          </td>
                                          <td className="py-1.5 px-2">
                                            <input
                                              type="text"
                                              value={d.target_pace || ""}
                                              onChange={(e) =>
                                                handleUpdatePreviewWeekDay(wNum, dIdx, { target_pace: e.target.value })
                                              }
                                              className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-amber-200 font-mono w-full"
                                            />
                                          </td>
                                          <td className="py-1.5 px-2">
                                            <input
                                              type="text"
                                              value={d.description || ""}
                                              onChange={(e) =>
                                                handleUpdatePreviewWeekDay(wNum, dIdx, { description: e.target.value })
                                              }
                                              className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-zinc-200 w-full"
                                            />
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            );
                          })()
                        ) : (
                          /* Baseline Week: read-only 7-day grid or toggle to edit */
                          <div className="space-y-2">
                            <div className="flex items-center justify-between gap-2 flex-wrap">
                              <span className="text-xs font-black text-white">
                                📅 模版基准周
                                <span className="ml-2 text-[10px] font-normal text-zinc-500">
                                  {templateCanovaProgression ? "修改基准周后可一键重新推演全部周次" : "每周沿用此课表"}
                                </span>
                              </span>
                              <div className="flex items-center gap-2 text-[11px]">
                                {templateApplyScope === "full_plan" && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      fetchTemplateMultiWeekPreview(
                                        activeTemplateObj,
                                        templateWeeksCount,
                                        templateScaleFactor,
                                        templateCanovaProgression,
                                        templateCustomDays
                                      );
                                      setTemplatePlanViewTab("matrix");
                                    }}
                                    className="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 font-bold cursor-pointer"
                                  >
                                    🔄 按此基准周重新推演 {templateWeeksCount} 周并查看全景表
                                  </button>
                                )}
                                {templateEditMode && (
                                  <button
                                    onClick={() => syncTemplateEditorFields(activeTemplateObj)}
                                    className="text-zinc-400 hover:text-white cursor-pointer"
                                  >
                                    ↺ 恢复默认
                                  </button>
                                )}
                                <button
                                  onClick={() => setTemplateEditMode(!templateEditMode)}
                                  className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-amber-300 font-bold cursor-pointer"
                                >
                                  {templateEditMode ? "✓ 完成微调" : "✏️ 微调基准周"}
                                </button>
                              </div>
                            </div>

                            {!templateEditMode ? (
                              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5">
                                {templateCustomDays.map((d: any, dIdx: number) => {
                                  const isRest = d.workout_type === "rest" || !(Number(d.distance_km) > 0);
                                  const typeColor: Record<string, string> = {
                                    interval: "border-rose-500/40 bg-rose-500/5",
                                    tempo: "border-amber-500/40 bg-amber-500/5",
                                    tempo_run: "border-amber-500/40 bg-amber-500/5",
                                    long_run: "border-blue-500/40 bg-blue-500/5",
                                    long: "border-blue-500/40 bg-blue-500/5",
                                    trail_climb: "border-emerald-500/40 bg-emerald-500/5",
                                  };
                                  return (
                                    <div
                                      key={dIdx}
                                      title={d.description || ""}
                                      className={`p-2 rounded-xl border min-h-[84px] ${
                                        isRest
                                          ? "border-white/5 bg-black/20"
                                          : typeColor[d.workout_type] || "border-white/10 bg-white/[0.02]"
                                      }`}
                                    >
                                      <div className="flex items-center justify-between text-[10px]">
                                        <span className="font-bold text-zinc-400">{d.day_of_week}</span>
                                        {!isRest && <span className="font-mono text-emerald-300 font-bold">{d.distance_km}k</span>}
                                      </div>
                                      <div
                                        className={`text-[11px] mt-1 leading-snug line-clamp-3 ${
                                          isRest ? "text-zinc-600" : "text-zinc-100 font-semibold"
                                        }`}
                                      >
                                        {isRest ? "休息" : d.title}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <div className="overflow-x-auto border border-white/10 rounded-xl">
                                <table className="w-full text-left border-collapse text-xs">
                                  <thead>
                                    <tr className="border-b border-white/10 text-[11px] text-zinc-400 bg-white/[0.02]">
                                      <th className="py-2 px-2 w-12">星期</th>
                                      <th className="py-2 px-2 w-24">类型</th>
                                      <th className="py-2 px-2 w-48">标题</th>
                                      <th className="py-2 px-2 w-20">km</th>
                                      <th className="py-2 px-2 w-32">配速</th>
                                      <th className="py-2 px-2">执行要求</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-white/5">
                                    {templateCustomDays.map((d: any, dIdx: number) => (
                                      <tr key={dIdx}>
                                        <td className="py-1.5 px-2 font-bold text-amber-300">{d.day_of_week}</td>
                                        <td className="py-1.5 px-2">
                                          <select
                                            value={d.workout_type || "easy_run"}
                                            onChange={(e) => handleUpdateTemplateDayField(dIdx, "workout_type", e.target.value)}
                                            className="bg-black/40 border border-white/10 rounded-lg px-1.5 py-1 text-[11px] text-white w-full"
                                          >
                                            <option value="easy_run">轻松跑</option>
                                            <option value="interval">间歇跑</option>
                                            <option value="tempo_run">节奏跑</option>
                                            <option value="long_run">长距离</option>
                                            <option value="trail_climb">越野爬升</option>
                                            <option value="rest">休息/身训</option>
                                          </select>
                                        </td>
                                        <td className="py-1.5 px-2">
                                          <input
                                            type="text"
                                            value={d.title || ""}
                                            onChange={(e) => handleUpdateTemplateDayField(dIdx, "title", e.target.value)}
                                            className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-white w-full"
                                          />
                                        </td>
                                        <td className="py-1.5 px-2">
                                          <input
                                            type="number"
                                            step="0.5"
                                            value={d.distance_km ?? 0}
                                            onChange={(e) =>
                                              handleUpdateTemplateDayField(dIdx, "distance_km", Number(e.target.value))
                                            }
                                            className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-emerald-300 font-mono w-16"
                                          />
                                        </td>
                                        <td className="py-1.5 px-2">
                                          <input
                                            type="text"
                                            value={d.target_pace || ""}
                                            onChange={(e) => handleUpdateTemplateDayField(dIdx, "target_pace", e.target.value)}
                                            className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-amber-200 font-mono w-full"
                                          />
                                        </td>
                                        <td className="py-1.5 px-2">
                                          <input
                                            type="text"
                                            value={d.description || ""}
                                            onChange={(e) => handleUpdateTemplateDayField(dIdx, "description", e.target.value)}
                                            className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-zinc-200 w-full"
                                          />
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Step 3: Members */}
                        <div className="bg-[#17171f] border border-white/10 rounded-2xl p-3.5 space-y-3">
                          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-2">
                            <div className="text-xs font-black text-white flex items-center gap-2">
                              👥 派发对象
                              <span className="px-2 py-0.5 rounded-full bg-amber-400/20 text-amber-300 text-[11px] font-black">
                                已选 {selectedMemberIdsForTemplate.length} / {coachCockpit?.students?.length || 0}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <input
                                type="text"
                                value={templateMemberSearch}
                                onChange={(e) => setTemplateMemberSearch(e.target.value)}
                                placeholder="🔍 搜索队员"
                                className="bg-black/40 border border-white/10 rounded-lg px-2.5 py-1 text-[11px] text-white outline-none focus:border-amber-400 w-28"
                              />
                              <button
                                onClick={() =>
                                  setSelectedMemberIdsForTemplate(
                                    (coachCockpit?.students || [])
                                      .filter((s: any) => s.recommended_group?.template_id === activeTemplateObj?.id)
                                      .map((s: any) => s.user_id)
                                  )
                                }
                                className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/35 text-[11px] font-bold cursor-pointer"
                              >
                                🎯 本组推荐 ({templateRecCountMap[activeTemplateObj?.id] || 0})
                              </button>
                              <button
                                onClick={() =>
                                  setSelectedMemberIdsForTemplate(
                                    (coachCockpit?.students || [])
                                      .filter((s: any) => (s.plan_info?.plan_state || "none") === "none")
                                      .map((s: any) => s.user_id)
                                  )
                                }
                                className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 text-[11px] font-bold cursor-pointer"
                              >
                                ⚪ 未排课
                              </button>
                              <button
                                onClick={() => setSelectedMemberIdsForTemplate((coachCockpit?.students || []).map((s: any) => s.user_id))}
                                className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 text-[11px] font-bold cursor-pointer"
                              >
                                全选
                              </button>
                              <button
                                onClick={() => setSelectedMemberIdsForTemplate([])}
                                className="px-2.5 py-1 rounded-lg text-zinc-500 hover:text-white text-[11px] cursor-pointer"
                              >
                                清空
                              </button>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1.5 max-h-64 overflow-y-auto pr-1">
                            {(coachCockpit?.students || [])
                              .filter((stu: any) => {
                                const q = templateMemberSearch.trim().toLowerCase();
                                return !q || String(stu.display_name || "").toLowerCase().includes(q);
                              })
                              .map((stu: any) => {
                                const checked = selectedMemberIdsForTemplate.includes(stu.user_id);
                                const isRec = stu.recommended_group?.template_id === activeTemplateObj?.id;
                                const pState = stu.plan_info?.plan_state || "none";
                                return (
                                  <label
                                    key={stu.user_id}
                                    className={`px-2.5 py-2 rounded-xl border cursor-pointer transition flex items-center gap-2.5 text-xs ${
                                      checked ? "bg-amber-500/12 border-amber-400/80" : "bg-black/25 border-white/10 hover:border-white/25"
                                    }`}
                                    title={stu.recommended_group?.reason || ""}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() => handleToggleMemberForTemplate(stu.user_id)}
                                      className="w-4 h-4 accent-amber-400 shrink-0"
                                    />
                                    <div className="min-w-0 flex-1">
                                      <div className="flex items-center gap-1.5">
                                        <span className="font-bold text-white truncate">{stu.display_name}</span>
                                        {isRec && <span className="px-1 rounded text-[9px] font-black bg-amber-400 text-black shrink-0">荐</span>}
                                      </div>
                                      <div className="text-[10px] text-zinc-500 truncate">
                                        推荐 {stu.recommended_group?.group_code || "—"}
                                        {stu.plan_info?.template_group_code ? ` · 现 ${stu.plan_info.template_group_code}` : ""}
                                        {" · "}
                                        {pState === "none" ? "未排课" : pState === "draft_pending" ? "待审核" : "执行中"}
                                      </div>
                                    </div>
                                  </label>
                                );
                              })}
                          </div>
                        </div>
                      </>
                    )}
                  </main>
                </div>
              )}

              {/* Sticky Footer: summary + actions */}
              <div className="shrink-0 border-t border-white/10 px-5 py-3 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-[#0f0f14]">
                <div className="text-[11px] text-zinc-400 truncate">
                  {activeTemplateObj ? (
                    <>
                      <strong className="text-amber-300">{activeTemplateObj.short_name}</strong>
                      {" → "}
                      <strong className="text-white">{selectedMemberIdsForTemplate.length} 人</strong>
                      {" · "}
                      {templateApplyScope === "full_plan" ? `${templateWeeksCount}周新周期` : templateApplyScope === "current_week" ? "替换本周" : "写入下周"}
                      {" · "}
                      {Math.round(templateScaleFactor * 100)}%跑量
                      {templateCanovaProgression ? " · 逐周递进" : ""}
                    </>
                  ) : (
                    "请先选择模版"
                  )}
                </div>
                <div className="flex items-center gap-2 flex-wrap justify-end">
                  <button
                    disabled={assigningTemplate || selectedMemberIdsForTemplate.length === 0}
                    onClick={() => handleAssignTemplateToMembers(true, false)}
                    className="px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-200 text-xs font-bold cursor-pointer disabled:opacity-40"
                    title="存为待审草案，稍后再审核发布"
                  >
                    存为草案
                  </button>
                  <button
                    disabled={assigningTemplate || selectedMemberIdsForTemplate.length === 0}
                    onClick={() => handleAssignTemplateToMembers(true, true)}
                    className="px-4 py-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-xs font-black cursor-pointer disabled:opacity-40"
                    title="存为草案后自动打开逐人批阅，微调后发布"
                  >
                    {assigningTemplate ? "处理中..." : "草案 + 逐人微调"}
                  </button>
                  <button
                    disabled={assigningTemplate || selectedMemberIdsForTemplate.length === 0}
                    onClick={() => {
                      if (confirm(`确认将【${activeTemplateObj?.short_name}】直接发布给 ${selectedMemberIdsForTemplate.length} 名队员？发布后队员立即可见。`)) {
                        handleAssignTemplateToMembers(false, false);
                      }
                    }}
                    className="px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black text-xs font-black shadow-lg shadow-emerald-500/20 cursor-pointer disabled:opacity-40"
                  >
                    {assigningTemplate ? "发布中..." : `🚀 派发并发布 (${selectedMemberIdsForTemplate.length}人)`}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Club Group Workout Broadcast Modal (跑团合练/公共课一键派发) ── */}
        {showBroadcastModal && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="bg-[#15151b] border border-purple-500/35 rounded-3xl p-6 max-w-lg w-full space-y-4 shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div>
                  <h3 className="text-base font-black text-white flex items-center gap-2">
                    📢 跑团公共合练课一键派发 ({coachCockpit?.summary?.total_students || 20}位队员)
                  </h3>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    将跑团统一合练（如周二交大间歇课、周日世纪公园长距离）一键同步写入全体队员的周课表，免去逐一修改20份计划的繁琐操作
                  </p>
                </div>
                <button
                  onClick={() => setShowBroadcastModal(false)}
                  className="p-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] text-zinc-400">快捷预设:</span>
                <button
                  onClick={() => {
                    setBcastDayIndex(1);
                    setBcastWorkoutType("interval");
                    setBcastTitle("交大合练：慢跑+身训+间歇速度课");
                    setBcastDistanceKm(12);
                    setBcastTargetPace("按A/B/C组配速");
                    setBcastDescription("慢跑热身4km + 臀腿核心身训2组 + 场地间歇速度训练");
                  }}
                  className="px-2.5 py-1 rounded-lg bg-purple-500/15 hover:bg-purple-500/25 text-purple-200 border border-purple-500/30 text-xs font-bold cursor-pointer"
                >
                  ⚡ 周二交大间歇+身训合练
                </button>
                <button
                  onClick={() => {
                    setBcastDayIndex(6);
                    setBcastWorkoutType("long");
                    setBcastTitle("跑团周末有氧长距离LSD合练");
                    setBcastDistanceKm(22);
                    setBcastTargetPace("E配速有氧巡航");
                    setBcastDescription("全团集体长距离有氧耐力课，按配速分组领跑，注意每5km补水补胶");
                  }}
                  className="px-2.5 py-1 rounded-lg bg-orange-500/15 hover:bg-orange-500/25 text-orange-200 border border-orange-500/30 text-xs font-bold cursor-pointer"
                >
                  🏔️ 周日长距离LSD集体拉练
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="text-zinc-400 block mb-1">派发目标周</label>
                  <select
                    value={bcastWeekMode}
                    onChange={(e) => setBcastWeekMode(e.target.value as "current" | "next")}
                    className="w-full bg-black/50 border border-white/15 rounded-xl px-3 py-2 text-white outline-none focus:border-purple-400"
                  >
                    <option value="current">本周执行周</option>
                    <option value="next">下周 (W+1) 课表</option>
                  </select>
                </div>
                <div>
                  <label className="text-zinc-400 block mb-1">合练星期</label>
                  <select
                    value={bcastDayIndex}
                    onChange={(e) => setBcastDayIndex(Number(e.target.value))}
                    className="w-full bg-black/50 border border-white/15 rounded-xl px-3 py-2 text-white outline-none focus:border-purple-400"
                  >
                    {["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((lbl, idx) => (
                      <option key={idx} value={idx}>
                        {lbl}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-zinc-400 block mb-1">课表类型</label>
                  <select
                    value={bcastWorkoutType}
                    onChange={(e) => setBcastWorkoutType(e.target.value)}
                    className="w-full bg-black/50 border border-white/15 rounded-xl px-3 py-2 text-white outline-none focus:border-purple-400"
                  >
                    <option value="interval">间歇/速度合练</option>
                    <option value="tempo">乳酸阈节奏合练</option>
                    <option value="long">周末长距离合练</option>
                    <option value="easy">集体有氧慢跑</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div className="sm:col-span-2">
                  <label className="text-zinc-400 block mb-1">合练课表标题</label>
                  <input
                    type="text"
                    value={bcastTitle}
                    onChange={(e) => setBcastTitle(e.target.value)}
                    className="w-full bg-black/50 border border-white/15 rounded-xl px-3 py-2 text-white outline-none focus:border-purple-400"
                  />
                </div>
                <div>
                  <label className="text-zinc-400 block mb-1">总里程 (km)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={bcastDistanceKm}
                    onChange={(e) => setBcastDistanceKm(Number(e.target.value))}
                    className="w-full bg-black/50 border border-white/15 rounded-xl px-3 py-2 text-white font-mono outline-none focus:border-purple-400"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 text-xs">
                <div>
                  <label className="text-zinc-400 block mb-1">目标配速说明</label>
                  <input
                    type="text"
                    value={bcastTargetPace}
                    onChange={(e) => setBcastTargetPace(e.target.value)}
                    className="w-full bg-black/50 border border-white/15 rounded-xl px-3 py-2 text-white outline-none focus:border-purple-400"
                  />
                </div>
                <div>
                  <label className="text-zinc-400 block mb-1">合练具体内容与分组要求</label>
                  <textarea
                    rows={2}
                    value={bcastDescription}
                    onChange={(e) => setBcastDescription(e.target.value)}
                    className="w-full bg-black/50 border border-white/15 rounded-xl px-3 py-2 text-white outline-none focus:border-purple-400"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  onClick={() => setShowBroadcastModal(false)}
                  className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-bold cursor-pointer"
                >
                  取消
                </button>
                <button
                  onClick={handleBroadcastClubWorkout}
                  disabled={broadcastingWorkout}
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-black shadow-lg cursor-pointer disabled:opacity-50"
                >
                  {broadcastingWorkout ? "同步派发中..." : "📢 一键同步至全团队员课表"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Coach Student Deep Report Modal ── */}
        {selectedStudentForReport && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="bg-[#151518] border border-white/10 rounded-3xl p-6 sm:p-8 max-w-3xl w-full max-h-[90vh] overflow-y-auto space-y-6 shadow-2xl relative">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div className="flex items-center gap-4">
                  <img
                    src={selectedStudentForReport.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                    alt={selectedStudentForReport.display_name}
                    className="w-14 h-14 rounded-full object-cover border-2 border-purple-500/50"
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-xl font-black text-white">{selectedStudentForReport.display_name}</h3>
                      <span className="text-xs px-2 py-0.5 rounded font-bold bg-purple-500/20 text-purple-300">
                        {selectedStudentForReport.canova_phase || "基础准备期"}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">
                      全马 PB: <strong className="text-white font-mono">{formatPb(selectedStudentForReport.marathon_pb)}</strong>
                      {" · "}
                      半马 PB: <strong className="text-white font-mono">{formatPb(selectedStudentForReport.half_pb)}</strong>
                      {selectedStudentForReport.height && selectedStudentForReport.weight && (
                        <>
                          {" · "}
                          身高体重: <strong className="text-zinc-300">{selectedStudentForReport.height}cm / {selectedStudentForReport.weight}kg</strong>
                        </>
                      )}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedStudentForReport(null)}
                  className="p-2 text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-full transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* 1. 2026 全年 12 个月跑量规划梯队图 */}
              <div className="bg-[#101013] border border-white/5 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-purple-400" />
                    2026 全年跑量计划目标规划 (1~12月)
                  </h4>
                  <span className="text-xs text-zinc-400">
                    当前月份: <strong className="text-[#FC4C02]">{new Date().getMonth() + 1} 月</strong>
                  </span>
                </div>

                <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-12 gap-2 text-center">
                  {(selectedStudentForReport.monthly_targets || Array(12).fill(200)).map((t: number, idx: number) => {
                    const isCurrent = idx === new Date().getMonth();
                    return (
                      <div
                        key={idx}
                        className={`p-2.5 rounded-xl border transition ${
                          isCurrent
                            ? "bg-[#FC4C02]/15 border-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/10"
                            : "bg-white/[0.02] border-white/5 text-zinc-400"
                        }`}
                      >
                        <span className={`text-[11px] block font-bold ${isCurrent ? "text-[#FC4C02]" : "text-zinc-500"}`}>
                          {idx + 1}月
                        </span>
                        <span className="text-xs font-mono font-black mt-1 block">
                          {t}
                          <span className="text-[9px] font-normal text-zinc-500 block">km</span>
                        </span>
                        {isCurrent && (
                          <span className="text-[9px] text-emerald-400 font-bold block mt-1">
                            进行中
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 2. 当月进度指标 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-4 text-center">
                  <span className="text-[11px] text-zinc-500 block">本月目标</span>
                  <span className="text-lg font-black text-white font-mono mt-0.5 block">{selectedStudentForReport.target_km || 200} km</span>
                </div>
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-4 text-center">
                  <span className="text-[11px] text-zinc-500 block">已完成跑量</span>
                  <span className="text-lg font-black text-emerald-400 font-mono mt-0.5 block">{selectedStudentForReport.month_km || 0} km</span>
                </div>
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-4 text-center">
                  <span className="text-[11px] text-zinc-500 block">计划完成度</span>
                  <span className="text-lg font-black text-[#FC4C02] font-mono mt-0.5 block">{selectedStudentForReport.completion_rate || 0}%</span>
                </div>
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-4 text-center">
                  <span className="text-[11px] text-zinc-500 block">建议日均跑量</span>
                  <span className="text-lg font-black text-blue-400 font-mono mt-0.5 block">{selectedStudentForReport.suggested_daily_km || 0} km</span>
                </div>
              </div>

              {/* 3. 生理状态与疲劳状况 */}
              <div className="bg-[#101013] border border-white/5 rounded-2xl p-5">
                <h4 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
                  <Activity className="w-4 h-4 text-cyan-400" />
                  生理机能状态与训练负荷监控
                </h4>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 text-center">
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">CTL 体能储备</span>
                    <span className="text-sm font-black text-blue-400 font-mono mt-1 block">
                      {selectedStudentForReport.ctl > 0 ? selectedStudentForReport.ctl : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">ATL 近期疲劳</span>
                    <span className="text-sm font-black text-purple-400 font-mono mt-1 block">
                      {selectedStudentForReport.atl > 0 ? selectedStudentForReport.atl : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">TSB 竞技状况</span>
                    <span className={`text-sm font-black font-mono mt-1 block ${
                      selectedStudentForReport.ctl > 0 || selectedStudentForReport.atl > 0
                        ? (selectedStudentForReport.tsb >= 0 ? "text-emerald-400" : "text-amber-400")
                        : "text-zinc-500"
                    }`}>
                      {selectedStudentForReport.ctl > 0 || selectedStudentForReport.atl > 0 ? selectedStudentForReport.tsb : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">静息心率</span>
                    <span className="text-sm font-black text-rose-400 font-mono mt-1 block">
                      {selectedStudentForReport.resting_heart_rate ? `${selectedStudentForReport.resting_heart_rate} bpm` : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">夜间 HRV</span>
                    <span className="text-sm font-black text-cyan-400 font-mono mt-1 block">
                      {selectedStudentForReport.hrv_ms ? `${selectedStudentForReport.hrv_ms} ms` : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">睡眠质量</span>
                    <span className="text-sm font-black text-emerald-400 font-mono mt-1 block">
                      {selectedStudentForReport.sleep_score ? `${selectedStudentForReport.sleep_score} 分` : "—"}
                    </span>
                  </div>
                </div>
              </div>

              {/* 4. 教练科学指导与 Canova 建议 */}
              <div className="bg-purple-950/20 border border-purple-500/30 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Shield className="w-4 h-4 text-purple-400" />
                  <h4 className="text-sm font-bold text-purple-300">Canova 科学训练期与教练专属指导</h4>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  {selectedStudentForReport.coach_diagnosis}
                </p>
              </div>

              {/* 5. 近期跑步记录明细 */}
              {selectedStudentForReport.recent_activities?.length > 0 && (
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-5">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                    <Flame className="w-4 h-4 text-amber-400" />
                    近期跑步与训练记录 (前 5 条)
                  </h4>
                  <div className="divide-y divide-white/5 text-xs">
                    {selectedStudentForReport.recent_activities.map((act: any, idx: number) => (
                      <div key={idx} className="py-2.5 flex items-center justify-between">
                        <div>
                          <span className="text-white font-bold block">{act.name}</span>
                          <span className="text-[10px] text-zinc-500">{act.start_time?.slice(0, 16).replace("T", " ")}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-emerald-400 font-mono font-bold">{act.distance_km} km</span>
                          <span className="text-[10px] text-zinc-400 ml-2">({act.duration_mins} 分钟)</span>
                          {act.avg_hr && (
                            <span className="text-[10px] text-rose-400 ml-2">均心: {act.avg_hr}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 4: 🏆 跑团挑战赛与活动 ── */}
        {activeTab === "events" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-black text-white flex items-center gap-2">
                  <Award className="w-5 h-5 text-blue-400" />
                  跑团活动与月度挑战赛
                </h2>
                <p className="text-xs text-zinc-400 mt-0.5">全团共同参与，用公里数兑换专属荣誉与完赛勋章</p>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                {activeManagedOrg && (
                  <button
                    onClick={() => openOrgEventsModalFor(activeManagedOrg)}
                    className="flex items-center gap-1.5 px-4 py-2 bg-purple-500/20 hover:bg-purple-500/30 text-purple-200 border border-purple-500/40 rounded-2xl text-xs font-bold transition cursor-pointer"
                  >
                    🚩 发起大群跨跑团联合活动
                  </button>
                )}
                {(currentRole === "owner" || currentRole === "coach") && (
                  <button
                    onClick={() => {
                      setEditingEvent(null);
                      setEventTitle("");
                      setEventTargetKm(200);
                      setEventRules("");
                      setShowCreateEventModal(true);
                    }}
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-blue-600/20 self-start sm:self-auto"
                  >
                    <Plus className="w-4 h-4" />
                    发起本团挑战 / 活动
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {events.map((evt) => (
                <div
                  key={evt.id}
                  className={`bg-[#121215] border rounded-3xl p-6 sm:p-8 shadow-xl flex flex-col justify-between ${
                    evt.is_org_event ? "border-amber-500/40 bg-gradient-to-br from-amber-500/[0.06] to-[#121215]" : "border-white/10"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {evt.is_org_event && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-black bg-amber-500/20 text-amber-300 border border-amber-500/40">
                            🏛️ 大群跨跑团联合
                          </span>
                        )}
                        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-500/20 text-blue-300">
                          <Award className="w-3.5 h-3.5" />
                          {evt.event_type === "group_run" ? "📍 线下联合约跑 / 合练" : "🏆 里程挑战赛"}
                        </div>
                      </div>

                      {/* Edit / Delete actions for Owner/Coach */}
                      {(currentRole === "owner" || currentRole === "coach") && (
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => handleOpenEditEvent(evt)}
                            className="px-2.5 py-1 bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white rounded-lg text-[11px] font-bold transition flex items-center gap-1"
                          >
                            <Edit2 className="w-3 h-3" /> 编辑
                          </button>
                          <button
                            onClick={() => handleDeleteEvent(evt.id)}
                            className="px-2.5 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 rounded-lg text-[11px] font-bold transition flex items-center gap-1"
                          >
                            <Trash2 className="w-3 h-3" /> 删除
                          </button>
                        </div>
                      )}
                    </div>

                    <h3 className="text-xl font-black text-white mb-2">{evt.title}</h3>
                    {evt.event_type === "group_run" && (evt.meet_time || evt.location) && (
                      <div className="flex flex-wrap gap-3 text-xs text-amber-300/90 mb-2 font-medium">
                        {evt.meet_time && <span>⏰ 集合时间：{evt.meet_time}</span>}
                        {evt.location && <span>📍 集合地点：{evt.location}</span>}
                        {evt.pace_requirement && <span>⚡ 配速分组：{evt.pace_requirement}</span>}
                      </div>
                    )}
                    <p className="text-xs text-zinc-300 leading-relaxed mb-4">{evt.rules}</p>
                  </div>

                  <div className="pt-4 border-t border-white/5 flex items-center justify-between gap-2 flex-wrap">
                    <span className="text-xs text-zinc-400">
                      目标里程: <strong className="text-white text-sm">{evt.target_km} km</strong>
                      {(evt.participant_count ?? evt.participants_count) != null && (
                        <span className="ml-3 text-zinc-400">
                          已报名: <strong className="text-amber-300">{evt.participant_count ?? evt.participants_count} 人</strong>
                        </span>
                      )}
                    </span>
                    <div className="flex items-center gap-2">
                      {evt.event_type === "group_run" && (
                        <button
                          type="button"
                          disabled={togglingEventId === evt.id}
                          onClick={() => handleToggleEventJoin(evt)}
                          className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer disabled:opacity-50 ${
                            evt.is_joined
                              ? "bg-white/10 hover:bg-rose-500/20 text-emerald-300 hover:text-rose-300 border border-white/15"
                              : "bg-[#FC4C02] hover:bg-orange-500 text-white shadow-md shadow-[#FC4C02]/20"
                          }`}
                        >
                          {togglingEventId === evt.id
                            ? "处理中..."
                            : evt.is_joined
                            ? "✅ 已报名 · 请假取消"
                            : "🚀 立即报名"}
                        </button>
                      )}
                      <span className="text-xs text-emerald-400 font-bold">
                        {evt.is_org_event ? "🏛️ 跨团同步进行中" : "进行中"}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
          </>
        )}
      </main>
      )}

      {/* Grand Organization Real-Name Join Modal (大群体实名认证加入) */}
      {showOrgJoinModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-amber-500/30 rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2">
                <span className="text-xl">🏛️</span>
                <div>
                  <h3 className="text-lg font-black text-white">
                    加入大群体 · 戈友实名认证
                  </h3>
                  <span className="text-[10px] text-amber-400 font-semibold">凭专属邀请码认证</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowOrgJoinModal(false)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Privacy Security Notice */}
            <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 space-y-1.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-bold text-amber-300">
                  <Shield className="w-4 h-4 text-amber-400" />
                  <span>个人隐私与数据安全保障</span>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  AES-256 加密
                </span>
              </div>
              <p className="text-[11px] text-zinc-300 leading-relaxed">
                真实姓名、证件号、出生日期及手机号均在底层采用 AES-256 密文存储，非必要不暴露，仅用于戈赛资格核验与分组合规。普通跑友无法查看您的明文隐私，且支持随时一键彻底清除。
              </p>
            </div>

            <form onSubmit={handleOrgJoin} className="space-y-3.5 text-xs">
              {/* 专属邀请码 */}
              <div>
                <label className="text-zinc-400 block mb-1 font-semibold">
                  大群体专属邀请码 <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={orgInviteCode}
                  onChange={(e) => {
                    const nextCode = e.target.value.toUpperCase();
                    setOrgInviteCode(nextCode);
                    verifyOrgCodeAndLoadRules(nextCode);
                  }}
                  placeholder="输入邀请码后自动加载该大群准入字段要求"
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-white font-mono tracking-wider uppercase focus:outline-none focus:border-amber-500"
                />
              </div>

              {/* 真实姓名 */}
              {isJoinFieldVisible("real_name") && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-zinc-400 font-semibold flex items-center gap-1.5">
                    <span>
                      真实姓名{" "}
                      {isJoinFieldRequired("real_name") ? (
                        <span className="text-rose-400">*</span>
                      ) : (
                        <span className="text-zinc-500 font-normal">(选填)</span>
                      )}
                    </span>
                    <span className="text-[10px] text-emerald-400/80 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">加密存储</span>
                  </label>
                  <span className="text-[11px] text-zinc-500">{showOrgRealName ? "明文" : "掩码"}</span>
                </div>
                <div className="relative flex items-center">
                  <input
                    type={showOrgRealName ? "text" : "password"}
                    required={isJoinFieldRequired("real_name")}
                    value={orgRealName}
                    onChange={(e) => setOrgRealName(e.target.value)}
                    placeholder="请填写真实姓名以便管理员核对"
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-white focus:outline-none focus:border-amber-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowOrgRealName(!showOrgRealName)}
                    className="absolute right-2.5 text-zinc-400 hover:text-white transition p-1"
                  >
                    {showOrgRealName ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              )}

              {/* 生理性别 */}
              {isJoinFieldVisible("gender") && (
              <div>
                <label className="text-zinc-400 block mb-1 font-semibold">
                  生理性别{" "}
                  {isJoinFieldRequired("gender") ? (
                    <span className="text-rose-400">*</span>
                  ) : (
                    <span className="text-zinc-500 font-normal">(选填)</span>
                  )}
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setOrgGender("male")}
                    className={`py-2 rounded-xl font-bold transition flex items-center justify-center gap-1.5 ${
                      orgGender === "male"
                        ? "bg-blue-600 text-white shadow-md shadow-blue-600/20"
                        : "bg-[#1c1c20] text-zinc-400 border border-white/5 hover:border-white/20"
                    }`}
                  >
                    <span>🚹 男 (Male)</span>
                    {orgGender === "male" && <span>✓</span>}
                  </button>
                  <button
                    type="button"
                    onClick={() => setOrgGender("female")}
                    className={`py-2 rounded-xl font-bold transition flex items-center justify-center gap-1.5 ${
                      orgGender === "female"
                        ? "bg-rose-600 text-white shadow-md shadow-rose-600/20"
                        : "bg-[#1c1c20] text-zinc-400 border border-white/5 hover:border-white/20"
                    }`}
                  >
                    <span>🚺 女 (Female)</span>
                    {orgGender === "female" && <span>✓</span>}
                  </button>
                </div>
              </div>
              )}

              {/* 出生日期 */}
              {isJoinFieldVisible("date_of_birth") && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-zinc-400 font-semibold flex items-center gap-1.5">
                    <span>
                      出生日期{" "}
                      {isJoinFieldRequired("date_of_birth") ? (
                        <span className="text-rose-400">*</span>
                      ) : (
                        <span className="text-zinc-500 font-normal">(选填)</span>
                      )}
                    </span>
                    <span className="text-[10px] text-emerald-400/80 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">密文分级</span>
                  </label>
                </div>
                <div className="relative flex items-center">
                  {showOrgDob ? (
                    <input
                      type="date"
                      required={isJoinFieldRequired("date_of_birth")}
                      value={orgDob}
                      onChange={(e) => setOrgDob(e.target.value)}
                      className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-white focus:outline-none focus:border-amber-500"
                    />
                  ) : (
                    <input
                      type="password"
                      readOnly
                      value={orgDob ? "1990-01-01" : ""}
                      placeholder="点击右侧眼睛显示并选择出生日期"
                      onClick={() => setShowOrgDob(true)}
                      className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-white focus:outline-none focus:border-amber-500 cursor-pointer"
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => setShowOrgDob(!showOrgDob)}
                    className="absolute right-2.5 text-zinc-400 hover:text-white transition p-1"
                  >
                    {showOrgDob ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[10px] text-zinc-500 mt-1">
                  仅用于生理体能评估与大组织分组核实，对外公开名册仅显示组别脱敏保护
                </p>
              </div>
              )}

              {/* 商学院项目与班级 */}
              {isJoinFieldVisible("class_name") && (
              <div className="space-y-2">
                <label className="text-zinc-400 block mb-1 font-semibold">
                  商学院项目与班级{" "}
                  {isJoinFieldRequired("class_name") ? (
                    <span className="text-rose-400">*</span>
                  ) : (
                    <span className="text-zinc-500 font-normal">(选填)</span>
                  )}
                </label>
                <div>
                  <span className="text-xs text-zinc-500 block mb-1.5">选择项目：</span>
                  <div className="flex flex-wrap gap-1.5">
                    {ORG_PROGRAM_OPTIONS.map((prog) => (
                      <button
                        key={prog}
                        type="button"
                        onClick={() => setOrgProgram(prog)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
                          orgProgram === prog
                            ? "bg-amber-500 text-black shadow-md shadow-amber-500/20 font-bold"
                            : "bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10 border border-white/5"
                        }`}
                      >
                        {prog}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-xs text-zinc-500 block mb-1.5">所在班级 / 届别 (自由输入)：</span>
                  <input
                    type="text"
                    required={isJoinFieldRequired("class_name")}
                    value={orgClassDetail}
                    onChange={(e) => setOrgClassDetail(e.target.value)}
                    placeholder="例如: 23春、21级、18班、2022秋"
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-amber-500 text-sm"
                  />
                  {orgProgram && orgClassDetail && (
                    <p className="text-[11px] text-amber-400/80 mt-1">
                      组合显示预览：<span className="font-semibold text-amber-300">{orgProgram} {orgClassDetail}</span>
                    </p>
                  )}
                </div>
              </div>
              )}

              {/* 戈壁经历 */}
              {isJoinFieldVisible("gobi_experience") && (
              <div className="space-y-2">
                <label className="text-zinc-400 block mb-1 font-semibold flex items-center justify-between">
                  <span>
                    戈壁经历 (戈赛经验){" "}
                    {isJoinFieldRequired("gobi_experience") ? (
                      <span className="text-rose-400">*</span>
                    ) : (
                      <span className="text-zinc-500 font-normal">(选填)</span>
                    )}
                  </span>
                  <span className="text-[11px] text-zinc-500">新戈 / 戈1-戈21</span>
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setOrgGobiType("new")}
                    className={`p-3 rounded-2xl border text-left transition flex items-center gap-2.5 ${
                      orgGobiType === "new"
                        ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-lg shadow-emerald-500/10"
                        : "bg-white/5 border-white/5 text-zinc-400 hover:bg-white/10"
                    }`}
                  >
                    <span className="text-xl">🌱</span>
                    <div>
                      <div className="font-bold text-sm">新戈</div>
                      <div className="text-[10px] text-zinc-500">首次备赛，暂无往届经历</div>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setOrgGobiType("vet")}
                    className={`p-3 rounded-2xl border text-left transition flex items-center gap-2.5 ${
                      orgGobiType === "vet"
                        ? "bg-amber-500/15 border-amber-500/40 text-amber-300 shadow-lg shadow-amber-500/10"
                        : "bg-white/5 border-white/5 text-zinc-400 hover:bg-white/10"
                    }`}
                  >
                    <span className="text-xl">🏅</span>
                    <div>
                      <div className="font-bold text-sm">往届戈友</div>
                      <div className="text-[10px] text-zinc-500">参加过戈1至戈21</div>
                    </div>
                  </button>
                </div>

                {orgGobiType === "vet" && (
                  <div className="p-3 bg-black/40 border border-white/10 rounded-2xl space-y-2.5 mt-2">
                    <div>
                      <span className="text-xs text-zinc-400 block mb-1.5">参加届数 (戈1 ~ 戈21)：</span>
                      <select
                        value={orgGobiEdition}
                        onChange={(e) => setOrgGobiEdition(e.target.value)}
                        className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:border-amber-500"
                      >
                        {GOBI_EDITIONS.map((ed) => (
                          <option key={ed} value={ed}>
                            {ed}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-400 block mb-1.5">参赛组别：</span>
                      <div className="flex gap-2">
                        {GOBI_GROUPS.map((grp) => (
                          <button
                            key={grp}
                            type="button"
                            onClick={() => setOrgGobiGroup(grp)}
                            className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition ${
                              orgGobiGroup === grp
                                ? "bg-amber-500 text-black font-extrabold shadow-md shadow-amber-500/20"
                                : "bg-white/5 text-zinc-400 hover:text-white border border-white/5"
                            }`}
                          >
                            {grp}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="pt-1 text-[11px] text-amber-300 flex items-center gap-1.5">
                      <span>经历标识：</span>
                      <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30">
                        🏅 {orgGobiEdition} {orgGobiGroup}
                      </span>
                    </div>
                  </div>
                )}
              </div>
              )}

              {/* 身份证号码 / 证件号 */}
              {isJoinFieldVisible("id_card") && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-zinc-400 font-semibold flex items-center gap-1.5">
                    <span>
                      身份证号码 / 证件号{" "}
                      {isJoinFieldRequired("id_card") ? (
                        <span className="text-rose-400">*</span>
                      ) : (
                        <span className="text-zinc-500 font-normal">(选填)</span>
                      )}
                    </span>
                    <span className="text-[10px] text-emerald-400/80 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">非必要不暴露</span>
                  </label>
                  <span className="text-[11px] text-zinc-500">{showOrgIdCard ? "明文" : "掩码"}</span>
                </div>
                <div className="relative flex items-center">
                  <input
                    type={showOrgIdCard ? "text" : "password"}
                    required={isJoinFieldRequired("id_card")}
                    maxLength={18}
                    value={orgIdCard}
                    onChange={(e) => setOrgIdCard(e.target.value)}
                    placeholder="用于赛事保险投保与参赛资格核验"
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-white focus:outline-none focus:border-amber-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowOrgIdCard(!showOrgIdCard)}
                    className="absolute right-2.5 text-zinc-400 hover:text-white transition p-1"
                  >
                    {showOrgIdCard ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              )}

              {/* 联系手机 */}
              {isJoinFieldVisible("phone") && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-zinc-400 font-semibold flex items-center gap-1.5">
                    <span>
                      联系手机{" "}
                      {isJoinFieldRequired("phone") ? (
                        <span className="text-rose-400">*</span>
                      ) : (
                        <span className="text-zinc-500 font-normal">(选填)</span>
                      )}
                    </span>
                    <span className="text-[10px] text-emerald-400/80 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">保密</span>
                  </label>
                  <span className="text-[11px] text-zinc-500">{showOrgPhone ? "明文" : "掩码"}</span>
                </div>
                <div className="relative flex items-center">
                  <input
                    type={showOrgPhone ? "tel" : "password"}
                    required={isJoinFieldRequired("phone")}
                    maxLength={11}
                    value={orgPhone}
                    onChange={(e) => setOrgPhone(e.target.value)}
                    placeholder="便于紧急联络与赛事活动通知"
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-white focus:outline-none focus:border-amber-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowOrgPhone(!showOrgPhone)}
                    className="absolute right-2.5 text-zinc-400 hover:text-white transition p-1"
                  >
                    {showOrgPhone ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              )}

              {/* 紧急联系人及电话 */}
              {isJoinFieldVisible("emergency_contact") && (
              <div>
                <label className="text-zinc-400 block mb-1 font-semibold">
                  紧急联系人及电话{" "}
                  {isJoinFieldRequired("emergency_contact") ? (
                    <span className="text-rose-400">*</span>
                  ) : (
                    <span className="text-zinc-500 font-normal">(选填)</span>
                  )}
                </label>
                <input
                  type="text"
                  required={isJoinFieldRequired("emergency_contact")}
                  value={orgEmergencyContact}
                  onChange={(e) => setOrgEmergencyContact(e.target.value)}
                  placeholder="例如：张三 13800000000"
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-amber-500"
                />
              </div>
              )}

              {/* 队服尺码 & 跑鞋尺码 */}
              {(isJoinFieldVisible("clothing_size") || isJoinFieldVisible("shoe_size")) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {isJoinFieldVisible("clothing_size") && (
                <div>
                  <label className="text-zinc-400 block mb-1 font-semibold">
                    队服尺码{" "}
                    {isJoinFieldRequired("clothing_size") ? (
                      <span className="text-rose-400">*</span>
                    ) : (
                      <span className="text-zinc-500 font-normal">(选填)</span>
                    )}
                  </label>
                  <select
                    required={isJoinFieldRequired("clothing_size")}
                    value={orgClothingSize}
                    onChange={(e) => setOrgClothingSize(e.target.value)}
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3 py-2.5 text-white focus:outline-none focus:border-amber-500"
                  >
                    <option value="">请选择尺码</option>
                    {["XS", "S", "M", "L", "XL", "2XL", "3XL"].map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                )}
                {isJoinFieldVisible("shoe_size") && (
                <div>
                  <label className="text-zinc-400 block mb-1 font-semibold">
                    跑鞋尺码 (EUR){" "}
                    {isJoinFieldRequired("shoe_size") ? (
                      <span className="text-rose-400">*</span>
                    ) : (
                      <span className="text-zinc-500 font-normal">(选填)</span>
                    )}
                  </label>
                  <select
                    required={isJoinFieldRequired("shoe_size")}
                    value={orgShoeSize}
                    onChange={(e) => setOrgShoeSize(e.target.value)}
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3 py-2.5 text-white focus:outline-none focus:border-amber-500"
                  >
                    <option value="">请选择鞋码</option>
                    {["36", "37", "38", "39", "40", "41", "42", "42.5", "43", "44", "45"].map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                )}
              </div>
              )}

              {/* 全马 PB */}
              {isJoinFieldVisible("marathon_pb") && (
              <div>
                <label className="text-zinc-400 block mb-1 font-semibold">
                  全马 PB 成绩{" "}
                  {isJoinFieldRequired("marathon_pb") ? (
                    <span className="text-rose-400">*</span>
                  ) : (
                    <span className="text-zinc-500 font-normal">(选填)</span>
                  )}
                </label>
                <input
                  type="text"
                  required={isJoinFieldRequired("marathon_pb")}
                  value={orgMarathonPb}
                  onChange={(e) => setOrgMarathonPb(e.target.value)}
                  placeholder="例如：3:25:00"
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-amber-500"
                />
              </div>
              )}

              {/* 健康状况声明 */}
              {isJoinFieldVisible("health_declaration") && (
              <div>
                <label className="text-zinc-400 block mb-1 font-semibold">
                  健康状况声明{" "}
                  {isJoinFieldRequired("health_declaration") ? (
                    <span className="text-rose-400">*</span>
                  ) : (
                    <span className="text-zinc-500 font-normal">(选填)</span>
                  )}
                </label>
                <button
                  type="button"
                  onClick={() => setOrgHealthChecked(!orgHealthChecked)}
                  className={`w-full p-3 rounded-2xl border text-left transition flex items-start gap-2.5 ${
                    orgHealthChecked
                      ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-200"
                      : "bg-[#1c1c20] border-white/10 text-zinc-400"
                  }`}
                >
                  <span className="text-base">{orgHealthChecked ? "✅" : "⬜"}</span>
                  <span className="text-[11px] leading-relaxed">
                    本人确认身体健康，无不适合高强度耐力跑步的疾病，自愿参加大群与分队训练活动。
                  </span>
                </button>
              </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOrgJoinModal(false)}
                  className="flex-1 py-3 bg-white/5 hover:bg-white/10 border border-white/10 text-white rounded-2xl text-xs font-bold transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={orgJoining}
                  className="flex-1 py-3 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-black font-black rounded-2xl text-xs transition shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {orgJoining ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-black" />
                      <span>正在认证加入...</span>
                    </>
                  ) : (
                    <span>立即提交实名认证</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── 大群主理人 / 管理员：大群基本设定与入会规则弹窗 ── */}
      {showOrgSettingsModal && activeManagedOrg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-amber-500/35 rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div>
                <h3 className="text-lg font-black text-white">
                  ⚙️ 【{activeManagedOrg.name}】大群设定与入会规则
                </h3>
                <p className="text-[11px] text-zinc-400 mt-0.5">
                  大群主理人与管理员可直接维护大群基本资料、自由/凭码入会模式及专属邀请码
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowOrgSettingsModal(false)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveOrgSettings} className="space-y-4 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2">
                  <label className="text-zinc-400 block mb-1 font-semibold">大群名称 *</label>
                  <input
                    type="text"
                    required
                    value={editOrgName}
                    onChange={(e) => setEditOrgName(e.target.value)}
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="text-zinc-400 block mb-1 font-semibold">所在城市</label>
                  <input
                    type="text"
                    value={editOrgCity}
                    onChange={(e) => setEditOrgCity(e.target.value)}
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-zinc-400 block mb-1 font-semibold">大群简介</label>
                <textarea
                  rows={2}
                  value={editOrgDesc}
                  onChange={(e) => setEditOrgDesc(e.target.value)}
                  placeholder="介绍大群体背景、参赛口号与训练文化..."
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="space-y-2">
                <label className="text-zinc-400 block font-semibold">大群入会规则</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setEditOrgJoinMode("free")}
                    className={`p-3 rounded-2xl border text-left transition ${
                      editOrgJoinMode === "free"
                        ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                        : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                    }`}
                  >
                    <div className="font-bold text-xs">🟢 自由入会（免邀请码）</div>
                    <div className="text-[10px] text-zinc-400 mt-0.5">跑友无需输入邀请码即可提交大群资料</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditOrgJoinMode("invite")}
                    className={`p-3 rounded-2xl border text-left transition ${
                      editOrgJoinMode === "invite"
                        ? "bg-amber-500/15 border-amber-500/40 text-amber-300"
                        : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                    }`}
                  >
                    <div className="font-bold text-xs">🔒 凭专属邀请码入会</div>
                    <div className="text-[10px] text-zinc-400 mt-0.5">需持有专属邀请码或群成员分享链接</div>
                  </button>
                </div>
              </div>

              <div>
                <label className="text-zinc-400 block mb-1 font-semibold">大群专属邀请码 (3-20位字母/数字)</label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    maxLength={20}
                    value={editOrgInviteCode}
                    onChange={(e) => setEditOrgInviteCode(e.target.value.toUpperCase())}
                    placeholder="例如 FDGOBI"
                    className="flex-1 bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-white font-mono tracking-wider uppercase focus:outline-none focus:border-amber-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
                      let res = "";
                      for (let i = 0; i < 6; i++) res += chars.charAt(Math.floor(Math.random() * chars.length));
                      setEditOrgInviteCode(res);
                    }}
                    className="px-3 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-zinc-200 font-bold"
                  >
                    🎲 随机
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (editOrgInviteCode) {
                        navigator.clipboard.writeText(editOrgInviteCode);
                        alert(`已复制邀请码：${editOrgInviteCode}`);
                      }
                    }}
                    className="px-3 py-2.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 font-bold"
                  >
                    📋 复制
                  </button>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowOrgSettingsModal(false)}
                  className="flex-1 py-3 bg-white/5 hover:bg-white/10 text-zinc-300 rounded-2xl text-xs font-bold transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={savingOrgSettings}
                  className="flex-1 py-3 bg-amber-500 hover:bg-amber-400 text-black rounded-2xl text-xs font-black transition shadow-lg shadow-amber-500/20 disabled:opacity-50"
                >
                  {savingOrgSettings ? "正在保存..." : "保存大群设定"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── 大群主理人 / 管理员：大群准入信息字段配置弹窗（必填 / 选填 / 不显示） ── */}
      {showOrgFieldRulesModal && activeManagedOrg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-purple-500/35 rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-3">
              <div>
                <h3 className="text-lg font-black text-white">
                  🛡️ 【{activeManagedOrg.name}】大群准入信息配置
                </h3>
                <p className="text-[11px] text-purple-300 mt-0.5">
                  逐个字段设为【必填】、【选填】或【不显示】（设为“不显示”后将在入群表单中隐藏且不纳入考核）
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowOrgFieldRulesModal(false)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {loadingOrgFieldRules ? (
                <div className="py-12 text-center text-xs text-zinc-400">正在加载准入规则...</div>
              ) : (
                orgFieldRules.map((rule: any, idx: number) => {
                  const ruleMode: "required" | "optional" | "hidden" =
                    rule.mode === "hidden" || rule.hidden
                      ? "hidden"
                      : rule.mode === "required" || rule.required
                      ? "required"
                      : "optional";
                  const setRuleMode = (nextMode: "required" | "optional" | "hidden") => {
                    setOrgFieldRules((prev) =>
                      prev.map((r, i) =>
                        i === idx
                          ? {
                              ...r,
                              mode: nextMode,
                              required: nextMode === "required",
                              hidden: nextMode === "hidden",
                            }
                          : r
                      )
                    );
                  };
                  return (
                    <div
                      key={rule.field || rule.field_key || idx}
                      className={`flex items-center justify-between gap-3 p-3.5 rounded-2xl border transition ${
                        ruleMode === "required"
                          ? "bg-purple-500/[0.06] border-purple-500/35"
                          : ruleMode === "hidden"
                          ? "bg-black/40 border-white/5 opacity-60"
                          : "bg-white/[0.02] border-white/10"
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`font-bold text-sm ${ruleMode === "hidden" ? "text-zinc-500 line-through" : "text-white"}`}>
                            {idx + 1}. {rule.label}
                          </span>
                          {ruleMode === "required" ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                              必填
                            </span>
                          ) : ruleMode === "hidden" ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-zinc-800 text-zinc-500">
                              不显示
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-300">
                              选填
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center bg-black/50 border border-white/10 rounded-xl p-1 shrink-0 gap-1">
                        <button
                          type="button"
                          onClick={() => setRuleMode("required")}
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                            ruleMode === "required"
                              ? "bg-purple-600 text-white shadow"
                              : "text-zinc-400 hover:text-white"
                          }`}
                        >
                          必填
                        </button>
                        <button
                          type="button"
                          onClick={() => setRuleMode("optional")}
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                            ruleMode === "optional"
                              ? "bg-emerald-600 text-white shadow"
                              : "text-zinc-400 hover:text-white"
                          }`}
                        >
                          选填
                        </button>
                        <button
                          type="button"
                          onClick={() => setRuleMode("hidden")}
                          className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                            ruleMode === "hidden"
                              ? "bg-zinc-700 text-zinc-200 shadow"
                              : "text-zinc-500 hover:text-zinc-300"
                          }`}
                        >
                          不显示
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="pt-4 mt-4 border-t border-white/10 flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3 text-xs text-zinc-400">
                <span>
                  必填:{" "}
                  <strong className="text-purple-400">
                    {orgFieldRules.filter((r) => !(r.mode === "hidden" || r.hidden) && (r.mode === "required" || r.required)).length}
                  </strong>
                </span>
                <span>
                  选填:{" "}
                  <strong className="text-emerald-400">
                    {orgFieldRules.filter((r) => !(r.mode === "hidden" || r.hidden) && !(r.mode === "required" || r.required)).length}
                  </strong>
                </span>
                <span>
                  不显示:{" "}
                  <strong className="text-zinc-500">
                    {orgFieldRules.filter((r) => r.mode === "hidden" || r.hidden).length}
                  </strong>
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setShowOrgFieldRulesModal(false)}
                  className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-bold transition"
                >
                  取消
                </button>
                <button
                  type="button"
                  disabled={savingOrgFieldRules || loadingOrgFieldRules}
                  onClick={handleSaveOrgFieldRules}
                  className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition shadow-lg shadow-purple-600/25 disabled:opacity-50"
                >
                  {savingOrgFieldRules ? "正在保存..." : "保存准入规则"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 大群主理人 / 管理员：大群戈友花名册与审核弹窗 ── */}
      {showOrgRosterModal && activeManagedOrg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-amber-500/35 rounded-3xl max-w-3xl w-full p-6 sm:p-8 shadow-2xl flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-3">
              <div>
                <h3 className="text-lg font-black text-white">
                  👥 【{activeManagedOrg.name}】大群花名册与资料审核 ({orgRosterMembers.length}人)
                </h3>
                <p className="text-[11px] text-zinc-400 mt-0.5">
                  核对成员实名与班级信息并点击【核对通过】；大群主理人可委派或撤销大群管理员
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowOrgRosterModal(false)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <input
              type="text"
              value={orgRosterSearch}
              onChange={(e) => setOrgRosterSearch(e.target.value)}
              placeholder="搜索姓名、班级或戈壁经历..."
              className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white mb-3 focus:outline-none focus:border-amber-500"
            />

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {loadingOrgRoster ? (
                <div className="py-12 text-center text-xs text-zinc-400">正在加载大群花名册...</div>
              ) : (
                orgRosterMembers
                  .filter((m) => {
                    const q = orgRosterSearch.trim().toLowerCase();
                    if (!q) return true;
                    return (
                      (m.real_name || "").toLowerCase().includes(q) ||
                      (m.display_name || "").toLowerCase().includes(q) ||
                      (m.class_name || "").toLowerCase().includes(q) ||
                      (m.gobi_experience || "").toLowerCase().includes(q)
                    );
                  })
                  .map((m) => {
                    const isManagedOrgOwner =
                      activeManagedOrg.role === "owner" || activeManagedOrg.owner_id === user?.id;
                    return (
                      <div
                        key={m.user_id}
                        className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-2xl bg-white/[0.02] border border-white/10"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-white text-sm">
                              {m.real_name || m.display_name || m.user_id}
                            </span>
                            {m.role === "owner" && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                👑 主理人
                              </span>
                            )}
                            {m.role === "admin" && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                                🛡️ 管理员
                              </span>
                            )}
                            <span className="px-2 py-0.5 rounded-full text-[10px] bg-white/10 text-zinc-300">
                              {m.class_name || "未填班级"}
                            </span>
                            {m.gobi_experience && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/15 text-emerald-300">
                                {m.gobi_experience}
                              </span>
                            )}
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                m.status === "confirmed"
                                  ? "bg-emerald-500/20 text-emerald-300"
                                  : m.status === "pending"
                                  ? "bg-amber-500/20 text-amber-300"
                                  : "bg-rose-500/20 text-rose-300"
                              }`}
                            >
                              {m.status === "confirmed" ? "✓ 已认证" : m.status === "pending" ? "⏳ 待审核" : "⚠️ 资料待补"}
                            </span>
                          </div>
                          {m.missing_required_fields && m.missing_required_fields.length > 0 && (
                            <div className="text-[11px] text-rose-400">
                              尚缺必填：{m.missing_required_fields.join("、")}
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {m.status !== "confirmed" && (
                            <button
                              type="button"
                              disabled={orgConfirmingUid === m.user_id}
                              onClick={() => handleOrgConfirmMember(m.user_id)}
                              className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition disabled:opacity-50"
                            >
                              ✓ 核对通过
                            </button>
                          )}
                          {isManagedOrgOwner && m.role !== "owner" && (
                            <button
                              type="button"
                              disabled={orgUpdatingRoleUid === m.user_id}
                              onClick={() =>
                                handleOrgToggleMemberRole(m.user_id, m.role === "admin" ? "member" : "admin")
                              }
                              className="px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-zinc-200 text-xs font-bold transition disabled:opacity-50"
                            >
                              {m.role === "admin" ? "撤销管理员" : "委派管理员"}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
              )}
            </div>
          </div>
        </div>
      )}

      {/* Grand Organization Periodic Report & Sub-Club PK Leaderboard Modal (大群全域跑量报表与分团 PK 榜) */}
      {showOrgReportModal && activeManagedOrg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-3 sm:p-4 overflow-y-auto">
          <div className="bg-[#141418] border border-emerald-500/35 rounded-3xl max-w-6xl w-full p-5 sm:p-7 shadow-2xl space-y-5 my-6 max-h-[92vh] flex flex-col">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4 shrink-0">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-emerald-500/20 text-emerald-300 border border-emerald-500/35">
                    📊 大群全域跑量中台
                  </span>
                  <h3 className="text-lg sm:text-xl font-black text-white">
                    【{orgReportData?.org_name || activeManagedOrg.name}】分跑团 PK 榜与全员跑量透视
                  </h3>
                  {orgReportData?.period_label && (
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                      {orgReportData.period_label} ({orgReportData.start_date} ~ {orgReportData.end_date})
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  自动跨分跑团按 UserID 去重汇总大群总跑量，支持下属各分跑团横向 PK（人均/总跑量/出勤/达标率）、跨团人员透视与游离群员一键分团调配
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0 flex-wrap">
                {orgReportData?.wechat_summary_text && (
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(orgReportData.wechat_summary_text);
                      setCopiedOrgReportText(true);
                      setTimeout(() => setCopiedOrgReportText(false), 2000);
                    }}
                    className="px-3.5 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-black transition cursor-pointer"
                  >
                    {copiedOrgReportText ? "✓ 已复制大群战报" : "📋 一键复制微信大群战报"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleExportOrgReportCsv}
                  disabled={!orgReportData?.member_rankings?.length}
                  className="px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white text-xs font-bold border border-white/15 transition cursor-pointer disabled:opacity-40"
                >
                  📥 导出全员明细 CSV
                </button>
                <button
                  type="button"
                  onClick={() => setShowOrgReportModal(false)}
                  className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Period & Trail Mode Toolbar */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 shrink-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                {[
                  { label: "📅 本周", type: "week" as const, offset: 0 },
                  { label: "⏪ 上周", type: "week" as const, offset: -1 },
                  { label: "🗓️ 本月", type: "month" as const, offset: 0 },
                  { label: "⏮️ 上月", type: "month" as const, offset: -1 },
                ].map((p) => {
                  const active = orgReportPeriodType === p.type && orgReportPeriodOffset === p.offset;
                  return (
                    <button
                      key={`${p.type}_${p.offset}`}
                      type="button"
                      onClick={() => {
                        setOrgReportPeriodType(p.type);
                        setOrgReportPeriodOffset(p.offset);
                        fetchOrgReport(activeManagedOrg.id, p.type, p.offset, orgReportTrailMode);
                      }}
                      className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
                        active
                          ? "bg-emerald-500 text-black font-black shadow-md shadow-emerald-500/20"
                          : "bg-white/5 text-zinc-300 hover:bg-white/10 border border-white/10"
                      }`}
                    >
                      {p.label}
                    </button>
                  );
                })}
              </div>

              <div className="flex items-center gap-1.5 flex-wrap text-xs">
                <span className="text-zinc-400 font-semibold">⛰️ 越野跑计入规则：</span>
                {[
                  { id: "exclude_pace" as const, label: "计入跑量·不拉低配速" },
                  { id: "include" as const, label: "跑量与配速均计入" },
                  { id: "exclude_all" as const, label: "仅统计路跑" },
                ].map((tm) => (
                  <button
                    key={tm.id}
                    type="button"
                    onClick={() => {
                      setOrgReportTrailMode(tm.id);
                      fetchOrgReport(activeManagedOrg.id, orgReportPeriodType, orgReportPeriodOffset, tm.id);
                    }}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                      orgReportTrailMode === tm.id
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                        : "bg-white/5 text-zinc-400 hover:text-white"
                    }`}
                  >
                    {tm.label}
                  </button>
                ))}
              </div>
            </div>

            {loadingOrgReport ? (
              <div className="flex-1 flex items-center justify-center py-16 text-zinc-400 text-sm gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
                <span>正在汇总大群下属各分跑团与全员跑量数据...</span>
              </div>
            ) : orgReportData ? (
              <div className="flex-1 min-h-0 overflow-y-auto space-y-5 pr-1">
                {/* 4 KPI Summary Cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  <div className="bg-[#18181c] border border-emerald-500/25 rounded-2xl p-4">
                    <div className="text-[11px] text-emerald-400 font-bold">🏃 全群去重总跑量 / 人均</div>
                    <div className="text-2xl font-black text-white mt-1 font-mono">
                      {orgReportData.summary?.total_distance_km ?? 0}{" "}
                      <span className="text-xs text-zinc-400 font-sans">km</span>
                    </div>
                    <div className="text-[11px] text-zinc-400 mt-1">
                      全群人均 <strong className="text-emerald-300 font-mono">{orgReportData.summary?.avg_distance_km ?? 0} km</strong> · 共{" "}
                      {orgReportData.summary?.total_runs ?? 0} 次打卡
                    </div>
                  </div>

                  <div className="bg-[#18181c] border border-amber-500/25 rounded-2xl p-4">
                    <div className="text-[11px] text-amber-400 font-bold">🏟️ 下属分跑团 / 人员归属</div>
                    <div className="text-2xl font-black text-white mt-1 font-mono">
                      {orgReportData.summary?.sub_clubs_count ?? 0}{" "}
                      <span className="text-xs text-zinc-400 font-sans">个分团</span>
                    </div>
                    <div className="text-[11px] text-zinc-400 mt-1">
                      大群共 <strong className="text-white">{orgReportData.summary?.total_members ?? 0}</strong> 人 · 未入分团{" "}
                      <strong className="text-rose-400">{orgReportData.summary?.unaffiliated_count ?? 0}</strong> 人
                    </div>
                  </div>

                  <div className="bg-[#18181c] border border-cyan-500/25 rounded-2xl p-4">
                    <div className="text-[11px] text-cyan-400 font-bold">🔥 全群出勤率 / 达标率</div>
                    <div className="text-2xl font-black text-white mt-1 font-mono">
                      {orgReportData.summary?.attendance_rate ?? 0}%{" "}
                      <span className="text-xs text-zinc-400 font-sans">
                        ({orgReportData.summary?.active_members ?? 0}人出勤)
                      </span>
                    </div>
                    <div className="text-[11px] text-zinc-400 mt-1">
                      周期达标({orgReportData.summary?.target_km_threshold ?? 30}km+)：
                      <strong className="text-cyan-300">
                        {orgReportData.summary?.achieved_count ?? 0}人 ({orgReportData.summary?.achievement_rate ?? 0}%)
                      </strong>
                    </div>
                  </div>

                  <div className="bg-[#18181c] border border-purple-500/25 rounded-2xl p-4">
                    <div className="text-[11px] text-purple-400 font-bold">🏅 长距离 LSD 与手表绑定</div>
                    <div className="text-2xl font-black text-white mt-1 font-mono">
                      {orgReportData.summary?.lsd_15k_count ?? 0}{" "}
                      <span className="text-xs text-zinc-400 font-sans">次 15k+</span>
                    </div>
                    <div className="text-[11px] text-zinc-400 mt-1">
                      25k+ 拉练 <strong className="text-purple-300">{orgReportData.summary?.lsd_25k_count ?? 0}</strong> 次 · 手表绑定{" "}
                      <strong className="text-emerald-300">{orgReportData.summary?.watch_bound_rate ?? 0}%</strong>
                    </div>
                  </div>
                </div>

                {/* Sub-navigation Tabs */}
                <div className="flex items-center justify-between gap-2 flex-wrap border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    {[
                      {
                        id: "clubs_pk" as const,
                        label: `🏆 下属分跑团横向 PK 榜 (${orgReportData.sub_club_rankings?.length || 0})`,
                      },
                      {
                        id: "members" as const,
                        label: `👥 跨跑团全员跑量透视表 (${orgReportData.member_rankings?.length || 0})`,
                      },
                      {
                        id: "unaffiliated" as const,
                        label: `⚠️ 未入分跑团游离群员调配 (${orgReportData.unaffiliated_members?.length || 0})`,
                      },
                    ].map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setOrgReportTab(t.id)}
                        className={`px-4 py-2 rounded-xl text-xs font-black transition cursor-pointer ${
                          orgReportTab === t.id
                            ? "bg-amber-500 text-black shadow-lg shadow-amber-500/20"
                            : "bg-white/5 text-zinc-300 hover:bg-white/10"
                        }`}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>

                  {orgReportTab === "clubs_pk" && (
                    <div className="flex items-center gap-1.5 text-xs">
                      <span className="text-zinc-400">PK 排序维度：</span>
                      {[
                        { id: "avg_km" as const, label: "按人均跑量" },
                        { id: "total_km" as const, label: "按总跑量" },
                        { id: "attendance" as const, label: "按出勤率" },
                        { id: "achievement" as const, label: "按达标率" },
                      ].map((s) => (
                        <button
                          key={s.id}
                          type="button"
                          onClick={() => setOrgClubPkSortBy(s.id)}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                            orgClubPkSortBy === s.id
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                              : "bg-white/5 text-zinc-400 hover:text-white"
                          }`}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* TAB 1: 下属分跑团横向 PK 榜 */}
                {orgReportTab === "clubs_pk" && (
                  <div className="space-y-3">
                    {(!orgReportData.sub_club_rankings || orgReportData.sub_club_rankings.length === 0) ? (
                      <div className="text-center py-12 text-zinc-500 text-xs">
                        当前大群暂未挂载下属分跑团，可在大群工作台创建或划入下属分跑团。
                      </div>
                    ) : (
                      [...(orgReportData.sub_club_rankings || [])]
                        .sort((a: any, b: any) => {
                          if (orgClubPkSortBy === "total_km") return (b.total_distance_km || 0) - (a.total_distance_km || 0);
                          if (orgClubPkSortBy === "attendance") return (b.attendance_rate || 0) - (a.attendance_rate || 0);
                          if (orgClubPkSortBy === "achievement") return (b.achievement_rate || 0) - (a.achievement_rate || 0);
                          return (b.avg_distance_km || 0) - (a.avg_distance_km || 0);
                        })
                        .map((sc: any, idx: number) => (
                          <div
                            key={sc.club_id}
                            className="bg-[#18181c] border border-white/10 hover:border-amber-500/40 rounded-2xl p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 transition"
                          >
                            <div className="space-y-2 min-w-0 flex-1">
                              <div className="flex items-center gap-2.5 flex-wrap">
                                <span
                                  className={`w-7 h-7 rounded-xl flex items-center justify-center text-xs font-black ${
                                    idx === 0
                                      ? "bg-amber-400 text-black"
                                      : idx === 1
                                      ? "bg-zinc-300 text-black"
                                      : idx === 2
                                      ? "bg-amber-700 text-white"
                                      : "bg-white/10 text-zinc-300"
                                  }`}
                                >
                                  {idx + 1}
                                </span>
                                <h4 className="text-base font-black text-white">{sc.club_name}</h4>
                                <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-white/5 text-zinc-300 border border-white/10">
                                  在册 {sc.member_count} 人 · 出勤 {sc.active_count} 人 ({sc.attendance_rate}%)
                                </span>
                                <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                  达标 {sc.achieved_count} 人 ({sc.achievement_rate}%)
                                </span>
                              </div>

                              {/* Top 3 runners strip */}
                              {sc.top_members && sc.top_members.length > 0 && (
                                <div className="flex items-center gap-2 flex-wrap text-xs text-zinc-400">
                                  <span className="text-zinc-500 font-semibold">🏅 本团领跑主力：</span>
                                  {sc.top_members.map((tm: any, tIdx: number) => (
                                    <span
                                      key={tm.user_id}
                                      className="px-2 py-0.5 rounded-lg bg-black/40 border border-white/10 text-zinc-200 font-medium"
                                    >
                                      {tIdx === 0 ? "🥇" : tIdx === 1 ? "🥈" : "🥉"} {tm.display_name}{" "}
                                      <strong className="text-emerald-400 font-mono">{tm.distance_km}km</strong>
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>

                            <div className="flex items-center gap-4 sm:gap-6 shrink-0 flex-wrap justify-between lg:justify-end border-t lg:border-t-0 pt-3 lg:pt-0 border-white/10">
                              <div className="text-left lg:text-right">
                                <div className="text-[11px] text-zinc-400">人均跑量 (PK主指标)</div>
                                <div className="text-lg font-black text-amber-400 font-mono">
                                  {sc.avg_distance_km} <span className="text-xs font-sans text-zinc-400">km/人</span>
                                </div>
                              </div>
                              <div className="text-left lg:text-right">
                                <div className="text-[11px] text-zinc-400">分团总跑量</div>
                                <div className="text-lg font-black text-emerald-400 font-mono">
                                  {sc.total_distance_km} <span className="text-xs font-sans text-zinc-400">km</span>
                                </div>
                              </div>
                              <div className="text-left lg:text-right">
                                <div className="text-[11px] text-zinc-400">15k+ / 25k+ 拉练</div>
                                <div className="text-sm font-black text-purple-300 font-mono">
                                  {sc.lsd_15k_count} / {sc.lsd_25k_count} <span className="text-xs font-sans text-zinc-400">次</span>
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => {
                                  setOrgReportClubFilter(sc.club_id);
                                  setOrgReportTab("members");
                                }}
                                className="px-3 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-xs font-bold text-white transition cursor-pointer"
                              >
                                查看该团人员明细 →
                              </button>
                            </div>
                          </div>
                        ))
                    )}
                  </div>
                )}

                {/* TAB 2: 跨跑团全员跑量透视表 */}
                {orgReportTab === "members" && (
                  <div className="space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <button
                          type="button"
                          onClick={() => setOrgReportClubFilter("all")}
                          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
                            orgReportClubFilter === "all"
                              ? "bg-emerald-500 text-black font-black"
                              : "bg-white/5 text-zinc-300 hover:bg-white/10"
                          }`}
                        >
                          全部大群成员 ({orgReportData.member_rankings?.length || 0})
                        </button>
                        {(orgReportData.sub_club_rankings || []).map((sc: any) => (
                          <button
                            key={sc.club_id}
                            type="button"
                            onClick={() => setOrgReportClubFilter(sc.club_id)}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
                              orgReportClubFilter === sc.club_id
                                ? "bg-emerald-500 text-black font-black"
                                : "bg-white/5 text-zinc-300 hover:bg-white/10"
                            }`}
                          >
                            {sc.club_name} ({sc.member_count})
                          </button>
                        ))}
                        <button
                          type="button"
                          onClick={() => setOrgReportClubFilter("unaffiliated")}
                          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
                            orgReportClubFilter === "unaffiliated"
                              ? "bg-rose-500 text-white font-black"
                              : "bg-rose-500/15 text-rose-300 border border-rose-500/30 hover:bg-rose-500/25"
                          }`}
                        >
                          ⚠️ 未入任何分跑团 ({orgReportData.unaffiliated_members?.length || 0})
                        </button>
                      </div>

                      <input
                        type="text"
                        value={orgReportMemberSearch}
                        onChange={(e) => setOrgReportMemberSearch(e.target.value)}
                        placeholder="🔍 搜索姓名 / 班级 / 戈赛组别 / 分跑团..."
                        className="bg-[#1c1c22] border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white w-full sm:w-64 focus:outline-none focus:border-emerald-400"
                      />
                    </div>

                    <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#18181c]">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead>
                          <tr className="border-b border-white/10 text-zinc-400 bg-black/30">
                            <th className="py-3 px-3">排名</th>
                            <th className="py-3 px-3">群员姓名 / 班级 / 组别</th>
                            <th className="py-3 px-3">所属下属分跑团</th>
                            <th className="py-3 px-3">周期跑量</th>
                            <th className="py-3 px-3">打卡次数 / 最长单次</th>
                            <th className="py-3 px-3">平均配速 / 心率</th>
                            <th className="py-3 px-3">手表状态</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-white/5">
                          {(orgReportData.member_rankings || [])
                            .filter((m: any) => {
                              if (orgReportClubFilter === "unaffiliated") return m.is_unaffiliated;
                              if (orgReportClubFilter !== "all") {
                                return (m.sub_club_ids || []).includes(orgReportClubFilter);
                              }
                              return true;
                            })
                            .filter((m: any) => {
                              const q = orgReportMemberSearch.trim().toLowerCase();
                              if (!q) return true;
                              return (
                                (m.display_name || "").toLowerCase().includes(q) ||
                                (m.class_name || "").toLowerCase().includes(q) ||
                                (m.gobi_experience || "").toLowerCase().includes(q) ||
                                (m.sub_club_names || []).join(" ").toLowerCase().includes(q)
                              );
                            })
                            .map((m: any) => (
                              <tr key={m.user_id} className="hover:bg-white/[0.02]">
                                <td className="py-3 px-3 font-mono font-bold text-zinc-300">#{m.rank}</td>
                                <td className="py-3 px-3">
                                  <div className="font-bold text-white">{m.display_name}</div>
                                  <div className="text-[11px] text-zinc-400">
                                    {[m.class_name, m.gobi_experience].filter(Boolean).join(" · ") || "未填班级/组别"}
                                  </div>
                                </td>
                                <td className="py-3 px-3">
                                  {m.is_unaffiliated ? (
                                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                                      ⚠️ 未加入任何分跑团
                                    </span>
                                  ) : (
                                    <div className="flex flex-wrap gap-1">
                                      {(m.sub_club_names || []).map((cn: string, idx: number) => (
                                        <span
                                          key={idx}
                                          className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30"
                                        >
                                          {cn}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </td>
                                <td className="py-3 px-3">
                                  <span className="font-mono font-black text-emerald-400 text-sm">{m.distance_km} km</span>
                                  {m.is_achieved && (
                                    <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300">
                                      达标
                                    </span>
                                  )}
                                </td>
                                <td className="py-3 px-3 font-mono text-zinc-300">
                                  {m.runs_count} 次 · 最长 {m.longest_run_km} km
                                </td>
                                <td className="py-3 px-3 font-mono text-zinc-300">
                                  {m.avg_pace !== "-" ? `${m.avg_pace}/km` : "-"}
                                  {m.avg_hr ? ` · ❤️${m.avg_hr}` : ""}
                                </td>
                                <td className="py-3 px-3">
                                  {m.watch_bound ? (
                                    <span className="text-emerald-400 font-bold">⌚ {m.watch_brand}</span>
                                  ) : (
                                    <span className="text-zinc-500">未绑定</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* TAB 3: 未入分跑团游离群员调配 */}
                {orgReportTab === "unaffiliated" && (
                  <div className="space-y-3">
                    <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-200">
                      💡 以下群员已实名加入【{orgReportData.org_name || activeManagedOrg.name}】大群，但尚未加入任何下属分跑团。大群主理人或管理员可在此一键将其划入对应下属分跑团。
                    </div>
                    {(!orgReportData.unaffiliated_members || orgReportData.unaffiliated_members.length === 0) ? (
                      <div className="text-center py-12 text-emerald-400 text-xs font-bold">
                        🎉 太棒了！当前大群所有在册成员均已归属至少一个下属分跑团，无游离群员。
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {orgReportData.unaffiliated_members.map((um: any) => (
                          <div
                            key={um.user_id}
                            className="bg-[#18181c] border border-white/10 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-white text-sm">{um.display_name}</span>
                                <span className="font-mono text-xs text-emerald-400 font-bold">
                                  本期 {um.distance_km} km ({um.runs_count}次)
                                </span>
                              </div>
                              <div className="text-xs text-zinc-400 mt-0.5">
                                {[um.class_name, um.gobi_experience].filter(Boolean).join(" · ") || "未填写班级与戈赛经历"}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              <select
                                value={assigningMemberClubMap[um.user_id] || orgReportData.sub_club_rankings?.[0]?.club_id || ""}
                                onChange={(e) =>
                                  setAssigningMemberClubMap((prev) => ({
                                    ...prev,
                                    [um.user_id]: e.target.value,
                                  }))
                                }
                                className="bg-black/50 border border-white/15 rounded-xl px-2.5 py-1.5 text-xs text-white"
                              >
                                {(orgReportData.sub_club_rankings || []).map((sc: any) => (
                                  <option key={sc.club_id} value={sc.club_id}>
                                    {sc.club_name}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                disabled={
                                  assigningMemberLoadingUid === um.user_id ||
                                  !(assigningMemberClubMap[um.user_id] || orgReportData.sub_club_rankings?.[0]?.club_id)
                                }
                                onClick={() =>
                                  handleAssignOrgMemberToClub(
                                    um.user_id,
                                    assigningMemberClubMap[um.user_id] || orgReportData.sub_club_rankings?.[0]?.club_id
                                  )
                                }
                                className="px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-black transition cursor-pointer disabled:opacity-40"
                              >
                                {assigningMemberLoadingUid === um.user_id ? "调配中..." : "➕ 划入该分团"}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* Grand Organization Cross-Club Joint Events Modal (跨跑团联合活动与分团对抗赛) */}
      {showOrgEventsModal && activeManagedOrg && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-3 sm:p-4 overflow-y-auto">
          <div className="bg-[#141418] border border-purple-500/35 rounded-3xl max-w-5xl w-full p-5 sm:p-7 shadow-2xl space-y-5 my-6 max-h-[92vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-white/10 pb-4 shrink-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-purple-500/20 text-purple-300 border border-purple-500/35">
                    🚩 大群跨跑团联合活动中心
                  </span>
                  <h3 className="text-lg sm:text-xl font-black text-white">
                    【{activeManagedOrg.name}】组织跨跑团合练与分团对抗赛
                  </h3>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  一键向全部或指定下属分跑团同步发布联合约跑/长距离拉练或跨团里程挑战赛，所有分跑团共享报名池并自动统计各分团参赛贡献榜
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowOrgEventsModal(false)}
                className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto grid grid-cols-1 lg:grid-cols-12 gap-5 pr-1">
              {/* Left 5 cols: Create New Cross-Club Event Form */}
              <form
                onSubmit={handleCreateOrgCrossClubEvent}
                className="lg:col-span-5 bg-[#18181c] border border-white/10 rounded-2xl p-4 sm:p-5 space-y-3.5 text-xs self-start"
              >
                <div className="text-sm font-black text-white flex items-center gap-2">
                  <span>✨ 发起新的跨跑团联合活动</span>
                </div>

                <div>
                  <label className="text-zinc-400 block mb-1 font-semibold">活动类型</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setOrgEvtType("group_run")}
                      className={`py-2 px-3 rounded-xl font-bold border text-left transition cursor-pointer ${
                        orgEvtType === "group_run"
                          ? "bg-purple-500/20 border-purple-400 text-purple-200"
                          : "bg-white/5 border-white/10 text-zinc-400"
                      }`}
                    >
                      📍 跨团联合约跑/大合练
                    </button>
                    <button
                      type="button"
                      onClick={() => setOrgEvtType("distance_challenge")}
                      className={`py-2 px-3 rounded-xl font-bold border text-left transition cursor-pointer ${
                        orgEvtType === "distance_challenge"
                          ? "bg-amber-500/20 border-amber-400 text-amber-200"
                          : "bg-white/5 border-white/10 text-zinc-400"
                      }`}
                    >
                      🏆 跨团里程挑战/PK赛
                    </button>
                  </div>
                </div>

                <div>
                  <label className="text-zinc-400 block mb-1 font-semibold">活动标题</label>
                  <input
                    type="text"
                    required
                    value={orgEvtTitle}
                    onChange={(e) => setOrgEvtTitle(e.target.value)}
                    placeholder="例如：周末全群25km大合练 / 11月分跑团百公里对抗赛"
                    className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2 text-white font-bold"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="text-zinc-400 block mb-1 font-semibold">
                      {orgEvtType === "group_run" ? "集合时间" : "开始日期"}
                    </label>
                    <input
                      type="text"
                      value={orgEvtMeetTime}
                      onChange={(e) => setOrgEvtMeetTime(e.target.value)}
                      placeholder="2026-11-15 06:30"
                      className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-zinc-400 block mb-1 font-semibold">目标里程 (km)</label>
                    <input
                      type="number"
                      min={1}
                      max={1000}
                      value={orgEvtTargetKm}
                      onChange={(e) => setOrgEvtTargetKm(Number(e.target.value) || 10)}
                      className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2 text-white font-mono font-bold"
                    />
                  </div>
                </div>

                {orgEvtType === "group_run" ? (
                  <div className="grid grid-cols-2 gap-2.5">
                    <div>
                      <label className="text-zinc-400 block mb-1 font-semibold">集合地点</label>
                      <input
                        type="text"
                        value={orgEvtLocation}
                        onChange={(e) => setOrgEvtLocation(e.target.value)}
                        placeholder="世纪公园7号门 / 奥森南园"
                        className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-zinc-400 block mb-1 font-semibold">配速分组要求</label>
                      <input
                        type="text"
                        value={orgEvtPaceReq}
                        onChange={(e) => setOrgEvtPaceReq(e.target.value)}
                        placeholder="A组430 / B组515 / C组600"
                        className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2 text-white"
                      />
                    </div>
                  </div>
                ) : (
                  <div>
                    <label className="text-zinc-400 block mb-1 font-semibold">挑战结束日期</label>
                    <input
                      type="date"
                      value={orgEvtEndDate}
                      onChange={(e) => setOrgEvtEndDate(e.target.value)}
                      className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2 text-white font-mono"
                    />
                  </div>
                )}

                <div>
                  <label className="text-zinc-400 block mb-1 font-semibold">联合覆盖范围 (下属分跑团)</label>
                  <div className="flex gap-2 mb-2">
                    <button
                      type="button"
                      onClick={() => setOrgEvtScopeMode("all")}
                      className={`flex-1 py-1.5 rounded-xl font-bold border transition cursor-pointer ${
                        orgEvtScopeMode === "all"
                          ? "bg-emerald-500/20 border-emerald-400 text-emerald-300"
                          : "bg-white/5 border-white/10 text-zinc-400"
                      }`}
                    >
                      🌐 全部下属分跑团 ({orgEventsData?.sub_clubs?.length || 0})
                    </button>
                    <button
                      type="button"
                      onClick={() => setOrgEvtScopeMode("selected")}
                      className={`flex-1 py-1.5 rounded-xl font-bold border transition cursor-pointer ${
                        orgEvtScopeMode === "selected"
                          ? "bg-amber-500/20 border-amber-400 text-amber-300"
                          : "bg-white/5 border-white/10 text-zinc-400"
                      }`}
                    >
                      ☑️ 指定部分分跑团
                    </button>
                  </div>

                  {orgEvtScopeMode === "selected" && (
                    <div className="flex flex-wrap gap-1.5 p-2.5 rounded-xl bg-black/40 border border-white/10">
                      {(orgEventsData?.sub_clubs || []).map((sc: any) => {
                        const checked = orgEvtSelectedClubs.includes(sc.id);
                        return (
                          <button
                            key={sc.id}
                            type="button"
                            onClick={() => {
                              setOrgEvtSelectedClubs((prev) =>
                                checked ? prev.filter((id) => id !== sc.id) : [...prev, sc.id]
                              );
                            }}
                            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                              checked
                                ? "bg-amber-500 text-black font-black"
                                : "bg-white/5 text-zinc-400 hover:text-white"
                            }`}
                          >
                            {checked ? "✓ " : "+ "}
                            {sc.name}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div>
                  <label className="text-zinc-400 block mb-1 font-semibold">活动规程与补给说明</label>
                  <textarea
                    rows={3}
                    value={orgEvtRules}
                    onChange={(e) => setOrgEvtRules(e.target.value)}
                    className="w-full bg-black/40 border border-white/15 rounded-xl px-3 py-2 text-white"
                  />
                </div>

                <button
                  type="submit"
                  disabled={creatingOrgEvent}
                  className="w-full py-2.5 rounded-xl bg-gradient-to-r from-[#FC4C02] to-[#ff6426] hover:from-[#ff6426] hover:to-[#ff7a45] text-white font-black text-xs shadow-lg shadow-[#FC4C02]/25 transition cursor-pointer disabled:opacity-50"
                >
                  {creatingOrgEvent ? "正在同步下发至各分跑团..." : "🚩 立即发布跨跑团联合活动"}
                </button>
              </form>

              {/* Right 7 cols: Active Cross-Club Events & Sub-Club Contribution Breakdown */}
              <div className="lg:col-span-7 space-y-3.5">
                <div className="text-sm font-black text-white flex items-center justify-between">
                  <span>📋 已发布的跨跑团联合活动 ({orgEventsData?.org_events?.length || 0})</span>
                </div>

                {loadingOrgEvents ? (
                  <div className="py-12 flex items-center justify-center text-zinc-400 text-xs gap-2">
                    <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                    <span>正在加载跨跑团联合活动与各分团报名统计...</span>
                  </div>
                ) : !orgEventsData?.org_events?.length ? (
                  <div className="bg-[#18181c] border border-white/10 rounded-2xl p-8 text-center text-xs text-zinc-500">
                    暂未发布跨跑团联合活动。在左侧填写并发布后，将自动置顶出现在各下属分跑团的活动列表中。
                  </div>
                ) : (
                  orgEventsData.org_events.map((ev: any) => (
                    <div
                      key={ev.id}
                      className="bg-[#18181c] border border-purple-500/30 rounded-2xl p-4 sm:p-5 space-y-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-amber-500/20 text-amber-300 border border-amber-500/35">
                              🏛️ 大群联合
                            </span>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-200">
                              {ev.event_type === "group_run" ? "📍 跨团联合约跑" : "🏆 跨团里程挑战"}
                            </span>
                            <h4 className="text-sm sm:text-base font-black text-white">{ev.title}</h4>
                          </div>
                          <div className="text-[11px] text-zinc-400 mt-1 flex flex-wrap gap-3">
                            {ev.meet_time && <span>⏰ {ev.meet_time}</span>}
                            {ev.location && <span>📍 {ev.location}</span>}
                            <span>🎯 目标 {ev.target_km} km</span>
                            {ev.pace_requirement && <span>⚡ {ev.pace_requirement}</span>}
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="text-xs font-black text-emerald-400">
                            已报名 {ev.participants_count || 0} 人 · 完赛 {ev.completed_count || 0} 人
                          </div>
                        </div>
                      </div>

                      {ev.rules && <p className="text-xs text-zinc-300 leading-relaxed">{ev.rules}</p>}

                      {/* Sub-club participation breakdown */}
                      {ev.club_breakdown && ev.club_breakdown.length > 0 && (
                        <div className="pt-2 border-t border-white/10 space-y-1.5">
                          <div className="text-[11px] font-bold text-zinc-400">
                            📊 下属各分跑团报名与完赛跑量贡献榜：
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {ev.club_breakdown.map((cb: any) => (
                              <div
                                key={cb.club_id}
                                className="bg-black/30 border border-white/10 rounded-xl px-3 py-2 flex items-center justify-between text-xs"
                              >
                                <span className="font-bold text-white truncate">{cb.club_name}</span>
                                <span className="text-[11px] text-zinc-300 font-mono shrink-0">
                                  报名 <strong className="text-amber-300">{cb.registered_count}</strong> · 完赛{" "}
                                  <strong className="text-emerald-300">{cb.completed_count}</strong> ·{" "}
                                  <strong className="text-white">{cb.total_km}km</strong>
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Club WeChat Invitation & Forwarding Modal (网页版发出跑团邀请 · 转发微信联系人) */}
      {showClubInviteModal && clubInviteShareData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-[#151518] border border-emerald-500/30 rounded-3xl max-w-3xl w-full p-6 sm:p-7 shadow-2xl space-y-5 my-8">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-emerald-500/20 text-emerald-300 border border-emerald-500/35">
                    💌 微信转发邀请
                  </span>
                  <h3 className="text-lg sm:text-xl font-black text-white">
                    邀请微信好友加入【{clubInviteShareData.name}】
                  </h3>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  支持一键复制高清邀请海报（直接在电脑/手机微信聊天窗口粘贴发送），或复制微信邀请文案与直达链接
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowClubInviteModal(false)}
                className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-stretch">
              {/* Left: Live Visual Invite Poster Card */}
              <div className="md:col-span-6 bg-gradient-to-b from-[#18181c] via-[#121215] to-[#18181c] border border-white/15 rounded-2xl p-5 flex flex-col justify-between space-y-4 shadow-xl relative overflow-hidden">
                <div className="space-y-3">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#FC4C02]/15 border border-[#FC4C02]/40 text-[#ff7a45] text-[11px] font-bold">
                    💌 万跑跑团助手 · 官方入团邀请函
                  </div>
                  <div>
                    <p className="text-sm font-black text-white">
                      {clubInviteShareData.inviter_name
                        ? `👋 跑友【${clubInviteShareData.inviter_name}】诚邀您入团`
                        : "👋 诚邀您加入我们的跑团"}
                    </p>
                    <p className="text-[11px] text-zinc-400 mt-0.5">
                      科学耐力训练 · 佳明/高驰数据直连 · 队友同频共进
                    </p>
                  </div>

                  <div className="bg-[#18181c] border border-white/10 rounded-2xl p-4 space-y-3">
                    <div className="flex items-center gap-3">
                      <img
                        src={clubInviteShareData.logo_url || "/logo.png"}
                        alt={clubInviteShareData.name}
                        className="w-12 h-12 rounded-xl object-cover border border-[#FC4C02]/40 shrink-0"
                      />
                      <div className="min-w-0">
                        <h4 className="text-base font-black text-white truncate">
                          {clubInviteShareData.name}
                        </h4>
                        <div className="flex items-center gap-1.5 flex-wrap mt-1">
                          {clubInviteShareData.org_name && (
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/35">
                              🏛️ {clubInviteShareData.org_name}
                            </span>
                          )}
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                            📍 {clubInviteShareData.city || "上海"} · {clubInviteShareData.member_count || 1} 人
                          </span>
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-zinc-300 line-clamp-2 leading-relaxed">
                      {clubInviteShareData.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。"}
                    </p>

                    <div className="bg-[#FC4C02]/10 border border-[#FC4C02]/35 rounded-xl p-3 flex items-center justify-between">
                      <div>
                        <div className="text-[10px] font-bold text-orange-300">
                          {clubInviteShareData.invite_code
                            ? "🔑 专属入团邀请码（小程序/网页通用）"
                            : "🟢 入团方式"}
                        </div>
                        <div className="text-lg font-mono font-black text-white tracking-widest mt-0.5">
                          {clubInviteShareData.invite_code || "免码自由入团"}
                        </div>
                      </div>
                      {clubInviteShareData.invite_code && (
                        <button
                          type="button"
                          onClick={() => {
                            navigator.clipboard?.writeText(clubInviteShareData.invite_code);
                            setCopiedInviteFlag("code");
                            setTimeout(() => setCopiedInviteFlag(""), 2500);
                          }}
                          className="px-2.5 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-orange-200 text-[11px] font-bold transition"
                        >
                          {copiedInviteFlag === "code" ? "✅ 已复制" : "复制邀请码"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Mini Program QR Code Footer */}
                <div className="bg-[#18181c] border border-white/10 rounded-2xl p-3.5 flex items-center justify-between gap-3">
                  <div className="space-y-1 min-w-0">
                    <div className="text-xs font-black text-[#FC4C02]">
                      📱 微信扫码或长按识别入团
                    </div>
                    <div className="text-xs font-bold text-white">
                      打开「万跑跑团助手」小程序
                    </div>
                    <div className="text-[10px] text-zinc-400">
                      直达受邀跑团主页 · 一键加入
                    </div>
                  </div>
                  <div className="w-20 h-20 rounded-xl bg-white p-1.5 shrink-0 flex items-center justify-center">
                    {loadingClubInviteShare && !clubInviteShareData.qrcode_base64 && !clubInviteShareData.qrcode_url ? (
                      <span className="text-[10px] text-zinc-500 text-center">生成小程序码...</span>
                    ) : clubInviteShareData.qrcode_base64 || clubInviteShareData.qrcode_url ? (
                      <img
                        src={
                          clubInviteShareData.qrcode_base64
                            ? clubInviteShareData.qrcode_base64.startsWith("data:")
                              ? clubInviteShareData.qrcode_base64
                              : `data:image/jpeg;base64,${clubInviteShareData.qrcode_base64}`
                            : clubInviteShareData.qrcode_url
                        }
                        alt="微信小程序入团码"
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <span className="text-[10px] text-zinc-500 text-center">小程序码</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Right: Forwarding Actions for WeChat Contacts */}
              <div className="md:col-span-6 flex flex-col justify-between space-y-4">
                <div className="space-y-4">
                  {/* Action 1: Poster Image Copy/Download */}
                  <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-black text-emerald-300">
                        方式一：发送邀请海报图片给微信好友（推荐）
                      </h4>
                      <span className="text-[10px] text-zinc-400">含专属小程序码</span>
                    </div>
                    <p className="text-[11px] text-zinc-400 leading-relaxed">
                      点击下方「复制海报图片」后，直接切到电脑或手机微信聊天窗口按{" "}
                      <span className="text-white font-mono font-bold">Ctrl+V / Cmd+V</span>{" "}
                      即可把邀请函图片发给微信联系人，对方长按识别二维码即可打开小程序入团。
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      <button
                        type="button"
                        disabled={generatingInvitePoster}
                        onClick={handleCopyClubInvitePosterImage}
                        className="py-2.5 px-3 rounded-xl bg-gradient-to-r from-[#22c55e] to-[#10b981] hover:from-[#4ade80] hover:to-[#34d399] text-black text-xs font-black transition shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                      >
                        {generatingInvitePoster
                          ? "生成海报中..."
                          : copiedInviteFlag === "poster"
                          ? "✅ 已复制图片！去微信粘贴"
                          : "📋 复制海报图片 (微信粘贴)"}
                      </button>
                      <button
                        type="button"
                        disabled={generatingInvitePoster}
                        onClick={handleDownloadClubInvitePoster}
                        className="py-2.5 px-3 rounded-xl bg-white/10 hover:bg-white/15 border border-white/15 text-white text-xs font-bold transition disabled:opacity-50"
                      >
                        💾 下载高清邀请海报 PNG
                      </button>
                    </div>
                  </div>

                  {/* Action 2: WeChat Text + Direct Link Copy */}
                  <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-black text-amber-300">
                        方式二：复制微信邀请文字口令与直达链接
                      </h4>
                      <span className="text-[10px] text-zinc-400">支持微信直接点击</span>
                    </div>
                    <textarea
                      readOnly
                      rows={6}
                      value={clubInviteShareData.share_text || ""}
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl p-3 text-xs text-zinc-200 leading-relaxed focus:outline-none resize-none"
                    />
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard?.writeText(clubInviteShareData.share_text || "");
                          setCopiedInviteFlag("text");
                          setTimeout(() => setCopiedInviteFlag(""), 3000);
                        }}
                        className="flex-1 py-2.5 px-3 rounded-xl bg-[#FC4C02] hover:bg-[#ff6426] text-white text-xs font-black transition shadow-lg shadow-[#FC4C02]/20"
                      >
                        {copiedInviteFlag === "text"
                          ? "✅ 邀请文案已复制！去微信粘贴发送"
                          : "📋 一键复制微信邀请文案"}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard?.writeText(clubInviteShareData.web_invite_url || "");
                          setCopiedInviteFlag("link");
                          setTimeout(() => setCopiedInviteFlag(""), 2500);
                        }}
                        className="py-2.5 px-3 rounded-xl bg-white/10 hover:bg-white/15 text-zinc-200 text-xs font-bold transition"
                      >
                        {copiedInviteFlag === "link" ? "✅ 链接已复制" : "🔗 仅复制链接"}
                      </button>
                      {typeof navigator !== "undefined" && typeof (navigator as any).share === "function" && (
                        <button
                          type="button"
                          onClick={handleNativeShareClubInvite}
                          className="py-2.5 px-3 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-xs font-bold transition"
                        >
                          📲 系统分享转发微信
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <div className="text-[11px] text-zinc-500 bg-white/[0.02] border border-white/5 rounded-xl p-3">
                  💡 提示：微信好友收到链接或海报后，既可在微信内长按识别二维码直接打开小程序一键入团，也可在网页端直接点击「立即加入跑团」。
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Incoming Web Club Invitation Landing Modal (微信好友点击邀请链接打开网页时的入团卡片) */}
      {showReceivedInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 overflow-y-auto">
          <div className="bg-[#151518] border border-emerald-500/40 rounded-3xl max-w-md w-full p-6 sm:p-7 shadow-2xl space-y-5">
            {loadingReceivedInvite ? (
              <div className="py-12 text-center text-sm text-zinc-400">正在加载跑团邀请函...</div>
            ) : receivedInviteData?.club ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="px-3 py-1 rounded-full text-xs font-black bg-emerald-500/20 text-emerald-300 border border-emerald-500/35">
                    🎉 收到跑团入团邀请函
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowReceivedInviteModal(false)}
                    className="p-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div>
                  <p className="text-xs text-zinc-400">
                    {receivedInviteData.inviter_name
                      ? `👋 您的跑友【${receivedInviteData.inviter_name}】诚邀您加入：`
                      : "👋 您的跑友诚邀您加入："}
                  </p>
                  <div className="mt-3 bg-[#1c1c22] border border-white/10 rounded-2xl p-4 flex items-center gap-3.5">
                    <img
                      src={receivedInviteData.club.logo_url || "/logo.png"}
                      alt={receivedInviteData.club.name}
                      className="w-14 h-14 rounded-2xl object-cover border border-[#FC4C02]/40 shrink-0"
                    />
                    <div className="min-w-0">
                      <h3 className="text-lg font-black text-white truncate">
                        {receivedInviteData.club.name}
                      </h3>
                      <div className="flex items-center gap-1.5 flex-wrap mt-1">
                        {receivedInviteData.club.org_name && (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/35">
                            🏛️ {receivedInviteData.club.org_name}
                          </span>
                        )}
                        <span className="text-xs text-zinc-400">
                          📍 {receivedInviteData.club.city || "上海"} · {receivedInviteData.club.member_count || 1} 位跑友
                        </span>
                      </div>
                    </div>
                  </div>
                  {receivedInviteData.club.description && (
                    <p className="text-xs text-zinc-400 mt-3 leading-relaxed">
                      {receivedInviteData.club.description}
                    </p>
                  )}
                </div>

                {(receivedInviteData.qrcode_base64 || receivedInviteData.qrcode_url) && (
                  <div className="bg-[#18181c] border border-white/10 rounded-2xl p-4 flex items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="text-xs font-black text-emerald-400">
                        📱 微信内推荐：长按或扫码入团
                      </div>
                      <div className="text-[11px] text-zinc-300">
                        直接打开「万跑跑团助手」微信小程序一键加入
                      </div>
                    </div>
                    <div className="w-20 h-20 rounded-xl bg-white p-1.5 shrink-0">
                      <img
                        src={
                          receivedInviteData.qrcode_base64
                            ? receivedInviteData.qrcode_base64.startsWith("data:")
                              ? receivedInviteData.qrcode_base64
                              : `data:image/jpeg;base64,${receivedInviteData.qrcode_base64}`
                            : receivedInviteData.qrcode_url
                        }
                        alt="微信小程序入团码"
                        className="w-full h-full object-contain"
                      />
                    </div>
                  </div>
                )}

                <div className="space-y-2.5 pt-1">
                  {receivedInviteData.is_club_member ? (
                    <button
                      type="button"
                      onClick={() => setShowReceivedInviteModal(false)}
                      className="w-full py-3 rounded-2xl bg-emerald-500 text-black text-xs font-black transition"
                    >
                      ✅ 您已是本跑团成员 · 进入跑团主页
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={acceptingReceivedInvite}
                      onClick={handleAcceptReceivedClubInvite}
                      className="w-full py-3 rounded-2xl bg-gradient-to-r from-[#FC4C02] to-[#ff6426] hover:from-[#ff6426] hover:to-[#ff7a45] text-white text-sm font-black transition shadow-lg shadow-[#FC4C02]/25 disabled:opacity-50"
                    >
                      {acceptingReceivedInvite
                        ? "正在加入跑团..."
                        : user?.id
                        ? `🚀 立即一键加入【${receivedInviteData.club.name}】`
                        : `💻 登录网页版并加入【${receivedInviteData.club.name}】`}
                    </button>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}

      {/* Self-Service Create Club Modal */}
      {showCreateClubModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-white/10 rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-black text-white">✨ 创建专属跑团</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              创建后您将自动成为跑团团长兼认证教练，可邀请跑友入团、发起线下约跑并批量派发训练课表（需累计邀请满 3 位绑定手表的跑友解锁）。
            </p>
            <form onSubmit={handleCreateSelfClub} className="space-y-3.5">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">跑团名称</label>
                <input
                  type="text"
                  required
                  maxLength={30}
                  value={newClubName}
                  onChange={(e) => setNewClubName(e.target.value)}
                  placeholder="例如：徐汇滨江晨跑团"
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-400 block mb-1">所在城市</label>
                  <input
                    type="text"
                    value={newClubCity}
                    onChange={(e) => setNewClubCity(e.target.value)}
                    placeholder="上海"
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 block mb-1">入团方式</label>
                  <select
                    value={newClubJoinMode}
                    onChange={(e) => setNewClubJoinMode(e.target.value as "free" | "invite")}
                    className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                  >
                    <option value="free">公开自由入团</option>
                    <option value="invite">仅凭邀请码入团</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">跑团简介（选填）</label>
                <textarea
                  rows={2}
                  value={newClubDesc}
                  onChange={(e) => setNewClubDesc(e.target.value)}
                  placeholder="介绍合练地点、时间与跑团理念..."
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>
              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setShowCreateClubModal(false)}
                  className="flex-1 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-2xl text-xs font-bold transition cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={creatingClub}
                  className="flex-1 py-3 bg-[#FC4C02] hover:bg-[#ff6426] text-white rounded-2xl text-xs font-bold transition disabled:opacity-50 cursor-pointer"
                >
                  {creatingClub ? "创建中..." : "立即创建"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Join Club Modal */}
      {showJoinModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-white/10 rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-black text-white">加入跑团</h3>
            <p className="text-xs text-zinc-400">请输入团长分享的 6 位专属邀请码：</p>
            <form onSubmit={handleJoinClub} className="space-y-4">
              <input
                type="text"
                maxLength={6}
                value={inviteCodeInput}
                onChange={(e) => setInviteCodeInput(e.target.value.toUpperCase())}
                placeholder="请输入专属邀请码"
                className="w-full bg-[#1c1c20] border border-white/10 rounded-2xl px-4 py-3 text-center text-xl font-mono font-bold tracking-widest text-white uppercase focus:outline-none focus:border-[#FC4C02]"
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowJoinModal(false)}
                  className="flex-1 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-2xl text-xs font-bold transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 py-3 bg-[#FC4C02] hover:bg-[#ff6426] text-white rounded-2xl text-xs font-bold transition"
                >
                  立即加入
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* All Clubs Modal (Browse and Select/Join) */}
      {showAllClubsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-white/10 rounded-3xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div>
                <h3 className="text-lg font-black text-white flex items-center gap-2">
                  🏆 平台所有跑团 ({allClubs.length})
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">浏览平台已创建跑团，点击即可切换查看或加入新跑团</p>
              </div>
              <button
                onClick={() => setShowAllClubsModal(false)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="overflow-y-auto space-y-3.5 pr-1 flex-1">
              {allClubs.map((club) => {
                const isCurrent = currentClub?.id === club.id;
                const isMember = clubs.some((c) => c.id === club.id) || club.is_member;

                return (
                  <div
                    key={club.id}
                    className={`border rounded-2xl p-4 flex items-center justify-between gap-4 transition ${
                      isCurrent
                        ? "bg-[#FC4C02]/10 border-[#FC4C02]/40"
                        : "bg-[#1c1c20] border-white/5 hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <img
                        src={club.logo_url || "/logo.png"}
                        alt={club.name}
                        className="w-12 h-12 rounded-xl object-cover border border-white/10 shrink-0"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="text-sm font-bold text-white truncate">{club.name}</h4>
                          {club.org_name && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                              🏛️ {club.org_name}
                            </span>
                          )}
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            club.join_mode === "invite"
                              ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                              : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                          }`}>
                            {club.join_mode === "invite" ? "🔒 需邀请码" : "🟢 自由入团"}
                          </span>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/10 text-zinc-300">
                            {club.city || "上海"}
                          </span>
                          {isCurrent && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FC4C02] text-white">
                              当前查看
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-400 truncate mt-0.5 max-w-md">
                          {club.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。"}
                        </p>
                        <div className="flex items-center gap-3 text-[11px] text-zinc-500 mt-1">
                          <span>团长: {club.owner_name || "平台指定"}</span>
                          <span>·</span>
                          <span className="text-zinc-400">{club.member_count || 1} 位跑者</span>
                        </div>
                      </div>
                    </div>

                    <div className="shrink-0">
                      {isCurrent ? (
                        <span className="text-xs text-[#FC4C02] font-bold px-3 py-1.5 bg-[#FC4C02]/10 rounded-xl">
                          正在查看
                        </span>
                      ) : isMember ? (
                        <button
                          onClick={() => {
                            const target = clubs.find((c) => c.id === club.id) || club;
                            handleSwitchClub(target);
                            setShowAllClubsModal(false);
                          }}
                          className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-xl text-xs font-bold transition"
                        >
                          切换查看
                        </button>
                      ) : (
                        <button
                          onClick={() => {
                            if (club.join_mode === "invite") {
                              const code = window.prompt(`跑团【${club.name}】已设置凭专属邀请码加入，请输入 6 位邀请码：`);
                              if (code) {
                                handleJoinClubDirect(club.id, code.trim().toUpperCase());
                              }
                            } else {
                              handleJoinClubDirect(club.id);
                            }
                          }}
                          disabled={joiningClubId === club.id}
                          className={`px-4 py-2 text-white rounded-xl text-xs font-bold transition shadow-md ${
                            club.join_mode === "invite"
                              ? "bg-amber-600 hover:bg-amber-500 shadow-amber-600/20"
                              : "bg-[#FC4C02] hover:bg-[#ff6426] shadow-[#FC4C02]/20"
                          }`}
                        >
                          {joiningClubId === club.id
                            ? "加入中..."
                            : club.join_mode === "invite"
                            ? "🔑 凭码加入"
                            : "+ 自由加入"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit Event Modal */}
      {showCreateEventModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-white/10 rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-black text-white">
              {editingEvent ? "编辑跑团挑战赛" : "发起跑团月度挑战赛"}
            </h3>
            <form onSubmit={handleCreateOrEditEvent} className="space-y-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">挑战赛标题</label>
                <input
                  type="text"
                  required
                  value={eventTitle}
                  onChange={(e) => setEventTitle(e.target.value)}
                  placeholder="例如: 9月 200km 破风进阶挑战"
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-2xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">目标跑量 (km)</label>
                <input
                  type="number"
                  required
                  value={eventTargetKm}
                  onChange={(e) => setEventTargetKm(Number(e.target.value))}
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-2xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">挑战规则说明</label>
                <textarea
                  rows={3}
                  value={eventRules}
                  onChange={(e) => setEventRules(e.target.value)}
                  placeholder="完赛即可获得专属完赛电子勋章与跑团定制奖章..."
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-2xl px-4 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateEventModal(false);
                    setEditingEvent(null);
                  }}
                  className="flex-1 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-2xl text-xs font-bold transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-blue-600/20"
                >
                  {editingEvent ? "保存修改" : "立即发布"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Club Weekly & Monthly Report Modal (Owner Only) ── */}
      {showReportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 overflow-y-auto">
          <div className="bg-[#141416] border border-amber-500/30 rounded-3xl max-w-2xl w-full p-6 sm:p-8 shadow-2xl space-y-6 my-8 max-h-[90vh] flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-white/10">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-amber-500/20 text-amber-300">
                  <BarChart3 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-black text-white flex items-center gap-2">
                    跑团专属战报与复盘
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-black tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      👑 团长专属
                    </span>
                  </h3>
                  <p className="text-xs text-zinc-400">仅跑团主理人有权查看与导出，方便一键转发微信群</p>
                </div>
              </div>
              <button
                onClick={() => setShowReportModal(false)}
                className="p-2 rounded-xl hover:bg-white/10 text-zinc-400 hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Period Selector Tabs */}
            <div className="space-y-3">
              <div className="flex gap-2 p-1 bg-white/5 rounded-2xl border border-white/10">
                <button
                  onClick={() => handleSwitchReportPeriod("week")}
                  className={`flex-1 py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                    reportPeriodType === "week"
                      ? "bg-amber-500 text-black shadow-md shadow-amber-500/20"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <Calendar className="w-3.5 h-3.5" />
                  <span>周报 (Weekly)</span>
                </button>
                <button
                  onClick={() => handleSwitchReportPeriod("month")}
                  className={`flex-1 py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                    reportPeriodType === "month"
                      ? "bg-amber-500 text-black shadow-md shadow-amber-500/20"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <Calendar className="w-3.5 h-3.5" />
                  <span>月报 (Monthly)</span>
                </button>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => handleSwitchReportOffset(0)}
                  className={`flex-1 py-1.5 rounded-xl text-xs font-bold border transition ${
                    reportPeriodOffset === 0
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                      : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10"
                  }`}
                >
                  {reportPeriodType === "week" ? "本周战报" : "本月战报"}
                </button>
                <button
                  onClick={() => handleSwitchReportOffset(-1)}
                  className={`flex-1 py-1.5 rounded-xl text-xs font-bold border transition ${
                    reportPeriodOffset === -1
                      ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                      : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10"
                  }`}
                >
                  {reportPeriodType === "week" ? "上周战报" : "上月战报"}
                </button>
              </div>

              {/* Trail running filter selector */}
              <div className="p-2 bg-white/[0.03] rounded-2xl border border-white/10 space-y-1.5">
                <div className="flex items-center justify-between px-1">
                  <span className="text-[11px] font-bold text-zinc-300 flex items-center gap-1">
                    🏔️ 越野跑统计口径
                  </span>
                  {reportData && Number(reportData.trail_activities_count || 0) > 0 && (
                    <span className="text-[10px] text-amber-400 font-mono">
                      本周期含越野 {reportData.trail_activities_count} 次 ({reportData.trail_distance_km} km)
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  <button
                    onClick={() => handleSwitchReportTrailMode("include")}
                    className={`py-1.5 px-2 rounded-xl text-[11px] font-bold border transition cursor-pointer ${
                      reportTrailMode === "include"
                        ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm"
                        : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    包含越野 (默认)
                  </button>
                  <button
                    onClick={() => handleSwitchReportTrailMode("exclude_pace")}
                    className={`py-1.5 px-2 rounded-xl text-[11px] font-bold border transition cursor-pointer ${
                      reportTrailMode === "exclude_pace"
                        ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm"
                        : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    仅去除越野配速
                  </button>
                  <button
                    onClick={() => handleSwitchReportTrailMode("exclude_all")}
                    className={`py-1.5 px-2 rounded-xl text-[11px] font-bold border transition cursor-pointer ${
                      reportTrailMode === "exclude_all"
                        ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm"
                        : "bg-white/5 text-zinc-400 border-white/5 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    去除越野跑量/配速
                  </button>
                </div>
              </div>

              {/* View mode switcher */}
              <div className="flex gap-2 p-1 bg-black/40 rounded-xl border border-white/5">
                <button
                  onClick={() => setReportViewMode("poster")}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                    reportViewMode === "poster"
                      ? "bg-gradient-to-r from-amber-500 to-amber-600 text-black shadow-md font-black"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <ImageIcon className="w-3.5 h-3.5" />
                  <span>🎨 战报海报图片样式</span>
                </button>
                <button
                  onClick={() => setReportViewMode("text")}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                    reportViewMode === "text"
                      ? "bg-gradient-to-r from-amber-500 to-amber-600 text-black shadow-md font-black"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <MessageCircle className="w-3.5 h-3.5" />
                  <span>💬 微信群转发文本</span>
                </button>
              </div>
            </div>

            {/* Content Area */}
            {loadingReport ? (
              <div className="py-16 flex flex-col items-center justify-center gap-3">
                <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
                <span className="text-xs text-zinc-400">正在汇算团队跑步大数据...</span>
              </div>
            ) : reportData ? (
              <div className="flex-1 overflow-y-auto space-y-5 pr-1 custom-scrollbar">
                {/* ── POSTER VIEW ── */}
                {reportViewMode === "poster" ? (
                  <div className="p-1">
                    <div className="bg-gradient-to-b from-[#11141d] via-[#151824] to-[#0c0d14] border-2 border-amber-500/40 rounded-3xl p-6 sm:p-7 shadow-2xl space-y-6">
                      {/* Top Branding Header */}
                      <div className="flex items-center justify-between pb-4 border-b border-white/10">
                        <div className="flex items-center gap-3">
                          <img
                            src={currentClub?.logo_url || "/logo.png"}
                            alt=""
                            className="w-12 h-12 rounded-full object-cover border-2 border-amber-400 shadow-md"
                          />
                          <div>
                            <h4 className="text-base font-black text-white">{reportData.club_name || currentClub?.name}</h4>
                            <span className="text-[11px] font-bold text-amber-400">👑 跑团官方战报 · 荣誉榜</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs font-black text-white">{reportData.period_label}</div>
                          <div className="text-[10px] text-zinc-400 font-mono">{reportData.date_range_str}</div>
                          {reportData.trail_mode && reportData.trail_mode !== "include" && (
                            <div className="mt-1 inline-block px-2 py-0.5 rounded-full text-[9px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                              {reportData.trail_mode === "exclude_pace" ? "⏱️ 均速已去除越野跑" : "🛣️ 已去除越野跑量与配速"}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Hero Total Mileage */}
                      <div className="bg-gradient-to-br from-[#fc4c02]/15 via-amber-500/10 to-transparent border border-[#fc4c02]/30 rounded-2xl p-5 text-center space-y-1">
                        <span className="text-[10px] font-bold text-zinc-400 tracking-wider uppercase">全团累计奔跑总里程</span>
                        <div className="flex items-baseline justify-center gap-2">
                          <span className="text-5xl sm:text-6xl font-black text-[#fc4c02] font-mono tracking-tight">{reportData.total_distance_km}</span>
                          <span className="text-2xl font-black text-amber-400">KM</span>
                        </div>
                        <p className="text-[11px] text-zinc-500">汇聚全员热血汗水 · 每一步都在突破极限</p>
                      </div>

                      {/* 4-Metrics Bar */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                        <div className="bg-white/[0.04] border border-white/[0.07] rounded-xl p-3 space-y-0.5">
                          <span className="text-[10px] text-zinc-400">队员出勤率</span>
                          <div className="text-lg font-black text-white">{reportData.attendance_rate_pct}%</div>
                          <span className="text-[9px] text-zinc-500">({reportData.active_members_count}/{reportData.total_members_count}人)</span>
                        </div>
                        <div className="bg-white/[0.04] border border-white/[0.07] rounded-xl p-3 space-y-0.5">
                          <span className="text-[10px] text-zinc-400">全团均速</span>
                          <div className="text-lg font-black text-white font-mono">{reportData.avg_pace_str}</div>
                          <span className="text-[9px] text-zinc-500">有效巡航</span>
                        </div>
                        <div className="bg-white/[0.04] border border-white/[0.07] rounded-xl p-3 space-y-0.5">
                          <span className="text-[10px] text-zinc-400">累计爬升</span>
                          <div className="text-lg font-black text-white">+{reportData.total_elevation_gain_m}m</div>
                          <span className="text-[9px] text-zinc-500">克服重力</span>
                        </div>
                        <div className="bg-white/[0.04] border border-white/[0.07] rounded-xl p-3 space-y-0.5">
                          <span className="text-[10px] text-zinc-400">打卡人次</span>
                          <div className="text-lg font-black text-white">{reportData.total_activities_count} 次</div>
                          <span className="text-[9px] text-zinc-500">坚持印记</span>
                        </div>
                      </div>

                      {/* 🏆 Podium Top 3 */}
                      <div className="bg-white/[0.03] border border-amber-500/25 rounded-2xl p-4 space-y-2.5">
                        <div className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                          <Trophy className="w-4 h-4" />
                          <span>荣誉三甲领奖台</span>
                        </div>
                        {reportData.podium && reportData.podium.length > 0 ? (
                          <div className="space-y-2">
                            {reportData.podium.map((p: any, idx: number) => (
                              <div
                                key={p.user_id}
                                className={`flex items-center justify-between p-2.5 rounded-xl border ${
                                  idx === 0
                                    ? "bg-amber-500/10 border-amber-500/40 shadow-sm"
                                    : idx === 1
                                    ? "bg-slate-400/10 border-slate-400/30"
                                    : "bg-amber-700/10 border-amber-700/30"
                                }`}
                              >
                                <div className="flex items-center gap-2.5">
                                  <span className="text-base font-black">
                                    {idx === 0 ? "🥇 冠军" : idx === 1 ? "🥈 亚军" : "🥉 季军"}
                                  </span>
                                  <img
                                    src={
                                      p.avatar_url ||
                                      "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80"
                                    }
                                    alt=""
                                    className="w-7 h-7 rounded-full object-cover"
                                  />
                                  <div>
                                    <div className="text-xs font-black text-white">{p.display_name}</div>
                                    <div className="text-[10px] text-zinc-400">
                                      {p.runs_count} 次打卡 · 均速 {p.avg_pace_str}
                                    </div>
                                  </div>
                                </div>
                                <div className="text-right">
                                  <span className="text-sm font-black text-[#fc4c02] font-mono">{p.distance_km}</span>
                                  <span className="text-[10px] text-zinc-500 ml-1">km</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-center py-3 text-xs text-zinc-500">本周期暂无打卡记录</div>
                        )}
                      </div>

                      {/* 🌟 Highlights */}
                      {(reportData.hardcore_runner || reportData.longest_run) && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                          {reportData.hardcore_runner && (
                            <div className="bg-sky-500/[0.06] border border-sky-500/25 rounded-xl p-3 space-y-0.5">
                              <span className="text-[10px] font-bold text-sky-400">🌟 毅力先锋</span>
                              <div className="text-xs font-black text-white">{reportData.hardcore_runner.display_name}</div>
                              <div className="text-[10px] text-zinc-400">
                                打卡 {reportData.hardcore_runner.runs_count} 次 · {reportData.hardcore_runner.distance_km} km
                              </div>
                            </div>
                          )}
                          {reportData.longest_run && (
                            <div className="bg-sky-500/[0.06] border border-sky-500/25 rounded-xl p-3 space-y-0.5">
                              <span className="text-[10px] font-bold text-sky-400">🚀 最长突破</span>
                              <div className="text-xs font-black text-white">{reportData.longest_run.runner_name}</div>
                              <div className="text-[10px] text-zinc-400">
                                单次 {reportData.longest_run.distance_km} km · {reportData.longest_run.avg_pace_str}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* 💡 Renato Canova Review */}
                      <div className="bg-gradient-to-br from-purple-500/10 via-[#181624] to-[#181624] border border-purple-500/35 rounded-2xl p-4 space-y-1.5">
                        <div className="text-xs font-bold text-purple-400 flex items-center gap-1.5">
                          <Sparkles className="w-4 h-4" />
                          <span>Renato Canova 科学耐力团队复盘</span>
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed italic">“{reportData.canova_critique}”</p>
                      </div>

                      {/* Bottom Stamp & Pure Mini-Program QR Code */}
                      <div className="flex items-center justify-between gap-4 pt-4 border-t border-white/10">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-black text-white tracking-wider">万跑跑团助手</span>
                            <span className="px-2 py-0.5 rounded text-[9px] font-black tracking-wider text-amber-400 border border-amber-400/60">
                              官方认证战报
                            </span>
                          </div>
                          <div className="text-xs font-bold text-amber-300">微信扫码打开万跑跑团助手小程序</div>
                          <div className="text-[10px] text-zinc-500">万跑跑团助手 · 科学耐力训练与跑团系统</div>
                        </div>
                        {(reportData.qrcode_base64 || reportData.qrcode_url) && (
                          <div className="shrink-0 flex flex-col items-center gap-1">
                            <div className="p-1.5 bg-white rounded-xl shadow-md">
                              <img
                                src={
                                  reportData.qrcode_base64
                                    ? `data:image/jpeg;base64,${reportData.qrcode_base64}`
                                    : reportData.qrcode_url
                                }
                                alt="万跑跑团小程序码"
                                className="w-16 h-16 sm:w-20 sm:h-20 object-contain"
                              />
                            </div>
                            <span className="text-[10px] text-zinc-400 font-medium">微信扫码体验</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  /* ── TEXT VIEW ── */
                  <div className="bg-[#0e0e11] border border-emerald-500/30 rounded-2xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                        <MessageCircle className="w-4 h-4" />
                        微信群转发排版预览
                      </span>
                      <span className="text-[10px] text-zinc-500 font-mono">支持直接复制</span>
                    </div>
                    <pre className="p-3 bg-black/60 rounded-xl text-[11px] text-zinc-200 font-mono whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto custom-scrollbar border border-white/5">
                      {reportData.forward_text}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-zinc-500">无法加载战报数据</div>
            )}

            {/* Footer Actions */}
            <div className="flex flex-col sm:flex-row gap-2.5 pt-3 border-t border-white/10">
              {reportViewMode === "poster" ? (
                <>
                  <button
                    onClick={handleDownloadPosterImage}
                    disabled={!reportData}
                    className="flex-1 py-3 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-black rounded-2xl text-xs font-black transition shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <ImageIcon className="w-4 h-4" />
                    <span>🖼️ 下载海报长图 (PNG)</span>
                  </button>
                  <button
                    onClick={handleCopyReportText}
                    disabled={!reportData}
                    className="py-3 px-4 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 rounded-2xl text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    {copiedReportText ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    <span>{copiedReportText ? "已复制！" : "📋 复制文本"}</span>
                  </button>
                  <button
                    onClick={handleExportReportFile}
                    disabled={!reportData}
                    className="py-3 px-4 bg-white/10 hover:bg-white/15 disabled:opacity-50 text-zinc-200 rounded-2xl text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer border border-white/10"
                  >
                    <Download className="w-4 h-4" />
                    <span>导出</span>
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={handleCopyReportText}
                    disabled={!reportData}
                    className="flex-1 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-2xl text-xs font-black transition shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2 cursor-pointer"
                  >
                    {copiedReportText ? (
                      <>
                        <Check className="w-4 h-4 text-white" />
                        <span>已复制到剪贴板，可直接发微信群！</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4" />
                        <span>📋 一键复制微信群转发文本</span>
                      </>
                    )}
                  </button>
                  <button
                    onClick={handleExportReportFile}
                    disabled={!reportData}
                    className="py-3 px-5 bg-white/10 hover:bg-white/15 disabled:opacity-50 text-zinc-200 rounded-2xl text-xs font-bold transition flex items-center justify-center gap-2 cursor-pointer border border-white/10"
                  >
                    <Download className="w-4 h-4" />
                    <span>📥 导出战报文本</span>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Dissolve Club Confirmation (Owner / Admin) ── */}
      {showDissolveModal && currentClub && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-md bg-[#141416] border border-red-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl">
            <button
              onClick={() => {
                setShowDissolveModal(false);
                setDissolveConfirmName("");
              }}
              className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-2xl bg-red-500/20 border border-red-500/30 flex items-center justify-center text-red-400 shrink-0">
                <Trash2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">解散并删除跑团</h3>
                <p className="text-xs text-zinc-400">仅跑团团长与超级管理员有权操作</p>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-3.5 bg-white/5 border border-white/10 rounded-2xl space-y-2">
                <div className="flex justify-between">
                  <span className="text-zinc-400">待解散跑团:</span>
                  <span className="font-bold text-white">{currentClub.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">跑团成员数:</span>
                  <span className="text-zinc-300">{dashboardMetrics?.members_count || members.length || 1} 人</span>
                </div>
              </div>

              {/* Data Safety Reassurance */}
              <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl space-y-1.5">
                <div className="font-bold text-emerald-400 flex items-center gap-1.5 text-xs">
                  <Shield className="w-4 h-4 text-emerald-400" />
                  队员个人数据安全保障
                </div>
                <p className="text-[11px] text-emerald-300/90 leading-relaxed">
                  本操作仅解散跑团组织与成员从属关系。全体队员的<strong>个人账号、个人跑者档案、历史打卡记录、GPS轨迹与生理负荷数据将 100% 完整保留</strong>，不受任何影响！
                </p>
              </div>

              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-2xl">
                <p className="text-[11px] text-red-300/90 leading-relaxed">
                  ⚠️ 跑团解散后无法恢复，跑团活动及团队排行榜将被清理。
                </p>
              </div>

              <form onSubmit={handleDissolveClub} className="space-y-4 pt-2">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                    请输入跑团全名 <span className="text-red-400 font-bold">"{currentClub.name}"</span> 确认解散：
                  </label>
                  <input
                    type="text"
                    required
                    value={dissolveConfirmName}
                    onChange={(e) => setDissolveConfirmName(e.target.value)}
                    placeholder={currentClub.name}
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-red-500"
                  />
                </div>

                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setShowDissolveModal(false);
                      setDissolveConfirmName("");
                    }}
                    className="flex-1 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-bold transition"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={dissolving || dissolveConfirmName.trim() !== currentClub.name.trim()}
                    className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:hover:bg-red-600 text-white text-xs font-bold transition shadow-lg shadow-red-600/30 flex items-center justify-center gap-1.5"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>{dissolving ? "解散中..." : "确认解散跑团"}</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Mentorship Bind / Invite (🥋 师徒传帮带结对弹窗) ── */}
      {showMentorshipBindModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-lg bg-[#141416] border border-emerald-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-5">
            <button
              onClick={() => setShowMentorshipBindModal(false)}
              className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
            >
              <X className="w-5 h-5" />
            </button>
            <div>
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <span>🥋 师徒传帮带 · 1对1结对</span>
              </h3>
              <p className="text-xs text-zinc-400 mt-1">
                每位队员可绑定 1 位师傅，每位师傅最多可同时带 3 位徒弟。在同一个大群内（如复旦戈大群）支持跨跑团结对，师傅可查看徒弟全部训练与睡眠恢复数据。
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => setMentorshipBindRole("as_mentee")}
                className={`py-2.5 px-3 rounded-2xl text-xs font-bold border transition ${
                  mentorshipBindRole === "as_mentee"
                    ? "bg-emerald-500/20 border-emerald-400 text-emerald-200"
                    : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                }`}
              >
                🙏 我要拜师（输入师傅ID）
              </button>
              <button
                type="button"
                onClick={() => setMentorshipBindRole("as_mentor")}
                className={`py-2.5 px-3 rounded-2xl text-xs font-bold border transition ${
                  mentorshipBindRole === "as_mentor"
                    ? "bg-emerald-500/20 border-emerald-400 text-emerald-200"
                    : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                }`}
              >
                🥋 我要收徒（输入徒弟ID）
              </button>
            </div>

            <form onSubmit={handleBindMentorshipWeb} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-zinc-300 mb-1.5">
                  {mentorshipBindRole === "as_mentee"
                    ? "输入师傅的跑者 ID（或从下方本团成员快捷选择）："
                    : "输入徒弟的跑者 ID（或从下方本团成员快捷选择）："}
                </label>
                <input
                  type="text"
                  required
                  value={mentorshipTargetUid}
                  onChange={(e) => setMentorshipTargetUid(e.target.value)}
                  placeholder="例如 user_xxxx 或 wx_xxxx"
                  className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-400"
                />
              </div>

              {members.length > 1 && (
                <div>
                  <span className="block text-[11px] text-zinc-400 mb-1.5">本团成员快捷点选（跨团成员请直接输入对方跑者ID）：</span>
                  <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2 bg-black/30 rounded-xl border border-white/5">
                    {members
                      .filter((m: any) => m.user_id !== user?.id)
                      .map((m: any) => (
                        <button
                          key={m.user_id}
                          type="button"
                          onClick={() => setMentorshipTargetUid(m.user_id)}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition ${
                            mentorshipTargetUid === m.user_id
                              ? "bg-emerald-500 text-black font-bold"
                              : "bg-white/5 text-zinc-300 hover:bg-white/10"
                          }`}
                        >
                          {m.display_name}
                        </button>
                      ))}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowMentorshipBindModal(false)}
                  className="flex-1 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-bold transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={bindingMentorship || !mentorshipTargetUid.trim()}
                  className="flex-1 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-black text-xs font-black transition"
                >
                  {bindingMentorship ? "结对中..." : "确认结对"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: Mentee Full Training & Rest Data Detail (🥋 师傅专属查看徒弟全量训练与恢复档案) ── */}
      {selectedMenteeDetail?.mentee && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-3xl max-h-[88vh] overflow-y-auto bg-[#141416] border border-emerald-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <button
              onClick={() => setSelectedMenteeDetail(null)}
              className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center justify-between gap-4 pr-8">
              <div className="flex items-center gap-3.5">
                <img
                  src={
                    selectedMenteeDetail.mentee.avatar_url ||
                    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                  }
                  alt={selectedMenteeDetail.mentee.display_name}
                  className="w-14 h-14 rounded-full object-cover border-2 border-emerald-500/40"
                />
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-lg font-black text-white">{selectedMenteeDetail.mentee.display_name}</h3>
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      🥋 师徒专属全量档案（含保密轨迹与HRV）
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    所属跑团：{(selectedMenteeDetail.mentee.clubs || []).join(" · ") || "同大群成员"} · 全马PB：
                    {selectedMenteeDetail.mentee.marathon_pb_str || "—"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => {
                    const mId = selectedMenteeDetail.mentee.mentee_id || selectedMenteeDetail.mentee.user_id;
                    setSelectedMenteeDetail(null);
                    router.push(`/dashboard/analysis?student_user_id=${encodeURIComponent(mId)}`);
                  }}
                  className="px-3.5 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/35 text-cyan-300 text-xs font-bold transition"
                >
                  📊 生理与VDOT全景 ›
                </button>
                <button
                  onClick={() =>
                    handleUnbindMentorshipWeb(
                      user?.id,
                      selectedMenteeDetail.mentee.mentee_id,
                      selectedMenteeDetail.mentee.display_name
                    )
                  }
                  className="px-3 py-1.5 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300 text-xs font-bold transition"
                >
                  解除师徒关系
                </button>
              </div>
            </div>

            {/* Rest & Recovery Metrics Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-[#1b1e24] border border-white/10 rounded-2xl p-3.5">
                <span className="text-[11px] text-zinc-400">💓 最新静息心率</span>
                <div className="text-lg font-black text-emerald-300 mt-0.5">
                  {selectedMenteeDetail.mentee.rest_summary?.latest_resting_hr || "—"}{" "}
                  <span className="text-xs font-normal text-zinc-400">bpm</span>
                </div>
              </div>
              <div className="bg-[#1b1e24] border border-white/10 rounded-2xl p-3.5">
                <span className="text-[11px] text-zinc-400">📈 最新晨起 HRV</span>
                <div className="text-lg font-black text-cyan-300 mt-0.5">
                  {selectedMenteeDetail.mentee.rest_summary?.latest_hrv || "—"}{" "}
                  <span className="text-xs font-normal text-zinc-400">ms</span>
                </div>
              </div>
              <div className="bg-[#1b1e24] border border-white/10 rounded-2xl p-3.5">
                <span className="text-[11px] text-zinc-400">😴 睡眠得分 / 时长</span>
                <div className="text-lg font-black text-purple-300 mt-0.5">
                  {selectedMenteeDetail.mentee.rest_summary?.latest_sleep_score || "—"}分{" "}
                  <span className="text-xs font-normal text-zinc-400">
                    ({selectedMenteeDetail.mentee.rest_summary?.latest_sleep_hours || "—"}h)
                  </span>
                </div>
              </div>
              <div className="bg-[#1b1e24] border border-white/10 rounded-2xl p-3.5">
                <span className="text-[11px] text-zinc-400">⚡ 疲劳指数 TSB / 伤痛</span>
                <div className="text-lg font-black text-amber-300 mt-0.5">
                  TSB {selectedMenteeDetail.mentee.training_summary?.tsb ?? 0}{" "}
                  <span className="text-xs font-normal text-zinc-400">
                    · {selectedMenteeDetail.mentee.rest_summary?.injury_note || "无伤痛"}
                  </span>
                </div>
              </div>
            </div>

            {/* 14-Day Biometrics & Sleep Log */}
            {(selectedMenteeDetail.mentee.rest_summary?.recent_biometrics || []).length > 0 && (
              <div className="bg-[#181a20] border border-white/10 rounded-2xl p-4 space-y-2.5">
                <h4 className="text-xs font-bold text-emerald-300">🛌 近 14 日晨起静息心率 · HRV · 睡眠恢复记录</h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-44 overflow-y-auto">
                  {selectedMenteeDetail.mentee.rest_summary.recent_biometrics.map((b: any, idx: number) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between px-3 py-2 rounded-xl bg-black/30 border border-white/5 text-xs"
                    >
                      <span className="font-bold text-zinc-300">{b.date}</span>
                      <span className="text-zinc-400">
                        静息 {b.resting_hr || "—"} · HRV {b.hrv || "—"} · 睡眠 {b.sleep_score || "—"}分
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Running Activities */}
            <div className="bg-[#181a20] border border-white/10 rounded-2xl p-4 space-y-3">
              <h4 className="text-xs font-bold text-white">
                🏃 最近跑步训练记录（近7天 {selectedMenteeDetail.mentee.training_summary?.week_km || 0}km · 本月{" "}
                {selectedMenteeDetail.mentee.training_summary?.month_km || 0}km）
              </h4>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {(selectedMenteeDetail.recent_activities || []).map((act: any) => (
                  <div
                    key={act.id}
                    className="flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-black/30 border border-white/5 text-xs"
                  >
                    <div>
                      <div className="font-bold text-white">
                        {act.name} · {act.distance_km} km
                      </div>
                      <div className="text-[11px] text-zinc-400 mt-0.5">
                        配速 {act.avg_pace} · 心率 {act.average_heartrate || "—"} bpm · TRIMP {act.trimp || "—"}
                      </div>
                    </div>
                    <span className="text-[11px] text-zinc-500">{String(act.start_time || "").slice(0, 10)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {user?.id && (
        <PersonalReportModal
          isOpen={showPersonalReportModal}
          onClose={() => setShowPersonalReportModal(false)}
          userId={user.id}
        />
      )}

      {showScheduleImportModal && currentClub?.id && user?.id && (
        <CoachScheduleImportModal
          isOpen={showScheduleImportModal}
          clubId={currentClub.id}
          coachUid={user.id}
          students={coachCockpit?.students || []}
          onClose={() => setShowScheduleImportModal(false)}
          onAssignedSuccess={async () => {
            await loadClubDetails(currentClub.id, user.id);
            await loadCoachTemplates();
          }}
        />
      )}

      {/* ── 🛡️ 防误触：团长移出队员二次确认弹窗 (Anti-Misoperation Remove Member Modal) ── */}
      {removeMemberTarget && currentClub && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-md bg-[#141416] border border-rose-500/40 rounded-3xl p-6 sm:p-7 shadow-2xl space-y-5">
            <button
              onClick={() => {
                setRemoveMemberTarget(null);
                setRemoveMemberChecked(false);
              }}
              className="absolute top-5 right-5 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2.5 text-rose-400">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-base font-black text-white">防误触 · 移出跑团成员确认</h3>
            </div>

            <div className="flex items-center gap-3.5 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30">
              <img
                src={
                  removeMemberTarget.avatar_url ||
                  "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                }
                alt={removeMemberTarget.display_name}
                className="w-12 h-12 rounded-full object-cover border border-rose-500/40 shrink-0"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-black text-white text-sm truncate">
                    {removeMemberTarget.display_name || "该成员"}
                  </span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300">
                    {removeMemberTarget.role === "coach" ? "🧢 教练" : "🏃 队员"}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-0.5">
                  加入时间：{String(removeMemberTarget.joined_at_display || removeMemberTarget.joined_at || "近期").slice(0, 16)} · 本月 {removeMemberTarget.month_km ?? 0} km
                </p>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-[#18181c] border border-white/10 text-xs text-zinc-300 space-y-2 leading-relaxed">
              <div className="font-bold text-white">📌 移出影响说明（请仔细核对）：</div>
              <div>
                1. 移出后，【{removeMemberTarget.display_name}】将离开跑团【{currentClub.name}】，不再参与本团排行榜与打卡动态。
              </div>
              <div className="text-emerald-400 font-semibold">
                2. 🛡️ 该跑友个人的所有历史运动记录、手表绑定与跑力档案 100% 完整保留，不受任何影响。
              </div>
            </div>

            <label className="flex items-start gap-3 p-3.5 rounded-2xl border border-rose-500/35 bg-rose-500/10 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={removeMemberChecked}
                onChange={(e) => setRemoveMemberChecked(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-rose-500"
              />
              <span className="text-xs font-bold text-white leading-snug">
                我已核对【{removeMemberTarget.display_name}】身份，确认将其移出跑团【{currentClub.name}】
              </span>
            </label>

            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={() => {
                  setRemoveMemberTarget(null);
                  setRemoveMemberChecked(false);
                }}
                className="flex-1 py-2.5 rounded-2xl bg-white/10 hover:bg-white/15 text-xs font-bold text-zinc-200 transition"
              >
                取消，保留队员
              </button>
              <button
                disabled={!removeMemberChecked || removeMemberCountdown > 0 || removingMemberLoading}
                onClick={confirmRemoveMemberExecution}
                className={`flex-1 py-2.5 rounded-2xl text-xs font-black transition ${
                  !removeMemberChecked || removeMemberCountdown > 0
                    ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
                    : "bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/30"
                }`}
              >
                {removingMemberLoading
                  ? "正在移出..."
                  : removeMemberCountdown > 0
                  ? `请核对信息 (${removeMemberCountdown}s)`
                  : removeMemberChecked
                  ? "确认移出该队员"
                  : "请先勾选确认"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 🛡️ 防误触：队员主动退出跑团二次确认弹窗 (Anti-Misoperation Leave Club Modal) ── */}
      {showLeaveClubModal && currentClub && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-md bg-[#141416] border border-rose-500/40 rounded-3xl p-6 sm:p-7 shadow-2xl space-y-5">
            <button
              onClick={() => {
                setShowLeaveClubModal(false);
                setLeaveClubChecked(false);
              }}
              className="absolute top-5 right-5 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2.5 text-rose-400">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-base font-black text-white">防误触 · 退出跑团确认</h3>
            </div>

            <div className="flex items-center gap-3.5 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30">
              <img
                src={currentClub.logo_url || "/logo.png"}
                alt={currentClub.name}
                className="w-12 h-12 rounded-2xl object-cover border border-rose-500/40 shrink-0"
              />
              <div className="min-w-0">
                <div className="font-black text-white text-sm truncate">{currentClub.name}</div>
                <p className="text-xs text-zinc-400 mt-0.5">
                  📍 {currentClub.city || "上海"} · 当前角色：{currentRole === "coach" ? "🧢 认证教练" : "🏃 跑团成员"}
                </p>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-[#18181c] border border-white/10 text-xs text-zinc-300 space-y-2 leading-relaxed">
              <div className="font-bold text-white">📌 退出跑团说明：</div>
              <div>
                1. 退出后，您将离开【{currentClub.name}】的月度英雄榜、跑友圈打卡动态与跑团约跑活动。
              </div>
              <div className="text-emerald-400 font-semibold">
                2. 🛡️ 您的所有个人跑步记录、手表连接、VDOT 跑力与个人训练计划 100% 完整保留，绝不丢失。
              </div>
              <div>
                3. 若本跑团开启了邀请码准入，后续重新加入需再次输入邀请码。
              </div>
            </div>

            <label className="flex items-start gap-3 p-3.5 rounded-2xl border border-rose-500/35 bg-rose-500/10 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={leaveClubChecked}
                onChange={(e) => setLeaveClubChecked(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-rose-500"
              />
              <span className="text-xs font-bold text-white leading-snug">
                我已了解退出影响，确认主动退出【{currentClub.name}】
              </span>
            </label>

            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={() => {
                  setShowLeaveClubModal(false);
                  setLeaveClubChecked(false);
                }}
                className="flex-1 py-2.5 rounded-2xl bg-white/10 hover:bg-white/15 text-xs font-bold text-zinc-200 transition"
              >
                我再想想
              </button>
              <button
                disabled={!leaveClubChecked || leaveClubCountdown > 0 || leavingClubLoading}
                onClick={confirmLeaveClubExecution}
                className={`flex-1 py-2.5 rounded-2xl text-xs font-black transition ${
                  !leaveClubChecked || leaveClubCountdown > 0
                    ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
                    : "bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-600/30"
                }`}
              >
                {leavingClubLoading
                  ? "正在退出..."
                  : leaveClubCountdown > 0
                  ? `请核对信息 (${leaveClubCountdown}s)`
                  : leaveClubChecked
                  ? "确认退出跑团"
                  : "请先勾选确认"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function roundKm(meters?: number): string {
  if (!meters) return "0.0";
  return (meters / 1000.0).toFixed(1);
}
