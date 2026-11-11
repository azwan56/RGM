"use client";

import React, { useState, useEffect, useCallback } from "react";
import apiClient from "@/lib/apiClient";
import PacerResumeModal from "@/components/PacerResumeModal";
import {
  Sparkles,
  Search,
  Check,
  Copy,
  Share2,
  Loader2,
  ShieldCheck,
  AlertTriangle,
  Activity,
  Award,
  Sliders,
} from "lucide-react";

interface PacerEvaluationCardProps {
  uid: string;
  viewerUid?: string;
}

const DISTANCE_TABS = [
  { key: "fm", label: "全程马拉松" },
  { key: "hm", label: "半程马拉松" },
  { key: "10k", label: "10公里路跑" },
  { key: "custom", label: "跑团拉练自定义" },
] as const;

export default function PacerEvaluationCard({ uid, viewerUid }: PacerEvaluationCardProps) {
  const [presets, setPresets] = useState<any[]>([]);
  const [distanceType, setDistanceType] = useState<"fm" | "hm" | "10k" | "custom">("fm");
  const [eventName, setEventName] = useState<string>("上海马拉松");
  const [customEventInput, setCustomEventInput] = useState<string>("");
  const [selectedGroup, setSelectedGroup] = useState<string>("");
  const [targetRaceDate, setTargetRaceDate] = useState<string>("");

  // Custom LSD inputs
  const [customDistKm, setCustomDistKm] = useState<number>(30);
  const [customPaceStr, setCustomPaceStr] = useState<string>("5:00");

  const [evalData, setEvalData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [searchingWeb, setSearchingWeb] = useState<boolean>(false);

  // On-demand AI prescription & self-recommendation statement
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiResult, setAiResult] = useState<any>(null);
  const [copiedBio, setCopiedBio] = useState<boolean>(false);

  // Poster modal
  const [resumeModalOpen, setResumeModalOpen] = useState<boolean>(false);

  useEffect(() => {
    apiClient
      .get("/api/science/pacer-presets")
      .then((res) => {
        if (res.data?.preset_events) {
          setPresets(res.data.preset_events);
        }
      })
      .catch(() => {});
  }, []);

  const fetchEvaluation = useCallback(
    async (opts?: {
      overrideEvent?: string;
      overrideDist?: "fm" | "hm" | "10k" | "custom";
      overrideGroup?: string;
      overrideDate?: string;
      allowWeb?: boolean;
    }) => {
      if (!uid) return;
      const effDist = opts?.overrideDist ?? distanceType;
      const effEvent = opts?.overrideEvent !== undefined ? opts.overrideEvent : eventName;
      const effGroup = opts?.overrideGroup !== undefined ? opts.overrideGroup : selectedGroup;
      const effDate = opts?.overrideDate !== undefined ? opts.overrideDate : targetRaceDate;
      const webFlag = Boolean(opts?.allowWeb);

      if (webFlag) setSearchingWeb(true);
      else setLoading(true);

      try {
        const params = new URLSearchParams();
        params.set("distance_type", effDist);
        if (effDist !== "custom" && effEvent) {
          params.set("event_name", effEvent);
        }
        if (effGroup) {
          params.set("target_group", effGroup);
        }
        if (effDate) {
          params.set("target_race_date", effDate);
        }
        if (effDist === "custom") {
          params.set("custom_distance_km", String(customDistKm || 30));
          params.set("custom_target_pace", customPaceStr || "5:00");
        }
        if (viewerUid && viewerUid !== uid) {
          params.set("viewer_uid", viewerUid);
        }
        params.set("allow_web_search", webFlag ? "true" : "false");

        const res = await apiClient.get(`/api/science/pacer-eval/${encodeURIComponent(uid)}?${params.toString()}`);
        const d = res.data;
        setEvalData(d);
        if (!effGroup && d?.selected_evaluation?.group_code) {
          setSelectedGroup(d.selected_evaluation.group_code);
        }
      } catch (e) {
        console.error("Failed to load pacer evaluation:", e);
      } finally {
        setLoading(false);
        setSearchingWeb(false);
      }
    },
    [uid, viewerUid, distanceType, eventName, selectedGroup, targetRaceDate, customDistKm, customPaceStr]
  );

  useEffect(() => {
    if (uid) {
      fetchEvaluation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid]);

  const handleSwitchDistance = (nextDist: "fm" | "hm" | "10k" | "custom") => {
    setDistanceType(nextDist);
    setSelectedGroup("");
    setAiResult(null);
    fetchEvaluation({ overrideDist: nextDist, overrideGroup: "" });
  };

  const handleSelectEvent = (evName: string, rDate = "") => {
    setEventName(evName);
    setTargetRaceDate(rDate);
    setAiResult(null);
    fetchEvaluation({ overrideEvent: evName, overrideDate: rDate, allowWeb: false });
  };

  const handleCustomEventSearch = () => {
    const q = customEventInput.trim();
    if (!q) return;
    setEventName(q);
    setAiResult(null);
    fetchEvaluation({ overrideEvent: q, allowWeb: true });
  };

  const handleSelectGroup = (gCode: string) => {
    setSelectedGroup(gCode);
    setAiResult(null);
    fetchEvaluation({ overrideGroup: gCode });
  };

  const handleGenerateAiPrescription = async () => {
    if (!uid || !evalData?.selected_evaluation) return;
    setAiLoading(true);
    try {
      const res = await apiClient.post(`/api/science/pacer-ai-prescription/${encodeURIComponent(uid)}`, {
        event_name: distanceType === "custom" ? "跑团专场模拟拉练" : eventName,
        distance_type: distanceType,
        target_group: evalData.selected_evaluation.group_code,
        custom_distance_km: distanceType === "custom" ? customDistKm : undefined,
        custom_target_pace: distanceType === "custom" ? customPaceStr : undefined,
        target_race_date: targetRaceDate || undefined,
      });
      if (res.data?.success) {
        setAiResult(res.data);
      }
    } catch (e) {
      console.error("AI pacer prescription failed:", e);
    } finally {
      setAiLoading(false);
    }
  };

  const handleCopyStatement = async () => {
    const txt = aiResult?.application_statement;
    if (!txt) return;
    try {
      await navigator.clipboard.writeText(txt);
      setCopiedBio(true);
      setTimeout(() => setCopiedBio(false), 2200);
    } catch {}
  };

  const sel = evalData?.selected_evaluation;
  const calib = evalData?.event_calibration;
  const upcomingRaces: any[] = (evalData?.upcoming_races || []).filter((r: any) => !r.is_trail);
  const allGroups: any[] = evalData?.all_groups_matrix || [];
  const recGroupCode = evalData?.recommended_group?.group_code || "";
  const showcase = evalData?.showcase_run;

  const gateIcon = (status?: string) => {
    if (status === "pass" || status === "exempt") {
      return <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />;
    }
    if (status === "warn" || status === "missing_cert" || status === "conflict") {
      return <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />;
    }
    return <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />;
  };

  const gateStyle = (status?: string) => {
    if (status === "pass" || status === "exempt") {
      return "bg-emerald-500/10 border-emerald-500/30 text-emerald-200";
    }
    if (status === "warn" || status === "missing_cert" || status === "conflict") {
      return "bg-amber-500/10 border-amber-500/35 text-amber-200";
    }
    return "bg-rose-500/10 border-rose-500/35 text-rose-200";
  };

  return (
    <div className="bg-[#121215] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
      {/* Header Row */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="text-2xl">🐰</span>
            <h2 className="text-lg sm:text-xl font-black text-white">
              马拉松官方配速员（官兔）胜任度评估
            </h2>
            <span className="px-2.5 py-0.5 rounded-full bg-[#FC4C02]/15 border border-[#FC4C02]/40 text-[#FC4C02] text-xs font-extrabold">
              六维量化 · 赛事动态校准
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            结合赛道标牌与爬升温湿参数、当期耐力跑力与官方完赛证书双闸门、近 90 天稳态巡航代表作控速波动综合评级
          </p>
        </div>

        {sel && (
          <button
            onClick={() => setResumeModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-[#FC4C02] hover:opacity-90 text-white text-xs font-bold transition"
          >
            <Share2 className="w-4 h-4" />
            生成竞选履历 / 分享卡
          </button>
        )}
      </div>

      {/* Distance Mode Switcher */}
      <div className="flex flex-wrap items-center gap-2">
        {DISTANCE_TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => handleSwitchDistance(t.key)}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold border transition ${
              distanceType === t.key
                ? "bg-[#FC4C02] border-[#FC4C02] text-white shadow"
                : "bg-[#18181c] border-white/10 text-zinc-300 hover:border-white/25"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Event Selector OR Custom Club LSD Bar */}
      {distanceType !== "custom" ? (
        <div className="bg-[#18181c] border border-white/5 rounded-2xl p-4 space-y-3">
          {upcomingRaces.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-bold text-emerald-400">🎯 我的待参赛程：</span>
              {upcomingRaces.slice(0, 3).map((ur: any) => (
                <button
                  key={ur.id || ur.name}
                  onClick={() => handleSelectEvent(ur.name, ur.date || "")}
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold border transition ${
                    eventName === ur.name
                      ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-200"
                      : "bg-white/5 border-white/10 text-zinc-300 hover:border-emerald-500/40"
                  }`}
                >
                  {ur.name} {ur.date ? `(${ur.date})` : ""}
                </button>
              ))}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-bold text-zinc-400 mr-1">🔥 热门标牌赛事：</span>
            {(presets.length > 0
              ? presets.slice(0, 9)
              : [
                  { name: "上海马拉松" },
                  { name: "北京马拉松" },
                  { name: "厦门马拉松" },
                  { name: "无锡马拉松" },
                  { name: "武汉马拉松" },
                  { name: "成都马拉松" },
                  { name: "广州马拉松" },
                  { name: "杭州马拉松" },
                  { name: "兰州马拉松" },
                ]
            ).map((ev: any) => (
              <button
                key={ev.name}
                onClick={() => handleSelectEvent(ev.name)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition ${
                  eventName === ev.name
                    ? "bg-[#FC4C02]/20 border-[#FC4C02]/60 text-white"
                    : "bg-white/[0.03] border-white/5 text-zinc-400 hover:text-white"
                }`}
              >
                {ev.name}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <div className="relative flex-1 min-w-[210px]">
              <input
                type="text"
                value={customEventInput}
                onChange={(e) => setCustomEventInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCustomEventSearch();
                }}
                placeholder="输入任意国内/国际路跑赛事名称（如：衡水湖马拉松、首尔马拉松）..."
                className="w-full bg-[#101014] border border-white/10 rounded-xl pl-3.5 pr-4 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-[#FC4C02]"
              />
            </div>
            <button
              onClick={handleCustomEventSearch}
              disabled={searchingWeb || !customEventInput.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 disabled:opacity-40 text-xs font-bold text-white transition"
            >
              {searchingWeb ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              检索规程并校准
            </button>
          </div>

          {/* Calibration Tags */}
          {calib?.calibration_tags?.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {calib.calibration_tags.map((tag: string, idx: number) => (
                <span
                  key={idx}
                  className="px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/10 text-[11px] font-semibold text-zinc-300"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="bg-[#18181c] border border-white/5 rounded-2xl p-4 flex flex-wrap items-end gap-4">
          <div className="flex items-center gap-2 text-xs font-bold text-amber-300 w-full">
            <Sliders className="w-4 h-4" />
            跑团内部 LSD 拉练选兔模式（豁免田协官方完赛证书，聚焦当期真实体能与定速巡航稳健度）
          </div>
          <div>
            <label className="text-[11px] text-zinc-400 block mb-1">拉练目标距离 (km)</label>
            <input
              type="number"
              min={5}
              max={50}
              step={1}
              value={customDistKm}
              onChange={(e) => setCustomDistKm(Number(e.target.value) || 30)}
              className="w-28 bg-[#101014] border border-white/10 rounded-xl px-3 py-2 text-xs font-mono text-white"
            />
          </div>
          <div>
            <label className="text-[11px] text-zinc-400 block mb-1">领跑目标配速 (分:秒/km)</label>
            <input
              type="text"
              value={customPaceStr}
              onChange={(e) => setCustomPaceStr(e.target.value)}
              placeholder="5:00"
              className="w-32 bg-[#101014] border border-white/10 rounded-xl px-3 py-2 text-xs font-mono text-white"
            />
          </div>
          <button
            onClick={() => fetchEvaluation({ overrideDist: "custom", overrideGroup: "custom" })}
            className="px-4 py-2 rounded-xl bg-[#FC4C02] hover:opacity-90 text-xs font-bold text-white transition"
          >
            重新测算拉练胜任度
          </button>
        </div>
      )}

      {/* Horizontal All-Groups Suitability Matrix Strip */}
      {distanceType !== "custom" && allGroups.length > 0 && (
        <div>
          <div className="flex items-center justify-between text-xs text-zinc-400 mb-2">
            <span>全组别适配矩阵（点击任意组别切换查看详情）</span>
            {evalData?.recommended_group && (
              <span className="text-emerald-400 font-bold">
                ★ 系统首推黄金组别：{evalData.recommended_group.group_label}（{evalData.recommended_group.overall_score}分）
              </span>
            )}
          </div>
          <div className="flex items-stretch gap-2 overflow-x-auto pb-2">
            {allGroups.map((g: any) => {
              const isSel = sel?.group_code === g.group_code;
              const isRec = recGroupCode === g.group_code;
              return (
                <button
                  key={g.group_code}
                  onClick={() => handleSelectGroup(g.group_code)}
                  className={`shrink-0 min-w-[92px] p-2.5 rounded-2xl border text-left transition relative ${
                    isSel
                      ? "bg-[#FC4C02]/15 border-[#FC4C02] shadow-lg"
                      : "bg-[#18181c] border-white/5 hover:border-white/20"
                  }`}
                >
                  {isRec && (
                    <span className="absolute -top-2 right-2 px-1.5 py-0.5 rounded bg-emerald-500 text-[9px] font-black text-black">
                      ★ 首推
                    </span>
                  )}
                  <div className="text-xs font-black text-white">{g.group_code} 兔</div>
                  <div className="text-[10px] text-zinc-400 font-mono">
                    {String(g.target_pace_str || "").endsWith("/km") ? g.target_pace_str : `${g.target_pace_str}/km`}
                  </div>
                  <div className="mt-1.5 flex items-baseline justify-between">
                    <span className="text-sm font-black font-mono rgm-tone-text" style={{ color: g.verdict_color, ["--rgm-tone" as any]: g.verdict_color }}>
                      {g.overall_score}分
                    </span>
                    <span className="text-[10px] font-bold text-zinc-300">{g.grade}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Evaluation Body */}
      {loading && !sel ? (
        <div className="py-12 flex items-center justify-center gap-2 text-sm text-zinc-400">
          <Loader2 className="w-4 h-4 animate-spin text-[#FC4C02]" />
          正在执行六维官兔量化模型演算...
        </div>
      ) : sel ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left 5 cols: Score Hero + Dual Gatekeepers + Showcase Split Curve */}
          <div className="lg:col-span-5 space-y-4">
            {/* Hero Score Card */}
            <div className="bg-[#18181c] border border-white/10 rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-xs font-bold text-zinc-400">
                    {calib?.event_name} · {sel.group_label}
                  </div>
                  <div className="text-2xl font-black text-white mt-0.5 font-mono">
                    目标 {sel.target_time || sel.target_time_str}{" "}
                    <span className="text-sm font-bold text-[#FC4C02]">
                      ({String(sel.target_pace_str || "").endsWith("/km") ? sel.target_pace_str : `${sel.target_pace_str}/km`})
                    </span>
                  </div>
                  <div
                    className="mt-2 inline-flex items-center px-3 py-1 rounded-full text-xs font-extrabold rgm-tone-text"
                    style={{
                      backgroundColor: `${sel.verdict_color}20`,
                      color: sel.verdict_color,
                      ["--rgm-tone" as any]: sel.verdict_color,
                    }}
                  >
                    {sel.verdict_label}
                  </div>
                </div>

                {/* Circular Score Badge */}
                <div className="w-24 h-24 rounded-full border-4 border-[#FC4C02] bg-[#101014] flex flex-col items-center justify-center shrink-0">
                  <span className="text-3xl font-black font-mono text-white leading-none">
                    {sel.overall_score}
                  </span>
                  <span className="text-[11px] font-bold mt-1 rgm-tone-text" style={{ color: sel.verdict_color, ["--rgm-tone" as any]: sel.verdict_color }}>
                    {sel.grade} 级
                  </span>
                </div>
              </div>

              {sel.gates?.cert_gate?.status === "missing_cert" && (
                <div className="px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 flex items-center justify-between">
                  <span>🏃 跑团私兔 / 内部拉练兔真实胜任分：</span>
                  <strong className="font-mono text-sm text-emerald-400">{sel.private_pacer_score} / 100</strong>
                </div>
              )}

              {/* Dual Gatekeepers + Schedule/Age Gates */}
              <div className="space-y-2 pt-2 border-t border-white/5">
                {["fitness_gate", "cert_gate", "schedule_gate", "age_gate"].map((gk) => {
                  const gObj = sel.gates?.[gk];
                  if (!gObj) return null;
                  if ((gk === "schedule_gate" || gk === "age_gate") && gObj.status === "pass") {
                    return null;
                  }
                  return (
                    <div
                      key={gk}
                      className={`p-3 rounded-xl border text-xs flex items-start gap-2 ${gateStyle(gObj.status)}`}
                    >
                      {gateIcon(gObj.status)}
                      <div>
                        <div className="font-bold">{gObj.badge}</div>
                        <p className="text-[11px] opacity-85 mt-0.5 leading-relaxed">{gObj.detail}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Showcase Steady-Run 1km Split Curve Mini Card */}
            <div className="bg-[#18181c] border border-white/5 rounded-2xl p-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  稳态巡航代表作 1km 分段节拍
                </span>
                {showcase && (
                  <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 text-[11px] font-mono font-bold">
                    ±{showcase.sigma_gap_sec}s/km
                  </span>
                )}
              </div>

              {showcase?.splits_series?.length >= 3 ? (
                <>
                  <div className="text-[11px] text-zinc-400">
                    {showcase.date} · {showcase.name} · {showcase.distance_km}km · 均配{" "}
                    {String(showcase.avg_pace_str || "").endsWith("/km") ? showcase.avg_pace_str : `${showcase.avg_pace_str}/km`}
                  </div>
                  <div className="h-24 w-full bg-[#101014] rounded-xl p-2 border border-white/5">
                    {(() => {
                      const pts = showcase.splits_series;
                      const avgP = Number(showcase.avg_pace_sec || 300);
                      const pVals = pts.map((p: any) => Number(p.pace_sec || avgP));
                      const minV = Math.min(avgP - 22, ...pVals);
                      const maxV = Math.max(avgP + 22, ...pVals);
                      const poly = pts
                        .map((p: any, i: number) => {
                          const x = (i / Math.max(1, pts.length - 1)) * 300;
                          const y = 8 + ((Number(p.pace_sec) - minV) / Math.max(1, maxV - minV)) * 60;
                          return `${x.toFixed(1)},${y.toFixed(1)}`;
                        })
                        .join(" ");
                      const refY = 8 + ((avgP - minV) / Math.max(1, maxV - minV)) * 60;
                      return (
                        <svg viewBox="0 0 300 76" className="w-full h-full overflow-visible">
                          <line
                            x1="0"
                            y1={refY}
                            x2="300"
                            y2={refY}
                            stroke="rgba(16,185,129,0.45)"
                            strokeDasharray="4 4"
                            strokeWidth="1.5"
                          />
                          <polyline
                            fill="none"
                            stroke="#FC4C02"
                            strokeWidth="2.4"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            points={poly}
                          />
                        </svg>
                      );
                    })()}
                  </div>
                  <p className="text-[10px] text-zinc-500">
                    * 已自动剥离间歇课、前2km热身、末1km冷身及红绿灯单点异常停顿，提取真实巡航稳态表现
                  </p>
                </>
              ) : (
                <p className="text-xs text-zinc-500 py-3">
                  近 90 天暂无带完整 1km 分段的稳态长距离数据，同步佳明/高驰手表后即可自动绘制定速节拍曲线。
                </p>
              )}
            </div>
          </div>

          {/* Right 7 cols: 6-Dimension Quantitative Bars + Action Tips + AI Prescription */}
          <div className="lg:col-span-7 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(sel.dimensions || []).map((dim: any) => (
                <div key={dim.key} className="bg-[#18181c] border border-white/5 rounded-2xl p-3.5">
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-bold text-white">
                      {dim.label}{" "}
                      <span className="text-[10px] text-zinc-500 font-normal">({dim.weight_pct}%)</span>
                    </span>
                    <span className="font-mono font-black text-amber-400">{dim.score}分</span>
                  </div>
                  <div className="text-[11px] font-mono text-zinc-300 mb-2 truncate" title={dim.display_value}>
                    {dim.display_value}
                  </div>
                  <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden mb-1.5">
                    <div
                      className="h-full bg-gradient-to-r from-[#FC4C02] to-amber-400 rounded-full transition-all"
                      style={{ width: `${Math.min(100, Math.max(8, dim.score || 0))}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">{dim.desc}</p>
                </div>
              ))}
            </div>

            {/* Actionable Deterministic Advice */}
            {(sel.action_tips || sel.action_items)?.length > 0 && (
              <div className="bg-[#18181c] border border-white/5 rounded-2xl p-4 space-y-2">
                <div className="flex items-center gap-1.5 text-xs font-bold text-amber-300">
                  <Award className="w-4 h-4" />
                  官兔选拔冲刺建议与短板诊断
                </div>
                <ul className="space-y-1.5">
                  {(sel.action_tips || sel.action_items).map((tip: string, i: number) => (
                    <li key={i} className="text-xs text-zinc-300 leading-relaxed flex items-start gap-2">
                      <span className="text-[#FC4C02] font-bold">•</span>
                      <span>{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* On-Demand AI 4-Week Blind-Pacing Plan & Official Recruitment Self-Recommendation */}
            <div className="bg-[#18181c] border border-white/10 rounded-2xl p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-bold text-white flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-[#FC4C02]" />
                    AI 官兔专项盲跑处方 & 组委会竞选自荐语
                  </div>
                  <p className="text-[11px] text-zinc-400 mt-0.5">
                    一键生成针对 {sel.group_label} 的 4 周无表盲跑特训计划，以及可直接粘贴进报名表的 180 字竞选自述
                  </p>
                </div>
                <button
                  onClick={handleGenerateAiPrescription}
                  disabled={aiLoading}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FC4C02] hover:opacity-90 disabled:opacity-50 text-xs font-bold text-white transition"
                >
                  {aiLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      正在撰写...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      {aiResult ? "重新生成特训与自荐语" : "生成特训计划 & 竞选自荐语"}
                    </>
                  )}
                </button>
              </div>

              {aiResult && (
                <div className="space-y-3 pt-2 border-t border-white/10">
                  {aiResult.pacing_strategy_tip && (
                    <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-xs text-emerald-200">
                      <strong>🧭 赛道控速纪律：</strong> {aiResult.pacing_strategy_tip}
                    </div>
                  )}
                  <div className="p-3 rounded-xl bg-black/30 border border-white/5 text-xs text-zinc-200 whitespace-pre-line leading-relaxed">
                    <div className="font-bold text-amber-300 mb-1">📅 赛前 4 周官兔盲跑特训重点</div>
                    {aiResult.four_week_plan}
                  </div>
                  <div className="p-3 rounded-xl bg-black/40 border border-[#FC4C02]/30 text-xs text-zinc-200 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-[#FC4C02]">📝 组委会官兔招募报名自荐语（可直接复制）</span>
                      <button
                        onClick={handleCopyStatement}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/10 hover:bg-white/15 text-[11px] font-bold text-white transition"
                      >
                        {copiedBio ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                        {copiedBio ? "已复制" : "复制自荐语"}
                      </button>
                    </div>
                    <p className="leading-relaxed text-zinc-300">{aiResult.application_statement}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}

      <PacerResumeModal
        open={resumeModalOpen}
        onClose={() => setResumeModalOpen(false)}
        evalData={evalData}
      />
    </div>
  );
}
