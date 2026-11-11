"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import apiClient, { formatBeijingTime } from "@/lib/apiClient";
import {
  Upload,
  Sparkles,
  Calendar,
  Users,
  CheckCircle2,
  Edit3,
  FileText,
  Image as ImageIcon,
  Loader2,
  X,
  Check,
  Dumbbell,
  MapPin,
  AlertCircle,
  Send,
  BookmarkPlus,
} from "lucide-react";

interface CoachScheduleImportModalProps {
  isOpen: boolean;
  clubId: string;
  coachUid: string;
  students: any[];
  onClose: () => void;
  onAssignedSuccess: () => void;
}

const WORKOUT_TYPE_OPTIONS = [
  { value: "easy_run", label: "轻松跑" },
  { value: "tempo_run", label: "节奏跑" },
  { value: "interval", label: "间歇跑" },
  { value: "long_run", label: "耐力/LSD" },
  { value: "cross_training", label: "体能/交叉" },
  { value: "rest", label: "休息" },
];

export default function CoachScheduleImportModal({
  isOpen,
  clubId,
  coachUid,
  students = [],
  onClose,
  onAssignedSuccess,
}: CoachScheduleImportModalProps) {
  const [inputMode, setInputMode] = useState<"image" | "text">("image");
  const [imagePreview, setImagePreview] = useState<string>("");
  const [rawText, setRawText] = useState<string>("");
  const [presets, setPresets] = useState<any[]>([]);
  const [activePresetId, setActivePresetId] = useState<string>("");
  const [parsing, setParsing] = useState<boolean>(false);
  const [parseError, setParseError] = useState<string>("");

  // Parsed state
  const [parsedData, setParsedData] = useState<any | null>(null);
  const [planTitle, setPlanTitle] = useState<string>("");
  const [sourceWeekIndex, setSourceWeekIndex] = useState<number>(2);
  const [coachReviewNote, setCoachReviewNote] = useState<string>("");
  const [dateAnchorMode, setDateAnchorMode] = useState<"next_week" | "parsed_date" | "current_week" | "custom">("next_week");
  const [customMonday, setCustomMonday] = useState<string>("");
  const [groups, setGroups] = useState<any[]>([]);
  const [selectedGroupCode, setSelectedGroupCode] = useState<string>("");

  // Member -> group_code mapping (or "" for skip)
  const [memberGroupMap, setMemberGroupMap] = useState<Record<string, string>>({});
  const [memberFilterGroup, setMemberFilterGroup] = useState<string>("all");
  const [memberSearch, setMemberSearch] = useState<string>("");
  const [saveAsTemplates, setSaveAsTemplates] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [lastDispatchResult, setLastDispatchResult] = useState<any | null>(null);
  const [rollingBackBatchId, setRollingBackBatchId] = useState<string | null>(null);
  const [showBatchHistory, setShowBatchHistory] = useState<boolean>(false);
  const [recentBatches, setRecentBatches] = useState<any[]>([]);
  const [loadingBatches, setLoadingBatches] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchPresets();
      fetchRecentBatches();
      setLastDispatchResult(null);
    }
  }, [isOpen]);

  async function fetchRecentBatches() {
    if (!clubId) return;
    setLoadingBatches(true);
    try {
      const res = await apiClient.get(`/api/coach/plan/club-batches?club_id=${clubId}&limit=10`);
      if (res.data?.batches) {
        setRecentBatches(res.data.batches);
      }
    } catch (err) {
      console.error("Failed to load recent batches:", err);
    } finally {
      setLoadingBatches(false);
    }
  }

  async function handleRollbackBatch(batchId: string) {
    if (!batchId || rollingBackBatchId) return;
    setRollingBackBatchId(batchId);
    try {
      const res = await apiClient.post(`/api/coach/plan/club-batches/${batchId}/rollback`, {
        operator_uid: coachUid,
      });
      alert(res.data?.message || "✅ 已成功撤回该批次派发，队员原课表已完整恢复！");
      if (lastDispatchResult?.batch_id === batchId) {
        setLastDispatchResult(null);
      }
      await fetchRecentBatches();
      onAssignedSuccess();
    } catch (err: any) {
      alert(err.response?.data?.detail || "撤回派发失败，请稍后重试");
    } finally {
      setRollingBackBatchId(null);
    }
  }

  async function fetchPresets() {
    try {
      const res = await apiClient.get("/api/coach/plan/import-presets");
      if (res.data?.presets) {
        setPresets(res.data.presets);
      }
    } catch (err) {
      console.error("Failed to load schedule presets:", err);
    }
  }

  function applyParsedResult(resData: any) {
    const p = resData.parsed_schedule;
    if (!p) return;
    setParsedData(p);
    setPlanTitle(p.plan_title || "周训练计划");
    setSourceWeekIndex(p.source_week_index || 1);
    setCoachReviewNote(p.coach_review_note || "");
    setGroups(p.groups || []);
    if (p.groups && p.groups.length > 0) {
      setSelectedGroupCode(p.groups[0].group_code);
    }
    if (p.raw_text) {
      setRawText(p.raw_text);
    }
    // Default date anchor: if parsed_monday exists, offer it; default to next_week for Sunday workflow
    if (p.parsed_monday) {
      setDateAnchorMode("parsed_date");
      setCustomMonday(p.parsed_monday);
    } else {
      setDateAnchorMode("next_week");
      setCustomMonday(p.next_monday || "");
    }

    // Initialize member mapping
    const recMap = resData.recommended_member_mapping || {};
    const initialMap: Record<string, string> = {};
    const validCodes = (p.groups || []).map((g: any) => g.group_code);
    students.forEach((s: any) => {
      const uid = s.user_id;
      if (recMap[uid] && validCodes.includes(recMap[uid])) {
        initialMap[uid] = recMap[uid];
      } else if (s.training_group && validCodes.includes(s.training_group)) {
        initialMap[uid] = s.training_group;
      } else if (validCodes.length > 0) {
        initialMap[uid] = validCodes[0];
      }
    });
    setMemberGroupMap(initialMap);
  }

  async function handleParseSchedule(opts?: { presetId?: string; imgB64?: string; textOverride?: string }) {
    setParsing(true);
    setParseError("");
    try {
      const payload: any = {
        club_id: clubId,
        operator_uid: coachUid,
      };
      if (opts?.presetId) {
        payload.preset_id = opts.presetId;
      } else if (opts?.imgB64) {
        payload.image_base64 = opts.imgB64;
      } else if (opts?.textOverride !== undefined) {
        payload.raw_text = opts.textOverride;
      } else if (inputMode === "image" && imagePreview) {
        payload.image_base64 = imagePreview;
      } else if (rawText.trim()) {
        payload.raw_text = rawText.trim();
      } else {
        setParseError("请先上传课表截图、粘贴课表文字，或点击上方示例课表");
        setParsing(false);
        return;
      }

      const res = await apiClient.post("/api/coach/plan/import-weekly-schedule", payload);
      applyParsedResult(res.data);
    } catch (err: any) {
      setParseError(err.response?.data?.detail || "识别课表失败，请检查图片清晰度或改用文字粘贴");
    } finally {
      setParsing(false);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    readImageFile(file);
  }

  function readImageFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = String(reader.result || "");
      setImagePreview(b64);
      setInputMode("image");
      setActivePresetId("");
      handleParseSchedule({ imgB64: b64 });
    };
    reader.readAsDataURL(file);
  }

  function handlePasteClipboard(e: React.ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.indexOf("image") !== -1) {
        const file = item.getAsFile();
        if (file) {
          e.preventDefault();
          readImageFile(file);
          return;
        }
      }
    }
  }

  const effectiveMonday = useMemo(() => {
    if (!parsedData) return customMonday;
    if (dateAnchorMode === "next_week") return parsedData.next_monday;
    if (dateAnchorMode === "current_week") return parsedData.current_monday;
    if (dateAnchorMode === "parsed_date") return parsedData.parsed_monday || parsedData.default_monday;
    return customMonday || parsedData.default_monday;
  }, [parsedData, dateAnchorMode, customMonday]);

  function addDaysIso(mondayIso: string, offset: number): string {
    if (!mondayIso) return "";
    const parts = mondayIso.split("-").map(Number);
    if (parts.length !== 3) return mondayIso;
    const dt = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] + offset));
    return dt.toISOString().slice(0, 10);
  }

  const effectiveSunday = useMemo(() => addDaysIso(effectiveMonday, 6), [effectiveMonday]);

  const activeGroupObj = useMemo(
    () => groups.find((g) => g.group_code === selectedGroupCode) || groups[0] || null,
    [groups, selectedGroupCode]
  );

  function handleUpdateDayField(groupCode: string, dayIdx: number, field: string, value: any) {
    setGroups((prev) =>
      prev.map((g) => {
        if (g.group_code !== groupCode) return g;
        const nextDays = (g.days || []).map((d: any, idx: number) => {
          if (idx !== dayIdx) return d;
          const updated = { ...d, [field]: value };
          if (field === "workout_type" && value === "rest") {
            updated.distance_km = 0;
            updated.target_pace = "—";
          }
          return updated;
        });
        const totKm =
          Math.round(
            nextDays.reduce(
              (acc: number, d: any) => acc + (d.workout_type === "rest" ? 0 : Number(d.distance_km) || 0),
              0
            ) * 10
          ) / 10;
        const runDays = nextDays.filter(
          (d: any) => d.workout_type !== "rest" && (Number(d.distance_km) || 0) > 0
        ).length;
        return {
          ...g,
          days: nextDays,
          weekly_km: totKm,
          days_per_week: runDays,
        };
      })
    );
  }

  async function handleSetMemberGroup(uid: string, groupCode: string) {
    setMemberGroupMap((prev) => ({
      ...prev,
      [uid]: groupCode,
    }));
    // Also persist to club_memberships in background if a real group is chosen
    if (clubId && groupCode) {
      try {
        await apiClient.post(`/api/team/${clubId}/member-group`, {
          operator_uid: coachUid,
          target_uid: uid,
          training_group: groupCode,
        });
      } catch (err) {
        // non-blocking
      }
    }
  }

  const groupMemberCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    groups.forEach((g) => {
      counts[g.group_code] = 0;
    });
    Object.values(memberGroupMap).forEach((code) => {
      if (code && counts[code] !== undefined) {
        counts[code] += 1;
      }
    });
    return counts;
  }, [groups, memberGroupMap]);

  const totalSelectedMembers = useMemo(
    () => Object.values(memberGroupMap).filter((code) => Boolean(code)).length,
    [memberGroupMap]
  );

  const filteredStudents = useMemo(() => {
    return students.filter((s: any) => {
      const assigned = memberGroupMap[s.user_id] || "";
      if (memberFilterGroup === "unassigned" && assigned !== "") return false;
      if (memberFilterGroup !== "all" && memberFilterGroup !== "unassigned" && assigned !== memberFilterGroup) {
        return false;
      }
      if (memberSearch.trim()) {
        const q = memberSearch.trim().toLowerCase();
        const nameMatch = String(s.display_name || "").toLowerCase().includes(q);
        const grpMatch = assigned.toLowerCase().includes(q);
        return nameMatch || grpMatch;
      }
      return true;
    });
  }, [students, memberGroupMap, memberFilterGroup, memberSearch]);

  const activePlanSelectedCount = useMemo(() => {
    return students.filter((s: any) => memberGroupMap[s.user_id] && s.plan_info?.has_active_plan).length;
  }, [students, memberGroupMap]);

  async function handleSubmitBatchAssign(asDraft: boolean) {
    if (!parsedData || groups.length === 0 || totalSelectedMembers === 0 || submitting) return;

    if (!asDraft && activePlanSelectedCount > 0) {
      const ok = window.confirm(
        `⚠️ 正式生效确认：\n\n您选择了【直接正式发布并生效】（共 ${totalSelectedMembers} 人，其中 ${activePlanSelectedCount} 人当前已有正在执行的 AI/教练周期计划）。\n\n• 正式发布将立即更新这 ${totalSelectedMembers} 位队员 ${effectiveMonday} ~ ${effectiveSunday} 当周的正式课表（历史打卡 100% 保留，原课表自动生成备份快照，可随时一键回退）。\n• 如果您希望先让教练逐人核对、不立即改动队员当前课表，请点击取消并选择【📝 存入待审草案】。\n\n确认立即正式发布并生效吗？`
      );
      if (!ok) return;
    }

    setSubmitting(true);
    try {
      const groupAssignments = groups.map((g) => {
        const uids = students
          .map((s: any) => s.user_id)
          .filter((uid: string) => memberGroupMap[uid] === g.group_code);
        return {
          group_code: g.group_code,
          group_name: g.group_name,
          badge_color: g.badge_color,
          pace_summary: g.pace_summary,
          days: g.days,
          user_ids: uids,
        };
      });

      const res = await apiClient.post("/api/coach/plan/batch-assign-imported-week", {
        club_id: clubId,
        operator_uid: coachUid,
        plan_title: planTitle,
        source_week_index: sourceWeekIndex,
        target_monday: effectiveMonday,
        coach_review_note: coachReviewNote,
        as_draft: asDraft,
        save_as_templates: saveAsTemplates,
        group_assignments: groupAssignments,
      });

      setLastDispatchResult({
        ...res.data,
        as_draft: asDraft,
        plan_title: planTitle,
        target_monday: effectiveMonday,
      });
      await fetchRecentBatches();
      onAssignedSuccess();
    } catch (err: any) {
      alert(err.response?.data?.detail || "派发周课表失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 overflow-y-auto"
      onPaste={handlePasteClipboard}
    >
      <div className="bg-[#121215] border border-white/15 rounded-3xl w-full max-w-6xl max-h-[94vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Top Header */}
        <div className="px-6 py-4 bg-[#18181c] border-b border-white/10 flex items-center justify-between gap-4 shrink-0">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                周课表智能导入与按组派发
              </span>
              <h2 className="text-base sm:text-lg font-bold text-white">
                导入主教练周课表（支持 A~E配速分组 / 男女分组 / 体能脚注自动合并）
              </h2>
            </div>
            <p className="text-xs text-zinc-400 mt-1">
              每周日主教练发布下周课表截图后，直接上传或粘贴（支持 Ctrl+V 粘贴截图），自动拆解各组课表并匹配对应队员一键派发
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                setShowBatchHistory((prev) => !prev);
                fetchRecentBatches();
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition flex items-center gap-1.5 cursor-pointer ${
                showBatchHistory
                  ? "bg-[#FC4C02] text-white border-[#FC4C02] font-bold"
                  : "bg-white/5 hover:bg-white/10 text-zinc-300 border-white/10"
              }`}
              title="查看历史派发批次并支持一键撤回恢复原课表"
            >
              派发记录与回退 {recentBatches.length > 0 ? `(${recentBatches.length})` : ""}
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          {/* Post-Dispatch Success & Instant 1-Click Undo Banner */}
          {lastDispatchResult && (
            <div className="p-4 sm:p-5 rounded-2xl bg-[#18181c] border border-white/15 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FC4C02]/15 text-[#FC4C02] border border-[#FC4C02]/30">
                    {lastDispatchResult.as_draft ? "已存入待审草案（未改动队员当前课表）" : "已正式派发并生效（已自动备份原课表）"}
                  </span>
                  <strong className="text-sm font-bold text-white">
                    {lastDispatchResult.message}
                  </strong>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  {lastDispatchResult.as_draft
                    ? "队员当前正在执行的 AI 周期计划或个人课表完全不受影响！您可以在排课工作台中逐人点击【确认转正生效】或【审阅微调】，也可以点击右侧按钮立即整批撤回。"
                    : "系统已自动为每位受影响队员保存派发前的课表快照（保留打卡记录）。如发现选错组别或派发有误，可随时点击右侧【一键撤回本次派发】恢复原状。"}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0 flex-wrap">
                {lastDispatchResult.batch_id && (
                  <button
                    onClick={() => handleRollbackBatch(lastDispatchResult.batch_id)}
                    disabled={rollingBackBatchId === lastDispatchResult.batch_id}
                    className="px-3.5 py-2 rounded-xl text-xs font-medium bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 transition cursor-pointer disabled:opacity-50"
                  >
                    {rollingBackBatchId === lastDispatchResult.batch_id ? "正在撤回..." : "一键撤回本次派发"}
                  </button>
                )}
                <button
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-[#FC4C02] hover:bg-[#ff5a14] text-white transition cursor-pointer"
                >
                  完成并返回工作台
                </button>
              </div>
            </div>
          )}

          {/* Collapsible Batch Dispatch History & Rollback Panel */}
          {showBatchHistory && (
            <div className="bg-[#18181c] border border-white/10 rounded-2xl p-4 sm:p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    最近课表派发批次与一键回退
                  </h3>
                  <p className="text-[11px] text-zinc-400 mt-0.5">
                    无论是「待审草案」还是「正式派发」，均可按批次一键撤回，系统会自动将队员课表恢复至派发前的版本
                  </p>
                </div>
                <button
                  onClick={() => setShowBatchHistory(false)}
                  className="text-xs text-zinc-400 hover:text-white cursor-pointer"
                >
                  收起 ✕
                </button>
              </div>

              {loadingBatches ? (
                <div className="py-4 text-center text-xs text-zinc-400">正在加载派发历史记录...</div>
              ) : recentBatches.length === 0 ? (
                <div className="py-4 text-center text-xs text-zinc-500">暂无近期批量派发记录</div>
              ) : (
                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {recentBatches.map((b: any) => (
                    <div
                      key={b.batch_id}
                      className="p-3 rounded-xl bg-[#121215] border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-white">{b.action_label || "批量派发周课表"}</span>
                          <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-300 text-[10px] font-medium">
                            涉及 {b.affected_users_count} 名队员
                          </span>
                          <span className="text-[10px] text-zinc-500 font-mono">
                            {formatBeijingTime(b.created_at, true)}
                          </span>
                        </div>
                        <div className="text-[11px] text-zinc-400">
                          包含队员：{(b.affected_users || []).map((u: any) => `${u.display_name}(${u.new_plan_title || "课表"})`).join("、")}
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          if (
                            window.confirm(
                              `确认撤回该批次（${b.action_label}，共 ${b.affected_users_count} 人）吗？\n撤回后将自动清理本次派发的草案或恢复队员派发前的原课表。`
                            )
                          ) {
                            handleRollbackBatch(b.batch_id);
                          }
                        }}
                        disabled={rollingBackBatchId === b.batch_id}
                        className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 text-xs font-medium transition shrink-0 cursor-pointer disabled:opacity-50"
                      >
                        {rollingBackBatchId === b.batch_id ? "撤回中..." : "整批撤回恢复"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {/* STEP 1: Input Source & Quick Presets */}
          <div className="bg-[#18181f] border border-white/10 rounded-2xl p-4 sm:p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-amber-500 text-black font-black text-xs flex items-center justify-center">
                  1
                </span>
                <span className="text-sm font-black text-white">上传课表图片 / 粘贴文本</span>
                <span className="text-[11px] text-zinc-400">（或点击右侧真实课表示例立即体验）</span>
              </div>

              {/* Preset Buttons */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {presets.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setActivePresetId(p.id);
                      setRawText(p.raw_text || "");
                      handleParseSchedule({ presetId: p.id });
                    }}
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer border ${
                      activePresetId === p.id
                        ? "bg-amber-500 text-black border-amber-400 font-black shadow"
                        : "bg-white/5 hover:bg-white/10 text-amber-200 border-amber-500/30"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Mode Switcher + Input Area */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
              {/* Left: Image Dropzone */}
              <div className="lg:col-span-5 flex flex-col">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="flex-1 min-h-[150px] border-2 border-dashed border-amber-500/35 hover:border-amber-400 bg-black/30 hover:bg-amber-500/5 rounded-2xl p-4 flex flex-col items-center justify-center text-center cursor-pointer transition relative overflow-hidden"
                >
                  {imagePreview ? (
                    <div className="w-full flex flex-col items-center gap-2">
                      <img
                        src={imagePreview}
                        alt="课表预览"
                        className="max-h-36 object-contain rounded-lg border border-white/15"
                      />
                      <span className="text-[11px] text-amber-300 font-bold">
                        点击更换课表图片（或直接按 Ctrl+V / ⌘+V 粘贴新截图）
                      </span>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-8 h-8 text-amber-400 mb-2" />
                      <div className="text-xs font-black text-white">
                        点击上传教练发布的课表图片，或直接按 <kbd className="px-1.5 py-0.5 bg-white/10 rounded text-amber-300">Ctrl+V</kbd> 粘贴截图
                      </div>
                      <p className="text-[11px] text-zinc-500 mt-1">
                        支持微信群 Excel 截图（自动识别 A/B/C/D/E 组或男/女配速及底部体能训练 a/b/c）
                      </p>
                    </>
                  )}
                </div>
              </div>

              {/* Right: Raw Text / OCR Output Box + Parse Button */}
              <div className="lg:col-span-7 flex flex-col gap-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400 font-bold flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-amber-400" />
                    课表原文 / 识图提取文本（可直接粘贴或修改后重新解析）：
                  </span>
                  <button
                    onClick={() => handleParseSchedule({ textOverride: rawText })}
                    disabled={parsing || (!rawText.trim() && !imagePreview)}
                    className="px-3.5 py-1.5 rounded-xl text-xs font-black bg-gradient-to-r from-amber-400 to-orange-500 hover:from-amber-300 hover:to-orange-400 text-black shadow transition flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    {parsing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    {parsing ? "AI 正在识图拆解..." : "✨ 解析并生成各组课表"}
                  </button>
                </div>
                <textarea
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  placeholder="可直接在此粘贴 Excel 课表文字，或上传左侧截图由 AI 自动提取文字..."
                  rows={5}
                  className="w-full flex-1 bg-black/50 border border-white/10 rounded-xl p-3 text-xs text-zinc-200 font-mono leading-relaxed focus:border-amber-400 outline-none resize-none"
                />
              </div>
            </div>

            {parseError && (
              <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{parseError}</span>
              </div>
            )}
          </div>

          {/* STEP 2: Multi-Group Schedule Preview & Editor */}
          {parsedData && groups.length > 0 && (
            <div className="bg-[#18181f] border border-white/10 rounded-2xl p-4 sm:p-5 space-y-5">
              {/* Header & Date Anchor Selector */}
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-white/10">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span className="w-6 h-6 rounded-full bg-amber-500 text-black font-black text-xs flex items-center justify-center">
                    2
                  </span>
                  <span className="text-sm font-black text-white">核对各组课表与派发周期</span>
                  <input
                    type="text"
                    value={planTitle}
                    onChange={(e) => setPlanTitle(e.target.value)}
                    className="bg-black/40 border border-white/15 rounded-xl px-3 py-1.5 text-xs font-bold text-amber-300 focus:border-amber-400 outline-none min-w-[260px]"
                  />
                  <div className="flex items-center gap-1 text-xs text-zinc-400">
                    <span>第</span>
                    <input
                      type="number"
                      min={1}
                      max={24}
                      value={sourceWeekIndex}
                      onChange={(e) => setSourceWeekIndex(Math.max(1, Number(e.target.value) || 1))}
                      className="w-12 bg-black/40 border border-white/15 rounded-lg px-2 py-1 text-center text-white font-mono"
                    />
                    <span>周</span>
                  </div>
                </div>

                {/* Date Anchor Options */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs text-zinc-400 font-bold flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5 text-amber-400" />
                    派发周日期：
                  </span>
                  {parsedData.parsed_monday && (
                    <button
                      onClick={() => setDateAnchorMode("parsed_date")}
                      className={`px-2.5 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer border ${
                        dateAnchorMode === "parsed_date"
                          ? "bg-amber-500 text-black border-amber-400 font-black"
                          : "bg-white/5 text-zinc-300 border-white/10 hover:text-white"
                      }`}
                    >
                      📅 课表原日期 ({parsedData.parsed_monday.slice(5)}起)
                    </button>
                  )}
                  <button
                    onClick={() => setDateAnchorMode("next_week")}
                    className={`px-2.5 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer border ${
                      dateAnchorMode === "next_week"
                        ? "bg-emerald-500 text-black border-emerald-400 font-black"
                        : "bg-white/5 text-zinc-300 border-white/10 hover:text-white"
                    }`}
                  >
                    ⏭️ 下周一至周日 ({parsedData.next_monday?.slice(5)}起)
                  </button>
                  <button
                    onClick={() => setDateAnchorMode("current_week")}
                    className={`px-2.5 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer border ${
                      dateAnchorMode === "current_week"
                        ? "bg-sky-500 text-black border-sky-400 font-black"
                        : "bg-white/5 text-zinc-300 border-white/10 hover:text-white"
                    }`}
                  >
                    📍 本周一至周日 ({parsedData.current_monday?.slice(5)}起)
                  </button>
                  <input
                    type="date"
                    value={effectiveMonday}
                    onChange={(e) => {
                      setDateAnchorMode("custom");
                      setCustomMonday(e.target.value);
                    }}
                    className="bg-black/40 border border-white/15 rounded-xl px-2.5 py-1 text-xs text-white font-mono outline-none focus:border-amber-400"
                  />
                </div>
              </div>

              {/* Extracted Strength Footnotes & Group Run Venue Banner */}
              {(Object.keys(parsedData.strength_footnotes || {}).length > 0 ||
                Object.keys(parsedData.weekday_group_run_notes || {}).length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.keys(parsedData.strength_footnotes || {}).length > 0 && (
                    <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-xs space-y-1">
                      <div className="font-black text-amber-300 flex items-center gap-1.5">
                        <Dumbbell className="w-3.5 h-3.5" />
                        已自动识别并挂载至对应日期的体能训练 (a/b/c)：
                      </div>
                      {Object.entries(parsedData.strength_footnotes).map(([k, v]: any) => (
                        <div key={k} className="text-zinc-200 leading-relaxed">
                          <strong className="text-amber-400 uppercase">{k}.</strong> {v}
                        </div>
                      ))}
                      {parsedData.strength_rest_note && (
                        <div className="text-[11px] text-amber-200/80">⏱️ {parsedData.strength_rest_note}</div>
                      )}
                    </div>
                  )}

                  {Object.keys(parsedData.weekday_group_run_notes || {}).length > 0 && (
                    <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/25 text-xs space-y-1">
                      <div className="font-black text-purple-300 flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5" />
                        已自动识别集中合练安排与注意事项：
                      </div>
                      {Object.entries(parsedData.weekday_group_run_notes).map(([wd, note]: any) => (
                        <div key={wd} className="text-zinc-200">
                          <span className="px-1.5 py-0.5 rounded bg-purple-500/25 text-purple-200 font-bold mr-1.5">
                            {wd}
                          </span>
                          {note}
                        </div>
                      ))}
                      <div className="pt-1">
                        <input
                          type="text"
                          value={coachReviewNote}
                          onChange={(e) => setCoachReviewNote(e.target.value)}
                          placeholder="全周注意事项..."
                          className="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1 text-[11px] text-zinc-300 outline-none focus:border-purple-400"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Group Tabs (A组 / B组 / C组 / D组 / E组 or 男组 / 女组) */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {groups.map((g) => {
                  const isSel = g.group_code === (activeGroupObj?.group_code || "");
                  const mCount = groupMemberCounts[g.group_code] || 0;
                  return (
                    <button
                      key={g.group_code}
                      onClick={() => setSelectedGroupCode(g.group_code)}
                      className={`px-4 py-2.5 rounded-2xl text-left transition cursor-pointer border shrink-0 flex items-center gap-3 ${
                        isSel
                          ? "bg-amber-500/20 border-amber-400 shadow-lg shadow-amber-500/10"
                          : "bg-black/40 border-white/10 hover:border-white/25"
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-black text-white">{g.group_code}</span>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                            已配 {mCount} 人
                          </span>
                        </div>
                        <div className="text-[11px] text-zinc-400 mt-0.5 font-mono">
                          周跑量 <strong className="text-amber-300">{g.weekly_km}km</strong> · {g.days_per_week}练 · {g.pace_summary}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Active Group 7-Day Editable Table */}
              {activeGroupObj && (
                <div className="overflow-x-auto border border-white/10 rounded-2xl">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-black/60 text-zinc-400 border-b border-white/10">
                        <th className="py-2.5 px-3 w-28">星期 / 日期</th>
                        <th className="py-2.5 px-3 w-28">课表类型</th>
                        <th className="py-2.5 px-3 w-56">训练课目名称</th>
                        <th className="py-2.5 px-3 w-24">距离 (km)</th>
                        <th className="py-2.5 px-3 w-44">【{activeGroupObj.group_code}】目标配速</th>
                        <th className="py-2.5 px-3">执行说明与跑后体能明细</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {(activeGroupObj.days || []).map((d: any, dIdx: number) => {
                        const rowDate = addDaysIso(effectiveMonday, dIdx);
                        const isRest = d.workout_type === "rest";
                        return (
                          <tr
                            key={dIdx}
                            className={isRest ? "bg-zinc-900/40 text-zinc-500" : "bg-[#14141a] hover:bg-[#191922]"}
                          >
                            <td className="py-2.5 px-3 font-mono">
                              <div className="font-black text-white">{d.day_of_week}</div>
                              <div className="text-[10px] text-zinc-500">{rowDate}</div>
                            </td>
                            <td className="py-2.5 px-3">
                              <select
                                value={d.workout_type}
                                onChange={(e) =>
                                  handleUpdateDayField(activeGroupObj.group_code, dIdx, "workout_type", e.target.value)
                                }
                                className="bg-black/50 border border-white/10 rounded-lg px-2 py-1 text-xs text-white outline-none focus:border-amber-400"
                              >
                                {WORKOUT_TYPE_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="py-2.5 px-3">
                              <input
                                type="text"
                                value={d.title || ""}
                                onChange={(e) =>
                                  handleUpdateDayField(activeGroupObj.group_code, dIdx, "title", e.target.value)
                                }
                                className="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1 text-xs font-bold text-white outline-none focus:border-amber-400"
                              />
                            </td>
                            <td className="py-2.5 px-3">
                              <input
                                type="number"
                                step="0.5"
                                min={0}
                                disabled={isRest}
                                value={d.distance_km ?? 0}
                                onChange={(e) =>
                                  handleUpdateDayField(
                                    activeGroupObj.group_code,
                                    dIdx,
                                    "distance_km",
                                    Number(e.target.value) || 0
                                  )
                                }
                                className="w-20 bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs font-mono font-bold text-emerald-300 outline-none focus:border-amber-400 disabled:opacity-40"
                              />
                            </td>
                            <td className="py-2.5 px-3">
                              <input
                                type="text"
                                disabled={isRest}
                                value={d.target_pace || ""}
                                onChange={(e) =>
                                  handleUpdateDayField(activeGroupObj.group_code, dIdx, "target_pace", e.target.value)
                                }
                                className="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1 text-xs font-mono text-amber-300 outline-none focus:border-amber-400 disabled:opacity-40"
                              />
                            </td>
                            <td className="py-2.5 px-3">
                              <input
                                type="text"
                                value={d.description || ""}
                                onChange={(e) =>
                                  handleUpdateDayField(activeGroupObj.group_code, dIdx, "description", e.target.value)
                                }
                                className="w-full bg-black/40 border border-white/10 rounded-lg px-2.5 py-1 text-xs text-zinc-300 outline-none focus:border-amber-400"
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* STEP 3: Member Group Assignment Matrix */}
          {parsedData && groups.length > 0 && (
            <div className="bg-[#18181f] border border-white/10 rounded-2xl p-4 sm:p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-amber-500 text-black font-black text-xs flex items-center justify-center">
                    3
                  </span>
                  <span className="text-sm font-black text-white">确认各组队员名单（点击组别按钮可随时调组，系统将自动记忆）</span>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => setMemberFilterGroup("all")}
                    className={`px-2.5 py-1 rounded-xl text-xs font-bold cursor-pointer ${
                      memberFilterGroup === "all"
                        ? "bg-white text-black font-black"
                        : "bg-white/5 text-zinc-400 hover:text-white"
                    }`}
                  >
                    全部 ({students.length})
                  </button>
                  {groups.map((g) => (
                    <button
                      key={g.group_code}
                      onClick={() =>
                        setMemberFilterGroup(memberFilterGroup === g.group_code ? "all" : g.group_code)
                      }
                      className={`px-2.5 py-1 rounded-xl text-xs font-bold cursor-pointer ${
                        memberFilterGroup === g.group_code
                          ? "bg-amber-500 text-black font-black"
                          : "bg-amber-500/10 text-amber-300 border border-amber-500/30"
                      }`}
                    >
                      {g.group_code} ({groupMemberCounts[g.group_code] || 0})
                    </button>
                  ))}
                  <button
                    onClick={() => setMemberFilterGroup("unassigned")}
                    className={`px-2.5 py-1 rounded-xl text-xs font-bold cursor-pointer ${
                      memberFilterGroup === "unassigned"
                        ? "bg-zinc-300 text-black font-black"
                        : "bg-white/5 text-zinc-400 hover:text-white"
                    }`}
                  >
                    不派发 ({students.length - totalSelectedMembers})
                  </button>
                  <input
                    type="text"
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                    placeholder="🔍 搜索队员姓名..."
                    className="bg-black/40 border border-white/10 rounded-xl px-3 py-1 text-xs text-white outline-none focus:border-amber-400 w-36"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-72 overflow-y-auto pr-1">
                {filteredStudents.map((stu: any) => {
                  const curGrp = memberGroupMap[stu.user_id] || "";
                  const pInfo = stu.plan_info || {};
                  return (
                    <div
                      key={stu.user_id}
                      className={`p-3 rounded-xl border flex items-center justify-between gap-2 transition ${
                        curGrp
                          ? "bg-[#121217] border-amber-500/30"
                          : "bg-black/30 border-white/5 opacity-60"
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-xs font-bold text-white truncate">{stu.display_name}</span>
                          {stu.gender_label && (
                            <span className="text-[10px] text-zinc-400">({stu.gender_label})</span>
                          )}
                          {pInfo.has_active_plan ? (
                            <span
                              className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-blue-500/15 text-blue-300 border border-blue-500/30"
                              title={`当前执行中：${pInfo.active_plan_title || pInfo.title}`}
                            >
                              {pInfo.active_source_label || "🤖 已有课表"}
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.2 rounded text-[9px] text-zinc-500 bg-white/5">
                              ⚪ 未排课
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-zinc-500 truncate mt-0.5">
                          全马PB: {stu.marathon_pb || "—"} · 推荐: {stu.recommended_group?.group_code || "—"}
                        </div>
                      </div>

                      <div className="flex items-center gap-1 shrink-0 flex-wrap justify-end">
                        {groups.map((g) => {
                          const active = curGrp === g.group_code;
                          return (
                            <button
                              key={g.group_code}
                              onClick={() => handleSetMemberGroup(stu.user_id, g.group_code)}
                              className={`px-2 py-1 rounded-lg text-[10px] font-black transition cursor-pointer ${
                                active
                                  ? "bg-amber-500 text-black shadow"
                                  : "bg-white/5 text-zinc-400 hover:bg-white/15 hover:text-white"
                              }`}
                            >
                              {g.short_key || g.group_code}
                            </button>
                          );
                        })}
                        <button
                          onClick={() => handleSetMemberGroup(stu.user_id, "")}
                          className={`px-2 py-1 rounded-lg text-[10px] font-bold transition cursor-pointer ${
                            !curGrp
                              ? "bg-zinc-700 text-white"
                              : "bg-white/5 text-zinc-500 hover:text-zinc-300"
                          }`}
                          title="本周暂不派发给该队员"
                        >
                          跳过
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Bottom Footer Actions */}
        <div className="px-6 py-4 bg-[#18181c] border-t border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
          <div className="space-y-1">
            <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={saveAsTemplates}
                onChange={(e) => setSaveAsTemplates(e.target.checked)}
                className="rounded border-white/20 accent-[#FC4C02]"
              />
              <BookmarkPlus className="w-4 h-4 text-zinc-400" />
              <span>同时将本次解析出的各组课表保存至「我的教练模版库」</span>
            </label>
            <div className="text-[11px] text-zinc-400">
              「存入待审草案」不会改动队员当前正在执行的 AI/个人计划；「直接正式发布」前会自动备份原计划，支持随时一键撤回。
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-wrap justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium bg-white/5 hover:bg-white/10 text-zinc-300 border border-white/10 transition cursor-pointer"
            >
              关闭
            </button>
            <button
              onClick={() => handleSubmitBatchAssign(true)}
              disabled={!parsedData || totalSelectedMembers === 0 || submitting}
              title="仅保存为教练工作台中的待审草案，队员端正在执行的 AI 计划或个人课表完全不受影响，待审核确认后才生效"
              className="px-4 py-2 rounded-xl text-xs font-bold bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 transition flex items-center gap-1.5 cursor-pointer disabled:opacity-40"
            >
              存入待审草案 ({totalSelectedMembers}人)
            </button>
            <button
              onClick={() => handleSubmitBatchAssign(false)}
              disabled={!parsedData || totalSelectedMembers === 0 || submitting}
              title="立即更新所选队员当周正式课表（系统自动生成原课表快照备份，支持一键撤回）"
              className="px-5 py-2 rounded-xl text-xs font-bold bg-[#FC4C02] hover:bg-[#ff5a14] text-white transition flex items-center gap-1.5 cursor-pointer disabled:opacity-40"
            >
              {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              直接正式发布并生效 ({totalSelectedMembers}人 · {effectiveMonday.slice(5)}~{effectiveSunday.slice(5)})
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
