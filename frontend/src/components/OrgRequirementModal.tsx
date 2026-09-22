"use client";

import React from "react";
import { AlertTriangle, Clock, X, ShieldAlert, ArrowRight, CheckCircle2 } from "lucide-react";

export interface OrgReminderInfo {
  hasReminder: boolean;
  type: "suspended" | "temporary" | "none";
  firstOrg?: any;
  orgCount?: number;
  orgNames?: string;
  missingLabels?: string;
  missingFields?: { field: string; label: string }[];
  remainingDays?: number;
  title?: string;
  content?: string;
  confirmText?: string;
  cancelText?: string;
}

interface OrgRequirementModalProps {
  isOpen: boolean;
  onClose: () => void;
  reminder: OrgReminderInfo | null;
  onNavigateToProfile: () => void;
}

export default function OrgRequirementModal({
  isOpen,
  onClose,
  reminder,
  onNavigateToProfile,
}: OrgRequirementModalProps) {
  if (!isOpen || !reminder || !reminder.hasReminder) return null;

  const isSuspended = reminder.type === "suspended";
  const orgName = reminder.firstOrg?.name || "跑团大组织";
  const missingList = reminder.missingFields || [];
  const daysLeft = reminder.remainingDays ?? 14;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className={`relative w-full max-w-lg bg-[#121215] border ${
          isSuspended ? "border-rose-500/40" : "border-amber-500/40"
        } rounded-3xl p-6 sm:p-8 shadow-2xl overflow-hidden`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Subtle Ambient Glow */}
        <div
          className={`absolute -top-24 -right-24 w-60 h-60 ${
            isSuspended ? "bg-rose-500/10" : "bg-amber-500/15"
          } rounded-full blur-3xl pointer-events-none`}
        />

        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-xl text-zinc-400 hover:text-white hover:bg-white/5 transition"
          aria-label="关闭"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3 mb-4">
          <div
            className={`p-3 rounded-2xl ${
              isSuspended
                ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
            }`}
          >
            {isSuspended ? <ShieldAlert className="w-6 h-6" /> : <AlertTriangle className="w-6 h-6" />}
          </div>
          <div>
            <span
              className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold tracking-wide uppercase ${
                isSuspended ? "bg-rose-500/20 text-rose-300" : "bg-amber-500/20 text-amber-300"
              }`}
            >
              {isSuspended ? "访问权限已暂停" : `临时成员 · 剩余 ${daysLeft} 天`}
            </span>
            <h2 className="text-xl font-black text-white mt-1">
              【{orgName}】档案信息待补齐
            </h2>
          </div>
        </div>

        {/* Modal Content */}
        <div className="space-y-4 text-sm text-zinc-300">
          <p className="leading-relaxed">
            {isSuspended
              ? `您在【${orgName}】的2周临时访问期已过。由于超期未完成入队必填字段并获审核确认，已暂停组织及下属跑团的浏览与活动参与权限！请立即补齐必填资料以恢复资格。`
              : `为了保障户外拉练安全合规、人身意外险投保及赛事准入核验，请尽快补齐以下必填项目。超期未完成将暂停组织成员资格：`}
          </p>

          {/* Missing Fields Badges */}
          {missingList.length > 0 && (
            <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/5 space-y-2">
              <span className="text-xs font-medium text-zinc-400">待完善必填项目：</span>
              <div className="flex flex-wrap gap-2 pt-1">
                {missingList.map((item, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-amber-500/15 border border-amber-500/30 text-amber-300"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                    {item.label || item.field}
                  </span>
                ))}
              </div>
            </div>
          )}

          {!isSuspended && (
            <div className="flex items-center gap-2 text-xs text-amber-400/90 font-medium">
              <Clock className="w-4 h-4 flex-shrink-0" />
              <span>距临时加入考察期截止还剩 <strong>{daysLeft}</strong> 天，请尽快补全。</span>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 mt-7 pt-4 border-t border-white/5">
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl text-xs font-semibold text-zinc-400 hover:text-white hover:bg-white/5 transition"
          >
            {reminder.cancelText || "稍后再说"}
          </button>
          <button
            onClick={onNavigateToProfile}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-amber-500 via-[#FC4C02] to-amber-600 shadow-lg shadow-orange-500/25 hover:brightness-110 active:scale-[0.98] transition cursor-pointer"
          >
            <span>{reminder.confirmText || "立即前往补齐"}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
