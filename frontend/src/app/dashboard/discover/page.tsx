"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import BuddyDiscoveryView from "@/components/community/BuddyDiscoveryView";
import { supabase } from "@/lib/supabase";

export default function DiscoverBuddiesPage() {
  const router = useRouter();
  const [uid, setUid] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const userId = data?.session?.user?.id;
      if (!userId) {
        router.replace("/login");
        return;
      }
      setUid(userId);
      setReady(true);
    });
  }, [router]);

  return (
    <div className="min-h-screen bg-[var(--rgm-bg)] text-[var(--rgm-text)] rgm-web3-page">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {!ready ? (
          <div className="rgm-bento-card p-10 text-center text-xs text-[var(--rgm-text-muted)]">
            正在加载六维同频寻搭子...
          </div>
        ) : (
          <BuddyDiscoveryView uid={uid} />
        )}
      </main>
    </div>
  );
}
