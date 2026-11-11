"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Check,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Copy,
  Flag,
  Landmark,
  Lock,
  MapPin,
  Settings,
  ShieldCheck,
  Unlock,
  Users,
} from "lucide-react";
import { showToast } from "@/components/ui/UiFeedbackProvider";

export interface OrgManagementHubProps {
  activeOrg: any;
  managedOrgs: any[];
  currentUserId?: string;
  onSelectOrg: (org: any) => void;
  onOpenReport: (org: any) => void;
  onOpenEvents: (org: any) => void;
  onOpenRoster: (org: any) => void;
  onOpenSettings: (org: any) => void;
  onOpenFieldRules: (org: any) => void;
}

const COLLAPSE_STORAGE_KEY = "rgm_org_hub_collapsed";

export default function OrgManagementHub({
  activeOrg,
  managedOrgs,
  currentUserId,
  onSelectOrg,
  onOpenReport,
  onOpenEvents,
  onOpenRoster,
  onOpenSettings,
  onOpenFieldRules,
}: OrgManagementHubProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(COLLAPSE_STORAGE_KEY);
      if (saved === "1") setCollapsed(true);
    } catch {}
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSE_STORAGE_KEY, next ? "1" : "0");
      } catch {}
      return next;
    });
  };

  const isOwner =
    activeOrg?.role === "owner" ||
    (Boolean(currentUserId) && activeOrg?.owner_id === currentUserId);

  const subClubsCount = Number(activeOrg?.sub_clubs_count ?? 0);
  const memberCount = Number(activeOrg?.member_count ?? 0);
  const pendingCount = Number(activeOrg?.pending_review_count ?? 0);
  const isFreeJoin = activeOrg?.join_mode === "free";
  const inviteCode = String(activeOrg?.invite_code || "").trim();

  const fieldStats = useMemo(() => {
    const rules = Array.isArray(activeOrg?.field_rules) ? activeOrg.field_rules : [];
    if (rules.length === 0) {
      return { required: 4, optional: 6, hidden: 0 };
    }
    let required = 0;
    let optional = 0;
    let hidden = 0;
    for (const r of rules) {
      if (r.mode === "hidden" || r.hidden === true || r.visible === false) {
        hidden += 1;
      } else if (r.mode === "required" || (r.mode !== "optional" && Boolean(r.required))) {
        required += 1;
      } else {
        optional += 1;
      }
    }
    return { required, optional, hidden };
  }, [activeOrg?.field_rules]);

  const handleCopyInviteCode = () => {
    if (!inviteCode) {
      onOpenSettings(activeOrg);
      return;
    }
    try {
      navigator.clipboard.writeText(inviteCode);
      setCopiedCode(true);
      showToast(`已复制【${activeOrg.name}】大群专属邀请码：${inviteCode}`);
      setTimeout(() => setCopiedCode(false), 2000);
    } catch {
      showToast(`大群专属邀请码：${inviteCode}`);
    }
  };

  if (!activeOrg) return null;

  return (
    <section className="rgm-org-hub rounded-3xl p-5 sm:p-6 transition-all">
      {/* Tier 1: Full-Width Executive Header Bar */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
        <div className="flex items-start sm:items-center gap-3.5 min-w-0">
          <div className="rgm-org-emblem w-11 h-11 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center shrink-0">
            <Landmark className="w-5 h-5 sm:w-6 sm:h-6" />
          </div>

          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-lg sm:text-xl font-black tracking-tight text-[var(--rgm-text)]">
                {activeOrg.name}
              </h2>
              <span className="text-xs font-bold text-[var(--rgm-text-2)]">
                · 大群管理工作台
              </span>
              <span className="rgm-org-role-badge inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold">
                {isOwner ? "👑 大群主理人" : "🛡️ 大群管理员"}
              </span>

              <span className="rgm-org-chip inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold">
                🏟️ {subClubsCount} 个下属分团
              </span>

              <span className="rgm-org-chip inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold">
                👥 {memberCount} 位成员
                {pendingCount > 0 && (
                  <span className="ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-extrabold bg-[#FC4C02] text-white">
                    待审 {pendingCount}
                  </span>
                )}
              </span>

              {isFreeJoin ? (
                <button
                  type="button"
                  onClick={() => onOpenSettings(activeOrg)}
                  className="rgm-org-chip rgm-org-chip-copy inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold transition cursor-pointer"
                  title="点击调整大群入会模式"
                >
                  <Unlock className="w-3 h-3 text-emerald-500" />
                  <span>自由免码入会</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleCopyInviteCode}
                  className="rgm-org-chip rgm-org-chip-copy inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold transition cursor-pointer"
                  title={inviteCode ? "点击一键复制大群邀请码" : "点击配置大群专属邀请码"}
                >
                  <Lock className="w-3 h-3 text-[#FC4C02]" />
                  <span>
                    邀请码:{" "}
                    <strong className="font-mono tracking-wider">
                      {inviteCode || "点击设置"}
                    </strong>
                  </span>
                  {inviteCode &&
                    (copiedCode ? (
                      <Check className="w-3 h-3 text-emerald-500" />
                    ) : (
                      <Copy className="w-3 h-3 opacity-70" />
                    ))}
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 text-xs text-[var(--rgm-text-2)]">
              <span className="inline-flex items-center gap-1 shrink-0 text-[var(--rgm-text-muted)]">
                <MapPin className="w-3 h-3" />
                {activeOrg.city || "上海"}
              </span>
              <span className="text-[var(--rgm-text-muted)]">·</span>
              <p className="truncate">
                {activeOrg.description ||
                  "统管下属分跑团横向 PK 战报、跨跑团联合拉练活动、入会准入字段（必填 / 选填 / 隐藏）及实名花名册审核"}
              </p>
            </div>
          </div>
        </div>

        {/* Right Controls: Multi-Org Pill Switcher & Collapse Toggle */}
        <div className="flex items-center justify-between xl:justify-end gap-2.5 flex-wrap shrink-0">
          {managedOrgs.length > 1 && (
            <div className="rgm-org-switcher inline-flex items-center gap-1 p-1 rounded-2xl max-w-full overflow-x-auto no-scrollbar">
              <span className="px-2 text-[11px] font-semibold text-[var(--rgm-text-muted)] shrink-0">
                切换大群
              </span>
              {managedOrgs.map((org) => {
                const active = org.id === activeOrg.id;
                return (
                  <button
                    key={org.id}
                    type="button"
                    onClick={() => onSelectOrg(org)}
                    className={`rgm-org-switcher-pill px-3 py-1 rounded-xl text-xs font-bold transition whitespace-nowrap cursor-pointer ${
                      active ? "is-active" : ""
                    }`}
                  >
                    {org.name}
                  </button>
                );
              })}
            </div>
          )}

          <button
            type="button"
            onClick={toggleCollapsed}
            className="rgm-org-collapse-btn inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer"
          >
            <span>{collapsed ? "展开管理 (5)" : "收起"}</span>
            {collapsed ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronUp className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Tier 2: Balanced 5-Column Bento Action Grid */}
      {!collapsed && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 pt-4 mt-4 border-t border-[var(--rgm-border)]">
          {/* 1. 大群报表与分团 PK (Primary Highlight) */}
          <button
            type="button"
            onClick={() => onOpenReport(activeOrg)}
            className="rgm-org-tile is-primary group rounded-2xl p-3.5 text-left flex flex-col justify-between gap-2.5 cursor-pointer"
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="rgm-org-tile-icon w-8 h-8 rounded-xl flex items-center justify-center shrink-0">
                  <BarChart3 className="w-4 h-4" />
                </span>
                <span className="rgm-org-tile-tag is-brand px-2 py-0.5 rounded-full text-[10px] font-extrabold">
                  全域战报
                </span>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--rgm-text-muted)] group-hover:translate-x-0.5 group-hover:text-[#FC4C02] transition-transform" />
            </div>
            <div>
              <div className="text-[13px] sm:text-sm font-black text-[var(--rgm-text)]">
                大群报表与分团 PK
              </div>
              <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5 truncate">
                {subClubsCount} 个分团对比 · 跨团去重汇总
              </div>
            </div>
          </button>

          {/* 2. 跨跑团联合活动 */}
          <button
            type="button"
            onClick={() => onOpenEvents(activeOrg)}
            className="rgm-org-tile group rounded-2xl p-3.5 text-left flex flex-col justify-between gap-2.5 cursor-pointer"
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="rgm-org-tile-icon w-8 h-8 rounded-xl flex items-center justify-center shrink-0">
                  <Flag className="w-4 h-4" />
                </span>
                <span className="rgm-org-tile-tag px-2 py-0.5 rounded-full text-[10px] font-bold">
                  多团联动
                </span>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--rgm-text-muted)] group-hover:translate-x-0.5 group-hover:text-[#FC4C02] transition-transform" />
            </div>
            <div>
              <div className="text-[13px] sm:text-sm font-extrabold text-[var(--rgm-text)]">
                跨跑团联合活动
              </div>
              <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5 truncate">
                联合 LSD 合练 · 分团里程赛
              </div>
            </div>
          </button>

          {/* 3. 大群花名册与审核 */}
          <button
            type="button"
            onClick={() => onOpenRoster(activeOrg)}
            className="rgm-org-tile group rounded-2xl p-3.5 text-left flex flex-col justify-between gap-2.5 cursor-pointer"
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="rgm-org-tile-icon w-8 h-8 rounded-xl flex items-center justify-center shrink-0">
                  <Users className="w-4 h-4" />
                </span>
                <span
                  className={`rgm-org-tile-tag px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                    pendingCount > 0 ? "is-alert" : "is-ok"
                  }`}
                >
                  {pendingCount > 0 ? `待审 ${pendingCount} 人` : `在册 ${memberCount} 人`}
                </span>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--rgm-text-muted)] group-hover:translate-x-0.5 group-hover:text-[#FC4C02] transition-transform" />
            </div>
            <div>
              <div className="text-[13px] sm:text-sm font-extrabold text-[var(--rgm-text)]">
                大群花名册与审核
              </div>
              <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5 truncate">
                实名班级核验 · 管理员委派
              </div>
            </div>
          </button>

          {/* 4. 大群设定与邀请码 */}
          <button
            type="button"
            onClick={() => onOpenSettings(activeOrg)}
            className="rgm-org-tile group rounded-2xl p-3.5 text-left flex flex-col justify-between gap-2.5 cursor-pointer"
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="rgm-org-tile-icon w-8 h-8 rounded-xl flex items-center justify-center shrink-0">
                  <Settings className="w-4 h-4" />
                </span>
                <span
                  className={`rgm-org-tile-tag px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    isFreeJoin ? "is-ok" : ""
                  }`}
                >
                  {isFreeJoin ? "自由入会" : "凭码入会"}
                </span>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--rgm-text-muted)] group-hover:translate-x-0.5 group-hover:text-[#FC4C02] transition-transform" />
            </div>
            <div>
              <div className="text-[13px] sm:text-sm font-extrabold text-[var(--rgm-text)]">
                大群设定与邀请码
              </div>
              <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5 truncate">
                {isFreeJoin
                  ? "当前免邀请码开放加入"
                  : `基础设定 · 邀请码 ${inviteCode || "未设"}`}
              </div>
            </div>
          </button>

          {/* 5. 准入信息配置 */}
          <button
            type="button"
            onClick={() => onOpenFieldRules(activeOrg)}
            className="rgm-org-tile group rounded-2xl p-3.5 text-left flex flex-col justify-between gap-2.5 cursor-pointer"
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="rgm-org-tile-icon w-8 h-8 rounded-xl flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-4 h-4" />
                </span>
                <span className="rgm-org-tile-tag px-2 py-0.5 rounded-full text-[10px] font-bold">
                  必填 {fieldStats.required} 项
                </span>
              </div>
              <ChevronRight className="w-4 h-4 text-[var(--rgm-text-muted)] group-hover:translate-x-0.5 group-hover:text-[#FC4C02] transition-transform" />
            </div>
            <div>
              <div className="text-[13px] sm:text-sm font-extrabold text-[var(--rgm-text)]">
                准入信息字段配置
              </div>
              <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5 truncate">
                必填 {fieldStats.required} · 选填 {fieldStats.optional} · 隐藏 {fieldStats.hidden}
              </div>
            </div>
          </button>
        </div>
      )}
    </section>
  );
}
