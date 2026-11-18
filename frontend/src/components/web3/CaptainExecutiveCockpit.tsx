"use client";

import React from "react";
import {
  Copy,
  FileBarChart2,
  QrCode,
  ShieldCheck,
  Target,
  Users,
  Zap,
} from "lucide-react";
import { showToast } from "@/components/ui/UiFeedbackProvider";

interface CaptainExecutiveCockpitProps {
  club: any;
  dashboardMetrics: any;
  members: any[];
  eventsCount: number;
  onOpenInviteModal: () => void;
  onOpenClubReport: () => void;
  onSwitchToEvents: () => void;
  onSwitchToCoach: () => void;
}

export default function CaptainExecutiveCockpit({
  club,
  dashboardMetrics,
  members,
  eventsCount,
  onOpenInviteModal,
  onOpenClubReport,
  onSwitchToEvents,
  onSwitchToCoach,
}: CaptainExecutiveCockpitProps) {
  const totalMembers = Math.max(
    Number(dashboardMetrics?.members_count || members?.length || 0),
    1
  );
  const activeRunners = Math.max(
    (members || []).filter(
      (m) => Number(m?.month_km || m?.distance_km || m?.total_km || 0) > 0
    ).length,
    Number(dashboardMetrics?.active_members_count || 0)
  );
  const monthKm = parseFloat(String(dashboardMetrics?.total_month_km || "0")) || 0;
  const monthTargetKm = Math.max(totalMembers * 80, 200);
  const completionPct = Math.min(100, Math.round((monthKm / monthTargetKm) * 100));

  const coachesCount =
    Number(dashboardMetrics?.coaches_count || 0) ||
    (members || []).filter((m) => m.role === "coach" || m.role === "owner").length ||
    1;

  const inviteCode = String(club?.invite_code || "").trim();
  const clubStatus = String(club?.status || "active");
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (completionPct / 100) * circumference;

  async function handleCopyInviteCode() {
    if (!inviteCode) {
      onOpenInviteModal();
      return;
    }
    try {
      await navigator.clipboard.writeText(inviteCode);
      showToast(`已复制 6 位入团邀请码：${inviteCode}`);
    } catch {
      onOpenInviteModal();
    }
  }

  return (
    <section
      aria-label="团长经营驾驶舱"
      className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
    >
      {/* Card 1: 月度跑量目标达成环 */}
      <div className="rgm-bento-card p-5 flex flex-col justify-between gap-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
              月度跑量目标环
            </div>
            <div className="text-xl font-black text-white mt-1">
              {monthKm.toFixed(1)}{" "}
              <span className="text-xs font-bold text-zinc-400">/ {monthTargetKm} km</span>
            </div>
            <div className="text-[11px] text-emerald-400 font-semibold mt-0.5">
              全团已完成 {completionPct}%
            </div>
          </div>

          <div className="relative w-14 h-14 flex items-center justify-center shrink-0">
            <svg className="w-14 h-14 -rotate-90" viewBox="0 0 56 56">
              <circle
                cx="28"
                cy="28"
                r={radius}
                stroke="currentColor"
                strokeWidth="5"
                fill="none"
                className="text-white/10"
              />
              <circle
                cx="28"
                cy="28"
                r={radius}
                stroke="#FC4C02"
                strokeWidth="5"
                strokeLinecap="round"
                fill="none"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
              />
            </svg>
            <span className="absolute text-[11px] font-black text-white">
              {completionPct}%
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenClubReport}
          className="w-full py-2 px-3 rounded-xl bg-[#FC4C02] hover:brightness-110 text-white text-xs font-bold flex items-center justify-center gap-1.5 transition"
        >
          <FileBarChart2 className="w-3.5 h-3.5" />
          <span>📊 生成跑团月报海报</span>
        </button>
      </div>

      {/* Card 2: 成员激活漏斗 */}
      <div className="rgm-bento-card p-5 flex flex-col justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
              成员激活漏斗
            </span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white">{members?.length || totalMembers}</span>
            <span className="text-xs text-zinc-400">位注册队员</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="px-2.5 py-1.5 rounded-xl bg-white/[0.03] border border-white/10">
              <div className="text-zinc-400">活跃打卡</div>
              <div className="font-black text-emerald-400 mt-0.5">
                {activeRunners || Math.min(members?.length || 1, totalMembers)} 人
              </div>
            </div>
            <div className="px-2.5 py-1.5 rounded-xl bg-white/[0.03] border border-white/10">
              <div className="text-zinc-400">进行中挑战赛</div>
              <div className="font-black text-amber-400 mt-0.5">{eventsCount} 场</div>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={onSwitchToEvents}
          className="w-full py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-bold text-zinc-200 flex items-center justify-center gap-1.5 transition"
        >
          <Target className="w-3.5 h-3.5 text-[#FC4C02]" />
          <span>🎯 管理挑战赛 ({eventsCount})</span>
        </button>
      </div>

      {/* Card 3: 6位入团邀请码与招募卡 */}
      <div className="rgm-bento-card p-5 flex flex-col justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
              6 位入团邀请码
            </span>
            <QrCode className="w-4 h-4 text-[#FC4C02]" />
          </div>
          <button
            type="button"
            onClick={handleCopyInviteCode}
            className="w-full px-3 py-2 rounded-xl bg-white/[0.03] hover:bg-white/[0.06] border border-white/10 flex items-center justify-between gap-2 transition"
          >
            <span className="text-lg font-black tracking-[0.2em] font-mono text-white">
              {inviteCode || "生成中"}
            </span>
            <Copy className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
          </button>
          <div className="text-[11px] text-zinc-400">
            点击邀请码可一键复制，或弹出专属招募小程序码卡片
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenInviteModal}
          className="w-full py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-bold text-zinc-200 flex items-center justify-center gap-1.5 transition"
        >
          <QrCode className="w-3.5 h-3.5 text-[#FC4C02]" />
          <span>🪪 打开招募邀请函</span>
        </button>
      </div>

      {/* Card 4: 教练协同与治理快捷舱 */}
      <div className="rgm-bento-card p-5 flex flex-col justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
              治理与教练协同
            </span>
            <ShieldCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`px-2.5 py-1 rounded-full text-[11px] font-bold border ${
                clubStatus === "active"
                  ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                  : clubStatus === "paused"
                  ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                  : "bg-rose-500/15 text-rose-300 border-rose-500/30"
              }`}
            >
              {clubStatus === "active"
                ? "🟢 正常运行"
                : clubStatus === "paused"
                ? "⏸️ 已暂停"
                : "🔒 已锁定"}
            </span>
            <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30">
              🧢 {coachesCount} 位教练
            </span>
          </div>
          <p className="text-[11px] text-zinc-400 leading-relaxed">
            可随时协同教练组对高风险疲劳队员发起极速点评与周课表微调。
          </p>
        </div>

        <button
          type="button"
          onClick={onSwitchToCoach}
          className="w-full py-2 px-3 rounded-xl bg-purple-500/15 hover:bg-purple-500/25 border border-purple-500/30 text-xs font-bold text-purple-200 flex items-center justify-center gap-1.5 transition"
        >
          <Zap className="w-3.5 h-3.5" />
          <span>🧢 切入教练批阅工作台</span>
        </button>
      </div>
    </section>
  );
}
