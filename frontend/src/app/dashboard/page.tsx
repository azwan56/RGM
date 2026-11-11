"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import GarminConnectModal from "@/components/GarminConnectModal";
import RouteMapPreview from "@/components/RouteMapPreview";
import OrgRequirementModal, { OrgReminderInfo } from "@/components/OrgRequirementModal";
import PersonalShareCardModal from "@/components/PersonalShareCardModal";
import PersonalReportModal from "@/components/PersonalReportModal";
import {
  Zap,
  Activity,
  Heart,
  Moon,
  BatteryCharging,
  RefreshCw,
  Trophy,
  ChevronRight,
  ChevronLeft,
  Clock,
  Loader2,
  Flame,
  Calendar,
  Target,
  Check,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
  Users,
  Sparkles,
} from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  BarChart,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

function computeCurrentWeekIndex(planData: any): number {
  if (!planData) return 1;
  if (planData.current_week_index) return planData.current_week_index;
  const weeks = planData.schedule_data?.weeks || [];
  if (!weeks.length) return 1;

  const now = new Date();
  const beijingTime = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000);
  const y = beijingTime.getFullYear();
  const m = String(beijingTime.getMonth() + 1).padStart(2, "0");
  const d = String(beijingTime.getDate()).padStart(2, "0");
  const todayStr = `${y}-${m}-${d}`;

  for (const w of weeks) {
    const days = w.days || [];
    if (days.some((day: any) => day.date === todayStr)) {
      return w.week_index || 1;
    }
    const dates = days.map((day: any) => day.date).filter(Boolean);
    if (dates.length && dates[0] <= todayStr && todayStr <= dates[dates.length - 1]) {
      return w.week_index || 1;
    }
  }
  return weeks[0]?.week_index || 1;
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [expandedTrackId, setExpandedTrackId] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [scienceData, setScienceData] = useState<any>(null);
  const [garminModalOpen, setGarminModalOpen] = useState(false);
  const [modalBrand, setModalBrand] = useState<"garmin" | "coros">("garmin");
  const [shareCardModalOpen, setShareCardModalOpen] = useState(false);
  const [shareCardActivityId, setShareCardActivityId] = useState<string>("");

  // Training Plan & Coach Diagnosis states
  const [activePlan, setActivePlan] = useState<any>(null);
  const [planWeekIdx, setPlanWeekIdx] = useState<number>(1);
  const [togglingDayKey, setTogglingDayKey] = useState<string | null>(null);
  const [coachReport, setCoachReport] = useState<any>(null);
  const [userRaces, setUserRaces] = useState<any[]>([]);

  // Running Club & Mentorship states
  const [myClubs, setMyClubs] = useState<any[]>([]);
  const [activeClub, setActiveClub] = useState<any>(null);
  const [clubMetrics, setClubMetrics] = useState<any>(null);
  const [clubLeaderboard, setClubLeaderboard] = useState<any[]>([]);
  const [clubFeed, setClubFeed] = useState<any[]>([]);
  const [mentorshipOverview, setMentorshipOverview] = useState<any>(null);
  const [clubTab, setClubTab] = useState<"leaderboard" | "feed">("leaderboard");

  // Month activities states
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1);
  const [monthActivities, setMonthActivities] = useState<any[]>([]);
  const [loadingMonthActs, setLoadingMonthActs] = useState<boolean>(false);
  const [showAllMonthActs, setShowAllMonthActs] = useState<boolean>(false);
  const [updatingExcludeId, setUpdatingExcludeId] = useState<string | null>(null);

  // Goal switcher ('week' | 'month' | 'year')
  const [activeGoalTab, setActiveGoalTab] = useState<"week" | "month" | "year">("week");

  // Grand Org field requirements reminder states
  const [userOrgs, setUserOrgs] = useState<any[]>([]);
  const [orgReminder, setOrgReminder] = useState<OrgReminderInfo | null>(null);
  const [showOrgReminderModal, setShowOrgReminderModal] = useState<boolean>(false);
  const [personalReportModalOpen, setPersonalReportModalOpen] = useState<boolean>(false);

  function parseOrgReminder(orgs: any[]): OrgReminderInfo {
    if (!orgs || !orgs.length) return { hasReminder: false, type: "none" };

    const suspendedMemberships = orgs.filter(
      (o: any) => o.status === "expired" || o.status === "suspended" || o.is_suspended
    );
    if (suspendedMemberships.length > 0) {
      const firstOrg = suspendedMemberships[0];
      const missingLabels = (firstOrg.missing_fields || []).map((f: any) => f.label || f.field).join("、");
      return {
        hasReminder: true,
        type: "suspended",
        firstOrg,
        orgCount: suspendedMemberships.length,
        orgNames: suspendedMemberships.map((o: any) => o.name).join("、"),
        missingLabels,
        missingFields: firstOrg.missing_fields || [],
        remainingDays: 0,
        title: `⚠️ 【${firstOrg.name}】组织访问权限已被暂停`,
        confirmText: "立即前往补齐",
        cancelText: "稍后再说",
      };
    }

    const incompleteMemberships = orgs.filter(
      (o: any) => (o.missing_fields && o.missing_fields.length > 0) || o.status === "temporary"
    );
    if (incompleteMemberships.length > 0) {
      const firstOrg = incompleteMemberships[0];
      const missingLabels = (firstOrg.missing_fields || []).map((f: any) => f.label || f.field).join("、");
      const orgCount = incompleteMemberships.length;
      const orgNames = incompleteMemberships.map((o: any) => o.name).join("、");
      const remainingDays =
        firstOrg.days_remaining !== undefined && firstOrg.days_remaining !== null
          ? firstOrg.days_remaining
          : 14;

      return {
        hasReminder: true,
        type: "temporary",
        firstOrg,
        orgCount,
        orgNames,
        missingLabels,
        missingFields: firstOrg.missing_fields || [],
        remainingDays,
        title: `📋 【${firstOrg.name}】入队必填档案待完善`,
        confirmText: "立即前往补齐",
        cancelText: "稍后再说",
      };
    }

    return { hasReminder: false, type: "none" };
  }

  function handleGoToRequiredFields() {
    if (typeof window !== "undefined") {
      sessionStorage.setItem("auto_scroll_to_required_fields", "1");
    }
    router.push("/dashboard/profile?scroll_to_required=1");
  }

  function handlePreviewReminderModal() {
    const sampleReminder: OrgReminderInfo = {
      hasReminder: true,
      type: "temporary",
      firstOrg: userOrgs?.[0] || { name: "复旦戈" },
      missingLabels: "身份证号、紧急联系人及电话、班级/届别",
      missingFields: [
        { field: "class_name", label: "班级/届别" },
        { field: "id_card", label: "证件号码(身份证/护照)" },
        { field: "emergency_contact", label: "紧急联系人及电话" },
      ],
      remainingDays: 13,
      confirmText: "立即前往补齐",
      cancelText: "稍后再说",
    };
    setOrgReminder(sampleReminder);
    setShowOrgReminderModal(true);
  }

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadDashboardData(u.id);
      } else {
        router.push("/login");
      }
    });
  }, [router]);

  async function loadClubHubData(club: any, uid: string) {
    if (!club?.id || !uid) return;
    setActiveClub(club);
    try {
      const [dashRes, lbRes, feedRes, mRes] = await Promise.all([
        apiClient.get(`/api/team/${club.id}/dashboard?user_id=${uid}`).catch(() => null),
        apiClient.get(`/api/team/${club.id}/leaderboard?user_id=${uid}`).catch(() => null),
        apiClient.get(`/api/team/${club.id}/feed?uid=${uid}&user_id=${uid}`).catch(() => null),
        apiClient.get(`/api/team/mentorship/overview?user_id=${uid}`).catch(() => null),
      ]);
      if (dashRes?.data?.metrics) setClubMetrics(dashRes.data.metrics);
      if (lbRes?.data?.leaderboard) setClubLeaderboard(lbRes.data.leaderboard);
      if (feedRes?.data?.feed) setClubFeed(feedRes.data.feed);
      if (mRes?.data) setMentorshipOverview(mRes.data);
    } catch (err) {
      console.warn("Load club hub error:", err);
    }
  }

  async function loadDashboardData(uid: string) {
    setLoading(true);
    try {
      const [dashRes, sciRes, planRes, coachRes, racesRes, clubsRes] = await Promise.all([
        apiClient.get(`/api/miniapp/dashboard/${uid}`),
        apiClient.get(`/api/science/metrics/${uid}`),
        apiClient.get(`/api/coach/plan/user/${uid}`).catch(() => null),
        apiClient.get(`/api/coach/latest/${uid}`).catch(() => null),
        apiClient.get(`/api/profile/${uid}/races`).catch(() => null),
        apiClient.get(`/api/team/my-clubs/${uid}`).catch(() => null),
      ]);
      setDashboardData(dashRes.data);
      setScienceData(sciRes.data);

      if (planRes?.data?.active_plan) {
        const ap = planRes.data.active_plan;
        setActivePlan(ap);
        setPlanWeekIdx(ap.current_week_index || computeCurrentWeekIndex(ap));
      }
      if (coachRes?.data?.summary) {
        setCoachReport(coachRes.data);
      }
      if (racesRes?.data?.races) {
        setUserRaces(racesRes.data.races);
      }
      if (clubsRes?.data?.clubs && clubsRes.data.clubs.length > 0) {
        const clubs = clubsRes.data.clubs;
        setMyClubs(clubs);
        const savedClubId = typeof window !== "undefined" ? localStorage.getItem("rgm_active_club_id") : null;
        const chosen = clubs.find((c: any) => c.id === savedClubId) || clubs[0];
        loadClubHubData(chosen, uid);
      }

      const acts = dashRes.data?.current_month_activities || dashRes.data?.recent_activities || [];
      setMonthActivities(acts);
      if (dashRes.data?.current_month_info) {
        setSelectedYear(dashRes.data.current_month_info.year);
        setSelectedMonth(dashRes.data.current_month_info.month);
      }

      try {
        const orgRes = await apiClient.get(`/api/org/my-orgs/${uid}`);
        const orgs = orgRes.data?.organizations || [];
        setUserOrgs(orgs);
        const rem = parseOrgReminder(orgs);
        if (rem.hasReminder) {
          setOrgReminder(rem);
          const dismissed = typeof window !== "undefined" ? sessionStorage.getItem(`org_reminder_dismissed_${uid}`) : null;
          if (!dismissed) {
            setShowOrgReminderModal(true);
          }
        } else {
          setOrgReminder(null);
          setShowOrgReminderModal(false);
        }
      } catch (orgErr) {
        console.warn("Check org reminder error:", orgErr);
      }
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    } finally {
      setLoading(false);
    }
  }

  async function handleSwitchMonth(offset: number) {
    let newMonth = selectedMonth + offset;
    let newYear = selectedYear;
    if (newMonth > 12) {
      newMonth = 1;
      newYear += 1;
    } else if (newMonth < 1) {
      newMonth = 12;
      newYear -= 1;
    }

    const now = new Date();
    const currentYear = dashboardData?.current_month_info?.year || now.getFullYear();
    const currentMonth = dashboardData?.current_month_info?.month || (now.getMonth() + 1);
    if (newYear > currentYear || (newYear === currentYear && newMonth > currentMonth)) {
      return;
    }

    setSelectedYear(newYear);
    setSelectedMonth(newMonth);
    setShowAllMonthActs(false);
    if (!user?.id) return;
    setLoadingMonthActs(true);
    try {
      const res = await apiClient.get(`/api/miniapp/activities/month/${user.id}?year=${newYear}&month=${newMonth}`);
      setMonthActivities(res.data?.activities || []);
    } catch (e) {
      console.error("Fetch month activities error:", e);
    } finally {
      setLoadingMonthActs(false);
    }
  }

  async function handleResetToCurrentMonth() {
    const currentYear = dashboardData?.current_month_info?.year || new Date().getFullYear();
    const currentMonth = dashboardData?.current_month_info?.month || (new Date().getMonth() + 1);
    if (selectedYear === currentYear && selectedMonth === currentMonth) return;
    setSelectedYear(currentYear);
    setSelectedMonth(currentMonth);
    setMonthActivities(dashboardData?.current_month_activities || dashboardData?.recent_activities || []);
  }

  async function handleSync() {
    if (!user) return;
    const hasGarmin = Boolean(dashboardData?.user?.garmin_connected);
    const hasCoros = Boolean(dashboardData?.user?.coros_connected);
    if (!hasGarmin && !hasCoros) {
      setModalBrand("garmin");
      setGarminModalOpen(true);
      return;
    }

    setSyncing(true);
    try {
      const res = await apiClient.post("/api/sync/trigger", { uid: user.id });
      if (res.data?.success === false) {
        alert("同步提示: " + (res.data?.error || "设备连接中，请稍后再试"));
      }
      await loadDashboardData(user.id);
    } catch (e) {
      console.error("Sync error:", e);
    } finally {
      setSyncing(false);
    }
  }

  const [togglingWorkout, setTogglingWorkout] = useState(false);

  const WEB_FEELING_TAGS = [
    "🤩 状态极佳",
    "😊 轻松舒适",
    "💪 正常发挥",
    "😮‍💨 略感吃力",
    "🥵 疲惫掉速",
    "🦵 肌肉酸紧",
  ];
  const [checkinLogModalOpen, setCheckinLogModalOpen] = useState(false);
  const [savingCheckinLog, setSavingCheckinLog] = useState(false);
  const [checkinFeelingTag, setCheckinFeelingTag] = useState("");
  const [checkinRpe, setCheckinRpe] = useState<number | null>(null);
  const [checkinNotes, setCheckinNotes] = useState("");
  const [checkinWorkoutPhotos, setCheckinWorkoutPhotos] = useState<string[]>([]);
  const [checkinNewPhotosBase64, setCheckinNewPhotosBase64] = useState<string[]>([]);

  function openCheckinLogModal(twData?: any) {
    const tw = twData || todayWorkout;
    if (!tw) return;
    setCheckinFeelingTag(tw.feeling_tag || "");
    setCheckinRpe(tw.rpe != null ? Number(tw.rpe) : null);
    setCheckinNotes(tw.athlete_notes || "");
    setCheckinWorkoutPhotos(
      Array.isArray(tw.workout_photos)
        ? [...tw.workout_photos]
        : tw.photo_url
        ? [tw.photo_url]
        : []
    );
    setCheckinNewPhotosBase64([]);
    setCheckinLogModalOpen(true);
  }

  function handleWebPhotoUploadChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const currentTotal = checkinWorkoutPhotos.length + checkinNewPhotosBase64.length;
    const remain = Math.max(0, 3 - currentTotal);
    files.slice(0, remain).forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          const maxDim = 1280;
          let w = img.width;
          let h = img.height;
          if (w > maxDim || h > maxDim) {
            if (w > h) {
              h = Math.round((h * maxDim) / w);
              w = maxDim;
            } else {
              w = Math.round((w * maxDim) / h);
              h = maxDim;
            }
          }
          const canvas = document.createElement("canvas");
          canvas.width = w;
          canvas.height = h;
          const ctx = canvas.getContext("2d");
          if (ctx) {
            ctx.drawImage(img, 0, 0, w, h);
            const dataUrl = canvas.toDataURL("image/jpeg", 0.82);
            setCheckinNewPhotosBase64((prev) => [...prev, dataUrl]);
          }
        };
        if (typeof reader.result === "string") {
          img.src = reader.result;
        }
      };
      reader.readAsDataURL(file);
    });
    e.target.value = "";
  }

  async function handleSaveWebCheckinLog() {
    const tw = todayWorkout;
    if (!tw || !tw.plan_id || !user?.id) return;
    setSavingCheckinLog(true);
    try {
      const res = await apiClient.patch(`/api/coach/plan/${tw.plan_id}/workout`, {
        week_index: tw.week_index,
        day_index: tw.day_index,
        completed: true,
        feeling_tag: checkinFeelingTag,
        rpe: checkinRpe,
        athlete_notes: checkinNotes,
        workout_photos: checkinWorkoutPhotos,
        new_photos_base64: checkinNewPhotosBase64,
        operator_uid: user.id,
      });
      if (res.data?.success) {
        setCheckinLogModalOpen(false);
        await loadDashboardData(user.id);
      }
    } catch (err) {
      console.error("Failed to save checkin log:", err);
      alert("保存感受与照片失败，请重试");
    } finally {
      setSavingCheckinLog(false);
    }
  }

  async function handleToggleTodayWorkout() {
    const tw = todayWorkout;
    if (!tw || !tw.plan_id || !user?.id) return;
    setTogglingWorkout(true);
    try {
      const newCompleted = !tw.completed;
      const res = await apiClient.patch(`/api/coach/plan/${tw.plan_id}/workout`, {
        week_index: tw.week_index,
        day_index: tw.day_index,
        completed: newCompleted,
        operator_uid: user.id,
      });
      if (res.data?.success) {
        await loadDashboardData(user.id);
        if (newCompleted) {
          openCheckinLogModal({ ...tw, completed: true });
        }
      }
    } catch (err) {
      console.error("Failed to toggle today workout:", err);
    } finally {
      setTogglingWorkout(false);
    }
  }

  async function handleTogglePlanDayWorkout(weekIndex: number, dayIndex: number, currentCompleted: boolean) {
    if (!activePlan?.id || !user?.id) return;
    const key = `${weekIndex}-${dayIndex}`;
    setTogglingDayKey(key);
    try {
      const res = await apiClient.patch(`/api/coach/plan/${activePlan.id}/workout`, {
        week_index: weekIndex,
        day_index: dayIndex,
        completed: !currentCompleted,
        operator_uid: user.id,
      });
      if (res.data?.success && res.data?.plan) {
        setActivePlan(res.data.plan);
        const dashRes = await apiClient.get(`/api/miniapp/dashboard/${user.id}`).catch(() => null);
        if (dashRes?.data) setDashboardData(dashRes.data);
      }
    } catch (err) {
      console.error("Failed to toggle plan day workout:", err);
    } finally {
      setTogglingDayKey(null);
    }
  }

  async function handleToggleFeedLike(activityId: string) {
    if (!user?.id) return;
    try {
      const res = await apiClient.post(`/api/team/activities/${activityId}/like`, {
        user_id: user.id,
      });
      setClubFeed((prev) =>
        prev.map((item) =>
          item.id === activityId
            ? {
                ...item,
                has_liked: res.data.liked,
                likes_count: res.data.likes_count,
                likers: Array.isArray(res.data.likers) ? res.data.likers : item.likers || [],
              }
            : item
        )
      );
    } catch (e) {
      console.error("Feed like error:", e);
    }
  }

  async function handleUpdateExcludeMode(actId: string, mode: "normal" | "ignore_vdot" | "excluded") {
    if (!user?.id) return;
    setUpdatingExcludeId(actId);
    try {
      const res = await apiClient.post(`/api/science/activities/${actId}/exclude-mode`, {
        user_id: user.id,
        exclude_mode: mode,
      });
      if (res.data?.success) {
        setMonthActivities((prev) =>
          prev.map((a) => (a.id === actId ? { ...a, exclude_mode: mode } : a))
        );
        await loadDashboardData(user.id);
      }
    } catch (err) {
      console.error("Failed to update exclude_mode:", err);
    } finally {
      setUpdatingExcludeId(null);
    }
  }

  const ctlHistory = scienceData?.ctl_atl_tsb_history || [];
  const monthlyTrend = dashboardData?.monthly_trend?.trend || [];
  const yearlyStats = dashboardData?.yearly_stats || {};
  const todayHealth = dashboardData?.today_health || {};
  const weeklyProgress = dashboardData?.weekly_progress || {};
  const todayWorkout = dashboardData?.today_workout || weeklyProgress?.today_workout;
  const effectiveVdot = scienceData?.canova_matrix?.effective_vdot ?? scienceData?.vdot ?? "—";
  const statusLabel = dashboardData?.fitness_form?.status_label || scienceData?.current_tsb_badge?.label || "训练中";
  const statusColor = dashboardData?.fitness_form?.status_color || scienceData?.current_tsb_badge?.color || "#38bdf8";

  // Active week in training plan
  const planWeeks = activePlan?.schedule_data?.weeks || [];
  const currentActiveWeek =
    planWeeks.find((w: any) => w.week_index === planWeekIdx) || planWeeks[0] || null;
  const defaultPlanWeekIdx = activePlan ? computeCurrentWeekIndex(activePlan) : 1;

  // Upcoming race countdown
  const upcomingRace = userRaces.find(
    (r: any) => r.status !== "completed" && !r.is_completed && !r.is_past
  );
  const myClubRankItem = clubLeaderboard.find((r: any) => r.user_id === user?.id);

  const currentYearNow = dashboardData?.current_month_info?.year || new Date().getFullYear();
  const currentMonthNow = dashboardData?.current_month_info?.month || (new Date().getMonth() + 1);
  const isViewingCurrentMonth = selectedYear === currentYearNow && selectedMonth === currentMonthNow;
  const displayedMonthActivities = showAllMonthActs ? monthActivities : monthActivities.slice(0, 6);

  const totalMonthKm = Math.round(monthActivities.reduce((acc, a) => acc + (Number(a.distance_km) || 0), 0) * 10) / 10;
  const totalMonthTrimp = Math.round(monthActivities.reduce((acc, a) => acc + (Number(a.trimp) || 0), 0));
  const runsWithPace = monthActivities.filter((a) => (a.moving_time_seconds || 0) > 0 && (a.distance_km || 0) > 0);
  let avgMonthPaceStr = "—";
  if (runsWithPace.length > 0) {
    const totalSec = runsWithPace.reduce((acc, a) => acc + (a.moving_time_seconds || 0), 0);
    const totalKm = runsWithPace.reduce((acc, a) => acc + (a.distance_km || 0), 0);
    if (totalKm > 0) {
      const secPerKm = Math.round(totalSec / totalKm);
      const pm = Math.floor(secPerKm / 60);
      const ps = secPerKm % 60;
      avgMonthPaceStr = `${pm}:${ps < 10 ? "0" : ""}${ps} /km`;
    }
  }

  function formatActivityTime(timeStr?: string) {
    if (!timeStr) return "—";
    try {
      const clean = timeStr.replace(" ", "T");
      const d = new Date(clean);
      if (isNaN(d.getTime())) return timeStr.slice(0, 16).replace("T", " ");
      const days = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
      const m = d.getMonth() + 1;
      const date = d.getDate();
      const hours = String(d.getHours()).padStart(2, "0");
      const mins = String(d.getMinutes()).padStart(2, "0");
      const dayName = days[d.getDay()];
      return `${m}月${date}日 ${hours}:${mins} ${dayName}`;
    } catch {
      return timeStr.slice(0, 16).replace("T", " ");
    }
  }

  function formatDurationSeconds(seconds?: number) {
    if (!seconds || seconds <= 0) return "—";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}h ${String(m).padStart(2, "0")}m`;
    }
    return `${m}m ${String(s).padStart(2, "0")}s`;
  }

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-7 py-7 space-y-6">
        {/* ── 顶部精简全息指挥栏（v2.1 双层防挤压结构：第1层独立展示问候语与长名字，第2层展示状态徽章，彻底杜绝末字符裁切与长名碰撞） ── */}
        <section className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-[#121215] border border-white/[0.08] rounded-[28px] px-6 py-5">
          <div className="min-w-0 flex-1 space-y-2.5">
            <h1 className="text-xl sm:text-[26px] font-black leading-[1.35] tracking-normal break-words pr-3 max-w-full text-white">
              {dashboardData?.user?.display_name ? `你好，${dashboardData.user.display_name}` : "跑步控制台"}
            </h1>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border shrink-0 bg-emerald-500/15 border-emerald-500/30 text-emerald-300">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                {statusLabel} · TSB{" "}
                {(scienceData?.current_tsb ?? dashboardData?.fitness_form?.tsb ?? 0) > 0
                  ? `+${scienceData?.current_tsb ?? dashboardData?.fitness_form?.tsb ?? 0}`
                  : scienceData?.current_tsb ?? dashboardData?.fitness_form?.tsb ?? 0}
              </span>
              {upcomingRace && (
                <Link
                  href="/dashboard/coach?tab=report"
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-purple-500/15 border border-purple-500/30 text-purple-300 hover:bg-purple-500/25 transition"
                >
                  🏁 {upcomingRace.name}
                  {upcomingRace.days_until != null && <span>· {upcomingRace.days_until}天后</span>}
                  {upcomingRace.target_time && <span className="text-purple-200/80">(目标 {upcomingRace.target_time})</span>}
                </Link>
              )}
              {activeClub && (
                <Link
                  href="/dashboard/team"
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/15 border border-amber-500/30 text-amber-300 hover:bg-amber-500/25 transition"
                >
                  🏆 {activeClub.name}
                  {myClubRankItem && <span>· #{myClubRankItem.rank}</span>}
                </Link>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap shrink-0">
            {dashboardData?.user?.garmin_connected && (
              <span className="px-3 py-1.5 rounded-full text-xs font-bold bg-emerald-500/15 border border-emerald-500/25 text-emerald-300">
                ⌚ Garmin 已同步
              </span>
            )}
            {dashboardData?.user?.coros_connected && (
              <span className="px-3 py-1.5 rounded-full text-xs font-bold bg-indigo-500/15 border border-indigo-500/25 text-indigo-300">
                ⌚ COROS 已同步
              </span>
            )}
            {userOrgs?.some((o) => o.role === "owner" || o.role === "admin") && (
              <button
                onClick={handlePreviewReminderModal}
                title="管理员测试：预览未完善信息队员打开看板时所见的弹窗"
                className="p-2 rounded-xl text-xs font-semibold bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 text-amber-300 transition"
              >
                <AlertTriangle className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setPersonalReportModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-2xl text-xs sm:text-[13px] font-bold bg-[#18181c] border border-white/10 text-white hover:bg-white/10 transition cursor-pointer shadow-sm"
            >
              <span>📊 个人周报/月报</span>
            </button>
            {dashboardData?.user?.garmin_connected || dashboardData?.user?.coros_connected ? (
              <button
                onClick={handleSync}
                disabled={syncing}
                className="flex items-center gap-2 px-4 py-2 rounded-2xl text-xs sm:text-[13px] font-bold bg-gradient-to-br from-[#FC4C02] to-[#EA580C] text-white hover:opacity-95 transition active:scale-95 shadow-lg shadow-[#FC4C02]/30"
              >
                <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
                {syncing ? "正在同步..." : "同步手表数据"}
              </button>
            ) : (
              <button
                onClick={() => {
                  setModalBrand("garmin");
                  setGarminModalOpen(true);
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-2xl text-xs sm:text-[13px] font-bold bg-gradient-to-br from-[#FC4C02] to-[#EA580C] text-white hover:opacity-95 transition active:scale-95 shadow-lg shadow-[#FC4C02]/30"
              >
                <Zap className="w-4 h-4" />
                绑定运动手表 ›
              </button>
            )}
          </div>
        </section>

        {/* ── 大组织必填资料待完善提醒 (若有) ── */}
        {orgReminder?.hasReminder && (
          <div
            onClick={handleGoToRequiredFields}
            className={`px-4 py-3 rounded-2xl border cursor-pointer transition flex items-center justify-between gap-3 ${
              orgReminder.type === "suspended"
                ? "bg-rose-500/10 border-rose-500/40 hover:border-rose-500/60"
                : "bg-amber-500/10 border-amber-500/40 hover:border-amber-500/60"
            }`}
          >
            <div className="flex items-center gap-3 min-w-0">
              {orgReminder.type === "suspended" ? (
                <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
              )}
              <div className="min-w-0 text-xs">
                <span className={`font-bold ${orgReminder.type === "suspended" ? "text-rose-300" : "text-amber-300"}`}>
                  {orgReminder.type === "suspended"
                    ? `【${orgReminder.firstOrg?.name}】访问已暂停`
                    : `【${orgReminder.firstOrg?.name}】入队档案待完善`}
                </span>
                {orgReminder.remainingDays !== undefined && orgReminder.remainingDays !== null && (
                  <span className="ml-2 text-amber-300/80">剩余 {orgReminder.remainingDays} 天</span>
                )}
                {orgReminder.missingLabels && (
                  <span className="ml-2 text-zinc-400 hidden sm:inline">缺：{orgReminder.missingLabels}</span>
                )}
              </div>
            </div>
            <span className="flex items-center gap-1 text-xs font-bold text-amber-400 flex-shrink-0">
              去补齐 <ArrowRight className="w-3.5 h-3.5" />
            </span>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════════
            第一行核心区：左栏 (7 cols)「卡片 A：今日核心处方 Hero Card + 卡片 B：本周 7 日微周期胶囊阵列」
                          右栏 (5 cols)「卡片 C：跑力罗盘与生理恢复 Bento 卡 + 卡片 D：周期跑量目标进度卡」
           ══════════════════════════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* ── LEFT COLUMN (7 cols): 训练与周期课表中心 ── */}
          <div className="lg:col-span-7 space-y-6">
            {/* 卡片 A：今日训练处方 Hero Card（视觉重心聚焦，收拢教练批注与诊断） */}
            <div className="rgm-hero-prescription border rounded-[28px] p-6 sm:p-7 space-y-5">
              {todayWorkout ? (
                <>
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-2.5 flex-wrap text-xs">
                      <span className="px-3 py-1 rounded-full font-bold bg-[#FC4C02]/15 text-[#FC4C02]">
                        📅 今日核心处方
                      </span>
                      <span className="font-semibold text-zinc-300">
                        {todayWorkout.date} {todayWorkout.day_of_week} ·{" "}
                        {currentActiveWeek?.phase ||
                          (todayWorkout.workout_type === "race"
                            ? "🏁 比赛日"
                            : todayWorkout.workout_type === "rest"
                            ? "☕ 休息恢复日"
                            : "科学专项期")}
                      </span>
                      {todayWorkout.completed && todayWorkout.actual_distance_km && (
                        <span className="px-2.5 py-0.5 rounded-full font-bold bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
                          ✅ 实跑 {todayWorkout.actual_distance_km}km
                        </span>
                      )}
                    </div>
                    <Link
                      href="/dashboard/coach"
                      className="text-xs font-bold text-purple-300 hover:text-purple-200 flex-shrink-0"
                    >
                      调整课表 ›
                    </Link>
                  </div>

                  <div className="flex items-end justify-between gap-5">
                    <div className="min-w-0 flex-1">
                      <h3 className="text-xl sm:text-2xl font-black text-white leading-tight break-words">
                        {todayWorkout.title}
                      </h3>
                      {todayWorkout.description && (
                        <p className="text-xs sm:text-[13.5px] text-zinc-300 leading-relaxed mt-2 max-w-xl">
                          {todayWorkout.description}
                        </p>
                      )}
                    </div>
                    {todayWorkout.workout_type !== "rest" && (
                      <div className="text-right flex-shrink-0">
                        <div className="text-4xl sm:text-5xl font-black tabular-nums text-[#FC4C02] leading-none">
                          {todayWorkout.distance_km || 0}
                        </div>
                        <div className="text-[11px] font-extrabold text-zinc-400 mt-1.5 tracking-wider">TARGET KM</div>
                      </div>
                    )}
                  </div>

                  {/* 双栏关键执行参数 */}
                  {todayWorkout.workout_type !== "rest" && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div className="bg-[#18181c] border border-white/[0.06] rounded-2xl px-4 py-3 flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-zinc-400">⏱️ 目标配速区间</span>
                        <span className="text-xs sm:text-sm font-black tabular-nums text-purple-300">
                          {todayWorkout.target_pace && todayWorkout.target_pace !== "—"
                            ? todayWorkout.target_pace
                            : "按体感有氧巡航"}
                        </span>
                      </div>
                      <div className="bg-[#18181c] border border-white/[0.06] rounded-2xl px-4 py-3 flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-zinc-400">❤️ 目标心率控制</span>
                        <span className="text-xs sm:text-sm font-black tabular-nums text-emerald-300">
                          {todayWorkout.target_hr_zone && todayWorkout.target_hr_zone !== "—"
                            ? todayWorkout.target_hr_zone
                            : "Zone 2-3 稳态区间"}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* 融合式 Canova 教练处方与体能诊断条（替代原本两块杂乱色块） */}
                  {(todayWorkout.coach_notes || coachReport) && (
                    <div className="px-4 py-3.5 rounded-2xl bg-[#18181c] border border-white/[0.06] border-l-4 border-l-purple-500 space-y-1.5">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2 text-xs">
                          <span className="font-extrabold text-purple-300">🧬 Canova 教练处方与体能诊断</span>
                          {coachReport?.periodization_phase && (
                            <span className="text-[11px] text-zinc-400">· {coachReport.periodization_phase}</span>
                          )}
                        </div>
                        <Link
                          href="/dashboard/coach?tab=report"
                          className="text-[11px] font-bold text-zinc-400 hover:text-purple-300 transition"
                        >
                          CTL {scienceData?.current_ctl ?? 0} · 完整专项诊断 ›
                        </Link>
                      </div>
                      <div className="text-xs sm:text-[12.5px] text-zinc-300 leading-relaxed space-y-1">
                        {todayWorkout.coach_notes && <div>{todayWorkout.coach_notes}</div>}
                        {coachReport?.summary && (
                          <div className={todayWorkout.coach_notes ? "text-zinc-400 pt-0.5" : ""}>
                            {coachReport.summary}
                          </div>
                        )}
                      </div>
                      {coachReport?.tsb_metrics?.risk_warning && (
                        <div className="text-xs text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-xl px-3 py-1.5 mt-1">
                          ⚠️ {coachReport.tsb_metrics.risk_warning}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 当日打卡后：展示/添加训练感受、备注与打卡照片（与小程序实时同步） */}
                  {todayWorkout.completed && (
                    <div className="rounded-2xl bg-emerald-950/20 border border-emerald-500/30 p-3.5 space-y-2.5">
                      {todayWorkout.feeling_tag ||
                      todayWorkout.rpe ||
                      todayWorkout.athlete_notes ||
                      (todayWorkout.workout_photos && todayWorkout.workout_photos.length > 0) ? (
                        <>
                          <div className="flex items-center justify-between gap-2 flex-wrap">
                            <div className="flex items-center gap-2 flex-wrap">
                              {todayWorkout.feeling_tag && (
                                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 border border-emerald-500/40 text-emerald-300">
                                  {todayWorkout.feeling_tag}
                                </span>
                              )}
                              {todayWorkout.rpe && (
                                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/20 border border-amber-500/40 text-amber-300">
                                  RPE {todayWorkout.rpe}/10
                                </span>
                              )}
                              {!todayWorkout.feeling_tag && !todayWorkout.rpe && (
                                <span className="text-xs font-bold text-emerald-300">💬 今日打卡感受与备注</span>
                              )}
                            </div>
                            <button
                              type="button"
                              onClick={() => openCheckinLogModal(todayWorkout)}
                              className="px-2.5 py-1 rounded-xl text-xs font-bold bg-white/10 hover:bg-white/15 text-white border border-white/15 transition cursor-pointer"
                            >
                              ✏️ 编辑感受/备注/照片
                            </button>
                          </div>
                          {todayWorkout.athlete_notes && (
                            <div className="text-xs text-zinc-200 leading-relaxed">{todayWorkout.athlete_notes}</div>
                          )}
                          {todayWorkout.workout_photos && todayWorkout.workout_photos.length > 0 && (
                            <div className="flex items-center gap-2.5 flex-wrap pt-1">
                              {todayWorkout.workout_photos.map((pUrl: string, pIdx: number) => (
                                <a
                                  key={pIdx}
                                  href={pUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="block w-16 h-16 rounded-xl overflow-hidden border border-white/15 hover:border-emerald-400 transition"
                                >
                                  <img src={pUrl} alt="打卡照片" className="w-full h-full object-cover" />
                                </a>
                              ))}
                            </div>
                          )}
                        </>
                      ) : (
                        <button
                          type="button"
                          onClick={() => openCheckinLogModal(todayWorkout)}
                          className="w-full flex items-center justify-between text-left px-1 py-0.5 text-xs font-bold text-emerald-200 hover:text-white transition cursor-pointer"
                        >
                          <span>📝 今日已完成打卡，点击添加训练感受、备注与照片（小程序与网页同步）</span>
                          <span className="text-emerald-400 font-extrabold shrink-0 ml-2">+ 立即添加 ›</span>
                        </button>
                      )}
                    </div>
                  )}

                  <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between flex-wrap gap-3">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <button
                        onClick={handleToggleTodayWorkout}
                        disabled={togglingWorkout}
                        className={`flex items-center gap-1.5 px-4 py-2 rounded-2xl text-xs sm:text-[13px] font-bold transition shadow-md ${
                          todayWorkout.completed
                            ? "bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 hover:bg-emerald-500/30"
                            : "bg-gradient-to-br from-[#FC4C02] to-[#EA580C] text-white hover:opacity-95 shadow-[#FC4C02]/30"
                        }`}
                      >
                        <Check className="w-3.5 h-3.5" />
                        {todayWorkout.completed
                          ? todayWorkout.actual_distance_km
                            ? `已打卡 ${todayWorkout.actual_distance_km}km`
                            : "今日已完成"
                          : "打卡今日课表"}
                      </button>
                      {todayWorkout.completed && (
                        <button
                          type="button"
                          onClick={() => openCheckinLogModal(todayWorkout)}
                          className="px-4 py-2 rounded-2xl text-xs sm:text-[13px] font-bold bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 transition cursor-pointer"
                        >
                          📝 感受/备注/照片
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setShareCardActivityId("");
                          setShareCardModalOpen(true);
                        }}
                        className="px-4 py-2 rounded-2xl text-xs sm:text-[13px] font-bold bg-[#18181c] border border-white/10 text-white hover:bg-white/10 transition"
                      >
                        📸 生成打卡海报
                      </button>
                    </div>
                    <span className="text-xs font-semibold text-zinc-400">
                      {todayWorkout.plan_title || activePlan?.title || "科学周期训练计划"}
                      {planWeeks.length > 0 ? ` · 第 ${planWeekIdx}/${planWeeks.length} 周` : ""}
                    </span>
                  </div>
                </>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">📅</span>
                      <div>
                        <div className="text-base font-black text-white">今日暂无专属课表</div>
                        <div className="text-xs text-zinc-400 mt-0.5">按目标赛事或体能维持一键生成 Canova 周期化训练计划</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          setShareCardActivityId("");
                          setShareCardModalOpen(true);
                        }}
                        className="text-xs px-3.5 py-2 rounded-2xl bg-[#18181c] border border-white/10 text-white hover:bg-white/10 transition font-bold"
                      >
                        📸 生成打卡海报
                      </button>
                      <Link
                        href="/dashboard/coach"
                        className="text-xs px-4 py-2 rounded-2xl bg-gradient-to-br from-[#FC4C02] to-[#EA580C] text-white hover:opacity-95 transition font-bold shadow-md shadow-[#FC4C02]/30"
                      >
                        去生成周期课表 ›
                      </Link>
                    </div>
                  </div>
                  {coachReport && (
                    <div className="px-4 py-3.5 rounded-2xl bg-[#18181c] border border-white/[0.06] border-l-4 border-l-purple-500 space-y-1.5">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className="text-xs font-extrabold text-purple-300">
                          🧬 {coachReport.periodization_phase || "Canova 专项诊断"}
                        </span>
                        <Link
                          href="/dashboard/coach?tab=report"
                          className="text-[11px] font-bold text-purple-400 hover:text-purple-300"
                        >
                          完整专项诊断 ›
                        </Link>
                      </div>
                      <div className="text-xs sm:text-[12.5px] text-zinc-300 leading-relaxed">{coachReport.summary}</div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 卡片 B：本周 7 日微周期课表（高呼吸感胶囊阵列） */}
            {currentActiveWeek ? (
              <div className="bg-[#121215] border border-white/[0.08] rounded-[28px] p-6 sm:p-7 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <h2 className="text-base sm:text-lg font-black text-white">
                      🗓️ {currentActiveWeek.week_title || "本周 7 日训练微周期"}
                    </h2>
                    <span className="px-3 py-1 rounded-full text-xs font-bold bg-purple-500/15 text-purple-300">
                      计划 {currentActiveWeek.weekly_mileage_km || 0} km
                    </span>
                    <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300">
                      已跑 {currentActiveWeek.actual_mileage_km || 0} km ({currentActiveWeek.compliance_rate || 0}%)
                    </span>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {planWeekIdx !== defaultPlanWeekIdx && (
                      <button
                        onClick={() => setPlanWeekIdx(defaultPlanWeekIdx)}
                        className="px-2.5 py-1.5 rounded-xl text-xs font-bold bg-[#18181c] border border-white/10 text-zinc-300 hover:text-purple-300 transition"
                      >
                        回到本周
                      </button>
                    )}
                    <button
                      onClick={() => setPlanWeekIdx(Math.max(1, planWeekIdx - 1))}
                      disabled={planWeekIdx <= 1}
                      className="px-3 py-1.5 rounded-xl text-xs font-bold bg-[#18181c] border border-white/10 text-zinc-300 hover:text-white disabled:opacity-30 transition"
                    >
                      ‹ 上周
                    </button>
                    <span className="text-xs font-bold text-zinc-400 px-1">
                      W{planWeekIdx}/{planWeeks.length}
                    </span>
                    <button
                      onClick={() => setPlanWeekIdx(Math.min(planWeeks.length, planWeekIdx + 1))}
                      disabled={planWeekIdx >= planWeeks.length}
                      className="px-3 py-1.5 rounded-xl text-xs font-bold bg-[#18181c] border border-white/10 text-zinc-300 hover:text-white disabled:opacity-30 transition"
                    >
                      下周 ›
                    </button>
                  </div>
                </div>

                {/* 7-Day Capsules Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-7 gap-2.5">
                  {(currentActiveWeek.days || []).map((day: any, dIdx: number) => {
                    const isRest = day.workout_type === "rest" || Number(day.distance_km || 0) <= 0;
                    const isRace = day.workout_type === "race";
                    const isToday = Boolean(todayWorkout?.date && day.date === todayWorkout.date);
                    const isDone = Boolean(day.completed) && !isToday;
                    const dayKey = `${currentActiveWeek.week_index}-${dIdx}`;
                    const shortTitle = (day.title || "").replace(/^Canova\s*/i, "");
                    return (
                      <div
                        key={dIdx}
                        className={`rgm-day-capsule rounded-[20px] p-3 min-h-[128px] flex flex-col items-center justify-between text-center transition ${
                          isToday
                            ? "is-today bg-[#161822] border-2 border-[#FC4C02] shadow-[0_8px_22px_-4px_rgba(252,76,2,0.2)] -translate-y-0.5"
                            : isDone
                            ? "is-done bg-emerald-950/20 border border-emerald-500/30"
                            : isRace
                            ? "bg-rose-950/20 border border-rose-500/35"
                            : "bg-[#18181c] border border-white/[0.06]"
                        }`}
                      >
                        <div className="w-full flex items-center justify-between text-[11px]">
                          <span className={`font-extrabold ${isToday ? "text-[#FC4C02]" : "text-zinc-400"}`}>
                            {day.day_of_week}
                          </span>
                          <span className="text-[10px] text-zinc-500 font-mono">
                            {day.date ? day.date.slice(5) : ""}
                          </span>
                        </div>

                        <div className="my-2 w-full">
                          {!isRest ? (
                            <div
                              className={`text-xl font-black tabular-nums leading-none ${
                                isToday ? "text-[#FC4C02]" : "text-white"
                              }`}
                            >
                              {day.distance_km}
                              <span className="text-[11px] font-semibold text-zinc-400 ml-0.5">k</span>
                            </div>
                          ) : (
                            <div className="text-sm font-extrabold text-zinc-500">☕ 休</div>
                          )}
                          <div
                            className="text-[11px] font-semibold text-zinc-300 mt-1.5 truncate px-0.5"
                            title={day.title}
                          >
                            {shortTitle}
                          </div>
                          {!isRest && day.target_pace && day.target_pace !== "—" && (
                            <div className="text-[10px] text-purple-300/90 truncate mt-0.5">{day.target_pace}</div>
                          )}
                        </div>

                        <button
                          onClick={() =>
                            handleTogglePlanDayWorkout(currentActiveWeek.week_index, dIdx, Boolean(day.completed))
                          }
                          disabled={togglingDayKey === dayKey}
                          className="w-full pt-1.5 border-t border-white/[0.06] text-[10px] font-bold flex items-center justify-center gap-1 hover:opacity-80 transition cursor-pointer"
                        >
                          {day.completed ? (
                            <span className="text-emerald-400">
                              ✓ {day.actual_distance_km ? `${day.actual_distance_km}k` : "已完成"}
                            </span>
                          ) : isToday ? (
                            <span className="text-[#FC4C02]">● 今日主课</span>
                          ) : (
                            <span className="text-zinc-500 hover:text-zinc-300">待执行</span>
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>

          {/* ── RIGHT COLUMN (5 cols): 卡片 C (跑力罗盘与生理恢复) + 卡片 D (周期跑量目标进度卡) ── */}
          <div className="lg:col-span-5 space-y-6">
            {/* 卡片 C：⚡ 跑力罗盘与生理恢复 Bento 卡 */}
            <div className="bg-[#121215] border border-white/[0.08] rounded-[28px] p-6 sm:p-7 space-y-4">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-base sm:text-lg font-black text-white">⚡ 跑力罗盘与生理恢复</h2>
                  {scienceData?.canova_matrix?.runner_type_label && (
                    <span className="px-2.5 py-0.5 rounded-full bg-sky-500/15 border border-sky-500/25 text-sky-300 text-xs font-bold">
                      {scienceData.canova_matrix.runner_type_label}
                    </span>
                  )}
                </div>
                <Link href="/dashboard/analysis" className="text-xs font-bold text-sky-400 hover:text-sky-300 shrink-0">
                  五维分析 ›
                </Link>
              </div>

              {/* VDOT 主视觉 + 四项预测一体卡 */}
              <div className="bg-[#18181c] border border-[#FC4C02]/25 rounded-[20px] p-4 space-y-3.5">
                <div className="flex items-center justify-between gap-3 pb-3.5 border-b border-white/[0.06]">
                  <div>
                    <div className="text-[11px] font-extrabold text-[#FC4C02] tracking-wider">
                      EFFECTIVE VDOT · 有效跑力
                    </div>
                    <div className="text-xs text-zinc-400 mt-0.5">
                      {scienceData?.canova_matrix?.endurance_retention_ratio
                        ? `耐力保持系数 ${scienceData.canova_matrix.endurance_retention_ratio} · `
                        : ""}
                      含全马衰减修正
                    </div>
                  </div>
                  <div className="text-3xl sm:text-4xl font-black tabular-nums text-white leading-none">
                    {effectiveVdot}
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2 text-center tabular-nums">
                  <div>
                    <div className="text-[10px] font-bold text-zinc-500">5K 预测</div>
                    <div className="text-xs sm:text-sm font-black text-white mt-1">
                      {scienceData?.race_predictions?.five_k || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-zinc-500">10K 预测</div>
                    <div className="text-xs sm:text-sm font-black text-white mt-1">
                      {scienceData?.race_predictions?.ten_k || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-zinc-500">半马预测</div>
                    <div className="text-xs sm:text-sm font-black text-[#FC4C02] mt-1">
                      {scienceData?.race_predictions?.half_marathon || "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-zinc-500">全马预测</div>
                    <div className="text-xs sm:text-sm font-black text-rose-400 mt-1">
                      {scienceData?.race_predictions?.marathon || "—"}
                    </div>
                  </div>
                </div>
              </div>

              {/* 3 列晨起生理指标 */}
              <div className="grid grid-cols-3 gap-2.5 tabular-nums">
                <div className="bg-[#18181c] border border-white/[0.06] rounded-[20px] p-3">
                  <div className="text-[11px] font-bold text-zinc-400">🔋 身体电量</div>
                  <div className="text-lg sm:text-xl font-black text-amber-400 mt-1">
                    {todayHealth?.body_battery_max != null ? `${todayHealth.body_battery_max}%` : "—"}
                  </div>
                  <div className="text-[10px] text-zinc-500 mt-0.5">
                    {todayHealth?.sleep_score != null ? `睡眠 ${todayHealth.sleep_score} 分` : "晨起电量"}
                  </div>
                </div>
                <div className="bg-[#18181c] border border-white/[0.06] rounded-[20px] p-3">
                  <div className="text-[11px] font-bold text-zinc-400">💓 夜间 HRV</div>
                  <div className="text-lg sm:text-xl font-black text-sky-400 mt-1">
                    {todayHealth?.hrv_ms != null ? todayHealth.hrv_ms : "—"}
                    {todayHealth?.hrv_ms != null && <span className="text-[11px] font-semibold ml-0.5">ms</span>}
                  </div>
                  <div className="text-[10px] text-zinc-500 mt-0.5">
                    {todayHealth?.hrv_weekly_avg ? `周均 ${todayHealth.hrv_weekly_avg} ms` : "心率变异性"}
                  </div>
                </div>
                <div className="bg-[#18181c] border border-white/[0.06] rounded-[20px] p-3">
                  <div className="text-[11px] font-bold text-zinc-400">❤️ 静息心率</div>
                  <div className="text-lg sm:text-xl font-black text-rose-400 mt-1">
                    {todayHealth?.resting_heart_rate != null ? todayHealth.resting_heart_rate : "—"}
                    {todayHealth?.resting_heart_rate != null && (
                      <span className="text-[11px] font-semibold ml-0.5">bpm</span>
                    )}
                  </div>
                  <div className="text-[10px] text-zinc-500 mt-0.5">自主神经平稳</div>
                </div>
              </div>

              {/* 30天 Banister PMC 负荷曲线 */}
              <div className="pt-1 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3 font-bold">
                    <span className="text-zinc-400">
                      体能 CTL <strong className="text-sky-400">{scienceData?.current_ctl ?? 0}</strong>
                    </span>
                    <span className="text-zinc-400">
                      疲劳 ATL <strong className="text-pink-400">{scienceData?.current_atl ?? 0}</strong>
                    </span>
                    <span className="text-zinc-400">
                      状态 TSB{" "}
                      <strong className="text-emerald-400">
                        {(scienceData?.current_tsb ?? 0) > 0
                          ? `+${scienceData?.current_tsb ?? 0}`
                          : scienceData?.current_tsb ?? 0}
                      </strong>
                    </span>
                  </div>
                  <span className="text-[11px] text-zinc-500">30天 Banister 曲线</span>
                </div>

                <div className="h-[150px] w-full">
                  {ctlHistory.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={ctlHistory.slice(-30)} margin={{ top: 5, right: 5, left: -28, bottom: 0 }}>
                        <CartesianGrid stroke="#222" strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="short_date" stroke="#555" fontSize={10} tickLine={false} />
                        <YAxis stroke="#555" fontSize={10} tickLine={false} />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#16161a",
                            borderColor: "rgba(255,255,255,0.15)",
                            borderRadius: "12px",
                            fontSize: "12px",
                            color: "#fff",
                          }}
                          formatter={(val: any, name: any) => {
                            if (name === "ctl") return [`${val}`, "体能 (CTL)"];
                            if (name === "atl") return [`${val}`, "疲劳 (ATL)"];
                            if (name === "tsb") return [`${val}`, "状态 (TSB)"];
                            return [val, name];
                          }}
                        />
                        <Bar dataKey="tsb" barSize={6} radius={[3, 3, 3, 3]}>
                          {ctlHistory.slice(-30).map((entry: any, index: number) => {
                            const tsbVal = Number(entry.tsb || 0);
                            let color = "#ef4444";
                            if (tsbVal > 5) color = "#10b981";
                            else if (tsbVal >= -30) color = "#0ea5e9";
                            else if (tsbVal >= -50) color = "#f59e0b";
                            return <Cell key={`cell-${index}`} fill={color} opacity={0.75} />;
                          })}
                        </Bar>
                        <Line type="monotone" dataKey="ctl" name="ctl" stroke="#0284c7" strokeWidth={2.5} dot={false} />
                        <Line
                          type="monotone"
                          dataKey="atl"
                          name="atl"
                          stroke="#ec4899"
                          strokeWidth={2}
                          strokeDasharray="4 3"
                          dot={false}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-center bg-[#18181c] rounded-2xl">
                      <Activity className="w-5 h-5 text-zinc-600 mb-1" />
                      <p className="text-xs text-zinc-500">同步跑步记录后自动生成负荷趋势</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* 卡片 D：周期跑量目标进度卡 */}
            <div className="bg-[#121215] border border-white/[0.08] rounded-[28px] p-6 sm:p-7 space-y-4">
              <div className="flex items-center justify-between gap-2">
                <div className="inline-flex p-1 rounded-xl bg-[#18181c] border border-white/[0.06]">
                  {(
                    [
                      { key: "week", label: "本周" },
                      { key: "month", label: `${currentMonthNow}月目标` },
                      { key: "year", label: "全年" },
                    ] as const
                  ).map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveGoalTab(tab.key)}
                      className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
                        activeGoalTab === tab.key
                          ? "bg-[#121215] text-white shadow-sm"
                          : "text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                <div className="text-right tabular-nums">
                  <span className="text-2xl font-black text-[#FC4C02]">
                    {activeGoalTab === "week"
                      ? weeklyProgress.progress_pct ?? 0
                      : activeGoalTab === "month"
                      ? dashboardData?.progress?.progress_pct ?? 0
                      : yearlyStats.progress_pct ?? 0}
                    %
                  </span>
                </div>
              </div>

              <div className="w-full h-2.5 bg-zinc-800/80 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 bg-gradient-to-r from-[#FC4C02] to-[#EA580C]"
                  style={{
                    width: `${Math.min(
                      100,
                      activeGoalTab === "week"
                        ? weeklyProgress.progress_pct ?? 0
                        : activeGoalTab === "month"
                        ? dashboardData?.progress?.progress_pct ?? 0
                        : yearlyStats.progress_pct ?? 0
                    )}%`,
                  }}
                />
              </div>

              <div className="grid grid-cols-4 divide-x divide-white/[0.06] text-center tabular-nums">
                {(activeGoalTab === "week"
                  ? [
                      { label: "本周已跑", value: `${weeklyProgress.current_week_km ?? 0} km`, cls: "text-emerald-400" },
                      { label: "周度目标", value: `${weeklyProgress.target_week_km ?? 50} km`, cls: "text-white" },
                      { label: "剩余里程", value: `${weeklyProgress.remaining_km ?? 0} km`, cls: "text-zinc-300" },
                      { label: "日均需跑", value: `${weeklyProgress.daily_required_km ?? 0} km`, cls: "text-amber-400" },
                    ]
                  : activeGoalTab === "month"
                  ? [
                      {
                        label: "本月已跑",
                        value: `${dashboardData?.progress?.current_month_km ?? 0} km`,
                        cls: "text-white",
                      },
                      {
                        label: "月度目标",
                        value: `${dashboardData?.progress?.target_month_km ?? 200} km`,
                        cls: "text-white",
                      },
                      {
                        label: "剩余里程",
                        value: `${dashboardData?.progress?.remaining_km ?? 0} km`,
                        cls: "text-amber-400",
                      },
                      {
                        label: "日均需跑",
                        value: `${dashboardData?.progress?.daily_required_km ?? 0} km`,
                        cls: "text-[#FC4C02]",
                      },
                    ]
                  : [
                      { label: "累计跑量", value: `${yearlyStats.total_km ?? 0} km`, cls: "text-rose-400" },
                      { label: "年度目标", value: `${yearlyStats.target_year_km ?? 2400} km`, cls: "text-white" },
                      { label: "总跑次", value: `${yearlyStats.total_runs ?? 0} 次`, cls: "text-zinc-300" },
                      { label: "年终预测", value: `${yearlyStats.projected_year_km ?? 0} km`, cls: "text-emerald-400" },
                    ]
                ).map((s) => (
                  <div key={s.label} className="px-1">
                    <div className="text-[11px] font-semibold text-zinc-500">{s.label}</div>
                    <div className={`text-sm sm:text-base font-black mt-1 ${s.cls}`}>{s.value}</div>
                  </div>
                ))}
              </div>

              {activeGoalTab === "week" && (weeklyProgress.daily_breakdown || []).length > 0 && (
                <div className="grid grid-cols-7 gap-1.5 pt-1">
                  {(weeklyProgress.daily_breakdown || []).map((day: any, idx: number) => (
                    <div
                      key={idx}
                      className={`py-2 rounded-xl border flex flex-col items-center text-center ${
                        day.is_today ? "bg-emerald-500/10 border-emerald-500/40" : "bg-[#18181c] border-white/[0.06]"
                      }`}
                    >
                      <span className={`text-[11px] ${day.is_today ? "text-emerald-400 font-black" : "text-zinc-400"}`}>
                        {day.day_name}
                      </span>
                      <span className="text-[9px] text-zinc-600">{day.date}</span>
                      <span
                        className={`mt-1 text-[11px] font-black tabular-nums ${
                          day.distance_km > 0 ? "text-emerald-300" : "text-zinc-600"
                        }`}
                      >
                        {day.distance_km > 0 ? day.distance_km : day.is_past ? "—" : "0"}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {activeGoalTab !== "week" && monthlyTrend.length > 0 && (
                <div className="h-[105px] w-full pt-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={monthlyTrend} margin={{ top: 5, right: 5, left: -28, bottom: 0 }}>
                      <CartesianGrid stroke="#1f1f24" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="month_label" stroke="#555" fontSize={10} tickLine={false} />
                      <YAxis stroke="#555" fontSize={10} tickLine={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#16161a",
                          borderColor: "rgba(255,255,255,0.15)",
                          borderRadius: "12px",
                          fontSize: "12px",
                        }}
                        formatter={(val: any) => [`${val} km`, "月跑量"]}
                      />
                      <Bar dataKey="distance_km" radius={[4, 4, 0, 0]}>
                        {monthlyTrend.map((entry: any, index: number) => (
                          <Cell key={`month-cell-${index}`} fill={entry.is_current ? "#fc4c02" : "#334155"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ══════════════════════════════════════════════════════════════════════════
            第二行核心区：左栏 (5 cols)「跑团荣誉领奖台 (Podium Cards) + 师徒传帮带 + 跑团动态」
                          右栏 (7 cols)「极简高可读性个人近期跑步记录明细」
           ══════════════════════════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* ── LEFT COLUMN (5 cols): 跑团荣誉领奖台与师徒 ── */}
          <div className="lg:col-span-5 space-y-6">
            <div className="bg-[#121215] border border-white/[0.08] rounded-[28px] p-6 sm:p-7 space-y-4">
              {/* Header with Club Selector */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-lg shrink-0">🏆</span>
                    {myClubs.length > 1 ? (
                      <select
                        value={activeClub?.id || ""}
                        onChange={(e) => {
                          const found = myClubs.find((c: any) => c.id === e.target.value);
                          if (found && user?.id) {
                            localStorage.setItem("rgm_active_club_id", found.id);
                            loadClubHubData(found, user.id);
                          }
                        }}
                        className="bg-[#18181c] border border-white/10 rounded-xl px-2.5 py-1 text-base font-black text-white focus:outline-none"
                      >
                        {myClubs.map((c: any) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <h2 className="text-base sm:text-lg font-black text-white break-words pr-1.5">
                        {activeClub?.name || "跑团看板"}
                      </h2>
                    )}
                  </div>
                  {activeClub && (
                    <div className="text-xs text-zinc-400 mt-1">
                      全团本月 <b className="text-white">{clubMetrics?.total_distance_km ?? 0} km</b> · 达标率{" "}
                      <b className="text-emerald-400">{clubMetrics?.avg_completion_rate ?? 0}%</b>
                      {myClubRankItem && (
                        <span>
                          {" "}
                          · 我的排名 <b className="text-amber-400">#{myClubRankItem.rank}</b>
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <Link
                  href="/dashboard/team"
                  className="text-xs font-bold text-[#FC4C02] hover:text-orange-400 shrink-0 mt-1"
                >
                  跑团主页 ›
                </Link>
              </div>

              {activeClub ? (
                <>
                  {/* Switcher: 🥇 本月英雄榜 | 🔥 跑团动态 */}
                  <div className="flex items-center justify-between">
                    <div className="inline-flex p-1 rounded-xl bg-[#18181c] border border-white/[0.06]">
                      <button
                        onClick={() => setClubTab("leaderboard")}
                        className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                          clubTab === "leaderboard"
                            ? "bg-[#121215] text-white shadow-sm"
                            : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        🥇 本月英雄榜 ({clubLeaderboard.length})
                      </button>
                      <button
                        onClick={() => setClubTab("feed")}
                        className={`px-3 py-1 rounded-lg text-xs font-bold transition ${
                          clubTab === "feed"
                            ? "bg-[#121215] text-white shadow-sm"
                            : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        🔥 跑团动态 ({clubFeed.length})
                      </button>
                    </div>
                    <Link href="/dashboard/team" className="text-[11px] font-bold text-zinc-500 hover:text-zinc-300">
                      全部 ›
                    </Link>
                  </div>

                  {clubTab === "leaderboard" ? (
                    <div className="space-y-3">
                      {/* 领奖台三甲矩阵 (Podium Cards: 🥈 #2 · 🥇 #1 · 🥉 #3) */}
                      {clubLeaderboard.length > 0 && (
                        <div className="grid grid-cols-3 gap-2.5 items-end">
                          {[clubLeaderboard[1], clubLeaderboard[0], clubLeaderboard[2]]
                            .filter(Boolean)
                            .map((runner: any) => {
                              const isFirst = runner.rank === 1;
                              const isMe = runner.user_id === user?.id;
                              const medal = runner.rank === 1 ? "🥇" : runner.rank === 2 ? "🥈" : "🥉";
                              return (
                                <div
                                  key={runner.user_id}
                                  className={`rounded-[20px] text-center transition ${
                                    isFirst
                                      ? "py-4 px-2.5 bg-amber-500/10 border-[1.5px] border-amber-500/45"
                                      : isMe
                                      ? "py-3 px-2.5 bg-[#FC4C02]/10 border-[1.5px] border-[#FC4C02]/45"
                                      : "py-3 px-2.5 bg-[#18181c] border border-white/[0.06]"
                                  }`}
                                >
                                  <div className={isFirst ? "text-2xl leading-none" : "text-lg leading-none"}>
                                    {medal}
                                  </div>
                                  <div className="text-xs font-extrabold text-white mt-1.5 break-words leading-snug px-1">
                                    {runner.display_name}
                                    {isMe && <span className="text-[#FC4C02] ml-0.5">(我)</span>}
                                  </div>
                                  <div className="text-base font-black tabular-nums text-[#FC4C02] mt-1">
                                    {runner.distance_km}
                                    <span className="text-[10px] font-semibold text-zinc-400 ml-0.5">km</span>
                                  </div>
                                  <div className="text-[10px] text-zinc-500 mt-0.5">
                                    完成 {runner.progress_pct ?? 0}%
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      )}

                      {/* 4–7 名简洁列表 */}
                      {clubLeaderboard.length > 3 && (
                        <div className="space-y-2">
                          {clubLeaderboard.slice(3, 7).map((runner: any) => {
                            const isMe = runner.user_id === user?.id;
                            return (
                              <div
                                key={runner.user_id}
                                className={`flex items-center justify-between gap-2 px-3.5 py-2.5 rounded-2xl border ${
                                  isMe
                                    ? "bg-[#FC4C02]/10 border-[#FC4C02]/40"
                                    : "bg-[#18181c] border border-white/[0.06]"
                                }`}
                              >
                                <div className="flex items-center gap-2.5 min-w-0">
                                  <span className="w-6 text-xs font-extrabold tabular-nums text-zinc-500 shrink-0">
                                    #{runner.rank}
                                  </span>
                                  <span className="text-xs sm:text-[13px] font-bold text-white break-words leading-snug pr-1">
                                    {runner.display_name}
                                    {isMe && <span className="ml-1 text-[10px] text-[#FC4C02]">(我)</span>}
                                  </span>
                                  <span className="text-[11px] text-zinc-500 shrink-0">
                                    达标 {runner.progress_pct ?? 0}%
                                  </span>
                                </div>
                                <div className="text-right shrink-0 tabular-nums">
                                  <span className="text-sm font-extrabold text-white">
                                    {runner.distance_km}{" "}
                                    <small className="text-[10px] text-[#FC4C02] font-bold">km</small>
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {clubFeed.slice(0, 5).map((item: any) => (
                        <div key={item.id} className="bg-[#18181c] border border-white/[0.06] rounded-2xl p-3 space-y-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0 flex-wrap">
                              <img
                                src={
                                  item.avatar_url ||
                                  "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                                }
                                alt={item.runner_name}
                                className="w-6 h-6 rounded-full object-cover shrink-0"
                              />
                              <span className="text-xs font-bold text-white break-words pr-1">{item.runner_name}</span>
                              <span className="text-[11px] font-black text-[#FC4C02] shrink-0">{item.distance_km} km</span>
                              <span className="text-[10px] text-sky-400 shrink-0">{item.avg_pace}</span>
                            </div>
                            <button
                              onClick={() => handleToggleFeedLike(item.id)}
                              className={`px-2 py-0.5 rounded-full text-[11px] font-bold border transition ${
                                item.has_liked
                                  ? "bg-rose-500/20 border-rose-500/40 text-rose-300"
                                  : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                              }`}
                            >
                              ❤️ {item.likes_count || 0}
                            </button>
                          </div>
                          {item.ai_comment && (
                            <p className="text-[11px] text-zinc-400 line-clamp-2 leading-snug">
                              👨‍🏫 {item.ai_comment}
                            </p>
                          )}
                          {Array.isArray(item.likers) && item.likers.length > 0 && (
                            <div className="flex items-center gap-1.5 pt-1 border-t border-white/[0.04]">
                              <div className="flex items-center -space-x-1.5">
                                {item.likers.slice(0, 6).map((lk: any) => (
                                  <img
                                    key={lk.user_id}
                                    src={
                                      lk.avatar_url ||
                                      `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(lk.user_id || "liker")}`
                                    }
                                    alt={lk.display_name || "跑友"}
                                    className="w-4 h-4 rounded-full object-cover border border-[#18181c]"
                                  />
                                ))}
                              </div>
                              <span className="text-[10px] text-zinc-400 truncate">
                                {item.likers
                                  .slice(0, 4)
                                  .map((lk: any) => lk.display_name || "跑友")
                                  .join("、")}
                                {item.likers.length > 4 ? ` 等${item.likers.length}人赞了` : " 赞了"}
                              </span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 🥋 师徒传帮带高对比度胶囊 */}
                  {(mentorshipOverview?.my_mentor || (mentorshipOverview?.my_mentees || []).length > 0) && (
                    <div className="bg-emerald-500/10 border border-emerald-500/25 rounded-2xl px-4 py-3 space-y-2">
                      {mentorshipOverview?.my_mentor && (
                        <div className="flex items-center justify-between gap-2 text-xs">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-sm shrink-0">🥋</span>
                            <span className="font-extrabold text-emerald-300 break-words">
                              师傅：{mentorshipOverview.my_mentor.display_name}
                              {mentorshipOverview.my_mentor.marathon_pb_str
                                ? ` (全马PB ${mentorshipOverview.my_mentor.marathon_pb_str})`
                                : ""}
                            </span>
                          </div>
                          <Link
                            href="/dashboard/team"
                            className="text-[11px] font-bold text-emerald-300 hover:underline shrink-0"
                          >
                            传帮带 ›
                          </Link>
                        </div>
                      )}
                      {(mentorshipOverview?.my_mentees || []).map((mt: any) => (
                        <Link
                          key={mt.mentee_id}
                          href={`/dashboard/analysis?student_user_id=${encodeURIComponent(mt.mentee_id)}`}
                          className="flex items-center justify-between text-xs bg-[#121215]/70 hover:bg-[#18181c] rounded-xl px-3 py-2 transition"
                        >
                          <div className="min-w-0">
                            <span className="font-bold text-white">徒弟：{mt.display_name}</span>
                            <span className="text-[11px] text-zinc-400 ml-2">
                              7天 {mt.training_summary?.week_km || 0}k · 本月 {mt.training_summary?.month_km || 0}k
                            </span>
                          </div>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 shrink-0">
                            TSB {mt.training_summary?.tsb ?? 0} ›
                          </span>
                        </Link>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="py-8 text-center space-y-3">
                  <Users className="w-8 h-8 text-zinc-600 mx-auto" />
                  <div className="text-xs text-zinc-400">加入或创建跑团，与队友比拼月度跑量、结对师徒传帮带</div>
                  <Link
                    href="/dashboard/team"
                    className="inline-block px-4 py-2 rounded-xl text-xs font-bold bg-[#FC4C02] text-white"
                  >
                    探索跑团 ›
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* ── RIGHT COLUMN (7 cols): 🏃 个人近期与当月跑步记录明细 ── */}
          <div className="lg:col-span-7">
            <div className="bg-[#121215] border border-white/[0.08] rounded-[28px] p-6 sm:p-7 space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3.5 border-b border-white/[0.06]">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h2 className="text-base sm:text-lg font-black text-white">🏃 近期跑步记录</h2>
                  <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-300">
                    {selectedMonth}月累计 {totalMonthKm} km
                  </span>
                  <span className="text-xs text-zinc-400">
                    {monthActivities.length} 次 · 均速 <b className="text-sky-400">{avgMonthPaceStr}</b> · TRIMP{" "}
                    <b className="text-amber-400">{totalMonthTrimp}</b>
                  </span>
                </div>
                <div className="flex items-center gap-2 self-start md:self-auto">
                  {!isViewingCurrentMonth && (
                    <button
                      onClick={handleResetToCurrentMonth}
                      className="px-2.5 py-1 rounded-lg text-[11px] bg-white/5 hover:bg-[#FC4C02]/20 text-zinc-300 hover:text-[#FC4C02] transition"
                    >
                      回到当月
                    </button>
                  )}
                  <div className="flex items-center bg-[#18181c] border border-white/10 rounded-xl p-1">
                    <button
                      onClick={() => handleSwitchMonth(-1)}
                      disabled={loadingMonthActs}
                      className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition disabled:opacity-30"
                      title="上一个月"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="px-2 text-xs font-bold text-white min-w-[84px] text-center">
                      {selectedYear}年{selectedMonth}月
                    </span>
                    <button
                      onClick={() => handleSwitchMonth(1)}
                      disabled={isViewingCurrentMonth || loadingMonthActs}
                      className="p-1 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition disabled:opacity-30 disabled:cursor-not-allowed"
                      title="下一个月"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              <div className="divide-y divide-white/[0.06]">
                {loadingMonthActs ? (
                  <div className="py-10 flex items-center justify-center gap-2 text-zinc-400 text-xs">
                    <Loader2 className="w-4 h-4 text-[#FC4C02] animate-spin" />
                    正在加载...
                  </div>
                ) : monthActivities.length === 0 ? (
                  <div className="py-10 text-center text-zinc-500 text-xs space-y-1.5">
                    <div className="text-2xl">👟</div>
                    <div>
                      {selectedYear}年{selectedMonth}月 暂无跑步记录
                    </div>
                    {isViewingCurrentMonth && (
                      <p className="text-[11px] text-zinc-600">跑完后点击右上角「同步手表数据」</p>
                    )}
                  </div>
                ) : (
                  displayedMonthActivities.map((act: any) => {
                    const mode = act.exclude_mode || "normal";
                    const rawJournal = act.ai_journal || act.ai_comment;
                    let reviewText = "";
                    if (typeof rawJournal === "string") {
                      const trimmed = rawJournal.trim();
                      if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
                        try {
                          const parsed = JSON.parse(trimmed);
                          reviewText = String(
                            parsed?.evaluation || parsed?.summary || parsed?.critique || parsed?.content || ""
                          );
                        } catch {
                          reviewText = trimmed;
                        }
                      } else {
                        reviewText = trimmed;
                      }
                    } else if (rawJournal && typeof rawJournal === "object") {
                      reviewText = String(
                        rawJournal.evaluation || rawJournal.summary || rawJournal.critique || rawJournal.content || ""
                      );
                    }
                    return (
                      <div key={act.id} className={`py-4 space-y-2.5 ${mode === "excluded" ? "opacity-50" : ""}`}>
                        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="font-extrabold text-[15px] text-white flex items-center gap-2 flex-wrap">
                              <span className="break-words pr-1">{act.name}</span>
                              {mode === "normal" && act.workout_effective_vdot && (
                                <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-[#FC4C02]/15 text-[#FC4C02]">
                                  ⚡ VDOT {act.workout_effective_vdot}
                                </span>
                              )}
                              {mode === "ignore_vdot" && (
                                <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-sky-500/15 text-sky-300">
                                  🤝 陪跑不计 VDOT
                                </span>
                              )}
                              {mode === "excluded" && (
                                <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-zinc-500/20 text-zinc-300">
                                  🚫 已忽略
                                </span>
                              )}
                              {act.elevation_gain_meters > 0 && (
                                <span className="text-[11px] font-semibold text-zinc-400">
                                  ⛰️ +{Math.round(act.elevation_gain_meters)}m
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-zinc-500 mt-1 flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatActivityTime(act.start_time)}
                              {act.moving_time_seconds > 0 && (
                                <span className="ml-2">· 用时 {formatDurationSeconds(act.moving_time_seconds)}</span>
                              )}
                            </div>
                          </div>

                          <div className="flex items-center justify-between xl:justify-end gap-4 text-xs flex-wrap">
                            <div className="flex items-center gap-5 tabular-nums">
                              <div>
                                <span className="text-zinc-500 font-semibold block text-[10px]">里程</span>
                                <span className="font-black text-base text-white">
                                  {act.distance_km}{" "}
                                  <small className="text-[11px] font-semibold text-zinc-400">km</small>
                                </span>
                              </div>
                              <div>
                                <span className="text-zinc-500 font-semibold block text-[10px]">配速</span>
                                <span className="font-extrabold text-sm text-sky-400">{act.avg_pace_str}</span>
                              </div>
                              <div>
                                <span className="text-zinc-500 font-semibold block text-[10px]">心率</span>
                                <span className="font-extrabold text-sm text-rose-400">
                                  {act.average_heartrate || "—"}{" "}
                                  {act.average_heartrate && (
                                    <small className="text-[10px] font-semibold text-zinc-500">bpm</small>
                                  )}
                                </span>
                              </div>
                              <div>
                                <span className="text-zinc-500 font-semibold block text-[10px]">负荷</span>
                                <span className="font-extrabold text-sm text-amber-400">{act.trimp || "—"}</span>
                              </div>
                            </div>

                            <div className="flex items-center gap-1.5">
                              <button
                                onClick={() => setExpandedTrackId(expandedTrackId === act.id ? null : act.id)}
                                className={`p-1.5 rounded-lg text-xs border transition ${
                                  expandedTrackId === act.id
                                    ? "bg-[#FC4C02] text-white border-[#FC4C02]"
                                    : "bg-white/5 hover:bg-white/10 text-zinc-300 border-white/5"
                                }`}
                                title="轨迹地图"
                              >
                                🗺️
                              </button>
                              <button
                                onClick={() => {
                                  setShareCardActivityId(act.id);
                                  setShareCardModalOpen(true);
                                }}
                                className="p-1.5 rounded-lg text-xs border bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border-sky-400/30 transition"
                                title="朋友圈分享卡"
                              >
                                📸
                              </button>
                              <select
                                value={mode}
                                disabled={updatingExcludeId === act.id}
                                onChange={(e) =>
                                  handleUpdateExcludeMode(
                                    act.id,
                                    e.target.value as "normal" | "ignore_vdot" | "excluded"
                                  )
                                }
                                title="统计设定：是否计入跑量 / VDOT"
                                className="bg-[#18181c] border border-white/10 rounded-lg text-[11px] text-zinc-300 px-1.5 py-1.5 focus:outline-none focus:border-[#FC4C02]/50 disabled:opacity-50"
                              >
                                <option value="normal">⚙️ 正常计入</option>
                                <option value="ignore_vdot">🤝 陪跑不计 VDOT</option>
                                <option value="excluded">🚫 忽略此记录</option>
                              </select>
                            </div>
                          </div>
                        </div>

                        {reviewText && (
                          <div className="bg-[#18181c] border-l-[3px] border-l-purple-500 rounded-r-xl px-3.5 py-2.5 text-xs text-zinc-300 leading-relaxed">
                            <strong className="font-bold text-purple-300">Canova 复盘：</strong>
                            {reviewText}
                          </div>
                        )}

                        {expandedTrackId === act.id && (
                          <div className="pt-2 animate-in fade-in duration-200">
                            <RouteMapPreview
                              activityId={act.id}
                              trackData={act.gps_track_data}
                              mapImageUrl={act.map_image_url}
                              activityName={act.name}
                              distanceMeters={act.distance_meters || (act.distance_km ? act.distance_km * 1000 : 0)}
                              elevationGain={act.elevation_gain_meters}
                              avgPace={act.avg_pace_str}
                              eagerFetch={true}
                            />
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

              {!loadingMonthActs && monthActivities.length > 6 && (
                <button
                  onClick={() => setShowAllMonthActs(!showAllMonthActs)}
                  className="w-full py-2.5 rounded-2xl text-xs font-bold text-zinc-400 hover:text-white bg-[#18181c] hover:bg-white/10 transition"
                >
                  {showAllMonthActs ? "收起记录 ▴" : `查看当月全部 ${monthActivities.length} 条跑步记录 ▾`}
                </button>
              )}
            </div>
          </div>
        </div>
      </main>

      <GarminConnectModal
        open={garminModalOpen}
        onClose={() => setGarminModalOpen(false)}
        uid={user?.id}
        initialBrand={modalBrand}
        onSuccess={() => user && loadDashboardData(user.id)}
      />

      <OrgRequirementModal
        isOpen={showOrgReminderModal}
        onClose={() => {
          setShowOrgReminderModal(false);
          if (user?.id) {
            sessionStorage.setItem(`org_reminder_dismissed_${user.id}`, "1");
          }
        }}
        reminder={orgReminder}
        onNavigateToProfile={handleGoToRequiredFields}
      />

      {checkinLogModalOpen && todayWorkout && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#18181c] border border-white/10 rounded-3xl max-w-lg w-full p-6 space-y-4 shadow-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <h3 className="text-base font-black text-white">📝 今日训练打卡 · 感受 · 备注 · 照片</h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  {todayWorkout.date || "今日"} · {todayWorkout.title}（小程序与网页实时同步）
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCheckinLogModalOpen(false)}
                className="px-2.5 py-1 rounded-xl bg-white/5 text-zinc-400 hover:text-white text-sm font-bold cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="text-zinc-200 font-bold block mb-2">😊 今日训练感受标签</label>
                <div className="grid grid-cols-3 gap-2">
                  {WEB_FEELING_TAGS.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => setCheckinFeelingTag(checkinFeelingTag === tag ? "" : tag)}
                      className={`py-2 px-2 rounded-xl font-bold border transition cursor-pointer ${
                        checkinFeelingTag === tag
                          ? "bg-emerald-500/20 border-emerald-500 text-emerald-300"
                          : "bg-[#121215] border-white/10 text-zinc-300 hover:text-white"
                      }`}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-zinc-200 font-bold">🔥 主观体感强度 (RPE 1-10)</label>
                  <span className="text-[11px] text-zinc-400">1-3轻松 · 4-6适中 · 7-8吃力 · 9-10极限</span>
                </div>
                <div className="grid grid-cols-10 gap-1.5">
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setCheckinRpe(checkinRpe === n ? null : n)}
                      className={`py-2 rounded-xl font-mono font-black border transition cursor-pointer ${
                        checkinRpe === n
                          ? n >= 8
                            ? "bg-rose-500 text-white border-rose-400"
                            : n >= 5
                            ? "bg-amber-500 text-black border-amber-400"
                            : "bg-emerald-500 text-black border-emerald-400"
                          : "bg-[#121215] border-white/10 text-zinc-400 hover:text-white"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-zinc-200 font-bold block mb-1.5">💬 训练备注与心得</label>
                <textarea
                  rows={3}
                  value={checkinNotes}
                  onChange={(e) => setCheckinNotes(e.target.value)}
                  placeholder="记录今日配速体感、心率表现、天气路况或身体反应..."
                  className="w-full bg-[#121215] border border-white/10 rounded-2xl px-3.5 py-2.5 text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-zinc-200 font-bold">📸 打卡照片（最多 3 张，可同步生成分享卡）</label>
                  <span className="text-zinc-400">
                    {checkinWorkoutPhotos.length + checkinNewPhotosBase64.length}/3
                  </span>
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  {checkinWorkoutPhotos.map((url, idx) => (
                    <div
                      key={`saved-${idx}`}
                      className="relative w-20 h-20 rounded-2xl overflow-hidden border border-white/15"
                    >
                      <img src={url} alt="已上传" className="w-full h-full object-cover" />
                      <button
                        type="button"
                        onClick={() =>
                          setCheckinWorkoutPhotos((prev) => prev.filter((_, i) => i !== idx))
                        }
                        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/75 text-white text-[10px] flex items-center justify-center cursor-pointer"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  {checkinNewPhotosBase64.map((b64, nIdx) => (
                    <div
                      key={`new-${nIdx}`}
                      className="relative w-20 h-20 rounded-2xl overflow-hidden border border-emerald-500/40"
                    >
                      <img src={b64} alt="待上传" className="w-full h-full object-cover" />
                      <button
                        type="button"
                        onClick={() =>
                          setCheckinNewPhotosBase64((prev) => prev.filter((_, i) => i !== nIdx))
                        }
                        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/75 text-white text-[10px] flex items-center justify-center cursor-pointer"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                  {checkinWorkoutPhotos.length + checkinNewPhotosBase64.length < 3 && (
                    <label className="w-20 h-20 rounded-2xl bg-[#121215] border-2 border-dashed border-white/20 hover:border-emerald-400 flex flex-col items-center justify-center gap-1 cursor-pointer transition">
                      <span className="text-lg">📷</span>
                      <span className="text-[10px] text-zinc-400 font-bold">添加照片</span>
                      <input
                        type="file"
                        accept="image/*"
                        multiple
                        onChange={handleWebPhotoUploadChange}
                        className="hidden"
                      />
                    </label>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
              <button
                type="button"
                onClick={() => setCheckinLogModalOpen(false)}
                className="px-4 py-2 rounded-xl border border-white/10 text-xs font-bold text-zinc-400 hover:text-white cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSaveWebCheckinLog}
                disabled={savingCheckinLog}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:opacity-95 text-white text-xs font-black shadow-lg transition cursor-pointer disabled:opacity-50"
              >
                {savingCheckinLog ? "保存同步中..." : "💾 保存打卡记录"}
              </button>
            </div>
          </div>
        </div>
      )}

      <PersonalShareCardModal
        open={shareCardModalOpen}
        onClose={() => setShareCardModalOpen(false)}
        uid={user?.id}
        activityId={shareCardActivityId}
      />

      {user?.id && (
        <PersonalReportModal
          isOpen={personalReportModalOpen}
          onClose={() => setPersonalReportModalOpen(false)}
          userId={user.id}
        />
      )}
    </div>
  );
}
