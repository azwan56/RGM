"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function TeamCoachWorkbenchPage() {
  const router = useRouter();

  useEffect(() => {
    const sp = new URLSearchParams(window.location.search);
    if (!sp.get("tab")) {
      sp.set("tab", "coach");
    }
    router.replace(`/dashboard/team?${sp.toString()}`);
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center text-sm text-[var(--rgm-text-muted)]">
      正在打开教练工作台…
    </div>
  );
}
