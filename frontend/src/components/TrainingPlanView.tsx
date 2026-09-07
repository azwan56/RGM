"use client";

import { useEffect, useState } from "react";
import apiClient from "@/lib/apiClient";
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

  // Edit workout modal state
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
  const [savingWorkout, setSavingWorkout] = useState(false);

  useEffect(() => {
    if (user?.id) {
      loadUserPlan(user.id);
    }
  }, [user]);

  async function loadUserPlan(uid: string) {
    setLoading(true);
    try {
      const res = await apiClient.get(`/api/coach/plan/user/${uid}`);
      if (res.data?.active_plan) {
        setPlan(res.data.active_plan);
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
      alert(err.response?.data?.detail || "同步失败，请稍后重试");
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

      const res = await apiClient.post("/api/coach/plan/generate", payload);
      if (res.data?.success && res.data?.plan) {
        setPlan(res.data.plan);
        setSelectedWeekIdx(1);
        setShowConfig(false);
      }
    } catch (err) {
      console.error("Generate plan error:", err);
      alert("生成训练计划失败，请稍后重试！");
    } finally {
      setGenerating(false);
    }
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
    setEditingModalOpen(true);
  }

  async function handleSaveWorkout() {
    if (!plan?.id || !user?.id) return;
    setSavingWorkout(true);
    try {
      const payload = {
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
        operator_uid: user.id
      };
      const res = await apiClient.patch(`/api/coach/plan/${plan.id}/workout`, payload);
      if (res.data?.success && res.data?.plan) {
        setPlan(res.data.plan);
        setEditingModalOpen(false);
      }
    } catch (err) {
      console.error("Failed to update workout:", err);
      alert("保存课表更新失败，请重试！");
    } finally {
      setSavingWorkout(false);
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
      }
    } catch (err) {
      console.error("Failed to toggle completion:", err);
    }
  }

  const currentWeeks = plan?.schedule_data?.weeks || [];
  const activeWeek = currentWeeks.find((w: any) => w.week_index === selectedWeekIdx) || currentWeeks[0];

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
            <div className="flex items-center gap-2">
              <h2 className="text-base font-black text-white">
                {plan ? plan.title : "个人科学周期训练计划"}
              </h2>
              {plan && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  执行中 · {plan.weeks_count}周周期
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Canova 专项性推进 · 结合 18 个月实战比赛表现与动态负荷自适应 · 跑者与教练双向协同
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          {plan && (
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="flex-1 sm:flex-none px-4 py-2 rounded-xl text-xs font-bold border border-white/10 text-zinc-300 bg-[#18181c] hover:border-purple-500/50 hover:text-white transition flex items-center justify-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
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

          {/* Goal Type Switcher */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-zinc-400 block">
              1. 核心目标类型 (Goal Type)
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setGoalType("race_prep")}
                className={`p-4 rounded-2xl border text-left transition flex items-start gap-3 ${
                  goalType === "race_prep"
                    ? "bg-purple-600/10 border-purple-500 text-white shadow-lg shadow-purple-900/20"
                    : "bg-[#18181c] border-white/5 text-zinc-400 hover:border-white/15"
                }`}
              >
                <div className={`p-2.5 rounded-xl ${goalType === "race_prep" ? "bg-purple-500 text-white" : "bg-zinc-800 text-zinc-400"}`}>
                  <Trophy className="w-5 h-5" />
                </div>
                <div>
                  <div className="font-bold text-sm text-white flex items-center gap-2">
                    赛事突破备战 (Race Preparation)
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-normal">全马/半马/越野</span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                    以既定比赛为导向，由比赛日倒排周期：基础构建 → 乳酸门槛 → 比赛专项收敛 → 赛前 2~3 周减量。
                  </p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => setGoalType("fitness_maintenance")}
                className={`p-4 rounded-2xl border text-left transition flex items-start gap-3 ${
                  goalType === "fitness_maintenance"
                    ? "bg-emerald-600/10 border-emerald-500 text-white shadow-lg shadow-emerald-900/20"
                    : "bg-[#18181c] border-white/5 text-zinc-400 hover:border-white/15"
                }`}
              >
                <div className={`p-2.5 rounded-xl ${goalType === "fitness_maintenance" ? "bg-emerald-500 text-white" : "bg-zinc-800 text-zinc-400"}`}>
                  <Mountain className="w-5 h-5" />
                </div>
                <div>
                  <div className="font-bold text-sm text-white flex items-center gap-2">
                    非赛季体能与专项能力进阶 (Off-Season / Trail)
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-normal">无比赛周期</span>
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
                    🚩 从您已登记的赛历中快速套用：
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {userRaces.map((r: any) => (
                      <button
                        key={r.id || r.name}
                        type="button"
                        onClick={() => {
                          setTargetRaceName(r.name);
                          if (r.target_time) setTargetTime(r.target_time);
                          if (r.race_date) setTargetDate(r.race_date);
                          if (r.race_type) setRaceType(r.race_type);
                        }}
                        className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition ${
                          targetRaceName === r.name
                            ? "bg-purple-600/30 border-purple-500 text-purple-200"
                            : "bg-[#121215] border-white/10 text-zinc-400 hover:text-white"
                        }`}
                      >
                        {r.name} · {r.target_time || "目标"}
                      </button>
                    ))}
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
                <span className="text-[10px] text-zinc-400 block font-bold">跑者周岁</span>
                <span className="text-sm font-black text-white">
                  {plan.schedule_data.current_fitness_snapshot.age ? `${plan.schedule_data.current_fitness_snapshot.age} 岁` : "—"}
                </span>
                <span className="text-[9px] text-zinc-500 block mt-0.5">
                  {plan.schedule_data.current_fitness_snapshot.age >= 50 ? "Masters 72-96h 恢复律" : "常规恢复"}
                </span>
              </div>

              <div className="bg-[#18181c] p-3 rounded-2xl border border-white/5">
                <span className="text-[10px] text-zinc-400 block font-bold">VO2Max 摄氧量</span>
                <span className="text-sm font-black text-purple-400">
                  {plan.schedule_data.current_fitness_snapshot.vo2max || "—"}
                </span>
                <span className="text-[9px] text-zinc-500 block mt-0.5">Daniels VDOT 模型基准</span>
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

          {/* Goal Summary Quote */}
          {plan.overview_summary && (
            <div className="p-5 rounded-3xl bg-purple-950/20 border border-purple-500/20 text-xs space-y-1.5">
              <div className="font-bold text-purple-300 flex items-center gap-2">
                <Target className="w-4 h-4 text-purple-400" />
                Canova 周期战术设计综述：
              </div>
              <p className="text-zinc-300 leading-relaxed font-light">
                {plan.overview_summary}
              </p>
            </div>
          )}

          {/* ── Week Tabs Bar ── */}
          <div className="bg-[#121215] border border-white/[0.08] p-3 sm:p-4 rounded-3xl">
            <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
              {currentWeeks.map((w: any) => {
                const isActive = w.week_index === selectedWeekIdx;
                const hasRace = (w.days || []).some((d: any) => d.workout_type === "race");
                return (
                  <button
                    key={w.week_index}
                    onClick={() => setSelectedWeekIdx(w.week_index)}
                    className={`shrink-0 px-4 py-2.5 rounded-2xl border text-xs font-bold transition flex flex-col items-start min-w-[110px] relative ${
                      isActive
                        ? "bg-purple-600 text-white border-purple-500 shadow-lg shadow-purple-600/30"
                        : hasRace
                        ? "bg-rose-950/20 border-rose-500/30 text-rose-200 hover:border-rose-500/50"
                        : "bg-[#18181c] border-white/5 text-zinc-400 hover:text-white hover:border-white/15"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 w-full justify-between">
                      <span>第 {w.week_index} 周</span>
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
                        <span className="text-[10px] text-zinc-500 block font-bold">自定周目标</span>
                        <span className="text-sm font-black text-emerald-400">
                          {userGoal?.weekly_target || 50} km
                        </span>
                      </div>
                      <div className="w-px h-6 bg-white/10" />
                      <div className="text-right">
                        <span className="text-[10px] text-zinc-500 block font-bold">训练天数</span>
                        <span className="text-sm font-black text-purple-400">
                          {(activeWeek.days || []).filter((d: any) => d.workout_type !== "rest").length} 天
                        </span>
                      </div>
                    </div>

                    {/* Sync to Goals Button */}
                    <button
                      onClick={handleSyncToGoals}
                      disabled={syncingGoal}
                      title="将当前训练计划的平均跑量与各月跑量同步为我的个人周/月目标"
                      className="px-3.5 py-2 rounded-2xl bg-gradient-to-r from-purple-600/30 to-indigo-600/30 hover:from-purple-600/50 hover:to-indigo-600/50 border border-purple-500/30 text-purple-200 text-xs font-bold transition flex items-center gap-1.5 shadow-sm active:scale-95 disabled:opacity-50"
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

              {/* Daily 7-day Workout Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-3">
                {(activeWeek.days || []).map((day: any, dIdx: number) => {
                  const typeMeta = workoutTypeStyles[day.workout_type] || workoutTypeStyles.easy_run;
                  const isRest = day.workout_type === "rest";

                  return (
                    <div
                      key={dIdx}
                      className={`bg-[#121215] border rounded-3xl p-4 flex flex-col justify-between transition-all hover:border-purple-500/40 ${
                        day.completed ? "border-emerald-500/30 bg-emerald-950/5" : typeMeta.border
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
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${typeMeta.badge}`}>
                            {typeMeta.label}
                          </span>
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

                        {/* Pace & Heart Rate Pills */}
                        {!isRest && (day.target_pace || day.target_hr_zone) && (
                          <div className="space-y-1 text-[10px]">
                            {day.target_pace && day.target_pace !== "—" && (
                              <div className="bg-[#18181c] px-2 py-1 rounded-lg border border-white/5 text-purple-300 font-medium">
                                ⏱️ {day.target_pace}
                              </div>
                            )}
                            {day.target_hr_zone && day.target_hr_zone !== "—" && (
                              <div className="bg-[#18181c] px-2 py-1 rounded-lg border border-white/5 text-emerald-300 font-medium truncate">
                                ❤️ {day.target_hr_zone}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Description */}
                        <p className="text-[11px] text-zinc-400 leading-relaxed font-light line-clamp-4">
                          {day.description}
                        </p>

                        {/* Coach Notes Bubble (if any) */}
                        {day.coach_notes && (
                          <div className="bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-xl text-[10px] text-amber-200 space-y-1">
                            <div className="font-bold flex items-center gap-1 text-amber-300">
                              <span>👨‍🏫 教练批注：</span>
                            </div>
                            <p className="leading-snug">{day.coach_notes}</p>
                          </div>
                        )}
                      </div>

                      {/* Card Footer Actions */}
                      <div className="pt-3 border-t border-white/5 mt-3 flex items-center justify-between gap-1">
                        <button
                          type="button"
                          onClick={() => handleToggleQuickComplete(activeWeek.week_index, dIdx, day)}
                          className={`flex-1 py-1 px-2 rounded-xl text-[10px] font-bold border transition flex items-center justify-center gap-1 ${
                            day.completed
                              ? "bg-emerald-500/20 border-emerald-500 text-emerald-300"
                              : "bg-[#18181c] border-white/10 text-zinc-400 hover:text-white"
                          }`}
                          title={day.completed ? "点击取消完成状态" : "点击打卡完成"}
                        >
                          <Check className={`w-3 h-3 ${day.completed ? "text-emerald-400" : "text-zinc-500"}`} />
                          {day.completed ? "已完成" : "打卡"}
                        </button>

                        <button
                          type="button"
                          onClick={() => handleOpenEditModal(activeWeek.week_index, dIdx, day)}
                          className="p-1.5 rounded-xl text-[10px] border border-white/10 text-zinc-400 hover:text-white hover:border-purple-500 bg-[#18181c] transition"
                          title="微调课表 / 添加教练批注"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
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

      {/* ── Collaborative Edit Modal ── */}
      {editingModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-[#18181c] border border-white/10 rounded-3xl max-w-lg w-full p-6 space-y-5 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <div className="flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-purple-400" />
                <h4 className="text-sm font-bold text-white">
                  微调训练课目与教练指导 (第 {editWeekIdx} 周)
                </h4>
              </div>
              <button
                onClick={() => setEditingModalOpen(false)}
                className="p-1.5 rounded-xl text-zinc-400 hover:text-white bg-[#121215]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3.5 text-xs">
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

              <div>
                <label className="text-zinc-400 block mb-1">训练课标题</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
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
                <div>
                  <label className="text-zinc-400 block mb-1">目标心率区间</label>
                  <input
                    type="text"
                    value={editTargetHrZone}
                    onChange={(e) => setEditTargetHrZone(e.target.value)}
                    placeholder="如: 135-145 bpm"
                    className="w-full bg-[#121215] border border-white/10 rounded-xl px-3 py-2 text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-zinc-400 block mb-1">课目详情与热身冷身说明</label>
                <textarea
                  rows={3}
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  className="w-full bg-[#121215] border border-white/10 rounded-xl p-3 text-white placeholder-zinc-600 focus:outline-none focus:border-purple-500 resize-none"
                />
              </div>

              {/* Coach Notes */}
              <div className="bg-amber-500/5 border border-amber-500/20 p-3 rounded-2xl space-y-1.5">
                <label className="text-amber-300 font-bold block flex items-center gap-1.5">
                  <span>👨‍🏫 跑团教练寄语与战术微调批注 (Coach Notes)</span>
                </label>
                <textarea
                  rows={2}
                  value={editCoachNotes}
                  onChange={(e) => setEditCoachNotes(e.target.value)}
                  placeholder="在此输入教练指导建议，例如：针对大师组心率反应，今天前5km务必压住速度..."
                  className="w-full bg-[#121215] border border-white/10 rounded-xl p-2.5 text-xs text-amber-100 placeholder-zinc-600 focus:outline-none focus:border-amber-500 resize-none"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <label className="flex items-center gap-2 text-zinc-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editCompleted}
                    onChange={(e) => setEditCompleted(e.target.checked)}
                    className="rounded bg-[#121215] border-white/10 text-purple-600 focus:ring-0"
                  />
                  <span>标记该项训练为已完成打卡</span>
                </label>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2 border-t border-white/5">
              <button
                type="button"
                onClick={() => setEditingModalOpen(false)}
                className="px-4 py-2 rounded-xl border border-white/10 text-xs text-zinc-400 hover:text-white"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleSaveWorkout}
                disabled={savingWorkout}
                className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs transition shadow-lg shadow-purple-600/30 flex items-center gap-1.5"
              >
                {savingWorkout ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    保存中...
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    保存课表修改
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
