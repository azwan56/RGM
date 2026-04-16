"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { auth } from "@/lib/firebase";
import dynamic from "next/dynamic";

const GoalSettingForm = dynamic(() => import("@/components/GoalSettingForm"), {
  loading: () => <div className="h-48 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />,
  ssr: false,
});

const AiCoachWidget = dynamic(() => import("@/components/AiCoachWidget"), {
  loading: () => <div className="h-80 bg-white/5 border border-white/10 rounded-3xl animate-pulse" />,
  ssr: false,
});


export default function CoachPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsub = auth.onAuthStateChanged((u) => {
      if (!u) {
        router.push("/");
        return;
      }
      setUser(u);
      setLoading(false);
    });
    return () => unsub();
  }, [router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-emerald-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-zinc-400 text-sm">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white pt-20 md:pt-24 px-4 md:px-6 pb-16 md:pb-20 relative">
      <div className="absolute top-0 right-0 w-[40%] h-[40%] rounded-full bg-emerald-600/10 blur-[160px] pointer-events-none" />

      <main className="max-w-5xl mx-auto space-y-8 relative z-10">
        {/* Header */}
        <header className="flex items-center gap-4">
          <Link
            href="/dashboard"
            className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center hover:bg-white/10 transition-all"
          >
            <svg className="w-5 h-5 text-zinc-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <div>
            <h1 className="text-2xl md:text-3xl font-black">AI 教练</h1>
            <p className="text-zinc-500 text-sm">目标设定 · 备赛指导 · 训练建议</p>
          </div>
        </header>

        {/* Goal Setting */}
        <section>
          <GoalSettingForm />
        </section>

        {/* AI Coach Analysis */}
        {user && (
          <section>
            <AiCoachWidget uid={user.uid} />
          </section>
        )}
      </main>
    </div>
  );
}
