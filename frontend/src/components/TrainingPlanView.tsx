"use client";

import { useEffect, useState, useMemo } from "react";
import apiClient, { formatBeijingTime } from "@/lib/apiClient";
import { showToast, askConfirm } from "@/components/ui/UiFeedbackProvider";
import {
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Edit3,
  Flame,
  Mountain,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
  Trophy,
  User,
  Zap,
  Clock,
  Dumbbell,
  Activity,
  Heart,
  AlertCircle,
  X,
  Check
} from "lucide-react";

interface TrainingPlanViewProps {
  user: any;
  userRaces?: any[];
  initialTargetRace?: string;
  initialTargetTime?: string;
}

export default function TrainingPlanView({
  user,
  userRaces = [],
  initialTargetRace = "上海马拉松",
  initialTargetTime = "3:09:30"
}: TrainingPlanViewProps) {
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [plan, setPlan] = useState<any>(null);
  const [savedPlanBeforePreview, setSavedPlanBeforePreview] = useState<any>(null);
  const [confirmingPreview, setConfirmingPreview] = useState(false);
  const [allPlans, setAllPlans] = useState<any[]>([]);
  const [planBackups, setPlanBackups] = useState<any[]>([]);
  const [showVersionSwitcher, setShowVersionSwitcher] = useState(false);
  const [rollingBackPlan, setRollingBackPlan] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [selectedWeekIdx, setSelectedWeekIdx] = useState(1);
  const [userGoal, setUserGoal] = useState<any>(null);
  const [syncingGoal, setSyncingGoal] = useState(false);
  const [syncSuccessMsg, setSyncSuccessMsg] = useState("");

  // Goal configuration form state
  const [goalType, setGoalType] = useState<"race_prep" | "fitness_maintenance">("race_prep");
  const [targetRaceName, setTargetRaceName] = useState(initialTargetRace);
  const [targetTime, setTargetTime] = useState(initialTargetTime);
  const [raceType, setRaceType] = useState("marathon");
  const [maintenanceFocus, setMaintenanceFocus] = useState<string>("aerobic_base");
  const [weeksCount, setWeeksCount] = useState(8);
  const [daysPerWeek, setDaysPerWeek] = useState(4);
  const [preferredLongRunDay, setPreferredLongRunDay] = useState("Sunday");
  const [targetDate, setTargetDate] = useState("");

  // Edit workout & runner daily self-report modal state
  const [weekViewMode, setWeekViewMode] = useState<"w19_table" | "cards">("w19_table");
  const [editingModalOpen, setEditingModalOpen] = useState(false);
  const [editWeekIdx, setEditWeekIdx] = useState(1);
  const [editDayIdx, setEditDayIdx] = useState(0);
  const [editWorkoutType, setEditWorkoutType] = useState("easy_run");
  const [editTitle, setEditTitle] = useState("");
  const [editDistanceKm, setEditDistanceKm] = useState<number | string>(10.0);
  const [editTargetPace, setEditTargetPace] = useState("");
  const [editTargetHrZone, setEditTargetHrZone] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editCompleted, setEditCompleted] = useState(false);
  const [editCoachNotes, setEditCoachNotes] = useState("");
  const [editFeelingTag, setEditFeelingTag] = useState("");
  const [editRpe, setEditRpe] = useState<string>("");
  const [editAthleteNotes, setEditAthleteNotes] = useState("");
  const [editWorkoutPhotos, setEditWorkoutPhotos] = useState<string[]>([]);
  const [editNewPhotosBase64, setEditNewPhotosBase64] = useState<string[]>([]);
  const [editExecutionText, setEditExecutionText] = useState("");

  const PLAN_FEELING_TAGS = [
    "🤩 状态极佳",
    "😊 轻松舒适",
    "💪 正常发挥",
    "😮‍💨 略感吃力",
    "🥵 疲惫掉速",
    "🦵 肌肉酸紧",
  ];

  function handlePlanPhotoUploadChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const currentTotal = editWorkoutPhotos.length + editNewPhotosBase64.length;
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
            setEditNewPhotosBase64((prev) => [...prev, dataUrl]);
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
  const [editHrv, setEditHrv] = useState<string>("");
  const [editRestingHr, setEditRestingHr] = useState<string>("");
  const [editRespRate, setEditRespRate] = useState<string>("");
  const [editStrainScore, setEditStrainScore] = useState<string>("");
  const [editRecoveryPct, setEditRecoveryPct] = useState<string>("");
  const [editStrengthDone, setEditStrengthDone] = useState(false);
  const [editSwapDayIdx, setEditSwapDayIdx] = useState<number>(-1);
  const [editIsSwapped, setEditIsSwapped] = useState(false);
  const [savingWorkout, setSavingWorkout] = useState(false);

  // Weekly summary & injury report state
  const [weekInjuryNote, setWeekInjuryNote] = useState("");
  const [weekAthleteSummary, setWeekAthleteSummary] = useState("");
  const [weekTravelNote, setWeekTravelNote] = useState("");
  const [weekStrengthCount, setWeekStrengthCount] = useState<number>(0);
  const [savingWeekSummary, setSavingWeekSummary] = useState(false);

  useEffect(() => {
    if (user?.id) {
      loadUserPlan(user.id);
    }
  }, [user]);

  function getRecommendedTargetRace(races: any[]): any | null {
    if (!races || races.length === 0) return null;
    const upcomingRaces = races.filter(
      (r) => r.status !== "completed" && !r.is_completed && !r.is_past
    );
    const candidates = upcomingRaces.length > 0 ? upcomingRaces : races;
    const aRace = candidates.find(
      (r) => r.priority === 1 || r.priority === "A" || r.priority === "1"
    );
    if (aRace) return aRace;
    const bRace = candidates.find(
      (r) => r.priority === 2 || r.priority === "B" || r.priority === "2"
    );
    if (bRace) return bRace;
    return candidates[0] || races[0];
  }

  const recommendedRace = useMemo(
    () => getRecommendedTargetRace(userRaces),
    [userRaces]
  );

  const isTargetRaceCompleted = useMemo(() => {
    if (!plan || !userRaces || userRaces.length === 0) return false;
    const targetName = plan.target_race_name;
    const matched = userRaces.find(
      (r: any) =>
        r.name === targetName || (plan.title && plan.title.includes(r.name))
    );
    return Boolean(
      matched &&
        (matched.status === "completed" ||
          matched.is_completed ||
          matched.is_past)
    );
  }, [plan, userRaces]);

  useEffect(() => {
    if (
      recommendedRace &&
      (!targetRaceName ||
        targetRaceName === "目标赛事" ||
        userRaces.find((r: any) => r.name === targetRaceName)?.status ===
          "completed")
    ) {
      setTargetRaceName(recommendedRace.name);
      if (recommendedRace.target_time) setTargetTime(recommendedRace.target_time);
      if (recommendedRace.race_date) setTargetDate(recommendedRace.race_date);
      if (recommendedRace.race_type) setRaceType(recommendedRace.race_type);
    }
  }, [recommendedRace, userRaces]);

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

  const firstDays = weeks[0]?.days || [];
  const firstDates = firstDays.map((day: any) => day.date).filter(Boolean);
  if (firstDates.length && todayStr < firstDates[0]) {
    return weeks[0].week_index || 1;
  }

  const lastDays = weeks[weeks.length - 1]?.days || [];
  const lastDates = lastDays.map((day: any) => day.date).filter(Boolean);
  if (lastDates.length && todayStr > lastDates[lastDates.length - 1]) {
    return weeks[weeks.length - 1].week_index || weeks.length;
  }

  return 1;
}

  async function loadUserPlan(uid: string) {
    setLoading(true);
    try {
      const res = await apiClient.get(`/api/coach/plan/user/${uid}`);
      setAllPlans(res.data?.all_plans || []);
      setPlanBackups(res.data?.backups || []);
      if (res.data?.active_plan) {
        setPlan(res.data.active_plan);
        const curWk = res.data.active_plan.current_week_index || computeCurrentWeekIndex(res.data.active_plan);
        setSelectedWeekIdx(curWk);
        setShowConfig(false);
      } else {
        setShowConfig(true);
      }
      if (res.data?.user_goal) {
        setUserGoal(res.data.user_goal);
      }
    } catch (err) {
      console.error("Failed to load user plan:", err);
      setShowConfig(true);
    } finally {
      setLoading(false);
    }
  }

  async function handleRunnerSwitchOrRollbackPlan(opts: { backupId?: string; targetPlanId?: string; label?: string }) {
    if (!user?.id || rollingBackPlan) return;
    if (
      !await askConfirm(
        `确认将当前训练计划切换/回退至「${opts.label || "历史方案"}」吗？\n（您已完成的每日跑步打卡数据将 100% 合并保留）`
      )
    ) {
      return;
    }
    setRollingBackPlan(true);
    try {
      const res = await apiClient.post(`/api/coach/plan/user/${user.id}/rollback`, {
        operator_uid: user.id,
        backup_id: opts.backupId,
        target_plan_id: opts.targetPlanId,
      });
      setSyncSuccessMsg(res.data?.message || "✅ 已成功切换训练方案！");
      setShowVersionSwitcher(false);
      await loadUserPlan(user.id);
      setTimeout(() => setSyncSuccessMsg(""), 5000);
    } catch (err: any) {
      showToast(err.response?.data?.detail || "切换方案失败，请稍后重试");
    } finally {
      setRollingBackPlan(false);
    }
  }

  async function handleSyncToGoals() {
    if (!plan?.id) return;
    setSyncingGoal(true);
    try {
      const res = await apiClient.post(`/api/coach/plan/${plan.id}/sync-to-goals`, {
        user_id: user.id
      });
      if (res.data?.success) {
        setSyncSuccessMsg(res.data.message || "课表跑量目标已成功同步为个人目标！");
        setUserGoal((prev: any) => ({
          ...prev,
          weekly_target: res.data.weekly_target,
          target_distance: res.data.monthly_target,
          monthly_targets: res.data.monthly_targets
        }));
        setTimeout(() => setSyncSuccessMsg(""), 6000);
      }
    } catch (err: any) {
      console.error("Sync goals error:", err);
      showToast(err.response?.data?.detail || "同步失败，请稍后重试");
    } finally {
      setSyncingGoal(false);
    }
  }

  async function handleGeneratePlan() {
    if (!user?.id) return;
    setGenerating(true);
    try {
      const payload: any = {
        athlete_uid: user.id,
        goal_type: goalType,
        target_race_name: targetRaceName,
        target_time: targetTime,
        race_type: raceType,
        maintenance_focus: maintenanceFocus,
        weeks_count: weeksCount,
        days_per_week: daysPerWeek,
        preferred_long_run_day: preferredLongRunDay,
        operator_uid: user.id
      };
      if (targetDate) {
        payload.target_date = targetDate;
      }
      if (userGoal?.weekly_target) {
        payload.user_weekly_target = Number(userGoal.weekly_target);
      }
      const hadActivePlan = Boolean(plan && !(plan as any)?.is_preview);
      if (hadActivePlan || Boolean((plan as any)?.is_preview)) {
        payload.preview_only = true;
        if (hadActivePlan) {
          setSavedPlanBeforePreview(plan);
        }
      }

      const res = await apiClient.post("/api/coach/plan/generate", payload);
      if (res.data?.success && res.data?.plan) {
        const nextPlan = payload.preview_only ? { ...res.data.plan, is_preview: true } : res.data.plan;
        setPlan(nextPlan);
        const curWk = nextPlan.current_week_index || computeCurrentWeekIndex(nextPlan);
        setSelectedWeekIdx(curWk);
        setShowConfig(false);
      }
    } catch (err) {
      console.error("Generate plan error:", err);
      showToast("生成训练计划失败，请稍后重试！");
    } finally {
      setGenerating(false);
    }
  }

  async function handleConfirmPreviewPlan() {
    if (!plan || !user?.id || confirmingPreview) return;
    setConfirmingPreview(true);
    try {
      const res = await apiClient.post("/api/coach/plan/confirm", {
        plan_payload: plan,
        operator_uid: user.id,
      });
      if (res.data?.success && res.data?.plan) {
        setPlan(res.data.plan);
        setSavedPlanBeforePreview(null);
        await loadUserPlan(user.id);
      }
    } catch (err: any) {
      showToast(err.response?.data?.detail || "确认启用新课表失败，请稍后重试");
    } finally {
      setConfirmingPreview(false);
    }
  }

  function handleDiscardPreviewPlan() {
    setPlan(savedPlanBeforePreview);
    setSavedPlanBeforePreview(null);
  }

  function handleOpenEditModal(wIdx: number, dIdx: number, day: any) {
    setEditWeekIdx(wIdx);
    setEditDayIdx(dIdx);
    setEditWorkoutType(day.workout_type || "easy_run");
    setEditTitle(day.title || "");
    setEditDistanceKm(day.distance_km !== undefined ? day.distance_km : 0);
    setEditTargetPace(day.target_pace || "");
    setEditTargetHrZone(day.target_hr_zone || "");
    setEditDescription(day.description || "");
    setEditCompleted(Boolean(day.completed));
    setEditCoachNotes(day.coach_notes || "");
    setEditFeelingTag(day.feeling_tag || "");
    setEditRpe(day.rpe != null ? String(day.rpe) : "");
    setEditAthleteNotes(day.athlete_notes || "");
    setEditWorkoutPhotos(
      Array.isArray(day.workout_photos)
        ? [...day.workout_photos]
        : day.photo_url
        ? [day.photo_url]
        : []
    );
    setEditNewPhotosBase64([]);
    setEditExecutionText(day.actual_execution_text || "");
    setEditHrv(day.hrv != null ? String(day.hrv) : "");
    setEditRestingHr(day.resting_hr != null ? String(day.resting_hr) : "");
    setEditRespRate(day.respiratory_rate != null ? String(day.respiratory_rate) : "");
    setEditStrainScore(day.strain_score != null ? String(day.strain_score) : "");
    setEditRecoveryPct(day.recovery_pct != null ? String(day.recovery_pct) : "");
    setEditStrengthDone(Boolean(day.strength_completed));
    setEditSwapDayIdx(-1);
    const noteStr = String(day.athlete_notes || "");
    const execStr = String(day.actual_execution_text || "");
    setEditIsSwapped(
      Boolean(
        day.is_swapped ||
          day.swapped_from ||
          noteStr.includes("对换课表") ||
          (execStr.startsWith("跑休") && execStr.includes("对换"))
      )
    );
    setEditingModalOpen(true);
  }

  async function handleUndoSwapWorkout() {
    if (!plan?.id || !user?.id) return;
    const isPreviewPlan = Boolean((plan as any)?.is_preview);
    setSavingWorkout(true);
    try {
      const payload: any = {
        week_index: editWeekIdx,
        day_index: editDayIdx,
        undo_swap: true,
        operator_uid: user.id
      };
      if (isPreviewPlan) {
        payload.preview_only = true;
        payload.plan_payload = plan;
        payload.schedule_data = plan?.schedule_data;
      }
      const res = await apiClient.patch(`/api/coach/plan/${plan.id}/workout`, payload);
      if (res.data?.success && res.data?.plan) {
        setPlan(res.data.plan);
        setEditingModalOpen(false);
      }
    } catch (err) {
      console.error("Failed to undo swap:", err);
      showToast("取消对换失败，请重试！");
    } finally {
      setSavingWorkout(false);
    }
  }

  async function handleSaveWorkout() {
    if (!plan?.id || !user?.id) return;
    setSavingWorkout(true);
    try {
      const payload: any = {
        week_index: editWeekIdx,
        day_index: editDayIdx,
        workout_type: editWorkoutType,
        title: editTitle,
        distance_km: parseFloat(String(editDistanceKm)) || 0,
        target_pace: editTargetPace,
        target_hr_zone: editTargetHrZone,
        description: editDescription,
        completed: editCompleted,
        coach_notes: editCoachNotes,
        feeling_tag: editFeelingTag,
        athlete_notes: editAthleteNotes,
        workout_photos: editWorkoutPhotos,
        new_photos_base64: editNewPhotosBase64,
        actual_execution_text: editExecutionText,
        strength_completed: editStrengthDone,
        operator_uid: user.id
      };
      if (editRpe.trim() !== "") payload.rpe = Number(editRpe);
      if (editHrv.trim() !== "") payload.hrv = Number(editHrv);
      if (editRestingHr.trim() !== "") payload.resting_hr = Number(editRestingHr);
      if (editRespRate.trim() !== "") payload.respiratory_rate = Number(editRespRate);
      if (editStrainScore.trim() !== "") payload.strain_score = Number(editStrainScore);
      if (editRecoveryPct.trim() !== "") payload.recovery_pct = Number(editRecoveryPct);
      if (editSwapDayIdx === -2) {
        payload.undo_swap = true;
      } else if (editSwapDayIdx >= 0 && editSwapDayIdx !== editDayIdx) {
        payload.swap_with_day_index = editSwapDayIdx;
      }
      const res = await apiClient.patch(`/api/coach/plan/${plan.id}/workout`, payload);
      if (res.data?.success && res.data?.plan) {
        setPlan(res.data.plan);
        setEditingModalOpen(false);
      }
    } catch (err) {
      console.error("Failed to update workout:", err);
      showToast("保存课表更新失败，请重试！");
    } finally {
      setSavingWorkout(false);
    }
  }

  async function handleSaveRunnerWeekSummary() {
    if (!plan?.id || !user?.id || !activeWeek) return;
    setSavingWeekSummary(true);
    try {
      const res = await apiClient.post(`/api/coach/plan/${plan.id}/week-summary`, {
        operator_uid: user.id,
        week_index: activeWeek.week_index || selectedWeekIdx,
        injury_note: weekInjuryNote,
        athlete_weekly_summary: weekAthleteSummary,
        travel_or_leave_note: weekTravelNote,
        strength_sessions_done: Number(weekStrengthCount) || 0,
      });
      if (res.data?.plan) {
        setPlan(res.data.plan);
        setSyncSuccessMsg("✅ 本周小结与伤痛报备已同步提交给教练！");
        setTimeout(() => setSyncSuccessMsg(""), 4000);
      }
    } catch (err: any) {
      showToast(err.response?.data?.detail || "保存周小结失败");
    } finally {
      setSavingWeekSummary(false);
    }
  }

  async function handleToggleQuickComplete(wIdx: number, dIdx: number, day: any) {
    if (!plan?.id || !user?.id) return;
    try {
      const newStatus = !day.completed;
      const payload = {
        week_index: wIdx,
        day_index: dIdx,
        completed: newStatus,
        operator_uid: user.id
      };
      const res = await apiClient.patch(`/api/coach/plan/${plan.id}/workout`, payload);
      if (res.data?.success && res.data?.plan) {
        setPlan(res.data.plan);
        if (newStatus) {
          const updatedWeek = (res.data.plan?.schedule_data?.weeks || []).find((w: any) => w.week_index === wIdx);
          const updatedDay = updatedWeek?.days?.[dIdx] || { ...day, completed: true };
          handleOpenEditModal(wIdx, dIdx, updatedDay);
        }
      }
    } catch (err) {
      console.error("Failed to toggle completion:", err);
    }
  }

  const currentWeeks = plan?.schedule_data?.weeks || [];
  const activeWeek = currentWeeks.find((w: any) => w.week_index === selectedWeekIdx) || currentWeeks[0];

  useEffect(() => {
    if (activeWeek) {
      setWeekInjuryNote(activeWeek.injury_note || "");
      setWeekAthleteSummary(activeWeek.athlete_weekly_summary || "");
      setWeekTravelNote(activeWeek.travel_or_leave_note || "");
      setWeekStrengthCount(activeWeek.strength_sessions_done || 0);
    }
  }, [activeWeek?.week_index, plan?.updated_at]);

  const maintenanceOptions = [
    {
      id: "aerobic_base",
      name: "🏃 基础有氧耐力扩容",
      desc: "低心率 Zone 2 扩容 · 慢肌毛细血管网 · 提升脂肪氧化率",
      tag: "筑底夯基"
    },
    {
      id: "lactate_threshold",
      name: "⚡ 乳酸阈值耐力提升",
      desc: "LT1/LT2 巡航间歇 · 提高抗乳酸能力 · 延伸高速巡航续航",
      tag: "门槛巡航"
    },
    {
      id: "vo2max_speed",
      name: "🚀 VO2Max 速度储备",
      desc: "800~1500m 短间歇 · 激活快肌纤维 · 强化神经步频刚性",
      tag: "速度突破"
    },
    {
      id: "trail_climbing",
      name: "🏔️ 山地越野爬坡抗阻",
      desc: "手杖爬升 (D+) · 阶梯爆发力 · 下坡股四头肌离心抗撕裂",
      tag: "山地专项"
    },
    {
      id: "general_maintenance",
      name: "🛡️ 综合体能维持与防伤",
      desc: "平衡周跑量 · 核心深层稳定 · 保持体能 CTL 与肌肉弹性",
      tag: "健康保持"
    }
  ];

  const workoutTypeStyles: Record<string, { label: string; badge: string; border: string }> = {
    easy_run: { label: "轻松跑", badge: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20", border: "border-emerald-500/20" },
    tempo: { label: "门槛跑", badge: "bg-sky-500/10 text-sky-300 border-sky-500/20", border: "border-sky-500/20" },
    interval: { label: "间歇跑", badge: "bg-amber-500/10 text-amber-300 border-amber-500/20", border: "border-amber-500/20" },
    long_run: { label: "长距离", badge: "bg-purple-500/10 text-purple-300 border-purple-500/20", border: "border-purple-500/20" },
    trail_climb: { label: "越野爬坡", badge: "bg-teal-500/10 text-teal-300 border-teal-500/20", border: "border-teal-500/20" },
    cross_training: { label: "交叉力量", badge: "bg-pink-500/10 text-pink-300 border-pink-500/20", border: "border-pink-500/20" },
    race: { label: "🏁 比赛日", badge: "bg-rose-500/20 text-rose-300 border-rose-500/40 font-black shadow-sm shadow-rose-500/20", border: "border-rose-500/40 bg-rose-950/10" },
    rest: { label: "休息日", badge: "bg-zinc-800 text-zinc-400 border-white/5", border: "border-white/5" }
  };

  return (
    <div className="space-y-6">
      {/* ── Top Control & Goal Bar ── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-[#121215] border border-white/[0.08] p-5 rounded-3xl shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-purple-500/20">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-black text-white">
                {plan ? plan.title : "个人科学周期训练计划"}
              </h2>
              {plan && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                  执行中 · {plan.weeks_count}周周期
                </span>
              )}
              {plan?.source_label && (
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                  {plan.source_label}
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Canova 专项性推进 · 结合 18 个月实战比赛表现与动态负荷自适应 · 跑者与教练双向协同
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto flex-wrap">
          {(planBackups.length > 0 || allPlans.filter((p) => p.status === "archived").length > 0) && (
            <button
              onClick={() => setShowVersionSwitcher((prev) => !prev)}
              className={`px-3.5 py-2 rounded-xl text-xs font-medium border transition flex items-center justify-center gap-1.5 cursor-pointer ${
                showVersionSwitcher
                  ? "bg-[#FC4C02] text-white border-[#FC4C02] font-bold"
                  : "bg-[#18181c] hover:bg-white/10 text-zinc-300 border-white/10"
              }`}
              title="在 AI 科学周期计划与教练派发课表之间自由切换或回退上一版"
            >
              历史方案切换 ({planBackups.length + allPlans.filter((p) => p.status === "archived").length})
            </button>
          )}
          {plan && (
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="flex-1 sm:flex-none px-4 py-2 rounded-xl text-xs font-medium border border-white/10 text-zinc-300 bg-[#18181c] hover:border-white/25 hover:text-white transition flex items-center justify-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5 text-zinc-400" />
              {showConfig ? "收起定制面板" : "重新制定训练计划"}
            </button>
          )}
          {plan && (
            <button
              onClick={() => loadUserPlan(user.id)}
              disabled={loading}
              className="p-2 rounded-xl text-xs border border-white/10 text-zinc-400 hover:text-white transition bg-[#18181c]"
              title="刷新计划"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          )}
        </div>
      </div>

      {/* ── Preview Confirmation Bar (prevents overwriting active plan without explicit confirmation) ── */}
      {Boolean((plan as any)?.is_preview) && (
        <div className="bg-amber-500/10 border border-amber-500/40 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
          <div className="space-y-0.5">
            <div className="text-xs font-black text-amber-300 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4" />
              新课表预览模式（尚未覆盖您正在执行的训练计划）
            </div>
            <p className="text-[11px] text-zinc-300">
              您可以先逐周查看配速与跑量安排；确认无误后点击右侧「确认启用新课表」正式生效，原课表将自动存入历史快照。
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleDiscardPreviewPlan}
              className="px-3.5 py-2 rounded-xl text-xs font-bold bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 transition cursor-pointer"
            >
              放弃预览
            </button>
            <button
              type="button"
              disabled={confirmingPreview}
              onClick={handleConfirmPreviewPlan}
              className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md transition flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
            >
              <Check className="w-3.5 h-3.5" />
              {confirmingPreview ? "正在写入..." : "确认启用新课表"}
            </button>
          </div>
        </div>
      )}

      {/* ── Collapsible Multi-Plan Switcher & Version Rollback Panel ── */}
      {showVersionSwitcher && (
        <div className="bg-[#18181c] border border-white/10 rounded-2xl p-5 space-y-3 shadow-xl">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                多套训练方案切换与历史版本回退
              </h3>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                每次重新生成或由教练派发课表时，系统都会自动保留历史方案。您可以随时切回任意方案，所有已完成的打卡数据自动合并保留。
              </p>
            </div>
            <button
              onClick={() => setShowVersionSwitcher(false)}
              className="text-xs text-zinc-400 hover:text-white cursor-pointer"
            >
              收起 ✕
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 max-h-60 overflow-y-auto pr-1">
            {planBackups.map((bk: any) => (
              <div
                key={bk.id}
                className="p-3 rounded-xl bg-[#121215] border border-white/10 flex items-center justify-between gap-2 text-xs"
              >
                <div className="min-w-0">
                  <div className="font-bold text-white truncate">
                    历史快照：{bk.previous_plan_title || "原训练课表"}
                  </div>
                  <div className="text-[10px] text-zinc-400 truncate mt-0.5">
                    备份原因：{bk.action_label || "课表变更"} · {formatBeijingTime(bk.created_at, true)}
                  </div>
                </div>
                <button
                  onClick={() =>
                    handleRunnerSwitchOrRollbackPlan({
                      backupId: bk.id,
                      label: bk.previous_plan_title || "原训练课表",
                    })
                  }
                  disabled={rollingBackPlan}
                  className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 text-xs font-medium shrink-0 cursor-pointer"
                >
                  恢复此版本
                </button>
              </div>
            ))}

            {allPlans
              .filter((p: any) => p.status === "archived")
              .map((arc: any) => (
                <div
                  key={arc.id}
                  className="p-3 rounded-xl bg-[#121215] border border-white/10 flex items-center justify-between gap-2 text-xs"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-white truncate">{arc.title}</span>
                      {arc.source_label && (
                        <span className="px-1.5 py-0.2 rounded bg-white/5 border border-white/10 text-zinc-300 text-[9px] font-medium shrink-0">
                          {arc.source_label}
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-zinc-400 truncate mt-0.5">
                      历史归档方案 · {arc.weeks_count || 4}周周期 · 更新于 {String(arc.updated_at || "").slice(0, 10)}
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      handleRunnerSwitchOrRollbackPlan({
                        targetPlanId: arc.id,
                        label: arc.title,
                      })
                    }
                    disabled={rollingBackPlan}
                    className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 text-xs font-medium shrink-0 cursor-pointer"
                  >
                    切回此方案
                  </button>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* ── 🏆 Target Race Completed / A-Race Switch Recommendation Banner ── */}
      {plan && isTargetRaceCompleted && recommendedRace && (
        <div className="bg-gradient-to-r from-amber-500/10 via-purple-500/10 to-transparent border border-amber-500/30 rounded-3xl p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xl">
          <div className="flex items-start gap-3">
            <span className="text-3xl">🏆</span>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-amber-300">
                  原目标「{plan.target_race_name}」已顺利完赛！
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-200 border border-amber-500/30">
                  自动推荐聚焦下一核心 A 标
                </span>
              </div>
              <p className="text-xs text-zinc-300 mt-1 leading-relaxed">
                依据科学周期化备赛逻辑，您的下一个宏观备赛终极目标应锚定为核心 A 标 <strong className="text-purple-300">「{recommendedRace.name}」</strong>（{recommendedRace.race_type || "核心突破"} · {recommendedRace.race_date}）。中途其他 B/C 标赛事将作为实战代练自动融入新课表！
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setTargetRaceName(recommendedRace.name);
              if (recommendedRace.target_time) setTargetTime(recommendedRace.target_time);
              if (recommendedRace.race_date) setTargetDate(recommendedRace.race_date);
              if (recommendedRace.race_type) setRaceType(recommendedRace.race_type);
              setShowConfig(true);
            }}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-500 text-white shadow-lg shadow-purple-600/30 transition flex items-center justify-center gap-1.5 flex-shrink-0"
          >
            <Sparkles className="w-4 h-4" />
            切换并重新制定计划 ➔
          </button>
        </div>
      )}

      {/* ── Collapsible Plan Generation / Configuration Panel ── */}
      {(showConfig || !plan) && (
        <div className="bg-[#121215] border border-purple-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6 relative overflow-hidden">
          <div className="absolute -top-16 -right-16 w-48 h-48 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="flex items-center justify-between border-b border-white/5 pb-4">
            <div className="flex items-center gap-2">
              <Zap className="w-5 h-5 text-purple-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                设定您的专属训练目标与周期参数
              </h3>
            </div>
            <span className="text-xs text-purple-300 font-medium">
              系统将结合您的周岁年龄、当前 TSB 与近 18 个月比赛记录量身推演
            </span>
          </div>

          {/* Goal Type Tabs */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-300 block">训练周期核心性质</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setGoalType("race_prep")}
                className={`p-4 rounded-2xl border text-left transition relative flex items-start gap-3 ${
                  goalType === "race_prep"
                    ? "bg-purple-600/15 border-purple-500 text-white shadow-lg shadow-purple-500/10"
                    : "bg-[#18181c] border-white/5 text-zinc-400 hover:border-white/10 hover:text-zinc-200"
                }`}
              >
                <div className={`p-2 rounded-xl ${goalType === "race_prep" ? "bg-purple-600 text-white" : "bg-zinc-800 text-zinc-400"}`}>
                  <Trophy className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">针对目标赛事周期备战</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold">
                      Canova 专项哲学
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                    以指定比赛日为终点，构建基础期、专项准备期、特定耐力期与巅峰赛前减量期。
                  </p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setGoalType("fitness_maintenance")}
                className={`p-4 rounded-2xl border text-left transition relative flex items-start gap-3 ${
                  goalType === "fitness_maintenance"
                    ? "bg-purple-600/15 border-purple-500 text-white shadow-lg shadow-purple-500/10"
                    : "bg-[#18181c] border-white/5 text-zinc-400 hover:border-white/10 hover:text-zinc-200"
                }`}
              >
                <div className={`p-2 rounded-xl ${goalType === "fitness_maintenance" ? "bg-purple-600 text-white" : "bg-zinc-800 text-zinc-400"}`}>
                  <Mountain className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">非赛期专项体能维持</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-white/10 font-bold">
                      Daniels 基础构建
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                    暂无比赛时，针对性强化低心率有氧底座、乳酸门槛、越野爬坡抗阻或 VO2Max 速度储备。
                  </p>
                </div>
              </button>
            </div>
          </div>

          {/* If Race Prep: Inputs */}
          {goalType === "race_prep" ? (
            <div className="space-y-4 bg-[#18181c] p-4 sm:p-5 rounded-2xl border border-white/5">
              {/* Quick Select from Registered Races */}
              {userRaces.length > 0 && (
                <div className="space-y-2">
                  <span className="text-[11px] font-bold text-zinc-400">
                    🚩 从您已登记的赛历中快速套用（优先推荐 A 标核心赛事）：
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {userRaces.map((r: any) => {
                      const isA = r.priority == 1 || r.priority === "A" || r.priority === "1";
                      const isB = r.priority == 2 || r.priority === "B" || r.priority === "2";
                      const isDone = r.status === "completed" || r.is_completed;
                      const priorityBadge = isDone
                        ? "🏁 已完赛"
                        : isA
                        ? "⭐ A标核心"
                        : isB
                        ? "⚡ B标代练"
                        : "🏃 C标拉练";

                      return (
                        <button
                          key={r.id || r.name}
                          type="button"
                          disabled={isDone}
                          onClick={() => {
                            if (isDone) return;
                            setTargetRaceName(r.name);
                            if (r.target_time) setTargetTime(r.target_time);
                            if (r.race_date) setTargetDate(r.race_date);
                            if (r.race_type) setRaceType(r.race_type);
                          }}
                          className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition flex items-center gap-1.5 ${
                            isDone
                              ? "bg-white/[0.02] border-white/5 text-zinc-600 cursor-not-allowed line-through"
                              : targetRaceName === r.name
                              ? "bg-purple-600/30 border-purple-500 text-purple-200 shadow-sm"
                              : isA
                              ? "bg-amber-500/10 border-amber-500/30 text-amber-200 hover:border-amber-500/60"
                              : "bg-[#121215] border-white/10 text-zinc-400 hover:text-white"
                          }`}
                        >
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded ${
                              isDone
                                ? "bg-zinc-800 text-zinc-500"
                                : isA
                                ? "bg-amber-500/20 text-amber-300 font-bold"
                                : isB
                                ? "bg-sky-500/20 text-sky-300"
                                : "bg-zinc-800 text-zinc-400"
                            }`}
                          >
                            {priorityBadge}
                          </span>
                          <span>
                            {r.name} · {r.target_time || "目标"}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="text-xs text-zinc-400 block mb-1.5">目标比赛名称</label>
                  <input
                    type="text"
                    value={targetRaceName}
                    onChange={(e) => setTargetRaceName(e.target.value)}
                    placeholder="如: 上海马拉松 / 武功山 50K"
                    className="w-full bg-[#121215] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 block mb-1.5">目标完赛成绩</label>
                  <input
                    type="text"
                    value={targetTime}
                    onChange={(e) => setTargetTime(e.target.value)}
                    placeholder="如: 3:09:30 或 8:00:00"
                    className="w-full bg-[#121215] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 block mb-1.5">比赛日期 (可选)</label>
                  <input
                    type="date"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                    className="w-full bg-[#121215] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>
            </div>
          ) : (
            /* If Fitness Maintenance: Focus Options */
            <div className="space-y-3 bg-[#18181c] p-4 sm:p-5 rounded-2xl border border-white/5">
              <label className="text-xs font-bold text-zinc-400 block">
                2. 选择当前周期的专项强化方向 (Maintenance Focus)
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {maintenanceOptions.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setMaintenanceFocus(opt.id)}
                    className={`p-3.5 rounded-xl border text-left transition flex flex-col justify-between ${
                      maintenanceFocus === opt.id
                        ? "bg-emerald-600/20 border-emerald-500 text-white shadow-md shadow-emerald-950/20"
                        : "bg-[#121215] border-white/5 text-zinc-400 hover:border-white/15"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-white">{opt.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300">
                          {opt.tag}
                        </span>
                      </div>
                      <p className="text-[11px] text-zinc-400 mt-1.5 leading-relaxed font-light">
                        {opt.desc}
                      </p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Schedule Parameters */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div>
              <label className="text-xs text-zinc-400 block mb-1.5">计划总周数</label>
              <select
                value={weeksCount}
                onChange={(e) => setWeeksCount(parseInt(e.target.value))}
                className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500"
              >
                <option value={4}>4 周快速强化周期</option>
                <option value={6}>6 周稳固进阶周期</option>
                <option value={8}>8 周经典大周期 (推荐)</option>
                <option value={12}>12 周完整赛季备战</option>
                <option value={16}>16 周巅峰突破周期</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-zinc-400 block mb-1.5">每周跑步训练天数</label>
              <select
                value={daysPerWeek}
                onChange={(e) => setDaysPerWeek(parseInt(e.target.value))}
                className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500"
              >
                <option value={3}>3 天 / 周 (高效率紧凑型，适合大师组充分恢复)</option>
                <option value={4}>4 天 / 周 (经典平衡型，推荐大部分业余精英)</option>
                <option value={5}>5 天 / 周 (进阶高跑量，需配合良好睡眠)</option>
                <option value={6}>6 天 / 周 (专业高密度，大课与排酸穿插)</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-zinc-400 block mb-1.5">长距离大课偏好日</label>
              <select
                value={preferredLongRunDay}
                onChange={(e) => setPreferredLongRunDay(e.target.value)}
                className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500"
              >
                <option value="Sunday">周日 (经典长距离拉练日)</option>
                <option value="Saturday">周六 (周日排酸休整)</option>
              </select>
            </div>
          </div>

          {/* Goal Alignment Hint */}
          <div className="p-3 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-between text-xs text-purple-300">
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400 shrink-0" />
              <span>
                自定周跑量基准：<strong className="text-white">{userGoal?.weekly_target || 50} km/周</strong> (系统将自动以此为基准，波浪式规划各周负荷)
              </span>
            </div>
            <span className="text-[11px] text-purple-400/80 bg-purple-500/20 px-2 py-0.5 rounded-full font-bold">已自动锚定</span>
          </div>

          <div className="pt-2 flex items-center justify-end gap-3">
            {plan && (
              <button
                type="button"
                onClick={() => setShowConfig(false)}
                className="px-5 py-2.5 rounded-xl border border-white/10 text-xs text-zinc-400 hover:text-white"
              >
                取消
              </button>
            )}
            <button
              type="button"
              onClick={handleGeneratePlan}
              disabled={generating}
              className="px-6 py-3 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-xs transition shadow-lg shadow-purple-600/30 flex items-center gap-2"
            >
              {generating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  AI 耐力推演生成中 (整合18个月比赛与TSB)...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  生成科学定制训练课表
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── Active Training Plan View ── */}
      {plan && plan.schedule_data && (
        <div className="space-y-6">
          {/* Baseline Snapshot Pill Banner */}
          {plan.schedule_data.current_fitness_snapshot && (
            <div className="bg-[#121215] border border-white/[0.08] p-4 sm:p-5 rounded-3xl grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
              <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                <span className="text-[10px] text-zinc-400 block font-bold">跑者组别</span>
                <span className="text-sm font-black text-white">
                  {plan.schedule_data.current_fitness_snapshot.age ? (plan.schedule_data.current_fitness_snapshot.age >= 50 ? "大师组 (Masters)" : `${plan.schedule_data.current_fitness_snapshot.age} 岁`) : "—"}
                </span>
                <span className="text-[9px] text-zinc-500 block mt-0.5">
                  {plan.schedule_data.current_fitness_snapshot.age >= 50 ? "72-96h 充分恢复律" : "常规恢复"}
                </span>
              </div>

              <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                <span className="text-[10px] text-zinc-400 block font-bold">VO2Max 摄氧量</span>
                <span className="text-sm font-black text-purple-400">
                  {plan.schedule_data.current_fitness_snapshot.vo2max || "—"}
                </span>
                <span className="text-[9px] text-zinc-500 block mt-0.5">
                  {plan.schedule_data.current_fitness_snapshot.vo2max_source === "watch"
                    ? "手表生理实测数据"
                    : "手表实测 / 生理基准"}
                </span>
              </div>

              <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                <span className="text-[10px] text-zinc-400 block font-bold">体能 CTL / 疲劳 ATL</span>
                <span className="text-sm font-black text-cyan-400">
                  {plan.schedule_data.current_fitness_snapshot.ctl || 0} / {plan.schedule_data.current_fitness_snapshot.atl || 0}
                </span>
                <span className="text-[9px] text-zinc-500 block mt-0.5">Banister EWMA 42天</span>
              </div>

              <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                <span className="text-[10px] text-zinc-400 block font-bold">状态平衡 TSB</span>
                <span className={`text-sm font-black ${plan.schedule_data.current_fitness_snapshot.tsb >= 0 ? "text-emerald-400" : "text-purple-400"}`}>
                  {plan.schedule_data.current_fitness_snapshot.tsb > 0 ? `+${plan.schedule_data.current_fitness_snapshot.tsb}` : plan.schedule_data.current_fitness_snapshot.tsb}
                </span>
                <span className="text-[9px] text-zinc-500 block mt-0.5">即时吸收状态</span>
              </div>

              <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                <span className="text-[10px] text-zinc-400 block font-bold">18个月最长实跑</span>
                <span className="text-sm font-black text-amber-400">
                  {plan.schedule_data.current_fitness_snapshot.max_long_run_18m_km || "—"} km
                </span>
                <span className="text-[9px] text-zinc-500 block mt-0.5">实战耐力上限</span>
              </div>

              <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                <span className="text-[10px] text-zinc-400 block font-bold">18个月实战比赛</span>
                <span className="text-sm font-black text-emerald-400">
                  {plan.schedule_data.current_fitness_snapshot.recent_races_count || 0} 次
                </span>
                <span className="text-[9px] text-zinc-500 block mt-0.5">完赛打卡经验</span>
              </div>
            </div>
          )}

          {/* Coach Verified & Published Banner */}
          {(plan.review_status === "published" || plan.coach_review_note || plan.schedule_data?.coach_review) && (
            <div className="p-5 rounded-3xl bg-emerald-950/25 border border-emerald-500/30 text-xs space-y-2 shadow-lg shadow-emerald-950/10">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="font-bold text-emerald-300 flex items-center gap-2 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>
                    🧢 跑团教练【{plan.reviewed_by_name || plan.schedule_data?.coach_review?.reviewed_by_name || "认证教练"}】已审核并发布本计划
                  </span>
                </div>
                {(plan.reviewed_at || plan.schedule_data?.coach_review?.reviewed_at) && (
                  <span className="text-[11px] text-emerald-400/70 font-mono">
                    发布于 {formatBeijingTime(plan.reviewed_at || plan.schedule_data?.coach_review?.reviewed_at, true)}
                  </span>
                )}
              </div>
              {(plan.coach_review_note || plan.schedule_data?.coach_review?.coach_review_note) && (
                <p className="text-zinc-200 leading-relaxed bg-black/30 rounded-2xl p-3.5 border border-emerald-500/20">
                  <strong className="text-emerald-400">👨‍🏫 教练执行叮嘱：</strong>
                  {plan.coach_review_note || plan.schedule_data?.coach_review?.coach_review_note}
                </p>
              )}
            </div>
          )}

          {/* Goal Summary Quote & Macro Roadmap */}
          {(plan.overview_summary || plan.schedule_data?.macro_roadmap) && (
            <div className="p-5 rounded-3xl bg-purple-950/20 border border-purple-500/20 text-xs space-y-2.5">
              {plan.overview_summary && (
                <div>
                  <div className="font-bold text-purple-300 flex items-center gap-2 mb-1">
                    <Target className="w-4 h-4 text-purple-400" />
                    Canova 周期战术设计综述：
                  </div>
                  <p className="text-zinc-300 leading-relaxed font-light">
                    {plan.overview_summary}
                  </p>
                </div>
              )}
              {plan.schedule_data?.macro_roadmap && (
                <div className="bg-black/30 border border-purple-500/20 rounded-2xl p-3.5">
                  <div className="font-bold text-purple-300 mb-1">🗺️ 阶段宏观周期大纲 (教练规划)：</div>
                  <p className="text-zinc-200 whitespace-pre-wrap leading-relaxed">
                    {String(plan.schedule_data.macro_roadmap)
                      .replace(/\bW(\d+)-W(\d+)\b/g, "第$1-$2周")
                      .replace(/\bW(\d+)\b/g, "第$1周")}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* ── Week Tabs Bar ── */}
          <div className="bg-[#121215] border border-white/[0.08] p-3 sm:p-4 rounded-3xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
              {currentWeeks.map((w: any) => {
                const isActive = w.week_index === selectedWeekIdx;
                const hasRace = (w.days || []).some((d: any) => d.workout_type === "race");
                return (
                  <button
                    key={w.week_index}
                    onClick={() => setSelectedWeekIdx(w.week_index)}
                    className={`shrink-0 px-4 py-2.5 rounded-2xl border text-xs font-bold transition flex flex-col items-start min-w-[110px] relative cursor-pointer ${
                      isActive
                        ? "bg-purple-600 text-white border-purple-500 shadow-lg shadow-purple-600/30"
                        : hasRace
                        ? "bg-rose-950/20 border-rose-500/30 text-rose-200 hover:border-rose-500/50"
                        : "bg-[#18181c] border-white/5 text-zinc-400 hover:text-white hover:border-white/15"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 w-full justify-between">
                      <span className="flex items-center gap-1">
                        <span>第 {w.week_index} 周</span>
                        {(plan?.current_week_index || computeCurrentWeekIndex(plan)) === w.week_index && (
                          <span className={`text-[9px] px-1 py-0.2 rounded font-bold ${
                            isActive ? "bg-white/20 text-white" : "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                          }`}>
                            本周
                          </span>
                        )}
                      </span>
                      {hasRace && (
                        <span className="text-[9px] px-1.5 py-0.2 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30">
                          🏁 实战
                        </span>
                      )}
                    </div>
                    <span className={`text-[10px] font-normal mt-0.5 ${isActive ? "text-purple-100" : hasRace ? "text-rose-300/80" : "text-zinc-500"}`}>
                      {w.weekly_mileage_km || 0} km · {w.phase ? w.phase.split(" ")[0] : "训练"}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-1 bg-[#18181c] p-1 rounded-xl border border-white/10 shrink-0 self-start sm:self-auto">
              <button
                onClick={() => setWeekViewMode("w19_table")}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer ${
                  weekViewMode === "w19_table"
                    ? "bg-[#FC4C02] text-white shadow"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                📊 周训练与体感表
              </button>
              <button
                onClick={() => setWeekViewMode("cards")}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer ${
                  weekViewMode === "cards"
                    ? "bg-purple-600 text-white shadow"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                🗓️ 7日卡片视图
              </button>
            </div>
          </div>

          {/* ── Active Week Detailed View ── */}
          {activeWeek && (
            <div className="space-y-4">
              {/* Week Header Card */}
              <div className="bg-[#121215] border border-white/[0.08] p-5 sm:p-6 rounded-3xl space-y-3.5">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-base font-black text-white">
                        {activeWeek.week_title || `第 ${activeWeek.week_index} 周`}
                      </h3>
                      <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                        {activeWeek.phase || "专项训练"}
                      </span>

                      {/* Goal Alignment Capsule */}
                      {(() => {
                        const wTarget = Number(userGoal?.weekly_target) || 50;
                        const wPlan = Number(activeWeek.weekly_mileage_km) || 0;
                        const ratio = Math.round((wPlan / wTarget) * 100);
                        const hasRace = (activeWeek.days || []).some((d: any) => d.workout_type === "race");
                        const isDownWeek = (activeWeek.phase || "").includes("减量") || (activeWeek.week_title || "").includes("减量");

                        if (hasRace) {
                          return (
                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1.5">
                              <span>🏁 实战周</span>
                              <span className="font-normal text-[10px] text-rose-300/80">计划 {wPlan}k / 目标 {wTarget}k</span>
                            </span>
                          );
                        }
                        if (isDownWeek) {
                          return (
                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30 flex items-center gap-1.5">
                              <span>🌊 减量超量恢复</span>
                              <span className="font-normal text-[10px] text-sky-300/80">计划 {wPlan}k / 目标 {wTarget}k ({ratio}%)</span>
                            </span>
                          );
                        }
                        if (ratio >= 88 && ratio <= 112) {
                          return (
                            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
                              <span>🎯 科学对齐</span>
                              <span className="font-normal text-[10px] text-emerald-300/80">计划 {wPlan}k / 目标 {wTarget}k ({ratio}%)</span>
                            </span>
                          );
                        }
                        return (
                          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5">
                            <span>⚡ 渐进爬坡</span>
                            <span className="font-normal text-[10px] text-amber-300/80">计划 {wPlan}k / 目标 {wTarget}k ({ratio}%)</span>
                          </span>
                        );
                      })()}
                    </div>
                    <p className="text-xs text-zinc-400 mt-1 flex items-center gap-1.5">
                      <span>🎯 本周核心重点：</span>
                      <span className="text-zinc-200">{activeWeek.key_focus}</span>
                    </p>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 flex-wrap">
                    <div className="flex items-center gap-3.5 bg-[#18181c] px-3.5 py-2 rounded-2xl border border-white/5 shrink-0">
                      <div className="text-right">
                        <span className="text-[10px] text-zinc-500 block font-bold">本周总跑量</span>
                        <span className="text-sm font-black text-white">{activeWeek.weekly_mileage_km || 0} km</span>
                      </div>
                      <div className="w-px h-6 bg-white/10" />
                      <div className="text-right">
                        <span className="text-[10px] text-zinc-500 block font-bold">本周已执行</span>
                        <span className="text-sm font-black text-emerald-400">
                          {activeWeek.actual_mileage_km || 0} km ({activeWeek.compliance_rate || 0}%)
                        </span>
                      </div>
                      <div className="w-px h-6 bg-white/10" />
                      <div className="text-right">
                        <span className="text-[10px] text-zinc-500 block font-bold">力量训练</span>
                        <span className="text-sm font-black text-purple-400">
                          {activeWeek.strength_sessions_done || 0} 次
                        </span>
                      </div>
                    </div>

                    {/* Sync to Goals Button */}
                    <button
                      onClick={handleSyncToGoals}
                      disabled={syncingGoal}
                      title="将当前训练计划的平均跑量与各月跑量同步为我的个人周/月目标"
                      className="px-3.5 py-2 rounded-2xl bg-gradient-to-r from-purple-600/30 to-indigo-600/30 hover:from-purple-600/50 hover:to-indigo-600/50 border border-purple-500/30 text-purple-200 text-xs font-bold transition flex items-center gap-1.5 shadow-sm active:scale-95 disabled:opacity-50 cursor-pointer"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${syncingGoal ? "animate-spin" : ""}`} />
                      <span>{syncingGoal ? "同步中..." : "同步至我的目标"}</span>
                    </button>
                  </div>
                </div>

                {/* Sync Success Notification */}
                {syncSuccessMsg && (
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl flex items-center justify-between gap-2 text-emerald-300 text-xs animate-in fade-in duration-200">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                      <span>{syncSuccessMsg}</span>
                    </div>
                    <button onClick={() => setSyncSuccessMsg("")} className="text-emerald-400/60 hover:text-emerald-200">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
              </div>

              {/* ── VIEW 1: W19 Standard Weekly Plan & Self-Report Table ── */}
              {weekViewMode === "w19_table" ? (
                <div className="bg-[#121215] border border-white/10 rounded-3xl overflow-hidden shadow-xl">
                  <div className="bg-[#191922] px-5 py-3 border-b border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="px-2 py-0.5 rounded bg-[#FC4C02]/20 text-[#FC4C02] font-black">
                        第 {activeWeek.week_index} 周 · 训练记录与体感反馈表
                      </span>
                      <span className="text-zinc-300 font-semibold">
                        {activeWeek.summary_banner_text || `周跑量：${activeWeek.weekly_mileage_km || 0}公里。执行：${activeWeek.actual_mileage_km || 0}公里，完成度${activeWeek.compliance_rate || 0}%；力量：${activeWeek.strength_sessions_done || 0}次。`}
                      </span>
                    </div>
                    <span className="text-[11px] text-zinc-400">
                      💡 点击任意一行可填报当日 RPE (1-10)、训练自我感受、晨起身体指标或调休对换课表
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-[#16161d] text-zinc-400 border-b border-white/10 text-[11px]">
                          <th className="py-2.5 px-3 font-bold w-24">星期 / 日期</th>
                          <th className="py-2.5 px-3 font-bold min-w-[210px]">训练计划 (教练处方)</th>
                          <th className="py-2.5 px-3 font-bold w-44">
                            身体指标
                            <span className="block text-[9px] text-zinc-500 font-normal">HRV / 静心 / 呼吸 / 压力(0-21)</span>
                          </th>
                          <th className="py-2.5 px-2.5 font-bold w-20 text-center">恢复%</th>
                          <th className="py-2.5 px-3 font-bold min-w-[170px]">计划执行情况</th>
                          <th className="py-2.5 px-2 font-bold w-16 text-center">RPE 10</th>
                          <th className="py-2.5 px-3 font-bold min-w-[180px]">备注 (自我感受 / 教练批注)</th>
                          <th className="py-2.5 px-3 font-bold w-28 text-right">打卡 / 填报</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {(activeWeek.days || []).map((day: any, dIdx: number) => {
                          const isRest = day.workout_type === "rest" || Number(day.distance_km || 0) <= 0;
                          const recPct = day.recovery_pct != null ? Number(day.recovery_pct) : null;
                          const recColor =
                            recPct == null
                              ? "bg-white/5 text-zinc-500"
                              : recPct >= 67
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                              : recPct >= 34
                              ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                              : "bg-rose-500/25 text-rose-300 border border-rose-500/40";
                          const lowHrv = Boolean(day.low_hrv_alert) || (day.hrv != null && Number(day.hrv) <= 32);

                          return (
                            <tr
                              key={dIdx}
                              onClick={() => handleOpenEditModal(activeWeek.week_index, dIdx, day)}
                              className="hover:bg-white/[0.03] transition cursor-pointer"
                            >
                              <td className="py-3 px-3 align-top">
                                <div className="font-bold text-white">{day.day_of_week}</div>
                                <div className="text-[10px] text-zinc-500 font-mono">{day.date ? day.date.slice(5) : ""}</div>
                                {day.swapped_from && (
                                  <span className="inline-block mt-1 px-1.5 py-0.5 rounded text-[9px] bg-blue-500/20 text-blue-300">
                                    🔁 与{day.swapped_from}对换
                                  </span>
                                )}
                              </td>

                              <td className="py-3 px-3 align-top">
                                <div className="font-bold text-white flex items-center gap-1.5 flex-wrap">
                                  <span>{day.title}</span>
                                  {!isRest && (
                                    <span className="text-[#FC4C02] font-mono text-xs">{day.distance_km}km</span>
                                  )}
                                </div>
                                {day.description && (
                                  <div className="text-[11px] text-zinc-400 mt-0.5 leading-snug">{day.description}</div>
                                )}
                              </td>

                              <td className={`py-3 px-3 align-top font-mono text-[11px] ${lowHrv ? "bg-rose-500/10" : ""}`}>
                                {day.biometrics_text ? (
                                  <span className={lowHrv ? "text-rose-300 font-bold" : "text-zinc-200"}>
                                    {day.biometrics_text}
                                  </span>
                                ) : (
                                  <span className="text-zinc-600">点击填报晨起指标</span>
                                )}
                              </td>

                              <td className="py-3 px-2.5 align-top text-center">
                                {recPct != null ? (
                                  <span className={`inline-block px-2 py-0.5 rounded-lg text-[11px] font-black font-mono ${recColor}`}>
                                    {recPct}%
                                  </span>
                                ) : (
                                  <span className="text-zinc-600">—</span>
                                )}
                              </td>

                              <td className="py-3 px-3 align-top">
                                {day.actual_execution_text ? (
                                  <div className="font-mono text-emerald-300 font-semibold">{day.actual_execution_text}</div>
                                ) : day.completed ? (
                                  <div className="font-mono text-emerald-400">
                                    ✅ 已完成 {day.actual_distance_km || day.distance_km}km
                                  </div>
                                ) : isRest ? (
                                  <span className="text-zinc-500">跑休</span>
                                ) : (
                                  <span className="text-zinc-500">待执行 / 点击录入</span>
                                )}
                              </td>

                              <td className="py-3 px-2 align-top text-center">
                                {day.rpe != null ? (
                                  <span
                                    className={`inline-block px-2 py-0.5 rounded-lg font-mono font-black text-xs ${
                                      Number(day.rpe) >= 8
                                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                        : Number(day.rpe) >= 6
                                        ? "bg-amber-500/20 text-amber-300"
                                        : "bg-emerald-500/15 text-emerald-300"
                                    }`}
                                  >
                                    {day.rpe}
                                  </span>
                                ) : (
                                  <span className="text-zinc-600">—</span>
                                )}
                              </td>

                              <td className="py-3 px-3 align-top space-y-1">
                                {day.feeling_tag && (
                                  <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 mr-1">
                                    {day.feeling_tag}
                                  </span>
                                )}
                                {day.athlete_notes ? (
                                  <div className="text-[11px] text-amber-200 bg-amber-500/10 border border-amber-500/20 rounded px-2 py-1">
                                    💬 感受: {day.athlete_notes}
                                  </div>
                                ) : !day.feeling_tag && !(day.workout_photos && day.workout_photos.length > 0) ? (
                                  <span className="text-zinc-600 text-[11px]">点击填写感受/备注/照片...</span>
                                ) : null}
                                {day.workout_photos && day.workout_photos.length > 0 && (
                                  <div className="flex items-center gap-1.5 flex-wrap pt-0.5" onClick={(e) => e.stopPropagation()}>
                                    {day.workout_photos.map((pUrl: string, pIdx: number) => (
                                      <a
                                        key={pIdx}
                                        href={pUrl}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="block w-10 h-10 rounded-lg overflow-hidden border border-white/15 hover:border-emerald-400"
                                      >
                                        <img src={pUrl} alt="打卡照片" className="w-full h-full object-cover" />
                                      </a>
                                    ))}
                                  </div>
                                )}
                                {day.coach_notes && (
                                  <div className="text-[11px] text-purple-200 bg-purple-500/10 border border-purple-500/20 rounded px-2 py-1">
                                    🧢 教练: {day.coach_notes}
                                  </div>
                                )}
                              </td>

                              <td className="py-3 px-3 align-top text-right" onClick={(e) => e.stopPropagation()}>
                                <div className="flex items-center justify-end gap-1">
                                  <button
                                    type="button"
                                    onClick={() => handleToggleQuickComplete(activeWeek.week_index, dIdx, day)}
                                    className={`px-2 py-1 rounded-lg text-[10px] font-bold border transition cursor-pointer ${
                                      day.completed
                                        ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                                        : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
                                    }`}
                                  >
                                    {day.completed ? "✓已卡" : "打卡"}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleOpenEditModal(activeWeek.week_index, dIdx, day)}
                                    className="px-2 py-1 rounded-lg bg-[#FC4C02]/20 hover:bg-[#FC4C02]/35 text-[#FC4C02] border border-[#FC4C02]/30 text-[10px] font-bold cursor-pointer"
                                  >
                                    {day.completed ? "感受/照片" : "体感/调休"}
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                /* ── VIEW 2: Daily 7-day Workout Cards Grid ── */
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-3">
                  {(activeWeek.days || []).map((day: any, dIdx: number) => {
                    const typeMeta = workoutTypeStyles[day.workout_type] || workoutTypeStyles.easy_run;
                    const isRest = day.workout_type === "rest";
                    const todayStr = new Date().toLocaleDateString("en-CA");
                    const isPast = Boolean(day.date && day.date < todayStr);
                    const isMissed = Boolean(day.is_missed ?? (isPast && !day.completed && !isRest && (day.distance_km || 0) > 0));

                    return (
                      <div
                        key={dIdx}
                        className={`bg-[#121215] border rounded-3xl p-4 flex flex-col justify-between transition-all hover:border-purple-500/40 ${
                          day.completed
                            ? "border-emerald-500/30 bg-emerald-950/5"
                            : isMissed
                            ? "border-rose-500/40 bg-rose-950/15 shadow-[0_0_15px_rgba(244,63,94,0.08)]"
                            : typeMeta.border
                        }`}
                      >
                        <div className="space-y-3">
                          {/* Day & Date Header */}
                          <div className="flex items-center justify-between border-b border-white/5 pb-2">
                            <div>
                              <span className="text-xs font-black text-white block">
                                {day.day_of_week}
                              </span>
                              <span className="text-[10px] text-zinc-500 block">
                                {day.date ? day.date.substring(5) : ""}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 flex-wrap justify-end">
                              {day.rpe != null && (
                                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300">
                                  RPE {day.rpe}
                                </span>
                              )}
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${typeMeta.badge}`}>
                                {typeMeta.label}
                              </span>
                            </div>
                          </div>

                          {/* Title & Distance */}
                          <div>
                            <div className="text-xs font-bold text-zinc-200 line-clamp-2 leading-snug">
                              {day.title}
                            </div>
                            {!isRest && (
                              <div className="mt-1.5 flex items-baseline gap-1">
                                <span className="text-base font-black text-white tracking-tight">
                                  {day.distance_km || 0}
                                </span>
                                <span className="text-[10px] text-zinc-400">km</span>
                              </div>
                            )}
                          </div>

                          {/* Description */}
                          <p className="text-[11px] text-zinc-400 leading-relaxed font-light line-clamp-3">
                            {day.description}
                          </p>

                          {/* Athlete Self-Feel, Photos & Coach Notes */}
                          {day.feeling_tag && (
                            <div className="inline-block px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                              {day.feeling_tag}
                            </div>
                          )}
                          {day.athlete_notes && (
                            <div className="bg-amber-500/10 border border-amber-500/20 p-2 rounded-xl text-[10px] text-amber-200">
                              💬 自我感受: {day.athlete_notes}
                            </div>
                          )}
                          {day.workout_photos && day.workout_photos.length > 0 && (
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {day.workout_photos.map((pUrl: string, pIdx: number) => (
                                <a
                                  key={pIdx}
                                  href={pUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="block w-11 h-11 rounded-lg overflow-hidden border border-white/15 hover:border-emerald-400"
                                >
                                  <img src={pUrl} alt="打卡照片" className="w-full h-full object-cover" />
                                </a>
                              ))}
                            </div>
                          )}
                          {day.coach_notes && (
                            <div className="bg-purple-500/10 border border-purple-500/20 p-2 rounded-xl text-[10px] text-purple-200">
                              👨‍🏫 教练批注: {day.coach_notes}
                            </div>
                          )}
                        </div>

                        {/* Card Footer Actions */}
                        <div className="pt-3 border-t border-white/5 mt-3 flex items-center justify-between gap-1">
                          <button
                            type="button"
                            onClick={() => handleToggleQuickComplete(activeWeek.week_index, dIdx, day)}
                            className={`flex-1 py-1 px-2 rounded-xl text-[10px] font-bold border transition flex items-center justify-center gap-1 cursor-pointer ${
                              day.completed
                                ? "bg-emerald-500/20 border-emerald-500 text-emerald-300"
                                : "bg-[#18181c] border-white/10 text-zinc-400 hover:text-white"
                            }`}
                          >
                            {day.completed ? "✓ 已打卡" : "打卡"}
                          </button>

                          <button
                            type="button"
                            onClick={() => handleOpenEditModal(activeWeek.week_index, dIdx, day)}
                            className="px-2 py-1 rounded-xl text-[10px] border border-white/10 text-zinc-300 hover:text-white hover:border-purple-500 bg-[#18181c] transition cursor-pointer"
                          >
                            {day.completed ? "📝 感受/照片" : "📝 体感/调休"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* ── W19 Weekly Summary & Injury Self-Report Box (周小结 & 伤痛报备) ── */}
              <div className="bg-[#121215] border border-white/10 rounded-3xl p-5 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-3">
                  <div>
                    <h4 className="text-sm font-black text-white flex items-center gap-2">
                      📝 第 {activeWeek.week_index} 周 · 周小结、伤痛上报与出行请假报备
                    </h4>
                    <p className="text-[11px] text-zinc-400 mt-0.5">
                      填写后跑团教练将在后台实时收到提醒，并结合您的周体感与伤痛为您滚动制定下一周课表
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleSaveRunnerWeekSummary}
                    disabled={savingWeekSummary}
                    className="px-4 py-2 rounded-xl bg-gradient-to-r from-[#FC4C02] to-orange-600 hover:from-[#ff5c16] hover:to-orange-500 text-white text-xs font-black shadow-md transition cursor-pointer disabled:opacity-50"
                  >
                    {savingWeekSummary ? "保存提交中..." : "💾 提交本周小结与伤痛给教练"}
                  </button>
                </div>

                {activeWeek.coach_weekly_diagnosis && (
                  <div className="p-3.5 rounded-2xl bg-purple-950/25 border border-purple-500/30 text-xs text-purple-200">
                    <strong className="text-purple-300">🧢 教练本周复盘与下周导向：</strong>
                    {activeWeek.coach_weekly_diagnosis}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                  <div>
                    <label className="text-zinc-400 block mb-1">🚨 伤痛部位与疼痛感上报</label>
                    <input
                      type="text"
                      value={weekInjuryNote}
                      onChange={(e) => setWeekInjuryNote(e.target.value)}
                      placeholder="无伤痛填“无”，如有如：右脚跟腱轻微酸胀"
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-white outline-none focus:border-rose-500"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="text-zinc-400 block mb-1">💬 队员本周训练自我小结</label>
                    <input
                      type="text"
                      value={weekAthleteSummary}
                      onChange={(e) => setWeekAthleteSummary(e.target.value)}
                      placeholder="如：本周间歇课完成顺利，周末长距离后半程稍微掉速"
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-white outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                  <div>
                    <label className="text-zinc-400 block mb-1">✈️ 下周出差/请假/比赛报备</label>
                    <input
                      type="text"
                      value={weekTravelNote}
                      onChange={(e) => setWeekTravelNote(e.target.value)}
                      placeholder="如：下周三至周五出差，仅能晨跑"
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-white outline-none focus:border-purple-500"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Runner Daily RPE, Biometrics, Day-Swap & Workout Edit Modal ── */}
      {editingModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#18181c] border border-white/10 rounded-3xl max-w-xl w-full p-6 space-y-4 shadow-2xl relative max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <div className="flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-[#FC4C02]" />
                <h4 className="text-sm font-black text-white">
                  训练执行打卡 · 主观疲劳度 (RPE) · 调休对换 (第 {editWeekIdx} 周)
                </h4>
              </div>
              <button
                onClick={() => setEditingModalOpen(false)}
                className="p-1.5 rounded-xl text-zinc-400 hover:text-white bg-[#121215] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3.5 text-xs">
              {/* Section 1: Feeling Tag, RPE 1-10, Notes & Workout Photos */}
              <div className="bg-[#121215] border border-[#FC4C02]/30 rounded-2xl p-3.5 space-y-3">
                <div>
                  <label className="text-emerald-300 font-bold block mb-1.5">
                    😊 当日训练感受标签
                  </label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {PLAN_FEELING_TAGS.map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => setEditFeelingTag(editFeelingTag === tag ? "" : tag)}
                        className={`py-1.5 px-2 rounded-xl font-bold text-xs border transition cursor-pointer ${
                          editFeelingTag === tag
                            ? "bg-emerald-500/20 border-emerald-500 text-emerald-300"
                            : "bg-white/5 text-zinc-300 border-white/10 hover:text-white"
                        }`}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-zinc-200 font-bold block mb-1.5">
                    🔥 当日训练主观疲劳度 RPE (1=极轻松 ~ 10=极限力竭)
                  </label>
                  <div className="grid grid-cols-10 gap-1">
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => (
                      <button
                        key={num}
                        type="button"
                        onClick={() => setEditRpe(editRpe === String(num) ? "" : String(num))}
                        className={`py-1.5 rounded-lg font-mono font-black text-xs border transition cursor-pointer ${
                          Number(editRpe) === num
                            ? num >= 8
                              ? "bg-rose-500 text-white border-rose-400"
                              : num >= 5
                              ? "bg-amber-500 text-black border-amber-400"
                              : "bg-emerald-500 text-black border-emerald-400"
                            : "bg-white/5 text-zinc-400 border-white/10 hover:text-white"
                        }`}
                      >
                        {num}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-zinc-400 block mb-1">🏃 计划执行情况 (实跑/力量记录)</label>
                    <input
                      type="text"
                      value={editExecutionText}
                      onChange={(e) => setEditExecutionText(e.target.value)}
                      placeholder="如: 15km*602, hr132 或 慢跑4.3km+身训2组"
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-white font-mono focus:outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                  <div>
                    <label className="text-zinc-400 block mb-1">💬 备注 (训练自我感受)</label>
                    <input
                      type="text"
                      value={editAthleteNotes}
                      onChange={(e) => setEditAthleteNotes(e.target.value)}
                      placeholder="如: 体感轻快 / 小腿微酸 / 天气闷热掉速"
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                </div>

                {/* Workout Photos Uploader */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-sky-300 font-bold">
                      📸 训练打卡照片（最多 3 张，小程序与网页同步）
                    </label>
                    <span className="text-zinc-400">
                      {editWorkoutPhotos.length + editNewPhotosBase64.length}/3
                    </span>
                  </div>
                  <div className="flex items-center gap-2.5 flex-wrap">
                    {editWorkoutPhotos.map((url, idx) => (
                      <div
                        key={`saved-${idx}`}
                        className="relative w-16 h-16 rounded-xl overflow-hidden border border-white/15"
                      >
                        <img src={url} alt="已上传" className="w-full h-full object-cover" />
                        <button
                          type="button"
                          onClick={() =>
                            setEditWorkoutPhotos((prev) => prev.filter((_, i) => i !== idx))
                          }
                          className="absolute top-1 right-1 w-4 h-4 rounded-full bg-black/75 text-white text-[9px] flex items-center justify-center cursor-pointer"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                    {editNewPhotosBase64.map((b64, nIdx) => (
                      <div
                        key={`new-${nIdx}`}
                        className="relative w-16 h-16 rounded-xl overflow-hidden border border-emerald-500/40"
                      >
                        <img src={b64} alt="待上传" className="w-full h-full object-cover" />
                        <button
                          type="button"
                          onClick={() =>
                            setEditNewPhotosBase64((prev) => prev.filter((_, i) => i !== nIdx))
                          }
                          className="absolute top-1 right-1 w-4 h-4 rounded-full bg-black/75 text-white text-[9px] flex items-center justify-center cursor-pointer"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                    {editWorkoutPhotos.length + editNewPhotosBase64.length < 3 && (
                      <label className="w-16 h-16 rounded-xl bg-[#18181c] border border-dashed border-white/25 hover:border-emerald-400 flex flex-col items-center justify-center gap-0.5 cursor-pointer transition">
                        <span className="text-base">📷</span>
                        <span className="text-[9px] text-zinc-400 font-bold">添加照片</span>
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          onChange={handlePlanPhotoUploadChange}
                          className="hidden"
                        />
                      </label>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between flex-wrap gap-2 pt-1">
                  <label className="flex items-center gap-2 text-zinc-200 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editCompleted}
                      onChange={(e) => setEditCompleted(e.target.checked)}
                      className="rounded bg-[#18181c] border-white/10 text-emerald-500"
                    />
                    <span className="font-bold">✅ 标记今日跑步课表已完成</span>
                  </label>

                  <label className="flex items-center gap-2 text-purple-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editStrengthDone}
                      onChange={(e) => setEditStrengthDone(e.target.checked)}
                      className="rounded bg-[#18181c] border-white/10 text-purple-500"
                    />
                    <span className="font-bold">💪 今日已完成力量/核心训练</span>
                  </label>
                </div>
              </div>

              {/* Section 2: Morning Biometrics & Day Swap */}
              <div className="bg-[#121215] border border-white/10 rounded-2xl p-3.5 space-y-2.5">
                <div className="font-bold text-zinc-300">💓 晨起身体指标 (HRV / 静息心率 / 呼吸 / 压力 / 恢复%) & 调休对换</div>
                <div className="grid grid-cols-5 gap-2">
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">HRV (ms)</label>
                    <input
                      type="number"
                      value={editHrv}
                      onChange={(e) => setEditHrv(e.target.value)}
                      placeholder="39"
                      className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2 py-1.5 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">静心 (bpm)</label>
                    <input
                      type="number"
                      value={editRestingHr}
                      onChange={(e) => setEditRestingHr(e.target.value)}
                      placeholder="50"
                      className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2 py-1.5 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">呼吸率</label>
                    <input
                      type="number"
                      step="0.1"
                      value={editRespRate}
                      onChange={(e) => setEditRespRate(e.target.value)}
                      placeholder="14.2"
                      className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2 py-1.5 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">压力(0-21)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={editStrainScore}
                      onChange={(e) => setEditStrainScore(e.target.value)}
                      placeholder="10.2"
                      className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2 py-1.5 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-zinc-400 block mb-1">恢复%</label>
                    <input
                      type="number"
                      value={editRecoveryPct}
                      onChange={(e) => setEditRecoveryPct(e.target.value)}
                      placeholder="78"
                      className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2 py-1.5 text-white font-mono"
                    />
                  </div>
                </div>

                <div className="pt-1">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <label className="text-[11px] text-blue-300">
                      🔁 临时有事调休？与本周其他天对换课表:
                    </label>
                    {editIsSwapped && (
                      <button
                        type="button"
                        onClick={handleUndoSwapWorkout}
                        disabled={savingWorkout}
                        className="px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-[11px] font-bold transition cursor-pointer"
                      >
                        ↩️ 取消对换 · 恢复原课表
                      </button>
                    )}
                  </div>
                  <select
                    value={editSwapDayIdx}
                    onChange={(e) => setEditSwapDayIdx(Number(e.target.value))}
                    className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-1.5 text-white"
                  >
                    <option value={-1}>不对换课表</option>
                    {editIsSwapped && (
                      <option value={-2}>↩️ 取消对换 · 恢复原本课表</option>
                    )}
                    {["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((lbl, idx) =>
                      idx !== editDayIdx ? (
                        <option key={idx} value={idx}>
                          与 {lbl} 对换课表
                        </option>
                      ) : null
                    )}
                  </select>
                </div>
              </div>

              {/* Section 3: Workout Prescription Details */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-zinc-400 block mb-1">课目类型</label>
                  <select
                    value={editWorkoutType}
                    onChange={(e) => setEditWorkoutType(e.target.value)}
                    className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="easy_run">轻松跑 (Zone 2)</option>
                    <option value="tempo">门槛跑 (Tempo / LT2)</option>
                    <option value="interval">间歇跑 (Interval / VO2Max)</option>
                    <option value="long_run">长距离 (Long Progression)</option>
                    <option value="trail_climb">越野爬坡抗阻 (Trail D+)</option>
                    <option value="cross_training">交叉力量 (Cross Training)</option>
                    <option value="race">🏁 实战比赛日 (Race Day)</option>
                    <option value="rest">完全休息 (Rest)</option>
                  </select>
                </div>

                <div>
                  <label className="text-zinc-400 block mb-1">计划跑量 (km)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={editDistanceKm}
                    onChange={(e) => setEditDistanceKm(e.target.value)}
                    className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-zinc-400 block mb-1">训练课标题</label>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
                <div>
                  <label className="text-zinc-400 block mb-1">目标配速区间</label>
                  <input
                    type="text"
                    value={editTargetPace}
                    onChange={(e) => setEditTargetPace(e.target.value)}
                    placeholder="如: 5:15 - 5:25 /km"
                    className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-white/5">
              <button
                type="button"
                onClick={() => setEditingModalOpen(false)}
                className="px-4 py-2 rounded-xl border border-white/10 text-xs text-zinc-400 hover:text-white cursor-pointer"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSaveWorkout}
                disabled={savingWorkout}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-[#FC4C02] to-orange-600 hover:from-[#ff5c16] hover:to-orange-500 text-white font-black text-xs transition shadow-lg flex items-center gap-1.5 cursor-pointer"
              >
                {savingWorkout ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    保存中...
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    保存打卡与体感记录
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
