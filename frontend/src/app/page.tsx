"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/firebase";
import { signOut } from "firebase/auth";
import StravaConnectBtn from "@/components/StravaConnectBtn";
import AuthModal from "@/components/AuthModal";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    return auth.onAuthStateChanged((u) => {
      setUser(u);
      setAuthLoading(false);
    });
  }, []);

  const isLoggedIn = !!user;

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white overflow-hidden relative">
      {/* Background aesthetic blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-[#FC4C02]/20 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-600/10 blur-[150px] pointer-events-none" />

      <main className="max-w-7xl mx-auto px-4 md:px-6 pt-24 md:pt-32 pb-16 md:pb-20 relative z-10 text-center flex flex-col items-center justify-center min-h-screen">

        <div className="mb-8 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-sm font-medium text-zinc-300">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Running Community Manager
        </div>

        <h1 className="text-4xl sm:text-6xl md:text-8xl font-black mb-6 tracking-tight">
          记录. <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#FC4C02] to-orange-400">竞争.</span> 进化.
        </h1>

        <p className="text-zinc-400 text-lg md:text-xl max-w-2xl mx-auto mb-12 font-light leading-relaxed">
          跑团一站式管理平台。自动同步 Strava 跑步数据，
          团队排行榜实时竟跑，AI 教练个性化训练建议直达面板。
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4">
          {authLoading ? (
            <div className="w-48 h-12 bg-white/5 rounded-xl animate-pulse" />
          ) : isLoggedIn ? (
            <>
              <button
                onClick={() => router.push("/dashboard")}
                className="px-8 py-3 bg-gradient-to-r from-[#FC4C02] to-orange-500 text-white font-bold rounded-xl transition-all hover:shadow-lg hover:shadow-[#FC4C02]/30 w-full sm:w-auto flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                进入 Dashboard
              </button>
              <StravaConnectBtn />
            </>
          ) : (
            <>
              <button
                onClick={() => setModalOpen(true)}
                className="px-8 py-3 bg-white text-black font-bold rounded-xl transition-all hover:bg-zinc-100 hover:shadow-lg hover:shadow-white/10 w-full sm:w-auto flex items-center justify-center gap-3"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
                </svg>
                登录 / 注册
              </button>
              <StravaConnectBtn />
            </>
          )}

          <button
            onClick={() => router.push("/leaderboard")}
            className="px-6 py-3 bg-white/5 border border-white/10 hover:bg-white/10 text-white font-semibold rounded-xl transition-all w-full sm:w-auto"
          >
            查看排行榜
          </button>
        </div>

        {/* Logged-in user status strip */}
        {isLoggedIn && (
          <div className="mt-6 flex items-center gap-3 text-sm text-zinc-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            已登录：{user.email || user.phoneNumber || user.displayName || "用户"}
            <button
              onClick={() => signOut(auth)}
              className="text-zinc-600 hover:text-red-400 transition-colors underline underline-offset-2"
            >
              登出
            </button>
          </div>
        )}

        <div className="mt-16 md:mt-24 grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 max-w-5xl mx-auto w-full text-left">
          {/* Card 1 */}
          <div className="bg-white/5 border border-white/10 p-6 rounded-2xl backdrop-blur-sm">
            <h3 className="text-xl font-bold mb-2 text-white">自动同步</h3>
            <p className="text-zinc-400 text-sm">连接一次 Strava，即可自动同步你的跑步数据、配速和心率。</p>
          </div>
          {/* Card 2 */}
          <div className="bg-white/5 border border-white/10 p-6 rounded-2xl backdrop-blur-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-[#FC4C02]/20 rounded-full blur-2xl" />
            <h3 className="text-xl font-bold mb-2 text-white relative z-10">智能目标</h3>
            <p className="text-zinc-400 text-sm relative z-10">设定每周或每月跑量目标，追踪完成率并与跑友比拼。</p>
          </div>
          {/* Card 3 */}
          <div className="bg-white/5 border border-white/10 p-6 rounded-2xl backdrop-blur-sm">
            <h3 className="text-xl font-bold mb-2 text-white">AI 分析</h3>
            <p className="text-zinc-400 text-sm">获取配速、心率区间和恢复建议等 AI 智能反馈。</p>
          </div>
        </div>

      </main>

      {/* Auth Modal */}
      <AuthModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSuccess={() => router.push("/dashboard")}
      />
    </div>
  );
}
