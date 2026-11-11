"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/apiClient";
import {
  Search,
  Copy,
  Check,
  Send,
  Loader2,
  ExternalLink,
  X,
  ChevronDown,
  ChevronUp,
  Sliders,
} from "lucide-react";

interface PacerClubRadarPanelProps {
  clubId: string;
  operatorUid: string;
  clubName?: string;
}

const HOT_EVENTS = [
  "上海马拉松",
  "北京马拉松",
  "厦门马拉松",
  "无锡马拉松",
  "武汉马拉松",
  "成都马拉松",
  "广州马拉松",
  "兰州马拉松",
];

export default function PacerClubRadarPanel({
  clubId,
  operatorUid,
  clubName,
}: PacerClubRadarPanelProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState<boolean>(false);
  const [distanceType, setDistanceType] = useState<"fm" | "hm" | "10k" | "custom">("fm");
  const [eventName, setEventName] = useState<string>("上海马拉松");
  const [customEventQuery, setCustomEventQuery] = useState<string>("");
  const [customDistKm, setCustomDistKm] = useState<number>(30);
  const [customPaceStr, setCustomPaceStr] = useState<string>("5:00");

  const [radarData, setRadarData] = useState<any>(null);
  const [activeGroupCode, setActiveGroupCode] = useState<string>("330");
  const [loading, setLoading] = useState<boolean>(false);
  const [copiedRoster, setCopiedRoster] = useState<boolean>(false);

  // Assign Event Pacer Modal State
  const [assignCandidate, setAssignCandidate] = useState<any | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string>("");
  const [assignPaceGroup, setAssignPaceGroup] = useState<string>("");
  const [assignNote, setAssignNote] = useState<string>("");
  const [assigning, setAssigning] = useState<boolean>(false);
  const [assignToast, setAssignToast] = useState<string>("");

  const loadRadar = useCallback(
    async (opts?: {
      overrideDist?: "fm" | "hm" | "10k" | "custom";
      overrideEvent?: string;
      allowWeb?: boolean;
    }) => {
      if (!clubId || !operatorUid) return;
      const effDist = opts?.overrideDist ?? distanceType;
      const effEv = opts?.overrideEvent !== undefined ? opts.overrideEvent : eventName;
      setLoading(true);
      try {
        const qs = new URLSearchParams();
        qs.set("operator_uid", operatorUid);
        qs.set("distance_type", effDist);
        if (effDist !== "custom" && effEv) {
          qs.set("event_name", effEv);
        }
        if (effDist === "custom") {
          qs.set("custom_distance_km", String(customDistKm || 30));
          qs.set("custom_target_pace", customPaceStr || "5:00");
        }
        qs.set("allow_web_search", opts?.allowWeb ? "true" : "false");

        const res = await apiClient.get(`/api/team/${encodeURIComponent(clubId)}/pacer-radar?${qs.toString()}`);
        const d = res.data;
        setRadarData(d);
        const groups = d?.groups_ranking || [];
        if (groups.length > 0 && !groups.some((g: any) => g.group_code === activeGroupCode)) {
          const firstQual = groups.find((g: any) => g.qualified_count > 0) || groups[0];
          setActiveGroupCode(firstQual.group_code);
        }
        if (d?.assignable_events?.length > 0 && !selectedEventId) {
          setSelectedEventId(String(d.assignable_events[0].id));
        }
      } catch (e) {
        console.error("Load club pacer radar failed:", e);
      } finally {
        setLoading(false);
      }
    },
    [clubId, operatorUid, distanceType, eventName, customDistKm, customPaceStr, activeGroupCode, selectedEventId]
  );

  useEffect(() => {
    if (expanded && !radarData && clubId && operatorUid) {
      loadRadar();
    }
  }, [expanded, radarData, clubId, operatorUid, loadRadar]);

  const groupsRanking: any[] = radarData?.groups_ranking || [];
  const activeBucket =
    groupsRanking.find((g: any) => g.group_code === activeGroupCode) || groupsRanking[0] || null;
  const assignableEvents: any[] = radarData?.assignable_events || [];

  const handleCopyRoster = async () => {
    if (!radarData) return;
    const evTitle = radarData.event_calibration?.event_name || eventName;
    const lines: string[] = [`🐰【${clubName || "跑团"} · ${evTitle} 领跑兔选拔推荐名单】`];
    for (const grp of groupsRanking) {
      const topCands = (grp.candidates || [])
        .filter((c: any) => c.overall_score >= 68 || c.private_pacer_score >= 75)
        .slice(0, 3);
      if (topCands.length === 0) continue;
      const names = topCands
        .map(
          (c: any) =>
            `${c.display_name}(${c.overall_score}分${
              c.cert_gate_status === "missing_cert" ? `·私兔${c.private_pacer_score}分` : ""
            })`
        )
        .join("、");
      lines.push(`• ${grp.group_label} (${grp.target_pace_str})：${names}`);
    }
    if (lines.length === 1) {
      lines.push("当前组别暂无评分 ≥68 分候选队员，建议降一档配速或切换拉练模式查看。");
    }
    lines.push("—— 由 RGM 六维官兔量化雷达生成");
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopiedRoster(true);
      setTimeout(() => setCopiedRoster(false), 2400);
    } catch {}
  };

  const openAssignModal = (cand: any) => {
    setAssignCandidate(cand);
    const defaultPace = activeBucket
      ? `${activeBucket.group_label} (${activeBucket.target_pace_str})`
      : "5:00/km 领跑组";
    setAssignPaceGroup(defaultPace);
    setAssignNote(
      `经跑团选兔雷达评估（综合胜任度 ${cand.overall_score} 分），特邀担任本场活动领跑兔！`
    );
    if (assignableEvents.length > 0 && !selectedEventId) {
      setSelectedEventId(String(assignableEvents[0].id));
    }
  };

  const handleConfirmAssign = async () => {
    if (!assignCandidate || !selectedEventId) return;
    setAssigning(true);
    try {
      const res = await apiClient.post(
        `/api/team/${encodeURIComponent(clubId)}/events/${encodeURIComponent(selectedEventId)}/assign-pacer`,
        {
          operator_uid: operatorUid,
          target_uid: assignCandidate.uid,
          pace_group: assignPaceGroup,
          note: assignNote,
        }
      );
      if (res.data?.success) {
        setAssignToast(`✅ 已成功指派 ${assignCandidate.display_name} 为【${assignPaceGroup}】领跑兔，并下发站内通知！`);
        setAssignCandidate(null);
        setTimeout(() => setAssignToast(""), 4200);
      }
    } catch (e: any) {
      alert(e?.response?.data?.detail || "指派领跑兔失败，请稍后重试");
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="bg-gradient-to-br from-[#16141a] to-[#111216] border border-[#FC4C02]/35 rounded-3xl p-5 sm:p-6 shadow-2xl space-y-5">
      {/* Header Toggle Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-3 cursor-pointer select-none"
        >
          <div className="w-10 h-10 rounded-2xl bg-[#FC4C02]/20 border border-[#FC4C02]/40 flex items-center justify-center text-xl">
            🐰
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-base sm:text-lg font-black text-white">
                全团选兔雷达 · 官方配速员与拉练领跑兔选拔
              </h3>
              <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300 text-[11px] font-bold">
                教练 / 团长专享
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              一键扫描全团活跃成员硬实力余量、90天稳态控速波动与完赛证书，支持直接指派约跑「🐰 领跑兔」
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {expanded && radarData && (
            <button
              onClick={handleCopyRoster}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-xs font-bold text-white transition"
            >
              {copiedRoster ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedRoster ? "已复制推荐名单" : "复制微信群推荐名单"}
            </button>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FC4C02] hover:opacity-90 text-xs font-black text-white transition"
          >
            {expanded ? (
              <>
                收起雷达 <ChevronUp className="w-4 h-4" />
              </>
            ) : (
              <>
                展开选兔雷达 <ChevronDown className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {assignToast && (
        <div className="px-4 py-2.5 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-xs font-bold text-emerald-200">
          {assignToast}
        </div>
      )}

      {expanded && (
        <div className="space-y-5 pt-2 border-t border-white/10">
          {/* Mode & Event Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5">
              {[
                { key: "fm", label: "全马官兔" },
                { key: "hm", label: "半马官兔" },
                { key: "10k", label: "10K官兔" },
                { key: "custom", label: "内部拉练领跑兔" },
              ].map((t) => (
                <button
                  key={t.key}
                  onClick={() => {
                    const nd = t.key as "fm" | "hm" | "10k" | "custom";
                    setDistanceType(nd);
                    loadRadar({ overrideDist: nd });
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold border transition ${
                    distanceType === t.key
                      ? "bg-[#FC4C02] border-[#FC4C02] text-white"
                      : "bg-[#18181d] border-white/10 text-zinc-400 hover:text-white"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {radarData && (
              <span className="text-xs text-zinc-400 font-mono">
                已评估活跃成员 <strong className="text-white">{radarData.total_members_evaluated}</strong> 人
              </span>
            )}
          </div>

          {distanceType !== "custom" ? (
            <div className="bg-[#18181d] border border-white/5 rounded-2xl p-3.5 space-y-2.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-bold text-zinc-400 mr-1">目标赛事：</span>
                {HOT_EVENTS.map((ev) => (
                  <button
                    key={ev}
                    onClick={() => {
                      setEventName(ev);
                      loadRadar({ overrideEvent: ev });
                    }}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition ${
                      eventName === ev
                        ? "bg-[#FC4C02]/20 border-[#FC4C02]/60 text-white"
                        : "bg-white/[0.03] border-white/5 text-zinc-400 hover:text-white"
                    }`}
                  >
                    {ev}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={customEventQuery}
                  onChange={(e) => setCustomEventQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && customEventQuery.trim()) {
                      setEventName(customEventQuery.trim());
                      loadRadar({ overrideEvent: customEventQuery.trim(), allowWeb: true });
                    }
                  }}
                  placeholder="输入任意其他路跑赛事名称检索规程..."
                  className="flex-1 bg-[#101014] border border-white/10 rounded-xl px-3 py-1.5 text-xs text-white placeholder-zinc-500"
                />
                <button
                  onClick={() => {
                    if (!customEventQuery.trim()) return;
                    setEventName(customEventQuery.trim());
                    loadRadar({ overrideEvent: customEventQuery.trim(), allowWeb: true });
                  }}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-xs font-bold text-white"
                >
                  <Search className="w-3.5 h-3.5" />
                  校准赛事
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-[#18181d] border border-white/5 rounded-2xl p-3.5 flex flex-wrap items-end gap-3">
              <div className="text-xs font-bold text-amber-300 w-full flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5" />
                自定义本周末跑团拉练距离与领跑配速（自动豁免田协完赛证书门槛）
              </div>
              <div>
                <label className="text-[11px] text-zinc-400 block mb-1">拉练距离 (km)</label>
                <input
                  type="number"
                  value={customDistKm}
                  onChange={(e) => setCustomDistKm(Number(e.target.value) || 30)}
                  className="w-24 bg-[#101014] border border-white/10 rounded-xl px-3 py-1.5 text-xs font-mono text-white"
                />
              </div>
              <div>
                <label className="text-[11px] text-zinc-400 block mb-1">领跑配速 (分:秒)</label>
                <input
                  type="text"
                  value={customPaceStr}
                  onChange={(e) => setCustomPaceStr(e.target.value)}
                  className="w-28 bg-[#101014] border border-white/10 rounded-xl px-3 py-1.5 text-xs font-mono text-white"
                />
              </div>
              <button
                onClick={() => loadRadar({ overrideDist: "custom" })}
                className="px-4 py-1.5 rounded-xl bg-[#FC4C02] text-xs font-bold text-white"
              >
                筛选拉练兔人选
              </button>
            </div>
          )}

          {/* Group Selector Strip */}
          {loading ? (
            <div className="py-10 flex items-center justify-center gap-2 text-xs text-zinc-400">
              <Loader2 className="w-4 h-4 animate-spin text-[#FC4C02]" />
              正在批量扫描全团成员训练负荷、巡航分段与赛事证书...
            </div>
          ) : groupsRanking.length > 0 ? (
            <>
              {distanceType !== "custom" && (
                <div className="flex items-center gap-2 overflow-x-auto pb-1">
                  {groupsRanking.map((grp: any) => {
                    const isAct = activeBucket?.group_code === grp.group_code;
                    return (
                      <button
                        key={grp.group_code}
                        onClick={() => setActiveGroupCode(grp.group_code)}
                        className={`shrink-0 px-3.5 py-2 rounded-2xl border text-left transition ${
                          isAct
                            ? "bg-[#FC4C02]/20 border-[#FC4C02] text-white"
                            : "bg-[#18181d] border-white/5 text-zinc-400 hover:border-white/20"
                        }`}
                      >
                        <div className="text-xs font-black text-white">{grp.group_label}</div>
                        <div className="text-[10px] font-mono text-zinc-400">
                          {grp.target_pace_str} · 适任{" "}
                          <strong className="text-emerald-400">{grp.qualified_count}</strong> 人
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Candidate Ranking Table / Cards */}
              {activeBucket?.candidates?.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {activeBucket.candidates.slice(0, 10).map((cand: any, idx: number) => (
                    <div
                      key={cand.uid}
                      className="bg-[#18181d] border border-white/5 hover:border-white/15 rounded-2xl p-4 flex flex-col justify-between gap-3 transition"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <span
                            className={`w-7 h-7 rounded-xl flex items-center justify-center text-xs font-black font-mono ${
                              idx === 0
                                ? "bg-amber-500 text-black"
                                : idx === 1
                                ? "bg-zinc-300 text-black"
                                : idx === 2
                                ? "bg-amber-700 text-white"
                                : "bg-white/10 text-zinc-300"
                            }`}
                          >
                            #{idx + 1}
                          </span>
                          <div>
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <button
                                onClick={() =>
                                  router.push(
                                    `/dashboard/analysis?student_user_id=${encodeURIComponent(cand.uid)}`
                                  )
                                }
                                className="text-sm font-bold text-white hover:text-[#FC4C02] inline-flex items-center gap-1 transition"
                              >
                                {cand.display_name}
                                <ExternalLink className="w-3 h-3 opacity-60" />
                              </button>
                              {cand.first_aid_cert_label && (
                                <span className="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-300 text-[10px] font-bold">
                                  🚑 {cand.first_aid_cert_label.split(" ").pop()}
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-zinc-400 font-mono mt-0.5">
                              当期预测 {cand.pred_finish_str} · 证书 {cand.cert_finish_str}
                              {cand.sigma_avg_sec !== null && cand.sigma_avg_sec !== undefined
                                ? ` · 波动 ±${cand.sigma_avg_sec}s`
                                : ""}
                            </div>
                          </div>
                        </div>

                        <div className="text-right shrink-0">
                          <div
                            className="text-lg font-black font-mono leading-none rgm-tone-text"
                            style={{ color: cand.verdict_color, ["--rgm-tone" as any]: cand.verdict_color }}
                          >
                            {cand.overall_score}分
                          </div>
                          <div className="text-[10px] font-bold text-zinc-400 mt-1">{cand.grade}级</div>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/5">
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                          <span
                            className="px-2 py-0.5 rounded-md font-bold rgm-tone-text"
                            style={{
                              backgroundColor: `${cand.verdict_color}18`,
                              color: cand.verdict_color,
                              ["--rgm-tone" as any]: cand.verdict_color,
                            }}
                          >
                            {cand.verdict_label}
                          </span>
                          {cand.cert_gate_status === "missing_cert" && (
                            <span className="text-emerald-400 font-mono font-bold">
                              私兔分 {cand.private_pacer_score}
                            </span>
                          )}
                        </div>

                        <button
                          onClick={() => openAssignModal(cand)}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-[#FC4C02]/20 hover:bg-[#FC4C02] text-[#FC4C02] hover:text-white text-xs font-bold transition"
                        >
                          <Send className="w-3 h-3" />
                          指派约跑领跑兔
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-zinc-500">
                  暂无活跃成员数据，邀请队员加入跑团并同步运动手表后即可自动排名。
                </div>
              )}
            </>
          ) : null}
        </div>
      )}

      {/* Assign Club Event Pacer Modal */}
      {assignCandidate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-[#141419] border border-white/10 rounded-3xl max-w-md w-full p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h4 className="text-base font-black text-white">
                🐰 指派【{assignCandidate.display_name}】担任活动领跑兔
              </h4>
              <button
                onClick={() => setAssignCandidate(null)}
                className="p-1.5 rounded-lg bg-white/5 text-zinc-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {assignableEvents.length === 0 ? (
              <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 leading-relaxed">
                当前跑团暂无未取消的线下约跑/拉练活动。请先在「活动约跑」页签发起一场周末拉练活动，即可一键指派领跑兔并发送站内受邀通知。
              </div>
            ) : (
              <>
                <div>
                  <label className="text-xs font-bold text-zinc-400 block mb-1.5">选择目标跑团活动</label>
                  <select
                    value={selectedEventId}
                    onChange={(e) => setSelectedEventId(e.target.value)}
                    className="w-full bg-[#101014] border border-white/10 rounded-xl px-3 py-2.5 text-xs text-white"
                  >
                    {assignableEvents.map((ev: any) => (
                      <option key={ev.id} value={String(ev.id)}>
                        {ev.title} ({(ev.meet_time || ev.start_date || "").slice(0, 10)})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-bold text-zinc-400 block mb-1.5">领跑配速组别标签</label>
                  <input
                    type="text"
                    value={assignPaceGroup}
                    onChange={(e) => setAssignPaceGroup(e.target.value)}
                    placeholder="例如：5:00/km 稳态领跑组"
                    className="w-full bg-[#101014] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-zinc-400 block mb-1.5">给队员的受邀寄语</label>
                  <textarea
                    rows={2}
                    value={assignNote}
                    onChange={(e) => setAssignNote(e.target.value)}
                    className="w-full bg-[#101014] border border-white/10 rounded-xl px-3 py-2 text-xs text-white resize-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    onClick={() => setAssignCandidate(null)}
                    className="px-4 py-2 rounded-xl bg-white/5 text-xs font-bold text-zinc-300"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleConfirmAssign}
                    disabled={assigning || !selectedEventId}
                    className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-[#FC4C02] hover:opacity-90 disabled:opacity-50 text-xs font-black text-white"
                  >
                    {assigning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    确认指派并通知队员
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
