"use client";

import { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import { ShowcasePlazaView } from "@/components/community/ShowcaseViews";
import { supabase } from "@/lib/supabase";

export default function ShowcasePlazaPage() {
  const [viewerUid, setViewerUid] = useState<string>("");
  const [initialTab, setInitialTab] = useState<"clubs" | "coaches">("clubs");
  const [initialClubId, setInitialClubId] = useState("");
  const [initialCoachUid, setInitialCoachUid] = useState("");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const sp = new URLSearchParams(window.location.search);
      const t = sp.get("tab");
      if (t === "coaches") setInitialTab("coaches");
      setInitialClubId(sp.get("club_id") || "");
      setInitialCoachUid(sp.get("coach_uid") || "");
    }
    supabase.auth.getSession().then(({ data }) => {
      if (data?.session?.user?.id) {
        setViewerUid(data.session.user.id);
      }
      setMounted(true);
    });
  }, []);

  return (
    <div className="min-h-screen bg-[var(--rgm-bg)] text-[var(--rgm-text)] rgm-web3-page">
      <Navbar />
      <main className="rgm-page-container py-6">
        {mounted ? (
          <ShowcasePlazaView
            viewerUid={viewerUid || undefined}
            initialTab={initialTab}
            initialClubId={initialClubId}
            initialCoachUid={initialCoachUid}
          />
        ) : (
          <div className="rgm-bento-card p-10 text-center text-xs text-[var(--rgm-text-muted)]">
            正在进入选团与名帅风采展厅...
          </div>
        )}
      </main>
    </div>
  );
}
