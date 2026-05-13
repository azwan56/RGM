"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/firebase";
import axios from "@/lib/apiClient";
import dynamic from "next/dynamic";
import PageNav from "@/components/PageNav";

const FitnessChart = dynamic(() => import("@/components/FitnessChart"), {
  loading: () => <div className="h-80 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />,
  ssr: false,
});

const RaceDashboard = dynamic(() => import("@/components/RaceDashboard"), {
  loading: () => (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div className="h-64 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />
      <div className="h-64 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />
    </div>
  ),
  ssr: false,
});

const TrendChart = dynamic(() => import("@/components/TrendChart"), {
  loading: () => <div className="h-64 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />,
  ssr: false,
});

const GoalHistoryPanel = dynamic(() => import("@/components/GoalHistoryPanel"), {
  loading: () => (
    <div className="space-y-5">
      <div className="h-56 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />
      <div className="h-40 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />
    </div>
  ),
  ssr: false,
});

export default function AnalysisPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [bundleData, setBundleData] = useState<any>(null);

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  // Fetch all analysis data in ONE request (replaces 4 serial requests)
  const fetchBundle = useCallback(async (uid: string) => {
    try {
      const t0 = Date.now();
      const res = await axios.post(`${backendUrl}/api/science/analysis-bundle`, { uid, days: 30, months: 6 });
      console.log(`[analysis] Bundle loaded in ${Date.now() - t0}ms`);
      setBundleData(res.data);
    } catch (err) {
      console.error("Analysis bundle error:", err);
      // Fallback: components will fetch individually
    }
  }, [backendUrl]);

  useEffect(() => {
    const unsub = auth.onAuthStateChanged(async (u) => {
      if (!u) {
        router.push("/");
        return;
      }
      setUser(u);
      await fetchBundle(u.uid);
      setLoading(false);
    });
    return () => unsub();
  }, [router, fetchBundle]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-[#FC4C02] border-t-transparent rounded-full animate-spin" />
          <p className="text-zinc-400 text-sm">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white pt-20 md:pt-24 px-4 md:px-6 pb-16 md:pb-20 relative">
      <div className="absolute top-0 right-0 w-[40%] h-[40%] rounded-full bg-blue-600/10 blur-[160px] pointer-events-none" />

      <main className="max-w-5xl mx-auto space-y-8 relative z-10">
        {/* Header */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-black">深度分析</h1>
            <p className="text-zinc-500 text-sm">体能趋势 · 跑力诊断 · 月度统计 · 目标回顾</p>
          </div>
          <PageNav />
        </header>

        {/* Fitness Trend (CTL · ATL · TSB) */}
        {user && (
          <section>
            <FitnessChart uid={user.uid} initialData={bundleData?.fitness_trend?.data} />
          </section>
        )}

        {/* Race Analysis + Training Zones (VDOT) */}
        {user && (
          <section>
            <RaceDashboard uid={user.uid} initialData={bundleData?.race_predictor} />
          </section>
        )}

        {/* Monthly Trend Chart */}
        {user && (
          <section>
            <TrendChart uid={user.uid} initialData={bundleData?.monthly_trend?.data} />
          </section>
        )}

        {/* Goal History + Annual Summary */}
        {user && (
          <section>
            <GoalHistoryPanel uid={user.uid} initialData={bundleData?.stats_summary} />
          </section>
        )}
      </main>
    </div>
  );
}

