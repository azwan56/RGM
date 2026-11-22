"use client";

import { useState, useEffect, useCallback } from "react";
import apiClient from "@/lib/apiClient";
import { useUiFeedback } from "@/components/ui/UiFeedbackProvider";
import { Target, Send, Copy, Sparkles, CheckSquare, Square, TrendingUp } from "lucide-react";

interface TargetedRecruitPanelProps {
  clubId: string;
  clubName: string;
  operatorUid: string;
}

const PRESETS = [
  { key: "", label: "全部符合条件" },
  { key: "female_gobi", label: "🎯 补强戈赛女子竞速" },
  { key: "pacer_330", label: "🐰 寻觅330官兔储备" },
  { key: "cross_club_elite", label: "🤝 同大群跨团高手" },
  { key: "org_newcomers", label: "🌱 新入大群新人" },
];

export default function TargetedRecruitPanel({
  clubId,
  clubName,
  operatorUid,
}: TargetedRecruitPanelProps) {
  const { showToast } = useUiFeedback();
  const [pool, setPool] = useState<"same_org" | "public_city" | "event_visitors">("same_org");
  const [preset, setPreset] = useState("");
  const [gender, setGender] = useState("");
  const [vdotMin, setVdotMin] = useState("");
  const [landmark, setLandmark] = useState("");

  const [candidates, setCandidates] = useState<any[]>([]);
  const [emptyReason, setEmptyReason] = useState("");
  const [selectedUids, setSelectedUids] = useState<string[]>([]);
  const [funnel, setFunnel] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // Composer fields
  const [preassignedGroup, setPreassignedGroup] = useState("A组");
  const [reasonTag, setReasonTag] = useState("同属大群校友 · 配速同频诚邀兼团");
  const [customMsg, setCustomMsg] = useState("");
  const [attachShowcase, setAttachShowcase] = useState(true);
  const [sending, setSending] = useState(false);
  const [lastSharePath, setLastSharePath] = useState("");

  const loadAll = useCallback(async () => {
    if (!clubId || !operatorUid) return;
    setLoading(true);
    try {
      const q = new URLSearchParams({ operator_uid: operatorUid, pool, limit: "30" });
      if (preset) q.set("preset", preset);
      if (gender) q.set("gender", gender);
      if (vdotMin) q.set("vdot_min", vdotMin);
      if (landmark.trim()) q.set("landmark", landmark.trim());

      const [cRes, fRes] = await Promise.all([
        apiClient.get(`/api/community/clubs/${encodeURIComponent(clubId)}/recruit-candidates?${q.toString()}`),
        apiClient.get(`/api/community/clubs/${encodeURIComponent(clubId)}/recruit-funnel?operator_uid=${encodeURIComponent(operatorUid)}`),
      ]);
      setCandidates(cRes.data?.candidates || []);
      setEmptyReason(cRes.data?.empty_reason || "");
      setFunnel(fRes.data);
    } catch (e: any) {
      setCandidates([]);
      const detail = e?.response?.data?.detail || e?.message || "";
      setEmptyReason(detail ? `加载候选人失败：${detail}` : "加载候选人失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }, [clubId, operatorUid, pool, preset, gender, vdotMin, landmark]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  function toggleSelect(uid: string) {
    setSelectedUids((prev) => {
      if (prev.includes(uid)) return prev.filter((x) => x !== uid);
      if (prev.length >= 20) {
        showToast("单批最多勾选 20 位跑友", "info");
        return prev;
      }
      return [...prev, uid];
    });
  }

  async function handleSendInvites(openShareOnly = false) {
    setSending(true);
    try {
      const targetIds = openShareOnly ? [] : selectedUids;
      const res = await apiClient.post(`/api/community/clubs/${encodeURIComponent(clubId)}/targeted-invites`, {
        inviter_uid: operatorUid,
        target_user_ids: targetIds,
        preassigned_group: preassignedGroup,
        reason_tag: reasonTag.trim(),
        custom_message: customMsg.trim(),
        attach_showcase: attachShowcase,
      });
      const sp = res.data?.share_join_path || "";
      setLastSharePath(sp);
      if (openShareOnly) {
        if (typeof window !== "undefined" && sp) {
          const fullUrl = `${window.location.origin}${sp}`;
          await navigator.clipboard?.writeText(fullUrl).catch(() => {});
          showToast(`✨ 已生成免码兼团专属特邀链接并复制：${sp}`);
        }
      } else {
        showToast(`🎉 已向 ${res.data?.created_count || 0} 位跑友发出预编组（${preassignedGroup || "标准"}）金色特邀函！`);
        setSelectedUids([]);
      }
      loadAll();
    } catch (e: any) {
      showToast("发送特邀失败：" + (e?.message || ""), "error");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="rgm-bento-card p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--rgm-divider)] pb-4">
        <div>
          <h2 className="text-base sm:text-lg font-black text-[var(--rgm-text)] flex items-center gap-2">
            <Target className="w-5 h-5 text-[#FC4C02]" />
            团长/教练多维靶向纳新雷达 · {clubName}
          </h2>
          <p className="text-xs text-[var(--rgm-text-2)] mt-1">
            跑团无排他性：仅展示在隐私设置中开启「允许被跑团搜索」的校友/跑友，支持一人多团无缝兼入并预编组
          </p>
        </div>

        {/* 4-Stage Conversion Funnel */}
        {funnel?.funnel && (
          <div className="flex items-center gap-2 text-xs flex-wrap">
            <TrendingUp className="w-4 h-4 text-emerald-500 shrink-0" />
            <span className="px-2.5 py-1 rounded-xl bg-[var(--rgm-card-2)] font-bold text-[var(--rgm-text)]">
              发函 {funnel.funnel.sent_count} → 查看 {funnel.funnel.viewed_count} → 免码入组 {funnel.funnel.accepted_count} → 首周出勤 {funnel.funnel.first_week_run_count}
            </span>
          </div>
        )}
      </div>

      {/* Candidate Pools + Tactical Presets */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex p-1 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] flex-wrap gap-1">
          {[
            { key: "same_org" as const, label: "🏛️ 同大群开放可搜校友（支持兼团）" },
            { key: "public_city" as const, label: "🌏 全平台允许被招募跑友" },
            { key: "event_visitors" as const, label: "🏃 本团活动访客" },
          ].map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => {
                setPool(p.key);
                setSelectedUids([]);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer ${
                pool === p.key ? "bg-[#FC4C02] text-white" : "text-[var(--rgm-text-2)]"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {PRESETS.map((pr) => (
            <button
              key={pr.key || "all"}
              type="button"
              onClick={() => setPreset(pr.key)}
              className={`px-2.5 py-1 rounded-full text-[11px] font-bold border cursor-pointer ${
                preset === pr.key
                  ? "bg-[var(--rgm-brand-tint)] border-[#FC4C02] text-[#FC4C02]"
                  : "bg-[var(--rgm-card-2)] border-[var(--rgm-border)] text-[var(--rgm-text-2)]"
              }`}
            >
              {pr.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <select
          value={gender}
          onChange={(e) => setGender(e.target.value)}
          className="px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
        >
          <option value="">不限性别</option>
          <option value="female">仅女性跑者</option>
          <option value="male">仅男性跑者</option>
        </select>
        <input
          type="number"
          value={vdotMin}
          onChange={(e) => setVdotMin(e.target.value)}
          placeholder="最低跑力 VDOT（如 45）"
          className="px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
        />
        <input
          type="text"
          value={landmark}
          onChange={(e) => setLandmark(e.target.value)}
          placeholder="常跑公园地标（如 世纪公园）"
          className="px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
        />
      </div>

      {/* Candidate List + Selection */}
      {loading ? (
        <div className="py-6 text-center text-xs text-[var(--rgm-text-muted)]">正在检索大群与同城可招募跑友...</div>
      ) : candidates.length === 0 ? (
        <div className="p-6 rounded-2xl bg-[var(--rgm-card-2)] text-center text-xs text-[var(--rgm-text-muted)]">
          {emptyReason || "当前筛选条件下暂无可邀约候选人（30天内已发或90天内婉拒会自动进入冷静期保护）"}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 max-h-72 overflow-y-auto pr-1">
          {candidates.map((cand) => {
            const checked = selectedUids.includes(cand.user_id);
            return (
              <div
                key={cand.user_id}
                onClick={() => toggleSelect(cand.user_id)}
                className={`p-3 rounded-2xl border cursor-pointer transition flex items-center justify-between gap-2 ${
                  checked
                    ? "bg-[var(--rgm-brand-tint)] border-[#FC4C02]"
                    : "bg-[var(--rgm-card-2)] border-[var(--rgm-border)] hover:border-[#FC4C02]/40"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  {checked ? (
                    <CheckSquare className="w-4 h-4 text-[#FC4C02] shrink-0" />
                  ) : (
                    <Square className="w-4 h-4 text-[var(--rgm-text-muted)] shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs font-black text-[var(--rgm-text)]">{cand.display_name}</span>
                      <span className="text-[10px] text-[var(--rgm-text-muted)]">{cand.age_group}</span>
                      {cand.other_clubs_count > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-[var(--rgm-blue-tint)] text-sky-400 text-[10px] font-bold">
                          已在 {cand.other_clubs_count} 个分团（支持兼团）
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-[var(--rgm-text-2)] truncate">
                      {cand.vdot_band} · 30日 {cand.monthly_km_30d} km
                      {(cand.running_landmarks || []).length > 0 ? ` · ${cand.running_landmarks.join("/")}` : ""}
                    </div>
                  </div>
                </div>
                <span className="text-[10px] font-bold text-[#FC4C02] shrink-0">推荐 {cand.suggested_group}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Golden Invite Composer */}
      <div className="p-4 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-black text-[var(--rgm-text)] flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-amber-500" />
            定向特邀函配置（已选 {selectedUids.length} / 20 人）
          </div>
          <label className="flex items-center gap-1.5 text-xs text-[var(--rgm-text-2)] cursor-pointer">
            <input
              type="checkbox"
              checked={attachShowcase}
              onChange={(e) => setAttachShowcase(e.target.checked)}
              className="accent-[#FC4C02]"
            />
            附带「跑团品牌宣传页 + 实拍相册 + 主教练资历」背书
          </label>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <select
            value={preassignedGroup}
            onChange={(e) => setPreassignedGroup(e.target.value)}
            className="px-3 py-2 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
          >
            <option value="A组">预编入 A组（竞速/破330）</option>
            <option value="B组">预编入 B组（进阶稳态）</option>
            <option value="C组">预编入 C组（有氧打底）</option>
            <option value="">暂不预设分组</option>
          </select>
          <input
            type="text"
            value={reasonTag}
            onChange={(e) => setReasonTag(e.target.value)}
            placeholder="邀请推荐理由标签"
            className="sm:col-span-2 px-3 py-2 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <input
            type="text"
            value={customMsg}
            onChange={(e) => setCustomMsg(e.target.value)}
            placeholder="选填团长专属寄语（例如：周六世纪公园长距离等你一起发车！）"
            className="flex-1 min-w-[220px] px-3 py-2 rounded-xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
          />
          <button
            type="button"
            disabled={sending}
            onClick={() => handleSendInvites(true)}
            className="px-3.5 py-2 rounded-xl border border-[var(--rgm-border)] bg-[var(--rgm-card)] text-xs font-bold text-[var(--rgm-text)] flex items-center gap-1.5 cursor-pointer"
          >
            <Copy className="w-3.5 h-3.5" /> 生成免码兼团特邀链接
          </button>
          <button
            type="button"
            disabled={sending || selectedUids.length === 0}
            onClick={() => handleSendInvites(false)}
            className="px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-black flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <Send className="w-3.5 h-3.5" /> 发出金色特邀函 ({selectedUids.length})
          </button>
        </div>

        {lastSharePath && (
          <div className="text-[11px] text-emerald-500 font-bold">
            ✅ 最新特邀直达路径：{lastSharePath}（支持免码一键兼入并展示跑团品牌主页）
          </div>
        )}
      </div>
    </div>
  );
}
