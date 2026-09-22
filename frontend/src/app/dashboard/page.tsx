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
import {
  Zap,
  Activity,
  Heart,
  Moon,
  BatteryCharging,
  TrendingUp,
  RefreshCw,
  Award,
  Trophy,
  ChevronRight,
  ChevronLeft,
  Clock,
  Loader2,
  Flame,
  Calendar,
  Compass,
  Target,
  Check,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
} from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  AreaChart,
  Area,
  LineChart,
  Line,
  Bar,
  BarChart,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";

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

  // Month activities states
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [selectedMonth, setSelectedMonth] = useState<number>(new Date().getMonth() + 1);
  const [monthActivities, setMonthActivities] = useState<any[]>([]);
  const [loadingMonthActs, setLoadingMonthActs] = useState<boolean>(false);

  // Grand Org field requirements reminder states
  const [userOrgs, setUserOrgs] = useState<any[]>([]);
  const [orgReminder, setOrgReminder] = useState<OrgReminderInfo | null>(null);
  const [showOrgReminderModal, setShowOrgReminderModal] = useState<boolean>(false);

  function parseOrgReminder(orgs: any[]): OrgReminderInfo {
    if (!orgs || !orgs.length) return { hasReminder: false, type: "none" };

    // 1. Check suspended/expired
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

    // 2. Check temporary OR has missing fields (even for admin/pending/etc)
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

  async function loadDashboardData(uid: string) {
    setLoading(true);
    try {
      const [dashRes, sciRes] = await Promise.all([
        apiClient.get(`/api/miniapp/dashboard/${uid}`),
        apiClient.get(`/api/science/metrics/${uid}`),
      ]);
      setDashboardData(dashRes.data);
      setScienceData(sciRes.data);

      const acts = dashRes.data?.current_month_activities || dashRes.data?.recent_activities || [];
      setMonthActivities(acts);
      if (dashRes.data?.current_month_info) {
        setSelectedYear(dashRes.data.current_month_info.year);
        setSelectedMonth(dashRes.data.current_month_info.month);
      }

      // Check organization field requirements & prompt modal if incomplete
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
        operator_uid: user.id
      });
      if (res.data?.success) {
        await loadDashboardData(user.id);
      }
    } catch (err) {
      console.error("Failed to toggle today workout:", err);
    } finally {
      setTogglingWorkout(false);
    }
  }

  const ctlHistory = scienceData?.ctl_atl_tsb_history || [];
  const monthlyTrend = dashboardData?.monthly_trend?.trend || [];
  const yearlyStats = dashboardData?.yearly_stats || {};
  const todayHealth = dashboardData?.today_health || {};
  const weeklyProgress = dashboardData?.weekly_progress || {};
  const todayWorkout = dashboardData?.today_workout || weeklyProgress?.today_workout;

  const currentYearNow = dashboardData?.current_month_info?.year || new Date().getFullYear();
  const currentMonthNow = dashboardData?.current_month_info?.month || (new Date().getMonth() + 1);
  const isViewingCurrentMonth = selectedYear === currentYearNow && selectedMonth === currentMonthNow;

  const totalMonthKm = Math.round(monthActivities.reduce((acc, a) => acc + (Number(a.distance_km) || 0), 0) * 10) / 10;
  const totalMonthTrimp = Math.round(monthActivities.reduce((acc, a) => acc + (Number(a.trimp) || 0), 0));
  const runsWithPace = monthActivities.filter(a => (a.moving_time_seconds || 0) > 0 && (a.distance_km || 0) > 0);
  let avgMonthPaceStr = "—";
  if (runsWithPace.length > 0) {
    const totalSec = runsWithPace.reduce((acc, a) => acc + (a.moving_time_seconds || 0), 0);
    const totalKm = runsWithPace.reduce((acc, a) => acc + (a.distance_km || 0), 0);
    if (totalKm > 0) {
      const secPerKm = Math.round(totalSec / totalKm);
      const pm = Math.floor(secPerKm / 60);
      const ps = secPerKm % 60;
      avgMonthPaceStr = `${pm}:${ps < 10 ? '0' : ''}${ps} /km`;
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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Top Header Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight flex items-center gap-2.5">
              <span>跑步控制台 Dashboard</span>
            </h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              追踪当前训练周期负荷，直连佳明 / 高驰手表与 Renato Canova 科学训练系统
            </p>
          </div>

          <div className="flex items-center gap-3">
            {dashboardData?.user?.garmin_connected || dashboardData?.user?.coros_connected ? (
              <div className="flex items-center gap-2">
                {dashboardData?.user?.garmin_connected && (
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    Garmin 已连接
                  </div>
                )}
                {dashboardData?.user?.coros_connected && (
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                    <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                    COROS 已连接
                  </div>
                )}
              </div>
            ) : (
              <button
                onClick={() => {
                  setModalBrand("garmin");
                  setGarminModalOpen(true);
                }}
                className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl text-xs sm:text-sm font-bold bg-[#FC4C02] text-white hover:bg-orange-600 transition active:scale-95 shadow-md shadow-[#FC4C02]/20"
              >
                <Zap className="w-3.5 h-3.5" />
                绑定运动设备 (Garmin/高驰)
              </button>
            )}

            {userOrgs?.some(o => o.role === "owner" || o.role === "admin") && (
              <button
                onClick={handlePreviewReminderModal}
                title="管理员测试：预览未完善信息队员打开看板时所见的弹窗"
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 text-amber-300 transition active:scale-95"
              >
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                <span>预览补齐弹窗</span>
              </button>
            )}

            <button
              onClick={handleSync}
              disabled={syncing}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold bg-[#1a1a1e] border border-white/10 hover:border-white/20 transition active:scale-95 text-zinc-200"
            >
              <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin text-[#FC4C02]" : ""}`} />
              {syncing ? "正在从手表同步..." : "一键同步数据"}
            </button>
          </div>
        </div>

        {/* ── 大组织必填资料待完善醒目提醒横幅 (若有) ── */}
        {orgReminder?.hasReminder && (
          <div
            onClick={handleGoToRequiredFields}
            className={`p-4 sm:p-5 rounded-3xl border cursor-pointer transition-all duration-300 flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
              orgReminder.type === "suspended"
                ? "bg-gradient-to-r from-rose-500/15 via-[#1a1215] to-[#121215] border-rose-500/40 hover:border-rose-500/60 shadow-lg shadow-rose-950/30"
                : "bg-gradient-to-r from-amber-500/15 via-[#1a1812] to-[#121215] border-amber-500/40 hover:border-amber-500/60 shadow-lg shadow-amber-950/30"
            }`}
          >
            <div className="flex items-start sm:items-center gap-3.5">
              <div
                className={`p-2.5 rounded-2xl flex-shrink-0 ${
                  orgReminder.type === "suspended"
                    ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                    : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                }`}
              >
                {orgReminder.type === "suspended" ? (
                  <ShieldAlert className="w-5 h-5" />
                ) : (
                  <AlertTriangle className="w-5 h-5" />
                )}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span
                    className={`text-sm sm:text-base font-bold ${
                      orgReminder.type === "suspended" ? "text-rose-300" : "text-amber-300"
                    }`}
                  >
                    {orgReminder.type === "suspended"
                      ? `⚠️ 【${orgReminder.firstOrg?.name}】组织访问已被暂停`
                      : `📋 【${orgReminder.firstOrg?.name}】入队必填档案待完善`}
                  </span>
                  {orgReminder.remainingDays !== undefined && orgReminder.remainingDays !== null && (
                    <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                      剩余 {orgReminder.remainingDays} 天
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  {orgReminder.missingLabels
                    ? `尚缺少必填项目：${orgReminder.missingLabels}`
                    : "请尽快补齐入队实名资料以获管理员审核确认并恢复完整权限"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs font-bold text-amber-400 bg-amber-500/10 hover:bg-amber-500/20 px-4 py-2 rounded-xl border border-amber-500/30 transition self-end sm:self-auto flex-shrink-0">
              <span>立即前往补齐</span>
              <ArrowRight className="w-4 h-4" />
            </div>
          </div>
        )}

        {/* ── CARD 0: 本周跑量进度与今日训练计划 (在周跑量进度下面) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
          {/* Top: Weekly Mileage Progress Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <Target className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                    本周跑量进度
                  </h2>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-black">
                    {weeklyProgress.progress_pct ?? 0}%
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-0.5">
                  {weeklyProgress.week_label || "本周周期"} · 目标 {weeklyProgress.target_week_km ?? 50} km
                </p>
              </div>
            </div>

            {/* Quick stats on the right */}
            <div className="flex items-center gap-2.5 sm:gap-3 flex-wrap">
              <div className="bg-[#18181c] border border-white/5 px-3.5 py-2 rounded-2xl text-center min-w-[68px]">
                <span className="text-[10px] text-zinc-500 font-bold block">已跑</span>
                <span className="text-base font-black text-emerald-400">{weeklyProgress.current_week_km ?? 0} <span className="text-[10px] font-normal text-zinc-400">km</span></span>
              </div>
              <div className="bg-[#18181c] border border-white/5 px-3.5 py-2 rounded-2xl text-center min-w-[68px]">
                <span className="text-[10px] text-zinc-500 font-bold block">目标</span>
                <span className="text-base font-black text-white">{weeklyProgress.target_week_km ?? 50} <span className="text-[10px] font-normal text-zinc-400">km</span></span>
              </div>
              <div className="bg-[#18181c] border border-white/5 px-3.5 py-2 rounded-2xl text-center min-w-[68px]">
                <span className="text-[10px] text-zinc-500 font-bold block">剩余</span>
                <span className="text-base font-black text-zinc-300">{weeklyProgress.remaining_km ?? 0} <span className="text-[10px] font-normal text-zinc-400">km</span></span>
              </div>
              <div className="bg-[#18181c] border border-white/5 px-3.5 py-2 rounded-2xl text-center min-w-[68px]">
                <span className="text-[10px] text-zinc-500 font-bold block">日均需跑</span>
                <span className="text-base font-black text-amber-400">{weeklyProgress.daily_required_km ?? 0} <span className="text-[10px] font-normal text-zinc-400">km</span></span>
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full h-2.5 bg-zinc-800/80 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, weeklyProgress.progress_pct ?? 0)}%` }}
            />
          </div>

          {/* 7-Day Strip */}
          <div className="grid grid-cols-7 gap-2">
            {(weeklyProgress.daily_breakdown || []).map((day: any, idx: number) => (
              <div
                key={idx}
                className={`py-2.5 px-1 rounded-2xl border flex flex-col items-center justify-between text-center transition ${
                  day.is_today
                    ? "bg-emerald-500/10 border-emerald-500/40 shadow-[0_0_12px_rgba(16,185,129,0.15)]"
                    : "bg-[#18181c] border-white/5"
                }`}
              >
                <span className={`text-[11px] font-semibold ${day.is_today ? "text-emerald-400 font-black" : "text-zinc-400"}`}>
                  {day.day_name}
                </span>
                <span className="text-[9px] text-zinc-500 mt-0.5">{day.date}</span>
                <div className={`mt-2 px-1.5 py-0.5 rounded-lg text-[10px] font-black ${
                  day.distance_km > 0
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : day.is_past
                    ? "text-zinc-600"
                    : "text-zinc-500"
                }`}>
                  {day.distance_km > 0 ? `${day.distance_km}k` : (day.is_past ? "—" : "0")}
                </div>
              </div>
            ))}
          </div>

          {/* ── TODAY'S SCHEDULED WORKOUT CARD (在周跑量进度正下方) ── */}
          <div className="pt-2 border-t border-white/5">
            {todayWorkout ? (
              <div className={`p-5 rounded-2xl border transition ${
                todayWorkout.completed
                  ? "bg-emerald-950/10 border-emerald-500/30"
                  : todayWorkout.workout_type === "race"
                  ? "bg-rose-950/15 border-rose-500/40"
                  : "bg-[#18181c] border-white/10"
              }`}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-base">📅</span>
                    <span className="text-sm font-bold text-white">今日训练课目</span>
                    <span className="text-xs text-zinc-400">({todayWorkout.date} {todayWorkout.day_of_week})</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold border border-purple-500/30 bg-purple-500/10 text-purple-300">
                      {todayWorkout.workout_type === "race" ? "🏁 比赛日" : todayWorkout.workout_type === "rest" ? "☕ 休息日" : "科学课表"}
                    </span>
                    {todayWorkout.completed && todayWorkout.actual_distance_km && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold border border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
                        实跑 {todayWorkout.actual_distance_km}km
                      </span>
                    )}
                  </div>
                  <Link
                    href="/dashboard/coach"
                    className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 font-medium transition"
                  >
                    <span>查看完整周期课表</span>
                    <span>→</span>
                  </Link>
                </div>

                <div className="space-y-2.5">
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-base font-black text-white">{todayWorkout.title}</h3>
                    {todayWorkout.workout_type !== "rest" && (
                      <div className="flex items-baseline gap-1">
                        <span className="text-2xl font-black text-white">{todayWorkout.distance_km || 0}</span>
                        <span className="text-xs text-zinc-400">km</span>
                      </div>
                    )}
                  </div>

                  {(todayWorkout.target_pace || todayWorkout.target_hr_zone) && todayWorkout.workout_type !== "rest" && (
                    <div className="flex flex-wrap gap-2 text-xs">
                      {todayWorkout.target_pace && todayWorkout.target_pace !== "—" && (
                        <div className="px-2.5 py-1 rounded-lg bg-[#121215] border border-white/5 text-purple-300 font-medium">
                          ⏱️ 配速: {todayWorkout.target_pace}
                        </div>
                      )}
                      {todayWorkout.target_hr_zone && todayWorkout.target_hr_zone !== "—" && (
                        <div className="px-2.5 py-1 rounded-lg bg-[#121215] border border-white/5 text-emerald-300 font-medium">
                          ❤️ 心率: {todayWorkout.target_hr_zone}
                        </div>
                      )}
                    </div>
                  )}

                  {todayWorkout.description && (
                    <p className="text-xs text-zinc-300 leading-relaxed font-light">
                      {todayWorkout.description}
                    </p>
                  )}

                  {todayWorkout.coach_notes && (
                    <div className="bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-xl text-xs text-amber-200">
                      <span className="font-bold text-amber-300">👨‍🏫 跑团教练批注：</span>
                      <span className="ml-1">{todayWorkout.coach_notes}</span>
                    </div>
                  )}
                </div>

                {/* Bottom Toggle Button */}
                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
                  <button
                    onClick={handleToggleTodayWorkout}
                    disabled={togglingWorkout}
                    className={`flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-xs font-bold border transition ${
                      todayWorkout.completed
                        ? "bg-emerald-500/20 border-emerald-500 text-emerald-300 hover:bg-emerald-500/30"
                        : "bg-[#1a1a20] border-white/10 text-white hover:border-purple-500/50 hover:bg-purple-950/20"
                    }`}
                  >
                    <Check className={`w-3.5 h-3.5 ${todayWorkout.completed ? "text-emerald-400" : "text-zinc-400"}`} />
                    <span>
                      {todayWorkout.completed
                        ? (todayWorkout.actual_distance_km ? `已打卡 ${todayWorkout.actual_distance_km}km` : "今日课表已完成")
                        : "今日打卡"}
                    </span>
                  </button>

                  <Link
                    href="/dashboard/coach"
                    className="text-xs text-zinc-400 hover:text-white transition"
                  >
                    所属计划: {todayWorkout.plan_title || "科学训练计划"}
                  </Link>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-2xl bg-[#18181c] border border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xl">💡</span>
                  <div>
                    <div className="text-xs font-bold text-zinc-200">今日暂无专属计划课表</div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">前往 AI 智能教练，根据您的目标赛事或体能维持一键生成定制计划</div>
                  </div>
                </div>
                <Link
                  href="/dashboard/coach"
                  className="text-xs px-3 py-1.5 rounded-xl bg-purple-600/20 border border-purple-500/30 text-purple-300 hover:bg-purple-600/30 transition font-bold"
                >
                  去制定课表 ›
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* ── CARD 1: 体能与状况指数 (Fitness & Form) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <div className="flex items-center gap-2.5">
                <Zap className="w-5 h-5 text-[#38bdf8]" />
                <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                  体能与状况指数 (Fitness & Form)
                </h2>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                基于标准 Banister TRIMP 与 EWMA 模型算法
              </p>
            </div>

            {/* Badges in Top Right */}
            <div className="flex items-center gap-3">
              <div className="bg-[#1a1a20] border border-white/5 px-4 py-2 rounded-2xl flex flex-col items-center min-w-[76px]">
                <span className="text-[10px] text-[#38bdf8] font-bold tracking-wider uppercase">CTL 体能</span>
                <span className="text-lg font-black text-white">{scienceData?.current_ctl ?? 0}</span>
              </div>
              <div className="bg-[#1a1a20] border border-white/5 px-4 py-2 rounded-2xl flex flex-col items-center min-w-[76px]">
                <span className="text-[10px] text-[#ec4899] font-bold tracking-wider uppercase">ATL 疲劳</span>
                <span className="text-lg font-black text-white">{scienceData?.current_atl ?? 0}</span>
              </div>
              <div className="bg-[#1a1a20] border border-white/5 px-4 py-2 rounded-2xl flex flex-col items-center min-w-[76px]">
                <span className="text-[10px] text-zinc-400 font-bold tracking-wider uppercase">TSB 状况</span>
                <span
                  className="text-lg font-black"
                  style={{ color: scienceData?.current_tsb_badge?.color || "#6b7280" }}
                >
                  {scienceData?.current_tsb ?? 0}
                </span>
              </div>
            </div>
          </div>

          {/* Combined Chart */}
          <div className="h-[280px] sm:h-[320px] w-full">
            {ctlHistory.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={ctlHistory.slice(-30)} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="#222" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="short_date"
                    stroke="#666"
                    fontSize={11}
                    tickLine={false}
                  />
                  <YAxis stroke="#666" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#16161a",
                      borderColor: "rgba(255,255,255,0.15)",
                      borderRadius: "16px",
                      fontSize: "12px",
                      color: "#fff",
                    }}
                    formatter={(val: any, name: any) => {
                      if (name === "ctl") return [`${val}`, "体能 (CTL)"];
                      if (name === "atl") return [`${val}`, "疲劳 (ATL)"];
                      if (name === "tsb") return [`${val}`, "状况 (TSB)"];
                      return [val, name];
                    }}
                  />
                  <Bar dataKey="tsb" barSize={12} radius={[4, 4, 4, 4]}>
                    {ctlHistory.slice(-30).map((entry: any, index: number) => {
                      const tsbVal = Number(entry.tsb || 0);
                      let color = "#0ea5e9";
                      if (tsbVal > 5) color = "#22c55e";
                      else if (tsbVal >= -30) color = "#1890ff";
                      else if (tsbVal >= -50) color = "#eab308";
                      else color = "#ef4444";
                      return <Cell key={`cell-${index}`} fill={color} opacity={0.85} />;
                    })}
                  </Bar>
                  <Line
                    type="monotone"
                    dataKey="ctl"
                    name="ctl"
                    stroke="#38bdf8"
                    strokeWidth={2.5}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="atl"
                    name="atl"
                    stroke="#ec4899"
                    strokeWidth={2.5}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 bg-[#16161a]/30 rounded-2xl border border-white/5">
                <Activity className="w-8 h-8 text-zinc-600 mb-2" />
                <p className="text-sm font-bold text-zinc-300">暂无体能负荷数据</p>
                <p className="text-xs text-zinc-500 max-w-sm mt-1">
                  连接 Garmin 或高驰手表并同步跑步记录后，将基于 Banister TRIMP 模型自动生成 42 天 CTL/ATL/TSB 趋势分析。
                </p>
              </div>
            )}
          </div>

          {/* Color-Coded Legend */}
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 mt-4 pt-4 border-t border-white/5 text-xs text-zinc-400">
            <div className="flex items-center gap-2">
              <span className="w-3 h-1 bg-[#38bdf8] rounded-full inline-block" />
              <span>体能 (CTL): 42天长期压力</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-1 bg-[#ec4899] rounded-full inline-block" />
              <span>疲劳 (ATL): 7天近期压力</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#22c55e] rounded-sm inline-block" />
              <span>&gt;5 巅峰</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#1890ff] rounded-sm inline-block" />
              <span>-30~5 训练中</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#eab308] rounded-sm inline-block" />
              <span>-50~-30 疲劳</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-[#ef4444] rounded-sm inline-block" />
              <span>&lt;-50 严重</span>
            </div>
          </div>
        </div>

        {/* ── CARD 2: 生理与恢复卡片 (Garmin / COROS) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="flex items-center gap-2">
                <Compass className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                  生理与恢复卡片
                </h2>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                最近更新: {todayHealth?.date || "今日"}
              </p>
            </div>
            <div className="text-xs text-zinc-500 bg-white/5 px-3 py-1.5 rounded-full border border-white/5">
              Device Direct Sync
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. 睡眠恢复 */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs mb-2">
                <Moon className="w-4 h-4 text-indigo-400" />
                <span>睡眠恢复</span>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-white">
                  {todayHealth?.sleep_score != null ? (
                    <>
                      {todayHealth.sleep_score} <span className="text-sm font-medium text-zinc-400">分</span>
                    </>
                  ) : (
                    <span className="text-zinc-500 font-medium text-xl">—</span>
                  )}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  {todayHealth?.sleep_duration_text ? `时长 ${todayHealth.sleep_duration_text}` : "未同步睡眠"}
                </div>
              </div>
            </div>

            {/* 2. 静息心率 */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs mb-2">
                <Heart className="w-4 h-4 text-rose-500" />
                <span>静息心率 (RHR)</span>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-rose-400">
                  {todayHealth?.resting_heart_rate != null ? (
                    <>
                      {todayHealth.resting_heart_rate} <span className="text-sm font-medium text-zinc-400">bpm</span>
                    </>
                  ) : (
                    <span className="text-zinc-500 font-medium text-xl">—</span>
                  )}
                </div>
                <div className="text-xs text-zinc-500 mt-1">清晨生理基线</div>
              </div>
            </div>

            {/* 3. 身体电量 */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs mb-2">
                <BatteryCharging className="w-4 h-4 text-amber-400" />
                <span>身体电量</span>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-amber-300">
                  {todayHealth?.body_battery_max != null ? `${todayHealth.body_battery_max}%` : "—"}
                </div>
                <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden mt-2">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 rounded-full"
                    style={{ width: `${Math.min(100, todayHealth?.body_battery_max ?? 0)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* 4. 夜间 HRV / 摄氧量 */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center gap-2 text-zinc-400 text-xs mb-2">
                <Activity className="w-4 h-4 text-cyan-400" />
                <span>夜间 HRV / 摄氧量</span>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-cyan-400">
                  {todayHealth?.hrv_ms != null ? (
                    <>
                      {todayHealth.hrv_ms} <span className="text-sm font-medium text-zinc-400">ms</span>
                    </>
                  ) : (
                    <span className="text-zinc-500 font-medium text-xl">—</span>
                  )}
                </div>
                <div className="text-xs text-zinc-500 mt-1">
                  {todayHealth?.hrv_weekly_avg ? `周均: ${todayHealth.hrv_weekly_avg} ms` : ""}
                  {todayHealth?.vo2_max ? ` · VO2Max ${todayHealth.vo2_max}` : ""}
                  {!todayHealth?.hrv_weekly_avg && !todayHealth?.vo2_max && (todayHealth?.hrv_status ? `状态: ${todayHealth.hrv_status}` : "清晨静息基线")}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── CARD 3: 月度跑量趋势 (近 6 个月) ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                月度跑量趋势
              </h2>
              <p className="text-xs text-zinc-400 mt-1">近 6 个月跑量分布与环比</p>
            </div>
            <div className="text-right">
              <div className="text-2xl sm:text-3xl font-black text-white">
                {dashboardData?.monthly_trend?.current_month_km ?? 119.9} <span className="text-sm text-zinc-400 font-normal">km</span>
              </div>
              <div className="text-xs text-emerald-400 font-semibold mt-0.5">
                ↑ 较上月 +{dashboardData?.monthly_trend?.pct_change ?? 9.2}%
              </div>
            </div>
          </div>

          {/* 6-Month Bar Chart */}
          <div className="h-[200px] sm:h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid stroke="#1f1f24" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month_label" stroke="#666" fontSize={11} tickLine={false} />
                <YAxis stroke="#666" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#16161a",
                    borderColor: "rgba(255,255,255,0.15)",
                    borderRadius: "14px",
                    fontSize: "12px",
                  }}
                  formatter={(val: any) => [`${val} km`, "总跑量"]}
                />
                <Bar dataKey="distance_km" radius={[6, 6, 0, 0]}>
                  {monthlyTrend.map((entry: any, index: number) => (
                    <Cell
                      key={`month-cell-${index}`}
                      fill={entry.is_current ? "#22c55e" : "#1b4332"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 3-Month Summary Breakdown */}
          <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-white/5 text-center">
            {(dashboardData?.monthly_trend?.recent_3_months || []).map((m: any, idx: number) => (
              <div key={idx} className="bg-[#18181c] border border-white/5 rounded-2xl py-3 px-2">
                <div className="text-xs text-zinc-400">{m.month_label}</div>
                <div className="text-base sm:text-lg font-black text-white mt-1">
                  {m.distance_km} <span className="text-xs text-zinc-500 font-normal">km</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-0.5">{m.count} 次</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── CARD 4: 2026 年度统计 ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2.5">
              <Trophy className="w-5 h-5 text-amber-500" />
              <div>
                <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                  {yearlyStats.year || 2026} 年度统计
                </h2>
                <p className="text-xs text-zinc-400 mt-1">
                  目标 {yearlyStats.target_year_km || 3400} km · 月均目标 {yearlyStats.monthly_target_km || 70} km
                </p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl sm:text-3xl font-black text-rose-500">
                {yearlyStats.progress_pct || 38.9}%
              </div>
              <div className="text-xs text-zinc-400 mt-0.5">完成度</div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
            {/* Circular Indicator */}
            <div className="flex flex-col items-center justify-center p-6 bg-[#18181c] border border-white/5 rounded-3xl">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="50" fill="transparent" stroke="#222" strokeWidth="10" />
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    fill="transparent"
                    stroke="#f43f5e"
                    strokeWidth="10"
                    strokeDasharray="314.159"
                    strokeDashoffset={314.159 * (1 - (yearlyStats.progress_pct || 38.9) / 100)}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-xl font-black text-white">{yearlyStats.total_km || 1324.3}</span>
                  <span className="text-[10px] text-zinc-400">km</span>
                </div>
              </div>
            </div>

            {/* 3 Metric Cards */}
            <div className="md:col-span-3 grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-center">
                <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                  <span>🏃 总跑次</span>
                </div>
                <div className="text-2xl font-black text-white">
                  {yearlyStats.total_runs || 88} <span className="text-xs text-zinc-500 font-normal">次</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-1">全年累计运动</div>
              </div>

              <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-center">
                <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                  <span>📅 月均跑量</span>
                </div>
                <div className="text-2xl font-black text-white">
                  {yearlyStats.avg_monthly_km || 165.5} <span className="text-xs text-zinc-500 font-normal">km</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-1">月度平均负荷</div>
              </div>

              <div className="bg-[#18181c] border border-white/5 rounded-2xl p-5 flex flex-col justify-center">
                <div className="flex items-center gap-2 text-zinc-400 text-xs mb-1">
                  <span>🎯 年终预测</span>
                </div>
                <div className="text-2xl font-black text-emerald-400">
                  {yearlyStats.projected_year_km || 1986.4} <span className="text-xs text-zinc-500 font-normal">km</span>
                </div>
                <div className="text-[11px] text-zinc-500 mt-1">年终推算跑量</div>
              </div>
            </div>
          </div>

          {/* Bottom Progress Bar */}
          <div className="mt-6 pt-6 border-t border-white/5">
            <div className="flex items-center justify-between text-xs text-zinc-400 mb-2">
              <span>0 km</span>
              <span className="font-bold text-white">
                {yearlyStats.total_km || 1324.3} / {yearlyStats.target_year_km || 3400} km
              </span>
              <span>{yearlyStats.target_year_km || 3400} km</span>
            </div>
            <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
              <div
                className="h-full bg-rose-500 rounded-full"
                style={{ width: `${Math.min(100, yearlyStats.progress_pct || 38.9)}%` }}
              />
            </div>
            <div className="text-xs text-amber-400 mt-3 flex items-center gap-1.5">
              <span>🏆 最佳月份:</span>
              <span className="text-white font-semibold">
                {yearlyStats.best_month?.name || "5月"} ({yearlyStats.best_month?.distance_km || 413.2}km) · 平均配速 {yearlyStats.best_month?.avg_pace || "7:41"}
              </span>
            </div>
          </div>
        </div>

        {/* ── CARD 5: 当月运动记录明细 ── */}
        <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                  {selectedYear}年{selectedMonth}月 运动记录明细
                </h2>
                {isViewingCurrentMonth ? (
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#FC4C02]/20 text-[#FC4C02] border border-[#FC4C02]/30">
                    当月
                  </span>
                ) : (
                  <button
                    onClick={handleResetToCurrentMonth}
                    className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-white/10 hover:bg-[#FC4C02]/20 text-zinc-300 hover:text-[#FC4C02] transition border border-white/10"
                  >
                    回到当月
                  </button>
                )}
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                {isViewingCurrentMonth ? "完整展示当月全部跑步打卡、配速用时与教练点评" : `展示 ${selectedYear}年${selectedMonth}月 全部跑步打卡记录`}
              </p>
            </div>

            {/* Month Switcher Controls */}
            <div className="flex items-center gap-2 self-start md:self-auto bg-[#18181c] border border-white/10 rounded-2xl p-1.5 shadow-inner">
              <button
                onClick={() => handleSwitchMonth(-1)}
                disabled={loadingMonthActs}
                className="p-1.5 rounded-xl hover:bg-white/10 text-zinc-400 hover:text-white transition disabled:opacity-30"
                title="查看上一个月"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <div className="px-3 text-xs font-bold text-white tracking-wide min-w-[90px] text-center">
                {selectedYear}年{selectedMonth}月
              </div>
              <button
                onClick={() => handleSwitchMonth(1)}
                disabled={isViewingCurrentMonth || loadingMonthActs}
                className="p-1.5 rounded-xl hover:bg-white/10 text-zinc-400 hover:text-white transition disabled:opacity-30 disabled:cursor-not-allowed"
                title="查看下一个月"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Month Stats Chips */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#18181c]/60 border border-white/5 rounded-2xl p-3.5">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-orange-500/10 text-[#FC4C02] flex items-center justify-center font-bold text-sm">
                🏃
              </div>
              <div>
                <span className="text-[10px] text-zinc-500 block">跑步次数</span>
                <span className="text-sm font-bold text-white">{monthActivities.length} 次</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-sm">
                📏
              </div>
              <div>
                <span className="text-[10px] text-zinc-500 block">累计跑量</span>
                <span className="text-sm font-bold text-emerald-400">{totalMonthKm} km</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold text-sm">
                ⏱️
              </div>
              <div>
                <span className="text-[10px] text-zinc-500 block">平均配速</span>
                <span className="text-sm font-bold text-cyan-400">{avgMonthPaceStr}</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center font-bold text-sm">
                ⚡
              </div>
              <div>
                <span className="text-[10px] text-zinc-500 block">累计TRIMP负荷</span>
                <span className="text-sm font-bold text-amber-400">{totalMonthTrimp}</span>
              </div>
            </div>
          </div>

          {/* Activities List */}
          <div className="divide-y divide-white/5">
            {loadingMonthActs ? (
              <div className="py-12 flex flex-col items-center justify-center gap-3 text-zinc-400 text-xs">
                <Loader2 className="w-5 h-5 text-[#FC4C02] animate-spin" />
                <span>正在加载 {selectedYear}年{selectedMonth}月 运动记录...</span>
              </div>
            ) : monthActivities.length === 0 ? (
              <div className="py-12 text-center text-zinc-500 text-xs sm:text-sm space-y-2">
                <div className="text-2xl">👟</div>
                <div>{selectedYear}年{selectedMonth}月 暂无跑步运动记录</div>
                {isViewingCurrentMonth && (
                  <p className="text-[11px] text-zinc-600">完成跑步后点击右上角【一键同步数据】即可自动呈现当月所有打卡记录。</p>
                )}
              </div>
            ) : (
              monthActivities.map((act: any) => (
                <div key={act.id} className="py-4 border-b border-white/5 last:border-none space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-3.5">
                      <div className="w-10 h-10 rounded-2xl bg-[#1e1e24] flex items-center justify-center text-[#FC4C02] flex-shrink-0">
                        🏃
                      </div>
                      <div>
                        <div className="font-bold text-sm sm:text-base text-white flex items-center gap-2">
                          <span>{act.name}</span>
                          {act.elevation_gain_meters > 0 && (
                            <span className="text-[10px] font-normal px-2 py-0.5 rounded-full bg-white/5 text-zinc-400">
                              ⛰️ +{Math.round(act.elevation_gain_meters)}m
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-zinc-500 mt-0.5 flex items-center gap-1.5">
                          <Clock className="w-3 h-3 text-zinc-500" />
                          <span>{formatActivityTime(act.start_time)}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 sm:gap-6 text-xs sm:text-sm flex-wrap">
                      <div>
                        <span className="text-zinc-500 block text-[10px]">距离</span>
                        <span className="font-bold text-white text-base">{act.distance_km} km</span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">配速</span>
                        <span className="font-bold text-cyan-400">{act.avg_pace_str}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">用时</span>
                        <span className="font-bold text-zinc-300">{formatDurationSeconds(act.moving_time_seconds)}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">心率</span>
                        <span className="font-bold text-rose-400">{act.average_heartrate ? `${act.average_heartrate} bpm` : "—"}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">TRIMP</span>
                        <span className="font-bold text-amber-400">{act.trimp || "—"}</span>
                      </div>
                      <button
                        onClick={() => setExpandedTrackId(expandedTrackId === act.id ? null : act.id)}
                        className={`px-2.5 py-1.5 rounded-xl transition flex items-center gap-1.5 text-xs font-medium border ${
                          expandedTrackId === act.id
                            ? "bg-[#FC4C02] text-white border-[#FC4C02] shadow-sm"
                            : "bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white border-white/5"
                        }`}
                        title="查看/收起 GPS 航迹路线"
                      >
                        <span>🗺️</span>
                        <span>{expandedTrackId === act.id ? "收起地图" : "轨迹地图"}</span>
                      </button>
                    </div>
                  </div>

                  {/* Canova AI Critique if available */}
                  {act.ai_journal && (
                    <div className="bg-[#18181c]/80 border border-white/5 rounded-2xl px-4 py-2.5 text-xs text-zinc-300 flex items-start gap-2.5">
                      <span className="text-base flex-shrink-0">👨‍🏫</span>
                      <div className="flex-1">
                        <span className="font-semibold text-zinc-200 text-[11px] block text-[#FC4C02]">Canova 教练复盘：</span>
                        <span className="leading-relaxed text-zinc-400">{act.ai_journal}</span>
                      </div>
                    </div>
                  )}

                  {/* Expanded GPS Track */}
                  {expandedTrackId === act.id && (
                    <div className="mt-3 pt-3 border-t border-white/5 animate-in fade-in duration-200">
                      <RouteMapPreview
                        activityId={act.id}
                        trackData={act.gps_track_data}
                        mapImageUrl={act.map_image_url}
                        activityName={act.name}
                        distanceMeters={act.distance_meters || (act.distance_km ? act.distance_km * 1000 : 0)}
                        elevationGain={act.elevation_gain_meters}
                        avgPace={act.avg_pace_str}
                      />
                    </div>
                  )}
                </div>
              ))
            )}
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
    </div>
  );
}
