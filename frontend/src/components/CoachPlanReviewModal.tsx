"use client";

import { useEffect, useState, useMemo } from "react";
import apiClient, { formatBeijingTime } from "@/lib/apiClient";
import { showToast as notifyToast, askConfirm } from "@/components/ui/UiFeedbackProvider";
import {
  Calendar,
  CheckCircle2,
  Edit3,
  Flame,
  Mountain,
  RefreshCw,
  Sparkles,
  Target,
  Trophy,
  Zap,
  Activity,
  AlertCircle,
  X,
  Check,
  Send,
  TrendingDown,
  TrendingUp,
  ShieldAlert,
  ClipboardCheck,
  BarChart3,
  Clock,
  Heart,
  ChevronLeft,
  ChevronRight,
  Table,
  ArrowRightLeft,
  Users
} from "lucide-react";

interface CoachPlanReviewModalProps {
  isOpen?: boolean;
  student: any;
  studentsQueue?: any[];
  onSelectStudent?: (student: any) => void;
  clubId?: string;
  coachUid: string;
  onClose: () => void;
  onPlanUpdated?: () => void;
  onUpdated?: () => void;
}

const WORKOUT_TYPES = [
  { id: "easy_run", label: "轻松跑 (Easy)", badgeClass: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
  { id: "tempo", label: "节奏/门槛跑 (Tempo)", badgeClass: "bg-amber-500/20 text-amber-300 border-amber-500/30" },
  { id: "interval", label: "间歇跑 (Interval)", badgeClass: "bg-rose-500/20 text-rose-300 border-rose-500/30" },
  { id: "long_run", label: "长距离 (LSD)", badgeClass: "bg-purple-500/20 text-purple-300 border-purple-500/30" },
  { id: "trail_climb", label: "越野爬升 (Trail)", badgeClass: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30" },
  { id: "cross_training", label: "交叉力量 (Cross)", badgeClass: "bg-sky-500/20 text-sky-300 border-sky-500/30" },
  { id: "race", label: "比赛日 (Race)", badgeClass: "bg-red-500/30 text-red-200 border-red-500/50" },
  { id: "rest", label: "休息恢复 (Rest)", badgeClass: "bg-zinc-800 text-zinc-400 border-white/10" },
];

const QUICK_COACH_NOTE_TEMPLATES = [
  "轻松跑务必压住心率在 Z2 区，切忌盲目拼配速",
  "重点保质完成周中专项课与周末长距离，注意途中补给",
  "近期疲劳指数偏高，课后加强拉伸与睡眠，如身体不适及时反馈减量",
  "大师组恢复优先，大课后严格执行 72 小时低强度超量恢复",
];

const QUICK_ROLLING_DIAGNOSIS_TAGS = [
  "腿部力量欠缺，落地弹性不够，下周加做2组臀腿核心身训",
  "本周完成度良好，下周需完成一次30km有氧长距离",
  "存在轻微伤痛/低HRV反馈，下周减量保护并以有氧恢复跑为主",
  "周二安排交大合练（慢跑+身训+间歇速度课），注意热身充分",
];

export default function CoachPlanReviewModal({
  isOpen = true,
  student,
  studentsQueue = [],
  onSelectStudent,
  clubId,
  coachUid,
  onClose,
  onPlanUpdated,
  onUpdated,
}: CoachPlanReviewModalProps) {
  const triggerUpdated = () => {
    if (onPlanUpdated) onPlanUpdated();
    if (onUpdated) onUpdated();
  };
  const [loading, setLoading] = useState(true);
  const [activePlan, setActivePlan] = useState<any>(null);
  const [draftPlan, setDraftPlan] = useState<any>(null);
  const [allPlans, setAllPlans] = useState<any[]>([]);
  const [planBackups, setPlanBackups] = useState<any[]>([]);
  const [inspectTarget, setInspectTarget] = useState<"draft" | "active">("draft");
  const [showVersionDrawer, setShowVersionDrawer] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);
  const [userGoal, setUserGoal] = useState<any>(null);
  const [upcomingRaces, setUpcomingRaces] = useState<any[]>([]);

  // Mode: 'w19_table' (Word+Excel周表与下周滚动工作台), 'review' (卡片微调), 'execution' (打卡详情), 'generate' (AI定制新草案)
  const [viewMode, setViewMode] = useState<"w19_table" | "review" | "execution" | "generate">("w19_table");
  const [selectedWeekIdx, setSelectedWeekIdx] = useState(1);

  // Plan Overview & Review Note fields
  const [editPlanTitle, setEditPlanTitle] = useState("");
  const [editPlanSummary, setEditPlanSummary] = useState("");
  const [coachReviewNote, setCoachReviewNote] = useState("");
  const [macroRoadmap, setMacroRoadmap] = useState("");
  const [syncToGoals, setSyncToGoals] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [savingOverview, setSavingOverview] = useState(false);
  const [adjustingWeek, setAdjustingWeek] = useState(false);
  const [toastMsg, setToastMsg] = useState("");

  // W19 Weekly Summary & Rolling Next-Week State
  const [weekInjuryNote, setWeekInjuryNote] = useState("");
  const [weekAthleteSummary, setWeekAthleteSummary] = useState("");
  const [weekTravelNote, setWeekTravelNote] = useState("");
  const [weekCoachDiagnosis, setWeekCoachDiagnosis] = useState("");
  const [rollingWeekdayWorkout, setRollingWeekdayWorkout] = useState("");
  const [rollingLongRunKm, setRollingLongRunKm] = useState<string>("");
  const [savingWeekSummary, setSavingWeekSummary] = useState(false);
  const [rollingNextWeek, setRollingNextWeek] = useState(false);
  const [applyingTemplateId, setApplyingTemplateId] = useState<string | null>(null);
  const [quickTemplateScope, setQuickTemplateScope] = useState<"current_week" | "full_plan">("current_week");
  const [quickTemplateWeeksCount, setQuickTemplateWeeksCount] = useState<number>(8);
  const [showAllWeeksMatrix, setShowAllWeeksMatrix] = useState<boolean>(false);
  const [availableTemplates, setAvailableTemplates] = useState<any[]>([]);
  const [showSaveWeekAsTemplateBar, setShowSaveWeekAsTemplateBar] = useState(false);
  const [newTplGroupCode, setNewTplGroupCode] = useState("");
  const [newTplShortName, setNewTplShortName] = useState("");
  const [newTplCategory, setNewTplCategory] = useState("custom");
  const [savingWeekAsTemplate, setSavingWeekAsTemplate] = useState(false);

  const quickBarTemplates = useMemo(() => {
    if (availableTemplates.length > 0) {
      return availableTemplates.map((t: any) => ({
        id: t.id,
        code: t.group_code,
        label: `${t.short_name || t.name} (${t.weekly_km || 50}k)`,
        is_custom: Boolean(t.is_custom),
      }));
    }
    return [
      { id: "group_s_sub240", code: "240组", label: "👑 240组·全马精英 (98k)" },
      { id: "group_a_sub300", code: "A组", label: "🔥 A组·破三 (76k)" },
      { id: "group_b_sub330", code: "B组", label: "⚡ B组·破330 (56k)" },
      { id: "group_c_sub400", code: "C组", label: "🛡️ C组·破四 (45k)" },
      { id: "group_d_base", code: "D组", label: "🌱 D组·筑基 (32k)" },
      { id: "group_e_taper", code: "E组", label: "🧘 E组·减量 (26k)" },
      { id: "group_gobi_a", code: "戈赛A组", label: "🏜️ 戈赛A组·竞赛 (88k)" },
      { id: "group_trail_ultra", code: "越野组", label: "⛰️ 越野组·长距离 (68k)" },
    ];
  }, [availableTemplates]);

  async function fetchAvailableTemplates() {
    try {
      const res = await apiClient.get(
        `/api/coach/plan/templates?club_id=${clubId || ""}&operator_uid=${coachUid || ""}`
      );
      if (res.data?.templates) {
        setAvailableTemplates(res.data.templates);
      }
    } catch (err) {
      console.error("Failed to fetch coach templates:", err);
    }
  }

  async function handleSaveCurrentWeekAsTemplate() {
    if (!workingPlan?.id || savingWeekAsTemplate) return;
    const codeTrim = newTplGroupCode.trim() || "特训组";
    const nameTrim = newTplShortName.trim() || `✨ ${student?.display_name || "专属"}定制周模版`;
    setSavingWeekAsTemplate(true);
    try {
      const res = await apiClient.post("/api/coach/plan/templates", {
        club_id: clubId || "",
        operator_uid: coachUid,
        from_plan_id: workingPlan.id,
        from_week_index: selectedWeekIdx,
        group_code: codeTrim,
        name: nameTrim,
        short_name: nameTrim,
        category: newTplCategory || "custom",
        macro_roadmap: macroRoadmap,
        coach_review_note: coachReviewNote,
      });
      if (res.data?.templates) {
        setAvailableTemplates(res.data.templates);
      }
      setShowSaveWeekAsTemplateBar(false);
      showToast(res.data?.message || `⭐ 已将 W${selectedWeekIdx} 周课表存为教练专属模版：【${nameTrim}】`);
      triggerUpdated();
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "保存为训练模版失败");
    } finally {
      setSavingWeekAsTemplate(false);
    }
  }

  async function handleQuickApplyGroupTemplate(templateId: string, scopeOverride?: "current_week" | "full_plan") {
    if (!student?.user_id || applyingTemplateId) return;
    const effScope = scopeOverride || quickTemplateScope;
    setApplyingTemplateId(templateId);
    try {
      const res = await apiClient.post("/api/coach/plan/assign-template", {
        club_id: clubId || "",
        operator_uid: coachUid,
        template_id: templateId,
        target_user_ids: [student.user_id],
        apply_scope: effScope,
        weeks_count: quickTemplateWeeksCount,
        canova_progression: true,
        as_draft: workingPlan ? workingPlan.status === "draft" : true,
        scale_factor: 1.0,
      });
      await fetchStudentPlanData(student.user_id);
      setViewMode("w19_table");
      showToast(res.data?.message || "✅ 已套用配速与专项组别模版，您可直接点击任意单日进行个别微调！");
      triggerUpdated();
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "套用训练模版失败");
    } finally {
      setApplyingTemplateId(null);
    }
  }

  // AI Draft Generator Config
  const [generating, setGenerating] = useState(false);
  const [goalType, setGoalType] = useState<"race_prep" | "fitness_maintenance">("race_prep");
  const [targetRaceName, setTargetRaceName] = useState("");
  const [targetTime, setTargetTime] = useState("3:30:00");
  const [targetDate, setTargetDate] = useState("");
  const [raceType, setRaceType] = useState("marathon");
  const [maintenanceFocus, setMaintenanceFocus] = useState("aerobic_base");
  const [weeksCount, setWeeksCount] = useState(8);
  const [daysPerWeek, setDaysPerWeek] = useState(4);
  const [weeklyTargetKm, setWeeklyTargetKm] = useState<number>(50);
  const [preferredLongRunDay, setPreferredLongRunDay] = useState("Sunday");
  const [coachNotesPrompt, setCoachNotesPrompt] = useState("");

  // Single Day Workout Edit Modal (includes W19 biometrics, execution, RPE, runner feel, and day swap)
  const [editingDay, setEditingDay] = useState<{ weekIdx: number; dayIdx: number; day: any } | null>(null);
  const [dayWorkoutType, setDayWorkoutType] = useState("easy_run");
  const [dayTitle, setDayTitle] = useState("");
  const [dayDistanceKm, setDayDistanceKm] = useState<number | string>(10);
  const [dayTargetPace, setDayTargetPace] = useState("");
  const [dayTargetHrZone, setDayTargetHrZone] = useState("");
  const [dayDescription, setDayDescription] = useState("");
  const [dayCoachNotes, setDayCoachNotes] = useState("");
  const [dayCompleted, setDayCompleted] = useState(false);
  const [dayActualExecText, setDayActualExecText] = useState("");
  const [dayRpe, setDayRpe] = useState<string>("");
  const [dayAthleteNotes, setDayAthleteNotes] = useState("");
  const [dayHrv, setDayHrv] = useState<string>("");
  const [dayRestingHr, setDayRestingHr] = useState<string>("");
  const [dayRespRate, setDayRespRate] = useState<string>("");
  const [dayStrain, setDayStrain] = useState<string>("");
  const [dayRecoveryPct, setDayRecoveryPct] = useState<string>("");
  const [daySwapWithIdx, setDaySwapWithIdx] = useState<string>("");
  const [savingDay, setSavingDay] = useState(false);

  // Current working plan (respect inspectTarget toggle between draftPlan and activePlan)
  const workingPlan = useMemo(() => {
    if (inspectTarget === "active" && activePlan) return activePlan;
    if (inspectTarget === "draft" && draftPlan) return draftPlan;
    return draftPlan || activePlan;
  }, [inspectTarget, draftPlan, activePlan]);

  function syncPlanFormFields(targetPlan: any) {
    if (!targetPlan) return;
    setEditPlanTitle(targetPlan.title || "");
    setEditPlanSummary(targetPlan.overview_summary || "");
    setCoachReviewNote(
      targetPlan.coach_review_note ||
        targetPlan.schedule_data?.coach_review?.coach_review_note ||
        ""
    );
    setMacroRoadmap(
      targetPlan.schedule_data?.macro_roadmap ||
        "7-8月基础期：夯实有氧跑量 | 9-10月强化期：专项耐力与乳酸阈值 | 11月以赛代练 | 12月目标赛事冲刺"
    );
    setSelectedWeekIdx(targetPlan.current_week_index || 1);
  }

  function handleSwitchInspectTarget(target: "draft" | "active") {
    setInspectTarget(target);
    const nextPlan = target === "draft" ? draftPlan : activePlan;
    if (nextPlan) {
      syncPlanFormFields(nextPlan);
      if (viewMode === "generate") setViewMode("w19_table");
    }
  }

  async function handleRollbackOrSwitchPlan(opts: {
    discardDraftOnly?: boolean;
    backupId?: string;
    targetPlanId?: string;
    label?: string;
  }) {
    if (!student?.user_id || rollingBack) return;
    const confirmText = opts.discardDraftOnly
      ? `确认撤回并删除【${student.display_name}】的待审草案「${draftPlan?.title || "新草案"}」吗？\n（队员当前正在执行的正式计划「${activePlan?.title || "原计划"}」不会受任何影响）`
      : `确认将【${student.display_name}】的生效训练计划切换/回退至「${opts.label || "历史版本"}」吗？\n（队员已完成的日常打卡记录将 100% 合并保留）`;
    if (!await askConfirm(confirmText)) return;

    setRollingBack(true);
    try {
      const res = await apiClient.post(`/api/coach/plan/user/${student.user_id}/rollback`, {
        operator_uid: coachUid,
        discard_draft_only: Boolean(opts.discardDraftOnly),
        backup_id: opts.backupId,
        target_plan_id: opts.targetPlanId,
      });
      await fetchStudentPlanData(student.user_id);
      showToast(res.data?.message || "✅ 已成功回退/切换训练方案！");
      triggerUpdated();
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "回退失败，请稍后重试");
    } finally {
      setRollingBack(false);
    }
  }

  // 20-Athlete Queue Navigation
  const currentQueueIdx = useMemo(() => {
    if (!student?.user_id || !studentsQueue?.length) return -1;
    return studentsQueue.findIndex((s: any) => s.user_id === student.user_id);
  }, [student, studentsQueue]);

  const prevStudent = currentQueueIdx > 0 ? studentsQueue[currentQueueIdx - 1] : null;
  const nextStudent =
    currentQueueIdx >= 0 && currentQueueIdx < studentsQueue.length - 1
      ? studentsQueue[currentQueueIdx + 1]
      : null;

  useEffect(() => {
    fetchAvailableTemplates();
    if (student?.user_id) {
      fetchStudentPlanData(student.user_id);
    }
  }, [student]);

  function showToast(msg: string) {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(""), 4000);
  }

  async function fetchStudentPlanData(uid: string) {
    setLoading(true);
    try {
      const res = await apiClient.get(`/api/coach/plan/user/${uid}`);
      const act = res.data?.active_plan || null;
      const drf = res.data?.draft_plan || null;
      const all = res.data?.all_plans || [];
      const bks = res.data?.backups || [];
      const goal = res.data?.user_goal || null;
      const races = res.data?.upcoming_races || student?.upcoming_races || [];

      setActivePlan(act);
      setDraftPlan(drf);
      setAllPlans(all);
      setPlanBackups(bks);
      setUserGoal(goal);
      setUpcomingRaces(races);

      const defaultInspect = drf ? "draft" : "active";
      setInspectTarget(defaultInspect);

      const targetPlan = drf || act;
      if (targetPlan) {
        syncPlanFormFields(targetPlan);
        setViewMode("w19_table");
      } else {
        setViewMode("generate");
      }

      // Pre-populate generator config from student's goals & races
      const wkTarget = Number(goal?.weekly_target || student?.weekly_target || 50);
      setWeeklyTargetKm(wkTarget);

      const primaryRace = student?.goal_race || races[0];
      if (primaryRace) {
        setGoalType("race_prep");
        setTargetRaceName(primaryRace.name || "上海马拉松");
        if (primaryRace.target_time) setTargetTime(primaryRace.target_time);
        if (primaryRace.race_date) setTargetDate(String(primaryRace.race_date).slice(0, 10));
        if (primaryRace.race_type) setRaceType(primaryRace.race_type);
      } else {
        setTargetRaceName("上海马拉松");
      }
    } catch (err) {
      console.error("Failed to load student plan data:", err);
      setViewMode("generate");
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateDraft() {
    if (!student?.user_id) return;
    setGenerating(true);
    try {
      const payload: any = {
        athlete_uid: student.user_id,
        club_id: clubId,
        goal_type: goalType,
        target_race_name: targetRaceName || "目标赛事",
        target_time: targetTime || "3:30:00",
        race_type: raceType,
        maintenance_focus: maintenanceFocus,
        weeks_count: weeksCount,
        days_per_week: daysPerWeek,
        preferred_long_run_day: preferredLongRunDay,
        user_weekly_target: Number(weeklyTargetKm) || 50,
        operator_uid: coachUid,
        as_draft: true,
        coach_notes_prompt: coachNotesPrompt.trim() || undefined,
      };
      if (targetDate) {
        payload.target_date = targetDate;
      }

      const res = await apiClient.post("/api/coach/plan/generate", payload);
      if (res.data?.plan) {
        const newPlan = res.data.plan;
        setDraftPlan(newPlan);
        setEditPlanTitle(newPlan.title || "");
        setEditPlanSummary(newPlan.overview_summary || "");
        setCoachReviewNote(newPlan.coach_review_note || coachNotesPrompt.trim() || "");
        setSelectedWeekIdx(newPlan.current_week_index || 1);
        setViewMode("w19_table");
        showToast("✨ 已根据队员目标与体能状态生成计划草案，请审核微调后发布！");
        triggerUpdated();
      }
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "生成计划草案失败，请稍后重试");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSaveOverviewOnly() {
    if (!workingPlan?.id) return;
    setSavingOverview(true);
    try {
      const res = await apiClient.put(`/api/coach/plan/${workingPlan.id}`, {
        title: editPlanTitle,
        overview_summary: editPlanSummary,
        coach_review_note: coachReviewNote,
        operator_uid: coachUid,
      });
      if (res.data?.plan) {
        if (workingPlan.status === "draft") {
          setDraftPlan(res.data.plan);
        } else {
          setActivePlan(res.data.plan);
        }
        showToast("💾 计划总评与教练批注已保存");
        triggerUpdated();
      }
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "保存失败");
    } finally {
      setSavingOverview(false);
    }
  }

  async function handlePublishPlan(jumpToNext: boolean = false) {
    if (!workingPlan?.id) return;
    setPublishing(true);
    try {
      const res = await apiClient.post(`/api/coach/plan/${workingPlan.id}/publish`, {
        operator_uid: coachUid,
        title: editPlanTitle,
        overview_summary: editPlanSummary,
        coach_review_note: coachReviewNote,
        sync_to_goals: syncToGoals,
      });
      if (res.data?.plan) {
        setActivePlan(res.data.plan);
        setDraftPlan(null);
        triggerUpdated();
        if (jumpToNext && nextStudent && onSelectStudent) {
          showToast(`✅ 已发布 ${student?.display_name} 的课表，自动进入下一位：${nextStudent.display_name}`);
          setTimeout(() => {
            onSelectStudent(nextStudent);
          }, 450);
        } else {
          showToast("✅ 训练计划已审核通过并正式发布给队员！");
        }
      }
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "发布失败，请稍后重试");
    } finally {
      setPublishing(false);
    }
  }

  async function handleWeekBatchAdjust(action: "scale_volume" | "downgrade_intensity", scaleFactor?: number) {
    if (!workingPlan?.id) return;
    setAdjustingWeek(true);
    try {
      const res = await apiClient.post(`/api/coach/plan/${workingPlan.id}/week-adjust`, {
        week_index: selectedWeekIdx,
        action,
        scale_factor: scaleFactor,
        operator_uid: coachUid,
      });
      if (res.data?.plan) {
        if (workingPlan.status === "draft") {
          setDraftPlan(res.data.plan);
        } else {
          setActivePlan(res.data.plan);
        }
        showToast(res.data.message || `第 ${selectedWeekIdx} 周课表已调整`);
        triggerUpdated();
      }
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "周课表调整失败");
    } finally {
      setAdjustingWeek(false);
    }
  }

  async function handleSaveWeekSummary() {
    if (!workingPlan?.id) return;
    setSavingWeekSummary(true);
    try {
      const res = await apiClient.post(`/api/coach/plan/${workingPlan.id}/week-summary`, {
        week_index: selectedWeekIdx,
        injury_note: weekInjuryNote,
        athlete_weekly_summary: weekAthleteSummary,
        travel_or_leave_note: weekTravelNote,
        coach_weekly_diagnosis: weekCoachDiagnosis,
        macro_roadmap: macroRoadmap,
        operator_uid: coachUid,
      });
      if (res.data?.plan) {
        if (workingPlan.status === "draft") {
          setDraftPlan(res.data.plan);
        } else {
          setActivePlan(res.data.plan);
        }
        showToast(`💾 W${selectedWeekIdx} 周小结、伤痛记录与教练复盘已保存`);
        triggerUpdated();
      }
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "保存周小结失败");
    } finally {
      setSavingWeekSummary(false);
    }
  }

  async function handleRollNextWeek() {
    if (!workingPlan?.id) return;
    setRollingNextWeek(true);
    try {
      const res = await apiClient.post(`/api/coach/plan/${workingPlan.id}/roll-next-week`, {
        source_week_index: selectedWeekIdx,
        coach_diagnosis: weekCoachDiagnosis,
        weekday_group_workout: rollingWeekdayWorkout.trim() || undefined,
        weekend_long_run_km: rollingLongRunKm ? Number(rollingLongRunKm) : undefined,
        operator_uid: coachUid,
      });
      if (res.data?.plan) {
        if (workingPlan.status === "draft") {
          setDraftPlan(res.data.plan);
        } else {
          setActivePlan(res.data.plan);
        }
        const nextIdx = res.data.next_week_index || selectedWeekIdx + 1;
        setSelectedWeekIdx(nextIdx);
        showToast(res.data.message || `✨ 已滚动生成 W${nextIdx} 周课表，已为您切换至 W${nextIdx} 审阅！`);
        triggerUpdated();
      }
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "滚动生成下周课表失败");
    } finally {
      setRollingNextWeek(false);
    }
  }

  async function handleQuickStepDistance(weekIdx: number, dayIdx: number, day: any, deltaKm: number) {
    if (!workingPlan?.id) return;
    const curKm = Number(day.distance_km) || 0;
    const nextKm = Math.max(0, Math.round((curKm + deltaKm) * 10) / 10);
    const nextType = nextKm === 0 ? "rest" : day.workout_type === "rest" ? "easy_run" : day.workout_type;
    try {
      const res = await apiClient.patch(`/api/coach/plan/${workingPlan.id}/workout`, {
        week_index: weekIdx,
        day_index: dayIdx,
        date: day.date,
        distance_km: nextKm,
        workout_type: nextType,
        operator_uid: coachUid,
      });
      if (res.data?.plan) {
        if (workingPlan.status === "draft") {
          setDraftPlan(res.data.plan);
        } else {
          setActivePlan(res.data.plan);
        }
        triggerUpdated();
      }
    } catch (err) {
      console.error("Quick distance step error:", err);
    }
  }

  function openDayEditModal(weekIdx: number, dayIdx: number, day: any) {
    setEditingDay({ weekIdx, dayIdx, day });
    setDayWorkoutType(day.workout_type || "easy_run");
    setDayTitle(day.title || "");
    setDayDistanceKm(day.distance_km ?? 0);
    setDayTargetPace(day.target_pace || "");
    setDayTargetHrZone(day.target_hr_zone || "");
    setDayDescription(day.description || "");
    setDayCoachNotes(day.coach_notes || "");
    setDayCompleted(Boolean(day.completed));
    setDayActualExecText(day.actual_execution_text || "");
    setDayRpe(day.rpe != null ? String(day.rpe) : "");
    setDayAthleteNotes(day.athlete_notes || "");
    setDayHrv(day.hrv != null ? String(day.hrv) : "");
    setDayRestingHr(day.resting_hr != null ? String(day.resting_hr) : "");
    setDayRespRate(day.respiratory_rate != null ? String(day.respiratory_rate) : "");
    setDayStrain(day.strain_score != null ? String(day.strain_score) : "");
    setDayRecoveryPct(day.recovery_pct != null ? String(day.recovery_pct) : "");
    setDaySwapWithIdx("");
  }

  async function handleSaveDayWorkout() {
    if (!workingPlan?.id || !editingDay) return;
    setSavingDay(true);
    try {
      const distNum = dayWorkoutType === "rest" ? 0 : Number(dayDistanceKm) || 0;
      const payload: any = {
        week_index: editingDay.weekIdx,
        day_index: editingDay.dayIdx,
        date: editingDay.day.date,
        workout_type: dayWorkoutType,
        title: dayTitle,
        distance_km: distNum,
        target_pace: dayTargetPace,
        target_hr_zone: dayTargetHrZone,
        description: dayDescription,
        coach_notes: dayCoachNotes,
        completed: dayCompleted,
        actual_execution_text: dayActualExecText,
        athlete_notes: dayAthleteNotes,
        operator_uid: coachUid,
      };
      if (dayRpe !== "") payload.rpe = Number(dayRpe);
      if (dayHrv !== "") payload.hrv = Number(dayHrv);
      if (dayRestingHr !== "") payload.resting_hr = Number(dayRestingHr);
      if (dayRespRate !== "") payload.respiratory_rate = Number(dayRespRate);
      if (dayStrain !== "") payload.strain_score = Number(dayStrain);
      if (dayRecoveryPct !== "") payload.recovery_pct = Number(dayRecoveryPct);
      if (daySwapWithIdx === "undo") {
        payload.undo_swap = true;
      } else if (daySwapWithIdx !== "") {
        payload.swap_with_day_index = Number(daySwapWithIdx);
      }

      const res = await apiClient.patch(`/api/coach/plan/${workingPlan.id}/workout`, payload);
      if (res.data?.plan) {
        if (workingPlan.status === "draft") {
          setDraftPlan(res.data.plan);
        } else {
          setActivePlan(res.data.plan);
        }
        setEditingDay(null);
        showToast("✅ 单日课表、身体指标与执行记录已保存");
        triggerUpdated();
      }
    } catch (err: any) {
      notifyToast(err.response?.data?.detail || "保存课表失败");
    } finally {
      setSavingDay(false);
    }
  }

  const weeks = useMemo(() => workingPlan?.schedule_data?.weeks || [], [workingPlan]);
  const activeWeek = useMemo(
    () => weeks.find((w: any) => w.week_index === selectedWeekIdx) || weeks[0] || null,
    [weeks, selectedWeekIdx]
  );

  // Sync week summary inputs whenever activeWeek changes
  useEffect(() => {
    if (activeWeek) {
      const ws = activeWeek.week_summary || {};
      setWeekInjuryNote(ws.injury_note || "");
      setWeekAthleteSummary(ws.athlete_weekly_summary || "");
      setWeekTravelNote(ws.travel_or_leave_note || "");
      setWeekCoachDiagnosis(ws.coach_weekly_diagnosis || "");
    }
  }, [activeWeek]);


  const weekExecStats = useMemo(() => {
    if (!activeWeek) return { plannedKm: 0, actualKm: 0, totalRuns: 0, doneRuns: 0, missedRuns: 0, rate: 0 };
    const days = activeWeek.days || [];
    const plannedKm = Math.round(days.reduce((acc: number, d: any) => acc + (Number(d.distance_km) || 0), 0) * 10) / 10;
    const actualKm =
      Math.round(
        days.reduce((acc: number, d: any) => {
          if (d.workout_type === "rest") return acc;
          const act = d.actual_distance_km ?? (d.completed ? d.distance_km : 0);
          return acc + (Number(act) || 0);
        }, 0) * 10
      ) / 10;
    const runDays = days.filter((d: any) => d.workout_type !== "rest" && (Number(d.distance_km) || 0) > 0);
    const totalRuns = runDays.length;
    const doneRuns = runDays.filter((d: any) => d.completed).length;
    const missedRuns = runDays.filter((d: any) => d.is_missed).length;
    const rate = totalRuns > 0 ? Math.round((doneRuns / totalRuns) * 100) : 0;
    return { plannedKm, actualKm, totalRuns, doneRuns, missedRuns, rate };
  }, [activeWeek]);

  function getWorkoutTypeMeta(type: string) {
    return WORKOUT_TYPES.find((t) => t.id === type) || WORKOUT_TYPES[0];
  }

  if (!isOpen || !student) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-2 sm:p-4">
      <div className="bg-[#121215] border border-white/10 rounded-3xl w-full max-w-6xl max-h-[94vh] flex flex-col shadow-2xl overflow-hidden relative">
        {/* Toast Banner */}
        {toastMsg && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-2xl bg-emerald-500 text-black font-bold text-xs shadow-xl flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{toastMsg}</span>
          </div>
        )}

        {/* ── Top Header: Athlete Snapshot & Mode Tabs ── */}
        <div className="p-5 sm:p-6 bg-[#18181c] border-b border-white/10 flex flex-col lg:flex-row lg:items-center justify-between gap-4 shrink-0">
          <div className="flex items-center gap-4">
            <img
              src={
                student?.avatar_url ||
                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
              }
              alt={student?.display_name}
              className="w-14 h-14 rounded-full object-cover border border-white/15 shrink-0"
            />
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h2 className="text-lg sm:text-xl font-black text-white">
                  {student?.display_name} · 训练计划制定、审核与执行
                </h2>
                {draftPlan ? (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-white/5 text-zinc-200 border border-white/10">
                    🟠 草案待审核
                  </span>
                ) : activePlan?.review_status === "published" ? (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-white/5 text-zinc-200 border border-white/10">
                    🟢 教练已发布 · 执行中
                  </span>
                ) : activePlan ? (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-white/5 text-zinc-200 border border-white/10">
                    🔵 队员自建计划 · 执行中
                  </span>
                ) : (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-white/5 text-zinc-400 border border-white/10">
                    ⚪ 暂未制定训练计划
                  </span>
                )}
              </div>

              <div className="flex items-center gap-3 text-xs text-zinc-400 mt-1.5 flex-wrap">
                <span>
                  状态:{" "}
                  <strong className="text-white font-mono">
                    CTL {student?.ctl || 0} / ATL {student?.atl || 0} / TSB{" "}
                    {student?.tsb > 0 ? `+${student.tsb}` : student?.tsb || 0}
                  </strong>
                </span>
                <span>·</span>
                <span>
                  目标跑量:{" "}
                  <strong className="text-white font-mono">
                    {student?.weekly_target || 50} km/周 ({student?.target_km || 200} km/月)
                  </strong>
                </span>
                {student?.goal_race && (
                  <>
                    <span>·</span>
                    <span className="text-zinc-300 font-medium">
                      🏅 目标赛事: {student.goal_race.name} ({student.goal_race.race_date?.slice(0, 10)} ·{" "}
                      {student.goal_race.target_time || "完赛"})
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start lg:self-auto flex-wrap">
            {workingPlan && (
              <>
                <button
                  onClick={() => setViewMode("w19_table")}
                  className={`px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer border ${
                    viewMode === "w19_table"
                      ? "bg-[#FC4C02] text-white border-[#FC4C02] shadow-sm"
                      : "bg-white/5 text-zinc-300 border-white/10 hover:bg-white/10"
                  }`}
                >
                  <Table className="w-4 h-4" />
                  周训练表与下周滚动
                </button>
                <button
                  onClick={() => setViewMode("review")}
                  className={`px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer border ${
                    viewMode === "review"
                      ? "bg-[#FC4C02] text-white border-[#FC4C02] shadow-sm"
                      : "bg-white/5 text-zinc-300 border-white/10 hover:bg-white/10"
                  }`}
                >
                  <ClipboardCheck className="w-4 h-4" />
                  卡片微调
                </button>
                <button
                  onClick={() => setViewMode("execution")}
                  className={`px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer border ${
                    viewMode === "execution"
                      ? "bg-[#FC4C02] text-white border-[#FC4C02] shadow-sm"
                      : "bg-white/5 text-zinc-300 border-white/10 hover:bg-white/10"
                  }`}
                >
                  <BarChart3 className="w-4 h-4" />
                  打卡比对 ({weekExecStats.rate}%)
                </button>
              </>
            )}
            <button
              onClick={() => setViewMode("generate")}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer border ${
                viewMode === "generate"
                  ? "bg-[#FC4C02] text-white border-[#FC4C02] shadow-sm"
                  : "bg-white/5 text-zinc-300 border-white/10 hover:bg-white/10"
              }`}
            >
              <Sparkles className="w-4 h-4" />
              {workingPlan ? "重新生成草案" : "制定训练计划"}
            </button>

            <button
              onClick={onClose}
              className="p-2 text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-full transition ml-1 cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* ── 20-Athlete Continuous Pipeline Bar (教练 20人周度流水线快速切换条) ── */}
        {studentsQueue && studentsQueue.length > 1 && onSelectStudent && (
          <div className="px-5 py-2.5 bg-[#141418] border-b border-white/10 flex items-center justify-between gap-3 shrink-0">
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                disabled={!prevStudent}
                onClick={() => prevStudent && onSelectStudent(prevStudent)}
                className="px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 disabled:opacity-30 text-xs font-bold text-zinc-200 flex items-center gap-1 transition cursor-pointer"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>上一位{prevStudent ? `: ${prevStudent.display_name}` : ""}</span>
              </button>
              <span className="text-[11px] font-mono font-bold px-2.5 py-1 rounded-lg bg-white/5 text-zinc-300 border border-white/10">
                流水线批阅 {currentQueueIdx + 1} / {studentsQueue.length}
              </span>
            </div>

            <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 flex-1">
              {studentsQueue.map((stu: any, idx: number) => {
                const isCur = stu.user_id === student?.user_id;
                const pSt = stu.plan_info?.plan_state || "none";
                const hasInj = stu.plan_info?.week_execution?.has_injury_alert;
                return (
                  <button
                    key={stu.user_id || idx}
                    type="button"
                    onClick={() => onSelectStudent(stu)}
                    className={`shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-bold border transition flex items-center gap-1 cursor-pointer ${
                      isCur
                        ? "bg-[#FC4C02] text-white border-[#FC4C02] shadow-sm"
                        : "bg-white/5 text-zinc-300 border-white/10 hover:bg-white/10"
                    }`}
                  >
                    <span>{idx + 1}.{stu.display_name}</span>
                    {hasInj && <span title="本周上报伤痛">🩹</span>}
                    {!hasInj && pSt === "draft_pending" && <span title="待审核">🟠</span>}
                    {!hasInj && pSt === "published" && <span title="已发布">🟢</span>}
                  </button>
                );
              })}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                disabled={!nextStudent}
                onClick={() => nextStudent && onSelectStudent(nextStudent)}
                className="px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 disabled:opacity-30 text-xs font-bold text-zinc-200 flex items-center gap-1 transition cursor-pointer"
              >
                <span>下一位{nextStudent ? `: ${nextStudent.display_name}` : ""}</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* ── Multi-Plan Switcher (Active vs Draft) & 1-Click Rollback Bar ── */}
        {!loading && (activePlan || draftPlan || planBackups.length > 0 || allPlans.length > 1) && (
          <div className="px-5 py-2.5 bg-[#18181c] border-b border-white/10 space-y-2.5 shrink-0">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-2.5 text-xs">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] font-bold text-zinc-400">当前审阅方案：</span>
                {draftPlan && (
                  <button
                    type="button"
                    onClick={() => handleSwitchInspectTarget("draft")}
                    className={`px-3 py-1.5 rounded-xl font-bold border transition flex items-center gap-1.5 cursor-pointer ${
                      workingPlan?.id === draftPlan.id
                        ? "bg-[#FC4C02] text-white border-[#FC4C02] font-black shadow-sm"
                        : "bg-white/5 text-zinc-300 border-white/10 hover:bg-white/10"
                    }`}
                  >
                    <span>📝 待审草案（未生效）：{draftPlan.title}</span>
                    {draftPlan.source_label && (
                      <span className="opacity-85 text-[10px]">
                        · {draftPlan.source_label}
                      </span>
                    )}
                  </button>
                )}

                {activePlan && (
                  <button
                    type="button"
                    onClick={() => handleSwitchInspectTarget("active")}
                    className={`px-3 py-1.5 rounded-xl font-bold border transition flex items-center gap-1.5 cursor-pointer ${
                      workingPlan?.id === activePlan.id
                        ? "bg-[#FC4C02] text-white border-[#FC4C02] font-black shadow-sm"
                        : "bg-white/5 text-zinc-300 border-white/10 hover:bg-white/10"
                    }`}
                  >
                    <span>✅ 当前执行中：{activePlan.title}</span>
                    {activePlan.source_label && (
                      <span className="opacity-85 text-[10px]">
                        · {activePlan.source_label}
                      </span>
                    )}
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                {draftPlan && (
                  <button
                    type="button"
                    disabled={rollingBack}
                    onClick={() => handleRollbackOrSwitchPlan({ discardDraftOnly: true })}
                    className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 font-bold text-xs transition cursor-pointer disabled:opacity-50"
                    title="删除此待审草案，保持队员当前正在执行的计划不变"
                  >
                    🗑️ 撤回此草案
                  </button>
                )}

                {(planBackups.length > 0 || allPlans.filter((p) => p.status === "archived").length > 0) && (
                  <button
                    type="button"
                    onClick={() => setShowVersionDrawer((prev) => !prev)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition cursor-pointer ${
                      showVersionDrawer
                        ? "bg-[#FC4C02] text-white border-[#FC4C02]"
                        : "bg-white/5 hover:bg-white/10 text-zinc-300 border-white/10"
                    }`}
                  >
                    ⏪ 历史版本与方案切换 ({planBackups.length + allPlans.filter((p) => p.status === "archived").length})
                  </button>
                )}
              </div>
            </div>

            {showVersionDrawer && (
              <div className="p-3.5 rounded-2xl bg-[#141418] border border-white/10 space-y-2.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-zinc-200">
                    ⏪ {student?.display_name} 的历史训练方案与备份快照（点击即可一键切回，已打卡记录 100% 合并保留）
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowVersionDrawer(false)}
                    className="text-zinc-400 hover:text-white cursor-pointer"
                  >
                    收起 ✕
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-44 overflow-y-auto pr-1">
                  {planBackups.map((bk: any) => (
                    <div
                      key={bk.id}
                      className="p-2.5 rounded-xl bg-[#18181c] border border-white/10 flex items-center justify-between gap-2"
                    >
                      <div className="min-w-0">
                        <div className="font-bold text-white truncate">
                          📸 快照：{bk.previous_plan_title || "原训练课表"}
                        </div>
                        <div className="text-[10px] text-zinc-400 truncate mt-0.5">
                          产生于：{bk.action_label || "课表变更"} · {formatBeijingTime(bk.created_at, true)}
                        </div>
                      </div>
                      <button
                        type="button"
                        disabled={rollingBack}
                        onClick={() =>
                          handleRollbackOrSwitchPlan({
                            backupId: bk.id,
                            label: bk.previous_plan_title || "快照课表",
                          })
                        }
                        className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 text-[11px] font-bold shrink-0 cursor-pointer"
                      >
                        ⏪ 恢复此快照
                      </button>
                    </div>
                  ))}

                  {allPlans
                    .filter((p: any) => p.status === "archived")
                    .map((arc: any) => (
                      <div
                        key={arc.id}
                        className="p-2.5 rounded-xl bg-[#18181c] border border-white/10 flex items-center justify-between gap-2"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-white truncate">{arc.title}</span>
                            {arc.source_label && (
                              <span className="px-1.5 py-0.2 rounded bg-white/5 text-zinc-300 border border-white/10 text-[9px] font-bold shrink-0">
                                {arc.source_label}
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-zinc-400 truncate mt-0.5">
                            归档方案 · {arc.weeks_count || 4}周周期 · 更新于 {String(arc.updated_at || "").slice(0, 10)}
                          </div>
                        </div>
                        <button
                          type="button"
                          disabled={rollingBack}
                          onClick={() =>
                            handleRollbackOrSwitchPlan({
                              targetPlanId: arc.id,
                              label: arc.title,
                            })
                          }
                          className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 text-[11px] font-bold shrink-0 cursor-pointer"
                        >
                          🔄 切回此方案
                        </button>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Main Scrollable Body ── */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-zinc-400 text-sm flex flex-col items-center gap-3">
              <RefreshCw className="w-6 h-6 animate-spin text-purple-400" />
              <span>正在加载队员训练计划与执行数据...</span>
            </div>
          ) : viewMode === "generate" || !workingPlan ? (
            /* ── VIEW 1: AI DRAFT GENERATOR FOR COACH ── */
            <div className="bg-[#18181c] border border-purple-500/30 rounded-3xl p-6 space-y-6">
              {/* Quick Apply Group Template Bar for Unscheduled Runner */}
              <div className="bg-gradient-to-r from-amber-500/10 via-[#15151b] to-[#15151b] border border-amber-500/35 rounded-2xl p-4 space-y-2.5">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="text-xs font-black text-amber-300 flex items-center gap-2">
                    <span>📚 快捷方案：一键套用配速与专项组别模版（含240精英/戈赛竞赛/长距离越野/自定义，分配后再微调）</span>
                    {student?.recommended_group && (
                      <span className="px-2 py-0.5 rounded-full bg-amber-400 text-black text-[10px] font-black">
                        🎯 智能推荐: {student.recommended_group.group_name}
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-zinc-400">点击即生成该组别 4 周标准课表并跳至周表微调</span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  {quickBarTemplates.map((g: any) => {
                    const isRec = student?.recommended_group?.template_id === g.id;
                    return (
                      <button
                        key={g.id}
                        type="button"
                        disabled={!!applyingTemplateId}
                        onClick={() => handleQuickApplyGroupTemplate(g.id, "full_plan")}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer ${
                          isRec
                            ? "bg-amber-400 text-black font-black shadow-md"
                            : g.is_custom
                            ? "bg-purple-500/20 hover:bg-purple-500/30 text-purple-200 border border-purple-400/40"
                            : "bg-white/5 hover:bg-amber-500/20 text-amber-200 border border-amber-500/30"
                        }`}
                      >
                        {applyingTemplateId === g.id ? "套用中..." : g.label}
                        {isRec ? " ★推荐" : ""}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center justify-between border-b border-white/10 pb-4 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-[#FC4C02]" />
                  <h3 className="text-base font-black text-white">
                    AI 教练智能排课 · 根据队员目标与当前状态生成计划草案
                  </h3>
                </div>
                <span className="text-xs text-zinc-400">
                  生成后将进入【待审核草案】状态，经您审核修改确认后再发布给队员
                </span>
              </div>

              {/* Goal Type Selector */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => setGoalType("race_prep")}
                  className={`p-4 rounded-2xl border text-left transition flex items-start gap-3 cursor-pointer ${
                    goalType === "race_prep"
                      ? "bg-purple-600/20 border-purple-500 text-white"
                      : "bg-[#121215] border-white/5 text-zinc-400 hover:border-white/15"
                  }`}
                >
                  <Trophy className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-sm font-bold text-white">🏅 赛事突破备战 (Canova 专项倒排)</div>
                    <p className="text-xs text-zinc-400 mt-1">
                      针对队员报名的全马/半马/越野赛事，科学规划基础期、专项期与赛前减量期。
                    </p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setGoalType("fitness_maintenance")}
                  className={`p-4 rounded-2xl border text-left transition flex items-start gap-3 cursor-pointer ${
                    goalType === "fitness_maintenance"
                      ? "bg-purple-600/20 border-purple-500 text-white"
                      : "bg-[#121215] border-white/5 text-zinc-400 hover:border-white/15"
                  }`}
                >
                  <Mountain className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-sm font-bold text-white">🏔️ 非赛期体能进阶 (Daniels 周期强化)</div>
                    <p className="text-xs text-zinc-400 mt-1">
                      针对有氧耐力扩容、乳酸阈值、VO2Max 速度储备或越野爬坡抗阻进行周期提升。
                    </p>
                  </div>
                </button>
              </div>

              {goalType === "race_prep" ? (
                <div className="space-y-4 bg-[#121215] p-5 rounded-2xl border border-white/5">
                  {upcomingRaces.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-xs font-bold text-zinc-300 block">
                        🚩 队员已登记的近期赛事（点击直接带入目标）：
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {upcomingRaces.map((r: any, idx: number) => (
                          <button
                            key={r.id || idx}
                            type="button"
                            onClick={() => {
                              setTargetRaceName(r.name);
                              if (r.target_time) setTargetTime(r.target_time);
                              if (r.race_date) setTargetDate(String(r.race_date).slice(0, 10));
                              if (r.race_type) setRaceType(r.race_type);
                            }}
                            className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition cursor-pointer ${
                              targetRaceName === r.name
                                ? "bg-purple-600/30 border-purple-400 text-white"
                                : "bg-white/5 border-white/10 text-zinc-300 hover:border-white/30"
                            }`}
                          >
                            {r.priority == 1 || r.priority === "A" ? "⭐ A标 · " : "⚡ "}
                            {r.name} ({String(r.race_date || "").slice(0, 10)} · {r.target_time || "完赛"})
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">目标赛事名称</label>
                      <input
                        type="text"
                        value={targetRaceName}
                        onChange={(e) => setTargetRaceName(e.target.value)}
                        placeholder="如: 上海马拉松"
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">目标完赛成绩</label>
                      <input
                        type="text"
                        value={targetTime}
                        onChange={(e) => setTargetTime(e.target.value)}
                        placeholder="如: 3:15:00"
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">比赛日期 (可选)</label>
                      <input
                        type="date"
                        value={targetDate}
                        onChange={(e) => setTargetDate(e.target.value)}
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-purple-500"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#121215] p-4 rounded-2xl border border-white/5">
                  {[
                    { id: "aerobic_base", name: "基础有氧耐力扩容" },
                    { id: "lactate_threshold", name: "乳酸阈值巡航提升" },
                    { id: "vo2max_speed", name: "VO2Max 速度储备" },
                    { id: "trail_climbing", name: "山地越野爬升强化" },
                  ].map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setMaintenanceFocus(m.id)}
                      className={`p-3 rounded-xl border text-xs font-bold transition cursor-pointer ${
                        maintenanceFocus === m.id
                          ? "bg-emerald-600/20 border-emerald-500 text-emerald-300"
                          : "bg-[#18181c] border-white/5 text-zinc-400"
                      }`}
                    >
                      {m.name}
                    </button>
                  ))}
                </div>
              )}

              {/* Volume, Weeks, Days, Long Run Day */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 bg-[#121215] p-5 rounded-2xl border border-white/5">
                <div>
                  <label className="text-xs text-zinc-400 block mb-1.5">基准周跑量目标 (km/周)</label>
                  <input
                    type="number"
                    value={weeklyTargetKm}
                    onChange={(e) => setWeeklyTargetKm(Number(e.target.value) || 40)}
                    className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 block mb-1.5">计划周期周数</label>
                  <div className="flex gap-1.5">
                    {[4, 6, 8, 12].map((w) => (
                      <button
                        key={w}
                        type="button"
                        onClick={() => setWeeksCount(w)}
                        className={`flex-1 py-2 rounded-xl text-xs font-bold border transition cursor-pointer ${
                          weeksCount === w
                            ? "bg-purple-600 text-white border-purple-500"
                            : "bg-[#18181c] text-zinc-400 border-white/5"
                        }`}
                      >
                        {w}周
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs text-zinc-400 block mb-1.5">每周训练天数</label>
                  <div className="flex gap-1.5">
                    {[3, 4, 5, 6].map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setDaysPerWeek(d)}
                        className={`flex-1 py-2 rounded-xl text-xs font-bold border transition cursor-pointer ${
                          daysPerWeek === d
                            ? "bg-purple-600 text-white border-purple-500"
                            : "bg-[#18181c] text-zinc-400 border-white/5"
                        }`}
                      >
                        {d}天
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs text-zinc-400 block mb-1.5">周末长距离偏好</label>
                  <div className="flex gap-1.5">
                    {[
                      { id: "Sunday", label: "周日长跑" },
                      { id: "Saturday", label: "周六长跑" },
                    ].map((dayOpt) => (
                      <button
                        key={dayOpt.id}
                        type="button"
                        onClick={() => setPreferredLongRunDay(dayOpt.id)}
                        className={`flex-1 py-2 rounded-xl text-xs font-bold border transition cursor-pointer ${
                          preferredLongRunDay === dayOpt.id
                            ? "bg-purple-600 text-white border-purple-500"
                            : "bg-[#18181c] text-zinc-400 border-white/5"
                        }`}
                      >
                        {dayOpt.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Coach Special Instructions to AI */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-zinc-300 block">
                  👨‍🏫 教练排课专项要求（可选，AI 制定课表时将优先遵循您的指令）：
                </label>
                <textarea
                  rows={2}
                  value={coachNotesPrompt}
                  onChange={(e) => setCoachNotesPrompt(e.target.value)}
                  placeholder="例如：该队员近期右膝轻微不适，前两周避免高配速间歇，周日长距离控制在22km以内，重点扎实有氧心率..."
                  className="w-full bg-[#121215] border border-white/10 rounded-2xl p-3.5 text-xs text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3">
                {workingPlan && (
                  <button
                    type="button"
                    onClick={() => setViewMode("review")}
                    className="px-5 py-3 rounded-2xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-bold transition cursor-pointer"
                  >
                    返回现有计划审核
                  </button>
                )}
                <button
                  type="button"
                  disabled={generating}
                  onClick={handleGenerateDraft}
                  className="px-6 py-3 rounded-2xl bg-gradient-to-r from-[#FC4C02] to-amber-500 hover:from-[#ff5a14] hover:to-amber-400 text-white font-black text-xs shadow-lg shadow-[#FC4C02]/25 transition flex items-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {generating ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>AI 正在结合队员体能与目标生成草案...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>生成 AI 训练计划草案 (进入教练审核)</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : viewMode === "w19_table" ? (
            /* ── VIEW 1B: W19 STANDARD WEEKLY PLAN & EXECUTION TABLE (1:1 复刻 Word + Excel 周训练计划与体感表) ── */
            <div className="space-y-5">
              {/* Top Action & Macro Roadmap Bar (Word 阶段宏观周期大纲 + 一键发布流水线) */}
              <div className="bg-[#18181c] border border-white/10 rounded-2xl p-4 sm:p-5 space-y-3">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-bold text-white">
                      {workingPlan.title || `${student?.display_name}训练计划`}
                    </span>
                    {workingPlan.status === "draft" ? (
                      <span className="text-[11px] px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 font-medium">
                        待审核草案
                      </span>
                    ) : (
                      <span className="text-[11px] px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 font-medium">
                        已发布生效
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      type="button"
                      disabled={savingWeekSummary}
                      onClick={handleSaveWeekSummary}
                      className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-xs font-medium transition cursor-pointer"
                    >
                      {savingWeekSummary ? "保存中..." : "保存周小结与大纲"}
                    </button>

                    <button
                      type="button"
                      disabled={publishing}
                      onClick={() => handlePublishPlan(false)}
                      className="px-3.5 py-1.5 rounded-lg bg-[#FC4C02] hover:bg-[#ff5a14] text-white font-bold text-xs transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>
                        {publishing
                          ? "发布中..."
                          : workingPlan.status === "draft"
                          ? "审核通过并发布"
                          : "保存并同步队员"}
                      </span>
                    </button>

                    {nextStudent && onSelectStudent && (
                      <button
                        type="button"
                        disabled={publishing}
                        onClick={() => handlePublishPlan(true)}
                        className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-200 font-bold text-xs transition flex items-center gap-1 cursor-pointer disabled:opacity-50"
                      >
                        <span>发布并下一位 ({nextStudent.display_name})</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Word Cross-Row Macro Roadmap Input */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-center">
                  <div className="lg:col-span-2 text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                    <span>阶段周期大纲:</span>
                  </div>
                  <div className="lg:col-span-10">
                    <input
                      type="text"
                      value={macroRoadmap}
                      onChange={(e) => setMacroRoadmap(e.target.value)}
                      placeholder="如：7-8月基础期 月跑量260-280km | 9-10月强化期 | 11月南马以赛代练 | 12.6上马"
                      className="w-full bg-[#121215] border border-white/10 rounded-xl px-3.5 py-2 text-xs text-zinc-200 font-medium focus:outline-none focus:border-white/25"
                    />
                  </div>
                </div>

                {/* Quick Apply Group Template Bar + Save Current Week As Template inside W19 Table */}
                <div className="pt-2 border-t border-white/10 space-y-2">
                  <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[11px] font-medium text-zinc-400">
                        套用训练模版:
                      </span>
                      <select
                        value={quickTemplateScope}
                        onChange={(e) => setQuickTemplateScope(e.target.value as "current_week" | "full_plan")}
                        className="bg-[#121215] border border-white/10 rounded-lg px-2 py-1 text-[11px] text-zinc-200 outline-none"
                      >
                        <option value="current_week">仅替换当前周 (第{selectedWeekIdx}周)</option>
                        <option value="full_plan">替换整份周期计划</option>
                      </select>
                      {quickTemplateScope === "full_plan" && (
                        <select
                          value={quickTemplateWeeksCount}
                          onChange={(e) => setQuickTemplateWeeksCount(Number(e.target.value) || 8)}
                          className="bg-[#121215] border border-white/10 rounded-lg px-2 py-1 text-[11px] text-zinc-200 outline-none"
                        >
                          <option value={4}>4周周期</option>
                          <option value={6}>6周周期</option>
                          <option value={8}>8周周期</option>
                          <option value={12}>12周周期</option>
                        </select>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setNewTplGroupCode(workingPlan?.schedule_data?.template_group_code || "特训组");
                          setNewTplShortName(`${student?.display_name || "专属"}第${selectedWeekIdx}周定制模版`);
                          setShowSaveWeekAsTemplateBar(!showSaveWeekAsTemplateBar);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 text-[11px] font-medium transition cursor-pointer"
                      >
                        + 存为新模版
                      </button>
                    </div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {quickBarTemplates.map((g: any) => {
                        const isRec = student?.recommended_group?.template_id === g.id;
                        const isCurTpl = workingPlan?.schedule_data?.template_id === g.id;
                        return (
                          <button
                            key={g.id}
                            type="button"
                            disabled={!!applyingTemplateId}
                            onClick={() => handleQuickApplyGroupTemplate(g.id)}
                            className={`px-2.5 py-1 rounded-lg text-[11px] transition cursor-pointer ${
                              isCurTpl
                                ? "bg-[#FC4C02] text-white font-bold border border-[#FC4C02]"
                                : "bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 font-medium"
                            }`}
                          >
                            {applyingTemplateId === g.id ? "套用中..." : g.label}
                            {isCurTpl ? " ✓" : isRec ? " · 推荐" : ""}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {showSaveWeekAsTemplateBar && (
                    <div className="p-3 rounded-xl bg-[#121215] border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2 flex-wrap flex-1">
                        <span className="text-zinc-300 font-bold shrink-0">存为新模版:</span>
                        <input
                          type="text"
                          value={newTplGroupCode}
                          onChange={(e) => setNewTplGroupCode(e.target.value)}
                          placeholder="组别代号(如:240组/戈赛A+/越野)"
                          className="bg-[#18181c] border border-white/10 rounded-lg px-2.5 py-1 text-white w-36"
                        />
                        <input
                          type="text"
                          value={newTplShortName}
                          onChange={(e) => setNewTplShortName(e.target.value)}
                          placeholder="新模版名称(如:交大240精英冲刺版)"
                          className="bg-[#18181c] border border-white/10 rounded-lg px-2.5 py-1 text-white flex-1 min-w-[180px]"
                        />
                        <select
                          value={newTplCategory}
                          onChange={(e) => setNewTplCategory(e.target.value)}
                          className="bg-[#18181c] border border-white/10 rounded-lg px-2 py-1 text-white"
                        >
                          <option value="marathon">路跑马拉松</option>
                          <option value="gobi">戈壁挑战赛</option>
                          <option value="trail">长距离越野</option>
                          <option value="custom">专属特训</option>
                        </select>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => setShowSaveWeekAsTemplateBar(false)}
                          className="px-2.5 py-1 rounded-lg bg-white/5 text-zinc-400 hover:text-white cursor-pointer"
                        >
                          取消
                        </button>
                        <button
                          type="button"
                          disabled={savingWeekAsTemplate}
                          onClick={handleSaveCurrentWeekAsTemplate}
                          className="px-3 py-1 rounded-lg bg-[#FC4C02] hover:bg-[#ff5a14] text-white font-bold cursor-pointer disabled:opacity-50"
                        >
                          {savingWeekAsTemplate ? "保存中..." : "保存模版"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Week Selector Tabs + Full Cycle Panoramic Toggle + Quick Week Batch Toolbar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                  <button
                    type="button"
                    onClick={() => setShowAllWeeksMatrix(!showAllWeeksMatrix)}
                    className={`shrink-0 px-3.5 py-2 rounded-xl border text-left transition cursor-pointer ${
                      showAllWeeksMatrix
                        ? "bg-[#FC4C02] text-white border-[#FC4C02] font-bold"
                        : "bg-[#18181c] border-white/10 text-zinc-300 hover:text-white font-medium"
                    }`}
                  >
                    <div className="text-xs font-bold">全周期总览 ({weeks.length}周)</div>
                    <div className={`text-[10px] mt-0.5 ${showAllWeeksMatrix ? "text-white/80" : "text-zinc-500"}`}>
                      {showAllWeeksMatrix ? "返回单周表" : "整体浏览与调整"}
                    </div>
                  </button>
                  {weeks.map((w: any) => {
                    const isSelected = !showAllWeeksMatrix && w.week_index === selectedWeekIdx;
                    const isCurrent = (workingPlan.current_week_index || 1) === w.week_index;
                    const wSum = w.week_summary || {};
                    return (
                      <button
                        key={w.week_index}
                        type="button"
                        onClick={() => {
                          setShowAllWeeksMatrix(false);
                          setSelectedWeekIdx(w.week_index);
                        }}
                        className={`shrink-0 px-3.5 py-2 rounded-xl border text-left transition cursor-pointer ${
                          isSelected
                            ? "bg-[#FC4C02] text-white border-[#FC4C02]"
                            : "bg-[#18181c] border-white/10 text-zinc-400 hover:text-white"
                        }`}
                      >
                        <div className="flex items-center gap-1.5 text-xs font-bold">
                          <span>第 {w.week_index} 周</span>
                          {isCurrent && (
                            <span className="text-[9px] px-1.5 py-0.2 rounded bg-white/20 text-white">本周</span>
                          )}
                          {wSum.has_injury_alert && <span title="存在伤痛上报">🩹</span>}
                        </div>
                        <div className={`text-[10px] mt-0.5 font-mono ${isSelected ? "text-white/85" : "text-zinc-500"}`}>
                          计{w.weekly_mileage_km || 0}k / 实{wSum.actual_mileage_km ?? 0}k
                        </div>
                      </button>
                    );
                  })}
                </div>

                <div className="flex items-center gap-1.5 flex-wrap shrink-0">
                  <button
                    type="button"
                    disabled={adjustingWeek}
                    onClick={() => handleWeekBatchAdjust("scale_volume", 0.85)}
                    className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-[11px] font-medium transition cursor-pointer"
                  >
                    第{selectedWeekIdx}周减量15%
                  </button>
                  <button
                    type="button"
                    disabled={adjustingWeek}
                    onClick={() => handleWeekBatchAdjust("scale_volume", 1.1)}
                    className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-[11px] font-medium transition cursor-pointer"
                  >
                    第{selectedWeekIdx}周增量10%
                  </button>
                  <button
                    type="button"
                    disabled={adjustingWeek}
                    onClick={() => handleWeekBatchAdjust("downgrade_intensity")}
                    className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-[11px] font-medium transition cursor-pointer"
                  >
                    强度降级轻松跑
                  </button>
                </div>
              </div>

              {/* Full Multi-Week Panoramic Matrix (W1..WN × Mon..Sun) when showAllWeeksMatrix is active */}
              {showAllWeeksMatrix && (
                <div className="bg-[#18181c] border border-white/10 rounded-2xl overflow-hidden shadow-xl">
                  <div className="px-5 py-3 bg-[#202026] border-b border-white/10 flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-white">
                        全周期 {weeks.length} 周训练计划全景表（点击任意单日即可编辑微调）
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowAllWeeksMatrix(false)}
                      className="px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-medium cursor-pointer"
                    >
                      返回单周执行详表
                    </button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs min-w-[960px]">
                      <thead>
                        <tr className="bg-[#141418] text-zinc-300 border-b border-white/10 font-bold">
                          <th className="py-2.5 px-3 border-r border-white/10 w-44">周次 / 阶段与跑量</th>
                          <th className="py-2.5 px-2 border-r border-white/5">周一</th>
                          <th className="py-2.5 px-2 border-r border-white/5">周二 (速度/间歇)</th>
                          <th className="py-2.5 px-2 border-r border-white/5">周三</th>
                          <th className="py-2.5 px-2 border-r border-white/5">周四 (门槛/专项)</th>
                          <th className="py-2.5 px-2 border-r border-white/5">周五</th>
                          <th className="py-2.5 px-2 border-r border-white/5">周六</th>
                          <th className="py-2.5 px-2">周日 (长距离)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10">
                        {weeks.map((w: any) => {
                          const wSum = w.week_summary || {};
                          return (
                            <tr key={w.week_index} className="hover:bg-white/[0.02] transition align-top">
                              <td className="p-2.5 border-r border-white/10 bg-[#141418]/70">
                                <div className="flex items-center justify-between gap-1">
                                  <span className="px-2 py-0.5 rounded bg-white/10 text-zinc-200 font-mono font-bold text-xs">
                                    第{w.week_index}周
                                  </span>
                                  <span className="font-mono font-bold text-zinc-200 text-xs">
                                    {w.weekly_mileage_km || 0}km
                                  </span>
                                </div>
                                <div className="font-bold text-white text-[11px] mt-1 truncate" title={w.theme || w.week_title}>
                                  {w.theme || w.phase || `第${w.week_index}周`}
                                </div>
                                <div className="text-[10px] text-zinc-500 mt-0.5 font-mono">
                                  已执行 {wSum.actual_mileage_km ?? 0}km
                                </div>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setSelectedWeekIdx(w.week_index);
                                    setShowAllWeeksMatrix(false);
                                  }}
                                  className="mt-1.5 w-full py-1 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white text-[10px] font-medium cursor-pointer"
                                >
                                  查看第 {w.week_index} 周详表 →
                                </button>
                              </td>
                              {(w.days || []).map((day: any, dIdx: number) => {
                                const isRest = day.workout_type === "rest" || !(Number(day.distance_km) > 0);
                                return (
                                  <td key={dIdx} className="p-1.5 border-r border-white/5 last:border-r-0 align-top">
                                    <div
                                      onClick={() => openDayEditModal(w.week_index, dIdx, day)}
                                      title={day.description ? `${day.title}\n${day.description}\n(点击编辑单日处方)` : "点击编辑单日处方"}
                                      className={`p-2 rounded-xl border min-h-[82px] flex flex-col justify-between transition cursor-pointer hover:border-white/30 ${
                                        isRest
                                          ? "border-white/5 bg-black/20"
                                          : "border-white/10 bg-white/[0.02]"
                                      }`}
                                    >
                                      <div className="flex items-center justify-between gap-1">
                                        <span className="text-[9px] text-zinc-500 font-mono">
                                          {day.date ? day.date.slice(5) : day.day_of_week}
                                        </span>
                                        {!isRest && (
                                          <div className="flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
                                            <span className="font-mono font-bold text-[#FC4C02] text-[11px] mr-0.5">
                                              {day.distance_km}k
                                            </span>
                                            <button
                                              type="button"
                                              onClick={() => handleQuickStepDistance(w.week_index, dIdx, day, -1)}
                                              className="px-1 rounded bg-white/5 hover:bg-white/15 text-[9px] font-mono text-zinc-300 cursor-pointer"
                                            >
                                              -1
                                            </button>
                                            <button
                                              type="button"
                                              onClick={() => handleQuickStepDistance(w.week_index, dIdx, day, 1)}
                                              className="px-1 rounded bg-white/5 hover:bg-white/15 text-[9px] font-mono text-zinc-300 cursor-pointer"
                                            >
                                              +1
                                            </button>
                                          </div>
                                        )}
                                      </div>
                                      <div
                                        className={`text-[11px] leading-snug line-clamp-2 my-1 ${
                                          isRest ? "text-zinc-600" : "text-white font-bold"
                                        }`}
                                      >
                                        {isRest ? "休息" : day.title}
                                      </div>
                                      <div className="flex items-center justify-between gap-1 text-[9px] font-mono">
                                        <span className="text-zinc-400 truncate">
                                          {!isRest && day.target_pace && day.target_pace !== "—" ? day.target_pace : ""}
                                        </span>
                                        {day.completed && <span className="text-emerald-400 font-bold">✓已卡</span>}
                                      </div>
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
                </div>
              )}

              {/* W19 Integrated Weekly Plan, Biometrics, Execution, RPE & Notes Table */}
              {activeWeek && (
                <div className="bg-[#18181c] border border-white/10 rounded-2xl overflow-hidden shadow-xl">
                  <div className="px-5 py-3.5 bg-[#202026] border-b border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span className="px-2.5 py-1 rounded-lg bg-white/10 border border-white/10 text-zinc-200 text-xs font-bold">
                        第 {activeWeek.week_index} 周
                      </span>
                      <span className="text-sm font-bold text-white">
                        {activeWeek.week_title || `第 ${activeWeek.week_index} 周训练计划与执行反馈表`}
                      </span>
                      <span className="text-xs text-zinc-400">
                        ({activeWeek.phase || "周期训练"})
                      </span>
                    </div>
                    <div className="text-xs font-mono font-medium text-zinc-300">
                      {activeWeek.week_summary?.summary_header_line ||
                        `周跑量：${weekExecStats.plannedKm}公里。执行：${weekExecStats.actualKm}公里，完成度${
                          weekExecStats.plannedKm > 0
                            ? Math.round((weekExecStats.actualKm * 100) / weekExecStats.plannedKm)
                            : 0
                        }%；力量：${activeWeek.week_summary?.strength_count ?? 0}次。`}
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-[#141418] text-zinc-300 border-b border-white/10 font-bold">
                          <th className="py-3 px-3.5 border-r border-white/10 w-24">星期 / 日期</th>
                          <th className="py-3 px-3.5 border-r border-white/10 min-w-[230px]">训练计划 (教练处方)</th>
                          <th className="py-3 px-3.5 border-r border-white/10 w-44">身体指标 (HRV/静心/呼吸/压力)</th>
                          <th className="py-3 px-2.5 border-r border-white/10 w-20 text-center">恢复%</th>
                          <th className="py-3 px-3.5 border-r border-white/10 min-w-[180px]">计划执行情况</th>
                          <th className="py-3 px-2.5 border-r border-white/10 w-16 text-center">RPE 10</th>
                          <th className="py-3 px-3.5 min-w-[210px]">备注 (队员自我感受 & 批注)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/10">
                        {(activeWeek.days || []).map((day: any, dIdx: number) => {
                          const isRest = day.workout_type === "rest";
                          const hrvNum = day.hrv != null ? Number(day.hrv) : null;
                          const isLowHrv = hrvNum !== null && hrvNum > 0 && hrvNum <= 32;
                          const recNum = day.recovery_pct != null ? Number(day.recovery_pct) : null;
                          const rpeNum = day.rpe != null ? Number(day.rpe) : null;

                          // Recovery % cell styling matching Excel (Green >= 67%, Yellow 34-66%, Red < 34%)
                          const recBadgeClass =
                            recNum === null
                              ? "bg-white/5 text-zinc-500"
                              : recNum >= 67
                              ? "bg-emerald-500/85 text-black font-black"
                              : recNum >= 34
                              ? "bg-amber-400/90 text-black font-black"
                              : "bg-rose-500/90 text-white font-black";

                          return (
                            <tr
                              key={dIdx}
                              className={`hover:bg-white/[0.03] transition ${
                                isRest ? "bg-[#121215]/60" : "bg-[#16161a]"
                              }`}
                            >
                              {/* 1. Day & Date */}
                              <td className="py-3 px-3.5 border-r border-white/10 align-top">
                                <div className="font-bold text-white text-xs">{day.day_of_week}</div>
                                <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
                                  {day.date ? day.date.slice(5) : ""}
                                </div>
                                {day.is_swapped && (
                                  <span className="inline-block mt-1 px-1.5 py-0.5 rounded bg-white/10 text-zinc-300 text-[9px] font-medium">
                                    已对换
                                  </span>
                                )}
                              </td>

                              {/* 2. Prescribed Workout */}
                              <td className="py-3 px-3.5 border-r border-white/10 align-top">
                                <div className="flex items-start justify-between gap-2">
                                  <div>
                                    <span className="font-bold text-white text-xs">
                                      {isRest ? "休息" : day.title}
                                    </span>
                                    {!isRest && Number(day.distance_km) > 0 && (
                                      <span className="ml-1.5 font-mono font-bold text-[#FC4C02]">
                                        {day.distance_km}km
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-1 shrink-0">
                                    {!isRest && (
                                      <>
                                        <button
                                          type="button"
                                          onClick={() => handleQuickStepDistance(activeWeek.week_index, dIdx, day, -1)}
                                          className="px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/15 text-[10px] font-mono text-zinc-300 cursor-pointer"
                                        >
                                          -1k
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => handleQuickStepDistance(activeWeek.week_index, dIdx, day, 1)}
                                          className="px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/15 text-[10px] font-mono text-zinc-300 cursor-pointer"
                                        >
                                          +1k
                                        </button>
                                      </>
                                    )}
                                  </div>
                                </div>
                                {!isRest && day.description && (
                                  <p className="text-[11px] text-zinc-300 mt-1 leading-relaxed">
                                    {day.description}
                                  </p>
                                )}
                                {!isRest && (day.target_pace !== "—" || day.target_hr_zone !== "—") && (
                                  <div className="text-[10px] text-zinc-400 mt-1 font-mono">
                                    {day.target_pace && day.target_pace !== "—" ? `配速 ${day.target_pace} ` : ""}
                                    {day.target_hr_zone && day.target_hr_zone !== "—" ? `· ${day.target_hr_zone}` : ""}
                                  </div>
                                )}
                              </td>

                              {/* 3. Biometrics (HRV / RHR / Resp / Strain) */}
                              <td
                                className={`py-3 px-3.5 border-r border-white/10 align-top font-mono text-[11px] space-y-0.5 ${
                                  isLowHrv ? "bg-rose-500/20 border-l-2 border-l-rose-400" : ""
                                }`}
                              >
                                {hrvNum || day.resting_hr || day.respiratory_rate || day.strain_score ? (
                                  <>
                                    <div className={isLowHrv ? "text-rose-200 font-bold" : "text-zinc-200"}>
                                      HRV：{hrvNum ?? "—"} {isLowHrv && "⚠️偏低"}
                                    </div>
                                    <div className="text-zinc-300">静心：{day.resting_hr ?? "—"}</div>
                                    {day.respiratory_rate != null && (
                                      <div className="text-zinc-400">呼吸：{day.respiratory_rate}</div>
                                    )}
                                    <div className="text-zinc-300">压力：{day.strain_score ?? "—"}</div>
                                  </>
                                ) : (
                                  <span className="text-zinc-600 text-[11px]">待同步/填写</span>
                                )}
                              </td>

                              {/* 4. Recovery % Badge */}
                              <td className="py-3 px-2.5 border-r border-white/10 align-middle text-center">
                                <div className={`px-2 py-1.5 rounded-xl text-xs font-mono ${recBadgeClass}`}>
                                  {recNum !== null ? `${recNum}%` : "—"}
                                </div>
                              </td>

                              {/* 5. Actual Execution Text */}
                              <td className="py-3 px-3.5 border-r border-white/10 align-top">
                                {day.actual_execution_text ? (
                                  <div className="font-mono font-bold text-zinc-200 text-xs leading-relaxed">
                                    {day.actual_execution_text}
                                  </div>
                                ) : day.completed ? (
                                  <div className="font-mono font-bold text-zinc-200 text-xs">
                                    {day.actual_distance_km || day.distance_km}km
                                    {day.actual_avg_pace ? `*${day.actual_avg_pace}` : ""}
                                    {day.actual_avg_hr ? `, hr${day.actual_avg_hr}` : ""}
                                  </div>
                                ) : isRest ? (
                                  <span className="text-zinc-500">跑休</span>
                                ) : day.is_missed ? (
                                  <span className="text-rose-400 font-bold">未打卡 (缺跑)</span>
                                ) : (
                                  <span className="text-zinc-500">待执行</span>
                                )}
                              </td>

                              {/* 6. RPE 10 */}
                              <td className="py-3 px-2.5 border-r border-white/10 align-middle text-center">
                                {rpeNum !== null ? (
                                  <span className="inline-block px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-zinc-200 font-mono font-bold text-xs">
                                    {rpeNum}
                                  </span>
                                ) : (
                                  <span className="text-zinc-600">—</span>
                                )}
                              </td>

                              {/* 7. Athlete Self-Feel Notes & Coach Notes + Edit Trigger */}
                              <td className="py-3 px-3.5 align-top">
                                <div className="flex items-start justify-between gap-2">
                                  <div className="space-y-1 flex-1">
                                    {day.athlete_notes ? (
                                      <p className="text-zinc-100 text-xs leading-relaxed">{day.athlete_notes}</p>
                                    ) : (
                                      <span className="text-zinc-600 text-[11px]">暂无体感备注</span>
                                    )}
                                    {day.coach_notes && (
                                      <div className="px-2 py-1 rounded-lg bg-white/5 border border-white/10 text-[10px] text-zinc-300">
                                        教练: {day.coach_notes}
                                      </div>
                                    )}
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => openDayEditModal(activeWeek.week_index, dIdx, day)}
                                    className="px-2 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 hover:text-white text-[10px] font-medium transition shrink-0 cursor-pointer"
                                  >
                                    编辑
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {/* W19 Weekly Summary Footer + Coach Rolling Next-Week Workbench (周小结 + 伤痛 + 滚动生成下周计划) */}
                  <div className="p-5 bg-[#141418] border-t border-white/10 space-y-4">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                      {/* Col 1: Injury & Travel/Leave */}
                      <div className="space-y-2.5 bg-[#18181c] p-4 rounded-2xl border border-white/10">
                        <div>
                          <label className="text-xs font-bold text-zinc-300 block mb-1">
                            本周伤痛记录 (队员上报 / 教练标注)：
                          </label>
                          <input
                            type="text"
                            value={weekInjuryNote}
                            onChange={(e) => setWeekInjuryNote(e.target.value)}
                            placeholder="如：左脚脚踝内侧有痛感（无伤痛可填“无”）"
                            className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-white/25"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-bold text-zinc-300 block mb-1">
                            近期出行 / 请假调休报备：
                          </label>
                          <input
                            type="text"
                            value={weekTravelNote}
                            onChange={(e) => setWeekTravelNote(e.target.value)}
                            placeholder="如：9.22—10.2 坦桑尼亚旅行"
                            className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-white/25"
                          />
                        </div>
                      </div>

                      {/* Col 2: Runner Weekly Summary */}
                      <div className="space-y-2 bg-[#18181c] p-4 rounded-2xl border border-white/10">
                        <label className="text-xs font-bold text-zinc-300 block">
                          队员周小结 (训练自我感受汇总)：
                        </label>
                        <textarea
                          rows={4}
                          value={weekAthleteSummary}
                          onChange={(e) => setWeekAthleteSummary(e.target.value)}
                          placeholder="如：周跑量59km，身体状态一般，周二合练强度较大，周末长距离后半程弹性下降..."
                          className="w-full bg-[#121215] border border-white/10 rounded-xl p-3 text-xs text-zinc-200 leading-relaxed focus:outline-none focus:border-white/25"
                        />
                      </div>

                      {/* Col 3: Coach Weekly Diagnosis & 1-Click Roll Next Week */}
                      <div className="space-y-2.5 bg-[#18181c] p-4 rounded-2xl border border-white/10">
                        <label className="text-xs font-bold text-zinc-300 block">
                          教练本周复盘与下周导向：
                        </label>
                        <textarea
                          rows={2}
                          value={weekCoachDiagnosis}
                          onChange={(e) => setWeekCoachDiagnosis(e.target.value)}
                          placeholder="如：腿部力量欠缺太多，弹性不够，下周需完成一次30km长距离..."
                          className="w-full bg-[#121215] border border-white/10 rounded-xl p-2.5 text-xs text-white leading-relaxed focus:outline-none focus:border-white/25"
                        />
                        <div className="flex flex-wrap gap-1">
                          {QUICK_ROLLING_DIAGNOSIS_TAGS.map((tag, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() =>
                                setWeekCoachDiagnosis((prev) => (prev ? `${prev}；${tag}` : tag))
                              }
                              className="text-[10px] px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-zinc-200 border border-white/5 transition cursor-pointer"
                            >
                              + {tag.slice(0, 12)}...
                            </button>
                          ))}
                        </div>

                        <div className="grid grid-cols-2 gap-2 pt-1">
                          <input
                            type="text"
                            value={rollingWeekdayWorkout}
                            onChange={(e) => setRollingWeekdayWorkout(e.target.value)}
                            placeholder="下周二合练(如:交大合练)"
                            className="bg-[#121215] border border-white/10 rounded-xl px-2.5 py-1.5 text-[11px] text-white"
                          />
                          <input
                            type="number"
                            value={rollingLongRunKm}
                            onChange={(e) => setRollingLongRunKm(e.target.value)}
                            placeholder="下周长距离km(如:30)"
                            className="bg-[#121215] border border-white/10 rounded-xl px-2.5 py-1.5 text-[11px] text-white font-mono"
                          />
                        </div>

                        <div className="flex items-center gap-2 pt-1">
                          <button
                            type="button"
                            disabled={savingWeekSummary}
                            onClick={handleSaveWeekSummary}
                            className="px-3 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-200 text-xs font-medium transition cursor-pointer"
                          >
                            保存小结
                          </button>
                          <button
                            type="button"
                            disabled={rollingNextWeek}
                            onClick={handleRollNextWeek}
                            className="flex-1 py-2 px-3 rounded-xl bg-[#FC4C02] hover:bg-[#ff5a14] text-white text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${rollingNextWeek ? "animate-spin" : ""}`} />
                            <span>
                              {rollingNextWeek
                                ? "正在智能生成下周..."
                                : `滚动生成 W${activeWeek.week_index + 1} 下周课表`}
                            </span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : viewMode === "review" ? (
            /* ── VIEW 2: COACH REVIEW, QUICK MODIFY & PUBLISH ── */
            <div className="space-y-6">
              {/* Step 1: Plan Overview, Coach Review Note & Publish Action Card */}
              <div className="bg-[#18181c] border border-white/10 rounded-2xl p-5 sm:p-6 space-y-4">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-white/10 pb-4">
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-zinc-400">计划标题</span>
                      {workingPlan.status === "draft" ? (
                        <span className="text-[11px] px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 font-medium">
                          待审核草案 · 尚未对队员生效
                        </span>
                      ) : (
                        <span className="text-[11px] px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 font-medium">
                          已向队员发布生效
                        </span>
                      )}
                    </div>
                    <input
                      type="text"
                      value={editPlanTitle}
                      onChange={(e) => setEditPlanTitle(e.target.value)}
                      className="w-full bg-[#121215] border border-white/10 rounded-xl px-3.5 py-2 text-sm font-bold text-white focus:outline-none focus:border-white/25"
                    />
                  </div>

                  {/* Publish & Save Action Buttons */}
                  <div className="flex items-center gap-3 flex-wrap shrink-0">
                    <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer select-none bg-[#121215] px-3 py-2 rounded-xl border border-white/10">
                      <input
                        type="checkbox"
                        checked={syncToGoals}
                        onChange={(e) => setSyncToGoals(e.target.checked)}
                        className="rounded accent-[#FC4C02]"
                      />
                      <span>发布时同步更新队员周/月跑量目标</span>
                    </label>

                    <button
                      type="button"
                      disabled={savingOverview}
                      onClick={handleSaveOverviewOnly}
                      className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-200 text-xs font-medium transition cursor-pointer"
                    >
                      {savingOverview ? "保存中..." : "保存草稿修改"}
                    </button>

                    <button
                      type="button"
                      disabled={publishing}
                      onClick={() => handlePublishPlan(false)}
                      className="px-4 py-2 rounded-xl bg-[#FC4C02] hover:bg-[#ff5a14] text-white font-bold text-xs transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>
                        {publishing
                          ? "正在发布..."
                          : workingPlan.status === "draft"
                          ? "审核通过并发布给队员"
                          : "确认修改并同步更新给队员"}
                      </span>
                    </button>
                  </div>
                </div>

                {/* Overview Summary & Coach Review Note */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-zinc-300 block">
                      周期战略设计综述（队员可见，可自由修订）：
                    </label>
                    <textarea
                      rows={3}
                      value={editPlanSummary}
                      onChange={(e) => setEditPlanSummary(e.target.value)}
                      className="w-full bg-[#121215] border border-white/10 rounded-2xl p-3 text-xs text-zinc-200 leading-relaxed focus:outline-none focus:border-white/25"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-zinc-300 block">
                      教练审核叮嘱与执行要求（展示在队员课表顶部）：
                    </label>
                    <textarea
                      rows={2}
                      value={coachReviewNote}
                      onChange={(e) => setCoachReviewNote(e.target.value)}
                      placeholder="输入您对该队员本阶段训练的重点叮嘱、配速纪律或伤病防护提醒..."
                      className="w-full bg-[#121215] border border-white/10 rounded-2xl p-3 text-xs text-white leading-relaxed focus:outline-none focus:border-white/25"
                    />
                    <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                      <span className="text-[10px] text-zinc-500">快捷填入:</span>
                      {QUICK_COACH_NOTE_TEMPLATES.map((tpl, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() =>
                            setCoachReviewNote((prev) => (prev ? `${prev}；${tpl}` : tpl))
                          }
                          className="text-[10px] px-2 py-0.5 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-zinc-200 border border-white/5 transition cursor-pointer"
                        >
                          + {tpl.slice(0, 14)}...
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Step 2: Week Tabs & 1-Click Week Batch Adjust Toolbar */}
              <div className="bg-[#18181c] border border-white/10 rounded-2xl p-4 sm:p-5 space-y-4">
                <div className="flex items-center gap-2 overflow-x-auto pb-1">
                  {weeks.map((w: any) => {
                    const isSelected = w.week_index === selectedWeekIdx;
                    const isCurrent = (workingPlan.current_week_index || 1) === w.week_index;
                    return (
                      <button
                        key={w.week_index}
                        type="button"
                        onClick={() => setSelectedWeekIdx(w.week_index)}
                        className={`shrink-0 px-4 py-2.5 rounded-xl border text-left transition min-w-[115px] cursor-pointer ${
                          isSelected
                            ? "bg-[#FC4C02] text-white border-[#FC4C02]"
                            : "bg-[#121215] border-white/10 text-zinc-400 hover:text-white"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1 text-xs font-bold">
                          <span>第 {w.week_index} 周</span>
                          {isCurrent && (
                            <span className="text-[9px] px-1.5 py-0.2 rounded bg-white/20 text-white">
                              当前周
                            </span>
                          )}
                        </div>
                        <div className={`text-[10px] mt-0.5 ${isSelected ? "text-white/85" : "text-zinc-500"}`}>
                          {w.weekly_mileage_km || 0} km · {(w.phase || "训练").split(" ")[0]}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {activeWeek && (
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-[#121215] p-4 rounded-xl border border-white/10">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-bold text-white">
                          {activeWeek.week_title || `第 ${activeWeek.week_index} 周`}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 font-medium">
                          {activeWeek.phase}
                        </span>
                        <span className="text-xs font-mono font-bold text-[#FC4C02]">
                          本周计划总跑量: {activeWeek.weekly_mileage_km || 0} km
                        </span>
                      </div>
                      <p className="text-xs text-zinc-400 mt-1">
                        本周核心重点：{activeWeek.key_focus || "按节奏完成有氧与专项训练"}
                      </p>
                    </div>

                    {/* 1-Click Coach Batch Adjust Buttons */}
                    <div className="flex items-center gap-2 flex-wrap shrink-0">
                      <span className="text-[11px] text-zinc-500">本周快捷调课:</span>
                      <button
                        type="button"
                        disabled={adjustingWeek}
                        onClick={() => handleWeekBatchAdjust("scale_volume", 0.85)}
                        className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-xs font-medium transition flex items-center gap-1 cursor-pointer"
                      >
                        <TrendingDown className="w-3.5 h-3.5" />
                        本周减量 15%
                      </button>
                      <button
                        type="button"
                        disabled={adjustingWeek}
                        onClick={() => handleWeekBatchAdjust("scale_volume", 1.1)}
                        className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-xs font-medium transition flex items-center gap-1 cursor-pointer"
                      >
                        <TrendingUp className="w-3.5 h-3.5" />
                        本周增量 10%
                      </button>
                      <button
                        type="button"
                        disabled={adjustingWeek}
                        onClick={() => handleWeekBatchAdjust("downgrade_intensity")}
                        className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-xs font-medium transition flex items-center gap-1 cursor-pointer"
                      >
                        <ShieldAlert className="w-3.5 h-3.5" />
                        强度降级为轻松跑
                      </button>
                    </div>
                  </div>
                )}

                {/* 7-Day Workout Cards Grid */}
                {activeWeek && (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-3">
                    {(activeWeek.days || []).map((day: any, dIdx: number) => {
                      const typeMeta = getWorkoutTypeMeta(day.workout_type);
                      const isRest = day.workout_type === "rest";
                      return (
                        <div
                          key={dIdx}
                          className={`p-3.5 rounded-2xl border flex flex-col justify-between transition ${
                            day.completed
                              ? "bg-emerald-950/15 border-emerald-500/30"
                              : day.is_missed
                              ? "bg-rose-950/15 border-rose-500/30"
                              : isRest
                              ? "bg-[#121215]/60 border-white/5"
                              : "bg-[#121215] border-white/10 hover:border-purple-500/40"
                          }`}
                        >
                          <div className="space-y-2">
                            {/* Day Top Bar */}
                            <div className="flex items-center justify-between gap-1">
                              <div>
                                <span className="text-xs font-black text-white">{day.day_of_week}</span>
                                <span className="text-[10px] text-zinc-500 font-mono ml-1">
                                  {day.date ? day.date.slice(5) : ""}
                                </span>
                              </div>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded border font-bold ${typeMeta.badgeClass}`}
                              >
                                {typeMeta.label.split(" ")[0]}
                              </span>
                            </div>

                            {/* Title & Distance */}
                            <div className="text-xs font-bold text-zinc-100 line-clamp-2 min-h-[2rem]">
                              {day.title}
                            </div>

                            {!isRest ? (
                              <div className="space-y-1">
                                <div className="flex items-baseline justify-between">
                                  <span className="text-lg font-black text-[#FC4C02] font-mono">
                                    {day.distance_km || 0}{" "}
                                    <span className="text-[10px] font-normal text-zinc-400">km</span>
                                  </span>
                                  {/* Quick +/- 1km stepper */}
                                  <div className="flex items-center gap-1">
                                    <button
                                      type="button"
                                      onClick={() =>
                                        handleQuickStepDistance(activeWeek.week_index, dIdx, day, -1)
                                      }
                                      className="px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/15 text-[10px] font-mono text-zinc-300 cursor-pointer"
                                      title="减少 1 km"
                                    >
                                      -1k
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() =>
                                        handleQuickStepDistance(activeWeek.week_index, dIdx, day, 1)
                                      }
                                      className="px-1.5 py-0.5 rounded bg-white/5 hover:bg-white/15 text-[10px] font-mono text-zinc-300 cursor-pointer"
                                      title="增加 1 km"
                                    >
                                      +1k
                                    </button>
                                  </div>
                                </div>

                                {day.target_pace && day.target_pace !== "—" && (
                                  <div className="text-[10px] text-zinc-400 truncate">
                                    ⏱️ {day.target_pace}
                                  </div>
                                )}
                                {day.target_hr_zone && day.target_hr_zone !== "—" && (
                                  <div className="text-[10px] text-rose-300/80 truncate">
                                    ❤️ {day.target_hr_zone}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="py-2 text-[11px] text-zinc-500">🛌 休息与筋膜放松</div>
                            )}

                            <p className="text-[11px] text-zinc-400 line-clamp-3 leading-relaxed">
                              {day.description}
                            </p>

                            {day.coach_notes && (
                              <div className="p-2 rounded-xl bg-purple-950/30 border border-purple-500/30 text-[10px] text-purple-200">
                                <strong>👨‍🏫 批注:</strong> {day.coach_notes}
                              </div>
                            )}
                          </div>

                          {/* Card Footer: Execution status & Edit button */}
                          <div className="pt-3 mt-3 border-t border-white/5 flex items-center justify-between gap-1">
                            <span className="text-[10px]">
                              {day.completed ? (
                                <span className="text-emerald-400 font-bold">
                                  ✅ 已完成 {day.actual_distance_km ? `${day.actual_distance_km}k` : ""}
                                </span>
                              ) : day.is_missed ? (
                                <span className="text-rose-400 font-bold">❌ 缺跑</span>
                              ) : (
                                <span className="text-zinc-500">⏳ 待执行</span>
                              )}
                            </span>

                            <button
                              type="button"
                              onClick={() => openDayEditModal(activeWeek.week_index, dIdx, day)}
                              className="px-2 py-1 rounded-lg bg-purple-600/20 hover:bg-purple-600 text-purple-200 hover:text-white text-[10px] font-bold transition flex items-center gap-1 cursor-pointer"
                            >
                              <Edit3 className="w-3 h-3" />
                              改课/批注
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* ── VIEW 3: EXECUTION & COMPLIANCE TRACKING ── */
            <div className="space-y-6">
              {/* Execution Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-[#18181c] border border-white/5 rounded-2xl p-4">
                  <span className="text-xs text-zinc-400 block">第 {selectedWeekIdx} 周计划跑量</span>
                  <span className="text-xl font-black text-white font-mono mt-1 block">
                    {weekExecStats.plannedKm} <span className="text-xs font-normal text-zinc-500">km</span>
                  </span>
                </div>
                <div className="bg-[#18181c] border border-white/5 rounded-2xl p-4">
                  <span className="text-xs text-zinc-400 block">本周实跑完成</span>
                  <span className="text-xl font-black text-emerald-400 font-mono mt-1 block">
                    {weekExecStats.actualKm} <span className="text-xs font-normal text-zinc-500">km</span>
                  </span>
                </div>
                <div className="bg-[#18181c] border border-white/5 rounded-2xl p-4">
                  <span className="text-xs text-zinc-400 block">课表打卡进度</span>
                  <span className="text-xl font-black text-[#FC4C02] font-mono mt-1 block">
                    {weekExecStats.doneRuns} / {weekExecStats.totalRuns}{" "}
                    <span className="text-xs font-normal text-zinc-500">次课 ({weekExecStats.rate}%)</span>
                  </span>
                </div>
                <div className="bg-[#18181c] border border-white/5 rounded-2xl p-4">
                  <span className="text-xs text-zinc-400 block">缺跑未完成</span>
                  <span
                    className={`text-xl font-black font-mono mt-1 block ${
                      weekExecStats.missedRuns > 0 ? "text-rose-400" : "text-zinc-400"
                    }`}
                  >
                    {weekExecStats.missedRuns} <span className="text-xs font-normal text-zinc-500">次</span>
                  </span>
                </div>
              </div>

              {/* Week Selector for Execution View */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {weeks.map((w: any) => (
                  <button
                    key={w.week_index}
                    type="button"
                    onClick={() => setSelectedWeekIdx(w.week_index)}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold border transition cursor-pointer ${
                      w.week_index === selectedWeekIdx
                        ? "bg-emerald-600 text-white border-emerald-400"
                        : "bg-[#18181c] text-zinc-400 border-white/5"
                    }`}
                  >
                    第 {w.week_index} 周 ({w.weekly_mileage_km}km)
                  </button>
                ))}
              </div>

              {/* Detailed Day-by-Day Planned vs Actual Comparison */}
              {activeWeek && (
                <div className="bg-[#18181c] border border-white/10 rounded-3xl overflow-hidden">
                  <div className="p-4 sm:p-5 border-b border-white/10 flex items-center justify-between">
                    <h3 className="text-sm font-black text-white">
                      📊 第 {activeWeek.week_index} 周 · 每日计划课表 vs 队员实际执行对比
                    </h3>
                    <span className="text-xs text-zinc-400">
                      系统自动同步队员手表上传记录并与当日课表比对
                    </span>
                  </div>

                  <div className="divide-y divide-white/5">
                    {(activeWeek.days || []).map((day: any, dIdx: number) => {
                      const typeMeta = getWorkoutTypeMeta(day.workout_type);
                      const isRest = day.workout_type === "rest";
                      return (
                        <div
                          key={dIdx}
                          className="p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 hover:bg-white/[0.02] transition"
                        >
                          {/* Left: Planned Workout */}
                          <div className="flex items-start gap-3.5 flex-1">
                            <div className="w-14 text-center shrink-0 bg-[#121215] rounded-xl p-2 border border-white/5">
                              <span className="text-xs font-black text-white block">{day.day_of_week}</span>
                              <span className="text-[10px] text-zinc-500 font-mono">
                                {day.date ? day.date.slice(5) : ""}
                              </span>
                            </div>
                            <div className="space-y-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span
                                  className={`text-[10px] px-2 py-0.5 rounded border font-bold ${typeMeta.badgeClass}`}
                                >
                                  {typeMeta.label}
                                </span>
                                <span className="text-sm font-bold text-white">{day.title}</span>
                                {!isRest && (
                                  <span className="text-xs font-mono font-bold text-[#FC4C02]">
                                    计划 {day.distance_km} km
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-zinc-400">{day.description}</p>
                              {day.coach_notes && (
                                <p className="text-xs text-purple-300">👨‍🏫 教练批注：{day.coach_notes}</p>
                              )}
                            </div>
                          </div>

                          {/* Right: Actual Execution Result & Coach Action */}
                          <div className="flex items-center gap-3 self-end lg:self-center shrink-0">
                            {isRest ? (
                              <span className="px-3 py-1.5 rounded-xl bg-zinc-800/80 text-zinc-400 text-xs font-bold">
                                🛌 休息恢复日
                              </span>
                            ) : day.completed ? (
                              <div className="bg-emerald-500/15 border border-emerald-500/30 rounded-2xl px-4 py-2 text-xs">
                                <div className="font-bold text-emerald-300 flex items-center gap-1.5">
                                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                  <span>
                                    已执行打卡{" "}
                                    {day.actual_distance_km
                                      ? `· 实跑 ${day.actual_distance_km} km`
                                      : `· ${day.distance_km} km`}
                                  </span>
                                </div>
                                {(day.actual_pace || day.actual_heartrate) && (
                                  <div className="text-[11px] text-emerald-200/80 mt-0.5 font-mono">
                                    {day.actual_pace ? `配速 ${day.actual_pace}` : ""}{" "}
                                    {day.actual_heartrate ? `· 均心 ${day.actual_heartrate} bpm` : ""}
                                  </div>
                                )}
                              </div>
                            ) : day.is_missed ? (
                              <div className="bg-rose-500/15 border border-rose-500/30 rounded-2xl px-4 py-2 text-xs text-rose-300 font-bold">
                                ❌ 未能按计划打卡 (缺跑)
                              </div>
                            ) : (
                              <div className="bg-white/5 border border-white/10 rounded-2xl px-4 py-2 text-xs text-zinc-400">
                                ⏳ 待执行 ({day.date || "近期"})
                              </div>
                            )}

                            <button
                              type="button"
                              onClick={() => openDayEditModal(activeWeek.week_index, dIdx, day)}
                              className="px-3 py-2 rounded-xl bg-white/5 hover:bg-purple-600/30 border border-white/10 text-zinc-200 text-xs font-bold transition cursor-pointer"
                            >
                              点评 / 调整
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Single Day Workout Edit Modal (Nested) ── */}
        {editingDay && (
          <div className="fixed inset-0 z-60 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[#18181c] border border-purple-500/40 rounded-3xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto space-y-4 shadow-2xl">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <h3 className="text-base font-black text-white">
                  ✏️ 编辑单日课表与体感 · 第 {editingDay.weekIdx} 周 {editingDay.day.day_of_week} (
                  {editingDay.day.date})
                </h3>
                <button
                  onClick={() => setEditingDay(null)}
                  className="p-1.5 text-zinc-400 hover:text-white rounded-full bg-white/5 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3.5 text-xs">
                <div>
                  <label className="text-zinc-400 block mb-1.5 font-bold">课表类型</label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {WORKOUT_TYPES.map((wt) => (
                      <button
                        key={wt.id}
                        type="button"
                        onClick={() => {
                          setDayWorkoutType(wt.id);
                          if (wt.id === "rest") setDayDistanceKm(0);
                        }}
                        className={`p-2 rounded-xl border text-[11px] font-bold transition cursor-pointer ${
                          dayWorkoutType === wt.id
                            ? "bg-purple-600 text-white border-purple-400"
                            : "bg-[#121215] text-zinc-400 border-white/5"
                        }`}
                      >
                        {wt.label.split(" ")[0]}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="text-zinc-400 block mb-1 font-bold">课表标题</label>
                    <input
                      type="text"
                      value={dayTitle}
                      onChange={(e) => setDayTitle(e.target.value)}
                      className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="text-zinc-400 block mb-1 font-bold">计划里程 (km)</label>
                    <input
                      type="number"
                      step="0.5"
                      value={dayDistanceKm}
                      onChange={(e) => setDayDistanceKm(e.target.value)}
                      disabled={dayWorkoutType === "rest"}
                      className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white font-mono"
                    />
                  </div>
                </div>

                {dayWorkoutType !== "rest" && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-zinc-400 block mb-1 font-bold">目标配速要求</label>
                      <input
                        type="text"
                        value={dayTargetPace}
                        onChange={(e) => setDayTargetPace(e.target.value)}
                        placeholder="如: 4'50-5'00 /km"
                        className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-zinc-400 block mb-1 font-bold">目标心率区间</label>
                      <input
                        type="text"
                        value={dayTargetHrZone}
                        onChange={(e) => setDayTargetHrZone(e.target.value)}
                        placeholder="如: Z2 (135-148 bpm)"
                        className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white"
                      />
                    </div>
                  </div>
                )}

                <div>
                  <label className="text-zinc-400 block mb-1 font-bold">具体训练内容与执行说明</label>
                  <textarea
                    rows={2}
                    value={dayDescription}
                    onChange={(e) => setDayDescription(e.target.value)}
                    className="w-full bg-[#121215] border border-white/10 rounded-xl p-2.5 text-white leading-relaxed"
                  />
                </div>

                {/* W19 Execution, RPE & Biometrics Block */}
                <div className="p-3.5 rounded-2xl bg-[#121215] border border-emerald-500/25 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-black text-emerald-300 text-xs">
                      📊 计划执行情况、身体指标与主观体感 (RPE)
                    </span>
                    <div className="flex items-center gap-2">
                      {(editingDay.day?.is_swapped ||
                        String(editingDay.day?.athlete_notes || "").includes("对换课表")) && (
                        <button
                          type="button"
                          onClick={async () => {
                            if (!workingPlan?.id) return;
                            setSavingDay(true);
                            try {
                              const res = await apiClient.patch(
                                `/api/coach/plan/${workingPlan.id}/workout`,
                                {
                                  week_index: editingDay.weekIdx,
                                  day_index: editingDay.dayIdx,
                                  undo_swap: true,
                                  operator_uid: coachUid,
                                }
                              );
                              if (res.data?.plan) {
                                if (workingPlan.status === "draft") {
                                  setDraftPlan(res.data.plan);
                                } else {
                                  setActivePlan(res.data.plan);
                                }
                                setEditingDay(null);
                                showToast("↩️ 已取消对换并恢复原课表");
                                triggerUpdated();
                              }
                            } catch (e: any) {
                              notifyToast(e.response?.data?.detail || "取消对换失败");
                            } finally {
                              setSavingDay(false);
                            }
                          }}
                          className="px-2 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-[11px] font-bold transition cursor-pointer"
                        >
                          ↩️ 取消对换
                        </button>
                      )}
                      <span className="text-[11px] text-zinc-400">🔄 课表调休对换:</span>
                      <select
                        value={daySwapWithIdx}
                        onChange={(e) => setDaySwapWithIdx(e.target.value)}
                        className="bg-[#18181c] border border-white/10 rounded-lg px-2 py-1 text-[11px] text-white"
                      >
                        <option value="">不对换</option>
                        {(editingDay.day?.is_swapped ||
                          String(editingDay.day?.athlete_notes || "").includes("对换课表")) && (
                          <option value="undo">↩️ 取消对换 · 恢复原课表</option>
                        )}
                        {["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map((lbl, idx) =>
                          idx !== editingDay.dayIdx ? (
                            <option key={idx} value={String(idx)}>
                              与 {lbl} 对换
                            </option>
                          ) : null
                        )}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div className="sm:col-span-3">
                      <label className="text-zinc-400 block mb-1 font-bold">
                        计划执行情况 (如: 15km*602, hr132 或 慢跑4.3km*554 / 身训2组)
                      </label>
                      <input
                        type="text"
                        value={dayActualExecText}
                        onChange={(e) => setDayActualExecText(e.target.value)}
                        placeholder="手表同步或手动填写执行详情..."
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-emerald-300 font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-zinc-400 block mb-1 font-bold">RPE (1-10)</label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={dayRpe}
                        onChange={(e) => setDayRpe(e.target.value)}
                        placeholder="如: 7"
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                    <div>
                      <label className="text-zinc-500 block mb-1 text-[11px]">HRV (ms)</label>
                      <input
                        type="number"
                        value={dayHrv}
                        onChange={(e) => setDayHrv(e.target.value)}
                        placeholder="37"
                        className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2.5 py-1.5 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-zinc-500 block mb-1 text-[11px]">静心 RHR</label>
                      <input
                        type="number"
                        value={dayRestingHr}
                        onChange={(e) => setDayRestingHr(e.target.value)}
                        placeholder="50"
                        className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2.5 py-1.5 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-zinc-500 block mb-1 text-[11px]">呼吸</label>
                      <input
                        type="number"
                        step="0.1"
                        value={dayRespRate}
                        onChange={(e) => setDayRespRate(e.target.value)}
                        placeholder="13.8"
                        className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2.5 py-1.5 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-zinc-500 block mb-1 text-[11px]">压力 (0-21)</label>
                      <input
                        type="number"
                        step="0.1"
                        value={dayStrain}
                        onChange={(e) => setDayStrain(e.target.value)}
                        placeholder="14.0"
                        className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2.5 py-1.5 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-zinc-500 block mb-1 text-[11px]">恢复 (%)</label>
                      <input
                        type="number"
                        min={0}
                        max={100}
                        value={dayRecoveryPct}
                        onChange={(e) => setDayRecoveryPct(e.target.value)}
                        placeholder="83"
                        className="w-full bg-[#18181c] border border-white/10 rounded-lg px-2.5 py-1.5 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-zinc-400 block mb-1 font-bold">
                      备注 · 队员训练自我感受 (如: 臀腿核心延迟性酸胀，后3公里落地弹性减弱)
                    </label>
                    <textarea
                      rows={2}
                      value={dayAthleteNotes}
                      onChange={(e) => setDayAthleteNotes(e.target.value)}
                      placeholder="记录当日身体感受、酸胀部位、配速与呼吸体感..."
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl p-2.5 text-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-purple-300 block mb-1 font-bold">
                    👨‍🏫 教练单日专属批注 / 点评（队员在当日课表可见）
                  </label>
                  <textarea
                    rows={2}
                    value={dayCoachNotes}
                    onChange={(e) => setDayCoachNotes(e.target.value)}
                    placeholder="例如：今天降温风大，热身延长到3公里，主课注意步频..."
                    className="w-full bg-[#121215] border border-purple-500/30 rounded-xl p-2.5 text-white"
                  />
                </div>

                <label className="flex items-center gap-2 text-zinc-300 pt-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={dayCompleted}
                    onChange={(e) => setDayCompleted(e.target.checked)}
                    className="rounded accent-emerald-500"
                  />
                  <span>标记该日课表为已完成打卡</span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setEditingDay(null)}
                  className="px-4 py-2 rounded-xl bg-white/5 text-zinc-300 text-xs font-bold cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="button"
                  disabled={savingDay}
                  onClick={handleSaveDayWorkout}
                  className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-black shadow-lg cursor-pointer"
                >
                  {savingDay ? "保存中..." : "保存单日课表与体感"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
