"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import PersonalReportModal from "@/components/PersonalReportModal";

export type TrainingTabKey = "plan" | "report" | "analysis";

const TABS: { key: TrainingTabKey; label: string; href: string }[] = [
  { key: "plan", label: "📅 训练课表", href: "/dashboard/coach?tab=plan" },
  { key: "report", label: "🎯 教练诊断", href: "/dashboard/coach?tab=report" },
  { key: "analysis", label: "📊 身体数据与跑力", href: "/dashboard/analysis" },
];

/**
 * 「训练」三合一分段切换器 —— 与小程序 coach.vue 顶部三段切换保持同一心智模型。
 * - 同页内切换（plan / report）时传入 onChange，避免整页跳转；
 * - 跨页（analysis ↔ coach）时自动使用 Link 导航。
 */
export default function TrainingTabSwitcher({
  active,
  onChange,
}: {
  active: TrainingTabKey;
  onChange?: (key: TrainingTabKey) => void;
}) {
  const [uid, setUid] = useState<string>("");
  const [showPersonalReport, setShowPersonalReport] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data?.session?.user?.id) {
        setUid(data.session.user.id);
      } else if (typeof window !== "undefined") {
        const devUid = localStorage.getItem("rgm_dev_uid") || "";
        setUid(devUid);
      }
    });
  }, []);

  const baseCls = "px-4 sm:px-5 py-2 rounded-xl text-xs sm:text-sm font-bold transition whitespace-nowrap";
  const activeCls = "bg-white/10 text-white shadow-inner";
  const idleCls = "text-zinc-500 hover:text-zinc-200";

  return (
    <>
      <div className="inline-flex items-center gap-1 p-1 bg-[#121215] border border-white/[0.08] rounded-2xl overflow-x-auto max-w-full">
        {TABS.map((t) => {
          const cls = `${baseCls} ${active === t.key ? activeCls : idleCls}`;
          const sameRoute = onChange && t.key !== "analysis" && active !== "analysis";
          if (sameRoute) {
            return (
              <button key={t.key} onClick={() => onChange!(t.key)} className={cls}>
                {t.label}
              </button>
            );
          }
          return (
            <Link key={t.key} href={t.href} className={cls}>
              {t.label}
            </Link>
          );
        })}
        {uid && (
          <button
            onClick={() => setShowPersonalReport(true)}
            className="px-4 sm:px-5 py-2 rounded-xl text-xs sm:text-sm font-bold transition whitespace-nowrap text-amber-300 hover:bg-amber-500/15 cursor-pointer"
          >
            🖼️ 个人周报/月报
          </button>
        )}
      </div>

      {uid && (
        <PersonalReportModal
          isOpen={showPersonalReport}
          onClose={() => setShowPersonalReport(false)}
          userId={uid}
        />
      )}
    </>
  );
}
